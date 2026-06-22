#!/usr/bin/env python3
"""
VCOO Agent — HTTP polling client with Rich TUI.

Usage: python3 agent_http.py <control_plane_base_url> <provision_token>

Features:
- POST /register with provision_token → agent_id, vcoo_id, agent_token
- Poll GET /agent/{agent_id}/poll every 5s
- Execute commands with sandbox (timeout, drop-privileges, whitelist)
- Playbook support: downloads script from /playbooks/{name} and executes
- Stream stdout/stderr to POST /agent/{agent_id}/logs
- Rich TUI: live status table + scrollable log panel

Environment:
- POLL_INTERVAL  — seconds between polls (default 5)
- CMD_TIMEOUT    — max command execution seconds (default 60)
- SAFE_MODE      — if '1', only whitelisted commands/playbooks allowed (default 1)
- NO_TUI         — if '1', plain text output (no rich)
"""

import sys, time, os, pwd, subprocess, tempfile, shlex
from datetime import datetime, timezone

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CONTROL_PLANE", "http://localhost:8000")
PROV = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("PROVISION_TOKEN", "")

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
CMD_TIMEOUT = int(os.environ.get("CMD_TIMEOUT", "60"))
SAFE_MODE = os.environ.get("SAFE_MODE", "1") == "1"
NO_TUI = os.environ.get("NO_TUI", "0") == "1"

ALLOWED_CMDS = set(
    c.strip()
    for c in os.environ.get(
        "ALLOWED_CMDS", "echo,ls,pwd,cat,whoami,date,uname,df,free"
    ).split(",")
)

# ── TUI (rich) ──────────────────────────────────────────
tui = None
if not NO_TUI:
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.live import Live
        from rich.panel import Panel
        from rich.layout import Layout
        from rich.text import Text
        from rich import box

        console = Console()

        class AgentTUI:
            def __init__(self):
                self.agent_id = "—"
                self.vcoo_id = "—"
                self.status = "connecting"
                self.cmds_done = 0
                self.cmds_blocked = 0
                self.uptime_start = time.time()
                self.log_lines: list[str] = []
                self.live: Live | None = None

            def set_meta(self, agent_id, vcoo_id):
                self.agent_id = agent_id
                self.vcoo_id = vcoo_id
                self.status = "polling"

            def log(self, text: str, style: str = ""):
                ts = datetime.now().strftime("%H:%M:%S")
                line = f"[dim]{ts}[/dim] {text}"
                if style:
                    line = f"[{style}]{line}[/{style}]"
                self.log_lines.append(line)
                if len(self.log_lines) > 200:
                    self.log_lines = self.log_lines[-100:]

            def build(self):
                uptime = int(time.time() - self.uptime_start)
                m, s = divmod(uptime, 60)
                h, m = divmod(m, 60)

                table = Table(box=box.ROUNDED, expand=True, show_header=False)
                table.add_column("k", style="dim cyan", width=14)
                table.add_column("v", style="white")
                table.add_row("Agent ID", self.agent_id[:20] + "…")
                table.add_row("VCOO ID", self.vcoo_id[:20] + "…")
                table.add_row("Status", self.status)
                table.add_row("Uptime", f"{h:02d}:{m:02d}:{s:02d}")
                table.add_row("Commands OK", str(self.cmds_done))
                table.add_row("Blocked", str(self.cmds_blocked))

                log_text = Text()
                for line in self.log_lines[-15:]:
                    log_text.append(line + "\n")

                layout = Layout()
                layout.split_column(
                    Layout(Panel(table, title="[bold]VCOO Agent[/bold]", border_style="cyan"), size=10),
                    Layout(Panel(log_text, title="Log", border_style="dim white")),
                )
                return layout

            def __enter__(self):
                self.live = Live(self.build(), console=console, refresh_per_second=4, screen=True)
                self.live.__enter__()
                return self

            def __exit__(self, *args):
                if self.live:
                    self.live.__exit__(*args)

            def update(self):
                if self.live:
                    self.live.update(self.build())

        tui = AgentTUI()
    except ImportError:
        pass

# ── Session ─────────────────────────────────────────────
session = requests.Session()


def drop_privileges():
    if os.geteuid() == 0:
        try:
            nobody = pwd.getpwnam("nobody")
            os.setgid(nobody.pw_gid)
            os.setuid(nobody.pw_uid)
            msg = "Dropped privileges to nobody"
            if tui:
                tui.log(msg, "dim yellow")
            else:
                print(msg)
        except Exception as e:
            msg = f"WARN: Could not drop privileges: {e}"
            if tui:
                tui.log(msg, "yellow")
            else:
                print(msg)


