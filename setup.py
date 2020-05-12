# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import setuptools

dependencies = [
    "hypercorn==0.9.0",
    "bcrypt==3.1.7",
    "itsdangerous==1.1.0",
    "cerberus==1.3.2",
    # --------------------------------------------------------------------
    # when changing these dependencies, make sure to change them in
    # .gitlab-ci.yml, too.
    "aioredis==1.3.1",
    "asyncpg==0.20.1",
    # ---------------------------------------------------------------------
    "aiohttp==3.6.2",
    "aioinflux==0.9.0",
    "cryptography==2.8",
    "python-magic==0.4.15",
    "parsedatetime==2.5",
    "dnspython==1.16.0",
    "Quart==0.10.0",
    "Pillow==7.0.0",
    "python-dateutil==2.8.1",
    "violet @ git+https://gitlab.com/elixire/violet.git@854c3f203b1eeefa60506d193f6f23461d2adc55#egg=violet",
    "winter @ git+https://gitlab.com/elixire/winter.git@988c6ca438663c30c6b617bdb16fd6be6c4226ba#egg=winter",
    "hail @ git+https://gitlab.com/elixire/hail.git@d72895019ef68eb96bb775f939182dd9344de36#egg=hail",
]

setuptools.setup(
    name="elixire",
    version="2018-2020.2.0.0",
    description="Image host and link shortener",
    license="AGPL-3.0-only",
    author="Ave Ozkal, Luna Mendes, Mary Strodl, slice",
    url="https://elixi.re",
    python_requires=">=3.7",
    package_data={"": ["*.sql"],},
    packages=setuptools.find_packages(),
    install_requires=dependencies,
    entry_points={"console_scripts": ["elixmanage = elixire.manage.__main__:run"]},
)
