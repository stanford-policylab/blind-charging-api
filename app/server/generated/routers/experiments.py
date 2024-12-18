# generated by fastapi-codegen:
#   filename:  openapi.yaml
#   timestamp: 2024-12-18T05:23:04+00:00

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..auth import ValidateAuth
from ..dependencies import *
from ..handlers import experiments_handler

router = APIRouter(tags=['experiments'])


@router.get(
    '/config',
    response_model=ExperimentConfig,
    status_code=200,
    tags=['experiments'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}, {'oauth2': []}]))],
)
async def get_active_config(request: Request) -> ExperimentConfig:
    """Get the experiment configuration

    Get the active randomizations configuration for the API deployment.
    """
    return await experiments_handler.get_active_config(**locals())


@router.post(
    '/config',
    response_model=None,
    responses={'400': {'model': Error}},
    tags=['experiments'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}, {'oauth2': []}]))],
)
async def update_config(request: Request, body: NewExperimentConfig) -> Optional[Error]:
    """Update the experiment configuration

    Update the randomizations configuration for the API deployment.
    """
    return await experiments_handler.update_config(**locals())


@router.get(
    '/config/{version}',
    response_model=ExperimentConfig,
    status_code=200,
    tags=['experiments'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}, {'oauth2': []}]))],
)
async def get_config(request: Request, version: str) -> ExperimentConfig:
    """Get the experiment configuration

    Get the randomizations configuration for the API deployment for a specific version.
    """
    return await experiments_handler.get_config(**locals())


@router.post(
    '/config/{version}/activate',
    response_model=None,
    status_code=201,
    tags=['experiments'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}, {'oauth2': []}]))],
)
async def activate_config(request: Request, version: str) -> None:
    """Activate an experiment configuration

    Activate a specific randomizations configuration for the API deployment.
    """
    return await experiments_handler.activate_config(**locals())


@router.get(
    '/configs',
    response_model=ConfigsGetResponse,
    status_code=200,
    tags=['experiments'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}, {'oauth2': []}]))],
)
async def get_all_configs(request: Request) -> ConfigsGetResponse:
    """Get all experiment configurations

    Get all the randomizations configurations for the API deployment.
    """
    return await experiments_handler.get_all_configs(**locals())


@router.post(
    '/exposure',
    response_model=None,
    status_code=201,
    tags=['experiments'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}, {'oauth2': []}]))],
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
    status_code=201,
    tags=['experiments'],
    dependencies=[Depends(ValidateAuth([{'preshared': []}, {'oauth2': []}]))],
)
async def log_outcome(request: Request, body: Review) -> None:
    """Log an outcome event

    This endpoint records the charging decisions made by attorneys, both for blind review and final review.

    Sending "outcome" events is required for all cases involved in research experiments, _regardless of whether the case is subject to blind review or not_.
    """
    return await experiments_handler.log_outcome(**locals())
