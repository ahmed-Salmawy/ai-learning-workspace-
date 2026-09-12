class AppError(Exception):
    """Base class for application errors mapped to HTTP responses."""


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass
