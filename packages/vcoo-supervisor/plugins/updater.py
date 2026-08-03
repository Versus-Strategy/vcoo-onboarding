import subprocess, os, logging

class Plugin:
    name = "updater"
    interval = 604800  # 7 days

    def start(self, config):
        pass

    def stop(self):
        pass

    def tick(self):
        try:
            r = subprocess.run(["hermes", "update"], capture_output=True, timeout=120)
            if r.returncode == 0:
                logging.info("[updater] Hermes updated successfully")
            else:
                logging.warning(f"[updater] hermes update failed: {r.stderr.decode()[:200]}")
        except Exception as e:
            logging.error(f"[updater] Error: {e}")
        self._refresh_supervisor()

    def _refresh_supervisor(self):
        """Redploya el supervisor VCOO desde el control plane y programa su reinicio."""
        script = "/opt/vcoo-supervisor/update.sh"
        if not os.path.isfile(script):
            logging.warning(f"[updater] no existe {script} (supervisor no auto-actualizable)")
            return
        try:
            r = subprocess.run(["sudo", "-n", "bash", script], capture_output=True, timeout=150)
            if r.returncode != 0:
                logging.warning(f"[updater] supervisor update failed: {r.stderr.decode()[:300]}")
                return
            logging.info("[updater] supervisor actualizado; reiniciando servicio...")
            subprocess.run(
                ["sudo", "-n", "systemd-run", "--on-active=2",
                 "systemctl", "restart", "vcoo-supervisor.service"],
                capture_output=True, timeout=30,
            )
        except Exception as e:
            logging.error(f"[updater] supervisor update error: {e}")
