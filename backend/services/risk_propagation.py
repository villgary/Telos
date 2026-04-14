"""
Risk Propagation Service — bottom-up risk aggregation across asset topology.

Risk propagates from leaf nodes (databases, containers) up to root nodes
(physical machines) via the asset relationship graph.
"""

import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from backend import models

logger = logging.getLogger("risk_propagation")

# ── Propagation coefficients ──────────────────────────────────────────────────

PROPAGATION_COEFFICIENT: dict[str, float] = {
    "hosts_container":  1.0,   # containers fully inherit host risk
    "hosts_vm":         0.9,   # VMs highly trusted
    "runs_service":     0.8,   # OS → database
    "network_peer":     0.6,   # network device cascade
    "belongs_to":       0.5,   # rack / room ownership
}

# ── Auto-alert on high risk ───────────────────────────────────────────────────

ALERT_THRESHOLDS = {
    "critical": 70,
    "warning": 45,
}


def _create_risk_alert(
    db: Session,
    asset: "models.Asset",
    score: int,
    level: str,
    factors: list[dict],
) -> None:
    """
    Create a risk alert for a high-risk asset, deduplicating within 30 minutes.
    """
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

    # Deduplicate: skip if same asset + level alert exists recently
    existing = db.query(models.Alert).filter(
        models.Alert.asset_id == asset.id,
        models.Alert.level == level,
        models.Alert.created_at >= cutoff,
    ).first()
    if existing:
        return

    top_factor = factors[0] if factors else None
    alert = models.Alert(
        asset_id=asset.id,
        level=models.AlertLevel(level),
        title=f"风险告警: {asset.asset_code}({score}分)",
        message=f"资产 {asset.asset_code}({asset.ip}) 风险评分 {score}分",
        title_key="risk.alert.title",
        title_params={"asset_code": asset.asset_code, "score": score},
        message_key="risk.alert.message",
        message_params={"asset_code": asset.asset_code, "ip": asset.ip, "score": score, "factor_name": top_factor['factor'] if top_factor else None},
        is_read=False,
    )
    db.add(alert)
    logger.info(f"Risk alert created: {asset.asset_code} score={score}")

DANGEROUS_ADMIN_NAMES = frozenset({
    "root", "administrator", "admin", "postgres",
    "mysql", "oracle", "sa", "sys", "system",
})


def compute_self_risk(
    asset: models.Asset,
    snapshots: list[models.AccountSnapshot],
    job_ids: set[int],
) -> tuple[int, list[dict]]:
    """
    Compute the self-risk score for an asset based on its account snapshots.
    Returns (score, risk_factors).
    """
    factors: list[dict] = []
    score = 0

    # Snapshot-based factors
    cutoff_90d = datetime.now(timezone.utc) - timedelta(days=90)
    cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)

    for s in snapshots:
        # 1. Unlogined admin accounts (highest severity)
        if s.is_admin and (not s.last_login or s.last_login < cutoff_90d):
            f = {"factor": "未登录管理员", "score": 15, "description": f"{s.username} 90天+未登录", "target": s.username}
            factors.append(f)
            score = min(score + 15, 100)

        # 2. Named high-privilege accounts
        uname_lower = s.username.lower()
        if s.is_admin and uname_lower in DANGEROUS_ADMIN_NAMES:
            f = {"factor": "高危管理员", "score": 10, "description": f"高危账号 {s.username}", "target": s.username}
            factors.append(f)
            score = min(score + 10, 100)

        # 3. NOPASSWD sudo rules
        sudo = s.sudo_config or {}
        if sudo.get("nopasswd_sudo") or sudo.get("nopasswd_all"):
            f = {"factor": "无密码sudo", "score": 10, "description": f"{s.username} 有 NOPASSWD ALL", "target": s.username}
            factors.append(f)
            score = min(score + 10, 100)

        # 4. Silent accounts (never logged in, non-admin)
        if s.last_login is None and not s.is_admin:
            f = {"factor": "静默账号", "score": 3, "description": f"{s.username} 从未登录", "target": s.username}
            factors.append(f)
            score = min(score + 3, 100)

        # 5. New privileged account in last 7 days
        if s.is_admin and s.last_login and cutoff_7d <= s.last_login:
            f = {"factor": "新增特权账号", "score": 5, "description": f"{s.username} 7天内新增", "target": s.username}
            factors.append(f)
            score = min(score + 5, 100)

    # 6. Asset-level factors
    if asset.status == models.AssetStatus.auth_failed:
        factors.append({"factor": "认证失败", "score": 8, "description": "扫描认证失败"})
        score = min(score + 8, 100)
    elif asset.status == models.AssetStatus.offline:
        factors.append({"factor": "离线资产", "score": 5, "description": "资产离线"})
        score = min(score + 5, 100)

    return min(score, 100), factors


