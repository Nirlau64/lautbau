"""Partial Matcher: IPA-Segmente gegen deutsche Wortdatenbank matchen via panphon."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import panphon.distance

# ── Diphthong-Approximation ─────────────────────────────────────────────

# Englische Phoneme → ähnlichste deutsche Entsprechung für Fallback-Suche
DIPHTHONG_APPROX = {
    "oʊ": "oː",   # "though" → deutsches langes o
    "eɪ": "eː",   # "say" → deutsches langes e
    "aɪ": "aɪ",   # "eye" → existiert im Deutschen ("Ei")
    "aʊ": "aʊ",   # "cow" → existiert im Deutschen ("Au")
    "ɔɪ": "ɔʏ",   # "boy" → "eu" in "heute"
    "ɪə": "iːɐ",  # "ear" → "ier" in "Bier"
    "eə": "eːɐ",  # "air" → "är" in "Bär"
    "ʊə": "uːɐ",  # "tour" → "ur" in "nur"
}

VOWEL_APPROX = {
    "æ": "ɛ",     # "cat" → deutsches kurzes ä
    "ʌ": "a",     # "but" → deutsches kurzes a
    "ɜ": "œ",     # "bird" → deutsches ö
    "ɝ": "œ",
    "ɒ": "ɔ",     # "hot" (BE) → deutsches kurzes o
    "ɑ": "a",     # "hot" (AE) → deutsches a
    "ʊ": "ʊ",     # "put" → existiert im Deutschen
    "ɔ": "ɔ",     # "thought" → deutsches o
}

# Konsonant-Approximation für Phoneme ohne DE-Äquivalent
CONSONANT_APPROX = {
    "ð": "d",   # "the" → deutsches d
    "θ": "s",   # "think" → deutsches s
    "w": "v",   # "we" → deutsches w (IPA: v)
    "ɹ": "r",   # "red" → deutsches r
    "ɾ": "r",   # Flap → deutsches r
}


# ── Deutsche Frequenzliste (Top ~500) ───────────────────────────────────

# Eingebettete Frequenzliste für Ranking-Bias.
# Quelle: Häufigkeitswörterbuch, extrahiert auf häufige kurze Wörter.
COMMON_GERMAN = set("""
der die und in den von zu das mit sich des auf für ist im dem nicht ein
die eine auch es als wird nach dass da er hat wie bei einen war ein
wir einer sein einem aber vor zur haben zum über noch sie mich mir
doch mehr können kann nur sehr ihr ja wenn schon gut diese weil dann
mich man uns soll also bis oder was Zeit Jahre Jahr muss keine sind
Leben heute weiter zwischen schon immer gehen stehen sehen kommen
wissen machen gehen lassen Frau Mann Kind Tag Haus Hand Freund Leute
Auge Herz Kopf Welt Frage Arbeit Stadt Weg Land Geld Name Wort Satz
Art Zahl Ende Nacht Stunde Platz Ding Buch Bild Sprache Grund Blick
Weg Wasser Feuer Luft Boden Himmel Sonne Licht Kraft Liebe Angst
Spiel Sinn Tat Stelle Raum Seite Form Macht Recht Stück Rolle Wert
Preis Blick Kraft Ehre Schutz Ziel Glück Sinn Kunst Geist Erfolg
Hilfe Ruhe Lust Mitte Gruppe Idee Wahl Rede Spur Linie Fläche
Natur Krieg Schuld Sorge Traum Punkt Anzug Figur Szene Masse Kreis
Folge Lehre Regel Weise Größe Ordnung Mode Pflicht Plan Seite Ruhe
Schuld Flucht Lust Lehre Rede Not Mode Netz Frist Post Wahl Bann
Berg See Wald Tier Hund Katze Vogel Fisch Brot Wein Milch Kuchen
Salz Pfeffer Suppe Soße Ei Obst Gemüse Fleisch Wurst Käse Butter
Tee Kaffee Wasser Bier Saft Teller Tasse Glas Messer Gabel Löffel
Topf Pfanne Herd Ofen Tisch Stuhl Bett Schrank Regal Fenster Tür
Wand Dach Zimmer Küche Bad Keller Garage Garten Zaun Baum Gras Blume
Strauch Ast Blatt Wurzel Frucht Samen Feld Wiese Wald Park Hof
Auto Bus Bahn Rad Schiff Flugzeug Fahrrad Motor Kette Bremse Reifen
Tank Öl Benzin Diesel Strom Gas Solar Wind Wasser Kraft Solar
Schuh Hose Hemd Jacke Mantel Mütze Rock Kleid Anzug Krawatte Gürtel
Tasche Rucksack Koffer Beutel Sack Paket Brief Karte Post Zeitung
Buch Heft Blatt Stift Schere Kleber Band Faden Nadel Knopf Haken
Nagel Schraube Hammer Zange Säge Leiter Seil Kette Schloss Schlüssel
Ring Kette Uhr Glas Stein Holz Metall Gold Silber Eisen Blei Kupfer
Zink Nickel Chrom Plastik Gummi Leder Wolle Baumwolle Seide Papier
Pappe Glas Ton Sand Kalk Lehm Erde Stein Fels Berg Tal Fluss See
Meer Ozean Insel Küste Strand Düne Welle Ebbe Flut Sturm Regen
Schnee Eis Frost Tau Nebel Wolke Blitz Donner Hagel Wind Frost
alle beide viele einige wenige keine jeder dieser jener welcher mein
dein sein unser euer ihr Anfang Ende groß klein alt neu jung lang
kurz rund eckig flach tief hoch niedrig breit schmal dick dünn
stark schwach schnell langsam hart weich warm kalt heiß kühl frisch
müde wach krank gesund blind taub stumm lahm reich arm stolz mutig
feige tapfer faul fleißig frech höflich grob fein klar trüb bunt
einfach doppelt dreifach halb ganz wenig viel mehr weniger genug voll
leer offen geschlossen frei besetzt billig teuer richtig falsch genau
ungefähr sicher möglich unmöglich nötig wichtig unwichtig bekannt
fremd nah fern links rechts oben unten vorn hinten drin draußen
drüben hier dort da weg fort los hierher überall nirgends
Boot Zoo Ski Dose Haus Maus Baum Traum Kuh Schuh Buch Hand Land
Kind Katze Käse Sonne Butter Woche Sprache Blume Himmel Apfel
Vater Mutter Bruder Schwester Fenster Garten Straße Licht Nacht
Kirche Arbeit Insel Vogel Fisch Brot Wein Milch Kuchen Salz Essen
Trinken Schlafen Laufen Sitzen Stehen Gehen Kommen Sagen Fragen
Antwort Hilfe Ruhe Lust Angst Mut Stolz Kraft Macht Recht Pflicht
Schuld Dank Bitte Grüße Liebe Glück Freude Leid Schmerz Wunder
Hoffnung Traum Schatten Spiegel Engel Regen Segen Wagen Hafen
Donner Blitz Sturm Wetter Wolke Sonne Mond Stern Himmel Erde
Feuer Wasser Luft Stahl Stein Holz Glas Gold Silber Geld Euro
Cent Mark Pfund Kilo Meter Liter Stunde Minute Woche Monat Jahr
""".split())


@dataclass
class Match:
    """Ein phonetischer Match zwischen IPA-Segment und deutschem Wort."""
    word: str
    ipa: str
    match_start: int
    match_end: int
    segment_ipa: str
    distance: float

    @property
    def match_quality(self) -> str:
        if self.distance < 0.15:
            return "exakt"
        elif self.distance < 0.3:
            return "sehr ähnlich"
        elif self.distance < 0.5:
            return "ähnlich"
        return "entfernt"


class Matcher:
    """Findet phonetische Partial-Matches in der deutschen Wortdatenbank."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._dst = panphon.distance.Distance()

    def _query_candidates(self, segment_ipa: str, limit: int = 500) -> list[tuple[str, str]]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        first_phone = segment_ipa[0]
        if len(segment_ipa) > 1 and segment_ipa[:2] in {
            "aɪ", "aʊ", "ɔɪ", "eɪ", "oʊ", "ɪə", "eə", "ʊə",
        }:
            first_phone = segment_ipa[:2]

        pattern = f"%{first_phone}%"
        rows = conn.execute(
            "SELECT word, ipa FROM words WHERE ipa LIKE ? LIMIT ?",
            (pattern, limit)
        ).fetchall()

        conn.close()
        return [(r["word"], r["ipa"]) for r in rows]

    def find_matches(
        self,
        segment_ipa: str,
        threshold: float = 0.5,
        top_n: int = 5,
    ) -> list[Match]:
        """Findet die besten Partial-Matches für ein IPA-Segment.

        Mit Diphthong/Vokal-Approximation als Fallback.
        """
        # Stufe 1: Exaktes Segment matchen
        matches = self._match_segment(segment_ipa, threshold)

        # Stufe 2: Falls keine guten Matches, Approximation versuchen
        best_score = matches[0].distance * 10 + self._word_score(matches[0].word) / 100 if matches else 999
        if not matches or best_score > 0.5:  # Niedriger Threshold = aggressivere Approximation
            approx = self._approximate(segment_ipa)
            if approx and approx != segment_ipa:
                approx_matches = self._match_segment(approx, threshold)
                if approx_matches:
                    approx_score = approx_matches[0].distance * 10 + self._word_score(approx_matches[0].word) / 100
                    if approx_score < best_score:
                        matches = approx_matches

        return matches[:top_n]

    def _match_segment(self, segment_ipa: str, threshold: float) -> list[Match]:
        """Interne Match-Logik für ein IPA-Segment."""
        candidates = self._query_candidates(segment_ipa)
        matches = []
        seg_len = len(segment_ipa)

        for word, ipa in candidates:
            clean_ipa = ipa.replace("ˈ", "").replace("ˌ", "").replace(".", "").replace(" ", "")

            for window_size in range(max(1, seg_len - 1), min(len(clean_ipa) + 1, seg_len + 2)):
                for start in range(len(clean_ipa) - window_size + 1):
                    end = start + window_size
                    sub_ipa = clean_ipa[start:end]

                    try:
                        dist = self._dst.feature_edit_distance(segment_ipa, sub_ipa)
                    except Exception:
                        continue

                    if dist <= threshold:
                        matches.append(Match(
                            word=word, ipa=clean_ipa,
                            match_start=start, match_end=end,
                            segment_ipa=sub_ipa, distance=dist,
                        ))

        best_per_word: dict[str, Match] = {}
        for m in matches:
            if m.word not in best_per_word or m.distance < best_per_word[m.word].distance:
                best_per_word[m.word] = m

        # Kombinierter Score: Distanz (primär) + Wort-Qualität (sekundär)
        # Erlaubt einem relevanten Wort mit leicht höherer Distanz,
        # ein irrelevantes mit perfekter Distanz zu schlagen.
        sorted_matches = sorted(
            best_per_word.values(),
            key=lambda m: m.distance * 10 + self._word_score(m.word) / 100
        )
        return sorted_matches

    @staticmethod
    def _approximate(ipa: str) -> str | None:
        """Ersetzt englische Phoneme durch deutsche Entsprechungen."""
        result = ipa
        changed = False
        # Diphthonge zuerst (längere Matches)
        for eng, de in DIPHTHONG_APPROX.items():
            if eng in result:
                result = result.replace(eng, de)
                changed = True
        # Konsonanten
        for eng, de in CONSONANT_APPROX.items():
            if eng in result:
                result = result.replace(eng, de)
                changed = True
        # Einzelvokale
        for eng, de in VOWEL_APPROX.items():
            if eng in result:
                result = result.replace(eng, de, 1)
                changed = True
        return result if changed else None

    @staticmethod
    def _word_score(word: str) -> float:
        """Bewertet Wort-Qualität. Niedriger = besser."""
        score = 0.0

        if " " in word:
            return 999.0

        length = len(word)
        if length > 12:
            score += 80.0
        elif length > 8:
            score += 30.0
        elif length > 6:
            score += 5.0

        if any(c in word for c in "áéíóúýàèìòùãõñêâîôûëï"):
            score += 100.0

        # ASCII-Only-Strafen — aber nicht für bekannte deutsche Wörter
        if word.lower() not in COMMON_GERMAN:
            if word.isascii() and word[0].islower() and len(word) > 2:
                score += 200.0
            if word.isascii() and len(word) > 6:
                score += 50.0

        # Frequenz-Bonus: häufige deutsche Wörter stark bevorzugen
        if word.lower() in COMMON_GERMAN:
            score -= 50.0

        return score
