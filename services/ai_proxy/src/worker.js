/**
 * Smart Spectator AI proxy.
 *
 * The only component that holds the xAI API key. The main phone sends one
 * JPEG snapshot; the proxy asks xAI for a structured description and returns
 * it. Images are never stored or logged, and xAI is asked not to store the
 * request (`store: false`).
 *
 * Runs as a Cloudflare Worker (`wrangler deploy`) or locally with
 * `node dev-server.mjs` (same code, secrets read from .dev.vars).
 *
 * Environment:
 *   XAI_API_KEY                      required, secret
 *   PROXY_TOKEN                      required, secret; callers send "Authorization: Bearer <token>"
 *   XAI_MODEL                        optional, default "grok-4.7"
 *   XAI_BASE_URL                     optional, default "https://api.x.ai/v1" (tests point it at a fake)
 *   DAILY_REQUEST_LIMIT              optional, default 300 analyses per day (cost cap)
 *   PER_CAMERA_MIN_INTERVAL_SECONDS  optional, default 20
 */

export const CATEGORIES = ['person', 'vehicle', 'animal', 'package', 'motion_other', 'no_activity', 'camera_problem'];
export const THREAT_LEVELS = ['none', 'low', 'medium', 'high'];
const MAX_IMAGE_BYTES = 2 * 1024 * 1024;

const INSIGHT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    summary: { type: 'string', description: 'One plain sentence, at most 20 words, describing what is happening.' },
    category: { type: 'string', enum: CATEGORIES },
    threat_level: { type: 'string', enum: THREAT_LEVELS },
    people_count: { type: 'integer', minimum: 0 },
    confidence: { type: 'number', minimum: 0, maximum: 1 },
  },
  required: ['summary', 'category', 'threat_level', 'people_count', 'confidence'],
};

const PROMPT = [
  'You are the analysis engine of a home security camera app.',
  'The image is a snapshot taken because the camera detected motion.',
  'Describe only what is visible; never guess identities, names, age, race, or other sensitive traits.',
  'Use category "no_activity" if nothing meaningful is happening (e.g. lighting change, shadows),',
  'and "camera_problem" if the view is blocked, black, or unusable.',
  'threat_level: "none" for normal activity, "high" only for clear danger such as fire, a weapon, or forced entry.',
].join(' ');

// Best-effort limits. In-memory: per process locally, per isolate on Workers.
// Production should move these to Durable Objects or KV.
const state = { day: '', count: 0, lastByCamera: new Map() };

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

function timingSafeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function decodeBase64(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Validates the model's JSON so the app only ever sees the agreed shape. */
export function normaliseInsight(raw) {
  const o = typeof raw === 'string' ? JSON.parse(raw) : raw;
  const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, Number.isFinite(n) ? n : lo));
  if (typeof o?.summary !== 'string' || !o.summary.trim()) throw new Error('missing summary');
  return {
    summary: o.summary.trim().slice(0, 200),
    category: CATEGORIES.includes(o.category) ? o.category : 'motion_other',
    threat_level: THREAT_LEVELS.includes(o.threat_level) ? o.threat_level : 'none',
    people_count: Math.round(clamp(o.people_count, 0, 100)),
    confidence: clamp(Number(o.confidence), 0, 1),
  };
}

async function analyze(request, env, now) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json(400, { error: 'invalid_json' });
  }
  const b64 = body?.image_jpeg_base64;
  if (typeof b64 !== 'string' || !b64) return json(400, { error: 'image_jpeg_base64 required' });
  let bytes;
  try {
    bytes = decodeBase64(b64);
  } catch {
    return json(400, { error: 'image is not valid base64' });
  }
  if (bytes.length > MAX_IMAGE_BYTES) return json(413, { error: 'image too large' });
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return json(400, { error: 'image must be a JPEG' });

  const cameraId = String(body.camera_id ?? 'unknown').slice(0, 64);
  const cameraName = String(body.camera_name ?? 'Camera').slice(0, 64);

  // Cost controls: per-camera spacing and a daily cap.
  const today = new Date(now).toISOString().slice(0, 10);
  if (state.day !== today) {
    state.day = today;
    state.count = 0;
  }
  const limit = Number(env.DAILY_REQUEST_LIMIT ?? 300);
  if (state.count >= limit) return json(429, { error: 'daily_limit_reached', limit });
  const minInterval = Number(env.PER_CAMERA_MIN_INTERVAL_SECONDS ?? 20) * 1000;
  const last = state.lastByCamera.get(cameraId);
  if (last && now - last < minInterval) {
    return json(429, { error: 'too_frequent', retry_after_seconds: Math.ceil((minInterval - (now - last)) / 1000) });
  }
  state.lastByCamera.set(cameraId, now);
  state.count++;

  const model = env.XAI_MODEL || 'grok-4.7';
  const started = Date.now();
  let upstream;
  try {
    upstream = await fetch(`${env.XAI_BASE_URL || 'https://api.x.ai/v1'}/responses`, {
      method: 'POST',
      headers: { authorization: `Bearer ${env.XAI_API_KEY}`, 'content-type': 'application/json' },
      body: JSON.stringify({
        model,
        store: false,
        input: [
          {
            role: 'user',
            content: [
              { type: 'input_image', image_url: `data:image/jpeg;base64,${b64}`, detail: 'low' },
              { type: 'input_text', text: `${PROMPT} Camera name: "${cameraName}".` },
            ],
          },
        ],
        text: { format: { type: 'json_schema', name: 'camera_insight', schema: INSIGHT_SCHEMA, strict: true } },
      }),
    });
  } catch {
    return json(502, { error: 'ai_unreachable' });
  }

  if (!upstream.ok) {
    // Never forward upstream bodies (could echo request data); map to stable codes.
    const code = upstream.status === 401 || upstream.status === 403 ? 'ai_not_authorised' : upstream.status === 429 ? 'ai_rate_limited' : 'ai_error';
    console.log(JSON.stringify({ event: 'xai_error', status: upstream.status, camera: cameraId }));
    return json(502, { error: code, upstream_status: upstream.status });
  }

  try {
    const data = await upstream.json();
    const message = (data.output ?? []).find((o) => o.type === 'message');
    const text = (message?.content ?? []).find((c) => c.type === 'output_text')?.text;
    const insight = normaliseInsight(text);
    console.log(JSON.stringify({ event: 'analysed', camera: cameraId, category: insight.category, ms: Date.now() - started }));
    return json(200, { ...insight, model: data.model ?? model, latency_ms: Date.now() - started });
  } catch {
    return json(502, { error: 'ai_bad_response' });
  }
}

export function resetLimitsForTests() {
  state.day = '';
  state.count = 0;
  state.lastByCamera.clear();
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/health' && request.method === 'GET') {
      return json(200, { status: 'ok', service: 'smart-spectator-ai-proxy', configured: Boolean(env.XAI_API_KEY && env.PROXY_TOKEN) });
    }
    if (url.pathname !== '/v1/analyze' || request.method !== 'POST') return json(404, { error: 'not_found' });
    if (!env.XAI_API_KEY || !env.PROXY_TOKEN) return json(503, { error: 'proxy_not_configured' });

    const auth = request.headers.get('authorization') ?? '';
    const token = auth.toLowerCase().startsWith('bearer ') ? auth.slice(7).trim() : '';
    if (!timingSafeEqual(token, env.PROXY_TOKEN)) return json(401, { error: 'unauthorised' });

    const length = Number(request.headers.get('content-length') ?? 0);
    if (length > MAX_IMAGE_BYTES * 1.5) return json(413, { error: 'request too large' });

    return analyze(request, env, Date.now());
  },
};
