"""
Root entry point — delegates to api.main.

Run with:
    uvicorn main:app --reload
or:
    uvicorn api.main:app --reload
"""
from api.main import app  # noqa: F401
