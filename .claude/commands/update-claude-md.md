---
description: Sync CLAUDE.md with recent repo changes — fixes stale docs and adds missing structural info
allowed-tools: Read, Grep, Glob, Bash, Edit, Agent
---

# Update CLAUDE.md

Keep CLAUDE.md in sync with the actual codebase. This is NOT a full rewrite — it's a targeted sync that fixes what's stale and adds what's missing.

The user may pass optional instructions after the command (e.g., "last 10 commits", "focus on paper trading changes"). Use these to scope the work.

## Philosophy

CLAUDE.md exists so that a fresh Claude session can understand the repo without re-exploring it. When code changes make CLAUDE.md wrong or incomplete, a future session will be actively misled. The goal is to fix exactly those cases — nothing more.

**Update when the change would mislead a future session.** A renamed function that's documented in CLAUDE.md — update it. A new API endpoint — add it. A refactored internal helper — skip it, CLAUDE.md doesn't track internals.

**Don't document every change.** Bug fixes, minor refactors, style changes, and implementation details don't belong in CLAUDE.md. Only structural/architectural changes that affect how someone understands or navigates the project.

## Step 1: Gather what changed

Run these in parallel to understand recent changes:

1. **Git diff summary** — what files changed and how (uncommitted by default):
   ```bash
   git diff --stat          # unstaged changes
   git diff --cached --stat # staged changes
   ```
   If the user specifies a commit range (e.g., "last 10 commits"), use `git diff HEAD~10 --stat` instead.

2. **New/deleted/untracked files** — structural changes:
   ```bash
   git diff --diff-filter=AD --name-only
   git diff --cached --diff-filter=AD --name-only
   git ls-files --others --exclude-standard  # untracked new files
   ```

3. **Changed function signatures and classes** in modified Python files:
   ```bash
   git diff -- '*.py' | grep -E '^\+.*(def |class )' | head -40
   git diff --cached -- '*.py' | grep -E '^\+.*(def |class )' | head -40
   ```

4. **Current CLAUDE.md** — read it fully so you know what's documented.

## Step 2: Identify what's stale or missing

Compare the git changes against CLAUDE.md. Look for these specific categories:

### Must update (actively misleading if left)
- **Files documented in Project Structure that were renamed, moved, or deleted**
- **API endpoints that were added, removed, or changed** (check routes.py changes)
- **Config changes** — new env vars, changed defaults, removed options
- **Dependencies** — new entries in requirements.txt
- **Changed data flows** — if how components connect has changed (e.g., scanner now calls a new module)
- **Database schema changes** — new tables, new columns, changed migration logic
- **Key design decisions that changed** — e.g., scoring went from 13 layers to 12, or paper trading rules changed

### Should add (would help a future session)
- **New subsystems or modules** not mentioned anywhere in CLAUDE.md
- **New key file relationships** — if a new hot path was created
- **Changed numbers/constants** documented in CLAUDE.md (max positions, scoring weights, etc.)

### Skip (not worth documenting)
- Internal implementation changes within existing functions
- Bug fixes that don't change behavior or interfaces
- Test file changes
- CSS/styling changes
- Comment or docstring updates
- Changes to files not mentioned in CLAUDE.md (unless they represent a new subsystem)

## Step 3: Draft targeted edits

For each stale or missing item, draft the minimal edit needed. Prefer:
- **Editing existing lines** over adding new sections
- **One-line updates** over paragraphs
- **Updating existing tables** (like the API endpoints table or the layer weights table) over prose

Format each proposed change as:

```
### Section: [which CLAUDE.md section]
**Why:** [one line — what changed in the code that makes this stale]
**Change:** [the edit — show old → new, or just the addition]
```

## Step 4: Apply changes

After drafting all changes, apply them to CLAUDE.md using the Edit tool. Make each edit individually so they're reviewable.

Do NOT:
- Rewrite entire sections when a line edit suffices
- Add verbose explanations — CLAUDE.md is a reference, not a tutorial
- Remove existing content unless it's actively wrong
- Add sections for things that can be derived from the code
- Change the overall structure or ordering of the file

## What each CLAUDE.md section tracks (reference)

Use this to know which section to update:

| Section | Tracks | Update when... |
|---------|--------|---------------|
| Architecture Overview | High-level system description | New subsystem added, mode of operation changed |
| Tech Stack | Languages, frameworks, tools | New dependency, tool swap, model change |
| Running the App | Commands to run things | New entry point, changed CLI args |
| Configuration | Env vars and defaults | New config option, changed default |
| Project Structure | File tree with descriptions | File added/removed/moved, role changed |
| Key Design Decisions | Why things are the way they are | Design changed (scoring layers, trading rules, etc.) |
| Paper Trading System | Trading mechanics | Rules changed (stops, sizing, gates, limits) |
| Validation Framework | Testing systems | New strategy, changed metrics |
| Database Schema | Tables and columns | New table, new column, migration change |
| API Endpoints | Endpoint table | Route added/removed/changed |
| Change Protocol | How to make changes | Don't touch unless user asks |
| Context Management | How to navigate the codebase | Hot paths changed, new key relationships |
| Development Notes | Gotchas and tips | New gotcha discovered |
