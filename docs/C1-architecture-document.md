# Telos 架构设计文档
# Telos Architecture Design Document

> **文档版本 / Version**: v2.0
> **适用范围 / Audience**: 研发团队 / 安全架构师 / 架构评审委员会
> **状态 / Status**: 正式版

---

## 1. 系统概述 / System Overview

### 1.1 产品定位 / Product Positioning

Telos 是身份威胁检测与响应（ITDR）平台，通过自动化账号扫描、MITRE ATT&CK 威胁映射和五层 AI 语义分析，帮助组织发现影子账号、检测凭据滥用和横向移动风险。

### 1.2 核心设计原则 / Core Design Principles

| 原则 / Principle | 说明 / Description |
|----------------|------------------|
| **检测优先 / Detection First** | 所有架构决策以威胁检测能力为核心 |
| **左移安全 / Shift-Left Security** | 优先在攻击早期发现威胁（MTTD 最小化）|
| **数据驱动 / Data-Driven** | 基于历史数据建立行为基线，检测异常 |
| **开放集成 / Open Integration** | 通过 REST API + Webhook 无缝集成现有安全生态 |
| **弹性扩展 / Elastic Scalability** | 扫描节点按需扩展，支持大规模并发分析 |

---

## 2. 系统架构 / System Architecture

### 2.1 整体架构图 / Overall Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Telos 系统架构 / Telos Architecture                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         客户端层 / Client Layer                       │   │
│  │   浏览器 (React SPA) │ API 客户端 │ CLI 工具 │ 第三方集成系统           │   │
│  └────────────────────────────────┬─────────────────────────────────────┘   │
│                                    │ HTTPS (REST API)                       │
│  ┌────────────────────────────────▼─────────────────────────────────────┐   │
│  │                         应用层 / Application Layer                      │   │
│  │                                                                        │   │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │   │
│  │  │ 扫描调度 │  │ 威胁分析  │  │ 告警引擎  │  │ 策略评估  │  │ 账号生命周期│ │   │
│  │  │ ScanSch │  │AnalyzerSvc│  │ AlertSvc  │  │ PolicySvc │  │LifecycleSvc│ │   │
│  │  └─────────┘  └──────────┘  └──────────┘  └──────────┘  └────────┘ │   │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │   │
│  │  │ 用户管理 │  │ NHI管理  │  │ 实时监控  │  │ 合规评估  │  │ ATT&CK映射│ │   │
│  │  │ UserSvc │  │ NHISvc   │  │RtMonitorSvc│ │ComplianceSvc│ │AttckMapSvc│ │   │
│  │  └─────────┘  └──────────┘  └──────────┘  └──────────┘  └────────┘ │   │
│  │                                                                        │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │                     API Gateway / 中间件 / Middleware             │ │   │
│  │  │  JWT Auth │ Rate Limiter │ Request Logger │ CORS │ Exception Handler │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  └────────────────────────────────┬─────────────────────────────────────┘   │
│                                    │                                         │
│  ┌────────────────────────────────▼─────────────────────────────────────┐   │
│  │                         数据层 / Data Layer                             │   │
│  │                                                                        │   │
│  │  ┌───────────────────────────────────────────────────────────────┐   │   │
│  │  │                 PostgreSQL 14+ (主数据存储 / Primary Data)         │   │   │
│  │  │                                                                        │   │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │   │
│  │  │  │ assets  │ │ accounts│ │ scans   │ │ signals │ │ alerts  │   │   │   │
│  │  │  │ 资产表  │ │ 账号表  │ │ 扫描表  │ │ 信号表  │ │ 告警表  │   │   │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │   │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │   │
│  │  │  │   nhi   │ │policies │ │compliance│ │  users  │ │ audit   │   │   │   │
│  │  │  │ NHI表  │ │ 策略表  │ │ 合规表  │ │ 用户表  │ │ 审计表  │   │   │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │   │   │
│  │  └───────────────────────────────────────────────────────────────┘   │   │
│  │                                                                        │   │
│  │  ┌──────────────────┐    ┌────────────────────────────────────────┐  │   │
│  │  │  Redis 7+         │    │           OPA Engine (可选)              │  │   │
│  │  │  (缓存/会话/队列)   │    │           (Rego 策略评估)                │  │   │
│  │  │  Cache/Session/Queue│    │                                         │  │   │
│  │  └──────────────────┘    └────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                         分析引擎层 / Analysis Engine Layer              │    │
│  │                                                                        │    │
│  │  ┌─────────────────────┐         ┌─────────────────────────────┐     │    │
│  │  │ Python (默认)        │         │ Go 分析引擎 (可选)             │     │    │
│  │  │ FastAPI 内置分析      │         │ 高性能大规模威胁分析          │     │    │
│  │  │ <10,000 账号         │         │ 10,000+ 账号并发             │     │    │
│  │  └─────────────────────┘         └─────────────────────────────┘     │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                         扫描层 / Scanner Layer                         │    │
│  │                                                                        │    │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐         │    │
│  │  │  SSH   │  │  WMI   │  │ Cloud  │  │  PAM   │  │  DB    │         │    │
│  │  │ Scanner│  │Scanner │  │ IAM API│  │Scanner │  │Scanner │         │    │
│  │  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘         │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 架构说明 / Architecture Description

