"""Link this repository's authored skills into Codex's user skills directory.

Uses junctions on Windows and symlinks elsewhere. Existing paths are never
replaced, and every source and target is checked before creating links.
"""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    yaml = None


NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "skills"


def check_manifest(skill):
    """Parse actual YAML before allowing filesystem mutations."""
    if yaml is None:
        raise ValueError("PyYAML is required; run: python -m pip install -r requirements-dev.txt")
    content = (skill / "SKILL.md").read_text(encoding="utf-8-sig")
    match = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", content, re.DOTALL)
    if not match:
        raise ValueError(f"Missing frontmatter: {skill / 'SKILL.md'}")
    try:
        manifest = yaml.safe_load(match.group(1))
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML frontmatter: {skill / 'SKILL.md'}: {error}") from error
    if not isinstance(manifest, dict):
        raise ValueError(f"Frontmatter must be a mapping: {skill / 'SKILL.md'}")
    name = manifest.get("name")
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name) or len(name) > 64 or name != skill.name:
        raise ValueError(f"Manifest name must match source folder: {skill}")
    description = manifest.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        raise ValueError(f"Description must be a nonempty string of at most 1024 characters: {skill / 'SKILL.md'}")
    if not content[match.end():].strip():
        raise ValueError(f"Skill instructions are empty: {skill / 'SKILL.md'}")


def discover_skills(source, selected=None):
    if not source.is_dir():
        raise ValueError(f"Skill source directory does not exist: {source}")
    candidates = sorted(
        child for child in source.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    )
    if selected:
        candidates = [child for child in candidates if child.name == selected]
    if not candidates:
        raise ValueError(f"No matching skills in source: {source}")
    for skill in candidates:
        check_manifest(skill)
    return candidates


def create_link(source, target):
    if os.name != "nt":
        target.symlink_to(source, target_is_directory=True)
        return
    # Pass paths as environment values, never interpolate them into shell code.
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "$literalSource = [System.Management.Automation.WildcardPattern]::Escape($env:PERSONAL_SKILL_SOURCE); "
        "New-Item -ItemType Junction -Path $env:PERSONAL_SKILL_LINK "
        "-Target $literalSource | Out-Null"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=dict(os.environ, PERSONAL_SKILL_LINK=str(target), PERSONAL_SKILL_SOURCE=str(source)),
        capture_output=True, timeout=30,
    )
    if result.returncode:
        message = result.stderr.decode(errors="replace").strip()
        raise OSError(f"Could not create link {target}: {message}")


def sync_skills(source, destination, selected=None, dry_run=False):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if destination == source or source in destination.parents:
        raise ValueError("Destination must be outside the skill source directory")
    skills = discover_skills(source, selected)
    planned = []
    for skill in skills:
        resolved_skill = skill.resolve()
        if destination == resolved_skill or resolved_skill in destination.parents:
            raise ValueError(f"Destination must be outside every resolved source skill: {resolved_skill}")
        target = destination / skill.name
        exists = os.path.lexists(target)
        if exists and target.resolve() != resolved_skill:
            raise ValueError(f"Existing skill conflict; nothing replaced: {target}")
        planned.append((resolved_skill, target, exists))
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)
    for skill, target, exists in planned:
        if exists:
            print(f"Already linked: {target} -> {skill}")
        elif dry_run:
            print(f"Would link: {target} -> {skill}")
        else:
            create_link(skill, target)
            if target.resolve() != skill:
                raise OSError(f"Created link does not point to the expected source: {target}")
            print(f"Linked: {target} -> {skill}")
    return len(planned)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination", type=Path, default=Path.home() / ".agents" / "skills")
    parser.add_argument("--skill", help="Install only this folder name; default: all authored skills")
    parser.add_argument("--dry-run", action="store_true", help="Check and show links without writing")
    args = parser.parse_args()
    try:
        sync_skills(args.source, args.destination, args.skill, args.dry_run)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Skill sync failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
