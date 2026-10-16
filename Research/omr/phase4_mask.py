"""Research-only recurrent mask intervention on identical padded input bytes."""
from __future__ import annotations

from contextlib import contextmanager


def valid_steps(width: int, timestep: int) -> int:
    if type(width) is not int or type(timestep) is not int or min(width, timestep) <= 0:
        raise ValueError("Width and timestep must be positive integers")
    return (width + timestep - 1) // timestep


@contextmanager
def original_width_mask(model, width: int, timestep: int):
    import tensorflow as tf
    steps = valid_steps(width, timestep)
    layers = [layer for layer in model.encoder.layers if "sequence_mask" in layer.name]
    if len(layers) != 1:
        raise ValueError("Expected exactly one upstream recurrent sequence mask")
    layer, evidence = layers[0], []
    original = layer.call

    def call(lengths, *args, **kwargs):
        if not tf.executing_eagerly():
            raise RuntimeError("Research mask intervention requires eager inference")
        padded_steps = tf.reduce_max(lengths)
        if int(padded_steps.numpy()) < steps:
            raise ValueError("Valid width exceeds padded input")
        mask = tf.sequence_mask(tf.fill(tf.shape(lengths), tf.cast(steps, lengths.dtype)), maxlen=padded_steps)
        evidence.append({"valid_steps": steps, "padded_steps": int(padded_steps.numpy()),
                         "true_count": int(tf.reduce_sum(tf.cast(mask, tf.int32)).numpy())})
        return mask

    layer.call = call
    try:
        yield evidence
        if not evidence:
            raise RuntimeError("Mask intervention was not executed")
    finally:
        layer.call = original
