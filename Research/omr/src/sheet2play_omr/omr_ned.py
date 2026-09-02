"""OMR Normalized Edit Distance, the field's current standard OMR metric.

OMR-NED was introduced alongside the Sheet Music Benchmark (arXiv:2506.10488) and is now the
number published OMR results are quoted in, so scoring with it makes this project's results
directly comparable to the literature instead of only to itself.

It is defined as `(I + D) / (N1 + N2)` - insertions plus deletions of individual music
symbols, normalised by the symbol counts of both scores - and unlike the note-level F1 metrics
in `metrics.py` it covers noteheads, beams, accidentals, clefs, key and time signatures, and
so on. Lower is better, which is the opposite direction to every other metric in this harness;
`OmrNedResult.score` is named rather than returned bare to make that hard to misread.

This lives apart from `metrics.py` deliberately. `metrics.py` is pure stdlib and imports in
milliseconds; musicdiff pulls in music21 and converter21. Keeping the heavy import here, and
lazy, means the existing metrics stay cheap to use.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ResearchError


@dataclass(frozen=True, slots=True)
class OmrNedResult:
    """One prediction scored against one ground truth. Lower `score` is better."""

    score: float
    edit_distance: int
    ground_truth_symbols: int
    predicted_symbols: int
    by_category: dict[str, int]

    @property
    def accuracy_like(self) -> float:
        """`1 - score`, for reading next to the F1 metrics without flipping direction."""
        return 1.0 - self.score


def _load_musicdiff() -> Any:
    try:
        import musicdiff
    except ImportError as error:
        raise ResearchError(
            "RUNTIME_MISSING",
            "omr_ned",
            "musicdiff is required for OMR-NED; install it into the research venv",
        ) from error
    return musicdiff


def score_pair(prediction: Path, ground_truth: Path) -> OmrNedResult | None:
    """Score one prediction against one ground truth.

    Both paths may be any format music21 reads - MusicXML, MEI, Humdrum `**kern`. Returns
    None when musicdiff declines the pair, which it does for scores it cannot parse; callers
    should treat that as a failed sample rather than a zero, because scoring it as 0.0 would
    silently reward an engine for emitting garbage.
    """
    musicdiff = _load_musicdiff()

    # `diff_ml_training` is the public entry point but only scores whole folders. The
    # per-pair function underneath it is private, so fall back to the public one if a
    # musicdiff upgrade renames it rather than failing outright.
    per_pair = getattr(musicdiff, "_diff_omr_ned_metrics", None)
    if per_pair is None:
        return _score_pair_via_folders(musicdiff, prediction, ground_truth)

    try:
        # `detail` has no default on the private function, unlike the public one.
        metrics = per_pair(
            predpath=str(prediction),
            gtpath=str(ground_truth),
            detail=musicdiff.DetailLevel.Default,
        )
    except Exception as error:
        raise ResearchError(
            "OMR_NED_FAILED", "omr_ned", f"musicdiff failed on {prediction.name}: {error}"
        ) from error
    if metrics is None:
        return None
    return OmrNedResult(
        score=float(metrics.omr_ned),
        edit_distance=int(metrics.omr_edit_distance),
        ground_truth_symbols=int(metrics.gt_numsyms),
        predicted_symbols=int(metrics.pred_numsyms),
        by_category=dict(metrics.edit_distances_dict or {}),
    )


def _score_pair_via_folders(musicdiff: Any, prediction: Path, ground_truth: Path):
    """Fallback: stage the pair into two temp folders and use the public batch API."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory(prefix="omr-ned-") as temporary:
        root = Path(temporary)
        predicted_dir = root / "predicted"
        truth_dir = root / "truth"
        output_dir = root / "out"
        for directory in (predicted_dir, truth_dir, output_dir):
            directory.mkdir()
        # musicdiff pairs files by identical name, so both copies must share one.
        name = "score" + prediction.suffix
        shutil.copyfile(prediction, predicted_dir / name)
        shutil.copyfile(ground_truth, truth_dir / name)
        try:
            score, _ = musicdiff.diff_ml_training(
                str(predicted_dir), str(truth_dir), str(output_dir)
            )
        except Exception as error:
            raise ResearchError(
                "OMR_NED_FAILED", "omr_ned", f"musicdiff failed on {prediction.name}: {error}"
            ) from error
    return OmrNedResult(
        score=float(score),
        edit_distance=-1,
        ground_truth_symbols=-1,
        predicted_symbols=-1,
        by_category={},
    )


def score_folders(prediction_dir: Path, ground_truth_dir: Path, output_dir: Path) -> float:
    """Batch OMR-NED over two folders whose files share names. Returns the overall score."""
    musicdiff = _load_musicdiff()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        score, _ = musicdiff.diff_ml_training(
            str(prediction_dir), str(ground_truth_dir), str(output_dir)
        )
    except Exception as error:
        raise ResearchError("OMR_NED_FAILED", "omr_ned", str(error)) from error
    return float(score)
