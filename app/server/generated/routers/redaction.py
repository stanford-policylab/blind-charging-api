# generated by fastapi-codegen:
#   filename:  openapi.yaml
#   timestamp: 2024-12-19T14:25:50+00:00

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..auth import ValidateAuth
from ..dependencies import *
from ..handlers import redaction_handler

router = APIRouter(tags=['redaction'])


# Callbacks for redact_documents, supplied here for documentation.
# See https://fastapi.tiangolo.com/advanced/openapi-callbacks/
_cb_router_redact_documents = APIRouter()


@_cb_router_redact_documents.post('{$request.body#/callbackUrl}', response_model=None)
def post_redaction_complete_0(body: RedactionResultCompleted) -> None:
    """Redaction complete

    This callback is made for each input document when it is finished.
    """
    pass


@router.post(
    '/redact',
    response_model=None,
    status_code=201,
    tags=['redaction'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}, {'oauth2': []}]))],
    callbacks=_cb_router_redact_documents.routes,
)
async def redact_documents(request: Request, body: RedactionRequest) -> None:
    """Redact a document

    Submit a document for redaction. Redaction happens asynchronously and may take some time.
    When finished, the redacted document will be posted to the provided callback URL.

    A callback will be POSTed to the provided URL when the redaction process is completed for each input document.
    The callback will contain either `RedactionResultSuccess` or `RedactionResultError`.
    """
    return await redaction_handler.redact_documents(**locals())


@router.get(
    '/redact/{jurisdictionId}/{caseId}',
    response_model=RedactionStatus,
    status_code=200,
    tags=['redaction'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}, {'oauth2': []}]))],
)
async def get_redaction_status(
    request: Request,
    jurisdiction_id: str = Path(..., alias='jurisdictionId'),
    case_id: str = Path(..., alias='caseId'),
    subject_id: Optional[str] = Query(None, alias='subjectId'),
) -> RedactionStatus:
    """Get status of document redaction for a case.

    Get the status of redaction for all documents in a case.
    This will return a list of document IDs and their redaction status.

    Generally, the push mechanism provided by the callback URL passed to the `/redact` endpoint should be used to determine when the redaction process is completed.
    However, this endpoint can be used to poll for the status of redaction if necessary.
    """
    return await redaction_handler.get_redaction_status(**locals())
