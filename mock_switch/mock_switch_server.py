#!/usr/bin/env python3
"""
Mock Network Switch SSH Server using paramiko.
Simulates Cisco IOS, Huawei VRP, H3C Comware for testing account discovery.
"""

import os
import socket
import threading
import paramiko
from paramiko import ServerInterface, AUTH_SUCCESSFUL, OPEN_SUCCEEDED, AUTH_FAILED, OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

# ──────────────────────────────────────────────
#  Command outputs per vendor
# ──────────────────────────────────────────────

CISCO = {
    "name": "cisco",
    "admin_pass": "CiscoPass123",
    "prompt": b"CiscoSwitch> ",
    "show users": b"""\
    Line       User                   Host(s)              Idle   Location
   0 con 0     idle                      00:00:00
*  2 vty 0     admin      192.168.1.100     00:05:23  192.168.1.100
   3 vty 1     operator   192.168.1.101     00:12:45  192.168.1.101
   4 vty 2     guest      192.168.1.102     00:00:10  192.168.1.102
""",
    "show privilege": b"Current privilege level is 15\n",
    "show running-config | include ^username": b"""\
username admin privilege 15 secret 5 $1$mERr$hx5rMWvfYLPQowzC1B.v0
username operator privilege 5 secret 5 $1$sOMe$H2.pMGJQi2F1xQ0
username netops privilege 10 secret 5 $1$Salt.$xQbw4cIJIHqb3xLvHyj9k0
username guest privilege 1 secret 5 $1$Salt.$g4Es2xLPHV1pWqK9x0
username monitoring privilege 3 secret 5 $1$Salt.$aBcDeFgHiJkLmNoPqR
""",
}

HUAWEI = {
    "name": "huawei",
    "admin_pass": "HuaweiPass123",
    "prompt": b"<Huawei> ",
    "display users": b"""\
  User  Host Address     Port   Serialno Type
  0     admin 192.168.1.100   23      -     HUAWEI
  1     netops 192.168.1.103  23      -     HUAWEI
""",
    "display user": b"Current user level is 3\n",
    "display local-user": b"""\
Local-user admin
 State:         Active
 Privilege:     15
 Access-type:   Telnet/SSH
 Description:   Network Administrator

Local-user netops
 State:         Active
 Privilege:     10
 Access-type:   SSH
 Description:   Network Operations

Local-user guest
 State:         Active
 Privilege:     1
 Access-type:   HTTP
 Description:   Guest User

Local-user operator
 State:         Inactive
 Privilege:     5
 Access-type:   Telnet
""",
}

H3C = {
    "name": "h3c",
    "admin_pass": "H3CPass123",
    "prompt": b"<H3C> ",
    "display users": b"""\
  User  Host Address     Port   Serialno Type
  0     admin 192.168.1.100   23      -     H3C
  1     netops 192.168.1.104  23      -     H3C
""",
    "display user": b"Current user level is 3\n",
    "display local-user": b"""\
user name admin
 access-limit disable
 authorization-attribute level 3
 service-type ssh telnet
 state active
user name netops
 access-limit disable
 authorization-attribute level 3
 service-type ssh
 state active
user name monitoring
 access-limit disable
 authorization-attribute level 2
 service-type telnet
 state active
user name operator
 access-limit disable
 authorization-attribute level 1
 service-type ssh
 state inactive
""",
}


