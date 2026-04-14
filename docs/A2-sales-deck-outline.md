# Telos 销售演示文稿大纲
# Telos Sales Deck — Slide Outline

> **用途**: 销售演示 / 客户汇报 / 渠道培训
> **版本**: v2.0 | 中英双语

---

## Slide 1 — 封面 / Cover

**标题 / Title:**

> **Telos**
> 身份威胁检测与响应平台
> Identity Threat Detection & Response Platform

**副标题 / Subtitle:**
Know every account. Detect every threat. Respond before damage.
洞察全量账号，主动发现威胁，在损失发生前快速响应。

**联系信息 / Contact:**
🌐 www.telos.com | 📧 contact@telos.com

---

## Slide 2 — 目录 / Table of Contents

1. 市场背景 / Market Context
2. 核心痛点 / Core Pain Points
3. Telos 解决方案 / Telos Solution
4. 核心能力 / Core Capabilities
5. 产品演示 / Product Demo
6. 客户价值 / Customer Value
7. 适用场景 / Use Cases
8. 竞争优势 / Competitive Edge
9. 客户案例 / Customer Stories
10. 部署模式 / Deployment Options
11. 联系我们 / Contact Us

---

## Slide 3 — 市场背景 / Market Context

**标题 / Title:**
身份安全新威胁格局
The New Identity Security Threat Landscape

**内容 / Content:**

| 数据点 / Data Point | 数值 / Value |
|---------------------|-------------|
| 2024 年数据泄露平均成本 / Avg. data breach cost (2024) | **$488 万美元 / USD 4.88M** |
| 涉身份的攻击占比 / Identity-related attacks | **>80%** of breaches involve compromised credentials |
| 企业平均账号数量（10,000+ 服务器）/ Avg. account count | **50,000+ accounts** |
| 影子账号发现率 / Shadow account discovery rate | **平均 15-25%** 未在册 / undiscovered |
| NHI 爆发增速 / NHI growth rate | 机器账号已超过人员账号 **3-5x** |

**引言 / Quote:**
> "身份是新的边界。攻击者不再需要绕过防火墙——他们绕过口令。"
> "Identity is the new perimeter. Attackers no longer bypass firewalls — they bypass credentials."

---

## Slide 4 — 典型损失案例 / Cost of Identity Breaches

**标题 / Title:**
一场账号泄露的代价
The True Cost of a Compromised Account

**案例 / Cases:**

| 事件 / Incident | 损失 / Impact |
|----------------|--------------|
| SolarWinds 供应链攻击 / SolarWinds supply chain | $900M+ 直接损失，数千企业受影响 |
| Capital One 数据泄露 / Capital One breach | $300M 罚款，1亿账号信息曝光 |
| 特权账号滥用导致勒索 / Privileged account ransomware | 平均赎金 $570K+，停机损失 $M 级别 |
| 离职 IT 账号未清理 / Unterminated IT account | 平均驻留时间 180+ 天，横向移动风险极高 |

**核心信息 / Key Message:**
> 80% 的攻击源于有效凭据。发现账号即阻断攻击链第一步。
> 80% of attacks start with valid credentials. Discovering accounts breaks the kill chain at Step 1.

**亮点 / Highlight:**
80% 的攻击源于有效凭据。每发现一个隐藏账号，就是斩断一条攻击链。

---

## Slide 5 — 核心痛点 / Core Pain Points

**标题 / Title:**
您的账号安全面临六大困境
Six Critical Account Security Challenges You Face

| # | 痛点 / Pain Point | 后果 / Consequence |
|---|-------------------|-------------------|
| 1 | 账号资产分散，底数不清 / Account assets scattered, no unified inventory | 影子账号横行，攻击面持续扩大 / Shadow accounts proliferate, expanding attack surface |
| 2 | 离职账号、沉睡特权账号长期存在 / Departed/dormant privileged accounts persist | 攻击者利用"永久凭证"横向移动 / Attackers exploit "permanent credentials" for lateral movement |
| 3 | 凭据泄露、弱密码、特权滥用靠人工巡检 / Credential leaks/weak passwords detected manually | 发现时已造成损失，平均泄露成本逾 $488 万 / Damage already done by time of detection; avg. $4.88M cost |
| 4 | 告警孤立，看不到账号间的关系与攻击路径 / Alerts isolated, no attack path visibility | 无法判断影响范围，响应滞后 / Cannot determine blast radius, response delayed |
| 5 | NHI（非人类身份）爆发式增长 / NHI (Non-Human Identity) explosive growth | 机器账号远超人员账号，最大攻击面无人看管 / Machine accounts outnumber human 3-5x, largest attack surface unguarded |
| 6 | 合规审计靠人工整理，效率低下 / Compliance audits rely on manual work | 等保2.0/SOC2/ISO27001 要求难以满足 / Difficult to meet GB/T 22239-2019, SOC2, ISO27001 requirements |

