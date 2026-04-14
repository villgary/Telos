"""
Knowledge Base Router — RAG-based security Q&A.

Provides:
  GET  /kb/search?q=      — keyword search across KB
  POST /kb/question       — RAG Q&A with LLM
  GET  /kb/stats          — KB statistics
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.auth import get_current_user, require_role
from backend import models
from backend.services.kb_data import (
    search_kb,
    get_kb_stats,
    build_rag_context,
    ATTACK_TACTICS,
    DATABASE_CVES,
    SECURITY_PRACTICES,
)
from backend.services.llm_service import generate_report

router = APIRouter(prefix="/api/v1/kb", tags=["knowledge-base"])


class QuestionRequest(BaseModel):
    question: str
    snapshot_id: Optional[int] = None


class QuestionResponse(BaseModel):
    answer: str
    sources: list[dict]
    snapshot_id: Optional[int] = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[dict]


@router.get("/search", response_model=SearchResponse)
def search(
    query: str,
    limit: int = 10,
    lang: str = "zh",
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    if not query or len(query.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    results = search_kb(query.strip(), limit=min(limit, 20), lang=lang, db=db)
    return SearchResponse(query=query, total=len(results), results=results)


@router.get("/stats")
def stats(
    lang: str = "zh",
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    from backend.services.kb_data import _localize_tactic, _localize_cve, _localize_practice
    stats_data = get_kb_stats(db=db)
    mitre_cats = [_localize_tactic(t, lang) for t in ATTACK_TACTICS]
    cve_cats = [_localize_cve(c, lang) for c in DATABASE_CVES]
    practice_cats = [_localize_practice(p, lang) for p in SECURITY_PRACTICES]
    return {
        **stats_data,
        "categories": {
            "mitre": [{"id": t["id"], "sub": t["sub"], "name": t["name"]} for t in mitre_cats],
            "cve": [{"cve": c["cve"], "product": c["product"], "severity": c["severity"]} for c in cve_cats],
            "practice": [{"category": p["category"], "title": p["title"]} for p in practice_cats],
        },
    }



@router.post("/question", response_model=QuestionResponse)
def ask_question(
    req: QuestionRequest,
    lang: str = Query("zh", description="Language: zh or en"),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    # Build system context from snapshot if provided
    system_context = None
    snapshot = None
    if req.snapshot_id:
        snapshot = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.id == req.snapshot_id
        ).first()
        if snapshot:
            asset = db.query(models.Asset).filter(models.Asset.id == snapshot.asset_id).first()
            # Get risk score
            risk_score = db.query(models.AccountRiskScore).filter(
                models.AccountRiskScore.snapshot_id == snapshot.id
            ).first()
            # Get lifecycle
            lc = db.query(models.AccountLifecycleStatus).filter(
                models.AccountLifecycleStatus.snapshot_id == snapshot.id
            ).first()
            risk_factors = []
            if risk_score and risk_score.risk_factors:
                risk_factors = [f.get("factor", "") for f in risk_score.risk_factors]
            system_context = {
                "account": {
                    "username": snapshot.username,
                    "uid_sid": snapshot.uid_sid,
                    "is_admin": snapshot.is_admin,
                    "shell": snapshot.shell,
                    "last_login": snapshot.last_login.isoformat() if snapshot.last_login else None,
                    "lifecycle": lc.lifecycle_status if lc else "unknown",
                },
                "asset": {
                    "asset_code": asset.asset_code if asset else None,
                    "ip": asset.ip if asset else None,
                    "os_type": str(asset.os_type) if asset else None,
                },
                "risk_factors": risk_factors,
            }

    # Get LLM config
    llm_config = db.query(models.LLMConfig).first()
    if not llm_config or not llm_config.api_key_set:
        raise HTTPException(status_code=503, detail="LLM not configured. Please set API key in AI Settings.")

    # Build RAG context
    kb_context = build_rag_context(system_context, lang=lang, db=db)

    # Build user question with context
    if lang == "en":
        system_prompt = """You are a professional account security analyst, expert in CVE vulnerabilities, MITRE ATT&CK tactics, and account security best practices.
Answer requirements:
1. Be concise and clear
2. Reference relevant CVEs (e.g. CVE-2021-3156) and ATT&CK IDs (e.g. T1078.003)
3. If system context (account/asset info) is provided, answer with that context
4. Provide actionable remediation recommendations
5. If no relevant information exists in the knowledge base, clearly state so
"""
        user_prompt = f"""Based on the following knowledge base content, answer the user's question. If no relevant information exists, say so directly.

--- Knowledge Base ---
{kb_context}
---

--- User Question ---
{req.question}
"""
    else:
        system_prompt = """你是一个专业的账号安全分析师，擅长解读 CVE 漏洞、MITRE ATT&CK 战术和账号安全最佳实践。
