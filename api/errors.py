class APIError(Exception):
    status_code = 500

class BadInput(APIError):
    status_code = 400

class FailedAuth(APIError):
    status_code = 403
