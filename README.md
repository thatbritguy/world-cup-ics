# World Cup ICS

An automatically updated iCalendar feed for all 104 matches at the 2026 FIFA
World Cup, plus validated static historical calendars.

## Subscribe

Use this calendar URL in Apple Calendar, Google Calendar, Outlook, or another
calendar application that supports subscribed `.ics` calendars:

```text
https://raw.githubusercontent.com/thatbritguy/world-cup-ics/master/ics/world-cup-2026.ics
```

Apple Calendar also accepts the `webcal` form:

```text
webcal://raw.githubusercontent.com/thatbritguy/world-cup-ics/master/ics/world-cup-2026.ics
```

Static historical calendars are available at:

```text
https://raw.githubusercontent.com/thatbritguy/world-cup-ics/master/ics/world-cup-1930.ics
https://raw.githubusercontent.com/thatbritguy/world-cup-ics/master/ics/world-cup-1934.ics
https://raw.githubusercontent.com/thatbritguy/world-cup-ics/master/ics/world-cup-1938.ics
https://raw.githubusercontent.com/thatbritguy/world-cup-ics/master/ics/world-cup-1950.ics
https://raw.githubusercontent.com/thatbritguy/world-cup-ics/master/ics/world-cup.ics
```

Each event includes the kickoff time, stadium, geographic coordinates for map
integration, UK broadcaster, a Forza Football match link, and alerts 15 minutes
before kickoff and at kickoff. Results and goalscorers are added when they
appear in the upstream fixture data.

## Event format

Examples:

```text
[A1] 🇲🇽 MEX vs RSA 🇿🇦 [001]
[QF1] 🇲🇽 MEX 1-0 (aet) RSA 🇿🇦 [097]
[SF2] 🇲🇽 MEX (p) 1-1 RSA 🇿🇦 [102]
```

Stable UIDs such as `wc2026-match-001@world-cup-ics` allow subscribed calendar
applications to update an existing event as teams, scores, and goals become
known. Visible match numbers follow the published tournament numbering rather
than openfootball's group-organized JSON array order.

## Data pipeline

- Fixtures, kickoff times, teams, and results: [openfootball/worldcup.json](https://github.com/openfootball/worldcup.json)
- UK broadcaster enrichment: [Live Football On TV](https://www.live-footballontv.com/live-world-cup-football-on-tv.html)
- Match links: [Forza Football](https://forzafootball.com/)
- Team codes and flags: the checked-in `data/countries.json`
- 2026 stadium names: the checked-in openfootball stadium mapping

The GitHub Actions workflow runs every two hours. Automatic broadcast updates
end after the final on 19 July 2026, and fixture/result polling ends after
31 July 2026. Manual forced updates remain available from the Actions page.

Broadcast and Forza data are deliberately stored separately from the upstream
fixture snapshot. A failure in either optional source cannot alter match
identity or kickoff data.

Historical calendars are generated separately and have no scheduled source
polling. Match results and goals come from fixed openfootball snapshots. RSSSF
full tournament records are the default source for local kickoff times.
Contemporary primary evidence may override RSSSF, while agreeing Wikipedia and
archived FIFA values provide a fallback where RSSSF omits a time. Every source
value, confidence level and resolution note is retained in the enrichment data.
Calendar events use scheduled kickoff times. Small RSSSF offsets that appear to
record the actual whistle time are retained for audit but do not alter events.
For 2002 onward, contemporary FIFA/Wikipedia timing is accepted without an
RSSSF full-file comparison; explicit source conflicts still require review.
Selected local times are converted using historical IANA host timezones; FIFA's
derived UTC fields remain audit data only. Historical events contain no alerts.

Tournament manifests begin in `review` status. Review calendars can be fully
generated and structurally validated, but only manifests explicitly promoted
to `validated` with the `archive` profile are included in `world-cup.ics`.
Source import is supervised; rebuilding standalone and master calendars from
checked-in data is deterministic.

## Local commands

```bash
python3 scripts/generate_calendar.py
python3 scripts/validate_calendar.py
python3 scripts/generate_historical_calendar.py 1930
python3 scripts/validate_historical_calendar.py 1930
python3 scripts/generate_historical_calendar.py 1934
python3 scripts/validate_historical_calendar.py 1934
python3 scripts/generate_historical_calendar.py 1938
python3 scripts/validate_historical_calendar.py 1938
python3 scripts/generate_historical_calendar.py 1950
python3 scripts/validate_historical_calendar.py 1950
python3 scripts/generate_master_calendar.py
python3 scripts/validate_master_calendar.py
python3 -m unittest discover -s tests
```

Historical source imports are manually supervised and can be reproduced with:

```bash
python3 scripts/import_historical_times.py 1930
python3 scripts/import_historical_times.py 1934
python3 scripts/import_historical_times.py 1938
python3 scripts/import_historical_times.py 1950
```

After the kickoff audit is clean, prepare fixed tournament snapshots and
candidate venue catalogues with:

```bash
python3 scripts/prepare_historical_tournaments.py
python3 scripts/resolve_historical_venues.py
```

New manifests and calendars remain in `review` status. Candidate coordinates
must be checked against the historical stadium site before a manifest can be
promoted to `validated`; review calendars are never included in the master
`world-cup.ics` feed.

Audit every legitimate men's World Cup year without publishing calendars with:

```bash
python3 scripts/audit_historical_tournaments.py
```

The explicit tournament allowlist excludes openfootball's `2025` Club World
Cup folder. Per-year comparisons and the consolidated review queue are written
to `reports/historical/`; downloaded source caches are ignored by Git.
RSSSF's private legacy abbreviations are translated only while parsing that
source. All stored and published team codes remain the official FIFA codes from
`data/countries.json`.

The shared country dataset contains all 211 current FIFA members plus defunct
teams that appeared at a World Cup. Rebuild it from the agreed FIFA-code,
confederation, ISO and Unicode-flag sources with:

```bash
python3 scripts/build_countries.py
```

`name` is the stable English calendar display name. Official, localised and
source-specific alternatives are retained in `aliases` for matching only.
Historical teams normally have no emoji; where a modern Unicode flag has the
same historical design, `flag_representation` records that deliberate mapping.

To run the full live update pipeline:

```bash
python3 scripts/update_calendar.py
```

## Repository layout

```text
data/countries.json                    Team metadata and aliases
data/2026/worldcup.json                Cached upstream fixture snapshot
data/2026/worldcup.uidmap.json         Stable local match identity map
data/2026/worldcup.stadiums.json       Static 2026 stadium mapping
data/2026/worldcup.forza.json          Stable Forza match IDs
data/2026/worldcup.broadcasters.json   UK channel enrichment
data/2026/overrides.json               Manual per-match corrections
data/{YEAR}/worldcup.json              Fixed historical results snapshot
data/{YEAR}/worldcup.enrichment.json   Times, FIFA links and official numbers
data/{YEAR}/worldcup.manifest.json     Stable identities and archive status
data/{YEAR}/worldcup.stadiums.json     Historical venue coordinates
reports/historical/{YEAR}.json         Non-publishing source comparison report
reports/historical/summary.json        Consolidated historical review queue
ics/world-cup-2026.ics                 Published calendar feed
ics/world-cup-1930.ics                 Static historical calendar proof
ics/world-cup-1934.ics                 Static 1934 historical calendar
ics/world-cup-1938.ics                 Static 1938 historical calendar
ics/world-cup-1950.ics                 Static 1950 historical calendar
ics/world-cup.ics                      Validated historical master calendar
```
