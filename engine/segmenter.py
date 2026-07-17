"""IPA-Segmentierer: Zerlegt IPA-String in matchbare Segmente (1-4 Phoneme)."""

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


def tokenize(ipa: str) -> list[str]:
    """Zerlegt IPA-String in Phonem-Tokens."""
    tokens = []
    i = 0
    while i < len(ipa):
        ch = ipa[i]
        if ch in "͜͡":
            if tokens and i + 1 < len(ipa):
                tokens[-1] = tokens[-1] + ipa[i + 1]
                i += 2
                continue
            i += 1
            continue
        if i + 1 < len(ipa):
            pair = ipa[i : i + 2]
            if pair in DIPHTHONGS or (_is_vowel(ipa[i]) and _is_vowel(ipa[i + 1])):
                tokens.append(pair)
                i += 2
                continue
        tokens.append(ch)
        i += 1
    return tokens


def segment(tokens: list[str]) -> list[list[str]]:
    """Gruppiert Phonem-Tokens in matchbare Segmente.

    Strategie: Onset vom Nucleus+Coda trennen. Dadurch können
    triviale Konsonanten (wie /n/, /t/) einzeln bleiben und
    der interessante Teil (Vokal+Diphthong) separat gematcht werden.

    Beispiele:
        /naɪt/ → [n] [aɪt]
        /kæt/  → [k] [æt]
        /ðoʊ/  → [ð] [oʊ]
    """
    segments = []
    i = 0

    while i < len(tokens):
        remaining = len(tokens) - i

        if remaining == 0:
            break

        # Wenig übrig → Rest als Segment
        if remaining <= 1:
            segments.append(tokens[i:])
            break

        # Nächsten Vokal finden
        vowel_pos = None
        for j in range(i, min(i + 4, len(tokens))):
            if _is_vowel(tokens[j]) or (
                len(tokens[j]) == 2 and any(_is_vowel(c) for c in tokens[j])
            ):
                vowel_pos = j
                break

        if vowel_pos is None:
            segments.append(tokens[i : i + 2])
            i += 2
            continue

        # Onset (Konsonanten vor Vokal) als eigenes Segment?
        # Nur wenn: mindestens 2 Konsonanten ODER das gesamte Wort ≥5 Phoneme hat
        onset_end = vowel_pos
        onset_size = onset_end - i
        if onset_size >= 2 or (onset_size >= 1 and len(tokens) >= 5):
            segments.append(tokens[i:onset_end])
            i = onset_end
            continue

        # Onset nicht abgespalten → ganzes Segment ab i
        coda_end = min(len(tokens), vowel_pos + 2)
        segments.append(tokens[i:coda_end])
        i = coda_end

    # Merge: zu kurze Segmente an Nachbarn (nur wenn beide konsonantisch)
    merged = []
    for seg in segments:
        if merged and len(seg) == 1 and len(merged[-1]) == 1:
            merged[-1].extend(seg)
        else:
            merged.append(seg)

    return merged


def segments_to_str(segments: list[list[str]]) -> str:
    return " · ".join("".join(seg) for seg in segments)
