# AccountScan 产品路线图

> **愿景**：智能化身份威胁检测与合规平台
> **定位**：从账号扫描工具 → 持续身份监控 + AI 推理 + 合规自动化平台

---

## 现状分析

**当前能力**：
- Linux / Windows / 数据库 / 网络设备 / IoT 账号扫描
- 资产拓扑关系管理（物理机 → 虚拟机 → 数据库）
- 账号快照与基线比对
- 多语言支持（中文 + 英文，架构支持任意语言扩展）
- AI 威胁报告生成（中文/英文随 UI 语言自动切换）
- 自然语言资产搜索（LLM 解析查询）
- 账号风险评分（基于登录频率 + 特权范围 + 身份融合）
- 多合规框架自动验证（SOC2 / ISO 27001 / 等保2.0）
- 账号身份融合：跨系统同一自然人识别
- 账号生命周期管理（活跃 → 休眠 → 离机）
- PAM / 堡垒机集成（CustomAPI / 腾讯云 / 阿里云 / CyberArk）
- 定期账号审查提醒（月度 / 季度 Review）
- 横向移动风险热点分析
- Excel 报表导出（审查报告 / 合规报告）

**待填补的能力缺口**：
- 行为分析（基于历史基线的 UEBA）
- SIEM / SOAR 集成
- 策略即代码（OPA/Rego）

---

## 最终愿景：Identity Threat Detection & Compliance Platform

### 核心概念演进

| 当前 | 未来 |
|------|------|
| 扫描发现 | 持续监控 + 异常检测 |
| JSON 快照 | 自然语言报告 |
| 手动关系建立 | 自动拓扑推理 |
| 规则告警 | LLM 辅助推理 |
| 工具 | 平台 |

---

## 一、知识图谱与本体论

### 1.1 账号安全本体（Ontology）

```python
# 实体（Entity）
PhysicalAsset       # 物理机
VirtualAsset        # VM / 容器
ServiceAccount      # 服务账号（MySQL root, postgres）
HumanAccount       # 人员账号（LDAP / AD 同步）
Credential         # 凭据（密码 / SSH Key / Cert）
IdentityProvider    # 身份源（LDAP / AD / SSO / GitHub）

# 关系（Relation）
runs_on:      VM          → PhysicalAsset      # 虚拟机运行于物理机
hosts:        OS          → Database           # 操作系统承载数据库
maps_to:      DB_Account  → HumanAccount       # 数据库账号映射到自然人
synced_from:  Cloud_Account → AD_Account       # 云账号同步自 AD
grants_to:    Group       → Account            # 用户组授予权限
```

### 1.2 风险传播推理引擎

```
物理机被攻陷 → 旗下所有虚拟机 → 虚拟机上所有数据库
自动量化风险路径和影响范围，生成处置建议。
```

### 1.3 账号身份融合

```
同一自然人在多个系统中有多个账号：
  LDAP: zhangsan@company.com
  GitHub: zhangsan_cn
  AWS: zhangsan-root
  本地: zhangsan@192.168.1.12

融合后：HumanIdentity(zhangsan)
  - risk_score: 78/100
  - accounts: [LDAP, GitHub, AWS, Linux]
  - certification_status: 待认证
```

---

## 二、AI/LLM 技术整合

### 2.1 自然语言威胁报告生成 ✅

**输入**：扫描结果 + 拓扑关系 + 资产上下文
**输出**：自然语言威胁报告（语言跟随 UI 自动切换）

```
例（中文 UI）：
"192.168.1.12 上发现 6 个账号，其中 root@localhost
权限极高且从未登录，存在配置错误风险。
关联资产：ASM-00004 (VMware 虚拟机)，
若该虚拟机被攻陷，将直接暴露数据库所有账号。
建议：审查 root 账号来源，禁用 debian-sys-maint 的外部访问权限。"
```

**技术路径**：MiniMax / DeepSeek / Claude API / OpenAI（可配置）

### 2.2 自然语言资产查询 ✅

**示例**：
```
"过去30天有新增管理员账号的Linux服务器"
"和ASM-00001相同物理机上的所有数据库账号"
"所有在生产环境存在的test或admin通用账号"
"权限高于postgres但最近90天未登录的账号"
```

**技术路径**：自然语言 → LLM 解析为 SQL/Graph 查询 → 执行

### 2.3 异常检测增强

| 异常类型 | 规则 | LLM 增强 |
|---------|------|---------|
| 新增特权账号 | 告警 | 上下文推理：是否在变更窗口内？ |
| 同一账号多资产 | 正常 vs 横向移动 | 结合拓扑判断是否属于同一业务单元 |
| 权限升级 | diff 比对 | 评估攻击路径的杀伤链概率 |
| 非工作时段登录 | 时间规则 | 结合日历，判断是否值班人员 |

### 2.4 RAG：账号安全知识库

```
用户问："为什么 MySQL root 账号风险高？"
系统答：
→ 检索 CVE 数据库：MySQL 已知特权账号漏洞
→ 检索 MITRE ATT&CK：T1078.003 特权账号利用
→ 检索本系统：root 最近登录时间、关联资产拓扑
→ 生成回答
```

### 2.5 账号风险评分 ✅

每个账号快照计算独立风险分（0-100），因子包括：

