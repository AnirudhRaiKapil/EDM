class EdmError(Exception):
    status_code = 500


class NotFoundError(EdmError):
    status_code = 404


class ConflictError(EdmError):
    status_code = 409


class UnauthorizedError(EdmError):
    status_code = 401


class ValidationFailedError(EdmError):
    status_code = 422
