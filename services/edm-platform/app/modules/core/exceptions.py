class EdmError(Exception):
    status_code = 500


class NotFoundError(EdmError):
    status_code = 404


class ConflictError(EdmError):
    status_code = 409


class UnauthorizedError(EdmError):
    status_code = 401


class ForbiddenError(EdmError):
    status_code = 403


class ValidationFailedError(EdmError):
    status_code = 422


class PayloadTooLargeError(EdmError):
    status_code = 413


class TooManyRequestsError(EdmError):
    status_code = 429


class QualityCheckFailedError(EdmError):
    status_code = 422
