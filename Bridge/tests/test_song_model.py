from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

BRIDGE_DIRECTORY = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIRECTORY))

import song_entry  # noqa: E402
import song_model  # noqa: E402
import timing_correction  # noqa: E402
from musicxml_normalizer import combine_score_pages, normalize_musicxml  # noqa: E402

def pitch(midi: int) -> str:
    names = {0: ("C", 0), 2: ("D", 0), 4: ("E", 0), 5: ("F", 0), 7: ("G", 0), 9: ("A", 0), 11: ("B", 0),
             1: ("C", 1), 3: ("D", 1), 6: ("F", 1), 8: ("G", 1), 10: ("A", 1)}
    step, alter = names[midi % 12]
    alter_xml = f"<alter>{alter}</alter>" if alter else ""
    return f"<pitch><step>{step}</step>{alter_xml}<octave>{midi // 12 - 1}</octave></pitch>"


def note(midi: int, duration: int = 2, *, voice: int = 1, staff: int | None = None, extra: str = "",
         notations: str = "", chord: bool = False) -> str:
    staff_xml = f"<staff>{staff}</staff>" if staff else ""
    notations_xml = f"<notations>{notations}</notations>" if notations else ""
    return (f"<note>{'<chord/>' if chord else ''}{pitch(midi)}<duration>{duration}</duration>{extra}"
            f"<voice>{voice}</voice>{staff_xml}{notations_xml}</note>")


def measure(number: int, body: str, *, left: str = "", right: str = "", first: bool = False,
            beats: int = 2) -> str:
    attributes = (f"<attributes><divisions>1</divisions><time><beats>{beats}</beats><beat-type>4</beat-type>"
                  "</time><clef><sign>G</sign><line>2</line></clef></attributes>") if first else ""
    left_xml = f'<barline location="left">{left}</barline>' if left else ""
    right_xml = f'<barline location="right">{right}</barline>' if right else ""
    return f'<measure number="{number}">{left_xml}{attributes}{body}{right_xml}</measure>'


def score(*measures: str, parts: int = 1) -> str:
    part_list = "".join(f'<score-part id="P{index + 1}"><part-name>Part {index + 1}</part-name></score-part>'
                        for index in range(parts))
    body = "".join(f'<part id="P{index + 1}">{"".join(measures)}</part>' for index in range(parts))
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0">'
            f"<part-list>{part_list}</part-list>{body}</score-partwise>")


def melody(*midis: int, first_number: int = 1, marks: dict[int, dict[str, str]] | None = None) -> list[str]:
    """One half note per 2/4 measure; `marks` adds left/right barline content by measure index."""
    marks = marks or {}
    return [measure(first_number + index, note(midi), first=index == 0, **marks.get(index, {}))
            for index, midi in enumerate(midis)]


FORWARD = '<repeat direction="forward"/>'
BACKWARD = '<repeat direction="backward"/>'

# 2/4. Measure 2's <backup> is one beat short, the fault the timing fix repairs (as in
# test_timing_correction): the second voice's half note starts on beat 2 and the bar overflows.
LOST_BACKUP_PAGE = score(
    measure(1, note(60), first=True),
    measure(2, note(64, 1) + note(65, 1) + "<backup><duration>1</duration></backup>" + note(55, 2, voice=2)),
    measure(3, note(62)),
)
# A second page whose last measure reads a beat short, so page stitching rounds it.
SHORT_LAST_PAGE = score(
    measure(1, note(67), first=True),
    measure(2, note(69, 1)),
)


class SongModelCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.directory / name
        path.write_text(text, encoding="utf-8")
        return path

    @staticmethod
    def keys(notes) -> Counter:
        return Counter((round(start * 1e6), midi, round(duration * 1e6)) for start, midi, duration in notes)


