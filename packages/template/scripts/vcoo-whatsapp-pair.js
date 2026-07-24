#!/usr/bin/env node
const path = require('path');
const fs = require('fs');

const HERMES_HOME = process.env.HERMES_HOME || path.join(require('os').homedir(), '.hermes');
const BRIDGE_DIR = path.join(HERMES_HOME, 'hermes-agent', 'scripts', 'whatsapp-bridge');
const BAIL_EYS_DIR = path.join(BRIDGE_DIR, 'node_modules', '@whiskeysockets', 'baileys');

// Use a fresh session per pairing attempt
const SESSION_DIR = path.join(HERMES_HOME, 'whatsapp-session', 'pair-' + Date.now().toString(36));

function emit(ev) {
  process.stdout.write(JSON.stringify({ ts: Date.now(), ...ev }) + '\n');
}

const args = process.argv.slice(2);
const phoneIdx = args.indexOf('--phone');
const phoneNumber = phoneIdx >= 0 ? args[phoneIdx + 1] : null;

async function main() {
  if (!fs.existsSync(path.join(BAIL_EYS_DIR, 'package.json'))) {
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

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr && !paired && !qrEmitted) {
      qrEmitted = true;
      if (!phoneNumber) {
        emit({ event: 'qr', qr });
      } else {
        // Pairing code mode: request code when socket is ready
        const cleanPhone = phoneNumber.replace(/[^0-9]/g, '');
        if (cleanPhone.length < 7) {
          emit({ event: 'error', error: 'invalid_phone', message: 'Phone number too short. Use international format, e.g. 521234567890' });
          return;
        }
        try {
          const code = await sock.requestPairingCode(cleanPhone);
          emit({ event: 'pairing_code', code, phone: phoneNumber });
        } catch (err) {
          emit({ event: 'error', error: 'pairing_code_failed', message: err.message });
        }
      }
    }

    if (connection === 'open') {
      paired = true;
      const user = sock.authState.creds.me;
      emit({ event: 'connected', user });
      setTimeout(() => process.exit(0), 500);
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