---

## Slide 6 — Telos 如何解决 / How Telos Addresses This

**标题 / Title:**
Telos：身份威胁检测与响应的完整闭环
Telos: Complete Identity Threat Detection & Response

**闭环四步 / Four-Phase Loop:**

```
[发现 / Discover]     →  [分析 / Analyze]   →  [告警 / Alert]    →  [响应 / Respond]
 全面扫描所有账号        五层AI威胁分析          实时多渠道告警         自动化处置剧本
 Scan all accounts      5-Layer AI analysis     Real-time alerting    Automated playbooks
```

**一句话价值主张 / One-Liner:**
> Telos Know every account. Detect every threat. Respond before damage.
> Telos 洞察全量账号，主动发现威胁，在损失发生前快速响应。

---

## Slide 7 — 核心能力 1：全面账号资产发现
## Core Capability 1: Comprehensive Account Discovery

**标题 / Title:**
自动发现全量账号，构建完整资产清单
Automatically Discover All Accounts — Build a Complete Asset Inventory

**支持扫描源 / Supported Scan Sources:**

| 平台 / Platform | 账号类型 / Account Types |
|----------------|------------------------|
| 🐧 Linux / Unix (SSH) | 系统账号、普通账号、服务账号 |
| 🪟 Windows (WMI/WinRM) | 本地账号、AD 域账号 |
| ☁️ 云平台 (AWS IAM / 阿里云 / 腾讯云) | IAM 用户/角色/组、Access Key |
| 🗄️ 特权访问管理 (PAM) | 堡垒机账号、特权审批记录 |
| 🗃️ 数据库 (MySQL / PostgreSQL / Redis) | 应用账号、数据库管理员 |
| 📁 LDAP / Active Directory | 企业目录账号、联合身份 |

**核心优势 / Key Advantage:**
- ✅ 自动发现，无需手动录入 / Auto-discovery, no manual entry
- ✅ 增量扫描，仅检测变更 / Incremental scan detects only changes
- ✅ 统一清单，告别 Excel / Unified inventory, no more spreadsheets

**亮点 / Highlight:**
单一平台覆盖 Linux、Windows、云平台、数据库、PAM 等所有账号来源，告别多套工具分散管理的混乱。

---

## Slide 8 — 核心能力 2：MITRE ATT&CK 威胁映射
## Core Capability 2: MITRE ATT&CK Threat Mapping

**标题 / Title:**
所有账号异常，自动映射 ATT&CK 框架
Every Account Anomaly → ATT&CK Framework Mapping

**覆盖范围 / Coverage:**

| ATT&CK 战术 / ATT&CK Tactic | 说明 / Description | Telos 支持 |
|----------------------------|-------------------|-----------|
| TA0001 初始访问 / Initial Access | 凭据盗取、钓鱼 / Credential theft, phishing | ✅ |
| TA0004 权限提升 / Privilege Escalation | sudo 滥用、UID 变更 / sudo abuse, UID changes | ✅ |
| TA0006 凭据访问 / Credential Access | 密码窃取、SSH 密钥复用 / Password theft, key reuse | ✅ |
| TA0008 横向移动 / Lateral Movement | SSH 密钥复用传播 / SSH key reuse propagation | ✅ |
| TA0003 持久化 / Persistence | 后门账号、特权账号新增 / Backdoor accounts, new privileged | ✅ |
| TA0005 防御规避 / Defense Evasion | 账号隐藏、权限降级掩盖 / Account hiding, de-escalation masking | ✅ |

