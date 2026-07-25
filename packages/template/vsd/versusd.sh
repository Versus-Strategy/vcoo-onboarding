#!/usr/bin/env bash
# versusd.sh – watchdog cuyo único trabajo es vigilar el agente Hermes
LOGFILE="/var/log/versusd.log"
SERVICE="hermes-gateway"
USER="ubuntu"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOGFILE"
}

# Check if Hermes agent process is running
hermes_running() {
    pgrep -f "hermes_cli.main gateway run" > /dev/null
    return $?
}

# Start Hermes via user systemd service
start_hermes() {
    su - "$USER" -c "systemctl --user start hermes-gateway"
}

while true; do
    if hermes_running; then
        # Service is active, just log occasionally
        if [ $(( $(date +%s) % 300 )) -lt 10 ]; then
            log "Hermes agent is active."
        fi
    else
        log "Hermes agent is not running! Attempting start..."
        start_hermes
        sleep 10
        if hermes_running; then
            log "Hermes agent started successfully."
        else
            log "Hermes agent start failed."
        fi
    fi
    sleep 30
done
