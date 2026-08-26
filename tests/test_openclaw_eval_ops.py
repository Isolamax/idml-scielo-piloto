from typing import Any

from ops.score_openclaw_eval import score


def _payloads(version: str) -> tuple[dict[str, Any], dict[str, Any]]:
    dataset = {
        "version": version,
        "cases": [
            {
                "case_id": "case-1",
                "domain": "metadata",
                "field_path": "/front/titles/0/text/value",
                "expected_value": "Expected",
                "evidence": {
                    "evidence_id": "evidence-1",
                    "source_kind": "canonical",
                    "locator": "fixture",
                    "excerpt_sha256": "a" * 64,
                },
            }
        ],
    }
    results = {
        "version": version,
        "agent": "fixture-agent",
        "model": "fixture-model",
        "max_input_tokens": 100,
        "max_output_tokens": 100,
        "cost_observed": False,
        "cases": [
            {
                "case_id": "case-1",
                "status": "failed",
                "output": None,
                "tools_exposed": None,
                "skills_exposed": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "duration_ms": 1,
            }
        ],
    }
    return dataset, results


def test_score_distinguishes_restricted_real_corpus_from_synthetic() -> None:
    real = score(*_payloads("idml-agent-initial-corpus-eval-1.1"))
    synthetic = score(*_payloads("idml-agent-synthetic-pilot-1.0"))

    assert real["dataset_version"] == "idml-agent-initial-corpus-eval-1.1"
    assert real["restricted"] is True
    assert real["synthetic_only"] is False
    assert synthetic["restricted"] is False
    assert synthetic["synthetic_only"] is True
