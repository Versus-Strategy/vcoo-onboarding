#!/usr/bin/env bash
# versusd.sh – watchdog cuyo único trabajo es vigilar hermes‑gateway.service
LOGFILE="/var/log/versusd.log"
SERVICE="hermes-gateway"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOGFILE"
}

while true; do
    if systemctl is-active --quiet "$SERVICE"; then
        # Sólo cada 5 min para evitar ruido
        if [ $(( $(date +%s) % 300 )) -lt 10 ]; then
            log "$SERVICE is active."
        fi
    else
        log "$SERVICE is inactive! Attempting restart..."
        systemctl restart "$SERVICE" 2>>"$LOGFILE" || true
        sleep 10
        if systemctl is-active --quiet "$SERVICE"; then
            log "$SERVICE restarted successfully."
        else
            log "$SERVICE restart failed."
        fi
    fi
    sleep 30
done