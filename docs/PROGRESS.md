# Progress Log

Append an entry after each task in `docs/TASKS.md` is tested and accepted
(or blocked). Keep entries short and verifiable.

## T1. Fork sleap-develop into `workspace/sleap/` and launch the GUI

- **Status:** ✅ done — SLEAP main window confirmed visible on 2026-04-19.
- **Source commit SHA:** `28480a0` (pigvlm_gui HEAD at copy time —
  `sleap-develop/` has no own `.git`, so the parent repo pins its state)
- **Upstream sleap version:** `v1.6.2` (from `workspace/sleap/sleap/version.py`
  — `__version__ = "1.6.2"`; upstream tag: `talmolab/sleap@v1.6.2`)
- **Copy timestamp:** `2026-04-19T13:50:38-04:00`
- **Copy command:** `cp -r sleap-develop/ workspace/sleap/`
- **Environment:** `uv sync --extra nn` from `workspace/sleap/` — exit 0
- **Versions:** sleap `1.6.2` (editable), sleap-io `0.6.5`, sleap-nn `0.1.3`,
  torch `2.9.1`, Python `3.13.12`
- **GUI launch:** `uv run sleap-label` from `workspace/sleap/` printed the
  SLEAP banner and opened the main window.

### Notes
- sleap-nn was installed from PyPI (not editable) — fine, we only customize
  the GUI layer. If neural-network internals need patching later, add
  `uv pip install -e "../sleap-nn[torch]" --torch-backend=auto`.
- `sleap-develop/` is gitignored in pigvlm_gui; it is a read-only reference
  and must never be modified per `CLAUDE.md`.

## T2. Sanity-check upstream DLC import on our CSVs

- **Status:** ✅ done — tested 2026-04-19.
- **What was imported (File → Import → DeepLabCut dataset...):**
  - Single-animal:
    `PigFarm_Sow-jiale-2026-02-08/labeled-data/ch07_Crate08_20220428080001_20220428100000_clip_00h15m00s/CollectedData_jiale.csv`
  - Multi-animal:
    `PigFarm_Multi-jiale-2026-02-08/labeled-data/ch07_Crate08_20220430040000_20220430060000_clip_00h35m00s/CollectedData_jiale.csv`
- **Result:** both CSVs imported cleanly; existing labels render correctly in
  the main view. Skeletons and (for multi) per-individual tracks match
  `docs/MUST_KNOW.md §2`.

### Findings — important for T5

Original T2 said "pick `config.yaml`". The DLC importer's file dialog filter
is `DeepLabCut dataset (*.yaml *.csv)` (`sleap/gui/commands.py:938`), which
*allows* selecting a yaml, but the backend does not handle it:

- `sleap_io.io.dlc.load_dlc` (`sleap_io/io/dlc.py:49`) is CSV-only —
  `pd.read_csv(filename, ...)`, no branching on extension.
- **H5 is also unsupported** by `load_dlc`. Training-ready `.h5` files come
  from DLC's `convertcsv2h5` server-side and are not an input path here.

**Consequence for T5 (yaml picker):** cannot reuse `load_dlc` verbatim as
originally planned. When starting a fresh labeling session (no CSV exists
yet), the wizard must parse `config.yaml` itself with PyYAML to derive the
skeleton + individuals. T5's wording updated accordingly.

**Consequence for T2 itself:** the "yaml round-trip" sanity check upstream
does not exist. What T2 *does* validate is that once a CSV is produced, the
`load_dlc` path reads back the skeleton/tracks we care about — which is
still a useful checkpoint for T7/T10 output verification.

## T3. Add "New DLC Project..." to the File menu

- **Status:** ✅ done — tested 2026-04-19.
- **Changes:**
  - `workspace/sleap/sleap/gui/app.py` — added `add_menu_item(fileMenu,
    "new_dlc", "New DLC Project...", self.commands.newDLCProject)` directly
    below the existing `"new"` / "New Project" item.
  - `workspace/sleap/sleap/gui/commands.py` — added
    `CommandContext.newDLCProject()` next to `newProject()`, and a new
    `NewDLCProject(AppCommand)` class next to `NewProject` that opens a
    modal `QtWidgets.QWizard` parented to the main window with a single
    blank `QWizardPage`.
