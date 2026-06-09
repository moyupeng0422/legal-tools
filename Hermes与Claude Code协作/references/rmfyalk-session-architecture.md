# 人民法院案例库（rmfyalk）Session 架构

> 来源：2026-06-03 浏览器保活讨论，CC 探索 `login-helper` 代码库（14 次工具调用）的输出。

## 核心发现

**根因不是 cookie 丢失，是服务端 ASP.NET session 超时。**

### 两层有效期对比

| 层 | 存储位置 | 超时机制 | 实测有效期 |
|----|---------|---------|-----------|
| JWT Token (`faxin-cpws-al-token`) | `tokens.json` / MCP 配置 | JWT `exp` 字段 | **~4 小时** |
| 浏览器登录态 (ASP.NET Session) | Edge Cookie → 服务端 | 服务端 session 超时（默认 20 分钟无活动） | **~20 分钟无活动后失效** |

### 失效链路

```
用户不操作 → 20 分钟 → ASP.NET Session 超时 → Cookie 仍然存在但已无效
                                              → extract_tokens.py 提取到的 token 已过期
                                              → set_token 返回 "Token 已过期"
```

`browser_data/` 保存了 cookie 文件，但 cookie 在服务端 session 超时后即无效。

### 保活原理

每次页面请求都会重置 ASP.NET session 的超时计数器。因此：

- **每小时访问一次页面即可实现浏览器登录态永不过期**
- 不需要高频轮询，1 小时间隔对于 20 分钟超时窗口绰绰有余

## 保活方案（CC 推荐）

**方案 A：长驻浏览器 + 定时保活**

改造 `auto_refresh.py`：
1. 浏览器保持打开（一次 `launch`，多次 `navigate`），不做 `close`/`launch` 循环
2. 每次提取 token 前先做保活访问（`navigate` 到首页 → 等待加载 → 检测登录状态）
3. 登录态检测：读取页面右上角 DOM 元素（用户名/退出按钮），确认未跳到登录页
4. 保活成功后 → 正常提取 token → `set_token` 注入 MCP

## 待确认

- 人民法院案例库登录后页面右上角的 DOM 选择器（用户名/头像/退出按钮的具体 CSS selector）
- 需要有一次有头模式下手动登录后截图确认页面结构
