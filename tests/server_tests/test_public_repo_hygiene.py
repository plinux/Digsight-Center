import ast
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

PUBLIC_CONTROLLER_IP_PLACEHOLDER = "0.0.0.0"


def assert_controller_config_safe_for_public_repo(testcase: unittest.TestCase, path: Path) -> None:
  data = json.loads(path.read_text(encoding="utf-8"))
  testcase.assertIsInstance(data, dict, f"controller config must be a JSON object: {path}")
  testcase.assertEqual(
    data.get("ip"),
    PUBLIC_CONTROLLER_IP_PLACEHOLDER,
    f"public controller config sample must keep placeholder IP in {path}",
  )


class PublicRepoHygieneTest(unittest.TestCase):
  def test_controller_config_hygiene_rejects_real_ip(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "Digsight_D9000.json"
      path.write_text('{"ip":"192.168.1.20"}\n', encoding="utf-8")

      with self.assertRaises(AssertionError):
        assert_controller_config_safe_for_public_repo(self, path)

  def test_controller_configs_are_runtime_generated_not_tracked(self):
    result = subprocess.run(["git", "ls-files", "config/controllers/*.json"], check=True, text=True, capture_output=True)
    config_files = [Path(file_name) for file_name in result.stdout.splitlines()]
    self.assertEqual(config_files, [])

  def test_root_protocol_package_shims_are_not_tracked(self):
    result = subprocess.run(["git", "ls-files", "train_dcc", "digsight_dxdcnet"], check=True, text=True, capture_output=True)
    self.assertEqual(result.stdout.strip(), "")

  def test_tracked_public_files_do_not_include_private_paths(self):
    blocked_tokens = [
      "/Users/" + "plx",
      "~" + "/",
      "Input" + "Temp",
    ]
    result = subprocess.run(["git", "ls-files"], check=True, text=True, capture_output=True)
    for file_name in result.stdout.splitlines():
      path = Path(file_name)
      if not path.exists():
        continue
      if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".sqlite3", ".z21"}:
        continue
      text = path.read_text(encoding="utf-8", errors="ignore")
      for token in blocked_tokens:
        self.assertNotIn(token, text, f"{token} leaked in {file_name}")

  def test_tracked_public_text_files_do_not_embed_real_fixture_controller_ip(self):
    blocked_controller_ip = ".".join(["10", "10", "200", "98"])
    result = subprocess.run(["git", "ls-files"], check=True, text=True, capture_output=True)
    for file_name in result.stdout.splitlines():
      path = Path(file_name)
      if not path.exists() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".sqlite3", ".z21"}:
        continue
      text = path.read_text(encoding="utf-8", errors="ignore")
      self.assertNotIn(blocked_controller_ip, text, f"real fixture controller IP leaked in {file_name}")

  def test_unittest_test_methods_have_unique_names_per_class(self):
    result = subprocess.run(["git", "ls-files", "tests"], check=True, text=True, capture_output=True)
    duplicates = []
    for file_name in result.stdout.splitlines():
      path = Path(file_name)
      if path.suffix != ".py":
        continue
      tree = ast.parse(path.read_text(encoding="utf-8"), filename=file_name)
      for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
          continue
        seen = {}
        for child in node.body:
          if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) or not child.name.startswith("test_"):
            continue
          previous_line = seen.get(child.name)
          if previous_line is not None:
            duplicates.append(f"{file_name}:{child.lineno}: {node.name}.{child.name} duplicates line {previous_line}")
          seen[child.name] = child.lineno
    self.assertEqual(duplicates, [])


if __name__ == "__main__":
  unittest.main()
