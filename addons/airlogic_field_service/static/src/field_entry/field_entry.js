/** @odoo-module **/

// This file used to also define AirlogicVisualChecklist, a desktop-only
// OWL client action for entering the checklist from Inventory. Removed:
// checklist data is entered exclusively through the Field Service
// mobile app now, and the desktop Job form shows it read-only (see
// airlogic_service_job_views.xml's Visual Checklist page). PHASES/
// LEAK_SPOTS stay here and stay exported -- mobile_app.js imports them
// from this same module path, and moving them would just be churn.

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
        title: "Outdoor/Indoor ON",
        items: [
            { key: "amp_draw", label: "Amp Draw", type: "number", unit: "A" },
            { key: "cfm_outdoor", label: "Anemometer (Outdoor)", type: "number", unit: "CFM" },
            { key: "cfm_indoor", label: "Anemometer (Indoor)", type: "number", unit: "CFM" },
        ],
    },
    {
        id: 2,
        title: "Outdoor OFF",
        items: [
            { key: "meg_u", label: "Megger U Phase", type: "number", unit: "MΩ", standard: "≥ 1.0 MΩ" },
            { key: "meg_v", label: "Megger V Phase", type: "number", unit: "MΩ", standard: "≥ 1.0 MΩ" },
            { key: "meg_w", label: "Megger W Phase", type: "number", unit: "MΩ", standard: "≥ 1.0 MΩ" },
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
        id: 3,
        title: "Indoor OFF",
        items: [
            { key: "coil", label: "Coil & Fins", type: "check" },
            { key: "drain", label: "Drain Pan", type: "check" },
            { key: "drainline", label: "Drain Line", type: "check" },
            { key: "motor_fan", label: "Motor & Fan", type: "check" },
            { key: "wires_in", label: "Wires & Sensors", type: "check" },
        ],
    },
    {
        id: 4,
        title: "Lines",
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

