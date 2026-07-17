"""Renderer: ANSI + Plain-Text Ausgabe für LautBau."""

import sys
from dataclasses import dataclass

from engine.matcher import Match
from engine.fallback import get_hint


# ANSI-Codes
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
LIGHTNING = "⚡"


@dataclass
class RenderedSegment:
    """Ein gerendertes Segment mit Match-Information."""
    match: Match | None       # None = Artikulations-Hinweis
    hint: str | None          # Artikulations-Hinweis-Text


def render_word(match: Match) -> str:
    """Rendert ein deutsches Wort mit hervorgehobenem Match-Teil.

    ANSI: irrelevante Teile dim, relevanter Teil bold.
    Plain-Text: [relevanter]irrelevanter Teil.
    """
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
    """Rendert die vollständige Aussprachehilfe.

    Args:
        word: Fremdwort
        ipa: IPA des Fremdworts
        stress_idx: Primary-Stress-Position
        segments: Gerenderte Segmente
        use_ansi: True/False/None (auto-detect)

    Returns:
        Formatierter String
    """
    if use_ansi is None:
        use_ansi = _use_ansi()

    lines = []
    lines.append(f"{BOLD}{word}{RESET} → " if use_ansi else f"{word} → ")

    parts = []
    for i, seg in enumerate(segments):
        if seg.hint and seg.match:
            # Beides: Hint + Match
            parts.append(f"({seg.hint}) + {render_word(seg.match)}")
        elif seg.hint:
            parts.append(f"({seg.hint})")
        elif seg.match:
            parts.append(render_word(seg.match))
        else:
            parts.append("(?)")

        # Stress-Markierung
        if stress_idx is not None and i == _find_stressed_segment(segments, stress_idx):
            parts.append(LIGHTNING if use_ansi else "⚡")

    lines.append(" + ".join(parts))
    return "\n".join(lines)


def render_verbose(
    word: str,
    ipa: str,
    stress_idx: int | None,
    segments_raw: list[str],
    segments: list[RenderedSegment],
) -> str:
    """Detaillierte Ausgabe mit IPA, Token, Segment-Infos."""
    lines = []
    lines.append(f"{word} /{ipa}/  ⚡Pos={stress_idx}")

    for i, (seg_raw, seg) in enumerate(zip(segments_raw, segments)):
        lines.append(f"  Segment {i+1} [{seg_raw}]:")
        if seg.hint:
            lines.append(f"    ↳ Artikulation: {seg.hint}")
        elif seg.match:
            lines.append(
                f"    ↳ {seg.match.word:15s} "
                f"dist={seg.match.distance:.3f} "
                f"({seg.match.match_quality})"
            )
        else:
            lines.append(f"    ↳ KEIN MATCH")

    return "\n".join(lines)


def _use_ansi() -> bool:
    """Erkennt, ob ANSI-Codes unterstützt werden."""
    if not sys.stdout.isatty():
        return False
    term = sys.stdout.encoding or ""
    return "utf" in term.lower()


def _find_stressed_segment(segments: list[RenderedSegment], stress_idx: int) -> int:
    """Findet Index des Segments, das den Stress enthält (einfache Heuristik)."""
    # Vereinfacht: erstes Segment = 0, bei mehr als 2 Segmenten das mittlere
    # TODO: präzisere Berechnung basierend auf Phonem-Positionen
    n = len(segments)
    if n <= 1:
        return 0
    if n == 2 and stress_idx is not None and stress_idx <= 2:
        return 0
    return 1 if n == 3 else 0
