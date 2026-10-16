"""Observe Zeus imports and configuration without constructing or running a model."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import sys


def collect(zeus_root: Path) -> dict:
    sys.path.insert(0, str(zeus_root))
    sys.path.insert(0, str(zeus_root / "source"))
    import zeus_runner
    from zeus import parser
    import tensorflow as tf

    model = zeus_root / "weights/zeus-olimpic-1.0-2024-02-12.model"
    options = json.loads((model / "options.json").read_text(encoding="utf-8"))
    effective = vars(parser.parse_args([]))
    effective.update(options)
    effective["train_batches"] = 1
    tags = (model / "tags.txt").read_text(encoding="utf-8").splitlines()
    if not tags or len(tags) != len(set(tags)) or tags[0] != "<unk>":
        raise ValueError("Invalid ordered Zeus vocabulary")
    imported = {}
    for name, module in sorted(sys.modules.copy().items()):
        filename = getattr(module, "__file__", None)
        if filename and Path(filename).is_file():
            imported[name] = str(Path(filename).resolve())
    symbols = {name: str(Path(inspect.getfile(value)).resolve()) for name, value in {
        "Model": zeus_runner.Model, "Delinearizer": zeus_runner.Delinearizer,
        "part_to_score": zeus_runner.part_to_score,
        "ZeusRunner": zeus_runner.ZeusRunner,
    }.items()}
    return {
        "schema_version": 1, "inference_started": False,
        "probe_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version, "executable": sys.executable,
        "prefix": sys.prefix, "base_prefix": sys.base_prefix,
        "base_executable": getattr(sys, "_base_executable", sys.executable),
        "tensorflow": tf.__version__,
        "tensorflow_build": tf.sysconfig.get_build_info(),
        "gpu_devices": [device.name for device in tf.config.list_physical_devices("GPU")],
        "environment": {key: os.environ.get(key) for key in (
            "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
            "TF_NUM_INTRAOP_THREADS", "TF_NUM_INTEROP_THREADS", "CUDA_VISIBLE_DEVICES")},
        "symbols": symbols, "imported_modules": imported,
        "distributions": {dist.metadata["Name"]: dist.version
                          for dist in importlib.metadata.distributions()},
        "effective_options": effective, "ordered_tags": tags,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zeus-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = collect(args.zeus_root.resolve())
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, ValueError, ImportError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
