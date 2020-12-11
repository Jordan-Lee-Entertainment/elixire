# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from setuptools import setup

setup(
    name="elixire",
    version="2018-2020.2.0.0",
    description="Image host",
    url="https://elixi.re",
    author="Ave Ozkal, Luna Mendes, Mary Strodl, slice",
    python_requires=">=3.7",
    install_requires=[
        "hypercorn==0.11.1",
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
        "violet @ git+https://gitlab.com/elixire/violet.git@bddfb7901dffd9e09c1887eaffc280bae9615699#egg=violet",
        "winter @ git+https://gitlab.com/elixire/winter.git@988c6ca438663c30c6b617bdb16fd6be6c4226ba#egg=winter",
        "hail @ git+https://gitlab.com/elixire/hail.git@d72895019ef68eb96bb775f939182dd9344de36#egg=hail",
        "metomi-isodatetime @ git+https://github.com/metomi/isodatetime.git@db717514a3cc759e656bee9eecb2b1ab1bc7cc5f#egg=metomi-isodatetime",
        "drillbit @ git+https://gitlab.com/elixire/drillbit.git@2e63af2744ac328c9006be80b0b40b51e74d26dc#egg=drillbit",
    ],
)
