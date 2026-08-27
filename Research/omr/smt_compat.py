"""Make the Sheet Music Transformer load under current transformers.

SMTConfig.__init__ never calls PretrainedConfig.__init__, so the instance is
missing every attribute the base class normally sets. Older transformers did not
look at them; 4.57 does, and weight tying fails with:

    AttributeError: 'SMTConfig' object has no attribute 'is_encoder_decoder'

Rather than edit the vendored upstream repo, this patches the config class so the
framework defaults are populated first and SMT's own fields are applied on top.
Import this module before loading the model.
"""
from __future__ import annotations

from transformers import PretrainedConfig

from smt_model.configuration_smt import SMTConfig

_original_init = SMTConfig.__init__
_PATCH_FLAG = "_sheet2play_compat"


def _patched_init(self, *args, **kwargs):
    # Populate the base-class defaults the upstream __init__ skips.
    PretrainedConfig.__init__(self)
    _original_init(self, *args, **kwargs)
    # SMT keeps its decoder embedding and output projection separate, so weight
    # tying must stay off; leaving the default True makes transformers tie them.
    self.is_encoder_decoder = False
    self.tie_word_embeddings = False
    self.tie_encoder_decoder = False


def apply() -> None:
    if not getattr(SMTConfig, _PATCH_FLAG, False):
        SMTConfig.__init__ = _patched_init
        setattr(SMTConfig, _PATCH_FLAG, True)


apply()
