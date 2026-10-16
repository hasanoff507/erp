-- 0002 core_tenant_user — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.tenants (
  id            UUID PRIMARY KEY DEFAULT app.uuidv7(),
  name          TEXT NOT NULL,
  activity_type TEXT NULL,
  stir          TEXT NULL,
  phone         TEXT NOT NULL,
  legal_form    TEXT NOT NULL DEFAULT 'llc' CHECK (legal_form IN ('llc','jsc','private_enterprise','sole_proprietor')),
                -- "Egasi oldi" hisobini belgilaydi (13-provodka-qoidalari.md §2.18): llc/jsc/private_enterprise → 4890, sole_proprietor → 8720
  go_live_date  DATE NULL, -- tizimda ishlash boshlangan sana; boshlang'ich qoldiqlar entry_date = go_live_date - 1 (13 §2.13, §2.21, §5.5)
  accepted_terms_version TEXT NULL,        -- qabul qilingan foydalanish shartlari versiyasi (aksept)
  accepted_terms_at      TIMESTAMPTZ NULL,
  accepted_terms_ip      INET NULL,
  settings      JSONB NOT NULL DEFAULT '{}', -- TenantSettings kalitlari (11-malumotlar-modeli.md §2):
  -- ai_training_consent, ai_cross_border_enabled (standart false — rozilik berilmaguncha AI'ga chegaradan tashqari
  -- uzatish yo'q), negative_stock_policy (allow/forbid), weight_barcode_templates[] (standart 22=WEIGHT, 21=AMOUNT),
  -- low_stock_check_enabled, expiry_warning_days (standart 7), vat_diff_tolerance_amount (standart "1000.00", qaror #50),
  -- supplier_overpay_policy ('warn'|'block', standart 'warn', qaror #47), discount_posting ('gross_9050'|'net', standart
  -- 'gross_9050'), owner_withdrawal_account ('4890'|'8720', standart legal_form'dan), payment_org_commission_account
  -- ('9430'|'9410', standart '9430'), turnover_tax_account ('9430'|'9820', standart '9430'), fiscal_policy
  -- {debt_receipt_split: 'single'|'per_sale' (standart 'single', qaror #45), credit_sale_receipt: 'none'|'credit_type'
  -- (standart 'none')}, marking_precheck ('off'|'warn'|'block', standart 'warn', qaror #62), bank_account (20 raqam),
  -- bank_mfo — tenantning yagona bank hisobi (qaror #49), payment_providers.{click|payme|uzum}.autofiscal_off_confirmed_at
  -- (ISO vaqt — provayder avtofiskalizatsiyasi o'chirilgani tasdig'i, 20 #40d), card_manual_fallback ('allow'|
  -- 'manager_approval'|'forbid' — faol card_terminals bog'langan kassada karta to'lovini terminalsiz (rekvizitsiz)
  -- qabul qilish siyosati, qaror #71; kalit yo'q bo'lsa 'manager_approval'; terminal bog'lanmagan kassada qo'llanmaydi —
  -- u yerda karta = faqat summa, manual_reason='standalone_terminal', har doim ruxsat). Baholash usuli BU YERDA EMAS — valuation_method_history
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  version       INT NOT NULL DEFAULT 1
);

-- (qaror #31) Bitta tenant = bitta yuridik shaxs (STIR), ko'p filial/kassa/faoliyat turi
-- (branches.activity_type) bitta tenant ichida; ko'p yuridik shaxsli egalar har bir shaxs uchun alohida tenant
-- ochadi va memberships orqali ular o'rtasida almashadi (tasdiqlandi — 13-provodka-qoidalari.md §5.4).

CREATE TABLE app.users (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  phone      TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL,
  locale     TEXT NOT NULL DEFAULT 'uz',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  version    INT NOT NULL DEFAULT 1
);

CREATE TABLE app.branches (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  code                 TEXT NOT NULL CHECK (code ~ '^[0-9A-Z]{1,4}$'), -- hujjat raqamidagi filial kodi, signup'da '01'
  name                 TEXT NOT NULL,
  address              TEXT NULL,
  is_default           BOOLEAN NOT NULL DEFAULT false,
  settlement_category  TEXT NOT NULL CHECK (settlement_category IN ('city_100k_plus','other','remote_mountain')),
  activity_type        TEXT NOT NULL CHECK (activity_type IN ('retail','other')),
  archived_at          TIMESTAMPTZ NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  version              INT NOT NULL DEFAULT 1,
  UNIQUE (tenant_id, code)
);

CREATE UNIQUE INDEX uq_branches_one_default ON app.branches (tenant_id) WHERE is_default AND archived_at IS NULL;

CREATE TABLE app.branch_tax_settings (
  id                  UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id           UUID NOT NULL REFERENCES app.tenants(id),
  branch_id           UUID NOT NULL REFERENCES app.branches(id),
  valid_from          DATE NOT NULL,
  settlement_category TEXT NOT NULL CHECK (settlement_category IN ('city_100k_plus','other','remote_mountain')),
  activity_type       TEXT NOT NULL CHECK (activity_type IN ('retail','other')),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by          UUID NOT NULL REFERENCES app.users(id),
  UNIQUE (branch_id, valid_from)
);

CREATE TABLE app.warehouses (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  branch_id   UUID NOT NULL REFERENCES app.branches(id),
  name        TEXT NOT NULL,
  type        TEXT NOT NULL CHECK (type IN ('store','stock')),
  inventory_account TEXT NOT NULL CHECK (inventory_account IN ('2910','2920')),
              -- tovar hisobi (13 §1 inv_acct): yaratishda type='store' → '2920', type='stock' → '2910' (ilova qo'yadi);
              -- omborda stock_moves bo'lgach o'zgartirilmaydi (409 WAREHOUSE_ACCOUNT_LOCKED)
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  version     INT NOT NULL DEFAULT 1
);

CREATE TABLE app.cash_registers (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  name             TEXT NOT NULL,
  kind             TEXT NOT NULL CHECK (kind IN ('web','android')),
  fiscal_module_id TEXT NULL,
  ofd_status       TEXT NOT NULL DEFAULT 'pending' CHECK (ofd_status IN ('pending','registered','active','suspended','deregistered')),
                   -- soliq ro'yxati holati; 'registered'/'active' bo'lmagan kassada fiskal chek chiqarilmaydi.
                   -- Fiskal hamkor holat kodlari adapterda shu qiymatlarga xaritalanadi (26 #89 (OQ-008))
  fm_state         TEXT NOT NULL DEFAULT 'unknown' CHECK (fm_state IN ('ok','locked','ack_overdue','memory_full','unknown')),
                   -- fiskal modul holati (FiscalPort.get_device_status); != 'ok' → FISCAL_DEVICE_LOCKED
  last_unacked_receipt_at TIMESTAMPTZ NULL, -- FM xabar qilgan eng eski OFD tasdiqlamagan chek vaqti
  fm_receipts_pending     INT NULL CHECK (fm_receipts_pending IS NULL OR fm_receipts_pending >= 0),
  tax_registered_at       TIMESTAMPTZ NULL, -- TXKM orqali soliq organida ro'yxatga olingan vaqt (VMQ-943 1-ilova 16–20-band)
  outlet_address_snapshot TEXT NULL,        -- ro'yxatdagi savdo shoxobchasi manzili (o'zgarsa 3 ish kunida qayta ariza)
  txkm_contract_ref       TEXT NULL,        -- TXKM bilan xizmat shartnomasi raqami
  fiscal_agent_id         UUID NULL,        -- lokal fiskal ko'prik kassasiga xizmat qiluvchi Do'kon agenti (qaror #66);
                                            -- FK 0028 store_agent da: fk_cr_fiscal_agent → app.onec_agents(id)
  fiscal_local_device_id  TEXT NULL,        -- agent capabilities.fiscal.devices[].local_id
  archived_at      TIMESTAMPTZ NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  version          INT NOT NULL DEFAULT 1,
  CHECK (fiscal_agent_id IS NULL OR fiscal_local_device_id IS NOT NULL)
);

CREATE TABLE app.devices (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  cash_register_id UUID NULL REFERENCES app.cash_registers(id),
  kind             TEXT NOT NULL CHECK (kind IN ('web','android','onec_agent')), -- onec_agent — mijoz kompyuteridagi 1C agenti (qaror #36/#38)
  app_version      TEXT NULL,
  revoked_at       TIMESTAMPTZ NULL,
  revoked_by       UUID NULL REFERENCES app.users(id),
  last_seen_at     TIMESTAMPTZ NULL,
  last_sync_at     TIMESTAMPTZ NULL,
  -- POST /sync/push outbox_state'idan (16-offline-sync.md §3.1): push qayta ishlangach last_sync_at bilan
  -- bitta tranzaksiyada yoziladi; faqat 1C eksporti tayyorligi uchun (33-1c-integratsiya.md §7.3 devices_synced).
  -- onec_agent qurilmasida doim NULL.
  outbox_pending_count     INT NULL,         -- outbox_state.pending_count + shu so'rovda rad etilgan voqealar soni
  outbox_oldest_pending_at TIMESTAMPTZ NULL, -- min(oldest_pending_created_at, rad etilganlarning created_at) — qurilma soati
  outbox_reported_at       TIMESTAMPTZ NULL, -- = now() o'sha push tranzaksiyasida
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (kind <> 'onec_agent' OR cash_register_id IS NULL)
  -- 'onec_agent' — Do'kon agenti (qaror #60): fiskal ko'prik, printer, tarozi va 1C imkoniyatlari shu qurilmada;
  -- kassaga bog'lanish cash_registers.fiscal_agent_id orqali (qaror #66)
);

CREATE TABLE app.memberships (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  user_id    UUID NOT NULL REFERENCES app.users(id),
  role_ids   UUID[] NOT NULL DEFAULT '{}',
  branch_ids UUID[] NOT NULL DEFAULT '{}', -- bo'sh = barcha filial
  status     TEXT NOT NULL CHECK (status IN ('active','blocked','invited')) DEFAULT 'active',
  -- 'invited' — BO-11 boshqa tenantda allaqachon mavjud foydalanuvchini taklif qilgan, u hali kod bilan
  -- qabul qilmagan (14 §18.2): login/tenant tanlovi/switch-tenant/sessiya profili uni e'tiborsiz qoldiradi
  invited_name TEXT NULL,
  -- taklif qiluvchi kiritgan ism: qabul qilinmaguncha (NOT NULL = hali qabul qilinmagan) BO-11 ro'yxatida
  -- users.name o'rniga ko'rsatiladi; qabulda NULL bo'ladi. Qabul qilinmagan a'zolik bloklansa, blokdan
  -- chiqarish uni 'invited'ga qaytaradi ('active'ga emas)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  version    INT NOT NULL DEFAULT 1,
  UNIQUE (tenant_id, user_id),
  CHECK (status <> 'invited' OR invited_name IS NOT NULL)
);

CREATE TABLE app.roles (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  name        TEXT NOT NULL,
  is_system   BOOLEAN NOT NULL DEFAULT false,
  system_code TEXT NULL CHECK (system_code IN ('owner','manager','cashier','storekeeper','accountant')),
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  version     INT NOT NULL DEFAULT 1,
  UNIQUE (tenant_id, name)
);

CREATE TABLE app.role_permissions (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  role_id         UUID NOT NULL REFERENCES app.roles(id),
  permission_code TEXT NOT NULL,
  limit_value     NUMERIC(18,4) NULL, -- ma'nosi permission_code'ga bog'liq: foiz YOKI summa (3-bo'lim, aniqlashtirish #6);
  -- API'da 4 xonali satr ("5.0000"), UI foiz/so'mni permission_code'ga qarab formatlaydi
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (role_id, permission_code)
);
