"""
Causal Inference Engine — Layer 2 of Identity Threat Analysis.

Detects causal chains and permission propagation patterns:
1. Privilege escalation paths (NOPASSWD lateral movement)
2. Dormant account privilege chains
3. Multi-hop lateral movement paths
4. Root cause attribution: causal hub identification

Uses the in-memory ThreatGraph to find propagation paths via BFS.
"""
from typing import Literal

from backend.services.threat_graph import ThreatGraph, ThreatEdge

Lang = Literal["zh", "en"]


def _T(lang: Lang, zh: str, en: str) -> str:
    return en if lang == "en" else zh


def _node_label(graph: ThreatGraph, nid: str) -> str:
    """Get display label for a node id: username@asset_code."""
    n = graph.nodes.get(nid)
    if n:
        return f"{n.username}@{n.asset_code or n.snapshot_id}"
    return nid


def _bfs_paths(graph: ThreatGraph, source_id: str, edge_types: list[str],
                max_depth: int = 5) -> list[tuple[list[str], float]]:
    """
    BFS to find all paths from source via given edge types.
    Returns list of (path_node_ids, max_weight_product) up to max_depth.
    """
    results = []
    queue = [(source_id, [source_id], 1.0)]
    depth = 0
    while queue:
        current, path, weight_prod = queue.pop(0)
        depth = len(path) - 1
        if depth >= max_depth:
            continue
        for edge in graph.adjacency.get(current, []):
            if edge.edge_type not in edge_types:
                continue
            new_weight = weight_prod * edge.weight
            new_path = path + [edge.target_id]
            results.append((new_path, new_weight))
            if edge.target_id not in path:
                queue.append((edge.target_id, new_path, new_weight))
    return results


def _find_escalation_paths(graph: ThreatGraph, lang: Lang = "zh") -> list[dict]:
    """Find privilege escalation paths via permission_propagation edges."""
    signals = []

    priv_nodes = {
        nid: n for nid, n in graph.nodes.items()
        if n.is_admin or n.is_privileged()
    }

    for priv_nid, _priv_node in priv_nodes.items():
        for nid, _node in graph.nodes.items():
            if nid == priv_nid:
                continue
            paths = _bfs_paths(graph, nid, ['permission_propagation'], 4)
            for path, weight in paths:
                if priv_nid in path:
                    end_node = graph.nodes.get(path[-1])
                    if end_node and end_node.is_privileged():
                        source = graph.nodes.get(path[0])
                        if source is None:
                            continue
                        path_len = len(path) - 1
                        severity = 'critical' if path_len >= 3 else 'high' if path_len == 2 else 'medium'
                        if source.lifecycle in ('dormant', 'departed'):
                            severity = 'critical'
                        path_str = " → ".join(_node_label(graph, p) for p in path)
                        signals.append({
                            'type': 'privilege_escalation_path',
                            'detail': _T(lang,
                                f"路径 {path_len} 跳: {path_str}",
                                f"Path ({path_len} hop): {path_str}"),
                            'severity': severity,
                            'path': path,
                            'hops': path_len,
                            'path_weight': round(weight, 3),
                            'source': path[0],
                            'target': path[-1],
                            'confidence': min(weight * 0.9, 0.99),
                        })

    return signals


