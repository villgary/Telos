# Telos API 参考文档
# Telos API Reference

> **文档版本 / API Version**: v2.0
> **Base URL**: `https://your-telos-domain.com/api/v2`
> **认证方式 / Authentication**: Bearer Token (JWT)
> **格式 / Format**: JSON

---

## 目录 / Table of Contents

1. [概述与认证 / Overview & Authentication](#1-概述与认证)
2. [通用说明 / General Conventions](#2-通用说明)
3. [资产 API / Assets API](#3-资产-api-assets-api)
4. [扫描作业 API / Scans API](#4-扫描作业-api-scans-api)
5. [身份威胁分析 API / Analysis API](#5-身份威胁分析-api-analysis-api)
6. [ATT&CK 覆盖率 API / ATT&CK Coverage API](#6-attck-覆盖率-api-attck-coverage-api)
7. [告警 API / Alerts API](#7-告警-api-alerts-api)
8. [NHI API](#8-nhi-api)
9. [账号生命周期 API / Account Lifecycle API](#9-账号生命周期-api-account-lifecycle-api)
10. [合规评估 API / Compliance API](#10-合规评估-api-compliance-api)
11. [策略管理 API / Policies API](#11-策略管理-api-policies-api)
12. [用户管理 API / Users API](#12-用户管理-api-users-api)
13. [Webhook 回调 / Webhook Callbacks](#13-webhook-回调)
14. [错误码 / Error Codes](#14-错误码)

---

## 1. 概述与认证 / Overview & Authentication

### 1.1 认证流程 / Authentication Flow

Telos API 使用 JWT Bearer Token 认证。

**步骤 1：获取访问令牌 / Step 1: Obtain Access Token**

```
POST /api/v2/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password"
}
```

**响应 / Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**步骤 2：在后续请求中携带令牌 / Step 2: Include Token in Requests**

```
Authorization: Bearer <access_token>
```

### 1.2 令牌刷新 / Token Refresh

```
POST /api/v2/auth/refresh
Authorization: Bearer <access_token>
```

### 1.3 登出 / Logout

```
POST /api/v2/auth/logout
Authorization: Bearer <access_token>
```

### 1.4 错误认证 / Authentication Errors

| HTTP 状态码 / HTTP Status | 错误码 / Error Code | 说明 / Description |
|--------------------------|-------------------|-------------------|
| 401 | `AUTH_INVALID_CREDENTIALS` | 用户名或密码错误 / Invalid username or password |
| 401 | `AUTH_TOKEN_EXPIRED` | Token 已过期 / Token has expired |
| 401 | `AUTH_TOKEN_INVALID` | Token 无效 / Token is invalid |
| 403 | `AUTH_INSUFFICIENT_PERMISSION` | 权限不足 / Insufficient permissions |

---

## 2. 通用说明 / General Conventions

### 2.1 请求格式 / Request Format

- 所有请求必须包含 `Content-Type: application/json`（除文件上传外）
- 所有时间格式使用 ISO 8601：`2026-04-12T10:00:00Z`（UTC）
- 所有 ID 字段为整数（自增主键）

### 2.2 响应格式 / Response Format

**成功响应 / Success Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

**分页响应 / Paginated Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [ ... ],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

### 2.3 通用请求参数 / Common Parameters

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|-------------------|
| `page` | int | 页码，默认 1 / Page number, default 1 |
| `page_size` | int | 每页数量，默认 20 / Page size, default 20 |
| `order_by` | string | 排序字段 / Order field |
| `order_dir` | string | 排序方向：`asc` / `desc`，默认 `desc` |
| `created_after` | datetime | 筛选：创建时间晚于 / Filter: created after |
| `created_before` | datetime | 筛选：创建时间早于 / Filter: created before |

### 2.4 通用过滤参数 / Common Filter Parameters

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|-------------------|
| `search` | string | 模糊搜索 / Fuzzy search |
| `asset_id` | int | 按资产 ID 筛选 / Filter by asset ID |
| `level` | string | 按严重性筛选：`critical` / `high` / `medium` / `low` |
| `status` | string | 按状态筛选 / Filter by status |
| `is_admin` | bool | 按是否管理员筛选 / Filter by admin status |

---

## 3. 资产 API / Assets API

**端点前缀 / Base Path:** `/api/v2/assets`

### 3.1 资产列表 / List Assets

```
GET /api/v2/assets
```

**请求参数 / Request Parameters:**

| 参数 / Parameter | 类型 / Type | 必填 / Required | 说明 / Description |
|----------------|------------|:--------------:|------------------|
| `category` | string | 否 / No | 资产类别 slug / Asset category slug |
| `group_id` | int | 否 / No | 资产分组 ID / Asset group ID |
| `os_type` | string | 否 / No | 操作系统：`linux` / `windows` / `database` / `cloud` |
| `status` | string | 否 / No | 状态：`online` / `offline` / `scanning` |

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "name": "web-server-01",
        "code": "WEB01",
        "ip_address": "192.168.1.100",
        "os_type": "linux",
        "category": "server/linux",
        "account_count": 45,
        "privileged_count": 3,
        "last_scan_at": "2026-04-12T08:00:00Z",
        "status": "online",
        "risk_score": 72,
        "group_id": 2,
        "credential_id": 5,
        "created_at": "2026-01-15T10:00:00Z",
        "updated_at": "2026-04-12T08:00:00Z"
      }
    ],
    "total": 150,
    "page": 1,
    "page_size": 20
  }
}
```

### 3.2 获取单个资产 / Get Asset

```
GET /api/v2/assets/{id}
```

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "name": "web-server-01",
    "code": "WEB01",
    "ip_address": "192.168.1.100",
    "os_type": "linux",
    "category": "server/linux",
    "description": "Web application server",
    "account_count": 45,
    "privileged_count": 3,
    "last_scan_at": "2026-04-12T08:00:00Z",
    "last_scan_job_id": 42,
    "status": "online",
    "risk_score": 72,
    "group_id": 2,
    "group_name": "Production",
    "parent_asset_id": null,
    "credential_id": 5,
    "credential_name": "SSH-Prod-Key",
    "created_at": "2026-01-15T10:00:00Z",
    "updated_at": "2026-04-12T08:00:00Z"
  }
}
```

### 3.3 创建资产 / Create Asset

```
POST /api/v2/assets
```

**请求体 / Request Body:**

```json
{
  "name": "web-server-01",
  "code": "WEB01",
  "ip_address": "192.168.1.100",
  "os_type": "linux",
  "category": "server/linux",
  "description": "Web application server",
  "group_id": 2,
  "parent_asset_id": null,
  "credential_id": 5
}
```

| 字段 / Field | 类型 / Type | 必填 / Required | 说明 / Description |
|-------------|------------|:--------------:|------------------|
| `name` | string | ✅ | 资产名称 / Asset name |
| `code` | string | ✅ | 唯一编码 / Unique code |
| `ip_address` | string | ✅ | IP 地址 / IP address |
| `os_type` | string | ✅ | 操作系统类型 / OS type |
| `category` | string | ✅ | 资产类别 / Asset category |
| `credential_id` | int | ✅ | 关联凭据 ID / Credential ID |
| `group_id` | int | 否 / No | 资产分组 ID / Asset group ID |
| `parent_asset_id` | int | 否 / No | 上级资产 ID / Parent asset ID |
| `description` | string | 否 / No | 描述 / Description |

### 3.4 更新资产 / Update Asset

```
PUT /api/v2/assets/{id}
```

请求体同创建接口，仅包含需要修改的字段。

### 3.5 删除资产 / Delete Asset

```
DELETE /api/v2/assets/{id}
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|------------------|
| `force` | bool | 强制删除（含扫描记录）/ Force delete (including scan records) |

### 3.6 测试连接 / Test Connection

```
POST /api/v2/assets/{id}/test-connection
```

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "reachable": true,
    "response_time_ms": 245,
    "account_count_estimate": 42,
    "error_message": null
  }
}
```

### 3.7 资产账号列表 / Get Asset Accounts

```
GET /api/v2/assets/{id}/accounts
```

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 101,
        "username": "root",
        "uid": 0,
        "primary_gid": 0,
        "primary_group": "root",
        "shell": "/bin/bash",
        "home_dir": "/root",
        "is_admin": true,
        "sudo_config": "ALL=(ALL) ALL",
        "account_status": "enabled",
        "last_login": "2026-04-10T08:30:00Z",
        "last_login_ip": "192.168.1.50",
        "account_type": "system",
        "is_nhi": false,
        "account_lifecycle_status": "active",
        "first_seen": "2026-01-15T10:00:00Z",
        "last_seen": "2026-04-12T08:00:00Z"
      }
    ],
    "total": 45
  }
}
```

---

## 4. 扫描作业 API / Scans API

**端点前缀 / Base Path:** `/api/v2/scans`

### 4.1 扫描任务列表 / List Scan Jobs

```
GET /api/v2/scans
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|------------------|
| `status` | string | 状态：`pending` / `running` / `completed` / `failed` |
| `asset_id` | int | 按资产筛选 / Filter by asset ID |
| `scan_type` | string | 扫描类型：`full` / `incremental` |

### 4.2 创建扫描任务 / Create Scan Job

```
POST /api/v2/scans
```

**请求体 / Request Body:**

```json
{
  "name": "Weekly Full Scan - Production",
  "scan_type": "full",
  "asset_ids": [1, 2, 3, 5, 8],
  "credential_ids": [5, 6],
  "priority": "normal",
  "callback_url": "https://your-system.com/webhook/scan-complete"
}
```

| 字段 / Field | 类型 / Type | 必填 / Required | 说明 / Description |
|-------------|------------|:--------------:|------------------|
| `name` | string | 否 / No | 扫描任务名称，默认自动生成 |
| `scan_type` | string | ✅ | `full`（全量）或 `incremental`（增量）|
| `asset_ids` | int[] | ✅ | 目标资产 ID 列表 / Target asset IDs |
| `credential_ids` | int[] | 否 / No | 覆盖资产默认凭据 / Override default credentials |
| `priority` | string | 否 / No | `low` / `normal` / `high`，默认 `normal` |
| `callback_url` | string | 否 / No | 扫描完成回调 URL / Callback URL on completion |

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 43,
    "name": "Weekly Full Scan - Production",
    "scan_type": "full",
    "status": "pending",
    "asset_count": 5,
    "progress": 0,
    "account_count_discovered": 0,
    "created_at": "2026-04-12T10:00:00Z",
    "started_at": null,
    "completed_at": null,
    "callback_url": "https://your-system.com/webhook/scan-complete"
  }
}
```

### 4.3 获取扫描详情 / Get Scan Job Detail

```
GET /api/v2/scans/{id}
```

### 4.4 取消扫描 / Cancel Scan

```
POST /api/v2/scans/{id}/cancel
```

### 4.5 扫描 Diff 对比 / Scan Diff

```
GET /api/v2/scans/diff
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 必填 / Required | 说明 / Description |
|----------------|------------|:--------------:|------------------|
| `scan_a_id` | int | ✅ | 第一次扫描 ID / First scan ID |
| `scan_b_id` | int | ✅ | 第二次扫描 ID / Second scan ID |
| `asset_id` | int | 否 / No | 按资产筛选 / Filter by asset ID |

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "scan_a": { "id": 40, "started_at": "2026-04-05T10:00:00Z" },
    "scan_b": { "id": 42, "started_at": "2026-04-12T10:00:00Z" },
    "changes": [
      {
        "asset_id": 1,
        "asset_name": "web-server-01",
        "change_type": "NEW_ACCOUNT",
        "risk_level": "medium",
        "username": "attacker_backdoor",
        "details": {
          "uid": 1001,
          "is_admin": true,
          "shell": "/bin/bash",
          "sudo_config": "ALL=(ALL) ALL"
        }
      },
      {
        "asset_id": 1,
        "asset_name": "web-server-01",
        "change_type": "PRIVILEGE_ESCALATION",
        "risk_level": "critical",
        "username": "bob",
        "details": {
          "was_admin": false,
          "is_admin": true,
          "sudo_added": "ALL=(ALL) ALL",
          "change_time": "2026-04-11T15:30:00Z"
        }
      }
    ],
    "summary": {
      "new_accounts": 2,
      "deleted_accounts": 0,
      "privilege_escalations": 1,
      "config_changes": 3
    }
  }
}
```

### 4.6 定时扫描计划 / Scheduled Scans

#### 列表 / List Schedules

```
GET /api/v2/scans/schedules
```

#### 创建定时扫描 / Create Schedule

```
POST /api/v2/scans/schedules
```

```json
{
  "name": "Daily Linux Scan",
  "scan_type": "full",
  "asset_filter": { "category": "server/linux" },
  "cron_expression": "0 3 * * *",
  "enabled": true,
  "callback_url": "https://your-system.com/webhook/scan-complete"
}
```

#### 更新定时扫描 / Update Schedule

```
PUT /api/v2/scans/schedules/{id}
```

#### 删除定时扫描 / Delete Schedule

```
DELETE /api/v2/scans/schedules/{id}
```

---

## 5. 身份威胁分析 API / Analysis API

**端点前缀 / Base Path:** `/api/v2/analysis`

### 5.1 触发分析 / Trigger Analysis

```
POST /api/v2/analysis
```

**请求体 / Request Body:**

```json
{
  "scope": "global",
  "asset_ids": [1, 2, 3],
  "engine": "python",
  "layers": ["semiotics", "ontology", "cognitive", "anthropology", "causal"],
  "callback_url": "https://your-system.com/webhook/analysis-complete"
}
```

| 字段 / Field | 类型 / Type | 必填 / Required | 说明 / Description |
|-------------|------------|:--------------:|------------------|
| `scope` | string | ✅ | `global`（全局）或 `assets`（指定资产）|
| `asset_ids` | int[] | 仅 scope=assets 时 | 资产 ID 列表 / Asset IDs |
| `engine` | string | 否 / No | `python`（默认）或 `go`（高性能）|
| `layers` | string[] | 否 / No | 分析层级，默认全部 / Analysis layers, default all |
| `callback_url` | string | 否 / No | 分析完成回调 / Callback on completion |

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 15,
    "scope": "global",
    "status": "running",
    "engine": "python",
    "layers": ["semiotics", "ontology", "cognitive", "anthropology", "causal"],
    "account_count_analyzed": 4521,
    "signal_count": 0,
    "progress": 0,
    "started_at": "2026-04-12T10:00:00Z",
    "completed_at": null,
    "estimated_remaining_seconds": 28
  }
}
```

### 5.2 获取分析结果 / Get Analysis Result

```
GET /api/v2/analysis/{id}
```

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 15,
    "status": "completed",
    "scope": "global",
    "engine": "python",
    "account_count_analyzed": 4521,
    "signal_count": 87,
    "critical_count": 3,
    "high_count": 12,
    "medium_count": 45,
    "low_count": 27,
    "overall_risk_score": 68,
    "overall_risk_level": "high",
    "layer_summary": {
      "semiotics": { "signals": 12, "risk_level": "medium" },
      "ontology": { "signals": 8, "risk_level": "high" },
      "cognitive": { "signals": 15, "risk_level": "medium" },
      "anthropology": { "signals": 22, "risk_level": "high" },
      "causal": { "signals": 30, "risk_level": "critical" }
    },
    "started_at": "2026-04-12T10:00:00Z",
    "completed_at": "2026-04-12T10:00:28Z",
    "duration_seconds": 28
  }
}
```

### 5.3 获取威胁信号列表 / List Threat Signals

```
GET /api/v2/analysis/{id}/signals
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|------------------|
| `layer` | string | 层级筛选 / Layer filter |
| `level` | string | 严重性筛选 / Severity filter |
| `mitre_tactic` | string | ATT&CK 战术筛选 / ATT&CK tactic filter |

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1001,
        "layer": "causal",
        "level": "critical",
        "title": "权限提升路径：web-user → root",
        "mitre_tactic": "TA0004",
        "mitre_tactic_label": "Privilege Escalation",
        "mitre_technique": "T1078.003",
        "mitre_technique_label": "Local Accounts",
        "affected_accounts": ["web-user"],
        "affected_assets": ["web-server-01"],
        "confidence": 0.92,
        "description": "通过 SSH 密钥复用，web-user 可通过 db-server-01 跳转到 web-server-01 并提权至 root",
        "evidence": [
          { "type": "ssh_key", "from": "db-server-01", "to": "web-server-01" },
          { "type": "sudo_config", "username": "web-user", "config": "web-user ALL=(ALL) NOPASSWD: /usr/bin/su" }
        ],
        "remediation": "移除 web-user 的 NOPASSWD sudo 配置，限制 SSH authorized_keys 范围",
        "created_at": "2026-04-12T10:00:28Z"
      }
    ],
    "total": 87
  }
}
```

### 5.4 攻击路径模拟 / Attack Path Simulation

```
POST /api/v2/analysis/{id}/simulate
```

**请求体 / Request Body:**

```json
{
  "patient_zero": "bob",
  "patient_zero_asset_id": 3,
  "max_hops": 5,
  "target_condition": "is_admin=true"
}
```

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "patient_zero": { "username": "bob", "asset_name": "dev-server-01" },
    "max_hops": 5,
    "paths_found": 2,
    "paths": [
      {
        "hop_count": 3,
        "path": [
          { "asset": "dev-server-01", "username": "bob", "method": "initial" },
          { "asset": "db-server-01", "username": "bob", "method": "ssh_key_reuse" },
          { "asset": "web-server-01", "username": "bob", "method": "sudo_privilege_escalation", "is_admin": true }
        ],
        "mitre_techniques": ["T1078", "T1021.004", "T1548.001"],
        "risk_score": 95
      }
    ]
  }
}
```

