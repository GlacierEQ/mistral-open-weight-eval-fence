"""Open Weight Eval Fence.

Plans a bounded evaluation portfolio to maximize distinct failure-class coverage,
then refuses model promotion unless required classes are covered and every
executed fence evaluation passes.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REFUSE = "REFUSE"


@dataclass(frozen=True)
class OpenWeightEvalFenceRequest:
    subject_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    budget: float = 1.0
    grant_id: str | None = None
    not_after: float | None = None


@dataclass(frozen=True)
class OpenWeightEvalFenceReceipt:
    decision: Decision
    reasons: tuple[str, ...]
    digest: str
    metrics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"decision": self.decision.value, "reasons": list(self.reasons), "digest": self.digest, "metrics": self.metrics}


class EvalFenceError(ValueError):
    pass


class OpenWeightEvalFence:
    MIN_BUDGET = 0.0

    @staticmethod
    def _num(value: Any, label: str, *, minimum: float | None = None) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EvalFenceError(f"{label}_invalid")
        value = float(value)
        if not math.isfinite(value):
            raise EvalFenceError(f"{label}_not_finite")
        if minimum is not None and value < minimum:
            raise EvalFenceError(f"{label}_below_minimum")
        return value

    @staticmethod
    def _classes(value: Any, label: str) -> set[str]:
        if not isinstance(value, list) or not value:
            raise EvalFenceError(f"{label}_missing")
        classes = {str(item).strip() for item in value if str(item).strip()}
        if not classes:
            raise EvalFenceError(f"{label}_missing")
        return classes

    @classmethod
    def _candidate(cls, raw: Any, index: int) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise EvalFenceError(f"eval_{index}_not_object")
        eval_id = str(raw.get("eval_id", "")).strip()
        if not eval_id:
            raise EvalFenceError(f"eval_{index}_id_missing")
        return {
            "eval_id": eval_id,
            "cost": cls._num(raw.get("cost"), f"eval_{index}_cost", minimum=0.001),
            "failure_classes": cls._classes(raw.get("failure_classes"), f"eval_{index}_failure_classes"),
            "critical": bool(raw.get("critical", False)),
        }

    @classmethod
    def plan(cls, candidates_raw: Any, required_raw: Any, budget: float) -> dict[str, Any]:
        if not isinstance(candidates_raw, list) or not candidates_raw:
            raise EvalFenceError("candidates_missing")
        required = cls._classes(required_raw, "required_failure_classes")
        candidates = [cls._candidate(row, i) for i, row in enumerate(candidates_raw)]
        if len({c["eval_id"] for c in candidates}) != len(candidates):
            raise EvalFenceError("duplicate_eval_id")
        selected: list[dict[str, Any]] = []
        covered: set[str] = set()
        spent = 0.0
        remaining = list(candidates)
        while remaining:
            affordable = [c for c in remaining if spent + c["cost"] <= budget]
            if not affordable:
                break
            affordable.sort(
                key=lambda c: (
                    -len(c["failure_classes"] - covered) / c["cost"],
                    -int(c["critical"]),
                    c["cost"],
                    c["eval_id"],
                )
            )
            best = affordable[0]
            gain = best["failure_classes"] - covered
            if not gain and required <= covered:
                break
            selected.append(best)
            spent += best["cost"]
            covered |= best["failure_classes"]
            remaining.remove(best)
        missing = sorted(required - covered)
        return {
            "selected_eval_ids": [c["eval_id"] for c in selected],
            "covered_failure_classes": sorted(covered),
            "required_failure_classes": sorted(required),
            "missing_required_classes": missing,
            "spent": round(spent, 12),
            "budget": budget,
            "plan_digest": _digest({"selected": [c["eval_id"] for c in selected], "covered": sorted(covered), "spent": spent, "required": sorted(required)}),
        }

    @classmethod
    def verify_promotion(cls, plan: Any, results_raw: Any) -> dict[str, Any]:
        if not isinstance(plan, dict):
            raise EvalFenceError("plan_missing")
        selected = plan.get("selected_eval_ids")
        required = set(plan.get("required_failure_classes") or [])
        covered = set(plan.get("covered_failure_classes") or [])
        if not isinstance(selected, list) or not selected:
            raise EvalFenceError("selected_eval_ids_missing")
        if required - covered:
            raise EvalFenceError("required_failure_class_uncovered")
        if not isinstance(results_raw, list):
            raise EvalFenceError("results_missing")
        results: dict[str, dict[str, Any]] = {}
        for i, raw in enumerate(results_raw):
            if not isinstance(raw, dict):
                raise EvalFenceError(f"result_{i}_not_object")
            eval_id = str(raw.get("eval_id", "")).strip()
            if not eval_id or eval_id in results:
                raise EvalFenceError("result_identity_invalid_or_duplicate")
            results[eval_id] = raw
        missing_results = [eval_id for eval_id in selected if eval_id not in results]
        failed = [eval_id for eval_id in selected if eval_id in results and results[eval_id].get("passed") is not True]
        return {
            "selected_eval_ids": selected,
            "missing_results": missing_results,
            "failed_eval_ids": failed,
            "promotion_ready": not missing_results and not failed,
            "verification_digest": _digest({"selected": selected, "missing": missing_results, "failed": failed}),
        }

    def evaluate(self, req: OpenWeightEvalFenceRequest) -> OpenWeightEvalFenceReceipt:
        reasons: list[str] = []
        if not str(req.subject_id or "").strip():
            reasons.append("subject_id_missing")
        if isinstance(req.budget, bool) or not isinstance(req.budget, (int, float)) or not math.isfinite(float(req.budget)) or float(req.budget) <= self.MIN_BUDGET:
            reasons.append("budget_non_positive_or_invalid")
        payload = req.payload if isinstance(req.payload, dict) else {}
        if not isinstance(req.payload, dict):
            reasons.append("payload_not_object")
        result: dict[str, Any] | None = None
        try:
            mode = str(payload.get("mode", "plan")).lower()
            if mode == "plan":
                result = self.plan(payload.get("candidates"), payload.get("required_failure_classes"), float(req.budget))
                if result["missing_required_classes"]:
                    reasons.append("budget_cannot_cover_required_failure_classes")
            elif mode == "promote":
                result = self.verify_promotion(payload.get("plan"), payload.get("results"))
                if result["missing_results"]:
                    reasons.append("selected_eval_result_missing")
                if result["failed_eval_ids"]:
                    reasons.append("eval_fence_failed")
            else:
                raise EvalFenceError("mode_invalid")
        except EvalFenceError as exc:
            reasons.append(str(exc))
        decision = Decision.REFUSE if reasons else Decision.ALLOW
        metrics = {"result": result}
        body = {"subject_id": req.subject_id, "decision": decision.value, "reasons": reasons, "metrics": metrics}
        return OpenWeightEvalFenceReceipt(decision, tuple(reasons or ["eval_fence_passed"]), _digest(body), metrics)


Mechanism = OpenWeightEvalFence
