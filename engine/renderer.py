"""Renderer v2: Orthographische Hervorhebung — zeigt DE-Wort mit relevanten Buchstaben."""

import sys
from dataclasses import dataclass

from engine.matcher import Match

DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
LIGHTNING = "⚡"


@dataclass
class RenderedSegment:
    match: Match | None
    hint: str | None


def _align_ipa_to_letters(word: str, ipa: str, ipa_start: int, ipa_end: int) -> tuple[int, int]:
    """Schätzt welche Buchstaben im Wort dem IPA-Substring [ipa_start:ipa_end] entsprechen.

    Heuristik: Pro IPA-Zeichen ≈ 1 Buchstabe, mit Gewichtung.
    Deutsche Sonderfälle: 'sch' = 1 IPA-Zeichen [ʃ], 'ch' = 1 IPA-Zeichen [ç/x].
    """
    # Normalisiere IPA: entferne Diakritika, Stress
    ipa_simple = ipa.replace("ˈ", "").replace("ˌ", "").replace("ː", "").replace("̯", "")

    # Wenn match am Ende → letzten Buchstaben nehmen
    # Wenn match am Anfang → ersten Buchstaben nehmen
    # Sonst proportional
    total_ipa = max(len(ipa_simple), 1)
    total_letters = len(word)

    letter_start = int((ipa_start / total_ipa) * total_letters)
    letter_end = int((ipa_end / total_ipa) * total_letters)

    # Clampen
    letter_start = max(0, min(letter_start, total_letters - 1))
    letter_end = max(letter_start + 1, min(letter_end, total_letters))

    return letter_start, letter_end


def render_word_highlight(match: Match) -> str:
    """Rendert ein deutsches Wort mit hervorgehobenen MATCH-Buchstaben (nicht IPA).

    ANSI: irrelevante Buchstaben dim, relevante bold.
    Plain-Text: RELEVANTE Buchstaben in UPPERCASE.
    """
    letter_start, letter_end = _align_ipa_to_letters(
        match.word, match.ipa, match.match_start, match.match_end
    )

    pre = match.word[:letter_start]
    mid = match.word[letter_start:letter_end]
    post = match.word[letter_end:]

    if _use_ansi():
        return f"{DIM}{pre}{RESET}{BOLD}{mid}{RESET}{DIM}{post}{RESET}"
    else:
        return f"{pre}{mid.upper()}{post}"


def render(
    word: str,
    ipa: str,
    stress_idx: int | None,
    segments: list[RenderedSegment],
    use_ansi: bool | None = None,
) -> str:
    if use_ansi is None:
        use_ansi = _use_ansi()

    parts = []
    for i, seg in enumerate(segments):
        if stress_idx is not None and i == _stressed_seg_idx(len(segments), stress_idx):
            parts.append(LIGHTNING)

        if seg.hint and seg.match:
            parts.append(f"({seg.hint}) + {render_word_highlight(seg.match)}")
        elif seg.hint:
            parts.append(f"({seg.hint})")
        elif seg.match:
            parts.append(render_word_highlight(seg.match))
        else:
            parts.append("(?)")

    prefix = f"{BOLD}{word}{RESET} → " if use_ansi else f"{word} → "
    return prefix + " + ".join(parts)


def render_verbose(
    word: str,
    ipa: str,
    stress_idx: int | None,
    segments_raw: list[str],
    segments: list[RenderedSegment],
) -> str:
    lines = [f"{word} /{ipa}/  ⚡Pos={stress_idx}"]
    for i, (seg_raw, seg) in enumerate(zip(segments_raw, segments)):
        lines.append(f"  Segment {i+1} [{seg_raw}]:")
        if seg.hint and seg.match:
            lines.append(f"    ↳ Hint: {seg.hint}")
            lines.append(f"    ↳ {seg.match.word:15s} [{seg.match.segment_ipa}] dist={seg.match.distance:.3f}")
        elif seg.hint:
            lines.append(f"    ↳ Artikulation: {seg.hint}")
        elif seg.match:
            lines.append(
                f"    ↳ {seg.match.word:15s} [{seg.match.segment_ipa}] "
                f"dist={seg.match.distance:.3f} ({seg.match.match_quality})"
            )
        else:
            lines.append("    ↳ KEIN MATCH")
    return "\n".join(lines)


def _use_ansi() -> bool:
    if not sys.stdout.isatty():
        return False
    term = sys.stdout.encoding or ""
    return "utf" in term.lower()


def _stressed_seg_idx(num_segments: int, stress_idx: int) -> int:
    if num_segments <= 1 or stress_idx <= 1:
        return 0
    if stress_idx >= 4:
        return min(num_segments - 1, num_segments // 2 + 1)
    return min(num_segments - 1, stress_idx // 3)