---

## 6. ATT&CK 覆盖率 API / ATT&CK Coverage API

**端点前缀 / Base Path:** `/api/v2/attck`

### 6.1 覆盖率概览 / Coverage Overview

```
GET /api/v2/attck/coverage
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|------------------|
| `analysis_id` | int | 分析 ID（不传则用最新）|

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "attck_version": "v14",
    "total_signals": 87,
    "overall_risk_score": 68,
    "overall_risk_level": "high",
    "tactic_coverage": [
      { "tactic_id": "TA0001", "name": "Initial Access", "signal_count": 5, "techniques": ["T1078", "T1078.001"] },
      { "tactic_id": "TA0004", "name": "Privilege Escalation", "signal_count": 22, "techniques": ["T1078.003", "T1548.001"] },
      { "tactic_id": "TA0006", "name": "Credential Access", "signal_count": 18, "techniques": ["T1552.001", "T1552"] },
      { "tactic_id": "TA0008", "name": "Lateral Movement", "signal_count": 25, "techniques": ["T1021.004"] },
      { "tactic_id": "TA0003", "name": "Persistence", "signal_count": 10, "techniques": ["T1078"] },
      { "tactic_id": "TA0005", "name": "Defense Evasion", "signal_count": 7, "techniques": ["T1562"] }
    ],
    "technique_details": [
      {
        "technique_id": "T1078",
        "name": "Valid Accounts",
        "tactic": "TA0004",
        "signal_count": 30,
        "confidence": 0.88,
        "affected_accounts": ["root", "admin", "oracle"],
        "affected_assets": ["server-01", "server-02", "db-server"],
        "risk_level": "critical"
      }
    ]
  }
}
```

