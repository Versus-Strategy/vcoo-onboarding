#!/usr/bin/env python3
"""VCOO Supervisor — modular agent health reporter, watchdog, and updater."""

import os, sys, time, importlib, logging, signal, json
from pathlib import Path

CONFIG_PATHS = [
    "/etc/vcoo/supervisor.json",
    os.path.expanduser("~/.vcoo/supervisor.json"),
    "supervisor.json",
    "/opt/vcoo-supervisor/config.json",
]

class Supervisor:
    def __init__(self, config: dict):
        self.config = config
        self.plugins: list = []
        self.running = True
        self.last_tick: dict[str, float] = {}

    def load_plugins(self):
        plugin_dir = Path(__file__).parent / "plugins"
        sys.path.insert(0, str(plugin_dir))
        for name, cfg in self.config.get("plugins", {}).items():
            if not cfg.get("enabled", True):
                continue
            mod = importlib.import_module(name)
            plugin = mod.Plugin()
            plugin.start(cfg)
            self.plugins.append(plugin)
            self.last_tick[name] = 0

    def run(self):
        self.load_plugins()
        while self.running:
            now = time.time()
            for plugin in self.plugins:
                if now - self.last_tick[plugin.name] >= plugin.interval:
                    try:
                        plugin.tick()
                    except Exception as e:
                        logging.error(f"[{plugin.name}] Error: {e}")
                    self.last_tick[plugin.name] = now
            time.sleep(1)

    def stop(self, signum=None, frame=None):
        self.running = False
        for plugin in self.plugins:
            try:
                plugin.stop()
            except Exception as e:
                logging.error(f"[{plugin.name}] Stop error: {e}")

def load_config() -> dict:
    for path in CONFIG_PATHS:
        if os.path.isfile(path):
            with open(path) as f:
                return json.load(f)
    return {"plugins": {}}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    config = load_config()
    sup = Supervisor(config)
    signal.signal(signal.SIGTERM, sup.stop)
    signal.signal(signal.SIGINT, sup.stop)
    sup.run()
