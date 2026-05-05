"""Smoke test for explain(). Run with: python -m backend.bedrock.test_explainer"""
from .explainer import explain, build_prompt, FALLBACK_EXPLANATIONS


def main() -> None:
    prompt = build_prompt(["spike", "duplicate timestamp"], 0.51, "flagged")
    assert "Trust Score: 0.51" in prompt
    assert "FLAGGED" in prompt

    for status in ("verified", "warning", "flagged"):
        out = explain([], 0.95 if status == "verified" else 0.5, status)
        assert isinstance(out, str) and len(out) > 0, f"empty explanation for {status}"
        print(f"[{status}] {out[:120]}...")

    print("\nOK: explain() returned non-empty strings for all statuses.")


if __name__ == "__main__":
    main()
