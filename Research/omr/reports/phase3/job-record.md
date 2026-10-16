# Phase 3 job record — 2026-09-25

## Boundary

Phase 3 is authorized by the user's request. The reduced roster and entry checks from
`PHASE3_READINESS_REVIEW.md` govern execution. No Phase 4 checkpoint selection, training,
accuracy ranking, promotion, or shipped-app change is in scope.

## Pinned SMB primary-image fetch

- Working directory: repository root.
- Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_fetch_inputs.py --collection smb-pianoform`.
- Input: Phase-1 `smb-pianoform.jsonl`, SHA-256 `f73419cb60019d0bfbaf7ce0efaf2fdea66d89648eec3d2552c606f2172d9a81` (402 eligible pages); `smb.lock.json`, SHA-256 `8227e7c14dc706eb59d12926a30aa4970d72dbb44db31a6be772976da733e146`, revision `96332e8c4ac81cbdb7f61093ec5a4bfff76a0adb`.
- Fetch script SHA-256: `01feea717b427bebd9a050386ef10b4a4c69a90be9aaa92d67090b0cf42fccb6`.
- Output: `Research/omr/data/smb/test/...` plus the Hugging Face local cache; progress log: `Research/omr/.runtime/phase3/smb-fetch.log`.
- Resume: check for a live fetch process before relaunch. The script skips locally present images only after checking their frozen SHA-256 and fails on mismatches. One representative image was fetched and hash verified before the full job.
- Launched with network escalation; active `exec_command` session ID `19275`. At the last read, progress was **34/402** frozen primary pages, with the latest completed item `test/beethoven/sonata05_1/sonata05_1_5.png`. The log is append-only for this run. Leave the job running; check this session and the log before doing anything else on resume.

### Resume, 2026-09-25

On resume, session `19275` was no longer attachable, no Python fetch process was live, and
the log ended at **221/402** without a traceback. The first 221 frozen image hashes were
rechecked successfully with `phase3_fetch_inputs.py --collection smb-pianoform --max-items 221`.
The same pinned fetch may therefore resume, writing stdout and stderr to separate
`Research/omr/.runtime/phase3/smb-fetch-resume.{out,err}.log` files. Check its recorded
PID **21768** before launching another copy. The script skips all 221 verified images.
The resumed fetch finished at **402/402**. A separate full audit verified the SHA-256
of all 402 images; log: `.runtime/phase3/smb-402-audit.log`, exit code 0. No SMB
candidate inference has run during the fetch or audit.

## Shipped HOMR development page entry

- Working directory: repository root.
- Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_development_entry.py homr_page`.
- Frozen development item: `openscore-6211535-page-1`, image SHA-256 `b368dd864dc235272728822a578551fbed619cce02265cc52043dea3051c57c8`.
- Configuration/input/source identity SHA-256: `85d732f3432621dcc11c185fb379acdf6399fdc102ea61a6fcd4410181087684`.
- Log: `Research/omr/.runtime/phase3/homr-page-entry.log`; raw artifacts under `.runtime/phase3/development-entry/`; immutable result and identity sidecar under `reports/phase3/development-entry/`.
- Preflight: runtime probe available; local RTX 4050 has 6141 MiB total, 0 MiB used at the check; 60.6 GiB free disk. The SMB fetch is network-only and runs separately.
- Resume: inspect process and result/raw output before retrying. The entry script refuses to overwrite any partial or completed evidence.
- Completed successfully: `homr_page-openscore-6211535-page-1-85d732f34326.json`; 14.15 s recognition/native conversion and 0.65 s shared normalization, with native tokens, MusicXML, canonical events, engine log, and no warnings. This establishes a complete-page development route, not accuracy.

## Zeus neutral development page entry

