# Bulk File Transfer: Windows ↔ Cloud

> 双向批量文件传输方案比较：Windows → Cloud（CC侧上传）和 Cloud → Windows（Hermes侧下发）

---

## 方向一：Windows → Cloud（CC上传到云端）

> 从 Windows 本地（CC 侧）到云端服务器的批量文件传输方案比较

## 方案对比

| 方案 | 适用场景 | 可靠性 | 速度 |
|------|----------|--------|------|
| **tar-over-SSH pipe** | 含空格路径、大量小文件、完整目录结构 | ✅ 最可靠 | ⭐⭐⭐ |
| SCP `-r` | 无空格路径、少量文件 | ⚠️ 路径空格易断 | ⭐⭐ |
| rsync | rsync 两端都安装时 | ✅ | ⭐⭐⭐⭐ |

## 推荐方案：tar-over-SSH pipe

### 从云端拉取（Windows → Cloud）

```bash
# 云端执行：SSH 到 Windows，tar 打包，pipe 到本地 tar 解压
cd <cloud_dest_dir>
mkdir -p <cloud_dest_dir>

ssh -p <port> user@windows \
  "tar -czf - -C \"D:/path/with spaces/target\" ." \
  | tar -xzf -
```

### 参数说明

| 参数 | 含义 |
|------|------|
| `-czf -` | 创建 gzip 压缩 tar，输出到 stdout（`-`=stdout） |
| `-C "D:/path"` | 先 cd 到该目录再打包 |
| `.` | 打包当前目录全部内容（不含容器目录本身） |
| `tar -xzf -` | 从 stdin（`-`）读取并解压 |

### 避坑

- **目标目录先 mkdir -p**：tar 不会自动创建根目录
- **Windows 路径用双引号包裹**：防止 shell 把空格当成分隔符
- **正斜杠 `/` 或双反斜杠 `\\\\\\\\`**：Windows 下 `tar` 命令两者都支持，推荐正斜杠
- **压缩率**：gzip 压缩可选项。网络带宽充足时可去掉 `-z` 加速（`tar -cf -`）

### 方案 B：PowerShell ReadAllBytes + tar pipe（tar 不可靠时）

当 Windows 端 `tar` 命令不可用或行为异常时，可用 PowerShell 字节级读取 + 云端 tar 解压：

```bash
# 云端执行：从 Windows 拉取已打包的 tar.gz 到云端解压
ssh <host-alias> 'powershell -Command "[Console]::OpenStandardOutput().Write([System.IO.File]::ReadAllBytes(\"C:\\Users\\用户名\\AppData\\Local\\Temp\\package.tar.gz\"),0,[System.IO.File]::ReadAllBytes(\"C:\\Users\\用户名\\AppData\\Local\\Temp\\package.tar.gz\").Length)"' | tar -xzf - -C /home/<云端用户>/target/
```

**原理**：PowerShell 将文件以原始字节写入 stdout，通过 SSH pipe 传到云端，tar 从 stdin 解压。不依赖 Windows 端 tar 命令。

**适用场景**：
- Windows SCP 到云端 Connection refused（SSH 反向不通）
- Windows 端 tar 命令路径含空格、中文导致打包失败
- 需要从云端主动拉取（而非 Windows 推送）

**注意**：
- 文件路径必须用 `\"` 转义（PowerShell 字符串内嵌双引号）
- Windows `%TEMP%` 实际映射到 `C:\Users\<用户>\AppData\Local\Temp\`，不要用 `/tmp/`（Windows 上可能映射到 `C:\tmp\` 且不存在）
- 需要先确认 SSH 从云端到 Windows 通（`ssh <host-alias> echo OK`）

---

## 方向二：Cloud → Windows（Hermes下发到CC）

> 从云端服务器到 Windows 本地的文件传输方案

## 问题：Tailscale Relay 下大文件传输不可靠

当云端和 Windows 通过 Tailscale relay（DERP）连接时（非直连 P2P），以下方式会失败：
- **SCP**: 2.6MB 文件在 Tailscale relay 下持续超时（60s）
- **SSH pipe**: bash pipe 方案同样超时

**根因**: relay 连接延迟 ~350ms，吞吐量极低，大文件传输在 timeout 内无法完成。

## 方案：Python HTTP Server + curl

### 步骤

```bash
# === 云端（Hermes侧） ===

# 1. 将文件放到 /tmp/ 目录
tar -czf /tmp/package.tar.gz --exclude='__pycache__' --exclude='.git' /path/to/source/

# 2. 启动临时 HTTP 服务器（后台）
cd /tmp && python3 -m http.server 18888 --bind 0.0.0.0

# === Windows（CC侧） ===

# 3. CC 通过 curl 下载（从 tmux session 内执行）
curl -s http://<服务器IP>:<临时端口>/package.tar.gz -o C:\Users\用户名\package.tar.gz

# 4. 文件到达后解压分析
tar xzf "C:/Users/用户名/package.tar.gz" -C /tmp/extract
```

### 说明

- HTTP（curl）比 SCP/SSH pipe 更健壮：支持断点续传（-C -）、重试（--retry）
- 文件即使只有几 MB，在 relay 下也可能耗时 60s+，但最终能成功
- 使用 `--exclude='__pycache__' --exclude='.git' --exclude='*.pyc'` 大幅缩小包体
- 传输完及时关闭 HTTP 服务器

---

## 为什么不用 SCP

SCP 在以下场景会失败：

1. **路径空格**：`scp "<项目目录>/target/*" user@host:dest/` — 通配符 `*` 被本地 shell 展开后路径含空格，SCP 无法解析
2. **中断无原子性**：传输中途失败导致部分文件到达、部分丢失，状态不确定
3. **目录必须全路径存在**：SCP 要求目标子目录结构精确存在，中途创建失败则整批中断
4. **Tailscale relay 下超时**：延迟~350ms 时大文件在 timeout 内无法完成

## 验证传输完整性

传输完成后：

```bash
# 云端计数
find <cloud_dest> -type f | wc -l

# Windows 计数（通过 SSH）
ssh -p <port> user@windows "dir /s /b \"D:\\path\\target\" | find /c /v \"\""

# 对比两数值，确认一致
```
