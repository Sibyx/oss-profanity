# notebooks/

IP-008. Statistical pass + plot generation for the OpenCamp deck.

## Run

```bash
# from repo root, with the dev env active
pip install -r requirements-dev.txt
jupyter execute notebooks/ip-008-results.ipynb
```

Or interactively:

```bash
jupyter lab notebooks/ip-008-results.ipynb
```

The notebook reads `MONGO_URI` from the environment (defaults to
`mongodb://localhost:27017/profanity`), pulls the `done` cohort, runs
the five a-priori Mann-Whitney U tests + Bonferroni correction at
α/5 = 0.01, writes eight PNGs into `presentation/public/images/plots/`,
and dumps the numerical record to `presentation/results.json`.

## What the notebook is NOT

- Not new pipeline code. It only reads `code_analysis` documents that
  IP-007 has already populated.
- Not the paper. The paper-grade analysis (mixed-effects model, BH-FDR
  in the appendix, NSFW sensitivity) is tracked in `docs/IDEAS.md`.

## Why a notebook

It's the artefact for the talk. Outputs are committed
(`Q5/B` resolution) so a reviewer can read the numbers from GitHub
without running anything.

## See also

- [IP-008 proposal](../docs/proposals/posts/ip-008-aggregation-and-plots.md)
- [`docs/NOTES.md`](../docs/NOTES.md) — slide-by-slide edits driven by these results
- [`presentation/slides.md`](../presentation/slides.md) — the deck the plots feed