### 6.2 导出 Navigator Layer / Export Navigator Layer

```
GET /api/v2/attck/coverage/export
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|------------------|
| `analysis_id` | int | 分析 ID |
| `format` | string | `json`（默认）或 `xlsx` |

**响应 / Response:**
返回符合 ATT&CK Navigator v4.x schema 的 JSON 文件。

---

## 7. 告警 API / Alerts API

**端点前缀 / Base Path:** `/api/v2/alerts`

### 7.1 告警列表 / List Alerts

```
GET /api/v2/alerts
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|------------------|
| `status` | string | `new` / `acknowledged` / `responded` / `dismissed` |
| `level` | string | `critical` / `high` / `medium` / `low` |
| `asset_id` | int | 按资产筛选 |
| `alert_type` | string | 告警类型 |
| `date_from` | date | 开始日期 |
| `date_to` | date | 结束日期 |

### 7.2 获取告警详情 / Get Alert Detail

```
GET /api/v2/alerts/{id}
```

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 12345,
    "level": "critical",
    "title_key": "alert.credential_leak",
    "title_params": { "username": "root" },
    "message_key": "alert.msg.credential_leak",
    "message_params": { "username": "root", "file_count": 3 },
    "asset_id": 5,
    "asset_name": "web-server-01",
    "asset_ip": "192.168.1.100",
    "job_id": 42,
    "status": "new",
    "acknowledged_by": null,
    "acknowledged_at": null,
    "responded_by": null,
    "responded_at": null,
    "notes": [],
    "created_at": "2026-04-12T10:00:00Z"
  }
}
```

### 7.3 确认告警 / Acknowledge Alert

```
POST /api/v2/alerts/{id}/acknowledge
```

### 7.4 响应告警 / Respond to Alert

```
POST /api/v2/alerts/{id}/respond
```

```json
{
  "action_taken": "Account disabled, ticket created",
  "ticket_id": "INC-20260412-001"
}
```

### 7.5 驳回告警 / Dismiss Alert

```
POST /api/v2/alerts/{id}/dismiss
```

```json
{
  "reason": "False positive - legitimate administrative action"
}
```

### 7.6 告警统计 / Alert Statistics

```
GET /api/v2/alerts/stats
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|------------------|
| `period` | string | `24h` / `7d` / `30d` / `90d` |

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 156,
    "by_level": { "critical": 5, "high": 23, "medium": 78, "low": 50 },
    "by_status": { "new": 12, "acknowledged": 8, "responded": 130, "dismissed": 6 },
    "by_type": { "admin_privilege_added": 45, "credential_leak": 12, "nopasswd_sudo": 23 },
    "trend": [
      { "date": "2026-04-05", "count": 8 },
      { "date": "2026-04-06", "count": 12 }
    ]
  }
}
```

---

## 8. NHI API

**端点前缀 / Base Path:** `/api/v2/nhi`

### 8.1 NHI 列表 / List NHI

```
GET /api/v2/nhi
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|------------------|
| `nhi_type` | string | `service` / `system` / `cloud` / `cicd` / `application` / `workload` / `ai_agent` / `unknown` |
| `risk_level` | string | `critical` / `high` / `medium` / `low` |
| `owner` | string | 归属人邮箱 / Owner email |

