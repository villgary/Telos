"""
Anthropology Engine — Layer 5 of Identity Threat Analysis.

Models human↔account relationships using an anthropological lens:
- TRUST_CHAIN: Which accounts are trusted bridges between organizational units
- PERMISSION_CLUSTER: Groups of accounts with overlapping privilege patterns
- IDENTITY_ISOLATION: Privileged accounts not linked to any human identity
- PERMISSION_BRIDGE: Chokepoint accounts connecting otherwise separate clusters
"""
from collections import defaultdict
from typing import Literal

from backend.services.threat_graph import ThreatGraph, ThreatNode, ThreatEdge

Lang = Literal["zh", "en"]


def _T(lang: Lang, zh: str, en: str) -> str:
    return en if lang == "en" else zh


def _get_connected_component(graph: ThreatGraph, start: str, visited: set) -> set:
    component = {start}
    queue = [start]
    while queue:
        current = queue.pop(0)
        for edge in graph.adjacency.get(current, []):
            if edge.target_id not in component:
                component.add(edge.target_id)
                queue.append(edge.target_id)
        for edge in graph.reverse_adj.get(current, []):
            if edge.source_id not in component:
                component.add(edge.source_id)
                queue.append(edge.source_id)
    return component


def _find_trust_chains(graph: ThreatGraph, lang: Lang) -> list[dict]:
    """Analyze trust chains: from a privileged account, which others are reachable?"""
    signals = []

    for nid, node in graph.nodes.items():
        if not node.is_privileged():
            continue

        visited = {nid}
        queue = [(nid, 0)]
        reachable = []

        while queue:
            current, depth = queue.pop(0)
            if depth >= 3:
                continue
            for edge in graph.adjacency.get(current, []):
                if edge.edge_type == 'permission_propagation' and edge.target_id not in visited:
                    visited.add(edge.target_id)
                    target = graph.nodes.get(edge.target_id)
                    if target:
                        reachable.append({
                            'target_id': edge.target_id,
                            'username': target.username,
                            'asset_code': target.asset_code,
                            'hops': depth + 1,
                            'weight': edge.weight,
                        })
                        queue.append((edge.target_id, depth + 1))

        if len(reachable) >= 3:
            top_targets_zh = ', '.join(
                f"{r['username']}@{r['asset_code']}({r['hops']}跳)"
                for r in reachable[:3]
            )
            top_targets_en = ', '.join(
                f"{r['username']}@{r['asset_code']}({r['hops']}h)"
                for r in reachable[:3]
            )
            signals.append({
                'type': 'trust_chain_high_risk',
                'detail': _T(lang,
                    f"账号 {node.username}@{node.asset_code} 可横向移动至 {len(reachable)} 个目标: {top_targets_zh}",
                    f"Account {node.username}@{node.asset_code} can laterally move to {len(reachable)} targets: {top_targets_en}"),
                'severity': 'high' if len(reachable) >= 5 else 'medium',
                'node_id': nid,
                'username': node.username,
                'asset_code': node.asset_code,
                'reachable_count': len(reachable),
                'reachable_targets': reachable[:5],
                'confidence': min(0.5 + len(reachable) * 0.05, 0.95),
            })

    return signals


def _find_permission_clusters(graph: ThreatGraph, lang: Lang) -> list[dict]:
    """Find clusters mixing human and service accounts with same privileges."""
    signals = []

    def perm_fingerprint(node: ThreatNode) -> tuple:
        return (
            node.is_admin,
            bool(node.sudo_config),
            tuple(sorted(node.groups or []))[:5],
            node.uid_sid,
        )

    clusters: dict = defaultdict(list)
    for nid, node in graph.nodes.items():
        clusters[perm_fingerprint(node)].append((nid, node))

    for fp, members in clusters.items():
        if len(members) < 2:
            continue

        service_count = sum(1 for _, n in members if n.is_service_account())
        human_count = len(members) - service_count

        if human_count > 0 and service_count > 0:
            svc_names_zh = ','.join(n.username for _, n in members if n.is_service_account())[:3]
            hum_names_zh = ','.join(n.username for _, n in members if not n.is_service_account())[:3]
            svc_names_en = ','.join(n.username for _, n in members if n.is_service_account())[:3]
            hum_names_en = ','.join(n.username for _, n in members if not n.is_service_account())[:3]
            signals.append({
                'type': 'permission_cluster_mix',
                'detail': _T(lang,
                    f"权限簇混合 {len(members)} 个账号: 服务账号[{svc_names_zh}] + 人类账号[{hum_names_zh}]",
                    f"Permission cluster of {len(members)} accounts mixes service [{svc_names_en}] + human [{hum_names_en}]"),
                'severity': 'medium',
                'cluster_size': len(members),
                'service_count': service_count,
                'human_count': human_count,
                'confidence': 0.65,
            })

    return signals


