class MockAuditLog:
    def __init__(self):
        pass

    async def push(self, _action):
        """Mock method to push an action into the audit log
        action queue, which doesn't exist."""
        pass

    async def send_email(self, _subject, _full_text):
        """Mock method to send an email."""
        return
