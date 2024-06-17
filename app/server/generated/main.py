# generated by fastapi-codegen:
#   filename:  openapi.yaml
#   timestamp: 2024-06-17T17:33:27+00:00

from __future__ import annotations

from fastapi import FastAPI

from .routers import experiments, operations, redaction, review

app = FastAPI(
    title='Blind Charging API',
    description='Status: **DRAFT**\n\n**_This is a draft specification. The objects and routes are subject to revision._**\n\nThis API lets an application communicate with the CPL Blind Charging module via an HTTP REST API.\n',
    version='0.2.0',
    contact={'name': 'Joe Nudell', 'email': 'jnudell@hks.harvard.edu'},
    license={'name': 'MIT License', 'url': 'https://opensource.org/license/mit/'},
)

app.include_router(experiments.router)
app.include_router(operations.router)
app.include_router(redaction.router)
app.include_router(review.router)
