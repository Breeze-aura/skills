"""Run the installer against disposable, real directories.

These tests catch broken links, unsafe conflict replacement, partial mutation,
and dry-run side effects. They do not inspect implementation text.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "sync_skills.py"


class SyncSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.destination = self.root / "installed"

    def make_skill(self, name="sample-skill"):
        skill = self.source / name
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Use when testing skill installation.\n---\n\n# Sample\n",
            encoding="utf-8",
        )
        return skill

    def run_sync(self, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--source", str(self.source),
             "--destination", str(self.destination), *extra],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def test_source_edits_are_visible_through_installed_link(self):
        skill = self.make_skill()
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.destination / "sample-skill"
        self.assertEqual(target.resolve(), skill.resolve())
        (skill / "notes.md").write_text("a new revision", encoding="utf-8")
        self.assertEqual((target / "notes.md").read_text(encoding="utf-8"), "a new revision")

    def test_repeated_sync_preserves_same_link(self):
        skill = self.make_skill()
        first = self.run_sync()
        second = self.run_sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.destination / "sample-skill").resolve(), skill.resolve())

    def test_conflict_preserves_existing_skill_without_partial_install(self):
        self.make_skill("a-new-skill")
        self.make_skill("z-existing-skill")
        existing = self.destination / "z-existing-skill"
        existing.mkdir(parents=True)
        (existing / "personal.txt").write_text("keep me", encoding="utf-8")
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((existing / "personal.txt").read_text(encoding="utf-8"), "keep me")
        self.assertFalse((self.destination / "a-new-skill").exists())

    def test_dry_run_does_not_create_destination(self):
        self.make_skill()
        result = self.run_sync("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.destination.exists())

    def test_selecting_one_skill_leaves_others_uninstalled(self):
        self.make_skill("selected-skill")
        self.make_skill("another-skill")
        result = self.run_sync("--skill", "selected-skill")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.destination / "selected-skill" / "SKILL.md").is_file())
        self.assertFalse((self.destination / "another-skill").exists())

    def test_unknown_skill_does_not_create_destination(self):
        self.make_skill()
        result = self.run_sync("--skill", "does-not-exist")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_missing_source_fails_visibly(self):
        self.source.rmdir()
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source", result.stderr.lower())
        self.assertFalse(self.destination.exists())

    def test_mismatched_manifest_name_prevents_installation(self):
        skill = self.make_skill()
        (skill / "SKILL.md").write_text(
            "---\nname: another-name\ndescription: Use when testing.\n---\n# Sample\n",
            encoding="utf-8",
        )
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_malformed_yaml_prevents_any_installation(self):
        self.make_skill("a-valid-skill")
        broken = self.make_skill("z-broken-skill")
        (broken / "SKILL.md").write_text(
            '---\nname: z-broken-skill\ndescription: "unterminated\n---\n# Broken\n',
            encoding="utf-8",
        )
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_non_string_or_empty_description_prevents_installation(self):
        skill = self.make_skill()
        for description in ("[]", "null", '"  "', "\nmetadata: example"):
            with self.subTest(description=description):
                (skill / "SKILL.md").write_text(
                    f"---\nname: sample-skill\ndescription: {description}\n---\n# Broken\n",
                    encoding="utf-8",
                )
                result = self.run_sync()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.destination.exists())

    def test_valid_yaml_comments_and_multiline_description_install(self):
        skill = self.make_skill()
        (skill / "SKILL.md").write_text(
            "---\nname: 'sample-skill' # a valid YAML comment\n"
            "description: >\n  Use when testing\n  skill installation.\n---\n# Sample\n",
            encoding="utf-8",
        )
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "sample-skill").resolve(), skill.resolve())

    def test_source_path_brackets_are_literal_even_with_a_decoy(self):
        self.source.rmdir()
        self.source = self.root / "source[x]"
        self.source.mkdir()
        skill = self.make_skill()
        (skill / "marker.txt").write_text("correct source", encoding="utf-8")
        decoy = self.root / "sourcex" / "sample-skill"
        decoy.mkdir(parents=True)
        (decoy / "marker.txt").write_text("wrong source", encoding="utf-8")
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.destination / "sample-skill"
        self.assertEqual(target.resolve(), skill.resolve())
        self.assertEqual((target / "marker.txt").read_text(encoding="utf-8"), "correct source")

    def test_aliased_source_cannot_install_into_itself(self):
        actual = self.root / "outside" / "sample-skill"
        actual.mkdir(parents=True)
        (actual / "SKILL.md").write_text(
            "---\nname: sample-skill\ndescription: Use when testing.\n---\n# Sample\n",
            encoding="utf-8",
        )
        alias = self.source / "sample-skill"
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 f"New-Item -ItemType Junction -Path '{alias}' -Target '{actual}' | Out-Null"],
                capture_output=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            alias.symlink_to(actual, target_is_directory=True)
        self.destination = actual / "installed"
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