- Working directory: repository root.
- Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_development_entry.py zeus_page`.
- Frozen development item: `openscore-6211535-page-1`, image SHA-256 `b368dd864dc235272728822a578551fbed619cce02265cc52043dea3051c57c8`.
- Configuration/input/source identity SHA-256: `0c7dfd9008175c141840da3a28d54e5a7e92f8fa71f449dc7fabf5d89faec2ec`; adapter configuration SHA-256 `efb15301cda04a473423a33080cb44709e49101b1ce4e10d4bd4e2ff38d62331` includes the revised runner hash.
- Log: `Research/omr/.runtime/phase3/zeus-page-entry.log`; raw artifacts and immutable result follow the development-entry paths above.
- Preflight: Zeus runtime and checkpoint directory present; note-bearing runner/join fixture and focused regression suite passed. Resume by inspecting live process and output before retrying.
- Completed successfully: `zeus_page-openscore-6211535-page-1-0c7dfd900817.json`; 64.99 s recognition/conversion/stitching and 0.61 s shared normalization, with native LMX, MusicXML, canonical events, and no warnings. The fixture independently establishes part/tie/pickup preservation; this page establishes the revised runtime path, not general accuracy.

## Remaining development entries

Run sequentially from repository root, preserving separate logs and immutable evidence:

| Configuration | Command suffix | Item / input SHA-256 | Identity SHA-256 | Log |
| --- | --- | --- | --- | --- |
| Zeus upstream system | `phase3_development_entry.py zeus_system` | `generated-baseline-piano-001` / `2cbe267a15f2f5791943523413ce6c3d25dee32e283f43af156c7eeee5f08805` | `59b19481dbaac5c6fd8ee5ed6604f91df59600d99d47502ffe2ed0a248153bb1` | `.runtime/phase3/zeus-system-entry.log` |
| Audiveris page | `phase3_development_entry.py audiveris_page` | `openscore-6211535-page-1` / `b368dd864dc235272728822a578551fbed619cce02265cc52043dea3051c57c8` | `a91f1087c5567a1740b2a6e6531b5a72305da3bdb4f69a829d4e3cffa3b92b0d` | `.runtime/phase3/audiveris-page-entry.log` |

Use `Research/omr/.venv/Scripts/python.exe` for both. The entry script refuses to overwrite
partial or completed evidence. Check each process and result before retrying.

Both remaining entries completed successfully. Zeus upstream produced native LMX,
MusicXML, and canonical events on the generated system. Audiveris produced native
project, MusicXML, and canonical events on the development page in 21.91 s engine time
plus 0.69 s normalization, with no warnings. The revised Zeus page, HOMR page, and
these two routes therefore have development execution evidence; accuracy is unmeasured.

The shared research adapter was subsequently changed to preserve full logs and partial
outputs on HOMR/Zeus failure. `ADAPTER_REVISION` is source-derived, so all four earlier
development-entry configurations are historical, not the final frozen identity. Run the
same four development entries once under their new identities before creating the freeze:

| Configuration | New source/input identity SHA-256 | New adapter configuration SHA-256 | Log |
| --- | --- | --- | --- |
| HOMR page | `c624ddab6590847d7a6f54a1034bee12ffcb9bf1810857b3dda2bdb88072f967` | `ebf2773246e5dc58d0d0ffbbcc18a388c3f17937b3de85cb087d16d67578198c` | `.runtime/phase3/homr-page-entry-v2.log` |
| Zeus neutral page | `9c064b3ed7dcf47c119f51644b824ad52a415557d9335f6fc3c7c8cceb23dd07` | `7373b663fc5ac2e69ded8d5b3fb2b8e5dd9ccbfc13fc75f05eec1dcd322340bb` | `.runtime/phase3/zeus-page-entry-v2.log` |
| Zeus upstream system | `6f7a23d48dc7839e4a39e3c314376ab0c140c1d986f4824c86b964314b1b5537` | `f1abe5752acf0798ba742a9da259fe40673271aa2643e1a325dfd1accca0689c` | `.runtime/phase3/zeus-system-entry-v2.log` |
| Audiveris page | `45d0929784d0cc3c30d3615bcf3c5e49df9dc86dde1cab7aab712c7234ebfc0f` | `a60883fe6e39455af4f2c39ce62de54618d0c4ffe5de8f3da4d359f8bfed7b0c` | `.runtime/phase3/audiveris-page-entry-v2.log` |

## SMB complete-page reference audit

- Working directory: repository root.
- Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_reference_audit.py --collection smb-pianoform`.
- Input identity: frozen primary manifest `f73419cb60019d0bfbaf7ce0efaf2fdea66d89648eec3d2552c606f2172d9a81`; SMB metadata `3a1f727011fb6a468dbdaa45052f4b35e7282c4002fe4e395d98d369a7101c52`; parser source `0bea9cdb67f60110ff53305904909ddb56de9d965958b344aa824244ef900c8d`.
- Reference-builder source `6172cd483a1b0a2986c3a01ff60ccbfbfa177218e5c5cc78acd1a4aeeb8f04e3`; audit runner `dcbe4daccf613f9755d901acb03966e970d3e1fbb72355c223d098a357fd6d68`.
- Output: immutable per-item JSON under `.runtime/phase3/references/`; full audit report under `reports/phase3/`; stdout/stderr logs `.runtime/phase3/reference-audit.{out,err}.log`.
- Preflight: first page parsed and produced 471 sounding notes from seven regions; cross-region tie fixtures passed 4 tests. All 402 page images passed frozen SHA-256 audit.
- Resume: check the PID below and final report before relaunch. A complete report with invalid references blocks candidate inference. Per-item references are reused only when input/code identities match.
- Background process PID **16644**. The launching shell also returned `exec_command` session ID `32988`; use the PID and logs if that session becomes unavailable.

