-- 0028 store_agent — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.onec_agents (
  id                      UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id               UUID NOT NULL REFERENCES app.tenants(id),
  device_id               UUID NOT NULL REFERENCES app.devices(id),
  client_id               TEXT NOT NULL,                 -- 'onec-agent:' || id — private_key_jwt iss/sub
  name                    TEXT NOT NULL,                 -- BO'da ko'rinadigan nom (standart = pc_name)
  pc_name                 TEXT NOT NULL,
  machine_hash            TEXT NOT NULL CHECK (machine_hash ~ '^[0-9a-f]{64}$'), -- SHA-256(MachineGuid|user SID) — agent hisoblaydi
  os_version              TEXT NULL,
  agent_version           TEXT NULL,
  worker_bits             SMALLINT[] NOT NULL DEFAULT '{}' CHECK (worker_bits <@ ARRAY[32,64]::smallint[]),
  platforms               JSONB NOT NULL DEFAULT '[]',   -- [{version:"8.3.25.1374", bits:64, progid:"V83.COMConnector", registered:true}]
  public_jwk              JSONB NOT NULL,                -- {"kty":"OKP","crv":"Ed25519","x":"...","kid":"<thumbprint>"}
  public_key_thumbprint   TEXT NOT NULL,                 -- RFC 7638 JWK thumbprint (base64url)
  status                  TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
  update_channel          TEXT NOT NULL DEFAULT 'stable' CHECK (update_channel IN ('stable','pilot')),
  capabilities            JSONB NOT NULL DEFAULT '{}',   -- 34 §14.2 sxemasi; A-01 hello'dan yangilanadi
                                                         -- (vazifa faqat capabilities.<oila>.enabled = true bo'lsa navbatga qo'yiladi)
  paired_by               UUID NOT NULL REFERENCES app.users(id),
  paired_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  paired_ip               INET NULL,
  last_hello_at           TIMESTAMPTZ NULL,
  last_poll_at            TIMESTAMPTZ NULL,
  last_ip                 INET NULL,
  machine_hash_changed_at TIMESTAMPTZ NULL,              -- hello'da boshqa machine_hash kelsa (ogohlantirish)
  offline_notified_at     TIMESTAMPTZ NULL,
  revoked_at              TIMESTAMPTZ NULL,
  revoked_by              UUID NULL REFERENCES app.users(id),
  revoke_reason           TEXT NULL CHECK (revoke_reason IN ('user','uninstall','key_compromised','replaced')),
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  version                 INT NOT NULL DEFAULT 1,
  UNIQUE (client_id),
  UNIQUE (device_id),
  CHECK (client_id = 'onec-agent:' || id::text),
  CHECK (status <> 'revoked' OR (revoked_at IS NOT NULL AND revoke_reason IS NOT NULL))
);

CREATE INDEX idx_onec_agents_tenant_status ON app.onec_agents (tenant_id, status);

-- kassa ↔ agent bog'lanishi (lokal fiskal ko'prik, qaror #66); cash_registers.fiscal_agent_id 0002 da FK'siz
ALTER TABLE app.cash_registers ADD CONSTRAINT fk_cr_fiscal_agent FOREIGN KEY (fiscal_agent_id) REFERENCES app.onec_agents(id);

