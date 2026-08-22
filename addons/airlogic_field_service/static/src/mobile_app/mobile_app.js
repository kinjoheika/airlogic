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
        this.notification = useService("notification");
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

            history: [],

            equipmentEdit: null,
            deleteConfirmDevice: null,
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
        });
        onWillUnmount(() => {
            window.removeEventListener("online", this._onlineHandler);
            window.removeEventListener("offline", this._offlineHandler);
        });
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
            this.loadHistory();
        }
    }

    backToClients() {
        this.state.screen = "clients";
        this.state.selectedPartner = null;
        this.state.equipmentUnlocked = false;
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
            } else {
                const created = await this.orm.create("airlogic.service.job", [
                    { equipment_id: device.id },
                ]);
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

    get dsrReadingLinesForPhase() {
        // Ph1's Amp Draw/Anemometer are checklist items, not
        // measurement-field reading lines -- the 30-field Fieldpiece
        // grid isn't phase-scoped in the mockup's DSR, so it's reachable
        // as its own phase-independent list at the end of Ph4 (folded
        // into "Line Set + Submit" alongside the PDF import).
        return this.state.readingLines;
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
            const required = phase.items.filter((it) => it.type !== "text");
            const complete = required.length > 0 && required.every((it) => {
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
            this.notification.add(
                "Complete this phase's required items before moving on.",
                { type: "warning" }
            );
            return;
        }
        this.state.dsrPhase = id;
    }

    checklistLine(key) {
        return this.state.checklistLines.find((l) => l.key === key);
    }

    async onReadingChange(code, ev) {
        const value = ev.target.value;
        const line = this.state.readingLines.find((l) => l.code === code);
        if (line) {
            line.value = value;
        }
        this.persistLocal();
        await this.trySync({ type: "save_readings", values: { [code]: value } });
    }

    onNumberChecklistChange(key, ev) {
        this.commitChecklistValue(key, ev.target.value, this.checklistLine(key)?.note);
    }

    // Mirrors _compute_is_out_of_range on airlogic.reading.line -- computed
    // client-side from the same min/max thresholds so the red highlight
    // updates the instant the technician types, not just after the next
    // server round-trip/reload.
    isReadingOutOfRange(line) {
        if (!line.value || (!line.min_value && !line.max_value)) {
            return false;
        }
        const v = parseFloat(line.value);
        if (Number.isNaN(v)) {
            return false;
        }
        if (line.min_value && v < line.min_value) {
            return true;
        }
        if (line.max_value && v > line.max_value) {
            return true;
        }
        return false;
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
            this.notification.add(
                "A reason is required to clear a flagged/alert item.", { type: "danger" }
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
            this.notification.add("All offline changes synced.", { type: "success" });
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
            this.notification.add(
                "Offline -- PDF queued, will import once back online.", { type: "warning" }
            );
            return;
        }
        try {
            await this.runAction(action);
            await this.loadJob(this.state.job.id);
            this.notification.add("PDF imported.", { type: "success" });
        } catch (e) {
            this.state.pendingCount = queueAction(this.state.job.id, action);
        }
    }

    async onPhotoSelected(ev) {
        const files = Array.from(ev.target.files || []);
        if (!files.length) {
            return;
        }
        if (!navigator.onLine) {
            this.notification.add(
                "Photos need a live connection to upload -- try again once online.",
                { type: "warning" }
            );
            return;
        }
        this.state.loading = true;
        try {
            for (const file of files) {
                const b64 = await this._fileToBase64(file);
                const [attachmentId] = await this.orm.create("ir.attachment", [{
                    name: file.name,
                    datas: b64,
                    res_model: "airlogic.service.job",
                    res_id: this.state.job.id,
                    mimetype: file.type,
                }]);
                await this.orm.call("airlogic.service.job", "write", [[this.state.job.id], {
                    media_ids: [[4, attachmentId]],
                }]);
            }
            this.notification.add(`${files.length} file(s) uploaded.`, { type: "success" });
        } finally {
            this.state.loading = false;
        }
    }

    async onSubmitJob() {
        await this.syncPending();
        if (this.state.pendingCount > 0) {
            this.notification.add(
                "Still has unsynced changes -- can't submit yet. Try again once online.",
                { type: "danger" }
            );
            return;
        }
        await this.orm.call("airlogic.service.job", "action_submit", [[this.state.job.id]]);
        this.notification.add("Job submitted.", { type: "success" });
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
        } finally {
            this.state.loading = false;
        }
    }

    closeUnit() {
        this.state.unitEquipment = null;
    }

    // --- History tab (major-events feed, filtered by History Tags) -------

    async loadHistory() {
        this.state.loading = true;
        try {
            const jobs = await this.orm.searchRead(
                "airlogic.service.job",
                [
                    ["partner_id", "=", this.state.selectedPartner.id],
                    ["state", "=", "submitted"],
                    ["history_tag_ids", "!=", false],
                ],
                ["name", "equipment_id", "technician_id", "date", "notes", "history_tag_ids"],
                { order: "date desc", limit: 30 }
            );
            const allTagIds = [...new Set(jobs.flatMap((j) => j.history_tag_ids))];
            let tagsById = {};
            if (allTagIds.length) {
                const tags = await this.orm.read("airlogic.history.tag", allTagIds, ["name"]);
                tagsById = Object.fromEntries(tags.map((t) => [t.id, t.name]));
            }
            this.state.history = jobs.map((j) => ({
                ...j,
                tagNames: j.history_tag_ids.map((id) => tagsById[id]).filter(Boolean),
            }));
        } finally {
            this.state.loading = false;
        }
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
            this.notification.add("Equipment saved.", { type: "success" });
        } else {
            if (!e.name) {
                this.notification.add("Unit label is required.", { type: "danger" });
                return;
            }
            await this.orm.call("airlogic.equipment", "action_senior_tech_create", [[], {
                partner_id: this.state.selectedPartner.id,
                name: e.name,
                model: e.model,
                serial_number: e.serial_number,
            }]);
            this.notification.add("Equipment added.", { type: "success" });
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
        this.notification.add("Equipment deleted.", { type: "success" });
        this.state.deleteConfirmDevice = null;
        this.state.equipmentEdit = null;
        await this.loadDevices();
    }
}

registry.category("actions").add("airlogic_mobile_field_entry", AirlogicMobileFieldEntry);
