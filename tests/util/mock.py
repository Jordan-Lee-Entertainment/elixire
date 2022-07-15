# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only


from quart import current_app as app
from collections import namedtuple

import api.common.email
import api.common.webhook
from api.bp.admin.audit_log import AuditLog


WrappedResponse = namedtuple("WrappedResponse", ("status",))


async def mocked_send_email(user_email: str, subject: str, email_body: str) -> tuple:
    app._test_email_list.append(
        {"email": user_email, "subject": subject, "body": email_body}
    )
    return WrappedResponse(200), None


api.common.email.send_email = mocked_send_email
assert api.common.email.send_email == mocked_send_email


async def mocked_post_webhook(webhook_url: str, json_payload: str) -> None:
    return


api.common.webhook._do_post_webhook = mocked_post_webhook


class MockAuditLog(AuditLog):
    def __init__(self):
        super().__init__()
        self._test_emails = []

    async def _sender(self):
        await self._consume_and_process_queue()

    async def send_email(self, subject, full_text):
        """Mock method to send an email."""
        self._test_emails.append({"subject": subject, "body": full_text})


class MockResolver:
    def __init__(self):
        self.test_queries = []

    def query(self, domain: str, resource_type: str) -> None:
        self.test_queries.append({"domain": domain, "resource_type": resource_type})