## Secondary complete-SMB image preparation

- Working directory: repository root. Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_fetch_inputs.py --collection smb-complete`.
- Frozen complete manifest SHA-256 `aa4443de3f836fca36fb3413943028fd44b9db48cb41667598385a67598d65b2` (611 eligible pages); pinned SMB lock SHA-256 `8227e7c14dc706eb59d12926a30aa4970d72dbb44db31a6be772976da733e146`; fetcher SHA-256 `01feea717b427bebd9a050386ef10b4a4c69a90be9aaa92d67090b0cf42fccb6`.
- Preflight: 209 images missing, 244,293,169 expected bytes; 63.95 GB free disk. Fetch verifies all local and downloaded hashes. Separate stdout/stderr logs `Research/omr/.runtime/phase3/smb-complete-fetch.{out,err}.log`.
- Resume: inspect process PID and latest log before launching another copy; existing images are rehashed and skipped. No secondary inference is authorized until its references and configuration identity pass.
- Launched hidden background process PID **17256**.
- Completed **611/611** pinned images; the last item was `test/weber/erk164/erk164_1.png`. A separate full hash audit remains to run before secondary inference.

## SMB reference audit, builder `1001ca94` (diagnostic)

- Working directory: repository root. Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_reference_audit.py --collection smb-pianoform`.
- Frozen primary manifest SHA-256: `f73419cb60019d0bfbaf7ce0efaf2fdea66d89648eec3d2552c606f2172d9a81`; SMB metadata SHA-256: `3a1f727011fb6a468dbdaa45052f4b35e7282c4002fe4e395d98d369a7101c52`.
- Corrected builder SHA-256: `1001ca94138001790aceb0c6565447d81b4a480b3e989f8c7f7361b85c4949d0`; runner SHA-256: `24fbec470c2cb8cef978ee5a4a9d43df1f4a97ba38019ff8c12f3e19bea71f40`.
- First frozen item passed 471 notes, zero normalization warnings, and round-trip note timing validation. Full output will be `reference-audit-smb-pianoform-full-1001ca941380.json`; stdout/stderr logs `Research/omr/.runtime/phase3/reference-audit-v2.{out,err}.log`.
- The earlier audit with builder `6172cd483a1b...` is historical diagnostic evidence and cannot satisfy the Phase-3 freeze. It remains running until completion. This corrected job uses different immutable reference paths and may reuse only artifacts with the exact new identity.
- Resume: inspect the corrected job PID and logs before relaunching. Require 402/402 valid and zero warnings before freeze or inference.
- Launched hidden background process PID **10032**; launcher session ID `93939`.

## SMB reference audit, builder `cbc03074` (current)

