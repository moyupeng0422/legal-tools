"""国家法律法规数据库 API 客户端"""

from __future__ import annotations

import asyncio
import time

import httpx

BASE_URL = "https://flk.npc.gov.cn/law-search/"

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Referer": "https://flk.npc.gov.cn/",
    "Origin": "https://flk.npc.gov.cn",
}

RATE_LIMIT_INTERVAL = 0.5


class ApiError(Exception):
    pass


class FlkClient:
    def __init__(self):
        self._instance: httpx.AsyncClient | None = None
        self._last_request_time: float = 0.0

    def _get_client(self) -> httpx.AsyncClient:
        if self._instance is None or self._instance.is_closed:
            self._instance = httpx.AsyncClient(
                base_url=BASE_URL,
                headers=COMMON_HEADERS,
                timeout=30.0,
            )
        return self._instance

    async def _rate_limit(self):
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < RATE_LIMIT_INTERVAL:
            await asyncio.sleep(RATE_LIMIT_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    async def post(self, path: str, body: dict | None = None) -> dict:
        await self._rate_limit()
        client = self._get_client()
        resp = await client.post(path, json=body or {})
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise ApiError(data.get("msg") or f"API error code={data.get('code')}")
        return data

    async def get(self, path: str) -> dict:
        await self._rate_limit()
        client = self._get_client()
        resp = await client.get(path)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise ApiError(data.get("msg") or f"API error code={data.get('code')}")
        return data

    async def close(self):
        if self._instance and not self._instance.is_closed:
            await self._instance.aclose()


client = FlkClient()
