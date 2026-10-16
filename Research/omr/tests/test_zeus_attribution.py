from fractions import Fraction
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zeus_attribution_prepare import first_page, install_cpu_segnet
from zeus_attribution_infer import render_tokens
from zeus_attribution_infer import collect_runtime_probe
from zeus_attribution_analyze import read_prediction, failed_variant, system_truth, rebase
from zeus_attribution_verify import verify_selected_records
from zeus_provenance import file_record
from sheet2play_omr.zeus_trace import xml_trace, merge_segments, local_metrics, metric_summary, Segment


def test_detector_cpu_session_preserves_installed_runner_and_forbids_gpu(tmp_path):
    from types import SimpleNamespace
    model = tmp_path / "weights.onnx"
    model.write_bytes(b"pinned model")
    calls = []
    class InstalledSegnet:
        def __init__(self, *_):
            raise AssertionError("Default model/provider selection must not execute")
        def run(self, data):
            return data
    session = SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"],
        io_binding=lambda: "binding", get_inputs=lambda: [SimpleNamespace(name="input")],
        get_outputs=lambda: [SimpleNamespace(name="output")])
    def create(path, *, sess_options, providers):
        calls.append((path, sess_options, providers))
        return session
    module = SimpleNamespace(segnet_path_onnx_fp16=model, _segnet_inference=None, Segnet=InstalledSegnet)
    runtime = SimpleNamespace(SessionOptions=SimpleNamespace, InferenceSession=create,
                              ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"))
    evidence = install_cpu_segnet(module, runtime)
    assert calls[0][2] == ["CPUExecutionProvider"]
    assert calls[0][1].intra_op_num_threads == 8 and calls[0][1].inter_op_num_threads == 1
    assert module._segnet_inference.run("unchanged") == "unchanged"
    assert module._segnet_inference.fp16 and not module._segnet_inference.use_gpu
    assert evidence["weights_sha256"] == file_record(model)["sha256"]
    with pytest.raises(RuntimeError, match="already initialized"):
        install_cpu_segnet(module, runtime)
    module._segnet_inference = None
    session.get_providers = lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"]
    with pytest.raises(RuntimeError, match="explicit CPU"):
        install_cpu_segnet(module, runtime)
    assert module._segnet_inference is None
    model.unlink()
    with pytest.raises(FileNotFoundError, match="weights missing"):
        install_cpu_segnet(module, runtime)


def xml_file(tmp_path, measures: str) -> Path:
    path = tmp_path / "score.musicxml"
    path.write_text('<score-partwise><part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>'
                    '<part id="P1">' + measures + '</part></score-partwise>', encoding="utf-8")
    return path


def test_probe_uses_original_distribution_context_and_restores_paths(monkeypatch, tmp_path):
    import zeus_attribution_infer as inference
    import zeus_provenance_probe as provenance
    diagnostic = str(inference.HERE / "src")
    unrelated = str(tmp_path)
    saved = [diagnostic, unrelated, *sys.path]
    monkeypatch.setattr(sys, "path", saved.copy())
    def collect(root):
        assert diagnostic not in sys.path and unrelated in sys.path
        sys.path.insert(0, "temporary-probe-import-path")
        return {"distributions": {"pinned-runtime": "1"}}
    monkeypatch.setattr(provenance, "collect", collect)
    actual = collect_runtime_probe()
    assert actual["distributions"] == {"pinned-runtime": "1"}
    assert sys.path == saved
    def fail(root):
        raise RuntimeError("fixture probe failure")
    monkeypatch.setattr(provenance, "collect", fail)
    with pytest.raises(RuntimeError, match="fixture probe failure"):
        collect_runtime_probe()
    assert sys.path == saved


def note(step="C", duration=1, chord=False, tie="", voice=1):
    return (f'<note>{"<chord/>" if chord else ""}<pitch><step>{step}</step><octave>4</octave></pitch>'
            f'<duration>{duration}</duration><voice>{voice}</voice>{tie}</note>')


def test_tuplet_pickup_backups_and_independent_chord_ties(tmp_path):
    path = xml_file(tmp_path, '<measure number="0" implicit="yes"><attributes><divisions>3</divisions>'
        '<time><beats>4</beats><beat-type>4</beat-type></time></attributes>'
        + note(tie='<tie type="start"/>') + note("E", chord=True, tie='<tie type="start"/>')
        + '<backup><duration>1</duration></backup>' + note("G", voice=2) + '</measure>'
        '<measure number="1"><print new-system="yes"/><attributes><time><beats>3</beats><beat-type>4</beat-type></time></attributes>'
        + note(duration=2, tie='<tie type="stop"/>') + note("E", 2, True, '<tie type="stop"/>')
        + note("D", 7) + '</measure>')
    segments, measures = xml_trace(path)
    merged, issues = merge_segments(segments)
    assert not issues
    assert len(segments) == 6 and len(merged) == 4
    assert {(n.pitch, n.onset, n.duration) for n in merged} == {
        (60, Fraction(0), Fraction(1)), (64, Fraction(0), Fraction(1)),
        (67, Fraction(0), Fraction(1, 3)), (62, Fraction(1), Fraction(7, 3))}
    assert measures[0]["advance"] == "1/3"
    assert measures[1]["new_system"] and measures[1]["overflow"] is False


def test_malformed_backup_fails_closed(tmp_path):
    path = xml_file(tmp_path, '<measure><backup><duration>1</duration></backup></measure>')
    with pytest.raises(ValueError, match="precedes"):
        xml_trace(path)


@pytest.mark.parametrize("divisions", [0, -2])
def test_invalid_divisions(tmp_path, divisions):
    path = xml_file(tmp_path, f'<measure><attributes><divisions>{divisions}</divisions></attributes></measure>')
    with pytest.raises(ValueError, match="positive"):
        xml_trace(path)


def test_page_reference_stops_at_layout_page_boundary(tmp_path):
    path = xml_file(tmp_path, '<measure number="1">' + note() + '</measure>'
        '<measure number="2"><print new-page="yes"/>' + note("D") + '</measure>')
    dest = tmp_path / "page.musicxml"
    info = first_page(path, dest)
    assert info["retained_measures_per_part"] == {"P1": 1}
    assert len(xml_trace(dest)[0]) == 1


def test_unknown_mapping_matches_upstream_and_wrapper_difference():
    tags = ["<unk>", "measure", "C4"]
    assert render_tokens([1, 0, 2], tags) == "measure <unk> C4"
    assert render_tokens([1, 0, 2], tags, filter_unknown=True) == "measure C4"
    with pytest.raises(ValueError, match="invalid"):
        render_tokens([-1], tags)
    with pytest.raises(ValueError, match="invalid"):
        render_tokens([True], tags)


def segment(onset=0, measure=0, local=0, duration=1, ties=(), voice="1"):
    return Segment(60, Fraction(onset), Fraction(duration), 0, voice, "P1", measure, Fraction(local), ties)


def test_measure_local_diagnoses_accumulated_drift_without_changing_global_score():
    truth = [segment(), segment(4, 1)]
    prediction = [segment(), segment(5, 1)]
    assert metric_summary([n.metric() for n in prediction], [n.metric() for n in truth])["onset_duration_f1"] == 0.5
    assert local_metrics(prediction, truth)["macro_onset_duration_f1"] == 1
    changed_duration = [segment(), segment(5, 1, duration=2)]
    assert local_metrics(changed_duration, truth)["macro_onset_duration_f1"] == 0.5


def test_missing_measure_and_failed_prediction_are_penalized():
    truth = [segment(), segment(4, 1)]
    assert local_metrics(truth[:1], truth)["macro_onset_duration_f1"] == 0.5
    result = metric_summary([], [n.metric() for n in truth])
    assert result["onset_duration_f1"] == 0 and result["missing_notes"] == 2


def test_tie_merge_preserves_independent_voice_and_requires_contiguity():
    notes = [segment(ties=("start",)), segment(1, 1, ties=("stop",), voice="2")]
    merged, issues = merge_segments(notes)
    assert len(merged) == 2 and len(issues) == 2
    notes = [segment(ties=("start",)), segment(2, 1, ties=("stop",))]
    merged, issues = merge_segments(notes)
    assert len(merged) == 2
    assert {issue["kind"] for issue in issues} == {
        "unmatched_or_noncontiguous_tie_stop", "interrupted_tie_start"}


def test_invalid_xml_is_recorded_and_penalized(tmp_path):
    path = tmp_path / "invalid.musicxml"
    path.write_text("<score-partwise>", encoding="utf-8")
    failure = read_prediction(path)
    assert failure["status"] == "failed" and failure["stage"] == "xml_trace"
    result = failed_variant([segment().metric()], [failure], [], 1.0)
    assert result["global"]["onset_duration_f1"] == 0
    assert result["global"]["missing_notes"] == 1


def test_normalizer_error_is_recorded(monkeypatch, tmp_path):
    import zeus_attribution_analyze as analysis
    path = xml_file(tmp_path, '<measure>' + note() + '</measure>')
    def reject(_):
        raise ValueError("Invalid normalization result")
    monkeypatch.setattr(analysis, "normalized_notes", reject)
    result = read_prediction(path)
    assert result["status"] == "failed" and result["stage"] == "unchanged_normalization"


def test_diagnostic_trace_does_not_reject_output_accepted_by_unchanged_bridge(tmp_path):
    path = xml_file(tmp_path, '<measure><attributes><divisions>1</divisions>'
        '<time><beats>4</beats><beat-type>4</beat-type></time></attributes>' + note() +
        '<note print-object="no"><rest measure="yes"/><voice>2</voice></note></measure>')
    result = read_prediction(path)
    assert result["status"] == "succeeded" and len(result["normalized"]) == 1
    assert result["raw"] is None and result["trace_failure"]["stage"] == "xml_trace"
    assert metric_summary(result["normalized"], result["normalized"])["onset_duration_f1"] == 1


def test_primary_page_scoring_survives_unavailable_exact_trace(monkeypatch, tmp_path):
    import json
    import zeus_attribution_analyze as analysis
    reference = xml_file(tmp_path, '<measure>' + note() + '</measure>')
    reference = reference.rename(tmp_path / 'reference.musicxml')
    prediction = xml_file(tmp_path, '<measure>' + note() +
        '<note print-object="no"><rest measure="yes"/><voice>2</voice></note></measure>')
    work = tmp_path / 'inference/example/system-0001'
    work.mkdir(parents=True)
    row = {'seconds': 1, 'token_count': 1, 'termination': 'EOS', 'unknown_token_count': 0,
           'conversion': {'status': 'succeeded', 'diagnostics': '',
                          'musicxml_sha256': file_record(prediction)['sha256']}}
    for variant in ('upstream', 'wrapper'):
        (work / f'{variant}.musicxml').write_bytes(prediction.read_bytes())
    (work / 'prediction.json').write_text(json.dumps(
        {'crop_sha256': 'crop-identity', 'upstream': row, 'wrapper': row}), encoding='utf-8')
    destination = tmp_path / 'analysis'
    destination.mkdir()
    monkeypatch.setattr(analysis, 'OUT', tmp_path)
    result = analysis.analyze_item({'item_id': 'example', 'collection': 'generated',
        'reference': str(reference), 'reference_sha256': file_record(reference)['sha256'],
        'crops': [{'sha256': 'crop-identity'}]}, destination)
    for variant in result['variants'].values():
        assert variant['status'] == 'succeeded' and variant['global']['onset_duration_f1'] == 1
        assert variant['measure_local'] is None and variant['trace_failure']['stage'] == 'xml_trace'


def test_deferred_chord_tie_defect_is_attributed_to_normalization():
    path = Path(__file__).resolve().parents[1] / "reports/zeus-attribution/phase2/cross-system-chord-tie.musicxml"
    result = read_prediction(path)
    assert result["status"] == "succeeded"
    assert len(result["raw"]) == 6 and len(result["merged"]) == 4
    assert not result["ties"] and len(result["normalized"]) == 6
    merged = {(n.pitch, n.onset, n.duration) for n in result["merged"]}
    assert merged == {(60, Fraction(0), Fraction(1)), (64, Fraction(0), Fraction(1)),
                      (55, Fraction(0), Fraction(1, 3)), (62, Fraction(1), Fraction(7, 3))}
    assert metric_summary(result["normalized"], [n.metric() for n in result["merged"]])["onset_duration_f1"] == 0.4


def test_parser_observations_preserve_independent_voice_and_tie_segments():
    from zeus_attribution_parser_trace import parsed_trace
    path = Path(__file__).resolve().parents[1] / "reports/zeus-attribution/phase2/cross-system-chord-tie.musicxml"
    raw, measures = parsed_trace(path)
    merged, issues = merge_segments(raw)
    assert len(raw) == 6 and len(merged) == 4 and not issues
    assert len(measures) == 2
    assert {(n.pitch, n.onset, n.duration) for n in merged} == {
        (60, Fraction(0), Fraction(1)), (64, Fraction(0), Fraction(1)),
        (55, Fraction(0), Fraction(1, 3)), (62, Fraction(1), Fraction(7, 3))}


def test_selected_source_pins_do_not_require_whole_repository_inventory(tmp_path):
    path = tmp_path / "pinned.py"
    path.write_text("value = 1\n", encoding="utf-8")
    record = {**file_record(path), "path": path.name}
    (tmp_path / "unrelated.txt").write_text("unrelated", encoding="utf-8")
    verify_selected_records(tmp_path, [record])
    path.write_text("value = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        verify_selected_records(tmp_path, [record])
    with pytest.raises(ValueError, match="escapes"):
        verify_selected_records(tmp_path, [{**record, "path": "../outside.py"}])


def test_image_system_boundaries_preserve_unmatched_systems():
    notes = [segment(), segment(4, 1), segment(8, 2)]
    measures = [{"part": "P1", "index": i, "new_system": False} for i in range(3)]
    groups = system_truth(notes, measures, [0, 2])
    assert [len(group) for group in groups] == [2, 1]
    with pytest.raises(ValueError, match="boundaries"):
        system_truth(notes, measures, [0, 3])


def test_system_local_origin_keeps_initial_missing_staff_rests():
    notes = [segment(7, 2)]
    measures = [{"part": "P1", "index": 1, "start": "4"}]
    rebased = rebase(notes, measures, 1)
    assert rebased[0].onset == 3
    assert notes[0].onset == 7


def test_underfilled_hidden_staff_rest_is_flagged_without_reference_repair(tmp_path):
    path = xml_file(tmp_path, '<measure><attributes><divisions>1</divisions><time><beats>3</beats>'
        '<beat-type>2</beat-type></time></attributes><note><rest measure="yes"/><duration>4</duration>'
        '</note></measure><measure>' + note() + '</measure>')
    segments, measures = xml_trace(path)
    assert measures[0]["underfilled"] and measures[0]["full_measure_rests"] == 1
    assert measures[0]["pitched_notes"] == 0 and segments[0].onset == 4
