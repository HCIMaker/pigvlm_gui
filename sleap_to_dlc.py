import numpy as np
from pathlib import Path
import shutil
import re
import sleap_io as sio

# ── Configuration ─────────────────────────────────────────────────────
SLP_FILE = Path("C:\Academic\Research\PigVLM\sleap_label\ch07_Crate08_20220428080001_20220428100000_clip_00h15m00s\labels.v001.slp")  # ← Update this
DLC_PROJECT = Path("C:\Academic\Research\PigVLM\PigFarm_Sow-jiale-2026-02-08")  # ← Update this
SCORER = "jiale"  # Must match config.yaml scorer field

# If SLEAP's image folder name doesn't match the DLC labeled-data subdir,
# provide an explicit mapping: {"sleap_folder_name": "dlc_video_name"}
# Leave empty to auto-detect from folder names.
FOLDER_NAME_MAP = {}

# ── Load SLEAP labels ────────────────────────────────────────────────
labels = sio.load_slp(str(SLP_FILE))
skeleton = labels.skeletons[0]
bodyparts = [node.name for node in skeleton.nodes]

print(f"Skeleton bodyparts: {bodyparts}")
print(f"Labeled frames: {len(labels.labeled_frames)}")
print(f"Videos (image folders): {len(labels.videos)}")

for v in labels.videos:
    print(f"  {v.filename}")

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