**导出能力 / Export:**
📤 支持导出 ATT&CK Navigator Layer JSON 文件，可直接导入 Red Canary Atomic Threat Coverage 等工具
📤 Export ATT&CK Navigator Layer JSON — importable to Red Canary and other tools

**亮点 / Highlight:**
所有账号异常自动关联 ATT&CK 战术 → 可直接输出 Red Team 可用的攻击路径图。

---

## Slide 9 — 核心能力 3：五层 AI 威胁分析引擎
## Core Capability 3: Five-Layer AI Threat Analysis Engine

**标题 / Title:**
业界领先的语义级威胁分析
Industry-First Semantic-Level Threat Analysis

**五层模型 / Five-Layer Model:**

| 层级 / Layer | 名称 / Name | 检测能力 / Detection |
|-------------|------------|---------------------|
| 🔤 Layer 1 | 符号层 Semiotics | 字符伪装（l→1, o→0）、匿名命名（_admin）、符号模仿 |
| 🎭 Layer 2 | 本体层 Ontology | 影子账号、角色混淆、孤立孤儿账号 |
| 🧠 Layer 3 | 认知层 Cognitive | 确认偏差、光环效应、正常化偏差 |
| 👥 Layer 4 | 人类学层 Anthropology | 高风险信任链、权限簇人机混用、身份隔离 |
| 🔗 Layer 5 | 因果层 Causal | 权限提升路径、沉睡特权链、因果中枢 |

**分析引擎 / Analysis Engine:**
- 🐍 Python FastAPI（默认）— 快速原型化，灵活配置
- ⚡ Go 分析引擎（可选）— 高性能，10,000+ 账号并发分析

**亮点 / Highlight:**
业界首个语义级账号威胁分析引擎，五层分析覆盖从字符伪装到因果攻击路径的完整链路。

---

## Slide 10 — 核心能力 4：NHI 非人类身份管理
## Core Capability 4: Non-Human Identity (NHI) Management

**标题 / Title:**
机器账号——最大却最无人看管的攻击面
Machine Accounts — The Largest Yet Most Unguarded Attack Surface

**NHI 类型 / NHI Types:**

| 类型 / Type | 风险 / Risk | 示例 / Example |
|-----------|-----------|---------------|
| Service Account | 权限过度配置 / Over-privileged | 运行服务的 root 账号 |
| CI/CD Credential | 永久 Token / Permanent tokens | GitHub Actions secrets |
| API Key | 无轮换机制 / No rotation | 云平台 Access Key |
| Cloud IAM | 最小权限原则违反 / Principle of least privilege violated | 过度授权的 IAM 角色 |
| AI Agent Credential | 新兴风险 / Emerging risk | Agent 使用的 LLM API Key |

**核心功能 / Key Features:**
- 📊 NHI 风险仪表板（Top 10 高风险 NHI）
- 🔄 轮换提醒与生命周期管理
- 🔗 归属人关联（自动关联到人员身份）
- 📤 合规报告导出（满足审计要求）

**亮点 / Highlight:**
机器账号是最大却最无人看管的攻击面，Telos 是业界首个将 NHI 纳入统一安全管控的产品。

---

## Slide 11 — 核心能力 5：账号生命周期自动化
## Core Capability 5: Account Lifecycle Automation

**标题 / Title:**
消灭僵尸账号，让每个账号都有主
Eliminate Zombie Accounts — Every Account Has an Owner

**账号状态机 / Account State Machine:**

```
[活跃 / Active]  ── 90天无登录 ──→  [沉睡 / Dormant]
     ↑                                     │
     └─── 有登录行为 ─────────────────────────┘
                                          ↓
                              180天无登录 → [离职 / Departed]
```

**自动化能力 / Automation:**
- ⏰ 基于登录行为自动判断账号状态
- 🔔 状态变更自动触发告警（沉睡→离职时通知）
- 🤖 支持触发自动化处置剧本（禁用/归档）
- 📊 生命周期报告定期生成（支持 SOC2/ISO27001）

**亮点 / Highlight:**
账号生命周期全自动化，活跃→沉睡→离机状态自动流转，消灭僵尸账号，从源头压缩攻击面。

---

## Slide 12 — 核心能力 6：实时告警与联动响应
## Core Capability 6: Real-Time Alerting & Orchestrated Response

