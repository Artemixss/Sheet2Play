# Phase 3 planner review and proposed Phase 4 boundary

**Date:** 2026-10-05. **Owning plan:** [archived owning plan](../archive/2026-10-03-zeus-attribution-repair.superseded.md),
`2026-10-03-zeus-attribution-repair`.
**Decision:** Conditional go for bounded Phase 4 development. Phase 3 execution
and reporting are complete; full acceptance remains incomplete. Start any newly
requested Phase 4 with the validation prerequisites below. This review authorized
no repair, test rerun, inference, screening, training, spending or promotion.

## Evidence reviewed

This review inspected the canonical plan, Phase 2 acceptance closeout, Phase 3
report/handoff, crop and reference reviews, saved JSON/JUnit evidence, and relevant
implementations: actual dataset/wrapper inference, crop boxes, XML tracing,
analysis failure policy, tie ablations, Bridge normalization, HOMR compatibility
verification and strict historical freezing. It did not rely only on the report.

Fresh read-only checks verified all **207 audited artifact hashes** and all **17
experiment source pins**, with no mismatch. The final JUnit independently confirms
**14 failures: 12 Git-guard failures and two historical-freeze failures**. The saved
freeze diagnosis records **33 added metadata entries**, not proof that those
entries can safely be ignored. Saved tie-control results and diagnostic aggregates
match the report. Two contact sheets were independently inspected: clipped
single-staff notation and the duplicated bass fragment are visible. No worker lock
or Python process was present at this review's inspection. No Git command, model
execution or regression rerun was performed.

Evidence: [Phase 2 acceptance](../../Research/omr/reports/zeus-attribution/phase2/closeout-20261004/REPORT.md),
[Phase 3 report](../../Research/omr/reports/zeus-attribution/phase3/REPORT.md),
[experiment manifest](../../Research/omr/reports/zeus-attribution/phase3/experiment-manifest.json),
[artifact audit](../../Research/omr/reports/zeus-attribution/phase3/artifact-audit.json),
[final JUnit](../../Research/omr/reports/zeus-attribution/phase3/resume-20261005-1746/regression-parser-trace-junit.xml),
[freeze differences](../../Research/omr/reports/zeus-attribution/phase3/freeze-differences.json).

## Executed state and supported conclusions

| Area | Verified state | Consequence |
| --- | --- | --- |
| Phase 1 identity | Zeus is the OLiMPiC TensorFlow/LMX recognizer, distinct from Rokot; historical execution-time source remains unverified | Use the fully pinned diagnostic identity for new work; retain the historical limitation |
| Phase 2 scoring | All 295 cached outcomes were rescored symmetrically and independently accepted; Zeus changed from 0.0228105 to 0.0237688 | Numeric serialization was a real shared defect, but does not explain most of the low Zeus score |
| Phase 3 execution | All 15 selected items, 25 crops, 50 outputs and 30 stitched recipe pages completed; actual dataset/direct prediction parity passed for all 25 crops | Fixed execution is finished; repeating the unchanged inference is unnecessary |
| Cropping | Eleven generated single-staff controls have clipped notation; page 6211555 has three detected crops for two engraved systems, including a duplicated bass fragment | The controls do not establish intrinsic recognizer quality under complete inputs; coordinate correctness did not establish coverage |
| Preprocessing | Resized prefixes match for all 25 crops, while all token sequences differ between recipes | Padding/valid-width handling affects decoding; mask-specific causality and the better recipe are unresolved |
| Conversion | Replay preserves all 50 XML hashes, exposes 57 diagnostic lines in 15 outputs, and finds one dropped base-pitch token | Successful return and Bridge acceptance do not establish faithful native-token conversion |
| Stitching | All 30 stitched note-element multisets are preserved | This does not prove backup, attribute, accidental or system-boundary timing semantics |
| Shared ties | The unchanged Bridge keeps six events where the exact controlled input requires four; removing layout or changing voice containers/types does not resolve it | This is a demonstrated shared normalization defect, not an exclusively Zeus defect |
| Validation | 75 focused fixtures pass; saved full suite has 328 passed, 14 failed, two skipped and nine passing subtests | Full green acceptance is unmet; unchanged failures are still failures |

The tie ablation that removes the independent voice reaches F1 1.0 by deleting a
musical event. It is evidence of causality, **not a repair**. The valid acceptance
target retains that voice and produces the four expected sounding events.

The primary Phase 3 diagnostic F1 is **0.0064309 upstream / 0.0041483 wrapper**.
These are item-macro results on the 15 development items, not the historical
59-page/18-composition benchmark. They do not show that upstream universally wins
or that Zeus regressed from 0.0228. Wrapper performance is better on the generated
baseline; both have substantial recognition/timing errors on observed content.

## Acceptance gaps and their role in the next decision

