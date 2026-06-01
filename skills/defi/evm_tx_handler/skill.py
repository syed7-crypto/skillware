"""
EVM transaction handler — PR1: resolve, quote, preview, transfer, balances,
wallet_info, update_preferences. Swap execute() ships in PR2.
"""

from __future__ import annotations

import copy
import os
import re
import sys
import time
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Optional, Tuple

import yaml
from eth_account import Account
from web3 import Web3
from web3.contract import Contract

from skillware.core.base_skill import BaseSkill

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)
from abis import ERC20_ABI, ROUTER_V2_ABI  # noqa: E402

_ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_SENSITIVE_ENV_SUFFIXES = ("PRIVATE_KEY", "SECRET", "MNEMONIC")
_PREFERENCE_KEYS = frozenset(
    {
        "default_chain",
        "default_spend_asset",
        "gas_policy",
        "confirm_before_send",
        "slippage_bps",
        "max_trade_usd",
        "allowed_chains",
        "allowed_tokens",
        "private_key_env",
    }
)
_GAS_MULTIPLIERS = {
    "low": (0.95, 1.0),
    "normal": (1.1, 1.5),
    "high": (1.25, 2.5),
    "aggressive": (1.5, 3.0),
}


class EvmTxHandlerSkill(BaseSkill):
    """Structured EVM buy/sell quotes and transfers for a dedicated agent wallet."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self._skill_dir = os.path.dirname(os.path.abspath(__file__))
        self._data_dir = os.path.join(self._skill_dir, "data")
        self.chains = self._load_yaml("chains.yaml")
        self.tokens = self._load_yaml("tokens.yaml")
        self.addressbook = self._load_yaml("addressbook.yaml")
        self.user_config = self._load_user_config()
        self._web3_cache: Dict[str, Web3] = {}

    @property
    def manifest(self) -> Dict[str, Any]:
        path = os.path.join(self._skill_dir, "manifest.yaml")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = (params.get("action") or "").strip().lower()
        intent = params.get("intent") or {}
        if not isinstance(intent, dict):
            return self._error("intent must be an object")

        handlers = {
            "resolve": self._action_resolve,
            "quote": self._action_quote,
            "preview": self._action_preview,
            "execute": self._action_execute,
            "transfer": self._action_transfer,
            "balances": self._action_balances,
            "wallet_info": self._action_wallet_info,
            "update_preferences": self._action_update_preferences,
        }
        if action not in handlers:
            return self._error(
                f"Unknown action {action!r}. "
                f"Use one of: {', '.join(sorted(handlers))}."
            )

        try:
            return handlers[action](intent, params)
        except ValueError as exc:
            return self._error(str(exc))
        except Exception as exc:
            return self._error(self._safe_error_message(exc))

    # --- Config & registry ---

    def _load_yaml(self, name: str) -> Dict[str, Any]:
        path = os.path.join(self._data_dir, name)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}

    def _load_user_config(self) -> Dict[str, Any]:
        defaults = {
            "default_chain": "ethereum",
            "default_spend_asset": "usdc",
            "gas_policy": "normal",
            "confirm_before_send": True,
            "slippage_bps": 50,
            "private_key_env": "AGENT_WALLET_PRIVATE_KEY",
        }
        path = os.path.join(self._skill_dir, "config.yaml")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict):
                defaults.update(loaded)
        return defaults

    def _save_user_config(self, updates: Dict[str, Any]) -> None:
        merged = copy.deepcopy(self.user_config)
        merged.update(updates)
        path = os.path.join(self._skill_dir, "config.yaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(merged, f, default_flow_style=False, sort_keys=False)
        self.user_config = merged

    def _chain_key(self, chain: Optional[str]) -> str:
        key = (chain or self.user_config.get("default_chain") or "ethereum").strip().lower()
        if key not in self.chains:
            raise ValueError(f"Unknown chain {key!r}. Supported: {', '.join(self.chains)}.")
        allowed = self.user_config.get("allowed_chains")
        if allowed and key not in [c.lower() for c in allowed]:
            raise ValueError(f"Chain {key!r} is not in allowed_chains.")
        return key

    def _token_allowed(self, symbol: str) -> None:
        allowed = self.user_config.get("allowed_tokens")
        if allowed and symbol.lower() not in [t.lower() for t in allowed]:
            raise ValueError(f"Token {symbol!r} is not in allowed_tokens.")

    def _resolve_token_meta(self, chain: str, symbol: str) -> Dict[str, Any]:
        sym = symbol.strip().lower()
        self._token_allowed(sym)
        chain_tokens = self.tokens.get(chain) or {}
        if sym not in chain_tokens:
            raise ValueError(f"Token {sym!r} not in tokens.yaml for chain {chain!r}.")
        meta = dict(chain_tokens[sym])
        meta["symbol"] = sym
        meta["chain"] = chain
        if meta.get("native"):
            meta["address"] = None
        elif meta.get("address"):
            meta["address"] = Web3.to_checksum_address(meta["address"])
        return meta

    def _resolve_recipient(self, recipient: str) -> str:
        raw = recipient.strip()
        if _ETH_ADDRESS_RE.match(raw):
            return Web3.to_checksum_address(raw)
        label = raw.lower()
        if label in self.addressbook:
            return Web3.to_checksum_address(str(self.addressbook[label]))
        raise ValueError(
            f"Recipient {recipient!r} is not a valid address or addressbook label."
        )

    def _rpc_url(self, chain: str) -> str:
        chain_cfg = self.chains[chain]
        env_key = chain_cfg.get("rpc_env")
        if not env_key:
            raise ValueError(f"chains.yaml missing rpc_env for {chain!r}.")
        url = os.environ.get(env_key) or (self.config or {}).get(env_key)
        if not url:
            raise ValueError(f"Missing RPC: set environment variable {env_key}.")
        return url

    def _get_web3(self, chain: str) -> Web3:
        if chain not in self._web3_cache:
            self._web3_cache[chain] = Web3(Web3.HTTPProvider(self._rpc_url(chain)))
        return self._web3_cache[chain]

    def _private_key_env(self) -> str:
        return str(self.user_config.get("private_key_env") or "AGENT_WALLET_PRIVATE_KEY")

    def _account(self):
        env_name = self._private_key_env()
        key = os.environ.get(env_name) or (self.config or {}).get(env_name)
        if not key:
            raise ValueError(
                f"Missing dedicated agent wallet key: set {env_name} in .env "
                "(never pass private keys in tool arguments)."
            )
        if key.startswith("0x"):
            key = key[2:]
        return Account.from_key(key)

    def _wallet_address(self) -> str:
        return self._account().address

    # --- Intent merge / resolve ---

    def _merge_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        chain = self._chain_key(intent.get("chain"))
        merged["chain"] = chain
        merged["gas_policy"] = (
            intent.get("gas_policy") or self.user_config.get("gas_policy") or "normal"
        ).lower()
        if merged["gas_policy"] not in _GAS_MULTIPLIERS:
            raise ValueError(f"Invalid gas_policy {merged['gas_policy']!r}.")

        side = (intent.get("side") or "").strip().lower()
        if side:
            merged["side"] = side

        for key in (
            "target_asset",
            "spend_asset",
            "amount",
            "amount_kind",
            "recipient",
            "slippage_bps",
        ):
            if intent.get(key) is not None:
                merged[key] = intent[key]

        if intent.get("slippage_bps") is None and self.user_config.get("slippage_bps") is not None:
            merged.setdefault("slippage_bps", self.user_config["slippage_bps"])

        if side in ("buy", "sell"):
            if not merged.get("target_asset"):
                raise ValueError("target_asset is required for buy/sell.")
            merged["target_asset"] = str(merged["target_asset"]).lower()
            if merged.get("spend_asset"):
                merged["spend_asset"] = str(merged["spend_asset"]).lower()
            if not merged.get("amount_kind"):
                merged["amount_kind"] = "target_out" if side == "buy" else "spend_in"
        elif merged.get("target_asset"):
            merged["target_asset"] = str(merged["target_asset"]).lower()
        if merged.get("recipient"):
            merged["recipient"] = str(merged["recipient"]).strip()

        return merged

    def _missing_for_trade(self, resolved: Dict[str, Any]) -> List[str]:
        missing = []
        if not resolved.get("spend_asset"):
            missing.append("spend_asset")
        if resolved.get("amount") is None:
            missing.append("amount")
        return missing

    def _suggested_defaults(self, resolved: Dict[str, Any], missing: List[str]) -> Dict[str, Any]:
        suggestions: Dict[str, Any] = {}
        if "spend_asset" in missing:
            side = resolved.get("side")
            if side == "buy":
                suggestions["spend_asset"] = self.user_config.get("default_spend_asset", "usdc")
            elif side == "sell":
                suggestions["spend_asset"] = self.user_config.get("default_spend_asset", "usdc")
        return suggestions

    def _action_resolve(self, intent: Dict[str, Any], _params: Dict[str, Any]) -> Dict[str, Any]:
        resolved = self._merge_intent(intent)
        side = resolved.get("side")

        if side in ("buy", "sell"):
            missing = self._missing_for_trade(resolved)
            if missing:
                return {
                    "status": "needs_input",
                    "resolved": resolved,
                    "missing_fields": missing,
                    "suggested_defaults": self._suggested_defaults(resolved, missing),
                    "agent_hint": (
                        f"Ask which token to pay with; suggest "
                        f"{self._suggested_defaults(resolved, missing).get('spend_asset', 'usdc').upper()} "
                        f"from config."
                        if "spend_asset" in missing
                        else "Ask for the trade amount."
                    ),
                }
            self._resolve_token_meta(resolved["chain"], resolved["target_asset"])
            self._resolve_token_meta(resolved["chain"], resolved["spend_asset"])
            return {"status": "ready", "resolved": resolved}

        if side == "send" or intent.get("recipient") or _params.get("action") == "transfer":
            missing = []
            if not resolved.get("target_asset"):
                missing.append("target_asset")
            if resolved.get("amount") is None:
                missing.append("amount")
            if not resolved.get("recipient") and not intent.get("recipient"):
                missing.append("recipient")
            if missing:
                return {
                    "status": "needs_input",
                    "resolved": resolved,
                    "missing_fields": missing,
                    "suggested_defaults": {},
                    "agent_hint": "Ask for token, amount, and recipient (address or addressbook label).",
                }
            return {"status": "ready", "resolved": resolved}

        return self._error("intent.side must be buy, sell, or use transfer action for sends.")

    # --- Quote / preview ---

    def _swap_path(
        self, chain: str, token_in: Dict[str, Any], token_out: Dict[str, Any]
    ) -> List[str]:
        weth = Web3.to_checksum_address(self.chains[chain]["weth"])

        def addr(meta: Dict[str, Any]) -> str:
            if meta.get("native"):
                return weth
            return meta["address"]

        a_in, a_out = addr(token_in), addr(token_out)
        if a_in == a_out:
            raise ValueError("Cannot swap an asset into itself.")
        if a_in == weth or a_out == weth:
            return [a_in, a_out]
        return [a_in, weth, a_out]

    def _to_wei(self, amount: float, decimals: int) -> int:
        quant = Decimal(str(amount)).quantize(
            Decimal(10) ** -decimals, rounding=ROUND_DOWN
        )
        return int(quant * (10**decimals))

    def _from_wei(self, wei: int, decimals: int) -> str:
        value = Decimal(wei) / Decimal(10**decimals)
        return format(value.normalize(), "f")

    def _router(self, w3: Web3, chain: str) -> Contract:
        router_addr = Web3.to_checksum_address(self.chains[chain]["router_v2"])
        return w3.eth.contract(address=router_addr, abi=ROUTER_V2_ABI)

    def _trade_assets(self, resolved: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        chain = resolved["chain"]
        side = resolved["side"]
        target = self._resolve_token_meta(chain, resolved["target_asset"])
        spend = self._resolve_token_meta(chain, resolved["spend_asset"])
        if side == "buy":
            return spend, target
        return target, spend

    def _build_quote(self, resolved: Dict[str, Any]) -> Dict[str, Any]:
        chain = resolved["chain"]
        w3 = self._get_web3(chain)
        token_in, token_out = self._trade_assets(resolved)
        path = self._swap_path(chain, token_in, token_out)
        router = self._router(w3, chain)
        amount_kind = (resolved.get("amount_kind") or "target_out").lower()
        amount = float(resolved["amount"])
        slippage_bps = int(resolved.get("slippage_bps") or self.user_config.get("slippage_bps") or 50)

        if amount_kind == "target_out":
            amount_out_wei = self._to_wei(amount, token_out["decimals"])
            amounts = router.functions.getAmountsIn(amount_out_wei, path).call()
            amount_in_wei = amounts[0]
            amount_out_wei = amounts[-1]
        elif amount_kind == "spend_in":
            amount_in_wei = self._to_wei(amount, token_in["decimals"])
            amounts = router.functions.getAmountsOut(amount_in_wei, path).call()
            amount_out_wei = amounts[-1]
        else:
            raise ValueError("amount_kind must be target_out or spend_in.")

        min_out_wei = amount_out_wei * (10_000 - slippage_bps) // 10_000
        deadline = int(time.time()) + 1200
        gas = self._estimate_gas(w3, resolved.get("gas_policy", "normal"))

        return {
            "path": path,
            "token_in": token_in,
            "token_out": token_out,
            "amount_in_wei": str(amount_in_wei),
            "amount_out_wei": str(amount_out_wei),
            "min_out_wei": str(min_out_wei),
            "deadline": deadline,
            "slippage_bps": slippage_bps,
            "gas_estimate": gas,
            "side": resolved["side"],
            "chain": chain,
        }

    def _preview_from_quote(self, quote: Dict[str, Any]) -> Dict[str, Any]:
        tin, tout = quote["token_in"], quote["token_out"]
        pay_amt = self._from_wei(int(quote["amount_in_wei"]), tin["decimals"])
        recv_amt = self._from_wei(int(quote["amount_out_wei"]), tout["decimals"])
        rate = ""
        if Decimal(pay_amt) > 0:
            rate = (
                f"1 {tin['symbol']} = "
                f"{format(Decimal(recv_amt) / Decimal(pay_amt), 'f')} {tout['symbol']}"
            )

        return {
            "side": quote["side"],
            "chain": quote["chain"],
            "you_pay": {"asset": tin["symbol"], "amount": pay_amt},
            "you_receive": {"asset": tout["symbol"], "amount": recv_amt},
            "rate": rate,
            "gas_estimate": quote["gas_estimate"],
            "router": "uniswap_v2",
            "warnings": [
                "Rates are indicative; slippage may apply.",
                "Swap execution is not enabled in PR1.",
            ],
        }

    def _action_quote(self, intent: Dict[str, Any], _params: Dict[str, Any]) -> Dict[str, Any]:
        resolved = self._merge_intent(intent)
        if resolved.get("side") not in ("buy", "sell"):
            return self._error("quote requires intent.side buy or sell.")
        missing = self._missing_for_trade(resolved)
        if missing:
            return self._error(f"Cannot quote; missing fields: {', '.join(missing)}.")

        quote = self._build_quote(resolved)
        preview = self._preview_from_quote(quote)
        confirm = bool(self.user_config.get("confirm_before_send", True))
        return {
            "status": "ready",
            "preview": preview,
            "quote": {
                "path": quote["path"],
                "amount_in_wei": quote["amount_in_wei"],
                "amount_out_wei": quote["amount_out_wei"],
                "min_out_wei": quote["min_out_wei"],
                "deadline": quote["deadline"],
            },
            "requires_confirmation": confirm,
        }

    def _action_preview(self, intent: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        result = self._action_quote(intent, params)
        if result.get("status") != "ready":
            return result
        return {
            "status": "ready",
            "preview": result["preview"],
            "requires_confirmation": result.get("requires_confirmation", True),
        }

    def _action_execute(self, _intent: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        need_confirm = self._require_confirmed(params)
        if need_confirm:
            return need_confirm
        return {
            "status": "not_available",
            "code": "pr2_execute",
            "message": (
                "Swap execution (execute) ships in PR2. Use quote/preview to plan trades; "
                "use transfer for sends in PR1."
            ),
        }

    # --- Transfer ---

    def _require_confirmed(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.user_config.get("confirm_before_send", True) and not params.get("confirmed"):
            return {
                "status": "needs_confirmation",
                "message": "Set confirmed: true after the user approves this transaction.",
            }
        return None

    def _estimate_gas(self, w3: Web3, policy: str) -> Dict[str, Any]:
        policy = policy if policy in _GAS_MULTIPLIERS else "normal"
        base_fee = w3.eth.gas_price
        max_mult, tip_gwei = _GAS_MULTIPLIERS[policy]
        max_fee = int(base_fee * max_mult)
        priority = w3.to_wei(tip_gwei, "gwei")
        return {
            "policy": policy,
            "max_fee_gwei": str(Decimal(max_fee) / Decimal(10**9)),
            "max_priority_fee_gwei": str(Decimal(priority) / Decimal(10**9)),
        }

    def _eip1559_fees(self, w3: Web3, policy: str) -> Tuple[int, int]:
        policy = policy if policy in _GAS_MULTIPLIERS else "normal"
        base_fee = w3.eth.gas_price
        max_mult, tip_gwei = _GAS_MULTIPLIERS[policy]
        return int(base_fee * max_mult), w3.to_wei(tip_gwei, "gwei")

    def _sign_and_send(self, w3: Web3, tx: Dict[str, Any]) -> str:
        signed = self._account().sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        return tx_hash.hex()

    def _wait_receipt(self, w3: Web3, tx_hash: str, timeout: int = 120) -> Dict[str, Any]:
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            return {
                "block_number": receipt["blockNumber"],
                "gas_used": receipt["gasUsed"],
                "success": receipt["status"] == 1,
            }
        except Exception:
            return {"success": None, "note": "Receipt not confirmed within timeout."}

    def _explorer_url(self, chain: str, tx_hash: str) -> str:
        template = self.chains[chain].get("explorer_tx_url", "")
        return template.format(tx_hash=tx_hash)

    def _action_transfer(self, intent: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        need_confirm = self._require_confirmed(params)
        if need_confirm:
            return need_confirm

        resolved = self._merge_intent({**intent, "side": "send"})
        chain = resolved["chain"]
        if not resolved.get("target_asset"):
            return self._error("target_asset is required for transfer.")
        if resolved.get("amount") is None:
            return self._error("amount is required for transfer.")
        if not resolved.get("recipient"):
            return self._error("recipient is required for transfer.")

        recipient = self._resolve_recipient(str(resolved["recipient"]))
        token = self._resolve_token_meta(chain, str(resolved["target_asset"]))
        w3 = self._get_web3(chain)
        amount_wei = self._to_wei(float(resolved["amount"]), token["decimals"])
        policy = resolved.get("gas_policy", "normal")

        account = self._account()
        chain_id = int(self.chains[chain]["chain_id"])
        max_fee, priority = self._eip1559_fees(w3, policy)
        base_tx: Dict[str, Any] = {
            "from": account.address,
            "chainId": chain_id,
            "nonce": w3.eth.get_transaction_count(account.address),
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority,
        }

        if token.get("native"):
            tx = {
                **base_tx,
                "to": recipient,
                "value": amount_wei,
                "gas": 21_000,
            }
        else:
            contract = w3.eth.contract(address=token["address"], abi=ERC20_ABI)
            tx = contract.functions.transfer(recipient, amount_wei).build_transaction(base_tx)

        tx_hash = self._sign_and_send(w3, tx)
        receipt = self._wait_receipt(w3, tx_hash)
        return {
            "status": "confirmed",
            "tx_hash": tx_hash,
            "explorer_url": self._explorer_url(chain, tx_hash),
            "recipient_resolved": recipient,
            "receipt": receipt,
        }

    # --- Read-only ---

    def _action_balances(self, intent: Dict[str, Any], _params: Dict[str, Any]) -> Dict[str, Any]:
        chain = self._chain_key(intent.get("chain"))
        w3 = self._get_web3(chain)
        address = self._wallet_address()
        chain_tokens = self.tokens.get(chain) or {}
        balances: Dict[str, str] = {}

        native_bal = w3.eth.get_balance(address)
        balances["eth"] = self._from_wei(native_bal, 18)

        for symbol, meta in chain_tokens.items():
            if meta.get("native"):
                continue
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(meta["address"]), abi=ERC20_ABI
            )
            raw = contract.functions.balanceOf(address).call()
            balances[symbol] = self._from_wei(raw, int(meta["decimals"]))

        return {"status": "ready", "chain": chain, "address": address, "balances": balances}

    def _action_wallet_info(self, _intent: Dict[str, Any], _params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            address = self._wallet_address()
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

        prefs = {
            k: self.user_config[k]
            for k in (
                "default_chain",
                "default_spend_asset",
                "gas_policy",
                "confirm_before_send",
                "slippage_bps",
                "max_trade_usd",
            )
            if k in self.user_config
        }
        return {
            "status": "ready",
            "address": address,
            "supported_chains": list(self.chains.keys()),
            "preferences": prefs,
            "capabilities": {
                "resolve": True,
                "quote": True,
                "preview": True,
                "transfer": True,
                "balances": True,
                "execute": False,
            },
        }

    def _action_update_preferences(
        self, intent: Dict[str, Any], params: Dict[str, Any]
    ) -> Dict[str, Any]:
        updates = params.get("preferences") or intent.get("preferences") or {}
        if not isinstance(updates, dict) or not updates:
            return self._error("preferences object with fields to update is required.")

        invalid = [k for k in updates if k not in _PREFERENCE_KEYS]
        if invalid:
            return self._error(f"Cannot update unknown preference keys: {', '.join(invalid)}.")

        if "gas_policy" in updates and updates["gas_policy"] not in _GAS_MULTIPLIERS:
            return self._error("Invalid gas_policy in preferences.")

        self._save_user_config(updates)
        return {"status": "updated", "preferences": copy.deepcopy(self.user_config)}

    # --- Helpers ---

    @staticmethod
    def _error(message: str) -> Dict[str, Any]:
        return {"status": "error", "message": message}

    def _safe_error_message(self, exc: Exception) -> str:
        text = str(exc)
        for key, value in os.environ.items():
            if not value or len(value) < 8:
                continue
            if any(s in key.upper() for s in _SENSITIVE_ENV_SUFFIXES):
                text = text.replace(value, "[REDACTED]")
                if value.startswith("0x"):
                    text = text.replace(value[2:], "[REDACTED]")
        cfg_key = (self.config or {}).get(self._private_key_env())
        if cfg_key and len(str(cfg_key)) >= 8:
            text = text.replace(str(cfg_key), "[REDACTED]")
        if len(text) > 500:
            text = text[:500] + "..."
        return text
