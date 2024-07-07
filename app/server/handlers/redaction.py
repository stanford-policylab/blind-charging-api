import asyncio
import base64
import logging
from urllib.parse import urlparse

import aiohttp
from fastapi import HTTPException, Request
from nameparser import HumanName
from sqlalchemy import select

from ..config import config
from ..db import Alias, Subject, SubjectDocument, Task, nowts
from ..generated.models import (
    Document,
    DocumentContent,
    DocumentLink,
    MaskedSubject,
    RedactionRequest,
    RedactionResult,
    RedactionResultError,
    RedactionResultPending,
    RedactionResultSuccess,
    RedactionStatus,
    RedactionTarget,
)
from ..generated.models import (
    Subject as SubjectModel,
)
from ..tasks import RedactionTask, RedactionTaskResult, get_result, redact

logger = logging.getLogger(__name__)


# Only allow HTTP callbacks in debug mode
_callback_schemes = {"http", "https"} if config.debug else {"https"}
_disallowed_callback_hosts = {"localhost", "127.0.0.1"} if not config.debug else set()


def validate_callback_url(url: str | None) -> None:
    """Validate a callback URL.

    Args:
        url (str): The URL to validate.

    Raises:
        HTTPException: If the URL is invalid.
    """
    if not url:
        return
    parsed = urlparse(url)
    if not parsed.scheme:
        raise HTTPException(status_code=400, detail="Invalid callback URL")
    if parsed.scheme not in _callback_schemes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid callback URL scheme (must use {_callback_schemes})",
        )
    # Prevent use of localhost (etc) in production
    if parsed.hostname in _disallowed_callback_hosts:
        raise HTTPException(status_code=400, detail="Invalid callback URL host")


async def redact_documents(*, request: Request, body: RedactionRequest) -> None:
    """Handle requests to redact a document.

    Args:
        request (Request): The incoming request.
        body (RedactionRequest): The request body.

    Raises:
        HTTPException: If the document content cannot be fetched.
    """
    logger.debug(f"Received redaction request for {body.jurisdictionId}-{body.caseId}")

    subject_ids = set[str]()
    # Process the individuals submitted with the request
    for subj in body.subjects:
        subject = process_subject(subj)
        for doc in body.objects:
            subject.documents.append(
                SubjectDocument(
                    subject_id=subject.subject_id,
                    document_id=doc.document.root.documentId,
                    role=subj.role,
                )
            )
        request.state.db.add(subject)
        subject_ids.add(subject.subject_id)

    logger.debug(f"Processed {len(subject_ids)} subjects.")

    # Create a task for each document. Do this concurrently since the files will
    # often be on remote servers that we can fetch simultaneously.
    subj_ids_list = list(subject_ids)
    task_params_list = await asyncio.gather(
        *[
            create_document_redaction_task(
                body.jurisdictionId, body.caseId, subj_ids_list, obj
            )
            for obj in body.objects
        ]
    )

    # Create a task for each document
    for task_params in task_params_list:
        task_id = redact.delay(task_params)
        logger.debug(f"Created redaction task {task_id}.")
        # Save the task to the database
        request.state.db.add(
            Task(
                task_id=str(task_id),
                case_id=task_params.case_id,
                jurisdiction_id=task_params.jurisdiction_id,
                document_id=task_params.document_id,
            )
        )


def process_subject(subject: SubjectModel) -> Subject:
    """Process a subject for the database

    Args:
        subjects (list[SubjectModel]): The subjects to process.

    Returns:
        Subject: The processed subject.
    """
    aliases: list[Alias] = []
    all_aliases = [subject.subject.name] + (subject.subject.aliases or [])
    for i, alias in enumerate(all_aliases):
        if isinstance(alias, str):
            parsed_name = HumanName(alias)
            aliases.append(
                Alias(
                    primary=nowts() if i == 0 else None,
                    first_name=parsed_name.first,
                    middle_name=parsed_name.middle,
                    last_name=parsed_name.last,
                    suffix=parsed_name.suffix,
                    title=parsed_name.title,
                    nickname=parsed_name.nickname,
                )
            )
        else:
            aliases.append(
                Alias(
                    primary=nowts() if i == 0 else None,
                    first_name=alias.firstName,
                    middle_name=alias.middleName,
                    last_name=alias.lastName,
                    suffix=alias.suffix,
                    title=alias.title,
                    nickname=alias.nickname,
                )
            )

    logger.debug(f"Processed {len(aliases)} aliases for {subject.subject.subjectId}.")

    return Subject(
        subject_id=subject.subject.subjectId,
        aliases=aliases,
    )


