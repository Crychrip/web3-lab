from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Layer:
    id: str
    parents: tuple[str, ...]


@dataclass
class BisectStep:
    query: str
    equal: bool
    remaining: list[str]
    consistent: list[str]
    inconsistent: list[str]
    note: str


@dataclass
class BisectResult:
    fault: str
    steps: list[BisectStep]
    rounds: int


def ancestors(layers: dict[str, Layer], node: str) -> set[str]:
    out: set[str] = set()
    stack = list(layers[node].parents)
    while stack:
        cur = stack.pop()
        if cur in out or cur not in layers:
            continue
        out.add(cur)
        stack.extend(layers[cur].parents)
    return out


def sequential_mlp(n: int = 8) -> dict[str, Layer]:
    layers: dict[str, Layer] = {}
    for i in range(1, n + 1):
        pid = f"L{i-1}" if i > 1 else "x"
        layers[f"L{i}"] = Layer(f"L{i}", (pid,) if i > 1 else ())
    return layers


def inception_toy() -> dict[str, Layer]:
    """Small DAG reminiscent of an Inception block (SAKSHI Fig. 9)."""
    return {
        "L1": Layer("L1", ()),
        "A": Layer("A", ("L1",)),
        "B": Layer("B", ("L1",)),
        "C": Layer("C", ("L1",)),
        "L2": Layer("L2", ("A", "B", "C")),
        "L3": Layer("L3", ("L2",)),
    }


def _greedy_query(layers: dict[str, Layer], remaining: set[str]) -> str:
    best, best_score = None, -1
    n = len(remaining)
    for node in remaining:
        anc = ancestors(layers, node) & remaining
        x = len(anc)
        score = min(x, n - x)
        if score > best_score or (score == best_score and (best is None or node < best)):
            best, best_score = node, score
    assert best is not None
    return best


def model_bisection(
    layers: dict[str, Layer],
    honest: dict[str, int],
    accused: dict[str, int],
) -> BisectResult:
    """Optimistic proof-of-inference: find first layer with same inputs, different outputs."""
    remaining = set(layers)
    consistent: set[str] = set()
    inconsistent: set[str] = set()
    steps: list[BisectStep] = []

    def inputs_equal(node: str) -> bool:
        pars = layers[node].parents
        if not pars:
            return True
        return all(honest.get(p) == accused.get(p) for p in pars if p in honest)

    while remaining:
        if len(remaining) == 1:
            node = next(iter(remaining))
            equal = honest[node] == accused[node]
            steps.append(
                BisectStep(
                    query=node,
                    equal=equal,
                    remaining=sorted(remaining, key=lambda s: (len(s), s)),
                    consistent=sorted(consistent),
                    inconsistent=sorted(inconsistent | ({node} if not equal else set())),
                    note="single candidate left",
                )
            )
            if not equal and inputs_equal(node):
                return BisectResult(fault=node, steps=steps, rounds=len(steps))
            raise RuntimeError("could not isolate a faulty layer")

        query = _greedy_query(layers, remaining)
        equal = honest[query] == accused[query]
        anc = ancestors(layers, query)
        if equal:
            pruned = (anc | {query}) & remaining
            consistent |= pruned
            remaining -= pruned
            note = "outputs match; ancestors are consistent"
        else:
            pruned = remaining - (anc | {query})
            inconsistent |= {query}
            remaining -= pruned
            note = "outputs differ; fault is this node or an ancestor"
        steps.append(
            BisectStep(
                query=query,
                equal=equal,
                remaining=sorted(remaining, key=lambda s: (len(s), s)),
                consistent=sorted(consistent),
                inconsistent=sorted(inconsistent),
                note=note,
            )
        )

        for node in [n for n in _topo(layers) if n in remaining]:
            if honest[node] != accused[node] and inputs_equal(node):
                return BisectResult(fault=node, steps=steps, rounds=len(steps))

    raise RuntimeError("search emptied without a fault")


def chain_bisection(n: int = 12, fault: str = "L7") -> BisectResult:
    """Midpoint search on a chain. A fault is reported only for the queried node."""
    layers = sequential_mlp(n)
    honest, accused = diverge_at(layers, fault)
    remaining = [f"L{i}" for i in range(1, n + 1)]
    consistent: set[str] = set()
    inconsistent: set[str] = set()
    steps: list[BisectStep] = []

    def inputs_equal(node: str) -> bool:
        pars = layers[node].parents
        if not pars:
            return True
        return all(honest.get(p) == accused.get(p) for p in pars if p in honest)

    while remaining:
        mid = (len(remaining) - 1) // 2
        query = remaining[mid]
        equal = honest[query] == accused[query]
        idx = remaining.index(query)
        if equal:
            pruned = remaining[: idx + 1]
            consistent |= set(pruned)
            remaining = remaining[idx + 1 :]
            note = "outputs match; drop this node and its ancestors"
        else:
            pruned = remaining[idx + 1 :]
            inconsistent.add(query)
            remaining = remaining[: idx + 1]
            note = "outputs differ; drop strictly downstream nodes"
        steps.append(
            BisectStep(
                query=query,
                equal=equal,
                remaining=list(remaining),
                consistent=sorted(consistent, key=lambda s: int(s[1:])),
                inconsistent=sorted(inconsistent, key=lambda s: int(s[1:])),
                note=note,
            )
        )
        if (not equal) and inputs_equal(query):
            return BisectResult(fault=query, steps=steps, rounds=len(steps))
        if len(remaining) == 1:
            node = remaining[0]
            if honest[node] != accused[node] and inputs_equal(node):
                return BisectResult(fault=node, steps=steps, rounds=len(steps))
            raise RuntimeError("could not isolate a faulty layer")

    raise RuntimeError("search emptied without a fault")


def diverge_at(layers: dict[str, Layer], fault: str) -> tuple[dict[str, int], dict[str, int]]:
    """Honest outputs are 1,2,3,...; accused matches except the fault and its descendants."""
    order = _topo(layers)
    tainted = {fault} | {n for n in layers if fault in ancestors(layers, n)}
    honest: dict[str, int] = {}
    accused: dict[str, int] = {}
    for i, node in enumerate(order, start=1):
        honest[node] = i
        accused[node] = i + (100 if node in tainted else 0)
    return honest, accused


def _topo(layers: dict[str, Layer]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def visit(n: str) -> None:
        if n in seen or n not in layers:
            return
        for p in layers[n].parents:
            visit(p)
        seen.add(n)
        out.append(n)

    for n in layers:
        visit(n)
    return out
