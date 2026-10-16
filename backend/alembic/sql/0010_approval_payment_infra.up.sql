-- 0010 approval_payment_infra — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- masofaviy tasdiq navbati (BO-16)
CREATE TABLE app.approval_requests (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  branch_id            UUID NOT NULL REFERENCES app.branches(id),
  kind                 TEXT NOT NULL CHECK (kind IN ('discount_over_limit','return_over_limit','return_no_receipt',
                         'debt_over_limit','cash_withdrawal_over_limit','price_change','expense_over_limit',
                         'write_off_over_limit','card_manual_entry')), -- card_manual_entry — qaror #71
  permission_code      TEXT NOT NULL, -- tasdiqlovchida bo'lishi shart kod (`15-xavfsizlik-va-audit.md` §2.3 xaritasi)
  requested_value      NUMERIC(18,4) NULL, -- summa yoki foiz (role_permissions.limit_value bilan bir xil birlik)
  context              JSONB NOT NULL DEFAULT '{}',
  linked_doc_type      TEXT NULL, -- jadval nomi ('price_changes','expenses',...)
  linked_doc_id        UUID NULL,
  device_id            UUID NULL REFERENCES app.devices(id),
  status               TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','approved','rejected','expired','consumed')),
  requested_by         UUID NOT NULL REFERENCES app.users(id),
  requested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at           TIMESTAMPTZ NOT NULL, -- requested_at + 15 daqiqa (standart, sozlanadi — 26 #87)
  resolved_by          UUID NULL REFERENCES app.users(id),
  resolved_at          TIMESTAMPTZ NULL,
  reject_reason        TEXT NULL,
  consumed_at          TIMESTAMPTZ NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status <> 'rejected' OR reject_reason IS NOT NULL),
  CHECK (status NOT IN ('approved','rejected','consumed') OR (resolved_by IS NOT NULL AND resolved_at IS NOT NULL)),
  CHECK (resolved_by IS NULL OR resolved_by <> requested_by) -- o'zini o'zi tasdiqlay olmaydi
);

CREATE INDEX idx_approval_requests_pending ON app.approval_requests (tenant_id, branch_id, requested_at)
  WHERE status = 'pending';

CREATE INDEX idx_approval_requests_linked ON app.approval_requests (tenant_id, linked_doc_type, linked_doc_id)
  WHERE linked_doc_id IS NOT NULL;

-- price_changes.approval_request_id qo'shilmaydi — bog'lanish linked_doc_type='price_changes' orqali.

