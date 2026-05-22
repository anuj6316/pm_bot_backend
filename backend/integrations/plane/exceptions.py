class PlaneAPIError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PlaneNotFoundError(PlaneAPIError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class PlaneAuthError(PlaneAPIError):
    def __init__(self, message: str = "Invalid or missing Plane API token"):
        super().__init__(message, status_code=401)


class PlaneValidationError(PlaneAPIError):
    def __init__(self, message: str, errors: dict = None):
        self.errors = errors or {}
        super().__init__(message, status_code=400)
