#!/usr/bin/env python3
"""Autograder helper for the dinosaur weights lab."""

from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BINARY = "student_program"
WEIGHTS_FILE = "dino_weights.txt"
EXCLUDE_FOLDERS = {".git", ".github", "tests"}


class AutograderError(RuntimeError):
    """Raised when the autograder encounters a recoverable error."""


def find_cpp_sources() -> List[Path]:
    """Locate student C++ source files while skipping infrastructure folders."""
    sources: List[Path] = []
    for path in ROOT.rglob("*.cpp"):
        if any(part in EXCLUDE_FOLDERS for part in path.parts):
            continue
        sources.append(path)
    return sources


def compile_sources(binary_name: str = DEFAULT_BINARY) -> None:
    """Compile the student's submission into an executable."""
    if shutil.which("g++") is None:
        raise AutograderError("g++ compiler is not available on the PATH.")

    sources = find_cpp_sources()
    if not sources:
        raise AutograderError("No .cpp files found to compile.")

    command = [
        "g++",
        "-std=c++17",
        "-Wall",
        "-Wextra",
        "-pedantic",
        *[str(src) for src in sources],
        "-o",
        binary_name,
    ]

    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        diagnostic = "\n".join(
            [
                "Compilation failed.",
                "Command: " + " ".join(command),
                "Standard Output:\n" + result.stdout if result.stdout else "Standard Output: (empty)",
                "Standard Error:\n" + result.stderr if result.stderr else "Standard Error: (empty)",
            ]
        )
        raise AutograderError(diagnostic)


def load_weights(weights_path: Path) -> List[float]:
    """Read the dinosaur weights from the provided file."""
    try:
        lines = weights_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AutograderError(f"Unable to read weights file: {weights_path}") from exc

    weights: List[float] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            weights.append(float(stripped))
        except ValueError as exc:
            raise AutograderError(
                f"Invalid numeric value on line {idx} of {weights_path}: '{line}'"
            ) from exc

    if not weights:
        raise AutograderError(f"Weights file {weights_path} is empty.")
    return weights


def compute_expected_stats(weights: Iterable[float]) -> Dict[str, float]:
    """Calculate the ground-truth statistics for comparison."""
    collected = list(weights)
    total = math.fsum(collected)
    count = len(collected)
    return {
        "count": count,
        "total": total,
        "min": min(collected),
        "max": max(collected),
        "average": total / count,
    }


METRIC_REGEX: Dict[str, List[str]] = {
    "total": [r"(?:total|sum)[^\-\d]*(\-?\d+(?:\.\d+)?)"],
    "average": [r"(?:average|avg|mean)[^\-\d]*(\-?\d+(?:\.\d+)?)"],
    "min": [r"(?:min(?:imum)?|smallest|lowest)[^\-\d]*(\-?\d+(?:\.\d+)?)"],
    "max": [r"(?:max(?:imum)?|largest|highest)[^\-\d]*(\-?\d+(?:\.\d+)?)"],
}

TOLERANCE = {
    "total": 0.5,
    "average": 0.05,
    "min": 0.5,
    "max": 0.5,
}


def extract_metric(output: str, metric: str) -> Optional[float]:
    """Attempt to extract a numeric value for the desired metric from the output."""
    patterns = METRIC_REGEX.get(metric, [])
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                return float(match.group(1))
            except (IndexError, ValueError):
                continue
    return None


def fallback_by_value(output: str, expected_value: float, tolerance: float) -> Optional[float]:
    """Fallback matcher that looks for a numeric literal within tolerance of the expected value."""
    numbers = [float(token) for token in re.findall(r"\-?\d+(?:\.\d+)?", output)]
    for number in numbers:
        if math.isclose(number, expected_value, abs_tol=tolerance):
            return number
    return None


def verify_statistics(output: str, expected: Dict[str, float]) -> None:
    """Ensure the student's output reports the required statistics within tolerance."""
    discovered: Dict[str, Optional[float]] = {metric: extract_metric(output, metric) for metric in TOLERANCE}

    messages: List[str] = []
    for metric, value in discovered.items():
        if value is None:
            fallback = fallback_by_value(output, expected[metric], TOLERANCE[metric])
            if fallback is not None:
                discovered[metric] = fallback
            else:
                messages.append(f"Could not find a value for '{metric}' in the program output.")

    if messages:
        raise AutograderError("\n".join(messages))

    issues: List[str] = []
    for metric, reported in discovered.items():
        expected_value = expected[metric]
        tolerance = TOLERANCE[metric]
        if not math.isclose(reported, expected_value, abs_tol=tolerance):
            issues.append(
                f"{metric.title()} mismatch: expected {expected_value:.3f} (±{tolerance}), got {reported:.3f}."
            )

    if issues:
        raise AutograderError("\n".join(issues))


def run_functional_check(binary_name: str, weights_path: Path, timeout: float, stdin_text: str) -> None:
    """Compile the submission and validate its runtime behaviour."""
    compile_sources(binary_name)

    command = [f"./{binary_name}"]
    try:
        completed = subprocess.run(
            command,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=ROOT,
        )
    except FileNotFoundError as exc:
        raise AutograderError(f"Executable '{binary_name}' not found after compilation.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AutograderError(
            f"Program execution exceeded the {timeout} second timeout."
        ) from exc

    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise AutograderError(
            f"Program exited with status {completed.returncode}. Output:\n{output.strip()}"
        )

    weights = load_weights(weights_path)
    expected = compute_expected_stats(weights)
    verify_statistics(output, expected)

    print("All required statistics detected and validated.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autograder harness for the dinosaur weights lab.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--compile-only", action="store_true", help="Only compile the submission.")
    group.add_argument("--functional", action="store_true", help="Compile and verify program output.")
    parser.add_argument("--binary-name", default=DEFAULT_BINARY, help="Name for the compiled executable.")
    parser.add_argument("--weights", default=WEIGHTS_FILE, help="Relative path to the weights data file.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Seconds to wait for program output.")
    parser.add_argument(
        "--stdin",
        default="dino_weights.txt\n",
        help="Text to feed to the program on standard input (useful if the program prompts for the filename).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    weights_path = (ROOT / args.weights).resolve()
    try:
        if args.compile_only:
            compile_sources(args.binary_name)
            print("Compilation succeeded.")
        elif args.functional:
            run_functional_check(args.binary_name, weights_path, args.timeout, args.stdin)
    except AutograderError as exc:
        print(str(exc).strip(), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
