# Gameplay benchmark suite

`tools/gameplay_bench.py` measures the work `tools/perf_bench.py` does not: a live player walking,
mining, crafting, fighting, and running redstone, entity-heavy, world-loading and soak workloads. It
drives the real game through `horizon-ctl`'s control protocol and writes a
`horizon-benchmark-suite` version 2 JSON report with raw samples, per-repeat details, statistics,
contamination findings and explicit correctness checks. Version 1 files still parse; version 2 adds
`stats`, `runs`, `contamination` and the comparison verdict. It complements the flight/startup
benchmark; it does not replace it.

The suite is qualified in [the audit](audit/benchmark-qualification.md); the first measured
multi-repeat baseline is [there too](audit/baseline.md).

## What one pass does

1. Starts one game with a fresh scratch game folder (a fresh world), audio off, telemetry off, a
   fixed seed and a fixed window/render distance. The player's saves, options, logs and caches are
   never touched.
2. Creates the world `GameplayBench`, waits for the spawn chunks, and for each selected scenario:
   clears any leftover screen, performs the real controls (`move`, `tp`, `place`, `break`, `give`,
   `click-slot`, `attack`, `setblock`, `container`, `summon`, `fly`), then measures a stationary hold
   with **warm-up**, **measurement** and **cooldown** phases.
3. Records the scenario's checks. A workload that could not run is invalid and stays in the report;
   later scenarios still run.
4. Cleans up between scenarios (screen closed, non-player entities killed, weather/time reset), so a
   dense-entity scenario cannot bias the next one.

The default is **five measured passes** (`--repeats`, configurable). Each pass relaunches the game,
so every repeat sees a cold world and empty caches; within a pass the scenarios share one world, as
in one player's session.

### Phases

`hold()` always runs:

| Phase | What happens | What is kept |
|---|---|---|
| warm-up (`--warmup-seconds`, 2 s) | the same camera and world, no polling | `Frames` with phase `warmup`; no metrics |
| measurement (`--seconds`, 8 s) | the same hold, frame statistics reset by the game | all metrics, raw samples, frame distribution |
| cooldown (`--cooldown-seconds`, 1 s) | no polling; limiter/allocator settle | nothing (the next scenario starts clean) |

`explore`, `world_ops` and `mixed` measure their own action windows instead of a stationary hold;
they use the same phases around and after the action.

## Scenarios

| Name | What it does | What is asserted |
|---|---|---|
| `idle` | Stationary camera at spawn. | Frames drawn, ticks advanced, tick rate plausible. |
| `walk` | Sprint forward for 2 s on a controlled platform. | The player moved more than 3 blocks. |
| `explore` | Fly 512 blocks at 10 blocks/s over fresh terrain. | New chunks generated, chunks resident, frames drawn. |
| `mine_place` | Place and break 8 stone blocks on a platform. | At least 6 placements and 6 breaks changed the block. |
| `crafting` | Survival 2×2 grid, oak log in, shift-click the result. | Output is oak planks and planks reached the inventory. |
| `combat` | Summon a zombie, face it and attack until it is hurt. | The target's health fell. |
| `redstone` | Piston, repeater/lamp and hopper/chest circuits. | Piston extends/retracts, lamp lights/turns off, hopper transfers an item. |
| `entities` | `--mobs` still, no-AI mobs in view (200 by default). | The client knows at least 80% of them. |
| `world_ops` | `--world-ops-cycles` (4) teleports to fresh terrain, each revisited warm. | Every cycle generated terrain and kept chunks resident; cold/warm load times and generated/meshed counts are sampled. |
| `mixed` | Teleports, mining, placing, inventory and combat for `--soak-seconds`. | Actions completed, ticks advanced, frames drawn; RSS slope reported. |

### Scaling workloads (opt-in)

