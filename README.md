# Legal Tools

> 面向法律从业者的自研 AI 工具集合，涵盖 MCP 服务器、Claude Code Skills 等法律技术工具。兼容 Claude Code 等主流 AI Agent 平台。

## 项目概述

本仓库收录法律实务场景下自主研发的 AI 工具，将法律检索、案例分析等能力集成到 AI 工作流中。目前包含连接中国法律数据库的 MCP 服务器，后续将持续添加更多法律相关的 Skills 和工具。

### 核心特点

- **即插即用**：配置后可直接使用，无需额外开发
- **Obsidian 集成**：支持导出为 Obsidian 格式，构建个人法律知识库
- **批量操作**：内置批量导出脚本，支持按关键词批量检索并导出
- **完整覆盖**：支持高级检索、分类筛选、命中法条展示等专业功能

---

## 工具列表

### MCP 服务器

| 服务器 | 数据源 | 工具数 | 认证 | 说明 |
|--------|--------|--------|------|------|
| **人民法院案例库 MCP** | [rmfyalk.court.gov.cn](https://rmfyalk.court.gov.cn) | 7 | 需 Token | 指导性案例和参考案例检索 |
| **国家法律法规数据库 MCP** | [flk.npc.gov.cn](https://flk.npc.gov.cn) | 11 | 无需 | 法律法规全文检索 |

#### 人民法院案例库 MCP

连接最高人民法院人民法院案例库，搜索和查阅指导性案例、参考案例。

**功能**：案例搜索（一般+高级）、案例详情、聚类统计、分类枚举、导出到 Obsidian、Token 管理

**端口**：`http://localhost:18061/mcp`

详细说明见 [人民法院案例库MCP/README.md](人民法院案例库MCP/README.md)

#### 国家法律法规数据库 MCP

连接全国人大常委会主办的国家法律法规数据库，检索法律法规全文。

**功能**：法律法规搜索、详情获取、命中法条展示、分类枚举、搜索建议、相关法规推荐、下载链接、Obsidian 导出、高级检索

**端口**：`http://localhost:18062/mcp`

详细说明见 [国家法律法规数据库MCP/README.md](国家法律法规数据库MCP/README.md)

---

## 快速开始

### 前置条件

- Python 3.x
- Claude Code 或其他支持 MCP 的 AI 工具

### 安装

```bash
# 克隆仓库
git clone https://github.com/moyupeng0422/legal-tools.git
cd legal-tools

# 安装人民法院案例库 MCP
cd 人民法院案例库MCP
pip install -r requirements.txt

# 安装国家法律法规数据库 MCP
cd ../国家法律法规数据库MCP
pip install -r requirements.txt
```

### 启动

```bash
# 人民法院案例库 MCP
cd 人民法院案例库MCP/scripts
python server.py

# 国家法律法规数据库 MCP
cd 国家法律法规数据库MCP/scripts
python server.py
```

### 配置 MCP 客户端

在 Claude Code 的 MCP 配置中添加：

```json
{
  "rmfyalk": {
    "type": "http",
    "url": "http://localhost:18061/mcp"
  },
  "flk-npc": {
    "type": "http",
    "url": "http://localhost:18062/mcp"
  }
}
```

> 人民法院案例库 MCP 首次使用需设置 Token，详见 [人民法院案例库MCP/README.md](人民法院案例库MCP/README.md)

---

## 技术栈

- Python 3.x + [FastMCP](https://github.com/modelcontextprotocol/python-sdk)（streamable-http 传输）
- httpx（异步 HTTP，内置请求限速）
- Pydantic v2（输入验证）

---

## 许可证

本项目采用 [CC-BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) 许可证。

- **可以**：自由使用、修改、分享（需署名）
- **不可以**：用于商业用途

如需商业授权，请联系作者。

---

## 免责声明

1. **本工具仅供个人学习研究使用**，不得用于商业用途。
2. 本工具通过用户自行提供的合法认证凭证访问相应数据库，**不包含任何绕过认证的功能**。
3. 法律法规和案例内容版权归属相关立法机关和司法机构。本工具仅提供检索便利，不主张对任何内容拥有权利。
4. 用户应自行确保其使用行为符合相关网站的用户协议和法律法规。因不当使用产生的法律责任由用户自行承担。
5. 本工具不对 API 接口的稳定性和可用性做任何保证。
