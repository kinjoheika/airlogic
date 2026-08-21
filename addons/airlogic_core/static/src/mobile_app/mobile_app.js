/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { PHASES as CHECKLIST_PHASES } from "@airlogic_core/field_entry/field_entry";

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
    static template = "airlogic_core.MobileFieldEntry";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.checklistPhases = CHECKLIST_PHASES;
        this.state = useState({
            screen: "clients",
            loading: false,
            clients: [],
            devices: [],
            selectedPartner: null,
            selectedEquipment: null,
            job: null,
            readingLines: [],
            checklistLines: [],
            phase: "measurements",
            checklistPhase: 1,
            pendingCount: 0,
            online: navigator.onLine,
        });

        onWillStart(async () => {
            await this.loadClients();
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

    // --- Navigation ---------------------------------------------------

    async loadClients() {
        this.state.loading = true;
        try {
            const groups = await this.orm.readGroup(
                "airlogic.equipment", [], ["partner_id"], ["partner_id"]
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
        this.state.loading = true;
        try {
            const equipment = await this.orm.searchRead(
                "airlogic.equipment",
                [["partner_id", "=", client.id]],
                ["name", "sublocation_id", "serial_number", "brand_id", "model", "hp_id"]
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
            this.state.screen = "devices";
        } finally {
            this.state.loading = false;
        }
    }

    backToClients() {
        this.state.screen = "clients";
        this.state.selectedPartner = null;
    }

    backToDevices() {
        this.state.screen = "devices";
        this.state.job = null;
        this.state.selectedEquipment = null;
    }

    async selectDevice(device) {
        this.state.selectedEquipment = device;
        this.state.loading = true;
        try {
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
            this.state.phase = "measurements";
            this.state.screen = "job";
        } finally {
            this.state.loading = false;
        }
    }

    // --- Job data -------------------------------------------------------

    async loadJob(jobId) {
        const data = await this.orm.call("airlogic.service.job", "get_field_entry_data", [[jobId]]);
        this.state.job = data;
        this.state.readingLines = data.reading_lines;
        this.state.checklistLines = data.checklist_lines;

        // Merge in any locally-cached, possibly-unsynced values so a
        // reload mid-offline-session doesn't lose in-progress entries.
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
                    line.value = local.checklistValues[line.key];
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
            checklistValues[l.key] = l.value;
        }
        saveLocalValues(this.state.job.id, { readingValues, checklistValues });
    }

    get groupedReadingLines() {
        const bySection = {};
        for (const l of this.state.readingLines) {
            const sec = l.section || "";
            if (!bySection[sec]) {
                bySection[sec] = [];
            }
            bySection[sec].push(l);
        }
        return Object.entries(bySection).map(([section, items]) => ({ section, items }));
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

    get currentChecklistPhase() {
        return this.checklistPhases.find((p) => p.id === this.state.checklistPhase);
    }

    setChecklistPhase(id) {
        this.state.checklistPhase = id;
    }

    checklistLineValue(key) {
        const line = this.state.checklistLines.find((l) => l.key === key);
        return line ? line.value : "";
    }

    async setChecklistValue(key, value) {
        const line = this.state.checklistLines.find((l) => l.key === key);
        if (line) {
            line.value = value;
        }
        this.persistLocal();
        await this.trySync({ type: "save_checklist", values: { [key]: value } });
    }

    onChecklistTextChange(key, ev) {
        this.setChecklistValue(key, ev.target.value);
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
                "airlogic.service.job", "action_save_visual_checklist", [[jobId], action.values]
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
        this.backToDevices();
    }
}

registry.category("actions").add("airlogic_mobile_field_entry", AirlogicMobileFieldEntry);
