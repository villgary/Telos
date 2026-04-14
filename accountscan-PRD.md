这是一份**账号安全审计与发现系统（Account Discovery & Audit System）**需求文档（PRD）。

---

# 原型系统需求文档 (PRD)

| 版本 | 状态 | 修改日期 | 修订人 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| V1.0 | 草案 | 2026-03-28 | Gemini | 初始原型定义 |
| V1.1 | 草案 | 2026-03-28 | Claude | 补充缺失数据模型、增加安全要求、权限模型、通知机制 |
| V1.2 | 完成 | 2026-03-31 | Claude | 新增 AI 报告、自然语言搜索、身份融合、生命周期、PAM集成、审查提醒、Excel导出、账号风险评分、合规框架、多语言支持 |

---

## 1. 项目背景

在复杂的 IT 环境中，非预期的账号创建（如黑客后门、临时维护遗留）是重大的安全隐患。本系统旨在通过自动化扫描和历史快照对比，帮助安全管理员实时掌握资产账号状态，并借助 AI 能力提供智能化威胁分析与合规自动化。

## 2. 核心目标

- **资产兼容性：** 支持 Linux (SSH) 和 Windows (WinRM) 的账号提取，以及数据库和网络设备。
- **全量扫描：** 不仅采集特权账号，也采集系统默认及普通用户账号。
- **历史审计：** 实现两次扫描任务之间的账号增、删、改差异对比。
- **AI 智能分析：** 自然语言威胁报告、账号风险评分、自然语言资产搜索。
- **身份融合：** 跨系统识别同一自然人账号。
- **合规自动化：** 支持 SOC2 / ISO 27001 / 等保2.0 自动评估，Excel 报表导出。
- **账号生命周期：** 活跃 → 休眠 → 离机状态自动跟踪与告警。
- **安全合规：** 凭据安全存储、操作审计可追溯、权限最小化、多语言支持。

---

## 3. 功能需求

### 3.1 资产与凭据管理

#### 3.1.1 资产配置
- 支持录入：IP 地址、主机名（hostname）、操作系统类型（Linux / Windows）。
- 资产具有连接状态：`untested`（未测试）、`online`（在线）、`offline`（离线）、`auth_failed`（认证失败）。
- 支持测试连接（ping / port check）。
- 支持按资产类型（category）和资产分组（group）管理。
- 支持导入导出（Excel 格式）。

#### 3.1.2 资产拓扑
- 记录资产之间的关系：物理机 → 虚拟机 → 数据库，Web → App → DB 分层架构。
- 横向移动风险分析：高风险资产作为入口点，追踪可达高权限资产路径。
- 拓扑可视化（节点关系图），按关系类型（hosts_vm / runs_service / network_peer 等）着色。

#### 3.1.3 凭据中心
- 集中管理登录凭据，支持两种认证方式：
  - **用户名 + 密码**
  - **SSH 密钥对**（私钥内容 + 私钥密码 passphrase，支持 RSA/ED25519）
- **安全要求：** 密码和私钥内容在数据库中需 AES-256 加密存储。
  - 加密密钥由环境变量或密钥管理服务（KMS）注入，不硬编码。
  - 私钥 passphrase 单独加密存储。
- 凭据可关联多个资产。

#### 3.1.4 权限模型
系统内置以下角色：

| 角色 | 权限范围 |
|------|----------|
| `admin` | 全量读写，包括凭据管理 |
| `operator` | 资产增删改、发起扫描、查看快照，不可见明文凭据 |
| `viewer` | 只读访问，查看资产和快照，不可操作扫描 |

> **说明：** 普通用户不可见任何明文凭据内容；敏感操作（删除资产/凭据）需 `admin` 角色。

### 3.2 自动化扫描引擎

#### 3.2.1 扫描任务管理
- **手动触发：** 用户选择资产，点击"立即扫描"。
- **定时预约：** 支持 Cron 表达式配置周期性扫描任务（可按资产分组）。
- **任务状态：** `pending` → `running` → `success` / `partial_success` / `failed`。
  - `partial_success`：部分资产扫描成功，部分失败。
- **并发控制：** 同一资产同时只允许一个扫描任务执行，防止数据竞争。

