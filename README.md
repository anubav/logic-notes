Master source for the *Introduction to Logic* course notes. This is the
single, portable source of truth: section-specific course websites are
generated from this repo by `coursecraft`, not edited here directly.

## Editing

```
git clone <this repo>
cd logic-notes
quarto preview
```

That's it -- `quarto preview` renders everything in this repo (all
chapters and appendices), no profile needed. The instructor profile
(`--profile instructor`) adds a solutions appendix on top of this, but
requires cloning the private `logic-solutions` repo first; see
"Solutions" below.

### Conventions to know before editing by hand

- **One coarse file per chapter/appendix.** `chapters/01-....qmd`,
  `appendices/A-....qmd`. Don't split a chapter across multiple files --
  keeping it as one file is what lets Quarto resolve cross-references
  and citations while you preview, without needing a full book render.
- **Every revealable section needs a label.** A `##` heading that a
  course section might want to reveal/hide independently needs a
  `{#sec-<chapter-slug>-<heading-slug>}` label. `coursecraft` uses these
  labels to build each section's profile; an unlabeled `##` heading just
  travels along with whichever labeled section contains it.
- **`.lproof` blocks are raw text, not prose.** Each proof line must stay
  indented at least 4 spaces with its line number, on its own line. The
  formatting tool (see below) knows to leave these alone entirely --
  never hand-reformat one, and don't let a generic Markdown formatter
  (e.g. Prettier) touch this repo (see `.vscode/settings.json`).
- **Sentence-per-line formatting.** Files are formatted with one
  sentence per line (not column-wrapped) for clean git diffs. Turn on
  soft word-wrap in your editor for on-screen readability -- this
  doesn't change the file, just how it displays
  (`.vscode/settings.json` already does this for VS Code).
- **Exercises and inserts are shared, flat fragments**, pulled into
  chapters via `{{< include /exercises/name.qmd >}}` or
  `{{< include /inserts/... >}}`. A fragment file itself has no
  `{#sec-...}` label and isn't part of the chapter/section reveal
  scheme -- only whether an exercise is *assigned* is section-specific,
  and that's decided in a section's own `course.yaml`, not here.

## Formatting is automatic, not manual

Don't hand-format `.qmd` files. `chapter_tools.py` does it for you:

- **On save** (VS Code, if you installed the *Run on Save* extension --
  see `.vscode/settings.json`): reformats the file you just saved.
- **On commit**: a pre-commit hook reformats staged files and stops the
  commit for review if anything changed. One-time setup:
  ```
  pip install pre-commit
  pre-commit install
  ```
- **In CI**: `.github/workflows/check-format.yml` fails a PR if any
  tracked `.qmd` file isn't already correctly formatted -- the backstop
  for anyone who edited without the hook installed.

## Solutions

Solutions live in a **separate, private** repository, `logic-solutions`,
and are never committed here. It contains the raw per-exercise solution
fragments plus a `solutions-appendix.qmd` that assembles them (with
cross-references back to each exercise). Clone it into `solutions/`
(already gitignored):

```
git clone <logic-solutions repo url> solutions
quarto preview --profile instructor
```

Once cloned, `--profile instructor` picks up `solutions/solutions-
appendix.qmd` automatically and renders it as an appendix -- nothing
else to configure. Without it, `--profile instructor` fails with a
clear "file not found" error rather than silently omitting the
appendix, so it's obvious when the private repo hasn't been cloned yet.

To request access to `logic-solutions`, contact the repo owner.

## Layout

```
chapters/       one coarse .qmd per chapter
appendices/     one coarse .qmd per appendix (letters), or flat files
exercises/      shared exercise-prompt fragments (flat)
inserts/        shared worked-example fragments
static/         images, audio
solutions/      gitignored -- private repo clones in here
assets/         styles, macros, fonts, header includes
_extensions/    vendored Quarto extensions (lproof)
coursecraft.yml portability manifest -- see the coursecraft docs
```
