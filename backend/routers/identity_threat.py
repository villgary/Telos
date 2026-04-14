"""
Identity Threat Cognitive Analysis — API Router

五层分析引擎入口：
  POST /identity-threat/analyze         — 触发分析
  GET  /identity-threat/analyses       — 分析历史
  GET  /identity-threat/analyses/{id}  — 分析详情
  GET  /identity-threat/accounts/{id}  — 账号级信号
  GET  /identity-threat/graph/{id}     — 威胁图快照
  GET  /identity-threat/attack-paths/{id} — 攻击路径
  POST /identity-threat/report/{id}    — 重新生成LLM报告
  GET  /identity-threat/mitre-layer/{id} — MITRE ATT&CK Navigator层导出
  GET  /identity-threat/stream         — SSE实时分析完成通知
"""
import asyncio
import re
import time
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user
from backend.database import get_db
from backend.schemas import (
    IdentityThreatAnalysisResponse,
    IdentityThreatAnalysisListItem,
    ThreatAccountSignalResponse,
    ThreatGraphData,
    ThreatGraphNode,
    ThreatGraphEdge,
    AnalyzeRequest,
    AnalyzeResponse,
)
from backend.services.mitre_mapping import export_attack_nav_layer
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/identity-threat", tags=["identity-threat"])


def _analysis_to_response(
    a: models.IdentityThreatAnalysis,
    include_graph: bool = True,
    signals_limit: int = 0,
    include_report: bool = True,
) -> IdentityThreatAnalysisResponse:
    """Convert ORM model to Pydantic response.

    Args:
        include_graph: if False, threat_graph is empty (saves ~180KB per response).
            Use this for the initial page load; GraphVizTab fetches it separately.
        signals_limit: if > 0, truncate each signal array to this many items.
            Use 0 (default) to include all signals.
        include_report: if False, llm_report is excluded (saves ~10-20KB per response).
            Use False for initial page load; load on demand via "加载AI报告" button.
    """
    tg_data = ThreatGraphData()
    total_nodes = 0
    total_edges = 0
    if a.threat_graph and include_graph:
        nodes = [ThreatGraphNode(**n) for n in a.threat_graph.get("nodes", [])]
        edges = [ThreatGraphEdge(**e) for e in a.threat_graph.get("edges", [])]
        tg_data = ThreatGraphData(nodes=nodes, edges=edges)
        total_nodes = len(nodes)
        total_edges = len(edges)
    elif a.threat_graph:
        # Count only — avoid serializing all node/edge objects
        total_nodes = len(a.threat_graph.get("nodes", []))
        total_edges = len(a.threat_graph.get("edges", []))

    def _limit(signals, limit):
        return signals[:limit] if limit > 0 else signals

    semiotic_all = a.semiotic_signals or []
    causal_all = a.causal_signals or []
    ontological_all = a.ontological_signals or []
    cognitive_all = a.cognitive_signals or []
    anthro_all = a.anthropological_signals or []

    return IdentityThreatAnalysisResponse(
        id=a.id,
        analysis_type=a.analysis_type,
        scope=a.scope,
        scope_id=a.scope_id,
        semiotic_score=a.semiotic_score,
        causal_score=a.causal_score,
        ontological_score=a.ontological_score,
        cognitive_score=a.cognitive_score,
        anthropological_score=a.anthropological_score,
        overall_score=a.overall_score,
        overall_level=a.overall_level,
        semiotic_signals=_limit(semiotic_all, signals_limit),
        causal_signals=_limit(causal_all, signals_limit),
        ontological_signals=_limit(ontological_all, signals_limit),
        cognitive_signals=_limit(cognitive_all, signals_limit),
        anthropological_signals=_limit(anthro_all, signals_limit),
        threat_graph=tg_data,
        total_nodes=total_nodes,
        total_edges=total_edges,
        total_semiotic=len(semiotic_all),
        total_causal=len(causal_all),
        total_ontological=len(ontological_all),
        total_cognitive=len(cognitive_all),
        total_anthropological=len(anthro_all),
        llm_report=a.llm_report if include_report else None,
        analyzed_count=a.analyzed_count,
        duration_ms=a.duration_ms,
        model_used=a.model_used,
        created_by=a.created_by,
        created_at=a.created_at,
    )


