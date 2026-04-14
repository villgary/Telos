"""
Cognitive Blindspot Engine — Layer 4 of Identity Threat Analysis.

Detects account security patterns that exploit human cognitive biases:
1. Confirmation Bias: service accounts with interactive shell / unchanged for years
2. Halo Effect: familiar names assumed trustworthy despite high privileges
3. Sunk Cost: dormant accounts retaining admin perms
4. Social Proof Anomaly: outlier permissions vs peer group
5. Normalcy Bias: privileged accounts with no recent login events

The key insight: attackers exploit what defenders DON'T look at.
"""
from collections import defaultdict
from datetime import datetime
from typing import Literal

from backend.services.threat_graph import ThreatGraph, ThreatNode

Lang = Literal["zh", "en"]


def _T(lang: Lang, zh: str, en: str) -> str:
    return en if lang == "en" else zh


def _find_confirmation_bias(graph: ThreatGraph, lang: Lang) -> list[dict]:
    """Confirmation bias: service accounts assumed safe due to inertia."""
    signals = []

    for nid, node in graph.nodes.items():
        if not node.is_service_account():
            continue

        issues_zh, issues_en = [], []

        # Interactive shell on service account
        if node.shell and node.shell not in ('/sbin/nologin', '/usr/sbin/nologin',
                                               '/bin/false', '/sbin/shutdown', 'false', 'nologin', None, ''):
            issues_zh.append(f'服务账号 {node.username}@{node.asset_code} 存在可登录shell: {node.shell}')
            issues_en.append(f'Service account {node.username}@{node.asset_code} has login shell: {node.shell}')

        # Service account with admin
        if node.is_admin:
            issues_zh.append(f'服务账号 {node.username}@{node.asset_code} 具有管理员权限（确认偏误风险）')
            issues_en.append(f'Service account {node.username}@{node.asset_code} has admin privileges (confirmation bias)')

        # Last login very old
        if node.last_login:
            days_old = (datetime.utcnow() - node.last_login).days
            if days_old > 730:
                issues_zh.append(f'服务账号 {node.username}@{node.asset_code} 超过{days_old}天未登录（可能已废弃）')
                issues_en.append(f'Service account {node.username}@{node.asset_code} has not logged in for {days_old} days (possibly abandoned)')

        # Service account with sudo_config
        if node.sudo_config:
            issues_zh.append(f'服务账号 {node.username}@{node.asset_code} 配置了sudo权限')
            issues_en.append(f'Service account {node.username}@{node.asset_code} has sudo permissions configured')

        if issues_zh:
            severity = 'high' if len(issues_zh) >= 2 else 'medium'
            signals.append({
                'type': 'confirmation_bias',
                'detail': _T(lang,
                    f"{node.username}@{node.asset_code}: " + '; '.join(issues_zh),
                    f"{node.username}@{node.asset_code}: " + '; '.join(issues_en)),
                'severity': severity,
                'node_id': nid,
                'username': node.username,
                'asset_code': node.asset_code,
                'confidence': 0.8,
            })

    return signals


def _find_halo_effect(graph: ThreatGraph, lang: Lang) -> list[dict]:
    """Halo effect: familiar names assumed trustworthy despite high privileges."""
    signals = []

    common_names = {
        'admin', 'administrator', 'root', 'user', 'guest', 'test', 'default',
        'zhangsan', 'zhangsan01', 'zhangsan02',
        'lisi', 'lisi01', 'wangwu', 'wangwu01',
        'operator', 'support', 'service', 'deploy',
    }

    for nid, node in graph.nodes.items():
        name_lower = node.username.lower()

        if node.is_admin and name_lower in common_names:
            signals.append({
                'type': 'halo_effect',
                'detail': _T(lang,
                    f"常见账号名 {node.username}@{node.asset_code} 具有管理员权限（光圈效应风险）",
                    f"Common account name '{node.username}'@{node.asset_code} has admin privileges (halo effect)"),
                'severity': 'medium',
                'node_id': nid,
                'username': node.username,
                'asset_code': node.asset_code,
                'confidence': 0.65,
            })

        if node.uid_sid in ('0', '500', '544') and name_lower != 'root':
            signals.append({
                'type': 'halo_effect',
                'detail': _T(lang,
                    f"账号 {node.username}@{node.asset_code} UID={node.uid_sid} 等同root（光圈效应风险）",
                    f"Account {node.username}@{node.asset_code} UID={node.uid_sid} is root-equivalent (halo effect)"),
                'severity': 'high',
                'node_id': nid,
                'username': node.username,
                'uid_sid': node.uid_sid,
                'asset_code': node.asset_code,
                'confidence': 0.9,
            })

    return signals


