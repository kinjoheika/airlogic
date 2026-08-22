/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Ph1-4 visual checklist, ported from the aircon-service-ui mockup's
// buildEquipDataTable() rows. Keys here must match
// models/airlogic_checklist_line.py's CHECKLIST_ITEMS -- keep both in
// sync by hand. Exported so mobile_app.js can reuse it instead of a
// second copy.
export const PHASES = [
    {
        id: 1,
        title: "Outdoor Unit — OFF",
        items: [
            { key: "brk", label: "Breaker Wires & Terminals", type: "check" },
            { key: "comp", label: "Compressor Body", type: "check" },
            { key: "coils", label: "Coils & Fins", type: "check" },
            { key: "motor", label: "Motor & Fan", type: "check" },
            { key: "pcb", label: "PCB", type: "check" },
            { key: "ipm", label: "IPM", type: "check" },
            { key: "wires", label: "Wires & Terminals", type: "check" },
            { key: "cables", label: "Cable Ties / Paste / Grommets", type: "check" },
        ],
    },
    {
        id: 2,
        title: "Outdoor Unit — ON",
        items: [
            { key: "volt", label: "Line Voltage", type: "number", unit: "V", standard: "198–242 V" },
            { key: "a1", label: "Amp Draw L1", type: "number", unit: "A", standard: "Nameplate ±10%" },
            { key: "a2", label: "Amp Draw L2", type: "number", unit: "A", standard: "Nameplate ±10%" },
            { key: "a3", label: "Amp Draw L3", type: "number", unit: "A", standard: "Nameplate ±10%" },
        ],
    },
    {
        id: 3,
        title: "Indoor Unit",
        items: [
            { key: "cfm", label: "Anemometer", type: "number", unit: "CFM", standard: "Per BTU rating" },
            { key: "coil", label: "Coil & Fins", type: "check" },
            { key: "drain", label: "Drain Pan", type: "check" },
            { key: "wiresIn", label: "Wires (tactile)", type: "check" },
        ],
    },
    {
        id: 4,
        title: "Line Set",
        items: [
            { key: "ins", label: "Insulation Tape", type: "check" },
            { key: "wireCond", label: "Wire Condition", type: "check" },
            { key: "cond", label: "Condensation", type: "check" },
            { key: "leak", label: "Leak Check", type: "leak" },
            { key: "notes", label: "Tech Notes", type: "text" },
        ],
    },
];

export class AirlogicVisualChecklist extends Component {
    static template = "airlogic_field_service.VisualChecklist";
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.phases = PHASES;
        this.state = useState({
            phase: 1,
            values: { ...(this.params.values || {}) },
            saving: false,
        });
    }

    get params() {
        return this.props.action.params || {};
    }

    get currentPhase() {
        return this.phases.find((p) => p.id === this.state.phase);
    }

    get progress() {
        const total = this.phases.reduce((n, p) => n + p.items.length, 0);
        const done = Object.values(this.state.values).filter(
            (v) => v !== undefined && v !== ""
        ).length;
        return { done, total };
    }

    setPhase(id) {
        this.state.phase = id;
    }

    prevPhase() {
        if (this.state.phase > 1) {
            this.state.phase -= 1;
        }
    }

    nextPhase() {
        if (this.state.phase < this.phases.length) {
            this.state.phase += 1;
        }
    }

    setValue(key, value) {
        this.state.values[key] = value;
    }

    onNumberChange(key, ev) {
        this.setValue(key, ev.target.value);
    }

    onTextChange(key, ev) {
        this.setValue(key, ev.target.value);
    }

    async onDone() {
        if (!this.params.job_id) {
            this.notification.add("No job to save against.", { type: "danger" });
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call(
                "airlogic.service.job",
                "action_save_visual_checklist",
                [[this.params.job_id], this.state.values]
            );
            this.notification.add("Visual checklist saved.", { type: "success" });
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "airlogic.service.job",
                res_id: this.params.job_id,
                views: [[false, "form"]],
                target: "current",
            });
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("airlogic_visual_checklist", AirlogicVisualChecklist);
