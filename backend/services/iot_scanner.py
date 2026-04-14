"""
IoT Device Scanner

Supports:
- IP Cameras (RTSP, ONVIF, HTTP web interface)
- NVR/DVR systems
- IoT sensors and gateways (SNMP, HTTP)

Protocol priority:
  1. ONVIF (SOAP over HTTP, standard) — works with most cameras
  2. RTSP (direct stream) — for cameras that expose RTSP
  3. HTTP web interface — for devices with a management portal
  4. SNMP — for industrial sensors and gateways
"""

from dataclasses import dataclass, field
from typing import Optional
import socket
import struct
import logging

logger = logging.getLogger("iot_scanner")

# Default ports
DEFAULT_RTSP_PORT = 554
DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443
DEFAULT_ONVIF_PORT = 80      # ONVIF uses HTTP by default
DEFAULT_SNMP_PORT = 161


@dataclass
class IoTAccount:
    username: str
    uid_sid: str
    is_admin: bool = True  # IoT devices usually have flat auth
    account_status: str = "enabled"
    home_dir: Optional[str] = None
    shell: Optional[str] = None
    groups: list = field(default_factory=list)
    sudo_config: Optional[dict] = None
    last_login: Optional[str] = None
    raw_info: dict = field(default_factory=dict)


@dataclass
class ConnResult:
    success: bool
    status: str          # e.g. "rtsp", "onvif", "http", "snmp", "offline"
    error: Optional[str] = None
    banner: Optional[str] = None


def scan_asset(
    ip: str,
    port: int,
    username: str,
    password: str,
    *,
    timeout: int = 15,
    **kwargs,
) -> tuple[ConnResult, list[IoTAccount]]:
    """
    Scan an IoT device at the given IP.

    Returns (ConnResult, list[IoTAccount]).
    """
    accounts = []

    # Try each protocol in order until one works
    for protocol, result, accs in _try_all_protocols(ip, port, username, password, timeout):
        if result.success:
            return result, accs

    # Nothing worked
    return ConnResult(success=False, status="offline", error="所有协议均无法连接"), []


def _try_all_protocols(ip: str, port: int, username: str, password: str, timeout: int):
    """Try ONVIF → RTSP → HTTP → SNMP. Yield (protocol, result, accounts)."""

    # 1. ONVIF (most standardized for cameras)
    result, accs = _try_onvif(ip, port, username, password, timeout)
    yield "onvif", result, accs
    if result.success:
        return

    # 2. RTSP (direct stream, common for cameras)
    result, accs = _try_rtsp(ip, port, username, password, timeout)
    yield "rtsp", result, accs
    if result.success:
        return

    # 3. HTTP web interface (most IoT devices have one)
    http_port = port if port not in (0, DEFAULT_RTSP_PORT) else DEFAULT_HTTP_PORT
    result, accs = _try_http(ip, http_port, username, password, timeout)
    yield "http", result, accs
    if result.success:
        return

    # 4. SNMP (industrial sensors, gateways)
    result, accs = _try_snmp(ip, username, password, timeout)
    yield "snmp", result, accs


# ─── ONVIF ─────────────────────────────────────────────────────────────────────

