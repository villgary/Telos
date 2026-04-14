"""
AI Reports Router — LLM config management, report generation, executive dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import func
import re

from backend.database import get_db
from backend import models, schemas, auth, encryption

router = APIRouter(prefix="/api/v1/ai", tags=["AI 报告"])


# ─── LLM Config ────────────────────────────────────────────────────────────────

@router.get("/config", response_model=schemas.LLMConfigResponse)
async def get_llm_config(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    cfg = db.query(models.LLMConfig).first()
    if not cfg:
        return schemas.LLMConfigResponse(
            id=0,
            provider=models.LLMProvider.openai,
            api_key_set=False,
            base_url=None,
            model="gpt-4o-mini",
            enabled=False,
            created_at=datetime.now(timezone.utc),
        )
    return schemas.LLMConfigResponse(
        id=cfg.id,
        provider=cfg.provider,
        api_key_set=cfg.api_key_enc is not None,
        base_url=cfg.base_url,
        model=cfg.model,
        enabled=cfg.enabled,
        created_at=cfg.created_at,
    )


@router.put("/config", response_model=schemas.LLMConfigResponse)
async def update_llm_config(
    cfg_in: schemas.LLMConfigUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    cfg = db.query(models.LLMConfig).first()
    if not cfg:
        cfg = models.LLMConfig(
            provider=models.LLMProvider.minimax,
            base_url="https://api.minimaxi.com/v1",
            model=cfg_in.model or "MiniMax-M2.7-highspeed",
            enabled=cfg_in.enabled or False,
        )
        db.add(cfg)
    else:
        # Always default to minimax provider with correct endpoint
        cfg.provider = models.LLMProvider.minimax
        if cfg_in.base_url is not None:
            cfg.base_url = cfg_in.base_url or "https://api.minimaxi.com/v1"
        else:
            cfg.base_url = cfg.base_url or "https://api.minimaxi.com/v1"
        if cfg_in.model is not None:
            cfg.model = cfg_in.model
        if cfg_in.enabled is not None:
            cfg.enabled = cfg_in.enabled

    if cfg_in.api_key:
        cfg.api_key_enc = encryption.encrypt(cfg_in.api_key)

    db.commit()
    db.refresh(cfg)
    return schemas.LLMConfigResponse(
        id=cfg.id,
        provider=cfg.provider,
        api_key_set=cfg.api_key_enc is not None,
        base_url=cfg.base_url,
        model=cfg.model,
        enabled=cfg.enabled,
        created_at=cfg.created_at,
    )


# ─── Executive Dashboard ─────────────────────────────────────────────────────

def _compute_risk_score(db: Session) -> tuple[int, str, dict]:
    """
    Compute overall risk score (0-100) and supporting metrics.
    """
    total_assets = db.query(models.Asset).count()

    # Count accounts per asset (latest snapshots)
    job_ids = [a.last_scan_job_id for a in db.query(models.Asset.last_scan_job_id).all() if a.last_scan_job_id]
    total_accounts = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.job_id.in_(job_ids)
    ).count() if job_ids else 0

    admin_accounts = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.job_id.in_(job_ids),
        models.AccountSnapshot.is_admin == True,
    ).count() if job_ids else 0

    # Unlogined admin accounts (90+ days)
    cutoff = datetime.utcnow() - timedelta(days=90)
    unlogin_admins = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.job_id.in_(job_ids),
        models.AccountSnapshot.is_admin == True,
    ).all()
    def _naive(dt):
        """Convert a Postgres timestamp-with-tz to naive UTC for comparison."""
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None) - dt.utcoffset()
        return dt
    unlogin_admins = sum(
        1 for a in unlogin_admins
        if a.last_login is None or _naive(a.last_login) < cutoff
    )

    # Dormant accounts (never logged in + not service accounts)
    dormant = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.job_id.in_(job_ids),
        models.AccountSnapshot.last_login == None,
    ).count()

    # Offline / auth_failed assets
    offline_count = db.query(models.Asset).filter(
        models.Asset.status == models.AssetStatus.offline
    ).count()
    auth_fail_count = db.query(models.Asset).filter(
        models.Asset.status == models.AssetStatus.auth_failed
    ).count()

    # Risk formula
    score = 0
    score += min(admin_accounts * 3, 25)          # admin accounts
    score += min(unlogin_admins * 5, 20)          # unlogined admins (high risk)
    score += min(dormant * 1, 10)                 # dormant
    score += min(offline_count * 2, 10)          # offline assets
    score += min(auth_fail_count * 3, 15)        # auth failures
    score += min((total_assets - len(job_ids)) * 2, 10)  # un-scanned assets
    score = min(score, 100)

    # Risk level
    if score < 20:
        level = "low"
    elif score < 45:
        level = "medium"
    elif score < 70:
        level = "high"
    else:
        level = "critical"

    # 7d trend: count account changes in last 7 days
    recent_cutoff = datetime.utcnow() - timedelta(days=7)
    new_accounts_7d = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.job_id.in_(job_ids),
        models.AccountSnapshot.snapshot_time >= recent_cutoff,
    ).count() if job_ids else 0

    trends = {
        "period": "7d",
        "total_accounts": total_accounts,
        "new_accounts_7d": new_accounts_7d,
        "admin_accounts": admin_accounts,
        "unlogin_admin_accounts": unlogin_admins,
        "offline_assets": offline_count,
        "auth_failed_assets": auth_fail_count,
    }

    return score, level, trends


# ─── Language-aware prompt builders ──────────────────────────────────────────

def _get_dashboard_system_prompt(lang: str) -> str:
    if lang == "en-US":
        return """You are a senior cybersecurity analyst generating an account security posture summary for an enterprise Security Operations Center (CSOC).