async def create_document_redaction_task(
    jurisdiction_id: str, case_id: str, subject_ids: list[str], object: RedactionTarget
) -> RedactionTask:
    """Create database objects representing a document redaction task.

    Args:
        jurisdiction_id (str): The jurisdiction ID.
        case_id (str): The case ID.
        subject_ids (list[str]): The IDs of the subjects to redact.
        object (RedactionTarget): The document to redact.

    Returns:
        RedactionTask: The task parameters.
    """
    callback_url = str(object.callbackUrl) if object.callbackUrl else None
    target_blob_url = str(object.targetBlobUrl) if object.targetBlobUrl else None
    validate_callback_url(callback_url)
    validate_callback_url(target_blob_url)

    try:
        # TODO: Fetch the document content in a background task?
        content = await fetch_document_content(object.document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    task_params = RedactionTask(
        document_id=object.document.root.documentId,
        file_bytes=content,
        jurisdiction_id=jurisdiction_id,
        case_id=case_id,
        callback_url=callback_url,
        target_blob_url=target_blob_url,
        subject_ids=subject_ids,
    )

    return task_params


async def fetch_document_content(doc: Document) -> bytes:
    """Fetch the content of a document.

    Args:
        doc (Document): The document to fetch.

    Returns:
        bytes: The content of the document.
    """
    content = b""
    match doc.root.attachmentType:
        case "LINK":
            timeout = aiohttp.ClientTimeout(
                total=config.task.link_download_timeout_seconds
            )
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(str(doc.root.url)) as response:
                    content = await response.read()
        case "TEXT":
            content = doc.root.content.encode("utf-8")
        case "BASE64":
            content = base64.b64decode(doc.root.content)
        case _:
            raise ValueError(f"Unsupported attachment type: {doc.root.attachmentType}")
    return content


async def get_redaction_status(
    *,
    request: Request,
    jurisdiction_id: str,
    case_id: str,
    subject_id: str | None = None,
) -> RedactionStatus:
    """Get the redaction status for a case.

    Args:
        request (Request): The incoming request.
        jurisdiction_id (str): The jurisdiction ID.
        case_id (str): The case ID.
        subject_id (str, optional): The ID of a person to get redaction status for.

    Returns:
        RedactionStatus: The redaction status summary.
    """
    redaction_results = list[RedactionResult]()

    # Get the redaction status from the database
    tasks_q = select(Task).filter(
        Task.jurisdiction_id == jurisdiction_id, Task.case_id == case_id
    )
    tasks_result = await request.state.db.execute(tasks_q)
    tasks = tasks_result.scalars().all()
    document_ids = [task.document_id for task in tasks]
    masks_q = select(SubjectDocument).filter(
        SubjectDocument.document_id.in_(document_ids)
    )

    masks_result = await request.state.db.execute(masks_q)
    subjects_map: dict[str, list[SubjectDocument]] = {}
    for mask in masks_result.scalars().unique():
        subjects_map.setdefault(mask.document_id, []).append(mask)

    for task in tasks:
        masked_subjects = [
            MaskedSubject(subjectId=fs.subject.subject_id, alias=fs.mask or "")
            for fs in subjects_map.get(task.document_id, [])
        ]

        # Get the status of the task from celery
        task_result = get_result(task.task_id)

        # The job should exist, but if it doesn't, we'll just assume it's queued.
        if not task_result:
            redaction_results.append(
                RedactionResult(
                    RedactionResultPending(
                        jurisdictionId=jurisdiction_id,
                        caseId=case_id,
                        maskedSubjects=masked_subjects,
                        status="QUEUED",
                    )
                )
            )
            continue

        match task_result.status:
            case "PENDING" | "RETRY":
                redaction_results.append(
                    RedactionResult(
                        RedactionResultPending(
                            jurisdictionId=jurisdiction_id,
                            caseId=case_id,
                            maskedSubjects=masked_subjects,
                            status="QUEUED",
                        )
                    )
                )
            case "STARTED":
                redaction_results.append(
                    RedactionResult(
                        RedactionResultPending(
                            jurisdictionId=jurisdiction_id,
                            caseId=case_id,
                            maskedSubjects=masked_subjects,
                            status="PROCESSING",
                        )
                    )
                )
            case "SUCCESS":
                redaction_results.append(
                    RedactionResult(
                        RedactionResultSuccess(
                            jurisdictionId=jurisdiction_id,
                            caseId=case_id,
                            maskedSubjects=masked_subjects,
                            status="COMPLETE",
                            redactedDocument=format_document(task_result.result),
                        )
                    )
                )
            case "FAILURE":
                redaction_results.append(
                    RedactionResult(
                        RedactionResultError(
                            jurisdictionId=jurisdiction_id,
                            caseId=case_id,
                            maskedSubjects=masked_subjects,
                            status="ERROR",
                            error=str(task_result.result),
                        )
                    )
                )
            case _:
                raise ValueError(f"Unknown job status: {task_result.status}")

    return RedactionStatus(
        jurisdictionId=jurisdiction_id,
        caseId=case_id,
        requests=redaction_results,
    )


def format_document(redaction: RedactionTaskResult) -> Document:
    """Format a redacted document for the API response.

    Args:
        redaction (RedactionTaskResult): The redaction results.

    Returns:
        Document: The formatted document.
    """
    document_id = redaction.document_id
    if redaction.external_link:
        return Document(
            root=DocumentLink(
                documentId=document_id,
                attachmentType="LINK",
                url=redaction.external_link,
            )
        )
    else:
        if not redaction.content:
            raise ValueError("No redacted content")
        return Document(
            root=DocumentContent(
                documentId=document_id,
                attachmentType="BASE64",
                content=base64.b64encode(redaction.content).decode("utf-8"),
            )
        )