-- qo'llangan har tasdiqning append-only izi
CREATE TABLE app.doc_approvals (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  doc_type             TEXT NOT NULL, -- 'sales','returns','cash_movements','expenses','write_offs','price_changes','debt_payments'
  doc_id               UUID NOT NULL,
  line_id              UUID NULL, -- chegirma — sale_lines.id; card_manual_entry — sale_payments.id (debt_payments/returns'da NULL)
  kind                 TEXT NOT NULL CHECK (kind IN ('discount_over_limit','return_over_limit','return_no_receipt',
                         'debt_over_limit','cash_withdrawal_over_limit','price_change','expense_over_limit',
                         'write_off_over_limit','card_manual_entry')), -- card_manual_entry — qaror #71
  mode                 TEXT NOT NULL CHECK (mode IN ('local_pin','remote_request')),
  approved_by          UUID NOT NULL REFERENCES app.users(id),
  approval_request_id  UUID NULL REFERENCES app.approval_requests(id),
  pin_verified_locally BOOLEAN NOT NULL DEFAULT false,
  requested_value      NUMERIC(18,4) NULL,
  approved_at          TIMESTAMPTZ NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (mode <> 'remote_request' OR approval_request_id IS NOT NULL),
  CHECK (mode <> 'local_pin' OR pin_verified_locally)
);

CREATE UNIQUE INDEX uq_doc_approvals_request ON app.doc_approvals (approval_request_id) WHERE approval_request_id IS NOT NULL;

CREATE INDEX idx_doc_approvals_doc ON app.doc_approvals (tenant_id, doc_type, doc_id);

-- Mavjud returns.approved_by/approved_at, price_changes.approved_by, debt_writeoffs.approved_by —
-- hujjat sarlavhasidagi "yakuniy tasdiqlovchi" sifatida qoladi; batafsil iz — doc_approvals.

-- UzQR/Click/Payme/Uzum to'lov seansi (faqat do'kon to'lovi; billing checkout — billing_payments)
CREATE TABLE app.payment_checkouts (
  checkout_ref     UUID PRIMARY KEY, -- qurilma beradi (UUIDv7)
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  device_id        UUID NULL REFERENCES app.devices(id),
  provider         TEXT NOT NULL CHECK (provider IN ('uzqr','click','payme','uzum')),
  qr_type          TEXT NULL CHECK (qr_type IN ('static','dynamic')),
  amount           NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  provider_tx_id   TEXT NULL,
  status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','confirmed','failed','expired','consumed')),
  confirmed_at     TIMESTAMPTZ NULL,
  expires_at       TIMESTAMPTZ NOT NULL,
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (provider = 'uzqr' OR qr_type IS NULL),
  CHECK (provider <> 'uzqr' OR qr_type = 'dynamic'), -- statik UzQR seanssiz: sale_payments'da kassir qo'lda tasdiqlaydi
  UNIQUE (provider, provider_tx_id)
);

CREATE INDEX idx_payment_checkouts_expiry ON app.payment_checkouts (expires_at) WHERE status = 'pending';

-- Webhook tenant kontekstisiz keladi → 4.5-bo'limdagi SECURITY DEFINER funksiyalar.

-- Integratsiyalangan bank karta terminallari reyestri (qaror #71). Bitta terminal — bitta filial; kassaga bog'lash
-- ixtiyoriy (bir kassada bir nechta terminal bo'lishi mumkin, is_default — POS avtomatik tanlaydigani).
-- adapter (21 §9.4): agent_ecr — AgentEcrAdapter, Do'kon agenti (127.0.0.1:47110/v1/card/*) orqali LAN/Wi-Fi'dagi
-- terminal; cloud — CloudTerminalAdapter, server ↔ vendor bulut API (terminal ID bo'yicha); android_intent — Kotlin POS
-- shu smart-terminaldagi vendor to'lov ilovasi (Intent/AIDL/SDK); softpos — SoftPosAdapter (NFC, MayaSoft SDK);
-- fake — FakeCardTerminalAdapter (dev/test/staging va demo-tenant, prod guard; real pul yo'q).
-- agent_id FK — 0028 store_agent da (fk_ct_agent), cash_registers.fiscal_agent_id naqshi.
CREATE TABLE app.card_terminals (
  id                       UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id                UUID NOT NULL REFERENCES app.tenants(id),
  branch_id                UUID NOT NULL REFERENCES app.branches(id),
  cash_register_id         UUID NULL REFERENCES app.cash_registers(id),
  name                     TEXT NOT NULL,                  -- BO-12 da ko'rinadigan nom ("Kassa 1 — Humo P3")
  vendor                   TEXT NOT NULL CHECK (vendor ~ '^[a-z0-9_]{2,32}$'), -- 'rahmat','era','humo','smartone','mayasoft','fake'
  model                    TEXT NULL,                      -- 'Sunmi P3', 'PAX A930' ...
  adapter                  TEXT NOT NULL CHECK (adapter IN ('agent_ecr','cloud','android_intent','softpos','fake')),
  driver                   TEXT NOT NULL CHECK (driver ~ '^[a-z0-9_]{2,40}$'), -- 'rahmat_lan','era_lan','arcus2_tcp','era_cloud','sunmi_intent','mayasoft_softpos','fake'
  agent_id                 UUID NULL,                      -- adapter='agent_ecr': xizmat qiluvchi Do'kon agenti
  local_id                 TEXT NULL,                      -- agent capabilities.card_terminal.devices[].local_id
  host                     INET NULL,                      -- terminalning LAN manzili (faqat xususiy tarmoq)
  port                     INT NULL CHECK (port IS NULL OR port BETWEEN 1 AND 65535),
  vendor_terminal_ref      TEXT NULL,                      -- adapter='cloud': vendor bulutidagi terminal ID
  tid                      TEXT NULL CHECK (tid IS NULL OR tid ~ '^[0-9A-Za-z]{1,16}$'), -- bank terminal ID (TID)
  mid                      TEXT NULL CHECK (mid IS NULL OR mid ~ '^[0-9A-Za-z]{1,20}$'), -- merchant ID (MID)
  acquirer_counterparty_id UUID NULL REFERENCES app.counterparties(id), -- ekvayer bank (bank_settlements solishtirish)
  status                   TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','archived')),
  is_default               BOOLEAN NOT NULL DEFAULT false,
  capabilities             JSONB NOT NULL DEFAULT '{}',
                           -- {refund, void, status_query, last_transaction, settlement, contactless, returns_card_type,
                           --  returns_bin} — adapter/agent hello'dan; POS faqat true bo'lgan amallarni taklif qiladi.
                           -- status — boshqaruv holati (BO-12); jonli holat — health_status (agent card.status vazifasi,
                           -- har 5 daqiqa, yoki POS health() natijasi)
  health_status            TEXT NOT NULL DEFAULT 'unknown' CHECK (health_status IN ('online','busy','offline','error','unknown')),
  health_checked_at        TIMESTAMPTZ NULL,
  created_by               UUID NOT NULL REFERENCES app.users(id),
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  version                  INT NOT NULL DEFAULT 1,
  CHECK (adapter <> 'agent_ecr' OR (agent_id IS NOT NULL AND local_id IS NOT NULL AND host IS NOT NULL)),
  CHECK (adapter <> 'cloud' OR vendor_terminal_ref IS NOT NULL),
  CHECK (adapter = 'agent_ecr' OR (agent_id IS NULL AND local_id IS NULL)),
  CHECK ((adapter = 'fake') = (driver = 'fake')),
  -- ixtiyoriy host yo'q: faqat RFC 1918 xususiy IPv4 (printer qoidasi kabi, 34 §14.3)
  CHECK (host IS NULL OR host << inet '10.0.0.0/8' OR host << inet '172.16.0.0/12' OR host << inet '192.168.0.0/16'),
  CHECK (adapter = 'fake' OR status <> 'active' OR tid IS NOT NULL),
  CHECK (NOT is_default OR cash_register_id IS NOT NULL)
);

CREATE UNIQUE INDEX uq_card_terminals_agent_local ON app.card_terminals (agent_id, local_id)
  WHERE agent_id IS NOT NULL AND status <> 'archived';

CREATE UNIQUE INDEX uq_card_terminals_tid ON app.card_terminals (tenant_id, tid)
  WHERE tid IS NOT NULL AND status <> 'archived';

CREATE UNIQUE INDEX uq_card_terminals_default ON app.card_terminals (cash_register_id)
  WHERE is_default AND status = 'active';

CREATE INDEX idx_card_terminals_register ON app.card_terminals (tenant_id, cash_register_id) WHERE status = 'active';