-- karta terminali ↔ agent (adapter='agent_ecr', qaror #71); card_terminals.agent_id 0010 da FK'siz
ALTER TABLE app.card_terminals ADD CONSTRAINT fk_ct_agent FOREIGN KEY (agent_id) REFERENCES app.onec_agents(id);

CREATE TABLE app.onec_agent_tasks (
  id                     UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id              UUID NOT NULL REFERENCES app.tenants(id),
  agent_id               UUID NOT NULL REFERENCES app.onec_agents(id),
  base_id                UUID NULL,   -- NULL: agent darajasidagi vazifa; FK fk_oat_base (0029)
  batch_id               UUID NULL,   -- FK fk_oat_batch (0029)
  item_id                UUID NULL,   -- FK fk_oat_item (0029)
  ref_create_request_id  UUID NULL,   -- FK fk_oat_ref_create (0029)
  reconciliation_id      UUID NULL,   -- FK fk_oat_reconciliation (0029)
  kind                   TEXT NOT NULL CHECK (kind IN ('probe','discover_bases','read_metadata','read_refs',
                           'read_date_prohibition','read_totals','read_stock_balances','preview_object','write_object',
                           'post_object','unpost_object','mark_delete_object','collect_diagnostics',
                           'fiscal.status','fiscal.resend_unsent','fiscal.zreport','print.raw','scale.plu_upload',
                           'card.status','card.settlement')), -- card.* — karta terminali (qaror #71)
  purpose                TEXT NOT NULL CHECK (purpose IN ('onboarding','mapping','export','reconcile','correction',
                           'ref_create','diagnostics','user_test','device_service')),
  is_write               BOOLEAN GENERATED ALWAYS AS
                           (kind IN ('write_object','post_object','unpost_object','mark_delete_object')) STORED,
  priority               SMALLINT NOT NULL DEFAULT 100,  -- kichik = birinchi: user_test/onboarding 10, mapping 30, ref_create 50, export 100, reconcile 150
  payload                JSONB NOT NULL,                 -- §9.5 vazifa turi bo'yicha
  payload_sha256         TEXT NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),  -- SHA-256(JCS(payload))
  status                 TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','leased','done','failed','expired','cancelled')),
  attempt                INT NOT NULL DEFAULT 1 CHECK (attempt >= 1),
  timeout_s              INT NOT NULL CHECK (timeout_s BETWEEN 10 AND 1800),
  not_before             TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at             TIMESTAMPTZ NULL,               -- shu vaqtgacha lease qilinmasa → expired (o'qish vazifalari)
  lease_id               UUID NULL,
  leased_at              TIMESTAMPTZ NULL,
  lease_until            TIMESTAMPTZ NULL,
  heartbeat_at           TIMESTAMPTZ NULL,
  progress               JSONB NULL,                     -- {"stage":"posting","pct":40}
  signing_kid            UUID NULL,                      -- platform.signing_keys.kid (purpose='onec_task')
  signature              TEXT NULL,                      -- compact JWS (§9.4)
  outcome                TEXT NULL CHECK (outcome IN ('done','failed','unknown')),
  error_code             TEXT NULL,
  finished_at            TIMESTAMPTZ NULL,
  created_by             UUID NULL REFERENCES app.users(id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status <> 'leased' OR (lease_id IS NOT NULL AND lease_until IS NOT NULL AND signature IS NOT NULL)),
  CHECK (status NOT IN ('done','failed') OR outcome IS NOT NULL),
  CHECK (base_id IS NOT NULL OR kind IN ('probe','discover_bases','collect_diagnostics',
         'fiscal.status','fiscal.resend_unsent','fiscal.zreport','print.raw','scale.plu_upload',
         'card.status','card.settlement')),
  CHECK ((kind LIKE '%.%') = (purpose = 'device_service')),
  CHECK (kind NOT LIKE '%.%' OR base_id IS NULL),
  CHECK (NOT is_write OR base_id IS NOT NULL)
);

CREATE INDEX idx_onec_tasks_dispatch ON app.onec_agent_tasks (agent_id, priority, not_before) WHERE status = 'queued';

CREATE INDEX idx_onec_tasks_lease ON app.onec_agent_tasks (lease_until) WHERE status = 'leased';

-- bitta bazada bir vaqtda bitta lease (bitta COM sessiya, fayl bazada 1C qulflari)
CREATE UNIQUE INDEX uq_onec_tasks_one_leased_per_base ON app.onec_agent_tasks (base_id)
  WHERE status = 'leased' AND base_id IS NOT NULL;

-- agent darajasidagi vazifadan bir vaqtda bittasi
CREATE UNIQUE INDEX uq_onec_tasks_one_leased_agent_level ON app.onec_agent_tasks (agent_id)
  WHERE status = 'leased' AND base_id IS NULL;

CREATE INDEX idx_onec_tasks_item ON app.onec_agent_tasks (item_id) WHERE item_id IS NOT NULL;

CREATE TABLE app.onec_task_results (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  task_id        UUID NOT NULL REFERENCES app.onec_agent_tasks(id),
  lease_id       UUID NOT NULL,
  attempt        INT NOT NULL,
  outcome        TEXT NOT NULL CHECK (outcome IN ('done','failed','unknown')),
  data           JSONB NOT NULL DEFAULT '{}',   -- read_refs/read_metadata katta qismi o'z jadvaliga ko'chiriladi, bu yerda qisqartiriladi
  data_trimmed   BOOLEAN NOT NULL DEFAULT false,
  error          JSONB NULL,                    -- §9.10
  duration_ms    INT NULL CHECK (duration_ms >= 0),
  agent_version  TEXT NULL,
  worker_bits    SMALLINT NULL CHECK (worker_bits IN (32,64)),
  late           BOOLEAN NOT NULL DEFAULT false, -- lease muddati o'tgandan keyin keldi
  received_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (task_id, lease_id)
);

CREATE TABLE auth.onec_device_authorizations (
  id                     UUID PRIMARY KEY DEFAULT app.uuidv7(),
  device_code_hash       TEXT NOT NULL UNIQUE,      -- SHA-256(device_code); kodning o'zi saqlanmaydi
  user_code              TEXT NOT NULL CHECK (user_code ~ '^[BCDFGHJKLMNPQRSTVWXZ]{8}$'),  -- chiziqchasiz, katta harf
  client_id              TEXT NOT NULL DEFAULT 'onec-agent',
  scope                  TEXT NOT NULL DEFAULT 'onec.agent',
  public_jwk             JSONB NOT NULL,
  public_key_thumbprint  TEXT NOT NULL,
  machine_hash           TEXT NOT NULL,
  pc_name                TEXT NOT NULL,
  os_version             TEXT NULL,
  agent_version          TEXT NULL,
  request_ip             INET NULL,
  status                 TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','denied','consumed','expired')),
  tenant_id              UUID NULL REFERENCES app.tenants(id),
  approved_by            UUID NULL REFERENCES app.users(id),
  approved_at            TIMESTAMPTZ NULL,
  agent_id               UUID NULL,                 -- tasdiqlanganda yaratilgan app.onec_agents.id
  poll_interval_s        INT NOT NULL DEFAULT 5,
  last_poll_at           TIMESTAMPTZ NULL,
  expires_at             TIMESTAMPTZ NOT NULL,      -- created_at + 10 daqiqa
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status NOT IN ('approved','consumed') OR (tenant_id IS NOT NULL AND agent_id IS NOT NULL AND approved_by IS NOT NULL))
);

CREATE UNIQUE INDEX uq_onec_device_auth_user_code_pending ON auth.onec_device_authorizations (user_code) WHERE status = 'pending';

-- 0028 store_agent
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['onec_agents','onec_agent_tasks'] LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON app.%I FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t);
  END LOOP;
