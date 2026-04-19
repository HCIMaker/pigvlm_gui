# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Windows-side staging area for preparing **DeepLabCut (DLC) keypoint-tracking datasets** for pig behavior analysis (sow and piglets). The actual model training happens on a Linux server; this repo owns everything *up to* producing the `CollectedData_<scorer>.csv` that DLC's `convertcsv2h5` consumes.

Read `must_know.md` first — it is the authoritative spec for the DLC CSV format (3-row header for single-animal, 4-row for multi-animal, how occluded keypoints are represented, folder/filename conventions, and the server-side post-processing commands). Do not re-derive those rules from code.

## The pipeline (end-to-end)

```
raw video (.mp4)                        server (D:\ or remote)
    │
    │  short_video_extraction.ipynb    (moviepy; hms_to_secs → subclip)
    ▼
clip.mp4  →  pre-extracted frames: img<NNN>.png  in a folder named after the clip
    │
    │  SLEAP GUI (external) — produces .slp files under sleap_label/single/ or sleap_label/mutli/
    ▼
.slp file
    │
    │  sleap_to_dlc_multi.py  (or sleap_to_dlc.py for single-only)
    │    - copies frames into <DLC_PROJECT>/labeled-data/<clip_name>/
    │    - writes CollectedData_<scorer>.csv beside them
    │    - validates every CSV path resolves to a real image
    ▼
<DLC_PROJECT>/labeled-data/<clip_name>/
    ├── img*.png
    └── CollectedData_jiale.csv
    │
    │  (upload to server, then in `dlc` conda env:)
    │  deeplabcut.convertcsv2h5(config, scorer="jiale")
    │  python 2_create_project/csv_to_h5_official.py      ← server-side
    │  python 2_create_project/check_labels_from_sleap.py ← server-side
    │  python 3_training/create_training_dataset.py --project sow
    │  CUDA_VISIBLE_DEVICES=0 python 3_training/train.py  --project sow
    ▼
trained DLC model
```

The `2_create_project/` and `3_training/` scripts are **not in this repo** — they live on the server at `~/Jiale_Research/PigVLM/PigFarmDataProcessing/deeplabcut/`. Do not try to run them locally.

## DLC projects in this repo

Three DLC-layout directories (`config.yaml` + `labeled-data/` + `dlc-models/` + `training-datasets/` + `videos/`):

| Project | Mode | Bodyparts | Individuals |
|---|---|---|---|
| `PigFarm_Sow-jiale-2026-02-08/` | single-animal (`multianimalproject: false`) | `left_ear, right_ear, torso, hip` | — |
| `PigFarm_Multi-jiale-2026-02-08/` | multi-animal (`multianimalproject: true`, `bodyparts: MULTI!`) | `multianimalbodyparts: head, torso, hip` | `sow, piglet1..piglet12` (13 total) |
| `PigFarm_Sow_Test-jiale-2026-04-17/` | single-animal test project | same as Sow | — |

**Path gotcha in `config.yaml`:** `project_path` and `video_sets` keys use Linux server paths (e.g. `/home/jiale/Jiale_Research/...`). The `PigFarm_Sow` config has a Windows `project_path` line with the Linux one commented out — this is intentional so the conversion scripts can resolve paths locally. When adding new projects, keep both forms handy and do not let a Windows-only `project_path` leak back to the server.

## The conversion scripts (what to edit, when)

- `sleap_to_dlc_multi.py` — **the canonical script.** Handles both single- and multi-animal via the `MULTI_ANIMAL` toggle. Edit `SLP_FILE`, `SCORER`, `MULTI_ANIMAL`, and the `SOW_DLC_PROJECT` / `MULTI_DLC_PROJECT` constants at the top.
- `sleap_to_dlc.py` — single-animal only, kept as a simpler reference.
- `sleap_to_dlc.ipynb` / `sleap_to_dlc_multi.ipynb` — interactive versions of the above; the `.py` files are the ones to run non-interactively.
- `short_video_extraction.ipynb` — trims a long surveillance clip down to a labeling-sized window. Edit `input_video`, `output_video`, `start_time`, `end_time`.

### Multi-animal subtlety — trackless SLEAP files

SLEAP `.slp` files from image-folder projects usually have **no tracks** (`labels.tracks == []`). In that case the converter falls back to **instance-order mapping**: instance 0 in each frame → `individuals[0]` (sow), instance 1 → `individuals[1]` (piglet1), etc. This means the human labeler **must label the sow first in every frame, then piglets in the same order throughout**. If the SLEAP file *does* have tracks, `TRACK_NAME_MAP` or auto-detection (exact name match first, then ordered fill) decides the mapping — see `build_track_mapping()`.

For a single labeled frame the converter only writes the individuals that were actually labeled; missing ones get NaN via `df.reindex(columns=all_columns)`.

### Frame filename handling

The converter preserves `img<NNN>.png` filenames as-is. Other patterns (`frame_000050.png`, `000050.png`, etc.) are renamed to `img<NNNN>.png` using `parse_frame_index()` (first integer in the stem, zero-padded to 4). The CSV row index uses the relative path `labeled-data/<folder>/<img_name>`.

## Running conversions

No virtualenv or build system — scripts are run directly. Required packages:

```bash
pip install sleap-io pandas numpy pyyaml moviepy
python sleap_to_dlc_multi.py   # edit the top-of-file configuration first
```

The script ends with a path-validation pass: every row in the generated CSV is resolved against the filesystem, and the script exits non-zero if any image is missing. Treat that failure as "DLC will crash later" — fix the image placement, do not bypass the check.

## Naming & typos to be aware of

- The SLEAP subdirectory is spelled `sleap_label/mutli/` (not `multi/`) — don't "fix" it without also updating the hardcoded paths in the multi-animal notebook.
- Clip/folder names follow `ch07_Crate08_<start>_<end>_clip_<HHhMMmSSs>` — this exact string appears in the SLEAP `.slp`, the `labeled-data/` subfolder, the CSV row index, and `video_sets` in `config.yaml`. They must all match.

## Do not

- Do not mock or synthesize the reference CSVs — use the real ones on the server (see `must_know.md` §8) to verify format.
- Do not run `deeplabcut.create_new_project` or any training step locally — this machine is Windows without the DLC conda env. Those are server operations.
- Do not round keypoint coordinates to integers. DLC expects sub-pixel floats.
