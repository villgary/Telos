# Telos 故障排查指南
# Telos Troubleshooting Guide

> **适用范围 / Audience**: 运维工程师 / SRE / 客户支持
> **版本 / Version**: v2.0 | 中英双语

---

## 目录 / Table of Contents

1. [快速索引 / Quick Index](#1-快速索引)
2. [安装部署问题 / Installation & Deployment Issues](#2-安装部署问题)
3. [扫描问题 / Scanning Issues](#3-扫描问题)
4. [分析引擎问题 / Analysis Engine Issues](#4-分析引擎问题)
5. [告警问题 / Alert Issues](#5-告警问题)
6. [性能问题 / Performance Issues](#6-性能问题)
7. [集成问题 / Integration Issues](#7-集成问题)
8. [前端问题 / Frontend Issues](#8-前端问题)
9. [数据库问题 / Database Issues](#9-数据库问题)
10. [日志收集方法 / Log Collection](#10-日志收集方法)
11. [错误代码速查 / Error Code Reference](#11-错误代码速查)

---

## 1. 快速索引 / Quick Index

### 1.1 按症状快速定位 / Symptom-Based Quick Lookup

| 症状 / Symptom | 可能原因 / Likely Cause | 解决方案 / Solution | 参考章节 / Section |
|--------------|----------------------|-------------------|-----------------|
| 前端白屏 / Frontend blank screen | 后端服务未启动 / Backend not running | 检查后端服务 / Check backend | [8.1](#81-前端白屏-blank-screen) |
| 扫描失败提示连接超时 / Scan timeout | 防火墙/凭据/网络问题 | 检查网络和凭据 | [3.1](#31-连接超时-scan-timeout) |
| 告警未触发 / Alert not triggered | 实时监控未运行 / Monitor not running | 重启实时监控 | [5.1](#51-告警未触发-alert-not-triggering) |
| 分析结果为空 / Analysis returns empty | 尚未执行扫描 / No scan done | 先执行扫描 | [4.1](#41-分析结果为空-empty-analysis-results) |
| 英文界面显示中文 / Chinese in English UI | i18n 配置问题 | 检查 locale 设置 | [8.2](#82-英文界面显示中文-wrong-language) |
| API 500 错误 / API 500 error | 数据库/后端异常 | 查看后端日志 | [11](#11-错误代码速查) |
| 扫描速度慢 / Slow scan | 网络/凭据/资产规模 | 优化配置 | [6.1](#61-扫描速度慢-slow-scan) |

### 1.2 日志文件位置 / Log File Locations

| 服务 / Service | 日志位置 / Location | 查看命令 / Command |
|--------------|-------------------|------------------|
| 后端 / Backend | Docker logs | `docker compose logs -f app` |
| 前端 / Frontend | Docker logs | `docker compose logs -f frontend` |
| Go 引擎 / Go Engine | journalctl | `journalctl -u telos-engine -f` |
| 扫描器 / Scanner | Docker logs | `docker compose logs -f app` (扫描日志) |
| Nginx | `/var/log/nginx/` | `docker compose logs -f nginx` |
| PostgreSQL | Docker 日志 | `docker compose logs -f db` |

---

## 2. 安装部署问题 / Installation & Deployment Issues

### 2.1 Docker Compose 启动失败 / Docker Compose Fails to Start

**症状 / Symptom:**
`docker compose up -d` 命令报错，容器未启动。

**排查步骤 / Troubleshooting Steps:**

**Step 1: 检查 Docker 环境 / Check Docker Environment**
```bash
docker --version
docker compose version
docker info | grep "Server Version"
```

**Step 2: 检查端口占用 / Check Port Conflicts**
```bash
# 检查 3000, 8000, 5432, 6379 端口
netstat -tlnp | grep -E '3000|8000|5432|6379'
```

**Step 3: 检查 .env 文件 / Check .env File**
```bash
# 确保必填环境变量已设置
cat .env | grep -E "DB_PASSWORD|ACCOUNTSCAN_MASTER_KEY|ACCOUNTSCAN_JWT_SECRET"
```

**Step 4: 查看详细错误 / View Detailed Errors**
```bash
docker compose up  # 不使用 -d，查看实时输出
```

**常见错误与解决 / Common Errors & Solutions:**

| 错误 / Error | 原因 / Cause | 解决 / Solution |
|------------|------------|---------------|
| `port is already allocated` | 端口被占用 | 修改 `.env` 中的端口或停止占用进程 |
| `network not found` | Docker 网络未创建 | `docker network create telos_default` |
| `permission denied` | 目录权限问题 | `chmod 755 data/ logs/` |
| `pgdata` directory not writable | PostgreSQL 数据目录权限 | `chown -R 1000:1000 data/postgres` |

### 2.2 首次启动后端报错 / Backend Error on First Start

**症状 / Symptom:**
后端服务启动后立即退出，Docker logs 显示数据库连接错误。

**排查步骤 / Troubleshooting Steps:**

```bash
# 1. 检查数据库是否就绪
docker compose ps db
# 确认状态为 "healthy"

# 2. 等待数据库就绪后重试
docker compose up -d app
docker compose logs app | grep -i error

# 3. 检查数据库连接字符串
docker compose exec app env | grep DATABASE
```

**解决方案 / Solution:**
数据库需要约 10-30 秒完成初始化。在 `docker compose up -d` 后等待 60 秒再检查服务状态：
```bash
sleep 60 && docker compose ps
```

### 2.3 前端构建失败 / Frontend Build Failure

**症状 / Symptom:**
`docker compose build frontend` 失败。

**排查步骤 / Troubleshooting Steps:**

```bash
# 查看详细构建日志
docker compose build --progress=plain frontend

# 常见原因：node_modules 缓存问题
docker compose build --no-cache frontend
```

---

## 3. 扫描问题 / Scanning Issues

### 3.1 连接超时 / Scan Timeout

**症状 / Symptom:**
扫描失败，错误信息：`Connection timeout` 或 `Connection refused`

**排查步骤 / Troubleshooting Steps:**

```
Step 1: 检查网络连通性 ──────────────────
```

```bash
# 从 Telos 服务器 ping 目标资产
ping -c 3 192.168.1.100

# 测试端口连通性（Linux SSH: 22, Windows WinRM: 5985/5986）
nc -zv 192.168.1.100 22
nc -zv 192.168.1.100 5985  # Windows WinRM
```

**Step 2: 检查防火墙 / Check Firewall**
```bash
# 在目标服务器上检查 SSH 端口是否监听
ss -tlnp | grep :22
# 或
netstat -tlnp | grep :22

# 检查防火墙规则（Linux）
sudo iptables -L -n | grep 22
# 或
sudo firewall-cmd --list-ports
```

**Step 3: 检查凭据 / Check Credentials**
```bash
# 在 Telos 中测试连接
curl -X POST http://localhost:8000/api/v1/assets/{id}/test-connection

# 或通过前端 UI：资产管理 → 选择资产 → 测试连接
```

**Step 4: 检查 Control Plane 网络 / Check Control Plane Network**
Telos 服务器需要能访问目标资产的 SSH/WinRM 端口（而非通过跳板机）：
- **直连模式：** Telos 服务器在目标网络内，或有 VPN 连接
- **跳板模式：** 需要配置 SSH 跳板（Jump Server）或使用 SSH ProxyCommand

**跳板配置示例 / Jump Host Configuration:**
在 `.env` 中配置：
```bash
SSH_JUMP_HOST=192.168.1.1
SSH_JUMP_USER=bastion
SSH_JUMP_KEY=/path/to/jump_key
```

**常见错误与解决 / Common Errors & Solutions:**

| 错误信息 / Error Message | 原因 / Cause | 解决 / Solution |
|------------------------|------------|----------------|
| `Connection refused` | SSH 服务未启动或端口不对 | 检查目标服务器 SSH 配置 |
| `Connection timeout` | 防火墙阻断 | 开放 Telos 服务器 IP 到目标端口 |
| `No route to host` | 网络路由问题 | 检查网络/VPN 配置 |
| `Host key verification failed` | SSH HostKey 未确认 | `ssh-keyscan -H 192.168.1.100 >> ~/.ssh/known_hosts` |
| `Permission denied (password)` | 密码错误 | 重新配置正确凭据 |
| `Permission denied (publickey)` | SSH 密钥问题 | 检查私钥格式和权限（`chmod 600`）|

### 3.2 扫描结果账号不完整 / Incomplete Account Discovery

**症状 / Symptom:**
扫描成功但只发现了部分账号。

**排查步骤 / Troubleshooting Steps:**

**Step 1: 确认扫描类型 / Confirm Scan Type**
- **增量扫描** vs **全量扫描**：增量扫描只报告变更，如果上次扫描后无变化，账号数为 0 是正常的
- 建议首次扫描使用**全量扫描**

**Step 2: 检查扫描日志 / Check Scan Logs**
```bash
# 获取扫描任务的详细信息
curl http://localhost:8000/api/v1/scans/{scan_id}
docker compose logs app | grep "scan_id={scan_id}"
```

**Step 3: 手动 SSH 连接验证 / Manual SSH Verification**
```bash
# 手动 SSH 登录，确认能读取 /etc/passwd
ssh user@192.168.1.100 "cat /etc/passwd | wc -l"
```

**Step 4: 检查权限 / Check Permissions**
扫描账号需要能读取 `/etc/passwd`、`/etc/shadow`（如需检测弱密码）、`/etc/sudoers`。

**Step 5: 检查账号隐藏配置 / Check Account Hide Configuration**
某些系统使用 LDAP/NIS 统一认证，本地 `/etc/passwd` 可能不包含所有账号。需要额外配置 LDAP 扫描插件。

### 3.3 扫描卡住无响应 / Scan Hangs

**症状 / Symptom:**
扫描任务状态一直是"扫描中"，无进展。

**排查步骤 / Troubleshooting Steps:**

```bash
# 1. 查看扫描任务的当前状态
curl http://localhost:8000/api/v1/scans/{scan_id}

# 2. 查看后端日志
docker compose logs app | grep -i "scan" | tail -50

# 3. 检查是否有僵尸扫描进程
ps aux | grep -i "ssh\|scanner" | grep -v grep

# 4. 手动 SSH 测试响应速度
time ssh user@192.168.1.100 "echo ok"
```

**解决方案 / Solution:**
如果 SSH 响应慢（> 10 秒），在资产配置中调整超时时间：
```bash
# 在 .env 中调整扫描超时
SCAN_TIMEOUT_SECONDS=300
```

---

## 4. 分析引擎问题 / Analysis Engine Issues

### 4.1 分析结果为空 / Empty Analysis Results

**症状 / Symptom:**
执行"身份威胁分析"后，结果为空。

**排查步骤 / Troubleshooting Steps:**

```
检查优先级（从高到低）：
1. 是否已执行扫描？  ──→ 必须先扫描
2. 扫描是否发现账号？──→ 账号数 > 0
3. 是否有扫描结果关联？──→ 扫描已完成
4. 分析引擎是否正常？──→ 检查日志
```

```bash
# Step 1: 确认已执行扫描
curl http://localhost:8000/api/v1/scans | jq '.data.items[] | {id, status, account_count}'

# Step 2: 确认扫描任务已完成
# status 应为 "completed"

# Step 3: 检查分析引擎日志
docker compose logs app | grep -i "analysis\|go.engine" | tail -30

# Step 4: 检查 Go 引擎是否运行（如果使用）
sudo systemctl status telos-engine
journalctl -u telos-engine -n 20 --no-pager
```

**关键前提 / Key Prerequisite:**
> ⚠️ **必须先完成至少一次扫描，分析才有数据来源。**
> 分析引擎对扫描结果进行分析，如果扫描结果为空，分析结果自然为空。

### 4.2 Go 分析引擎连接失败 / Go Analysis Engine Connection Failed

**症状 / Symptom:**
使用 Go 引擎时报错：`Engine unavailable` 或 `Connection refused`

**排查步骤 / Troubleshooting Steps:**

```bash
# Step 1: 检查 Go 引擎服务状态
sudo systemctl status telos-engine

# Step 2: 检查 Go 引擎日志
journalctl -u telos-engine -n 30 --no-pager

# Step 3: 测试 Go 引擎健康状态
curl http://localhost:8082/health

# Step 4: 检查后端配置
grep GO_ANALYSIS_ENGINE / .env
# 应为: GO_ANALYSIS_ENGINE_URL=http://localhost:8082
```

**解决方案 / Solution:**

```bash
# 重启 Go 引擎
sudo systemctl restart telos-engine

# 如果使用 Python 引擎（默认），则无需配置 GO_ANALYSIS_ENGINE_URL
# 在分析请求中使用 engine="python" 而非 engine="go"
```

---

## 5. 告警问题 / Alert Issues

### 5.1 告警未触发 / Alert Not Triggering

**症状 / Symptom:**
扫描发现了高危配置（如 NOPASSWD sudo），但没有生成告警。

**排查步骤 / Troubleshooting Steps:**

**Step 1: 确认实时监控是否运行 / Confirm Realtime Monitor Running**
```bash
# 检查后台任务
curl http://localhost:8000/api/v1/tasks
# 或查看后端日志中的 "realtime_monitor" 关键词
docker compose logs app | grep -i "realtime_monitor\|alert"
```

**Step 2: 确认告警规则已启用 / Confirm Alert Rules Enabled**
进入前端：**系统设置 → 告警配置**，确认告警类型已启用。

**Step 3: 确认告警渠道已配置 / Confirm Notification Channels**
- Webhook 需要 URL 配置
- 邮件需要 SMTP 配置

**Step 4: 检查告警去重窗口 / Check Alert Deduplication**
告警在同一资产、同一类型 30 分钟内去重。如果之前的告警在 30 分钟内，本次不会重复触发：
```bash
# 查看最近告警
curl http://localhost:8000/api/v1/alerts | jq '.data.items[0:5]'
```

### 5.2 告警重复触发 / Duplicate Alerts

**症状 / Symptom:**
同一告警重复出现多次。

**原因 / Cause:**
- 未正确配置 Webhook 导致重复回调
- 告警去重窗口内多次扫描触发

**排查步骤 / Troubleshooting Steps:**

```bash
# 检查告警创建时间分布
curl http://localhost:8000/api/v1/alerts/stats
```

**解决方案 / Solution:**

1. **检查 Webhook 配置是否重复注册：**
   ```bash
   curl http://localhost:8000/api/v1/webhooks
   # 确保每个 webhook URL 只注册一次
   ```

2. **调整告警去重窗口：**
   在 `.env` 中调整：
   ```bash
   ALERT_DEDUP_WINDOW_MINUTES=60
   ```

### 5.3 告警显示中文但界面为英文 / Chinese Alert in English UI

**症状 / Symptom:**
英文界面下，告警标题和内容显示为中文。

**原因 / Cause:**
告警是在中文界面下创建的，或后端存储了中文文本而未使用 i18n key。

**解决方案 / Solution:**

> ⚠️ 此问题在 v2.0 中已修复（后端已改为存储 `title_key` 和 `message_key`）。
> 旧数据如需迁移，可联系技术支持获取迁移脚本（support@telos.com）。

```bash
# 迁移脚本由技术支持提供后，执行：
sudo -u postgres psql accountscan -f /path/to/migrate_alerts.sql
```

---

## 6. 性能问题 / Performance Issues

### 6.1 扫描速度慢 / Slow Scan

**症状 / Symptom:**
扫描任务耗时远超预期。

**排查步骤 / Troubleshooting Steps:**

**Step 1: 单次扫描时间基线 / Baseline Single Scan Time**

| 规模 / Scale | 预期时间 / Expected | 异常时间 / Abnormal |
|------------|------------------|-----------------|
| 单台服务器（200 账号）| < 5 秒 | > 30 秒 = 慢 |
| 100 台服务器并发 | < 2 分钟 | > 10 分钟 = 慢 |

**Step 2: 诊断网络延迟 / Diagnose Network Latency**
```bash
# 测试到所有目标资产的 SSH 响应时间
for ip in $(cat target_ips.txt); do
  time ssh -o ConnectTimeout=5 user@$ip "echo ok" 2>&1
done
```

**Step 3: 调整并发数 / Adjust Concurrency**
在 `.env` 中调整扫描并发数：
```bash
SCAN_CONCURRENCY=10  # 默认 5，可调高到 20-50
```

**Step 4: 使用 Go 分析引擎 / Use Go Analysis Engine**
对于 10,000+ 账号规模，建议使用 Go 分析引擎（已在 systemd 运行）：
```bash
# 确认 Go 引擎已部署并运行
sudo systemctl status telos-engine

# 在 .env 中配置（Go 引擎通过 systemd 运行，不通过 Docker）
echo "GO_ANALYSIS_ENGINE_URL=http://localhost:8082" >> .env

# 重启后端使配置生效
docker compose restart app
```

### 6.2 前端加载慢或白屏 / Frontend Slow or Blank

**症状 / Symptom:**
前端页面加载缓慢或显示白屏。

**排查步骤 / Troubleshooting Steps:**

**Step 1: 检查后端 API 响应时间 / Check Backend API Response**
```bash
time curl -w "\n" http://localhost:8000/api/v1/assets 2>&1 | tail -5
# 响应时间应 < 1 秒
```

**Step 2: 检查前端容器资源 / Check Frontend Container Resources**
```bash
docker stats
# 确认 CPU 和内存使用率
```

**Step 3: 检查浏览器控制台 / Check Browser Console**
- F12 → Console → 查看 JS 错误
- F12 → Network → 查看是否有请求超时

**Step 4: 检查 Redis 缓存 / Check Redis Cache**
```bash
docker compose exec redis redis-cli ping
# 应返回 PONG
```

---

## 7. 集成问题 / Integration Issues

### 7.1 Webhook 推送失败 / Webhook Delivery Failed

**症状 / Symptom:**
告警已生成，但 Webhook 未收到推送。

**排查步骤 / Troubleshooting Steps:**

**Step 1: 检查 Webhook 配置 / Check Webhook Config**
```bash
curl http://localhost:8000/api/v1/webhooks
# 确认 URL 正确、事件已订阅
```

**Step 2: 在目标服务器测试 Webhook 端点 / Test Webhook Endpoint**
```bash
# 在 Webhook 接收端测试
curl -X POST https://your-soar.com/webhook/telos \
  -H "Content-Type: application/json" \
  -d '{"event":"test","timestamp":"2026-04-12T10:00:00Z"}'
```

**Step 3: 检查后端 Webhook 日志 / Check Backend Webhook Logs**
```bash
docker compose logs app | grep -i webhook | tail -20
```

**Step 4: 检查网络连通性 / Check Network**
```bash
# Telos 服务器到 Webhook 端点的连通性
curl -v --max-time 10 https://your-soar.com/webhook/telos
```

**Step 5: 验证 Webhook 签名 / Verify Webhook Signature**
Webhook 使用 `X-Telos-Signature` 头进行签名验证：
```python
# 接收端验证示例
import hmac, hashlib

def verify(signature, payload, secret):
    expected = 'sha256=' + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 7.2 SSO / LDAP 集成失败 / SSO / LDAP Integration Failed

**症状 / Symptom:**
SSO 登录失败或 LDAP 用户同步失败。

**排查步骤 / Troubleshooting Steps:**

```bash
# Step 1: 测试 LDAP 连接
ldapsearch -H ldap://your-ldap-server:389 \
  -D "cn=admin,dc=company,dc=com" \
  -w "your-password" \
  -b "dc=company,dc=com" "(objectClass=user)" 1

# Step 2: 检查 SSO 配置
cat /opt/accountscan/config/sso.yaml

# Step 3: 查看认证日志
docker compose logs app | grep -i "sso\|ldap\|oidc\|saml" | tail -30
```

### 7.3 PAM 集成比对失败 / PAM Integration Comparison Failed

**症状 / Symptom:**
PAM 集成后，"账号比对"结果显示大量"未匹配"。

**排查步骤 / Troubleshooting Steps:**

```bash
# Step 1: 测试 PAM API 连通性
curl -X GET "https://your-pam-server/api/v1/accounts" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -w "\nHTTP_CODE: %{http_code}\n"

# Step 2: 检查 PAM API 版本兼容性
# 不同 PAM 产品的 API 格式可能不同，确认 Telos 支持该版本

# Step 3: 查看比对日志
docker compose logs app | grep -i "pam\|comparison" | tail -30
```

---

## 8. 前端问题 / Frontend Issues

### 8.1 前端白屏 / Frontend Blank Screen

**排查步骤 / Troubleshooting Steps:**

**Step 1: 检查前端容器 / Check Frontend Container**
```bash
docker compose ps frontend
# 状态应为 "Up"
```

**Step 2: 检查前端容器日志 / Check Frontend Logs**
```bash
docker compose logs frontend --tail=50
```

**Step 3: 检查 Nginx 配置 / Check Nginx Config**
```bash
docker compose exec frontend nginx -t
```

**Step 4: 检查浏览器控制台 / Check Browser Console**
F12 → Console，查找 JavaScript 错误。

### 8.2 英文界面显示中文 / Wrong Language Display

**排查步骤 / Troubleshooting Steps:**

**Step 1: 确认语言设置 / Confirm Language Setting**
检查前端 URL 是否有语言参数：
- 英文：`/en/dashboard`
- 中文：`/zh/dashboard`

**Step 2: 检查 i18n 资源加载 / Check i18n Resources**
```bash
# 浏览器 Network 标签查看 locale 文件请求
# 应请求 /locales/en-US.json 或 /locales/zh-CN.json
```

**Step 3: 确认浏览器语言设置 / Confirm Browser Language**
浏览器语言首选应为 `en-US` 或 `zh-CN`。

---

## 9. 数据库问题 / Database Issues

### 9.1 数据库连接失败 / Database Connection Failed

**排查步骤 / Troubleshooting Steps:**

```bash
# Step 1: 检查 PostgreSQL 容器状态
docker compose ps db
# 状态应为 "healthy"

# Step 2: 检查连接字符串
docker compose exec app env | grep DATABASE

# Step 3: 手动连接测试
docker compose exec db psql -U accountscan -d accountscan -c "SELECT 1;"

# Step 4: 检查连接数
docker compose exec db psql -U accountscan -d accountscan -c \
  "SELECT count(*) FROM pg_stat_activity;"
```

### 9.2 数据库性能慢 / Database Slow

**排查步骤 / Troubleshooting Steps:**

```bash
# Step 1: 检查慢查询
docker compose exec db psql -U accountscan -d accountscan -c \
  "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Step 2: 检查索引
docker compose exec db psql -U accountscan -d accountscan -c \
  "SELECT indexrelname, idx_scan, idx_tup_read FROM pg_stat_user_indexes ORDER BY idx_scan ASC LIMIT 10;"

# Step 3: 调整 PostgreSQL 配置
# 编辑 docker-compose.yml 中的 postgres 容器环境变量：
environment:
  POSTGRES_MAX_CONNECTIONS: "200"
  POSTGRES_SHARED_BUFFERS: "256MB"
```

---

## 10. 日志收集方法 / Log Collection

### 10.1 收集完整诊断信息 / Collect Full Diagnostic Information

```bash
#!/bin/bash
# 诊断脚本 / Diagnostic Script

OUTPUT_DIR="/tmp/telos_diagnostics_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

# 1. 容器状态
docker compose ps > "$OUTPUT_DIR/01_container_status.txt"

# 2. 所有服务日志（最近 500 行）
docker compose logs --tail=500 > "$OUTPUT_DIR/02_all_logs.txt"

# 3. 数据库连接数
docker compose exec db psql -U accountscan -d accountscan -c \
  "SELECT count(*) FROM pg_stat_activity;" > "$OUTPUT_DIR/03_db_connections.txt"

# 4. 系统资源
df -h > "$OUTPUT_DIR/04_disk_usage.txt"
free -h > "$OUTPUT_DIR/05_memory_usage.txt"
uptime > "$OUTPUT_DIR/06_system_load.txt"

# 5. 网络连接
netstat -tlnp > "$OUTPUT_DIR/07_listening_ports.txt"
netstat -an | grep ESTABLISHED | wc -l > "$OUTPUT_DIR/08_active_connections.txt"

echo "Diagnostic data collected at: $OUTPUT_DIR"
tar -czf "/tmp/telos_diagnostics_$(date +%Y%m%d_%H%M%S).tar.gz" -C /tmp telos_diagnostics_*
```

### 10.2 实时日志监控 / Real-Time Log Monitoring

```bash
# 监控后端所有日志
docker compose logs -f app

# 监控后端 + 扫描相关日志
docker compose logs -f app | grep -E "scan|alert|analysis"

# 监控 Go 引擎日志（systemd 服务）
journalctl -u telos-engine -f

# 多服务同时监控
docker compose logs -f app scanner 2>/dev/null; journalctl -u telos-engine -f --no-pager
```

---

## 11. 错误代码速查 / Error Code Reference

### 11.1 前端错误代码 / Frontend Error Codes

| 错误代码 / Error Code | 描述 / Description | 建议操作 / Recommended Action |
|---------------------|-------------------|---------------------------|
| `NETWORK_ERROR` | 网络请求失败 | 检查网络连接和后端服务状态 |
| `401 UNAUTHORIZED` | 未登录或 Token 过期 | 重新登录 |
| `403 FORBIDDEN` | 权限不足 | 联系管理员申请权限 |
| `404 NOT_FOUND` | 请求的资源不存在 | 刷新页面确认资源是否存在 |
| `500 SERVER_ERROR` | 服务器内部错误 | 查看后端日志，联系支持 |
| `TIMEOUT` | 请求超时 | 检查后端性能和数据库状态 |

### 11.2 后端错误代码 / Backend Error Codes

| 错误码 / Error Code | HTTP 状态 / HTTP | 描述 / Description | 解决方案 / Solution |
|--------------------|:--------------:|-------------------|-------------------|
| `AUTH_INVALID_CREDENTIALS` | 401 | 用户名或密码错误 | 检查登录凭据 |
| `AUTH_TOKEN_EXPIRED` | 401 | Token 已过期 | 重新登录获取新 Token |
| `PERMISSION_DENIED` | 403 | 权限不足 | 确认用户角色和权限 |
| `ASSET_NOT_FOUND` | 404 | 资产不存在 | 确认资产 ID 是否正确 |
| `ASSET_CODE_EXISTS` | 409 | 资产编码已存在 | 使用唯一的资产编码 |
| `CONNECTION_FAILED` | 422 | 连接目标服务器失败 | 检查网络和凭据 |
| `CREDENTIAL_INVALID` | 422 | 凭据无效 | 重新配置正确凭据 |
| `SCAN_ALREADY_RUNNING` | 409 | 扫描正在运行 | 等待当前扫描完成或取消 |
| `ENGINE_UNAVAILABLE` | 503 | 分析引擎不可用 | 检查 telos-engine 服务状态（systemctl status telos-engine） |
| `DATABASE_ERROR` | 500 | 数据库错误 | 检查 PostgreSQL 状态和连接 |
| `VALIDATION_ERROR` | 400 | 请求参数校验失败 | 检查请求参数格式 |

### 11.3 数据库错误 / Database Errors

| 错误 / Error | 原因 / Cause | 解决 / Solution |
|------------|------------|----------------|
| `FATAL: password authentication failed` | 数据库密码错误 | 检查 `.env` 中的 `DB_PASSWORD` |
| `FATAL: database "accountscan" does not exist` | 数据库未创建 | 运行数据库迁移 `docker compose run app alembic upgrade head` |
| `FATAL: remaining connection slots are reserved` | 连接数达到上限 | 重启后端或调整 `DB_POOL_SIZE` |
| `ERROR: deadlock detected` | 死锁 | 等待自动回滚或重启服务 |
| `ERROR: duplicate key value` | 唯一索引冲突 | 检查数据唯一性约束 |

---

## 附录：联系技术支持 / Appendix: Contact Technical Support

如上述故障排查无法解决问题，请联系技术支持：

| 渠道 / Channel | 信息 / Information |
|--------------|------------------|
| 📧 邮件 / Email | support@telos.com |
| 📋 工单 / Ticket | https://support.telos.com |
| 📄 诊断包上传 / Upload Diagnostics | 上传第 10.1 节收集的诊断包 |
| 🕐 响应时间 / Response Time | 工作日 24 小时内 |

**收集诊断包时，请包含 / When collecting diagnostics, include:**
1. 容器状态 (`01_container_status.txt`)
2. 完整日志 (`02_all_logs.txt`)
3. 环境变量（脱敏后）(`.env` with secrets redacted)
4. 复现步骤描述（Step-by-step reproduction steps）

---

*Telos v2.0 | © 2026 Telos. All rights reserved.*
*Telos v2.0 | © 2026 Telos 版权所有。*
