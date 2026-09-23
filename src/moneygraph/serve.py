"""Локальный эндпоинт для ассистента в интерфейсе.

Только стандартная библиотека — новых зависимостей у проекта не появляется.
Слушает исключительно 127.0.0.1: инструмент работает с данными расследования,
наружу он не смотрит.

Страница `viewer.html` остаётся самодостаточной и открывается двойным кликом
без этого сервера — чат просто не появится.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .agent import Assistant
from .agent import llm

MAX_BODY = 8192          # вопрос аналитика не бывает длиннее
DEFAULT_PORT = 8765


class _Handler(BaseHTTPRequestHandler):
    assistant: Assistant
    viewer_path: Path

    server_version = "moneygraph"

    def _headers(self, status: int, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        # Страница может быть открыта как file://, тогда её origin — null.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()

    def _json(self, status: int, payload: dict) -> None:
        self._headers(status, "application/json; charset=utf-8")
        self.wfile.write(json.dumps(payload, ensure_ascii=False, default=str).encode())

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/viewer.html"):
            if not self.viewer_path.exists():
                self._json(404, {"error": "viewer.html не найден — запустите ./run.sh"})
                return
            self._headers(200, "text/html; charset=utf-8")
            self.wfile.write(self.viewer_path.read_bytes())
        elif self.path == "/health":
            self._json(200, {
                "status": "ok",
                "nodes": self.assistant.ctx.g.number_of_nodes(),
                "llm": llm.available(),
                "model": llm.MODEL if llm.available() else None,
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/ask":
            self._json(404, {"error": "not found"})
            return
        length = min(int(self.headers.get("Content-Length") or 0), MAX_BODY)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "тело запроса не является JSON"})
            return

        question = str(body.get("question") or "").strip()
        if not question:
            self._json(400, {"error": "пустой вопрос"})
            return

        answer = self.assistant.ask(question)
        self._json(200, {
            "answer": answer.text,
            "tools_used": list(dict.fromkeys(answer.tools_used)),
            "warnings": answer.warnings,
            "llm_used": answer.llm_used,
        })

    def log_message(self, fmt: str, *args) -> None:
        # Стандартный лог шумит на каждый запрос страницы; оставляем только вопросы.
        if self.command == "POST":
            print(f"  вопрос: {self.path}")


def serve(data_dir: Path, out_dir: Path, port: int = DEFAULT_PORT) -> None:
    _Handler.assistant = Assistant(data_dir, out_dir)
    _Handler.viewer_path = out_dir / "viewer.html"

    mode = "LLM" if llm.available() else "детерминированный"
    print(f"Ассистент: {_Handler.assistant.ctx.g.number_of_nodes()} узлов, режим {mode}.")
    print(f"Откройте http://127.0.0.1:{port}  (или {out_dir}/viewer.html — чат подключится сам)")
    print("Ctrl+C для остановки.")

    with ThreadingHTTPServer(("127.0.0.1", port), _Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nОстановлено.")


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="moneygraph-serve",
        description="Локальный сервер: схема сети и AI-ассистент в одном окне")
    ap.add_argument("--data", default=Path("data"), type=Path)
    ap.add_argument("--out", default=Path("out"), type=Path)
    ap.add_argument("--port", default=DEFAULT_PORT, type=int)
    a = ap.parse_args()
    serve(a.data, a.out, a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
