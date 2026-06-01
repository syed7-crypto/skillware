# EVM Transaction Handler

**ID**: `defi/evm_tx_handler`  
**Issuer**: [@Hendobox](https://github.com/Hendobox)

[Skill Library](README.md) · [Testing](../TESTING.md)

Structured EVM operations for a **dedicated agent wallet**: resolve trade intent, quote Uniswap V2 swaps, preview outcomes, and send native/ERC20 transfers. **PR1** ships read/plan/transfer paths; **swap `execute`** arrives in PR2.

## Capabilities (PR1)

| Action | Description |
|--------|-------------|
| `resolve` | Merge intent with config and YAML registries; surface missing fields |
| `quote` / `preview` | On-chain Uni V2 quote (buy/sell) |
| `transfer` | Sign and send native or ERC20 (with optional confirmation gate) |
| `balances` | Wallet balances for registered tokens |
| `wallet_info` | Address, supported chains, preferences (no secrets) |
| `update_preferences` | Persist allowed keys to `config.yaml` |
| `execute` | Returns `not_available` until PR2 |

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `AGENT_WALLET_PRIVATE_KEY` | Yes | Dedicated agent wallet (never in tool args) |
| `ETHEREUM_RPC_URL` | If using `ethereum` | JSON-RPC |
| `BASE_RPC_URL` | If using `base` | JSON-RPC |
| `COINGECKO_API_KEY` | No | Reserved for USD caps in a later release |

Copy `skills/defi/evm_tx_handler/config.yaml.example` to `config.yaml` in the same folder for long-term defaults. See [API keys for skills](../usage/api_keys.md).

## Registry data

- `data/chains.yaml` — chain IDs, RPC env keys, explorers, Uni V2 routers  
- `data/tokens.yaml` — symbol → contract per chain  
- `data/addressbook.yaml` — label → address  

## Usage Examples

Sample user message: *“Buy 10 DEGEN on Base with USDC”* → `resolve` → `quote` → show preview (execution in PR2).

### Load and run

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("defi/evm_tx_handler")
skill = bundle["module"].EvmTxHandlerSkill()

result = skill.execute({
    "action": "resolve",
    "intent": {
        "side": "buy",
        "chain": "base",
        "target_asset": "degen",
        "amount": 10,
        "amount_kind": "target_out",
    },
})
```

Provider loops: [Agent loops](../usage/agent_loops.md), [Gemini](../usage/gemini.md), [Claude](../usage/claude.md).

## Limitations (PR1)

- No swap broadcast (`execute` stubbed).  
- Uniswap V2 only; Ethereum + Base.  
- No cross-chain bridges or aggregators.  
- Create and fund the agent wallet outside the skill; key only in `.env`.

## Security

- Fail closed on missing RPC or registry entries.  
- `confirm_before_send` blocks transfers until `confirmed: true`.  
- Not financial or legal advice; agents can mis-parse NL — always preview.
