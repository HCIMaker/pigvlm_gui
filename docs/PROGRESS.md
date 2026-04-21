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

## T6a. Default the right-side dock to "DLC Image Frames" for DLC projects

- **Status:** ✅ done — 2026-04-21 (user accepted after the `dataviews.py`
  follow-up fix below; all 5 manual verification steps + the 3 post-fix
  checks confirmed).
- **Changes (all in `workspace/sleap/sleap/gui/app.py`):**
  - `_create_dock_windows()` — the unconditional `self.videos_dock.wgt_layout.parent().parent().raise_()`
    at line 1130 is replaced by a call to a new helper `_raise_default_right_dock()`,
    followed by `self.state.connect("labels", self._raise_default_right_dock)` so every
    subsequent labels change (File → Open, wizard finish → `loadLabelsObject`) re-evaluates
    which tab to surface.
  - New method `_raise_default_right_dock(self, *_)` — predicate
    `any(isinstance(v.filename, list) for v in self.labels.videos)` picks
    `dlc_frames_dock.raise_()` for ImageVideo-backed projects (DLC wizard or
    imported DLC CSV) and falls back to the original
    `videos_dock.wgt_layout.parent().parent().raise_()` form otherwise. The
    `*_` signature absorbs the value arg that `GuiState.emit` passes into
    callbacks with non-empty parameter signatures.
- **Why `isinstance(filename, list)` over `provenance["mode"] == "dlc"`:** the
  predicate has to fire for DLC-backed `.slp` files that were produced by any
  path, including the upstream File → Import → DeepLabCut CSV (T2) which does
  not stamp our provenance keys. Filename-shape is the ground truth for
  ImageVideo; provenance is only a hint.
- **Timing note:** `_create_dock_windows()` runs inside `_initialize_gui()`
  *before* the `loadProjectFile` / `loadLabelsObject` calls in
  `MainWindow.__init__` (lines 229–232). For the wizard path,
  `self.labels = labels or Labels()` at line 171 has already attached the
  ImageVideo, so the initial `_raise_default_right_dock()` call already picks
  the DLC tab. For the File → Open path, labels are empty at dock-creation
  time, so the initial call defaults to Videos; the state connect then fires
  when `LoadProjectFile` eventually writes the loaded `Labels` back into
  `state["labels"]`.
- **Headless predicate smoke test (no MainWindow boot, per memory):**
  - Empty videos list → False → videos_dock.
  - Single MediaVideo (str filename) → False → videos_dock.
  - Single ImageVideo (list filename) → True → dlc_frames_dock.
  - Mixed media + image → True → dlc_frames_dock (DLC wins if any present).
  - `python -c "import sleap.gui.app"` exits 0 and the helper docstring is
    retrievable via `MainWindow._raise_default_right_dock.__doc__`.
- **Pending manual verification:**
  1. `uv run sleap-label` with no args → "Videos" dock frontmost
     (fresh-start regression check).
  2. Open an mp4-backed `.slp` via File → Open → "Videos" frontmost
     (non-DLC regression check).
  3. Open an ImageVideo-backed `.slp` (e.g. `test.slp`) via File → Open →
     "DLC Image Frames" frontmost.
  4. File → New DLC Project → complete the wizard → new window opens with
     "DLC Image Frames" frontmost (wizard path).
  5. From a DLC-backed project, File → Open a different mp4-backed `.slp` in
     the same window → "Videos" frontmost (switch-project check: confirms the
     state-connect handler re-runs on every labels change, not just the first).

### T6a follow-up — `SuggestionsTableModel` ImageVideo crash (2026-04-21)

Manual step 3 above (File → Open an ImageVideo-backed `.slp`) surfaced a
pre-existing upstream bug, not introduced by T6a but triggered by the DLC
workflow. Fold into T6a's scope because it directly pollutes T6a's own
acceptance test (stderr-noise and a partially-reset Qt model every open).

- **Symptom:** `TypeError: expected str, bytes or os.PathLike object, not list`
  from `os.path.basename(item.video.filename)` in
  `workspace/sleap/sleap/gui/dataviews.py:527`, inside
  `SuggestionsTableModel.item_to_data`. Qt's event loop swallows the exception
  so the main GUI keeps working, but the traceback leaks to stderr and the
  items-setter aborts mid-`beginResetModel`/`endResetModel` — leaving the
  Suggestions panel partially rendered.
- **Root cause:** `ImageVideo.filename` is `list[str]` (sorted frame paths);
  `MediaVideo`/`HDF5Video.filename` is `str`. Upstream handles this branching
  in several sites in `commands.py` (1528, 3035, 3074, 3103) but missed this
  one in `dataviews.py`. Pre-T6a nobody in our workflow was opening
  ImageVideo-backed `.slp` files so the site never fired.
- **Why it triggers on File → Open:** `LoadProjectFile.do_action` calls
  `on_data_update([UpdateTopic.project, UpdateTopic.all])`; `app.py:1355`
  then runs `self.suggestions_dock.table.model().items = self.labels.suggestions`,
  which iterates each `SuggestionFrame` through `item_to_data` → crash.
  `test.slp` happened to carry at least one suggestion from an earlier session.
