# generated by fastapi-codegen:
#   filename:  openapi.yaml
#   timestamp: 2024-08-21T19:45:30+00:00

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..auth import ValidateAuth
from ..dependencies import *
from ..handlers import experiments_handler

router = APIRouter(tags=['experiments'])


@router.post(
    '/exposure',
    response_model=None,
    tags=['experiments'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}]))],
)
async def log_exposure(request: Request, body: Exposure) -> None:
    """Log an exposure event

    This endpoint records which information is presented to attorneys and when, prior to them making a decision.

    Sending "exposure" events is required for all cases involved in research experiments, _both for blind review and also final review_.
    """
    return await experiments_handler.log_exposure(**locals())


@router.post(
    '/outcome',
    response_model=None,
    tags=['experiments'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}]))],
)
async def log_outcome(request: Request, body: Review) -> None:
    """Log an outcome event

    This endpoint records the charging decisions made by attorneys, both for blind review and final review.

    Sending "outcome" events is required for all cases involved in research experiments, _regardless of whether the case is subject to blind review or not_.
    """
    return await experiments_handler.log_outcome(**locals())
