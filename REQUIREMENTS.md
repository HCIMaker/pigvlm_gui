I'm building a SLEAP-like keypoint labeling GUI that exports DeepLabCut-compatible labels. 

Requirements:
- We do not build from scratch, we will add one option in the existing sleap gui called "customized" with updated functionalities based on the existing sleap-gui: https://github.com/talmolab/sleap
    - I can handle this program to other people, and they can also label.
    - The program should return meta data including labeler name, date of labeling, and which dataset is being labelled.
    - It should accept a folder of images, and consider them as an integrity instead of taking them as separate 1-frame videos.
    - Define skeleton via YAML config (keypoint names + edges)
    - Support multiple instances (animals) per frame
    - Export to DeepLabCut CSV and HDF5 format
    - Able to visualize the labeled image

Plan out the full project and generate these files:
1. CLAUDE.md — session bootstrap instructions
2. docs/TASKS.md — granular task list with acceptance criteria
3. docs/PROGRESS.md — The file that claude code must update after finishing/stucking in each task with note.
4. docs/MUST_KNOW.md - The features of how dlc consuming dataset.

Each task should be small enough to complete in one focused session.
List dependencies between tasks. Order them so I can test 
incrementally — every task should produce something I can see or verify.