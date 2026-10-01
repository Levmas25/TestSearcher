import logging
from collections.abc import Mapping
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from src.api.schemas import ErrorBody, ErrorDetail, ErrorResponse
from src.application.exceptions import DependencyUnavailable

logger = logging.getLogger(__name__)


def error_response(
    status: int, code: str, message: str,
    details: list[ErrorDetail] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or []))
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [ErrorDetail(field=".".join(map(str, item["loc"])), message=item["msg"])
               for item in exc.errors()]
    return error_response(422, "validation_error", "Request validation failed.", details)


async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    codes = {404: "not_found", 405: "method_not_allowed"}
    try:
        message = HTTPStatus(exc.status_code).phrase
    except ValueError:
        message = "Request failed."
    return error_response(exc.status_code, codes.get(exc.status_code, "http_error"),
                          message, headers=exc.headers)


async def dependency_error(request: Request, exc: DependencyUnavailable) -> JSONResponse:
    logger.warning("Dependency unavailable", exc_info=exc)
    return error_response(503, "dependency_unavailable", "A required service is temporarily unavailable.")


async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled request failure", exc_info=exc)
    return error_response(500, "internal_error", "An unexpected error occurred.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error)  # pyright: ignore[reportArgumentType]
    app.add_exception_handler(HTTPException, http_error)  # pyright: ignore[reportArgumentType]
    app.add_exception_handler(DependencyUnavailable, dependency_error)  # pyright: ignore[reportArgumentType]
    app.add_exception_handler(Exception, unexpected_error)
