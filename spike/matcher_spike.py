#!/usr/bin/env python3
"""Spike: Partial Matcher für LautBau.

Testet, ob IPA-Segmente gegen eine deutsche Wortliste gematcht werden können.
Nutzt panphon für phonetische Distanz.

Für den Spike: Kleine manuelle DE-Wortliste mit IPA.
Später: SQLite mit 364K Einträgen aus kaikki.org.
"""

from dataclasses import dataclass
from typing import Optional

import panphon.distance

# ── Deutsche Wortliste (manuell, für Spike) ─────────────────────────────

# Format: (wort, ipa)
# IPA grob vereinfacht — für Spike-Zwecke ausreichend
DE_WORDS = [
    # Häufige kurze Wörter
    ("Zoo", "tsoː"),
    ("Boot", "boːt"),
    ("Ski", "ʃiː"),
    ("wäre", "vɛːrə"),
    ("Kamel", "kaˈmeːl"),
    ("Tasche", "taʃə"),
    ("Vieh", "fiː"),
    ("Foto", "foːto"),
    ("Dose", "doːzə"),
    ("Kohl", "koːl"),
    ("Quelle", "kvɛlə"),
    ("Kerl", "kɛrl"),
    ("Käse", "kɛːzə"),
    ("Sonne", "zɔnə"),
    ("Butter", "bʊtər"),
    ("Katze", "katsə"),
    ("Haus", "haʊs"),
    ("Maus", "maʊs"),
    ("Baum", "baʊm"),
    ("Traum", "traʊm"),
    ("Kuh", "kuː"),
    ("Schuh", "ʃuː"),
    ("Buch", "buːx"),
    ("Tuch", "tuːx"),
    ("Hand", "hant"),
    ("Land", "lant"),
    ("Wind", "vɪnt"),
    ("Kind", "kɪnt"),
    ("Mann", "man"),
    ("Wasser", "vasər"),
    ("Feuer", "fɔʏər"),
    ("Bier", "biːr"),
    ("Tier", "tiːr"),
    ("Kopf", "kɔpf"),
    ("Apfel", "apfəl"),
    ("Mutter", "mʊtər"),
    ("Vater", "faːtər"),
    ("Bruder", "bruːdər"),
    ("Schwester", "ʃvɛstər"),
    ("Fenster", "fɛnstər"),
    ("Zimmer", "tsɪmər"),
    ("Garten", "ɡartən"),
    ("Straße", "ʃtrasə"),
    ("Platz", "plats"),
    ("Herz", "hɛrts"),
    ("Schmerz", "ʃmɛrts"),
    ("Licht", "lɪçt"),
    ("Nacht", "naxt"),
    ("Macht", "maxt"),
    ("Recht", "rɛçt"),
    ("Sicht", "zɪçt"),
    ("Pflicht", "pflɪçt"),
    ("Arbeit", "arbaɪt"),
    ("Freiheit", "fraɪhaɪt"),
    ("Einheit", "aɪnhaɪt"),
    ("Kirche", "kɪrçə"),
    ("Woche", "vɔxə"),
    ("Sprache", "ʃpraːxə"),
    ("Blume", "bluːmə"),
    ("Himmel", "hɪməl"),
    ("Wunder", "vʊndər"),
    ("Donner", "dɔnər"),
    ("Schatten", "ʃatən"),
    ("Spiegel", "ʃpiːɡəl"),
    ("Engel", "ɛŋəl"),
    ("Insel", "ɪnzəl"),
    ("Regen", "reːɡən"),
    ("Segen", "zeːɡən"),
    ("Hafen", "haːfən"),
    ("Wagen", "vaːɡən"),
    ("Magazin", "maɡaˈtsiːn"),
    ("Maschine", "maˈʃiːnə"),
]


@dataclass
class MatchCandidate:
    word: str
    ipa: str
    match_start: int  # Position im IPA-String (0-basiert)
    match_end: int    # Position im IPA-String (exklusiv)
    segment_ipa: str  # Der tatsächlich gematchte Substring
    distance: float   # panphon Distanz (0 = identisch)
    
    @property
    def match_position(self) -> str:
        """Anfang/Mitte/Ende basierend auf Position im Wort."""
        ratio_start = self.match_start / max(len(self.ipa), 1)
        ratio_end = self.match_end / max(len(self.ipa), 1)
        if ratio_start < 0.2:
            return "Anfang"
        elif ratio_end > 0.8:
            return "Ende"
        else:
            return "Mitte"
    
    @property
    def match_quality(self) -> str:
        if self.distance < 0.15:
            return "exakt"
        elif self.distance < 0.3:
            return "sehr ähnlich"
        elif self.distance < 0.5:
            return "ähnlich"
        else:
            return "entfernt"


