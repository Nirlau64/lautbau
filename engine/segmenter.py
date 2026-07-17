"""IPA-Segmentierer: Zerlegt IPA-String in matchbare Segmente (2-4 Phoneme)."""

# ── Phonem-Kategorien ───────────────────────────────────────────────────

VOWELS = set("iyɨʉɯuɪʏʊeøɘɵɤoəɛœɜɞʌɔæɐaɶɑɒ")
DIPHTHONGS = {
    "aɪ", "aʊ", "ɔɪ", "eɪ", "oʊ", "ɪə", "eə", "ʊə",
    "ɑɪ", "ɑʊ", "eɪ", "oʊ",
}
CONSONANTS = set("pbtdʈɖcɟkɡqɢʔɓɗʄɠʛmnɳɲŋɴʙrʀɾɽɸβfvθðszʃʒʂʐçʝxɣχʁħʕhɦɬɮʋɹɻjɰlɭʎʟwʍ")


def _is_vowel(ch: str) -> bool:
    return ch in VOWELS


def _is_consonant(ch: str) -> bool:
    return ch in CONSONANTS


# ── Tokenizer ───────────────────────────────────────────────────────────

def tokenize(ipa: str) -> list[str]:
    """Zerlegt IPA-String in Phonem-Tokens.

    Behandelt Diphthonge, ignoriert Diakritika.
    """
    tokens = []
    i = 0
    while i < len(ipa):
        ch = ipa[i]

        # Tie-Bar überspringen (Affrikaten)
        if ch in "͜͡":
            if tokens and i + 1 < len(ipa):
                tokens[-1] = tokens[-1] + ipa[i + 1]
                i += 2
                continue
            i += 1
            continue

        # Diphthong (2 Zeichen)
        if i + 1 < len(ipa):
            pair = ipa[i : i + 2]
            if pair in DIPHTHONGS or (_is_vowel(ipa[i]) and _is_vowel(ipa[i + 1])):
                tokens.append(pair)
                i += 2
                continue

        tokens.append(ch)
        i += 1

    return tokens


# ── Segmentierer ────────────────────────────────────────────────────────

def segment(tokens: list[str]) -> list[list[str]]:
    """Gruppiert Phonem-Tokens in matchbare Segmente.

    Strategie: Onset-Nucleus-Coda um Vokale herum.
    Segmente haben 2-4 Phoneme, kurze Wörter (≤3 Phoneme) bleiben ganz.

    Args:
        tokens: Liste von Phonem-Tokens (aus tokenize())

    Returns:
        Liste von Segmenten (jedes Segment = Liste von Tokens)
    """
    if len(tokens) <= 3:
        return [tokens]

    segments = []
    i = 0

    while i < len(tokens):
        remaining = len(tokens) - i

        # Wenig übrig → Rest als letztes Segment
        if remaining <= 2:
            segments.append(tokens[i:])
            break

        # Nächsten Vokal finden (als Segment-Anker)
        vowel_pos = None
        for j in range(i, min(i + 4, len(tokens))):
            if _is_vowel(tokens[j]) or (
                len(tokens[j]) == 2 and any(_is_vowel(c) for c in tokens[j])
            ):
                vowel_pos = j
                break

        if vowel_pos is None:
            # Kein Vokal in Reichweite → 2 Konsonanten als Segment
            segments.append(tokens[i : i + 2])
            i += 2
            continue

        # Onset: Konsonanten vor dem Vokal (max 3 am Wortanfang, sonst 2)
        max_onset = 3 if i == 0 else 2
        onset_start = max(i, vowel_pos - max_onset)
        coda_end = min(len(tokens), vowel_pos + 2)

        segment_tokens = tokens[onset_start:coda_end]

        # Nicht zu kurz: ggf. einen Token mehr
        if len(segment_tokens) < 2 and coda_end < len(tokens):
            segment_tokens = tokens[onset_start : coda_end + 1]

        # Nicht zu lang: auf max 4 kürzen
        if len(segment_tokens) > 4:
            segment_tokens = tokens[onset_start : vowel_pos + 2]

        segments.append(segment_tokens)
        i = coda_end

    # Merge: zu kurze Segmente (1 Token) an Nachbar anhängen
    merged = []
    for seg in segments:
        if merged and len(seg) <= 1:
            merged[-1].extend(seg)
        else:
            merged.append(seg)

    if len(merged) >= 2 and len(merged[-1]) <= 1:
        merged[-2].extend(merged[-1])
        merged.pop()

    return merged


def segments_to_str(segments: list[list[str]]) -> str:
    """Formatierte Ausgabe: 'skwər · əl'"""
    return " · ".join("".join(seg) for seg in segments)
