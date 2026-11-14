# CPU, memory, rendering and simulation profiling

This is what the Phase 2 suite measured, not a source-code opinion. Every number comes from a
machine-readable report in `benchmarks/gameplay/` or from the bounded Chrome traces the suite wrote
under `.local/traces/` (not committed). The host was shared with the development application; see
[the baseline](baseline.md) for the qualification limits.

## Instrumentation that exists

| Signal | Where it comes from | Unit / meaning |
|---|---|---|
| Frame wall distribution | game frame statistics, `Frames` | avg FPS, 1%/0.1% low, p50/p95/p99/p99.9/max, fixed histograms |
| Frame CPU/GPU split | renderer timestamp queries and frame spans | `cpu_p50/p99_ms`, `gpu_p50/p99_ms`, `gpu_wait_p50_ms` |
| Phase CPU time | renderer `phases_avg_ms` and `slow_phases_avg_ms` | update, tick, prepare, render; slowest 1% of CPU frames |
| Simulation | integrated server thread | smoothed `tick.mspt`, `tick.mspt_max`, `tick.tps`, per-tick spans |
| Named spans per thread | `spans::trace` / `HORIZON_TRACE`, `HORIZON_SPIKES` | wall (and CPU for spikes) ms, thread, nesting; Perfetto-compatible |
| Resident memory | working set on Windows, RSS on Unix | `process.rss_*` |
| Private/commit and virtual memory | `PROCESS_MEMORY_COUNTERS_EX` via `NtQueryInformationProcess`, `/proc/<pid>/status` | `process.private_*`, `process.virtual_*` |
| CPU time and cores | `GetProcessTimes`, `ps` | `process.cpu_seconds`, `process.cpu_cores_used` |
| Threads | process sampler where the OS allows it; trace thread names | `process.threads_peak`, `profile.trace.threads` |
| Leak trend | least-squares RSS slope over the soak | `memory.rss_slope_mb_per_min` |
| Instrumentation cost | the `overhead` scenario pauses the sampler for one identical hold | `overhead.sampler_cost_pct` |
| Contamination | background CPU (game's own cores subtracted), free memory, tick collapse, frame collapse | `scenario.contamination` |

The table's source run is `benchmarks/gameplay/profile-final.json` (8 s traces, one repeat each,
final `bench` binary).

The suite does **not** collect allocation call sites or call stacks. Those need a platform profiler
(see the end of this page); the permanent instrumentation is cheap enough to leave on (the sampler
costs one `status`/`GetProcessMemoryInfo` pair per 0.5 s, measured by the `overhead` scenario).

## Frame and thread time

Bounded traces (8 s, `--trace-seconds 8`, one repeat each) on the final `bench` binary, on a
less-contended moment, split the render thread (`main`) and the integrated server thread. Per-call
wall time is the total divided by the calls, so a span's share of a 20 TPS tick (`mspt`) or a
1.2–1.6 ms frame is readable directly:

