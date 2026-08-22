/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Ph1-4 checklist, ported from the aircon-service-ui mockup's actual
// mobile DSR flow (tab-mobile #pp-dsr / dsp-ph1..4) -- NOT the earlier
// desktop Equipment Data table this was first built against, which
// turned out to have a different phase grouping and was missing the
// Megger insulation test. Keys/order here must match
// models/airlogic_checklist_line.py's CHECKLIST_ITEMS -- keep both in
// sync by hand. Exported so mobile_app.js can reuse it instead of a
// second copy.
export const PHASES = [
    {
        id: 1,
        title: "Outdoor — Power ON",
        items: [
            { key: "amp_draw", label: "Amp Draw", type: "number", unit: "A" },
            { key: "cfm_outdoor", label: "Anemometer (Outdoor)", type: "number", unit: "CFM" },
        ],
    },
    {
        id: 2,
        title: "Outdoor — Power OFF",
        items: [
            { key: "brk", label: "Breaker Wires & Terminals", type: "check" },
            { key: "comp", label: "Compressor Body", type: "check" },
            { key: "coils", label: "Coils & Fins", type: "check" },
            { key: "motor", label: "Motor & Fan", type: "check" },
            { key: "pcb", label: "PCB", type: "check" },
            { key: "ipm", label: "IPM", type: "check" },
            { key: "wires", label: "Wires & Terminals", type: "check" },
            { key: "cables", label: "Cable Ties / Paste / Grommets", type: "check" },
            { key: "meg_u", label: "Megger U Phase", type: "number", unit: "MΩ", standard: "≥ 1.0 MΩ" },
            { key: "meg_v", label: "Megger V Phase", type: "number", unit: "MΩ", standard: "≥ 1.0 MΩ" },
            { key: "meg_w", label: "Megger W Phase", type: "number", unit: "MΩ", standard: "≥ 1.0 MΩ" },
        ],
    },
    {
        id: 3,
        title: "Indoor Unit",
        items: [
            { key: "cfm_indoor", label: "Anemometer (Indoor)", type: "number", unit: "CFM" },
            { key: "coil", label: "Coil & Fins", type: "check" },
            { key: "drain", label: "Drain Pan", type: "check" },
            { key: "drainline", label: "Drain Line", type: "check" },
            { key: "blower", label: "Blower Fan", type: "check" },
            { key: "fanmotor", label: "Fan Motor", type: "check" },
            { key: "wires_in", label: "Wires", type: "check" },
        ],
    },
    {
        id: 4,
        title: "Line Set + Submit",
        items: [
            { key: "ins", label: "Insulation Tape", type: "check" },
            { key: "wire_cond", label: "Wire Condition", type: "check" },
            { key: "cond", label: "Condensation", type: "check" },
            { key: "leak", label: "Leak Check", type: "leak" },
            { key: "notes", label: "Technician Notes", type: "text" },
        ],
    },
];

// 7 leak-detector check spots for the Leak Check step, split into the
// two zones shown in the mockup's leak map.
export const LEAK_SPOTS = [
    { index: 0, zone: "Indoor Unit" },
    { index: 1, zone: "Indoor Unit" },
    { index: 2, zone: "Indoor Unit" },
    { index: 3, zone: "Condenser" },
    { index: 4, zone: "Condenser" },
    { index: 5, zone: "Condenser" },
    { index: 6, zone: "Condenser" },
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
