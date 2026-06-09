# Reference: SSH 连通性诊断

Hermes 与本地 Windows 之间的 SSH 不通时的系统化诊断流程。

## 架构

```
Hermes（云端）── SSH ──→ Windows（HUAWEI@100.107.207.104:2222）
                     ↑
                 ~/.ssh/config → local-win
```

> **SSH 配置：** `Host local-win` / `HostName 100.107.207.104`（Tailscale IP）/ `Port 2222` / `User HUAWEI`

## 诊断决策树

```
SSH 连接失败
    │
    ├── "Could not resolve hostname"
    │    → 检查 ~/.ssh/config 中 Host 别名是否存在
    │    → cat ~/.ssh/config | grep -A4 local-win
    │
    ├── "Connection refused"
    │    → sshd 未运行或端口不对
    │    → Windows 上检查：
    │       Get-Service sshd                    # 是否 Running
    │       netstat -an | findstr :2222          # 是否 LISTENING
    │    → 修复：Start-Service sshd
    │
    └── "Connection timed out" / Operation timed out
         │
         ├── Step 1: 区分端口状态
         │    nc -zv -w10 100.107.207.104 2222
         │    ├── "refused" → sshd 挂了（回退到上方 refused 流程）
         │    └── "timed out" → TCP 握手失败，继续 Step 2
         │
         ├── Step 2: 检查 Tailscale 连通性
         │    tailscale status | grep 100.107.207
         │    tailscale ping -c 3 100.107.207.104
         │    │
         │    ├── ping 不通 → Tailscale 数据面故障
         │    │    → 让用户在 Windows 上重启 Tailscale
         │    │       Disconnect → Connect，确认在线
         │    │    → 或切换网络（WiFi/热点/有线）
         │    │
         │    └── ping 通但延迟高（如 ~4.7s relay）
         │         → 走中继而非直连（derp），SSH 超时需加大：
         │            ssh -o ConnectTimeout=30 local-win "..."
         │         仍超时 → Step 3
         │
         └── Step 3: 检查 Windows 防火墙
              Tailscale 通但 SSH TCP 握手卡住 → 大概率防火墙拦截
              → Windows 上检查：
                 Get-NetFirewallRule -DisplayName "*SSH*" | ft DisplayName, Enabled, Direction, Action
              → 如果无入站允许规则，添加：
                 New-NetFirewallRule -DisplayName "SSH 2222" -Direction Inbound -Port 2222 -Protocol TCP -Action Allow
              → 或者临时禁用防火墙测试：Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False
                 （⚠️ 仅测试用，测试完需恢复）
```

## Tailscale 状态解读

```
tailscale status 中的连接模式：

  active; direct ...    → 直连（优），延迟低
  active; relay "hkg"   → 中继（降级），延迟高，说明 NAT 打洞失败
  active; relay "sfo"   → 中继（降级），同上
  offline / -           → 不在线
```

**中继常见原因：** 手机热点、受限网络、严格的 NAT 类型。切回 WiFi/有线通常能回到直连。

## 反向：用户直连云端 tmux

用户有时想从本地 Windows SSH 到云端 Ubuntu，直接 `tmux attach` 查看 CC 界面。
此方向已预配：

```bash
# 用户本地 VSCode 终端执行
ssh ubuntu@100.90.24.4 -p 2222    # 云端 Tailscale IP，端口 2222
tmux attach -t claude-session      # 进入后执行，实时看到 CC
```

**前提：** 用户 Windows 的公钥已在云端 `~/.ssh/authorized_keys` 中（`claude-code-remote` 条目）。
若不通，检查云端 `authorized_keys` 是否含用户公钥：`cat ~/.ssh/authorized_keys`。

**常见问题：**
- 退出 tmux（不杀死 session）：`Ctrl+B, D`
- SSH 长时间无操作断开：`ssh -o ServerAliveInterval=60 ...`
- 云端 IP 变动：运行 `tailscale ip -4` 获取当前 IP

```bash
# 云端（Hermes）
tailscale status | grep 100.107.207         # 连接状态和模式
tailscale ping 100.107.207.104              # Tailscale 层 ping
nc -zv -w10 100.107.207.104 2222            # 端口级别测试
ssh -v -o ConnectTimeout=10 local-win "echo OK"  # 详细 SSH 调试日志

# Windows 端（用户手动执行）
Get-Service sshd                             # SSH 服务状态
netstat -an | findstr :2222                  # 端口监听状态
Get-NetFirewallRule -DisplayName "*SSH*"    # 防火墙规则
```

## 本季诊断实录

| 阶段 | 症状 | 根因 | 修复 |
|------|------|------|------|
| 1 | `Connection refused` | sshd 未启动 | `Start-Service sshd` |
| 2 | `timed out`，Tailscale ping 通但延迟高 (~4.7s relay) | 中继延迟 + 网络波动 | 加大 ConnectTimeout 至 30s，持续重试；网络稳定后自行恢复 |
| 3 | 稳定连接 | ✅ | — |

> **注意**：阶段 2 中 `timed out` 但 ping 通，优先怀疑网络抖动/中继延迟，不要过早下结论说防火墙拦截。防火墙只在端口 `refused`（而不是 `timed out`）时才是主因。