**标题 / Title:**
发现即告警，告警即响应
Detect → Alert → Respond in Seconds

**告警类型 / Alert Types:**

| 告警类型 / Alert Type | 严重性 / Severity | 说明 / Description |
|----------------------|-----------------|-------------------|
| 🔴 新增管理权限 / New Admin Privilege | 严重 / Critical | 普通账号突获管理员权限 |
| 🔴 NOPASSWD Sudo 新增 / NOPASSWD Sudo Added | 严重 / Critical | 无密码 sudo 配置引入 |
| 🔴 敏感凭据泄露 / Credential Leak Detected | 严重 / Critical | 发现 shadow/known_hosts 等危险文件 |
| 🟠 孤儿特权账号 / Orphan Privileged Account | 高危 / High | 无关联人员身份的特权账号 |
| 🟡 休眠账号重新激活 / Dormant Account Reactivated | 中危 / Medium | 沉寂账号再次活跃 |

**通知渠道 / Notification Channels:**
📧 邮件 / Email | 🔔 Slack | 💬 飞书 / Feishu | 💼 企业微信 / WeCom | 🌐 Webhook（SIEM/SOAR）

**亮点 / Highlight:**
新增特权账号、权限爬升等高危事件秒级触发告警，支持多渠道实时推送，平均 MTTR 从 69 天降至 2 小时。

---

## Slide 13 — 解决方案架构图
## Solution Architecture

**标题 / Title:**
Telos 系统架构
Telos System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     前端 UI (React + Ant Design)        │
│               仪表盘 / 威胁分析 / 告警 / NHI              │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS (REST API)
┌──────────────────────▼──────────────────────────────────┐
│              Python FastAPI 后端 (端口 8000)               │
│  扫描调度 / 威胁分析 / 告警引擎 / 策略评估 / 用户管理 / RBAC  │
└──────┬────────────────┬───────────────────┬──────────────┘
       │                │                   │
┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────────┐
│ PostgreSQL  │  │    Redis    │  │ Go 分析引擎     │
│  (账号数据)  │  │  (缓存/队列) │  │  (高性能分析引擎) │
└─────────────┘  └─────────────┘  └─────────────────┘
       │
┌──────▼──────────────────────────────────────────────────┐
│              扫描代理 / Scanner Plugins                  │
│  SSH / WMI / WinRM / 云 API / PAM API / 数据库连接       │
└─────────────────────────────────────────────────────────┘
```

**部署模式 / Deployment Modes:**
🏠 本地部署 On-Prem | ☁️ 私有云 Private Cloud | 🔀 混合云 Hybrid | 📡 SaaS

---

## Slide 14 — 产品界面：仪表盘
## Product UI: Dashboard

**标题 / Title:**
一目了然的全局风险态势
At-a-Glance Global Risk Posture

<!-- screenshot: 仪表盘界面 / Dashboard UI -->

**界面要素 / UI Components:**

| 组件 / Component | 说明 / Description |
|-----------------|-------------------|
| 风险评分 / Risk Score | 全局 0-100，颜色标识（绿→黄→橙→红） |
| 账号统计 / Account Stats | 总账号数、特权账号数、沉睡账号数 |
| 风险趋势 / Risk Trend | 近 7/30 天告警趋势图 |
| 横向移动热点 / Lateral Movement Hotspots | 风险最高的资产 TOP 5 |
| ATT&CK 战术覆盖 / ATT&CK Tactic Coverage | 各战术阶段信号数量柱状图 |
| AI 安全摘要 / AI Security Summary | LLM 自动生成的威胁态势报告 |

**视图切换 / View Toggle:**
运营视图（Operator View）↔ 管理视图（Admin View）

**亮点 / Highlight:**
全局风险评分 + ATT&CK 战术覆盖 + AI 摘要三图合一，让管理层 5 秒读懂安全态势。

---

## Slide 15 — 产品界面：ATT&CK 覆盖率
## Product UI: ATT&CK Coverage

**标题 / Title:**
账号威胁的 ATT&CK 战术全景
ATT&CK Tactic Panorama for Identity Threats

<!-- screenshot: ATT&CK覆盖率界面 / ATT&CK Coverage UI -->

**两大视图 / Two Views:**

**视图 1：风险摘要 / Risk Summary**
- 按严重性分组展示所有信号
- 每条信号显示：信号类型 / 影响账号 / ATT&CK ID / 处置建议
- 适合快速了解最高风险项

**视图 2：技术详情 / Technique Details**
- 按 ATT&CK 技术分组
- 显示置信度 / 信号数量 / 证据摘要
- 适合深度分析和报告

**导出功能 / Export:**
📤 ATT&CK Navigator Layer JSON → 导入 mitre-attack.github.io/attack-navigator/

**亮点 / Highlight:**
一键导出 Navigator Layer JSON，Red Team 与 Blue Team 使用同一套威胁语言协同作战。

---

## Slide 16 — 产品界面：告警中心
## Product UI: Alert Center

**标题 / Title:**
实时告警，秒级响应
Real-Time Alerts — Respond in Seconds

<!-- screenshot: 告警中心界面 / Alert Center UI -->

**告警工作流 / Alert Workflow:**

```
新告警 (New)
  ↓
