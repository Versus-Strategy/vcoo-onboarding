import os, json, socket, subprocess, time, urllib.request

class Plugin:
    name = "health_reporter"
    interval = 60

    def start(self, config):
        self.agent_id = os.environ.get("AGENT_ID", config.get("agent_id", ""))
        self.agent_token = os.environ.get("AGENT_TOKEN", config.get("agent_token", ""))
        self.control_plane = os.environ.get("CONTROL_PLANE", config.get("control_plane", "http://localhost:8000"))

    def stop(self):
        pass

    def _get_uptime(self):
        try:
            with open("/proc/uptime") as f:
                return float(f.read().split()[0])
        except:
            return 0

    def _get_disk(self):
        try:
            s = os.statvfs("/")
            total = s.f_frsize * s.f_blocks
            free = s.f_frsize * s.f_bfree
            return total, free, round((1 - free / total) * 100, 1)
        except:
            return 0, 0, 0

    def _hermes_running(self):
        try:
            r = subprocess.run(["pgrep", "-f", "hermes.*gateway"], capture_output=True, timeout=5)
            return r.returncode == 0
        except:
            return False

    def tick(self):
        if not self.agent_id:
            return
        total, free, pct = self._get_disk()
        payload = {
            "hostname": socket.gethostname(),
            "timestamp": time.time(),
            "uptime_seconds": int(self._get_uptime()),
            "hermes_running": self._hermes_running(),
            "disk_total_gb": round(total / (1024**3), 1),
            "disk_free_gb": round(free / (1024**3), 1),
            "disk_used_pct": pct,
            "template_version": os.environ.get("TEMPLATE_VERSION", ""),
            "supervisor_version": "0.1.0",
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.control_plane}/agent/{self.agent_id}/health",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.agent_token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
        except Exception:
            pass