def _find_causal_hubs(graph: ThreatGraph, lang: Lang = "zh") -> list[dict]:
    """Find accounts that are 'causal hubs' — high out-degree permission nodes."""
    signals = []

    out_degrees = {}
    in_degrees = {}
    for nid in graph.nodes:
        out_degrees[nid] = len([
            e for e in graph.adjacency.get(nid, [])
            if e.edge_type == 'permission_propagation'
        ])
        in_degrees[nid] = len([
            e for e in graph.reverse_adj.get(nid, [])
            if e.edge_type == 'permission_propagation'
        ])

    hub_scores = {
        nid: out_degrees.get(nid, 0) * 2 + in_degrees.get(nid, 0)
        for nid in graph.nodes
    }
    top_hubs = sorted(hub_scores.items(), key=lambda x: x[1], reverse=True)[:5]

    for nid, score in top_hubs:
        if score < 2:
            continue
        node = graph.nodes.get(nid)
        if not node:
            continue
        node_out = out_degrees.get(nid, 0)
        node_in = in_degrees.get(nid, 0)
        severity = 'high' if node_out >= 3 else 'medium' if node_out >= 2 else 'low'
        signals.append({
            'type': 'causal_hub',
            'detail': _T(lang,
                f"{node.username}@{node.asset_code} 可影响 {node_out + node_in} 个账号（出度:{node_out} 入度:{node_in}）",
                f"{node.username}@{node.asset_code} can reach {node_out + node_in} accounts (out:{node_out} in:{node_in})"),
            'severity': severity,
            'node_id': nid,
            'username': node.username,
            'asset_code': node.asset_code,
            'out_degree': node_out,
            'in_degree': node_in,
            'hub_score': score,
            'confidence': min(score * 0.1, 0.95),
        })

    return signals


def _find_dormant_privilege_chains(graph: ThreatGraph, lang: Lang = "zh") -> list[dict]:
    """Find dormant/inactive accounts retaining privileged access."""
    signals = []
    dormant = {
        nid: n for nid, n in graph.nodes.items()
        if n.lifecycle in ('dormant', 'departed', 'unknown') and n.is_privileged()
    }

    for nid, node in dormant.items():
        paths = _bfs_paths(graph, nid, ['permission_propagation'], max_depth=3)
        reachable_priv = [
            p for p, w in paths
            if graph.nodes.get(p[-1]) and graph.nodes[p[-1]].is_privileged()
        ]

        if not reachable_priv:
            continue

        priv_reachable = len(set(tuple(p) for p in reachable_priv))
        severity = 'high' if priv_reachable >= 3 else 'medium' if priv_reachable >= 1 else 'low'
        lifecycle_text = _T(lang, f"{node.lifecycle}状态",
                           f"status: {node.lifecycle}")
        signals.append({
            'type': 'dormant_privilege_chain',
            'detail': _T(lang,
                f"沉睡账号 {node.username}@{node.asset_code} 保留 {priv_reachable} 个特权目标访问权限（{lifecycle_text}）",
                f"Dormant account {node.username}@{node.asset_code} retains access to {priv_reachable} privileged targets ({lifecycle_text})"),
            'severity': severity,
            'node_id': nid,
            'username': node.username,
            'asset_code': node.asset_code,
            'lifecycle': node.lifecycle,
            'reachable_targets': priv_reachable,
            'confidence': 0.85 if node.lifecycle == 'departed' else 0.7,
        })

    return signals


def _compute_causal_score(signals: list[dict]) -> int:
    """Compute causal layer score (0-100)."""
    if not signals:
        return 0
    weights = {'critical': 40, 'high': 25, 'medium': 15, 'low': 5}
    total = sum(weights.get(s.get('severity', 'low'), 5) for s in signals)
    max_score = 40 * 3 + 25 * 3 + 15 * 3
    return min(int(total / max_score * 100), 100)


def analyze(graph: ThreatGraph, lang: Lang = "zh") -> tuple[int, list[dict]]:
    """
    Main entry point for Causal Inference Engine.

    Args:
        graph: ThreatGraph with account nodes and edges
        lang: "zh" (default) or "en" for signal text language

    Returns:
        (causal_score: int 0-100, signals: list[dict])
    """
    all_signals = []
    all_signals.extend(_find_escalation_paths(graph, lang))
    all_signals.extend(_find_causal_hubs(graph, lang))
    all_signals.extend(_find_dormant_privilege_chains(graph, lang))

    score = _compute_causal_score(all_signals)
    return score, all_signals
