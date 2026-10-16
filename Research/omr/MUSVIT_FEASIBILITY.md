# MuSViT recognition feasibility — Phase 2R, 2026-09-24

**Disposition: requires training—not evaluated.** No MuSViT-based recognition checkpoint with a verified decoder, vocabulary, and MusicXML conversion path was found in the official [MuSViT model collection](https://huggingface.co/collections/PRAIG/musvit) or the [official source tree](https://github.com/OMR-PRAIG-UA-ES/MuSViT). This does not claim that no private or third-party checkpoint exists. No OMR accuracy score is assigned, and no training was started.

## Verified intake

- The [base encoder](https://huggingface.co/PRAIG/musvit) at revision `02a42371b861a68ba99e409480c67e19ad6ca2d2` is a ViT/MAE pretraining model, not a symbolic decoder. The official collection also lists the light encoder at `380452835e7fd64650cdde4350040b999f9dd9f9`. Their license is CC BY-NC-SA 4.0.
- The configured Hugging Face account cannot download even the base encoder's small `config.json`: the pinned-revision access check returned `GatedRepoError` / HTTP 403 and says access must be requested. No weights were downloaded.
- The official source at `96bab6296bde65caebce00e5b014a68dba0404ab` provides full-page OMR training code with an SMT-style autoregressive decoder and dataset-specific BeKern vocabulary arrays (`FP_GrandStaff`, `Mozarteum`, `Polish_Scores`), plus a separate staff-level BiLSTM/CTC training path. The [vocabulary utility](https://github.com/OMR-PRAIG-UA-ES/MuSViT/blob/main/experiments/full_page_omr/utils/vocab_utils.py) generates token maps from training sequences; the [Polish Scores configuration](https://github.com/OMR-PRAIG-UA-ES/MuSViT/blob/main/experiments/full_page_omr/config/Polish_Scores/finetuning.json) specifies BeKern tokenization. The official repository tree contains no released `.pt`, `.ckpt`, or `.safetensors` recognition weights. A local filtered clone was stopped after stalling; these findings use the official remote tree and files, not an incomplete local checkout.
- BeKern-to-MusicXML compatibility with the frozen Sheet2Play normalizer has **not** been established. Existing vocabulary arrays do not by themselves identify a runnable decoder or a faithful converter.

## Separate future training proposal, not authorized by Phase 2R

1. Obtain explicit access to the encoder and pin its file hashes. Choose one decoder and vocabulary for the intended page or staff granularity; save architecture, tokenizer, and every checkpoint hash together. Do not treat encoder-only weights as an OMR candidate.
2. Train on faithful BeKern labels with composition-disjoint development and test partitions. Keep the frozen SMB/OLiMPiC evaluation items out of training and selection. Include Sheet2Play's own dataset generator alongside any public corpus, and audit generated notation features and rendering provenance.
3. Implement and test BeKern-to-MusicXML conversion and shared normalization for ties, tuplets, voices, meter changes, multi-system/page ordering, malformed output, and omissions. Reject silent corruption before any benchmark.
4. Estimate local and cloud time, storage, and transfer before a separate approval. Keep the current comparison's $10 total cloud cap and private-file locality constraints unless the user explicitly changes them. Only a verified trained recognition checkpoint could enter a later comparison configuration.
