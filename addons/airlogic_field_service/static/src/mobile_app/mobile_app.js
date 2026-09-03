/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { PHASES as CHECKLIST_PHASES, LEAK_SPOTS } from "@airlogic_field_service/field_entry/field_entry";

// --- Local-first cache + offline write queue -----------------------------
// Readings/checklist/PDF-import are cached to localStorage on every change
// and synced to Odoo opportunistically; if a sync attempt fails (offline),
// the action is queued and retried on the browser's `online` event or the
// next app open. Photos are NOT queued offline (binary + multi-MB is a
// bigger lift than this pass needs) -- the photo phase just tells the
// technician to retry once back online.
const LS_PREFIX = "airlogic_job_";

function pendingKey(jobId) {
    return LS_PREFIX + jobId + "_pending";
}

function getPending(jobId) {
    try {
        return JSON.parse(localStorage.getItem(pendingKey(jobId)) || "[]");
    } catch {
        return [];
    }
}

function setPending(jobId, list) {
    try {
        localStorage.setItem(pendingKey(jobId), JSON.stringify(list));
    } catch {
        // storage full/unavailable -- degrade silently, sync just won't queue
    }
}

function queueAction(jobId, action) {
    const list = getPending(jobId);
    const dedupeKey =
        action.type === "save_readings" || action.type === "save_checklist"
            ? Object.keys(action.values)[0]
            : null;
    if (dedupeKey) {
        const idx = list.findIndex(
            (a) => a.type === action.type && Object.keys(a.values)[0] === dedupeKey
        );
        if (idx >= 0) {
            list[idx] = action;
        } else {
            list.push(action);
        }
    } else {
        list.push(action);
    }
    setPending(jobId, list);
    return list.length;
}

function loadLocalValues(jobId) {
    try {
        const raw = localStorage.getItem(LS_PREFIX + jobId);
        return raw ? JSON.parse(raw) : {};
    } catch {
        return {};
    }
}

function saveLocalValues(jobId, values) {
    try {
        localStorage.setItem(LS_PREFIX + jobId, JSON.stringify(values));
    } catch {
        // ignore
    }
}

export class AirlogicMobileFieldEntry extends Component {
    static template = "airlogic_field_service.MobileFieldEntry";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        // Odoo's own notification service renders toasts at the browser
        // viewport's corner, outside the phone-frame div entirely -- that
        // breaks the "looks like a real phone" illusion, so this app
        // shows its own toast (state.toast, styled/positioned inside
        // .o_airlogic_mobile) instead of using useService("notification").
        // Neither useService("user") nor the odoo.session_info global
        // proved reliable on this build -- PIN verification runs entirely
        // server-side against self.env.user, so the client never needs to
        // know its own uid.
        this.checklistPhases = CHECKLIST_PHASES;
        this.leakSpots = LEAK_SPOTS;
        this.state = useState({
            // pin1 -> clients -> main (tab: visit|units|history|equipment)
            // device tap -> pin2 -> dsr (phase entry)
            screen: "pin1",
            tab: "visit",
            loading: false,
            pinInput: "",
            pinError: false,
            pinPurpose: null, // 'clients' | 'device' | 'equipment'
            equipmentUnlocked: false,

            clients: [],
            selectedPartner: null,
            devices: [],
            selectedEquipment: null,
            currentVisitId: null, // this client-session's Service Visit; every
                                   // unit's Job during this session attaches to it

            job: null,
            readingLines: [],
            checklistLines: [],
            dsrPhase: 1,
            flagDialog: null, // {key, label, note}
            exitConfirm: false,
            pendingCount: 0,
            online: navigator.onLine,

            unitEquipment: null,
            unitComparisonTab: "reading",
            unitReadingSection: "Air Side", // sub-badge under Readings
            unitChecklistPhase: 1, // sub-badge under Visual Checklist

            history: [],
            historyEquipment: null, // which unit's history is showing (null = unit list)

            equipmentEdit: null,
            deleteConfirmDevice: null,

            toast: null, // {message, type}
            wallpaperUrl: null, // Configuration > App Wallpaper, applied behind every screen
            currentTechnician: null, // {name, isSenior}, set once the clients-list PIN passes
            clockText: "", // small digital clock in the header, ticks every second

            partsCatalog: [], // [{id, name, airlogic_zone, ...}], loaded once and cached
            partRequests: [], // this job's airlogic.part.request rows
            partsExpanded: { 2: false, 3: false, 4: false },

            consumablesCatalog: [], // loaded once, cached
            consumableQty: {}, // productId -> quantity input value

            scheduleUpcoming: [], // this technician's own future jobs
            schedulePast: [], // this technician's own completed/past jobs
        });

