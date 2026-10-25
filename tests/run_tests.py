"""Own tests for Assignment 3 (Java solution in src/Java).
 
Usage (from the repository root):
    python tests/run_tests.py                 # everything
    python tests/run_tests.py --skip-large    # skip the full-limit cases
    python tests/run_tests.py --javac "javac" # compiler command (default: javac)
 
What it does
  1. compiles src/Java/*.java into a temporary directory;
  2. self-tests the checkers: each one must ACCEPT an alternative valid answer
     and REJECT an invalid witness;
  3. runs hand-written cases with justified expectations, random small cases
     compared with brute force, full-limit and deep-chain cases, and a mixed
     request sequence repeated in ONE process (state reset);
  4. writes tests/my_cases.jsonl, tests/my_cases_actual.jsonl, tests/TESTS.md
     and tests/large_report.txt, so the inputs, expectations and ACTUAL outputs
     are stored in the repository.
 
The checkers never reuse the Java code: references are written independently
in Python (own DSU, Kruskal, iterative Tarjan, Kahn, brute force).
"""
import argparse
import json
import random
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
 
ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
SRC = ROOT / "src" / "Java"
BIG_N, BIG_M = 100_000, 250_000
W = 1_000_000_000
 
class PyDsu:
    def __init__(self, n):
        self.p = list(range(n))
 
    def find(self, x):
        r = x
        while self.p[r] != r:
            r = self.p[r]
        while self.p[x] != r:
            nxt = self.p[x]
            self.p[x] = r
            x = nxt
        return r
 
    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        self.p[a] = b
        return True
 
 
def ref_dsu(n, ops):
    p = list(range(n))
    size = [1] * n
 
    def find(x):
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x
 
    comps, largest, states = n, (1 if n > 0 else 0), []
    for u, v in ops:
        a, b = find(u), find(v)
        if a != b:
            p[a] = b
            size[b] += size[a]
            comps -= 1
            largest = max(largest, size[b])
        states.append([comps, largest])
    return states
 
 
def ref_kruskal(n, edges):
    """Return (cost, components) of a minimum spanning forest."""
    d, cost, taken = PyDsu(n), 0, 0
    for i in sorted(range(len(edges)), key=lambda i: edges[i][2]):
        u, v, w = edges[i]
        if d.union(u, v):
            cost += w
            taken += 1
    return cost, n - taken
 
 
def brute_msf_cost(n, edges):
    """Minimum forest cost by trying every edge subset (m must be small)."""
    _, c = ref_kruskal(n, edges)
    need, m, best = n - c, len(edges), None
    for mask in range(1 << m):
        if bin(mask).count("1") != need:
            continue
        d, ok, cost = PyDsu(n), True, 0
        for i in range(m):
            if mask >> i & 1:
                if not d.union(edges[i][0], edges[i][1]):
                    ok = False
                    break
                cost += edges[i][2]
        if ok and (best is None or cost < best):
            best = cost
    return best
 
 
def ref_scc(n, edges):
    """Iterative Tarjan: list of component ids."""
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
    index, low, on, comp = [-1] * n, [0] * n, [False] * n, [-1] * n
    stack, idx, cc = [], 0, 0
    for s in range(n):
        if index[s] != -1:
            continue
        index[s] = low[s] = idx
        idx += 1
        stack.append(s)
        on[s] = True
        work = [(s, 0)]
        while work:
            u, i = work.pop()
            if i < len(adj[u]):
                work.append((u, i + 1))
                v = adj[u][i]
                if index[v] == -1:
                    index[v] = low[v] = idx
                    idx += 1
                    stack.append(v)
                    on[v] = True
                    work.append((v, 0))
                elif on[v]:
                    low[u] = min(low[u], index[v])
            else:
                if low[u] == index[u]:
                    while True:
                        w = stack.pop()
                        on[w] = False
                        comp[w] = cc
                        if w == u:
                            break
                    cc += 1
                if work:
                    par = work[-1][0]
                    low[par] = min(low[par], low[u])
    return comp
 
 
def kahn(n, edges):
    """Topological order by Kahn's algorithm, or None if a cycle exists."""
    adj = [[] for _ in range(n)]
    indeg = [0] * n
    for e in edges:
        adj[e[0]].append(e[1])
        indeg[e[1]] += 1
    queue = [v for v in range(n) if indeg[v] == 0]
    for u in queue:
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    return queue if len(queue) == n else None
 
 
def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)
 
 
def short(obj, limit=90):
    s = json.dumps(obj, separators=(",", ":"))
    return s if len(s) <= limit else s[:limit] + "...(%d chars)" % len(s)
 
 