**客户端层（Client Layer）**
- React SPA：通过 HTTPS 与后端 REST API 通信
- API 客户端：第三方系统通过 Webhook 接收告警
- CLI 工具：自动化脚本和批量操作

**应用层（Application Layer）**
- FastAPI 异步 Web 框架
- 每个业务域独立服务模块
- API Gateway 提供统一认证、限流、日志
- 后台任务使用 asyncio +后台 worker

**数据层（Data Layer）**
- PostgreSQL：主数据存储，支持 JSONB 扩展字段
- Redis：热点数据缓存、会话存储、实时消息队列
- OPA Engine：策略评估（可选，默认使用内置 Python 策略引擎）

**分析引擎层（Analysis Engine Layer）**
- Python 引擎：默认引擎，适合中小规模
- Go 分析引擎：可选引擎，适合大规模高性能场景

**扫描层（Scanner Layer）**
- 每个扫描类型对应独立插件
- 支持 SSH/WMI/API 等多种协议

---

## 3. 模块职责与边界 / Module Responsibilities

### 3.1 后端模块划分 / Backend Module Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── assets.py        # 资产管理 API
│   │   │   ├── scans.py         # 扫描任务 API
│   │   │   ├── analysis.py      # 威胁分析 API
│   │   │   ├── alerts.py        # 告警 API
│   │   │   ├── nhi.py           # NHI API
│   │   │   ├── lifecycle.py      # 生命周期 API
│   │   │   ├── compliance.py     # 合规评估 API
│   │   │   ├── policies.py       # 策略管理 API
│   │   │   ├── users.py          # 用户管理 API
│   │   │   └── webhooks.py       # Webhook API
│   │   └── deps.py               # 依赖注入
│   │
│   ├── services/
│   │   ├── scan_scheduler.py     # 扫描调度服务
│   │   ├── threat_analyzer.py    # 威胁分析服务
│   │   ├── alert_engine.py       # 告警引擎
│   │   ├── realtime_monitor.py   # 实时监控服务
│   │   ├── lifecycle_service.py  # 账号生命周期服务
│   │   ├── compliance_service.py # 合规评估服务
│   │   ├── attck_mapper.py       # ATT&CK 映射服务
│   │   └── nhi_service.py        # NHI 服务
│   │
│   ├── scanners/
│   │   ├── base.py               # 扫描器基类
│   │   ├── ssh_scanner.py        # SSH 扫描器
│   │   ├── wmi_scanner.py        # WMI 扫描器
│   │   ├── cloud_scanner.py      # 云 IAM 扫描器
│   │   ├── pam_scanner.py        # PAM 扫描器
│   │   └── db_scanner.py         # 数据库扫描器
│   │
│   ├── models/                   # SQLAlchemy ORM 模型
│   │   ├── asset.py
│   │   ├── account.py
│   │   ├── scan.py
│   │   ├── signal.py
│   │   ├── alert.py
│   │   └── ...
│   │
│   ├── schemas/                  # Pydantic 请求/响应模型
│   │   ├── asset.py
│   │   ├── scan.py
│   │   └── ...
│   │
│   └── core/
│       ├── config.py             # 配置管理
│       ├── security.py           # JWT/AES 加密
│       ├── db.py                 # 数据库连接
│       └── middleware.py          # 中间件
│
├── go-analysis-engine/           # Go 分析引擎（可选）
│   └── cmd/engine/
│
└── alembic/                      # 数据库迁移
```

### 3.2 各模块职责 / Module Responsibilities

| 模块 / Module | 职责 / Responsibility | 边界 / Boundary |
|------------|---------------------|---------------|
| `scanners/` | 负责连接目标资产，采集账号数据 | 仅负责数据采集，不做分析 |
| `services/` | 负责业务逻辑，编排扫描、分析、告警流程 | 调用 scanners 获取数据，调用 models 存储结果 |
| `models/` | 负责数据建模和数据库操作 | 不包含业务逻辑 |
| `api/v1/` | 负责 HTTP 接口，接收请求、调用 service、返回响应 | 不包含业务逻辑，仅请求路由 |
| `core/` | 负责通用基础设施（配置、安全、日志）| 被所有模块共享 |

---

## 4. 数据模型 / Data Model

### 4.1 核心实体关系 / Core Entity Relationships

```
┌─────────────┐
│   User      │  用户
│─────────────│
│ id (PK)     │
│ username    │
│ password_hash│
│ role        │──────────┐
│ email       │          │
└─────────────┘          │
                         │
