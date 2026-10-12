# Personal Skills Bootstrap Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Author the files in this checkout; use independent agents for behavioral validation and final review.

**Goal:** Publish Breeze-aura's personal skills repository, connect authored skills to Codex globally, and deliver the first course-paper-writing draft.

**Architecture:** `skills/` is the source of truth. Directory links provide user-level discovery without duplicate copies. A short skill entrypoint routes to four stage guides and reusable templates.

**Tech Stack:** Markdown, YAML, Python 3.11+, filesystem sync tooling; PyYAML for manifest validation before installation.

**Spec:** `docs/design.md`

## Global Constraints

- GitHub owner: `Breeze-aura`; public repository: `skills`; license: MIT.
- User skills directory: `~/.agents/skills/`; do not replace unrelated skills.
- Course scope: 2000–5000 Chinese characters, four confirmed stages, user-authored judgments.
- Preserve local handoff and real coursework outside Git tracking.

## Review Focus

- Conflicting names: preserve existing installation and report the conflict.
- Missing source or malformed frontmatter: fail visibly, without partial installation.
- Topic changes after confirmation: invalidate affected evidence and outline.
- Missing/full-text-inaccessible sources: leave unverified material out of the final paper.
- First-use request: stay within Stage 1 and ask for the user's direction.

### Task 1: Repository and repeatable global installation

**Files:** `README.md`, `LICENSE`, `AGENTS.md`, `.gitignore`, `tools/sync_skills.py`, `tools/validate_skills.py`, `tests/test_sync_skills.py`, `requirements-dev.txt`, `.github/workflows/validate.yml`.

**Interfaces:** Sync CLI `--source PATH --destination PATH [--skill NAME] [--dry-run]`; validation CLI `--root PATH`. Success exits 0; invalid source or conflict exits nonzero.

- [ ] Write subprocess integration tests asserting the target can read source files and source edits appear through the link; assert conflict preservation and dry-run causes no writes.
- [ ] Run `python -m unittest discover -s tests -v`; expect failure because sync implementation does not exist.
- [ ] Implement preflight validation, non-destructive junction/symlink installation, idempotent repeated invocation, and development validation.
- [ ] Run the tests; expect all to pass.
- [ ] Initialize Git on `main`, configure the Aura remote, and retain handoff as an ignored local file.

### Task 2: Course-paper-writing draft

**Files:** `skills/course-paper-writing/`, `prompts/course-paper-start.md`, `docs/evaluation.md`, `ROADMAP.md`.

**Interfaces:** Required frontmatter `name`/`description`; implicit invocation enabled; project state template stores stage, gate evidence, and user text paths.

- [ ] Run first-use baseline without the skill; record concrete premature thesis/outline behavior.
- [ ] Write entrypoint, four stage guides, outline templates for four paper types, research pack and project-state templates, and a synthetic Stage 1 example.
- [ ] Run the same first-use request with the skill, then test resumed state and unavailable evidence using independent agents.
- [ ] Run `python tools/validate_skills.py` and the bundled skill-creator validator; expect pass.
- [ ] Run `python tools/sync_skills.py`; verify target resolution and Codex `skills/list` discovery.

### Task 3: Verify and publish

**Files:** `docs/evaluation.md`, `.work/bootstrap-progress.md` (local only).

**Interfaces:** Local commit and `origin/main` point to the same SHA.

- [ ] Review all public files for private material and incomplete scaffolds.
- [ ] Obtain independent final review of installation behavior and skill semantics; fix substantive issues and verify.
- [ ] Run `python -m unittest discover -s tests -v`, `python tools/validate_skills.py`, and `git diff --check`.
- [ ] Commit and push to Aura's `main`; verify the remote SHA and GitHub metadata.
- [ ] Report repository URL, installed skill invocation, validation, and remaining real-case work.