#### 3.2.2 多源采集

**Linux（SSH）：**
| 数据项 | 来源 | 说明 |
|--------|------|------|
| 用户账号 | `/etc/passwd` | username, uid, gid, gecos, home, shell |
| 密码状态 | `/etc/shadow` | 是否过期、是否锁定 |
| Sudo 权限 | `/etc/sudoers` + `visudo -c` | 是否属于 sudo 或 wheel 组 |
| SSH 公钥 | `~/.ssh/authorized_keys` | 公钥指纹 |
| 最近登录 | `lastlog` | 最近登录时间 |

**Windows（WinRM）：**
| 数据项 | 来源 | 说明 |
|--------|------|------|
| 本地用户 | `Get-LocalUser` | username, SID, Enabled, PasswordExpired |
| 用户组 | `Get-LocalGroupMember -Group Administrators` | 管理员组成员 |
| 账号状态 | `net user <username>` | 密码永不过期等属性 |

#### 3.2.3 异步处理
- 扫描逻辑在后台任务中执行，不阻塞前端。
- **重试机制：** 连接失败自动重试 3 次，间隔 30s / 60s / 120s。
- **超时控制：** 单资产扫描超时时间为 120s（可配置）。
- **扫描结果写入：** raw_info JSON 中**不存储密码哈希**，采集字段由 §5 快照表定义。

### 3.3 差异比对（Diff Engine）

#### 3.3.1 快照存储
- 每次扫描完成后，结果作为"快照"存入数据库，关联资产 ID 和任务批次 ID。
- 快照为只读记录，不修改；历史数据永久保留。

#### 3.3.2 对比逻辑

| 差异类型 | 判断规则 | 风险等级 |
|----------|----------|----------|
| **新增账号** | 快照 B 中存在 username，快照 A 中不存在 | 🔴 异常 |
| **消失账号** | 快照 A 中存在 username，快照 B 中不存在 | 🟡 关注 |
| **权限爬升** | 同一 `uid_sid`，`is_admin` 从 `False` 变为 `True` | 🔴 异常 |
| **账号禁用** | 同一 `uid_sid`，状态从 `enabled` 变为 `disabled` | 🟢 正常 |
| **UID/SID 不变，属性变更** | username 的 gecos/shell 等元数据变化 | 🟡 关注 |

> **异常账号判定标准：** 新增账号（`added`）和权限爬升（`escalated`）直接标记为异常；其余需管理员复核后标记为"合规变更"或"确认后门"。

#### 3.3.3 告警通知
- 支持配置通知渠道：邮件（ SMTP）、钉钉群机器人（Webhook）、Slack Webhook。
- 触发条件：扫描发现新增账号或权限爬升时，发送告警。
- 告警分级：`critical`（严重）/ `warning`（警告）/ `info`（信息）。

### 3.4 AI 智能分析

#### 3.4.1 AI 安全态势摘要
- LLM 自动分析扫描结果、拓扑关系、资产上下文，生成自然语言威胁报告。
- **语言跟随：** 报告语言跟随 UI 当前语言（zh-CN 生成中文报告，en-US 生成英文报告）。
- 支持配置 LLM Provider（MiniMax / DeepSeek / Claude / OpenAI，可配置 API 地址和 Key）。

#### 3.4.2 自然语言资产搜索
- 用户输入自然语言查询，系统自动解析为 SQL/Graph 查询并执行。
- 示例查询：
  - "过去30天有新增管理员账号的Linux服务器"
  - "和 ASM-00001 相同物理机上的所有数据库账号"
  - "所有在生产环境存在的 root 或 admin 通用账号"
  - "权限高于 postgres 但最近 90 天未登录的账号"

#### 3.4.3 账号风险评分
每个账号快照独立计算风险分（0-100），因子包括：

| 因子 | 触发条件 | 分值 |
|------|---------|------|
| 长期未登录 | last_login > 90天 | +20 |
| 特权账号 | is_admin=True | +15 |
| 高危用户名 | root/admin/postgres/sa 等 | +10 |
| 免密sudo | NOPASSWD in sudoers | +10 |
| 跨系统关联 | 同一身份跨N个资产 | +5*N，上限20 |
| 休眠账号 | lifecycle_status=dormant | +10 |
| 离机账号 | lifecycle_status=departed | +20 |