### 8.2 NHI 仪表板 / NHI Dashboard

```
GET /api/v2/nhi/dashboard
```

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_count": 3450,
    "by_type": {
      "service": 820,
      "system": 450,
      "cloud": 980,
      "cicd": 320,
      "application": 380,
      "workload": 280,
      "ai_agent": 120,
      "unknown": 100
    },
    "by_risk_level": { "critical": 45, "high": 230, "medium": 890, "low": 2285 },
    "top_risks": [
      {
        "id": 101,
        "username": "ci-deploy-prod",
        "nhi_type": "cicd",
        "risk_level": "critical",
        "risk_score": 95,
        "owner": "devops@company.com",
        "rotation_status": "overdue",
        "rotation_due_days": -30,
        "reason": "API key has not been rotated in 400 days"
      }
    ],
    "rotation_overview": {
      "compliant": 2100,
      "due_soon": 340,
      "overdue": 120
    }
  }
}
```

### 8.3 分配归属人 / Assign Owner

```
POST /api/v2/nhi/{id}/assign-owner
```

```json
{
  "owner_email": "devops@company.com"
}
```

### 8.4 创建 NHI 记录 / Create NHI Record

```
POST /api/v2/nhi
```

```json
{
  "username": "ai-agent-gpt4-prod",
  "nhi_type": "ai_agent",
  "asset_id": 5,
  "credential_identifier": "sk-xxxxxxxxxxxxxxxx",
  "credential_type": "api_key",
  "owner_email": "ml-team@company.com",
  "rotation_days": 90,
  "description": "Production LLM API key for customer service AI agent"
}
```

---

## 9. 账号生命周期 API / Account Lifecycle API

**端点前缀 / Base Path:** `/api/v2/lifecycle`

### 9.1 账号状态列表 / List Account Lifecycle Status

```
GET /api/v2/lifecycle/accounts
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|------------------|
| `status` | string | `active` / `dormant` / `departed` / `unknown` |
| `asset_id` | int | 按资产筛选 |
| `is_admin` | bool | 按是否管理员筛选 |

