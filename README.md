# Legal Tools

> 面向中国法律从业者的自研 AI 工具集合，涵盖 MCP 服务器、Claude Code Skills 及知识库管理工具，覆盖法律法规检索、案例分析、合规审核等法律实务场景。兼容 Claude Code 等主流 AI Agent 平台。

![License](https://img.shields.io/badge/License-CC--BY--NC%204.0-lightgrey)
![Python](https://img.shields.io/badge/Python-3.x-blue)

## 关于作者

**彭雨诗律师**，上海市华诚律师事务所合伙人律师、专利代理师、中级知识产权师。毕业于中国政法大学（法学学士）、美国康奈尔大学（法学硕士）、浙江工业大学（计算机工学学士），兼具法律与计算机专业背景。

专注于知识产权民商事争议解决与权利保护。积极探索 AI 技术在法律实务中的应用与开发，致力于推动法律工作流的智能化。

欢迎交流（请注明来意）：

| 微信号 | 微信公众号 |
|--------|-----------|
| <img src="assets/wechat-qr.png" width="200"> | <img src="assets/wechat-mp-qr.jpg" width="200"> |

## 相关项目

| 项目 | 说明 | 许可证 |
|------|------|--------|
| [legal-doc-redactor](https://github.com/moyupeng0422/legal-doc-redactor) | 完全离线的法律文档脱敏工具，支持脱敏和还原，数据不上传 | MIT |

---

## 项目概述

本仓库收录法律实务场景下自主研发的 AI 工具。法律从业者在日常工作中需要频繁检索法律法规、分析案例、审核合规性、管理知识库——这些重复性工作正是 AI 可以显著提效的环节。

本项目的每个工具都源自真实的法律工作需求，在实际业务中持续迭代。

### 工具体系

1. **MCP 服务器** — 连接中国法律数据库，为 AI 工具提供法律检索能力
2. **法律分析 Skills** — 面向具体法律业务的 Claude Code Skills
3. **知识库工具** — 法律法规批量处理、引用关系建立、标签生成等（后续发布）

### 核心特点

- **即插即用**：MCP 服务器配置后可直接使用，无需额外开发
- **Obsidian 集成**：支持将法律法规和案例导出为 Obsidian 格式，构建个人法律知识库
- **批量操作**：内置批量导出脚本，支持按关键词批量检索并导出
- **专业检索**：支持高级检索、分类筛选、命中法条展示等法律专业功能

---

## MCP 服务器

| 服务器 | 数据源 | 工具数 | 认证 | 说明 |
|--------|--------|--------|------|------|
| **人民法院案例库 MCP** | [rmfyalk.court.gov.cn](https://rmfyalk.court.gov.cn) | 7 | 需 Token | 指导性案例和参考案例检索 |
| **国家法律法规数据库 MCP** | [flk.npc.gov.cn](https://flk.npc.gov.cn) | 11 | 无需 | 法律法规全文检索 |

### 人民法院案例库 MCP

连接最高人民法院人民法院案例库，搜索和查阅指导性案例、参考案例。

**功能**：案例搜索（一般+高级）、案例详情（裁判要点/基本案情/裁判理由/关联法条）、聚类统计、分类枚举、导出到 Obsidian、Token 管理

**端口**：`http://localhost:18061/mcp`

详细说明 → [人民法院案例库MCP/README.md](人民法院案例库MCP/README.md)

### 国家法律法规数据库 MCP

连接全国人大常委会主办的国家法律法规数据库，检索法律法规全文。

**功能**：法律法规搜索、详情获取（元数据+目录树+历史版本）、命中法条展示、分类枚举、搜索建议、相关法规推荐、下载链接、Obsidian 导出、多条件高级检索

**端口**：`http://localhost:18062/mcp`

详细说明 → [国家法律法规数据库MCP/README.md](国家法律法规数据库MCP/README.md)

---

## Claude Code Skills

| Skill | 说明 | 许可证 |
|--------|------|--------|
| **法律问题研究分析** | 整合两大 MCP 实现多源法律检索与综合分析（Quick/Full 双模式） | MIT |

### 法律问题研究分析

整合人民法院案例库、国家法律法规数据库两大 MCP，实现多源法律检索与综合分析。

**功能**：
- **Quick 模式**：单一法条查询、快速确认，定向检索后直接回答
- **Full 模式**：五阶段完整流程（问题拆解→法律依据检索→案例检索→交叉校验→报告生成），输出结构化研究报告（Obsidian/DOCX）
- 知识产权案件专项检索策略（专利/商标/著作权/商业秘密）

详细说明 → [法律问题研究分析/SKILL.md](法律问题研究分析/SKILL.md)

---

## 快速开始

### 前置条件

- Python 3.x
- Claude Code 或其他支持 MCP 的 AI 工具

### 安装与启动

```bash
# 克隆仓库
git clone https://github.com/moyupeng0422/legal-tools.git
cd legal-tools

# 安装依赖（二选一或都安装）
cd 人民法院案例库MCP && pip install -r requirements.txt
cd ../国家法律法规数据库MCP && pip install -r requirements.txt

# 启动服务（二选一或都启动）
cd 人民法院案例库MCP/scripts && python server.py
cd 国家法律法规数据库MCP/scripts && python server.py
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
>
> 国家法律法规数据库为公开 API，无需认证。

---

## 技术栈

- **MCP 框架**：[FastMCP](https://github.com/modelcontextprotocol/python-sdk)（streamable-http 传输）
- **HTTP 客户端**：httpx（异步，内置请求限速）
- **数据验证**：Pydantic v2
- **语言**：Python 3.x

---

## 许可证

本项目采用 [CC-BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) 许可证。

| 权限 | 说明 |
|------|------|
| ✅ 使用 | 个人学习研究自由使用 |
| ✅ 修改 | 可自由修改和适配 |
| ✅ 分享 | 可自由分享（需署名） |
| ❌ 商用 | 禁止商业用途 |

如需商业授权，请提交 Issue 联系。

---

## 免责声明

1. **本工具仅供个人学习研究使用**，不得用于商业用途。
2. 本工具通过用户自行提供的合法认证凭证访问相应数据库，**不包含任何绕过认证的功能**。
3. 法律法规和案例内容版权归属相关立法机关和司法机构。本工具仅提供检索便利，不主张对任何内容拥有权利。
4. 用户应自行确保其使用行为符合相关网站的用户协议和法律法规。因不当使用产生的法律责任由用户自行承担。
5. 本工具不对 API 接口的稳定性和可用性做任何保证。