class ParityTests(SongModelCase):
    def bridge_notes(self, pages: list[Path], timing: bool) -> Counter:
        normalized = []
        for number, path in enumerate(pages):
            page = normalize_musicxml(path)
            normalized.append(timing_correction.correct_page(path, page, number == 0) if timing else page)
        return self.keys((item.start_beat, item.midi_pitch, item.duration_beats)
                         for item in combine_score_pages(normalized).notes)

    def test_notes_land_where_the_bridge_puts_them_with_and_without_the_timing_fix(self) -> None:
        pages = [self.write("page-0001.musicxml", LOST_BACKUP_PAGE), self.write("page-0002.musicxml", SHORT_LAST_PAGE)]
        for timing in (False, True):
            with self.subTest(timing=timing):
                performance = song_model.interpret(pages, timing_correction_enabled=timing)
                self.assertEqual(self.keys(song_model.sequential_notes(performance)), self.bridge_notes(pages, timing))
                self.assertEqual(self.keys(song_model.played_notes(performance)), self.bridge_notes(pages, timing))
        corrected = song_model.interpret(pages, timing_correction_enabled=True)
        self.assertEqual([page["timing"] for page in corrected["pages"]], ["corrected", "corrected"])
        # The fix shortens the faulty measure to its 2/4 bar, so the next one starts on beat 4.
        self.assertEqual([measure["start_beat"] for measure in corrected["measures"]][:3], [0.0, 2.0, 4.0])

    def test_staves_match_the_timing_fixs_own_reading(self) -> None:
        path = self.write("page.musicxml", LOST_BACKUP_PAGE)
        self.assertEqual(song_model.read_page(path).staves, timing_correction.load_page(path))

    def test_page_stitching_rounds_like_the_bridge(self) -> None:
        pages = [self.write("a.musicxml", LOST_BACKUP_PAGE), self.write("b.musicxml", SHORT_LAST_PAGE)]
        performance = song_model.interpret(pages)
        second = performance["pages"][1]
        self.assertEqual(second["start_beat"], 7.0)  # page 1 decodes to 7 beats and is exempt from rounding
        self.assertEqual(second["decoded_beats"], 3.0)
        self.assertEqual(second["advance_beats"], 4.0)
        last = performance["measures"][-1]
        self.assertEqual(last["start_beat"] + last["length_beats"], 11.0)

    def test_grace_notes_are_kept_and_flagged_where_the_bridge_drops_them(self) -> None:
        grace = f"<note><grace slash=\"yes\"/>{pitch(74)}<voice>1</voice><type>eighth</type></note>"
        path = self.write("grace.musicxml", score(measure(1, grace + note(72), first=True)))
        performance = song_model.interpret([path], kind=song_model.MUSICXML)
        flagged = [item for item in performance["notes"] if item["grace"]]
        self.assertEqual([(item["midi"], item["duration"], item["grace_slash"]) for item in flagged], [(74, 0.0, True)])
        self.assertEqual(len(normalize_musicxml(path).notes), 1)
        self.assertEqual(self.keys(song_model.sequential_notes(performance)),
                         self.keys((n.start_beat, n.midi_pitch, n.duration_beats) for n in normalize_musicxml(path).notes))