### 9.2 状态统计 / Status Statistics

```
GET /api/v2/lifecycle/stats
```

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_accounts": 4521,
    "active": 3200,
    "dormant": 890,
    "departed": 231,
    "unknown": 200,
    "active_rate": "70.8%",
    "privileged_breakdown": {
      "active_admin": 145,
      "dormant_admin": 78,
      "departed_admin": 34
    }
  }
}
```

### 9.3 配置生命周期阈值 / Configure Lifecycle Thresholds

```
PUT /api/v2/lifecycle/settings
```

```json
{
  "global": {
    "active_threshold_days": 90,
    "departed_threshold_days": 180
  },
  "category_overrides": {
    "server/linux": {
      "active_threshold_days": 60,
      "departed_threshold_days": 120
    },
    "database": {
      "active_threshold_days": 180,
      "departed_threshold_days": 365
    }
  }
}
```

### 9.4 账号状态历史 / Account Status History

```
GET /api/v2/lifecycle/accounts/{id}/history
```

---

## 10. 合规评估 API / Compliance API

**端点前缀 / Base Path:** `/api/v2/compliance`

### 10.1 执行合规评估 / Run Compliance Assessment

```
POST /api/v2/compliance/assess
```

```json
{
  "framework": "soc2",
  "scope": { "asset_ids": [1, 2, 3] },
  "callback_url": "https://your-system.com/webhook/compliance-complete"
}
```

**支持的框架 / Supported Frameworks:**
- `soc2` — SOC 2 Trust Services Criteria
- `iso27001` — ISO/IEC 27001
- `gb22239` — 等保 2.0（GB/T 22239-2019）

### 10.2 获取评估结果 / Get Assessment Result

```
GET /api/v2/compliance/assessments/{id}
```

**响应 / Response:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 8,
    "framework": "soc2",
    "status": "completed",
    "overall_score": 78,
    "pass_rate": "78%",
    "controls": [
      {
        "control_id": "CC6.1",
        "name": "Logical and Physical Access Controls",
        "description": "Shared privileged account detection",
        "status": "fail",
        "finding_count": 15,
        "findings": [
          { "account": "oracle", "asset": "db-server-01", "severity": "high" }
        ],
        "recommendation": "立即禁用共享管理员账号，建立独立的个人账号"
      }
    ],
    "summary": {
      "total_controls": 20,
      "pass": 11,
      "fail": 6,
      "not_applicable": 3
    },
    "executed_at": "2026-04-12T10:30:00Z",
    "duration_seconds": 45
  }
}
```

