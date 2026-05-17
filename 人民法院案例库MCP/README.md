# 人民法院案例库 MCP Server

通过 MCP（Model Context Protocol）连接 [人民法院案例库](https://rmfyalk.court.gov.cn)，在 Claude Code 等 AI 工具中直接搜索和查阅指导性案例、参考案例。

## 功能

- 案例搜索（一般检索 + 高级多条件组合检索）
- 案例详情获取（裁判要点、基本案情、裁判结果、裁判理由、关联法条）
- 聚类统计（类型分布、关键词聚类、年份分布）
- 分类枚举查询（案由、法院、审理程序等下拉选项）
- 导出案例到 Obsidian 知识库
- Token 管理（设置、检查有效期）

## 工具列表（7 个）

| 工具 | 功能 | 必填参数 |
|------|------|---------|
| `rmfyalk_search` | 搜索案例 | keyword 或任意高级检索字段 |
| `rmfyalk_get_case` | 获取案例详情 | case_id |
| `rmfyalk_get_statistics` | 聚类统计 | 无 |
| `rmfyalk_get_enum` | 分类枚举代码 | field |
| `rmfyalk_export_case` | 导出案例到 Obsidian | case_id 或 keyword/sort_id |
| `rmfyalk_set_token` | 设置认证 Token | token |
| `rmfyalk_check_token` | 检查 Token 有效性 | 无 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

依赖：mcp[cli]、httpx、pydantic、python-dotenv

### 2. 获取 Token

本工具需要您自己在浏览器中登录人民法院案例库网站，从 Cookie 中提取 Token：

1. 访问 [rmfyalk.court.gov.cn](https://rmfyalk.court.gov.cn) 并登录
2. 按 F12 打开开发者工具 → Application → Cookies
3. 找到 `faxin-cpws-al-token`，复制其值

### 3. 配置

```bash
cp .env.example .env
# 编辑 .env，将 Token 粘贴到 RMFYALK_TOKEN= 后面
```

### 4. 启动服务

```bash
# 双击 start.bat 或手动运行：
cd scripts
python server.py
```

服务监听地址：`http://localhost:18061/mcp`

### 5. 配置 MCP 客户端

在 Claude Code 的 MCP 配置中添加：

```json
"rmfyalk": {
  "type": "http",
  "url": "http://localhost:18061/mcp"
}
```

### 6. 使用

启动后，调用 `rmfyalk_set_token` 设置 Token，然后即可使用搜索、详情等工具。

> Token 有效期约 4 小时，过期后需重新获取并设置。

## 项目结构

```
人民法院案例库MCP/
├── scripts/
│   ├── server.py           # MCP 服务器入口
│   ├── client.py           # API 客户端
│   ├── models.py           # 数据模型
│   ├── formatters.py       # 响应格式化
│   ├── export_formatter.py # Obsidian 导出格式化
│   └── export_cases.py     # CLI 批量导出脚本
├── references/
│   └── api-reference.md    # API 端点参考
├── .env.example
├── requirements.txt
└── start.bat
```

## 技术栈

- Python 3.x + FastMCP（streamable-http 传输）
- httpx（异步 HTTP，内置 0.5 秒请求间隔）
- Pydantic v2（输入验证）

---

## ⚠️ 免责声明

1. **本工具仅供个人学习研究使用**，不得用于商业用途。
2. 本工具通过用户自行提供的合法认证凭证（Cookie/Token）访问人民法院案例库，**不包含任何绕过认证、破解验证码或获取他人凭证的功能**。
3. 人民法院案例库（rmfyalk.court.gov.cn）的案例内容版权归属相关法院和司法机构。本工具仅提供检索便利，不主张对任何案例内容拥有权利。
4. 用户应自行确保其使用行为符合人民法院案例库网站的用户协议和相关法律法规。因不当使用产生的法律责任由用户自行承担。
5. 本工具不对 API 接口的稳定性和可用性做任何保证。如网站接口变更导致工具失效，开发者不承担任何责任。
