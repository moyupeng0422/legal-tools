# badi_finish.ps1 v2.0 (2026-11-23)
# 芭迪完成任务唯一出口（依据 PROTOCOL-v1.8.md §4 + badi-instructions-v18.md + R55 方案）
#   两步：① conv 追加 [state:] 行（fingerprint）→ ② SSH 推云端 conv_inbox（校验+分类重试）
#   卡片由框架回合边界发出，ps1 不管；status.json 更新已移除（v1.8 看板由 Hermes 侧维护）
# v2.0 相对 v1.0 变更：
#   - 删：Update-StatusJson / $StatusPath 及全部调用（下游读者退役）
#   - 加：-DryRun 仅本地校验，不写 state 行、不推、不更新闸门、不发通知
#   - 加：推送三分类 pushed / already / 失败(TRANSIENT|DETERMINISTIC)；瞬时故障退避 2/4/8s 重试 3 次
#   - 加：确定性拒绝（认证/密钥/文件名非法/超限/同名）立即定性不重试
#   - 改：失败纯文本告警 [推送失败] <task-id>，禁 @ Hermes/法律助手/家庭助手（v1.8 §0）
# 约束说明：远端 SSH 被服务端强制命令劫持为 wm_conv_recv，无 ls/test 列目录通道，
#   故"推送前查远端同名"不可实现；等效为推送后响应判定 already（v1.0 P1 逻辑保留），
#   语义=幂等成功、不重试、exit 0、日志标 IDEMPOTENT_SKIP、不写成功闸门。
# 退出码：0=闭环/幂等跳过/仅 dryrun / 1=push 失败 / 2=参数或本地错误

param(
    [Parameter(Mandatory=$true)][string]$TaskId,
    [Parameter(Mandatory=$true)][string]$Step,
    [Parameter(Mandatory=$true)][string]$ConvPath,
    [ValidateSet('done','fail','need_input')]
    [string]$Status = 'done',
    [string]$Summary = '',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# ---- 常量 ----
$CollabDir  = 'D:\<workbuddy-root>\collab\hermes-badi'
$LogPath    = Join-Path $CollabDir 'badi_finish.log'
$GatePath   = Join-Path $CollabDir '.badi_finish_state.json'
$KeyPath    = 'D:\<workbuddy-root>\.ssh\conv-inbox-push-badi'   # T4(2026-11-22)：规范路径密钥，ACL 已收紧
$SshHost    = 'ubuntu@<cloud-tailscale-ip>'
$SshPort    = '2222'
$SshConf    = 'D:\<workbuddy-root>\.ssh\config'
$SshKH      = 'D:\<workbuddy-root>\.ssh\known_hosts'
$NotifyCfg  = Join-Path $CollabDir 'badi_notify.json'
$Utf8NoBom  = New-Object System.Text.UTF8Encoding($false)

# CLI 简写 → 协议状态机词汇（state 行用）
$StatusMap = @{ done='completed'; fail='failed'; need_input='waiting' }
$RetryDelays = @(2, 4, 8)   # 瞬时故障退避：2s / 4s / 8s，最多重试 3 次

function Write-Log([string]$Message) {
    $line = '{0} | {1} | {2} | {3}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $TaskId, $Step, $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Exit-Code([int]$Code, [string]$Message) {
    if ($Message) { Write-Log ('{0} (exit={1})' -f $Message, $Code) }
    exit $Code
}

# FP = sha256("<TaskId>|<Step>|<conv文件名>") 前 12 位 hex（ASCII 字节流）
function Get-Fingerprint([string]$a, [string]$b, [string]$c) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::ASCII.GetBytes(('{0}|{1}|{2}' -f $a, $b, $c))
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLower().Substring(0,12)
    } finally { $sha.Dispose() }
}

