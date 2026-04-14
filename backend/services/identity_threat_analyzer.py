"""
Identity Threat Analyzer — 五层分析编排器

P1: Semiotics (已实现)
P2: Ontology + Causal Inference (已实现)
P3: Cognitive Blindspot (已实现)
P4: Anthropology (已实现)
P5: LLM Report (已实现)

Usage:
    analyzer = IdentityThreatAnalyzer(db)
    analysis = analyzer.run_full_analysis(scope="global", user_id=1)
"""
import os
import time
from typing import Optional

from sqlalchemy.orm import Session

from backend import models
from backend.services.threat_graph import ThreatGraph, ThreatNode, ThreatEdge
from backend.services.semiotics_engine import SemioticsEngine
from backend.services.causal_inference_engine import analyze as causal_analyze
from backend.services.ontology_engine import analyze as ontology_analyze
from backend.services.cognitive_blindspot_engine import analyze as cognitive_analyze
from backend.services.anthropology_engine import analyze as anthropology_analyze
from backend.services.mitre_mapping import enrich_signal_list
from backend.services.go_analysis_engine import run_full_analysis_go


# ─── LLM report generation ───────────────────────────────────────────────────────

_REPORT_PROMPT_ZH = """你是一名高级网络安全分析师，负责 CSOC 账号安全威胁分析。

以下是基于五层身份威胁分析框架的结构化结果：

## 综合风险评分
- 符号异常分: {semiotic_score}/100
- 因果推断分: {causal_score}/100
- 本体同一性分: {ontological_score}/100
- 认知盲区分: {cognitive_score}/100
- 人类学关系分: {anthropological_score}/100
- 综合风险分: {overall_score}/100

## 分析范围
- 分析账号数: {analyzed_count}

## 关键信号摘要

### 符号异常 (Top 5)
{top_semiotic}

### 因果推断 (Top 5)
{top_causal}

### 本体同一性 (Top 5)
{top_ontological}

### 认知盲区 (Top 5)
{top_cognitive}

### 人类学关系 (Top 5)
{top_anthro}

## 输出要求

请按以下 Markdown 格式输出分析报告（中文，500字以内）：

### 【总结】
1-2 句话概括当前账号安全态势。

### 【关键发现】
列出最可疑的 3 个点（结合五层信号），每点一句话。

### 【攻击者假设】
如果攻击者已获得初始访问权限，最可能的横向移动路径是什么？基于图中的 permission_propagation 边和同一身份链路分析。

### 【验证步骤】
给出 3 个具体的验证排查建议，按优先级排序。

### 【处置建议】
给出最安全的处置建议（1-2 条）。
"""

_REPORT_PROMPT_EN = """You are a senior cybersecurity analyst for a CSOC, specializing in account identity threat analysis.

Based on the five-layer Identity Threat Cognitive Analysis framework, here are the structured results:

## Overall Risk Scores
- Semiotics Score: {semiotic_score}/100
- Causal Inference Score: {causal_score}/100
- Ontological Identity Score: {ontological_score}/100
- Cognitive Blindspot Score: {cognitive_score}/100
- Anthropological Relations Score: {anthropological_score}/100
- Overall Score: {overall_score}/100

## Scope
- Accounts analyzed: {analyzed_count}

## Key Signals

### Semiotics (Top 5)
{top_semiotic}

### Causal Inference (Top 5)
{top_causal}

### Ontological Identity (Top 5)
{top_ontological}

### Cognitive Blindspot (Top 5)
{top_cognitive}

### Anthropological Relations (Top 5)
{top_anthro}

## Output Format (English, < 500 words)

### [Summary]
1-2 sentences summarizing current account security posture.

### [Key Findings]
Top 3 most suspicious signals (across all five layers).

### [Attacker Hypothesis]
If an attacker has initial access, what is the most likely lateral movement path based on the permission propagation graph and same-identity links?

### [Verification Steps]
3 specific investigation steps in priority order.

### [Remediation]
1-2 most secure remediation recommendations.
"""


