"""国家法律法规数据库 MCP - 输入模型"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FlkSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    search_content: str = Field(
        default="",
        description="搜索关键词",
        max_length=200,
    )
    search_type: int = Field(
        default=2,
        description="匹配类型：1=精确匹配，2=模糊匹配（默认）",
        ge=1,
        le=2,
    )
    search_range: int = Field(
        default=1,
        description="搜索范围：1=标题（默认），2=全文",
        ge=1,
        le=2,
    )
    flfg_code_id: list[str] = Field(
        default_factory=list,
        description="法律分类代码列表（通过 flk_get_enum 查询 flfgfl 获取）",
    )
    zdjg_code_id: list[str] = Field(
        default_factory=list,
        description="制定机关代码列表（通过 flk_get_enum 查询 zdjgfl 获取）",
    )
    gbrq_year: list[str] = Field(
        default_factory=list,
        description="公布年份过滤，如 ['2024', '2023']",
    )
    sxx: Optional[int] = Field(
        default=None,
        description="时效性过滤：1=已废止, 2=被修订, 3=生效中, 4=未生效",
        ge=1,
        le=4,
    )
    page_num: int = Field(
        default=1,
        description="页码，从 1 开始",
        ge=1,
    )
    page_size: int = Field(
        default=20,
        description="每页条数（最大 50）",
        ge=1,
        le=50,
    )


class FlkDetailInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    bbbs: str = Field(
        ...,
        description="法律法规 ID（搜索结果中的 bbbs 字段）",
        min_length=1,
    )


class FlkHitDisplayInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    bbbs: str = Field(
        ...,
        description="法律法规 ID（搜索结果中的 bbbs 字段）",
        min_length=1,
    )
    search_content: str = Field(
        ...,
        description="搜索关键词",
        min_length=1,
        max_length=200,
    )
    search_type: int = Field(
        default=2,
        description="匹配类型：1=精确, 2=模糊（默认）",
        ge=1,
        le=2,
    )
    search_range: int = Field(
        default=1,
        description="搜索范围：1=标题, 2=全文（默认标题）",
        ge=1,
        le=2,
    )


class FlkEnumInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: str = Field(
        ...,
        description="分类类型：flfgfl=法律分类, zdjgfl=制定机关",
    )


class FlkSuggestInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        ...,
        description="搜索关键词前缀",
        min_length=1,
        max_length=100,
    )


class FlkRelatedInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    bbbs: str = Field(
        ...,
        description="法律法规 ID",
        min_length=1,
    )


class FlkDownloadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    bbbs: str = Field(
        ...,
        description="法律法规 ID",
        min_length=1,
    )
    file_type: str = Field(
        default="docx",
        description="文件类型：docx（默认）或 word",
    )


class FlkExportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    bbbs: Optional[str] = Field(
        default=None,
        description="单条导出：法律法规 ID",
    )
    search_content: Optional[str] = Field(
        default=None,
        description="批量导出：搜索关键词",
    )
    search_range: int = Field(
        default=1,
        description="批量导出搜索范围：1=标题, 2=全文",
    )
    sxx: Optional[int] = Field(
        default=3,
        description="批量导出时效性过滤（默认生效中），1=已废止, 2=被修订, 3=生效中, 4=未生效",
    )
    target_dir: Optional[str] = Field(
        default=None,
        description="导出目标目录（默认 Obsidian 法律法规数据库路径）",
    )
    dry_run: bool = Field(
        default=False,
        description="只预览不写文件",
    )
    max_results: int = Field(
        default=50,
        description="批量导出最大条数",
        ge=1,
        le=200,
    )


class HighSearchCondition(BaseModel):
    """高级检索单个条件"""
    field_name: str = Field(
        ...,
        description="搜索字段：title=法律标题, content=法律全文, xgzl.title=相关资料标题, xgzl.content=相关资料全文, gbrq=公布日期, sxrq=施行日期, flfg_code_id=法律分类, zdjg_code_id=制定机关, sxx=时效性",
        min_length=1,
    )
    values: list[str | int] = Field(
        ...,
        description="搜索值列表。文本字段传关键词数组如['专利']；日期字段传['起始日期','结束日期']；分类/时效性传代码数组如[3]",
        min_length=1,
    )
    search_type: int = Field(
        default=2,
        description="匹配类型：1=精确匹配, 2=模糊匹配（默认）。仅对文本字段有效",
        ge=1,
        le=2,
    )
    link: int = Field(
        default=0,
        description="逻辑连接词：0=并且（AND，默认）, 1=或者（OR）, 2=不含（NOT）。第一个条件建议用 0",
        ge=0,
        le=2,
    )

    def to_api_dict(self, index: int) -> dict:
        return {
            "fieldName": self.field_name,
            "values": self.values,
            "searchType": self.search_type,
            "link": self.link,
            "index": index,
        }


class FlkHighSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    conditions: list[HighSearchCondition] = Field(
        ...,
        description="搜索条件列表，支持多个字段组合。每个条件包含字段名、值、匹配类型和逻辑连接词",
        min_length=1,
    )
    page_num: int = Field(
        default=1,
        description="页码，从 1 开始",
        ge=1,
    )
    page_size: int = Field(
        default=10,
        description="每页条数（最大 50）",
        ge=1,
        le=50,
    )

    def to_api_dict(self) -> dict:
        return {
            "dataList": [c.to_api_dict(i) for i, c in enumerate(self.conditions)],
            "orderByParam": {"order": "", "sort": ""},
            "pageNum": self.page_num,
            "pageSize": self.page_size,
        }


class FlkHighHitDisplayInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    bbbs: str = Field(
        ...,
        description="法律法规 ID（搜索结果中的 bbbs 字段）",
        min_length=1,
    )
    conditions: list[HighSearchCondition] = Field(
        ...,
        description="与搜索时相同的条件列表，用于获取命中片段",
        min_length=1,
    )

    def to_api_dict(self) -> dict:
        return {
            "bbbs": self.bbbs,
            "dataList": [c.to_api_dict(i) for i, c in enumerate(self.conditions)],
        }


class FlkHighXgzlInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    bbbs: str = Field(
        ...,
        description="法律法规 ID（搜索结果中的 bbbs 字段）",
        min_length=1,
    )
    conditions: list[HighSearchCondition] = Field(
        ...,
        description="与搜索时相同的条件列表，用于获取相关资料",
        min_length=1,
    )

    def to_api_dict(self) -> dict:
        return {
            "bbbs": self.bbbs,
            "dataList": [c.to_api_dict(i) for i, c in enumerate(self.conditions)],
        }