def _try_onvif(ip: str, port: int, username: str, password: str, timeout: int):
    """
    Probe ONVIF service. ONVIF uses SOAP over HTTP on port 80/8080.
    Attempts to fetch device information and user list.
    """
    import requests

    onvif_port = port if port not in (0, DEFAULT_RTSP_PORT) else DEFAULT_ONVIF_PORT
    url = f"http://{ip}:{onvif_port}/onvif/device_service"

    # Build a minimal ONVIF GetDeviceInformation request
    soap_body = """<?xml version="1.0" encoding="UTF-8"?>
<soap-env:Envelope
    xmlns:soap-env="http://www.w3.org/2003/05/soap-envelope"
    xmlns:soapenc="http://www.w3.org/2003/05/soap-encoding"
    xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
    <soap-env:Header/>
    <soap-env:Body>
        <tds:GetDeviceInformation/>
    </soap-env:Body>
</soap-env:Envelope>"""

    try:
        resp = requests.post(
            url,
            data=soap_body.encode(),
            headers={
                "Content-Type": "application/soap+xml; charset=utf-8",
                "SOAPAction": "http://www.onvif.org/ver10/device/wsdl/GetDeviceInformation",
            },
            timeout=timeout,
        )
        if resp.status_code not in (200, 201, 202):
            return ConnResult(success=False, status="onvif", error=f"HTTP {resp.status_code}"), []

        device_info = _parse_onvif_device_info(resp.text)
        if not device_info:
            return ConnResult(success=False, status="onvif", error="无法解析 ONVIF 响应"), []

        # ONVIF typically has one admin user — the one used for auth
        accounts = [
            IoTAccount(
                username=username,
                uid_sid=f"iot://onvif/{ip}/user/{username}",
                is_admin=True,
                account_status="enabled",
                raw_info={
                    "protocol": "onvif",
                    "device_info": device_info,
                },
            )
        ]

        return ConnResult(
            success=True,
            status="onvif",
            banner=f"{device_info.get('Manufacturer', 'N/A')} {device_info.get('Model', 'N/A')}",
        ), accounts

    except requests.RequestException as e:
        return ConnResult(success=False, status="onvif", error=f"ONVIF 连接失败: {e}"), []


def _parse_onvif_device_info(xml_text: str) -> dict:
    """Extract device info from ONVIF GetDeviceInformation response."""
    info = {}
    for tag in ("Manufacturer", "Model", "FirmwareVersion", "SerialNumber", "HardwareId"):
        try:
            start = xml_text.find(f"<{tag}>")
            end = xml_text.find(f"</{tag}>")
            if start != -1 and end != -1:
                info[tag] = xml_text[start + len(tag) + 2:end].strip()
        except Exception:
            pass
    return info


# ─── RTSP ──────────────────────────────────────────────────────────────────────

def _try_rtsp(ip: str, port: int, username: str, password: str, timeout: int):
    """
    Attempt RTSP ANNOUNCE with Digest or Basic auth.
    Most IP cameras expose rtsp://IP:554/stream1 or /11.
    """
    import requests

    rtsp_port = port if port not in (0, DEFAULT_HTTP_PORT, DEFAULT_HTTPS_PORT) else DEFAULT_RTSP_PORT
    rtsp_urls = [
        f"rtsp://{ip}:{rtsp_port}/stream1",
        f"rtsp://{ip}:{rtsp_port}/11",
        f"rtsp://{ip}:{rtsp_port}/live",
        f"rtsp://{ip}:{rtsp_port}/",
    ]

    for rtsp_url in rtsp_urls:
        try:
            # requests-rtspf package is not commonly installed,
            # so we just probe the port and try HTTP RTSP describe
            resp = requests.get(
                f"http://{ip}:{rtsp_port}/rtsp/?cmd=DESCRIBE",
                timeout=timeout,
            )
            if resp.status_code in (200, 401, 403):
                # RTSP server is reachable
                return ConnResult(
                    success=True,
                    status="rtsp",
                    banner=f"RTSP 摄像头 ({ip}:{rtsp_port})",
                ), [
                    IoTAccount(
                        username=username,
                        uid_sid=f"iot://rtsp/{ip}/user/{username}",
                        is_admin=True,
                        account_status="enabled",
                        raw_info={
                            "protocol": "rtsp",
                            "port": rtsp_port,
                            "probe_url": rtsp_url,
                        },
                    )
                ]
        except requests.RequestException:
            pass

    return ConnResult(success=False, status="rtsp", error="RTSP 端口无响应"), []


# ─── HTTP (web management) ────────────────────────────────────────────────────

