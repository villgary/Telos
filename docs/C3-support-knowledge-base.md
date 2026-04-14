# Telos 支持知识库
# Telos Support Knowledge Base

> **适用范围 / Audience**: 技术支持团队 / 客户自助
> **版本 / Version**: v2.0 | 中英双语

---

## 目录 / Table of Contents

1. [FAQ 常见问题 / Frequently Asked Questions](#1-faq-常见问题)
2. [错误代码速查 / Error Code Quick Reference](#2-错误代码速查)
3. [最佳实践 / Best Practices](#3-最佳实践)
4. [配置模板库 / Configuration Templates](#4-配置模板库)
5. [场景化排查指南 / Scenario-Based Troubleshooting](#5-场景化排查指南)

---

## 1. FAQ 常见问题 / Frequently Asked Questions

### 1.1 安装部署类 / Installation & Deployment

**Q1: Docker Compose 启动时报 `port is already allocated`，如何解决？**

**A:**
端口已被其他服务占用。有两种解决方案：

**方案一：修改 Telos 端口**
```bash
# 编辑 .env 文件
FRONTEND_PORT=3001    # 改为 3001
PORT=8001            # 改为 8001

# 重启
docker compose down && docker compose up -d
```

**方案二：停止占用端口的服务**
```bash
# 查找占用端口的进程
netstat -tlnp | grep :3000

# 停止对应服务后重启 Telos
docker compose up -d
```

---

**Q2: 后端启动后立即退出，提示数据库连接失败？**

**A:**
PostgreSQL 需要约 30 秒完成初始化。执行以下步骤：

```bash
# 1. 确认数据库容器已就绪
docker compose ps db
# 确认状态为 "healthy"

# 2. 等待 60 秒后重启后端
sleep 60 && docker compose restart app

# 3. 检查日志确认
docker compose logs app | grep -i "startup"
```

如果问题持续，检查数据库连接字符串：
```bash
docker compose exec app env | grep DATABASE
```

---

**Q3: 如何修改默认管理员密码？**

**A:**
**通过前端修改（推荐）：**
1. 右上角用户菜单 → 个人设置 → 修改密码
2. 输入旧密码和新密码
3. 点击保存

**通过 API 修改：**
```bash
curl -X POST http://localhost:8000/api/v1/users/{user_id}/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"old_password": "old123", "new_password": "NewPass123!"}'
```

---

**Q4: 是否支持离线安装？**

**A:**
支持。所有 Docker 镜像可以导出后在离线环境导入：

```bash
# 在有网络环境导出
docker save -o telos_images.tar \
  telos-app:latest telos-frontend:latest telos-db:latest telos-redis:latest

# 在离线环境导入
docker load -i telos_images.tar
```

---

**Q5: 如何配置 HTTPS？**

**A:**
**方案一：使用 Nginx 反向代理（推荐）：**
```nginx
# /etc/nginx/conf.d/telos.conf
server {
    listen 443 ssl;
    server_name telos.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**方案二：使用 Let's Encrypt 自动证书：**
```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d telos.yourdomain.com
```

---

### 1.2 扫描类 / Scanning

**Q6: 扫描提示"连接超时"，但 ping 通目标服务器？**

**A:**
SSH 端口可能被防火墙阻断，即使 ICMP（ping）正常：

```bash
# 测试 SSH 端口（Linux 默认 22）
nc -zv 192.168.1.100 22

# 测试 WinRM 端口（Windows 默认 5985/5986）
nc -zv 192.168.1.101 5985
```

**解决方案：**
1. 在目标服务器开放 Telos 服务器 IP 的 SSH 端口（22）
2. 或者在 Telos 服务器配置 SSH 跳板

---

**Q7: 扫描只发现了部分账号？**

**A:**
可能原因及解决方案：

**原因 1：增量扫描 vs 全量扫描**
- 增量扫描只报告上次扫描后新增/变更的账号
- 首次扫描请使用**全量扫描**

**原因 2：扫描账号权限不足**
- 扫描账号需要有读取 `/etc/passwd` 和 `/etc/shadow` 的权限
- 使用 `sudo` 权限扫描账号（需要将扫描账号加入 sudoers 或使用 NOPASSWD）

**原因 3：使用了 LDAP/NIS**
- 如果系统使用 LDAP 统一认证，本地 `/etc/passwd` 不包含所有账号
- 需要额外配置 LDAP 扫描插件

---

**Q8: 如何扫描 Windows 服务器？**

**A:**
**前提条件：**
1. Windows 服务器开启 WinRM 服务（PowerShell）：
   ```powershell
   Enable-PSRemoting -Force
   ```
2. 防火墙开放 5985（HTTP）或 5986（HTTPS）端口
3. 在 Telos 中创建 Windows 凭据（用户名+密码+域）

**添加 Windows 资产：**
1. 资产管理 → 添加资产
2. 操作系统选择 `Windows`
3. 选择或创建 Windows 凭据
4. 保存后执行扫描

---

**Q9: 如何扫描云平台（AWS/阿里云/腾讯云）账号？**

**A:**
**AWS:**
1. 创建 IAM 用户，授予 `ReadOnlyAccess` 或更精细的权限
2. 生成 Access Key 和 Secret Key
3. 在 Telos 凭据管理中添加"云平台凭据"
4. 添加云资产，选择 `Cloud / AWS` 类别

**阿里云 RAM:**
1. 创建 RAM 用户，授予 `AliyunRAMReadOnlyAccess` 权限
2. 在 Telos 凭据中添加阿里云 AccessKey

---

**Q10: 扫描是否支持 SSH 密钥认证？**

**A:**
是的，完全支持：

1. 在 Telos **凭据管理**中添加 SSH 密钥凭据
2. 粘贴私钥内容（`-----BEGIN OPENSSH PRIVATE KEY-----` 开头）
3. 如果私钥有密码短语（Passphrase），填入对应字段
4. 测试连接后保存
5. 在资产配置中关联该凭据

**私钥权限要求：**
```bash
# 确保私钥文件权限为 600
chmod 600 /path/to/private_key
```

---

### 1.3 分析与告警类 / Analysis & Alerts

**Q11: 为什么五层分析结果为空？**

**A:**
**必须先执行扫描！** 分析引擎对扫描结果进行分析，如果没有扫描数据，分析结果自然为空。

**正确步骤：**
1. ✅ 资产列表 → 选择资产 → 执行扫描
2. ✅ 等待扫描完成（账号数量 > 0）
3. ✅ AI 分析 → 选择分析范围 → 开始分析
4. ✅ 查看分析结果

---

**Q12: 告警没有触发，如何排查？**

**A:**
按以下优先级检查：

**Step 1: 确认告警类型已启用**
- 系统设置 → 告警配置 → 确认对应告警类型已开启

**Step 2: 确认通知渠道已配置**
- Webhook 需要 URL
- 邮件需要 SMTP 配置

**Step 3: 检查 Webhook 日志**
```bash
docker compose logs app | grep -i "webhook\|alert" | tail -20
```

**Step 4: 手动触发测试告警**
```bash
# 在前端：系统设置 → 测试告警 → 发送测试邮件
```

---

**Q13: 如何导出 ATT&CK Navigator Layer 文件？**

**A:**
**步骤：**
1. AI 分析 → 执行一次全局分析
2. ATT&CK 覆盖率页面
3. 点击右上角**导出 Layer**
4. 下载 JSON 文件
5. 打开 https://mitre-attack.github.io/attack-navigator/
6. 点击 **+ Layer** → **Upload Layer** → 上传 JSON 文件

---

**Q14: 告警去重规则是什么？**

**A:**
- **时间窗口：** 同一资产的同一告警类型，30 分钟内不重复触发
- **告警内容：** 标题相同的告警会被去重
- **变更检测：** 如果告警条件在 30 分钟内持续存在，新告警会在窗口结束后再次触发

---

**Q15: 如何配置邮件告警？**

**A:**
**Step 1: 在 .env 中配置 SMTP**
```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=alerts@example.com
SMTP_PASSWORD=your-smtp-password
```

**Step 2: 重启后端使配置生效**
```bash
docker compose restart app
```

**Step 3: 测试邮件发送**
- 前端：系统设置 → 通知配置 → 发送测试邮件

---

### 1.4 NHI 管理类 / NHI Management

**Q16: 如何区分服务账号和普通用户账号？**

**A:**
Telos 自动根据以下规则分类：

| 规则 / Rule | 分类结果 / Classification |
|------------|----------------------|
| UID < 100（Linux）或 SID 内置（Windows）| System Account |
| Shell = `/sbin/nologin` 或 `/bin/false` | System Account |
| 无个人归属人关联 | NHI（Service Account）|
| Owner 为系统邮箱或服务名 | NHI |
| 数据库用户名 | NHI（Database Account）|
| 云平台 Access Key 关联 | NHI（Cloud IAM）|

**手动调整：**
- NHI 详情页 → 编辑 → 选择正确的 NHI 类型
- 支持批量修改 NHI 类型

---

**Q17: NHI 轮换提醒是什么意思？**

**A:**
轮换提醒基于凭证的创建/轮换时间自动计算：

```
轮换提醒 = 当前日期 - 最后轮换日期 >= 轮换周期
```

**配置方法：**
- NHI 列表 → 选择 NHI → 编辑
- 设置**轮换周期**（天数）
- 系统自动计算距下次轮换的剩余天数
- 剩余 ≤ 30 天触发告警

---

### 1.5 合规类 / Compliance

**Q18: SOC2 合规评估需要多久执行一次？**

**A:**
建议频率：

| 评估类型 / Assessment Type | 建议频率 / Recommended Frequency |
|--------------------------|-------------------------------|
| 全量 SOC2 评估 / Full SOC2 | 每季度（90 天）|
| 特权账号专项 / Privileged account | 每月（30 天）|
| 合规报告生成 / Report generation | 与评估同步 |
| 实时告警监控 / Real-time monitoring | 持续（7×24 小时）|

---

**Q19: 等保 2.0 中哪些控制项 Telos 可以自动化？**

**A:**
| 等保 2.0 控制项 / Control | Telos 功能 / Telos Function |
|-----------------------|--------------------------|
| DBAP_TS（离线资产特权账号）| 资产扫描 + 特权账号发现 |
| DBAP_OA（静默管理员账号）| 孤儿账号检测 |
| CC6.3（长期不活跃特权账号）| 账号生命周期管理 |
| A.9.2.3（无密码 sudo）| NOPASSWD sudo 检测 |
| 安全审计（身份标识与鉴别）| 账号发现 + 审计日志 |

---

### 1.6 性能类 / Performance

**Q20: 扫描速度很慢，如何优化？**

**A:**
**Step 1: 确认单次 SSH 连接时间**
```bash
time ssh -o ConnectTimeout=10 user@target "echo ok"
# 如果 > 5 秒，说明网络延迟大
```

**Step 2: 调整扫描并发数**
```bash
# .env
SCAN_CONCURRENCY=20   # 默认 5，可提高到 20-50
docker compose restart app
```

**Step 3: 启用 Go 分析引擎（大规模）**
```bash
# Go 引擎通过 systemd 运行（/etc/systemd/system/telos-engine.service）
# 确认服务运行中
sudo systemctl status telos-engine

# 配置后端连接地址
echo "GO_ANALYSIS_ENGINE_URL=http://localhost:8082" >> .env
docker compose restart app
```

---

**Q21: 前端加载很慢？**

**A:**
**可能原因及解决方案：**

**原因 1：后端性能问题**
```bash
time curl -w "\n" http://localhost:8000/api/v1/assets 2>&1 | grep "time_total"
# 应 < 1 秒
```

**原因 2：Redis 缓存未命中**
```bash
docker compose exec redis redis-cli ping
# 应返回 PONG
```

**原因 3：数据量太大**
- 告警/账号列表分页参数：`page_size=20`（不要一次加载太多）

---

### 1.7 集成类 / Integration

**Q22: 如何与 Splunk 集成？**

**A:**
**方案：通过 Webhook 推送告警到 Splunk HEC**
1. Splunk 配置 HEC（HTTP Event Collector）端点
2. 在 Telos 系统设置 → Webhook → 添加：
   - URL: `https://your-splunk:8088/services/collector`
   - Token: 你的 HEC Token
   - Header: `Authorization: Splunk <YOUR_TOKEN>`
3. 测试并保存

---

**Q23: 如何与飞书/企业微信集成？**

**A:**
**飞书（Feishu）：**
1. 创建飞书自建应用，获取 App ID 和 App Secret
2. 配置 Webhook Bot
3. 在 Telos Webhook 中配置：
   ```json
   {
     "url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx",
     "events": ["alert.created"]
   }
   ```

**企业微信（WeCom）：**
1. 创建企业微信群机器人
2. 获取 Webhook URL
3. 配置 Telos Webhook 指向该 URL

---

**Q24: 是否支持 SSO 登录？**

**A:**
**当前版本（v2.0）支持：**
- LDAP / Active Directory 用户认证
- SAML 2.0（计划中）
- OIDC（计划中）

**LDAP 集成配置：**
```bash
# .env
LDAP_URL=ldap://your-ldap-server:389
LDAP_BASE_DN="dc=company,dc=com"
LDAP_BIND_DN="cn=admin,dc=company,dc=com"
LDAP_BIND_PASSWORD=xxx
LDAP_USER_SEARCH_BASE="ou=users,dc=company,dc=com"
```

---

## 2. 错误代码速查 / Error Code Quick Reference

### 2.1 快速错误对照表 / Quick Error Reference

> ⚠️ Telos v2.0 后端 API 返回 **描述性错误码**（如 `AUTH_INVALID_CREDENTIALS`），与旧版 E码（如 `E1001`）的对应关系如下：

| 描述性错误码 (v2.0 API) | 旧码 | 说明 / Description | 一句话解决方案 / Quick Fix |
|------------------------|------|------------------|------------------------|
| `AUTH_INVALID_CREDENTIALS` | E1002 | 认证失败 | 确认用户名/密码正确 |
| `AUTH_TOKEN_EXPIRED` | E1002 | Token 过期 | 重新登录获取新 Token |
| `PERMISSION_DENIED` | E1003 | 权限不足 | 联系管理员确认角色权限 |
| `ASSET_NOT_FOUND` | E1001 | 资产不存在 | 确认资产 ID 是否正确 |
| `ASSET_CODE_EXISTS` | E1001 | 资产编码重复 | 使用唯一的资产编码 |
| `CONNECTION_FAILED` | E1001 | 连接超时/拒绝 | 检查网络、防火墙、目标服务 |
| `CREDENTIAL_INVALID` | E1002 | 凭据无效 | 重新配置正确凭据 |
| `SCAN_ALREADY_RUNNING` | E1001 | 扫描任务冲突 | 等待当前扫描完成或取消 |
| `ENGINE_UNAVAILABLE` | E3001 | 分析引擎不可用 | 检查 Go 引擎服务（`systemctl status telos-engine`） |
| `DATABASE_ERROR` | E2001 | 数据库错误 | 检查 PostgreSQL 状态 |
| `VALIDATION_ERROR` | E4002 | 参数校验失败 | 检查请求参数格式 |
| — | E2002 | 数据库连接数满 | 重启后端或调高 `max_connections` |
| — | E4001 | Webhook 推送失败 | 检查 Webhook URL 网络可达性 |
| — | E5001 | 磁盘空间不足 | 清理日志/备份，扩展磁盘 |
| — | E5002 | 内存不足 | 增加宿主机内存或调低并发数 |

### 2.2 日志关键词搜索 / Log Keyword Search

| 搜索关键词 / Search | 相关问题 / Related Issue |
|-----------------|----------------------|
| `connection refused` | 连接被拒绝，检查服务端口 |
| `authentication failed` | 凭据错误 |
| `permission denied` | 权限不足 |
| `deadlock detected` | 数据库死锁，通常自动恢复 |
| `out of memory` | OOM，增加内存 |
| `connection pool exhausted` | 连接池耗尽，重启后端 |
| `certificate verify failed` | SSL 证书问题 |

---

## 3. 最佳实践 / Best Practices

### 3.1 安全配置 / Security Configuration

**✅ 推荐：最小权限扫描账号**
```bash
# 创建专用扫描账号，仅授予必要权限
useradd -m -s /bin/bash scanner
echo "scanner ALL=(ALL) NOPASSWD: /usr/bin/getent, /usr/bin/cat /etc/passwd, /usr/bin/cat /etc/shadow" | sudo tee /etc/sudoers.d/scanner
```

**✅ 推荐：启用 TLS**
- 生产环境务必使用 HTTPS
- 使用 Let's Encrypt 自动证书或商业证书
- 定期更新证书

**✅ 推荐：定期轮换密钥**
- `ACCOUNTSCAN_MASTER_KEY` 定期轮换（建议每 90 天）
- SSH 扫描密钥定期轮换（建议每 180 天）
- 云平台 Access Key 启用自动轮换

### 3.2 扫描配置 / Scanning Configuration

**✅ 推荐：增量扫描优先**
- 日常扫描使用**增量扫描**（更快、更精准）
- 每周或每月执行一次**全量扫描**

**✅ 推荐：定时扫描避开业务高峰**
```cron
# 每天凌晨 3 点执行增量扫描
0 3 * * * curl -X POST http://localhost:8000/api/v1/scans -d '{"scan_type":"incremental"}'
```

**✅ 推荐：分类扫描策略**
```json
{
  "schedules": [
    { "category": "server/linux", "frequency": "daily", "scan_type": "incremental" },
    { "category": "database", "frequency": "weekly", "scan_type": "full" },
    { "category": "cloud/aws", "frequency": "daily", "scan_type": "incremental" }
  ]
}
```

### 3.3 告警管理 / Alert Management

**✅ 推荐：分级告警通知**
- 🔴 严重告警：邮件 + Webhook + 短信
- 🟠 高危告警：邮件 + Webhook
- 🟡 中危告警：仅 Webhook（聚合）
- 🔵 低危告警：仅记录，不通知

**✅ 推荐：告警静默规则**
- 计划内维护窗口：设置静默规则
- 误报率高的告警：评估后调整检测规则或标记为误报

### 3.4 合规管理 / Compliance Management

**✅ 推荐：合规评估与告警联动**
- SOC2 CC6.3（不活跃特权账号）：触发后自动创建工单
- NOPASSWD 检测：立即通知 + 自动生成修复建议

**✅ 推荐：报告自动化**
- 每月自动生成特权账号报告，发送给安全管理员
- 季度评估自动执行，报告归档

---

## 4. 配置模板库 / Configuration Templates

### 4.1 Webhook 飞书配置模板 / Feishu Webhook Template

```json
{
  "name": "飞书告警",
  "url": "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_ID",
  "events": [
    "alert.created"
  ],
  "custom_headers": {
    "Content-Type": "application/json"
  }
}
```

### 4.2 Webhook Slack 配置模板 / Slack Webhook Template

```json
{
  "name": "Slack 告警",
  "url": "https://hooks.slack.com/services/XXX/YYY/ZZZ",
  "events": [
    "alert.created",
    "alert.critical"
  ],
  "template": {
    "text": "🔴 *{{level}} Alert*: {{title}}\n资产: {{asset_name}}\n时间: {{created_at}}"
  }
}
```

### 4.3 合规检查阈值配置 / Compliance Threshold Config

```json
{
  "thresholds": {
    "privileged_account_inactive_days": 90,
    "dormant_account_days": 180,
    "shared_admin_account_threshold": 3,
    "sudo_config_risk_rules": {
      "nopasswd": "critical",
      "ALL_ALL": "high",
      "sudo_without_tty": "medium"
    },
    "lifecycle_thresholds": {
      "default": { "active_days": 90, "departed_days": 180 },
      "database": { "active_days": 180, "departed_days": 365 },
      "cloud_iam": { "active_days": 60, "departed_days": 90 }
    }
  }
}
```

### 4.4 NHI 轮换周期建议 / NHI Rotation Period Recommendations

| NHI 类型 / NHI Type | 建议轮换周期 / Recommended Rotation Period | 说明 / Note |
|-------------------|-----------------------------------------|------------|
| API Key（高危）| 90 天 | 建议启用自动轮换 |
| API Key（中危）| 180 天 | 定期检查使用情况 |
| Service Account | 365 天 | 结合服务变更时轮换 |
| CI/CD Credential | 90 天 | Pipeline 变更时强制轮换 |
| 数据库账号 | 180 天 | 应用重启时轮换 |
| SSH 密钥 | 180 天 | 人员离职时必须轮换 |
| 云 Access Key | 90 天 | 启用云平台自动轮换 |

---

## 5. 场景化排查指南 / Scenario-Based Troubleshooting

### 场景 A：攻防演练前准备 / Red Team Exercise Preparation

**目标：** 2 天内完成所有资产梳理和风险评估

```
Day 1:
├── Step 1: 快速安装部署 Telos（4 小时）
│   └── Docker Compose 一键部署
├── Step 2: 批量导入资产（2 小时）
│   ├── 从 CSV 导入
│   └── 配置 SSH 跳板（如有）
├── Step 3: 全量扫描（4 小时）
│   └── 全部资产执行全量扫描
└── Step 4: 初始威胁分析（2 小时）
    └── 执行全局分析，导出 ATT&CK Navigator Layer

Day 2:
├── Step 5: 重点资产二次扫描（持续）
│   └── 核心服务器每日增量扫描
├── Step 6: 告警配置（4 小时）
│   ├── 配置 Webhook 推送
│   └── 配置实时监控
└── Step 7: 演练当日实时监控
    └── 大屏监控 + 告警实时推送
```

### 场景 B：等保 2.0 合规评估 / GB/T 22239-2019 Assessment

**目标：** 1 周内完成合规评估并生成报告

```
Day 1-2: 资产扫描
├── 全量扫描所有资产
├── 导出账号清单
└── 识别特权账号基线

Day 3: 风险分析
├── 执行五层威胁分析
├── 识别高危账号和配置
└── ATT&CK 覆盖率评估

Day 4-5: 合规评估
├── 执行 SOC2/等保 2.0 评估
├── 逐项核对控制要求
└── 记录不符合项

Day 6-7: 报告与整改
├── 生成合规报告
├── 制定整改计划
└── 整改后重新评估
```

### 场景 C：凭据泄露应急响应 / Credential Leak Incident Response

**发现阶段（0-30 分钟）：**
```
1. 收到"发现敏感凭据泄露"告警
2. 确认泄露的凭据类型和范围
3. 评估影响资产数量
```

**控制阶段（30 分钟 - 2 小时）：**
```
4. 立即禁用相关账号或轮换凭据
5. 执行受影响资产的紧急扫描
6. 查看告警详情中的 ATT&CK 信号
7. 如果有横向移动告警，立即隔离相关资产
```

**恢复阶段（2 小时 - 1 天）：**
```
8. 清理攻击者创建的账号
9. 恢复被修改的配置（sudoers、authorized_keys）
10. 全局扫描确保无遗留
11. 生成事件报告
12. 复盘并加固（配置告警规则，防止再次发生）
```

---

## 联系技术支持 / Contact Technical Support

| 渠道 / Channel | 信息 / Information |
|--------------|------------------|
| 📧 邮件 / Email | support@telos.com |
| 📋 工单 / Ticket | https://support.telos.com |
| 📞 电话 / Phone | 400-XXX-XXXX（工作日 9:00-18:00）|
| 🕐 紧急支持 / 24/7 Critical | emergency@telos.com |

**联系时请提供 / When contacting support, please provide:**
1. 您的客户编号（Customer ID）
2. 问题描述和复现步骤
3. 诊断日志（使用巡检脚本收集）
4. 相关截图（如有 UI 问题）

---

*Telos v2.0 | © 2026 Telos. All rights reserved.*
*Telos v2.0 | © 2026 Telos 版权所有。*
