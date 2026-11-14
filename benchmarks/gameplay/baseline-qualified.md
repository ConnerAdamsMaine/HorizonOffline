# Gameplay benchmark: baseline-phase2

- Commit: `eb1e54725ce50aa42c4dc0f585a73db95786367a` (dirty)
- Profile: `bench`; rustc 1.100.0-nightly (f7575a9da 2026-09-24)
- Binary: 102137856 bytes, sha256 `bf934eb69325b109f9ad67458162f0c6503b1f35f3279b5e528faa9a9b1def61`
- Machine: windows 10.0.19045, Intel64 Family 6 Model 158 Stepping 10, GenuineIntel, 48866 MiB, 12 thread(s)
- GPU: Quadro P2000 (vulkan), driver NVIDIA 582.78
- Conditions: window [1280, 720], render distance 12, seed 1234, 5 repeat(s), warm-up 2.0 s, cooldown 1.0 s

| scenario | valid | checks | avg FPS | 1% low | p99 ms | tick mspt | tps | RSS MB | contamination |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| idle | yes | 3/3 | 180 ±214 | 102 ±81.6 | 13.1 ±8.87 | 7.07 ±2.83 | 20 ±0.064 | 772 ±16.7 | - |
| walk | yes | 1/1 | 255 ±186 | 92.7 ±33.9 | 10.7 ±3.46 | 5.57 ±0.745 | 20 ±0.023 | 816 ±10.6 | - |
| explore | yes | 3/3 | 235 ±45 | 67.5 ±14.4 | 10.3 ±1.2 | - | - | 860 ±11.2 | - |
| mine_place | yes | 2/2 | 247 ±124 | 106 ±8.95 | 9.25 ±0.919 | 5.17 ±0.824 | 20.1 ±0.009 | 859 ±12.9 | - |
| crafting | yes | 2/2 | 199 ±102 | 99.4 ±9.52 | 9.89 ±1.04 | 3.63 ±1.06 | 20.1 ±0.062 | 867 ±19.8 | repeat 4: machine 96.7% busy in other work after the scenario (system 100.0%, game 3.3%, limit 75%) |
| combat | yes | 1/1 | 279 ±156 | 100 ±13.9 | 9.45 ±1 | 3.73 ±0.434 | 20.1 ±0.023 | 875 ±14.2 | repeat 4: machine 95.8% busy in other work before the scenario (system 100.0%, game 4.2%, limit 75%) |
| redstone | yes | 5/5 | 244 ±87.6 | 97.1 ±6.73 | 9.93 ±0.667 | 3.42 ±0.866 | 20.1 ±0.014 | 876 ±14.7 | - |
| entities | yes | 2/2 | 112 ±51.4 | 65.8 ±4.63 | 14.9 ±0.906 | 4.58 ±1.13 | 20 ±0.024 | 880 ±14.3 | - |
| world_ops | yes | 8/8 | 291 ±77.7 | 105 ±16.2 | 7.7 ±0.63 | 4.95 ±0.518 | 20 ±0.062 | 912 ±11.3 | - |
| mixed | yes | 3/3 | 146 ±107 | 38.3 ±16.5 | 24.6 ±13.3 | - | 20 ±0.02 | 918 ±14.6 | - |

## Statistics (mean, 95% CI, coefficient of variation; repeats, raw samples kept)

