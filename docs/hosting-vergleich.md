# LautBau — Hosting-Vergleich

> **Datum:** 17.07.2026, 10:05
> **Frage:** Welche Hosting-Strategie für das Web-UI (Phase 2) — Abwägung nach Kosten, Aufwand, Self-Hosting-Anteil

---

## Technische Anforderungen

| Anforderung | Warum |
|---|---|
| **Python-Runtime** | `epitran` (IPA-Konvertierung) + `panphon` (phonetische Distanz) sind Python-only |
| **~50-100 MB persistent Storage** | SQLite-Datenbank mit 364K deutschen Wörtern + IPA |
| **Statisches Frontend** | HTML/CSS/JS — Eingabefeld + Ergebnis-Rendering (ANSI/Highlight) |
| **API-Endpunkt** | `POST /api/pronounce` → `{word, from_lang, to_lang}` → `{result, segments}` |
| **Kein Cold Start > 2s** | Nutzer tippt Wort ein und will SOFORT Ergebnis |

---

## Optionen

### A: Static Site (CF Pages) + In-Browser Logik
**Architektur:** Precomputed IPA-Daten als JSON, Segmentierer + Matcher in JavaScript neu geschrieben. Kein Backend.

| Pro | Contra |
|---|---|
| 0€, zero maintenance | Segmentierer + panphon-Logik muss in JS neu geschrieben werden (~300 Zeilen) |
| Global CDN, instant load | DB-Größe begrenzt: 364K DE-Wörter mit IPA-Substring-Index ≈ 15-25 MB JSON |
| Kein Server, kein Sleep | panphon-Äquivalent in JS existiert nicht — müsste selbst gebaut werden |
| Cloudflare Pages = existierende Infra | Matching-Qualität ggf. schlechter als Python-panphon |

### B: CF Pages (Frontend) + HuggingFace Spaces (Backend)
**Architektur:** Statisches Frontend auf CF Pages, FastAPI-Backend auf HF Spaces (Docker, free).

| Pro | Contra |
|---|---|
| Python-Backend nativ (epitran + panphon) | Zwei Services = zwei Deploy-Pipelines |
| 0€, kein Self-Hosting | HF Spaces: 16 GB RAM aber **kein persistentes Volume** — DB muss ins Docker-Image gebacken werden |
| HF Spaces schläft nicht ein (aktiver Docker-Container) | Docker-Image mit 100 MB SQLite = groß, langsamer Build |
| Schnelles Setup (Dockerfile + requirements.txt) | HF Spaces CPU-Limit (2 vCPU shared) — Matching ggf. langsam bei vielen Requests |

### C: CF Pages (Frontend) + Self-Hosted Docker (Backend via CF Tunnel)
**Architektur:** Docker-Container auf lg-srv, exposed via Cloudflare Tunnel. Frontend auf CF Pages.

| Pro | Contra |
|---|---|
| Volle Kontrolle, persistent DB | Self-hosted — Wartung, Updates, Monitoring |
| Existierende Infrastruktur (Docker, CF Tunnel) | Nirlau: „fully selfhosted eher ungern" |
| Keine Resource-Limits (CPU, RAM) | Bei Ausfall von lg-srv: Tool down |
| Einfaches Deployment (git pull + docker restart) | — |

### D: Fly.io (Full Stack)
**Architektur:** FastAPI-Server + statische Files auf Fly.io. Free tier: 3 shared VMs, 3 GB persistent volume.

| Pro | Contra |
|---|---|
| Python nativ, persistent Volume (SQLite lebt) | Setup-Aufwand: Fly CLI, `fly.toml`, Dockerfile |
| 0€ im Free Tier (3 VMs, 3 GB Vol, 100 GB Bandbreite) | „Fully fremdgehosted" aber mit eigenem Account/Config |
| Kein Cold Start, kein Sleep | Free tier: shared CPU, 256 MB RAM pro VM — grenzwertig für panphon? |
| Ein Service, ein Deploy (`fly deploy`) | Neue Plattform im Stack (kein existierendes Know-How) |

### E: Render (Full Stack)
**Architektur:** FastAPI als Web Service auf Render. Free tier: 750h/Monat, 512 MB RAM.

| Pro | Contra |
|---|---|
| Simples Setup (Git-Push-Deploy) | **Schläft nach 15 Min Inaktivität** → erster Request dauert 30-60s |
| Python nativ | Kein persistentes Volume im Free Tier (DB weg bei Restart) |
| 0€ | Schlechte UX durch Cold Start — KO-Kriterium |

---

## Bewertungsmatrix

