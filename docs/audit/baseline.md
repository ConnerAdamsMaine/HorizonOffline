# Qualified gameplay baseline (Phase 2)

Five repeats of the ten core scenarios against the production-equivalent `bench` build, on the
machine available to Phase 2, with the suite's correctness checks, raw samples and statistics. This
is the comparison baseline for future work **on comparable hardware**; it is not a public
performance claim and its absolute frame rates are limited by a shared host.

## Provenance

| Field | Value |
|---|---|
| Commit | `eb1e54725ce50aa42c4dc0f585a73db95786367a` (`main`) plus the Phase 1/2 working tree (`dirty: true`) |
| Binary | `target/release/horizon-client.exe`, 102,137,856 B, SHA-256 `bf934eb69325b109f9ad67458162f0c6503b1f35f3279b5e528faa9a9b1def61` |
| Profile | `bench` (Thin LTO, 4 codegen units, line tables; Cargo writes it to `target/release`) |
| Toolchain | `rustc 1.100.0-nightly (f7575a9da 2026-09-24)`, host `x86_64-pc-windows-msvc` |
| Python | 3.15.2 |
| Machine | Windows 10.0.19045, Intel Core i7-8700 (6C/12T), 48,866 MiB |
| GPU | NVIDIA Quadro P2000, Vulkan, driver 582.78; display 1920×1080, 60 Hz |
| Conditions | window 1280×720, render distance 12, simulation distance 12, seed 1234, VSync off, FPS cap 260, creative, high process priority |
| Phases | 2 s warm-up, 8 s measurement, 1 s cooldown; `world_ops` 4 cold + 4 warm loads; `mixed` 20 s |
| Repeats | 5, each pass a fresh game process and fresh world |
| Contamination limit | 75% other CPU, 1024 MiB free (see limits) |
| Raw results | `benchmarks/gameplay/baseline-qualified.json` (505 KB) and `.md` |
| Run window | 2026-11-13 06:26–06:48 UTC |
| Command | `python3 tools/gameplay_bench.py --build target/release --profile-name bench --repeats 5 --seconds 8 --warmup-seconds 2 --cooldown-seconds 1 --render-distance 12 --label baseline-phase2 --out benchmarks/gameplay/baseline-qualified.json --contamination-cpu-pct 75` |

The `profile` field was corrected from the output-folder name (`release`) to the Cargo profile
(`bench`) after the run; `run.build_dir` records the folder. No measurement was changed.

## Results (mean ± 95% Student-t interval over 5 repeats)

All ten scenarios are valid and every correctness check passed (30 assertions in total).

| Scenario | Valid | Checks | Avg FPS | 1% low | p99 ms | CPU p50 ms | tick mspt | TPS | RSS MB | Private MB | Virtual MB | Cores |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| idle | yes | 3/3 | 180.1 ±214.0 | 101.9 ±81.6 | 13.1 ±8.9 | 1.5 ±0.5 | 7.1 ±2.8 | 20.0 ±0.1 | 772.0 ±16.7 | 1766 ±28 | 7787 ±44 | 0.8 ±0.6 |
| walk | yes | 1/1 | 255.2 ±185.7 | 92.7 ±33.9 | 10.7 ±3.5 | 1.0 ±0.4 | 5.6 ±0.7 | 20.0 ±0.0 | 815.9 ±10.6 | 1820 ±10 | 7801 ±50 | 0.5 ±0.2 |
| explore | yes | 3/3 | 234.8 ±45.0 | 67.5 ±14.4 | 10.3 ±1.2 | 1.0 ±0.3 | — | — | 860.2 ±11.2 | 2030 ±9 | 7956 ±24 | 2.9 ±0.4 |
| mine_place | yes | 2/2 | 247.0 ±124.3 | 105.5 ±8.9 | 9.2 ±0.9 | 1.1 ±0.4 | 5.2 ±0.8 | 20.1 ±0.0 | 858.5 ±12.9 | 2067 ±20 | 7946 ±39 | 0.6 ±0.2 |
| crafting | yes | 2/2 | 198.9 ±101.9 | 99.4 ±9.5 | 9.9 ±1.0 | 1.2 ±0.5 | 3.6 ±1.1 | 20.1 ±0.1 | 866.8 ±19.8 | 2026 ±20 | 7985 ±34 | 0.5 ±0.2 |
| combat | yes | 1/1 | 278.6 ±156.0 | 100.4 ±13.9 | 9.4 ±1.0 | 1.2 ±0.5 | 3.7 ±0.4 | 20.1 ±0.0 | 874.8 ±14.2 | 2023 ±22 | 7988 ±33 | 0.6 ±0.1 |
| redstone | yes | 5/5 | 244.4 ±87.6 | 97.1 ±6.7 | 9.9 ±0.7 | 1.1 ±0.3 | 3.4 ±0.9 | 20.1 ±0.0 | 876.1 ±14.7 | 2042 ±18 | 7977 ±37 | 0.5 ±0.1 |
| entities (200) | yes | 2/2 | 111.9 ±51.4 | 65.8 ±4.6 | 14.9 ±0.9 | 2.3 ±0.8 | 4.6 ±1.1 | 20.0 ±0.0 | 880.5 ±14.3 | 1990 ±41 | 7964 ±33 | 0.4 ±0.1 |
| world_ops | yes | 8/8 | 291.3 ±77.7 | 105.5 ±16.2 | 7.7 ±0.6 | 0.8 ±0.2 | 5.0 ±0.5 | 20.0 ±0.1 | 912.3 ±11.3 | 1960 ±75 | 7885 ±96 | 0.7 ±0.2 |
| mixed (20 s) | yes | 3/3 | 146.3 ±107.2 | 38.3 ±16.5 | 24.6 ±13.3 | 1.4 ±0.4 | — | 20.0 ±0.0 | 917.6 ±14.6 | 2010 ±37 | 7898 ±69 | 0.4 ±0.2 |