- 总分封顶100
- 等级：>=70 critical，>=45 high，>=25 medium，<25 low
- 触发时机：扫描完成 / 身份融合 / 手动重算

### 3.5 身份融合

#### 3.5.1 跨系统身份识别
- 同一自然人在多个系统中有多个账号（LDAP / GitHub / AWS / Linux 本地）。
- 通过 UID / 用户名相似度匹配，自动建立 HumanIdentity 档案。
- 支持手动关联（当自动融合置信度不足时）。

#### 3.5.2 融合置信度
| 匹配条件 | 置信度增量 |
|---------|-----------|
| UID 完全一致 | +40 |
| 用户名完全一致（忽略大小写） | +30 |
| 用户名前缀相同 | +15 |
| 同一资产上 | +20 |
| 手工关联 | +100（覆盖） |

### 3.6 账号生命周期管理

| 状态 | 触发条件 | 动作 |
|------|---------|------|
| **活跃** | last_login <= 活跃阈值（默认30天） | 正常 |
| **休眠** | 活跃阈值 < last_login <= 休眠阈值（默认90天） | 标记，触发告警 |
| **离机** | last_login > 休眠阈值 | 标记，触发 critical 告警 |

- 阈值可配置（活跃天数 / 休眠天数）。
- 支持自动告警开关。
- 结合身份融合：同一 HumanIdentity 下所有账号，任一活跃则整体为活跃。

### 3.7 合规中心

#### 3.7.1 多框架自动评估
| 合规框架 | 检查项 | 说明 |
|---------|------|------|
| **SOC2** | CC6.3 特权账号定期审查 | 检查账号 last_login，识别长期未审账号 |
| **ISO 27001** | A.9.2.3 权限管理 | 检查 sudoers / Administrators 组 |
| **等保2.0** | 三权分立 | 检查是否存在同时拥有管理+审计权限的账号 |
| **PCI-DSS** | 共享账号禁用 | 检查是否存在 root / admin 类共享账号 |

#### 3.7.2 合规报告
- 每次评估生成报告，含：通过率 / 失败项清单 / 处置建议。
- 支持 Excel 导出（合规报告）。

### 3.8 PAM 集成（堡垒机）

- **支持类型：** CustomAPI / 腾讯云 / 阿里云 / CyberArk
- **集成方式：** 只读对接（采集账号快照，不做变更）
- 支持同步账号列表到本地资产管理。

### 3.9 定期账号审查提醒

#### 3.9.1 审查计划
- 配置审查周期：月度 / 季度。
- 配置执行日（每月/每季度第几天）。
- 配置通知渠道：邮件列表 + Webhook URL。
- 支持启用/禁用。

#### 3.9.2 审查报告
- 自动生成报告，包含：
  - 周期内新增特权账号
  - 休眠账号清单
  - 离机账号清单
  - 高风险账号清单
- 支持审核流程：草稿 → 待审核 → 已通过 / 已忽略
- 支持 Excel 导出（审查报告）。

---

## 4. 界面原型设计（UI/UX）

### 4.1 仪表盘（Dashboard）
- **统计卡片：** 资产总数、在线资产数、异常账号总数、最近 24 小时新增账号。
- **风险仪表：** 综合风险分（0-100），5色刻度。
- **资产类型分布：** 饼图（Linux / Windows / Database / Network 等）。
- **最近告警：** 告警中心卡片，含分级标签。
- **横向移动风险热点：** 高风险传播路径卡片（Top 3）。

### 4.2 AI 智能分析页
- **Tab 1：** AI 安全态势摘要 — 点击"生成报告"，LLM 生成威胁分析报告。
- **Tab 2：** 自然语言搜索 — 输入框 + 示例查询 + 结果资产卡片。
- **Tab 3：** 账号风险分析 — 点击"生成"，LLM 基于账号风险评分输出分析报告。

### 4.3 资产管理页
- **列表字段：** 复选框、IP、主机名、系统类型、连接状态、品类、分组、最后扫描时间、操作列。
- **操作：** 添加资产（抽屉表单）、编辑、测试连接、删除、立即扫描。

