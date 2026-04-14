"""
Semiotics Engine — Identity Threat Analysis Layer 1

理论基础：账号名是符号，攻击者利用符号的任意性制造混淆。

五维检测：
1. 字符替换 (Character Substitution)
2. 命名风格漂移 (Naming Style Drift)
3. 刻意普通化 (Deliberate Anonymization)
4. 符号模仿 (Symbolic Imitation)
5. 模式分类 (Account Classification: human / service / suspicious)

Signals are returned as a list of dicts for each node, plus an overall score.
"""
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Literal, Optional

from backend.services.threat_graph import ThreatGraph, ThreatNode

Lang = Literal["zh", "en"]


def _T(lang: Lang, zh: str, en: str) -> str:
    return en if lang == "en" else zh


# ─── Character substitution matrix ───────────────────────────────────────────────

# Common character substitution patterns (l->1, o->0, @->a, etc.)
SUBSTITUTIONS: list[tuple[str, str]] = [
    ('l', '1'), ('1', 'l'),
    ('o', '0'), ('0', 'o'),
    ('i', '1'), ('1', 'i'),
    ('e', '3'), ('3', 'e'),
    ('a', '@'), ('@', 'a'),
    ('s', '$'), ('$', 's'),
    ('t', '7'), ('7', 't'),
    ('g', '9'), ('9', 'g'),
    ('b', '8'), ('8', 'b'),
    ('o', 'o'),  # handled separately (o->0 covered above)
]

# Regex patterns for character substitution
_LEET_RE = re.compile(r'[lLiIoO@$]')


def _detect_char_substitution(username: str, lang: Lang = "zh") -> list[dict]:
    """Detect if username contains common character substitutions."""
    signals = []
    original = username.lower()

    de_leet = original
    de_leet = de_leet.replace('1', 'l').replace('0', 'o').replace('@', 'a')
    de_leet = de_leet.replace('3', 'e').replace('$', 's').replace('7', 't')
    de_leet = de_leet.replace('9', 'g').replace('8', 'b').replace('1', 'i')

    if de_leet != original:
        subs = []
        for i, (orig_c, sub_c) in enumerate(zip(original, de_leet)):
            if orig_c != sub_c:
                subs.append(f"{sub_c}→{orig_c}")
        signals.append({
            "type": "char_substitution",
            "detail": _T(lang,
                f"字符替换伪装: {', '.join(subs)}",
                f"Char substitution disguise: {', '.join(subs)}"),
            "original_username": username,
            "de_leet": de_leet,
            "substituted_chars": subs,
            "severity": "high" if len(subs) > 1 else "medium",
            "evidence": _T(lang,
                f"'{username}' 包含可疑字符替换，真实身份可能为 '{de_leet}'",
                f"'{username}' contains suspicious char substitution, real identity may be '{de_leet}'"),
        })
    return signals


# ─── High-frequency names ───────────────────────────────────────────────────────

COMMON_HUMAN_NAMES: set[str] = {
    # Chinese common names
    'zhangsan', 'lisi', 'wangwu', 'zhaoliu', 'sunqi',
    'zhouba', 'wujiu', 'zhengshi', 'wangyi', 'dukang',
    'xiaoming', 'xiaohong', 'laowang', 'laoli', 'laozhang',
    'admin', 'administrator', 'root', 'user', 'test', 'testuser',
    'guest', 'default', 'backup', 'service', 'svc',
    'oracle', 'mysql', 'postgres', 'postgresql', 'redis', 'mongodb',
    'nginx', 'apache', 'tomcat', 'jenkins', 'docker',
    'deploy', 'automation', 'monitor', 'backup', 'dbadmin',
}

ADMIN_KEYWORDS = {'root', 'administrator', 'admin', 'sudo', 'wheel'}


