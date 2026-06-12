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
- ⏭️ Skipped (intentionally dropped — see task body for rationale)

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

### T6a. Default the right-side dock to "DLC Image Frames" for DLC projects ✅
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

### T6b. Add "points (labeled/total)" progress column to DLC Image Frames ✅
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

### T6c. Add "labeled" (0/1) status column to DLC Image Frames ✅
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

### T6d. Rebind "Add Instance" to the `L` key ✅
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

### T6e. Gate "Add Instance" at the per-frame max-instance cap ✅
- **Depends on:** T6d
- **Context:** The `points` column from T6b already exposes the budget:
  `total = len(skeleton.nodes) * max(1, len(labels.tracks))`. For the sow
  project that's `4 × 1 = 4`; for the multi project `3 × 13 = 39`. Because
  every SLEAP instance owns exactly `len(skeleton.nodes)` point slots, the
  only way to exceed that point total is to exceed the expected instance
  count. The gate is therefore an **instance-count cap**, not a
  point-count cap — same adaptive numbers, cheaper to check.
- **Invariant to enforce:**
  `len(frame.user_instances) ≤ max(1, len(labels.tracks))`.
  Count only user-placed instances (not prediction-only ones); predictions
  should not consume the user budget.
- **Where to patch (single patch point):** in
  `workspace/sleap/sleap/gui/commands.py:613` `NewInstance.do_action` (the
  command layer — this covers L from T6d, the Labels → Add Instance menu,
  **and** the right-click → Add Instance context path, because they all
  funnel through `commands.newInstance`). Compute `max_instances` from
  `context.labels.tracks` and the current labeled frame's user-instance
  count, and bail early when the cap is reached. Do **not** patch
  `new_instance_menu_action` at `app.py:774` alone — that would leave the
  right-click path ungated.
- **Do:**
  1. At the top of `NewInstance.do_action`, fetch:
     - `lf = context.state["labeled_frame"]` (may be `None`).
     - `n_user = sum(1 for inst in lf.instances if not inst.is_predicted)`
       (or the equivalent `inst.from_predicted is None` check — confirm
       the `sleap_io` attribute name while implementing).
     - `max_instances = max(1, len(context.labels.tracks))`.
  2. If `n_user >= max_instances`, show a status-bar message (reuse
     `context.app.statusBar().showMessage(msg, timeout_ms=3000)` — see
     existing uses in `app.py`) and `return` without creating an instance.
     Suggested message: `"Frame already has the maximum {max_instances}
     instance(s); cannot add another."`
  3. No other code paths need changes — the rest of `newInstance` runs
     unchanged when the gate passes.
- **Decision to surface (rejection UX):** three options; pick one when
  implementing and note the choice in `docs/PROGRESS.md`:
  - **(A, recommended)** Status-bar message + silent no-op. Non-blocking,
    matches how SLEAP surfaces most user-correctable conditions.
  - **(B)** `QMessageBox.information` modal. Louder — good for first-time
    users but interrupts fast labeling workflow.
  - **(C)** Disable the menu item / shortcut when at cap. Cleanest
    affordance but requires wiring to `state["labeled_frame"]` changes to
    re-enable on frame navigation — more code for the same outcome.
- **Accept:** (Shortcut is `1` = Add Instance (Default), per T6d final state
  — `L` was rebound away during that task.)
  - Sow project on any frame → press `1` once → 1 instance created → press
    `1` again → no 2nd instance; status bar shows the cap message; the
    `points` column row stays at `0/4` (or whatever the current labeled
    count was). Placing all 4 nodes does not change the gate.
  - Multi project on any frame → press `1` thirteen times → 13 instances
    created (one per track) → 14th `1` → rejected with status-bar message;
    `points` row denominator reads `/39`.
  - Multi project, subsequent frames where the bulk-copy helper
    (`2` = Add Instance (Copy Prior Frame)) is used → helper internally
    calls `commands.newInstance` in a loop; the gate must not fire
    spuriously during that loop as long as the prior frame had ≤13 user
    instances. A 14th iteration (shouldn't happen given 13 tracks, but
    worth asserting) is rejected by the same guard.
  - Right-click → Add Instance on a capped frame → same rejection
    behavior (confirms the command-layer gate covers all entry points).
  - Prediction-only frames do not eat the user budget: a frame with 13
    prediction instances and 0 user instances still accepts `1` up to 13
    user instances.
- **Why the command-layer gate matters:** putting the check in
  `new_instance_menu_action` would leave right-click, future hotkeys, and
  any programmatic `commands.newInstance(...)` callers ungated. One guard
  at the command boundary is both simpler and safer against regressions
  when new entry points are added.

### T6f. Add a "Keyboard Shortcuts" reference dialog under Help ✅
- **Depends on:** T6d
- **Do:** Add a new menu item under the Help menu (or under File if Help
  doesn't exist yet in the fork — check `app.py:_create_menus` around line
  567) called "Keyboard Shortcuts". Wire it to a new command
  `showShortcutsDialog` that opens a non-modal `QDialog` with a read-only
  two-column `QTableWidget` (Key → Action). Populate the table by reading
  `workspace/sleap/sleap/config/shortcuts.yaml` at dialog-open time and
  filtering to a curated DLC subset reflecting T6d's final bindings (at
  minimum: `1 → Add Instance (Default)`, `2 → Add Instance (Copy Prior
  Frame)`, `W/S → Frame prev/next`, `A/D → optional left/right nav if
  wired`, `Ctrl+S → Save`, `Esc → Clear selection`). Keep ~5–10 rows —
  this is a quick reference, not a full cheatsheet.
