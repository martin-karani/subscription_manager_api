class APIError(Exception):
    status_code = 500
    message = "An unexpected API error occurred."
    payload = None

    def __init__(self, message=None, status_code=None, payload=None):
        super().__init__(message or self.message)
        if status_code is not None:
            self.status_code = status_code
        if message is not None:
            self.message = message
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        rv["status"] = "error"
        return rv


class APIValidationError(APIError):
    status_code = 400
    message = "Input validation failed."


class APIAuthError(APIError):
    status_code = 401
    message = "Authentication failed or access denied."


class APIResourceNotFoundError(APIError):
    status_code = 404
    message = "The requested resource was not found."


class APIBadRequestError(APIError):
    status_code = 400
    message = "The request was malformed or invalid."


class APIDatabaseError(APIError):
    status_code = 500
    message = "A database error occurred. Please try again later."
