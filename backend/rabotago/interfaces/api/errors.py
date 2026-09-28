from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from rabotago.domain import errors as e

STATUS = {
    e.ValidationFailed: 422,
    e.NotFound: 404,
    e.Unauthorized: 401,
    e.Forbidden: 403,
    e.Conflict: 409,
    e.InvalidState: 409,
    e.RateLimited: 429,
}


def _body(code: str, message: str, details=None) -> dict:
    return {"code": code, "message": message, "details": details}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(e.DomainError)
    async def domain_error(_: Request, exc: e.DomainError):
        status = next((s for cls, s in STATUS.items() if isinstance(exc, cls)), 400)
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        details = [{"loc": err["loc"], "msg": err["msg"]} for err in exc.errors()]
        return JSONResponse(_body("VALIDATION_ERROR", "Ma'lumot noto'g'ri", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse(_body(f"HTTP_{exc.status_code}", str(exc.detail)), status_code=exc.status_code)
