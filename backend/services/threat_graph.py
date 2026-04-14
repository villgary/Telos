"""
ThreatGraph: in-memory directed graph for Identity Threat Analysis.

Nodes are account snapshots (ThreatNode).
Edges represent relationships: permission propagation, temporal precedence,
auth chain, behavior similarity, same identity (ThreatEdge).

No external graph DB — pure Python dict + list.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from collections import defaultdict


# ─── Data classes ──────────────────────────────────────────────────────────────────

@dataclass
class ThreatNode:
    snapshot_id: int
    username: str
    uid_sid: str
    asset_id: int
    asset_code: Optional[str]
    ip: Optional[str]
    hostname: Optional[str]
    is_admin: bool
    lifecycle: str          # active / dormant / departed / unknown
    last_login: Optional[datetime]
    sudo_config: dict       # from account_snapshot.sudo_config
    raw_info: dict           # from account_snapshot.raw_info (SSH keys, etc.)
    groups: list[str]
    shell: Optional[str]
    home_dir: Optional[str]
    account_status: str      # enabled / disabled / locked / no_password / unknown
    identity_id: Optional[int]  # linked human identity
    nhi_type: str = "human"    # NHI classification: service/system/cloud/workload/cicd/application/apikey/human

    def node_id(self) -> str:
        return f"snap_{self.snapshot_id}"

    def is_service_account(self) -> bool:
        """Classify as service account by shell/homedir patterns."""
        if not self.shell:
            return True
        # Non-login shells
        if self.shell in ('/sbin/nologin', '/usr/sbin/nologin', '/bin/false', '/bin/sync', '/sbin/shutdown', '/usr/sbin/shutdown', 'false', 'nologin'):
            return True
        # Service-like homedirs
        if self.home_dir and any(p in self.home_dir for p in ('/var/', '/opt/', '/srv/', '/nonexistent', '/nonexist')):
            return True
        return False

    def is_privileged(self) -> bool:
        return self.is_admin or bool(self.sudo_config)

    def is_nhi(self) -> bool:
        """Returns True if this node is a Non-Human Identity (not a human account)."""
        return self.nhi_type != "human"

    def compute_nhi_type(self) -> str:
        """
        Classify this node's NHI type based on username, shell, homedir patterns.
        Mirrors backend.services.nhi_analyzer.NHIAnalyzer._classify_type().
        """
        import re
        username = self.username.lower()

        KNOWN_SYSTEM = frozenset({
            "root", "bin", "daemon", "adm", "sync", "shutdown", "halt",
            "mail", "news", "uucp", "operator", "games", "gopher",
            "ftp", "nfsnobody", "postgres", "mysql", "redis", "nginx",
            "apache", "httpd", "www-data", "systemd", "dbus", "polkitd",
            "sshd", "rpc", "rpcuser", "rpcbind", "nobody",
            # Oracle database accounts
            "oracle", "anonymous", "appqossys", "audsys", "dbsfwuser",
            "sys", "system", "outln", "flows_files", "apex_public_user",
            "gsmadmin", "gsmuser", "gsmroot", "orddatatype", "ordplugin",
            "si_informtn_schema", "spatial_csw_admin", "spatial_wfs_admin",
            "mddata", "mdsys", "lbacsys", "oqadmin", "oracle_ocr",
            "ctxsys", "xdb", "watershop", "dip", "oralebs",
            "scott", "hr", "oe", "sh", "pm", "bi",
        })

        CLOUD_KW = frozenset({
            "aws", "amazon", "azure", "gcp", "google", "alibaba",
            "kubernetes", "k8s", "eks", "gke", "aks",
            "iam", "role", "serviceaccount",
        })

        # AI Agent / LLM system accounts
        AI_AGENT_KW = frozenset({
            # Local LLM servers
            "ollama", "lmstudio", "lm-studio", "vllm", "text-generation-webui",
            "open-webui", "openwebui", "ollama-srv", "lLocalAI", "localai",
            # AI development tools
            "cursor", "copilot", "claude", "openai", "gemini", "groq", "deepseek",
            # AI agent frameworks
            "langchain", "autogen", "crewai", "llamaindex", "dify", "fastgpt",
            # AI inference endpoints
            "inference-server", "model-server", "tensor serving", "tritonserver",
        })

        if self.uid_sid in ("0", "1", "2", "3") or username in KNOWN_SYSTEM:
            return "system"

        if not self.shell or self.shell in ("/sbin/nologin", "/usr/sbin/nologin", "/bin/false",
                          "/bin/sync", "/sbin/shutdown", "/usr/sbin/shutdown",
                          "false", "nologin", "/usr/bin/nologin"):
            if username in ("root", "Administrator"):
                return "system"
            return "service"

        if self.home_dir and any(p in self.home_dir for p in ("/var/", "/opt/", "/srv/",
                                                                  "/nonexistent", "/nonexist")):
            return "service"

        if re.match(r'^\d+$', username):
            return "service"

        if any(k in username for k in ("runner", "actions", "pipeline", "deploy",
                                        "jenkins", "github", "gitlab", "cicd", "ci-")):
            return "cicd"

        if any(k in username for k in CLOUD_KW):
            return "cloud"

        # AI Agent / LLM system account
        if any(k in username.lower() for k in AI_AGENT_KW):
            return "ai_agent"
        if self.home_dir and any(k in self.home_dir.lower() for k in AI_AGENT_KW):
            return "ai_agent"

        # SSH key present but no human characteristics
        if self.raw_info.get("ssh_key_audit", {}).get("keys"):
            return "service"

        return "human"


@dataclass
class ThreatEdge:
    source_id: str    # node id (snapshot_id)
    target_id: str   # node id (snapshot_id)
    edge_type: str    # permission_propagation / temporal_precedence / auth_chain / behavior_similar / same_identity / owns
    weight: float     # 0.0 - 1.0

    def is_reverse_of(self, other: "ThreatEdge") -> bool:
        return self.source_id == other.target_id and self.target_id == other.source_id


# ─── ThreatGraph ──────────────────────────────────────────────────────────────────

class ThreatGraph:
    """
    In-memory directed graph for account threat analysis.
    """

    def __init__(self):
        self.nodes: dict[str, ThreatNode] = {}
        self.edges: list[ThreatEdge] = []
        self.adjacency: dict[str, list[ThreatEdge]] = defaultdict(list)   # outgoing
        self.reverse_adj: dict[str, list[ThreatEdge]] = defaultdict(list)  # incoming

    # ── Build ────────────────────────────────────────────────────────────────────

    def add_node(self, node: ThreatNode) -> None:
        nid = node.node_id()
        if nid not in self.nodes:
            self.nodes[nid] = node

    def add_edge(self, edge: ThreatEdge) -> None:
        # Avoid duplicate edges
        existing = [e for e in self.adjacency[edge.source_id]
                    if e.target_id == edge.target_id and e.edge_type == edge.edge_type]
        if not existing:
            self.edges.append(edge)
            self.adjacency[edge.source_id].append(edge)
            self.reverse_adj[edge.target_id].append(edge)

    def build_permission_edges(self) -> None:
        """
        For each admin account, add permission_propagation edges to
        accounts it can sudo to (based on sudo_config analysis).
        """
        admin_nodes = {n.node_id(): n for n in self.nodes.values() if n.is_admin}

        for admin_nid, admin in admin_nodes.items():
            # Parse sudo_config to find privilege grant patterns
            rules = admin.sudo_config or {}
            nopasswd_users = set()
            all_sudo_users = set()

            # Handle NOPASSWD: ALL users found by scanner
            if 'sudo_warnings' in rules:
                for w in rules['sudo_warnings']:
                    if isinstance(w, dict) and w.get('type') == 'nopasswd_all':
                        nopasswd_users.update(w.get('affected_users', []))

            # For each non-admin node, check if admin has access
            for nid, node in self.nodes.items():
                if nid == admin_nid:
                    continue
                if not node.is_admin:
                    # Check if admin can sudo to this user
                    weight = 0.0
                    if node.username in nopasswd_users:
                        weight = 0.9
                    elif admin.uid_sid == '0' or admin.uid_sid == '500':  # root / Administrator
                        weight = 0.8
                    if weight > 0:
                        self.add_edge(ThreatEdge(admin_nid, nid, 'permission_propagation', weight))

    def build_temporal_edges(self) -> None:
        """
        For each asset, sort snapshots by time and add edges
        from earlier to later accounts (temporal precedence).
        """
        by_asset: dict[int, list[ThreatNode]] = defaultdict(list)
        for node in self.nodes.values():
            by_asset[node.asset_id].append(node)

        for asset_id, nodes in by_asset.items():
            # Sort by snapshot_id as proxy for time order (higher id = later scan)
            sorted_nodes = sorted(nodes, key=lambda n: n.snapshot_id)
            for i in range(len(sorted_nodes) - 1):
                prev = sorted_nodes[i]
                next_ = sorted_nodes[i + 1]
                # Temporal precedence: earlier → later
                self.add_edge(ThreatEdge(
                    prev.node_id(), next_.node_id(),
                    'temporal_precedence', 0.3
                ))

    def build_same_identity_edges(self) -> None:
        """
        For nodes with the same uid_sid (跨资产同一身份),
        add same_identity edges.
        """
        by_uid: dict[str, list[ThreatNode]] = defaultdict(list)
        for node in self.nodes.values():
            if node.uid_sid:
                by_uid[node.uid_sid].append(node)

        for uid_sid, nodes in by_uid.items():
            if len(nodes) > 1:
                for i, a in enumerate(nodes):
                    for b in nodes[i + 1:]:
                        # Bidirectional same_identity edge
                        self.add_edge(ThreatEdge(a.node_id(), b.node_id(), 'same_identity', 0.95))
                        self.add_edge(ThreatEdge(b.node_id(), a.node_id(), 'same_identity', 0.95))

    def build_owns_edges(self) -> None:
        """
        Add OWNS edges from human identity → account.
        """
        identity_nodes: dict[int, list[ThreatNode]] = defaultdict(list)
        for node in self.nodes.values():
            if node.identity_id is not None:
                identity_nodes[node.identity_id].append(node)

        for identity_id, nodes in identity_nodes.items():
            for node in nodes:
                # Create a pseudo-node for the identity? No — just link to account
                # OWNS edge: identity → account (represented as edge type 'owns')
                self.add_edge(ThreatEdge(
                    f"identity_{identity_id}", node.node_id(), 'owns', 1.0
                ))

    def build_ssh_key_edges(self) -> None:
        """
        Build SSH trust edges from raw_info SSH key audit data.

        Two edge types are added:
        - ssh_key_reuse: same SSH key fingerprint appears on accounts across assets
          → strong lateral movement signal (possession of the same private key)
        - auth_chain: authorized_keys contains a from= restriction pointing to another
          asset's hostname/IP → ProxyJump / known-host trust path

        Both edge types allow BFS path traversal in get_permission_path().
        """
        from collections import defaultdict

        # 1. Fingerprint → [node_ids]
        fingerprint_map: dict[str, list[str]] = defaultdict(list)
        for nid, node in self.nodes.items():
            raw = node.raw_info or {}
            audit = raw.get("ssh_key_audit", {})
            for key in audit.get("keys", []):
                fp = key.get("fingerprint", "")
                if fp:
                    fingerprint_map[fp].append(nid)

        # Add ssh_key_reuse edges for keys shared across 2+ nodes
        for fp, node_ids in fingerprint_map.items():
            if len(node_ids) < 2:
                continue
            for i in range(len(node_ids)):
                for j in range(i + 1, len(node_ids)):
                    # Bidirectional: if I have your key, I can impersonate you
                    self.add_edge(ThreatEdge(
                        node_ids[i], node_ids[j], "ssh_key_reuse", 0.95
                    ))
                    self.add_edge(ThreatEdge(
                        node_ids[j], node_ids[i], "ssh_key_reuse", 0.95
                    ))

        # 2. authorized_keys with from= restrictions (jump-host chains)
        #    comment like "from=192.168.1.10" or "from=server-prod" in authorized_keys
        #    means this key can only be used FROM that host.
        #    Build auth_chain edges: authorized_key holder → referenced host account
        hostname_map: dict[str, list[str]] = {}  # hostname/ip → [node_ids]
        for nid, node in self.nodes.items():
            key = (node.hostname or "") or (node.ip or "")
            if key:
                hostname_map[key.lower()] = nid

        for nid, node in self.nodes.items():
            raw = node.raw_info or {}
            audit = raw.get("ssh_key_audit", {})
            for key in audit.get("keys", []):
                file_path = key.get("file", "")
                comment = key.get("comment", "")
                # Only from authorized_keys, not from private keys
                if "authorized_keys" not in file_path:
                    continue
                # Parse "from=host" pattern in comment (SSH authorized_keys syntax)
                import re
                from_hosts: list[str] = []
                # SSH: from=hostname-or-ip (RFC 4252 §8)
                from_hosts.extend(re.findall(r"from=([\w\.\-]+)", comment, re.IGNORECASE))
                # Human convention: "user@hostname" in comment line (key was copied from that host)
                from_hosts.extend(re.findall(r"@([\w\.\-]+)$", comment.strip(), re.IGNORECASE))

                for from_host in from_hosts:
                    from_host_lower = from_host.lower()
                    target_nid = hostname_map.get(from_host_lower)
                    if target_nid and target_nid != nid:
                        # The holder of this key can SSH to the target (from from_host)
                        self.add_edge(ThreatEdge(
                            nid, target_nid, "auth_chain", 0.80
                        ))

    def build_behavior_similar_edges(self, threshold: float = 0.70) -> None:
        """
        Add behavior_similar edges between accounts whose SSH key comments
        share high lexical similarity.

        Uses Jaccard similarity on normalized word sets:
        similarity = |words_a ∩ words_b| / |words_a ∪ words_b|
        Threshold: ≥0.70 (matches MITRE T1078 behavior_similar signal rationale).

        behavior_similar edges indicate coordinated credential staging — the same
        actor likely provisioned keys across assets with similar annotations.
        Bidirectional edges are added because similarity is symmetric.
        """
        # Extract comment word-sets per node
        def _words(comment: str) -> frozenset[str]:
            import re
            # Strip common noise: fingerprint prefixes, timestamps, IPs
            cleaned = re.sub(r"[\d\.\-:]+", " ", comment or "")
            return frozenset(w.lower() for w in re.findall(r"\w{3,}", cleaned))

        node_comments: dict[str, frozenset[str]] = {}
        for nid, node in self.nodes.items():
            raw = node.raw_info or {}
            audit = raw.get("ssh_key_audit", {})
            combined: frozenset[str] = frozenset()
            for key in audit.get("keys", []):
                combined = combined | _words(key.get("comment", ""))
            if combined:
                node_comments[nid] = combined

        if len(node_comments) < 2:
            return

        # Pairwise Jaccard similarity
        nids = list(node_comments.keys())
        for i in range(len(nids)):
            for j in range(i + 1, len(nids)):
                a, b = nids[i], nids[j]
                words_a = node_comments[a]
                words_b = node_comments[b]
                union = len(words_a | words_b)
                if union == 0:
                    continue
                jaccard = len(words_a & words_b) / union
                if jaccard < threshold:
                    continue
                weight = jaccard  # 0.70–1.0
                self.add_edge(ThreatEdge(a, b, "behavior_similar", weight))
                self.add_edge(ThreatEdge(b, a, "behavior_similar", weight))

    def compute_all_edges(self) -> None:
        """Convenience: compute all edge types."""
        self.build_permission_edges()
        self.build_temporal_edges()
        self.build_same_identity_edges()
        self.build_owns_edges()
        self.build_ssh_key_edges()
        self.build_behavior_similar_edges()

    # ── Queries ──────────────────────────────────────────────────────────────────

    def get_peers(self, node_id: str, threshold: float = 0.5) -> list[ThreatNode]:
        """Accounts behavior-similar to node_id (via behavior_similar edges above threshold)."""
        peers = []
        for edge in self.adjacency.get(node_id, []):
            if edge.edge_type == 'behavior_similar' and edge.weight >= threshold:
                peer = self.nodes.get(edge.target_id)
                if peer:
                    peers.append(peer)
        return peers

    # Edge types that represent actual lateral movement capability
    ATTACK_EDGE_TYPES = frozenset({"permission_propagation", "ssh_key_reuse", "auth_chain"})

    def get_permission_path(
        self, source_id: str, target_id: str,
    ) -> list[ThreatEdge]:
        """
        BFS to find a path from source to target via ATTACK_EDGE_TYPES edges
        (permission_propagation, ssh_key_reuse, auth_chain).
        Returns the list of edges forming the path (empty if no path).
        """
        if source_id == target_id:
            return []
        visited = {source_id}
        queue = [(source_id, [])]
        while queue:
            current, path = queue.pop(0)
            for edge in self.adjacency.get(current, []):
                if edge.edge_type not in self.ATTACK_EDGE_TYPES:
                    continue
                if edge.target_id == target_id:
                    return path + [edge]
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append((edge.target_id, path + [edge]))
        return []

    def get_all_reachable(
        self, source_id: str, max_hops: int = 3,
    ) -> list[tuple[list[ThreatEdge], ThreatNode]]:
        """
        BFS from source_id up to max_hops, returning all reachable nodes with their paths.
        Only traverses ATTACK_EDGE_TYPES edges.
        Returns list of (path_edges, target_node) tuples.
        """
        results: list[tuple[list[ThreatEdge], ThreatNode]] = []
        visited = {source_id}
        queue: list[tuple[str, list[ThreatEdge], int]] = [(source_id, [], 0)]
        while queue:
            current, path, depth = queue.pop(0)
            if depth >= max_hops:
                continue
            for edge in self.adjacency.get(current, []):
                if edge.edge_type not in self.ATTACK_EDGE_TYPES:
                    continue
                target = self.nodes.get(edge.target_id)
                if not target:
                    continue
                new_path = path + [edge]
                results.append((new_path, target))
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append((edge.target_id, new_path, depth + 1))
        return results

    def get_causal_chain(self, start_id: str) -> list[str]:
        """
        Follow permission_propagation edges backward (from effect to cause).
        Returns ordered list of node_ids from root cause to start_id.
        """
        chain = []
        current = start_id
        visited = set()
        while current not in visited:
            visited.add(current)
            incoming = self.reverse_adj.get(current, [])
            root_edges = [e for e in incoming if e.edge_type == 'permission_propagation']
            if not root_edges:
                break
            # Pick highest-weight root edge
            root = max(root_edges, key=lambda e: e.weight)
            chain.insert(0, root.source_id)
            current = root.source_id
        chain.append(start_id)
        return chain

    def compute_centrality(self) -> dict[str, float]:
        """
        Degree centrality: (in_degree + out_degree) / (2 * (n - 1))
        Returns node_id → centrality score.
        """
        n = len(self.nodes)
        if n <= 1:
            return {nid: 0.0 for nid in self.nodes}
        result = {}
        for nid in self.nodes:
            out_deg = len(self.adjacency.get(nid, []))
            in_deg = len(self.reverse_adj.get(nid, []))
            result[nid] = (out_deg + in_deg) / (2.0 * (n - 1))
        return result

    def to_dict(self) -> dict:
        """Serialize graph to JSON-serializable dict for storage in DB."""
        return {
            "nodes": [
                {
                    "id": nid,
                    "snapshot_id": n.snapshot_id,
                    "username": n.username,
                    "uid_sid": n.uid_sid,
                    "asset_id": n.asset_id,
                    "asset_code": n.asset_code,
                    "ip": n.ip,
                    "hostname": n.hostname,
                    "is_admin": n.is_admin,
                    "lifecycle": n.lifecycle,
                    "last_login": n.last_login.isoformat() if n.last_login else None,
                    "sudo_config": n.sudo_config or {},
                    "raw_info": n.raw_info or {},
                    "groups": n.groups or [],
                    "shell": n.shell,
                    "home_dir": n.home_dir,
                    "account_status": n.account_status,
                    "identity_id": n.identity_id,
                    "nhi_type": n.nhi_type,
                }
                for nid, n in self.nodes.items()
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "edge_type": e.edge_type,
                    "weight": e.weight,
                }
                for e in self.edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ThreatGraph":
        """
        Reconstruct a ThreatGraph from stored JSON data.

        Handles two formats:
        - Python format: {"nodes": [{id, snapshot_id, ...}], "edges": [{source, target, ...}]}
        - Go format (legacy): {"nodes": {"snap_1": {...node...}}, "edges": [...]}
          (Auto-converted to Python format internally)
        """
        # Auto-detect Go format (nodes as dict instead of list) and convert
        if data and isinstance(data.get("nodes"), dict):
            nodes_dict = data.get("nodes") or {}
            nodes_list = []
            for node_id, node_data in nodes_dict.items():
                nd = dict(node_data)
                nd["id"] = node_id
                nodes_list.append(nd)
            data = {"nodes": nodes_list, "edges": data.get("edges") or []}

        graph = cls()
        for nodedata in data.get("nodes", []):
            node = ThreatNode(
                snapshot_id=nodedata.get("snapshot_id", 0) or 0,
                username=nodedata.get("username", "") or "",
                uid_sid=nodedata.get("uid_sid", "") or "",
                asset_id=nodedata.get("asset_id", 0) or 0,
                asset_code=nodedata.get("asset_code"),
                ip=nodedata.get("ip"),
                hostname=nodedata.get("hostname"),
                is_admin=bool(nodedata.get("is_admin", False)),
                lifecycle=nodedata.get("lifecycle", "unknown") or "unknown",
                last_login=datetime.fromisoformat(nodedata["last_login"]) if nodedata.get("last_login") else None,
                sudo_config=nodedata.get("sudo_config") or {},
                raw_info=nodedata.get("raw_info") or {},
                groups=nodedata.get("groups") or [],
                shell=nodedata.get("shell"),
                home_dir=nodedata.get("home_dir"),
                account_status=nodedata.get("account_status", "unknown") or "unknown",
                identity_id=nodedata.get("identity_id"),
                nhi_type=nodedata.get("nhi_type") or "human",
            )
            graph.add_node(node)

        for edgedata in data.get("edges", []):
            edge = ThreatEdge(
                source_id=edgedata.get("source", ""),
                target_id=edgedata.get("target", ""),
                edge_type=edgedata.get("edge_type", ""),
                weight=float(edgedata.get("weight", 0.0) or 0.0),
            )
            graph.add_edge(edge)

        return graph
