# Assignment 3 – Graph Algorithms: Analysis

Language: **Java 17** (`src/Java/Algorithms.java`; `Main`, `Json`, `Input` are the supplied adapters).

> Sections marked **TODO** must be filled in with results of runs on your own machine before submission.
> Delete this note when everything is filled in.

## 1. Build, run and test commands

Run everything from the repository root.

```
python tools/run.py --setup                    # launch check
python tools/run.py --check                    # 36 public cases (run twice in one process)
python tools/run.py --input tests/my_cases.jsonl   # actual results of my own cases

python tests/run_tests.py                      # own tests: checkers, hand-written, random, full-limit, state reset
python tests/run_tests.py --skip-large         # same, without the n=100000 cases

# route helper tests
javac -d build/route src/Java/*.java tests/java/RouteTest.java
java -cp build/route RouteTest

# benchmark (Kruskal vs Prim)
javac -d build/bench src/Java/*.java tests/java/Bench.java
java -cp build/bench Bench 12345 | tee tests/benchmark_results.md
```

Manual compilation and launch of the solution itself:

```
javac -d build/app src/Java/*.java
java -cp build/app Main < tests/my_cases.jsonl
```

`tests/run_tests.py` needs Python 3.12+ (standard library only) and `javac`/`java` on the PATH.

## 2. Common design

**State reset.** No algorithm keeps data in static fields. Every method allocates its arrays (`parent`, `size`, `state`, `next`, heap, ...) inside the call, so a request cannot see anything from the previous one. The only static members are constants and the stateless helpers. `Main` calls one method per input line, so repeated and mixed requests in one process are independent. This is tested by sending a mixed sequence (including a cyclic `dag` request directly before an acyclic one) three times in one process and requiring identical results each round (Section 8).

**Deep DFS.** All DFS traversals (`topologicalOrder`, both Kosaraju passes) are iterative. An explicit `int[]` stack holds the suspended vertices and an `int[] next` array stores, for each vertex, the index of its next unscanned neighbour, so a resumed vertex continues where it stopped and neighbours are never rescanned. A vertex is pushed only when it changes from unvisited to visited/active, so each vertex is pushed at most once and a stack of size `n` is sufficient. There is no recursion, so a chain of 100 000 vertices cannot overflow the call stack (tested with deep chains and cycles).

**Adjacency lists.** `Graph` stores a compressed (CSR) adjacency structure: `start[v]..start[v+1]-1` index into `to[]` (neighbour) and `id[]` (original edge ID). Building it is a counting pass plus a fill pass, O(n + m); original IDs are preserved because every adjacency entry remembers its input position.

**Weights and overflow.** Costs and distances are `long`. Packed sort keys use `(w + 10^9) << 20 | edgeId`; `w + 10^9` is in `[0, 2·10^9]` (31 bits) and `edgeId < 2^20`, so the key fits in 63 bits and sorting keys sorts by `(weight, id)`.

## 3. DSU (`dsu`)

**Steps.** `parent[i]=i`, `size[i]=1`, `components=n`, `largest = n>0 ? 1 : 0`. For each pair, `find` both ends (iteratively: locate the root, then compress the whole path onto it). If the roots differ, attach the smaller tree under the larger one (union by size), add the sizes, decrement `components`, update `largest`. Append `[components, largest]` after every operation.

**Invariants.** The `parent` array is a forest whose trees are exactly the current connected components; `size[r]` is the number of vertices in the tree of root `r`; `components` is the number of roots; `largest` is the maximum size over all roots. A union of two different roots creates one tree whose size is the sum, so `largest` can only grow and only the merged size needs to be compared.

**Correctness.** Path compression changes only parent pointers inside one tree, never membership, so the partition is unchanged. Repeated unions and self-unions find equal roots and change nothing. Sizes are maintained separately from the union decision (size, not rank).

**Boundary cases.** `n=0` (no states), no operations (no initial state is emitted), self-union, repeated or reversed union, long chains (deep trees are handled by the iterative `find`).

