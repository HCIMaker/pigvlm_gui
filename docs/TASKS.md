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

### T1. Fork sleap-develop into `workspace/` and launch the GUI ✅
- **Depends on:** —
- **Do:** Copy `sleap-develop/` to `workspace/sleap/`. Run `uv sync --extra nn`
  inside `workspace/sleap/` per that repo's `CLAUDE.md`. Editable install.
- **Accept:** `uv run sleap-label` (from `workspace/sleap/`) launches the
  SLEAP main window. Record the source commit SHA and the copy timestamp in
  `docs/PROGRESS.md`.

### T2. Sanity-check upstream DLC import on our CSVs ✅
- **Depends on:** T1
- **Do:** No code changes. Use File → Import → DeepLabCut dataset... and pick
  an existing `CollectedData_<scorer>.csv` from `labeled-data/<folder>/`. Do
  this for both the single-animal and multi-animal CSVs. Confirm via the GUI
  that the skeleton panel shows the correct bodyparts and edges; for multi,
  confirm `Labels.tracks` has one entry per individual.
- **Note:** Although the file dialog filter is `*.yaml *.csv`, upstream
  `sleap_io.io.dlc.load_dlc` is CSV-only (`pd.read_csv` — no yaml/h5 branch).
  Picking a yaml would raise a parse error. This confirms T5 **cannot** reuse
  `load_dlc` for the fresh-labeling case (no CSV exists yet) — it must parse
  the yaml itself.
- **Accept:** For both CSVs, skeleton panel shows the bodyparts/edges from
  `docs/MUST_KNOW.md §2`; multi shows 13 tracks. Result logged in
  `docs/PROGRESS.md`.

## Phase 2 — GUI Integration (the "DLC" option)

### T3. Add "New DLC Project..." to the File menu ✅
- **Depends on:** T2
- **Do:** In `workspace/sleap/sleap/gui/app.py` near line 472 (the existing
  `New Project` menu item), add a new entry `new_dlc` →
  `self.commands.newDLCProject`. Add a matching `newDLCProject`
  method on the Commands class and a new `NewDLCProject` AppCommand in
  `commands.py` that opens a placeholder `QWizard`.
- **Accept:** Launch GUI → File menu shows "New DLC Project..." → click
  → placeholder wizard with one blank page opens.

### T4. Wizard metadata + "mark folder finished" action ✅
- **Depends on:** T3
- **Pre-decided facts (from 2026-04-19 session with user):**
  1. **Labeler = `scorer` from `config.yaml`, NOT a typed wizard input.**
     The user who creates the DLC project *is* the scorer; the scorer
     string is the single source of truth for "who labeled this." Do not
     add a labeler QLineEdit — the value will be populated by T5's
     yaml-picker into `labels.provenance["labeler"]`.
  2. **Date = "finish labeling" timestamp, not wizard-open.** Labeling a
     folder often spans multiple sessions, so stamping the date at wizard
     open is wrong. Instead, stamp it when the user explicitly confirms
     the folder is done. Use `date.today().isoformat()` (YYYY-MM-DD) to
     match DLC's folder-naming convention (e.g., `PigFarm_Sow-jiale-2026-02-08`).
  3. **Empty dataset name is not allowed.** Block Finish until non-empty.
     (Labeler cannot be empty either, but that's enforced in T5 via yaml.)
  4. **`Labels.provenance` round-trips through `.slp`** — verified in T3's
     session via `sleap_io.Labels(provenance={...}).save() → load_file()`.
     Our keys survive; sleap_io auto-adds a `filename` key on save (expected).
- **Ordering note — read before coding:** this task's pre-decision #1 means
  the yaml picker (currently T5) logically needs to run *before* the
  metadata page so the scorer is known when we build provenance. Two ways
  to handle it; pick one and update both T4 and T5 accordingly:
  - **(A, recommended)** Keep task numbers T4/T5/T6 as-is, but inside the
    `QWizard` make yaml-picker page 1 and metadata page 2. Task T5 still
    owns the yaml-parsing code; task T4 owns the metadata page + finish
    action. They cooperate: T5's page stores the parsed scorer on the
    wizard object (e.g. `wizard._scorer`); T4's page reads it and displays
    it read-only next to the dataset field.
  - **(B)** Swap task ordering (do T5 first, then T4). Cleaner
    dependency but churns the task list. Only choose if (A) feels awkward.
- **Do:**
  1. Replace T3's placeholder `QWizardPage` with a real metadata page:
     - `QLineEdit` for **dataset name** (required, non-empty, trim whitespace).
     - Read-only display of the labeler/scorer (populated from the
       wizard-shared state that T5 will set; for now show "<set by config.yaml>"
       if T5 is not yet wired).
     - No date field on this page.
  2. On wizard Finish, write to `labels.provenance`:
     ```python
     labels.provenance["mode"] = "dlc"
     labels.provenance["dataset"] = <dataset from field>
     # labels.provenance["labeler"] = <from T5>  # set by T5, or here if both pages exist
     # labels.provenance["date"] = <set by finish-labeling action, not here>
     ```
  3. Add a **"Mark folder finished labeling"** action to the File menu
     (near Save). When triggered:
     - Show `QMessageBox.question` with "Are you finished labeling all
       frames in this folder? This stamps today's date into the project
       provenance." Yes/No.
     - On Yes: `labels.provenance["date"] = date.today().isoformat()`,
       mark the project dirty so the next save persists it.
  4. Update the main window title to include the labeler when
     `labels.provenance.get("labeler")` is set. Leave title unchanged when
     it's absent (so this task doesn't visibly break anything pre-T5).
