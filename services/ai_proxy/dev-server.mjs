// Runs the AI proxy (src/worker.js) on this Mac for development, no packages needed.
//   node dev-server.mjs            → http://0.0.0.0:8787
// Secrets come from .dev.vars (git-ignored), the same file `wrangler dev` uses.
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import worker from './src/worker.js';

function loadEnv(path) {
  const env = {};
  try {
    for (const line of readFileSync(path, 'utf8').split('\n')) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
      if (m) env[m[1]] = m[2];
    }
  } catch {
    console.error('No .dev.vars found next to dev-server.mjs');
  }
  return { ...env, ...Object.fromEntries(Object.entries(process.env).filter(([k]) => k.startsWith('XAI_') || k === 'PROXY_TOKEN')) };
}

const env = loadEnv(new URL('./.dev.vars', import.meta.url));
const port = Number(process.env.PORT ?? 8787);

createServer(async (req, res) => {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const request = new Request(`http://localhost${req.url}`, {
    method: req.method,
    headers: req.headers,
    body: ['GET', 'HEAD'].includes(req.method) ? undefined : Buffer.concat(chunks),
  });
  const response = await worker.fetch(request, env);
  res.writeHead(response.status, Object.fromEntries(response.headers));
  res.end(Buffer.from(await response.arrayBuffer()));
}).listen(port, '0.0.0.0', () => {
  console.log(`AI proxy listening on http://0.0.0.0:${port} (key configured: ${Boolean(env.XAI_API_KEY)})`);
});
