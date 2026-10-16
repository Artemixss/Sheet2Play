# Epoch-14 local parity run

This directory contains offline verification evidence only. It does not contain a
checkpoint, ONNX graph, dataset, private music, optimizer state, or credentials.

Preflight command, run before verification:

```powershell
wsl -d Ubuntu-24.04 -- bash -c "ps -eo pid,ppid,stat,etime,cmd | grep -E '[r]un_finetune|[t]rain_transformer|[p]ython.*onnx' || true"
```

Observed preflight result: no matching process.

Verification command and working directory:

```powershell
wsl -d Ubuntu-24.04 -- bash -c "cd /root/Sheet2Play/Research/omr/vendor/homr && .venv/bin/python /mnt/c/Users/PC1/dev/omr-training/reports/finetune-export-verification-v1/verify_epoch14_parity.py"
```

Inputs recorded by the script: the epoch-14 safetensors checkpoint; the existing
fp16 encoder and decoder ONNX files; and an in-memory crop of the public HOMR
test fixture `Research/omr/tests/fixtures/transcoda-baseline/baseline-piano.png`.
The input fixture is not copied into this directory.

Tolerance declared before execution: `atol=0.02`, `rtol=0.02`.

The initial `CUDAExecutionProvider` attempt is retained as
`verification-cuda-failure.log`: it reached the fused decoder and failed at
`layers_1_1_MultiHeadAttention` with CUDA error 9. The CPU-provider parity
retry uses the same inputs and command with `HOMR_VERIFY_ORT_PROVIDER=cpu`.
