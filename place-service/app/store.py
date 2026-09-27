"""In-memory lookup over cleaned places."""
import difflib
from collections import defaultdict

from .cleaning import Place, canonical_province, norm


class PlaceStore:
    def __init__(self, places: list[Place]):
        self._by_town: dict[str, list[Place]] = defaultdict(list)
        for p in places:
            self._by_town[norm(p.town)].append(p)
        self.count = len(places)

    def validate(self, town: str, province: str | None = None) -> dict:
        """Return {status, ...}. status is one of:
        valid | ambiguous | not_found | invalid_province
        """
        key = norm(town)
        wanted_province = None
        if province:
            wanted_province = canonical_province(province)
            if wanted_province is None:
                return {"status": "invalid_province", "province": province}

        matches = self._by_town.get(key, [])
        if wanted_province:
            matches = [m for m in matches if m.province == wanted_province]

        if len(matches) == 1:
            m = matches[0]
            return {"status": "valid", "town": m.town, "province": m.province}
        if len(matches) > 1:
            return {
                "status": "ambiguous",
                "town": matches[0].town,
                "provinces": sorted(m.province for m in matches),
            }
        suggestions = difflib.get_close_matches(key, self._by_town.keys(), n=3, cutoff=0.75)
        return {
            "status": "not_found",
            "town": town,
            "suggestions": [self._by_town[s][0].town for s in suggestions],
        }

    def list_places(self, province: str | None = None) -> list[Place]:
        out = [p for group in self._by_town.values() for p in group]
        if province:
            canon = canonical_province(province)
            out = [p for p in out if p.province == canon]
        return sorted(out, key=lambda p: (p.province, p.town))
