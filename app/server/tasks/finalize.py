import asyncio
import json

from celery.result import AsyncResult
from pydantic import BaseModel

from ..case import CaseStore
from ..config import config
from ..db import DocumentStatus
from ..generated.models import Document, OutputFormat, RedactionTarget
from .callback import CallbackTaskResult
from .queue import ProcessingError, queue
from .serializer import register_type


class FinalizeTask(BaseModel):
    jurisdiction_id: str
    case_id: str
    next_objects: list[RedactionTarget] = []
    subject_ids: list[str] = []
    renderer: OutputFormat

    def s(self):
        return finalize.s(self)


class FinalizeTaskResult(BaseModel):
    jurisdiction_id: str
    case_id: str
    document_id: str
    document: Document | None
    errors: list[ProcessingError] = []
    next_task_id: str | None = None


register_type(FinalizeTaskResult)


@queue.task(
    task_track_started=True,
    task_time_limit=30,
    task_soft_time_limit=25,
    max_retries=3,
    retry_backoff=True,
    autoretry_for=(Exception,),
)
def finalize(
    callback_result: CallbackTaskResult, params: FinalizeTask
) -> FinalizeTaskResult:
    """Finalize the redaction process."""
    format_result = callback_result.formatted
    if config.experiments.enabled:
        with config.experiments.store.driver.sync_session() as session:
            status = DocumentStatus(
                jurisdiction_id=format_result.jurisdiction_id,
                case_id=format_result.case_id,
                document_id=format_result.document_id,
                status="ERROR" if format_result.errors else "COMPLETE",
                error=format_errors(format_result.errors),
            )
            session.add(status)
            session.commit()

    # Queue up the next document for processing now, if there is one.
    next_task: AsyncResult | None = None
    if params.next_objects:
        from .controller import create_document_redaction_task

        new_active_task = params.next_objects[0]
        new_chain = create_document_redaction_task(
            params.jurisdiction_id,
            params.case_id,
            params.subject_ids,
            params.next_objects,
            renderer=params.renderer,
        )
        if not new_chain:
            # Unclear why we would get here, since we've verified that
            # there are more objects to redact
            raise RuntimeError("Failed to create redaction task")
        next_task = new_chain.apply_async()
        # Save the new task to the store for tracking
        save_doc_task_id_sync(
            params.jurisdiction_id,
            params.case_id,
            new_active_task.document.root.documentId,
            str(next_task),
        )

    return FinalizeTaskResult(
        document=format_result.document,
        jurisdiction_id=format_result.jurisdiction_id,
        case_id=format_result.case_id,
        document_id=format_result.document_id,
        errors=format_result.errors,
        next_task_id=str(next_task) if next_task else None,
    )


def format_errors(errors: list[ProcessingError]) -> str | None:
    if not errors:
        return None
    return json.dumps([err.model_dump() for err in errors])


def save_doc_task_id_sync(
    jurisdiction_id: str, case_id: str, doc_id: str, task_id: str
) -> None:
    """Save the task ID for a document to the store

    Args:
        jurisdiction_id (str): The jurisdiction ID.
        case_id (str): The case ID.
        doc_id (str): The document ID.
        task_id (str): The task ID.
    """

    async def _save_id() -> None:
        async with config.queue.store.driver() as store:
            async with store.tx() as tx:
                cs = CaseStore(tx)
                await cs.init(jurisdiction_id, case_id)
                return await cs.save_doc_task(doc_id, task_id)

    return asyncio.run(_save_id())
