from __future__ import annotations

import json
import math
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .assets import RuntimePaths, verify_runtime
from .errors import ResearchError
from .gates import baseline_adaptation_gate, enforce_cloud_budget
from .input_pages import TARGET_HEIGHT, TARGET_WIDTH, normalize_page
from .kern import validate_kern


@dataclass(frozen=True, slots=True)
class AdapterTrainingConfig:
    rank: int = 8
    alpha: float = 16.0
    dropout: float = 0.05
    learning_rate: float = 2e-4
    weight_decay: float = 0.01
    epochs: int = 3
    patience: int = 1
    max_runtime_hours: float = 12.0
    max_temperature_c: int = 85

    def validate(self) -> None:
        if self.rank < 1 or self.epochs < 1 or self.epochs > 3 or self.patience < 1:
            raise ResearchError("TRAINING_CONFIG_INVALID", "adaptation", "Invalid rank, epoch, or patience setting")
        values = (self.alpha, self.dropout, self.learning_rate, self.weight_decay, self.max_runtime_hours)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ResearchError("TRAINING_CONFIG_INVALID", "adaptation", "Training values must be finite and non-negative")
        if not 0 <= self.dropout < 1 or self.max_runtime_hours <= 0:
            raise ResearchError("TRAINING_CONFIG_INVALID", "adaptation", "Dropout or runtime limit is invalid")


