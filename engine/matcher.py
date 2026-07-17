"""Matcher v2: FTS5-basierte Phonem-Suche statt LIKE-Grobfilter.

Architektur:
1. FTS5 Phrase-Query: "k æ t" → exakte Phonem-Folge in DB
2. Falls 0 Treffer: Vokal/Diphthong-Approximation → Retry
3. Falls 0: Teil-Sequenz (nur Vokale + benachbarte Konsonanten)
4. panphon Feature-Distance als Ranking
5. Wort-Qualitäts-Score als Tie-Breaker
"""

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import panphon.distance

# ── Approximation ──────────────────────────────────────────────────────

DIPHTHONG_APPROX = {
    "oʊ": "oː",
    "eɪ": "eː",
    "aɪ": "aɪ",
    "aʊ": "aʊ",
    "ɔɪ": "ɔʏ",
    "ɪə": "iːɐ",
    "eə": "eːɐ",
    "ʊə": "uːɐ",
}

VOWEL_APPROX = {
    "æ": "ɛ",
    "ʌ": "a",
    "ɜ": "œ",
    "ɝ": "œ",
    "ɒ": "ɔ",
    "ɑ": "a",
    "ʊ": "ʊ",
    "ɔ": "ɔ",
}

CONSONANT_APPROX = {
    "ð": "d",
    "θ": "s",
    "w": "v",
    "ɹ": "r",
    "ɾ": "r",
}

# Häufige deutsche Wörter für Ranking-Bias
COMMON_GERMAN = set("""
der die und in den von zu das mit sich des auf für ist im dem nicht ein
eine auch es als wird nach dass da er hat wie bei einen war ein wir einer
sein einem aber vor zur haben zum über noch sie mich mir doch mehr können
kann nur sehr ihr ja wenn schon gut diese weil dann man uns soll also bis
oder was Zeit Jahre Jahr muss keine sind Leben heute weiter zwischen schon
immer gehen stehen sehen kommen wissen machen lassen Frau Mann Kind Tag
Haus Hand Freund Leute Auge Herz Kopf Welt Frage Arbeit Stadt Weg Land
Geld Name Wort Satz Art Zahl Ende Nacht Stunde Platz Ding Buch Bild Sprache
Grund Blick Wasser Feuer Luft Boden Himmel Sonne Licht Kraft Liebe Angst
Spiel Sinn Tat Stelle Raum Seite Form Macht Recht Stück Rolle Wert Preis
Ehre Schutz Ziel Glück Kunst Geist Erfolg Hilfe Ruhe Lust Mitte Gruppe
Idee Wahl Rede Spur Linie Natur Krieg Schuld Sorge Traum Punkt Figur Masse
Kreis Folge Lehre Regel Weise Ordnung Pflicht Plan Berg See Wald Tier Hund
Katze Vogel Fisch Brot Wein Milch Kuchen Salz Suppe Ei Obst Gemüse Fleisch
Wurst Käse Butter Tee Kaffee Bier Saft Teller Tasse Glas Messer Gabel
Löffel Topf Pfanne Herd Ofen Tisch Stuhl Bett Schrank Regal Fenster Tür
Wand Dach Zimmer Küche Bad Keller Garten Zaun Baum Gras Blume Strauch Ast
Blatt Wurzel Frucht Samen Feld Wiese Park Hof Auto Bus Bahn Rad Schiff
Fahrrad Motor Kette Bremse Reifen Tank Öl Benzin Strom Gas Solar Wind
Schuh Hose Hemd Jacke Mantel Mütze Rock Kleid Anzug Krawatte Gürtel Tasche
Rucksack Koffer Beutel Sack Paket Brief Karte Post Zeitung Buch Heft Stift
Schere Kleber Band Faden Nadel Knopf Haken Nagel Schraube Hammer Zange Säge
Leiter Seil Schloss Schlüssel Ring Uhr Stein Holz Metall Gold Silber Eisen
Blei Kupfer Zink Nickel Chrom Plastik Gummi Leder Wolle Baumwolle Seide
Papier Pappe Ton Sand Kalk Lehm Erde Fels Berg Tal Fluss Meer Ozean Insel
Küste Strand Welle Ebbe Flut Sturm Regen Schnee Eis Frost Tau Nebel Wolke
Blitz Donner Hagel alle beide viele einige wenige keine jeder dieser jener
welcher mein dein sein unser euer ihr Anfang Ende groß klein alt neu jung
lang kurz rund eckig flach tief hoch niedrig breit schmal dick dünn stark
schwach schnell langsam hart weich warm kalt heiß kühl frisch müde wach
krank gesund blind taub stumm lahm reich arm stolz mutig feige tapfer faul
fleißig frech höflich grob fein klar trüb bunt einfach doppelt halb ganz
wenig viel mehr weniger genug voll leer offen geschlossen frei besetzt billig
teuer richtig falsch genau sicher möglich nötig wichtig bekannt fremd nah
fern links rechts oben unten vorn hinten drin draußen hier dort da weg
Boot Zoo Ski Dose Maus Baum Traum Kuh Buch Kind Käse Sonne Butter Woche
Blume Apfel Vater Mutter Bruder Schwester Straße Licht Nacht Kirche Insel
Vogel Essen Trinken Schlafen Laufen Sitzen Gehen Kommen Sagen Fragen Antwort
Mut Stolz Dank Bitte Liebe Glück Freude Leid Schmerz Wunder Hoffnung Schatten
Spiegel Engel Regen Segen Wagen Hafen Donner Wetter Mond Stern Feuer Stahl
Euro Cent Mark Pfund Kilo Meter Liter Minute Monat
nicht dein sein hier dort jetzt heute morgen gestern Abend Nacht Mittag
wieder immer noch schon bald später früher manchmal oft selten nie immer
""".split())


