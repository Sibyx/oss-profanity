# OpenCamp 2026 deck

60-minute Slidev deck for [Bratislava OpenCamp 2026](https://pretalx.opencamp.sk/bratislava-opencamp-2026/talk/DHS8R3/),
2026-04-25 10:00, Aula Magna. Talk title: *"Vulgarizmy, otvorený kód a
jeho kvalita"* (Profanity, open-source code, and its quality).

Slide copy is English; delivery is Slovak; speaker notes are English
(hit `o` in Slidev presenter mode).

## Run

```bash
cd presentation/opencamp
npm install
npm run dev
```

Opens `http://localhost:3030/`. Press `o` for the overview, `s` for
speaker mode.

## Refresh numbers

Every number on a Results-act slide traces back to a Mongo aggregation
in `scripts/presentation_stats.py`. Regenerate before each dry run:

```bash
# From the repo root:
python -m scripts.presentation_stats --json > presentation/opencamp/stats.json

# Or the terminal summary:
python -m scripts.presentation_stats
```

`stats.json` is gitignored. The slides currently bake the numbers from
the 2026-04-25 run in directly — update the Results slides manually
from a fresh `stats.json` if the cohort has changed since.

## Export

```bash
npm run build       # static HTML → dist/
npm run export      # PDF         → dist/slides.pdf
```

Both artefacts are gitignored. Print the PDF before the talk — it's
the offline backup if the Aula Magna Wi-Fi misbehaves.

## Structure

Seven acts across ≈59 slides:

| Act | Minutes | Slides | Role |
|---|---|---|---|
| I — Hook | 5 | 6 | Linus, the HN thread, the question |
| II — Prior Art | 5 | 5 | Guzman & Azócar, Miller et al., the hypothesis |
| III — Methodology | 15 | 15 | GH Archive → LDNOOBW → tree-sitter → Mann-Whitney U |
| IV — Tech Stack | 10 | 9 | Python 3.14, Mongo, Docker, 36-way CAS |
| V — Results | 15 | 15 | 3.7 M repos, top emoji/profanity, honest limits |
| VI — AI & Future | 5 | 5 | Speculative — will Copilot kill `// this is horrible`? |
| VII — Q&A | 5 | 4 | Thanks, reading list, credits |

See IP-011 in `docs/proposals/posts/` for the proposal and its
decision trail.
