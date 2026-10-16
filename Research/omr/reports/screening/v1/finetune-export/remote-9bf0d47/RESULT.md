# Result: conditional pass

The selected epoch-14 checkpoint strictly loaded into the source model and
decoder wrapper. On ONNX Runtime CPU, the existing fp16 encoder and decoder
passed the declared `atol=0.02`, `rtol=0.02` contract for two encoder inputs,
the initial decoder call, and two cache-bearing decoder calls. Complete greedy
generation was deterministic: two source runs and two ONNX CPU runs produced
the same 63-token sequence and terminated at EOS.

The fused decoder does not currently execute through ONNX Runtime CUDA on this
machine: the initial cache step fails in `layers_1_1_MultiHeadAttention` with
CUDA error 9. This is a provider-specific failure, retained verbatim in
`verification-cuda-failure.log`; it does not invalidate the CPU parity result.

`provenance-manifest-v2.json` binds the verified checkpoint to the current ONNX
hashes. It preserves the earlier manifest and calls out its stale decoder hash
rather than replacing it.