def _generate_llm_report(
    semiotic_score: int,
    causal_score: int,
    ontological_score: int,
    cognitive_score: int,
    anthropological_score: int,
    overall_score: int,
    semiotic_signals: list,
    causal_signals: list,
    ontological_signals: list,
    cognitive_signals: list,
    anthropological_signals: list,
    analyzed_count: int,
    lang: str = "zh",
    db: Session = None,
) -> Optional[str]:
    """
    Generate LLM-powered natural language report.
    Returns None if LLM is not configured/enabled.
    """
    # Try to load LLM config
    if db is None:
        return None

    llm_cfg = db.query(models.LLMConfig).filter(
        models.LLMConfig.enabled == True  # noqa: E712
    ).first()

    if not llm_cfg:
        return None

    def _summarize_signals(signals: list, label: str) -> str:
        if not signals:
            return f"{label}: 无信号"
        top = signals[:5]
        lines = [f"{label} ({len(signals)} total):"]
        for s in top:
            detail = s.get('detail', s.get('description', ''))
            sev = s.get('severity', 'unknown')
            lines.append(f"  - [{sev}] {detail}")
        return '\n'.join(lines)

    top_semiotic = _summarize_signals(semiotic_signals, "符号异常")
    top_causal = _summarize_signals(causal_signals, "因果推断")
    top_ontological = _summarize_signals(ontological_signals, "本体同一性")
    top_cognitive = _summarize_signals(cognitive_signals, "认知盲区")
    top_anthro = _summarize_signals(anthropological_signals, "人类学关系")

    template = _REPORT_PROMPT_ZH if lang and lang.startswith("zh") else _REPORT_PROMPT_EN

    user_prompt = template.format(
        semiotic_score=semiotic_score,
        causal_score=causal_score,
        ontological_score=ontological_score,
        cognitive_score=cognitive_score,
        anthropological_score=anthropological_score,
        overall_score=overall_score,
        analyzed_count=analyzed_count,
        top_semiotic=top_semiotic,
        top_causal=top_causal,
        top_ontological=top_ontological,
        top_cognitive=top_cognitive,
        top_anthro=top_anthro,
    )

    system_prompt = (
        "你是一名高级网络安全分析师，专注于账号身份威胁分析。"
        if lang == "zh" else
        "You are a senior cybersecurity analyst specializing in account identity threat analysis."
    )

    try:
        from backend.services.llm_service import generate_report

        report = generate_report(
            provider=llm_cfg.provider.value,
            api_key_enc=llm_cfg.api_key_enc,
            base_url=llm_cfg.base_url,
            model=llm_cfg.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return report
    except Exception:
        return None


# ─── Main Analyzer ───────────────────────────────────────────────────────────────

class IdentityThreatAnalyzer:
    """
    五层身份威胁分析编排器.

    Usage:
        analyzer = IdentityThreatAnalyzer(db)
        analysis = analyzer.run_full_analysis(scope="global", user_id=1, lang="zh")
    """

    def __init__(self, db: Session):
        self.db = db

    # ─── Go Engine Integration ─────────────────────────────────────────────────

    @staticmethod
    def _convert_go_threat_graph(go_tg: dict) -> dict:
        """
        Convert Go engine threat_graph format to Python ThreatGraph.from_dict() format.

        Go engine returns:
            {"nodes": {"snap_1": {...node...}}, "edges": [{source, target, edge_type, weight}]}

        Python ThreatGraph.from_dict() expects:
            {"nodes": [{id, snapshot_id, ...}], "edges": [{source, target, edge_type, weight}]}
        """
        if not go_tg:
            return {}
        nodes_dict = go_tg.get("nodes") or {}
        nodes_list = []
        for node_id, node_data in nodes_dict.items():
            nd = dict(node_data)
            nd["id"] = node_id
            nodes_list.append(nd)
        return {
            "nodes": nodes_list,
            "edges": go_tg.get("edges") or [],
        }

    def _run_via_go_engine(
        self,
        scope: str,
        scope_id: Optional[int],
        user_id: Optional[int],
        lang: str,
        generate_report: bool,
    ) -> models.IdentityThreatAnalysis:
        """
        Run analysis via the Go engine microservice (telos-engine on port 8082).

        The Go engine runs all 5 analysis layers in parallel goroutines and
        returns layer scores + signals + threat_graph in a single HTTP call.
        """
        import logging
        logger = logging.getLogger(__name__)

        t0 = time.time()
        logger.info("Delegating analysis to Go engine (USE_GO_ANALYSIS_ENGINE=1)")

        try:
            result = run_full_analysis_go(scope=scope, scope_id=scope_id, lang=lang)
        except Exception as e:
            logger.error(f"Go engine call failed: {e}")
            raise RuntimeError(f"Go analysis engine unavailable: {e}") from e

        layer_scores = result.get("layer_scores") or {}
        threat_graph_raw = result.get("threat_graph") or {}

        # Convert Go graph format to Python format for ThreatGraph.from_dict()
        threat_graph = self._convert_go_threat_graph(threat_graph_raw)

        # Pull out the Go-computed edges (already in correct format)
        # and keep them as-is — do NOT run Python compute_all_edges() on them
        go_edges = threat_graph.get("edges") or []
        logger.info(f"Go engine returned {len(threat_graph.get('nodes', []))} nodes, {len(go_edges)} edges")

        semiotic_score = layer_scores.get("semiotic_score", 0)
        causal_score = layer_scores.get("causal_score", 0)
        ontological_score = layer_scores.get("ontological_score", 0)
        cognitive_score = layer_scores.get("cognitive_score", 0)
        anthropological_score = layer_scores.get("anthropological_score", 0)
        overall_score = layer_scores.get("overall_score", 0)
        overall_level = layer_scores.get("overall_level", "low")

        # Persist Go signals into DB (mirrors Python engine's per-account signal persistence)
        all_go_signals = {
            "semiotic": result.get("semiotic_signals") or [],
            "causal": result.get("causal_signals") or [],
            "ontological": result.get("ontological_signals") or [],
            "cognitive": result.get("cognitive_signals") or [],
            "anthropological": result.get("anthropological_signals") or [],
        }

        # Enrich all signals with MITRE ATT&CK metadata before persisting
        from backend.services.mitre_mapping import enrich_signal_list
        for layer in all_go_signals:
            all_go_signals[layer] = enrich_signal_list(all_go_signals[layer])
        analyzed_count = self._persist_account_signals_from_go(
            threat_graph, all_go_signals, scope, scope_id,
            semiotic_score, causal_score, ontological_score,
            cognitive_score, anthropological_score,
            overall_score, overall_level, user_id, lang,
            generate_report, t0,
        )

        # Return the analysis record (already flushed and committed by _persist...)
        # Re-query to get the fully-populated object
        analysis = self.db.query(models.IdentityThreatAnalysis).order_by(
            models.IdentityThreatAnalysis.id.desc()
        ).first()
        return analysis

    def _persist_account_signals_from_go(
        self,
        threat_graph: dict,
        signals: dict,
        scope: str,
        scope_id: Optional[int],
        semiotic_score: int,
        causal_score: int,
        ontological_score: int,
        cognitive_score: int,
        anthropological_score: int,
        overall_score: int,
        overall_level: str,
        user_id: Optional[int],
        lang: str,
        generate_report: bool,
        t0: float,
    ) -> int:
        """
        Persist Go engine results into IdentityThreatAnalysis + ThreatAccountSignal records.

        Returns the number of nodes (accounts) analyzed.
        """
        semiotic_sigs = signals.get("semiotic") or []
        causal_sigs = signals.get("causal") or []
        ontological_sigs = signals.get("ontological") or []
        cognitive_sigs = signals.get("cognitive") or []
        anthro_sigs = signals.get("anthropological") or []
        all_signals = semiotic_sigs + causal_sigs + ontological_sigs + cognitive_sigs + anthro_sigs

        # Build snapshot_id → node metadata map from graph nodes
        snapshot_meta: dict[int, dict] = {}
        for nodedata in threat_graph.get("nodes", []):
            snap_id = nodedata.get("snapshot_id")
            if snap_id:
                snapshot_meta[snap_id] = nodedata

        # Build snapshot_id → signal list map
        sig_map: dict[int, list] = {}
        for sig in all_signals:
            snap_id = sig.get("snapshot_id")
            if snap_id:
                sig_map.setdefault(snap_id, []).append(sig)

        analyzed_count = len(threat_graph.get("nodes", []))

        # Persist analysis record
        analysis = models.IdentityThreatAnalysis(
            analysis_type="full",
            scope=scope,
            scope_id=scope_id,
            semiotic_score=semiotic_score,
            causal_score=causal_score,
            ontological_score=ontological_score,
            cognitive_score=cognitive_score,
            anthropological_score=anthropological_score,
            overall_score=overall_score,
            overall_level=overall_level,
            semiotic_signals=semiotic_sigs,
            causal_signals=causal_sigs,
            ontological_signals=ontological_sigs,
            cognitive_signals=cognitive_sigs,
            anthropological_signals=anthro_sigs,
            threat_graph=threat_graph,
            analyzed_count=analyzed_count,
            duration_ms=int((time.time() - t0) * 1000),
            created_by=user_id,
        )
        self.db.add(analysis)
        self.db.flush()  # get the ID

        # Persist per-account signals
        weights = {"critical": 100, "high": 75, "medium": 50, "low": 25, "info": 0}
        for snap_id, meta in snapshot_meta.items():
            node_sigs = sig_map.get(snap_id, [])

            semiotic_f = [s for s in semiotic_sigs if s.get("snapshot_id") == snap_id]
            causal_f = [s for s in causal_sigs if s.get("snapshot_id") == snap_id]
            ontological_f = [s for s in ontological_sigs if s.get("snapshot_id") == snap_id]
            cognitive_f = [s for s in cognitive_sigs if s.get("snapshot_id") == snap_id]
            anthro_f = [s for s in anthro_sigs if s.get("snapshot_id") == snap_id]

            all_f = semiotic_f + causal_f + ontological_f + cognitive_f + anthro_f
            account_score = int(sum(weights.get(s.get("severity", "info"), 0) for s in all_f) / max(len(all_f), 1)) if all_f else 0

            if account_score >= 80:
                account_level = "critical"
            elif account_score >= 60:
                account_level = "high"
            elif account_score >= 40:
                account_level = "medium"
            else:
                account_level = "low"

            sig_record = models.ThreatAccountSignal(
                analysis_id=analysis.id,
                snapshot_id=snap_id,
                username=meta.get("username", ""),
                asset_id=meta.get("asset_id", 0) or 0,
                asset_code=meta.get("asset_code"),
                semiotic_flags=semiotic_f,
                causal_flags=causal_f,
                ontological_flags=ontological_f,
                cognitive_flags=cognitive_f,
                anthropological_flags=anthro_f,
                account_score=account_score,
                account_level=account_level,
            )
            self.db.add(sig_record)

        self.db.commit()
        self.db.refresh(analysis)

        # Broadcast completion
        self._broadcast_if_critical(analysis, overall_score, overall_level, analyzed_count)
        self._broadcast_analysis_complete(analysis, overall_score, overall_level, analyzed_count)

        # LLM report
        if generate_report:
            report_text = _generate_llm_report(
                semiotic_score, causal_score, ontological_score,
                cognitive_score, anthropological_score,
                overall_score,
                semiotic_sigs, causal_sigs, ontological_sigs,
                cognitive_sigs, anthro_sigs,
                analyzed_count, lang, self.db,
            )
            if report_text:
                analysis.llm_report = report_text
                self.db.commit()
                self.db.refresh(analysis)

        return analyzed_count

    def _broadcast_if_critical(
        self,
        analysis: models.IdentityThreatAnalysis,
        overall_score: int,
        overall_level: str,
        analyzed_count: int,
    ) -> None:
        """
        If the overall threat level is high or critical, persist an alert and
        broadcast it to all connected SSE clients in real-time.
        Uses a fire-and-forget thread to avoid blocking the sync analysis flow.
        """
        if overall_level not in ("critical", "high"):
            return

        try:
            import asyncio
            from backend.models import AlertLevel

            def _sync_broadcast():
                """Sync wrapper — runs alert creation + async broadcast in a new loop."""
                from backend.routers.alerts import create_and_broadcast_alert
                from backend.database import SessionLocal

                db = SessionLocal()
                try:
                    level = AlertLevel.critical if overall_level == "critical" else AlertLevel.warning
                    title_zh = (
                        f"【{overall_level.upper()}】身份威胁分析完成 — "
                        f"整体评分 {overall_score}，分析 {analyzed_count} 个账号"
                    )
                    message_zh = (
                        f"分析类型: {analysis.analysis_type}，"
                        f"符号层 {analysis.semiotic_score}，因果层 {analysis.causal_score}，"
                        f"本体层 {analysis.ontological_score}，认知层 {analysis.cognitive_score}，"
                        f"人类学层 {analysis.anthropological_score}。"
                    )
                    asyncio.run(create_and_broadcast_alert(
                        db=db,
                        asset_id=0,
                        level=level,
                        title=title_zh,
                        message=message_zh,
                        job_id=None,
                    ))
                finally:
                    db.close()

            import threading
            t = threading.Thread(target=_sync_broadcast, daemon=True)
            t.start()
        except Exception:
            pass

    def _broadcast_analysis_complete(
        self,
        analysis: models.IdentityThreatAnalysis,
        overall_score: int,
        overall_level: str,
        analyzed_count: int,
    ) -> None:
        """
        Broadcast analysis completion event to all connected SSE clients.
        The /identity-threat/stream endpoint pushes this event so the frontend
        can auto-refresh the analyses list in real-time.
        """
        try:
            import asyncio
            import json

            event_data = {
                "event": "analysis_complete",
                "analysis_id": analysis.id,
                "scope": analysis.scope,
                "overall_score": overall_score,
                "overall_level": overall_level,
                "analyzed_count": analyzed_count,
                "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            }

            def _sync_broadcast():
                # Schedule broadcast in the uvicorn async event loop
                try:
                    import threading
                    # uvicorn runs on asyncio; we inject into the running loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        # Import here to avoid circular issues at module load
                        from backend.routers.identity_threat import _analysis_broadcast
                        loop.run_until_complete(_analysis_broadcast(event_data))
                    finally:
                        loop.close()
                except Exception:
                    pass

            t = threading.Thread(target=_sync_broadcast, daemon=True)
            t.start()
        except Exception:
            pass

    def _build_graph(self, scope: str, scope_id: Optional[int]) -> ThreatGraph:
        """Load account data from DB into an in-memory ThreatGraph."""
        graph = ThreatGraph()

        # Build base query
        q = self.db.query(
            models.AccountSnapshot,
            models.Asset.asset_code,
            models.Asset.ip,
            models.Asset.hostname,
        ).join(
            models.Asset, models.AccountSnapshot.asset_id == models.Asset.id
        ).outerjoin(
            models.AccountLifecycleStatus,
            models.AccountSnapshot.id == models.AccountLifecycleStatus.snapshot_id
        ).filter(
            models.AccountSnapshot.deleted_at.is_(None)
        )

        if scope == "asset" and scope_id:
            q = q.filter(models.AccountSnapshot.asset_id == scope_id)
        elif scope == "identity" and scope_id:
            q = q.join(
                models.IdentityAccount,
                models.AccountSnapshot.id == models.IdentityAccount.snapshot_id
            ).filter(models.IdentityAccount.identity_id == scope_id)

        rows = q.all()

        # Pre-build identity_id lookup map from IdentityAccount links
        identity_link_map: dict[int, int] = {}
        for link in self.db.query(models.IdentityAccount).all():
            identity_link_map[link.snapshot_id] = link.identity_id

        for snapshot, asset_code, ip, hostname in rows:
            lifecycle = ""
            if snapshot.id:
                lc = self.db.query(models.AccountLifecycleStatus).filter(
                    models.AccountLifecycleStatus.snapshot_id == snapshot.id
                ).first()
                lifecycle = lc.lifecycle_status if lc else "unknown"

            # Compute NHI type from snapshot data
            _tmp_node = ThreatNode(
                snapshot_id=snapshot.id,
                username=snapshot.username or "",
                uid_sid=snapshot.uid_sid or "",
                asset_id=snapshot.asset_id,
                asset_code=asset_code,
                ip=ip,
                hostname=hostname,
                is_admin=bool(snapshot.is_admin),
                lifecycle=lifecycle,
                last_login=snapshot.last_login,
                sudo_config=snapshot.sudo_config or {},
                raw_info=snapshot.raw_info or {},
                groups=snapshot.groups or [],
                shell=snapshot.shell,
                home_dir=snapshot.home_dir,
                account_status=snapshot.account_status or "unknown",
                identity_id=identity_link_map.get(snapshot.id),
            )
            nhi_type = _tmp_node.compute_nhi_type()

            node = ThreatNode(
                snapshot_id=snapshot.id,
                username=snapshot.username or "",
                uid_sid=snapshot.uid_sid or "",
                asset_id=snapshot.asset_id,
                asset_code=asset_code,
                ip=ip,
                hostname=hostname,
                is_admin=bool(snapshot.is_admin),
                lifecycle=lifecycle,
                last_login=snapshot.last_login,
                sudo_config=snapshot.sudo_config or {},
                raw_info=snapshot.raw_info or {},
                groups=snapshot.groups or [],
                shell=snapshot.shell,
                home_dir=snapshot.home_dir,
                account_status=snapshot.account_status or "unknown",
                identity_id=identity_link_map.get(snapshot.id),
                nhi_type=nhi_type,
            )
            graph.add_node(node)

        # Build edges
        graph.build_same_identity_edges()
        graph.build_temporal_edges()
        graph.build_permission_edges()
        graph.build_owns_edges()
        graph.build_ssh_key_edges()  # SSH key reuse across assets = lateral movement path
        graph.build_behavior_similar_edges()  # SSH key comment similarity = coordinated actor signal

        return graph

    def _score_overall(
        self,
        semiotic: int,
        causal: int,
        ontological: int,
        cognitive: int,
        anthropological: int,
    ) -> tuple[int, str]:
        """
        Compute weighted overall score.
        Weights: semiotic=0.25, causal=0.30, ontological=0.20, cognitive=0.15, anthropological=0.10
        """
        score = int(
            semiotic * 0.25 +
            causal * 0.30 +
            ontological * 0.20 +
            cognitive * 0.15 +
            anthropological * 0.10
        )

        if score >= 80:
            level = "critical"
        elif score >= 60:
            level = "high"
        elif score >= 40:
            level = "medium"
        else:
            level = "low"

        return score, level

    def rerun_engines(self, scope: str, scope_id: Optional[int], lang: str = "zh") -> dict:
        """
        Re-run the five-layer analysis engines from live DB data,
        returning signals in the requested language.
        Does NOT persist — callers decide what to do with the result.
        Scores are already stored; only signal text needs regeneration.
        """
        graph = self._build_graph(scope, scope_id)

        semiotic_score, semiotic_signals = SemioticsEngine(graph, lang).analyze()
        ontological_score, ontological_signals = ontology_analyze(graph, self.db, lang)
        causal_score, causal_signals = causal_analyze(graph, lang)
        cognitive_score, cognitive_signals = cognitive_analyze(graph, lang)
        anthropological_score, anthropological_signals = anthropology_analyze(graph, lang)

        return {
            "semiotic_signals": semiotic_signals,
            "causal_signals": causal_signals,
            "ontological_signals": ontological_signals,
            "cognitive_signals": cognitive_signals,
            "anthropological_signals": anthropological_signals,
        }

    def run_full_analysis(
        self,
        scope: str = "global",
        scope_id: Optional[int] = None,
        user_id: Optional[int] = None,
        lang: str = "zh",
        generate_report: bool = True,
    ) -> models.IdentityThreatAnalysis:
        """
        Run the full five-layer identity threat analysis.

        When USE_GO_ANALYSIS_ENGINE=1, delegates to the Go engine microservice
        (telos-engine on port 8082) for parallel 5-layer analysis.

        Args:
            scope: "global" | "asset" | "identity"
            scope_id: asset_id or identity_id (None for global)
            user_id: user who triggered the analysis
            lang: "zh" | "en" — for LLM report language
            generate_report: whether to generate LLM report

        Returns:
            The persisted IdentityThreatAnalysis record.
        """
        if os.environ.get("USE_GO_ANALYSIS_ENGINE") == "1":
            return self._run_via_go_engine(scope, scope_id, user_id, lang, generate_report)

        t0 = time.time()

        # Step 1: Build threat graph
        graph = self._build_graph(scope, scope_id)
        analyzed_count = len(graph.nodes)

        # Step 2: Layer 1 — Semiotics
        semiotic_score, semiotic_signals = SemioticsEngine(graph, lang).analyze()

        # Step 3: Layer 2 — Ontology
        ontological_score, ontological_signals = ontology_analyze(graph, self.db, lang)

        # Step 4: Layer 3 — Causal Inference
        causal_score, causal_signals = causal_analyze(graph, lang)

        # Step 5: Layer 4 — Cognitive Blindspot
        cognitive_score, cognitive_signals = cognitive_analyze(graph, lang)

        # Step 6: Layer 5 — Anthropology
        anthropological_score, anthropological_signals = anthropology_analyze(graph, lang)

        # Step 6.5: Enrich all signals with MITRE ATT&CK TTP mappings
        all_signals = (
            semiotic_signals
            + causal_signals
            + ontological_signals
            + cognitive_signals
            + anthropological_signals
        )
        enrich_signal_list(all_signals)

        # Step 7: Overall score
        overall_score, overall_level = self._score_overall(
            semiotic_score, causal_score, ontological_score,
            cognitive_score, anthropological_score,
        )

        # Step 8: Persist
        analysis = models.IdentityThreatAnalysis(
            analysis_type="full",
            scope=scope,
            scope_id=scope_id,
            semiotic_score=semiotic_score,
            causal_score=causal_score,
            ontological_score=ontological_score,
            cognitive_score=cognitive_score,
            anthropological_score=anthropological_score,
            overall_score=overall_score,
            overall_level=overall_level,
            semiotic_signals=semiotic_signals,
            causal_signals=causal_signals,
            ontological_signals=ontological_signals,
            cognitive_signals=cognitive_signals,
            anthropological_signals=anthropological_signals,
            threat_graph=graph.to_dict(),
            analyzed_count=analyzed_count,
            duration_ms=int((time.time() - t0) * 1000),
            created_by=user_id,
        )
        self.db.add(analysis)
        self.db.flush()  # get the ID

        # Persist per-account signals
        for nid, node in graph.nodes.items():
            node_signals = []
            for sig_group in [semiotic_signals, causal_signals, ontological_signals,
                               cognitive_signals, anthropological_signals]:
                for sg in sig_group:
                    if sg.get("node_id") == nid or sg.get("snapshot_id") == node.snapshot_id:
                        node_signals.append(sg)

            # Collect per-layer flags
            semiotic_flags = [s for s in semiotic_signals if s.get("node_id") == nid]
            causal_flags = [s for s in causal_signals if s.get("node_id") == nid]
            ontological_flags = [s for s in ontological_signals if s.get("node_id") == nid]
            cognitive_flags = [s for s in cognitive_signals if s.get("node_id") == nid]
            anthro_flags = [s for s in anthropological_signals if s.get("node_id") == nid]

            # Account score
            weights = {"critical": 100, "high": 75, "medium": 50, "low": 25, "info": 0}
            all_sigs = semiotic_flags + causal_flags + ontological_flags + cognitive_flags + anthro_flags
            account_score = int(sum(weights.get(s.get("severity", "info"), 0) for s in all_sigs) / max(len(all_sigs), 1))
            if not all_sigs:
                account_score = 0

            if account_score >= 80:
                account_level = "critical"
            elif account_score >= 60:
                account_level = "high"
            elif account_score >= 40:
                account_level = "medium"
            else:
                account_level = "low"

            signal = models.ThreatAccountSignal(
                analysis_id=analysis.id,
                snapshot_id=node.snapshot_id,
                username=node.username,
                asset_id=node.asset_id,
                asset_code=node.asset_code,
                semiotic_flags=semiotic_flags,
                causal_flags=causal_flags,
                ontological_flags=ontological_flags,
                cognitive_flags=cognitive_flags,
                anthropological_flags=anthro_flags,
                account_score=account_score,
                account_level=account_level,
            )
            self.db.add(signal)

        self.db.commit()
        self.db.refresh(analysis)

        # Step 8.5: Create + broadcast a real-time alert if critical
        self._broadcast_if_critical(analysis, overall_score, overall_level, analyzed_count)

        # Step 8.6: Broadcast analysis completion via SSE
        self._broadcast_analysis_complete(analysis, overall_score, overall_level, analyzed_count)

        # Step 9: LLM report (P5)
        if generate_report:
            report_text = _generate_llm_report(
                semiotic_score, causal_score, ontological_score,
                cognitive_score, anthropological_score,
                overall_score,
                semiotic_signals, causal_signals, ontological_signals,
                cognitive_signals, anthropological_signals,
                analyzed_count, lang, self.db,
            )
            if report_text:
                analysis.llm_report = report_text
                self.db.commit()
                self.db.refresh(analysis)

        return analysis