┌─────────────┐     ┌──────────────────┐
│   Asset     │────<│    Credential    │  凭据（多对一）
│─────────────│     │─────────────────│
│ id (PK)     │     │ id (PK)          │
│ name        │     │ type             │  SSH/Password/API
│ code        │     │ encrypted_data   │  AES-256 加密
│ ip_address  │     │ created_at      │
│ os_type     │     │ last_used_at    │
│ category    │     └──────────────────┘
│ credential_id│
└──────┬──────┘
       │ 1:N
       ▼
┌─────────────────────────────────────┐
│            ScanJob                  │  扫描任务
│─────────────────────────────────────│
│ id (PK)                             │
│ asset_id (FK)                       │
│ scan_type (full/incremental)        │
│ status (pending/running/completed/failed)│
│ started_at                         │
│ completed_at                       │
└──────────┬──────────────────────────┘
           │ 1:N
           ▼
┌─────────────────────────────────────┐
│            Account                  │  账号
│─────────────────────────────────────│
│ id (PK)                             │
│ asset_id (FK)                       │
│ scan_job_id (FK)                   │
│ username                           │
│ uid / sid                          │
│ primary_gid                        │
│ shell                              │
│ home_dir                           │
│ is_admin (bool)                   │
│ sudo_config (JSONB)                │
│ account_status (enabled/disabled)  │
│ last_login                         │
│ account_type (system/user/service)  │
│ is_nhi (bool)                     │
│ lifecycle_status (active/dormant/departed)│
│ lifecycle_updated_at               │
│ created_at                         │
│ updated_at                         │
└──────────┬────────────────────────┘
           │ NHI 关联
           ▼
┌─────────────────────────────────────┐
│           NHIRecord                 │  NHI 记录
│─────────────────────────────────────│
│ id (PK)                             │
│ account_id (FK)                    │
│ nhi_type (service/cloud/cicd...)   │
│ owner_email                        │
│ credential_identifier              │
│ rotation_days                      │
│ rotation_due_date                  │
│ risk_score                         │
└─────────────────────────────────────┘
           │
           │ 产生
           ▼
┌─────────────────────────────────────┐
│         ThreatSignal                │  威胁信号
│─────────────────────────────────────│
│ id (PK)                             │
│ analysis_job_id (FK)               │
│ account_id (FK)                    │
│ layer (semiotics/ontology/...)     │
│ level (critical/high/medium/low)  │
│ title_key                          │
│ mitre_tactic                       │
│ mitre_technique                    │
│ confidence (float)                 │
│ description                        │
│ evidence (JSONB)                   │
│ remediation                        │
│ created_at                         │
└─────────────────────────────────────┘
           │ 触发
           ▼
