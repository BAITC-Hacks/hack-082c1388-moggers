"""Local web application: dataset API, assistant and built React interface."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from threading import Lock

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import Assistant, llm
from .viewer import ROLE_RU_FULL, ROLE_STYLE

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
app = FastAPI(title="MoneyGraph", docs_url=None, redoc_url=None)
_chat_lock = Lock()


def _records(frame: pd.DataFrame, ids: tuple[str, ...] = ()) -> list[dict]:
    frame = frame.copy()
    for column in ids:
        frame[column] = frame[column].astype(str)
    # pandas serializes NaN/Infinity as null; identifiers stay exact strings.
    return json.loads(frame.to_json(orient="records", double_precision=10))


@lru_cache(maxsize=1)
def dataset() -> dict:
    nodes = pd.read_parquet(OUT / "features.parquet")
    edges = pd.read_parquet(ROOT / "data" / "edges.parquet")
    clusters = pd.read_csv(OUT / "clusters.csv", dtype={"top_gids": str})
    cluster_rows = _records(clusters)
    for row in cluster_rows:
        row["top_gids"] = (row["top_gids"] or "").split()
    return {
        "schema_version": 1,
        "summary": json.loads((OUT / "summary.json").read_text(encoding="utf-8"))["facts"],
        "nodes": _records(nodes, ("gid",)),
        "edges": _records(edges, ("src", "dst")),
        "clusters": cluster_rows,
        "top_nodes": _records(pd.read_csv(OUT / "top_nodes.csv", dtype={"gid": str}), ("gid",)),
        "resilience": _records(pd.read_csv(OUT / "resilience.csv")),
        "role_labels": ROLE_RU_FULL,
        "role_styles": ROLE_STYLE,
    }


@lru_cache(maxsize=1)
def assistant() -> Assistant:
    return Assistant(ROOT / "data", OUT)


@app.get("/api/v1/dataset")
def get_dataset():
    try:
        return dataset()
    except FileNotFoundError:
        raise HTTPException(503, "Данные отсутствуют. Выполните python -m moneygraph.pipeline") from None


@app.get("/health")
def health():
    return {"status": "ok", "nodes": len(get_dataset()["nodes"]),
            "llm": llm.available(), "model": llm.MODEL if llm.available() else None}


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


@app.post("/ask")
def ask(body: Question):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Пустой вопрос")
    # This application is a single-user local workspace. Serialize its conversation.
    with _chat_lock:
        answer = assistant().ask(question)
    return {"answer": answer.text, "tools_used": answer.tools_used,
            "warnings": answer.warnings, "llm_used": answer.llm_used}


@app.get("/assistant")
def assistant_page():
    return FileResponse(OUT / "viewer.html", media_type="text/html")


app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True, check_dir=False), name="frontend")
