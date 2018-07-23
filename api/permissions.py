"""
elixi.re - domain permission helper
"""
from .errors import BadInput, FeatureDisabled


class Permissions:
    """Hold bit positions for each permission."""
    SHORTEN = 0
    UPLOAD = 1


async def domain_permissions(app, domain_id: int, permission: Permissions,
                             raise_on_err=True) -> bool:
    """Check if the given domain matches a given permission.

    This is used to check if you can upload/shorten to a domain.
    """
    perm = await app.db.fetchval("""
    SELECT permissions
    FROM domains
    WHERE domain_id = $1
    """, domain_id)

    if not perm:
        raise BadInput('Domain not found')

    flag = perm & (1 << permission)

    if (not flag) and raise_on_err:
        raise FeatureDisabled(f'This domain has perm {permission} disabled')

    return bool(flag)