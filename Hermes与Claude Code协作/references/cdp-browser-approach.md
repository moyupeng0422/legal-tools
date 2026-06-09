# CDP 浏览器方案：SSH 无法弹窗时的替代路径

## 问题

SSH → tmux → Windows 链路启动的 Playwright `headless=False` 浏览器，进程能正常运行但窗口不出现在用户桌面。`MainWindowHandle` 始终为 0。

根因：Windows session 隔离。SSH 服务运行在独立 session 中，无权创建交互式桌面窗口。即使同一台物理机器上，SSH 启动的进程和桌面启动的进程属于不同 Windows session，前者看不到后者桌面。

## 解决方案：CDP (Chrome DevTools Protocol)

### 用户侧（一次性操作）

在 Windows 桌面打开 cmd/PowerShell，启动 Edge 并开启调试端口：

```bash
# Edge 通常不在 PATH 中，需用完整路径：
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222

# 或：
"C:\Program Files\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222
```

在弹出的 Edge 中登录目标网站（可分批登录，先登录一个也可以启动保活）。浏览器保持打开，CDP 端口常驻 `http://localhost:9222`。

### CC/脚本侧

通过 CDP 连接到用户桌面上的 Edge 实例：

```python
# Playwright CDP 连接
browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
```

已有 `auto_refresh.py` 的 `--cdp` 模式可直接使用：

```bash
# 启动 CDP 保活（仅盯一个系统）
cd <login-helper目录> && python auto_refresh.py --cdp --system rmfyalk --interval 10
```

关键代码注意：`browser.close()` 必须 `await`，否则只发 closed 事件不等待断开，产生 warning：

```python
# ❌ 错误
browser.close()

# ✅ 正确
await browser.close()
```

### 限制

- 登录态失效时**无法自动弹出浏览器让用户登录**——只能提示用户在已打开的 Edge 中手动登录
- CDP 端口仅监听 localhost，远程访问需 SSH 端口转发
- 浏览器意外关闭后需用户手动重启

### 已验证的端到端工作流

2026-06-03，在人民法院案例库（rmfyalk）上完成 CDP 保活完整验证：

**操作流程**：
1. 用户 Windows 桌面启动 Edge + 调试端口（`msedge --remote-debugging-port=9222`）
2. 用户手动登录 rmfyalk（桌面 Edge，有 GUI 权限）
3. Hermes → SSH → CC 执行 `python auto_refresh.py --cdp --system rmfyalk --interval 10`
4. 后台进程 PID 持续运行，每 10 分钟自动检查

**三轮测试结果**（全部通过）：

| 轮次 | 时间 | 登录态 | JWT 有效期 |
|------|------|--------|-----------|
| R1 | 14:32:07 | ✅ OK | -610.7 分钟（过期，已重新提取） |
| R2 | 14:42:11 | ✅ OK | 232.9 分钟（刷新成功） |
| R3 | 14:52:13 | ✅ OK | 222.9 分钟（自然衰减，稳定） |

**关键发现**：
- CC 进程退出不影响保活——Edge 在桌面上独立运行，登录态不丢。CC 重连后重启脚本即可恢复，空窗仅 = 发现断连到重新拉起的时间
- CC `compact` 后可能丢失上下文，误判 keepalive_status.json 为旧数据——需主动纠正
- 长期保活应交由**用户本地桌面 CC** 接管（含 cron 心跳监控一行一报），而非 SSH CC
- Edge 不在 Windows PATH 中，需用完整路径启动

### 适用场景

所有需要通过 SSH 链路操控 Windows 桌面浏览器的场景——登录保活、cookie 提取、页面监控等。
