import os

from fastapi import Depends, FastAPI, Request
from fastapi_sso.sso.github import GithubSSO

from ..server.generated import app as generated_app

app = FastAPI()

app.mount("/api/v1", generated_app)


def get_github_sso() -> GithubSSO:
    return GithubSSO(
        os.getenv("GITHUB_CLIENT_ID"),
        os.getenv("GITHUB_CLIENT_SECRET"),
        redirect_uri=os.getenv("GITHUB_REDIRECT_URI"),
    )


GithubSSODependency = Depends(get_github_sso)


@app.get("/sso/github/login")
async def sso_github_login(github_sso: GithubSSO = GithubSSODependency):
    return await github_sso.get_login_redirect()


@app.get("/sso/github/callback")
async def sso_github_callback(
    request: Request, github_sso: GithubSSO = GithubSSODependency
):
    user = await github_sso.verify_and_process(request)
    print("USER", user)
    # TODO - check if user has access to bc2 repo
    return user
