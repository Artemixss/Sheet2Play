# Phase 2R master review — 2026-09-24

**Decision: accept the completed execution and preserved evidence; do not advance the expanded roster to Phase 3 yet. A confirmed detector-to-crop integration defect requires a bounded development correction before excluding Rokot on its page failures.**

This is a review and proposed next work, not authorization to execute another phase. The [canonical plan](COMPARISON_PLAN.md), frozen evaluation manifests, scoring rules, fine-tuned-HOMR approval baseline, and promotion gate remain unchanged. No recognition, training, cloud rental, or app promotion was started during this review.

## What remains valuable

Phase 2R established real runtime identities, retained raw output and hashed artifacts, executed failure contracts, exercised all 32 development inputs, and exposed conversion limitations. Preserve this work and all original reports. Audiveris is now demonstrably runnable. The generated Rokot controls establish a functioning recognition/conversion path on some inputs. None of these success counts measures transcription accuracy.

Independent review checks: the 13 tests in `tests/test_phase2r.py` passed; all 96 final per-item reports and 338 declared artifacts matched the hashes recorded in their aggregates/reports. The handoff's larger 97-test research suite and 26-test bridge suite are reported prior validation, not suites independently rerun in this review. Hash integrity establishes provenance, not correctness of the experiment.

## Blocking finding: detector and crop use different coordinate spaces

`Bridge/detect_systems.py` discards the image returned by `detect_staffs_in_image` and exports the staff boxes directly. The installed HOMR implementation first autocrops and resizes the input; its resize helper targets 1920 pixels wide. Detection returns boxes in the resulting prediction-image coordinate space, together with `predictions.preprocessed`.

`src/sheet2play_omr/phase2r_vlm.py::crop_detected_systems` then opens the original image and applies those vertical coordinates without a transform. Autocrop offsets also matter: multiplying by a guessed width ratio is not a generally correct repair.

This is visible in retained artifacts for `openscore-6211535-page-1`. The source is 2480 × 3509 pixels. Its first saved box spans y=646.80–930.28; the adapter produced a 2480 × 284 crop. Inspection shows that crop cuts through the upper staff and omits the lower staff, although the source contains a complete two-staff piano system.

- [Original page](data/phase1-development/open/6211535/page-1.png)
- [Actual model input crop](.runtime/phase2r/smokes/rokot-openscore-6211535-page-1-fb28064ca084-no-runtime/crops/system-0001.png)
- [Recorded boxes](.runtime/phase2r/smokes/rokot-openscore-6211535-page-1-fb28064ca084-no-runtime/detected-systems.json)

Both Rokot and Qwen use this complete-page path. Their open-page failures remain accurate records of the tested broken pipeline, but cannot establish model-only failure. The handoff's attribution to model output rather than integration is too strong. Missing voices and repetition may still remain after correction; this review does not predict that fixing crops will make either model accurate.

Annotated generated controls bypass page detection, so their failures are not explained by this defect. The detector test mocks a staff box without exercising a transformed source image, and the reviewed Phase 2R tests do not verify detector-to-original coordinate consistency. Passing those tests therefore does not close this gap.

## Candidate decisions

| Candidate | Evidence and planning decision |
| --- | --- |
| Rokot Q8 | 10/12 generated controls succeeded; 0/20 open pages succeeded under the defective crop path. Highest priority for corrected development validation. Do not exclude or rank it from the current page results. |
| Vanilla Qwen3-VL | 0/12 generated controls and 0/20 open pages succeeded. Page results share the crop defect, but the independent control failures justify lower priority. Allow one bounded runtime/prompt sanity check; avoid an open-ended prompt search. |
| Audiveris | 22/32 succeeded: 2/12 generated and 20/20 open first pages. Runnable, with genuine failures and one normalizer error to diagnose. Success means accepted output, not correct rhythm. Its native-page route does not use the defective VLM crop path. |
| Shipped HOMR / Zeus | Preserve earlier readiness evidence and configurations. Phase 2R does not provide a new accuracy ranking for them. Audit any dependency on the shared detector before carrying evidence forward. |
| Fine-tuned HOMR | Remains the approval baseline for later verified evaluation. Do not alter or restart the existing training. No claim that rhythm is solved without measured results. |
| LEGATO | Recognition is unprovisioned and unmeasured locally. Keep unavailable in this round, but do not call hardware impossibility demonstrated. |
| HOMR PR #156 | Conditional on verified compatible weights; no invented result. |
| MuSViT | Requires a usable recognition decoder or separately authorized training; outside the runnable comparison. |

LEGATO needs a narrower hardware conclusion. The pinned source loads the external dependency through `MllamaVisionModel.from_pretrained`, not the complete external 11B language model. Full repository download size and a model-card memory estimate do not establish the actual peak memory of that vision encoder plus LEGATO decoder. This does not prove a 6 GB fit. A static load/dtype/memory assessment should precede either a large download or a separately costed cloud proposal.

## Recommended next work: bounded Phase 2R correction

1. **Repair and prove the image-coordinate contract.** Prefer cropping the exact detector image, or return a verified full transform to original coordinates. Preserve the selected detector algorithm and source images. Record image dimensions, coordinate space, transforms, crop hashes, and the revised adapter identity. Test both resizing and autocrop offsets, plus complete grand-staff coverage. Visually verify the representative retained failure before new inference.
2. **Validate Rokot in stages.** Run one corrected representative development page, examine each raw system output and conversion before the join, then run the full existing 12-control/20-first-page development suite after the targeted checks pass. Retain original failed reports and create new versioned reports. Separate segmentation, recognition, conversion, and merge failures. Further prompt/precision changes require specific evidence; do not change several variables at once.
3. **Close the conversion and reporting gaps.** Classify the open-reference warning ledger; all 20 strict reference projections currently warn, and the warning-tolerant diagnostic minimum exact-event F1 is only 0.78669. These are representation/conversion diagnostics, not candidate scores. Exercise relevant ties, tuplets, voice/state changes, and joins without reference-guided repair or blanket warning suppression. Record time and resource consumption on failed attempts as well as successes. Scope the Audiveris normalization exception before deciding whether it is an adapter defect or invalid native output.
4. **Freeze a defensible roster.** Retain runnable candidates, explicitly record unavailable or excluded configurations and reasons, and preserve system-level versus page-level reporting. Require a verified end-to-end page path for candidates entering page comparison, not perfection on every development item. Submit the corrected readiness outcome before separately requesting Phase 3.

Do not expand this correction into new datasets, another training run, a new engine search, or spending the cloud allowance. The immediate bottleneck is experiment validity. If corrected Rokot still fails broadly, retain that evidence and make a bounded stop/exclusion decision rather than repeatedly tuning until the development set looks good.

## Phase boundary and resume point

Phase 3 remains unstarted. After corrected readiness, Phase 3 can evaluate the ready pretrained configurations under the frozen protocol; Phase 4 evaluates verified fine-tuned HOMR; Phase 5 supplies paired statistics and replacement recommendations. A smaller honest roster is acceptable, but excluding a model because its integration fed it damaged inputs is not.

The exact next implementation task is the detector-to-crop coordinate contract and its regression checks. No fix or rerun was performed by this review. At the final substantive investigation checkpoint, the five-hour allowance had 18% remaining; this review was wrapped up to preserve the user's requested 10–15% reserve.
