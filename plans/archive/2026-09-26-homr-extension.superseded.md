# Phase 4 — fine-tuned baseline and upstream HOMR extension

**Plan ID:** `2026-09-26-homr-extension`.
**Lifecycle:** Superseded on 2026-09-26 by the [selected screening plan](2026-09-26-omr-screening-comparison.superseded.md);
archived in the plans directory on 2026-10-04. This proposal was not completed
as written. Its original planning text follows as reference evidence;
prospective instructions and phase numbering are historical.
[Current plan](../MAIN_PLAN.md); [all plans](../README.md).

The original HOMR extension snapshot remains unchanged at
[PHASE4_HOMR_EXTENSION_PLAN.retired.md](../../Research/omr/.runtime/plan-retirement-20260926/PHASE4_HOMR_EXTENSION_PLAN.retired.md).

Planning amendment: 2026-09-26. Status: **planned only; no execution authorized by this document update**.

The user asked to incorporate the upstream findings reported in the task **Analyze fine-tune results**. That report identifies released model 455, updated multi-voice PR #156 training, and issue #161's meter-export behavior. These findings motivate candidate intake; they do not establish local compatibility or superior accuracy. This document supplements the [canonical comparison plan](2026-09-26-omr-screening-comparison.superseded.md).

## Candidate identities and experiment boundaries

| Display name / planned identifier | Kind | Planned comparison |
| --- | --- | --- |
| Fine-tuned HOMR / existing `fine_tuned_homr` | Existing approval baseline | Verified development-selected checkpoint and final checkpoint if different, using the same compatible decoder for the checkpoint comparison. |
| HOMR-455 upstream / `homr_upstream_455` | New pretrained challenger configuration | Pin the source that selects 455 and compatible ONNX weights, tokenizer and decoder; evaluate against shipped and fine-tuned HOMR under the same protocol. |
| HOMR-PR156 multi-voice / existing `homr_pr156` | Updated intake for an existing conditional challenger | Obtain and verify the updated stem-direction/multi-voice model with its matching representation, tokenizer and decoder. Do not substitute 455 weights or count the old placeholder as another model. |
| HOMR [pinned model] + meter-export fix / identifier assigned only after verification | Conditional pipeline variant, not a model | If issue #161 reproduces, isolate a validated remedy and compare the same model/configuration with and without it on development data before freezing the variant. |
| HOMR-Combined / `homr_combined` | Conditional combined pipeline configuration requested in the user's follow-up | One verified multi-voice model/decoder with compatible 455-era changes and a validated #161 remedy where applicable. Evaluate after isolated development checks; do not assume 455 and PR #156 weights are interchangeable. |

Do not collect all new commits into a mutable “latest HOMR” candidate. A released model with its required decoder is one pinned configuration. A representation-changing model is a separate challenger. An export fix is a controlled pipeline variant. Precision variants and combinations are configurations, not additional independent models. Avoid a full matrix of speculative combinations: add one only when a demonstrated dependency or scientific question justifies it.

If later inspection shows an upstream model already contains a relevant fix, record it in that configuration's provenance; do not apply it twice or invent a distinct unfixed control. If compatible decoders differ, label a comparison as model-plus-decoder rather than claiming the weights alone caused the change.

## 4A — Preserve the fine-tuned approval baseline

Verify checkpoint identity, training completion/provenance, tokenizer/decoder compatibility and development selection. Evaluate under the existing frozen protocol; do not restart or alter the training run. Shipped HOMR remains a control and fallback. Neither 455 nor PR #156 silently becomes the approval baseline. A worse fine-tune does not justify displacing a better shipped engine.

## 4B — Intake upstream challengers, 455 first

1. Resolve exact source revisions and model artifacts. Hash all weights and tokenizer/decoder assets, record precision/runtime/patches and known or unknown training overlap, and distinguish reported availability from downloaded, verified, runnable status.
2. Use isolated research runtimes and caches. Do not upgrade `Bridge/.venv-homr-gpu`, replace installed weights, mutate active Phase 3 adapters, or invalidate existing results.
3. Validate representation/conversion fixtures and real development inference before evaluation. Include independent voices, ties, tuplets, pickups, meter changes and complete-page joins. Keep the project's generator in the development/training strategy.
4. Freeze new configuration identities in a separately versioned extension manifest, then evaluate the same eligible items under the existing scoring and failure policy. Missing PR #156 weights remain “not evaluated,” never a zero score; they need not block a ready 455 candidate.

Model 455 can answer whether a newer released upstream configuration improves the current baseline without another local training run. PR #156 can test the more specific multi-voice representation hypothesis. Neither is presumed to fix rhythm.

## 4C — Issue #161 as a development diagnostic

The reported behavior is an inferred time signature preceding a recognized one, such as `3/4` before `6/8`, with some consumers taking the wrong entry. First reproduce the exact native XML structure and determine how the current normalizer and playback extraction handle it. Include valid meter changes, distinct staff-specific meters, duplicate entries and conflicting entries in fixtures; do not assume the first or last entry is universally correct.

