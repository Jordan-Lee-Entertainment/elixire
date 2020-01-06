# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import secrets

from cryptography.fernet import Fernet

pytestmark = pytest.mark.asyncio


async def test_d1check(test_cli):
    """Test the /api/check route."""
    test_cli.app.econfig.SECRET_KEY = Fernet.generate_key()
    random_data = secrets.token_hex(10)

    fernet = Fernet(test_cli.app.econfig.SECRET_KEY)
    encrypted = fernet.encrypt(random_data.encode()).decode()

    resp = await test_cli.post("/api/d1/check", json={"data": encrypted})
    assert resp.status_code == 200

    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["data"], str)

    ciphertext = rjson["data"]
    plaintext = fernet.decrypt(ciphertext.encode()).decode()
    assert plaintext.startswith(random_data)
