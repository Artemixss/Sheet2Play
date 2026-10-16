import os
import shutil
import sys
from typing import Any

import torch
import torch._dynamo
from transformers import (
    EarlyStoppingCallback,
    TrainerCallback,
    TrainerControl,
    TrainerState,
    TrainingArguments,
)

from homr.simple_logging import eprint
from homr.transformer.configs import Config
from training.architecture.transformer.tromr_arch import TrOMR, load_model
from training.omr_datasets.convert_grandstaff import (
    convert_grandstaff,
    grandstaff_train_index,
)
from training.omr_datasets.convert_lieder import convert_lieder, lieder_train_index
from training.omr_datasets.convert_musetrainer import (
    convert_musetrainer,
    musetrainer_train_index,
)
from training.omr_datasets.convert_pdmx import convert_pdmx, pdmx_train_index
from training.omr_datasets.convert_primus import (
    convert_primus_dataset,
    primus_train_index,
)
from training.run_id import get_run_id
from training.transformer.data_loader import label_names, load_dataset
from training.transformer.distribute import Distribute
from training.transformer.metrics import HomrTrainer
from training.transformer.mix_datasets import mix_training_sets

torch._dynamo.config.suppress_errors = True


class FreezeCallback(TrainerCallback):
    """
    Callback to freeze the backbone for a set number of epochs.
    Standard practice is ~2 epochs.
    """

    def __init__(self, epochs_to_freeze: int = 2):
        self.epochs_to_freeze = epochs_to_freeze
        self._backbone_frozen = False

    def on_train_begin(
        self, args: TrainingArguments, state: TrainerState, control: TrainerControl, **kwargs: Any
    ) -> None:
        model = kwargs.get("model")
        if model and hasattr(model, "freeze_backbone"):
            eprint(f"Freezing backbone for the first {self.epochs_to_freeze} epochs")
            model.freeze_backbone()
            self._backbone_frozen = True

    def on_epoch_begin(
        self, args: TrainingArguments, state: TrainerState, control: TrainerControl, **kwargs: Any
    ) -> None:
        model = kwargs.get("model")
        if model and self._backbone_frozen and state.epoch and state.epoch >= self.epochs_to_freeze:
            eprint(f"Unfreezing backbone at epoch {state.epoch}")
            model.unfreeze_backbone()
            self._backbone_frozen = False


def load_training_index(file_path: str) -> list[str]:
    with open(file_path) as f:
        return f.readlines()


def check_data_source(all_file_paths: list[str]) -> bool:
    result = True
    for file_paths in all_file_paths:
        paths = file_paths.strip().split(",")
        for path in paths:
            if path == "nosymbols":
                continue
            if not os.path.exists(path):
                eprint(f"Index {file_paths} does not exist due to {path}")
                result = False
    return result


def load_and_mix_training_sets(
    index_paths: list[str], weights: list[float], number_of_files: int
) -> list[str]:
    if len(index_paths) != len(weights):
        eprint("Error: Number of index paths and weights do not match")
        sys.exit(1)
    data_sources = [load_training_index(index) for index in index_paths]
    if not all(check_data_source(data) for data in data_sources):
        eprint("Error in datasets found")
        sys.exit(1)
    eprint(
        "Total number of training files to choose from", sum([len(data) for data in data_sources])
    )
    return mix_training_sets(data_sources, weights, number_of_files)


script_location = os.path.dirname(os.path.realpath(__file__))

git_root = os.path.join(script_location, "..", "..")


def _check_datasets_are_present(selected_datasets: list[str]) -> list[str]:
    for dataset in selected_datasets:
        if dataset == primus_train_index and not os.path.exists(primus_train_index):
            convert_primus_dataset()

        if dataset == grandstaff_train_index and not os.path.exists(grandstaff_train_index):
            convert_grandstaff()

        if dataset == lieder_train_index and not os.path.exists(lieder_train_index):
            convert_lieder()

        if dataset == musetrainer_train_index and not os.path.exists(musetrainer_train_index):
            convert_musetrainer()

        if dataset == pdmx_train_index and not os.path.exists(pdmx_train_index):
            convert_pdmx()
    return selected_datasets