**Complexity.** Time O(n + q·α(n)) amortised (union by size plus path compression); memory O(n + q) because the `q` states are returned.

## 4. Kruskal (`kruskal`)

**Steps.** Pack each edge into the key `(w + 10^9) << 20 | id` and sort the keys (primitive `long[]`). Scan in order; the edge is accepted iff `find(u) != find(v)` in a fresh DSU, then the sets are united. Collect cost and IDs; `components = n - acceptedEdges`; IDs are sorted ascending for a tidy output.

**Invariant.** After processing a prefix of the sorted edges, the accepted edges form a minimum spanning forest of the graph made of the processed edges, and the DSU sets are exactly the components of that processed graph.

**Correctness.** An edge whose ends are already in one set closes a cycle (or is a self-loop) and is never needed: by the cycle property it is a heaviest-or-tied edge of that cycle. An edge connecting two different sets is a lightest edge crossing the cut between them among the remaining edges, so the cut property allows it. Every component ends with `size-1` accepted edges, so the forest has `n - c` edges.

**Boundary cases.** self-loops (never accepted), parallel and tied edges (ID breaks ties; any answer is valid), negative weights (work unchanged, sort is by signed value), totals beyond 32 bits, isolates (counted in `components`), `n=0`, `m=0`.

**Complexity.** O(n + m log(m+1)) time (sort dominates), O(n + m) memory.

## 5. Prim (`prim`)

**Steps.** Build undirected adjacency lists of edge IDs (each edge appears at both ends; a self-loop appears twice and is skipped later). For every unvisited start vertex `s` (a new component, `components++`): mark `s`, push its incident edges into a min-heap of keys `(w + 10^9) << 20 | id`; repeatedly pop the lightest edge; if both ends are visited skip it, otherwise visit the unvisited end, add the edge and weight, and push the new vertex's edges. When the heap is empty the component is complete and the outer loop restarts from the next unvisited vertex.

**Invariant.** The visited vertices of the current component form a tree that belongs to a minimum spanning tree of that component; the heap contains every edge incident to a visited vertex that has not been popped. Popped edges with both ends visited are useless (they would close a cycle).

**Correctness.** The first popped edge with exactly one visited end is a lightest edge crossing the cut (visited, unvisited) because all crossing edges are in the heap; by the cut property it extends a minimum spanning tree. Restarting at an unvisited vertex handles every component, including isolates, so the result is a minimum spanning forest.

**Boundary cases.** same as Kruskal; self-loops are popped and skipped; a restart is required for disconnected graphs.

