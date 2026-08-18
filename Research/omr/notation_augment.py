"""Inject notation-layer annotations into MusicXML before engraving.

The image degradation in build_dataset.py models the *imaging* layer - skew, blur,
noise, JPEG. Real target scores differ from a bare render in the *notation* layer
instead: they carry title blocks, arranger credits, note-name letters, fingerings,
chord symbols and performance text. A model trained only on bare renders has never
had to ignore any of that.

These helpers rewrite a canonical MusicXML export before it is engraved, so the
rendered page gains those distractors while the training label stays the clean,
unannotated score. The model therefore learns to transcribe notes and ignore the
surrounding clutter.

Element ordering follows the MusicXML DTD where it matters: <work> precedes
<identification>, <harmony> precedes the note it applies to, and within <note> the
<notations> element precedes <lyric>.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

DOCTYPE = ('<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
           '"http://www.musicxml.org/dtds/partwise.dtd">')

TITLE_WORDS = [
    "Main Theme", "Battle Theme", "Opening", "Ending Theme", "Boss Theme",
    "Character Theme", "Piano Arrangement", "OST", "Prelude", "Reprise",
]
TITLE_SOURCES = [
    "Genshin Impact", "Dark Souls", "Chainsaw Man", "Tokyo Ghoul", "Oppenheimer",
    "Honkai: Star Rail", "Attack on Titan", "Your Name", "Elden Ring",
]
COMPOSERS = [
    "Yu-peng Chen", "Kensuke Ushio", "Motoi Sakuraba", "Hiroyuki Sawano",
    "Ludwig Goransson", "Yuki Kajiura", "Joe Hisaishi",
]
ARRANGERS = [
    "Arr. by Animenz", "Arr. by Prower's Sheets", "Arr. by The Rhythmic Pianist",
    "Arr. Alice Lefebvre", "Piano arrangement by Sheet2Play",
]
PERFORMANCE_WORDS = [
    "rit.", "accel.", "dolce", "espressivo", "cantabile", "poco a poco",
    "molto rall.", "a tempo", "sim.", "cresc.", "dim.", "8va",
]
CHORD_ROOTS = ["C", "D", "E", "F", "G", "A", "B"]
CHORD_KINDS = ["major", "minor", "dominant", "suspended-fourth", "minor-seventh"]
FOOTERS = [
    "Downloaded from a public score library",
    "For personal practice use only",
    "Transcribed by ear",
    "Page {page}",
]


def _note_name(note):
    """Letter name for a pitched note, e.g. C, F#, Bb. None for rests."""
    pitch = note.find("pitch")
    if pitch is None:
        return None
    step = pitch.findtext("step")
    if not step:
        return None
    alter = pitch.findtext("alter")
    if alter in ("1", "1.0"):
        return step + "#"
    if alter in ("-1", "-1.0"):
        return step + "b"
    return step


def set_title_block(root, rng):
    """Give the score a title, composer and arranger, which MuseScore renders as a
    header. Almost every real export has one; a bare render has none."""
    title = rng.choice(TITLE_SOURCES) + " - " + rng.choice(TITLE_WORDS)

    for existing in root.findall("work"):
        root.remove(existing)
    work = ET.Element("work")
    ET.SubElement(work, "work-title").text = title
    root.insert(0, work)  # <work> must precede <identification>

    identification = root.find("identification")
    if identification is None:
        identification = ET.Element("identification")
        root.insert(1, identification)
    for creator in identification.findall("creator"):
        identification.remove(creator)
    composer = ET.Element("creator", {"type": "composer"})
    composer.text = rng.choice(COMPOSERS)
    arranger = ET.Element("creator", {"type": "arranger"})
    arranger.text = rng.choice(ARRANGERS)
    identification.insert(0, composer)
    identification.insert(1, arranger)
    return title