# conv [state:] 行：移除全部旧行 → 末尾写新行（保证全文件唯一 live state 行，单行 greppable）
# 注：WorkBuddy safe-delete 钩子拦 Remove-Item，tmp→rename 不可用；conv 单写者，直接覆写风险可接受
function Set-ConvStateLine([string]$Path, [string]$StateLine) {
    $lines = [System.IO.File]::ReadAllLines($Path)
    $kept  = @($lines | Where-Object { $_ -notmatch '^\[state:.*\]\s*$' })
    $kept += $StateLine
    [System.IO.File]::WriteAllLines($Path, $kept, $Utf8NoBom)
}

# 推送彻底失败纯文本告警（best-effort，绝不影响退出码）
# v1.8 §0：禁主动 @ Hermes/法律助手/家庭助手 —— 告警文本不带任何 @ 标签
function Send-PushFailureText([string]$TaskId, [string]$Reason) {
    try {
        if (-not (Test-Path -LiteralPath $NotifyCfg)) { Write-Log 'push failure text skipped: no config'; return }
        $cfg = [System.IO.File]::ReadAllText($NotifyCfg) | ConvertFrom-Json
        if (-not $cfg.webhook) { Write-Log 'push failure text skipped: webhook empty'; return }
        $text = '[推送失败] {0} {1}' -f $TaskId, $Reason
        $body = @{ msg_type = 'text'; content = @{ text = $text } } | ConvertTo-Json -Depth 4
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        Invoke-RestMethod -Uri $cfg.webhook -Method Post -ContentType 'application/json; charset=utf-8' -Body $bytes -TimeoutSec 10 | Out-Null
        Write-Log 'push failure text sent'
    } catch { Write-Log "push failure text error (best-effort, ignored): $_" }
}

# SSH 推送（stdin=conv 文件字节流）
# 返回分类：'pushed'(新落盘) / 'already'(同名幂等) / 'TRANSIENT:<reason>' / 'DETERMINISTIC:<reason>'
# 不用 Start-Process：本会话含 HTTPS_PROXY/https_proxy 重复键，PS5.1 Start-Process 会抛异常；
# 改用 .NET Process 原生继承环境 + ReadToEndAsync 防死锁 + 30s 超时；远端输出按 UTF-8 解码（P1 修正保留）
function Invoke-Push([string]$RemoteName, [string]$LocalPath) {
    $sshExe = (Get-Command ssh.exe -ErrorAction SilentlyContinue).Source
    if (-not $sshExe) { $sshExe = "$env:SystemRoot\System32\OpenSSH\ssh.exe" }
    if (-not (Test-Path -LiteralPath $sshExe)) { Write-Log 'ssh.exe not found'; return 'DETERMINISTIC:ssh-exe-missing' }
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $sshExe
        # D9：-F/UserKnownHostsFile 显式指向 D 盘，避免读取 C:\Users\<windows-username>\.ssh 触发沙箱弹窗
        $psi.Arguments = '-i ' + $KeyPath + ' -F ' + $SshConf + ' -p ' + $SshPort + ' -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=' + $SshKH + ' ' + $SshHost + ' "wm_conv_recv ' + $RemoteName + '"'
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardInput = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
        $proc = [System.Diagnostics.Process]::Start($psi)
        $outTask = $proc.StandardOutput.ReadToEndAsync()
        $errTask = $proc.StandardError.ReadToEndAsync()
        $bytes = [System.IO.File]::ReadAllBytes($LocalPath)
        $proc.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
        $proc.StandardInput.BaseStream.Close()
        if (-not $proc.WaitForExit(30000)) { $proc.Kill(); Write-Log 'ssh timeout 30s, killed'; return 'TRANSIENT:ssh-timeout' }
        $out = ($outTask.Result + ' ' + $errTask.Result).Trim()
        $snippet = $out.Substring(0, [Math]::Min(200, $out.Length))
        Write-Log ("ssh exit={0} resp={1}" -f $proc.ExitCode, $snippet)

        # 同名已存在（幂等成功）：仅"同名+已存在"双词命中才判 already（历史 P1 口径保持不变）
        if ($out -match 'CONV_RECV_FAIL') {
            if ($out -match '同名.{0,40}已存在|已存在.{0,40}同名') { return 'already' }
            Write-Log 'CONV_RECV_FAIL (not duplicate-name) -> deterministic reject'
            return 'DETERMINISTIC:remote-reject'   # pattern 非法 / 超大小上限
        }
        if ($proc.ExitCode -eq 0) { return 'pushed' }

        # 非零退出→故障分类（决定重试与否）
        if ($out -match 'Permission denied|Authentication failed|Load key|UNPROTECTED PRIVATE KEY|Host key verification failed|no such identity') {
            return 'DETERMINISTIC:auth'            # 认证失败：重试无意义
        }
        if ($out -match 'pattern illegal|too long|文件名非法|超限') {
            return 'DETERMINISTIC:remote-reject'   # 文件名非法/超限
        }
        if ($out -match 'Connection refused|Network is unreachable|Connection reset|Connection timed out|No route to host|Operation timed out|Temporary failure|Name or service not known') {
            return 'TRANSIENT:network'             # 瞬时网络故障：可重试
        }
        return 'TRANSIENT:unknown'                  # 未知非零：保守归瞬时，允许有限重试
    } catch {
        Write-Log "ssh spawn/exec error: $_"
        return 'TRANSIENT:spawn-error'
    }
}

