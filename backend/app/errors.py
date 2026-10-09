STATUS = {
    "validation_error": 422,
    "not_found": 404,
    "provider_not_configured": 400,
    "provider_unavailable": 503,
    "provider_timeout": 504,
    "db_unavailable": 503,
    "internal_error": 500,
}


class AppError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self, request_id: str) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "request_id": request_id}
