# Epoch-14 verification bundle

This small bundle supports local reproduction and review of the epoch-14 ONNX
parity check. `source_bundle/` contains only the inspected public HOMR source,
the exact local code patch, configuration/vocabulary code, and four tokenizer
JSON files. The command, provider failure evidence, CPU parity report, and
provenance manifest are adjacent to it.

It deliberately excludes model/checkpoint weights, ONNX binaries, optimizer
state, datasets, credentials, and music fixtures. The public development image
used by the check remains in the upstream-like local Sheet2Play test fixture and
is identified by hash and crop metadata in `verification.json`; it is not copied.