Output requirements:
1. Use English
2. Keep between 200-300 words
3. Structure: Current Status → Risk Points → Recommendations (up to 3)
4. Only use the provided data, do not fabricate information
5. Professional but accessible language, targeted at IT managers
6. Markdown format is supported"""
    return """你是一名资深网络安全分析师，为企业安全运营中心（CSOC）生成账号安全态势摘要。
输出要求：
1. 使用中文
2. 总字数控制在 200-300 字
3. 结构清晰：现状 → 风险点 → 处置建议（3条以内）
4. 仅基于提供的数据，不要编造数据
5. 用专业但易懂的语言，面向 IT 管理者
6. 报告格式支持 Markdown"""


def _build_dashboard_user_prompt(metrics: schemas.ExecutiveMetrics, lang: str) -> str:
    trends = metrics.trends
    risk_label = {"low": "低", "medium": "中", "high": "高", "critical": "极高"}.get(metrics.risk_level, metrics.risk_level)
    if lang == "en-US":
        return f"""## Current Account Security Posture Data

- Risk Score: {metrics.risk_score}/100 ({metrics.risk_level})
- Total Assets: {metrics.total_assets}
- Total Accounts: {metrics.total_accounts}
- Admin Accounts: {metrics.high_risk_accounts}
- Unlogged-in Admin Accounts (90d+): {metrics.unlogin_admin_accounts}
- Compliance Coverage: {metrics.compliance_ready}%
- Offline Assets: {trends.get('offline_assets', 0)}
- Auth-failed Assets: {trends.get('auth_failed_assets', 0)}
- New Accounts (past 7 days): {trends.get('new_accounts_7d', 0)}

Please generate a concise security posture report."""
    return f"""## 当前账号安全态势数据

- 风险评分：{metrics.risk_score}/100（{risk_label}级）
- 资产总数：{metrics.total_assets}
- 账号总数：{metrics.total_accounts}
- 管理员账号数：{metrics.high_risk_accounts}
- 未登录管理员账号（90天+）：{metrics.unlogin_admin_accounts}
- 合规覆盖率：{metrics.compliance_ready}%
- 离线资产数：{trends.get('offline_assets', 0)}
- 认证失败资产数：{trends.get('auth_failed_assets', 0)}
- 过去7天新增账号：{trends.get('new_accounts_7d', 0)}

请生成一份简明的安全态势报告。"""


def _get_report_system_prompt(report_type: str, lang: str) -> str:
    if lang == "en-US":
        base = """You are a senior cybersecurity analyst generating account security threat analysis reports for IT security teams.
