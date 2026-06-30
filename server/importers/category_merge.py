"""Category merge strategies for normalized configuration imports."""

import hashlib

from server.importers.base import CATEGORY_MERGE_SHARED_BY_NORMALIZED_NAME


def normalize_category_name(name: str) -> str:
  return " ".join(str(name or "").strip().split()).casefold()


def shared_category_id(source_key: str, name: str) -> str:
  normalized = normalize_category_name(name)
  digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
  return f"{source_key}-category-shared-{digest}"


def should_share_by_name(import_source) -> bool:
  return import_source.category_merge_strategy == CATEGORY_MERGE_SHARED_BY_NORMALIZED_NAME
