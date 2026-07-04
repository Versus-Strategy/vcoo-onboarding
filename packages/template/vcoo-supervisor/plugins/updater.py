import subprocess, logging

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