END $$;

-- 0028 store_agent
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['onec_agents','onec_agent_tasks','onec_task_results'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE app.%I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY tenant_isolation ON app.%I USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id())', t);
  END LOOP;
END $$;

-- 0028 store_agent
GRANT SELECT, INSERT, UPDATE, DELETE ON app.onec_agents, app.onec_agent_tasks, app.onec_task_results TO erp_app;

GRANT ALL ON auth.onec_device_authorizations TO erp_system;

-- 0028 store_agent
-- AS POST /oauth/device_authorization: yangi pending yozuv (10 daqiqa).
-- user_code to'qnashsa (uq_onec_device_auth_user_code_pending) — ilova yangi kod bilan qayta chaqiradi.
CREATE OR REPLACE FUNCTION app.onec_device_auth_start(
  p_device_code_hash text, p_user_code text, p_public_jwk jsonb, p_thumbprint text,
  p_machine_hash text, p_pc_name text, p_os text, p_agent_version text, p_ip inet
) RETURNS uuid
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  INSERT INTO auth.onec_device_authorizations
    (device_code_hash, user_code, public_jwk, public_key_thumbprint, machine_hash, pc_name,
     os_version, agent_version, request_ip, expires_at)
  VALUES
    (p_device_code_hash, p_user_code, p_public_jwk, p_thumbprint, p_machine_hash, p_pc_name,
     p_os, p_agent_version, p_ip, now() + interval '10 minutes')
  RETURNING id;
$$;

