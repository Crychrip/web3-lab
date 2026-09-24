from __future__ import annotations

import json
from pathlib import Path

from web3 import Web3

ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT = ROOT / "chain" / "deployments" / "localhost.json"


class ChainClient:
    def __init__(self, rpc: str = "http://127.0.0.1:8545", key: str | None = None) -> None:
        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
        if not self.w3.is_connected():
            raise ConnectionError(f"cannot connect to {rpc}; start: npm --prefix chain run node")
        payload = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
        self.address = Web3.to_checksum_address(payload["address"])
        self.abi = payload["abi"]
        self.contract = self.w3.eth.contract(address=self.address, abi=self.abi)
        self.accounts = self.w3.eth.accounts
        self.coordinator = self.accounts[0]
        self.default_from = key or self.coordinator

    def _send(self, fn, sender: str):
        tx = fn.build_transaction(
            {
                "from": sender,
                "nonce": self.w3.eth.get_transaction_count(sender),
                "gas": 500_000,
                "gasPrice": self.w3.eth.gas_price,
            }
        )
        tx_hash = self.w3.eth.send_transaction(tx)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            raise RuntimeError(f"tx failed: {tx_hash.hex()}")
        return receipt

    def faucet(self, account: str, amount: int) -> None:
        self._send(self.contract.functions.faucet(amount), account)

    def lock(self, account: str, amount: int, native: bool = True) -> None:
        self._send(self.contract.functions.lock(amount, native), account)

    def unlock(self, account: str) -> None:
        self._send(self.contract.functions.unlock(), account)

    def weight_of(self, account: str) -> int:
        return int(self.contract.functions.weightOf(account).call())

    def valid_pass(self, account: str) -> bool:
        return bool(self.contract.functions.validPass(account).call())

    def credit_reward(self, miner: str, amount: int) -> None:
        self._send(self.contract.functions.creditReward(miner, amount), self.coordinator)

    def miner_rewards(self, miner: str) -> int:
        return int(self.contract.functions.minerRewards(miner).call())

    def total_locked(self) -> int:
        return int(self.contract.functions.totalLocked().call())

    def locked_event_weights(self) -> list[tuple[str, int]]:
        logs = self.contract.events.Locked.get_logs(from_block=0)
        return [(ev.args.client, int(ev.args.effectiveStake)) for ev in logs]

    def reward_events(self) -> list[tuple[str, int]]:
        logs = self.contract.events.RewardCredited.get_logs(from_block=0)
        return [(ev.args.miner, int(ev.args.amount)) for ev in logs]
