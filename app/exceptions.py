from fastapi import HTTPException
from fastapi.responses import JSONResponse

class ValidationError(HTTPException):
    def __init__(self, message: str, field: str = None):
        detail = {"error": "validation_error", "message": message}
        if field:
            detail["field"] = field
        super().__init__(status_code=422, detail=detail)


async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": exc.detail.get("message", "Validation error"),
            "field": exc.detail.get("field"),
        },
    )