### 4.4 扫描任务页
- **列表字段：** 任务 ID、关联资产数、成功/失败数、开始时间、耗时、状态。
- **操作：** 查看详情（跳转扫描详情页）、取消（仅 running 状态）。

### 4.5 扫描详情与对比页
- **筛选器：** 选择"基准批次"（A）和"对比批次"（B）。
- **结果展示：** 三色标记 + 差异类型标签 + 账号详情。
  - 🔴 **红色：** 异常新增（疑似后门）/ 权限爬升 → 可一键"标记为合规"或"确认为后门"
  - 🟡 **黄色：** 消失账号 / 元数据变更 → 需管理员复核
  - 🟢 **绿色：** 已确认的合规变更
- **账号详情：** 点击展开可查看 `uid_sid`、`is_admin`、采集时间、`raw_info`（已脱敏）

### 4.6 合规中心页
- 左侧：合规框架列表（SOC2 / ISO 27001 / 等保2.0 / PCI-DSS）。
- 右侧：选中框架的评估结果（通过/失败/未评分）+ 执行历史。
- 按钮：评估全部 / 导出 Excel。

### 4.7 身份融合页
- **HumanIdentity 列表：** 身份名称、置信度、关联账号数、风险分、状态。
- **账号关联视图：** 展示同一身份下跨系统的所有账号卡片。
- **操作：** 手动关联 / 取消关联 / 审核通过。

### 4.8 账号生命周期页
- **配置区：** 活跃阈值 / 休眠阈值 / 自动告警开关。
- **账号状态分布：** 活跃 / 休眠 / 离机 统计卡片。
- **账号明细表：** 用户名、资产、状态、last_login、关联身份，可按状态筛选。

### 4.9 堡垒机集成页
- **集成列表：** 名称、类型、状态、上次同步时间。
- **操作：** 添加集成（配置表单）、测试连接、同步、删除。

### 4.10 审查提醒页
- **审查计划卡片：** 名称、周期、执行日、渠道、下次执行时间、启用开关。
- **审查报告历史表格：** 周期、生成时间、状态、审核人、操作（查看/通过/忽略/导出Excel）。

### 4.11 凭据管理页（admin 可见）
- **列表字段：** 凭据名称（别名）、关联资产数、认证类型（密码/密钥）、创建时间。
- **操作：** 添加凭据、编辑、删除（关联资产时禁止删除）。

### 4.12 多语言支持
- 头部右侧 LanguageSwitcher：中文 / English。
- 切换即时生效，无需刷新页面。
- AI 报告语言跟随 UI 当前语言。

---

## 5. 数据模型（核心表）

### 5.1 `users`（用户表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| username | varchar(64) UNIQUE | 登录用户名 |
| password_hash | varchar(256) | 登录密码（bcrypt 哈希） |
| role | enum('admin','operator','viewer') | 角色 |
| email | varchar(128) | 通知邮箱 |
| is_active | boolean | 是否启用 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 5.2 `assets`（资产表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| ip | varchar(45) UNIQUE | 目标 IP（支持 IPv6） |
| hostname | varchar(255) | 主机名（可为空） |
| asset_code | varchar(32) | 资产编号（如 ASM-00001） |
| os_type | enum('linux','windows','database','network','other') | 操作系统类型 |
| category_id | bigint FK | 资产品类 ID |
| port | int | SSH(22) 或 WinRM(5985/5986)，默认 22 |
| status | enum('untested','online','offline','auth_failed') | 连接状态 |
| risk_score | int | 资产风险分（0-100） |
| risk_level | enum('critical','high','medium','low') | 风险等级 |
| last_scan_at | datetime | 最后扫描时间 |
| last_scan_job_id | bigint FK | 最后一次扫描任务 ID |
| credential_id | bigint FK | 关联凭据 ID |
| created_by | bigint FK | 创建人（users.id） |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 5.3 `asset_relationships`（资产关系表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| source_asset_id | bigint FK | 源资产 |
| target_asset_id | bigint FK | 目标资产 |
| relation_type | varchar(32) | 关系类型（hosts_vm / runs_service / network_peer 等） |
| created_at | datetime | 创建时间 |

