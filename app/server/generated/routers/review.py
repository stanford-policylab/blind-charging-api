# generated by fastapi-codegen:
#   filename:  openapi.yaml
#   timestamp: 2024-12-11T00:24:55+00:00

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..auth import ValidateAuth
from ..dependencies import *
from ..handlers import review_handler

router = APIRouter(tags=['review'])


@router.get(
    '/blindreview/{jurisdictionId}/{caseId}',
    response_model=BlindReviewInfo,
    responses={'424': {'model': Error}},
    tags=['review'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}, {'oauth2': []}]))],
)
async def get_blind_review_info(
    request: Request,
    jurisdiction_id: str = Path(..., alias='jurisdictionId'),
    case_id: str = Path(..., alias='caseId'),
    subject_id: Optional[str] = Query(None, alias='subjectId'),
) -> Union[BlindReviewInfo, Error]:
    """Get information about blind review for a given case.

    This endpoint provides information about the blind review process for the given case.

    The payload will indicate whether blind review is required for this case.

    If blind review is required, this endpoint will also provide a list of redacted documents to present for review.
    """
    return await review_handler.get_blind_review_info(**locals())
