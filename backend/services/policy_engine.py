"""
OPA/Rego Policy Engine.

Supports evaluating Rego-like policies against account snapshots.
Uses a pure-Python lightweight evaluator (no OPA binary required).

Supported Rego patterns:
  deny[msg] { input.account.is_admin == true }
  allow { not input.account.is_admin }
  deny[msg] { input.account.uid < 1000 }

Field paths supported (input.account.*):
  username, uid, is_admin, account_status, lifecycle_status,
  last_login (datetime), groups (list), sudo_config (dict),
  asset_code, asset_ip, hostname, os_type

Built-in functions:
  days_since(dt)  — days since a datetime (0 if null)
  contains(s, sub) — string contains
  startswith(s, prefix) — string starts with
  endswith(s, suffix) — string ends with
  lower(s)        — lowercase string
  in_list(val, list) — value in list
"""

import re
import operator as op
from datetime import datetime, timezone
from typing import Any, Optional, List
from backend import models


# ── Rego Evaluator ────────────────────────────────────────────────────────────

class RegoValue:
    """A value in the Rego evaluation context."""
    def __init__(self, val: Any):
        # Unwrap nested RegoValues to prevent double-wrapping
        if isinstance(val, RegoValue):
            self._val = val._val
        else:
            self._val = val

    def get(self, path: str) -> "RegoValue":
        """Get a nested field: 'a.b.c'"""
        parts = path.split(".")
        cur = self._val
        for p in parts:
            if cur is None:
                return RegoValue(None)
            if isinstance(cur, dict):
                cur = cur.get(p)
            else:
                return RegoValue(None)
        return RegoValue(cur)

    def eq(self, other: "RegoValue") -> bool:
        return self._val == other._val
    def ne(self, other: "RegoValue") -> bool:
        return self._val != other._val
    def lt(self, other: "RegoValue") -> bool:
        try:
            return float(self._val) < float(other._val)
        except (TypeError, ValueError):
            return False
    def le(self, other: "RegoValue") -> bool:
        try:
            return float(self._val) <= float(other._val)
        except (TypeError, ValueError):
            return False
    def gt(self, other: "RegoValue") -> bool:
        try:
            return float(self._val) > float(other._val)
        except (TypeError, ValueError):
            return False
    def ge(self, other: "RegoValue") -> bool:
        try:
            return float(self._val) >= float(other._val)
        except (TypeError, ValueError):
            return False

    def is_true(self) -> bool:
        return bool(self._val)

    def contains(self, sub: "RegoValue") -> bool:
        hay = self._val if isinstance(self._val, str) else getattr(self._val, '_val', self._val)
        needle = sub._val if isinstance(sub, RegoValue) else getattr(sub, '_val', sub)
        if isinstance(hay, str) and isinstance(needle, str):
            return needle in hay
        if isinstance(hay, (list, tuple)):
            return needle in hay
        return False

    def startswith(self, prefix: "RegoValue") -> bool:
        if isinstance(self._val, str) and isinstance(prefix._val, str):
            return self._val.startswith(prefix._val)
        return False

    def endswith(self, suffix: "RegoValue") -> bool:
        if isinstance(self._val, str) and isinstance(suffix._val, str):
            return self._val.endswith(suffix._val)
        return False

    def lower(self) -> "RegoValue":
        return RegoValue(self._val.lower() if isinstance(self._val, str) else self._val)

    def in_list(self, items: "RegoValue") -> bool:
        return self._val in (items._val or [])

    @staticmethod
    def days_since(dt_val: Optional["RegoValue"]) -> float:
        if dt_val is None or dt_val._val is None:
            return 9999.0
        try:
            dt = dt_val._val
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
        except (ValueError, TypeError):
            return 9999.0

    def __repr__(self):
        return f"RegoValue({self._val!r})"


# ── Policy Parser ─────────────────────────────────────────────────────────────