Output requirements:
- Use English
- Markdown format supported
- Structure: Overview → Detailed Analysis → Risk Assessment → Recommendations
"""
        if report_type == "compliance":
            return base + "\nFocus on compliance gaps and improvement recommendations, aligned with SOC2 / ISO27001."
        if report_type == "account_risk":
            return base + "\nFocus on individual account-level risk: categorize each account as critical/high/medium/low, explain WHY each account has that risk level, and provide specific remediation steps for each account."
        return base + "\nFocus on account risks, privilege issues, and potential threat paths."
    base = """你是一名资深网络安全分析师，为 IT 安全团队生成账号安全威胁分析报告。
输出要求：
- 使用中文
- 支持 Markdown 格式
- 结构：概述 → 详细分析 → 风险评估 → 处置建议
"""
    if report_type == "compliance":
        return base + "\n重点分析合规差距和改进建议，对标 SOC2 / ISO27001。"
    if report_type == "account_risk":
        return base + "\n重点分析单个账号的风险：对每个账号给出风险等级（严重/高/中/低），说明原因，并给出具体处置建议。"
    return base + "\n重点分析账号风险、权限问题、潜在威胁路径。"


def _build_account_risk_context(db: Session, lang: str = "zh-CN") -> str:
    """Build context for all accounts across all assets for risk analysis."""
    def _naive(dt):
        """Strip timezone info from a datetime, returning a naive local-equivalent value."""
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None) - dt.utcoffset()
        return dt
    cutoff_90d = datetime.utcnow() - timedelta(days=90)
    cutoff_30d = datetime.utcnow() - timedelta(days=30)

    # Get all latest snapshots per asset
    assets = db.query(models.Asset).filter(
        models.Asset.last_scan_job_id.isnot(None)
    ).all()

    all_lines = []
    total_accounts = 0
    high_risk_accounts = []

    for asset in assets:
        snaps = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.job_id == asset.last_scan_job_id
        ).all()
        if not snaps:
            continue

        for s in snaps:
            total_accounts += 1
            risk_flags = []

            if s.is_admin:
                risk_flags.append("特权账号")
            if not s.last_login:
                risk_flags.append("从未登录")
            elif _naive(s.last_login) < cutoff_90d:
                risk_flags.append(f"超过90天未登录({(datetime.utcnow() - _naive(s.last_login)).days}天)")
            elif _naive(s.last_login) < cutoff_30d:
                risk_flags.append(f"超过30天未登录({(datetime.utcnow() - _naive(s.last_login)).days}天)")

            if s.account_status in ("dormant", "departed"):
                risk_flags.append(f"账号状态: {s.account_status}")

            sudo = s.sudo_config or {}
            if sudo.get("nopasswd_sudo"):
                risk_flags.append("免密sudo权限")
            if any(r.get("all_commands") and r.get("nopasswd") for r in sudo.get("sudo_rules", [])):
                risk_flags.append("NOPASSWD ALL权限")

            if risk_flags:
                if lang == "en-US":
                    lines = [
                        f"- **{s.username}** (Asset: {asset.ip}, UID: {s.uid_sid})",
                        f"  Status: {s.account_status or 'unknown'}, Last Login: {s.last_login or 'Never'}",
                        f"  Risk Factors: {', '.join(risk_flags)}",
                    ]
                else:
                    lines = [
                        f"- **{s.username}**（资产: {asset.ip}，UID: {s.uid_sid}）",
                        f"  状态: {s.account_status or '未知'}，上次登录: {s.last_login or '从未登录'}",
                        f"  风险因子: {', '.join(risk_flags)}",
                    ]
                all_lines.extend(lines)

    if lang == "en-US":
        header = f"""## Account Risk Overview

