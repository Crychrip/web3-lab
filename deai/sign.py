from __future__ import annotations

import hashlib
import json

from eth_account import Account
from eth_account.messages import encode_defunct

# Hardhat 本地节点的默认账户，只用于本地签名测试。
DEMO_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def sign_json(payload: dict, key: str = DEMO_KEY) -> dict:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(body.encode()).hexdigest()
    account = Account.from_key(key)
    signed = Account.sign_message(encode_defunct(text=digest), private_key=key)
    return {
        "payload": payload,
        "sha256": digest,
        "signer": account.address,
        "signature": signed.signature.hex(),
    }
