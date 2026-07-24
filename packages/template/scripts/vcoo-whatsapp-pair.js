#!/usr/bin/env node
const path = require('path');
const fs = require('fs');

const HERMES_HOME = process.env.HERMES_HOME || path.join(require('os').homedir(), '.hermes');
const BRIDGE_DIR = path.join(HERMES_HOME, 'hermes-agent', 'scripts', 'whatsapp-bridge');
const BAIL_EYS = path.join(BRIDGE_DIR, 'node_modules', '@whiskeysockets', 'baileys');
const SESSION_DIR = path.join(HERMES_HOME, 'whatsapp-session', 'pair-' + Date.now().toString(36));

function emit(ev) {
  process.stdout.write(JSON.stringify({ ts: Date.now(), ...ev }) + '\n');
}

const args = process.argv.slice(2);
const phoneIdx = args.indexOf('--phone');
const phoneNumber = phoneIdx >= 0 ? args[phoneIdx + 1] : null;
const timeoutIdx = args.indexOf('--timeout');
const scriptTimeout = (timeoutIdx >= 0 ? parseInt(args[timeoutIdx + 1]) : 60) * 1000;

async function main() {
  if (!fs.existsSync(path.join(BAIL_EYS, 'package.json'))) {
    emit({ event: 'installing' });
    const { execSync } = require('child_process');
    execSync('npm install --no-audit --no-fund --loglevel=error', {
      cwd: BRIDGE_DIR, stdio: 'pipe', timeout: 180000,
    });
  }

  const Baileys = require('@whiskeysockets/baileys');
  const { makeWASocket, useMultiFileAuthState, DisconnectReason } = Baileys;
  const P = require('pino');

  fs.mkdirSync(SESSION_DIR, { recursive: true });
  const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);

  const sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
    logger: P({ level: 'silent' }),
    browser: ['VCOO', 'Chrome', ''],
    syncFullHistory: false,
    markOnlineOnConnect: false,
  });

  let paired = false;
  let qrEmitted = false;
  let timeout = setTimeout(() => {
    if (!paired) {
      emit({ event: 'error', error: 'timeout' });
      process.exit(1);
    }
  }, scriptTimeout);

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr && !paired && !qrEmitted) {
      qrEmitted = true;
      clearTimeout(timeout);
      if (!phoneNumber) {
        emit({ event: 'qr', qr });
        // Keep connection alive for pairing
      } else {
        const cleanPhone = phoneNumber.replace(/[^0-9]/g, '');
        if (cleanPhone.length < 7) {
          emit({ event: 'error', error: 'invalid_phone' });
          process.exit(1);
          return;
        }
        try {
          const code = await sock.requestPairingCode(cleanPhone);
          emit({ event: 'pairing_code', code, phone: phoneNumber });
          // Don't exit — wait for connection
          timeout = setTimeout(() => {
            if (!paired) {
              emit({ event: 'error', error: 'pairing_timeout' });
              process.exit(1);
            }
          }, 120000);
        } catch (err) {
          emit({ event: 'error', error: 'pairing_code_failed', message: err.message });
          process.exit(1);
        }
      }
    }

    if (connection === 'open') {
      paired = true;
      clearTimeout(timeout);
      const user = sock.authState.creds.me;
      emit({ event: 'connected', user });
    }

    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      if (statusCode === DisconnectReason.loggedOut) {
        emit({ event: 'error', error: 'logged_out' });
      } else if (!paired) {
        emit({ event: 'error', error: 'connection_closed', code: statusCode });
      }
      process.exit(paired ? 0 : 1);
    }
  });
}

main().catch((err) => {
  emit({ event: 'error', error: err.message });
  process.exit(1);
});
