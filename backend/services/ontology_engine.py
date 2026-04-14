"""
Ontology Engine — Layer 3 of Identity Threat Analysis.

Based on Saul Kripke's theory of Strict Designators and modal rigid designators:
- Same name ≠ Same entity (cross-asset same-name accounts may be different entities)
- Identity continuity requires: causal chain + temporal continuity + semantic continuity

Detects "same-name-different-entity" (SNADE) patterns.
"""
from collections import defaultdict
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from backend.services.threat_graph import ThreatGraph, ThreatNode

Lang = Literal["zh", "en"]


def _T(lang: Lang, zh: str, en: str) -> str:
    return en if lang == "en" else zh


def _levenshtein_distance(a: str, b: str) -> int:
    """Simple Levenshtein distance for similarity scoring."""
    if len(a) > 50 or len(b) > 50:
        a, b = a[:50], b[:50]
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[m][n]


def _name_similarity(name1: str, name2: str) -> float:
    if name1 == name2:
        return 1.0
    if not name1 or not name2:
        return 0.0
    max_len = max(len(name1), len(name2))
    if max_len == 0:
        return 1.0
    dist = _levenshtein_distance(name1.lower(), name2.lower())
    return max(0.0, 1.0 - dist / max_len)


def _classify_account_type(username: str) -> str:
    """Classify account name type."""
    u = username.lower()
    human_patterns = (
        'zhang', 'wang', 'li', 'liu', 'chen', 'yang', 'huang', 'zhao',
        'wu', 'xu', 'sun', 'ma', 'zhu', 'hu', 'guo', 'he', 'lin', 'luo',
        'john', 'jane', 'mike', 'james', 'alice', 'bob', 'charlie', 'david',
        'smith', 'jones', 'admin', 'root', 'test', 'guest', 'default',
    )
    service_patterns = (
        'oracle', 'mysql', 'postgres', 'nginx', 'apache', 'redis', 'mongodb',
        'jenkins', 'gitlab', 'docker', 'k8s', 'kubernetes', 'system', 'daemon',
        'bin', 'sys', 'adm', 'sync', 'shutdown', 'halt', 'mail', 'news',
        'uucp', 'operator', 'games', 'ftp', 'nobody', 'sshd', 'rpc',
        'app', 'svc', 'service', 'oms', 'agent', 'monitor',
    )
    if any(u.startswith(p) or u == p for p in human_patterns):
        if u in ('admin', 'root', 'test', 'guest', 'default'):
            return 'generic'
        return 'human'
    if any(u.startswith(p) or u == p for p in service_patterns):
        return 'service'
    if any(c.isdigit() for c in username[-3:]) and len(username) > 4:
        return 'numeric_suffix'
    if '_' in u or '-' in u:
        return 'underscore_variant'
    return 'other'


