# Terms of Service Evaluator

**Domain:** `compliance`
**Skill ID:** `compliance/tos_evaluator`

A local-first compliance guardrail that checks whether an intended automated action appears permissible on a target website. It evaluates `robots.txt`, discovers candidate legal pages, extracts relevant clauses, and can optionally use a low-cost LLM to interpret ambiguous policy language.

## What It Checks

1. `robots.txt` rules for the exact target URL and user-agent.
2. Likely Terms, Legal, Acceptable Use, and API policy pages on the same site.
3. Clauses related to scraping, crawling, indexing, monitoring, downloading, and API-only access.
4. Optional LLM-backed clause review when local heuristics cannot confidently classify the policy language.

## Manifest Details

**Parameters Schema:**
* `target_url` (string): Full URL the agent intends to access.
* `intended_action` (string): Natural-language action such as `scrape pricing data` or `index docs`.
* `user_agent` (string, optional): User-agent used for `robots.txt` checks.
* `fetch_mode` (string, optional): `lightweight` or `deep`.
* `use_llm_evaluator` (boolean, optional): Enables optional clause interpretation for low-confidence cases.
* `llm_provider` (string, optional): Provider name for the optional evaluator.
* `llm_model` (string, optional): Model name such as `gemini-2.5-flash-lite`.
* `assume_authenticated_session` (boolean, optional): Helps represent paid or logged-in usage contexts.
* `max_terms_pages` (integer, optional): Caps discovery breadth.

**Outputs Schema:**
* `is_safe_to_proceed` (boolean): Whether the action was approved.
* `confidence_score` (number): Confidence in the verdict.
* `verdict` (string): `SAFE`, `UNSAFE`, `CAUTION`, or `INSUFFICIENT_EVIDENCE`.
* `reason` (string): Short explanation of the verdict.
* `robots_assessment` (object): Structured `robots.txt` result.
* `tos_assessment` (object): Structured policy discovery and clause result.
* `llm_assessment` (object): Optional evaluator result.
* `evidence` (array): Supporting snippets and sources.

## Verdict Semantics

* `SAFE`: strong evidence suggests the requested action is allowed, and `robots.txt` does not block it.
* `UNSAFE`: `robots.txt` blocks the path or discovered policy text explicitly restricts the automation.
* `CAUTION`: the site may allow access, but only with conditions such as API usage, permission, or strict rate limits.
* `INSUFFICIENT_EVIDENCE`: the evaluator could not find enough trustworthy evidence to safely approve the action.

## Example Usage (Direct)

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
TOSEvaluatorSkill = bundle["module"].TOSEvaluatorSkill
skill = TOSEvaluatorSkill()

result = skill.execute(
    {
        "target_url": "https://hackernoon.com/tagged/ai",
        "intended_action": "crawl tagged article pages for research indexing",
        "use_llm_evaluator": True,
        "llm_provider": "gemini",
        "llm_model": "gemini-2.5-flash-lite",
    }
)

print(result["verdict"])
print(result["reason"])
```

## Gemini Example

Use the skill through `SkillLoader.to_gemini_tool(...)` and pass the skill instructions as the `system_instruction`. See `examples/gemini_tos_evaluator.py`.

## Claude Example

Use the skill through `SkillLoader.to_claude_tool(...)` and return the structured result back to Claude as a tool result. See `examples/claude_tos_evaluator.py`.

## Ollama Example

Use the text-based prompt adapter from `SkillLoader.to_ollama_prompt(...)` and execute the skill locally when the model emits a JSON tool block. See `examples/ollama_tos_evaluator.py`.

## Notes

This skill is a practical operational safeguard, not legal counsel. If the result is `CAUTION` or `INSUFFICIENT_EVIDENCE`, the safe default is manual review or an official API/developer integration path.

To run tests specifically for this skill:

```bash
pytest tests/skills/compliance/test_tos_evaluator.py
pytest skills/compliance/tos_evaluator/test_skill.py
```