- **Verification:**
  - `uv run python -c "from sleap.gui.commands import NewDLCProject, CommandContext;
    assert hasattr(CommandContext, 'newDLCProject')"` → OK.
  - `uv run sleap-label` → File menu shows "New DLC Project..." → click →
    blank wizard opens with Finish + Cancel enabled and Back greyed out (no
    Next, as expected for a single-page wizard). Closes cleanly via Finish,
    Cancel, or window-X.

### Notes — carried into T4+
- Wizard is created with `QtWidgets.QWizard(context.app)` and shown via
  `exec_()` (modal). `exec_()` returns `QDialog.Accepted` on Finish — that
  return path is where T4/T5/T6 will hand the built `Labels` object back to
  the main window.
- `QWizard` auto-manages Back/Next/Finish/Cancel based on page count. Once
  T4 adds a second page, Next will appear automatically on page 1 and
  Finish will move to the last page. No manual button wiring needed.

## T4. Wizard metadata + "mark folder finished" action

- **Status:** ✅ done — 2026-04-19 (user accepted).
- **Ordering chosen:** option (A) from TASKS.md — task numbers kept; inside
  the wizard, yaml-picker is page 1 (placeholder until T5), metadata is
  page 2. T5 will set `wizard._scorer`; `_DLCMetadataPage.initializePage`
  reads it.
- **Changes:**
  - `workspace/sleap/sleap/gui/commands.py`
    - New class `_DLCMetadataPage(QtWidgets.QWizardPage)` — dataset
      `QLineEdit` + read-only labeler `QLabel`. `isComplete()` returns
      `bool(text.strip())` so whitespace-only names also disable Finish.
    - `NewDLCProject` rewritten to build a 2-page wizard; on Finish,
      constructs `Labels` with `provenance["mode"]="dlc"` and
      `provenance["dataset"]=<field>`, and `provenance["labeler"]` only
      if T5 has stashed `wizard._scorer`. Opens a new `MainWindow` via
      `context.app.__class__(labels=labels)`.
    - New class `MarkFolderFinished(AppCommand)` (`does_edits=True`):
      asks via `QMessageBox.question`, then writes
      `provenance["date"] = datetime.now().isoformat(timespec="minutes")`
      on Yes — ISO 8601 with minute precision (`YYYY-MM-DDTHH:MM`).
      **Deviation from task spec note:** TASKS.md T4 pre-decision #2
      specified `date.today().isoformat()` (date-only) "to match DLC's
      folder-naming convention". The minute-precision timestamp is a
      user-requested tweak (2026-04-19) — safe because
      `provenance["date"]` is internal metadata and does not drive any
      DLC folder name (the folder name is fixed when the DLC project
      itself is created, not when labeling finishes).
    - New `CommandContext.markFolderFinished()` method.
    - Added `from datetime import datetime` import.
  - `workspace/sleap/sleap/gui/app.py`
    - `setWindowTitle` now reads `labels.provenance.get("labeler")` via
      `self.state.get("labels", None)` and, when present, inserts it
      between filename and " - SLEAP v..." using an em-dash separator
      (`"<filename> — <labeler> - SLEAP v..."`). Title unchanged when
      labeler is absent, so this is a no-op until T5 lands.
    - Added `"mark_folder_finished"` menu entry under `fileMenu`
      directly below "Save As..." → `self.commands.markFolderFinished`.
- **Headless smoke tests (QT_QPA_PLATFORM=offscreen):**
  - `_DLCMetadataPage.isComplete()` is False for empty and whitespace-only
    dataset names, True for non-empty — confirmed.
  - `_DLCMetadataPage.initializePage()` leaves the labeler label at its
    placeholder when `wizard._scorer` is absent — confirmed.
  - Provenance round-trip (`save_file` → `load_file`) preserves
    `mode`/`dataset`/`labeler`/`date` keys — confirmed.
