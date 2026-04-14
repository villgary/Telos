# AccountScan — 账号安全审计与发现系统

基于 PRD V1.1 Phase 1 (MVP) 原型实现。

## 功能特性（Phase 1 MVP）

- **资产管理**：Linux 资产录入、连接测试
- **SSH 扫描**：通过 Paramiko 连接目标主机，采集 `/etc/passwd`、`/etc/shadow`、sudoers、authorized_keys、lastlog
- **快照存储**：每次扫描结果持久化为只读快照
- **差异比对**：新增账号 / 消失账号 / 权限爬升（`is_admin` False→True）检测
- **凭据安全**：密码和 SSH 私钥 AES-256-GCM 加密存储
- **JWT 认证**：无状态 API 认证，支持 `admin / operator / viewer` 三角色
- **审计日志**：全量操作记录

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + SQLite |
| 前端 | React 18 + Ant Design 5 + Vite |
| SSH | Paramiko |
| 加密 | cryptography (AES-256-GCM) |
| 认证 | python-jose (JWT) + bcrypt (直接调用) |

## 环境要求

- Python 3.10+
- Node.js 18+
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

# 写入 .env（可选，也可直接设置环境变量）
echo "ACCOUNTSCAN_MASTER_KEY=<生成的密钥>" > .env
echo "ACCOUNTSCAN_JWT_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env
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

## 快速操作流程

1. **创建凭据**：`凭据管理` → `添加凭据`（输入用户名+密码 or SSH 私钥）
2. **添加资产**：`资产管理` → `添加资产`（输入 IP + 选择刚创建的凭据）
3. **测试连接**：`测试` 按钮 → 查看连接状态
4. **触发扫描**：`扫描` 按钮 → 查看发现的账号列表
5. **差异比对**：`差异比对` → 选择同一资产的两次扫描批次 → 查看新增/消失/权限爬升

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

## 数据库

SQLite（`backend/accountscan.db`），由 SQLAlchemy ORM 自动创建，无需手动初始化。

## 角色权限说明

| 角色 | 资产管理 | 发起扫描 | 凭据管理 | 查看快照 |
|------|---------|---------|---------|---------|
| admin | ✅ | ✅ | ✅ | ✅ |
| operator | ✅ | ✅ | ❌ | ✅ |
| viewer | ❌ | ❌ | ❌ | ✅ |

## 项目结构

```
accountscan/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── database.py           # SQLite + SQLAlchemy
│   ├── models.py             # ORM 模型（7 张表）
│   ├── schemas.py            # Pydantic 模型
│   ├── auth.py               # JWT 认证
│   ├── encryption.py         # AES-256-GCM 加密
│   ├── routers/              # API 路由
│   │   ├── auth.py
│   │   ├── assets.py
│   │   ├── credentials.py
│   │   ├── scan_jobs.py
│   │   └── snapshots.py
│   └── services/
│       ├── ssh_scanner.py    # Paramiko SSH 扫描
│       └── diff_engine.py    # 差异比对引擎
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Assets.tsx
│   │   │   ├── ScanJobs.tsx
│   │   │   ├── DiffView.tsx
│   │   │   └── Credentials.tsx
│   │   └── api/client.ts
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 后续路线图

- **Phase 2**：Windows WinRM 扫描插件 + 邮件/钉钉告警通知
- **Phase 3**：数据库（MySQL/Oracle）/ 网络设备（Cisco/Huawei）账号插件
- **Phase 4**：日志溯源（auth.log / Windows Security Event Log）

## 安全说明

- AES-256-GCM 加密密钥**必须**通过环境变量注入，不要硬编码
- 生产环境建议使用 AWS KMS 或 HashiCorp Vault 管理密钥
- `raw_info` 中的密码哈希已脱敏，不会上报
- SSH 私钥内容全程在内存中处理，不写入日志
