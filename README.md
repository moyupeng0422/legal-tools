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

---

## 项目概述

本仓库收录法律实务场景下自主研发的 AI 工具。法律从业者在日常工作中需要频繁检索法律法规、分析案例、审核合规性、管理知识库——这些重复性工作正是 AI 可以显著提效的环节。

本项目的每个工具都源自真实的法律工作需求，在实际业务中持续迭代。

### 核心特点

- **即插即用**：MCP 服务器配置后可直接使用，无需额外开发
- **Obsidian 集成**：支持将法律法规和案例导出为 Obsidian 格式，构建个人法律知识库
- **批量操作**：内置批量导出脚本，支持按关键词批量检索并导出
- **专业检索**：支持高级检索、分类筛选、命中法条展示等法律专业功能

---

## 工具列表

### MCP 服务器

| 工具 | 说明 | 许可证 | 备注 |
|------|------|--------|------|
| **人民法院案例库 MCP** | 连接 [rmfyalk.court.gov.cn](https://rmfyalk.court.gov.cn)，指导性/参考案例检索、详情、统计、导出 | CC-BY-NC | 需 Token，[详情](人民法院案例库MCP/README.md) |
| **国家法律法规数据库 MCP** | 连接 [flk.npc.gov.cn](https://flk.npc.gov.cn)，法律法规搜索、命中法条、高级检索、导出 | CC-BY-NC | 无需认证，[详情](国家法律法规数据库MCP/README.md) |

### Skills

| 工具 | 说明 | 许可证 | 备注 |
|------|------|--------|------|
| **法律问题研究分析** | 整合两大 MCP 多源法律检索与综合分析，Quick/Full 双模式，输出 Obsidian/DOCX 研究报告 | MIT | [详情](法律问题研究分析/SKILL.md) |
| **Hermes与Claude Code协作** | 双 AI Agent 结构化协作规范（SSH+tmux），含 CC 端协议、监控辩论、错误恢复等 22 个参考文档 | MIT | [详情](Hermes与Claude Code协作/SKILL.md) |

### 相关项目

| 项目 | 说明 | 许可证 |
|------|------|--------|
| [legal-doc-redactor](https://github.com/moyupeng0422/legal-doc-redactor) | 完全离线的法律文档脱敏工具，支持脱敏和还原，数据不上传 | MIT |

---

## 快速开始

### 安装

```bash
git clone https://github.com/moyupeng0422/legal-tools.git
cd legal-tools

# 安装 MCP 依赖（按需安装）
cd 人民法院案例库MCP && pip install -r requirements.txt
cd ../国家法律法规数据库MCP && pip install -r requirements.txt
```

### 启动 MCP 服务器

```bash
# 人民法院案例库 MCP（端口 18061）
cd 人民法院案例库MCP/scripts && python server.py

# 国家法律法规数据库 MCP（端口 18062）
cd 国家法律法规数据库MCP/scripts && python server.py
```

### 配置 Claude Code

在 MCP 配置中添加：

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

## 许可证

| 许可证 | 适用范围 | 说明 |
|--------|---------|------|
| **CC-BY-NC 4.0** | MCP 服务器 | 可自由使用和分享（需署名），不可商用 |
| **MIT** | Skills、独立工具 | 可自由使用、修改和分发 |

如需商业授权，请提交 Issue 联系。

---

## 免责声明

1. **本工具仅供个人学习研究使用**，不得用于商业用途。
2. 本工具通过用户自行提供的合法认证凭证访问相应数据库，**不包含任何绕过认证的功能**。
3. 法律法规和案例内容版权归属相关立法机关和司法机构。本工具仅提供检索便利，不主张对任何内容拥有权利。
4. 用户应自行确保其使用行为符合相关网站的用户协议和法律法规。因不当使用产生的法律责任由用户自行承担。
5. 本工具不对 API 接口的稳定性和可用性做任何保证。
