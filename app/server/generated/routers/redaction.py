# generated by fastapi-codegen:
#   filename:  api.yaml
#   timestamp: 2024-05-09T02:33:54+00:00

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from ..dependencies import *
from ..handlers import redaction_handler

router = APIRouter(tags=['redaction'])


@router.post('/redact', response_model=None, tags=['redaction'])
def redact_document(body: RedactionRequest) -> None:
    """
    Redact a document
    """
    return redaction_handler.redact_document(**locals())


@router.get(
    '/redact/{jurisdictionId}/{caseId}',
    response_model=RedactionStatus,
    tags=['redaction'],
)
def get_redaction_status(
    jurisdiction_id: str = Path(..., alias='jurisdictionId'),
    case_id: str = Path(..., alias='caseId'),
) -> RedactionStatus:
    """
    Get status of document redaction for a case.
    """
    return redaction_handler.get_redaction_status(**locals())
