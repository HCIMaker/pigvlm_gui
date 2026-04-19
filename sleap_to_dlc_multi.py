"""Convert SLEAP .slp labels to DeepLabCut CollectedData CSV.

Reads a SLEAP labels file (labeled from an image folder), copies frames
into DLC's labeled-data/ directory with proper naming, and generates
the CollectedData_<scorer>.csv that DLC expects.

Supports both single-animal and multi-animal projects:
  - Single-animal: 3-level CSV header (scorer, bodyparts, coords)
  - Multi-animal:  4-level CSV header (scorer, individuals, bodyparts, coords)

After running this script, finalize with:
    deeplabcut.convertcsv2h5(config_path, scorer="jiale")

Usage:
    pip install sleap-io pandas pyyaml
    python sleap_to_dlc.py
"""

import sleap_io as sio
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
import shutil
import re
import yaml

# ── Configuration ─────────────────────────────────────────────────────
SLP_FILE = Path("path/to/your/labels.slp")  # ← Update this
SCORER = "jiale"  # Must match config.yaml scorer field

# ── Mode toggle ───────────────────────────────────────────────────────
MULTI_ANIMAL = False  # Set True for multi-animal project

# Single-animal project path
SOW_DLC_PROJECT = Path("path/to/PigFarm_Sow-jiale-2026-02-08")  # ← Update this
# Multi-animal project path
MULTI_DLC_PROJECT = Path("path/to/PigFarm_Multi-jiale-2026-02-08")  # ← Update this

DLC_PROJECT = MULTI_DLC_PROJECT if MULTI_ANIMAL else SOW_DLC_PROJECT

# If SLEAP's image folder name doesn't match the DLC labeled-data subdir,
# provide an explicit mapping: {"sleap_folder_name": "dlc_video_name"}
# Leave empty to auto-detect from folder names.
FOLDER_NAME_MAP = {}

# ── Multi-animal: SLEAP track → DLC individual mapping ───────────────
# Map SLEAP track names to DLC individual names from config.yaml.
# Example: {"Track 0": "sow", "Track 1": "piglet1", "Track 2": "piglet2", ...}
# Leave empty to auto-detect (exact name match, then ordered assignment).
TRACK_NAME_MAP = {}

# When SLEAP instances have no tracks (common with image-based labeling),
# instances are mapped to DLC individuals by their order in each frame.
# Set this list to control the mapping: instance 0 → first name, etc.
# Example: ["sow", "piglet1", "piglet2", "piglet3"]
# Leave empty to use the order from config.yaml's individuals list.
INSTANCE_ORDER_INDIVIDUALS = []


def build_track_mapping(
    sleap_tracks: list,
    dlc_individuals: list[str],
    manual_map: dict[str, str],
) -> dict[str, str]:
    """Map SLEAP track names to DLC individual names.

    Strategy:
      1. If manual_map is provided, use it (validated against dlc_individuals).
      2. Otherwise auto-detect: exact name matches first, then assign remaining
         tracks to remaining individuals in order.

    Returns dict mapping SLEAP track name → DLC individual name.
    """
    if manual_map:
        sleap_track_names = {t.name for t in sleap_tracks}
        for sleap_name, dlc_name in manual_map.items():
            if sleap_name not in sleap_track_names:
                raise ValueError(
                    f"TRACK_NAME_MAP has key '{sleap_name}' which is not "
                    f"a SLEAP track name. Available tracks: {sorted(sleap_track_names)}"
                )
            if dlc_name not in dlc_individuals:
                raise ValueError(
                    f"TRACK_NAME_MAP maps '{sleap_name}' → '{dlc_name}', "
                    f"but '{dlc_name}' is not in config.yaml individuals: {dlc_individuals}"
                )
        return dict(manual_map)

    # Auto-detect mapping
    mapping = {}
    used_individuals = set()

    # Pass 1: exact name matches (e.g. track named "sow" → individual "sow")
    for track in sleap_tracks:
        if track.name in dlc_individuals:
            mapping[track.name] = track.name
            used_individuals.add(track.name)

    # Pass 2: assign remaining tracks to unused individuals in order
    remaining_tracks = [t for t in sleap_tracks if t.name not in mapping]
    remaining_individuals = [i for i in dlc_individuals if i not in used_individuals]

    for track, ind_name in zip(remaining_tracks, remaining_individuals):
        mapping[track.name] = ind_name
        print(f"  Auto-mapped: '{track.name}' → '{ind_name}'")

    if len(remaining_tracks) > len(remaining_individuals):
        unmapped = remaining_tracks[len(remaining_individuals):]
        print(f"  WARNING: {len(unmapped)} track(s) could not be mapped:")
        for t in unmapped:
            print(f"    '{t.name}' — no remaining DLC individual available")

    return mapping

# ── Load SLEAP labels ────────────────────────────────────────────────
labels = sio.load_slp(str(SLP_FILE))
skeleton = labels.skeletons[0]
sleap_node_names = [node.name for node in skeleton.nodes]

