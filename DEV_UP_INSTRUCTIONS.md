# DEV_UP_INSTRUCTIONS — implementation record

**Repository:** `GlacierEQ/mistral-open-weight-eval-fence`  
**Independent company lens:** Mistral AI  
**Innovation:** Open Weight Eval Fence

## Mission

Use finite evaluation budget to maximize failure-class coverage and block model promotion until the selected fence is completely proven.

## Implemented

The generic scaffold has been replaced by a two-stage evaluation portfolio system.

`src/open_weight_eval_fence.py` now:

- validates candidate eval identities, costs and covered failure classes;
- selects a deterministic portfolio by new failure coverage per unit cost;
- refuses planning when required failure classes cannot fit the budget;
- records selected eval identities, coverage, budget consumption and plan digest;
- verifies promotion against the exact selected plan;
- refuses missing results, failed evals, duplicate identities and uncovered required classes;
- emits deterministic verification and decision receipts.

`src/open_weight_eval_cli.py` and `scripts/operate.py` execute the planner directly. The project is packaged with the `open-weight-eval-fence` console command.

## Verification contract

Behavioral tests cover broad-vs-narrow coverage selection, insufficient budget, coverage-per-cost optimization, duplicate ids, all-pass promotion, missing results, failed evals and tampered uncovered plans. Existing adversarial coverage remains active.

CI must pass tests, cold-start, wheel build/install and installed CLI execution before Helix promotion evidence can be minted.

## Truth boundary

No Mistral AI affiliation, proprietary access, production deployment, customer impact, or company partnership is claimed. A provider-swappable real eval runner remains a further end-to-end depth step.