class MockSwitchServer(ServerInterface):
    """paramiko ServerInterface that behaves like a network switch shell."""

    def __init__(self, vendor_data: dict):
        self.vendor_data = vendor_data
        self.event = threading.Event()     # set when shell starts
        self.shell_done = threading.Event() # set when shell thread exits
        self.channel = None

    def check_channel_request(self, kind, chanid):
        # kind is channel type string e.g. "session"
        # Return OPEN_SUCCEEDED (0) to accept
        return OPEN_SUCCEEDED  # 0 = success

    def check_auth_password(self, username, password):
        expected_pass = self.vendor_data["admin_pass"]
        if username == "admin" and password == expected_pass:
            return AUTH_SUCCESSFUL
        return AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_session_request(self, channel):
        self.channel = channel
        self.event.set()
        return True

    def check_channel_shell_request(self, channel):
        # Spawn interactive shell in a daemon thread so we return immediately.
        # The daemon thread exits when the client disconnects (recv returns empty).
        self.channel = channel
        self.event.set()
        _run_shell(self.vendor_data, channel, self.shell_done)
        return True

    def check_channel_exec_request(self, channel, command):
        cmd = command.decode('utf-8', errors='replace').strip()
        output = self._get_output(cmd)
        import sys
        sys.stderr.write(f"[SVR] exec_request cmd={cmd!r}\n")
        sys.stderr.flush()
        # Bypass paramiko's flow-control gate so channel.send() never blocks.
        # Without this, paramiko waits for the client to send CHANNEL_WINDOW_ADJUST,
        # which can't happen while the Transport thread is blocked in send().
        chan_transport = getattr(channel, 'transport', None)
        if chan_transport:
            chan_transport.clear_to_send.set()
        def _send():
            try:
                sent = channel.send(output)
                sys.stderr.write(f"[SVR] send returned {sent} for cmd={cmd!r}\n")
                sys.stderr.flush()
                p = self.vendor_data["prompt"]
                s2 = channel.send(p)
                sys.stderr.write(f"[SVR] prompt send returned {s2}\n")
                sys.stderr.flush()
                channel.send_exit_status(0)
                sys.stderr.write(f"[SVR] exec done for cmd={cmd!r}\n")
                sys.stderr.flush()
            except Exception as e:
                sys.stderr.write(f"[SVR] send error: {e}\n")
                sys.stderr.flush()
        t = threading.Thread(target=_send, daemon=True)
        t.start()
        return True

    def _get_output(self, cmd: str) -> bytes:
        lower = cmd.lower().strip()
        if not lower:
            return b"\r\n"
        if "terminal length" in lower or "screen-length" in lower:
            return b""
        if "privilege" in lower:
            return self.vendor_data.get("show privilege", b"")
        if lower == "who":
            return self.vendor_data.get("show users", self.vendor_data.get("display users", b""))
        if lower == "display users":
            return self.vendor_data.get("display users", b"")
        if lower == "display user":
            return self.vendor_data.get("display user", b"")
        if "show user" in lower:
            return self.vendor_data.get("display users", self.vendor_data.get("show users", b""))
        if "display local-user" in lower:
            return self.vendor_data.get("display local-user", b"")
        if "running-config" in lower and "username" in lower:
            return self.vendor_data.get("show running-config | include ^username", b"")
        if lower in ("exit", "quit", "logout"):
            return b"\r\n"
        return b"%\r\nUnknown command\r\n"


def _run_shell(vendor_data, channel, done_event=None):
    """Interactive shell: runs in a daemon thread.  All sends are wrapped in a
    background thread so they never block the caller's Transport thread."""
    def _send_safe(data):
        def _inner():
            try:
                channel.send(data)
            except Exception:
                pass
        t = threading.Thread(target=_inner, daemon=True)
        t.start()

    def _wait_and_run():
        _send_safe(vendor_data["prompt"])
        while True:
            try:
                data = channel.recv(4096)
                if not data:
                    break
                cmd = data.decode('utf-8', errors='replace').strip()
                if not cmd:
                    continue
                if cmd.lower() in ('exit', 'quit', 'logout'):
                    _send_safe(b"\r\n")
                    try:
                        channel.close()
                    except Exception:
                        pass
                    break
                output = _shell_get_output(cmd, vendor_data)
                _send_safe(output)
                _send_safe(vendor_data["prompt"])
            except EOFError:
                break
            except Exception:
                break
        if done_event:
            done_event.set()

    t = threading.Thread(target=_wait_and_run, daemon=True)
    t.start()
    return t


