import asyncio
import aiohttp
import logging
import config
import asyncpg

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("elixiretest")


class ElixireTestManager():
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.initialize())
        self.loop.run_until_complete(self.run_tests())
        self.loop.run_until_complete(self.finalize())

    async def initialize(self):
        self.aiosession = aiohttp.ClientSession(loop=self.loop)
        self.testurl = "http://127.0.0.1"
        self.testusername = "ave"
        self.testpassword = "7XDNb2f71bxXB3MViraIKdJW77uFXiKF2w"

        log.info('connecting to db')
        self.db = await asyncpg.create_pool(**config.db)
        log.info('connected to db')

        self.test_usernames = [self.testusername, "", " ",
                               "elixiretest", self.testpassword]
        self.test_passwords = [self.testusername, "", " ",
                               "elixiretest", self.testpassword]
        self.test_creds = []

        for test_username in self.test_usernames:
            for test_password in self.test_passwords:
                should_succeed = test_username == self.testusername\
                    and test_password == self.testpassword
                to_append = [test_username, test_password, should_succeed]
                self.test_creds.append(to_append)

    async def finalize(self):
        await self.aiosession.close()
        log.info("All tests successfully complete")

    async def run_tests(self):
        test_functions = [self.check_connection,
                          self.test_get_login,
                          self.test_empty_login,
                          self.test_usernameonly_login,
                          self.test_passwordonly_login,
                          self.test_full_login,
                          self.test_get_apikey,
                          self.test_empty_apikey,
                          self.test_usernameonly_apikey,
                          self.test_passwordonly_apikey,
                          self.test_full_apikey]
        tcount = 0
        for tfunc in test_functions:
            tcount += 1
            log.info(f"Running test {tcount}/{len(test_functions)}:"
                     f" {tfunc.__name__}")
            await tfunc()

    async def check_connection(self):
        res = await self.aiosession.get(f"{self.testurl}/api/domains")
        assert res.status == 200
        log.debug("Got 200 on /api/domains, server is up.")

    async def test_get_login(self):
        res = await self.aiosession.get(f"{self.testurl}/api/login")
        assert res.status == 500
        log.debug(f"Success on GET /api/login.")

    async def test_empty_login(self):
        json_to_send = {}
        res = await self.aiosession.post(f"{self.testurl}/api/login",
                                         json=json_to_send)
        assert res.status == 400
        log.debug(f"Success on empty POST /api/login.")

    async def test_usernameonly_login(self):
        for test_username in self.test_usernames:
            json_to_send = {"user": test_username}
            res = await self.aiosession.post(f"{self.testurl}/api/login",
                                             json=json_to_send)
            assert res.status == 400
        log.debug(f"Success on username-only POST /api/login.")

    async def test_passwordonly_login(self):
        for test_password in self.test_passwords:
            json_to_send = {"password": test_password}
            res = await self.aiosession.post(f"{self.testurl}/api/login",
                                             json=json_to_send)
            assert res.status == 400
        log.debug(f"Success on password-only POST /api/login.")

    async def test_full_login(self):
        for cred in self.test_creds:
            log.debug(f"Trying to login with {cred[0]}:{cred[1]}, "
                      f"expected to login: {cred[2]}")

            json_to_send = {"user": cred[0], "password": cred[1]}

            res = await self.aiosession.post(f"{self.testurl}/api/login",
                                             json=json_to_send)

            log.debug(f"Result: {res.status}")
            if cred[2]:
                assert res.status == 200
                resjson = await res.json()
                self.logintoken = resjson["token"]
                log.debug(f"Got login token: {self.logintoken}")
            else:
                assert res.status == 403
        log.debug("Success on proper POST /api/login.")

    async def test_get_apikey(self):
        res = await self.aiosession.get(f"{self.testurl}/api/apikey")
        assert res.status == 500
        log.debug(f"Success on GET /api/apikey.")

    async def test_empty_apikey(self):
        json_to_send = {}
        res = await self.aiosession.post(f"{self.testurl}/api/apikey",
                                         json=json_to_send)
        assert res.status == 400
        log.debug(f"Success on empty POST /api/apikey.")

    async def test_usernameonly_apikey(self):
        for test_username in self.test_usernames:
            json_to_send = {"user": test_username}
            res = await self.aiosession.post(f"{self.testurl}/api/apikey",
                                             json=json_to_send)
            assert res.status == 400
        log.debug(f"Success on username-only POST /api/apikey.")

    async def test_passwordonly_apikey(self):
        for test_password in self.test_passwords:
            json_to_send = {"password": test_password}
            res = await self.aiosession.post(f"{self.testurl}/api/apikey",
                                             json=json_to_send)
            assert res.status == 400
        log.debug(f"Success on password-only POST /api/apikey.")

    async def test_full_apikey(self):
        for cred in self.test_creds:
            log.debug(f"Trying to get apikey with {cred[0]}:{cred[1]}, "
                      f"expected to get: {cred[2]}")

            json_to_send = {"user": cred[0], "password": cred[1]}

            res = await self.aiosession.post(f"{self.testurl}/api/apikey",
                                             json=json_to_send)

            log.debug(f"Result: {res.status}")
            if cred[2]:
                assert res.status == 200
                resjson = await res.json()
                self.apikeytoken = resjson["api_key"]
                log.debug(f"Got uploader token: {self.apikeytoken}")
            else:
                assert res.status == 403
        log.debug("Success on proper POST /api/apikey.")

    async def test_get_profile(self):
        res = await self.aiosession.get(f"{self.testurl}/api/domains")
        assert res.status == 200
        log.debug("Got 200 on /api/domains, server is up.")


if __name__ == '__main__':
    a = ElixireTestManager()
