# Phase 1 request — evidence review and admission stop

2026-10-07. Owner: [archived owning plan](../../../../../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md), plan
`2026-10-03-zeus-attribution-repair`. Scope: **Phase 1 only**. Hard network cap:
**2,000,000,000 bytes total**; no later-phase execution authorized by this request.

## Outcome

Phase 1 was already implemented and accepted on 2026-10-03. Reviewed its
[original provenance ledger](../REPORT.md), [handoff](../handoff.md),
[job record](../job-record.md), [closeout](../closeout.json), and relevant
collector, identity builder, replay verifier and fixtures. No implementation
change was needed. The current plan also records later completed work; those
records were retained without executing those phases.

A fresh Git-free revalidation was prepared using the existing
`zeus_attribution_verify.py`. Its supervisor rejected admission **before launching
a worker** at 16:53:13 Europe/Istanbul: **88.326498% RAM**, exceeding the unchanged
85% stop threshold. Commit was 22,152,384,512 of 35,696,578,560 bytes. The
[receipt](jobs/bytes/result.json) and [resource sample](jobs/bytes/resources.jsonl)
are preserved. No automatic pressure retry, limit adjustment, inference, scoring,
Phase 2 work or app publication occurred. No owned Python worker or worker lock
remained; the receipt reports no cleanup error.

## Acceptance ledger

The original statuses below describe saved acceptance evidence, not a fresh
attestation of current bytes. This request's revalidation did not finish.

| Phase 1 criterion | Original acceptance | This request |
| --- | --- | --- |
| Actual imported source paths/hashes, revision and dirty state identified | **Met** | Ledger and implementation reviewed; fresh state **unverified** |
| Weights/configuration/ordered vocabulary compared with original release | **Met** | Cached archive available; fresh comparison **unverified** |
| Preprocessing, decoding, conversion and dependency versions recorded | **Met** | Saved ledger reviewed; fresh import resolution **unverified** |
| Historical provenance uncertainty separated from current evidence | **Met** | **Met**: qualification retained explicitly |
| Separate fully pinned diagnostic identity created | **Met** | Existing identity retained; current-byte validation **unverified** |
| Historical manifests/results/scores preserved and checked | **Met** | **Met** for preservation; no fresh artifact rehash |
| Relevant fixtures and complete research/bridge regression run | **Met** | Saved 12 focused / 251 passed, 2 skipped reviewed; no fresh run |
| Historical execution-time upstream source recovered/proven | **Unverified** | **Unverified**; no new execution-time evidence |
| Fresh revalidation completed for this request | Not an original criterion | **Unmet**: admission stopped before worker launch |

Original diagnostic identity:
`ade1709596afff5023e14bfb73257028ff2bc8521f4ff895ec91dc863b842cbb`.
The original ledger documents the invalid historical recognizer revision,
release-matching checkpoint/options/ordered vocabulary, and likely current
checkout without claiming recovery of historical execution-time bytes. No new
model-quality, upstream-parity or causal conclusion is supported here.

## Network accounting and remaining work

**Task artifact downloads/uploads: 0 bytes / 2,000,000,000 bytes.** No web request,
source fetch, dependency install or model download was made. All evidence was read
locally. The cached 27,051,365-byte release archive was not downloaded again.
The audit-local Python startup gate blocks network connections/name resolution
and Git launches; it recorded no blocked action. Its use does not claim to meter
unrelated host traffic or Codex service traffic.

Remaining on explicit resume after RAM relief: fresh guarded byte verification,
Phase 1 fixtures, cached release comparison and, if current process provenance is
needed, a guarded import-only probe. Do not regenerate a historical identity to
conceal drift. Preserve any mismatches and all prior failed evidence. The existing
Phase 1 acceptance permits historical-source uncertainty; fresh hashing cannot
recover missing execution-time source.

[Handoff](HANDOFF.md) retains commands, resource/network constraints and exact
continuation. No full regression rerun or release gate was required because no
research implementation, shipped code or runtime asset changed.