Gewichtung: Kosten ×3, Aufwand ×2.5, Self-Hosting-Vermeidung ×2, Performance ×2, Zukunft ×1

| Kriterium (Gewicht) | A: Static+JS | B: CF+HF Spaces | C: CF+Self | D: Fly.io | E: Render |
|---|---|---|---|---|---|
| **Kosten** (×3) | 5 (0€) | 5 (0€) | 5 (0€) | 5 (0€) | 5 (0€) |
| **Setup-Aufwand** (×2.5) | 2 (JS-Rewrite) | 4 (2 Services) | 3 (Docker) | 3 (Fly Setup) | 5 (Git-Push) |
| **Wenig Self-Hosting** (×2) | 5 (nichts) | 5 (nichts) | 2 (lg-srv) | 5 (nichts) | 5 (nichts) |
| **Performance** (×2) | 5 (CDN, instant) | 4 (API-Latenz) | 4 (Lokal schnell) | 3 (Shared CPU) | 1 (Cold Start) |
| **Wartung** (×2.5) | 5 (keine Server) | 4 (HF Spaces stabil) | 2 (Server-Wartung) | 4 (Platform-managed) | 3 (Platform, aber Sleep) |
| **Daten-Persistenz** (×1.5) | 4 (JSON baked) | 3 (DB im Image) | 5 (Volumes) | 4 (Fly Volume) | 1 (ephemeral) |
| **Skalierbarkeit** (×1) | 5 (CDN unendlich) | 3 (2 vCPU shared) | 4 (Eigene HW) | 3 (Free Tier) | 2 (Free Tier) |

### Gewichtete Summe

| Option | Summe | Platz |
|---|---|---|
| **A: Static + In-Browser JS** | `15+5+10+10+12.5+6+5` = **63.5** | 🥇 |
| **B: CF Pages + HF Spaces** | `15+10+10+8+10+4.5+3` = **60.5** | 🥈 |
| **D: Fly.io Full Stack** | `15+7.5+10+6+10+6+3` = **57.5** | 🥉 |
| **C: CF + Self-Hosted** | `15+7.5+4+8+5+7.5+4` = **51.0** | 4 |
| **E: Render** | `15+12.5+10+2+7.5+1.5+2` = **50.5** | 5 |

---

## Empfehlung

### Platz 1: **Static Site + In-Browser JS**
Wenn wir die Matching-Logik in JavaScript portieren können (Segmentierer ist ~100 Zeilen, phonetischer Matcher mit vorberechneten IPA-Vektoren ~200 Zeilen), ist das die eleganteste Lösung: **0€, 0 Server, 0 Wartung, global instant**.

**Risiko:** Qualität des JS-Panphon-Ersatzes. Statt panphon's 21-dimensionaler Feature-Vektoren könnte man IPA-Strings direkt via Levenshtein/Substring matchen — für "close enough" reicht das vermutlich. Sollte man vorher mit 10 Testwörtern validieren.

### Platz 2: **CF Pages + HuggingFace Spaces**
Wenn JS-Matching nicht gut genug ist, ist das der beste Kompromiss. Python-Backend ohne Self-Hosting, 0€. Die DB muss ins Docker-Image (kein Volume), aber das ist ein One-Time-Build.

---

## Technischer Stack (finaler Vorschlag)

```
┌─────────────────────────────────────┐
│           Cloudflare Pages          │  ← Statisches Frontend
│  index.html + laubau.js + data.json │     (immer, kostenlos)
└──────────────┬──────────────────────┘
               │
               │ (nur bei Option B)
               ▼
┌─────────────────────────────────────┐
│       HuggingFace Spaces            │  ← Fallback-Backend
│  FastAPI + epitran + panphon + DB   │     (wenn JS-Matching nicht reicht)
└─────────────────────────────────────┘
```

**MVP-Ansatz (empfohlen):**
1. Zuerst Option A bauen (Static + JS) — schnell, kein Backend
2. Mit 20 Testwörtern Matching-Qualität prüfen
3. Falls ungenügend → Option B (HF Spaces Backend) als Fallback

---

## Anhang: Größenabschätzung Precomputed Data

| Datensatz | Geschätzte Größe |
|---|---|
| DE-Wort → IPA Map (364K Einträge) | ~8 MB JSON |
| IPA-Substring-Index (FTS5-äquivalent) | ~12 MB JSON |
| CMUdict EN-Wort → IPA (134K Einträge) | ~3 MB JSON |
| Artikulations-Tabelle (10 Einträge) | <1 KB |
| **Total** | **~23 MB** |

Für Cloudflare Pages: Limit ist 25 MB pro File (nach Compression ~5-8 MB mit gzip). Passt.