- Working directory: repository root. Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_reference_audit.py --collection smb-pianoform`.
- Input: frozen primary manifest SHA-256 `f73419cb60019d0bfbaf7ce0efaf2fdea66d89648eec3d2552c606f2172d9a81`; metadata SHA-256 `3a1f727011fb6a468dbdaa45052f4b35e7282c4002fe4e395d98d369a7101c52`.
- Builder SHA-256 `cbc030745b1d3318513f21c39e51c2ee1bb99b1a6a66485d6be2ca323bbf5af0`; audit runner SHA-256 `24fbec470c2cb8cef978ee5a4a9d43df1f4a97ba38019ff8c12f3e19bea71f40`.
- The builder now pads every short measure before MusicXML export. It passed the actual Haydn failure item (392 notes, exact raw timing) and two synthetic partial-measure tests. A first frozen page passed with 471 notes and no warnings. Output: `reference-audit-smb-pianoform-full-cbc030745b1d.json`; logs `.runtime/phase3/reference-audit-v3.{out,err}.log`.
- Resume: inspect the active PID and logs; do not relaunch against the same identity. Freeze requires 402 valid references. Pedal-only MusicXML warnings are being classified separately from note/rhythm corruption.
- Launched hidden background process PID **22120**; launcher session ID `26267`.

## OLiMPiC canary annotated-system reference audit

- Working directory: repository root. Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_olimpic.py audit`.
- Frozen 100-system manifest SHA-256 `fc5da2b418b9f86b7d41a8128f6b5c5f184405b9f2233a8159999553cfcde750`; audit/runner source SHA-256 `8493bc91c9e5d91880ceec01585a2b9d1802290534fb6607db612637db918685`.
- First system preflight passed image/reference hash validation and shared normalization with 95 notes, six measure boundaries, and no warnings. Output is immutable `reports/phase3/olimpic-canary-reference-audit-8493bc91c9e5.json`; per-system references are under `.runtime/phase3/olimpic-references`; logs `.runtime/phase3/olimpic-reference-audit.{out,err}.log`.
- Resume: inspect audit process and logs before relaunch. A 100/100 valid audit and unchanged builder/normalizer/input hashes are required for system inference.
- Launched hidden background process PID **22988**.
- Completed **100/100** valid canary references with 30 recorded, Phase-1-allowed notation warnings and no invalid systems. The freeze verifier rehashed every canary image, MusicXML, and canonical reference and accepted the audit SHA-256 `453826ef232be08a681cbb699449c911bcebffa2be94f65c53ab0928efaad93c`.

## SMB reference audit, builder `0bd4f11e` (current)

- Working directory: repository root. Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_reference_audit.py --collection smb-pianoform`.
- Frozen manifest SHA-256 `f73419cb60019d0bfbaf7ce0efaf2fdea66d89648eec3d2552c606f2172d9a81`; metadata SHA-256 `3a1f727011fb6a468dbdaa45052f4b35e7282c4002fe4e395d98d369a7101c52`.
- Builder SHA-256 `0bd4f11ed34affe2a07604963e98c4d06fa07d4ef503c5007a0c4f3aa9a5b87a`; audit runner SHA-256 `24fbec470c2cb8cef978ee5a4a9d43df1f4a97ba38019ff8c12f3e19bea71f40`.
- Preflight: first frozen page 471 notes, no warnings, exact raw note timing; known Bach returning-staff, Beethoven overlapping-rest, and Haydn short-measure failures pass. Output `reference-audit-smb-pianoform-full-0bd4f11ed34a.json`; logs `.runtime/phase3/reference-audit-v4.{out,err}.log`.
- Resume: inspect PID/log and final report. Require 402/402 valid. The older `6172`, `1001`, and `cbc0` builder audits remain immutable diagnostic evidence and cannot satisfy this freeze.
- Launched hidden background process PID **4896**; launcher session ID `96114`.

## Complete-SMB secondary reference audit

- Working directory: repository root. Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_reference_audit.py --collection smb-complete`.
- Frozen 611-page manifest SHA-256 `aa4443de3f836fca36fb3413943028fd44b9db48cb41667598385a67598d65b2`; metadata SHA-256 `3a1f727011fb6a468dbdaa45052f4b35e7282c4002fe4e395d98d369a7101c52`.
- Builder SHA-256 `0bd4f11ed34affe2a07604963e98c4d06fa07d4ef503c5007a0c4f3aa9a5b87a`; audit runner SHA-256 `24fbec470c2cb8cef978ee5a4a9d43df1f4a97ba38019ff8c12f3e19bea71f40`.
- All 611 pinned image hashes passed a separate local audit (`.runtime/phase3/smb-complete-611-audit.log`). First secondary reference passed with 63 notes, exact raw timing, and no warnings. Output `reference-audit-smb-complete-full-0bd4f11ed34a.json`; logs `.runtime/phase3/smb-complete-reference-audit.{out,err}.log`.
- Resume: inspect PID/log; never relaunch against the same identity while running. Require 611 valid references or adjudicate a frozen exclusion ledger before evaluation.
- Launched hidden background process PID **19800**; launcher session ID `20118`.