def _score_continuity(
    node_a: ThreatNode,
    node_b: ThreatNode,
    db: Session,
    lang: Lang = "zh",
) -> dict:
    """
    Score identity continuity between two same-name accounts.
    Returns both numeric scores and bilingual text.
    """
    scores = {}
    details_zh = {}
    details_en = {}

    # 1. Causal continuity
    causal_score = 0.0
    if node_a.uid_sid and node_b.uid_sid:
        if node_a.uid_sid == node_b.uid_sid:
            causal_score += 0.5
            details_zh['causal'] = f'UID/SID一致'
            details_en['causal'] = f'UID/SID match'
        else:
            details_zh['causal'] = f'UID/SID不同: {node_a.uid_sid} vs {node_b.uid_sid}'
            details_en['causal'] = f'UID/SID differs: {node_a.uid_sid} vs {node_b.uid_sid}'
    else:
        causal_score += 0.2
        details_zh['causal'] = 'UID/SID缺失'
        details_en['causal'] = 'UID/SID missing'

    if node_a.asset_id == node_b.asset_id:
        causal_score += 0.2
        details_zh['asset'] = '同一资产'
        details_en['asset'] = 'Same asset'
    else:
        causal_score += 0.1
        details_zh['asset'] = '跨资产'
        details_en['asset'] = 'Cross-asset'

    if node_a.groups and node_b.groups:
        common = set(node_a.groups) & set(node_b.groups)
        if common:
            causal_score += 0.3 * (len(common) / max(len(node_a.groups), len(node_b.groups)))
            details_zh['groups'] = f'共享组: {list(common)[:3]}'
            details_en['groups'] = f'Shared groups: {list(common)[:3]}'

    scores['causal'] = min(causal_score, 1.0)

    # 2. Temporal continuity
    temporal_score = 0.5
    if node_a.last_login and node_b.last_login:
        delta = abs((node_a.last_login - node_b.last_login).days)
        if delta <= 7:
            temporal_score = 0.8
            details_zh['temporal'] = f'最后登录时间相近（{delta}天）'
            details_en['temporal'] = f'Last login close ({delta}d apart)'
        elif delta <= 90:
            temporal_score = 0.5
            details_zh['temporal'] = f'最后登录间隔{delta}天'
            details_en['temporal'] = f'Last login {delta}d apart'
        else:
            temporal_score = 0.3
            details_zh['temporal'] = f'最后登录间隔{delta}天（长间隔）'
            details_en['temporal'] = f'Last login {delta}d apart (long gap)'

    from backend import models
    try:
        deleted = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.username == node_a.username,
            models.AccountSnapshot.asset_id == node_a.asset_id,
            models.AccountSnapshot.deleted_at.isnot(None),
        ).order_by(models.AccountSnapshot.deleted_at.desc()).first()
        if deleted and deleted.deleted_at:
            gap_days = (datetime.utcnow() - deleted.deleted_at.replace(tzinfo=None)).days
            if gap_days <= 90:
                temporal_score = max(temporal_score, 0.6)
                details_zh['temporal'] = f'旧账号删除后{gap_days}天内新建同名账号'
                details_en['temporal'] = f'New same-name account created within {gap_days}d of deletion'
    except Exception:
        pass

    scores['temporal'] = min(temporal_score, 1.0)

    # 3. Semantic continuity
    name_sim = _name_similarity(node_a.username, node_b.username)
    type_a = _classify_account_type(node_a.username)
    type_b = _classify_account_type(node_b.username)
    type_match = type_a == type_b
    semantic_score = name_sim * 0.7 + (0.3 if type_match else 0.0)
    scores['semantic'] = min(semantic_score, 1.0)
    details_zh['semantic'] = f'命名相似度{name_sim:.0%}, 类型:{type_a}/{type_b}'
    details_en['semantic'] = f'Name similarity {name_sim:.0%}, types:{type_a}/{type_b}'

    # 4. Attribute inheritance
    attr_score = 0.5
    if node_a.is_admin != node_b.is_admin:
        if node_b.is_admin and not node_a.is_admin:
            attr_score = 0.3
            details_zh['attr'] = '新账号权限提升'
            details_en['attr'] = 'New account has elevated privileges'
        else:
            attr_score = 0.4
            details_zh['attr'] = '权限配置变化'
            details_en['attr'] = 'Privilege config changed'
    else:
        attr_score = 0.7
        details_zh['attr'] = '权限一致'
        details_en['attr'] = 'Privileges consistent'

    if node_a.sudo_config != node_b.sudo_config:
        attr_score *= 0.8
        details_zh['attr'] += ', sudo配置变化'
        details_en['attr'] += ', sudo config changed'

    scores['attribute'] = min(attr_score, 1.0)

    # Overall
    overall = (
        scores['causal'] * 0.40 +
        scores['temporal'] * 0.30 +
        scores['semantic'] * 0.15 +
        scores['attribute'] * 0.15
    )

    # Bilingual evidence string
    details_combined_zh = '; '.join(f"{k}: {v}" for k, v in details_zh.items())
    details_combined_en = '; '.join(f"{k}: {v}" for k, v in details_en.items())

    return {
        'overall': overall,
        'causal': scores['causal'],
        'temporal': scores['temporal'],
        'semantic': scores['semantic'],
        'attribute': scores['attribute'],
        'evidence_zh': details_combined_zh,
        'evidence_en': details_combined_en,
    }


def _find_snade_pairs(graph: ThreatGraph, db: Session, lang: Lang) -> list[dict]:
    """Find Same-Name-Different-Entity (SNADE) account pairs."""
    by_username: dict = defaultdict(list)
    for node in graph.nodes.values():
        by_username[node.username.lower()].append(node)

    signals = []

    for username_lower, nodes in by_username.items():
        if len(nodes) < 2:
            continue
        for i, node_a in enumerate(nodes):
            for node_b in nodes[i + 1:]:
                if node_a.asset_id == node_b.asset_id:
                    continue

                continuity = _score_continuity(node_a, node_b, db, lang)
                continuity_score = continuity['overall']

                if continuity_score < 0.5:
                    severity = 'critical' if continuity_score < 0.3 else 'high' if continuity_score < 0.4 else 'medium'
                    detail_zh = (
                        f"同名账号 {node_a.username} 在 {node_a.asset_code} 和 {node_b.asset_code} "
                        f"可能非同一人（连续性评分 {continuity_score:.0%}）"
                    )
                    detail_en = (
                        f"Same-name accounts '{node_a.username}' at {node_a.asset_code} and "
                        f"{node_b.asset_code} may be different entities (continuity: {continuity_score:.0%})"
                    )
                    signals.append({
                        'type': 'same_name_different_entity',
                        'detail': _T(lang, detail_zh, detail_en),
                        'severity': severity,
                        'username': node_a.username,
                        'asset_a': node_a.asset_code or f"#{node_a.asset_id}",
                        'asset_b': node_b.asset_code or f"#{node_b.asset_id}",
                        'continuity_score': round(continuity_score, 3),
                        'causal_score': round(continuity['causal'], 2),
                        'temporal_score': round(continuity['temporal'], 2),
                        'semantic_score': round(continuity['semantic'], 2),
                        'uid_a': node_a.uid_sid,
                        'uid_b': node_b.uid_sid,
                        'is_admin_a': node_a.is_admin,
                        'is_admin_b': node_b.is_admin,
                        'evidence': _T(lang, continuity['evidence_zh'], continuity['evidence_en']),
                        'confidence': continuity_score,
                    })

    return signals


