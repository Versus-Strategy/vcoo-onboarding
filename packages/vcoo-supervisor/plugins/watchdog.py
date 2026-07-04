import subprocess, logging

class Plugin:
    name = "watchdog"
    interval = 30

    def start(self, config):
        self.service = config.get("service", "hermes-gateway")

    def stop(self):
        pass

    def tick(self):
        try:
            r = subprocess.run(["pgrep", "-f", "hermes.*gateway"], capture_output=True, timeout=5)
            if r.returncode != 0:
                logging.warning("[watchdog] Hermes not running — restarting")
                subprocess.run(["systemctl", "restart", self.service], capture_output=True, timeout=30)
        except Exception as e:
            logging.error(f"[watchdog] Error: {e}")
