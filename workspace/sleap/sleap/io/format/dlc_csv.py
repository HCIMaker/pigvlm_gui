"""Adaptor for exporting SLEAP labels as a DeepLabCut CollectedData CSV.

Single-animal: 3-row header (T7). Multi-animal: 4-row header (T10).
Mode is detected from `len(labels.tracks)` (T5 attaches one `Track` per
yaml `individuals` entry for multi; tracks list is empty for single).

Output matches the single-level-index + N-level-MultiIndex-column shape
that `pandas.DataFrame.to_csv()` produces — the shape of the reference
`CollectedData_<scorer>.csv` files under
``PigFarm_{Sow,Multi}-jiale-2026-02-08/labeled-data/<folder>/``. See
`docs/MUST_KNOW.md` §3A/§3B for the format spec (with the caveat, noted
in `docs/PROGRESS.md` under T7, that the diagram's 3-cell leading offset
does not match the real CSV — the real CSV uses a single combined-path
index column).

Occluded and unplaced keypoints both land as empty CSV cells (option A —
matches the T6b/T6c numerator semantics: if a point is not counted toward
`labeled/total`, it is not written to the CSV either).

Multi-animal mapping is **trackless / order-based** (per 2026-04-27 user
decision): the Nth user instance on a frame is written under the Nth
yaml `individual`. Labelers do not identify instances; columns are
treated as anonymous slots. Frames with fewer than `len(individuals)`
instances leave the trailing individuals' columns empty (= "not present"
per MUST_KNOW §4). T6e caps the per-frame instance count at
`len(individuals)`, so overflow cannot occur in practice.
"""

from pathlib import Path
from typing import Optional

import pandas as pd

from sleap_io import Labels, Video
from sleap_io.model.skeleton import Skeleton

from sleap.io.format import adaptor, filehandle


class DLCCSVAdaptor(adaptor.Adaptor):
    FORMAT_ID = 1.0

    @property
    def handles(self):
        return adaptor.SleapObjectType.labels

    @property
    def default_ext(self):
        return "csv"

    @property
    def all_exts(self):
        return ["csv"]

    @property
    def name(self):
        return "DeepLabCut CollectedData CSV"

    def can_read_file(self, file: filehandle.FileHandle):
        return False

    def can_write_filename(self, filename: str):
        return self.does_match_ext(filename)

    def does_read(self) -> bool:
        return False

    def does_write(self) -> bool:
        return True

    @classmethod
    def write(
        cls,
        filename: str,
        source_object: Labels,
        source_path: str = None,
        video: Video = None,
        scorer: str = None,
        folder_name: str = None,
        skeleton: Optional[Skeleton] = None,
        is_multi: Optional[bool] = None,
        instance_slice: Optional[slice] = None,
    ):
        """Write a DLC CollectedData CSV (single- or multi-animal).

        Mode is inferred from ``len(source_object.tracks)``: empty → single
        (3-row header); non-empty → multi (4-row header, trackless
        order-based individual mapping — see module docstring).

        Args:
            filename: Absolute path to the output CSV (e.g.
                ``<image_folder>/CollectedData_<scorer>.csv``).
            source_object: The ``Labels`` object.
            source_path: Unused; kept for adaptor-signature parity.
            video: The ImageVideo to export. Defaults to
                ``source_object.videos[0]``.
            scorer: Scorer name (also used in header). Required.
            folder_name: The DLC folder name used in the CSV's combined-path
                index (i.e. ``labeled-data/<folder_name>/<img>``). Required.
            skeleton: Which skeleton's nodes drive the column layout.
                Defaults to ``source_object.skeletons[0]``. T17 passes
                ``skeletons[0]`` or ``skeletons[1]`` for the sow vs piglet
                halves of a dual-skeleton project.
            is_multi: Explicit single/multi format selector. Defaults to
                ``bool(source_object.tracks)``. T17 passes ``False`` for the
                sow CSV (which uses single-animal 3-row header even though
                the project has piglet tracks) and ``True`` for the piglet
                CSV.
            instance_slice: Slice of each frame's user-instance list to
                include. Defaults to ``slice(None)`` (all instances). T17
                passes ``slice(0, 1)`` for sow (1st instance only) and
                ``slice(1, None)`` for piglets (2nd onward).

        Returns:
            ``True`` if a CSV was written, ``False`` if no labeled frames
            were found (nothing to export).
        """
        if scorer is None or folder_name is None:
            raise ValueError("DLCCSVAdaptor.write requires scorer and folder_name.")

        if video is None:
            video = source_object.videos[0] if source_object.videos else None
        if video is None:
            raise ValueError("No video in labels to export.")

        if skeleton is None:
            skeleton = source_object.skeletons[0]
        bodyparts = [node.name for node in skeleton.nodes]
        individuals = [t.name for t in source_object.tracks]
        if is_multi is None:
            is_multi = bool(individuals)

        rows: dict[str, dict[tuple, float]] = {}
        for lf in source_object.find(video):
            user_instances = [i for i in lf.instances if not i.from_predicted]
            if instance_slice is not None:
                user_instances = user_instances[instance_slice]
            if not user_instances:
                continue

            img_name = Path(video.filename[lf.frame_idx]).name
            rel_path = f"labeled-data/{folder_name}/{img_name}"

            row_data: dict[tuple, float] = {}
            if is_multi:
                # Trackless order-based mapping: nth user instance →
                # individuals[n]. T6e caps at len(individuals) so the
                # break is defensive only.
                for inst_idx, inst in enumerate(user_instances):
                    if inst_idx >= len(individuals):
                        break
                    ind_name = individuals[inst_idx]
                    coords = inst.numpy()  # (n_nodes, 2), NaN for invisible
                    for i, bp in enumerate(bodyparts):
                        x, y = coords[i]
                        row_data[(scorer, ind_name, bp, "x")] = float(x)
                        row_data[(scorer, ind_name, bp, "y")] = float(y)
            else:
                inst = user_instances[0]
                coords = inst.numpy()  # (n_nodes, 2), NaN for invisible
                for i, bp in enumerate(bodyparts):
                    x, y = coords[i]
                    row_data[(scorer, bp, "x")] = float(x)
                    row_data[(scorer, bp, "y")] = float(y)
            rows[rel_path] = row_data

        if not rows:
            return False

        if is_multi:
            col_names = ["scorer", "individuals", "bodyparts", "coords"]
            full_cols = pd.MultiIndex.from_product(
                [[scorer], individuals, bodyparts, ["x", "y"]],
                names=col_names,
            )
        else:
            col_names = ["scorer", "bodyparts", "coords"]
            full_cols = pd.MultiIndex.from_product(
                [[scorer], bodyparts, ["x", "y"]],
                names=col_names,
            )

        df = pd.DataFrame.from_dict(rows, orient="index")
        df.columns = pd.MultiIndex.from_tuples(df.columns, names=col_names)
        # Guarantee column order matches yaml-derived (individuals ×) bodyparts,
        # regardless of insertion order of the row dicts.
        df = df.reindex(columns=full_cols)
        df = df.sort_index()
        df.to_csv(filename)
        return True
