import io

from blind_charging_core import Pipeline, PipelineConfig
from celery import Task
from celery.utils.log import get_task_logger
from pydantic import BaseModel

from ..config import config
from .fetch import FetchTaskResult
from .queue import ProcessingError, queue
from .serializer import register_type

logger = get_task_logger(__name__)


class RedactionTask(BaseModel):
    document_id: str
    jurisdiction_id: str
    case_id: str


class RedactionTaskResult(BaseModel):
    jurisdiction_id: str
    case_id: str
    document_id: str
    errors: list[ProcessingError] = []
    content: bytes | None = None


register_type(RedactionTask)
register_type(RedactionTaskResult)


@queue.task(
    bind=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    max_retries=3,
    retry_backoff=True,
)
def redact(
    self: Task, fetch_result: FetchTaskResult, params: RedactionTask
) -> RedactionTaskResult:
    """Redact a document."""
    if fetch_result.errors:
        # If there are errors from the fetch task, pass through.
        # There's nothing to redact, but we still want to get through the
        # chain to the error callback.
        return RedactionTaskResult(
            jurisdiction_id=params.jurisdiction_id,
            case_id=params.case_id,
            document_id=params.document_id,
            errors=fetch_result.errors,
        )

    try:
        pipeline_cfg = PipelineConfig.model_validate(
            {
                "pipe": [
                    {
                        "engine": "in:memory",
                    },
                    {
                        "engine": "out:memory",
                    },
                ]
            }
        )
        # Splice in the pipeline from the config. We only fix the I/O engines.
        pipeline_cfg.pipe[1:1] = config.processor.pipe
        pipeline = Pipeline(pipeline_cfg)
        input_buffer = io.BytesIO(fetch_result.file_bytes)
        output_buffer = io.BytesIO()

        # Run the pipeline with memory I/O.
        pipeline.run(
            {
                "in": {"buffer": input_buffer},
                "out": {"buffer": output_buffer},
            }
        )

        content = output_buffer.getvalue()

        return RedactionTaskResult(
            jurisdiction_id=params.jurisdiction_id,
            case_id=params.case_id,
            document_id=params.document_id,
            content=content,
        )
    except Exception as e:
        if self.request.retries >= self.max_retries:
            logger.error(
                f"Redaction failed for {params.document_id} "
                f"after {self.max_retries} retries. Error: {e}"
            )
            new_error = ProcessingError.from_exception("redact", e)
            return RedactionTaskResult(
                jurisdiction_id=params.jurisdiction_id,
                case_id=params.case_id,
                document_id=params.document_id,
                error=[*fetch_result.errors, new_error],
            )
        else:
            logger.warning(
                f"Redaction failed for {params.document_id}. This task will be retried."
            )
            logger.error("The exception that caused the failure was:")
            logger.exception(e)
            raise self.retry() from e
