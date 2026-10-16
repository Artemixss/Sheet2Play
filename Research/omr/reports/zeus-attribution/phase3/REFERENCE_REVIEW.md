# Pre-inference development reference review

Scope: fixed12 generated controls and page1 of6211535,6211549,6211555.
Frozen source/reference hashes are checked by preparation; hashes alone do not establish
engraving alignment. These observations precede any Phase3 model output.

| Input | Engraved content checked against reference | Qualification |
|---|---|---|
| baseline-piano-001 | Eight measures; two two-staff systems, first five and last three measures; repeated half-note and quarter-chord layers | Kern import lacks layout markers; explicit diagnostic system boundaries0,5. Engraving puts bass above treble; staff order is not a hand label. |
| homophonic | Four quarter notes in each of two voices; upper E5,F5,G5,A5; lower C4,D4,E4,F4 | Single treble staff with independent stems. |
| offset_entry | Upper dotted quarter, eighth, half; lower four quarters | Upper entry at1.5 beats is visible; no onset tolerance. |
| quintuplet_vs_duple | Five quarter-shaped notes under5 bracket against four quarters | Durations4/5 and1 quarter beats from10080 divisions. |
| septuplet_vs_duple | Seven quarter-shaped notes under7 bracket against four quarters | Durations4/7 and1; single staff. |
| triplet_vs_duple | Three quarter-shaped notes under3 bracket against two quarters in2/4 | Durations2/3 and1. |
| triplet_vs_quadruple | Same upper triplet against four eighths in2/4 | Durations2/3 and1/2. |
| tuplet_aligned | Four groups of three beamed eighth triplets in both voices |24 segments at1/3 beat; one measure, one staff. |
| three_voices | Whole C5, halves E4/F4, quarters G3/A3/B3/C4 | Three voices on one treble staff; ledger notes are intentional. |
| same_position_sustain | Two half notes with overlapping short notes and low ledger lines | Generator uses A-2/B-2/A-3/E-4 for flats, not negative octaves; atypical register/domain. |
| tie_across_barline | C5 half, tied G5 halves across barline, E5 half | Four written segments, three sounding events; no system break. |
| syncopation | Four upper notes (three quarters then eighth) against four lower quarters | XML has leading eighth rest; rest is not clearly visible in image. Do not attribute an unobservable onset mismatch solely to recognition. |
| openscore6211535 | Five piano systems starting measures1,7,11,16,19; first page ends19 | Hidden vocal part has full-measure rest duration4 in3/2 meter. No vocal pitched notes expected on page1; trace part-specific origins and qualify hidden-rest timing. |
| openscore6211549 | Four systems starting1,4,7,10; page ends11; visible voice enters fourth system | Earlier vocal staves hidden; final system has voice plus two piano staves, lyrics and tuplets. Detector coverage must be inspected. |
| openscore6211555 | Two systems starting1,4; page ends7; visible voice plus piano throughout | Piano rests in measure3 and4; preserve that silence rather than starting local scoring at its first note. |

Generated controls are full pages with title/margins. Corrected HOMR crops must be inspected
before inference; passing full pages directly to a192-pixel-height system recognizer would
confound input scale with recognition. Both recipes use exactly the same saved crop bytes.
Reference files and the unchanged Bridge normalizer are retained. Global primary scoring
is not shifted, repaired, aligned or warped; system/measure-local scores are diagnostic only.
Staff indices from normalized events reset per part. Distinct XML part/staff counts are
reported alongside historical-index coverage; no automatic hand interpretation.
