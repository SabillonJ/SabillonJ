"""Refresh data/calendar.json from GitHub.

    python generator/fetch_calendar.py

With GITHUB_TOKEN set it asks the GraphQL API; without it, or if the API fails or
comes back empty, it reads the public calendar page. Either way GitHub only reports private work when the
profile setting "Private contributions" is on.

If the answer comes back empty while the file on disk has data, the file is left
alone: a bad night must not blank the cards.
"""
import datetime
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data" / "calendar.json"
QUERY = ("query($login:String!){user(login:$login){contributionsCollection{contributionCalendar"
         "{weeks{contributionDays{date contributionCount}}}}}}")


def from_api(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    request = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": login})
    with urllib.request.urlopen(request, timeout=30) as response:
        answer = json.load(response)
    if answer.get("errors"):
        raise RuntimeError(answer["errors"][0].get("message", "GraphQL error"))
    weeks = answer["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {day["date"]: day["contributionCount"] for week in weeks for day in week["contributionDays"]}


def from_page(login):
    request = urllib.request.Request(f"https://github.com/users/{login}/contributions",
                                     headers={"User-Agent": login})
    with urllib.request.urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8", "replace")
    dates = {}
    for cell in re.findall(r"<td[^>]*>", page):
        date = re.search(r'data-date="(\d{4}-\d\d-\d\d)"', cell)
        cell_id = re.search(r'\bid="(contribution-day-component-[\d-]+)"', cell)
        if date and cell_id:
            dates[cell_id.group(1)] = date.group(1)
    if not dates:
        raise RuntimeError("the calendar page has no day cells: its markup changed")
    days = {}
    for cell_id, tip in re.findall(r'<tool-tip[^>]*\bfor="(contribution-day-component-[\d-]+)"[^>]*>([^<]*)<', page):
        count = re.match(r"\s*(\d+) contribution", tip)
        if cell_id in dates:
            days[dates[cell_id]] = int(count.group(1)) if count else 0
    return days


def main():
    login = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))["login"]
    token = os.environ.get("GITHUB_TOKEN")
    days, source = None, None
    if token:
        try:
            days, source = from_api(login, token), "GitHub GraphQL API"
        except Exception as error:   # fall through to the page
            print(f"API: {error}", file=sys.stderr)
    if not days or not any(days.values()):   # no token, an API error, or an API that sees nothing
        days, source = from_page(login), "github.com contribution calendar"

    days = {date: n for date, n in sorted(days.items()) if n}
    previous = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {"days": {}}
    if not days and previous["days"]:
        print("GitHub reported no contributions. Kept the calendar on disk. "
              "Is 'Private contributions' still on in the profile settings?", file=sys.stderr)
        return

    fetched = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6))).date().isoformat()
    TARGET.write_text(json.dumps({"login": login, "fetched": fetched, "source": source, "days": days},
                                 indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{sum(days.values())} contributions on {len(days)} days, from the {source}.")


if __name__ == "__main__":
    main()
