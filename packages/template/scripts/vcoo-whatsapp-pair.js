#!/usr/bin/env node
/* VCOO WhatsApp pairing — supports QR code and pairing code modes.
 * Usage:
 *   node vcoo-whatsapp-pair.js                          # QR mode (default)
 *   node vcoo-whatsapp-pair.js --phone +1234567890      # Pairing code mode
 * Outputs JSON lines: {event, qr?, code?, error?}
 */
const path = require('path');
const fs = require('fs');

// Determine bridge directory (relative to Hermes home)
const HERMES_HOME = process.env.HERMES_HOME || path.join(require('os').homedir(), '.hermes');
const BRIDGE_DIR = path.join(HERMES_HOME, 'hermes-agent', 'scripts', 'whatsapp-bridge');
const SESSION_DIR = process.env.SESSION_DIR || path.join(HERMES_HOME, 'whatsapp-session', 'main');
const BAIL_EYS = path.join(BRIDGE_DIR, 'node_modules', '@whiskeysockets', 'baileys');

function emit(ev) {
  process.stdout.write(JSON.stringify({ ts: Date.now(), ...ev }) + '\n');
}

// Parse args
const args = process.argv.slice(2);
const phoneIdx = args.indexOf('--phone');
const phoneNumber = phoneIdx >= 0 ? args[phoneIdx + 1] : null;

async function main() {
  // Ensure Baileys is installed
  if (!fs.existsSync(path.join(BAIL_EYS, 'package.json'))) {
    emit({ event: 'installing' });
    const { execSync } = require('child_process');
    execSync('npm install --no-audit --no-fund --loglevel=error', {
      cwd: BRIDGE_DIR,
      stdio: 'pipe',
      timeout: 120000,
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

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr && !paired && !phoneNumber) {
      emit({ event: 'qr', qr });
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

  // If phone number provided, request pairing code
  if (phoneNumber) {
    // Wait a moment for socket to initialize
    await new Promise(r => setTimeout(r, 2000));
    try {
      const code = await sock.requestPairingCode(phoneNumber);
      emit({ event: 'pairing_code', code, phone: phoneNumber });
    } catch (err) {
      emit({ event: 'error', error: 'pairing_code_failed', message: err.message });
    }
  }
}

main().catch((err) => {
  emit({ event: 'error', error: err.message });
  process.exit(1);
});
