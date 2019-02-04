class MockAuditLog:
    def __init__(self):
        pass

    async def push(self, action):
        """Push an action to the mock audit log.

        Calls the action's render() method to test it.
        """
        await action.render()

    async def send_email(self, _subject, _full_text):
        """Mock method to send an email."""
        return