If behavior does not reproduce locally or does not affect canonical timing, record that finding and add no fix. If it does reproduce, identify the responsible producer/consumer and validate the smallest semantically justified remedy. Preserve note onsets, sounding durations, pickup timing and legitimate meter changes. No ground-truth-driven selection or post hoc alignment is allowed.

Do not change the shared frozen scorer/normalizer in place. If the remedy changes canonicalization semantics, require an explicit versioned protocol decision and comparable baseline reprocessing before making cross-version claims. A candidate-native export fix should likewise have its own configuration identity. This diagnostic can precede 4A/4B where it is a prerequisite; “4C” is a scope label, not an instruction to diagnose only after evaluation.

## 4D — One compatible combined configuration

The user's follow-up requests including a combination of the upstream improvements.
Use the name **HOMR-Combined**, not “455 with multi-voice,” until verified provenance
actually supports that latter description. A combined configuration is worth testing
because a useful application pipeline may need both stronger recognition and correct
export. It must not erase the isolated configurations needed to explain improvements.

- First establish the individual compatibility and development results in 4B/4C.
  Select a combination using development evidence only, then freeze it before evaluation.
- Use a verified multi-voice checkpoint with its matching representation, tokenizer and
  decoder. Include compatible 455-era inference fixes only when their applicability is
  demonstrated. Model 455's learned weights and PR #156's learned weights cannot simply
  be combined by applying source patches. Training-data improvements associated with
  455 are not inherited merely by copying converter code.
- Include a #161 remedy only if the issue reproduces on this configuration and the fix
  passes the meter/timing fixtures. If it is already fixed, record that fact rather than
  stacking another patch. Record inherited changes and explicitly absent or unverified
  features in the configuration provenance.
- Start with one meaningful combined configuration, not every possible permutation.
  Preserve the applicable component controls. If the combination is identical to a
  previously frozen PR #156-plus-export-fix variant, reuse that identity and result rather
  than counting it as a new independent model.
- Compare against the fine-tuned approval baseline and applicable component variants
  using the same protocol; include the additional superiority claims in Phase 5's
  multiple-comparison accounting. A combined pipeline may regress despite helpful
  individual changes, so acceptance is measured rather than assumed.
- If the desired combination requires unavailable weights, incompatible architecture
  changes, or a new training run, mark it **deferred: compatible trained checkpoint
  required**. It must not hold up runnable candidates or trigger training automatically.

This is a planned experimental configuration, not a promised released upstream model.
The documentation amendment does not authorize implementation or execution.

## Source leads and adjacent news

The detailed upstream findings were retrieved from **Analyze fine-tune results**, task `01a0abf9-cc75-7a60-8474-a5d040ab0951`, latest completed research turn. The following are source leads from that report, not artifacts independently downloaded or verified during this planning amendment. Recheck status and exact compatible revisions during future intake.

- **455:** [model-switch commit](https://github.com/liebharc/homr/commit/a4865663e7278f908d6d1b1a57d549f9ca3d1067) and [ONNX release assets](https://github.com/liebharc/homr/releases/tag/onnx_checkpoints). The report identifies a 426-to-455 default change and available ONNX/FP16 and training weights. [PR #162](https://github.com/liebharc/homr/pull/162) is associated training-rendering provenance, not another model entry.
- **Updated PR #156:** [PR discussion](https://github.com/liebharc/homr/pull/156), including the [reported completed training update](https://github.com/liebharc/homr/pull/156#issuecomment-5834285814). A contributor's completion claim or offer of weights is not verified public checkpoint availability. Upstream benchmark error figures are not Sheet2Play's rhythm F1.
- **Meter export:** [issue #161](https://github.com/liebharc/homr/issues/161). This is an issue report, not “model 161” or a verified ready-to-apply fix.
- **Future training-label audit:** [issue #165](https://github.com/liebharc/homr/issues/165) and [PR #166](https://github.com/liebharc/homr/pull/166) report repeat-start alignment across training-image boundaries. Track before any future data generation/training; do not infer that existing weights are repaired or add a model candidate merely because a dataset-converter patch exists.

## Acceptance and preserved work

Maintain the Phase-1 manifests, canonical scoring rules and Phase-3 freeze. Do not change `comparison-config-v2.json` to inject these entries into the active run. Reuse baseline predictions only when model/input/preprocessing/normalization identities remain compatible. Select settings on development data, not inspected frozen benchmark errors.

Phase 5 retains composition-grouped paired statistics, Holm correction for the relevant expanded superiority claims, full duration diagnostics, failure penalties and separate accuracy/practical conclusions. The promotion threshold remains at least 0.03 absolute primary F1 gain over verified fine-tuned HOMR, with the existing pitch/failure/OMR-NED safeguards and resource requirements. No automatic production replacement follows.

Local-first execution, the existing $10 total cloud ceiling, private-data restrictions and separation from ongoing training remain in force. No new training or cloud purchase is implied by this plan. Rokot, Qwen, LEGATO and conditional MuSViT remain on the expanded comparison roadmap independently of these HOMR additions.

**Next action is planning only:** retain these entries until execution is explicitly requested. This amendment performs no installation, checkpoint download, local #161 reproduction, inference, training, process restart or promotion.
