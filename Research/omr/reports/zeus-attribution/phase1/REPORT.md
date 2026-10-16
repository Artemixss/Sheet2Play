# Zeus provenance reconciliation — Phase 1

2026-10-03. Scope: Phase 1 of the [user-supplied main plan](../../../MAIN_PLAN.md).
Historical scores retain their existing identities. No model-quality or causal
attribution verdict follows from this provenance audit.

## Evidence ledger

| Component | Observation | Evidence / qualification |
| --- | --- | --- |
| Declared source | `df0d842596ccd199882ff958e628d59327ca6cba` | Frozen [v5 manifest](../../screening/v1/manifest-v5-607ff64134da.json). This is the upstream dataset tag; it contains no `zeus/zeus.py`. It cannot be the source of the imported recognizer. |
| Current actual source | Clean `a30b153ef10b81b58639daa8f937fccdd7e3e231` | Fresh Git HEAD/status. Reflog records clone at this revision on 2026-08-14, with no recorded HEAD transition. This corroborates current checkout continuity, not historical in-memory module contents. |
| Model-release source | `b87c33a0652dded9039328dce7480b847ad36592` (`zeus-release`) | Local Git tag and [published release](https://github.com/ufal/olimpic-icdar24/releases/tag/zeus-release). Recognizer differs from current source: `max_width` option/resize support and default thread count. Imported converter files match release source after newline normalization. |
| Current imports | `zeus/source/zeus/zeus.py`; `app/linearization/Delinearizer.py`; symbolic helpers | [Import probe v2](probe-v2/import-probe.json) resolves actual module paths, including vocabulary, PitchAlternator, fractional durations, attribute helpers, part-to-score and SER helper. This was an import-only probe; no model constructed or run. |
| Historical source inventory | Local helpers hashed, upstream recognizer/converter omitted | `_zeus_identity()` hashes `zeus/*.py` only. The frozen inventory therefore cannot attest execution-time imported upstream files. Existing screen provenance records attempts/result hashes, not imported module hashes. |
| Corrected crop helper inventory | Actual `phase2r_detector.py` / `phase2r_vlm.py` absent from historical Zeus candidate source list and freeze's explicit research-source list | Historical metadata instead lists `Bridge/detect_systems.py`. Their fresh hashes match the earlier Phase 2R correction handoff (`4ad2a8…` / `b4ffcc…`), supporting continuity without execution-time attestation. The diagnostic identity explicitly pins both actual helpers. |
| Checkpoint | Local/published weights byte-identical | SHA-256 `6f8808cc00e62ac643a1889eca087a1808f5a7d95366d95a5400f68b7802947d`; 29,241,592 bytes. Comparison against freshly downloaded original release, beyond historical local consistency. |
| Ordered vocabulary | All 182 tags identical in order; `<unk>` at index 0 | Published tags SHA-256 `d79da0b8db7a3c54b347e42e064f72afdc217f055c157c4768dea5e8431b2c4f`; local `3daf7ece0f23dbcffd96a38ad392382feadb1dd9ad7e578614e30adc787e2de2`. Difference is LF/CRLF only. |
| Options | Parsed options identical; text differs only LF/CRLF | Published SHA-256 `67b9e7528f2d3dfc6d275943059dce315abf518ee19cf0f04d9847d0e2a4c4ad`; local `5147216bddbf4530c75c5a72365d8b4482f0985bab52f071e0cf60cb94e40cf5`. Height 192; max prediction length 700. |
| Release bundle | All five files match bytes or solely CRLF normalization | [Original archive](published-model.tar.gz), SHA-256 `85f601cb7370175754c0cd9b2d4799f5a744c6d25e5e4f18705b08b79a0c54d2`. README/license text also matches. No independent publisher checksum or signed attestation was available. |
| Recognition runtime | TensorFlow and TensorFlow Intel 2.12.1; Keras 2.12.0 | NumPy 1.23.5, h5py 3.16.0, music21 9.7.0, Pillow 12.3.0. Probe records all installed distribution versions, Python executable/base runtime, TensorFlow build, resolved imported files and environment. GPU list empty in CPU probe. |
| Preprocessing | Grayscale float32, aspect-preserving antialiased resize to height 192, white right-pad to multiple of 500, ragged tensor after padding | Current local wrapper, also matching frozen wrapper hash. Upstream dataset uses variable-width ragged batching. Source identity alone does not establish parity; controlled inference belongs to Phase 3. |
| Decoding | Loaded ordered tags; upstream `predict_step` subtracts 1; local wrapper emits only IDs greater than 0 | Unknown-token/termination behavior recorded as implementation, not validated as a correct remedy. Max length 700. Phase 3 must test these behaviors. |
| Configuration precedence | Upstream parser defaults overlaid with all local options; `train_batches=1` | `max_width=None` from actual parser. Option `threads=6` is not applied through TF thread setters by the wrapper; screen uses environment caps of 8 intra-op and 1 inter-op thread. Wrapper does not call upstream main's seed initialization. No causal conclusion. |
| Conversion/assembly | Upstream Delinearizer → part-to-score, local XML part-ID stitch, shared normalizer | Delinearizer defaults and helper source are pinned. music21 is imported by the wrapper but `lmx_to_musicxml` uses ElementTree/upstream helpers. Research normalization uses its separate environment; detector uses the existing HOMR CUDA environment. |

## Historical reconciliation and next boundary

The weights, configuration and vocabulary have release provenance. The stated
historical source revision is invalid for the recognizer. The present clean
checkout and clone reflog support `a30b153…` as the likely historical checkout,
but do not recover or prove execution-time bytes: files could have been edited
and restored without a Git HEAD change. No execution-time upstream snapshot or
import ledger was found in the reviewed freeze, runtime inventories, screen
provenance or job record. Historical upstream source remains **unverified**.

The diagnostic identity supplements the historical identity and cannot retroactively
certify historical execution or admit another screen. It pins source/weights,
preprocessing, conversion, package/runtime bytes and current imports. Reverify it
before future diagnostic replay; require a new identity if any pinned input changes.
Preserve the historical manifest's incorrect source declaration as evidence.

Phase 1 is complete within its authorized provenance boundary. See the
[job record](job-record.md) for commands, logs, deviations and interruption recovery.

## Validation and acceptance closeout

The diagnostic identity is
`ade1709596afff5023e14bfb73257028ff2bc8521f4ff895ec91dc863b842cbb`,
with 113,385 non-bytecode files across the Zeus/research/detector/base-Python runtime
trees and a source snapshot. All 12 imported upstream files match actual current
HEAD; only the recognizer differs from the model-release tag. Final full rehash
**passed**, including 50 inherited detector files, source snapshot, imported files,
pipeline/model files and release evidence. [Verification log](identity-verify.log).

[Historical audit](historical-audit.json) reverified 59 successful results,
59 saved scores and 236 declared artifacts under the unchanged v5 manifest;
session ledger closed. This is artifact integrity, not recovery of missing
execution-time provenance. No score was recomputed.

Focused tests: **12 passed**. Complete research/bridge regression in the original
historical access context: **251 passed, 2 skipped**, existing bridge subtests passed.
Expanded access: **249 passed, 2 failed, 2 skipped**. Both failures are old strict
freeze-equality tests, with exactly the 33 extra package metadata entries already
recorded in v5. Read-only diff found no other change; current readable runtime
equals v5 exactly. Tests/freeze were preserved; none skipped or xfailed to obtain
the successful historical-context run. Making these two legacy tests portable to
the expanded context is an optional follow-up, not a scoring/runtime repair here.

| Acceptance criterion | Status | Evidence |
| --- | --- | --- |
| Actual imported source paths/hashes, Git revision and dirty state identified | **Met** | Probe v2, identity inventories, revision comparisons; current checkout clean. |
| Weights/configuration/ordered vocabulary compared with original published release | **Met** | Weights byte-identical; all four text files identical after newline normalization; options and ordered tags semantically identical. No publisher checksum claimed. |
| Preprocessing, decoding, conversion and TensorFlow/dependency versions recorded | **Met** | Ledger, probe and complete runtime inventories. Upstream inference parity remains untested. |
| Missing historical provenance explicitly distinguished from current evidence | **Met** | Declared revision invalid for recognizer; reflog supports likely checkout but does not attest execution-time bytes. Historical dependency versions do not attest historical dependency bytes either. |
| Fully pinned identity created for future diagnostic replay | **Met** | Separate identity/source snapshot; complete rehash and inherited detector verification passed. Fresh import-resolution check required before future inference. No screening admission granted. |
| Historical manifests/results/scores preserved and checked | **Met** | Unchanged v5 audit: 59 results, 59 scores, 236 declared artifacts; closed session. No rescoring. |
| Relevant fixtures and complete research/bridge regression run | **Met** | 12 focused passed; full historical-context suite 251 passed/2 skipped. Two documented expanded-context failures preserved, no test changes. |
| Execution-time upstream source recovered/proven | **Unverified** | Explicit allowed historical limitation; current identity does not retroactively certify old execution. |

No Phase 1 acceptance criterion is unmet. The historical-source limitation is
explicitly allowed by the plan's exit gate. **Stop before Phase 2** until a new
request. No timing repair, attribution inference, model remedy, Rokot execution,
training, cloud spending, promotion, confirmation or app publish occurred.
