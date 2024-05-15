from fastapi import HTTPException, Request
from sqlalchemy import text

from ..generated.models import APIStatus

_sql_test = text("SELECT 1")


async def health_check(request: Request) -> APIStatus:
    """Report health of the API."""
    try:
        res = await request.state.db.execute(_sql_test)
        s = res.scalar()
        if s != 1:
            raise Exception("Unexpected result from database")
        return APIStatus(detail="ok")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
