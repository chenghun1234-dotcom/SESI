/**
 * SESI Monetization Gateway - Cloudflare Worker
 * This worker fetches the static SESI index from GitHub and serves it as a professional API.
 */

const GITHUB_RAW_URL = "https://raw.githubusercontent.com/chenghun1234-dotcom/SESI/main/public/api/sesi_index.json";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Fetch the raw data from GitHub
    const response = await fetch(GITHUB_RAW_URL, {
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'SESI-Gateway-Worker'
      }
    });

    if (!response.ok) {
      return new Response(JSON.stringify({ error: "Failed to fetch index data" }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    const data = await response.json();

    // Route: /index
    if (path === "/index" || path === "/") {
      return new Response(JSON.stringify(data), {
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      });
    }

    // Route: /scores
    if (path === "/scores") {
      return new Response(JSON.stringify({ 
        metadata: data.metadata,
        scores: data.scores 
      }), {
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      });
    }

    // Route: /fees/:country
    const feeMatch = path.match(/\/fees\/(KR|JP)/i);
    if (feeMatch) {
      const country = feeMatch[1].toUpperCase();
      return new Response(JSON.stringify({
        country: country,
        data: data.countries[country]
      }), {
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      });
    }

    return new Response(JSON.stringify({ error: "Endpoint not found" }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