- **Fix (`workspace/sleap/sleap/gui/dataviews.py:526`):** branch on
  `isinstance(fn, list)`. For `ImageVideo`, display the parent folder name
  (`os.path.basename(os.path.dirname(fn[0]))`), with `"(empty)"` fallback for
  an empty list. For `str` (`MediaVideo`/`HDF5Video`) keep the original
  `os.path.basename(fn)` call — **zero behavior change for non-DLC projects**.
- **Why parent-folder name over first image filename:** in DLC the folder *is*
  the conceptual "video"; showing one arbitrary frame (e.g. `img020.png`) as
  if it represents the whole clip is misleading. Upstream's coping pattern in
  `commands.py:3103` uses `filename[0]` but that's for path-resolution, not
  for user-facing display.
- **Headless smoke tests:**
  - `str("/some/path/video.mp4")` → `"video.mp4"` (unchanged).
  - `str("labels.h5")` → `"labels.h5"` (unchanged).
  - `list[<absolute DLC paths>]` → `"ch07_Crate08_..._00h15m00s"` (folder name).
  - `[]` → `"(empty)"`.
  - `import sleap.gui.dataviews, sleap.gui.app` → exits 0.
- **Pending manual verification (extends T6a step 3):**
  - On File → Open of an ImageVideo-backed `.slp` with suggestions → no
    `TypeError` traceback in stderr.
  - Click the "Labeling Suggestions" tab → video column reads
    `"1: <folder_name>"` for each row; the list renders in full (no
    partial-reset artifacts).
  - Open an mp4-backed `.slp` → the video column still reads
    `"1: <video_basename.mp4>"` (regression check).

## T6b. Add "points (labeled/total)" progress column to DLC Image Frames

- **Status:** ✅ done — 2026-04-21 (user accepted after the two fixes below).
- **Denominator policy (decision from TASKS.md T6b options):** option (a)
  — fixed budget `len(skeleton.nodes) * max(1, len(labels.tracks))`.
  Sow → 4×1=4. Multi → 3×13=39. If single-animal "4" feels wrong in
  practice, revisit per the TASKS.md note.
- **Labeled-point semantics:** count `Instance.n_visible` summed over
  `LabeledFrame.user_instances`. Skips `PredictedInstance` (model output,
  not labels) and skips points the user flagged occluded — so the
  numerator matches what ends up as a non-empty cell in the DLC CSV
  (MUST_KNOW.md §4).
- **Changes:**
  - `workspace/sleap/sleap/gui/dataviews.py`
    - New module-level `_dlc_denominator_parts(labels) -> (n_nodes, n_expected)`.
    - New module-level `_count_labeled_points(labeled_frame) -> int`.
    - `DLCFramesTableModel.properties` extended from `("frame","image")`
      to `("frame","image","points")`.
    - `object_to_items` now calls `labels.find(video, frame_idx,
      return_new=False)` per row and stores the `"labeled/total"` string
      in each row dict. Falls back to `"0/0"` if labels/skeletons are
      absent.
    - New `update_points_for_frame(frame_idx, labeled_frame)` method —
      recomputes a single row's `points` cell and emits `dataChanged`
      for just that cell (row, points-column) to preserve scroll/selection.
  - `workspace/sleap/sleap/gui/app.py`
    - `MainWindow.on_data_update` — added one call in the existing
      `_has_topic([UpdateTopic.project, UpdateTopic.on_frame])` branch
      (right next to the `instances_dock` refresh at line 1353):
      `self.dlc_frames_dock.model.update_points_for_frame(lf.frame_idx, lf)`
      when `state["labeled_frame"]` is not None.
  - `workspace/sleap/sleap/gui/widgets/docks.py` — no refresh hook
    added on the dock. Initially attempted a
    `state.connect("labeled_frame", ...)` but removed after manual test
    (see "Fix" below).

- **Fix 1 (post-first-manual-test 2026-04-21):** the initial implementation
  hooked refresh via `DLCFramesDock._on_labeled_frame_changed` listening
  to `state["labeled_frame"]`. In manual testing the `points` cell did
  NOT update when the user added/occluded an instance on the current
  frame — it only updated when the user arrow-keyed away and back.
  Root cause: `GuiState.__setitem__` at `sleap/gui/state.py:60` short-
  circuits the callback when `old_val == value`. `plotFrame` reassigns
  `state["labeled_frame"]` to the *same* `LabeledFrame` object after
  an in-place mutation, so equality holds and the callback is
  suppressed. Navigating away-and-back works because a *different*
  `LabeledFrame` (for the neighbour frame) gets set in between,
  breaking the equality check on the return trip. The fix moves the
  refresh call into `MainWindow.on_data_update`, which already runs
  unconditionally after every command (the same path that refreshes
  `instances_dock`). Single authoritative refresh path — removed the
  now-redundant `state["labeled_frame"]` connect on the dock.