### 5.4 `credentials`（凭据表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| name | varchar(128) UNIQUE | 凭据别名（如"运维账号-aliyun-prod"） |
| auth_type | enum('password','ssh_key') | 认证类型 |
| username | varchar(128) | 登录用户名 |
| password_enc | blob | AES-256 加密后的密码密文 |
| private_key_enc | blob | AES-256 加密后的私钥内容（SSH 密钥方式） |
| passphrase_enc | blob | AES-256 加密后的私钥密码（如有） |
| created_by | bigint FK | 创建人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

> **AES-256 加密说明：**
> - 算法：AES-256-GCM（加密 + 认证，防止篡改）。
> - 密钥来源：`ACCOUNTSCAN_MASTER_KEY` 环境变量注入（32 字节），生产环境建议使用 AWS KMS / HashiCorp Vault 管理。
> - 每条记录的 IV（初始化向量）随机生成，与密文一同存储。

### 5.5 `scan_jobs`（扫描任务表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| trigger_type | enum('manual','scheduled') | 触发方式 |
| status | enum('pending','running','success','partial_success','failed','cancelled') | 任务状态 |
| total_assets | int | 计划扫描资产数 |
| success_count | int | 成功数 |
| failed_count | int | 失败数 |
| started_at | datetime | 开始时间 |
| finished_at | datetime | 结束时间（可空） |
| created_by | bigint FK | 创建人 |
| created_at | datetime | 创建时间 |

### 5.6 `account_snapshots`（快照数据表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| asset_id | bigint FK | 所属资产 |
| job_id | bigint FK | 所属扫描任务批次 |
| username | varchar(128) | 账号名称 |
| uid_sid | varchar(256) | 唯一标识（Linux UID 或 Windows SID） |
| is_admin | boolean | 是否具备管理（sudo/Administrators）权限 |
| account_status | varchar(32) | 账号状态（如 enabled/disabled/locked） |
| home_dir | varchar(512) | 主目录（Linux）/ Profile 路径（Windows） |
| shell | varchar(128) | 登录 shell（Linux） |
| groups | json | 所属组列表（JSON 数组） |
| sudo_config | json | Sudo 权限配置（Linux，仅相关用户） |
| last_login | datetime | 最近登录时间（可空） |
| lifecycle_status | enum('active','dormant','departed') | 生命周期状态 |
| raw_info | json | 脱敏后的原始采集数据（不含密码哈希） |
| snapshot_time | datetime | 快照生成时间（= scan_jobs.started_at） |
| deleted_at | datetime | 软删除时间（扫描结果不物理删除） |

> **raw_info 脱敏规则：** `/etc/shadow` 的密码哈希字段替换为 `[REDACTED]`；Windows SAM 数据库内容不上报，仅上报解析后的结构化数据。

### 5.7 `human_identities`（身份融合表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| primary_username | varchar(128) | 主用户名 |
| confidence | int | 置信度（0-100） |
| status | enum('pending','confirmed','rejected') | 审核状态 |
| risk_score | int | 综合风险分（0-100） |
| reviewed_by | bigint FK | 审核人 |
| reviewed_at | datetime | 审核时间 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 5.8 `identity_accounts`（身份-账号关联表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| identity_id | bigint FK | HumanIdentity ID |
| snapshot_id | bigint FK | AccountSnapshot ID |
| match_type | enum('uid_match','username_match','prefix_match','same_asset','manual') | 匹配类型 |
| confidence | int | 本次匹配置信度 |
| created_at | datetime | 创建时间 |

### 5.9 `account_risk_scores`（账号风险评分表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| snapshot_id | bigint FK (unique) | AccountSnapshot ID |
| risk_score | int | 风险分（0-100） |
| risk_level | enum('critical','high','medium','low') | 风险等级 |
| risk_factors | json | 因子详情（如 `[{factor, score}]`） |
| identity_id | bigint FK (nullable) | HumanIdentity ID |
| cross_asset_count | int | 该身份跨资产数 |
| computed_at | datetime | 计算时间 |

