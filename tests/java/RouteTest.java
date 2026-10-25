import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
 
public final class RouteTest {
    private static int failures = 0;
 
    private static List<Object> row(int... values) {
        List<Object> list = new ArrayList<>();
        for (int v : values) {
            list.add((long) v);
        }
        return list;
    }
 
    private static Map<String, Object> request(int n, int source, int[][] edges) {
        List<Object> rows = new ArrayList<>();
        for (int[] e : edges) {
            rows.add(row(e));
        }
        Map<String, Object> request = new java.util.HashMap<>();
        request.put("n", (long) n);
        request.put("source", (long) source);
        request.put("edges", rows);
        return request;
    }
 
    
    private static void check(String name, int n, int source, int[][] edges, int target, boolean reachable) {
        Map<String, Object> result = Algorithms.dag(request(n, source, edges));
        List<?> parents = (List<?>) result.get("parent_edge");
        List<?> distances = (List<?>) result.get("distance");
        int[] parentEdge = new int[n];
        for (int i = 0; i < n; i++) {
            parentEdge[i] = (Integer) parents.get(i);
        }
 
        List<Integer> route = Algorithms.route(source, target, parentEdge, edges);
        List<Integer> edgeIds = new ArrayList<>();
        long weight = 0;
        boolean ok = true;
 
        if (!reachable) {
            ok = route.isEmpty() && distances.get(target) == null;
        } else {
            ok = !route.isEmpty() && route.get(0) == source && route.get(route.size() - 1) == target;
            for (int i = 0; ok && i + 1 < route.size(); i++) {
                int to = route.get(i + 1);
                int id = parentEdge[to];     
                edgeIds.add(id);
                ok = edges[id][0] == route.get(i) && edges[id][1] == to; 
                weight += edges[id][2];
            }
            ok = ok && weight == (Long) distances.get(target);        
        }
        if (!ok) {
            failures++;
        }
        System.out.printf("%-28s target=%d route=%s edge_ids=%s weight=%s distance=%s %s%n",
                name, target, route, edgeIds, reachable ? String.valueOf(weight) : "-",
                distances.get(target), ok ? "OK" : "FAILED");
    }
 
    public static void main(String[] args) {
        int[][] spec = {{0, 1, 3}, {0, 2, 8}, {1, 2, -7}, {2, 3, 4}};
        check("spec reachable target", 5, 0, spec, 3, true);
        check("spec route to source", 5, 0, spec, 0, true);
        check("spec unreachable target", 5, 0, spec, 4, false);
 
        int[][] ties = {{0, 1, 2}, {0, 1, 2}, {1, 2, 1}, {0, 2, 3}};
        check("tied/parallel target 1", 3, 0, ties, 1, true);
        check("tied/parallel target 2", 3, 0, ties, 2, true);
 
        int[][] negative = {{0, 1, -1}, {1, 2, -1}, {0, 2, 5}};
        check("negative weights target 2", 3, 0, negative, 2, true);
 
        int[][] middle = {{0, 1, 1}, {2, 3, 4}, {1, 2, 1}};
        check("source in the middle: 3", 4, 2, middle, 3, true);
        check("source in the middle: 0", 4, 2, middle, 0, false);
 
        System.out.println(failures == 0 ? "ALL ROUTE TESTS PASSED" : failures + " ROUTE TEST(S) FAILED");
        System.exit(failures == 0 ? 0 : 1);
    }
}
 
