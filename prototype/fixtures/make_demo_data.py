"""Builds the demo data: replay recordings, expected outputs and Acme's HR/SSO/contract files.

    python fixtures/make_demo_data.py [out_dir]

Everything is fake and deterministic: fake people at acme.example, fake IDs, no real data.
`expected.json` holds the right answer per user, computed from the ground truth here, not by
running the engine, so the contract tests check the engine against something independent.

Acme / Calendly matches TRD §11: 48 users = 6 left + 11 inactive + 31 active; 60 seats.
"""

from __future__ import annotations

import csv
import io
import json
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

RECORDED_AT = datetime(2026, 10, 29, 9, 0, 0, tzinfo=UTC)
DOMAIN = "acme.example"
WINDOW_DAYS = 90
NS = uuid.UUID("6f1c9a52-1d0b-4a8e-9f57-0c2d7d3b9e11")

FIRST = [
    "Aarav",
    "Abel",
    "Ada",
    "Aiko",
    "Alba",
    "Alma",
    "Amir",
    "Ana",
    "Anika",
    "Arlo",
    "Asha",
    "Aziz",
    "Beatriz",
    "Bilal",
    "Bo",
    "Carmen",
    "Chidi",
    "Clara",
    "Dara",
    "Dev",
    "Diego",
    "Eitan",
    "Elif",
    "Elio",
    "Emeka",
    "Esme",
    "Farah",
    "Femi",
    "Freya",
    "Gael",
    "Hana",
    "Hugo",
    "Ines",
    "Isak",
    "Ivy",
    "Jalen",
    "Jonas",
    "Kai",
    "Kenji",
    "Lara",
    "Leila",
    "Lior",
    "Luca",
    "Maya",
    "Mei",
    "Milo",
    "Nadia",
    "Nico",
    "Noor",
    "Omar",
    "Oona",
    "Pablo",
    "Priya",
    "Quinn",
    "Rafa",
    "Rhea",
    "Rumi",
    "Sami",
    "Sana",
    "Soren",
    "Tara",
    "Teo",
    "Uma",
    "Vera",
    "Wren",
    "Yara",
    "Yusuf",
    "Zara",
    "Zeke",
]
LAST = [
    "Abara",
    "Bauer",
    "Castillo",
    "Dahl",
    "Eze",
    "Fontaine",
    "Garcia",
    "Haddad",
    "Ito",
    "Jensen",
    "Kaur",
    "Larsen",
    "Moreau",
    "Nakamura",
    "Okafor",
    "Petrov",
    "Quist",
    "Rossi",
    "Sato",
    "Tanaka",
    "Ueda",
    "Varga",
    "Weber",
    "Xu",
    "Yilmaz",
    "Zhou",
    "Alvarez",
    "Brandt",
    "Chen",
    "Duarte",
    "Ekman",
    "Fischer",
    "Gupta",
    "Holm",
    "Ivanova",
]


def iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000000Z")


def fake_id(*parts: object) -> str:
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def people_pool(rng: random.Random, count: int) -> list[dict[str, Any]]:
    names = [f"{f} {last}" for f in FIRST for last in LAST]
    rng.shuffle(names)
    out = []
    for i, name in enumerate(names[:count]):
        first, surname = name.split(" ")
        out.append({"i": i, "name": name, "email": f"{first.lower()}.{surname.lower()}@{DOMAIN}"})
    return out


def days_ago(rng: random.Random, low: int, high: int) -> datetime:
    return RECORDED_AT - timedelta(days=rng.randint(low, high), hours=rng.randint(0, 9), minutes=rng.choice([0, 30]))


# --- Calendly (T2) -----------------------------------------------------------------


