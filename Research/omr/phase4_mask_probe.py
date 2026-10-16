from pathlib import Path
import sys
from zeus_attribution_prepare import HERE, configure_cpu

configure_cpu()
sys.path[:0] = [str(HERE / "zeus"), str(HERE / "zeus/source")]
from zeus_runner import ZeusRunner
from phase4_mask import original_width_mask
import tensorflow as tf

runner = ZeusRunner(HERE / "zeus/weights/zeus-olimpic-1.0-2024-02-12.model")
data = tf.RaggedTensor.from_tensor(tf.ones([1, runner.args.height, 500, 1]), ragged_rank=2)
print([(layer.name, type(layer).__name__) for layer in runner.model.encoder.layers if "mask" in layer.name], flush=True)
with original_width_mask(runner.model, 320, runner.args.timestep_width) as evidence:
    runner.model.encoder(data, training=False)
print(evidence, flush=True)