- **Pending manual verification (interactive GUI):**
  1. Launch `uv run sleap-label` → File → New DLC Project... → click
     Next past the yaml placeholder → metadata page → Finish is
     disabled with an empty/whitespace name, enabled otherwise → Finish
     → new labels window opens.
  2. Save As `.slp` → close → reopen: `Labels.provenance["dataset"]`
     matches input; `provenance["mode"] == "dlc"`;
     `provenance["date"]` is absent.
  3. With the project open, File → "Mark folder finished labeling" →
     Yes → save → reopen: `provenance["date"]` is an ISO 8601
     minute-precision timestamp (e.g. `2026-04-19T15:18`) matching the
     moment Yes was clicked.
  4. Title check (post-T5): when T5 populates `wizard._scorer`, the
     saved/loaded project's window title shows `<filename> — <scorer>`.

## T5. Wizard step 2 — DLC config.yaml picker

- **Status:** ✅ done — 2026-04-19 (user accepted after two parser fixes below).
- **Finding 1 — MUST_KNOW.md §2 is slightly wrong for multi-animal configs.**
  The real `PigFarm_Multi-jiale-2026-02-08/config.yaml` stores
  `skeleton` as `[[['head','torso'],['torso','hip']]]` (list *wrapping*
  a list of pairs), not the flat `[[a,b],[c,d]]` shown in the spec doc.
  Single-animal (`PigFarm_Sow-...`) is flat as documented. This is a
  known DLC multi-animal quirk (the outer wrap is DLC's per-individual
  container). `_parse_dlc_yaml` now detects the wrap by checking
  `isinstance(raw_skel[0][0], list)` and flattens one level. Consider
  amending MUST_KNOW.md §2 so future readers are not surprised.
- **Fix 1 — skeleton unwrap.** Initial `for a, b in cfg["skeleton"]`
  tripped on multi configs with "unhashable type: 'list'" because the
  outer wrap made `a` / `b` lists rather than strings. See Finding 1.
- **Fix 2 — `scorer: None` slipped past validation.** YAML parses a
  bare `scorer:` (no value) as Python `None`. The original guard
  `str(cfg.get("scorer", "")).strip()` returned `"None"` (4 chars,
  truthy) because `.get(k, default)` only substitutes the default when
  the key is absent, not when its value is `None`. Now
  `str(cfg.get("scorer") or "").strip()` coerces `None → ""` *before*
  the empty-check. Verified against
  `PigFarm_Sow_Test-jiale-2026-04-17/config.yaml` (with `scorer`
  removed): parser now raises, wizard status label shows
  `"Error: \`scorer\` is missing or empty in config.yaml."`, Next stays
  blocked.
- **Changes (all in `workspace/sleap/sleap/gui/commands.py`):**
  - Added `Edge` to the `sleap_io.model.skeleton` import.
  - New helper `_parse_dlc_yaml(yaml_path)` (~30 lines):
    - Uses PyYAML `safe_load`.
    - Multi detection: `multianimalproject: true` OR `bodyparts == "MULTI!"`.
    - Nodes from `multianimalbodyparts` (multi) or `bodyparts` (single).
    - Edges from `skeleton`; pairs referencing unknown nodes are silently
      skipped (defensive — DLC allows malformed-but-benign edges).
    - Tracks: one `Track` per `individuals` entry for multi; empty list
      for single-animal.
    - Raises `ValueError` on missing/empty `scorer`, missing bodyparts
      key, or missing `individuals` when multi is declared — the wizard
      page surfaces the message in its status label.
  - New `_DLCYamlPage(QtWidgets.QWizardPage)`: path `QLineEdit`
    (read-only) + "Browse…" button opening `QFileDialog.getOpenFileName`
    filtered to `*.yaml *.yml`. `isComplete()` gates Next on non-empty
    path; `validatePage()` calls `_parse_dlc_yaml`, writes
    `wizard._skeleton` / `_tracks` / `_scorer` / `_config_yaml` on
    success, or shows `"Error: ..."` in the status label and blocks
    Next on failure.
  - `NewDLCProject.do_action` now uses `_DLCYamlPage` as page 1 and
    builds `Labels(skeletons=[wizard._skeleton], tracks=list(wizard._tracks))`
    on Finish, writing
    `provenance = {mode, dataset, labeler=wizard._scorer, config_yaml}`.
    The placeholder yaml page from T4 is gone.
