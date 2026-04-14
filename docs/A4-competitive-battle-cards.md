# Telos 竞争差异化文档
# Telos Competitive Battle Cards

> **文件用途 / Purpose**: 销售对抗竞品 / 市场定位 / 内部培训
> **版本 / Version**: v2.0 | 中英双语

---

## 目录 / Table of Contents

1. [使用说明 / How to Use These Cards](#1-使用说明)
2. [竞品 1：阿里云堡垒机 / Aliyun Jump Server](#2-竞品-1阿里云堡垒机-aliyun-jump-server)
3. [竞品 2：传统 IGA 产品 / Traditional IGA Products](#3-竞品-2传统-iga-产品-traditional-iga-products)
4. [竞品 3：EDR 产品 / EDR Products](#4-竞品-3edr-产品-edr-products)
5. [竞品 4：云身份安全 CSPM/CIEM / Cloud Identity Security](#5-竞品-4云身份安全-cspmciem)
6. [竞品 5：其他 ITDR 厂商 / Other ITDR Vendors](#6-竞品-5其他-itdr-厂商)
7. [综合对比总表 / Competitive Comparison Matrix](#7-综合对比总表)

---

## 1. 使用说明 / How to Use These Cards

### 1.1 每张卡片结构 / Card Structure

每张竞品卡片包含以下内容：

| 章节 / Section | 内容 / Content |
|--------------|--------------|
| **竞品定位 / Positioning** | 竞品的市场定位和核心价值主张 |
| **竞品弱点 / Weaknesses** | 3-5 个核心弱点（可用话术切入点）|
| **Telos 对比优势 / Telos Advantages** | Telos 的对应优势（用数据说话）|
| **常用反驳话术 / Objection Handlers** | 3-5 个常见异议的标准回应 |
| **适合切入的客户画像 / ICP** | 最容易被 Telos 切入的客户特征 |

### 1.2 核心竞争信息 / Key Competitive Messages

**Telos 三大差异化支柱：**

1. **从"记录"到"检测"：** 传统堡垒机/IGA 解决的是合规和审计问题；Telos 解决的是威胁检测和响应问题
2. **五层 AI 语义分析：** 业界唯一覆盖符号层→因果层的账号威胁分析产品
3. **账号资产主动发现：** 自动扫描，不需要手动录入或半自动同步

### 1.3 竞品分类框架 / Competitor Taxonomy

```
身份安全市场 / Identity Security Market
├── 访问控制 / Access Control
│   └── 堡垒机 / Jump Server ← Telos 互补，不是替代
├── 身份治理 / Identity Governance
│   └── IGA (SailPoint/Saviynt) ← Telos 互补+竞争
├── 端点安全 / Endpoint Security
│   └── EDR (CrowdStrike/SentinelOne) ← Telos 互补
└── 身份威胁检测 / Identity Threat Detection
    └── ITDR (Telos) ← 新兴赛道，Telos 领先
```

---

## 2. 竞品 1：阿里云堡垒机 / Aliyun Jump Server

**竞品定位 / Positioning:**
阿里云堡垒机定位为企业级运维安全管控平台，提供运维审计、访问控制、账号管理等功能，主要面向阿里云用户。

### 2.1 竞品弱点 / Weaknesses

| # | 弱点 / Weakness | 严重程度 / Severity | 切入点说明 / Leverage Point |
|---|----------------|-------------------|--------------------------|
| 1 | **无法主动发现账号** — 堡垒机是被动管控工具，依赖手动录入或 AD 同步，影子账号无法发现 | 高 / High | 这是最核心的差异点，也是客户最痛的痛点 |
| 2 | **无威胁检测能力** — 阿里云堡垒机是事后审计工具，无 ATT&CK 映射、无五层分析，检测能力为零 | 高 / High | 攻击发生时客户不知道，只有事后审计 |
| 3 | **仅覆盖阿里云资产** — 多云/混合云环境下，其他平台账号完全无感知 | 中 / Medium | 政企客户通常有混合云需求 |
| 4 | **无 NHI 管理** — 机器账号、服务账号、API Key 完全不在管理范围内 | 高 / High | NHI 爆发时代，最大攻击面无人看管 |
| 5 | **横向移动检测缺失** — 看不到账号之间的信任关系和传播路径 | 高 / High | SSH 密钥复用等攻击路径完全不可见 |

### 2.2 Telos 对比优势 / Telos Advantages

| 对比维度 / Dimension | 阿里云堡垒机 / Aliyun | Telos | 优势幅度 / Advantage |
|--------------------|---------------------|-------|-------------------|
| 账号发现方式 / Account Discovery | 手动录入 | ✅ 自动扫描 | 从天→分钟 |
| 威胁检测 / Threat Detection | ❌ 无 | ✅ 五层 AI | 质的飞跃 |
| ATT&CK 映射 / ATT&CK Mapping | ❌ 无 | ✅ 原生支持 | 从无到有 |
| 横向移动检测 / Lateral Movement | ❌ 无 | ✅ 支持 | 从无到有 |
| NHI 管理 / NHI Management | ❌ 无 | ✅ 完整方案 | 填补空白 |
| 账号覆盖范围 / Account Coverage | 仅阿里云 | ✅ 全平台覆盖 | 多云友好 |
| 部署复杂度 / Deployment | 中 | ✅ 低 | 小时 vs 天 |

### 2.3 常用反驳话术 / Objection Handlers

**Q: "我们已经用了堡垒机，为什么还需要 Telos？"**

> A: "这是个好问题。堡垒机和 Telos 解决的是不同问题：堡垒机解决的是**谁可以访问什么**（访问控制），Telos 解决的是**账号本身是否已经被攻陷**（威胁检测）。
> 举个例子：攻击者通过钓鱼拿到了运维人员的 SSH 密钥，登录到服务器并创建了一个后门账号。这个过程堡垒机完全不会报警——因为所有操作都是'授权账号'在执行。但 Telos 会立即检测到新增特权账号、ATT&CK 信号触发、横向移动路径生成。
> 堡垒机和 Telos 是互补关系，不是替代关系。建议您保留堡垒机，在它之上叠加 Telos 来解决威胁检测的问题。"

**Q: "Telos 和堡垒机功能重复吗？"**

> A: "功能完全不重复。堡垒机的核心是**控制访问权限**（禁止 root 登录、记录操作审计）；Telos 的核心是**检测账号威胁**（发现被攻陷的账号）。一个管授权，一个管威胁。"

**Q: "阿里云堡垒机是云原生的，Telos 支持阿里云吗？"**

> A: "Telos 支持阿里云 RAM 账号的自动扫描，包括 RAM User、RAM Role、Access Key 等。同时 Telos 也支持 AWS IAM、腾讯云 CAM、其他云平台，以及本地服务器和数据库——多云环境下 Telos 能提供统一的账号安全视图。"

### 2.4 适合切入的客户画像 / ICP

| 维度 / Dimension | 特征 / Characteristics |
|----------------|---------------------|
| **使用堡垒机但发生过安全事件** | 已经被攻击过或审计发现问题 |
| **多云/混合云环境** | 同时使用阿里云+本地+其他云 |
| **攻防演练参与方** | 即将或已经参与攻防演练 |
| **合规审计压力** | SOC2、等保、金融监管 |
| **IT 团队规模中等** | 没有专门的账号安全团队 |

---

## 3. 竞品 2：传统 IGA 产品 / Traditional IGA Products

**竞品定位 / Positioning:**
SailPoint、Okta Identity Governance、Saviynt 等 IGA 产品定位于企业身份治理，通过身份生命周期管理、访问评审、合规策略自动化来满足合规要求。

### 3.1 竞品弱点 / Weaknesses

| # | 弱点 / Weakness | 严重程度 / Severity | 切入点说明 / Leverage Point |
|---|----------------|-------------------|--------------------------|
| 1 | **部署周期过长** — IGA 项目通常需要 6-18 个月实施，企业投入巨大 | 高 / High | Telos 小时级部署，快速见效 |
| 2 | **无威胁检测视角** — IGA 聚焦身份合规（谁应该有什么权限），没有威胁检测引擎 | 高 / High | 合规做好了但依然被攻陷 |
| 3 | **账号发现依赖同步** — 半自动同步，影子账号无法发现 | 中 / Medium | 同步延迟期间的攻击窗口 |
| 4 | **NHI 管理能力弱** — IGA 设计以人员身份为中心，机器账号管理能力极弱 | 高 / High | NHI 已超过人员账号 3-5 倍 |
| 5 | **五层 AI 分析缺失** — IGA 使用规则引擎，无法理解账号语义层面的威胁 | 中 / Medium | 检测深度不够 |
| 6 | **横向移动不可见** — 只看单点账号权限，无法分析跨主机攻击路径 | 中 / Medium | 横向移动是主要攻击手法 |

### 3.2 Telos 对比优势 / Telos Advantages

| 对比维度 / Dimension | IGA | Telos | 差异 / Difference |
|--------------------|-----|-------|-----------------|
| 部署周期 / Time to Value | 6-18 个月 | ✅ 小时级 | **98%+** 缩短 |
| 账号发现 / Account Discovery | 半自动同步 | ✅ 主动扫描 | 从天→分钟 |
| 威胁检测 / Threat Detection | ⚠️ 规则引擎 | ✅ 五层 AI | 深度优势 |
| ATT&CK 映射 / ATT&CK Mapping | ⚠️ 弱 | ✅ 原生 | 完整支持 |
| NHI 管理 / NHI Management | ⚠️ 弱 | ✅ 深度 | 全面优势 |
| 横向移动 / Lateral Movement | ⚠️ 无 | ✅ 支持 | 独有 |
| 采购模式 / Procurement | 大合同 | ✅ 灵活 | 降低采购门槛 |

### 3.3 常用反驳话术 / Objection Handlers

**Q: "我们已经上了 SailPoint，还需要 Telos 吗？"**

> A: "这取决于您想解决什么问题。SailPoint 解决了身份合规的问题——确保正确的人有正确的权限。Telos 解决了另一个问题——这些权限是否已经被攻击者利用。
> 事实上，很多上了 SailPoint 的客户告诉我们：他们的 SailPoint 显示'账号权限合规'，但 Telos 扫描后发现了大量隐藏的服务账号、SSH 密钥复用、孤儿特权账号。
> Telos 可以作为 SailPoint 的有效补充，填补威胁检测的空白。建议先做一次全面的账号扫描，看看 SailPoint 的盲区在哪里。"

**Q: "IGA 买了已经很贵，Telos 会不会增加太多成本？"**

> A: "Telos 的定位不是替代 IGA，而是补充威胁检测能力。从 ROI 角度看，一次数据泄露的平均成本是 488 万美元。Telos 的投入远远低于一次泄露的损失。
> 更重要的是，Telos 的采购模式非常灵活——可以按账号规模订阅，不需要大额前期投入。"

**Q: "IGA 有完整的身份目录，Telos 能否集成？"**

> A: "Telos 支持 LDAP/AD 同步，可以读取您现有的身份目录数据。同时 Telos 会自动发现目录中没有记录但实际存在的账号（即影子账号），这是 IGA 的盲区。"

### 3.4 适合切入的客户画像 / ICP

| 维度 / Dimension | 特征 / Characteristics |
|----------------|---------------------|
| **IGA 实施效果不理想** | 有 SailPoint/Okta 但发现率低 |
| **NHI 快速增长** | DevOps、云原生、服务账号爆发 |
| **合规压力大** | 等保 2.0、金融合规、SOC2 |
| **安全事件后复盘** | 发现 IGA 没有检测到攻击路径 |
| **多云环境** | IGA 无法覆盖多云账号 |

---

## 4. 竞品 3：EDR 产品 / EDR Products

**竞品定位 / Positioning:**
CrowdStrike Falcon、SentinelOne、Microsoft Defender for Endpoint 等 EDR 产品定位于端点检测与响应，通过终端行为分析检测高级威胁。

### 4.1 竞品弱点 / Weaknesses

| # | 弱点 / Weakness | 严重程度 / Severity | 切入点说明 / Leverage Point |
|---|----------------|-------------------|--------------------------|
| 1 | **不分析账号语义** — EDR 聚焦进程行为，不理解账号命名、权限配置的含义 | 高 / High | 账号命名伪装（`r00t`/`ladmin`）完全逃逸 |
| 2 | **跨主机攻击路径不可见** — EDR 只看单台主机，无法分析 SSH 信任链、横向移动路径 | 高 / High | 横向移动跨越多台主机，EDR 无法串联 |
| 3 | **Linux 账号检测弱** — EDR 在 Windows 上成熟，Linux 账号检测能力普遍偏弱 | 中 / Medium | 服务器环境以 Linux 为主 |
| 4 | **NHI 检测缺失** — 服务账号、API Key、CI/CD 凭证不在 EDR 检测范围内 | 高 / High | NHI 是最大攻击面 |
| 5 | **账号生命周期管理缺失** — EDR 不管僵尸账号、离职账号 | 中 / Medium | 僵尸账号长期存在 |
| 6 | **配置风险无法感知** — Sudoers 配置、NOPASSWD 设置等操作系统配置 EDR 无法评估 | 中 / Medium | 配置即风险 |

### 4.2 Telos 对比优势 / Telos Advantages

| 对比维度 / Dimension | EDR | Telos | 差异 / Difference |
|--------------------|-----|-------|-----------------|
| 检测视角 / Detection View | 端点行为 | ✅ 账号语义 | 互补 |
| Linux 账号覆盖 / Linux Accounts | ⚠️ 弱 | ✅ 完整 | Telos 优势 |
| 横向移动分析 / Lateral Movement | ⚠️ 单主机 | ✅ 跨主机 | Telos 独有 |
| ATT&CK 映射 / ATT&CK Mapping | ⚠️ 部分 | ✅ 账号专属 | Telos 完整 |
| NHI 管理 / NHI Management | ❌ 无 | ✅ 完整 | 独有 |
| 账号配置风险 / Account Config Risk | ❌ 无 | ✅ 全面 | 独有 |
| 与现有 EDR 冲突 / Conflict | — | ✅ 互补 | 可叠加 |

### 4.3 常用反驳话术 / Objection Handlers

**Q: "我们有 CrowdStrike，为什么还需要 Telos？"**

> A: "CrowdStrike 是全球最好的 EDR 之一，但它解决的是端点行为的问题。Telos 解决的是账号层面的问题。
> 举例说明：CrowdStrike 可以检测到某台服务器上执行了 `cat /etc/shadow`——但 Telos 能告诉你这个操作背后的账号是什么、权限是否过度、是否还有其他服务器上存在相同账号、攻击者是否可以通过 SSH 密钥复用横向移动到其他资产。
> EDR 和 Telos 是互补关系。CrowdStrike 告诉你'进程 X 在执行'，Telos 告诉你'账号 Y 已被攻陷，攻击路径是 A→B→C'。"

**Q: "Telos 和 EDR 会不会重复？"**

> A: "完全不重复。打个比方：EDR 是大楼的监控摄像头（看行为），Telos 是大楼的门禁系统（管账号）。摄像头可以记录谁进来了，但不知道谁偷偷复制了一把钥匙。Telos 告诉你哪些钥匙存在风险、哪些门不应该被打开。"
> "已经有 EDR 的客户往往是我们最满意的客户——因为他们理解安全的层次感，主动告诉我们'账号安全终于有产品了'。"

**Q: "EDR 也能检测横向移动？"**

> A: "EDR 的横向移动检测基于主机间的网络流量和进程行为，精度有限。Telos 的横向移动分析基于账号权限图的可达性分析——直接告诉你从 A 账号到管理员权限的完整路径，包括每一步用了什么凭据。这是完全不同的精度和覆盖度。"

### 4.4 适合切入的客户画像 / ICP

| 维度 / Dimension | 特征 / Characteristics |
|----------------|---------------------|
| **已有 EDR 但仍有告警疲劳** | 检测多但无法判断账号层面的根因 |
| **Linux 服务器为主** | EDR Linux 检测能力弱的场景 |
| **多云环境** | 跨主机账号关联分析 |
| **DevOps 密集** | CI/CD 凭证、机器账号多 |

---

## 5. 竞品 4：云身份安全 CSPM/CIEM / Cloud Identity Security

**竞品定位 / Positioning:**
云安全态势管理（CSPM）和云基础设施授权管理（CIEM）产品如 Wiz、Zscaler CSPM、微软 Defender for Cloud、Palo Alto Prisma Cloud 等，聚焦云平台的身份与访问安全。

### 5.1 竞品弱点 / Weaknesses

| # | 弱点 / Weakness | 严重程度 / Severity | 切入点说明 / Leverage Point |
|---|----------------|-------------------|--------------------------|
| 1 | **仅限云平台** — 本地服务器、Windows AD、数据库、PAM 等账号完全无感知 | 高 / High | 混合云环境需要 Telos 统一 |
| 2 | **CIEM 侧重云 IAM** — 对服务账号、CI/CD 凭证、AI Agent 凭据覆盖不足 | 中 / Medium | NHI 的范畴远超 CIEM |
| 3 | **无五层语义分析** — CIEM 使用规则引擎，无深度语义分析 | 中 / Medium | 检测深度有限 |
| 4 | **与本地身份系统割裂** — 云 IAM 和 AD/LDAP 之间存在身份孤岛 | 高 / High | 横向移动跨越云和本地 |
| 5 | **ATT&CK 映射弱** — 主要关注 CSPM 配置错误，缺乏账号 ATT&CK 映射 | 中 / Medium | 账号攻击的 ATT&CK 映射需 Telos |
| 6 | **实施复杂** — CSPM/CIEM 通常需要大量配置才能产生价值 | 中 / Medium | Telos 更快见效 |

### 5.2 Telos 对比优势 / Telos Advantages

| 对比维度 / Dimension | CSPM/CIEM | Telos | 差异 / Difference |
|--------------------|----------|-------|-----------------|
| 平台覆盖 / Platform Coverage | 仅云 | ✅ 云+本地+混合 | 全面覆盖 |
| 五层 AI 分析 / 5-Layer AI | ❌ 无 | ✅ 完整 | 深度优势 |
| ATT&CK 映射 / ATT&CK Mapping | ⚠️ 弱 | ✅ 账号专属 | 完整 |
| 账号发现方式 / Discovery | 云 API | ✅ 主动扫描+API | 更全面 |
| NHI 覆盖 / NHI Coverage | IAM 为主 | ✅ 全类型 NHI | 广度优势 |
| 本地账号管理 / On-Prem | ❌ 无 | ✅ 完整 | 独有 |
| 部署速度 / Deployment Speed | 中 | ✅ 快 | Telos 优势 |

### 5.3 常用反驳话术 / Objection Handlers

**Q: "我们已经在用 Wiz/Prisma Cloud 了。"**

> A: "Wiz 和 Prisma Cloud 在云安全态势管理方面非常出色——主要覆盖云资源配置错误、暴露的存储桶、过度宽松的 IAM 策略。
> Telos 和 Wiz 的区别在于：**Wiz 关注云配置本身的安全，Telos 关注云账号的威胁检测**。举例：Wiz 可能告诉你某个 IAM Role 过度授权，Telos 告诉你这个 IAM Role 对应的服务账号是否被攻陷、攻击者是否已经利用它横向移动。
> 如果您只用 Wiz，我们建议做一次对比扫描：看看 Wiz 没有发现但 Telos 能发现的账号威胁是什么。"

**Q: "CIEM 已经覆盖了云 IAM。"**

> A: "CIEM 主要覆盖云平台的 IAM 用户和 Role，但机器账号的范围远大于此——Kubernetes Service Account、GitHub Actions secrets、数据库应用账号、AI Agent 的 LLM API Key……这些 NHI 类型 CIEM 通常没有覆盖。
> Telos 是全类型的 NHI 管理平台，不仅包括云 IAM，还包括 CI/CD、数据库、K8s、AI Agent 等所有非人类身份。"

### 5.4 适合切入的客户画像 / ICP

| 维度 / Dimension | 特征 / Characteristics |
|----------------|---------------------|
| **混合云/多云** | 同时使用本地+多朵云 |
| **有 CSPM 但仍有云上事故** | CSPM 告警多但无法定位根因 |
| **DevOps/AI 应用** | 大量 CI/CD 凭证、AI Agent 凭据 |
| **合规审计** | 需要统一报告云+本地账号 |

---

## 6. 竞品 5：其他 ITDR 厂商 / Other ITDR Vendors

**竞品定位 / Positioning:**
随着 ITDR 赛道的兴起，市场上出现了一批新兴 ITDR 产品，包括 Silverfort、SpecterOps (BloodHound)、Delinea、Xton Technologies 等。

### 6.1 各竞品对比 / Individual Comparisons

**6.1.1 Silverfort**

| 维度 / Dimension | Silverfort | Telos |
|----------------|-----------|-------|
| 核心能力 / Core Capability | 统一身份安全平台（UAP）| 身份威胁检测与响应 |
| 覆盖范围 / Coverage | 混合云 AD/SSO 集成 | 全平台账号扫描+五层分析 |
| ATT&CK 映射 / ATT&CK Mapping | ⚠️ 部分 | ✅ 完整账号 ATT&CK |
| NHI 管理 / NHI Management | ⚠️ 弱 | ✅ 完整 |
| 五层 AI 分析 / 5-Layer AI | ❌ 无 | ✅ 独有 |
| 切入场景 / Entry Point | SSO/MFA 集成 | 账号扫描+威胁分析 |

**6.1.2 BloodHound / SpecterOps**

| 维度 / Dimension | BloodHound | Telos |
|----------------|-----------|-------|
| 核心能力 / Core Capability | AD 攻击路径分析（开源）| 全平台账号威胁检测 |
| 覆盖范围 / Coverage | 仅 AD | ✅ 全平台 |
| 主动发现 / Proactive Discovery | ⚠️ 需手动采集 | ✅ 自动扫描 |
| ATT&CK 映射 / ATT&CK Mapping | ⚠️ 部分 | ✅ 完整 |
| 五层 AI 分析 / 5-Layer AI | ❌ 无 | ✅ 独有 |
| 产品形态 / Form | 工具（非生产级）| ✅ 企业级产品 |

**6.1.3 Delinea (Formerly Thycotic/Centrify)**

| 维度 / Dimension | Delinea | Telos |
|----------------|--------|-------|
| 核心能力 / Core Capability | 特权账号管理（PAM）| 身份威胁检测与响应 |
| 威胁检测 / Threat Detection | ⚠️ 规则引擎 | ✅ 五层 AI |
| ATT&CK 映射 / ATT&CK Mapping | ❌ 无 | ✅ 完整 |
| NHI 管理 / NHI Coverage | ⚠️ 特权账号 | ✅ 全类型 NHI |
| 账号主动发现 / Proactive Discovery | ⚠️ 手动 | ✅ 自动 |

### 6.2 Telos 的整体竞争优势 / Telos Overall Competitive Moat

```
┌──────────────────────────────────────────────┐
│           Telos 竞争护城河                     │
│                                              │
│  1. 五层 AI 分析（业界唯一）                    │
│     5-Layer AI Analysis (Industry-First)      │
│                                              │
│  2. 全平台账号覆盖（云+本地+NHI）               │
│     Universal Account Coverage                │
│                                              │
│  3. ATT&CK 原生集成 + Navigator 导出           │
│     Native ATT&CK Integration                 │
│                                              │
│  4. 小时级部署，快速见效                        │
│     Hour-level Deployment, Rapid ROI          │
│                                              │
│  5. 全类型 NHI 管理（业界最强）                 │
│     Full-spectrum NHI Management              │
└──────────────────────────────────────────────┘
```

---

## 7. 综合对比总表 / Competitive Comparison Matrix

### 7.1 功能维度对比 / Feature-by-Feature Comparison

| 功能 / Feature | Telos | 堡垒机 | IGA | EDR | CSPM/CIEM | BloodHound |
|--------------|-------|-------|-----|-----|----------|-----------|
| **账号自动发现 / Auto Discovery** | ✅ | ❌ | ⚠️ | ❌ | ⚠️ | ❌ |
| **威胁检测引擎 / Threat Detection** | ✅ | ❌ | ⚠️ | ✅ | ⚠️ | ⚠️ |
| **五层 AI 分析 / 5-Layer AI** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **ATT&CK 映射 / ATT&CK Mapping** | ✅ | ❌ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| **横向移动检测 / Lateral Movement** | ✅ | ❌ | ⚠️ | ⚠️ | ⚠️ | ✅ |
| **NHI 完整管理 / Full NHI Mgmt** | ✅ | ❌ | ⚠️ | ❌ | ⚠️ | ❌ |
| **账号生命周期 / Lifecycle Mgmt** | ✅ | ⚠️ | ✅ | ❌ | ⚠️ | ❌ |
| **多平台覆盖 / Multi-platform** | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ |
| **合规评估 / Compliance Assessment** | ✅ | ⚠️ | ✅ | ❌ | ⚠️ | ❌ |
| **ATT&CK Navigator 导出 / Export** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **部署便捷性 / Deployment Ease** | ✅ | ✅ | ❌ | ⚠️ | ⚠️ | ⚠️ |

### 7.2 客户痛点 vs 竞品响应能力 / Pain Point vs. Competitor Coverage

| 客户痛点 / Customer Pain Point | Telos | 堡垒机 | IGA | EDR |
|-----------------------------|-------|-------|-----|-----|
| 影子账号发现 / Shadow account discovery | ✅ | ❌ | ⚠️ | ❌ |
| 离职账号清理 / Departed account cleanup | ✅ | ⚠️ | ✅ | ❌ |
| 横向移动路径可见 / Lateral movement visibility | ✅ | ❌ | ❌ | ⚠️ |
| NHI 全生命周期 / Full NHI lifecycle | ✅ | ❌ | ⚠️ | ❌ |
| 合规审计自动化 / Automated compliance | ✅ | ⚠️ | ✅ | ❌ |
| ATT&CK 覆盖率可视化 / ATT&CK visualization | ✅ | ❌ | ❌ | ⚠️ |
| 实时告警 / Real-time alerting | ✅ | ⚠️ | ⚠️ | ✅ |

### 7.3 切入话术总结 / Key Talking Points Summary

**对付堡垒机客户：**
> "堡垒机记录了谁访问了什么，但 Telos 告诉你哪些账号已经被攻陷。两者互补。"

**对付 IGA 客户：**
> "IGA 告诉你谁应该有什么权限，Telos 告诉你这些权限是否已被滥用。合规做好了，检测也不能少。"

**对付 EDR 客户：**
> "EDR 看行为，Telos 看账号语义。CrowdStrike 告诉你发生了什么，Telos 告诉你哪个账号是罪魁祸首。"

**对付 CSPM 客户：**
> "CSPM 关注云配置，Telos 关注云账号的威胁。配置合规不等于账号安全。"

**对付所有客户：**
> "一次数据泄露的平均成本是 488 万美元。Telos 的投入是保险，不是成本。"

---

*Telos v2.0 | © 2026 Telos. All rights reserved.*
*Telos v2.0 | © 2026 Telos 版权所有。*