## Entry state

- Phase-1 report plus all 15 frozen artifacts and four historical Phase-2 artifacts verified unchanged.
- Focused Phase 2/2R tests passed (29). The Zeus runner's note-bearing join fixture passes after matching parts by stable IDs; actual development inference and full suite still pending.
- The historical Phase-2R identity report incorrectly marks Zeus checkpoint missing because the checkpoint is a directory. Phase-3 identity will hash `weights.h5`, `options.json`, and `tags.txt` individually.

## SMB full reference audits, builder `6e027f2195f3` (2026-09-25)

- Working directory: repository root. Commands: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_reference_audit.py --collection smb-pianoform` and the same command with `--collection smb-complete`.
- Frozen manifest SHA-256: primary `f73419cb60019d0bfbaf7ce0efaf2fdea66d89648eec3d2552c606f2172d9a81`; secondary `aa4443de3f836fca36fb3413943028fd44b9db48cb41667598385a67598d65b2`. SMB metadata SHA-256 `3a1f727011fb6a468dbdaa45052f4b35e7282c4002fe4e395d98d369a7101c52`.
- Reference builder SHA-256 `6e027f2195f355e0ea0ff4c09dbadb2bfc87049a05fa3131c85089d0d2cc481f`; audit runner SHA-256 `24fbec470c2cb8cef978ee5a4a9d43df1f4a97ba38019ff8c12f3e19bea71f40`.
- Preflight: first primary and secondary items passed; all 34 failures from the prior secondary audit passed direct round-trip checks under this revision; 5 focused reference tests passed. The older secondary audit finished 577 valid / 34 invalid and is diagnostic only.
- Primary report: `reports/phase3/reference-audit-smb-pianoform-full-6e027f2195f3.json`; logs `.runtime/phase3/reference-audit-v5.{out,err}.log`. Secondary report: `reports/phase3/reference-audit-smb-complete-full-6e027f2195f3.json`; logs `.runtime/phase3/smb-complete-reference-audit-v2.{out,err}.log`. Per-item references are immutable under `.runtime/phase3/references/`.
- Resume: inspect report existence, last progress line, and process PID before relaunching. Reuse only exact matching source/input identities. Primary 402/402 valid gates the Phase-3 freeze; secondary 611/611 valid gates secondary inference.
- Launched hidden primary audit PID **2812** (`exec_command` session `42986`) and hidden secondary audit PID **24400** (`exec_command` session `44630`). These run against the same builder revision with separate per-collection identities and logs.

## OLiMPiC canary reference re-audit after score persistence

- Working directory: repository root. Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_olimpic.py audit`.
- The OLiMPiC runner now saves 100 individual score artifacts with source/result/reference identities; its source SHA-256 is `5382d5ffb4b37eb721c7c843cc7fe2a20611b194535ec6d7199edba1b7a6205b`. This changes the audit identity despite unchanged frozen inputs and reference logic.
- Frozen OLiMPiC manifest SHA-256 `fc5da2b418b9f86b7d41a8128f6b5c5f184405b9f2233a8159999553cfcde750`; output `reports/phase3/olimpic-canary-reference-audit-5382d5ffb4b3.json`; logs `.runtime/phase3/olimpic-reference-audit-v2.{out,err}.log`. The prior `8493bc91c9e5` audit is historical evidence.
- Resume: check final report and process before relaunching; require 100/100 valid and only the previously reviewed warning classes before configuration freeze.
- Launched hidden audit PID **26052**.
- Completed **100/100** valid with 30 previously reviewed warnings. `phase3_freeze._olimpic_audit()` rehashed all 100 images, MusicXML files, and canonical references and accepted report SHA-256 `1111a7f43ba8bb5901a9d21f99e217995522c576c4cb5ee9bbccf96c77b43b46`.

## Eligible local diagnostic rendering

