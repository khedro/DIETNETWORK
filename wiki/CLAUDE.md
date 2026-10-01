# Wiki schema — DIETNETWORK

This directory is an LLM-maintained wiki for the DIETNETWORK repo, following the
pattern in [../llm-wiki.md](../llm-wiki.md). Humans read it; the LLM writes and
maintains it. This file is the schema: read it before touching any wiki page.

## Layers

| Layer | Where | Rule |
|---|---|---|
| Raw sources | `../DIETNETWORK_Publication.pdf` (the theory), the repo's code and docs | **Immutable.** Never edit the PDF. Never edit code as part of wiki work. |
| Wiki | `wiki/**/*.md` | LLM-owned. Create, rewrite, and cross-link freely. |
| Schema | `wiki/CLAUDE.md` (this file) | Co-evolved with the user. Change only when the user agrees. |

The publication is the **theory of record**. The code is the **implementation**.
When they disagree, do not "fix" either one: record the disagreement in
[analysis/paper-vs-code.md](analysis/paper-vs-code.md) and cross-link it from
the affected pages.

## Directory layout

```
wiki/
  CLAUDE.md        schema (this file)
  index.md         catalog of every page, one line each, by category
  log.md           append-only chronological log
  overview.md      top-level synthesis: what the repo is and how the pieces fit
  sources/         one summary page per raw source (paper, README, deploy docs)
  concepts/        ideas from the theory (architecture, input dropout, attribution...)
  entities/        concrete things: datasets, populations, baselines, tools
  code/            how a part of the repo works, anchored to file paths
  analysis/        syntheses, comparisons, contradictions, open questions
```

## Page conventions

- Every page starts with YAML frontmatter:
  ```yaml
  ---
  title: <Title>
  type: source | concept | entity | code | analysis | overview
  sources: [paper, code]          # which raw layers back this page
  updated: YYYY-MM-DD
  ---
  ```
- One `# Title` heading, then a 1–3 sentence summary before any detail.
- Links are relative markdown links (`[Input dropout](../concepts/input-dropout.md)`),
  which work in VS Code, GitHub and Obsidian alike. Link generously.
- **Cite everything.**
  - Paper: `(Paper p.1464)` using the journal page numbers printed on the PDF
    (AJHG 113, pp. 1461–1477). Figures/tables: `(Paper Fig. 2C)`, `(Paper Table 1)`.
  - Code: a relative link to the file, with a line anchor when useful:
    `[infer.sh:62](../../Dietnet_inference/infer.sh#L62)`.
- Mark anything not verified against a source as **(unverified)**.
- Put a `## See also` list at the bottom of each page.

## Operations

**Ingest** (new source, or a significant code change):
1. Read the source in full.
2. Write or update its page in `sources/`.
3. Update every affected `concepts/`, `entities/`, `code/` page. A single source
   often touches 5–15 pages.
4. Check it against the paper; add any disagreement to `analysis/paper-vs-code.md`.
5. Update `index.md`. Append to `log.md`.

**Query**: read `index.md` first, then the relevant pages, then answer with
citations. If the answer is reusable (a comparison, an explanation, a found
connection), file it as a new page in `analysis/` and log it.

**Lint** (on request): look for contradictions between pages, stale claims after
code changes, orphan pages, concepts mentioned without a page, broken links, and
`(unverified)` claims that can now be checked. Log the pass.

## Log format

Each entry in `log.md` starts with a greppable header:

```
## [YYYY-MM-DD] ingest | <source>
## [YYYY-MM-DD] query | <question>
## [YYYY-MM-DD] lint | <scope>
```

`grep "^## \[" wiki/log.md | tail -5` shows the last five entries.
