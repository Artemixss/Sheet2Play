# Phase 4: recommendation and plan closeout

**Complete with qualifications, 2026-10-08.** Plan `2026-10-06-homr-timing-465`.
The user's request authorized Phase 4's recommendation and closeout only.
[Closed plan](../../../../../plans/archive/2026-10-06-homr-timing-465.done.md),
[acceptance ledger](acceptance-ledger.md), [adoption proposal](adoption-proposal.md),
[handoff](../handoff.md).

## Recommendation

Recommend **pinned no-title HOMR 465 for the next bounded, opt-in app trial and
integration review**. Keep shipped HOMR **426** as the installed app's default
until the proposed checks pass and the user separately authorizes adoption.
This is the plan's qualified viable-candidate outcome. No demonstrated runtime
incompatibility rules out a controlled trial; installed-app readiness remains
unverified and several integration contracts are incomplete.

The recommendation applies to the measured source/weights/pipeline bundle,
not weights alone: source `33baa326900faa12702df8c4bdcbea034a3d6a34`, matching
465 FP16 encoder/decoder `465-597144cab54c8f6d0f6c9619df5c5312694eadd6`, native
`title_detection=false`, unchanged production normalizer and the settings in
[candidate configuration](../phase2/candidate-configuration.json).
The isolated Phase 3 C# direct-XML revision branch is an integration prototype;
it is not a changed transcription profile or a production patch.

For the user, the plan found a promising existing checkpoint and established
why a controlled trial is worth attempting. It did not train a new model,
replace the current engine or publish a new `dist/Sheet2Play.exe`. Checkpoint
455 was an earlier comparison candidate; it is not the shipped checkpoint.

## Measured benefit and its limits

Phase 2's frozen fresh comparison covers 59 previously observed pages in
18 compositions. Its paired composition-macro results include the explicit
control export failure as zero. [Phase 2 acceptance](../phase2/REPORT.md),
[full comparison](../phase2/comparison-report.json).

| Measure | Pinned 465 | Fresh shipped-source 426 control |
| --- | ---: | ---: |
| Primary pitch/onset/duration F1 | 0.5313290603 | 0.4139483028 |
| Pitch/onset F1 | 0.5530193830 | 0.4374030143 |
| Pitch F1 | 0.9796934040 | 0.9700843734 |
| Missing / extra exact events | 11,139 / 11,325 | 14,658 / 14,289 |
| Complete reference chords / 5,894 | 2,861 | 1,860 |
| Usable XML conversions | 59/59 | 58/59 |

Primary difference is **+0.1173807575**, paired bootstrap 95% interval
**[0.0240277078, 0.2202143270]**, exact one-sided/Holm **p=0.0174827576** for
the one preregistered claim. Twelve composition differences are positive and
six negative. This supports superiority on this observed screen. It does not
establish universal improvement, untouched generalization, a paired advantage
over verified fine-tuned HOMR or the production promotion gate.

The conditional duration diagnostics are also retained: majority baseline
0.4048/0.4629, balanced accuracy 0.5770/0.6252 and macro-F1 0.5786/0.6099 for
candidate/control, with full ordered matrices in the comparison JSON. Both
predict multiple classes. Different matched-note populations prevent interpreting
these as an isolated duration-classifier ranking. Staff coverage is recorded
there by notation index; the four-position fixture verifies two voices per staff,
not an annotated right/left-hand accuracy claim. Human correction time was not measured.

Matched capture timing is descriptive: candidate/control mean 15.6904/15.5420
seconds before the reported RAM upgrade, and 15.6509/15.0261 after fresh RAM
admission. The cross-transition page is excluded from matched performance claims.
Those captures do not establish installed-app p95, cold-start or unattended
performance. Historical title-OCR allocation failures and the unexplained Phase 2
deadline remain preserved; the upgrade is not a verified remedy for their causes.

## Regression and conversion decisions

