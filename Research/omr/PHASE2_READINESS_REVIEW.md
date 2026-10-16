# Phase 2 readiness review — 2026-09-18

## Recommendation

Complete a bounded readiness follow-up before frozen Phase-3 evaluation. The user requested
analysis and a go/no-go recommendation, not execution of Phase 3. No evaluation inference,
training, engine installation, or production changes were performed during this review.

Read this alongside COMPARISON_PLAN.md and PHASE2_HANDOFF.md. This review does not replace
the canonical plan or alter the frozen Phase-1 or Phase-2 artifacts.

## Independently checked

- Read the canonical plan, both handoffs, Phase-2 report/checklist/adapter manifest, relevant
  adapter and fixture code, and the frozen scoring protocol.
- Ran `Research/omr/.venv/Scripts/python.exe -m pytest Research/omr/tests/test_phase2.py Research/omr/tests/test_phase2_zeus_runner.py Bridge/tests/test_detect_systems.py -q`.
  All 12 targeted tests passed. This includes the Phase-1 artifact hash verification.
- The report contains three real development successes: HOMR on one generated crop, Zeus
  upstream on the same crop, and Zeus integration on one open-development page. These are
  execution smokes, not comparative accuracy or speed evidence.
- LEGATO and Audiveris are explicitly unavailable; their execution tests mock the external
  processes and canonicalization. They have not yet passed actual end-to-end inference.

## Readiness gaps

1. In `src/sheet2play_omr/phase2_fixtures.py`, the empty-output and missing-middle-system
   fixtures pass literal `True` into `_fixture` and supply expected failure dictionaries.
   They do not exercise detection, typed failure propagation, or aggregate zero-F1 handling.
   Replace these with executed failure-path tests before trusting the 14-pass claim. Empty
   canonical output is rejected by `_canonicalize`; that existing rejection still needs to
   be tested through the result/scoring path. Do not infer from this review that rejection
   itself is absent.
2. Install and verify the pinned LEGATO and Audiveris runtimes, then run real development
   inference and conversion checks before their frozen evaluation. Previous HF access checks
   in this conversation succeeded; the report's missing-runtime message does not demonstrate
   that account permission is missing. Recheck access at setup time.
3. Strengthen reproducibility verification before the benchmark: configurations declare source
   and checkpoint identities, but the reviewed provenance test only checks revision-string
   and config-hash lengths. Verify actual loaded weight hashes, source state, and installed
   executable versions. A config hash alone does not verify those external files.
4. Broaden development validation beyond the two smoke inputs, covering multi-voice rhythm,
   tuplets, ties, meter changes, and multi-system joins with real conversion paths. Do not
   debug or select settings on SMB, OLiMPiC, or private evaluation diagnostics.

## Interpretation and next authorized step

The repaired Zeus detector compatibility issue demonstrates a real integration defect,
but does not establish that it caused all historical poor accuracy or that Zeus beats HOMR.
The benchmark remains necessary. The 402 eligible SMB pianoform pages can support the
planned comparison; 67 exclusions and only one eligible private diagnostic pair limit
generalization and must remain visible.

After the readiness checks pass, proceed with Phase 3 when explicitly requested. Preserve
Phase-1 artifacts; record additional development evidence and revised implementation/config
hashes as a new version rather than overwriting historical Phase-2 evidence. Fine-tune
checkpoint evaluation remains Phase 4. No replacement decision is justified yet.

Review stopped at the user's usage threshold: five-hour usage 87% consumed, 13% remaining.
No further investigation was performed after that reading; only this handoff was saved.