def _detect_deliberate_anonymization(username: str, is_admin: bool, groups: list[str], lang: Lang = "zh") -> list[dict]:
    """Common name + high privileges = deliberate anonymization signal."""
    signals = []
    name_lower = username.lower().strip()

    is_common = name_lower in COMMON_HUMAN_NAMES or any(
        name_lower.startswith(p) and name_lower[len(p):] in ('', '1', '2', '3', '_dev', '_prod', '_test')
        for p in ('admin', 'test', 'user', 'guest', 'backup', 'service')
    )

    if is_common and is_admin:
        priv_groups = set(g.lower() for g in groups) & ADMIN_KEYWORDS
        if priv_groups or is_admin:
            signals.append({
                "type": "deliberate_anonymization",
                "detail": _T(lang,
                    f"刻意普通化: 常见名 '{username}' 拥有高权限",
                    f"Deliberate anonymization: common name '{username}' has high privileges"),
                "severity": "critical" if priv_groups else "high",
                "evidence": _T(lang,
                    f"用户名 '{username}' 为常见词汇/名字，但关联了高权限组 {list(priv_groups)}",
                    f"Username '{username}' is common but linked to privileged groups {list(priv_groups)}"),
            })
    return signals


def _detect_symbolic_imitation(all_usernames: list[str], username: str, lang: Lang = "zh") -> list[dict]:
    """Detect imitation of existing legitimate account names."""
    signals = []
    name_lower = username.lower()

    for legit in all_usernames:
        legit_lower = legit.lower()
        if legit_lower == name_lower:
            continue

        suffixes = ('_admin', '_test', '_backup', '_svc', '_service', '_prod', '_dev', '-admin', '.admin', '__admin')
        for suf in suffixes:
            if name_lower.endswith(suf) and legit_lower == name_lower[:-len(suf)]:
                signals.append({
                    "type": "symbolic_imitation",
                    "detail": _T(lang,
                        f"符号模仿: '{username}' 模仿正规账号 '{legit}'",
                        f"Symbolic imitation: '{username}' mimics legitimate account '{legit}'"),
                    "imitated_account": legit,
                    "imitation_pattern": f"变体后缀: ...{suf}",
                    "severity": "high",
                    "evidence": _T(lang,
                        f"'{username}' 通过后缀 '{suf}' 模仿已有账号 '{legit}'",
                        f"'{username}' mimics existing account '{legit}' via suffix '{suf}'"),
                })
                break

        ratio = SequenceMatcher(None, name_lower, legit_lower).ratio()
        if ratio >= 0.75 and ratio < 1.0:
            dist = _levenshtein(name_lower, legit_lower)
            if dist <= 2:
                signals.append({
                    "type": "symbolic_imitation",
                    "detail": _T(lang,
                        f"疑似模仿/混淆: '{username}' 与 '{legit}' 编辑距离 {dist}",
                        f"Possible imitation/obfuscation: '{username}' vs '{legit}' (edit distance {dist})"),
                    "imitated_account": legit,
                    "similarity": round(ratio, 3),
                    "edit_distance": dist,
                    "severity": "medium",
                    "evidence": _T(lang,
                        f"'{username}' 与正规账号 '{legit}' 高度相似，可能是混淆或影子账号",
                        f"'{username}' highly similar to '{legit}', possible obfuscation or shadow account"),
                })
    return signals