- **Fix 2 (post-second-manual-test 2026-04-21):** `Add Instance` now
  immediately flips the row to `4/4`, but flagging a keypoint occluded
  still only updated after the navigate-away-and-back trick. Root
  cause: `SetInstancePointVisibility` (commands.py:4648) had
  `topics = []` — intentionally empty per its docstring to avoid a
  full scene redraw on each visibility toggle. With empty topics,
  `on_data_update` never fires, so the DLC dock refresh in Fix 1
  never runs. Fix: set `topics = [UpdateTopic.on_frame]`.
  `on_data_update`'s branch at line 1309 only calls `plotFrame()` for
  `frame / skeleton / project_instances / tracks` — **not** `on_frame`
  — so the "no visual scene redraw" invariant the original docstring
  guaranteed is preserved. Data panels (instances dock, our DLC dock)
  now get the `on_frame` refresh that the occlude toggle always should
  have sent. Docstring updated to explain the new topic choice.

## T6c. Add "labeled" (0/1) status column to DLC Image Frames

- **Status:** ✅ done — 2026-04-21 (user accepted).
- **Threshold:** `DLC_LABELED_THRESHOLD = 2` module constant in
  `dataviews.py` — matches spec wording "have >1 body points labeled"
  (>1 → ≥2). The "walked through" part of the spec is implied by
  "has labeled points" since placing a keypoint requires navigating
  to the frame first, so no separate visit tracker is needed.
- **Changes (all in `workspace/sleap/sleap/gui/dataviews.py`):**
  - New module-level `DLC_LABELED_THRESHOLD = 2`.
  - `DLCFramesTableModel.properties` extended from
    `("frame","image","points")` to `("frame","image","points","labeled")`.
  - `object_to_items` now computes `"labeled": 1 if labeled >=
    DLC_LABELED_THRESHOLD else 0` alongside the points cell, reusing
    the same `_count_labeled_points` call (no new data source).
  - Renamed `update_points_for_frame` → `update_row_for_frame` since
    it now updates two derived cells. Emits a single `dataChanged`
    spanning `(row, points_col)` to `(row, labeled_col)` — one repaint
    for both cells, preserves scroll/selection. Updated the one call
    site in `app.py:1360`.
- **Headless smoke tests (QT_QPA_PLATFORM=offscreen):** all PASS.
  - Fresh sow project → all rows `labeled=0` (no instances).
  - 1 keypoint placed on frame 3 → `points=1/4, labeled=0` (below
    threshold, expected).
  - 2 keypoints placed → `points=2/4, labeled=1` (meets threshold,
    flips to 1).
  - Clear the instance → `points=0/4, labeled=0` (back to 0).
  - `update_row_for_frame(2, lf)` after adding a 3rd point → row
    shows `points=3/4, labeled=1` and emits exactly one `dataChanged`
    with topLeft=(2,2) and bottomRight=(2,3), covering both derived
    columns in a single repaint.
- **Pending manual verification:**
  1. Fresh sow project → all rows show `labeled=0`.
  2. Label 1 keypoint on frame 3 → row stays `labeled=0`.
  3. Label a 2nd keypoint on frame 3 → row flips to `labeled=1`.
  4. Right-click the 2nd keypoint to flag occluded → row drops back
     to `labeled=0` (only 1 visible point remains).
  5. Clear the instance → row returns to `labeled=0`.
  6. Save `.slp` → close → reopen → `labeled` column reflects saved
     labels (no persistence state carried across sessions).

## T6d. Rebind "Add Instance" to the L key

- **Status:** ✅ done — 2026-04-21 (user accepted after L → `1`/`2` rebinding
  and the multi-animal bulk-copy follow-ups below).
- **Changes:**
  - `workspace/sleap/sleap/config/shortcuts.yaml` line 1 —
    `add instance: Ctrl+I` → `add instance: L`. No Python changes;
    `shortcuts.py:_process_shortcut_dict` and `app.py:add_menu_item`
    (which does `menu.addAction(name, action, self.shortcuts[key])`)
    are both generic.
  - `C:\Users\Jiale\.sleap\1.6.2\shortcuts.yaml` same one-line edit.
    SLEAP's config loader (`sleap/util.py:get_config_yaml`) copies the
    packaged `shortcuts.yaml` to the user-local cache on first launch,
    then always reads from the cache. So a source-only edit would have
    been silently overridden on next launch. The cache was only Apr 19
    bundled defaults (no user customizations — verified before editing).
- **Headless smoke tests:** `Shortcuts()["add instance"].toString() == "L"`.
- **Decision (binding conflict):** per TASKS.md, we default to *replacing*
  the previous `Ctrl+I` binding, not adding `L` as an alternative. `Ctrl+I`
  is now unbound. Flag in PROGRESS.md if another team member objects —
  the alternative-bindings path would need a small `shortcuts.py` patch
  to accept list-valued yaml entries.
- **Pending manual verification:**
  1. Launch `uv run sleap-label` fresh → File → New DLC Project → open
     a folder → press `L` → a new instance appears at the current frame
     (same result as right-click → Add Instance).
  2. Pressing `Ctrl+I` does nothing (expected — we replaced the binding).
  3. Menu → Labels → Add Instance still shows shortcut hint as `L`.

