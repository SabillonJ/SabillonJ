"""Measure how I change code, from private clones, into data/work.json.

Runs on my machine, where the private clones live. What it writes is a shape, not a
history: which languages the files are in, and how big a single change tends to be.
No commit count, no breakdown by subject, no commit messages, no file names — the
repositories belong to the company, and data/work.json is public.

    python generator/mine.py --author SabillonJ --branch origin/Dev path/to/repo [more repos]
"""
import argparse
import collections
import datetime
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LANGUAGES = {".cs": "C#", ".tsx": "TypeScript", ".ts": "TypeScript", ".py": "Python", ".css": "CSS", ".sql": "SQL"}


def git(repo, *args):
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        sys.exit(f"git failed in {repo}: {out.stderr.strip()}")
    return out.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--author", required=True)
    ap.add_argument("--branch", default="HEAD")
    args = ap.parse_args()

    languages = collections.Counter()
    files_per_commit = []
    for repo in args.repos:
        log = git(repo, "log", args.branch, f"--author={args.author}", "--no-merges", "--name-only", "--format=@@")
        files = None
        for line in log.splitlines():
            if line.startswith("@@"):
                if files is not None:
                    files_per_commit.append(files)
                files = 0
            elif line.strip():
                files += 1
                languages[LANGUAGES.get(Path(line).suffix.lower(), "Other")] += 1
        if files is not None:
            files_per_commit.append(files)

    if not files_per_commit:
        sys.exit("No commits found for that author and branch.")

    work = {
        "asOf": datetime.date.today().isoformat(),
        "medianFilesPerCommit": int(statistics.median(files_per_commit)),
        "languages": dict(languages.most_common()),
    }
    target = ROOT / "data" / "work.json"
    target.write_text(json.dumps(work, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(work, indent=2))


if __name__ == "__main__":
    main()
