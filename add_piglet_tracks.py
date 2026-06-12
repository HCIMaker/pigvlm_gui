"""Raise the piglet (track) count of an existing SLEAP .slp project.

The per-frame instance cap in the labeling GUI is computed *live* from
`len(labels.tracks)` (see `workspace/sleap/sleap/gui/commands.py`, the
`max_instances = 1 + len(context.labels.tracks)` line for dual mode).
Tracks are baked into the `.slp` when the project is first created from
the DLC `config.yaml`; opening the `.slp` afterwards does NOT re-read the
yaml. So to allow one more piglet you must add a `Track` to the `.slp`
itself — editing the yaml alone has no effect on an existing project.

This script appends piglet tracks (named `piglet{N}`) until the project
has the requested total. It is idempotent: re-running with the same
target makes no change. Existing labels are left untouched.

# ---------------------------------------------------------------------------
# IMPORTANT — ALSO UPDATE THE YAML
# After running this, add the matching individuals to the piglet
# `config_multi.yaml` (the `individuals:` list), e.g.:
#     individuals:
#       - piglet1
#       ...
#       - piglet13      # <- add the new one(s) here
# The yaml is NOT read when opening an existing .slp, so this step does
# not change the current project's behavior — but it keeps the yaml (the
# project spec / source of truth) consistent with the .slp, which matters
# if the project is ever recreated from the yaml.
# ---------------------------------------------------------------------------

Usage:
    # Bump the project to 13 piglet tracks total:
    uv run python add_piglet_tracks.py C:\\Academic\\Research\\PigVLM\\Jiale\\jiale.slp --piglets 13
"""

import argparse
import sys
from pathlib import Path

import sleap_io as sio


def add_piglet_tracks(slp_path: Path, target_piglets: int) -> None:
    labels = sio.load_file(str(slp_path))

    current = list(labels.tracks)
    print(f"Current tracks ({len(current)}): {[t.name for t in current]}")

    if len(current) >= target_piglets:
        print(
            f"Already have {len(current)} track(s) >= requested {target_piglets}; "
            "no change made."
        )
        return

    existing_names = {t.name for t in current}
    for n in range(len(current) + 1, target_piglets + 1):
        name = f"piglet{n}"
        if name in existing_names:
            continue
        labels.tracks.append(sio.Track(name=name))
        existing_names.add(name)
        print(f"  + added {name}")

    sio.save_file(labels, str(slp_path))
    print(f"\nSaved {slp_path}")
    print(f"Tracks now ({len(labels.tracks)}): {[t.name for t in labels.tracks]}")
    print(
        "\nREMINDER: add the matching entries to the piglet config_multi.yaml "
        "`individuals:` list so the yaml spec stays in sync (see header note)."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Append piglet tracks to an existing .slp to raise the GUI cap."
    )
    parser.add_argument("slp_path", type=Path, help="Path to the .slp file.")
    parser.add_argument(
        "--piglets",
        type=int,
        required=True,
        help="Desired TOTAL number of piglet tracks (e.g. 13).",
    )
    args = parser.parse_args()

    if not args.slp_path.exists():
        print(f"Error: file not found: {args.slp_path}", file=sys.stderr)
        sys.exit(1)

    add_piglet_tracks(args.slp_path, args.piglets)


if __name__ == "__main__":
    main()
