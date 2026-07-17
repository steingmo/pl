#!/usr/bin/env python3
"""Refresh the FIXTURES array and UK TV OVERRIDES map in index.html.

Fixtures come from fixturedownload.com, UK TV picks from live-footballontv.com.
Run by .github/workflows/update-fixtures.yml on a weekly cron.
Exits non-zero (failing the workflow) if either source looks wrong.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime
from html import unescape
from zoneinfo import ZoneInfo

FEED = "https://fixturedownload.com/feed/json/epl-2026"

# Must match the order of TEAMS in index.html.
TEAMS = ['Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton',
         'Chelsea', 'Coventry', 'Crystal Palace', 'Everton', 'Fulham',
         'Hull', 'Ipswich', 'Leeds', 'Liverpool', 'Man City', 'Man Utd',
         'Newcastle', "Nott'm Forest", 'Spurs', 'Sunderland']
IDX = {t: i for i, t in enumerate(TEAMS)}

req = urllib.request.Request(FEED, headers={'User-Agent': 'Mozilla/5.0 (pl-site-updater; +https://github.com/steingmo/pl)'})
with urllib.request.urlopen(req, timeout=30) as r:
    feed = json.load(r)

assert len(feed) == 380, f"expected 380 fixtures, got {len(feed)}"
rows = []
for m in sorted(feed, key=lambda m: (m['DateUtc'], m['MatchNumber'])):
    assert m['HomeTeam'] in IDX, f"unknown team {m['HomeTeam']!r}"
    assert m['AwayTeam'] in IDX, f"unknown team {m['AwayTeam']!r}"
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:00Z', m['DateUtc']), m['DateUtc']
    iso = m['DateUtc'].replace(' ', 'T').replace(':00Z', 'Z')
    rows.append([iso, m['RoundNumber'], IDX[m['HomeTeam']], IDX[m['AwayTeam']]])

fixtures_js = json.dumps(rows, separators=(',', ':'))
html = open('index.html').read()
new = re.sub(r'const FIXTURES = \[\[.*?\]\];',
             'const FIXTURES = ' + fixtures_js + ';', html, count=1)
assert 'const FIXTURES = [[' in new, "FIXTURES line not found in index.html"

# --- UK TV picks -> OVERRIDES ---------------------------------------------
TV_URL = "https://www.live-footballontv.com/live-premier-league-football-on-tv.html"
# Site team name -> TEAMS index; codes must match TEAMS[i].c in index.html.
SITE = {'Arsenal': 0, 'Aston Villa': 1, 'AFC Bournemouth': 2, 'Brentford': 3,
        'Brighton & Hove Albion': 4, 'Chelsea': 5, 'Coventry City': 6,
        'Crystal Palace': 7, 'Everton': 8, 'Fulham': 9, 'Hull City': 10,
        'Ipswich Town': 11, 'Leeds United': 12, 'Liverpool': 13,
        'Manchester City': 14, 'Manchester United': 15, 'Newcastle United': 16,
        'Nottingham Forest': 17, 'Tottenham Hotspur': 18, 'Sunderland': 19}
CODES = ['ARS', 'AVL', 'BOU', 'BRE', 'BHA', 'CHE', 'COV', 'CRY', 'EVE', 'FUL',
         'HUL', 'IPS', 'LEE', 'LIV', 'MCI', 'MUN', 'NEW', 'NFO', 'TOT', 'SUN']

req = urllib.request.Request(TV_URL, headers={'User-Agent': 'Mozilla/5.0 (pl-site-updater; +https://github.com/steingmo/pl)'})
with urllib.request.urlopen(req, timeout=30) as r:
    tv = r.read().decode()

valid = {CODES[h] + '-' + CODES[a] for _, _, h, a in rows}
overrides, dates = {}, []
for datestr, chunk in re.findall(
        r'<div class="fixture-date">([^<]+)</div>(.*?)(?=<div class="fixture-date"|$)', tv, re.S):
    dates.append(datetime.strptime(
        re.sub(r'(\d+)(?:st|nd|rd|th)', r'\1', datestr.strip()), '%A %d %B %Y').date())
    for teams, chans in re.findall(
            r'class="fixture__teams">\s*(.+?)\s*</div>.*?class="fixture__channel">(.*?)</div></div>', chunk, re.S):
        home, away = unescape(teams).split(' v ')
        assert home in SITE and away in SITE, f"unknown team in {teams!r}"
        pills = ' '.join(re.findall(r'class="channel-pill"[^>]*>([^<]+)<', chans))
        okey = CODES[SITE[home]] + '-' + CODES[SITE[away]]
        assert okey in valid, f"{okey} not in this season's fixtures"
        overrides[okey] = 'SKY' if 'Sky Sports' in pills else 'TNT' if 'TNT Sports' in pills else None

assert sum(v is not None for v in overrides.values()) >= 10, "suspiciously few TV picks parsed"

# Within the window the site covers, an unlisted match is not televised in the
# UK (e.g. the Saturday 15:00 blackout) -> explicit null override.
for iso, _, h, a in rows:
    # ponytail: UTC->UK date; kickoffs are never near midnight so this is safe
    d = datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/London')).date()
    okey = CODES[h] + '-' + CODES[a]
    if min(dates) <= d <= max(dates) and okey not in overrides:
        overrides[okey] = None

new = re.sub(r'const OVERRIDES = \{.*?\};',
             'const OVERRIDES = ' + json.dumps(overrides, separators=(',', ':')) + ';',
             new, count=1, flags=re.S)
assert 'const OVERRIDES = {' in new, "OVERRIDES line not found in index.html"

if new == html:
    print("no changes")
else:
    open('index.html', 'w').write(new)
    print("index.html updated")