| Evidence | Verified result | Decision implication |
| --- | --- | --- |
| `offset_entry`, `triplet_vs_duple` | Two generated measures become exact | Retain corrected controls in future trial checks |
| `three_voices` | Extra A5 already in raw recognition; export/normalization preserve it; F1 0.9333 vs 1.0 | Known recognition harm; no justified downstream deletion |
| `tuplet_aligned` | One bracket row disappears between saved staff stages; lower durations are wrong in raw tokens; native clock explains later onsets; F1 0.125 vs 1.0 | Severe local rhythm harm; exact crop/model initiating mechanism remains unverified |
| Fixed-token exports and conversion | 12 generated exports replay in both runtimes; 32 actual published-Bridge/app-Python/research-C#/cache-MIDI/controller inputs pass | Bounded import/export/conversion compatibility supports a trial |
| Direct-XML C# contract | One missing revision branch demonstrated and repaired in the research source copy | Prototype passes; default runtime/model/cache branches still need work if this route is used |
| Independent-voice tie limitation | Existing production normalizer emits six events where four are required | Retain explicit limitation; do not insert the restricted research parser into production |

[Phase 3 report](../phase3/REPORT.md) and its
[ledger](../phase3/acceptance-ledger.md) distinguish demonstrated stages from
hypotheses. Perfect recognition and identification of every internal model
cause are not closure requirements. The known regressions remain visible;
no speculative crop, duration, exporter or normalizer repair was selected.
Pinned source already contains #171/#178, and no demonstrated 465 blocker
justifies entering the conditional shipped-exporter fallback.

Phase 3 validation remains the applicable cached evidence: **56 focused cases**,
**417 Research/Bridge cases with two skips and zero failures/errors**, and
**74/74 fresh research frontend tests**. These validate the exercised paths,
not candidate GPU inference inside the launched installed EXE, complete default
XML import, persistent-library integration or physical audio. Preserve the
calibrated 0.055-second audio offset. Title-on equivalence is unverified;
the recommendation selects the measured no-title profile.

## Adoption proposal and remaining evidence

[The concrete proposal](adoption-proposal.md) fixes candidate paths/settings,
per-process source isolation, visible opt-in selection, distinct revision/cache
identity, scratch library, guarded installed-runtime inference, conversion and
physical-playback checks. It separates bounded trial acceptance from a later
eligible confirmation and production decision. All are proposed follow-up work;
Phase 4 executes none of them.

The [frozen scoring/promotion protocol](../../phase1/scoring-protocol.json)
and [historical comparison gate](../../../../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md)
remain unchanged: +0.03 primary F1 over verified fine-tuned HOMR with statistical
support, at most 0.01 pitch-F1 loss, failure-rate and failure-penalized OMR-NED
increases at most 0.01, no conversion/stitching corruption and practical eligibility.
The current plan did not measure a candidate paired comparison against the
verified fine-tune, failure-penalized NED or untouched confirmation, so it cannot
declare that gate passed. App publication requires separate authorization and
the release gate after integration is accepted.

## Preservation and lifecycle

This artifact-only review recomputed no score and reran no inference or test.
[Starting preservation](preservation-before.json) reverified all **7,630 Phase 2
files, 98 protected/pinned entries and 38 production source files**. It additionally
snapshotted **205 Phase 3 files, two frozen rule documents and eight published
EXE/Bridge Python files** for the closing check. Decision values are extracted in
[review evidence](review-evidence.json); final hashes/link results are recorded
in `audit.json`. [Execution record](job-record.md) and guarded receipts preserve
commands, live-process checks, resource admission and outcomes.

The 85% RAM/commit stops, 4 GiB reserve/worker cap, 16-process containment and
deadlines remain; the offline/Git gate applies to both audits. No downloads,
dependency changes, cloud spending, training, app/library write or publication.

All four phases are complete with the stated qualifications. The complete plan
is archived as `.done.md`; `MAIN_PLAN.md` is a no-active-plan pointer. The next
decision is whether to select and authorize the bounded 465 trial/integration
proposal. No subsequent execution is authorized by this closeout.
