# Existing benchmark assessment

Audit of `tools/perf_bench.py`, `pacing_bench.py`, `graphics_bench.py`, `stress_scenes.py`,
`bench.py`, `build_times.py`, `docs/benchmark*.md`, `crates/horizon-bench` and the in-game
`--benchmark` driver. This is a code and methodology review; no benchmark was run by this audit
track. The new suite's implementation and results are in [benchmark-suite](../benchmark-suite.md).

## What is measured correctly (retain)

- **One statistics implementation for every game.** `tools/perf_bench.py:frames()` mirrors
  `horizon_bench::Frames::of`; same rounding, histogram edges, nearest-rank percentiles, and 1%/0.1%
  lows defined as the average frame time of the slowest x% as FPS. Raw frame streams are kept.
- **Fairness is enforced, not just recorded.** `perf_bench.py:table()` refuses a comparison unless
  scenario, seed, simulation distance, window, vsync, fps cap and offscreen match. `fps_cap` absent
  means unlimited.
- **Student-t confidence intervals**, repeats (3 by default), fresh world per run, recorded load
  average, and a warm-up start excluded from the measurement.
- **Input equivalence.** Vanilla and Horizon place the player on the same path every frame, with the
  same teleport, time, yaw and pitch.
- **Frame-time semantics match.** Both measure wall time between frame starts, including present and
  display waits.
- **CPU/GPU split.** Horizon reports frame CPU time (frame minus GPU/display/limiter waits), phase
  spans `update/tick/prepare/render`, and GPU timestamp queries. `slow_phases_avg_ms` attributes the
  slowest 1% of frames by CPU time.
- **`pacing_bench.py`** is the right complement: long stutter-prone sessions, over-33 ms and
  over-2×-median counts, `HORIZON_SPIKES` span lines on the slowest frames, frame caps/vsync, and
  scenario assertions (alive, flying, dimension changed).
- **Stress scenes** are built by the same vanilla commands in every game, held still, placed inside
  vanilla's entity render distance, and cleaned up deterministically.
- **Server benches** use each server's own `/tick query` MSPT, measure the whole process tree, and
  `server_bench.py` warns when a faster server got more terrain to generate.

## Gaps and misleading metrics

1. **Readiness clocks differ.** Horizon's `wait_loaded` requires no queued work, counts stable for
   1 s, resident chunks ≥ 80% of π·RD² and meshing quiet. Vanilla's driver requires only stable
   counts, all sections rendered and chunks within RD−1. `graphics_bench.py` uses `wait-ready`, which
   does not wait for the last sections to be lit/meshed at all, so graphics and perf numbers are not
   calibrated to each other.
2. **`streaming.protos` is ignored.** Generation work outside the view distance can remain queued
   while the game reports loaded; vanilla has no analogous ignore.
3. **No workload validation in perf_bench stress scenes.** If a game spawns 600 of 1000 mobs or the
   fill limit clips a wall, nothing fails. Horizon and vanilla also record different entity counters.
   A broken game can produce a beautiful FPS table. The new suite adds checks; `perf_bench.py` still
   needs them.
4. **`client_tick_ms` is not the same quantity on both sides.** Horizon scales a per-frame tick span
   by frames/tick; vanilla averages `Minecraft.tick` durations. A few percent can look like a tick
   regression. It is silently omitted when ticks == 0.
5. **CPU/GPU medians only.** `frames()` emits CPU/GPU p50 but not p99; a p99 frame with 2 ms CPU and
   60 ms wall is a GPU wait or limiter artifact. This audit added `cpu_p99_ms`, `gpu_p99_ms` and
   `gpu_wait_p50_ms` to the report format and both statistics implementations.
6. **GPU timestamp association can slip** under GPU backpressure: timestamps are drained once per
   frame and the last value is attributed to the current frame. Median GPU time on a saturated GPU
   can describe earlier frames.
7. **Memory semantics differ.** Windows uses working set, Linux/macOS use `ps` RSS; cross-OS memory
   tables are not comparable. 4 Hz sampling misses short peaks. GPU memory mixes NVIDIA per-process
   VRAM with Horizon's allocator total using `or`, so the source silently changes.
8. **Integrated-server tick cost is not in client benches.** Single player runs on the server thread;
   `perf_bench` captures only the client tick. `tick.mspt`/`tick.tps` remain "planned" in the report
   table. A server-thread regression shows up as diffuse FPS noise.
9. **Power/thermal and repeat-level conditions are incomplete.** `power_source()` exists and the
   in-game driver records it, but `perf_bench.py` does not; only the first repeat's pre-run load
   average reaches conditions.
10. **Repeat 0 is not separated.** Driver/pipeline caches make the first repeat colder on Horizon;
    for vanilla, JIT warm-up is intentionally kept. A/B runs starting from different cache states
    are biased.
11. **`wait_loaded` is duplicated** in Rust (`benchmark.rs`) and Python (`perf_bench.py`), including
    magic constants; only `view_chunks`/`yaw` have parity tests.
12. **Minor:** `graphics_bench.py` hardcodes a data version; `pacing_bench.stats()` does not filter
    non-finite values; `pacing_bench --compare` has no dispersion; `bench.py` TPS includes console
    latency and its CPU sampling needs `ps` (unavailable on Windows).

## Rendering vs simulation

The design separates them well: wall frame time, CPU frame time, phase spans, GPU timestamps, chunk
load time and client tick time. The blur points are the integrated server's invisible MSPT, the lack
of CPU/GPU p99, and `load_ms` mixing generation/network/meshing without a stage breakdown. FPS does
not hide spikes here: raw frames, p99.9/max, 1%/0.1% lows, histograms and pacing spans are all kept.
What FPS cannot show is *why* a frame was slow; the new `gpu_wait_p50_ms` and p99 fields help.

## Statistical validity

Means over repeats with sample SD and t-based 95% CIs are sound. n=3 gives very wide CIs for lows;
metric-level CIs are over per-repeat aggregates, which is correct for independent runs but noisy for
12 s flights. `suite.rs::compare` defaults to not requiring significance, so a 5% single-run delta is
flagged; the new suite documents this and offers `--require-significance`. There is no
multiple-comparison correction across dozens of metrics.

## Recommendations

1. Port the suite's `Check`/`valid()` gate to perf_bench stress scenes.
2. Add CPU/GPU p99 and GPU-wait metrics (started in this audit).
3. Make `graphics_bench.py` use the same strict readiness as `perf_bench.py`.
4. Record integrated-server MSPT in both client benches.
5. Align or explicitly caveat tick definitions across games.
6. Report GPU memory provenance as separate fields, never with `or`.
7. Extract the shared `wait_loaded` state machine and test both implementations against one fixture.
8. Record power and every repeat's load before/after.
9. Report repeat 0 separately or discard it for a cache-warm comparison.
10. Use one compare rule across pacing and the suite.