def _find_identity_isolation(graph: ThreatGraph, lang: Lang) -> list[dict]:
    """Find privileged accounts not linked to any human identity."""
    signals = []

    for nid, node in graph.nodes.items():
        if node.identity_id is None and node.is_privileged():
            severity = 'high' if node.is_admin else 'medium'
            signals.append({
                'type': 'identity_isolation',
                'detail': _T(lang,
                    f"特权账号 {node.username}@{node.asset_code} 未关联任何人员身份（孤立账号风险）",
                    f"Privileged account {node.username}@{node.asset_code} is not linked to any human identity (orphaned account risk)"),
                'severity': severity,
                'node_id': nid,
                'username': node.username,
                'asset_code': node.asset_code,
                'confidence': 0.75,
            })

    return signals


def _find_permission_bridges(graph: ThreatGraph, lang: Lang) -> list[dict]:
    """Find bridge accounts connecting otherwise separate permission clusters."""
    signals = []

    visited = set()
    bridges = []

    for nid in graph.nodes:
        if nid in visited:
            continue
        component = _get_connected_component(graph, nid, set())
        for n in component:
            visited.add(n)

        if len(component) >= 3:
            for cand_nid in list(component):
                node = graph.nodes.get(cand_nid)
                if node and node.is_privileged():
                    out_deg = len(graph.adjacency.get(cand_nid, []))
                    in_deg = len(graph.reverse_adj.get(cand_nid, []))
                    total_deg = out_deg + in_deg
                    if total_deg >= 3 and len(component) >= 5:
                        bridges.append({
                            'nid': cand_nid,
                            'node': node,
                            'degree': total_deg,
                            'component_size': len(component),
                        })

    bridges.sort(key=lambda x: x['degree'], reverse=True)
    for b in bridges[:5]:
        signals.append({
            'type': 'permission_bridge',
            'detail': _T(lang,
                f"特权账号 {b['node'].username}@{b['node'].asset_code} 是{b['component_size']}个账号组件中的权限桥梁（度:{b['degree']}）",
                f"Privileged account {b['node'].username}@{b['node'].asset_code} is a permission bridge in a component of {b['component_size']} accounts (degree:{b['degree']})"),
            'severity': 'medium',
            'node_id': b['nid'],
            'username': b['node'].username,
            'asset_code': b['node'].asset_code,
            'degree': b['degree'],
            'component_size': b['component_size'],
            'confidence': min(0.5 + b['degree'] * 0.05, 0.9),
        })

    return signals


def _compute_anthropology_score(signals: list[dict]) -> int:
    """Compute anthropology score (0-100)."""
    if not signals:
        return 0
    weights = {'critical': 40, 'high': 25, 'medium': 15, 'low': 5}
    total = sum(weights.get(s.get('severity', 'low'), 5) for s in signals)
    max_score = 40 * 3 + 25 * 3 + 15 * 3
    return min(int(total / max_score * 100), 100)


def analyze(graph: ThreatGraph, lang: Lang = "zh") -> tuple[int, list[dict]]:
    """
    Main entry point for Anthropology Engine.

    Args:
        graph: ThreatGraph
        lang: "zh" (default) or "en" for signal text language

    Returns:
        (anthropological_score: int 0-100, signals: list[dict])
    """
    all_signals = []
    all_signals.extend(_find_trust_chains(graph, lang))
    all_signals.extend(_find_permission_clusters(graph, lang))
    all_signals.extend(_find_identity_isolation(graph, lang))
    all_signals.extend(_find_permission_bridges(graph, lang))

    score = _compute_anthropology_score(all_signals)
    return score, all_signals
