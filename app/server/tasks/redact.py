import io

from blind_charging_core import Pipeline, PipelineConfig
from pydantic import BaseModel

from .queue import queue
from .serializer import register_type


class RedactionTask(BaseModel):
    document_id: str
    file_bytes: bytes
    jurisdiction_id: str
    case_id: str
    callback_url: str | None = None
    target_blob_url: str | None = None


class RedactionTaskResult(BaseModel):
    document_id: str
    external_link: str | None = None
    content: bytes | None = None


register_type(RedactionTask)
register_type(RedactionTaskResult)


@queue.task(task_track_started=True, task_time_limit=300, task_soft_time_limit=240)
def redact(params: RedactionTask) -> RedactionTaskResult:
    """Redact a document."""
    # NOTE(jnu): for now this is just a playground implementation.
    pipeline_cfg = PipelineConfig.model_validate(
        {
            "pipe": [
                {
                    "engine": "in:memory",
                },
                {
                    "engine": "extract:tesseract",
                },
                {
                    "engine": "redact:noop",
                    "delimiters": ["[", "]"],
                },
                {
                    "engine": "render:pdf",
                },
                {
                    "engine": "out:memory",
                },
            ]
        }
    )
    pipeline = Pipeline(pipeline_cfg)
    input_buffer = io.BytesIO(params.file_bytes)
    output_buffer = io.BytesIO()
    pipeline.run(
        {
            "in": {"buffer": input_buffer},
            "out": {"buffer": output_buffer},
        }
    )

    content = output_buffer.getvalue()

    # TODO (jnu): upload the content to the target_blob_url if passed
    return RedactionTaskResult(
        document_id=params.document_id,
        content=content,
    )
