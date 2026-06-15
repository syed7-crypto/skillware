import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

from .skill import WalletScreeningSkill


@pytest.fixture
def skill():
    return WalletScreeningSkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]


def test_invalid_address(skill):
    result = skill.execute({"address": "invalid_addr"})
    assert "error" in result
    assert "Invalid Ethereum address" in result["error"]


def test_missing_api_key(skill):
    skill.etherscan_api_key = None
    result = skill.execute({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})
    assert "error" in result
    assert "Missing ETHERSCAN_API_KEY" in result["error"]


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_execute_success(mock_get, skill):
    skill.etherscan_api_key = "dummy_key"

    mock_eth_balance = MagicMock()
    mock_eth_balance.json.return_value = {
        "status": "1",
        "result": "1000000000000000000",
    }

    mock_txs = MagicMock()
    mock_txs.json.return_value = {
        "status": "1",
        "result": [
            {
                "from": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045".lower(),
                "to": "0x123",
                "value": "500000000000000000",
                "isError": "0",
                "gasUsed": "21000",
                "gasPrice": "1000000000",
            }
        ],
    }

    mock_price = MagicMock()
    mock_price.json.return_value = {"ethereum": {"usd": 2000.0, "eur": 1800.0}}

    def get_side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if params.get("action") == "balance":
            return mock_eth_balance
        if params.get("action") == "txlist":
            return mock_txs
        return mock_price

    mock_get.side_effect = get_side_effect

    result = skill.execute({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})

    assert "error" not in result
    assert "summary" in result
    assert result["summary"]["balance_eth"] == 1.0
    assert result["summary"]["balance_usd"] == 2000.0