class PlayOrderTests(SongModelCase):
    def order(self, measures: list[str]) -> tuple[list[int], list[str]]:
        performance = song_model.interpret([self.write("score.musicxml", score(*measures))], kind=song_model.MUSICXML)
        return performance["play_order"], performance["warnings"]

    def test_repeat_with_two_voltas(self) -> None:
        marks = {1: {"left": FORWARD},
                 2: {"left": '<ending number="1" type="start"/>', "right": '<ending number="1" type="stop"/>' + BACKWARD},
                 3: {"left": '<ending number="2" type="start"/>', "right": '<ending number="2" type="discontinue"/>'}}
        order, warnings = self.order(melody(60, 62, 64, 65, 67, marks=marks))
        self.assertEqual(order, [0, 1, 2, 1, 3, 4])
        self.assertEqual(warnings, [])

    def test_closing_repeat_without_opening_returns_to_the_section_start(self) -> None:
        marks = {1: {"right": BACKWARD}, 3: {"right": BACKWARD}}
        order, _ = self.order(melody(60, 62, 64, 65, 67, marks=marks))
        self.assertEqual(order, [0, 1, 0, 1, 2, 3, 2, 3, 4])

    def test_times_counts_the_plays(self) -> None:
        marks = {0: {"left": FORWARD}, 0 + 1: {"right": '<repeat direction="backward" times="3"/>'}}
        order, _ = self.order(melody(60, 62, 64, marks=marks))
        self.assertEqual(order, [0, 1, 0, 1, 0, 1, 2])

    def test_da_capo_al_fine_skips_repeats_after_the_jump(self) -> None:
        measures = melody(60, 62, 64, 65, marks={1: {"right": BACKWARD}})
        measures[2] = measures[2].replace("</measure>", '<sound fine="yes"/></measure>')
        measures[3] = measures[3].replace("</measure>", '<sound dacapo="yes"/></measure>')
        order, _ = self.order(measures)
        self.assertEqual(order, [0, 1, 0, 1, 2, 3, 0, 1, 2])

    def test_dal_segno_al_coda(self) -> None:
        measures = melody(60, 62, 64, 65, 67)
        measures[1] = measures[1].replace("</measure>", '<sound segno="s1"/></measure>')
        measures[2] = measures[2].replace("</measure>", '<sound tocoda="c1"/></measure>')
        measures[3] = measures[3].replace("</measure>", '<sound dalsegno="s1"/></measure>')
        measures[4] = measures[4].replace("</measure>", '<sound coda="c1"/></measure>')
        order, _ = self.order(measures)
        self.assertEqual(order, [0, 1, 2, 3, 1, 2, 4])

    def test_a_repeat_across_pages_plays_twice(self) -> None:
        first = self.write("page-0001.musicxml", score(*melody(60, 62, marks={0: {"left": FORWARD}})))
        second = self.write("page-0002.musicxml", score(*melody(64, 65, first_number=3, marks={0: {"right": BACKWARD}})))
        performance = song_model.interpret([first, second])
        self.assertEqual(performance["play_order"], [0, 1, 2, 0, 1, 2, 3])
        played = [midi for _, midi, _ in sorted(song_model.played_notes(performance))]
        self.assertEqual(played, [60, 62, 64, 60, 62, 64, 65])
        # The bridge expands each page on its own: page 2's closing repeat finds no opening on
        # its page and repeats only that page's part of the section.
        bridge = combine_score_pages([normalize_musicxml(first), normalize_musicxml(second)])
        self.assertEqual([item.midi_pitch for item in bridge.notes], [60, 62, 64, 64, 65])
        starts = [start for start, _, _ in sorted(song_model.played_notes(performance))]
        self.assertEqual(starts, [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0])


