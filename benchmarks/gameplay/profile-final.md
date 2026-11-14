# Gameplay benchmark: trace-final

- Commit: `eb1e54725ce50aa42c4dc0f585a73db95786367a` (dirty)
- Profile: `bench`; rustc 1.100.0-nightly (f7575a9da 2026-09-24)
- Binary: 102137856 bytes, sha256 `bf934eb69325b109f9ad67458162f0c6503b1f35f3279b5e528faa9a9b1def61`
- Machine: windows 10.0.19045, Intel64 Family 6 Model 158 Stepping 10, GenuineIntel, 48866 MiB, 12 thread(s)
- GPU: Quadro P2000 (vulkan), driver NVIDIA 582.78
- Conditions: window [1280, 720], render distance 12, seed 1234, 1 repeat(s), warm-up 1.0 s, cooldown 0.0 s

| scenario | valid | checks | avg FPS | 1% low | p99 ms | tick mspt | tps | RSS MB | contamination |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| idle | yes | 3/3 | 397.367 | 146.78 | 5.854 | 11.979 | 20.131 | 761.797 | - |
| entities_100 | yes | 2/2 | 409.727 | 114.107 | 6.929 | 7.562 | 20.099 | 801.746 | - |
| redstone_medium | yes | 2/2 | 488.881 | 108.951 | 8.639 | 5.782 | 20.103 | 850.465 | - |

## Statistics (mean, 95% CI, coefficient of variation; repeats, raw samples kept)