def check_dsu(req, res):
    exp = ref_dsu(req["n"], req["operations"])
    errs = [] if res.get("states") == exp else ["states differ from reference"]
    return errs, "states=" + short(exp)
 
 
def check_forest(req, res, exp_cost=None):
    n, edges = req["n"], req["edges"]
    ref_cost, c = ref_kruskal(n, edges)
    if exp_cost is not None:
        ref_cost = exp_cost
    text = "cost=%d, components=%d, forest size=%d" % (ref_cost, c, n - c)
    errs = []
    ids = res.get("edge_ids")
    if not isinstance(ids, list) or not all(is_int(i) for i in ids):
        return ["edge_ids is not a list of integers"], text
    if len(set(ids)) != len(ids):
        errs.append("repeated edge id")
    if any(i < 0 or i >= len(edges) for i in ids):
        return errs + ["edge id out of range"], text
    d, total = PyDsu(n), 0
    for i in ids:
        u, v, w = edges[i]
        if not d.union(u, v):
            errs.append("selected edges contain a cycle or self-loop (id %d)" % i)
        total += w
    if len(ids) != n - c:
        errs.append("forest has %d edges, expected n-c=%d" % (len(ids), n - c))
    if res.get("components") != c:
        errs.append("components=%r, expected %d" % (res.get("components"), c))
    if res.get("cost") != ref_cost:
        errs.append("cost=%r, expected %d" % (res.get("cost"), ref_cost))
    if total != res.get("cost"):
        errs.append("reported cost differs from the sum of selected weights")
    return errs, text
 
 
def check_scc(req, res):
    n, edges = req["n"], req["edges"]
    ref = ref_scc(n, edges)
    groups = {}
    for v, c in enumerate(ref):
        groups.setdefault(c, []).append(v)
    text = "SCCs=" + short(sorted(groups.values()), 70)
    lab, cond = res.get("component"), res.get("condensation")
    if not isinstance(lab, list) or len(lab) != n or not all(is_int(x) and x >= 0 for x in lab):
        return ["component must be n nonnegative integers"], text
    errs = []
    fwd, bwd = {}, {}
    for v in range(n):
        if fwd.setdefault(lab[v], ref[v]) != ref[v] or bwd.setdefault(ref[v], lab[v]) != lab[v]:
            errs.append("labels do not match the SCC partition (vertex %d)" % v)
            break
    if not isinstance(cond, list) or not all(isinstance(p, list) and len(p) == 2 for p in cond):
        return errs + ["condensation must be a list of pairs"], text
    pairs = [tuple(p) for p in cond]
    if len(pairs) != len(set(pairs)):
        errs.append("duplicate condensation pair")
    expected = {(lab[u], lab[v]) for u, v in edges if lab[u] != lab[v]}
    if set(pairs) != expected:
        errs.append("condensation differs from the exact cross-component pairs")
    return errs, text + ", condensation pairs=%d" % len(expected)
 
 
def check_topo(req, res):
    n, edges = req["n"], req["edges"]
    cyclic = kahn(n, edges) is None
    text = "acyclic=%s" % str(not cyclic).lower()
    if res.get("acyclic") is not (not cyclic):
        return ["acyclic=%r, expected %s" % (res.get("acyclic"), not cyclic)], text
    order = res.get("order")
    if cyclic:
        return ([] if order == [] else ["order must be [] for a cyclic graph"]), text
    if not isinstance(order, list) or sorted(order) != list(range(n)):
        return ["order is not a permutation of all vertices"], text
    pos = {v: i for i, v in enumerate(order)}
    for u, v in edges:
        if pos[u] >= pos[v]:
            return ["edge %d->%d goes backwards" % (u, v)], text
    return [], text
 
 
