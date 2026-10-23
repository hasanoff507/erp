-- 0014 docs_inventory — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.transfers (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id), -- aniqlashtirish: jo'natuvchi filial sifatida ishlatiladi
  number           TEXT NULL,
  temp_number      TEXT NULL,
  doc_date         DATE NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('draft','posted','sent','received','discrepancy','cancelled')) DEFAULT 'draft',
                   -- posted = hujjat o'tkazildi + e-TTN yaratildi (qoldiq o'zgarmaydi); sent = stock_moves jo'natuvchida −
  from_branch_id   UUID NOT NULL REFERENCES app.branches(id),
  to_branch_id     UUID NOT NULL REFERENCES app.branches(id),
  from_warehouse_id UUID NOT NULL, -- FK app.warehouses(id)
  to_warehouse_id   UUID NOT NULL, -- FK app.warehouses(id)
  sent_at          TIMESTAMPTZ NULL,
  sent_by          UUID NULL REFERENCES app.users(id),
  received_at      TIMESTAMPTZ NULL,
  received_by      UUID NULL REFERENCES app.users(id),
  transport_mode   TEXT NOT NULL DEFAULT 'vehicle' CHECK (transport_mode IN ('vehicle','on_foot_or_public')),
                   -- vehicle — e-TTN ("Ombordan omborga") majburiy; on_foot_or_public — e-TTN talab qilinmaydi
  ettn_ref         TEXT NULL, -- operator kabinetida rasmiylashtirilgan e-TTN raqami; send — transport_mode='vehicle' da
                   -- e-TTN registered bo'lmaguncha rad (409 ETTN_REQUIRED)
  vehicle_plate    TEXT NULL, -- e-TTN rekviziti; transport_mode='vehicle' bo'lsa post'da shart (ilova tekshiradi)
  driver_name      TEXT NULL, -- e-TTN rekviziti
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
  CHECK (from_branch_id <> to_branch_id),
  CHECK (branch_id = from_branch_id)
);

ALTER TABLE app.transfers ADD CONSTRAINT fk_tr_from_wh FOREIGN KEY (from_warehouse_id) REFERENCES app.warehouses(id);

ALTER TABLE app.transfers ADD CONSTRAINT fk_tr_to_wh   FOREIGN KEY (to_warehouse_id)   REFERENCES app.warehouses(id);

-- bitta qator FIFO bo'yicha bir nechta partiyadan chiqishi mumkin — bitta lot_id yetarli emas,
-- shuning uchun lot_allocations JSONB ishlatiladi (sale_lines bilan bir xil shakl), alohida lot_id ustuni yo'q.
CREATE TABLE app.transfer_lines (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  transfer_id UUID NOT NULL REFERENCES app.transfers(id),
  line_no     INT NOT NULL,
  product_id  UUID NOT NULL REFERENCES app.products(id),
  qty_sent    NUMERIC(18,3) NOT NULL CHECK (qty_sent > 0),
  qty_received NUMERIC(18,3) NULL CHECK (qty_received IS NULL OR qty_received >= 0),
  unit_cost       NUMERIC(18,4) NULL, -- send'da to'ldiriladi (allokatsiyalarning o'rtachasi)
  lot_allocations JSONB NOT NULL DEFAULT '[]', -- [{lot_id, qty, unit_cost}] — sale_lines bilan bir xil shakl
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (transfer_id, line_no)
);

CREATE TABLE app.stock_counts (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('counting','review','posted','cancelled')) DEFAULT 'counting',
  warehouse_id    UUID NOT NULL, -- FK app.warehouses(id)
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(), -- snapshot vaqti (qaror #53)
  responsible_user_id UUID NULL REFERENCES app.users(id), -- ko'rsatilsa kamomad → 4730, aks holda 5910 (13 §2.11)
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

ALTER TABLE app.stock_counts ADD CONSTRAINT fk_sc_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);

CREATE TABLE app.count_lines (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  count_id   UUID NOT NULL REFERENCES app.stock_counts(id),
  line_no    INT NOT NULL,
  product_id UUID NOT NULL REFERENCES app.products(id),
  snapshot_qty NUMERIC(18,3) NOT NULL, -- stock_counts.started_at holatidagi qoldiq
  expected   NUMERIC(18,3) NOT NULL, -- yaratishda = snapshot_qty; post'da qayta hisoblanadi (qaror #53, 13 X-02):
             -- snapshot_qty + Σ stock_moves.qty (started_at < moved_at <= counted_at)
  counted    NUMERIC(18,3) NULL, -- sanash tugamaguncha NULL (19-api-ombor.md `counted:null`)
  counted_at TIMESTAMPTZ NULL, -- counted kiritilgan vaqt (qaror #53): qurilma vaqti (offline sanashda ham —
             -- voqeaning recorded_at'i, server_time ofseti bilan tuzatilgan), online kiritishda — server vaqti;
             -- counted NULL bo'lsa NULL
  diff       NUMERIC(18,3) GENERATED ALWAYS AS (counted - expected) STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (count_id, line_no),
  CHECK ((counted IS NULL) = (counted_at IS NULL))
);

CREATE TABLE app.write_offs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  warehouse_id    UUID NOT NULL, -- FK app.warehouses(id)
  responsible_user_id UUID NULL REFERENCES app.users(id), -- belgilansa 4730 (13-provodka-qoidalari.md §2.12)
  promo_order_ref TEXT NULL, -- reklama aksiyasi buyrug'i raqami; gift_kind='promo_justified' qatori bo'lsa majburiy (ilova tekshiradi)
  source_return_id UUID NULL REFERENCES app.returns(id), -- muddati o'tgan tovar qaytarilganda avtomatik qoralama (qaror #48)
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

ALTER TABLE app.write_offs ADD CONSTRAINT fk_wo_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);

CREATE TABLE app.write_off_lines (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  write_off_id UUID NOT NULL REFERENCES app.write_offs(id),
  line_no     INT NOT NULL,
  product_id  UUID NOT NULL REFERENCES app.products(id),
  lot_id      UUID NULL, -- FK app.stock_lots(id) — 2.7-bo'limda qo'shiladi
  qty         NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  reason      TEXT NOT NULL CHECK (reason IN ('expired','damaged','gift','expired_return','other')),
  gift_kind   TEXT NULL CHECK (gift_kind IN ('promo_justified','other')), -- 13 §2.12: promo_justified → 9410, QQSsiz; other → 9430 + QQS
  cost_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (write_off_id, line_no),
  CHECK ((reason = 'gift') = (gift_kind IS NOT NULL))
);

CREATE TABLE app.stock_openings (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  warehouse_id    UUID NOT NULL, -- FK app.warehouses(id)
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

ALTER TABLE app.stock_openings ADD CONSTRAINT fk_so_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);

CREATE TABLE app.opening_lines (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  opening_id  UUID NOT NULL REFERENCES app.stock_openings(id),
  line_no     INT NOT NULL,
  product_id  UUID NOT NULL REFERENCES app.products(id),
  qty         NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  unit_cost   NUMERIC(18,4) NOT NULL CHECK (unit_cost >= 0),
  expiry_date DATE NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (opening_id, line_no)
);