### 10.3 合规报告导出 / Export Compliance Report

```
GET /api/v2/compliance/assessments/{id}/export
```

**查询参数 / Query Parameters:**

| 参数 / Parameter | 类型 / Type | 说明 / Description |
|----------------|------------|------------------|
| `format` | string | `pdf` / `xlsx` / `docx` |

---

## 11. 策略管理 API / Policies API

**端点前缀 / Base Path:** `/api/v2/policies`

### 11.1 策略列表 / List Policies

```
GET /api/v2/policies
```

### 11.2 创建策略 / Create Policy

```
POST /api/v2/policies
```

```json
{
  "name": "禁止 root SSH 交互登录",
  "name_en": "Prohibit root SSH interactive login",
  "description": "检测 root 账号是否配置了交互式 Shell 登录",
  "category": "privileged",
  "severity": "high",
  "rego_code": "package accountscan.policy\n\ndeny[msg] {\n    input.account.username == \"root\"\n    input.account.shell != \"/sbin/nologin\"\n    input.account.shell != \"/usr/sbin/nologin\"\n    msg := \"root account has interactive login access\"\n}"
}
```

### 11.3 评估策略 / Evaluate Policy

```
POST /api/v2/policies/{id}/evaluate
```

```json
{
  "asset_ids": [1, 2, 3],
  "scan_id": 42
}
```

