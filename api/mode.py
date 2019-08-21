# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os


class ElixireMode:
    """Wrapper class for the ELIXIRE_ENV variable."""

    def __init__(self):
        self._env = os.getenv("ELIXIRE_ENV") or "dev"

        if not self.is_dev and not self.is_prod:
            raise ValueError(
                "Invalid ELIXIRE_ENV value "
                "(can be dev, development, prod, production)"
            )

    @property
    def is_dev(self) -> bool:
        """Return if the app is in development mode."""
        return self._env in ("dev", "development")

    @property
    def is_prod(self) -> bool:
        """Return if the app is in production mode."""
        return self._env in ("prod", "production")
