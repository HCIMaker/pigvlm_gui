# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Windows-side staging area for preparing **DeepLabCut (DLC) keypoint-tracking datasets** for pig behavior analysis (sow and piglets). The actual model training happens on a Linux server; this repo owns everything *up to* producing the `CollectedData_<scorer>.csv` that DLC's `convertcsv2h5` consumes.

Read `must_know.md` first — it is the authoritative spec for the DLC CSV format (3-row header for single-animal, 4-row for multi-animal, how occluded keypoints are represented, folder/filename conventions, and the server-side post-processing commands). Do not re-derive those rules from code.

## Key Docs — MUST READ BEFORE ANY TASK
- `docs/MUST_KNOW.md` — Related rules of how deeplabcut consume ground truth data.
- `docs/TASKS.md` — Task list with status and acceptance criteria
- `docs/PROGRESS.md` — Record the current working state of CLAUDE. Update after every single task is tested and done successfully with note.

## Key Reference - MUST READ BEFORE CODING
- sleap.ai: C:\Jiale\pigvlm_gui\pigvlm_gui\sleap-develop (local) ; https://github.com/talmolab/sleap (github)
- deeplabcut: https://github.com/deeplabcut/deeplabcut

## Key Rules
- Use uv to create a virtual environment inside C:\Jiale\pigvlm_gui\pigvlm_gui\workspace for project implementation
- Do not modify other code file outside workspace directory, they are here as reference.
- We do not create from scratch, we modify based on the sleap gui with as indicated in the reference

## Conventions

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.
