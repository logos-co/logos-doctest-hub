#!/usr/bin/env python3
"""Refresh tutorial lists in repos.json from workspace CI workflows and specs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "ERROR: PyYAML is required. Install with: pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(2)


def default_workspace(hub_dir: Path) -> Path:
    # logos-doctest-hub lives at <workspace>/repos/logos-doctest-hub
    return hub_dir.parent.parent


def find_publish_workflow(repo_dir: Path) -> Path | None:
    workflows = repo_dir / ".github" / "workflows"
    if not workflows.is_dir():
        return None
    for path in sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        if "peaceiris/actions-gh-pages" not in text:
            continue
        if "--report" not in text and "-- report" not in text:
            continue
        if not re.search(r"--\s+run\s+", text):
            continue
        return path
    return None


def _parse_run_args(args_block: str, repo_dir: Path) -> list[Path]:
    args_block = re.sub(r"\\\s*\n", " ", args_block)
    args_block = re.sub(r"\$\{\{[^}]+\}\}", "", args_block)

    specs: list[Path] = []
    for token in args_block.split():
        token = token.strip().strip('"').strip("'")
        if not token or token.startswith("-"):
            continue
        if ".test.yaml" not in token:
            continue
        if "*" in token:
            if "/" in token:
                rel_dir, pattern = token.rsplit("/", 1)
                base = repo_dir / rel_dir
            else:
                base = repo_dir
                pattern = token
            for path in sorted(base.glob(pattern)):
                if path.is_file():
                    specs.append(path.resolve())
        else:
            path = (repo_dir / token).resolve()
            if path.is_file():
                specs.append(path)
    return specs


def _score_specs(specs: list[Path]) -> int:
    score = len(specs)
    paths = [str(p) for p in specs]
    if any("/doctests/" in p or "/tests/" in p for p in paths):
        score += 100
    if len(specs) == 1 and any("/examples/" in p for p in paths):
        score -= 50
    return score


def extract_report_specs(workflow_text: str, repo_dir: Path) -> list[Path]:
    matches = list(re.finditer(r"--\s+run\s+(.*?)\s+--report", workflow_text, re.DOTALL))
    if not matches:
        return []

    candidates: list[list[Path]] = []
    for match in matches:
        specs = _parse_run_args(match.group(1), repo_dir)
        if specs:
            candidates.append(specs)

    if not candidates:
        return []

    return max(candidates, key=_score_specs)


def load_spec(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"spec is not a mapping: {path}")
    return data


def requires_order(spec_path: Path) -> list[Path]:
    spec_path = spec_path.resolve()
    spec = load_spec(spec_path)
    spec_dir = spec_path.parent
    ordered: list[Path] = []
    ran: set[Path] = set()

    def resolve(req_path: Path) -> None:
        req_path = req_path.resolve()
        if req_path in ran:
            return
        if not req_path.is_file():
            raise FileNotFoundError(f"required spec not found: {req_path}")
        req_spec = load_spec(req_path)
        req_dir = req_path.parent
        for nested_rel in req_spec.get("requires", []):
            resolve((req_dir / nested_rel).resolve())
        ran.add(req_path)
        ordered.append(req_path)

    for req_rel in spec.get("requires", []):
        resolve((spec_dir / req_rel).resolve())

    if spec_path not in ran:
        ordered.append(spec_path)
    return ordered


def tutorial_names(top_level_specs: list[Path]) -> list[str]:
    seen_paths: set[Path] = set()
    names: list[str] = []
    for spec_path in top_level_specs:
        for path in requires_order(spec_path):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            spec = load_spec(path)
            name = spec.get("name")
            if not name:
                raise ValueError(f"spec missing top-level name: {path}")
            names.append(str(name))
    return names


def diff_tutorials(old: list[str], new: list[str]) -> list[str]:
    lines: list[str] = []
    old_set, new_set = set(old), set(new)
    if old == new:
        return lines
    for name in new:
        if name not in old_set:
            lines.append(f'+ tutorial "{name}"')
    for name in old:
        if name not in new_set:
            lines.append(f'- tutorial "{name}"')
    if old != new and not lines:
        lines.append("order changed")
    return lines


def refresh(
    manifest: dict,
    workspace: Path,
    *,
    verbose: bool = False,
) -> tuple[dict, list[str], bool]:
    """Return updated manifest, log lines, and whether any errors occurred."""
    workspace = workspace.resolve()
    repos_dir = workspace / "repos"
    updated = json.loads(json.dumps(manifest))
    log: list[str] = []
    had_errors = False

    for entry in updated.get("repos", []):
        repo_name = entry.get("name", "")
        repo_dir = repos_dir / repo_name
        old_tutorials = list(entry.get("tutorials") or [])

        if not repo_dir.is_dir():
            log.append(f"{repo_name}: ERROR repo not found at {repo_dir}")
            had_errors = True
            continue

        workflow = find_publish_workflow(repo_dir)
        if workflow is None:
            log.append(f"{repo_name}: ERROR no publish workflow with doctest --report")
            had_errors = True
            continue

        if verbose:
            log.append(f"{repo_name}: using workflow {workflow.relative_to(repo_dir)}")

        specs = extract_report_specs(workflow.read_text(encoding="utf-8"), repo_dir)
        if not specs:
            log.append(f"{repo_name}: ERROR could not parse specs from workflow")
            had_errors = True
            continue

        if verbose:
            for spec in specs:
                log.append(f"  spec: {spec.relative_to(repo_dir)}")

        try:
            new_tutorials = tutorial_names(specs)
        except (FileNotFoundError, ValueError) as exc:
            log.append(f"{repo_name}: ERROR {exc}")
            had_errors = True
            continue

        entry["tutorials"] = new_tutorials
        changes = diff_tutorials(old_tutorials, new_tutorials)
        if changes:
            log.append(f"{repo_name}:")
            log.extend(f"  {line}" for line in changes)
        else:
            log.append(f"{repo_name}: unchanged")

    return updated, log, had_errors


def main() -> int:
    hub_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Refresh repos.json tutorial lists from workspace CI and specs.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=default_workspace(hub_dir),
        help="logos-workspace root (default: parent of repos/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=hub_dir / "repos.json",
        help="manifest to read and write (default: repos.json next to this script)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print changes without writing repos.json",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="show workflow and spec paths per repo",
    )
    args = parser.parse_args()

    output_path = args.output.resolve()
    if not output_path.is_file():
        print(f"ERROR: manifest not found: {output_path}", file=sys.stderr)
        return 1

    with open(output_path, encoding="utf-8") as f:
        manifest = json.load(f)

    updated, log, had_errors = refresh(manifest, args.workspace, verbose=args.verbose)

    for line in log:
        print(line)

    if updated != manifest:
        if args.dry_run:
            print("\n(dry-run: repos.json not written)")
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(updated, f, indent=2, ensure_ascii=False)
                f.write("\n")
            print(f"\nWrote {output_path}")
    elif not args.dry_run:
        print(f"\nNo changes; {output_path} is up to date")

    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
