# Gameplay benchmark: baseline-repeat

- Commit: `eb1e54725ce50aa42c4dc0f585a73db95786367a` (dirty)
- Profile: `bench`; rustc 1.100.0-nightly (f7575a9da 2026-09-24)
- Binary: 102137856 bytes, sha256 `bf934eb69325b109f9ad67458162f0c6503b1f35f3279b5e528faa9a9b1def61`
- Machine: windows 10.0.19045, Intel64 Family 6 Model 158 Stepping 10, GenuineIntel, 48866 MiB, 12 thread(s)
- GPU: Quadro P2000 (vulkan), driver NVIDIA 582.78
- Conditions: window [1280, 720], render distance 12, seed 1234, 5 repeat(s), warm-up 2.0 s, cooldown 1.0 s

| scenario | valid | checks | avg FPS | 1% low | p99 ms | tick mspt | tps | RSS MB | contamination |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| idle | yes | 3/3 | 165 ±78.7 | 55.9 ±5.35 | 17.3 ±2.31 | 8.26 ±4.89 | 20.1 ±0.063 | 773 ±14.3 | - |
| walk | yes | 1/1 | 316 ±157 | 98.8 ±34.9 | 9.59 ±3.51 | 5.21 ±1.14 | 20 ±0.071 | 809 ±21.1 | - |
| entities | yes | 2/2 | 233 ±143 | 87.5 ±24.9 | 10.6 ±4.84 | 4.97 ±0.824 | 20.1 ±0.065 | 825 ±21.4 | - |
| redstone | yes | 5/5 | 389 ±158 | 120 ±16.3 | 8.14 ±1.23 | 5.53 ±1.28 | 20 ±0.088 | 850 ±11 | repeat 1: machine 82.1% busy in other work before the scenario (system 88.1%, game 6.0%, limit 75%) |
| mixed | yes | 3/3 | 345 ±203 | 64.1 ±32.7 | 15.3 ±10.2 | - | 20 ±0.017 | 856 ±7.43 | - |

## Statistics (mean, 95% CI, coefficient of variation; repeats, raw samples kept)

