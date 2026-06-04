"""
Example Usage: Local PII Guardrail Flow
=======================================

This script demonstrates how to intercept an outgoing LLM prompt containing sensitive
user information, run it through the `compliance/pii_masker` skill locally (which leverages
the micro-f1-mask edge model via Ollama), and then generate a secure payload for a cloud LLM API.
"""

from skillware.core.loader import SkillLoader


def simulate_agentic_flow():
    # 1. The user provides a highly sensitive prompt
    raw_user_input = (
        "Please schedule a meeting with Satoshi Nakamoto. "
        "His email is satoshi@bitcoin.org and his wallet is 0x1234567890ABCDEF."
    )
    print("--- 🔴 ORIGINAL RAW INPUT ---")
    print(raw_user_input)
    print()

    # 2. Load the Privacy Firewall Skill
    print("[System] Loading compliance/pii_masker skill...")
    pii_skill = SkillLoader.load_skill("compliance/pii_masker")[
        "module"
    ].PIIMaskerSkill()

    # 3. Intercept and Sanitize (Redact mode)
    print("[System] Intercepting prompt...")
    # NOTE: This requires Ollama running locally with the arpacorp/micro-f1-mask model.
    # If Ollama is not running, the skill falls back to returning the original string.
    result = pii_skill.execute(
        {
            "text": raw_user_input,
            "mode": "redact",  # Change to "mask" to see entity tags like [PERSON_1] instead of XXXX
            "ollama_url": "http://localhost:11434",
        }
    )

    scrubbed_input = result["sanitized_text"]
    metadata = result["metadata"]

    print("\n--- 🟢 SANITIZED PAYLOAD TO CLOUD ---")
    print(scrubbed_input)
    print("\n[System] Metadata:")
    print(metadata)
    print()

    # 4. Safe Cloud Invocation (Simulated)
    # The external cloud provider (Google, Anthropic, OpenAI) never sees the raw PII.
    print("[System] Calling External LLM with sanitized payload...")
    print("... Done.")


if __name__ == "__main__":
    simulate_agentic_flow()
