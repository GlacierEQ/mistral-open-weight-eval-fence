from __future__ import annotations

from open_weight_eval_fence import Decision, OpenWeightEvalFence, OpenWeightEvalFenceRequest


def candidate(eval_id: str, cost: float, classes: list[str], critical: bool = False):
    return {"eval_id": eval_id, "cost": cost, "failure_classes": classes, "critical": critical}


def plan(candidates, required, budget=5.0):
    return OpenWeightEvalFence().evaluate(
        OpenWeightEvalFenceRequest("model-a", {"mode": "plan", "candidates": candidates, "required_failure_classes": required}, budget)
    )


def promote(plan_result, results):
    return OpenWeightEvalFence().evaluate(
        OpenWeightEvalFenceRequest("model-a", {"mode": "promote", "plan": plan_result, "results": results}, 1.0)
    )


def test_planner_maximizes_distinct_failure_coverage_under_budget() -> None:
    receipt = plan([
        candidate("broad", 3.0, ["hallucination", "tool-use", "prompt-injection"]),
        candidate("narrow-a", 2.0, ["hallucination"]),
        candidate("narrow-b", 2.0, ["tool-use"]),
    ], ["hallucination", "tool-use", "prompt-injection"], 3.0)
    assert receipt.decision is Decision.ALLOW
    result = receipt.metrics["result"]
    assert result["selected_eval_ids"] == ["broad"]
    assert result["missing_required_classes"] == []


def test_budget_that_cannot_cover_required_classes_refuses() -> None:
    receipt = plan([
        candidate("a", 2.0, ["hallucination"]),
        candidate("b", 2.0, ["tool-use"]),
    ], ["hallucination", "tool-use"], 2.0)
    assert receipt.decision is Decision.REFUSE
    assert "budget_cannot_cover_required_failure_classes" in receipt.reasons


def test_greedy_selection_values_new_coverage_per_cost() -> None:
    receipt = plan([
        candidate("expensive", 4.0, ["a", "b"]),
        candidate("cheap-a", 1.0, ["a"]),
        candidate("cheap-bc", 1.5, ["b", "c"]),
    ], ["a", "b", "c"], 3.0)
    result = receipt.metrics["result"]
    assert receipt.decision is Decision.ALLOW
    assert set(result["selected_eval_ids"]) == {"cheap-a", "cheap-bc"}


def test_duplicate_eval_ids_fail_closed() -> None:
    receipt = plan([candidate("same", 1.0, ["a"]), candidate("same", 1.0, ["b"])], ["a"], 3.0)
    assert receipt.decision is Decision.REFUSE
    assert "duplicate_eval_id" in receipt.reasons


def test_promotion_allowed_only_when_every_selected_eval_passes() -> None:
    planned = plan([candidate("a", 1.0, ["hallucination"]), candidate("b", 1.0, ["tool-use"])], ["hallucination", "tool-use"], 3.0)
    result = promote(planned.metrics["result"], [{"eval_id": "a", "passed": True}, {"eval_id": "b", "passed": True}])
    assert result.decision is Decision.ALLOW
    assert result.metrics["result"]["promotion_ready"] is True


def test_missing_selected_eval_result_blocks_promotion() -> None:
    planned = plan([candidate("a", 1.0, ["hallucination"]), candidate("b", 1.0, ["tool-use"])], ["hallucination", "tool-use"], 3.0)
    result = promote(planned.metrics["result"], [{"eval_id": "a", "passed": True}])
    assert result.decision is Decision.REFUSE
    assert "selected_eval_result_missing" in result.reasons


def test_failed_eval_blocks_promotion() -> None:
    planned = plan([candidate("a", 1.0, ["hallucination"])], ["hallucination"], 1.0)
    result = promote(planned.metrics["result"], [{"eval_id": "a", "passed": False}])
    assert result.decision is Decision.REFUSE
    assert "eval_fence_failed" in result.reasons


def test_tampered_plan_with_uncovered_required_class_is_refused() -> None:
    tampered = {"selected_eval_ids": ["a"], "required_failure_classes": ["a", "b"], "covered_failure_classes": ["a"]}
    result = promote(tampered, [{"eval_id": "a", "passed": True}])
    assert result.decision is Decision.REFUSE
    assert "required_failure_class_uncovered" in result.reasons
