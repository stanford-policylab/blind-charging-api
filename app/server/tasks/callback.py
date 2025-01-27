import asyncio
import json
import logging

import requests
from celery.canvas import Signature
from pydantic import BaseModel

from app.func import allf

from ..case import CaseStore
from ..case_helper import save_retry_state_sync
from ..config import config
from ..generated.models import (
    MaskedSubject,
    OutputDocument,
    RedactionResult,
    RedactionResultError,
    RedactionResultSuccess,
)
from .format import FormatTaskResult
from .metrics import (
    celery_counters,
    record_task_failure,
    record_task_retry,
    record_task_start,
    record_task_success,
)
from .queue import ProcessingError, queue
from .serializer import register_type

logger = logging.getLogger(__name__)


class CallbackTask(BaseModel):
    callback_url: str | None = None

    def s(self) -> Signature:
        return callback.s(self)


class CallbackTaskResult(BaseModel):
    status_code: int
    response: str | None = None
    formatted: FormatTaskResult


register_type(CallbackTask)
register_type(CallbackTaskResult)


_callback_timeout = config.queue.task.callback_timeout_seconds


@queue.task(
    task_track_started=True,
    task_time_limit=_callback_timeout + 10,
    task_soft_time_limit=_callback_timeout,
    max_retries=5,
    retry_backoff=True,
    autoretry_for=(Exception,),
    default_retry_delay=30,
    on_retry=allf(save_retry_state_sync, record_task_retry),
    on_failure=record_task_failure,
    on_success=record_task_success,
    before_start=record_task_start,
)
def callback(
    format_result: FormatTaskResult, params: CallbackTask
) -> CallbackTaskResult:
    """Post callbacks to the client as requested."""
    if params.callback_url:
        try:
            masked_subjects = get_masks_sync(
                format_result.jurisdiction_id, format_result.case_id
            )
        except Exception:
            logger.exception("Error getting masked subjects")
            masked_subjects = []

        if format_result.errors:
            body = RedactionResult(
                RedactionResultError(
                    jurisdictionId=format_result.jurisdiction_id,
                    caseId=format_result.case_id,
                    inputDocumentId=format_result.document_id,
                    maskedSubjects=masked_subjects,
                    error=format_errors(format_result.errors),
                    status="ERROR",
                )
            )
        else:
            doc = get_result_sync(
                format_result.jurisdiction_id,
                format_result.case_id,
                format_result.document_id,
            )
            if not doc:
                body = RedactionResult(
                    RedactionResultError(
                        jurisdictionId=format_result.jurisdiction_id,
                        caseId=format_result.case_id,
                        inputDocumentId=format_result.document_id,
                        maskedSubjects=masked_subjects,
                        error="Redaction result not found",
                        status="ERROR",
                    )
                )
            else:
                body = RedactionResult(
                    RedactionResultSuccess(
                        jurisdictionId=format_result.jurisdiction_id,
                        caseId=format_result.case_id,
                        inputDocumentId=format_result.document_id,
                        maskedSubjects=masked_subjects,
                        redactedDocument=doc,
                        status="COMPLETE",
                    )
                )
        response = requests.post(
            params.callback_url,
            json=body.model_dump(mode="json"),
        )
        try:
            response.raise_for_status()
            celery_counters.record_callback(True)
        except Exception:
            celery_counters.record_callback(False)
            raise

        return CallbackTaskResult(
            status_code=response.status_code,
            response=response.text,
            formatted=format_result,
        )

    return CallbackTaskResult(
        status_code=0,
        response="[nothing to do]",
        formatted=format_result,
    )


def format_errors(errors: list[ProcessingError]) -> str:
    if not errors:
        return json.dumps(
            [
                {
                    "message": "Unknown error",
                    "task": "unknown",
                    "exception": "UnknownException",
                }
            ]
        )
    return json.dumps([err.model_dump() for err in errors])


def get_masks_sync(jurisdiction_id: str, case_id: str) -> list[MaskedSubject]:
    """Get the masked subjects for a case.

    Args:
        jurisdiction_id (str): The jurisdiction ID.
        case_id (str): The case ID.

    Returns:
        list[MaskedSubject]: The masked subjects.
    """

    async def _get_masks_with_store() -> list[MaskedSubject]:
        async with config.queue.store.driver() as store:
            async with store.tx() as tx:
                cs = CaseStore(tx)
                await cs.init(jurisdiction_id, case_id)
                return await cs.get_masked_names()

    return asyncio.run(_get_masks_with_store())


def get_result_sync(
    jurisdiction_id: str, case_id: str, doc_id: str
) -> OutputDocument | None:
    """Get the redacted document for a case.

    Args:
        jurisdiction_id (str): The jurisdiction ID.
        case_id (str): The case ID.
        doc_id (str): The document ID.

    Returns:
        OutputDocument | None: The redacted document.
    """

    async def _get_result_with_store() -> OutputDocument | None:
        async with config.queue.store.driver() as store:
            async with store.tx() as tx:
                cs = CaseStore(tx)
                await cs.init(jurisdiction_id, case_id)
                return await cs.get_result_doc(doc_id)

    return asyncio.run(_get_result_with_store())
