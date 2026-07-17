"""Partial Matcher: IPA-Segmente gegen deutsche Wortdatenbank matchen via panphon."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import panphon.distance


@dataclass
class Match:
    """Ein phonetischer Match zwischen IPA-Segment und deutschem Wort."""
    word: str        # Deutsches Wort (z.B. "Zoo")
    ipa: str         # Volles IPA des deutschen Wortes
    match_start: int  # Start-Position im IPA-String
    match_end: int    # End-Position (exklusiv)
    segment_ipa: str  # Der tatsächlich gematchte IPA-Substring
    distance: float   # panphon-Distanz (0 = identisch)

    @property
    def match_quality(self) -> str:
        if self.distance < 0.15:
            return "exakt"
        elif self.distance < 0.3:
            return "sehr ähnlich"
        elif self.distance < 0.5:
            return "ähnlich"
        return "entfernt"


class Matcher:
    """Findet phonetische Partial-Matches in der deutschen Wortdatenbank."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._dst = panphon.distance.Distance()

    def _query_candidates(self, segment_ipa: str, limit: int = 200) -> list[tuple[str, str]]:
        """Findet deutsche Wörter, deren IPA den Segment-String als Substring
        enthalten könnten. Nutzt LIKE für Grobfilter, verfeinert dann mit panphon.

        Args:
            segment_ipa: IPA-Segment (z.B. "oʊ")
            limit: Max Anzahl Kandidaten für Grobfilter

        Returns:
            Liste von (word, ipa) Tupeln
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        # Grobfilter: IPA enthält mindestens ein Zeichen des Segments
        # (LIKE ist schneller als FTS5 für diesen Use Case)
        pattern = f"%{segment_ipa[0]}%"
        rows = conn.execute(
            "SELECT word, ipa FROM words WHERE ipa LIKE ? LIMIT ?",
            (pattern, limit)
        ).fetchall()

        conn.close()
        return [(r["word"], r["ipa"]) for r in rows]

    def find_matches(
        self,
        segment_ipa: str,
        threshold: float = 0.5,
        top_n: int = 5,
    ) -> list[Match]:
        """Findet die besten Partial-Matches für ein IPA-Segment.

        Args:
            segment_ipa: IPA-Segment (z.B. "oʊ")
            threshold: Maximale panphon-Distanz
            top_n: Anzahl Top-Ergebnisse

        Returns:
            Top-N Matches, sortiert nach Distanz (beste zuerst)
        """
        candidates = self._query_candidates(segment_ipa)
        matches = []
        seg_len = len(segment_ipa)

        for word, ipa in candidates:
            # IPA normalisieren: Stress-Marker + Silbentrenner entfernen
            clean_ipa = ipa.replace("ˈ", "").replace("ˌ", "").replace(".", "").replace(" ", "")

            # Gleitendes Fenster
            for window_size in range(max(1, seg_len - 1), min(len(clean_ipa) + 1, seg_len + 2)):
                for start in range(len(clean_ipa) - window_size + 1):
                    end = start + window_size
                    sub_ipa = clean_ipa[start:end]

                    try:
                        dist = self._dst.feature_edit_distance(segment_ipa, sub_ipa)
                    except Exception:
                        continue

                    if dist <= threshold:
                        matches.append(Match(
                            word=word,
                            ipa=clean_ipa,
                            match_start=start,
                            match_end=end,
                            segment_ipa=sub_ipa,
                            distance=dist,
                        ))

        # Bester Match pro Wort
        best_per_word: dict[str, Match] = {}
        for m in matches:
            if m.word not in best_per_word or m.distance < best_per_word[m.word].distance:
                best_per_word[m.word] = m

        # Sortieren: Distanz, dann Wortlänge (kürzer = bekannter)
        sorted_matches = sorted(
            best_per_word.values(),
            key=lambda m: (m.distance, len(m.word))
        )

        return sorted_matches[:top_n]
