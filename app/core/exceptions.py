from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "APP_ERROR"
    message = "Application error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class ResourceNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "RESOURCE_NOT_FOUND"
    message = "Resource was not found"


class ResourceAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "RESOURCE_ALREADY_EXISTS"
    message = "Resource already exists"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "AUTHENTICATION_FAILED"
    message = "Could not validate credentials"


class AuthorizationError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "AUTHORIZATION_FAILED"
    message = "You do not have permission to perform this action"


class BusinessRuleError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "BUSINESS_RULE_VIOLATION"
    message = "Business rule violation"


class TicketNotFoundError(ResourceNotFoundError):
    code = "TICKET_NOT_FOUND"
    message = "Ticket was not found"


class TicketAccessDeniedError(AuthorizationError):
    code = "TICKET_ACCESS_DENIED"
    message = "You do not have access to this ticket"


class InvalidStatusTransitionError(BusinessRuleError):
    code = "INVALID_STATUS_TRANSITION"
    message = "Invalid ticket status transition"


class InvalidAssigneeError(BusinessRuleError):
    code = "INVALID_ASSIGNEE"
    message = "Tickets can only be assigned to active admins"


class TicketClosedError(BusinessRuleError):
    code = "TICKET_CLOSED"
    message = "Closed tickets must be reopened before they can be changed"


class InternalCommentForbiddenError(AuthorizationError):
    code = "INTERNAL_COMMENT_FORBIDDEN"
    message = "Only admins may create or view internal comments"


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    app_error = cast(AppError, exc)
    return error_response(app_error.code, app_error.message, app_error.status_code)


async def validation_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    validation_error = cast(RequestValidationError, exc)
    first_error = validation_error.errors()[0] if validation_error.errors() else {}
    location = ".".join(str(part) for part in first_error.get("loc", []) if part != "body")
    message = first_error.get("msg", "Invalid request")
    if location:
        message = f"{location}: {message}"
    return error_response("VALIDATION_ERROR", message, status.HTTP_422_UNPROCESSABLE_ENTITY)


async def unhandled_exception_handler(_: Request, __: Exception) -> JSONResponse:
    return error_response(
        "INTERNAL_SERVER_ERROR",
        "An unexpected error occurred",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
