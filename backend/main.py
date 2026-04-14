import os
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env file from backend directory before any other imports
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.middleware import SlowAPIMiddleware

# Must configure logging before other imports that use it
from backend.logging_config import configure_logging, get_trace_id, logger
configure_logging()

from backend.database import init_db, SessionLocal
from backend.auth import seed_default_user
from backend.routers import auth, assets, asset_groups, asset_categories, asset_relationships, credentials, users, scan_jobs, snapshots, schedules, alerts, ai_reports, risk, compliance, identities, lifecycle, pam_integration, review_reminders, export, ueba, policies, knowledge_base, identity_threat, playbooks, nhi
from backend.services import scheduler_service
from backend.middleware.request_context import TraceIdMiddleware
from backend.middleware.security_headers import SecurityHeadersMiddleware
from backend.middleware.body_capture import BodyCaptureMiddleware
from backend.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


def _seed_asset_categories(db):
    """Seed default asset categories if none exist."""
    from backend.models import AssetCategoryDef, SubTypeKind
    if db.query(AssetCategoryDef).count() > 0:
        return
    defaults = [
        ("server",   "服务器",          "Linux / Windows 主机",          "CloudServerOutlined",  SubTypeKind.os),
        ("database", "数据库",           "MySQL / PostgreSQL / Redis 等",  "DatabaseOutlined",      SubTypeKind.database),
        ("network",  "网络设备",         "交换机 / 路由器",               "GlobalOutlined",        SubTypeKind.network),
        ("iot",      "物联网设备",        "摄像头 / 传感器 / 网关等",       "CameraOutlined",        SubTypeKind.iot),
    ]
    for slug, name, desc, icon, sub_kind in defaults:
        db.add(AssetCategoryDef(slug=slug, name=name, description=desc, icon=icon, sub_type_kind=sub_kind))
    db.commit()
    logger.info("seeded-default-asset-categories", count=len(defaults))


def _seed_default_policies(db):
    """Seed default security policies if none exist."""
    from backend.models import SecurityPolicy
    if db.query(SecurityPolicy).count() > 0:
        return
    defaults = [
        {
            "name": "Prohibited Shared Username",
            "description": "Detect shared accounts such as admin, root, test, guest, oracle, etc. These accounts are at high risk of being exploited by attackers.",
            "name_key": "policy.builtin.prohibitedSharedUsername.name",
            "description_key": "policy.builtin.prohibitedSharedUsername.desc",
            "category": "privilege",
            "severity": "high",
            "rego_code": 'deny["Prohibited username: admin/Administrator (shared privileged account)"] {\n  input.account.username contains "admin"\n}',
            "enabled": True,
        },
        {
            "name": "Privileged Account Long-term Inactive",
            "description": "Privileged accounts (is_admin=True) with no login records in 90 days — may be abandoned or compromised.",
            "name_key": "policy.builtin.privilegedInactive.name",
            "description_key": "policy.builtin.privilegedInactive.desc",
            "category": "lifecycle",
            "severity": "high",
            "rego_code": 'deny["Privileged account has not logged in for over 90 days"] {\n  input.account.is_admin == true\n  days_since(input.account.last_login) > 90\n  input.account.last_login != null\n}',
            "enabled": True,
        },
        {
            "name": "NOPASSWD Sudo Permission",
            "description": "Detect NOPASSWD sudo permissions that bypass password verification for privileged operations.",
            "name_key": "policy.builtin.nopasswdSudo.name",
            "description_key": "policy.builtin.nopasswdSudo.desc",
            "category": "privilege",
            "severity": "critical",
            "rego_code": 'deny["NOPASSWD sudo configured — privilege escalation risk"] {\n  input.account.sudo_config != null\n  contains(input.account.sudo_config, "NOPASSWD")\n}',
            "enabled": True,
        },
        {
            "name": "System Account UID Range",
            "description": "Accounts with UID < 1000 are typically system accounts and should not be used by human users.",
            "name_key": "policy.builtin.uidRange.name",
            "description_key": "policy.builtin.uidRange.desc",
            "category": "compliance",
            "severity": "medium",
            "rego_code": 'deny["Human user with UID < 1000 — should use UID >= 1000"] {\n  input.account.uid < 1000\n  input.account.uid > 0\n}',
            "enabled": True,
        },
        {
            "name": "Dormant Account Should Be Disabled",
            "description": "Accounts in dormant status for over 180 days should be disabled or removed.",
            "name_key": "policy.builtin.dormantAccount.name",
            "description_key": "policy.builtin.dormantAccount.desc",
            "category": "lifecycle",
            "severity": "medium",
            "rego_code": 'deny["Dormant account (no login > 180 days) should be disabled"] {\n  input.account.lifecycle_status == "dormant"\n  days_since(input.account.last_login) > 180\n}',
            "enabled": True,
        },
        {
            "name": "Root Account Detection",
            "description": "Linux root account should be disabled if not strictly necessary, as attackers can directly log in as root.",
            "name_key": "policy.builtin.rootAccount.name",
            "description_key": "policy.builtin.rootAccount.desc",
            "category": "privilege",
            "severity": "critical",
            "rego_code": 'deny["Root account detected — should be disabled or renamed"] {\n  lower(input.account.username) == "root"\n}',
            "enabled": True,
        },
    ]
    for p in defaults:
        pol = SecurityPolicy(**p, is_built_in=True)
        db.add(pol)
    db.commit()
    logger.info("seeded-default-policies", count=len(defaults))


