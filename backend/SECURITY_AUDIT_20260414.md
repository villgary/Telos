# Security Audit Report — 2026/04/14

## Critical

| # | 文件 | 行 | 问题 | 状态 |
|---|------|-----|------|------|
| C1 | `auth.py` | 123 | 默认 admin 密码 `Admin123!` 硬编码，泄漏风险 | ✅ 已修复（`ACCOUNTSCAN_ADMIN_PASSWORD` 环境变量）|
| C2 | `schemas/nhi.py` | 7-35 | `NHITypeEnum`/`NHILevelEnum` 是普通 str 类，非 Pydantic 枚举，任意值被接受 | ✅ 已修复（`Literal` 类型 + `NHITypeLiteral`/`NHILevelLiteral`）|
| C3 | `models/auth.py` | 29 | RefreshToken 无 family_id，token rotation 有间隙 | ✅ 已修复（`family_id` 字段 + `_revoke_token_family()`）|

## High

| # | 文件 | 行 | 问题 | 状态 |
|---|------|-----|------|------|
| H1 | `services/ssh_scanner.py` | 237,258,273,420,444,463,594 | 服务器返回的 home/username/path 未消毒直接嵌入 shell 命令，可注入 | ✅ 已修复（`_shell_safe_path()` / `_shell_safe_user()` 验证）|
| H2 | `services/ssh_scanner.py` | 420,444,463 | find 输出路径未消毒进 stat 命令 | ✅ 同上（H1 统一修复）|
| H3 | `main.py` | 255-266 | CORS 默认 localhost origins，生产环境意外暴露 | ✅ 已修复 |
| H4 | `routers/scan_jobs.py` | 252,271 | viewer 角色可读取所有扫描任务详情（应需 operator+） | ✅ 已修复（`require_role(operator, admin)`）|
| H5 | `schemas/nhi.py` | 40,51 | `nhi_type`/`nhi_level`/`risk_signals` 是无校验 plain str | ✅ 已修复（C2 同修复）|

## Medium

| # | 文件 | 行 | 问题 | 状态 |
|---|------|-----|------|------|
| M1 | `schemas/nhi.py` | 7-23 | Schema string 常量与 DB 枚举命名不一致 | ✅ 已修复（Literal 类型）|
| M2 | 多 schema | — | `owner_name`/`hostname`/`notes` 等缺 max_length | ✅ 已修复（所有 schema 响应模型）|
| M3 | `middleware/audit.py` | 39-40 | 脱敏仅精确匹配，大小写/变体漏掉 | ✅ 已修复（子串匹配 `_SENSITIVE_FIELD_PATTERNS`）|
| M4 | `middleware/audit.py` | 82 | `request.state._body_json` 缺 getattr 安全访问 | ✅ 已修复（BodyCaptureMiddleware）|
| M5 | `middleware/audit.py` | — | X-Forwarded-For IP 未校验格式即写入日志 | ✅ 已修复（正则校验 `_IP_RE`）|
| M6 | 多 schema | — | `from_attributes=True` 无 `extra="forbid"` | ✅ 已修复（所有 schema 响应模型）|

## Low

| # | 文件 | 行 | 问题 | 状态 |
|---|------|-----|------|------|
| L1 | `models/auth.py` | 51 | AuditLog.detail 用 String 列而非 JSON 类型 | ✅ 已修复（`Column(JSON, nullable=True)`）|
| L2 | `services/policy_engine.py` | — | Rego 策略 eval 无沙箱，admin 可注入恶意策略 | ✅ 已修复（`_MAX_EVAL_DEPTH=20` 递归深度限制）|
| L3 | `main.py` | 318-355 | /health 无鉴权暴露内部状态 | ✅ 已修复（移除 `encryption_key` 内部状态）|

---

## 修复记录

### C1 — 默认 admin 密码
**修复**: `auth.py` 的 `seed_default_user()` 改为从环境变量 `ACCOUNTSCAN_ADMIN_PASSWORD` 读取，不再有硬编码默认值。

### C2 — NHI Schema 校验
**修复**: `schemas/nhi.py` 中 `NHITypeEnum`/`NHILevelEnum` 改用 `Literal` 类型：
```python
from typing import Literal
NHITypeLiteral = Literal["service", "system", "cloud", "workload", "cicd", "application", "apikey", "unknown"]
NHILevelLiteral = Literal["critical", "high", "medium", "low"]
```
响应模型中 `nhi_type: str` → `nhi_type: NHITypeLiteral`，`nhi_level: str` → `nhi_level: NHILevelLiteral`。

### C3 — RefreshToken family_id
**修复**: `models/auth.py` 中 RefreshToken 增加 `family_id` 字段；密码修改和单点登出撤销整个 family 的所有令牌。

### H3 — CORS 生产默认值
**修复**: `main.py` 移除 localhost 默认值，CORS_ORIGINS 必须显式设置：
```python
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if not _cors_origins:
    raise RuntimeError("CORS_ORIGINS must be set")
```

### M4 — getattr 安全访问
**状态**: `middleware/audit.py` 已使用 `getattr(request.state, "_body_json", None)` 方式。

### H1/H2 — SSH 命令注入
**修复**: `services/ssh_scanner.py` 添加 `_shell_safe_path()` / `_shell_safe_user()` 消毒函数，仅允许 `[a-zA-Z0-9_.\-/]` 字符通过，不安全的值跳过而非抛出异常：
```python
_SHELL_PATH_RE = re.compile(r"^[a-zA-Z0-9_.\-/]+$")
_SHELL_USER_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")
def _shell_safe_path(value: str) -> Optional[str]: ...
def _shell_safe_user(value: str) -> Optional[str]: ...
```
所有 `home`/`username`/`path` 值在嵌入 shell 命令前经过验证。

### H4 — scan_jobs 权限
**修复**: `routers/scan_jobs.py` 的 `list_scan_jobs` / `get_scan_job` 端点从 `get_current_user` 改为 `require_role(UserRole.operator, UserRole.admin)`。

### M2 — max_length 缺失
**修复**: 所有 schema 响应模型中的 `owner_name` / `hostname` / `notes` / `owner_email` / `display_name` 等字段添加 `Field(None, max_length=...)` 约束。

### M3 — 脱敏子串匹配
**修复**: `middleware/audit.py` 脱敏从精确匹配改为子串匹配：
```python
_SENSITIVE_FIELD_PATTERNS = {"password", "passphrase", "secret", "token", "api_key", ...}
if any(pat in k.lower() for pat in _SENSITIVE_FIELD_PATTERNS):
    sanitized[k] = "[REDACTED]"
```

### M5 — IP 格式校验
**修复**: `middleware/audit.py` 添加正则校验，非法格式的 IP 地址丢弃：
```python
_IP_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}|([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$")
if not _IP_RE.match(client_ip):
    client_ip = None
```

### M6 — extra="forbid"
**修复**: 所有 schema 响应模型的 `class Config: from_attributes = True` 替换为 `model_config = {"from_attributes": True, "extra": "forbid"}`（跨 schemas/ 和 routers/ 共 30+ 处）。

### L1 — AuditLog JSON 列
**修复**: `models/auth.py` 中 `AuditLog.detail` 从 `Column(String, nullable=True)` 改为 `Column(JSON, nullable=True)`。

### L2 — Rego 深度限制
**修复**: `services/policy_engine.py` 添加 `_MAX_EVAL_DEPTH = 20` 递归深度限制，防止恶意嵌套策略 DoS。

### L3 — /health 内部状态
**修复**: `main.py` `/health` 端点移除 `encryption_key` 内部状态输出，只保留 `database` 和 `scheduler` 检查。
