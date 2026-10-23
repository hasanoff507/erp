-- 0008 catalog_pricing — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.product_categories (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  parent_id   UUID NULL REFERENCES app.product_categories(id),
  name        TEXT NOT NULL,
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  version     INT NOT NULL DEFAULT 1
);

CREATE TABLE app.products (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  name             TEXT NOT NULL,
  name_ru          TEXT NULL, -- (qaror #29) ixtiyoriy, chek/UI ikkinchi til qatori ("name / name_ru")
  category_id      UUID NULL REFERENCES app.product_categories(id),
  unit_code        TEXT NOT NULL REFERENCES platform.units(code),
  mxik_code        TEXT NULL CHECK (mxik_code IS NULL OR mxik_code ~ '^[0-9]{17}$'), -- yaratishda bloklamaydi, sotuvdan oldin shart
  package_code     TEXT NULL CHECK (package_code IS NULL OR length(package_code) <= 20),
                   -- tasnif.soliq.uz qadoq kodi; mxik_code kabi yaratishda bloklamaydi, fiskal chekdan oldin shart (OFD PackageCode)
  vat_rate         NUMERIC(5,2) NULL, -- 12.00 / 0.00 (aniqlashtirish #8: vat_exemption_code bilan birga)
  vat_exemption_code TEXT NULL, -- imtiyoz kodi, vat_rate o'rniga/bilan
  is_marked        BOOLEAN NOT NULL DEFAULT false,
  marking_group_code TEXT NULL REFERENCES platform.marking_product_groups(code), -- is_marked=true bo'lsa majburiy (qabul muddati, qaror #63)
  is_weighed       BOOLEAN NOT NULL DEFAULT false,
  turnover_tax_group TEXT NOT NULL DEFAULT 'general' CHECK (turnover_tax_group IN ('general','tobacco')),
                   -- aylanma solig'i stavka guruhi (13 §4.3, platform.turnover_tax_rates); tamaki — alohida stavka
  min_stock        NUMERIC(18,3) NULL,
  archived_at      TIMESTAMPTZ NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  version          INT NOT NULL DEFAULT 1,
  CHECK (vat_rate IS NOT NULL OR vat_exemption_code IS NOT NULL),
  CHECK (NOT is_marked OR marking_group_code IS NOT NULL)
);

CREATE INDEX idx_products_name_trgm ON app.products USING gin (name gin_trgm_ops);

CREATE INDEX idx_products_tenant_archived ON app.products (tenant_id) WHERE archived_at IS NULL;

CREATE TABLE app.product_barcodes (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  product_id        UUID NOT NULL REFERENCES app.products(id),
  barcode           TEXT NOT NULL,
  kind              TEXT NOT NULL CHECK (kind IN ('ean','internal','weighed_prefix')),
  units_per_barcode NUMERIC(18,3) NOT NULL DEFAULT 1 CHECK (units_per_barcode > 0),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, barcode),
  CHECK (kind <> 'internal' OR barcode ~ '^04[0-9]{11}$') -- internal_barcode_seq diapazoni (GS1 RCN 040–049)
);

CREATE TABLE app.product_prices (
  id                  UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id           UUID NOT NULL REFERENCES app.tenants(id),
  product_id          UUID NOT NULL REFERENCES app.products(id),
  branch_id           UUID NULL REFERENCES app.branches(id), -- null = hamma filial
  price               NUMERIC(18,4) NOT NULL CHECK (price >= 0),
  valid_from          TIMESTAMPTZ NOT NULL DEFAULT now(),
  set_by              UUID NULL REFERENCES app.users(id),
  price_change_doc_id UUID NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_product_prices_current ON app.product_prices (tenant_id, product_id, branch_id, valid_from DESC);

CREATE TABLE app.label_print_queue (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  product_id UUID NOT NULL REFERENCES app.products(id),
  reason     TEXT NOT NULL CHECK (reason IN ('price_changed','new')),
  printed_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_label_queue_pending ON app.label_print_queue (tenant_id) WHERE printed_at IS NULL;

-- Ichki shtrix-kod (US-M09-05): EAN-13 = lpad(next_value, 12, '0') || nazorat raqami → '04' + 10 raqam + K.
-- GS1 RCN-13 diapazoni 040–049 (kompaniya ichida ishlatish) — real GTIN'lar bilan ham, tarozi prefikslari
-- (weight_barcode_templates, 20–29) bilan ham kesishmaydi.
CREATE TABLE app.internal_barcode_seq (
  tenant_id  UUID PRIMARY KEY REFERENCES app.tenants(id),
  next_value BIGINT NOT NULL DEFAULT 40000000000
             CHECK (next_value BETWEEN 40000000000 AND 49999999999) -- 040000000000…049999999999
);

CREATE TABLE app.discount_rules (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  name        TEXT NOT NULL,
  scope       TEXT NOT NULL CHECK (scope IN ('product','category','all')),
  target_ids  UUID[] NOT NULL DEFAULT '{}',
  kind        TEXT NOT NULL CHECK (kind IN ('percent','amount','n_plus_m')),
  value       NUMERIC(18,4) NOT NULL, -- kind='percent' bo'lsa foiz, aks holda summa (aniqlashtirish #7)
  branch_ids  UUID[] NOT NULL DEFAULT '{}', -- bo'sh = hammasi
  valid_from  DATE NOT NULL,
  valid_to    DATE NULL,
  priority    INT NOT NULL DEFAULT 0,
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  version     INT NOT NULL DEFAULT 1
);

CREATE INDEX idx_discount_rules_active ON app.discount_rules (tenant_id, priority DESC) WHERE archived_at IS NULL;
