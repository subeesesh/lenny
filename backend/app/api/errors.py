import psycopg
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException

from app.errors import STATUS, AppError

log = structlog.get_logger()


def error_response(request: Request, code: str, message: str, status: int | None = None) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        {"error": {"code": code, "message": message, "request_id": request_id}},
        status_code=status or STATUS[code],
        headers={"X-Request-ID": request_id},
    )


async def app_error(request: Request, exc: AppError) -> JSONResponse:
    return error_response(request, exc.code, exc.message)


async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    code = "not_found" if exc.status_code == 404 else "internal_error"
    return error_response(request, code, str(exc.detail), exc.status_code)


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", ()))
    return error_response(request, "validation_error", f"{where}: {first.get('msg', 'invalid input')}")


async def db_error(request: Request, exc: Exception) -> JSONResponse:
    log.error("db_error", error_code="db_unavailable", error=type(exc).__name__)
    return error_response(request, "db_unavailable", "The database is not reachable.")


async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception("internal_error", error_code="internal_error")
    return error_response(request, "internal_error", "Something went wrong.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(psycopg.OperationalError, db_error)
    app.add_exception_handler(PoolTimeout, db_error)
    app.add_exception_handler(Exception, unhandled_error)
