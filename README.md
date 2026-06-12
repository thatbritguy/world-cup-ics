# World Cup ICS

An automatically updated iCalendar feed for all 104 matches at the 2026 FIFA
World Cup, plus a static historical calendar proof of concept for 1930.

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

The static 1930 calendar is available at:

```text
https://raw.githubusercontent.com/thatbritguy/world-cup-ics/master/ics/world-cup-1930.ics
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

The 1930 calendar is generated separately and has no scheduled workflow. Match
results and goals come from the fixed openfootball snapshot; local kickoff
times and FIFA report links are imported once from Wikipedia match boxes and
stored in `data/1930/enrichment.json`. Historical events contain no alerts.

## Local commands

```bash
python3 scripts/generate_calendar.py
python3 scripts/validate_calendar.py
python3 scripts/generate_historical_calendar.py 1930
python3 scripts/validate_historical_calendar.py 1930
python3 -m unittest discover -s tests
```

The one-time 1930 time import can be reproduced with:

```bash
python3 scripts/import_historical_times.py 1930
```

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
data/1930/worldcup.json                Fixed historical results snapshot
data/1930/enrichment.json              Kickoff times and source links
data/1930/manifest.json                Stable chronological match identities
data/1930/venues.json                  Historical venue coordinates
ics/world-cup-2026.ics                 Published calendar feed
ics/world-cup-1930.ics                 Static historical calendar proof
```
