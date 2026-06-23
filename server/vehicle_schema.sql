PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vehicles (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'manual',
  source_vehicle_id TEXT,
  track_mode TEXT DEFAULT '',
  z21_position INTEGER,
  custom_sort_order INTEGER DEFAULT 0,
  name TEXT NOT NULL,
  address INTEGER NOT NULL,
  image_name TEXT,
  image_path TEXT,
  type INTEGER DEFAULT 0,
  sync_function_control INTEGER DEFAULT 0,
  energy_type TEXT DEFAULT '',
  car_subtype TEXT DEFAULT '',
  consist_kind TEXT DEFAULT '',
  max_speed INTEGER,
  brand TEXT,
  full_name TEXT,
  railway TEXT,
  article_number TEXT,
  decoder_type TEXT,
  buffer_length TEXT,
  model_buffer_length TEXT,
  service_weight TEXT,
  model_weight TEXT,
  rmin TEXT,
  description TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicle_functions (
  id TEXT PRIMARY KEY,
  vehicle_id TEXT NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  source_function_id TEXT,
  function_number INTEGER NOT NULL,
  label TEXT NOT NULL,
  icon_name TEXT,
  button_type INTEGER DEFAULT 0,
  time TEXT,
  trigger_mode TEXT DEFAULT 'toggle',
  duration_ms INTEGER DEFAULT 0,
  position INTEGER DEFAULT 0,
  show_function_number INTEGER DEFAULT 1,
  is_configured INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS categories (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'manual',
  source_category_id TEXT,
  track_mode TEXT DEFAULT '',
  name TEXT NOT NULL,
  description TEXT,
  sort_order INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicle_categories (
  vehicle_id TEXT NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  category_id TEXT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  PRIMARY KEY (vehicle_id, category_id)
);

CREATE TABLE IF NOT EXISTS consists (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'manual',
  source_train_id TEXT,
  control_vehicle_id TEXT REFERENCES vehicles(id) ON DELETE SET NULL,
  track_mode TEXT DEFAULT '',
  consist_kind TEXT DEFAULT '',
  name TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consist_members (
  consist_id TEXT NOT NULL REFERENCES consists(id) ON DELETE CASCADE,
  vehicle_id TEXT NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  address INTEGER NOT NULL,
  direction TEXT NOT NULL DEFAULT 'forward',
  member_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (consist_id, vehicle_id, member_order)
);

CREATE TABLE IF NOT EXISTS vehicle_imports (
  id TEXT PRIMARY KEY,
  file_name TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  imported_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vehicle_functions_vehicle_id ON vehicle_functions(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_vehicle_categories_category_id ON vehicle_categories(category_id);
