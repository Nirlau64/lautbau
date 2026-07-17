"""LautBau Pipeline: IPA → Segmentierung → Matching → Rendering."""

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

    def _match_one(self, ipa: str, threshold: float) -> RenderedSegment:
        """Matcht einen IPA-String und gibt RenderedSegment zurück."""
        hint_phonemes = [ch for ch in ipa if get_hint(ch)]
        matchable = "".join(ch for ch in ipa if not get_hint(ch))

        hint_text = None
        if hint_phonemes:
            hints = [get_hint(ch) for ch in hint_phonemes if get_hint(ch)]
            hint_text = "; ".join(hints) if hints else None

        match = None
        if matchable:
            # Bei kurzem matchable (≤2): Vollsegment versuchen
            search_ipa = ipa if len(matchable) <= 2 else matchable
            matches = self.matcher.find_matches(search_ipa, threshold=threshold, top_n=1)
            if matches:
                match = matches[0]

        if not match and not hint_text:
            return RenderedSegment(match=None, hint=None)
        return RenderedSegment(match=match, hint=hint_text)

    def _try_split_match(
        self, seg_ipa: str, threshold: float
    ) -> list[RenderedSegment] | None:
        """Versucht ein Segment in zwei Teile zu splitten und separat zu matchen.

        Nur sinnvoll für Segmente mit ≥3 Phonemen.
        """
        if len(seg_ipa) < 3:
            return None

        # Finde Vokal-Position für den Split
        vowel_pos = None
        for i, ch in enumerate(seg_ipa):
            if ch in "iyɨʉɯuɪʏʊeøɘɵɤoəɛœɜɞʌɔæɐaɶɑɒ" or (
                i + 1 < len(seg_ipa)
                and seg_ipa[i : i + 2]
                in {"aɪ", "aʊ", "ɔɪ", "eɪ", "oʊ"}
            ):
                vowel_pos = i
                break

        if vowel_pos is None:
            return None

        # Split: onset (vor Vokal) und nucleus+coda (ab Vokal)
        if vowel_pos == 0:
            return None  # Kein Onset zum Abspalten

        part1 = seg_ipa[:vowel_pos]  # Onset
        part2 = seg_ipa[vowel_pos:]   # Nucleus+Coda

        seg1 = self._match_one(part1, threshold)
        seg2 = self._match_one(part2, threshold)

        if seg1.match or seg2.match:
            return [seg1, seg2]
        return None

    def pronounce(
        self, word: str, threshold: float = 0.5, verbose: bool = False,
    ) -> str:
        ipa_raw = en_to_ipa(word)
        ipa_clean, stress_idx = strip_stress(ipa_raw)
        tokens = tokenize(ipa_clean)
        segments = segment(tokens)

        rendered_segments = []
        for seg_tokens in segments:
            seg_ipa = "".join(seg_tokens)

            # Versuche Split-Match für bessere visuelle Darstellung
            split_result = self._try_split_match(seg_ipa, threshold)
            if split_result and any(s.match for s in split_result):
                rendered_segments.extend(split_result)
            else:
                rendered = self._match_one(seg_ipa, threshold)
                rendered_segments.append(rendered)

        if verbose:
            segments_raw = [segments_to_str([s]) for s in segments]
            return render_verbose(word, ipa_raw, stress_idx, segments_raw, rendered_segments)
        else:
            return render(word, ipa_raw, stress_idx, rendered_segments)