def _seed_default_playbooks(db):
    """Seed default remediation playbooks if none exist."""
    from backend.models import ReviewPlaybook
    if db.query(ReviewPlaybook).count() > 0:
        return
    defaults = [
        {
            "name": "严重敏感文件泄露 — 自动禁用",
            "description": "检测到 SSH 私钥 world-readable 或其他严重凭据泄露时，自动禁用该账号并通知归属人",
            "name_key": "playbooks.templateCredLeak.name",
            "description_key": "playbooks.templateCredLeak.desc",
            "trigger_type": "alert",
            "trigger_filter": {"level": "critical"},
            "steps": [
                {"action": "disable_account", "target": "snapshot"},
                {"action": "notify_owner", "target": "identity"},
            ],
            "approval_required": True,
            "enabled": True,
        },
        {
            "name": "NOPASSWD sudo 检测 — 标记复核",
            "description": "检测到账号配置了 NOPASSWD sudo 权限时，标记为高危待复核，并建议撤销",
            "name_key": "playbooks.templateNopasswd.name",
            "description_key": "playbooks.templateNopasswd.desc",
            "trigger_type": "alert",
            "trigger_filter": {"level": "high", "keyword": "nopasswd"},
            "steps": [
                {"action": "flag_review", "target": "snapshot"},
                {"action": "revoke_nopasswd", "target": "snapshot"},
                {"action": "notify_owner", "target": "identity"},
            ],
            "approval_required": True,
            "enabled": True,
        },
        {
            "name": "长期未活跃特权账号 — 自动禁用",
            "description": "检测到离职或长期不活跃账号仍保留特权时，自动禁用并通知管理员",
            "name_key": "playbooks.templateDormant.name",
            "description_key": "playbooks.templateDormant.desc",
            "trigger_type": "alert",
            "trigger_filter": {"level": "high", "keyword": "dormant"},
            "steps": [
                {"action": "disable_account", "target": "snapshot"},
                {"action": "notify_owner", "target": "identity"},
            ],
            "approval_required": True,
            "enabled": False,  # off by default — enable when ready
        },
        {
            "name": "影子账号 — 标记待复核",
            "description": "检测到无归属人的活跃账号（潜在影子账号）时，通知安全团队进行人工复核",
            "name_key": "playbooks.templateShadow.name",
            "description_key": "playbooks.templateShadow.desc",
            "trigger_type": "alert",
            "trigger_filter": {"level": "warning", "keyword": "orphan"},
            "steps": [
                {"action": "flag_review", "target": "snapshot"},
                {"action": "notify_owner", "target": "identity"},
            ],
            "approval_required": False,
            "enabled": True,
        },
        {
            "name": "SSH 密钥复用 — 标记横向移动风险",
            "description": "检测到跨资产 SSH 公钥复用（横向移动路径）时，通知安全团队评估风险",
            "name_key": "playbooks.templateSSHReuse.name",
            "description_key": "playbooks.templateSSHReuse.desc",
            "trigger_type": "alert",
            "trigger_filter": {"level": "warning", "keyword": "ssh"},
            "steps": [
                {"action": "flag_review", "target": "snapshot"},
                {"action": "notify_owner", "target": "identity"},
            ],
            "approval_required": False,
            "enabled": True,
        },
        {
            "name": "新建特权账号 — 标记待复核",
            "description": "检测到新增特权账号（admin/sudo 组）时，通知安全团队确认是否为授权变更",
            "name_key": "playbooks.templateNewPrivilege.name",
            "description_key": "playbooks.templateNewPrivilege.desc",
            "trigger_type": "alert",
            "trigger_filter": {"level": "high", "keyword": "privilege"},
            "steps": [
                {"action": "flag_review", "target": "snapshot"},
            ],
            "approval_required": False,
            "enabled": True,
        },
    ]
    for spec in defaults:
        db.add(ReviewPlaybook(**spec))
    db.commit()
    logger.info("seeded-default-playbooks", count=len(defaults))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("accountscan-starting", version="2.0.0")
    # Startup: init DB + seed default admin + seed default categories + start scheduler
    init_db()
    db = SessionLocal()
    try:
        seed_default_user(db)
        _seed_asset_categories(db)
        _seed_default_policies(db)
        _seed_default_playbooks(db)
    finally:
        db.close()
    scheduler_service.start_scheduler()
    logger.info("accountscan-started")
    yield
    # Shutdown: stop scheduler
    logger.info("accountscan-shutting-down")
    scheduler_service.stop_scheduler()
    logger.info("accountscan-stopped")


