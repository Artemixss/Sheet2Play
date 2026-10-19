# Current upstream exporter and run 480 for the app

**Plan ID:** `2026-10-17-upstream-exporter-480`
**Status:** Selected by the user on 2026-10-17 as a separate bounded task; authorized on
2026-10-18 ("approved, download run 480 weights and test the new things"). The test set
passed the pre-registered rule, and on 2026-10-19 the user made 480 the app default with 465 as
the secondary. Open: two large single-score regressions, flagged for investigation. The
[handoff](../Research/omr/reports/upstream-480/handoff.md) records state and the next action.
**Evidence:** [October 17 upstream audit](../Research/omr/reports/diagnosis/UPSTREAM_AUDIT_2026-10-17.md).

## Goal

Find out whether moving the app's 465 runtime from `33baa32` to current upstream main, and
whether run 480, improve the app, without changing the shipped default until measured.

## Steps

1. **Provision a candidate runtime beside the current one.** Upstream main
   `ab369ac54277afab582afa4725441f7cbba76593`, under a new `Bridge/.runtime/` profile with
   its own `runtime_profile_sha256`, reusing the existing launcher and identity checks. The
   current 465 runtime and its caches stay untouched. Run 480's weights are a ~100 MB
   download from upstream's release; ask the user before downloading.
2. **Retry the one failed migration item** with 465 weights on the new exporter. Upstream
   removed the assertion that failed it; record whether it now converts or fails elsewhere.
3. **Score on exact labels**, with 465 weights on the old and new exporter (separating the
   exporter effect) and 480 weights on the new exporter. Use the frozen 59-page/18-composition
   sample and its scoring as a new candidate run, without altering historical results. Add the
   displacement plan's engraved set if it exists by then. Report composition-macro
   pitch/onset/duration F1 with paired statistics, plus `tuplet_aligned` and the other
   generated controls.
4. **Check practical fit.** 480 has no FP16 decoder, so measure p95 page latency against the
   465 control under the existing 2x gate, plus VRAM within the 90% admission.

## Accept and decide

Adopt a new pin or 480 as the app default only under the criterion the user chose for 465:
measured aggregate improvement plus passing app checks (release gate, fallback, cache
identity). A new default re-recognizes the library through the existing migration path; old
caches stay available. Report regressions as plainly as gains.

**Out of scope:** displacement correction, PR #146 re-timing (the displacement plan's Phase 3),
training, cloud spending.