┌─────────────────────────────────────┐
│           Alert                      │  告警
│─────────────────────────────────────│
│ id (PK)                             │
│ asset_id (FK)                      │
│ signal_id (FK)                     │
│ level (critical/high/medium/low)  │
│ title (Chinese text)               │
│ message (Chinese text)             │
│ title_key (i18n key)              │──→ 用于前端多语言
│ title_params (JSONB)              │
│ message_key (i18n key)           │
│ message_params (JSONB)            │
│ status (new/acknowledged/responded/dismissed)│
│ created_at                         │
└─────────────────────────────────────┘
```

### 4.2 索引设计 / Index Design

| 表名 / Table | 索引 / Index | 用途 / Purpose |
|------------|-------------|--------------|
| `accounts` | `(asset_id, scan_job_id)` | 快速查询某资产某次扫描的账号 |
| `accounts` | `(account_type, is_nhi)` | NHI 筛选 |
| `accounts` | `(lifecycle_status, last_login)` | 生命周期状态查询 |
| `threat_signals` | `(analysis_job_id, level)` | 分析结果按级别筛选 |
| `threat_signals` | `(mitre_tactic, mitre_technique)` | ATT&CK 战术技术查询 |
| `alerts` | `(status, level, created_at)` | 告警列表和统计查询 |
| `scans` | `(asset_id, status, started_at)` | 扫描历史查询 |

---

## 5. API 设计规范 / API Design Conventions

### 5.1 REST 风格 / REST Conventions

```
资源命名:  /api/v1/{resource_name}
复数形式:  /api/v1/assets (不是 /api/v1/asset)
嵌套资源:  /api/v1/assets/{id}/accounts
动作:      POST /api/v1/scans/{id}/cancel
过滤:      GET /api/v1/alerts?level=critical&status=new
分页:      GET /api/v1/assets?page=1&page_size=20
```

### 5.2 版本策略 / Versioning Strategy

- 当前版本：`/api/v2`
- 不兼容变更：升版本号（`/api/v3`）
- 兼容变更（如新增字段）：在同一版本内进行
- 旧版本：提供 6 个月过渡期

### 5.3 认证授权 / Authentication & Authorization

```
JWT Token 结构:
{
  "sub": user_id,
  "role": "admin|operator|viewer",
  "exp": expiry_timestamp,
  "iat": issued_at_timestamp
}

RBAC 权限矩阵:
                    Admin   Operator  Viewer
资产 CRUD             ✅       ❌       ❌
扫描操作              ✅       ✅       ❌
告警响应              ✅       ✅       ❌
用户管理              ✅       ❌       ❌
策略管理              ✅       ✅       ❌
只读（所有资源）       ✅       ✅       ✅
```

---

## 6. 安全设计 / Security Design

### 6.1 数据安全 / Data Security

| 安全措施 / Measure | 实现 / Implementation |
|------------------|----------------------|
| 传输加密 / In Transit | TLS 1.2+ 强制，HTTP Strict Transport Security |
| 存储加密 / At Rest | PostgreSQL 透明数据加密（TDE），或文件系统级加密 |
| 凭据加密 / Credential Encryption | AES-256-GCM，`ACCOUNTSCAN_MASTER_KEY` 环境变量管理密钥 |
| JWT 安全 / JWT Security | HS256 签名，24 小时过期，支持黑名单 |
| 审计日志 / Audit Logs | 所有写操作（CREATE/UPDATE/DELETE）写入 `audit_logs` 表 |

### 6.2 凭据加密流程 / Credential Encryption Flow

```
用户输入凭据
     ↓
前端 HTTPS POST /api/v1/credentials
     ↓
后端读取 ACCOUNTSCAN_MASTER_KEY（环境变量，从密钥管理服务读取）
     ↓
AES-256-GCM 加密
     ↓
存储加密结果（ciphertext + nonce + tag）到数据库
     ↓
扫描时：后端解密 → SSH/WinRM 连接 → 返回扫描结果（不返回明文凭据）
```

### 6.3 网络安全 / Network Security

- PostgreSQL/Redis 仅监听内部 Docker 网络，不暴露到宿主机
- 前端仅通过 Nginx 反向代理访问后端
- SSH 扫描走独立网络策略，按需开放

---

## 7. 扩展性设计 / Scalability Design

### 7.1 扫描并发扩展 / Scan Concurrency Scaling

```
单实例（默认）:
  - 扫描并发数: 5（可配置到 20）
  - 适用规模: 500 台服务器

