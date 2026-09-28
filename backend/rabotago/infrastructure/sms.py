import logging
from typing import Protocol

import httpx

log = logging.getLogger(__name__)


class SmsSender(Protocol):
    async def send(self, phone: str, text: str) -> None: ...


class ConsoleSmsSender:
    """dev/test: SMS yubormaydi, logga yozadi."""

    async def send(self, phone: str, text: str) -> None:
        log.warning("SMS %s: %s", phone, text)


class EskizSmsSender:
    """Eskiz.uz API (https://documenter.getpostman.com/view/663428/RzfmES4z)."""

    BASE = "https://notify.eskiz.uz/api"

    def __init__(self, email: str, password: str, sender: str):
        self._email, self._password, self._from = email, password, sender
        self._token: str | None = None

    async def _login(self, client: httpx.AsyncClient) -> str:
        r = await client.post(f"{self.BASE}/auth/login", data={"email": self._email, "password": self._password})
        r.raise_for_status()
        self._token = r.json()["data"]["token"]
        return self._token

    async def send(self, phone: str, text: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            token = self._token or await self._login(client)
            payload = {"mobile_phone": phone.lstrip("+"), "message": text, "from": self._from}
            r = await client.post(
                f"{self.BASE}/message/sms/send", data=payload, headers={"Authorization": f"Bearer {token}"}
            )
            if r.status_code == 401:  # token eskirgan
                token = await self._login(client)
                r = await client.post(
                    f"{self.BASE}/message/sms/send", data=payload, headers={"Authorization": f"Bearer {token}"}
                )
            r.raise_for_status()
