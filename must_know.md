# DeepLabCut Labeling Interface — Must-Know Reference

This document contains everything needed to build a custom keypoint labeling interface that outputs DeepLabCut-compatible CSV files. Inject this into your development session as context.

---

## 1. Input: A Folder of Images

The labeling interface receives a **folder of pre-extracted image frames** (PNG files). Frame extraction from video is already handled upstream by DLC or custom scripts — the labeler does NOT need to deal with video files.

Image naming convention: `img<frame_index>.png` with zero-padding to 3 digits.
Examples: `img020.png`, `img099.png`, `img579.png`

The folder name corresponds to the source video name (without `.mp4` extension). For example:
```
ch07_Crate08_20220428080001_20220428100000_clip_00h15m00s/
  img020.png
  img099.png
  img104.png
  ...
```

---

## 2. Configuration: `config.yaml`

The labeler must read a DLC `config.yaml` to know what to annotate. Here are the critical fields:

### Single-Animal Project (`multianimalproject: false`)

```yaml
Task: PigFarm_Sow
scorer: jiale
multianimalproject: false

bodyparts: [left_ear, right_ear, torso, hip]

skeleton:
- [left_ear, torso]
- [right_ear, torso]
- [torso, hip]

dotsize: 12
colormap: rainbow
pcutoff: 0.6
```

**What the labeler needs from this:**
- `scorer` — used in CSV header row (always the same value repeated)
- `bodyparts` — the list of keypoints to place on each frame
- `skeleton` — edges to draw between keypoints for visual guidance
- `multianimalproject` — determines which CSV format to use (3-row vs 4-row header)

### Multi-Animal Project (`multianimalproject: true`)

```yaml
Task: PigFarm_Multi
scorer: jiale
multianimalproject: true

individuals: [sow, piglet1, piglet2, piglet3, piglet4, piglet5, piglet6,
  piglet7, piglet8, piglet9, piglet10, piglet11, piglet12]
multianimalbodyparts: [head, torso, hip]
bodyparts: MULTI!

skeleton:
- [head, torso]
- [torso, hip]
```

**What the labeler needs from this:**
- `individuals` — the list of trackable entities (each gets its own set of keypoints)
- `multianimalbodyparts` — keypoints per individual (replaces `bodyparts` when `bodyparts: MULTI!`)
- When `bodyparts` is the literal string `MULTI!`, use `multianimalbodyparts` instead

---

## 3. Output Format: CSV

The labeler outputs a single file named `CollectedData_<scorer>.csv` (e.g., `CollectedData_jiale.csv`) placed in the same folder as the images.

### 3A. Single-Animal CSV Format

**Structure:** 3 header rows + 1 data row per labeled frame.

```csv
scorer,,,jiale,jiale,jiale,jiale,jiale,jiale,jiale,jiale
bodyparts,,,left_ear,left_ear,right_ear,right_ear,torso,torso,hip,hip
coords,,,x,y,x,y,x,y,x,y
labeled-data,<folder_name>,img020.png,,,300.579,506.171,628.237,449.275,880.632,444.383
labeled-data,<folder_name>,img099.png,280.598,521.695,330.612,495.885,617.611,441.220,872.099,426.441
labeled-data,<folder_name>,img104.png,,,304.208,412.099,614.427,439.986,897.702,434.513
```

**Key rules:**
- First 3 columns of every row are index columns: `labeled-data`, `<folder_name>`, `<image_filename>`
- The header rows also have 3 empty cells at the start (matching the index columns), written as `scorer,,,` / `bodyparts,,,` / `coords,,,`
- Each bodypart occupies 2 value columns: `x, y`
- Column order follows `bodyparts` list from config: `[left_ear_x, left_ear_y, right_ear_x, right_ear_y, torso_x, torso_y, hip_x, hip_y]`
- The `scorer` header row repeats the scorer name for every value column
- The `bodyparts` header row repeats each bodypart name twice (once for x, once for y)
- The `coords` header row alternates `x, y, x, y, ...`
- **Total value columns** = `len(bodyparts) * 2`