- **Why yaml-backed:** source of truth stays in one file
  (`shortcuts.yaml`). If T6d's bindings ever change, the dialog follows
  automatically.
- **Accept:**
  - Help → Keyboard Shortcuts → dialog opens with a two-column table.
  - Rows for `1 → Add Instance (Default)` and `2 → Add Instance (Copy
    Prior Frame)` are present and correct.
  - Close button dismisses; reopening shows current yaml contents (any
    edits made since last launch appear).

## Phase 3 — Single-Animal Full Pipeline

### T7. DLC CSV export — single-animal ✅
- **Depends on:** T4, T6
- **Do:** Create `workspace/sleap/sleap/io/format/dlc_csv.py` with a
  `DLCCSVAdaptor` class (mirror the shape of `csv.py`'s `CSVAdaptor`). Port
  the single-animal 3-row-header logic from `../sleap_to_dlc_multi.py`. Output
  name: `CollectedData_<scorer>.csv` in the image folder. Unlabeled
  keypoints → empty cells (see `docs/MUST_KNOW.md §3A`). Wire it into the
  File menu next to existing "Export Analysis CSV..." (`app.py:538`). Look at structure, for example,
  C:\Jiale\pigvlm_gui\pigvlm_gui\PigFarm_Sow-jiale-2026-02-08\labeled-data
- **Accept:** Export on the sow project → diff the CSV against
  `PigFarm_Sow-jiale-2026-02-08/labeled-data/<folder>/CollectedData_jiale.csv`.
  Header rows identical, column order identical, occluded-keypoint cells
  truly empty, scorer row shows our labeler name.

### T8. Batch-render labeled previews to disk ⏭️
- **Decision (2026-04-23):** skipped. Static preview PNGs were intended for
  pre-upload QA and out-of-GUI sharing, but the workflow doesn't actually
  need them:
  1. **In-GUI rendering is automatic on `.slp` reopen.** SLEAP's
     `QtInstance` overlays at `sleap/gui/widgets/video.py:497` redraw
     every label on every frame nav — visualization is free, just open
     the project. (Verified during the T7 follow-up discussion.)
  2. **Server already validates labels post-upload.** Per
     `docs/MUST_KNOW.md §9`, `check_labels_from_sleap.py` re-renders the
     uploaded CSV server-side. Client-side preview PNGs would duplicate
     that step.
  3. **Sharing/audit-trail use cases haven't come up** in this project —
     can revisit if they ever do; `sleap_io.render_image` is still
     available as the building block.

### T9. End-to-end smoke test — single-animal ✅
- **Depends on:** T7, T6f
- **Do:** Full flow on `sleap_label/single/ch07_Crate08_..._00h15m00s/`:
  File → New DLC Project → sow config → folder → confirm DLC Image Frames
  dock is the frontmost tab (T6a) → for ≥5 frames: navigate to frame,
  press `1` to add a default instance (T6d), place all 4 keypoints, watch
  row flip to `4/4` + `labeled=1` in the panel (T6b/T6c) → Export → DLC CSV
  → upload CSV to server → run
  `python 2_create_project/csv_to_h5_official.py` and
  `python 2_create_project/check_labels_from_sleap.py`.
- **Accept:** Both server commands exit 0. DLC Image Frames panel shows
  the labeled 5 rows at `4/4` and `labeled=1`; unlabeled rows stay at
  `0/4`/`0`. `docs/PROGRESS.md` captures the command outputs. (Visual
  label-correctness is verified by the server's `check_labels_from_sleap.py`,
  not by client-side preview PNGs — see T8 for why.)

## Phase 4 — Multi-Animal Add-On

### T10. DLC CSV export — multi-animal ✅
- **Depends on:** T7, T9
- **Do:** Extend `DLCCSVAdaptor` with the 4-row header (`scorer / individuals
  / bodyparts / coords`). Column order: `individuals × bodyparts × (x,y)`
  (NOT SLEAP's per-instance grouping — see `docs/MUST_KNOW.md §3B`). Port
  logic from `../sleap_to_dlc_multi.py`.
- **Mapping decision (2026-04-27 user call):** trackless / order-based —
  the Nth user instance on a frame is written under the Nth yaml
  `individual`. Labelers do NOT identify instances; columns are anonymous
  slots. T6e caps per-frame instance count at `len(individuals)`, so
  overflow can't occur; frames with fewer instances leave trailing
  individuals' columns empty (= MUST_KNOW §4 "individual not present").
- **Accept:** Export on multi project. Diff against
  `PigFarm_Multi-jiale-2026-02-08/labeled-data/<folder>/CollectedData_jiale.csv`.

### T11. End-to-end smoke test — multi-animal ✅
- **Depends on:** T10, T6f
- **Do:** Full flow on `sleap_label/mutli/ch07_Crate08_..._00h35m00s/`:
  wizard with multi config → folder → confirm DLC Image Frames dock is
  frontmost (T6a) → for the first labeled frame, press `1` thirteen times
  to add 13 default instances (T6d) and place keypoints on each (in any
  order — instance N maps to `individuals[N]` positionally per T10's
  trackless-mapping decision); for subsequent frames press `2` once to
  bulk-copy all 13 instances from the prior frame (T6d follow-up), then
  adjust keypoints. Watch the `points` and `labeled` columns update
  (T6b/T6c) → Export → DLC CSV → upload → server scripts.
- **Accept:** Both server commands exit 0 on the multi project. Per-row
  `points` denominator matches `nodes × len(tracks)` from the yaml; rows
  with ≥2 labeled points read `labeled=1`. (Preview-PNG step removed —
  see T8 for rationale.)

## Phase 5 — Maintenance

### T12. Sync DLC image folder (append-only, on-demand) ✅
- **Depends on:** T6
- **Background:** When the wizard finishes, `Video.from_filename(folder)`
  expands the folder to a frozen `list[str]` of paths and stores it in the
  `.slp` as `backend["filenames"]` (sleap_io `io/slp.py:359`). On reopen,
  the loader reads that list back verbatim — no re-globbing. So images
  added to `labeled-data/<folder>/` *after* the project was saved are
  invisible to the open project: they don't appear in DLC Image Frames,
  can't be navigated to, and won't be exported. This task adds an
  on-demand action to pull new files in without disturbing existing labels.
- **Pre-decided facts (from 2026-05-07 session with user):**
  1. **Append-only, dedupe by basename.** Use sleap_io's
     `Video.merge_with` (`model/video.py:735`) which keeps existing files
     in their current positions and appends only basenames not already in
     the list. This preserves `frame_idx` for every existing label —
     critical, because labels are keyed by integer index, and a sorted
     re-scan that inserts a new file in the middle would silently shift
     every label onto the wrong image.
  2. **On-demand menu item, not auto-sync on open.** Predictable behavior;
     the project on disk doesn't go dirty without the user asking for it.
  3. **Folder source = `labels.provenance["image_folder"]`** (set by the
     wizard at `commands.py:989`). If the key is missing (legacy `.slp`
     made before that field existed) or the folder no longer exists on
     disk, abort with a status-bar message — same UX convention as T6e
     and `ExportDLCCSV`.
  4. **No CSV change.** The exporter (`dlc_csv.py`) already iterates
     `video.filename` for its row order, so newly-appended frames
     automatically show up in the next CSV export with empty cells until
     they get labeled. Nothing in T7/T10 needs to change.
- **Do:**
  1. Add a new `AppCommand` `SyncDLCImageFolder` in
     `workspace/sleap/sleap/gui/commands.py` (place it next to
     `MarkFolderFinished` so the DLC-related commands stay grouped).
     `does_edits = True` so the project goes dirty when files are added.
  2. In `do_action`:
     - Read `image_folder` from `labels.provenance`. If missing or not a
       directory on disk → status-bar message, return. Reuse the same
       `_status` helper pattern from `ExportDLCCSV.do_action`
       (`commands.py:1042`).
     - Resolve the existing video: `video = labels.videos[0]` if the
       project has exactly one video; if there's no video or multiple
       videos, status-bar message and abort (DLC projects always have one
       ImageVideo per the wizard).
     - Sanity-check `isinstance(video.filename, list)` — if it's not, the
       project isn't ImageVideo-backed and this command doesn't apply.
     - Build a fresh `Video.from_filename(image_folder)` to get the
       current on-disk list. Call `merged = video.merge_with(new_video)`.
     - If `len(merged.filename) == len(video.filename)` → no new files;
       status-bar message "Sync DLC image folder: no new images found in
       <folder>" and return without marking dirty.
     - Otherwise, replace the project's video. Use
       `context.commands.execute(ReplaceVideo, ...)` if a `ReplaceVideo`
       command already exists (check `commands.py` for `replaceVideo` /
       `class ReplaceVideo` first); otherwise do the replacement in-place
       via `labels.videos[0] = merged` and update the labeled-frames'
       video reference (each `LabeledFrame.video` must point at the new
       `Video` object — iterate `labels.labeled_frames` and reassign).
       Picking which path to use is a judgment call once you've checked
       what's in `commands.py` — record the choice in `docs/PROGRESS.md`.
     - Refresh the DLC Image Frames dock so the new rows appear. The
       cleanest path is to re-emit on whatever signal `DLCFramesDock`
       already listens to for full-table refresh; if no such signal
       exists, call the dock's table model `update(video)` method
       directly. Locate the dock via `context.app.dlc_frames_dock`.
     - Status-bar message: `"Sync DLC image folder: added N new image(s)
       (was M, now M+N)"`.
  3. Wire it into the File menu in `workspace/sleap/sleap/gui/app.py`.
     Place it directly after the "Mark folder finished labeling" menu
     item so all DLC-specific actions are co-located. Label:
     `"Sync DLC image folder"`. No keyboard shortcut for now (the action
     is rare; adding it would consume a single-key binding for little
     gain).
  4. Add a new `Commands` method `syncDLCImageFolder` that calls
     `self.execute(SyncDLCImageFolder)`, mirroring how `markFolderFinished`
     and `newDLCProject` are wired (see `commands.py:317`).
- **Accept:**
  - **Sow project, no new files:** open an existing DLC `.slp` whose
     folder hasn't changed → File → Sync DLC image folder → status bar
     reads "no new images found"; project stays clean (Save action is
     not pulsing/highlighted).
  - **Sow project, files added:** drop 3 new `imgNNN.png` files into the
     folder → reopen the `.slp` → DLC Image Frames dock shows the
     original row count → File → Sync DLC image folder → dock now shows
     `original + 3` rows; the new rows appear at the **bottom** with
     `points = 0/4` and `labeled = 0`; existing rows are unchanged
     (frame number, image name, points, labeled all match pre-sync) →
     Save → close → reopen → row count and ordering match the post-sync
     state.
  - **Existing labels survive:** before sync, label frame index 5 with
     all 4 keypoints (`4/4`, `labeled = 1`) → run sync → frame index 5
     still reads `4/4`, `labeled = 1`, and the same image filename is
     shown in the `image` column.
  - **Multi project:** same flow on the multi project; new rows show
     `points = 0/39` (nodes × tracks per T6b's denominator).
  - **Missing provenance key:** open a non-DLC `.slp` (or one made
     before `image_folder` was added to provenance) → File → Sync DLC
     image folder → status-bar message naming the missing field;
     nothing else changes.
  - **Folder gone:** rename the folder on disk → reopen the `.slp` →
     File → Sync DLC image folder → status-bar message "image folder
     not found on disk: <path>"; project stays clean.
  - **Re-export sanity:** after a successful sync, Export DLC CSV → the
     CSV's image column lists the original images followed by the new
     ones in append order; new rows have empty x/y cells.
- **Why these shapes matter:**
  - `merge_with` is the only safe primitive here. A naive "rebuild from
    a sorted directory listing" would re-sort the list and shift every
    label index — silent data corruption that would only surface when
    the server-side checker runs. The append-only contract is what makes
    this command non-destructive.
  - Putting the action in the File menu (not under a hidden refresh
    button on the dock) matches where labelers already look for
    project-level actions like Save and Mark folder finished. Keeping it
    on-demand means an unchanged folder produces zero side effects on
    open — important for the workflow where users open a project just to
    review CSV output before upload.

## Phase 6 — Dual-Skeleton Labeling (sow + piglets in one `.slp`)

**Motivation (2026-05-12 session):** every image in `sleap_label/` is
training material for *two* DLC models — a single-animal sow model and a
multi-animal piglet model. Today the wizard reads ONE `config.yaml` and the
resulting `.slp` contains one skeleton. To avoid double-labeling each image
in two separate projects, the wizard should optionally pair a sow yaml with
a piglet yaml, producing a single `.slp` whose `labels.skeletons` holds
both. Export then splits back into two CSVs, one per DLC project folder on
disk. Upstream `sleap_io` needs no changes — `Labels.provenance` is a
free-form dict (T4 verified round-trip), and the DLC server scripts consume
each project folder independently.

**Pre-decided facts (2026-05-12 session with user):**
1. **Storage = one `.slp`, two skeletons.** `labels.skeletons[0]` is the
   sow skeleton (4 nodes, no tracks); `labels.skeletons[1]` is the piglet
   skeleton (3 nodes, 13 tracks). Verified `sleap_io.Labels.skeletons` is
   already a list and `state["skeleton"]` is the active-skeleton pointer.
2. **Mode = `"dlc_dual"` explicit, not inferred.** `provenance["mode"]`
   becomes one of `"dlc"` (legacy single-yaml) or `"dlc_dual"` (this
   phase). Reason: the export path forks fundamentally (1 CSV vs 2 CSVs to
   2 output folders), so a named mode keeps the fork obvious in code and
   greppable in saved files. Inferring from `len(labels.skeletons) > 1`
   would also work — explicit is the chosen convention.
3. **Positional skeleton assignment.** The Nth user instance on a frame
   maps to a skeleton positionally: instance 1 → sow, instances 2–14 →
   piglets (the Nth-2 individual per T10's trackless rule). Labelers do
   NOT toggle an active skeleton — pressing `1` always does the right
   thing based on current instance count. Cap becomes 14 per frame.
4. **Missing sow → empty placeholder.** When sow is not visible, the
   labeler still presses `1` once to create a sow instance with no
   keypoints placed (all 4 nodes stay occluded → empty CSV cells per
   `MUST_KNOW §3A`). This preserves the "1st = sow" invariant and avoids
   ambiguity on piglet-only frames.
5. **Same scorer in both yamls.** The wizard parses both and aborts (with
   a status-label message) if the `scorer:` fields differ — a single
   `.slp` cannot have a labeler conflict.
6. **One image folder, one dataset name.** Both DLC projects on disk
   share the same image folder under `labeled-data/<basename>/`. The
   wizard's metadata page (T4) and folder-picker page (T6) are unchanged.
7. **Backward compatibility.** Existing single-yaml projects keep
   `mode == "dlc"` and the old single-skeleton behavior. Nothing about
   T6a–T12 changes for those projects.

### T13. Wizard — "pair with second config" checkbox + dual-yaml parse ✅
- **Depends on:** T5, T6, T12
- **Do:**
  1. In `_DLCYamlPage` (`workspace/sleap/sleap/gui/commands.py:818`), add
     a `QCheckBox("Pair with a second config (dual sow + piglets)")`
     directly below the existing path row. Default unchecked.
  2. When toggled on, reveal a second path row (`QLineEdit` + `Browse…`
     button + status label) using the same widget pattern as the first.
     Hide the row when unchecked.
  3. Extend `validatePage()`:
     - **Unchecked path:** existing single-yaml behavior; sets
       `wizard._skeleton`, `wizard._tracks`, `wizard._scorer`,
       `wizard._config_yaml`, and `wizard._mode = "dlc"`.
     - **Checked path:** parse both yamls via `_parse_dlc_yaml`. Verify
       one is single-animal (no `multianimalproject`) and one is
       multi (`multianimalproject: true`); auto-assign roles by that
       flag (either picker slot may hold either role). Verify
       `scorer_sow == scorer_piglet`. On any mismatch, write the error
       to the second status label and return `False`. On success, set:
       ```python
       wizard._skeleton_sow      = sow_skel
       wizard._skeleton_piglet   = piglet_skel
       wizard._tracks            = piglet_tracks
       wizard._scorer            = scorer  # same in both
       wizard._config_yaml_sow   = <abs path>
       wizard._config_yaml_piglet= <abs path>
       wizard._mode              = "dlc_dual"
       ```
  4. In `NewDLCProject.do_action` (the Finish handler), branch on
     `wizard._mode`. For `"dlc_dual"`, append BOTH skeletons to
     `labels.skeletons` (sow first, piglet second) and copy `tracks` from
     the piglet skeleton. Write provenance:
     ```python
     labels.provenance["mode"]                = "dlc_dual"
     labels.provenance["sow_config_yaml"]     = wizard._config_yaml_sow
     labels.provenance["piglet_config_yaml"]  = wizard._config_yaml_piglet
     labels.provenance["labeler"]             = wizard._scorer
     # dataset, date, image_folder unchanged (set by T4/T6/T12 paths)
     ```
- **Accept:**
  - Wizard opened → checkbox unchecked → existing single-yaml flow
    works unchanged; `provenance["mode"] == "dlc"` after Finish.
  - Checkbox checked → pick sow yaml + multi yaml (in either order) →
    skeleton panel shows BOTH skeletons (4 sow nodes + 3 piglet nodes)
    and 13 tracks → save `.slp` → reopen →
    `len(labels.skeletons) == 2`, `provenance["mode"] == "dlc_dual"`,
    both `*_config_yaml` keys present.
  - Pick two single-animal yamls (or two multi yamls) → status label
    says "one config must be single-animal and one must be multi";
    Next stays disabled.
  - Pick yamls whose `scorer:` differs → status label says "scorer
    mismatch (<a> vs <b>)"; Next stays disabled.

### T14. Positional skeleton assignment in `NewInstance` ✅
- **Depends on:** T13, T6e
- **Context:** T6e already gates `NewInstance.do_action`
  (`commands.py:613`) on `n_user >= max_instances`, with
  `max_instances = max(1, len(labels.tracks))`. For dual mode, that cap
  becomes `1 + len(labels.tracks) = 14`, and the skeleton chosen for the
  new instance depends on the current count.
- **Do:**
  1. At the top of `NewInstance.do_action`, after computing `n_user`,
     branch on `labels.provenance.get("mode") == "dlc_dual"`:
     - `max_instances = 1 + len(labels.tracks)` (sow + piglets).
     - `target_skel = labels.skeletons[0] if n_user == 0 else labels.skeletons[1]`.
  2. For legacy modes (`"dlc"` or absent), keep the existing
     `max(1, len(labels.tracks))` cap and `labels.skeletons[0]` as the
     only skeleton. No regression.
  3. Pass `target_skel` to the instance constructor (where the existing
     code uses the implicit-first-skeleton path, replace it with the
     selected skeleton). Verify `sleap_io.Instance` accepts the skeleton
     parameter — if not, follow the same construction pattern as
     `LoadProjectFile` or `_DLCYamlPage`.
  4. Status-bar rejection message updates to use the new cap value
     ("Frame already has the maximum 14 instance(s); cannot add another").
- **Accept:**
  - Dual project on any frame → press `1` once → sow instance appears
    (4 nodes from sow skeleton, no track) → `points` columns from T15
    read `sow_pts = 0/4`, `piglet_pts = 0/39`.
  - Press `1` again → piglet instance appears (3 nodes, assigned to
    `tracks[0]`) → `piglet_pts = 0/39` (instance present but no points
    placed yet; per-instance breakdown surfaces during labeling).
  - Press `1` thirteen more times → 1 sow + 13 piglets exist; 15th
    press shows the cap message.
  - Single-yaml project (legacy `mode == "dlc"`) → caps and behavior
    identical to T6e — sow project caps at 1, multi at 13.
  - Prediction-only instances do not consume the user budget
    (preserve T6e invariant).

### T15. DLC Image Frames dock — `sow_pts` + `piglet_pts` columns ✅
- **Depends on:** T13, T6b, T6c
- **Do:**
  1. In `DLCFramesTableModel` (`workspace/sleap/sleap/gui/dataviews.py:677`),
     branch on `context.labels.provenance.get("mode")`:
     - Legacy (`"dlc"`): keep `("frame", "image", "points", "labeled")`.
     - Dual (`"dlc_dual"`): use `("frame", "image", "sow_pts",
       "piglet_pts", "labeled")`.
  2. `sow_pts` cell value: `f"{L}/{n_sow_nodes}"` where `L` is the count
     of visible nodes on the 1st user instance (`labels.skeletons[0]`).
     If no sow instance exists, show `"—/4"`.
  3. `piglet_pts` cell value: `f"{L}/{n_piglet_nodes * len(tracks)}"`
     summed across user instances 2..N.
  4. `labeled` semantics (strict, per design §6): flips to `1` only when
     BOTH skeletons meet `DLC_LABELED_THRESHOLD = 2` visible points.
     Reuse the constant from T6c.
  5. Refresh hook from T6b/T6c carries over — emit `dataChanged` for
     the affected row only.
- **Decision to surface (strict vs lenient — revisit):** strict was
  chosen because dual mode's whole purpose is "both models get data per
  frame". If a session shows the sow is genuinely absent for long
  stretches (e.g., camera fixed on a partial view), strict forces ghost
  placeholders on every such frame. Switching to "either" is a one-line
  change to the `labeled` predicate (`or` instead of `and`). Re-evaluate
  during T18.
- **Accept:**
  - Open a fresh dual project → all rows show `sow_pts = —/4`,
    `piglet_pts = 0/39`, `labeled = 0`.
  - Press `1` once on frame 3 (creates empty sow) → row 3 reads
    `sow_pts = 0/4`, `piglet_pts = 0/39`, `labeled = 0`.
  - Place 4 sow keypoints → `sow_pts = 4/4`; `labeled` still `0`
    (piglets below threshold).
  - Press `1` 13 more times, label 2 nodes on the 1st piglet, leave
    rest empty → `piglet_pts = 2/39`, `labeled = 1` (both ≥2).
  - Single-yaml project unchanged: 4-column layout from T6b/T6c.

### T16. Per-skeleton viewer color + show/hide toggle ✅
- **Depends on:** T13
- **Do:**
  1. In the viewer (search `sleap/gui/widgets/video.py` for instance/edge
     coloring — likely `QtInstance` and its color helper around
     `video.py:497`), branch coloring on the instance's skeleton:
     - Sow skeleton instances render edges/nodes in a single distinct
       color (suggested: bright white `#FFFFFF`, possibly with thicker
       lines).
     - Piglet skeleton instances keep the existing per-track palette
       cycle.
     Pick the exact sow color while running the GUI — must be visually
     distinct against pig fur (light pink/cream) and image background.
  2. Add two checkboxes to the right-side dock (next to "DLC Image
     Frames"): **Show sow** and **Show piglets**. Both default to
     checked. Wire them to a `MainWindow._dlc_show_skel = {"sow": True,
     "piglet": True}` dict; toggling repaints the viewer.
  3. The hide toggles affect rendering only — they do NOT affect the
     `sow_pts`/`piglet_pts` columns or the `NewInstance` cap.
- **Decision to surface (color choice — revisit during impl):** white is
  the proposal because piglets are colored. If the image background is
  often white (lighting overexposure), pick a different distinct color
  (e.g., cyan or magenta).
- **Accept:**
  - Dual project with both skeletons labeled on the same frame → sow
    instance renders in distinct color; 13 piglet instances cycle the
    existing palette.
  - Uncheck "Show piglets" → only the sow instance is visible; checking
    it again restores all 13 piglets.
  - Single-yaml project (legacy) → toggles either don't appear, or
    appear but have no visible effect (only one skeleton exists).
  - Cap and column behavior unchanged when toggles flip.

### T17. Export — two CSVs in dual mode ✅
- **Depends on:** T13, T7, T10, T14
- **Do:**
  1. In `ExportDLCCSV.do_action` (`commands.py`, near the existing T7/T10
     export path), branch on `labels.provenance.get("mode")`:
     - `"dlc"` or absent: existing single-CSV behavior, no changes.
     - `"dlc_dual"`: write TWO CSVs as described below.
  2. In `workspace/sleap/sleap/io/format/dlc_csv.py`, extend
     `DLCCSVAdaptor.write` (or add a sibling `write_dual`) to accept a
     `skeleton_filter` argument:
     - When writing the sow CSV, include only the 1st user instance per
       frame and use `labels.skeletons[0]`. Single-animal 3-row header
       (per T7 / `MUST_KNOW §3A`).
     - When writing the piglet CSV, include user instances 2..N per
       frame and use `labels.skeletons[1]`. Multi-animal 4-row header
       (per T10 / `MUST_KNOW §3B`). The Nth-2 user instance maps to
       `individuals[N-2]` positionally (trackless rule).
  3. Output paths:
     - Sow: `<dirname(sow_config_yaml)>/labeled-data/<basename(image_folder)>/CollectedData_<scorer>.csv`
     - Piglet: `<dirname(piglet_config_yaml)>/labeled-data/<basename(image_folder)>/CollectedData_<scorer>.csv`
     If either parent directory doesn't exist, create it. If the file
     already exists, follow the same overwrite-with-confirmation pattern
     as T7's existing export (re-check what T7 does and match it).
  4. Status bar: `"Exported sow CSV (N rows) → <sow path>; piglet CSV
     (M rows) → <piglet path>"`. On any error (missing provenance key,
     unwritable directory), show a status-bar error and abort both
     writes — no partial export.
- **Accept:**
  - Dual project with ≥5 labeled frames → File → Export DLC CSV → two
    CSVs land at the two expected paths; status bar shows both row
    counts.
  - Diff sow CSV against a reference single-mode export of the same
    labels — identical header rows, column order, occluded cells
    truly empty.
  - Diff piglet CSV against a reference multi-mode export — identical
    4-row header, `individuals × bodyparts × (x,y)` column order;
    rows with fewer than 13 piglets have trailing-individual columns
    empty.
  - Re-export over existing files → overwrite behavior matches T7's
    legacy single-CSV behavior.
  - Single-yaml project → `mode == "dlc"` branch fires; one CSV
    written exactly as in T7/T10.

### T18. End-to-end smoke test — dual mode ⬜
- **Depends on:** T13–T17, T6f
- **Do:** Full flow on `sleap_label/single/ch07_Crate08_..._00h15m00s/`
  (or whichever folder has both sow and piglet visible across most
  frames):
  - File → New DLC Project → check "Pair with second config" → pick the
    sow `config.yaml` and the multi `config.yaml` → dataset name → image
    folder → Finish.
  - Confirm DLC Image Frames dock is frontmost (T6a) and shows columns
    `frame | image | sow_pts | piglet_pts | labeled`.
  - For ≥5 frames: press `1` to add sow → place 4 keypoints; press `1`
    13 more times to add 13 piglets → place 3 keypoints on each (in any
    order; trackless mapping). Watch sow renders in distinct color
    (T16). Watch `sow_pts` go 0→4/4 and `piglet_pts` accumulate to
    39/39; `labeled` flips to 1.
  - For ≥1 frame: simulate "sow not present" — press `1` once and
    place NO keypoints (empty sow placeholder); press `1` once more to
    add 1 piglet and label its 2 visible points. `sow_pts = 0/4`,
    `piglet_pts = 2/39`, `labeled = 0` (strict rule rejects).
  - Save `.slp` → close → reopen → all label state intact, both
    skeletons in `labels.skeletons`, provenance keys present.
  - File → Export DLC CSV → two CSVs written.
  - Upload both CSVs to server. Run
    `python 2_create_project/csv_to_h5_official.py` against each DLC
    project folder, then
    `python 2_create_project/check_labels_from_sleap.py` against each.
- **Accept:** Both server commands exit 0 for both projects. The empty
  sow placeholder row in the sow CSV has all-empty x/y cells.
  `docs/PROGRESS.md` captures the command outputs for both projects.
  Decision recorded on whether to keep strict or switch to lenient
  `labeled` semantics (T15) based on the workflow feel.

## Phase 7 — Frame-level environment labels (lying direction, heat lamp, food)

**Motivation (2026-05-28 session):** beyond per-keypoint annotation, the
research needs three **general, frame-level** observations per image that are
not tied to any keypoint or skeleton — they describe the scene. The labeler
sets them from dropdowns in the DLC Image Frames dock, they carry forward from
the prior frame, persist in the `.slp` like keypoints, and export to a separate
CSV. Full design: `docs/superpowers/specs/2026-05-28-frame-environment-labels-design.md`.

**Pre-decided facts (2026-05-28 session with user):**
1. **The three labels and their space-free CSV/stored tokens** (dropdown may
   show friendlier text; what is stored in the `.slp` and written to CSV is
   always the no-space token):
   - `lying` (sow lying direction): `up` / `down` / `none` (`none` = not
     lying / unclear).
   - `heat_lamp`: `on` / `off` / `not_clear` (dropdown displays "not clear").
   - `food` (tank level): `3` / `2` / `1` / `0` (dropdown displays
     "3 — very much" … "0 — none").
2. **Unset is the default**, shown as `—`, distinct from real observations
   (`food=0`, `heat_lamp=off`). Unset exports as an **empty cell**.
3. **Edit UI = three inline dropdown columns** added to the DLC Image Frames
   dock (not a separate panel). Column order — single-config:
   `frame | image | points | lying | heat lamp | food | labeled`; dual:
   `frame | image | sow_pts | piglet_pts | lying | heat lamp | food | labeled`.
4. **Storage = `labels.provenance["frame_labels"]`**, a dict keyed by **string**
   frame index holding only set fields, e.g.
   `{"1": {"lying": "up", "heat_lamp": "on", "food": "3"}}`. Keyed by
   `str(frame_idx)` (not filename) to match `LabeledFrame` keying and survive
   T12's append-only sync.
5. **Persistence is the standard `.slp` save path — no extra mechanism.**
   Verified against installed `sleap_io` 0.6.5: `slp.py:write_metadata` does
   `json.dumps(md)` with `md["provenance"]=labels.provenance`, and
   `read_metadata` does `json.loads(...)`. The nested `frame_labels` dict
   round-trips intact — same store the keypoints live in.
6. **Copy-prior = folded into `2`** (Copy Prior Frame), not a separate action.
7. **Export = one `FrameLabels_<scorer>.csv`, folded into Export DLC CSV.**
   Every image gets a row (blanks for unset). Written into
   `provenance["image_folder"]`; in dual mode, one file there (not duplicated
   into both project dirs).

### T19. Frame-label dropdown columns + `SetFrameLabel` command + persistence ✅
- **Depends on:** T6c, T13, T15
- **Do:**
  1. In `workspace/sleap/sleap/gui/dataviews.py`, add the three columns to both
     `_DLC_SINGLE_COLUMNS` and `_DLC_DUAL_COLUMNS` (before `labeled`):
     keys `lying`, `heat_lamp`, `food`. Add a module-level mapping of each
     column to its `(token, display)` option list (plus the `""`/`—` unset
     default).
  2. In `DLCFramesTableModel.object_to_items`, populate each label cell's
     display string from `context.labels.provenance.get("frame_labels", {})`
     keyed by `str(frame_idx)`; unset → `—`.
  3. Override `flags()` to OR in `Qt.ItemIsEditable` for the three label
     columns only (existing columns stay read-only).
  4. Override `setData()` for those columns: route the new value through a new
     `SetFrameLabel` command (below), then refresh that row's label cells
     (reuse the single-row `dataChanged` pattern from `update_row_for_frame`).
  5. Header display: if `GenericTableModel` shows the raw `properties` key,
     add a `headerData` override so `heat_lamp` reads "heat lamp".
  6. In `workspace/sleap/sleap/gui/widgets/docks.py`, add a
     `FrameLabelDelegate(QStyledItemDelegate)` whose `createEditor` returns a
     `QComboBox` populated from the column's option list (itemText = friendly
     display, itemData = canonical token), `setEditorData` /`setModelData`
     wire the combo to the model. Install it on the DLC frames table via
     `setItemDelegateForColumn` for the three label columns in `DLCFramesDock`.
  7. In `workspace/sleap/sleap/gui/commands.py`, add `SetFrameLabel(EditCommand)`
     with `does_edits = True`. `do_action(params={"frame_idx","field","value"})`
     writes `provenance["frame_labels"][str(idx)][field] = value`, pruning the
     field when value is `""`/unset and pruning the per-frame dict when empty.
- **Accept:**
  - Open the sow DLC project → DLC Image Frames dock shows
    `lying | heat lamp | food` columns; every cell starts at `—`.
  - Click a `lying` cell → dropdown lists `— / up / down / none`; pick `up` →
    cell shows `up`. `heat lamp` dropdown shows "not clear" but the stored
    token is `not_clear`. `food` dropdown shows "3 — very much" but stores `3`.
  - After any edit the project is **dirty** (Save indicates unsaved changes).
    (This fork has no functional undo; dirty-tracking is what makes the save
    persist the labels.)
  - **Persistence:** set values on ≥3 frames → `Ctrl+S` → close → reopen the
    `.slp` → the same cells show the same values. Headless test:
    `save_file → load_file` preserves `provenance["frame_labels"]` exactly.
  - Dual project → the three columns appear before `labeled`; same editing
    behavior. Non-DLC (mp4-backed) `.slp` → dock empty, no label columns shown.

### T20. Carry the three labels on "Copy Prior Frame" (`2`) ✅
- **Depends on:** T19, T6d
- **Do:** Extend `add_all_instances_copying_prior_frame` (`app.py:819`). After
  the existing instance-copy loop, read the **prior labeled frame's**
  `provenance["frame_labels"][str(prev_idx)]` entry and, for each **set** field,
  execute `SetFrameLabel` to write it onto the current frame. Fields unset in
  the prior frame are left untouched. The label copy must run **even when
  `n_to_copy == 0`** (current frame already has its instances) so labels still
  carry forward on a single keypress.
- **Accept:**
  - On frame N set `lying=up, heat_lamp=on, food=2`. Move to empty frame N+1,
    press `2` → N+1 shows the same three values (in addition to copied
    keypoints).
  - On a frame that already has all its instances (so `n_to_copy == 0`),
    pressing `2` still carries the prior frame's labels.
  - Override `food=1` on N+1, press `2` on N+2 → N+2 inherits N+1's values
    (`lying=up, heat_lamp=on, food=1`).
  - Prior frame with a field unset (e.g. `heat_lamp` never set) → pressing `2`
    leaves the current frame's `heat_lamp` unchanged (no clobber to `—`).
  - Single-animal regression: the existing one-instance copy still works.

### T21. Export `FrameLabels_<scorer>.csv` (folded into Export DLC CSV) ✅
- **Depends on:** T19, T7, T17
- **Do:**
  1. New `workspace/sleap/sleap/io/format/frame_labels_csv.py` mirroring
     `dlc_csv.py`'s shape: a `write(filename, labels, video, scorer)` that emits
     a **plain CSV** (no multi-row header) with columns
     `image, lying, heat_lamp, food`, **one row per image** in `video.filename`
     order. Each value comes from `provenance["frame_labels"].get(str(idx), {})`;
     unset fields → empty cell. Returns `True` if written.
  2. Wire into `ExportDLCCSV.do_action` (`commands.py:1272`): after the existing
     keypoint CSV write(s) succeed, also write `FrameLabels_<scorer>.csv` into
     `provenance["image_folder"]` (single **and** dual mode — one file in the
     shared image folder). Use the same overwrite-confirmation convention as the
     keypoint CSV. Extend the status-bar message to name the frame-labels file.
  3. The frame-labels CSV should write even if the project has frame labels but
     no instances (it is independent of keypoints) — but keep the existing
     "no user labels → nothing to export" guard for the keypoint CSV path only.
- **Accept:**
  - Sow project with labels on ≥5 frames → File → Export DLC CSV →
    `FrameLabels_jiale.csv` lands next to `CollectedData_jiale.csv`; header is
    exactly `image,lying,heat_lamp,food`; one row per image; unset cells blank;
    `heat_lamp` cells read `not_clear` (no space); `food` cells read `3/2/1/0`.
  - The keypoint CSV(s) are byte-identical to a pre-T21 export (no regression).
  - Dual project → exactly one `FrameLabels_jiale.csv` in the shared image
    folder; the two `CollectedData_jiale.csv` files unchanged.
  - Re-export over an existing `FrameLabels` file → same overwrite-confirm
    behavior as the keypoint CSV.

### T22. End-to-end smoke test — frame labels ⬜
- **Depends on:** T19–T21, T6f
- **Do:** Full GUI flow on the sow project: New DLC Project → label ≥5 frames'
  keypoints → on each, set `lying`/`heat lamp`/`food` from the dropdowns; use
  `2` on later frames to carry labels forward, then tweak. Save `.slp` → close →
  reopen → confirm all dropdown values survived. Export DLC CSV → open
  `FrameLabels_<scorer>.csv` and the keypoint CSV. Repeat the save/reload +
  export on the dual project.
- **Accept:** Reopened project shows every previously-set dropdown value (no
  rework). `FrameLabels_<scorer>.csv` matches the dropdown values with space-free
  tokens and blank unset cells; keypoint CSV(s) unchanged. `docs/PROGRESS.md`
  captures the result. (No server-side step — the frame-labels CSV is downstream
  research data, not consumed by `csv_to_h5_official.py`.)
