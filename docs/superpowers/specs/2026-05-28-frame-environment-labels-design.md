# Design — Frame-level environment labels (lying direction, heat lamp, food)

**Date:** 2026-05-28
**Status:** approved design, pending implementation plan
**Phase:** 7 (new) — extends the DLC labeling workflow built in T1–T17

## Motivation

Beyond per-keypoint annotation, the research needs three **general, frame-level**
observations recorded per image. These are not tied to any keypoint or skeleton —
they describe the scene:

1. **Lying direction** of the mother (sow) — which way she is lying.
2. **Heat lamp** — whether the heat lamp is on.
3. **Food level** — how much food is left in the tank.

The labeler should set these from dropdowns while labeling, the values must carry
forward from the prior frame to save time, persist in the `.slp` across sessions
(same as keypoints), and export to a **separate CSV** for downstream research use.

## The three labels and their value sets

| Column (display) | Storage key | Unset | Stored/CSV tokens | Dropdown display |
|---|---|---|---|---|
| `lying` | `lying` | `—` | `up`, `down`, `none` | same |
| `heat lamp` | `heat_lamp` | `—` | `on`, `off`, `not_clear` | `on`, `off`, `not clear` |
| `food` | `food` | `—` | `3`, `2`, `1`, `0` | `3 — very much`, `2 — middle`, `1 — almost done`, `0 — none` |

- **Tokens are space-free** (user requirement): what gets stored in the `.slp`
  and written to the CSV is always the canonical no-space token (`not_clear`,
  not "not clear"; `3`, not "very much"). The friendly text is **display-only**.
- Implemented via `QComboBox` `itemData` (canonical token) vs `itemText`
  (friendly display), so the display↔token mapping lives in one place.
- **Unset (`—`) is the default** and is distinct from real observations
  (`food=0` "empty tank", `heat_lamp=off`). Unset exports as an empty cell.
- `none` (lying) means "not lying / unclear" per the user's definition.

## Storage & persistence — `labels.provenance["frame_labels"]`

A dict keyed by **string** frame index, holding only the fields that are set:

```python
labels.provenance["frame_labels"] = {
    "1": {"lying": "up", "heat_lamp": "on", "food": "3"},
    "2": {"lying": "down"},          # only lying set; heat_lamp/food still unset
    # frames with nothing set: no key at all
}
```

**Persistence is guaranteed by the standard `.slp` save path — no extra
mechanism.** Verified against the installed `sleap_io` 0.6.5:

- Write: `slp.py:write_metadata` →
  `grp.attrs["json"] = np.bytes_(json.dumps(md, ...))`, where `md["provenance"]
  = labels.provenance`. JSON serializes the nested dict natively.
- Read: `slp.py:read_metadata` → `return json.loads(md.decode())`; the nested
  `frame_labels` dict is restored intact into `labels.provenance`.

This is the same store the keypoint labels travel in and the same path that
already persists `mode`, `dataset`, `labeler` (T4/T5 verified). So **save +
reopen restores the frame labels exactly, with no rework** — the user's explicit
requirement.

Design notes:
- **Keyed by `str(frame_idx)`**, not filename — matches how `LabeledFrame` is
  keyed, and survives T12's append-only folder sync (filename keys would break
  on a rename; index keys are stable because the ImageVideo list is frozen and
  only appended to).
- **Pruning:** clearing a cell back to unset removes that field key; an empty
  per-frame dict removes the frame key. Keeps the stored dict minimal and the
  CSV's "blank = unset" semantics exact.
- **Rejected alternatives:** (a) patching `sleap_io.LabeledFrame` to add a
  metadata field — out of scope, cannot modify dependencies (CLAUDE.md); (b) a
  sidecar JSON file — would not live inside the `.slp`, trivially desyncs from
  the labels it describes.

## Editing UI — three inline dropdown columns in the DLC Image Frames dock

Column order (single-config):
`frame | image | points | lying | heat lamp | food | labeled`

Dual-config (T13/T15) — the three slot in before `labeled`:
`frame | image | sow_pts | piglet_pts | lying | heat lamp | food | labeled`

- `DLCFramesTableModel` (`workspace/sleap/sleap/gui/dataviews.py`) gains the
  three columns in both `_DLC_SINGLE_COLUMNS` and `_DLC_DUAL_COLUMNS`.
- `object_to_items` populates each cell's display string from
  `provenance["frame_labels"]` (unset → `—`).
- `flags()` returns `ItemIsEditable` for the three label columns only (the
  existing columns stay read-only).
- A `QStyledItemDelegate` (`FrameLabelDelegate`, in
  `workspace/sleap/sleap/gui/widgets/docks.py`) is installed on the dock's table
  for those columns; `createEditor` returns a `QComboBox` populated per-column,
  `setModelData` commits the selection.
- The displayed header for `heat_lamp` reads **"heat lamp"** (header override in
  the model if `properties` keys are shown verbatim).

## Edit integration — a small `SetFrameLabel` command

`setData()` routes the dropdown change through a new
`SetFrameLabel(EditCommand)` in `workspace/sleap/sleap/gui/commands.py`:

- `does_edits = True` → the project goes **dirty** so the next save persists the
  change, matching how every other mutation in this fork marks dirty (rather
  than a bespoke flag). (This SLEAP fork has no functional undo — the
  changestack only tracks the unsaved-changes flag — so dirty-tracking, not
  undo, is what guarantees the save/reload requirement.)
- `do_action(params={"frame_idx", "field", "value"})` writes/prunes
  `provenance["frame_labels"]` as described above.
- After execution, refresh just that row's three cells (one `dataChanged` over
  the label-column span), preserving scroll/selection — same pattern as
  `update_row_for_frame` (T6b/T6c).

## Copy-from-prior — folded into `2` (Copy Prior Frame)

Extend `add_all_instances_copying_prior_frame` (`app.py:819`):

- After the existing instance-copy loop, read the **prior labeled frame's**
  `frame_labels` entry and write each **set** field onto the current frame via
  `SetFrameLabel`. Fields unset in the prior frame are left untouched on the
  current frame (nothing to copy).
- Runs **even when `n_to_copy == 0`** (current frame already has its instances),
  so labels still carry forward on a single keypress.
- Each set field is copied via one `SetFrameLabel` command (so the project is
  marked dirty once per copied field — harmless; no functional undo exists).

## Export — `FrameLabels_<scorer>.csv`, folded into Export DLC CSV

A new writer `workspace/sleap/sleap/io/format/frame_labels_csv.py`, mirroring the
shape of `dlc_csv.py`:

- **Plain CSV, no multi-row header.** Columns: `image, lying, heat_lamp, food`.
- **One row per image** in the folder, in the video's frame order (the "every
  image" choice). Unset fields → empty cell. All values are the space-free
  canonical tokens: `food` as `3/2/1/0`, `lying` as `up/down/none`, `heat_lamp`
  as `on/off/not_clear`.
- Filename `FrameLabels_<scorer>.csv` where `<scorer>` is
  `provenance["labeler"]`.

Wired into the existing `ExportDLCCSV.do_action` (`commands.py:1272`) so **one
"Export DLC CSV" action writes the keypoint CSV(s) AND the frame-labels CSV**:

- **Single-config (`mode == "dlc"` / absent):** write `FrameLabels_<scorer>.csv`
  into `provenance["image_folder"]`, next to `CollectedData_<scorer>.csv`.
- **Dual (`mode == "dlc_dual"`):** write **one** `FrameLabels_<scorer>.csv` into
  `provenance["image_folder"]` (the shared source image folder). Not duplicated
  into the two project dirs — flagged as a future tweak if needed.
- Frame-labels export is independent of whether keypoints exist; it should write
  even on a project with frame labels but no instances (still useful research
  data). Status-bar message extended to mention the frame-labels file.

## Files touched

| File | Change |
|---|---|
| `workspace/sleap/sleap/gui/dataviews.py` | 3 columns in both layouts; `flags()` editable; `setData()` → command; populate cells from provenance; header override for "heat lamp"; refresh helper |
| `workspace/sleap/sleap/gui/widgets/docks.py` | install `FrameLabelDelegate` (QComboBox) on the DLC frames table |
| `workspace/sleap/sleap/gui/commands.py` | new `SetFrameLabel(EditCommand)`; extend `ExportDLCCSV` to also write the frame-labels CSV |
| `workspace/sleap/sleap/gui/app.py` | extend `add_all_instances_copying_prior_frame` to carry the 3 labels |
| `workspace/sleap/sleap/io/format/frame_labels_csv.py` | **new** plain-CSV writer |

## Acceptance criteria

1. **Dropdowns appear & edit.** Open a DLC project → DLC Image Frames dock shows
   `lying | heat lamp | food` columns; each cell opens a dropdown with the listed
   values plus `—`; picking a value updates the cell.
2. **Persistence (the key requirement).** Set values on ≥3 frames → `Ctrl+S` →
   close → reopen the `.slp`: the same cells show the same values (no rework).
   Confirm `provenance["frame_labels"]` round-trips via a headless
   `save_file → load_file` test.
3. **Unset vs real value.** A frame left untouched shows `—` and exports as a
   blank cell; a frame set to `food=0` shows `0` and exports `0`.
4. **Copy-prior carries labels.** On frame N set `lying=up, heat_lamp=on,
   food=2`. On frame N+1 press `2` → N+1 inherits those three values (in addition
   to copied keypoints). Works whether or not N+1 needed new instances.
   Overriding one value on N+1 and pressing `2` on N+2 carries N+1's values.
5. **Export.** File → Export DLC CSV → `FrameLabels_<scorer>.csv` is written next
   to the keypoint CSV, one row per image, header `image,lying,heat_lamp,food`,
   unset cells blank, values matching the dropdowns. Keypoint CSV(s) unchanged.
6. **Dual mode.** Same behavior; columns slot in before `labeled`; one
   `FrameLabels_<scorer>.csv` written into the shared image folder.
7. **No regression** for non-DLC projects (mp4-backed `.slp`): the dock is empty
   as before; no frame-label columns appear where there are no image rows.

## Out of scope

- Keyboard shortcuts for setting label values (dropdown-only for now).
- Writing the frame-labels CSV into both dual-mode project dirs.
- Server-side consumption of the frame-labels CSV (downstream research concern).