print(f"Skeleton bodyparts: {sleap_node_names}")
print(f"Labeled frames: {len(labels.labeled_frames)}")
print(f"Videos (image folders): {len(labels.videos)}")
for v in labels.videos:
    print(f"  {v.filename[0]}")

# ── Resolve bodyparts and (optionally) individuals ───────────────────
if MULTI_ANIMAL:
    config_path = DLC_PROJECT / "config.yaml"
    with open(config_path) as f:
        dlc_cfg = yaml.safe_load(f)

    bodyparts = dlc_cfg["multianimalbodyparts"]  # e.g. [head, torso, hip]
    individuals = dlc_cfg["individuals"]  # e.g. [sow, piglet1, ..., piglet12]

    # Validate SLEAP skeleton nodes match DLC bodyparts
    if set(sleap_node_names) != set(bodyparts):
        print(f"\nWARNING: SLEAP nodes {sleap_node_names} != DLC bodyparts {bodyparts}")
        print("Coordinates will be matched by name; unmatched nodes are skipped.")

    # Build node name → index lookup for position-independent access
    node_name_to_idx = {node.name: i for i, node in enumerate(skeleton.nodes)}

    # Determine whether instances use tracks or are trackless
    sleap_tracks = labels.tracks
    has_tracks = len(sleap_tracks) > 0

    if has_tracks:
        print(f"\nSLEAP tracks found: {len(sleap_tracks)}")
        for t in sleap_tracks:
            print(f"  Track: '{t.name}'")
        track_to_individual = build_track_mapping(sleap_tracks, individuals, TRACK_NAME_MAP)
        print(f"Track mapping: {track_to_individual}")
    else:
        # Trackless mode: map instances by their order in each frame
        order_list = INSTANCE_ORDER_INDIVIDUALS or individuals
        print(f"\nNo SLEAP tracks found — using instance-order mapping.")
        print(f"  Instance 0 → '{order_list[0]}', 1 → '{order_list[1]}', ...")
        print(f"  IMPORTANT: label the sow FIRST in every frame, then piglets in consistent order.")

    print(f"\nMulti-animal mode: {len(individuals)} individuals, {len(bodyparts)} bodyparts")
else:
    bodyparts = sleap_node_names


def parse_frame_index(filename: str) -> int:
    """Extract the frame index number from various naming patterns.

    Handles:
      - "frame_000050.png" → 50
      - "img0050.png"      → 50
      - "img050.png"       → 50
      - "000050.png"       → 50
    """
    match = re.search(r"(\d+)", Path(filename).stem)
    if match:
        return int(match.group(1))
    raise ValueError(f"Cannot parse frame index from: {filename}")


def get_dlc_video_name(sleap_video_path: Path) -> str:
    """Map SLEAP video (image folder) path to DLC labeled-data subdirectory name."""
    folder_name = sleap_video_path.name if sleap_video_path.is_dir() else sleap_video_path.stem
    return FOLDER_NAME_MAP.get(folder_name, folder_name)


# ── Resolve source images per labeled frame ──────────────────────────
# SLEAP may store videos as:
#   (a) an image folder  → video.filename is a directory
#   (b) individual files → video.filename is a single image path
# We handle both by resolving each labeled frame to its source image.

# Group labeled frames by their DLC video subdirectory
# (determined by the parent folder of the source image)
groups = defaultdict(list)  # video_name → list of (src_image_path, lf)

for lf in labels.labeled_frames:
    if len(lf.instances) == 0:
        print(f"WARNING: frame with no instances, skipping")
        continue

    src_path = Path(lf.video.filename[0])

    if src_path.is_dir():
        # Case (a): video is an image folder — map frame_idx to sorted file list
        src_images = sorted(
            list(src_path.glob("*.png")) + list(src_path.glob("*.jpg"))
        )
        if lf.frame_idx >= len(src_images):
            print(f"WARNING: frame_idx {lf.frame_idx} out of range in {src_path.name}, skipping")
            continue
        src_image = src_images[lf.frame_idx]
        video_name = src_path.name
    else:
        # Case (b): video is a single image file
        src_image = src_path
        video_name = src_path.parent.name

    video_name = FOLDER_NAME_MAP.get(video_name, video_name)
    groups[video_name].append((src_image, lf))

print(f"\nGrouped into {len(groups)} video folder(s):")
for name, items in groups.items():
    print(f"  {name}: {len(items)} labeled frames")

# ── Process each group ────────────────────────────────────────────────
total_frames = 0