| scenario | metric | n | mean | ci95 | cv% | outliers |
|---|---|---:|---:|---:|---:|---|
| idle | render.avg_fps | 5 | 165.208 | ±78.663 | 38.354 | 0 |
| idle | render.low_1pct_fps | 5 | 55.939 | ±5.347 | 7.699 | 1 |
| idle | render.low_01pct_fps | 5 | 52.61 | ±2.218 | 3.397 | 1 |
| idle | render.p50_ms | 5 | 6.696 | ±5.898 | 70.948 | 1 |
| idle | render.p95_ms | 5 | 13.372 | ±5.045 | 30.392 | 0 |
| idle | render.p99_ms | 5 | 17.298 | ±2.307 | 10.745 | 1 |
| idle | render.p999_ms | 5 | 18.81 | ±0.952 | 4.076 | 0 |
| idle | render.max_ms | 5 | 19.24 | ±0.889 | 3.721 | 1 |
| idle | render.frames | 5 | 1323.4 | ±630.707 | 38.389 | 0 |
| idle | render.cpu_p50_ms | 5 | 1.727 | ±1.25 | 58.319 | 1 |
| idle | render.cpu_p99_ms | 5 | 4.371 | ±2.388 | 44.006 | 1 |
| idle | render.gpu_p50_ms | 5 | 6.304 | ±5.654 | 72.248 | 1 |
| idle | render.gpu_p99_ms | 5 | 13.933 | ±0.581 | 3.36 | 0 |
| idle | render.gpu_wait_p50_ms | 5 | 4.864 | ±5.622 | 93.1 | 2 |
| idle | run.wall_s | 5 | 8.025 | ±0.017 | 0.173 | 0 |
| idle | tick.tps | 5 | 20.088 | ±0.063 | 0.253 | 2 |
| idle | tick.mspt | 5 | 8.255 | ±4.895 | 47.762 | 2 |
| idle | tick.mspt_max | 5 | 11.044 | ±5.841 | 42.605 | 1 |
| idle | tick.client_ms | 5 | 0.867 | ±0.548 | 50.959 | 1 |
| idle | cpu.phase_prepare_ms | 5 | 0.54 | ±0.385 | 57.38 | 1 |
| idle | cpu.phase_render_ms | 5 | 1.095 | ±0.669 | 49.201 | 1 |
| idle | cpu.phase_tick_ms | 5 | 0.129 | ±0.11 | 68.693 | 0 |
| idle | cpu.phase_update_ms | 5 | 0.143 | ±0.113 | 63.644 | 0 |
| idle | cpu.slow_phase_prepare_ms | 5 | 1.54 | ±0.636 | 33.285 | 1 |
| idle | cpu.slow_phase_render_ms | 5 | 2.098 | ±1.232 | 47.31 | 1 |
| idle | cpu.slow_phase_tick_ms | 5 | 0.859 | ±0.88 | 82.483 | 0 |
| idle | cpu.slow_phase_update_ms | 5 | 0.491 | ±0.282 | 46.29 | 0 |
| idle | process.rss_peak_mb | 5 | 801.829 | ±43.601 | 4.38 | 0 |
| idle | process.rss_steady_mb | 5 | 772.666 | ±14.288 | 1.49 | 0 |
| idle | process.rss_samples | 5 | 16.0 | ±- | - | 0 |
| idle | process.cpu_cores_used | 5 | 0.916 | ±0.496 | 43.635 | 1 |
| idle | process.cpu_seconds | 5 | 7.347 | ±3.965 | 43.476 | 1 |
| idle | process.private_peak_mb | 5 | 1801.749 | ±50.932 | 2.277 | 0 |
| idle | process.private_steady_mb | 5 | 1755.226 | ±20.943 | 0.961 | 2 |
| idle | process.virtual_peak_mb | 5 | 7796.01 | ±37.67 | 0.389 | 0 |
| idle | process.virtual_steady_mb | 5 | 7792.01 | ±43.157 | 0.446 | 0 |
| walk | play.action_s | 5 | 2.015 | ±0.008 | 0.332 | 0 |
| walk | play.distance_blocks | 5 | 16.593 | ±0.329 | 1.598 | 0 |
| walk | play.walk_mps | 5 | 8.233 | ±0.139 | 1.356 | 0 |
| walk | render.avg_fps | 5 | 315.992 | ±156.968 | 40.013 | 0 |
| walk | render.low_1pct_fps | 5 | 98.799 | ±34.887 | 28.443 | 1 |
| walk | render.low_01pct_fps | 5 | 80.243 | ±11.993 | 12.039 | 0 |
| walk | render.p50_ms | 5 | 3.679 | ±2.949 | 64.562 | 0 |
| walk | render.p95_ms | 5 | 7.571 | ±4.362 | 46.415 | 0 |
| walk | render.p99_ms | 5 | 9.589 | ±3.508 | 29.47 | 0 |
| walk | render.p999_ms | 5 | 12.156 | ±1.578 | 10.457 | 0 |
| walk | render.max_ms | 5 | 13.213 | ±2.135 | 13.013 | 0 |
| walk | render.frames | 5 | 2528.2 | ±1254.734 | 39.977 | 0 |
| walk | render.cpu_p50_ms | 5 | 0.89 | ±0.427 | 38.625 | 1 |
| walk | render.cpu_p99_ms | 5 | 2.678 | ±1.318 | 39.647 | 1 |
| walk | render.gpu_p50_ms | 5 | 3.404 | ±3.309 | 78.296 | 0 |
| walk | render.gpu_p99_ms | 5 | 7.015 | ±3.108 | 35.69 | 0 |
| walk | render.gpu_wait_p50_ms | 5 | 2.651 | ±2.519 | 76.548 | 0 |
| walk | run.wall_s | 5 | 8.023 | ±0.006 | 0.059 | 1 |
| walk | tick.tps | 5 | 20.042 | ±0.071 | 0.286 | 2 |
| walk | tick.mspt | 5 | 5.213 | ±1.141 | 17.633 | 1 |
| walk | tick.mspt_max | 5 | 8.245 | ±2.645 | 25.837 | 0 |
| walk | tick.client_ms | 5 | 0.709 | ±0.148 | 16.875 | 0 |
| walk | cpu.phase_prepare_ms | 5 | 0.219 | ±0.106 | 38.987 | 1 |
| walk | cpu.phase_render_ms | 5 | 0.725 | ±0.324 | 36.017 | 1 |
| walk | cpu.phase_tick_ms | 5 | 0.054 | ±0.041 | 61.293 | 1 |
| walk | cpu.phase_update_ms | 5 | 0.028 | ±0.017 | 49.034 | 1 |
| walk | cpu.slow_phase_prepare_ms | 5 | 0.538 | ±0.247 | 37.047 | 0 |
| walk | cpu.slow_phase_render_ms | 5 | 2.03 | ±0.748 | 29.667 | 1 |
| walk | cpu.slow_phase_tick_ms | 5 | 0.554 | ±0.431 | 62.709 | 1 |
| walk | cpu.slow_phase_update_ms | 5 | 0.068 | ±0.028 | 33.663 | 0 |
| walk | process.rss_peak_mb | 5 | 816.696 | ±20.712 | 2.043 | 0 |
| walk | process.rss_steady_mb | 5 | 809.162 | ±21.123 | 2.103 | 0 |
| walk | process.rss_samples | 5 | 16.0 | ±- | - | 0 |
| walk | process.cpu_cores_used | 5 | 0.601 | ±0.167 | 22.334 | 0 |
| walk | process.cpu_seconds | 5 | 4.819 | ±1.336 | 22.332 | 0 |
| walk | process.private_peak_mb | 5 | 1824.828 | ±37.621 | 1.661 | 0 |
| walk | process.private_steady_mb | 5 | 1810.356 | ±44.49 | 1.98 | 0 |
| walk | process.virtual_peak_mb | 5 | 7796.433 | ±27.787 | 0.287 | 1 |
| walk | process.virtual_steady_mb | 5 | 7796.433 | ±27.787 | 0.287 | 1 |
| entities | play.spawn_s | 5 | 9.989 | ±0.01 | 0.082 | 0 |
| entities | entities.mobs | 5 | 200.2 | ±1.36 | 0.547 | 2 |
| entities | entities.spawned | 5 | 200.0 | ±- | - | 0 |
| entities | render.avg_fps | 5 | 233.078 | ±142.853 | 49.369 | 0 |
| entities | render.low_1pct_fps | 5 | 87.48 | ±24.939 | 22.964 | 0 |
| entities | render.low_01pct_fps | 5 | 67.057 | ±7.843 | 9.422 | 0 |
| entities | render.p50_ms | 5 | 5.041 | ±4.97 | 79.414 | 1 |
| entities | render.p95_ms | 5 | 9.711 | ±5.207 | 43.189 | 0 |
| entities | render.p99_ms | 5 | 10.626 | ±4.837 | 36.669 | 0 |
| entities | render.p999_ms | 5 | 14.698 | ±2.133 | 11.687 | 1 |
| entities | render.max_ms | 5 | 15.28 | ±1.827 | 9.629 | 0 |
| entities | render.frames | 5 | 1865.6 | ±1143.093 | 49.355 | 0 |
| entities | render.cpu_p50_ms | 5 | 1.934 | ±0.779 | 32.461 | 1 |
| entities | render.cpu_p99_ms | 5 | 4.939 | ±2.024 | 33.003 | 0 |
| entities | render.gpu_p50_ms | 5 | 4.185 | ±4.501 | 86.628 | 0 |
| entities | render.gpu_p99_ms | 5 | 7.303 | ±3.472 | 38.295 | 0 |
| entities | render.gpu_wait_p50_ms | 5 | 2.888 | ±4.444 | 123.951 | 1 |
| entities | run.wall_s | 5 | 8.03 | ±0.014 | 0.138 | 0 |
| entities | tick.tps | 5 | 20.099 | ±0.065 | 0.261 | 0 |
| entities | tick.mspt | 5 | 4.974 | ±0.824 | 13.344 | 2 |
| entities | tick.mspt_max | 5 | 7.142 | ±1.839 | 20.743 | 0 |
| entities | tick.client_ms | 5 | 0.629 | ±0.188 | 24.105 | 1 |
| entities | cpu.phase_prepare_ms | 5 | 1.16 | ±0.456 | 31.679 | 1 |
| entities | cpu.phase_render_ms | 5 | 0.906 | ±0.28 | 24.895 | 1 |
| entities | cpu.phase_tick_ms | 5 | 0.082 | ±0.1 | 98.209 | 1 |
| entities | cpu.phase_update_ms | 5 | 0.033 | ±0.031 | 75.545 | 1 |
| entities | cpu.slow_phase_prepare_ms | 5 | 2.621 | ±0.614 | 18.861 | 0 |
| entities | cpu.slow_phase_render_ms | 5 | 1.969 | ±0.434 | 17.777 | 1 |
| entities | cpu.slow_phase_tick_ms | 5 | 0.78 | ±0.867 | 89.603 | 1 |
| entities | cpu.slow_phase_update_ms | 5 | 0.112 | ±0.105 | 75.716 | 1 |
| entities | process.rss_peak_mb | 5 | 830.063 | ±14.598 | 1.417 | 0 |
| entities | process.rss_steady_mb | 5 | 825.252 | ±21.387 | 2.088 | 2 |
| entities | process.rss_samples | 5 | 15.8 | ±0.555 | 2.83 | 1 |
| entities | process.cpu_cores_used | 5 | 0.693 | ±0.258 | 29.932 | 0 |
| entities | process.cpu_seconds | 5 | 5.566 | ±2.068 | 29.925 | 0 |
| entities | process.private_peak_mb | 5 | 1827.3 | ±6.728 | 0.297 | 1 |
| entities | process.private_steady_mb | 5 | 1818.113 | ±9.14 | 0.405 | 0 |
| entities | process.virtual_peak_mb | 5 | 7810.026 | ±18.883 | 0.195 | 2 |
| entities | process.virtual_steady_mb | 5 | 7786.411 | ±4.735 | 0.049 | 0 |
| redstone | redstone.piston_extended | 5 | 1.0 | ±- | - | 0 |
| redstone | redstone.lamp_lit | 5 | 1.0 | ±- | - | 0 |
| redstone | redstone.hopper_moved | 5 | 5.0 | ±- | - | 0 |
| redstone | render.avg_fps | 5 | 389.223 | ±157.842 | 32.666 | 1 |
| redstone | render.low_1pct_fps | 5 | 119.99 | ±16.29 | 10.935 | 1 |
| redstone | render.low_01pct_fps | 5 | 111.801 | ±15.674 | 11.293 | 2 |
| redstone | render.p50_ms | 5 | 2.359 | ±2.112 | 72.106 | 1 |
| redstone | render.p95_ms | 5 | 6.426 | ±2.007 | 25.154 | 0 |
| redstone | render.p99_ms | 5 | 8.142 | ±1.229 | 12.158 | 1 |
| redstone | render.p999_ms | 5 | 8.807 | ±1.442 | 13.193 | 1 |
| redstone | render.max_ms | 5 | 9.481 | ±1.356 | 11.519 | 2 |
| redstone | render.frames | 5 | 3115.0 | ±1262.831 | 32.655 | 1 |
| redstone | render.cpu_p50_ms | 5 | 1.061 | ±0.641 | 48.709 | 1 |
| redstone | render.cpu_p99_ms | 5 | 3.167 | ±1.631 | 41.481 | 1 |
| redstone | render.gpu_p50_ms | 5 | 1.726 | ±2.096 | 97.856 | 1 |
| redstone | render.gpu_p99_ms | 5 | 4.853 | ±0.362 | 6.011 | 0 |
| redstone | render.gpu_wait_p50_ms | 5 | 1.215 | ±1.636 | 108.412 | 1 |
| redstone | run.wall_s | 5 | 8.024 | ±0.002 | 0.024 | 0 |
| redstone | tick.tps | 5 | 20.015 | ±0.088 | 0.353 | 0 |
| redstone | tick.mspt | 5 | 5.531 | ±1.283 | 18.686 | 1 |
| redstone | tick.mspt_max | 5 | 7.842 | ±1.148 | 11.787 | 1 |
| redstone | tick.client_ms | 5 | 0.858 | ±0.173 | 16.24 | 1 |
| redstone | cpu.phase_prepare_ms | 5 | 0.264 | ±0.117 | 35.535 | 1 |
| redstone | cpu.phase_render_ms | 5 | 0.854 | ±0.476 | 44.872 | 1 |
| redstone | cpu.phase_tick_ms | 5 | 0.055 | ±0.053 | 77.298 | 1 |
| redstone | cpu.phase_update_ms | 5 | 0.022 | ±0.013 | 46.019 | 1 |
| redstone | cpu.slow_phase_prepare_ms | 5 | 0.697 | ±0.317 | 36.628 | 1 |
| redstone | cpu.slow_phase_render_ms | 5 | 2.203 | ±0.909 | 33.232 | 2 |
| redstone | cpu.slow_phase_tick_ms | 5 | 0.713 | ±0.55 | 62.108 | 1 |
| redstone | cpu.slow_phase_update_ms | 5 | 0.077 | ±0.044 | 45.792 | 0 |
| redstone | process.rss_peak_mb | 5 | 851.357 | ±10.025 | 0.948 | 0 |
| redstone | process.rss_steady_mb | 5 | 849.911 | ±10.986 | 1.041 | 1 |
| redstone | process.rss_samples | 5 | 15.8 | ±0.555 | 2.83 | 1 |
| redstone | process.cpu_cores_used | 5 | 0.767 | ±0.08 | 8.376 | 0 |
| redstone | process.cpu_seconds | 5 | 6.153 | ±0.64 | 8.379 | 0 |
| redstone | process.private_peak_mb | 5 | 1848.145 | ±19.346 | 0.843 | 0 |
| redstone | process.private_steady_mb | 5 | 1840.796 | ±22.909 | 1.002 | 0 |
| redstone | process.virtual_peak_mb | 5 | 7789.238 | ±25.34 | 0.262 | 1 |
| redstone | process.virtual_steady_mb | 5 | 7789.226 | ±25.308 | 0.262 | 1 |
| mixed | render.avg_fps | 5 | 344.628 | ±203.384 | 47.537 | 1 |
| mixed | render.low_1pct_fps | 5 | 64.136 | ±32.683 | 41.048 | 0 |
| mixed | render.low_01pct_fps | 5 | 44.55 | ±21.386 | 38.668 | 0 |
| mixed | render.p50_ms | 5 | 3.586 | ±5.004 | 112.388 | 1 |
| mixed | render.p95_ms | 5 | 10.296 | ±10.706 | 83.757 | 1 |
| mixed | render.p99_ms | 5 | 15.278 | ±10.158 | 53.554 | 0 |
| mixed | render.p999_ms | 5 | 22.661 | ±9.933 | 35.306 | 0 |
| mixed | render.max_ms | 5 | 31.518 | ±16.364 | 41.822 | 1 |
| mixed | render.frames | 5 | 7190.4 | ±4212.011 | 47.185 | 1 |
| mixed | render.cpu_p50_ms | 5 | 1.26 | ±0.621 | 39.725 | 1 |
| mixed | render.cpu_p99_ms | 5 | 4.009 | ±2.443 | 49.093 | 1 |
| mixed | render.gpu_p50_ms | 5 | 2.629 | ±4.123 | 126.323 | 1 |
| mixed | render.gpu_p99_ms | 5 | 13.357 | ±10.294 | 62.081 | 0 |
| mixed | render.gpu_wait_p50_ms | 5 | 2.188 | ±4.393 | 161.7 | 1 |
| mixed | run.wall_s | 10 | 21.001 | ±0.165 | 1.096 | 2 |
| mixed | play.actions | 5 | 118.0 | ±- | - | 0 |
| mixed | play.action_s | 5 | 21.001 | ±0.303 | 1.163 | 1 |
| mixed | tick.tps | 5 | 19.98 | ±0.017 | 0.07 | 2 |
| mixed | process.rss_peak_mb | 5 | 860.87 | ±12.382 | 1.159 | 0 |
| mixed | process.rss_steady_mb | 5 | 856.091 | ±7.426 | 0.699 | 1 |
| mixed | process.rss_samples | 5 | 41.4 | ±0.68 | 1.323 | 0 |
| mixed | process.cpu_cores_used | 5 | 0.885 | ±0.294 | 26.756 | 0 |
| mixed | process.cpu_seconds | 5 | 18.55 | ±5.977 | 25.952 | 0 |
| mixed | process.private_peak_mb | 5 | 1861.473 | ±18.43 | 0.798 | 0 |
| mixed | process.private_steady_mb | 5 | 1852.232 | ±19.091 | 0.83 | 0 |
| mixed | process.virtual_peak_mb | 5 | 7789.226 | ±25.308 | 0.262 | 1 |
| mixed | process.virtual_steady_mb | 5 | 7787.626 | ±25.609 | 0.265 | 1 |
| mixed | memory.rss_slope_mb_per_min | 5 | -9.222 | ±24.645 | 215.264 | 0 |

## Correctness checks

- PASS `idle`: frames drawn (expected > 10, got 1799)
- PASS `idle`: ticks advanced (expected > 1, got 160.8)
- PASS `idle`: tick rate plausible (expected > 5 tps, got 20.105)
- PASS `walk`: player moved (expected > 3 blocks, got 16.4)
- PASS `entities`: mobs spawned (expected >= 160, got 199)
- PASS `entities`: frames drawn (expected > 10, got 806)
- PASS `redstone`: piston extends (expected piston_head, got minecraft:piston_head)
- PASS `redstone`: piston retracts (expected air, got minecraft:air)
- PASS `redstone`: repeater lights lamp (expected lit=true, got minecraft:redstone_lamp)
- PASS `redstone`: lamp turns off (expected lit=false, got minecraft:redstone_lamp)
- PASS `redstone`: hopper transfers (expected >= 1 item, got 5)
- PASS `mixed`: actions completed (expected > 10, got 118)
- PASS `mixed`: ticks advanced (expected > 20, got 428)
- PASS `mixed`: frames drawn (expected > 10, got 1557)