| scenario | metric | n | mean | ci95 | cv% | outliers |
|---|---|---:|---:|---:|---:|---|
| idle | render.avg_fps | 1 | 397.367 | ±- | - | 0 |
| idle | render.low_1pct_fps | 1 | 146.78 | ±- | - | 0 |
| idle | render.low_01pct_fps | 1 | 93.744 | ±- | - | 0 |
| idle | render.p50_ms | 1 | 2.314 | ±- | - | 0 |
| idle | render.p95_ms | 1 | 4.694 | ±- | - | 0 |
| idle | render.p99_ms | 1 | 5.854 | ±- | - | 0 |
| idle | render.p999_ms | 1 | 6.999 | ±- | - | 0 |
| idle | render.max_ms | 1 | 16.918 | ±- | - | 0 |
| idle | render.frames | 1 | 2385.0 | ±- | - | 0 |
| idle | render.cpu_p50_ms | 1 | 1.672 | ±- | - | 0 |
| idle | render.cpu_p99_ms | 1 | 5.083 | ±- | - | 0 |
| idle | render.gpu_p50_ms | 1 | 1.656 | ±- | - | 0 |
| idle | render.gpu_p99_ms | 1 | 1.686 | ±- | - | 0 |
| idle | render.gpu_wait_p50_ms | 1 | 0.454 | ±- | - | 0 |
| idle | run.wall_s | 1 | 6.011 | ±- | - | 0 |
| idle | tick.tps | 1 | 20.131 | ±- | - | 0 |
| idle | tick.mspt | 1 | 11.979 | ±- | - | 0 |
| idle | tick.mspt_max | 1 | 15.332 | ±- | - | 0 |
| idle | tick.client_ms | 1 | 1.304 | ±- | - | 0 |
| idle | cpu.phase_prepare_ms | 1 | 0.629 | ±- | - | 0 |
| idle | cpu.phase_render_ms | 1 | 1.147 | ±- | - | 0 |
| idle | cpu.phase_tick_ms | 1 | 0.066 | ±- | - | 0 |
| idle | cpu.phase_update_ms | 1 | 0.08 | ±- | - | 0 |
| idle | cpu.slow_phase_prepare_ms | 1 | 1.667 | ±- | - | 0 |
| idle | cpu.slow_phase_render_ms | 1 | 2.709 | ±- | - | 0 |
| idle | cpu.slow_phase_tick_ms | 1 | 0.668 | ±- | - | 0 |
| idle | cpu.slow_phase_update_ms | 1 | 0.463 | ±- | - | 0 |
| idle | process.rss_peak_mb | 1 | 762.156 | ±- | - | 0 |
| idle | process.rss_steady_mb | 1 | 761.797 | ±- | - | 0 |
| idle | process.rss_samples | 1 | 12.0 | ±- | - | 0 |
| idle | process.cpu_cores_used | 1 | 1.521 | ±- | - | 0 |
| idle | process.cpu_seconds | 1 | 9.141 | ±- | - | 0 |
| idle | process.private_peak_mb | 1 | 1770.41 | ±- | - | 0 |
| idle | process.private_steady_mb | 1 | 1761.68 | ±- | - | 0 |
| idle | process.virtual_peak_mb | 1 | 7767.484 | ±- | - | 0 |
| idle | process.virtual_steady_mb | 1 | 7767.484 | ±- | - | 0 |
| entities_100 | play.spawn_s | 1 | 4.976 | ±- | - | 0 |
| entities_100 | entities.mobs | 1 | 102.0 | ±- | - | 0 |
| entities_100 | entities.spawned | 1 | 100.0 | ±- | - | 0 |
| entities_100 | render.avg_fps | 1 | 409.727 | ±- | - | 0 |
| entities_100 | render.low_1pct_fps | 1 | 114.107 | ±- | - | 0 |
| entities_100 | render.low_01pct_fps | 1 | 83.525 | ±- | - | 0 |
| entities_100 | render.p50_ms | 1 | 2.087 | ±- | - | 0 |
| entities_100 | render.p95_ms | 1 | 5.021 | ±- | - | 0 |
| entities_100 | render.p99_ms | 1 | 6.929 | ±- | - | 0 |
| entities_100 | render.p999_ms | 1 | 11.175 | ±- | - | 0 |
| entities_100 | render.max_ms | 1 | 12.448 | ±- | - | 0 |
| entities_100 | render.frames | 1 | 2459.0 | ±- | - | 0 |
| entities_100 | render.cpu_p50_ms | 1 | 1.508 | ±- | - | 0 |
| entities_100 | render.cpu_p99_ms | 1 | 3.503 | ±- | - | 0 |
| entities_100 | render.gpu_p50_ms | 1 | 1.508 | ±- | - | 0 |
| entities_100 | render.gpu_p99_ms | 1 | 4.708 | ±- | - | 0 |
| entities_100 | render.gpu_wait_p50_ms | 1 | 0.526 | ±- | - | 0 |
| entities_100 | run.wall_s | 1 | 6.02 | ±- | - | 0 |
| entities_100 | tick.tps | 1 | 20.099 | ±- | - | 0 |
| entities_100 | tick.mspt | 1 | 7.562 | ±- | - | 0 |
| entities_100 | tick.mspt_max | 1 | 9.048 | ±- | - | 0 |
| entities_100 | tick.client_ms | 1 | 0.943 | ±- | - | 0 |
| entities_100 | cpu.phase_prepare_ms | 1 | 0.713 | ±- | - | 0 |
| entities_100 | cpu.phase_render_ms | 1 | 0.845 | ±- | - | 0 |
| entities_100 | cpu.phase_tick_ms | 1 | 0.046 | ±- | - | 0 |
| entities_100 | cpu.phase_update_ms | 1 | 0.029 | ±- | - | 0 |
| entities_100 | cpu.slow_phase_prepare_ms | 1 | 1.495 | ±- | - | 0 |
| entities_100 | cpu.slow_phase_render_ms | 1 | 1.562 | ±- | - | 0 |
| entities_100 | cpu.slow_phase_tick_ms | 1 | 0.557 | ±- | - | 0 |
| entities_100 | cpu.slow_phase_update_ms | 1 | 0.162 | ±- | - | 0 |
| entities_100 | process.rss_peak_mb | 1 | 801.918 | ±- | - | 0 |
| entities_100 | process.rss_steady_mb | 1 | 801.746 | ±- | - | 0 |
| entities_100 | process.rss_samples | 1 | 11.0 | ±- | - | 0 |
| entities_100 | process.cpu_cores_used | 1 | 1.02 | ±- | - | 0 |
| entities_100 | process.cpu_seconds | 1 | 6.141 | ±- | - | 0 |
| entities_100 | process.private_peak_mb | 1 | 1821.152 | ±- | - | 0 |
| entities_100 | process.private_steady_mb | 1 | 1820.18 | ±- | - | 0 |
| entities_100 | process.virtual_peak_mb | 1 | 7793.492 | ±- | - | 0 |
| entities_100 | process.virtual_steady_mb | 1 | 7793.492 | ±- | - | 0 |
| redstone_medium | redstone.cells | 1 | 16.0 | ±- | - | 0 |
| redstone_medium | redstone.extended | 1 | 16.0 | ±- | - | 0 |
| redstone_medium | redstone.retracted | 1 | 16.0 | ±- | - | 0 |
| redstone_medium | redstone.state_transitions | 1 | 32.0 | ±- | - | 0 |
| redstone_medium | redstone.power_on_s | 1 | 1.581 | ±- | - | 0 |
| redstone_medium | redstone.power_off_s | 1 | 4.1 | ±- | - | 0 |
| redstone_medium | render.avg_fps | 1 | 488.881 | ±- | - | 0 |
| redstone_medium | render.low_1pct_fps | 1 | 108.951 | ±- | - | 0 |
| redstone_medium | render.low_01pct_fps | 1 | 100.628 | ±- | - | 0 |
| redstone_medium | render.p50_ms | 1 | 1.542 | ±- | - | 0 |
| redstone_medium | render.p95_ms | 1 | 5.749 | ±- | - | 0 |
| redstone_medium | render.p99_ms | 1 | 8.639 | ±- | - | 0 |
| redstone_medium | render.p999_ms | 1 | 9.785 | ±- | - | 0 |
| redstone_medium | render.max_ms | 1 | 10.078 | ±- | - | 0 |
| redstone_medium | render.frames | 1 | 2935.0 | ±- | - | 0 |
| redstone_medium | render.cpu_p50_ms | 1 | 1.039 | ±- | - | 0 |
| redstone_medium | render.cpu_p99_ms | 1 | 2.816 | ±- | - | 0 |
| redstone_medium | render.gpu_p50_ms | 1 | 0.924 | ±- | - | 0 |
| redstone_medium | render.gpu_p99_ms | 1 | 6.034 | ±- | - | 0 |
| redstone_medium | render.gpu_wait_p50_ms | 1 | 0.447 | ±- | - | 0 |
| redstone_medium | run.wall_s | 1 | 6.019 | ±- | - | 0 |
| redstone_medium | tick.tps | 1 | 20.103 | ±- | - | 0 |
| redstone_medium | tick.mspt | 1 | 5.782 | ±- | - | 0 |
| redstone_medium | tick.mspt_max | 1 | 7.118 | ±- | - | 0 |
| redstone_medium | tick.client_ms | 1 | 0.557 | ±- | - | 0 |
| redstone_medium | cpu.phase_prepare_ms | 1 | 0.321 | ±- | - | 0 |
| redstone_medium | cpu.phase_render_ms | 1 | 0.78 | ±- | - | 0 |
| redstone_medium | cpu.phase_tick_ms | 1 | 0.023 | ±- | - | 0 |
| redstone_medium | cpu.phase_update_ms | 1 | 0.023 | ±- | - | 0 |
| redstone_medium | cpu.slow_phase_prepare_ms | 1 | 0.815 | ±- | - | 0 |
| redstone_medium | cpu.slow_phase_render_ms | 1 | 2.102 | ±- | - | 0 |
| redstone_medium | cpu.slow_phase_tick_ms | 1 | 0.193 | ±- | - | 0 |
| redstone_medium | cpu.slow_phase_update_ms | 1 | 0.151 | ±- | - | 0 |
| redstone_medium | process.rss_peak_mb | 1 | 850.66 | ±- | - | 0 |
| redstone_medium | process.rss_steady_mb | 1 | 850.465 | ±- | - | 0 |
| redstone_medium | process.rss_samples | 1 | 12.0 | ±- | - | 0 |
| redstone_medium | process.cpu_cores_used | 1 | 1.132 | ±- | - | 0 |
| redstone_medium | process.cpu_seconds | 1 | 6.813 | ±- | - | 0 |
| redstone_medium | process.private_peak_mb | 1 | 1867.301 | ±- | - | 0 |
| redstone_medium | process.private_steady_mb | 1 | 1865.801 | ±- | - | 0 |
| redstone_medium | process.virtual_peak_mb | 1 | 7839.57 | ±- | - | 0 |
| redstone_medium | process.virtual_steady_mb | 1 | 7839.57 | ±- | - | 0 |

## Correctness checks

- PASS `idle`: frames drawn (expected > 10, got 2810)
- PASS `idle`: ticks advanced (expected > 1, got 120.8)
- PASS `idle`: tick rate plausible (expected > 5 tps, got 20.131)
- PASS `entities_100`: mobs spawned (expected >= 80, got 102)
- PASS `entities_100`: frames drawn (expected > 10, got 2849)
- PASS `redstone_medium`: every piston extended (expected == 16, got 16)
- PASS `redstone_medium`: every piston retracted (expected == 16, got 16)