# Registry so the shell thread can call the right _get_output per vendor
def _shell_get_output(cmd, vendor_data):
    lower = cmd.lower().strip()
    if not lower:
        return b"\r\n"
    if "terminal length" in lower or "screen-length" in lower:
        return b""
    if "privilege" in lower:
        return vendor_data.get("show privilege", b"")
    if lower == "who":
        return vendor_data.get("show users", vendor_data.get("display users", b""))
    if lower == "display users":
        return vendor_data.get("display users", b"")
    if lower == "display user":
        return vendor_data.get("display user", b"")
    if "show user" in lower:
        return vendor_data.get("display users", vendor_data.get("show users", b""))
    if "display local-user" in lower:
        return vendor_data.get("display local-user", b"")
    if "running-config" in lower and "username" in lower:
        return vendor_data.get("show running-config | include ^username", b"")
    if lower in ("exit", "quit", "logout"):
        return b"\r\n"
    return b"%\r\nUnknown command\r\n"


def handle_client(client_sock, vendor_data: dict, local_version: str):
    """Handle one SSH client connection.

    paramiko's Transport thread processes ALL SSH callbacks autonomously:
    - check_channel_exec_request  → exec command (net_scanner uses this)
    - check_channel_shell_request → spawns interactive shell in a daemon thread

    handle_client waits on server.shell_done (set when client disconnects) so
    the Transport thread stays responsive to all callbacks throughout the
    connection lifetime.  If no shell is opened, exec commands still work.
    """
    transport = None
    try:
        transport = paramiko.Transport(client_sock, default_window_size=2097152)
        transport.local_version = local_version
        transport.add_server_key(paramiko.RSAKey.generate(2048))

        server = MockSwitchServer(vendor_data)
        transport.start_server(server=server)

        # Patch _send_user_message to skip flow-control wait.
        # The original blocks on clear_to_send, which deadlocks with
        # paramiko's exec_command() (holds client's Transport while waiting
        # for CHANNEL_SUCCESS).  We bypass by calling _send_message directly.
        _orig = transport._send_user_message
        def _no_block_send(data):
            if transport.active:
                transport._send_message(data)
        transport._send_user_message = _no_block_send

        # Wait for shell to finish (or 5 min timeout for exec-only sessions).
        # The Transport thread handles exec callbacks while we wait.
        server.shell_done.wait(timeout=300)

    except Exception as e:
        import sys
        sys.stderr.write(f"handle_client error: {e}\n")
        sys.stderr.flush()
    finally:
        if transport:
            try:
                transport.close()
            except Exception:
                pass
        try:
            client_sock.close()
        except Exception:
            pass


def run_server(port: int, vendor_data: dict, local_version: str):
    """Run a mock switch SSH server on given port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.listen(10)
    print(f"[{vendor_data['name']}] Listening on port {port}", flush=True)

    while True:
        try:
            client, addr = sock.accept()
            t = threading.Thread(
                target=handle_client,
                args=(client, vendor_data, local_version),
                daemon=True
            )
            t.start()
        except Exception as e:
            print(f"accept error on port {port}: {e}", flush=True)


if __name__ == "__main__":
    import sys

    VENDORS = [
        {"name": "cisco",  "data": CISCO,  "port": 2200, "version": "SSH-2.0-Cisco-1.25"},
        {"name": "huawei", "data": HUAWEI, "port": 2201, "version": "SSH-2.0-HUAWEI-1.1"},
        {"name": "h3c",    "data": H3C,    "port": 2202, "version": "SSH-2.0-H3C-1.0"},
    ]

    for v in VENDORS:
        t = threading.Thread(target=run_server, args=(v["port"], v["data"], v["version"]), daemon=True)
        t.start()
        print(f"Started {v['name']} on port {v['port']}", flush=True)

    print("Mock switches running. PID=" + str(os.getpid()), flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    stop_event = threading.Event()
    try:
        stop_event.wait()  # wait until interrupted
    except KeyboardInterrupt:
        print("Stopping...")
        sys.exit(0)