- **Headless smoke tests (QT_QPA_PLATFORM=offscreen):** all PASS.
  - Sow yaml → 4 nodes, 3 edges, 0 tracks, scorer `"jiale"`.
  - Multi yaml (PigFarm_Multi from MUST_KNOW §2) → 3 nodes, 2 edges,
    13 tracks (sow + piglet1..12), scorer `"jiale"`.
  - `_DLCYamlPage.validatePage()` stashes all four keys on the wizard.
  - Missing `scorer` → `validatePage()` returns False and status label
    reads `"Error: `scorer` is missing or empty in config.yaml."`.
  - `_DLCMetadataPage.initializePage()` reads `wizard._scorer` and
    updates the labeler display to `"jiale"`.
  - Round-trip: `save_file` → `load_file` preserves skeleton (name,
    nodes, edges), all 13 track names, and provenance keys
    (`mode`, `dataset`, `labeler`, `config_yaml`). sleap_io auto-adds
    `filename` on save as expected.
- **Pending manual verification (interactive GUI):**
  1. Launch `uv run sleap-label` → File → New DLC Project... → page 1
     "Select DLC config.yaml" → Browse…; pick the sow config
     (`PigFarm_Sow-jiale-2026-02-08/config.yaml`) → Next → page 2
     "Project metadata" → labeler label reads `"jiale"` (not the
     placeholder) → type a dataset name → Finish.
  2. In the new main window, skeleton panel shows
     `left_ear / right_ear / torso / hip` with 3 edges matching
     MUST_KNOW §2. Save `.slp` → reopen → window title shows
     `<filename> — jiale - SLEAP v...`.
  3. Repeat with the multi config (`PigFarm_Multi-*/config.yaml`):
     skeleton panel shows `head / torso / hip`; Tracks panel shows 13
     entries in order `sow, piglet1 … piglet12`.
  4. Negative: pick a yaml whose `scorer:` is blank → Next stays
     disabled/blocked and the error status text is visible.

## T6. Wizard step 3 — image-folder picker

- **Status:** ✅ done — 2026-04-20 (user accepted after dock + status-bar follow-ups).
- **Changes (all in `workspace/sleap/sleap/gui/commands.py`):**
  - New `_validate_dlc_folder(folder_path)`: enforces rules
    (a) folder contains ≥1 image with a supported extension
    (`png/jpg/jpeg/tif/tiff/bmp`), and (b) every image filename matches
    `img<NNN>.<ext>` (case-insensitive). Raises `ValueError` with a
    user-visible message on rejection; surfaced by the page's status label.
    Rule (b) is enforced because server-side `csv_to_h5_official.py`
    assumes the DLC `img<NNN>.png` shape — renaming mid-project would
    silently break that contract.
  - New `_DLCFolderPage(QtWidgets.QWizardPage)` — path `QLineEdit`
    (read-only) + "Browse…" using `QFileDialog.getExistingDirectory`.
    `isComplete()` gates Finish on non-empty path;
    `validatePage()` calls `_validate_dlc_folder`, writes
    `wizard._image_folder` on success or shows the error and blocks
    Finish on failure.
  - `NewDLCProject.do_action` now adds `_DLCFolderPage` as page 3 and,
    on Finish, builds `Video.from_filename(wizard._image_folder)`,
    attaches via `labels.add_video(video)`, and writes
    `provenance["image_folder"]` (useful to T7 for deriving the DLC
    CSV output path).
- **Why not reuse `ImportVideos` dialog:** that dialog requires picking
  the images explicitly (file filter). DLC's `img<NNN>.png` convention
  means selecting a whole directory is the right affordance here.
  `Video.from_filename(<dir>)` auto-delegates to
  `ImageVideo.find_images` which sorts by filename and filters by
  `ImageVideo.EXTS` — matches DLC's expected ordering for free.
