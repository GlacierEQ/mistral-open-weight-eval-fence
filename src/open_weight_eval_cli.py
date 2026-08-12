from __future__ import annotations

import argparse
import json
from pathlib import Path

from open_weight_eval_fence import Decision, OpenWeightEvalFence, OpenWeightEvalFenceRequest


def demo_payload() -> dict:
    return {
        "mode": "plan",
        "required_failure_classes": ["hallucination", "tool-use", "prompt-injection"],
        "candidates": [
            {"eval_id": "broad-safety", "cost": 3.0, "failure_classes": ["hallucination", "tool-use", "prompt-injection"], "critical": True},
            {"eval_id": "code-only", "cost": 1.0, "failure_classes": ["tool-use"]},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or verify an open-weight evaluation fence")
    parser.add_argument("--input", type=Path, help="JSON payload; defaults to a deterministic planning demo")
    parser.add_argument("--subject", default="eval-fence-demo")
    parser.add_argument("--budget", type=float, default=3.0)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text()) if args.input else demo_payload()
    receipt = OpenWeightEvalFence().evaluate(OpenWeightEvalFenceRequest(args.subject, payload, args.budget))
    print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    return 0 if receipt.decision is Decision.ALLOW else 2


if __name__ == "__main__":
    raise SystemExit(main())
