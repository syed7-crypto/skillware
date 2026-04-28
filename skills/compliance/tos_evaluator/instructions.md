# Operational Instructions: TOS Evaluator

You are an agent equipped with the `compliance/tos_evaluator` skill.

## When to use this skill
- Use this skill before scraping, crawling, indexing, bulk downloading, automated monitoring, or other programmatic access to a website.
- Use it when the user asks whether a website permits bots, scraping, or non-browser automation.
- Use it when you need a conservative compliance check before a downstream agent or script touches a domain.

## What this skill actually checks
The skill evaluates:
1. `robots.txt` access rules for the requested URL and user-agent.
2. Candidate Terms of Service, legal, acceptable-use, and API policy pages discovered on the same site.
3. Optional low-cost LLM review for ambiguous legal clauses when enabled.

## How to interpret the output
- `SAFE`: strong evidence suggests the requested action is allowed, and `robots.txt` does not block it.
- `UNSAFE`: `robots.txt` blocks the path or the discovered policy text explicitly restricts the requested automation.
- `CAUTION`: the site may allow some access, but the policy text contains conditions, ambiguities, or API-only restrictions.
- `INSUFFICIENT_EVIDENCE`: the skill could not find enough trustworthy evidence to safely approve the action.

Always explain the result conservatively. This tool is an operational guardrail, not legal counsel.

## Important behavior rules
- Do not claim legal certainty.
- If the result is `CAUTION` or `INSUFFICIENT_EVIDENCE`, recommend manual review or an official API path.
- If the result is `UNSAFE`, clearly tell the user not to proceed without explicit permission.
- If the result relied on `llm_assessment`, mention that it was an auxiliary interpretation layer on top of fetched evidence.

## Example uses
- User: "Can I scrape pricing from this page?" -> call the tool with `target_url` and `intended_action=\"scrape pricing data\"`
- User: "Can I index these docs into search?" -> call the tool with `intended_action=\"index documentation pages\"`
- User: "Can I use a bot to monitor changes daily?" -> call the tool with `intended_action=\"monitor content with automated bot\"`
- If legal language is vague and the user enabled fallback review, set `use_llm_evaluator=true`.