# ─── Trigger analysis ────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_201_CREATED)
def trigger_analysis(
    body: AnalyzeRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Trigger a new identity threat analysis run.

    - scope "global": analyze all accounts
    - scope "asset": analyze accounts on specific asset (scope_id = asset_id)
    - scope "identity": analyze accounts for specific human identity (scope_id = identity_id)
    """
    if body.scope not in ("global", "asset", "identity"):
        raise HTTPException(400, "scope must be global | asset | identity")
    if body.scope != "global" and body.scope_id is None:
        raise HTTPException(400, "scope_id required when scope is asset or identity")

    from backend.services.identity_threat_analyzer import IdentityThreatAnalyzer

    analyzer = IdentityThreatAnalyzer(db)
    analysis = analyzer.run_full_analysis(
        scope=body.scope,
        scope_id=body.scope_id,
        user_id=user.id,
        lang=body.lang,
        generate_report=True,
    )

    return AnalyzeResponse(
        id=analysis.id,
        analysis_type=analysis.analysis_type,
        scope=analysis.scope,
        overall_score=analysis.overall_score,
        overall_level=analysis.overall_level,
        analyzed_count=analysis.analyzed_count,
        duration_ms=analysis.duration_ms,
        llm_report=analysis.llm_report,
        created_at=analysis.created_at,
    )


# ─── List analysis history ────────────────────────────────────────────────────────

@router.get("/analyses", response_model=list[IdentityThreatAnalysisListItem])
def list_analyses(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """List recent analysis runs (paginated)."""
    analyses = (
        db.query(models.IdentityThreatAnalysis)
        .order_by(models.IdentityThreatAnalysis.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Pre-fetch scope labels for asset/identity scopes
    asset_ids = {a.scope_id for a in analyses if a.scope == "asset" and a.scope_id}
    identity_ids = {a.scope_id for a in analyses if a.scope == "identity" and a.scope_id}
    asset_map = {a.id: a.asset_code for a in db.query(models.Asset).filter(models.Asset.id.in_(asset_ids)).all()} if asset_ids else {}
    identity_map = {i.id: i.name for i in db.query(models.Identity).filter(models.Identity.id.in_(identity_ids)).all()} if identity_ids else {}

    return [
        IdentityThreatAnalysisListItem(
            id=a.id,
            analysis_type=a.analysis_type,
            scope=a.scope,
            scope_id=a.scope_id,
            scope_label=(
                asset_map.get(a.scope_id)
                if a.scope == "asset" else
                identity_map.get(a.scope_id)
                if a.scope == "identity" else
                None
            ),
            overall_score=a.overall_score,
            overall_level=a.overall_level,
            analyzed_count=a.analyzed_count,
            duration_ms=a.duration_ms,
            created_by=a.created_by,
            created_at=a.created_at,
        )
        for a in analyses
    ]


# ─── Analysis detail ─────────────────────────────────────────────────────────────

@router.get("/analyses/{analysis_id}", response_model=IdentityThreatAnalysisResponse)
def get_analysis(
    analysis_id: int,
    lang: Annotated[str, Query(regex="^(zh|en)$")] = "zh",
    include_graph: Annotated[bool, Query(description="Include full threat_graph in response (~180KB)")] = False,
    signals_limit: Annotated[int, Query(ge=0, le=500, description="Max signals per category (0=all, saves ~700KB when small)")] = 0,
    include_report: Annotated[bool, Query(description="Include LLM report text (~10-20KB)")] = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Get full analysis result with five-layer signals.

    Optimizations for fast initial page load:
      - include_graph=False (default): GraphVizTab fetches separately.
      - include_report=False (default): load on demand via "加载AI报告" button.
      - signals_limit=0 (default): use getLayerSignals for per-tab loading.
    """
    a = db.query(models.IdentityThreatAnalysis).filter(
        models.IdentityThreatAnalysis.id == analysis_id
    ).first()
    if not a:
        raise HTTPException(404, "Analysis not found")

    # Fast path: use cached data directly (no re-computation).
    # include_report=False skips the report; signals_limit applies to signal arrays.
    return _analysis_to_response(
        a,
        include_graph=include_graph,
        signals_limit=signals_limit,
        include_report=include_report,
    )


# ─── Layer signals (with language re-computation) ───────────────────────────────

class LayerSignalsResponse(BaseModel):
    layer: str
    signals: list
    total: int


@router.get("/analyses/{analysis_id}/signals/{layer}", response_model=LayerSignalsResponse)
def get_analysis_layer_signals(
    analysis_id: int,
    layer: str,
    lang: Annotated[str, Query(regex="^(zh|en)$")] = "zh",
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Fetch signals for a specific layer, re-running engines in the requested language."""
    valid_layers = ("semiotic", "causal", "ontological", "cognitive", "anthropological")
    if layer not in valid_layers:
        raise HTTPException(400, f"layer must be one of: {', '.join(valid_layers)}")

    a = db.query(models.IdentityThreatAnalysis).filter(
        models.IdentityThreatAnalysis.id == analysis_id
    ).first()
    if not a:
        raise HTTPException(404, "Analysis not found")

    # Return stored signals directly (Go engine already enriched with MITRE data)
    key_map = {
        "semiotic": "semiotic_signals",
        "causal": "causal_signals",
        "ontological": "ontological_signals",
        "cognitive": "cognitive_signals",
        "anthropological": "anthropological_signals",
    }
    stored = getattr(a, key_map[layer], None) or []

    return LayerSignalsResponse(layer=layer, signals=stored, total=len(stored))


# ─── Account-level signals ───────────────────────────────────────────────────────

@router.get("/accounts/{analysis_id}", response_model=list[ThreatAccountSignalResponse])
def get_account_signals(
    analysis_id: int,
    lang: Annotated[str, Query(regex="^(zh|en)$")] = "zh",
    min_score: Annotated[int, Query(ge=0, le=100)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Get per-account signal明细 for an analysis, sorted by score desc.

    Re-runs engines from live DB data to get signals in the requested language.
    """
    a = db.query(models.IdentityThreatAnalysis).filter(
        models.IdentityThreatAnalysis.id == analysis_id
    ).first()
    if not a:
        raise HTTPException(404, "Analysis not found")

    # Re-run engines with requested language
    from backend.services.identity_threat_analyzer import IdentityThreatAnalyzer
    analyzer = IdentityThreatAnalyzer(db)
    new_signals = analyzer.rerun_engines(scope=a.scope, scope_id=a.scope_id, lang=lang)

    # Group signals by snapshot_id
    weights = {"critical": 100, "high": 75, "medium": 50, "low": 25, "info": 0}
    by_snapshot: dict = {}
    for key, sigs in [
        ("semiotic", new_signals["semiotic_signals"]),
        ("causal", new_signals["causal_signals"]),
        ("ontological", new_signals["ontological_signals"]),
        ("cognitive", new_signals["cognitive_signals"]),
        ("anthropological", new_signals["anthropological_signals"]),
    ]:
        for sig in sigs:
            nid = sig.get("node_id", "")
            snap_id = int(nid.replace("snap_", "")) if nid else 0
            if snap_id not in by_snapshot:
                by_snapshot[snap_id] = {
                    "semiotic": [], "causal": [], "ontological": [],
                    "cognitive": [], "anthropological": [], "username": "",
                    "asset_id": 0, "asset_code": "",
                }
            by_snapshot[snap_id][key].append(sig)
            if sig.get("username"):
                by_snapshot[snap_id]["username"] = sig["username"]
            if sig.get("asset_id"):
                by_snapshot[snap_id]["asset_id"] = sig["asset_id"]
            if sig.get("asset_code"):
                by_snapshot[snap_id]["asset_code"] = sig["asset_code"]

    # Build response list
    results = []
    for snap_id, grouped in by_snapshot.items():
        all_sigs = (
            grouped["semiotic"] + grouped["causal"] + grouped["ontological"]
            + grouped["cognitive"] + grouped["anthropological"]
        )
        score = int(sum(weights.get(s.get("severity", "info"), 0) for s in all_sigs) / max(len(all_sigs), 1))
        if score < min_score:
            continue
        level = "critical" if score >= 80 else "high" if score >= 60 else "medium" if score >= 40 else "low"
        results.append(ThreatAccountSignalResponse(
            id=0,
            analysis_id=analysis_id,
            snapshot_id=snap_id,
            username=grouped["username"],
            asset_id=grouped["asset_id"],
            asset_code=grouped["asset_code"],
            semiotic_flags=grouped["semiotic"],
            causal_flags=grouped["causal"],
            ontological_flags=grouped["ontological"],
            cognitive_flags=grouped["cognitive"],
            anthropological_flags=grouped["anthropological"],
            account_score=score,
            account_level=level,
            created_at=datetime.utcnow(),
        ))

    results.sort(key=lambda x: x.account_score, reverse=True)
    return results[:limit]


# ─── Threat graph snapshot ────────────────────────────────────────────────────────

# ─── Attack paths ─────────────────────────────────────────────────────────────────

class AttackPathEdge(BaseModel):
    source: str
    target: str
    edge_type: str
    weight: float


class AttackPathNode(BaseModel):
    id: str
    snapshot_id: int
    username: str
    asset_id: int
    ip: Optional[str]
    hostname: Optional[str]
    is_admin: bool
    account_status: str


class AttackPathEntry(BaseModel):
    source_id: int
    source_name: str
    source_ip: Optional[str]
    source_has_credential_leak: bool
    source_has_nopasswd: bool
    hops: list[AttackPathEdge]
    targets: list[AttackPathNode]


class AttackPathsResponse(BaseModel):
    analysis_id: int
    max_hops: int
    total_paths: int
    paths: list[AttackPathEntry]


@router.get("/attack-paths/{analysis_id}", response_model=AttackPathsResponse)
def get_attack_paths(
    analysis_id: int,
    source_id: Annotated[int | None, Query(description="起点 snapshot_id，不传则从所有高危节点出发")] = None,
    max_hops: Annotated[int, Query(ge=1, le=5)] = 3,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    查询攻击路径图。

    - 不传 source_id：从所有 credential_findings 或 NOPASSWD 高危节点出发
    - 路径经过 ssh_key_reuse / auth_chain / permission_propagation 边
    - 返回每条路径的 hops（跳链）和 targets（可达终点）
    """
    a = db.query(models.IdentityThreatAnalysis).filter(
        models.IdentityThreatAnalysis.id == analysis_id
    ).first()
    if not a:
        raise HTTPException(404, "Analysis not found")
    if not a.threat_graph:
        return AttackPathsResponse(analysis_id=analysis_id, max_hops=max_hops, total_paths=0, paths=[])

    from backend.services.threat_graph import ThreatGraph

    graph = ThreatGraph.from_dict(a.threat_graph)

    def _is_high_risk(node) -> bool:
        raw = node.raw_info or {}
        findings = raw.get("credential_findings", [])
        has_cred_leak = any(f.get("risk") == "critical" for f in findings)
        has_nopasswd = node.sudo_config.get("nopasswd_sudo", False) if node.sudo_config else False
        return has_cred_leak or has_nopasswd

    if source_id:
        start_nodes = [n for nid, n in graph.nodes.items() if n.snapshot_id == source_id]
    else:
        start_nodes = [n for n in graph.nodes.values() if _is_high_risk(n)]

    paths: list[AttackPathEntry] = []
    for src in start_nodes:
        raw_src = src.raw_info or {}
        findings = raw_src.get("credential_findings", [])
        has_cred_leak = any(f.get("risk") == "critical" for f in findings)
        reachable = graph.get_all_reachable(src.node_id(), max_hops=max_hops)
        if not reachable:
            continue
        # Collect unique targets
        seen_targets = set()
        hops: list[AttackPathEdge] = []
        targets: list[AttackPathNode] = []
        for path_edges, target_node in reachable:
            if target_node.node_id() not in seen_targets:
                seen_targets.add(target_node.node_id())
                targets.append(AttackPathNode(
                    id=target_node.node_id(),
                    snapshot_id=target_node.snapshot_id,
                    username=target_node.username,
                    asset_id=target_node.asset_id,
                    ip=target_node.ip,
                    hostname=target_node.hostname,
                    is_admin=target_node.is_admin,
                    account_status=target_node.account_status,
                ))
            hops.extend(
                AttackPathEdge(source=e.source_id, target=e.target_id, edge_type=e.edge_type, weight=e.weight)
                for e in path_edges
            )

        paths.append(AttackPathEntry(
            source_id=src.snapshot_id,
            source_name=src.username,
            source_ip=src.ip,
            source_has_credential_leak=has_cred_leak,
            source_has_nopasswd=src.sudo_config.get("nopasswd_sudo", False) if src.sudo_config else False,
            hops=hops,
            targets=targets,
        ))

    return AttackPathsResponse(
        analysis_id=analysis_id,
        max_hops=max_hops,
        total_paths=sum(len(p.targets) for p in paths),
        paths=paths,
    )


# ─── Analysis diff ───────────────────────────────────────────────────────────────


class AnalysisDiffEntry(BaseModel):
    change_type: str          # new_signal | resolved_signal | score_delta
    layer: str
    severity: str
    detail: str
    evidence: Optional[str] = None
    node_id: Optional[str] = None
    username: Optional[str] = None
    asset_code: Optional[str] = None


class ScoreDelta(BaseModel):
    layer: str
    score_before: int
    score_after: int
    delta: int   # positive = worsened


class AnalysisDiffResponse(BaseModel):
    analysis_a: int
    analysis_b: int
    score_deltas: list[ScoreDelta]
    new_signals: list[AnalysisDiffEntry]
    resolved_signals: list[AnalysisDiffEntry]
    summary: str


@router.get("/diff", response_model=AnalysisDiffResponse)
def get_analysis_diff(
    a_id: Annotated[int, Query(description="较早的分析 ID")],
    b_id: Annotated[int, Query(description="较新的分析 ID")],
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Compare two identity threat analysis runs to show threat landscape evolution.

    Returns:
      - score_deltas: per-layer score changes (positive = worsened)
      - new_signals: signals present in B but not in A
      - resolved_signals: signals present in A but not in B
      - summary: human-readable narrative
    """
    a = db.query(models.IdentityThreatAnalysis).filter(
        models.IdentityThreatAnalysis.id == a_id
    ).first()
    b = db.query(models.IdentityThreatAnalysis).filter(
        models.IdentityThreatAnalysis.id == b_id
    ).first()
    if not a:
        raise HTTPException(404, f"Analysis {a_id} not found")
    if not b:
        raise HTTPException(404, f"Analysis {b_id} not found")

    # Score deltas
    score_deltas = []
    for layer, field_a, field_b in [
        ("semiotic", a.semiotic_score, b.semiotic_score),
        ("causal", a.causal_score, b.causal_score),
        ("ontological", a.ontological_score, b.ontological_score),
        ("cognitive", a.cognitive_score, b.cognitive_score),
        ("anthropological", a.anthropological_score, b.anthropological_score),
        ("overall", a.overall_score, b.overall_score),
    ]:
        delta = (field_b or 0) - (field_a or 0)
        if delta != 0:
            score_deltas.append(ScoreDelta(
                layer=layer,
                score_before=field_a or 0,
                score_after=field_b or 0,
                delta=delta,
            ))

    # Signal diff: flatten all signals per analysis, compare by type+node_id+detail hash
    def _flatten_signals(analysis):
        layers = {
            "semiotic": analysis.semiotic_signals or [],
            "causal": analysis.causal_signals or [],
            "ontological": analysis.ontological_signals or [],
            "cognitive": analysis.cognitive_signals or [],
            "anthropological": analysis.anthropological_signals or [],
        }
        items = []
        for layer, sigs in layers.items():
            for sig in sigs:
                items.append({
                    "layer": layer,
                    "type": sig.get("type", ""),
                    "detail": (sig.get("detail") or sig.get("evidence") or "")[:200],
                    "severity": sig.get("severity", "info"),
                    "evidence": sig.get("evidence"),
                    "node_id": sig.get("node_id"),
                    "username": sig.get("username"),
                    "asset_code": sig.get("asset_code"),
                })
        return items

    def _sig_key(s):
        return f"{s['layer']}::{s['type']}::{s['detail']}"

    sigs_a = {_sig_key(s): s for s in _flatten_signals(a)}
    sigs_b = {_sig_key(s): s for s in _flatten_signals(b)}

    new_keys = set(sigs_b.keys()) - set(sigs_a.keys())
    resolved_keys = set(sigs_a.keys()) - set(sigs_b.keys())

    def _to_entry(k: str, sigs_dict: dict) -> AnalysisDiffEntry:
        s = sigs_dict[k]
        return AnalysisDiffEntry(
            change_type="new_signal" if k in new_keys else "resolved_signal",
            layer=s["layer"],
            severity=s["severity"],
            detail=s["detail"],
            evidence=s.get("evidence"),
            node_id=s.get("node_id"),
            username=s.get("username"),
            asset_code=s.get("asset_code"),
        )

    new_signals = [_to_entry(k, sigs_b) for k in new_keys]
    resolved_signals = [_to_entry(k, sigs_a) for k in resolved_keys]

    # Sort: critical/high first
    def sev_weight(e: AnalysisDiffEntry) -> int:
        return {"critical": 3, "high": 2, "medium": 1, "low": 0, "info": -1}.get(e.severity, 0)

    new_signals.sort(key=sev_weight, reverse=True)
    resolved_signals.sort(key=sev_weight, reverse=True)

    # Summary
    worsened = sum(1 for d in score_deltas if d.delta > 0)
    improved = sum(1 for d in score_deltas if d.delta < 0)
    summary = (
        f"Compared analysis #{a_id} vs #{b_id}: "
        f"{len(new_signals)} new signals, {len(resolved_signals)} resolved. "
        f"{ worsened} layer(s) worsened, {improved} improved. "
        f"Overall score: {(b.overall_score or 0) - (a.overall_score or 0):+d}."
    )

    return AnalysisDiffResponse(
        analysis_a=a_id,
        analysis_b=b_id,
        score_deltas=score_deltas,
        new_signals=new_signals,
        resolved_signals=resolved_signals,
        summary=summary,
    )



@router.get("/graph/{analysis_id}", response_model=ThreatGraphData)
def get_threat_graph(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Get the threat graph (nodes + edges) for an analysis."""
    a = db.query(models.IdentityThreatAnalysis).filter(
        models.IdentityThreatAnalysis.id == analysis_id
    ).first()
    if not a:
        raise HTTPException(404, "Analysis not found")
    if not a.threat_graph:
        return ThreatGraphData()
    return ThreatGraphData(
        nodes=[ThreatGraphNode(**n) for n in a.threat_graph.get("nodes", [])],
        edges=[ThreatGraphEdge(**e) for e in a.threat_graph.get("edges", [])],
    )


# ─── Regenerate LLM report ───────────────────────────────────────────────────────

@router.post("/report/{analysis_id}", response_model=AnalyzeResponse)
def regenerate_report(
    analysis_id: int,
    lang: Annotated[str, Query(regex="^(zh|en)$")] = "zh",
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Regenerate the LLM report for an existing analysis."""
    a = db.query(models.IdentityThreatAnalysis).filter(
        models.IdentityThreatAnalysis.id == analysis_id
    ).first()
    if not a:
        raise HTTPException(404, "Analysis not found")

    from backend.services.identity_threat_analyzer import _generate_llm_report

    report = _generate_llm_report(
        semiotic_score=a.semiotic_score,
        causal_score=a.causal_score,
        ontological_score=a.ontological_score,
        cognitive_score=a.cognitive_score,
        anthropological_score=a.anthropological_score,
        overall_score=a.overall_score,
        semiotic_signals=a.semiotic_signals or [],
        causal_signals=a.causal_signals or [],
        ontological_signals=a.ontological_signals or [],
        cognitive_signals=a.cognitive_signals or [],
        anthropological_signals=a.anthropological_signals or [],
        analyzed_count=a.analyzed_count,
        lang=lang,
        db=db,
    )
    if report:
        a.llm_report = report
        a.model_used = "llm_configured"
        db.commit()
        db.refresh(a)

    return AnalyzeResponse(
        id=a.id,
        analysis_type=a.analysis_type,
        scope=a.scope,
        overall_score=a.overall_score,
        overall_level=a.overall_level,
        analyzed_count=a.analyzed_count,
        duration_ms=a.duration_ms,
        llm_report=a.llm_report,
        created_at=a.created_at,
    )


# ─── MITRE ATT&CK Navigator Layer Export ────────────────────────────────────────

@router.get("/mitre-layer/{analysis_id}")
async def get_mitre_layer(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Export MITRE ATT&CK Navigator-compatible layer JSON for an analysis.

    The layer colors each active technique by severity:
      - critical → #93281b (dark red)
      - high     → #e83e3e (red)
      - medium   → #f5c518 (yellow)
      - low      → #82c342 (green)

    Upload the result to https://mitre-attack.github.io/attack-navigator/
    """
    a = db.query(models.IdentityThreatAnalysis).get(analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found")

    # Collect all signals from the analysis
    all_signals = []
    for sig_group in [
        a.semiotic_signals or [],
        a.causal_signals or [],
        a.ontological_signals or [],
        a.cognitive_signals or [],
        a.anthropological_signals or [],
    ]:
        all_signals.extend(sig_group)

    layer = export_attack_nav_layer(all_signals, analysis_id)
    return layer


# ─── What-If Attack Simulation ──────────────────────────────────────────────────

class WhatIfReachableNode(BaseModel):
    snapshot_id: int
    username: str
    uid_sid: str
    asset_id: int
    asset_code: Optional[str]
    ip: Optional[str]
    hostname: Optional[str]
    is_admin: bool
    lifecycle: str
    account_status: str
    hops: int
    entry_edge_type: str
    entry_edge_weight: float


class WhatIfSimulationResponse(BaseModel):
    source_node: dict
    total_reachable: int
    human_reachable: int
    admin_reachable: int
    privileged_reachable: int
    asset_count: int
    unique_assets: list[int]
    mitre_techniques: list[dict]
    blast_radius_score: float
    blast_radius_level: str
    reachable_nodes: list[WhatIfReachableNode]
    hop_distribution: dict[int, int]


_HUMAN_SERVICE_PATTERNS = re.compile(
    r'^(root|bin|daemon|adm|sync|shutdown|halt|mail|news|uucp|operator|games|'
    r'gopher|ftp|nobody|nfsnobody|postgres|mysql|redis|nginx|apache|httpd|'
    r'www-data|systemd|dbus|polkitd|sshd|rpc|rpcuser|rpcbind)$'
)


def _is_human(username: str) -> bool:
    lower = username.lower()
    if _HUMAN_SERVICE_PATTERNS.match(lower):
        return False
    if re.match(r'^\d+$', username):
        return False
    return True


@router.get("/whatif/{analysis_id}")
async def whatif_simulate(
    analysis_id: int,
    source_id: Annotated[str, Query(description="Threat graph node ID (e.g. snap_123)")],
    max_hops: Annotated[int, Query(ge=1, le=10)] = 5,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    What-If Attack Simulation: if an attacker compromises the source account,
    what is the blast radius?

    Returns:
      - All reachable accounts (BFS up to max_hops)
      - Blast radius score and level
      - MITRE ATT&CK techniques applicable to this attack path
      - Per-hop distribution
    """
    a = db.query(models.IdentityThreatAnalysis).get(analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found")
    if not a.threat_graph:
        raise HTTPException(400, "Analysis has no threat graph")

    from backend.services.threat_graph import ThreatGraph

    graph = ThreatGraph.from_dict(a.threat_graph)
    # NOTE: Do NOT call compute_all_edges() here — it rebuilds edges from scratch,
    # overwriting the Go engine's computed attack edges (permission_propagation,
    # ssh_key_reuse, auth_chain) that are already correctly stored in threat_graph.
    # The stored edges from the Go engine are authoritative for WhatIf simulation.

    if source_id not in graph.nodes:
        raise HTTPException(404, f"Node {source_id} not found in graph")

    source_node = graph.nodes[source_id]
    reachable = graph.get_all_reachable(source_id, max_hops=max_hops)

    # Aggregate metrics
    human_reachable = 0
    admin_reachable = 0
    privileged_reachable = 0
    unique_assets: set[int] = {source_node.asset_id}
    hop_counts: dict[int, int] = {}
    reachable_nodes: list[WhatIfReachableNode] = []

    for path_edges, node in reachable:
        depth = len(path_edges)
        hop_counts[depth] = hop_counts.get(depth, 0) + 1
        unique_assets.add(node.asset_id)
        if _is_human(node.username):
            human_reachable += 1
        if node.is_admin:
            admin_reachable += 1
        if node.sudo_config or node.is_admin:
            privileged_reachable += 1
        entry_edge = path_edges[-1] if path_edges else None
        reachable_nodes.append(WhatIfReachableNode(
            snapshot_id=node.snapshot_id,
            username=node.username,
            uid_sid=node.uid_sid,
            asset_id=node.asset_id,
            asset_code=node.asset_code,
            ip=node.ip,
            hostname=node.hostname,
            is_admin=node.is_admin,
            lifecycle=node.lifecycle,
            account_status=node.account_status,
            hops=depth,
            entry_edge_type=entry_edge.edge_type if entry_edge else "",
            entry_edge_weight=entry_edge.weight if entry_edge else 0.0,
        ))

    total_reachable = len(reachable)
    asset_count = len(unique_assets)

    # Blast radius score: weighted sum
    blast_radius_score = (
        total_reachable * 1.0
        + admin_reachable * 5.0
        + (privileged_reachable - admin_reachable) * 3.0
        + human_reachable * 2.0
    )

    if blast_radius_score >= 50:
        level = "critical"
    elif blast_radius_score >= 25:
        level = "high"
    elif blast_radius_score >= 10:
        level = "medium"
    elif blast_radius_score > 0:
        level = "low"
    else:
        level = "minimal"

    # MITRE ATT&CK techniques for this simulation
    techniques: list[dict] = []
    if source_node.sudo_config or source_node.is_admin:
        techniques.append({
            "technique_id": "T1548.003",
            "name": "sudo / privilege escalation",
            "tactic": "TA0004",
            "tactic_label": "Privilege Escalation",
            "severity": "high",
            "rationale": "Compromised account has sudo privileges",
        })
    for path_edges, node in reachable:
        if not path_edges:
            continue
        edge_types = {e.edge_type for e in path_edges}
        if 'ssh_key_reuse' in edge_types:
            techniques.append({
                "technique_id": "T1552.004",
                "name": "SSH key reuse / lateral movement",
                "tactic": "TA0008",
                "tactic_label": "Lateral Movement",
                "severity": "critical",
                "rationale": "Attacker can authenticate using the shared SSH private key",
            })
        if 'permission_propagation' in edge_types:
            techniques.append({
                "technique_id": "T1021.004",
                "name": "Remote SSH / lateral movement",
                "tactic": "TA0008",
                "tactic_label": "Lateral Movement",
                "severity": "high",
                "rationale": "Permission propagation edge allows lateral movement",
            })
    # Deduplicate by technique_id
    seen = set()
    deduped = []
    for t in techniques:
        if t["technique_id"] not in seen:
            seen.add(t["technique_id"])
            deduped.append(t)

    return WhatIfSimulationResponse(
        source_node={
            "id": source_node.node_id(),
            "snapshot_id": source_node.snapshot_id,
            "username": source_node.username,
            "asset_code": source_node.asset_code,
            "ip": source_node.ip,
            "hostname": source_node.hostname,
            "is_admin": source_node.is_admin,
            "lifecycle": source_node.lifecycle,
            "account_status": source_node.account_status,
        },
        total_reachable=total_reachable,
        human_reachable=human_reachable,
        admin_reachable=admin_reachable,
        privileged_reachable=privileged_reachable,
        asset_count=asset_count,
        unique_assets=list(unique_assets),
        mitre_techniques=deduped,
        blast_radius_score=blast_radius_score,
        blast_radius_level=level,
        reachable_nodes=reachable_nodes,
        hop_distribution=hop_counts,
    )


# ─────────────── Real-time SSE Stream ─────────────────────────────────────────

# Lightweight in-process SSE manager for analysis events.
# No external dependency — self-contained in this router.
_analysis_sse_queues: dict[int, asyncio.Queue] = {}

async def _analysis_broadcast(event_data: dict) -> None:
    """Push an event to all connected SSE clients."""
    if not _analysis_sse_queues:
        return
    import json
    sse_msg = f"data: {json.dumps(event_data, default=str)}\n\n"
    for q in list(_analysis_sse_queues.values()):
        try:
            q.put_nowait(sse_msg)
        except asyncio.QueueFull:
            pass


@router.get("/stream")
async def analysis_stream(
    user: models.User = Depends(get_current_user),
):
    """
    Server-Sent Events (SSE) stream of analysis completion notifications.

    Frontend connects via:
      const es = new EventSource('/api/v1/identity-threat/stream')

    Each event is a JSON object: { event: "analysis_complete", analysis_id, scope, overall_score, overall_level, created_at }
    """
    from fastapi.responses import StreamingResponse

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        _analysis_sse_queues[user.id] = queue
        heartbeat_count = 0
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                    yield event
                    heartbeat_count = 0
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    heartbeat_count += 1
                    if heartbeat_count > 5:
                        break
        except asyncio.CancelledError:
            pass
        finally:
            _analysis_sse_queues.pop(user.id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
