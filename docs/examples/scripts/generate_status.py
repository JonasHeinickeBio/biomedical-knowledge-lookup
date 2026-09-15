#!/usr/bin/env python3
"""Run every per-source example and record what happened.

Usage, from the repository root::

    python docs/examples/scripts/generate_status.py              # all sources
    python docs/examples/scripts/generate_status.py OLS HPO      # a subset
    python docs/examples/scripts/generate_status.py --timeout 180 --jobs 4

For each source this

1. runs ``docs/examples/<category>/<source>/<source>_example.py`` with a timeout,
2. writes its real output to ``<source>_example_output.txt`` (ANSI colours
   stripped, API keys and other secrets redacted),
3. classifies the run from the example's closing ``Summary:`` line.

Afterwards it rewrites ``scripts/all_adapters_test_results.json`` and
``availability-status.md`` from the results of *all* sources: a subset run
merges into the previous JSON results.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_all_examples import EXAMPLES_DIR, SOURCES, Source  # noqa: E402

REPO_ROOT = EXAMPLES_DIR.parents[1]
RESULTS_JSON = EXAMPLES_DIR / "scripts" / "all_adapters_test_results.json"
STATUS_PAGE = EXAMPLES_DIR / "availability-status.md"

ANSI = re.compile(r"\x1b\[[0-9;]*m")
SUMMARY = re.compile(r"^Summary: search=(\d+)(?: details=(found|not found))?$", re.M)
URL_SECRET = re.compile(r"((?:api_?key|token|key)=)[^&\s'\"]+", re.I)
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.I)

STATUS_LABELS = {
    "working": "Working",
    "partial": "Partial",
    "no-results": "No results",
    "skipped": "Skipped",
    "timeout": "Timeout",
    "error": "Error",
}
STATUS_MEANING = {
    "working": "search and (if the example has one) the details lookup returned data",
    "partial": "only one of search and details returned data",
    "no-results": "the adapter is available but returned nothing",
    "skipped": "the adapter is not available here (API key or optional extra missing)",
    "timeout": "the example did not finish within the timeout",
    "error": "the example exited with an error",
}


def secret_values() -> list[str]:
    """Values of secret-looking variables from the environment and any .env file."""
    values = {v for k, v in os.environ.items() if SECRET_NAME.search(k)}
    try:
        from dotenv import dotenv_values, find_dotenv

        env_file = find_dotenv(usecwd=True)  # searches the working directory and its parents
        if env_file:
            env = dotenv_values(env_file)
            values |= {value for name, value in env.items() if value and SECRET_NAME.search(name)}
    except ImportError:
        pass
    return sorted((v for v in values if v and len(v) >= 8), key=len, reverse=True)


def clean(text: str, secrets: list[str]) -> str:
    text = ANSI.sub("", text)
    for value in secrets:
        text = text.replace(value, "***")
    text = URL_SECRET.sub(r"\1***", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip() + "\n"


def classify(output: str, returncode: int | None) -> tuple[str, int | None, str | None]:
    """Return (status, number of search results, details outcome)."""
    if returncode is None:
        return "timeout", None, None
    if "Summary: skipped" in output:
        return "skipped", None, None
    match = SUMMARY.search(output)
    if returncode != 0 or match is None:
        return "error", None, None
    hits, details = int(match.group(1)), match.group(2)
    successes = [hits > 0] + ([details == "found"] if details else [])
    if all(successes):
        status = "working"
    elif any(successes):
        status = "partial"
    else:
        status = "no-results"
    return status, hits, details


def run(source: Source, timeout: float, secrets: list[str]) -> dict:
    command = [sys.executable, str(source.script.relative_to(REPO_ROOT))]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "NO_COLOR": "1"},
        )
        output, returncode = proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        partial = partial.decode(errors="replace") if isinstance(partial, bytes) else partial
        output = partial + f"\nTIMEOUT: the example did not finish within {timeout:.0f}s\n"
        returncode = None
    duration = time.monotonic() - started

    output = clean(output, secrets)
    source.output.write_text(output, encoding="utf-8")
    status, hits, details = classify(output, returncode)
    print(f"{status:<10} {duration:5.1f}s  {source.name}", flush=True)
    return {
        "source": source.name,
        "category": source.category,
        "script": str(source.script.relative_to(EXAMPLES_DIR)),
        "status": status,
        "search_results": hits,
        "details": details,
        "exit_code": returncode,
        "duration_s": round(duration, 1),
        "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def write_status_page(results: dict[str, dict]) -> None:
    counts = dict.fromkeys(STATUS_LABELS, 0)
    for result in results.values():
        counts[result["status"]] += 1
    checked = max(r["checked_at"] for r in results.values())[:10]

    lines = [
        "---",
        "description: Which per-source examples return data, as of the last recorded run.",
        "---",
        "",
        "# Availability status",
        "",
        f"Results of running every per-source example on {checked}. The public services"
        " change and go down from time to time, so treat this as a snapshot.",
        "",
        '{% hint style="info" %}',
        "This page is generated. To refresh it, run"
        " `python docs/examples/scripts/generate_status.py` from the repository root;"
        " it also rewrites every `*_example_output.txt` and"
        " [`scripts/all_adapters_test_results.json`](scripts/all_adapters_test_results.json).",
        "{% endhint %}",
        "",
        "## Summary",
        "",
        "| Status | Sources | Meaning |",
        "| --- | ---: | --- |",
    ]
    for key, label in STATUS_LABELS.items():
        lines.append(f"| {label} | {counts[key]} | {STATUS_MEANING[key]} |")
    lines += [
        "",
        "Examples that need an API key print `SKIPPED` and exit cleanly when the key is not"
        " set. See [the examples overview](README.md#api-keys-and-extras) for the keys.",
        "",
        "## By source",
        "",
        "| Category | Source | Status | Search hits | Details | Needs | Notes |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for source in SOURCES:
        result = results.get(source.name)
        if result is None:
            continue
        hits = "" if result["search_results"] is None else str(result["search_results"])
        details = result["details"] or ("n/a" if source.concept_id is None else "")
        needs = (source.requires or "").replace("the ", "").replace(" environment variable", "")
        needs = needs.replace("[", "`[").replace("]", "]`")
        needs = re.sub(r"\b([A-Z_]+_API_KEY)\b", r"`\1`", needs)
        lines.append(
            f"| {source.category.title()} | [{source.title}]({result['script']})"
            f" | {STATUS_LABELS[result['status']]} | {hits} | {details} | {needs}"
            f" | {source.issue or ''} |"
        )
    lines.append("")
    STATUS_PAGE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sources", nargs="*", help="KnowledgeSource names (default: all)")
    parser.add_argument("--timeout", type=float, default=120, help="seconds per example")
    parser.add_argument("--jobs", type=int, default=6, help="examples to run in parallel")
    args = parser.parse_args()

    wanted = {name.upper() for name in args.sources}
    unknown = wanted - {s.name for s in SOURCES}
    if unknown:
        parser.error(f"unknown sources: {', '.join(sorted(unknown))}")
    selected = [s for s in SOURCES if not wanted or s.name in wanted]

    previous: dict[str, dict] = {}
    if RESULTS_JSON.exists():
        try:
            previous = {r["source"]: r for r in json.loads(RESULTS_JSON.read_text())}
        except (ValueError, KeyError, TypeError):
            previous = {}

    secrets = secret_values()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        fresh = list(pool.map(lambda s: run(s, args.timeout, secrets), selected))

    results = {**previous, **{r["source"]: r for r in fresh}}
    results = {s.name: results[s.name] for s in SOURCES if s.name in results}
    RESULTS_JSON.write_text(json.dumps(list(results.values()), indent=2) + "\n", encoding="utf-8")
    write_status_page(results)
    written = [path.relative_to(REPO_ROOT) for path in (STATUS_PAGE, RESULTS_JSON)]
    print(f"\nWrote {written[0]} and {written[1]}")


if __name__ == "__main__":
    main()
