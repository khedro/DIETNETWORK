# Wiki index

Catalog of every page. Read this first when answering a question. Schema and
workflows: [CLAUDE.md](CLAUDE.md). History: [log.md](log.md).

## Start here
- [Overview](overview.md) — what the repo is, the idea in five lines, the three code layers

## Sources
- [Publication](sources/publication.md) — AJHG 2026 paper summary: claims in order, key numbers (theory of record, immutable)
- [Repo docs](sources/repo-docs.md) — README, deployPlan.md, DEPLOYMENT.md and their known errors

## Concepts
- [Diet Network architecture](concepts/diet-network-architecture.md) — aux net generates fat-layer weights; exact layer shapes
- [SNP embedding](concepts/snp-embedding.md) — per-population genotype frequencies (SNPs × 72), per fold
- [Input dropout](concepts/input-dropout.md) — p = 0.995, why it drives generalization
- [Missing-SNP handling](concepts/missing-snp-handling.md) — fill, mean-impute, standardize, rescale; PUR drift
- [Harmonized SNP set](concepts/harmonized-snp-set.md) — how the 229,986 SNPs were chosen; ID and allele conventions
- [15-model ensemble](concepts/ensemble.md) — 5 folds × 3 repeats, voting, class index order
- [Latent representations](concepts/latent-representations.md) — 1,500-d last-hidden-layer PCA; North Africans
- [Feature attribution](concepts/feature-attribution.md) — Saliency/IG/DeepLift/GradientSHAP, A_ord/A_rev, Table 1
- [Attribution baselines](concepts/attribution-baselines.md) — genotype-average chosen; Table 2
- [F_ST vs attributions](concepts/fst.md) — model uses differentiated SNPs; "evidence against" for admixed groups

## Entities
- [Datasets](entities/datasets.md) — 1KGP, CaG (GSA/Omni/Axiom), MHIB, AoU: sizes, labels, SNP overlap
- [Populations](entities/populations.md) — the 24 classes, index order, per-population notes
- [Benchmark methods](entities/benchmark-methods.md) — PCA+RF, Rye, and related tools

## Code
- [Inference pipeline](code/inference-pipeline.md) — `infer.sh` stages, real argument order, gotchas
- [Training pipeline](code/training-pipeline.md) — create → partition → stats → embedding → train.py
- [Worker pipeline](code/worker-pipeline.md) — upload → PLINK → 4 guardrails → infer.sh → parse; retention
- [Web platform](code/web-platform.md) — FastAPI/SvelteKit/Celery topology, governance
- [Deployment](code/deployment.md) — dev, local-test (ICM), Arbutus via Pulumi

## Analysis
- [Paper vs code](analysis/paper-vs-code.md) — matches, gaps, doc errors, open questions
- [Spec status](analysis/spec-status.md) — specifications.docx item by item: done / partial / not done, suggested order