### 5.10 `diff_results`（差异比对结果表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| base_job_id | bigint FK | 基准快照任务 ID |
| compare_job_id | bigint FK | 对比快照任务 ID |
| diff_type | enum('added','removed','escalated','deactivated','modified') | 差异类型 |
| risk_level | enum('critical','warning','info') | 风险等级 |
| snapshot_a_id | bigint FK | 快照 A ID（可空，仅新增时有快照 B） |
| snapshot_b_id | bigint FK | 快照 B ID（可空，仅消失时有快照 A） |
| status | enum('pending','confirmed_safe','confirmed_threat') | 复核状态 |
| reviewed_by | bigint FK | 复核人 |
| reviewed_at | datetime | 复核时间 |
| created_at | datetime | 生成时间 |

### 5.11 `review_schedules`（审查计划表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| name | varchar(128) | 计划名称 |
| period | enum('monthly','quarterly') | 审查周期 |
| day_of_month | int | 执行日（1-28） |
| alert_channels | json | 通知渠道（如 `{"email": [], "webhook": ""}`） |
| enabled | boolean | 是否启用 |
| next_run_at | datetime | 下次执行时间 |
| created_by | bigint FK | 创建人 |
| created_at | datetime | 创建时间 |

### 5.12 `review_reports`（审查报告表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| schedule_id | bigint FK | 审查计划 ID |
| period | enum('monthly','quarterly') | 本次报告所属周期 |
| period_start | datetime | 周期起始 |
| period_end | datetime | 周期结束 |
| status | enum('draft','pending_review','approved','dismissed') | 审核状态 |
| reviewed_by | bigint FK | 审核人 |
| reviewed_at | datetime | 审核时间 |
| notes | text | 审核备注 |
| content_summary | json | 报告摘要 JSON |
| created_at | datetime | 创建时间 |

### 5.13 `audit_logs`（审计日志表）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | bigint PK | 主键 |
| user_id | bigint FK | 操作人 |
| action | varchar(64) | 操作类型（如 `asset.create`, `scan.trigger`） |
| target_type | varchar(32) | 目标资源类型 |
| target_id | bigint | 目标资源 ID |
| detail | json | 操作详情（旧值/新值） |
| ip_address | varchar(45) | 操作来源 IP |
| created_at | datetime | 操作时间 |

---

## 6. 技术架构建议

### 6.1 技术栈

| 组件 | 建议选型 | 说明 |
|------|----------|------|
| 后端框架 | FastAPI（Python） | 高性能、自动 OpenAPI 文档 |
| 数据库 | SQLite / PostgreSQL | JSONB 字段支持 |
| 前端 | React + Ant Design + TypeScript | 企业级组件库 |
| i18n | i18next + react-i18next | 多语言支持 |
| AI/LLM | MiniMax / DeepSeek / Claude / OpenAI | 可配置多 Provider |
| SSH 连接 | Paramiko（Python） | SSH 协议实现 |
| WinRM 连接 | PyWinRM（Python） | WinRM 协议实现 |
| 加密 | cryptography AES-256-GCM | 生产级加密 |
| 图表 | Recharts | 资产分布、趋势图表 |
| Excel 导出 | openpyxl | 报表导出 |

### 6.2 API 规范（完整端点）

#### 资产与扫描
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/assets` | 创建资产 | operator+ |
| GET | `/api/v1/assets` | 资产列表（分页、筛选） | viewer+ |
| PUT | `/api/v1/assets/{id}` | 更新资产 | operator+ |
| DELETE | `/api/v1/assets/{id}` | 删除资产 | operator+ |
| POST | `/api/v1/assets/{id}/test` | 测试连接 | operator+ |
| POST | `/api/v1/assets/{id}/scan` | 触发扫描 | operator+ |
| GET | `/api/v1/assets/{id}/relationships` | 资产关系 | viewer+ |
| POST | `/api/v1/assets/{id}/relationships` | 添加关系 | operator+ |
| DELETE | `/api/v1/assets/{id}/relationships/{rid}` | 删除关系 | operator+ |

#### 扫描任务与快照
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/scan-jobs` | 扫描任务列表 | viewer+ |
| GET | `/api/v1/scan-jobs/{id}` | 扫描任务详情 | viewer+ |
| POST | `/api/v1/scan-jobs/{id}/cancel` | 取消任务 | operator+ |
| GET | `/api/v1/assets/{id}/snapshots` | 资产快照列表 | viewer+ |
| GET | `/api/v1/snapshots/diff` | 差异对比（?base=&compare=） | viewer+ |
| POST | `/api/v1/snapshots/{id}/confirm-safe` | 标记为合规 | operator+ |
| POST | `/api/v1/snapshots/{id}/confirm-threat` | 确认为后门 | operator+ |