1. **Regression verification is a prerequisite.** Twelve paths fail because the
   recovery policy prevents Git invocation before substantive validation runs.
   Two fail because a live runtime inventory does not equal its historical freeze.
   A Git-free verification design must retain source/model/vocabulary/import-origin
   checks and rejection of altered or missing inputs. Reconcile historical artifact
   verification with separately pinned current-runtime admission. Do not overwrite
   the old freeze, suppress differences, mock success, skip failures or weaken
   identity checks to obtain a green result.
2. **Exact tracing must support the selected repair.** All 30 stitched page traces
   are unavailable: 29 fail the positive-duration check and one has a backup before
   measure start. The music21 fallback observes parser interpretation, including
   inferred timing; it is not independent proof of literal XML event preservation.
   For each repair, record exact supported transitions and structured unsupported
   cases. Do not invent missing durations, infer reference-derived timing or claim
   full end-to-end parity from note counts. The valid tie reproducer already has an
   exact trace and can support a bounded normalization repair. Resolving every
   malformed Zeus page is not a prerequisite for that isolated repair.
3. **Reference limitations restrict claims.** Hidden vocal rests, voice+piano pages,
   atypical generated staff order/register and the ambiguous syncopation rest remain
   qualified. Staff indices reset per part and do not establish hand accuracy.
   Retain all preselected items/failures; do not silently replace, align, reorder or
   correct references after seeing outputs. Additional piano-only controls, if
   needed, get a separately recorded development identity before inference.
4. **Historical provenance and memory initiation remain unresolved limitations.**
   Neither can be reconstructed by rerunning the same model. They do not prohibit
   a fully pinned, guarded new development experiment. Successful memory containment
   is sufficient for guarded admission, not evidence of a durable system/app fix.

## Proposed Phase 4 execution sequence

| Step | Objective and exit evidence | Recommended executor |
| --- | --- | --- |
| 4.0 — Validation prerequisites | Resolve the 14 failures through safe, meaningful verification; preserve frozen evidence and explicit unsupported traces; pass relevant fixtures and the full research/Bridge suite | GPT-6.1 Sol, high for integrity/design decisions; medium for defined changes |
| 4.1 — Shared independent-voice tie repair | Research-only or opt-in normalization variant. Preserve the independent voice; six segments become the four exact sounding events. Check ordinary notes/chords, partial/continued ties, simultaneous same pitches in different voices/staves/parts, gaps, pickups, tuplets and cross-system boundaries. Verify MIDI event preservation before any playback claim | GPT-6.1 Sol, medium for implementation; high for causal acceptance |
| 4.2 — Symbol-safe crop coverage and deduplication | Separately pinned detector/crop variant. Review all 15 fixed inputs before inference; demonstrate retained noteheads, stems, accidentals, tuplets and ledger notation. Remove the demonstrated duplicate without deleting legitimate adjacent systems or staff groups. Report unchanged and changed cases, complete-item failures and event metrics | GPT-6.1 Sol, medium; high if system grouping requires new architecture |
| 4.3 — Remaining Zeus conversion/preprocessing decisions | Make converter errout observable with byte-identical replay first; distinguish grammar/data-loss defects from recoverable warnings. Test an additional padded-input condition retaining original valid-width masking before attributing the recipe difference specifically to masks. Repair only a demonstrated defect, one configuration at a time | GPT-6.1 Sol, high for diagnosis; medium after the remedy is specified |

After each isolated change, review evidence before the next change. Relevant
fixtures precede representative development execution and the complete regression
suite; cached analysis is reused only when identities match. Luna medium is suitable
for prescribed hashes, test runs and log summaries after commands/gates are fixed.
No automatic change of assistant model or effort is made by this review.

The shared tie correction can affect predictions **and references for every
candidate**. It must not be presented as a Zeus-only gain against baselines using
the old normalizer. Any subsequent comparison needs symmetric processing, a new
declared identity and a separately reviewed execution proposal. Production remains
unchanged until measured and separately requested; a shipped change also requires
the release gate.

The Phase 4 endpoint is a supported verdict on the bounded remedies, with all
failures and unresolved cases reported. Zeus superiority is not an exit criterion
or a prerequisite for Phase 5. If the verified pipeline still recognizes poorly,
retain that finding and review Rokot readiness next; do not add repeated tuning or
training simply to keep Zeus work open. Phase 5 remains separately requested.

## Operational and authorization boundary

Use the recorded supervisor: one heavy CPU worker, 85% physical RAM/system commit
stops, 4 GiB commit reserve, at most 4 GiB aggregate worker commit, 16-process
containment and deadlines. Git count/private memory are informational, but agent
Git invocation remains prohibited during recovery. Inspect jobs/locks before any
new execution and retain failures; no automatic pressure retries. Historical GPU
admission contracts remain separate. No cloud spending or training is proposed.

**Next authorized action after this review:** report the decision. A new request
for Phase 4 would start at 4.0, then permit only the remedies/gates selected in
that request. This review does not mark Phase 3 fully accepted or the plan complete.

Documentation verification: all 83 local links across the four changed documents
resolve. This pass changed documentation only; no inference or test suite was rerun.
