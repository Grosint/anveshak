/**
 * Redis buffer for WhatsApp messages.
 *
 * Messages are RPUSH'd to a list key. LTRIM caps the buffer to prevent
 * unbounded growth when the Python adapter is down.
 */
const Redis = require("ioredis");
const pino = require("pino");

const log = pino({ name: "whatsapp-bridge-redis" });

const BUFFER_KEY = "anveshak:whatsapp:buffer";

/**
 * Create a Redis client with reconnect handling.
 * @param {string} redisUrl
 * @returns {Redis}
 */
function createRedisClient(redisUrl) {
  const client = new Redis(redisUrl, {
    retryStrategy: (times) => Math.min(times * 500, 5000),
    maxRetriesPerRequest: 3,
  });

  client.on("connect", () => log.info("redis.connected"));
  client.on("error", (err) => log.error({ err: err.message }, "redis.error"));

  return client;
}

/**
 * Push a message to the buffer and trim to max size.
 * @param {Redis} redis
 * @param {object} messageJson - Message object to serialize
 * @param {number} maxBuffer - Maximum buffer size
 */
async function pushMessage(redis, messageJson, maxBuffer) {
  try {
    await redis.rpush(BUFFER_KEY, JSON.stringify(messageJson));
    // Trim from left (oldest), keep newest maxBuffer entries
    await redis.ltrim(BUFFER_KEY, -maxBuffer, -1);
  } catch (err) {
    log.error({ err: err.message }, "redis.push_failed");
  }
}

/**
 * Push a logout sentinel to notify the Python adapter.
 * @param {Redis} redis
 */
async function pushLogoutSentinel(redis) {
  try {
    const sentinel = {
      _type: "logout",
      timestamp: Math.floor(Date.now() / 1000),
      reason: "logged_out",
    };
    await redis.rpush(BUFFER_KEY, JSON.stringify(sentinel));
  } catch (err) {
    log.error({ err: err.message }, "redis.logout_sentinel_failed");
  }
}

/**
 * Get current buffer length.
 * @param {Redis} redis
 * @returns {Promise<number>}
 */
async function getBufferLength(redis) {
  try {
    return await redis.llen(BUFFER_KEY);
  } catch {
    return -1;
  }
}

module.exports = { createRedisClient, pushMessage, pushLogoutSentinel, getBufferLength, BUFFER_KEY };
