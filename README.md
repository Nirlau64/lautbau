# LautBau

Phonetische Aussprachehilfe — zerlegt fremdsprachige Wörter in muttersprachliche Wortbausteine.

**MVP:** Englisch → Deutsch. CLI-Tool + später Web-UI.

## Status

Konzeptphase abgeschlossen. Bereit für Spike-Prototyp.

## Konzept

Siehe [`docs/konzept.md`](docs/konzept.md) für das vollständige Konzept.
Siehe [`docs/hosting-vergleich.md`](docs/hosting-vergleich.md) für Hosting-Strategie.

## Tech Stack (geplant)

- **CLI:** Python 3.10+, Click/argparse
- **IPA-Konvertierung:** epitran (EN: eng-Latn, DE: deu-Latn)
- **Phonetische Distanz:** panphon
- **Datenbank:** SQLite (via kaikki.org Wiktionary-Dumps)
- **Web-UI (Phase 2):** Static HTML/JS auf Cloudflare Pages + Precomputed IPA-Daten

## Projektstruktur

```
lautbau/
├── cli/            # CLI-Tool
├── engine/         # Core: Segmentierer, Matcher, Renderer
├── data/           # Ingest-Scripte + Daten
├── web/            # Web-UI (Phase 2)
├── docs/           # Konzepte, Design-Docs
└── tests/          # Test-Suite
```

## Quick Start (wenn MVP fertig)

```bash
pip install -r requirements.txt
python -m laubau "though"
```