def _cap_vram_for_desktop_use() -> None:
    """Sheet2Play addition: leave a slice of VRAM for whatever else uses the machine.

    A training run will otherwise take every byte the card has, and the desktop then fights
    it for memory. On the 8 GB box this is meant for that is the difference between being
    able to browse while it trains and not - a browser with hardware acceleration on can hold
    most of a gigabyte of VRAM.

    This does not make training need less memory. It makes an over-large batch fail fast and
    loudly instead of quietly starving the rest of the system, so the real lever is still
    SHEET2PLAY_BATCH. Set SHEET2PLAY_VRAM_FRACTION to 1.0 on a machine nobody is using.
    """
    fraction = float(os.environ.get("SHEET2PLAY_VRAM_FRACTION", "0.90"))
    if not torch.cuda.is_available() or fraction >= 1.0:
        return
    total = torch.cuda.get_device_properties(0).total_memory / 1e9
    torch.cuda.set_per_process_memory_fraction(fraction, 0)
    eprint(
        f"Capping training at {fraction:.0%} of VRAM "
        f"({total * fraction:.1f} GB of {total:.1f} GB); "
        f"{total * (1 - fraction):.1f} GB left for the desktop. "
        "Set SHEET2PLAY_VRAM_FRACTION=1.0 to use the whole card."
    )


def _is_ampere_or_newer() -> bool:
    """Compute capability 8.0 or higher.

    Sheet2Play change. Two separate decisions depend on this - whether bf16 is real rather
    than emulated, and whether torch.compile is worth attempting - so the check lives in one
    place.
    """
    if not torch.cuda.is_available():
        return False
    return torch.cuda.get_device_capability(0)[0] >= 8


def _has_native_bf16() -> bool:
    """True only for Ampere and newer.

    Sheet2Play change. Upstream sets bf16=not fp32, which leaves pre-Ampere cards with a
    choice between emulated bf16 and no mixed precision at all - the RTX 20xx series has
    no native bf16, but it does have real fp16 tensor cores. Note that
    torch.cuda.is_bf16_supported() counts the emulated path and returns True on Turing,
    so it cannot be used as the gate; compute capability is the honest signal.

    HuggingFace's Trainer attaches a GradScaler when fp16 is set, so overflow is handled.
    """
    if not torch.cuda.is_available():
        return False
    return torch.cuda.get_device_capability(0)[0] >= 8


