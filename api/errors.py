class APIError(Exception):
    status_code = 500


class BadInput(APIError):
    status_code = 400


class FailedAuth(APIError):
    status_code = 403


# upload specific errors
class BadImage(APIError):
    """Wrong image mimetype."""
    status_code = 415


class BadUpload(APIError):
    """Upload precondition failed"""
    status_code = 412
