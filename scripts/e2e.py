from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from deai.chain_client import ChainClient
from deai.engine import ProtocolEngine
from deai.types import Rating
from deai.wrr import stake_weights

ROOT = Path(__file__).resolve().parents[1]
GO = Path(os.environ.get("GOROOT", r"D:\dev\go")) / "bin" / "go.exe"
NODE = Path(os.environ.get("NODE_HOME", r"D:\dev\nodejs"))
COORD = ROOT / "coord"
CHAIN = ROOT / "chain"
FIG = ROOT / "figures"
TAB = ROOT / "tables"
BIN = COORD / "deai-coord.exe"


class CoordBridge:
    def __init__(self, n: int, loss: float) -> None:
        env = os.environ.copy()
        env["GOROOT"] = str(Path(r"D:\dev\go"))
        env["GOPATH"] = str(Path(r"D:\dev\gopath"))
        env["GOPROXY"] = "https://goproxy.cn,direct"
        path = str(NODE) + os.pathsep + str(Path(r"D:\dev\go\bin")) + os.pathsep + env.get("Path", "")
        env["Path"] = path
        self.proc = subprocess.Popen(
            [str(BIN), "-stdio"],
            cwd=str(COORD),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=1,
        )
        self._send({"cmd": "start", "n": n, "loss": loss, "byzantine": 0})

    def _send(self, payload: dict) -> dict:
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"coord exited: {err}")
        return json.loads(line)

    def cycle(self, order, rating: int) -> None:
        self._send(
            {
                "cmd": "cycle",
                "orderId": order.order_id,
                "clientId": order.client_id,
                "minerId": order.miner_id,
                "service": order.service,
                "allocation": "avrf",
                "confirm": True,
                "rating": rating,
            }
        )

    def flush(self, timeout_ms: int = 60000) -> dict:
        return self._send({"cmd": "flush", "timeoutMs": timeout_ms})

    def close(self) -> None:
        try:
            self._send({"cmd": "quit"})
        except Exception:
            pass
        self.proc.terminate()


import threading


def _drain(proc: subprocess.Popen) -> None:
    if not proc.stdout:
        return
    for _ in proc.stdout:
        pass


