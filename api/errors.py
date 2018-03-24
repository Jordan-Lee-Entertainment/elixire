class APIError(Exception):
    status_code = 500

    def get_payload(self):
        return {}


class BadInput(APIError):
    status_code = 400


class FailedAuth(APIError):
    status_code = 403


class NotFound(APIError):
    status_code = 404


class Ratelimited(APIError):
    """Memes: here"""
    status_code = 429

    def get_payload(self):
        return {
            'retry_after': self.args[1],
        }


class Banned(APIError):
    """To be thrown by the ratelimiting handler.

    Banned error handlers should disable the user on sight.
    """
    status_code = 420

    def get_payload(self):
        return {
            'reason': self.args[0]
        }


# upload specific errors
class BadImage(APIError):
    """Wrong image mimetype."""
    status_code = 415


class BadUpload(APIError):
    """Upload precondition failed"""
    status_code = 412


class QuotaExploded(APIError):
    status_code = 469
