"""人民法院案例库 API 客户端"""

from __future__ import annotations

import os
from typing import Any

import httpx
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


class RmfyalkClient:
    def __init__(self) -> None:
        self._token = os.getenv("RMFYALK_TOKEN", "")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Content-Type": "application/json",
                "Referer": "https://rmfyalk.court.gov.cn/view/list.html",
                "Origin": "https://rmfyalk.court.gov.cn",
            }
            if self._token:
                headers["faxin-cpws-al-token"] = self._token
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                timeout=30.0,
                verify=False,
                headers=headers,
            )
        return self._client

    @property
    def token(self) -> str:
        return self._token

    def set_token(self, token: str) -> None:
        self._token = token
        c = self._get_client()
        c.headers["faxin-cpws-al-token"] = token

    async def post(self, path: str, body: dict | None = None) -> dict[str, Any]:
        c = self._get_client()
        resp = await c.post(path, json=body or {})
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 401:
            raise TokenExpiredError("Token 已过期，请使用 rmfyalk_set_token 更新")
        if data.get("code") != 0:
            raise ApiError(f"API 错误: {data.get('msg', '未知错误')}")
        return data

    async def get(self, path: str) -> dict[str, Any]:
        c = self._get_client()
        resp = await c.get(path)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 401:
            raise TokenExpiredError("Token 已过期，请使用 rmfyalk_set_token 更新")
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

        # 一般检索关键词
        if keyword:
            search_params["keyTitle"] = [keyword]

        # 高级检索字段（AND 组合）
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
