# Sheet2Play - OMR Upgrade Master Context

## Project Current State & Context
Sheet2Play is a C# (Raylib) desktop application that visualizes sheet music as falling piano notes (like Synthesia). It features an integrated Python bridge (`bridge.py`) that handles Optical Music Recognition (OMR) to convert PDF sheet music into playable MIDI/MusicXML data. 

**Recent Architecture Changes:**
- **UI:** A 3-column landing page (PDFs, Cache, Direct MIDI).
- **Direct Playback:** Native `.mid` and `.mxl` playback bypasses the OMR pipeline entirely for 100% accuracy and speed.
- **OMR Engines:** We have historically used `HOMR` (accurate but sometimes lacks rhythmic precision) and `Zeus` (a YOLO-based model). We recently eradicated `Transcoda` due to extreme instability and memory leaks.
- **The Zeus Problem:** Zeus's YOLO architecture limits its semantic understanding of musical sequences. It fails to accurately calculate global rhythmic beats (`start_beat`) leading to near-zero onset accuracy compared to commercial solutions like Scan2Notes.

---

## The Master Plan: Project "Next-Gen OMR"

This document outlines the strategic roadmap for replacing Zeus with a state-of-the-art (SOTA) Optical Music Recognition engine, and establishing a fine-tuning pipeline if necessary.

### Phase 1: Academic Literature & SOTA Model Search
YOLO-based object detection is no longer sufficient for complex OMR. We need models that understand *sequences* (e.g., Vision Transformers, Sequence-to-Sequence models, TrOMR).
- **Objective:** Run a deep literature search (arXiv, bioRxiv, PapersWithCode) for OMR models released between 2023–2026.
- **Criteria:**
  - Must be open-source with available model weights.
  - Must utilize a modern architecture (Transformers/Attention) rather than raw bounding-box detection.
  - Must output semantic music representations (MusicXML, Kern, LilyPond, or MIDI).

### Phase 2: Engine Integration & Evaluation
Once a candidate engine is found, we will wrap it in our existing `bridge.py` architecture.
- **Objective:** Hook the new model into the `OmrEngine` enum in the C# frontend and `bridge.py` backend.
- **Outcome 2.1 (The Golden Path):** The model works out of the box with high accuracy. We deprecate Zeus and adopt it as the new standard.
- **Outcome 2.2 (The Flawed Path):** The model's architecture is brilliant, but its accuracy on complex piano scores is lacking. We proceed to Phase 3 for custom Fine-Tuning.

### Phase 3: The "MuseScore" Ground Truth Dataset
The biggest bottleneck in OMR is the lack of aligned, high-quality (PDF-to-MIDI) ground-truth datasets. We will solve this by automating MuseScore.
- **Objective:** Build an automated dataset generator.
- **Execution:**
  1. Utilize the Microsoft Edge extension "Music Score Downloader".
  2. Write a Python automation script (e.g., using Playwright or Selenium) to automatically iterate through MuseScore URLs.
  3. Download both the visual `PDF` and the exact corresponding `MIDI/MusicXML` for thousands of piano pieces.
- **Result:** A proprietary dataset of 10,000+ perfect, human-verified sheet music ground truths.

### Phase 4: Model Fine-Tuning
- **Objective:** Take the high-potential architecture from Phase 1 and fine-tune it using the dataset generated in Phase 3.
- **Execution:** 
  - Since we have perfectly aligned PDF to MusicXML/MIDI data, we can run a supervised fine-tuning pipeline on the model, forcing it to learn the exact rhythmic spacing and semantic relationships specific to dense piano scores.
  - This bridges the gap between open-source academic models and commercial-grade products like Scan2Notes.

---
## Notes for Future AI Assistants
- **Language/Stack:** C# (.NET 9) for frontend UI, Python 3 for the backend bridge and ML evaluation.
- **Important:** Do NOT try to resurrect Transcoda. It was removed for systemic architectural failures.
- **Current Bridge Location:** `Bridge/bridge.py` manages the python virtual environments dynamically. Any new OMR model should be given its own isolated virtual environment to prevent dependency conflicts with HOMR.