- Working directory: repository root. Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_private_preflight.py`.
- The single eligible Phase-1 private pair was located by its opaque ID. Its local PDF and symbolic reference exist and match frozen SHA-256 values. Names and source paths stay out of reports.
- Preflight source SHA-256 `4524dec41633cea73bd2e652d123b41903e782cbdfa94954ba058d3a9e2b793a`; 300-DPI `pdftoppm` renderer is available. Expected page count is eight from the Phase-1 coverage review.
- Output: ignored local `.runtime/phase3/private-diagnostic/preflight.json` and `.runtime/phase3/private-diagnostic/pages/page-*.png`; source/renderer/page hashes and dimensions are pinned there. This is already-inspected diagnostic material, not ranking data.
- Resume: if a report exists, run the script's `verify()` to rehash all eight pages. If only a partial pages directory exists, inspect it before retrying; the renderer refuses to reuse unverified pages.
- Completed all **8/8** 300-DPI page renders. The preflight rehashed every page and accepted report SHA-256 `b1307979253a5274f44e2fd42ce76b257a3ce36df6badd314999664fe98e0dcb`.
- `phase3_private_diagnostic.py` now provides eight-page per-candidate local inference and an explicitly unaligned document-wide pitch-count diagnostic; it does not claim page-level onset/duration F1 or ranking eligibility. Its source is included in the configuration freeze. No private candidate inference has run yet.

## Candidate-launch preflight while reference audits run

- Historical Phase-1/2 evidence, current HOMR/Zeus/Audiveris runtime identities, all four current development-entry identities, and frozen scorer package versions passed separate read-only checks. Scorer versions are music21 9.9.1, converter21 4.0.1, and musicdiff 5.2.
- The local GPU is an NVIDIA GeForce RTX 4050 Laptop GPU with 6,141 MiB installed and 0 MiB used at the preflight snapshot. C: had about 62.6 GB free. No GPU-heavy frozen inference has started.
- The private symbolic reference parses as 2,229 sounding notes across two parts and 480 quarter notes, consistent with the frozen eight-page coverage review. This does not establish page-level onset boundaries.
- Seven in-progress primary references (including a pedal-warning page) were independently compared after shared normalization against their exported MusicXML sounding-note pitch/onset/duration counters. All seven had zero missing or extra events. The builder's complete per-item round-trip check remains the formal gate; this sample checks the additional normalizer transition.
- The pending configuration freeze now pins named package versions in all three Python environments: 79 research, 35 HOMR, and 72 Zeus distributions. Unnamed stale metadata entries are ignored; duplicate named distributions are rejected. This complements hashed model sources, weights, scripts, and executables.

## Prepared unattended Phase-3 sequence (not launched)

- `phase3_sequence.py` source SHA-256 `ffc6e32d5800af2f29e6f01b7c1e9814105926b7d8d59b858404073739abfa94`; pure plan check found 20 unique stages, ten summary stages, and all script paths present.
- After the current primary audit passes, create the configuration freeze and preflight one frozen item per ready route. Then launch `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_sequence.py --freeze <absolute-freeze-path>` from the repository root, hidden, with separate top-level stdout/stderr logs. The sequence runs one candidate stage at a time and uses per-item identity caches.
- Its state and per-stage logs will be under `.runtime/phase3/sequence/<freeze-sha-prefix>/`. It records the active child PID and stops on infrastructure failure; inspect a `running` or `failed` stage before restart. Do not launch a duplicate sequence against the same freeze.
- A read-only snapshot preflight temporarily substituted only the still-running primary reference-audit field in memory (no freeze file written). Every other gate passed: 402 image hashes, 100 OLiMPiC references, eight private pages, four development entries, historical artifacts, all candidate runtimes, and 13 pinned research sources. The actual freeze still requires the completed 402/402 audit.

## One-time Phase-3 bootstrap and sequential evaluation

- Working directory: repository root. Command: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_bootstrap.py --primary-pid 18944 --primary-created-at 1790364255.1055455`.
- Bootstrap source SHA-256 `20a01e3ee00a47e1ddb70ba2371cb046ca5acecfc28855cdb945503209065a0c`; freeze source SHA-256 `e684af6d019caeca87ca58b84e81ba4215f1d01859186a5557b20b5b447d3110`. A read-only snapshot preflight passed every gate except the still-running primary audit; the final snapshot pins 13 research sources.
- Primary audit process identity is PID **18944**, creation epoch `1790364255.1055455`; its own launcher is PID 2812. The bootstrap waits for that exact process and verifies the full 402/402 report with hashes and reviewed warnings before writing a freeze. It does not alter the active audit.
- Top-level logs: `.runtime/phase3/bootstrap.{out,err}.log`. Frozen one-item logs: `.runtime/phase3/bootstrap-preflight/`. The seven one-item checks cover the three primary page routes, Zeus annotated system, and the same three routes on the first private diagnostic page. Benchmark item failure is retained as an outcome; infrastructure failure stops the bootstrap.
- After checks, `phase3_sequence.py` runs the 20-stage local sequence with one candidate stage at a time. Its state/logs are under `.runtime/phase3/sequence/<freeze-sha-prefix>/`; no cloud or shipped-app changes. Inspect top-level and stage logs, active PIDs, and immutable identities before resuming or restarting; do not start a duplicate bootstrap/sequence.
- Launched hidden bootstrap wrapper PID **14736**, worker PID **25200** (`exec_command` session `53822`). Its log confirms it is waiting on the exact primary audit PID; stderr is empty.
- After the bootstrap source was added, the full research test suite passed **115/115** again. The seven frozen preflight command paths and 20 sequence-stage command paths exist, source files compile, the documentation links resolve, and no trailing whitespace was found in the touched Phase-3 files.

