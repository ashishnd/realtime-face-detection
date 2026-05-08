# Milestone Tags and Phase Gates

This repository uses milestone tags to enforce small, reviewable delivery phases.

## Milestone tags

- `milestone-1-foundation`: scaffold + app bootstrap + DB baseline
- `milestone-2-core-streaming`: schema + manager + CV pipeline + WS + ROI API
- `milestone-3-frontend-tests`: frontend streaming client + tests + compose/runtime
- `milestone-4-docs-release`: README + architecture + attestation

## Gate policy

- Every PR into `main` must include the milestone checklist in the PR body.
- The `phase-gates` workflow fails if any milestone checkbox is not explicitly checked.
- Use the PR template to keep the gate format consistent.
