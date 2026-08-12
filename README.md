# Open Weight Eval Fence

Independent GlacierEQ portfolio implementation aligned to **Mistral AI** operating themes.

> **Not affiliated.** This repository is not affiliated with, endorsed by, employed by, or deployed at Mistral AI. No proprietary access, production deployment, customer impact, or company partnership is claimed.

## Purpose

Treat evaluation as a **coverage portfolio under a finite budget**, then make promotion impossible unless the selected fence actually ran and passed.

## Implemented fence

`OpenWeightEvalFence` has two phases.

### Plan

Given candidate evaluations, their execution cost, and the failure classes each covers, the planner selects a deterministic portfolio that maximizes new failure-class coverage per cost while staying inside the declared budget. Required failure classes are explicit. If the available budget cannot cover them, planning fails closed.

### Promote

The promotion fence consumes the exact selected plan and executed results. Promotion is refused when:

- a required failure class was never covered;
- a selected evaluation result is missing;
- any selected evaluation failed;
- identities are duplicated or malformed.

The plan and verification each carry deterministic digests.

## Run

```bash
python -m pytest -q
python scripts/operate.py
```

Build and install:

```bash
python -m pip install build
python -m build
python -m pip install dist/*.whl
open-weight-eval-fence
```

## Proof surface

- `src/open_weight_eval_fence.py` — budgeted coverage planner + promotion verifier
- `src/open_weight_eval_cli.py` — installable execution surface
- `tests/test_open_weight_eval_fence.py` — coverage, budget, duplicate, missing-result and failed-eval behavior
- `tests/test_adversarial.py` — fail-closed adversarial coverage
- `.github/workflows/tests.yml` — tests + cold-start + wheel build/install + installed CLI
- `machine/` — existing Helix control-plane and promotion surfaces remain preserved

## Current boundary

The mechanism consumes declared eval costs, coverage and results; it does not call Mistral AI services or claim proprietary evaluation data. The next depth step is a provider-swappable eval runner that produces these result receipts from permitted cloud/on-prem model endpoints while keeping the same fence contract.
