import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;

/**
 * Implement the six methods and add your route-reconstruction helper.
 * Input extraction is provided; all algorithm state belongs to the current request.
 * See ../../README.md for contracts and Java guidance.
 *
 * All DFS traversals are iterative (explicit stack), so deep graphs
 * (for example a chain of 100000 vertices) cannot overflow the call stack.
 * No state is kept in static fields, so every request starts clean.
 */
public final class Algorithms {
    private static final long WEIGHT_OFFSET = 1_000_000_000L;
    private static final int ID_BITS = 20; // edge ids fit in 20 bits (m <= 250000)
    private static final long ID_MASK = (1L << ID_BITS) - 1;

    private Algorithms() {
    }

    // ------------------------------------------------------------------
    // Shared helpers
    // ------------------------------------------------------------------

    /** Disjoint-set union with path compression and union by size. */
    private static final class Dsu {
        final int[] parent;
        final int[] size;

        Dsu(int n) {
            parent = new int[n];
            size = new int[n];
            for (int i = 0; i < n; i++) {
                parent[i] = i;
                size[i] = 1;
            }
        }

        /** Iterative find: first locate the root, then compress the path. */
        int find(int x) {
            int root = x;
            while (parent[root] != root) {
                root = parent[root];
            }
            while (parent[x] != root) {
                int next = parent[x];
                parent[x] = root;
                x = next;
            }
            return root;
        }

        /** Returns the size of the merged set, or -1 if already together. */
        int union(int a, int b) {
            int ra = find(a);
            int rb = find(b);
            if (ra == rb) {
                return -1;
            }
            if (size[ra] < size[rb]) {
                int tmp = ra;
                ra = rb;
                rb = tmp;
            }
            parent[rb] = ra;
            size[ra] += size[rb];
            return size[ra];
        }
    }

    /**
     * Compressed adjacency lists (CSR). For vertex v, its neighbours are
     * to[start[v] .. start[v + 1] - 1] and the matching original edge ids are
     * id[...]. With reverse = true the edge direction is flipped (transpose).
     */
    private static final class Graph {
        final int[] start;
        final int[] to;
        final int[] id;

        Graph(int n, int[][] edges, boolean reverse) {
            start = new int[n + 1];
            for (int[] e : edges) {
                int from = reverse ? e[1] : e[0];
                start[from + 1]++;
            }
            for (int i = 0; i < n; i++) {
                start[i + 1] += start[i];
            }
            to = new int[edges.length];
            id = new int[edges.length];
            int[] fill = Arrays.copyOf(start, n);
            for (int i = 0; i < edges.length; i++) {
                int from = reverse ? edges[i][1] : edges[i][0];
                int dest = reverse ? edges[i][0] : edges[i][1];
                int pos = fill[from]++;
                to[pos] = dest;
                id[pos] = i;
            }
        }
    }

    /**
     * Three-state iterative DFS (0 = white, 1 = gray, 2 = black).
     * Returns a topological order, or null if a directed cycle exists
     * (a gray vertex reached again, including self-loops).
     */
    private static int[] topologicalOrder(int n, Graph g) {
        int[] state = new int[n];
        int[] next = new int[n];
        int[] stack = new int[n];
        int[] finish = new int[n];
        int finished = 0;

        for (int s = 0; s < n; s++) {
            if (state[s] != 0) {
                continue;
            }
            int top = 0;
            stack[top++] = s;
            state[s] = 1;
            next[s] = g.start[s];
            while (top > 0) {
                int u = stack[top - 1];
                if (next[u] < g.start[u + 1]) {
                    int v = g.to[next[u]++];
                    if (state[v] == 1) {
                        return null; // back edge: directed cycle
                    }
                    if (state[v] == 0) {
                        state[v] = 1;
                        next[v] = g.start[v];
                        stack[top++] = v;
                    }
                } else {
                    state[u] = 2;
                    finish[finished++] = u;
                    top--;
                }
            }
        }

        int[] order = new int[n];
        for (int i = 0; i < n; i++) {
            order[i] = finish[n - 1 - i]; // reverse finish order
        }
        return order;
    }

    private static List<Integer> toList(int[] values) {
        List<Integer> list = new ArrayList<>(values.length);
        for (int value : values) {
            list.add(value);
        }
        return list;
    }

    // ------------------------------------------------------------------
    // dsu
    // ------------------------------------------------------------------

    /** DSU with path compression and union by size/rank; return states. */
    static Map<String, Object> dsu(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] operations = Input.operations(input);

