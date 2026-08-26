"""人民法院案例库 API 客户端"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import aiohttp
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE_URL = "https://rmfyalk.court.gov.cn/cpws_al_api/api/"

CASE_TYPE_MAP = {
    "all": "cpwsAl_qb",
    "guiding": "cpwsAl_01",
    "reference": "cpwsAl_02",
}

SEARCH_FIELD_MAP = {
    "qw": "全文",
    "title": "标题",
    "albh": "案例编号",
    "cprq": "裁判日期",
    "keyword": "关键词",
    "jbaq": "基本案情",
    "cply": "裁判理由",
}


# tokens.json 路径（MCP 项目根目录，login_rmfyalk.py 写入的新 token 在此）
_TOKENS_JSON = os.path.join(
    os.path.dirname(__file__), "..", "tokens.json"
)

class RmfyalkClient:
    def __init__(self) -> None:
        self._token = os.getenv("RMFYALK_TOKEN", "")
        self._cpws004_token = ""  # 长寿命 session token（24h），作为 cookie 发送
        self._session: aiohttp.ClientSession | None = None
        self._env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        self._last_refresh_time: float = 0.0
        # 启动时优先从 tokens.json 加载最新凭证
        self._sync_from_tokens_json()

    def _sync_from_tokens_json(self) -> bool:
        """从 tokens.json 同步最新的 token 到内存。

        login_rmfyalk.py 每次登录后提取两个 token 写入 tokens.json。
        此方法在每次请求前调用，检测是否有更新并同步到内存。

        Returns:
            True 如果同步了新 token，False 如果无需更新
        """
        if not os.path.exists(_TOKENS_JSON):
            return False
        try:
            with open(_TOKENS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            entry = data.get("rmfyalk")
            if not entry:
                return False

            new_token = entry.get("token", "")
            new_cpws004 = entry.get("cpws004_token", "")
            changed = False

            if new_token and new_token != self._token:
                self._token = new_token
                self._last_refresh_time = entry.get("timestamp", time.time())
                changed = True

            if new_cpws004 and new_cpws004 != self._cpws004_token:
                self._cpws004_token = new_cpws004
                changed = True

            if changed and self._session is not None:
                self._update_session_headers()
                print(f"[rmfyalk] token 已从 tokens.json 同步")
            return changed
        except (json.JSONDecodeError, OSError, KeyError):
            return False

    def _update_session_headers(self) -> None:
        """更新 aiohttp session 的 headers。"""
        if self._session is None:
            return
        if self._token:
            self._session._default_headers["faxin-cpws-al-token"] = self._token
        if self._cpws004_token:
            self._session._default_headers["Cookie"] = f"faxin-cpws004-token={self._cpws004_token}"

    def _extract_token_from_response(self, resp: aiohttp.ClientResponse) -> bool:
        """从 API 响应的 Set-Cookie 中提取刷新后的 cpws-al-token。"""
        set_cookies = resp.headers.getall("set-cookie", [])
        for sc in set_cookies:
            if sc.startswith("faxin-cpws-al-token="):
                val = sc.split("=", 1)[1].split(";")[0]
                if val and val != self._token:
                    self._token = val
                    self._last_refresh_time = time.time()
                    if self._session is not None:
                        self._session._default_headers["faxin-cpws-al-token"] = val
                    self._save_tokens_to_json()
                    return True
        return False

    def _save_tokens_to_json(self) -> None:
        """将当前双 token 写入 tokens.json。"""
        try:
            existing = {}
            if os.path.exists(_TOKENS_JSON):
                with open(_TOKENS_JSON, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing["rmfyalk"] = {
                "token": self._token,
                "cpws004_token": self._cpws004_token,
                "timestamp": self._last_refresh_time,
            }
            with open(_TOKENS_JSON, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        except (OSError, TypeError):
            pass

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Content-Type": "application/json",
                "Referer": "https://rmfyalk.court.gov.cn/view/list.html",
                "Origin": "https://rmfyalk.court.gov.cn",
            }
            if self._token:
                headers["faxin-cpws-al-token"] = self._token
            if self._cpws004_token:
                headers["Cookie"] = f"faxin-cpws004-token={self._cpws004_token}"
            self._session = aiohttp.ClientSession(
                base_url=BASE_URL,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(ssl=False),
            )
        return self._session

    @property
    def token(self) -> str:
        return self._token

    def _persist_to_env(self, key: str, value: str) -> None:
        """写入/更新 .env 文件中的 token/cookie 值"""
        env_path = self._env_path
        if not os.path.exists(env_path):
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"{key}={value}\n")
            return
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        updated = []
        found = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key}="):
                updated.append(f"{key}={value}\n")
                found = True
            else:
                updated.append(line)
        if not found:
            updated.append(f"{key}={value}\n")
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(updated)

    def set_token(self, token: str) -> None:
        self._token = token
        s = self._get_session()
        if token:
            self._persist_to_env("RMFYALK_TOKEN", token)

    async def _sync_token_if_available(self) -> None:
        """请求前检查 tokens.json 是否有 login_rmfyalk.py 写入的新 token。"""
        self._sync_from_tokens_json()

    async def post(self, path: str, body: dict | None = None) -> dict[str, Any]:
        await self._sync_token_if_available()
        s = self._get_session()
        async with s.post(path, json=body or {}) as resp:
            resp.raise_for_status()
            self._extract_token_from_response(resp)
            data = await resp.json()

        if data.get("code") == 401:
            if self._sync_from_tokens_json():
                async with s.post(path, json=body or {}) as resp:
                    resp.raise_for_status()
                    self._extract_token_from_response(resp)
                    data = await resp.json()
                    if data.get("code") == 0:
                        return data
            raise TokenExpiredError(
                "Token 已过期。"
                "请使用 rmfyalk_auto_login 工具自动登录获取新 Token。"
            )
        if data.get("code") != 0:
            raise ApiError(f"API 错误: {data.get('msg', '未知错误')}")
        return data

    async def get(self, path: str) -> dict[str, Any]:
        await self._sync_token_if_available()
        s = self._get_session()
        async with s.get(path) as resp:
            resp.raise_for_status()
            self._extract_token_from_response(resp)
            data = await resp.json()

        if data.get("code") == 401:
            if self._sync_from_tokens_json():
                async with s.get(path) as resp:
                    resp.raise_for_status()
                    self._extract_token_from_response(resp)
                    data = await resp.json()
                    if data.get("code") == 0:
                        return data
            raise TokenExpiredError(
                "Token 已过期。"
                "请使用 rmfyalk_auto_login 工具自动登录获取新 Token。"
            )
        if data.get("code") != 0:
            raise ApiError(f"API 错误: {data.get('msg', '未知错误')}")
        return data

    def build_search_body(
        self,
        keyword: str = "",
        search_field: str = "qw",
        case_type: str = "all",
        match_type: str = "fuzzy",
        page: int = 1,
        page_size: int = 10,
        sort_field: str = "",
        # 高级检索：文本字段
        key_title: str | None = None,
        key_content: str | None = None,
        case_number: str | None = None,
        case_ref: str | None = None,
        keyword_tag: str | None = None,
        # 高级检索：下拉字段
        sort_id: str | None = None,
        case_sort: str | None = None,
        court_level: str | None = None,
        trial_procedure: str | None = None,
        court: str | None = None,
        doc_type: str | None = None,
    ) -> dict:
        lib_code = CASE_TYPE_MAP.get(case_type, "cpwsAl_qb")
        adv_fields = [
            key_title, key_content, case_number, case_ref, keyword_tag,
            sort_id, case_sort, court_level, trial_procedure, court, doc_type,
        ]
        is_advanced = any(v is not None for v in adv_fields)
        user_search_type = 2 if match_type == "fuzzy" else 1

        search_params: dict[str, Any] = {
            "userSearchType": user_search_type,
            "isAdvSearch": "1" if is_advanced else "0",
            "selectValue": [search_field],
            "lib": lib_code,
            "sort_field": sort_field,
        }

        if keyword:
            search_params["keyTitle"] = [keyword]

        if is_advanced:
            if key_title:
                search_params["keyTitle"] = [key_title]
            if key_content:
                search_params["keyContent"] = [key_content]
            if case_number:
                search_params["cpws_al_no"] = case_number
            if case_ref:
                search_params["cpws_al_ajzh"] = case_ref
            if keyword_tag:
                search_params["keyword_cpwsAl"] = [keyword_tag]
            if sort_id:
                search_params["sort_id_cpwsAl"] = sort_id
            if case_sort:
                search_params["case_sort_id_cpwsAl"] = case_sort
            if court_level:
                search_params["fyjb_id_cpwsAl"] = court_level
            if trial_procedure:
                search_params["slcx_id_cpwsAl"] = trial_procedure
            if court:
                search_params["slfy_id_cpwsAl"] = court
            if doc_type:
                search_params["wslx_id_cpwsAl"] = doc_type

        return {
            "page": page,
            "size": page_size,
            "lib": "qb",
            "searchParams": search_params,
        }


class TokenExpiredError(Exception):
    pass


class ApiError(Exception):
    pass


client = RmfyalkClient()