def _read_summary(path: Path) -> dict[str, float]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ResearchError("GATE_INPUT_INVALID", "adaptation", f"Cannot read {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ResearchError("GATE_INPUT_INVALID", "adaptation", f"Expected a JSON object in {path}")
    return {str(key): float(value) for key, value in payload.items() if isinstance(value, (int, float))}


def authorize_training(
    candidate_summary: Path,
    homr_summary: Path,
    *,
    hourly_rate: float,
    estimated_hours: float,
) -> float:
    decision = baseline_adaptation_gate(_read_summary(candidate_summary), _read_summary(homr_summary))
    if not decision.passed:
        raise ResearchError("BASELINE_GATE_FAILED", "adaptation", "; ".join(decision.failures))
    return enforce_cloud_budget(hourly_rate, estimated_hours, 10.0)


def _temperature_c() -> int:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu",
                "--format=csv,noheader,nounits",
                "--id=0",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return int(result.stdout.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as error:
        raise ResearchError("GPU_TELEMETRY_FAILED", "adaptation", f"Cannot read GPU temperature: {error}") from error


def _load_training_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ResearchError("DATASET_INVALID", "adaptation", f"Cannot read {path}: {error}") from error
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            image = Path(item["image"]).resolve(strict=True)
            kern = Path(item["kern"]).resolve(strict=True)
            validate_kern(kern.read_text(encoding="utf-8"))
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ResearchError("DATASET_INVALID", "adaptation", f"Invalid line {line_number}: {error}") from error
        rows.append({"image": str(image), "kern": str(kern)})
    if not rows:
        raise ResearchError("DATASET_INVALID", "adaptation", "Training manifest is empty")
    return rows


def train_adapter(
    train_manifest: Path,
    validation_manifest: Path,
    output_dir: Path,
    candidate_summary: Path,
    homr_summary: Path,
    *,
    hourly_rate: float,
    estimated_hours: float,
    config: AdapterTrainingConfig | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    configuration = config or AdapterTrainingConfig()
    configuration.validate()
    approved_cost = authorize_training(
        candidate_summary,
        homr_summary,
        hourly_rate=hourly_rate,
        estimated_hours=estimated_hours,
    )
    runtime_paths = paths or RuntimePaths.discover()
    runtime_metadata = verify_runtime(runtime_paths)
    os.environ["HF_HOME"] = str(runtime_paths.hf_cache)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    train_rows = _load_training_rows(train_manifest)
    validation_rows = _load_training_rows(validation_manifest)

    try:
        import torch
        from safetensors.torch import save_file
        from torch import nn
        from torch.utils.data import DataLoader, Dataset
        from transformers import AutoModelForCausalLM, PreTrainedTokenizerFast
    except ImportError as error:
        raise ResearchError("RUNTIME_MISSING", "adaptation", f"Training dependency is missing: {error}") from error
    if not torch.cuda.is_available() or "RTX 4050" not in torch.cuda.get_device_name(0).upper():
        raise ResearchError("CUDA_UNAVAILABLE", "adaptation", "Adapter training requires the benchmark RTX 4050")

    class LoRALinear(nn.Module):
        def __init__(self, base: nn.Linear) -> None:
            super().__init__()
            self.base = base
            self.base.requires_grad_(False)
            self.lora_a = nn.Linear(base.in_features, configuration.rank, bias=False)
            self.lora_b = nn.Linear(configuration.rank, base.out_features, bias=False)
            self.dropout = nn.Dropout(configuration.dropout)
            self.scale = configuration.alpha / configuration.rank
            nn.init.kaiming_uniform_(self.lora_a.weight, a=math.sqrt(5))
            nn.init.zeros_(self.lora_b.weight)

        def forward(self, values: Any) -> Any:
            return self.base(values) + self.lora_b(self.lora_a(self.dropout(values))) * self.scale

    class PairDataset(Dataset):
        def __init__(self, rows: list[dict[str, str]], tokenizer: Any) -> None:
            self.rows = rows
            self.tokenizer = tokenizer

        def __len__(self) -> int:
            return len(self.rows)

        def __getitem__(self, index: int) -> dict[str, Any]:
            row = self.rows[index]
            with Image.open(row["image"]) as source:
                normalized = normalize_page(source)
                array = np.asarray(normalized, dtype=np.float32)
                normalized.close()
            pixels = torch.from_numpy(array).permute(2, 0, 1).contiguous() / 255.0
            pixels = (pixels - 0.5) / 0.5
            target_lines = Path(row["kern"]).read_text(encoding="utf-8").splitlines()
            target = "\n".join(target_lines[1:]) + "\n"
            encoded = self.tokenizer(
                target,
                truncation=False,
                return_tensors="pt",
            )["input_ids"][0]
            if encoded.shape[0] > 2048:
                raise ResearchError(
                    "DATASET_INVALID",
                    "adaptation",
                    f"Target has {encoded.shape[0]} tokens; maximum is 2048",
                )
            return {"pixel_values": pixels, "labels": encoded}

    def collate(batch: list[dict[str, Any]]) -> dict[str, Any]:
        pixels = torch.stack([item["pixel_values"] for item in batch])
        maximum = max(int(item["labels"].shape[0]) for item in batch)
        labels = torch.full((len(batch), maximum), -100, dtype=torch.long)
        for index, item in enumerate(batch):
            labels[index, : item["labels"].shape[0]] = item["labels"]
        return {
            "pixel_values": pixels,
            "image_sizes": torch.tensor([[TARGET_HEIGHT, TARGET_WIDTH]] * len(batch)),
            "labels": labels,
        }

    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(runtime_paths.model), local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(runtime_paths.model),
        trust_remote_code=True,
        local_files_only=True,
        torch_dtype=torch.float32,
    )
    model.requires_grad_(False)
    replacements = 0
    for module_name, module in tuple(model.named_modules()):
        if "decoder" not in module_name.casefold() or not isinstance(module, nn.Linear):
            continue
        parent_name, _, child_name = module_name.rpartition(".")
        parent = model.get_submodule(parent_name) if parent_name else model
        setattr(parent, child_name, LoRALinear(module))
        replacements += 1
    if replacements == 0:
        raise ResearchError("MODEL_INVALID", "adaptation", "No decoder linear layers were eligible for LoRA")
    model.to("cuda:0")

    train_loader = DataLoader(PairDataset(train_rows, tokenizer), batch_size=1, shuffle=True, collate_fn=collate)
    validation_loader = DataLoader(PairDataset(validation_rows, tokenizer), batch_size=1, shuffle=False, collate_fn=collate)
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=configuration.learning_rate, weight_decay=configuration.weight_decay)
    scaler = torch.amp.GradScaler("cuda")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    best_loss = math.inf
    stale_epochs = 0
    history: list[dict[str, float]] = []

    def enforce_guards() -> None:
        if time.monotonic() - started > configuration.max_runtime_hours * 3600:
            raise ResearchError("TRAINING_LIMIT_REACHED", "adaptation", "Maximum training runtime reached")
        temperature = _temperature_c()
        if temperature > configuration.max_temperature_c:
            raise ResearchError(
                "GPU_TEMPERATURE_LIMIT",
                "adaptation",
                f"GPU temperature {temperature}C exceeds {configuration.max_temperature_c}C",
            )

    def adapter_state() -> dict[str, Any]:
        return {
            name: tensor.detach().cpu().contiguous()
            for name, tensor in model.state_dict().items()
            if ".lora_a." in name or ".lora_b." in name
        }

    for epoch in range(configuration.epochs):
        model.train()
        train_losses: list[float] = []
        for batch in train_loader:
            enforce_guards()
            optimizer.zero_grad(set_to_none=True)
            batch = {name: value.to("cuda:0") for name, value in batch.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                loss = model(**batch).loss
            if not torch.isfinite(loss):
                raise ResearchError("TRAINING_DIVERGED", "adaptation", "Training loss is non-finite")
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable, 1.0)
            scaler.step(optimizer)
            scaler.update()
            train_losses.append(float(loss.detach().cpu()))

        model.eval()
        validation_losses: list[float] = []
        with torch.inference_mode():
            for batch in validation_loader:
                batch = {name: value.to("cuda:0") for name, value in batch.items()}
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    validation_losses.append(float(model(**batch).loss.detach().cpu()))
        validation_loss = sum(validation_losses) / len(validation_losses)
        history.append(
            {
                "epoch": float(epoch + 1),
                "train_loss": sum(train_losses) / len(train_losses),
                "validation_loss": validation_loss,
            }
        )
        save_file(adapter_state(), str(output_dir / f"adapter-epoch-{epoch + 1}.safetensors"))
        if validation_loss < best_loss:
            best_loss = validation_loss
            stale_epochs = 0
            save_file(adapter_state(), str(output_dir / "adapter-best.safetensors"))
        else:
            stale_epochs += 1
            if stale_epochs >= configuration.patience:
                break

    result = {
        "runtime": runtime_metadata,
        "approved_estimated_cost_usd": approved_cost,
        "config": asdict(configuration),
        "decoder_lora_layers": replacements,
        "history": history,
        "best_validation_loss": best_loss,
    }
    (output_dir / "training-run.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
