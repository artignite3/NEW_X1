"""
NEW_X1 — Venue Registry
Cricsheet's historical venue strings are inconsistent across eras:
"Wankhede Stadium, Mumbai" (529 matches) and bare "Wankhede Stadium" (462)
are the same ground. Left raw, the duplicates pollute the venue datalist and
split pitch/weather lookups across two spellings of one venue.

The registry groups venue strings by their ground part (text before the first
comma, normalized) and elects one canonical display variant per ground —
preferring the variant that carries a city, then the most frequently seen.

Same-ground *alias* pairs with entirely different names (Feroz Shah Kotla vs
Arun Jaitley Stadium) are intentionally NOT merged — only suffix variance is.
"""

import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, Optional


def _ground_key(name: str) -> str:
    """Normalized ground part of a venue string: 'Wankhede Stadium, Mumbai' -> 'wankhede stadium'."""
    ground = (name or "").split(",")[0]
    return re.sub(r"\s+", " ", ground.strip().lower())


def _city_part(name: str) -> str:
    parts = (name or "").split(",")
    return parts[-1].strip().lower() if len(parts) > 1 else ""


class VenueRegistry:
    """Frequency-backed canonical mapping over venue strings."""

    def __init__(self, counts: Counter):
        # counts: raw venue string -> occurrences
        self._counts = counts
        self._by_ground: Dict[str, Dict[str, int]] = defaultdict(dict)
        for raw, n in counts.items():
            self._by_ground[_ground_key(raw)][raw] = n
        self._canonical_cache: Dict[str, str] = {}

    @classmethod
    def from_fantasy(cls, fantasy_by_fmt: Dict[str, dict]) -> "VenueRegistry":
        counts: Counter = Counter()
        for fantasy in fantasy_by_fmt.values():
            for matches in fantasy.values():
                for stats in matches.values():
                    venue = stats.get("venue")
                    if venue:
                        counts[venue] += 1
        return cls(counts)

    def canonical(self, raw: str) -> str:
        """Canonical display name for a raw venue string (identity if unknown)."""
        if not raw:
            return raw
        cached = self._canonical_cache.get(raw)
        if cached:
            return cached

        key = _ground_key(raw)
        group = self._by_ground.get(key)
        if not group or len(group) == 1:
            resolved = raw
        else:
            # Prefer variants carrying a city, then raw frequency, then length
            resolved = max(
                group.items(),
                key=lambda kv: (bool(_city_part(kv[0])), kv[1], len(kv[0])),
            )[0]
        self._canonical_cache[raw] = resolved
        return resolved

    def dedupe(self, raw_names: Iterable[str]) -> list:
        """Canonical, sorted venue list for UI datalists."""
        seen = {self.canonical(n) for n in raw_names if n}
        return sorted(seen)

    def stats(self) -> Dict[str, int]:
        return {
            "raw_variants": len(self._counts),
            "canonical_venues": len(self._by_ground),
        }


# Process-level singleton, built lazily (the fantasy dicts are already cached
# by team_generator.get_fantasy with mtime invalidation).
_REGISTRY = None
_REGISTRY_BUILDER = None


def configure(builder) -> None:
    """Inject the registry builder (wired in model_fastapi startup)."""
    global _REGISTRY_BUILDER, _REGISTRY
    _REGISTRY_BUILDER = builder
    _REGISTRY = None


def _get() -> Optional[VenueRegistry]:
    global _REGISTRY
    if _REGISTRY is None and _REGISTRY_BUILDER is not None:
        _REGISTRY = _REGISTRY_BUILDER()
    return _REGISTRY


def canonical_venue(raw: str) -> str:
    """Public helper — canonical display name, identity when registry absent."""
    registry = _get()
    return registry.canonical(raw) if registry else raw


def dedupe_venues(raw_names: Iterable[str]) -> list:
    registry = _get()
    if registry is None:
        return sorted({n for n in raw_names if n})
    return registry.dedupe(raw_names)


def registry_stats() -> Dict[str, int]:
    registry = _get()
    return registry.stats() if registry else {}
