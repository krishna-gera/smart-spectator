import { test, beforeEach, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import worker, { normaliseInsight, resetLimitsForTests } from '../src/worker.js';

const JPEG_B64 = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3, 0xff, 0xd9]).toString('base64');

// Fake xAI: records requests and replies like the Responses API.
const seen = [];
let reply = { status: 200, text: JSON.stringify({ summary: 'A person walks to the door.', category: 'person', threat_level: 'none', people_count: 1, confidence: 0.9 }) };
const fake = createServer(async (req, res) => {
  let raw = '';
  for await (const c of req) raw += c;
  seen.push({ path: req.url, auth: req.headers.authorization, body: JSON.parse(raw) });
  res.writeHead(reply.status, { 'content-type': 'application/json' });
  res.end(JSON.stringify({ model: 'grok-test', output: [{ type: 'message', content: [{ type: 'output_text', text: reply.text }] }] }));
});
await new Promise((r) => fake.listen(0, '127.0.0.1', r));
after(() => fake.close());

const env = {
  XAI_API_KEY: 'xai-test-key',
  PROXY_TOKEN: 'proxy-test-token',
  XAI_BASE_URL: `http://127.0.0.1:${fake.address().port}`,
  DAILY_REQUEST_LIMIT: '3',
  PER_CAMERA_MIN_INTERVAL_SECONDS: '20',
};

const call = (body, { token = env.PROXY_TOKEN, e = env } = {}) =>
  worker.fetch(
    new Request('http://proxy/v1/analyze', {
      method: 'POST',
      headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
      body: typeof body === 'string' ? body : JSON.stringify(body),
    }),
    e,
  );

beforeEach(() => {
  seen.length = 0;
  resetLimitsForTests();
  reply = { status: 200, text: JSON.stringify({ summary: 'A person walks to the door.', category: 'person', threat_level: 'none', people_count: 1, confidence: 0.9 }) };
});

test('returns a structured insight and keeps the key server-side', async () => {
  const res = await call({ image_jpeg_base64: JPEG_B64, camera_id: 'cam_a', camera_name: 'Front door' });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.summary, 'A person walks to the door.');
  assert.equal(body.category, 'person');
  assert.equal(body.people_count, 1);
  assert.equal(body.model, 'grok-test');
  assert.ok(!JSON.stringify(body).includes('xai-test-key'));

  const sent = seen[0];
  assert.equal(sent.path, '/responses');
  assert.equal(sent.auth, 'Bearer xai-test-key');
  assert.equal(sent.body.store, false, 'xAI must be told not to store the request');
  assert.equal(sent.body.text.format.type, 'json_schema');
  assert.ok(sent.body.input[0].content[0].image_url.startsWith('data:image/jpeg;base64,'));
});

test('rejects missing or wrong proxy token', async () => {
  assert.equal((await call({ image_jpeg_base64: JPEG_B64 }, { token: 'nope' })).status, 401);
  assert.equal(seen.length, 0);
});

test('rejects non-JPEG and malformed input without calling xAI', async () => {
  assert.equal((await call({ image_jpeg_base64: Buffer.from('hello').toString('base64') })).status, 400);
  assert.equal((await call({})).status, 400);
  assert.equal((await call('{bad json')).status, 400);
  assert.equal(seen.length, 0);
});

test('spaces out requests per camera and caps the day', async () => {
  assert.equal((await call({ image_jpeg_base64: JPEG_B64, camera_id: 'a' })).status, 200);
  const tooSoon = await call({ image_jpeg_base64: JPEG_B64, camera_id: 'a' });
  assert.equal(tooSoon.status, 429);
  assert.equal((await tooSoon.json()).error, 'too_frequent');
  assert.equal((await call({ image_jpeg_base64: JPEG_B64, camera_id: 'b' })).status, 200);
  assert.equal((await call({ image_jpeg_base64: JPEG_B64, camera_id: 'c' })).status, 200);
  const capped = await call({ image_jpeg_base64: JPEG_B64, camera_id: 'd' });
  assert.equal(capped.status, 429);
  assert.equal((await capped.json()).error, 'daily_limit_reached');
});

test('maps xAI failures to stable errors without leaking upstream bodies', async () => {
  reply = { status: 403, text: 'secret upstream detail' };
  const res = await call({ image_jpeg_base64: JPEG_B64, camera_id: 'x' });
  assert.equal(res.status, 502);
  const body = await res.json();
  assert.equal(body.error, 'ai_not_authorised');
  assert.ok(!JSON.stringify(body).includes('secret upstream detail'));
});

test('a malformed model answer is reported, not passed through', async () => {
  reply = { status: 200, text: 'not json' };
  const res = await call({ image_jpeg_base64: JPEG_B64, camera_id: 'y' });
  assert.equal(res.status, 502);
  assert.equal((await res.json()).error, 'ai_bad_response');
});

test('normaliseInsight clamps and fixes out-of-range values', () => {
  const n = normaliseInsight({ summary: '  Cat on sofa  ', category: 'dragon', threat_level: 'extreme', people_count: -3, confidence: 7 });
  assert.deepEqual(n, { summary: 'Cat on sofa', category: 'motion_other', threat_level: 'none', people_count: 0, confidence: 1 });
  assert.throws(() => normaliseInsight({ summary: '' }));
});

test('health reports configuration without exposing secrets', async () => {
  const res = await worker.fetch(new Request('http://proxy/health'), env);
  const body = await res.json();
  assert.deepEqual(body, { status: 'ok', service: 'smart-spectator-ai-proxy', configured: true });
});

test('refuses to run without secrets', async () => {
  const res = await call({ image_jpeg_base64: JPEG_B64 }, { e: { PROXY_TOKEN: 'proxy-test-token' } });
  assert.equal(res.status, 503);
});
