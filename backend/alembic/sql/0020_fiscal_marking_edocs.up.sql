-- 0020 fiscal_marking_edocs — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- kind='z_report' — smena yopilganda Z-hisobot shu jadvalga yoziladi (sale_id/return_id/receipt_seq hammasi
-- NULL, raqami = shifts.shift_no). kind='debt_settlement' — qarz to'lovida chiqariladigan chek, debt_payment_id
-- orqali bog'lanadi; har doim cash_register_id, shift_id, receipt_seq bilan; bank o'tkazmasi orqali qarz to'lovida
-- chek yaratilmaydi (qaror #67). Lokal ko'prik rejimida FM natijasi POS voqeasining fiscal_result'idan yoziladi
-- (qaror #68); receipt_seq to'qnashuvida server qayta raqamlaydi, qurilma qiymati payload.device_receipt_seq da. Chek
-- matni/payload ikki tilda chiqariladi (o'zbek + ixtiyoriy rus — `products.name_ru`, qaror #29).
-- kind='credit_sale' — nasiya sotuvda "kredit" turidagi chek (QR va fiskal belgisiz, VMQ-943 1-ilova 7-band),
-- faqat tenants.settings.fiscal_policy.credit_sale_receipt='credit_type' bo'lsa yaratiladi.
-- payload.items[] har qatorda: mxik (17 raqam), package_code, katalog o'lchov birligi, marking_codes[] (GS bilan aynan).
-- 48 soatlik blok (qaror #43): shu kassada ofd_acked_at IS NULL bo'lgan eng eski fiskal chek created_at'idan
-- 48 soat o'tsa yangi fiskal chek yaratilmaydi (FISCAL_OFFLINE_48H_BLOCKED) — idx_fiscal_receipts_unacked.
CREATE TABLE app.fiscal_receipts (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  kind             TEXT NOT NULL CHECK (kind IN ('sale','return','z_report','debt_settlement','credit_sale')),
  sale_id          UUID NULL REFERENCES app.sales(id),
  return_id        UUID NULL REFERENCES app.returns(id),
  debt_payment_id  UUID NULL REFERENCES app.debt_payments(id), -- (qaror #30) kind='debt_settlement'da majburiy
  cash_register_id UUID NULL REFERENCES app.cash_registers(id), -- barcha turlarda majburiy (CHECK pastda)
  shift_id         UUID NULL REFERENCES app.shifts(id), -- xuddi shunday
  receipt_seq      INT  NULL, -- qurilma beradi (qaror #12); faqat z_report'da NULL
  fm_terminal_id   TEXT NULL, -- fiskal modul (FM) seriya raqami — FiscalResult.terminal_id
  fm_receipt_seq   BIGINT NULL, -- FM bergan chek raqami (OFD ReceiptSeq); receipt_seq'dan alohida
  fiscal_at        TIMESTAMPTZ NULL, -- FM imzolagan vaqt (FiscalResult.fiscal_datetime)
  payload          JSONB NOT NULL,
  fiscal_sign      TEXT NULL,
  qr_url           TEXT NULL,
  payment_form     TEXT NULL CHECK (payment_form IN ('cash','card','qr','mixed')),
                   -- chek "to'lov shakli" rekviziti: cash; card; uzqr/click/payme/uzum → qr; bir nechta shakl → mixed. z_report'da NULL
  delivery         TEXT NOT NULL DEFAULT 'printed' CHECK (delivery IN ('printed','electronic')),
  delivery_reason  TEXT NULL, -- electronic bo'lsa majburiy (printer nosoz / xaridor so'radi), audit
  sent_at          TIMESTAMPTZ NULL,
  ofd_acked_at     TIMESTAMPTZ NULL, -- OFD tasdig'i olingan vaqt; NULL — 48 soatlik hisoblagichga kiradi
  offline_since    TIMESTAMPTZ NULL,
  status           TEXT NOT NULL CHECK (status IN ('pending','sent','fiscalized','failed')) DEFAULT 'pending',
  attempts         INT NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (delivery = 'printed' OR delivery_reason IS NOT NULL),
  CHECK (kind = 'z_report' OR payment_form IS NOT NULL),
  CHECK (
       (kind IN ('sale','credit_sale') AND sale_id IS NOT NULL AND return_id IS NULL AND debt_payment_id IS NULL AND receipt_seq IS NOT NULL AND cash_register_id IS NOT NULL AND shift_id IS NOT NULL)
    OR (kind = 'return'          AND return_id IS NOT NULL AND sale_id IS NULL AND debt_payment_id IS NULL AND receipt_seq IS NOT NULL AND cash_register_id IS NOT NULL AND shift_id IS NOT NULL)
    OR (kind = 'z_report'        AND sale_id IS NULL AND return_id IS NULL AND debt_payment_id IS NULL AND receipt_seq IS NULL AND cash_register_id IS NOT NULL AND shift_id IS NOT NULL)
    OR (kind = 'debt_settlement' AND debt_payment_id IS NOT NULL AND sale_id IS NULL AND return_id IS NULL AND receipt_seq IS NOT NULL AND cash_register_id IS NOT NULL AND shift_id IS NOT NULL)
  ),
  UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)
);

CREATE UNIQUE INDEX uq_fiscal_z_per_shift ON app.fiscal_receipts (shift_id) WHERE kind = 'z_report';

CREATE INDEX idx_fiscal_receipts_pending ON app.fiscal_receipts (tenant_id) WHERE status IN ('pending','failed');

CREATE INDEX idx_fiscal_receipts_unacked ON app.fiscal_receipts (cash_register_id, created_at)
  WHERE ofd_acked_at IS NULL AND kind <> 'z_report';

CREATE UNIQUE INDEX uq_fiscal_fm_seq ON app.fiscal_receipts (tenant_id, fm_terminal_id, fm_receipt_seq)
  WHERE fm_receipt_seq IS NOT NULL;

CREATE TABLE app.marking_codes (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  code        TEXT NOT NULL, -- DataMatrix
  product_id  UUID NOT NULL REFERENCES app.products(id),
  status      TEXT NOT NULL CHECK (status IN ('in_stock','sold','returned','written_off','returned_to_supplier','pending_verification')),
  last_doc_id UUID NULL,
  verified_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, code)
);

CREATE INDEX idx_marking_codes_pending_verif ON app.marking_codes (tenant_id) WHERE status = 'pending_verification';

ALTER TABLE app.sale_lines ADD CONSTRAINT fk_sl_marking
  FOREIGN KEY (tenant_id, marking_code) REFERENCES app.marking_codes(tenant_id, code) DEFERRABLE INITIALLY DEFERRED;

-- SalePostingService sale_lines'dan oldin, shu tranzaksiyada INSERT INTO marking_codes ...
-- ON CONFLICT (tenant_id, code) DO UPDATE SET status=..., last_doc_id=... bajaradi
-- (status='pending_verification'; chek OFD tasdig'ini olgach — fiscal_receipts.ofd_acked_at — 'sold', qaror #62,
-- 18 §4.2, 16 §7); FK DEFERRABLE shu tartibni kafolatlaydi.

CREATE TABLE app.einvoices (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  direction       TEXT NOT NULL CHECK (direction IN ('in','out')),
  operator        TEXT NOT NULL CHECK (operator IN ('didox','faktura')),
  operator_doc_id TEXT NULL,
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  related_doc_type TEXT NULL,
  related_doc_id  UUID NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','received','signed','sent','accepted','rejected','cancelled')),
  number          TEXT NULL, -- operator/faktura raqami
  doc_date        DATE NULL,
  total_amount    NUMERIC(18,2) NULL,
  vat_amount      NUMERIC(18,2) NULL,
  signed_by       UUID NULL REFERENCES app.users(id),
  risk_flag       TEXT NOT NULL DEFAULT 'unknown' CHECK (risk_flag IN ('green','red','unknown')),
                  -- VM 830 xavf darajasi (Didox `scoring`; Faktura.uz — unknown); unknown — QQS krediti qizil kabi
                  -- to'lovgacha kechiktiriladi (13 §2.8), Buxgalter BO-15'da qo'lda belgilaydi
  factura_type    TEXT NOT NULL DEFAULT 'standard' CHECK (factura_type IN ('standard','additional','corrected')),
  related_einvoice_id UUID NULL REFERENCES app.einvoices(id), -- additional/corrected — asl EHF
  signed_at       TIMESTAMPTZ NULL,
  payload         JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (related_doc_type IS NULL OR related_doc_type IN ('sales','goods_receipts','supplier_returns')),
  CHECK (factura_type = 'standard' OR related_einvoice_id IS NOT NULL)
);

-- 13-provodka-qoidalari.md §2.22 cheklovi: bitta chekka bitta faol chiquvchi faktura
CREATE UNIQUE INDEX uq_einvoice_out_per_doc ON app.einvoices (tenant_id, related_doc_type, related_doc_id)
  WHERE direction = 'out' AND related_doc_id IS NOT NULL AND status <> 'cancelled';

CREATE UNIQUE INDEX uq_einvoice_operator_doc ON app.einvoices (tenant_id, operator, operator_doc_id)
  WHERE operator_doc_id IS NOT NULL;

ALTER TABLE app.vat_moves ADD CONSTRAINT fk_vm_einvoice FOREIGN KEY (einvoice_id) REFERENCES app.einvoices(id);

-- goods_receipts.einvoice_id shu yerda FK bilan bog'lanadi (einvoices jadvali yuqorida yaratilgan):
ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_einvoice FOREIGN KEY (einvoice_id) REFERENCES app.einvoices(id);

CREATE UNIQUE INDEX uq_gr_einvoice_active ON app.goods_receipts (tenant_id, einvoice_id)
  WHERE einvoice_id IS NOT NULL AND status <> 'cancelled';

-- E-ishonchnoma (BO-04 → E-IMZO → operator, 19 §8a). Holatlar: draft → pending_signature → sending → sent →
-- accepted | rejected; sending → failed → sending (qayta imzo/yuborish); draft | pending_signature → cancelled.
-- Yuborish — outbox_jobs(kind='poa_send'), EInvoicePort.send_power_of_attorney.
CREATE TABLE app.powers_of_attorney (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  purchase_order_id UUID NULL REFERENCES app.purchase_orders(id),
  supplier_id      UUID NOT NULL REFERENCES app.counterparties(id),
  employee_user_id UUID NOT NULL REFERENCES app.users(id),   -- ishonchli shaxs (odatda Omborchi)
  doc_date         DATE NOT NULL,
  valid_from       DATE NOT NULL,
  valid_to         DATE NOT NULL,
  number           TEXT NULL,                                -- operator bergan raqam
  operator_doc_id  TEXT NULL,
  status           TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending_signature','sending','sent',
                     'accepted','rejected','cancelled','failed')),
  last_error       TEXT NULL,
  signed_at        TIMESTAMPTZ NULL,
  sent_at          TIMESTAMPTZ NULL,
  responded_at     TIMESTAMPTZ NULL,
  reject_reason    TEXT NULL,
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  version          INT NOT NULL DEFAULT 1,
  CHECK (valid_to >= valid_from)
);

CREATE INDEX idx_poa_po ON app.powers_of_attorney (tenant_id, purchase_order_id);

ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_poa FOREIGN KEY (poa_id) REFERENCES app.powers_of_attorney(id);

-- e-TTN: kiruvchi xaridda EHF bilan birlashtirilgan (einvoice_id); ichki ko'chirishda ("Ombordan omborga")
-- yozuvchi — transfer `post` (transfer_id; qaror #63, 19 §13).
CREATE TABLE app.ettn_documents (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  einvoice_id     UUID NULL REFERENCES app.einvoices(id),
  transfer_id     UUID NULL REFERENCES app.transfers(id),
  transport_type  TEXT NOT NULL CHECK (transport_type IN ('warehouse_to_warehouse','seller_to_buyer','other')),
  direction       TEXT NOT NULL CHECK (direction IN ('in','out')),
  status          TEXT NOT NULL CHECK (status IN ('pending_signature','sending','registered','received','accepted',
                    'rejected','cancelled','failed')),
                  -- chiquvchi: pending_signature → sending → registered → accepted/rejected; sending → failed → sending
                  -- (qayta imzo/yuborish); kiruvchi: received → accepted/rejected; cancelled
  counterparty_id UUID NULL REFERENCES app.counterparties(id), -- kiruvchi: jo'natuvchi; chiquvchi (seller_to_buyer): oluvchi
  receipt_id      UUID NULL REFERENCES app.goods_receipts(id), -- kiruvchi e-TTN bog'langan kirim
  doc_date        DATE NULL,
  payload         JSONB NOT NULL DEFAULT '{}',
  signed_at       TIMESTAMPTZ NULL,
  last_error      TEXT NULL,
  operator_doc_id TEXT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (direction = 'in' OR einvoice_id IS NOT NULL OR transfer_id IS NOT NULL),
  CHECK (transport_type <> 'warehouse_to_warehouse' OR transfer_id IS NOT NULL)
);

CREATE TABLE app.state_reports (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  tax_type           TEXT NOT NULL CHECK (tax_type IN ('vat','turnover')), -- MVP: QQS va aylanma solig'i (05 §1.3 — mol-mulk/yer/JShDS/ijtimoiy Won't)
  period             DATE NOT NULL,
  published_at       TIMESTAMPTZ NULL,
  deadline_at        TIMESTAMPTZ NULL, -- min(published_at + 5 ish kuni, topshirish muddati) (SK 5-modda 7-qism, 81-modda 6-qism)
  file_attachment_id UUID NULL REFERENCES app.attachments(id),
  status             TEXT NOT NULL CHECK (status IN ('uploaded','compared','match','diff_found','correction_sent','confirmed',
                       'auto_accepted')),
                     -- uploaded → compared → match | diff_found → correction_sent | confirmed | auto_accepted
  state_amount         NUMERIC(18,2) NULL,
  our_amount           NUMERIC(18,2) NULL,
  diff_amount          NUMERIC(18,2) NULL,
  compared_at          TIMESTAMPTZ NULL,
  correction_sent_at   TIMESTAMPTZ NULL,
  correction_comment   TEXT NULL, -- my.soliq.uz kabinetida kiritilgan tuzatish izohi (tizim faqat qayd etadi, imzosiz)
  correction_portal_ref TEXT NULL, -- kabinetdagi tuzatish raqami (ixtiyoriy)
  confirmed_at         TIMESTAMPTZ NULL,
  confirmed_by         UUID NULL REFERENCES app.users(id),
  uploaded_by          UUID NOT NULL REFERENCES app.users(id),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tolerantlik — tenants.settings.vat_diff_tolerance_amount

CREATE TABLE app.state_report_diffs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  state_report_id UUID NOT NULL REFERENCES app.state_reports(id),
  indicator       TEXT NOT NULL,
  state_value     NUMERIC(18,2) NULL,
  our_value       NUMERIC(18,2) NULL,
  diff            NUMERIC(18,2) NULL,
  explanation     TEXT NULL,
  resolved        BOOLEAN NOT NULL DEFAULT false,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
