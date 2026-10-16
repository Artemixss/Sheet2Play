# HOMR upstream update — 2026-09-29

## Decision

Continue the bounded comparison plan. Update the existing PR #156 candidate to **HOMR 465 multi-voice: weights published, local compatibility/admission pending**. Do not replace the shipped model, rerun completed screens, or start another fine-tune based on this news. Add issue #167 to the existing development-only meter-export investigation beside #161. PR #168 belongs in the future training-label quality work, not as a ready inference improvement.

This is a documentation-only follow-up to the [September 26 audit](UPSTREAM_AUDIT_2026-09-26.md). Its description of #156 as open and unreleased is now historical. The [canonical plan](../../COMPARISON_PLAN.md) remains authoritative; this update does not authorize execution or change its order.

## What changed

| Item | Verified status on September 29 | Effect on Sheet2Play |
| --- | --- | --- |
| [PR #168: slur grouping across voices](https://github.com/liebharc/homr/pull/168) | Open, unmerged; one commit, three files | Corrects training-token construction; no released checkpoint incorporating this patch was identified |
| [PR #156: multiple voices](https://github.com/liebharc/homr/pull/156) / model 465 | Merged September 26; PyTorch and ONNX release assets published | Existing conditional candidate now has obtainable weights; still needs local verification |
| [Issue #167: mixed time signatures](https://github.com/liebharc/homr/issues/167) | Open; exporter-only reproduction reported | Concrete conversion diagnostic alongside #161 |
| [Image-position comments](https://github.com/liebharc/homr/commit/dda4d2ffe4410a360e18251936884eba9a41c321) | Landed on main September 28 | Potential future score highlighting/debugging feature; no demonstrated rhythm gain |
| [PR #169](https://github.com/liebharc/homr/pull/169) | Open, unmerged | GRANDSTAFF index/token regeneration workflow; not an inference candidate |
| [PR #166](https://github.com/liebharc/homr/pull/166) | Still open, unmerged | Previously known repeat-start training-label fix; retain in future training work |

## PR #168: useful, but it cannot repair the existing checkpoint by itself

The patch changes `training/transformer/training_vocabulary.py` and two test files. Previously, slur tags were collected by upper/lower staff, collapsing distinctions between voices on the same staff. The new implementation groups them by the exact position label (`upper`, `upper2`, `lower`, `lower2`) and attaches the combined tags to the first sorted note within that voice.

For example, when one voice ends a slur while another starts one at the same instant, the old grouping could put both tags on one voice. The proposed grouping preserves which voice starts and which stops. Tests cover both staves, ordering, aggregation within a voice, and a reduced GRANDSTAFF example. Articulation grouping remains separate.

This strengthens the earlier concern about lossy training representations: more source scores cannot recover a distinction discarded by label construction. It does **not** prove that this specific defect caused Sheet2Play's measured onset/duration failures. Slur/tie handling can affect interpretation, but no local rhythm-score improvement was established here.

The changed routine constructs training tokens; the reviewed patch does not change ordinary image-to-MusicXML inference. The local MusicXML module's training-vocabulary import is in its standalone `__main__` helper. Installing this patch alone will not update learned behavior in model 426, the local fine-tune, 455, or already released 465 weights. Model 465's September 26 assets predate this PR. Review this fix before any separately authorized future dataset regeneration/training, together with repeat labels and the project's own generator round-trip checks.

## Model 465: the material candidate-availability change

PR #156 merged at `5dc91d6a30bcb66ae31e4e50935ee6a568fb7039`. The subsequent model-update source commit is `7d97c3cee4ad772b50266fdf9dc78bbf9064701e`. Upstream identifies run 465 as `597144cab54c8f6d0f6c9619df5c5312694eadd6` and explicitly describes multiple voices per staff. The maintainer confirms the model update in [this comment](https://github.com/liebharc/homr/pull/156#issuecomment-5847578552).

The [ONNX release](https://github.com/liebharc/homr/releases/tag/onnx_checkpoints) contains matching 465 encoder/decoder assets in FP16 and FP32. The [training checkpoint release](https://github.com/liebharc/homr/releases/tag/checkpoints) contains the PyTorch checkpoint. API metadata for the FP16 files records:

| Asset | Bytes | SHA-256 from release metadata |
| --- | ---: | --- |
| `encoder_pytorch_model_465-597144cab54c8f6d0f6c9619df5c5312694eadd6_fp16.zip` | 24,003,849 | `646166a655e7ca9db19463a2fd3cd10cf829213d2d0b6b7708a3bd111a7b058a` |
| `decoder_pytorch_model_465-597144cab54c8f6d0f6c9619df5c5312694eadd6_fp16.zip` | 86,552,290 | `6fad93e6dadc56fd5f86cfe92a32fbe28fe5fe7fda1681632c9f934880fe9ac8` |

These are published metadata, not locally verified downloaded bytes. No weights were downloaded or executed in this audit. Upstream's run record reports system-level SER 4.0%, Polish 17.52%, and SMB 13.84%; these are upstream benchmark figures, **not** Sheet2Play composition-macro pitch/onset/duration F1 and cannot be inserted into our ranking. See [the pinned training record](https://github.com/liebharc/homr/blob/7d97c3cee4ad772b50266fdf9dc78bbf9064701e/TRAINING.md).

Name this candidate **HOMR 465 (PR #156 multi-voice)**, not a second independent “PR156” entry and not “455 plus multi-voice.” Its source, weights, ordered vocabularies, position classes, decoder and preprocessing must be pinned together. The earlier 455/465 position-head mismatch demonstrates why checking only familiar tokenizer filenames is insufficient. Require representation fixtures, a complete-page development smoke, resource admission, and a separate immutable identity before screening. Whether it fits and works on this PC remains unverified.

## Issue #167: check export separately from recognition

The reporter supplies recognized tokens for a 4/4 measure followed by a 2/4 measure. The exporter produces 3/4 for both: the representation carries `timeSignature/4`, while the numerator is inferred from a median across supplied measure durations. Four and two therefore yield three. The example exercises export without an image or model, so it isolates a conversion problem from recognition.

The installed source contains the same general whole-staff numerator-estimation pattern, with additional local voice-repair logic. That makes this relevant, but this audit did not reproduce the defect through the installed app. The report preserves note durations; an effect on sounding onsets/durations depends on downstream interpretation and normalization.

Keep #167 distinct from [#161](https://github.com/liebharc/homr/issues/161), which concerns duplicate inferred/recognized time signatures. Investigate both using development fixtures, including 4/4 to 2/4, pickups, rests and legitimate meter changes. Do not infer that every short bar changes meter. A demonstrated repair needs a controlled pipeline comparison, not a claim that the neural model improved.

## Selective adoption and the next decision

The current [corrected HOMR-only report](../screening/v1/2c98d5638c36/reports/homr-only-stage4-e35f73ca9f75/REPORT.md) still governs: shipped primary F1 0.4061, fine-tuned 0.3844, corrected 455 0.2857; paired intervals cross zero. Neither challenger established superiority. New upstream activity does not invalidate those frozen configurations or their results; 455's result also does not establish 465's quality.

Recommended disposition:

1. Keep shipped HOMR and all completed evidence. Audiveris/Zeus and consolidation remain the next requested-execution boundary in the selected plan.
2. Treat 465 as the existing conditional HOMR addition with published artifacts, pending development verification. Do not add multiple overlapping candidates merely because several commits exist.
3. Investigate #161/#167 together as one bounded export task. If a fix is demonstrated, test at most the already permitted compatible HOMR-Combined variant against its unmodified control.
4. Retain #168/#166/#169 for future training/data preparation. No new training run is justified by their existence alone. Preserve the bounded Qwen/Rokot follow-up and LEGATO/MuSViT roadmap.

The newer image-position feature writes approximate `imgpos` comments based on attention-derived coordinates. It could help explain recognition errors or support future highlighting. Its commit spans cropping, dewarping, coordinate mapping and export; copying one function without those dependencies is unsafe. It is optional product/debugging work, not a current rhythm remedy.

A pinned local fork is appropriate while it remains measured and reproducible. Maintain a small inventory of local patches and adopt compatible upstream fixes deliberately. A blanket sync to main would mix model representation, preprocessing and export changes, obscuring which helped or regressed. No inference candidate, environment, shipped code, frozen artifact, training job or evaluation job changed during this audit.

## Evidence scope

This was a targeted delta review of PR #168, #156 status/discussion/releases, recent commits/issues and relevant source, not a repeat of the earlier complete inventory. The reviewed main head was `93e17ba99402fe768dc16dd59b3e1b53abc405e8`; PR #168 head was `74062f7f3bca3b97ef69d3848a60e170c32e910f`. PR tests were inspected, not executed. Public API snapshots for #156, #168 and its diff, #167 and both release asset lists are retained locally under `Research/omr/.runtime/upstream-audit-20260929/`. Statuses may change after this dated review.
