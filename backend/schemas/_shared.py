"""Shared utilities used by schema validators."""
import re
from typing import List

_PASSWORD_SPECIAL_PATTERN = r"[!@#$%^&*(),.?\":{}|<>_+\-/\[\] ]"


def _check_password_strength(password: str, *, field_name: str = "") -> None:
    """Raise ValueError if password doesn't meet strength requirements."""
    errors = []
    if len(password) < 8:
        errors.append("至少8个字符")
    if not re.search(r"[A-Z]", password):
        errors.append("至少包含一个大写字母")
    if not re.search(r"[a-z]", password):
        errors.append("至少包含一个小写字母")
    if not re.search(r"\d", password):
        errors.append("至少包含一个数字")
    if not re.search(_PASSWORD_SPECIAL_PATTERN, password):
        errors.append("至少包含一个特殊字符")
    if errors:
        prefix = f"{field_name}不符合安全要求: " if field_name else "密码不符合安全要求: "
        raise ValueError(prefix + "; ".join(errors))


RELATION_TYPE_LABELS: dict[str, str] = {
    "hosts_vm": "承载虚拟机",
    "hosts_container": "承载容器",
    "runs_service": "运行服务",
    "network_peer": "网络互联",
    "belongs_to": "归属关系",
}