@dataclass
class Match:
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
    """FTS5-basierter Partial Matcher."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._dst = panphon.distance.Distance()

    def find_matches(
        self,
        segment_ipa: str,
        threshold: float = 0.5,
        top_n: int = 5,
    ) -> list[Match]:
        """Findet die besten Matches für ein IPA-Segment.

        Strategie (kaskadierend):
        1. Exact FTS5 Phrase-Query
        2. Approximation + FTS5 Phrase-Query
        3. Teil-Sequenzen (Vokal + Nachbarn)
        4. panphon auf allen Kandidaten
        """
        matches: list[Match] = []

        # Segment in Tokens zerlegen (space-separated für FTS5)
        tokens = self._tokenize_segment(segment_ipa)
        if not tokens:
            return []

        # Stufe 1: Exact FTS5
        candidates = self._fts_query(tokens)
        if candidates:
            matches = self._rank_candidates(segment_ipa, candidates, threshold)

        # Stufe 2: Approximation + FTS5
        if not matches or (matches and matches[0].distance > 0.2):
            approx = self._approximate(segment_ipa)
            if approx and approx != segment_ipa:
                approx_tokens = self._tokenize_segment(approx)
                if approx_tokens:
                    approx_candidates = self._fts_query(approx_tokens)
                    if approx_candidates:
                        approx_matches = self._rank_candidates(approx, approx_candidates, threshold)
                        # Übernehmen wenn besser
                        if not matches or (
                            approx_matches and approx_matches[0].distance < matches[0].distance
                        ):
                            matches = approx_matches

        # Stufe 3: Teil-Sequenzen (Subsequences)
        if not matches and len(tokens) >= 2:
            sub_matches = self._try_subsequences(segment_ipa, tokens, threshold)
            if sub_matches:
                matches = sub_matches

        return matches[:top_n]

    def _tokenize_segment(self, ipa: str) -> list[str]:
        """Tokenisiert IPA-String in einzelne Phoneme."""
        # Bereits tokenisiert?
        if " " in ipa:
            return ipa.split()

        # Manuell tokenisieren
        result = []
        i = 0
        while i < len(ipa):
            # Diphthong?
            if i + 1 < len(ipa):
                pair = ipa[i : i + 2]
                if pair in {"aɪ", "aʊ", "ɔɪ", "eɪ", "oʊ", "ɔʏ", "aɪ̯", "aʊ̯"}:
                    result.append(pair)
                    i += 2
                    continue
            # Längemarkierung
            if ipa[i] == "ː":
                if result:
                    result[-1] = result[-1] + "ː"
                i += 1
                continue
            result.append(ipa[i])
            i += 1
        return result

    def _fts_query(self, tokens: list[str]) -> list[tuple[str, str, str]]:
        """FTS5 Phrase-Query: findet Wörter mit exakter Phonem-Folge.

        Returns: [(word, ipa, phonemes), ...]
        """
        conn = sqlite3.connect(str(self.db_path))

        # Phrase-Query: "k æ t" → exakte Reihenfolge
        phrase = " ".join(tokens)
        query = f'"{phrase}"'

        try:
            rows = conn.execute(
                """SELECT w.word, w.ipa, w.phonemes
                   FROM words_fts f
                   JOIN words w ON w.id = f.rowid
                   WHERE words_fts MATCH ?
                   LIMIT 100""",
                (query,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        # Falls Phrase-Query zu wenig: AND-Query (alle Phoneme, beliebige Reihenfolge)
        if len(rows) < 10:
            and_query = " ".join(tokens)
            try:
                and_rows = conn.execute(
                    """SELECT w.word, w.ipa, w.phonemes
                       FROM words_fts f
                       JOIN words w ON w.id = f.rowid
                       WHERE words_fts MATCH ?
                       LIMIT 100""",
                    (and_query,),
                ).fetchall()
                # Merge, dedup by word
                seen = {r[0] for r in rows}
                for r in and_rows:
                    if r[0] not in seen:
                        rows.append(r)
                        seen.add(r[0])
            except sqlite3.OperationalError:
                pass

        conn.close()
        return [(r[0], r[1], r[2]) for r in rows]

    def _rank_candidates(
        self,
        segment_ipa: str,
        candidates: list[tuple[str, str, str]],
        threshold: float,
    ) -> list[Match]:
        """Rankt Kandidaten via panphon Feature-Distance."""
        matches = []

        for word, ipa, phonemes in candidates:
            clean_ipa = ipa.replace("ˈ", "").replace("ˌ", "").replace(".", "").replace(" ", "").replace("̯", "")

            # Sliding window: finde beste Position im Wort
            seg_len = len(segment_ipa)
            for window_size in range(max(1, seg_len - 1), min(len(clean_ipa) + 1, seg_len + 2)):
                for start in range(len(clean_ipa) - window_size + 1):
                    end = start + window_size
                    sub = clean_ipa[start:end]
                    try:
                        dist = self._dst.feature_edit_distance(segment_ipa, sub)
                    except Exception:
                        continue
                    if dist <= threshold:
                        matches.append(Match(
                            word=word, ipa=clean_ipa,
                            match_start=start, match_end=end,
                            segment_ipa=sub, distance=dist,
                        ))

        if not matches:
            return []

        # Best per word
        best: dict[str, Match] = {}
        for m in matches:
            if m.word not in best or m.distance < best[m.word].distance:
                best[m.word] = m

        # Sort: distance * 10 + word_score / 100
        return sorted(
            best.values(),
            key=lambda m: m.distance * 10 + self._word_score(m.word) / 100,
        )

    def _try_subsequences(
        self,
        segment_ipa: str,
        tokens: list[str],
        threshold: float,
    ) -> list[Match]:
        """Versucht kürzere Subsequences wenn keine Full-Matches gefunden wurden."""
        matches = []

        # Alle Subsequences der Länge len-1
        for skip_idx in range(len(tokens)):
            sub_tokens = tokens[:skip_idx] + tokens[skip_idx + 1 :]
            if not sub_tokens:
                continue
            candidates = self._fts_query(sub_tokens)
            if candidates:
                # Subsequence gegen Original-Segment matchen
                sub_ipa = "".join(sub_tokens)
                ranked = self._rank_candidates(segment_ipa, candidates, threshold)
                if ranked:
                    matches.extend(ranked)

        if not matches:
            return []

        # Best per word
        best: dict[str, Match] = {}
        for m in matches:
            if m.word not in best or m.distance < best[m.word].distance:
                best[m.word] = m

        return sorted(
            best.values(),
            key=lambda m: m.distance * 10 + self._word_score(m.word) / 100,
        )

    @staticmethod
    def _approximate(ipa: str) -> str | None:
        """Ersetzt englische Phoneme durch deutsche Entsprechungen."""
        result = ipa
        changed = False
        for eng, de in DIPHTHONG_APPROX.items():
            if eng in result:
                result = result.replace(eng, de)
                changed = True
        for eng, de in CONSONANT_APPROX.items():
            if eng in result:
                result = result.replace(eng, de)
                changed = True
        for eng, de in VOWEL_APPROX.items():
            if eng in result:
                result = result.replace(eng, de, 1)
                changed = True
        return result if changed else None

    @staticmethod
    def _word_score(word: str) -> float:
        """Bewertet Wort-Qualität. Niedriger = besser."""
        score = 0.0

        if " " in word or "-" in word:
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

        if word.lower() not in COMMON_GERMAN:
            if word.isascii() and word[0].islower() and len(word) > 2:
                score += 200.0
            if word.isascii() and len(word) > 6:
                score += 50.0

        if word.lower() in COMMON_GERMAN:
            score -= 50.0

        return score
