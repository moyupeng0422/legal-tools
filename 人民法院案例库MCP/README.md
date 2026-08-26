# 人民法院案例库 MCP Server

**版本：v2.0.0**（2026-08-26）

通过 MCP（Model Context Protocol）连接 [人民法院案例库](https://rmfyalk.court.gov.cn)，在 Claude Code、WorkBuddy 等 AI 工具中直接搜索和查阅指导性案例、参考案例，支持按需自动登录与每周定时案例自动导入。

## 更新日志

- **v2.0.0（2026-08-26）**
  - 架构升级：手动 Token → **按需自动登录**（Playwright + Edge 有头浏览器，Token 过期时自动登录刷新，无需保活协程）
  - 新增工具 `rmfyalk_auto_login`（共 8 个工具）
  - 新增每周定时案例自动导入（`cron_import.py` + Windows 任务计划，每周日 20:00）
  - 修复：auto_login 改为同进程直调（子 agent 环境浏览器弹出、超时问题）、登录弹窗自动点击增强（无跳转时补充再次点击）、check_token 回显矛盾
  - 导出目录改为 `.env` 的 `EXPORT_DIR` 配置（去除硬编码本地路径）
- **v1.0.0（2026-05-17）**：初始版本，手动 Token + 7 个工具

## 功能

- 案例搜索（一般检索 + 高级多条件组合检索）
- 案例详情获取（裁判要点、基本案情、裁判结果、裁判理由、关联法条）
- 聚类统计（类型分布、关键词聚类、年份分布等 7 维度）
- 分类枚举查询（案由、法院、审理程序等下拉选项，支持层级下钻）
- 导出案例到 Obsidian 知识库（自动 IP 类型分类）
- **按需自动登录**（Token 过期自动刷新）
- **每周定时案例自动导入**

## 工具列表（8 个）

| 工具 | 功能 | 必填参数 |
|------|------|---------|
| `rmfyalk_search` | 搜索案例（支持高级检索 AND 组合） | keyword 或任意高级检索字段 |
| `rmfyalk_get_case` | 获取案例详情 | case_id |
| `rmfyalk_get_statistics` | 聚类统计（7 维度分布） | 无 |
| `rmfyalk_get_enum` | 分类枚举代码（案由/法院/程序层级树） | field |
| `rmfyalk_export_case` | 导出案例到 Obsidian | case_id 或 keyword/sort_id |
| `rmfyalk_set_token` | 手动设置 Token（兜底） | token |
| `rmfyalk_check_token` | 检查 Token 有效性 | 无 |
| `rmfyalk_auto_login` | 按需自动登录（Playwright） | 无 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install msedge   # 自动登录需要（首次）
```

依赖：mcp、aiohttp、httpx、pydantic、python-dotenv、playwright

### 2. 配置 .env

```bash
cp .env.example .env
```

编辑 `.env`，配置账号密码（自动登录用）：

```ini
RMFYALK_USERNAME=你的手机号
RMFYALK_PASSWORD=你的密码
# 可选：导出目录（rmfyalk_export_case / 定时导入输出）
EXPORT_DIR=D:\path\to\obsidian\司法案例数据库
```

### 3. 启动服务

```bash
# 双击 start.bat 或手动运行：
cd scripts
python server.py
```

服务默认监听 `http://localhost:18061/mcp`（streamable-http）；作为 MCP 客户端以 stdio 方式拉起时自动走 stdio 传输。

### 4. 配置 MCP 客户端

**方式 A：stdio（推荐，自动登录更稳）**

```json
"rmfyalk": {
  "type": "stdio",
  "command": "python",
  "args": ["路径/人民法院案例库MCP/scripts/server.py"],
  "cwd": "路径/人民法院案例库MCP/scripts"
}
```

**方式 B：streamable-http**

```json
"rmfyalk": {
  "type": "http",
  "url": "http://localhost:18061/mcp"
}
```

### 5. 使用

Token 有效期内直接搜索；**Token 过期时调用 `rmfyalk_auto_login`**——浏览器会自动弹出并完成登录（有头模式，属正常现象），登录后 Token 自动写入 `tokens.json` 与 `.env`，无需手动复制 Cookie。

> Token 有效期约 4 小时，过期后自动登录刷新；自动登录异常时可用 `rmfyalk_set_token` 手动兜底。

## 每周定时导入

- 每周日 20:00 自动执行（Windows 任务计划）：检查 Token → 11 个案由精确检索 + 3 个关键词兜底 → 去重 → 导出 Obsidian
- 手动运行：`cd scripts && python cron_import.py`
- 注册/管理定时任务：`python scripts/register_task.py`（需管理员权限）

## 项目结构

```
人民法院案例库MCP/
├── scripts/
│   ├── server.py             # MCP 服务器入口（8 个工具）
│   ├── client.py             # API 客户端（aiohttp，token 懒同步 + 401 自动重试）
│   ├── login_rmfyalk.py      # 按需自动登录（Playwright + Edge 有头，反检测）
│   ├── cron_import.py        # 每周定时案例自动导入
│   ├── register_task.py      # Windows 定时任务注册
│   ├── models.py             # 数据模型
│   ├── formatters.py         # 响应格式化
│   ├── export_formatter.py   # Obsidian 导出格式化
│   └── export_cases.py       # CLI 批量导出脚本
├── references/
│   └── api-reference.md      # 完整 API 参考（端点/参数/响应/枚举值）
├── .env.example              # 配置模板（账密 + 导出目录）
├── requirements.txt
├── start.bat                 # 启动 MCP Server
└── start_cron_import.bat     # 定时导入启动脚本
```

## 技术栈

- Python 3.x + FastMCP（stdio + streamable-http 双传输）
- aiohttp（主 API 调用，SSL 关闭）+ httpx（枚举查询辅助）
- Playwright + Edge（按需自动登录，拟人化输入 + 反检测）
- Pydantic v2（输入验证）

---

## ⚠️ 免责声明

1. **本工具仅供个人学习研究使用**，不得用于商业用途。
2. 本工具通过用户自行提供的合法认证凭证（账号密码/Token）访问人民法院案例库，**不包含任何绕过认证、破解验证码或获取他人凭证的功能**。
3. 人民法院案例库（rmfyalk.court.gov.cn）的案例内容版权归属相关法院和司法机构。本工具仅提供检索便利，不主张对任何案例内容拥有权利。
4. 用户应自行确保其使用行为符合人民法院案例库网站的用户协议和相关法律法规。因不当使用产生的法律责任由用户自行承担。
5. 本工具不对 API 接口的稳定性和可用性做任何保证。如网站接口变更导致工具失效，开发者不承担任何责任。