def _detect_naming_style_drift(
    username: str,
    asset_id: int,
    all_usernames_same_asset: list[tuple[int, str]],
    lang: Lang = "zh",
) -> list[dict]:
    """
    同一资产内，同一用户的命名风格在跨时间扫描中发生漂移。
    当前 snapshot 数据没有历史扫描快照的 username，
    所以我们通过同资产其他账号来估算"正常风格"。
    """
    signals = []

    # Compute character class distribution
    def char_dist(s: str) -> dict:
        return {
            'upper': sum(1 for c in s if c.isupper()) / max(len(s), 1),
            'lower': sum(1 for c in s if c.islower()) / max(len(s), 1),
            'digit': sum(1 for c in s if c.isdigit()) / max(len(s), 1),
            'special': sum(1 for c in s if not c.isalnum()) / max(len(s), 1),
            'hyphen': s.count('-'),
            'underscore': s.count('_'),
            'dot': s.count('.'),
        }

    d = char_dist(username)
    same_asset = [u for aid, u in all_usernames_same_asset if aid == asset_id]

    # If there are other accounts on same asset, compare style
    if len(same_asset) >= 3:
        avg_dist = {
            'upper': 0.0, 'lower': 0.0, 'digit': 0.0,
            'special': 0.0, 'hyphen': 0.0, 'underscore': 0.0,
        }
        for other in same_asset:
            if other.lower() == username.lower():
                continue
            od = char_dist(other)
            for k in avg_dist:
                avg_dist[k] += abs(d[k] - od[k])
        for k in avg_dist:
            avg_dist[k] /= max(len(same_asset) - 1, 1)

        # If this account is a big outlier (>2x average) on digit or special ratio
        outlier_score = d['digit'] * 10 + d['special'] * 5
        avg_outlier = sum(avg_dist[k] for k in ('digit', 'special')) / 2
        if outlier_score > 2 and outlier_score > avg_outlier * 3:
            signals.append({
                "type": "naming_style_drift",
                "detail": _T(lang,
                    f"命名风格漂移: '{username}' 数字/特殊字符比例显著偏离同资产账号均值",
                    f"Naming style drift: '{username}' digit/special char ratio significantly deviates from same-asset average"),
                "char_distribution": d,
                "avg_deviation": avg_dist,
                "severity": "medium",
                "evidence": _T(lang,
                    f"'{username}' 的数字/特殊字符分布与其他账号显著不同",
                    f"'{username}' digit/special char distribution significantly differs from other accounts"),
            })
    return signals


# ─── Account classification ─────────────────────────────────────────────────────

def _classify_account(username: str, shell: Optional[str], home_dir: Optional[str],
                     uid_sid: str, is_admin: bool, groups: list[str]) -> str:
    """
    Classify account as: human / service / suspicious
    """
    name_lower = username.lower()
    shell_lower = (shell or '').lower()
    home_lower = (home_dir or '').lower()

    # Oracle / well-known database system accounts — always service
    _ORACLE_DB_RE = re.compile(r'^(oracle|anonymous|appqossys|audsys|dbsfwuser|sqlnet|'
                                r'sys|system|outln|dip|ctxsys|xdb|'
                                r'gsmadmin|gsmuser|gsmroot|dvsys|scott|hr|oe|sh|pm|bi|mdsys|lbacsys|'
                                r'sysbackup|dg|rac|dvf|ordsys|ordspec|orddatatype|'
                                r'spatial_csw|spatial_wfs|si_informtn|mddata|oqadmin|oracle_ocr|'
                                r'goldengate|asm[a-z]*|apex[a-z]*|febo[a-z]*|ctxhx|aq[a-z]*|'
                                r'mdsys|ordpip|ordsys|ordsvc|mgw_user|rman[a-z]*|'
                                r'dip|oem[a-z]*|odm[a-z]*)[$a-z]*$', re.IGNORECASE)
    if _ORACLE_DB_RE.match(name_lower):
        return "service"

    # Service indicators
    service_indicators = [
        shell_lower in ('/sbin/nologin', '/usr/sbin/nologin', '/bin/false',
                        '/sbin/shutdown', '/usr/sbin/shutdown', 'false', 'nologin', '/bin/sync'),
        bool(re.match(r'^/var/|^/opt/|^/srv/|^/nonexist', home_lower)),
        bool(re.match(r'^(daemon|bin|sys|adm|mail|news|ftp|www-data|mysql|postgres|redis|nginx|apache|tomcat|jenkins|docker)[\d]*$', name_lower)),
        bool(re.match(r'^[a-z]+_[a-z]+(_\d+)?$', name_lower)) and len(groups) == 0,
    ]

    # Suspicious indicators
    suspicious_indicators = [
        bool(re.search(r'[Il|]', username)) and bool(re.search(r'[lLI|0O]', username)),  # mixed l/1/I or o/0/O
        '@' in username,
        bool(re.search(r'^_', username)) or bool(re.search(r'_$', username)),  # leading/trailing underscore
        bool(re.search(r'\.sh$|\.py$|\.pl$', username)),  # looks like a script filename
    ]

    if sum(service_indicators) >= 2:
        return "service"
    if sum(suspicious_indicators) >= 2:
        return "suspicious"
    return "human"