| scenario | metric | n | mean | ci95 | cv% | outliers |
|---|---|---:|---:|---:|---:|---|
| idle | render.avg_fps | 5 | 180.112 | ±213.971 | 95.693 | 0 |
| idle | render.low_1pct_fps | 5 | 101.926 | ±81.565 | 64.46 | 0 |
| idle | render.low_01pct_fps | 5 | 89.57 | ±61.608 | 55.404 | 0 |
| idle | render.p50_ms | 5 | 9.965 | ±8.135 | 65.756 | 0 |
| idle | render.p95_ms | 5 | 12.541 | ±9.007 | 57.849 | 0 |
| idle | render.p99_ms | 5 | 13.118 | ±8.869 | 54.46 | 0 |
| idle | render.p999_ms | 5 | 13.752 | ±8.687 | 50.883 | 0 |
| idle | render.max_ms | 5 | 14.476 | ±7.512 | 41.8 | 0 |
| idle | render.frames | 5 | 1441.2 | ±1711.54 | 95.66 | 0 |
| idle | render.cpu_p50_ms | 5 | 1.519 | ±0.452 | 23.996 | 0 |
| idle | render.cpu_p99_ms | 5 | 4.294 | ±1.417 | 26.587 | 0 |
| idle | render.gpu_p50_ms | 5 | 9.272 | ±7.813 | 67.873 | 0 |
| idle | render.gpu_p99_ms | 5 | 9.519 | ±7.671 | 64.907 | 0 |
| idle | render.gpu_wait_p50_ms | 5 | 8.491 | ±7.956 | 75.475 | 0 |
| idle | run.wall_s | 5 | 8.026 | ±0.012 | 0.123 | 1 |
| idle | tick.tps | 5 | 20.034 | ±0.064 | 0.258 | 0 |
| idle | tick.mspt | 5 | 7.065 | ±2.829 | 32.252 | 0 |
| idle | tick.mspt_max | 5 | 9.767 | ±4.125 | 34.018 | 0 |
| idle | tick.client_ms | 5 | 0.833 | ±0.309 | 29.876 | 1 |
| idle | cpu.phase_prepare_ms | 5 | 0.467 | ±0.086 | 14.793 | 0 |
| idle | cpu.phase_render_ms | 5 | 0.952 | ±0.202 | 17.118 | 2 |
| idle | cpu.phase_tick_ms | 5 | 0.162 | ±0.128 | 63.905 | 0 |
| idle | cpu.phase_update_ms | 5 | 0.155 | ±0.129 | 67.167 | 0 |
| idle | cpu.slow_phase_prepare_ms | 5 | 1.269 | ±0.456 | 28.938 | 2 |
| idle | cpu.slow_phase_render_ms | 5 | 1.795 | ±0.454 | 20.377 | 0 |
| idle | cpu.slow_phase_tick_ms | 5 | 1.106 | ±0.747 | 54.39 | 0 |
| idle | cpu.slow_phase_update_ms | 5 | 0.739 | ±0.489 | 53.367 | 1 |
| idle | process.rss_peak_mb | 5 | 792.719 | ±39.938 | 4.058 | 0 |
| idle | process.rss_steady_mb | 5 | 772.036 | ±16.674 | 1.74 | 0 |
| idle | process.rss_samples | 5 | 16.0 | ±- | - | 0 |
| idle | process.cpu_cores_used | 5 | 0.75 | ±0.643 | 69.061 | 1 |
| idle | process.cpu_seconds | 5 | 6.016 | ±5.159 | 69.072 | 1 |
| idle | process.private_peak_mb | 5 | 1799.051 | ±56.537 | 2.531 | 0 |
| idle | process.private_steady_mb | 5 | 1766.055 | ±28.148 | 1.284 | 1 |
| idle | process.virtual_peak_mb | 5 | 7789.369 | ±38.726 | 0.4 | 0 |
| idle | process.virtual_steady_mb | 5 | 7786.969 | ±43.696 | 0.452 | 0 |
| walk | play.action_s | 5 | 2.022 | ±0.008 | 0.31 | 0 |
| walk | play.distance_blocks | 5 | 16.689 | ±0.329 | 1.588 | 0 |
| walk | play.walk_mps | 5 | 8.256 | ±0.192 | 1.869 | 0 |
| walk | render.avg_fps | 5 | 255.213 | ±185.727 | 58.619 | 0 |
| walk | render.low_1pct_fps | 5 | 92.727 | ±33.875 | 29.427 | 1 |
| walk | render.low_01pct_fps | 5 | 76.336 | ±21.446 | 22.63 | 1 |
| walk | render.p50_ms | 5 | 4.936 | ±4.579 | 74.721 | 0 |
| walk | render.p95_ms | 5 | 9.02 | ±3.799 | 33.924 | 0 |
| walk | render.p99_ms | 5 | 10.703 | ±3.456 | 26.008 | 1 |
| walk | render.p999_ms | 5 | 13.516 | ±4.966 | 29.598 | 1 |
| walk | render.max_ms | 5 | 13.864 | ±4.502 | 26.159 | 1 |
| walk | render.frames | 5 | 2042.8 | ±1485.947 | 58.593 | 0 |
| walk | render.cpu_p50_ms | 5 | 0.981 | ±0.444 | 36.431 | 0 |
| walk | render.cpu_p99_ms | 5 | 2.873 | ±1.248 | 34.986 | 0 |
| walk | render.gpu_p50_ms | 5 | 4.3 | ±4.598 | 86.144 | 0 |
| walk | render.gpu_p99_ms | 5 | 7.737 | ±2.561 | 26.66 | 2 |
| walk | render.gpu_wait_p50_ms | 5 | 3.961 | ±4.358 | 88.618 | 0 |
| walk | run.wall_s | 5 | 8.031 | ±0.009 | 0.089 | 0 |
| walk | tick.tps | 5 | 20.048 | ±0.023 | 0.092 | 0 |
| walk | tick.mspt | 5 | 5.566 | ±0.745 | 10.783 | 0 |
| walk | tick.mspt_max | 5 | 8.181 | ±1.303 | 12.832 | 0 |
| walk | tick.client_ms | 5 | 0.724 | ±0.133 | 14.824 | 0 |
| walk | cpu.phase_prepare_ms | 5 | 0.229 | ±0.066 | 23.238 | 0 |
| walk | cpu.phase_render_ms | 5 | 0.748 | ±0.293 | 31.515 | 0 |
| walk | cpu.phase_tick_ms | 5 | 0.085 | ±0.079 | 75.109 | 0 |
| walk | cpu.phase_update_ms | 5 | 0.04 | ±0.026 | 53.577 | 0 |
| walk | cpu.slow_phase_prepare_ms | 5 | 0.567 | ±0.198 | 28.054 | 1 |
| walk | cpu.slow_phase_render_ms | 5 | 1.816 | ±0.446 | 19.784 | 0 |
| walk | cpu.slow_phase_tick_ms | 5 | 0.752 | ±0.678 | 72.681 | 0 |
| walk | cpu.slow_phase_update_ms | 5 | 0.221 | ±0.145 | 52.61 | 0 |
| walk | process.rss_peak_mb | 5 | 841.8 | ±20.244 | 1.937 | 0 |
| walk | process.rss_steady_mb | 5 | 815.93 | ±10.585 | 1.045 | 2 |
| walk | process.rss_samples | 5 | 15.6 | ±0.68 | 3.511 | 0 |
| walk | process.cpu_cores_used | 5 | 0.547 | ±0.24 | 35.385 | 1 |
| walk | process.cpu_seconds | 5 | 4.394 | ±1.929 | 35.353 | 1 |
| walk | process.private_peak_mb | 5 | 1856.723 | ±17.121 | 0.743 | 0 |
| walk | process.private_steady_mb | 5 | 1820.049 | ±9.584 | 0.424 | 0 |
| walk | process.virtual_peak_mb | 5 | 7807.426 | ±39.024 | 0.403 | 2 |
| walk | process.virtual_steady_mb | 5 | 7801.024 | ±50.252 | 0.519 | 2 |
| explore | render.avg_fps | 5 | 234.805 | ±45.028 | 15.447 | 1 |
| explore | render.low_1pct_fps | 5 | 67.497 | ±14.412 | 17.199 | 0 |
| explore | render.low_01pct_fps | 5 | 35.354 | ±9.934 | 22.634 | 0 |
| explore | render.p50_ms | 5 | 3.842 | ±0.544 | 11.41 | 2 |
| explore | render.p95_ms | 5 | 7.489 | ±0.596 | 6.414 | 0 |
| explore | render.p99_ms | 5 | 10.337 | ±1.201 | 9.362 | 0 |
| explore | render.p999_ms | 5 | 20.919 | ±7.646 | 29.443 | 0 |
| explore | render.max_ms | 5 | 57.64 | ±13.301 | 18.587 | 1 |
| explore | render.frames | 5 | 4695.2 | ±900.892 | 15.456 | 1 |
| explore | render.cpu_p50_ms | 5 | 1.019 | ±0.316 | 24.961 | 1 |
| explore | render.cpu_p99_ms | 5 | 4.554 | ±0.746 | 13.197 | 2 |
| explore | render.gpu_p50_ms | 5 | 3.244 | ±0.794 | 19.729 | 1 |
| explore | render.gpu_p99_ms | 5 | 4.345 | ±0.078 | 1.444 | 0 |
| explore | render.gpu_wait_p50_ms | 5 | 2.733 | ±0.647 | 19.06 | 1 |
| explore | run.wall_s | 5 | 20.068 | ±0.076 | 0.305 | 1 |
| explore | world.generated_chunks | 5 | 1080.0 | ±- | - | 0 |
| explore | world.resident_chunks | 5 | 637.0 | ±- | - | 0 |
| explore | world.travel_blocks | 5 | 527.758 | ±- | - | 0 |
| explore | process.rss_peak_mb | 5 | 882.338 | ±12.021 | 1.097 | 1 |
| explore | process.rss_steady_mb | 5 | 860.219 | ±11.17 | 1.046 | 1 |
| explore | process.rss_samples | 5 | 39.2 | ±0.555 | 1.141 | 1 |
| explore | process.cpu_cores_used | 5 | 2.85 | ±0.448 | 12.663 | 0 |
| explore | process.cpu_seconds | 5 | 57.2 | ±9.014 | 12.694 | 0 |
| explore | process.private_peak_mb | 5 | 2136.863 | ±15.845 | 0.597 | 0 |
| explore | process.private_steady_mb | 5 | 2030.062 | ±9.324 | 0.37 | 0 |
| explore | process.virtual_peak_mb | 5 | 8065.351 | ±28.946 | 0.289 | 1 |
| explore | process.virtual_steady_mb | 5 | 7956.126 | ±23.904 | 0.242 | 0 |
| mine_place | play.action_s | 5 | 2.756 | ±0.22 | 6.439 | 1 |
| mine_place | play.placed | 5 | 8.0 | ±- | - | 0 |
| mine_place | play.broken | 5 | 8.0 | ±- | - | 0 |
| mine_place | play.ops_per_s | 5 | 5.825 | ±0.456 | 6.307 | 1 |
| mine_place | render.avg_fps | 5 | 247.014 | ±124.322 | 40.541 | 0 |
| mine_place | render.low_1pct_fps | 5 | 105.525 | ±8.949 | 6.831 | 2 |
| mine_place | render.low_01pct_fps | 5 | 100.252 | ±8.472 | 6.807 | 2 |
| mine_place | render.p50_ms | 5 | 3.978 | ±2.438 | 49.372 | 0 |
| mine_place | render.p95_ms | 5 | 8.357 | ±1.362 | 13.127 | 2 |
| mine_place | render.p99_ms | 5 | 9.249 | ±0.919 | 8.003 | 1 |
| mine_place | render.p999_ms | 5 | 9.863 | ±0.951 | 7.766 | 1 |
| mine_place | render.max_ms | 5 | 10.205 | ±0.794 | 6.267 | 2 |
| mine_place | render.frames | 5 | 1976.6 | ±993.577 | 40.49 | 0 |
| mine_place | render.cpu_p50_ms | 5 | 1.082 | ±0.401 | 29.836 | 1 |
| mine_place | render.cpu_p99_ms | 5 | 2.892 | ±0.795 | 22.136 | 1 |
| mine_place | render.gpu_p50_ms | 5 | 2.885 | ±2.864 | 79.951 | 0 |
| mine_place | render.gpu_p99_ms | 5 | 5.73 | ±0.216 | 3.043 | 2 |
| mine_place | render.gpu_wait_p50_ms | 5 | 2.783 | ±2.295 | 66.424 | 0 |
| mine_place | run.wall_s | 5 | 8.022 | ±0.004 | 0.038 | 0 |
| mine_place | tick.tps | 5 | 20.069 | ±0.009 | 0.036 | 0 |
| mine_place | tick.mspt | 5 | 5.173 | ±0.824 | 12.832 | 0 |
| mine_place | tick.mspt_max | 5 | 7.536 | ±1.338 | 14.305 | 0 |
| mine_place | tick.client_ms | 5 | 0.439 | ±0.093 | 17.102 | 0 |
| mine_place | cpu.phase_prepare_ms | 5 | 0.304 | ±0.09 | 23.945 | 1 |
| mine_place | cpu.phase_render_ms | 5 | 0.834 | ±0.284 | 27.479 | 1 |
| mine_place | cpu.phase_tick_ms | 5 | 0.041 | ±0.026 | 50.076 | 0 |
| mine_place | cpu.phase_update_ms | 5 | 0.038 | ±0.021 | 44.902 | 0 |
| mine_place | cpu.slow_phase_prepare_ms | 5 | 0.823 | ±0.228 | 22.271 | 0 |
| mine_place | cpu.slow_phase_render_ms | 5 | 2.122 | ±0.535 | 20.327 | 1 |
| mine_place | cpu.slow_phase_tick_ms | 5 | 0.254 | ±0.271 | 85.893 | 0 |
| mine_place | cpu.slow_phase_update_ms | 5 | 0.211 | ±0.096 | 36.783 | 0 |
| mine_place | process.rss_peak_mb | 5 | 867.426 | ±28.615 | 2.657 | 2 |
| mine_place | process.rss_steady_mb | 5 | 858.501 | ±12.863 | 1.207 | 2 |
| mine_place | process.rss_samples | 5 | 16.0 | ±- | - | 0 |
| mine_place | process.cpu_cores_used | 5 | 0.607 | ±0.171 | 22.647 | 0 |
| mine_place | process.cpu_seconds | 5 | 4.869 | ±1.369 | 22.648 | 0 |
| mine_place | process.private_peak_mb | 5 | 2084.67 | ±26.278 | 1.015 | 0 |
| mine_place | process.private_steady_mb | 5 | 2067.438 | ±20.387 | 0.794 | 2 |
| mine_place | process.virtual_peak_mb | 5 | 7948.051 | ±36.181 | 0.367 | 2 |
| mine_place | process.virtual_steady_mb | 5 | 7946.451 | ±39.402 | 0.399 | 2 |
| crafting | play.oak_logs_given | 5 | 4.0 | ±- | - | 0 |
| crafting | play.oak_planks | 5 | 16.0 | ±- | - | 0 |
| crafting | render.avg_fps | 5 | 198.896 | ±101.861 | 41.252 | 0 |
| crafting | render.low_1pct_fps | 5 | 99.399 | ±9.516 | 7.711 | 1 |
| crafting | render.low_01pct_fps | 5 | 95.5 | ±9.369 | 7.902 | 1 |
| crafting | render.p50_ms | 5 | 4.888 | ±2.994 | 49.335 | 0 |
| crafting | render.p95_ms | 5 | 9.292 | ±0.827 | 7.169 | 1 |
| crafting | render.p99_ms | 5 | 9.887 | ±1.039 | 8.468 | 1 |
| crafting | render.p999_ms | 5 | 10.439 | ±1.014 | 7.828 | 1 |
| crafting | render.max_ms | 5 | 10.631 | ±1.206 | 9.138 | 1 |
| crafting | render.frames | 5 | 1592.8 | ±815.895 | 41.261 | 0 |
| crafting | render.cpu_p50_ms | 5 | 1.217 | ±0.478 | 31.617 | 1 |
| crafting | render.cpu_p99_ms | 5 | 3.206 | ±1.302 | 32.709 | 1 |
| crafting | render.gpu_p50_ms | 5 | 3.91 | ±3.385 | 69.741 | 0 |
| crafting | render.gpu_p99_ms | 5 | 6.118 | ±0.294 | 3.865 | 0 |
| crafting | render.gpu_wait_p50_ms | 5 | 3.59 | ±2.95 | 66.185 | 0 |
| crafting | run.wall_s | 5 | 8.03 | ±0.01 | 0.097 | 0 |
| crafting | tick.tps | 5 | 20.074 | ±0.062 | 0.247 | 2 |
| crafting | tick.mspt | 5 | 3.628 | ±1.06 | 23.536 | 0 |
| crafting | tick.mspt_max | 5 | 5.418 | ±1.834 | 27.271 | 0 |
| crafting | tick.client_ms | 5 | 0.4 | ±0.077 | 15.461 | 1 |
| crafting | cpu.phase_prepare_ms | 5 | 0.355 | ±0.101 | 22.834 | 1 |
| crafting | cpu.phase_render_ms | 5 | 0.921 | ±0.386 | 33.774 | 1 |
| crafting | cpu.phase_tick_ms | 5 | 0.046 | ±0.022 | 38.979 | 0 |
| crafting | cpu.phase_update_ms | 5 | 0.044 | ±0.02 | 37.428 | 0 |
| crafting | cpu.slow_phase_prepare_ms | 5 | 0.789 | ±0.147 | 15.022 | 0 |
| crafting | cpu.slow_phase_render_ms | 5 | 2.28 | ±1.222 | 43.161 | 2 |
| crafting | cpu.slow_phase_tick_ms | 5 | 0.283 | ±0.192 | 54.694 | 0 |
| crafting | cpu.slow_phase_update_ms | 5 | 0.24 | ±0.11 | 36.732 | 1 |
| crafting | process.rss_peak_mb | 5 | 897.246 | ±17.241 | 1.548 | 1 |
| crafting | process.rss_steady_mb | 5 | 866.816 | ±19.783 | 1.838 | 0 |
| crafting | process.rss_samples | 5 | 15.6 | ±0.68 | 3.511 | 0 |
| crafting | process.cpu_cores_used | 5 | 0.482 | ±0.195 | 32.554 | 0 |
| crafting | process.cpu_seconds | 5 | 3.875 | ±1.564 | 32.501 | 0 |
| crafting | process.private_peak_mb | 5 | 2258.583 | ±66.718 | 2.379 | 1 |
| crafting | process.private_steady_mb | 5 | 2025.748 | ±20.197 | 0.803 | 2 |
| crafting | process.virtual_peak_mb | 5 | 8151.251 | ±73.483 | 0.726 | 0 |
| crafting | process.virtual_steady_mb | 5 | 7984.851 | ±33.891 | 0.342 | 0 |
| combat | play.attacks | 5 | 1.0 | ±- | - | 0 |
| combat | play.action_s | 5 | 0.401 | ±0.034 | 6.909 | 0 |
| combat | combat.health_before | 5 | 20.0 | ±- | - | 0 |
| combat | combat.health_after | 5 | 18.575 | ±- | - | 0 |
| combat | render.avg_fps | 5 | 278.6 | ±155.982 | 45.098 | 0 |
| combat | render.low_1pct_fps | 5 | 100.398 | ±13.924 | 11.171 | 0 |
| combat | render.low_01pct_fps | 5 | 90.492 | ±22.018 | 19.599 | 1 |
| combat | render.p50_ms | 5 | 3.888 | ±3.032 | 62.82 | 0 |
| combat | render.p95_ms | 5 | 7.804 | ±2.054 | 21.204 | 0 |
| combat | render.p99_ms | 5 | 9.447 | ±1.001 | 8.538 | 0 |
| combat | render.p999_ms | 5 | 11.159 | ±2.983 | 21.533 | 1 |
| combat | render.max_ms | 5 | 11.876 | ±4.19 | 28.416 | 1 |
| combat | render.frames | 5 | 2229.6 | ±1248.072 | 45.09 | 0 |
| combat | render.cpu_p50_ms | 5 | 1.25 | ±0.486 | 31.319 | 0 |
| combat | render.cpu_p99_ms | 5 | 3.097 | ±0.842 | 21.889 | 0 |
| combat | render.gpu_p50_ms | 5 | 2.958 | ±3.235 | 88.087 | 0 |
| combat | render.gpu_p99_ms | 5 | 5.844 | ±0.32 | 4.408 | 0 |
| combat | render.gpu_wait_p50_ms | 5 | 2.537 | ±2.71 | 86.047 | 0 |
| combat | run.wall_s | 5 | 8.026 | ±0.009 | 0.093 | 1 |
| combat | tick.tps | 5 | 20.06 | ±0.023 | 0.093 | 1 |
| combat | tick.mspt | 5 | 3.735 | ±0.434 | 9.355 | 0 |
| combat | tick.mspt_max | 5 | 5.378 | ±1.036 | 15.51 | 0 |
| combat | tick.client_ms | 5 | 0.473 | ±0.03 | 5.16 | 2 |
| combat | cpu.phase_prepare_ms | 5 | 0.352 | ±0.081 | 18.545 | 0 |
| combat | cpu.phase_render_ms | 5 | 0.952 | ±0.365 | 30.881 | 0 |
| combat | cpu.phase_tick_ms | 5 | 0.043 | ±0.03 | 56.327 | 0 |
| combat | cpu.phase_update_ms | 5 | 0.032 | ±0.018 | 44.492 | 0 |
| combat | cpu.slow_phase_prepare_ms | 5 | 0.771 | ±0.151 | 15.802 | 0 |
| combat | cpu.slow_phase_render_ms | 5 | 2.329 | ±0.775 | 26.785 | 1 |
| combat | cpu.slow_phase_tick_ms | 5 | 0.317 | ±0.206 | 52.362 | 0 |
| combat | cpu.slow_phase_update_ms | 5 | 0.145 | ±0.091 | 50.623 | 1 |
| combat | process.rss_peak_mb | 5 | 877.326 | ±14.593 | 1.34 | 0 |
| combat | process.rss_steady_mb | 5 | 874.789 | ±14.168 | 1.305 | 0 |
| combat | process.rss_samples | 5 | 15.8 | ±0.555 | 2.83 | 1 |
| combat | process.cpu_cores_used | 5 | 0.622 | ±0.143 | 18.482 | 0 |
| combat | process.cpu_seconds | 5 | 4.994 | ±1.149 | 18.536 | 0 |
| combat | process.private_peak_mb | 5 | 2031.66 | ±23.871 | 0.946 | 0 |
| combat | process.private_steady_mb | 5 | 2023.009 | ±21.73 | 0.865 | 0 |
| combat | process.virtual_peak_mb | 5 | 7988.013 | ±33.382 | 0.337 | 0 |
| combat | process.virtual_steady_mb | 5 | 7988.013 | ±33.382 | 0.337 | 0 |
| redstone | redstone.piston_extended | 5 | 1.0 | ±- | - | 0 |
| redstone | redstone.lamp_lit | 5 | 1.0 | ±- | - | 0 |
| redstone | redstone.hopper_moved | 5 | 5.0 | ±- | - | 0 |
| redstone | render.avg_fps | 5 | 244.364 | ±87.578 | 28.868 | 1 |
| redstone | render.low_1pct_fps | 5 | 97.082 | ±6.726 | 5.58 | 1 |
| redstone | render.low_01pct_fps | 5 | 89.779 | ±6.934 | 6.221 | 0 |
| redstone | render.p50_ms | 5 | 3.681 | ±2.278 | 49.85 | 1 |
| redstone | render.p95_ms | 5 | 8.963 | ±1.552 | 13.949 | 2 |
| redstone | render.p99_ms | 5 | 9.928 | ±0.667 | 5.409 | 2 |
| redstone | render.p999_ms | 5 | 10.998 | ±0.854 | 6.258 | 0 |
| redstone | render.max_ms | 5 | 11.372 | ±0.78 | 5.528 | 0 |
| redstone | render.frames | 5 | 1955.2 | ±700.535 | 28.861 | 1 |
| redstone | render.cpu_p50_ms | 5 | 1.102 | ±0.344 | 25.185 | 1 |
| redstone | render.cpu_p99_ms | 5 | 3.188 | ±0.824 | 20.811 | 0 |
| redstone | render.gpu_p50_ms | 5 | 2.536 | ±2.57 | 81.644 | 1 |
| redstone | render.gpu_p99_ms | 5 | 6.417 | ±0.178 | 2.234 | 1 |
| redstone | render.gpu_wait_p50_ms | 5 | 2.38 | ±2.085 | 70.563 | 1 |
| redstone | run.wall_s | 5 | 8.017 | ±0.006 | 0.055 | 0 |
| redstone | tick.tps | 5 | 20.082 | ±0.014 | 0.056 | 0 |
| redstone | tick.mspt | 5 | 3.419 | ±0.866 | 20.41 | 1 |
| redstone | tick.mspt_max | 5 | 5.203 | ±0.834 | 12.917 | 0 |
| redstone | tick.client_ms | 5 | 0.434 | ±0.051 | 9.531 | 0 |
| redstone | cpu.phase_prepare_ms | 5 | 0.273 | ±0.063 | 18.475 | 0 |
| redstone | cpu.phase_render_ms | 5 | 0.917 | ±0.277 | 24.313 | 1 |
| redstone | cpu.phase_tick_ms | 5 | 0.04 | ±0.023 | 46.925 | 1 |
| redstone | cpu.phase_update_ms | 5 | 0.029 | ±0.013 | 36.574 | 2 |
| redstone | cpu.slow_phase_prepare_ms | 5 | 0.654 | ±0.13 | 15.958 | 0 |
| redstone | cpu.slow_phase_render_ms | 5 | 2.692 | ±0.696 | 20.835 | 0 |
| redstone | cpu.slow_phase_tick_ms | 5 | 0.272 | ±0.195 | 57.757 | 0 |
| redstone | cpu.slow_phase_update_ms | 5 | 0.089 | ±0.039 | 35.147 | 0 |
| redstone | process.rss_peak_mb | 5 | 876.487 | ±14.744 | 1.355 | 0 |
| redstone | process.rss_steady_mb | 5 | 876.137 | ±14.685 | 1.35 | 0 |
| redstone | process.rss_samples | 5 | 15.6 | ±0.68 | 3.511 | 0 |
| redstone | process.cpu_cores_used | 5 | 0.523 | ±0.15 | 23.163 | 1 |
| redstone | process.cpu_seconds | 5 | 4.191 | ±1.206 | 23.188 | 1 |
| redstone | process.private_peak_mb | 5 | 2048.588 | ±21.061 | 0.828 | 0 |
| redstone | process.private_steady_mb | 5 | 2041.984 | ±18.186 | 0.717 | 0 |
| redstone | process.virtual_peak_mb | 5 | 7980.013 | ±35.586 | 0.359 | 0 |
| redstone | process.virtual_steady_mb | 5 | 7976.813 | ±36.845 | 0.372 | 0 |
| entities | play.spawn_s | 5 | 9.997 | ±0.017 | 0.134 | 0 |
| entities | entities.mobs | 5 | 199.8 | ±0.555 | 0.224 | 1 |
| entities | entities.spawned | 5 | 200.0 | ±- | - | 0 |
| entities | render.avg_fps | 5 | 111.879 | ±51.44 | 37.035 | 0 |
| entities | render.low_1pct_fps | 5 | 65.775 | ±4.629 | 5.669 | 0 |
| entities | render.low_01pct_fps | 5 | 64.022 | ±5.208 | 6.552 | 0 |
| entities | render.p50_ms | 5 | 9.265 | ±4.076 | 35.439 | 0 |
| entities | render.p95_ms | 5 | 14.189 | ±0.718 | 4.077 | 0 |
| entities | render.p99_ms | 5 | 14.902 | ±0.906 | 4.899 | 0 |
| entities | render.p999_ms | 5 | 15.66 | ±1.329 | 6.838 | 0 |
| entities | render.max_ms | 5 | 15.69 | ±1.304 | 6.696 | 0 |
| entities | render.frames | 5 | 895.8 | ±411.239 | 36.978 | 0 |
| entities | render.cpu_p50_ms | 5 | 2.294 | ±0.788 | 27.649 | 0 |
| entities | render.cpu_p99_ms | 5 | 5.435 | ±2.159 | 31.998 | 1 |
| entities | render.gpu_p50_ms | 5 | 7.977 | ±3.227 | 32.583 | 0 |
| entities | render.gpu_p99_ms | 5 | 10.044 | ±0.145 | 1.161 | 1 |
| entities | render.gpu_wait_p50_ms | 5 | 6.93 | ±3.864 | 44.911 | 0 |
| entities | run.wall_s | 5 | 8.03 | ±0.01 | 0.1 | 0 |
| entities | tick.tps | 5 | 20.049 | ±0.024 | 0.096 | 0 |
| entities | tick.mspt | 5 | 4.577 | ±1.131 | 19.914 | 0 |
| entities | tick.mspt_max | 5 | 6.947 | ±1.428 | 16.553 | 0 |
| entities | tick.client_ms | 5 | 0.549 | ±0.132 | 19.348 | 1 |
| entities | cpu.phase_prepare_ms | 5 | 1.246 | ±0.411 | 26.598 | 1 |
| entities | cpu.phase_render_ms | 5 | 1.116 | ±0.329 | 23.754 | 1 |
| entities | cpu.phase_tick_ms | 5 | 0.111 | ±0.06 | 43.777 | 0 |
| entities | cpu.phase_update_ms | 5 | 0.046 | ±0.02 | 34.433 | 0 |
| entities | cpu.slow_phase_prepare_ms | 5 | 3.073 | ±1.166 | 30.579 | 0 |
| entities | cpu.slow_phase_render_ms | 5 | 2.138 | ±0.561 | 21.155 | 1 |
| entities | cpu.slow_phase_tick_ms | 5 | 0.682 | ±0.437 | 51.602 | 2 |
| entities | cpu.slow_phase_update_ms | 5 | 0.154 | ±0.103 | 53.68 | 0 |
| entities | process.rss_peak_mb | 5 | 882.717 | ±14.196 | 1.295 | 0 |
| entities | process.rss_steady_mb | 5 | 880.495 | ±14.329 | 1.311 | 0 |
| entities | process.rss_samples | 5 | 15.6 | ±0.68 | 3.511 | 0 |
| entities | process.cpu_cores_used | 5 | 0.428 | ±0.08 | 14.971 | 0 |
| entities | process.cpu_seconds | 5 | 3.441 | ±0.64 | 14.979 | 0 |
| entities | process.private_peak_mb | 5 | 2000.019 | ±43.401 | 1.748 | 0 |
| entities | process.private_steady_mb | 5 | 1989.741 | ±40.905 | 1.656 | 0 |
| entities | process.virtual_peak_mb | 5 | 7964.013 | ±33.382 | 0.338 | 0 |
| entities | process.virtual_steady_mb | 5 | 7964.013 | ±33.382 | 0.338 | 0 |
| world_ops | world.cold_load_ms | 20 | 6864.656 | ±755.289 | 23.509 | 1 |
| world_ops | world.cold_generated_chunks | 20 | 637.0 | ±- | - | 0 |
| world_ops | world.cold_meshed_sections | 20 | 16413.75 | ±676.246 | 8.803 | 1 |
| world_ops | world.resident_chunks | 20 | 637.0 | ±- | - | 0 |
| world_ops | world.warm_load_ms | 20 | 6795.276 | ±314.559 | 9.891 | 3 |
| world_ops | world.warm_speedup | 5 | 1.01 | ±0.151 | 12.043 | 0 |
| world_ops | render.avg_fps | 5 | 291.333 | ±77.736 | 21.493 | 2 |
| world_ops | render.low_1pct_fps | 5 | 105.493 | ±16.249 | 12.407 | 0 |
| world_ops | render.low_01pct_fps | 5 | 49.988 | ±26.81 | 43.201 | 0 |
| world_ops | render.p50_ms | 5 | 3.312 | ±0.947 | 23.024 | 0 |
| world_ops | render.p95_ms | 5 | 7.038 | ±1.218 | 13.937 | 1 |
| world_ops | render.p99_ms | 5 | 7.697 | ±0.63 | 6.593 | 0 |
| world_ops | render.p999_ms | 5 | 8.441 | ±0.82 | 7.823 | 0 |
| world_ops | render.max_ms | 5 | 46.732 | ±24.029 | 41.418 | 0 |
| world_ops | render.frames | 5 | 2332.0 | ±622.373 | 21.498 | 2 |
| world_ops | render.cpu_p50_ms | 5 | 0.804 | ±0.151 | 15.114 | 2 |
| world_ops | render.cpu_p99_ms | 5 | 2.753 | ±0.307 | 8.996 | 0 |
| world_ops | render.gpu_p50_ms | 5 | 2.716 | ±1.441 | 42.754 | 0 |
| world_ops | render.gpu_p99_ms | 5 | 4.104 | ±0.386 | 7.568 | 0 |
| world_ops | render.gpu_wait_p50_ms | 5 | 2.334 | ±0.88 | 30.384 | 0 |
| world_ops | run.wall_s | 5 | 8.027 | ±0.013 | 0.129 | 0 |
| world_ops | tick.tps | 5 | 20.008 | ±0.062 | 0.249 | 0 |
| world_ops | tick.mspt | 5 | 4.952 | ±0.518 | 8.427 | 1 |
| world_ops | tick.mspt_max | 5 | 8.059 | ±1.256 | 12.551 | 0 |
| world_ops | tick.client_ms | 5 | 0.532 | ±0.092 | 13.926 | 0 |
| world_ops | cpu.phase_prepare_ms | 5 | 0.246 | ±0.031 | 10.138 | 2 |
| world_ops | cpu.phase_render_ms | 5 | 0.607 | ±0.138 | 18.291 | 2 |
| world_ops | cpu.phase_tick_ms | 5 | 0.038 | ±0.009 | 20.044 | 1 |
| world_ops | cpu.phase_update_ms | 5 | 0.051 | ±0.01 | 16.197 | 2 |
| world_ops | cpu.slow_phase_prepare_ms | 5 | 0.644 | ±0.239 | 29.944 | 0 |
| world_ops | cpu.slow_phase_render_ms | 5 | 1.825 | ±0.319 | 14.094 | 0 |
| world_ops | cpu.slow_phase_tick_ms | 5 | 0.318 | ±0.225 | 56.985 | 0 |
| world_ops | cpu.slow_phase_update_ms | 5 | 0.584 | ±0.096 | 13.197 | 2 |
| world_ops | process.rss_peak_mb | 5 | 912.824 | ±11.331 | 1.0 | 2 |
| world_ops | process.rss_steady_mb | 5 | 912.27 | ±11.303 | 0.998 | 2 |
| world_ops | process.rss_samples | 5 | 15.6 | ±0.68 | 3.511 | 0 |
| world_ops | process.cpu_cores_used | 5 | 0.681 | ±0.194 | 22.931 | 0 |
| world_ops | process.cpu_seconds | 5 | 5.466 | ±1.554 | 22.906 | 0 |
| world_ops | process.private_peak_mb | 5 | 2043.13 | ±124.768 | 4.919 | 1 |
| world_ops | process.private_steady_mb | 5 | 1959.617 | ±74.739 | 3.072 | 1 |
| world_ops | process.virtual_peak_mb | 5 | 7981.626 | ±160.679 | 1.622 | 1 |
| world_ops | process.virtual_steady_mb | 5 | 7885.463 | ±96.395 | 0.985 | 0 |
| mixed | render.avg_fps | 5 | 146.313 | ±107.196 | 59.014 | 0 |
| mixed | render.low_1pct_fps | 5 | 38.335 | ±16.512 | 34.696 | 0 |
| mixed | render.low_01pct_fps | 5 | 27.718 | ±11.837 | 34.398 | 0 |
| mixed | render.p50_ms | 5 | 10.691 | ±11.238 | 84.671 | 0 |
| mixed | render.p95_ms | 5 | 19.136 | ±13.535 | 56.974 | 0 |
| mixed | render.p99_ms | 5 | 24.59 | ±13.281 | 43.504 | 0 |
| mixed | render.p999_ms | 5 | 31.415 | ±10.624 | 27.241 | 0 |
| mixed | render.max_ms | 5 | 53.388 | ±18.027 | 27.198 | 0 |
| mixed | render.frames | 5 | 3074.4 | ±2259.18 | 59.191 | 0 |
| mixed | render.cpu_p50_ms | 5 | 1.419 | ±0.396 | 22.463 | 0 |
| mixed | render.cpu_p99_ms | 5 | 3.933 | ±1.313 | 26.893 | 0 |
| mixed | render.gpu_p50_ms | 5 | 9.939 | ±11.082 | 89.813 | 0 |
| mixed | render.gpu_p99_ms | 5 | 23.125 | ±13.365 | 46.554 | 0 |
| mixed | render.gpu_wait_p50_ms | 5 | 9.115 | ±10.72 | 94.733 | 0 |
| mixed | run.wall_s | 10 | 21.051 | ±0.219 | 1.456 | 0 |
| mixed | play.actions | 5 | 114.4 | ±6.12 | 4.309 | 0 |
| mixed | play.action_s | 5 | 21.051 | ±0.404 | 1.545 | 0 |
| mixed | tick.tps | 5 | 19.998 | ±0.02 | 0.081 | 0 |
| mixed | process.rss_peak_mb | 5 | 918.634 | ±15.617 | 1.369 | 1 |
| mixed | process.rss_steady_mb | 5 | 917.626 | ±14.648 | 1.286 | 1 |
| mixed | process.rss_samples | 5 | 41.6 | ±1.11 | 2.15 | 0 |
| mixed | process.cpu_cores_used | 5 | 0.435 | ±0.18 | 33.259 | 0 |
| mixed | process.cpu_seconds | 5 | 9.159 | ±3.81 | 33.506 | 0 |
| mixed | process.private_peak_mb | 5 | 2021.957 | ±41.18 | 1.641 | 0 |
| mixed | process.private_steady_mb | 5 | 2010.074 | ±36.904 | 1.479 | 0 |
| mixed | process.virtual_peak_mb | 5 | 7898.263 | ±68.917 | 0.703 | 0 |
| mixed | process.virtual_steady_mb | 5 | 7898.263 | ±68.917 | 0.703 | 0 |
| mixed | memory.rss_slope_mb_per_min | 5 | -6.987 | ±28.107 | 324.012 | 1 |