- **Headless smoke tests (QT_QPA_PLATFORM=offscreen):** all PASS.
  - Validator accepts
    `PigFarm_Sow-jiale-2026-02-08/labeled-data/.../00h15m00s` (20 images).
  - Rejects a file path (not a dir): "Selected path is not a directory."
  - Rejects an empty tmpdir: "Folder contains no supported image files."
  - Rejects a dir containing `frame_001.png`: the error message names
    the offending file and cites the `img<NNN>.<ext>` convention.
  - `_DLCFolderPage.validatePage()` stashes `wizard._image_folder`.
  - `Video.from_filename(<real folder>)` yields 20 frames sorted, first
    entry `img020.png` (matches the real DLC folder's alphanumeric order
    — no renumbering).
- **Pending manual verification (interactive GUI):**
  1. Launch `uv run sleap-label` → File → New DLC Project... →
     page 1 pick sow `config.yaml` → page 2 dataset name → page 3
     "Select image folder" → Browse… → pick
     `PigFarm_Sow-jiale-2026-02-08/labeled-data/ch07_Crate08_..._00h15m00s/`
     → Finish → new window opens on first frame (`img020.png`).
  2. Arrow keys step through all 20 frames in sorted order
     (img020, img099, img104, ...); status bar shows current filename.
  3. Save `.slp` → reopen → `labels.provenance["image_folder"]` equals
     the picked path; `labels.videos[0]` has 20 frames.
  4. Negative: pick an empty folder → Finish blocked, status label
     reads "Error: Folder contains no supported image files."
  5. Negative: pick a folder containing `frame_001.png` → Finish
     blocked with the "img<NNN>.<ext> convention" message.

### T6 follow-ups — post-acceptance tweaks (2026-04-20)

After first manual check, user asked for two add-ons:

1. **Per-frame filename in status bar.** The Videos panel only shows the
   first image (video-level name); the status bar previously showed
   `Frame: N/M` only. Added ImageVideo-aware branch in
   `app.py:updateStatusMessage()`: when `current_video.filename` is a
   `list[str]`, the message appends `(img<NNN>.png)` for the current
   frame. No-op for MediaVideo/HDF5 (single-string filename).
2. **"DLC Image Frames" dock.** User wanted a scrollable, clickable list
   of all images in the folder so a labeler can jump to a specific
   frame without relying on arrow keys / seekbar. Added as a new,
   separate dock (not an overload of `VideosDock`), tabbed next to
   Videos on the right side.
   - `dataviews.py`: new `DLCFramesTableModel(GenericTableModel)` with
     columns `("frame", "image")`. `object_to_items(video)` returns
     `[]` unless `video.filename` is a list — so non-ImageVideo
     projects see an empty dock (harmless).
   - `widgets/docks.py`: new `DLCFramesDock(DockWidget)` — double-click
     a row → `commands.gotoVideoAndFrame(video, frame_idx)`. Connects
     to `state["video"]` (repopulate on file load / video switch) and
     to `state["frame_idx"]` (selection follows the currently
     displayed frame).
   - `app.py`: imports `DLCFramesDock` and creates it in
     `_create_dock_windows` with `tab_with=self.videos_dock`.
   - Design note: per user feedback, DLC-specific UI stays in new
     components (`DLCFramesDock`, `DLCFramesTableModel`) rather than
     modifying `VideosDock` or its model. Keeps the fork upstream-diffable.

- **User confirmation:** status bar per-frame filename confirmed working
  on 2026-04-20. DLC Image Frames dock design approved pending interactive
  test.
- **Pending manual verification (post-tweaks):**
  1. Open an ImageVideo-backed `.slp` (e.g. your `test.slp`) → new
     "DLC Image Frames" tab next to Videos. Click it → 20 rows,
     one per image, in the same sorted order as the status bar.
  2. Double-click any row → main view jumps to that frame; status bar
     updates to the matching `img<NNN>.png`.
  3. Press left/right arrow keys → row selection in the dock tracks the
     current frame.
  4. Open any non-DLC `.slp` (mp4-backed) → dock is present but empty.