World operations, measured per repeat (n = 20 cold and 20 warm loads):

| Metric | Mean | 95% CI | CV |
|---|---:|---:|---:|
| cold load | 6,865 ms | ±755 | 23.5% |
| warm revisit | 6,795 ms | ±315 | 9.9% |
| cold generated columns | 637 | 0 | 0% |
| cold meshed sections | 16,414 | ±676 | 8.8% |
| warm/cold speedup | 1.01× | ±0.15 | 12.0% |

The cold and warm waits both require the view to settle, so at RD 12 on this host the revisit does
not yet show a cache benefit; the metric is retained as a workload and as a check that a revisit is
not slower. The generated/meshed counts are deterministic (637 columns every time).

## How to read it

- **FPS is noisy on this host; CPU/tick/memory are not.** FPS CV is 15–96%; frame CPU p50 CV is
  15–36%, `tick.mspt` 8–32%, and steady RSS 1.0–1.8%. The wide FPS intervals are honest: a bare
  average-FPS change below ~30% is not attributable on this machine. Use the CPU p50, `tick.mspt`,
  `tick.mspt_max`, RSS/private/virtual and the workload counts for engineering decisions.
- **The game is present-bound, not CPU-bound, in the windowed build.** The trace shows
  `r_acquire` at 75–91% of the main-thread `renderer` span on this GPU. That is the machine, not a
  regression; offscreen reduces it ([profiling.md](profiling.md)).
- **RSS grows from ~772 MB to ~918 MB and plateaus.** Chunk, section and mesh caches are retained by
  design; a leak needs the 300 s `memory_soak` and its slope, not a single scenario.
- **Contamination was measured, not hidden.** The machine runs the development application in the
  background. The report records `crafting` repeat 4 and `combat` repeat 4 as contaminated (>75%
  other CPU); raw samples and CPU snapshots remain. The baseline is validated (`horizon-bench
  validate`), but `validate --strict` refuses it as comparison-grade because of those two entries.
  The 75% limit is recorded in `conditions.contamination_cpu_pct`; a quiet machine's default is 20%.
- **Virtual memory is not RSS.** `virtual` (~7.9 GB) is address space/reservation; `private` (~2 GB)
  is commit; `rss` (~0.8–0.9 GB) is resident. The final baseline uses the corrected sampler; an
  earlier repeat run in `baseline-repeat.json` predates that correction and its `virtual` fields are
  the old aliased values (do not compare them).

## Repeatability

An independent five-repeat run with the same binary and settings covered the five scenarios that
span the range (`idle,walk,entities,redstone,mixed`) and is stored as
`benchmarks/gameplay/baseline-repeat.json`. The comparison uses the suite rule: worse by >5% **and**
clearing the combined 95% interval. Across 181 common metrics:

| Verdict | Count |
|---|---:|
| confirmed regression | 7 |
| uncertain | 97 |
| neutral | 60 |
| improvement | 17 |

All seven confirmed regressions were CPU/tick figures in `redstone` and `mixed`
(`process.cpu_cores_used`, `process.cpu_seconds`, `tick.client_ms`, `tick.mspt`,
`tick.mspt_max`); the `redstone` run also recorded one contaminated repeat at 82% background CPU.
There was **no confirmed regression** in frame time, RSS, private/virtual memory, world counts or
any correctness check. An earlier full-ten-scenario A/B pair (before the virtual-memory correction)
produced 1 confirmed regression in 368 metrics with 208 uncertain.

The headline is the noise-aware design working: two runs of the *same binary* on this shared host
can move CPU/tick figures by 30–60% with intervals that barely clear zero, and FPS by far more. A
change should be claimed only from a paired `--baseline-build` run, or from a run on a quiet machine
with the default 20% contamination limit — not from a single absolute comparison.

## Reproduce and compare

```sh
python3 tools/cargo_build.py --profile bench
python3 tools/gameplay_bench.py --build target/release --profile-name bench --repeats 5 \
    --seconds 8 --warmup-seconds 2 --cooldown-seconds 1 --render-distance 12 \
    --label baseline-phase2 --out benchmarks/gameplay/baseline-qualified.json
./target/release/horizon-bench compare benchmarks/gameplay/baseline-qualified.json \
    <new-report>.json --threshold 5 --require-significance
```

A candidate build compared with a previous build should use `--baseline-build` so the two alternate
and the comparison is paired:

```sh
python3 tools/gameplay_bench.py --build target/release --baseline-build target/previous \
    --repeats 5 --label pair
```
