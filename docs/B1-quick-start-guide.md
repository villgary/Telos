# Telos 快速开始指南
# Telos Quick Start Guide

> **预计完成时间 / Estimated Time**: 30 分钟
> **目标 / Goal**: 在本地环境完成安装、扫描第一台服务器、查看威胁分析结果
> **前提 / Prerequisites**: Docker 20.10+ 和 Docker Compose v2 已安装

---

## 目录 / Table of Contents

1. [环境准备 / Environment Preparation](#1-环境准备)
2. [下载与安装 / Download & Install](#2-下载与安装)
3. [配置环境变量 / Configure Environment Variables](#3-配置环境变量)
4. [启动服务 / Start Services](#4-启动服务)
5. [登录系统 / Log In](#5-登录系统)
6. [添加第一台资产 / Add Your First Asset](#6-添加第一台资产)
7. [执行首次扫描 / Run First Scan](#7-执行首次扫描)
8. [查看威胁分析结果 / View Threat Analysis Results](#8-查看威胁分析结果)
9. [配置告警 / Configure Alerts](#9-配置告警)
10. [下一步 / Next Steps](#10-下一步)

---

## 1. 环境准备 / Environment Preparation

### 1.1 系统要求 / System Requirements

| 项目 / Item | 最低要求 / Minimum | 推荐配置 / Recommended |
|-----------|------------------|---------------------|
| CPU | 4 核 | 8 核+ |
| 内存 / Memory | 8 GB | 16 GB+ |
| 磁盘 / Disk | 50 GB | 100 GB+ |
| 操作系统 / OS | Ubuntu 20.04+ / Debian 11+ / macOS 12+ | Ubuntu 22.04 LTS |
| Docker | 20.10+ | 24.0+ |
| Docker Compose | v2.0+ | v2.20+ |

### 1.2 检查 Docker 环境 / Check Docker Environment

```bash
docker --version
docker compose version
```

如果未安装，请参考 [Docker 官方安装文档](https://docs.docker.com/engine/install/)。

---

## 2. 下载与安装 / Download & Install

### 2.1 获取安装包 / Get Installation Package

```bash
# 方式一：从仓库克隆（推荐用于开发/测试）
git clone https://github.com/telos-project/telos.git
cd accountscan

# 方式二：下载发布版本压缩包
# 访问 https://github.com/telos-project/telos/releases 下载最新版本
# unzip accountscan-x.x.x.tar.gz
# cd accountscan-x.x.x
```

### 2.2 目录结构 / Directory Structure

```
accountscan/
├── docker-compose.yml      # 容器编排配置
├── Dockerfile             # 后端镜像构建
├── backend/               # Python FastAPI 后端
│   └── services/          # Go 分析引擎封装 (analysis_engine_go.py 等)
├── frontend/              # React 前端
│   └── Dockerfile
├── docs/                  # 文档
└── .env                   # 环境变量（需创建）
```

---

## 3. 配置环境变量 / Configure Environment Variables

### 3.1 创建环境变量文件 / Create Environment File

```bash
cp .env.example .env
```

### 3.2 配置必填参数 / Configure Required Parameters

编辑 `.env` 文件，填入以下必填参数：

```bash
# =============================================
# 必填参数 / REQUIRED PARAMETERS
# =============================================

# PostgreSQL 数据库密码
DB_PASSWORD=YourSecurePassword123

# 主密钥 - 用于加密存储凭据（AES-256-GCM）
# 生成方法：python -c "import secrets; print(secrets.token_hex(32))"
ACCOUNTSCAN_MASTER_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

# JWT 签名密钥 - 生成方法同上
ACCOUNTSCAN_JWT_SECRET=fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210

# =============================================
# 可选参数 / OPTIONAL PARAMETERS
# =============================================

# 前端端口（默认 3000）
FRONTEND_PORT=3000

# Go 扫描引擎地址（可选，高性能大规模扫描时启用）
# GO_SCANNER_URL=http://localhost:8081

# 邮件告警配置（可选）
# SMTP_HOST=smtp.example.com
# SMTP_PORT=587
# SMTP_USER=alerts@example.com
# SMTP_PASSWORD=your_smtp_password
```

### 3.3 生成安全密钥（推荐）/ Generate Secure Keys (Recommended)

```bash
python3 -c "import secrets; print('MASTER_KEY:', secrets.token_hex(32)); print('JWT_SECRET:', secrets.token_hex(32))"
```

---

## 4. 启动服务 / Start Services

### 4.1 启动所有服务 / Start All Services

```bash
docker compose up -d
```

### 4.2 等待服务就绪 / Wait for Services to be Ready

```bash
# 等待约 30 秒，检查所有容器状态
docker compose ps

# 检查后端健康状态
curl http://localhost:8000/health
# 期望输出：{"status":"ok","service":"accountscan",...}
```

**预期输出示例 / Expected Output:**
```
NAME                STATUS          PORTS
accountscan-db-1    healthy        5432/tcp
accountscan-redis-1 healthy        6379/tcp
accountscan-app-1  running        0.0.0.0:8000->8000/tcp
accountscan-frontend-1 running     0.0.0.0:3000->80/tcp
```

### 4.3 查看日志 / View Logs

```bash
# 查看所有服务日志
docker compose logs -f

# 仅查看后端日志
docker compose logs -f app

# 仅查看前端日志
docker compose logs -f frontend
```

---

## 5. 登录系统 / Log In

### 5.1 访问 Web 界面 / Access Web UI

打开浏览器访问：**http://localhost:3000**

### 5.2 默认账户 / Default Credentials

| 用户名 / Username | 密码 / Password | 角色 / Role |
|----------------|-----------------|------------|
| `admin` | `Admin123!` | 管理员 / Administrator |

> ⚠️ **重要 / IMPORTANT**: 生产环境部署后请立即修改默认密码。
> **Change the default password immediately after production deployment.**

### 5.3 语言切换 / Language Switch

登录后点击右上角语言下拉框，在 **中文** 和 **English** 之间切换。

---

## 6. 添加第一台资产 / Add Your First Asset

### 6.1 进入资产管理 / Navigate to Asset Management

左侧菜单 → **资产管理** → **资产列表**

### 6.2 添加服务器资产 / Add a Server Asset

点击 **添加资产** 按钮，填写以下信息：

| 字段 / Field | 示例值 / Example | 说明 |
|-------------|-----------------|------|
| 资产名称 / Name | `web-server-01` | 便于识别的名称 |
| 资产编码 / Code | `WEB01` | 唯一编码 |
| IP 地址 / IP Address | `192.168.1.100` | 服务器 IP |
| 操作系统 / OS Type | `Linux` | Linux 或 Windows |
| 类别 / Category | `Server / Linux` | 选择对应分类 |
| 凭据 / Credential | 选择已添加的凭据或新建 | SSH 连接凭据 |

### 6.3 添加 SSH 连接凭据 / Add SSH Credential

1. 进入 **系统** → **凭据管理**
2. 点击 **添加凭据**
3. 选择类型 **SSH**
4. 填入用户名和密码或 SSH 私钥
5. 点击 **测试连接** 验证连通性

### 6.4 验证连接 / Verify Connection

添加资产时或添加后，点击 **测试连接** 按钮，确保能成功 SSH 到目标服务器。

---

## 7. 执行首次扫描 / Run First Scan

### 7.1 发起扫描 / Trigger a Scan

两种方式发起扫描：

**方式一：从资产列表扫描**
1. 进入 **资产管理** → **资产列表**
2. 勾选要扫描的资产（可多选）
3. 点击 **扫描** 按钮

**方式二：从扫描作业扫描**
1. 进入 **扫描作业** → **扫描任务**
2. 点击 **新建扫描**
3. 选择目标资产（可按组/类别筛选）
4. 点击 **开始扫描**

### 7.2 查看扫描进度 / Monitor Scan Progress

扫描作业页面实时显示：
- 扫描状态（进行中/已完成/失败）
- 发现账号数量
- 扫描耗时
- 发现的账号列表（用户名、UID、是否管理员）

### 7.3 首次扫描预期结果 / Expected Results After First Scan

| 指标 / Metric | 说明 |
|--------------|------|
| 账号数量 | 目标服务器上的所有系统账号和普通账号 |
| 管理员账号 | 具有 sudo 权限的账号 |
| 特权账号 | UID=0 或 sudo权限组内成员 |
| 危险配置 | NOPASSWD sudo、空密码、SSH 密钥复用等 |

---

## 8. 查看威胁分析结果 / View Threat Analysis Results

### 8.1 身份威胁分析 / Identity Threat Analysis

路径：**AI 分析** → **身份威胁分析**

- **全局分析**：对所有资产执行五层威胁分析
- **ATT&CK 覆盖率**：查看 MITRE ATT&CK 框架映射结果

**五层分析模型 / Five-Layer Analysis Model:**

| 层级 | 名称 | 检测内容 |
|------|------|---------|
| Layer 1 | 符号层 Semiotics | 字符伪装、匿名命名、符号模仿 |
| Layer 2 | 本体层 Ontology | 影子账号、角色混淆、孤立孤儿账号 |
| Layer 3 | 认知层 Cognitive | 确认偏差、光环效应、正常化偏差 |
| Layer 4 | 人类学层 Anthropology | 信任链、权限簇、身份隔离 |
| Layer 5 | 因果层 Causal | 权限提升路径、因果中枢、沉睡特权链 |

### 8.2 ATT&CK 覆盖率 / ATT&CK Coverage

路径：**ATT&CK 覆盖率**

查看：
- **Risk Summary（风险摘要）**：按严重性分类的高风险信号
- **Technique Details（技术详情）**：按 MITRE ATT&CK 技术分组的详细信号

可导出 ATT&CK Navigator Layer JSON 文件，导入 [https://mitre-attack.github.io/attack-navigator/](https://mitre-attack.github.io/attack-navigator/) 可视化。

### 8.3 仪表盘 / Dashboard

路径：**仪表盘**

查看全局风险评分、账号统计、告警趋势等关键指标。

---

## 9. 配置告警 / Configure Alerts

### 9.1 告警中心 / Alert Center

路径：**安全运营** → **告警中心**

支持以下告警类型：
- 新增管理权限
- 新增 NOPASSWD sudo 权限
- 发现敏感凭据泄露
- 休眠账号重新激活
- 孤儿特权账号

### 9.2 Webhook 告警配置 / Configure Webhook Alerts

1. 进入 **系统** → **系统设置** → **告警配置**
2. 选择告警类型（新增管理权限、NOPASSWD sudo、敏感凭据泄露等）
3. 添加 Webhook URL（如：飞书机器人 / Slack / SOAR 接收端）
4. 点击 **测试** 验证推送是否到达

**飞书机器人示例 URL：**
```
https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxxxx
```

### 9.3 邮件告警配置 / Configure Email Alerts

在 `.env` 中配置 SMTP 参数后，重启服务：

```bash
docker compose restart app
```

---

## 10. 下一步 / Next Steps

恭喜完成快速开始！以下文档帮助深入使用：

| 文档 | 说明 |
|------|------|
| [安装部署手册](./B4-installation-guide.md) | 生产环境部署、高可用、备份恢复 |
| [管理员手册](./B3-admin-guide.md) | 用户管理、策略配置、告警规则 |
| [用户手册](./B2-user-guide.md) | 日常运营操作手册 |
| [API 参考文档](./B5-api-reference.md) | API 接口文档 |

### 建议的后续步骤 / Recommended Next Steps

1. ✅ 添加更多资产，构建完整账号清单
2. ✅ 配置定时扫描，自动发现账号变更
3. ✅ 查看 ATT&CK 覆盖率，了解当前威胁态势
4. ✅ 配置 Webhook 告警，接入现有安全运营体系
5. ✅ 设置合规检查（SOC2 / ISO27001 / 等保2.0）
6. ✅ 探索 NHI 非人类身份管理

---

## 常见问题 / FAQ

**Q: 扫描失败，提示"连接超时"**
A: 检查目标服务器防火墙是否放行 SSH 端口（默认 22），确认凭据正确。

**Q: 告警没有触发**
A: 检查告警类型是否在"实时监控"范围内，确认通知渠道已配置。

**Q: 前端加载慢或白屏**
A: 检查浏览器控制台错误，确认后端服务（8000端口）正常运行。

**Q: 如何查看详细日志？**
A: `docker compose logs -f app` 查看后端日志；`docker compose logs -f frontend` 查看前端日志。

**Q: 如何配置定时自动扫描？**
A:
1. 进入 **扫描作业** → **扫描计划**
2. 点击 **添加计划**
3. 选择目标资产（可按分组或全量）
4. 配置 Cron 表达式（如 `0 3 * * *` = 每天凌晨 3 点）
5. 选择扫描类型（增量 / 全量）
6. 保存并启用

```bash
# Cron 表达式示例：
# 每天凌晨 3 点:    0 3 * * *
# 每周一凌晨 2 点:  0 2 * * 1
# 每季度第一天 9 点: 0 9 1 1,4,7,10 *
```

---

## 技术支持 / Support

- 文档：[https://docs.telos.com](https://docs.telos.com)
- 邮件：support@telos.com
- GitHub Issues：[https://github.com/telos-project/telos/issues](https://github.com/telos-project/telos/issues)

---

*Telos v2.0 | © 2026 Telos*
