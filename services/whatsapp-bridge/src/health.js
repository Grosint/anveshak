/**
 * Express health/QR/groups endpoints for the WhatsApp bridge.
 *
 * All endpoints except GET /health require Bearer token auth.
 */
const express = require("express");
const QRCode = require("qrcode");
const pino = require("pino");

const log = pino({ name: "whatsapp-bridge-health" });

/**
 * Create Express router with health, QR, and groups endpoints.
 * @param {object} state - Shared bridge state (qr, status, sock, redis, bufferLength)
 * @param {string} bridgeToken - Bearer token for auth
 * @returns {express.Router}
 */
function createRouter(state, bridgeToken) {
  const router = express.Router();

  // Auth middleware — skip for /health (returns minimal info without auth)
  const requireAuth = (req, res, next) => {
    if (!bridgeToken) return next(); // no token configured = open access
    const auth = req.headers.authorization;
    if (!auth || auth !== `Bearer ${bridgeToken}`) {
      return res.status(401).json({ error: "Unauthorized" });
    }
    next();
  };

  // GET /health — minimal info, no auth required
  router.get("/health", async (_req, res) => {
    const { getBufferLength } = require("./redis");
    const bufferLength = state.redis ? await getBufferLength(state.redis) : 0;
    res.json({
      status: state.status,
      groups: state.groupCount || 0,
      buffer_length: bufferLength,
      uptime: Math.floor(process.uptime()),
    });
  });

  // GET /qr — QR code or pairing code page for WhatsApp pairing
  router.get("/qr", requireAuth, async (_req, res) => {
    if (state.status === "connected") {
      return res.send(
        "<html><body><h2>Already connected</h2>" +
        "<p>WhatsApp bridge is paired and running.</p></body></html>"
      );
    }
    if (state.status === "logged_out") {
      return res.send(
        "<html><body><h2>Session logged out</h2>" +
        "<p>Restart the bridge container to generate a new QR code.</p></body></html>"
      );
    }
    // Pairing code method
    if (state.pairingCode) {
      return res.send(
        "<html><body>" +
        "<h2>Enter Pairing Code in WhatsApp</h2>" +
        '<meta http-equiv="refresh" content="10">' +
        `<h1 style="font-size:3em;letter-spacing:0.3em;font-family:monospace">${state.pairingCode}</h1>` +
        "<p>Open WhatsApp > Settings > Linked Devices > Link a Device > Link with phone number</p>" +
        "<p>Enter the code shown above.</p>" +
        "</body></html>"
      );
    }
    // QR method
    if (!state.qr) {
      return res.send(
        "<html><body><h2>Waiting for QR...</h2>" +
        '<meta http-equiv="refresh" content="5">' +
        "<p>QR code is being generated. This page will auto-refresh.</p>" +
        "<p><b>Tip:</b> If QR doesn't appear, set WHATSAPP_PHONE_NUMBER env var to use pairing code instead.</p>" +
        "</body></html>"
      );
    }
    try {
      const qrDataUrl = await QRCode.toDataURL(state.qr, { width: 300 });
      res.send(
        "<html><body>" +
        "<h2>Scan QR Code with WhatsApp</h2>" +
        '<meta http-equiv="refresh" content="15">' +
        `<img src="${qrDataUrl}" alt="QR Code" />` +
        "<p>Open WhatsApp > Settings > Linked Devices > Link a Device</p>" +
        "<p>This page auto-refreshes every 15 seconds.</p>" +
        "</body></html>"
      );
    } catch (err) {
      log.error({ err: err.message }, "qr.render_failed");
      res.status(500).json({ error: "Failed to render QR code" });
    }
  });

  // GET /groups — list joined WhatsApp groups
  router.get("/groups", requireAuth, async (_req, res) => {
    if (!state.sock || state.status !== "connected") {
      return res.status(503).json({ error: "Not connected" });
    }
    try {
      const groups = await state.sock.groupFetchAllParticipating();
      const result = Object.values(groups).map((g) => ({
        jid: g.id,
        name: g.subject || g.id,
        participants_count: (g.participants || []).length,
      }));
      state.groupCount = result.length;
      res.json(result);
    } catch (err) {
      log.error({ err: err.message }, "groups.fetch_failed");
      res.status(500).json({ error: "Failed to fetch groups" });
    }
  });

  return router;
}

module.exports = { createRouter };
