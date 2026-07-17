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
        """Matcht ein Segment, mit Fallback auf Artikulations-Hinweise."""
        hint_phonemes = [ch for ch in seg_ipa if get_hint(ch)]
        matchable = "".join(ch for ch in seg_ipa if not get_hint(ch))

        hint_text = None
        if hint_phonemes:
            hints = [get_hint(ch) for ch in hint_phonemes if get_hint(ch)]
            hint_text = "; ".join(hints) if hints else None

        match = None
        if matchable and len(matchable) > 2:
            # Genug Phoneme für eigenständiges Matching
            matches = self.matcher.find_matches(matchable, threshold=threshold, top_n=1)
            if matches:
                match = matches[0]
        elif seg_ipa:
            # Kurzes Segment oder hint-dominiert → Vollsegment mit Approximation
            matches = self.matcher.find_matches(seg_ipa, threshold=threshold, top_n=1)
            if matches:
                match = matches[0]

        if not match and not hint_text:
            return RenderedSegment(match=None, hint=None)

        return RenderedSegment(match=match, hint=hint_text)

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