def send_log(agent_id, cmd_id, chunk, stream="stdout"):
    try:
        session.post(
            f"{BASE}/agent/{agent_id}/logs",
            json={"cmd_id": cmd_id, "chunk": chunk, "stream": stream},
            timeout=5,
        )
    except Exception as e:
        msg = f"[WARN] Failed to send log: {e}"
        if tui:
            tui.log(msg, "red")
        else:
            print(msg)


def send_result(vcoo_id, cmd_id, summary):
    try:
        session.post(
            f"{BASE}/vcoo/{vcoo_id}/commands/{cmd_id}/result",
            json={"result": summary},
            timeout=5,
        )
    except Exception as e:
        msg = f"[WARN] Failed to send result: {e}"
        if tui:
            tui.log(msg, "red")
        else:
            print(msg)


def is_allowed(command: str) -> bool:
    if not SAFE_MODE:
        return True
    # Playbooks are always allowed in safe mode
    if command.startswith("playbook:"):
        return True
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if not tokens:
        return False
    base_cmd = os.path.basename(tokens[0])
    return base_cmd in ALLOWED_CMDS


def resolve_playbook(command: str) -> str | None:
    """If command is 'playbook:<name>', download and return the script content."""
    if not command.startswith("playbook:"):
        return None
    name = command.split(":", 1)[1].strip()
    if not name:
        return None
    try:
        resp = session.get(f"{BASE}/playbooks/{name}", timeout=10)
        if resp.status_code != 200:
            msg = f"Playbook '{name}' not found (HTTP {resp.status_code})"
            if tui:
                tui.log(msg, "red")
            else:
                print(msg)
            return None
        data = resp.json()
        script = data.get("script", "")
        if not script:
            msg = f"Playbook '{name}' is empty"
            if tui:
                tui.log(msg, "red")
            else:
                print(msg)
            return None
        msg = f"Downloaded playbook '{name}' ({len(script)} bytes)"
        if tui:
            tui.log(msg, "green")
        else:
            print(msg)
        return script
    except Exception as e:
        msg = f"Failed to download playbook '{name}': {e}"
        if tui:
            tui.log(msg, "red")
        else:
            print(msg)
        return None