[确认 / Acknowledge]  →  [响应 / Respond]  ✓ 处理完毕
  ↓ 驳回
[驳回 / Dismiss]      →  ✗ 误报标记
```

**实时能力 / Real-Time Capabilities:**
- 🔄 SSE 实时推送，新告警秒达
- 🔕 告警去重（同类告警 30 分钟内去重）
- 📊 告警趋势分析（按日/周/月维度）
- 📤 支持导出告警记录供审计

**亮点 / Highlight:**
告警噪声从每天 1000+ 降至 <50 条，运营团队不再被淹没，聚焦真正威胁。

---

## Slide 17 — 客户价值量化 / Customer Value Metrics

**标题 / Title:**
投资回报可量化，效果可衡量
Quantifiable ROI — Measurable Results

**核心指标 / Key Metrics:**

| 指标 / Metric | 行业平均 / Industry Avg | Telos 客户 / With Telos | 提升幅度 / Improvement |
|--------------|----------------------|----------------------|---------------------|
| MTTD（平均发现时间）/ Mean Time to Detect | 207 天 / days | **< 24 小时 / hours** | **↓ 98%** |
| MTTR（平均响应时间）/ Mean Time to Respond | 69 天 / days | **< 2 小时 / hours** | **↓ 97%** |
| 攻击面缩减 / Attack Surface Reduction | — | **平均 62%** | 清理僵尸账号后 |
| 特权账号发现率 / Privileged Account Discovery | 65% 已知 / known | **100%** 全发现 | **+35%** |
| 合规审计效率 / Compliance Audit Efficiency | 人工 2-4 周 / manual weeks | **< 1 小时 / hours** | **↓ 95%** |
| 告警疲劳 / Alert Fatigue | 每天 1000+ 噪声 / noise | **< 50 条/天** | **↓ 95%** |

**亮点 / Highlight:**
平均投资回报周期 < 6 个月；MTTD 从 207 天降至 <24 小时，98% 的威胁在造成损失前被发现。

---

## Slide 18 — 适用行业与场景
## Applicable Industries & Use Cases

**标题 / Title:**
Telos 适用场景
Telos Use Cases

| 场景 / Scenario | 说明 / Description |
|----------------|-------------------|
| 🏦 金融机构 / Financial | 特权账号审计、横向移动检测、等保合规 |
| 🏛️ 政府部门 / Government | 政务云资产梳理、等保 2.0 合规审计 |
| 🏢 大型企业 / Large Enterprise | 多地域资产统一管控、身份融合 |
| ☁️ 云原生 / Cloud-Native | 云 IAM 安全、CI/CD 凭证管理 |
| 🔒 攻防演练 / Red Team / Pen Testing | 攻击前资产梳理、攻击路径识别 |
| 🛡️ 攻防演练防御 / Blue Team | 横向移动检测、攻击路径阻断 |

**切入场景 / Best Entry Points:**
1. **攻防演练前** → 快速摸清所有账号资产
2. **特权账号审计** → 发现 NOPASSWD/UID=0 等高危配置
3. **离职账号清理** → 自动识别待清理账号

---

## Slide 19 — 竞争优势对比
## Competitive Comparison

**标题 / Title:**
为什么选择 Telos？
Why Telos Over Alternatives?

| 对比维度 / Dimension | Telos | 传统堡垒机 / Traditional Bastion | 身份治理 IGA | EDR |
|---------------------|-------|-------------------------------|------------|-----|
| 账号发现方式 / Account Discovery | ✅ 自动扫描 | ❌ 手动录入 | ⚠️ 半自动同步 | ❌ 不支持 |
| ATT&CK 映射 / ATT&CK Mapping | ✅ 原生支持 | ❌ 不支持 | ⚠️ 部分支持 | ⚠️ 部分支持 |
| 五层 AI 威胁分析 / 5-Layer AI Analysis | ✅ 自主研发 | ❌ 不支持 | ⚠️ 规则引擎 | ⚠️ 规则引擎 |
| NHI 管理 / NHI Management | ✅ 原生支持 | ❌ 不支持 | ⚠️ 弱支持 | ❌ 不支持 |
| 横向移动检测 / Lateral Movement Detection | ✅ 支持 | ❌ 不支持 | ⚠️ 部分支持 | ⚠️ 部分支持 |
| 部署复杂度 / Deployment Complexity | ✅ 低 | ✅ 低 | ❌ 高 | ⚠️ 中 |
| 响应时间 / Time to Value | ✅ 小时级 | ✅ 小时级 | ❌ 天级 | ⚠️ 天级 |

---

## Slide 20 — 竞争优势（续）：独特卖点
## Competitive Edge: Unique Selling Points

**标题 / Title:**
Telos 独特价值主张
Telos Unique Value Proposition

**差异化亮点 / Differentiation Highlights:**

🧠 **五层 AI 威胁分析（业界首创）**
业界首个语义级账号威胁分析引擎，覆盖符号层→因果层的完整攻击链路。

🔗 **ATT&CK 原生集成**
所有账号异常自动映射到 ATT&CK 框架，支持 Navigator Layer 导出，赋能 Red Team 协同防御。

🤖 **NHI 全生命周期管理**
首个将机器账号、服务账号、CI/CD 凭证、AI Agent 凭据纳入统一安全管控的产品。

⚡ **分钟级部署，小时级见效**
All-in-One 部署，开箱即用，扫描→分析→告警全流程 < 1 小时完成。

📊 **攻击面量化可见**
全局风险评分（0-100）+ ATT&CK 战术覆盖可视化，让安全态势一目了然。

---

## Slide 21 — 客户案例 1：某省级政务云
## Customer Story 1: Provincial Government Cloud

**标题 / Title:**
某省级政务云：攻击面缩减 62%
Provincial Government Cloud: 62% Attack Surface Reduction

**客户背景 / Customer Profile:**
- 🏛️ 省级政务云，200+ 台服务器
- 面临问题：账号资产底数不清，攻防演练前急需摸排

**Telos 解决方案 / Solution:**
1. 全量账号扫描（200+ 服务器，48 小时内完成）
2. 五层 AI 威胁分析
3. 僵尸账号自动化清理

**成果 / Results:**

| 指标 / Metric | 数值 / Value |
|--------------|-------------|
| 🆕 新发现隐藏服务账号 / Hidden service accounts discovered | **847 个** |
| 📉 攻击面缩减 / Attack surface reduction | **62%** |
| ⚠️ 高危配置项检出 / High-risk configurations detected | **234 项** |
| ⏱️ 部署到首份报告 / Time to first report | **< 4 小时 / hours** |

> "Telos 让我们在攻防演练前真正掌握了账号资产的家底。"
> "Telos gave us true visibility into our account assets before the red team exercise."

**亮点 / Highlight:**
从"底数不清"到"全面可视化"，仅用 4 小时就输出了第一份攻击面报告。

---

## Slide 22 — 客户案例 2：某金融机构
## Customer Story 2: Financial Institution

**标题 / Title:**
某金融机构：安全评分从 45 提升至 92
Financial Institution: Security Score Jumps from 45 to 92

**客户背景 / Customer Profile:**
- 🏦 大型金融机构，3000+ 终端，500+ 服务器
- 面临问题：横向移动风险高，合规审计压力大

**Telos 解决方案 / Solution:**
1. ATT&CK 覆盖率全面分析
2. 特权账号专项审计
3. 自动化合规报告（SOC2 / ISO27001）

**成果 / Results:**

| 指标 / Metric | 数值 / Value |
|--------------|-------------|
| 🛡️ 发现高危权限提升路径 / High-risk privilege escalation paths found | **4 条** |
| 📈 安全评分提升 / Security score improvement | **45 → 92** |
| ✅ 合规检查项通过率 / Compliance pass rate | **100%** |
| ⏱️ 审计周期缩短 / Audit cycle reduction | **从 4 周 → 1 小时** |

> "Telos 的 ATT&CK 映射让我们第一次看清了横向移动路径。"
> "Telos's ATT&CK mapping gave us visibility into lateral movement paths for the first time."

**亮点 / Highlight:**
合规审计从 4 周缩短至 1 小时，100% 合规通过率，SOC2/ISO27001 自动化验证。

---

## Slide 23 — 部署模式
## Deployment Options

**标题 / Title:**
灵活部署，适应各类环境
Flexible Deployment for Any Environment

| 部署模式 / Mode | 适用场景 / Use Case | 优势 / Advantage |
|-------------|-------------------|----------------|
| 🏠 **本地部署 / On-Prem** | 金融、政务等高合规要求 | 数据不出网，完全自主可控 |
| ☁️ **私有云 / Private Cloud** | 企业私有云环境 | 复用云基础设施，弹性扩展 |
| 🔀 **混合云 / Hybrid** | 多云 + 本地混合 | 统一管控跨环境账号 |
| 📡 **SaaS** | 快速上线、无运维能力 | 零运维，订阅即用 |

**系统要求 / System Requirements:**

| 资源 / Resource | 最低 / Minimum | 推荐 / Recommended |
|---------------|--------------|-------------------|
| CPU | 4 核 / cores | 8 核+ / cores |
| 内存 / Memory | 8 GB | 16 GB+ |
| 磁盘 / Disk | 50 GB | 100 GB+ |
| 账号规模 / Account Scale | — | 单引擎 10,000+ |

---

## Slide 24 — 合作伙伴与生态
## Partner Ecosystem

**标题 / Title:**
与现有安全生态无缝集成
Seamless Integration with Your Security Stack

**集成生态 / Integration Ecosystem:**

| 类别 / Category | 集成产品 / Products |
|---------------|-------------------|
| 🔍 SIEM | Splunk, Elastic, IBM QRadar, 奇安信, 阿里云 SLS |
| 🤖 SOAR | 阿里云 SOAR, 腾讯云 SOAR, Palo Alto XSOAR |
| 🔑 身份 IdM | Azure AD, Okta, Keycloak, LDAP/AD |
| 🛡️ PAM 特权访问 | 腾讯云 PAM, 阿里云 PAM, CyberArk |
| 💬 协同办公 | Slack, 飞书, 企业微信, 钉钉 |
| 📊 可视化 | Grafana, Kibana, 自定义 Dashboard |

**开放 API / Open API:**
📤 RESTful API + Webhook，支持二次开发和自动化编排

---

## Slide 25 — 联系我们 / Contact Us

**标题 / Title:**
立即开启身份安全新篇章
Start Your Identity Security Journey Today

**联系信息 / Contact:**

🌐 **www.telos.com**
📧 **contact@telos.com**
📞 **400-XXX-XXXX**

**下一步 / Next Steps:**

1. 📋 产品演示预约 / Schedule a Demo
2. 🔍 POC 环境申请 / Request a POC
3. 📊 风险评估咨询 / Risk Assessment Consultation

**合作方式 / Partnership:**

- 🤝 渠道合作 / Channel Partnership
- 🔧 技术集成 / Technical Integration
- 🏢 企业采购 / Enterprise Procurement

---

**附录 / Appendix:**

- 📄 完整技术规格 / Full Technical Specifications
- 📋 功能对比表（详细版）/ Detailed Feature Comparison
- 📊 ROI 计算器 / ROI Calculator
- 📑 客户案例集 / Customer Case Study Collection

---

*Telos v2.0 | © 2026 Telos. All rights reserved.*
*Telos v2.0 | © 2026 Telos 版权所有。*
