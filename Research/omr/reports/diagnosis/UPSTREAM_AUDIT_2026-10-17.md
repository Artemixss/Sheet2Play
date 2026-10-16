# HOMR upstream audit — 2026-10-17

## Decision and scope

Upstream published a new checkpoint, **run 480**, and merged exporter and staff-detection
fixes that the app's pinned 465 runtime (`33baa32`) predates. One of them removes the exact
assertion that failed the only unsuccessful score in the 465 library migration. The user
selected a [separate bounded task](../../../../plans/2026-10-17-upstream-exporter-480.md) to
evaluate these; the [displacement plan](../../../../plans/2026-10-17-displacement-correction.md)
does not wait for it.

This audit ran no inference, scoring, download or release. It read the GitHub REST API.

- Prior audited main: `33baa326900faa12702df8c4bdcbea034a3d6a34` ([October 6 audit](UPSTREAM_AUDIT_2026-10-06.md)).
- Current main: `ab369ac54277afab582afa4725441f7cbba76593`, 2026-10-15.
- [Complete comparison](https://github.com/liebharc/homr/compare/33baa326900faa12702df8c4bdcbea034a3d6a34...ab369ac54277afab582afa4725441f7cbba76593):
  25 commits, 34 files. PyPI is still 0.7.0 (2026-06-26).
- Release assets: 87, up from 84. The three new ones are run 480's encoder, FP16 encoder
  and decoder, created 2026-10-15. **There is no FP16 decoder for 480**; the app runs 465
  with FP16 encoder and decoder.

## Run 480

From upstream `Training.md` (lower is better for every figure):

| | 465 | 480 |
| --- | --- | --- |
| System level | 5.1 diffs, SER 4.0% | 5.4 diffs, SER 3.7% |
| Polish OMR-NED | 17.52% (17.70% after staff detection changes) | 16.41% (16.46%) |
| SMB OMR-NED | 13.84% (13.60%) | 12.71% (12.46%) |

Its one stated change ([PR #181](https://github.com/liebharc/homr/pull/181)): tuplets whose
number is not printed are labelled as tuplets, and staff lines with many tuplets stay in
the training data. That targets 465's recorded severe `tuplet_aligned` regression. OMR-NED
does not measure onset placement well, so these figures do not settle rhythm.

## Changes that reach inference or the exporter

| Commit / PR | Effect for this app |
| --- | --- |
| [`e5e17cc33`](https://github.com/liebharc/homr/commit/e5e17cc33) | Replaces `assert group_duration > Fraction(0)` in `build_note_chord` with a guard. That assertion failed the one unsuccessful migration item (`NORMALIZATION_FAILED`, exit 7, `music_xml_generator.py:795`). |
| [`5e072a471`](https://github.com/liebharc/homr/commit/5e072a471), issue #161 | The computed time signature is no longer emitted ahead of the recognized one. `Bridge/musicxml_normalizer.py:_extract_measure_beats` breaks a one-to-one tie by taking the shorter bar, so the computed meter could win. That only affects page stitching, where drift jumps are not concentrated: a minor lead. |
| [PR #185](https://github.com/liebharc/homr/pull/185) | Staff detection made robust (`system_repair.py`, `staff_parsing.py`, `autocrop.py`); upstream reports small gains for 465 and 480. |
| [`4807e9542`](https://github.com/liebharc/homr/commit/4807e9542), issue #190 | Staffs containing only rests no longer fail with "No noteheads found"; exit code 1 on failure. |
| [`7bddf8157`](https://github.com/liebharc/homr/commit/7bddf8157) | Duplicate images on case-insensitive file systems (Windows). |

Training-label changes only matter to a future fine-tune: grace notes take no tick in the
MusicXML converter (#182/#183), repeat signs stay paired with their images (#165/#166),
slur grouping across voices (#168).

## Open items worth tracking

- [Issue #188](https://github.com/liebharc/homr/issues/188): a staff detected in two pieces
  silently loses a measure on main. A dropped measure is a displacement mechanism; the
  displacement plan's measure-count check detects it. Reproduced only on a synthetic image.
- Issue #150 (this project's chord-split overflow) and #167 (mixed time signatures) remain open.
- The maintainer has asked for real images after being "burnt by someone with Claude Code
  generated images" (#188), and upstream added AI-disclosure guidance (#173). Any issue
  filed from this project needs real pages and must disclose AI assistance.

## Not new to this project

The 465 integration never carried PR #146's measure re-timing: the 465 runtime is unpatched
upstream source, and its evaluation compared 465 with upstream's exporter against 426 with
#146. That is a local finding rather than upstream news; the displacement plan tests it.
