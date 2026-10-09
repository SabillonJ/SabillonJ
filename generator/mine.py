"""Aggregate my commits in private repositories into data/work.json.

Runs on my machine, where the private clones live. Only counts leave the repo:
no code, no commit messages, no file names.

    python generator/mine.py --author SabillonJ --branch origin/Dev path/to/repo [more repos]
"""
import argparse
import collections
import datetime
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# First match wins, so every commit lands in exactly one area and the bars add up.
AREAS = [
    ("vision", r"bloquera|block line|block production|block pallet|yolo|camera|nvr|waste|broken"),
    ("assistant", r"whatsapp|chatbot|ollama|advisor|webhook|voice note"),
    ("people", r"\bhr\b|rrhh|recursos humanos|employee|clock|biotime|sick|incapacit|shift|overtime|bonus|d[eé]cim|payroll|labor|naf\b"),
    ("gate", r"access|\bpass(es)?\b|gate|visitor|porter|qr scanner|single-use scan|entry and exit"),
    ("beams", r"beam|offer|viga|quote|tramo|span"),
    ("cement", r"cement|cenosa|silo|freight|flete|factsap|cardex|contract|tonnage"),
    ("wall", r"\btv\b|wall|4k|radio|music"),
    ("warehouse", r"supplier|payment|exchange rate|warehouse|almacen|inventory|raw material|scale|bascula|boleta|dispatch|price change|invoice|purchase-orders|oc dashboard|fuel|tank"),
    ("platform", r"test|guard|outage|theme|halloween|galax|login|auth|401|token|notification|maintenance|menu|module|pwa|service worker|health check|api is down|skill|agent|rules|traps|ticket"),
]

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

    areas = collections.Counter()
    languages = collections.Counter()
    files_per_commit = []
    dates = []
    for repo in args.repos:
        log = git(repo, "log", args.branch, f"--author={args.author}", "--no-merges", "--name-only", "--format=@@%ad|%s", "--date=short")
        files = None
        for line in log.splitlines():
            if line.startswith("@@"):
                if files is not None:
                    files_per_commit.append(files)
                files = 0
                date, subject = line[2:].split("|", 1)
                dates.append(date)
                area = next((key for key, pattern in AREAS if re.search(pattern, subject, re.I)), "other")
                areas[area] += 1
            elif line.strip():
                files += 1
                languages[LANGUAGES.get(Path(line).suffix.lower(), "Other")] += 1
        if files is not None:
            files_per_commit.append(files)

    if not dates:
        sys.exit("No commits found for that author and branch.")

    work = {
        "asOf": datetime.date.today().isoformat(),
        "repos": len(args.repos),
        "commits": len(dates),
        "firstCommit": min(dates),
        "lastCommit": max(dates),
        "medianFilesPerCommit": int(statistics.median(files_per_commit)),
        "areas": dict(areas.most_common()),
        "languages": dict(languages.most_common()),
    }
    target = ROOT / "data" / "work.json"
    target.write_text(json.dumps(work, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(work, indent=2))


if __name__ == "__main__":
    main()
