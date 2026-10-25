import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Random;
 
public final class Bench {
    private static final int WARMUP = 3;
    private static final int RUNS = 7;
    private static final int[][] SIZES = {{1_000, 5_000}, {10_000, 50_000}, {100_000, 250_000}};
 
    private static Map<String, Object> request(String task, int n, List<Object> rows) {
        Map<String, Object> request = new java.util.HashMap<>();
        request.put("task", task);
        request.put("n", (long) n);
        request.put("edges", rows);
        return request;
    }
 
    private static int find(int[] p, int x) {
        while (p[x] != x) {
            p[x] = p[p[x]];
            x = p[x];
        }
        return x;
    }
 
    private static void verify(String who, int n, int[][] edges, Map<String, Object> r, long refCost, int refComps) {
        List<?> ids = (List<?>) r.get("edge_ids");
        int[] p = new int[n];
        for (int i = 0; i < n; i++) {
            p[i] = i;
        }
        long sum = 0;
        boolean[] used = new boolean[edges.length];
        for (Object o : ids) {
            int id = (Integer) o;
            if (used[id]) throw new IllegalStateException(who + ": repeated edge id");
            used[id] = true;
            int a = find(p, edges[id][0]);
            int b = find(p, edges[id][1]);
            if (a == b) throw new IllegalStateException(who + ": cycle or loop selected");
            p[a] = b;
            sum += edges[id][2];
        }
        if (ids.size() != n - refComps) throw new IllegalStateException(who + ": wrong forest size");
        if (sum != (Long) r.get("cost") || sum != refCost) throw new IllegalStateException(who + ": wrong cost");
        if ((Integer) r.get("components") != refComps) throw new IllegalStateException(who + ": wrong components");
    }
 
    private static double median(long[] nanos) {
        long[] copy = nanos.clone();
        Arrays.sort(copy);
        int mid = copy.length / 2;
        double value = copy.length % 2 == 1 ? copy[mid] : (copy[mid - 1] + copy[mid]) / 2.0;
        return value / 1e6;
    }
 
    public static void main(String[] args) {
        long seed = args.length > 0 ? Long.parseLong(args[0]) : 12345L;
        System.out.println("# Kruskal vs Prim benchmark");
        System.out.println();
        System.out.println("- seed: " + seed + " (graph for size i uses new Random(seed + i): random endpoints, weights in [-1e9, 1e9], loops and parallel edges possible)");
        System.out.println("- java.version: " + System.getProperty("java.version") + ", vm: " + System.getProperty("java.vm.name"));
        System.out.println("- os: " + System.getProperty("os.name") + " " + System.getProperty("os.version") + " " + System.getProperty("os.arch")
                + ", logical processors: " + Runtime.getRuntime().availableProcessors()
                + ", max heap MB: " + Runtime.getRuntime().maxMemory() / (1024 * 1024));
        System.out.println("- timer: System.nanoTime(); warm-up: " + WARMUP + " untimed runs per method and size; measured runs: " + RUNS + " per method and size, alternating Kruskal/Prim");
        System.out.println("- boundary: one Algorithms.<method>(request) call = Input.edges conversion + algorithm + result map; excludes compilation, graph generation, JSON parsing and output");
        System.out.println("- CPU model / RAM: fill in manually from your machine");
        System.out.println();
        System.out.println("| n | m | method | cost (verified) | components | runs ms (in order) | median ms |");
        System.out.println("|---|---|---|---|---|---|---|");
 
        for (int s = 0; s < SIZES.length; s++) {
            int n = SIZES[s][0];
            int m = SIZES[s][1];
            Random rng = new Random(seed + s);
            int[][] edges = new int[m][];
            List<Object> rows = new ArrayList<>(m);
            for (int i = 0; i < m; i++) {
                int u = rng.nextInt(n);
                int v = rng.nextInt(n);
                int w = rng.nextInt(2_000_000_001) - 1_000_000_000;
                edges[i] = new int[] {u, v, w};
                rows.add(new ArrayList<Object>(Arrays.asList((long) u, (long) v, (long) w)));
            }
            Map<String, Object> kReq = request("kruskal", n, rows);
            Map<String, Object> pReq = request("prim", n, rows);
 
            Map<String, Object> kRes = Algorithms.kruskal(kReq);
            Map<String, Object> pRes = Algorithms.prim(pReq);
            long cost = (Long) kRes.get("cost");
            int comps = (Integer) kRes.get("components");
            verify("kruskal", n, edges, kRes, cost, comps);
            verify("prim", n, edges, pRes, cost, comps);
 
            for (int i = 1; i < WARMUP; i++) {
                Algorithms.kruskal(kReq);
                Algorithms.prim(pReq);
            }
            long[] kt = new long[RUNS];
            long[] pt = new long[RUNS];
            for (int i = 0; i < RUNS; i++) {
                long t0 = System.nanoTime();
                Algorithms.kruskal(kReq);
                kt[i] = System.nanoTime() - t0;
                t0 = System.nanoTime();
                Algorithms.prim(pReq);
                pt[i] = System.nanoTime() - t0;
            }
            System.out.printf("| %d | %d | Kruskal | %d | %d | %s | %.2f |%n", n, m, cost, comps, fmt(kt), median(kt));
            System.out.printf("| %d | %d | Prim | %d | %d | %s | %.2f |%n", n, m, cost, comps, fmt(pt), median(pt));
        }
    }
 
    private static String fmt(long[] nanos) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < nanos.length; i++) {
            if (i > 0) sb.append(", ");
            sb.append(String.format("%.2f", nanos[i] / 1e6));
        }
        return sb.toString();
    }
}
 
