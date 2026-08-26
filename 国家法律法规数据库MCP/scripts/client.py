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

    async def download_bytes(self, url: str) -> bytes:
        """下载二进制文件内容（用于 docx 等）

        注意：下载 URL 是 flkoss.obs-bj2.cucloud.cn 签名 URL，
        不是 flk API 路径，需要独立 httpx 客户端。
        """
        await self._rate_limit()
        async with httpx.AsyncClient(timeout=60.0) as dl_client:
            resp = await dl_client.get(url)
            resp.raise_for_status()
            return resp.read()

    async def close(self):
        if self._instance and not self._instance.is_closed:
            await self._instance.aclose()


client = FlkClient()