**Complexity.** Each edge is pushed at most twice, so time is O(n + m log(m+1)) with this lazy heap; memory O(n + m). (Java's `PriorityQueue<Long>` boxes the keys, which adds a constant factor.)

## 6. Kosaraju SCC (`scc`)

**Steps.** Build the graph and its transpose. Pass 1: iterative DFS over all vertices on the original graph, recording vertices in order of finishing. Pass 2: for vertices in decreasing finishing time, if the vertex has no label, run a DFS on the transpose and give every newly reached vertex the next label. Condensation: for every edge with different labels, encode `(a, b)` as `a·k + b`, sort, remove duplicates, decode.

**Invariant.** If there is an edge from SCC `C` to a different SCC `C'`, the latest finishing time in `C` is later than in `C'`. Therefore the unlabelled vertex with the greatest finishing time lies in a source component of the remaining condensation, and a DFS from it in the transpose reaches exactly its own SCC (all components that could reach it in the transpose are already labelled).

**Correctness.** Each pass-2 DFS labels exactly one SCC, so equal labels identify one SCC, and every vertex gets a label. Labels come out as 0..k-1. Edges inside an SCC have equal labels and are dropped; every cross-label edge yields a pair and duplicates are removed, so the condensation lists each cross-component pair once.

**Boundary cases.** `n=0` (both arrays empty), isolates (singleton SCCs), self-loops (internal, ignored), duplicate edges (one condensation pair), one big cycle, long path (deep DFS), graph that is already a DAG.

**Complexity.** The two DFS passes are O(n + m). My condensation de-duplication sorts the pairs, so the total is O(n + m log(m+1)) time rather than the O(n+m) expected with hashing; memory is O(n + m).

## 7. DFS topological order (`topo`) and DAG shortest paths (`dag`)

### topo

**Steps.** Three states: 0 unvisited, 1 active, 2 finished. Iterative DFS from every unvisited vertex. For the top vertex `u`, take the next neighbour `v`: state 1 means a back edge (directed cycle, return "cyclic"); state 0 means push `v` as active; state 2 is ignored. When all neighbours are scanned, mark `u` finished and append it to the finish list. The order is the finish list reversed.

**Invariant.** The active vertices are exactly the vertices on the DFS stack, and each is reachable from the one below it. A finished vertex has all its out-neighbours finished.

**Correctness.** An edge to an active vertex closes a cycle along the stack (a self-loop reaches its own active vertex). If no edge hits an active vertex, then for every edge `u→v`, `v` is finished before `u` is finished, so `u` appears before `v` in the reversed finish order. All components are covered by the outer loop.

**Boundary cases.** `n=0` (`acyclic=true`, `order=[]`), self-loop, cycle in a later component, duplicate edges, diamond (edge to a finished vertex is not a cycle), graph without edges. For a cycle the result is `acyclic=false`, `order=[]`.

**Complexity.** O(n + m) time and memory.

### dag

**Steps.** Compute the topological order of the whole graph with the same routine. If it finds a cycle (anywhere, even unreachable from the source) return `acyclic=false`, `distance=[]`, `parent_edge=[]`. Otherwise set the source reached with distance 0, then process vertices in topological order; for every reached vertex `u` and outgoing edge `e=(u,v,w)`, if `v` is not reached or `dist[u]+w < dist[v]`, set `dist[v]`, `parent_edge[v]=e`. Unreached vertices output `null` and `-1`.

**Invariant.** When `u` is taken from the order, all its predecessors have already been processed, so `dist[u]` is already final. Relaxation starts only from reached vertices, so no unreachable vertex ever lowers a distance.

**Correctness.** Induction along the topological order: the shortest path to `v` ends with some edge `(u,v)` whose tail `u` precedes `v`, so it is relaxed with the final `dist[u]`. Negative weights do not matter because no vertex is revisited. `parent_edge[v]` always stores the ID of the edge that last improved `v`, so it ends at `v`, starts at a reached vertex with an equally optimal distance, and following parents moves strictly backwards in the topological order until it reaches the source (the only reached vertex with parent `-1`). `null` is used for unreachable vertices, so `-1` remains a valid finite distance.

**Boundary cases.** `n=1`, source not first in the order, vertices before the source (unreachable), unreachable vertex with a very negative edge into a reachable vertex, parallel and tied edges, self-loop (cycle), cycle unreachable from the source, sums beyond 32 bits (`long`).

**Complexity.** O(n + m) time and memory.

### Route helper (`Algorithms.route`)

`route(source, target, parentEdge, edges)` follows `parentEdge[target]` back to the source, using the tail of each selected edge as the previous vertex, then reverses. It returns the vertex sequence from source to target; `[source]` when `target == source`; and an **empty list** when the target is unreachable (`parentEdge[target] == -1` and `target != source`). This choice concerns the helper only; the JSON `distance` still uses `null`. Time and space O(L) for a route with L vertices.

**Actual calls (output of `RouteTest`).**

**TODO – paste the output of `java -cp build/route RouteTest` here.** It must show the four required cases: reachable target (spec graph, target 3), the source, an unreachable target (spec graph, target 4) and tied/parallel edges. For each, check direction (tail of each selected edge equals the previous vertex) and total weight (equal to `distance`); the test prints `OK` only if both hold.

## 8. Testing

Everything below is produced by `python tests/run_tests.py`; inputs and actual outputs are stored in `tests/my_cases.jsonl`, `tests/my_cases_actual.jsonl`, `tests/TESTS.md` (inputs, justification, expected, actual, verdict) and `tests/large_report.txt`.

Checks are semantic, using references written independently in Python: own DSU simulation for `dsu`; own Kruskal (and brute force over all edge subsets for small graphs) for forests, with validation of distinct IDs, acyclicity, `n-c` edges and the sum of weights; iterative Tarjan for SCC partition equality plus the exact condensation set; Kahn's algorithm for the existence of a cycle and for the reference DAG distances, followed by the check that every `parent_edge[v]` ends at `v` and satisfies `dist[tail] + w == dist[v]`.

The checkers themselves are tested: each one accepts an alternative valid answer (a different tied forest, relabelled SCCs, another topological order, another tied parallel parent edge) and rejects invalid witnesses (cycle in the forest, wrong cost, merged SCCs, missing or duplicated condensation pair, edge going backwards, parent edge that ends elsewhere or is not on a shortest path, ignored unreachable cycle).

Coverage: empty and disconnected graphs, isolates, repeated and self unions, self-loops, parallel and tied edges, negative weights, totals beyond 32 bits in both directions, unreachable vertices, cycles outside the source's reachability, 710 random small cases compared with brute force/references, full-limit inputs (`n=100000`, `m` or `q = 250000`) for every task, deep chains and cycles of 100 000 vertices, and a mixed request sequence repeated three times in one process.

**TODO – paste the summary that your run prints** (self-test lines, number of passed hand-written/random cases, mixed-sequence result, and `tests/large_report.txt`), and the output of `python tools/run.py --check`. Report only what you actually ran.

## 9. Benchmark: Kruskal vs Prim

Setup is printed by `Bench` (see the header of `tests/benchmark_results.md`): same generated graph for both methods, a fixed seed, `System.nanoTime()`, 3 untimed warm-up runs per method and size, 7 measured runs per method and size, alternating Kruskal and Prim. Before timing, both results are verified to have equal cost and component count and to be valid forests. Timing boundary (identical for both methods): one `Algorithms.<method>(request)` call on an already parsed request, i.e. `Input.edges` conversion + algorithm + building the result map; compilation, graph generation, JSON parsing and JSON output are excluded.

**TODO – paste the table printed by `java -cp build/bench Bench 12345`** (three sizes: n=1 000/m=5 000, n=10 000/m=50 000, n=100 000/m=250 000; all runs and medians), and fill in: CPU model, RAM, operating system, Java version, the exact commands you used.

**Asymptotic argument.** Both are O(n + m log m). Kruskal sorts m primitive keys once and then does about m near-constant DSU operations. Prim's lazy heap handles up to 2m entries, each a boxed `Long` with O(log m) push and pop.

**TODO – observations.** After you have the numbers, write 3–5 sentences: which method was faster at each size, how the ratio changes with size, and whether that matches the argument above.

**Limitations (design of this benchmark).** Random graphs with average degree 5 are not the only possible shape (dense or special graphs may change the ranking); the JVM's JIT compilation and garbage collection add noise, so only medians of few runs are reported; boxing in `PriorityQueue<Long>` favours Kruskal in constants; the three sizes are small in number, so no growth rate is fitted; results depend on hardware and background load.

## 10. Sources and AI assistance

**TODO – rewrite this section in your own words according to the syllabus.** It has to state, truthfully:

- Sources used (course lecture notes, textbook chapters or web pages, with titles). Example candidates: the algorithms of Kruskal, Prim, Kosaraju, DFS topological sorting and DAG relaxation as taught in the course.
- AI tools used: no
- Your own contribution and verification: what you read and understood, what you ran (`tools/run.py --check`, `tests/run_tests.py`, the benchmark), and what you changed or fixed.

You are responsible for the correctness and originality of the submission.
