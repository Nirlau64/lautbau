# LautBau — Konzept: Phonetische Aussprachehilfe durch muttersprachliche Wortbausteine

> **Status:** Design-Phase abgeschlossen — bereit für Spike-Prototyp
> **Datum:** 15.07.2026, 17:43
> **Autor:** Hermes / Nirlau
> **Letzte Änderung:** Design-Entscheidungen §6 integriert

---

## 1. Ziel

Ein Tool, das die korrekte Aussprache eines fremdsprachigen Wortes (z.B. Englisch) für einen deutschen Muttersprachler **ohne IPA-Kenntnisse** verständlich macht — indem es die phonetischen Bestandteile des Fremdworts mit **Teilen bekannter deutscher Wörter** beschreibt.

**Beispiele (Darstellung: natives Wort vollständig, irrelevante Teile ausgegraut):**

```
though → (ð: Zunge zwischen Zähnen, wie weiches 'd') + Zoo
         ───────────────────────────────────────────   ──
                                                       relevant

squirrel → Ski + wäre + Kamel
           ──    ──       ──
           ⚡              (betont: erste Silbe)
```

**Plain-Text-Notation** (wo ANSI nicht verfügbar):
```
though → (ð: Zunge zwischen Zähnen) + Z[oo]
squirrel → [Sk]i + w[är]e + Kam[el]
           ⚡
```

---

## 2. Abgrenzung: Was existiert, was ist neu