| 因子 | 触发条件 | 分值 |
|------|---------|------|
| 长期未登录 | last_login > 90天 | +20 |
| 特权账号 | is_admin=True | +15 |
| 高危用户名 | root/admin/postgres/sa 等 | +10 |
| 免密sudo | NOPASSWD in sudoers | +10 |
| 跨系统关联 | 同一身份跨N个资产 | +5*N，上限20 |
| 休眠账号 | lifecycle_status=dormant | +10 |
| 离机账号 | lifecycle_status=departed | +20 |

---

## 三、认知科学 UX 设计

### 3.1 双模式界面

**运营者（Operator）**：快速定位问题
- 告警优先级队列
- 一键处置（禁用账号、封禁 IP）
- 操作历史追溯

**管理者（Manager/CISO）**：理解全局态势
- 数字仪表盘：风险分数、合规进度
- 自然语言摘要："本周新增 3 个高危账号，已处置 1 个"
- 趋势图表

### 3.2 认知负荷控制

```
系统根据历史处置数据，学习每个运营者的"真实威胁感知阈值"，
自动调整告警呈现优先级。每天只呈现最重要的 N 件事。
```

### 3.3 拓扑可视化增强

- **风险热力叠加**：节点颜色 = 最高风险子节点的颜色
- **时间维度**：账号变化用 diff 标记动画
- **攻击路径模拟**：给定入口点，用红色箭头标注所有可达高权限资产

---

## 四、形式化安全策略

### 4.1 策略即代码

```rego
# OPA / Rego 策略
allow_production_sudo {
    input.user.department == "IT"
    input.user.mfa_enabled == true
    input.user.last_login < "90 days"
}

deny_manual_high_privilege {
    input.account.privilege_level >= "admin"
    input.account.synced_from == "manual"
}
```

### 4.2 合规框架自动验证 ✅

| 合规框架 | 检查项 | 自动化程度 |
|---------|------|---------|
| SOC2 | 特权账号定期审查 | 全自动（ReviewReminder） |
| ISO 27001 | 离职账号及时禁用 | 全自动（生命周期管理） |
| 等保2.0 | 三权分立（管理/审计/运维） | 半自动 |
| PCI-DSS | 共享账号禁用 | 全自动 |

---

## 五、实施路线图

### 第一阶段（✅已完成）：智能报告 + Executive Dashboard
- [x] LLM 报告生成（接入 MiniMax / DeepSeek / Claude / OpenAI，可配置）
- [x] Executive Dashboard（风险分数、合规进度）
- [x] 自然语言搜索
- [x] Dashboard 5分钟智能缓存（加速加载）
- [x] AI 智能分析独立菜单（安全态势摘要 / 自然语言搜索 / 账号风险分析）

### 第二阶段（✅已完成）：知识图谱
- [x] 资产关系知识图谱（SQLite 实现资产关系）
- [x] 风险传播推理引擎
- [x] 攻击路径可视化（横向移动风险热点）
- [x] 高风险自动告警（扫描完成后自动创建 critical/warning 告警）

### 第三阶段（✅已完成）：合规自动化 + 身份融合
- [x] 多合规框架自动验证（SOC2 / ISO 27001 / 等保2.0）
- [x] 账号身份融合：跨系统同一自然人识别
- [x] 账号生命周期管理：活跃 → 休眠 → 离机状态跟踪（可配置阈值）
- [x] PAM / 堡垒机集成（只读对接，支持 CustomAPI / 腾讯云 / 阿里云 / CyberArk）
- [x] 定期账号审查提醒（季度 / 月度 Review）
- [x] Excel 报表导出（审查报告 / 合规报告）
- [x] 账号风险评分（独立账号级风险分）

### 第四阶段（规划中）：横向移动检测
- [ ] 行为分析（基于历史基线）
- [ ] UEBA（用户实体行为分析）
- [ ] 与 SIEM / SOAR 集成

### 第五阶段（规划中）：国际化与扩展
- [ ] 日语、韩语等语言支持（i18n 架构已就绪）
- [ ] 多租户隔离
- [ ] 策略即代码（OPA/Rego）

---

## 六、多语言架构 ✅

基于 i18next + react-i18next，支持任意语言扩展：

```
frontend/src/
  locales/
    zh-CN.json      ← 中文（默认）
    en-US.json      ← 英文
  LanguageSwitcher.tsx  ← 头部语言切换（中文 / English）
```

新增语言只需：
1. 在 `locales/` 添加新语言文件（如 `ja-JP.json`）
2. 在 `i18n.ts` 的 `resources` 中注册
3. 在 `LanguageSwitcher.tsx` 添加语言选项

AI 报告生成语言跟随 UI 当前语言自动切换（zh-CN → 中文报告，en-US → 英文报告）。

---

## 七、商业化版本

| 版本 | 定价 | 目标客户 | 核心卖点 |
|------|------|---------|---------|
| **Team** | 免费/低价 | 10-50人IT团队 | 账号发现与拓扑 |
| **Professional** | ¥999/月 | 中小企业 | AI报告 + 合规 + 身份融合 |
| **Enterprise** | ¥9999+/月 | 大企业/政府 | 知识图谱 + 攻击路径 + 多租户 + UEBA |

### 销售话术

> "你知道吗？一次供应链攻击往往始于一个被遗忘的服务账号。
> AccountScan 让你的每一个账号都有迹可循、有险必知、有变即告。"