def check_dag(req, res):
    n, edges, s = req["n"], req["edges"], req["source"]
    order = kahn(n, edges)
    if order is None:
        text = "acyclic=false, distance=[], parent_edge=[]"
        ok = res.get("acyclic") is False and res.get("distance") == [] and res.get("parent_edge") == []
        return ([] if ok else ["cyclic graph needs acyclic=false and two empty arrays"]), text
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u].append((v, w))
    dist = [None] * n
    dist[s] = 0
    for u in order: 
        if dist[u] is None:
            continue
        for v, w in adj[u]:
            if dist[v] is None or dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    text = "acyclic=true, distance=" + short(dist, 60)
    if res.get("acyclic") is not True:
        return ["acyclic should be true"], text
    errs = []
    if res.get("distance") != dist:
        errs.append("distance differs from reference")
    par = res.get("parent_edge")
    if not isinstance(par, list) or len(par) != n or not all(is_int(x) for x in par):
        return errs + ["parent_edge must be n integers"], text
    for v in range(n):
        e = par[v]
        if v == s or dist[v] is None:
            if e != -1:
                errs.append("parent_edge[%d] must be -1" % v)
            continue
        if not (0 <= e < len(edges)):
            errs.append("parent_edge[%d]=%d is not a valid edge id" % (v, e))
            continue
        u, t, w = edges[e]
       
        if t != v or dist[u] is None or dist[u] + w != dist[v]:
            errs.append("parent_edge[%d]=%d is not a shortest-path edge into %d" % (v, e, v))
    return errs[:3], text
 
 
CHECKERS = {
    "dsu": check_dsu, "kruskal": check_forest, "prim": check_forest,
    "scc": check_scc, "topo": check_topo, "dag": check_dag,
}
 
 
def run_check(req, res):
    if "error" in res:
        return ["solver returned error: %s" % res["error"]], "-"
    return CHECKERS[req["task"]](req, res)
 

def self_test_checkers():
    log = []
 
    def expect(name, errs, want_valid):
        ok = (not errs) == want_valid
        log.append((name, "accepted" if not errs else "rejected", ok))
        return ok
 
    tie = {"task": "kruskal", "n": 3, "edges": [[0, 1, 1], [1, 2, 1], [0, 2, 1]]}
    expect("forest: valid forest {0,1}", check_forest(tie, {"cost": 2, "edge_ids": [0, 1], "components": 1})[0], True)
    expect("forest: ALTERNATIVE valid forest {1,2}", check_forest(tie, {"cost": 2, "edge_ids": [2, 1], "components": 1})[0], True)
    expect("forest: INVALID cycle {0,1,2}", check_forest(tie, {"cost": 3, "edge_ids": [0, 1, 2], "components": 1})[0], False)
    expect("forest: INVALID too few edges", check_forest(tie, {"cost": 1, "edge_ids": [0], "components": 1})[0], False)
    expect("forest: INVALID wrong cost", check_forest(tie, {"cost": 5, "edge_ids": [0, 1], "components": 1})[0], False)
    loop = {"task": "prim", "n": 2, "edges": [[0, 0, -5], [0, 1, 1]]}
    expect("forest: INVALID self-loop selected", check_forest(loop, {"cost": -4, "edge_ids": [0, 1], "components": 1})[0], False)
 
    sc = {"task": "scc", "n": 4, "edges": [[0, 1], [1, 0], [1, 2], [0, 2], [2, 3]]}
    expect("scc: relabelled valid answer", check_scc(sc, {"component": [5, 5, 7, 9], "condensation": [[7, 9], [5, 7]]})[0], True)
    expect("scc: INVALID merged SCCs", check_scc(sc, {"component": [5, 5, 5, 9], "condensation": [[5, 9]]})[0], False)
    expect("scc: INVALID missing condensation pair", check_scc(sc, {"component": [5, 5, 7, 9], "condensation": [[5, 7]]})[0], False)
    expect("scc: INVALID duplicate pair", check_scc(sc, {"component": [5, 5, 7, 9], "condensation": [[5, 7], [5, 7], [7, 9]]})[0], False)
    expect("scc: INVALID reversed pair", check_scc(sc, {"component": [5, 5, 7, 9], "condensation": [[7, 5], [7, 9]]})[0], False)
 
    tp = {"task": "topo", "n": 4, "edges": [[0, 2], [1, 2], [2, 3]]}
    expect("topo: order [1,0,2,3]", check_topo(tp, {"acyclic": True, "order": [1, 0, 2, 3]})[0], True)
    expect("topo: ALTERNATIVE order [0,1,2,3]", check_topo(tp, {"acyclic": True, "order": [0, 1, 2, 3]})[0], True)
    expect("topo: INVALID edge goes backwards", check_topo(tp, {"acyclic": True, "order": [2, 0, 1, 3]})[0], False)
    expect("topo: INVALID missing vertex", check_topo(tp, {"acyclic": True, "order": [0, 1, 2]})[0], False)
    cy = {"task": "topo", "n": 2, "edges": [[0, 1], [1, 0]]}
    expect("topo: cycle -> false, []", check_topo(cy, {"acyclic": False, "order": []})[0], True)
    expect("topo: INVALID cycle reported acyclic", check_topo(cy, {"acyclic": True, "order": [0, 1]})[0], False)
 
    dg = {"task": "dag", "n": 3, "source": 0, "edges": [[0, 1, 2], [0, 1, 2], [1, 2, 1], [0, 2, 3]]}
    good = {"acyclic": True, "distance": [0, 2, 3], "parent_edge": [-1, 0, 2]}
    expect("dag: valid answer", check_dag(dg, good)[0], True)
    expect("dag: ALTERNATIVE tied parallel edge", check_dag(dg, {**good, "parent_edge": [-1, 1, 3]})[0], True)
    expect("dag: INVALID parent edge ends elsewhere", check_dag(dg, {**good, "parent_edge": [-1, 0, 0]})[0], False)
    expect("dag: INVALID parent edge is not shortest", check_dag(dg, {**good, "parent_edge": [-1, 0, 99]})[0], False)
    expect("dag: INVALID wrong distance", check_dag(dg, {**good, "distance": [0, 2, 4]})[0], False)
    expect("dag: INVALID parent vertex instead of edge id", check_dag(dg, {**good, "parent_edge": [-1, 0, 1]})[0], False)
    dc = {"task": "dag", "n": 3, "source": 0, "edges": [[0, 1, 1], [2, 2, 0]]}
    expect("dag: cycle unreachable from source -> false", check_dag(dc, {"acyclic": False, "distance": [], "parent_edge": []})[0], True)
    expect("dag: INVALID ignored unreachable cycle", check_dag(dc, {"acyclic": True, "distance": [0, 1, None], "parent_edge": [-1, 0, -1]})[0], False)
 
    expect("dsu: exact states", check_dsu({"task": "dsu", "n": 2, "operations": [[0, 1]]}, {"states": [[1, 2]]})[0], True)
    expect("dsu: INVALID states", check_dsu({"task": "dsu", "n": 2, "operations": [[0, 1]]}, {"states": [[2, 1]]})[0], False)
    return log
 
 
