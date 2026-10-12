"""Validate authored skill manifests, UI metadata, and bundled Markdown links."""

import argparse
from pathlib import Path
import re
import sys

import yaml

from sync_skills import DEFAULT_SOURCE, NAME_PATTERN


def validate_skill(skill):
    failures = []
    content = (skill / "SKILL.md").read_text(encoding="utf-8-sig")
    frontmatter = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", content, re.DOTALL)
    if not frontmatter:
        return ["SKILL.md: missing YAML frontmatter"]
    manifest = yaml.safe_load(frontmatter.group(1))
    if not isinstance(manifest, dict):
        return ["SKILL.md: frontmatter must be a mapping"]
    name = manifest.get("name")
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name) or len(name) > 64 or name != skill.name:
        failures.append("SKILL.md: name must match the folder and use lowercase hyphenated words")
    description = manifest.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        failures.append("SKILL.md: description must be a nonempty string of at most 1024 characters")
    if not content[frontmatter.end():].strip():
        failures.append("SKILL.md: instructions are empty")
    for document in skill.rglob("*.md"):
        text = document.read_text(encoding="utf-8-sig")
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if re.match(r"(?:[a-z][a-z0-9+.-]*:|#)", link, re.IGNORECASE):
                continue
            path = link.split("#", 1)[0]
            target = (document.parent / path).resolve()
            if not target.is_file():
                failures.append(f"{document.relative_to(skill)}: broken link {link}")
            elif not target.is_relative_to(skill.resolve()):
                failures.append(f"{document.relative_to(skill)}: dependency outside skill package {link}")
    interface_path = skill / "agents" / "openai.yaml"
    if interface_path.is_file():
        metadata = yaml.safe_load(interface_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict) or not isinstance(metadata.get("interface"), dict):
            failures.append("agents/openai.yaml: interface must be a mapping")
        else:
            interface = metadata["interface"]
            for field in ("display_name", "short_description", "default_prompt"):
                if not isinstance(interface.get(field), str) or not interface[field].strip():
                    failures.append(f"agents/openai.yaml: missing interface.{field}")
            short = interface.get("short_description", "")
            if isinstance(short, str) and not 25 <= len(short) <= 64:
                failures.append("agents/openai.yaml: short_description must be 25–64 characters")
            prompt = interface.get("default_prompt", "")
            if isinstance(name, str) and isinstance(prompt, str) and f"${name}" not in prompt:
                failures.append("agents/openai.yaml: default_prompt must mention $skill-name")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    if not args.root.is_dir():
        print(f"Skill root does not exist: {args.root}", file=sys.stderr)
        return 1
    skills = sorted(path for path in args.root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file())
    if not skills:
        print(f"No skill manifests found in {args.root}", file=sys.stderr)
        return 1
    failed = False
    for skill in skills:
        try:
            failures = validate_skill(skill)
        except (OSError, yaml.YAMLError) as error:
            failures = [str(error)]
        if failures:
            failed = True
            for error in failures:
                print(f"FAIL {skill.name}: {error}", file=sys.stderr)
        else:
            print(f"PASS {skill.name}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
