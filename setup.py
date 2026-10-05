#!/usr/bin/env python3
"""Install every skill in this repo into Claude Code's and/or Codex CLI's
skills directory.

Each top-level directory in this repo that contains a SKILL.md is treated
as one skill. Running this script copies each one into:

    ~/.claude/skills/<skill-name>/   (Claude Code)
    ~/.codex/skills/<skill-name>/    (Codex CLI)

Both CLIs read the exact same SKILL.md + scripts/ folder structure, so a
plain copy is enough -- no build step, no dependencies beyond the Python
standard library (so this runs the same way on Windows/macOS/Linux).

Usage:
    python setup.py                 # install everywhere, all skills
    python setup.py --target claude # Claude Code only
    python setup.py --target codex  # Codex CLI only
    python setup.py --only 이어서     # install just one skill
"""
import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

TARGET_DIRS = {
    "claude": Path.home() / ".claude" / "skills",
    "codex": Path.home() / ".codex" / "skills",
}


def discover_skills():
    skills = []
    for child in sorted(REPO_ROOT.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            skills.append(child)
    return skills


def install_skill(skill_dir: Path, target_root: Path):
    target_root.mkdir(parents=True, exist_ok=True)
    dest = target_root / skill_dir.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(skill_dir, dest)
    return dest


def main():
    # Skill names/paths can contain non-ASCII characters (e.g. Korean).
    # Some terminals (notably Windows consoles on a non-UTF-8 codepage)
    # can't encode those directly and would crash print() with a
    # UnicodeEncodeError. Reconfigure stdout to UTF-8 with a safe
    # fallback so this always runs, even if the glyphs don't render.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["claude", "codex", "both"], default="both")
    ap.add_argument("--only", help="install only this skill (by directory name)")
    args = ap.parse_args()

    skills = discover_skills()
    if args.only:
        skills = [s for s in skills if s.name == args.only]
        if not skills:
            print(f"ERROR=no skill named '{args.only}' found under {REPO_ROOT}")
            sys.exit(1)

    if not skills:
        print(f"ERROR=no skills found under {REPO_ROOT} (expected <name>/SKILL.md)")
        sys.exit(1)

    targets = ["claude", "codex"] if args.target == "both" else [args.target]

    for skill_dir in skills:
        for target in targets:
            dest = install_skill(skill_dir, TARGET_DIRS[target])
            print(f"INSTALLED {skill_dir.name} -> {dest}")


if __name__ == "__main__":
    main()