| Flag | Workload | Names |
|---|---|---|
| `--entity-counts 0,100,250,500,1000,2000` | Fixed entity populations, each spawned and counted. Above 250 requires `--large`. | `entities_<n>` |
| `--redstone-sizes small,medium,large,extreme` | Piston-cell buses of 1/16/64/256 cells driven from one source. Every piston must extend and retract. `extreme` requires `--large`. | `redstone` (small), `redstone_<size>` |
| `--render-matrix` | Adds `render` for every configuration. | `render@<W>x<H>rd<D>` |
| `--resolutions 1280x720,1920x1080` | One pass per window size (a relaunch, because the window is a startup flag). | suffix `@<W>x<H>rd<D>` |
| `--render-distances 8,12,16` | One pass per render distance. | suffix `@<W>x<H>rd<D>` |
| `--include memory_soak` | Extended mixed gameplay with chunk turnover, a settle and a cleanup sample. | `memory_soak` |
| `--include overhead` | The same hold with the process sampler paused and running. | `overhead` |

Large workloads are opt-in (`--large`) because 2,000 entities or 256 pistons need a machine that can
run them; a run that cannot is invalid rather than fast. `--scenarios all` adds every opt-in
scenario, but the default run stays the ten core scenarios.

### Alternating baseline and candidate

`--baseline-build DIR` runs a second build beside `--build`, alternating their order on every pass
(candidate-first, then baseline-first, then candidate-first...), and writes both reports plus a
comparison. This is the paired design: slow drift over a session (thermal, driver, background work)
hits both sides, and the order effect is balanced.

```sh
python3 tools/gameplay_bench.py --build target/release --baseline-build target/previous \
    --repeats 5 --label pair
```

## Metrics

Every scenario stores raw samples, per-repeat detail (`runs`), and statistics derived from the raw
values:

- `render.avg_fps`, `render.low_1pct_fps`, `render.low_01pct_fps`
- `render.p50_ms`, `p95_ms`, `p99_ms`, `p999_ms`, `max_ms`
- `render.cpu_p50_ms`, `cpu_p99_ms`, `gpu_p50_ms`, `gpu_p99_ms`, `gpu_wait_p50_ms`
- `cpu.phase_<update|tick|prepare|render>_ms` and `cpu.slow_phase_*_ms` (the renderer's phase spans
  inside a frame, and where the slowest 1% of CPU frames went)
- `tick.tps` (wall-clock ticks per second), `tick.mspt` (the game's smoothed server tick time),
  `tick.mspt_max`, and `tick.client_ms` where a flight measured it
- `process.rss_peak_mb`, `rss_steady_mb`, `private_peak_mb`, `private_steady_mb`,
  `virtual_peak_mb`, `virtual_steady_mb`, `cpu_cores_used`, `cpu_seconds`, `threads_peak`
- `memory.rss_slope_mb_per_min`, `rss_base_mb`, `rss_peak_mb`, `rss_retained_mb`,
  `rss_growth_mb`, `rss_after_cleanup_mb`
- scenario-specific counts (`play.distance_blocks`, `play.placed`, `play.oak_planks`,
  `combat.health_after`, `redstone.cells`/`extended`/`retracted`/`state_transitions`,
  `world.cold_load_ms`/`warm_load_ms`/`generated_chunks`, …)
- `overhead.sampler_cost_pct` in the overhead scenario.

Resident memory is the working set (Task Manager's view) on Windows and RSS on Unix; private/commit
and virtual are reported separately, never merged. Frame figures use the same definitions, rounding
and histogram edges as [the benchmark report format](benchmark-report.md).

### Statistics, outliers and noise

`summary()` gives n, mean, median, sample SD, min/max, the Student-t 95% interval (absolute and
percent of the mean), coefficient of variation and the interquartile range. Outliers are reported by
Tukey's 1.5×IQR fences **without deleting them**; with fewer than four samples the fences have no
meaning and none is reported. A pooled mean is never stored without its raw values.

`--compare` (and `horizon-bench compare`) classify each metric:

| Verdict | Meaning |
|---|---|
| `regression` | Worse than the threshold **and** the difference clears the combined 95% interval. |
| `improvement` | Better than the threshold and clears the interval. |
| `uncertain` | Over the threshold but inside the noise, or too few repeats (fewer than two on either side). Never a failure. |
| `neutral` | Inside the threshold. |

`--require-significance` is accepted for compatibility; it never turns an uncertain change into a
failure. A single-run historical baseline therefore reports `uncertain`, not a regression.

## Metadata and contamination

Each report records the commit and dirty flag, profile name, rustc/cargo/target, Python version, the
binary's size, mtime and SHA-256, the command line, the machine (OS, CPU, physical/logical cores,
RAM), GPU and driver, display, window, render distance, seed, repeats, phase lengths, sampler period
and the load/memory snapshot before and after.

A measurement is **contaminated** (reported, not deleted) when the machine was more than 15% busy or
short of memory before/after the scenario, when the tick rate collapsed below 15 TPS, or when the
frame rate fell below 5 FPS. Correctness can still pass; `horizon-bench validate --strict` refuses a
contaminated run as a baseline or comparison side. This is how a background game or a Windows update
is kept from becoming a "regression".

`--trace-dir DIR` writes one bounded Chrome trace per selected scenario and `--trace-repeat` (default
the first repeat) through the game's `trace` command, and stores the top spans (name, thread, count,
wall and max time) in the scenario's `profile`. `--trace-seconds` bounds each file; nothing is traced
for other repeats. `tools/startup_trace.py` and `HORIZON_SPIKES` remain the startup and slow-frame
tools.

