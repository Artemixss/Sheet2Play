# Interim HOMR screen review — 2026-09-26

**Decision: correct the 455 model/source compatibility error before using this comparison to select engines. Make a bounded attempt to admit the already-planned fine-tune, then finish the ready-candidate screen. Do not expand into many combined HOMR variants now.**

This is a review of the [interim report](reports/screening/v1/2c98d5638c36/reports/interim-homr-dd1c0a4aeea5/REPORT.md), [screening handoff](SCREENING_HANDOFF.md), current [canonical plan](COMPARISON_PLAN.md), and historical Phase 2/2R and Phase 3 reviews. The canonical screening plan supersedes the old exhaustive phase order. No inference, export repair, training, engine change, or production release was performed by this review.

## Blocking finding: the screened 455 source decodes a different position vocabulary

The screening manifest pins model 455's FP16 encoder/decoder but source revision `7d97c3cee4ad772b50266fdf9dc78bbf9064701e`. That source's default model is **465**, overridden by the research launcher to use 455 files. Pinning hashes establishes reproducibility, not model/source compatibility.

Independent local inspection found:

| Contract | Model 455 / its release source | Source used for the screen |
| --- | --- | --- |
| Position output classes | Decoder ONNX metadata: `out_positions [1, 1, 3]` | Vocabulary has five entries |
| Class 0 | `.` | `.` |
| Class 1 | `upper` | `upper` |
| Class 2 | `lower` | `upper2` |
| Classes 3 and 4 | Not present in the 455 output head | `lower`, `lower2` |

The reviewed `decoder_inference.py` builds its inverse position mapping from the source vocabulary and detokenizes output argmax IDs with that mapping. Thus a predicted class 2 is interpreted as `upper2`, not `lower`. Merely hashing the four legacy tokenizer JSON files does not test this Python-defined vocabulary.

