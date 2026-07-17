#!/usr/bin/env python3
"""Spike: IPA-Segmentierer für LautBau.

Phase 1: Englische Wörter in IPA konvertieren.
Phase 2: IPA-String in matchbare Segmente zerlegen (2-4 Phoneme).
"""

import sys
from dataclasses import dataclass
from typing import Optional

import eng_to_ipa

# ── IPA-Konvertierung ───────────────────────────────────────────────────

def en_to_ipa(word: str) -> str:
    """Konvertiert englisches Wort zu IPA via eng_to_ipa (CMUdict-backed)."""
    result = eng_to_ipa.convert(word)
    # eng_to_ipa gibt manchmal mehrere Aussprachen zurück (*-separiert)
    if "*" in result:
        result = result.split("*")[0].strip()
    return result.strip()


def strip_stress(ipa: str) -> tuple[str, Optional[int]]:
    """Entfernt Stress-Markierungen, gibt (clean_ipa, stress_index) zurück.
    
    Stress-Markierungen: ˈ = primary, ˌ = secondary
    """
    stress_idx = None
    clean = []
    for i, ch in enumerate(ipa):
        if ch == "ˈ":
            stress_idx = i - len([c for c in ipa[:i] if c in "ˈˌ"])
        elif ch == "ˌ":
            pass  # ignore secondary stress for now
        else:
            clean.append(ch)
    return "".join(clean), stress_idx


# ── Segmentierer ────────────────────────────────────────────────────────

# IPA phoneme categories (simplified)
VOWELS = set("iyɨʉɯuɪʏʊeøɘɵɤoəɛœɜɞʌɔæɐaɶɑɒ")
DIPHTHONGS = {
    "aɪ", "aʊ", "ɔɪ", "eɪ", "oʊ", "ɪə", "eə", "ʊə",
    "ɑɪ", "ɑʊ", "ɔɪ", "eɪ", "oʊ",  # broad transcription variants
}
CONSONANTS = set("pbtdʈɖcɟkɡqɢʔɓɗʄɠʛmnɳɲŋɴʙrʀɾɽɸβfvθðszʃʒʂʐçʝxɣχʁħʕhɦɬɮʋɹɻjɰlɭʎʟwʍ")

# Length/suprasegmental markers to merge
LENGTH = set("ːˑ")
NASALIZATION = set("\u0303")  # combining tilde


def _is_vowel_like(ch: str) -> bool:
    return ch in VOWELS or ch in DIPHTHONGS


def _is_consonant_like(ch: str) -> bool:
    return ch in CONSONANTS


def _phoneme_type(ch: str) -> str:
    """C = consonant, V = vowel/diphthong, X = other/diacritic"""
    if _is_vowel_like(ch):
        return "V"
    if _is_consonant_like(ch):
        return "C"
    return "X"


def tokenize_ipa(ipa: str) -> list[str]:
    """Zerlegt IPA-String in einzelne Phoneme (Tokens).
    
    Behandelt:
    - Affrikaten: t͡ʃ, d͡ʒ (werden als ein Token behandelt)
    - Diphthonge: aɪ, oʊ etc.
    - Diakritika an vorheriges Phonem gebunden
    
    Args:
        ipa: Bereinigter IPA-String (ohne Stress-Marker)
    
    Returns:
        Liste von Phonem-Tokens
    """
    tokens = []
    i = 0
    while i < len(ipa):
        ch = ipa[i]
        
        # Skip tie bars (͡) - they connect previous and next
        if ch == "͡" or ch == "͜":
            # Merge previous token with next
            if tokens and i + 1 < len(ipa):
                tokens[-1] = tokens[-1] + ipa[i + 1]
                i += 2
                continue
            i += 1
            continue
        
        # Check for diphthong (2-char)
        if i + 1 < len(ipa):
            pair = ipa[i : i + 2]
            if pair in DIPHTHONGS or (
                _is_vowel_like(ipa[i]) and _is_vowel_like(ipa[i + 1])
            ):
                tokens.append(pair)
                i += 2
                continue
        
        # Single phoneme
        tokens.append(ch)
        i += 1
    
    return tokens