### T6d follow-ups — shortcut overhaul (2026-04-21, user-requested)

User found `L` unintuitive and asked for WASD-style navigation plus
`Ctrl+1`/`Ctrl+2` for two fixed instance-placement methods. Folded
into T6d rather than split into a new task since it's pure shortcut
config.

- **New bindings:**
  - `frame next: S` (was `Right`)
  - `frame prev: W` (was `Left`)
  - `add instance: ` (unbound — the generic menu item loses its `L` shortcut)
  - `add instance default: '1'` → always uses `init_method="best"`
  - `add instance copy prior: '2'` → always uses `init_method="prior_frame"`
- **Loader fix — bare-digit shortcuts:** initial attempt used `Ctrl+1`/`Ctrl+2`
  which the user then simplified to just `1`/`2`. The existing
  `Shortcuts._process_shortcut_dict` at `shortcuts.py:106` had
  `try: eval(key_string) except: QKeySequence.fromString(key_string)`.
  For digit-only strings, `eval("1")` returns the int `1` (no exception),
  so `shortcuts[action]` silently became `1` instead of a `QKeySequence`
  — the shortcut never fired. Removed the `eval` branch and always use
  `QKeySequence.fromString`. Safe because no stock binding was a valid
  Python expression: `Ctrl+I`, `Right`, `Esc`, `Space`, `` ` ``, `H`,
  `Ctrl+=` all go through `fromString` as strings already. Verified with
  a headless regression test covering: letter bindings, modifier combos,
  named keys (`Esc`, `Space`), special chars (`` ` ``), digits (`1`,
  `2`), empty (unbound), and `Ctrl+=`. All load correctly.
- **Why two dedicated menu items instead of repurposing "Add Instance":**
  the existing "Add Instance" menu item reads `state["instance_init_method"]`
  from the "Instance Placement Method" submenu — so its behavior depends
  on UI state, not the shortcut itself. Ctrl+1/Ctrl+2 are meant to be
  *fixed* (always default / always copy-prior) per user intent, so they
  each get their own menu item with a hardcoded `init_method`. The generic
  "Add Instance" stays in the menu (unbound) for users who want to use
  the submenu radio-buttons.
- **Why W/S scrolls the DLC Image Frames list automatically:** changing
  `state["frame_idx"]` (via the existing QShortcut path in
  `widgets/video.py:330`) fires `DLCFramesDock._on_frame_changed` which
  calls `table.selectRow(frame_idx)`. So binding W/S to frame navigation
  gets the "list follows" behavior for free — no dock changes needed.
- **Changes:**
  - `workspace/sleap/sleap/config/shortcuts.yaml` — 4 line edits.
  - `C:\Users\Jiale\.sleap\1.6.2\shortcuts.yaml` — same 4 edits (user cache).
  - `workspace/sleap/sleap/gui/shortcuts.py` — added
    `"add instance default"` and `"add instance copy prior"` to
    `_names` tuple so the new yaml keys are recognized.
  - `workspace/sleap/sleap/gui/app.py` — two new `add_menu_item` calls
    right after the existing "Add Instance", each binding a lambda that
    calls `self.commands.newInstance(...)` with a hardcoded init_method.
    Default uses `offset=10` (matches `new_instance_menu_action`'s
    behavior); prior_frame uses no offset (matches the right-click
    "Copy Prior Frame" path in `widgets/video.py:397`).
- **Known risk to flag:** binding bare `W` / `S` to QShortcuts with
  `Qt.WindowShortcut` context means pressing W or S inside a text
  input (e.g., the wizard dataset field) will still trigger frame
  navigation instead of typing the character. Same risk class as the
  existing `H: show instances` binding. Mitigated in practice because
  text input is rare during labeling sessions. If this becomes a
  problem, the fix is to switch the video-widget shortcut context to
  application-level-but-ignore-text-input (a small patch in
  `widgets/video.py:343`).
- **Headless smoke test:** all new bindings resolve to the expected
  `QKeySequence.toString()` via `Shortcuts()`; unchanged bindings
  (`save = Ctrl+S`, `show instances = H`, `close = Ctrl+Q`) still
  resolve correctly.
- **Pending manual verification:**
  1. Press `W`/`S` anywhere in the main window → main view steps one
     frame; the DLC Image Frames selected row follows.
  2. Press `Ctrl+1` on an empty frame → a new default instance appears.
  3. Move to the next frame, press `Ctrl+2` → a new instance appears
     with keypoints copied from the previous frame's instance.
  4. Pressing `L` no longer does anything.
  5. Pressing `Right`/`Left` arrow keys no longer steps frames (arrows
     may still move the DLC list cursor via Qt default — that's fine
     and doesn't change the main view, matching the user's initial
     complaint).
  6. Menu → Labels shows three items: "Add Instance" (no shortcut),
     "Add Instance (Default)" (`Ctrl+1`), "Add Instance (Copy Prior
     Frame)" (`Ctrl+2`).

