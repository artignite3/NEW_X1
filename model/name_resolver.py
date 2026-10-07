"""
NEW_X1 — Player Name Resolver
Bridges Cricbuzz-style squad names ("Shubman Gill") with Cricsheet-style
fantasy-data keys ("RG Sharma", "YBK Jaiswal").

Design principles:
  1. NEVER guess a match that could belong to a different player.
     A false positive (e.g. "Rashid Khan" -> "Rabeya Khan") silently feeds the
     wrong player's history into predictions, which is far worse than leaving
     a player unresolved (falling back to a league prior).
  2. The fantasy dataset contains both men's and women's cricket. Squad data
     from Cricbuzz is men's international, so candidates must have male
     match history to be considered.
  3. Resolution ladder: exact -> initials-variant -> spelling variant (fuzzy).
     Ambiguity is resolved by career prominence (number of male matches);
     ties stay unresolved.

Returns (fantasy_key, method) where method is one of:
  'exact', 'initials', 'initials-prominence', 'fuzzy', None
"""

import difflib
import re
from typing import Dict, List, Optional, Tuple


class PlayerNameResolver:
    """Index-backed resolver over one format's fantasy-points dictionary."""

    def __init__(self, fantasy_points: Dict):
        self._by_norm: Dict[str, str] = {}
        self._by_last: Dict[str, List[dict]] = {}
        self._entries: Dict[str, dict] = {}
        self._build(fantasy_points)

    # ── Index construction ────────────────────────────────────────────────
    def _build(self, fantasy_points: Dict) -> None:
        for key, matches in fantasy_points.items():
            male = sum(1 for mk in matches if "-male-" in mk)
            female = len(matches) - male
            norm = self._normalize(key)
            parts = norm.split()
            if not parts:
                continue
            last = parts[-1]
            initials = "".join(p[0] for p in parts[:-1])
            entry = {
                "key": key,
                "norm": norm,
                "last": last,
                "initials": initials,
                "male_matches": male,
                "female_matches": female,
                "total_matches": len(matches),
            }
            self._entries[norm] = entry
            self._by_norm.setdefault(norm, key)
            self._by_last.setdefault(last, []).append(entry)

    @staticmethod
    def _normalize(name: str) -> str:
        return re.sub(r"\s+", " ", name.strip().lower())

    # ── Public API ────────────────────────────────────────────────────────
    def resolve(self, name: str, require_gender: str = "male") -> Tuple[Optional[str], Optional[str]]:
        """Resolve a display name to a fantasy-data key."""
        norm = self._normalize(name)
        if not norm:
            return None, None

        # 1. Exact (case-insensitive)
        if norm in self._by_norm:
            if self._gender_ok(self._entries[norm], require_gender):
                return self._by_norm[norm], "exact"
            return None, None

        parts = norm.split()
        if len(parts) < 2:
            return None, None
        last = parts[-1]
        query_initials = "".join(p[0] for p in parts[:-1])

        # 2. Initials-variant within same surname, restricted to match gender
        candidates = [
            e for e in self._by_last.get(last, [])
            if self._gender_ok(e, require_gender)
        ]
        if candidates:
            prefix_matches = [e for e in candidates if e["initials"].startswith(query_initials)]
            if prefix_matches:
                exact_initials = [e for e in prefix_matches if e["initials"] == query_initials]
                pool = exact_initials or prefix_matches
                if len(pool) == 1:
                    return pool[0]["key"], "initials"
                # Ambiguity: prefer clear career prominence (2x the runner-up)
                ranked = sorted(pool, key=lambda e: self._prominence(e, require_gender), reverse=True)
                top, second = ranked[0], ranked[1]
                if self._prominence(top, require_gender) >= 2 * max(1, self._prominence(second, require_gender)):
                    return top["key"], "initials-prominence"
                return None, None  # ambiguous — refuse to guess

            # 3. Spelling variant (e.g. "Nitish" vs "Nithish") within same surname
            close = difflib.get_close_matches(
                norm, [e["norm"] for e in candidates], n=2, cutoff=0.84
            )
            if len(close) == 1:
                return self._entries[close[0]]["key"], "fuzzy"

        return None, None

    # ── Helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _gender_ok(entry: dict, require_gender: str) -> bool:
        if require_gender == "male":
            return entry["male_matches"] > 0
        if require_gender == "female":
            return entry["female_matches"] > 0
        return entry["total_matches"] > 0

    def _prominence(self, entry: dict, require_gender: str) -> int:
        return entry["male_matches"] if require_gender == "male" else entry["total_matches"]
