"""Writer for the frame-level environment-labels CSV (Phase 7 / T21).

Unlike `dlc_csv.py` (which emits DeepLabCut's multi-row-header CollectedData
format), this is a **plain** CSV — the three labels are per-image scalar
observations independent of any keypoint/skeleton:

    image,lying,heat_lamp,food
    img020.png,up,on,3
    img099.png,down,off,2
    img104.png,,,
    img111.png,none,on,1

One row per image in the video's frame order. Values come from
``labels.provenance["frame_labels"]`` keyed by ``str(frame_idx)`` (see T19);
unset fields are written as empty cells. Tokens are space-free (``lying``
up/down/none, ``heat_lamp`` on/off/not_clear, ``food`` 3/2/1/0).
"""

import csv
from pathlib import Path
from typing import Optional

from sleap_io import Labels, Video

# Mirror of dataviews.FRAME_LABEL_FIELDS — kept local so the IO layer has no
# dependency on the GUI layer.
FRAME_LABEL_FIELDS = ("lying", "heat_lamp", "food")


def write_frame_labels_csv(
    filename: str, labels: Labels, video: Optional[Video] = None
) -> bool:
    """Write the frame-labels CSV for an ImageVideo-backed project.

    Args:
        filename: Absolute path to the output CSV.
        labels: The ``Labels`` object holding ``provenance["frame_labels"]``.
        video: The ImageVideo to export. Defaults to ``labels.videos[0]``.

    Returns:
        ``True`` if a CSV was written; ``False`` if there is no ImageVideo to
        enumerate (a non-image-backed project — nothing to write).
    """
    if video is None:
        video = labels.videos[0] if labels.videos else None
    if video is None or not isinstance(getattr(video, "filename", None), list):
        return False

    frame_labels = labels.provenance.get("frame_labels", {})

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["image", *FRAME_LABEL_FIELDS])
        for idx, path in enumerate(video.filename):
            entry = frame_labels.get(str(idx), {})
            writer.writerow(
                [Path(path).name]
                + [entry.get(field, "") for field in FRAME_LABEL_FIELDS]
            )
    return True