-- W-03: foydalanuvchi kiritgan kod bo'yicha so'rov kartasi. Faqat pending va muddati o'tmagan; aks holda bo'sh.
-- public_jwk/public_key_thumbprint/machine_hash — W-04 shu qiymatlar bilan onec_agents qatorini yaratadi.
CREATE OR REPLACE FUNCTION app.onec_device_auth_lookup(p_user_code text)
RETURNS TABLE (
  id uuid, pc_name text, os_version text, agent_version text, request_ip inet,
  created_at timestamptz, expires_at timestamptz,
  public_jwk jsonb, public_key_thumbprint text, machine_hash text
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT d.id, d.pc_name, d.os_version, d.agent_version, d.request_ip, d.created_at, d.expires_at,
         d.public_jwk, d.public_key_thumbprint, d.machine_hash
  FROM auth.onec_device_authorizations d
  WHERE d.user_code = p_user_code AND d.status = 'pending' AND d.expires_at > now();
$$;

-- W-04: onec_agents/devices shu tranzaksiyada RLS ostida yaratilgandan keyin chaqiriladi.
-- pending → approved. Agent joriy tenant'da bo'lishi va kaliti so'rovdagi kalit bilan bir xil bo'lishi shart.
-- Natija: 'approved' | 'not_found' (kod yo'q yoki agent/kalit mos emas → 404 ONEC_PAIRING_CODE_INVALID) |
-- 'expired' (→ 409 ONEC_PAIRING_CODE_EXPIRED) | 'used' (allaqachon tasdiqlangan/rad etilgan/iste'mol qilingan → 404 ONEC_PAIRING_CODE_INVALID).
CREATE OR REPLACE FUNCTION app.onec_device_auth_approve(
  p_user_code text, p_tenant_id uuid, p_user_id uuid, p_agent_id uuid
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  r auth.onec_device_authorizations%ROWTYPE;
BEGIN
  IF p_tenant_id IS DISTINCT FROM app.current_tenant_id()
     OR p_user_id IS DISTINCT FROM app.current_user_id() THEN
    RAISE EXCEPTION 'onec_device_auth_approve: tenant/foydalanuvchi konteksti mos emas'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  -- user_code faqat pending orasida noyob — pending birinchi, aks holda eng oxirgisi
  SELECT * INTO r FROM auth.onec_device_authorizations d
   WHERE d.user_code = p_user_code
   ORDER BY (d.status = 'pending') DESC, d.created_at DESC
   LIMIT 1
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'not_found';
  END IF;
  IF r.status = 'expired' OR (r.status = 'pending' AND r.expires_at <= now()) THEN
    UPDATE auth.onec_device_authorizations d SET status = 'expired' WHERE d.id = r.id AND d.status = 'pending';
    RETURN 'expired';
  END IF;
  IF r.status <> 'pending' THEN
    RETURN 'used';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM app.onec_agents a
                 WHERE a.id = p_agent_id AND a.tenant_id = p_tenant_id
                   AND a.public_key_thumbprint = r.public_key_thumbprint) THEN
    RETURN 'not_found';
  END IF;

  UPDATE auth.onec_device_authorizations d
     SET status = 'approved', tenant_id = p_tenant_id, approved_by = p_user_id,
         approved_at = now(), agent_id = p_agent_id
   WHERE d.id = r.id;
  RETURN 'approved';
END;
$$;

-- W-04 "Rad etish": pending → denied; agent poll'i 'denied' oladi (AS: access_denied).
-- Natija: 'denied' | 'not_found' | 'expired' | 'used' (approve bilan bir xil xaritalash).
CREATE OR REPLACE FUNCTION app.onec_device_auth_deny(p_user_code text, p_user_id uuid)
RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  r auth.onec_device_authorizations%ROWTYPE;
BEGIN
  IF app.current_tenant_id() IS NULL OR p_user_id IS DISTINCT FROM app.current_user_id() THEN
    RAISE EXCEPTION 'onec_device_auth_deny: tenant/foydalanuvchi konteksti mos emas'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  SELECT * INTO r FROM auth.onec_device_authorizations d
   WHERE d.user_code = p_user_code
   ORDER BY (d.status = 'pending') DESC, d.created_at DESC
   LIMIT 1
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'not_found';
  END IF;
  IF r.status = 'expired' OR (r.status = 'pending' AND r.expires_at <= now()) THEN
    UPDATE auth.onec_device_authorizations d SET status = 'expired' WHERE d.id = r.id AND d.status = 'pending';
    RETURN 'expired';
  END IF;
  IF r.status <> 'pending' THEN
    RETURN 'used';
  END IF;

  UPDATE auth.onec_device_authorizations d
     SET status = 'denied', tenant_id = app.current_tenant_id()
   WHERE d.id = r.id;
  RETURN 'denied';
END;
$$;

-- AS /oauth/token (grant_type=urn:ietf:params:oauth:grant-type:device_code).
-- Bo'sh natija → invalid_grant. slow_down=true → poll_interval_s dan tez so'raldi (holat o'zgarmaydi).
-- approved → consumed bir martalik: shu chaqiruv status='approved' qaytaradi (token beriladi),
-- keyingilari 'consumed' (invalid_grant). Muddati o'tgan pending/approved → 'expired'.
CREATE OR REPLACE FUNCTION app.onec_device_auth_poll(p_device_code_hash text)
RETURNS TABLE (status text, tenant_id uuid, agent_id uuid, slow_down boolean)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
#variable_conflict use_column
DECLARE
  r      auth.onec_device_authorizations%ROWTYPE;
  v_slow boolean;
  v_new  text;
BEGIN
  SELECT * INTO r FROM auth.onec_device_authorizations d
   WHERE d.device_code_hash = p_device_code_hash
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN;
  END IF;

  v_slow := r.last_poll_at IS NOT NULL
            AND now() - r.last_poll_at < make_interval(secs => r.poll_interval_s);

  IF r.status IN ('pending','approved') AND r.expires_at <= now() THEN
    r.status := 'expired';
  END IF;
  v_new := CASE WHEN r.status = 'approved' AND NOT v_slow THEN 'consumed' ELSE r.status END;

  UPDATE auth.onec_device_authorizations d
     SET last_poll_at = now(), status = v_new
   WHERE d.id = r.id;

  RETURN QUERY SELECT r.status, r.tenant_id, r.agent_id, v_slow;
END;
$$;

-- AS /oauth/token (client_credentials + private_key_jwt): client_id = 'onec-agent:{agent_id}' bo'yicha
-- tenant kontekstisiz agent kalitini topish. status='revoked' bo'lsa AS rad etadi.
CREATE OR REPLACE FUNCTION app.onec_agent_credentials(p_client_id text)
RETURNS TABLE (tenant_id uuid, agent_id uuid, device_id uuid, public_jwk jsonb, status text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
  SELECT a.tenant_id, a.id, a.device_id, a.public_jwk, a.status
  FROM app.onec_agents a
  WHERE a.client_id = p_client_id;
$$;

-- 0028: funksiyalar ichida o'qiladigan app jadvali (erp_system — BYPASSRLS, lekin jadval grant'i baribir kerak)
GRANT SELECT ON app.onec_agents TO erp_system;

-- egalikni topshirish uchun vaqtincha (0027 juftligi bilan bir xil; blok oxirida REVOKE)
GRANT CREATE ON SCHEMA app TO erp_system;

ALTER FUNCTION app.onec_device_auth_start(text, text, jsonb, text, text, text, text, text, inet) OWNER TO erp_system;

ALTER FUNCTION app.onec_device_auth_lookup(text) OWNER TO erp_system;

ALTER FUNCTION app.onec_device_auth_approve(text, uuid, uuid, uuid) OWNER TO erp_system;

ALTER FUNCTION app.onec_device_auth_deny(text, uuid) OWNER TO erp_system;

ALTER FUNCTION app.onec_device_auth_poll(text) OWNER TO erp_system;

ALTER FUNCTION app.onec_agent_credentials(text) OWNER TO erp_system;

REVOKE ALL ON FUNCTION app.onec_device_auth_start(text, text, jsonb, text, text, text, text, text, inet) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.onec_device_auth_lookup(text) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.onec_device_auth_approve(text, uuid, uuid, uuid) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.onec_device_auth_deny(text, uuid) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.onec_device_auth_poll(text) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.onec_agent_credentials(text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.onec_device_auth_start(text, text, jsonb, text, text, text, text, text, inet) TO erp_app;

GRANT EXECUTE ON FUNCTION app.onec_device_auth_lookup(text) TO erp_app;

GRANT EXECUTE ON FUNCTION app.onec_device_auth_approve(text, uuid, uuid, uuid) TO erp_app;

GRANT EXECUTE ON FUNCTION app.onec_device_auth_deny(text, uuid) TO erp_app;

GRANT EXECUTE ON FUNCTION app.onec_device_auth_poll(text) TO erp_app;

GRANT EXECUTE ON FUNCTION app.onec_agent_credentials(text) TO erp_app;

REVOKE CREATE ON SCHEMA app FROM erp_system;