def req(task, n, **kw):
    r = {"task": task, "n": n}
    r.update(kw)
    return r
 
 
HAND = [] 
 
 
def add(cid, request, why):
    HAND.append((cid, request, why))
 
 
add("dsu-spec", req("dsu", 4, operations=[[0, 1], [1, 2], [0, 2], [3, 3]]),
    "0-1 and 1-2 give one set of size 3; 0-2 is a repeat and 3-3 a self-union, neither changes the partition.")
add("dsu-n0", req("dsu", 0, operations=[]), "n=0: no vertices, no operations -> states=[].")
add("dsu-n1-self", req("dsu", 1, operations=[[0, 0]]), "Single vertex, self-union keeps [1,1].")
add("dsu-no-ops", req("dsu", 5, operations=[]), "No operations -> no states (no initial state is output).")
add("dsu-pairs-then-merge", req("dsu", 6, operations=[[0, 1], [2, 3], [4, 5], [1, 2], [3, 4]]),
    "Three pairs (5,4,3 components, largest 2), then 1-2 gives size 4 (2 comps), then 3-4 joins all 6 (1 comp).")
add("dsu-repeat-self", req("dsu", 3, operations=[[2, 1], [1, 2], [2, 2]]),
    "Only the first union merges {1,2}; reversed repeat and self-union change nothing.")
 
