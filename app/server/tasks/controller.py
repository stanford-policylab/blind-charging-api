import logging

from celery import chain

from ..generated.models import OutputFormat, RedactionTarget
from .callback import CallbackTask
from .fetch import FetchTask
from .finalize import FinalizeTask
from .format import FormatTask
from .redact import RedactionTask

logger = logging.getLogger(__name__)


def create_document_redaction_task(
    jurisdiction_id: str,
    case_id: str,
    subject_ids: list[str],
    objects: list[RedactionTarget],
    renderer: OutputFormat = OutputFormat.PDF,
) -> chain | None:
    """Create database objects representing a document redaction task.

    Args:
        jurisdiction_id (str): The jurisdiction ID.
        case_id (str): The case ID.
        subject_ids (list[str]): The IDs of the subjects to redact.
        objects (list[RedactionTarget]): The documents to redact.
        renderer (OutputFormat, optional): The output format for the redacted document.

    Returns:
        chain: The Celery chain representing the redaction pipeline.
    """
    if not objects:
        return None

    active_object = objects[0]

    return chain(
        FetchTask(
            document=active_object.document,
        ).s(),
        RedactionTask(
            document_id=active_object.document.root.documentId,
            jurisdiction_id=jurisdiction_id,
            case_id=case_id,
            renderer=renderer,
        ).s(),
        FormatTask(
            target_blob_url=active_object.target_blob_url,
        ).s(),
        CallbackTask(
            callback_url=active_object.callback_url,
        ).s(),
        FinalizeTask(
            jurisdiction_id=jurisdiction_id,
            case_id=case_id,
            next_objects=objects[1:],
            subject_ids=subject_ids,
            renderer=renderer,
        ).s(),
    )
