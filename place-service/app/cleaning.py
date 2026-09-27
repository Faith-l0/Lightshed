"""Data cleaning for the raw town/province dataset.

Pure functions only (no I/O except clean_file), so every rule is easy to unit test.
"""
import csv
import re
import unicodedata
from dataclasses import dataclass

PROVINCES = [
    "Eastern Cape",
    "Free State",
    "Gauteng",
    "KwaZulu-Natal",
    "Limpopo",
    "Mpumalanga",
    "North West",
    "Northern Cape",
    "Western Cape",
]


def norm(text: str | None) -> str:
    """Normalise for comparison: unicode-fold, lowercase, hyphens/dots -> spaces, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.casefold()
    text = re.sub(r"[-_.]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_PROVINCE_ALIASES: dict[str, str] = {norm(p): p for p in PROVINCES}
_PROVINCE_ALIASES.update(
    {
        "ec": "Eastern Cape", "e cape": "Eastern Cape",
        "fs": "Free State",
        "gp": "Gauteng", "gt": "Gauteng",
        "kzn": "KwaZulu-Natal", "kwazulu natal": "KwaZulu-Natal",
        "lp": "Limpopo",
        "mp": "Mpumalanga",
        "nw": "North West", "northwest": "North West",
        "nc": "Northern Cape", "n cape": "Northern Cape",
        "wc": "Western Cape", "w cape": "Western Cape",
    }
)


def canonical_province(raw: str | None) -> str | None:
    """Map any known spelling/abbreviation to the canonical province name, or None."""
    key = norm(raw)
    key = re.sub(r"\s+province$", "", key)
    return _PROVINCE_ALIASES.get(key)


def clean_town(raw: str | None) -> str:
    """Trim, collapse whitespace, and title-case (keeping hyphenated names like Graaff-Reinet)."""
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", raw or "")).strip()
    parts = re.split(r"([ -])", text)  # keep the separators
    return "".join(p.capitalize() if p not in (" ", "-") else p for p in parts)


@dataclass(frozen=True)
class Place:
    town: str
    province: str


@dataclass(frozen=True)
class Rejected:
    line: int
    town: str
    province: str
    reason: str


@dataclass
class CleanResult:
    places: list[Place]
    rejected: list[Rejected]
    duplicates: int


def clean_rows(rows: list[dict]) -> CleanResult:
    places: list[Place] = []
    rejected: list[Rejected] = []
    seen: set[tuple[str, str]] = set()
    duplicates = 0

    for i, row in enumerate(rows, start=2):  # line 1 is the header
        raw_town = row.get("town") or ""
        raw_prov = row.get("province") or ""
        town = clean_town(raw_town)

        def reject(reason: str) -> None:
            rejected.append(Rejected(i, raw_town, raw_prov, reason))

        if not town:
            reject("missing town")
        elif any(ch.isdigit() for ch in town):
            reject("town contains digits")
        elif not raw_prov.strip():
            reject("missing province")
        else:
            province = canonical_province(raw_prov)
            if province is None:
                reject("unknown province")
                continue
            key = (norm(town), province)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            places.append(Place(town, province))

    return CleanResult(places, rejected, duplicates)


def clean_file(path: str) -> CleanResult:
    with open(path, newline="", encoding="utf-8") as f:
        return clean_rows(list(csv.DictReader(f)))