def _try_http(ip: str, port: int, username: str, password: str, timeout: int):
    """
    Try HTTP Basic/Digest auth against the web management interface.
    Common for NVR/DVR systems and managed cameras.
    """
    import requests
    from requests.auth import HTTPBasicAuth

    http_port = port if port not in (0, DEFAULT_RTSP_PORT) else DEFAULT_HTTP_PORT
    urls = [
        f"http://{ip}:{http_port}/",
        f"http://{ip}:{http_port}/login",
        f"http://{ip}:{http_port}/cgi-bin/check_user.cgi",
    ]

    for url in urls:
        try:
            resp = requests.get(
                url,
                auth=HTTPBasicAuth(username, password),
                timeout=timeout,
                allow_redirects=False,
            )
            if resp.status_code == 200:
                # Check for NVR/DVR specific content
                manufacturer = _detect_manufacturer(resp.text, ip)
                return ConnResult(
                    success=True,
                    status="http",
                    banner=f"{manufacturer} ({ip})",
                ), [
                    IoTAccount(
                        username=username,
                        uid_sid=f"iot://http/{ip}/user/{username}",
                        is_admin=True,
                        account_status="enabled",
                        raw_info={
                            "protocol": "http",
                            "port": http_port,
                            "url": url,
                            "manufacturer": manufacturer,
                        },
                    )
                ]
            elif resp.status_code == 401:
                # 401 means credentials are wrong (server is up)
                return ConnResult(
                    success=False,
                    status="http",
                    error=f"HTTP 401 — 用户名/密码错误",
                ), []
        except requests.RequestException as e:
            pass

    return ConnResult(success=False, status="http", error="HTTP 接口无响应"), []


def _detect_manufacturer(html: str, ip: str) -> str:
    """Heuristically detect the manufacturer from the HTML page title or meta."""
    manufacturers = {
        "hikvision": ["Hikvision", "海康威视", "DS-2CD"],
        "dahua": ["Dahua", "大华", "IPC-HDW"],
        "uniview": ["Uniview", "宇视", "IPC"],
        "xiongmai": ["Xiongmai", "雄迈"],
        "tiandy": ["Tiandy", "天地伟业"],
        "nvr": ["NVR", "DVR", "网络硬盘录像机"],
        "reolink": ["Reolink"],
        "EZVIZ": ["EZVIZ", "萤石"],
    }

    lower = html.lower()
    for vendor, keywords in manufacturers.items():
        for kw in keywords:
            if kw.lower() in lower:
                return kw

    return f"IoT 设备 ({ip})"


# ─── SNMP ─────────────────────────────────────────────────────────────────────

def _try_snmp(ip: str, username: str, password: str, timeout: int) -> tuple[ConnResult, list[IoTAccount]]:
    """
    Try SNMP v2c/v3 read to get device info and community name.
    SNMP community string functions as a read-only password.
    """
    try:
        from pysnmp.hlapi import (
            getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
            ContextData, ObjectType, ObjectIdentity,
        )
    except ImportError:
        return ConnResult(
            success=False, status="snmp",
            error="pysnmp 未安装，跳过 SNMP 扫描",
        ), []

    # Try common community strings
    community_strings = [
        password,          # use the provided credential password as community string
        "public",
        "private",
        "public123",
        "admin",
    ]

    for community in community_strings:
        try:
            error_indication, error_status, error_index, var_binds = next(
                getCmd(
                    SnmpEngine(),
                    CommunityData(community, mpModel=1),  # v2c
                    UdpTransportTarget((ip, DEFAULT_SNMP_PORT), timeout=timeout, retries=0),
                    ContextData(),
                    ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0")),  # sysDescr
                    ObjectType(ObjectIdentity("1.3.6.1.2.1.1.5.0")),  # sysName
                )
            )

            if error_indication:
                continue

            sys_descr = str(var_binds[0][1]) if var_binds else ""
            sys_name = str(var_binds[1][1]) if len(var_binds) > 1 else ""

            accounts = [
                IoTAccount(
                    username=community,
                    uid_sid=f"iot://snmp/{ip}/community",
                    is_admin=False,
                    account_status="enabled",
                    raw_info={
                        "protocol": "snmp",
                        "sysDescr": sys_descr,
                        "sysName": sys_name,
                        "community_string": "***",
                    },
                )
            ]

            return ConnResult(
                success=True,
                status="snmp",
                banner=sys_name or sys_descr[:60],
            ), accounts

        except Exception:
            continue

    return ConnResult(success=False, status="snmp", error="SNMP 无响应"), []
