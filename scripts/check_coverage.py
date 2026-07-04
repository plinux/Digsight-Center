#!/usr/bin/env python3
"""Run the Digsight-Center test suite and enforce coverage gates."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


FUNCTION_COVERAGE_MINIMUM = 100.0
LINE_COVERAGE_MINIMUM = 90.0
BRANCH_COVERAGE_MINIMUM = 80.0
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON_VERSION = (3, 10)


@dataclass(frozen=True)
class FunctionCoverage:
  covered: int
  total: int
  missing: list[str]

  @property
  def percent(self) -> float:
    if self.total == 0:
      return 100.0
    return self.covered * 100.0 / self.total


def main() -> int:
  if not python_version_supported():
    print(python_version_error(sys.version.split()[0]), file=sys.stderr)
    return 2
  if not _coverage_module_available():
    print("缺少 coverage.py，请先执行：python3 -m pip install -r requirements-dev.txt", file=sys.stderr)
    return 2

  env = coverage_environment()
  _run([sys.executable, "-m", "coverage", "erase"], env)
  _run([sys.executable, "-m", "coverage", "run", "-m", "unittest", "discover", "-s", "tests"], env)

  with tempfile.TemporaryDirectory() as temp_dir:
    json_path = Path(temp_dir) / "coverage.json"
    _run([sys.executable, "-m", "coverage", "json", "-o", str(json_path)], env)
    coverage_data = json.loads(json_path.read_text(encoding="utf-8"))

  _run([sys.executable, "-m", "coverage", "report", "-m"], env)
  return _enforce_thresholds(coverage_data)


def python_version_supported(version_info=sys.version_info) -> bool:
  return tuple(version_info[:2]) >= MIN_PYTHON_VERSION


def python_version_error(version_text: str) -> str:
  return (
    "Digsight-Center coverage checks require Python 3.10 or newer; "
    f"current Python is {version_text}. Use a Python 3.10+ interpreter."
  )


def local_package_pythonpath_entries() -> list[str]:
  return [
    str(PROJECT_ROOT),
    str(PROJECT_ROOT / "packages" / "train-dcc" / "src"),
    str(PROJECT_ROOT / "packages" / "digsight-dxdcnet" / "src"),
    str(PROJECT_ROOT / "packages" / "esu-ecos" / "src"),
    str(PROJECT_ROOT / "packages" / "z21-lan" / "src"),
  ]


def coverage_environment(base_env: dict | None = None) -> dict:
  env = dict(base_env or os.environ)
  existing_pythonpath = env.get("PYTHONPATH", "")
  env["PYTHONPATH"] = os.pathsep.join([
    *local_package_pythonpath_entries(),
    *([existing_pythonpath] if existing_pythonpath else []),
  ])
  return env


def _coverage_module_available() -> bool:
  try:
    import coverage  # noqa: F401
  except ImportError:
    return False
  return True


def _run(command: list[str], env: dict[str, str]) -> None:
  subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=True)


def _enforce_thresholds(coverage_data: dict) -> int:
  totals = coverage_data["totals"]
  function_coverage = _measure_function_coverage(coverage_data)
  line_percent = totals["covered_lines"] * 100.0 / totals["num_statements"]
  branch_percent = totals["covered_branches"] * 100.0 / totals["num_branches"]
  print(
    "覆盖率门禁："
    f"函数 {function_coverage.percent:.2f}% ({function_coverage.covered}/{function_coverage.total})，"
    f"行 {line_percent:.2f}% ({totals['covered_lines']}/{totals['num_statements']})，"
    f"分支 {branch_percent:.2f}% ({totals['covered_branches']}/{totals['num_branches']})"
  )

  failures = []
  if function_coverage.percent < FUNCTION_COVERAGE_MINIMUM:
    failures.append(f"函数覆盖率低于 {FUNCTION_COVERAGE_MINIMUM:.0f}%")
  if line_percent < LINE_COVERAGE_MINIMUM:
    failures.append(f"行覆盖率低于 {LINE_COVERAGE_MINIMUM:.0f}%")
  if branch_percent < BRANCH_COVERAGE_MINIMUM:
    failures.append(f"分支覆盖率低于 {BRANCH_COVERAGE_MINIMUM:.0f}%")

  if not failures:
    return 0
  for failure in failures:
    print(f"覆盖率门禁失败：{failure}", file=sys.stderr)
  for item in function_coverage.missing[:40]:
    print(f"未覆盖函数：{item}", file=sys.stderr)
  return 1


def _measure_function_coverage(coverage_data: dict) -> FunctionCoverage:
  covered = 0
  total = 0
  missing = []
  for relative_file, file_data in sorted(coverage_data["files"].items()):
    path = PROJECT_ROOT / relative_file
    if path.suffix != ".py" or not path.exists():
      continue
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    executed_lines = set(file_data.get("executed_lines", []))
    excluded_lines = set(file_data.get("excluded_lines", []))
    for node in ast.walk(tree):
      if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
      first_line = _first_executable_line(node)
      if first_line is None or first_line in excluded_lines:
        continue
      total += 1
      if first_line in executed_lines:
        covered += 1
      else:
        missing.append(f"{relative_file}:{node.lineno}:{node.name}")
  return FunctionCoverage(covered=covered, total=total, missing=missing)


def _first_executable_line(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
  body = []
  for statement in node.body:
    if (
      isinstance(statement, ast.Expr)
      and isinstance(statement.value, ast.Constant)
      and isinstance(statement.value.value, str)
    ):
      continue
    if isinstance(statement, (ast.Global, ast.Nonlocal, ast.Pass)):
      continue
    body.append(statement)
  if not body:
    return None
  return min(getattr(statement, "lineno", node.lineno) for statement in body)


if __name__ == "__main__":
  raise SystemExit(main())