for video_name, frame_list in groups.items():
    labeled_data_dir = DLC_PROJECT / "labeled-data" / video_name
    labeled_data_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'─'*60}")
    print(f"Video: {video_name}")
    print(f"Target: {labeled_data_dir}")

    rows = {}
    for src_image, lf in frame_list:
        # Preserve original filename if it's already DLC format (img*.png),
        # otherwise rename from other patterns (frame_*.png, etc.)
        if src_image.name.startswith("img"):
            dlc_img_name = src_image.name
        else:
            orig_idx = parse_frame_index(src_image.name)
            dlc_img_name = f"img{orig_idx:04d}.png"
        dlc_img_path = labeled_data_dir / dlc_img_name

        # Copy image to DLC directory (skip if already present)
        if not dlc_img_path.exists() and src_image.exists():
            shutil.copy2(src_image, dlc_img_path)

        # DLC relative path (used as CSV row index)
        rel_path = f"labeled-data/{video_name}/{dlc_img_name}"

        if MULTI_ANIMAL:
            # Extract coordinates from ALL instances in this frame
            row_data = {}
            order_list = INSTANCE_ORDER_INDIVIDUALS or individuals

            for inst_idx, inst in enumerate(lf.instances):
                if has_tracks:
                    # Track-based mapping
                    if inst.track is None:
                        print(f"  WARNING: instance with no track in {rel_path}, skipping")
                        continue
                    dlc_individual = track_to_individual.get(inst.track.name)
                    if dlc_individual is None:
                        print(f"  WARNING: unmapped track '{inst.track.name}' in {rel_path}, skipping")
                        continue
                else:
                    # Trackless mode: map by instance order
                    if inst_idx >= len(order_list):
                        print(f"  WARNING: frame has more instances ({len(lf.instances)}) "
                              f"than individuals ({len(order_list)}) in {rel_path}, "
                              f"skipping instance {inst_idx}")
                        continue
                    dlc_individual = order_list[inst_idx]

                coords = inst.numpy()  # shape: (n_nodes, 2)
                for bp in bodyparts:
                    idx = node_name_to_idx.get(bp)
                    if idx is None:
                        continue  # SLEAP node not found for this DLC bodypart
                    x, y = coords[idx]
                    row_data[(SCORER, dlc_individual, bp, "x")] = float(x)
                    row_data[(SCORER, dlc_individual, bp, "y")] = float(y)

            rows[rel_path] = row_data
        else:
            # Single-animal: extract first instance only
            inst = lf.instances[0]
            coords = inst.numpy()  # shape: (n_nodes, 2)

            row_data = {}
            for i, bp in enumerate(bodyparts):
                x, y = coords[i]
                row_data[(SCORER, bp, "x")] = float(x)
                row_data[(SCORER, bp, "y")] = float(y)

            rows[rel_path] = row_data

    if not rows:
        print("  No labeled frames to export, skipping.")
        continue

    # Build DataFrame with DLC's expected MultiIndex columns
    df = pd.DataFrame.from_dict(rows, orient="index")

    if MULTI_ANIMAL:
        # 4-level MultiIndex: (scorer, individuals, bodyparts, coords)
        all_columns = pd.MultiIndex.from_product(
            [[SCORER], individuals, bodyparts, ["x", "y"]],
            names=["scorer", "individuals", "bodyparts", "coords"],
        )
        df.columns = pd.MultiIndex.from_tuples(
            df.columns, names=["scorer", "individuals", "bodyparts", "coords"]
        )
        # Reindex to guarantee ALL individuals have columns (NaN for unlabeled)
        df = df.reindex(columns=all_columns)
    else:
        # 3-level MultiIndex: (scorer, bodyparts, coords)
        df.columns = pd.MultiIndex.from_tuples(
            df.columns, names=["scorer", "bodyparts", "coords"]
        )

    df = df.sort_index()

    # Save CSV
    csv_path = labeled_data_dir / f"CollectedData_{SCORER}.csv"
    df.to_csv(csv_path)

    total_frames += len(df)
    print(f"  Saved: {csv_path}")
    print(f"  Frames exported: {len(df)}")

# ── Validate: every CSV path must have a matching image on disk ───────
print(f"\n{'='*60}")
print("Validating image paths...")

missing = []
for video_name, frame_list in groups.items():
    labeled_data_dir = DLC_PROJECT / "labeled-data" / video_name
    csv_path = labeled_data_dir / f"CollectedData_{SCORER}.csv"
    if not csv_path.exists():
        continue

    header = [0, 1, 2, 3] if MULTI_ANIMAL else [0, 1, 2]
    df = pd.read_csv(csv_path, header=header, index_col=0)
    for rel_path in df.index:
        abs_path = DLC_PROJECT / rel_path
        if not abs_path.exists():
            missing.append(rel_path)

if missing:
    print(f"\nERROR: {len(missing)} image(s) referenced in CSV but NOT found on disk:")
    for m in missing:
        print(f"  MISSING: {m}")
    print("\nThe CSV references files that don't exist. DLC will fail during training.")
    print("Check that image filenames in labeled-data/ match the CSV entries.")
    raise SystemExit(1)
else:
    print(f"All {total_frames} image paths verified — every CSV entry has a matching file.")

# ── Summary ───────────────────────────────────────────────────────────
print(f"\nConversion complete! {total_frames} total frames exported.")
print(f"\nNext step — finalize with DLC (on server in dlc conda env):")
print(f"  import deeplabcut")
print(f"  deeplabcut.convertcsv2h5('{DLC_PROJECT}/config.yaml', scorer='{SCORER}')")
