# 04 — Mustaqil tekshiruv: yagona tuzatish rejasi

**Maqsad:** A (31), B (147), C (183) topilmalarini takrorsiz birlashtirish, har birini spec qatorlari bo'yicha tekshirish (TASDIQ/RAD), har qabul qilingan muammo uchun **bitta** tuzatish tanlash va uni fayl guruhlari bo'yicha aniq amallarga bo'lish. · **Kim uchun:** spec tuzatuvchi agentlar (G-a…G-f), asoschi. · **Bog'liq fayllar:** `A-havolalar-va-sonlar.md`, `B-malumot-shartnomasi.md`, `C-qoidalar-va-amalga-oshirish.md`, `spec/kod-uchun/00–34`, `research_notes/ochiq-savollar/01-qollash-yoriqnomasi.md`. · **Holat:** Opus qabul darvozasi qarori, 2026-10-16; spec fayllari hali o'zgartirilmagan (asos — commit 00dd8aa).

---

## 0. Qo'llash qoidalari (barcha guruhlar uchun majburiy)

1. **Har guruh faqat o'z fayllarini** o'zgartiradi: G-a — 00–09, 26, 27, 29, 30; G-b — 10–13; G-c — 14–20; G-d — 21–25, 28, 32; G-e — 31; G-f — 33, 34. Boshqa guruh fayliga tegadigan o'zgarish o'sha guruhning ro'yxatida alohida yozilgan — o'zingiznikini bajaring, boshqasini kutmang.
2. **Yagona manba qoidasi:** DDL — `12`; xato kodlari — `17` §15; ruxsatlar — `15` §2; provodkalar — `13`; 1C — `33`; qarorlar — `01`. Yangi xato kodi nomi shu rejadagi bilan aynan bir xil yoziladi (G-c uni `17` §15 ga qo'shadi).
3. **Joriy haqiqat:** "endi", "olib tashlandi", "avval … edi", "qo'shildi" kabi tarix izlari yozilmaydi (01 #59c, yo'riqnoma C). Qarorga havola — "(qaror #N)".
4. **Qator raqamlari** — commit 00dd8aa bo'yicha. Boshqa amal matnni surgan bo'lsa, qatorni keltirilgan matn yoki bo'lim bo'yicha toping.
5. **Yangi dizayn elementlari** (§3, `D-xx`) — to'liq ta'rif shu faylda. Amal "D-xx bo'yicha" desa, applier §3 dagi ustun/holat/qoidalarni aynan ko'chiradi; boshqa manbani o'qish shart emas.
6. **Asoschi standartlari** (§2, `F-xx`) — qo'llanadi. Spec matnida "asoschi ko'rib chiqadi" belgisi faqat `01` dagi tegishli qaror qatorining "Asos/manba" ustunida bo'ladi.
7. **Yangi qaror raqamlari:** #66–#70 (G-a `01` ga yozadi). Yangi `26` bandlari #171 dan.
8. **Sanoqlar** (`31` §0/§0.7, `00`, `30`, `20` indeksi) — qator qo'shilgandan keyin haqiqiy sanab yoziladi, shu rejadagi taxminiy songa tayanilmaydi.
9. Til — o'zbek lotin; kod nomlari (jadval, ustun, enum, endpoint) — o'zgarishsiz, backtick ichida.

---

## 1. Yig'ma

### 1.1 Manba topilmalari va noyob muammolar

| Manba | kritik | o'rta | kichik | Jami |
|---|---|---|---|---|
| A — havolalar va sonlar | 0 | 8 | 23 | 31 |
| B — ma'lumot shartnomasi | 23 | 88 | 36 | 147 |
| C — qoidalar va amalga oshirish | 33 | 90 | 60 | 183 |
| **Jami manba ID** | **56** | **186** | **119** | **361** |

Takrorlar birlashtirilgach — **289 ta noyob muammo** (T-001…T-289). Noyob muammo darajasi — manbalaridagi eng yuqori daraja.

| Daraja | Noyob | TASDIQ (to'liq yoki qisman) | RAD |
|---|---|---|---|
| kritik | 43 | 43 | 0 |
| o'rta | 135 | 135 | 0 |
| kichik | 111 | 109 | 2 |
| **Jami** | **289** | **287** | **2** |

### 1.2 Tekshirish usuli

- **kritik** — 56 manba ID'ning hammasi darvoza tomonidan spec qatorlarini ochib tekshirildi (12 DDL, 13, 18, 19, 20, 07, 08, 03, 27, 31, 33 qatorlari).
- **o'rta** — 186 manba ID'ning hammasi qatorlari ochilib tekshirildi (darvoza + uchta parallel tekshiruv shoxi, natijalar darvozada qayta ko'rildi). Qisman tasdiq: B-016, B-072, B-106, B-141, C-034, C-049, C-058 — tuzatish shunga moslab tanlandi.
- **kichik** — 52 tasi (≈44%) qatorlari ochib tekshirildi; qolganlari matn bo'yicha qabul qilindi. RAD: **A-016** (12:2486 kirish izohi `§` havolalari 33 ga tegishli ekanini allaqachon aytadi), **B-123** (T-132 / C-058 qarori: bekor qilish yopilgan davrda ham ruxsat, storno joriy davrda — `PERIOD_CLOSED` qo'shilmaydi, aksincha olib tashlanadi).

---

## 2. Asoschi standartlari — ASOSCHI KO'RIB CHIQADI

Quyidagi bandlar bo'yicha spec ichida qaror yo'q yoki qarorlar o'zaro zid. Darvoza mavjud qarorlarga eng mos standartni tanladi va u **qo'llanadi**; asoschi keyin tasdiqlaydi yoki o'zgartiradi (o'zgartirsa — bitta qaror qatori va shu yerda ko'rsatilgan fayllar qayta tahrirlanadi).

| ID | Savol (manba) | Qo'llanadigan standart | Asos | Qayerda yoziladi |
|---|---|---|---|---|
| F-01 | Qaytarish faqat online mi? #23(5) "qaytarish faqat online" ↔ 03/18/06/07 offline qaytarishni qo'llaydi (C-059) | **Markirovkasiz tovarni qaytarish offline ruxsat** (lokal Menejer/Egasi PIN limit qoidasi bilan); **markirovkali qaytarish — faqat online**. #23(5) matni shunga | #17, #62 ("qaytarish online-only qoidasi" markirovka kontekstida), 16 §5 PIN qoidasi, FM offline qaytarish chekini imzolay oladi | 01 #23 (5); 08:506 |
| F-02 | Uzum MVP'dami? (C-119) | **Ha — Bosqich 3 da Click/Payme bilan birga ixtiyoriy provayder** | #10, #46, #64 Uzum'ni Click/Payme bilan bir qatorda beradi; 03/13/18 MVP'da | 27:111, 27:252 |
| F-03 | Server yorliq PDF qaysi bosqichda? #54 "Bosqich 2 oxiri" ↔ 27 M09 yorliq chop etish B6 (C-118) | **Bosqich 6** — M09 yorliq chop etish bilan birga (>200 yorliq yoki iOS) | Yorliq chop etishning o'zi B6 da; alohida PDF B2 da foydalanuvchisiz qoladi | 01 #54; 27 B6 |
| F-04 | Yillik −20% qo'shimcha kassaga ham tegadimi? (C-076) | **Yo'q — chegirma faqat asosiy tarifga**: oy = `99000 + 39000×extra`; yil = `950400 + 39000×12×extra` | #22: 950 400 = 99 000×12×0,8; qo'shimcha kassa marjasi hamkor narxidan past (26 #168) | 01 #70 (yangi); 20 #61; 07 BO-19 |
| F-05 | Obuna `restricted → closed` triggeri, `trial` tugashi (C-076) | `trial` → `grace` (24 soat) → `restricted`; **avtomatik `closed` yo'q**; `closed` faqat platforma admini (`platform_admins`) amali bilan, US-M17-05 (MVP'dan keyin) yo'li orqali; ma'lumot ≥5 yil saqlanadi | #15, #7, #33 (US-M17-05 MVP'dan keyin) | 01 #70; 11 §8; 14 §16 |
| F-06 | `card_type` standart qiymati (C-038, B-146m) | **Standart qiymat yo'q** — kassir har karta to'lovida terminal chekiga qarab tanlaydi; `unknown` qiymati qoladi, chekda yorlig'i "Noma'lum / Не определён" | #64 "standart so'raladi" ma'nosi; noto'g'ri oldindan to'ldirilgan qonuniy rekvizit xavfi | 01 #64; 18:267; 21:580; 06:114; 08:556 |
| F-07 | Bank o'tkazmasi bilan qarz to'lovida fiskal chek kerakmi? (C-003) | **Kerak emas** — `debt_payments.method='bank'` — kassasiz, chek yo'q; boshqa barcha usullar faqat POS kassasi orqali, chek bilan (D-03) | VMQ-943 1-ilova 30-band kassa orqali hisob-kitobga tegishli; bank o'tkazmasi kassa operatsiyasi emas. Huquqiy tasdiq — 26 #171 | 01 #67; 26 #171 (yangi, Tashqi javob kerak) |
| F-08 | Offline qarz to'lovida qarzdan ortiq summa (C-005) | **Qabul qilinadi** (FM chekni allaqachon imzolagan): ortig'i `Kt 6310` (olingan bo'nak), `sync_exceptions(kind='debt_overpayment_offline')`, Egasiga M18; hal qilish — qaytarish (kassa chiqimi) yoki keyingi qarzga hisoblash (D-04) | #45 dagi "ortiqcha rad" qoidasi faqat online/REST uchun saqlanadi | 01 #67; 18 §12.2; 13 §2.14 |
| F-09 | Yopilgan davrdagi offline chek kech sinxronlansa (C-017) | **Qabul qilinadi**, registr yozuvlari birinchi ochiq davrda (`correction_of_period` = asl oy); davr yopish tayyorligida sinxronlanmagan qurilmalar — bloker (D-06) | #23 (#15 tavsiya — yopilgan oy qayta ochilmaydi), 13 §5.1 "tuzatish joriy ochiq davrda" | 01 #69 |
| F-10 | Authenticode OV sertifikati qachon? #38 "Bosqich 7 dan oldin" ↔ 26 #105 / 21 §16 lokal ko'prikda B5 (C-117) | **Lokal fiskal ko'prik tanlansa — B5/B6 pilot tarqatishidan oldin; aks holda Bosqich 7 dan oldin** | #60 (agent asosi B5) | 01 #38; 27:190 |
| F-11 | YaTT'ga e-faktura (bank orqali to'lovchi YaTT) — modelda belgi yo'q (C-108) | **Yangi ustun yo'q**: e-faktura qoidasi `counterparties.kind='company'`; STIR'li YaTT mijoz `company` sifatida kiritiladi (BO-06 izohi) | Model soddaligi; 26 #114 javobi kelganda qayta ko'riladi | 04:99/118; 07:1146 |

---

## 3. Yangi dizayn elementlari

Har element — amal qiluvchi fayllar ro'yxati bilan. Ustun/holat nomlari shu yerdagidek aynan ko'chiriladi.

### D-01. Do'kon agenti infratuzilmasi — Bosqich 5 (T-022; qaror #66)

**Muammo:** agentni ulash, token, A-API, vazifa navbati va imzo faqat Bosqich 7 (`0028 onec_integration`) da; `onec_agent_tasks` CHECK'lari fiskal/printer vazifalarini rad etadi; agent qaysi kassaga xizmat qilishi bog'lanmagan.

**Qoida:**
1. Jadval nomlari o'zgarmaydi: `app.onec_agents`, `app.onec_agent_tasks`, `app.onec_task_results`, `auth.onec_device_authorizations` — bu **Do'kon agentining umumiy registri** (nom 33 bilan moslik uchun `onec_` prefiksli). 1C ga xos jadvallar (`onec_bases` va qolgan 14 ta) — Bosqich 7.
2. **Migratsiya bo'linadi** (12 §6.1):
   - `0028 store_agent` (Bosqich 5): `onec_agents` (+ yangi ustun `capabilities JSONB NOT NULL DEFAULT '{}'`), `onec_agent_tasks` (`base_id`, `batch_id`, `item_id`, `ref_create_request_id`, `reconciliation_id` ustunlari **FK'siz** yaratiladi), `onec_task_results`, `auth.onec_device_authorizations`; `ALTER TABLE app.cash_registers ADD CONSTRAINT fk_cr_fiscal_agent FOREIGN KEY (fiscal_agent_id) REFERENCES app.onec_agents(id)`; funksiyalar `onec_device_auth_start/lookup/approve/poll/deny`, `onec_agent_credentials`; shu jadvallarning RLS uchligi, grantlari, `updated_at` trigger'lari.
   - `0029 onec_integration` (Bosqich 7): qolgan 1C jadvallari, `onec_forbid_namespace_change`, `onec_tenants_due`, va `onec_agent_tasks` ga kechiktirilgan FK'lar: `fk_oat_base` (`base_id` → `onec_bases`), `fk_oat_batch`, `fk_oat_item`, `fk_oat_ref_create`, `fk_oat_reconciliation`.
3. **`onec_agent_tasks` CHECK'lari:**
   ```sql
   kind TEXT NOT NULL CHECK (kind IN ('probe','discover_bases','read_metadata','read_refs','read_date_prohibition',
        'read_totals','read_stock_balances','preview_object','write_object','post_object','unpost_object',
        'mark_delete_object','collect_diagnostics',
        'fiscal.status','fiscal.resend_unsent','fiscal.zreport','print.raw','scale.plu_upload')),
   purpose TEXT NOT NULL CHECK (purpose IN ('onboarding','mapping','export','reconcile','correction','ref_create',
        'diagnostics','user_test','device_service')),
   CHECK (base_id IS NOT NULL OR kind IN ('probe','discover_bases','collect_diagnostics',
        'fiscal.status','fiscal.resend_unsent','fiscal.zreport','print.raw','scale.plu_upload')),
   CHECK ((kind LIKE '%.%') = (purpose = 'device_service')),
   CHECK (kind NOT LIKE '%.%' OR base_id IS NULL)
   ```
   `is_write` generated ustuni o'zgarmaydi (xizmat vazifalari yozuvchi emas).
4. **Kassa ↔ agent bog'lanishi** (C-069): `cash_registers.fiscal_agent_id UUID NULL` (lokal ko'prik kassasiga xizmat qiluvchi agent), `cash_registers.fiscal_local_device_id TEXT NULL` (agent `capabilities.fiscal.devices[].local_id`), `CHECK (fiscal_agent_id IS NULL OR fiscal_local_device_id IS NOT NULL)`. `devices` dagi "1C agenti kassaga bog'lanmaydi" CHECK'i qoladi — bog'lanish kassa tomonida. BO-12 kassa qatorida "Fiskal agent" `Select` (`settings.branches`, `PATCH /cash-registers/{id}` tanasiga `fiscal_agent_id`, `fiscal_local_device_id`).
5. **Vazifa payload'lari:** `fiscal.status` / `fiscal.resend_unsent` — `{cash_register_id}`; `fiscal.zreport` — `{cash_register_id, shift_id}`; `print.raw` — `{printer_local_id, data_base64, encoding: "cp866"|"raster"}`; `scale.plu_upload` — `{scale_local_id, items:[{plu, name, price, barcode_prefix}]}` (MVP'dan keyin).
6. **`fiscal.status` natijasi:** `{cash_register_id, fm_state, pending_count, oldest_unacked_at, acked:[{fm_terminal_id, fm_receipt_seq, acked_at}]}` → `cash_registers.fm_state`, `fm_receipts_pending`, `last_unacked_receipt_at` va D-05 bo'yicha `fiscal_receipts.ofd_acked_at`.
7. **A-01 `hello`** so'roviga `capabilities` (34 §14.2 sxemasi) qo'shiladi, protokol `X-Agent-Protocol: 2`; server `onec_agents.capabilities` ga yozadi; vazifa navbatga faqat `capabilities.<oila>.enabled = true` bo'lsa qo'yiladi (aks holda `AgentTaskPort.enqueue` → `409 AGENT_CAPABILITY_DISABLED`; 17 §15 ga yangi kod, `ONEC_*` sanog'iga kirmaydi).
8. **Ekran:** BO-14 da "Do'kon agenti" bloki — agentlar ro'yxati (W-01), "Kompyuterni ulash" (W-03 → W-04), "Uzish" (W-05), diagnostika (W-07), loglar (W-08); ruxsatlar 33 dagidek (`onec.view`, `onec.settings.manage` — Egasida bor, #28). BO-22 (1C) shu agentdan foydalanadi.
9. **Bosqichlar** (27): Bosqich 5 — OAuth `onec-agent` mijozi, `/oauth/device_authorization`, device grant, `client_credentials` + `private_key_jwt`, `aud=urn:erp:onec-agent`; A-01, A-03…A-10 (A-02 dan tashqari hammasi), long-poll + Redis wake, lease/heartbeat/sweeper, Ed25519 vazifa imzosi va kalitlar to'plami, imzoli avto-yangilanish, W-01…W-05, W-07, W-08; `0028 store_agent`; xom TCP 9100 printer. Kirish sharti: "`agent_update` ildiz kaliti oflayn yaratilgan". Bosqich 7 — A-02, W-06, W-09…W-55, `0029 onec_integration`, 1C vazifa turlari. Tarozi (`scale.plu_upload`) — MVP'dan keyin (MVP'da PLU CSV eksport); jonli og'irlik — Web Serial, MVP'dan keyin.

**Fayllar:** 01 (#66), 10, 12, 21 §16, 23 §4.2, 27, 33 §5.15/§9.2/§9.5/A-01, 34 §14, 07 BO-12/BO-14, 20 #40, 17 §15.

### D-02. Auth SECURITY DEFINER funksiyalari to'plami (T-021)

**Muammo:** `erp_app` ning `auth.*` ga GRANT'i yo'q, lekin login oqimining yozuvchi amallari uchun funksiya yo'q.

**Qoida:** 12 §4.5 ga quyidagi funksiyalar qo'shiladi — naqsh mavjudlari bilan bir xil (`LANGUAGE plpgsql|sql SECURITY DEFINER`, `SET search_path = app, auth, pg_temp`, egasi `erp_system`, `REVOKE ALL … FROM PUBLIC`, `GRANT EXECUTE … TO erp_app`). Revizion `0027` dagi son va 6.2 CI ro'yxati yangilanadi.

| Funksiya | Imzo | Mazmuni |
|---|---|---|
| `auth_issue_code` | `(p_code_hash text, p_client_id uuid, p_user_id uuid, p_tenant_id uuid, p_code_challenge text, p_redirect_uri text, p_scope text, p_ttl_s int) RETURNS void` | `auth.authorization_codes` INSERT, `expires_at = now() + p_ttl_s` (standart 60) |
| `auth_issue_tokens` | `(p_user_id uuid, p_tenant_id uuid, p_client_id uuid, p_device_id uuid, p_refresh_token_hash text, p_refresh_expires_at timestamptz, p_scope text, p_with_session boolean, p_idle_expires_at timestamptz, p_absolute_expires_at timestamptz, p_ip inet, p_user_agent text) RETURNS TABLE (session_id uuid, refresh_token_id uuid, family_id uuid)` | Bitta tranzaksiyada yangi `family_id = app.uuidv7()` bilan birinchi `refresh_tokens` qatori; `p_with_session=true` (BFF mijozlari) bo'lsa `sessions` qatori (`current_refresh_token_id` = shu token); Android (public client) — `false`, `session_id = NULL` |
| `auth_session_by_id` | `(p_session_id uuid) RETURNS TABLE (session_id uuid, user_id uuid, tenant_id uuid, client_id uuid, device_id uuid, current_refresh_token_id uuid, idle_expires_at timestamptz, absolute_expires_at timestamptz, revoked_at timestamptz)` | BFF `__Host-sid` bo'yicha sessiyani o'qiydi (Redis keshi bo'sh bo'lganda) |
| `auth_touch_session` | `(p_session_id uuid, p_idle_expires_at timestamptz) RETURNS void` | `last_seen_at = now()`, sliding `idle_expires_at` |
| `auth_otp_create` | `(p_phone text, p_purpose text, p_channel text, p_code_hash text, p_ttl_s int) RETURNS uuid` | `otp_challenges` INSERT (TTL standart 300, #54); shu `(phone, purpose)` dagi oldingi tasdiqlanmagan challenge'lar `expires_at = now()` |
| `auth_otp_verify` | `(p_challenge_id uuid, p_code_hash text) RETURNS text` | `'ok'` (`verified_at = now()`), `'invalid'` (`attempts += 1`), `'expired'`, `'locked'` (`attempts >= max_attempts`), `'used'` (`verified_at` bor) |
| `auth_record_login` | `(p_phone text, p_ip inet, p_success boolean, p_failure_reason text) RETURNS TABLE (failed_login_count int, locked_until timestamptz)` | `login_attempts` INSERT; foydalanuvchi topilsa `user_credentials`: muvaffaqiyatda `failed_login_count = 0, locked_until = NULL`; xatoda `+1`, 5 xato/15 daq oynasida progressiv blok 1→5→15→60 daqiqa (#54) |
| `auth_set_credentials` | `(p_user_id uuid, p_password_hash text, p_pin_hash text) RETURNS void` | UPSERT `user_credentials`; NULL argument — o'sha maydon o'zgarmaydi; berilganda `*_updated_at = now()`, mos `must_change_* = false` |
| `auth_reset_credentials` | `(p_user_id uuid, p_reset_password boolean, p_reset_pin boolean) RETURNS void` | Tanlangan hash `NULL`, `must_change_* = true`; `p_reset_password=true` bo'lsa foydalanuvchining barcha sessiya/refresh oilasi revoke (`revoked_reason='credential_reset'`) |
| `auth_get_pin_hash` | `(p_user_id uuid) RETURNS TABLE (pin_hash text, must_change_pin boolean)` | `/auth/pin/verify` uchun |
| `auth_revoke_session` | `(p_session_id uuid, p_reason text) RETURNS void` | Sessiya + uning `current_refresh_token_id` oilasi revoke |
| `auth_revoke_user` | `(p_user_id uuid, p_tenant_id uuid, p_reason text) RETURNS int` | Foydalanuvchining (`p_tenant_id` berilsa — faqat shu tenantdagi) barcha sessiya/refresh tokenlari revoke; qaytaradi — revoke qilingan sessiyalar soni |
| `auth_list_user_sessions` | `(p_user_id uuid, p_tenant_id uuid) RETURNS TABLE (session_id uuid, client_id uuid, device_id uuid, created_at timestamptz, last_seen_at timestamptz, ip inet, user_agent text)` | `GET /admin/users/{id}/sessions` (faol, revoke qilinmagan) |
| `auth_telegram_chat_by_phone` | `(p_phone text) RETURNS text` | `app.users.phone = p_phone` → `app.telegram_links` (`revoked_at IS NULL`), eng oxirgi `linked_at` dagi `chat_id`; topilmasa NULL (B-039) |

Qo'shimcha: obuna lokauti `auth_suspend_tenant(tenant_id, true)` faqat `refresh_tokens.suspended_at = now(), revoked_reason = 'subscription'` qiladi; `sessions` o'zgarmaydi — kirish Redis `sub_status` orqali to'xtaydi (B-037). 14 §19 dagi funksiya ro'yxati 12 §4.5 dagi imzolarni aynan takrorlaydi ("va h.k." yo'q).

**Fayllar:** 12 §4.5, §6.1 (0027 soni: mavjud 12 + 14 = 26), §6.2; 14 §2/§4/§7/§16/§18/§19; 31 QT-SUB-03.

### D-03. Qarz to'lovi cheki — kassa bog'lanishi (T-023; qaror #67; F-07)

1. `debt_payments.method='bank'` — **kassasiz, fiskal chek yo'q**: `cash_register_id`, `shift_id`, `receipt_seq` NULL; provodka `Dt 5110 / Kt 4010` (13 §2.14). Faqat back-office `POST /debt-payments` (BO-06).
2. `method IN ('cash','card','uzqr','click','payme','uzum')` — **faqat POS** `debt_payment.created` voqeasi (offline ham): `branch_id`, `cash_register_id`, `shift_id` (`status=open`), `receipt_seq` (qurilma beradi, smenada ketma-ket, qaror #12) majburiy; chek shu kassa FM'ida chiqadi va shu kassaning 48 soat hisobiga kiradi (#43).
3. Back-office `POST /debt-payments`: `method` faqat `bank`; boshqa qiymat → `422 VALIDATION_ERROR` (`params.field="method"`, `message_key=validation.debt_payment_backoffice_bank_only`).
4. **12 DDL:** `debt_payments` ga `receipt_seq INT NULL`, `unallocated_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (unallocated_amount >= 0)`; 1483-qatordagi CHECK almashtiriladi: `CHECK ((method = 'bank') = (cash_register_id IS NULL AND shift_id IS NULL AND receipt_seq IS NULL))`. `fiscal_receipts` CHECK'ining `debt_settlement` tarmog'i: `(kind = 'debt_settlement' AND debt_payment_id IS NOT NULL AND sale_id IS NULL AND return_id IS NULL AND receipt_seq IS NOT NULL AND cash_register_id IS NOT NULL AND shift_id IS NOT NULL)`; 1994–1995 va 2009–2011 izohlari: "debt_settlement — har doim kassa/smena/receipt_seq bilan; bank orqali qarz to'lovida chek yo'q".
5. `debt_payments.branch_id` har doim majburiy (DDL `NOT NULL`, API ham).

### D-04. Offline qarz to'lovi: allokatsiya, chek qatorlari, ortiqcha summa (T-024, T-025, T-120; qaror #67; F-08)

1. **Lokal kesh** (16 §1 `customers`): `receivable_balance > 0` bo'lgan har mijozga `open_debt_docs[]`:
   `{doc_type: "sales"|"debt_openings"|"debt_writeoffs", doc_id, doc_date, due_date|null, open_amount, lines: [{sale_line_id, product_id, name, name_ru, mxik_code, unit_code, barcode, qty, price, line_total, vat_rate, vat_exemption_code, settled_amount, marking_code|null}]}` (`lines` faqat `sales` uchun). Delta — `scope=customers`.
2. **Yagona allokatsiya funksiyasi** — TS `shared/lib/debt-allocation` va Python `app/shared/debt_allocation.py`, umumiy test-vektorlar `shared/debt-allocation-vectors.json`:
   - tartib: avval `sales` + `debt_openings` ochiq qoldiqlari `ORDER BY COALESCE(due_date, doc_date), doc_date, doc_id`; keyin `debt_writeoffs` (hisobdan chiqarilgan, eng eskisi birinchi) — bu qism `Kt 9390` (13 §2.14 1a);
   - to'lov chegarasi: `amount ≤ receivable_balance + Σ written_off_open` (online/REST); offline — §5 bo'yicha.
3. **Chek qatorlari** (`debt_settlement`): har allokatsiya qilingan sotuv uchun `ratio = alloc_amount / sales.total_amount`;
   - `amt_i = ROUND_HALF_UP(line_total_i × ratio, 2)`, lekin `amt_i ≤ line_total_i − settled_amount_i`; yaxlitlash qoldig'i eng katta `line_total` qatoriga (teng bo'lsa — eng katta `line_no`);
   - sotuvni **to'liq yopuvchi** to'lovda: `amt_i = line_total_i − settled_amount_i` (kumulyativ aniq);
   - `qty_i = ROUND_HALF_UP(qty_i × ratio, 3)` (kamida `0.001`); yopuvchi chekda — qolgan miqdor;
   - `vat_i = ROUND_HALF_UP(amt_i × r / (100 + r), 2)` (#26);
   - markirovka kodi faqat sotuv qatorini to'liq yopuvchi chekda;
   - `debt_openings`/`debt_writeoffs` qismi — tovar qatorsiz bitta umumiy qator ("Qarz to'lovi (boshlang'ich qoldiq) / Погашение долга (начальный остаток)");
   - `sale_lines.settled_amount NUMERIC(18,2) NOT NULL DEFAULT 0` (12) — server posting'da kumulyativ yangilanadi.
   - Aralash to'lovli sotuvda birinchi (non-debt) chek qatorlari ham shu formula bilan, `ratio = non_debt_amount / total_amount`, va `settled_amount` ga qo'shiladi (C-041).
4. **Payload** (`debt_payment.created`): qo'shimcha `receipt_seq`, `allocations: [{target_doc_type, target_doc_id, amount}]`, `fiscal_lines: [{sale_id|null, sale_line_id|null, product_id|null, qty, amount, vat_rate, vat_amount, marking_code|null}]`, `fiscal_result` (D-05).
5. **Server qayta hisoblaydi** (postingda, DB holatidan): registrlar (`debt_payment_allocations`, `debt_moves`, `settled_amount`) **server** allokatsiyasi bo'yicha; fiskal chek payload'i qurilma yuborgan ko'rinishda saqlanadi (FM imzolagan — o'zgarmaydi). Farq bo'lsa voqea rad etilmaydi — `sync_exceptions(kind='debt_allocation_mismatch', details:{device, server})`.
6. **Ortiqcha summa (offline, F-08):** `is_offline=true` va `amount` server chegarasidan katta — qabul; chegaragacha allokatsiya; qolgani `debt_payments.unallocated_amount`; provodka `Dt 5010/5710 / Kt 6310` (olingan bo'nak, analitika `counterparty_id`); `sync_exceptions(kind='debt_overpayment_offline')` + M18 Egasiga. Hal qilish (BO-06, Buxgalter/Egasi): (a) qaytarish — `cash_movements` `reason='other'`, `direction='out'`, `account='6310'`, `counterparty_id` (D-17); (b) keyingi qarzga hisoblash — `ledger_adjustments` `Dt 6310 / Kt 4010` (`analytics.counterparty_id`). `422 VALIDATION_ERROR` (`debt_payment_exceeds_balance`) — faqat online (`is_offline=false`) va REST.
7. **Fiskal yo'l:** lokal ko'prik — chekni qurilma FM orqali imzolaydi (natija `fiscal_result` bilan); hamkor bulut va `fake` — server chiqaradi; `outbox_jobs(kind='ofd_send')` faqat `partner_cloud` rejimida.

### D-05. POS voqeasida fiskal natija va OFD tasdig'i qaytishi (T-026, T-119, T-154; qaror #68)

1. `sale.created`, `return.created`, `debt_payment.created` payload ildizida: `fiscal_result: {fm_terminal_id, fm_receipt_seq, fiscal_sign, qr_url, fiscal_at} | null` — lokal ko'prik rejimida (`FISCAL_PROVIDER = multikassa_local | fiscaldrive_local`) chek FM'da imzolangan bo'lsa **majburiy**; hamkor bulut va `fake` rejimida — `null` (server chiqaradi); faqat-qarz sotuvda — `null`.
2. Server: `fiscal_receipts` yozuvi `status='fiscalized'`, `fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`, `fiscal_at` to'ldiriladi; `ofd_acked_at` NULL qoladi (48 soat hisobida).
3. Server javobi `fiscal.status` ∈ `"pending" | "fiscalized" | "deferred"`.
4. **OFD tasdig'i:** lokal ko'prik — `fiscal.status` agent vazifasi natijasidagi `acked[]` (D-01 6-band) bo'yicha server `fiscal_receipts.ofd_acked_at` ni `uq_fiscal_fm_seq` (`tenant_id, fm_terminal_id, fm_receipt_seq`) orqali yangilaydi; hamkor bulut — adapter poll/webhook. Barcha cheklar ack olgach 48 soat bloki yechiladi (#43).
5. **`RECEIPT_SEQ_CONFLICT`** (C-103): `fiscal_result` bor voqea rad etilmaydi — server `receipt_seq` ni shu smenadagi `max(receipt_seq) + 1` ga qayta raqamlaydi, qurilma qiymati `fiscal_receipts.payload.device_receipt_seq` da, `sync_exceptions(kind='receipt_seq_conflict')`; `fiscal_result` yo'q bo'lsa — `rejected`, `retryable:false` (hozirgidek).
6. 18:628 dagi `FiscalPort.issue_credit_payment()` → `FiscalPort.register_sale(kind='debt_settlement')`; 21 §1 `register_sale` izohi `# kind: sale | debt_settlement | credit_sale`.

### D-06. Yopilgan davrga kech kelgan POS voqealari va davr yopish tayyorligi (T-028; qaror #69; F-09)

1. `/sync/push` orqali keladigan POS voqealari (`shift.*`, `sale.created`, `return.created`, `debt_payment.created`, `cash_movement.created`, `expense.created`, `transfer.*`, `stock_count.line_recorded`) **`PERIOD_CLOSED` bilan rad etilmaydi**.
2. Hujjat `doc_date` — asl (fiskal haqiqat). `doc_date` yopilgan davrda bo'lsa: registr sanalari = birinchi ochiq davrning 1-kuni (`ledger_entries.entry_date`, `vat_moves.period`, `cash_moves`/`debt_moves` sanasi); `stock_moves.moved_at` = asl biznes vaqti (D-19) — qoldiq tarixi buzilmaydi, tannarx tuzatishi recost bilan joriy davrda; `ledger_entries.analytics.correction_of_period = "YYYY-MM"` (asl oy); `sync_exceptions(kind='late_in_closed_period', details:{period, doc_date})`; Buxgalterga M18.
3. Back-office REST hujjatlari uchun `PERIOD_CLOSED` qoidasi o'zgarmaydi (`doc_date` yopilgan davrda → rad). Bekor qilish (`cancel`) — yopilgan davrdagi hujjatda ham ruxsat, storno joriy ochiq davr sanasida (13 §5.2; T-132).
4. **`GET /period-closings/{period}/readiness`** javobi:
   `{period, ready, blockers: ["recost_pending","fiscal_pending","devices_unsynced"], warnings: ["tax_settlement_missing","opening_0000_nonzero","open_shifts","drafts_in_period","devices_not_synced_after_period_end"], pending_recost_jobs, pending_fiscal_receipts, unsynced_devices: [{device_id, cash_register_name, outbox_pending_count, outbox_oldest_pending_at}], opening_balance_unresolved: bool}`
   - `devices_unsynced` (bloker): `devices.kind IN ('web','android') AND revoked_at IS NULL AND outbox_pending_count > 0 AND outbox_oldest_pending_at < period_end + 1 kun`; hal qilish — sinxronlash yoki qurilmani bekor qilish (16 §9, `confirm_pending_loss`);
   - `devices_not_synced_after_period_end` (ogohlantirish): faol qurilmaning `last_sync_at < period_end + 1 kun`;
   - `recost_pending` (bloker): `recost_jobs.status IN ('queued','running','failed') AND from_date ≤ period_end`;
   - `fiscal_pending` (bloker): davr cheklari `fiscal_receipts.status IN ('pending','sent','failed')`.
5. `POST /period-closings`: faqat **eng eski ochiq oy** yopiladi, aks holda `409 PERIOD_CLOSE_OUT_OF_ORDER` (17 §15 ga yangi kod).

### D-07. E-ishonchnoma (`powers_of_attorney`) (T-006)

1. **12 DDL** (revizion 0020 `fiscal_marking_edocs` ichida, `einvoices` dan keyin):
   ```sql
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
   ```
   `goods_receipts` ga `poa_id UUID NULL REFERENCES app.powers_of_attorney(id)`; `poa_number` qoladi (poa'dan to'ldiriladi yoki qo'lda). `outbox_jobs.kind` ga `poa_send`. RLS/`updated_at` trigger ro'yxatlariga qo'shiladi.
2. **Holatlar** (11): `draft → pending_signature → sending → sent → accepted | rejected`; `sending → failed → (submit-signed) sending`; `draft | pending_signature → cancelled`.
3. **REST** (19 §8a "E-ishonchnoma"):
   - `POST /powers-of-attorney` — `{purchase_order_id?, supplier_id, employee_user_id, valid_from (standart bugun), valid_to (standart +10 kun), doc_date}` → `201 {id, status:"pending_signature", …}`; ruxsat `purchases.create`; Idempotency majburiy.
   - `GET /powers-of-attorney?purchase_order_id=&supplier_id=&status=&cursor=&limit=`, `GET /powers-of-attorney/{id}` — `purchases.create` yoki `purchases.receive` yoki `purchases.post`.
   - `POST /powers-of-attorney/{id}/sign-challenge` → `{document_hash, challenge_id}`; `POST /powers-of-attorney/{id}/submit-signed` `{challenge_id, signature_pkcs7}` → `202 {status:"sending"}`, `outbox_jobs(kind='poa_send')` → operator qabul qilgach `sent`, `number`/`operator_doc_id`; javob poll orqali `accepted`/`rejected`. Ruxsat `einvoice.sign`; xatolar `409 DOC_INVALID_STATE` (`pending_signature`/`failed` dan tashqari), `422 EIMZO_SIGN_FAILED`, `503 EINVOICE_PROVIDER_UNAVAILABLE`.
   - `POST /powers-of-attorney/{id}/cancel` `{reason}` — faqat `draft`/`pending_signature`; `purchases.create`.
4. `EInvoicePort.send_power_of_attorney(poa_id, signed_payload)` (21 §6) shu jadvaldan o'qiydi.
5. **Ekranlar:** BO-04 "E-ishonchnoma berish" → `POST /powers-of-attorney` → E-IMZO → `submit-signed`; POS-08 `poaNumber` — ixtiyoriy `Input`, standart: `GET /powers-of-attorney?purchase_order_id=` dagi `sent|accepted` yozuv `number`i → `goods_receipts.poa_id`/`poa_number`; BO-15 "E-ishonchnomalar" ro'yxati — `GET /powers-of-attorney`.

### D-08. E-TTN: holatlar, ustunlar va ekran amallari (T-003, T-004)

1. **12 `ettn_documents`:** status CHECK → `('pending_signature','sending','registered','received','accepted','rejected','cancelled','failed')`; yangi ustunlar `counterparty_id UUID NULL REFERENCES app.counterparties(id)`, `receipt_id UUID NULL REFERENCES app.goods_receipts(id)`, `doc_date DATE NULL`, `payload JSONB NOT NULL DEFAULT '{}'`, `signed_at TIMESTAMPTZ NULL`, `last_error TEXT NULL`; CHECK `(direction = 'in' OR einvoice_id IS NOT NULL OR transfer_id IS NOT NULL)` (2121-qator o'rniga). Izoh (2117): "chiquvchi: pending_signature → sending → registered → accepted/rejected; sending → failed → sending (qayta imzo/yuborish); kiruvchi: received → accepted/rejected; cancelled".
2. **11 holat mashinasi** shu izoh bilan.
3. **19 §20:** `register-manual` tanasi `{operator_doc_id, doc_date}` (`ettn_date` emas); `ettn_status` filtri qiymatlari — CHECK ro'yxati.
4. **Ekran amallari:**
   - BO-03 "Ko'chirishlar" tabi: har `posted` ko'chirish qatorida e-TTN holati va amallar — "E-TTN imzolash" (`einvoice.sign`; `POST /ettn-documents/{id}/sign-challenge` → E-IMZO → `/submit-signed`), "Qo'lda ro'yxatga olish" (`transfer.create`; `/register-manual`), "Jo'natish" (`transfer.create`; `POST /transfers/{id}/send`, faqat e-TTN `registered` yoki `on_foot_or_public`); qabul tomonida "E-TTN tasdiqlash / rad etish" (`transfer.receive` + `einvoice.sign`; `sign-challenge?action=accept|reject` → `/accept` | `/reject`).
   - BO-15: "Kiruvchi e-TTN" ro'yxati (`GET /ettn-documents?direction=in`) — "Tasdiqlash"/"Rad etish" (`purchases.receive` + `einvoice.sign`); chiquvchi e-faktura uchun "Yuborish" (`POST /einvoices/{id}/send`, `einvoice.sign`) va "Bekor qilish" (`POST /einvoices/{id}/cancel`, `einvoice.sign`).
   - POS-09 e-TTN izohi: "server `post`da `ettn_documents(status='pending_signature')` yaratadi; Egasi/Buxgalter BO-03 da E-IMZO bilan imzolaydi; Omborchi ekranida holat 'E-TTN imzo kutilmoqda'".
   - Omborchida `einvoice.sign` yo'q — o'zgarmaydi (imzo Egasi/Buxgalterda).

### D-09. Chek shablonida qator QQS (T-030)

08 §13.1 namunasida har tovar qatori ostidagi kichik shriftli qator: `MXIK 10202001001000000 · dona · 4780000123456 · QQS 12%: 2 571,43` (1-qator: 24 000 × 12/112 = 2 571,43). QQSsiz qatorda: `· QQSsiz (imtiyoz: <kod>)`. 554-qator: "MXIK, o'lchov birligi, shtrix kod va **QQS stavkasi/summasi** (qator darajasida, qaror #26 formulasi) har tovar qatori ostida kichik shrift bilan". Chek oxiridagi "QQS / НДС (12%, ichida)" jami qatori qoladi.

### D-10. Davlat hisobotini tuzatish va tasdiqlash (T-014)

1. Tuzatish my.soliq.uz kabinetida kiritiladi; tizim faqat **qayd etadi** (imzosiz): `POST /state-reports/{id}/correction` tanasi `{comment (majburiy, ≤1000), portal_ref?: string}` → `200 {id, status:"correction_sent", correction_sent_at}`; xatolar `VALIDATION_ERROR`, `DOC_INVALID_STATE`; `EIMZO_SIGN_FAILED` olib tashlanadi.
2. Yangi `7a. POST /state-reports/{id}/confirm` (20 da #7 va #8 orasiga) `{comment?}` → `200 {id, status:"confirmed", confirmed_at}` — `match`/`diff_found` (tolerance ichida) holatdan; ruxsat `tax.correction.submit`.
3. Ruxsat: `tax.correction.submit` — **Buxgalter va Egasi** (15 §2.2 matritsasi); 20:228 dagi "faqat Egasi" olib tashlanadi. 15 §2.1 tavsifi: "Davlat hisobotiga tuzatish/tasdiqni qayd etish".
4. **12 `state_reports`:** status CHECK → `('uploaded','compared','match','diff_found','correction_sent','confirmed','auto_accepted')`; `correction_signature` ustuni o'rniga `correction_comment TEXT NULL`, `correction_portal_ref TEXT NULL`; yangi `confirmed_at TIMESTAMPTZ NULL`, `confirmed_by UUID NULL REFERENCES app.users(id)`.
5. **11** holat mashinasi: `uploaded → compared → match | diff_found → correction_sent | confirmed | auto_accepted`.
6. **07 BO-10:** `correctionNote` → `comment`; "Tasdiqlangan deb belgilash" → `POST /state-reports/{id}/confirm`; holat nomlari 12 enum'i bilan (`confirmed` — "Tasdiqlandi").

### D-11. 1C partiyasining o'lik holatlari (T-016, T-036, T-037)

1. **T7 yon ta'siri:** "partiyaning **barcha** `pending` itemlari → `queued`" (dispetcher so'rovi `queued|unknown` o'zgarmaydi); §7.5 diagramma izohi: `pending → queued: partiya queued bo'lganda (T7)`.
2. **T12a** `verifying → mismatch`: `read_totals` vazifasi 3 urinishdan keyin `failed`/`expired` → `onec_reconciliations.status='failed'`, partiya `error_code` = vazifa xato kodi, itemlar `written` holatida qoladi, Telegram `onec_export_mismatch`; foydalanuvchi W-50 (qayta solishtirish) yoki W-47 (qabul) qila oladi.
3. **T17** `mismatch → done`: W-50 natijasida barcha itemlar mos — `accepted_by/accepted_at/accept_reason` tozalanadi (`onec_export_batches_check3` buzilmaydi), itemlar `mismatch → verified` (§7.5 ga shu o'tish). **T17b** `done → mismatch`: W-50 farq topsa.
4. 1738-qator: "Yakuniy holatlar: `done`, `failed`, `cancelled`. `partial` → T13 (qayta yuborish) yoki T14 (qabul); `mismatch` → T14 (qabul), T17 (W-50). `partial`/`mismatch` qabul qilinsa (`accepted_at`) status o'zgarmaydi — faqat navbatni ochadi."
5. W-50 (`reconcile`) ruxsat etilgan holatlar: `done`, `partial`, `mismatch`; javob izohi: "natija T17/T17b bo'yicha".

### D-12. `sync_exceptions.kind` yagona ro'yxati (T-069)

12 `sync_exceptions.kind` CHECK va 16 §5 ro'yxati: `price_mismatch`, `archived_product`, `stock_negative`, `debt_limit_exceeded_offline`, `approval_limit_exceeded_offline`, `receipt_seq_conflict`, `debt_overpayment_offline`, `debt_allocation_mismatch`, `late_in_closed_period`, `cost_unknown`, `count_late_move`. Har tur — 16 §5 jadvalida bir qatorlik ta'rif va manba bo'lim. Offline qaytarish/chegirma limitidan oshish — ustun-bayroq emas, `sync_exceptions(kind='approval_limit_exceeded_offline')` + `doc_approvals` + M18.

### D-13. Qaytarish: fiskal qaytarish summasi va qaytarish usuli (T-031)

1. **Qarzli sotuvni qaytarish:** avval shu sotuvning ochiq qarzi kamayadi (`debt_adjustment` qismi — chek yo'q, `Kt 4010`), qolgani `refund_method` bo'yicha pul bilan qaytariladi va faqat shu qismga `kind='return'` chek chiqadi:
   `debt_part = min(return_amount, open_debt_of_sale)`; `money_part = return_amount − debt_part`; `fiscal_refund ≤ fiscalized_amount(sale) − already_fiscally_refunded(sale)` (`fiscalized_amount` = sotuvning `sale`/`debt_settlement` cheklaridagi summalar).
2. `return.created.receipt_seq` — `integer|null` (`money_part = 0` bo'lsa `null`, chek yo'q).
3. `refund_method` enum: `cash | card | uzqr | click | payme | uzum | debt_adjustment` (standart — asl to'lov usuli). Click/Payme/Uzum pulni qaytarish provayder kabinetida qo'lda; tizim qayd etadi.
4. 13 §2.5: `Kt 5710` analitikasi `payment_method = refund_method`; `debt_adjustment` → `Kt 4010`.
5. **Qator summasi** (chegirmali qator): `refund_line = ROUND_HALF_UP(sale_line.line_total × ret_qty / sale_line.qty, 0)`, qatorning oxirgi qaytarilishi qoldiqni oladi (`line_total − Σ oldingi refund_line`); payload'dagi `price` (4 xona, `return_lines.price`) — faqat ma'lumot, server hisoblaydi.

### D-14. Filial yaratish va ombor hisobi (T-013)

1. `POST /branches` tanasiga `warehouse: {type: "store"|"stock"}` (standart `store`); server `warehouses.inventory_account` ni `type` dan qo'yadi (`store` → `2920`, `stock` → `2910`).
2. 12: `warehouses.inventory_account` dan `DEFAULT '2910'` olib tashlanadi (NOT NULL qoladi, ilova to'ldiradi). Signup provisioning (12 §5.2) — standart filial ombori `type='store'`, `inventory_account='2920'`.
3. Yangi `37a. PATCH /warehouses/{id}` — `{inventory_account: "2910"|"2920", name?, version}`, ruxsat `settings.branches`; omborda `stock_moves` bo'lsa `409 WAREHOUSE_ACCOUNT_LOCKED` (17 §15 ga yangi kod); javob `{id, name, type, inventory_account, version}`.
4. 07 BO-12 manbasiga `GET /api/v1/warehouses?branch_id=`, `PATCH /api/v1/warehouses/{id}`.

### D-15. Aylanma solig'i rejimida QQSli kirim (T-029)

13 §4.3 ga: "`regime='turnover'` tenantda 2.6 1-qatori = faktura summasi **QQS bilan** (`stock_lots.unit_cost` QQS bilan), 2-qator (`Dt 4410`) yozilmaydi; 2.12 dagi sovg'a QQS qatori (`Dt 9430 / Kt 6410`) yozilmaydi; `vat_moves` yozilmaydi". 13 §2.6 va §2.12 ostiga shu qoidaga havola.

### D-16. `vat_offset` — tenant darajasida (T-032)

1. `POST /tax-settlements`: `branch_id` faqat `tax_kind='turnover_tax'` da majburiy (filial bo'yicha, SK 468-modda 2-qism); `vat_offset` da yuborilmaydi — server `branches.is_default = true` filialini yozadi (DDL `NOT NULL` saqlanadi).
2. Yagonalik: `vat_offset` — (tenant, davr) uchun bitta faol hujjat; `turnover_tax` — (filial, davr) uchun bitta. Xato matni shunga.
3. 13 §2.26 ga: "`vat_offset` (tenant, davr) bo'yicha, `vat_moves` tenant bo'yicha yig'iladi (#31 — 1 tenant = 1 STIR)".
4. 07 BO-07: `branchId` `Select` faqat `turnover_tax` tanlanganda ko'rinadi va majburiy.

### D-17. Kassa pul harakati `reason='other'` (T-027)

1. Juftlik: `collection`, `owner_withdrawal` → faqat `out`; `deposit` → faqat `in`; `other` → ikkalasi; buzilsa `422 VALIDATION_ERROR`.
2. 13 §2.18 ga: `other/out` → `Dt account / Kt 5010` (standart `account = 9430`); `other/in` → `Dt 5010 / Kt account` (standart `account = 9390`). Ixtiyoriy `account` (Buxgalter/Egasi tanlaydi) ruxsat etilgan ro'yxatdan: `9430`, `9390`, `6310`, `4010`, `4730`; `6310`/`4010` da `counterparty_id`, `4730` da `employee_id` majburiy.
3. 12 `cash_movements`: `account TEXT NULL CHECK (account IS NULL OR account IN ('9430','9390','6310','4010','4730'))`, `employee_id UUID NULL REFERENCES app.users(id)`, `CHECK (reason = 'other' OR account IS NULL)`, `CHECK ((reason IN ('collection','owner_withdrawal') AND direction='out') OR (reason='deposit' AND direction='in') OR reason='other')`; mavjud `CHECK (reason = 'owner_withdrawal' OR counterparty_id IS NULL)` → `CHECK (reason IN ('owner_withdrawal','other') OR counterparty_id IS NULL)`.
4. 13 §1 hisoblar ro'yxatiga `6310 — Xaridor va buyurtmachilardan olingan bo'naklar (P, kontragent)`.

### D-18. POS xarajati — `expense.created` voqeasi (T-002)

1. POS-14 "Xarajat" — alohida `expense.created` voqeasi (`source='cash'`), `cash_movement.created` emas. Payload: `{id, doc_date, branch_id, cash_register_id, shift_id, category_id, amount, comment?, tax_type?, approval?}` (20 #42 tanasi bilan bir xil maydonlar).
2. Ruxsat (POS): `cash.withdraw` (limit, standart 50 000 so'm — #23); limitdan oshsa `approval` (`ApprovalRef`, `kind='cash_withdrawal_over_limit'`). Kassirda `expenses.create` yo'q — bu yo'l faqat `source='cash'` uchun. Server `ExpensePostingService` bilan darhol `posted` (`expenses` + `cash_moves`).
3. `cash_movement.created.reason` enum'idan `expense` va `expense_category_id` maydoni olib tashlanadi; 12 CHECK o'zgarmaydi.

### D-19. Biznes vaqti: `effective_created_at` va `stock_moves.moved_at` (T-043)

1. 16 §8: `effective_created_at = clamp(created_at, received_at − OFFLINE_CLAMP_WINDOW, received_at + CLOCK_SKEW_WARN_S)`; `doc_date`, 48 soat hisobi va `moved_at` shundan; xom qiymat `sync_receipts.result.client_created_at` da.
2. 12 `stock_moves.moved_at` izohi: "hujjat biznes vaqti — POS voqeasida `effective_created_at`, back-office hujjatda `posted_at`; `DEFAULT now()` faqat zaxira".
3. 13 X-02: "`stock_counts` `post`dan keyin kelgan, `started_at < moved_at ≤ line.counted_at` bo'lgan harakat → avtomatik tuzatuvchi inventarizatsiya qatori (13 §2.11 provodkasi bilan, `doc_type='stock_counts'`, `entry_date` = joriy ochiq davr) + `sync_exceptions(kind='count_late_move')`".

### D-20. Qaytgan muddati o'tgan tovar — `blocked_qty` (T-123)

12 `stock_lots.blocked_qty NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (blocked_qty >= 0 AND blocked_qty <= qty_left)`. 13 §2.5 #48 bandi: "`+qty` asl partiyaga va shu miqdor `blocked_qty` ga; FIFO/sotuv `qty_left − blocked_qty` dan; `write_offs` (`expired_return`) `post`ida `blocked_qty` va `qty_left` kamayadi". 18:426 va 04 BP-04 shu matnga.

### D-21. AVECO va manfiy qoldiq tannarxi (T-124, T-134)

1. 12 `avg_costs.total_value NUMERIC(18,2) NOT NULL DEFAULT 0`.
2. 13 §3.1/§3.3: kirim — `total_value += qty × cost`, `avg = total_value / qty_after`; chiqim — `cogs = ROUND_HALF_UP(qty × avg, 2)`, `total_value −= cogs`; `qty_after ≤ 0` → `avg` o'zgarmaydi, `total_value = 0`, chiqim `pending`.
3. Manfiy qoldiqdagi chiqim: `lot_allocations` elementi `{lot_id: null, qty, unit_cost, pending: true}`; `unit_cost` = oxirgi partiya narxi → `products.last_purchase_cost` (eng so'nggi `goods_receipts` partiyasi `unit_cost`) → `0` + `sync_exceptions(kind='cost_unknown')`. Keyingi kirim `post`i `recost_jobs(from_date = eng eski pending chiqim sanasi)` qo'yadi.
4. FIFO ↔ AVECO almashtirish (yil boshida): FIFO→AVECO — `avg = Σ qty_left × unit_cost / Σ qty_left`, `total_value = Σ`; AVECO→FIFO — har (ombor, mahsulot) uchun bitta partiya `unit_cost = avg`, `qty = qty`; provodkasiz.

### D-22. Do'kon agenti lokal API sxemalari (T-141)

21 §16.1 "Lokal API sxemalari" (yangi): standart port `47110` (agent sozlamasida o'zgaradi). Barcha so'rov/javob JSON, pul — butun son tiyin (`int64`), vaqt — ISO 8601 UTC.

| Yo'l | So'rov | Javob |
|---|---|---|
| `GET /v1/status` | — | `{agent_version, capabilities:{fiscal:{enabled, provider}, print:{enabled}}, fiscal_devices:[{local_id, fm_state, pending_count, oldest_unacked_at}]}` |
| `POST /v1/pair` | `{code, device_id}` | `{local_token, expires_at:null}` |
| `POST /v1/fiscal/open-shift` | `{cash_register: CashRegisterRef, shift_no, cashier_name}` | `FiscalShiftResult {fm_terminal_id, opened_at}` |
| `POST /v1/fiscal/close-shift` | `{cash_register, shift_no}` | `ZReport {fm_terminal_id, z_number, totals:{sale, return, by_payment_form}, closed_at}` |
| `POST /v1/fiscal/sale`, `/refund` | `FiscalReceiptPayload {cash_register, receipt_seq, kind, items:[{name, mxik, package_code, unit_code, qty_milli, price_tiyin, amount_tiyin, vat_rate, vat_tiyin, marking_codes[]}], payments:{payment_form, cash_tiyin, card_tiyin, qr_tiyin, card_type, card_mask, rrn}, refund_info?:{fm_terminal_id, fm_receipt_seq, fiscal_sign}}` | `FiscalResult {fm_terminal_id, fm_receipt_seq, fiscal_sign, qr_url, fiscal_at}` |
| `GET /v1/fiscal/device-status` | `?local_id=` | `FiscalDeviceStatus {fm_state, pending_count, oldest_unacked_at}` |
| `GET /v1/fiscal/unsent` | `?local_id=` | `{items: [UnsentReceipt {fm_receipt_seq, fiscal_at, amount_tiyin}]}` |
| `POST /v1/fiscal/resend` | `{local_id}` | `ResendResult {sent, failed, acked:[{fm_terminal_id, fm_receipt_seq, acked_at}]}` |
| `POST /v1/print/raw` | `{printer_local_id, data_base64, encoding}` | `{status:"sent"}` |

`CashRegisterRef = {cash_register_id, local_id}`. Xato shakli `{code, message_key, params?}`; HTTP: `401` (lokal token yo'q/noto'g'ri), `403` (`Origin` ro'yxatda yo'q), `409` (`FISCAL_SHIFT_STATE`, `FISCAL_DEVICE_LOCKED`), `423` (`FISCAL_OFFLINE_48H_BLOCKED`), `502` (`FISCAL_PROVIDER_ERROR`); hamkorga xos maydonlar adapter ichida qoladi. `FakeLocalBridge` shu sxemalarga tayanadi.

### D-23. Obuna to'lovi summasi va davr (T-144; qaror #70; F-04, F-05)

`POST /billing/checkout`: `amount` — oy: `99000 + 39000 × extra_registers`; yil: `950400 + 39000 × 12 × extra_registers` (chegirma faqat asosiy tarifga); `billing_payments.amount_breakdown = {plan, period, addons:[{code, qty, unit_price, months}], discount}`; muvaffaqiyatli to'lovda `new_end = max(current_period_end, now()) + 1 oy | 12 oy`. Holatlar: `trial` (30 kun) → `grace` (24 soat) → `restricted`; to'lov → `active`; `closed` — faqat platforma admini (avtomatik yo'q). 07 BO-19 `period` qiymatlari `month|year`.

---

## 4. Noyob muammolar reestri

Ustunlar: **T** — noyob ID; **Daraja**; **Manbalar**; **Verdikt**; **Muammo**; **Guruhlar** — amali bor guruhlar. Verdikt izohi kerak bo'lsa qavsda.

### 4.1 Kritik (43)

| T | Daraja | Manbalar | Verdikt | Muammo | Guruhlar |
|---|---|---|---|---|---|
| T-001 | kritik | B-003, C-001, C-072, B-147y | TASDIQ | `price_changes` limitdan oshganda 19/18/17/15 `draft` deydi; #25, 11, 12 CHECK, 07, QT-M09-02 — `pending_approval` → `posted`/`rejected` | G-a, G-b, G-c, G-e |
| T-002 | kritik | B-002, C-012 | TASDIQ | POS xarajati `cash_movement.reason=expense` — DB CHECK'da yo'q; 16/20 esa `expense.created` (D-18) | G-a, G-c |
| T-003 | kritik | B-004, B-005, B-006, C-011, B-112 | TASDIQ | `ettn_documents`: `failed` holati, kiruvchi alohida e-TTN CHECK'i, `counterparty_id/doc_date/payload/signed_at` ustunlari yo'q (D-08) | G-b, G-c |
| T-004 | kritik | C-008, B-088 | TASDIQ | E-TTN imzolash/qabul va chiquvchi e-faktura `send`/`cancel` hech bir ekranda yo'q (D-08) | G-a |
| T-005 | kritik | B-018, B-019, C-009, C-089, B-104, B-105 | TASDIQ | POS-09: `fromBranchId` (API `from_warehouse_id`), `/post` qadami tushgan, `vehicle_plate` yo'q, natija matni noto'g'ri | G-a |
| T-006 | kritik | B-014, C-010, B-108 | TASDIQ | E-ishonchnoma: jadval, REST, `poa_send` yo'q (D-07) | G-a, G-b, G-c, G-d |
| T-007 | kritik | B-007, C-040 | TASDIQ | Faqat-qarz sotuvda "`fiscal_receipt_seq` saqlanadi" — ustun yo'q; `receipt_seq` `null` bo'lishi kerak | G-c |
| T-008 | kritik | B-008 | TASDIQ | `return.created.lines[].unit_price` (Money) ↔ `return_lines.price` (4 xona) | G-c |
| T-009 | kritik | B-009 | TASDIQ | `POST /ledger-adjustments` da `branch_id` yo'q, DDL `NOT NULL` | G-c |
| T-010 | kritik | B-010, C-014, B-092, C-050 | TASDIQ | `BankSettlement.variance_amount` ishorasi/formulasi 20 va 07 BO-24 da teskari; BO-24 da `variance` maydoni, PATCH endpoint, import natijasi yo'q | G-a, G-c |
| T-011 | kritik | B-011, C-091 | TASDIQ | BO-08: `doc_date__*` filtri (API `entry_date__*`), `entryDate` (API `doc_date`), `account_dt/kt/amount` maydonlari yo'q | G-a |
| T-012 | kritik | B-012, C-023, B-063, B-064 | TASDIQ | Kassa arxivlash: 07 PATCH `archived:true`; 20 da alohida endpoint indekssiz/bo'limsiz; GET/POST `version` qaytarmaydi | G-a, G-c |
| T-013 | kritik | B-013, C-015 | TASDIQ | Filial ombori har doim `2910`; `type` so'ralmaydi; `inventory_account` ni saqlash endpointi yo'q (D-14) | G-a, G-b, G-c |
| T-014 | kritik | B-015, B-016 (qisman), C-024, C-140 | TASDIQ | BO-10 "Tasdiqlandi" — endpoint/holat yo'q; tuzatish E-IMZO talab qiladi (07/13: kabinetda, imzosiz); ruxsat "faqat Egasi" ↔ 15 (D-10) | G-a, G-b, G-c |
| T-015 | kritik | B-017, C-130 | TASDIQ | POS-03 `card_manual` — API/CHECK `card` | G-a |
| T-016 | kritik | B-020, C-063 | TASDIQ | W-50 "`mismatch → done`" §7.1 da yo'q va `check3` ni buzadi; "yakuniy holatlar" T13/W-50 ga zid (D-11) | G-f |
| T-017 | kritik | B-021, C-007 | TASDIQ | "`sales.status='deferred'`" — CHECK'da yo'q; `deferred` — faqat javobdagi `fiscal.status` | G-a, G-e |
| T-018 | kritik | B-022 | TASDIQ | QT-RLS-05 `products` ni global jadval deydi — `app.products` tenantli | G-e |
| T-019 | kritik | B-023 | TASDIQ | Bonus birlik: 31/03 — 0 narxli partiya; 13 — narx chegirmasi (13 qoladi) | G-a, G-e |
| T-020 | kritik | B-001 | TASDIQ | 0003 dagi `auth.*` FK'lari 0007 da yaratiladigan `platform.oauth_clients` ga — migratsiya yiqiladi | G-b |
| T-021 | kritik | B-037, B-038, B-039, B-145c, B-145e, B-145f | TASDIQ | Auth yozuvchi SECURITY DEFINER funksiyalari yo'q; Telegram chat'ini telefon bo'yicha topish yo'q; lokaut `sessions.suspended_at` yo'q (D-02) | G-b, G-c, G-e |
| T-022 | kritik | C-002, C-069, C-071, B-145i, C-148 | TASDIQ | Do'kon agenti asosi (B5) B7 jadvallari/vazifalariga tayanadi; CHECK fiskal/printer vazifalarini rad etadi; kassa↔agent bog'lanmagan; tarozi bosqichi zid (D-01) | G-a, G-b, G-c, G-d, G-f |
| T-023 | kritik | C-003, B-047 | TASDIQ | Kassasiz qarz to'lovi cheki: FM, 48 soat hisobi, `receipt_seq` aniqlanmagan; `branch_id` "shartli" (D-03) | G-a, G-b, G-c, G-e |
| T-024 | kritik | C-004, C-097, C-098 | TASDIQ | Offline qarz to'lovi cheki qatorlarini qurilma hisoblay olmaydi; proporsiya/yaxlitlash/tartib aniqlanmagan (D-04) | G-a, G-b, G-c, G-d, G-e |
| T-025 | kritik | C-005 | TASDIQ | Offline ortiqcha qarz to'lovi `422` — FM imzolagan chek "yetim" (D-04 §6, F-08) | G-a, G-b, G-c, G-e |
| T-026 | kritik | C-006 | TASDIQ | Lokal ko'prik FM natijasi `sale.created` da yo'q; OFD ack serverga qaytmaydi (D-05) | G-a, G-c, G-d, G-e |
| T-027 | kritik | C-013, B-076 | TASDIQ | `cash_movements.reason='other'` provodkasi yo'q; `reason↔direction` juftligi majburlanmagan (D-17) | G-b, G-c, G-e |
| T-028 | kritik | C-017, C-048, B-127, B-128 | TASDIQ | Yopilgan davrdagi offline chek `PERIOD_CLOSED` bilan rad; tayyorlikda qurilmalar, `warnings`, ketma-ket yopish yo'q (D-06) | G-a, G-b, G-c, G-e |
| T-029 | kritik | C-018 | TASDIQ | Aylanma rejimida QQSli kirim provodkasi muvozanatlashmaydi (D-15) | G-b |
| T-030 | kritik | C-019 | TASDIQ | Chek namunasida qator QQS stavkasi/summasi yo'q (D-09) | G-a |
| T-031 | kritik | C-020, C-099 | TASDIQ | Fiskallanmagan qarz sotuvini qaytarishda chek; `refund_method` da QR/provayderlar yo'q; chegirmali qator qaytarish summasi (D-13) | G-a, G-b, G-c |
| T-032 | kritik | C-021, B-060, B-086, C-090 | TASDIQ | `vat_offset` filial bo'yicha, `vat_moves` da filial yo'q (D-16) | G-b, G-c |
| T-033 | kritik | C-022, B-109 | TASDIQ | `POST /goods-receipts` da `lines[].marking_codes` yo'q | G-a, G-c |
| T-034 | kritik | C-025 | TASDIQ | 15 matritsasida Kassirda `returns.approve` "–"; katalog/seed/#23 — limit 100 000 | G-c |
| T-035 | kritik | C-026 | TASDIQ | US-M07-02 / QT-M07-02: Omborchi tasdig'i bilan qoldiq oshadi — #49 ga zid | G-a, G-e |
| T-036 | kritik | C-027 | TASDIQ | `verifying` dan chiqish yo'q — baza navbati cheksiz bloklanadi (D-11) | G-f |
| T-037 | kritik | C-028 | TASDIQ | T7 faqat "birinchi itemlar"ni `queued` qiladi — partiya to'xtaydi (D-11) | G-f |
| T-038 | kritik | C-029 | TASDIQ | B1 da boshlang'ich qoldiq (posting B2 da) | G-a |
| T-039 | kritik | C-030 | TASDIQ | US-M09-03 (kassada narx) B1 da, kassa B3 da | G-a |
| T-040 | kritik | C-031 | TASDIQ | B2 DoD "13 dagi barcha misollar" — ko'plari B3–B5 da quriladi | G-a |
| T-041 | kritik | C-032 | TASDIQ | B3 DoD "qarz limiti" — M08 B4 da | G-a |
| T-042 | kritik | C-033 | TASDIQ | B4 DoD "pilot do'kon bir hafta" — pilot B6 da | G-a |
| T-043 | kritik | C-016, C-102 | TASDIQ | `stock_moves.moved_at DEFAULT now()` — kech offline sotuv #53 oynasidan chiqadi; soat clamp faqat pastdan (D-19) | G-b, G-c |

### 4.2 O'rta (135)

| T | Daraja | Manbalar | Verdikt | Muammo | Guruhlar |
|---|---|---|---|---|---|
| T-044 | o'rta | B-024 | TASDIQ | W-49 `422 ONEC_DATE_PROHIBITED` ↔ katalog `409` | G-f |
| T-045 | o'rta | B-025 | TASDIQ | 11:149/15:63 `settings.valuation_method` — manba `valuation_method_history` | G-b, G-c |
| T-046 | o'rta | B-026 | TASDIQ | W-11 `config_supported=warn` — bunday holat yo'q | G-f |
| T-047 | o'rta | B-027 | TASDIQ | W-14 reassign holatlari §5.3 da yo'q | G-f |
| T-048 | o'rta | B-028 | TASDIQ | W-46 skip holatlari §7.5 ga zid, `unknown` xavfli | G-f |
| T-049 | o'rta | B-029 | TASDIQ | W-32 javobida `errors[]` yo'q | G-f |
| T-050 | o'rta | B-030 | TASDIQ | W-39 da `preview_result` yo'q | G-f |
| T-051 | o'rta | B-031 | TASDIQ | ExportBatch shaklida `accepted_at`, `cancel_*` maydonlari yo'q | G-f |
| T-052 | o'rta | B-032 | TASDIQ | W-08 log birlashmasi: `warn/warning`, `message_key`, `attachment_id` | G-f |
| T-053 | o'rta | B-033 | TASDIQ | A-10 `revoke_reason` doim `uninstall` | G-f |
| T-054 | o'rta | B-034 | TASDIQ | A-04 `cancel_requested` manbasi yo'q | G-f |
| T-055 | o'rta | B-035 | TASDIQ | A-07 `attachments.uploaded_by NOT NULL` — agentda foydalanuvchi yo'q | G-f |
| T-056 | o'rta | B-036, C-153 | TASDIQ | `onec_device_auth_approve` boolean — `ONEC_PAIRING_CODE_EXPIRED` ga yetib bo'lmaydi | G-b, G-c, G-e, G-f |
| T-057 | o'rta | B-040 | TASDIQ | `lines[].line_id` → `sale_lines.id` | G-c |
| T-058 | o'rta | B-041 | TASDIQ | Qurilma `cost_amount` yuboradi; `line_total`/`vat_amount` jadvalda yo'q | G-c |
| T-059 | o'rta | B-042, C-100, B-147q | TASDIQ | Faqat `discount_pct` CHECK'ni buzadi; chek chegirmasini taqsimlash va limit formulasi yo'q | G-a, G-c |
| T-060 | o'rta | B-043 | TASDIQ | `GET /sales` javobi `total` → `total_amount` | G-c |
| T-061 | o'rta | B-044 | TASDIQ | `ApprovalRef.approved_by_user_id` → `approved_by` | G-c |
| T-062 | o'rta | B-045 | TASDIQ | `payment_checkouts` enum'da `consumed` yo'q | G-c |
| T-063 | o'rta | B-046 | TASDIQ | `PAYMENT_NOT_CONFIRMED` noto'g'ri bo'limda | G-c |
| T-064 | o'rta | B-048, C-092 | TASDIQ | `owner_withdrawal` ta'sischisi POS payload/POS-14 da yo'q | G-a, G-c |
| T-065 | o'rta | B-049 | TASDIQ | `POST /einvoices` tanasida `source`, `sale_id` — ustun yo'q | G-c |
| T-066 | o'rta | B-050, B-107 | TASDIQ | `/sync/pull` scope ro'yxati to'liq emas; lokal `stock` keshi yo'q | G-c |
| T-067 | o'rta | B-051 | TASDIQ | Push `devices.last_seen_at` ni yangilamaydi | G-c |
| T-068 | o'rta | B-052 | TASDIQ | `device_name` ustuni yo'q | G-a, G-c |
| T-069 | o'rta | B-053, B-054 | TASDIQ | `sync_exceptions.kind` ro'yxati/CHECK yo'q; `limit_exceeded` ustun-bayrog'i yo'q (D-12) | G-b, G-c |
| T-070 | o'rta | B-055 | TASDIQ | `transfers` `lines[].qty` → `qty_sent` | G-c |
| T-071 | o'rta | B-056 | TASDIQ | PO/supplier_returns `version`/`VERSION_CONFLICT` — ustun yo'q | G-c |
| T-072 | o'rta | B-057 | TASDIQ | Bir filial ichida ko'chirish DB'da yiqiladi | G-c |
| T-073 | o'rta | B-058 | TASDIQ | Yetkazib beruvchi to'lovi `debt_openings` ni yopa olmaydi | G-c |
| T-074 | o'rta | B-059 | TASDIQ | 19 ro'yxatida mavjud bo'lmagan `suppliers` resursi | G-c |
| T-075 | o'rta | B-061 | TASDIQ | `EINVOICE_PROVIDER_UNAVAILABLE` 422 ↔ katalog 503 | G-c |
| T-076 | o'rta | B-062 | TASDIQ | `TenantSettings.store_name/locale` ↔ `tenants.name` | G-c |
| T-077 | o'rta | B-065, B-068, C-106, C-170 | TASDIQ | debts-aging: indeks ruxsati, `bucket`, `due_date`, `overdue_since` asosi | G-c |
| T-078 | o'rta | B-066 | TASDIQ | Davlat hisoboti yuklash faqat `vat|turnover` | G-a, G-c |
| T-079 | o'rta | B-067 | TASDIQ | `vat_moves` `doc_type` filtrida `write_offs`, `supplier_payments` yo'q | G-c |
| T-080 | o'rta | B-069 | TASDIQ | `owner_withdrawal_account` enum/standarti yo'q | G-c |
| T-081 | o'rta | B-070 | TASDIQ | Eksport `format` 20 da tanada, 17 da query'da | G-c |
| T-082 | o'rta | B-071 | TASDIQ | Bir/uch bosqichli hujjatlar ro'yxati 20:11 da xato | G-c |
| T-083 | o'rta | B-072, C-049 | TASDIQ (qisman) | Bank ko'chirmasi importi: FIFO moslashtirish birligi/chegarasi/ikki marta band qilish, manfiy komissiya | G-c |
| T-084 | o'rta | B-073 | TASDIQ | OCR `return` — `returns` faqat sync orqali | G-b, G-c, G-d |
| T-085 | o'rta | B-074 | TASDIQ | OCR `catalog` confirm ko'p mahsulot — bitta `created_doc_id` | G-b, G-c |
| T-086 | o'rta | B-075, C-060 | TASDIQ | Standart xarajat toifalari 7 umumiy nom ↔ seed 21 kod; 6410 nomi | G-a, G-c, G-d |
| T-087 | o'rta | B-077 | TASDIQ | Takroriy xarajat tasdig'i `expenses.approve` limitini chetlab o'tadi | G-c |
| T-088 | o'rta | B-078 | TASDIQ | 13 "Buxgalter o'zgartiradi" ↔ PATCH faqat `settings.tenant` | G-b |
| T-089 | o'rta | B-079, B-081, C-093 | TASDIQ | BO-14: 40c/40d manbada yo'q, Faktura.uz 4 maydon, `AVECO/FIFO` katta harf | G-a |
| T-090 | o'rta | B-080, C-039 | TASDIQ | `providerFiscalizationOff` saqlanmaydi | G-a, G-b, G-c |
| T-091 | o'rta | B-082, C-087 | TASDIQ | OCR tasdiq ruxsati `purchases.create` ↔ `purchases.receive` + `ai.ocr.use` | G-a |
| T-092 | o'rta | B-083 | TASDIQ | Yetkazib beruvchi to'lovi formasi `payment.source`, `shift_id` yo'q | G-a |
| T-093 | o'rta | B-084, C-086 | TASDIQ | Yetkazib beruvchiga qaytarish formasi to'liq emas; create/post bitta ruxsat bilan | G-a |
| T-094 | o'rta | B-085, C-074, B-147g | TASDIQ | `nameRu` ruxsati `prices.edit` ↔ `catalog.manage`; 200 ↔ 255 | G-a |
| T-095 | o'rta | B-087, C-165 | TASDIQ | Chekdan e-faktura ruxsati `einvoice.sign` ↔ `einvoice.create` | G-a |
| T-096 | o'rta | B-089 | TASDIQ | Risk-flag dialogida `note` yo'q | G-a |
| T-097 | o'rta | B-090 | TASDIQ | Qurilma bekor qilish dialogida `reason`, `confirm_pending_loss` yo'q | G-a |
| T-098 | o'rta | B-091 | TASDIQ | `attachments.kind='import'` faqat `catalog.manage` — Buxgalter BO-24 da 403 | G-c |
| T-099 | o'rta | B-093 | TASDIQ | BO-19 manbasida `GET /billing/subscription`, `/billing/payments` yo'q | G-a |
| T-100 | o'rta | B-094, C-166 | TASDIQ | PLU eksport ruxsati `labels.print` ↔ `catalog.manage` | G-a |
| T-101 | o'rta | B-095, C-078, B-147a | TASDIQ | Signup ① dan keyin chaqiriladi; `owner_name`, `legal_form`, `accepted_terms_version` saqlanmaydi | G-a, G-c |
| T-102 | o'rta | B-096 | TASDIQ | Hisobdan chiqarish `gift_kind`/`promo_order_ref` formada yo'q | G-a |
| T-103 | o'rta | B-097, C-088, B-147k | TASDIQ | POS-08 `discrepancyReason` ustunsiz; `receivedQty ≥0`; PO dan standartlar | G-a, G-b, G-c |
| T-104 | o'rta | B-098, C-083 | TASDIQ | `GET /fiscal-receipts` Kassirga yopiq (POS-04) | G-c |
| T-105 | o'rta | B-099 | TASDIQ | `debt_settlement` chekini qidirish/qayta chop etish yo'li yo'q | G-a, G-c |
| T-106 | o'rta | B-100 | TASDIQ | `delivery='electronic'` ni hech qaysi voqea olib bormaydi | G-a, G-c |
| T-107 | o'rta | B-101, C-082 | TASDIQ | Z-hisobot endpointi Kassirga yopiq | G-c |
| T-108 | o'rta | B-102, C-084 | TASDIQ | POS-06 `POST /einvoices` chaqiradi — Kassirda ruxsat yo'q | G-a, G-c |
| T-109 | o'rta | B-103 | TASDIQ | POS-05 qidiruvidan qatorlar olinmaydi | G-a |
| T-110 | o'rta | B-106 | TASDIQ (qisman) | "Sanashni boshlash" endpointi ekranda ko'rsatilmagan | G-a |
| T-111 | o'rta | B-110 | TASDIQ | QT-PERM-07 `approved`+`consumed_at`; xato kodi ikki xil | G-c, G-e |
| T-112 | o'rta | B-111 | TASDIQ | QT-M15-01 `cash_moves.direction` — ustun yo'q | G-e |
| T-113 | o'rta | C-034 | TASDIQ (qisman) | Blok konstantasi `OFFLINE_FISCAL_BLOCK_HOURS` ↔ #43 `OFFLINE_BLOCK_HOURS` | G-c, G-d |
| T-114 | o'rta | C-035 | TASDIQ | `block` rejimida "offline siyosati taklif qilinadi" — #62 ga zid | G-c |
| T-115 | o'rta | C-036 | TASDIQ | `outbox_jobs.kind` ro'yxatlari 11/12/21 da farqli | G-b, G-d |
| T-116 | o'rta | C-037 | TASDIQ | 03/12: e-TTN yo'qligi "ogohlantirish", plate "send'da" ↔ 19 | G-a, G-b, G-c |
| T-117 | o'rta | C-038, B-146m | TASDIQ | `card_type` standarti `personal` ↔ "har safar so'raladi" (F-06) | G-a, G-c, G-d |
| T-118 | o'rta | C-041 | TASDIQ | `credit_type` aralash to'lovda ikki chek — bitta `receipt_seq` | G-c |
| T-119 | o'rta | C-042 | TASDIQ | `FiscalPort.issue_credit_payment()` ↔ `register_sale(kind='debt_settlement')` | G-c, G-d |
| T-120 | o'rta | C-043 | TASDIQ | Hisobdan chiqarilgan qarzga to'lov `amount ≤ receivable_balance` bilan doim rad (D-04 §2) | G-b, G-c |
| T-121 | o'rta | C-044 | TASDIQ | Lokaut eksporti "SMS OTP" (#34 — Telegram birinchi); kim eksport qiladi | G-c, G-d |
| T-122 | o'rta | C-045 | TASDIQ | 06:66 "qo'lda MXIK" — markirovkali tovar kodsiz sotiladi | G-a |
| T-123 | o'rta | C-046 | TASDIQ | `restock=false` qaytarishda tovar sotuvga chiqishi mumkin (D-20) | G-a, G-b, G-c |
| T-124 | o'rta | C-047 | TASDIQ | Manfiy qoldiq/`pending_cost` va AVECO `qty≤0` aniqlanmagan (D-21) | G-a, G-b |
| T-125 | o'rta | C-051 | TASDIQ | Storno "teskari belgili nusxa" — `ledger_entries.amount > 0` | G-b, G-d |
| T-126 | o'rta | C-052 | TASDIQ | Aylanma solig'i bazasi, tamaki belgisi, YaTT stavkasi, stavkalar seed'i | G-b |
| T-127 | o'rta | C-053 | TASDIQ | Ichki 0102 bilan ledger farqi (qarzga sotuv vaqti) ko'rsatilmagan | G-a, G-b |
| T-128 | o'rta | C-054 | TASDIQ | Boshlang'ich qoldiq `go_live_date − 1` ↔ `ledger_adjustments` faqat joriy davr | G-b, G-c |
| T-129 | o'rta | C-055 | TASDIQ | BP-04 "Omborchi — ichki kirim hujjati" mavjud emas | G-a |
| T-130 | o'rta | C-056 | TASDIQ | Ko'chirish qabulida ortiqcha uchun provodka yo'q | G-c |
| T-131 | o'rta | C-057 | TASDIQ | Risk-flag va recost tuzatishlari `doc_type`/`entry_date`/storno/tartib | G-b, G-c, G-d |
| T-132 | o'rta | C-058 | TASDIQ (qisman) | Yopilgan davrdagi hujjatni bekor qilish — 13 storno joriy davrda, 20 `PERIOD_CLOSED` | G-b, G-c |
| T-133 | o'rta | C-059 | TASDIQ | #23(5) "qaytarish faqat online" ↔ boshqa fayllar (F-01) | G-a |
| T-134 | o'rta | C-061 | TASDIQ | FIFO↔AVECO almashtirish algoritmi yo'q (D-21 §4) | G-b, G-c |
| T-135 | o'rta | C-062, A-019 | TASDIQ | 26 dagi 1C vaqtinchalik standartlari 33 da yo'q nomlar bilan | G-a |
| T-136 | o'rta | C-064 | TASDIQ | "Bosqich 7 ni faqat #105 bloklaydi" ↔ #132/#133 BLOK; "Bosqich A" | G-a, G-f |
| T-137 | o'rta | C-065 | TASDIQ | `uuid5` katalog nomlari §8.1 da boshqacha | G-f |
| T-138 | o'rta | C-066 | TASDIQ | `onec_ref_create_requests` qayta urinish va tartib | G-f |
| T-139 | o'rta | A-022, C-067, C-123 | TASDIQ | Must US uchun QT yo'q: US-M01-07, US-M17-03, US-M19-04, US-M19-14 | G-a, G-e |
| T-140 | o'rta | C-068 | TASDIQ | Muddati o'tgan o'qish vazifasi: "qator qayta queued" ↔ "yangi vazifa" | G-f |
| T-141 | o'rta | C-070 | TASDIQ | Lokal API sxemalari, port, xato shakli yo'q (D-22) | G-d |
| T-142 | o'rta | C-073 | TASDIQ | 17 "faqat Egasi" misolida `platform.admin` | G-c |
| T-143 | o'rta | C-075 | TASDIQ | 9 ta endpointda ruxsat ko'rsatilmagan | G-c |
| T-144 | o'rta | C-076 | TASDIQ | Obuna summasi, davr oxiri, `trial` tugashi, `closed` triggeri (D-23, F-04, F-05) | G-a, G-b, G-c |
| T-145 | o'rta | C-077 | TASDIQ | "Kod SMS orqali yuborildi" doim | G-a |
| T-146 | o'rta | C-079 | TASDIQ | `ai.ocr_enabled=false` javobi aniqlanmagan | G-c |
| T-147 | o'rta | C-080 | TASDIQ | 26 #21: AI-10 "MVP'da" ↔ #16 | G-a |
| T-148 | o'rta | C-081 | TASDIQ | 30: lokaut eksport endpointi butunlay MVP'dan keyin | G-a, G-f |
| T-149 | o'rta | C-085, C-174 (qism) | TASDIQ | `counterparties` endpoint ruxsatlari 18 ↔ 19 farqli | G-c |
| T-150 | o'rta | C-094 | TASDIQ | BO-17 da `taxType` yo'q | G-a |
| T-151 | o'rta | C-095 | TASDIQ | `shifts.status='closing'` ga yo'l yo'q; inventarizatsiya `posted→cancelled`; qarz hujjatlarida `/cancel`/`GET` yo'q | G-a, G-b, G-c |
| T-152 | o'rta | C-096 | TASDIQ | Aralash to'lovda QQS qatorining Dt hisobi | G-b |
| T-153 | o'rta | C-101 | TASDIQ | Narx farqi foizi formulasi yo'q | G-c |
| T-154 | o'rta | C-103 | TASDIQ | FM imzolagan chek `RECEIPT_SEQ_CONFLICT` bilan rad (D-05 §5) | G-a, G-c |
| T-155 | o'rta | C-104 | TASDIQ | Inventarizatsiyada sanalmagan qatorlar; 19:688 zid jumla | G-c |
| T-156 | o'rta | C-105 | TASDIQ | Javobgarsiz kamomad 19 "5910→9430" ↔ 13 `Dt 9430` | G-c |
| T-157 | o'rta | C-107 | TASDIQ | `total_sales`, `revenue`, `discounts` ta'rifi yo'q | G-c |
| T-158 | o'rta | C-108 | TASDIQ | YaTT e-faktura qoidasi modelda yo'q (F-11) | G-a |
| T-159 | o'rta | C-109 | TASDIQ | "Nasiya/В долг" to'lov shakli yorlig'i — CHECK'da yo'q | G-a |
| T-160 | o'rta | C-110 | TASDIQ | "QQS ixtiyoriy 6%" manbasiz | G-a |
| T-161 | o'rta | C-111 | TASDIQ | 26 #145 `discount_posting` standarti `net` ↔ `gross_9050` | G-a |
| T-162 | o'rta | C-112 | TASDIQ | "Oyning 10-sanasigacha" manbasiz | G-a |
| T-163 | o'rta | C-113 | TASDIQ | M18 bildirishnomalari M18 qurilishidan oldin talab qilinadi | G-a |
| T-164 | o'rta | C-114 | TASDIQ | Offline ko'chirish/sanash testlari B2 da, sync B3 da; QT-M05-05 Android | G-a, G-e |
| T-165 | o'rta | C-115 | TASDIQ | e-TTN stub `registered` qilishi aytilmagan | G-a |
| T-166 | o'rta | C-116 | TASDIQ | B1 "haqiqiy SMS provayder" ↔ Eskiz shartnomasi B6 | G-a |
| T-167 | o'rta | C-117 | TASDIQ | OV sertifikat muddati #38 ↔ 26/21 (F-10) | G-a, G-d |
| T-168 | o'rta | C-118 | TASDIQ | Server yorliq PDF bosqichi #54 ↔ 27 (F-03) | G-a |
| T-169 | o'rta | C-119 | TASDIQ | Uzum B3 da yo'q, MVP'dan keyingi ro'yxatda (F-02) | G-a |
| T-170 | o'rta | C-120 | TASDIQ | B4 da `debt_writeoffs`/shubhali qarz vazifasi yo'q | G-a |
| T-171 | o'rta | C-121 | TASDIQ | B5 DoD real CRPT/hamkor javobiga bog'liq | G-a |
| T-172 | o'rta | C-122 | TASDIQ | B0 DoD da QT-ID va CI/migratsiya/zaxira mezonlari yo'q | G-a |
| T-173 | o'rta | A-001 | TASDIQ | 01 dagi eskirgan `OSn` ko'rsatkichlari | G-a |
| T-174 | o'rta | A-003, C-176 | TASDIQ | `18` §15a mavjud emas (→ §14a); 27 dagi `DB-0x` ID'lari | G-a |
| T-175 | o'rta | A-009, C-163 | TASDIQ | 12 DDL izohlarida eski fayl raqamlari | G-b |
| T-176 | o'rta | A-018 | TASDIQ | Mavjud bo'lmagan `34-dokon-agenti.md` ga havola | G-a, G-b, G-f |
| T-177 | o'rta | A-020 | TASDIQ | 26 "yangi bandlar #106 dan" — #170 gacha band | G-a |
| T-178 | o'rta | A-021 | TASDIQ | 23 "README qarori" — `kod-uchun` dan tashqari manba | G-d |

### 4.3 Kichik (111)

| T | Daraja | Manbalar | Verdikt | Muammo | Guruhlar |
|---|---|---|---|---|---|
| T-179 | kichik | A-002 | TASDIQ (qisman) | 26:103 `/OS6`, `/OS3` qoldiqlari | G-a |
| T-180 | kichik | A-004 | TASDIQ | `14` §1.4 → `15` §1.4 | G-a |
| T-181 | kichik | A-005 | TASDIQ | 19:266 `§attachments` → `§12` | G-c |
| T-182 | kichik | A-006 | TASDIQ | 23:226 "(13-0 §8)" | G-d |
| T-183 | kichik | A-007 | TASDIQ | 29:14 `10 §Qoidalar` → `00` | G-a |
| T-184 | kichik | A-008 | TASDIQ | 07:957 "06 §1.3 Won't" → 05 | G-a |
| T-185 | kichik | A-010 | TASDIQ | 12:4016 `15 §19` | G-b |
| T-186 | kichik | A-011 | TASDIQ | `14 §16.1.N` sarlavhalari yo'q | G-c |
| T-187 | kichik | A-012 | TASDIQ | `08 §0.1` sarlavhasi yo'q | G-a, G-d |
| T-188 | kichik | A-013 | TASDIQ | 26: `05 §4.2/§4.3/§4.4` | G-a |
| T-189 | kichik | A-014 | TASDIQ | `12 §7.12` | G-a |
| T-190 | kichik | A-015 | TASDIQ | 20/15 prefiksisiz `§16.5`, `§18.1` | G-c |
| T-191 | kichik | A-016 | **RAD** | 12 §2.11 `§` havolalari — 12:2486 kirish izohi allaqachon 33 ekanini aytadi | — |
| T-192 | kichik | A-017 | TASDIQ | "31 M19 §14" → 33 §14 | G-a, G-f |
| T-193 | kichik | A-023 | TASDIQ | `QT-AI-GUARD-01` yo'q, tartib buzilgan | G-e |
| T-194 | kichik | A-024 | TASDIQ | 00 da sarlavha bloki yo'q | G-a |
| T-195 | kichik | A-025 | TASDIQ | "endi/ko'chirildi/qo'shildi" tarix qoldiqlari | G-a, G-c |
| T-196 | kichik | A-026 | TASDIQ | 12:3867 kirill "ролига" | G-b |
| T-197 | kichik | A-027 | TASDIQ | 32:377 eskirgan branch nomi | G-d |
| T-198 | kichik | A-028 | TASDIQ | 09 `texnik/` prefiksi | G-a |
| T-199 | kichik | A-029 | TASDIQ | 23:366 `postgres:17-alpine` ↔ PG16 | G-d |
| T-200 | kichik | A-030 | TASDIQ | 14:622 #3 → #14 | G-c |
| T-201 | kichik | A-031 | TASDIQ | `spec/README.md` manba sifatida | G-a, G-c |
| T-202 | kichik | B-113 | TASDIQ | `import_jobs` `total_rows/result` null ↔ `NOT NULL DEFAULT` | G-c |
| T-203 | kichik | B-114 | TASDIQ | `Product` javobida `marking_group_code` yo'q | G-c |
| T-204 | kichik | B-115 | TASDIQ | `vat_rate` "majburiy" ↔ "kamida bittasi" | G-c |
| T-205 | kichik | B-116 | TASDIQ | `factura_type` ro'yxatida `/…` | G-c |
| T-206 | kichik | B-117 | TASDIQ | `params.resource` ko'plik/birlik | G-c |
| T-207 | kichik | B-118 | TASDIQ | Yorliq shabloni javobida `code` yo'q | G-c |
| T-208 | kichik | B-119 | TASDIQ | `/platform/*` 9 → 10 | G-c |
| T-209 | kichik | B-120 | TASDIQ | "75 ta `ONEC_*`" → 81 | G-c |
| T-210 | kichik | B-121 | TASDIQ | `import_id` "ustun bilan bir xil" izohi | G-c |
| T-211 | kichik | B-122 | TASDIQ | Telegram ulanishi "o'chiriladi" ↔ `revoked_at` | G-c |
| T-212 | kichik | B-123 | **RAD** | Kassa harakati bekor qilishga `PERIOD_CLOSED` qo'shish — T-132 qaroriga zid | — |
| T-213 | kichik | B-124 | TASDIQ | Eksport `export_id/download_url` ↔ 17 `job_id/file_url` | G-c |
| T-214 | kichik | B-125 | TASDIQ | "Faqat Egasi" endpointlarida `OWNER_ONLY` yo'q | G-c |
| T-215 | kichik | B-126 | TASDIQ | Rol "nomi/tavsifi" — tavsif ustuni yo'q | G-c |
| T-216 | kichik | B-129 | TASDIQ (qisman) | `pending_events` → `outbox_pending_count` | G-c |
| T-217 | kichik | B-130 | TASDIQ | Ombor/kassa ro'yxati sahifalash shakli | G-c |
| T-218 | kichik | B-131 | TASDIQ | `payment_org_commission_account` qamrovi | G-c |
| T-219 | kichik | B-132 | TASDIQ | `discount_posting` standarti yozilmagan | G-c |
| T-220 | kichik | B-133 | TASDIQ | `negative_stock_policy`, `ai_training_consent` ni o'zgartirish yo'li | G-c |
| T-221 | kichik | B-134 | TASDIQ | `fiscal_partner`, `eimzo` sirlarini o'rnatish yo'li | G-c |
| T-222 | kichik | B-135 | TASDIQ | `activity_type` o'zgarishi, bir oyda ikki marta | G-c |
| T-223 | kichik | B-136 | TASDIQ | `published_at` turi | G-c |
| T-224 | kichik | B-137 | TASDIQ | W-29 `warnings` shakli | G-f |
| T-225 | kichik | B-138 | TASDIQ | `batch_id` → `last_batch_id` | G-f |
| T-226 | kichik | B-139 | TASDIQ | `actor`, `paired_by` shakli | G-f |
| T-227 | kichik | B-140 | TASDIQ | Cursor ro'yxatida mavjud bo'lmagan yo'llar | G-f |
| T-228 | kichik | B-141 | TASDIQ (qisman) | M19 buyruq yo'llari uchun 17 §2 istisnosi yo'q (yo'l o'zgarmaydi) | G-c |
| T-229 | kichik | B-142 | TASDIQ | "preview'siz" izohi ostida `preview` | G-f |
| T-230 | kichik | B-143 | TASDIQ | W-55/ExportItem/legenda maydonlari | G-a, G-f |
| T-231 | kichik | B-144 | TASDIQ | 07 `agent_name` ↔ W-04 `name` | G-a |
| T-232 | kichik | B-145a | TASDIQ | `denied`/`access_denied` hech qachon o'rnatilmaydi | G-a, G-b, G-f |
| T-233 | kichik | B-145b, C-152 | TASDIQ | 14:126 lokaut ro'yxatida A-02 yo'q | G-c |
| T-234 | kichik | B-145d, B-145g, B-145h | TASDIQ | 14:42 `oauth_clients.name`; A-05 vaqtlar; A-01 `os_version`/`pc_name` | G-c, G-f |
| T-235 | kichik | B-146a | TASDIQ | `DEPENDENCY_NOT_SYNCED` 18 da yo'q | G-c |
| T-236 | kichik | B-146b, B-146c, B-146h | TASDIQ | 16 misollari: `+05:00`, `device_id/actor_user_id`, xom `created_at` joyi | G-c |
| T-237 | kichik | B-146d | TASDIQ | 16:267 "avans" cheki | G-c |
| T-238 | kichik | B-146e, B-146f | TASDIQ | 17 katalog izohlari: `DEBT_LIMIT_EXCEEDED` offline, `PIN_INVALID` | G-c |
| T-239 | kichik | B-146g, B-146i, B-146j, B-146k, B-146l | TASDIQ | 18 mayda: `marking_offline`, `"25"`, `stock/cash_moves`, havola, `without_receipt` | G-c |
| T-240 | kichik | B-147b–f, h–j, l–p, r; C-164, C-167, C-168, C-169 | TASDIQ | 07 mayda tafovutlar (ruxsat, nom, oqim) | G-a |
| T-241 | kichik | B-147s, B-147t, B-147u | TASDIQ | 31 fixture'lari va `related_doc` | G-e |
| T-242 | kichik | B-147v, B-147w, B-147x | TASDIQ | 13 mayda: `doc_type`, `last_purchase_cost`, `customs_vat_base` | G-b, G-e |
| T-243 | kichik | B-147z, B-147aa | TASDIQ | 11 mayda: `valuation_method_history` istisno, DDL nomlari | G-b |
| T-244 | kichik | C-124 | TASDIQ | 21:116 46 soat matni | G-d |
| T-245 | kichik | C-125 | TASDIQ | 06:41 blok ro'yxati; BO-06 `fiscal-blocked` | G-a |
| T-246 | kichik | C-126 | TASDIQ | Offline statik UzQR server tekshiruvi | G-c |
| T-247 | kichik | C-127 | TASDIQ | 46 soat modali ikki ekranda | G-a |
| T-248 | kichik | C-128 | TASDIQ | `qrType` default "Tenant sozlamasi" | G-a |
| T-249 | kichik | C-129 | TASDIQ | 18:313 UNIQUE `tenant_id`siz | G-c |
| T-250 | kichik | C-131 | TASDIQ | 26:65 ish haqi faqat `Dt 9420` | G-a |
| T-251 | kichik | C-132 | TASDIQ | 13:566 "1C ga 0000 → 000" | G-b |
| T-252 | kichik | C-133 | TASDIQ | 03:362/366 eski havolalar | G-a |
| T-253 | kichik | C-134 | TASDIQ | `bank_settlements` holat mashinasi 11 da yo'q | G-b |
| T-254 | kichik | C-135 | TASDIQ | Inkassa testi yo'q | G-e |
| T-255 | kichik | C-136 | TASDIQ (qisman) | 13 "BP-01…12"; §2.25 tartibi/darajasi | G-b |
| T-256 | kichik | C-137 | TASDIQ | QQS krediti proporsiyasi yaxlitlash | G-b |
| T-257 | kichik | C-138 | TASDIQ | `gross_9050` 1a-qator 1 tiyin | G-b |
| T-258 | kichik | C-139 | TASDIQ | FIFO tartib kaliti | G-b |
| T-259 | kichik | C-141 | TASDIQ | "AI risk-scoring" — davlat xavf-baholashi | G-a |
| T-260 | kichik | C-142 | TASDIQ | "QQS hisoboti 15-sanagacha" manbasiz | G-b |
| T-261 | kichik | C-143 | TASDIQ | 05:179 BHM raqami | G-a |
| T-262 | kichik | C-144 | TASDIQ | "Jarima 2–20%" manbasiz | G-a |
| T-263 | kichik | C-145 | TASDIQ | 29: e-TTN "o'z omborlari orasida ham" — faqat avtotransportda | G-a |
| T-264 | kichik | C-146 | TASDIQ | 19:969 26 #40 → #117 | G-c |
| T-265 | kichik | C-147 | TASDIQ | `duplicate` xato sinfi §12 da yo'q | G-f |
| T-266 | kichik | C-149 | TASDIQ (qisman) | `V82.COMConnector` tekshiruvi | G-f |
| T-267 | kichik | C-150 | TASDIQ | `orp_negative_payment` manfiy `Оплата` qatori | G-f |
| T-268 | kichik | C-151 | TASDIQ | QT-M19-04 ↔ P-05 (→ P-13) | G-e |
| T-269 | kichik | C-154 | TASDIQ | 26 #134 "33 §10" | G-a |
| T-270 | kichik | C-155 | TASDIQ | Dispetcher izohi "phase ichida" | G-f |
| T-271 | kichik | C-156 | TASDIQ | `fiscal.zreport` natijasi | G-d |
| T-272 | kichik | C-157 | TASDIQ | M07 da Menejer "Y, T" | G-a |
| T-273 | kichik | C-158 | TASDIQ | `billing.manage` "Tarif tanlash" | G-c |
| T-274 | kichik | C-159 | TASDIQ | Unit-iqtisod/AI xarajati raqamlari farqli | G-a, G-d |
| T-275 | kichik | C-160 | TASDIQ | #44 "yagona 15 daq" ↔ admin-bff/`sync.drain` 5 daq | G-a |
| T-276 | kichik | C-161 | TASDIQ | `ai.cross_border_enabled` → `settings.ai_cross_border_enabled` | G-c |
| T-277 | kichik | C-162 | TASDIQ | `mypy app` → `mypy --strict app` | G-d |
| T-278 | kichik | C-171 | TASDIQ | 17:148 `review` → `submit-for-review` | G-c |
| T-279 | kichik | C-172 | TASDIQ | `GET/POST /admin/users` 14 §18.2 da aniqlanmagan | G-c |
| T-280 | kichik | C-173 | TASDIQ | 07 validatsiya farqlari; 14 §4 da parol siyosati yo'q | G-a, G-c |
| T-281 | kichik | C-174 | TASDIQ | 30 matritsasi noto'g'ri qatorlari | G-a |
| T-282 | kichik | C-175 | TASDIQ | BO-05 chegirma qoidalari MVP belgisi, maydonlar; ishlatilmaydigan kodlar | G-a, G-c |
| T-283 | kichik | C-177 | TASDIQ | 27 "A-01" signup uchun, "E-32" | G-a |
| T-284 | kichik | C-178 | TASDIQ | Signup aksepti B0 da, signup B1 da | G-a |
| T-285 | kichik | C-179 | TASDIQ | "10 daqiqada ro'yxat + 500 tovar" QT'siz; 03 "2 daqiqa" | G-a, G-e |
| T-286 | kichik | C-180 | TASDIQ | B5 DoD qamrovi; QT-M10-07 bosqichi | G-a |
| T-287 | kichik | C-181 | TASDIQ (qisman) | 27 bloklash ustuni 26 Jadval B bilan farqli | G-a |
| T-288 | kichik | C-182 | TASDIQ | US-M08-08, US-M03-02 ikki marta; QT-M09-09 US ustuni | G-a, G-e |
| T-289 | kichik | C-183 | TASDIQ | "FiscalPort+Fake — Bosqich 0 dan"; QT-SUB sarlavhasi | G-d, G-e |

---

## 5. Rad etilganlar va qisman qabul qilinganlar

- **T-191 (A-016) — RAD.** 12:2486 (§2.11 kirish) "DDL izohlaridagi `§` havolalari — `33-1c-integratsiya.md` bo'limlari" deb aniq yozgan; har izohga "33" qo'shish shart emas.
- **T-212 (B-123) — RAD.** T-132 qarori: hujjatni bekor qilish yopilgan davrda ham ruxsat, storno joriy ochiq davr sanasida (13 §5.1/§5.2) — `cancel` endpointlariga `PERIOD_CLOSED` qo'shilmaydi, aksincha 20 dagi `cancel` xatolaridan olib tashlanadi.
- **B-016 (T-014) — qisman.** Ekran va API mos emasligi tasdiqlandi; "ekranga E-IMZO qadami qo'shish" varianti rad: 03/07/13 bo'yicha tuzatish my.soliq.uz kabinetida, tizim faqat qayd etadi (D-10).
- **B-141 (T-228) — qisman.** `POST /onec-agents/pair` — RFC 8628 kodni tasdiqlash amali; yo'l o'zgarmaydi, faqat 17 §2 ga buyruq yo'llari istisnosi yoziladi.
- **B-072 + C-049 (T-083), B-106 (T-110), C-034 (T-113), C-058 (T-132), A-002 (T-179), B-129 (T-216), C-136 (T-255), C-149 (T-266), C-181 (T-287)** — muammo tasdiqlandi, tuzatish manba taklifidan torroq yoki aniqroq (§6 da).

---

## 6. Amallar — guruhlar bo'yicha

Har amal: `[T-xxx]` — bo'lim/qator — nima qilinadi. Bir faylga tegishli amallar ketma-ket.

### G-a — `00`–`09`, `26`, `27`, `29`, `30`

#### `00-README.md`
- [T-194] 1-qatordan keyin sarlavha bloki: "**Maqsad:** kod uchun spec'ga kirish nuqtasi va o'qish tartibi. · **Kim uchun:** hammasi. · **Bog'liq fayllar:** 01–34. · **Holat:** joriy, 2026-10-16."
- [sanoq] Qarorlar oralig'i "#1–#65" → "#1–#70". QT soni tilga olingan bo'lsa — G-e tugatgach `31` §0 dagi yakuniy son.

#### `01-qarorlar.md`
- [T-173] "Ta'sir qiladigan fayllar" ustunidagi barcha `OSn` ko'rsatkichlari (24, 38, 40, 41, 55, 56, 74, 75, 76, 90, 91, 100, 101-qatorlar) olib tashlanadi. Mavzu shu fayl bo'limida yozilgan bo'lsa — bo'lim raqami bilan almashtiriladi (masalan `` `17` OS2 `` → `` `17` §15.1 ``, `` `10` OS3 `` → `` `10` §1 ``), mavzu 26 da yopilgan bo'lsa — `` `26` #N ``, aks holda faqat fayl raqami qoladi.
- [T-195] #10 (13-qator): "M01 to'lov turlariga … qo'shildi" → "M01 to'lov turlarida **UzQR (bank yagona QR)** bor — …" (qolgan matn o'zgarmaydi).
- [T-133, F-01] #23, tavsiya (5): "offline ko'chirish ruxsat, qaytarish faqat online" → "offline ko'chirish ruxsat; markirovkasiz tovarni qaytarish offline ruxsat (limitdan oshsa lokal Menejer/Egasi PIN), markirovkali tovarni qaytarish faqat online (#17, #62)". Asos ustuniga: "; (5)-band talqini — mustaqil tekshiruv standarti F-01, asoschi ko'rib chiqadi".
- [T-187] #26: `` `08-dizayn-tizimi.md` §0.1 `` → `` `08-dizayn-tizimi.md` §0 (1-band) ``.
- [T-167, F-10] #38: "Authenticode **OV kod-imzolash sertifikati** Bosqich 7 dan oldin olinadi (26 #105)" → "Authenticode **OV kod-imzolash sertifikati** — lokal fiskal ko'prik tanlansa Bosqich 5/6 pilot tarqatishidan oldin, aks holda Bosqich 7 dan oldin (26 #105)". Asos: "; muddat — F-10, asoschi ko'rib chiqadi".
- [T-275] #44 oxiriga: "Istisnolar: `admin-bff` (ADM-01) tokeni va `sync.drain` scope tokeni — 5 daqiqa (`14` §16.4, §18.1)."
- [T-180] #56 (24-qator): `` `14` §1.4 `` → `` `15` §1.4 ``.
- [T-168, F-03] #54: "server yorliq PDF — faqat >200 yorliq yoki iOS uchun (Bosqich 2 oxiri)" → "server yorliq PDF — faqat >200 yorliq yoki iOS uchun (Bosqich 6, M09 yorliq chop etish bilan birga; `outbox_jobs(kind='label_pdf')`)". Asos: "; bosqich — F-03, asoschi ko'rib chiqadi".
- [T-189] #54: `` `12` §7.12 `` → `` `12` §7 (12-band) ``.
- [T-176] #60: "`34-1c-agent.md` `34-dokon-agenti.md` ga kengaytiriladi (hozircha 34 da "Kengaytirish" bo'limi)" → "Fiskal ko'prik, printer va tarozi imkoniyatlari — `34-1c-agent.md` §14 «Do'kon agenti kengaytmasi»; agent infratuzilmasi (ulash, token, vazifa navbati) — Bosqich 5 (qaror #66)".
- [T-117, F-06] #64: "`card_type` (`personal | corporate | social | unknown`, standart so'raladi)" → "`card_type` (`personal | corporate | social | unknown`; standart qiymat yo'q — kassir har karta to'lovida terminal chekiga qarab tanlaydi; `unknown` chekda «Noma'lum / Не определён»)". Asos: "; standart — F-06, asoschi ko'rib chiqadi".
- [T-022] Yangi qator **#66** ("Arxitektura va texnologiya" jadvali oxiriga): "**Do'kon agenti infratuzilmasi — Bosqich 5**: agent ro'yxati va ulash (RFC 8628), `onec-agent` OAuth mijozi (`client_credentials` + `private_key_jwt`, token 10 daqiqa), A-API (A-02 dan tashqari), imzoli vazifa navbati, avto-yangilanish — Bosqich 5 da quriladi (migratsiya `0028 store_agent`); jadvallar `onec_agents`, `onec_agent_tasks`, `onec_task_results`, `auth.onec_device_authorizations` — agentning umumiy registri; 1C ga xos qism — Bosqich 7 (`0029 onec_integration`). Xizmat vazifalari (`fiscal.status`, `fiscal.resend_unsent`, `fiscal.zreport`, `print.raw`, `scale.plu_upload`) — `purpose='device_service'`, `base_id` NULL, faqat agent `capabilities` da yoqilgan oila uchun. Lokal ko'prik kassasi agentga `cash_registers.fiscal_agent_id`/`fiscal_local_device_id` orqali bog'lanadi. Tarozi PLU yuklash — MVP'dan keyin." Asos: "Mustaqil tekshiruv (`research_notes/mustaqil-tekshiruv/04-tuzatish-rejasi.md` D-01), 2026-10-16". Ta'sir: `10`, `12`, `21` §16, `23` §4.2, `27`, `33` §5.15/§9, `34` §14, `07` BO-12/BO-14.
- [T-023, T-024, T-025] Yangi qator **#67** ("Fiskal va soliq"): "**Qarz to'lovi cheki — kassa va offline**: (a) `debt_payments.method='bank'` — faqat back-office (BO-06), kassasiz, fiskal chek yo'q; boshqa usullar — faqat POS `debt_payment.created` (offline ham), `cash_register_id`/`shift_id`/`receipt_seq` majburiy, chek shu kassa FM'ida va shu kassaning 48 soat hisobida (#43); (b) allokatsiya va chek qatorlari — umumiy deterministik funksiya (`shared/lib/debt-allocation`, test-vektorlar), qurilma lokal `customers.open_debt_docs` keshidan hisoblaydi, server qayta hisoblaydi va farqni `sync_exceptions` ga yozadi (rad etmaydi); (c) offline qarz to'lovida qarzdan ortiq summa qabul qilinadi — ortig'i `Kt 6310`, Egasiga xabar; online/REST'da #45 qoidasi (rad) amal qiladi." Asos: "Mustaqil tekshiruv (04, D-03/D-04; F-07, F-08), 2026-10-16 — asoschi ko'rib chiqadi; bank to'lovi cheki — 26 #171". Ta'sir: `12`, `13` §2.14, `16` §1, `18` §12, `07` POS-13/BO-06, `31`.
- [T-026, T-154] Yangi qator **#68**: "**POS voqeasida fiskal natija**: lokal ko'prik rejimida `sale.created`/`return.created`/`debt_payment.created` payload'i `fiscal_result {fm_terminal_id, fm_receipt_seq, fiscal_sign, qr_url, fiscal_at}` ni olib keladi, server chekni `fiscalized` qiladi; OFD tasdig'i (`ofd_acked_at`) agentning `fiscal.status` natijasidagi `acked[]` dan yoziladi. FM imzolagan chek `RECEIPT_SEQ_CONFLICT` bilan rad etilmaydi — server `receipt_seq` ni qayta raqamlaydi va `sync_exceptions` ga yozadi." Asos: "Mustaqil tekshiruv (04, D-05), 2026-10-16". Ta'sir: `16`, `18` §4/§7/§12, `21` §1/§16, `24`.
- [T-028] Yangi qator **#69**: "**Yopilgan davrga kech kelgan POS voqealari**: `/sync/push` voqealari `PERIOD_CLOSED` bilan rad etilmaydi; registr yozuvlari birinchi ochiq davrda (`analytics.correction_of_period` = asl oy), `sync_exceptions(kind='late_in_closed_period')`; davr yopish tayyorligida sinxronlanmagan faol qurilmalar — bloker (`devices_unsynced`); faqat eng eski ochiq oy yopiladi." Asos: "Mustaqil tekshiruv (04, D-06; F-09), 2026-10-16 — asoschi ko'rib chiqadi". Ta'sir: `13` §5.1, `16` §3.4, `18`, `20` #15/#16, `31`.
- [T-144] Yangi qator **#70** ("Mahsulot va narx"): "**Obuna to'lovi va holatlari**: oy — `99 000 + 39 000 × qo'shimcha kassa`; yil — `950 400 + 39 000 × 12 × qo'shimcha kassa` (−20% faqat asosiy tarifga); yangi davr oxiri = `max(joriy davr oxiri, to'lov vaqti) + 1 oy | 12 oy`; `trial` (30 kun) → `grace` (24 soat) → `restricted`; avtomatik `closed` yo'q — faqat platforma admini (US-M17-05 bilan, MVP'dan keyin)." Asos: "Mustaqil tekshiruv (04, D-23; F-04, F-05), 2026-10-16 — asoschi ko'rib chiqadi". Ta'sir: `11` §8, `12` (`billing_payments.amount_breakdown`), `14` §16, `20` #61, `07` BO-19.

#### `02-rollar-va-ssenariylar.md`
- [T-262] 41-qator "jarima 2–20% aylanma" → oxiriga "(raqobatchi sharhlari, qonuniy manba tasdiqlanmagan)".
- [T-201] 112, 255-qator: manba `spec/README.md` → mos `01` qarori (offline-first — "qaror #21, #43"; boshqalari mazmuniga ko'ra) yoki `research_notes/…` manbasi.
- [T-162] 200-qator "oyning 10-sanasigacha" → "har oyning 10-sanasi — ichki eslatma sanasi (sozlanadi), qonuniy muddat emas".
- [T-272] 219-qator M07 da Menejer "Y, T" → "Y" (`purchases.receive/post/pay` Menejerda yo'q — `15` §2.2).

#### `03-modullar-talablari.md`
- [T-017] 28-qator "sotuv holati `deferred`" → "sotuv `posted`, fiskal holat `deferred` (javobdagi `fiscal.status`), `fiscal_receipts` yozuvi yo'q"; 314-qator "sotuv holati `deferred`" → xuddi shunday.
- [T-201] 125, 460, 511, 616, 883-qator: `spec/README.md` → mos `01` qaror raqami.
- [T-116] 241-qator: e-TTN yo'qligi "ogohlantirish" → "e-TTN `registered` bo'lmaguncha `send` rad etiladi (`409 ETTN_REQUIRED`)"; 257-qator → "offline `transfer.sent` — hujjat `posted` da qoladi, `warnings: ["ETTN_REQUIRED"]`; jo'natish e-TTN ro'yxatdan o'tgach online".
- [T-035] 271-qator → "Then farq (kam/ko'p) belgilanadi, kirim `draft` holatda saqlanadi; ombor balansi (M04) Buxgalter/Egasi `post` qilganda oshadi (qaror #49)".
- [T-019] 302-qator bonus → "bonus miqdori kirim qatoriga qo'shiladi, partiya `unit_cost` = faktura summasi / (to'langan + bonus miqdor) (13 §2.6, BHMS №4); 0 narxli alohida partiya yo'q".
- [T-252] 362-qator "Ochiq savollar 14" → "26 #9 (OQ-002)"; 366-qator "qaror #42" → "qaror #30".
- [T-160] 415, 435-qator "QQS 12%, 0%, ixtiyoriy 6%" → "QQS 12% (SK 258-modda), 0% / imtiyoz (`vat_exemption_code`)".
- [T-014] 440, 444-qator BO-10 holat nomlari → `uploaded`, `compared`, `match`, `diff_found`, `correction_sent`, `confirmed`, `auto_accepted` (D-10); tuzatish — kabinetda, tizim qayd etadi.
- [T-162] 446-qator "10-sanagacha" → ichki eslatma sanasi (yuqoridagi matn).
- [T-259] 451-qator "AI risk-scoring" → "davlat xavf-baholashi (VM 830) / qo'lda belgi; `unknown` — qizil kabi".
- [T-086] 633-qator (US-M15-01) standart toifalar → "standart ro'yxat — `13` §2.17 seed xaritasi (21 kod, ish haqi 9410/9420 alohida)".
- [T-285] US-M17-01: vaqt mezoni → "ro'yxatdan o'tish ≤ 2 daqiqa; 500 tovar Excel importi bilan birga ≤ 10 daqiqa" (27 B1 DoD bilan bir xil).
- [T-133] 114-qator: F-01 bilan mosligini tekshiring (markirovkali qaytarish — faqat online; boshqasi offline ruxsat) — matn shunday bo'lsa o'zgarmaydi.

#### `04-biznes-jarayonlar.md`
- [T-158, F-11] 99, 118-qator "bank orqali to'lovchi YaTT" → "e-faktura — `counterparty.kind='company'` (STIR'li YaTT mijoz `company` sifatida kiritiladi)".
- [T-017] 101-qator `deferred` → "sotuv `posted`, `fiscal.status='deferred'`".
- [T-129, T-123] BP-04 5-qadam (142) → "Tizim | M04 | `returns` posting — `stock_moves +qty` asl partiyaga; `restock=false` (muddati o'tgan, #48) bo'lsa shu miqdor `stock_lots.blocked_qty` ga va `write_offs` qoralamasi"; 6-qadam aktori → "Tizim".
- [T-259] 203-qator "AI risk-scoring" → "davlat xavf-baholashi (VM 830) / qo'lda belgi"; diagrammaga `unknown → qizil kabi` tarmog'i.
- [T-162] 227, 240-qator "10-sanagacha" → ichki eslatma sanasi.

#### `05-mvp-chegarasi.md`
- [T-201] 10, 12-qator `spec/README.md` → mos `01` qarori.
- [T-262] 121-qator jarima → "(raqobatchi sharhlari, qonuniy manba tasdiqlanmagan)".
- [T-261, T-274] 179-qator → "1 BHM/yil (440 000 so'm, 26 #25) ≈ 36 700 so'm/oy"; unit-iqtisod raqamlari `25` §11 dagi qiymatlar bilan bir xil (25 manba).

#### `06-ekranlar-umumiy.md`
- [T-245] 41-qator blok ro'yxati → "(sotuv, qaytarish, qarz to'lovi, kredit cheki)".
- [T-122] 66-qator (b) "qo'lda MXIK kiriting … Asl belgisi chiqarish bajarilmaydi" → "(b) 2–3 urinishdan keyin DataMatrix kodini qo'lda kiritish (faqat online, `POST /marking-codes/verify`, audit `marking.manual_entry`); markirovkali tovarni kodsiz sotish taqiqlanadi".
- [T-117] 114-qator "standart `personal`" → "standart qiymat yo'q — kassir har to'lovda tanlaydi (F-06)".
- [T-078] 144-qator BO-10 tablari → "QQS / Aylanma (MVP); mol-mulk, yer, JShDS, ijtimoiy soliq — API qabul qiladi, solishtirish yo'q (MVP'dan keyin)".
- [T-017] 167-qator `deferred` → fiskal holat.

#### `07-ekran-tafsilotlari.md`
- [T-059] 83-qator: "butun chek chegirmasi qatorlarga `line_gross` ulushida taqsimlanadi (qoldiq eng katta qatorga), har qatorda `discount_source='manual'`; limit `Σ discount_manual / Σ line_gross × 100`".
- [T-247] 93-qator (POS-02) dagi 46 soat modali olib tashlanadi — faqat POS-03 "TASDIQLASH" oldidan (129).
- [T-015] 115-qator `card_manual` → `card` (yorliq "Karta (qo'lda)"): `cash|card|uzqr|payme|click|uzum|debt`.
- [T-248] 120-qator `qrType` default "Tenant sozlamasi" → `static`.
- [T-026] POS-03/POS-04 fiskal holatlari: `pending | fiscalized | deferred` (lokal ko'prikda chek FM'da imzolanadi va `fiscal_result` voqeaga qo'shiladi — D-05).
- [T-017] 162, 230, 429, 461-qator "holat `deferred`" → "sotuv `posted`, `fiscal.status='deferred'` (fiskal chek yo'q)".
- [T-106] 168-qator (POS-04 elektron chek): natija — `sale.created.delivery='electronic'` va `delivery_reason` (`printer_failure|customer_request`).
- [T-105] 174-qator: chek qayta chop etish — `GET /api/v1/fiscal-receipts?sale_id=` yoki `?debt_payment_id=`; voqea `receipt.reprinted {fiscal_receipt_id}`.
- [T-109] 204-qator (POS-05): "`GET /api/v1/sales?number=` → tanlangach `GET /api/v1/sales/{id}` (qatorlar, `returned_qty`)".
- [T-031, T-133] POS-05 qaytarish: `refundMethod` ∈ `cash|card|uzqr|click|payme|uzum|debt_adjustment` (standart — asl to'lov usuli); qarzli sotuvda avval ochiq qarz kamayadi (chek yo'q), pul bilan qaytarilgan qismga chek (D-13); markirovkali qaytarish — faqat online (F-01).
- [T-108] 232-qator (POS-06): "B2B mijozda server `sale.created` postingida `einvoices(direction='out', status='draft', related_doc_type='sales')` ni o'zi yaratadi; POS chaqirmaydi"; `debt_balances` → lokal `customers` (232, 466).
- [T-240] 233-qator `limit_exceeded` → `debt_limit_exceeded`.
- [T-035] POS-08 (296) — o'zgarmaydi (allaqachon `draft` → BO-04 `post`).
- [T-103] 285-qator `receivedQty` "≥0" → ">0; 0 bo'lsa qator yuborilmaydi"; 286-qator `discrepancyReason` → `Select` (`short|excess|damaged|wrong_item|other`), farq bo'lsa majburiy → API `lines[].discrepancy_reason`.
- [T-006] 287-qator `poaNumber` → `Input` (ixtiyoriy); standart — `GET /api/v1/powers-of-attorney?purchase_order_id=` dagi `sent|accepted` yozuvning `number`i; saqlanadi `goods_receipts.poa_id`/`poa_number` (D-07).
- [T-033, T-240] 295-qator: "2–3 urinishdan keyin qo'lda MXIK maydoni" → "2–3 urinishdan keyin DataMatrix kodini qo'lda kiritish"; natija → "kod `POST/PATCH /goods-receipts` `lines[].marking_codes[]` ga (soni = qty, GS ajratgichlari aynan)".
- [T-005] POS-09 (326–344): `fromBranchId`/`toBranchId` → `fromWarehouseId`/`toWarehouseId` (MVP: filial tanlanadi, ombor avtomatik — #54; validatsiya `≠`); 333-qatordan keyin `vehiclePlate` (`transportMode=vehicle` da majburiy, ≤16) va `driverName` (ixtiyoriy); 341-qator natija → "`transfer.sent`; `vehicle` va e-TTN `registered` emas → hujjat `posted`, holat «E-TTN imzo kutilmoqda» (jo'natish e-TTN ro'yxatdan o'tgach)"; 344-qator → "online — `POST /api/v1/transfers` → `POST /api/v1/transfers/{id}/post` → (e-TTN `registered`) → `POST /api/v1/transfers/{id}/send`; `POST /api/v1/transfers/{id}/receive`".
- [T-004] 335-qator e-TTN izohi → "server `post`da `ettn_documents(status='pending_signature')` yaratadi; Egasi/Buxgalter BO-03 «Ko'chirishlar» tabida E-IMZO bilan imzolaydi; Omborchi ekranida holat «E-TTN imzo kutilmoqda»; qabul tomonida e-TTN BO-03 da tasdiqlanadi".
- [T-195] 429-qator "yangi qarz yozish endi POS-02 orqali" → "yangi qarz POS-02 orqali oddiy sotuv sifatida yoziladi"; 1357-qator "bu bosqich endi …" → "bu bosqich `/install` route'ini ichiga oladi".
- [T-240] 462-qator `debt_payment.created → /post` → "server darhol o'tkazadi (alohida `/post` yo'q)"; debt-openings ruxsati (464) → "`stock.opening.manage` yoki `debts.limit.manage`" (18 §12.4).
- [T-023, T-024] POS-13 (qarz to'lovi): `method` ∈ `cash|card|uzqr|click|payme|uzum` (`bank` yo'q); allokatsiya va chek qatorlari qurilmada `shared/lib/debt-allocation` bilan (offline ham), ekranda qaysi sotuvlar yopilishi ko'rsatiladi; voqeada `receipt_seq`, `allocations`, `fiscal_lines`; holatlarga `fiscal-blocked` (48 soat bloki) qo'shiladi.
- [T-023, T-025] BO-06 (840–846) "To'lov qabul qilish" → faqat `method='bank'` (bank o'tkazmasi, chek yo'q; naqd/karta qarz to'lovi — POS-13); "Ortiqcha to'lovlar" bloki — `sync_exceptions(kind='debt_overpayment_offline')` ro'yxati, amallar "Qaytarish" (POS-14/`POST /cash-movements` `reason='other'`, `account='6310'`, `counterparty_id`) va "Keyingi qarzga hisoblash" (`POST /ledger-adjustments` `Dt 6310 / Kt 4010`, `analytics.counterparty_id`) — `accounting.post`.
- [T-240] 839-qator AI qoralama → ruxsat: qoralama `ai.chat.use`, yuborish `debts.remind`.
- [T-002, T-064] POS-14 (494–508): `reason` ro'yxatidan `expense` olib tashlanadi; alohida "Xarajat" tugmasi/rejimi → `expense.created` voqeasi (`category_id` — `GET /expense-categories` keshidan, `amount`, `comment`; ruxsat `cash.withdraw` (limit), limitdan oshsa `ApprovalDialog`; D-18); `expenseCategoryId` faqat shu rejimda; `reason=owner_withdrawal` da `founderId` `Select` (`counterparties.is_founder=true`; `tenants.legal_form ≠ sole_proprietor` bo'lsa majburiy) → payload `counterparty_id`; `reason=other` da ixtiyoriy `account` `Select` (`9430`/`9390`/`6310`/`4010`/`4730`, standart — yo'nalishga ko'ra) faqat Buxgalter/Egasi uchun; 506-qator natija → `cash_movement.created`; 508 manba → outbox `cash_movement.created` / `expense.created`.
- [T-280] 500, 224, 1212-qator `note` → `comment`, max 1000; 1213 `cancel_reason` → "majburiy, 3–500 belgi"; 51-qator `openingCash` → `MoneyInput` (2 xona); 1334 parol "≥8" → "8–128 belgi (`14` §4)".
- [T-240] 559-qator: ruxsat `catalog.manage`, ekran — mos BO ekran ID'si.
- [T-240] 650-qator "15 daqiqa" → "24 soat (qaror #51)".
- [T-110] 690-qator "Inventarizatsiya" natijasi → "`POST /api/v1/stock-counts` (`{warehouse_id, doc_date, product_ids?, responsible_user_id?}`, `stock.count.create`) → POS-10".
- [T-102] 691-qator: `reason=gift` tanlanganda `giftKind` (`promo_justified|other`, standart `other`) va `promoOrderRef` (`promo_justified` da majburiy).
- [T-272] 705-qator (BO-04 rollari) — rollar bo'yicha ajratiladi: Menejer `purchases.create`; Omborchi `purchases.receive`; Buxgalter `purchases.post`, `purchases.pay`, `purchases.return`.
- [T-092] 734-qator `payment.source` → `payment.method` (`cash|bank`); 735-qatordan keyin `payment.shiftId` (`method=cash` da majburiy, ochiq smena).
- [T-006] 739–740-qator `poa.employeeId`, `poa.validTo` qoladi; 745-qator: "Saqlanadi: `powers_of_attorney` (D-07), kirimda `goods_receipts.poa_id`/`poa_number`"; 760-qator "E-ishonchnoma berish" → "`POST /api/v1/powers-of-attorney` (`purchases.create`) → `sign-challenge` → E-IMZO → `submit-signed` (`einvoice.sign`)".
- [T-093] 741-qator → `return.receiptId`, `return.docDate`, `return.lines[]` (`receiptLineId`, `lotId`, `qty`), `return.reason` ∈ `expired|damaged|excess|other`; 761-qator ikkiga: "Qoralama" (`purchases.return`, `POST /supplier-returns`) va "O'tkazish" (`purchases.post`, `POST /supplier-returns/{id}/post`).
- [T-091] 755-qator ruxsati → `purchases.receive` + `ai.ocr.use`.
- [T-094] 794-qator `nameRu` max 200 → 255; 804-qator ruxsat `prices.edit` → `catalog.manage`.
- [T-282] BO-05 (795–811) "Chegirma qoidalari" bloki → "MVP'dan keyin (qaror #33, US-M03-02)" belgisi.
- [T-001] 803-qator: rad etilsa holat `rejected` ekanini tekshiring (to'g'ri bo'lsa o'zgarmaydi).
- [T-240] 906-qator recost ustunlari → `19` §17 `GET /recost-jobs` javobidagi maydon nomlari.
- [T-011] 907-qator `adjustment.entryDate` → `adjustment.docDate` (faqat joriy ochiq davr; istisno — `0000` hisobli boshlang'ich balans yozuvi `go_live_date − 1`); yangi maydonlar `adjustment.accountDt`, `adjustment.accountKt` (4 raqam, majburiy, `≠`), `adjustment.amount` (`MoneyInput`, >0), `adjustment.branchId` (majburiy, standart joriy filial), `adjustment.correctionOfPeriod` (ixtiyoriy, `YYYY-MM`); 914-qator → `POST /ledger-adjustments` (`doc_date` …); 916-qator → `GET /api/v1/ledger-entries?entry_date__gte=&entry_date__lte=&account_dt=&account_kt=`.
- [T-240] 912-qator eksport → `POST /api/v1/reports/ledger-entries/export` (`format: xlsx|pdf`, `reports.export`).
- [T-028] 913-qator: readiness blokerlari `recost_pending`, `fiscal_pending`, `devices_unsynced` (sinxronlanmagan qurilmalar ro'yxati, "Qurilmani bekor qilish" havolasi BO-11 ga); ogohlantirishlar (`tax_settlement_missing`, `opening_0000_nonzero`, `open_shifts`, `drafts_in_period`, `devices_not_synced_after_period_end`) — tasdiqlash dialogida; faqat eng eski ochiq oy tanlanadi.
- [T-127] 952-qator (0102): "ichki 0102 = Σ `fiscal_receipts` (`sale`/`return`/`debt_settlement`) chek sanasi bo'yicha; ledger bilan farq — «qarzga sotuv vaqt farqi» izoh qatori".
- [T-014] BO-10 (954–968): rollar — Buxgalter va Egasi (`tax.correction.submit`); 957-qator `correctionNote` → `comment` (max 1000) + ixtiyoriy `portalRef`; 965-qator natija → `POST /api/v1/state-reports/{id}/correction` `{comment, portal_ref?}` (imzosiz qayd), holat `correction_sent`; 966-qator → `POST /api/v1/state-reports/{id}/confirm`, holat `confirmed` ("Tasdiqlandi"); 968 manbaga `/confirm`.
- [T-184] 957-qator "06 §1.3 Won't" → "05 §1.3 Won't".
- [T-068] 995-qator `device_name` → `cash_register_name` + `kind` + `app_version` (hisoblanadi).
- [T-097] 1017-qator bekor qilish dialogi: `reason` (majburiy) + `outbox_pending_count > 0` bo'lsa `confirm_pending_loss` checkbox; `pending_events` → `outbox_pending_count`.
- [T-013] 1049-qator `warehouses[].inventoryAccount` — saqlash `PATCH /api/v1/warehouses/{id}` (`settings.branches`; harakat bo'lsa `409 WAREHOUSE_ACCOUNT_LOCKED`); "+ Filial qo'shish" dialogiga `warehouseType` (`store|stock`, standart `store`); 1057 natija → `POST /api/v1/branches`.
- [T-012] 1060-qator → `POST /api/v1/cash-registers/{id}/archive` (`{}`); 1062 manbaga `POST /cash-registers/{id}/archive`, `GET /api/v1/warehouses?branch_id=`, `PATCH /api/v1/warehouses/{id}`.
- [T-022] BO-12 kassa qatoriga "Fiskal agent" `Select` (shu tenant agentlari, `capabilities.fiscal.devices[]` dan `local_id`) → `PATCH /cash-registers/{id}` `{fiscal_agent_id, fiscal_local_device_id, version}`; BO-14 ga "Do'kon agenti" bloki: agentlar ro'yxati (W-01), "Kompyuterni ulash" (W-03 → W-04, "Rad etish" — T-232), "Uzish" (W-05), "Diagnostika" (W-07), "Loglar" (W-08); ruxsatlar `onec.view` / `onec.settings.manage`.
- [T-089] 1114–1117-qator: `taxRegime` → `POST /api/v1/tenant/tax-regimes` (40c); `crptApiKey`, `fakturaUz.*` → `PUT /api/v1/tenant/integrations/{provider}` (40d); Faktura.uz maydonlari 4 ta: `fakturaUz.login`, `fakturaUz.password`, `fakturaUz.clientId`, `fakturaUz.clientSecret` (maskalangan); 1115 `costingMethod` → `aveco|fifo` (standart `aveco`; yorliq katta harfda); 1130 manbaga 40c va 40d.
- [T-090] 1121-qator `providerFiscalizationOff` → API `provider_autofiscal_disabled_confirmed: true` (40d, click/payme/uzum uchun majburiy; belgilanmasa saqlash o'chiq).
- [T-101] 1120-qator consent so'roviga `terms_version`.
- [T-095] 1141-qator rollarga `einvoice.create`; 1156-qator ruxsati → `einvoice.create`.
- [T-004] BO-15 (1149–1160): "E-IMZO imzo" natijasi → "… `submit-signed` → `POST /api/v1/einvoices/{id}/send`"; yangi amallar "Yuborish" (`einvoice.sign`, `/send`) va "Bekor qilish" (`einvoice.sign`, `/cancel`); yangi blok "Kiruvchi e-TTN" (`GET /api/v1/ettn-documents?direction=in`) — "Tasdiqlash"/"Rad etish" (`purchases.receive` + `einvoice.sign`; `sign-challenge?action=accept|reject` → `/accept`|`/reject`); 1160 manbaga `/send`, `/cancel`, `GET /ettn-documents`.
- [T-004] BO-03 "Ko'chirishlar" tabi: D-08 §4 dagi amallar ("E-TTN imzolash", "Qo'lda ro'yxatga olish", "Jo'natish", qabul tomonida "E-TTN tasdiqlash / rad etish") ruxsat va endpointlari bilan.
- [T-158] 1146-qator YaTT → "yuridik shaxs (`counterparty.kind='company'`; STIR'li YaTT ham `company` sifatida kiritiladi)".
- [T-006] 1148-qator "E-ishonchnomalar" → manba `GET /api/v1/powers-of-attorney?status=`; holatlar D-07 bo'yicha.
- [T-096] 1158-qator risk-flag dialogiga `note` (`Textarea`, majburiy) → tana `{risk_flag, note}`.
- [T-240] 1171-qator BO-16: `write_off_over_limit` tasdiqlovchi ruxsati `stock.writeoff`.
- [T-150] 1211-qatordan keyin `taxType` `Select` (`vat|turnover|pit|social|property|land|other`) — toifa `default_account=6410` bo'lsa majburiy, aks holda yashirin.
- [T-100] 1243-qator PLU eksport ruxsati → `catalog.manage`.
- [T-144, T-240] 1271-qator `monthly|yearly` → `month|year`; BO-19 summasi `amount_breakdown` dan (D-23: chegirma faqat asosiy tarifga).
- [T-099] 1273-qator manbaga `GET /api/v1/billing/subscription`, `GET /api/v1/billing/payments`.
- [T-101] BO-21 (1331–1351): ① ga `ownerName` (Ism, 2–100, majburiy); signup chaqiruvi ② dan keyin ("Davom" ②); "(A-01)" belgisi olib tashlanadi; tana `{phone|google_id_token, otp, password, owner_name, store_name, business_type, legal_form, accepted_terms_version, ai_cross_border_consent}`.
- [T-240] 1359-qator OCR oqimiga poll (`GET /ai/ocr/jobs/{id}`) va `/confirm` qadamlari (`catalog.manage`).
- [T-231] 1402-qator `agent_name` → `name`.
- [T-230] 1460, 1474-qator W-55 ga agent nomi/versiyasi (W-37 `agent.name`, `agent.agent_version`); 1511–1512 legendaga `draft`, `cancelled`; ExportItem ustunlariga `max_attempts`, `progress`.
- [T-010] BO-24 (1546–1565): 1553-qatordan keyin `varianceAmount` (`MoneyInput`, ±, faqat `method=collection`; manfiy — kamomad, musbat — ortiqcha); 1554 → `net = gross − commission + variance`; 1565 → "server FIFO bilan taklif qiladi (20 #55g); natija dialogi — `drafts_created`, `duplicates`, `unmatched_lines`"; qoralamani tahrirlash → `PATCH /api/v1/bank-settlements/{id}` (55h).
- [T-240] B-147 qolgan bandlari (b, c, d, e, h, i, j, l–p, r) yuqoridagi qatorlarda; C-167: BO-09 (938) Menejer uchun QQS registri ko'rinishi olib tashlanadi (`tax.vat.view` Menejerda yo'q).

#### `08-dizayn-tizimi.md`
- [T-145] 478-qator "Kod SMS orqali yuborildi" → ikki kalit: `otp_sent_telegram` "Kod Telegram orqali yuborildi / Код отправлен в Telegram" va `otp_sent_sms` "Kod SMS orqali yuborildi / Код отправлен по SMS" — `channel_used` bo'yicha.
- [T-133] 506-qator izohi → "faqat markirovkali qaytarish online (F-01)".
- [T-030] §13.1 (522–554) — D-09 bo'yicha: namunadagi har tovar qatori ostiga kichik qator `MXIK … · dona · <shtrix kod> · QQS 12%: <summa>`; 554-qatorga "va QQS stavkasi/summasi (qator darajasida, qaror #26 formulasi)".
- [T-117, T-159] 556-qator: karta turi yorliqlariga "noma'lum / не определён"; "Nasiya/В долг" yorlig'i olib tashlanadi → "`debt_settlement` chekida to'lov shakli `debt_payments.method` dan; chek sarlavhasi «Qarz to'lovi / Погашение долга»".

#### `09-ai-funksiyalar.md`
- [T-198] 11, 12, 13, 15, 27, 40, 54, 55, 68, 69, 70, 95, 109, 119, 133, 143, 153, 155-qator: `texnik/` → `research_notes/texnik/`.
- [T-274] 169-qator AI xarajati raqamlari → `25` §11 dagi qiymatlar.

#### `26-ochiq-savollar-reestri.md`
- [T-177] 8-qator "(#106 dan)" → "(#171 dan)".
- [T-147] 50-qator (#21) AI-10 → "MVP'dan keyin; boshlanishi qoida-asosidagi, ML keyin (qaror #16)".
- [T-188] 53 → `` `05` §4 (3-band) ``; 68 → `` `05` §4 (4-band) ``; 128 → `` `05` §4 (oxirgi xatboshi) ``.
- [T-250] 65-qator → "`Dt 9410|9420 / Kt 5010|5110` (#52)".
- [T-179] 103-qator `/OS6` va `/OS3` olib tashlanadi (`` `08` §13 `` qoladi).
- [T-174] 104-qator `` `18` §15a `` → `` `18` §14a ``.
- [T-269] 133-qator (#134) "33 §10" → "`33` §9.10, §12; `34` §8.12".
- [T-161] 140-qator (#145) → "`gross_9050` standart / `net` ixtiyoriy".
- [T-189] 141-qator `` `12` §7.12 `` → `` `12` §7 (12-band) ``.
- [T-180] 153-qator (#56) `` `14` §1.4 `` → `` `15` §1.4 ``.
- [T-135] 184–204-qatorlar (#94–#104, #132, #133, #135, #136) "Vaqtinchalik standart" ustuni `33` §16.2 (33:3895 atrofi) matni bilan: tranzit — `5710` + `val(payment_method)` (#42), boshqa schyot — `ONEC_PAYMENT_ACCOUNT_NOT_TRANSIT`; `fill_accounts=true`, to'ldirilmagan schyot — `ONEC_FILL_CHECK_FAILED`; qaytarish — `orp_returns_section`; QQS yaxlitlash — profil `vat_rounding_mode` (33 §8); metadata — `read_metadata`; tekshiruv kodlari — 33 §2.3; vaqt chegarasi — `timeout_s = clamp(60 + 0.4 × qatorlar, 120, 1800)`; "#34" havolasi → "#42". `card_transit_account=5711`, `credit_customer_mode`, `discount_mode`, `late_receipt_policy`, `cost_source_for_reports`, `PF_*`, `meta_sync`, `fill_accounts_mode`, `ONEC_ACCOUNTS_UNRESOLVED`, `vat_round`, `max_lines_per_doc`, `per_call_timeout_s` nomlari va "yozish va o'tkazish alohida" iborasi olib tashlanadi.
- [T-136] 201–202-qator: "Bosqich A gacha kod yozilmaydi" → "`33` §16.1 pilot oldi testlari (P-03…P-07, P-12) o'tguncha Bosqich 7 kodi bloklanadi".
- [T-023, F-07] Jadval B ga yangi **#171** (Tashqi javob kerak): "Bank o'tkazmasi orqali mijoz qarzini to'lashda (kassa orqali emas) fiskal chek talab qilinadimi (VMQ-943 1-ilova 30-band)? | Kim: soliq maslahatchisi / fiskal hamkor (Xat 1) | Vaqtinchalik standart: chek yo'q, `debt_payments.method='bank'` faqat BO-06 (qaror #67) | Bloklaydi: — (pilotdan oldin javob olinadi)". Yig'ma jadvalidagi B soni +1.

#### `27-backlog.md`
- [T-284] 37-qator (B0) dagi signup aksepti (`accepted_terms_*`) → 62-qatordagi signup vazifasiga ko'chiriladi.
- [T-172] 51-qator B0 DoD ga: "QT-RLS-01…08, QT-OAUTH-01…07, QT-AI-PII-01 yashil; CI'da `mypy --strict`, `pip-audit`, `npm audit --audit-level=high`, `gitleaks`; `devices.kind`/`signing_keys.purpose` migratsiya testi (#58c); tashqi provayderdagi nusxadan staging restore bir marta (#65)".
- [T-283] 62-qator "A-01" olib tashlanadi; 64-qator "E-32" → "BO-21 ⑥".
- [T-038] 68-qatordan "va boshlang'ich qoldiq (`stock_openings`)" olinadi; 74-qator "US-M04-04 (katalog importi)"; 93-qatorga "`stock_openings` importi/kiritish (US-M04-04 qoldiq qismi, `Dt inv_acct / Kt 0000`)"; 98-qator Hikoyalarga "US-M04-04 (boshlang'ich qoldiq)".
- [T-166] 69-qator → "SMS — `EskizSmsAdapter` `ESKIZ_TEST_MODE=true` (Eskiz shartnomasi B6 gacha, 26 #45); Telegram OTP — real"; 76-qator DoD "OTP (Telegram/SMS)" → "Telegram OTP real; SMS — test rejimi".
- [T-039] 74-qatordan US-M09-03 olinadi; 127-qator (B3 Hikoyalar) ga qo'shiladi.
- [T-285] 76-qator DoD → "ro'yxatdan o'tish ≤ 2 daqiqa, 500 tovar Excel importi bilan ≤ 10 daqiqa (QT-NFR-SIGNUP-01)".
- [T-123, T-124] B2 vazifalariga: "`stock_lots.blocked_qty` (qaytgan muddati o'tgan tovar, D-20); AVECO `avg_costs.total_value`, manfiy qoldiq `pending` tannarxi, FIFO↔AVECO almashtirish (D-21)".
- [T-164] 90-qatorga "offline `transfer.*` / `stock_count.line_recorded` — B3 sync bilan"; QT-M06-04 va QT-M05-05 B3 DoD ga.
- [T-165] 91-qator → "`FakeEInvoiceAdapter` e-TTN ni darhol `registered` qiladi (staging/test); real yuborish va E-IMZO — B5".
- [T-040] 100-qator B2 DoD → "`13` §2.6–§2.12, §2.20, §2.21, §3 (FIFO/AVECO), X-02 misollari avtomatik testlarda"; B3 DoD ga "§2.1–§2.5, §2.18, §2.19, §3.2a"; B4 DoD ga "§2.13–§2.17, §2.18a, §2.26, §4.3"; B5 DoD ga "§2.22, §2.23, §5.1, §5.5".
- [T-163] B2/B3 vazifalariga: "bildirishnoma voqealari `outbox_jobs(kind='telegram')` ga yoziladi (yuborish — B4)"; 200-qatordagi M18 ogohlantirishlari va 201-qatordagi yaroqlilik ogohlantirishi → B4 (148-qator yoniga).
- [T-169, F-02] 111-qator → "… UzQR …; Click/Payme/Uzum ixtiyoriy"; 252-qatordan "Uzum to'lovi" olinadi.
- [T-174] 122-qator `DB-09`/`DB-10` va 175-qator `DB-0x` ID'lari → `12` dagi jadval nomi va bo'lim raqami (masalan `approval_requests`, `doc_approvals` — `12` §2.x); 178-qator `` `18-api-kassa.md` §15a `` → `§14a`.
- [T-139] 117-qatordagi US-M01-07 vazifasi va 129-qator B3 DoD ga "printer matritsasi va tarozi prefiksi — QT-M01-22".
- [T-041] 129-qator B3 DoD dan "qarz limiti" olinadi; B4 DoD ga "`16` §5 qarz limiti/balans konflikt qoidalari test bilan qoplangan (QT-M08-03, QT-M08-16, QT-M08-17)".
- [T-002] B4 M15 vazifasiga: "POS kassa xarajati — `expense.created` voqeasi (D-18)".
- [T-024, T-025] B4 M08 vazifasiga: "offline qarz to'lovi: `customers.open_debt_docs` keshi, `shared/lib/debt-allocation` + `shared/debt-allocation-vectors.json`, `sale_lines.settled_amount`, `debt_payments.receipt_seq`/`unallocated_amount`, ortiqcha offline to'lov (`Kt 6310`) — D-03/D-04; back-office qarz to'lovi faqat `bank`".
- [T-170] B4 (140–146) ga "`debt_writeoffs` (`POST /debt-writeoffs`, `/post`, Egasi) va `debt-doubtful-flags` (`13` §2.15/§2.15a, `18` §12.5–§12.6)".
- [T-286] QT-M10-07 (`tax_settlements`) — B4 DoD ga; B3 dan olinadi.
- [T-028] Davr yopish (US-M11-02) vazifasi bor bosqichga: "D-06 — yopilgan davrga kech POS voqealari, readiness `devices_unsynced`/`warnings`, `PERIOD_CLOSE_OUT_OF_ORDER`".
- [T-042] 155-qator B4 DoD → "QT-M08-01…17 yashil; staging'da ichki demo-tenant bilan bir haftalik qarz daftari ssenariysi; bank ko'chirmasi namunasi import qilinib 5710 tranzit qoldig'i yopiladi"; "pilot do'kon qog'oz daftarsiz bir hafta" mezoni B6 DoD ga.
- [T-022] B5 (163–168): kirish shartiga "`agent_update` ildiz kaliti oflayn yaratilgan"; 166-qator "Do'kon agenti asosi" vazifasiga 225-qatordagi umumiy qismlar ko'chiriladi — "OAuth `onec-agent` mijozi, `/oauth/device_authorization`, device grant, `client_credentials` + `private_key_jwt`, `aud=urn:erp:onec-agent`; A-01, A-03…A-10; long-poll + Redis wake, lease/heartbeat/sweeper, Ed25519 vazifa imzosi va kalitlar to'plami; W-01…W-05, W-07, W-08; migratsiya `0028 store_agent` (D-01); `cash_registers.fiscal_agent_id`"; 168-qator → "Agentda xom TCP 9100 printer (`print.raw`); tarozi PLU yuklash — MVP'dan keyin (MVP'da PLU CSV eksport); jonli og'irlik — Web Serial, MVP'dan keyin".
- [T-026] B5 fiskal vazifasiga: "lokal ko'prikda `fiscal_result` voqeada, `fiscal.status` natijasidagi `acked[]` → `ofd_acked_at` (D-05); lokal API sxemalari `21` §16.1 (D-22)".
- [T-006] B5 e-faktura vazifasiga: "e-ishonchnoma — `powers_of_attorney`, `POST /powers-of-attorney` + E-IMZO, `outbox_jobs(kind='poa_send')` (D-07)"; e-TTN ekran amallari (D-08).
- [T-171, T-286] 182-qator B5 DoD → majburiy: "CI'da FM emulyatori va `FakeMarkingAdapter` bilan QT-M01-18, QT-M01-20, QT-M01-21, QT-M01-23, QT-OFFLINE48-05 yashil; US-M01-06, US-M11-02, US-M10-03, `ledger_adjustments`, e-ishonchnoma qabul mezonlari testlangan"; "real hamkor/CRPT test muhitida" — 26 #109/#40 javobidan keyin (alohida band).
- [T-167, F-10] 190-qator (B6 kirish sharti) ga "lokal fiskal ko'prik tanlangan bo'lsa — Authenticode OV olingan (26 #105)".
- [T-168, F-03] 200-qator (B6, M09 yorliq) ga ">200 yorliq yoki iOS uchun server PDF (`outbox_jobs(kind='label_pdf')`, qaror #54)".
- [T-022] B7 (220–228): 224–225-qatordagi B5 ga ko'chirilgan qismlar olinadi; qoladi — "A-02, W-06, W-09…W-55, migratsiya `0029 onec_integration`, 1C vazifa turlari, 6 ta 1C SECURITY DEFINER funksiyasidan qolganlari (`onec_tenants_due`)"; 223-qator "12/14/16 dagi o'zgarishlar (§5.22)" → "§5.22 dagi qolganlari (`devices.kind`/`signing_keys.purpose` — Bosqich 0 da, #58c)".
- [T-192] 235-qator → "Qabul testlari (`31` M19; `33` §14 qabul mezonlari)".
- [T-288] 250–257: US-M08-08 va US-M03-02 bitta joyda qoladi (ikkinchisi olinadi).
- [T-287] 272, 273, 280, 287, 289-qator "Bloklaydigan bosqich" ustuni `26` Jadval B dagi tegishli band ustuni bilan aynan tenglashtiriladi (#20, #63, #112, #137, #167/#168).

#### `29-atamalar-lugati.md`
- [T-183] 14-qator `` `10-umumiy-arxitektura.md` §Qoidalar, 2-band `` → `` `00-README.md` §Qoidalar, 2-band ``.
- [T-263] 178, 189-qator "o'z omborlari orasida ham majburiy" → "avtotransportda (`transport_mode='vehicle'`) majburiy, o'z omborlari orasida ham; piyoda/jamoat transportida — yo'q (VM 249 31-ilova 24-band)".
- [T-006] "E-ishonchnoma" atamasiga: "saqlanadi — `powers_of_attorney`".

#### `30-izchillik-matritsasi.md`
- [T-281] 84-qator US-M07-05 ruxsati → `purchases.return` + `purchases.post`; 91-qator US-M08-02 → BO-06; 97-qator US-M08-08 → `POST /counterparties/{id}/statement-link`; 98-qator `PATCH /counterparties` → `debts.limit.manage`.
- [T-148] 186-qator → "endpoint MVP'da (lokaut, #20, B6); faqat `closed` holatdan chiqish eksporti (US-M17-05) — MVP'dan keyin".
- [T-006, T-010, T-012, T-013, T-014, T-151] Matritsaga yangi endpoint qatorlari: `POST/GET /powers-of-attorney` (+`sign-challenge`, `submit-signed`, `cancel`), `PATCH /bank-settlements/{id}`, `POST /cash-registers/{id}/archive`, `PATCH /warehouses/{id}`, `POST /state-reports/{id}/confirm`, `POST /debt-payments/{id}/cancel`, `POST /debt-openings/{id}/cancel`, `POST /debt-writeoffs/{id}/cancel` — ekran va ruxsat bilan (shu reja §6 G-c dagi qiymatlar).
- [sanoq] 331-qator "19: ~110 endpoint" va 20 endpoint soni — G-c tugatgach qayta sanaladi.

### G-b — `10`–`13`

#### `10-umumiy-arxitektura.md`
- [T-176] 89-qator: "`34-dokon-agenti.md` ga kengaytiriladi" iborasi olinadi → "fiskal ko'prik, printer va tarozi — `34-1c-agent.md` §14 «Do'kon agenti kengaytmasi»".
- [T-022] §1 dagi Do'kon agenti bandiga: "agent infratuzilmasi (ulash, token, imzoli vazifa navbati) — Bosqich 5 (qaror #66); 1C moduli — Bosqich 7".

#### `11-malumotlar-modeli.md`
- [T-243] 141, 147-qator registrlar ro'yxati: `valuation_method_history` — registr emas, istisno ro'yxatida (sozlama tarixi).
- [T-125] 147-qator storno → "`ledger_entries` — Dt/Kt o'rni almashtiriladi, `amount` musbat; `stock_moves`/`debt_moves`/`cash_moves`/`vat_moves` — teskari ishorali miqdor/summa (13 §5.2)".
- [T-045] 149-qator → "tannarx usuli — `valuation_method_history` (joriy = eng oxirgi `valid_from ≤ doc_date`)".
- [T-001] 162-qator → "`draft` → `pending_approval` (limitdan katta, US-M09-02; `approval_requests` `expired` bo'lsa hujjat `draft` ga qaytadi) → `posted` / `rejected`; `draft` → `cancelled`".
- [T-151] 164-qator inventarizatsiya → "`counting` → `review` → `posted` → (`cancelled` — storno); `counting`/`review` → `cancelled` (registrsiz)"; 165-qator smena → "`open` → `closed` (Z-hisobot)".
- [T-003] 167-qator e-TTN → D-08 §1 izohi: "chiquvchi: `pending_signature` → `sending` → `registered` → `accepted`/`rejected`; `sending` → `failed` → `sending`; kiruvchi: `received` → `accepted`/`rejected`; `cancelled`".
- [T-006] Holatlar jadvaliga yangi qator "E-ishonchnoma (`powers_of_attorney`)": `draft` → `pending_signature` → `sending` → `sent` → `accepted`/`rejected`; `sending` → `failed` → `sending`; `draft`/`pending_signature` → `cancelled` (D-07). §2/§6 obyektlar ro'yxatiga `powers_of_attorney` (xarid hujjatlari ostida; `goods_receipts.poa_id`).
- [T-253] Holatlar jadvaliga "Bank tushumi tasdig'i (`bank_settlements`)": `draft` → `posted` → (`cancelled` — storno); `source='statement_import'` qoralamalari avtomatik `post` qilinmaydi.
- [T-014] 172-qator davlat hisoboti → "`uploaded` → `compared` → `match`/`diff_found` → `correction_sent` / `confirmed` / `auto_accepted`".
- [T-144, F-05] 173-qator obuna → "`trial` (30 kun) → `grace` (24 soat) → `restricted` …; `restricted` → `active` (to'lov); `closed` — faqat platforma admini amali (avtomatik emas; US-M17-05, MVP'dan keyin) (qaror #70)".
- [T-115] 193-qator `outbox_jobs.kind` ro'yxati → `ofd_send`, `einvoice_send`, `einvoice_accept`, `ettn_send`, `ettn_accept`, `poa_send`, `marking_verify`, `marking_accept`, `marking_supplier_return`, `marking_writeoff`, `state_report_reminder`, `sms`, `telegram`, `ai`, `report_export`, `label_pdf`, `billing_webhook_reconcile`.
- [T-069] 195-qator `sync_exceptions.kind` → D-12 ro'yxati.
- [T-022, T-024] Ustun ro'yxatlariga: `cash_registers.fiscal_agent_id`, `fiscal_local_device_id`; `onec_agents.capabilities`; `sale_lines.settled_amount`; `debt_payments.receipt_seq`, `unallocated_amount`; `stock_lots.blocked_qty`; `avg_costs.total_value`.
- [T-243] 241–242-qator → DDL nomlari: `accept_reason`, `cancel_reason`, `skip_note`.

#### `12-db-sxema.md`
- [T-175] 22, 52-qator "05-xavfsizlik §3.2/§3.3" → "`15` §3.2" / "`15` §3.3"; 1893-qator "04-offline-sync §5" → "`16` §5"; 3867-qator "05-xavfsizlik §2.3" → "`15` §2.3", "12-auth §19" → "`14` §19".
- [T-196] 3867-qator "Kassir ролига" → "Kassir roliga".
- [T-090] 356–366 `tenants.settings` izohiga kalit: `payment_providers.{click|payme|uzum}.autofiscal_off_confirmed_at` (ISO vaqt; 40d tasdig'i).
- [T-013] 443–446 `warehouses.inventory_account`: `DEFAULT '2910'` olib tashlanadi (`NOT NULL` va CHECK qoladi); izoh: "yaratishda `type='store'` → `'2920'`, `type='stock'` → `'2910'` (ilova qo'yadi); `stock_moves` bo'lgach o'zgartirilmaydi (`409 WAREHOUSE_ACCOUNT_LOCKED`)".
- [T-022] `cash_registers` (453–474) ga: `fiscal_agent_id UUID NULL` (FK 0028 da `ALTER … ADD CONSTRAINT fk_cr_fiscal_agent FOREIGN KEY (fiscal_agent_id) REFERENCES app.onec_agents(id)`), `fiscal_local_device_id TEXT NULL`, `CHECK (fiscal_agent_id IS NULL OR fiscal_local_device_id IS NOT NULL)`. `devices` (494–495) izohi → "`onec_agent` — Do'kon agenti; kassaga bog'lanish `cash_registers.fiscal_agent_id` orqali (qaror #66)".
- [T-151] 910-qator `shifts.status` CHECK → `('open','closed')`.
- [T-024] `sale_lines` (965–989) ga `settled_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (settled_amount >= 0)` (izoh: "qarz to'lovi/aralash cheklarida fiskallangan kumulyativ summa, D-04").
- [T-116] 1225–1226 `transfers` izohlari → "`vehicle_plate` — `post` da shart (`transport_mode='vehicle'`); `send` — e-TTN `registered` bo'lmaguncha rad (`409 ETTN_REQUIRED`)".
- [T-103] `receipt_lines` ga `discrepancy_reason TEXT NULL CHECK (discrepancy_reason IN ('short','excess','damaged','wrong_item','other'))`.
- [T-006] `goods_receipts` ga `poa_id UUID NULL` (FK `powers_of_attorney` yaratilgach 0020 da `ALTER`); `poa_number` izohi → "e-ishonchnoma raqami (`powers_of_attorney.number` dan yoki qo'lda)".
- [T-023, T-024, T-025] `debt_payments` (1450–1491) ga `receipt_seq INT NULL`, `unallocated_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (unallocated_amount >= 0)`; 1483-qator CHECK → `CHECK ((method = 'bank') = (cash_register_id IS NULL AND shift_id IS NULL AND receipt_seq IS NULL))` (D-03).
- [T-027] `cash_movements` (≈1660–1690): `account TEXT NULL CHECK (account IS NULL OR account IN ('9430','9390','6310','4010','4730'))`, `employee_id UUID NULL REFERENCES app.users(id)`; `CHECK (reason = 'other' OR account IS NULL)`; `CHECK ((reason IN ('collection','owner_withdrawal') AND direction = 'out') OR (reason = 'deposit' AND direction = 'in') OR reason = 'other')`; 1689-qator CHECK → `CHECK (reason IN ('owner_withdrawal','other') OR counterparty_id IS NULL)`; `CHECK (account IS DISTINCT FROM '4730' OR employee_id IS NOT NULL)`, `CHECK (account NOT IN ('6310','4010') OR counterparty_id IS NOT NULL)`. `reason` CHECK o'zgarmaydi (`expense` qo'shilmaydi — D-18).
- [T-043] 1841-qator `stock_moves.moved_at` izohi → "hujjat biznes vaqti: POS voqeasida `effective_created_at` (16 §8), back-office hujjatda `posted_at`; `DEFAULT now()` faqat zaxira".
- [T-123] `stock_lots` ga `blocked_qty NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (blocked_qty >= 0 AND blocked_qty <= qty_left)` (D-20).
- [T-124] 1874-qator `avg_costs` ga `total_value NUMERIC(18,2) NOT NULL DEFAULT 0` (D-21).
- [T-023] §2.8 izohi (1993–1995) va 2009–2011 izohlari → "`debt_settlement` — har doim `cash_register_id`, `shift_id`, `receipt_seq` bilan; bank o'tkazmasi orqali qarz to'lovida chek yaratilmaydi (qaror #67)"; 2035-qator CHECK tarmog'i → `(kind = 'debt_settlement' AND debt_payment_id IS NOT NULL AND sale_id IS NULL AND return_id IS NULL AND receipt_seq IS NOT NULL AND cash_register_id IS NOT NULL AND shift_id IS NOT NULL)`.
- [T-006] Yangi jadval `app.powers_of_attorney` — D-07 §1 DDL aynan (0020 `fiscal_marking_edocs` revizionida `einvoices` dan keyin); `updated_at` trigger ro'yxati (2.10) va RLS uchligi (4.2) ro'yxatlariga qo'shiladi.
- [T-003] `ettn_documents` (2106–2123) — D-08 §1: status CHECK ga `'failed'`; ustunlar `counterparty_id`, `receipt_id`, `doc_date`, `payload JSONB NOT NULL DEFAULT '{}'`, `signed_at`, `last_error`; 2121-qator CHECK → `CHECK (direction = 'in' OR einvoice_id IS NOT NULL OR transfer_id IS NOT NULL)`; 2117 izohi D-08 bo'yicha.
- [T-014] `state_reports` (2125–2140): status CHECK → `('uploaded','compared','match','diff_found','correction_sent','confirmed','auto_accepted')`; `correction_signature` o'rniga `correction_comment TEXT NULL`, `correction_portal_ref TEXT NULL`; yangi `confirmed_at TIMESTAMPTZ NULL`, `confirmed_by UUID NULL REFERENCES app.users(id)`.
- [T-115, T-006] 2187–2189 `outbox_jobs.kind` CHECK → G-b `11` dagi 17 qiymatli ro'yxat (`marking_return` → `marking_supplier_return`; `poa_send`, `marking_writeoff`, `billing_webhook_reconcile` qo'shiladi); §6.1 0022 izohi shunga.
- [T-069] 2224-qator `sync_exceptions.kind` → `TEXT NOT NULL CHECK (kind IN ('price_mismatch','archived_product','stock_negative','debt_limit_exceeded_offline','approval_limit_exceeded_offline','receipt_seq_conflict','debt_overpayment_offline','debt_allocation_mismatch','late_in_closed_period','cost_unknown','count_late_move'))` (izoh "16 §5 ro'yxati").
- [T-084, T-085] `ai_ocr_jobs.doc_type_hint` CHECK dan `'return'` olinadi (`purchase|catalog`); 2346 izohi → `'goods_receipts'|'stock_openings'` (`'products'` va `'returns'` olinadi); yangi ustun `created_product_ids UUID[] NOT NULL DEFAULT '{}'`.
- [T-126] `products` ga `turnover_tax_group TEXT NOT NULL DEFAULT 'general' CHECK (turnover_tax_group IN ('general','tobacco'))`; yangi global jadval `platform.turnover_tax_rates (code TEXT, rate_pct NUMERIC(5,2) NOT NULL, valid_from DATE NOT NULL, PRIMARY KEY (code, valid_from))` + seed (§5.1): `retail_city_100k_plus` 4, `retail_other` 2, `retail_remote_mountain` 1, `general` 4, `tobacco` 4, `sole_proprietor` 1 (`valid_from='2026-01-01'`); `erp_app` ga faqat SELECT.
- [T-144] 600-qator `billing_payments.amount_breakdown` izohi → `{plan, period, addons:[{code, qty, unit_price, months}], discount}` (D-23).
- [T-022] `onec_agents` (2517+) ga `capabilities JSONB NOT NULL DEFAULT '{}'` (izoh: "34 §14.2 sxemasi; A-01 `hello` dan yangilanadi"); `onec_agent_tasks` (3054–3058, 3084) CHECK'lari — D-01 §3 aynan; §2.11 kirish izohiga "Do'kon agenti umumiy jadvallari (`onec_agents`, `onec_agent_tasks`, `onec_task_results`, `auth.onec_device_authorizations`) — `0028 store_agent`, qolganlari — `0029 onec_integration`".
- [T-021] §4.5 (3527–3636): D-02 jadvalidagi 14 funksiya — to'liq SQL (naqsh mavjud funksiyalar bilan bir xil: `SECURITY DEFINER`, `SET search_path = app, auth, pg_temp`, `ALTER FUNCTION … OWNER TO erp_system`, `REVOKE ALL … FROM PUBLIC`, `GRANT EXECUTE … TO erp_app`); 3530-qatordagi "qolgan AS yozuvlari ham … qo'shiladi" jumlasi → "AS yozuvlari to'liq ro'yxati — quyida (14 §19 bilan aynan)". `auth_suspend_tenant` izohi (3610–3611): "`sessions` o'zgarmaydi — kirish Redis `sub_status` orqali to'xtaydi".
- [T-056] 3681–3710 `onec_device_auth_approve` → `RETURNS text` (`'approved'|'not_found'|'expired'|'used'`); W-03/W-04 shu natijani `404 ONEC_PAIRING_CODE_INVALID` / `409 ONEC_PAIRING_CODE_EXPIRED` ga xaritalaydi.
- [T-232] Yangi `app.onec_device_auth_deny(p_user_code text, p_user_id uuid) RETURNS text` (`'denied'|'not_found'|'expired'|'used'`; `status='denied'`), naqsh boshqa `onec_device_auth_*` bilan bir xil.
- [T-020] §6.1: `platform.oauth_clients` (+`status`, `pending_secret` CHECK) 0007 qatoridan **0003 `auth_schema`** qatoriga ko'chiriladi ("auth FK'lari uchun oldin"); 0007 izohidan olinadi.
- [T-022] §6.1 0028 qatori ikkiga: `0028 store_agent` (Bosqich 5) va `0029 onec_integration` (Bosqich 7) — D-01 §2 tarkibi bilan; jadvallar soni izohlari ("19 ta" = 4 umumiy + 15 1C ga xos) moslanadi.
- [T-021] §6.1 0027 qatori: funksiyalar soni "jami 12" → "jami 26" (12 + D-02 dagi 14); §6.2 CI SECURITY DEFINER ro'yxatiga yangi funksiyalar (va `onec_device_auth_deny`).
- [T-013] §5.2 tenant-provisioning seed'i: standart filial ombori `type='store'`, `inventory_account='2920'`.
- [T-185] 4016-qator → "`15-xavfsizlik-va-audit.md` §3.3, `14-autentifikatsiya-oauth2.md` §19".

#### `13-provodka-qoidalari.md`
- [T-255] 5-qator "BP-01…12" → "BP-01…15"; "## 2.25 Posting qamrovi" bo'limi `###` darajasiga tushiriladi va §2.24 dan keyin, §2.26 dan oldin joylashtiriladi.
- [T-027, T-025] §1 hisoblar ro'yxatiga: `6310 | Xaridor va buyurtmachilardan olingan bo'naklar | P | kontragent | S1`.
- [T-257] §2.1a 1a-qator → `1a = (list_total − list_vat) − (net_total − net_vat)` (1 tiyin muvozanat).
- [T-242] 103-qator `customs_vat_base` → "MVP'dan keyin (sxemada yo'q)".
- [T-152] §2.4 (121) → "QQS to'lov usullari bo'yicha bo'linadi: har to'lov `p` uchun `vat_p = ROUND_HALF_UP(vat_total × p.amount / total, 2)` (oxirgi to'lov — qoldiq); `Dt acct(p) / Kt 9020 = p.amount − vat_p`, `Dt acct(p) / Kt 6410 = vat_p`; tannarx qatori bitta".
- [T-031] §2.5 (127–131): "`refund_method` = `cash` → `Kt 5010`; `card`/`uzqr`/`click`/`payme`/`uzum` → `Kt 5710` (`payment_method` = `refund_method`); `debt_adjustment` → `Kt 4010`. Qarzli sotuv qaytarilsa avval sotuvning ochiq qarzi (`Kt 4010`, chek yo'q), qolgani pul bilan (D-13)".
- [T-123] §2.5 #48 bandi (133) → D-20 matni: "`+qty` asl partiyaga va shu miqdor `stock_lots.blocked_qty` ga; FIFO/sotuv `qty_left − blocked_qty` dan; `write_offs` (`expired_return`) `post`ida `blocked_qty` va `qty_left` kamayadi; provodka 2.12 bo'yicha".
- [T-029] §2.6 va §2.12 ostiga havola, §4.3 ga D-15 qoidasi: "`regime='turnover'` tenantda 2.6 1-qatori = faktura summasi QQS bilan (`stock_lots.unit_cost` QQS bilan), 2-qator (`Dt 4410`) yozilmaydi; 2.12 dagi sovg'a QQS qatori yozilmaydi; `vat_moves` yozilmaydi".
- [T-131] §2.8 ga risk-flag provodkasi: "`Dt 4410 / Kt 6010` — `doc_type='goods_receipts'`, `doc_id` = bog'langan kirim, `entry_date` = belgilash kuni (joriy ochiq davr)".
- [T-242] 192-qator `last_purchase_cost` manbasi → "eng so'nggi `goods_receipts` partiyasi `stock_lots.unit_cost`; yo'q bo'lsa `avg_costs.avg_cost`".
- [T-024, T-120, T-025] §2.14 (217–224): allokatsiya tartibi → "avval `sales`/`debt_openings` `ORDER BY COALESCE(due_date, doc_date), doc_date, doc_id`, keyin `debt_writeoffs` (eng eskisi)"; chegara → "`amount ≤ receivable_balance + Σ written_off_open` (online/REST; oshsa `422`, #45)"; yangi qator "1b — offline ortiqcha qism (`debt_payments.unallocated_amount`): `Dt 5010/5710 / Kt 6310` (kontragent); hal qilish — `cash_movements` `other`/`out` `account='6310'` yoki `ledger_adjustments` `Dt 6310 / Kt 4010` (qaror #67)"; `method='bank'` — chek yo'q.
- [T-256] §2.16 (257) QQS krediti proporsiyasi → "`vat_i = ROUND_HALF_UP(invoice_vat × alloc_i / invoice_total, 2)`, faktura bo'yicha yopuvchi to'lov qoldiqni oladi".
- [T-242] 269-qator `doc_type=expense` → `doc_type='expenses'`.
- [T-027] §2.18 jadvaliga: `other` (`out`) | `account` (standart `9430`) | 5010; `other` (`in`) | 5010 | `account` (standart `9390`); izoh: "`account` ∈ `9430`, `9390`, `6310`, `4010`, `4730` (Buxgalter/Egasi tanlaydi); `6310`/`4010` da `counterparty_id`, `4730` da `employee_id` majburiy; `reason↔direction` juftligi — `collection`/`owner_withdrawal` → `out`, `deposit` → `in`".
- [T-088] 308, 321, 516-qator "Buxgalter o'zgartira oladi/tanlashi mumkin" → "Egasi BO-14 da o'zgartiradi (`settings.tenant`)".
- [T-128] §2.23 (374) ga istisno: "`account_dt` yoki `account_kt` = `0000` bo'lgan boshlang'ich balans yozuvi — `doc_date = go_live_date − 1` ruxsat (shu davr yopilmagan bo'lsa)".
- [T-032] §2.26 (382) → "bitta (tenant, davr) uchun bitta faol `vat_offset`; bitta (filial, davr) uchun bitta faol `turnover_tax`. `vat_offset` tenant bo'yicha `vat_moves` dan (#31 — 1 tenant = 1 STIR), `branch_id` — tenantning `is_default` filiali".
- [T-043] X-02 (428–432) ga D-19 §3: "`stock_counts` `post`dan keyin kelgan, `started_at < moved_at ≤ line.counted_at` harakat → avtomatik tuzatuvchi inventarizatsiya qatori (§2.11 provodkasi, `entry_date` — joriy ochiq davr) + `sync_exceptions(kind='count_late_move')`".
- [T-258, T-124, T-134] §3.1: FIFO tartibi `ORDER BY received_at, id WHERE qty_left − blocked_qty > 0`; AVECO va manfiy qoldiq — D-21 §1–§3 formulalari; FIFO↔AVECO almashtirish — D-21 §4.
- [T-131] §3.3 recost: "eski qator storno (`reversal_of_id`) + yangi qator, `doc_type`/`doc_id` = asl chiqim hujjati, `analytics.recost_job_id`; `entry_date` = asl sana (davr ochiq bo'lsa); tartib `ORDER BY moved_at, created_at, id`; yopilgan davrga tegsa — joriy ochiq davrda tuzatish".
- [T-260] 503-qator "QQS hisoboti keyingi oyning 15-sanasigacha tuziladi" → "QQS hisoboti topshirish muddatigacha (keyingi oyning 20-sanasi, SK 273-modda) shaxsiy kabinetga joylashtiriladi".
- [T-126] §4.3 (508–510): baza → "`(9020 − 9040 − 9050) + 9390 + 8530` (filial, davr)"; stavka → `platform.turnover_tax_rates`: tamaki (`products.turnover_tax_group='tobacco'`) 4%; `tenants.legal_form='sole_proprietor'` → 1%; chakana — `branches.settlement_category` bo'yicha.
- [T-127] §4.3 ga: "davlat hisobotidagi 0102 = Σ `fiscal_receipts` (`sale`/`return`/`debt_settlement`) chek sanasi bo'yicha; ledger daromadi (sotuv kuni, #30) bilan farq — «qarzga sotuv vaqt farqi» izoh qatori".
- [T-028] §5.1 ga D-06 §1–§2 va §4–§5 qoidalari (kech POS voqealari, `correction_of_period`, readiness bloker/ogohlantirishlari, faqat eng eski ochiq oy).
- [T-132] §5.2 ga: "asl hujjat yopilgan davrda bo'lsa ham `cancel` ruxsat — storno joriy ochiq davr sanasida".
- [T-251] 566-qator "1C eksportida 0000 → 000" → "Bosqich 7 da 1C ga yuborilmaydi (33 §6.12); keyin `ВводНачальныхОстатков`".
- [T-128] §5.5 ga: "yopuvchi `ledger_adjustments` — §2.23 istisnosi bilan `go_live_date − 1`".

### G-c — `14`–`20`

#### `14-autentifikatsiya-oauth2.md`
- [T-234] 42-qator sarlavhasi `oauth_clients.name` → `oauth_clients.client_id`.
- [T-021] §2 diagrammasi (70–80): "authorization_codes INSERT" → `app.auth_issue_code(...)`; "sessions INSERT" → `app.auth_issue_tokens(..., p_with_session=true)`; login xatolari → `app.auth_record_login`.
- [T-233] 126-qator → "lokautda A-01, A-02, A-03 → `403`; A-04…A-10 ruxsat".
- [T-021] 153-qator "tenant kontekstisiz phone↔chat_id" → "`app.auth_telegram_chat_by_phone(phone)` (SECURITY DEFINER, 12 §4.5)".
- [T-234] 168-qator `users.pin_hash` → `user_credentials.pin_hash`.
- [T-280] §4 ga parol siyosati: "parol 8–128 belgi; argon2id"; (07 BO-21 bilan bir xil).
- [T-186] §16.1 dagi 1–5 raqamli ro'yxat bandlari `#### 16.1.1 …` – `#### 16.1.5 …` sarlavhalariga aylantiriladi (mavjud `16.1.1a` — 16.1.1 ostida qoladi); shunda 11, 12, 15, 20, 23 va 14 ichidagi `§16.1.N` havolalari o'zgarishsiz to'g'ri bo'ladi.
- [T-021] 372, 388-qator → "`app.auth_suspend_tenant(tenant_id, true)`: `refresh_tokens.suspended_at = now()`, `revoked_reason = 'subscription'`; `sessions` o'zgarmaydi — kirish Redis `sub_status` orqali to'xtaydi" ("revoke" so'zi olinadi).
- [T-144, F-05] §16 ga: "`trial` (30 kun) tugasa → `grace` (24 soat) → `restricted`; `closed` — faqat platforma admini (avtomatik emas, qaror #70)".
- [T-121] 440–443 va 580-qator "SMS OTP" → "OTP (`purpose=data_export`) — Telegram birinchi, SMS zaxira (#34)"; §16.5 ga "faqat `billing.manage` (Egasi); boshqa rolga `403 FORBIDDEN`".
- [T-195] 484-qator "(endi `/admin/users` bilan aralashmaydi)" → "(tenant `/admin/users` dan alohida)"; 533-qator → "`users` — id, phone, name, locale; parol/PIN heshlari `user_credentials` da".
- [T-279] §18.2 ga `GET /admin/users` (ro'yxat: `{items:[{user_id, name, phone, role_ids, branch_ids, status, last_login_at}], next_cursor}`) va `POST /admin/users` tanasi (`{phone, name, role_ids, branch_ids}` → taklif OTP `purpose=invite`) — ruxsati jadvaldagi mavjud xodim boshqaruvi kodi bilan.
- [T-234] 536-qator `oauth_clients` izohi → "`client_secret_encrypted` NULL = `public` mijoz yoki `status='pending_secret'`".
- [T-021] 549-qator (§19 RLS/funksiyalar) — "va h.k." olib tashlanadi; D-02 jadvalidagi funksiyalar va mavjud 4 tasi (`auth_consume_code(p_code_hash)`, `auth_rotate_refresh(p_token_hash, p_new_token_hash, p_new_expires_at)`, `auth_revoke_tenant(p_tenant_id, p_reason)`, `auth_suspend_tenant(p_tenant_id, p_suspend)`) 12 §4.5 dagi imzolar bilan aynan sanab o'tiladi.
- [T-101] 565-qator `/auth/signup` tanasiga `owner_name` (2–100), `legal_form` (`llc|jsc|private_enterprise|sole_proprietor`), `accepted_terms_version` (majburiy, joriy `platform.terms_versions` (`kind='terms'`, `is_current`) bilan mos, aks holda `422 VALIDATION_ERROR`), `ai_cross_border_consent` (ixtiyoriy); server `tenants.accepted_terms_at`, `accepted_terms_ip` yozadi.
- [T-056] 609-qator: approve natijalari `approved|not_found|expired|used` (12 §4.5).
- [T-200] 622-qator → "(#14 veb-kassa autentifikatsiyasi, #3 — 401 qayta kirish qismi, #4 CSRF, #13 obuna holati)".

#### `15-xavfsizlik-va-audit.md`
- [T-045] 63-qator seed → "provisioning'da `valuation_method_history(method='aveco', valid_from=go_live_date)` qatori"; `settings.valuation_method` iborasi olinadi.
- [T-014] 108-qator `tax.correction.submit` tavsifi → "Davlat hisobotiga tuzatish yoki tasdiqni qayd etish".
- [T-273] 127-qator `billing.manage` → "Obuna to'lovi (oy/yil), qo'shimcha kassa, to'lovlar tarixi".
- [T-034] 154-qator Kassir ustuni `returns.approve` → "✓(limit, 100 000)".
- [T-001] 225-qator → "`approval_requests(status='pending')` yaratiladi, hujjat `draft` da qoladi (#25; yagona istisno — `price_changes` → `pending_approval`)".
- [T-190] 373-qator `§16.5`, `§18.1` → `` `14` §16.5 ``, `` `14` §18.1 ``.
- [T-121] 408-qator → OTP Telegram birinchi, SMS zaxira.
- [T-101] §1.5 ga: "Foydalanish shartlari aksepti — signup'da (`accepted_terms_version`, `_at`, `_ip`)".

#### `16-offline-sync.md`
- [T-236] 12, 92–93-qator misollariga `device_id`, `actor_user_id`; 54-qator `+05:00` → `Z` (UTC).
- [T-246] 16-qator UzQR "faqat online" havolasi → `18` §4.1.
- [T-024] §1 `customers` qatoriga: "+ `open_debt_docs[]` (faqat `receivable_balance > 0` mijozlar): D-04 §1 sxemasi"; [T-066] §1 ga yangi qator: "Qoldiq (`stock_balances`, shu filial omborlari) | `stock` | katalog bilan birga | Delta (`scope=stock`), faqat ko'rsatish".
- [T-002] 65-qator `expense.created` izohi → "(POS-14 «Xarajat», `source=cash`; payload — `18` §13.2)".
- [T-007] 68-qator → "`receipt_seq` — `integer|null` (fiskal chek yaratilmaydigan faqat-qarz sotuvda `null`)".
- [T-067] 99-qator → "push va pull'ning har so'rovida `devices.last_seen_at = now()` (push'da `last_sync_at` bilan bitta tranzaksiyada)".
- [T-154, T-007] 116-qator → "`receipt_seq` qurilmadan keladi; takror bo'lsa: voqeada `fiscal_result` bor (FM imzolagan) — qabul, server `receipt_seq` ni smenadagi `max+1` ga qayta raqamlaydi, `sync_exceptions(kind='receipt_seq_conflict')`; `fiscal_result` yo'q — `rejected`, `RECEIPT_SEQ_CONFLICT`, `retryable:false`".
- [T-066] §3.2 ga jadval "scope → javob kaliti → manba": `catalog` → `catalog` (`products`, `product_categories`, `units`); `barcodes` → `barcodes`; `prices` → `prices`; `customers` → `customers` (+`open_debt_docs`); `limits` → `limits`; `permissions` → `permissions`; `marking_codes` → `marking_codes`; `fiscal` → `fiscal`; `settings` → `settings`; `stock` → `stock`; `all` — hammasi.
- [T-028] §3.4 (145) ga: "POS voqeasi `PERIOD_CLOSED` bilan rad etilmaydi — D-06 (qaror #69): registr yozuvlari birinchi ochiq davrda, `sync_exceptions(kind='late_in_closed_period')`".
- [T-121] 156-qator OTP → Telegram birinchi, SMS zaxira.
- [T-069] §5 (243) "`limit_exceeded=true` bayrog'i" → "`sync_exceptions(kind='approval_limit_exceeded_offline')` + `doc_approvals` + M18"; §5 ga `sync_exceptions.kind` ro'yxati (D-12) — har tur bir qator ta'rif.
- [T-026] 255-qator → "natija (`fiscal_result`: `fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`, `fiscal_at`) chek voqeasi bilan `/sync/push` ga boradi (`18` §4.1, D-05)".
- [T-113] 258-qator `OFFLINE_FISCAL_BLOCK_HOURS` → `OFFLINE_BLOCK_HOURS`.
- [T-237] 267-qator blok ro'yxati → "(sotuv, qaytarish, kredit cheki, `debt_settlement`)" ("avans" olinadi).
- [T-043] §8 (303, 305) → "`effective_created_at = clamp(created_at, received_at − OFFLINE_CLAMP_WINDOW, received_at + CLOCK_SKEW_WARN_S)`; `doc_date`, 48 soat hisobi va `stock_moves.moved_at` shundan; xom qiymat `sync_receipts.result.client_created_at` da".
- [T-068] 312-qator `device_name` → `cash_register_name` (hisoblanadi) + `kind` + `app_version`.

#### `17-api-umumiy.md`
- [T-201] 5-qator "Bog'liq fayllar" dan `spec/README.md` → `00-README.md`.
- [T-228] §2 ga istisno: "M19 buyruq yo'llari (`/onec-agents/pair`, `/refresh`, `/auto-match`, `/discover-bases` va h.k.) — holat/buyruq amallari, `/{resurs}/{id}/{fe'l}` naqshidan istisno".
- [T-280] §3 ga: "erkin matn maydonlari (`comment`, `note`, `reason`) — ≤ 1000 belgi, agar endpointda boshqacha yozilmagan bo'lsa".
- [T-217] 65-qatordagi sahifasiz ro'yxatlar istisnosiga `warehouses`, `cash-registers` qo'shiladi.
- [T-278] 148-qator `stock-counts/{id}/review` → `stock-counts/{id}/submit-for-review`.
- [T-082] 152-qator bilan 20:11 mos (bir bosqichli: `cash-movements`, `ledger-adjustments`, `supplier-payments`).
- [T-001] 161-qator → "`202 {status:"draft", approval_request_id}` (`APPROVAL_REQUIRED`); `pending_approval` holati faqat `price_changes` da (#25)".
- [T-142] 162-qator "faqat Egasi" misollaridan `platform.admin` olinadi; alohida qator "faqat `platform_admins` (`aud=urn:erp:platform`)".
- [T-098] 201–202-qator → "`kind='import'` — `catalog.manage` yoki `stock.opening.manage` yoki `bank_settlements.manage` (biri yetarli)".
- [T-081] 212-qator → "eksport formati so'rov tanasidagi `format: "xlsx"|"pdf"` maydoni bilan".
- [T-238] 254-qator `PIN_INVALID` "Qachon" ga "approval-requests approve (PIN)"; 277-qator `DEBT_LIMIT_EXCEEDED` ga "offline sync'da xato emas — `200` `warnings[]` da".
- [T-114] 302-qator `MARKING_VERIFY_UNAVAILABLE` matni → "…markirovkali tovarni hozir sotib bo'lmaydi (qat'iy rejim)".
- [T-014] `EIMZO_SIGN_FAILED` "Qayerda" ustunidan davlat hisoboti tuzatishi olinadi.
- [T-282] Ishlatilmaydigan kodlar joylashtiriladi: `NEGATIVE_STOCK_NOT_ALLOWED` → "Qayerda: `19` write-offs/transfers `post` (`settings.negative_stock_policy='block'`)"; `DEBT_ALREADY_PAID` → "`18` §12.5 (qoldiq 0)"; `DOUBTFUL_FLAG_REQUIRES_OWNER` → "`18` §12.6"; `RECOST_REJECTED_PERIOD_CLOSED` → "`19` recost-jobs retry"; `INVALID_CREDENTIALS` → "BO-01 login".
- [T-028, T-013, T-146, T-155, T-022] §15 ga yangi kodlar: `PERIOD_CLOSE_OUT_OF_ORDER` (409, "faqat eng eski ochiq oy yopiladi", 20 #15); `WAREHOUSE_ACCOUNT_LOCKED` (409, "omborda harakat bor — tovar hisobini o'zgartirib bo'lmaydi", 20 #37a); `AI_FEATURE_DISABLED` (403, `params.feature`, 20 #73); `COUNT_LINES_INCOMPLETE` (422, `params.uncounted_count`, 19 stock-counts post); `AGENT_CAPABILITY_DISABLED` (409, `params.capability`, agent vazifasi navbatga qo'yilganda). Katalog jami soni qayta sanaladi (`ONEC_*` 81 o'zgarmaydi).

#### `18-api-kassa.md`
- [T-002] 11-qator → "… `cash_movement.created`, `counterparty.created`, `expense.created` (POS-14 «Xarajat», `source=cash` — §13.2), …"; §1 indeksiga `expense.created` qatori.
- [T-061] 120, 121, 124-qator `approved_by_user_id` → `approved_by`; [T-111] 124-qator qayta ishlatilgan so'rov → `409 APPROVAL_REQUEST_ALREADY_RESOLVED` (`APPROVAL_INVALID` — faqat huquq/limit yetmasa yoki `ApprovalRef` kelmasa).
- [T-239] 183-qator "`stock`/`cash_moves` registridan" → "`cash_moves` (`shift_id`, `method='cash'`)".
- [T-107] 212-qator Z-hisobot ruxsati → "`reports.sales.view` yoki `cash.count.shift`".
- [T-026] §4.1 jadvaliga `fiscal_result` (`object|null`, shartli — lokal ko'prik rejimida FM imzolagan bo'lsa majburiy; `{fm_terminal_id, fm_receipt_seq, fiscal_sign, qr_url, fiscal_at}`); xuddi shu maydon §7.1 (`return.created`) va §12.2 (`debt_payment.created`) payload'lariga.
- [T-007] 229-qator `receipt_seq` → `integer|null` ("faqat-qarz sotuvda va `credit_sale_receipt='none'` da `null`; aks holda majburiy").
- [T-118] §4.1 ga `credit_receipt_seq` (`integer|null`; `FiscalPolicy.credit_sale_receipt='credit_type'` va `payments[]` da `debt` bo'lsa majburiy — `kind='credit_sale'` cheki uchun).
- [T-106] §4.1 ga `delivery` (`printed|electronic`, standart `printed`) va `delivery_reason` (`printer_failure|customer_request|null`, `electronic` da majburiy).
- [T-057] 243-qator `line_id` → `id` ("qurilma beradi — `sale_lines.id`").
- [T-059] 250–254-qator: "`discount_amount` — hisob manbai; `discount_source` berilsa `discount_amount > 0` majburiy va aksincha; `discount_pct` — faqat ma'lumot"; §4.4 (295): "server `pct_i = discount_amount_i / ROUND_HALF_UP(qty × price, 0) × 100` ni o'zi hisoblaydi; chek chegirmasi qatorlarga `line_gross` ulushida taqsimlanadi (qoldiq eng katta qatorga, `discount_source='manual'`); limit `Σ discount_manual / Σ line_gross × 100` bo'yicha".
- [T-239] 256-qator `marking_offline` → "saqlanmaydi — `sales.is_offline` dan hisoblanadi".
- [T-058] 258-qator → "`line_total`, `vat_amount` — qurilma #26 formulasi bilan hisoblaydi, server tekshiradi (mos kelmasa `VALIDATION_ERROR`); `cost_amount` — qurilma yubormaydi, faqat server (FIFO/AVECO)"; `lines[]` jadvaliga `line_total`, `vat_amount` (Money, majburiy) qatorlari.
- [T-117] 267-qator "POS standart qiymati `personal`" → "standart qiymat yo'q — kassir terminal chekiga qarab tanlaydi (qaror #64)".
- [T-246] §4.1 ga: "`is_offline=true` va `method='uzqr'` → `VALIDATION_ERROR` (`message_key=validation.uzqr_online_only`)".
- [T-114] 284-qator "(javob bermaganda offline siyosatini taklif qiladi …)" → "qator chekka qo'shilmaydi; offline/zaxira yo'l yo'q (qaror #62)".
- [T-026, T-007] §4.5 (299): `fiscal.status` ∈ `"pending" | "fiscalized" | "deferred"`; 303-qatordagi "(`fiscal_receipt_seq` shunga qaramay saqlanadi)" olinadi → "`fiscal_receipt_seq = null`".
- [T-118] §4.5 aralash to'lov (304): "aralash chek qatorlari — D-04 §3 formulasi, `ratio = non_debt_amount / total_amount`; keyingi `debt_settlement` qatorlari `line_total_i − settled_amount_i` qoldiqdan"; `credit_type` da ikkinchi chek `credit_receipt_seq` bilan.
- [T-063, T-235, T-249] §4.6 (313): `PAYMENT_NOT_CONFIRMED`, `DEPENDENCY_NOT_SYNCED` qo'shiladi; `RECEIPT_SEQ_CONFLICT` izohi → "`UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)`; `fiscal_result` bor bo'lsa qayta raqamlanadi (D-05)".
- [T-060] 326-qator javob `total` → `total_amount`.
- [T-031, T-008] §7.1 (400–426): `receipt_seq` → `integer|null` (pul bilan qaytarilgan qism 0 bo'lsa `null`); `refund_method` → `cash|card|uzqr|click|payme|uzum|debt_adjustment` (standart — asl to'lov usuli; Click/Payme/Uzum puli provayder kabinetida qaytariladi); qarzli sotuv qoidasi va qator summasi — D-13 §1, §5; 422-qator `unit_price` (Money) → `price` ("o'nlik satr, 4 xona — `sale_lines.price` bilan bir xil; faqat ma'lumot, summa server hisoblaydi").
- [T-123] 426-qator `restock=false` → "qoldiqqa sotuvga yaroqli bo'lib qaytmaydi: `+qty` asl partiyaga va `stock_lots.blocked_qty` ga (D-20)".
- [T-239] 445-qator `without_receipt` → "= `sale_id IS NULL`"; 500-qator `"25"` → `"25.00"`.
- [T-001] 554-qator → "`202 {status:"pending_approval", approval_request_id}`".
- [T-149] §11 (585, 603, 610) — yagona manba: GET → `sales.create | debts.create | stock.view | purchases.create`; POST → `debts.create` (tezkor mijoz) / `debts.limit.manage` (to'liq) / `purchases.create` (`is_supplier=true`); PATCH → `debts.limit.manage | purchases.create`.
- [T-119] 628-qator `FiscalPort.issue_credit_payment()` → `FiscalPort.register_sale(kind='debt_settlement')`; tovar qatorlari — D-04 §3 formulasi.
- [T-023, T-024] §12.2 (630–651): `branch_id`, `cash_register_id`, `shift_id` — majburiy (`shift.status=open`); yangi `receipt_seq` (int, majburiy); `method` → `cash|card|uzqr|click|payme|uzum` (`bank` — faqat §12.3); yangi `allocations[]`, `fiscal_lines[]` (D-04 §4); 647-qator → "allokatsiya — `shared/lib/debt-allocation` (D-04 §2) tartibi bilan; qurilma hisoblaydi, server qayta hisoblaydi va farqni `sync_exceptions(kind='debt_allocation_mismatch')` ga yozadi (rad etmaydi)"; 651-qator → "offline to'liq ishlaydi; lokal ko'prikda chek FM'da darhol imzolanadi (`fiscal_result`); `outbox_jobs(kind='ofd_send')` faqat `partner_cloud` rejimida; havola → `16` §6".
- [T-025, T-120] 637-qator `amount` → "> 0; online — `≤ receivable_balance + Σ written_off_open`, oshsa `422 VALIDATION_ERROR` (`debt_payment_exceeds_balance`, #45); `is_offline=true` — rad etilmaydi: chegaragacha allokatsiya, qolgani `unallocated_amount` (`Kt 6310`), `sync_exceptions(kind='debt_overpayment_offline')` + M18 (qaror #67)".
- [T-063, T-235] §12.2 xatolariga `PAYMENT_NOT_CONFIRMED`, `DEPENDENCY_NOT_SYNCED`.
- [T-023] §12.3 (654–659) → "`POST /api/v1/debt-payments` (back-office, BO-06): faqat `method='bank'` — kassasiz, fiskal chek yo'q; `branch_id` majburiy; boshqa usul → `422 VALIDATION_ERROR` (`message_key=validation.debt_payment_backoffice_bank_only`)".
- [T-151] §12.3–§12.5 ga `POST /{id}/cancel` (`{reason}`; ruxsat: debt-payments — `debts.payment.accept`, debt-openings — `stock.opening.manage | debts.limit.manage`, debt-writeoffs — `debts.forgive`) va `GET` ro'yxat/bitta (`reports.sales.view` yoki yaratuvchi ruxsati); bekor qilish — storno joriy ochiq davrda.
- [T-282] §12.5 xatolariga `DEBT_ALREADY_PAID`; §12.6 ga `DOUBTFUL_FLAG_REQUIRES_OWNER`.
- [T-143] 680-qator `unflag` ruxsati → `debts.forgive` (Egasi); 847-qator `GET /payments/checkouts/{ref}` → `sales.create`.
- [T-077] 692-qator `bucket` qiymatlari → `0-30|31-60|60+`.
- [T-064] §13.1 ga `counterparty_id` (`UUID|null`; `reason=owner_withdrawal` va `tenants.legal_form ≠ sole_proprietor` bo'lsa majburiy, `counterparties.is_founder=true`; `reason=other` va `account ∈ {6310, 4010}` bo'lsa majburiy).
- [T-002, T-027] §13.1 (705–714): `reason` enum'idan `expense` va `expense_category_id` qatori olinadi; `reason↔direction` juftligi (D-17 §1); ixtiyoriy `account`, `employee_id` (D-17 §2); yangi **§13.2 Voqea: `expense.created`** — D-18 (payload, ruxsat `cash.withdraw` (limit), `approval`, server `ExpensePostingService` bilan darhol `posted`).
- [T-104] 734-qator `GET /fiscal-receipts` ruxsati → "`reports.sales.view` yoki `sales.create` (faqat o'z filiali)"; [T-105] 735-qatorga `?debt_payment_id=` filtri, javobga `debt_payment_id`; `receipt.reprinted` payload → `{fiscal_receipt_id}` (majburiy), `sale_id` ixtiyoriy.
- [T-065, T-108] 755–756-qator `POST /einvoices` tanasi → `{direction:"out", counterparty_id, related_doc_type:"sales"|null, related_doc_id|null, doc_date, lines?}` (`source`, `sale_id` olinadi); "`counterparty.kind='company'` va sotuvda `method=debt` bo'lsa server `sale.created` postingida `draft` ni o'zi yaratadi; POS chaqirmaydi" — majburiy qoida.
- [T-062] 849-qator enum'ga `consumed`; §16.1 ga "sotuv/qarz to'lovi posting'i checkout'ni `confirmed → consumed` qiladi; `confirmed` bo'lmasa yoki `consumed` bo'lsa → `PAYMENT_NOT_CONFIRMED`".
- [T-028] 914-qator `PERIOD_CLOSED` "Qayerda" → "faqat back-office REST; POS sync voqealari rad etilmaydi (`16` §3.4, qaror #69)".
- [T-063] 916-qator `PAYMENT_NOT_CONFIRMED` "Qayerda" → "§4.6, §12.2"; [T-235] §18 jadvaliga `DEPENDENCY_NOT_SYNCED` ("§4.6, §7.1, §12.2 — retryable").

#### `19-api-ombor.md`
- [T-001] 13-qator → "`price-changes` — `draft → pending_approval (202) → posted | rejected` (§4)"; 216-qator → "`202 {status:"pending_approval", approval_request_id}` (`APPROVAL_REQUIRED`) — `approval_requests(kind='price_change')`; `price_changes` — `pending_approval` ga o'tadigan yagona hujjat turi (qaror #25); `product_prices` hali o'zgarmaydi"; 219-qator xatolariga `409 DOC_INVALID_STATE` (`pending_approval` da `post`); 223-qator → "approve — `product_prices` yangilanadi, hujjat `posted`; reject — hujjat `rejected`, narx o'zgarmaydi; `approval_requests` `expired` bo'lsa hujjat `draft` ga qaytadi"; `post` faqat `draft` dan.
- [T-074] 14-qator `suppliers` → `counterparties` (`is_supplier=true`).
- [T-134] 16, 783-qator → "usul almashtirish — `13` §3.1 (FIFO↔AVECO o'tish algoritmi)".
- [T-203] 78-qator `Product` javobiga `marking_group_code`.
- [T-204] 98-qator `vat_rate` "Majburiy: ha" → "shartli (`vat_rate` yoki `vat_exemption_code`)".
- [T-143] 146, 164, 168-qator `mxik-codes/{code}`, `product-categories` PATCH/archive → `catalog.manage`; 298, 310 `import-jobs/{id}/validate`, `…/errors` → `POST /import-jobs` bilan bir xil; 670 `stock-counts/{id}/lines/{line_id}` → `stock.count.create`; 827 `recost-jobs/{id}` → `stock.view`; 851 `einvoices/{id}` → `purchases.post`.
- [T-153] §4 `post` (214) ga formula: "`base` = filial narxi, yo'q bo'lsa global narx; `base` yo'q — limit tekshirilmaydi; `pct = |new − base| / base × 100`; bitta qator oshsa butun hujjat tasdiqqa, `requested_value = max(pct)`".
- [T-206] 219, 385, 463-qator `params.resource` → birlik: `price_change`, `counterparty`.
- [T-207] 242-qator yorliq shabloni javobiga `code`.
- [T-181] 266-qator `` `17-api-umumiy.md` §attachments `` → `§12`.
- [T-202] 294, 307-qator `total_rows:null`, `result:null` → `0`, `{}`.
- [T-276] 359-qator `ai.cross_border_enabled` → `tenants.settings.ai_cross_border_enabled`.
- [T-033, T-103] §8 (368–383) jadvali va `PATCH` ga: `lines[].marking_codes: string[]` (`is_marked=true` da majburiy, soni = `qty`, GS ajratgichlari aynan), `lines[].discrepancy_reason` (`short|excess|damaged|wrong_item|other`; `po_id` berilgan va `qty ≠ po_lines.qty` bo'lsa majburiy); izoh: "`po_id` berilsa `supplier_id`, `cost`, `vat_rate` PO va mahsulot kartasidan olinadi; `po_lines.price` NULL bo'lsa `cost` majburiy".
- [T-006] 382, 387-qator → `poa_id` (ixtiyoriy, `powers_of_attorney` dan) + `poa_number`; yangi **§8a E-ishonchnoma** — D-07 §3 endpointlari to'liq (ruxsat, so'rov, javob, xatolar, Idempotency); 1-qator (12) "e-ishonchnoma" bandiga §8a havolasi.
- [T-149] 430, 434, 447-qator `counterparties` ruxsatlari → "`18` §11 (yagona manba)".
- [T-071] 497-qator "`version` talab qiladi" olinadi; 502 va 570-qator `409 VERSION_CONFLICT` → `409 DOC_INVALID_STATE`.
- [T-073] 524-qator `target_doc_type` → `"goods_receipts"|"debt_openings"`.
- [T-072] 595-qator → "boshqa filial ombori (bir filial ichida ko'chirish yo'q — MVP'da filialda bitta ombor, #54); `from_branch_id`/`to_branch_id` ni server omborlardan oladi; `from_warehouse_id` ∈ `X-Branch-Id`".
- [T-070] 601-qator `lines[].qty` → `lines[].qty_sent`; 632-qator "`qty_received = qty`" → "`qty_received = qty_sent`".
- [T-130] `receive` (625–633) ga validatsiya "`qty_received ≤ qty_sent`, aks holda `422 VALIDATION_ERROR` (ortiqcha — alohida kirim hujjati)"; 632-qator "kamomad/ortiqcha provodkasi" → "kamomad provodkasi (`13` §2.10)".
- [T-003, T-116] 637-qator `ettn_status?` qiymatlari → `pending_signature|sending|registered|received|accepted|rejected|cancelled|failed`.
- [T-155] stock-counts `post` (678–688): "`counted IS NULL` qator bo'lsa `422 COUNT_LINES_INCOMPLETE`; `?treat_uncounted_as_zero=true` bilan majburlash (farq = `−expected`)"; 688-qator → "`posted` — storno (`cancel`); `counting`/`review` — registrsiz `cancelled`".
- [T-156] 720-qator → "javobgar belgilansa `4730`, aks holda `9430` (`13` §2.12)".
- [T-282] write-offs/transfers `post` xatolariga `NEGATIVE_STOCK_NOT_ALLOWED` (`settings.negative_stock_policy='block'`); recost-jobs retry xatolariga `RECOST_REJECTED_PERIOD_CLOSED`.
- [T-123] §15 hisobdan chiqarish: `expired_return` qatori `post` qilinganda `stock_lots.blocked_qty` kamayadi (D-20).
- [T-131] 857-qator risk-flag provodkasi → "`13` §2.8 (`doc_type='goods_receipts'`, `entry_date` — belgilash kuni)".
- [T-205] 849-qator `factura_type` ro'yxatidagi `/…` olinadi.
- [T-003] §20 (898–924): 898 holatlar ro'yxati D-08 §1 bilan; 903-qator javobi `counterparty_id`, `doc_date`, `receipt_id` — DDL ustunlari (12); 915-qator `{operator_doc_id, ettn_date}` → `{operator_doc_id, doc_date}`.
- [T-195] 962-qator "Limitdan katta — endi `202 APPROVAL_REQUIRED`…" → "Limitdan katta — `202 APPROVAL_REQUIRED` yo'li; bu kod faqat tasdiq so'ralmaganda".
- [T-264] 969-qator 26 #40 → 26 #117 (OQ-027).

#### `20-api-moliya-admin.md`
- [T-082] 11-qator → "`expenses`, `bank-settlements`, `tax-settlements` — uch bosqichli; `cash-movements`, `ledger-adjustments`, `supplier-payments` — bir bosqichli (`17` §9)".
- [T-077] 48-qator debts-aging ruxsati → "`reports.finance.view` yoki `debts.approve`"; 486–493 (#21): `bucket=0-30|31-60|60+` parametri; `rows[]` ga `due_date`, `overdue_since`; "`overdue_since = min(COALESCE(due_date, doc_date))` ochiq hujjatlar bo'yicha; `days_overdue = max(0, as_of − overdue_since)`; bucket shundan".
- [T-215] 53-qator "nomi/tavsifi" → "Rol nomini tahrirlash".
- [T-012] 69-qator → "Kassani tahrirlash"; indeksga `| 40i | POST /cash-registers/{id}/archive | M14 | Kassani arxivlash | cash_register.manage |`; yangi **40i** bo'limi: tana `{}`, `200 {id, archived_at}`, xatolar `409 RESOURCE_ARCHIVED`, Idempotency majburiy, bog'langan BO-12; 752 (#38 javobi `items[]`) va 765 (#39 javobi) ga `version`; 10-qatordagi M14 soni → 12 (yangi 37a bilan — 13; haqiqiy sanab yoziladi).
- [T-076] 71-qator indeks → "Do'kon nomi, yuridik shakli, bank hisobi va tenant siyosatlari"; 794-qator `store_name` → `name` (`tenants.name`), `locale` olinadi (til — `users.locale`).
- [T-208] 111-qator "(9 endpoint)" → "(10 endpoint)".
- [T-079] 151-qator `doc_type` → `sales|goods_receipts|returns|supplier_returns|write_offs|supplier_payments`.
- [T-078] 164-qator `tax_type` → `vat|turnover|property|land|pit|social`; #4 compare (171) ga: "`our_amount` faqat `vat`/`turnover` uchun hisoblanadi; boshqalarida `null`, holat `compared`".
- [T-223] 164-qator `published_at` → "ISO 8601 vaqt (`timestamptz`)".
- [T-014] yangi **7a. `POST /state-reports/{id}/confirm`** (D-10 §2); #8 (223–234): maqsad → "Kabinetda kiritilgan tuzatishni qayd etish (imzosiz)"; ruxsat → "`tax.correction.submit` — Buxgalter va Egasi (`15` §2.2)"; so'rov → `{comment (majburiy, ≤1000), portal_ref?: string}`; xatolardan `EIMZO_SIGN_FAILED` olinadi.
- [T-032] 8b (259–263): `branch_id` → "faqat `tax_kind='turnover_tax'` da majburiy; `vat_offset` da yuborilmaydi — server `branches.is_default` filialini yozadi"; dublikat xato matni → "`vat_offset` — (tenant, davr), `turnover_tax` — (filial, davr) uchun allaqachon bor".
- [T-132] 289, 334, 1199-qator va boshqa `…/cancel` xatolaridan `PERIOD_CLOSED` olinadi; izoh: "yopilgan davrdagi hujjat ham bekor qilinadi — storno joriy ochiq davr sanasida (`13` §5.2)"; 1100-qator (#54) ga `PERIOD_CLOSED` qo'shilmaydi.
- [T-009, T-128] #10 (319–320): so'rovga `branch_id: UUID (majburiy)`; `doc_date` istisnosi "`account_dt` yoki `account_kt` = `0000` bo'lsa `go_live_date − 1` ruxsat (davr yopilmagan bo'lsa)"; 320 va 346 javoblariga `branch_id`; 345 (#10b) filtriga `branch_id=`.
- [T-157] #18 (447–454) `total_sales = Σ sales.total_amount (posted) − Σ returns.total`; #12 (365–372) `revenue = Kt 9020`, `returns = Dt 9040`, `discounts = Dt 9050` (`net` rejimda Σ `sale_lines.discount_amount` QQSsiz), `cogs = Dt 9120`.
- [T-028] #15 (412) xatolariga `409 PERIOD_CLOSE_OUT_OF_ORDER` va bloker ro'yxati `recost_pending`/`fiscal_pending`/`devices_unsynced`; #16 (424) javobi — D-06 §4 sxemasi aynan (`warnings[]`, `unsynced_devices[]`, `opening_balance_unresolved`).
- [T-131] #16 `recost_pending` sharti → "`recost_jobs.status IN ('queued','running','failed') AND from_date ≤ period_end`".
- [T-068, T-216] #29a (617, 630, 631): `pending_events` → `outbox_pending_count`; `device_name` o'rniga `cash_register_name`, `kind`, `app_version`.
- [T-013] #31 (657–660): so'rovga `warehouse: {type: "store"|"stock"}` (standart `store`); javobga `warehouse: {id, type, inventory_account}`; yangi **37a. `PATCH /warehouses/{id}`** — D-14 §3.
- [T-222] #33/#35 (685): "`activity_type` va `settlement_category` o'zgarishi — `branch_tax_settings` ga `(branch_id, valid_from)` bo'yicha upsert (bir oyda ikki marta — oxirgisi amal qiladi)".
- [T-217] 739, 752-qator ro'yxat javoblari → "`{items}` — sahifasiz ro'yxat (`17`:65 istisnosi)".
- [T-022] #40 (777) so'roviga `fiscal_agent_id?: UUID|null`, `fiscal_local_device_id?: string|null` (birga); javobga ham; 752 (#38) `items[]` ga `fiscal_agent_id`, `txkm_contract_ref`.
- [T-219] 802-qator `discount_posting` → "standart `gross_9050`".
- [T-080] 803-qator `owner_withdrawal_account` → `"4890"|"8720"`, standart `legal_form` dan (`sole_proprietor` → `8720`, qolganlari → `4890`).
- [T-218] 804-qator `payment_org_commission_account` → "faqat `click/payme/uzum`; `card/uzqr` — doim `9430`".
- [T-220] `TenantSettings` (790–807) ga `negative_stock_policy` (`allow|block`) va `ai_training_consent` (bool) — `PATCH /tenant/settings` orqali (`settings.tenant`).
- [T-221] 816, 850-qator provider ro'yxati: "`fiscal_partner`, `eimzo` sirlari — platforma boshqaradi (deploy konfiguratsiyasi), tenant API'si yo'q".
- [T-090] 40d (848–860): `click`/`payme`/`uzum` tanasiga majburiy `provider_autofiscal_disabled_confirmed: true` → `settings.payment_providers.{p}.autofiscal_off_confirmed_at`; yo'q/false → `422 VALIDATION_ERROR`.
- [T-075] 858-qator → `503 {code:"EINVOICE_PROVIDER_UNAVAILABLE"}`.
- [T-002] #42 (942) "Offline" → "`source='cash'` — POS'dan `expense.created` voqeasi (`18` §13.2): ruxsat `cash.withdraw` (limit) — Kassirda `expenses.create` yo'q; server `ExpensePostingService` bilan darhol `posted`".
- [T-086] #45 (975) → "standart ro'yxat — `13` §2.17 seed xaritasi (21 kod)"; 978-qator → "`6410` — «Soliq to'lovi (byudjetga)» (`tax_payment`)".
- [T-087] #51 (1053–1057) javobi → "`201 {expense_id, status:"posted"}` yoki limitdan oshsa `202 {status:"draft", approval_request_id}` (`APPROVAL_REQUIRED`)"; xatolarga `EXPENSE_LIMIT_EXCEEDED`.
- [T-027, T-064] #53 (1085): `reason↔direction` juftligi (D-17 §1), ixtiyoriy `account` (`9430|9390|6310|4010|4730`, faqat `reason=other`), `employee_id` (`account=4730` da majburiy), `counterparty_id` (`owner_withdrawal` yoki `account ∈ {6310, 4010}` da majburiy); xatolarga `VALIDATION_ERROR` holatlari.
- [T-010] 1124-qator `BankSettlement` tavsifi → "`variance_amount` — faqat `method="collection"` (standart `"0.00"`): manfiy — kamomad (`Dt 5910`), musbat — ortiqcha (`Kt 9390`); `net_amount = gross_amount − commission_amount + variance_amount`"; yangi **55h. `PATCH /bank-settlements/{id}`** — faqat `draft`, `{gross_amount?, commission_amount?, variance_amount?, settled_from?, settled_to?, bank_ref?, comment?, version}`, ruxsat `bank_settlements.manage`, xatolar `DOC_NOT_DRAFT`, `VERSION_CONFLICT`, `VALIDATION_ERROR`.
- [T-083] 55g (1214–1215) (3)–(4)-band → "moslashtirish birligi — (filial, usul, `entry_date`) kunlik 5710 debet yig'indisi; eng eski kunlardan boshlab `n` ta kun `Σ ≥ kirim` va `(Σ − kirim) / Σ ≤ 5%` bo'lgan eng kichik `n`; shu import ichidagi va ochiq `draft` larda band qilingan summa ayiriladi; `commission_amount < 0` yoki `≥ gross_amount` → qoralama yaratilmaydi, `unmatched_lines` (`reason:"commission_invalid"`)"; [T-210] 1215-qator `import_id` izohi → "`bank_settlements.statement_import_id` (import yozuvining `id`si)".
- [T-214] 1292, 1323, 1365-qator xatolariga `403 OWNER_ONLY`.
- [T-144] #61 (1305–1308): `amount` — D-23 formulasi; javobga `amount_breakdown`; muvaffaqiyatli to'lovda `new_end = max(current_period_end, now()) + 1 oy | 12 oy`.
- [T-213] 65a (1374–1377) `export_id`/`download_url` → `job_id`/`file_url` (`17` §13); [T-190] 1375, 1382-qator `§16.5`, `§18.1` → `` `14` §16.5 ``, `` `14` §18.1 ``; [T-121] eksport tasdig'i — OTP Telegram birinchi, faqat Egasi.
- [T-211] 1435-qator Telegram ulanishi "o'chiriladi" → "`telegram_links.revoked_at = now()`".
- [T-084, T-085] #73–#75 (1502, 1510, 1535–1537): `doc_type_hint` → `purchase|catalog` (`return` olinadi); confirm javobi → `{created_doc_type: "goods_receipts"|"stock_openings"|null, created_doc_id|null, created_product_ids: [UUID], status}`.
- [T-146] #73 (1504–1516) xatolariga `403 AI_FEATURE_DISABLED` (`ai.ocr_enabled=false`).
- [T-209] 1603-qator "75 ta `ONEC_*`" → "81 ta".

### G-d — `21`–`25`, `28`, `32`

#### `21-integratsiyalar.md`
- [T-115, T-024] 49-qator `outbox_jobs.kind` ro'yxati → `11` dagi 17 qiymatli ro'yxat (`marking_supplier_return`, `poa_send`, `marking_writeoff`, `billing_webhook_reconcile` bilan); `ofd_send` — "faqat `partner_cloud` rejimida (lokal ko'prikda chekni FM imzolaydi va natija POS voqeasi bilan keladi)"; 288-qator ham shu ro'yxat.
- [T-119] 97-qator `register_sale` izohi → `# kind: sale | debt_settlement | credit_sale`.
- [T-113, T-244] 116-qator: konstanta nomi `OFFLINE_BLOCK_HOURS = 48`; 46 soat modali matni #43 dagidek ("2 soatdan keyin kassa bloklanadi — internetga ulaning", "Tushundim"); blokda ruxsat etilgan amallar ro'yxati `16` §6 bilan aynan.
- [T-024] 122-qator: offline qarz to'lovi cheki — qurilma `shared/lib/debt-allocation` bilan qatorlarni hisoblaydi (D-04).
- [T-026] §1 (155–158): "lokal ko'prikda FM natijasi (`fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`, `fiscal_at`) POS voqeasidagi `fiscal_result` bilan keladi (`18` §4.1); OFD tasdig'i — `fiscal.status` agent vazifasi natijasidagi `acked[]` → `fiscal_receipts.ofd_acked_at` (D-05)".
- [T-006] §6 (192, 399–403): `EInvoicePort.send_power_of_attorney(poa_id, signed_payload)` — `powers_of_attorney` jadvalidan; `outbox_jobs(kind='poa_send')`; javob poll orqali `accepted`/`rejected` (D-07).
- [T-121] 529-qator OTP → "Telegram birinchi, SMS zaxira (#34)".
- [T-117] 580-qator `card_type` standarti `personal` → "standart yo'q — kassir har to'lovda tanlaydi (qaror #64)".
- [T-289] 772-qator "FiscalPort+Fake — Bosqich 0 dan" → "Bosqich 3 dan".
- [T-022] §16 (810–853): "Bulut kanali" (835) ga "agent infratuzilmasi — Bosqich 5 (qaror #66), migratsiya `0028 store_agent`"; vazifa turlari jadvali (839–845) ga payload ustuni (D-01 §5) va `fiscal.status` natijasi (D-01 §6, `acked[]`); "Kassa bog'lanishi: lokal ko'prik kassasi `cash_registers.fiscal_agent_id` + `fiscal_local_device_id` (BO-12)"; "Vazifa faqat agent `capabilities` da yoqilgan oilaga qo'yiladi, aks holda `409 AGENT_CAPABILITY_DISABLED`"; `scale.plu_upload` qatori ustuniga "MVP'dan keyin".
- [T-141] §16 dan keyin yangi **§16.1 «Lokal API sxemalari»** — D-22 jadvali va qoidalari aynan (port `47110`, sxemalar, xato shakli, HTTP kodlari); 828–830-qatordagi yo'llar jadvali §16.1 ga havola qiladi.
- [T-167, F-10] 851-qator "lokal ko'prik tanlansa sertifikat Bosqich 5 dan oldin kerak" → "lokal ko'prik tanlansa — Bosqich 5/6 pilot tarqatishidan oldin (qaror #38)".

#### `22-ai-qatlami.md`
- [T-084] 215-qator OCR `doc_type_hint` → `purchase|catalog`.

#### `23-backend-arxitekturasi.md`
- [T-178] 15, 324, 389-qator "README qarori" → "`22-ai-qatlami.md` §1 (AI porti rejimlari `fake`/`cli`/`api`; qaror #16)".
- [T-125] 182-qator storno → "`ledger_entries` — Dt/Kt o'rni almashtiriladi, `amount` musbat; `stock_moves`/`debt_moves`/`cash_moves`/`vat_moves` — teskari ishora (`13` §5.2)".
- [T-131] 186-qator recost → `13` §3.3 qoidasi (storno + yangi qator, `ORDER BY moved_at, created_at, id`).
- [T-182] 226-qator "(13-0 §8)" → "(`17-api-umumiy.md` §8)".
- [T-121] 233-qator lokaut eksport OTP → Telegram birinchi, SMS zaxira.
- [T-022, T-271] §4.2 (276–288): 278-qator → "Agent ro'yxati, ulash, token va vazifa navbati — Bosqich 5 da quriladigan umumiy mexanizm (qaror #66; jadvallar `onec_agents`, `onec_agent_tasks`, `onec_task_results`, `auth.onec_device_authorizations`, migratsiya `0028 store_agent`); `AgentTaskPort.enqueue` agent `capabilities` ni tekshiradi (`409 AGENT_CAPABILITY_DISABLED`)"; jadvalga payload (D-01 §5); 282-qator natija → "`cash_registers.*` (payload `cash_register_id` bo'yicha) va `acked[]` → `fiscal_receipts.ofd_acked_at`"; 284-qator → "`ZReport` → `fiscal_receipts(kind='z_report')` yoziladi"; 286-qator `scale.plu_upload` → "MVP'dan keyin".
- [T-199] 366-qator `postgres:17-alpine` → `postgres:16-alpine`.
- [T-086] 446-qator standart xarajat toifalari → "`13` §2.17 seed xaritasi (21 kod)".

#### `24-frontend-arxitekturasi.md`
- [T-026] 170-qator (lokal ko'prik): "FM natijasi outbox voqeasiga `fiscal_result` sifatida yoziladi (`18` §4.1)".

#### `25-nofunksional-talablar.md`
- [T-167, F-10] 20-qator OV sertifikat muddati → "lokal fiskal ko'prik tanlansa Bosqich 5/6 pilotidan oldin, aks holda Bosqich 7 dan oldin (qaror #38)".
- [T-274] §11 — o'zgarmaydi (unit-iqtisod va AI xarajati raqamlarining manbai; 01/05/09 unga moslanadi).

#### `28-android-pos.md`
- [T-117] 17, 119-qator `card_type` qoidasiga: "standart qiymat yo'q — kassir har to'lovda tanlaydi (qaror #64)".

#### `32-kod-qoidalari.md`
- [T-187] 206, 225, 473-qator `` `08-dizayn-tizimi.md` §0.1 `` → `` `08-dizayn-tizimi.md` §0 (1-band) ``.
- [T-277] 347-qator `mypy app` → `mypy --strict app` (#57).
- [T-197] 377-qator qavs ichidagi "(joriy branch nomi shu uslubga mos)" olinadi; namuna `spec/<qisqa-tavsif>` qoladi.
- [T-024] `shared/` paketlari ro'yxatiga `shared/lib/debt-allocation` (TS) va `app/shared/debt_allocation.py`, test-vektorlar `shared/debt-allocation-vectors.json` — `shared/money-vectors.json` bilan bir xil qoida (CI'da ikki tomon bir xil natija).

### G-e — `31-qabul-testlari.md`

- [T-018] 111-qator (QT-RLS-05) → "`platform.units`/`platform.plans`/`platform.addons` kabi `tenant_id`siz global jadval".
- [T-021] 149-qator (QT-SUB-03) → "`app.auth_suspend_tenant(tenant_id, true)`: `refresh_tokens.suspended_at = now()`, `revoked_reason='subscription'`; `sessions` o'zgarmaydi".
- [T-111] 179-qator (QT-PERM-07) → "`status='consumed'`"; qayta ishlatish → `409 APPROVAL_REQUEST_ALREADY_RESOLVED`.
- [T-241] 35-qator fixture `settings` ga `discount_posting='gross_9050'`, `turnover_tax_account`; 37, 403, 405-qator fixture'lariga `branch_tax_settings.activity_type='retail'`, ombor `type='stock'`, `marking_group_code`; 201-qator `related_doc=receipt` → `related_doc_type='sales'`, `related_doc_id`.
- [T-242] 270-qator `last_purchase_cost` manbasi → "eng so'nggi `goods_receipts` partiyasi `unit_cost`, yo'q bo'lsa `avg_cost`".
- [T-035] 291-qator (QT-M07-02) → "… unda farq (2 dona kam) belgilanadi, kirim `status='draft'`, `stock_balances` o'zgarmaydi; Buxgalter `POST /goods-receipts/{id}/post` dan keyin `stock_balances` 48 donaga oshadi".
- [T-019] 297-qator (QT-M07-08) → "bonus miqdori kirim qatoriga qo'shiladi, partiya `unit_cost` = faktura summasi / (to'langan + bonus); 0 narxli alohida partiya yaratilmaydi; AVECO'da `avg_cost` shu `unit_cost` bilan".
- [T-017] 304-qator (QT-M08-01) `sales.status='deferred'` → "`sales.status='posted'`, sinxronlash javobida `fiscal.status="deferred"`"; 306-qator `debt_moves.limit_exceeded=true` → "`sales.debt_limit_exceeded=true`".
- [T-001] 334-qator (QT-M09-02): "rad etilsa `price_changes.status='rejected'`" qo'shiladi.
- [T-288] 341-qator QT-M09-09 US ustuni US-M03-02 → US-M09-01.
- [T-112] 411-qator (QT-M15-01) → "`cash_moves(amount='-500000.00', method='cash', doc_type='expenses', …)`; `cash_movements` hujjati yaratilmaydi".
- [T-027] 422-qator (QT-M16-01) ga kutilgan provodka: `other`/`out` → `Dt 9430 / Kt 5010`; `other`/`in` → `Dt 5010 / Kt 9390`; noto'g'ri juftlik (`deposit` + `out`) → `422 VALIDATION_ERROR`.
- [T-056] 461-qator (pairing) → "muddati o'tgan kod → `409 ONEC_PAIRING_CODE_EXPIRED`; noma'lum/ishlatilgan → `404 ONEC_PAIRING_CODE_INVALID`".
- [T-268] 485-qator QT-M19-04 izohi P-05 → P-13.
- [T-193] 501–504-qator `QT-AI-GUARD-02/03/04` → `01/02/03` (tartib bilan).
- [T-164] QT-M05-05 "Android POS" → "veb PWA (POS-10)"; QT-M06-04 va QT-M05-05 — Bosqich 3 (sync) ustunida.
- [T-289] QT-SUB sarlavhasiga US-M17-03.
- **Yangi testlar** (har biri mos modul jadvaliga, Berilgan/qachonki/unda shaklida):
  - [T-139] **QT-M01-22** (US-M01-07): printer sozlamasi va sinov cheki — cp866 matn, o'zbek kirill/`ʻ` bo'lsa raster, U+02BB → `'`; tarozi prefiksi `settings.weight_barcode_templates` (22 = gramm, 21 = summa) bo'yicha vaznli shtrix kod to'g'ri o'qiladi.
  - [T-026] **QT-M01-23**: lokal ko'prik rejimida `sale.created` `fiscal_result` bilan → `fiscal_receipts.status='fiscalized'`, `fm_*` to'ldirilgan, `ofd_acked_at` NULL; `fiscal.status` vazifasi `acked[]` qaytargach `ofd_acked_at` to'ladi va 48 soat taymeri keyingi chekka o'tadi; `fiscal_result` bor voqeada `receipt_seq` takror → qabul, qayta raqamlangan, `sync_exceptions(kind='receipt_seq_conflict')`.
  - [T-024] **QT-M08-16**: mijozda ikki ochiq sotuv (A — 300 000, `due_date` erta; B — 200 000), offline 350 000 to'lov → allokatsiya A 300 000 + B 50 000; B qatorlari `ratio = 50000/200000` bilan, qoldiq eng katta qatorda; `sale_lines.settled_amount` yangilanadi; boshqa qurilma oraliqda A ga 100 000 to'lagan bo'lsa — voqea qabul, registrlar server allokatsiyasi bo'yicha, `sync_exceptions(kind='debt_allocation_mismatch')`.
  - [T-025] **QT-M08-17**: offline qarz to'lovi 120 000, server qarzi 100 000 → qabul, `unallocated_amount = 20000.00`, `Dt 5010 / Kt 6310 = 20000.00`, `sync_exceptions(kind='debt_overpayment_offline')`; online xuddi shu summa → `422` (`debt_payment_exceeds_balance`).
  - [T-023] **QT-M08-18**: `POST /debt-payments` `method='cash'` → `422 VALIDATION_ERROR` (`validation.debt_payment_backoffice_bank_only`); `method='bank'` → `posted`, `Dt 5110 / Kt 4010`, `fiscal_receipts` yozuvi yo'q.
  - [T-254] **QT-M11-13**: inkassa 2 000 000, bank 1 990 000, komissiya 5 000, kamomad −5 000 → `Dt 5110 1 990 000`, `Dt 9410 5 000`, `Dt 5910 5 000` / `Kt 5710 2 000 000`.
  - [T-028] **QT-M11-14**: oktyabr yopilgan; oktyabr sanali offline sotuv noyabrda sinxronlanadi → qabul (`PERIOD_CLOSED` yo'q), `ledger_entries.entry_date` = 1-noyabr, `analytics.correction_of_period="2026-10"`, `sync_exceptions(kind='late_in_closed_period')`; noyabr readiness'da shu qurilmada sentyabr/oktyabr voqeasi kutilayotgan bo'lsa `devices_unsynced` bloker; dekabrni noyabrdan oldin yopish → `409 PERIOD_CLOSE_OUT_OF_ORDER`.
  - [T-139] **QT-M17-09** (US-M17-03): obuna muddati o'tdi → `grace` 24 soat → `restricted` (login rad, `sync.drain` va to'lov havolasi ochiq); to'lov → `active`, `new_end = max(current_period_end, now) + 1 oy`; yillik to'lov 1 qo'shimcha kassa bilan `amount = 950400 + 468000 = 1418400.00`.
  - [T-139] **QT-M19-25** (US-M19-04): auto-match `exact`/`probable`; tasdiqlanmagan moslash eksportda ishlatilmaydi; `confirm_all_exact`; 5710 bo'lmagan to'lov turi schyotida `warnings[]` (`ONEC_PAYMENT_ACCOUNT_NOT_TRANSIT`).
  - [T-139] **QT-M19-26** (US-M19-14): hikoyaning `33` §14 qabul mezoni bo'yicha.
  - [T-285] **QT-NFR-SIGNUP-01**: yangi do'kon ≤ 2 daqiqada ro'yxatdan o'tadi, 500 tovarli Excel importi bilan ≤ 10 daqiqada savdoga tayyor.
- [sanoq] §0 va §0.7 dagi sonlar (jami, modul bo'yicha, M19, Bosqich 7) qatorlarni qayta sanab yoziladi; 31:67 dagi "182" va boshqa raqamlar shunga.

### G-f — `33`, `34`

#### `33-1c-integratsiya.md`
- [T-266] 99-qator platforma ro'yxatidan 8.2 olinadi (faqat 8.3/8.5; 8.2 → `ONEC_PLATFORM_VERSION_MISMATCH`).
- [T-265] 213-qator (`errors.py` izohi) va 1851-qator (§7.5 jadvali) dan `duplicate` sinfi olinadi; `ONEC_DUPLICATE_REF` → `unknown` sinfi.
- [T-140] 301-qator (§4.4) → "muddati o'tgan o'qish vazifasi — yangi vazifa qatori (`attempt + 1`, ≤ 3); 3-urinishdan keyin bog'liq `onec_reconciliations`/`onec_ref_create_requests`/tekshiruv `failed`"; §5.15 (1030–1035) jadvaliga izoh "`expired` — yakuniy; qayta urinish yangi qator".
- [T-047] 502-qator (§5.3) `→ onboarding` o'tishining "Dan" ustuni → `onboarding`/`ready`/`error`/`disabled`; shart: eski agent `revoked` yoki `ONEC_BASE_DUPLICATE`; faol partiya bo'lsa `409 ONEC_ACTIVE_BATCH_EXISTS` (W-14 bilan bir xil).
- [T-138] §5.10 (764) va 1678, 1692: "yaratish tartibi — `unit`/`payment_method` → `counterparty` → `counterparty_contract` → `product` (oldingisi `created` bo'lmaguncha keyingisi navbatga qo'yilmaydi); transient/unknown → `approved`, §7.5 backoff bilan yangi vazifa; `attempts ≥ 8` → `failed`".
- [T-022] §5.15 DDL nusxasi (980–984, 1010) — D-01 §3 CHECK'lari aynan (12 bilan bir xil); §5.15 ga `leased → cancelled` (T-054 sharti bilan); §5 kirishiga "umumiy agent jadvallari — Bosqich 5, `0028 store_agent` (qaror #66)".
- [T-056] §5.18 (1124–1125, 1161): `onec_device_auth_approve` → `RETURNS text` (`approved|not_found|expired|used`); [T-232] yangi `onec_device_auth_deny` (12 bilan aynan).
- [T-148] 1389, 1392, 3918-qator: `devices.kind`/`signing_keys.purpose` — "Bosqich 0 migratsiyasida allaqachon (#58c)"; B7 vazifasi sifatida takrorlanmaydi.
- [T-267] 1525-qator `orp_negative_payment` → "qaytarish summasi `СуммаОплаты` dan ayiriladi; natija < 0 → `ONEC_ORP_CASH_MISMATCH`".
- [T-016, T-036, T-037] §7.1 (1722–1760) — D-11: T7 yon ta'siri "partiyaning barcha `pending` itemlari → `queued`"; yangi **T12a** `verifying → mismatch`; yangi **T17** `mismatch → done` va **T17b** `done → mismatch` (W-50 natijasi); mermaid diagrammasiga shu o'tishlar; 1738-qator D-11 §4 matni bilan; 1760-qator ga "(T12a dan tashqari)".
- [T-048, T-016] §7.5 (1825–1842): `pending/queued/retry_wait → skipped: W-46 (sabab bilan)`; `mismatch → verified: W-50 (T17)`; `pending → queued` izohi "partiya `queued` bo'lganda (T7)".
- [T-270] 1877-qator dispetcher izohi → "qat'iy `(phase, seq)` tartibi; `retry_wait` keyingi itemlarni ham kuttiradi (ataylab)".
- [T-137] §8.1 (1924–1926) katalog nomlari → `catalog_branch` (`branches.id`), `catalog_expense_category`, `catalog_payment_method` (§5.10 entity nomlari bilan); `shared/onec-guid-vectors.json` ga shu uch vektor.
- [T-022, T-234] §9.2 A-01 (2155–2185): so'rov misoliga `capabilities` (34 §14.2 sxemasi), sarlavha `X-Agent-Protocol: 2`; server yangilaydigan maydonlar ro'yxatiga `os_version`, `pc_name`, `capabilities` (→ `onec_agents.capabilities`).
- [T-054] A-04 (2232, 2235): `cancel_requested` hisoblanadi — `NOT is_write AND batch.cancel_requested_at IS NOT NULL`; ustun qo'shilmaydi.
- [T-234] A-05 (2244): "`started_at`/`finished_at` saqlanmaydi — faqat `duration_ms`".
- [T-055] A-07 (2267): `attachments.uploaded_by` = `collect_diagnostics` vazifasining `created_by` (W-07 so'rovchisi); u NULL bo'lsa `422`.
- [T-053] A-10 (2279): `revoke_reason = <so'rovdagi reason>` (`uninstall`|`user`).
- [T-022] §9.5 (2317): "Do'kon agenti kengaytmasi" paragrafiga — "bu vazifalar `purpose='device_service'`, payload'lar D-01 §5 (`21` §16), natija `fiscal.status` — `acked[]` bilan; agent infratuzilmasining o'zi (A-01, A-03…A-10, imzo, lease) Bosqich 5 da quriladi (qaror #66), 1C turlari — Bosqich 7".
- [T-227] 2575-qator cursor ro'yxati — haqiqiy yo'llar (`/onec-agents/{id}/logs`, `/onec-export-batches/{id}/items`, …); mavjud bo'lmagan `onec-events`, `onec-agent-logs` olinadi.
- [T-226] 2645, 3325-qator: `actor` → `actor_user_id` + `actor_name`; `paired_by` → `paired_by` (UUID) + `paired_by_name`.
- [T-051, T-229] §10.2 ExportBatch (2654–2658): `accepted_at`, `accept_reason`, `cancel_requested_at`, `cancelled_at`, `cancel_reason` qo'shiladi; 2654 "preview'siz" izohi misolga moslanadi (misoldan `preview` olinadi yoki izoh "preview bilan" deb).
- [T-230] ExportItem shakli (2660–2663) ga `max_attempts`, `progress`; W-37 `agent` obyektiga `agent_version` (3143); W-55 (3377) ga agent nomi/versiyasi.
- [T-056] W-03 (2702) → noma'lum/ishlatilgan `404 ONEC_PAIRING_CODE_INVALID`, muddati o'tgan `409 ONEC_PAIRING_CODE_EXPIRED`; W-04 (2715) shu natija xaritasi; [T-232] W-04 ga "Rad etish" varianti — `POST /onec-agents/pairing-requests/{user_code}/deny` (`onec.settings.manage`) → `onec_device_auth_deny`, agent poll'iga `access_denied`.
- [T-052] W-08 (2753, 2765–2766) ga xaritalash: server voqeasida `warning → warn`; `message_key` maydoni (agent logida `null`); `context = params`; diagnostika — `code='diagnostics_ready'`, `context.attachment_id`.
- [T-046] W-11 (2802) → "profilni qo'lda tanlash — faqat `config_supported=fail` va `metadata_profile=pass` bo'lsa (Egasi)".
- [T-047] W-14 (2841, 2845) — §5.3 o'zgarishi bilan mos.
- [T-224] W-29 (3039) `warnings` → `[{code, params:{kind, erp_value}}]`.
- [T-049] W-32 (3078–3079) javobi → `202 {approved, task_ids, errors:[{id, code}]}`; `409` — faqat hamma `id` yaroqsiz bo'lsa.
- [T-050] W-39 (3169) javobiga `preview_result: null | {task_id, outcome, data, error, received_at}` (oxirgi `preview_object` vazifasining `onec_task_results` yozuvi); W-40 (3182) shunga havola.
- [T-048] W-46 (3257) ruxsat holatlari → `failed`/`pending`/`queued`/`retry_wait`; 3261-qator `409` → `sending`/`unknown`/`written`/`verified`/`mismatch`/`skipped`.
- [T-044] W-49 (3300) `422 ONEC_DATE_PROHIBITED` → `409`.
- [T-016] W-50 (3305–3314): maqsad — "`done`/`partial`/`mismatch` partiyada"; javob izohi "natija T17/T17b bo'yicha (D-11)"; "natijada `mismatch → done` bo'lishi mumkin" — T17 havolasi bilan qoladi.
- [T-225] 3364-qator `batch_id` → `last_batch_id`.
- [T-136] 3878-qator → "#105, #132, #133 (P-03…P-07, P-12) Bosqich 7 kodini bloklaydi"; 3895-qator "Bosqich A gacha" → "§16.1 pilot oldi testlari o'tguncha".
- [T-192] 3930-qator → "Qabul testlari (`31` M19; shu fayl §14 qabul mezonlari)".

#### `34-1c-agent.md`
- [T-266] 251-qator probe ro'yxatidan `V82.COMConnector` olinadi.
- [T-232] 506-qator `access_denied` — W-04 "Rad etish" (`onec_device_auth_deny`) natijasi ekanini yozing.
- [T-176] 1586-qator "Fayl keyin `34-dokon-agenti.md` ga kengaytiriladi" jumlasi olinadi.
- [T-022] §14 (1584–1641): §14.1 "Identitet" qatoriga "agent infratuzilmasi — Bosqich 5 (qaror #66)"; §14.2 `capabilities` — "A-01 sxemasiga kiritilgan, `X-Agent-Protocol: 2`; server `onec_agents.capabilities` ga yozadi"; §14.3 (b) jadvaliga payload ustuni (D-01 §5), `fiscal.status` natijasi `acked[]` bilan, kassa bog'lanishi (`cash_registers.fiscal_agent_id`/`fiscal_local_device_id`), `scale.plu_upload` — "MVP'dan keyin"; (a) lokal API — "sxemalar `21` §16.1".

---

## 7. Qo'llash tartibi va tekshiruv

1. Guruhlar parallel ishlaydi. Faqat sanoqlar (`00`, `30`, `31` §0, `20` indeksi) — boshqa guruh tugagach yakuniy qiymat bilan.
2. Har guruh tugagach: (a) o'z fayllarida `grep` bilan tarix so'zlari ("endi", "olib tashlandi", "qo'shildi"), eski nomlar (`card_manual`, `fromBranchId`, `OFFLINE_FISCAL_BLOCK_HOURS`, `correction_signature`, `issue_credit_payment`, `pending_events`, `34-dokon-agenti`) qolmaganini tekshiradi; (b) yangi ID'lar (`T-`, `D-`, `F-`) spec matniga yozilmagan (ular faqat shu rejada).
3. Yakuniy darvoza: 12 DDL PG16 da yuklanadi (yangi ustun/CHECK/funksiyalar), 17 §15 kod soni, 15 ruxsat soni, 31 QT soni qayta sanaladi.
