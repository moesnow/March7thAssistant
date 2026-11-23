"""Detail filters use the date as written in the account's game timezone."""
from dataclasses import dataclass
from datetime import date, datetime


def _day(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    return (value if isinstance(value, date) else date.fromisoformat(value)).isoformat()


@dataclass(frozen=True, slots=True)
class DetailFilter:
    stars: frozenset[int] | None
    keyword: str
    start: str
    end: str

    @classmethod
    def make(cls, stars=None, keyword="", start=None, end=None):
        return cls(None if stars is None else frozenset(map(int, stars)),
                   keyword.strip().casefold(), _day(start), _day(end))

    def accepts(self, row):
        return ((self.stars is None or row.stars in self.stars)
                and (not self.keyword or self.keyword in row.name.casefold())
                and (not self.start or row.time[:10] >= self.start)
                and (not self.end or row.time[:10] <= self.end))


def newest_first(rows):
    return sorted(rows, key=lambda row: (row.time, int(row.id)), reverse=True)


def filter_details(rows, *, stars=None, keyword="", start=None, end=None):
    rule = DetailFilter.make(stars, keyword, start, end)
    return newest_first(row for row in rows if rule.accepts(row))