### 3B. Multi-Animal CSV Format

**Structure:** 4 header rows + 1 data row per labeled frame.

```csv
scorer,,,jiale,jiale,jiale,jiale,jiale,jiale,jiale,jiale,jiale,jiale,jiale,jiale,...
individuals,,,sow,sow,sow,sow,sow,sow,piglet1,piglet1,piglet1,piglet1,piglet1,piglet1,...
bodyparts,,,head,head,torso,torso,hip,hip,head,head,torso,torso,hip,hip,...
coords,,,x,y,x,y,x,y,x,y,x,y,x,y,...
labeled-data,<folder_name>,img009.png,350.673,342.528,610.641,318.092,892.171,325.780,476.650,517.994,,,414.914,608.776,...
```

**Key rules:**
- Same index column structure (first 3 columns)
- 4 header rows instead of 3: `scorer` → `individuals` → `bodyparts` → `coords`
- Column ordering: all bodyparts for individual 1, then all bodyparts for individual 2, etc.
- For each individual: `[head_x, head_y, torso_x, torso_y, hip_x, hip_y]`
- **Total value columns** = `len(individuals) * len(multianimalbodyparts) * 2` (e.g., 13 * 3 * 2 = 78)

---

## 4. Handling Missing/Occluded Keypoints

- When a keypoint is **not visible or not labeled**, leave BOTH x and y as empty cells in the CSV (which DLC reads as NaN)
- When an entire individual is **not present** in a frame (e.g., a piglet not visible), leave ALL of that individual's columns empty
- A frame can have partial annotations — some keypoints labeled, others empty
- Example: in `img020.png` above, `left_ear` x,y are both empty (the sow's left ear was occluded), while the other 3 keypoints are labeled

---

## 5. Output Folder Structure

After labeling, the folder should look like:

```
<folder_name>/
  img020.png
  img099.png
  img104.png
  ...
  CollectedData_jiale.csv    <-- labeler output
```

This folder gets placed into the DLC project at:
```
PigFarm_Sow-jiale-2026-02-08/labeled-data/<folder_name>/
```

The `<folder_name>` must exactly match a video entry in `config.yaml`'s `video_sets` (the video filename without `.mp4`).

---

## 6. CSV Generation Reference (Python)

Here is pseudocode for generating a valid single-animal CSV:

```python
import csv

def write_single_animal_csv(output_path, scorer, bodyparts, folder_name, annotations):
    """
    annotations: dict mapping image_filename -> dict mapping bodypart -> (x, y) or None
    Example: {"img020.png": {"left_ear": None, "right_ear": (300.58, 506.17), ...}, ...}
    """
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)

        # Header row 1: scorer
        row1 = ['scorer', '', ''] + [scorer] * (len(bodyparts) * 2)
        writer.writerow(row1)

        # Header row 2: bodyparts
        row2 = ['bodyparts', '', '']
        for bp in bodyparts:
            row2.extend([bp, bp])
        writer.writerow(row2)

        # Header row 3: coords
        row3 = ['coords', '', ''] + ['x', 'y'] * len(bodyparts)
        writer.writerow(row3)

        # Data rows (sorted by image filename)
        for img_file in sorted(annotations.keys()):
            row = ['labeled-data', folder_name, img_file]
            for bp in bodyparts:
                coord = annotations[img_file].get(bp)
                if coord is None:
                    row.extend(['', ''])  # NaN / unlabeled
                else:
                    row.extend([coord[0], coord[1]])
            writer.writerow(row)
```

For multi-animal, add the `individuals` header row and nest the loop:

```python
def write_multi_animal_csv(output_path, scorer, individuals, bodyparts, folder_name, annotations):
    """
    annotations: dict mapping image_filename ->
        dict mapping individual -> dict mapping bodypart -> (x, y) or None
    """
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        n_cols = len(individuals) * len(bodyparts) * 2

        # Header row 1: scorer
        writer.writerow(['scorer', '', ''] + [scorer] * n_cols)

        # Header row 2: individuals
        row2 = ['individuals', '', '']
        for ind in individuals:
            row2.extend([ind] * (len(bodyparts) * 2))
        writer.writerow(row2)

        # Header row 3: bodyparts
        row3 = ['bodyparts', '', '']
        for _ in individuals:
            for bp in bodyparts:
                row3.extend([bp, bp])
        writer.writerow(row3)

        # Header row 4: coords
        writer.writerow(['coords', '', ''] + ['x', 'y'] * (len(individuals) * len(bodyparts)))

        # Data rows
        for img_file in sorted(annotations.keys()):
            row = ['labeled-data', folder_name, img_file]
            for ind in individuals:
                for bp in bodyparts:
                    coord = annotations[img_file].get(ind, {}).get(bp)
                    if coord is None:
                        row.extend(['', ''])
                    else:
                        row.extend([coord[0], coord[1]])
            writer.writerow(row)
```

---

## 7. Common Pitfalls

1. **The first 3 columns are NOT data columns** — they are row indices (`labeled-data`, folder name, image filename). Do not treat them as part of the annotation data.

2. **Folder name must match exactly** — the folder name in the CSV rows and the actual directory name must be identical to the video name (without `.mp4`) registered in `config.yaml`.

3. **Image filenames must use DLC convention** — `img<NNN>.png` where NNN is the frame index. Not `frame_000050.png`, not `050.png`.

4. **Coordinate precision** — DLC uses sub-pixel float coordinates. Preserve full precision (no rounding to integers).

5. **Row ordering** — rows should be sorted by image filename for consistency, though DLC does not strictly require it.

6. **No trailing commas or extra whitespace** — standard CSV formatting.

7. **The scorer name must match** — the scorer in the CSV header must match the `scorer` field in `config.yaml`, and must also match the filename suffix (`CollectedData_<scorer>.csv`).

---

## 8. Reference Files

To verify your output format, compare against these reference files (download from server):

```bash
# Single-animal reference CSV
scp server:~/Jiale_Research/PigVLM/PigFarmDataProcessing/deeplabcut/PigFarm_Sow-jiale-2026-02-08/labeled-data/ch07_Crate08_20220428080001_20220428100000_clip_00h15m00s/CollectedData_jiale.csv ./ref_single_animal.csv

# Multi-animal reference CSV
scp server:~/Jiale_Research/PigVLM/PigFarmDataProcessing/deeplabcut/PigFarm_Multi-jiale-2026-02-08/labeled-data/ch07_Crate08_20220430040000_20220430060000_clip_00h35m00s/CollectedData_jiale.csv ./ref_multi_animal.csv

# Single-animal config
scp server:~/Jiale_Research/PigVLM/PigFarmDataProcessing/deeplabcut/PigFarm_Sow-jiale-2026-02-08/config.yaml ./ref_sow_config.yaml

# Multi-animal config
scp server:~/Jiale_Research/PigVLM/PigFarmDataProcessing/deeplabcut/PigFarm_Multi-jiale-2026-02-08/config.yaml ./ref_multi_config.yaml
```

---

## 9. Post-Labeling Workflow (Server-Side)

After the labeler produces `CollectedData_<scorer>.csv` and the file is uploaded to the server into the correct `labeled-data/<folder>/` directory:

1. Convert CSV to H5 (required by DLC for training):
   ```bash
   conda activate dlc
   python 2_create_project/csv_to_h5_official.py
   ```

2. Verify labels visually:
   ```bash
   python 2_create_project/check_labels_from_sleap.py
   ```

3. Create training dataset and train:
   ```bash
   python 3_training/create_training_dataset.py --project sow
   CUDA_VISIBLE_DEVICES=0 python 3_training/train.py --project sow
   ```