class MarkTests(SongModelCase):
    def test_pedals_dynamics_wedges_and_tempo_are_placed_in_their_measure(self) -> None:
        directions = (
            '<direction><direction-type><metronome><beat-unit>quarter</beat-unit><beat-unit-dot/>'
            '<per-minute>60</per-minute></metronome></direction-type><sound tempo="90"/></direction>'
            '<direction><direction-type><dynamics><p/></dynamics></direction-type><sound dynamics="54.44"/></direction>'
            '<direction><direction-type><pedal type="start" line="yes"/></direction-type><staff>1</staff></direction>'
        )
        body = (directions + note(60, 1) +
                '<direction><direction-type><wedge type="crescendo" number="1"/></direction-type></direction>'
                + note(62, 1) + "<backup><duration>1</duration></backup>"
                '<direction><direction-type><pedal type="change"/></direction-type></direction>'
                "<forward><duration>1</duration></forward>")
        second = ('<direction><direction-type><wedge type="stop" number="1"/></direction-type></direction>'
                  '<direction><offset sound="yes">1</offset><direction-type><pedal type="stop"/></direction-type>'
                  '</direction>' + note(64))
        path = self.write("marks.musicxml", score(measure(1, body, first=True), measure(2, second)))
        performance = song_model.interpret([path], kind=song_model.MUSICXML)
        self.assertEqual([(p["measure"], p["offset"], p["type"]) for p in performance["pedals"]],
                         [(0, 0.0, "start"), (0, 1.0, "change"), (1, 1.0, "stop")])
        self.assertEqual([(d["mark"], d["sound_dynamics"]) for d in performance["dynamics"]], [("p", 54.44)])
        self.assertEqual(performance["wedges"], [{"kind": "crescendo", "part": 0, "staff": 0, "start_measure": 0,
                                                  "start_offset": 1.0, "end_measure": 1, "end_offset": 0.0}])
        self.assertEqual([(t["quarter_bpm"], t["beat_unit"], t["dots"], t["source"]) for t in performance["tempos"]],
                         [(90.0, "quarter", 1, "metronome+sound")])

    def test_metronome_alone_converts_to_quarter_notes(self) -> None:
        direction = ('<direction><direction-type><metronome><beat-unit>half</beat-unit><per-minute>c. 50</per-minute>'
                     '</metronome></direction-type></direction>')
        path = self.write("tempo.musicxml", score(measure(1, direction + note(60), first=True)))
        tempos = song_model.interpret([path], kind=song_model.MUSICXML)["tempos"]
        self.assertEqual([(t["quarter_bpm"], t["source"]) for t in tempos], [(100.0, "metronome")])

    def test_no_tempo_mark_means_no_tempo(self) -> None:
        path = self.write("plain.musicxml", score(*melody(60, 62)))
        self.assertEqual(song_model.interpret([path], kind=song_model.MUSICXML)["tempos"], [])

    def test_articulations_join_chords_and_ties(self) -> None:
        staccato = "<articulations><staccato/></articulations>"
        tied_start = note(67, 2, extra='<tie type="start"/>', notations='<tied type="start"/><articulations><accent/></articulations>')
        tied_stop = note(67, 2, extra='<tie type="stop"/>', notations='<tied type="stop"/><fermata/>')
        path = self.write("marks.musicxml", score(
            measure(1, note(60, 2, notations=staccato) + note(64, 2, notations=staccato, chord=True), first=True),
            measure(2, tied_start), measure(3, tied_stop)))
        performance = song_model.interpret([path], kind=song_model.MUSICXML)
        by_pitch = {item["midi"]: item for item in performance["notes"]}
        self.assertEqual(by_pitch[60]["articulations"], ["staccato"])
        self.assertEqual(by_pitch[64]["articulations"], ["staccato"])
        self.assertEqual(by_pitch[67]["articulations"], ["accent", "fermata"])
        self.assertTrue(by_pitch[67]["tied"])
        self.assertEqual(by_pitch[67]["duration"], 4.0)
        self.assertEqual(performance["features"]["unjoined_marked_notes"], 0)

    def test_an_unreadable_duration_degrades_instead_of_failing(self) -> None:
        body = (note(60, 1) + "<backup><duration>one</duration></backup>"
                '<direction><direction-type><pedal type="start"/></direction-type></direction>' + note(62, 1))
        path = self.write("bad.musicxml", score(measure(1, body, first=True)))
        pedals = song_model.read_xml_page(path.read_bytes()).marks
        self.assertEqual([(mark.kind, mark.onset) for mark in pedals], [("pedal", 1)])

    def test_feature_counts_match_an_independent_count(self) -> None:
        body = ('<direction><direction-type><pedal type="start"/></direction-type><sound damper-pedal="yes"/></direction>'
                '<direction><direction-type><dynamics><f/></dynamics></direction-type></direction>'
                + note(60, 2, notations="<articulations><tenuto/></articulations><fermata/>"))
        rest_with_fermata = "<note><rest/><duration>2</duration><voice>1</voice><notations><fermata/></notations></note>"
        document = score(measure(1, body, first=True), measure(2, rest_with_fermata,
                                                               right='<bar-style>light-heavy</bar-style><fermata/>'))
        path = self.write("counts.musicxml", document)
        features = song_model.interpret([path], kind=song_model.MUSICXML)["features"]
        for key, value in song_model.independent_counts(document.encode()).items():
            self.assertEqual(features[key], value, key)
        self.assertEqual(features["articulation_marks"], 3)