def find_matches(
    segment_ipa: str,
    de_words: list[tuple[str, str]],
    threshold: float = 0.5,
    top_n: int = 5,
) -> list[MatchCandidate]:
    """Findet die besten Partial-Matches für ein IPA-Segment in der DE-Wortliste.
    
    Verwendet gleitendes Fenster über die IPA-Strings der DE-Wörter
    und panphon für die Distanz-Berechnung.
    
    Args:
        segment_ipa: IPA-Segment (z.B. "oʊ")
        de_words: Liste von (wort, ipa) Tupeln
        threshold: Maximale panphon-Distanz (0 = identisch)
        top_n: Anzahl der zurückzugebenden Kandidaten
    
    Returns:
        Top-N Match-Kandidaten, sortiert nach Distanz
    """
    dst = panphon.distance.Distance()
    candidates = []
    
    seg_len = len(segment_ipa)
    
    for word, ipa in de_words:
        # Gleitendes Fenster über den IPA-String
        # Fenstergröße: seg_len ± 1 (etwas Flexibilität)
        for window_size in range(max(1, seg_len - 1), min(len(ipa) + 1, seg_len + 2)):
            for start in range(len(ipa) - window_size + 1):
                end = start + window_size
                sub_ipa = ipa[start:end]
                
                # panphon Distanz berechnen
                try:
                    dist = dst.feature_edit_distance(segment_ipa, sub_ipa)
                except Exception:
                    # Fallback: wenn panphon mit dem Input nicht klarkommt
                    continue
                
                if dist <= threshold:
                    candidates.append(MatchCandidate(
                        word=word,
                        ipa=ipa,
                        match_start=start,
                        match_end=end,
                        segment_ipa=sub_ipa,
                        distance=dist,
                    ))
    
    # Dedupliziere: nur bester Match pro Wort behalten
    best_per_word = {}
    for c in candidates:
        key = c.word
        if key not in best_per_word or c.distance < best_per_word[key].distance:
            best_per_word[key] = c
    
    # Sortieren nach Distanz, dann Wortlänge (kürzere bevorzugt)
    sorted_candidates = sorted(
        best_per_word.values(),
        key=lambda c: (c.distance, len(c.word))
    )
    
    return sorted_candidates[:top_n]


# ── Test ────────────────────────────────────────────────────────────────

# IPA-Segmente aus dem Segmentierer-Spike
TEST_SEGMENTS = [
    "oʊ",      # from "though"
    "skwər",   # from "squirrel"
    "əl",      # from "squirrel" (2nd segment)
    "fət",     # from "photography"
    "ɑg",      # from "photography"
    "kæt",     # from "cat"
    "bjut",    # from "beautiful"
    "əf",      # from "beautiful"
    "aɪl",     # from "island"
    "naɪt",    # from "knight"
]


def main():
    print("=" * 60)
    print("LAUTBAU SPIKE: Partial Matcher")
    print("=" * 60)
    print(f"DE-Wortliste: {len(DE_WORDS)} Wörter\n")
    
    for seg in TEST_SEGMENTS:
        matches = find_matches(seg, DE_WORDS, threshold=0.5, top_n=3)
        
        print(f"Segment: [{seg}]")
        if matches:
            for m in matches:
                # Visuelle Darstellung: [match]irrelevant
                pre = m.ipa[:m.match_start]
                mid = m.ipa[m.match_start:m.match_end]
                post = m.ipa[m.match_end:]
                visual = f"{pre}[{mid}]{post}"
                
                print(
                    f"  → {m.word:12s} {visual:25s} "
                    f"dist={m.distance:.3f} "
                    f"({m.match_quality}, {m.match_position})"
                )
        else:
            print("  → KEINE MATCHES GEFUNDEN")
        print()


if __name__ == "__main__":
    main()