| Scene | Thread | Span | Calls | Total wall | Per call | Max |
|---|---|---|---:|---:|---:|---:|
| idle | main | `renderer` | 2,885 | 4,444.5 ms | 1.541 ms | 15.70 ms |
| idle | main | `r_acquire` | 2,885 | 866.1 ms | 0.300 ms | 14.92 ms |
| idle | main | `prepare` | 2,885 | 1,698.1 ms | 0.589 ms | 2.82 ms |
| idle | main | `encode` | 2,885 | 950.3 ms | 0.329 ms | 1.65 ms |
| idle | Server thread | `level_overworld` | 144 | 1,746.1 ms | 12.126 ms | 20.01 ms |
| idle | Server thread | `tick_mobs` | 144 | 799.7 ms | 5.554 ms | 10.05 ms |
| idle | Server thread | `tick_blocks` | 144 | 379.4 ms | 2.634 ms | 5.10 ms |
| idle | Server thread | `spawn_natural` | 144 | 134.8 ms | 0.936 ms | 1.92 ms |
| idle | Server thread | `streaming` | 144 | 114.3 ms | 0.794 ms | 3.06 ms |
| idle | Server thread | `tick_hud` | 144 | 3.3 ms | **0.023 ms** | 0.07 ms |
| 100 entities | main | `renderer` | 2,367 | 2,837.4 ms | 1.199 ms | 12.41 ms |
| 100 entities | main | `r_acquire` | 2,367 | 333.1 ms | 0.141 ms | 11.07 ms |
| 100 entities | main | `prepare` | 2,367 | 1,189.6 ms | 0.503 ms | 3.14 ms |
| 100 entities | Server thread | `level_overworld` | 159 | 1,226.7 ms | 7.715 ms | 27.04 ms |
| 100 entities | Server thread | `tick_mobs` | 160 | 320.7 ms | 2.004 ms | 5.01 ms |
| 100 entities | Server thread | `tick_blocks` | 160 | 245.3 ms | 1.533 ms | 7.74 ms |
| 100 entities | Server thread | `tick_items` | 161 | 212.0 ms | 1.317 ms | 3.87 ms |
| 100 entities | Server thread | `spawn_natural` | 160 | 205.1 ms | 1.282 ms | 2.99 ms |
| 16 pistons | main | `renderer` | 2,870 | 4,438.9 ms | 1.547 ms | 13.04 ms |
| 16 pistons | main | `r_acquire` | 2,870 | 1,641.9 ms | 0.572 ms | 12.29 ms |
| 16 pistons | Server thread | `level_overworld` | 160 | 1,246.5 ms | 7.791 ms | 28.90 ms |
| 16 pistons | Server thread | `tick_blocks` | 161 | 420.5 ms | 2.612 ms | 18.00 ms |
| 16 pistons | Server thread | `tick_mobs` | 160 | 277.2 ms | 1.733 ms | 8.24 ms |
| 16 pistons | Server thread | `spawn_natural` | 160 | 200.6 ms | 1.253 ms | 3.89 ms |

An earlier trace on the same machine while the development application was busy showed `r_acquire`
at 75–91% of `renderer` (2.7 s of 2.9 s in the idle trace): the render thread was waiting for the
GPU/desktop. That is a **host-contention** result, not a stable property of the renderer; the
less-contended trace above puts `r_acquire` at 6–37% of `renderer`. The benchmark reports record the
conditions (background CPU, contamination) so the two are not confused.

Two conclusions are safe at this sample size:

1. **Frame CPU is small and split across prepare/encode/entities.** On a quiet run `renderer` is
   ~1.2–1.6 ms/frame, with `prepare` ~0.45–0.59 ms, `encode` ~0.23–0.33 ms and entity preparation
   ~0.2 ms (100 entities). `r_acquire` ranges from 0.14 to 0.57 ms here and dominates when the
   desktop/GPU is contended.
2. **The integrated server is where code changes move the needle.** `level_overworld` costs
   7.7–12.1 ms/tick (15–24% of the 50 ms budget), of which mob AI is 1.7–5.6 ms, block ticks
   1.5–2.6 ms, natural spawning 0.9–1.3 ms and streaming 0.2–0.8 ms. The 16-piston bus raises
   `tick_blocks` to a 18 ms single-tick spike.

The audit's suspected per-tick cost of `held_name()` is **refuted by measurement**: `tick_hud`
(the span that contains it, plus the title/action-bar work) costs **0.014–0.023 ms per tick**, about
0.03–0.05% of a tick and far below the noise. No caching change was made. The same applies to
particle sprite `String` clones: the particle-heavy traces did not surface a particle span in the
top set, so interning stays a measured-backlog item rather than a speculative rewrite.

## Memory

Baseline medians per scenario (resident / private commit / virtual address space; the final
baseline distinguishes all three):