回答要求：
1. 简洁明了，使用中文
2. 引用相关 CVE（如 CVE-2021-3156）和 ATT&CK ID（如 T1078.003）
3. 如系统提供了具体账号/资产信息，结合该上下文回答
4. 给出可操作的处置建议
5. 如果知识库中没有相关信息，明确告知用户
"""
        user_prompt = f"""基于以下知识库内容，回答用户问题。如果知识库中没有相关信息，直接说明。

--- 知识库 ---
{kb_context}
---

--- 用户问题 ---
{req.question}
"""

    try:
        answer = generate_report(
            provider=llm_config.provider,
            api_key_enc=llm_config.encrypted_api_key,
            base_url=llm_config.base_url,
            model=llm_config.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")

    # Build sources list — include most relevant entries
    search_results = search_kb(req.question, limit=5, lang=lang)
    sources = []
    for r in search_results:
        src = {"type": r["type"]}
        if r["type"] == "mitre":
            src["id"] = r.get("id", "")
            src["title"] = f"{r.get('id','')}{'.'+r.get('sub','') if r.get('sub') else ''} {r.get('name','')}"
        elif r["type"] == "cve":
            src["id"] = r.get("cve", "")
            src["title"] = f"{r.get('cve','')} {r.get('product','')} ({r.get('severity','')})"
        elif r["type"] == "practice":
            src["title"] = f"[{r.get('category','')}] {r.get('title','')}"
        sources.append(src)

    return QuestionResponse(
        answer=answer,
        sources=sources,
        snapshot_id=req.snapshot_id,
    )


@router.get("/tactics")
def list_tactics(lang: str = "zh", _: models.User = Depends(get_current_user)):
    from backend.services.kb_data import _localize_tactic
    return {"data": [{"type": "mitre", **_localize_tactic(t, lang)} for t in ATTACK_TACTICS]}


@router.get("/cves")
def list_cves(lang: str = "zh", _: models.User = Depends(get_current_user)):
    from backend.services.kb_data import _localize_cve
    return {"data": [{"type": "cve", **_localize_cve(c, lang)} for c in DATABASE_CVES]}


@router.get("/practices")
def list_practices(lang: str = "zh", _: models.User = Depends(get_current_user)):
    from backend.services.kb_data import _localize_practice
    return {"data": [{"type": "practice", **_localize_practice(p, lang)} for p in SECURITY_PRACTICES]}


# ── Admin CRUD for custom KB entries ─────────────────────────────────────────

from backend.schemas import KBEntryCreate, KBEntryUpdate, KBEntryResponse

VALID_ENTRY_TYPES = {"mitre", "cve", "practice"}


def _map_kb_entry(entry: models.KBEntry, lang: str = "zh") -> dict:
    """Map a DB KBEntry to the same dict shape used by search_kb results."""
    title = entry.title_en if lang == "en" and entry.title_en else entry.title
    desc = entry.description_en if lang == "en" and entry.description_en else entry.description
    result = {
        "type": entry.entry_type,
        "id": entry.id,
        "name": title,
        "title": title,
        "description": desc,
    }
    if entry.extra_data:
        result.update(entry.extra_data)
    return result


@router.get("/entries", response_model=list[KBEntryResponse])
def list_entries(
    type: str = Query(None, description="Filter by entry type: mitre, cve, practice"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.KBEntry)
    if type and type in VALID_ENTRY_TYPES:
        q = q.filter(models.KBEntry.entry_type == type)
    total = q.count()
    entries = q.order_by(models.KBEntry.created_at.desc()).offset(offset).limit(limit).all()
    return entries


@router.get("/entries/{entry_id}", response_model=KBEntryResponse)
def get_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    entry = db.query(models.KBEntry).filter(models.KBEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.post("/entries", response_model=KBEntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    data: KBEntryCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.UserRole.admin)),
):
    if data.entry_type not in VALID_ENTRY_TYPES:
        raise HTTPException(status_code=400, detail=f"entry_type must be one of {VALID_ENTRY_TYPES}")
    entry = models.KBEntry(
        entry_type=data.entry_type,
        title=data.title,
        title_en=data.title_en,
        description=data.description,
        description_en=data.description_en,
        extra_data=data.extra_data or {},
        created_by=user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/entries/{entry_id}", response_model=KBEntryResponse)
def update_entry(
    entry_id: int,
    data: KBEntryUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.UserRole.admin)),
):
    entry = db.query(models.KBEntry).filter(models.KBEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    for field in ["title", "title_en", "description", "description_en", "enabled"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(entry, field, val)
    if data.extra_data is not None:
        entry.extra_data = data.extra_data
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role(models.UserRole.admin)),
):
    entry = db.query(models.KBEntry).filter(models.KBEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