## 2026-09-26 interrupted-run recovery

- Phase boundary: finish only the frozen reduced Phase 3 comparison. No Phase 4 checkpoints, training, promotion, or app publish.
- The primary reference audit completed **402/402 valid**. The immutable configuration freeze `reports/phase3/phase3-config-freeze-v1-89f385c8790b.json` still verifies at SHA-256 `3fdd3d76aeab4188244795ea7b5eb310b2129d8d50131290297aeb1a32020633`. All seven frozen one-item preflights had completed before the interruption.
- No Phase 3 workers were live on resumption. Sequence stage 1 remained marked `running` at old PID 14012. Its old log ended at item **76/402**, with 75 succeeded and one failed result; all 76 reports, identity sidecars, and declared artifacts were independently rehashed and verified. Item 77 had only an empty raw-output directory. The old stage state was backed up at `sequence/3fdd3d76aeab/state.interrupted-20260926.json` (SHA-256 `66ab9d2ba06c7764199dac4a363b92b138c537ae220c0a330d93798e6f4191d3`), and its stdout/stderr logs were moved to same-directory `*.interrupted-20260926.*.log` names. The empty item-77 directory was preserved under `.runtime/phase3/recovery-20260926/`. Stage 1 is now `pending` with the original attempt embedded in the state; the sequence runner will verify cached items before generating item 77.
- The secondary reference audit had logged **432/611 valid** before interruption, with no full report. Item 433 had a MusicXML file but no verified JSON reference. That file (SHA-256 `f8e8adbf2a62b7025dd792bedeee443ccee05eaf82a3280f9cebaf82ea4e7a55`) was preserved under `.runtime/phase3/recovery-20260926/` so the same-identity audit can regenerate and validate item 433. Prior audit log `smb-complete-reference-audit-v2.out.log` remains unchanged (SHA-256 `9c45d9851b67c3272887af57aac37ffa56f867b12fd61fdae48a6583d2fc5ec7`).
- Secondary resume command from repository root: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_reference_audit.py --collection smb-complete`. Frozen manifest SHA-256 `aa4443de3f836fca36fb3413943028fd44b9db48cb41667598385a67598d65b2`; builder SHA-256 `6e027f2195f355e0ea0ff4c09dbadb2bfc87049a05fa3131c85089d0d2cc481f`; output report `reports/phase3/reference-audit-smb-complete-full-6e027f2195f3.json`; new logs `.runtime/phase3/smb-complete-reference-audit-v3.{out,err}.log`. It must finish 611/611 before any secondary inference stage.
- Evaluation resume command from repository root: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_sequence.py --freeze Research/omr/reports/phase3/phase3-config-freeze-v1-89f385c8790b.json`. New top-level logs `.runtime/phase3/sequence-resume-20260926.{out,err}.log`; per-stage logs and state stay under `.runtime/phase3/sequence/3fdd3d76aeab/`. The local 6 GB GPU was idle and C: had about 59.5 GB free at preflight. Do not launch duplicate sequence or secondary audit processes. On any failure, inspect state, log, partial output, and immutable identity before a retry.

