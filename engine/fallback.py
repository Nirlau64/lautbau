"""Fallback-Strategie: Artikulations-Hinweise für Phoneme ohne DE-Äquivalent."""

ARTICULATION_HINTS = {
    "ð": "Zunge zwischen Zähnen, wie weiches 'd'",
    "θ": "Zunge zwischen Zähnen, wie scharfes 's'",
    "æ": "Zwischen 'a' und 'ä', Mund breit (wie „cat\")",
    "w": "Lippen rund wie für 'u', dann schnell öffnen",
    "ɹ": "Zunge zurückgerollt, kein rollendes r",
    "ʒ": "Wie 'j' in „Journal\" (stimmhaftes sch)",
    "dʒ": "Wie 'd' + 'j' zusammen („Dschungel\")",
    "ʌ": "Kurzes, offenes 'a' (wie „butter\")",
    "ŋ": "Wie 'ng' in „singen\" (nie am Wortanfang)",
    "ɝ": "Betonte Variante von ɜ — wie 'ör' in „Wörthersee\"",
    "ɔ": "Offenes 'o', wie in „offen\"",
    "ɾ": "Einmaliges Zungenschlagen, wie 'tt' in amerikanisch „butter\"",
}


def get_hint(phoneme: str) -> str | None:
    """Gibt Artikulations-Hinweis für ein Phonem, oder None wenn DE-Äquivalent existiert."""
    # Normalisiere: ersten Char + ggf. Diphthong
    key = phoneme.strip()
    return ARTICULATION_HINTS.get(key)


def needs_hint(segment_ipa: str) -> bool:
    """Prüft ob ein Segment Phoneme enthält, die Artikulations-Hinweise brauchen."""
    for ch in segment_ipa:
        if ch in ARTICULATION_HINTS:
            return True
    return False