| Tool | Macht | Fehlt |
|---|---|---|
| **TransPhoner** (2014) | Findet ganze phonetisch ähnliche Keywords sprachübergreifend | Keine Zerlegung, keine partiellen Matches |
| **PhoniTale** (2025) | Segmentiert IPA + matched Segmente gegen koreanische Wörter | Korean-spezifisch, kein Partial-Matching („Mitte von X"), Research-Code |
| **Wakean Word Forge** (2026) | `phonetic_neighbors()` via panphon-Distanz, Portmanteau-Forge | Designed für Literatur, nicht für Aussprache-Lernen |

**Neu an LautBau:**
- **Partielles Matching**: Nicht „Wort A klingt wie Wort B", sondern „Teil X von Fremdwort klingt wie Teil Y von deutschem Wort"
- **Positionsbewusst**: Ausgabe beschreibt WO im nativen Wort der Match sitzt (Anfang / Mitte / Ende)
- **Fuzzy-Threshold**: Kein exaktes IPA-Matching — „close enough" via panphon articulatory feature distance
- **Kombinatorik**: Mehrere Teil-Matches werden zu einer Aussprache-Anleitung zusammengesetzt

---

## 3. Algorithmus-Design

### Phase 1: IPA-Extraktion

```
Input: "though" (en)
  ↓ epitran / CMUdict
IPA:  /ðoʊ/
```

**Datenquelle:** 
- Englisch: CMU Pronouncing Dictionary (CMUdict) oder epitran `eng-Latn`
- Deutsch: epitran `deu-Latn` oder Wiktionary-IPA via kaikki.org

### Phase 2: Segmentierung

Der IPA-String wird in **matcchbare Segmente** zerlegt. Nicht strikt nach Silben — sondern so, dass Segmente eine realistische Chance haben, in deutschen Wörtern als Substring vorzukommen.

**Strategien (nach Priorität):**

1. **Onset-Nucleus-Coda (Präferiert):** Zerlege Silben in Konsonant-Cluster + Vokal(+Konsonant). 
   - `/ðoʊ/` → eher als Ganzes matchen (ist kurz genug), sonst: `[ð]` + `[oʊ]`

2. **Phonem-Paar-Gruppierung:** Zwei bis drei benachbarte Phoneme bilden ein Segment. 
   - Längere Wörter: `squirrel` /ˈskwɜrəl/ → `[skw]` `[ɜr]` `[əl]`

3. **Fallback: Gleitendes Fenster** — wenn Segment 1 keinen Match findet, Fenster vergrößern/verkleinern und neu versuchen.

**Heuristik:**
- Segmente sollten 2-4 Phoneme lang sein (Einzelphoneme sind nicht aussagekräftig genug)
- Vokale bevorzugt MIT umgebenden Konsonanten gruppieren (reiner Vokal-Match ist zu vage)
- Segmentgrenzen an natürlichen Übergängen: zwischen Konsonant-Cluster und Vokal

### Phase 3: Phonetisches Partial-Matching

Für jedes Segment wird die **deutsche Wortdatenbank** nach Substring-Matches im IPA-Raum durchsucht.

```
Segment: [oʊ]
  ↓ Suche in DE-Wortliste (364K Einträge, IPA-Substrings)

Kandidaten (mit Match-Position):
  "Zoo"     /tsoː/      → Substring [oː]  an Position 2-3  (Ende)  
  "Boot"    /boːt/      → Substring [oː]  an Position 2     (Mitte)
  "Dose"    /ˈdoːzə/    → Substring [oː]  an Position 2     (Mitte)
  "Kohl"    /koːl/      → Substring [oː]  an Position 2     (Mitte)
```

**Distanz-Berechnung:**
- panphon: `[oʊ]` vs `[oː]` → Feature-Distanz (21-dimensionale Vektoren)
- Schwellwert: Distanz < 0.3 → „match", 0.3–0.5 → „ähnlich", > 0.5 → verwerfen
- Gewichtung: Vokalqualität stärker gewichten als Länge (weil Deutsche [oː] vs [oʊ] intuitiv als „ähnliches o" wahrnehmen)

**Position im nativen Wort:**
- Match an Position 0–20% der Wortlänge → „Anfang von"
- Match an Position 20–80% → „Mitte von"  
- Match an Position 80–100% → „Ende von"

### Phase 4: Ranking & Selektion

Kandidaten-Ranking pro Segment:

1. **Phonetische Distanz** (primär) — je niedriger, desto besser
2. **Wort-Bekanntheit** (sekundär) — häufige, kurze Wörter bevorzugen („Zoo" > „Zoologe")
3. **Match-Präzision** — je mehr Phoneme des Segments abgedeckt, desto besser
4. **Position im nativen Wort** — klare Positionen (Anfang/Ende) > Mitte (schwerer zu isolieren beim Nachsprechen)

### Phase 5: Assembly & Output

**Darstellungsprinzip:** Das native Wort wird VOLLSTÄNDIG angezeigt — irrelevante Teile ausgegraut (ANSI dim), der relevante Phonem-Match hervorgehoben. So kann der Nutzer sich von Wortteil zu Wortteil hangeln, ohne kognitive Last durch fragmentierte Darstellung.

```
Segment-Matches:
  [ð]   → Kein DE-Match → Artikulations-Hinweis
  [oʊ]  → IPA-Match in "Zoo" /tsoː/ → Substring [oː] an Position 2-3 (Ende)

Output (ANSI):
  though → (ð: Zunge zwischen Zähnen, wie weiches 'd') + Zoo
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^   ^^
           dim (Artikulations-Hinweis)                    bold (relevanter Teil)

Output (Plain-Text):
  though → (ð: Zunge zwischen Zähnen) + Z[oo]
```

**Betonung:** Primary stress (ˈ) wird als ⚡ am betonten Segment markiert. Im ANSI-Modus: betontes Segment fett.

```
photography /fəˈtɑɡrəfi/ → Foto + Tasche + VIEH
                            ──    ──        ──
                                  ⚡
```

**Regeln für die visuelle Darstellung:**
1. Fremdwort (Input) immer fett/dim je nach Kontext
2. Native Wörter VOLLSTÄNDIG anzeigen
3. Relevanter Phonem-Teil im nativen Wort → **bold/bright**; irrelevanter Teil → ANSI dim (`\033[2m`)
4. Artikulations-Hinweise (für Phoneme ohne DE-Äquivalent) → in Klammern, kursiv/dim
5. Betonung → ⚡ vor oder über dem betonten Segment
6. Fallback Plain-Text: `[relevant]irrelevant` Notation (für Non-ANSI-Terminals)

**Sonderfälle:**
- **Kein DE-Match für Phonem:** Artikulations-Beschreibung statt nativem Wortteil (siehe oben: ð, θ, æ, w etc.)
- **Phonem existiert nicht im Deutschen:** Feste Lookup-Tabelle mit ~10-15 Einträgen (ð, θ, æ, ʌ, ɝ, w, ʒ, dʒ, ɹ, ŋ etc.)
- **Sehr kurze Wörter (≤3 Phoneme):** Nicht segmentieren — direkt als Ganzes matchen + ggf. Artikulations-Hinweis
- **Mehrere gleich gute Matches:** Kürzestes/bekanntestes Wort wählen

---

## 4. Architektur

```
┌─────────────────────────────────────────────────┐
│                  LautBau CLI                      │
│  $ laubau "though" --from en --to de             │
└──────────────────┬──────────────────────────────┘
                   │
      ┌────────────┼────────────┐
      ▼            ▼            ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ IPA      │ │ Segment  │ │ Matcher  │
│ Engine   │ │ Engine   │ │ Engine   │
│          │ │          │ │          │
│ epitran  │ │ Phoneme- │ │ panphon  │
│ CMUdict  │ │ Grouping │ │ distance │
│ Wiki-IPA │ │          │ │ DE-Wort- │
└──────────┘ └──────────┘ │ DB       │
                           └──────────┘
                   │
                   ▼
            ┌──────────┐
            │ Renderer │
            │          │
            │ Text-    │
            │ Output   │
            └──────────┘
```

### Komponenten:

| Komponente | Technologie | Quelle |
|---|---|---|
| IPA-Konvertierung (EN) | epitran `eng-Latn` + CMUdict Fallback | pip install epitran |
| IPA-Konvertierung (DE) | epitran `deu-Latn` | pip install epitran |
| Phonetische Distanz | panphon | pip install panphon |
| Deutsche Wortdatenbank | SQLite aus kaikki.org JSONL (364K DE-Einträge) | Wakean Word Forge Ingest-Pipeline recyclen |
| Segmentierer | Eigenbau (Python) | — |
| Partial IPA Matcher | Eigenbau (Python) | — |

### Daten-Pipeline:

1. **Initial:** Deutsche Wortdatenbank aus kaikki.org JSONL einlesen → SQLite (`de_words.db`)
   - Schema: `word TEXT, ipa TEXT, language TEXT`
   - Index: FTS5 auf IPA für Substring-Suche
2. **Runtime:** IPA-Strings der nativen Wörter gegen Segment-IPA matchen via panphon
3. **Caching:** Häufige Matches cachen (z.B. `[oʊ]→Zoo`)

---

## 5. User Interface

### CLI (MVP):
```bash
$ laubau "though"
though → (ð: Zunge zwischen Zähnen, wie weiches 'd') + Zoo

$ laubau "squirrel" --verbose
squirrel /ˈskwɜrəl/:
  [skw] → Ski        (Distanz: 0.12, Position: Anfang)
  [ɜr]  → wäre       (Distanz: 0.18, Position: Mitte)
  [əl]  → Kamel      (Distanz: 0.08, Position: Ende)
  ⚡ = betont
squirrel → Ski + wäre + Kamel

$ laubau "photography"
photography → Foto + Tasche + VIEH
                    ⚡
```

### Optionen:
- `--from LANG` (default: en)
- `--to LANG` (default: de)
- `--threshold FLOAT` (default: 0.3, höher = lockerer)
- `--verbose` / `-v` — Segment-Details anzeigen
- `--ipa` — IPA-Transkription mit ausgeben

### Web-UI (später):
- Einfaches Eingabefeld + Sprache-Selector
- Ausgabe mit farblich markierten Wort-Teilen
- Audio-Playback via TTS (nice-to-have)

---

## 6. Design-Entscheidungen & Fallback-Strategie

### 6.1 Gestaffelte Fallback-Strategie für Nicht-Matches

Wenn ein Segment keinen Match im Deutschen findet, wird diese Reihenfolge abgearbeitet:

```
Stufe 1: Segment wie gegeben matchen (Distanz < 0.3)
  ✅ Match gefunden → direkt verwenden
  ❌ kein Match

Stufe 2: Segment aufspalten in kleinere Einheiten
  [skw] → [s] + [kw]
  [kw] gibt's im Deutschen: "Quelle" /ˈkvɛlə/
  ✅ Teil-Match gefunden

Stufe 3: Segment mit Nachbarsegment fusionieren (größeres Fenster)
  [ɜr] + [əl] → [ɜrəl]
  Vergrößertes Fenster hat höhere Match-Chance

Stufe 4: Artikulations-Beschreibung (für Phoneme ohne DE-Äquivalent)
  Feste Lookup-Tabelle mit Beschreibungstexten:
  ┌──────┬──────────────────────────────────────────────┐
  │ /ð/  │ Zunge zwischen Zähnen, wie weiches 'd'        │
  │ /θ/  │ Zunge zwischen Zähnen, wie scharfes 's'       │
  │ /æ/  │ Zwischen 'a' und 'ä', Mund breit (wie „cat")  │
  │ /w/  │ Lippen rund wie für 'u', dann schnell öffnen  │
  │ /ɹ/  │ Zunge zurückgerollt, kein rollendes r         │
  │ /ʒ/  │ Wie 'j' in „Journal" (stimmhaftes sch)        │
  │ /dʒ/ │ Wie 'd' + 'j' zusammen („Dschungel")          │
  │ /ʌ/  │ Kurzes, offenes 'a' (wie „butter")            │
  │ /ŋ/  │ Wie 'ng' in „singen" — gibt's im DE, nur nie am Anfang │
  └──────┴──────────────────────────────────────────────┘

Stufe 5: Ganzer IPA-String als Fallback
  "Keine Teil-Matches gefunden. Klingt insgesamt am ehesten wie [ganzes DE-Wort]"
```

### 6.2 Betonung

- Nur **Primary Stress** (ˈ) wird markiert
- Darstellung: ⚡ vor dem betonten Segment; im ANSI-Modus fett
- Secondary Stress (ˌ) wird ignoriert (fürs MVP nicht relevant)
- Keine Rhythmus-Beschreibung („kurz-lang-kurz") — erst Phase 2

### 6.3 Darstellung

- **Natives Wort immer vollständig** anzeigen
- Irrelevante Teile: ANSI dim (`\033[2m`) oder Plain-Text `[x]` Notation
- Relevante Phonem-Teile: **bold/bright**
- Artikulations-Hinweise: in Klammern, vom Rest abgesetzt
- Kein „Ende von X" / „Anfang von Y" — die visuelle Hervorhebung am vollen Wort macht die Position selbsterklärend

### 6.4 Sehr kurze Wörter

Wörter mit ≤3 Phonemen werden **nicht segmentiert**, sondern als Ganzes gegen die deutsche Wortliste gematcht. Bei Phonemen ohne DE-Äquivalent (z.B. `cat` /kæt/) wird ein Artikulations-Hinweis ergänzt.

---

## 7. Technische Machbarkeit

### Was existiert bereits:
- ✅ `panphon` — phonetische Distanz auf IPA-Strings (pip-installable, 0 dependencies)
- ✅ `epitran` — IPA-Konvertierung für EN und DE (60+ Sprachen)
- ✅ kaikki.org — strukturierte Wiktionary-Dumps mit IPA (monatlich aktualisiert)
- ✅ Wakean Word Forge — Referenz-Implementierung für Ingest + `phonetic_neighbors()`

### Was gebaut werden muss:
- 🔨 IPA-Segmentierer (die eigentliche Innovation)
- 🔨 Partial-Substring-Matcher über IPA (FTS5 + panphon)
- 🔨 Output-Renderer mit Positions-Beschreibung
- 🔨 CLI-Frontend

### Geschätzter Aufwand:
- **MVP (EN→DE, CLI):** ~500-800 Zeilen Python, 2-3 Tage
- **Deutsche Wort-DB aufbauen:** 1x Ingest-Script (~30 Min Laufzeit auf 364K Einträgen)
- **Web-UI:** zusätzlich 1-2 Tage (Flask + minimales Frontend)

---

## 8. Nächste Schritte

1. **Spike: IPA-Segmentierer-Prototyp** — Ein Python-Script, das ein englisches Wort in IPA umwandelt und sinnvoll segmentiert
2. **Spike: Partial Matcher** — Segment gegen deutsche IPA-Datenbank matchen, Top-3-Kandidaten ausgeben
3. **Daten-Ingest:** Deutsche Wortdatenbank aus kaikki.org aufbauen
4. **MVP:** CLI-Tool das alles zusammenführt
5. **Evaluation:** 20 Testwörter (Englisch→Deutsch), manuell bewerten ob die Ausgabe hilfreich ist

---

## 9. Name

**Arbeitstitel: „LautBau"** — kurz, deutsch, selbsterklärend („Bau" = Konstruktion aus Lauten).

Alternativen: KlangBrücke, PhonoMatch, AusspracheBau.

---

> **Nächster Schritt:** Feedback von Nirlau einholen, dann Spike-Prototyp bauen.
