"""Bedrock-backed plain-English explanation layer for TRAC3R verification results.

If Bedrock is unreachable (no creds, no network, model access not granted, etc.),
explain() falls back to a pre-written explanation keyed off status so callers can
always rely on a non-empty string.
"""
import json

BEDROCK_REGION = "us-east-1"
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

FALLBACK_EXPLANATIONS = {
    "verified": "This dataset passed all integrity checks. No anomalies were detected. It is safe for use by agents or automated systems.",
    "warning": "This dataset passed most integrity checks but contains minor issues. Review before use.",
    "flagged": "This dataset failed integrity checks. Anomalies were detected that may indicate manipulation or data corruption. Reject or review manually before use.",
}


def build_prompt(flags: list[str], trust_score: float, status: str) -> str:
    flag_text = "\n".join(f"- {f}" for f in flags) if flags else "- No anomalies detected."
    return f"""You are a data integrity analyst. A dataset has been verified by TRAC3R with the following results:

Trust Score: {trust_score}
Status: {status.upper()}
Anomalies Detected:
{flag_text}

Write a 2-3 sentence plain-English explanation of what these results mean and whether an autonomous agent or application should trust this data. Be specific about the anomalies. End with a clear recommendation: proceed, review manually, or reject."""


def explain(flags: list[str], trust_score: float, status: str) -> str:
    try:
        import boto3

        client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": build_prompt(flags, trust_score, status)}],
        })
        response = client.invoke_model(modelId=BEDROCK_MODEL_ID, body=body)
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
    except Exception:
        return FALLBACK_EXPLANATIONS.get(status.lower(), FALLBACK_EXPLANATIONS["flagged"])
