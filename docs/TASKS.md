# Task List

Each task is sized for one focused session. Every task has a visible acceptance
criterion (GUI behavior, file on disk, or a server command that returns 0).
Update `docs/PROGRESS.md` after each task is tested or blocked.

All work happens in `workspace/sleap/` (a fork of `sleap-develop/`). Never
modify files under `sleap-develop/` itself — it is the read-only reference.

## Status Key
- ✅ Done (tested & approved)
- 🔵 Current
- ⬜ Pending

## Phase 1 — Workspace Setup

### T1. Fork sleap-develop into `workspace/` and launch the GUI ⬜
- **Depends on:** —
- **Do:** Copy `sleap-develop/` to `workspace/sleap/`. Run `uv sync --extra nn`
  inside `workspace/sleap/` per that repo's `CLAUDE.md`. Editable install.
- **Accept:** `uv run sleap-label` (from `workspace/sleap/`) launches the
  SLEAP main window. Record the source commit SHA and the copy timestamp in
  `docs/PROGRESS.md`.

### T2. Sanity-check upstream DLC import on our configs ⬜
- **Depends on:** T1
- **Do:** No code changes. Use File → Import → DeepLabCut dataset... and pick
  `PigFarm_Sow-jiale-2026-02-08/config.yaml`. Then separately try the multi
  config. Confirm via the GUI that the skeleton panel shows the correct
  bodyparts and edges; for multi, confirm `Labels.tracks` has one entry per
  individual.
- **Accept:** Screenshot of the skeleton panel for both configs saved to
  `docs/PROGRESS.md`. This validates that `load_dlc` handles our YAML — so T5
  can reuse it verbatim.

## Phase 2 — GUI Integration (the "Customized" option)

### T3. Add "New Customized Project..." to the File menu ⬜
- **Depends on:** T2
- **Do:** In `workspace/sleap/sleap/gui/app.py` near line 472 (the existing
  `New Project` menu item), add a new entry `new_customized` →
  `self.commands.newCustomizedProject`. Add a matching `newCustomizedProject`
  method on the Commands class and a new `NewCustomizedProject` AppCommand in
  `commands.py` that opens a placeholder `QWizard`.
- **Accept:** Launch GUI → File menu shows "New Customized Project..." → click
  → placeholder wizard with one blank page opens.

### T4. Wizard step 1 — labeler metadata ⬜
- **Depends on:** T3
- **Do:** First wizard page has QLineEdits for labeler name and dataset name,
  plus today's date filled in read-only (stamped at wizard open). On Next,
  stash values on the wizard object. When the wizard finishes, write them to
  `labels.provenance` (dict with keys `labeler`, `dataset`, `date`,
  `mode: "customized"`). Display labeler name in the main window title.
- **Accept:** Fill fields → finish wizard (skeleton/folder steps can be
  placeholders for now) → save `.slp` → close → reopen: window title shows
  the labeler, and `Labels.provenance` round-trips.

### T5. Wizard step 2 — DLC config.yaml picker ⬜
- **Depends on:** T4
- **Do:** Second wizard page: file picker limited to `*.yaml`. On Next, call
  `sleap_io.io.dlc.load_dlc(filename=path_to_yaml)` (same call already used
  by `ImportDeepLabCut` at `commands.py:930`) to get a `Labels` object that
  carries the skeleton and (for multi-animal) the tracks. Reuse the existing
  call verbatim — don't write a new parser.
- **Accept:** Pick the sow config → skeleton panel shows the 4 sow
  bodyparts and correct edges. Repeat with the multi config → skeleton
  panel shows head/torso/hip plus 13 tracks for sow+piglets.

### T6. Wizard step 3 — image-folder picker ⬜
- **Depends on:** T5
- **Do:** Third wizard page: directory picker. On Finish, build a single
  `sleap_io` `Video` from the folder (same path `ImageVideo` handles via
  `importvideos.py`) and attach it to the Labels object from T5. Preserve
  the DLC `img<NNN>.png` filenames — no renaming.
- **Accept:** Pick `sleap_label/single/ch07_Crate08_..._00h15m00s/` → main
  labeling window opens on the first frame; arrow keys navigate through all
  frames in sorted order; status bar shows `img020.png`, `img099.png`, etc.

## Phase 3 — Single-Animal Full Pipeline

### T7. DLC CSV export — single-animal ⬜
- **Depends on:** T4, T6
- **Do:** Create `workspace/sleap/sleap/io/format/dlc_csv.py` with a
  `DLCCSVAdaptor` class (mirror the shape of `csv.py`'s `CSVAdaptor`). Port
  the single-animal 3-row-header logic from `../sleap_to_dlc.py`. Output
  name: `CollectedData_<scorer>.csv` in the image folder. Unlabeled
  keypoints → empty cells (see `docs/MUST_KNOW.md §3A`). Wire it into the
  File menu next to existing "Export Analysis CSV..." (`app.py:538`).
- **Accept:** Export on the sow project → diff the CSV against
  `PigFarm_Sow-jiale-2026-02-08/labeled-data/<folder>/CollectedData_jiale.csv`.
  Header rows identical, column order identical, occluded-keypoint cells
  truly empty, scorer row shows our labeler name.

### T8. Batch-render labeled previews to disk ⬜
- **Depends on:** T6
- **Do:** Add "View → Render labeled previews" action. For each labeled
  frame, call `sleap_io.render_image` (already used by
  `sleap/gui/widgets/rendering_preview.py:19`) and save the rendered PNG to
  `<image_folder>/labeled_preview/`.
- **Accept:** Run on a folder where 5 frames have been labeled → 5 PNGs in
  `labeled_preview/` with keypoints (colored dots) and skeleton edges drawn.
  Occluded keypoints not drawn.

### T9. End-to-end smoke test — single-animal ⬜
- **Depends on:** T7, T8
- **Do:** Full flow on `sleap_label/single/ch07_Crate08_..._00h15m00s/`:
  File → New Customized Project → sow config → folder → label ≥5 frames →
  Export → DLC CSV → Render labeled previews → upload CSV to server → run
  `python 2_create_project/csv_to_h5_official.py` and
  `python 2_create_project/check_labels_from_sleap.py`.
- **Accept:** Both server commands exit 0. Previews exist and match the
  labels. `docs/PROGRESS.md` captures the command outputs.

## Phase 4 — Multi-Animal Add-On

### T10. DLC CSV export — multi-animal ⬜
- **Depends on:** T7, T9
- **Do:** Extend `DLCCSVAdaptor` with the 4-row header (`scorer / individuals
  / bodyparts / coords`). Column order: `individuals × bodyparts × (x,y)`
  (NOT SLEAP's per-instance grouping — see `docs/MUST_KNOW.md §3B`). Port
  logic from `../sleap_to_dlc_multi.py`.
- **Accept:** Export on multi project. Diff against
  `PigFarm_Multi-jiale-2026-02-08/labeled-data/<folder>/CollectedData_jiale.csv`.

### T11. End-to-end smoke test — multi-animal ⬜
- **Depends on:** T10
- **Do:** Full flow on `sleap_label/mutli/ch07_Crate08_..._00h35m00s/`:
  wizard with multi config → folder → label ≥5 frames using ≥2 individuals
  → Export → DLC CSV → Render previews → upload → server scripts.
- **Accept:** Both server commands exit 0 on the multi project.
