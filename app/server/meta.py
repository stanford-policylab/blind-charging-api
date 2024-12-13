import json
import os
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

import psutil
import tomllib
import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..logo import api_logo, cpl_logo
from .tasks.queue import queue
from .time import utcnow

meta_router = APIRouter()


@dataclass
class SystemInfo:
    cpu_count: int
    cpu_freq: float
    cpu_percent: float
    cpu_temp: float
    mem_total: float
    mem_used: float
    mem_percent: float
    swap_total: float
    swap_used: float
    swap_percent: float
    disk_total: float
    disk_used: float
    disk_percent: float
    net_io: dict


@dataclass
class WorkersInfo:
    total_workers: int
    healthy_workers: list[str]
    unhealthy_workers: list[str]
    status: Literal["ok", "error"]


@dataclass
class PlatformInfo:
    py_version: str
    os: str
    os_version: str
    hostname: str
    processor: str


@dataclass
class ApiHealth:
    alive: bool
    startup_time: str
    current_time: str
    api_version: str
    schema_version: str


@dataclass
class ApiMeta:
    platform: PlatformInfo
    api: ApiHealth
    workers: WorkersInfo
    system: SystemInfo


def _get_system_info() -> SystemInfo:
    cpu_count = psutil.cpu_count(logical=False)
    cpu_freq = psutil.cpu_freq().current
    cpu_percent = psutil.cpu_percent()
    cpu_temp = -1
    if hasattr(psutil, "sensors_temperatures"):
        temps = psutil.sensors_temperatures()
        if "coretemp" in temps:
            core_temps = temps["coretemp"]
            if core_temps:
                cpu_temp = core_temps[0].current

    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")
    net_io = psutil.net_io_counters()

    return SystemInfo(
        cpu_count=cpu_count,
        cpu_freq=cpu_freq,
        cpu_percent=cpu_percent,
        cpu_temp=cpu_temp,
        mem_total=mem.total,
        mem_used=mem.used,
        mem_percent=mem.percent,
        swap_total=swap.total,
        swap_used=swap.used,
        swap_percent=swap.percent,
        disk_total=disk.total,
        disk_used=disk.used,
        disk_percent=disk.percent,
        net_io=net_io,
    )


def _get_root_dir() -> str:
    this_dir = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(this_dir, "..", ".."))


def _get_api_version() -> str:
    pyproject_toml = os.path.join(_get_root_dir(), "pyproject.toml")
    with open(pyproject_toml, "r") as f:
        data = f.read()
        project = tomllib.loads(data)
        return project["tool"]["poetry"]["version"]


def _get_schema_version() -> str:
    openai_yaml = os.path.join(_get_root_dir(), "app", "schema", "openapi.yaml")
    with open(openai_yaml, "r") as f:
        data = f.read()
        schema = yaml.safe_load(data)
        return schema["info"]["version"]


def _get_worker_health() -> WorkersInfo:
    workers = queue.control.ping()
    healthy = list[str]()
    unhealthy = list[str]()
    for worker in workers:
        for key in worker.keys():
            if worker[key].get("ok") == "pong":
                healthy.append(key)
            else:
                unhealthy.append(key)
    return WorkersInfo(
        total_workers=len(workers),
        healthy_workers=healthy,
        unhealthy_workers=unhealthy,
        status="ok" if healthy else "error",
    )


def _get_platform_info() -> PlatformInfo:
    return PlatformInfo(
        py_version=sys.version,
        os=platform.platform(),
        os_version=platform.version(),
        hostname=platform.node(),
        processor=platform.machine(),
    )


def _get_api_health(startup_time: datetime) -> ApiHealth:
    return ApiHealth(
        alive=True,
        startup_time=startup_time.isoformat(),
        current_time=utcnow().isoformat(),
        api_version=_get_api_version(),
        schema_version=_get_schema_version(),
    )


def inspect_api(startup: datetime) -> ApiMeta:
    return ApiMeta(
        platform=_get_platform_info(),
        api=_get_api_health(startup),
        workers=_get_worker_health(),
        system=_get_system_info(),
    )


