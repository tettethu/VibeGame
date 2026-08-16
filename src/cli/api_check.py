"""Paid API smoke checks for `vibegame check --api`."""

from __future__ import annotations

import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApiSmokeResult:
    name: str
    command: str
    ok: bool
    detail: str


def _run_cli(args: list[str], project_dir: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("vibegame")
    if executable is None:
        raise FileNotFoundError("vibegame executable not found on PATH")
    print(f"  Running: {_command_text(args)} (cwd: {project_dir})", flush=True)
    return subprocess.run(
        [executable, *args],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _command_text(args: list[str]) -> str:
    import shlex

    return shlex.join(["vibegame", *args])


def _result_detail(result: subprocess.CompletedProcess[str]) -> str:
    parts = []
    if result.stdout.strip():
        parts.append(f"stdout: {result.stdout.strip()}")
    if result.stderr.strip():
        parts.append(f"stderr: {result.stderr.strip()}")
    return "\n".join(parts) or f"exit code {result.returncode} with no output"


def _run_vlm_check(project_dir: Path) -> ApiSmokeResult:
    args = ["vlm", "-t", "hi"]
    command = _command_text(args)
    try:
        result = _run_cli(args, project_dir, timeout=180)
    except subprocess.TimeoutExpired as exc:
        return ApiSmokeResult("VLM", command, False, f"timed out after {exc.timeout}s")
    if result.returncode != 0:
        return ApiSmokeResult("VLM", command, False, _result_detail(result))
    response = result.stdout.strip()
    if not response or response.lower() in {"none", "null"}:
        return ApiSmokeResult("VLM", command, False, "API returned an empty response")
    return ApiSmokeResult("VLM", command, True, response)


def _run_image_check(project_dir: Path) -> ApiSmokeResult:
    output = project_dir / "logs" / "smoke.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = output.stat().st_mtime_ns if output.is_file() else None
    args = [
        "art", "gen", "image",
        "-t", "A simple white background, nothing there",
        "--quality", "low",
        "--size", "512x512",
        "-o", "logs/smoke.png",
    ]
    command = _command_text(args)
    try:
        result = _run_cli(args, project_dir, timeout=300)
    except subprocess.TimeoutExpired as exc:
        return ApiSmokeResult("Image", command, False, f"timed out after {exc.timeout}s")
    if result.returncode != 0:
        return ApiSmokeResult("Image", command, False, _result_detail(result))
    if not output.is_file() or output.stat().st_size == 0:
        return ApiSmokeResult("Image", command, False, "command succeeded but logs/smoke.png is missing or empty")
    if previous is not None and output.stat().st_mtime_ns == previous:
        return ApiSmokeResult("Image", command, False, "command succeeded but logs/smoke.png was not updated")
    return ApiSmokeResult("Image", command, True, f"saved logs/smoke.png ({output.stat().st_size} bytes)")


def run_api_smoke_checks(project_dir: Path) -> list[ApiSmokeResult]:
    """Run paid API checks in deterministic order without retries."""
    return [_run_vlm_check(project_dir), _run_image_check(project_dir)]


def print_api_smoke_report(results: list[ApiSmokeResult]) -> int:
    print("\nAPI smoke checks:")
    for result in results:
        print(f"  Running: {result.command}")
        status = "PASS" if result.ok else "FAIL"
        print(f"  [{status}] {result.name}: {result.detail}")
    failures = sum(not result.ok for result in results)
    if failures:
        print(f"API FAILED: {failures} check(s)")
        return 1
    print(f"API PASSED: {len(results)} check(s)")
    return 0