def train_transformer(
    fp32: bool = False, resume: str = "", smoke_test: bool = False, fine_tune: bool = False
) -> None:
    distribute = Distribute()
    _cap_vram_for_desktop_use()

    number_of_epochs = 35
    if smoke_test:
        number_of_epochs = 10
    elif fine_tune:
        number_of_epochs = 15
    resume_from_checkpoint = None

    checkpoint_folder = "current_training"
    if resume:
        resume_from_checkpoint = os.path.join(git_root, checkpoint_folder, resume)
    elif os.path.exists(os.path.join(git_root, checkpoint_folder)):
        if distribute.is_rank0():
            shutil.rmtree(os.path.join(git_root, checkpoint_folder))

    dataset_index = [
        lieder_train_index,
        grandstaff_train_index,
        primus_train_index,
        pdmx_train_index,
        musetrainer_train_index,
    ]
    dataset_weights = [1.0, 1.0, 1.0, 1.0, 1.0]
    if distribute.is_rank0():
        _check_datasets_are_present(dataset_index)
    distribute.barrier()

    number_of_files = -1
    train_index = load_and_mix_training_sets(
        dataset_index,
        dataset_weights,
        number_of_files,
    )

    config = Config()
    datasets = load_dataset(train_index, config, val_split=0.1)

    compile_threshold = 50000
    # Sheet2Play change. TorchInductor's compile worker pool deadlocks here on pre-Ampere
    # hardware: the main thread parks in futex_do_wait, the fork-based workers sit idle, and
    # the run makes zero progress with load average near nothing - observed hanging at step 0
    # of 96910 for over half an hour. torch itself reports that "speedups for torchdynamo
    # mostly come with GPU Ampere or higher", so on those cards compiling buys nothing and
    # costs a hang. Gate it on the same capability check the precision choice uses.
    compile_model = (
        number_of_files < 0 or number_of_files * number_of_epochs >= compile_threshold
    ) and _is_ampere_or_newer()  # Compiling needs time, but pays off for large datasets
    if compile_model:
        eprint("Compiling model")

    run_id = get_run_id()

    # Sheet2Play change: 8 assumes 8 GB of VRAM. This machine has a 6 GB RTX 4050 Laptop,
    # below homr's documented floor, so the batch is halved and accumulation doubled to hold
    # the same effective batch. Raise SHEET2PLAY_BATCH if running on a larger card.
    batch_size = int(os.environ.get("SHEET2PLAY_BATCH", "4"))

    train_args = TrainingArguments(
        checkpoint_folder,
        torch_compile=compile_model,
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=1e-5 if fine_tune else 1e-4,
        optim="adamw_torch_fused",
        # Sheet2Play change. Upstream fixes this at 8, which silently changes the effective
        # batch whenever SHEET2PLAY_BATCH moves - the halved-batch comment above says the
        # intent is to hold it constant, so derive it instead. Effective batch stays
        # 4 x 8 = 32 per optimizer step, leaving SHEET2PLAY_BATCH as a pure throughput knob
        # rather than something that also alters the optimisation.
        gradient_accumulation_steps=max(
            1, 32 // (batch_size * distribute.get_world_size())
        ),
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size // 2,
        num_train_epochs=number_of_epochs,
        weight_decay=0.05,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        load_best_model_at_end=True,
        metric_for_best_model="eval_accuracy",
        greater_is_better=True,
        report_to=["tensorboard"],
        logging_dir=os.path.join("logs", f"run{run_id}"),
        label_names=label_names,
        bf16=not fp32 and _has_native_bf16(),
        fp16=not fp32 and not _has_native_bf16(),
        dataloader_pin_memory=True,
        dataloader_num_workers=int(os.environ.get("SHEET2PLAY_WORKERS", "12")),
    )

    if fine_tune:
        eprint("Fine tuning model from", config.filepaths.checkpoint)
        model = load_model(config)
        # Sheet2Play change. Upstream's fine-tune path freezes the encoder and decoder and
        # unfreezes only the lift branch - accidentals - which is a leftover from PR #52.
        # The defect we target is rhythm: homr issue #142, where notes vanish from the token
        # stream in multi-voice passages. That is a perception failure, not a projection one,
        # so training a single output head with a frozen encoder cannot fix it; the
        # maintainer says the same in issue #51. Everything therefore stays trainable, and
        # FreezeCallback below holds the encoder backbone for the first epochs so the decoder
        # settles before the encoder starts moving.
    else:
        model = TrOMR(config)

    model_name = "pytorch_model"

    model_destination = os.path.join(
        git_root, "training", "architecture", "transformer", f"{model_name}_{run_id}.pth"
    )

    if os.path.exists(model_destination):
        eprint("Model already exists", model_destination)
        distribute.destroy()
        return

    try:
        callbacks: list[TrainerCallback] = [EarlyStoppingCallback(early_stopping_patience=5)]
        # Sheet2Play change: the backbone warmup now applies to fine-tuning too, since the
        # fine-tune path no longer freezes the encoder outright.
        callbacks.append(FreezeCallback(epochs_to_freeze=2))

        trainer = HomrTrainer(
            model,
            train_args,
            train_dataset=datasets["train"],
            eval_dataset=datasets["validation"],
            callbacks=callbacks,
            distribute=distribute,
        )

        trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    except KeyboardInterrupt:
        eprint("Interrupted")
    if distribute.is_rank0():
        torch.save(model.state_dict(), model_destination)
        eprint(f"Saved model to {model_destination}")
    distribute.barrier()
    distribute.destroy()


if __name__ == "__main__":
    if "--fine" in sys.argv:
        train_transformer(fp32=False, fine_tune=True)
    elif len(sys.argv) > 1:
        raise ValueError("Unknown argument")
    else:
        train_transformer(smoke_test=True)