GRAPHS = [
    ("spec", 4, [[0, 1, 4], [1, 2, 2], [0, 2, 3]], "Weights 2 and 3 connect 0,1,2 (cost 5); vertex 3 is isolated -> 2 components."),
    ("n0", 0, [], "n=0: cost 0, no edges, 0 components."),
    ("n1", 1, [], "One isolated vertex: cost 0, 1 component."),
    ("self-loop-negative", 3, [[1, 1, -5], [0, 1, 2]], "The -5 self-loop must never be selected; only edge 1 (cost 2); vertex 2 isolated -> 2 components."),
    ("parallel-equal", 2, [[0, 1, 3], [0, 1, 3], [0, 1, 3]], "Three tied parallel edges: any one, cost 3, 1 component."),
    ("negative-weights", 4, [[0, 1, -3], [1, 2, -4], [0, 2, -10], [2, 3, 5]], "Take -10, -4 (the -3 edge would close a cycle) and 5: -9."),
    ("sum-over-32-bit", 4, [[0, 1, W], [1, 2, W], [2, 3, W]], "Path with three 1e9 edges is the only spanning tree: 3e9 > 2^31."),
    ("negative-over-32-bit", 4, [[0, 1, -W], [1, 2, -W], [2, 3, -W]], "Only spanning tree has total -3e9 < -2^31."),
    ("disconnected", 6, [[0, 1, 1], [2, 3, 7], [3, 4, 2], [2, 4, 9]], "{0,1}: 1; {2,3,4}: 2+7 (9 dropped); {5} isolated -> cost 10, 3 components."),
    ("triangle-ties", 3, [[0, 1, 1], [1, 2, 1], [0, 2, 1]], "Any two of three tied edges: cost 2 (several valid forests)."),
]
for gid, n, e, why in GRAPHS:
    add("kruskal-" + gid, req("kruskal", n, edges=e), why)
    add("prim-" + gid, req("prim", n, edges=e), why + " (same graph, Prim)")
 
add("scc-spec", req("scc", 4, edges=[[0, 1], [1, 0], [1, 2], [0, 2], [2, 3]]), "SCCs {0,1},{2},{3}; condensation {01->2, 2->3}, duplicates 1->2/0->2 merged.")
add("scc-n0", req("scc", 0, edges=[]), "n=0: both output arrays empty.")
add("scc-isolates", req("scc", 3, edges=[]), "No edges: three singleton SCCs, empty condensation.")
add("scc-self-loops", req("scc", 2, edges=[[0, 0], [1, 1], [0, 1]]), "Self-loops do not merge anything; SCCs {0},{1} with one pair 0->1.")
add("scc-duplicates", req("scc", 4, edges=[[0, 1], [0, 1], [1, 0], [2, 3], [2, 3]]), "SCCs {0,1},{2},{3}; duplicate 2->3 must appear once, internal edges excluded.")
add("scc-two-cycles", req("scc", 6, edges=[[0, 1], [1, 2], [2, 0], [3, 4], [4, 5], [5, 3], [2, 3]]), "Two 3-cycles joined by one edge: 2 SCCs, 1 condensation pair.")
add("scc-one-cycle", req("scc", 5, edges=[[0, 1], [1, 2], [2, 3], [3, 4], [4, 0]]), "One 5-cycle: a single SCC, empty condensation.")
add("scc-diamond-dag", req("scc", 4, edges=[[0, 1], [0, 2], [1, 3], [2, 3]]), "A DAG: four singleton SCCs and four condensation pairs.")
 
add("topo-spec", req("topo", 4, edges=[[0, 2], [1, 2], [2, 3]]), "Acyclic; 0 and 1 precede 2, 2 precedes 3.")
add("topo-n0", req("topo", 0, edges=[]), "n=0: acyclic=true, order=[].")
add("topo-self-loop", req("topo", 1, edges=[[0, 0]]), "A self-loop is a directed cycle.")
add("topo-cycle-second-component", req("topo", 5, edges=[[0, 1], [2, 3], [3, 4], [4, 2]]), "Cycle 2->3->4->2 lies in a later component; every component must be checked.")
add("topo-diamond", req("topo", 4, edges=[[0, 1], [0, 2], [1, 3], [2, 3]]), "Second visit of vertex 3 reaches a FINISHED vertex: no cycle.")
add("topo-duplicates", req("topo", 3, edges=[[0, 1], [0, 1], [1, 2]]), "Duplicate edges are harmless; chain 0,1,2.")
add("topo-two-cycle", req("topo", 2, edges=[[0, 1], [1, 0]]), "0->1->0 is a cycle.")
add("topo-no-edges", req("topo", 3, edges=[]), "No edges: any permutation is valid.")
 
