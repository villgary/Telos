# Telos — 身份威胁检测与合规平台

Telos 是智能化身份威胁检测与合规（ITDR）平台，通过自动化账号扫描、MITRE ATT&CK 威胁映射和 AI 语义分析，帮助组织发现影子账号、检测凭据滥用和横向移动风险。

## 功能特性

### 核心能力
- **资产管理** — Linux/Windows/数据库/网络设备账号扫描，支持 SSH/WMI/API 等多种协议
- **账号快照与比对** — 每次扫描结果持久化为只读快照，支持新增/消失/权限爬升检测
- **身份融合** — 跨系统同一自然人识别，构建完整身份图谱
- **NHI（非人身份）管理** — 服务账号、服务密钥的全生命周期管理
- **AI Agent 管理** — 发现与治理 LLM 驱动的 AI Agent（LangChain / AutoGen / CrewAI / Claude Code 等），含 API Key 指纹、工具能力识别与风险评分
- **风险评分** — 基于登录频率、特权范围、身份融合的账号风险评分
- **合规自动化** — SOC2 / ISO 27001 / 等保2.0 / PCI-DSS 多框架自动验证
- **ATT&CK 覆盖率分析** — 账号安全威胁映射到 MITRE ATT&CK 框架
- **UEBA** — 用户实体行为分析，检测异常登录和横向移动
- **Playbooks** — 可配置自动处置剧本（禁用账号、封禁 IP 等）
- **知识库** — RAG 增强的账号安全问答系统
- **AI 报告生成** — 自然语言威胁报告，支持中文/英文自动切换
- **自然语言搜索** — LLM 解析查询，模糊搜索资产和账号

### 技术特性
- **JWT 认证** — 无状态 API 认证，支持 `admin / operator / viewer` 三角色
- **AES-256-GCM 加密** — 密码和 SSH 私钥加密存储
- **PostgreSQL** — 关系型数据存储，支持 JSONB 扩展
- **多语言 i18n** — 中文（zh-CN）/ 英文（en-US）界面
- **Excel 报表导出** — 审查报告 / 合规报告导出

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + PostgreSQL |
| 前端 | React 18 + Ant Design 5 + Vite + TypeScript |
| 扫描 | Paramiko (SSH), WinRM (Windows) |
| 认证 | python-jose (JWT) + bcrypt |
| 加密 | cryptography (AES-256-GCM) |
| AI 集成 | MiniMax / DeepSeek / Claude / OpenAI (可配置) |

## 环境要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- npm 或 yarn

## 快速启动

### 1. 克隆并安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 生成加密密钥（32字节 hex）
python -c "import secrets; print(secrets.token_hex(32))"

# 写入 .env
cp .env.example .env
# 编辑 .env 填入必要的环境变量
```

**重要**：首次启动会自动在数据库中创建默认管理员账号：

```
用户名：admin
密码：admin123
角色：admin
```

### 3. 启动后端

```bash
cd backend
uvicorn main:app --reload --port 8000
```

- API 文档：`http://localhost:8000/docs`（Swagger UI）
- ReDoc：`http://localhost:8000/redoc`

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`，使用 `admin / admin123` 登录。

## 项目结构

```
telos/
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── database.py             # PostgreSQL + SQLAlchemy
│   ├── models.py               # ORM 模型
│   ├── schemas.py              # Pydantic 模型
│   ├── routers/                # API 路由
│   │   ├── auth.py
│   │   ├── assets.py
│   │   ├── credentials.py
│   │   ├── scan_jobs.py
│   │   ├── snapshots.py
│   │   ├── alerts.py
│   │   ├── compliance.py
│   │   ├── policies.py
│   │   ├── lifecycle.py
│   │   ├── nhi.py
│   │   ├── ai_agents.py
│   │   ├── identities.py
│   │   ├── ueba.py
│   │   ├── risk.py
│   │   ├── playbooks.py
│   │   ├── knowledge_base.py
│   │   └── ...
│   └── services/
│       ├── ssh_scanner.py
│       ├── ai_agent_scanner.py
│       ├── diff_engine.py
│       ├── risk_scorer.py
│       └── ...
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Assets.tsx
│   │   │   ├── Credentials.tsx
│   │   │   ├── SubTypes.tsx
│   │   │   ├── IdentityThreatAnalysis.tsx
│   │   │   ├── AIAgentsPage.tsx
│   │   │   ├── AIAgentDetailPage.tsx
│   │   │   ├── BehaviorAnalytics.tsx
│   │   │   ├── Playbooks.tsx
│   │   │   ├── KnowledgeBase.tsx
│   │   │   └── ...
│   │   ├── components/
│   │   │   └── AppLayout.tsx
│   │   └── locales/
│   │       ├── en-US.json
│   │       └── zh-CN.json
│   └── package.json
└── docs/
    ├── roadmap.md
    └── ...
```

## API 认证

所有 `/api/v1/*` 接口（除 `/api/v1/auth/login`）均需要 JWT Bearer Token。

```bash
# 获取 token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"

# 使用 token 访问受保护接口
curl http://localhost:8000/api/v1/assets \
  -H "Authorization: Bearer <token>"
```

## 角色权限说明

| 角色 | 资产管理 | 发起扫描 | 凭据管理 | 查看快照 |
|------|---------|---------|---------|---------|
| admin | ✅ | ✅ | ✅ | ✅ |
| operator | ✅ | ✅ | ❌ | ✅ |
| viewer | ❌ | ❌ | ❌ | ✅ |

## 安全说明

- AES-256-GCM 加密密钥**必须**通过环境变量注入，不要硬编码
- 生产环境建议使用 AWS KMS 或 HashiCorp Vault 管理密钥
- `raw_info` 中的密码哈希已脱敏，不会上报
- SSH 私钥内容全程在内存中处理，不写入日志
