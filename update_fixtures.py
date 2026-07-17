#!/usr/bin/env python3
"""Refresh the FIXTURES array in index.html from fixturedownload.com.

Run by .github/workflows/update-fixtures.yml on a weekly cron.
Exits non-zero (failing the workflow) if the feed looks wrong.
"""
import json
import re
import sys
import urllib.request

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

if new == html:
    print("no changes")
else:
    open('index.html', 'w').write(new)
    print("index.html updated")
