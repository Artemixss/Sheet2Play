# LEGATO Phase 2R readiness — 2026-09-24

> **2026-09-25 correction:** The 21.3 GB external repository size and model-card
> 20 GB+ figure do not establish LEGATO's actual inference weight footprint.
> Pinned `LegatoModel.from_pretrained` first loads the dedicated decoder checkpoint
> (429,478,304-byte safetensors file), then calls
> `MllamaVisionModel.from_pretrained` for the external vision encoder—not the full
> Llama language model. Upstream `scripts/inference.py` moves the combined model
> to the device before its optional `--fp16` cast; default inference is therefore
> not a demonstrated FP16 path. A meta-device parameter count for the installed
> Transformers *default* Mllama vision configuration (1280 hidden, 32 local and
> 8 global layers) is 836,288,019 parameters, or 1.56 GiB in FP16 and 3.12 GiB
> in FP32 for vision weights alone. This is a scenario estimate, **not** the
> verified pinned encoder's exact parameter count or peak VRAM. Add the decoder,
> activations, generation cache, framework overhead, and possible load/cast
> transients. A 6 GB fit is neither proven nor ruled out. No weight download,
> cloud proposal, or recognition attempt followed this static assessment.

**Status: local inference unavailable; converter smoke passed.** This is not an accuracy score. A full end-to-end development inference was not represented as successful.

- The official [source](https://github.com/guang-yng/legato) is cloned cleanly at `179c228d3d5f67113cf739b44891b3abe046f1dc`. `utils/convert.py` and `utils/abc2xml.py` are present. MuseScore 4 is installed.
- The dedicated [checkpoint](https://huggingface.co/guangyangmusic/legato) is pinned at `2d07c5d0e73186f2c0b12e35ea187bbc30dec18c`. Its `config.json` was accessed and names `meta-llama/Llama-3.2-11B-Vision` as the external frozen vision encoder; `model.safetensors` is 429,478,304 bytes. These weights were **not** downloaded or hashed locally, so only remote metadata and the config are verified.
- The external [Meta encoder repository](https://huggingface.co/meta-llama/Llama-3.2-11B-Vision) is accessible for its small configuration but publishes 21,286,002,142 bytes of sharded safetensors. The [LEGATO card](https://huggingface.co/guangyangmusic/legato) specifies roughly 20 GB+ GPU memory at full precision and recommends FP16 to reduce usage without giving a 6 GB guarantee. This computer has 6 GB VRAM and 15.2 GB RAM. The exact pinned model cannot be responsibly claimed runnable locally without a substantial download and memory test; no cloud instance was rented and no private files were transferred.
- The real upstream ABC cleanup/`abc2xml.py`/MuseScore path was run on [legato-native-basic.json](tests/fixtures/legato-native-basic.json). It produced a nonempty MusicXML document that shared normalization accepted with four notes and zero warnings. This checks conversion plumbing only. The initial sandboxed attempt failed to read the installed `pyparsing` file; the verified path succeeded with an escalated local run. More complex LEGATO-native outputs still require a model-generated development smoke before benchmark eligibility.

The repository's historical Phase-2 `LEGATO unavailable` result therefore remains accurate for recognition. Do not substitute `legato-small` or a newer checkpoint under the pinned candidate identity, and do not give a zero or fabricated accuracy score to this unavailable configuration.
