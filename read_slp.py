"""Print a one-screen summary of a SLEAP .slp file.

Usage:
    uv run python read_slp.py <path/to/file.slp>
    uv run python read_slp.py test.slp --frames        # also list every labeled frame
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import sleap_io as sio


def summarize(slp_path: Path, show_frames: bool) -> None:
    labels = sio.load_file(str(slp_path))

    print(f"=== {slp_path} ===\n")

    # Provenance (mode, labeler, image_folder, *_config_yaml ...)
    print("Provenance:")
    for k, v in labels.provenance.items():
        print(f"  {k}: {v}")
    mode = labels.provenance.get("mode", "(unset)")
    print()

    # Videos
    print(f"Videos ({len(labels.videos)}):")
    for i, vid in enumerate(labels.videos):
        if isinstance(vid.filename, list):
            print(f"  [{i}] ImageVideo, {len(vid.filename)} frames")
            print(f"        first: {vid.filename[0]}")
            print(f"        last:  {vid.filename[-1]}")
        else:
            print(f"  [{i}] {vid.filename}")
    print()

    # Skeletons
    print(f"Skeletons ({len(labels.skeletons)}):")
    for i, skel in enumerate(labels.skeletons):
        node_names = [n.name for n in skel.nodes]
        edges = [(e.source.name, e.destination.name) for e in skel.edges]
        role = ""
        if mode == "dlc_dual":
            role = " (sow)" if i == 0 else " (piglet)"
        print(f"  [{i}]{role} nodes={node_names}")
        print(f"        edges={edges}")
    print()

    # Tracks
    print(f"Tracks ({len(labels.tracks)}):")
    for t in labels.tracks:
        print(f"  - {t.name}")
    print()

    # Labeled frames summary
    print(f"Labeled frames: {len(labels.labeled_frames)}")
    total_user_inst = sum(len(lf.user_instances) for lf in labels.labeled_frames)
    print(f"Total user instances: {total_user_inst}")
    print()

    if show_frames:
        print("Per-frame breakdown:")
        for lf in labels.labeled_frames:
            if mode == "dlc_dual" and len(labels.skeletons) >= 2:
                sow_inst = [i for i in lf.user_instances
                            if i.skeleton is labels.skeletons[0]]
                pig_inst = [i for i in lf.user_instances
                            if i.skeleton is labels.skeletons[1]]
                sow_pts = sum(int(np.isfinite(i.numpy()).all(axis=1).sum())
                              for i in sow_inst)
                pig_pts = sum(int(np.isfinite(i.numpy()).all(axis=1).sum())
                              for i in pig_inst)
                n_sow_nodes = len(labels.skeletons[0].nodes)
                n_pig_total = len(labels.skeletons[1].nodes) * max(1, len(labels.tracks))
                print(f"  frame {lf.frame_idx:>4}: "
                      f"sow {sow_pts}/{n_sow_nodes} "
                      f"({len(sow_inst)} inst) | "
                      f"piglet {pig_pts}/{n_pig_total} "
                      f"({len(pig_inst)} inst)")
            else:
                pts = sum(int(np.isfinite(i.numpy()).all(axis=1).sum())
                          for i in lf.user_instances)
                n_nodes = len(labels.skeletons[0].nodes) if labels.skeletons else 0
                denom = n_nodes * max(1, len(labels.tracks))
                print(f"  frame {lf.frame_idx:>4}: "
                      f"{pts}/{denom} ({len(lf.user_instances)} inst)")


def main():
    parser = argparse.ArgumentParser(description="Summarize a SLEAP .slp file.")
    parser.add_argument("slp_path", type=Path, help="Path to the .slp file.")
    parser.add_argument(
        "--frames",
        action="store_true",
        help="Also print per-frame instance/point breakdown.",
    )
    args = parser.parse_args()

    if not args.slp_path.exists():
        print(f"Error: file not found: {args.slp_path}", file=sys.stderr)
        sys.exit(1)

    summarize(args.slp_path, show_frames=args.frames)


if __name__ == "__main__":
    main()
