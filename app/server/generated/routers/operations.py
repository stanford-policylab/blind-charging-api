# generated by fastapi-codegen:
#   filename:  openapi.yaml
#   timestamp: 2024-11-11T16:03:22+00:00

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..auth import ValidateAuth
from ..dependencies import *
from ..handlers import operations_handler

router = APIRouter(tags=['operations'])


@router.get(
    '/health',
    response_model=APIStatus,
    responses={'500': {'model': APIStatus}},
    tags=['operations'],
)
async def health_check(request: Request) -> APIStatus:
    """Health check

    Check the health of the API.
    """
    return await operations_handler.health_check(**locals())


@router.post(
    '/oauth2/revoke',
    response_model=None,
    responses={'400': {'model': Error}, '501': {'model': Error}},
    tags=['operations'],
)
async def revoke_access_token(
    request: Request, body: ClientCredentialsRevokeTokenRequest
) -> Optional[Error]:
    """Revoke an access token

    Revoke an access token.

    This endpoint is only available if the `client_credentials` flow is configured
    for the API deployment. If it is not turned on, this endpoint will return a 501.
    """
    return await operations_handler.revoke_access_token(**locals())


@router.post(
    '/oauth2/token',
    response_model=ClientCredentialsTokenResponse,
    responses={'400': {'model': Error}, '501': {'model': Error}},
    tags=['operations'],
)
async def get_access_token(
    request: Request, body: ClientCredentialsTokenRequest
) -> Union[ClientCredentialsTokenResponse, Error]:
    """Get an access token

    Get an access token to use the API.

    This endpoint is only available if the `client_credentials` flow is configured
    for the API deployment. If it is not turned on, this endpoint will return a 501.
    """
    return await operations_handler.get_access_token(**locals())
