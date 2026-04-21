"""Adaptor for exporting SLEAP labels as a DeepLabCut CollectedData CSV.

Single-animal projects only (T7). Multi-animal is T10.

Output matches the single-level-index + 3-level-MultiIndex-column shape that
`pandas.DataFrame.to_csv()` produces — i.e., the shape of the reference
`CollectedData_<scorer>.csv` files under
``PigFarm_Sow-jiale-2026-02-08/labeled-data/<folder>/``. See
`docs/MUST_KNOW.md` §3A for the format spec (with the caveat, noted in
`docs/PROGRESS.md` under T7, that the diagram's 3-cell leading offset does
not match the real CSV — the real CSV uses a single combined-path index
column).

Occluded and unplaced keypoints both land as empty CSV cells (option A —
matches the T6b/T6c numerator semantics: if a point is not counted toward
`labeled/total`, it is not written to the CSV either).
"""

from pathlib import Path

import pandas as pd

from sleap_io import Labels, Video

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
    ):
        """Write single-animal DLC CollectedData CSV.

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
        """
        if scorer is None or folder_name is None:
            raise ValueError("DLCCSVAdaptor.write requires scorer and folder_name.")

        if video is None:
            video = source_object.videos[0] if source_object.videos else None
        if video is None:
            raise ValueError("No video in labels to export.")

        skeleton = source_object.skeletons[0]
        bodyparts = [node.name for node in skeleton.nodes]

        rows: dict[str, dict[tuple, float]] = {}
        for lf in source_object.find(video):
            user_instances = [i for i in lf.instances if not i.from_predicted]
            if not user_instances:
                continue
            inst = user_instances[0]
            coords = inst.numpy()  # (n_nodes, 2), NaN for invisible/unplaced

            img_name = Path(video.filename[lf.frame_idx]).name
            rel_path = f"labeled-data/{folder_name}/{img_name}"

            row_data: dict[tuple, float] = {}
            for i, bp in enumerate(bodyparts):
                x, y = coords[i]
                row_data[(scorer, bp, "x")] = float(x)
                row_data[(scorer, bp, "y")] = float(y)
            rows[rel_path] = row_data

        if not rows:
            print(f"No labeled frames in video. Skipping DLC CSV export: {filename}")
            return

        df = pd.DataFrame.from_dict(rows, orient="index")
        df.columns = pd.MultiIndex.from_tuples(
            df.columns, names=["scorer", "bodyparts", "coords"]
        )
        # Guarantee bodypart column order matches the skeleton (and thus
        # config.yaml), regardless of insertion order of the row dicts.
        full_cols = pd.MultiIndex.from_product(
            [[scorer], bodyparts, ["x", "y"]],
            names=["scorer", "bodyparts", "coords"],
        )
        df = df.reindex(columns=full_cols)
        df = df.sort_index()
        df.to_csv(filename)
