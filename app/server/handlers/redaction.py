from fastapi import Request

from ..db import File
from ..generated.models import RedactionRequest, RedactionStatus


async def redact_document(*, request: Request, body: RedactionRequest) -> None:
    if body.document.attachmentType != "LINK":
        raise NotImplementedError("Only document links are supported at this time")

    # Insert document into database
    file = File(
        external_id=body.document.documentId,
        jurisdiction_id=body.jurisdictionId,
        case_id=body.caseId,
        name="test",
        file_type="test",
        file_size=1,
        storage_path=str(body.document.url),
    )
    await file.save(request.state.db)


async def get_redaction_status(
    *, request: Request, jurisdiction_id: str, case_id: str
) -> RedactionStatus:
    return RedactionStatus(
        jurisdictionId=jurisdiction_id,
        caseId=case_id,
        requests=[],
    )
