# HOMR upstream audit — 2026-10-06

## Decision and scope

The main new developments since the [September 29 audit](UPSTREAM_AUDIT_2026-09-29.md)
are two merged MusicXML exporter fixes: [PR #171](https://github.com/liebharc/homr/pull/171)
for onset timing and [PR #178](https://github.com/liebharc/homr/pull/178) for malformed
chords containing structural symbols. These deserve a bounded development comparison
with Sheet2Play's existing exporter repairs. No new checkpoint was found.

This is an upstream research audit, not an implementation or promotion decision.
[MAIN_PLAN.md](../../../../plans/MAIN_PLAN.md) and its current handoff continue to own
execution. The frozen screening identities and the decision to retain shipped HOMR
are unchanged. No inference, scoring, dataset regeneration, training, model download,
release or Git command was run for this audit.

The project memory was in this diagnosis folder, linked from the startup section of
[CONTEXT.md](../../../../CONTEXT.md). A scoped Markdown search in Research, plans and
docs found no references to the new PRs/commits before this update; this does not
establish what an unrelated chat might have discussed.

Checked on **2026-10-05 at 21:00 UTC / 2026-10-06 at 00:00 Europe/Istanbul**:

- Prior audited main: `93e17ba99402fe768dc16dd59b3e1b53abc405e8`.
- Current main: `33baa326900faa12702df8c4bdcbea034a3d6a34`.
- Complete comparison: **5 new main commits**, 7 changed files.
- Retrieved 100 PRs sorted by latest update, covering every PR updated since
  September 29; the page reaches back to August 2025. Reviewed all **10 changed PRs**,
  relevant patches, **15 updated non-PR issues** and **52 issue/PR discussion comments**.
  The post-cutoff inline review-comment endpoint returned zero.
- Current open PRs: **#166, #168, #174 and #181**.
- Release inventory: 4 releases, **84 assets**. No asset creation or update since
  September 29. Both checkpoint inventories exactly match the September 29 snapshots
  by asset ID, name, size and GitHub digest: 51 ONNX assets and 27 training assets.

The GitHub HTML overview returned older data than the live REST responses, so inventory
and status decisions use the REST results. The [saved evidence](../../.runtime/upstream-audit-20261005/github-evidence.json)
contains the comparison, PR identities/patches, issue discussions and release metadata.
It is an ignored runtime snapshot; the dated findings and immutable revision links
below remain the durable project record. Asset bytes were not downloaded or rehashed.

## All main commits since the previous audit

| Date (UTC) | Commit | Change and relevance |
| --- | --- | --- |
| September 30 | [cb27ab41409a](https://github.com/liebharc/homr/commit/cb27ab41409a94af33ffe420991224f9b0ad1d18) | PR #169: GRANDSTAFF conversion writes index.txt directly; training workflow consistency |
| October 1 | [df364471ab48](https://github.com/liebharc/homr/commit/df364471ab484b25abc57b7572e2f6f7b46f14c2) | PR #171: account for still-sounding earlier notes when placing subsequent groups |
| October 1 | [863eb3c6487f](https://github.com/liebharc/homr/commit/863eb3c6487f3c6fe50267fb71613f05162bb7c5) | PR #173: AI disclosure/verification guidance for upstream contributions |
| October 4 | [560ca5ce254d](https://github.com/liebharc/homr/commit/560ca5ce254db129b1b2167598bdc7a20ac5d6b0) | Clarify position tokens as staves plus voices; README also adds a short preprocessing note |
| October 5 | [33baa326900f](https://github.com/liebharc/homr/commit/33baa326900faa12702df8c4bdcbea034a3d6a34) | PR #178: split structural symbols out of note/rest chords before MusicXML conversion |

The [pinned comparison](https://github.com/liebharc/homr/compare/93e17ba99402fe768dc16dd59b3e1b53abc405e8...33baa326900faa12702df8c4bdcbea034a3d6a34)
is the complete main-branch delta. It contains no checkpoint or inference-network update.

## PR #171: the most relevant timing lead

The old exporter advanced by the shortest note in the current group, ignoring a held
note from an earlier group that might end sooner. The patch tracks the end times of
all sounding notes and uses the next ending to place the next group. It treats grace
notes as taking no clock time. Correctly recognized notes can consequently receive
better onset positions without changing their pitches or token order.

The author reports correct-token beat placement improving from **91.6% to 96.9%**
on 85 pages; correctly recognized bars improving from **94.4% to 98.0%** on 115
real-scan pages; and musicdiff NED decreasing from **40.1% to 37.5%**. These are
upstream observations, not Sheet2Play results. The maintainer reported another
regression without problems and confirmed that the native benchmark score did not
change. That parser measures token order and misses these onset changes.
[PR and discussion](https://github.com/liebharc/homr/pull/171).

This does not reconstruct missed notes, settle every issue in #150, or establish a
local F1 improvement. The later [grace-note issue #182](https://github.com/liebharc/homr/issues/182)
also corrects the author's premise about training grouping: zero-time grace handling
is true for the kern parser but not the current MusicXML training parser.

### Local compatibility finding

Static inspection of
[the installed exporter](../../../../Bridge/.venv-homr-gpu/Lib/site-packages/homr/music_xml_generator.py)
found the local `_plan_voice_repairs` path and a fallback still advancing by
`group.get_duration()`; the upstream `_advance_to_next_group` routine is absent.
The planner only attempts repair when a measure's grouped duration differs from
the estimated meter, so the two algorithms are not interchangeable.

The wheel metadata pins `457e7c6518a10ba755db2e60883419e56c4d7369`; the
[bridge](../../../../Bridge/bridge.py) labels it
`homr-0.7.0.post38+457e7c6+pr146`. The inspected exporter SHA-256 is
`c01415ed218a29326e207b9c21c9ff46fa6b2403c02e90f0b8e73399ac7afd83`.
Metadata alone does not identify every subsequent local edit or prove which runtime
a separately launched app uses.

A future comparison should hold decoded tokens fixed, reconcile the local planner,
compare exact pitch/onset/duration events and voice/tie behavior, and include
independent hands, grace notes, tuplets, missing notes and meter changes. Changing
model weights at the same time would obscure the exporter effect.

## PR #178: MusicXML robustness, with limits

This merged fix separates clefs, keys and time signatures before notes, and barlines
and repeats after them. Previously these mixed chords could cause a zero-duration
assertion or silently discard notes. Tests cover ordering, repeated barlines,
rests and tuplet boundaries. The author reports four affected pages repaired among
433 pages, with the other 429 byte-identical; another contributor reports one fewer
Polish benchmark failure. None of those checks was rerun locally.
[PR #178](https://github.com/liebharc/homr/pull/178).

The maintainer explicitly distinguishes robust export from repairing the transformer's
recognition error. The installed local exporter has no `split_mixed_chords` step
and retains the zero-duration assertion, so the affected code pattern is present;
a local token reproduction is still needed before claiming the patch fixes our failures.

[Issue #179](https://github.com/liebharc/homr/issues/179) remains open for a malformed
grace-note token with no valid pitch/position. That is distinct from the structural
symbols handled by #178; this audit does not certify it as fixed.

## Training work and all other changed PRs

| Item | Current status / change since September 29 | Project disposition |
| --- | --- | --- |
| [#181: hidden tuplets](https://github.com/liebharc/homr/pull/181) | New, open. MusicXML training parser counts tuplets even when their number is hidden; tests distinguish tuplets from tremolo | Training-label candidate, not an existing-model inference fix |
| [#174: dynamics](https://github.com/liebharc/homr/pull/174) | New, open, still under discussion. Changes vocabulary, training parser and XML export | Requires compatible training/checkpoints and later application integration |
| [#166: repeat ownership](https://github.com/liebharc/homr/pull/166) | Previously known, still open; head updated to aa6ada566aca11c7828de87436e13912d58616b7 | Updated crop-boundary normalization, opening attributes and empty-measure handling; future dataset quality work |
| [#168: slur grouping](https://github.com/liebharc/homr/pull/168) | Still open at the previously audited head 74062f7f3bca3b97ef69d3848a60e170c32e910f; discussion now recommends training/evaluation | No newly published checkpoint incorporating it was found; cross-voice slurs are not prohibited by the patch |
| [#169: GRANDSTAFF index](https://github.com/liebharc/homr/pull/169) | Previously open; merged September 30 | Converter workflow change, not a model accuracy gain |
| [#173: contribution policy](https://github.com/liebharc/homr/pull/173) | New; merged October 1 | Explain AI use and what was verified when contributing upstream; this is not a new Sheet2Play agent instruction |
| [#144: CUDA library preload](https://github.com/liebharc/homr/pull/144) | Old PR closed October 2 without merge; maintainer says preloading already exists | No newly missing CUDA patch established; do not reopen GPU diagnosis based on this closure |
| [#137: notehead coordinates](https://github.com/liebharc/homr/pull/137) | Old PR closed October 2 without merge | Not evidence that this proposed JSON interface shipped; previously recorded image-position comments remain separate |

Together with #171 and #178, this accounts for all ten PRs updated within the scan window.

[Issue #182](https://github.com/liebharc/homr/issues/182) is a new, unfixed training-parser
lead: grace notes without durations are given a one-tick advance, changing grouping
across staves. The maintainer welcomed a PR; no implementation was identified. The
reporter's corpus counts are not local verification. Merely changing the duration
to zero could incorrectly merge successive grace notes into a chord.

For hidden tuplets, the maintainer explains in
[issue #180](https://github.com/liebharc/homr/issues/180) that the old exclusion was
intentional because training on invisible tuplets caused hallucinated tuplets.
Any future #181 evaluation must therefore measure both recovered tuplets and new
false positives. Contributors discussed combining this with dynamics and
[distinct strong/soft accents (#176)](https://github.com/liebharc/homr/issues/176)
in a future training run; a request to schedule training is not evidence of a run
or a released checkpoint. The accent change also needs vocabulary, parser and
exporter work.

For #166, the author reports stable image/index inventories and corrected repeat
answers on saved development scores, with excluded sources still excluded. These
are converter evidence, not measured recognition improvements. All these training
leads should precede any separately requested regeneration/training assessment,
including checks of Sheet2Play's own generator and matching vocabulary/weight identities.

## Clarifications and lower-priority issue updates

- **upper2/lower2 are second voices on their respective staves.** They are not a
  second piano or staves 3/4. The new
  [pinned vocabulary documentation](https://github.com/liebharc/homr/blob/560ca5ce254db129b1b2167598bdc7a20ac5d6b0/Vocabulary.md#positions-and-voices)
  makes this explicit. [Issue #172](https://github.com/liebharc/homr/issues/172)
  was closed because its proposed remapping relied on a wrong interpretation.
  The shown historical scan did have staff/brace detection problems; that does
  not validate the proposed token remapping.
- [#170](https://github.com/liebharc/homr/issues/170) was closed after the reporter
  narrowed a claimed general natural-sign failure to short/sparse lines. Full-width
  examples performed much better in the reported tests. This supports checking
  crop context as a development variable, not declaring naturals universally broken.
- [#167](https://github.com/liebharc/homr/issues/167) remains open. The reporter
  clarified the exporter-only 4/4 plus 2/4 becoming 3/4 median defect; a planned PR
  is not a merged fix. Numerator recognition is a separate, broader limitation.
- [#142](https://github.com/liebharc/homr/issues/142) was closed with a reference to
  #171; [#150](https://github.com/liebharc/homr/issues/150) remains open and retains
  recognition/engraving concerns.
- [#175](https://github.com/liebharc/homr/issues/175) remains open on clef/barline
  ordering in training examples; discussion also references #178.
  [#177](https://github.com/liebharc/homr/issues/177) notes that the README example
  lags current slur/tie output; it is not new benchmark evidence.
- #165 remains open and tied to #166. Old #108, #133 and #139 were closed through
  follow-up discussion or already known changes, without a new main-code fix.

## Recommended next decision

If the user later requests HOMR improvement work, first propose a small comparison
of #171 and #178 against the current local repairs using development tokens and
explicit event/failure evidence. Keep model 465 and the training proposals separate.
The current checkpoint inventory adds no reason to replace the shipped model,
repeat frozen screens or advance the active plan automatically.

Validation for this documentation update: checked the live API pagination boundaries,
the complete five-commit comparison, checkpoint metadata equality, static local
exporter differences, saved JSON parsing and changed local documentation links.
Runtime compatibility, upstream benchmark replication and local accuracy gains
remain unverified.
