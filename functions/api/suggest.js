// Cloudflare Pages Function — AI Chef for The Shared Table meal-plan site.
// Receives ingredients the user likes plus a condensed catalogue of the
// site's recipes, and uses Workers AI (env.AI binding, configured in
// wrangler.toml) to pick the best matches and pitch one new recipe idea.
// If the AI binding is missing the client falls back to local matching.

export async function onRequestPost({ request, env }) {
  try {
    const data = await request.json().catch(() => null);
    if (!data) return json({ error: 'invalid-request' }, 400);

    const ingredients = (Array.isArray(data.ingredients) ? data.ingredients : [])
      .map((s) => String(s).replace(/[^\w\s&'-]/g, '').trim().slice(0, 40))
      .filter(Boolean)
      .slice(0, 15);

    const catalog = (Array.isArray(data.catalog) ? data.catalog : [])
      .slice(0, 40)
      .map((r) => ({
        id: String(r.id || '').slice(0, 8),
        title: String(r.title || '').slice(0, 90),
        ing: String(r.ing || '').slice(0, 220),
      }))
      .filter((r) => r.id && r.title);

    if (!ingredients.length) return json({ error: 'no-ingredients' }, 400);
    if (!env.AI) return json({ error: 'ai-unavailable' }, 503);

    const recipeList = catalog
      .map((r) => `- id "${r.id}": ${r.title} (key ingredients: ${r.ing})`)
      .join('\n');

    const prompt = `You are the resident chef for "The Shared Table", a high-protein family recipe site (UK supermarket ingredients, one adult on ~2,000 kcal with 150g+ protein per day, one teenage daughter who eats the same meals with bigger carb portions).

The site's recipes:
${recipeList}

The family likes or has these ingredients: ${ingredients.join(', ')}.

Reply with STRICT JSON only, no markdown fences, exactly this shape:
{"matches":[{"id":"<recipe id>","reason":"<one warm, specific sentence on why it fits their ingredients>"}],"idea":{"title":"<an appetising new high-protein recipe name using their ingredients>","description":"<2-3 sentences describing it: key ingredients with rough amounts, method in brief, why the teenager will like it>"}}

Rules: up to 3 matches, best first, only ids from the list, only include a match if it genuinely uses their ingredients. The idea must be realistic for a UK supermarket, high in protein, and not ultra-processed.`;

    const result = await env.AI.run('@cf/meta/llama-3.1-8b-instruct-fast', {
      messages: [
        { role: 'system', content: 'You are a helpful family chef. You reply with strict, valid JSON only — no markdown, no commentary.' },
        { role: 'user', content: prompt },
      ],
      max_tokens: 700,
    });

    // Workers AI models return either { response } or OpenAI-style { choices };
    // content may be a string or an array of { text } parts.
    const rawContent = (result && result.response)
      || (result && result.choices && result.choices[0] && result.choices[0].message && result.choices[0].message.content)
      || '';
    const text = typeof rawContent === 'string'
      ? rawContent
      : Array.isArray(rawContent)
        ? rawContent.map((p) => (typeof p === 'string' ? p : (p && p.text) || '')).join('')
        : JSON.stringify(rawContent);
    let parsed = null;
    try {
      const m = text.match(/\{[\s\S]*\}/);
      if (m) parsed = JSON.parse(m[0]);
    } catch (_) { /* fall through to raw */ }

    if (parsed && (Array.isArray(parsed.matches) || parsed.idea)) {
      const validIds = new Set(catalog.map((r) => r.id));
      const matches = (parsed.matches || [])
        .filter((m) => m && validIds.has(String(m.id)))
        .slice(0, 3)
        .map((m) => ({ id: String(m.id), reason: String(m.reason || '').slice(0, 300) }));
      const idea = parsed.idea
        ? { title: String(parsed.idea.title || '').slice(0, 120), description: String(parsed.idea.description || '').slice(0, 600) }
        : null;
      return json({ ok: true, matches, idea });
    }

    return json({ ok: true, matches: [], idea: null, raw: text.slice(0, 800) });
  } catch (err) {
    return json({ error: 'server-error', detail: String(err && err.message || err).slice(0, 300) }, 500);
  }
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}
