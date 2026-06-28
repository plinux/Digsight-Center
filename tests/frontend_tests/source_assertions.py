"""Shared source-code assertions for frontend contract tests."""

import re
from pathlib import Path


class SourceAssertionsMixin:
  _source_cache = {}

  def read_text(self, path: str) -> str:
    if path not in self._source_cache:
      self._source_cache[path] = Path(path).read_text(encoding="utf-8")
    return self._source_cache[path]

  def source_slice(self, source: str, start_token: str, end_token: str) -> str:
    start = source.index(start_token)
    end = source.index(end_token, start)
    return source[start:end]

  def source_function(self, source: str, function_name: str) -> str:
    pattern = re.compile(rf"(?:async\s+)?function\s+{re.escape(function_name)}\s*\(")
    match = pattern.search(source)
    self.assertIsNotNone(match, f"function not found: {function_name}")
    start = match.start()
    open_paren = source.index("(", match.start())
    paren_depth = 0
    close_paren = None
    for index in range(open_paren, len(source)):
      char = source[index]
      if char == "(":
        paren_depth += 1
      elif char == ")":
        paren_depth -= 1
        if paren_depth == 0:
          close_paren = index
          break
    self.assertIsNotNone(close_paren, f"function parameters not closed: {function_name}")
    brace = source.index("{", close_paren)
    depth = 0
    for index in range(brace, len(source)):
      char = source[index]
      if char == "{":
        depth += 1
      elif char == "}":
        depth -= 1
        if depth == 0:
          return source[start:index + 1]
    self.fail(f"function not closed: {function_name}")

  def assert_source_contains_all(self, source: str, tokens: list[str]) -> None:
    missing = [token for token in tokens if token not in source]
    self.assertEqual(missing, [], f"missing source tokens: {missing}")

  def assert_source_not_contains_any(self, source: str, tokens: list[str]) -> None:
    present = [token for token in tokens if token in source]
    self.assertEqual(present, [], f"unexpected source tokens: {present}")

  def assert_source_order(self, source: str, before: str, after: str) -> None:
    self.assert_source_contains_all(source, [before, after])
    self.assertLess(source.index(before), source.index(after), f"{before!r} should appear before {after!r}")
