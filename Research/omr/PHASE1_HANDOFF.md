# Phase 1 OMR comparison handoff

**Lifecycle update, 2026-10-04:** Completed historical comparison Phase 1; frozen contracts remain preserved.
[Plans/status index](../../plans/README.md) identifies the owning historical
plan and its successor. Current research phases belong to [the main plan](../../plans/MAIN_PLAN.md);
dated next-step/stop statements below do not authorize new execution.

## Governing plan

Read the [canonical Astra comparison plan](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md) before continuing.
This handoff records the result of its Phase 1 and entry conditions for its Phase 2;
it is not a replacement specification. The [frozen scoring protocol](reports/phase1/scoring-protocol.json)
and [plan checklist](reports/phase1/phase1-plan-checklist.json) supply the concrete contracts.

Phase 1 also froze the parent OLiMPiC test partition alongside the plan's 100-system
canary. This is a recorded implementation addition, not permission to expand the primary
ranking. Preserve the frozen collections; report any additional evaluation separately.
Only one of the seven local diagnostic pairs passed validation; retain the six exclusions.

## Stop state

Phase 1 completed and passed on 2026-09-17. Phase 2 has not started: no candidate
adapter, candidate inference, benchmark prediction, or model-selection run was added.

The frozen status is [phase1-report.json](reports/phase1/phase1-report.json), SHA-256
`96266247b0ed475f7a9dfec8248d813cb867ba7a16c6f56e00c321b3de93b211`.

## Phase-1 plan and result

| Work item | Result | Evidence |
| --- | --- | --- |
| Audit historical evidence | Passed | Every historical aggregate remains ranking-ineligible; `historical_ranking_eligible` is `0`. |
| Freeze evaluation inputs | Passed | SMB, OLiMPiC, and local diagnostic outcomes are pinned, hashed, and partition-complete. |
| Freeze development inputs | Passed | 20 open compositions and 12 project-generated controls; no composition overlap with evaluation. |
| Record per-item metadata | Passed | Source revision/hash, composition group, page/system identity, provenance, source type, notation features, and candidate-specific training-overlap disclosure are required by assembly. |
| Validate references first | Passed | All references were parsed before candidate predictions; failures are retained in the exclusion ledger. |
| Freeze scoring and acceptance rules | Passed | Accuracy, failure, resource, statistics, fixture, and promotion policies are in `scoring-protocol.json`. |
| Test source-MusicXML-to-app control | Passed | Canonical pitch, MIDI pitch, onset, duration, part, staff, and voice survive the direct bridge path. |
| Validate against the plan | Passed | 9 Phase-1 checklist entries passed; 2 adapter-dependent Phase-2 entries are explicitly deferred; every recorded artifact hash independently matched. |
| Start Phase 2 | Not started | `phase_2_started: false`; adapters, inference, and adapter-dependent fixture execution remain deferred. |

## Frozen collections

| Collection | Eligible | Excluded | Total |
| --- | ---: | ---: | ---: |
| SMB pianoform primary | 402 | 67 | 469 |
| Complete SMB secondary | 611 | 74 | 685 |
| OLiMPiC full test partition | 1,492 | 1 | 1,493 |
| OLiMPiC 100-system canary | 100 | 0 | 100 |
| Local application diagnostics | 1 | 6 | 7 |
| Open development compositions | 20 | — | 20 |
| Generated development controls | 12 | — | 12 |

The OLiMPiC exclusion is `5026306/p5-s1`: its reference emits an overfull-measure
warning that can affect canonical timing. Known wedge, pedal, dashes, bracket, and ottava
import warnings are recorded but are not exclusions because those spanners are outside the
canonical pitch/onset/duration event schema. Unknown warnings fail closed.

## Reproducibility and validation

Reference validator signatures:

- SMB: `2b709caa77b3e487d3b5b56b1bd1067ff318782a4f8a4554057b032b6c760ef3`
- OLiMPiC: `c6a2076b90efa46871ff1119a9f596b3aed4a21fb8783bbb3f74e561ef86c6f5`

Key artifact hashes:

- `scoring-protocol.json`: `0fdc0796ee68aa6920f2be20cab98e73b7565682a987eb9bedea6b2f210f809b`
- `phase1-plan-checklist.json`: `bc532181248b41995f3b8197aaa956a9cf02c9c96f6511b47f4b8053fab7dd29`
- `smb-pianoform.jsonl`: `f73419cb60019d0bfbaf7ce0efaf2fdea66d89648eec3d2552c606f2172d9a81`
- `smb-complete.jsonl`: `aa4443de3f836fca36fb3413943028fd44b9db48cb41667598385a67598d65b2`
- `olimpic-full.jsonl`: `a3a750fd8ba835b56f83dafa925af10009b53aa926fed7e20a172e390bbc2876`
- `olimpic-canary.jsonl`: `fc5da2b418b9f86b7d41a8128f6b5c5f184405b9f2233a8159999553cfcde750`

Reproduce the freeze and assembly with:

```powershell
Research\omr\.venv\Scripts\python.exe Research\omr\phase1.py --collection all
```

Validation completed:

```text
Python research + bridge: 101 collected, 99 passed, 2 expected skips, 0 failed
.NET release suite:       69 passed, 0 skipped, 0 failed
Phase-1 artifact audit:   0 hash mismatches
git diff --check:         passed
```

The release gate passed every step: lock check, tests, clean publish, 13/13 declared
content assets, 3/3 runtime-referenced assets, and published-app launch. Verified artifact:

```text
dist\Sheet2Play.exe
SHA-256 715d6dde5281e6c8b9f016a2e57dd8cc20f203705080bcae6228021e0d595319
```

Launch evidence: `dist\_verify\launch.png`.

## Important implementation notes

- Phase-1 OLiMPiC validation uses `force_source=True` so music21 cannot satisfy a
  validation pass from its parsed-object cache. The normal shipped bridge path omits this
  option and retains music21's default behavior.
- Validation caches are atomic, signature-bound, and ignored under
  `Research/omr/.runtime/phase1/`.
- SMB's license metadata is corrected to CC BY-NC 4.0 and the downloader can freeze
  metadata plus remote LFS hashes without downloading the full image payload.
- The OpenScore development downloader excludes evaluation composition IDs before applying
  its limit and rewrites a deterministic manifest; skipped files are no longer counted as
  fresh conversions.
- Existing user changes in `Research/omr/reports/diagnosis/FINDINGS.md` and the untracked
  root `AGENTS.md` were preserved.

## Known limitations retained deliberately

- SMB training overlap is unknown for most candidates and must not be called unseen.
- OLiMPiC has known OpenScore Lieder repertoire overlap and is regression evidence, not
  independent generalization evidence.
- The seven local pairs are already-inspected private diagnostics, not an untouched test set.
- Adapter-dependent scorer fixture execution belongs to Phase 2 because native-output and
  failure-path assertions require the adapter contract. The fixture contract is already frozen.

## Successor handoff

Phase 2 subsequently completed without changing these frozen artifacts. Continue from the
[Phase 2 handoff](PHASE2_HANDOFF.md), which records adapter/fixture evidence and the explicit
stop before Phase 3. This Phase 1 handoff remains the immutable record of the dataset and
scoring freeze.
