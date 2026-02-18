import time
import httpx
from .config import REMOTE_SERVERS

class TokenClient:
    def __init__(self, name, url, client_id, client_secret):
        self.name = name
        self.url = url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._exp = 0

    async def get_token(self):
        if self._token and time.time() < (self._exp - 60):
            return self._token
        return await self._do_login()

    async def _do_login(self):
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{self.url}/auth/token",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
            data = r.json()
            self._token = data["access_token"]
            self._exp = time.time() + data.get("expires_in", 86400)
        return self._token

_clients = {}
for name, cfg in REMOTE_SERVERS.items():
    _clients[name] = TokenClient(name, cfg["url"], cfg["user"], cfg["pass"])

def get_remote_client(name: str) -> TokenClient:
    key = name.lower()
    if key not in _clients:
        raise KeyError(f"Remote server '{name}' not configured in env vars.")
    return _clients[key]