def execute_command(command: str, agent_id: str, cmd_id: str) -> str:
    if not is_allowed(command):
        summary = f"BLOCKED: '{command}' not in allowed commands"
        if tui:
            tui.log(summary, "red")
        else:
            print(summary)
        send_log(agent_id, cmd_id, summary + "\n", "stderr")
        if tui:
            tui.cmds_blocked += 1
        return summary

    # Resolve playbook
    script = resolve_playbook(command)
    if script is not None:
        if script == "":  # empty means failed to download
            summary = f"FAILED: could not download playbook from '{command}'"
            send_log(agent_id, cmd_id, summary + "\n", "stderr")
            return summary
        # Write playbook to temp file and execute
        fd, tmpath = tempfile.mkstemp(prefix="vcoo-playbook-", suffix=".sh")
        with os.fdopen(fd, "w") as f:
            f.write(script)
        os.chmod(tmpath, 0o700)
        actual_cmd = f"bash {shlex.quote(tmpath)}"
        cleanup = tmpath
    else:
        actual_cmd = command
        cleanup = None

    label = command if len(command) < 60 else command[:57] + "..."
    if tui:
        tui.log(f"Exec: {label}", "cyan")
    else:
        print(f"Executing: {label}")

    try:
        proc = subprocess.Popen(
            actual_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,
        )

        def stream_and_send(pipe, stream_name, style):
            if pipe:
                for line in pipe:
                    stripped = line.rstrip()
                    if tui:
                        tui.log(f"  {stripped}", style)
                    else:
                        print(f"  {stripped}")
                    send_log(agent_id, cmd_id, line, stream_name)

        # Stream stdout and stderr
        import threading

        t_stdout = threading.Thread(target=stream_and_send, args=(proc.stdout, "stdout", "white"))
        t_stderr = threading.Thread(target=stream_and_send, args=(proc.stderr, "stderr", "red"))
        t_stdout.start()
        t_stderr.start()

        try:
            exit_code = proc.wait(timeout=CMD_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            summary = f"TIMEOUT ({CMD_TIMEOUT}s): {label}"
            send_log(agent_id, cmd_id, summary + "\n", "stderr")
            if cleanup:
                os.unlink(cleanup)
            return summary

        t_stdout.join(timeout=2)
        t_stderr.join(timeout=2)

        if exit_code == 0:
            summary = f"OK (exit 0)"
        else:
            summary = f"FAILED (exit {exit_code})"

        if tui:
            tui.cmds_done += 1
        return summary

    except Exception as e:
        summary = f"ERROR: {e}"
        send_log(agent_id, cmd_id, summary + "\n", "stderr")
        if tui:
            tui.log(summary, "red")
        return summary
    finally:
        if cleanup:
            try:
                os.unlink(cleanup)
            except OSError:
                pass


def register():
    try:
        resp = session.post(
            f"{BASE}/register",
            json={"token": PROV, "info": {"hostname": os.uname().nodename}},
            timeout=10,
        )
    except Exception as e:
        msg = f"Registration failed: {e}"
        if tui:
            tui.log(msg, "red")
        else:
            print(msg)
        return None

    if resp.status_code != 200:
        msg = f"Registration failed: HTTP {resp.status_code} {resp.text}"
        if tui:
            tui.log(msg, "red")
        else:
            print(msg)
        return None

    j = resp.json()
    aid = j.get("agent_id", "?")
    vid = j.get("vcoo_id", "?")
    if tui:
        tui.log(f"Registered as agent {aid[:20]}…", "green")
        tui.set_meta(aid, vid)
    else:
        print(f"Registered agent_id {aid}")
    return j


def poll_loop(agent_id, agent_token, vcoo_id):
    headers = {"Authorization": f"Bearer {agent_token}"}
    if tui:
        tui.log(f"Polling {BASE} every {POLL_INTERVAL}s", "cyan")
    else:
        print(f"Poll loop started (interval={POLL_INTERVAL}s, safe_mode={SAFE_MODE})")

    while True:
        try:
            r = session.get(f"{BASE}/agent/{agent_id}/poll", headers=headers, timeout=10)
        except Exception as e:
            if tui:
                tui.log(f"Poll error: {e}", "yellow")
            else:
                print(f"Poll error: {e}")
            time.sleep(POLL_INTERVAL)
            continue

        if r.status_code == 200:
            j = r.json()
            cmds = j.get("commands", [])
            for c in cmds:
                cmd_id = c.get("cmd_id")
                command = c.get("command")
                summary = execute_command(command, agent_id, cmd_id)
                send_result(vcoo_id, cmd_id, summary)
                if tui:
                    tui.log(f"Done: {summary}", "green" if "OK" in summary else "yellow")
                else:
                    ts = datetime.now(timezone.utc).isoformat()
                    print(f"{ts} DONE {cmd_id}: {summary}")
        elif r.status_code == 401:
            msg = "Auth expired, exiting"
            if tui:
                tui.log(msg, "red")
            else:
                print(msg)
            break
        else:
            if tui:
                tui.log(f"Poll HTTP {r.status_code}", "dim")
            else:
                print(f"poll returned {r.status_code}")

        if tui:
            tui.update()
        time.sleep(POLL_INTERVAL)


def main():
    if not PROV:
        print("Provision token required", file=sys.stderr)
        print("Usage: python3 agent_http.py <control_plane_url> <provision_token>", file=sys.stderr)
        print("   or: PROVISION_TOKEN=*** python3 agent_http.py <control_plane_url>", file=sys.stderr)
        sys.exit(2)

    drop_privileges()

    if tui:
        with tui:
            tui.log("Starting VCOO Agent…", "cyan bold")
            tui.update()
            meta = register()
            if not meta:
                tui.log("FATAL: Registration failed", "red bold")
                time.sleep(2)
                sys.exit(1)
            agent_id = meta.get("agent_id")
            agent_token = meta.get("agent_token")
            vcoo_id = meta.get("vcoo_id")
            try:
                poll_loop(agent_id, agent_token, vcoo_id)
            except KeyboardInterrupt:
                tui.log("Interrupted, exiting", "yellow")
    else:
        meta = register()
        if not meta:
            sys.exit(1)
        agent_id = meta.get("agent_id")
        agent_token = meta.get("agent_token")
        vcoo_id = meta.get("vcoo_id")
        try:
            poll_loop(agent_id, agent_token, vcoo_id)
        except KeyboardInterrupt:
            print("Interrupted, exiting")


if __name__ == "__main__":
    main()
