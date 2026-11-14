# Architecture and code-quality audit

Source review of the hot paths, performed with `rg`; Phase 2 added bounded traces and the measured
results in [profiling.md](profiling.md). Ranked by severity/confidence. Full line references are
from `eb1e547`, with Phase 2 status beside each finding.

## Confirmed defects

None with a concrete crash or corruption trigger were found in the paths reviewed. Mechanisms that
looked suspicious but traced sound:

- `torch_toggles` in `crates/horizon-world/src/level/redstone.rs` is time-pruned in `torch_tick`
  (60-tick window), bounded and O(n), matching vanilla's `RECENT_TOGGLES`.
- The LAN player-data writer's `Disconnected` branch drains, logs and falls back to inline writes;
  durable saves still wait for completion.
- Mesh-pool recycling and queue caps in streaming/light are bounded; per-face mesher loops do not
  build `String`s.
- `sync_data` caches are cleared on disconnect/title return; two-call flows were traced.

## Suspected hot-path inefficiencies

| # | Finding | Class | Severity | Confidence | Evidence |
|---|---|---|---|---|---|
| 1 | `streaming.rs` uses `lock().unwrap()` on shared queues. A worker panic poisons the mutex and the tick thread's next unwrap panics the game, rather than one worker. Elsewhere the code uses `unwrap_or_else(|e| e.into_inner())`. | Concurrency risk | Medium | High code / unverified trigger | `crates/horizon-client-render/src/streaming.rs:424,444,840,864,946,1008,1042,1313,1337` | **FIXED in Phase 2**: every lock recovers; `try_lock` returns the poisoned guard. Tests pass. |
| 2 | Autosave/durability errors are dropped at call sites (`let _ =`). The error is logged when captured, then `take()`n and unrecoverable; no UI or dedicated event sees it. | Error concealment | Medium | High | `game.rs:7783,13938`; `lan/playerdata.rs:467-472` | **FIXED in Phase 2**: propagate/log with the world root; status only after completed player writes. |
| 3 | `held_name()` rebuilds the styled item name, item id string and rarity lookup every tick; the tool-highlight code only compares it for equality. | Redundant computation + alloc | Low–Medium | High | `game/titles.rs:64-96`; `horizon-client-render/src/hud_overlays.rs:450-465` | **Measured, not changed**: `tick_hud` is absent from the top 16 spans and under 0.7 ms/frame; no allocation profile shows it dominating. |
| 4 | Particle spawn clones a `String`/`Vec<String>` of sprite names per particle; interned atlas indices would remove the heap hit in burst spawns. | Excessive allocation | Low–Medium | High | `horizon-client-render/src/particles.rs:38,50,2121,2139,3340,3469` | **Measured, not changed**: no particle span surfaced in the burst traces; allocation profile needed. |
| 5 | Process-lifetime caches keyed by resources root (`BUILTIN`, `RESOURCE_IDS`, `COMMAND_EXPORTS`, `SHARED`) are unbounded across worlds/servers; a long session hopping roots accumulates MBs. | Unbounded memory | Low (normal) / Medium (long sessions) | High | `game/remote.rs:62`; `game/chat.rs:471,600`; `chunk.rs:296` | **FIXED in Phase 2**: 8-root bounds and 4096 shared sections; evicted `Arc`s stay valid. |
| 6 | `block_properties` is keyed by a registry pointer cast to `usize`. Sound only while registries are leaked/`'static`; a future dropped registry plus realloc is an ABA hazard. A comment pinning the invariant is cheap. | Fragile invariant | Low | Medium | `game/chat.rs:568` | **Documented**; a stable registry id remains backlog item 5. |
| 7 | `tick_guests` builds a `Vec` and does an O(n²) `position()` lookup per connection each tick. Negligible at ≤16 LAN guests. | Minor alloc/algorithm | Low | High | `game/lan_actions.rs:4156-4170` | Open (negligible). |
| 8 | `spawn_mob_raw` result ignored for tadpoles; a failed spawn is silent and parity-visible. | Error concealment | Low | High | `game.rs:6100` | **FIXED in Phase 2**: logs the frogspawn and spawn positions. |

## Unverified

- Runtime cost of 3–5; a profile on a real session would settle ranking.
- `PRELOAD`/`SYNC` behavior with two game instances in one process; only single-instance flows were
  traced.
- Whether `held_name()` runs on the pure-remote path (the remote tick returns before `tick_world`);
  if it does not, finding 3 is lower impact on guests.
- No worker-panic trigger was found for finding 1; the risk is propagation, not a known panic.

## Priority

1. Fix the streaming lock-poison pattern (small, removes a whole-process failure mode).
2. Surface durability errors at the call site or in a user-visible status.
3. Cache the held-item display name and intern particle sprite names only after a profile confirms
   they matter; both are localized.
4. Bound or document the process-lifetime caches; comment the `'static` registry invariant.
