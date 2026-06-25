/**
 * Anveshak WhatsApp Bridge — Baileys sidecar.
 *
 * Connects to WhatsApp Web via multi-device auth, listens for group messages,
 * and pushes them to a Redis buffer for the Python WhatsAppAdapter to drain.
 *
 * Media is downloaded to a shared volume (/app/media) accessible by the
 * social and vision services.
 */
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  downloadMediaMessage,
} = require("@whiskeysockets/baileys");
const express = require("express");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const pino = require("pino");

const { createRedisClient, pushMessage, pushLogoutSentinel } = require("./redis");
const { createRouter } = require("./health");

const log = pino({ name: "whatsapp-bridge" });

// ---------------------------------------------------------------------------
// Configuration from environment
// ---------------------------------------------------------------------------

const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";
const PORT = parseInt(process.env.WHATSAPP_BRIDGE_PORT || "3002", 10);
const AUTH_DIR = process.env.WHATSAPP_AUTH_DIR || "/app/auth";
const MEDIA_DIR = process.env.WHATSAPP_MEDIA_DIR || "/app/media";
const BUFFER_MAX = parseInt(process.env.WHATSAPP_BUFFER_MAX || "10000", 10);
const BRIDGE_TOKEN = process.env.WHATSAPP_BRIDGE_TOKEN || "";
const PHONE_NUMBER = process.env.WHATSAPP_PHONE_NUMBER || ""; // e.g. "919876543210" for pairing code auth

// Media files need to be readable by social worker (different container user)
// Auth files in /app/auth are protected by volume isolation
process.umask(0o022);

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------

const state = {
  qr: null,
  status: "disconnected",
  sock: null,
  redis: null,
  groupCount: 0,
};

// ---------------------------------------------------------------------------
// Media download
// ---------------------------------------------------------------------------

/**
 * Download media from a WhatsApp message to shared volume.
 * @param {object} message - Baileys message object
 * @param {string} groupJid - Group JID for path organization
 * @returns {Promise<{path: string, type: string} | null>}
 */
async function downloadMedia(message, groupJid) {
  try {
    const buffer = await downloadMediaMessage(message, "buffer", {});
    if (!buffer || buffer.length === 0) return null;

    const hash = crypto.createHash("sha256").update(buffer).digest("hex");
    const now = new Date();
    const dateDir = `${now.getFullYear()}/${String(now.getMonth() + 1).padStart(2, "0")}/${String(now.getDate()).padStart(2, "0")}`;

    // Determine extension from message type
    let ext = ".bin";
    let mediaType = "unknown";
    const msg = message.message;
    if (msg.imageMessage) { ext = ".jpg"; mediaType = "image"; }
    else if (msg.videoMessage) { ext = ".mp4"; mediaType = "video"; }
    else if (msg.documentMessage) {
      ext = path.extname(msg.documentMessage.fileName || "") || ".bin";
      mediaType = "document";
    }
    else if (msg.audioMessage) { ext = ".ogg"; mediaType = "audio"; }

    const groupId = groupJid.split("@")[0];
    const filePath = path.join(MEDIA_DIR, groupId, dateDir, `${hash}${ext}`);

    // Ensure directory exists
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, buffer);

    log.info({ path: filePath, type: mediaType, hash, size: buffer.length }, "media.downloaded");
    return { path: filePath, type: mediaType };
  } catch (err) {
    log.error({ err: err.message }, "media.download_failed");
    return null;
  }
}

// ---------------------------------------------------------------------------
// Text extraction from deeply nested Baileys message
// ---------------------------------------------------------------------------

/**
 * Extract text from Baileys message object (handles all nesting paths).
 * @param {object} msg - message.message object
 * @returns {string | null}
 */
function extractText(msg) {
  if (!msg) return null;
  // Direct conversation
  if (msg.conversation) return msg.conversation;
  // Extended text (replies, links)
  if (msg.extendedTextMessage?.text) return msg.extendedTextMessage.text;
  // Ephemeral messages
  if (msg.ephemeralMessage?.message?.extendedTextMessage?.text)
    return msg.ephemeralMessage.message.extendedTextMessage.text;
  if (msg.ephemeralMessage?.message?.conversation)
    return msg.ephemeralMessage.message.conversation;
  // View-once messages
  if (msg.viewOnceMessage?.message?.extendedTextMessage?.text)
    return msg.viewOnceMessage.message.extendedTextMessage.text;
  // Image/video captions
  if (msg.imageMessage?.caption) return msg.imageMessage.caption;
  if (msg.videoMessage?.caption) return msg.videoMessage.caption;
  return null;
}

/**
 * Check if message contains downloadable media.
 * @param {object} msg - message.message object
 * @returns {boolean}
 */
function hasMedia(msg) {
  if (!msg) return false;
  return !!(msg.imageMessage || msg.videoMessage || msg.documentMessage || msg.audioMessage);
}

// ---------------------------------------------------------------------------
// Baileys connection
// ---------------------------------------------------------------------------

let reconnectAttempts = 0;
let reconnectTimer = null;
const MAX_RECONNECT_DELAY = 30000;