Total scanned accounts: {total_accounts}
High-risk accounts found: {len(all_lines) // 3}

### High-Risk Account List
"""
    else:
        header = f"""## 账号风险总览

扫描账号总数：{total_accounts}
高风险账号数量：{len(all_lines) // 3}

### 高风险账号清单
"""

    if not all_lines:
        if lang == "en-US":
            return header + "No high-risk accounts found."
        return header + "未发现高风险账号。"
    return header + "\n".join(all_lines)


def _build_asset_context(
    asset: models.Asset,
    snaps: list[models.AccountSnapshot],
    job: models.ScanJob,
    lang: str = "zh-CN",
) -> str:
    if lang == "en-US":
        lines = [
            f"## Asset: {asset.asset_code} ({asset.ip})",
            f"  Category: {asset.asset_category.value}",
            f"  Status: {asset.status.value}",
            f"  Last Scan: {asset.last_scan_at}",
            f"  Scan Task: {'Success' if job.status.value == 'success' else job.status.value}",
            "",
            f"### Account List ({len(snaps)} total)",
        ]
        for s in snaps:
            lines.append(
                f"  - {s.username} | UID:{s.uid_sid} | "
                f"Admin:{'Yes' if s.is_admin else 'No'} | "
                f"Status:{s.account_status or 'Unknown'} | "
                f"Last Login:{s.last_login or 'Never'}"
            )
            if s.is_admin and not s.last_login:
                lines.append(f"    WARNING: Admin account never logged in")
            sudo = s.sudo_config
            if sudo:
                if sudo.get("nopasswd_sudo"):
                    lines.append(f"    WARNING: Passwordless sudo permission found")
                rules = sudo.get("sudo_rules", [])
                for r in rules:
                    if r.get("all_commands") and r.get("nopasswd"):
                        lines.append(f"    WARNING: {s.username} has NOPASSWD ALL permission")
    else:
        lines = [
            f"## 资产：{asset.asset_code} ({asset.ip})",
            f"  类别：{asset.asset_category.value}",
            f"  状态：{asset.status.value}",
            f"  最后扫描：{asset.last_scan_at}",
            f"  扫描任务：{'成功' if job.status.value == 'success' else job.status.value}",
            "",
            f"### 账号列表（共 {len(snaps)} 个）",
        ]
        for s in snaps:
            lines.append(
                f"  - {s.username} | UID:{s.uid_sid} | "
                f"Admin:{'是' if s.is_admin else '否'} | "
                f"状态:{s.account_status or '未知'} | "
                f"最后登录:{s.last_login or '从未登录'}"
            )
            if s.is_admin and not s.last_login:
                lines.append(f"    高危：admin 账号从未登录")
            sudo = s.sudo_config
            if sudo:
                if sudo.get("nopasswd_sudo"):
                    lines.append(f"    高危：有无密码 sudo 权限")
                rules = sudo.get("sudo_rules", [])
                for r in rules:
                    if r.get("all_commands") and r.get("nopasswd"):
                        lines.append(f"    高危：{s.username} 有 NOPASSWD ALL 权限")

    # Credential findings from raw_info
    cred_findings: list = []
    for s in snaps:
        raw = s.raw_info or {}
        cf = raw.get("credential_findings") or []
        cred_findings.extend(cf)

    if cred_findings:
        if lang == "en-US":
            lines.append("\n### Credential File Risks")
            for f in cred_findings:
                lines.append(f"  [{f.get('risk', '?')}] {f.get('path', '?')}: {f.get('warning', '')}")
        else:
            lines.append("\n### 凭据文件风险")
            for f in cred_findings:
                lines.append(f"  [{f.get('risk', '?')}] {f.get('path', '?')}: {f.get('warning', '')}")

    return "\n".join(lines)


def _build_job_context(job: models.ScanJob, snaps: list[models.AccountSnapshot], lang: str = "zh-CN") -> str:
    if lang == "en-US":
        return f"""
## Scan Task #{job.id}
  Trigger: {job.trigger_type.value}
  Status: {job.status.value}
  Successful Accounts: {job.success_count}
  Failed Accounts: {job.failed_count}
  Error: {job.error_message or 'None'}
"""
    return f"""
## 扫描任务 #{job.id}
  触发方式：{job.trigger_type.value}
  状态：{job.status.value}
  成功账号：{job.success_count}
  失败账号：{job.failed_count}
  错误信息：{job.error_message or '无'}
"""


# ─── Executive Dashboard Endpoint ─────────────────────────────────────────────

# In-memory cache for dashboard metrics (5-minute TTL)
_dashboard_cache: dict[str, tuple[float, schemas.ExecutiveMetrics]] = {}  # key: "lang|user_id"


def _get_cached_dashboard(key: str, ttl: float = 300) -> schemas.ExecutiveMetrics | None:
    if key in _dashboard_cache:
        ts, metrics = _dashboard_cache[key]
        if (datetime.now(timezone.utc).timestamp() - ts) < ttl:
            return metrics
    return None


def _set_cached_dashboard(key: str, metrics: schemas.ExecutiveMetrics) -> None:
    _dashboard_cache[key] = (datetime.now(timezone.utc).timestamp(), metrics)


@router.get("/dashboard", response_model=schemas.ExecutiveMetrics)
async def get_executive_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Executive dashboard metrics: risk score, account counts, compliance, trends.
    """
    # Detect language from Accept-Language header, fallback to zh-CN
    accept_lang = request.headers.get("accept-language", "zh-CN")
    lang = "en-US" if accept_lang.startswith("en") else "zh-CN"

    # Try cache first (5-minute TTL)
    cache_key = f"{lang}|{user.id}"
    cached = _get_cached_dashboard(cache_key)
    if cached:
        return cached

    risk_score, risk_level, trends = _compute_risk_score(db)

    total_assets = db.query(models.Asset).count()
    total_accounts = trends.get("total_accounts", 0)

    # Compliance: % of assets with successful scan (online) + no auth failures
    if total_assets > 0:
        online = db.query(models.Asset).filter(
            models.Asset.status == models.AssetStatus.online
        ).count()
        compliance = round(online / total_assets * 100)
    else:
        compliance = 0

    metrics = schemas.ExecutiveMetrics(
        risk_score=risk_score,
        risk_level=risk_level,
        total_assets=total_assets,
        total_accounts=total_accounts,
        high_risk_accounts=trends.get("admin_accounts", 0),
        dormant_accounts=trends.get("unlogin_admin_accounts", 0),
        unlogin_admin_accounts=trends.get("unlogin_admin_accounts", 0),
        compliance_ready=compliance,
        trends=trends,
        ai_summary=None,  # filled by LLM if configured
    )

    # Fire-and-forget: LLM summary runs in background, dashboard returns immediately.
    # Load any previously cached AI summary so the UI can show it without blocking.
    ai_cache_key = f"ai_summary|{lang}|{user.id}"
    cached_ai = _get_cached_dashboard(ai_cache_key, ttl=600)  # 10-min TTL
    if cached_ai and cached_ai.ai_summary:
        metrics.ai_summary = cached_ai.ai_summary

    llm_cfg = db.query(models.LLMConfig).filter(models.LLMConfig.enabled == True).first()
    if llm_cfg and llm_cfg.api_key_enc:
        import threading

        def _llm_call():
            try:
                from backend.services import llm_service
                system_prompt = _get_dashboard_system_prompt(lang)
                user_prompt = _build_dashboard_user_prompt(metrics, lang)
                summary = llm_service.generate_report(
                    provider=llm_cfg.provider.value,
                    api_key_enc=llm_cfg.api_key_enc,
                    base_url=llm_cfg.base_url,
                    model=llm_cfg.model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                # Cache AI summary separately (long TTL, refreshed each call)
                metrics.ai_summary = summary
                _set_cached_dashboard(ai_cache_key, metrics)
            except Exception:
                pass  # silently fail — dashboard already returned without LLM block

        t = threading.Thread(target=_llm_call, daemon=True)
        t.start()
        # Do NOT join — fire and forget, dashboard returns immediately

    # Cache the result
    _set_cached_dashboard(cache_key, metrics)
    return metrics


# ─── AI Report Generation ────────────────────────────────────────────────────

@router.post("/report", response_model=schemas.AIReportResponse)
async def generate_ai_report(
    req: schemas.AIReportRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Generate an AI-powered threat analysis report for a specific asset or scan job.
    Accepts optional `lang` field: "zh-CN" (default) or "en-US".
    """
    lang = req.lang or "zh-CN"
    err_not_configured_zh = "AI 未配置。请管理员在设置中配置 LLM API。"
    err_not_configured_en = "AI not configured. Please ask your administrator to set up the LLM API."

    llm_cfg = db.query(models.LLMConfig).filter(
        models.LLMConfig.enabled == True,
        models.LLMConfig.api_key_enc.isnot(None),
    ).first()
    if not llm_cfg:
        return schemas.AIReportResponse(
            success=False,
            report=None,
            error=err_not_configured_en if lang == "en-US" else err_not_configured_zh,
        )

    # Gather context
    context = ""
    asset = None

    if req.asset_id:
        asset = db.query(models.Asset).filter(models.Asset.id == req.asset_id).first()
        if not asset:
            return schemas.AIReportResponse(
                success=False, report=None,
                error="Asset not found" if lang == "en-US" else "资产不存在"
            )

    if req.scan_job_id:
        job = db.query(models.ScanJob).filter(models.ScanJob.id == req.scan_job_id).first()
        if job:
            if not asset:
                asset = job.asset
            snaps = db.query(models.AccountSnapshot).filter(
                models.AccountSnapshot.job_id == req.scan_job_id
            ).all()
            context += _build_job_context(job, snaps, lang)

    if asset:
        # Get latest snapshots
        latest_job_id = asset.last_scan_job_id
        if latest_job_id and (not req.scan_job_id):
            latest_job = db.query(models.ScanJob).filter(models.ScanJob.id == latest_job_id).first()
            latest_snaps = db.query(models.AccountSnapshot).filter(
                models.AccountSnapshot.job_id == latest_job_id
            ).all()
            context += _build_asset_context(asset, latest_snaps, latest_job, lang)

    if req.report_type == "account_risk":
        context = _build_account_risk_context(db, lang)

    # For threat_analysis without specific asset, use global account risk context
    if req.report_type == "threat_analysis" and not req.asset_id and not req.scan_job_id:
        context = _build_account_risk_context(db, lang)

    if not context:
        context = "No scan data." if lang == "en-US" else "无扫描数据。"

    try:
        from backend.services import llm_service
        system_prompt = _get_report_system_prompt(req.report_type or "threat_analysis", lang)
        if lang == "en-US":
            user_prompt = f"## Context\n{context}\n\nPlease generate the report."
        else:
            user_prompt = f"## 上下文\n{context}\n\n请生成报告。"
        report = llm_service.generate_report(
            provider=llm_cfg.provider.value,
            api_key_enc=llm_cfg.api_key_enc,
            base_url=llm_cfg.base_url,
            model=llm_cfg.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return schemas.AIReportResponse(success=True, report=report)
    except Exception as e:
        return schemas.AIReportResponse(success=False, report=None, error=str(e))


# ─── Natural Language Asset Search ───────────────────────────────────────────

class SearchFilter:
    """Parsed filter from natural language query."""
    def __init__(self):
        self.asset_categories: list[str] = []
        self.os_types: list[str] = []
        self.db_types: list[str] = []
        self.network_types: list[str] = []
        self.iot_types: list[str] = []
        self.keywords: list[str] = []
        self.has_admin_accounts: bool = False
        self.unlogined_admin: bool = False
        self.dormant: bool = False
        self.online_only: bool = False
        self.offline_only: bool = False
        self.scan_failed: bool = False
        self.parent_asset_id: int | None = None


def _parse_nl_patterns(query: str) -> tuple[SearchFilter, list[str]]:
    """
    Parse natural language query using keyword patterns.
    Returns (filter, explanation).
    """
    q = query.lower()
    f = SearchFilter()
    explanation: list[str] = []

    # Asset category keywords
    if any(k in q for k in ['服务器', 'server', 'linux', 'windows', '物理机', '虚拟机']):
        f.asset_categories.append('server')
        explanation.append('资产类别: 服务器')
    if any(k in q for k in ['数据库', 'database', 'mysql', 'postgresql', 'redis', 'mongodb']):
        f.asset_categories.append('database')
        explanation.append('资产类别: 数据库')
    if any(k in q for k in ['网络', 'network', '交换机', '路由器', 'cisco', 'h3c', 'huawei']):
        f.asset_categories.append('network')
        explanation.append('资产类别: 网络设备')
    if any(k in q for k in ['iot', '摄像头', 'camera', 'nvr', 'sensor']):
        f.asset_categories.append('iot')
        explanation.append('资产类别: IoT')

    # OS type
    if any(k in q for k in ['linux']):
        f.os_types.append('linux')
        explanation.append('操作系统: Linux')
    if any(k in q for k in ['windows']):
        f.os_types.append('windows')
        explanation.append('操作系统: Windows')

    # DB type
    for db in ['mysql', 'postgresql', 'redis', 'mongodb', 'mssql']:
        if db in q:
            f.db_types.append(db)
            explanation.append(f'数据库类型: {db}')

    # Admin accounts
    if any(k in q for k in ['管理员', 'admin', '特权', 'sudo', 'root']):
        f.has_admin_accounts = True
        explanation.append('有管理员账号')

    # Unlogined admin
    if any(k in q for k in ['未登录', '从未登录', '未登录过']):
        f.unlogined_admin = True
        explanation.append('有未登录的管理员账号')

    # Dormant
    if any(k in q for k in ['静默', 'dormant', '长期未登录', '90天']):
        f.dormant = True
        explanation.append('长期未登录')

    # Online/Offline
    if any(k in q for k in ['在线', 'online']):
        f.online_only = True
        explanation.append('在线资产')
    if any(k in q for k in ['离线', 'offline', 'down']):
        f.offline_only = True
        explanation.append('离线资产')

    # Scan failed
    if any(k in q for k in ['扫描失败', '认证失败', 'auth_failed']):
        f.scan_failed = True
        explanation.append('扫描失败/认证失败')

    # Keywords (IP, hostname, username)
    ip_pattern = re.findall(r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b', query)
    f.keywords.extend(ip_pattern)
    if ip_pattern:
        explanation.append(f'IP: {", ".join(ip_pattern)}')

    asm_codes = re.findall(r'\bASM-\d+\b', query, re.IGNORECASE)
    f.keywords.extend(asm_codes)

    # Generic keyword (everything else that looks like a hostname or term)
    generic = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b', query)
    stop_words = {'过去', '现在', '所有', '的', '和', '或', '在', 'with', 'and', 'or', 'the', '所有', '最近'}
    f.keywords.extend([w for w in generic if w not in stop_words])

    return f, explanation


def _build_search_filter(query: str, llm_cfg, db) -> SearchFilter:
    """
    Try LLM-based parsing first; fall back to pattern matching.
    """
    if llm_cfg and llm_cfg.api_key_enc:
        try:
            from backend.services import llm_service
            system_prompt = """你是一个资产安全查询解析器。
给定一个自然语言查询，返回 JSON 对象描述过滤条件。
支持的字段：
- asset_categories: ["server","database","network","iot"]
- os_types: ["linux","windows"]
- db_types: ["mysql","postgresql","redis","mongodb","mssql"]
- network_types: ["cisco","h3c","huawei"]
- has_admin_accounts: bool
- unlogined_admin: bool
- dormant: bool
- online_only: bool
- offline_only: bool
- scan_failed: bool
- keywords: [string]  # IP addresses, hostnames, account names
返回纯 JSON，不要解释。"""
            user_prompt = f"查询：{query}"
            raw = llm_service.generate_report(
                provider=llm_cfg.provider.value,
                api_key_enc=llm_cfg.api_key_enc,
                base_url=llm_cfg.base_url,
                model=llm_cfg.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            import json
            data = json.loads(raw)
            f = SearchFilter()
            f.asset_categories = data.get('asset_categories', [])
            f.os_types = data.get('os_types', [])
            f.db_types = data.get('db_types', [])
            f.network_types = data.get('network_types', [])
            f.iot_types = data.get('iot_types', [])
            f.has_admin_accounts = data.get('has_admin_accounts', False)
            f.unlogined_admin = data.get('unlogined_admin', False)
            f.dormant = data.get('dormant', False)
            f.online_only = data.get('online_only', False)
            f.offline_only = data.get('offline_only', False)
            f.scan_failed = data.get('scan_failed', False)
            f.keywords = data.get('keywords', [])
            return f
        except Exception:
            pass
    return _parse_nl_patterns(query)[0]


@router.post("/search")
async def natural_language_search(
    q: str = Query(..., description="自然语言查询"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Natural language asset search.
    Examples:
      "过去30天有新增管理员账号的Linux服务器"
      "MySQL 数据库中有 root 账号的所有资产"
      "离线超过90天的资产"
    """
    # Check LLM config
    llm_cfg = db.query(models.LLMConfig).filter(
        models.LLMConfig.enabled == True,
    ).first()

    filt = _build_search_filter(q, llm_cfg, db)
    _, explanation = _parse_nl_patterns(q)

    # Build SQL query
    query = db.query(models.Asset)

    if filt.asset_categories:
        query = query.filter(models.Asset.asset_category.in_(filt.asset_categories))
    if filt.os_types:
        query = query.filter(models.Asset.os_type.in_(filt.os_types))
    if filt.db_types:
        query = query.filter(models.Asset.db_type.in_(filt.db_types))
    if filt.network_types:
        query = query.filter(models.Asset.network_type.in_(filt.network_types))
    if filt.iot_types:
        query = query.filter(models.Asset.iot_type.in_(filt.iot_types))

    if filt.online_only:
        query = query.filter(models.Asset.status == models.AssetStatus.online)
    elif filt.offline_only:
        query = query.filter(models.Asset.status == models.AssetStatus.offline)
    elif filt.scan_failed:
        query = query.filter(models.Asset.status == models.AssetStatus.auth_failed)

    # Separate account-name keywords from asset IP/hostname keywords.
    # Account-name keywords (root, oracle, mysql, nginx…) filter account usernames.
    account_name_kws = [kw for kw in filt.keywords if not _is_ip_or_asm(kw)]
    # Remaining keywords (IP, ASM codes) filter asset IP / hostname
    asset_kws = [kw for kw in filt.keywords if _is_ip_or_asm(kw)]
    if asset_kws:
        from sqlalchemy import or_ as or_filter
        kw_filters = [
            models.Asset.ip.ilike(f"%{kw}%")
            for kw in asset_kws
        ]
        query = query.filter(or_filter(*kw_filters))

    results = query.all()

    # Load all relevant account snapshots for filtering and display
    def _naive(dt):
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None) - dt.utcoffset()
        return dt

    job_ids = list({a.last_scan_job_id for a in results if a.last_scan_job_id})
    cutoff = datetime.utcnow() - timedelta(days=90)
    snaps_by_asset: dict = {}
    if job_ids:
        all_snaps_q = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.job_id.in_(job_ids)
        )
        for s in all_snaps_q.all():
            snaps_by_asset.setdefault(s.asset_id, []).append(s)

    def _asset_matches(asset_id: int) -> bool:
        snaps = snaps_by_asset.get(asset_id, [])
        # Username keyword filter: asset must have at least one matching account
        if account_name_kws:
            matched = [
                s for s in snaps
                if any(kw.lower() in (s.username or "").lower() for kw in account_name_kws)
            ]
            if not matched:
                return False
            # If has_admin_accounts / unlogined_admin also set, apply on top of matched accounts
            if filt.unlogined_admin:
                return any(s.is_admin and (not s.last_login or _naive(s.last_login) < cutoff) for s in matched)
            if filt.has_admin_accounts:
                return any(s.is_admin for s in matched)
            return True
        # No username kw: apply normal admin/dormant filters on all accounts
        if filt.unlogined_admin:
            return any(s.is_admin and (not s.last_login or _naive(s.last_login) < cutoff) for s in snaps)
        if filt.has_admin_accounts:
            return any(s.is_admin for s in snaps)
        return True

    filtered_results = [a for a in results if _asset_matches(a.id)]

    response_assets = []
    for asset in filtered_results[:50]:
        all_snaps = snaps_by_asset.get(asset.id, [])
        snaps_for_display = [
            {
                "id": s.id,
                "username": s.username,
                "is_admin": s.is_admin,
                "account_status": s.account_status,
                "last_login": s.last_login.isoformat() if s.last_login else None,
            }
            for s in all_snaps[:20]
        ]
        response_assets.append({
            "id": asset.id,
            "asset_code": asset.asset_code,
            "ip": asset.ip,
            "hostname": asset.hostname,
            "asset_category": asset.asset_category.value,
            "status": asset.status.value,
            "account_count": len(all_snaps),
            "admin_count": sum(1 for s in snaps_for_display if s["is_admin"]),
            "latest_accounts": snaps_for_display[:5],
        })

    return {
        "query": q,
        "filter_explanation": explanation,
        "llm_powered": bool(llm_cfg and llm_cfg.api_key_enc),
        "total_found": len(response_assets),
        "assets": response_assets,  # matches frontend SearchResult interface
    }


def _is_ip_or_asm(s: str) -> bool:
    """Return True if s looks like an IP address or ASM-XXXX code."""
    import re
    if re.match(r'\b\d{1,3}(\.\d{1,3}){3}\b', s):
        return True
    if re.match(r'\bASM-\d+\b', s, re.IGNORECASE):
        return True
    return False