| Scenario | RSS MB | Private MB | Virtual MB | Cores used | Notes |
|---|---:|---:|---:|---:|---|
| idle | 772 | 1766 | 7787 | 0.8 | title/world transition already done |
| walk | 816 | 1820 | 7801 | 0.5 | |
| explore | 860 | 2030 | 7956 | 2.9 | terrain generation/meshing workers busy |
| mine_place | 859 | 2067 | 7946 | 0.6 | |
| crafting | 867 | 2026 | 7985 | 0.5 | |
| combat | 875 | 2023 | 7988 | 0.6 | |
| redstone | 876 | 2042 | 7977 | 0.5 | |
| entities (200) | 881 | 1990 | 7964 | 0.4 | still, no-AI mobs |
| world_ops | 912 | 1960 | 7885 | 0.7 | 4 cold + 4 warm loads |
| mixed (20 s) | 918 | 2010 | 7898 | 0.4 | slope +23.5 MB/min |

Resident memory grows about 150 MB from idle to the first heavy scenarios and then plateaus; it
does not return to the idle figure because chunk/section/mesh caches are retained, which is the
intended cache behavior. Private commit is ~1.8–2.1 GB and virtual address space ~7.8–8.0 GB:
the three are not interchangeable, and a working-set plateau does not by itself rule out a commit
leak. The 20 s mixed soak's +23.5 MB/min is the noisiest single sample (one point per
repeat, no long history); a 300 s `memory_soak` is the tool for a leak decision, and its checks fail
only above 512 MB/min. No evidence of a runaway process-lifetime cache was found in a normal
session; the per-root caches were still bounded because pack reloads and long sessions can create
distinct roots (see the audit findings).

## Rendering

Frame distributions come from `Frames` and are kept raw per repeat. On this host the FPS mean has a
coefficient of variation of 28–109% across five repeats, while frame CPU p50 varies by 3–15% and RSS
by 1–3%. The baseline report therefore publishes both; performance comparisons should treat the CPU
and simulation figures as the stable signal and a bare average-FPS delta as `uncertain` unless its
confidence interval clears noise. `--trace-dir` plus `--trace-repeat 0` keeps a trace to one bounded
file per selected scenario (8–30 MB for 10 s, capped by `--trace-seconds`), and only when asked.

## Limitations and what to use instead

- **No call stacks or allocation sites.** Use:
  - Windows: Visual Studio's Concurrency Visualizer / WPA (ETW) or Superluminal; capture the
    `horizon-client` process while running tier 3.
  - Linux: `perf record -g --call-graph dwarf` and `heaptrack`/`dhat` for allocations.
  - The game's `HORIZON_TRACE` and `HORIZON_SPIKES` for named spans without a profiler.
- **No per-thread CPU split without `psutil`.** The trace gives per-thread span wall time and thread
  names; process CPU is external and exact. Install `psutil` to get thread counts on Windows.
- **The shared host** adds scheduler stalls; contamination records them, and the `overhead` scenario
  proves the sampler is not the cause.
- **GPU timestamps** are drained once per frame; under backpressure a timestamp can describe a
  slightly earlier frame. `gpu_wait_p50_ms` is a diagnostic, not a per-frame pair.

## Reproduce

```sh
python3 tools/gameplay_bench.py --build target/release --repeats 1 \
    --scenarios idle,mine_place,redstone_large,entities_500,mixed \
    --trace-dir .local/traces --trace-seconds 10 --large \
    --out .local/profile.json --contamination-cpu-pct 90
python3 tools/gameplay_bench.py --include overhead,memory_soak --soak-seconds 300 \
    --build target/release --repeats 1 --out .local/soak.json
```

Then open the trace files in <https://ui.perfetto.dev>, or read `benchmarks/gameplay/profile-final.json`
(the report from the final binary; `scenarios[].profile.trace`) for the ranked span table. Raw traces
are not committed (bounded but tens of MB each); the report keeps their summary.