def calendly(rng: random.Random, pool: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    api = "https://api.calendly.com"
    org = f"{api}/organizations/{fake_id('cal-org')}"
    members = pool[:48]
    left, inactive, active = members[:6], members[6:17], members[17:]
    roles = {m["i"]: "user" for m in members}
    roles[active[0]["i"]] = "owner"  # the token owner, in Marketing Ops
    for m in (active[1], active[2], inactive[0]):
        roles[m["i"]] = "admin"
    uri = {m["i"]: f"{api}/users/{fake_id('cal-user', m['i'])}" for m in members}

    hosted = {m["i"]: 0 for m in members}
    last_hosted: dict[int, datetime] = {}
    events: list[dict[str, Any]] = []

    def add_event(hosts: list[dict[str, Any]], start: datetime, counts: bool) -> None:
        events.append(
            {
                "uri": f"{api}/scheduled_events/{fake_id('cal-event', len(events))}",
                "name": rng.choice(["Intro call", "Demo", "Weekly sync", "Interview", "Office hours"]),
                "status": "active",
                "start_time": iso(start),
                "end_time": iso(start + timedelta(minutes=30)),
                "event_memberships": [
                    {"user": uri[h["i"]], "user_email": h["email"], "user_name": h["name"]} for h in hosts
                ],
            }
        )
        if counts:
            for h in hosts:
                hosted[h["i"]] += 1
                last_hosted[h["i"]] = max(last_hosted.get(h["i"], start), start)

    for m in active:
        for _ in range(rng.randint(1, 7)):
            add_event([m], days_ago(rng, 1, WINDOW_DAYS - 1), True)
    for _ in range(8):  # co-hosted meetings count for every host
        a, b = rng.sample(active, 2)
        add_event([a, b], days_ago(rng, 1, WINDOW_DAYS - 1), True)
    for m in left[:2]:  # met people before they left
        add_event([m], days_ago(rng, 60, WINDOW_DAYS - 1), True)
    # Traps: a future meeting and an old one, both by inactive people. Neither may count.
    add_event([inactive[1]], RECORDED_AT + timedelta(days=3), False)
    add_event([inactive[2]], RECORDED_AT - timedelta(days=WINDOW_DAYS + 5), False)
    events.sort(key=lambda e: e["start_time"])

    me = {
        "resource": {
            "uri": uri[active[0]["i"]],
            "name": active[0]["name"],
            "email": active[0]["email"],
            "current_organization": org,
        }
    }
    member_rows = [
        {
            "uri": f"{api}/organization_memberships/{fake_id('cal-mem', m['i'])}",
            "role": roles[m["i"]],
            "user": {
                "uri": uri[m["i"]],
                "name": m["name"],
                "email": m["email"].upper() if m["i"] % 9 == 0 else m["email"],
            },
            "organization": org,
        }
        for m in members
    ]
    interactions = [{"method": "GET", "url": f"{api}/users/me", "query": {}, "body": me}]
    members_url, members_query = f"{api}/organization_memberships", {"organization": org, "count": "*?"}
    interactions += _cursor_pages(
        members_url,
        members_query,
        member_rows,
        [25],
        "page_token",
        lambda rows, token: {
            "collection": rows,
            "pagination": _calendly_paging(rows, token, members_url, members_query),
        },
    )
    # Calendly's date range and status filter are optional: without them the API returns every event, and the
    # window still applies. The recorded events are all active.
    event_query = {
        "organization": org,
        "min_start_time": "*?",
        "max_start_time": "*?",
        "status": "*?",
        "count": "*?",
    }
    events_url = f"{api}/scheduled_events"
    interactions += _cursor_pages(
        events_url,
        event_query,
        events,
        [100],
        "page_token",
        lambda rows, token: {"collection": rows, "pagination": _calendly_paging(rows, token, events_url, event_query)},
    )
    recording = {"app": "calendly", "recorded_at": iso(RECORDED_AT), "variables": {}, "interactions": interactions}
    expected = {
        uri[m["i"]]: {
            "email": m["email"],
            "name": m["name"],
            "role": roles[m["i"]],
            "status": "active",
            "is_admin": roles[m["i"]] in ("owner", "admin"),
            "usage_available": True,
            "usage_is_proxy": True,
            "usage_metric_label": "Meetings hosted (90 days)",
            "usage_metric_value": hosted[m["i"]],
            "usage_window_days": WINDOW_DAYS,
            "last_active_at": _z(last_hosted.get(m["i"])),
        }
        for m in members
    }
    truth = {"members": members, "left": left, "inactive": inactive, "active": active, "token_owner": active[0]}
    return recording, expected, truth


# --- Zendesk (T1) ------------------------------------------------------------------


def zendesk(rng: random.Random, pool: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    subdomain = "acme-demo"
    api = f"https://{subdomain}.zendesk.com"
    agents = pool[30:66]
    service = {"i": -1, "name": "Zendesk Sync (service account)", "email": f"zendesk-sync@{DOMAIN}"}
    users = [service, *agents]
    rows, expected = [], {}
    for n, person in enumerate(users):
        role = "admin" if n < 4 else "agent"
        suspended = n in (10, 21)
        if person is service:
            last = RECORDED_AT - timedelta(hours=2)
        elif n % 12 == 5:
            last = None
        elif n % 5 == 3:
            last = days_ago(rng, 31, 120)
        else:
            last = days_ago(rng, 0, 29)
        user_id = 900000000001 + n
        rows.append(
            {
                "id": user_id,
                "url": f"{api}/api/v2/users/{user_id}.json",
                "name": person["name"],
                "email": person["email"],
                "role": role,
                "active": True,
                "suspended": suspended,
                "last_login_at": last.strftime("%Y-%m-%dT%H:%M:%SZ") if last else None,
            }
        )
        expected[str(user_id)] = {
            "email": person["email"],
            "name": person["name"],
            "role": role,
            "status": "suspended" if suspended else "active",
            "is_admin": role == "admin",
            "usage_available": True,
            "usage_is_proxy": False,
            "usage_metric_label": "Last login",
            "usage_metric_value": None,
            "usage_window_days": None,
            "last_active_at": _z(last),
        }
    token = {
        "method": "POST",
        "url": f"{api}/oauth/tokens",
        "query": {},
        "body": {"access_token": "replay-access-token-not-secret", "token_type": "bearer", "scope": "read"},
    }
    users_url, users_query = f"{api}/api/v2/users", {"role[]": ["agent", "admin"], "page[size]": "*?"}
    pages = _cursor_pages(
        users_url,
        users_query,
        rows,
        [20],
        "page[after]",
        lambda page, cursor: {
            "users": page,
            "meta": {"has_more": cursor is not None, "after_cursor": cursor, "before_cursor": None},
            "links": {"next": _page_link(users_url, users_query, "page[after]", cursor), "prev": None},
        },
    )
    recording = {
        "app": "zendesk",
        "recorded_at": iso(RECORDED_AT),
        "variables": {"subdomain": subdomain},
        "interactions": [token, *pages],
    }
    return recording, expected, {"agents": agents, "service": service}


# --- Notion (T3) -------------------------------------------------------------------


def notion(rng: random.Random, pool: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    api = "https://api.notion.com/v1"
    people = pool[:87]
    results: list[dict[str, Any]] = []
    expected = {}
    for person in people:
        user_id = fake_id("notion-user", person["i"])
        results.append(
            {
                "object": "user",
                "id": user_id,
                "type": "person",
                "name": person["name"],
                "avatar_url": None,
                "person": {"email": person["email"]},
            }
        )
        expected[user_id] = {
            "email": person["email"],
            "name": person["name"],
            "status": "active",
            "usage_available": False,
            "usage_is_proxy": False,
            "usage_metric_value": None,
            "last_active_at": None,
        }
    for n in range(3):  # bots are not seats; the records_path filter drops them
        results.insert(
            n * 30 + 5,
            {"object": "user", "id": fake_id("notion-bot", n), "type": "bot", "name": f"Automation {n + 1}", "bot": {}},
        )
    pages = _cursor_pages(
        f"{api}/users",
        {"page_size": "*?"},
        results,
        [45],
        "start_cursor",
        lambda page, cursor: {"object": "list", "results": page, "next_cursor": cursor, "has_more": cursor is not None},
    )
    recording = {"app": "notion", "recorded_at": iso(RECORDED_AT), "variables": {}, "interactions": pages}
    return recording, expected, {"people": people}


# --- Slack (T2) --------------------------------------------------------------------

SLACK_ZONES = [
    ("America/Los_Angeles", "Pacific Daylight Time", -25200),
    ("America/New_York", "Eastern Daylight Time", -14400),
    ("Europe/London", "Greenwich Mean Time", 0),
    ("Asia/Kolkata", "India Standard Time", 19800),
]
SLACK_TITLES = [
    "Account Executive", "Support Specialist", "Software Engineer", "Product Designer", "Marketing Manager",
    "Recruiter", "Data Analyst", "Finance Partner", "Customer Success Manager", "Engineering Manager",
]  # fmt: skip
SLACK_AGENTS = {
    "desktop": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Slack/4.46.101 Chrome/138.0.7204.100 Electron/37.2.2 Safari/537.36",
    "ios": "com.tinyspeck.chatlyio/25.10.10 (iPhone; iOS 18.6.2; Scale/3.00)",
    "android": "com.Slack/25.10.10.0 (Linux; Android 15; Pixel 8)",
    "web": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
}
GUEST_DOMAIN = "brightpath-studio.example"  # an outside agency: guests are not in Acme's HR data


def slack_id(prefix: str, *parts: object) -> str:
    return prefix + "0" + uuid.uuid5(NS, "/".join(str(p) for p in ("slack", *parts))).hex[:9].upper()


def slack(
    rng: random.Random, pool: list[dict[str, Any]], left: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Acme on Slack Business+: 140 people, 6 guests, 4 bots. users.list + team.accessLogs (TRD §4 tiers)."""
    api = "https://slack.com/api"
    team = slack_id("T", "team")
    window = 90
    left_ids = {p["i"] for p in left}
    gone = {p["i"] for p in left[:4]}  # offboarded: deactivated in Slack. left[4:] left Acme but are still active
    staff = [p for p in pool if p["i"] not in left_ids]
    names = {p["name"] for p in pool}
    guests = []
    while len(guests) < 6:
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if name not in names:
            names.add(name)
            first, last = name.split(" ")
            guests.append(
                {"i": f"g{len(guests)}", "name": name, "email": f"{first.lower()}.{last.lower()}@{GUEST_DOMAIN}"}
            )

    def last_seen(p: dict[str, Any]) -> datetime:
        if p["i"] in gone:
            return days_ago(rng, 45, 120)
        if p["i"] in left_ids:
            return days_ago(rng, 41, 60)  # before they left
        if p["i"] in (70, 71):
            return days_ago(rng, 35, 80)  # on leave
        r = rng.random()
        if r < 0.80:
            return days_ago(rng, 0, 6)
        if r < 0.89:
            return days_ago(rng, 7, 29)
        if r < 0.97:
            return days_ago(rng, 30, 89)
        return days_ago(rng, 95, 200)  # no sign-in in the 90-day window

    def ts(value: datetime) -> int:
        return int(value.timestamp())

    members: list[dict[str, Any]] = []
    logins: list[dict[str, Any]] = []
    expected: dict[str, Any] = {}
    people = [(p, "member") for p in pool] + [(g, "multi") for g in guests[:4]] + [(g, "single") for g in guests[4:]]
    roles = {staff[0]["i"]: "Primary owner", staff[1]["i"]: "Owner", **{p["i"]: "Admin" for p in staff[2:5]}}
    for n, (p, kind) in enumerate(people):
        uid = slack_id("U", p["i"])
        first, last = p["name"].split(" ")
        zone = rng.choice(SLACK_ZONES)
        deleted = p["i"] in gone
        role = roles.get(p["i"], "Member") if kind == "member" else f"{kind.title()}-channel guest"
        seen = last_seen(p) if kind == "member" else days_ago(rng, 0, 20 if n % 3 else 50)
        members.append(
            {
                "id": uid, "team_id": team, "name": f"{first.lower()}.{last.lower()}", "deleted": deleted,
                "color": rng.choice(["9f69e7", "4bbe2e", "e7392d", "3c989f", "e0a729"]),
                "real_name": p["name"], "tz": zone[0], "tz_label": zone[1], "tz_offset": zone[2],
                "profile": {
                    "title": rng.choice(SLACK_TITLES) if kind == "member" else "Contractor, Brightpath Studio",
                    "real_name": p["name"], "display_name": first, "email": p["email"],
                    "first_name": first, "last_name": last, "team": team,
                },
                "is_admin": role in ("Primary owner", "Owner", "Admin"), "is_owner": role in ("Primary owner", "Owner"),
                "is_primary_owner": role == "Primary owner", "is_restricted": kind != "member",
                "is_ultra_restricted": kind == "single", "is_bot": False, "is_app_user": False,
                "updated": ts(seen - timedelta(days=rng.randint(1, 300))), "has_2fa": n % 4 != 0,
            }
        )  # fmt: skip
        # One access-log row per device (user + IP + user agent); the newest is the last sign-in.
        ip = f"203.0.113.{n % 250 + 1}" if n % 2 else f"198.51.100.{n % 250 + 1}"
        for d, device in enumerate(rng.sample(sorted(SLACK_AGENTS), rng.randint(1, 3))):
            latest = seen - timedelta(days=rng.randint(1, 20) if d else 0, hours=d)
            logins.append(
                {
                    "user_id": uid, "username": f"{first.lower()}.{last.lower()}",
                    "date_first": ts(latest - timedelta(days=rng.randint(30, 400))), "date_last": ts(latest),
                    "count": rng.randint(5, 900), "ip": ip, "user_agent": SLACK_AGENTS[device],
                    "isp": "Example Broadband", "country": "US", "region": "California",
                }
            )  # fmt: skip
        expected[uid] = {
            "email": p["email"],
            "name": p["name"],
            "role": role,
            "status": "deactivated" if deleted else "active",
            "is_admin": role in ("Primary owner", "Owner", "Admin"),
            "is_billable": not deleted and kind != "single",  # single-channel guests are free
            "usage_available": True,
            "usage_is_proxy": False,
            "usage_metric_label": "Last sign-in",
            "usage_metric_value": None,
            "usage_window_days": window,
            "last_active_at": _z(seen) if RECORDED_AT - seen <= timedelta(days=window) else None,
        }
    # Not seats: Slackbot (listed with is_bot false) and the workspace's apps.
    members.insert(0, {
        "id": "USLACKBOT", "team_id": team, "name": "slackbot", "deleted": False, "real_name": "Slackbot",
        "profile": {"real_name": "Slackbot", "display_name": "Slackbot", "first_name": "slackbot", "last_name": ""},
        "is_admin": False, "is_owner": False, "is_primary_owner": False, "is_restricted": False,
        "is_ultra_restricted": False, "is_bot": False, "is_app_user": False, "updated": 0,
    })  # fmt: skip
    for n, bot in enumerate(["Standup bot", "Deploy notifier", "Polly"]):
        members.insert(40 * (n + 1), {
            "id": slack_id("U", "bot", n), "team_id": team, "name": bot.lower().replace(" ", "_"), "deleted": False,
            "real_name": bot, "profile": {"real_name": bot, "bot_id": slack_id("B", "bot", n)},
            "is_admin": False, "is_owner": False, "is_primary_owner": False, "is_restricted": False,
            "is_ultra_restricted": False, "is_bot": True, "is_app_user": False, "updated": ts(RECORDED_AT) - 86400 * n,
        })  # fmt: skip
    logins.sort(key=lambda row: -row["date_last"])  # newest first, as Slack returns them

    def page(key: str) -> Any:
        return lambda rows, cursor: {"ok": True, key: rows, "response_metadata": {"next_cursor": cursor or ""}}

    interactions = _cursor_pages(f"{api}/users.list", {"limit": "*?"}, members, [80], "cursor", page("members"))
    interactions += _cursor_pages(f"{api}/team.accessLogs", {"limit": "*?"}, logins, [200], "cursor", page("logins"))
    recording = {"app": "slack", "recorded_at": iso(RECORDED_AT), "variables": {}, "interactions": interactions}
    return recording, expected


# --- Acme's HR, SSO and contract files (TRD §11) ---------------------------------------


def acme_files(
    rng: random.Random,
    pool: list[dict[str, Any]],
    cal: dict[str, Any],
    zen: dict[str, Any],
    notion_truth: dict[str, Any],
) -> dict[str, str]:
    left = {p["i"] for p in cal["left"]}
    hris = io.StringIO()
    writer = csv.writer(hris, lineterminator="\n")
    writer.writerow(["email", "employment_status", "termination_date"])
    for p in pool:
        if p["i"] in left:
            writer.writerow([p["email"], "terminated", (RECORDED_AT - timedelta(days=rng.randint(5, 40))).date()])
        elif p["i"] in (70, 71):
            writer.writerow([p["email"], "leave", ""])
        else:
            writer.writerow([p["email"], "active", ""])

    sso = io.StringIO()
    writer = csv.writer(sso, lineterminator="\n")
    writer.writerow(["email", "app", "assigned", "last_login_at"])
    for p in cal["members"]:
        writer.writerow([p["email"], "Calendly", "true", days_ago(rng, 0, 20).strftime("%Y-%m-%dT%H:%M:%SZ")])
    for p in zen["agents"]:
        writer.writerow([p["email"], "Zendesk", "true", days_ago(rng, 0, 20).strftime("%Y-%m-%dT%H:%M:%SZ")])
    for n, p in enumerate(notion_truth["people"]):
        if n % 7 == 3:
            last = ""  # never logged in through SSO
        elif n % 4 == 1:
            last = days_ago(rng, 31, 150).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            last = days_ago(rng, 0, 29).strftime("%Y-%m-%dT%H:%M:%SZ")
        writer.writerow([p["email"], "Notion", "true", last])

    contract = [
        {"app": "Calendly", "seats": 60, "annual_cost": 14400, "renewal_date": "2026-12-26"},
        {"app": "Zendesk", "seats": 40, "annual_cost": 38000, "renewal_date": "2027-02-15"},
        {"app": "Notion", "seats": 100, "annual_cost": 12000, "renewal_date": "2027-03-31"},
    ]
    return {
        "hris.csv": hris.getvalue(),
        "sso.csv": sso.getvalue(),
        "contract.json": json.dumps(contract, indent=2) + "\n",
        "notes.json": json.dumps(
            {
                "calendly_token_owner_email": cal["token_owner"]["email"],
                "zendesk_service_account": zen["service"]["email"],
            },
            indent=2,
        )
        + "\n",
    }


# --- helpers ---------------------------------------------------------------------


def _z(value: datetime | None) -> str | None:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


def _page_link(url: str, query: dict[str, Any], param: str, token: str | None) -> str | None:
    """The ready-made next-page link real APIs send next to the token (Calendly's next_page, Zendesk's links.next),
    so an AI draft that pages by link works on the recording as it would on the real API."""
    if token is None:
        return None
    fixed = [
        (k, v) for k, vs in query.items() for v in (vs if isinstance(vs, list) else [vs]) if not str(v).startswith("*")
    ]
    return f"{url}?{urlencode([*fixed, (param, token)])}"


def _calendly_paging(rows: list[Any], token: str | None, url: str, query: dict[str, Any]) -> dict[str, Any]:
    return {"count": len(rows), "next_page": _page_link(url, query, "page_token", token), "next_page_token": token}


def _cursor_pages(
    url: str, query: dict[str, Any], rows: list[Any], first_page_sizes: list[int], cursor_param: str, body: Any
) -> list[dict[str, Any]]:
    """Split rows into pages. APIs may return fewer rows than asked for; that's what exercises paging."""
    out, start, n = [], 0, 0
    while True:
        size = first_page_sizes[n] if n < len(first_page_sizes) else 100
        page = rows[start : start + size]
        start += size
        cursor_in = None if n == 0 else f"cursor-{url.rsplit('/', 1)[-1]}-{n}"
        cursor_out = f"cursor-{url.rsplit('/', 1)[-1]}-{n + 1}" if start < len(rows) else None
        q = dict(query) if cursor_in is None else {**query, cursor_param: cursor_in}
        out.append({"method": "GET", "url": url, "query": q, "body": body(page, cursor_out)})
        n += 1
        if cursor_out is None:
            return out


def build(out_dir: Path) -> None:
    rng = random.Random(20261029)
    pool = people_pool(rng, 140)
    cal_rec, cal_exp, cal_truth = calendly(rng, pool)
    zen_rec, zen_exp, zen_truth = zendesk(rng, pool)
    not_rec, not_exp, not_truth = notion(rng, pool)
    # Slack has its own seed, so adding it left the files above unchanged.
    slack_rec, slack_exp = slack(random.Random(20261030), pool, cal_truth["left"])
    apps = [("calendly", cal_rec, cal_exp), ("zendesk", zen_rec, zen_exp), ("notion", not_rec, not_exp)]
    for app, rec, exp in [*apps, ("slack", slack_rec, slack_exp)]:
        folder = out_dir / "replay" / app
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "recording.json").write_text(json.dumps(rec, indent=1) + "\n")
        (folder / "expected.json").write_text(json.dumps(exp, indent=1, sort_keys=True) + "\n")
    acme = out_dir / "acme"
    acme.mkdir(parents=True, exist_ok=True)
    for name, content in acme_files(rng, pool, cal_truth, zen_truth, not_truth).items():
        (acme / name).write_text(content)


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent)