#### AI 与报告
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/ai/dashboard` | Dashboard 指标（缓存5分钟） | viewer+ |
| POST | `/api/v1/ai/report` | 生成 AI 报告（可指定语言） | viewer+ |
| POST | `/api/v1/ai/nl-search` | 自然语言资产搜索 | viewer+ |
| GET | `/api/v1/llm/config` | 获取 LLM 配置 | admin |
| PUT | `/api/v1/llm/config` | 更新 LLM 配置 | admin |

#### 身份融合
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/identities` | 身份列表 | viewer+ |
| GET | `/api/v1/identities/{id}` | 身份详情 | viewer+ |
| POST | `/api/v1/identities/{id}/link` | 手动关联账号 | operator+ |
| DELETE | `/api/v1/identities/{id}/accounts/{snapshot_id}` | 取消关联 | operator+ |
| POST | `/api/v1/identities/fuse` | 触发自动融合 | operator+ |

#### 账号生命周期
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/lifecycle/config` | 获取配置 | viewer+ |
| PUT | `/api/v1/lifecycle/config` | 更新配置（阈值、告警开关） | admin |

#### 合规中心
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/compliance/frameworks` | 合规框架列表 | viewer+ |
| POST | `/api/v1/compliance/run/{framework}` | 执行单框架评估 | operator+ |
| POST | `/api/v1/compliance/run-all` | 执行全部评估 | operator+ |
| GET | `/api/v1/compliance/runs` | 评估历史 | viewer+ |
| GET | `/api/v1/compliance/runs/{id}` | 评估报告详情 | viewer+ |

#### 账号风险评分
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/risk/account/{snapshot_id}` | 单个账号评分详情 | viewer+ |
| GET | `/api/v1/risk/accounts` | 评分列表（分页、排序） | viewer+ |
| POST | `/api/v1/risk/accounts/recompute` | 全量重算 | admin |

#### 审查提醒
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/review/schedules` | 审查计划列表 | viewer+ |
| POST | `/api/v1/review/schedules` | 新增计划 | admin |
| PUT | `/api/v1/review/schedules/{id}` | 更新计划 | admin |
| DELETE | `/api/v1/review/schedules/{id}` | 删除计划 | admin |
| GET | `/api/v1/review/reports` | 报告历史 | viewer+ |
| GET | `/api/v1/review/reports/{id}` | 报告详情 | viewer+ |
| POST | `/api/v1/review/reports/{id}/approve` | 审核通过 | operator+ |
| POST | `/api/v1/review/reports/{id}/dismiss` | 标记已处理 | operator+ |
| POST | `/api/v1/review/generate` | 手动触发报告生成 | operator+ |

#### 报表导出
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/export/review-report/{report_id}` | 下载审查报告 Excel | viewer+ |
| GET | `/api/v1/export/compliance-run/{run_id}` | 下载合规报告 Excel | viewer+ |

#### PAM 集成
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/pam/integrations` | 集成列表 | viewer+ |
| POST | `/api/v1/pam/integrations` | 添加集成 | admin |
| PUT | `/api/v1/pam/integrations/{id}` | 更新集成 | admin |
| DELETE | `/api/v1/pam/integrations/{id}` | 删除集成 | admin |
| POST | `/api/v1/pam/integrations/{id}/test` | 测试连接 | operator+ |
| POST | `/api/v1/pam/integrations/{id}/sync` | 立即同步 | operator+ |

