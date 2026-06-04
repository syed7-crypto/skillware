"""
Shared helpers for evm_tx_handler examples.

Set EVM_TX_HANDLER_EXAMPLE_DEMO=1 to run the full resolve → quote → preview → execute
flow with mocked Web3 (no live RPC or private key required).
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from typing import Any, Dict, Iterator
from unittest.mock import MagicMock, patch

from skillware.core.loader import SkillLoader

SKILL_ID = "defi/evm_tx_handler"

BUY_INTENT: Dict[str, Any] = {
    "side": "buy",
    "chain": "base",
    "target_asset": "degen",
    "spend_asset": "usdc",
    "amount": 10,
    "amount_kind": "target_out",
}


def demo_mode_enabled() -> bool:
    return os.environ.get("EVM_TX_HANDLER_EXAMPLE_DEMO", "").strip() in (
        "1",
        "true",
        "yes",
    )


@contextmanager
def demo_skill() -> Iterator[Any]:
    """Yield an EvmTxHandlerSkill with mocked chain access for examples."""
    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["module"].EvmTxHandlerSkill()
    test_key = "0x" + "11" * 32
    os.environ.setdefault("AGENT_WALLET_PRIVATE_KEY", test_key)
    os.environ.setdefault("BASE_RPC_URL", "http://localhost:8546")

    skill_dir = os.path.join(os.path.dirname(__file__), "..", "skills", "defi", "evm_tx_handler")
    if skill_dir not in sys.path:
        sys.path.insert(0, os.path.abspath(skill_dir))
    from abis import ROUTER_V2_ABI  # type: ignore[import-not-found]

    w3 = MagicMock()
    w3.eth.gas_price = 10**9
    w3.eth.get_transaction_count.return_value = 0
    w3.eth.get_balance = MagicMock(return_value=10**20)
    w3.to_wei.side_effect = lambda val, unit: int(val * 10**9) if unit == "gwei" else val

    router = MagicMock()
    router.functions.getAmountsIn.return_value.call.return_value = [
        100_000_000,
        10_000_000_000_000_000_000,
    ]
    router.functions.swapTokensForExactTokens.return_value.build_transaction.return_value = {
        "gas": 250000,
    }

    erc20 = MagicMock()

    def _allowance(_owner, _spender):
        fn = MagicMock()
        fn.call.return_value = 0
        return fn

    def _balance_of(_addr):
        fn = MagicMock()
        fn.call.return_value = 10**18
        return fn

    erc20.functions.allowance.side_effect = _allowance
    erc20.functions.balanceOf.side_effect = _balance_of
    erc20.functions.approve.return_value.build_transaction.return_value = {"gas": 60000}

    def contract_factory(address=None, abi=None):
        if abi == ROUTER_V2_ABI:
            return router
        return erc20

    w3.eth.contract.side_effect = contract_factory

    patches = [
        patch.object(skill, "_get_web3", return_value=w3),
        patch.object(skill, "_sign_and_send", side_effect=["0xapprove", "0xswap"]),
        patch.object(
            skill,
            "_wait_receipt",
            return_value={"block_number": 1, "gas_used": 200000, "success": True},
        ),
        patch.object(skill, "_usd_for_token_amount", return_value=10.0),
    ]
    for item in patches:
        item.start()
    try:
        yield skill
    finally:
        for item in reversed(patches):
            item.stop()


def load_skill():
    if demo_mode_enabled():
        return demo_skill()
    bundle = SkillLoader.load_skill(SKILL_ID)
    return bundle["module"].EvmTxHandlerSkill()


def run_scripted_flow(skill: Any, *, execute: bool = False) -> None:
    """Deterministic agent-style sequence using structured skill actions."""
    print("=== evm_tx_handler scripted flow ===\n")

    print("1) resolve")
    resolved = skill.execute({"action": "resolve", "intent": BUY_INTENT})
    print(json.dumps(resolved, indent=2))

    print("\n2) quote")
    quote = skill.execute({"action": "quote", "intent": BUY_INTENT})
    print(json.dumps(quote, indent=2))

    print("\n3) preview")
    preview = skill.execute({"action": "preview", "intent": BUY_INTENT})
    print(json.dumps(preview, indent=2))

    if not execute:
        print(
            "\nSkipping execute (pass execute=True or set EVM_TX_HANDLER_EXAMPLE_DEMO=1)."
        )
        return

    print("\n4) execute (confirmed)")
    result = skill.execute(
        {"action": "execute", "intent": BUY_INTENT, "confirmed": True}
    )
    print(json.dumps(result, indent=2))


def handle_tool_call(skill: Any, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a single evm_tx_handler tool call payload."""
    return skill.execute(tool_input)
