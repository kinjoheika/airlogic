// AirLogic Field Entry: works offline. Data is cached on the phone; inspection
// values entered offline are queued and sent to Supabase when the phone is online.
(function () {
  "use strict";
  const cfg = window.AIRLOGIC_CONFIG || {};
  const sb = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey);
  const page = document.getElementById("page");
  const bar = document.getElementById("bar");
  const syncEl = document.getElementById("sync");
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---------- local storage (IndexedDB) ----------
  function idb() {
    return new Promise((res, rej) => {
      const r = indexedDB.open("airlogic-field", 1);
      r.onupgradeneeded = () => { r.result.createObjectStore("kv"); r.result.createObjectStore("outbox", { keyPath: "id" }); };
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  }
  async function kvGet(k) {
    const d = await idb();
    return new Promise((res, rej) => { const q = d.transaction("kv").objectStore("kv").get(k); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); });
  }
  async function kvSet(k, v) {
    const d = await idb();
    return new Promise((res, rej) => { const t = d.transaction("kv", "readwrite"); t.objectStore("kv").put(v, k); t.oncomplete = res; t.onerror = () => rej(t.error); });
  }
  async function outPut(item) {
    const d = await idb();
    return new Promise((res, rej) => { const t = d.transaction("outbox", "readwrite"); t.objectStore("outbox").put(item); t.oncomplete = res; t.onerror = () => rej(t.error); });
  }
  async function outAll() {
    const d = await idb();
    return new Promise((res, rej) => { const q = d.transaction("outbox").objectStore("outbox").getAll(); q.onsuccess = () => res(q.result || []); q.onerror = () => rej(q.error); });
  }
  async function outDel(id) {
    const d = await idb();
    return new Promise((res, rej) => { const t = d.transaction("outbox", "readwrite"); t.objectStore("outbox").delete(id); t.oncomplete = res; t.onerror = () => rej(t.error); });
  }

  // ---------- server -> phone (download the visits and their units) ----------
  async function downloadAll() {
    const { data: visits, error } = await sb.from("service_visits")
      .select("id,reference,visit_date,state,sublocation,technician_name,clients(name)")
      .order("visit_date", { ascending: false }).limit(60);
    if (error) throw error;
    const out = [];
    for (const v of visits || []) {
      const { data: jobs, error: je } = await sb.from("service_jobs")
        .select("id, equipment(name, model, serial_number, sublocations(name)), checklist_lines(id, phase, key, label, value, section, standard)")
        .eq("visit_id", v.id);
      if (je) throw je;
      out.push({ visit: v, jobs: jobs || [] });
    }
    await kvSet("visits", out);
    await kvSet("cachedAt", new Date().toISOString());
    return out;
  }
  async function cachedVisits() { return (await kvGet("visits")) || []; }

  // ---------- phone -> server (send queued values) ----------
  async function sendQueue() {
    if (!navigator.onLine) return;
    const items = await outAll();
    for (const it of items) {
      const { error } = await sb.from("checklist_lines").update({ value: it.value }).eq("id", it.id);
      if (error) break; // keep the rest for the next try
      await outDel(it.id);
    }
    await showStatus();
  }
  async function showStatus() {
    const waiting = (await outAll()).length;
    if (!navigator.onLine) { syncEl.className = "sync wait"; syncEl.textContent = waiting ? `Offline · ${waiting} to sync` : "Offline"; return; }
    if (waiting) { syncEl.className = "sync wait"; syncEl.textContent = `${waiting} to sync`; }
    else { syncEl.className = "sync ok"; syncEl.textContent = "Synced"; }
  }

  // ---------- screens ----------
  let state = { view: "visits" };

  function jobDone(j) { return (j.checklist_lines || []).length > 0 && (j.checklist_lines || []).every((c) => c.value != null); }

  function renderVisits(visits) {
    bar.classList.add("hidden");
    if (!visits.length) { page.innerHTML = `<div class="notice">No visits downloaded yet. Connect to the internet and tap <b>Download</b>.</div>`; return; }
    page.innerHTML = `<div class="title">Visits</div>` + `<div class="card">` + visits.map((x, i) => {
      const done = x.jobs.filter(jobDone).length;
      return `<button class="row" data-visit="${i}">
        <div><div class="t">${esc(x.visit.clients?.name)}</div><div class="s">${esc(x.visit.reference)} · ${esc(x.visit.sublocation) || "—"}</div></div>
        <span class="pill ${done === x.jobs.length && x.jobs.length ? "p-done" : "p-pending"}">${done} of ${x.jobs.length}</span></button>`;
    }).join("") + `</div>`;
    page.querySelectorAll("[data-visit]").forEach((b) => b.onclick = () => { state = { view: "units", visit: Number(b.dataset.visit) }; render(); });
  }

  function renderUnits(visits) {
    const x = visits[state.visit];
    bar.classList.add("hidden");
    const rooms = new Map();
    x.jobs.forEach((j, i) => { const r = j.equipment?.sublocations?.name || "Unassigned"; if (!rooms.has(r)) rooms.set(r, []); rooms.get(r).push(i); });
    page.innerHTML = `<button class="back" data-back>← Visits</button>
      <div class="title">${esc(x.visit.clients?.name)}</div>
      <div class="card">` + [...rooms.entries()].map(([room, idxs]) => `
        <div class="room">${esc(room)}</div>
        ${idxs.map((i) => { const j = x.jobs[i]; const d = jobDone(j); return `<button class="row" data-unit="${i}">
          <div><div class="t">${esc(j.equipment?.name)}</div><div class="s">${esc(j.equipment?.serial_number)} · ${esc(j.equipment?.model)}</div></div>
          <span class="pill ${d ? "p-done" : "p-pending"}">${d ? "Completed" : "Pending"}</span></button>`; }).join("")}
      `).join("") + `</div>`;
    page.querySelector("[data-back]").onclick = () => { state = { view: "visits" }; render(); };
    page.querySelectorAll("[data-unit]").forEach((b) => b.onclick = () => { state = { view: "unit", visit: state.visit, unit: Number(b.dataset.unit) }; render(); });
  }

  function renderUnit(visits) {
    const x = visits[state.visit];
    const j = x.jobs[state.unit];
    const items = (j.checklist_lines || []).slice().sort((a, b) => (a.phase ?? 0) - (b.phase ?? 0) || String(a.key).localeCompare(String(b.key)));
    const groups = []; items.forEach((c) => { let g = groups.find((y) => y.name === c.section); if (!g) { g = { name: c.section, rows: [] }; groups.push(g); } g.rows.push(c); });
    page.innerHTML = `<button class="back" data-back>← Units</button>
      <div class="title">${esc(j.equipment?.name)}</div>
      <div class="s" style="color:#6b7587;margin:-6px 2px 10px">${esc(j.equipment?.serial_number)} · ${esc(j.equipment?.sublocations?.name)}</div>
      <div class="card" id="form">` + groups.map((g) => `<div class="sec">${esc(g.name)}</div>` +
        g.rows.map((c) => `<div class="item"><label>${esc(c.label)}</label><small>Standard: ${esc(c.standard) || "—"}</small>
          <input data-cid="${esc(c.id)}" value="${esc(c.value ?? "")}" placeholder="${esc(c.standard) || "Enter value"}" inputmode="text"></div>`).join("")).join("") +
      `</div><div class="msg" id="msg"></div>`;
    bar.classList.remove("hidden");
    bar.innerHTML = `<button class="btn ghost" data-back>Cancel</button><button class="btn primary" id="save">Save inspection</button>`;
    bar.querySelectorAll("[data-back]").forEach((b) => b.onclick = () => { state = { view: "units", visit: state.visit }; render(); });
    page.querySelector("[data-back]").onclick = () => { state = { view: "units", visit: state.visit }; render(); };
    document.getElementById("save").onclick = () => saveUnit(visits, x, j);
  }

  async function saveUnit(visits, x, j) {
    const msg = document.getElementById("msg");
    const inputs = [...document.querySelectorAll("[data-cid]")];
    let changed = 0;
    for (const el of inputs) {
      const id = el.dataset.cid;
      const val = el.value.trim() || null;
      const row = (j.checklist_lines || []).find((c) => String(c.id) === id);
      if (!row || (row.value ?? null) === val) continue;
      row.value = val;
      await outPut({ id, value: val, savedAt: new Date().toISOString() }); // queued, safe offline
      changed++;
    }
    await kvSet("visits", visits); // keep the phone copy up to date
    msg.textContent = "";
    await sendQueue();
    msg.style.color = "#1a7f4b";
    msg.textContent = changed ? (navigator.onLine ? "Inspection saved" : "Saved on this phone. It will sync when you're online.") : "No changes to save.";
    await showStatus();
  }

  async function render() {
    const visits = await cachedVisits();
    if (state.view === "units") return renderUnits(visits);
    if (state.view === "unit") return renderUnit(visits);
    return renderVisits(visits);
  }

  // ---------- sign in and start ----------
  function renderLogin() {
    bar.classList.add("hidden");
    page.innerHTML = `<div class="login card"><div class="title">Sign in</div>
      <label>Email</label><input id="em" type="email" autocomplete="username">
      <label>Password</label><input id="pw" type="password" autocomplete="current-password">
      <button class="btn primary" id="go" style="width:100%">Sign in</button>
      <div class="msg" id="lm"></div></div>`;
    document.getElementById("go").onclick = async () => {
      const { error } = await sb.auth.signInWithPassword({ email: document.getElementById("em").value.trim(), password: document.getElementById("pw").value });
      if (error) { document.getElementById("lm").textContent = error.message; return; }
      start();
    };
  }

  async function downloadNow() {
    if (!navigator.onLine) return;
    syncEl.className = "sync wait"; syncEl.textContent = "Downloading…";
    try { await downloadAll(); await sendQueue(); } catch (e) { syncEl.className = "sync wait"; syncEl.textContent = "Download failed"; }
    await showStatus();
    render();
  }

  async function start() {
    const { data: { session } } = await sb.auth.getSession();
    const cached = await cachedVisits();
    if (!session && navigator.onLine) return renderLogin();
    if (!session && !cached.length) { page.innerHTML = `<div class="notice">Connect to the internet once and sign in to download the visits. After that the app works offline.</div>`; return; }
    if (navigator.onLine && session) { try { await downloadAll(); } catch (e) { /* keep the cached copy */ } }
    await sendQueue();
    await showStatus();
    render();
  }

  window.addEventListener("online", async () => { await sendQueue(); await showStatus(); });
  window.addEventListener("offline", showStatus);
  window.addEventListener("pagehide", () => {});
  const dl = document.createElement("button");
  dl.className = "btn ghost"; dl.textContent = "Download"; dl.style.cssText = "min-height:36px;padding:0 10px;font-size:13px";
  dl.onclick = downloadNow;
  document.querySelector("header.top").appendChild(dl);

  start();
})();