TOKEN_TYPES = [
    ("STRING", r'"[^"]*"'),
    ("NUMBER", r"-?\d+(?:\.\d+)?"),
    ("AND", r"\bnot\b|\band\b|\bor\b"),
    ("TRUE", r"\btrue\b"),
    ("FALSE", r"\bfalse\b"),
    ("NULL", r"\bnull\b"),
    ("IDENT", r"[a-zA-Z_][a-zA-Z0-9_]*"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("LBRACKET", r"\["),
    ("RBRACKET", r"\]"),
    ("COMMA", r","),
    ("SEMICOLON", r";"),
    ("EQ", r"=="),
    ("NE", r"!="),
    ("LE", r"<="),
    ("GE", r">="),
    ("LT", r"<"),
    ("GT", r">"),
    ("WHITESPACE", r"\s+"),
    ("DOT", r"\."),
]


class Token:
    def __init__(self, type_: str, value: str):
        self.type = type_
        self.value = value


def tokenize(code: str) -> list[Token]:
    tokens = []
    pos = 0
    while pos < len(code):
        matched = False
        for ttype, pattern in TOKEN_TYPES:
            m = re.match(pattern, code[pos:])
            if m:
                val = m.group(0)
                if ttype not in ("WHITESPACE",):
                    tokens.append(Token(ttype, val))
                pos += len(val)
                matched = True
                break
        if not matched:
            raise ValueError(f"Unexpected character at pos {pos}: {code[pos]!r}")
    return tokens


class TokenStream:
    def __init__(self, tokens: list[Token]):
        self.t = tokens
        self.i = 0

    def peek(self) -> Token:
        return self.t[self.i] if self.i < len(self.t) else Token("EOF", "")

    def consume(self, expected_type: Optional[str] = None) -> Token:
        tok = self.peek()
        if expected_type and tok.type != expected_type:
            raise ValueError(f"Expected {expected_type}, got {tok.type} ({tok.value!r})")
        self.i += 1
        return tok


def parse_rule(code: str) -> dict:
    """Parse a single Rego-like rule into a structured dict."""
    tokens = tokenize(code)
    ts = TokenStream(tokens)

    rule = {"type": "allow", "conditions": []}

    # Rule header: deny[...] or deny or allow or default deny
    tok = ts.peek()
    if tok.type == "IDENT":
        if tok.value == "deny":
            ts.consume("IDENT")
            if ts.peek().type == "LBRACKET":
                ts.consume("LBRACKET")
                # msg can be string or ident
                msg_tok = ts.peek()
                if msg_tok.type == "STRING":
                    ts.consume("STRING")
                    rule["msg_var"] = msg_tok.value[1:-1]
                else:
                    ts.consume("IDENT")
                    rule["msg_var"] = msg_tok.value
                ts.consume("RBRACKET")
            rule["type"] = "deny"
        elif tok.value == "allow":
            ts.consume("IDENT")
            rule["type"] = "allow"
        elif tok.value == "default":
            ts.consume("IDENT")
            def_tok = ts.consume("IDENT")
            rule["default_var"] = def_tok.value
            if ts.peek().value == "=":
                ts.consume("IDENT")  # skip =
                val_tok = ts.peek()
                rule["default_value"] = val_tok.value == "true"
                ts.consume(val_tok.type)

    # Skip "{" if present
    if ts.peek().type == "LBRACE":
        ts.consume("LBRACE")

    conditions: list[dict] = []
    while True:
        peek = ts.peek()
        # Exit conditions
        if peek.type in ("RBRACE", "EOF"):
            break
        # SEMICOLON separates conditions — consume and continue
        if peek.type == "SEMICOLON":
            ts.consume("SEMICOLON")
            continue
        # "not" negation
        is_not = (peek.type == "IDENT" and peek.value == "not") or (peek.type == "AND" and re.match(r"\bnot\b", peek.value))
        if is_not:
            if peek.type == "IDENT":
                ts.consume("IDENT")
            else:
                ts.consume("AND")
            cond = _parse_condition(ts)
            if cond:
                conditions.append({"type": "not", "inner": cond})
            continue
        # "and"/"or" (AND token not matched as "not") — consume and treat as separator
        if peek.type == "AND":
            ts.consume("AND")
            continue
        cond = _parse_condition(ts)
        if cond:
            conditions.append(cond)

    rule["conditions"] = conditions
    return rule


def _parse_condition(ts: TokenStream) -> Optional[dict]:
    tok = ts.peek()
    if tok.type in ("RBRACE", "EOF", "SEMICOLON"):
        return None

    # simple comparison: input.account.field op value
    # or: startswith(input.account.field, "prefix")
    if tok.type == "IDENT":
        next_tok = ts.t[ts.i + 1] if ts.i + 1 < len(ts.t) else Token("EOF", "")
        if next_tok.type == "LPAREN":
            # function call: lower(input.account.username) [possibly followed by comparison]
            func_name = tok.value
            ts.consume("IDENT")
            ts.consume("LPAREN")
            args = []
            while ts.peek().type != "RPAREN":
                arg = _parse_value(ts)
                args.append(arg)
                if ts.peek().type == "COMMA":
                    ts.consume("COMMA")
            ts.consume("RPAREN")
            # Check if followed by comparison operator (e.g. lower(input.account.username) == "root")
            cmp_tok = ts.peek()
            if cmp_tok.type in ("EQ", "NE", "LT", "GT", "LE", "GE"):
                ts.consume(cmp_tok.type)
                rhs = _parse_value(ts)
                # Return as comparison with a special "call result" field path marker
                return {
                    "type": "compare",
                    "field": f"__call__:{func_name}",
                    "args": args,
                    "op": cmp_tok.type.lower(),
                    "value": rhs,
                    "is_call_result": True,
                }
            return {"type": "call", "func": func_name, "args": args}

        # Field path: input.account.field[.field...] (but check if first ident is a built-in func)
        # e.g. "lower.input.account.username" should NOT treat "lower" as field
        # Only treat as field path if next token is DOT
        if next_tok.type == "DOT":
            parts = [tok.value]
            ts.consume("IDENT")
            while ts.peek().type == "DOT":
                ts.consume("DOT")
                part_tok = ts.consume("IDENT")
                parts.append(part_tok.value)
            field_path = ".".join(parts)

            # Comparison operator or bare field (end of expression)
            cmp_tok = ts.peek()
            if cmp_tok.type in ("EQ", "NE", "LT", "GT", "LE", "GE"):
                ts.consume(cmp_tok.type)
                rhs = _parse_value(ts)
                return {"type": "compare", "field": field_path, "op": cmp_tok.type.lower(), "value": rhs}
            elif cmp_tok.type in ("IDENT", "AND") and cmp_tok.value in ("contains", "startswith", "endswith"):
                # Bare comparison: input.account.username contains "admin" (no parens)
                # OR method call: input.account.username.contains("admin")
                # Check if followed by LPAREN (method call syntax)
                after_cmp_tok = ts.t[ts.i + 1] if ts.i + 1 < len(ts.t) else Token("EOF", "")
                if after_cmp_tok.type == "LPAREN":
                    # Method call: input.account.username.contains("admin")
                    func_name = cmp_tok.value
                    ts.consume(cmp_tok.type)
                    ts.consume("LPAREN")
                    args = [_parse_value_from_path(field_path)]
                    while ts.peek().type != "RPAREN":
                        ts.consume("COMMA")
                        args.append(_parse_value(ts))
                    ts.consume("RPAREN")
                    return {"type": "call", "func": func_name, "args": args}
                else:
                    # Bare comparison: input.account.username contains "admin"
                    func_name = cmp_tok.value
                    ts.consume(cmp_tok.type)
                    rhs = _parse_value(ts)
                    return {"type": "call", "func": func_name, "args": [_parse_value_from_path(field_path), rhs]}
            elif cmp_tok.type == "LPAREN":
                # startswith(input.account.username, "prefix") — function call at START of expression
                func_tok = ts.t[ts.i]
                func_name = func_tok.value
                ts.consume("LPAREN")
                args = [_parse_value_from_path(field_path)]
                while ts.peek().type != "RPAREN":
                    ts.consume("COMMA")
                    args.append(_parse_value(ts))
                ts.consume("RPAREN")
                return {"type": "call", "func": func_name, "args": args}
            elif cmp_tok.type in ("RBRACE", "EOF", "SEMICOLON", "AND", "IDENT"):
                return {"type": "boolean", "field": field_path}
            else:
                return None
        else:
            # Single bare identifier (built-in function reference or literal)
            ts.consume("IDENT")
            # Check if followed by comparison
            cmp_tok = ts.peek()
            if cmp_tok.type in ("EQ", "NE", "LT", "GT", "LE", "GE"):
                ts.consume(cmp_tok.type)
                rhs = _parse_value(ts)
                return {"type": "compare", "field": tok.value, "op": cmp_tok.type.lower(), "value": rhs}
            return None

    elif tok.type in ("TRUE", "FALSE"):
        ts.consume(tok.type)
        return {"type": "literal", "value": tok.value == "true"}
    elif tok.type == "AND":
        # 'and'/'or' — these are consumed here (infix ops not yet implemented)
        # 'not' arrives as AND too, but parse_rule already consumed it before calling
        ts.consume("AND")
        return None
    return None


def _parse_value(ts: TokenStream) -> Any:
    tok = ts.peek()
    if tok.type == "STRING":
        ts.consume("STRING")
        return tok.value[1:-1]  # strip quotes
    if tok.type == "NUMBER":
        ts.consume("NUMBER")
        return float(tok.value) if "." in tok.value else int(tok.value)
    if tok.type == "TRUE":
        ts.consume("TRUE")
        return True
    if tok.type == "FALSE":
        ts.consume("FALSE")
        return False
    if tok.type == "NULL":
        ts.consume("NULL")
        return None
    if tok.type == "IDENT":
        # Handle Python-style True/False as boolean literals (not field paths)
        ident_name = tok.value
        if ident_name == "True":
            ts.consume("IDENT")
            return True
        if ident_name == "False":
            ts.consume("IDENT")
            return False
        # Otherwise it's a field path
        ts.consume("IDENT")
        path_parts = [ident_name]
        while ts.peek().type == "DOT":
            ts.consume("DOT")
            part_tok = ts.consume("IDENT")
            path_parts.append(part_tok.value)
        if len(path_parts) == 1:
            return {"__path": path_parts[0]}
        return {"__path": ".".join(path_parts)}
    return None


def _parse_value_from_path(path: str) -> dict:
    return {"__path": path}


# ── Evaluator ─────────────────────────────────────────────────────────────────

# Maximum recursion depth for policy evaluation to prevent DoS via deeply nested policies
_MAX_EVAL_DEPTH = 20


def evaluate_rule(rule: dict, input_data: dict, _depth: int = 0) -> tuple[bool, str]:
    """Evaluate a parsed rule against input_data. Returns (passed, message)."""
    if _depth > _MAX_EVAL_DEPTH:
        return False, f"policy evaluation exceeded max depth ({_MAX_EVAL_DEPTH})"
    conditions = rule.get("conditions", [])
    msgs: list[str] = []

    # AND all conditions
    for cond in conditions:
        result, msg = _eval_cond(cond, input_data, _depth + 1)
        if rule["type"] == "deny":
            # deny: violation when condition evaluates to True
            if result:
                msgs.append(msg or "violated")
        else:  # allow
            if not result:
                return False, msg or "condition not satisfied"

    if rule["type"] == "deny":
        passed = len(msgs) == 0
        return passed, "; ".join(msgs) if msgs else "ok"
    else:
        return True, "allowed"


def _eval_cond(cond: dict, input_data: dict, _depth: int = 0) -> tuple[bool, str]:
    """Evaluate a single condition. Returns (passed, message)."""
    if _depth > _MAX_EVAL_DEPTH:
        return False, f"condition evaluation exceeded max depth ({_MAX_EVAL_DEPTH})"
    ctype = cond.get("type")

    if ctype == "compare":
        field = cond["field"]
        op_str = cond["op"]
        rhs_val = cond["value"]

        if cond.get("is_call_result"):
            # Function call result compared: lower(input.account.username) == "root"
            # field is "__call__:func_name", extract the func name
            func = cond["field"].split(":")[1]
            args = cond["args"]
            receiver = _resolve_arg(args[0], input_data)
            if func == "lower":
                lhs = receiver.lower()
            else:
                lhs = receiver
        else:
            # Normal field comparison
            lhs = _get_field(input_data, field)

        if isinstance(rhs_val, dict) and "__path" in rhs_val:
            rhs = _get_field(input_data, rhs_val["__path"])
        else:
            rhs = RegoValue(rhs_val)

        op_fn_map = {
            "eq": RegoValue.eq, "ne": RegoValue.ne,
            "lt": RegoValue.lt, "le": RegoValue.le,
            "gt": RegoValue.gt, "ge": RegoValue.ge,
        }
        op_fn = op_fn_map.get(op_str, RegoValue.eq)
        passed = op_fn(lhs, rhs)
        return passed, f"{field} {op_str} {rhs_val}"

    elif ctype == "boolean":
        field = cond["field"]
        val = _get_field(input_data, field)
        return val.is_true(), ""

    elif ctype == "call":
        func = cond["func"]
        args = cond["args"]
        if func in ("contains", "startswith", "endswith"):
            receiver = _resolve_arg(args[0], input_data)
            sub = _resolve_arg(args[1], input_data) if len(args) > 1 else RegoValue(None)
            fn_map = {
                "contains": lambda r, s: r.contains(s),
                "startswith": lambda r, s: r.startswith(s),
                "endswith": lambda r, s: r.endswith(s),
            }
            passed = fn_map[func](receiver, sub)
            return passed, f"{func}({receiver._val}, {sub._val})"
        elif func == "days_since":
            arg = _resolve_arg(args[0], input_data)
            days = RegoValue.days_since(arg)
            if len(args) > 1:
                threshold = _resolve_arg(args[1], input_data)
                threshold_val = float(threshold._val) if threshold._val is not None else 9999
                return days >= threshold_val, f"days_since >= {threshold_val}"
            return True, f"days_since={days:.1f}"
        elif func == "in":
            val = _resolve_arg(args[0], input_data)
            items = _resolve_arg(args[1], input_data)
            return val.in_list(items), f"{val._val} in {items._val}"
        elif func == "lower":
            receiver = _resolve_arg(args[0], input_data)
            return receiver.lower().is_true(), ""
        else:
            return True, f"unknown function {func}"

    elif ctype == "literal":
        return cond["value"], ""

    elif ctype == "not":
        inner_passed, inner_msg = _eval_cond(cond["inner"], input_data, _depth + 1)
        return not inner_passed, f"not ({inner_msg})"

    return True, ""


def _get_field(input_data: dict, path: str) -> RegoValue:
    """Get a nested field from input_data following path 'a.b.c'."""
    parts = path.split(".")
    if len(parts) > _MAX_EVAL_DEPTH:
        return RegoValue(None)
    cur = input_data
    for p in parts:
        if cur is None:
            return RegoValue(None)
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return RegoValue(None)
    return RegoValue(cur)


def _resolve_arg(arg: Any, input_data: dict) -> RegoValue:
    if isinstance(arg, dict) and "__path" in arg:
        return _get_field(input_data, arg["__path"])
    return RegoValue(arg)


# ── Full Policy Evaluation ───────────────────────────────────────────────────

def evaluate_policy(policy: models.SecurityPolicy, snapshot: models.AccountSnapshot, asset: Optional[models.Asset]) -> dict:
    """
    Evaluate a single policy against an account snapshot.
    Returns {"passed": bool, "message": str}
    """
    try:
        rule = parse_rule(policy.rego_code)
    except Exception as e:
        return {"passed": False, "message": f"Parse error: {e}"}

    # Build input context — wrapped in "input" so Rego paths like input.account.username resolve
    input_data = {
        "input": {
            "account": {
                "username": snapshot.username,
                "uid_sid": snapshot.uid_sid,
                "is_admin": snapshot.is_admin,
                "account_status": snapshot.account_status or "unknown",
                "lifecycle_status": "unknown",
                "last_login": snapshot.last_login.isoformat() if snapshot.last_login else None,
                "groups": snapshot.groups or [],
                "sudo_config": snapshot.sudo_config,
                "shell": snapshot.shell,
                "home_dir": snapshot.home_dir,
            },
            "asset": {
                "asset_code": asset.asset_code if asset else None,
                "ip": asset.ip if asset else None,
                "hostname": asset.hostname if asset else None,
                "os_type": asset.os_type.value if asset and hasattr(asset.os_type, 'value') else str(asset.os_type) if asset else None,
            },
        }
    }

    # Inject lifecycle status
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        lc_row = db.query(models.AccountLifecycleStatus).filter(
            models.AccountLifecycleStatus.snapshot_id == snapshot.id
        ).first()
        if lc_row:
            input_data["input"]["account"]["lifecycle_status"] = lc_row.lifecycle_status
    finally:
        db.close()

    passed, msg = evaluate_rule(rule, input_data)
    return {
        "passed": passed,
        "message": msg,
        "policy_id": policy.id,
        "policy_name": policy.name,
        "policy_name_key": policy.name_key,
    }


def evaluate_all_policies(snapshot: models.AccountSnapshot, asset: Optional[models.Asset], db) -> List[dict]:
    """Evaluate all enabled policies against a single account snapshot."""
    policies = db.query(models.SecurityPolicy).filter(
        models.SecurityPolicy.enabled == True
    ).all()

    results = []
    for pol in policies:
        result = evaluate_policy(pol, snapshot, asset)
        result["policy_id"] = pol.id
        result["policy_name"] = pol.name
        result["policy_name_key"] = pol.name_key
        result["severity"] = pol.severity
        results.append(result)

        # Persist result
        db.add(models.PolicyEvaluationResult(
            policy_id=pol.id,
            snapshot_id=snapshot.id,
            passed=result["passed"],
            message=result["message"],
            evaluated_at=datetime.now(timezone.utc),
        ))
    db.commit()
    return results