## Correctness checks

- PASS `idle`: frames drawn (expected > 10, got 4506)
- PASS `idle`: ticks advanced (expected > 1, got 160.5)
- PASS `idle`: tick rate plausible (expected > 5 tps, got 20.062)
- PASS `walk`: player moved (expected > 3 blocks, got 16.88)
- PASS `explore`: new terrain generated (expected > 0 chunks, got 1080)
- PASS `explore`: terrain resident (expected > 0 chunks, got 637)
- PASS `explore`: frames drawn (expected > 10, got 5873)
- PASS `mine_place`: blocks placed (expected >= 6, got 8)
- PASS `mine_place`: blocks broken (expected >= 6, got 8)
- PASS `crafting`: craft result (expected oak_planks, got oak_planks)
- PASS `crafting`: planks obtained (expected >= 1, got 16)
- PASS `combat`: target took damage (expected < 20.0, got 18.575000762939453)
- PASS `redstone`: piston extends (expected piston_head, got minecraft:piston_head)
- PASS `redstone`: piston retracts (expected air, got minecraft:air)
- PASS `redstone`: repeater lights lamp (expected lit=true, got minecraft:redstone_lamp)
- PASS `redstone`: lamp turns off (expected lit=false, got minecraft:redstone_lamp)
- PASS `redstone`: hopper transfers (expected >= 1 item, got 5)
- PASS `entities`: mobs spawned (expected >= 160, got 200)
- PASS `entities`: frames drawn (expected > 10, got 1328)
- PASS `world_ops`: cycle 1 generated terrain (expected > 0 chunks, got 637)
- PASS `world_ops`: cycle 1 chunks resident (expected >= 361 chunks, got 637)
- PASS `world_ops`: cycle 2 generated terrain (expected > 0 chunks, got 637)
- PASS `world_ops`: cycle 2 chunks resident (expected >= 361 chunks, got 637)
- PASS `world_ops`: cycle 3 generated terrain (expected > 0 chunks, got 637)
- PASS `world_ops`: cycle 3 chunks resident (expected >= 361 chunks, got 637)
- PASS `world_ops`: cycle 4 generated terrain (expected > 0 chunks, got 637)
- PASS `world_ops`: cycle 4 chunks resident (expected >= 361 chunks, got 637)
- PASS `mixed`: actions completed (expected > 10, got 118)
- PASS `mixed`: ticks advanced (expected > 20, got 424)
- PASS `mixed`: frames drawn (expected > 10, got 4543)
