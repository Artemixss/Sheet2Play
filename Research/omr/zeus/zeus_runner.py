import sys
import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any

# Ensure we don't spam TF logs
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

# Set up paths to the cloned Zeus source
_HERE = Path(__file__).resolve().parent
_SOURCE_ROOT = _HERE / "source"
_ZEUS_DIR = _SOURCE_ROOT / "zeus"
if str(_ZEUS_DIR) not in sys.path:
    sys.path.insert(0, str(_ZEUS_DIR))
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

import numpy as np
import tensorflow as tf

# From ufal/olimpic-icdar24 repository
from zeus import Model
from app.linearization.Delinearizer import Delinearizer
import music21

import argparse

class FakeDataset:
    def __init__(self, tags, tags_map):
        self.tags = tags
        self.tags_map = tags_map

class ZeusRunner:
    def __init__(self, model_dir: str | Path):
        self.model_dir = Path(model_dir)
        
        # 1. Load tags
        tags_file = self.model_dir / "tags.txt"
        self.tags = tags_file.read_text("utf-8").splitlines()
        self.tags_map = {tag: i for i, tag in enumerate(self.tags)}
        
        # 2. Load options
        options_file = self.model_dir / "options.json"
        config_dict = {}
        if options_file.exists():
            config_dict = json.loads(options_file.read_text("utf-8"))
        
        # We need all the defaults from zeus.py parser
        from zeus import parser
        self.args = parser.parse_args([])
        for k, v in config_dict.items():
            setattr(self.args, k, v)
            
        # Ensure we have dummy values for training-related args that Model init expects
        self.args.train_batches = 1
        if not hasattr(self.args, "max_predict_length"):
            self.args.max_predict_length = 1000
        if not hasattr(self.args, "height"):
            self.args.height = 192

        # 3. Build model
        print("Building Zeus model...", flush=True)
        fake_ds = FakeDataset(self.tags, self.tags_map)
        
        strategy = tf.distribute.MirroredStrategy() if len(tf.config.list_physical_devices("GPU")) > 1 else None
        if strategy:
            with strategy.scope():
                self.model = Model(self.args, fake_ds)
        else:
            self.model = Model(self.args, fake_ds)
            
        # 4. Initialize graph and load weights
        print("Loading weights...", flush=True)
        # Dummy forward pass to build weights
        dummy_input = tf.RaggedTensor.from_tensor(
            tf.ones([1, self.args.height, 128, 1], dtype=tf.float32), 
            ragged_rank=2
        )
        self.model.decoder_inference(self.model.encoder(dummy_input), 1)
        self.model.built = True
        
        # Load weights.h5
        weights_path = self.model_dir / "weights.h5"
        self.model.load_weights(str(weights_path))
        print("Zeus model loaded successfully.", flush=True)

    def predict_image(self, image_path: Path | str) -> str:
        """Run Zeus on a single system image and return LMX string."""
        image_bytes = tf.io.read_file(str(image_path))
        image = tf.image.decode_image(image_bytes, channels=1, expand_animations=False)
        image = tf.image.convert_image_dtype(image, tf.float32)
        
        # Resize to fixed height (e.g. 192), preserving aspect ratio
        image = tf.image.resize(
            image, 
            size=[self.args.height, tf.int32.max], 
            preserve_aspect_ratio=True, 
            antialias=True
        )
        
        # Bucket the width to the nearest 500 to prevent TF retracing every new width
        width = tf.shape(image)[1]
        padded_width = tf.cast(tf.math.ceil(tf.cast(width, tf.float32) / 500.0) * 500, tf.int32)
        pad_amount = padded_width - width
        image = tf.pad(image, [[0, 0], [0, pad_amount], [0, 0]], constant_values=1.0)
        
        # Model expects [batch, height, width, channels] as RaggedTensor
        batched = tf.expand_dims(image, 0) # [1, height, width, 1]
        batched = tf.RaggedTensor.from_tensor(batched, ragged_rank=2)
        
        # Run inference
        predicted_tokens = self.model.predict_step(batched)
        
        # Convert token IDs back to strings
        tags = predicted_tokens[0].numpy()
        predicted_lmx = " ".join(self.tags[tag] for tag in tags if tag > 0)
        
        return predicted_lmx

from app.symbolic.part_to_score import part_to_score
import xml.etree.ElementTree as ET

def lmx_to_musicxml(lmx_string: str, output_path: Path | str) -> None:
    """Convert LMX string to MusicXML using OLiMPiC Delinearizer."""
    delinearizer = Delinearizer()
    delinearizer.process_text(lmx_string)
    score_etree = part_to_score(delinearizer.part_element)
    
    # Write to file with XML declaration
    score_etree.write(
        str(output_path),
        encoding="utf-8",
        xml_declaration=True
    )