### T6d follow-up 2 — bulk copy-prior-frame for multi-animal (2026-04-21)

- **Symptom:** on a multi-animal project (5–13 tracks), pressing `2`
  only copied one instance from the prior frame. User had to press
  `2` repeatedly to clone all piglets.
- **Root cause:** upstream `newInstance(init_method="prior_frame")` is
  one-shot by design — `find_instance_to_copy_from` at
  `commands.py:4579` picks `prev_instances[len(current)]`, so each call
  walks forward by one. This supports SLEAP's track-assignment flow
  (place → assign track → place next). For DLC labeling of
  sow+piglets, that's friction.
- **Fix:** in `app.py`, replaced the `"add instance copy prior"` menu
  lambda with a helper `add_all_instances_copying_prior_frame` that:
  1. Finds the prior labeled frame via
     `AddInstance.get_previous_frame_index(self.commands)`.
  2. Computes `n_to_copy = max(0, len(prev.instances) -
     len(current.instances))`.
  3. Calls `self.commands.newInstance(init_method="prior_frame")` in a
     loop `n_to_copy` times. Each call adds the next unmatched
     instance (upstream's one-shot logic is fine; we just wrap it).
- **Why not a new AddInstancesCopyingPriorFrame command:** would
  require a new EditCommand class + do_action + topics etc. The loop
  is ~15 lines and reuses upstream logic unchanged. If the user
  later wants single-undo semantics for the bulk copy, promoting to
  a dedicated command is a ~30 line refactor.
- **Safe on edge cases (headless-verified via n_to_copy math):**
  - Current empty, prior has 5 → `n_to_copy=5`.
  - Current has 2, prior has 5 → `n_to_copy=3` (fills in the rest).
  - Current has 5, prior has 5 → `n_to_copy=0` (no-op).
  - No prior labeled frame → helper returns early, no crash.
  - `current_lf is None` or `video is None` → returns early.
- **Single-animal regression:** single-animal projects have 1 prior
  instance, so `n_to_copy` is 0 or 1 — identical behavior to the
  pre-fix one-shot. No regression.
- **Pending manual verification (multi-animal):**
  1. Open a multi-animal DLC project with ≥2 prior-labeled frames
     worth of instances.
  2. On an empty later frame, press `2` → all N instances appear at
     once (no repeated keypresses needed).
  3. Press `2` again → no-op (already at N).
  4. On a frame that already has 2 of 13 instances, press `2` → the
     remaining 11 appear.
- **Known behavior:** each copied instance is a separate undo step
  (13 undos to reverse one bulk copy). Consistent with SLEAP's
  delete-one-at-a-time UX. Promote to a single command if this
  becomes a pain point.
- **Headless smoke tests (QT_QPA_PLATFORM=offscreen):** all PASS.
  - `_count_labeled_points` — empty frame → 0, 2 visible of 4 → 2,
    3 placed with 1 flagged occluded → 3 (matches the "occluded = not
    counted" rule).
  - `_dlc_denominator_parts` — sow (skel only, 0 tracks) → (4,1) → 4;
    multi (3 nodes, 13 tracks) → (3,13) → 39; `labels=None` → (0,1).
  - `DLCFramesTableModel(context=ctx); model.items = video` on a
    single-animal project with one 2-point frame → rows show
    `0/4, 0/4, 2/4, 0/4, 0/4` (exactly matches TASKS.md T6b acceptance
    `row 3 shows 2/4; other rows unchanged`).
  - Multi-animal (3 nodes × 13 tracks) with one 3-point instance on
    frame 2 → rows show `0/39, 3/39, 0/39` (matches acceptance
    `fresh rows show 0/39; fully-labeled instance → 3/39`).
  - `update_points_for_frame(2, lf)` after adding a 3rd keypoint → row
    2's cell flips to `3/4` and exactly one `dataChanged` is emitted
    with `(row=2, col=2)` — column-scoped refresh, not whole-model.
  - Defensive: model with no context → `0/0` cells (graceful);
    MediaVideo (str filename) → 0 rows (non-DLC projects unaffected);
    out-of-range `update_points_for_frame(5, None)` → no-op, no raise.
  - `import sleap.gui.dataviews, sleap.gui.widgets.docks` → exits 0.
- **Pending manual verification:**
  1. Open sow project fresh via the wizard → DLC Image Frames dock's
     "points" column shows `0/4` for every row.
  2. Label 2 keypoints on frame 3 → that row flips to `2/4`; all other
     rows stay `0/4`; scroll position and row selection preserved.
  3. Label all 4 on frame 3 → `4/4`.
  4. Flag the 4th as occluded → row returns to `3/4` (matches CSV-empty
     semantics).
  5. Save `.slp` → reopen → column values reflect the saved instances.
  6. Multi-animal project (13 individuals × 3 nodes) → fresh rows show
     `0/39`; fully label one sow instance → `3/39`.
- **Open design question (surfaced from TASKS.md):** the fixed denominator
  (a) makes the single-animal case show `N/4` (fixed budget of 4
  points). Alternative (b) would be `nodes × instances_on_frame`, so a
  frame with 0 instances shows `0/0` and a frame with 1 sow instance
  shows `N/4`. (a) is clearer as "how close to labeling budget" and is
  the current choice — revisit only if manual tests feel wrong.

## T6e. Gate "Add Instance" at the per-frame max-instance cap

- **Status:** ✅ done — 2026-04-21 (user accepted after manual verification).
- **UX choice (from TASKS.md T6e options):** option (A) — status-bar
  message + silent no-op when the cap is hit. Non-blocking, matches
  how SLEAP already surfaces user-correctable conditions (e.g.,
  `app.py:1554`). (B) modal interrupts the keyboard-driven labeling
  flow; (C) disable-on-cap requires a `state["labeled_frame"]`
  connect for the same outcome. Flag for revisit if (A) feels too
  quiet in practice.
- **Patch location:** `AddInstance.do_action` in
  `workspace/sleap/sleap/gui/commands.py` (class defined at line
  4274 — note: TASKS.md references line 613, but that's
  `CommandContext.newInstance`, a routing wrapper; the real
  `do_action` is farther down). Gate inserted directly after the
  existing `labeled_frame is None` / empty-skeleton early returns,
  so the cap check runs before `find_instance_to_copy_from` and
  `create_new_instance`.
- **Why at the command layer (not the menu actions):** all entry
  points — `1`/`2` shortcuts (T6d), Labels → Add Instance menu,
  right-click → Add Instance, and the bulk-copy helper
  (`app.py:800`) — funnel through `commands.newInstance`, which
  calls `AddInstance.execute`. A single guard here catches them
  all; patching `new_instance_menu_action` alone would leave
  right-click and the bulk helper ungated.
- **Invariant enforced:**
  `len(labeled_frame.user_instances) < max(1, len(labels.tracks))`.
  Uses `LabeledFrame.user_instances` (already used at
  `commands.py:494, 2809`) so `PredictedInstance` rows don't
  count against the user's budget. Sow: cap = 1. Multi (13
  tracks): cap = 13.
- **Why `user_instances` over `is_predicted` / `from_predicted`:**
  `user_instances` is the canonical sleap_io filter for
  "user-placed only" and is already the idiom in this codebase.
  Manual filtering would duplicate its logic.
- **FakeApp safety:** `CommandContext.from_labels` uses a `FakeApp`
  that has no `statusBar` method. The gate guards with
  `getattr(context.app, "statusBar", None)` so headless tests
  bail cleanly when the cap fires without a crash.
- **Bulk-copy helper composition:** `app.py:800`'s
  `add_all_instances_copying_prior_frame` computes
  `n_to_copy = len(prev.instances) - len(curr.instances)` and
  calls `commands.newInstance` in a loop. Because the gate uses
  `user_instances` (not `instances`), a prior frame with
  predictions + user labels can drive an `n_to_copy` higher than
  the cap. The gate silently short-circuits the excess iterations
  — correct behavior, matches TASKS.md T6e acceptance: "14th
  iteration … rejected by the same guard."
- **Headless smoke tests (QT_QPA_PLATFORM=offscreen):** all PASS.
  Mocked `find_instance_to_copy_from` and `create_new_instance` to
  detect whether the gate short-circuits before downstream calls:
  - Case 1a: sow (0 tracks), 0 user → pass (→ create).
  - Case 1b: sow, 1 user → blocked.
  - Case 2a: multi (13 tracks), 12 user → pass.
  - Case 2b: multi, 13 user → blocked.
  - Case 3: multi, 0 user + 20 predictions → pass (predictions
    don't count).
  - Case 4: multi, 13 user + 5 predictions → blocked.
  - Case 5 (bulk composition): 13 tracks, prior has 15 instances,
    current starts at 0 → helper runs 15 loop iterations →
    current ends at exactly 13 user instances (iterations 14 and
    15 silently no-op).
  - `import sleap.gui.commands, sleap.gui.app` → exits 0.
- **Pending manual verification:**
  1. Sow project fresh → press `1` → 1 instance; press `1` again
     → no 2nd instance; status-bar reads "Frame already has the
     maximum 1 instance(s); cannot add another." (message clears
     after ~3s).
  2. Multi project fresh → press `1` thirteen times → 13
     instances; 14th `1` → rejected with the message reading
     `maximum 13 instance(s)`.
  3. Right-click → Add Instance on a capped frame → same
     rejection (confirms the command-layer gate covers the
     right-click path, not just shortcuts).
  4. Bulk copy-prior (`2`) onto an empty frame where prior has
     13 instances → all 13 copied, no rejection. Press `2`
     again → no-op. If prior frame somehow has 14+ user
     instances (shouldn't happen post-T6e), pressing `2` copies
     only the first 13.
  5. Prediction-only frame (13 predictions, 0 user) → `1` adds
     user instances normally up to 13; predictions are
     preserved, not replaced.
  6. `points` column denominator from T6b matches the cap:
     `nodes × max(1, n_tracks)` — sow `N/4`, multi `N/39`.

## T6f. Add a "Keyboard Shortcuts" reference dialog under Help

- **Status:** ✅ done — 2026-04-21 (user accepted).
- **Coexist vs. replace (TASKS.md design decision):** the new reference
  card is added *alongside* the upstream `ShortcutDialog` editor, not
  in place of it. Help menu now has two entries, back-to-back:
  "Keyboard Shortcuts" (upstream, modal, editable, all ~40 actions)
  and "DLC Shortcuts" (new, non-modal, read-only, 6 curated rows).
  Editor is kept because customization is still a valid use case;
  reference card is the quick-lookup affordance a labeler pops open
  mid-session. Revisit if users find two entries confusing.
- **Changes:**
  - New file `workspace/sleap/sleap/gui/dialogs/dlc_shortcuts_reference.py` —
    `DLCShortcutsReferenceDialog(QtWidgets.QDialog)` with a
    non-modal two-column `QTableWidget` (Key → Action).
    Module-level `DLC_SHORTCUT_ENTRIES: list[tuple[str, str]]`
    curated list seeded from TASKS.md guidance
    (`add instance default`, `add instance copy prior`,
    `frame prev`, `frame next`, `save`, `clear selection`).
    Bindings resolved at `_build_ui()` time via `Shortcuts()` so
    the dialog reflects the live user-cached yaml — entries whose
    binding is empty are silently dropped.
  - `workspace/sleap/sleap/gui/app.py` —
    - New `helpMenu.addAction("DLC Shortcuts",
      self._show_dlc_shortcuts_reference)` right below the existing
      `"Keyboard Shortcuts"` line in `_create_menus`.
    - New `_show_dlc_shortcuts_reference` method that instantiates
      the dialog, stashes it on `self._dlc_shortcuts_dialog` to
      prevent Python GC of the non-modal widget, then calls
      `.show()` + `.raise_()`.
- **Why `Shortcuts()` over re-parsing `shortcuts.yaml`:** the class
  already handles the cache-vs-package shortcut precedence
  (`util.get_config_yaml` reads from `~/.sleap/1.6.2/shortcuts.yaml`
  first). Re-parsing the packaged yaml would miss user customizations
  — the exact trap the T5/T6d memory entry warns about.
- **Why `QtCore.Qt.Tool` window flag:** without it, a non-modal
  `QDialog.show()` on Windows tends to stack behind the main
  window and look like it didn't open. `Tool` keeps the dialog
  floating above the parent without blocking input.
- **Why a MainWindow method instead of an AppCommand:** matches the
  existing `_show_keyboard_shortcuts_window` pattern (direct
  `MainWindow._show_xxx` for simple dialog openers). Adding an
  `AppCommand` would be ~20 lines of boilerplate for no gain — no
  undoable edit, no command-layer reuse.
- **Headless smoke test (QT_QPA_PLATFORM=offscreen):** PASS.
  - `Shortcuts()` resolves each of the 6 curated entries to
    `('1', '2', 'W', 'S', 'Ctrl+S', 'Esc')` — confirms T6d's
    rebindings are picked up live.
  - `DLCShortcutsReferenceDialog()` builds a 6-row, 2-column
    `QTableWidget`; `isModal() == False`; `windowTitle() == "DLC Shortcuts"`.
  - `import sleap.gui.app` → exits 0.
- **Pending manual verification:**
  1. `uv run sleap-label` → Help → "DLC Shortcuts" → non-modal
     dialog opens floating above the main window; table shows
     6 rows with the mapping above; main window still accepts
     input while the dialog is open.
  2. Close via the Close button or the window X → dialog
     dismisses; reopening shows the same content.
  3. Edit `~/.sleap/1.6.2/shortcuts.yaml` (e.g., change
     `save: Ctrl+S` to `save: Ctrl+Shift+S`) → reopen dialog
     → the `save` row reflects the new binding without a SLEAP
     restart (display-only; application of the shortcut still
     requires restart as with the upstream editor).
  4. Menu structure check: Help menu shows both "Keyboard
     Shortcuts" (editor) and "DLC Shortcuts" (reference) as
     separate entries; former still opens the editable dialog,
     latter opens the reference.

## T7. DLC CSV export — single-animal

- **Status:** 🔵 implementation complete, awaiting user acceptance via
  manual GUI test (2026-04-21).
- **Occluded/unplaced semantics chosen (from T7 options surfaced pre-code):**
  option (A) — both `visible=False` and NaN coordinates collapse to empty
  CSV cells. Matches the T6b/T6c numerator (if a point is not counted in
  `labeled/total`, it is not written to the CSV either). Falls out for
  free: `Instance.numpy()` returns NaN for non-visible points, and pandas'
  default `to_csv` writes NaN as empty.
- **Finding — MUST_KNOW.md §3A diagram is slightly wrong:** the doc shows
  header rows with 3 leading empty cells and a 3-column index (`labeled-data`,
  `<folder>`, `<img>`). The real reference CSVs under
  `PigFarm_Sow-jiale-2026-02-08/labeled-data/<folder>/CollectedData_jiale.csv`
  have **one** leading cell and a **combined-path single index column** —
  exactly the shape `pandas.DataFrame.to_csv()` produces for a single-level
  row index with a 3-level column MultiIndex. Same pattern as the MUST_KNOW
  §2 skeleton-shape amendment flagged during T5. Worth amending
  MUST_KNOW.md §3A in a follow-up; implementation matches the reference.
- **Changes:**
  - New file `workspace/sleap/sleap/io/format/dlc_csv.py` — `DLCCSVAdaptor`
    mirroring the shape of `sleap/io/format/csv.py`'s `CSVAdaptor`. Single
    `write(filename, source_object, scorer, folder_name, video=...)`
    classmethod. Builds rows keyed by `f"labeled-data/{folder_name}/{img}"`,
    one per `LabeledFrame` whose user-instances list is non-empty, uses
    first user instance, pulls coords via `Instance.numpy()`. Reindexes
    columns to `MultiIndex.from_product([[scorer], bodyparts, ["x","y"]])`
    so the output's column order follows `skeleton.nodes` (which T5's
    wizard already builds from `config.yaml` — so config-yaml order is
    preserved end-to-end).
  - `workspace/sleap/sleap/gui/commands.py`
    - New `ExportDLCCSV(AppCommand)` — reads `provenance["labeler"]` and
      `provenance["image_folder"]`, validates both are present and the
      folder exists, calls the adaptor with
      `out = image_folder / f"CollectedData_{labeler}.csv"`. Falls back
      to a status-bar message on any missing prerequisite (same UX
      convention as T6e). Guards on `getattr(context.app, "statusBar",
      None)` so headless test paths don't crash.
    - New `CommandContext.exportDLCCSV()` method (one-liner delegating to
      `execute(ExportDLCCSV)`).
  - `workspace/sleap/sleap/gui/app.py` — added
    `add_menu_item(fileMenu, "export_dlc_csv", "Export DLC CSV...",
    self.commands.exportDLCCSV)` directly above the existing
    "Export NWB..." entry (so it sits just under the "Export Analysis
    CSV..." submenu, matching TASKS.md wording "next to existing
    Export Analysis CSV...").
- **Why not reuse the existing `ExportAnalysisFile` command (`commands.py:1421`):**
  that command opens a `QFileDialog` asking the user where to save. For a
  DLC project the output path is deterministic — `<image_folder>/CollectedData_<scorer>.csv`
  — so asking the user would only invite miskeyed paths. Mirroring the
  shape of `CSVAdaptor` as the adaptor class and using a dedicated one-click
  command keeps the UX tight.
- **Float-formatting note (investigated during verification diff):**
  Initial line-by-line diff vs. the reference showed trailing-digit
  differences (e.g. `280.59840519126135` vs `280.5984051912613`). When
  both strings are parsed by `pandas.read_csv`, they yield the *same*
  `float64` value — so the semantic content is identical even though the
  textual repr differs. The reference CSV was written when pandas used
  17-digit float format; our modern pandas writes the 16-digit
  shortest-round-trippable form. DLC's `convertcsv2h5` reads CSVs via
  pandas, so the parsed arrays are bit-identical. No action required.
- **Headless diff verification (2026-04-21):** built a `Labels` with a
  config-yaml-ordered skeleton (`left_ear, right_ear, torso, hip`) from
  the reference CSV's data, exported via the adaptor, then compared
  programmatically:
  - Header rows (first 3) byte-identical.
  - Row count (23), column count (9 incl. index), and row-path index
    (`labeled-data/<folder>/img<NNN>.png`) byte-identical.
  - All 156 float cells parse to bit-identical `float64` values (0 ULP
    difference via `pd.read_csv` on both files).
  - Empty-cell pattern (`,,` markers for occluded keypoints) matches
    every row — i.e. option (A) works as spec'd.
  - Occlusion synthetic test on `test.slp`: flipping `points['visible'][0] = False`
    for left_ear AND setting torso coords to NaN with visible=False both
    produced empty cells in the output row; other keypoints retained
    full precision.
- **Pending manual verification (interactive GUI):**
  1. Launch `uv run sleap-label` → File → New DLC Project → complete the
     wizard with the sow `config.yaml` and an existing DLC folder →
     label ≥1 frame (press `1`, place keypoints) → File → "Export DLC
     CSV..." → status bar reads
     "Exported DLC CSV: <image_folder>/CollectedData_jiale.csv" (5s).
  2. Open the exported CSV in a text editor → header rows
     (`scorer,jiale,...` / `bodyparts,...` / `coords,x,y,...`) match the
     reference; data row(s) present for every labeled frame.
  3. Mark a keypoint as occluded (right-click → Mark Occluded) → re-export
     → that keypoint's x,y cells are empty; others unchanged.
  4. Export with no labeled frames → status bar reports "No labeled
     frames in video. Skipping DLC CSV export: ..." (from the adaptor's
     early return) and no CSV is written.
  5. Open a non-DLC project (mp4-backed `.slp`) → File → "Export DLC
     CSV..." → status bar reads "Export DLC CSV: project is missing
     provenance `labeler` or `image_folder`..." and no CSV is written.