class DocumentTests(SongModelCase):
    def test_mxl_archives_are_read_through_their_container(self) -> None:
        archive = self.directory / "song.mxl"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="music/score.xml"/>'
                                                      "</rootfiles></container>")
            bundle.writestr("music/score.xml", score(*melody(60, 62)))
        performance = song_model.interpret([archive], kind=song_model.MUSICXML)
        self.assertEqual([item["midi"] for item in performance["notes"]], [60, 62])
        self.assertEqual(song_model.combined_musicxml([archive], song_model.MUSICXML), score(*melody(60, 62)).encode())

    def test_interpretation_is_deterministic(self) -> None:
        pages = [self.write("page-0001.musicxml", LOST_BACKUP_PAGE), self.write("page-0002.musicxml", SHORT_LAST_PAGE)]
        first = song_model.write_song(pages, self.directory / "one", timing_correction_enabled=True)
        song_model.write_song(pages, self.directory / "two", timing_correction_enabled=True)
        for name in ("performance.json", "score.musicxml"):
            self.assertEqual((self.directory / "one" / name).read_bytes(), (self.directory / "two" / name).read_bytes())
        self.assertEqual(json.loads((self.directory / "one" / "performance.json").read_text(encoding="utf-8")), first)
        self.assertEqual(first["sources"][0]["sha256"], hashlib.sha256(pages[0].read_bytes()).hexdigest())

    def test_combined_score_numbers_measures_through_and_keeps_a_missing_part_empty(self) -> None:
        from music21 import converter

        first = self.write("page-0001.musicxml", score(*melody(60, 62), parts=2))
        second = self.write("page-0002.musicxml", score(*melody(64, 65, 67)))
        combined = song_model.combined_musicxml([first, second])
        parsed = converter.parse(combined.decode("utf-8"), format="musicxml")
        self.assertEqual(len(parsed.parts), 2)
        for part in parsed.parts:
            self.assertEqual([measure.number for measure in part.getElementsByClass("Measure")], [1, 2, 3, 4, 5])
        self.assertIn(b'new-page="yes"', combined)
        self.assertEqual(len(parsed.parts[1].recurse().notes), 2)
        filled = combined.decode("utf-8").split('<part id="P2">')[1]
        self.assertEqual(filled.count("<note>"), 2)  # page 2 has no second part: its measures stay empty

    def test_a_part_missing_from_the_first_page_opens_with_its_attributes(self) -> None:
        from music21 import converter

        first = self.write("page-0001.musicxml", score(*melody(60, 62)))
        second = self.write("page-0002.musicxml", score(*melody(64, 65), parts=2))
        combined = song_model.combined_musicxml([first, second])
        second_part = combined.decode("utf-8").split('<part id="P2">')[1]
        self.assertTrue(second_part.startswith('<measure number="1"><attributes><divisions>1</divisions>'))
        parsed = converter.parse(combined.decode("utf-8"), format="musicxml")
        self.assertEqual([len(part.getElementsByClass("Measure")) for part in parsed.parts], [4, 4])

    def test_interpretation_key_follows_the_timing_fix(self) -> None:
        self.assertNotEqual(song_model.interpretation_key(False), song_model.interpretation_key(True))
        self.assertEqual(song_model.interpretation_key(True), song_model.interpretation_key(True))


class FakeBridge:
    """The parts of `bridge` that song_entry uses: a normalize hook, argument parsing and main."""

    def __init__(self, pages: list[Path], status: int = 0, normalize=normalize_musicxml) -> None:
        self.pages = pages
        self.status = status
        self.normalize_musicxml = normalize

    @staticmethod
    def parse_arguments(arguments):
        return SimpleNamespace(input_path=Path(arguments[-1]))

    def main(self, arguments) -> int:
        for path in self.pages:
            self.normalize_musicxml(path)
        print(json.dumps({"schema_version": 2}))
        return self.status


