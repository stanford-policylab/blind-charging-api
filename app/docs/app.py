import os

import aiohttp
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_sso.sso.github import GithubSSO, OpenID

from ..server.generated import app as generated_app

app = FastAPI()

DEFAULT_SECRET = "not a real secret!"
app_secret: str = os.getenv("GITHUB_CLIENT_SECRET", DEFAULT_SECRET)


@generated_app.middleware("http")
async def validate_token(request: Request, call_next):
    """Validate that the requester has a valid auth cookie."""
    redirect_response = RedirectResponse(url="/sso/github/login")
    token = request.cookies.get("token")
    if not token:
        return redirect_response

    try:
        payload = jwt.decode(token, app_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return redirect_response
    except jwt.InvalidTokenError:
        return redirect_response

    if not payload["user"]["id"]:
        return redirect_response

    if not payload.get("perms", {}).get("bc2", False):
        return redirect_response

    request.state.user = payload["user"]
    request.state.perms = payload["perms"]
    return await call_next(request)


app.mount("/api/v1", generated_app)


def get_github_sso() -> GithubSSO:
    """Get the GithubSSO object with the environment variables."""
    return GithubSSO(
        os.getenv("GITHUB_CLIENT_ID"),
        os.getenv("GITHUB_CLIENT_SECRET"),
        redirect_uri=os.getenv("GITHUB_REDIRECT_URI"),
    )


GithubSSODependency = Depends(get_github_sso)


async def check_repo_perm(user: OpenID, repo: str) -> bool:
    """Check if the user has permission to access the given repo.

    Args:
        user (OpenID): The user's information
        repo (str): The name of the repo to check

    Returns:
        bool: True if the user has permission, False otherwise
    """
    # Make a request to the github API:
    # repos/stanford-policylab/:repo/collaborators/:username
    # to check if the user is a collaborator
    username = user.display_name
    if not username:
        return False

    async with aiohttp.ClientSession() as session:
        # Use the env variable GITHUB_PAT to authenticate
        session.headers.update(
            {
                "Authorization": f"Bearer {os.getenv('GITHUB_PAT')}",
                "Accept": "application/vnd.github.v3+json",
            }
        )
        async with session.get(
            f"https://api.github.com/repos/stanford-policylab/{repo}/collaborators/{username}"
        ) as response:
            if response.status == 204:
                return True
            return False


@app.get("/sso/github/login")
async def sso_github_login(github_sso: GithubSSO = GithubSSODependency):
    return await github_sso.get_login_redirect()


@app.get("/sso/github/callback")
async def sso_github_callback(
    request: Request, github_sso: GithubSSO = GithubSSODependency
):
    user = await github_sso.verify_and_process(request)
    can_see_bc2 = await check_repo_perm(user, "bc2")

    if not can_see_bc2:
        raise HTTPException(
            status_code=403, detail="You do not have permission to access this page."
        )

    # Set a signed cookie with the user's information
    token = jwt.encode(
        {
            "user": {
                "id": user.id,
                "display_name": user.display_name,
                "email": user.email,
            },
            "perms": {
                "bc2": can_see_bc2,
            },
        },
        app_secret,
        algorithm="HS256",
    )

    response = RedirectResponse(url="/api/v1/docs")
    response.set_cookie("token", token)
    return response
