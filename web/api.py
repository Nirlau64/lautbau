"""LautBau Web API — FastAPI-Backend für die Web-UI."""

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from engine.pipeline import LautBau

app = FastAPI(title="LautBau API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
)

# Pipeline initialisieren
DB_PATH = Path(__file__).parent.parent / "data" / "de_words.db"
lb = LautBau(db_path=DB_PATH)


@app.get("/api/pronounce")
def pronounce(word: str = Query(..., description="Englisches Wort")):
    """Gibt die Aussprachehilfe für ein englisches Wort zurück."""
    try:
        result = lb.pronounce(word)
        # Strip ANSI codes for web output
        import re
        clean = re.sub(r"\033\[\d+m", "", result)
        return {"word": word, "result": clean}
    except Exception as e:
        return {"word": word, "error": str(e)}


@app.get("/health")
def health():
    return {"status": "ok"}


# Static files (frontend)
WEB_DIR = Path(__file__).parent
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")