async function connectWhatsApp() {
  const { state: authState, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  const sock = makeWASocket({
    auth: authState,
    printQRInTerminal: true,
    version: [2, 3000, 1033893291],                    // WhatsApp-accepted version (fixes 405)
    browser: ["Anveshak OSINT", "Chrome", "145.0.0"],  // match modern Chrome fingerprint
    logger: pino({ level: "info" }),
    syncFullHistory: false,
    generateHighQualityLinkPreview: false,
    markOnlineOnConnect: false,
  });

  state.sock = sock;

  // Credential save handler
  sock.ev.on("creds.update", saveCreds);

  // If phone number provided and not already registered, use pairing code
  if (PHONE_NUMBER && !authState.creds.registered) {
    setTimeout(async () => {
      try {
        const code = await sock.requestPairingCode(PHONE_NUMBER);
        state.pairingCode = code;
        state.status = "pairing_code_pending";
        log.info({ code, phone: PHONE_NUMBER }, "pairing_code.generated — enter this code in WhatsApp > Linked Devices > Link with phone number");
      } catch (err) {
        log.error({ err: err.message }, "pairing_code.request_failed");
      }
    }, 2000);
  }

  // Connection state handler
  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      state.qr = qr;
      state.status = "qr_pending";
      log.info("qr.generated");
    }

    if (connection === "open") {
      state.status = "connected";
      state.qr = null;
      state.pairingCode = null;
      reconnectAttempts = 0;
      // Cancel any pending reconnect timer to prevent race condition
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      log.info("connection.open");

      // Update group count
      try {
        const groups = await sock.groupFetchAllParticipating();
        state.groupCount = Object.keys(groups).length;
        log.info({ groups: state.groupCount }, "groups.counted");
      } catch {
        // Non-fatal — groups endpoint will fetch on demand
      }
    }

    if (connection === "close") {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      log.warn({ statusCode }, "connection.closed");

      if (statusCode === DisconnectReason.loggedOut) {
        // Session invalidated — user unlinked device
        state.status = "logged_out";
        state.qr = null;
        state.sock = null;
        log.error("connection.logged_out — re-scan QR required");

        // Push logout sentinel to Redis buffer
        if (state.redis) {
          await pushLogoutSentinel(state.redis);
        }
        // DO NOT reconnect — session is dead
        return;
      }

      // If pairing code was issued, wait longer before reconnecting
      // to give user time to enter it on their phone
      if (state.pairingCode) {
        state.status = "pairing_code_pending";
        log.info("connection.waiting_for_pairing — enter code on phone, bridge will reconnect in 60s");
        state.pairingCode = null; // clear so next cycle generates a fresh one
        reconnectTimer = setTimeout(connectWhatsApp, 60000);
        return;
      }

      // All other disconnect reasons — retry with exponential backoff
      state.status = "disconnected";
      reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), MAX_RECONNECT_DELAY);
      log.info({ delay, attempt: reconnectAttempts }, "connection.reconnecting");
      reconnectTimer = setTimeout(connectWhatsApp, delay);
    }
  });

  // Message handler — only group messages
  sock.ev.on("messages.upsert", async ({ messages }) => {
    for (const msg of messages) {
      try {
        const jid = msg.key.remoteJid;
        // Only process group messages
        if (!jid || !jid.endsWith("@g.us")) continue;
        // Skip status broadcasts
        if (jid === "status@broadcast") continue;
        // Skip messages sent by us
        if (msg.key.fromMe) continue;

        const text = extractText(msg.message);
        const msgHasMedia = hasMedia(msg.message);

        // Skip if no text and no media (system messages, reactions, etc.)
        if (!text && !msgHasMedia) continue;

        // Download media if present
        let mediaInfo = null;
        if (msgHasMedia) {
          mediaInfo = await downloadMedia(msg, jid);
        }

        const payload = {
          group_jid: jid,
          group_name: msg.key.remoteJid, // Will be resolved by /groups endpoint
          sender: msg.key.participant || jid,
          sender_name: msg.pushName || null,
          message_id: msg.key.id,
          text: text,
          timestamp: msg.messageTimestamp
            ? typeof msg.messageTimestamp === "number"
              ? msg.messageTimestamp
              : msg.messageTimestamp.low || Math.floor(Date.now() / 1000)
            : Math.floor(Date.now() / 1000),
          media_path: mediaInfo?.path || null,
          media_type: mediaInfo?.type || null,
          reply_to_id: msg.message?.extendedTextMessage?.contextInfo?.stanzaId || null,
          forwarded: !!(msg.message?.extendedTextMessage?.contextInfo?.isForwarded),
        };

        await pushMessage(state.redis, payload, BUFFER_MAX);
        log.debug({ jid, msgId: msg.key.id, hasText: !!text, hasMedia: !!mediaInfo }, "message.buffered");
      } catch (err) {
        log.error({ err: err.message, msgId: msg.key?.id }, "message.process_failed");
      }
    }
  });
}

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------

async function main() {
  log.info({ port: PORT, authDir: AUTH_DIR, mediaDir: MEDIA_DIR, bufferMax: BUFFER_MAX }, "bridge.starting");

  // Ensure directories exist
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  fs.mkdirSync(MEDIA_DIR, { recursive: true });

  // Connect to Redis
  state.redis = createRedisClient(REDIS_URL);

  // Start Express server
  const app = express();
  app.use(createRouter(state, BRIDGE_TOKEN));
  app.listen(PORT, () => {
    log.info({ port: PORT }, "http.listening");
  });

  // Connect to WhatsApp
  await connectWhatsApp();
}

main().catch((err) => {
  log.fatal({ err: err.message }, "bridge.fatal");
  process.exit(1);
});