- **Accept:**
  - Launch wizard → empty dataset field → Finish stays disabled (or shows
    validation error if using `QWizardPage.registerField("dataset*", ...)`).
  - Fill dataset name → Finish → new labels window opens → save `.slp` →
    close → reopen: `Labels.provenance["dataset"]` matches input;
    `provenance["mode"] == "dlc"`; `provenance["date"]` is absent.
  - Click "Mark folder finished labeling" → Yes → save → reopen:
    `provenance["date"]` equals today's ISO date.
  - Once T5 is done: window title shows the scorer from the picked yaml.
- **Why these shapes matter (for the implementer):**
  - Making the date a user-triggered stamp (not an auto wizard-time stamp)
    is the user's explicit requirement — multi-session labeling is common
    and the "finish" moment is semantically what DLC's folder date
    represents.
  - Using `QWizardPage.registerField("name*", widget)` (the trailing `*`)
    is the idiomatic Qt way to make Finish depend on a non-empty field —
    prefer that over manually gating the button.

### T5. Wizard step 2 — DLC config.yaml picker ✅
- **Depends on:** T4
- **Contract with T4 (from 2026-04-19 decisions):** the scorer parsed from
  the yaml is the *only* source of the labeler identity. This page must
  either (a) run before T4's metadata page inside the `QWizard` so T4 can
  read it (recommended — see T4's "Ordering note"), or (b) back-populate
  `labels.provenance["labeler"]` after T4 finishes. Also write
  `provenance["config_yaml"] = <absolute path of picked yaml>` so we can
  trace which config a given `.slp` was built against.
- **Do:** Second wizard page: file picker limited to `*.yaml`. On Next, parse
  the yaml with PyYAML and build a `sleap_io` `Skeleton` (nodes from
  `bodyparts` or, if `bodyparts: MULTI!`, from `multianimalbodyparts`; edges
  from `skeleton`). For multi (`multianimalproject: true`), also build one
  `Track` per entry in `individuals`. Attach to a fresh `Labels` object and
  stash the scorer into both `labels.provenance["labeler"]` and shared
  wizard state (e.g. `wizard._scorer`) so T4's page can display it.
- **Why not reuse `load_dlc`:** verified in T2 — upstream `load_dlc` is
  CSV-only (`pd.read_csv`). It cannot read yaml. We need a small dedicated
  yaml→Skeleton/Tracks helper; keep it ≤30 lines.
- **Accept:** Pick the sow config → skeleton panel shows the 4 sow
  bodyparts and correct edges. Repeat with the multi config → skeleton
  panel shows head/torso/hip plus 13 tracks for sow+piglets.

### T6. Wizard step 3 — image-folder picker ✅
- **Depends on:** T5
- **Do:** Third wizard page: directory picker. On Finish, build a single
  `sleap_io` `Video` from the folder (same path `ImageVideo` handles via
  `importvideos.py`) and attach it to the Labels object from T5. Preserve
  the DLC `img<NNN>.png` filenames — no renaming.
- **Accept:** Pick `sleap_label/single/ch07_Crate08_..._00h15m00s/` → main
  labeling window opens on the first frame; arrow keys navigate through all
  frames in sorted order; status bar shows `img020.png`, `img099.png`, etc.

## Phase 2B — Labeling UX

All five tasks below scope the **actual labeling experience** on a loaded DLC
project. They are sized to fit single focused sessions and each produces a
visibly testable change in the GUI. Each builds on T6 (folder loaded via the
wizard; DLC Image Frames dock already present from the T6 follow-up).

### T6a. Default the right-side dock to "DLC Image Frames" for DLC projects ⬜
- **Depends on:** T6
- **Do:** In `workspace/sleap/sleap/gui/app.py` replace the unconditional
  `self.videos_dock.wgt_layout.parent().parent().raise_()` at line 1130 with
  a check: if any video in `self.labels.videos` has `filename` as a `list`
  (the ImageVideo tell-tale), call `raise_()` on `self.dlc_frames_dock`
  instead. Wire the same check into the state["labels"] change handler so
  opening a DLC `.slp` via File → Open (not just via the wizard) also
  surfaces the DLC tab on top.
- **Accept:**
  - Open `test.slp` (DLC-backed) → "DLC Image Frames" is the frontmost tab
    in the right-side dock area.
  - Start SLEAP fresh with File → New Project, or open any mp4-backed
    `.slp` → "Videos" is frontmost (current behavior preserved).
- **Why this matters:** labelers are spending their time in the DLC Image
  Frames list; making them click a tab every session adds friction. The
  check is cheap and degrades gracefully for non-DLC projects.

### T6b. Add "points (labeled/total)" progress column to DLC Image Frames ⬜
- **Depends on:** T6a
- **Do:** Extend `DLCFramesTableModel.columns` in
  `workspace/sleap/sleap/gui/dataviews.py:677` from `("frame", "image")` to
  `("frame", "image", "points")`. In `object_to_items(video)`, for each
  frame_idx, look up the existing labeled_frame via
  `self.context.labels.find(video=video, frame_idx=i, return_new=False)`
  (keep a reference to the `CommandContext` the same way `DLCFramesDock`
  already does) and compute `"labeled/total"`:
  - `labeled` = total visible nodes across all instances on that frame
    (count `Instance.points_array` entries that are not NaN, or iterate
    `instance.points` checking `pt.visible`).
  - `total` = `len(skeleton.nodes) * n_expected_instances`, where
    `n_expected_instances = max(1, len(labels.tracks))`. For single-animal
    projects `labels.tracks` is empty, so this is just the node count.
- **Refresh hook:** connect `DLCFramesDock` to `state["labeled_frame"]`
  changes AND to a generic "labels dirty" signal so the column re-emits
  `dataChanged` when the user adds/edits/deletes an instance. Emit for the
  affected row only (not the whole column) to keep scroll position stable.
- **Decision to surface (design):** the "total" denominator could be
  (a) `nodes × len(tracks)` (fixed target — current proposal) or
  (b) `nodes × len(existing_instances_on_frame)` (denominator floats with
  instance count). (a) answers "how complete is this frame toward its
  labeling budget"; (b) answers "how much of what's present is labeled".
  Default to (a); if the single-animal case feels wrong, revisit.
- **Accept:**
  - Sow project fresh → every row `0/4`.
  - Label 2 keypoints on frame 3 → row 3 shows `2/4`; other rows unchanged.
  - Label all 4 → row 3 shows `4/4`.
  - Multi project with 13 individuals × 3 nodes → fresh rows show `0/39`;
    one fully-labeled instance → row shows `3/39`.

### T6c. Add "labeled" (0/1) status column to DLC Image Frames ⬜
- **Depends on:** T6b
- **Do:** Extend `DLCFramesTableModel.columns` to `("frame", "image",
  "points", "labeled")`. Value is `1` if the frame has at least the
  threshold number of visible keypoints; else `0`. Threshold constant
  defined at module top (`DLC_LABELED_THRESHOLD = 2`), matching the
  requirement "have >1 body points labeled" (i.e., at least 2 points).
- **Decision to surface (semantics):** user's requirement also says "as
  long as this image has been walked through AND have >1 body points
  labeled". Because placing a keypoint requires navigating to the frame,
  "walked through" is implied by "has labeled points" — no separate visit
  set is needed. If the user later clarifies that visited-but-empty frames
  should also flip to 1, add a `MainWindow._dlc_visited: set[int]` tracked
  via `state["frame_idx"]` changes and persist in
  `labels.provenance["visited_frames"]`. Flag this in `docs/PROGRESS.md`
  as an open question.
- **Refresh hook:** same signal wiring as T6b; the two columns can share
  one refresh call.
- **Accept:**
  - Fresh sow project → all rows show `labeled = 0`.
  - Label 1 keypoint on frame 3 → row 3 still `0` (below threshold).
  - Label a 2nd keypoint on frame 3 → row 3 flips to `1`.
  - Clear the instance on frame 3 → row 3 returns to `0`.
  - Save `.slp` → close → reopen → `labeled` column reflects actual label
    content (no persistence state to carry across sessions).

### T6d. Rebind "Add Instance" to the `L` key ⬜
- **Depends on:** T6
- **Do:** In `workspace/sleap/sleap/config/shortcuts.yaml` change line 1
  from `add instance: Ctrl+I` to `add instance: L`. Verify the existing
  shortcut loader in `workspace/sleap/sleap/gui/shortcuts.py` picks up the
  new binding on next launch — no Python changes needed if the yaml loader
  is generic.
- **Rationale:** the menu action already exists at `app.py:789`
  (`add_menu_item(labelMenu, "add instance", "Add Instance",
  new_instance_menu_action)`) and calls
  `self.commands.newInstance(init_method="best", offset=10)`. We're
  reusing that same action with a single-key shortcut — no duplicate code
  path.
- **Decision to surface (binding conflict):** the default SLEAP binding
  was `Ctrl+I` and we're replacing it. If other users of the fork need
  the old binding, add `L` as an additional shortcut instead (requires
  `QAction.setShortcuts([...])` via a small patch to `shortcuts.py` to
  accept lists). Default to replace; flag if a team member objects.
- **Accept:**
  - GUI open on any frame of a DLC project → press `L` → a new instance
    appears at the current frame with default keypoint positions (same
    result as right-click → Add Instance or Labels → Add Instance menu).
  - Pressing `Ctrl+I` after the rebind no longer triggers the action
    (expected — it's the replacement case).

### T6e. Add a "Keyboard Shortcuts" reference dialog under Help ⬜
- **Depends on:** T6d
- **Do:** Add a new menu item under the Help menu (or under File if Help
  doesn't exist yet in the fork — check `app.py:_create_menus` around line
  567) called "Keyboard Shortcuts". Wire it to a new command
  `showShortcutsDialog` that opens a non-modal `QDialog` with a read-only
  two-column `QTableWidget` (Key → Action). Populate the table by reading
  `workspace/sleap/sleap/config/shortcuts.yaml` at dialog-open time and
  filtering to a curated DLC subset (at minimum: `L → Add instance`,
  `Right/Left → Frame next/prev`, `Ctrl+S → Save`, `Esc → Clear
  selection`). Keep ~5–10 rows — this is a quick reference, not a full
  cheatsheet.
- **Why yaml-backed:** source of truth stays in one file
  (`shortcuts.yaml`). If T6d's binding ever changes, the dialog follows
  automatically.
- **Accept:**
  - Help → Keyboard Shortcuts → dialog opens with a two-column table.
  - The `L → Add instance` row is present and correct.
  - Close button dismisses; reopening shows current yaml contents (any
    edits made since last launch appear).

## Phase 3 — Single-Animal Full Pipeline

### T7. DLC CSV export — single-animal 🔵
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
- **Depends on:** T7, T8, T6e
- **Do:** Full flow on `sleap_label/single/ch07_Crate08_..._00h15m00s/`:
  File → New DLC Project → sow config → folder → confirm DLC Image Frames
  dock is the frontmost tab (T6a) → for ≥5 frames: navigate to frame,
  press `L` to add instance (T6d), place all 4 keypoints, watch row flip
  to `4/4` + `labeled=1` in the panel (T6b/T6c) → Export → DLC CSV →
  Render labeled previews → upload CSV to server → run
  `python 2_create_project/csv_to_h5_official.py` and
  `python 2_create_project/check_labels_from_sleap.py`.
- **Accept:** Both server commands exit 0. Previews exist and match the
  labels. DLC Image Frames panel shows the labeled 5 rows at `4/4` and
  `labeled=1`; unlabeled rows stay at `0/4`/`0`. `docs/PROGRESS.md`
  captures the command outputs.

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
- **Depends on:** T10, T6e
- **Do:** Full flow on `sleap_label/mutli/ch07_Crate08_..._00h35m00s/`:
  wizard with multi config → folder → confirm DLC Image Frames dock is
  frontmost (T6a) → for ≥5 frames: press `L` twice to add two instances
  (T6d), assign each to a distinct individual via the Tracks panel, place
  keypoints, watch the `points` and `labeled` columns update (T6b/T6c) →
  Export → DLC CSV → Render previews → upload → server scripts.
- **Accept:** Both server commands exit 0 on the multi project. Per-row
  `points` denominator matches `nodes × len(tracks)` from the yaml; rows
  with ≥2 labeled points read `labeled=1`.