### 11.4 获取策略评估结果 / Get Policy Evaluation Result

```
GET /api/v2/policies/{id}/evaluations/{eval_id}
```

---

## 12. 用户管理 API / Users API

**端点前缀 / Base Path:** `/api/v2/users`

### 12.1 用户列表 / List Users

```
GET /api/v2/users
```

### 12.2 创建用户 / Create User

```
POST /api/v2/users
```

```json
{
  "username": "alice",
  "password": "SecurePass123!",
  "role": "operator",
  "email": "alice@company.com"
}
```

**角色 / Roles:** `admin` / `operator` / `viewer`

### 12.3 修改密码 / Change Password

```
POST /api/v2/users/{id}/change-password
```

```json
{
  "old_password": "current-password",
  "new_password": "new-secure-password"
}
```

### 12.4 重置密码（管理员） / Reset Password (Admin)

```
POST /api/v2/users/{id}/reset-password
```

---

## 13. Webhook 回调 / Webhook Callbacks

### 13.1 注册 Webhook / Register Webhook

```
POST /api/v2/webhooks
```

```json
{
  "name": "SOC SOAR Integration",
  "url": "https://your-soar.com/webhook/telos",
  "events": ["alert.created", "alert.responded", "scan.completed", "analysis.completed"],
  "secret": "your-webhook-secret"
}
```

