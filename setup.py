# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from setuptools import setup

setup(
    name="elixire",
    version="3.0.0",
    description="Image host",
    url="https://elixi.re",
    author="Ave Ozkal, Luna Mendes, Mary Strodl, slice",
    python_requires=">=3.7",
    install_requires=[
        # hypercorn does not support non-standard http codes yet
        # for now, use forked hypercorn with relevant patch
        # see https://gitlab.com/pgjones/hypercorn/-/merge_requests/48
        "hypercorn @ git+https://gitlab.com/luna/hypercorn.git@1a80b964c5f6997bc0267128a66e5b444d6ccd2e#egg=hypercorn",
        # "hypercorn==0.11.1",
        "bcrypt==3.2.0",
        "itsdangerous==1.1.0",
        "cerberus==1.3.2",
        # --------------------------------------------------------------------
        # when changing these dependencies, make sure to change them in
        # .gitlab-ci.yml, too.
        "aioredis==1.3.1",
        "asyncpg==0.21.0",
        # ---------------------------------------------------------------------
        "aiohttp==3.7.3",
        "aioinflux==0.9.0",
        "cryptography==3.3.1",
        "python-magic==0.4.18",
        "parsedatetime==2.6",
        "dnspython==1.16.0",
        "Quart==0.14.0",
        "Pillow==8.0.1",
        "python-dateutil==2.8.1",
        "violet @ git+https://gitlab.com/elixire/violet.git@ea5b8373c46dc8f5314ef44f2570c00059d58d3b#egg=violet",
        "winter @ git+https://gitlab.com/elixire/winter.git@988c6ca438663c30c6b617bdb16fd6be6c4226ba#egg=winter",
        "hail @ git+https://gitlab.com/elixire/hail.git@d481786d256e682f6992ca250e9f8516205d0608#egg=hail",
        "metomi-isodatetime @ git+https://github.com/metomi/isodatetime.git@db717514a3cc759e656bee9eecb2b1ab1bc7cc5f#egg=metomi-isodatetime",
        "drillbit @ git+https://gitlab.com/elixire/drillbit.git@2e63af2744ac328c9006be80b0b40b51e74d26dc#egg=drillbit",
    ],
)
