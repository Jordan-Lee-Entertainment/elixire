# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only


def transform_wildcard(domain: str, subdomain_name: str) -> str:
    """Do domain transformations in the case of a wildcard.

    Parameters
    ---------
    domain: str
        The domain as a template for the transformation.
    subdomain_name: str
        The subdomain to be applied on the template.

    Returns
    -------
    str
        The actual domain you should use.
    """
    # Check if it's wildcard and if we have a subdomain set
    if domain[0:2] == "*.":
        if subdomain_name:
            domain = domain.replace("*.", f"{subdomain_name}.")
        else:
            domain = domain.replace("*.", "")

    return domain
