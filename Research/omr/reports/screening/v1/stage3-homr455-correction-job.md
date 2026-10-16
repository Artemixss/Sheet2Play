# HOMR 455 compatibility correction — development job record

Working directory: `C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play`.

## Pinned inputs and stop point

- Release source checkout: `Research/omr/.runtime/homr-455-compatible/source`, clean detached commit `a4865663e7278f908d6d1b1a57d549f9ca3d1067`. The screened checkout remains at `Research/omr/.runtime/homr-455/source`.
- Encoder SHA-256: `7b9ba90082ef5096df51a9faf7c7960d6b9e5efaea5feb41d245d3172a6073ba`; decoder SHA-256: `6b261559c235c79b656dd3b83b75a275ce917029fe5c743328d482c406af140d`.
- Final manifest: `Research/omr/reports/screening/v1/manifest-v3-0b5eb110e968.json`, SHA-256 `5e59f99006c4a8c7c169eee667080f7ff7537010bb1c6f3f91952ee70571de4f`. Sample SHA-256 `2c98d5638c368b1a53bdb3440177d04fa585f9b1ca6ce6adbe65af64cd8e27d1`; corrected 455 identity `a2411bef278d7a511ff9ece34c5096b7ef3f4ed0bbdee71484e5dd9dc0fdbb3e`; shipped control identity `0a0004e3c354793271a4298ec7a8c14ff68653acd1704d2cf9e0ffa30250ce51`.
- Compatibility report: `Research/omr/reports/screening/v1/compatibility/homr455-3c9f495122d6.json`, SHA-256 `14c6ad366d41a48afb6323b7356cac62296c31dc6d9751d7af1ecd34514e3303`.
- 2026-09-27 preflight: 84.3% system RAM, 0/6,141 MiB device-wide VRAM, no worker lock. The user authorized a **95% RAM threshold for these development pages only**; the 75% screening policy remains unchanged. Each development attempt records its effective limit and retains the five-second sampling and 30-second pressure stop. The system process inventory is access denied; no `python` or `git` worker appeared in `Get-Process`.
- `manifest-v3-c82c41a2f0e9.json` was prepared before the authorized RAM change and has no inference. `manifest-v3-4080269113d5.json` captured the 95% limit and three successful development pages plus one admission, but the verifier could recreate a missing compatibility report. The final manifest pins the corrected fail-closed verifier. Earlier reports remain preserved and cannot satisfy its new identity.

## Authorized development sequence

Run only after a fresh resource sample passes the **development 95% RAM** and existing VRAM limits and the shared worker lock is absent. Each command is sequential; stop on a failed or pending result. The exact configuration and input identities are in the manifest and development-open manifest. Preserve full stdout/stderr in separate `Research/omr/reports/screening/v1/homr455-compatible-final-{1,2,3}.log` files.

```powershell
$manifest = 'Research/omr/reports/screening/v1/manifest-v3-0b5eb110e968.json'
Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_development.py --manifest $manifest --candidate homr_455 --item-id openscore-6211535-page-1 --session-id homr455-compatible-final-01
Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_development.py --manifest $manifest --candidate homr_455 --item-id openscore-6211549-page-1 --session-id homr455-compatible-final-02
Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_development.py --manifest $manifest --candidate homr_455 --item-id openscore-6211555-page-1 --session-id homr455-compatible-final-03
```

Before any resume, inspect live processes and `2c98d5638c36/worker.lock`, the three final log files, development attempts, and immutable reports under `2c98d5638c36/development/homr_455/a2411bef278d/`. Do not score or launch the 59-page screen under this correction request.

## Final validation and handoff

- All three final commands above returned successful complete-page reports and matching identity sidecars under `2c98d5638c36/development/homr_455/a2411bef278d/`. Full command output is retained in `homr455-compatible-final-1.log`, `-2.log`, and `-3.log` beside this record. No pending attempts or worker lock remain.
- Development results, in listed page order: native position tokens `upper/lower` **102/142**, **107/104**, and **59/0**; MusicXML staff 1/2 note counts **101/137**, **106/103**, and **57/0**; canonical note counts **222**, **181**, and **42**. All three had exit status zero, zero normalization warnings, and no declared artifact hash/size mismatch. Peak sampled system RAM was **83.9%**, **83.0%**, and **84.0%**; device-wide VRAM **1,245**, **1,415**, and **1,417 MiB**. No resource interruption occurred.
- On the first page, the old incompatible development result has **142 `upper2`** tokens and all **238 MusicXML notes on staff 1**. The corrected result has **142 `lower`** tokens and **137 of 238 notes on staff 2**. This demonstrates the routing repair; no accuracy score was computed.
- Final admission command: `Research/omr/.venv/Scripts/python.exe -B Research/omr/screening_admit.py --manifest Research/omr/reports/screening/v1/manifest-v3-0b5eb110e968.json --candidate homr_455 --development-report Research/omr/reports/screening/v1/2c98d5638c36/development/homr_455/a2411bef278d/openscore-6211535-page-1.json`. Admission: `2c98d5638c36/admissions/homr_455/a2411bef278d/admission-4252a5d236bd.json`, SHA-256 `c9c6cb3390d1d0ba145cf93a9951eb3ea1a91db95dacf1fecfafd28a590b782c`.
- `screening_run.validate_admission` accepted the final admission and rejected the old `cb45056ebb22` admission. All **59** historical 455 completed results and their declared artifacts still verify against their saved v2 identities. The original sample, scorer, and shipped control identities equal the v1/v2 values. The v2 configuration is rejected for new execution.
- Full research and Bridge suite: **199 passed, 2 skipped, 9 subtests passed**, with one expected `music21` warning. `git diff --check` passed, apart from existing Windows line-ending notices. This is research-only work; no desktop publish was needed.
- Stop state: corrected development admission complete. The separately selected 90% RAM policy for any future screen is not present in this manifest, whose screening policy remains 75%; version the runner/policy/manifest before a separately requested corrected 59-page screen. Fine-tune provenance, Audiveris, Zeus, training, promotion, and production publishing remain separate.