`--raw-frames DIR` keeps the per-frame streams as JSONL, bounded by the frames actually taken.
Reports themselves always keep raw scalar samples, per-repeat samples and per-scenario frame
distributions.

## Reproduce the baseline

```sh
python3 tools/cargo_build.py --profile bench
python3 tools/gameplay_bench.py --build target/release --render-distance 12 \
    --repeats 5 --label baseline-$(git rev-parse --short HEAD)
```

The qualified baseline is `benchmarks/gameplay/baseline-qualified.json` (see
[the audit baseline](audit/baseline.md) for provenance and the numbers). Compare against it with:

```sh
./target/release/horizon-bench compare benchmarks/gameplay/baseline-qualified.json \
    benchmarks/gameplay/<new>.json --threshold 5 --require-significance
```

## Tiers

`tools/bench_tiers.py` is the front door; [the audit](audit/README.md) records what was run here.

| Tier | What runs | When |
|---|---|---|
| 1 | rustfmt, Clippy on `horizon-bench`, its tests, the Python statistics/schema tests | every change that touches the suite |
| 2 | the smoke gameplay scenarios (`idle`, `mine_place`, `redstone`, `world_ops`) plus workload assertions | integration, CI nightly |
| 3 | repeated gameplay (`--repeats 3`), entity scaling 0/100/250, redstone sizes and render distances 8/12, compared with the approved baseline | performance, CI nightly/manual |
| 4 | long soak, 500–2,000 entities, extreme redstone, two resolutions, traces | release candidates, manual |

```sh
python3 tools/bench_tiers.py --tier 1
python3 tools/bench_tiers.py --tier 2 --build target/release
python3 tools/bench_tiers.py --tier 3 --build target/release
python3 tools/bench_tiers.py --tier 4 --large
python3 tools/bench_tiers.py --tier 3 --dry-run
```

`.github/workflows/bench.yml` runs tier 1 on pull requests that touch the suite and tiers 2–4 on the
repository's game runner (nightly tier 3, manual 2/3/4). Performance tiers never fail on an
`uncertain` verdict.

## Limits

- This is not a vanilla comparison. Use `tools/perf_bench.py` for Horizon vs vanilla 26.3; that
  tool owns the shared world, options and camera paths. The suite's scenarios drive `horizon-ctl`
  and are Horizon-only.
- `tick.mspt` comes from the game's smoothed server tick, not an external tick counter. `tick.tps`
  is computed from the `ticks` field over the measured wall time, so a stalled client can undercount
  it. Both are reported so an inconsistent pair is visible.
- The stationary hold has a control round trip before and after it; that overhead is outside the
  frame window but the two status calls perturb the first/last frames slightly. Raw samples make it
  visible; the `overhead` scenario measures the sampler itself.
- GPU memory is not reported here; `tools/perf_bench.py` and the in-game `--benchmark` cover the
  renderer's allocator and vendor counters.
- Scenario setup uses cheats (creative, `setblock`, `summon`, `clear`). The measured actions are
  ordinary controls, but this is a controlled workload, not a survival session.
- A machine that is busy, on battery, thermally throttled or using a software renderer produces
  numbers that are not comparable to the baseline. Contamination detects busy and memory-starved
  runs, not a quiet thermal decline; record the machine state in the report.
- Traces name timed spans, not call stacks. For stacks and allocation sites use the platform
  profiler named in [profiling.md](audit/profiling.md); the suite keeps the evidence bounded.
