from __future__ import annotations


WORLD_CUP_YEARS = (
    1930,
    1934,
    1938,
    1950,
    1954,
    1958,
    1962,
    1966,
    1970,
    1974,
    1978,
    1982,
    1986,
    1990,
    1994,
    1998,
    2002,
    2006,
    2010,
    2014,
    2018,
    2022,
    2026,
)

# 2025 in openfootball/worldcup.json is the FIFA Club World Cup, not this series.
EXCLUDED_OPENFOOTBALL_YEARS = {2025}

TOURNAMENTS = {
    1930: {"slug": "1930uruguay", "timezone": "America/Montevideo"},
    1934: {"slug": "1934italy", "timezone": "Europe/Rome"},
    1938: {"slug": "1938france", "timezone": "Europe/Paris"},
    1950: {"slug": "1950brazil", "timezone": "America/Sao_Paulo"},
    1954: {"slug": "1954switzerland", "timezone": "Europe/Zurich"},
    1958: {"slug": "1958sweden", "timezone": "Europe/Stockholm"},
    1962: {"slug": "1962chile", "timezone": "America/Santiago"},
    1966: {"slug": "1966england", "timezone": "Europe/London"},
    1970: {"slug": "1970mexico", "timezone": "America/Mexico_City"},
    1974: {"slug": "1974germany", "timezone": "Europe/Berlin"},
    1978: {"slug": "1978argentina", "timezone": "America/Argentina/Buenos_Aires"},
    1982: {"slug": "1982spain", "timezone": "Europe/Madrid"},
    1986: {"slug": "1986mexico", "timezone": "America/Mexico_City"},
    1990: {"slug": "1990italy", "timezone": "Europe/Rome"},
    1994: {"slug": "1994usa", "timezone": "multi-zone"},
    1998: {"slug": "1998france", "timezone": "Europe/Paris"},
    2002: {"slug": "2002korea-japan", "timezone": "multi-zone"},
    2006: {"slug": "2006germany", "timezone": "Europe/Berlin"},
    2010: {"slug": "2010south-africa", "timezone": "Africa/Johannesburg"},
    2014: {"slug": "2014brazil", "timezone": "multi-zone"},
    2018: {"slug": "2018russia", "timezone": "multi-zone"},
    2022: {"slug": "2022qatar", "timezone": "Asia/Qatar"},
    2026: {"slug": "2026canada-mexico-usa", "timezone": "multi-zone"},
}

RSSSF_FULL_YEARS = frozenset(year for year in WORLD_CUP_YEARS if year <= 1998)
FIFA_ARCHIVE_YEARS = frozenset(year for year in WORLD_CUP_YEARS if year <= 2014)


def historical_years() -> tuple[int, ...]:
    return tuple(year for year in WORLD_CUP_YEARS if year < 2026)

