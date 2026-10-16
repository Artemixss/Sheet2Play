# Pre-inference crop coverage review — 2026-10-05

Owning plan: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), Phase3 attribution.
All15 inputs and25 saved crops were visually reviewed before Zeus inference.
[Frozen manifest](experiment-manifest.json) pins the identical inputs for both recipes.
[Contact sheets and dimensions](resume-20261005-1746/crop-review/inventory.json)
preserve this review. Preparation completed152.984s, peak RAM59.672%/commit48.863%.

| Inputs | Crop finding | Attribution consequence |
|---|---|---|
| Generated baseline,2 systems | Both complete grand staves and ledger noteheads present; original bass-above-treble engraving retained | Best generated coverage control; atypical staff order still limits model-domain interpretation |
| Other11 generated single-staff controls | Five staff lines retained but upper/lower notes, stems, clef tails or ledger notation visibly meet/cross crop boundaries; same-position-sustain loses substantial low-register content | Incomplete input coverage is established before recognition. Their F1 cannot establish poor recognition under a complete input pipeline |
| 6211535,5 systems | Expected system count and piano staves; some bracket/slur/ledger tails at boundaries | Preserve pitched-content/reference qualifications; no universal coverage claim |
| 6211549,4 systems | Expected systems and final vocal+piano group; low bass ledger notation intersects lower boundaries in early systems | Missing bass content may originate before recognition; final three-staff group differs from piano-only recognizer assumptions |
| 6211555,3 detected vs2 engraved systems | First complete voice+piano group, then an overlapping duplicate bass-staff fragment from that group, then the second complete voice+piano group | Duplicated input and ordinal system mismatch are integration defects. System-local pairing is not musically aligned for this item |

The unchanged `_system_boxes` uses20% of staff-line envelope height above/below
that envelope. This coordinate-space correction does not ensure symbol coverage:
single-staff envelopes are much shorter than grand-staff envelopes. The extra6211555
box is visible in the detector output, not introduced by the crop saver or stitcher.
These are supported input/integration findings, not evidence that reference notes
should be used to reconstruct predictions.

No model output was consulted for crop selection. These actual pipeline crops remain
frozen for both recipes. A coverage remedy or detector deduplication belongs to separately
requested Phase4. Global scores remain unchanged; local diagnostics retain explicit
ordinal-pairing limitations. Poor recognition can be assessed only for complete observed
content and cannot be extrapolated from the clipped controls.
