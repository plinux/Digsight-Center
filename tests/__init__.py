from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for package_src in (
  PROJECT_ROOT / "packages" / "train-dcc" / "src",
  PROJECT_ROOT / "packages" / "digsight-dxdcnet" / "src",
):
  package_src_text = str(package_src)
  if package_src_text not in sys.path:
    sys.path.insert(0, package_src_text)
