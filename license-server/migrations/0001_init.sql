-- Máy chủ bản quyền skill C-Cut (Cloudflare D1 / SQLite)
CREATE TABLE products (           -- skill bán lẻ (id = slug skill) + combo "all"
  id TEXT PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL DEFAULT 0,   -- VND; 0 = chưa mở bán
  active INTEGER NOT NULL DEFAULT 1, sort INTEGER NOT NULL DEFAULT 0
);
INSERT INTO products (id, name, price, sort) VALUES
  ('review-editor', 'Skill Review', 0, 1),
  ('voice-to-motion', 'Skill Voice to Motion', 0, 2),
  ('all', 'Combo toàn bộ skill', 0, 9);

CREATE TABLE devices (
  id TEXT PRIMARY KEY, os TEXT, app TEXT, first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
  blocked INTEGER NOT NULL DEFAULT 0, note TEXT
);

CREATE TABLE trial_uses (         -- 1 dòng = 1 dự án đã dùng lượt thử của skill trên máy (gọi lại cùng dự án không trừ thêm)
  device TEXT NOT NULL, skill TEXT NOT NULL, project TEXT NOT NULL, at INTEGER NOT NULL,
  PRIMARY KEY (device, skill, project)
);

CREATE TABLE licenses (
  key TEXT PRIMARY KEY, product TEXT NOT NULL, device TEXT,          -- device NULL = chưa kích hoạt
  created INTEGER NOT NULL, activated INTEGER, order_id TEXT, note TEXT, revoked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX licenses_device ON licenses (device);

CREATE TABLE orders (
  id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, product TEXT NOT NULL, amount INTEGER NOT NULL,
  contact TEXT, device TEXT, status TEXT NOT NULL DEFAULT 'pending',  -- pending | paid
  created INTEGER NOT NULL, paid INTEGER, license TEXT, payment TEXT
);

CREATE TABLE payments (           -- giao dịch ngân hàng nhận qua webhook (chống ghi trùng)
  id TEXT PRIMARY KEY, amount INTEGER, content TEXT, at INTEGER NOT NULL, order_id TEXT, raw TEXT
);

CREATE TABLE settings (k TEXT PRIMARY KEY, v TEXT);   -- bank, account, account_name, trial_limit
INSERT INTO settings (k, v) VALUES ('trial_limit', '2');
