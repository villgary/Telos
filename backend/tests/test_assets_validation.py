"""Asset schema validation — IPs, ports, hostnames.

The asset form used to accept any string for IP, which let a real bug
through (user typed 192.168.1.8, stored as 1921.68.1.8). These tests
prove both layers reject malformed input.
"""
import os
import sys

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from pydantic import ValidationError

from backend.schemas.assets import AssetCreate


def _base(**overrides):
    defaults = {
        "ip": "192.168.1.8",
        "port": 22,
        "credential_id": 1,
    }
    defaults.update(overrides)
    return AssetCreate(**defaults)


def test_accepts_valid_ipv4():
    a = _base(ip="10.0.0.1")
    assert a.ip == "10.0.0.1"


def test_accepts_valid_ipv6():
    a = _base(ip="2001:db8::1")
    assert a.ip == "2001:db8::1"


def test_accepts_valid_ipv4_full():
    a = _base(ip="255.255.255.255")
    assert a.ip == "255.255.255.255"


def test_rejects_malformed_ip():
    """The bug we saw today: 1921.68.1.8 was accepted because the form
    only checked `required: true` and no format. The backend now rejects
    it at the Pydantic layer (defense in depth)."""
    with pytest.raises(ValidationError) as exc:
        _base(ip="1921.68.1.8")
    assert "not a valid IPv4 or IPv6" in str(exc.value)


def test_rejects_garbage_ip():
    with pytest.raises(ValidationError):
        _base(ip="not an ip")


def test_rejects_empty_ip():
    with pytest.raises(ValidationError):
        _base(ip="")


def test_rejects_ip_with_spaces():
    with pytest.raises(ValidationError):
        _base(ip="192.168 1.8")


def test_strips_whitespace_around_ip():
    a = _base(ip="  192.168.1.8  ")
    assert a.ip == "192.168.1.8"


def test_rejects_port_below_range():
    with pytest.raises(ValidationError):
        _base(port=0)


def test_rejects_port_above_range():
    with pytest.raises(ValidationError):
        _base(port=70000)


def test_rejects_negative_port():
    with pytest.raises(ValidationError):
        _base(port=-1)


def test_accepts_port_at_boundaries():
    assert _base(port=1).port == 1
    assert _base(port=65535).port == 65535


def test_accepts_empty_hostname():
    """Hostname is optional — empty / None should be allowed."""
    a = _base(hostname="")
    assert a.hostname in (None, "")


def test_rejects_hostname_with_spaces():
    with pytest.raises(ValidationError):
        _base(hostname="my host")


def test_rejects_hostname_with_slash():
    with pytest.raises(ValidationError):
        _base(hostname="path/to/host")


def test_accepts_hostname_with_dots():
    a = _base(hostname="web-prod-01.example.com")
    assert a.hostname == "web-prod-01.example.com"
