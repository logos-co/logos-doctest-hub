# logos-doctest-hub

Central index for Logos executable documentation (doc-test) reports published by
each repo's CI to GitHub Pages.

**Live site:** https://logos-co.github.io/logos-doctest-hub/

## What it does

Each repo that runs `doctest run … --report` in CI publishes a two-column HTML
report to its own `gh-pages` branch:

```
https://logos-co.github.io/<repo>/main/<platform>/
```

This hub provides a sidebar listing all registered repos and their tutorials.
Selecting a tutorial loads that repo's **live** `main/` report in an iframe, deep-linked
to the specific tutorial via `#<tutorial-slug>`. Because reports are embedded rather
than copied, the hub always reflects the latest `main/` CI publish with no rebuild.

## One-time setup

1. Repo **Settings → Pages → Build and deployment**: Source = **Deploy from a branch**,
   Branch = `gh-pages` / `(root)`.
2. Push to `main` — the `publish.yml` workflow creates and updates `gh-pages`.

## Adding a repo or tutorial

Edit [`repos.json`](repos.json):

- Add a repo entry with `name` (GitHub repo name), `label` (sidebar heading), and
  `tutorials` (exact `name:` values from each `*.test.yaml` spec).
- Tutorial slugs are derived automatically (lowercase, non-alphanumerics → hyphens)
  and must match the deep-link format in `logos-doctest` reports.

After merging, the hub site updates on the next push to `main`.

## Related

- [`logos-doctest`](../logos-doctest/) — the doc-test runner and HTML report generator
- Individual repo workflows (e.g. `logos-tutorial/.github/workflows/ci.yml`) publish
  per-repo reports that this hub aggregates