The expected three-entry mapping was independently confirmed by reading the upstream vocabulary at the [455 model-switch commit](https://github.com/liebharc/homr/commit/a4865663e7278f908d6d1b1a57d549f9ca3d1067). Its configuration identifies `pytorch_model_455-7bf1389908b44047d4cba9d5d06e868ceaf946ef`. The local decoder was inspected through ONNX Runtime CPU metadata only; no prediction was generated. Its output head sizes are rhythm 260, pitch 72, lift 7, position 3, articulation 62, slur 5. The screened source matches those counts except position, which is 5. Exact token ordering must also be checked; matching head sizes alone is insufficient.

**Consequence:** preserve the existing 455 results as evidence of this incompatible configuration, but exclude them from claims about correctly configured model 455. The reported 0.2819 F1 and its paired interval cannot decide whether the actual 455 model should be rejected. This defect may explain part of the observed degradation; its numerical contribution and the corrected score remain unmeasured. The installed HOMR result is not invalidated by this specific defect.

Relevant implementation: `screening_homr_455_launcher.py`, `screening_homr_extension.py`, `.runtime/homr-455/source/homr/transformer/configs.py`, `vocabulary.py`, and `decoder_inference.py`. The active manifest is `reports/screening/v1/manifest-v2-0de561e2ae9d.json`. Do not edit its frozen identity or old outputs in place.

## What was compared, and where the fine-tune went

`homr_page` means the installed HOMR engine run through the complete-page research path, with resource limits and frozen scoring normalization. It is not a model named “page,” nor the fine-tune. The source is the project's `457e7c6+pr146` configuration. This does not test the entire desktop playback experience.

`homr_455` is the isolated upstream configuration described above. Both reported 58 accepted outputs and one failure across the same 59 pages/18 compositions. Accepted output means parseable canonical notes, not correct notes or compatible labels.

Fine-tuned HOMR is already second priority in Stage 3. It was deferred because the decoder's actual hash (`54c4940a…`) differs from the export manifest (`daee4ce3…`) and the source training checkpoint is unavailable locally. This is an artifact-provenance blocker, not evidence of a bad model, a memory problem, or a decision to exclude fine-tuning. Do not change the manifest to match an unexplained file. Obtain the authoritative export/source checkpoint, verify the pairing and tokenizer/decoder contract, and demonstrate export equivalence where needed. If unavailable, record the exact required artifact and move on rather than repeating an open-ended investigation.

## Does 455 need the app's improvements?

The user's hypothesis has a concrete basis. The installed `music_xml_generator.py` contains `_plan_voice_repairs`, planned measure-cursor handling and voice-assignment logic absent from the screened upstream converter. Therefore this was a comparison of different model-plus-converter pipelines, not a controlled weights-only test.

However, 455 already uses the same hashed `Bridge/musicxml_normalizer.py`, shared GPU wrapper, and resource-limit policy. Applying “all app fixes” indiscriminately would duplicate some shared behavior and risk breaking upstream changes. The installed vocabulary also has 61 articulation labels whereas model 455 outputs 62; copying the entire older runtime is not a safe shortcut.

Recommended order: first make upstream 455 internally compatible. Then inventory the specific project converter differences. If a missing repair demonstrates benefit without corruption on development fixtures, propose **one** separately pinned `455 + project voice-timing repair` configuration, with the corrected upstream 455 as control. Validate before screening; do not tune the repair on these 59-page errors. Multi-voice PR #156 weights and issue #161 are different questions and should not be mixed into that first repair experiment.

## Interpretation of the current numbers

The report records installed HOMR primary F1 0.4061, pitch/onset F1 0.4316 and pitch F1 0.9701. This pattern indicates strong pitch matching alongside much weaker timing-sensitive matching. F1 0.4061 is not a claim that exactly 40.61% of the music is correct; it is a composition-macro balance of precision and recall under the matching rules. A timing displacement can make many subsequent notes fail strict onset matching.

The reported 455-minus-installed difference is -0.1242, with interval [-0.2557, 0.0155]. Even without the compatibility defect, the interval crosses zero. With the defect, neither that difference nor the duration diagnostics justify a model-quality verdict. No replacement is supported by this screen.

## Recommended next executor request

1. **Bounded 455 correctness repair:** pin source/vocabulary compatible with the released weights; verify every head's class count and label ordering, including position and articulation; add a regression that rejects the present 3-versus-5 mismatch and checks class 2 maps to lower staff. Pass known symbolic/conversion fixtures and complete-page development inference. Then create a new configuration identity and rerun only that candidate's 59-page screen. Preserve the installed baseline and all historical failed-configuration evidence.
2. **Bounded fine-tune intake:** reconcile the exact checkpoint/export identity. If authoritative artifacts can be obtained and verified, admit and screen the fine-tune on the existing sample. If not, stop with a precise missing-artifact handoff; do not retrain or substitute another file.
3. **Finish ready-candidate screening:** admit Audiveris and corrected Zeus, run one at a time under current resource/session limits, and produce the consolidated report. Do not delay these indefinitely for unavailable weights or speculative combinations.
4. **Stage 4 decision, then Stage 5:** analyze the consolidated screen and choose the next investment. The larger confirmation run needs a separate decision. Stage 5 permits at most four hours and one focused Rokot/Qwen development remedy, followed by a proposed future screen only if readiness passes. It does not automatically evaluate every deferred engine.

Any new report must visibly identify invalid historical configurations and the absent fine-tuned approval baseline. Do not repeatedly screen speculative patches until one happens to look good. The original fine-tuned-baseline promotion gate and separate release requirements still apply.

## Product progress and scope control

The research work has preserved data, repaired cropping, made failure accounting explicit, recovered interrupted results, and produced a reusable bounded comparison. Those are real infrastructure gains. They are not a shipped rhythm improvement. The user's concern about two weeks without an app improvement is therefore legitimate; lack of a deployment is not explained away by more reports.

The immediate milestone should be a trustworthy, small comparison with the existing fine-tune accounted for, not another expansive roadmap. After that, select one measured integration improvement or keep the current engine. Review and commit completed research work in focused batches as a separate housekeeping task; neither a commit nor passing research tests means the desktop app improved. No commit or publish was made in this review.
