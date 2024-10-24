"""HTTP server to expose health check endpoint while worker is running."""

import logging
import socket
from typing import Literal, TypedDict

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ..bg import BackgroundServer
from .queue import queue

logger = logging.getLogger(__name__)

app = FastAPI()


class HealthCheckResponse(TypedDict):
    """Response from Celery worker.

    See:
    https://docs.celeryq.dev/en/v5.3.6/reference/celery.app.control.html#celery.app.control.Control.ping
    """

    status: Literal["ok"] | Literal["error"]
    error: str | None
    total_workers: int
    local_workers: int
    host: str
    healthy_workers: list[str]
    unhealthy_workers: list[str]


@app.get("/health")
def health() -> JSONResponse:
    """Health check endpoint."""
    health = queue.control.ping()
    local = socket.gethostname()
    address = f"@{local}"
    healthy: list[str] = []
    unhealthy: list[str] = []
    for workers in health:
        for worker, response in workers.items():
            if not worker.endswith(address):
                continue
            if response.get("ok") == "pong":
                healthy.append(worker)
            else:
                unhealthy.append(worker)

    data = {
        "total_workers": len(health),
        "local_workers": len(unhealthy) + len(healthy),
        "host": local,
        "healthy_workers": healthy,
        "unhealthy_workers": unhealthy,
        "status": "ok",
        "error": None,
    }
    status_code = 200

    if not healthy:
        logger.error("No healthy workers found.")
        status_code = 500
        data["error"] = "No healthy workers found"
        data["status"] = "error"

    return JSONResponse(
        status_code=status_code,
        content=data,
    )


class RawWorkerHealth(TypedDict):
    """Response from Celery worker.

    See:
    https://docs.celeryq.dev/en/v5.3.6/reference/celery.app.control.html#celery.app.control.Control.ping
    """

    ok: Literal["pong"]


class WorkerRawHealthCheckResponse(TypedDict):
    """Health check response from the worker daemon."""

    workers: list[dict[str, RawWorkerHealth]]


@app.get("/health/all")
def health_all_workers() -> dict:
    """Inspect all workers."""
    return {"workers": queue.control.ping()}


@app.get("/")
def root() -> None:
    """Root endpoint."""
    return None


def get_liveness_app(host: str = "127.0.0.1", port: int = 8001) -> BackgroundServer:
    """Get a background server instance for liveness checks."""
    cfg = uvicorn.Config(app, host=host, port=port)
    return BackgroundServer(cfg)