app = FastAPI(
    title="AccountSentinel API",
    description="账号安全审计与发现系统",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Rate limit state + handler ────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ── Middleware (applied bottom-to-top = first-to-last in chain) ──
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TraceIdMiddleware)
app.add_middleware(BodyCaptureMiddleware)  # must run before route handlers read body
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ─────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    trace_id = get_trace_id()
    logger.exception(
        "unhandled-exception",
        trace_id=trace_id,
        path=request.url.path,
        method=request.method,
        exc_type=type(exc).__name__,
    )
    # Distinguish known vs unknown exceptions
    if hasattr(exc, "status_code"):
        return JSONResponse(status_code=getattr(exc, "status_code", 500), content={"detail": str(exc)})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "服务器内部错误，请联系管理员", "trace_id": trace_id},
    )


# ── Mount routers ────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(assets.router)
app.include_router(asset_groups.router)
app.include_router(asset_categories.router)
app.include_router(asset_relationships.router)
app.include_router(credentials.router)
app.include_router(users.router)
app.include_router(scan_jobs.router)
app.include_router(snapshots.router)
app.include_router(schedules.router)
app.include_router(alerts.router)
app.include_router(ai_reports.router)
app.include_router(risk.router)
app.include_router(compliance.router)
app.include_router(identities.router)
app.include_router(lifecycle.router)
app.include_router(pam_integration.router)
app.include_router(review_reminders.router)
app.include_router(export.router)
app.include_router(ueba.router)
app.include_router(policies.router)
app.include_router(knowledge_base.router)
app.include_router(identity_threat.router)
app.include_router(playbooks.router)
app.include_router(nhi.router)


# ── Health check (enhanced) ─────────────────────────────────────
@app.get("/health", tags=["系统"])
async def health_check():
    checks = {
        "database": "ok",
        "scheduler": "stopped",
    }
    status_overall = "ok"

    # DB connectivity
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        checks["database"] = f"error: {e}"
        status_overall = "degraded"

    # Scheduler
    from backend.services.scheduler_service import SchedulerService
    if SchedulerService.get_instance().is_running:
        checks["scheduler"] = "running"

    return {
        "status": status_overall,
        "service": "accountscan",
        "version": "2.0.0",
    }


# ── Run with uvicorn ────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
