# CC 推送 GitHub 部署指南

## 问题模式

CC（Windows 端）需要创建 GitHub 仓库并推送内容时，常见阻塞点：

| 阻塞 | 根因 | 处理 |
|------|------|------|
| `gh: command not found` | gh CLI 未安装 | 安装 winget install GitHub.cli 或手动下载安装 |
| winget MSI 挂起 | MSI 安装弹 UAC 弹窗，SSH 无法响应 | SSHSession 无法提升权限 → 换用 GitHub API token 方案 |
| `git credential fill` 无输出 | 未配置 credential.helper，无缓存 token | 检查 git config --global --list，环境变量，.claude/settings.json |
| `git config` 显示 Claude Code 默认信息 | 用户未在 Windows 上配置 GitHub 身份 | 需用户提供 token 或用 gh auth login |

## 推荐工作流

### 方案 A：提供 Token（推荐）

1. CC 检查凭证 → 无 → 告知用户需要 GitHub Personal Access Token（repo 权限）
2. 用户提供 token 后，CC 用 GitHub API 创建仓库：
   ```bash
   curl -s -H "Authorization: token <PAT>" \
     -H "Accept: application/vnd.github.v3+json" \
     -d '{"name":"repo-name","private":false}' \
     https://api.github.com/user/repos
   ```
3. 本地 init git → add 内容 → commit → 添加 remote → push（用 token 做密码）

### 方案 B：无凭证时本地准备

1. 在独立目录 init git 仓库（不要在主仓库内操作）
2. 复制内容到新仓库
3. 添加 LICENSE（MIT）和更新 README
4. git add + commit
5. 告知用户凭证准备就绪后继续 push

### 检查凭证的命令链

```bash
# 1. git config
git config --global --list
# 2. credential store
git credential fill <<EOF
protocol=https
host=github.com
EOF
# 3. 环境变量
printenv | grep -i GIT
printenv | grep -i GITHUB
# 4. 凭证文件
cat ~/.git-credentials 2>/dev/null
cat ~/.netrc 2>/dev/null
# 5. Windows Credential Manager
cmdkey /list | grep -i github
# 6. CC settings
cat ~/.claude/settings.json 2>/dev/null | grep -i github
```

## 反面案例

2026-06-19：推送 hermes-workbuddy-feishu-collab skill 到 legal-tools 仓库。gh CLI 未安装 → winget install 卡在 UAC → 无缓存的 GitHub 凭证 → 只能准备本地内容后等用户提供 token。总共耗时约 30 分钟确认凭证不可用。教训：如果任务涉及 GitHub push，先检查 gh 和凭证状态，再决定走哪条路径。