## 2026-09-26 secondary audit completion

- The resumed `smb-complete` audit finished 611/611 valid with zero invalid references; its stderr was empty and its launcher exited 0. Full report: `reports/phase3/reference-audit-smb-complete-full-6e027f2195f3.json`, SHA-256 `50e5f6942eb2282c37fdecbf5c31b9bb7330224b794620baab1514eb9494b6fb`.
- Independent `phase3_freeze.verify_secondary_audit()` verified all 611 report entries, canonical reference and MusicXML hashes, frozen image hashes, coverage, and accepted warning classes. It counted 488 known pedal-import warnings and zero missing-voice-tag warnings. The references had verified exact note timing before normalization.
- The secondary inference gate is now ready for the ongoing sequence. Do not launch a separate secondary worker while its ordered sequence remains active.

## 2026-09-26 one-time completion monitor

- The 20-stage sequence remains the only inference worker. At monitor preparation, primary HOMR inference had reached item 166/402 with empty stderr; the sequence launcher PID **24440** had creation epoch `1790413698.3434684`. Its earlier cached 76 results and the completed secondary reference audit remain verified.
- A one-time local monitor waits for that exact sequence process identity. It does not launch inference or retry failed stages. On all 20 stages complete, it rechecks the freeze, both audit gates, stage exit codes and summary hashes, validates eligible counts and metric ranges, writes `reports/phase3/PHASE3_COMPLETION_REPORT.md`, and updates the active handoff and `CONTEXT.md`. If a stage fails or the sequence stops early, it exits with an error for manual diagnosis. It never starts Phase 4.
- Monitor source: `phase3_completion.py`, SHA-256 `272ff7c4239d81910b5024cf027909163c57566052457e1abbf684ee07727915`. The module compiled, `--check` reported 0/20 completed while the sequence ran, and a bounded synthetic page-summary validation/format check passed. Adding this postprocessing file did not change the pinned freeze; `phase3_freeze.py --verify` still passed.
- Planned command from repository root: `Research/omr/.venv/Scripts/python.exe Research/omr/phase3_completion.py --wait-pid 24440 --created-at 1790413698.3434684`. Logs: `.runtime/phase3/completion-monitor.{out,err}.log`. Before any restart, inspect those logs, the sequence state, and whether the monitor process remains alive. The monitor writes the completion report once and refuses to overwrite a different report.
- Launched hidden completion monitor PID **3292**, creation epoch `1790415206.536939`, after confirming the sequence PID and creation epoch. Its command line matched the planned command, its logs were empty at the first health check, and both the monitor and sequence were alive.
- An isolated document-update fixture passed, including repeat invocation without duplicate completion notices. A first fixture attempt used literal `\\n` characters instead of real line breaks and failed the insertion-point check; the corrected newline fixture passed. No production document was written by either fixture.

## 2026-09-26 PC hard-freeze interruption — no restart authorized yet

- The user reported a PC hard freeze and requested dataset, runtime, and GPU answers before evaluation resumes. Read-only inspection found sequence launcher PID 24440, inference worker PID 26892, and completion monitor PID 3292 absent. The sequence state remained stale at stage 1 `running`, 0/20 stages complete; the stage log ended at item 255/402 with empty stage and top-level stderr. The monitor logs were empty and no completion report exists.
- The primary HOMR report directory currently has 255 result JSON files and 255 identity sidecars. Its raw-output area has 256 directories, so item 256 is partial until inspected. The 255 outputs have **not** been independently rehashed after this interruption. The last report modification time was 2026-09-26 12:52:26 Europe/Istanbul. The verified 402/402 and 611/611 reference audits and the original freeze remain historical evidence, but all live identities must be checked again before any restart or transfer.
- Exact next action: decide whether to stay on this PC or move to the other PC after checking its OS, CPU, RAM, GPU/VRAM, and disk. Then inspect the partial item, verify the freeze and all saved artifacts, preserve old state/logs, and create a new bounded resume record. Do not launch a duplicate sequence or monitor from the stale `running` state. No Phase 4 work.