def segment_ipa(tokens: list[str]) -> list[list[str]]:
    """Zerlegt Phonem-Tokens in matchbare Segmente (2-4 Phoneme pro Segment).
    
    Strategie (nach Priorität):
    1. Onset-Nucleus-Coda: Gruppiere Konsonanten + Vokal (+ Folgekonsonant)
    2. Phonen-Paar-Gruppierung: 2-3 benachbarte Phoneme bilden Segment
    3. Gleitendes Fenster: Für Rest-Phoneme
    
    Args:
        tokens: Liste von Phonem-Tokens
    
    Returns:
        Liste von Segmenten (jedes Segment ist eine Liste von Tokens)
    """
    if len(tokens) <= 3:
        # Zu kurz zum Segmentieren — als Ganzes zurück
        return [tokens]
    
    segments = []
    i = 0
    
    while i < len(tokens):
        remaining = len(tokens) - i
        
        # Fall 1: Am Ende, wenig übrig
        if remaining <= 2:
            # Nimm den Rest als letztes Segment
            segments.append(tokens[i:])
            break
        
        # Fall 2: Finde Vokal als Anker
        # Suche nächsten Vokal
        vowel_pos = None
        for j in range(i, min(i + 4, len(tokens))):
            if _is_vowel_like(tokens[j]) or (
                len(tokens[j]) == 2 and any(
                    _is_vowel_like(c) for c in tokens[j]
                )
            ):
                vowel_pos = j
                break
        
        if vowel_pos is None:
            # Kein Vokal in Reichweite — nimm 2 Konsonanten
            segments.append(tokens[i : i + 2])
            i += 2
            continue
        
        # Fall 3: Onset-Nucleus-Coda um den Vokal herum
        # Nimm Konsonanten VOR dem Vokal (max 3 für initiales Cluster, sonst max 2)
        max_onset = 3 if i == 0 else 2
        onset_start = max(i, vowel_pos - max_onset)
        # Nimm Konsonanten NACH dem Vokal (max 1)
        coda_end = min(len(tokens), vowel_pos + 2)
        
        # Aber nicht zu kurz (<2) oder zu lang (>4)
        segment = tokens[onset_start:coda_end]
        
        if len(segment) < 2 and coda_end < len(tokens):
            segment = tokens[onset_start : coda_end + 1]
        
        if len(segment) > 4:
            segment = tokens[onset_start : vowel_pos + 2]
        
        segments.append(segment)
        i = coda_end
    
    # Merge: benachbarte Segmente die zu kurz sind
    merged = []
    for seg in segments:
        if merged and len(seg) <= 1:
            merged[-1].extend(seg)
        else:
            merged.append(seg)
    
    # Final merge: wenn letztes Segment zu kurz, an vorletztes anhängen
    if len(merged) >= 2 and len(merged[-1]) <= 1:
        merged[-2].extend(merged[-1])
        merged.pop()
    
    return merged


def segments_to_str(segments: list[list[str]]) -> str:
    """Formatierte Segment-Ausgabe."""
    parts = []
    for seg in segments:
        parts.append("".join(seg))
    return " · ".join(parts)


# ── Test ────────────────────────────────────────────────────────────────

TEST_WORDS = [
    "though",
    "squirrel",
    "photography",
    "cat",
    "through",
    "beautiful",
    "restaurant",
    "comfortable",
    "island",
    "knight",
]

def main():
    print("=" * 60)
    print("LAUTBAU SPIKE: IPA-Segmentierer")
    print("=" * 60)
    
    for word in TEST_WORDS:
        ipa_raw = en_to_ipa(word)
        ipa_clean, stress = strip_stress(ipa_raw)
        tokens = tokenize_ipa(ipa_clean)
        segments = segment_ipa(tokens)
        
        print(f"\n{word:15s} → {ipa_raw:20s}", end="")
        if stress is not None:
            print(f"  ⚡Pos={stress}", end="")
        print()
        print(f"  Clean:   {ipa_clean}")
        print(f"  Tokens:  {tokens}")
        print(f"  Segmente: {segments_to_str(segments)}  ({len(segments)} Segmente)")
        
        # Debug: show phoneme types
        types = "".join(_phoneme_type(t) for t in tokens)
        print(f"  Types:   {types}")


if __name__ == "__main__":
    main()
