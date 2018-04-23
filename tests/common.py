import secrets
import random

def token():
    return secrets.token_urlsafe(random.randint(100, 300))

def username():
    return token()