# ─── Levenshtein distance ───────────────────────────────────────────────────────

def _levenshtein(a: str, b: str) -> int:
    """Simple Levenshtein distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(
                prev[j + 1] + 1,      # deletion
                curr[j] + 1,          # insertion
                prev[j] + (ca != cb),  # substitution
            ))
        prev = curr
    return prev[-1]


# ─── Main Engine ────────────────────────────────────────────────────────────────

class SemioticsEngine:
    """
    Five-dimension semiotics anomaly analysis engine.

    Usage:
        engine = SemioticsEngine(threat_graph)
        result = engine.analyze(lang="zh")
    """

    def __init__(self, graph: ThreatGraph, lang: Lang = "zh"):
        self.graph = graph
        self.lang = lang
        self._all_usernames: list[str] = []
        self._usernames_by_asset: list[tuple[int, str]] = []

    def _build_indexes(self):
        self._all_usernames = [n.username for n in self.graph.nodes.values()]
        self._usernames_by_asset = [(n.asset_id, n.username) for n in self.graph.nodes.values()]

    def analyze(self) -> tuple[int, list[dict]]:
        """
        Run full five-dimension analysis on the graph.

        Returns:
            (overall_score, list_of_signals_for_all_nodes)
            overall_score: 0-100 weighted score
        """
        self._build_indexes()

        all_signals: list[dict] = []
        node_scores: list[int] = []

        for nid, node in self.graph.nodes.items():
            node_signals: list[dict] = []

            # 1. Character substitution
            char_sub_signals = _detect_char_substitution(node.username, self.lang)
            node_signals.extend(char_sub_signals)

            # 2. Naming style drift
            drift_signals = _detect_naming_style_drift(
                node.username, node.asset_id, self._usernames_by_asset, self.lang
            )
            node_signals.extend(drift_signals)

            # 3. Deliberate anonymization
            anon_signals = _detect_deliberate_anonymization(
                node.username, node.is_admin, node.groups, self.lang
            )
            node_signals.extend(anon_signals)

            # 4. Symbolic imitation
            imitation_signals = _detect_symbolic_imitation(
                self._all_usernames, node.username, self.lang
            )
            node_signals.extend(imitation_signals)

            # 5. Account classification (always added as a signal)
            classification = _classify_account(
                node.username, node.shell, node.home_dir,
                node.uid_sid, node.is_admin, node.groups
            )
            node_signals.append({
                "type": "account_classification",
                "detail": _T(self.lang, f"账号分类: {classification}", f"Account type: {classification}"),
                "classification": classification,
                "severity": "info",
            })

            # Suspicious classification itself is a signal
            if classification == "suspicious":
                node_signals.append({
                    "type": "suspicious_account",
                    "detail": _T(self.lang,
                        f"可疑账号模式: '{node.username}' 存在多个可疑特征",
                        f"Suspicious account pattern: '{node.username}' has multiple anomalous features"),
                    "severity": "high",
                    "evidence": _T(self.lang,
                        f"分类为 suspicious，综合了多个异常特征",
                        f"Classified as suspicious, combined multiple anomalous features"),
                })

            all_signals.append({
                "node_id": nid,
                "snapshot_id": node.snapshot_id,
                "username": node.username,
                "asset_code": node.asset_code,
                "signals": node_signals,
            })

            # Score for this node
            score = self._score_signals(node_signals)
            node_scores.append(score)

        # Overall score: average of top-N anomalous nodes
        top_scores = sorted(node_scores, reverse=True)
        overall = int(sum(top_scores[:max(len(top_scores), 1)]) / len(node_scores)) if node_scores else 0

        return overall, all_signals

    def _score_signals(self, signals: list[dict]) -> int:
        """Compute a 0-100 score from signal severities."""
        weights = {"critical": 100, "high": 75, "medium": 50, "low": 25, "info": 0}
        total = 0
        for sig in signals:
            total += weights.get(sig.get("severity", "info"), 0)
        if not signals:
            return 0
        return min(int(total / len(signals)), 100)
