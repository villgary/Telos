# Telos
## Identity Threat Detection & Response Platform
## 身份威胁检测与响应平台

---

## 一句话价值主张 / One-Liner Value Proposition

> **Know every account. Detect every threat. Respond before damage.**
> **洞察全量账号，主动发现威胁，在损失发生前快速响应。**

---

## 解决的问题 / The Problem We Solve

| # | 痛点 / Pain Point | 后果 / Consequence |
|---|-------------------|-------------------|
| 1 | 账号资产分散，运维、安全、审计各有一套账本，底数不清 | 影子账号横行，攻击面持续扩大 |
| 2 | 离职账号、沉睡特权账号长期存在，无人清理 | 攻击者利用"永久凭证"横向移动 |
| 3 | 凭据泄露、弱密码、特权滥用靠人工巡检，发现时已造成损失 | 平均数据泄露成本逾 400 万美元 |
| 4 | 告警孤立，看不到账号间的关系与攻击路径 | 无法判断攻击影响范围，响应滞后 |
| 5 | NHI（非人类身份）爆发式增长，机器账号远超人员账号 | 最大攻击面无人看管 |

---

## 核心能力 / Core Capabilities

### 1. 全面账号资产发现 / Comprehensive Account Discovery
自动发现并统一管理 SSH、Local System、PAM、云平台、AD/LDAP 等所有账号来源，构建完整账号资产清单。

**支持扫描源：**
- Linux/Unix SSH 账号
- Windows 本地账号与 AD 域账号
- 特权访问管理（PAM）系统
- 云平台身份（IAM）

### 2. MITRE ATT&CK 威胁映射 / MITRE ATT&CK Mapping
所有账号异常行为自动映射到 MITRE ATT&CK 框架，覆盖 TA0001–TA0011 等 14 个战术阶段，可导出 ATT&CK Navigator Layer 文件直接导入 Red Canary Atomic Threat Coverage 等工具。

### 3. 五层 AI 威胁分析引擎 / Five-Layer AI Threat Analysis Engine
自主研发的多层语义分析引擎，对账号进行全方位威胁研判：

| 层级 | 名称 | 能力 |
|------|------|------|
| Layer 1 | 符号层 Semiotics | 检测字符伪装、匿名命名、符号模仿等符号层攻击 |
| Layer 2 | 本体层 Ontology | 识别影子账号、角色混淆、孤立孤儿账号 |
| Layer 3 | 认知层 Cognitive | 发现确认偏差、光环效应、正常化偏差等认知盲点 |
| Layer 4 | 人类学层 Anthropology | 分析信任链、权限簇、身份隔离等组织层威胁 |
| Layer 5 | 因果层 Causal | 推理权限提升路径、因果中枢、沉睡特权链等深度威胁 |

### 4. NHI 非人类身份管理 / Non-Human Identity Management
对机器账号、服务账号、API Key、CI/CD 凭证等 NHI 进行全生命周期管理，跟踪凭证泄露风险和轮换周期。

### 5. 账号生命周期自动化 / Account Lifecycle Automation
基于登录行为自动判断账号状态（活跃/沉睡/离职），触发自动化处置流程，消灭僵尸账号。

### 6. 实时告警与联动响应 / Real-Time Alerting & Orchestrated Response
基于规则 + AI 的双重告警引擎，支持邮件、Webhook、Slack 等多渠道通知，自动生成处置工单。

---

## 适用场景 / Use Cases

| 场景 / Scenario | 解决的问题 / Problem Solved |
|-----------------|---------------------------|
| 攻防演练前资产梳理 | 快速摸清所有账号资产，不遗漏任何攻击入口 |
| 特权账号审计 | 发现 NOPASSWD sudo、UID=0 非 root 等高危配置 |
| 离职账号清理 | 自动识别离职后仍有活跃会话的服务账号 |
| 横向移动检测 | 基于 ATT&CK 框架检测 SSH 密钥复用、权限链传播 |
| 合规审计（等保 2.0） | 满足身份标识、访问控制、安全审计等控制要求 |
| 云环境 NHI 安全 | 发现云 IAM 过度授权和服务账号凭证泄露 |

---

## 技术规格 / Technical Specifications

| 项目 | 规格 / Spec |
|------|------------|
| 部署模式 | 本地部署 / 私有云 / 混合云 / SaaS |
| 扫描协议 | SSH（Key/Password/GSSAPI）、WMI、API |
| 数据库 | PostgreSQL 14+ |
| 分析引擎 | Python FastAPI + Go 分析引擎（可选）|
| 前端 | React + Ant Design |
| ATT&CK 版本 | ATT&CK v14+ |
| 账号规模 | 单引擎支持 10,000+ 账号并发分析 |
| 高可用 | 支持主备部署 |
| 安全合规 | TLS 传输加密、AES-256 数据加密、细粒度 RBAC |

---

## 客户案例 / Customer Stories

> **案例 1：某省级政务云**
> 在 200+ 台服务器环境中发现隐藏服务账号 847 个，清理休眠特权账号后攻击面缩减 62%。
>
> **案例 2：某金融机构**
> 通过 ATT&CK 覆盖率分析发现 4 个高危权限提升路径，在渗透测试前完成修复，安全评分从 45 提升至 92。

---

## 竞争优势 / Competitive Differentiation

| 对比维度 | Telos | 传统堡垒机 | 身份治理（IGA） |
|---------|------------|-----------|----------------|
| 账号发现 | 自动发现 | 手动录入 | 半自动同步 |
| ATT&CK 映射 | 原生支持 | 不支持 | 部分支持 |
| 五层威胁分析 | 自主研发 AI 引擎 | 不支持 | 规则引擎 |
| NHI 管理 | 原生支持 | 不支持 | 弱支持 |
| 横向移动检测 | 支持 | 不支持 | 部分支持 |
| 部署复杂度 | 低 | 低 | 高 |

---

## 联系我们 / Contact Us

🌐 **www.telos.com** | 📧 **contact@telos.com**

*Version 2.0 | © 2026 Telos. All rights reserved.*
