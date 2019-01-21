class MockAuditLog:
    def __init__(self):
        pass

    async def send_email(self, _subject, _full_text):
        """Mock method to send an email."""
        return
