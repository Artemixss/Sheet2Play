# Zeus provenance Phase 1 handoff — 2026-10-03

**Lifecycle update, 2026-10-07:** The [owning Zeus/shared repair plan](../../../../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md)
is superseded by [HOMR 465 and shipped-engine rhythm repairs](../../../../../plans/MAIN_PLAN.md).
This phase's evidence and acceptance limits remain unchanged. Phase 3 stays
qualified; unexecuted Phase 5/Rokot and further Zeus work are deferred.
Read the [new plan handoff](../../homr-timing-465/handoff.md) for current scope.
The dated next-action/authorization statements below are historical; this
documentation transition does not start a new execution phase.

**Lifecycle update, 2026-10-04:** Phase 1 is complete. Phase 2 subsequently
completed, including independent acceptance; [its handoff](../phase2/handoff.md)
owns the latest state. [Plans index](../../../../../plans/README.md);
Phases 3–5 require a separate request. Authorization/stop statements below
describe the Phase 1 request at its closeout date.

Authority: [main plan](../../../../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md), Phase 1 only.
[Ledger and acceptance status](REPORT.md); [commands/deviations](job-record.md).

Changed research tools:

- [Collector](../../../zeus_provenance_probe.py): imports/configuration only; no model execution.
- [Identity builder](../../../zeus_provenance.py): release comparison, runtime/source inventories,
  source snapshot and immutable diagnostic identity, separate from historical manifests.
- [Replay verifier](../../../zeus_provenance_verify.py): complete runtime byte checks plus
  inherited detector/Bridge pins.
- [Fixtures](../../../tests/test_zeus_provenance.py): release newline distinctions,
  reordered vocabulary/changed weights, unsafe archives, import shadows, file changes
  and external detector patch mutation.

Verified release weights/configuration/ordered vocabulary. Current checkout is clean
`a30b153…`; declared `df0d842…` lacks the recognizer. Historical execution-time upstream
source remains unverified. Diagnostic identity:
`ade1709596afff5023e14bfb73257028ff2bc8521f4ff895ec91dc863b842cbb`.
The [identity](diagnostic-identity.json), [source snapshot](diagnostic-identity.source.zip),
[release archive](published-model.tar.gz), and [historical audit](historical-audit.json)
are preserved locally.

12 focused tests pass. Original-context full suite: 251 passed, 2 skipped; existing
bridge subtests pass. Two elevated-context historical-freeze tests fail solely on
the 33 known v5 metadata additions; neither tests nor freeze were altered. This
portability limitation is disclosed in the ledger.

Final byte verification passed, including 50 inherited detector files. Phase 1 is
complete; no worker remains. Only Phase 1 was authorized. Phase 2 timing
repair/rescoring, Phase 3 controlled inference/attribution, remedies, Rokot readiness,
training, cloud spending, confirmation and promotion require separate requests.
Historical comparison/source declarations and scores remain untouched.

For a future diagnostic replay, run the byte verifier first and collect a fresh
import-only probe under the same recorded CPU environment. Compare resolved module
paths/options/environment to the saved probe before inference. File integrity
alone does not attest a future process's import resolution or upstream parity.
