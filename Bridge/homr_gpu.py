from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path


CUDA_PROVIDER = "CUDAExecutionProvider"
_DLL_DIRECTORY_HANDLES: list[object] = []


def configure_windows_nvidia_dll_paths() -> None:
    if os.name != "nt":
        return

    nvidia_directory = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    binary_directories = sorted(
        path for path in nvidia_directory.glob("*/bin") if path.is_dir()
    )
    if not binary_directories:
        raise RuntimeError(
            f"No pip-installed NVIDIA runtime DLL directories were found under {nvidia_directory}"
        )

    existing_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join(
        [*(str(path) for path in binary_directories), existing_path]
    )
    for directory in binary_directories:
        _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(directory)))


def configure_cuda() -> None:
    configure_windows_nvidia_dll_paths()

    try:
        import onnxruntime as ort
    except ImportError as error:
        raise RuntimeError(
            "onnxruntime-gpu is not installed in the homr GPU environment"
        ) from error

    try:
        ort.preload_dlls(directory="")
    except Exception as error:
        raise RuntimeError(f"Could not preload CUDA/cuDNN runtime libraries: {error}") from error

    providers = ort.get_available_providers()
    if CUDA_PROVIDER not in providers:
        available = ", ".join(providers) if providers else "none"
        raise RuntimeError(
            f"{CUDA_PROVIDER} is unavailable; detected providers: {available}"
        )

    print(
        f"homr GPU runtime ready: ONNX Runtime {ort.__version__}, provider={CUDA_PROVIDER}",
        file=sys.stderr,
        flush=True,
    )


KEEP_TUPLETS_VARIABLE = "SHEET2PLAY_HOMR_KEEP_TUPLETS"


def disable_tuplet_cleanup() -> None:
    """Neutralise homr's over-eager tuplet repair for rhythm diagnosis.

    homr post-processes decoder output with `_fix_over_eager_tuplets`, which strips every
    tuplet from any measure shorter than the median measure in the system. On a genuine
    triplet measure that rescales the durations and shifts every later onset while leaving
    the pitches intact. Replacing it with the identity leaves the rest of the cleanup chain
    untouched, so the A/B isolates that one heuristic.

    Note that homr's own `cleanup_tuplets=False` switch is *not* equivalent: it also skips
    `_only_keep_lower_staff_if_there_is_a_clef`, which would confound the comparison.
    """
    from homr.transformer import vocabulary

    vocabulary._fix_over_eager_tuplets = lambda chords: chords
    print(
        "homr diagnostic: tuplet cleanup disabled via " + KEEP_TUPLETS_VARIABLE,
        file=sys.stderr,
        flush=True,
    )


def run_homr(arguments: Sequence[str]) -> int:
    configure_cuda()

    try:
        from homr.main import main as homr_main
    except ImportError as error:
        raise RuntimeError("homr is not installed in the GPU environment") from error

    if os.environ.get(KEEP_TUPLETS_VARIABLE) == "1":
        disable_tuplet_cleanup()

    original_arguments = sys.argv
    sys.argv = ["homr", "--gpu", "force", *arguments]
    try:
        homr_main()
    finally:
        sys.argv = original_arguments
    return 0


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        return run_homr(tuple(sys.argv[1:] if arguments is None else arguments))
    except KeyboardInterrupt:
        print("homr GPU processing was interrupted", file=sys.stderr, flush=True)
        return 130
    except Exception as error:
        print(f"homr GPU startup failed: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
