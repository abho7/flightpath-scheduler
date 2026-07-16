const BASE = "/api";

async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchCatalogList() {
  return handle(await fetch(`${BASE}/catalogs`));
}

export async function fetchCatalog(catalogId) {
  return handle(await fetch(`${BASE}/catalog/${catalogId}`));
}

export async function fetchHealth() {
  return handle(await fetch(`${BASE}/health`));
}

export async function solveSchedule(payload) {
  return handle(
    await fetch(`${BASE}/solve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}
