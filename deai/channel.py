from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


def _digest(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


@dataclass
class Micropayment:
    request_id: str
    nonce: int
    amount: int
    total: int
    prev_hash: str
    commitment: str
    signer: str


@dataclass
class DisputeVerdict:
    winner: str
    payable: int
    reason: str
    used_receipts: list[str]


@dataclass
class PaymentChannel:
    consumer: str
    supplier: str
    escrow: int
    payments: list[Micropayment] = field(default_factory=list)

    def pay(self, request_id: str, amount: int, signer: str) -> Micropayment:
        prev = self.payments[-1].commitment if self.payments else "0" * 64
        nonce = len(self.payments) + 1
        total = (self.payments[-1].total if self.payments else 0) + amount
        body = {
            "request_id": request_id,
            "nonce": nonce,
            "amount": amount,
            "total": total,
            "prev_hash": prev,
            "signer": signer,
        }
        pay = Micropayment(
            request_id=request_id,
            nonce=nonce,
            amount=amount,
            total=total,
            prev_hash=prev,
            commitment=_digest(body),
            signer=signer,
        )
        self.payments.append(pay)
        return pay

    def dispute(self, request_id: str, server_claims_unpaid: bool) -> DisputeVerdict:
        by_id = {p.request_id: p for p in self.payments}
        if request_id not in by_id:
            return DisputeVerdict("consumer", 0, "no micropayment for this requestID", [])
        current = by_id[request_id]
        prev = None
        if current.nonce > 1:
            prev = self.payments[current.nonce - 2]
            if prev.commitment != current.prev_hash:
                return DisputeVerdict(
                    "consumer",
                    0,
                    "broken hash chain",
                    [current.commitment],
                )
        if server_claims_unpaid:
            return DisputeVerdict(
                "supplier",
                current.amount,
                "payer must post this receipt and the previous commitment",
                [current.commitment] + ([prev.commitment] if prev else []),
            )
        return DisputeVerdict("consumer", 0, "receipt already settles the unit", [current.commitment])
