// Cloudflare Pages Function — family sync for The Shared Table.
// A shared shopping list and weekly plan keyed by a short family code,
// stored in Workers KV (FAMILY binding in wrangler.toml). Last write wins;
// no accounts, no personal data — just the code.

const VALID_KEYS = ['shop', 'plan'];
const MAX_BYTES = 120000;

export async function onRequestPost({ request, env }) {
  try {
    if (!env.FAMILY) return json({ error: 'sync-unavailable' }, 503);
    const body = await request.json().catch(() => null);
    if (!body) return json({ error: 'bad-request' }, 400);

    const code = String(body.code || '').trim().toUpperCase();
    if (!/^[A-Z0-9-]{6,24}$/.test(code)) return json({ error: 'bad-code' }, 400);
    const key = String(body.key || '');
    if (!VALID_KEYS.includes(key)) return json({ error: 'bad-key' }, 400);
    const kvKey = 'fam:' + code + ':' + key;

    if (body.action === 'put') {
      const payload = JSON.stringify({ data: body.data, updatedAt: Date.now() });
      if (payload.length > MAX_BYTES) return json({ error: 'too-large' }, 413);
      await env.FAMILY.put(kvKey, payload);
      return json({ ok: true, updatedAt: Date.now() });
    }

    // default: get
    const stored = await env.FAMILY.get(kvKey, 'json');
    return json({ ok: true, data: stored ? stored.data : null, updatedAt: stored ? stored.updatedAt : 0 });
  } catch (err) {
    return json({ error: 'server-error' }, 500);
  }
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}
