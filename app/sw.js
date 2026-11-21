// Service worker: lets the field app open with no internet after the first visit.
const CACHE = "airlogic-field-v1";
const SHELL = ["./field.html", "./field.js", "./manifest.webmanifest", "./icon.svg", "./config.js"];
const CDN = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js";

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await Promise.all(SHELL.map((u) => cache.add(u).catch(() => {})));
    await cache.add(new Request(CDN, { mode: "no-cors" })).catch(() => {});
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // Live data (Supabase) always goes to the network; the phone keeps its own copy.
  if (url.hostname.endsWith("supabase.co")) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const hit = await cache.match(req, { ignoreSearch: true });
    if (hit) return hit;
    try {
      const res = await fetch(req);
      if (res && (res.ok || res.type === "opaque")) cache.put(req, res.clone()).catch(() => {});
      return res;
    } catch (e) {
      if (req.mode === "navigate") return (await cache.match("./field.html")) || Response.error();
      return Response.error();
    }
  })());
});
