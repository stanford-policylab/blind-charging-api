from pathlib import Path
from typing import Literal, TypedDict

import tomllib
from opentelemetry.metrics import get_meter


class WorkersData(TypedDict):
    total: int
    local: int
    healthy: list[str]
    unhealthy: list[str]


class TasksData(TypedDict):
    active: int
    scheduled: int
    reserved: int


class ProcessesData(TypedDict):
    total: int
    idle: int
    expected: int


class HealthCheckData(TypedDict):
    """Aggregated status of Celery workers.

    See:
    https://docs.celeryq.dev/en/v5.3.6/reference/celery.app.control.html#celery.app.control.Control.inspect
    """

    status: Literal["ok"] | Literal["error"]
    error: str | None
    host: str
    workers: WorkersData
    tasks: TasksData
    memory_usage: int
    processes: ProcessesData


def _get_version() -> str:
    """Get the currenet app version from pyprpoject.toml."""
    pyproject = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
    toml = tomllib.loads(pyproject.read_text())
    return toml["tool"]["poetry"]["version"]


class CeleryCustomHealthMetrics:
    def __init__(self):
        self.meter = get_meter(__name__, _get_version())

        self.active_tasks = self.meter.create_gauge(
            "celery.queue.tasks.active",
            "Number of active tasks in the queue",
            "tasks",
        )
        self.scheduled_tasks = self.meter.create_gauge(
            "celery.queue.tasks.scheduled",
            "Number of scheduled tasks in the queue",
            "tasks",
        )
        self.reserved_tasks = self.meter.create_gauge(
            "celery.queue.tasks.reserved",
            "Number of reserved tasks in the queue",
            "tasks",
        )
        self.num_workers = self.meter.create_gauge(
            "celery.workers.count",
            "Number of workers in the pool",
            "workers",
        )
        self.num_unhealthy_workers = self.meter.create_gauge(
            "celery.workers.count.unhealthy",
            "Number of unhealthy workers in the pool",
            "workers",
        )
        self.num_processes = self.meter.create_gauge(
            "celery.workers.processes",
            "Number of worker processes in the pool",
            "processes",
        )
        self.idle_processes = self.meter.create_gauge(
            "celery.workers.processes.idle",
            "Number of idle worker processes in the pool",
            "processes",
        )
        self.expected_processes = self.meter.create_gauge(
            "celery.workers.processes.expected",
            "Number of expected worker processes in the pool",
            "processes",
        )
        self.memory_usage = self.meter.create_gauge(
            "celery.workers.memory",
            "Memory usage of the worker processes",
            "bytes",
        )

    def report(self, data: HealthCheckData):
        self.active_tasks.set(data["tasks"]["active"])
        self.scheduled_tasks.set(data["tasks"]["scheduled"])
        self.reserved_tasks.set(data["tasks"]["reserved"])
        self.num_workers.set(data["workers"]["total"])
        self.num_unhealthy_workers.set(len(data["workers"]["unhealthy"]))
        self.num_processes.set(data["processes"]["total"])
        self.idle_processes.set(data["processes"]["idle"])
        self.expected_processes.set(data["processes"]["expected"])
        self.memory_usage.set(data["memory_usage"])


class CeleryCustomCounter:
    def init(self):
        self.meter = get_meter(__name__, _get_version())
        self.task_counter = self.meter.create_counter(
            "celery.queue.tasks.total",
            "Total number of tasks processed",
            "tasks",
        )
        self.failed_task_counter = self.meter.create_counter(
            "celery.queue.tasks.failed",
            "Total number of failed tasks",
            "tasks",
        )
        self.success_task_counter = self.meter.create_counter(
            "celery.queue.tasks.success",
            "Total number of successful tasks",
            "tasks",
        )
        self.success_callback_counter = self.meter.create_counter(
            "celery.queue.callbacks.success",
            "Total number of successful callbacks",
            "callbacks",
        )
        self.failed_callback_counter = self.meter.create_counter(
            "celery.queue.callbacks.failed",
            "Total number of failed callbacks",
            "callbacks",
        )

    def record_task(self, success: bool):
        self.task_counter.add(1)
        if success:
            self.success_task_counter.add(1)
        else:
            self.failed_task_counter.add(1)

    def record_callback(self, success: bool):
        if success:
            self.success_callback_counter.add(1)
        else:
            self.failed_callback_counter.add(1)


celery_counters = CeleryCustomCounter()
