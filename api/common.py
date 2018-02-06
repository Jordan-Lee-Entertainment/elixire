import itsdangerous

VERSION = '2.0.0'


class TokenType:
    """Token type "enum"."""
    NONTIMED = 1
    TIMED = 2


SIGNERS = {
    TokenType.TIMED: itsdangerous.TimestampSigner,
    TokenType.NONTIMED: itsdangerous.Signer,
}

