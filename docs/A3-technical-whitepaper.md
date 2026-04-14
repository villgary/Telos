# Telos 技术白皮书
# Telos Technical Whitepaper

> **文件用途 / Purpose**: 技术决策者 / CSO / CISO / 投标文件 / 技术选型参考
> **版本 / Version**: v2.0 | 中英双语

---

## 目录 / Table of Contents

1. [执行摘要 / Executive Summary](#1-执行摘要)
2. [行业背景与挑战 / Industry Background & Challenges](#2-行业背景与挑战)
3. [传统方案的局限性 / Limitations of Traditional Approaches](#3-传统方案的局限性)
4. [Telos 技术架构 / Telos Technical Architecture](#4-telos-技术架构)
5. [核心技术解析 / Core Technology Deep Dives](#5-核心技术解析)
6. [NHI 非人类身份管理方案 / NHI Management Solution](#6-nhi-非人类身份管理方案)
7. [安全生态集成 / Security Ecosystem Integration](#7-安全生态集成)
8. [性能与规模化 / Performance & Scalability](#8-性能与规模化)
9. [安全与合规 / Security & Compliance](#9-安全与合规)
10. [部署架构选项 / Deployment Architecture Options](#10-部署架构选项)
11. [总结与建议 / Conclusion & Recommendations](#11-总结与建议)

---

## 1. 执行摘要 / Executive Summary

### 1.1 文档目的 / Purpose

本白皮书面向 CSO、CISO、安全架构师和技术决策者，详细介绍 Telos 身份威胁检测与响应（ITDR）平台的技术架构、核心算法、产品能力和部署方案。

本文档旨在为技术选型提供深度参考，帮助安全团队理解 Telos 如何通过自动化账号发现、MITRE ATT&CK 威胁映射和五层 AI 威胁分析，解决现代企业面临的账号安全挑战。

### 1.2 核心主张 / Core Proposition

> **Telos 是业界首个将五层语义分析（符号层→因果层）应用于账号威胁检测的产品。** Telos 不仅仅检测账号异常，更通过深度语义分析理解异常背后的攻击意图和传播路径，帮助安全团队在攻击造成损失之前主动阻断。

### 1.3 关键价值 / Key Value

| 价值维度 / Value Dimension | 具体收益 / Specific Benefit |
|--------------------------|--------------------------|
| **检测深度 / Detection Depth** | 五层 AI 分析，覆盖符号伪装到因果链路的完整攻击路径 |
| **覆盖广度 / Coverage Breadth** | 一站式覆盖 SSH/Windows/云 IAM/PAM/数据库所有账号来源 |
| **响应速度 / Response Speed** | MTTD 从 207 天缩短至 <24 小时；MTTR 从 69 天缩短至 <2 小时 |
| **合规支撑 / Compliance Support** | SOC2 / ISO27001 / 等保 2.0 一键评估，自动化报告 |
| **部署便捷 / Deployment Ease** | All-in-One Docker 部署，小时级上线 |

### 1.4 目标读者 / Target Audience

- CSO / CISO：评估整体安全架构和投资回报
- 安全架构师：评估技术可行性和集成方案
- 安全运营团队：理解检测能力和告警机制
- IT 运维团队：评估部署需求和运维复杂度
- 合规团队：评估合规自动化能力

---

## 2. 行业背景与挑战 / Industry Background & Challenges

### 2.1 身份安全的新威胁格局 / The New Identity Security Threat Landscape

传统的网络安全以网络边界为核心，依赖防火墙和 VPN 构建安全边界。然而，云计算、远程办公和 DevOps 的普及使网络边界日趋模糊。根据 Verizon DBIR 2024 报告：

- **82%** 的数据泄露涉及被盗凭据（Compromised Credentials）
- **39%** 的泄露涉及 Web 应用攻击，而 Web 攻击的核心路径往往是通过服务账号的横向移动
- **平均数据泄露成本**已达 $488 万美元（IBM Cost of a Data Breach Report 2024）

### 2.2 账号资产的复杂性 / Complexity of Account Assets

现代企业的账号资产呈现以下特点：

**多源性 / Multi-Source:**
```
大型企业典型账号分布：
├── Linux/Unix 服务器（1000+ 台）→ SSH 账号 5000+
│   ├── 系统账号（root, daemon, bin...）
│   ├── 应用服务账号（oracle, mysql, nginx...）
│   └── 普通用户账号
├── Windows 服务器（500+ 台）→ WMI/WinRM 账号 2000+
│   ├── AD 域账号
│   ├── 本地管理员账号
│   └── 服务账号（managed service accounts）
├── 云平台（AWS / 阿里云 / 腾讯云）→ IAM 账号 3000+
│   ├── IAM 用户（含 Access Key）
│   ├── IAM 角色（Assume Role）
│   └── 服务账号（Service Account）
├── PAM 特权访问系统 → 特权审批账号 500+
├── 数据库（MySQL / PostgreSQL / Redis）→ 500+
└── CI/CD 流水线 → API Key / Token 1000+
```

**估算规模 / Estimated Scale:**
一个 3000 人规模的中大型企业，账号总量通常在 **50,000 至 200,000** 之间，其中 **NHI（非人类身份）占比超过 60%**。

### 2.3 当前面临的核心挑战 / Core Challenges

| 挑战 / Challenge | 描述 / Description | 影响 / Impact |
|----------------|-------------------|---------------|
| **底数不清 / Unknown Inventory** | 各团队独立管理，无统一清单 | 影子账号横行，攻击面不透明 |
| **僵尸账号 / Zombie Accounts** | 离职/项目结束账号未及时清理 | 永久凭证被攻击者利用 |
| **NHI 爆炸 / NHI Explosion** | CI/CD、云函数、K8s Service Account 爆发 | 最大攻击面无人看管 |
| **告警疲劳 / Alert Fatigue** | 大量噪声告警，关键信号被淹没 | MTTD 居高不下 |
| **攻击路径不可见 / Invisible Attack Paths** | 看不到账号间的信任关系 | 横向移动检测失效 |
| **合规负担 / Compliance Burden** | 人工整理合规证据，效率低下 | 审计周期长，成本高 |

---

## 3. 传统方案的局限性 / Limitations of Traditional Approaches

### 3.1 堡垒机（Jump Server / Bastion）的局限

传统堡垒机聚焦于**访问控制和审计**，而非威胁检测：

| 能力 / Capability | 堡垒机 / Bastion | Telos |
|-----------------|----------------|-------|
| 账号发现 / Account Discovery | ❌ 手动录入 | ✅ 自动扫描 |
| 威胁检测 / Threat Detection | ❌ 仅事后审计日志 | ✅ 实时检测 |
| ATT&CK 映射 / ATT&CK Mapping | ❌ 不支持 | ✅ 原生支持 |
| 横向移动分析 / Lateral Movement Analysis | ❌ 不支持 | ✅ 支持 |
| NHI 管理 / NHI Management | ❌ 不支持 | ✅ 原生支持 |
| 攻击路径模拟 / Attack Path Simulation | ❌ 不支持 | ✅ 支持 |

**核心问题 / Core Issue:** 堡垒机是"事后审计"工具，无法主动发现账号层面的威胁，更无法感知账号间的信任关系和攻击路径。

### 3.2 身份治理（IGA）的局限

身份治理与管理（IGA）产品（如 SailPoint、Saviynt）主要解决身份生命周期合规问题，但：

| 能力 / Capability | IGA | Telos |
|----------------|-----|-------|
| 账号发现 / Account Discovery | ⚠️ 半自动同步 | ✅ 主动扫描 |
| 威胁检测 / Threat Detection | ⚠️ 规则引擎 | ✅ 五层 AI |
| ATT&CK 映射 / ATT&CK Mapping | ⚠️ 弱支持 | ✅ 原生支持 |
| NHI 管理 / NHI Management | ⚠️ 弱支持 | ✅ 深度管理 |
| 部署复杂度 / Deployment Complexity | ❌ 高（6-12个月） | ✅ 低（小时级）|
| 横向移动检测 / Lateral Movement | ⚠️ 部分支持 | ✅ 支持 |

**核心问题 / Core Issue:** IGA 以"身份合规"为核心，不具备威胁检测视角，无法识别账号命名伪装、SSH 密钥复用等攻击技术。

### 3.3 EDR 的局限

EDR 聚焦于终端行为检测，但：

- EDR 以**主机进程行为**为核心，不分析**账号语义**
- 无法理解账号命名中的字符伪装（`r00t`/`ladmin`）
- 无法分析跨主机的账号信任关系
- 对 Linux 账号的检测能力普遍偏弱

**结论 / Conclusion:** 需要专门的 ITDR（Identity Threat Detection & Response）产品来填补账号安全领域的空白。

---

## 4. Telos 技术架构 / Telos Technical Architecture

### 4.1 整体架构 / Overall Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Telos 技术架构 / Telos Architecture         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  前端 / Frontend (React + Ant Design)     │   │
│  │   仪表盘 | ATT&CK 覆盖率 | 威胁分析 | 告警 | NHI | 合规   │   │
│  └────────────────────────────┬─────────────────────────────┘   │
│                                │ HTTPS (REST API)                │
│  ┌────────────────────────────▼─────────────────────────────┐   │
│  │              应用层 / Application Layer (Python FastAPI)    │   │
│  │                                                              │   │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │   │
│  │  │ 扫描调度 │  │ 威胁分析  │  │ 告警引擎  │  │  策略评估  │    │   │
│  │  │ Scanner │  │ Analyzer │  │  Alert   │  │  Policy  │    │   │
│  │  │ Scheduler│  │ Engine  │  │  Engine  │  │ Evaluator│    │   │
│  │  └─────────┘  └──────────┘  └──────────┘  └──────────┘    │   │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │   │
│  │  │ 用户/权限│  │ 账号生命周期│ │ 实时监控  │  │ 合规评估  │    │   │
│  │  │  User/  │  │  Account  │  │ Realtime │  │Compliance│    │   │
│  │  │  RBAC   │  │ Lifecycle │  │ Monitor  │  │ Assessor │    │   │
│  │  └─────────┘  └──────────┘  └──────────┘  └──────────┘    │   │
│  └────────────────────────────┬─────────────────────────────┘   │
│                               │                                   │
│  ┌────────────────────────────▼─────────────────────────────┐   │
│  │               数据层 / Data Layer (PostgreSQL 14+)          │   │
│  │  资产 | 账号 | 扫描结果 | 威胁信号 | 告警 | 策略 | NHI | 用户  │   │
│  └───────────────────────────────────────────────────────────┘   │
│                               │                                   │
│  ┌──────────────┐  ┌──────────▼──────────┐  ┌──────────────────┐  │
│  │    Redis     │  │  Go 分析引擎        │  │   OPA Policy     │  │
│  │ 缓存/消息队列 │  │   (可选 / Optional)  │  │   Engine (Rego)  │  │
│  │ Cache/Queue  │  │   高性能威胁分析      │  │   策略规则评估    │  │
│  └──────────────┘  └─────────────────────┘  └──────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                  扫描插件层 / Scanner Plugin Layer           │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │   │
│  │  │  SSH   │ │  WMI   │ │ Cloud  │ │  PAM   │ │  DB    │   │   │
│  │  │ Scanner│ │Scanner │ │ IAM API│ │Scanner │ │Scanner │   │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 技术栈 / Technology Stack

| 组件 / Component | 技术选型 / Technology | 说明 / Description |
|-----------------|---------------------|-------------------|
| 前端 / Frontend | React 18 + Ant Design 5 | 企业级 UI 组件库 |
| 后端 / Backend | Python 3.11+ / FastAPI | 高性能异步 API |
| 数据库 / Database | PostgreSQL 14+ | 主数据存储，支持 JSONB |
| 缓存/队列 / Cache/Queue | Redis 7+ | 缓存、会话、实时消息 |
| 分析引擎 / Analysis Engine | Go 分析引擎 | 可选，高性能威胁分析 |
| 策略引擎 / Policy Engine | OPA (Rego) | 声明式策略评估 |
| 实时监控 / Realtime Monitor | asyncio + 后台任务 | 扫描后实时告警 |
| 部署 / Deployment | Docker Compose / K8s | 容器化部署 |

### 4.3 各层职责 / Layer Responsibilities

**4.3.1 前端展示层 / Frontend Presentation Layer**

职责：
- 提供用户交互界面（React SPA）
- 渲染仪表盘、ATT&CK 可视化、告警列表
- 管理前端 i18n（中英文切换）
- SSE 实时接收告警推送

技术要点：
- Ant Design 5 组件库（企业级设计语言）
- ECharts / G2Plot 可视化图表
- React Query 数据获取与缓存
- react-i18next 多语言支持

**4.3.2 应用层 / Application Layer**

职责：
- REST API 提供所有业务功能
- 扫描任务调度（支持 Cron 定时）
- 威胁分析结果聚合
- 告警生成与分发
- 用户认证与 RBAC 权限控制

关键 API 模块：

| 模块 / Module | 端点前缀 / Prefix | 功能 / Function |
|-------------|-----------------|----------------|
| 资产 / Assets | `/api/v1/assets` | 资产管理 CRUD |
| 扫描 / Scans | `/api/v1/scans` | 扫描任务管理 |
| 分析 / Analysis | `/api/v1/analysis` | 威胁分析触发与结果 |
| 告警 / Alerts | `/api/v1/alerts` | 告警查询与响应 |
| NHI | `/api/v1/nhi` | NHI 全生命周期管理 |
| 合规 / Compliance | `/api/v1/compliance` | 合规评估与报告 |
| 策略 / Policies | `/api/v1/policies` | OPA 策略管理 |
| 账号 / Accounts | `/api/v1/accounts` | 账号详情查询 |
| 用户 / Users | `/api/v1/users` | 用户管理与认证 |

**4.3.3 数据存储层 / Data Storage Layer**

PostgreSQL 核心数据模型：

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│   Asset    │────<│   Account  │────<│ ScanResult │
│   资产      │     │   账号      │     │  扫描结果   │
└────────────┘     └────────────┘     └────────────┘
       │                  │                   │
       │                  │                   │
┌──────▼──────┐    ┌──────▼──────┐     ┌──────▼──────┐
│ ThreatSignal│    │AccountOwner │     │ Alert       │
│  威胁信号    │    │  账号归属人  │     │  告警       │
└────────────┘    └────────────┘     └────────────┘
       │
┌──────▼──────┐
│   NHIRecord │
│   NHI记录   │
└────────────┘
```

**4.3.4 扫描插件层 / Scanner Plugin Layer**

每个扫描插件对应一种账号来源：

| 插件 / Plugin | 协议 / Protocol | 扫描内容 / Content |
|-------------|----------------|------------------|
| SSH Scanner | SSH (Key/Password/GSSAPI) | /etc/passwd, /etc/shadow, sudoers, SSH authorized_keys |
| WMI Scanner | WMI / WinRM | Win32_UserAccount, LocalGroupMembership |
| Cloud IAM Scanner | 云平台 REST API | AWS IAM / 阿里云 RAM / 腾讯云 CAM |
| PAM Scanner | REST API | 特权账号、特权审批记录 |
| DB Scanner | DB Connection | MySQL user, PostgreSQL pg_roles, Redis ACL |

### 4.4 数据流 / Data Flow

```
[资产注册]
 Asset Registration
        ↓
[扫描触发] ──→ [扫描插件执行]
 Scan Trigger     Scanner Plugins
        ↓                  ↓
[扫描结果入库] ←── [结果规范化]
 Results Stored    Result Normalization
        ↓
[账号合并去重] ──→ [Diff 检测变更]
 Account Merge      Diff Detection
        ↓                  ↓
[五层威胁分析] ──→ [威胁信号输出]
 5-Layer Analysis    Threat Signals
        ↓
[ATT&CK 映射] ──→ [信号入库]
 ATT&CK Mapping      Signal Storage
        ↓
[告警判断] ──→ [告警生成 + 通知]
 Alert Evaluation    Alert + Notification
        ↓
[仪表盘展示] ──→ [报表生成]
 Dashboard           Report Generation
```

---

## 5. 核心技术解析 / Core Technology Deep Dives

### 5.1 五层 AI 威胁分析模型 / Five-Layer AI Threat Analysis Model

Telos 的五层分析模型是业界首个将语义分析引入账号安全的产品创新。每一层对应一种威胁分析视角，由浅入深。

**5.1.1 第一层：符号层（Semiotics Layer）**

**分析对象：** 账号的命名符号本身

**威胁假设：** 攻击者常通过符号伪装来隐藏恶意账号，符号层分析检测这些伪装模式：

| 攻击模式 / Attack Pattern | 示例 / Example | 检测方法 / Detection |
|------------------------|---------------|---------------------|
| 字符替换 / Character substitution | `r00t`, `l admin`, `admín` | Unicode 视觉相似字符检测 |
| 数字混淆 / Number混淆 | `admin1`, `root2`, `test001` | 常见账号+数字序列检测 |
| 特殊符号混入 / Symbol injection | `_admin`, `admin_`, `root.` | 账号名结构异常检测 |
| 匿名命名 / Anonymized naming | `_svc_`, `____`, `xXx` | 无意义短名称检测 |
| 系统账号伪装 / System account impersonation | `daem0n`, `bin_` | 已知系统账号变体检测 |

**技术实现：** 基于字符级别的相似度计算，结合 Unicode 规范（IDN 同形异义攻击）和常见伪装规则库。

**5.1.2 第二层：本体层（Ontology Layer）**

**分析对象：** 账号的身份本体——即账号与真实人员/实体的关联关系

**威胁假设：** 孤立、无关联的特权账号往往是攻击者建立的后门或被遗忘的影子账号：

| 攻击模式 / Attack Pattern | 示例 / Example | 检测方法 / Detection |
|------------------------|---------------|---------------------|
| 影子账号 / Shadow accounts | 特权账号无任何人员关联 | AD/LDAP 交叉验证 |
| 孤儿账号 / Orphan accounts | 服务账号的负责人已离职 | 人员状态 + 账号归属链 |
| 角色混淆 / Role confusion | 同名账号存在于多台资产但权限差异大 | 聚类分析 |
| 虚假服务账号 / Fake service accounts | 普通用户账号被用于服务运行 | Shell 类型 + 登录行为交叉 |

**技术实现：** 构建账号-人员-资产-权限四元关系图谱，使用图数据库查询（PostgreSQL 递归 CTE）识别孤立节点。

**5.1.3 第三层：认知层（Cognitive Layer）**

**分析对象：** 账号的使用模式与正常行为基线的偏差

**威胁假设：** 人的认知存在盲点，导致安全策略的偏差，认知层分析这些偏差：

| 认知偏差类型 / Cognitive Bias Type | 示例 / Example | 检测方法 / Detection |
|----------------------------------|---------------|---------------------|
| 确认偏差 / Confirmation bias | 服务账号配置了交互式 Shell（`/bin/bash`），运维认为"一直是这样" | Shell 类型 vs. 账号类型匹配度 |
| 光环效应 / Halo effect | root 账号一直被使用，无人质疑 | root 登录频率异常检测 |
| 正常化偏差 / Normalization of deviance | NOPASSWD sudo 配置被逐步扩大使用范围 | Sudoers 配置变更 Diff |
| 可用性偏差 / Availability bias | 大量测试账号存在，被认为"偶尔用用没关系" | 账号活跃度与配置匹配度 |

**技术实现：** 基于历史行为数据建立账号行为基线，检测偏离基线的异常模式。

**5.1.4 第四层：人类学层（Anthropology Layer）**

**分析对象：** 账号的组织关系——信任链、权限簇和身份隔离

**威胁假设：** 攻击者利用组织关系中的信任链进行横向移动，人类学层分析这些关系：

| 关系类型 / Relationship Type | 威胁 / Threat | 检测方法 / Detection |
|----------------------------|-------------|---------------------|
| 信任链 / Trust chain | A 主机到 B 主机的 SSH 信任，攻击者可利用 | SSH known_hosts + authorized_keys 分析 |
| 权限簇 / Privilege cluster | 一组账号共享相似的高危权限集 | 聚类分析相似权限模式 |
| 人机混用 / Human-machine mixing | 同一个人使用多个高危服务账号 | 账号归属人交叉分析 |
| 身份隔离缺失 / Identity isolation failure | 不同业务系统使用相同的服务账号 | 跨资产账号共享分析 |

**技术实现：** 构建权限相似度矩阵，使用 K-Means 聚类识别异常权限簇，结合归属人图谱分析人机混用风险。

**5.1.5 第五层：因果层（Causal Layer）**

**分析对象：** 账号间的因果关系——权限提升路径、因果中枢和沉睡特权链

**威胁假设：** 攻击者不只利用单个账号的弱点，而是沿着因果链逐步提升权限：

| 因果威胁类型 / Causal Threat Type | 描述 / Description | 检测算法 / Algorithm |
|--------------------------------|-------------------|---------------------|
| 权限提升路径 / Privilege escalation path | A 账号 → B 账号 → Admin 的权限提升链 | BFS 图搜索 |
| 因果中枢 / Causal hub | 被多个账号依赖的高权限账号 | PageRank 类算法 |
| 沉睡特权链 / Dormant privilege chain | 长期不活跃账号突然活跃的权限链 | 时序分析 + 图搜索 |
| SSH 密钥复用传播 / SSH key reuse propagation | 通过 SSH authorized_keys 横向扩散 | 图可达性分析 |

**技术实现：**
```python
# 伪代码：权限提升路径 BFS 搜索
def find_privilege_escalation_paths(start_account, max_hops=5):
    queue = [(start_account, [start_account])]
    while queue:
        current, path = queue.pop(0)
        if is_privileged(current) and len(path) > 1:
            yield path  # 发现一条路径
        if len(path) <= max_hops:
            for neighbor in get_neighbors(current):
                if neighbor not in path:
                    queue.append((neighbor, path + [neighbor]))
```

**分析引擎选择：**
- **Python FastAPI（默认）：** 灵活性强，适合中小规模（<10,000 账号）
- **Go 分析引擎（可选）：** 高性能 BFS/DFS，图算法优化，支持 10,000+ 账号并发分析

### 5.2 ATT&CK 框架映射方法 / ATT&CK Framework Mapping Method

**5.2.1 映射策略 / Mapping Strategy**

Telos 将每条威胁信号（Threat Signal）自动映射到 MITRE ATT&CK Framework，版本支持 v14+。

**映射规则 / Mapping Rules:**

| 威胁信号 / Signal | ATT&CK 技术 / ATT&CK Technique | ATT&CK 战术 / Tactic |
|-----------------|------------------------------|---------------------|
| 普通账号突获 sudo 权限 | T1078.003（本地账号） | TA0004 权限提升 |
| NOPASSWD sudo 配置存在 | T1552.001（明文凭证） | TA0006 凭据访问 |
| SSH 密钥复用（跨主机）| T1021.004（SSH） | TA0008 横向移动 |
| 新增特权账号 | T1078（有效账号） | TA0001 初始访问 / TA0003 持久化 |
| 服务账号配置交互 Shell | T1548.001（sudo 滥用） | TA0004 权限提升 |
| 孤儿特权账号 | T1078（有效账号滥用） | TA0003 持久化 |
| 凭据泄露文件发现 | T1552（凭据访问） | TA0006 凭据访问 |

**5.2.2 ATT&CK Navigator Layer 导出 / Export ATT&CK Navigator Layer**

每条信号包含以下元数据，支撑 Navigator Layer 导出：

```json
{
  "signal_id": "sig_001",
  "mitre_tactic": "TA0004",
  "mitre_technique": "T1078.003",
  "confidence": 0.85,
  "affected_accounts": ["user1", "user2"],
  "affected_assets": ["asset_001", "asset_002"],
  "first_seen": "2026-04-10T08:00:00Z",
  "severity": "high",
  "evidence": {
    "detail": "Account 'bob' added to sudo group on server-01",
    "scan_job_id": 42
  }
}
```

导出文件格式符合 ATT&CK Navigator v4.x schema，可直接导入 https://mitre-attack.github.io/attack-navigator/

### 5.3 账号 Diff 引擎 / Account Diff Engine

**5.3.1 设计目标 / Design Goals**

扫描结果与历史快照对比，检测增量变更：

| 变更类型 / Change Type | 风险级别 / Risk Level | 说明 / Description |
|----------------------|---------------------|-------------------|
| 新增账号 / New account | 🟡 中危 | 潜在未授权账号 |
| 删除账号 / Deleted account | 🟢 低危 | 可能是正常清理 |
| 权限提升 / Privilege escalation | 🔴 高危 | 普通→管理员 |
| 权限降级 / Privilege de-escalation | 🔵 低危 | 可能是正常处置 |
| 配置变更 / Config change | 🟡 中危 | Shell/状态变更 |
| NOPASSWD 新增 / NOPASSWD added | 🔴 严重 | 高危 sudo 配置 |
| SSH 密钥变更 / SSH key change | 🔴 高危 | 潜在横向移动准备 |

**5.3.2 Diff 算法 / Diff Algorithm**

```sql
-- 伪代码：账号 Diff SQL
WITH current_scan AS (
    SELECT username, uid, gid, shell, sudo_config, is_admin
    FROM accounts WHERE scan_id = :current_scan_id
),
previous_scan AS (
    SELECT username, uid, gid, shell, sudo_config, is_admin
    FROM accounts WHERE scan_id = :previous_scan_id
)
SELECT
    c.username,
    CASE
        WHEN p.username IS NULL THEN 'NEW'
        WHEN c.is_admin AND NOT p.is_admin THEN 'PRIV_ESCALATION'
        WHEN NOT c.is_admin AND p.is_admin THEN 'PRIV_DEESCALATION'
        WHEN c.sudo_config IS DISTINCT FROM p.sudo_config THEN 'CONFIG_CHANGE'
        ELSE 'UNCHANGED'
    END AS change_type,
    c.*, p.*
FROM current_scan c
FULL OUTER JOIN previous_scan p USING (username);
```

### 5.4 风险传播算法 / Risk Propagation Algorithm

**5.4.1 设计动机 / Motivation**

子资产的高风险可传播到父资产，形成风险累积：

```
机架 (Rack A)          风险: 10
  └── 服务器 (Web-01)   风险: 60 ← 某账号被攻陷
  └── 服务器 (Web-02)   风险: 30
  └── 服务器 (DB-01)    风险: 90 ← 高危账号存在
机架 (Rack B)          风险: 45
  └── ...
```

**5.4.2 传播算法 / Propagation Algorithm**

```python
def propagate_risk(asset_graph):
    """自底向上传播风险"""
    # 1. 初始化叶子节点风险为账号风险之和
    leaf_risks = compute_account_risks(leaf_assets)

    # 2. 自底向上传播
    for node in get_nodes_bottom_up(asset_graph):
        child_risks = [child.risk for child in node.children]
        node.risk = max(
            compute_asset_inherent_risk(node),
            max(child_risks) * propagation_factor  # 子资产最大风险 * 传播系数
        )

    return asset_graph
```

---

## 6. NHI 非人类身份管理方案 / NHI Management Solution

### 6.1 NHI 定义与分类 / NHI Definition & Classification

NHI（Non-Human Identity，非人类身份）是指不由自然人直接持有的凭据和账号，主要包括：

| 类型 / Type | 说明 / Description | 典型凭据 / Typical Credentials |
|-----------|-------------------|---------------------------|
| Service Account | 进程/服务运行使用的账号 | Linux 服务账号、Windows MSA |
| System Account | 操作系统内置账号 | root, SYSTEM, Administrator |
| Cloud IAM | 云平台身份与访问管理 | AWS IAM Role, Access Key |
| CI/CD Credential | 流水线凭据 | GitHub Token, Jenkins Credential |
| Application Account | 应用间调用账号 | API Key, OAuth Client |
| Workload Identity | K8s/Docker 工作负载身份 | K8s Service Account Token |
| AI Agent Credential | AI Agent 使用的凭据 | LLM API Key, Agent Token |
| Database Account | 数据库访问账号 | MySQL/PostgreSQL 用户 |
| Unknown | 未能自动分类的账号 | 待人工审查 |

### 6.2 NHI 生命周期管理 / NHI Lifecycle Management

```
[创建 / Creation]
  ↓
[登记 / Registration] ← 发现账号 → 自动/手动登记
  ↓
[分配归属人 / Owner Assignment] ← 可关联到人员或业务系统
  ↓
[监控 / Monitoring] ← 活跃度 + 风险评分 + 轮换状态
  ↓
[轮换 / Rotation] ← 提醒触发 → 人工/自动轮换
  ↓
[退役 / Retirement] ← 关联服务下线 → 账号清理
```

### 6.3 NHI 风险评分模型 / NHI Risk Scoring Model

```
NHI_Risk_Score = f(
    权限级别 × 0.3,         # 权限权重
    轮换周期合规性 × 0.2,    # 轮换合规
    归属人明确性 × 0.2,      # 归属人是否清晰
    活跃度异常 × 0.15,       # 异常活跃
    配置风险 × 0.15          # NOPASSWD 等危险配置
)
```

---

## 7. 安全生态集成 / Security Ecosystem Integration

### 7.1 SIEM 集成 / SIEM Integration

Telos 通过 Webhook 将告警推送到主流 SIEM 系统：

**支持的 SIEM 产品 / Supported SIEM Products:**
- Splunk (HEC → Index)
- Elastic (→ Elasticsearch Index via webhook)
- IBM QRadar (→ Log Management)
- 奇安信 NGSOC
- 阿里云 SLS（日志服务）
- 腾讯云 CLS（日志服务）

**Webhook 格式 / Webhook Format:**
```json
POST /webhook
{
  "alert_id": 12345,
  "level": "critical",
  "title_key": "alert.credential_leak",
  "title_params": {"username": "root", "asset_id": 5},
  "message_key": "alert.msg.credential_leak",
  "message_params": {
    "username": "root",
    "file_count": 3,
    "asset_name": "web-server-01"
  },
  "asset_id": 5,
  "created_at": "2026-04-12T10:00:00Z"
}
```

### 7.2 SOAR 集成 / SOAR Integration

Webhook 可被 SOAR 系统接收并触发自动化处置剧本：

| 告警类型 / Alert Type | SOAR 剧本动作 / SOAR Playbook Action |
|---------------------|-----------------------------------|
| 新增管理权限 / New admin privilege | 自动创建 ServiceNow 工单 |
| NOPASSWD sudo 新增 | 自动发送 Slack 通知安全团队 |
| 敏感凭据泄露 / Credential leak | 自动禁用相关账号（需审批）|
| 孤儿特权账号 / Orphan privileged | 自动标记待审查 + 发送邮件 |

### 7.3 PAM 集成 / PAM Integration

Telos 支持与主流 PAM 系统集成，实现账号比对：

| PAM 产品 / PAM Product | 集成方式 / Method | 账号比对 / Comparison |
|----------------------|----------------|---------------------|
| 腾讯云 PAM | REST API (Bearer Token) | 账号匹配、合规差距分析 |
| 阿里云 PAM | REST API (API Key) | 同上 |
| CyberArk | REST API | 同上 |
| 自定义 PAM | REST API (Bearer/Basic Auth) | 同上 |

**比对结果类型 / Comparison Result Types:**
- ✅ **合规（Matched）：** PAM 与 Telos 一致
- ⚠️ **特权差距（Privileged Gap）：** PAM 有但 Telos 无，或反之
- ❌ **未匹配（Unmatched PAM）：** PAM 中的账号在 Telos 中不存在

### 7.4 SSO / LDAP 集成 / SSO / LDAP Integration

- 支持 LDAP / Active Directory 用户同步
- 支持 SAML 2.0 / OIDC SSO 集成
- 用户属性（姓名、邮箱、部门）自动从 LDAP 同步

### 7.5 开放 API / Open API

Telos 提供完整的 RESTful API，支持：

- 全量 CRUD 操作（资产、账号、扫描、告警等）
- Webhook 回调注册
- API Key 认证（支持细粒度权限控制）
- OpenAPI 3.0 规范文档（Swagger UI / ReDoc）

---

## 8. 性能与规模化 / Performance & Scalability

### 8.1 性能基准 / Performance Benchmarks

| 场景 / Scenario | 规模 / Scale | 耗时 / Duration |
|----------------|------------|---------------|
| 单台 Linux 服务器扫描 / Single Linux server scan | 200 账号 | < 5 秒 |
| 100 台 Linux 服务器并发扫描 / 100 Linux servers concurrent scan | 20,000 账号 | < 2 分钟 |
| 全量账号威胁分析（Python 引擎）/ Full analysis (Python) | 5,000 账号 | < 30 秒 |
| 全量账号威胁分析（Go 分析引擎）/ Full analysis (Go) | 10,000 账号 | < 5 秒 |
| 权限提升路径 BFS 搜索 / Privilege escalation BFS | 10,000 账号, 深度 5 | < 10 秒 |
| 增量扫描 Diff / Incremental scan diff | 200 账号变更 | < 3 秒 |
| ATT&CK 覆盖率计算 / ATT&CK coverage calculation | 全量信号 | < 5 秒 |

### 8.2 规模化架构 / Scalability Architecture

**小规模（< 1,000 账号）：**
- All-in-One 部署（单一服务器）
- Python FastAPI 后端 + 内置分析引擎

**中规模（1,000 - 10,000 账号）：**
- 分布式部署（扫描节点 + 分析节点分离）
- 可选 Go 分析引擎提升分析性能

**大规模（10,000+ 账号）：**
- Kubernetes 水平扩展
- 扫描节点池化（根据负载自动伸缩）
- Go 分析引擎专用集群
- Redis 集群缓存热点数据

### 8.3 高可用配置 / High Availability

- **主备部署：** Active-Passive Failover，RPO < 5 分钟，RTO < 30 分钟
- **多可用区：** 支持跨 AZ 部署，数据零丢失
- **健康检查：** 每 30 秒检查所有服务组件状态

---

## 9. 安全与合规 / Security & Compliance

### 9.1 数据安全 / Data Security

| 安全措施 / Security Measure | 实现 / Implementation |
|---------------------------|----------------------|
| **传输加密** / Data in Transit | TLS 1.2+ 强制加密所有通信 |
| **存储加密** / Data at Rest | AES-256-GCM 加密敏感字段（凭据、API Key）|
| **凭据保护** / Credential Protection | `ACCOUNTSCAN_MASTER_KEY` 加密密钥单独管理 |
| **JWT 安全** / JWT Security | HS256/RS256 签名，令牌 24 小时过期 |
| **RBAC 细粒度权限** / Fine-grained RBAC | 三级角色（Admin/Operator/Viewer）+ 资源级权限 |
| **审计日志** / Audit Logs | 所有操作写入审计日志，不可篡改 |
| **会话管理** / Session Management | Redis 会话存储，支持强制下线 |

### 9.2 合规框架支持 / Compliance Framework Support

| 合规框架 / Framework | 检查项 / Checks | 支持情况 / Status |
|--------------------|---------------|----------------|
| **SOC 2** | CC6.1（共享特权账号）、CC6.3（未使用特权账号）、CC6.6（定期访问审查）| ✅ 完整支持 |
| **ISO 27001** | A.9.2.3（无密码 sudo）、A.9.4.3（特权账号比例）、A.9.2.5（认证失败处理）| ✅ 完整支持 |
| **等保 2.0** | DBAP_TS（离线资产特权）、DBAP_OA（静默管理员）、CC6.3（长期不活跃特权账号）| ✅ 完整支持 |
| **GDPR** | 账号数据处理最小化、删除权支持 | ✅ 完整支持 |

### 9.3 合规评估自动化 / Automated Compliance Assessment

```python
# 伪代码：SOC2 CC6.3 合规检查
def check_soc2_cc6_3(db, asset_ids, inactive_days=90):
    """
    CC6.3: Unused privileged accounts should be removed
    """
    inactive_privileged = db.query("""
        SELECT a.username, a.asset_id, a.last_login
        FROM accounts a
        JOIN assets ast ON a.asset_id = ast.id
        WHERE a.asset_id = ANY(:asset_ids)
          AND a.is_admin = true
          AND a.last_login < NOW() - INTERVAL ':days days'
    """, asset_ids=asset_ids, days=inactive_days)

    return ComplianceReport(
        framework="SOC2",
        control="CC6.3",
        pass_rate=1 - len(inactive_privileged) / total_privileged,
        findings=inactive_privileged,
        recommendation="Disable or remove inactive privileged accounts"
    )
```

---

## 10. 部署架构选项 / Deployment Architecture Options

### 10.1 All-in-One 单机部署 / All-in-One Single Server

**适用场景：** 快速验证 / 小规模（< 500 账号）

```
┌──────────────────────────────────┐
│        单台服务器 (4C/8GB)         │
│  ┌─────────┐  ┌────────────────┐ │
│  │   App   │  │  PostgreSQL    │ │
│  │ (FastAPI)│  │    (Data)      │ │
│  └─────────┘  └────────────────┘ │
│  ┌─────────┐  ┌────────────────┐ │
│  │ Frontend│  │     Redis      │ │
│  │(React)  │  │  (Cache/Queue) │ │
│  └─────────┘  └────────────────┘ │
└──────────────────────────────────┘
```

**部署命令：**
```bash
git clone https://github.com/telos-project/telos.git
cd accountscan
cp .env.example .env
# 配置 .env 中的必填参数
docker compose up -d
```

### 10.2 分布式部署 / Distributed Deployment

**适用场景：** 中大规模（500 - 10,000 账号）

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  扫描节点1  │    │  扫描节点2  │    │  扫描节点N  │
│ (Scanner)  │    │ (Scanner)  │    │ (Scanner)  │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │ 网络
       ┌──────────────────▼──────────────────┐
       │          中央 API 集群                 │
       │  ┌─────────┐  ┌─────────────────┐   │
       │  │ FastAPI │  │ Go 分析引擎   │   │
       │  │ (×2)    │  │    (×2)         │   │
       │  └─────────┘  └─────────────────┘   │
       │  ┌─────────┐  ┌─────────────────┐   │
       │  │Frontend │  │  PostgreSQL     │   │
       │  │(×2)    │  │  (主备)          │   │
       │  └─────────┘  └─────────────────┘   │
       │  ┌─────────┐  ┌─────────────────┐   │
       │  │  Redis  │  │   Nginx          │   │
       │  │ Cluster │  │  (Load Balancer)│   │
       │  └─────────┘  └─────────────────┘   │
       └─────────────────────────────────────┘
```

### 10.3 Kubernetes 部署 / Kubernetes Deployment

**适用场景：** 大规模（10,000+ 账号）、需弹性伸缩

Helm Chart 支持以下组件水平扩展：
- `app`（FastAPI）：HPA 基于 CPU/内存
- `go-analysis-engine`（Go）：HPA 基于扫描队列深度
- `scanner`（扫描节点）：按需调度
- `postgres`（Operator）：建议使用云厂商托管 RDS

### 10.4 网络要求 / Network Requirements

| 端口 / Port | 方向 / Direction | 说明 / Description |
|------------|----------------|-------------------|
| 3000 | 入站 / Inbound | 前端 Web UI（HTTPS 建议）|
| 8000 | 入站 / Inbound | 后端 API（HTTPS 建议）|
| 22 | 出站 / Outbound | SSH 扫描 Linux 服务器 |
| 135/445 | 出站 / Outbound | WMI/WinRM 扫描 Windows |
| 443 | 出站 / Outbound | 云平台 API 扫描 |
| 5432 | 内部 / Internal | PostgreSQL |
| 6379 | 内部 / Internal | Redis |

---

## 11. 总结与建议 / Conclusion & Recommendations

### 11.1 核心结论 / Key Conclusions

1. **身份安全是现代安全的核心战场：** 82% 的攻击以凭据为起点，账号安全是安全体系的第一道防线。

2. **传统工具存在结构性缺陷：** 堡垒机聚焦访问控制，IGA 聚焦身份合规，EDR 聚焦终端行为——均无法完整解决账号层面的威胁检测问题。

3. **Telos 填补了 ITDR 领域的技术空白：** 通过五层语义分析（符号层→因果层），Telos 实现了从"发现账号异常"到"理解攻击意图"的跨越。

4. **NHI 管理是当务之急：** 机器账号已超过人员账号 3-5 倍，但现有工具普遍缺乏 NHI 管理能力，Telos 率先填补这一空白。

### 11.2 建议的下一步 / Recommended Next Steps

| 受众 / Audience | 建议行动 / Recommended Action |
|---------------|----------------------------|
| CSO / CISO | 安排产品演示，评估与现有安全体系的协同价值 |
| 安全运营团队 | 申请 POC 环境，验证检测能力 |
| 安全架构师 | 评审 API 集成方案和 SSO 集成可行性 |
| 合规团队 | 评估 SOC2 / ISO27001 / 等保 2.0 自动化检查覆盖度 |
| IT 运维团队 | 评审部署方案和运维要求 |

### 11.3 关于 Telos / About Telos

Telos 成立于 2024 年，专注于身份威胁检测与响应领域。我们的使命是帮助每一个组织洞察全量账号、主动发现威胁、在损失发生前快速响应。

**联系我们 / Contact Us:**
🌐 www.telos.com | 📧 contact@telos.com

---

*Telos v2.0 | © 2026 Telos. All rights reserved.*
*Telos v2.0 | © 2026 Telos 版权所有。*
