# airlogic

Odoo SH deploy target for **Standard Airlogic** (aircon service management):
field service, dispatch, parts/consumables purchasing, and subscription
billing. Odoo 19.0, Enterprise.

Extracted from `kinjoheika/philjapagency` (which now serves the unrelated
Kiroku/KTC platform only) with full commit history for the 3 modules below
preserved via `git filter-repo`. Anything Kiroku-specific was deliberately
left behind, including its own commit history for shared infra files prior
to this split.

## Modules

- **`airlogic_core`** ("Inventory") — clients, equipment, service visits,
  the 4 role groups (Technician / Operations Officer / Manager /
  Accounting).
- **`airlogic_field_service`** ("Field Service") — the technician-facing
  mobile app, PDF reports, parts/consumables requests, subscription
  contracts.
- **`airlogic_dispatch`** ("Dispatch") — zones and the 6-rule dispatch
  cascade.

## New contributor / new session onboarding

**Enable the commit-message hook first, before authoring any commit:**

```bash
cd /path/to/airlogic
git config core.hooksPath .githooks
```

This activates [`.githooks/commit-msg`](.githooks/commit-msg), which
enforces the KCC-1.0 commit-message standard (carried over unchanged from
`philjapagency`, already proven against this project's own commits).

**Standard grammar:**

```
<type>[!](<scope>): <subject>[ (<task-id>)]
```

- `type` — feat|fix|refactor|perf|docs|style|test|build|ci|chore|revert
- `subject` — imperative, ≤72 chars total on the line
- `task-id` — required for feat/fix, e.g. `AIR-T70`; optional otherwise

## Odoo.sh

This repo drives its own dedicated odoo.sh project — separate from
`philjapagency`'s, which continues to serve Kiroku alone.