def add_note_names(root, rng, coverage=0.85):
    """Attach the letter name under notes, the style used by beginner-friendly
    arrangements. Applied as <lyric> because MusicXML has no notehead-interior text."""
    added = 0
    for note in root.iter("note"):
        if note.find("rest") is not None or note.find("chord") is not None:
            continue
        name = _note_name(note)
        if name is None or rng.random() > coverage:
            continue
        lyric = ET.SubElement(note, "lyric", {"number": "1"})
        ET.SubElement(lyric, "syllabic").text = "single"
        ET.SubElement(lyric, "text").text = name
        added += 1
    return added


def add_fingerings(root, rng, coverage=0.35):
    added = 0
    for note in root.iter("note"):
        if note.find("rest") is not None or rng.random() > coverage:
            continue
        notations = note.find("notations")
        if notations is None:
            notations = ET.Element("notations")
            lyric = note.find("lyric")
            if lyric is None:
                note.append(notations)
            else:
                note.insert(list(note).index(lyric), notations)  # notations before lyric
        technical = notations.find("technical")
        if technical is None:
            technical = ET.SubElement(notations, "technical")
        ET.SubElement(technical, "fingering").text = str(rng.randint(1, 5))
        added += 1
    return added


def add_chord_symbols(root, rng, probability=0.4):
    """Chord symbols sit above the staff and are pure distraction for a note-level
    transcription target."""
    added = 0
    for measure in root.iter("measure"):
        if rng.random() > probability:
            continue
        children = list(measure)
        first_note = next((index for index, child in enumerate(children)
                           if child.tag == "note"), None)
        if first_note is None:
            continue
        harmony = ET.Element("harmony")
        root_element = ET.SubElement(harmony, "root")
        ET.SubElement(root_element, "root-step").text = rng.choice(CHORD_ROOTS)
        if rng.random() < 0.3:
            ET.SubElement(root_element, "root-alter").text = rng.choice(["-1", "1"])
        ET.SubElement(harmony, "kind").text = rng.choice(CHORD_KINDS)
        measure.insert(first_note, harmony)  # <harmony> precedes its note
        added += 1
    return added


def add_performance_words(root, rng, probability=0.18):
    added = 0
    for measure in root.iter("measure"):
        if rng.random() > probability:
            continue
        children = list(measure)
        first_note = next((index for index, child in enumerate(children)
                           if child.tag == "note"), None)
        if first_note is None:
            continue
        direction = ET.Element("direction", {"placement": rng.choice(["above", "below"])})
        direction_type = ET.SubElement(direction, "direction-type")
        ET.SubElement(direction_type, "words").text = rng.choice(PERFORMANCE_WORDS)
        measure.insert(first_note, direction)
        added += 1
    return added


def annotate_tree(root, rng, profile):
    """Apply a named annotation profile. Returns a summary for the manifest."""
    summary = {"profile": profile}
    if profile == "none":
        return summary

    summary["title"] = set_title_block(root, rng)
    if profile == "title":
        return summary

    if rng.random() < 0.55:
        summary["note_names"] = add_note_names(root, rng, coverage=rng.uniform(0.5, 0.95))
    if rng.random() < 0.5:
        summary["fingerings"] = add_fingerings(root, rng, coverage=rng.uniform(0.15, 0.45))
    if rng.random() < 0.45:
        summary["chord_symbols"] = add_chord_symbols(root, rng, probability=rng.uniform(0.2, 0.6))
    if rng.random() < 0.5:
        summary["performance_words"] = add_performance_words(root, rng)
    return summary


def write_tree(root, path):
    """Write MusicXML back out, restoring the DOCTYPE ElementTree drops."""
    body = ET.tostring(root, encoding="unicode")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        handle.write(DOCTYPE + "\n")
        handle.write(body)


def annotate_file(source_path, target_path, rng, profile):
    tree = ET.parse(source_path)
    root = tree.getroot()
    summary = annotate_tree(root, rng, profile)
    write_tree(root, target_path)
    return summary
