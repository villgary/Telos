# Telos 管理员手册
# Telos Administrator Guide

> **适用范围 / Audience**: 安全管理员、系统管理员，负责系统配置、用户管理、告警规则、策略管理等
> **版本 / Version**: v2.0

---

## 目录 / Table of Contents

1. [系统管理概览 / System Management Overview](#1-系统管理概览)
2. [资产管理配置 / Asset Management Configuration](#2-资产管理配置)
3. [用户与权限 / Users & Permissions](#3-用户与权限)
4. [凭据管理 / Credential Management](#4-凭据管理)
5. [告警配置 / Alert Configuration](#5-告警配置)
6. [策略管理 / Policy Management](#6-策略管理)
7. [处置剧本 / Remediation Playbooks](#7-处置剧本)
8. [特权审查 / Privileged Review](#8-特权审查)
9. [特权访问管理集成 / PAM Integration](#9-特权访问管理集成)
10. [AI 模型配置 / AI Model Configuration](#10-ai-模型配置)
11. [系统设置 / System Settings](#11-系统设置)

---

## 1. 系统管理概览 / System Management Overview

### 1.1 管理员职责 / Admin Responsibilities

| 职责 | 频率 | 重要度 |
|------|------|--------|
| 用户账户管理 | 按需 | ⭐⭐⭐ |
| 扫描配置与调度 | 初始配置+按需 | ⭐⭐⭐ |
| 告警规则配置 | 初始配置+定期审查 | ⭐⭐⭐ |
| 策略管理 | 初始配置+按需 | ⭐⭐ |
| PAM 集成配置 | 初始配置 | ⭐⭐ |
| 系统升级维护 | 按版本 | ⭐⭐ |
| 数据备份 | 每日/每周 | ⭐⭐⭐ |

### 1.2 初始安装后检查清单 / Post-Installation Checklist

- [ ] 修改默认管理员密码（admin/Admin123!）
- [ ] 添加其他管理员账户（至少 2 名）
- [ ] 配置 SMTP 邮件通知
- [ ] 配置 Webhook 告警（如有 SOC/SIEM 集成）
- [ ] 添加第一批被扫描资产
- [ ] 执行首次全量扫描
- [ ] 运行首次全局威胁分析
- [ ] 配置定时扫描计划
- [ ] 配置合规评估计划（SOC2/ISO27001）
- [ ] 确认告警正常推送

---

## 2. 资产管理配置 / Asset Management Configuration

### 2.1 资产类别管理 / Asset Categories

路径：**资产管理 → 资产类别**

资产类别决定扫描引擎的路由：
- 每个类别对应一个**扫描插件**（Linux SSH / Windows WinRM / 数据库连接 / 云 API）
- 类别slug 唯一，确定后不可修改

**创建自定义类别：**
1. 点击**添加类别**
2. 填写类别名称、slug（英文，用于系统识别）
3. 选择父类别（如有层级）
4. 设置该类别的**沉睡阈值**（天数）
5. 保存

### 2.2 资产分组 / Asset Groups

路径：**资产管理 → 资产分组**

使用分组对资产进行逻辑组织：
- 支持颜色标签
- 支持按分组批量扫描
- 建议按业务系统/部门/环境（生产/测试）分组

### 2.3 资产拓扑关系 / Asset Relationships

路径：**资产管理 → 资产拓扑**

配置资产间的层级关系（父子关系），用于**风险传播**：
- 子资产的高风险可传播到父资产
- 父子关系支持：物理包含（机架→服务器）、服务依赖（数据库→应用）

---

## 3. 用户与权限 / Users & Permissions

路径：**系统 → 用户管理**

### 3.1 角色定义 / Role Definitions

| 角色 | 可执行操作 |
|------|-----------|
| **管理员 / Admin** | 全部操作，包括用户管理、系统配置 |
| **运营员 / Operator** | 资产管理、扫描、分析、告警响应 |
| **查看者 / Viewer** | 只读，不能修改任何内容 |

### 3.2 创建用户 / Create User

1. 进入**用户管理**
2. 点击**添加用户**
3. 填写：用户名（唯一）、密码、角色、邮箱（可选）
4. 点击**保存**

### 3.3 修改密码（管理员） / Change Password (Admin)

管理员可为任何用户重置密码：
1. 用户管理列表点击用户右侧**操作**→**重置密码**
2. 系统生成随机密码并显示（请立即告知用户）
3. 用户首次登录后强制修改密码

---

## 4. 凭据管理 / Credential Management

路径：**系统 → 凭据管理**

### 4.1 凭据类型 / Credential Types

| 类型 | 用途 | 字段 |
|------|------|------|
| **SSH 用户名+密码** | Linux SSH 连接 | Username, Password |
| **SSH 密钥对** | Linux SSH 连接（密钥认证）| Username, Private Key, Passphrase（可选）|
| **Windows 凭据** | WinRM 连接 | Username, Domain, Password |
| **数据库凭据** | 数据库扫描 | Username, Password |

### 4.2 添加 SSH 密钥凭据 / Add SSH Key Credential

1. 点击**添加凭据**
2. 类型选择 **SSH 密钥对**
3. 填入用户名
4. 粘贴**私钥**内容（-----BEGIN OPENSSH PRIVATE KEY----- 开头）
5. 如私钥有密码短语，填入 Passphrase
6. 点击**测试连接**验证可用性
7. 保存

### 4.3 凭据加密存储 / Encrypted Storage

所有凭据使用 **AES-256-GCM** 加密后存储于数据库。
`ACCOUNTSCAN_MASTER_KEY` 环境变量是加密密钥，**请妥善保管，切勿泄露或丢失**。

### 4.4 凭据使用追踪 / Usage Tracking

凭据管理页面显示：
- 最后使用时间
- 使用次数
- 关联的资产数量

---

## 5. 告警配置 / Alert Configuration

### 5.1 实时监控配置 / Real-Time Monitoring

实时监控在后台持续运行，每次扫描完成后自动检测以下告警：

| 告警类型 | 检测引擎 | 说明 |
|---------|---------|------|
| 账号「X」新增管理权限 | realtime_monitor | 普通→管理员权限变更 |
| NOPASSWD sudo 新增 | realtime_monitor | 免密 sudo 配置新增 |
| 敏感凭据泄露 | realtime_monitor | 发现危险凭据文件 |
| 休眠账号重新激活 | realtime_monitor | 沉寂账号再次活跃 |
| 孤儿特权账号 | realtime_monitor | 无关联人员身份的高危账号 |

### 5.2 Webhook 告警 / Webhook Alerts

配置 Webhook 将告警推送到外部系统（SIEM / SOAR / Slack / 飞书 / 企业微信）：

**Webhook 格式（POST）：**
```json
{
  "alert_id": 12345,
  "level": "critical",
  "title": "发现敏感凭据泄露 — 「root」",
  "title_key": "alert.credential_leak",
  "title_params": {"username": "root"},
  "asset_id": 5,
  "message": "资产 #5 账号「root」发现 3 个危险凭据...",
  "created_at": "2026-04-12T10:00:00Z"
}
```

### 5.3 邮件告警 / Email Alerts

在 `.env` 中配置 SMTP 参数：

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=alerts@example.com
SMTP_PASSWORD=your_smtp_password
```

重启后端服务使配置生效。

### 5.4 告警去重 / Alert Deduplication

同一类型的告警在 30 分钟内去重：
- 相同资产的相同告警类型，30 分钟内仅触发一次
- 超过 30 分钟重新触发（如果条件仍满足）

---

## 6. 策略管理 / Policy Management

路径：**安全运营 → 策略管理**

### 6.1 OPA Rego 策略 / OPA Rego Policies

 Telos 使用 **Open Policy Agent (OPA)** 的 Rego 语言编写安全策略。

### 6.2 内置策略 / Built-In Policies

以下策略默认启用，不可删除：

| 策略名称 | 说明 | 严重性 |
|---------|------|--------|
| Prohibited Shared Username | 检测 admin/root/test/guest/oracle 等禁止用户名 | 高危 |
| Privileged Account Long-term Inactive | 特权账号 90 天+无登录 | 中危 |
| NOPASSWD Sudo Permission | 检测免密 sudo 配置 | 严重 |
| System Account UID Range | 检测 UID < 1000 的系统账号 | 低危 |
| Dormant Account Should Be Disabled | 沉睡 180 天+账号应禁用 | 中危 |

### 6.3 自定义策略 / Custom Policies

**创建新策略：**
1. 点击**添加策略**
2. 填写策略名称和描述
3. 选择类别（特权管理/生命周期/合规/自定义）
4. 编写 Rego 规则
5. 点击**保存并评估**测试规则
6. 评估通过后启用

**示例策略：检测 root 账号 SSH 登录：**
```rego
package accountscan.policy

deny[msg] {
    input.account.username == "root"
    input.account.shell == "/bin/bash"
    input.account.last_login != null
    msg := "root account has interactive login access"
}
```

### 6.4 策略评估 / Policy Evaluation

1. 选择要评估的**资产**和**扫描快照**
2. 点击**执行评估**
3. 查看结果：每条策略显示 PASS / FAIL 及违规详情
4. 结果可导出为合规报告

---

## 7. 处置剧本 / Remediation Playbooks

路径：**系统 → 处置剧本**

### 7.1 剧本模板 / Playbook Templates

系统内置以下剧本模板：

| 剧本 | 触发条件 | 自动处置动作 |
|------|---------|------------|
| Critical Credential Leak | 发现敏感凭据泄露 | 标记并通知 |
| NOPASSWD Sudo Alert | NOPASSWD sudo 新增 | 标记并通知 |
| Inactive Privileged Account | 特权账号长期不活跃 | 标记并通知 |
| Shadow Account Alert | 孤儿特权账号 | 标记并通知 |
| SSH Key Reuse | SSH 密钥复用 | 标记横向移动风险 |
| New Privileged Account | 新增特权账号 | 标记待审查 |

### 7.2 手动执行剧本 / Execute Playbook Manually

1. 进入剧本列表
2. 点击剧本右侧**执行**
3. 选择目标资产或账号
4. 确认执行
5. 查看执行结果和审计日志

### 7.3 审批流程 / Approval Workflow

对于高危处置动作（如禁用账号），可开启**审批流程**：
1. 编辑剧本 → 开启"需要审批"
2. 执行时创建待审批记录
3. 管理员审批/驳回
4. 通过后执行实际处置动作

---

## 8. 特权审查 / Privileged Review

路径：**安全运营 → 特权审查**

### 8.1 审查计划 / Review Schedules

配置周期性特权账号审查：

| 周期 | 说明 | Cron |
|------|------|------|
| 每月 | 每月第一天凌晨生成报告 | `0 3 1 * *` |
| 每季度 | 每季度第一天凌晨生成报告 | `0 3 1 */3 *` |

### 8.2 审查报告内容 / Review Report Contents

- 总账号数 / 特权账号数 / 沉睡账号数 / 离职账号数
- 高风险资产清单
- 各合规框架检查结果

### 8.3 审查工作流 / Review Workflow

```
待审查 → 已批准 / 已驳回
```

审查员对报告中的每项进行：
- **批准**：确认账号使用正常
- **驳回**：需要处置（触发剧本或手动处理）
- **添加备注**：记录审查意见

---

## 9. 特权访问管理集成 / PAM Integration

路径：**安全运营 → 特权访问管理**

### 9.1 支持的 PAM 系统 / Supported PAM Systems

| PAM 产品 | 集成方式 | 备注 |
|---------|---------|------|
| 腾讯云 PAM | REST API (Bearer Token) | 云堡垒机 |
| 阿里云 PAM | REST API (API Key) | 云堡垒机 |
| CyberArk | REST API | 企业级 PAM |
| 自定义 API | REST API (可配置认证) | 支持标准 Bearer/Basic Auth |

### 9.2 配置 PAM 连接 / Configure PAM Connection

1. 点击**添加 PAM 集成**
2. 选择 PAM 类型
3. 填入 API Endpoint URL
4. 配置认证凭据（API Token / Bearer Key 等）
5. 点击**测试连接**
6. 连接成功后点击**保存**

### 9.3 账号比对 / Account Comparison

PAM 集成后，系统自动将 PAM 中的账号与 Telos 扫描结果比对：

| 比对结果 | 说明 |
|---------|------|
| **合规（Matched）** | PAM 与 Telos 一致 |
| **特权差距（Privileged Gap）** | PAM 有但 Telos 无，或反之 |
| **未匹配（Unmatched PAM）** | PAM 中的账号在 Telos 中不存在 |

---

## 10. AI 模型配置 / AI Model Configuration

路径：**系统 → 系统设置 → AI 模型**

### 10.1 支持的 LLM 提供商 / Supported LLM Providers

| 提供商 | Base URL | 说明 |
|-------|---------|------|
| OpenAI | `https://api.openai.com/v1` | GPT-4o 等 |
| MiniMax | `https://api.minimax.chat/v1` | 国产大模型 |
| 自定义兼容 API | 用户指定 | 兼容 OpenAI 格式的其他 LLM |

### 10.2 配置步骤 / Configuration Steps

1. 进入系统设置
2. 选择 LLM 提供商
3. 填入 Base URL（如使用代理或私有部署）
4. 填入 API Key（加密存储）
5. 选择模型名称（如 `gpt-4o`、`abab6.5s`）
6. 点击**测试连接**验证配置
7. 保存

### 10.3 AI 功能说明 / AI Feature Overview

| 功能 | 说明 |
|------|------|
| AI 安全摘要 | 自动生成威胁态势自然语言报告 |
| 自然语言资产搜索 | 用自然语言查询资产（例："近30天新增管理员的Linux服务器"）|
| 账号风险深度分析 | LLM 解读账号风险因素 |
| 知识库问答 | RAG 驱动的安全知识问答 |

---

## 11. 系统设置 / System Settings

路径：**系统 → 系统设置**

### 11.1 AI 模型 / AI Model

见第 10 节。

### 11.2 许可证 / License

显示当前许可证状态：
- **激活状态**：已注册版本
- **试用版**：有效期倒计时
- **到期**：需续费

**激活许可证：**
1. 点击**激活许可证**
2. 输入许可证密钥
3. 确认激活

### 11.3 数据保留策略 / Data Retention

| 数据类型 | 默认保留期 | 说明 |
|---------|-----------|------|
| 扫描快照 | 90 天 | 可配置 |
| 告警记录 | 永久 | 不可配置 |
| 分析记录 | 90 天 | 可配置 |
| 操作审计日志 | 180 天 | 可配置 |

---

## 附录 A：环境变量快速参考 / Appendix A: Environment Variables Quick Reference

```bash
# 必填
DB_PASSWORD=xxx
ACCOUNTSCAN_MASTER_KEY=xxx  # 64位hex，AES-256密钥
ACCOUNTSCAN_JWT_SECRET=xxx   # 64位hex，JWT签名密钥

# 数据库
DATABASE_URL=postgresql://accountscan:xxx@db:5432/accountscan
DB_POOL_SIZE=10

# 端口
PORT=8000
FRONTEND_PORT=3000

# 可选
GO_ANALYSIS_ENGINE_URL=http://telos-engine:8082   # Go威胁分析引擎
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=alerts@example.com
SMTP_PASSWORD=xxx
REDIS_URL=redis://redis:6379/0
LOG_LEVEL=INFO
```

---

*Telos v2.0 | © 2026 Telos*
