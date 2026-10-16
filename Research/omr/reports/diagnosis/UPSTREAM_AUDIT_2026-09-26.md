# HOMR upstream model audit — 2026-09-26

**Later update:** The [September 29 delta audit](UPSTREAM_AUDIT_2026-09-29.md) records PR #156's merge and published model 465 weights, PR #168, and issue #167. Statuses below are preserved as observed on September 26.

## Scope and conclusion

Read-only upstream investigation for Sheet2Play. No model, runtime, phase configuration, training job, or evaluation job changed.

The public GitHub inventory contains 100 PRs (96 closed, 4 open), 58 non-PR issues, 652 issue/PR conversation comments, 102 inline review comments, and 8 Discussions. Formal PR review summaries were also retrieved, with no remaining pagination. Titles were screened and model-relevant threads examined in depth; this is not a claim that every attachment, screenshot, external link, or private conversation was inspected. Raw API evidence is retained locally in `Research/omr/.runtime/upstream-audit-20260926/`.

The strongest recommendation remains controlled comparison, not automatic promotion or another broad fine-tune. Upstream has a newer released model, a promising but unreleased voice-representation change, and substantial evidence that simply adding data or epochs is insufficient. No reviewed source establishes a universal 0.63–0.69 rhythm-F1 ceiling.

## What is new relative to the project's diagnosis

The bridge records `homr-0.7.0.post38+457e7c6+pr146`; the installed transformer configuration names model 426. The project's September 16 diagnosis already discusses several failed experiments, PR #156's earlier approach, and #157. Those are not newly discovered fixes. The later model 455 release, #162's synthesis, #156's stem-based retraining, and issues #161/#165 with PR #166 were not covered in that diagnosis.

| Development | Verified status at audit | Relevance |
|---|---|---|
| Model 455 | Default updated September 24; PyTorch and ONNX assets exist | A new pretrained comparison candidate, not demonstrated piano-rhythm improvement |
| #162, training rendering pipeline | Merged September 24 | More realistic beams and corrected slur/tie rendering; reported gains small |
| #156, multiple voices | Open; revised training reported complete September 25 | Directly addresses information missing from the old voice representation |
| #165/#166, repeat-start labels | Issue and proposed fix open | Training image/label mismatch; impact on released weights unquantified |
| #161, time signatures | Open | Inferred and recognized signatures may both appear; downstream interpretation matters |