**支持的 Webhook 事件 / Supported Events:**

| 事件 / Event | 触发条件 / Trigger |
|------------|-----------------|
| `alert.created` | 新告警创建 |
| `alert.acknowledged` | 告警被确认 |
| `alert.responded` | 告警已响应 |
| `alert.dismissed` | 告警被驳回 |
| `scan.completed` | 扫描任务完成 |
| `scan.failed` | 扫描任务失败 |
| `analysis.completed` | 威胁分析完成 |
| `compliance.assessment.completed` | 合规评估完成 |

### 13.2 Webhook 签名验证 / Webhook Signature Verification

Webhook 请求包含 `X-Telos-Signature` 头，格式为：
```
X-Telos-Signature: sha256=<hmac_hex>
```

**验证方法（Python）：**
```python
import hmac, hashlib

def verify_webhook(payload_bytes, signature, secret):
    expected = 'sha256=' + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 13.3 Webhook 事件示例 / Webhook Event Examples

**扫描完成事件 / Scan Completed Event:**

```json
POST https://your-system.com/webhook/scan-complete
Content-Type: application/json
X-Telos-Signature: sha256=abc123...

{
  "event": "scan.completed",
  "timestamp": "2026-04-12T10:30:00Z",
  "data": {
    "scan_id": 42,
    "status": "completed",
    "asset_count": 5,
    "account_count_discovered": 234,
    "error_count": 0
  }
}
```

---

## 14. 错误码 / Error Codes

### 14.1 HTTP 状态码与业务错误码 / HTTP Status Codes & Business Error Codes

| HTTP 状态码 / HTTP Status | 业务错误码 / Error Code | 说明 / Description |
|--------------------------|---------------------|-------------------|
| 400 | `VALIDATION_ERROR` | 请求参数校验失败 / Request validation failed |
| 400 | `INVALID_SCAN_TYPE` | 扫描类型无效 / Invalid scan type |
| 400 | `INVALID_FRAMEWORK` | 合规框架无效 / Invalid compliance framework |
| 401 | `AUTH_INVALID_CREDENTIALS` | 认证凭据无效 / Invalid credentials |
| 401 | `AUTH_TOKEN_EXPIRED` | Token 已过期 / Token expired |
| 403 | `PERMISSION_DENIED` | 操作权限不足 / Operation not permitted |
| 404 | `ASSET_NOT_FOUND` | 资产不存在 / Asset not found |
| 404 | `SCAN_NOT_FOUND` | 扫描任务不存在 / Scan not found |
| 404 | `ANALYSIS_NOT_FOUND` | 分析任务不存在 / Analysis not found |
| 404 | `ALERT_NOT_FOUND` | 告警不存在 / Alert not found |
| 409 | `ASSET_CODE_EXISTS` | 资产编码已存在 / Asset code already exists |
| 409 | `SCAN_ALREADY_RUNNING` | 扫描任务正在运行 / Scan already running |
| 422 | `CONNECTION_FAILED` | 资产连接失败 / Asset connection failed |
| 422 | `CREDENTIAL_INVALID` | 凭据无效 / Credential invalid |
| 500 | `INTERNAL_ERROR` | 内部错误 / Internal server error |
| 503 | `ENGINE_UNAVAILABLE` | 分析引擎不可用 / Analysis engine unavailable |

### 14.2 错误响应格式 / Error Response Format

```json
{
  "code": 404,
  "message": "ASSET_NOT_FOUND",
  "detail": "Asset with id=999 does not exist",
  "request_id": "req_abc123"
}
```

---

## 附录 A：OpenAPI 规范下载 / Appendix A: OpenAPI Spec Download

```
GET /api/v2/openapi.json  → OpenAPI 3.0 JSON 规范
GET /api/v2/redoc         → ReDoc API 文档
GET /api/v2/swagger       → Swagger UI
```

---

*Telos v2.0 | © 2026 Telos. All rights reserved.*
*Telos v2.0 | © 2026 Telos 版权所有。*
