"""Run one Phase 2R candidate on a frozen development crop or page."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
SRC = HERE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phase2 import development_inputs  # noqa: E402
from phase2r import verify_historical_artifacts  # noqa: E402
from sheet2play_omr.adapter_contract import sha256_file, write_result  # noqa: E402
from sheet2play_omr.phase2_adapters import AudiverisAdapter, ZeusAdapter  # noqa: E402
from sheet2play_omr.phase2r_validation import run_with_typed_failure  # noqa: E402
from sheet2play_omr.phase2r_vlm import QwenVlAbcAdapter  # noqa: E402


def _adapter(candidate: str) -> object:
    if candidate == "rokot":
        return QwenVlAbcAdapter(WORKSPACE, rokot=True)
    if candidate == "qwen":
        return QwenVlAbcAdapter(WORKSPACE, rokot=False)
    if candidate == "audiveris":
        executable = HERE / ".runtime" / "phase2r" / "audiveris-extract" / "Audiveris" / "Audiveris.exe"
        os.environ["SHEET2PLAY_AUDIVERIS_EXECUTABLE"] = str(executable.resolve())
        return AudiverisAdapter(WORKSPACE)
    if candidate == "zeus_app":
        return ZeusAdapter(WORKSPACE, integration=True)
    raise ValueError(f"Unknown candidate: {candidate}")


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=("rokot", "qwen", "audiveris", "zeus_app"), required=True)
    parser.add_argument("--path", choices=("crop", "page"), required=True)
    args = parser.parse_args(arguments)
    if args.candidate in ("audiveris", "zeus_app") and args.path != "page":
        parser.error("This candidate supports complete pages only")

    verify_historical_artifacts()
    crop, page = development_inputs()
    item = crop if args.path == "crop" else page
    adapter = _adapter(args.candidate)
    config_hash = adapter.config.sha256  # type: ignore[attr-defined]
    executable = getattr(adapter, "executable", None) or getattr(adapter, "cli", None)
    runtime_hash = sha256_file(executable)[:12] if executable is not None and executable.is_file() else "no-runtime"
    identity = f"{args.candidate}-{item.item_id}-{config_hash[:12]}-{runtime_hash}"
    result_path = HERE / "reports" / "phase2r" / "development-smokes" / f"{identity}.json"
    output = HERE / ".runtime" / "phase2r" / "smokes" / identity
    legacy_result = HERE / "reports" / "phase2r" / "development-smokes" / (
        f"{args.candidate}-{item.item_id}-{config_hash[:12]}-no-runtime.json"
    )
    if result_path.exists() or output.exists() or legacy_result.exists():
        raise FileExistsError(f"Refusing to overwrite an existing development smoke: {identity}")
    print(json.dumps({"event": "start", "candidate": args.candidate, "item_id": item.item_id,
                      "input_sha256": item.input_sha256, "config_sha256": config_hash,
                      "output": str(result_path)}, sort_keys=True), flush=True)
    result = run_with_typed_failure(adapter, item, output)
    write_result(result_path, result)
    print(json.dumps({"event": "complete", "candidate": args.candidate,
                      "status": result.status.value, "error": result.error,
                      "result": str(result_path)}, sort_keys=True), flush=True)
    return 0 if result.status.value == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
