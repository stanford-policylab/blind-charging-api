from fastapi import FastAPI

from .generated import app as generated_app

app = FastAPI()

app.mount("/api/v1", generated_app)