# ---- 主流程 ----
try {
    # 0. 本地校验（失败 → exit 2，不推）
    if ([string]::IsNullOrWhiteSpace($TaskId) -or [string]::IsNullOrWhiteSpace($Step)) { Exit-Code 2 'TaskId/Step empty' }
    if (-not (Test-Path -LiteralPath $KeyPath)) { Exit-Code 2 "SSH key missing: $KeyPath" }
    try   { $ConvPath = (Resolve-Path -LiteralPath $ConvPath -ErrorAction Stop).Path }
    catch { Exit-Code 2 "conv file not found: $ConvPath" }
    $ConvName = [System.IO.Path]::GetFileName($ConvPath)

    $mapped = $StatusMap[$Status]
    $fp = Get-Fingerprint $TaskId $Step $ConvName
    $stateLine = '[state: task={0} status={1} files=[{2}] fingerprint={3}]' -f $TaskId, $mapped, $ConvName, $fp

    # 远端目标名（slug 取自 conv 文件名；无远程列目录通道，仅本地生成）
    $slug = ''
    if ($ConvName -match '^conv[_-]([A-Za-z0-9][A-Za-z0-9\-]*)') { $slug = $Matches[1].ToLower() }
    if (-not $slug) { $slug = (($ConvName.ToLower() -replace '[^a-z0-9\-]', '').Trim('-')) }
    if (-not $slug) { $slug = (($TaskId.ToLower()    -replace '[^a-z0-9\-]', '').Trim('-')) }
    $remoteName = 'conv-{0}-{1}-{2}.md' -f $slug, (Get-Date -Format 'yyyyMMdd'), (Get-Date -Format 'HHmm')

    # ---- DryRun：只做本地校验，不写 state 行、不推、不更新闸门、不发通知 ----
    if ($DryRun) {
        $fmtOk = $stateLine -match '^\[state: task=[^\]\s]+ status=(completed|failed|waiting) files=\[[^\]]*\] fingerprint=[0-9a-f]{12}\]$'
        $fmtText = if ($fmtOk) { 'OK' } else { 'INVALID' }
        $convSize = (Get-Item -LiteralPath $ConvPath).Length
        Write-Output 'DRYRUN_BEGIN'
        Write-Output ('  TaskId={0} Step={1} Status={2}->{3}' -f $TaskId, $Step, $Status, $mapped)
        Write-Output ('  Conv={0} (exists, {1} bytes)' -f $ConvName, $convSize)
        Write-Output ('  SSHKey={0} (exists)' -f $KeyPath)
        Write-Output ('  Fingerprint={0}' -f $fp)
        Write-Output ('  StateLine={0}' -f $stateLine)
        Write-Output ('  StateLineFormat={0}' -f $fmtText)
        Write-Output ('  RemoteTarget={0} (slug-derived; NOT pre-checked: forced-command ssh has no ls channel)' -f $remoteName)
        Write-Output '  SKIPPED: state-line-write / ssh-push / gate-write / notify'
        Write-Log "dryrun (fmt=$fmtText, fp=$fp, remote=$remoteName)"
        if (-not $fmtOk) { Exit-Code 2 'dryrun: state line format invalid' }
        Write-Output 'DRYRUN_OK'
        Exit-Code 0 'dryrun only, no push'
    }

    # 幂等闸门：同 TaskId+Step 5 分钟内成功闭环过 → ALREADY_FINISHED exit 0（失败路径不写闸门，重调畅通）
    $gate = $null
    if (Test-Path -LiteralPath $GatePath) {
        try { $gate = [System.IO.File]::ReadAllText($GatePath) | ConvertFrom-Json } catch { $gate = $null }
    }
    $gateKey = '{0}|{1}' -f $TaskId, $Step
    if ($gate -and $gate.last_finish) {
        $prop = $gate.last_finish.PSObject.Properties[$gateKey]
        if ($prop) {
            $last = [DateTime]::Parse($prop.Value)
            if (((Get-Date) - $last).TotalMinutes -lt 5) {
                Write-Output 'ALREADY_FINISHED'
                Exit-Code 0 'duplicate gate hit (within 5 min)'
            }
        }
    }

    # 1. conv 追加 [state] 行
    Set-ConvStateLine $ConvPath $stateLine
    Write-Log "conv state line written (fingerprint=$fp, status=$mapped)"

    # 2. SSH 推送：瞬时故障退避重试 3 次（2/4/8s）；确定性失败/同名立即定性不重试
    $result = Invoke-Push $remoteName $ConvPath
    $attempt = 0
    while ($result -like 'TRANSIENT:*' -and $attempt -lt 3) {
        $delay = $RetryDelays[$attempt]
        Write-Log ("transient failure [{0}], retry {1}/3 after {2}s" -f $result, ($attempt + 1), $delay)
        Start-Sleep -Seconds $delay
        $attempt++
        $result = Invoke-Push $remoteName $ConvPath
    }

    # 同名已存在 = 幂等成功（exit 0，不写闸门，不算成功也不算失败）
    if ($result -eq 'already') {
        Write-Log 'IDEMPOTENT_SKIP: remote same-name exists (exit 0, no gate write)'
        Write-Output ('IDEMPOTENT_SKIP fingerprint={0} remote={1}' -f $fp, $remoteName)
        Exit-Code 0 'idempotent skip (same-name exists remotely)'
    }

    # 新落盘成功
    if ($result -eq 'pushed') {
        $entry = @{ last_finish = @{} }
        if ($gate -and $gate.last_finish) {
            foreach ($prop in $gate.last_finish.PSObject.Properties) { $entry.last_finish[$prop.Name] = $prop.Value }
        }
        $entry.last_finish[$gateKey] = (Get-Date).ToString('o')
        [System.IO.File]::WriteAllText($GatePath, ($entry | ConvertTo-Json -Depth 5), $Utf8NoBom)
        Write-Output ('FINISHED fingerprint={0} remote={1}' -f $fp, $remoteName)
        Exit-Code 0 "closed loop, remote=$remoteName"
    }

    # 推送彻底失败：conv state 标 failed + 纯文本告警 + exit 1（不写 status.json）
    Set-ConvStateLine $ConvPath ('[state: task={0} status=failed files=[{1}] fingerprint={2}]' -f $TaskId, $ConvName, $fp)
    Send-PushFailureText $TaskId $result
    Write-Output ('PUSH_FAILED reason={0}' -f $result)
    Exit-Code 1 ("push failed: {0}; conv kept local; no status.json written" -f $result)
}
catch {
    Exit-Code 2 "unexpected error: $_"
}