        Dsu sets = new Dsu(n);
        int components = n;
        int largest = n > 0 ? 1 : 0;

        List<int[]> states = new ArrayList<>(operations.length);
        for (int[] op : operations) {
            int merged = sets.union(op[0], op[1]);
            if (merged != -1) {
                components--;
                largest = Math.max(largest, merged);
            }
            states.add(new int[] {components, largest});
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("states", states);
        return result;
    }

    // ------------------------------------------------------------------
    // kruskal
    // ------------------------------------------------------------------

    /** Separate Kruskal implementation; return cost, edge_ids, components. */
    static Map<String, Object> kruskal(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);

        // Sort by (weight, original id) packed into one long.
        long[] keys = new long[edges.length];
        for (int i = 0; i < edges.length; i++) {
            keys[i] = ((edges[i][2] + WEIGHT_OFFSET) << ID_BITS) | i;
        }
        Arrays.sort(keys);

        Dsu sets = new Dsu(n);
        long cost = 0;
        List<Integer> chosen = new ArrayList<>();
        for (long key : keys) {
            int index = (int) (key & ID_MASK);
            int[] e = edges[index];
            if (sets.union(e[0], e[1]) != -1) { // loops and cycles are rejected
                cost += e[2];
                chosen.add(index);
            }
        }
        Collections.sort(chosen);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("cost", cost);
        result.put("edge_ids", chosen);
        result.put("components", n - chosen.size());
        return result;
    }

    // ------------------------------------------------------------------
    // prim
    // ------------------------------------------------------------------

    /** Separate Prim implementation; restart for every unvisited component. */
    static Map<String, Object> prim(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);

        // Undirected adjacency: every edge appears at both endpoints.
        int[] start = new int[n + 1];
        for (int[] e : edges) {
            start[e[0] + 1]++;
            start[e[1] + 1]++;
        }
        for (int i = 0; i < n; i++) {
            start[i + 1] += start[i];
        }
        int[] adjEdge = new int[2 * edges.length];
        int[] fill = Arrays.copyOf(start, n);
        for (int i = 0; i < edges.length; i++) {
            adjEdge[fill[edges[i][0]]++] = i;
            adjEdge[fill[edges[i][1]]++] = i;
        }

        boolean[] visited = new boolean[n];
        long cost = 0;
        int components = 0;
        List<Integer> chosen = new ArrayList<>();
        PriorityQueue<Long> heap = new PriorityQueue<>();

        for (int s = 0; s < n; s++) {
            if (visited[s]) {
                continue;
            }
            components++; // new component: restart Prim from s
            visited[s] = true;
            pushEdges(s, start, adjEdge, edges, heap);

            while (!heap.isEmpty()) {
                int index = (int) (heap.poll() & ID_MASK);
                int[] e = edges[index];
                int next;
                if (!visited[e[0]]) {
                    next = e[0];
                } else if (!visited[e[1]]) {
                    next = e[1];
                } else {
                    continue; // both endpoints already in the tree
                }
                visited[next] = true;
                cost += e[2];
                chosen.add(index);
                pushEdges(next, start, adjEdge, edges, heap);
            }
        }
        Collections.sort(chosen);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("cost", cost);
        result.put("edge_ids", chosen);
        result.put("components", components);
        return result;
    }

    private static void pushEdges(int v, int[] start, int[] adjEdge,
                                  int[][] edges, PriorityQueue<Long> heap) {
        for (int p = start[v]; p < start[v + 1]; p++) {
            int index = adjEdge[p];
            heap.add(((edges[index][2] + WEIGHT_OFFSET) << ID_BITS) | index);
        }
    }

    // ------------------------------------------------------------------
    // scc
    // ------------------------------------------------------------------

    /** Kosaraju's two DFS passes; return component and exact condensation. */
    static Map<String, Object> scc(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);

        Graph forward = new Graph(n, edges, false);
        Graph transpose = new Graph(n, edges, true);

        // Pass 1: DFS on the original graph, record finishing order.
        boolean[] seen = new boolean[n];
        int[] next = new int[n];
        int[] stack = new int[n];
        int[] finish = new int[n];
        int finished = 0;
        for (int s = 0; s < n; s++) {
            if (seen[s]) {
                continue;
            }
            int top = 0;
            stack[top++] = s;
            seen[s] = true;
            next[s] = forward.start[s];
            while (top > 0) {
                int u = stack[top - 1];
                if (next[u] < forward.start[u + 1]) {
                    int v = forward.to[next[u]++];
                    if (!seen[v]) {
                        seen[v] = true;
                        next[v] = forward.start[v];
                        stack[top++] = v;
                    }
                } else {
                    finish[finished++] = u;
                    top--;
                }
            }
        }

        // Pass 2: DFS on the transpose in decreasing finishing time.
        int[] component = new int[n];
        Arrays.fill(component, -1);
        int count = 0;
        for (int i = n - 1; i >= 0; i--) {
            int s = finish[i];
            if (component[s] != -1) {
                continue;
            }
            int top = 0;
            stack[top++] = s;
            component[s] = count;
            while (top > 0) {
                int u = stack[--top];
                for (int p = transpose.start[u]; p < transpose.start[u + 1]; p++) {
                    int v = transpose.to[p];
                    if (component[v] == -1) {
                        component[v] = count;
                        stack[top++] = v;
                    }
                }
            }
            count++;
        }

        // Condensation: distinct cross-component pairs.
        long[] pairs = new long[edges.length];
        int used = 0;
        for (int[] e : edges) {
            int a = component[e[0]];
            int b = component[e[1]];
            if (a != b) {
                pairs[used++] = (long) a * count + b;
            }
        }
        pairs = Arrays.copyOf(pairs, used);
        Arrays.sort(pairs);
        List<int[]> condensation = new ArrayList<>();
        for (int i = 0; i < used; i++) {
            if (i > 0 && pairs[i] == pairs[i - 1]) {
                continue;
            }
            condensation.add(new int[] {(int) (pairs[i] / count), (int) (pairs[i] % count)});
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("component", component);
        result.put("condensation", condensation);
        return result;
    }

    // ------------------------------------------------------------------
    // topo
    // ------------------------------------------------------------------

    /** Three-state DFS and reverse finish order; return acyclic and order. */
    static Map<String, Object> topo(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);

        int[] order = topologicalOrder(n, new Graph(n, edges, false));

        Map<String, Object> result = new LinkedHashMap<>();
        if (order == null) {
            result.put("acyclic", false);
            result.put("order", new ArrayList<Integer>());
        } else {
            result.put("acyclic", true);
            result.put("order", order);
        }
        return result;
    }

    // ------------------------------------------------------------------
    // dag
    // ------------------------------------------------------------------

    /** Whole-graph cycle check and DAG relaxation; return acyclic, distance, parent_edge. */
    static Map<String, Object> dag(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int source = Input.source(input);
        int[][] edges = Input.edges(input);

        Graph g = new Graph(n, edges, false);
        // The cycle check covers the whole graph, even parts unreachable from source.
        int[] order = topologicalOrder(n, g);

        Map<String, Object> result = new LinkedHashMap<>();
        if (order == null) {
            result.put("acyclic", false);
            result.put("distance", new ArrayList<Long>());
            result.put("parent_edge", new ArrayList<Integer>());
            return result;
        }

        long[] dist = new long[n];
        boolean[] reached = new boolean[n];
        int[] parentEdge = new int[n];
        Arrays.fill(parentEdge, -1);
        reached[source] = true;
        dist[source] = 0;

        // Relax edges in topological order; negative weights are fine in a DAG.
        for (int u : order) {
            if (!reached[u]) {
                continue;
            }
            for (int p = g.start[u]; p < g.start[u + 1]; p++) {
                int v = g.to[p];
                int e = g.id[p];
                long candidate = dist[u] + edges[e][2];
                if (!reached[v] || candidate < dist[v]) {
                    reached[v] = true;
                    dist[v] = candidate;
                    parentEdge[v] = e;
                }
            }
        }

        List<Long> distance = new ArrayList<>(n);
        for (int v = 0; v < n; v++) {
            distance.add(reached[v] ? dist[v] : null);
        }
        result.put("acyclic", true);
        result.put("distance", distance);
        result.put("parent_edge", toList(parentEdge));
        return result;
    }

    /**
     * Route-reconstruction helper. Follows parent edges back from target to
     * source and returns the vertices from source to target.
     * Returns [source] when target == source and an empty list when the
     * target is unreachable.
     */
    static List<Integer> route(int source, int target, int[] parentEdge, int[][] edges) {
        List<Integer> path = new ArrayList<>();
        if (target == source) {
            path.add(source);
            return path;
        }
        if (parentEdge[target] == -1) {
            return path; // unreachable
        }
        int v = target;
        path.add(v);
        while (v != source) {
            v = edges[parentEdge[v]][0];
            path.add(v);
        }
        Collections.reverse(path);
        return path;
    }
}