        this._onlineHandler = () => {
            this.state.online = true;
            this.syncPending();
        };
        this._offlineHandler = () => {
            this.state.online = false;
        };
        onMounted(() => {
            window.addEventListener("online", this._onlineHandler);
            window.addEventListener("offline", this._offlineHandler);
            this.loadWallpaper();
            this.updateClock();
            this._clockTimer = setInterval(() => this.updateClock(), 1000);
        });
        onWillUnmount(() => {
            window.removeEventListener("online", this._onlineHandler);
            window.removeEventListener("offline", this._offlineHandler);
            clearTimeout(this._toastTimer);
            clearInterval(this._clockTimer);
        });
    }

    showToast(message, type = "success") {
        this.state.toast = { message, type };
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            this.state.toast = null;
        }, 3000);
    }

    // --- Exit (target=fullscreen hides Odoo's own navbar, so this app
    // needs its own way back to the backend) -------------------------
    // Plain browser navigation, not the action service: this build's
    // action-service internals have been unreliable enough elsewhere
    // (see the PIN-gate RPC notes below) that a guaranteed, framework-
    // independent way back is worth more here than a "proper" API call.

    exitApp() {
        window.location.href = "/odoo";
    }

    // "Logout" here means back to this app's own PIN entry screen, NOT
    // Odoo's real session logout -- the phone/tablet commonly gets
    // handed off between technicians without anyone signing out of
    // Odoo itself, so this just clears the app's own unlocked state
    // (selected client, current technician, equipment-edit access) and
    // sends the next person back to square one.
    onLogout() {
        this.state.screen = "pin1";
        this.state.tab = "visit";
        this.state.pinInput = "";
        this.state.pinError = false;
        this.state.pinPurpose = null;
        this.state.equipmentUnlocked = false;
        this.state.currentTechnician = null;
        this.state.selectedPartner = null;
        this.state.devices = [];
        this.state.selectedEquipment = null;
        this.state.currentVisitId = null;
        this.state.job = null;
        this.state.unitEquipment = null;
        this.state.historyEquipment = null;
        this.state.equipmentEdit = null;
    }

    updateClock() {
        this.state.clockText = new Date().toLocaleTimeString([], {
            hour: "2-digit", minute: "2-digit", second: "2-digit",
        });
    }

    // Configuration > App Wallpaper -- purely decorative, so a missing
    // record/image just leaves state.wallpaperUrl null and the app keeps
    // its plain white background.
    async loadWallpaper() {
        try {
            const url = await this.orm.call("airlogic.app.config", "get_wallpaper_url", []);
            if (url) {
                this.state.wallpaperUrl = url;
            }
        } catch {
            // ignore -- wallpaper is optional
        }
    }

    // Small icon+label shown under the client name in the main header so
    // it's clear which of the 4 bottom-nav tabs is currently open, even
    // once you've drilled into a specific unit (Units/History both push
    // their own sticky sub-header below this one, but this outer title
    // row stays visible the whole time).
    get currentTabMeta() {
        const map = {
            visit: { icon: "📋", label: "Visit" },
            schedule: { icon: "🗓", label: "Schedule" },
            units: { icon: "📊", label: "Units" },
            history: { icon: "🕐", label: "History" },
            equipment: { icon: "🔧", label: "Add/Delete" },
        };
        return map[this.state.tab] || null;
    }

    // --- PIN gates --------------------------------------------------------

    startPinCheck(purpose) {
        this.state.pinPurpose = purpose;
        this.state.pinInput = "";
        this.state.pinError = false;
        this.state.screen = "pin1_check";
    }

    onPinInput(ev) {
        this.state.pinInput = ev.target.value;
        this.state.pinError = false;
    }

    async confirmPin() {
        if (this.state.pinPurpose === "equipment") {
            const ok = await this.orm.call(
                "res.users", "action_verify_senior_tech_pin", [[], this.state.pinInput]
            );
            if (!ok) {
                this.state.pinError = true;
                return;
            }
            this.state.equipmentUnlocked = true;
            this.state.screen = "main";
            this.state.tab = "equipment";
            return;
        }
        const ok = await this.orm.call(
            "res.users", "action_verify_field_pin", [[], this.state.pinInput]
        );
        if (!ok) {
            this.state.pinError = true;
            return;
        }
        if (this.state.pinPurpose === "clients") {
            this.state.currentTechnician = await this.orm.call(
                "res.users", "get_current_technician_info", []
            );
            this.state.screen = "clients";
            await this.loadClients();
        } else if (this.state.pinPurpose === "device") {
            await this.enterDsr();
        }
    }

    cancelPin() {
        if (this.state.pinPurpose === "device" || this.state.pinPurpose === "equipment") {
            this.state.screen = "main";
        } else {
            this.state.screen = "pin1";
        }
    }

    // --- Navigation ---------------------------------------------------

    async loadClients() {
        this.state.loading = true;
        try {
            const groups = await this.orm.call(
                "airlogic.equipment", "read_group", [[], ["partner_id"], ["partner_id"]], {}
            );
            this.state.clients = groups
                .filter((g) => g.partner_id)
                .map((g) => ({
                    id: g.partner_id[0],
                    name: g.partner_id[1],
                    count: g.partner_id_count,
                }));
        } finally {
            this.state.loading = false;
        }
    }

    async selectClient(client) {
        this.state.selectedPartner = client;
        this.state.currentVisitId = null; // fresh Visit for this client session
        await this.loadDevices();
        this.state.tab = "visit";
        this.state.screen = "main";
    }

    async loadDevices() {
        this.state.loading = true;
        try {
            const equipment = await this.orm.searchRead(
                "airlogic.equipment",
                [["partner_id", "=", this.state.selectedPartner.id]],
                ["name", "sublocation_id", "serial_number", "brand_id", "model", "hp_id", "category_id"]
            );
            const bySub = {};
            for (const e of equipment) {
                const subName = e.sublocation_id ? e.sublocation_id[1] : "No Sublocation";
                if (!bySub[subName]) {
                    bySub[subName] = [];
                }
                bySub[subName].push(e);
            }
            this.state.devices = Object.entries(bySub).map(([sublocation, items]) => ({
                sublocation,
                items,
            }));
        } finally {
            this.state.loading = false;
        }
    }

    setTab(tab) {
        if (tab === "equipment" && !this.state.equipmentUnlocked) {
            this.startPinCheck("equipment");
            return;
        }
        this.state.tab = tab;
        this.state.unitEquipment = null;
        this.state.equipmentEdit = null;
        if (tab === "history") {
            this.state.historyEquipment = null; // land on the unit picker, not a stale unit's feed
            this.state.history = [];
        }
        if (tab === "schedule") {
            this.loadSchedule();
        }
    }

    // --- Schedule tab: the logged-in technician's own upcoming/past jobs,
    // independent of whichever client this "main" screen session started
    // from -- just airlogic.service.job, already scoped to "own" by the
    // Technician ir.rule, so no explicit technician_id filter is needed.
    async loadSchedule() {
        this.state.loading = true;
        try {
            const jobs = await this.orm.searchRead(
                "airlogic.service.job", [],
                ["name", "date", "state", "equipment_id", "partner_id"],
                { order: "date desc", limit: 100 }
            );
            const todayStr = new Date().toISOString().slice(0, 10);
            const upcoming = [];
            const past = [];
            for (const j of jobs) {
                const jobDateStr = (j.date || "").slice(0, 10);
                (jobDateStr >= todayStr ? upcoming : past).push(j);
            }
            upcoming.sort((a, b) => (a.date < b.date ? -1 : 1));
            this.state.scheduleUpcoming = upcoming;
            this.state.schedulePast = past;
        } finally {
            this.state.loading = false;
        }
    }

    backToClients() {
        this.state.screen = "clients";
        this.state.selectedPartner = null;
        this.state.equipmentUnlocked = false;
        this.state.currentVisitId = null;
    }

    // --- Device tap -> PIN2 -> DSR ---------------------------------------

    selectDeviceForEntry(device) {
        this.state.selectedEquipment = device;
        this.startPinCheck("device");
    }

    async enterDsr() {
        this.state.loading = true;
        try {
            const device = this.state.selectedEquipment;
            // draft AND in_progress: a technician who exited mid-entry and
            // comes back must resume the same job, not spawn a duplicate.
            const jobIds = await this.orm.search(
                "airlogic.service.job",
                [["equipment_id", "=", device.id], ["state", "in", ["draft", "in_progress"]]],
                { order: "date desc", limit: 1 }
            );
            let jobId;
            if (jobIds.length) {
                jobId = jobIds[0];
                // Resuming a job that already belongs to a Visit (e.g. the
                // app was closed and reopened mid-session): adopt that
                // Visit so any further NEW units this session attach to
                // the same one, instead of starting a second Visit.
                if (!this.state.currentVisitId) {
                    const [existing] = await this.orm.read(
                        "airlogic.service.job", [jobId], ["visit_id"]
                    );
                    if (existing.visit_id) {
                        this.state.currentVisitId = existing.visit_id[0];
                    }
                }
            } else {
                // One Service Visit per client session (see selectClient/
                // backToClients, which reset currentVisitId): the first
                // new unit in a session opens the Visit, every further
                // unit's Job attaches to that same one.
                if (!this.state.currentVisitId) {
                    const [visitId] = await this.orm.create("airlogic.service.visit", [{
                        partner_id: this.state.selectedPartner.id,
                    }]);
                    this.state.currentVisitId = visitId;
                }
                const created = await this.orm.create("airlogic.service.job", [{
                    equipment_id: device.id,
                    visit_id: this.state.currentVisitId,
                }]);
                jobId = created[0];
            }
            // Flips draft -> in_progress with an honest start timestamp,
            // right as entry actually begins -- no separate "Start Visit"
            // tap needed on mobile. No-ops if already past draft.
            await this.orm.call("airlogic.service.job", "action_start_visit", [[jobId]]);
            await this.loadJob(jobId);
            this.state.dsrPhase = 1;
            this.state.screen = "dsr";
        } finally {
            this.state.loading = false;
        }
    }

    // --- Exit-confirm guard (leaving the DSR phase entry) ----------------

    requestExitDsr() {
        this.state.exitConfirm = true;
    }

    stayInDsr() {
        this.state.exitConfirm = false;
    }

    async confirmExitDsr() {
        this.state.exitConfirm = false;
        await this.syncPending();
        this.state.screen = "main";
        this.state.tab = "visit";
    }

    // --- Job data -------------------------------------------------------

    async loadJob(jobId) {
        const data = await this.orm.call("airlogic.service.job", "get_field_entry_data", [[jobId]]);
        this.state.job = data;
        this.state.readingLines = data.reading_lines;
        this.state.checklistLines = data.checklist_lines;

        const local = loadLocalValues(jobId);
        if (local.readingValues) {
            for (const line of this.state.readingLines) {
                if (line.code in local.readingValues) {
                    line.value = local.readingValues[line.code];
                }
            }
        }
        if (local.checklistValues) {
            for (const line of this.state.checklistLines) {
                if (line.key in local.checklistValues) {
                    line.value = local.checklistValues[line.key].value;
                    line.note = local.checklistValues[line.key].note;
                }
            }
        }
        this.state.pendingCount = getPending(jobId).length;
        this.persistLocal();

        await this.loadPartsCatalog();
        this.state.partRequests = await this.orm.searchRead(
            "airlogic.part.request", [["job_id", "=", jobId]], ["part_id", "state"]
        );
    }

    persistLocal() {
        if (!this.state.job) {
            return;
        }
        const readingValues = {};
        for (const l of this.state.readingLines) {
            readingValues[l.code] = l.value;
        }
        const checklistValues = {};
        for (const l of this.state.checklistLines) {
            checklistValues[l.key] = { value: l.value, note: l.note };
        }
        saveLocalValues(this.state.job.id, { readingValues, checklistValues });
    }

    get currentDsrPhase() {
        return this.checklistPhases.find((p) => p.id === this.state.dsrPhase);
    }

    // Warn, don't block: a visit open a long time with unsynced changes
    // is worth flagging (spotty signal, technician forgot to check
    // back), but the spec is explicit this should never stop them from
    // continuing to work offline.
    get syncWarning() {
        if (!this.state.job || !this.state.job.started_at || !this.state.pendingCount) {
            return null;
        }
        const startedAt = new Date(this.state.job.started_at.replace(" ", "T") + "Z");
        const hoursOpen = (Date.now() - startedAt.getTime()) / 3600000;
        if (hoursOpen < 2) {
            return null;
        }
        return `Open ${Math.floor(hoursOpen)}h with ${this.state.pendingCount} unsynced change(s) -- reconnect when you can.`;
    }

    // --- Phase lock (mirrors get_unlocked_phase in airlogic_service_job.py
    // -- keep both in sync by hand, same convention as PHASES/
    // CHECKLIST_ITEMS). Computed client-side from live state rather than
    // the server's snapshot from load time, so it stays correct the
    // instant a required field is filled, no round-trip needed. The
    // server re-checks independently in action_save_visual_checklist --
    // this is UI responsiveness, not the actual security boundary. -----

    get unlockedPhase() {
        let unlocked = 1;
        for (const phaseId of [1, 2, 3]) {
            const phase = this.checklistPhases.find((p) => p.id === phaseId);
            // Only "number" items gate progress -- "check" items default
            // to Normal and are only touched to flag an exception, so
            // they stay blank by design and must not block the phase.
            // No `required.length > 0 &&` guard: [].every() is true, so
            // a phase with zero number items (Phase 3, "Indoor OFF", now
            // that Anemometer (Indoor) moved to Phase 1) is trivially
            // complete instead of stuck forever -- that guard is exactly
            // the bug AIR-T35 fixed for Phase 2, just re-triggered here.
            const required = phase.items.filter((it) => it.type === "number");
            const complete = required.every((it) => {
                const line = this.checklistLine(it.key);
                return line && line.value;
            });
            if (complete) {
                unlocked = phaseId + 1;
            } else {
                break;
            }
        }
        return unlocked;
    }

    goToPhase(id) {
        if (id > this.unlockedPhase) {
            this.showToast(
                "Complete this phase's required items before moving on.", "warning"
            );
            return;
        }
        this.state.dsrPhase = id;
    }

    checklistLine(key) {
        return this.state.checklistLines.find((l) => l.key === key);
    }

    onNumberChecklistChange(key, ev) {
        this.commitChecklistValue(key, ev.target.value, this.checklistLine(key)?.note);
    }

    // --- Request Parts (bottom of Ph2/3/4) ---------------------------
    // A tick list, not a real stock/consumption ledger -- see
    // airlogic_part.py for why. Phase 2 shows the Outdoor zone, Phase 3
    // shows Indoor, Phase 4 shows everything as a final catch-all before
    // submit.

    async loadPartsCatalog() {
        if (this.state.partsCatalog.length) {
            return; // catalog doesn't change mid-session, load once
        }
        // Real product.product records now (AIR-T53/Phase 6.2), not the
        // old bespoke airlogic.part -- airlogic_equipment_category_ids
        // is what lets currentPhaseParts below pre-fill the parts that
        // actually fit THIS unit instead of always showing everything.
        this.state.partsCatalog = await this.orm.searchRead(
            "product.product", [["airlogic_requestable", "=", true]],
            ["name", "default_code", "airlogic_zone", "airlogic_equipment_category_ids"]
        );
    }

    get currentPhaseParts() {
        let byZone;
        if (this.state.dsrPhase === 2) {
            byZone = this.state.partsCatalog.filter(
                (p) => p.airlogic_zone === "outdoor" || p.airlogic_zone === "both");
        } else if (this.state.dsrPhase === 3) {
            byZone = this.state.partsCatalog.filter(
                (p) => p.airlogic_zone === "indoor" || p.airlogic_zone === "both");
        } else if (this.state.dsrPhase === 4) {
            byZone = this.state.partsCatalog;
        } else {
            return [];
        }
        // Pre-fill: if this unit's own equipment category has any parts
        // mapped to it, show only those (the technician just confirms
        // the right model instead of typing/photographing it). Falls
        // back to the full zone list if nothing's mapped yet for that
        // category.
        const categoryId = this.state.selectedEquipment && this.state.selectedEquipment.category_id
            ? this.state.selectedEquipment.category_id[0] : null;
        if (categoryId) {
            const matched = byZone.filter(
                (p) => p.airlogic_equipment_category_ids.includes(categoryId));
            if (matched.length) {
                return matched;
            }
        }
        return byZone;
    }

    togglePartsSection(phase) {
        this.state.partsExpanded[phase] = !this.state.partsExpanded[phase];
    }

    findPartRequest(partId) {
        return this.state.partRequests.find((r) => r.part_id[0] === partId);
    }

    async togglePartRequest(partId) {
        const existing = this.findPartRequest(partId);
        if (existing) {
            if (existing.state !== "requested") {
                this.showToast(
                    "Already reviewed -- ask an Operations Officer to change it.", "warning"
                );
                return;
            }
            await this.orm.unlink("airlogic.part.request", [existing.id]);
            this.state.partRequests = this.state.partRequests.filter((r) => r.id !== existing.id);
        } else {
            const [id] = await this.orm.create("airlogic.part.request", [{
                job_id: this.state.job.id,
                part_id: partId,
            }]);
            this.state.partRequests.push({ id, part_id: [partId, ""], state: "requested" });
        }
    }

    // --- Order Consumables (not tied to a job/unit, own small screen) ------

    async openConsumables() {
        this.state.loading = true;
        try {
            if (!this.state.consumablesCatalog.length) {
                this.state.consumablesCatalog = await this.orm.searchRead(
                    "product.product", [["airlogic_is_consumable", "=", true]],
                    ["name", "default_code"]
                );
            }
            this.state.screen = "consumables";
        } finally {
            this.state.loading = false;
        }
    }

    closeConsumables() {
        this.state.screen = "main";
    }

    onConsumableQtyChange(productId, ev) {
        this.state.consumableQty[productId] = ev.target.value;
    }

    async orderConsumable(productId) {
        const qty = parseFloat(this.state.consumableQty[productId]) || 1;
        await this.orm.create("airlogic.consumable.request", [{
            product_id: productId,
            quantity: qty,
        }]);
        this.state.consumableQty[productId] = "";
        this.showToast("Consumable order sent for approval.", "success");
    }

    // --- Flag/Alert dialog -------------------------------------------------

    openFlagDialog(key, label) {
        const line = this.checklistLine(key);
        this.state.flagDialog = {
            key,
            label,
            note: (line && line.note) || "",
        };
    }

    onFlagNoteChange(ev) {
        if (this.state.flagDialog) {
            this.state.flagDialog.note = ev.target.value;
        }
    }

    async setFlagState(newValue) {
        const { key, note } = this.state.flagDialog;
        await this.commitChecklistValue(key, newValue, note);
        this.state.flagDialog = null;
    }

    async setNormal() {
        const { key, note } = this.state.flagDialog;
        const line = this.checklistLine(key);
        const wasFlagged = line && (line.value === "flagged" || line.value === "alert");
        if (wasFlagged && !note.trim()) {
            this.showToast(
                "A reason is required to clear a flagged/alert item.", "danger"
            );
            return;
        }
        await this.commitChecklistValue(key, "ok", note);
        this.state.flagDialog = null;
    }

    cancelFlagDialog() {
        this.state.flagDialog = null;
    }

    async commitChecklistValue(key, value, note) {
        const line = this.checklistLine(key);
        if (line) {
            line.value = value;
            line.note = note || "";
        }
        this.persistLocal();
        await this.trySync({
            type: "save_checklist",
            values: { [key]: value },
            notes: note ? { [key]: note } : {},
        });
    }

    // --- Leak check (7-spot map) ------------------------------------------

    get leakSpotIndices() {
        const line = this.checklistLine("leak");
        const val = (line && line.value) || "";
        if (val === "pass" || !val) {
            return [];
        }
        return val.split(",").filter(Boolean).map((s) => parseInt(s, 10));
    }

    async setLeakPass() {
        await this.commitChecklistValue("leak", "pass", "");
    }

    async toggleLeakSpot(index) {
        const current = new Set(this.leakSpotIndices);
        if (current.has(index)) {
            current.delete(index);
        } else {
            current.add(index);
        }
        const val = current.size ? Array.from(current).sort().join(",") : "";
        await this.commitChecklistValue("leak", val, this.checklistLine("leak")?.note || "");
    }

    get leakDetected() {
        const line = this.checklistLine("leak");
        return !!(line && line.value && line.value !== "pass");
    }

    // --- Sync / offline queue -------------------------------------------

    async trySync(action) {
        if (!navigator.onLine) {
            this.state.pendingCount = queueAction(this.state.job.id, action);
            return;
        }
        try {
            await this.runAction(action);
        } catch (e) {
            this.state.pendingCount = queueAction(this.state.job.id, action);
        }
    }

    async runAction(action) {
        const jobId = this.state.job.id;
        if (action.type === "save_readings") {
            await this.orm.call(
                "airlogic.service.job", "action_save_reading_lines", [[jobId], action.values]
            );
        } else if (action.type === "save_checklist") {
            await this.orm.call(
                "airlogic.service.job", "action_save_visual_checklist",
                [[jobId], action.values, action.notes || {}]
            );
        } else if (action.type === "import_pdf") {
            await this.orm.call("airlogic.service.job", "write", [[jobId], {
                fp_pdf: action.b64,
                fp_pdf_filename: action.filename,
            }]);
            await this.orm.call("airlogic.service.job", "action_import_fieldpiece_pdf", [[jobId]]);
        }
    }

    async syncPending() {
        if (!this.state.job) {
            return;
        }
        const jobId = this.state.job.id;
        const pending = getPending(jobId);
        if (!pending.length) {
            return;
        }
        const remaining = [];
        for (const action of pending) {
            try {
                await this.runAction(action);
            } catch (e) {
                remaining.push(action);
            }
        }
        setPending(jobId, remaining);
        this.state.pendingCount = remaining.length;
        if (!remaining.length) {
            this.showToast("All offline changes synced.", "success");
            await this.loadJob(jobId);
        }
    }

    // --- PDF / photos -----------------------------------------------------

    _fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(",")[1]);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    async onPdfSelected(ev) {
        const file = ev.target.files[0];
        if (!file) {
            return;
        }
        const b64 = await this._fileToBase64(file);
        const action = { type: "import_pdf", b64, filename: file.name };
        if (!navigator.onLine) {
            this.state.pendingCount = queueAction(this.state.job.id, action);
            this.showToast(
                "Offline -- PDF queued, will import once back online.", "warning"
            );
            return;
        }
        try {
            await this.runAction(action);
            await this.loadJob(this.state.job.id);
            this.showToast("PDF imported.", "success");
        } catch (e) {
            this.state.pendingCount = queueAction(this.state.job.id, action);
        }
    }

    // Best-effort geolocation for photo auto-tagging -- resolves null
    // (never rejects) if the browser has no geolocation, the technician
    // denies the permission prompt, or it just takes too long. Upload
    // proceeds either way; location is a nice-to-have on the tag, not a
    // requirement.
    _tryGetLocation() {
        return new Promise((resolve) => {
            if (!navigator.geolocation) {
                resolve(null);
                return;
            }
            navigator.geolocation.getCurrentPosition(
                (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
                () => resolve(null),
                { timeout: 4000 }
            );
        });
    }

    async onPhotoSelected(ev) {
        const files = Array.from(ev.target.files || []);
        if (!files.length) {
            return;
        }
        if (!navigator.onLine) {
            this.showToast(
                "Photos need a live connection to upload -- try again once online.",
                "warning"
            );
            return;
        }
        this.state.loading = true;
        try {
            // Auto-tag at capture time, not upload time: phase + when +
            // (if granted) where. Saved into the attachment's own
            // description so a Manager reviewing photos later in
            // Inventory sees it without the technician typing anything.
            const geo = await this._tryGetLocation();
            const capturedAt = new Date().toLocaleString();
            const phaseLabel = this.currentDsrPhase ? this.currentDsrPhase.title : "";
            const tagParts = [`Phase ${this.state.dsrPhase} — ${phaseLabel}`, `Captured ${capturedAt}`];
            if (geo) {
                tagParts.push(`Location ${geo.lat.toFixed(5)}, ${geo.lon.toFixed(5)}`);
            }
            const description = tagParts.join(" · ");
            for (const file of files) {
                const b64 = await this._fileToBase64(file);
                const [attachmentId] = await this.orm.create("ir.attachment", [{
                    name: file.name,
                    datas: b64,
                    res_model: "airlogic.service.job",
                    res_id: this.state.job.id,
                    mimetype: file.type,
                    description,
                }]);
                await this.orm.call("airlogic.service.job", "write", [[this.state.job.id], {
                    media_ids: [[4, attachmentId]],
                }]);
            }
            this.showToast(`${files.length} file(s) uploaded.`, "success");
        } finally {
            this.state.loading = false;
        }
    }

    async onSubmitJob() {
        await this.syncPending();
        if (this.state.pendingCount > 0) {
            this.showToast(
                "Still has unsynced changes -- can't submit yet. Try again once online.",
                "danger"
            );
            return;
        }
        await this.orm.call("airlogic.service.job", "action_submit", [[this.state.job.id]]);
        this.showToast("Job submitted.", "success");
        this.state.screen = "main";
        this.state.tab = "visit";
    }

    // --- Units tab (Reading/Visual comparison, mobile-friendly cards) ----
    // Same underlying data as the desktop Equipment form's comparison
    // tabs, but fetched as JSON (get_*_comparison_data) instead of the
    // desktop's wide HTML table, and rendered as stacked cards here --
    // a 5-column table doesn't fit a 380px-wide phone body.

    async openUnit(device) {
        this.state.loading = true;
        try {
            const [readingData, visualData] = await Promise.all([
                this.orm.call("airlogic.equipment", "get_reading_comparison_data", [[device.id]]),
                this.orm.call("airlogic.equipment", "get_visual_comparison_data", [[device.id]]),
            ]);
            this.state.unitEquipment = { ...device, readingData, visualData };
            this.state.unitComparisonTab = "reading";
            this.state.unitReadingSection = "Air Side";
            this.state.unitChecklistPhase = 1;
        } finally {
            this.state.loading = false;
        }
    }

    closeUnit() {
        this.state.unitEquipment = null;
    }

    // Sub-badge selection under Readings/Visual Checklist -- only the
    // selected section/phase renders, everything else in
    // readingData.sections / visualData.phases just isn't shown right
    // now (still fetched once up front in openUnit, no re-fetch on tap).

    get currentReadingSection() {
        if (!this.state.unitEquipment) {
            return null;
        }
        return this.state.unitEquipment.readingData.sections.find(
            (s) => s.section === this.state.unitReadingSection
        );
    }

    get currentChecklistPhaseCompare() {
        if (!this.state.unitEquipment) {
            return null;
        }
        return this.state.unitEquipment.visualData.phases.find(
            (p) => p.phase === this.state.unitChecklistPhase
        );
    }

    // --- History tab (unit picker -> that unit's major-events feed,
    // filtered by History Tags) -----------------------------------------

    async openHistoryUnit(device) {
        this.state.loading = true;
        try {
            this.state.historyEquipment = device;
            const jobs = await this.orm.searchRead(
                "airlogic.service.job",
                [
                    ["equipment_id", "=", device.id],
                    ["state", "=", "submitted"],
                    ["history_tag_ids", "!=", false],
                    // Only once a Manager has approved the whole Service
                    // Visit this job belongs to, not just on submission --
                    // History is client-facing shared record, submission
                    // alone isn't a sign-off.
                    ["visit_id.state", "=", "approved"],
                ],
                ["name", "technician_id", "date", "notes", "history_tag_ids"],
                { order: "date desc", limit: 30 }
            );
            const jobIds = jobs.map((j) => j.id);
            const allTagIds = [...new Set(jobs.flatMap((j) => j.history_tag_ids))];
            let tagsById = {};
            if (allTagIds.length) {
                const tags = await this.orm.read("airlogic.history.tag", allTagIds, ["name"]);
                tagsById = Object.fromEntries(tags.map((t) => [t.id, t.name]));
            }
            // "Main parts": every flagged/alert item, plus a detected
            // leak, each with its technician note if there is one --
            // mirrors _job_issues in airlogic_service_visit_ext.py (same
            // reasoning: History and the Owner Report should tell the
            // same story). One batched query for all jobs, not one per
            // job.
            let partsByJob = {};
            if (jobIds.length) {
                const lines = await this.orm.searchRead(
                    "airlogic.checklist.line",
                    [["job_id", "in", jobIds]],
                    ["job_id", "key", "label", "value", "note"]
                );
                for (const line of lines) {
                    const isFlagged = line.value === "flagged" || line.value === "alert";
                    const isLeak = line.key === "leak" && line.value && line.value !== "pass";
                    if (!isFlagged && !isLeak) {
                        continue;
                    }
                    const jid = line.job_id[0];
                    if (!partsByJob[jid]) {
                        partsByJob[jid] = [];
                    }
                    partsByJob[jid].push({
                        label: isLeak ? "Leak Detected" : line.label,
                        note: line.note || "",
                    });
                }
            }
            this.state.history = jobs.map((j) => {
                const parts = partsByJob[j.id] || [];
                return {
                    ...j,
                    tagNames: j.history_tag_ids.map((id) => tagsById[id]).filter(Boolean),
                    parts,
                    // Timeline dot color (AIR-T48): urgent if a leak was
                    // ever recorded on this visit, watch if any other
                    // flagged/alert part was, otherwise a routine entry
                    // (e.g. a plain "Cleaned"-tagged visit with no issues).
                    severity: parts.some((p) => p.label === "Leak Detected")
                        ? "urgent" : parts.length ? "watch" : "",
                };
            });
        } finally {
            this.state.loading = false;
        }
    }

    closeHistoryUnit() {
        this.state.historyEquipment = null;
        this.state.history = [];
    }

    formatHistoryTimestamp(dateStr) {
        if (!dateStr) {
            return "";
        }
        const d = new Date(dateStr.replace(" ", "T") + "Z");
        return d.toLocaleString(undefined, {
            weekday: "short", year: "numeric", month: "short", day: "numeric",
            hour: "2-digit", minute: "2-digit",
        });
    }

    // --- Equipment tab (Add/Delete) ----------------------------------
    // Locked behind the Senior Technician PIN gate (see confirmPin /
    // setTab above) -- only reachable for the currently selected,
    // already-existing client. Whatever gets added or deleted here is
    // the same airlogic.equipment record the Manager reviews under
    // Inventory > Equipment; there's no separate mobile-only store.

    openNewEquipment() {
        this.state.equipmentEdit = { id: null, name: "", model: "", serial_number: "" };
    }

    openEquipmentEdit(device) {
        this.state.equipmentEdit = { ...device };
    }

    closeEquipmentEdit() {
        this.state.equipmentEdit = null;
    }

    async saveEquipmentEdit() {
        const e = this.state.equipmentEdit;
        if (e.id) {
            await this.orm.call("airlogic.equipment", "action_senior_tech_write", [[e.id], {
                name: e.name,
                model: e.model,
                serial_number: e.serial_number,
            }]);
            this.showToast("Equipment saved.", "success");
        } else {
            if (!e.name) {
                this.showToast("Unit label is required.", "danger");
                return;
            }
            await this.orm.call("airlogic.equipment", "action_senior_tech_create", [[], {
                partner_id: this.state.selectedPartner.id,
                name: e.name,
                model: e.model,
                serial_number: e.serial_number,
            }]);
            this.showToast("Equipment added.", "success");
        }
        this.state.equipmentEdit = null;
        await this.loadDevices();
    }

    requestDeleteEquipment(device) {
        this.state.deleteConfirmDevice = device;
    }

    cancelDeleteEquipment() {
        this.state.deleteConfirmDevice = null;
    }

    async confirmDeleteEquipment() {
        const device = this.state.deleteConfirmDevice;
        await this.orm.call("airlogic.equipment", "action_senior_tech_unlink", [[device.id]]);
        this.showToast("Equipment deleted.", "success");
        this.state.deleteConfirmDevice = null;
        this.state.equipmentEdit = null;
        await this.loadDevices();
    }
}

registry.category("actions").add("airlogic_mobile_field_entry", AirlogicMobileFieldEntry);
