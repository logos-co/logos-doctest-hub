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

## Versions

The header has a **version dropdown** that selects which published report directory
the hub embeds. A version maps to the path segment in the Pages URL
(`<repo>/<dir>/<os>/`) and may restrict which repos are listed.

Edit the `versions` array in [`repos.json`](repos.json):

```json
"defaultVersion": "main",
"versions": [
  { "id": "main", "label": "main", "dir": "main" },
  { "id": "v3", "label": "releases/v3", "dir": "releases/v3", "repos": ["logos-tutorial"] }
]
```

- `id` — stable key used in deep-link hashes.
- `label` — text shown in the dropdown.
- `dir` — Pages directory segment for this version's reports.
- `repos` *(optional)* — repo `name`s to show for this version. Omit to show all repos.

`defaultVersion` selects the version shown on load (and its hashes omit the version
prefix, so existing `#<repo>/<os>/<tutorial>` links keep working). Versions reuse each
repo's existing `tutorials` array — there's no per-version tutorial list. The dropdown
is hidden when only one version is configured.

## Refreshing the manifest

When you add, rename, or remove `*.test.yaml` specs — or change which specs CI passes to
`doctest run --report` — refresh the tutorial list instead of editing it by hand:

```bash
# From logos-doctest-hub/
python3 refresh-repos.py              # update repos.json
./bin/refresh-repos --dry-run         # preview changes only
python3 refresh-repos.py -v           # verbose (workflow + spec paths)
python3 refresh-repos.py --workspace /path/to/logos-workspace
```

The script reads each repo already listed in `repos.json`, finds its GitHub Actions
workflow that publishes doctest reports, resolves the specs passed to `--report`
(including `requires:` chains), and updates each repo's `tutorials` array with the
exact `name:` values from those specs.

**Requires:** Python 3 and PyYAML (`pip install pyyaml`).

New repos are **not** auto-discovered — add `name` and `label` to `repos.json` manually,
then run the refresh tool to populate `tutorials`.

## Related

- [`logos-doctest`](../logos-doctest/) — the doc-test runner and HTML report generator
- Individual repo workflows (e.g. `logos-tutorial/.github/workflows/ci.yml`) publish
  per-repo reports that this hub aggregates