多扫描节点（扩展）:
  - 扫描节点池: 3-10 个
  - 任务分发: Redis 队列 + 多消费者
  - 适用规模: 1,000-10,000 台服务器

Go 分析引擎扩展:
  - 每个引擎实例支持 ~10,000 账号分析
  - 水平扩展 Go 分析引擎实例
  - 后端通过 round-robin 分发分析请求
```

### 7.2 缓存策略 / Caching Strategy

| 数据类型 / Data Type | 缓存策略 / Strategy | TTL |
|-------------------|------------------|-----|
| 仪表盘统计数据 | Redis Cache | 5 分钟 |
| ATT&CK 覆盖率 | Redis Cache | 1 小时 |
| 告警列表（实时性要求高）| 不缓存 | — |
| 账号列表（大结果集）| 分页缓存 | 1 分钟 |
| 用户会话 | Redis Session | 24 小时 |

### 7.3 数据库扩展 / Database Scaling

```
读写分离（Read Replica）:
  - 1 个主库（写） + 2 个从库（读）
  - 读操作路由到从库（分析查询等）
  - 写操作路由到主库（扫描结果写入等）

分表策略（未来规模>10万账号）:
  - 按 asset_id 哈希分片
  - 或按时间分片（扫描快照表）
  - 预计触发点: 账号表行数 > 5,000,000
```

---

## 8. 高可用设计 / High Availability Design

### 8.1 服务级别 HA / Service-Level HA

| 服务 / Service | HA 方案 / HA Method | RTO | RPO |
|--------------|-------------------|-----|-----|
| 后端 API / Backend API | 多实例 + Nginx 负载均衡 | < 30s | 0 |
| PostgreSQL | 主备复制（Async）| < 5 min | < 5 min |
| Redis | 主备或集群 | < 1 min | < 1 min |
| 前端 / Frontend | 多实例 + Nginx | < 30s | 0 |
| Go 分析引擎 | 多实例 + 负载均衡 | < 1 min | 0 |

### 8.2 备份策略 / Backup Strategy

| 数据类型 / Data Type | 备份频率 / Frequency | 保留期 / Retention | 方式 / Method |
|-------------------|-------------------|-----------------|-------------|
| PostgreSQL 全量 | 每日 03:00 | 30 天 | `pg_dump` + S3 |
| PostgreSQL WAL | 每 15 分钟 | 7 天 | WAL archiving |
| 配置和密钥 | 变更时 | 90 天 | Git + 密钥管理 |
| 日志 | 每日归档 | 30 天 | 日志服务或对象存储 |

---

## 9. 技术债务与未来规划 / Technical Debt & Future Roadmap

### 9.1 当前技术债务 / Current Technical Debt

| 债务项 / Debt Item | 影响 / Impact | 优先级 / Priority |
|-----------------|-------------|-----------------|
| Webhook 重试机制不完善 | 网络异常时告警可能丢失 | 高 / High |
| 数据库迁移依赖 Alembic，缺乏自动化回滚 | 升级风险 | 中 / Medium |
| 扫描插件日志不够详细 | 问题排查困难 | 中 / Medium |
| 前端无骨架屏（Skeleton Loading）| 加载体验差 | 低 / Low |

### 9.2 未来架构演进 / Future Architecture Evolution

| 方向 / Direction | 说明 / Description | 目标版本 / Target Version |
|----------------|-------------------|----------------------|
| 图数据库引入 | 使用图数据库（NebulaGraph）存储账号关系图，支持更复杂的图查询 | v3.0 |
| 实时流处理 | 引入 Kafka，实现扫描结果的流式处理和实时分析 | v3.0 |
| 多租户 SaaS | 支持多租户隔离，为 SaaS 版本做准备 | v2.5 |
| AI LLM 集成增强 | 接入更多 LLM 提供商（Claude/Gemini），增强 AI 摘要能力 | v2.5 |

---

*Telos v2.0 | © 2026 Telos.*
