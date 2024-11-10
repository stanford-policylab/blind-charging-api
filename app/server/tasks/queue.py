import traceback
from typing import Annotated

from celery import Celery
from celery.result import AsyncResult
from celery.signals import worker_process_init
from pydantic import BaseModel, Field

from ..config import config

queue = Celery(
    "app.server.tasks",
    broker=config.queue.broker.url,
    backend=config.queue.store.url,
)


@worker_process_init.connect(weak=False)
def setup_tracing(*args, **kwargs):
    """Setup tracing for the worker process."""
    import logging

    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    logger = logging.getLogger(__name__)
    if config.metrics.driver:
        CeleryInstrumentor().instrument()
        logger.info("Celery tracing initialized.")


def get_result(task_id: str) -> AsyncResult:
    """Get the async result for a task."""
    return AsyncResult(task_id, app=queue)


class ProcessingError(BaseModel):
    """An error that occurred during processing."""

    message: str
    task: str
    exception: str
    traceback: Annotated[str, Field(exclude=True)] = ""

    @classmethod
    def from_exception(cls, task: str, exception: Exception) -> "ProcessingError":
        """Create a processing error from an exception."""
        tb = "".join(
            traceback.format_exception(
                type(exception), value=exception, tb=exception.__traceback__
            )
        )
        return cls(
            message=str(exception),
            task=task,
            exception=exception.__class__.__name__,
            traceback=tb,
        )
