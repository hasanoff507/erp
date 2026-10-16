-- 0021 ai_ocr_jobs — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.ai_requests (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  user_id           UUID NULL REFERENCES app.users(id),
  feature           TEXT NOT NULL,
  model             TEXT NOT NULL,
  prompt_version    TEXT NULL,
  input_tokens      INT NOT NULL DEFAULT 0,
  output_tokens     INT NOT NULL DEFAULT 0,
  cache_read_tokens INT NOT NULL DEFAULT 0,
  cost_usd          NUMERIC(12,6) NOT NULL DEFAULT 0,
  fx_rate_used      NUMERIC(12,4) NULL,
  cost_uzs          NUMERIC(18,2) NULL,
  latency_ms        INT NULL,
  guard_result      TEXT NULL,
  status            TEXT NOT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_requests_tenant_month ON app.ai_requests (tenant_id, created_at);

-- AI hujjat yozmaydi — tasdiqdan keyin qoralama hujjat (goods_receipts/stock_openings) yoki mahsulot kartochkalari
-- (catalog — created_product_ids) yaratiladi. Qaytarish OCR orqali yaratilmaydi (returns faqat POS sync orqali).
CREATE TABLE app.ai_ocr_jobs (
  id                    UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id             UUID NOT NULL REFERENCES app.tenants(id),
  branch_id             UUID NULL REFERENCES app.branches(id),
  created_by            UUID NOT NULL REFERENCES app.users(id),
  attachment_id         UUID NOT NULL REFERENCES app.attachments(id),
  doc_type_hint         TEXT NOT NULL DEFAULT 'purchase' CHECK (doc_type_hint IN ('purchase','catalog')), -- 20-api-moliya-admin.md #73–75
  status                TEXT NOT NULL DEFAULT 'processing'
                          CHECK (status IN ('processing','done','failed','confirmed','expired')),
  fields                JSONB NULL, -- {header:{supplier_name:{value,confidence},...}, lines:[{...}]}
  low_confidence_fields TEXT[] NOT NULL DEFAULT '{}', -- masalan 'lines[0].product_name'
  error_code            TEXT NULL, -- 'OCR_IMAGE_UNREADABLE', 'AI_PROVIDER_UNAVAILABLE'
  ai_request_id         UUID NULL REFERENCES app.ai_requests(id),
  created_doc_type      TEXT NULL CHECK (created_doc_type IN ('goods_receipts','stock_openings')), -- (#75 javobi)
  created_doc_id        UUID NULL,
  created_product_ids   UUID[] NOT NULL DEFAULT '{}', -- catalog tasdig'ida yaratilgan mahsulotlar
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at           TIMESTAMPTZ NULL,
  confirmed_at          TIMESTAMPTZ NULL,
  expires_at            TIMESTAMPTZ NOT NULL, -- created_at + 7 kun (standart, sozlanadi), keyin 'expired' va fields tozalanadi
  CHECK (status <> 'confirmed' OR ((created_doc_id IS NOT NULL OR cardinality(created_product_ids) > 0)
                                   AND confirmed_at IS NOT NULL)),
  CHECK ((created_doc_type IS NULL) = (created_doc_id IS NULL))
);

CREATE INDEX idx_ai_ocr_jobs_expiry ON app.ai_ocr_jobs (expires_at) WHERE status IN ('processing','done');

ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_ocr_job FOREIGN KEY (ai_ocr_job_id) REFERENCES app.ai_ocr_jobs(id);
