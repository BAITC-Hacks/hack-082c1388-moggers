"""Read-only local API and static frontend host. No analysis runs on requests."""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, StrictStr


class Record(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)


class Node(Record):
    gid: StrictStr
    role: str
    evidence: str
    priority_score: float
    cluster_id: int
    role_score: float
    depth: int
    is_seed: bool
    in_deg: int
    out_deg: int
    in_kzt: float
    out_kzt: float
    in_tx: int
    out_tx: int
    pass_through: float | None
    seed_sources: int
    betweenness: float
    reciprocal_partners: int
    min_cycle_len: int
    is_articulation: bool
    depth_truncated: bool
    flow_kzt: float


class Edge(Record):
    src: StrictStr
    dst: StrictStr
    sum_kzt: float
    n_tx: int


class Summary(Record):
    n_nodes: int
    n_edges: int
    n_tx: int
    n_seed: int
    turnover_kzt: float
    period: tuple[str, str]


class Cluster(Record):
    cluster_id: int
    n_nodes: int
    n_seed: int
    sum_kzt_internal: float
    top_gids: list[StrictStr]
    hypothesis: str


class TopNode(Record):
    rank: int
    gid: StrictStr
    role: str
    priority_score: float
    why: str


class Resilience(Record):
    removed_top_n: int
    components: int
    largest_component: int
    reachable_from_seeds: int
    reachable_share: float
    flow_removed_kzt: float
    flow_removed_share: float


class RoleStyle(Record):
    color: str
    shape: str
    size: int


class Snapshot(Record):
    schema_version: int
    summary: Summary
    nodes: list[Node]
    edges: list[Edge]
    clusters: list[Cluster]
    top_nodes: list[TopNode]
    resilience: list[Resilience]
    role_labels: dict[str, str]
    role_styles: dict[str, RoleStyle]


def reject_constant(value: str):
    raise ValueError(f"Invalid JSON constant: {value}")


def create_app(data_path: Path | None = None, frontend_dir: Path | None = None) -> FastAPI:
    root = Path(__file__).resolve().parents[2]
    data_path = data_path or Path(os.environ.get("MONEYGRAPH_SNAPSHOT", root / "out/dashboard.json"))
    frontend_dir = frontend_dir or root / "frontend/dist"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.snapshot = None
        try:
            payload = json.loads(data_path.read_text(encoding="utf-8"),
                                 parse_constant=reject_constant)
            snapshot = Snapshot.model_validate(payload)
            ids = {node.gid for node in snapshot.nodes}
            if snapshot.schema_version != 1 or len(ids) != len(snapshot.nodes):
                raise ValueError("Unsupported or inconsistent snapshot")
            if any(edge.src not in ids or edge.dst not in ids for edge in snapshot.edges):
                raise ValueError("Dangling edge")
            cluster_ids = {cluster.cluster_id for cluster in snapshot.clusters}
            if any(node.cluster_id not in cluster_ids or node.role not in snapshot.role_labels
                   or node.role not in snapshot.role_styles for node in snapshot.nodes):
                raise ValueError("Missing cluster or role")
            referenced = [node.gid for node in snapshot.top_nodes]
            referenced.extend(gid for cluster in snapshot.clusters for gid in cluster.top_gids)
            if not set(referenced) <= ids:
                raise ValueError("Unknown node reference")
            if snapshot.summary.n_nodes != len(ids) or snapshot.summary.n_edges != len(snapshot.edges):
                raise ValueError("Inconsistent summary")
            app.state.snapshot = snapshot.model_dump()
        except (OSError, ValueError, TypeError):
            pass
        yield

    app = FastAPI(title="MoneyGraph API", lifespan=lifespan)

    @app.get("/api/v1/dataset", response_model=Snapshot)
    def dataset():
        if app.state.snapshot is None:
            raise HTTPException(503, "Данные отсутствуют или повреждены. Выполните ./run.sh и перезапустите сервер.")
        return app.state.snapshot

    @app.get("/", include_in_schema=False)
    def index():
        index_path = frontend_dir / "index.html"
        if not index_path.is_file():
            raise HTTPException(503, "Frontend не собран. Выполните make web.")
        return FileResponse(index_path)

    if (frontend_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")
    return app


app = create_app()
