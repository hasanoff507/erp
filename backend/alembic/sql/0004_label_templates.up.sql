-- 0004 label_templates — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- standart yorliq shablonlari (US-M09-04), tenant o'zgartirmaydi, RLS istisnosi
CREATE TABLE platform.label_templates (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  code       TEXT NOT NULL UNIQUE, -- '58x40_price', '40x30_barcode'
  name       TEXT NOT NULL,
  width_mm   NUMERIC(6,2) NOT NULL CHECK (width_mm > 0),
  height_mm  NUMERIC(6,2) NOT NULL CHECK (height_mm > 0),
  fields     JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- (qaror #63) Markirovkalangan tovar guruhlari — egalik o'tishi xabarnomasi (kirimda qabul) muddati guruhga bog'liq:
-- umumiy — 3 ish kuni (VM 833 66–67-band), suv/ichimlik (VM 631), dori (VM 149), o'simlik yog'i (VM 23) — 72 soat.
-- Global ma'lumotnoma (RLS istisnosi), seed 5.1; products.marking_group_code shu yerga ishora qiladi.
CREATE TABLE platform.marking_product_groups (
  code                TEXT PRIMARY KEY, -- 'general','water_beverages','medicines','vegetable_oil'
  name                TEXT NOT NULL,
  acceptance_deadline TEXT NOT NULL CHECK (acceptance_deadline IN ('3_business_days','72_hours')),
  legal_ref           TEXT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
