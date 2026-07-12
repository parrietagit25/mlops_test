"""Helpers HTTP de error consistentes."""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from schemas.common import ErrorBody, ErrorResponse


def error_payload(code: str, message: str, details=None) -> dict:
    return ErrorResponse(error=ErrorBody(code=code, message=message, details=details)).model_dump()


def raise_api_error(
    status_code: int,
    code: str,
    message: str,
    details=None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=error_payload(code, message, details),
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload("HTTP_ERROR", str(exc.detail)),
    )