def _find_role_confusion(graph: ThreatGraph, lang: Lang) -> list[dict]:
    """Find accounts where naming implies a different role than privileges."""
    signals = []
    by_username: dict = defaultdict(list)
    for node in graph.nodes.values():
        by_username[node.username.lower()].append(node)

    for username_lower, nodes in by_username.items():
        if len(nodes) < 2:
            continue
        for node in nodes:
            acct_type = _classify_account_type(node.username)

            if acct_type == 'human' and node.is_admin:
                signals.append({
                    'type': 'role_confusion',
                    'detail': _T(lang,
                        f"人类名账号 {node.username}@{node.asset_code} 具有管理员权限（命名与权限不匹配）",
                        f"Human-named account '{node.username}'@{node.asset_code} has admin privileges (role mismatch)"),
                    'severity': 'medium',
                    'node_id': node.node_id(),
                    'username': node.username,
                    'account_type': acct_type,
                    'confidence': 0.6,
                })

            if acct_type not in ('service', 'other') and node.sudo_config:
                signals.append({
                    'type': 'role_confusion',
                    'detail': _T(lang,
                        f"非服务账号 {node.username}@{node.asset_code} 配置了sudo权限",
                        f"Non-service account {node.username}@{node.asset_code} has sudo configured"),
                    'severity': 'low',
                    'node_id': node.node_id(),
                    'username': node.username,
                    'account_type': acct_type,
                    'confidence': 0.5,
                })

    return signals


def _compute_ontology_score(signals: list[dict]) -> int:
    if not signals:
        return 0
    weights = {'critical': 40, 'high': 25, 'medium': 15, 'low': 5}
    total = sum(weights.get(s.get('severity', 'low'), 5) for s in signals)
    max_score = 40 * 3 + 25 * 3 + 15 * 3
    return min(int(total / max_score * 100), 100)


def _find_orphan_accounts(graph: ThreatGraph, db: Session, lang: Lang) -> list[dict]:
    """
    Find accounts with no linked human identity but are active/departed.
    These are potential shadow accounts — they exist in the system but have
    no owner record, making them invisible to normal review processes.
    """
    from sqlalchemy import select
    from backend import models

    # Get all snapshot_ids that have a human identity link
    linked_ids = {
        node.snapshot_id
        for node in graph.nodes.values()
        if node.identity_id is not None
    }

    signals = []
    for node in graph.nodes.values():
        if node.snapshot_id in linked_ids:
            continue
        # Skip clearly service accounts
        if node.is_service_account():
            continue
        # Skip deleted
        if node.account_status in ('deleted', 'removed'):
            continue

        severity = 'high'
        detail_zh = (
            f"账号「{node.username}」(@ {node.ip or node.hostname or f'资产{node.asset_id}'}) "
            f"无归属人员身份，可能为影子账号，建议关联到 HR 身份记录"
        )
        detail_en = (
            f"Account '{node.username}' (@ {node.ip or node.hostname or f'asset#{node.asset_id}'}) "
            f"has no linked human identity — possible shadow account"
        )
        signals.append({
            'type': 'orphan_account',
            'detail': _T(lang, detail_zh, detail_en),
            'severity': severity,
            'username': node.username,
            'asset': node.ip or node.hostname or f"#{node.asset_id}",
            'account_status': node.account_status,
        })

    return signals


def analyze(graph: ThreatGraph, db: Session, lang: Lang = "zh") -> tuple[int, list[dict]]:
    """
    Main entry point for Ontology Engine.

    Args:
        graph: ThreatGraph
        db: SQLAlchemy session
        lang: "zh" (default) or "en" for signal text language

    Returns:
        (ontological_score: int 0-100, signals: list[dict])
    """
    all_signals = []
    all_signals.extend(_find_snade_pairs(graph, db, lang))
    all_signals.extend(_find_role_confusion(graph, lang))
    all_signals.extend(_find_orphan_accounts(graph, db, lang))

    score = _compute_ontology_score(all_signals)
    return score, all_signals
