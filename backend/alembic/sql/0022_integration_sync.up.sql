-- 0022 integration_sync — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- Tenant darajasidagi integratsiya hisob ma'lumotlari (CRPT, Click/Payme/Uzum, UzQR, Faktura.uz, E-IMZO) —
-- `21-integratsiyalar.md` kirish qismi #7, `20-api-moliya-admin.md` (integratsiya sozlamalari), `27-backlog.md`.
-- `ciphertext` — KEK orqali konvert-shifrlangan (platform.oauth_clients.client_secret_encrypted bilan bir xil
-- naqsh), API hech qachon qaytarmaydi (faqat yozish/almashtirish, `kind` + `rotated_at` ko'rinadi).
-- RLS: oddiy tenant jadvali — 4.2-bo'limdagi `tenant_isolation` siyosati (0026-revizion) qo'llanadi.
CREATE TABLE app.tenant_secrets (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  branch_id   UUID NULL REFERENCES app.branches(id), -- NULL = butun tenant uchun yagona (filialga xos bo'lmagan)
  cash_register_id UUID NULL REFERENCES app.cash_registers(id), -- uzqr: dinamik QR API kaliti har kassa uchun alohida
  kind        TEXT NOT NULL CHECK (kind IN ('faktura_uz','crpt','click','payme','uzum','uzqr','fiscal_partner','eimzo',
                                    'card_terminal_vendor')), -- card_terminal_vendor — CloudTerminalAdapter (qaror #71)
  ciphertext  BYTEA NOT NULL,
  key_version INT NOT NULL,
  rotated_at  TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (tenant_id, branch_id, cash_register_id, kind),
  CHECK (cash_register_id IS NULL OR kind = 'uzqr')
);

CREATE TABLE app.outbox_jobs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  kind            TEXT NOT NULL CHECK (kind IN ('ofd_send','einvoice_send','einvoice_accept','ettn_send',
                     'ettn_accept','poa_send','marking_verify','marking_accept','marking_supplier_return',
                     'marking_writeoff','state_report_reminder','sms','telegram','ai','report_export','label_pdf',
                     'billing_webhook_reconcile')),
                  -- ofd_send — faqat ERP_FISCAL_PROVIDER=partner_cloud rejimida (lokal ko'prikda chekni agent/FM yuboradi)
  payload         JSONB NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('queued','running','done','retry','failed')) DEFAULT 'queued',
  attempts        INT NOT NULL DEFAULT 0,
  next_run_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_error      TEXT NULL,
  idempotency_key TEXT NOT NULL,
  created_by           UUID NULL REFERENCES app.users(id), -- eksport job'ini faqat yaratuvchi/Egasi ko'radi
  progress_pct         SMALLINT NULL CHECK (progress_pct BETWEEN 0 AND 100),
  result_attachment_id UUID NULL REFERENCES app.attachments(id),
  error_code           TEXT NULL, -- 17-api-umumiy.md xato kodlari katalogidan (masalan EXPORT_JOB_FAILED)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);

-- API holati xaritasi: 'retry' → API'da 'running' sifatida ko'rsatiladi
CREATE INDEX idx_outbox_jobs_due ON app.outbox_jobs (next_run_at) WHERE status IN ('queued','retry');

CREATE TABLE app.sync_receipts (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  device_id       UUID NOT NULL REFERENCES app.devices(id),
  client_event_id UUID NOT NULL,
  received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  result          JSONB NOT NULL,
  UNIQUE (tenant_id, client_event_id)
);

-- sinxron istisnolari (16-offline-sync.md §5): offline narx farqi, arxivlangan tovar, manfiy qoldiq, limitdan
-- oshgan nasiya/tasdiq limiti, qarz to'lovi farqlari, yopilgan davrga kech kelgan voqea va h.k. — axborot, voqea
-- rad etilmaydi; BO-14 "Sinxron istisnolari" (qaror #56)
CREATE TABLE app.sync_exceptions (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  device_id       UUID NULL REFERENCES app.devices(id),
  client_event_id UUID NULL,
  kind            TEXT NOT NULL CHECK (kind IN ('price_mismatch','archived_product','stock_negative',
                    'debt_limit_exceeded_offline','approval_limit_exceeded_offline','receipt_seq_conflict',
                    'debt_overpayment_offline','debt_allocation_mismatch','late_in_closed_period','cost_unknown',
                    'count_late_move','card_result_mismatch','card_orphan_transaction')), -- 16 §5 ro'yxati
  doc_type        TEXT NULL,
  doc_id          UUID NULL,
  details         JSONB NOT NULL DEFAULT '{}',
  reviewed_at     TIMESTAMPTZ NULL,
  reviewed_by     UUID NULL REFERENCES app.users(id),
  review_note     TEXT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (reviewed_at IS NULL OR (reviewed_by IS NOT NULL AND review_note IS NOT NULL))
);

CREATE INDEX idx_sync_exceptions_open ON app.sync_exceptions (tenant_id, created_at) WHERE reviewed_at IS NULL;

CREATE TABLE app.idempotency_keys (
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  key             TEXT NOT NULL,
  request_hash    TEXT NOT NULL,
  response_status INT NOT NULL,
  response_body   JSONB NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, key)
);

CREATE INDEX idx_idempotency_keys_cleanup ON app.idempotency_keys (created_at);

CREATE TABLE app.recost_jobs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id    UUID NOT NULL REFERENCES app.warehouses(id),
  product_id      UUID NOT NULL REFERENCES app.products(id),
  from_date       DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('queued','running','done','failed','rejected_period_closed')) DEFAULT 'queued',
  reason_doc_type TEXT NOT NULL,
  reason_doc_id   UUID NOT NULL,
  attempts        INT NOT NULL DEFAULT 0,
  last_error      TEXT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at     TIMESTAMPTZ NULL
);

-- bitta (tenant, warehouse, product) uchun bir vaqtda faqat bitta "queued" job
CREATE UNIQUE INDEX uq_recost_jobs_queued ON app.recost_jobs (tenant_id, warehouse_id, product_id) WHERE status = 'queued';

CREATE TABLE app.import_jobs (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  kind       TEXT NOT NULL CHECK (kind IN ('products','opening_stock','opening_debts')),
  attachment_id UUID NOT NULL REFERENCES app.attachments(id),
  status     TEXT NOT NULL CHECK (status IN ('uploaded','validating','validated','committing','committed','failed')) DEFAULT 'uploaded',
  total_rows INT NOT NULL DEFAULT 0,
  ok_rows    INT NOT NULL DEFAULT 0,
  errors     JSONB NOT NULL DEFAULT '[]',
  result     JSONB NOT NULL DEFAULT '{}', -- {"created_doc_ids":[...], "created_product_count":n}
  created_by UUID NOT NULL REFERENCES app.users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 0022 integration_sync
REVOKE UPDATE, DELETE ON app.sync_receipts FROM erp_app;

CREATE TRIGGER trg_no_update_delete BEFORE UPDATE OR DELETE ON app.sync_receipts
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