#### 基础
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/credentials` | 创建凭据 | admin |
| GET | `/api/v1/credentials` | 凭据列表（不含明文） | admin |
| GET | `/api/v1/credentials/{id}` | 凭据详情（admin） | admin |
| PUT | `/api/v1/credentials/{id}` | 更新凭据 | admin |
| DELETE | `/api/v1/credentials/{id}` | 删除凭据 | admin |
| POST | `/api/v1/auth/login` | 用户登录 | 公开 |
| GET | `/api/v1/audit-logs` | 审计日志 | admin |
| GET | `/api/v1/alerts` | 告警列表 | viewer+ |
| POST | `/api/v1/alerts/{id}/read` | 标记已读 | viewer+ |
| GET | `/api/v1/asset-categories` | 资产品类列表 | viewer+ |
| POST | `/api/v1/asset-categories` | 新增品类 | admin |
| DELETE | `/api/v1/asset-categories/{id}` | 删除品类 | admin |
| GET | `/api/v1/asset-groups` | 资产分组列表 | viewer+ |
| POST | `/api/v1/asset-groups` | 新增分组 | admin |
| DELETE | `/api/v1/asset-groups/{id}` | 删除分组 | admin |

---

## 7. 安全要求汇总

| # | 要求 | 实现位置 |
|---|------|----------|
| S-1 | 凭据 AES-256-GCM 加密存储 | credentials 表 + 加密服务层 |
| S-2 | 登录密码 bcrypt 哈希 | users 表 |
| S-3 | raw_info 不含密码哈希 | 扫描采集层过滤 |
| S-4 | SSH 私钥 passphrase 单独加密 | credentials.passphrase_enc |
| S-5 | 操作日志全量记录（审计） | audit_logs 表 |
| S-6 | 最小权限角色模型 | users.role 字段 |
| S-7 | 凭据不可被 operator/viewer 可见 | API 权限拦截层 |
| S-8 | 扫描并发控制（防数据竞争） | 扫描任务调度层 |
| S-9 | AI 报告语言跟随 UI 自动切换 | i18n.lang 参数传递 |

---

## 8. 路线图（Roadmap）

| Phase | 目标 | 关键交付物 | 状态 |
|-------|------|-----------|------|
| **Phase 1** | Linux SSH 扫描 + 基础 Web UI | 资产 CRUD、Linux 账号采集（passwd/sudoers）、快照展示、用户登录（JWT） | ✅ 已完成 |
| **Phase 2** | Windows 扫描 + 差异告警 | WinRM 扫描插件、Diff Engine、告警通知渠道（邮件/Webhook）、差异复核流程 | ✅ 已完成 |
| **Phase 3** | 合规 + 身份融合 | SOC2/ISO27001/等保2.0 合规框架、身份融合、生命周期管理、PAM集成 | ✅ 已完成 |
| **Phase 4** | AI 智能化 | AI 威胁报告（语言跟随）、自然语言搜索、账号风险评分、横向移动分析 | ✅ 已完成 |
| **Phase 5** | 审查自动化 | 定期账号审查提醒（月度/季度）、Excel 报表导出 | ✅ 已完成 |
| **Phase 6** | 国际化 | i18n 架构（zh-CN + en-US）、LanguageSwitcher、多语言 Ant Design | ✅ 已完成 |
| **Phase 7** | 行为分析 | 基于历史基线的 UEBA、SIEM/SOAR 集成 | 🚧 规划中 |
| **Phase 8** | 策略即代码 | OPA/Rego 策略引擎 | 🚧 规划中 |

> **验收标准：** 每个 Phase 交付前需通过：功能演示 + 安全评审（凭据存储审计 + 权限模型验证）。

---

## 9. 术语表

| 术语 | 定义 |
|------|------|
| 快照（Snapshot） | 一次扫描任务对指定资产账号数据的完整采集记录 |
| 批次（Job） | 一次扫描任务，可能包含多个资产 |
| 差异（Diff） | 两次快照之间的账号状态变化 |
| 权限爬升（Escalation） | 账号从非管理员变为管理员 |
| AES-256-GCM | 带认证的块加密算法，兼顾机密性和完整性 |
| WinRM | Windows Remote Management，Windows 原生远程管理协议 |
| HumanIdentity | 跨系统融合后的同一自然人身份档案 |
| 生命周期（Lifecycle） | 账号从活跃到休眠到离机的状态流转 |
| PAM | Privileged Access Management，堡垒机/特权账号管理 |
| i18n | Internationalization，多语言支持 |
