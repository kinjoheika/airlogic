// AirLogic Field Entry: works offline. Data is cached on the phone; values entered
// offline are queued and sent to Supabase when the phone is back online.
(function () {
  "use strict";
  const cfg = window.AIRLOGIC_CONFIG || {};
  const sb = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey);
  const page = document.getElementById("page");
  const nav = document.getElementById("nav");
  const saveBar = document.getElementById("savebar");
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

  // ---------- server -> phone ----------
  async function downloadAll() {
    const { data: visits, error } = await sb.from("service_visits")
      .select("id,reference,visit_date,state,sublocation,technician_name,clients(name)")
      .order("visit_date", { ascending: false }).limit(60);
    if (error) throw error;
    const out = [];
    for (const v of visits || []) {
      const { data: jobs, error: je } = await sb.from("service_jobs")
        .select("id, equipment(name, model, serial_number, install_year, sublocations(name)), checklist_lines(id, phase, key, label, value, section, standard)")
        .eq("visit_id", v.id);
      if (je) throw je;
      out.push({ visit: v, jobs: jobs || [] });
    }
    await kvSet("visits", out);
    await kvSet("cachedAt", new Date().toISOString());
    return out;
  }
  async function cachedVisits() { return (await kvGet("visits")) || []; }

  // ---------- phone -> server ----------
  async function sendQueue() {
    if (!navigator.onLine) return;
    const items = await outAll();
    for (const it of items) {
      const { error } = await sb.from("checklist_lines").update({ value: it.value }).eq("id", it.id);
      if (error) break;
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

  // ---------- helpers ----------
  const jobDone = (j) => (j.checklist_lines || []).length > 0 && (j.checklist_lines || []).every((c) => c.value != null);
  const doneCount = (x) => x.jobs.filter(jobDone).length;
  let st = { tab: "visit", visit: null, unit: null };

  function setNav() {
    nav.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.tab === st.tab));
  }

  // ---------- screens ----------
  function visitList(visits) {
    if (!visits.length) return `<div class="notice">No visits downloaded yet. Connect to the internet and tap <b>Download</b>.</div>`;
    return `<div class="title">Visits</div><div class="card">` + visits.map((x, i) => `
      <button class="vrow" data-visit="${i}">
        <div><div class="t">${esc(x.visit.clients?.name)}</div><div class="s">${esc(x.visit.reference)} · ${esc(x.visit.sublocation) || "—"}</div></div>
        <span class="pill ${doneCount(x) === x.jobs.length && x.jobs.length ? "p-done" : "p-pending"}">${doneCount(x)} / ${x.jobs.length}</span>
      </button>`).join("") + `</div>`;
  }

  function visitDetail(visits) {
    const x = visits[st.visit];
    const done = doneCount(x), total = x.jobs.length, pct = total ? Math.round((done / total) * 100) : 0;
    const rooms = new Map();
    x.jobs.forEach((j, i) => { const r = j.equipment?.sublocations?.name || "Unassigned"; if (!rooms.has(r)) rooms.set(r, []); rooms.get(r).push(i); });
    return `<button class="back" data-back-visits>← All visits</button>
      <div class="hd">
        <h1>${esc(x.visit.clients?.name)}</h1>
        <div class="sub">${total} devices · ${esc(x.visit.reference)}</div>
        <div class="prog"><span>${done} / ${total}</span><div class="bar"><span style="width:${pct}%"></span></div></div>
      </div>
      <div class="actions">
        <button class="btn" data-newjob>+ New Service Job</button>
        <button class="btn good" data-closejob>✓ Close Job</button>
      </div>
      <button class="nfc" data-scroll-devices>
        <span class="ic">📱</span>
        <div><b>Tap NFC — Start Device Entry</b><small>Or select device from list below</small></div>
        <span class="chev">›</span>
      </button>
      <div id="devices">
      ${[...rooms.entries()].map(([room, idxs]) => `
        <div class="room">${esc(room)}</div>
        <div class="card">${idxs.map((i) => {
          const j = x.jobs[i];
          const d = jobDone(j);
          return `<button class="dev" data-unit="${i}">
            <div><div class="t">${esc(j.equipment?.name)}</div>
              <div class="s">…${esc(String(j.equipment?.serial_number || "").replace(/^…/, ""))} · ${esc(j.equipment?.model)}${j.equipment?.install_year ? " · " + esc(j.equipment.install_year) : ""}</div></div>
            <span class="pill ${d ? "p-done" : "p-pending"}">${d ? "DONE" : "PENDING"}</span></button>`;
        }).join("")}</div>`).join("")}
      </div>`;
  }

  function unitsView(visits) {
    if (!visits.length) return `<div class="notice">No visits downloaded yet.</div>`;
    return visits.map((x, vi) => `<div class="title">${esc(x.visit.clients?.name)}</div>
      <div class="card">${x.jobs.map((j, ji) => `<button class="dev" data-vunit="${vi}:${ji}">
        <div><div class="t">${esc(j.equipment?.name)}</div><div class="s">…${esc(String(j.equipment?.serial_number || "").replace(/^…/, ""))} · ${esc(j.equipment?.sublocations?.name)}</div></div>
        <span class="pill ${jobDone(j) ? "p-done" : "p-pending"}">${jobDone(j) ? "DONE" : "PENDING"}</span></button>`).join("")}</div>`).join("");
  }

  function historyView(visits) {
    const done = [];
    visits.forEach((x, vi) => x.jobs.forEach((j, ji) => { if (jobDone(j)) done.push({ j, vi, ji, x }); }));
    if (!done.length) return `<div class="notice">No completed units yet.</div>`;
    return `<div class="title">Completed units</div><div class="card">${done.map((d) => `<button class="dev" data-vunit="${d.vi}:${d.ji}">
      <div><div class="t">${esc(d.j.equipment?.name)}</div><div class="s">${esc(d.x.visit.clients?.name)} · ${esc(d.x.visit.reference)}</div></div>
      <span class="pill p-done">DONE</span></button>`).join("")}</div>`;
  }

  function unitForm(visits) {
    const x = visits[st.visit];
    const j = x.jobs[st.unit];
    const items = (j.checklist_lines || []).slice().sort((a, b) => (a.phase ?? 0) - (b.phase ?? 0) || String(a.key).localeCompare(String(b.key)));
    const groups = []; items.forEach((c) => { let g = groups.find((y) => y.name === c.section); if (!g) { g = { name: c.section, rows: [] }; groups.push(g); } g.rows.push(c); });
    return `<button class="back" data-back-unit>← ${esc(x.visit.clients?.name)}</button>
      <div class="title">${esc(j.equipment?.name)}</div>
      <div class="sub" style="color:#6b7587;margin:-6px 2px 10px">…${esc(String(j.equipment?.serial_number || "").replace(/^…/, ""))} · ${esc(j.equipment?.sublocations?.name)}</div>
      <div class="card">` + groups.map((g) => `<div class="sec">${esc(g.name)}</div>` +
        g.rows.map((c) => `<div class="item"><label>${esc(c.label)}</label><small>Standard: ${esc(c.standard) || "—"}</small>
          <input data-cid="${esc(c.id)}" value="${esc(c.value ?? "")}" placeholder="${esc(c.standard) || "Enter value"}"></div>`).join("")).join("") +
      `</div><div class="msg" id="msg"></div>`;
  }

  // ---------- render ----------
  async function render() {
    const visits = await cachedVisits();
    setNav();
    saveBar.hidden = true;
    nav.hidden = false;
    if (st.tab === "units") page.innerHTML = unitsView(visits);
    else if (st.tab === "history") page.innerHTML = historyView(visits);
    else if (st.tab === "more") page.innerHTML = `<div class="notice">Add/Delete is coming in the next step.</div>`;
    else if (st.visit != null && st.unit != null && visits[st.visit] && visits[st.visit].jobs[st.unit]) {
      nav.hidden = true; saveBar.hidden = false;
      page.innerHTML = unitForm(visits);
      saveBar.innerHTML = `<button class="btn" data-cancel>Cancel</button><button class="btn teal" id="save">Save inspection</button>`;
      saveBar.querySelector("[data-cancel]").onclick = () => { st.unit = null; render(); };
      document.getElementById("save").onclick = () => saveUnit(visits);
      page.querySelector("[data-back-unit]").onclick = () => { st.unit = null; render(); };
      return;
    }
    else if (st.visit != null && visits[st.visit]) page.innerHTML = visitDetail(visits);
    else page.innerHTML = visitList(visits);
    bindPage(visits);
  }

  function bindPage(visits) {
    page.querySelectorAll("[data-visit]").forEach((b) => b.onclick = () => { st.visit = Number(b.dataset.visit); st.unit = null; st.tab = "visit"; render(); });
    page.querySelectorAll("[data-unit]").forEach((b) => b.onclick = () => { st.unit = Number(b.dataset.unit); render(); });
    page.querySelectorAll("[data-vunit]").forEach((b) => b.onclick = () => {
      const [vi, ji] = b.dataset.vunit.split(":").map(Number);
      st = { tab: "visit", visit: vi, unit: ji };
      render();
    });
    const back = page.querySelector("[data-back-visits]");
    if (back) back.onclick = () => { st.visit = null; render(); };
    const scroll = page.querySelector("[data-scroll-devices]");
    if (scroll) scroll.onclick = () => { const d = document.getElementById("devices"); if (d) d.scrollIntoView({ behavior: "smooth" }); };
    const nj = page.querySelector("[data-newjob]");
    if (nj) nj.onclick = () => alert("New service job is coming in the next step.");
    const cj = page.querySelector("[data-closejob]");
    if (cj) cj.onclick = () => closeJob(visits);
  }

  async function closeJob(visits) {
    const x = visits[st.visit];
    if (doneCount(x) < x.jobs.length) { alert(`${x.jobs.length - doneCount(x)} device(s) still pending.`); return; }
    if (!navigator.onLine) { alert("Connect to the internet to close the job."); return; }
    if (!confirm("Close this job and send it for review?")) return;
    const { error } = await sb.from("service_visits").update({ state: "review" }).eq("id", x.visit.id);
    if (error) { alert(error.message); return; }
    x.visit.state = "review";
    await kvSet("visits", visits);
    alert("Job sent for review.");
    render();
  }

  async function saveUnit(visits) {
    const msg = document.getElementById("msg");
    const x = visits[st.visit];
    const j = x.jobs[st.unit];
    let changed = 0;
    for (const el of document.querySelectorAll("[data-cid]")) {
      const id = el.dataset.cid;
      const val = el.value.trim() || null;
      const row = (j.checklist_lines || []).find((c) => String(c.id) === id);
      if (!row || (row.value ?? null) === val) continue;
      row.value = val;
      await outPut({ id, value: val });
      changed++;
    }
    await kvSet("visits", visits);
    await sendQueue();
    if (!changed) { msg.style.color = "#6b7587"; msg.textContent = "No changes to save."; return; }
    msg.style.color = "#1a7f4b";
    msg.textContent = navigator.onLine ? "Inspection saved" : "Saved on this phone. It will sync when you're online.";
    await showStatus();
  }

  // ---------- sign in and start ----------
  function loginView() {
    nav.hidden = true; saveBar.hidden = true;
    page.innerHTML = `<div class="login card"><div class="title">Sign in</div>
      <label>Email</label><input id="em" type="email" autocomplete="username">
      <label>Password</label><input id="pw" type="password" autocomplete="current-password">
      <button class="btn teal" id="go" style="width:100%;margin-top:14px">Sign in</button>
      <div class="msg" id="lm"></div></div>`;
    document.getElementById("go").onclick = async () => {
      const { error } = await sb.auth.signInWithPassword({ email: document.getElementById("em").value.trim(), password: document.getElementById("pw").value });
      if (error) { document.getElementById("lm").textContent = error.message; return; }
      start();
    };
  }

  async function downloadNow() {
    if (!navigator.onLine) { alert("Connect to the internet to download."); return; }
    syncEl.className = "sync wait"; syncEl.textContent = "Downloading…";
    try { await downloadAll(); await sendQueue(); } catch (e) { syncEl.className = "sync wait"; syncEl.textContent = "Download failed"; }
    await showStatus();
    render();
  }

  async function start() {
    const { data: { session } } = await sb.auth.getSession();
    const cached = await cachedVisits();
    if (!session && navigator.onLine) return loginView();
    if (!session && !cached.length) { page.innerHTML = `<div class="notice">Connect to the internet once and sign in to download the visits. After that the app works offline.</div>`; return; }
    if (navigator.onLine && session) { try { await downloadAll(); } catch (e) { /* keep the cached copy */ } }
    await sendQueue();
    await showStatus();
    render();
  }

  nav.querySelectorAll("button").forEach((b) => b.onclick = () => { st.tab = b.dataset.tab; st.unit = null; if (st.tab !== "visit") st.visit = null; render(); });
  document.getElementById("dl").onclick = downloadNow;
  window.addEventListener("online", async () => { await sendQueue(); await showStatus(); });
  window.addEventListener("offline", showStatus);

  start();
})();