def start_hardhat() -> subprocess.Popen:
    env = os.environ.copy()
    env["Path"] = str(NODE) + os.pathsep + str(Path(r"D:\dev\git\cmd")) + os.pathsep + env.get("Path", "")
    proc = subprocess.Popen(
        [str(NODE / "npx.cmd"), "hardhat", "node", "--hostname", "127.0.0.1", "--port", "8545"],
        cwd=str(CHAIN),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.stdout
    ready = False
    for _ in range(120):
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            raise RuntimeError("hardhat node failed to start")
        if line and "Started HTTP" in line:
            ready = True
            break
    if not ready:
        proc.kill()
        raise TimeoutError("hardhat node did not start")
    threading.Thread(target=_drain, args=(proc,), daemon=True).start()
    return proc


def deploy() -> None:
    env = os.environ.copy()
    env["Path"] = str(NODE) + os.pathsep + str(Path(r"D:\dev\git\cmd")) + os.pathsep + env.get("Path", "")
    subprocess.check_call(
        [str(NODE / "npx.cmd"), "hardhat", "run", "scripts/deploy.js", "--network", "localhost"],
        cwd=str(CHAIN),
        env=env,
    )


def build_coord() -> None:
    env = os.environ.copy()
    env["GOROOT"] = r"D:\dev\go"
    env["GOPATH"] = r"D:\dev\gopath"
    env["GOPROXY"] = "https://goproxy.cn,direct"
    env["Path"] = r"D:\dev\go\bin;" + env.get("Path", "")
    subprocess.check_call([str(GO), "build", "-o", str(BIN), "."], cwd=str(COORD), env=env)


def choose_clients(i: int) -> str:
    # 1:3:6 WRR-like mix
    cycle = i % 10
    if cycle == 0:
        return "C1"
    if cycle <= 3:
        return "C2"
    return "C3"


def run() -> dict:
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    build_coord()
    hh = start_hardhat()
    try:
        deploy()
        chain = ChainClient()
        c1, c2, c3 = chain.accounts[1], chain.accounts[2], chain.accounts[3]
        m1, m2, m3 = chain.accounts[4], chain.accounts[5], chain.accounts[6]
        miner_addr = {"M1": m1, "M2": m2, "M3": m3}

        for acct, amount in ((c1, 100), (c2, 300), (c3, 600)):
            chain.faucet(acct, amount)
            chain.lock(acct, amount, native=True)

        onchain = {"C1": chain.weight_of(c1), "C2": chain.weight_of(c2), "C3": chain.weight_of(c3)}
        weights = stake_weights({k: float(v) for k, v in onchain.items()})

        eng = ProtocolEngine(seed=b"e2e-step4", epoch_reward=100.0)
        for cid, amount in (("C1", 100), ("C2", 300), ("C3", 600)):
            eng.add_client(cid, balance=0)
            eng.clients[cid].stake_native = float(amount)
            eng.clients[cid].locked = True
            eng.clients[cid].has_pass = True
        eng.add_client("Sybil", balance=0)
        eng.add_client("Attacker", balance=200)
        eng.lock_tokens("Attacker", 200)
        for mid, rep in (("M1", 20.0), ("M2", 50.0), ("M3", 80.0)):
            eng.add_miner(mid, reputation=rep)

        rejected = 0
        designate = 0
        malicious_blocked = 0
        accepted = []

        # seed honest majority on M-selected miners
        for cid in ("C1", "C2"):
            order = eng.put(cid)
            eng.force_rate(order.order_id, Rating.GOOD)
            accepted.append(order)

        for i in range(1000):
            if i < 50:
                order = eng.put("Sybil")
                rejected += 1
                continue
            if 50 <= i < 80:
                order = eng.put(choose_clients(i), requested_miner="M1")
                designate += 1
                if order.accepted:
                    eng.force_rate(order.order_id, Rating.GOOD)
                    accepted.append(order)
                continue
            if 80 <= i < 110:
                order = eng.put("Attacker")
                if order.accepted:
                    if not eng.rate(order.order_id, Rating.BAD):
                        malicious_blocked += 1
                    else:
                        accepted.append(order)
                continue
            order = eng.put(choose_clients(i))
            if order.accepted:
                eng.force_rate(order.order_id, Rating.GOOD)
                accepted.append(order)

        pbft0 = CoordBridge(50, 0.0)
        try:
            for order in accepted:
                rating = int(order.rating) if order.rating is not None else 1
                pbft0.cycle(order, rating)
            flush0 = pbft0.flush(90000)
        finally:
            pbft0.close()

        sample = accepted[:200]
        pbft5 = CoordBridge(50, 0.05)
        try:
            for order in sample:
                rating = int(order.rating) if order.rating is not None else 1
                pbft5.cycle(order, rating)
            flush5 = pbft5.flush(90000)
        finally:
            pbft5.close()

        rewards = eng.settle_epoch(100.0)
        onchain_rewards = {}
        for mid, amount in rewards.items():
            val = int(round(amount))
            if val > 0:
                chain.credit_reward(miner_addr[mid], val)
            onchain_rewards[mid] = chain.miner_rewards(miner_addr[mid])

        summary = {
            "onchain_weights": onchain,
            "wrr_weights": weights,
            "requests": 1000,
            "sybil_rejected": rejected,
            "designate_attempts": designate,
            "malicious_blocked": malicious_blocked,
            "accepted": len(accepted),
            "pbft0": flush0,
            "pbft5": flush5,
            "engine_rewards": rewards,
            "onchain_rewards": onchain_rewards,
            "total_locked": chain.total_locked(),
            "lock_events": len(chain.locked_event_weights()),
            "reward_events": len(chain.reward_events()),
        }
        (TAB / "e2e_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        lines = [
            "metric,value",
            f"sybil_rejected,{rejected}",
            f"designate_attempts,{designate}",
            f"malicious_blocked,{malicious_blocked}",
            f"accepted,{len(accepted)}",
            f"pbft0_committed,{flush0.get('committed')}",
            f"pbft0_agree,{flush0.get('agree')}",
            f"pbft5_committed,{flush5.get('committed')}",
            f"pbft5_agree,{flush5.get('agree')}",
            f"total_locked,{chain.total_locked()}",
            f"reward_onchain_sum,{sum(onchain_rewards.values())}",
        ]
        (TAB / "e2e_summary.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        plot_fig8(summary, accepted[:8])
        return summary
    finally:
        hh.terminate()
        try:
            hh.wait(timeout=5)
        except Exception:
            hh.kill()


def plot_fig8(summary: dict, trace) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.8))
    axes[0].bar(
        ["Sybil reject", "Designate", "Malicious ban", "Accepted"],
        [
            summary["sybil_rejected"],
            summary["designate_attempts"],
            summary["malicious_blocked"],
            summary["accepted"],
        ],
        color=["#E03131", "#F08C00", "#7048E8", "#2F9E44"],
    )
    axes[0].set_title("1000 Python requests")
    axes[0].tick_params(axis="x", rotation=15)
    axes[0].set_ylabel("Count")

    axes[1].bar(
        ["PBFT 0% commit", "PBFT 5% commit"],
        [summary["pbft0"]["committed"], summary["pbft5"]["committed"]],
        color="#4C6EF5",
    )
    axes[1].set_title("Go ledger commits")
    axes[1].set_ylabel("Task cycles")

    labels = list(summary["onchain_rewards"].keys())
    eng = [summary["engine_rewards"][k] for k in labels]
    chain = [summary["onchain_rewards"][k] for k in labels]
    x = range(len(labels))
    axes[2].bar([i - 0.18 for i in x], eng, width=0.36, label="Engine", color="#4C6EF5")
    axes[2].bar([i + 0.18 for i in x], chain, width=0.36, label="On-chain", color="#ADB5BD")
    axes[2].set_xticks(list(x), labels)
    axes[2].set_title("Epoch reward engine vs chain")
    axes[2].legend(frameon=False)

    for ax in axes:
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("E2E: lock → schedule → PBFT → creditReward", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "fig8_e2e_trace.png", dpi=160)
    plt.close(fig)

    path = TAB / "e2e_trace.csv"
    rows = ["step,client,miner,accepted,rating"]
    for i, order in enumerate(trace, start=1):
        rows.append(
            f"{i},{order.client_id},{order.miner_id},{str(order.accepted).lower()},{order.rating}"
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, default=str))