def _find_sunk_cost(graph: ThreatGraph, lang: Lang) -> list[dict]:
    """Sunk cost bias: old accounts retained despite dormancy/departure."""
    signals = []

    lifecycle_map = {
        'departed': ('离职账号', 'Departed account'),
        'dormant': ('长期未活跃账号', 'Dormant account'),
        'unknown': ('状态未知账号', 'Account with unknown status'),
    }

    for nid, node in graph.nodes.items():
        if node.lifecycle not in ('dormant', 'departed', 'unknown'):
            continue
        if not node.is_privileged():
            continue

        lc_zh, lc_en = lifecycle_map.get(node.lifecycle, ('未知状态', 'Unknown status'))
        details_zh, details_en = [], []

        if node.is_admin:
            details_zh.append('保留管理员权限')
            details_en.append('retains admin privileges')
        if node.sudo_config:
            details_zh.append('保留sudo权限')
            details_en.append('retains sudo permissions')

        severity = 'high' if node.lifecycle == 'departed' and node.is_admin else \
                   'medium' if node.lifecycle in ('dormant', 'departed') else 'low'
        signals.append({
            'type': 'sunk_cost',
            'detail': _T(lang,
                f"{lc_zh} {node.username}@{node.asset_code}（{' '.join(details_zh)}，沉默成本风险）",
                f"{lc_en} {node.username}@{node.asset_code} ({', '.join(details_en)}, sunk cost bias)"),
            'severity': severity,
            'node_id': nid,
            'username': node.username,
            'asset_code': node.asset_code,
            'lifecycle': node.lifecycle,
            'confidence': 0.85 if node.lifecycle == 'departed' else 0.7,
        })

    return signals


def _find_social_proof_anomaly(graph: ThreatGraph, lang: Lang) -> list[dict]:
    """Social proof anomaly: permissions outlier within peer group."""
    signals = []

    group_members: dict = defaultdict(list)
    for node in graph.nodes.values():
        for group in (node.groups or []):
            group_members[group].append(node)

    for group_name, members in group_members.items():
        if len(members) < 3:
            continue

        nopasswd_count = sum(
            1 for m in members
            if m.sudo_config and any(
                'nopasswd' in str(v).lower() or 'nopasswd' in str(k).lower()
                for k, v in (m.sudo_config or {}).items()
            )
        )
        nopasswd_ratio = nopasswd_count / len(members)

        for m in members:
            has_nopasswd = bool(m.sudo_config and any(
                'nopasswd' in str(v).lower() or 'nopasswd' in str(k).lower()
                for k, v in (m.sudo_config or {}).items()
            ))
            if has_nopasswd and nopasswd_ratio < 0.3:
                signals.append({
                    'type': 'social_proof_anomaly',
                    'detail': _T(lang,
                        f"账号 {m.username}@{m.asset_code} 在组 {group_name} 中少数拥有NOPASSWD权限（社会认同异常）",
                        f"Account {m.username}@{m.asset_code} is a minority in group '{group_name}' with NOPASSWD (social proof anomaly)"),
                    'severity': 'medium',
                    'node_id': m.node_id(),
                    'username': m.username,
                    'asset_code': m.asset_code,
                    'group': group_name,
                    'group_size': len(members),
                    'nopasswd_in_group': nopasswd_count,
                    'confidence': 0.7,
                })

    return signals


def _find_normalcy_bias(graph: ThreatGraph, lang: Lang) -> list[dict]:
    """Normalcy bias: privileged accounts with no login history = monitoring gap."""
    signals = []

    for nid, node in graph.nodes.items():
        if node.is_privileged() and not node.last_login:
            signals.append({
                'type': 'normalcy_bias',
                'detail': _T(lang,
                    f"特权账号 {node.username}@{node.asset_code} 无登录记录，可能处于监控盲区",
                    f"Privileged account {node.username}@{node.asset_code} has no login history, likely unmonitored"),
                'severity': 'low',
                'node_id': nid,
                'username': node.username,
                'asset_code': node.asset_code,
                'confidence': 0.55,
            })

    return signals


def _compute_cognitive_score(signals: list[dict]) -> int:
    """Compute cognitive blindspot score (0-100)."""
    if not signals:
        return 0
    weights = {'critical': 40, 'high': 25, 'medium': 15, 'low': 5}
    total = sum(weights.get(s.get('severity', 'low'), 5) for s in signals)
    max_score = 40 * 3 + 25 * 3 + 15 * 3
    return min(int(total / max_score * 100), 100)


def analyze(graph: ThreatGraph, lang: Lang = "zh") -> tuple[int, list[dict]]:
    """
    Main entry point for Cognitive Blindspot Engine.

    Args:
        graph: ThreatGraph
        lang: "zh" (default) or "en" for signal text language

    Returns:
        (cognitive_score: int 0-100, signals: list[dict])
    """
    all_signals = []
    all_signals.extend(_find_confirmation_bias(graph, lang))
    all_signals.extend(_find_halo_effect(graph, lang))
    all_signals.extend(_find_sunk_cost(graph, lang))
    all_signals.extend(_find_social_proof_anomaly(graph, lang))
    all_signals.extend(_find_normalcy_bias(graph, lang))

    score = _compute_cognitive_score(all_signals)
    return score, all_signals
