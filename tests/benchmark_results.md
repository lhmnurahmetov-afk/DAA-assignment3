# Kruskal vs Prim benchmark

- seed: 12345 (graph for size i uses new Random(seed + i): random endpoints, weights in [-1e9, 1e9], loops and parallel edges possible)
- java.version: 27, vm: OpenJDK 64-Bit Server VM
- os: Mac OS X 26.2 aarch64, logical processors: 8, max heap MB: 4096
- timer: System.nanoTime(); warm-up: 3 untimed runs per method and size; measured runs: 7 per method and size, alternating Kruskal/Prim
- boundary: one Algorithms.<method>(request) call = Input.edges conversion + algorithm + result map; excludes compilation, graph generation, JSON parsing and output
- CPU model / RAM: Apple M2, 16 GB (17179869184 bytes)

| n | m | method | cost (verified) | components | runs ms (in order) | median ms |
|---|---|---|---|---|---|---|
| 1000 | 5000 | Kruskal | -757096851848 | 1 | 1.26, 1.63, 1.04, 0.83, 0.69, 0.52, 0.46 | 0.83 |
| 1000 | 5000 | Prim | -757096851848 | 1 | 3.03, 1.60, 1.64, 2.07, 1.35, 1.32, 2.16 | 1.64 |
| 10000 | 50000 | Kruskal | -7573932896537 | 1 | 5.12, 5.11, 4.49, 4.06, 3.96, 4.39, 3.96 | 4.39 |
| 10000 | 50000 | Prim | -7573932896537 | 1 | 22.09, 22.90, 22.75, 21.54, 21.34, 21.54, 20.63 | 21.54 |
| 100000 | 250000 | Kruskal | -52905653145057 | 694 | 32.20, 31.74, 32.63, 31.93, 31.37, 31.15, 32.30 | 31.93 |
| 100000 | 250000 | Prim | -52905653145057 | 694 | 130.55, 128.35, 134.13, 135.89, 130.18, 135.67, 129.35 | 130.55 |