def _risk_level(score: int) -> str:
    if score < 20:   return "low"
    elif score < 45: return "medium"
    elif score < 70: return "high"
    else:             return "critical"


def _build_propagation_path(
    entry_asset_id: int,
    child_map: dict[int, list[tuple]],
    profiles: dict[int, int],
) -> list[dict]:
    """
    Trace path from a high-risk leaf (entry_asset_id) to root.
    Returns list of {asset_code, ip, hostname, risk_score, relation, is_entry_point}.
    """
    # BFS from entry upward to root
    path = []
    visited = set()
    queue = [(entry_asset_id, None, False)]  # (asset_id, relation, is_entry)

    while queue:
        current_id, relation, is_entry = queue.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)

        # Look up asset info - we'll get it from caller context
        path.append({
            "asset_id": current_id,
            "relation": relation,
            "is_entry_point": is_entry,
            "risk_score": profiles.get(current_id, 0),
        })

        # Find parent (child relations where child_id == current_id)
        # This will be filled in caller

    return path


def propagate_risk(db: Session) -> dict:
    """
    Full risk propagation across all assets.
    1. Compute self-risk for each asset
    2. BFS bottom-up: propagate child scores to parents
    3. Build propagation_path for high-risk chains
    4. Save/update AssetRiskProfile records
    Returns summary dict.
    """
    all_assets = db.query(models.Asset).all()
    if not all_assets:
        return {"computed": 0, "profiles": 0}

    all_asset_ids = {a.id for a in all_assets}
    asset_map: dict[int, models.Asset] = {a.id: a for a in all_assets}

    # ── Step 1: Build relationship graph ─────────────────────────────────────
    all_rels = db.query(models.AssetRelationship).all()

    # child_map[parent_id] = list[(rel, child_asset)]
    child_map: dict[int, list[tuple]] = defaultdict(list)
    # parent_map[child_id] = (parent_asset, rel)
    parent_map: dict[int, tuple] = {}

    for rel in all_rels:
        child_map[rel.parent_id].append((rel, asset_map.get(rel.child_id)))
        parent_map[rel.child_id] = (asset_map.get(rel.parent_id), rel)

    # ── Step 2: Gather all snapshots ─────────────────────────────────────────
    job_ids = [a.last_scan_job_id for a in all_assets if a.last_scan_job_id]
    all_snaps = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.job_id.in_(job_ids)
    ).all() if job_ids else []

    snaps_by_asset: dict[int, list[models.AccountSnapshot]] = defaultdict(list)
    for s in all_snaps:
        snaps_by_asset[s.asset_id].append(s)

    # ── Step 3: Compute self-risk for every asset ─────────────────────────────
    self_scores: dict[int, int] = {}
    self_factors: dict[int, list[dict]] = {}

    for asset in all_assets:
        snaps = snaps_by_asset.get(asset.id, [])
        score, factors = compute_self_risk(asset, snaps, set(job_ids))
        self_scores[asset.id] = score
        self_factors[asset.id] = factors

    # ── Step 4: Topological sort (reverse BFS from leaves) ───────────────────
    # We need to process leaves first (assets with no children), then parents
    # Kahn's algorithm on reversed graph (child → parent)
    in_degree: dict[int, int] = {aid: 0 for aid in all_asset_ids}
    for rel in all_rels:
        in_degree[rel.parent_id] = in_degree.get(rel.parent_id, 0) + 1

    # Queue: all leaf-like nodes (no outgoing edges = parents that have no further parent)
    # Actually for Kahn's we want nodes with no incoming edges in reversed graph
    # = nodes that ARE roots (have no parent)
    root_ids = [aid for aid, deg in in_degree.items() if deg == 0]
    queue = list(root_ids)

    # Build child→parent list for propagation
    rev_adj: dict[int, list[tuple]] = defaultdict(list)  # child → [(parent_id, rel_type)]
    for rel in all_rels:
        rev_adj[rel.child_id].append((rel.parent_id, rel.relation_type.value))

    # Process from leaves up: use reverse BFS
    # Simple approach: repeatedly propagate from leaves
    propagated_scores: dict[int, int] = dict(self_scores)
    visited: set[int] = set()
    changed = True
    iterations = 0
    max_iter = len(all_asset_ids) * 2  # safety

    while changed and iterations < max_iter:
        changed = False
        iterations += 1
        for asset in all_assets:
            if asset.id in visited:
                continue
            # A node is "ready" when all its children have been visited
            children_info = child_map.get(asset.id, [])
            all_children_done = all(
                child_asset is not None and child_asset.id in visited
                for _, child_asset in children_info
            )
            if not children_info or all_children_done:
                visited.add(asset.id)
                # Propagate to parent
                parent_info = parent_map.get(asset.id)
                if parent_info:
                    parent_asset, rel = parent_info
                    coeff = PROPAGATION_COEFFICIENT.get(
                        rel.value if hasattr(rel, 'value') else str(rel), 0.8
                    )
                    contribution = min(int(propagated_scores[asset.id] * coeff), 50)
                    if contribution > 0:
                        propagated_scores[parent_asset.id] = min(
                            propagated_scores[parent_asset.id] + contribution, 100
                        )
                        changed = True

    # For nodes that didn't get processed (disconnected), just use self score
    for aid in all_asset_ids:
        if aid not in propagated_scores:
            propagated_scores[aid] = self_scores.get(aid, 0)

    # ── Step 5: Build propagation paths for high-risk chains ───────────────────
    HOTSPOT_THRESHOLD = 40  # chains with score >= 40 are hotspots

    def build_path_to_root(asset_id: int) -> list[dict]:
        """Trace from asset to root, collecting propagation nodes."""
        path = []
        current_id = asset_id
        while current_id in parent_map:
            parent_asset, rel = parent_map[current_id]
            if parent_asset is None:
                break
            path.append({
                "asset_id": parent_asset.id,
                "relation": rel.value if hasattr(rel, 'value') else str(rel),
            })
            current_id = parent_asset.id
        return path

    # ── Step 6: Save/update profiles ─────────────────────────────────────────
    now = datetime.now(timezone.utc)
    updated = 0

    for asset in all_assets:
        score = propagated_scores.get(asset.id, self_scores.get(asset.id, 0))
        factors = self_factors.get(asset.id, [])

        # Find downstream affected children count
        affected_count = 0
        for child_asset in [ca for _, ca in child_map.get(asset.id, [])]:
            if child_asset and propagated_scores.get(child_asset.id, 0) > 0:
                affected_count += 1

        # Build propagation path (leaf→root for this asset)
        path_nodes: list[dict] = []
        if asset.id in parent_map:
            chain = build_path_to_root(asset.id)
            for step in chain:
                pa = asset_map.get(step["asset_id"])
                if pa:
                    path_nodes.append({
                        "asset_code": pa.asset_code,
                        "ip": pa.ip,
                        "hostname": pa.hostname,
                        "risk_score": propagated_scores.get(pa.id, 0),
                        "relation": step["relation"],
                        "is_entry_point": False,
                    })

        profile = db.query(models.AssetRiskProfile).filter(
            models.AssetRiskProfile.asset_id == asset.id
        ).first()

        if profile:
            profile.risk_score = score
            profile.risk_level = _risk_level(score)
            profile.risk_factors = factors
            profile.affected_children = affected_count
            profile.propagation_path = path_nodes or None
            profile.computed_at = now
        else:
            profile = models.AssetRiskProfile(
                asset_id=asset.id,
                risk_score=score,
                risk_level=_risk_level(score),
                risk_factors=factors,
                affected_children=affected_count,
                propagation_path=path_nodes or None,
                computed_at=now,
            )
            db.add(profile)

        updated += 1

        # Auto-create alert for high-risk assets
        if score >= ALERT_THRESHOLDS["critical"]:
            _create_risk_alert(db, asset, score, "critical", factors)
        elif score >= ALERT_THRESHOLDS["warning"]:
            _create_risk_alert(db, asset, score, "warning", factors)

    db.commit()
    logger.info(f"Risk propagation complete: {updated} profiles updated in {iterations} iterations")
    return {"computed": iterations, "profiles": updated}
