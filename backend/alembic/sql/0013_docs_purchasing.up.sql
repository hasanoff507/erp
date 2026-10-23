-- 0013 docs_purchasing — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.purchase_orders (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','sent','partially_received','closed','cancelled')) DEFAULT 'draft',
  supplier_id     UUID NOT NULL REFERENCES app.counterparties(id),
  warehouse_id    UUID NOT NULL, -- FK app.warehouses(id), ALTER bilan pastda
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);

ALTER TABLE app.purchase_orders ADD CONSTRAINT fk_po_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);

CREATE TABLE app.po_lines (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  po_id      UUID NOT NULL REFERENCES app.purchase_orders(id),
  line_no    INT NOT NULL,
  product_id UUID NOT NULL REFERENCES app.products(id),
  qty        NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  price      NUMERIC(18,4) NULL CHECK (price IS NULL OR price >= 0), -- ixtiyoriy
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (po_id, line_no)
);

CREATE TABLE app.goods_receipts (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  number           TEXT NULL,
  temp_number      TEXT NULL,
  doc_date         DATE NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  supplier_id      UUID NOT NULL REFERENCES app.counterparties(id),
  po_id            UUID NULL REFERENCES app.purchase_orders(id),
  warehouse_id     UUID NOT NULL, -- FK app.warehouses(id)
  paid_immediately BOOLEAN NOT NULL DEFAULT false, -- aniqlashtirish #9: 2.6/2.8-provodka yo'lini tanlaydi
  kind             TEXT NOT NULL DEFAULT 'purchase' CHECK (kind IN ('purchase','gratuitous')),
                   -- gratuitous — tekin olingan tovar: Dt inv_acct / Kt 8530 bozor qiymatida, QQS va kreditorlik yo'q (13 §2.6a)
  source           TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','purchase_order','einvoice','ocr')),
  einvoice_id      UUID NULL, -- FK pastda; "qizil" faktura QQS kechiktirish shu orqali aniqlanadi
  ai_ocr_job_id    UUID NULL, -- FK pastda → app.ai_ocr_jobs(id)
  ettn_ref         TEXT NULL, -- qo'lda e-TTN belgisi
  poa_id           UUID NULL, -- FK pastda (powers_of_attorney yaratilgach, 0020) → app.powers_of_attorney(id)
  poa_number       TEXT NULL, -- e-ishonchnoma raqami (powers_of_attorney.number dan yoki qo'lda)
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at        TIMESTAMPTZ NULL,
  cancelled_at     TIMESTAMPTZ NULL,
  cancelled_by     UUID NULL REFERENCES app.users(id),
  cancel_reason    TEXT NULL,
  client_event_id  UUID NULL,
  device_id        UUID NULL REFERENCES app.devices(id),
  comment          TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id),
  CHECK (source <> 'einvoice' OR einvoice_id IS NOT NULL),
  CHECK (kind <> 'gratuitous' OR NOT paid_immediately)
);

ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);

-- fk_gr_einvoice / uq_gr_einvoice_active — einvoices yaratilgandan keyin, 2.8-bo'limda (0020-revizion)

CREATE TABLE app.receipt_lines (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  receipt_id         UUID NOT NULL REFERENCES app.goods_receipts(id),
  line_no            INT NOT NULL,
  product_id         UUID NOT NULL REFERENCES app.products(id),
  qty                NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  cost               NUMERIC(18,4) NOT NULL CHECK (cost >= 0),
  vat_rate           NUMERIC(5,2) NOT NULL,
  vat_exemption_code TEXT NULL, -- imtiyoz kodi, products bo'linishi bilan izchil
  vat_amount         NUMERIC(18,2) NOT NULL DEFAULT 0,
  expiry_date        DATE NULL,
  discrepancy_reason TEXT NULL CHECK (discrepancy_reason IN ('short','excess','damaged','wrong_item','other')),
                     -- PO/e-faktura miqdoridan farq sababi (POS-08)
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (receipt_id, line_no)
);
