"""Renderer: ANSI + Plain-Text Ausgabe für LautBau."""

import sys
from dataclasses import dataclass

from engine.matcher import Match

# ANSI-Codes
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
LIGHTNING = "⚡"


@dataclass
class RenderedSegment:
    """Ein gerendertes Segment mit Match-Information."""
    match: Match | None
    hint: str | None


def render_word(match: Match) -> str:
    """Rendert ein deutsches Wort mit hervorgehobenem Match-Teil."""
    pre = match.ipa[:match.match_start]
    mid = match.ipa[match.match_start:match.match_end]
    post = match.ipa[match.match_end:]

    if _use_ansi():
        return f"{match.word} ({DIM}{pre}{RESET}{BOLD}{mid}{RESET}{DIM}{post}{RESET})"
    else:
        return f"{match.word} [{mid}]"


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
        # Stress vor dem betonten Segment
        if stress_idx is not None and i == _stressed_seg_idx(len(segments), stress_idx):
            parts.append(LIGHTNING if use_ansi else "⚡")

        if seg.hint and seg.match:
            parts.append(f"({seg.hint}) + {render_word(seg.match)}")
        elif seg.hint:
            parts.append(f"({seg.hint})")
        elif seg.match:
            parts.append(render_word(seg.match))
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
            lines.append(f"    ↳ {seg.match.word:15s} dist={seg.match.distance:.3f}")
        elif seg.hint:
            lines.append(f"    ↳ Artikulation: {seg.hint}")
        elif seg.match:
            lines.append(
                f"    ↳ {seg.match.word:15s} "
                f"dist={seg.match.distance:.3f} "
                f"({seg.match.match_quality})"
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
    """Ermittelt welches Segment den Primary Stress enthält.

    Heuristik: Stress-Index 0-1 → Segment 0, sonst proportional.
    """
    if num_segments <= 1 or stress_idx <= 1:
        return 0
    if stress_idx >= 4:
        return min(num_segments - 1, num_segments // 2 + 1)
    return min(num_segments - 1, stress_idx // 3)
