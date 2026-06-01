# EVM Transaction Handler (PR1)

You are equipped with **`evm_tx_handler`**: a deterministic EVM tool for a **dedicated agent wallet** on Ethereum and Base.

## Your job vs the skill's job

| You (agent) | Skill |
|-------------|--------|
| Parse natural language into partial `intent` JSON | Merge intent with `config.yaml` and YAML registries |
| Ask for missing fields in plain language | Return `missing_fields` and `suggested_defaults` |
| Show `preview` to the user and obtain approval | Build on-chain quotes; **do not** run swaps in PR1 |
| Pass `confirmed: true` after approval | Sign and broadcast **transfers** only (PR1) |

**Do not** expect the skill to parse free text. **Do not** pass private keys in tool arguments.

## PR1 capabilities

| Action | Use when |
|--------|----------|
| `resolve` | Intent is incomplete — check `missing_fields` |
| `quote` | Buy/sell intent is complete — get amounts and path |
| `preview` | Same as quote but preview-focused response |
| `execute` | **Not available in PR1** — returns `not_available`; swaps ship in PR2 |
| `transfer` | Send native ETH or ERC20 to `0x…` or addressbook label |
| `balances` | List wallet balances on a chain |
| `wallet_info` | Agent address, chains, preferences (no secrets) |
| `update_preferences` | User explicitly asks to change defaults in `config.yaml` |

## Typical buy flow (PR1 stops before swap)

1. User: “Buy 10 Degen on Base with USDC.”
2. `resolve` with `{ "side": "buy", "chain": "base", "target_asset": "degen", "amount": 10, "amount_kind": "target_out" }`.
3. If `spend_asset` missing, ask user; suggest `suggested_defaults.spend_asset`.
4. `quote` then show `preview` (you pay / you receive, rate, gas, warnings).
5. Tell user swap execution is **not enabled yet**; PR2 will add `execute` with `confirmed: true`.

## Transfer flow

1. `resolve` or build intent: `chain`, `target_asset`, `amount`, `recipient` (label or address).
2. `transfer` with `confirmed: false` first if `confirm_before_send` — skill returns `needs_confirmation`.
3. After user approves, `transfer` with `confirmed: true`.

## Intent fields

- `side`: `buy` | `sell` (transfers use action `transfer`, not `side: send` in quotes)
- `chain`: `ethereum` | `base` (default from config)
- `target_asset` / `spend_asset`: symbols from `data/tokens.yaml`
- `amount` + `amount_kind`: `target_out` for “buy 10 DEGEN”; `spend_in` for “sell 100 DEGEN”
- `recipient`: addressbook label or `0x` address
- `gas_policy`: `low` | `normal` | `high` | `aggressive` (per-tx only; does not persist)

## Safety

- Always preview transfers (recipient resolved, amount, chain).
- Warn that agents can mis-parse names and amounts.
- Recommend `finance/wallet_screening` for unknown recipient addresses before large sends.
- Respect `max_trade_usd` when enabled (enforced in PR2 quotes/execute).