add("dag-spec", req("dag", 5, source=0, edges=[[0, 1, 3], [0, 2, 8], [1, 2, -7], [2, 3, 4]]), "0->1 (3), ->2 (-4), ->3 (0); vertex 4 unreachable (null, -1).")
add("dag-n1", req("dag", 1, source=0, edges=[]), "n=1: distance [0], parent_edge [-1].")
add("dag-unreachable-cycle", req("dag", 4, source=0, edges=[[0, 1, 1], [2, 3, 1], [3, 2, 1]]), "Cycle 2<->3 is unreachable from the source but still makes acyclic=false.")
add("dag-negative-finite", req("dag", 3, source=0, edges=[[0, 1, -1], [1, 2, -1]]), "-1 is a valid finite distance: [0,-1,-2], not 'unreachable'.")
add("dag-ties-parallel", req("dag", 3, source=0, edges=[[0, 1, 2], [0, 1, 2], [1, 2, 1], [0, 2, 3]]), "Distances [0,2,3]; parallel tied edges 0/1 and tied routes to 2 give several valid parent arrays.")
add("dag-no-relax-from-unreachable", req("dag", 3, source=0, edges=[[2, 1, -100], [0, 1, 5]]), "Vertex 2 is unreachable; its -100 edge must not improve vertex 1 -> [0,5,null].")
add("dag-self-loop", req("dag", 2, source=0, edges=[[0, 1, 1], [1, 1, 0]]), "Self-loop makes the graph cyclic.")
add("dag-over-32-bit", req("dag", 4, source=0, edges=[[0, 1, W], [1, 2, W], [2, 3, W]]), "Distance to 3 is 3e9 > 2^31.")
add("dag-negative-over-32-bit", req("dag", 4, source=0, edges=[[0, 1, -W], [1, 2, -W], [2, 3, -W]]), "Distance to 3 is -3e9 < -2^31.")
add("dag-source-in-middle", req("dag", 4, source=2, edges=[[0, 1, 1], [2, 3, 4], [1, 2, 1]]), "Vertices 0,1 precede the source and stay unreachable: [null,null,0,4].")
 
 
def rnd_weighted(rng, n, m, lo, hi):
    return [[rng.randrange(n), rng.randrange(n), rng.randint(lo, hi)] for _ in range(m)] if n else []
 
 
def rnd_directed(rng, n, m):
    return [[rng.randrange(n), rng.randrange(n)] for _ in range(m)] if n else []
 
 
def rnd_dag_edges(rng, n, m, lo, hi):
    if n < 2:
        return []
    perm = list(range(n))
    rng.shuffle(perm)
    out = []
    for _ in range(m):
        a, b = sorted(rng.sample(range(n), 2))
        out.append([perm[a], perm[b], rng.randint(lo, hi)])
    return out
 
 
def small_random(rng, k):
    cases = []
    for i in range(k):
        n = rng.randint(0, 8)
        m = rng.randint(0, 10) if n else 0
        we = rnd_weighted(rng, n, m, -5, 5)
        cases.append(("rand%03d-kruskal" % i, req("kruskal", n, edges=we), True))
        cases.append(("rand%03d-prim" % i, req("prim", n, edges=we), True))
        cases.append(("rand%03d-dsu" % i, req("dsu", n, operations=[[a, b] for a, b, _ in rnd_weighted(rng, n, rng.randint(0, 10), 0, 0)]), False))
        de = rnd_directed(rng, n, rng.randint(0, 12) if n else 0)
        cases.append(("rand%03d-scc" % i, req("scc", n, edges=de), False))
        cases.append(("rand%03d-topo" % i, req("topo", n, edges=de), False))
        if n >= 1:
            src = rng.randrange(n)
            if rng.random() < 0.6:
                dg = rnd_dag_edges(rng, n, rng.randint(0, 12), -6, 6)
            else:
                dg = rnd_weighted(rng, n, rng.randint(0, 8), -6, 6)
            cases.append(("rand%03d-dag" % i, req("dag", n, source=src, edges=dg), False))
    return cases
 
 
