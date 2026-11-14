# Benchmark qualification

Whether the Phase 2 gameplay suite measures what it claims, whether its statistics are sound, and
where it must not be trusted. The suite itself is documented in
[benchmark-suite.md](../benchmark-suite.md); the Phase 1 review of the older tools is in
[benchmark-assessment.md](benchmark-assessment.md).

## What was tested

The suite was run end to end on the audit machine against the `bench` profile:

| Run | Scenarios | Repeats | Result |
|---|---|---:|---|
| Smoke | `idle`, `mine_place`, `redstone`, `world_ops` | 1 | 4/4 valid |
| Targeted scaling | `entities_0`, `entities_100`, `redstone_medium` | 1 | 3/3 valid |
| World operations | `world_ops` (2 cold + 2 warm loads, RD 12) | 1 | valid; 637 generated columns, 8–14 s cold, 7 s warm |
| Memory soak | `memory_soak` (8 s in validation; 300 s is the tier-4 setting) | 1 | valid; slope measured, cleanup sampled |
| Instrumentation | `overhead` | 1 | valid; sampler cost +0.5% FPS |
| Trace qualification | `idle`, `entities_100`, `redstone_medium` with `--trace-dir` | 1 | valid; 22k–90k trace events, 9–31 MB each, bounded by `--trace-seconds` |
| Full baseline | ten core scenarios | 5 | 10/10 valid; report accepted by `horizon-bench validate` |
| Repeatability | the same ten scenarios and settings again | 5 | see [baseline.md](baseline.md) |
| Report self-comparison | `baseline` against itself | — | 0 confirmed regressions, 0 uncertain (all `neutral`) |
| Single-repeat strictness | the smoke report | — | `validate --strict` rejects “one repeat; a baseline needs at least two” |

The workload setup defects found and fixed during qualification were real: a creative inventory has
no crafting grid, a repeater's `facing` is its input side, a far column must be loaded before a
control can place against it, and `give` crosses the server thread. Those were scenario bugs, not
game bugs, and fixing them made the assertions meaningful.

## Method

- **Five repeats by default**, one game process per repeat and a fresh world each time. Scenarios
  therefore compare cold worlds, not five visits to one warmed world.
- **Explicit phases**: a 2 s warm-up hold whose frames are kept but whose metrics are not pooled, the
  8 s measured hold, then a 1 s cooldown. The measurement excludes the control round trips before and
  after it; raw frames expose the first/last-frame perturbation.
- **Alternating A/B** for a candidate build and `--baseline-build`: the two builds swap order every
  pass, so thermal/driver/background drift cannot systematically favour one.
- **Paired statistics** are per-metric over the per-repeat values: mean, median, sample SD, Student-t
  95% interval (absolute and relative), coefficient of variation and IQR. Outliers are listed by
  Tukey fences and never removed.
- **Noise-aware comparison**: a metric is a regression only when it is worse than the threshold and
  the combined 95% interval excludes zero. Over-threshold changes inside the noise, and any change
  with fewer than two repeats on either side, are `uncertain` and exit 0.
- **Correctness gates run before statistics are trusted**: a scenario with a failed assertion is
  invalid, and `horizon-bench validate` refuses it. Comparisons skip invalid scenarios? No: they
  print a warning and the report remains in the evidence set; CI runs the validator first.
- **Contamination is reported beside the numbers**: background CPU with the game's own cores
  subtracted, free memory, tick collapse and frame collapse. It never deletes a sample.
- **Instrumentation cost is measured**, not asserted: the `overhead` scenario pauses the process
  sampler for one identical hold and resumes it for the next.

## Measured reliability on this host

From the five-repeat baseline:

| Metric class | Coefficient of variation across repeats | Consequence |
|---|---|---|
| Average FPS | 28–109% | A bare FPS delta below ~30% is not attributable on this host; it is `uncertain`. |
| Frame CPU p50 | 3–15% (3% idle, 5.5% idle in the priority check) | The stable CPU signal; use it with ticks and RSS. |
| `tick.mspt` | 5–60% (most 9–21%) | Usable for gross regressions and for server-thread work; spikes are visible in `tick.mspt_max`. |
| RSS steady | 0.9–2.9% | Reliable; a leak or cache retention shows immediately. |
| World cold/warm load | 10–20% on this host | Directional only; the per-cycle values and generated counts are kept. |

The host runs the development application in the background (~35–45% of all CPUs), which is why the
windowed frame rate swings and why the reports contain three contaminated repeat entries. The
baseline is retained with those entries and `--contamination-cpu-pct 75` recorded in its conditions;
it is a qualified **reference for CPU, simulation and memory** on this machine, not a stable
absolute-FPS table. The background CPU is in every report, so a reader can see the condition.

Sampling cost: +0.5% FPS with the sampler on versus paused (one pair, 8 s holds). Process memory is
sampled twice a second, which is far below the noise it measures.

## Correctness coverage

Every core scenario asserts the work it measured, not only that time passed:

| Scenario | Assertions |
|---|---|
| idle | frames drawn, ticks advanced, tick rate plausible |
| walk | player moved > 3 blocks |
| explore | new terrain generated, chunks resident, frames drawn |
| mine_place | ≥ 6 placements and ≥ 6 breaks changed the block |
| crafting | result is oak planks, planks reached the inventory |
| combat | target health fell |
| redstone | piston extended and retracted, lamp lit and turned off, hopper transferred |
| entities | ≥ 80% of the requested mobs known to the client; `entities_0` has no summoned population |
| world_ops | every cold cycle generated terrain and reached full residency |
| mixed | > 10 actions, > 20 ticks, > 10 frames |
| redstone_<size> | every piston of 16/64/256 cells extended and retracted (2×cells transitions) |
| memory_soak | actions, frames, a measured slope, and a runaway bound (512 MB/min) |
| overhead | both sampler phases drew frames |

## Remaining limitations

- **Not a vanilla comparison.** The suite drives `horizon-ctl`; use `tools/perf_bench.py` for
  Horizon-versus-vanilla.
- **FPS on this host is GPU/compositor-limited.** Offscreen reduces but does not remove the variance;
  the renderer figures are diagnostic while CPU/tick/RSS are the comparable quantities.
- **gRPC/control perturbation** is outside the measured window but not zero. The raw frame stream and
  the overhead scenario bound it.
- **No allocation call sites or stacks in the suite.** The bounded trace names spans and threads; use
  a platform profiler for stacks ([profiling.md](profiling.md)).
- **Traces cover scenario setup too**, because a scenario owns its setup. The top spans include
  `control` from the suite's own commands; they are identifiable and excluded from the profiling
  conclusions. `--trace-repeat 0` and `--trace-seconds` bound the files.
- **High-density workloads are opt-in** (`--large`: 500–2,000 entities, 256 pistons). No run of them
  is claimed as measured here; the checks scale with the configured count, and the suite refuses the
  workload without the flag.
- **The repeatability comparison is on the same machine and the same shared-host condition**; it
  establishes run-to-run stability, not cross-machine portability.
