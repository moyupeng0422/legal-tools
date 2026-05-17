# 国家法律法规数据库 MCP Server

通过 MCP（Model Context Protocol）连接 [国家法律法规数据库](https://flk.npc.gov.cn)，在 Claude Code 等 AI 工具中直接检索法律法规、查看命中法条、导出到 Obsidian。

## 功能

- 法律法规搜索（标题/全文，支持分类、状态、年份过滤）
- 法律法规详情获取（元数据 + 目录树 + 历史版本）
- 命中法条展示（关键词高亮的法条片段）
- 高级检索（多条件组合，支持精确/模糊、AND/OR/NOT）
- 分类枚举（法律分类 / 制定机关）
- 搜索建议（自动补全）
- 相关法规推荐
- 下载链接获取（docx/pdf）
- 导出到 Obsidian 法律法规数据库
- CLI 批量导出脚本

## 工具列表（11 个）

| 工具 | 功能 | 必填参数 |
|------|------|---------|
| `flk_search` | 搜索法律法规 | search_content |
| `flk_get_detail` | 获取法规详情（元数据+目录树） | bbbs |
| `flk_hit_display` | 命中法条展示 | bbbs, search_content |
| `flk_get_enum` | 分类枚举 | category |
| `flk_search_suggest` | 搜索建议 | title |
| `flk_get_related` | 相关法规推荐 | bbbs |
| `flk_download` | 获取下载链接 | bbbs |
| `flk_export_law` | 导出法规到 Obsidian | bbbs 或 search_content |
| `flk_high_search` | 高级检索 | conditions |
| `flk_high_hit_display` | 高级检索命中展示 | bbbs, conditions |
| `flk_high_xgzl` | 高级检索相关资料 | bbbs, conditions |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

依赖：mcp、httpx、pydantic、python-dotenv

### 2. 启动服务

```bash
# 双击 start.bat 或手动运行：
cd scripts
python server.py
```

服务监听地址：`http://localhost:18062/mcp`

> 国家法律法规数据库为公开 API，**无需登录或认证**。

### 3. 配置 MCP 客户端

在 Claude Code 的 MCP 配置中添加：

```json
"flk-npc": {
  "type": "http",
  "url": "http://localhost:18062/mcp"
}
```

### 4. 使用

启动后即可直接使用搜索、详情、命中展示等工具。

**示例**：
- 搜索法规：`flk_search(search_content="专利法")`
- 查看详情：`flk_get_detail(bbbs="<搜索结果中的 bbbs>")`
- 命中法条：`flk_hit_display(bbbs="<id>", search_content="侵权")`

## 项目结构

```
国家法律法规数据库MCP/
├── scripts/
│   ├── server.py           # MCP 服务器入口
│   ├── client.py           # API 客户端（内置 0.5s 限速）
│   ├── models.py           # 数据模型（10 个 Pydantic 模型）
│   ├── formatters.py       # 响应格式化
│   ├── export_formatter.py # Obsidian 导出格式化（14 类自动分类）
│   └── export_laws.py      # CLI 批量导出脚本
├── references/
│   └── 05-flk-api-reference.md  # API 端点参考
├── .env.example
├── requirements.txt
└── start.bat
```

## 技术栈

- Python 3.x + FastMCP（streamable-http 传输）
- httpx（异步 HTTP，内置 0.5 秒请求间隔）
- Pydantic v2（输入验证）
- 无需认证

---

## ⚠️ 免责声明

1. **本工具仅供个人学习研究使用**，不得用于商业用途。
2. 国家法律法规数据库（flk.npc.gov.cn）为全国人大常委会办公厅主办的公开平台。根据《著作权法》第五条，法律法规本身不适用著作权法保护。本工具仅提供检索便利，不主张对任何法规内容拥有权利。
3. 本工具不对 API 接口的稳定性和可用性做任何保证。如网站接口变更导致工具失效，开发者不承担任何责任。
4. 用户应自行确保其使用行为符合国家法律法规数据库网站的使用条款和相关法律法规。因不当使用产生的法律责任由用户自行承担。
