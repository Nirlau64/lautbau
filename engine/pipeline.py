"""LautBau Pipeline: Koordiniert IPA → Segmentierung → Matching → Rendering."""

from pathlib import Path

from engine.ipa import en_to_ipa, strip_stress
from engine.segmenter import tokenize, segment, segments_to_str
from engine.matcher import Matcher
from engine.renderer import RenderedSegment, render, render_verbose
from engine.fallback import get_hint


class LautBau:
    """Haupt-Pipeline für phonetische Aussprachehilfe."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "de_words.db"
        self.matcher = Matcher(db_path)

    def _match_or_hint(self, seg_ipa: str, threshold: float) -> RenderedSegment:
        """Versucht ein Segment zu matchen. Falls kein Match: prüft auf
        Artikulations-Hinweise für einzelne Phoneme.

        Gestaffelte Strategie (Konzept §6.1):
        1. Ganzes Segment matchen
        2. Wenn kein Match: Segment auf einzelne Phoneme prüfen
           - Phoneme mit Hint → Artikulations-Hinweis
           - Restliche Phoneme → erneut matchen
        """
        # Stufe 1: Ganzes Segment matchen
        matches = self.matcher.find_matches(seg_ipa, threshold=threshold, top_n=1)
        if matches:
            return RenderedSegment(match=matches[0], hint=None)

        # Stufe 2: Einzelne Phoneme auf Hints prüfen
        hints_found = []
        for ch in seg_ipa:
            hint = get_hint(ch)
            if hint:
                hints_found.append(hint)

        if hints_found:
            # Prüfe ob es auch matchbare Phoneme im Segment gibt
            matchable = "".join(ch for ch in seg_ipa if not get_hint(ch))
            if matchable and len(matchable) >= 1:
                sub_matches = self.matcher.find_matches(matchable, threshold=threshold, top_n=1)
                if sub_matches:
                    hint_text = "; ".join(hints_found)
                    return RenderedSegment(match=sub_matches[0], hint=hint_text)
            # Nur Hints, kein Match
            return RenderedSegment(match=None, hint="; ".join(hints_found))

        # Kein Match, keine Hints
        return RenderedSegment(match=None, hint=None)

    def pronounce(
        self,
        word: str,
        threshold: float = 0.5,
        verbose: bool = False,
    ) -> str:
        """Ermittelt die Aussprachehilfe für ein englisches Wort."""
        # Phase 1: IPA
        ipa_raw = en_to_ipa(word)
        ipa_clean, stress_idx = strip_stress(ipa_raw)

        # Phase 2: Segmentierung
        tokens = tokenize(ipa_clean)
        segments = segment(tokens)

        # Phase 3+4: Matching + Fallback
        rendered_segments = []
        for seg_tokens in segments:
            seg_ipa = "".join(seg_tokens)
            rendered = self._match_or_hint(seg_ipa, threshold)
            rendered_segments.append(rendered)

        # Phase 5: Rendering
        if verbose:
            segments_raw = [segments_to_str([s]) for s in segments]
            return render_verbose(word, ipa_raw, stress_idx, segments_raw, rendered_segments)
        else:
            return render(word, ipa_raw, stress_idx, rendered_segments)
