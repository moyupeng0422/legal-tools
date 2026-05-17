"""MCP 工具的 Pydantic 输入模型"""

from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class SearchInput(BaseModel):
    """案例搜索输入参数

    支持高级检索字段 AND 组合：所有非空字段同时生效。
    下拉字段（sort_id, case_sort, court_level, trial_procedure, court, doc_type）的分类代码
    可通过 rmfyalk_get_enum 工具查询。
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # --- 基础检索 ---
    keyword: str = Field(
        default="",
        description="搜索关键词，如'专利权权属'、'商标侵权'等。使用 sort_id 等高级字段时可省略",
        max_length=200,
    )
    search_field: str = Field(
        default="qw",
        description="一般检索的搜索字段：qw=全文, title=标题, albh=案例编号, cprq=裁判日期, keyword=关键词, jbaq=基本案情, cply=裁判理由",
    )
    case_type: str = Field(
        default="all",
        description="案例类型筛选：all=全部, guiding=指导性案例, reference=参考案例",
    )
    match_type: str = Field(
        default="fuzzy",
        description="匹配方式：fuzzy=模糊匹配, exact=精确匹配",
    )
    page: int = Field(default=1, description="页码，从 1 开始", ge=1)
    page_size: int = Field(default=10, description="每页条数", ge=1, le=50)
    sort_field: str = Field(
        default="",
        description="排序字段：空=相关性, -cpws_al_no=编号降序, -cpws_al_zs_date=裁判时间降序, +cpws_al_zs_date=裁判时间升序",
    )

    # --- 高级检索：文本字段 ---
    key_title: Optional[str] = Field(
        default=None,
        description="标题关键词（高级检索）",
    )
    key_content: Optional[str] = Field(
        default=None,
        description="全文关键词（高级检索）",
    )
    case_number: Optional[str] = Field(
        default=None,
        description="案例编号，如 2021-18-2-160-001",
    )
    case_ref: Optional[str] = Field(
        default=None,
        description="案号，如（2019）最高法民申6342号",
    )
    keyword_tag: Optional[str] = Field(
        default=None,
        description="案例关键词标签（高级检索 keyword_cpwsAl）",
    )

    # --- 高级检索：下拉字段（分类代码） ---
    sort_id: Optional[str] = Field(
        default=None,
        description="案由/罪名分类代码。如 20000528=知识产权权属侵权(父级), 20000528167=发明专利权权属侵权(子级)。可通过 rmfyalk_get_enum 查询",
    )
    case_sort: Optional[str] = Field(
        default=None,
        description="案件类型代码：01=刑事, 02=民事, 03=行政, 04=国家赔偿, 05=执行, 06=调解",
    )
    court_level: Optional[str] = Field(
        default=None,
        description="法院级别代码：01=最高法院, 02=高级法院, 03=中级法院, 04=基层法院, 05=专门法院",
    )
    trial_procedure: Optional[str] = Field(
        default=None,
        description="审理程序代码：01=一审, 02=二审, 03=再审, 04=其他审理程序",
    )
    court: Optional[str] = Field(
        default=None,
        description="审理法院代码。如 01=最高人民法院, 02=北京市(有子节点)。可通过 rmfyalk_get_enum 查询",
    )
    doc_type: Optional[str] = Field(
        default=None,
        description="文书类型代码：001=判决书, 002=裁定书, 003=决定书, 004=调解书, 005=其他文书, 06=通知书",
    )


class EnumInput(BaseModel):
    """分类枚举查询输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True)

    field: str = Field(
        ...,
        description="要查询的字段名：sort=案由罪名, case_sort=案件类型, court_level=法院级别, trial_procedure=审理程序, court=审理法院, doc_type=文书类型",
    )
    parent_id: Optional[str] = Field(
        default=None,
        description="父节点 ID，不传则返回根节点。适用于有层级结构的字段（sort、court、trial_procedure）",
    )


class CaseDetailInput(BaseModel):
    """案例详情输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True)

    case_id: str = Field(
        ...,
        description="案例 ID，来自搜索结果中的 cpws_al_id 字段",
        min_length=1,
    )
    sections: Optional[List[str]] = Field(
        default=None,
        description="指定返回的章节列表（可选）：key_points=裁判要点, case_facts=基本案情, judgment=裁判结果, reasoning=裁判理由, laws=关联法条。不传则返回全部章节",
    )


class StatisticsInput(BaseModel):
    """统计信息输入参数"""

    keyword: Optional[str] = Field(
        default=None,
        description="搜索关键词（可选）。不传则返回全库统计",
    )


class ExportInput(BaseModel):
    """案例导出输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True)

    case_id: Optional[str] = Field(
        default=None,
        description="单条导出：案例 ID（搜索结果中的 cpws_al_id）",
    )
    keyword: Optional[str] = Field(
        default=None,
        description="批量导出：搜索关键词",
    )
    sort_id: Optional[str] = Field(
        default=None,
        description="批量导出：案由分类代码",
    )
    case_type: str = Field(
        default="guiding",
        description="案例类型：all=全部, guiding=指导性案例, reference=参考案例",
    )
    target_dir: Optional[str] = Field(
        default=None,
        description="目标目录路径，默认为 Obsidian 司法案例数据库",
    )
    dry_run: bool = Field(
        default=False,
        description="只返回内容不写文件",
    )


class SetTokenInput(BaseModel):
    """设置 Token 输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True)

    token: str = Field(
        ...,
        description="浏览器 Cookie 中的 faxin-cpws-al-token 值（JWT 格式）",
        min_length=1,
    )