def large_cases(rng):
    N, M = BIG_N, BIG_M
    chain2 = [[i, i + 1] for i in range(N - 1)]
    out = []
    ops = [[rng.randrange(N), rng.randrange(N)] for _ in range(M)]
    out.append(("large-dsu-random-q250000", req("dsu", N, operations=ops)))
    out.append(("deep-dsu-chain", req("dsu", N, operations=[[i, i + 1] for i in range(N - 1)] + [[N - 1, 0]] * 5)))
    out.append(("deep-dsu-reverse-chain", req("dsu", N, operations=[[i + 1, i] for i in range(N - 2, -1, -1)])))
    for task in ("kruskal", "prim"):
        out.append(("large-%s-random-m250000" % task, req(task, N, edges=rnd_weighted(rng, N, M, -W, W))))
    path_w = [[i, i + 1, W if i % 2 else -W] for i in range(N - 1)]
    for task in ("kruskal", "prim"):
        out.append(("deep-%s-path-n100000" % task, req(task, N, edges=path_w)))
    out.append(("large-scc-random-m250000", req("scc", N, edges=rnd_directed(rng, N, M))))
    out.append(("deep-scc-single-cycle", req("scc", N, edges=chain2 + [[N - 1, 0]])))
    out.append(("deep-scc-path-dag", req("scc", N, edges=chain2)))
    out.append(("deep-topo-chain", req("topo", N, edges=chain2)))
    out.append(("deep-topo-chain-with-back-edge", req("topo", N, edges=chain2 + [[N - 1, 0]])))
    out.append(("large-topo-random-dag-m250000", req("topo", N, edges=[[a, b] for a, b, _ in rnd_dag_edges(rng, N, M, 0, 0)])))
    out.append(("deep-dag-chain-negative-1e9", req("dag", N, source=0, edges=[[i, i + 1, -W] for i in range(N - 1)])))
    out.append(("large-dag-random-m250000", req("dag", N, source=0, edges=rnd_dag_edges(rng, N, M, -W, W))))
    half = N // 2
    cyc = [[i, i + 1, 1] for i in range(half - 1)] + [[half + i, half + i + 1, 1] for i in range(N - half - 1)] + [[N - 1, half, 1]]
    out.append(("deep-dag-cycle-unreachable-from-source", req("dag", N, source=0, edges=cyc)))
    return out
 
 