class SongEntryTests(SongModelCase):
    def run_entry(self, bridge: FakeBridge, *extra: str) -> tuple[int, str]:
        source = self.write("song.pdf", "%PDF-1.4 stand-in")
        errors = io.StringIO()
        original = sys.stderr
        sys.stderr = errors
        try:
            status = song_entry.run(["--song-output", str(self.directory / "package"), *extra,
                                     "--engine", "homr480", str(source)], bridge)
        finally:
            sys.stderr = original
        return status, errors.getvalue()

    def test_a_successful_run_keeps_the_pages_and_interprets_them(self) -> None:
        pages = [self.write("p1.musicxml", LOST_BACKUP_PAGE), self.write("p2.musicxml", SHORT_LAST_PAGE)]
        status, errors = self.run_entry(FakeBridge(pages), "--timing-correction")
        self.assertEqual(status, 0)
        package = self.directory / "package"
        self.assertEqual((package / "pages" / "page-0001.musicxml").read_bytes(), pages[0].read_bytes())
        self.assertEqual((package / "pages" / "page-0002.musicxml").read_bytes(), pages[1].read_bytes())
        recognition = json.loads((package / "recognition.json").read_text(encoding="utf-8"))
        self.assertEqual((recognition["engine"], recognition["kind"]), ("homr480", "omr-pages"))
        self.assertEqual([item["name"] for item in recognition["files"]], ["pages/page-0001.musicxml", "pages/page-0002.musicxml"])
        derived = package / "derived" / song_model.interpretation_key(True)
        performance = json.loads((derived / "performance.json").read_text(encoding="utf-8"))
        self.assertTrue(performance["timing_correction"])
        self.assertTrue((derived / "score.musicxml").is_file())
        self.assertIn(song_entry.SONG_PREFIX, errors)
        self.assertEqual([path.name for path in self.directory.iterdir() if path.name.startswith(".package")], [])

    def test_a_failed_conversion_leaves_no_package(self) -> None:
        status, errors = self.run_entry(FakeBridge([self.write("p1.musicxml", LOST_BACKUP_PAGE)], status=3))
        self.assertEqual(status, 3)
        self.assertFalse((self.directory / "package").exists())
        self.assertNotIn(song_entry.SONG_PREFIX, errors)
        self.assertEqual([path.name for path in self.directory.iterdir() if path.name.startswith(".package")], [])

    def test_an_interpretation_failure_keeps_the_pages_and_the_status(self) -> None:
        # The stand-in bridge reads the page without complaint; the interpreter cannot.
        broken = self.write("p1.musicxml", "<score-timewise/>")
        status, errors = self.run_entry(FakeBridge([broken], normalize=lambda path: None))
        self.assertEqual(status, 0)
        self.assertTrue((self.directory / "package" / "pages" / "page-0001.musicxml").is_file())
        self.assertFalse((self.directory / "package" / "derived").exists())
        self.assertIn("interpretation_error", errors)


class PinTests(unittest.TestCase):
    def test_pinned_bridge_files_are_unchanged(self) -> None:
        for name in ("homr465-profile.json", "homr480-profile.json"):
            profile = json.loads((BRIDGE_DIRECTORY / name).read_text(encoding="utf-8"))
            for row in profile["bridge_files"]:
                with self.subTest(profile=name, file=row["path"]):
                    digest = hashlib.sha256((BRIDGE_DIRECTORY / row["path"]).read_bytes()).hexdigest()
                    self.assertEqual(digest, row["sha256"])
            self.assertNotIn("song_model.py", [row["path"] for row in profile["bridge_files"]])
            self.assertNotIn("song_entry.py", [row["path"] for row in profile["bridge_files"]])


if __name__ == "__main__":
    unittest.main()
