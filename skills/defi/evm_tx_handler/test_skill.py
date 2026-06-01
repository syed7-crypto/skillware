import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

from skillware.core.loader import SkillLoader

from .skill import EvmTxHandlerSkill

TEST_KEY = "0x" + "11" * 32


@pytest.fixture
def skill(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_WALLET_PRIVATE_KEY", TEST_KEY)
    monkeypatch.setenv("ETHEREUM_RPC_URL", "http://localhost:8545")
    monkeypatch.setenv("BASE_RPC_URL", "http://localhost:8546")
    return EvmTxHandlerSkill()


@pytest.fixture
def manifest():
    path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_manifest_consistency(skill, manifest):
    assert skill.manifest["name"] == manifest["name"]


def test_loader_loads_skill(monkeypatch):
    monkeypatch.setenv("AGENT_WALLET_PRIVATE_KEY", TEST_KEY)
    bundle = SkillLoader.load_skill("defi/evm_tx_handler")
    assert bundle["manifest"]["name"] == "evm_tx_handler"
    cls = bundle["module"].EvmTxHandlerSkill
    instance = cls()
    assert instance.execute({"action": "wallet_info", "intent": {}})["status"] == "ready"


def test_resolve_missing_spend_asset(skill):
    result = skill.execute(
        {
            "action": "resolve",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "needs_input"
    assert "spend_asset" in result["missing_fields"]
    assert result["suggested_defaults"]["spend_asset"] == "usdc"


@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_quote_buy(mock_web3, skill):
    w3 = MagicMock()
    w3.eth.gas_price = 10**9
    w3.to_wei.side_effect = lambda val, unit: int(val * 10**9) if unit == "gwei" else val
    mock_web3.return_value = w3

    router = MagicMock()
    router.functions.getAmountsIn.return_value.call.return_value = [100_000_000, 10_000_000_000_000_000_000]
    w3.eth.contract.return_value = router

    result = skill.execute(
        {
            "action": "quote",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "ready"
    assert result["preview"]["you_pay"]["asset"] == "usdc"
    assert result["preview"]["you_receive"]["asset"] == "degen"
    assert "quote" in result
    assert result["requires_confirmation"] is True


@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_quote_sell(mock_web3, skill):
    w3 = MagicMock()
    w3.eth.gas_price = 10**9
    w3.to_wei.side_effect = lambda val, unit: int(val * 10**9) if unit == "gwei" else val
    mock_web3.return_value = w3

    router = MagicMock()
    router.functions.getAmountsOut.return_value.call.return_value = [10**18, 50_000_000]
    w3.eth.contract.return_value = router

    result = skill.execute(
        {
            "action": "quote",
            "intent": {
                "side": "sell",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 1,
                "amount_kind": "spend_in",
            },
        }
    )
    assert result["status"] == "ready"
    assert result["preview"]["side"] == "sell"


def test_execute_not_available_pr1(skill):
    result = skill.execute(
        {
            "action": "execute",
            "intent": {"side": "buy", "chain": "base", "target_asset": "degen", "spend_asset": "usdc"},
            "confirmed": True,
        }
    )
    assert result["status"] == "not_available"
    assert result["code"] == "pr2_execute"


def test_execute_needs_confirmation_when_enabled(skill):
    result = skill.execute(
        {
            "action": "execute",
            "intent": {"side": "buy", "chain": "base", "target_asset": "degen", "spend_asset": "usdc"},
            "confirmed": False,
        }
    )
    assert result["status"] == "needs_confirmation"


def test_missing_rpc_fail_closed(skill, monkeypatch):
    monkeypatch.delenv("BASE_RPC_URL", raising=False)
    result = skill.execute(
        {
            "action": "balances",
            "intent": {"chain": "base"},
        }
    )
    assert result["status"] == "error"
    assert "BASE_RPC_URL" in result["message"]


def test_update_preferences_rejects_unknown_keys(skill):
    result = skill.execute(
        {
            "action": "update_preferences",
            "preferences": {"not_a_real_key": True},
        }
    )
    assert result["status"] == "error"
    assert "not_a_real_key" in result["message"]


def test_resolve_ready_buy(skill):
    result = skill.execute(
        {
            "action": "resolve",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "ready"
    assert result["resolved"]["spend_asset"] == "usdc"


def test_transfer_requires_confirmation(skill):
    result = skill.execute(
        {
            "action": "transfer",
            "intent": {
                "chain": "base",
                "target_asset": "usdc",
                "amount": 10,
                "recipient": "mom",
            },
        }
    )
    assert result["status"] == "needs_confirmation"


@patch.object(EvmTxHandlerSkill, "_wait_receipt")
@patch.object(EvmTxHandlerSkill, "_sign_and_send")
@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_transfer_resolves_addressbook(mock_web3, mock_send, mock_receipt, skill):
    w3 = MagicMock()
    w3.eth.gas_price = 10**9
    w3.eth.get_transaction_count.return_value = 0
    w3.to_wei.side_effect = lambda val, unit: int(val * 10**9) if unit == "gwei" else val
    mock_web3.return_value = w3
    mock_send.return_value = "0xabc"
    mock_receipt.return_value = {"block_number": 1, "gas_used": 21000, "success": True}

    contract = MagicMock()
    contract.functions.transfer.return_value.build_transaction.return_value = {
        "to": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "gas": 100000,
    }
    w3.eth.contract.return_value = contract

    result = skill.execute(
        {
            "action": "transfer",
            "confirmed": True,
            "intent": {
                "chain": "base",
                "target_asset": "usdc",
                "amount": 10,
                "recipient": "mom",
            },
        }
    )
    assert result["status"] == "confirmed"
    assert result["recipient_resolved"] == "0x000000000000000000000000000000000000dEaD"
    mock_send.assert_called_once()


def test_gas_override_does_not_mutate_config(skill, tmp_path):
    config_path = os.path.join(skill._skill_dir, "config.yaml")
    original_gas = skill.user_config.get("gas_policy")
    skill.execute(
        {
            "action": "resolve",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 1,
                "gas_policy": "aggressive",
            },
        }
    )
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            on_disk = yaml.safe_load(f)
        assert on_disk.get("gas_policy") == original_gas
    assert skill.user_config.get("gas_policy") == original_gas


def test_update_preferences(skill, tmp_path):
    config_path = os.path.join(skill._skill_dir, "config.yaml")
    try:
        result = skill.execute(
            {
                "action": "update_preferences",
                "preferences": {"default_chain": "base", "slippage_bps": 75},
            }
        )
        assert result["status"] == "updated"
        assert result["preferences"]["default_chain"] == "base"
        assert result["preferences"]["slippage_bps"] == 75
        with open(config_path, "r", encoding="utf-8") as f:
            saved = yaml.safe_load(f)
        assert saved["default_chain"] == "base"
    finally:
        if os.path.exists(config_path):
            os.remove(config_path)
        skill.user_config = skill._load_user_config()


def test_wallet_info_no_secrets(skill):
    result = skill.execute({"action": "wallet_info", "intent": {}})
    assert result["status"] == "ready"
    assert "address" in result
    body = str(result)
    assert TEST_KEY not in body
    assert TEST_KEY[2:] not in body


@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_balances(mock_web3, skill):
    w3 = MagicMock()
    w3.eth.get_balance.return_value = 10**18
    mock_web3.return_value = w3
    erc20 = MagicMock()
    erc20.functions.balanceOf.return_value.call.return_value = 5_000_000
    w3.eth.contract.return_value = erc20

    result = skill.execute({"action": "balances", "intent": {"chain": "ethereum"}})
    assert result["status"] == "ready"
    assert "eth" in result["balances"]