class Solver:
    def __init__(self, classes_dir):
        self.proc = subprocess.Popen(
            ["java", "-cp", str(classes_dir), "Main"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8")
 
    def ask_line(self, line):
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        out = self.proc.stdout.readline()
        if not out:
            raise RuntimeError("solver closed its output; stderr: " + self.proc.stderr.read()[:500])
        return out.rstrip("\n")
 
    def ask(self, request):
        return json.loads(self.ask_line(json.dumps(request, separators=(",", ":"))))
 
    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=30)
 
 
def compile_java(javac_cmd, out_dir):
    cmd = shlex.split(javac_cmd) + ["-encoding", "UTF-8", "-d", str(out_dir)] + [str(p) for p in sorted(SRC.glob("*.java"))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("compilation failed:\n" + r.stdout + r.stderr)
 
 
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--javac", default="javac")
    ap.add_argument("--skip-large", action="store_true")
    ap.add_argument("--random", type=int, default=120, help="random small cases per family")
    ap.add_argument("--seed", type=int, default=20261025)
    args = ap.parse_args()
    failures = []
 
    print("== checker self-test (accept alternative valid answers, reject invalid witnesses)")
    st = self_test_checkers()
    for name, verdict, ok in st:
        print("  %-48s %-9s %s" % (name, verdict, "ok" if ok else "SELF-TEST FAILED"))
        if not ok:
            failures.append("self-test: " + name)
 
    build = Path(tempfile.mkdtemp(prefix="daa3_"))
    compile_java(args.javac, build)
    solver = Solver(build)
 
    print("== ping")
    pong = solver.ask({"task": "ping"})
    print("  ", pong)
    if pong != {"status": "ready"}:
        failures.append("ping")
 
    print("== hand-written cases (%d)" % len(HAND))
    rows, actual_lines = [], []
    for cid, request, why in HAND:
        line = json.dumps(request, separators=(",", ":"))
        raw = solver.ask_line(line)
        res = json.loads(raw)
        errs, exp = run_check(request, res)
        actual_lines.append(raw)
        rows.append((cid, line, why, exp, raw, not errs, errs))
        if errs:
            failures.append("%s: %s" % (cid, "; ".join(errs)))
            print("  FAIL", cid, errs)
    print("   passed %d/%d" % (sum(1 for r in rows if r[5]), len(rows)))
 
    (TESTS / "my_cases.jsonl").write_text("\n".join(r[1] for r in rows) + "\n", encoding="utf-8")
    (TESTS / "my_cases_actual.jsonl").write_text("\n".join(actual_lines) + "\n", encoding="utf-8")
    with open(TESTS / "TESTS.md", "w", encoding="utf-8") as f:
        f.write("# Own test cases (generated by `python tests/run_tests.py`)\n\n")
        f.write("Inputs: `tests/my_cases.jsonl`; actual outputs, line by line: `tests/my_cases_actual.jsonl`.\n")
        f.write("Expected values come from independent Python references (see `run_tests.py`); "
                "non-unique answers are checked by validity, not by equality.\n\n")
        f.write("| # | id | why this answer is right | expected | actual output | verdict |\n|---|---|---|---|---|---|\n")
        for i, (cid, line, why, exp, raw, ok, errs) in enumerate(rows, 1):
            f.write("| %d | `%s` | %s | %s | `%s` | %s |\n" % (
                i, cid, why.replace("|", "/"), exp.replace("|", "/"), short(json.loads(raw), 110).replace("|", "/"),
                "PASS" if ok else "FAIL: " + "; ".join(errs)))
 
    print("== random small cases vs brute force / references")
    rng = random.Random(args.seed)
    cases, bad, count = small_random(rng, args.random), 0, 0
    for cid, request, brute in cases:
        res = solver.ask(request)
        errs, _ = run_check(request, res)
        if brute and not errs:
            b = brute_msf_cost(request["n"], request["edges"])
            if b != res["cost"]:
                errs.append("cost %r differs from brute force %r" % (res["cost"], b))
        count += 1
        if errs:
            bad += 1
            failures.append("%s: %s" % (cid, "; ".join(errs)))
            print("  FAIL", cid, errs, short(request, 200))
    print("   passed %d/%d" % (count - bad, count))
 
    print("== mixed requests repeated 3x in one process (state reset)")
    seq = [("ping", {"task": "ping"})]
    for cid in ("dag-unreachable-cycle", "dag-spec", "dsu-spec", "dsu-pairs-then-merge", "kruskal-disconnected",
                "prim-disconnected", "scc-two-cycles", "scc-spec", "topo-cycle-second-component", "topo-spec",
                "dag-ties-parallel", "dag-n1", "dsu-n0", "kruskal-n0", "scc-n0", "topo-n0"):
        seq.append((cid, next(r for c, r, _ in HAND if c == cid)))
    for task, gen in (("kruskal", lambda: req("kruskal", 2000, edges=rnd_weighted(rng, 2000, 6000, -W, W))),
                      ("prim", lambda: req("prim", 2000, edges=rnd_weighted(rng, 2000, 6000, -W, W))),
                      ("dsu", lambda: req("dsu", 2000, operations=[[rng.randrange(2000), rng.randrange(2000)] for _ in range(6000)])),
                      ("scc", lambda: req("scc", 2000, edges=rnd_directed(rng, 2000, 6000))),
                      ("dag", lambda: req("dag", 2000, source=0, edges=rnd_dag_edges(rng, 2000, 6000, -W, W)))):
        seq.append(("mid-" + task, gen()))
    first, bad = {}, 0
    for rnd in range(3):
        for cid, request in seq:
            raw = solver.ask_line(json.dumps(request, separators=(",", ":")))
            res = json.loads(raw)
            errs = [] if request["task"] == "ping" and res == {"status": "ready"} else (
                run_check(request, res)[0] if request["task"] != "ping" else ["bad ping reply"])
            if rnd == 0:
                first[cid] = raw
            elif raw != first[cid]:
                errs.append("repeat differs from first run (state leaked?)")
            if errs:
                bad += 1
                failures.append("mixed round %d %s: %s" % (rnd, cid, "; ".join(errs)))
    print("   %d requests per round, %d problems" % (len(seq), bad))
 
    report = []
    if not args.skip_large:
        print("== full-limit and deep-chain cases (n=%d, m/q=%d)" % (BIG_N, BIG_M))
        for cid, request in large_cases(random.Random(args.seed + 1)):
            t0 = time.perf_counter()
            res = solver.ask(request)
            dt = time.perf_counter() - t0
            errs, _ = run_check(request, res)
            size = len(request.get("edges", request.get("operations", [])))
            line = "%-42s n=%-7d m/q=%-7d %7.2fs  %s" % (cid, request["n"], size, dt, "PASS" if not errs else "FAIL " + "; ".join(errs))
            print("  ", line)
            report.append(line)
            if errs:
                failures.append("%s: %s" % (cid, "; ".join(errs)))
        (TESTS / "large_report.txt").write_text(
            "Wall-clock time of one request in a running process, including JSON parse/print and the Python pipe.\n"
            "Seed %d. Run: python tests/run_tests.py\n\n" % args.seed + "\n".join(report) + "\n", encoding="utf-8")
 
    solver.close()
    print("\n== SUMMARY: %s" % ("ALL PASSED" if not failures else "%d FAILURE(S)" % len(failures)))
    for f in failures[:20]:
        print("  -", f)
    sys.exit(1 if failures else 0)
 
 
if __name__ == "__main__":
    main()
 
