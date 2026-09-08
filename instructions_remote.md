# Fine-tuning homr on the training machine

**Audience: a Claude Code session on the user's second PC.** That machine has an NVIDIA GPU, no
ML environment, and no Linux. This document takes it from nothing to a running fine-tune, and it
is meant to be complete — you should not need to ask the main machine anything to follow it.

Read it end to end before typing the first command. The dataset preparation alone takes hours,
and two of the decisions below (where the repository lives, how much of the machine training is
allowed to take) are painful to change afterwards.

---

## 1. What this job is, and what it is not

Sheet2Play turns sheet music into a piano roll. Its OMR engine is
[homr](https://github.com/liebharc/homr), which reads **pitch** very well (F1 ~0.96) and places
notes **in time** far less well. The failure concentrates in dense multi-voice piano — two
rhythmic layers on one staff — which is most of what the user actually plays and almost none of
what homr was trained on: upstream's PDMX converter caps training data at complexity 2, excluding
dense piano outright.

The job is a **fine-tune from upstream's published run-426 checkpoint**, using a patched training
tree that changes two things:

- `convert_pdmx.py`'s complexity and track ceiling is raised, so dense multi-voice piano enters
  the training mix at all;
- upstream's fine-tune path is fixed. Stock homr freezes the encoder and decoder and unfreezes
  only the *lift* (accidentals) branch — a leftover from an old PR. Rhythm is a perception
  failure, so a frozen encoder cannot fix it. The patch keeps everything trainable and holds the
  encoder backbone for the first two epochs instead.

**What this is not:**

- Not a from-scratch training run. Upstream's own full run is 35 epochs over 190,722 systems;
  this is 15 epochs from an existing checkpoint at lr 1e-5.
- Not a change to the shipped app. Nothing here touches `Bridge/`, `Visualization_engine/` or
  `dist/`. The app keeps running the current engine until a checkpoint is measured and accepted.
- Not a decision you make alone. When the run finishes, report the numbers back — do not swap
  the model into the app from this machine.

### Honest expectations before spending two days

The headroom a fine-tune is competing for has been measured on this project's canary, like for
like on the same 94 systems:

| | onset F1 |
| --- | --- |
| homr today | 0.664 |
| the best any model could reach in this token vocabulary | 0.760 |
| **headroom** | **+0.096** |

That is real but modest, and it survived a check that could have erased it: correcting both sides
for time displacement moved them together (0.748 against 0.843), so the gap is not an artifact of
the scoring metric. Note also that the ceiling is measured on **single staff systems**; a good
part of what goes wrong on the user's real multi-page scores is displacement that no amount of
training inside this vocabulary will fix.

So: worth running, not guaranteed to pay. Report what you measure rather than what you hoped.

---

## 2. Before anything else: check the hardware

In **PowerShell** on Windows:

```powershell
nvidia-smi
```

Record the GPU name, total VRAM, and driver version. Then:

- **No NVIDIA GPU, or the command is not found** → stop here. Nothing below applies, and training
  on CPU is not viable (weeks, not days). Report back that the machine has no usable GPU.
- **GPU present** → note the VRAM. It sets the batch size in §9 and decides whether the run fits
  at all. Under 6 GB, say so before continuing; homr's documented floor is 8 GB and the project
  already runs below it on the main machine at batch 4.

Also check free disk space. **Budget about 60 GB** for the datasets, converted training images and
checkpoints, and it must be free on the Linux side (see §5).

---

## 3. Install WSL2

Requires Windows 10 version 21H2 or later, or Windows 11. In an **Administrator** PowerShell:

```powershell
wsl --install -d Ubuntu-24.04
```

Reboot when it asks. On first launch Ubuntu will ask for a username and password — these are
local to WSL and unrelated to the Windows account. If WSL is already installed but old:

```powershell
wsl --update
wsl --set-default-version 2
```

Confirm you are on version 2, because WSL1 has no GPU passthrough at all:

```powershell
wsl -l -v
```

Everything from here runs **inside the Ubuntu shell**, not PowerShell.

---

## 4. Make the GPU visible inside WSL

The single most common mistake here: **do not install an NVIDIA driver inside WSL.** The Windows
driver provides the GPU to WSL through `/usr/lib/wsl/lib`, and installing a Linux driver on top
breaks it. Update the driver on the **Windows** side only, from GeForce Experience or
nvidia.com.

Verify from the Ubuntu shell:

```bash
nvidia-smi
```

You should see the same GPU you saw in PowerShell. If not, stop and fix it before going further —
everything after this assumes CUDA works.

---

## 5. System packages

```bash
sudo apt update
sudo apt install -y build-essential git curl unzip python3 python3-venv python3-dev \
    librsvg2-bin libjack-jackd2-0 libfuse2t64
```

On Ubuntu 22.04 or 20.04 the last package is `libfuse2` rather than `libfuse2t64`. It is not
optional: the Lieder dataset converter runs MuseScore as an **AppImage**, which needs FUSE, and it
fails confusingly without it. `librsvg2-bin` is needed for score rendering.

Check the Python version — homr requires **>= 3.11 and < 3.16**:

```bash
python3 -V
```

Ubuntu 24.04 ships 3.12, which is fine. If the version is outside that range, install a suitable
one before continuing rather than letting `uv` pick something surprising.

Install `uv`, which is what the setup script prefers for dependency installation:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

---

## 6. Clone the repository — on the Linux filesystem

```bash
cd ~
git clone https://github.com/Artemixss/Sheet2Play.git
cd Sheet2Play
```

**Never put it under `/mnt/c`.** Windows files are reachable from WSL at `/mnt/c/...`, and using
that path is the single likeliest way to ruin this run. Cross-filesystem I/O is the most probable
explanation for the 70 seconds/iteration case reported in
[upstream issue #61](https://github.com/liebharc/homr/issues/61) — at that rate this run would
take 115 days. Keep the repository, the datasets and the checkpoints all under `~` on ext4.

---

## 7. Run the setup script

```bash
bash Research/omr/setup_training.sh
```

It does five things, and each is worth understanding because a failure in any of them is worth
reporting rather than working around:

1. **Checks prerequisites** — git, python3, curl, the Python version range, and `nvidia-smi`.
2. **Clones upstream homr at commit `457e7c6`** into `Research/omr/vendor/homr`. Pinned so every
   machine trains identical code. That commit carries two fixes that are not on PyPI: the
   zero-duration crash fix (upstream #136) and PR #141, which recovers ties from same-pitch slurs.
3. **Applies `Research/omr/patches/homr-training-sheet2play.patch`** — the PDMX complexity ceiling
   and the fine-tune fix described in §1. If it prints `PATCH DOES NOT APPLY`, upstream has moved
   and the patch needs reconciling by hand. **Stop and report that**; do not skip the patch, because
   training stock upstream would fix nothing.
4. **Installs dependencies** with `uv sync --extra training`.
5. **Fetches the run-426 checkpoint** (`pytorch_model_426-b6fd208...`) and extracts the `.pth`
   into `training/architecture/transformer/`. This is what the fine-tune starts from — without it
   there is nothing to fine-tune.

Then it prints a **GPU capability report**. Read it carefully:

- **`bf16 supported -> default settings are fine`** — compute capability 8.0 or higher (Ampere and
  newer: RTX 30xx, 40xx, 50xx, A-series). Nothing to do.
- **`bf16 NOT supported on this card (pre-Ampere)`** — a Turing or older card (RTX 20xx, GTX 16xx).
  The trainer defaults to bf16 and will fail or misbehave. You must pass `fp32=True` to every
  training call in §9 and §10, or change `bf16` to `fp16` in `TrainingArguments`.
- The **VRAM line** suggests a starting batch size. §9 turns that into the actual command.

---

## 8. Keep the machine usable while it trains

**Do this before starting the long run, not after.** The user keeps using this PC while it trains
— browsing, Twitter, video — and a run that makes the desktop unusable for two days is a failed
run even if the model comes out fine. Discuss the numbers below with them rather than picking
silently; they depend on this machine's specs.

There are four separate levers, and every one of them trades training speed for responsiveness.
Say which you have set and what it costs.

**VRAM — `SHEET2PLAY_VRAM_FRACTION`.** The patch caps training at 90% of the card by default,
leaving the rest for the desktop; a browser with hardware acceleration on can hold most of a
gigabyte of VRAM. `0.80` is a reasonable setting on a larger card.

```bash
export SHEET2PLAY_VRAM_FRACTION=0.80
```

**This does not reduce what training needs.** It makes an over-large batch fail fast and loudly
instead of quietly starving the rest of the system. So if you lower the fraction, lower
`SHEET2PLAY_BATCH` with it — that is still the lever that decides whether the run fits at all.

**Host RAM and CPU — `.wslconfig`.** Usually the bigger win for how responsive Windows *feels*.
An uncapped WSL2 takes up to half the host's RAM and all its cores, and homr's data loading is
CPU-hungry (upstream asks for something like an i5-11400). Create
`C:\Users\<name>\.wslconfig` on the **Windows** side:

```ini
[wsl2]
memory=16GB
processors=6
```

Set both below the machine's totals — leave at least 4 CPU threads and a quarter of RAM for
Windows. Apply with `wsl --shutdown` in PowerShell, then reopen Ubuntu.

**Dataloader workers.** Fewer workers means less CPU contention and a slower run. Only reach for
this if the desktop still stutters after the `.wslconfig` cap.

**What stays fine regardless.** Video *decode* runs on NVDEC, a separate engine from the shader
cores training saturates, so watching video is largely unaffected. Web browsing and scrolling are
fine. Games and anything else GPU-heavy are not — those will fight the run for the card.

---

## 9. Datasets, then the smoke test

### The datasets build themselves, and it takes hours

The first training call converts all five corpora — lieder, grandstaff, primus, pdmx,
musetrainer — into the token format training needs. PDMX downloads itself from Zenodo
(`PDMX.csv` ~214 MB and `mxl.tar.gz` ~1.8 GB); the others download too. Expect **several hours
before a single training step runs**, and roughly 12 GB of converted data.

Two things that look like errors and are not:

- The Lieder converter prints something like `Processed 1460/1467 files, skipped 350 files`.
  Upstream documents that as expected.
- Conversion is resumable. If it dies partway, re-running continues rather than restarting.

If PDMX's download fails, place the two files manually under
`Research/omr/vendor/homr/datasets/pdmx/` and re-run — `pdf.tar.gz` from the same Zenodo record is
**not** needed, homr renders its own images.

### Smoke test, and the go/no-go gate

```bash
cd ~/Sheet2Play/Research/omr/vendor/homr
python3 -c "from training.transformer.train import train_transformer; train_transformer(smoke_test=True)"
```

Watch **seconds per iteration** for the first fifteen minutes. This is the most important number
in the whole document:

- **under ~5 s/it** — proceed.
- **5 to 10 s/it** — usable but slow; report the number and the projected wall time before
  committing to the full run.
- **over ~10 s/it** — **stop.** Something is wrong, and the usual cause is the repository sitting
  on `/mnt/c` (see §6). Renting a cloud GPU is cheaper than waiting; the project's budget for that
  is roughly $10, and an RTX 3090 on a community cloud is about $0.40/hour.

The progress bar covers the **whole run**, not one epoch — do not read its estimate as an epoch
time.

---

## 10. Run the fine-tune

```bash
cd ~/Sheet2Play/Research/omr/vendor/homr
SHEET2PLAY_BATCH=<see table> SHEET2PLAY_VRAM_FRACTION=0.80 \
  python3 -c "from training.transformer.train import train_transformer; train_transformer(fine_tune=True)"
```

Add `fp32=True` to the call if §7 said bf16 is unsupported.

| VRAM | `SHEET2PLAY_BATCH` | note |
| --- | --- | --- |
| 6 GB | 4 | below homr's documented floor; what the main machine uses |
| 8 GB | 8 | upstream's stated minimum |
| 16 GB | 18 | upstream default |
| 24 GB | 32 | |

`gradient_accumulation_steps` moves the opposite way to keep the effective batch constant; the
patch already sets it to 8 for the batch-4 case. If you change the batch a lot, adjust it and say
that you did.

What the run does: 15 epochs at learning rate 1e-5, early stopping with patience 5, and the
encoder backbone frozen for the first 2 epochs before everything becomes trainable. Expect
roughly **two days**.

Interrupting with Ctrl-C is safe — the trainer catches it and still saves the model.

---

## 11. What to watch while it runs

- **Rare-token collapse is the likeliest failure.** A contributor in upstream's tracker took their
  symbol error rate from 26% to **132%** by adding rare tokens. If SER climbs rather than falls,
  stop and report; do not let it run for two days out of hope.
- **Early stopping** triggers after 5 evaluations without improvement. If it fires early, that is
  a result worth reporting, not a bug to work around.
- **Checkpoints** land in `~/Sheet2Play/Research/omr/vendor/homr/current_training/`. The final
  model is written to
  `training/architecture/transformer/pytorch_model_<run_id>.pth`.
- **Keep the log.** Seconds/iteration, per-epoch loss and SER are what make the run interpretable
  afterwards.

**This project's rule on judging a model, from its CLAUDE.md, applies to whatever you report:**
never select a checkpoint by maximising a single metric. Report the full picture, check for
degenerate all-one-class behaviour, and compare against the trivial baseline — here, the existing
run-426 model — before calling anything an improvement.

---

## 12. When it finishes

Export the ONNX the app actually loads:

```bash
cd ~/Sheet2Play/Research/omr/vendor/homr
python3 training/onnx/main.py --tromr
```

Then report back to the main machine. **Do not swap the model into the app from here** — the
comparison against the current engine happens on the machine that has the user's library.

What to send, and what to say:

- the `.pth` and the exported ONNX files, with their sizes;
- **seconds per iteration** from the smoke test and from the real run;
- **epochs actually completed**, and whether early stopping fired;
- the **symbol error rate** at the start and end, and the smoke-test number;
- any **skipped-file counts** the dataset converters printed;
- what you set for `SHEET2PLAY_BATCH`, `SHEET2PLAY_VRAM_FRACTION`, `.wslconfig`, and whether the
  machine stayed usable;
- anything that failed, was worked around, or looked wrong.

The main machine will score the checkpoint on the OLiMPiC canary and on the user's real library
before anything reaches the app.

---

## 13. Traps, collected

| Trap | Symptom | Fix |
| --- | --- | --- |
| Repository under `/mnt/c` | 10–70 s/iteration | Move it to `~` on ext4 and re-run the smoke test |
| NVIDIA driver installed inside WSL | CUDA stops working | Never do it; the Windows driver provides the GPU |
| WSL1 instead of WSL2 | No GPU at all | `wsl --set-version Ubuntu-24.04 2` |
| Missing `libfuse2` | Lieder converter fails on the MuseScore AppImage | Install `libfuse2t64` (24.04) or `libfuse2` |
| Pre-Ampere card | Training fails or misbehaves silently | Pass `fp32=True`, or switch bf16 to fp16 |
| Patch does not apply | `PATCH DOES NOT APPLY` from the setup script | Stop and report — do not train stock upstream |
| Both OpenCV distributions installed | Errors naming GStreamer, unrelated to the real cause | Exactly one of `opencv-python` / `opencv-python-headless` |
| Batch too large for the capped VRAM | Immediate OOM | Lower `SHEET2PLAY_BATCH`, not just the VRAM fraction |
| Reading the progress bar as one epoch | Wildly wrong time estimates | It covers the whole run |

---

## 14. If you are asked to do something else

This machine exists for the long training run. Inference experiments, engine comparisons and
anything touching the user's library belong on the main machine, which has the library and the
evaluation harness. If a request here would change the shipped app, say so and hand it back.