Sources: [model-update commit](https://github.com/liebharc/homr/commit/a4865663e7278f908d6d1b1a57d549f9ca3d1067), [PyTorch assets](https://github.com/liebharc/homr/releases/tag/checkpoints), [ONNX assets](https://github.com/liebharc/homr/releases/tag/onnx_checkpoints), [#162](https://github.com/liebharc/homr/pull/162), [#156](https://github.com/liebharc/homr/pull/156), [#165](https://github.com/liebharc/homr/issues/165), [#166](https://github.com/liebharc/homr/pull/166), [#161](https://github.com/liebharc/homr/issues/161).

## Important information hidden in comments and closed PRs

### 1. Newer checkpoints have not consistently been better

The September 25 write-up says model 426 regressed on the `tabi` example relative to 414. After applying benchmark corrections, 414 and 426 had similar benchmark scores. Filtering low-resolution examples improved that example without improving the aggregate benchmark; changing the rendering pipeline gave only small gains. More capacity, token-format limitations, and questionable benchmark references are proposed explanations, not established conclusions. [Maintainer's full write-up](https://github.com/liebharc/homr/pull/162#issuecomment-5828017653)

Implication: neither a higher checkpoint number nor a lower upstream error score is sufficient to replace Sheet2Play's model. Evaluate sounding pitches, onsets, durations, and failures under the same scoring contract.

### 2. A substantially larger dataset already failed to deliver a clear gain

A contributor expanded training from approximately 250,000 to 870,000 examples. Reported Polish normalized edit distance (NED) changed from 24.38% to 24.51%, with failures increasing from 2 to 3 out of 112. SMB NED changed from 22.37% to 22.20%, while failures increased from 22 to 24 out of 685. These are essentially flat results, not a compelling improvement. [Training results](https://github.com/liebharc/homr/discussions/129#discussioncomment-17809151)

This is evidence against repeating that particular data-scaling recipe. It does not prove that all synthetic data, targeted examples, or Sheet2Play's own generator are ineffective.

### 3. Several attractive ideas have already produced negative or marginal results

| Experiment | Reported outcome | Interpretation |
|---|---|---|
| [#125 history dropout](https://github.com/liebharc/homr/pull/125) | Full training left metrics essentially unchanged | No demonstrated solution to hallucinations/image ignoring |
| [#147 detector-derived training crops](https://github.com/liebharc/homr/pull/147) | Approximately 4,000 pairs; no observed fine-tuning improvement | That crop-matching experiment was insufficient |
| [#153 resolution/aspect filtering](https://github.com/liebharc/homr/pull/153) | Some visual improvement, benchmark similar | Useful examples can improve without moving the aggregate |
| [#159 alternative rendering](https://github.com/liebharc/homr/pull/159) | Small reported gains; continued in #162 | Rendering fidelity matters, but no breakthrough demonstrated |
| [#85 multiscale feature fusion](https://github.com/liebharc/homr/pull/85) | Added complexity without improvement; idea reverted before merge | A merged PR is not proof the proposed architecture was adopted |
| [#124 invisible tuplets](https://github.com/liebharc/homr/pull/124) | Training behaved essentially as before | A dataset-policy change alone did not resolve the ambiguity |

These experiments used different historical settings. Their numbers cannot be combined into a ranking against current Sheet2Play F1.

### 4. Some rhythm errors are information loss, not insufficient training

In #126, different same-staff voice structures can serialize to the same token sequence. Once that distinction is absent, a downstream converter cannot reliably recover it from tokens alone. #142 separately documents overlapping notes at the same pitch with different durations, including missing tokens. #150 documents chord splitting that overfills a measure. These are distinct failure mechanisms. [#126 discussion](https://github.com/liebharc/homr/pull/126#issuecomment-5024162424), [#142](https://github.com/liebharc/homr/issues/142), [#150](https://github.com/liebharc/homr/issues/150)

The revised #156 uses stem-based voice labeling. Its September 25 training result reports Polish 17.52% and SMB 13.84% benchmark error. These are not onset-duration F1 and do not establish improvement on Sheet2Play's songs. The PR remains open; no matching voice-model asset was identified in the official release lists. Model 455 must not be described as this multi-voice model. [Latest training comment](https://github.com/liebharc/homr/pull/156#issuecomment-5834285814)

A representation can impose an upper bound on a particular dataset, but the bound depends on the examples and scoring. Nothing here establishes 0.69 as a universal maximum. F1 of 0.63 also does not simply mean that 63% of the rhythm is correct: it combines precision and recall under specified note-matching conditions.

### 5. Export and training plumbing can imitate model-quality problems

Issue #99 records swapped slur/articulation inputs in an older ONNX export, fixed by replacing the export rather than retraining. This is historical, not evidence that current model 455 or epoch 14 has that bug. It makes PyTorch-versus-ONNX parity checks particularly relevant to the unresolved epoch-14 export identity problem. [#99](https://github.com/liebharc/homr/issues/99)

PR #84 fixed an older loss-mask problem in which a valid non-note pitch token was treated as padding. That predates installed model 426; its misleading pitch metric must not be used to explain the user's current results without evidence. [#84](https://github.com/liebharc/homr/pull/84)

A #86 contributor reported that the backbone remained frozen despite an unfreeze log, then improved after resuming. The suspected library-version cause was not established. Verify actual trainable parameters and gradients before future training, rather than relying exclusively on logs. [Report](https://github.com/liebharc/homr/pull/86#issuecomment-4582409020)

### 6. Playback correctness is broader than recognition benchmark scores

The merged tie-recovery PR reports strong recall on two engraved examples but only 0.12 and 0.04 on two scanned examples. Its discussion also found and fixed a chord-adjacency bug. These small examples are not population estimates, but they show why apparently successful XML repair cannot recover curves the model failed to recognize. [#141](https://github.com/liebharc/homr/pull/141)

Discussion #151 reports that changing part layouts across pages can produce an incorrect merged score. This is an integration failure, not necessarily a bad checkpoint. [Page-merging discussion](https://github.com/liebharc/homr/discussions/151#discussioncomment-18298512)

The benchmark discussions also warn about small saturated test sets, incompatible representations, questionable ground truth, and excluding failed examples. These support the project's common scorer and failure policy. [#107](https://github.com/liebharc/homr/pull/107#issuecomment-4965892183), [Discussion #74](https://github.com/liebharc/homr/discussions/74), [Discussion #95](https://github.com/liebharc/homr/discussions/95#discussioncomment-17362535)

## Recommended decisions

1. Preserve the existing frozen comparison and its candidate identities. This audit did not inspect live Phase 3 logs and makes no claim about whether inference has started.
2. Record model 455 as a separate candidate for a properly scoped follow-up comparison. Pin weights, code, tokenizer/configuration, export precision, and hashes. Do not silently replace the existing baseline.
3. Treat #156 as a promising representation experiment requiring matching weights and code plus explicit voice/rhythm evaluation. Do not infer readiness from its headline NED.
4. Before another fine-tune, prioritize verified labels, representation coverage, actual unfreezing, and export parity. Retain the project's own targeted generator in any future training plan.
5. Require paired composition-level pitch/onset/duration results, failure accounting, and the existing promotion gate before changing the app. The upstream audit alone authorizes no promotion.

PR status must be interpreted with the conversation: #85 preserves a reverted experiment, #97's fix was squashed into main despite closing without a PR merge, #153/#159 fed into #162, and #145 was withdrawn because its claimed improvement was already upstream. Closed does not necessarily mean rejected, and merged does not necessarily mean successful.
