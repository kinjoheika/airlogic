/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
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
        this.user = useService("user");
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
            pinPurpose: null, // 'clients' | 'device'
            isManager: false,

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
        });

        onWillStart(async () => {
            this.state.isManager = await this.user.hasGroup("airlogic_core.group_airlogic_manager");
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
        const ok = await this.orm.call(
            "res.users", "action_verify_field_pin", [[this.user.userId], this.state.pinInput]
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
        if (this.state.pinPurpose === "device") {
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
            const jobIds = await this.orm.search(
                "airlogic.service.job",
                [["equipment_id", "=", device.id], ["state", "=", "draft"]],
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
        const { key } = this.state.flagDialog;
        await this.commitChecklistValue(key, "ok", "");
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

    // --- Units tab (Reading/Visual comparison, reused from Equipment) ----

    async openUnit(device) {
        this.state.loading = true;
        try {
            const [data] = await this.orm.read(
                "airlogic.equipment", [device.id],
                ["reading_comparison_html", "visual_comparison_html"]
            );
            this.state.unitEquipment = { ...device, ...data };
            this.state.unitComparisonTab = "reading";
        } finally {
            this.state.loading = false;
        }
    }

    closeUnit() {
        this.state.unitEquipment = null;
    }

    // --- History tab (recent submitted jobs for this client) -------------

    async loadHistory() {
        this.state.loading = true;
        try {
            this.state.history = await this.orm.searchRead(
                "airlogic.service.job",
                [["partner_id", "=", this.state.selectedPartner.id], ["state", "=", "submitted"]],
                ["name", "equipment_id", "technician_id", "date", "notes"],
                { order: "date desc", limit: 30 }
            );
        } finally {
            this.state.loading = false;
        }
    }

    // --- Equipment tab (Add/Delete, Manager-only edit) --------------------

    openEquipmentEdit(device) {
        this.state.equipmentEdit = { ...device };
    }

    closeEquipmentEdit() {
        this.state.equipmentEdit = null;
    }

    async saveEquipmentEdit() {
        const e = this.state.equipmentEdit;
        await this.orm.write("airlogic.equipment", [e.id], {
            name: e.name,
            model: e.model,
            serial_number: e.serial_number,
        });
        this.notification.add("Equipment saved.", { type: "success" });
        this.state.equipmentEdit = null;
        await this.loadDevices();
    }
}

registry.category("actions").add("airlogic_mobile_field_entry", AirlogicMobileFieldEntry);