def _format_meta_html(content: str) -> str:
    return f"""
    <html>
        <head>
            <title>Blind Charging API</title>
            <style type="text/css">
            body {{
                font-family: sans-serif;
                text-align: center;
                color: #333;
            }}
            header {{
                padding: 2rem 0;
            }}
            p {{ margin-top: 2rem; }}
            a {{
                color: #007BFF;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            .yay {{
                color: #28a745;
                font-weight: bold;
            }}
            .divider {{
                border: 0;
                height: 1px;
                margin: 2rem 0;
                background-image: linear-gradient(to right,
                    rgba(0, 0, 0, 0),
                    rgba(0, 0, 0, 0.75),
                    rgba(0, 0, 0, 0));
            }}
            .links {{
                width: 50%;
                margin: auto;
            }}
            .links li {{
                text-align: left;
                margin-top: 1rem;
            }}
            .next_steps {{
                color: #666;
                font-style: italic;
            }}
            footer {{
                position: fixed;
                bottom: 0;
                width: 100%;
                background-color: #f8f9fa;
                padding: 1rem 0;
                color: #666;
                font-size: 0.8rem;
                text-align: center;
            }}
            .cpl {{
                font-size: 2px;
                letter-spacing: 0.1em;
                color: #666;
            }}
            </style>
        </head>
        <body>
            <header>
            <pre>{api_logo}</pre>
            </header>
            <main>{content}</main>
            <footer>
                <p>Need help? Email us at
                <a href="mailto:blind_charging@hks.harvard.edu">
                blind_charging@hks.harvard.edu</a>.
                </p>
                <p>© 2024 Computational Policy Lab, Harvard Kennedy School</p>
                <div><pre class="cpl">{cpl_logo}</pre></div>
            </footer>
        </body>
    </html>
    """


@meta_router.get("/status")
async def status(request: Request, format: str | None = None):
    health = inspect_api(request.app.state.startup_time)
    overall_healthy = health.api.alive and health.workers.status == "ok"
    status_code = 200 if overall_healthy else 500
    health_dict = asdict(health)
    # inspect `accept` header to determine default response format
    accept = request.headers.get("accept", "")
    if format is None:
        if "text/html" in accept:
            format = "html"
        elif "application/json" in accept:
            format = "json"

    if format == "json":
        return JSONResponse(content=health_dict, status_code=status_code)
    elif format == "html":
        content = f"""
    <html>
    <body>
    <pre>{json.dumps(health_dict, indent=2)}</pre>
    </body>
    </html>
    """
        return HTMLResponse(content=content, status_code=status_code)
    else:
        raise HTTPException(
            status_code=400, detail=f"Invalid format `{format}`. Use `json` or `html`."
        )


@meta_router.get("/", response_class=HTMLResponse)
async def root():
    return _format_meta_html("""
            <p>This server hosts the
                <a href="https://policylab.hks.harvard.edu/"
                    rel="noopener noreferrer"
                    target="_blank">Computational Policy Lab's</a>
                <a href="https://blindcharging.org/"
                    rel="noopener noreferrer"
                    target="_blank">Race-Blind Charging API</a>.</p>
            <p>
            Since you are reading this,
            it means the API has basically started correctly.
                <span class="yay">Congratulations!</span></p>
            <hr class="divider" />
            <p class="next_steps">
            Here are some useful links to get you started ...
            </p>
            <ul class="links">
                <li>Our GitHub repository's
                <a href="https://github.com/stanford-policylab/blind-charging-api"
                    rel="noopener noreferrer"
                    target="_blank">readme file</a>
                includes different tests you can run to start working with the API.</li>
                <li>Our
                <a href="/api/v1/docs"
                    rel="noopener noreferrer"
                    target="_blank">API documentation</a>
                has more detailed information about all of the API endpoints.</li>
                <li>The
                <a href="/status"
                    rel="noopener noreferrer">status page</a>
                will give you more details about the current API status.</li>
            </ul>""")
