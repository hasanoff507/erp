# Implementatsiya holati — yagona kuzatuv hujjati

**Maqsad:** spec'dagi (`spec/kod-uchun/`) har bir bosqich bandini — vazifa, hikoya, endpoint, ekran, jadval, qabul testi — kod va test bilan solishtirib, ish siklini (keyingi nima, nima qolgan) shu yerdan boshqarish. · **Kim uchun:** asoschi, Claude va kod yozayotgan agentlar. · **Bog'liq fayllar:** `27-backlog.md`, `30-izchillik-matritsasi.md`, `31-qabul-testlari.md`, `12`, `14`, `17`–`20`, `33`, `06`/`07`, `26`. · **Holat:** joriy, generatsiya qilingan — qo'lda tahrir faqat "Holat"/"Dalil" ustunlarida.

## Qanday yangilanadi

| Belgi | Ma'nosi |
|---|---|
| ✅ bajarildi | kod **va** test bor (dalil ustunida fayl/test nomi) |
| 🟡 qisman | kod bor, lekin test yo'q yoki band to'liq emas (nima qolgani dalilda) |
| ⬜ qilinmagan | kod yo'q |
| ⛔ tashqi javob kutmoqda | band tashqi javob/qarorsiz bajarilmaydi (26 Jadval B, asoschi) |
| ⏭ MVP'dan keyin | `27` "MVP'dan keyin" bo'limi |

**Qoida: band faqat kod va test ikkalasi mavjud bo'lsagina ✅ bo'ladi.** Test bor-yo'qligi — repo'dagi test fayllari (pytest/vitest/Playwright); "yashil" ekanini CI tasdiqlaydi.

- **ID sxemasi:** `B<bosqich>-<tur>-<manba>` — `B1-T03` (27 dagi 3-vazifa), `B1-DoD-02` (Tayyor ta'rifining 2-bandi), `B1-US-M13-04`, `B1-EP-20#28` (20 indeksi #28), `B1-EP-19#31` (19 dagi 31-endpoint sarlavhasi, tartib bo'yicha), `B0-EP-14#6` (14 §20 dagi 6-qator), `B1-EP-14§18.2#2`, `B0-EP-17#1`, `B5-EP-33W-01`, `B3-SCR-POS-02`, `B3-TBL-app.sales`, `B0-QT-RLS-01`; `BK-…` — MVP'dan keyin.
- **Bosqichga biriktirish** mexanik: vazifa/hikoya — `27`; endpoint — `27` vazifa matnidagi yo'l → `30` dagi US API ustuni → katalog raqami → resurs nomi (eng aniq moslik, keyin eng erta bosqich; "Manba" ustunida ko'rsatilgan); ekran — bosqich vazifasi va hikoyalarining ekranlari (bir ekran bir necha bosqichda bo'lishi mumkin — har bosqich o'z qismini quradi); jadval — birinchi tilga olingan bosqich (0028 → B5, 0029 → B7, tilga olinmagani → B0 infratuzilma); QT — `27` dagi aniq havola → `31` US ustuni → kross-kesma qoidalar (`_scripts/gen_holat.py` `QT_STAGE_RULES`).
- **Jadval qatori:** ✅ = DDL migratsiyada + ilova kodida ishlatiladi + testda bor; 🟡 = DDL bor, modul kodi/testi hali yo'q.
- **Qayta generatsiya:** `python spec/implementatsiya/_scripts/gen_holat.py` (repo ildizidan; `--check` — CI uchun, `--pytest` — dalilga `pytest --collect-only` qo'shadi). Skript route'larni, test nomlarini (`test_qt_…`) va jadval ishlatilishini o'zi topadi; qo'lda qo'yilgan holat/dalil (shu fayldagi) avtomatik ✅ topilmaguncha saqlanadi. Bosqich 0 va 1 ning qo'lda tekshirilgan holatlari — skriptdagi `MANUAL`; boshqa bosqichga ko'chirilganlar — `STAGE_MOVE` (sabab "Manba" ustunida).
- **Ish sikli:** bosqich boshida shu bosqich bo'limidagi ⬜ qatorlar — ish ro'yxati; band tugaganda kod+test bilan ✅ va dalil; bosqich "Tayyor ta'rifi" (`DoD`) qatorlarining hammasi ✅ bo'lganda keyingi bosqichga o'tiladi (27).

## Yig'ma (bosqich × holat)

| Bosqich | ✅ | 🟡 | ⬜ | ⛔ | ⏭ | Jami | Vazifa | DoD | US | EP | Ekran | Jadval | QT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [Bosqich 0](#bosqich-0-poydevor-va-tashqi-ishlar) | 61 | 0 | 0 | 13 | 0 | 74 | 19 | 11 | 0 | 17 | 1 | 10 | 16 |
| [Bosqich 1](#bosqich-1-royxatdan-otish-va-katalog) | 143 | 0 | 0 | 0 | 0 | 143 | 11 | 3 | 13 | 61 | 8 | 26 | 21 |
| [Bosqich 2](#bosqich-2-ombor-va-hujjat-otkazish-yadrosi) | 4 | 22 | 111 | 0 | 0 | 137 | 11 | 2 | 14 | 47 | 8 | 25 | 30 |
| [Bosqich 3](#bosqich-3-veb-kassa) | 7 | 17 | 173 | 0 | 0 | 197 | 18 | 6 | 16 | 37 | 18 | 22 | 80 |
| [Bosqich 4](#bosqich-4-qarz-daftari-xarajatlar-hisobotlar-telegram) | 1 | 17 | 148 | 0 | 0 | 166 | 11 | 6 | 23 | 49 | 15 | 17 | 45 |
| [Bosqich 5](#bosqich-5-fiskal-va-e-faktura) | 0 | 8 | 118 | 1 | 0 | 127 | 14 | 8 | 7 | 51 | 15 | 11 | 21 |
| [Bosqich 6](#bosqich-6-tolov-ai-pilot) | 4 | 11 | 128 | 2 | 0 | 145 | 14 | 4 | 12 | 45 | 15 | 14 | 41 |
| [Bosqich 7](#bosqich-7-1c-integratsiyasi) | 0 | 0 | 131 | 0 | 0 | 131 | 12 | 5 | 18 | 49 | 4 | 15 | 28 |
| [MVP'dan keyin](#mvpdan-keyin) | 1 | 2 | 0 | 0 | 21 | 24 | 11 | 0 | 4 | 6 | 1 | 2 | 0 |
| **Jami** | **221** | **77** | **809** | **16** | **21** | **1144** | **121** | **45** | **107** | **362** | **85** | **142** | **282** |

Manba qamrovi: 105 US (30) → 105 tasi bosqich ro'yxatlarida; 362 endpoint katalog qatori (17: 4, 14: 48, 18: 47, 19: 91, 20: 107, 33: 65); 42 ekran (07, UX-INSTALL bilan); 142 jadval (12); 282 QT (31). Biriktirilmagan: yo'q.

## Bosqich 0 dan qolganlar

Bosqich 0 kodi `e06e9cc` commit'ida; G-02…G-12 Bosqich 1 bilan birga yopildi (2026-10-17). Qolgani — asoschining tashqi ishlari (⛔).

| # | Bo'shliq | Tafsilot | Qatorlar | Kim / turi |
|---|---|---|---|---|
| G-01 | Asoschining tashqi vazifalari | yuridik shaxs va xat imzolovchi (26 #130); Xat 1–10 ni yuborish va `letter_tracker` (26 #71); buxgalter bilan `13` ni tekshirish; reyestr arizasi (26 #25/#42) va fiskal hamkor muzokarasi (26 #109/#168/#169), Eskiz (26 #45); karta terminali hamkorlari (26 #172–#176); pentest taklifi; qo'llab-quvvatlash kanali; 15–20 do'kon suhbati va 5–10 pilot; yurist (oferta, rozilik, runbook — 26 #127/#126) | B0-T11…T15, T17…T19, B0-DoD-06/07 | ⛔ asoschi |
| G-02 | Noto Sans subset zaxirasi (ʻ ʼ, Ққ Ғғ Ҳҳ) | ✅ `@fontsource-variable/noto-sans` (ʻ ʼ — `latin`, Ққ Ғғ Ҳҳ — `cyrillic-ext`), `apps/shell/src/noto-sans-fallback.css` (`unicode-range` faqat 8 belgi), stek `preset.ts`, PWA precache; `KNOWN_MANROPE_GAPS` olib tashlandi — `e2e/font-glyphs.spec.ts`; `08` §2, 26 #141 | B0-T07 | ✅ yopildi |
| G-03 | `get-nonce` pnpm katalogida | ✅ `pnpm-workspace.yaml` katalogi, `apps/shell/package.json` → `catalog:` | B0-T08 | ✅ yopildi |
| G-04 | `/oauth/revoke` — jonli access tokenlar | ✅ access tokenda `fam` claim; Redis belgilari `auth:jti_revoked`/`auth:fam_revoked`/`auth:sid_revoked` (bitta MGET, TTL = access muddati); refresh revoke, reuse aniqlash, qurilma revoke — oila bilan; `test_auth_revocation_and_switch.py`; `14` §5 | B0-T02, B0-EP-14#6 | ✅ yopildi |
| G-05 | CSP `sha256-…` zaxirasi | ✅ `ERP_CSP_MODE=hash` build: Radix scroll-lock `<style>` sha256 ro'yxati (`apps/shell/csp-hashes.ts`), `dist/_headers`, build guard (ruxsatsiz inline skript/stil — build xatosi); `csp-hashes.test.ts`, `e2e/csp-nonce.spec.ts`; `24` §4.4 | B0-T08 | ✅ yopildi |
| G-06 | AS login sahifasi ko'rinishi | ✅ BO-01 maketi va 07 bilan tekshirildi va tuzatildi (aria-invalid/aria-describedby, 'Parolni unutdim?', telefon maxlength/placeholder, logo, ro'yxatdan o'tish havolasi, tenant select `required`); skriptsiz, hash CSP; `tests/unit/test_login_page.py` | B0-T02, B0-EP-14#3, B0-SCR-BO-01 | ✅ yopildi |
| G-07 | `POST /bff/switch-tenant` (14 §9) | ✅ route + `14` §9 shartnoma va §20 qatori; eski `sid`/oila bekor, cookie yangi sessiyaga; veb `@shared/state` `switchTenantFx`, `/bff` proksi; testlar `test_bff_switch_tenant_*` | B0-EP-14#29 | ✅ yopildi |
| G-08 | Telemetriya: `/metrics`, OpenTelemetry, Sentry | ✅ `app/core/telemetry.py`: Prometheus (`/metrics`, bearer token, route-shablon label), OTel (FastAPI/SQLAlchemy/httpx + SAQ job span'lari, OTLP), Sentry (PII'siz, token scrub) — hammasi sozlama bilan; worker metrikalari; `test_telemetry.py`, `test_metrics.py`. Keyingi modullar metrikalari (posting, outbox, AI, fiskal, 1C) — o'z bosqichlarida | B0-EP-17#3, B0-T01 | ✅ yopildi |
| G-09 | Sirlar va zaxira infratuzilmasi | repo qismi ✅: `.sops.yaml` (age), WAL-G `backend/ops/backup/*.sh` (bazaviy zaxira, WAL qabul, offsite rclone, PITR, staging restore, lag metrikasi, cron/systemd), `RUNBOOK-backup-restore.md`, `test_ops_backup.py`, CI shellcheck. ⛔ asoschi: UzCloud avto-to'lov + billing ogohlantirishi, DBaaS replikatsiya roli/`pg_switch_wal`, S3 bucket'lar (UzCloud + ikkinchi provayder, object lock), age va `WALG_LIBSODIUM_KEY` kalitlari, **staging restore bir marta** (qaror #65) | B0-T09, B0-DoD-11 | ⛔ tashqi (repo qismi ✅) |
| G-10 | Hisoblar rejasi konstantasiga test | ✅ `tests/unit/test_chart_of_accounts.py` — 13 §1 jadvalini parse qilib kod/nom/tur, takrorsizlik, 4 xonali kod, 13 §2+ dagi har hisob mavjudligi (30 kod), 6710 ishlatilmasligi; konstanta 13 ga to'liq mos | B0-T04 | ✅ yopildi |
| G-11 | Pentest tayyorgarligi — DAST | kod ✅: `.github/workflows/dast.yml` (ZAP baseline + passiv API skan, High/FAIL → job xatosi), `backend/ops/zap/rules.tsv`. ⛔ asoschi: ichki OAuth/to'lov/fiskal tekshiruv ro'yxati, Celion/ONESEC taklifi | B0-T16 | ⛔ tashqi (CI qismi ✅) |
| G-12 | `POST /auth/sessions/revoke-all` — backend testi | ✅ `test_auth_revocation_and_switch.py::test_auth_revoke_all_ends_every_session_in_every_tenant` (2 tenant, brauzer + Android; CSRF/Bearer rad; cookie tozalanadi; access tokenlar 401) | B0-EP-14#19 | ✅ yopildi |
| G-13 | Endpoint katalogida B0 ga tegishli qolganlar | `/oauth/device_authorization` — B5, `/auth/pin/verify` — B3, `/auth/license` va `app.license_tokens` — B6, `/auth/google/token` — MVP'dan keyin (Android), `app.tenant_secrets` yozish yo'li — B5 | — | ma'lumot |

Bosqich 0 ning ✅ bo'lmagan barcha qatorlari (13): `B0-T09` ⛔, `B0-T11` ⛔, `B0-T12` ⛔, `B0-T13` ⛔, `B0-T14` ⛔, `B0-T15` ⛔, `B0-T16` ⛔, `B0-T17` ⛔, `B0-T18` ⛔, `B0-T19` ⛔, `B0-DoD-06` ⛔, `B0-DoD-07` ⛔, `B0-DoD-11` ⛔.

## Bosqich 1 tekshiruvi: keyingi bosqichlarga o'tkazilgan topilmalar

Bosqich 1 + B0 bo'shliqlari 3 ta Opus tekshiruvchidan (xavfsizlik, spec, veb — 39 topilma) va Opus qabul agentidan o'tdi: 30 qabul qilindi va tuzatildi (kod yoki spec), 3 rad etildi, quyidagilar — keyingi bosqichga.

| Topilma | Tafsilot | Bosqich | Sabab |
|---|---|---|---|
| SEC-08 | Redis ishlamayotganda `sid`siz (Android/Bearer) token uchun bekor qilish DB zaxirasiz (fail-open ≤ 15 daq) | 3 | B1 da faqat BFF tokenlari (hammasida `sid`); qurilma/Android login bilan — oila bo'yicha DB zaxirasi |
| SEC-09 | Bitta sessiyani bekor qilish Android access tokenini (`fam`, `sid`siz) darhol o'chirmaydi | 3 | B3 qurilma login — `mark_revoked(sids, families)` |
| SEC-12 | MXIK qidiruvi: foydalanuvchi bo'yicha limit, javob hajmi chegarasi (SSRF yo'q; 3 urinish — 19 §161 talabi) | 6 | umumiy mustahkamlash — pilot oldidan |
| CORR-06 | QT-M09-09: aksiya narxini sotuv posting'ida server qayta tekshirishi | 3 | sotuv posting'i B3 da (19 §4 ga yozildi); narx aniqlash qismi B1 da testlangan |
| WEB-12 | Topbar qo'ng'iroq/qidiruv va tasdiqlar soni belgisi | 3/4 | tasdiqlar (BO-16) — B3, bildirishnomalar (M18) — B4 |
| WEB-15 | BO-05 «Tannarx» va «Ustama %» ustunlari | 2 | tannarx (`stock_lots`/`avg_costs`) B2 da |
| — | Qurilmani bekor qilish (`branches/infrastructure/devices.py`) so'nggi foydalanuvchilarning PIN'ini global tiklaydi (SEC-01 ga o'xshash ko'p-tenant masalasi) | 3 | PIN login va qurilma bog'lash — B3; tenant-lokal PIN talqini bilan birga |
| — | Taklifni qayta yuborish amali yo'q (ikki tenant bir telefonni taklif qilsa, oxirgi kod amal qiladi) | 1+ | UX takomillashtirish — asoschi ustuvorligi bo'yicha |

## Asoschi qarorlari

| Band | Qaror mavzusi | Holat | Kodga ta'siri |
|---|---|---|---|
| 26 #179 | Rol limitlarining standart qiymatlari (Menejer — `discount.give` %, `cash.withdraw`, `stock.writeoff`; Kassir — `debts.create`; Omborchi — `stock.writeoff`) | ⛔ kutilmoqda | seed va provisioning'da `limit_value = NULL` (limitsiz); Egasi BO-11 da o'zi qo'yadi; qaror kelganda faqat `app/modules/access/domain/permissions.py` o'zgaradi (migratsiyasiz) |
| Agent porti | Do'kon agenti lokal API porti — ruxsat ro'yxati, standart `47110` | ✅ qabul qilingan | CSP `connect-src` deploy konfiguratsiyasidagi port ro'yxatidan generatsiya qilinadi (24 §CSP, 21 §16). Hozir kodda bitta port: `web/apps/shell/csp.ts` (`agentPort = 47110`, test `csp.test.ts`), `shared/lib/src/runtime-config`; ro'yxatga kengaytirish — agent bilan (B5) |
| braces audit | `pnpm audit` dagi `braces` topilmasini e'tiborsiz qoldirish | ✅ qabul qilingan | `web/pnpm-workspace.yaml` (audit ignore, sababi izohda: build-vaqt zanjiri, foydalanuvchi kiritmasi yo'q); tailwindcss/micromatch `braces`dan voz kechganda olib tashlanadi |
| Noto subset | Manrope'da yo'q gliflar uchun self-hosted Noto Sans subset zaxirasi | ✅ qabul qilingan | bajarildi — G-02 (`08` §2, 26 #141) |
| Karta `unknown` | Noma'lum karta natijasini menejer rekvizitsiz yopadi | ✅ qabul qilingan | menejer faqat tasdiqlaydi, hech narsa yozmaydi (`resolved_by='manager'`), rekvizitlar NULL (qaror #71, 21 §9.2) — B3 vazifasi |

## Tashqi bog'liqliklar (26 Jadval B)

Real adapterni bloklaydigan bandlar va ungacha ishlatiladigan vaqtinchalik standart / fake. Manba — `26-ochiq-savollar-reestri.md` Jadval B (generatsiya qilingan); xatlar `27` "Tashqi bog'liqliklar" jadvalida.

| 26 # | Savol | Kim | Vaqtinchalik standart / fake | Bloklaydigan bosqich |
|---|---|---|---|---|
| 9 | Qarzga sotuv paytida "kredit" turidagi chek kerakmi va OFD chek turi kodi (daromad/QQS vaqti yopilgan — #93) | Soliq qo'mitasi / OFD operatori, fiskal hamkor; buxgalter t… | Sotuvda chek yo'q (FiscalPolicy.credit_sale_receipt='none'), har qarz to'lovida debt_settlement chek (#30, #45); fiscal_receipts.kind='credit_sale' va credit_type rejimi tayyor — javob kelsa sozlama… | Bosqich 5 — bloklamaydi |
| 19 | AI-03 OCR aniqligi (kirill-lotin aralash hujjatlar) | Ichki pilot | ai.ocr_enabled=false (tenant bo'yicha yoqiladi); chegaralar summa ≥95%, sana ≥90%, miqdor/nom ≥80% | Bosqich 6 (AI-03 yoqilishi) |
| 20 | Shovqinli do'konda STT (AI-02) aniqligi | Ichki pilot | ai.stt_enabled=false, SttPort; matn/tugma asosiy | MVP'dan keyin |
| 24 | Biznes o'lchovlari, SLO, sig'im, unit-iqtisod, support SLA | Pilot do'konlar | Joriy taxminlar standart; 99 000 tarif (#22); support Telegram 09:00–21:00 + shoshilinch liniya, javob maqsadi 15 daq; telemetriya birinchi kundan | Yo'q (Bosqich 6 oxirida tasdiq) |
| 40 | CRPT Turon: sotuvdan oldin onlayn tekshiruv majburiymi, label formati, hisobdan chiqarish metodi, SaaS integrator kaliti, test muhit; offline chekda… | CRPT Turon | Sotuv/qaytarish — FiscalPort items[].marking_codes[]; MarkingPort faqat verify_code/writeoff (FakeMarkingAdapter); MARKING_PRECHECK=warn; tenant sirri crpt_api_key | Bosqich 5 — faqat verify/writeoff real adapteri |
| 42 | Reyestr: Kiberxavfsizlik markazi ekspertizasi va sertifikat narxi; 1 BHM har FM uchunmi | DSQ / "Yangi texnologiyalar" DUK, Kiberxavfsizlik markazi,… | Byudjetda ekspertiza va sertifikat uchun zahira; 1 BHM har kassa uchun; reja 45 ish kuni bilan | Yo'q (byudjet) — reyestr arizasi Bosqich 5 dan oldin |
| 45 | Eskiz.uz SMS shartnomasi, OTP shablon moderatsiyasi, yetkazish tezligi | Eskiz.uz (faqat O'zbekiston yuridik shaxsi bilan — #130 dan… | OtpPort: Telegram asosiy (#34) → EskizSmsAdapter zaxira (ERP_ESKIZ_TEST_MODE=true, sender 4546, 95 so'm/SMS) | Bosqich 1 — yo'q; SMS zaxira — Bosqich 6 dan oldin |
| 47 | Faktura.uz: VM 830 xavf darajasi (yashil/qizil) API'da qaytadimi, sandbox va narx | Faktura.uz | einvoices.risk_flag='unknown' standart → QQS krediti to'lovgacha kechiktiriladi, Buxgalter qo'lda green qila oladi (audit); kiruvchi faktura — poll (GetDocuments?IsInbox), webhook yo'q; do'kon login/… | Bosqich 5 (e-faktura) — bloklamaydi |
| 49 | Dinamik UzQR POS API spetsifikatsiyasi va test kaliti (har kassaga API kalit) | CBU MUNIS (1835, t.me/uzqr_cbu_gsi) yoki tenant ekvayer ban… | Statik UzQR hozir — kassir qo'lda tasdiqlaydi (qr_type='static', online'da; offline statik tasdiq — yo'q); dinamik — UzqrPort stub; kalit tenant_secrets.cash_register_id bo'yicha | Bosqich 5 — dinamik UzQR real adapteri |
| 51 | UzCloud: shartnoma SLA foizi va kompensatsiya, DBaaS PITR/HA, S3 SSE/versioning, at-rest shifrlash, insident xabari | UzCloud savdo bo'limi (info@uzcloud.uz) | Ichki maqsad 99,5%; o'z WAL PITR, ilova darajasida shifrlash, boshqa provayderda zaxira, avto-to'lov (#65) | Yo'q (Bosqich 0 infratuzilma — interim bilan) |
| 63 | PAX/UZKASSA (Sunmi P3) FM'iga uchinchi tomon Android ilovasidan kirish (SDK/intent/APDU) | PAX/UZKASSA vendori yoki fiskal hamkor | Android'da ham FiscalPort (Kotlin): AndroidIntentFiscalAdapter, ApduFiscalAdapter (keyin), FakeFiscalAdapter | MVP'dan keyin (Android POS) |
| 71 | Rasmiy xatlarga javob muddatlari | Har xat qabul qiluvchisi (Xat 1–10) | letter_tracker: 15 kun — nazorat, 30 kun — eslatma, 60 kun — "javobsiz" → zaxira yo'l; integratsiyalar adapter+stub ortida | Yo'q (jadvalga ta'sir) |
| 89 | cash_registers.ofd_status va FM holat kodlari; FM bloki qanday bildiriladi (webhook/poll) | Fiskal hamkor (Multikassa/E-POS) | Domen enum pending/registered/active/suspended/deregistered + cash_registers.fm_state (ok/locked/ack_overdue/memory_full/unknown), last_unacked_receipt_at, fm_receipts_pending; hamkor kodlari adapter… | Bosqich 5 — yo'q (flag) |
| 94 | 1C'da «Вид оплаты» tuzilmasi: har terminal-bank alohidami; karta tushumi 5711 yoki 4010 (5710 tranzit — yopilgan, #42) | Pilot do'kon buxgalteri | Har ERP to'lov usuli — bitta ВидОплаты, tranzit hisob 5710 + val(payment_method) (#42); boshqa schyot — ONEC_PAYMENT_ACCOUNT_NOT_TRANSIT ogohlantirishi; komissiya 9430 | Bosqich 7 — sozlama ortida |
| 95 | Bank ko'chirmasini 1C'ga kim kiritadi — ERP (bank_settlements) yoki buxgalter bank-klientdan | Pilot do'kon buxgalteri | Buxgalter (onec_settings.send_bank_settlements=false) | Bosqich 7 — sozlama ortida |
| 96 | Nasiyachi jismoniy shaxslar 1C'da — har biri alohida kontragent (ПИНФЛ) yoki umumiy | Pilot do'kon buxgalteri | Har biri alohida kontragent, debtor_folder papkasida; MVP'da nasiya sotuvida customer_id (+ ixtiyoriy pinfl) saqlanadi | Bosqich 7 — sozlama ortida |
| 97 | Chegirmani 1C'da alohida (9050) ko'rsatish | Pilot do'kon buxgalteri | Sof summa; MVP chek qatorida brutto narx va chegirma summasi alohida saqlanadi (settings.discount_posting) | Bosqich 7 — sozlama ortida |
| 98 | Yopilgan 1C davriga kech chek — tuzatish sanasi; oyni qayta yopish kimning ishi | Pilot do'kon buxgalteri, yurist | Joriy ochiq sana, buxgalter tasdig'i (33 §8.8); oyni qayta yopish — buxgalter; avtomatik sana almashtirish yo'q | Bosqich 7 — sozlama ortida |
| 99 | 1C'dagi hisob raqamlari: smena farqi, egasi olgan pul, inkasso, hisobdan chiqarish, inventarizatsiya farqi | Pilot do'kon buxgalteri | onec_value_mappings.account.* — standart taklif 13 dan (NSBU), buxgalter BO-22 da tasdiqlaydi | Bosqich 7 — sozlama ortida |
| 100 | Agentning 1C litsenziyasi — alohida ish o'rni hisoblanadimi (IX.1-57 talqini) | 1C rasmiy hamkori (yozma javob) | Agent litsenziyali PK'da, 1C bilan bitta Windows foydalanuvchisida, qisqa ulanish (#38); onboarding license_source tekshiruvi (33 §2.3); ONEC_LICENSE_UNAVAILABLE → 15 daq'dan keyin qayta. Texnik javo… | Bosqich 7 |
| 101 | 1C va ERP tannarxi farqi — hisobotda 1C tannarxi | Pilot do'kon buxgalteri | 1C — buxgalteriya haqiqati (#39); tannarx 1C'ga yuborilmaydi | Bosqich 7 — sozlama ortida |
| 102 | «ERP integratsiya» 1C foydalanuvchisining minimal rollari | Real БП UZ baza (pilot / 1C hamkori) | "Бухгалтер" rollari + ЗапускВнешнегоСоединения; ПолныеПрава yo'q; onboarding user_rights tekshiruvi (33 §2.3) — tashqi ulanish huquqi yo'q → ONEC_NO_RIGHTS; to'liq huquq bilan ham ishlaydi — ONEC_USE… | Bosqich 7 |
| 103 | ОРП darajasi: kassa × kun yoki filial × kun — Z-hisobot bilan solishtirish | Pilot buxgalterlari | orp_grouping='register_day' (#39) | Bosqich 7 — sozlama ortida |
| 104 | Bir tovar kun ichida turli narxda sotilganda ОРП'da bitta qator (o'rtacha Цена) | Pilot buxgalteri, real baza | Bitta qator (product × QQS) | Bosqich 7 — sozlama ortida |
| 105 | Authenticode OV kod-imzolash sertifikati — CA, narx, yuridik shaxs nomi | Tijoriy CA (SSL.com va b.) + asoschi | CodeSignPort, signing.provider="sslcom_esigner"; dev'da imzosiz agent faqat ichki sinovda (tarqatilmaydi) | Do'kon agenti pilot tarqatilishi (Bosqich 5 fiskal ko'prik, Bosqich 7 1C) |
| 109 | Fiskal integratsiya: hamkor tanlovi; lokal ko'prik (FiscalDriveService / Multikassa localhost) ruxsati; bulut rejimi (PK'siz, iOS uchun) bormi; auten… | Fiskal hamkor (Multikassa / E-POS) + "Yangi texnologiyalar"… | FiscalPort + FakeFiscalAdapter (ERP_FISCAL_PROVIDER=fake), CI'da FM emulyatori; arxitektura — Do'kon agenti fiskal ko'prigi (#60); fm_receipt_seq alohida (#12); iOS fiskal yo'li faqat bulut rejimi bo… | Bosqich 5 — real fiskal adapter (BLOK) |
| 112 | Faqat elektron chek (qog'ozsiz — QR/Telegram/SMS) qonuniymi (iOS yo'li) | Soliq qo'mitasi (DSQ), yurist | Standart — bosma chek (fiscal_receipts.delivery='printed'); elektron — zahira (delivery='electronic' + delivery_reason, xaridor roziligi); iOS — bulut printer (#21) | Bosqich 3 — bloklamaydi |
| 118 | E-IMZO: prod API-KEY (har production domen uchun), E-IMZO-SERVER shartnomasi, narx, muddat | НИЦ "Yangi texnologiyalar" (yt.uz, (71) 202-32-32) | Dev/test — TestCA + "Режим разработчика" + testvpn; yagona imzolash domeni sign.<domen>; prod jadvalida ~1 oy bufer | Bosqich 5 (e-faktura prod) — bloklamaydi |
| 127 | Foydalanish shartlari / ommaviy oferta: rekvizitlar, lokautda fiskal mas'uliyat, shaxsiy ma'lumot bloki (chegaradan tashqari uzatishga rozilik, prots… | Yurist | Matn qoralamasi (Claude, o'zbek tilida majburiy); ro'yxatdan o'tishda tenants.accepted_terms_version/at/ip; settings.ai_cross_border_enabled=false rozilikkacha; maskalash majburiy (#61) | Birinchi real tenant / pilot (Bosqich 6 oxiri) va AI'ni real ma'lumot bilan yoqish |
| 130 | Kompaniya yuridik shaxsi (MChJ nomi, STIR), rasmiy xatlarni kim imzolaydi | Asoschi | Xat shablonlarida [Kompaniya nomi]; MChJ amaliy tanlov (Eskiz va to'lov tizimlari yuridik shaxs kutadi) | Kod — yo'q; barcha xatlar (#71), Eskiz (#45), OV sertifikat (#105) shundan keyin |
| 132 | БП UZ 3.0.64 metadata: ОРП rekvizitlari va jadval qismlari («Безналичные оплаты», Возвраты), «Касса» (По кассам), ИКПУ/«Упаковка (ЭДО)», «Льготы по Н… | Real БП UZ baza (pilot / 1C hamkori) | Profil bp30_uz standart nomlari (sinonim bo'yicha nomzodlar), read_metadata tekshiradi (metadata_profile, tekshiruv kodlari — 33 §2.3) | Bosqich 7 (BLOK, MVP'dan keyin) — 33 §16.1 pilot oldi testlari (P-03…P-07, P-12) o'tgunch… |
| 133 | ОРП: bo'sh schyotlarni to'ldirish, o'tkazish provodkalari, qaytarish, QQS yaxlitlash, oy yopish | Real baza + buxgalter | fill_accounts=true, to'ldirilmagan schyot — ONEC_FILL_CHECK_FAILED; QQS yaxlitlash — profil vat_rounding_mode (33 §8); qaytarish — Возвраты jadval qismi (orp_returns_section, manfiy qator emas); oy y… | Bosqich 7 (BLOK) — 33 §16.1 pilot oldi testlari (P-03…P-07, P-12) o'tguncha Bosqich 7 kod… |
| 135 | COM yozish tezligi (100/300/1 500 qatorli ОРП) | Real baza, odatiy do'kon PK'si | 33 §15.1 taxminlari; vazifa vaqt chegarasi timeout_s = clamp(60 + 0.4 × qatorlar, 120, 1800) | Bosqich 7 |
| 136 | "Касса ККМ" uskunaga bog'lanmaganda COM o'tkazish fiskal qurilmaga murojaat qilmasligi | Real baza + fiskal sozlama | Agent uskuna/chop metodlarini chaqirmaydi; murojaat qilmaydi deb hisoblanadi | Bosqich 7 |
| 137 | Antivirus HTTPS skanerlashi bilan long-poll va imzo tekshiruvi | Pilot PK'lar (Kaspersky, ESET, Defender) | Qattiq pinning yo'q (Ed25519 vazifa imzosi), long-poll ≤ 25 s, 2 xatodan keyin 30 s qisqa poll; onboarding'da AV istisno yo'riqnomasi | Bosqich 5 (Do'kon agenti pilot) / Bosqich 7 |
| 139 | Chek printeri transportlari (WebUSB/Web Serial/Web Bluetooth/tizim printeri/agent) amaliy sinovi | Jamoa (2–3 model xaridi) | Avto-tanlov printer.transport: agent_raw → webserial → webusb → http_* → cloud → system_print (24 §6.1); printer.codepage="cp866"; o'zbek kirill (Қ/Ғ/Ҳ) bo'lsa printer.render_mode="raster"; U+02BB →… | Yo'q — Bosqich 3 qabul testlari |
| 167 | E-faktura operatori: MVP'da Didox'ni birinchi qilishni qayta ko'rish (ochiq hujjat, partner token — tenant paroli saqlanmaydi, test muhit, scoring ma… | Asoschi | #23 #4 o'zgarmaydi — MVP operatori Faktura.uz; EInvoicePort ikki adapterga tayyor | Bosqich 5 (e-faktura) — bloklamaydi |
| 168 | Fiskal hamkor virtual kassasining kassa boshiga narxi (chakana — Rahmat 123 600 so'm/oy) ↔ qo'shimcha kassa +39 000 so'm (#22) | Fiskal hamkor; asoschi | +39 000 so'm taxmini saqlanadi; narx kelgach asoschi qayta ko'radi | Yo'q (narx; Bosqich 6 oxirigacha) |
| 169 | VMQ-393 "ikkilamchi tizim" xavfi: reyestrdagi kassaga boshqa axborot tizimini QR chek chop etish uchun integratsiya qilish TXKM'ni reyestrdan chiqari… | Soliq qo'mitasi (DSQ), fiskal hamkor | Hamkor modeli Do'kon agenti ko'prigi orqali (#60); fiskal kod alohida paket; o'z reyestr yo'li (#25) zaxira | Bosqich 5 — hamkor tanlovi oldidan |
| 170 | Virtual kassa texnik talabi — karta va UzQR to'lovlarini "to'g'ridan-to'g'ri shu qurilma orqali qabul qilish imkoniyati" (VMQ-943 2-ilova 6-band 10-x… | Soliq qo'mitasi (DSQ), "Yangi texnologiyalar" DUK, yurist | Talab mahsulot darajasida (P8 talqini, ~75%): o'z reyestr arizamizdan oldin kamida bitta real karta terminali adapteri (#71); do'konda mustaqil terminal + terminalsiz karta (rekvizitsiz) qonuniy (#64… | O'z reyestr arizasi (#25) — MVP kodini bloklamaydi |
| 171 | Bank o'tkazmasi orqali mijoz qarzini to'lashda (kassa orqali emas) fiskal chek talab qilinadimi (VMQ-943 1-ilova 30-band) | Soliq maslahatchisi / fiskal hamkor | Chek yo'q, debt_payments.method='bank' faqat BO-06 (qaror #67) | — (pilotdan oldin javob olinadi) |
| 172 | Rahmat (Multicard, 1865) va Humo (НМПЦ): Sunmi P3/P2 "Open API" — transport (LAN HTTP/TCP yoki bulut), purchase/refund/void/status/settlement metodla… | Rahmat, Humo (НМПЦ, +998 78 113 24 07) | CardTerminalPort + FakeCardTerminalAdapter; agent drayver slotlari rahmat_lan/humo_lan (#71); terminalsiz karta (#64) | Yo'q (MVP); birinchi real drayver — Bosqich 5 dan keyin, o'z reyestr arizasidan (#25) old… |
| 173 | Arca Group / ERA: "ERP moduli" HTTPS API orqali PAX A930 da karta to'lovini boshlash va RRN/avtorizatsiya kodini olish mumkinmi; ERA onlayn-kassasini… | Arca Group (ERA) | CloudTerminalAdapter slot (adapter='cloud') yoki agent drayveri era_lan; fiskal chekni har doim bizning kassa chiqaradi | Yo'q (MVP) |
| 174 | Humo (НМПЦ) Ingenico Lane/3600 Smart PIN Pad: qaysi ECR protokoli (Arcus2/SmartVista?), Ethernet orqali kassa integratsiyasi hujjati dasturchiga qand… | Humo (НМПЦ) | Agent drayver slot arcus2_tcp (#71); terminalsiz karta (#64) | Yo'q (MVP) |
| 175 | MayaSoft (MARTA) SoftPOS SDK: uchinchi tomon Android ilovasiga qo'yish shartlari, hamkor bank/PSP talabi, attestatsiya, narx | MayaSoft; hamkor bank (Ipoteka, Asaka) | SoftPosAdapter — Kotlin POS (28), kontrakt CardTerminalPort | MVP'dan keyin (Android POS) |
| 176 | Integratsiyalangan karta to'lovida karta turi (shaxsiy/korporativ/ijtimoiy, VMQ-943 1-ilova 7-band) manbasi: terminal natijada qaytaradimi yoki Uzcar… | Uzcard, Humo, ekvayer bank; vendor hamkor (#172–#174) | platform.card_bin_rules bo'sh; natijada bo'lmasa BIN bo'yicha, BIN topilmasa card_type='unknown' (card_type_source='bin_table'); kassir tanlovi yo'q, #71 | Yo'q |
| 177 | VMQ-943 1-ilova 6-band 2-xatboshi (VMQ-23 tahriri): "reyestrdagi kassalar karta qabul qilish tizimlariga majburiy ulanishi" — har do'kon zimmasidagi… | Soliq qo'mitasi (DSQ), yurist | Mustaqil terminal + fiskal chek qonuniy (1-xatboshi, P8 talqini ~60%); terminalsiz karta standart sifatida bloklanmaydi, card_manual_fallback faqat faol terminal bog'langan kassada (#71) | Yo'q (javob "majburiy" bo'lsa — card_manual_fallback standarti va onboarding o'zgaradi) |
| 178 | Integratsiyalangan terminalsiz qabul qilingan karta to'lovi (terminalsiz karta, card_entry_mode='manual') uchun karta turi, niqobi va RRN'siz fiskal… | Fiskal hamkor; Soliq qo'mitasi (DSQ), yurist | Ilova karta ma'lumotini so'ramaydi va saqlamaydi; fiskal chekda faqat payment_form='card' va summa, card_type/card_mask/rrn yuborilmaydi (21 §1, §9.2); integratsiyalangan to'lovda rekvizitlar avtomat… | Yo'q (MVP kodi); javob "rekvizit majburiy" bo'lsa — terminalsiz karta modeli va onboardin… |
| 179 | Rol limitlarining standart qiymatlari (15-xavfsizlik-va-audit.md §2.2, "✓(limit²)"): Menejer — discount.give (foiz), cash.withdraw (so'm), stock.writ… | Asoschi | Seed va tenant-provisioning limit_value = NULL (limitsiz) — Egasi BO-11'da o'zi raqam qo'yadi; tasdiq oqimi (15 §2.3) raqam qo'yilgandan keyin ishlaydi; raqam kelganda faqat provisioning shabloni (ap… | Yo'q |

## Bosqich 0: poydevor va tashqi ishlar

**Maqsad (27):** Backend/veb skeleti ishlaydi, OAuth 2.0 asosiy qatlami tayyor, barcha tashqi murojaatlar (rasmiy xatlar, buxgalter, pentest, support, pilot suhbatlari) boshlangan.

Holat: ✅ 61 · 🟡 0 · ⬜ 0 · ⛔ 13 · ⏭ 0 · jami 74

### Bosqich 0 — Vazifalar (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B0-T01 | ✅ | Backend skeleti: FastAPI, `app/core` (tenant konteksti, RLS, xatolar, idempotentlik), Alembic, SAQ worker, docker compose, CI (`23-backend-arxitekturasi.md`) | 27 | `backend/app/core/` (context, db/rls, errors, idempotency, `telemetry.py`, `body_limit.py`), `backend/alembic/` 0001–0027, `backend/app/workers/` (SAQ), `backend/docker-compose.yml`, `.github/workflows/backend.yml`; test: `test_rls.py`, `test_health_and_idempotency.py`, `test_seed_and_worker.py`, `test_migrations.py`; telemetriya (G-08): `tests/unit/test_telemetry.py`, `tests/integration/test_metrics.py` |
| B0-T02 | ✅ | To'liq OAuth 2.0 AS+RS poydevori: `app/modules/auth/` — Authlib integratsiyasi, `/oauth/*`, `/auth/*` endpoint'lari, imzolash kaliti/JWKS, token/sessiya/litsenziya jadvallari (`14-autentifikatsiya-oauth2.md`, qaror #14) — Bosqich 0'da poydevor, Bosqich 1'da t… | 27 | `backend/app/modules/auth/` (Authlib AS, BFF, JWKS EdDSA, refresh oilasi; jonli access tokenlarni `jti`/`fam`/`sid` Redis belgilari bilan bekor qilish — G-04; `POST /bff/switch-tenant` — G-07; AS login sahifasi BO-01 ga moslandi — G-06); test: `test_oauth.py`, `test_auth_gate_fixes.py`, `test_auth_revocation_and_switch.py`, `tests/unit/test_login_page.py` |
| B0-T03 | ✅ | Veb skeleti: Turborepo, `apps/shell`, `@shared/api` (orval), `@shared/ui` (shadcn), `@shared/state`, i18n uz/ru, PWA (`24-frontend-arxitekturasi.md`) | 27 | `web/` Turborepo: `apps/shell`, `@shared/api` (orval, `src/generated/`), `@shared/ui` (shadcn), `@shared/state`, `@shared/i18n` (uz/ru), PWA (`vite-plugin-pwa`, `apps/shell/vite.config.ts`); test: vitest 347 + Playwright 53 (`apps/shell/e2e/*.spec.ts`) |
| B0-T04 | ✅ | Seed (`23-backend-arxitekturasi.md` §11): global seed — faqat `12-db-sxema.md` §5.1 (o'lchov birliklari, yagona tarif `plans.standard` + qo'shimcha kassa `addons` (qaror #22), markirovka guruhlari, aylanma solig'i stavkalari (26 #111), yorliq shabloni, OAuth… | 27 | global seed `backend/scripts/seed.py`, provisioning `app/modules/access/application/provisioning.py`, ruxsatlar `access/domain/permissions.py`, xarajat toifalari `expenses/domain/categories.py`, hisoblar rejasi `accounting/domain/chart_of_accounts.py`; test: `test_seed_and_worker.py::test_global_seed_values_and_rerun`, `::test_demo_tenant_provisioning`, `tests/unit/test_permissions.py`, `tests/unit/test_chart_of_accounts.py` (13 §1 bilan to'liq solishtirish — G-10). Rol limitlari NULL — 26 #179 |
| B0-T05 | ✅ | Bosqich 0 migratsiyasida: `devices.kind` + `'onec_agent'`, `signing_keys.purpose` + `'onec_task'`/`'agent_update'` (qaror #58 c) | 27 | `alembic/sql/0002`, `0007`; test: `test_migrations.py::test_devices_kind_accepts_onec_agent_qaror_58c`, `::test_signing_keys_purpose_qaror_58c` |
| B0-T06 | ✅ | Spike: `zxing-cpp` GS1 DataMatrix (FNC1) dekod/enkod — `tests/fixtures/datamatrix` test-vektorlari; mos kelmasa `bwip-js` server zahirasi (qaror #57, 26 #62) | 27 | `research_notes/ochiq-savollar/spike-datamatrix.md`; test: `tests/unit/test_spike_datamatrix.py` (16), vektorlar `tests/fixtures/datamatrix/vectors.json`; bwip-js server zahirasi kerak emas |
| B0-T07 | ✅ | Shrift: Manrope woff2 (400–800) ilova bilan bundle qilinadi (CDN yo'q, offline kesh), zaxira `system-ui`; uslub tokenlari `design/USLUB.md` dan (qaror #57). Spike: U+02BB (`oʻ gʻ`) va o'zbek kirill glif skrinshot-testi Windows/Android/iOS'da; natija yomon bo'… | 27 | Manrope (`@fontsource-variable/manrope`) + self-hosted Noto Sans zaxirasi (`@fontsource-variable/noto-sans`, `apps/shell/src/noto-sans-fallback.css`, `unicode-range` faqat ʻ ʼ Ққ Ғғ Ҳҳ, PWA precache — G-02, asoschi qarori 26 #141); test: `apps/shell/e2e/font-glyphs.spec.ts` (400/700/800, tofu/tizim shrifti yo'q) |
| B0-T08 | ✅ | Kod sifati: mypy `--strict`, ESLint pul qoidasi, `pip-audit`/`pnpm audit --audit-level=high`/`gitleaks` CI'da, `.env.example`, qat'iy CSP (qaror #57) | 27 | mypy --strict, ruff, pip-audit, gitleaks, shellcheck (`.github/workflows/backend.yml`), ESLint pul qoidasi (`shared/config/eslint-config/rules/no-money-arithmetic.js` + test), `pnpm audit --audit-level=high` (`web.yml`), `.env.example` (test `test_env_example_lists_every_setting`), CSP nonce + statik xost sha256 zaxirasi (`apps/shell/csp.ts`, `csp-hashes.ts`, build guard; test `csp.test.ts`, `csp-hashes.test.ts`, `e2e/csp-nonce.spec.ts` — G-05), `get-nonce` pnpm katalogida (G-03) |
| B0-T09 | ⛔ | Sirlar va zaxira: SOPS/age (yoki o'z-hosted Vault), ilova darajasida envelope shifrlash (`tenant_secrets`), o'z WAL PITR, boshqa provayderda zaxira nusxa, UzCloud avto-to'lov + billing ogohlantirishi (qaror #65, #51) | 27 | repo qismi bajarildi (G-09): envelope shifrlash `backend/app/core/secrets.py` (test `test_auth_units.py::test_envelope_roundtrip_binding_and_rotation`), `.sops.yaml` (age), WAL-G zaxira/PITR/offsite/staging-restore skriptlari `backend/ops/backup/*.sh` + `RUNBOOK-backup-restore.md`, test `tests/unit/test_ops_backup.py`; tashqi (asoschi): UzCloud avto-to'lov + billing ogohlantirishi, DBaaS replikatsiya roli, S3 bucket'lar (UzCloud + ikkinchi provayder), age/WAL-G kalitlari — runbook ⛔ bo'limi |
| B0-T10 | ✅ | Shaxsiy ma'lumot: AI so'rov quruvchisida majburiy maskalash qatlami (o'chirib bo'lmaydi), `settings.ai_cross_border_enabled=false` standart (qaror #61) | 27 | `backend/app/modules/ai/privacy/masking.py` (o'chirib bo'lmaydi), rozilik darvozasi `ai/application/ports.py`; test: `tests/unit/test_ai_masking.py`, `tests/integration/test_ai_pii.py` |
| B0-T11 | ⛔ | Tashqi: asoschi — kompaniya yuridik shaxsi (MChJ) va xatlarni imzolovchi (26 #130) — barcha xatlardan oldin | 27 | asoschi — G-01 |
| B0-T12 | ⛔ | Tashqi: rasmiy xatlarni yuborish — "Tashqi bog'liqliklar" jadvalidagi har xat (`spec/tarix/tekshiruv/rasmiy-xatlar.md`, Xat 1–10; qo'shimcha savollar — `research_notes/ochiq-savollar/D-qarorlar-va-E-standartlar.md` §5.2); `letter_tracker` (15/30/60 kun, 26 #7… | 27 | #130 dan keyin; `letter_tracker` — asoschi — G-01 |
| B0-T13 | ⛔ | Tashqi: buxgalter bilan `13-provodka-qoidalari.md` ni tekshirish — tasdiqlangan hisoblar rejasi + ogohlantirish blokidagi bandlar bo'yicha yozma javoblar | 27 | asoschi + buxgalter — G-01 (`tests/unit/test_chart_of_accounts.py` kod ↔ 13 mosligini tekshiradi; buxgalter tasdig'i tashqi) |
| B0-T14 | ⛔ | Tashqi: o'z virtual kassamizni davlat reyestriga kiritish arizasi (VMQ-943 4-ilova, 35 ish kuni, Kiberxavfsizlik markazi xulosasi bilan — 26 #25/#42); parallel — pilot uchun fiskal hamkor (Multikassa/E-POS) bilan muzokara: lokal ko'prik ruxsati, bulut rejimi,… | 27 | asoschi — G-01 |
| B0-T15 | ⛔ | Tashqi: karta terminali hamkori muzokarasi — Rahmat, Humo (НМПЦ), Arca/ERA: API hujjati, test qurilma, NDA, narx (26 #172–#174); MayaSoft SoftPOS SDK (26 #175); BIN ro'yxati manbasi (26 #176) | 27 | asoschi — G-01 |
| B0-T16 | ⛔ | Tashqi: pentest tayyorgarligi — avtomatik DAST (OWASP ZAP) CI'ga ulash, ichki OAuth/to'lov/fiskal tekshiruv ro'yxati, Celion/ONESEC'dan rasmiy taklif so'rash (`15-xavfsizlik-va-audit.md` §8) | 27 | kod qismi bajarildi (G-11): OWASP ZAP baseline + API DAST — `.github/workflows/dast.yml`, qoidalar `backend/ops/zap/rules.tsv` (test `tests/unit/test_ops_backup.py`); tashqi: ichki OAuth/to'lov/fiskal tekshiruv ro'yxati va Celion/ONESEC taklifi — asoschi |
| B0-T17 | ⛔ | Tashqi: qo'llab-quvvatlash kanali — Telegram "/yordam" + bitta telefon raqami, ish vaqti va dam olish kuni navbatchilik jadvali (`25-nofunksional-talablar.md` §12) | 27 | asoschi — G-01 (bot/support havolalari runtime-config'da tayyor: `telegramBot`, `supportTelegram`, `supportPhone`, `supportUrl`) |
| B0-T18 | ⛔ | Tashqi: 15–20 do'kon egasi bilan suhbat, 5–10 pilot do'kon tanlash | 27 | asoschi — G-01 |
| B0-T19 | ⛔ | Tashqi: yurist — Foydalanish shartlari / ommaviy oferta (o'zbek tilida), shaxsiy ma'lumot bloki va chegaradan tashqari uzatishga rozilik, lokautda fiskal mas'uliyat (qaror #15), 24/72 soat insident runbook'i (26 #127, #126). Natija: imzolangan oferta — birinc… | 27 | asoschi + yurist — G-01 |

### Bosqich 0 — Tayyor ta'rifi (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B0-DoD-01 | ✅ | `GET /health` (`GET /health/live` ning aliasi — jarayon tirik; tayyorlik — `GET /health/ready`, `23-backend-arxitekturasi.md` §8) va RLS izolyatsiya testi yashil | 27 Tayyor ta'rifi | `backend/app/core/health.py` (`/health`, `/health/live`, `/health/ready`); test: `test_health_and_idempotency.py::test_health_ready_gates_on_postgres_schema_and_redis`, `test_core_misc.py::test_health_liveness_without_dependencies`; RLS — `tests/integration/test_rls.py` |
| B0-DoD-02 | ✅ | DataMatrix va shrift spike natijalari yozilgan | 27 Tayyor ta'rifi | `research_notes/ochiq-savollar/spike-datamatrix.md`, `spike-font.md` (Noto zaxirasi qabul qilindi — `08` §2) |
| B0-DoD-03 | ✅ | maskalash qatlami unit-testlari yashil | 27 Tayyor ta'rifi | `tests/unit/test_ai_masking.py` (31 holat) |
| B0-DoD-04 | ✅ | `/oauth/authorize`→`/oauth/token` to'liq Authorization Code+PKCE oqimi real Postgres/Redis'da ishlaydi (mock yo'q) | 27 Tayyor ta'rifi | `tests/integration/test_oauth.py` — haqiqiy PostgreSQL 16 + Redis (testcontainers yoki CI servislari, `tests/conftest.py`) |
| B0-DoD-05 | ✅ | login sahifasi, layout va generatsiya qilingan API klient ishlaydi | 27 Tayyor ta'rifi | BO-01 `web/apps/shell/src/pages/login/`, layout `src/app/ui/layout/`, klient `web/packages/shared/api/src/generated/`; test: `e2e/login.spec.ts`, `e2e/session.spec.ts`, `instance.test.ts` |
| B0-DoD-06 | ⛔ | yuridik shaxs bo'yicha asoschi qarori bor va rejalashtirilgan barcha rasmiy xatlar yuborilgan | 27 Tayyor ta'rifi | asoschi — G-01 |
| B0-DoD-07 | ⛔ | reyestr arizasi va hamkor muzokarasi boshlangan | 27 Tayyor ta'rifi | asoschi — G-01 |
| B0-DoD-08 | ✅ | QT-RLS-01…08, QT-OAUTH-01…07, QT-AI-PII-01 yashil | 27 Tayyor ta'rifi | `test_rls.py::test_qt_rls_01…08`, `test_oauth.py::test_qt_oauth_01…07`, `test_ai_pii.py`/`test_ai_masking.py::test_qt_ai_pii_01_*` |
| B0-DoD-09 | ✅ | CI'da `mypy --strict`, `pip-audit`, `pnpm audit --audit-level=high`, `gitleaks` | 27 Tayyor ta'rifi | `.github/workflows/backend.yml` (mypy --strict, pip-audit, gitleaks), `web.yml` (`pnpm audit --audit-level=high`) |
| B0-DoD-10 | ✅ | `devices.kind`/`signing_keys.purpose` migratsiya testi (qaror #58 c) | 27 Tayyor ta'rifi | `tests/integration/test_migrations.py` (qaror #58 c) |
| B0-DoD-11 | ⛔ | tashqi provayderdagi nusxadan staging restore bir marta (qaror #65). | 27 Tayyor ta'rifi | protsedura tayyor: `backend/ops/backup/staging-restore.sh`, `verify-restore.sql`, `RUNBOOK-backup-restore.md` (staging restore bo'limi); bajarish UzCloud hisobi, bucket'lar va kalitlardan keyin — asoschi (G-09) |

### Bosqich 0 — Endpointlar (14/17/18/19/20/33)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B0-EP-17#1 | ✅ | GET /health/live | 17 §1, 23 §8; 27 vazifa matni | kod: `backend/app/core/health.py`; test: `backend/tests/unit/test_core_misc.py` |
| B0-EP-17#2 | ✅ | GET /health/ready | 17 §1, 23 §8; 27 vazifa matni | kod: `backend/app/core/health.py`; test: `backend/tests/integration/test_health_and_idempotency.py`, `backend/tests/integration/test_metrics.py` |
| B0-EP-17#3 | ✅ | GET /metrics | 17 §1, 23 §8; 23 §8 / §1 skelet (`telemetry.py`) | kod: `backend/app/core/telemetry.py` (`GET /metrics`, Prometheus, bearer token, `ERP_METRICS_ENABLED`; OTel/Sentry config bilan — G-08); test: `tests/integration/test_metrics.py::test_metrics_report_requests_pool_and_queue_depth`, `tests/unit/test_telemetry.py` |
| B0-EP-17#4 | ✅ | GET /health (live aliasi, 27 B0) | 17 §1, 23 §8; 27 vazifa matni | kod: `backend/app/core/health.py`; test: `backend/tests/integration/test_health_and_idempotency.py`, `backend/tests/unit/test_core_misc.py`, `web/packages/shared/api/src/_base/instance.test.ts` |
| B0-EP-14#1 | ✅ | GET /.well-known/oauth-authorization-server | 14 §20; 27 B0: imzolash kaliti/JWKS, AS metadata | kod: `backend/app/modules/auth/api/oauth.py`; test: `backend/tests/integration/test_oauth.py` |
| B0-EP-14#2 | ✅ | GET /.well-known/jwks.json | 14 §20; 27 B0: imzolash kaliti/JWKS | kod: `backend/app/modules/auth/api/oauth.py`; test: `backend/tests/integration/test_oauth.py` |
| B0-EP-14#3 | ✅ | GET/POST /oauth/authorize | 14 §20; 27 vazifa matni | kod: `auth/api/oauth.py`, `auth/api/login_page.py`; test: `test_oauth.py`, `tests/unit/test_login_page.py` (BO-01 ko'rinishi — G-06) |
| B0-EP-14#4 | ✅ | POST /oauth/token | 14 §20; 27 vazifa matni | kod: `backend/app/modules/auth/api/oauth.py`; test: `backend/tests/integration/test_oauth.py`, `backend/tests/support/auth.py` |
| B0-EP-14#6 | ✅ | POST /oauth/revoke | 14 §20; 27 vazifa matni (`/*`) | kod: `auth/api/oauth.py`, `auth/application/revocation.py` (refresh → oila + jonli access tokenlar, access → `jti`); test: `test_oauth.py::test_revoke_and_introspect`, `test_auth_revocation_and_switch.py::test_oauth_revoke_refresh_kills_live_access_token_of_its_family`, `::test_oauth_revoke_access_token_by_jti_keeps_the_family`, `::test_oauth_revoke_reuse_detection_kills_every_access_token_of_the_family` |
| B0-EP-14#7 | ✅ | POST /oauth/introspect | 14 §20; 27 vazifa matni (`/*`) | kod: `backend/app/modules/auth/api/oauth.py`; test: `backend/tests/integration/test_oauth.py` |
| B0-EP-14#8 | ✅ | GET /auth/login/start | 14 §20; 27 vazifa matni (`/*`) | kod: `backend/app/modules/auth/api/bff.py`; test: `backend/tests/support/auth.py`, `web/apps/shell/e2e/credentials.spec.ts`, `web/apps/shell/e2e/login.spec.ts` |
| B0-EP-14#9 | ✅ | GET /auth/callback | 14 §20; 27 vazifa matni (`/*`) | kod: `backend/app/modules/auth/api/bff.py`; test: `backend/tests/integration/test_oauth.py`, `backend/tests/support/auth.py`, `backend/tests/unit/test_login_page.py` |
| B0-EP-14#18 | ✅ | POST /auth/logout | 14 §20; 27 vazifa matni (`/*`) | kod: `backend/app/modules/auth/api/bff.py`; test: `backend/tests/integration/test_auth_revocation_and_switch.py`, `backend/tests/integration/test_oauth.py` |
| B0-EP-14#19 | ✅ | POST /auth/sessions/revoke-all | 14 §20; 27 vazifa matni (`/*`) | kod: `auth/api/bff.py`; test: `test_auth_revocation_and_switch.py::test_auth_revoke_all_ends_every_session_in_every_tenant` (G-12), `web/packages/shared/state/src/session/session.test.ts` |
| B0-EP-14#20 | ✅ | GET /api/v1/auth/csrf | 14 §20; 27 vazifa matni (`/*`) | kod: `backend/app/modules/auth/api/bff.py`; test: `backend/tests/support/auth.py`, `web/apps/shell/e2e/branches.spec.ts`, `web/apps/shell/e2e/catalog.spec.ts` |
| B0-EP-14#22 | ✅ | GET /auth/session | 14 §20; 27 vazifa matni (`/*`) | kod: `backend/app/modules/auth/api/bff.py`; test: `backend/tests/integration/test_admin_users_credentials.py`, `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_sessions.py` |
| B0-EP-14#29 | ✅ | POST /bff/switch-tenant | 14 §20; 14 §9 — Bosqich 0 poydevori (BFF) | kod: `auth/api/bff.py`, `auth/application/bff.py` (14 §9); veb: `@shared/state` session `switchTenantFx`; test: `test_auth_revocation_and_switch.py::test_bff_switch_tenant_repoints_the_cookie`, `::test_bff_switch_tenant_refusals_keep_the_session`, `::test_bff_switch_tenant_needs_a_cookie_session`, `session.test.ts` |

### Bosqich 0 — Ekranlar (06/07)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B0-SCR-BO-01 | ✅ | BO-01 — Kirish (login), tenant/filial tanlash | 27 B0 Tayyor ta'rifi (login sahifasi) | `web/apps/shell/src/pages/login/` + AS sahifasi `backend/app/modules/auth/api/login_page.py` (BO-01 maketi va 07 ga moslandi: aria-invalid, 'Parolni unutdim?', ro'yxatdan o'tish havolasi, logo — G-06); test: `e2e/login.spec.ts`, `e2e/session.spec.ts`, `tests/unit/test_login_page.py::test_bo01_fields_and_links`, `::test_error_marks_fields_invalid_without_revealing_which` |

### Bosqich 0 — Jadvallar / migratsiyalar (12)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B0-TBL-platform.units | ✅ | `platform.units` (revizion 0007) | 12; infratuzilma — 12 §6.1 revizioni Bosqich 0 da | DDL 0007; kod va test: `backend/tests/integration/test_rls.py`, `backend/tests/integration/test_seed_and_worker.py` |
| B0-TBL-platform.plans | ✅ | `platform.plans` (revizion 0007) | 12; 27 vazifa matni | DDL 0007; kod va test: `backend/tests/integration/test_purge_idempotency.py`, `backend/tests/integration/test_rls.py` |
| B0-TBL-platform.addons | ✅ | `platform.addons` (revizion 0007) | 12; 27 vazifa matni | DDL 0007; kod va test: `backend/tests/integration/test_rls.py`, `backend/tests/integration/test_seed_and_worker.py` |
| B0-TBL-platform.oauth_clients | ✅ | `platform.oauth_clients` (revizion 0003) | 12; infratuzilma — 12 §6.1 revizioni Bosqich 0 da | DDL 0003; kod va test: `backend/tests/integration/test_seed_and_worker.py` |
| B0-TBL-platform.signing_keys | ✅ | `platform.signing_keys` (revizion 0007) | 12; 27 vazifa matni | DDL 0007; kod va test: `backend/tests/integration/test_migrations.py` |
| B0-TBL-platform.turnover_tax_rates | ✅ | `platform.turnover_tax_rates` (revizion 0007) | 12; infratuzilma — 12 §6.1 revizioni Bosqich 0 da | DDL 0007; kod va test: `backend/tests/integration/test_seed_and_worker.py` |
| B0-TBL-auth.login_attempts | ✅ | `auth.login_attempts` (revizion 0003) | 12; infratuzilma — 12 §6.1 revizioni Bosqich 0 da | DDL 0003; kod va test: `backend/tests/integration/test_migrations.py`, `backend/tests/integration/test_oauth.py` |
| B0-TBL-app.devices | ✅ | `app.devices` (revizion 0002) | 12; 27 vazifa matni | DDL 0002; kod va test: `backend/tests/integration/test_admin_users_sessions.py`, `backend/tests/integration/test_credentials_flow.py` |
| B0-TBL-app.expense_categories | ✅ | `app.expense_categories` (revizion 0018) | 12; 27 vazifa matni | DDL 0018; kod va test: `backend/tests/integration/test_health_and_idempotency.py`, `backend/tests/integration/test_seed_and_worker.py` |
| B0-TBL-app.audit_log | ✅ | `app.audit_log` (revizion 0024) | 12; infratuzilma — 12 §6.1 revizioni Bosqich 0 da | DDL 0024; kod va test: `backend/tests/integration/test_auth_revocation_and_switch.py`, `backend/tests/integration/test_catalog_products.py` |

### Bosqich 0 — Qabul testlari (31)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B0-QT-RLS-01 | ✅ | QT-RLS-01 (integration) — Berilgan Tenant A'da sale_id=S1 chek mavjud va Tenant B tizimda butunlay boshqa tenant, qachonki Tenant B foydalanuvchisi token bilan GET /api/… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_rls.py` :: `test_qt_rls_01_other_tenant_sale_is_not_found` |
| B0-QT-RLS-02 | ✅ | QT-RLS-02 (unit) — Berilgan DB sessiyasida app.tenant_id sozlanmagan (current_setting bo'sh), qachonki SELECT * FROM app.sales to'g'ridan-to'g'ri bajariladi, unda 0 qat… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_rls.py` :: `test_qt_rls_02_no_tenant_context_returns_nothing` |
| B0-QT-RLS-03 | ✅ | QT-RLS-03 (integration) — Berilgan Tenant A qurilmasi (device_id → faqat Tenant A'ga bog'langan) autentifikatsiyalangan, qachonki POST /sync/push payload'ida (frontend x… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_rls.py` :: `test_qt_rls_03_foreign_tenant_id_in_payload_is_not_written` |
| B0-QT-RLS-04 | ✅ | QT-RLS-04 (integration) — Berilgan oddiy tenant foydalanuvchisi (Egasi) tokeni, qachonki GET /platform/tenants (faqat platform_admins uchun) so'raladi, unda 403; Berilga… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_rls.py` :: `test_qt_rls_04_no_platform_bypass_for_the_app_role` |
| B0-QT-RLS-05 | ✅ | QT-RLS-05 (integration) — Berilgan platform.units/platform.plans/platform.addons kabi tenant_idsiz global jadval, qachonki oddiy erp_app roli bilan INSERT/UPDATE qilinsa… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_rls.py` :: `test_qt_rls_05_app_role_cannot_write_global_tables` |
| B0-QT-RLS-06 | ✅ | QT-RLS-06 (integration) — Berilgan Tenant B'da product_id=PB1 va price="9999.00" mavjud, Tenant A qurilmasi hali hech qachon bu ID bilan ishlamagan, qachonki Tenant A qu… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_rls.py` :: `test_qt_rls_06_other_tenant_catalog_and_prices_are_invisible` |
| B0-QT-RLS-07 | ✅ | QT-RLS-07 (integration) — Berilgan Tenant B qurilmasi /sync/push orqali counterparty.created voqeasini yuborgan (counterparty_id=CB1, Tenant B kontekstida qabul qilingan… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_rls.py` :: `test_qt_rls_07_search_does_not_leak_other_tenant_counterparty` |
| B0-QT-RLS-08 | ✅ | QT-RLS-08 (integration) — Berilgan bitta DB ulanishi (connection pool) ichida scheduler ketma-ket ikki tenant (Tenant A, keyin Tenant B) uchun job navbatga qo'yadi, biri… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_rls.py` :: `test_qt_rls_08_context_does_not_survive_on_a_pooled_connection` |
| B0-QT-OAUTH-01 | ✅ | QT-OAUTH-01 (integration) — Berilgan /oauth/authorize so'rovida code_challenge_method=plain, qachonki so'rov yuborilsa, unda rad etiladi (faqat S256 qabul qilinadi). | 31; 27 (aniq havola) | test: `backend/tests/integration/test_oauth.py` :: `test_qt_oauth_01_plain_code_challenge_is_rejected` |
| B0-QT-OAUTH-02 | ✅ | QT-OAUTH-02 (integration) — Berilgan to'g'ri code_challenge bilan olingan code, qachonki POST /oauth/tokenga noto'g'ri code_verifier bilan almashtirilsa, unda rad etilad… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_oauth.py` :: `test_qt_oauth_02_code_verifier_and_single_use` |
| B0-QT-OAUTH-03 | ✅ | QT-OAUTH-03 (integration) — Berilgan refresh_token=RT1 muvaffaqiyatli ishlatilgan (used_at o'rnatilgan, RT2 berilgan), qachonki RT1 qayta (now - used_at > 30 soniya) yub… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_auth_gate_fixes.py` |
| B0-QT-OAUTH-04 | ✅ | QT-OAUTH-04 (integration) — Berilgan RT1 endigina ishlatilgan (RT2 hali ishlatilmagan), qachonki RT1 ≤30 soniya ichida (tarmoq uzilishi/parallel so'rov taqlidi — single-… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_oauth.py` :: `test_qt_oauth_04_retry_within_grace_keeps_family` |
| B0-QT-OAUTH-05 | ✅ | QT-OAUTH-05 (integration) — Berilgan veb-BFF orqali faol sessiya, qachonki POST/PUT/PATCH/DELETE so'rovi X-CSRF-Token sarlavhasisiz yoki eskirgan token bilan yuborilsa,… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_oauth.py` :: `test_qt_oauth_05_bff_cookie_writes_need_csrf` |
| B0-QT-OAUTH-06 | ✅ | QT-OAUTH-06 (integration) — Berilgan Android POS (public client, to'g'ridan-to'g'ri Bearer), qachonki X-CSRF-Tokensiz yozuvchi so'rov yuborilsa, unda CSRF tekshiruvidan… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_oauth.py` :: `test_qt_oauth_06_android_bearer_is_csrf_exempt` |
| B0-QT-OAUTH-07 | ✅ | QT-OAUTH-07 (integration) — Berilgan Egasi xodimni "Bloklash" tugmasini bosadi (US-M13-05), qachonki amal bajarilgan zahoti, unda shu xodimning barcha sessions/refresh_t… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_admin_users_update.py` |
| B0-QT-AI-PII-01 | ✅ | QT-AI-PII-01 (integration) — Berilgan AI-01 so'rovi "Aliyev Vali qancha qarz?" va tool natijasida mijoz ismi, telefoni, STIR/PINFL bor, qachonki Claude'ga yuboriladigan… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_ai_pii.py` :: `test_qt_ai_pii_01_token_map_is_not_persisted` |

## Bosqich 1: ro'yxatdan o'tish va katalog

**Maqsad (27):** Yangi do'kon mustaqil ro'yxatdan o'tadi, xodim qo'shadi, katalogini yuklaydi va turli kirish usullari bilan kira oladi.

Holat: ✅ 143 · 🟡 0 · ⬜ 0 · ⛔ 0 · ⏭ 0 · jami 143

### Bosqich 1 — Vazifalar (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B1-T01 | ✅ | M17 ro'yxatdan o'tish: `POST /auth/signup` — bitta tranzaksiyada tenant+obuna (trial 30 kun)+Egasi+5 rol+standart filial/ombor/kassa provisioning (`14-autentifikatsiya-oauth2.md` §4/§20); ro'yxatdan o'tish formasida Foydalanish shartlari aksepti — `tenants.ac…` | 27 | `auth/api/signup.py`, `auth/application/signup.py` (`business_type` → filial `activity_type` va birinchi `branch_tax_settings`, Toshkent sanasi), `auth/infrastructure/signup_repository.py`, `access/application/provisioning.py`, `branches/application/services.py`, `billing/application/trial.py`; test: `test_signup_flow.py::test_qt_m17_01_sms_code_then_trial_and_full_provisioning`, `::test_signup_is_one_transaction`, `::test_qt_m17_08_terms_required_current_and_consent_recorded`, `::test_signup_business_type_other_reaches_the_branch_and_its_tax_setting`, `::test_signup_rate_limited_per_ip_and_cross_origin_refused` |
| B1-T02 | ✅ | Do'kon sozlamalari (BO-21, BO-14), `tenants.legal_form` ("Egasi oldi" hisobi uchun, 26 #39); filial sozlamasida `branches.settlement_category` (`city_100k_plus`/`other`/`remote_mountain`, aylanma solig'i stavkasi uchun, SK 467-modda) | 27 | `branches/api/tenant.py`, `branches/application/tenant_settings.py`, `branches/api/branches.py` (`settlement_category`, standart `city_100k_plus`); test: `test_tenant_settings_api.py`, `test_branches_api.py::test_qt_m14_03/04/05_*`, `e2e/store-settings.spec.ts`, `e2e/branches.spec.ts` |
| B1-T03 | ✅ | `/install` — autentifikatsiyasiz ochiq route, biznes ekranlardan tashqari; BO-21 ⑥ bosqichi va iOS o'rnatish yo'riqnomasi shu komponentni ichiga oladi (`07-ekran-tafsilotlari.md` UX-INSTALL, BO-21 ⑥) | 27 | `web/packages/pages/billing/src/pages/install/`, `features/install-guide/`, `apps/shell/src/features/ios-install-gate/` (`@shared/lib/platform`), ochiq route `createPublicRoutes`; test: `e2e/install.spec.ts`, `install-guide/model/model.test.ts` |
| B1-T04 | ✅ | M13/M14: xodim qo'shish, standart rollar, bitta filial va ombor avtomatik; yangi filial qo'shish (US-M14-03) | 27 | `auth/application/admin_users.py::create` (mavjud hisob — `invited`, qabul qilinguncha kirish yo'q), provisioning, `branches/application/branches.py`; test: `test_admin_users_invite.py::test_qt_m13_04_invite_sends_one_time_code_never_a_secret`, `::test_invite_of_an_existing_account_waits_for_acceptance`, `test_branches_api.py::test_qt_m14_02_*` |
| B1-T05 | ✅ | Admin foydalanuvchilar paneli (BO-11): xodim bloklash, rol/filial tayinlash, xodimni to'liq ma'lumoti bilan qo'shish (US-M13-04), PIN/parolni qayta o'rnatish (US-M13-06, bir martalik taklif/tiklash kodi — Telegram bot birinchi, SMS faqat zaxira, qaror #34), s… | 27 | `auth/api/admin_users.py` (PATCH `status`/`role_ids`/`branch_ids`, reset-pin/password — boshqa tenantdagi hisobda rad, Egasi nishoniga faqat Egasi), `auth/application/admin_users.py`; veb BO-11 `pages/settings/src/pages/users/`; test: `test_admin_users_update.py`, `test_admin_users_credentials.py`, `test_admin_users_sessions.py`, `test_admin_users_invite.py`, `e2e/staff.spec.ts` |
| B1-T06 | ✅ | M09: tovarlar, shtrix-kodlar, MXIK kodi, narx va narx tarixi | 27 | `catalog/` (tovar, shtrix-kod, MXIK, toifa, birlik), `pricing/` (narx, narx tarixi `set_by_name`, `GET /products` `current_price`, narx o'zgarishlari); test: `test_catalog_products.py`, `test_catalog_mxik.py`, `test_pricing_price_changes.py`, `test_pricing_current_price.py`, `tests/unit/test_catalog_barcodes.py`, `tests/unit/test_pricing_resolution.py`, `e2e/catalog.spec.ts`, `e2e/prices.spec.ts` |
| B1-T07 | ✅ | Import (US-M04-04): `import_jobs` orqali (yuklash → tekshirish/xatolar ro'yxati → tasdiqlash) | 27 | `imports/` (yuklash → tekshirish/xatolar → tasdiqlash; xlsx zip/o'lcham/qator chegaralari, 413 `FILE_TOO_LARGE`); test: `test_import_jobs.py::test_us_m04_04_csv_upload_validate_commit`, `::test_upload_limits_and_file_checks`, `::test_commit_rechecks_catalog_and_rls`, `tests/unit/test_import_parsing.py::test_xlsx_far_cell_fails_fast`, `::test_zip_bomb_ratio_and_unpacked_size_are_refused_before_parsing`, `e2e/product-import.spec.ts`. Boshlang'ich qoldiq importi — B2 (27 B2 `stock_openings`), qarzlar — B4 |
| B1-T08 | ✅ | Telegram OTP — real (`21-integratsiyalar.md` §11.1 — asosiy kanal); SMS — `EskizSmsAdapter` `ERP_ESKIZ_TEST_MODE=true` (`21-integratsiyalar.md` §10 — faqat zaxira; Eskiz shartnomasi Bosqich 6 gacha, 26 #45); `FakeSms`/`FakeTelegram` faqat lokal dev'da flag bi… | 27 | `auth/application/otp.py`, `integrations/otp/infrastructure/{telegram,eskiz,fakes}.py` (Telegram birinchi, Eskiz test rejimi, staging/prod'da fake taqiqlangan); test: `test_otp_flow.py::test_telegram_is_the_first_channel_when_linked`, `::test_telegram_failure_falls_back_to_sms`, `::test_qt_m17_06_no_channel_delivers_503`, `::test_eskiz_test_mode_sends_only_the_allowed_text`, `::test_refused_requests_do_not_spend_the_sms_budget`, `test_otp_service.py` |
| B1-T09 | ✅ | `purge_idempotency_keys` cron job'i (`23-backend-arxitekturasi.md` §4; `ERP_IDEMPOTENCY_RETENTION_DAYS`, tenant fan-out) — birinchi yozuvchi back-office endpoint bilan birga | 27 | `workers/cron.py` (03:30 Toshkent), `workers/jobs/system.py` (tenant fan-out, `ERP_IDEMPOTENCY_RETENTION_DAYS`); test: `test_purge_idempotency.py` |
| B1-T10 | ✅ | Modul qatlamlari: `application` qatlami `infrastructure`ni faqat port (Protocol) orqali ko'radi, implementatsiya `wiring.py`da ulanadi; CI'da `import-linter` shartnomasi (`23-backend-arxitekturasi.md` §1) | 27 | `backend/pyproject.toml` `[tool.importlinter]` (5 shartnoma), CI `.github/workflows/backend.yml` (`lint-imports`); har modulda `application/ports.py` + `wiring.py`; `lint-imports`: 5 kept, 0 broken |
| B1-T11 | ✅ | Google bilan kirish (`/auth/google/start`/`/auth/google/callback`, `user_identities` jadvali, `14-autentifikatsiya-oauth2.md` §2.2) — qo'shimcha ixtiyoriy login yo'li, telefon+parol/OTP'ni almashtirmaydi | 27 | `auth/application/google.py`, `auth/infrastructure/google_oidc.py` (JWKS faqat noma'lum `kid`da, 60 s), `/auth/google/{start,callback}` (sozlanmagan bo'lsa → `/login?error=google_auth_failed`, IP limit); veb `googleEnabled` runtime-config; test: `test_google_login.py` (`test_qt_m17_02_*`), `tests/unit/test_auth_units.py`, `e2e/signup.spec.ts` |

### Bosqich 1 — Tayyor ta'rifi (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B1-DoD-01 | ✅ | ro'yxatdan o'tish ≤ 2 daqiqa, 500 tovar Excel importi bilan ≤ 10 daqiqa (QT-NFR-SIGNUP-01) | 27 Tayyor ta'rifi | `test_signup_flow.py::test_qt_nfr_signup_01_otp_verify_signup_session_under_two_minutes` (~1 s), `test_import_jobs.py::test_qt_nfr_signup_01_catalog_import_500_products_xlsx` (~1.3 s, < 120 s); server vaqti — brauzer e2e vaqti kuzatiladi, blok emas (31). "Birinchi sotuv" qismi — B3 |
| B1-DoD-02 | ✅ | foydalanuvchi telefon+OTP (Telegram OTP real; SMS — test rejimi) yoki Google bilan ham kirishi mumkin | 27 Tayyor ta'rifi | telefon+parol (OTP bilan ro'yxatdan o'tgach): `test_signup_flow.py::test_signup_owner_can_log_in_with_phone_and_password`; OTP tiklash: `test_credentials_flow.py::test_recovery_end_to_end_*`; Google: `test_google_login.py` |
| B1-DoD-03 | ✅ | tegishli US qabul mezonlari avtomatik test bilan qoplangan. | 27 Tayyor ta'rifi | barcha B1 QT nomli testlar bilan (pastdagi QT qatorlari); QT-M09-09 ning posting'dagi qayta tekshiruvi — B3 (sotuv kerak, 19 §4) |

### Bosqich 1 — Hikoyalar (27 → 30)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B1-US-M17-01 | ✅ | US-M17-01 — 2 daqiqada ro'yxatdan o'tish | 27 Hikoyalar; 30 (Must) | B1-T01, T08, T11 ga qarang; veb BO-21 `pages/billing/src/pages/onboarding/`; test: `e2e/signup.spec.ts`, `test_signup_flow.py` |
| B1-US-M13-01 | ✅ | US-M13-01 — Xodim qo'shib, rol(lar) belgilash | 27 Hikoyalar; 30 (Must) | `test_access_roles.py::test_qt_m13_01_role_grants_its_permissions`, `test_admin_users_invite.py::test_qt_m13_01_cashier_role_gives_cashier_permissions` |
| B1-US-M13-02 | ✅ | US-M13-02 — Kichik do'konda bitta xodimga bir nechta rol | 27 Hikoyalar; 30 (Must) | `test_access_roles.py::test_qt_m13_02_two_roles_union_and_most_generous_limit`, `test_admin_users_invite.py::test_qt_m13_02_two_roles_give_the_union_and_the_higher_right_wins` |
| B1-US-M13-03 | ✅ | US-M13-03 — Operatsiya limitlarini rolga/shaxsga bog'lab sozlash | 27 Hikoyalar; 30 (Should) | `access/api/roles.py`, `access/application/roles.py` (limitlar rolga, Egasi — 31 QT-M13-03 tuzatildi); test: `test_access_roles.py::test_qt_m13_03_limit_change_takes_effect_immediately`, `::test_put_permissions_validation` |
| B1-US-M13-04 | ✅ | US-M13-04 — Xodimni admin panel orqali to'liq ma'lumoti bilan qo'shish | 27 Hikoyalar; 30 (Must) | `test_admin_users_invite.py::test_qt_m13_04_*`, `::test_us_m13_04_staff_sees_only_assigned_branches`, `::test_invite_of_an_existing_account_waits_for_acceptance`; veb `/invite` (`credential-set`, `invite_accepted`), `e2e/credentials.spec.ts` |
| B1-US-M13-05 | ✅ | US-M13-05 — Xodimni vaqtincha bloklash/blokdan chiqarish | 27 Hikoyalar; 30 (Must) | `test_admin_users_update.py::test_qt_m13_05_block_revokes_now_and_unblock_restores_login`, `::test_qt_m13_09_*` |
| B1-US-M13-06 | ✅ | US-M13-06 — Xodimning parolini/PIN kodini qayta tiklash | 27 Hikoyalar; 30 (Must) | `test_admin_users_credentials.py::test_qt_m13_06_reset_password_kills_sessions_and_sends_admin_reset_code`, `::test_qt_m13_06_reset_pin_forces_a_new_pin_and_keeps_sessions`; o'zi tiklash: `test_credentials_flow.py::test_recovery_end_to_end_*`; `e2e/credentials.spec.ts`. POS-01 da majburiy yangi PIN — B3 |
| B1-US-M13-07 | ✅ | US-M13-07 — Xodim sessiyalarini ko'rish va bekor qilish | 27 Hikoyalar; 30 (Must) | `test_admin_users_sessions.py::test_qt_m13_07_revoking_one_session_leaves_the_other`, `::test_revoke_sessions_ends_every_session_and_device_token` |
| B1-US-M14-03 | ✅ | US-M14-03 — Yangi filial (do'kon) qo'shish | 27 Hikoyalar; 30 (Must) | `test_branches_api.py::test_qt_m14_02_*` (haqiqiy tenant kabi "Kassa 1" bilan — `ADDON_REQUIRED`), `::test_cash_register_patch_fiscal_pair_and_archive` |
| B1-US-M14-04 | ✅ | US-M14-04 — Filial uchun "aholi punkti toifasi"ni belgilash (aylanma solig'i) | 27 Hikoyalar; 30 (Must) | `test_branches_api.py::test_qt_m14_03/04/05_*`, `::test_patch_branch_upserts_current_month_and_keeps_history`, `tests/unit/test_branches_domain.py::test_qt_m14_05_*`, `settings/src/pages/branches/model/model.test.ts` |
| B1-US-M09-01 | ✅ | US-M09-01 — Narxni yangilash, eski narx tarixda saqlanishi | 27 Hikoyalar; 30 (Must) | `test_pricing_price_changes.py::test_qt_m09_01_manager_updates_price_old_one_goes_to_history`, `tests/unit/test_pricing_resolution.py::test_qt_m09_01_*`, `e2e/prices.spec.ts` |
| B1-US-M09-05 | ✅ | US-M09-05 — Shtrix-kodi yo'q tovarga ichki shtrix-kod berish | 27 Hikoyalar; 30 (Should) | `catalog/domain/barcodes.py`, `ProductService.generate_internal_barcode`; test: `test_catalog_products.py::test_qt_m09_05_internal_barcode_generation`, `tests/unit/test_catalog_barcodes.py`. Yorliqda chop — B6 (US-M09-04) |
| B1-US-M04-04 | ✅ | US-M04-04 — Boshlang'ich katalog/qoldiq kiritish (qo'lda/import/AI-03) | 27 Hikoyalar; 30 (Must) | qo'lda: `POST /products` (`test_catalog_products.py::test_product_crud_version_archive`); import: `test_import_jobs.py::test_us_m04_04_*`, `e2e/product-import.spec.ts`. Boshlang'ich qoldiq — B2 (27 B2), AI-03 — B6 |

### Bosqich 1 — Endpointlar (14/17/18/19/20/33)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B1-EP-14#10 | ✅ | POST /auth/signup | 14 §20; 27 B1: `POST /auth/signup` | kod: `backend/app/modules/auth/api/signup.py`; test: `backend/tests/integration/test_credentials_flow.py`, `backend/tests/integration/test_google_login.py`, `backend/tests/integration/test_signup_flow.py` |
| B1-EP-14#11 | ✅ | POST /auth/otp/request | 14 §20; 27 B1: Telegram OTP real (`/auth/otp/*`) | kod: `backend/app/modules/auth/api/signup.py`; test: `backend/tests/integration/test_otp_flow.py`, `backend/tests/integration/test_signup_flow.py`, `backend/tests/support/auth_signup.py` |
| B1-EP-14#12 | ✅ | POST /auth/otp/verify | 14 §20; 27 B1: Telegram OTP real (`/auth/otp/*`) | kod: `backend/app/modules/auth/api/signup.py`; test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_credentials_flow.py`, `backend/tests/integration/test_otp_flow.py` |
| B1-EP-14#13 | ✅ | POST /auth/credentials | 14 §20; 27 B1: taklif/tiklash kodi bilan kredensial o'rnatish (US-M13-04/06, 14 §4.2) | kod: `backend/app/modules/auth/api/signup.py`; test: `backend/tests/integration/test_credentials_flow.py`, `web/apps/shell/e2e/credentials.spec.ts` |
| B1-EP-14#14 | ✅ | GET /auth/terms | 14 §20; 27 B1: Foydalanish shartlari aksepti | kod: `backend/app/modules/billing/api/terms.py`; test: `backend/tests/integration/test_terms_current.py`, `web/apps/shell/e2e/login.spec.ts`, `web/apps/shell/e2e/signup.spec.ts` |
| B1-EP-14#15 | ✅ | GET /auth/google/start | 14 §20; 27 B1: Google bilan kirish (§2.2) | kod: `backend/app/modules/auth/api/signup.py`; test: `backend/tests/integration/test_google_login.py`, `backend/tests/unit/test_login_page.py`, `backend/tests/unit/test_otp_units.py` |
| B1-EP-14#16 | ✅ | GET /auth/google/callback | 14 §20; 27 B1: Google bilan kirish (§2.2) | kod: `backend/app/modules/auth/api/signup.py`; test: `backend/tests/integration/test_google_login.py` |
| B1-EP-14§18.2#1 | ✅ | GET /admin/users — Xodimlar ro'yxati | 14 §18.2; 30 (US API) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_update.py`, `backend/tests/support/admin_users.py` |
| B1-EP-14§18.2#2 | ✅ | POST /admin/users — Xodim qo'shish | 14 §18.2; 30 (US API) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_update.py`, `backend/tests/support/admin_users.py` |
| B1-EP-14§18.2#3 | ✅ | PATCH /admin/users/{id} — Xodimni bloklash | 14 §18.2; 30 (US API) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_update.py`, `backend/tests/integration/test_auth_gate_fixes.py` |
| B1-EP-14§18.2#4 | ✅ | PATCH /admin/users/{id} — Rol/filial tayinlash (mavjud) | 14 §18.2; 30 (US API) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_update.py`, `backend/tests/integration/test_auth_gate_fixes.py` |
| B1-EP-14§18.2#5 | ✅ | POST /admin/users/{id}/reset-pin — PIN'ni qayta o'rnatish | 14 §18.2; 30 (resurs) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_credentials.py`, `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_sessions.py` |
| B1-EP-14§18.2#6 | ✅ | POST /admin/users/{id}/reset-password — Parolni tiklash (Egasi tomonidan) | 14 §18.2; 30 (US API) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_credentials.py`, `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_update.py` |
| B1-EP-14§18.2#7 | ✅ | POST /admin/users/{id}/revoke-sessions — Sessiya/qurilmalarni bekor qilish | 14 §18.2; 30 (US API) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_sessions.py`, `backend/tests/integration/test_admin_users_update.py` |
| B1-EP-14§18.2#8 | ✅ | GET /admin/users/{id}/sessions — Sessiya/qurilmalarni bekor qilish | 14 §18.2; 30 (US API) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_sessions.py`, `web/apps/shell/e2e/staff.spec.ts` |
| B1-EP-14§18.2#9 | ✅ | GET /admin/users/{id}/devices — Sessiya/qurilmalarni bekor qilish | 14 §18.2; 30 (US API) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_sessions.py`, `web/apps/shell/e2e/staff.spec.ts` |
| B1-EP-14§18.2#10 | ✅ | GET /admin/users — Sessiya/qurilmalarni bekor qilish | 14 §18.2; 30 (US API) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_update.py`, `backend/tests/support/admin_users.py` |
| B1-EP-14§18.2#11 | ✅ | POST /admin/users/{id}/sessions/{session_id}/revoke — Bitta sessiyani bekor qilish | 14 §18.2; 30 (US API) | kod: `backend/app/modules/auth/api/admin_users.py`; test: `backend/tests/integration/test_admin_users_sessions.py`, `backend/tests/integration/test_admin_users_update.py`, `web/apps/shell/e2e/staff.spec.ts` |
| B1-EP-18#16 | ✅ | POST /api/v1/price-changes/{id}/post → approval-requests bog'lanishi | 18 §10; 30 (US API) | kod: `backend/app/modules/pricing/api/router.py`; test: `backend/tests/integration/test_pricing_price_changes.py`, `backend/tests/support/catalog.py`, `web/apps/shell/e2e/prices.spec.ts` |
| B1-EP-19#1 | ✅ | GET /products | 19 §1; 30 (resurs) | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py`, `backend/tests/integration/test_import_jobs.py`, `backend/tests/integration/test_pricing_current_price.py` |
| B1-EP-19#2 | ✅ | POST /products | 19 §1; 30 (resurs) | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py`, `backend/tests/integration/test_import_jobs.py`, `backend/tests/integration/test_pricing_current_price.py` |
| B1-EP-19#3 | ✅ | GET /products/{id} · PATCH /products/{id} | 19 §1; 30 (resurs) | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py`, `backend/tests/integration/test_pricing_current_price.py`, `web/apps/shell/e2e/catalog.spec.ts` |
| B1-EP-19#4 | ✅ | POST /products/{id}/archive · POST /products/{id}/unarchive | 19 §1; 30 (resurs) | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py`, `backend/tests/integration/test_pricing_price_changes.py` |
| B1-EP-19#5 | ✅ | Shtrix-kodlar — GET/POST /products/{id}/barcodes · DELETE /products/{id}/barcodes/{barcod… | 19 §1; 30 (resurs) | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py`, `web/apps/shell/e2e/catalog.spec.ts` |
| B1-EP-19#6 | ✅ | POST /products/{id}/barcodes/internal-generate | 19 §1; 30 (US API) | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py`, `web/apps/shell/e2e/catalog.spec.ts` |
| B1-EP-19#7 | ✅ | GET /product-categories | 19 §2; katalog (M09) — 27 B1 | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py`, `web/apps/shell/e2e/catalog.spec.ts`, `web/apps/shell/e2e/permissions.spec.ts` |
| B1-EP-19#8 | ✅ | POST /product-categories | 19 §2; katalog (M09) — 27 B1 | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py`, `web/apps/shell/e2e/catalog.spec.ts`, `web/apps/shell/e2e/permissions.spec.ts` |
| B1-EP-19#9 | ✅ | PATCH /product-categories/{id} | 19 §2; katalog (M09) — 27 B1 | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py` |
| B1-EP-19#10 | ✅ | POST /product-categories/{id}/archive | 19 §2; katalog (M09) — 27 B1 | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py` |
| B1-EP-19#11 | ✅ | GET /units | 19 §3; birliklar — katalog, 27 B1 | kod: `backend/app/modules/catalog/api/router.py`; test: `backend/tests/integration/test_catalog_products.py`, `web/apps/shell/e2e/catalog.spec.ts`, `web/apps/shell/e2e/prices.spec.ts` |
| B1-EP-19#12 | ✅ | GET /products/{id}/prices | 19 §4; 30 (US API) | kod: `backend/app/modules/pricing/api/router.py`; test: `backend/tests/integration/test_catalog_products.py`, `backend/tests/integration/test_import_jobs.py`, `backend/tests/integration/test_pricing_current_price.py` |
| B1-EP-19#13 | ✅ | POST /price-changes | 19 §4; 30 (US API) | kod: `backend/app/modules/pricing/api/router.py`; test: `backend/tests/integration/test_pricing_price_changes.py`, `backend/tests/support/catalog.py`, `web/apps/shell/e2e/prices.spec.ts` |
| B1-EP-19#14 | ✅ | POST /price-changes/{id}/post | 19 §4; 30 (US API) | kod: `backend/app/modules/pricing/api/router.py`; test: `backend/tests/integration/test_pricing_price_changes.py`, `backend/tests/support/catalog.py`, `web/apps/shell/e2e/prices.spec.ts` |
| B1-EP-19#20 | ✅ | GET /import-jobs/templates/{kind} | 19 §6; 30 (resurs) | kod: `backend/app/modules/imports/api/router.py`; test: `web/apps/shell/e2e/product-import.spec.ts` |
| B1-EP-19#21 | ✅ | POST /import-jobs | 19 §6; 30 (US API) | kod: `backend/app/modules/imports/api/router.py`; test: `backend/tests/integration/test_import_jobs.py`, `backend/tests/unit/test_body_limit.py`, `web/apps/shell/e2e/product-import.spec.ts` |
| B1-EP-19#22 | ✅ | POST /import-jobs/{id}/validate | 19 §6; 30 (resurs) | kod: `backend/app/modules/imports/api/router.py`; test: `backend/tests/integration/test_import_jobs.py` |
| B1-EP-19#23 | ✅ | GET /import-jobs/{id} | 19 §6; 30 (resurs) | kod: `backend/app/modules/imports/api/router.py`; test: `web/apps/shell/e2e/product-import.spec.ts` |
| B1-EP-19#24 | ✅ | GET /import-jobs/{id}/errors | 19 §6; 30 (resurs) | kod: `backend/app/modules/imports/api/router.py`; test: `backend/tests/integration/test_import_jobs.py` |
| B1-EP-19#25 | ✅ | POST /import-jobs/{id}/commit | 19 §6; 30 (resurs) | kod: `backend/app/modules/imports/api/router.py`; test: `backend/tests/integration/test_import_jobs.py` |
| B1-EP-20#24 | ✅ | GET /roles — Rollar ro'yxati | 20 indeks; 30 (resurs) | kod: `backend/app/modules/access/api/roles.py`; test: `backend/tests/integration/test_access_roles.py`, `web/apps/shell/e2e/staff.spec.ts`, `web/packages/pages/settings/src/pages/users/model/model.test.ts` |
| B1-EP-20#25 | ✅ | POST /roles — Yangi (maxsus) rol yaratish | 20 indeks; 30 (resurs) | kod: `backend/app/modules/access/api/roles.py`; test: `backend/tests/integration/test_access_roles.py`, `web/apps/shell/e2e/staff.spec.ts`, `web/packages/pages/settings/src/pages/users/model/model.test.ts` |
| B1-EP-20#26 | ✅ | PATCH /roles/{id} — Rol nomini tahrirlash | 20 indeks; 30 (resurs) | kod: `backend/app/modules/access/api/roles.py`; test: `backend/tests/integration/test_access_roles.py` |
| B1-EP-20#27 | ✅ | GET /roles/{id}/permissions — Rolning ruxsat/limit ro'yxati | 20 indeks; 30 (US API) | kod: `backend/app/modules/access/api/roles.py`; test: `backend/tests/integration/test_access_roles.py` |
| B1-EP-20#28 | ✅ | PUT /roles/{id}/permissions — Rol ruxsat/limitlarini belgilash | 20 indeks; 30 (US API) | kod: `backend/app/modules/access/api/roles.py`; test: `backend/tests/integration/test_access_roles.py` |
| B1-EP-20#29 | ✅ | GET /permissions-catalog — To'liq ruxsat kodlari katalogi (statik) | 20 indeks; US-M13-03 (30 §2b, 20 #27–29) | kod: `backend/app/modules/access/api/roles.py`; test: `backend/tests/integration/test_access_roles.py` |
| B1-EP-20#30 | ✅ | GET /branches — Filiallar ro'yxati | 20 indeks; 30 (US API) | kod: `backend/app/modules/branches/api/branches.py`; test: `backend/tests/integration/test_admin_users_update.py`, `backend/tests/integration/test_branches_api.py`, `backend/tests/integration/test_devices_api.py` |
| B1-EP-20#31 | ✅ | POST /branches — Yangi filial yaratish | 20 indeks; 30 (US API) | kod: `backend/app/modules/branches/api/branches.py`; test: `backend/tests/integration/test_admin_users_update.py`, `backend/tests/integration/test_branches_api.py`, `backend/tests/integration/test_devices_api.py` |
| B1-EP-20#32 | ✅ | GET /branches/{id} — Filial tafsiloti | 20 indeks; 30 (resurs) | kod: `backend/app/modules/branches/api/branches.py`; test: `backend/tests/integration/test_branches_api.py` |
| B1-EP-20#33 | ✅ | PATCH /branches/{id} — Filialni tahrirlash | 20 indeks; 30 (resurs) | kod: `backend/app/modules/branches/api/branches.py`; test: `backend/tests/integration/test_branches_api.py` |
| B1-EP-20#34 | ✅ | GET /branches/{id}/tax-settings — Aholi punkti toifasi tarixi | 20 indeks; 30 (US API) | kod: `backend/app/modules/branches/api/branches.py`; test: `backend/tests/integration/test_branches_api.py` |
| B1-EP-20#35 | ✅ | POST /branches/{id}/tax-settings — Yangi toifa qiymati qo'shish | 20 indeks; 30 (US API) | kod: `backend/app/modules/branches/api/branches.py`; test: `backend/tests/integration/test_branches_api.py` |
| B1-EP-20#37 | ✅ | GET /warehouses — Omborlar ro'yxati | 20 indeks; US-M14-03 (30 §2b) | kod: `backend/app/modules/branches/api/branches.py`; test: `backend/tests/integration/test_branches_api.py`, `web/apps/shell/e2e/branches.spec.ts` |
| B1-EP-20#37a | ✅ | PATCH /warehouses/{id} — Ombor nomi va tovar hisobini (2910/2920) o'zgartirish | 20 indeks; US-M14-03 (30 §2b) | kod: `backend/app/modules/branches/api/branches.py`; test: `backend/tests/integration/test_branches_api.py` |
| B1-EP-20#38 | ✅ | GET /cash-registers — Kassalar ro'yxati | 20 indeks; 30 (katalog raqami) | kod: `backend/app/modules/branches/api/cash_registers.py`; test: `backend/tests/integration/test_branches_api.py`, `web/apps/shell/e2e/branches.spec.ts` |
| B1-EP-20#39 | ✅ | POST /cash-registers — Yangi kassa qo'shish | 20 indeks; 30 (katalog raqami) | kod: `backend/app/modules/branches/api/cash_registers.py`; test: `backend/tests/integration/test_branches_api.py`, `web/apps/shell/e2e/branches.spec.ts` |
| B1-EP-20#40 | ✅ | PATCH /cash-registers/{id} — Kassani tahrirlash | 20 indeks; 30 (katalog raqami) | kod: `backend/app/modules/branches/api/cash_registers.py`; test: `backend/tests/integration/test_branches_api.py` |
| B1-EP-20#40a | ✅ | GET /tenant/settings — Do'kon sozlamalari + integratsiya holati | 20 indeks; 27 B1: do'kon sozlamalari (BO-14, BO-21) | kod: `backend/app/modules/branches/api/tenant.py`; test: `backend/tests/integration/test_tenant_settings_api.py`, `web/apps/shell/e2e/store-settings.spec.ts` |
| B1-EP-20#40b | ✅ | PATCH /tenant/settings — Do'kon nomi, yuridik shakli, bank hisobi va tenant siyosatlari | 20 indeks; 27 B1: do'kon sozlamalari (`tenants.legal_form`) | kod: `backend/app/modules/branches/api/tenant.py`; test: `backend/tests/integration/test_tenant_settings_api.py`, `web/apps/shell/e2e/store-settings.spec.ts` |
| B1-EP-20#40c | ✅ | POST /tenant/tax-regimes — Soliq rejimini o'zgartirish (keyingi oydan) | 20 indeks; do'kon sozlamalari BO-14 — 27 B1 | kod: `backend/app/modules/branches/api/tenant.py`; test: `backend/tests/integration/test_tenant_settings_api.py`, `web/apps/shell/e2e/store-settings.spec.ts` |
| B1-EP-20#40h | ✅ | POST /tenant/consents — AI chegaradan tashqari uzatish roziligini qabul qilish/qaytarib o… | 20 indeks; 30 (US API) | kod: `backend/app/modules/branches/api/tenant.py`; test: `backend/tests/integration/test_tenant_settings_api.py`, `web/apps/shell/e2e/store-settings.spec.ts`, `web/packages/pages/settings/src/pages/tenant/model/model.test.ts` |
| B1-EP-20#40i | ✅ | POST /cash-registers/{id}/archive — Kassani arxivlash | 20 indeks; 30 (resurs) | kod: `backend/app/modules/branches/api/cash_registers.py`; test: `backend/tests/integration/test_branches_api.py` |

### Bosqich 1 — Ekranlar (06/07)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B1-SCR-BO-01 | ✅ | BO-01 — Kirish (login), tenant/filial tanlash | 07; 27/30 | `apps/shell/src/pages/login/` (Google — `googleEnabled`, `/recover`, `/invite`, shartlar havolalari `GET /auth/terms` dan), AS sahifasi `auth/api/login_page.py`; test: `tests/unit/test_otp_units.py::test_login_page_has_google_and_code_entry_points_uz_ru`, `e2e/login.spec.ts`, `e2e/signup.spec.ts`. "Ma'lumotlarimni yuklab olish" — B6 (`/billing/export-my-data`) |
| B1-SCR-BO-05 | ✅ | BO-05 — Narxlar va chegirma qoidalarini boshqarish | 07; 27/30 | B1 qismi: `pages/catalog/src/pages/prices/` (barcha sahifalardagi qoralamalar, doira almashtirishda tasdiq); test: `prices/model/*.test.ts`, `e2e/prices.spec.ts`. Katta o'zgarish tasdig'i (US-M09-02) — B6; Tannarx/Ustama — B2 |
| B1-SCR-BO-11 | ✅ | BO-11 — Foydalanuvchilar, huquqlar va sessiyalar | 07; 27/30 | `pages/settings/src/pages/users/` (xodimlar — `invited` holati, rollar — ruxsatlar uz/ru i18n, sessiyalar); test: `users/model/model.test.ts`, `shared/i18n/src/permissions.test.ts`, `e2e/staff.spec.ts` |
| B1-SCR-BO-12 | ✅ | BO-12 — Filiallar boshqaruvi | 07; 27/30 | B1 qismi: `pages/settings/src/pages/branches/`; test: `branches/model/model.test.ts`, `e2e/branches.spec.ts`. Konsolidatsiya (US-M14-01) — B4; karta terminallari — B3/B5 |
| B1-SCR-BO-14 | ✅ | BO-14 — Tenant/do'kon sozlamalari | 07; 27/30 | B1 qismi: `pages/settings/src/pages/tenant/` (yuridik shakl, siyosatlar, soliq rejimi, AI rozilik; yashirin tabdagi xato → tabga o'tish + banner); test: `tenant/model/model.test.ts`, `e2e/store-settings.spec.ts`. Integratsiya kalitlari (20 #40d/e) — B5 |
| B1-SCR-BO-18 | ✅ | BO-18 — Yorliq va shtrix-kod chop etish | 07; 27/30 | B1 qismi — ichki shtrix-kod yaratish: `pages/catalog/src/pages/products/ui/editor/Barcodes.tsx`; test: `e2e/catalog.spec.ts` (QT-M09-05/08), `test_catalog_products.py::test_qt_m09_05_internal_barcode_generation`. Yorliq navbati/chop — B6 (US-M09-04), tarozi PLU — B3 (US-M09-06) |
| B1-SCR-BO-21 | ✅ | BO-21 — Ro'yxatdan o'tish va birinchi sozlash (onboarding wizard) | 07; 27/30 | `pages/billing/src/pages/onboarding/` (①② ro'yxatdan o'tish, ③a Excel/qo'lda, ⑤, ⑥ `<InstallGuide embedded/>`); test: `e2e/signup.spec.ts`, `onboarding` model testlari. ③b — B2, ④ — B4, ③ foto (AI-03) — B6 |
| B1-SCR-UX-INSTALL | ✅ | UX-INSTALL — Qurilmani o'rnatish yo'riqnomasi (41 ta biznes ekranga kirmaydi, yordamchi rout… | 07; 27/30 | B1-T03 ga qarang; analitika `install_guide_viewed`/`pwa_installed`, PWA precache `apps/shell/vite.config.ts`; test: `e2e/install.spec.ts` |

### Bosqich 1 — Jadvallar / migratsiyalar (12)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B1-TBL-platform.terms_versions | ✅ | `platform.terms_versions` (revizion 0007) | 12; 27 B1: Foydalanish shartlari aksepti | DDL 0007; kod va test: `backend/tests/support/auth_signup.py`, `backend/tests/support/branches.py` |
| B1-TBL-auth.user_credentials | ✅ | `auth.user_credentials` (revizion 0003) | 12; 30 (US jadvallari) | DDL 0003; kod va test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_update.py` |
| B1-TBL-auth.otp_challenges | ✅ | `auth.otp_challenges` (revizion 0003) | 12; 30 (US jadvallari) | DDL 0003; kod va test: `backend/tests/integration/test_admin_users_credentials.py`, `backend/tests/integration/test_admin_users_invite.py` |
| B1-TBL-auth.sessions | ✅ | `auth.sessions` (revizion 0003) | 12; 30 (US jadvallari) | DDL 0003; kod va test: `backend/tests/integration/test_admin_users_sessions.py`, `backend/tests/integration/test_admin_users_update.py` |
| B1-TBL-app.tenants | ✅ | `app.tenants` (revizion 0002) | 12; 27 vazifa matni | DDL 0002; kod va test: `backend/tests/integration/test_migrations.py`, `backend/tests/integration/test_rls.py` |
| B1-TBL-app.users | ✅ | `app.users` (revizion 0002) | 12; 30 (US jadvallari) | DDL 0002; kod va test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_otp_flow.py` |
| B1-TBL-app.user_identities | ✅ | `app.user_identities` (revizion 0003) | 12; 27 vazifa matni | DDL 0003; kod va test: `backend/tests/integration/test_google_login.py` |
| B1-TBL-app.branches | ✅ | `app.branches` (revizion 0002) | 12; 27 vazifa matni | DDL 0002; kod va test: `backend/tests/integration/test_branches_api.py`, `backend/tests/integration/test_pricing_current_price.py` |
| B1-TBL-app.branch_tax_settings | ✅ | `app.branch_tax_settings` (revizion 0002) | 12; 30 (US jadvallari) | DDL 0002; kod va test: `backend/tests/integration/test_signup_flow.py` |
| B1-TBL-app.warehouses | ✅ | `app.warehouses` (revizion 0002) | 12; 30 (US jadvallari) | DDL 0002; kod va test: `backend/tests/integration/test_catalog_products.py`, `backend/tests/integration/test_seed_and_worker.py` |
| B1-TBL-app.cash_registers | ✅ | `app.cash_registers` (revizion 0002) | 12; 30 (US jadvallari) | DDL 0002; kod va test: `backend/tests/integration/test_admin_users_sessions.py`, `backend/tests/integration/test_signup_flow.py` |
| B1-TBL-app.memberships | ✅ | `app.memberships` (revizion 0002) | 12; 30 (US jadvallari) | DDL 0002; kod va test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_update.py` |
| B1-TBL-app.roles | ✅ | `app.roles` (revizion 0002) | 12; 30 (US jadvallari) | DDL 0002; kod va test: `backend/tests/integration/test_admin_users_update.py`, `backend/tests/integration/test_seed_and_worker.py` |
| B1-TBL-app.role_permissions | ✅ | `app.role_permissions` (revizion 0002) | 12; 30 (US jadvallari) | DDL 0002; kod va test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_update.py` |
| B1-TBL-app.subscriptions | ✅ | `app.subscriptions` (revizion 0007) | 12; 30 (US jadvallari) | DDL 0007; kod va test: `backend/tests/integration/test_auth_gate_fixes.py`, `backend/tests/integration/test_auth_revocation_and_switch.py` |
| B1-TBL-app.tenant_tax_regimes | ✅ | `app.tenant_tax_regimes` (revizion 0007) | 12; 27 B1: do'kon sozlamalari (soliq rejimi) | DDL 0007; kod `branches/infrastructure/tenant.py`; test `test_tenant_settings_api.py::test_tax_regime_from_next_month_only` (API orqali) |
| B1-TBL-app.consents | ✅ | `app.consents` (revizion 0007) | 12; US-M17-01 — `POST /tenant/consents` (qaror #61) | DDL 0007; kod va test: `backend/tests/integration/test_signup_flow.py`, `backend/tests/integration/test_tenant_settings_api.py` |
| B1-TBL-app.product_categories | ✅ | `app.product_categories` (revizion 0008) | 12; 27 B1: M09 katalog | DDL 0008; kod va test: `backend/tests/integration/test_import_jobs.py` |
| B1-TBL-app.products | ✅ | `app.products` (revizion 0008) | 12; 27 B1: M09 tovarlar | DDL 0008; kod va test: `backend/tests/integration/test_catalog_products.py`, `backend/tests/integration/test_import_jobs.py` |
| B1-TBL-app.product_barcodes | ✅ | `app.product_barcodes` (revizion 0008) | 12; 30 (US jadvallari) | DDL 0008; kod va test: `backend/tests/integration/test_catalog_products.py`, `backend/tests/integration/test_import_jobs.py` |
| B1-TBL-app.product_prices | ✅ | `app.product_prices` (revizion 0008) | 12; 30 (US jadvallari) | DDL 0008; kod va test: `backend/tests/integration/test_import_jobs.py`, `backend/tests/integration/test_pricing_current_price.py` |
| B1-TBL-app.internal_barcode_seq | ✅ | `app.internal_barcode_seq` (revizion 0008) | 12; 30 (US jadvallari) | DDL 0008; kod `catalog/infrastructure/repositories.py` (`lock_internal_seq`/`set_internal_seq`); test `test_catalog_products.py::test_qt_m09_05_internal_barcode_generation` (band qiymatni o'tkazib yuboradi) |
| B1-TBL-app.price_changes | ✅ | `app.price_changes` (revizion 0017) | 12; 30 (US jadvallari) | DDL 0017; kod va test: `backend/tests/integration/test_import_jobs.py`, `backend/tests/integration/test_pricing_price_changes.py` |
| B1-TBL-app.price_change_lines | ✅ | `app.price_change_lines` (revizion 0017) | 12; 30 (US jadvallari) | DDL 0017; kod `pricing/infrastructure/repositories.py`; test `test_pricing_price_changes.py::test_qt_m09_01_manager_updates_price_old_one_goes_to_history` (`lines[0].old_price/new_price`) |
| B1-TBL-app.import_jobs | ✅ | `app.import_jobs` (revizion 0022) | 12; 27 vazifa matni | DDL 0022; kod `imports/infrastructure/repositories.py`; test `test_import_jobs.py::test_us_m04_04_csv_upload_validate_commit`, `::test_all_rows_invalid_fails_and_job_requires_tenant` |
| B1-TBL-app.doc_sequences | ✅ | `app.doc_sequences` (revizion 0019) | 12; 30 (US jadvallari) | DDL 0019; kod `core/doc_numbers.py` (`app.next_doc_number`, birinchi hujjatda yaratiladi — 12 §5.2, 14 §20); test `test_pricing_price_changes.py::test_qt_m09_01_*` (`C-01-2026-000001` → `…000002`), `test_import_jobs.py::test_us_m04_04_*` |

### Bosqich 1 — Qabul testlari (31)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B1-QT-M09-01 | ✅ | QT-M09-01 (happy) — Berilgan tovar joriy narxi "12000.00", qachonki Menejer yangi narx "13000.00" kiritsa (valid_from bilan), unda eski narx tarix yozuviga ko'chadi, yan… | 31; 31 US (US-M09-01) | test: `backend/tests/integration/test_pricing_price_changes.py` :: `test_qt_m09_01_manager_updates_price_old_one_goes_to_history` |
| B1-QT-M09-05 | ✅ | QT-M09-05 (happy) — Berilgan tovar shtrix-kodsiz, qachonki "Ichki shtrix-kod yaratish" bosilsa, unda tenant ichida noyob 13 raqamli EAN-13 kod yaratiladi: 04 bilan boshl… | 31; 31 US (US-M09-05) | test: `backend/tests/integration/test_catalog_products.py` :: `test_qt_m09_05_internal_barcode_generation` |
| B1-QT-M09-08 | ✅ | QT-M09-08 (negative (shtrix-kod takrori)) — Berilgan shtrix-kod "4780000000012" "Coca-Cola 1.5L"da bor, qachonki shu kod "Mol go'shti (kg)"ga ham berilmoqchi bo'lsa, und… | 31; 31 US (US-M09-01) | test: `backend/tests/integration/test_catalog_products.py` :: `test_qt_m09_08_barcode_duplicate_within_tenant` |
| B1-QT-M09-09 | ✅ | QT-M09-09 (negative (aksiya muddati)) — Berilgan aksiya narxi valid_to="2026-10-14" bilan tugagan, qachonki 2026-10-15'da sotuv qilinsa, unda aksiya avtomatik tugaydi, c… | 31; 31 US (US-M09-01) | test: `backend/tests/unit/test_pricing_resolution.py` :: `test_qt_m09_09_promo_price_ends_automatically` |
| B1-QT-M13-01 | ✅ | QT-M13-01 (happy) — Berilgan yangi xodim ma'lumoti kiritilgan, qachonki Egasi "Kassir" rolini belgilasa, unda xodim shu rolga mos role_permissions ruxsatlarini oladi. | 31; 31 US (US-M13-01) | test: `backend/tests/integration/test_access_roles.py` :: `test_qt_m13_01_role_grants_its_permissions` |
| B1-QT-M13-02 | ✅ | QT-M13-02 (happy) — Berilgan xodimga "Kassir" va "Omborchi" ikkala rol berilgan, qachonki u login qilsa, unda ikki rolning jamlangan huquqlariga ega bo'ladi (yuqori huqu… | 31; 31 US (US-M13-02) | test: `backend/tests/integration/test_access_roles.py` :: `test_qt_m13_02_two_roles_union_and_most_generous_limit` |
| B1-QT-M13-03 | ✅ | QT-M13-03 (happy) — Berilgan Egasi discount.give.limit_valueni (settings.users — 15-xavfsizlik-va-audit.md §2.2, 20-api-moliya-admin.md #28 PUT /roles/{id}/permissions)… | 31; 31 US (US-M13-03) | test: `backend/tests/integration/test_access_roles.py` :: `test_qt_m13_03_limit_change_takes_effect_immediately` |
| B1-QT-M13-04 | ✅ | QT-M13-04 (happy) — Berilgan Egasi yangi xodim qo'shadi (telefon, ism, rol, filial), qachonki saqlansa, unda bir martalik taklif kodi (OTP, purpose=invite) Telegram (bir… | 31; 31 US (US-M13-04) | test: `backend/tests/integration/test_admin_users_invite.py` :: `test_qt_m13_04_invite_sends_one_time_code_never_a_secret` |
| B1-QT-M13-05 | ✅ | QT-M13-05 (happy) — Berilgan xodim ro'yxatda tanlangan, qachonki Egasi "Bloklash"ni bossa, unda xodimning barcha faol sessiyalari darhol bekor qilinadi (QT-OAUTH-07), u… | 31; 31 US (US-M13-05) | test: `backend/tests/integration/test_admin_users_update.py` :: `test_qt_m13_05_block_revokes_now_and_unblock_restores_login` |
| B1-QT-M13-06 | ✅ | QT-M13-06 (happy) — Berilgan xodim parolini unutgan, qachonki Egasi "Parolni tiklash" bossa, unda eski parol/PIN bekor qilinadi, barcha sessiyalar tugatiladi, bir martal… | 31; 31 US (US-M13-06) | test: `backend/tests/integration/test_admin_users_credentials.py` :: `test_qt_m13_06_reset_password_kills_sessions_and_sends_admin_reset_code` |
| B1-QT-M13-07 | ✅ | QT-M13-07 (happy) — Berilgan xodimning 2 faol sessiyasi bor, qachonki Egasi bittasini "Bekor qilish" bossa, unda shu sessiyaning tokeni darhol bekor qilinadi, ikkinchisi… | 31; 31 US (US-M13-07) | test: `backend/tests/integration/test_admin_users_sessions.py` :: `test_qt_m13_07_revoking_one_session_leaves_the_other` |
| B1-QT-M13-09 | ✅ | QT-M13-09 (negative) — Berilgan Egasi o'zining yagona hisobini bloklashga urinmoqda, unda tizim rad etadi (tenant egasiz qolib ketmasin); faqat platforma admin orqali ti… | 31; 31 US (US-M13-03) | test: `backend/tests/integration/test_admin_users_update.py` :: `test_qt_m13_09_owner_cannot_block_himself_or_drop_the_owner_role` |
| B1-QT-M14-02 | ✅ | QT-M14-02 (happy) — Berilgan biznes yangi do'kon ochyapti, qachonki Egasi yangi filialni (nom, manzil; kassa(lar) — POST /cash-registers bilan, tarif limiti/ADDON_REQUIR… | 31; 31 US (US-M14-03) | test: `backend/tests/integration/test_branches_api.py` :: `test_qt_m14_02_new_branch_is_its_own_warehouse_and_cash_unit` |
| B1-QT-M14-03 | ✅ | QT-M14-03 (happy) — Berilgan yangi filial yaratilmoqda, qachonki Egasi "aholi punkti toifasi"ni "Boshqa aholi punkti" deb tanlasa, unda aylanma solig'i stavkasi 2% qo'll… | 31; 31 US (US-M14-04) | test: `backend/tests/integration/test_branches_api.py` :: `test_qt_m14_03_other_settlement_category_rate_2pct` |
| B1-QT-M14-04 | ✅ | QT-M14-04 (negative) — Berilgan toifa tanlanmagan, qachonki filial saqlansa, unda standart qiymat "Shahar, 100 ming+" (4%, eng ehtiyotkor) qo'yiladi va Egasiga tekshiris… | 31; 31 US (US-M14-04) | test: `backend/tests/integration/test_branches_api.py` :: `test_qt_m14_04_no_category_defaults_to_city_4pct` |
| B1-QT-M14-05 | ✅ | QT-M14-05 (unit (tarix)) — Berilgan filial toifasi "other"dan "city_100k_plus"ga valid_from="2026-11-01" bilan o'zgartirilgan, qachonki 2026-10 oyi uchun aylanma solig'i… | 31; 31 US (US-M14-04) | test: `backend/tests/integration/test_branches_api.py` :: `test_qt_m14_05_future_category_change_keeps_old_rate_for_current_month` |
| B1-QT-M17-01 | ✅ | QT-M17-01 (happy) — Berilgan yangi foydalanuvchi telefon+parol bilan ro'yxatdan o'tmoqda, Telegram ulanmagan, qachonki OTP so'ralsa, unda SMS zaxira orqali 6 xonali kod… | 31; 31 US (US-M17-01) | test: `backend/tests/integration/test_otp_flow.py` |
| B1-QT-M17-02 | ✅ | QT-M17-02 (happy (Google)) — Berilgan foydalanuvchi "Google bilan kirish"ni tanlaydi, qachonki OIDC oqimi muvaffaqiyatli yakunlansa, unda user_identities yozuvi yaratila… | 31; 31 US (US-M17-01) | test: `backend/tests/integration/test_google_login.py` :: `test_qt_m17_02_new_google_account_signs_up_without_password_then_logs_in` |
| B1-QT-M17-06 | ✅ | QT-M17-06 (negative (OTP kanal)) — Berilgan foydalanuvchi telefon raqami hali Telegram botga ulanmagan, SMS provayder (Eskiz) ham vaqtincha ishlamayapti, qachonki OTP so… | 31; 31 US (US-M17-01) | test: `backend/tests/integration/test_otp_flow.py` :: `test_qt_m17_06_no_channel_delivers_503` |
| B1-QT-M17-08 | ✅ | QT-M17-08 (negative (Foydalanish shartlari)) — Berilgan ro'yxatdan o'tish formasi, qachonki Foydalanish shartlari belgilanmasdan yuborilsa, unda 422 VALIDATION_ERROR, te… | 31; 31 US (US-M17-01) | test: `backend/tests/integration/test_signup_flow.py` :: `test_qt_m17_08_terms_required_current_and_consent_recorded` |
| B1-QT-NFR-SIGNUP-01 | ✅ | QT-NFR-SIGNUP-01 (e2e (performance)) — Berilgan yangi foydalanuvchi (US-M17-01), qachonki telefon + OTP + do'kon nomi + Foydalanish shartlari bilan ro'yxatdan o'tsa, und… | 31; 27 (aniq havola) | test: `backend/tests/integration/test_import_jobs.py` :: `test_qt_nfr_signup_01_catalog_import_500_products_xlsx` |

## Bosqich 2: ombor va hujjat o'tkazish yadrosi

**Maqsad (27):** Hujjat postingi (kirim, ko'chirish, inventarizatsiya, hisobdan chiqarish) to'g'ri qoldiq va provodka hosil qiladi.

Holat: ✅ 4 · 🟡 22 · ⬜ 111 · ⛔ 0 · ⏭ 0 · jami 137

### Bosqich 2 — Vazifalar (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B2-T01 | ⬜ | Posting xizmati: hujjat → `stock_moves`, `stock_lots`, `ledger_entries`, `vat_moves` bitta tranzaksiyada; teskari hujjat (`13-provodka-qoidalari.md` §2) | 27 |  |
| B2-T02 | ⬜ | M07 kirim (naqd va nasiyaga), yetkazib beruvchilar | 27 |  |
| B2-T03 | ⬜ | M04 qoldiq, FIFO/AVECO (US-M04-05), qayta hisoblash ishi | 27 |  |
| B2-T04 | ⬜ | M06 ko'chirish, M05 inventarizatsiya (US-M05-01…03) — `expected` formulasi `count_lines.counted_at` bilan (qaror #53); ortiqcha `Kt 9390`, kamomad 5910/4730 (26 #35); ombor hisobi `warehouses.inventory_account` (2910/2920); offline `transfer.*` / `stock_count…` | 27 |  |
| B2-T05 | ⬜ | Ko'chirish `post` — `ettn_documents` qoralamasi ("Ombordan omborga", `transfers.transport_mode`) yaratiladi (qaror #63); `FakeEInvoiceAdapter` e-TTN ni darhol `registered` qiladi (staging/test); real yuborish va E-IMZO — Bosqich 5 | 27 |  |
| B2-T06 | ⬜ | US-M07-05 yetkazib beruvchiga qaytarish | 27 |  |
| B2-T07 | ⬜ | US-M04-06 hisobdan chiqarish + yaroqlilik muddati maydoni; faqat online (qaror #54) | 27 |  |
| B2-T08 | ⬜ | `stock_openings` importi/kiritish (US-M04-04 qoldiq qismi, `Dt inv_acct / Kt 0000`; kontr-hisob `0000` — 26 #36) | 27 |  |
| B2-T09 | ⬜ | `stock_lots.blocked_qty` (qaytgan muddati o'tgan tovar, `13` §2.5); AVECO `avg_costs.total_value`, manfiy qoldiq `pending` tannarxi, FIFO↔AVECO almashtirish (`13` §3) | 27 |  |
| B2-T10 | ⬜ | Bildirishnoma voqealari `outbox_jobs(kind='telegram')` ga yoziladi (yuborish — Bosqich 4) | 27 |  |
| B2-T11 | ⬜ | BO-03 "Ko'chirishlar" tabi (US-M06-03) | 27 |  |

### Bosqich 2 — Tayyor ta'rifi (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B2-DoD-01 | ⬜ | `13` §2.6–§2.12, §2.20, §2.21, §3 (FIFO/AVECO), X-02 misollari avtomatik testlarda | 27 Tayyor ta'rifi |  |
| B2-DoD-02 | ⬜ | posting o'zgarsa raqamli testlar yangilangan. | 27 Tayyor ta'rifi |  |

### Bosqich 2 — Hikoyalar (27 → 30)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B2-US-M04-01 | ⬜ | US-M04-01 — Kirimda balans avto yangilanish | 27 Hikoyalar; 30 (Must) |  |
| B2-US-M04-05 | ⬜ | US-M04-05 — Tannarx usulini (FIFO/AVECO) tanlash | 27 Hikoyalar; 30 (Must) |  |
| B2-US-M04-06 | ⬜ | US-M04-06 — Yaroqlilik muddati ogohlantirish + hisobdan chiqarish | 27 Hikoyalar; 30 (Should) |  |
| B2-US-M05-01 | ⬜ | US-M05-01 — Sanash varag'i / haqiqiy son kiritish | 27 Hikoyalar; 30 (Must) |  |
| B2-US-M05-02 | ⬜ | US-M05-02 — Farqni (ortiqcha/kamomad) tasdiqlash | 27 Hikoyalar; 30 (Must) |  |
| B2-US-M05-03 | ⬜ | US-M05-03 — Kamomad/ortiqchani buxgalteriya yozuviga aks ettirish | 27 Hikoyalar; 30 (Must) |  |
| B2-US-M06-01 | ⬜ | US-M06-01 — Ko'chirish hujjatini yaratish (yuborish) | 27 Hikoyalar; 30 (Must) |  |
| B2-US-M06-02 | ⬜ | US-M06-02 — Kelgan tovarni tasdiqlab qabul qilish | 27 Hikoyalar; 30 (Must) |  |
| B2-US-M06-03 | ⬜ | US-M06-03 — Ko'chirishlar tarixi va bajarilish vaqti | 27 Hikoyalar; 30 (Should) |  |
| B2-US-M07-01 | ⬜ | US-M07-01 — Yetkazib beruvchiga xaridnoma yaratish | 27 Hikoyalar; 30 (Must) |  |
| B2-US-M07-02 | ⬜ | US-M07-02 — Kelgan tovarni xaridnoma bilan solishtirib qabul qilish | 27 Hikoyalar; 30 (Must) |  |
| B2-US-M07-05 | ⬜ | US-M07-05 — Yetkazib beruvchiga tovar qaytarish | 27 Hikoyalar; 30 (Should) |  |
| B2-US-M11-01 | ⬜ | US-M11-01 — Har bir sotuv/xariddan avtomatik provodka | 27 Hikoyalar; 30 (Must) |  |
| B2-US-M04-04 | ⬜ | US-M04-04 — Boshlang'ich katalog/qoldiq kiritish (qo'lda/import/AI-03) | 27 Hikoyalar; 30 (Must) |  |

### Bosqich 2 — Endpointlar (14/17/18/19/20/33)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B2-EP-18#17 | ⬜ | POST /api/v1/counterparties / GET / GET /{id} / PATCH /{id} | 18 §11.2–11.4; kontragentlar CRUD — 27 B2 (yetkazib beruvchilar); mijoz qismi — B4 |  |
| B2-EP-19#26 | ⬜ | GET /stock-balances | 19 §7; qoldiq registri — 27 B2 (US-M04-01); `low_stock` filtri — B4 |  |
| B2-EP-19#27 | ⬜ | GET /stock-lots | 19 §7; ombor registrlari — 27 B2 |  |
| B2-EP-19#28 | ⬜ | GET /stock-moves | 19 §7; ombor registrlari — 27 B2 |  |
| B2-EP-19#29 | ⬜ | POST /goods-receipts | 19 §8; 30 (US API) |  |
| B2-EP-19#31 | ⬜ | GET /goods-receipts · GET /goods-receipts/{id} · PATCH /goods-receipts/{id} | 19 §8; 30 (US API) |  |
| B2-EP-19#32 | ⬜ | POST /goods-receipts/{id}/post | 19 §8; 30 (US API) |  |
| B2-EP-19#33 | ⬜ | POST /goods-receipts/{id}/cancel | 19 §8; 30 (resurs) |  |
| B2-EP-19#39 | ⬜ | GET /counterparties?is_supplier=true&search=&archived=&cursor=&limit= | 19 §9; 27 B2: yetkazib beruvchilar (M07) |  |
| B2-EP-19#40 | ⬜ | POST /counterparties (is_supplier=true) | 19 §9; 27 B2: yetkazib beruvchilar (M07) |  |
| B2-EP-19#41 | ⬜ | GET/PATCH /counterparties/{id} | 19 §9; 27 B2: yetkazib beruvchilar (M07) |  |
| B2-EP-19#42 | ⬜ | POST /counterparties/{id}/archive | 19 §9; 27 B2: yetkazib beruvchilar (M07) |  |
| B2-EP-19#43 | ⬜ | GET /counterparties/{id}/debt-balance | 19 §9; 27 B2: yetkazib beruvchilar (M07) |  |
| B2-EP-19#44 | ⬜ | POST /counterparties/lookup-by-stir | 19 §9; 27 B2: yetkazib beruvchilar (STIR qidiruv) |  |
| B2-EP-19#45 | ⬜ | POST /purchase-orders | 19 §10; 30 (US API) |  |
| B2-EP-19#46 | ⬜ | POST /purchase-orders/{id}/send | 19 §10; 30 (US API) |  |
| B2-EP-19#47 | ⬜ | GET /purchase-orders · GET /purchase-orders/{id} | 19 §10; 30 (US API) |  |
| B2-EP-19#48 | ⬜ | PATCH /purchase-orders/{id} | 19 §10; 30 (resurs) |  |
| B2-EP-19#49 | ⬜ | POST /purchase-orders/{id}/cancel | 19 §10; 30 (resurs) |  |
| B2-EP-19#52 | ⬜ | POST /supplier-returns | 19 §12; 30 (US API) |  |
| B2-EP-19#53 | ⬜ | POST /supplier-returns/{id}/post | 19 §12; 30 (US API) |  |
| B2-EP-19#54 | ⬜ | POST /supplier-returns/{id}/cancel | 19 §12; 30 (resurs) |  |
| B2-EP-19#55 | ⬜ | POST /transfers | 19 §13; 30 (US API) |  |
| B2-EP-19#56 | ⬜ | POST /transfers/{id}/post | 19 §13; 30 (US API) |  |
| B2-EP-19#57 | ⬜ | POST /transfers/{id}/send | 19 §13; 30 (resurs) |  |
| B2-EP-19#58 | ⬜ | POST /transfers/{id}/receive | 19 §13; 30 (US API) |  |
| B2-EP-19#59 | ⬜ | GET /transfers · GET /transfers/{id} | 19 §13; 30 (US API) |  |
| B2-EP-19#60 | ⬜ | POST /transfers/{id}/cancel | 19 §13; 30 (resurs) |  |
| B2-EP-19#61 | ⬜ | POST /stock-counts | 19 §14; 30 (US API) |  |
| B2-EP-19#62 | ⬜ | POST /stock-counts/{id}/lines (skaner kiritish) | 19 §14; 30 (US API) |  |
| B2-EP-19#63 | ⬜ | PATCH /stock-counts/{id}/lines/{line_id} | 19 §14; 30 (resurs) |  |
| B2-EP-19#64 | ⬜ | POST /stock-counts/{id}/submit-for-review | 19 §14; 30 (US API) |  |
| B2-EP-19#65 | ⬜ | POST /stock-counts/{id}/post | 19 §14; 30 (US API) |  |
| B2-EP-19#66 | ⬜ | POST /stock-counts/{id}/cancel | 19 §14; 30 (resurs) |  |
| B2-EP-19#67 | ⬜ | GET /stock-counts · GET /stock-counts/{id} | 19 §14; 30 (US API) |  |
| B2-EP-19#68 | ⬜ | POST /write-offs | 19 §15; 30 (US API) |  |
| B2-EP-19#69 | ⬜ | POST /write-offs/{id}/post | 19 §15; 30 (US API) |  |
| B2-EP-19#70 | ⬜ | POST /write-offs/{id}/cancel | 19 §15; 30 (resurs) |  |
| B2-EP-19#71 | ⬜ | POST /stock-openings | 19 §16; 27 B2: `stock_openings` (US-M04-04 qoldiq qismi) |  |
| B2-EP-19#72 | ⬜ | POST /stock-openings/{id}/post | 19 §16; 27 B2: `stock_openings` |  |
| B2-EP-19#73 | ⬜ | POST /stock-openings/{id}/cancel | 19 §16; 27 B2: `stock_openings` |  |
| B2-EP-19#74 | ⬜ | GET /valuation-settings | 19 §17; 30 (US API) |  |
| B2-EP-19#75 | ⬜ | PATCH /valuation-settings | 19 §17; 30 (US API) |  |
| B2-EP-19#78 | ⬜ | GET /recost-jobs | 19 §18; 27 B2: qayta hisoblash ishi |  |
| B2-EP-19#79 | ⬜ | GET /recost-jobs/{id} | 19 §18; 27 B2: qayta hisoblash ishi |  |
| B2-EP-19#80 | ⬜ | POST /recost-jobs/{id}/retry | 19 §18; 27 B2: qayta hisoblash ishi |  |
| B2-EP-20#9 | ⬜ | GET /ledger-entries — Buxgalteriya jurnali | 20 indeks; 30 (US API) |  |

### Bosqich 2 — Ekranlar (06/07)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B2-SCR-BO-03 | ⬜ | BO-03 — Ombor qoldig'i (+ Ko'chirishlar tab) | 07; 27/30 |  |
| B2-SCR-BO-04 | ⬜ | BO-04 — Xaridnoma yaratish, yetkazib beruvchiga to'lov/qaytarish | 07; 27/30 |  |
| B2-SCR-BO-08 | ⬜ | BO-08 — Buxgalteriya jurnali, provodkalar | 07; 27/30 |  |
| B2-SCR-BO-14 | ⬜ | BO-14 — Tenant/do'kon sozlamalari | 07; 27/30 |  |
| B2-SCR-BO-21 | ⬜ | BO-21 — Ro'yxatdan o'tish va birinchi sozlash (onboarding wizard) | 07; 27/30 |  |
| B2-SCR-POS-08 | ⬜ | POS-08 — Yetkazib beruvchidan tovar qabul qilish (kirim) | 07; 27/30 |  |
| B2-SCR-POS-09 | ⬜ | POS-09 — Omborlar orasida tovar ko'chirish | 07; 27/30 |  |
| B2-SCR-POS-10 | ⬜ | POS-10 — Inventarizatsiya (jismoniy sanash) | 07; 27/30 |  |

### Bosqich 2 — Jadvallar / migratsiyalar (12)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B2-TBL-app.valuation_method_history | ✅ | `app.valuation_method_history` (revizion 0005) | 12; 30 (US jadvallari) | DDL 0005; kod va test: `backend/tests/integration/test_signup_flow.py` |
| B2-TBL-app.counterparties | 🟡 | `app.counterparties` (revizion 0006) | 12; 27 B2: yetkazib beruvchilar (M07); mijozlar — B4 | DDL 0006 bor; modul kodi/testi yo'q |
| B2-TBL-app.purchase_orders | 🟡 | `app.purchase_orders` (revizion 0013) | 12; 30 (US jadvallari) | DDL 0013 bor; modul kodi/testi yo'q |
| B2-TBL-app.po_lines | 🟡 | `app.po_lines` (revizion 0013) | 12; 30 (US jadvallari) | DDL 0013 bor; modul kodi/testi yo'q |
| B2-TBL-app.goods_receipts | 🟡 | `app.goods_receipts` (revizion 0013) | 12; 30 (US jadvallari) | DDL 0013 bor; modul kodi/testi yo'q |
| B2-TBL-app.receipt_lines | 🟡 | `app.receipt_lines` (revizion 0013) | 12; 30 (US jadvallari) | DDL 0013 bor; modul kodi/testi yo'q |
| B2-TBL-app.supplier_returns | 🟡 | `app.supplier_returns` (revizion 0015) | 12; 30 (US jadvallari) | DDL 0015 bor; modul kodi/testi yo'q |
| B2-TBL-app.supplier_return_lines | 🟡 | `app.supplier_return_lines` (revizion 0015) | 12; 30 (US jadvallari) | DDL 0015 bor; modul kodi/testi yo'q |
| B2-TBL-app.transfers | 🟡 | `app.transfers` (revizion 0014) | 12; 27 vazifa matni | DDL 0014 bor; modul kodi/testi yo'q |
| B2-TBL-app.transfer_lines | 🟡 | `app.transfer_lines` (revizion 0014) | 12; 30 (US jadvallari) | DDL 0014 bor; modul kodi/testi yo'q |
| B2-TBL-app.stock_counts | 🟡 | `app.stock_counts` (revizion 0014) | 12; 30 (US jadvallari) | DDL 0014 bor; modul kodi/testi yo'q |
| B2-TBL-app.count_lines | 🟡 | `app.count_lines` (revizion 0014) | 12; 27 vazifa matni | DDL 0014 bor; modul kodi/testi yo'q |
| B2-TBL-app.write_offs | 🟡 | `app.write_offs` (revizion 0014) | 12; 30 (US jadvallari) | DDL 0014 bor; modul kodi/testi yo'q |
| B2-TBL-app.write_off_lines | 🟡 | `app.write_off_lines` (revizion 0014) | 12; 30 (US jadvallari) | DDL 0014 bor; modul kodi/testi yo'q |
| B2-TBL-app.stock_openings | 🟡 | `app.stock_openings` (revizion 0014) | 12; 27 B2: `stock_openings` | DDL 0014 bor; modul kodi/testi yo'q |
| B2-TBL-app.opening_lines | 🟡 | `app.opening_lines` (revizion 0014) | 12; 27 B2: `stock_openings` | DDL 0014 bor; modul kodi/testi yo'q |
| B2-TBL-app.stock_moves | ✅ | `app.stock_moves` (revizion 0015) | 12; 27 vazifa matni | DDL 0015; kod va test: `backend/tests/support/branches.py` |
| B2-TBL-app.stock_lots | 🟡 | `app.stock_lots` (revizion 0015) | 12; 27 vazifa matni | DDL 0015 bor; modul kodi/testi yo'q |
| B2-TBL-app.avg_costs | 🟡 | `app.avg_costs` (revizion 0015) | 12; 27 vazifa matni | DDL 0015 bor; modul kodi/testi yo'q |
| B2-TBL-app.stock_balances | ✅ | `app.stock_balances` (revizion 0015) | 12; 30 (US jadvallari) | DDL 0015; kod va test: `backend/tests/integration/test_catalog_products.py`, `backend/tests/support/branches.py` |
| B2-TBL-app.ledger_entries | 🟡 | `app.ledger_entries` (revizion 0015) | 12; 27 vazifa matni | DDL 0015 bor; modul kodi/testi yo'q |
| B2-TBL-app.vat_moves | 🟡 | `app.vat_moves` (revizion 0015) | 12; 27 vazifa matni | DDL 0015 bor; modul kodi/testi yo'q |
| B2-TBL-app.ettn_documents | 🟡 | `app.ettn_documents` (revizion 0020) | 12; 27 vazifa matni | DDL 0020 bor; modul kodi/testi yo'q |
| B2-TBL-app.outbox_jobs | 🟡 | `app.outbox_jobs` (revizion 0022) | 12; 27 vazifa matni | DDL 0022 bor; ilova kodi bor, test yo'q |
| B2-TBL-app.recost_jobs | 🟡 | `app.recost_jobs` (revizion 0022) | 12; 27 B2: qayta hisoblash ishi | DDL 0022 bor; modul kodi/testi yo'q |

### Bosqich 2 — Qabul testlari (31)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B2-QT-PERM-08 | ✅ | QT-PERM-08 (integration) — Berilgan Kassir faqat "Chilonzor filiali"ga bog'langan (memberships.branch_ids=['Chilonzor']), qachonki X-Branch-Idda boshqa filial ID'si bila… | 31; 31 §1.7 — filial doirasi `stock-balances` (B2) | test: `backend/tests/integration/test_rs_dependencies.py` |
| B2-QT-PERM-09 | ⬜ | QT-PERM-09 (integration) — Berilgan Egasi (memberships.branch_ids=[], bo'sh massiv = barcha filiallar), qachonki istalgan filial ID'si bilan so'rov yuborsa, unda hech qa… | 31; 31 §1.7 — filial doirasi `stock-balances` (B2) |  |
| B2-QT-M04-01 | ⬜ | QT-M04-01 (happy) — Berilgan xaridnoma bo'yicha tovar qabul qilingan, qachonki qabul hujjati post qilinsa, unda stock_balances.qty avtomatik oshadi, yangi stock_lots qat… | 31; 31 US (US-M04-01) |  |
| B2-QT-M04-04 | ⬜ | QT-M04-04 (happy) — Berilgan yangi tenant (go_live_date belgilangan), qachonki Egasi "Boshlang'ich qoldiq" (stock-openings) kiritsa, unda stock_lots/stock_balances boshl… | 31; boshlang'ich qoldiq (`stock-openings`) — 27 B2 |  |
| B2-QT-M04-05 | ⬜ | QT-M04-05 (happy — FIFO) — Berilgan 2 kirim: 100 dona × "8000.0000" so'm, so'ng 50 dona × "9000.0000" so'm, qachonki 120 dona sotilsa, unda FIFO bo'yicha COGS = 100×8000… | 31; 31 US (US-M04-05) |  |
| B2-QT-M04-06 | ⬜ | QT-M04-06 (happy — AVECO) — Berilgan xuddi shu 2 kirim, tenant usuli AVECO, qachonki 120 dona sotilsa, unda kirim 2'dan keyin avg_cost = "8333.3333"; COGS = 120 × 8333.3… | 31; 31 US (US-M04-05) |  |
| B2-QT-M04-07 | ⬜ | QT-M04-07 (happy) — Berilgan partiyada yaroqlilik muddatiga 7 kun qolgan, qachonki kunlik tekshiruv ishga tushsa, unda Egasi/Menejerga ro'yxat (tovar, partiya, qoldiq, m… | 31; 31 US (US-M04-06) |  |
| B2-QT-M04-08 | ⬜ | QT-M04-08 (negative) — Berilgan tovar muddati o'tgan, qachonki Omborchi "Hisobdan chiqarish" hujjatini sabab bilan yaratsa, unda stock_moves(qty=-N), ledger_entries: Dt… | 31; 31 US (US-M04-06) |  |
| B2-QT-M04-09 | ⬜ | QT-M04-09 (unit — qaytarish tannarxi (FIFO)) — Berilgan QT-M04-05'dagi sotuv (lot_allocations: 100×"8000.0000" + 20×"9000.0000"), qachonki mijoz shu chekdagi 5 donani qa… | 31; 31 US (US-M04-05) |  |
| B2-QT-M04-10 | ⬜ | QT-M04-10 (unit — qaytarish tannarxi (AVECO)) — Berilgan QT-M04-06'dagi holat (avg_cost="8333.3333" sotuv paytida), keyinroq yangi kirim bilan avg_cost o'zgargan, qachon… | 31; 31 US (US-M04-05) |  |
| B2-QT-M04-11 | ⬜ | QT-M04-11 (negative (manfiy qoldiq, offline)) — Berilgan ikki qurilma bir-biridan bexabar offline rejimda oxirgi ma'lum qoldiqdagi bitta donani sotadi (stock_balances.qt… | 31; 31 US (US-M04-01) |  |
| B2-QT-M05-01 | ⬜ | QT-M05-01 (happy) — Berilgan inventarizatsiya boshlangan (stock-counts), qachonki Omborchi har tovar bo'yicha haqiqiy sonni kiritsa, unda tizim haqiqiy son bilan tizimda… | 31; 31 US (US-M05-01) |  |
| B2-QT-M05-02 | ⬜ | QT-M05-02 (happy) — Berilgan farq ro'yxati tayyor — "Coca-Cola 1.5L" bo'yicha kamomad 3 dona, qachonki Menejer/Egasi tasdiqlasa (POST /stock-counts/{id}/post), unda stoc… | 31; 31 US (US-M05-02) |  |
| B2-QT-M05-03 | ⬜ | QT-M05-03 (happy) — Berilgan inventarizatsiya tasdiqlangan (kamomad 3 dona), qachonki buxgalteriya yozuvi yaratilsa, unda tannarx bo'yicha Dt 4730 / Kt 2910 (stock_count… | 31; 31 US (US-M05-03) |  |
| B2-QT-M05-04 | ⬜ | QT-M05-04 (negative) — Berilgan inventarizatsiya hali submit qilinmagan (submit-for-review bosqichida), qachonki post chaqirilsa, unda rad etiladi — holat mashinasi ketm… | 31; 31 US (US-M05-03) |  |
| B2-QT-M05-06 | ⬜ | QT-M05-06 (happy (ortiqcha)) — Berilgan inventarizatsiyada "Coca-Cola 1.5L" bo'yicha 2 dona ortiqcha, oxirgi kirim narxi (last_purchase_cost) "8000.0000", qachonki post… | 31; 31 US (US-M05-03) |  |
| B2-QT-M05-07 | ⬜ | QT-M05-07 (unit (expected formulasi)) — Berilgan stock_counts.started_at=T0, count_lines.snapshot_qty=10, T1 da 2 dona sotildi, qachonki qator T2 (> T1) da counted=8 bil… | 31; 31 US (US-M05-02) |  |
| B2-QT-M06-01 | ⬜ | QT-M06-01 (happy) — Berilgan "Asosiy ombor"dan boshqa filialga 10 dona yuborilmoqda, qachonki POST /transfers/{id}/send chaqirilsa, unda ledger_entries: Dt 2970/Kt 2910… | 31; 31 US (US-M06-01) |  |
| B2-QT-M06-02 | ⬜ | QT-M06-02 (happy) — Berilgan tovar manzilga yetib kelgan, qachonki qabul qiluvchi POST /transfers/{id}/receive bilan tasdiqlasa, unda ledger_entries: Dt 2910/Kt 2970, qa… | 31; 31 US (US-M06-02) |  |
| B2-QT-M06-03 | ⬜ | QT-M06-03 (negative) — Berilgan jo'natilgan 10 dona, qabulda haqiqiy 8 dona kelgan, qachonki qabul qiluvchi 8 dona bilan tasdiqlasa, unda farq (2 dona) Dt 5910/Kt 2970 s… | 31; 31 US (US-M06-02) |  |
| B2-QT-M06-05 | ⬜ | QT-M06-05 (negative) — Berilgan ko'chirish uzoq vaqt "yo'lda" holatida (tenant sozlamasidagi muddatdan ortiq), qachonki Menejer ro'yxatni ochsa, unda shu ko'chirish "kec… | 31; 31 US (US-M06-03) |  |
| B2-QT-M06-06 | ⬜ | QT-M06-06 (negative (markirovka, offline)) — Berilgan "Hayot suvi 1.5L" (markirovkalangan) boshqa filialga offline ko'chirilmoqda — bu M02'dagi qaytarish siyosatidan far… | 31; 31 US (US-M06-01) |  |
| B2-QT-M06-07 | ⬜ | QT-M06-07 (happy (e-TTN)) — Berilgan ko'chirish transport_mode='vehicle', vehicle_plate to'ldirilgan, qachonki POST /transfers/{id}/post bajarilsa, unda ettn_documents(t… | 31; 31 US (US-M06-01) |  |
| B2-QT-M06-08 | ⬜ | QT-M06-08 (happy (e-TTN istisnosi)) — Berilgan ko'chirish transport_mode='on_foot_or_public', qachonki post va send bajarilsa, unda ettn_documents yaratilmaydi va jo'nat… | 31; 31 US (US-M06-01) |  |
| B2-QT-M07-01 | ⬜ | QT-M07-01 (happy) — Berilgan kam qolgan tovar aniqlangan, qachonki Menejer POST /purchase-orders orqali xaridnoma yaratsa, unda hujjat draftda yaratiladi; POST /purchase… | 31; 31 US (US-M07-01) |  |
| B2-QT-M07-02 | ⬜ | QT-M07-02 (happy) — Berilgan xaridnomada 50 dona buyurtma qilingan, qachonki Omborchi POST /goods-receipts orqali haqiqiy 48 dona kiritsa, unda farq (2 dona kam) belgila… | 31; 31 US (US-M07-02) |  |
| B2-QT-M07-06 | ⬜ | QT-M07-06 (happy) — Berilgan tovar muddati o'tgan, shu yetkazib beruvchidan kirim qilingan, qachonki Omborchi "Yetkazib beruvchiga qaytarish" hujjatini yaratsa, unda omb… | 31; 31 US (US-M07-05) |  |
| B2-QT-M07-07 | ⬜ | QT-M07-07 (negative) — Berilgan xaridnoma allaqachon status="cancelled", qachonki shu xaridnomaga POST /goods-receipts yaratishga urinilsa, unda 409 PURCHASE_ORDER_CLOSE… | 31; 31 US (US-M07-02) |  |
| B2-QT-M07-08 | ⬜ | QT-M07-08 (negative (bonus tovar)) — Berilgan yetkazib beruvchi "10+1 tekin" bonus bergan, qachonki qabul qilinsa, unda bonus miqdori kirim qatoriga qo'shiladi, partiya… | 31; 31 US (US-M07-02) |  |
| B2-QT-M11-01 | ⬜ | QT-M11-01 (happy) — Berilgan sotuv yakunlangan, qachonki tizim buxgalteriya modulini ishga tushirsa, unda kassa/hisob-kitob/tovar-moddiy zaxira/QQS/daromad hisoblari bo'… | 31; 31 US (US-M11-01) |  |

## Bosqich 3: veb-kassa

**Maqsad (27):** Do'kon internet bor-yo'qligidan qat'i nazar kassada sotish, qaytarish, chegirma va smena yopish ishini to'liq bajara oladi.

Holat: ✅ 7 · 🟡 17 · ⬜ 173 · ⛔ 0 · ⏭ 0 · jami 197

### Bosqich 3 — Vazifalar (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B3-T01 | ⬜ | M01 kassa (onlayn): qidiruv/skaner, chek, to'lov (naqd, karta, aralash, UzQR — yuridik shaxslar uchun 2026-07-01'dan majburiy, PF-246 3-b; Click/Payme/Uzum ixtiyoriy), smena va Z-hisobot; chek `FiscalPort` orqali `ERP_FISCAL_PROVIDER=fake` bilan (real — Bosqi… | 27 |  |
| B3-T02 | ⬜ | Karta rekvizitlari (qaror #64, #71): `sale_payments`/`debt_payments`/`returns` — `card_type`, `card_type_source` (`terminal`/`bin_table`), `card_mask`, `rrn`, `approval_code`, `card_scheme` faqat `card_entry_mode='integrated'` da, terminal natijasidan avtomat… | 27 |  |
| B3-T03 | ⬜ | Karta terminali — port va Fake (qaror #71, `21` §9.4): `CardTerminalPort` kontrakti (Pydantic DTO → TS tiplari, `integrations/card_terminal/`), `FakeCardTerminalAdapter` (deterministik: tasdiq, rad, taymaut → `unknown`, busy), holat mashinasi va `attempt_id`… | 27 |  |
| B3-T04 | ⬜ | Karta terminali — POS UI (`07` POS-03): "Kartani terminalga qo'ying" (summa, bekor qilish, 120 s hisoblagich) → natija (tasdiq/rad/`unknown`); `unknown` — yangi urinish bloklanadi, `get_status`, menejer tasdig'i bilan yopish; tartib karta → fiskal chek → `sal…` | 27 |  |
| B3-T05 | ⬜ | Terminalsiz karta (rekvizitsiz) va zaxira siyosati (`21` §9.2): POS'da karta ma'lumoti so'ralmaydi — faqat "Karta terminalsiz qabul qilindi" tasdig'i; terminal bog'lanmagan kassada (`manual_reason='standalone_terminal'`) har doim ruxsat, tasdiqsiz; faol termi… | 27 |  |
| B3-T06 | ⬜ | Statik UzQR — kassir qo'lda tasdiqlaydi (`qr_type='static'`, faqat online); dinamik UzQR — `UzqrPort` stub (26 #49) | 27 |  |
| B3-T07 | ⬜ | 48 soatlik shkala va blok (qaror #43): 24 soat 🟡, 40 soat 🔴 + M18, 46 soat modal, 48 soat `FISCAL_OFFLINE_48H_BLOCKED` (`ofd_acked_at IS NULL` eng eski chekdan), blok OFD tasdiqlaridan keyin avtomatik yechiladi; `cash_registers.fm_state` → `FISCAL_DEVICE_LOCK…` | 27 |  |
| B3-T08 | ⬜ | Markirovka sotuvda: kod chek qatorida (`items[].marking_codes`), `MARKING_PRECHECK=warn` + lokal takror-kod tekshiruvi (qaror #62) | 27 |  |
| B3-T09 | ⬜ | Chek chop etish — printer matritsasi (`24-frontend-arxitekturasi.md` §6, `25-nofunksional-talablar.md` §7, 26 #139): Chrome/Edge desktop — Web Serial → WebUSB → tizim printeri (avto-aniqlash), cp866, o'zbek kirill bo'lsa raster rejimi, U+02BB → `'`; Android C… | 27 |  |
| B3-T10 | ⬜ | US-M01-07 printer va tarozi sozlamasi (bir martalik, sinov cheki); tarozi EAN-13 prefiksi — `settings.weight_barcode_templates` (22 = gramm, 21 = summa); printer matritsasi va tarozi prefiksi — QT-M01-22 | 27 |  |
| B3-T11 | ⬜ | Bulut printer adapteri (`shared/lib/printer/cloud`) — iOS yo'li uchun majburiy, Chromium'da ixtiyoriy zahira; iOS o'rnatish ko'rsatmasi (Safari → "Bosh ekranga qo'shish") POS-01/onboarding ekraniga | 27 |  |
| B3-T12 | ⬜ | M16 kassa pul harakati, smena oxirida naqdni sanash | 27 |  |
| B3-T13 | ⬜ | M02 qaytarish; M03 chegirma (limit + PIN tasdiq) | 27 |  |
| B3-T14 | ⬜ | Offline: Dexie keshi, outbox, `/sync/push`/`/sync/pull` (`16-offline-sync.md`) | 27 |  |
| B3-T15 | ⬜ | BO-16 masofaviy tasdiq navbati (M02/M03/M08/M16 turlari) — `approval_requests` va `doc_approvals` (`12` §2.5a); `GET /approval-requests?status=pending`, `POST /approval-requests/{id}/approve/reject` | 27 |  |
| B3-T16 | ⬜ | BO-11 "Qurilmalar" tabi — `GET /devices`, `POST /devices/{id}/revoke` (`devices.revoke`, qaror #56 a); `sale.draft_voided`, qayta chop etish auditi | 27 |  |
| B3-T17 | ⬜ | Qurilmaga bog'langan login (`14-autentifikatsiya-oauth2.md` §7): veb-kassa qurilmasini ro'yxatdan o'tkazish, `auth.authorization_codes.device_id` (+ `auth_issue_code`/`auth_consume_code` imzosi, append-only migratsiya), `refresh_tokens.device_id`, sirpanuvchi… | 27 |  |
| B3-T18 | ⬜ | Bildirishnoma voqealari `outbox_jobs(kind='telegram')` ga yoziladi (yuborish — Bosqich 4) | 27 |  |

### Bosqich 3 — Tayyor ta'rifi (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B3-DoD-01 | ⬜ | internet o'chirilganda 2 soat savdo, keyin barcha cheklar yo'qotishsiz va takrorsiz sinxronlanadi | 27 Tayyor ta'rifi |  |
| B3-DoD-02 | ⬜ | `FakeCardTerminalAdapter` bilan integratsiyalangan karta qabul testlari (tasdiq, rad, taymaut → `unknown` → holat so'rovi, takroriy `attempt_id`, fiskal xato → "chek kutilmoqda" va kassir bekor qilsa `void`, `CARD_AMOUNT_MISMATCH` da avtomatik `void`, qaytari… | 27 Tayyor ta'rifi |  |
| B3-DoD-03 | ⬜ | `16-offline-sync.md`dagi konflikt qoidalari (overselling, narx muzlatish) va 48 soat zinapoyasi (QT-OFFLINE48) test bilan qoplangan | 27 Tayyor ta'rifi |  |
| B3-DoD-04 | ⬜ | offline ko'chirish va inventarizatsiya (QT-M06-04, QT-M05-05) yashil | 27 Tayyor ta'rifi |  |
| B3-DoD-05 | ⬜ | `13` §2.1–§2.5, §2.18, §2.19, §3.2a misollari avtomatik testlarda | 27 Tayyor ta'rifi |  |
| B3-DoD-06 | ⬜ | printer matritsasi va tarozi prefiksi qabul testi (QT-M01-22, 26 #139) o'tkazilgan. | 27 Tayyor ta'rifi |  |

### Bosqich 3 — Hikoyalar (27 → 30)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B3-US-M01-01 | ⬜ | US-M01-01 — Chek yaratish va to'lov qabul qilish | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M01-02 | ⬜ | US-M01-02 — Offline savdo + avtomatik sinxronlanish | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M01-04 | ⬜ | US-M01-04 — Smena ochish va yopish (Z-hisobot) | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M01-05 | ⬜ | US-M01-05 — UzQR to'lov (yuridik shaxs, 2026-07-01'dan majburiy) | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M01-07 | ⬜ | US-M01-07 — Kassada chek printeri va tarozini bir marta sozlash, sinov chek (qaror #60) | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M01-08 | ⬜ | US-M01-08 — Integratsiyalangan karta terminali: summa terminalga, natija avtomatik; terminalsiz karta (rekvizitsiz) zaxirasi siyosat bo'yicha — faqat faol term… | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M02-01 | ⬜ | US-M02-01 — Asl chek bo'yicha qaytarish | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M02-02 | ⬜ | US-M02-02 — Menejer limitdan yuqori qaytarishni tasdiqlash | 27 Hikoyalar; 30 (Should) |  |
| B3-US-M02-03 | ⬜ | US-M02-03 — QQS tuzatish (qaytarishda avtomatik) | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M03-01 | ⬜ | US-M03-01 — Kassir chegirma (limit ichida) | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M09-03 | ⬜ | US-M09-03 — Kassada joriy narxni ko'rish (o'zgartirib bo'lmaydi) | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M09-06 | ⬜ | US-M09-06 — Tarozida tortilgan tovarni bitta skanerlash bilan sotish | 27 Hikoyalar; 30 (Should) |  |
| B3-US-M10-01 | ⬜ | US-M10-01 — Har bir sotuvdan QQS avtomatik hisoblash | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M16-01 | ⬜ | US-M16-01 — Kassaga pul qo'yish/olishni sabab bilan yozish | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M16-02 | ⬜ | US-M16-02 — Smena yopilganda kassadagi pulni sanab kiritish | 27 Hikoyalar; 30 (Must) |  |
| B3-US-M16-03 | ⬜ | US-M16-03 — Har bir smena/kassa bo'yicha naqd pul tarixini ko'rish | 27 Hikoyalar; 30 (Must) |  |

### Bosqich 3 — Endpointlar (14/17/18/19/20/33)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B3-EP-14#21 | ⬜ | POST /auth/pin/verify | 14 §20; Kassir PIN — Bosqich 3 (qurilmaga bog'langan login, 14 §4.3/§7) |  |
| B3-EP-18#1 | ⬜ | event shift.opened | 18 §3.1; 30 (US API) |  |
| B3-EP-18#2 | ⬜ | event shift.closed | 18 §3.2; 30 (US API) |  |
| B3-EP-18#3 | ⬜ | GET /api/v1/shifts | 18 §3.3; 30 (resurs) |  |
| B3-EP-18#4 | ⬜ | GET /api/v1/shifts/{id} | 18 §3.3; 30 (resurs) |  |
| B3-EP-18#5 | ⬜ | GET /api/v1/shifts/{id}/z-report | 18 §3.3; 30 (US API) |  |
| B3-EP-18#6 | ⬜ | event sale.created | 18 §4; 27 vazifa matni |  |
| B3-EP-18#7 | ⬜ | event sale.draft_voided | 18 §5; 27 vazifa matni |  |
| B3-EP-18#8 | ⬜ | event receipt.reprinted | 18 §6; 27 B3: qayta chop etish auditi |  |
| B3-EP-18#9 | ⬜ | event return.created | 18 §7.1; 27 vazifa matni |  |
| B3-EP-18#10 | ⬜ | GET /api/v1/returns / GET /api/v1/returns/{id} | 18 §7.2; 30 (US API) |  |
| B3-EP-18#12 | ⬜ | POST /api/v1/approval-requests | 18 §9.2; 27 vazifa matni |  |
| B3-EP-18#13 | ⬜ | GET /api/v1/approval-requests / GET /{id} | 18 §9.3; 27 vazifa matni |  |
| B3-EP-18#14 | ⬜ | POST /api/v1/approval-requests/{id}/approve | 18 §9.4; 27 vazifa matni |  |
| B3-EP-18#15 | ⬜ | POST /api/v1/approval-requests/{id}/reject | 18 §9.5; 30 (US API) |  |
| B3-EP-18#30 | ⬜ | event cash_movement.created | 18 §13.1; 30 (US API) |  |
| B3-EP-18#32 | ⬜ | GET /api/v1/cash-movements | 18 §13.3; 30 (US API) |  |
| B3-EP-18#33 | ⬜ | GET /api/v1/fiscal-receipts / GET /{id} | 18 §14.1; fiskal chek (`FakeFiscalAdapter`) — 27 B3; infratuzilma/admin (30 §3-E) |  |
| B3-EP-18#34 | ⬜ | POST /api/v1/fiscal-receipts/{id}/retry | 18 §14.2; fiskal retry (BO-14) — 27 B3; infratuzilma/admin |  |
| B3-EP-18#40 | ⬜ | POST /api/v1/sync/push / GET /api/v1/sync/pull | 18 §17, 2.6; 27 vazifa matni |  |
| B3-EP-18#41 | ⬜ | GET /api/v1/sales / GET /api/v1/sales/{id} | 18 §4.8; 30 (US API) |  |
| B3-EP-18#42 | ⬜ | POST /api/v1/card-terminal-transactions | 18 §16a.3; 27 vazifa matni |  |
| B3-EP-18#43 | ⬜ | GET /api/v1/card-terminal-transactions/{id} | 18 §16a.4; 30 (US API) |  |
| B3-EP-18#44 | ⬜ | GET /api/v1/card-terminals / POST /api/v1/card-terminals | 18 §16a.5; 27 vazifa matni |  |
| B3-EP-18#45 | ⬜ | PATCH /api/v1/card-terminals/{id} | 18 §16a.5; 30 (US API) |  |
| B3-EP-18#46 | ⬜ | POST /api/v1/card-terminal-settlements | 18 §16a.6; 30 (US API) |  |
| B3-EP-19#76 | ⬜ | GET/PATCH /stock-settings | 19 §17; tarozi shtrix-kod formati (US-M09-06, B3), kam qoldiq chegarasi — B4 |  |
| B3-EP-20#1 | ⬜ | GET /reports/vat-summary — Ichki QQS/aylanma hisob-kitobi (davr bo'yicha) | 20 indeks; 30 (US API) |  |
| B3-EP-20#2 | ⬜ | GET /vat-moves — QQS registri (vat_moves) ro'yxati | 20 indeks; 30 (US API) |  |
| B3-EP-20#29a | ✅ | GET /devices — Tenant qurilmalari ro'yxati (BO-11 «Qurilmalar» tabi) | 20 indeks; 27 vazifa matni | kod: `backend/app/modules/branches/api/devices.py`; test: `backend/tests/integration/test_admin_users_invite.py`, `backend/tests/integration/test_admin_users_sessions.py`, `backend/tests/integration/test_devices_api.py` |
| B3-EP-20#29b | ✅ | POST /devices/{id}/revoke — Qurilmani bekor qilish | 20 indeks; 27 vazifa matni | kod: `backend/app/modules/branches/api/devices.py`; test: `backend/tests/integration/test_admin_users_sessions.py`, `backend/tests/integration/test_devices_api.py`, `web/apps/shell/e2e/staff.spec.ts` |
| B3-EP-20#40f | ⬜ | GET /sync-exceptions — Sinxron istisnolari ro'yxati (BO-14) | 20 indeks; sinxron istisnolari (BO-14) — 27 B3 offline |  |
| B3-EP-20#40g | ⬜ | POST /sync-exceptions/{id}/review — Istisnoni «Ko'rib chiqildi» deb belgilash | 20 indeks; sinxron istisnolari (BO-14) — 27 B3 offline |  |
| B3-EP-20#52 | ⬜ | GET /cash-movements — Kassa pul harakati ro'yxati | 20 indeks; 30 (US API) |  |
| B3-EP-20#53 | ⬜ | POST /cash-movements — Pul qo'yish/olish yozish | 20 indeks; 30 (US API) |  |
| B3-EP-20#54 | ⬜ | POST /cash-movements/{id}/cancel — Harakatni bekor qilish | 20 indeks; 30 (resurs) |  |
| B3-EP-20#55 | ⬜ | GET /cash-registers/{id}/cash-history — Smena/kassa bo'yicha naqd tarixi | 20 indeks; 30 (US API) |  |

### Bosqich 3 — Ekranlar (06/07)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B3-SCR-POS-01 | ⬜ | POS-01 — Kassaga kirish / Smena ochish | 07; 27/30; ko'chirildi B1 → B3: 27 B3: M01 kassa, smena ochish va POS-01 (iOS ko'rsatmasi bilan) — Bosqich 3 da quriladi; B1 ulushi (US-M13-06 tiklash) `/recover` sahifasida, BO-01 qatorida |  |
| B3-SCR-BO-07 | ⬜ | BO-07 — QQS ichki hisob-kitobi | 07; 27/30 |  |
| B3-SCR-BO-09 | ⬜ | BO-09 — Hisobotlar markazi | 07; 27/30 |  |
| B3-SCR-BO-11 | ⬜ | BO-11 — Foydalanuvchilar, huquqlar va sessiyalar | 07; 27/30 |  |
| B3-SCR-BO-12 | ⬜ | BO-12 — Filiallar boshqaruvi | 07; 27/30 |  |
| B3-SCR-BO-14 | ⬜ | BO-14 — Tenant/do'kon sozlamalari | 07; 27/30 |  |
| B3-SCR-BO-16 | ⬜ | BO-16 — Tasdiqlash navbati (limitdan oshgan so'rovlar) | 07; 27/30 |  |
| B3-SCR-BO-24 | ⬜ | BO-24 — Bank tushumi tasdig'i (yo'ldagi pul → bank) | 07; 27/30 |  |
| B3-SCR-POS-02 | ⬜ | POS-02 — Sotish paneli (asosiy chek) | 07; 27/30 |  |
| B3-SCR-POS-03 | ⬜ | POS-03 — To'lov usuli va hisoblash | 07; 27/30 |  |
| B3-SCR-POS-04 | ⬜ | POS-04 — Chekni chop etish (elektron chek — zahira) | 07; 27/30 |  |
| B3-SCR-POS-05 | ⬜ | POS-05 — Mijozdan tovar qaytarish | 07; 27/30 |  |
| B3-SCR-POS-07 | ⬜ | POS-07 — Smena yopish, Z-hisobot | 07; 27/30 |  |
| B3-SCR-POS-11 | ⬜ | POS-11 — Mahsulot va narxni tez qidirish | 07; 27/30 |  |
| B3-SCR-POS-12 | ⬜ | POS-12 — Offline/sinxronizatsiya holati | 07; 27/30 |  |
| B3-SCR-POS-14 | ⬜ | POS-14 — Kassaga pul qo'yish / kassadan pul olish | 07; 27/30 |  |
| B3-SCR-POS-15 | ⬜ | POS-15 — Smena yopishda naqdni sanash | 07; 27/30 |  |
| B3-SCR-POS-16 | ⬜ | POS-16 — Uskunalar sozlamasi (printer, skaner, tarozi) | 07; 27/30 |  |

### Bosqich 3 — Jadvallar / migratsiyalar (12)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B3-TBL-platform.card_bin_rules | 🟡 | `platform.card_bin_rules` (revizion 0007) | 12; 27 vazifa matni | DDL 0007 bor; ilova kodi bor, test yo'q |
| B3-TBL-auth.authorization_codes | 🟡 | `auth.authorization_codes` (revizion 0003) | 12; 27 vazifa matni | DDL 0003 bor; ilova kodi bor, test yo'q |
| B3-TBL-auth.refresh_tokens | ✅ | `auth.refresh_tokens` (revizion 0003) | 12; 27 vazifa matni | DDL 0003; kod va test: `backend/tests/integration/test_admin_users_sessions.py`, `backend/tests/integration/test_auth_gate_fixes.py` |
| B3-TBL-app.approval_requests | ✅ | `app.approval_requests` (revizion 0010) | 12; 27 vazifa matni | DDL 0010; kod va test: `backend/tests/integration/test_pricing_price_changes.py` |
| B3-TBL-app.doc_approvals | 🟡 | `app.doc_approvals` (revizion 0010) | 12; 27 vazifa matni | DDL 0010 bor; modul kodi/testi yo'q |
| B3-TBL-app.payment_checkouts | 🟡 | `app.payment_checkouts` (revizion 0010) | 12; 30 (US jadvallari) | DDL 0010 bor; modul kodi/testi yo'q |
| B3-TBL-app.card_terminals | 🟡 | `app.card_terminals` (revizion 0010) | 12; 27 vazifa matni | DDL 0010 bor; modul kodi/testi yo'q |
| B3-TBL-app.shifts | ✅ | `app.shifts` (revizion 0011) | 12; 30 (US jadvallari) | DDL 0011; kod va test: `backend/tests/integration/test_admin_users_sessions.py`, `backend/tests/support/branches.py` |
| B3-TBL-app.sales | ✅ | `app.sales` (revizion 0011) | 12; 30 (US jadvallari) | DDL 0011; kod va test: `backend/tests/integration/test_rls.py`, `backend/tests/support/branches.py` |
| B3-TBL-app.sale_lines | 🟡 | `app.sale_lines` (revizion 0011) | 12; 30 (US jadvallari) | DDL 0011 bor; modul kodi/testi yo'q |
| B3-TBL-app.card_terminal_transactions | 🟡 | `app.card_terminal_transactions` (revizion 0011) | 12; 27 vazifa matni | DDL 0011 bor; modul kodi/testi yo'q |
| B3-TBL-app.sale_payments | 🟡 | `app.sale_payments` (revizion 0011) | 12; 27 vazifa matni | DDL 0011 bor; modul kodi/testi yo'q |
| B3-TBL-app.returns | 🟡 | `app.returns` (revizion 0012) | 12; 27 vazifa matni | DDL 0012 bor; modul kodi/testi yo'q |
| B3-TBL-app.return_lines | 🟡 | `app.return_lines` (revizion 0012) | 12; 30 (US jadvallari) | DDL 0012 bor; modul kodi/testi yo'q |
| B3-TBL-app.debt_payments | 🟡 | `app.debt_payments` (revizion 0017) | 12; 27 vazifa matni | DDL 0017 bor; modul kodi/testi yo'q |
| B3-TBL-app.cash_movements | 🟡 | `app.cash_movements` (revizion 0018) | 12; 30 (US jadvallari) | DDL 0018 bor; modul kodi/testi yo'q |
| B3-TBL-app.card_terminal_settlements | 🟡 | `app.card_terminal_settlements` (revizion 0018) | 12; 30 (US jadvallari) | DDL 0018 bor; modul kodi/testi yo'q |
| B3-TBL-app.cash_moves | 🟡 | `app.cash_moves` (revizion 0015) | 12; 30 (US jadvallari) | DDL 0015 bor; modul kodi/testi yo'q |
| B3-TBL-app.fiscal_receipts | 🟡 | `app.fiscal_receipts` (revizion 0020) | 12; 30 (US jadvallari) | DDL 0020 bor; modul kodi/testi yo'q |
| B3-TBL-app.sync_receipts | 🟡 | `app.sync_receipts` (revizion 0022) | 12; 30 (US jadvallari) | DDL 0022 bor; modul kodi/testi yo'q |
| B3-TBL-app.sync_exceptions | 🟡 | `app.sync_exceptions` (revizion 0022) | 12; 27 vazifa matni | DDL 0022 bor; modul kodi/testi yo'q |
| B3-TBL-app.idempotency_keys | ✅ | `app.idempotency_keys` (revizion 0022) | 12; 30 (US jadvallari) | DDL 0022; kod va test: `backend/tests/integration/test_health_and_idempotency.py`, `backend/tests/integration/test_purge_idempotency.py` |

### Bosqich 3 — Qabul testlari (31)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B3-QT-IDEMP-01 | ⬜ | QT-IDEMP-01 (integration) — Berilgan Idempotency-Key=K1 bilan POST /api/v1/cash-movements muvaffaqiyatli yakunlangan (201), qachonki xuddi shu K1 va bir xil so'rov tanas… | 31; 31 §1.2 — `cash-movements`/`sync/push` ustida (B3) |  |
| B3-QT-IDEMP-02 | ⬜ | QT-IDEMP-02 (integration) — Berilgan Idempotency-Key=K2 bilan birinchi so'rov hali bajarilmoqda (DB tranzaksiyasi tugamagan — test parallel thread/lock simulyatsiyasi bi… | 31; 31 §1.2 — `cash-movements`/`sync/push` ustida (B3) |  |
| B3-QT-IDEMP-03 | ⬜ | QT-IDEMP-03 (integration) — Berilgan Idempotency-Key=K3 allaqachon bir so'rov (masalan cash_movements, summa "50000.00") uchun ishlatilgan, qachonki xuddi shu K3 bilan b… | 31; 31 §1.2 — `cash-movements`/`sync/push` ustida (B3) |  |
| B3-QT-IDEMP-04 | ⬜ | QT-IDEMP-04 (integration) — Berilgan POS offline rejimda sale.created voqeasini client_event_id=E1 bilan outbox'ga yozgan va bir marta POST /sync/push orqali yuborgan (q… | 31; 31 §1.2 — `cash-movements`/`sync/push` ustida (B3) |  |
| B3-QT-SEQ-01 | ⬜ | QT-SEQ-01 (integration) — Berilgan shift_id=SH1, cash_register_id=CR1 ochiq smenada receipt_seq=5 bilan chek allaqachon fiscal_receiptsga yozilgan, qachonki xuddi shu (c… | 31; 31 §1.3 — smena/chek (B3) |  |
| B3-QT-SEQ-02 | ⬜ | QT-SEQ-02 (integration) — Berilgan shift_id=SH1 qurilma D1da ochilgan (shifts.device_id=D1), qachonki qurilma D2dan xuddi shu shift_id=SH1 uchun yangi voqea (sale.create… | 31; 31 §1.3 — smena/chek (B3) |  |
| B3-QT-SEQ-03 | ⬜ | QT-SEQ-03 (integration) — Berilgan shift_id=SH1 yopilgan va Z-hisobot (fiscal_receipts.kind='z_report') allaqachon yaratilgan, qachonki shu smena uchun ikkinchi Z-hisobo… | 31; 31 §1.3 — smena/chek (B3) |  |
| B3-QT-OFFLINE48-01 | ⬜ | QT-OFFLINE48-01 (integration (fake clock)) — Berilgan "Kassa-1"da OFD tasdig'ini olmagan eng eski fiskal chek (fiscal_receipts.ofd_acked_at IS NULL) t0da yaratilgan, int… | 31; 27 B3 Tayyor (QT-OFFLINE48); -05 — B5 |  |
| B3-QT-OFFLINE48-02 | ⬜ | QT-OFFLINE48-02 (integration (fake clock)) — Berilgan qurilma soati server qabul vaqtidan (received_at) ancha orqada (soat "orqaga surilgan" taqlidi), qachonki created_a… | 31; 27 B3 Tayyor (QT-OFFLINE48); -05 — B5 |  |
| B3-QT-OFFLINE48-03 | ⬜ | QT-OFFLINE48-03 (integration (fake clock) + e2e) — Berilgan QT-OFFLINE48-01 holati, qachonki t0+48 soat o'tib Kassir yangi sotuv (shuningdek qaytarish, debt_settlement)… | 31; 27 B3 Tayyor (QT-OFFLINE48); -05 — B5 |  |
| B3-QT-OFFLINE48-04 | ⬜ | QT-OFFLINE48-04 (integration (fake clock)) — Berilgan kassa QT-OFFLINE48-03 bo'yicha bloklangan, qachonki internet qaytib barcha kutilayotgan cheklar OFD tasdig'ini olsa… | 31; 27 B3 Tayyor (QT-OFFLINE48); -05 — B5 |  |
| B3-QT-PERM-01 | ⬜ | QT-PERM-01 (integration) — Berilgan Egasi hisobi, qachonki u istalgan summa/foizdagi chegirma, qaytarish, kassadan pul olish, qarzni kechirish amalini bajarsa, unda hech… | 31; 31 §1.7 — chegirma/qaytarish/pul olish limitlari (B3) |  |
| B3-QT-PERM-02 | ⬜ | QT-PERM-02 (integration) — Berilgan Kassir chekka discount_pct="5.00" (standart limit) chegirma qo'ymoqda, qachonki chek yakunlansa, unda 201, tasdiq talab qilinmaydi. | 31; 31 §1.7 — chegirma/qaytarish/pul olish limitlari (B3) |  |
| B3-QT-PERM-03 | ⬜ | QT-PERM-03 (integration) — Berilgan Kassir chekka discount_pct="6.00" (limitdan yuqori) chegirma qo'ymoqda, qachonki tasdiqsiz yakunlashga urinsa, unda 403 DISCOUNT_LIMI… | 31; 31 §1.7 — chegirma/qaytarish/pul olish limitlari (B3) |  |
| B3-QT-PERM-04 | ⬜ | QT-PERM-04 (integration) — Berilgan Kassir asl chek topilmagan qaytarishni amalga oshirmoqda, summa atigi "10000.00" (limitdan ancha past), qachonki tasdiqsiz yakunlashg… | 31; 31 §1.7 — chegirma/qaytarish/pul olish limitlari (B3) |  |
| B3-QT-PERM-05 | ⬜ | QT-PERM-05 (integration) — Berilgan Kassir kassadan "50000.00" (standart limit chegarasida) pul olmoqda, qachonki amal bajarilsa, unda tasdiqsiz o'tadi; qachonki "50001.… | 31; 31 §1.7 — chegirma/qaytarish/pul olish limitlari (B3) |  |
| B3-QT-PERM-06 | ⬜ | QT-PERM-06 (integration) — Berilgan approval_requests qatori Kassir tomonidan yaratilgan (requested_by=kassir), qachonki xuddi shu Kassir uni "tasdiqlash" so'rovini yubo… | 31; 31 §1.7 — chegirma/qaytarish/pul olish limitlari (B3) |  |
| B3-QT-PERM-07 | ⬜ | QT-PERM-07 (integration) — Berilgan bitta approval_requests qatori tasdiqlangan va hujjatda bir marta ishlatilgan (status='consumed'), qachonki xuddi shu approval_reques… | 31; 31 §1.7 — chegirma/qaytarish/pul olish limitlari (B3) |  |
| B3-QT-M01-01 | ⬜ | QT-M01-01 (happy) — Berilgan ochiq smena, kassaga "Coca-Cola 1.5L" (narx "12000.00", QQS 12%) 1 dona qo'shiladi va naqd to'lov bilan yakunlanadi, qachonki chek post qili… | 31; 31 US (US-M01-01) |  |
| B3-QT-M01-02 | ⬜ | QT-M01-02 (negative) — Berilgan ochiq smena yo'q, qachonki sale.created voqeasi yuborilsa, unda error_code=SHIFT_NOT_OPEN, hujjat yaratilmaydi. | 31; 31 US (US-M01-01) |  |
| B3-QT-M01-03 | ⬜ | QT-M01-03 (happy) — Berilgan POS offline rejimda, qachonki kassir chek yaratsa, unda chek lokal (client_event_id bilan) saqlanadi, fiscal_receipts.offline_since to'ldiri… | 31; 31 US (US-M01-02) |  |
| B3-QT-M01-06 | ⬜ | QT-M01-06 (happy) — Berilgan smena yopilmoqda, kutilgan naqd "500000.00" hisoblangan, sanalgan naqd "500000.00" kiritilgan, qachonki "Smena yopish" bosilsa, unda farq "0… | 31; 31 US (US-M01-04) |  |
| B3-QT-M01-07 | ⬜ | QT-M01-07 (negative) — Berilgan kutilgan naqd "500000.00", sanalgan "480000.00", qachonki smena yopilsa, unda farq "-20000.00" (kamomad) ko'rsatiladi, kassir izoh kiriti… | 31; 31 US (US-M01-04) |  |
| B3-QT-M01-08 | ⬜ | QT-M01-08 (happy) — Berilgan yuridik shaxs mijoz UzQR orqali to'lamoqda, qachonki bank yagona QR skanerlanib to'lov tasdiqlansa, unda cash_moves.method='uzqr', ledger_en… | 31; 31 US (US-M01-05) |  |
| B3-QT-M01-10 | ⬜ | QT-M01-10 (happy (aralash to'lov)) — Berilgan chek jami "100000.00", naqd "40000.00" + karta "30000.00" + nasiya "30000.00", qachonki yakunlansa, unda sale_payments 3 qa… | 31; 31 US (US-M01-01) |  |
| B3-QT-M01-11 | ⬜ | QT-M01-11 (negative (draft void)) — Berilgan chek hali to'lanmagan (draft), ichida 2 qator bor, qachonki Kassir to'lovdan oldin butun chekni "BEKOR" bossa, unda sale.dra… | 31; 31 US (US-M01-01) |  |
| B3-QT-M01-12 | ⬜ | QT-M01-12 (happy (qayta chop etish)) — Berilgan S1 chek allaqachon chop etilgan va to'liq fiskallashgan, qachonki Kassir "Qayta chop etish"ni bossa, unda receipt.reprint… | 31; 31 US (US-M01-01) |  |
| B3-QT-M01-13 | ⬜ | QT-M01-13 (negative (UzQR kutilmoqda)) — Berilgan mijoz dinamik UzQR'ni skanerlagan, bank tasdig'i hali kelmagan, qachonki internet uzilib ketsa, unda chek "to'lov kutil… | 31; 31 US (US-M01-05) |  |
| B3-QT-M01-14 | ⬜ | QT-M01-14 (happy (terminalsiz karta, rekvizitsiz)) — Berilgan chek jami "12000.00", "Kassa-2" (faol bog'langan karta terminali yo'q), qachonki sale_payments(method='card… | 31; 31 US (US-M01-01) |  |
| B3-QT-M01-15 | ⬜ | QT-M01-15 (negative (terminalsiz karta qatorida re…) — Berilgan terminalsiz karta to'lovi (card_entry_mode='manual', manual_reason='standalone_terminal'), qachonki qator… | 31; 31 US (US-M01-01) |  |
| B3-QT-M01-16 | ⬜ | QT-M01-16 (happy (statik UzQR)) — Berilgan do'konda statik UzQR plakat, qachonki mijoz to'lagach Kassir to'lovni qo'lda tasdiqlasa, unda sale_payments(method='uzqr', qr_… | 31; 31 US (US-M01-05) |  |
| B3-QT-M01-17 | ⬜ | QT-M01-17 (negative (UzQR maydonlari)) — Berilgan method='uzqr', qachonki qr_type yuborilmasa — 422 VALIDATION_ERROR; qachonki qr_type='dynamic' va provider_tx_id bo'sh… | 31; 31 US (US-M01-05) |  |
| B3-QT-M01-22 | ⬜ | QT-M01-22 (happy (uskunalar sozlamasi, e2e)) — Berilgan POS-16 ochiq (Chrome desktop), printer Web Serial orqali tanlangan, qachonki "Sinov chek" bosilsa, unda "Ўзбекист… | 31; 27 (aniq havola) |  |
| B3-QT-M01-24 | ⬜ | QT-M01-24 (happy (integratsiyalangan karta, qaror…) — Berilgan "Kassa-1" ga FakeCardTerminalAdapter terminali T1 bog'langan (adapter='fake', is_default=true, health_stat… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-25 | ⬜ | QT-M01-25 (negative (rad etildi)) — Berilgan QT-M01-24 holati, Fake declined qaytaradi (decline_code="51", decline_message="Mablag' yetarli emas"), qachonki Kassir "Kart… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-26 | ⬜ | QT-M01-26 (negative (taymaut → unknown → holat so'…) — Berilgan Fake purchase ga javob bermaydi (taymaut), keyin get_status(attempt_id) → approved, qachonki Kassir "Kart… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-27 | ⬜ | QT-M01-27 (negative (unknown ni menejer yopishi)) — Berilgan urinish unknown va holat so'rovi natija bermadi, terminal chekida tasdiq bor, qachonki Kassir (card.manual_e… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-28 | ⬜ | QT-M01-28 (happy (idempotentlik, attempt_id)) — Berilgan approved natija POST /api/v1/card-terminal-transactions bilan id=A1 sifatida yozilgan, qachonki xuddi shu id=A1… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-29 | ⬜ | QT-M01-29 (negative (fiskal xato → "chek kutilmoqd…) — Berilgan karta approved, lekin FM emulyatori fiskal chekni xato bilan qaytaradi, qachonki POS holatini tekshirsak,… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-30 | ⬜ | QT-M01-30 (negative (summa mos emas)) — Berilgan chek jami "12000.00", Fake approved qaytaradi lekin approved_amount="11000.00", qachonki natija olinsa, unda CARD_AMOUNT… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-31 | ⬜ | QT-M01-31 (negative (terminalsiz karta siyosati —…) — Berilgan "Kassa-1" (T1 bog'langan), T1 health_status='offline' (CARD_TERMINAL_UNREACHABLE), tenants.settings.card_m… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-32 | ⬜ | QT-M01-32 (negative (to'lov qatori CHECK'lari)) — Qachonki sale_payments(method='card') card_entry_modesiz yuborilsa — 422 VALIDATION_ERROR; card_entry_mode='integrated'… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-33 | ⬜ | QT-M01-33 (happy (karta turi manbasi)) — Berilgan Fake natijasida card_type yo'q, card_mask="86001234", terminal xom javobida BIN 860031, platform.card_bin_rules da 8600… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-34 | ⬜ | QT-M01-34 (happy (offline, agent orqali)) — Berilgan do'kon interneti yo'q (server yetib bo'lmaydi), Do'kon agenti va Fake terminal ishlaydi, qachonki integratsiyalangan… | 31; 31 US (US-M01-08) |  |
| B3-QT-M01-35 | ⬜ | QT-M01-35 (happy (POS-03 e2e, Playwright)) — Berilgan QT-M01-24 holati, Fake 3 soniya kutib approved qaytaradi, qachonki Kassir "Karta"ni bossa, unda POS-03 da: terminal… | 31; 31 US (US-M01-08) |  |
| B3-QT-M02-01 | ⬜ | QT-M02-01 (happy) — Berilgan asl chek topilgan, 1 dona "Coca-Cola 1.5L" qaytarilmoqda, qachonki qaytarish post qilinsa, unda stock_moves(qty=+1.000) asl partiyaga, ledge… | 31; 31 US (US-M02-01) |  |
| B3-QT-M02-02 | ⬜ | QT-M02-02 (negative) — Berilgan asl chek topilmagan, qachonki Kassir summadan qat'i nazar tasdiqsiz yakunlashga urinsa, unda har doim Menejer/Egasi PIN (return_no_receip… | 31; 31 US (US-M02-01) |  |
| B3-QT-M02-03 | ⬜ | QT-M02-03 (happy) — Berilgan asl chek bilan qaytarish summasi "100000.00" (standart limit chegarasida), qachonki Kassir tasdiqsiz yakunlasa, unda 201, tasdiq talab qilin… | 31; 31 US (US-M02-02) |  |
| B3-QT-M02-04 | ⬜ | QT-M02-04 (negative) — Berilgan qaytarish summasi "150000.00" (limitdan yuqori), qachonki Kassir tasdiqsiz yakunlashga urinsa, unda return_over_limit approval talab qili… | 31; 31 US (US-M02-02) |  |
| B3-QT-M02-05 | ⬜ | QT-M02-05 (happy) — 4010 (refund_method bo'yicha) yoziladi, shu tranzaksiyada vat_moves(kind=output) qaytarish hujjatiga bog'lanib QQSni kamaytiradi (13-provodka-qoidala… | 31; 31 US (US-M02-03) |  |
| B3-QT-M02-06 | ⬜ | QT-M02-06 (negative (markirovka, offline)) — Berilgan "Hayot suvi 1.5L" (is_marked=true) qatori bilan asl chek, qurilma offline, qachonki Kassir shu qatorni qaytarishga… | 31; 31 US (US-M02-01) |  |
| B3-QT-M02-07 | ⬜ | QT-M02-07 (negative (muddati o'tgan tovar)) — Berilgan qaytarilayotgan qator mahsulotining yaroqlilik muddati o'tgan, qachonki Kassir (returns.approve yo'q) qaytarishni… | 31; 31 US (US-M02-01) |  |
| B3-QT-M02-08 | ⬜ | QT-M02-08 (happy (integratsiyalangan karta qaytari…) — Berilgan asl sotuv QT-M01-24 bo'yicha (card_entry_mode='integrated', rrn="612345678901"), qachonki shu kuni, termi… | 31; 31 US (US-M02-01) |  |
| B3-QT-M03-01 | ⬜ | QT-M03-01 (happy) — Berilgan Kassir chekka "5.00"% chegirma qo'ymoqda, qachonki yakunlansa, unda QQS chegirmadan keyingi summadan hisoblanadi (M10 qoidasi), sale_lines.d… | 31; 31 US (US-M03-01) |  |
| B3-QT-M03-02 | ⬜ | QT-M03-02 (negative) — QT-PERM-03 bilan bir xil (limitdan yuqori chegirma — tasdiq talab qilinadi). | 31; 31 US (US-M03-01) |  |
| B3-QT-M03-04 | ⬜ | QT-M03-04 (negative (stacking)) — Berilgan bir chekda mijozning doimiy chegirmasi ("10.00"%) va kassir chegirmasi ("5.00"%) to'qnashgan, qachonki chek yakunlansa, unda c… | 31; 31 US (US-M03-01) |  |
| B3-QT-M03-05 | ⬜ | QT-M03-05 (negative (manfiy narx)) — Berilgan tovar narxi "3000.00", qachonki Kassir "120.00"% chegirma kiritishga urinsa (narxni manfiy qilib yuboradigan), unda 422 VAL… | 31; 31 US (US-M03-01) |  |
| B3-QT-M05-05 | ⬜ | QT-M05-05 (happy (mobil skaner, offline; Bosqich 3…) — Berilgan Omborchi veb PWA (POS-10) bilan inventarizatsiya skanerlaydi, internet yo'q, qachonki har tovar skanerlan… | 31; 27 (aniq havola) |  |
| B3-QT-M06-04 | ⬜ | QT-M06-04 (happy (offline; Bosqich 3 — sync)) — Berilgan ichki (o'z filiallari orasidagi) ko'chirish, internet yo'q, qachonki hujjat lokal yaratilsa, unda append-only ju… | 31; 27 (aniq havola) |  |
| B3-QT-M09-03 | ⬜ | QT-M09-03 (happy) — Berilgan kassa ekrani ochiq, qachonki tovar tanlansa, unda joriy narx ko'rsatiladi, tahrirlash tugmasi Kassir uchun faol emas. | 31; 31 US (US-M09-03) |  |
| B3-QT-M09-06 | ⬜ | QT-M09-06 (happy) — Berilgan "Mol go'shti (kg)" uchun tarozi yorlig'i (EAN-13 "2x" prefiks, og'irlik kodlangan), qachonki kassir skanerlasa, unda POS kod ichidan tovar v… | 31; 31 US (US-M09-06) |  |
| B3-QT-M10-01 | ⬜ | QT-M10-01 (happy) — Berilgan tovar vat_rate=12.00, qachonki sotuv amalga oshsa, unda QQS summasi avtomatik hisoblanib chekka va ledger_entriesga (Kt 6410) kiradi. | 31; 31 US (US-M10-01) |  |
| B3-QT-M10-06 | ⬜ | QT-M10-06 (unit (formula)) — Berilgan price="3000.00" (QQS kiritilgan), vat_rate="12.00"; qachonki vat_amount = ROUND_HALF_UP(price × rate/(100+rate), 2) hisoblansa, und… | 31; 31 US (US-M10-01) |  |
| B3-QT-M16-01 | ⬜ | QT-M16-01 (happy) — Berilgan smena ochiq, qachonki Kassir "40000.00" kassadan "Boshqa" sababi bilan olsa (limit "50000.00"dan past), unda tasdiqsiz o'tadi, cash_moves(am… | 31; 31 US (US-M16-01) |  |
| B3-QT-M16-02 | ⬜ | QT-M16-02 (negative) — QT-PERM-05 bilan bir xil ("50001.00" — tasdiq talab qilinadi). | 31; 31 US (US-M16-01) |  |
| B3-QT-M16-03 | ⬜ | QT-M16-03 (happy) — Berilgan smena yopilmoqda: boshlang'ich naqd "200000.00", naqd sotuvlar "350000.00", naqd qarz to'lovlari "50000.00", qo'yilgan "0.00", olingan "4000… | 31; 31 US (US-M16-02) |  |
| B3-QT-M16-04 | ⬜ | QT-M16-04 (happy) — Berilgan tanlangan davr, qachonki "Kassa harakati" hisoboti ochilsa, unda har smena bo'yicha boshlanish/sotuv/qo'yilgan-olingan/kutilgan-sanalgan/far… | 31; 31 US (US-M16-03) |  |
| B3-QT-M16-05 | ⬜ | QT-M16-05 (happy (karta jami)) — Berilgan smenada terminalsiz "Karta" to'lovlari (card_entry_mode='manual', rekvizitsiz) jami "450000.00" (3 ta to'lov) va integratsiyala… | 31; 31 US (US-M16-02) |  |
| B3-QT-M16-06 | ⬜ | QT-M16-06 (happy (Egasi oldi)) — Berilgan tenant legal_form='llc', ta'sischi kontragent (counterparties.is_founder=true), qachonki cash_movements(reason='owner_withdrawa… | 31; 31 US (US-M16-01) |  |
| B3-QT-M16-07 | ⬜ | QT-M16-07 (happy (smena ortiqchasi)) — Berilgan kutilgan naqd "500000.00", sanalgan "505000.00", qachonki smena yopilsa, unda ledger_entries: Dt 5010 / Kt 9390 = "5000.0… | 31; 31 US (US-M16-02) |  |
| B3-QT-M16-08 | ⬜ | QT-M16-08 (negative (terminal settlement farqi, qa…) — Berilgan smenada T1 orqali integratsiyalangan karta xaridlari "700000.00" (expected_total), qachonki smena yopilis… | 31; 31 US (US-M16-02) |  |
| B3-QT-NFR-01 | ⬜ | QT-NFR-01 (e2e (performance)) — Berilgan POS ochiq, lokal SQLite/IndexedDB, qachonki shtrix-kod skanerlansa, unda chekka qator qo'shilishi < 100 ms ichida tugaydi (serve… | 31; POS tezligi (B3) |  |
| B3-QT-NFR-02 | ⬜ | QT-NFR-02 (e2e (performance)) — Berilgan offline rejim, qachonki to'lov tasdiqlanib chek yakunlansa, unda chek chiqishi < 1 s ichida tugaydi (fiskal/OFD yuborish asinxro… | 31; POS tezligi (B3) |  |
| B3-QT-NFR-03 | ⬜ | QT-NFR-03 (integration (load)) — Berilgan o'qish so'rovi (masalan qoldiq/narx), qachonki yuklama testi bajarilsa, unda API javob vaqti p95 < 300 ms. | 31; API p95 — sotuv posting (B3) |  |
| B3-QT-NFR-04 | ⬜ | QT-NFR-04 (integration (load)) — Berilgan yozuvchi so'rov (sotuv posting — hujjat+registr+provodka bitta tranzaksiyada), qachonki yuklama testi bajarilsa, unda API javob… | 31; API p95 — sotuv posting (B3) |  |
| B3-QT-NFR-06 | ⬜ | QT-NFR-06 (integration (fake clock)) — QT-OFFLINE48-01/03 bilan bir xil — offline chekning OFD'ga yetib borishi ≤ 48 soat; 48 soatda yangi fiskal chek bloklanadi (100% q… | 31; 48 soat (B3) |  |
| B3-QT-NFR-09 | ⬜ | QT-NFR-09 (integration (load)) — Berilgan bitta qurilma, qachonki /sync/pushga soniyasiga 6 so'rov yuborilsa (5/soniya chegarasidan yuqori), unda 429 Too Many Requests +… | 31; sync sig'imi (B3) |  |
| B3-QT-NFR-10 | ⬜ | QT-NFR-10 (integration) — Berilgan qurilma birinchi marta ro'yxatdan o'tgan (lokal baza bo'sh), qachonki GET /sync/pull?scope=all&cursor= chaqirilsa, unda natija page_si… | 31; sync sig'imi (B3) |  |
| B3-QT-NFR-11 | ⬜ | QT-NFR-11 (integration (offline sig'im)) — Berilgan qurilma 48 soat uzluksiz offline ishlagan, shu davrda ≈300 ta sale.created/return.created/cash_movement.created voqea… | 31; sync sig'imi (B3) |  |
| B3-QT-NFR-12 | ⬜ | QT-NFR-12 (integration (mavjudlik)) — Berilgan ilova darajasidagi rejali texnik ish oynasi (yakshanba 02:00–04:00, taxmin), qachonki shu oynada backend vaqtincha mavjud… | 31; sync sig'imi (B3) |  |

## Bosqich 4: qarz daftari, xarajatlar, hisobotlar, Telegram

**Maqsad (27):** Do'kon qog'oz qarz daftarini va xarajat qaydlarini to'liq elektron qiladi, egasi kunlik hisobotni Telegram'da oladi.

Holat: ✅ 1 · 🟡 17 · ⬜ 148 · ⛔ 0 · ⏭ 0 · jami 166

### Bosqich 4 — Vazifalar (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B4-T01 | ⬜ | M08 qarz daftari: tez qarz yozish (offline), mijoz daftari, boshlang'ich qarzlar, to'lov (eng eski qarzdan), va'da sanasi, qarzlar hisoboti; offline qarz to'lovi: `customers.open_debt_docs` keshi, `shared/lib/debt-allocation` + `shared/debt-allocation-vectors…` | 27 |  |
| B4-T02 | ⬜ | `debt_writeoffs` (`POST /debt-writeoffs`, `/post`, Egasi) va `debt-doubtful-flags` (`13` §2.15/§2.15a, `18` §12.5–§12.6) | 27 |  |
| B4-T03 | ⬜ | Yetkazib beruvchiga qarz va unga to'lov (US-M08-11, US-M07-04 — `supplier_payments`, bank/naqd) | 27 |  |
| B4-T04 | ⬜ | M15 xarajatlar (+ takrorlanuvchi), sof foyda; POS kassa xarajati — `expense.created` voqeasi (`16`/`18` `expense.created`) | 27 |  |
| B4-T05 | ⬜ | Bank tushumi tasdig'i (`bank_settlements`, qaror #42): 5710 dagi karta/UzQR/Click/Payme/Uzum tushumlari va inkassani bank ko'chirmasi bo'yicha 5110 ga o'tkazish + komissiya (`Dt 9430 / Kt 5710`; inkassa komissiyasi 9410; `bank_settlements.variance_amount` — f… | 27 |  |
| B4-T06 | ⬜ | Bank ko'chirmasi importi: `POST /bank-settlements/imports` (1CClientBankExchange `.txt` → `bank_settlements` qoralamalari, `source='statement_import'`) va BO-24 tranzit qoldig'i `GET /bank-settlements/transit-balances` (26 #124); parser testlari — pilot buxga… | 27 |  |
| B4-T07 | ⬜ | Soliq hisob-kitobi: `tax_settlements` (`ST`) — QQS hisobga olish `Dt 6410 / Kt 4410`, aylanma solig'i `Dt 9430 / Kt 6410`; soliq to'lovi `Dt 6410 / Kt 5110` (`expenses.tax_type`); `POST /tax-settlements`, `/{id}/post`, `/{id}/cancel` (`13` §2.26, §4.3) | 27 |  |
| B4-T08 | ⬜ | Qarz to'lovi: joriy qarzdan ortiq summa rad — online/REST (`debt_payment_exceeds_balance`, qaror #45); yetkazib beruvchiga ortiqcha to'lov — `supplier_overpay_policy` (qaror #47); hisobdan chiqarilgan qarzga to'lov `Kt 9390` | 27 |  |
| B4-T09 | ⬜ | M12 Egasi dashboard va asosiy hisobotlar; US-M03-03 chegirmalar margin hisoboti (Could) | 27 |  |
| B4-T10 | ⬜ | M18 Telegram bot: ulash va kunlik hisobot; M18 ogohlantirishlari, yaroqlilik muddati ogohlantirishi (M18) | 27 |  |
| B4-T11 | ⬜ | Filiallar bo'yicha va jami ko'rinish (US-M14-01, US-M04-03); kam qoldiq ogohlantirishi (US-M04-02) | 27 |  |

### Bosqich 4 — Tayyor ta'rifi (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B4-DoD-01 | ⬜ | QT-M08-01…17 yashil | 27 Tayyor ta'rifi |  |
| B4-DoD-02 | ⬜ | staging'da ichki demo-tenant bilan bir haftalik qarz daftari ssenariysi | 27 Tayyor ta'rifi |  |
| B4-DoD-03 | ⬜ | bank ko'chirmasi namunasi import qilinib 5710 tranzit qoldig'i yopiladi | 27 Tayyor ta'rifi |  |
| B4-DoD-04 | ⬜ | `16` §5 qarz limiti/balans konflikt qoidalari test bilan qoplangan (QT-M08-03, QT-M08-16, QT-M08-17) | 27 Tayyor ta'rifi |  |
| B4-DoD-05 | ⬜ | QT-M10-07 (`tax_settlements`) yashil | 27 Tayyor ta'rifi |  |
| B4-DoD-06 | ⬜ | `13` §2.13–§2.17, §2.18a, §2.26, §4.3 misollari avtomatik testlarda. | 27 Tayyor ta'rifi |  |

### Bosqich 4 — Hikoyalar (27 → 30)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B4-US-M03-03 | ⬜ | US-M03-03 — Chegirmalarning margin'ga ta'sirini hisobotda ko'rish | 27 Hikoyalar; 30 (Could) |  |
| B4-US-M04-02 | ⬜ | US-M04-02 — Minimal zaxira chegarasida ogohlantirish | 27 Hikoyalar; 30 (Should) |  |
| B4-US-M04-03 | ⬜ | US-M04-03 — Ko'p filial konsolidatsiyalangan qoldiq | 27 Hikoyalar; 30 (Should) |  |
| B4-US-M07-04 | ⬜ | US-M07-04 — Yetkazib beruvchiga kreditorlik qarzini to'lash | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M08-01 | ⬜ | US-M08-01 — Mijozga limit ichida nasiyaga sotish | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M08-02 | ⬜ | US-M08-02 — Mijoz kredit limitini belgilash/o'zgartirish | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M08-04 | ⬜ | US-M08-04 — Mijozning nasiya qarzini (qisman/to'liq) to'lashini qabul qilish | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M08-05 | ⬜ | US-M08-05 — Qarzga berishni 2–3 soniyada (offline) yozish | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M08-06 | ⬜ | US-M08-06 — Mijozning qarz daftarini qog'oz daftardek ko'rish | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M08-07 | ⬜ | US-M08-07 — Eski qog'oz daftardagi qarzlarni tizimga ko'chirish | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M08-09 | ⬜ | US-M08-09 — Qarzlarni o'z vaqtida qaytarib olish (va'da sanasi, eslatma) | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M08-10 | ⬜ | US-M08-10 — Qarzlar holatini bir qarashda ko'rish | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M08-11 | ⬜ | US-M08-11 — Yetkazib beruvchilarga qarzni ham daftar kabi yuritish | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M11-04 | ⬜ | US-M11-04 — Bank tushumi tasdig'i: yo'ldagi pul (5710) → bank (5110) + komissiya (qaror #42) | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M12-01 | ⬜ | US-M12-01 — Kunlik savdo hisoboti (umumiy va filial bo'yicha) | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M12-02 | ⬜ | US-M12-02 — Eng ko'p/kam sotiladigan tovarlar hisoboti | 27 Hikoyalar; 30 (Should) |  |
| B4-US-M14-01 | ⬜ | US-M14-01 — Barcha filiallar bo'yicha konsolidatsiyalangan ko'rinish | 27 Hikoyalar; 30 (Should) |  |
| B4-US-M15-01 | ⬜ | US-M15-01 — Xarajatni 10 soniyada yozish | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M15-02 | ⬜ | US-M15-02 — Doimiy xarajatlarni har oy qayta kiritmaslik | 27 Hikoyalar; 30 (Should) |  |
| B4-US-M15-03 | ⬜ | US-M15-03 — Haqiqiy sof foydani ko'rish | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M18-01 | ⬜ | US-M18-01 — Telegram akkauntini do'konga ulash | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M18-02 | ⬜ | US-M18-02 — Har kuni kechqurun qisqa hisobot | 27 Hikoyalar; 30 (Must) |  |
| B4-US-M18-03 | ⬜ | US-M18-03 — Muhim hodisalar haqida darhol xabar | 27 Hikoyalar; 30 (Should) |  |

### Bosqich 4 — Endpointlar (14/17/18/19/20/33)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B4-EP-18#18 | ⬜ | event counterparty.created | 18 §11.1; 30 (US API) |  |
| B4-EP-18#19 | ⬜ | GET /api/v1/counterparties/{id}/debt-ledger | 18 §12.1; 30 (US API) |  |
| B4-EP-18#21 | ⬜ | event debt_payment.created | 18 §12.2; qarz to'lovi — 27 B4 (US-M08-04); karta natijasi maydoni — B3 |  |
| B4-EP-18#22 | ⬜ | POST /api/v1/debt-payments → POST /{id}/post | 18 §12.3; 30 (US API) |  |
| B4-EP-18#23 | ⬜ | POST /api/v1/debt-openings → POST /{id}/post | 18 §12.4; 30 (US API) |  |
| B4-EP-18#24 | ⬜ | POST /api/v1/debt-writeoffs → POST /{id}/post | 18 §12.5; 27 vazifa matni |  |
| B4-EP-18#25 | ⬜ | GET /api/v1/debt-payments / GET /{id} / POST /{id}/cancel | 18 §12.5a; 30 (US API) |  |
| B4-EP-18#26 | ⬜ | GET /api/v1/debt-openings / GET /{id} / POST /{id}/cancel | 18 §12.5a; 30 (US API) |  |
| B4-EP-18#27 | ⬜ | GET /api/v1/debt-writeoffs / GET /{id} / POST /{id}/cancel | 18 §12.5a; 27 vazifa matni |  |
| B4-EP-18#28 | ⬜ | POST /api/v1/debt-doubtful-flags / POST /{id}/unflag | 18 §12.6; 27 (resurs) |  |
| B4-EP-18#29 | ⬜ | GET /api/v1/reports/debts-aging?direction=receivable | 18 §12.8; 30 (US API) |  |
| B4-EP-18#31 | ⬜ | event expense.created | 18 §13.2; 27 vazifa matni |  |
| B4-EP-19#50 | ⬜ | POST /supplier-payments | 19 §11; 30 (US API) |  |
| B4-EP-19#51 | ⬜ | POST /supplier-payments/{id}/cancel | 19 §11; 30 (resurs) |  |
| B4-EP-20#8a | ⬜ | GET /tax-settlements — Soliq hisob-kitobi hujjatlari (tax_settlements) ro'yxati | 20 indeks; 27 vazifa matni |  |
| B4-EP-20#8b | ⬜ | POST /tax-settlements — QQS hisobga olish / aylanma solig'i qoralamasi (server hisoblaydi) | 20 indeks; 27 vazifa matni |  |
| B4-EP-20#8c | ⬜ | POST /tax-settlements/{id}/post — O'tkazish (Dt 6410 / Kt 4410 yoki Dt 9430/9820 / Kt 641… | 20 indeks; 27 vazifa matni |  |
| B4-EP-20#8d | ⬜ | POST /tax-settlements/{id}/cancel — Bekor qilish (storno) | 20 indeks; 27 vazifa matni |  |
| B4-EP-20#12 | ⬜ | GET /reports/profit-and-loss — Foyda-zarar hisoboti | 20 indeks; 30 (US API) |  |
| B4-EP-20#17 | ⬜ | GET /reports/dashboard — Egasi/Menejer dashboard ma'lumoti | 20 indeks; 30 (US API) |  |
| B4-EP-20#18 | ⬜ | GET /reports/sales — Savdo hisoboti (filial/davr) | 20 indeks; 30 (US API) |  |
| B4-EP-20#19 | ⬜ | GET /reports/top-products — Eng ko'p/kam sotilgan tovarlar | 20 indeks; 30 (US API) |  |
| B4-EP-20#20 | ⬜ | GET /reports/stock — Qoldiq hisoboti | 20 indeks; 30 (US API) |  |
| B4-EP-20#21 | ⬜ | GET /reports/debts-aging — Qarzdorlik "yosh" guruhlari (0-30/31-60/60+) | 20 indeks; 30 (US API) |  |
| B4-EP-20#41 | ⬜ | GET /expenses — Xarajatlar ro'yxati | 20 indeks; 30 (US API) |  |
| B4-EP-20#42 | ⬜ | POST /expenses — Xarajat qoralamasi yaratish | 20 indeks; 30 (US API) |  |
| B4-EP-20#43 | ⬜ | POST /expenses/{id}/post — Xarajatni o'tkazish | 20 indeks; 30 (US API) |  |
| B4-EP-20#44 | ⬜ | POST /expenses/{id}/cancel — Xarajatni bekor qilish | 20 indeks; 30 (resurs) |  |
| B4-EP-20#45 | ⬜ | GET /expense-categories — Xarajat toifalari ro'yxati | 20 indeks; M15 xarajatlar — 27 B4 |  |
| B4-EP-20#46 | ⬜ | POST /expense-categories — Yangi toifa qo'shish | 20 indeks; M15 xarajatlar — 27 B4 |  |
| B4-EP-20#47 | ⬜ | PATCH /expense-categories/{id} — Toifani tahrirlash | 20 indeks; M15 xarajatlar — 27 B4 |  |
| B4-EP-20#48 | ⬜ | GET /recurring-expenses — Takrorlanuvchi xarajat qoidalari | 20 indeks; 30 (US API) |  |
| B4-EP-20#49 | ⬜ | POST /recurring-expenses — Yangi takrorlanuvchi qoida | 20 indeks; 30 (US API) |  |
| B4-EP-20#50 | ⬜ | PATCH /recurring-expenses/{id} — Qoidani tahrirlash | 20 indeks; 30 (katalog raqami) |  |
| B4-EP-20#51 | ⬜ | POST /recurring-expenses/{id}/confirm — Eslatmani tasdiqlab xarajat yaratish | 20 indeks; 30 (US API) |  |
| B4-EP-20#55a | ⬜ | GET /bank-settlements — Bank tushumi tasdiqlari ro'yxati | 20 indeks; 27 vazifa matni |  |
| B4-EP-20#55b | ⬜ | GET /bank-settlements/transit-balances — Yo'ldagi pul (5710) qoldig'i — filial × to'lov u… | 20 indeks; 27 vazifa matni |  |
| B4-EP-20#55c | ⬜ | POST /bank-settlements — Bank tushumi tasdig'i qoralamasini yaratish | 20 indeks; 27 vazifa matni |  |
| B4-EP-20#55d | ⬜ | GET /bank-settlements/{id} — Hujjat tafsiloti (provodkalar bilan) | 20 indeks; 30 (US API) |  |
| B4-EP-20#55e | ⬜ | POST /bank-settlements/{id}/post — O'tkazish: 5710 → 5110 + komissiya (9430 / inkassa — 9… | 20 indeks; 30 (US API) |  |
| B4-EP-20#55f | ⬜ | POST /bank-settlements/{id}/cancel — Bekor qilish (storno) | 20 indeks; 30 (US API) |  |
| B4-EP-20#55g | ⬜ | POST /bank-settlements/imports — Bank ko'chirmasini (1CClientBankExchange .txt) import qi… | 20 indeks; 27 vazifa matni |  |
| B4-EP-20#55h | ⬜ | PATCH /bank-settlements/{id} — Qoralamani tahrirlash | 20 indeks; 30 (US API) |  |
| B4-EP-20#66 | ⬜ | POST /notifications/telegram/link-start — Telegram ulash kodi generatsiya | 20 indeks; 30 (US API) |  |
| B4-EP-20#67 | ⬜ | GET /notifications/telegram/status — Ulanish holati | 20 indeks; 30 (resurs) |  |
| B4-EP-20#68 | ⬜ | DELETE /notifications/telegram/link — Ulanishni uzish | 20 indeks; 30 (resurs) |  |
| B4-EP-20#69 | ⬜ | GET /notification-settings — Ogohlantirish sozlamalari | 20 indeks; 30 (US API) |  |
| B4-EP-20#70 | ⬜ | PATCH /notification-settings — Sozlamalarni yangilash | 20 indeks; 30 (US API) |  |
| B4-EP-20#71 | ⬜ | GET /notifications-log — Yuborilgan xabarlar tarixi | 20 indeks; M18 bildirishnomalar — 27 B4 |  |

### Bosqich 4 — Ekranlar (06/07)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B4-SCR-BO-02 | 🟡 | BO-02 — Dashboard (Egasi/Menejer) | 07; 27/30 | maket-skelet `web/packages/pages/reports/src/pages/dashboard/` (qiymatlar '—'), test `model.test.ts`; `GET /reports/dashboard` yo'q |
| B4-SCR-BO-03 | ⬜ | BO-03 — Ombor qoldig'i (+ Ko'chirishlar tab) | 07; 27/30 |  |
| B4-SCR-BO-04 | ⬜ | BO-04 — Xaridnoma yaratish, yetkazib beruvchiga to'lov/qaytarish | 07; 27/30 |  |
| B4-SCR-BO-06 | ⬜ | BO-06 — Nasiya/qarzdorlar ro'yxati va eslatmalar | 07; 27/30 |  |
| B4-SCR-BO-09 | ⬜ | BO-09 — Hisobotlar markazi | 07; 27/30 |  |
| B4-SCR-BO-12 | ⬜ | BO-12 — Filiallar boshqaruvi | 07; 27/30 |  |
| B4-SCR-BO-16 | ⬜ | BO-16 — Tasdiqlash navbati (limitdan oshgan so'rovlar) | 07; 27/30 |  |
| B4-SCR-BO-17 | ⬜ | BO-17 — Xarajatlar | 07; 27/30 |  |
| B4-SCR-BO-20 | ⬜ | BO-20 — Telegram va bildirishnomalar | 07; 27/30 |  |
| B4-SCR-BO-21 | ⬜ | BO-21 — Ro'yxatdan o'tish va birinchi sozlash (onboarding wizard) | 07; 27/30 |  |
| B4-SCR-BO-24 | ⬜ | BO-24 — Bank tushumi tasdig'i (yo'ldagi pul → bank) | 07; 27/30 |  |
| B4-SCR-POS-03 | ⬜ | POS-03 — To'lov usuli va hisoblash | 07; 27/30 |  |
| B4-SCR-POS-06 | ⬜ | POS-06 — Nasiyaga sotish | 07; 27/30 |  |
| B4-SCR-POS-13 | ⬜ | POS-13 — Qarz daftari (tezkor) | 07; 27/30 |  |
| B4-SCR-POS-14 | ⬜ | POS-14 — Kassaga pul qo'yish / kassadan pul olish | 07; 27/30 |  |

### Bosqich 4 — Jadvallar / migratsiyalar (12)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B4-TBL-app.debt_doubtful_flags | 🟡 | `app.debt_doubtful_flags` (revizion 0006) | 12; 27 B4: `debt-doubtful-flags` | DDL 0006 bor; modul kodi/testi yo'q |
| B4-TBL-app.debt_openings | 🟡 | `app.debt_openings` (revizion 0017) | 12; 30 (US jadvallari) | DDL 0017 bor; modul kodi/testi yo'q |
| B4-TBL-app.debt_payment_allocations | 🟡 | `app.debt_payment_allocations` (revizion 0017) | 12; 30 (US jadvallari) | DDL 0017 bor; modul kodi/testi yo'q |
| B4-TBL-app.debt_writeoffs | 🟡 | `app.debt_writeoffs` (revizion 0017) | 12; 27 vazifa matni | DDL 0017 bor; modul kodi/testi yo'q |
| B4-TBL-app.supplier_payments | 🟡 | `app.supplier_payments` (revizion 0017) | 12; 27 vazifa matni | DDL 0017 bor; modul kodi/testi yo'q |
| B4-TBL-app.supplier_payment_allocations | 🟡 | `app.supplier_payment_allocations` (revizion 0017) | 12; 30 (US jadvallari) | DDL 0017 bor; modul kodi/testi yo'q |
| B4-TBL-app.recurring_expenses | 🟡 | `app.recurring_expenses` (revizion 0018) | 12; 30 (US jadvallari) | DDL 0018 bor; modul kodi/testi yo'q |
| B4-TBL-app.attachments | ✅ | `app.attachments` (revizion 0018) | 12; 30 (US jadvallari) | DDL 0018; kod va test: `backend/tests/integration/test_import_jobs.py` |
| B4-TBL-app.expenses | 🟡 | `app.expenses` (revizion 0018) | 12; 27 vazifa matni | DDL 0018 bor; modul kodi/testi yo'q |
| B4-TBL-app.bank_statement_imports | 🟡 | `app.bank_statement_imports` (revizion 0018) | 12; 27 B4: bank ko'chirmasi importi | DDL 0018 bor; modul kodi/testi yo'q |
| B4-TBL-app.bank_settlements | 🟡 | `app.bank_settlements` (revizion 0018) | 12; 27 vazifa matni | DDL 0018 bor; modul kodi/testi yo'q |
| B4-TBL-app.tax_settlements | 🟡 | `app.tax_settlements` (revizion 0018) | 12; 27 B4: `tax_settlements` | DDL 0018 bor; modul kodi/testi yo'q |
| B4-TBL-app.debt_moves | 🟡 | `app.debt_moves` (revizion 0015) | 12; 30 (US jadvallari) | DDL 0015 bor; modul kodi/testi yo'q |
| B4-TBL-app.debt_balances | 🟡 | `app.debt_balances` (revizion 0015) | 12; 30 (US jadvallari) | DDL 0015 bor; modul kodi/testi yo'q |
| B4-TBL-app.telegram_links | 🟡 | `app.telegram_links` (revizion 0023) | 12; 30 (US jadvallari) | DDL 0023 bor; modul kodi/testi yo'q |
| B4-TBL-app.notification_settings | 🟡 | `app.notification_settings` (revizion 0023) | 12; 30 (US jadvallari) | DDL 0023 bor; modul kodi/testi yo'q |
| B4-TBL-app.notifications_log | 🟡 | `app.notifications_log` (revizion 0023) | 12; 30 (US jadvallari) | DDL 0023 bor; modul kodi/testi yo'q |

### Bosqich 4 — Qabul testlari (31)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B4-QT-M03-03 | ⬜ | QT-M03-03 (happy) — Berilgan tanlangan davrda chegirmalar berilgan, qachonki Egasi hisobotni ochsa, unda berilgan chegirmalar summasi va shu sabab kamaygan margin ko'rsa… | 31; 31 US (US-M03-03) |  |
| B4-QT-M04-02 | ⬜ | QT-M04-02 (happy) — Berilgan tovar qoldig'i min_stockdan past, qachonki tizim kunlik tekshiruvni bajarsa, unda Menejerga M18 orqali ogohlantirish ketadi. | 31; 31 US (US-M04-02) |  |
| B4-QT-M04-03 | ⬜ | QT-M04-03 (happy) — Berilgan 2 filial mavjud, qachonki konsolidatsiyalangan hisobot ochilsa, unda har bir filial alohida va jami qoldiq ko'rsatiladi. | 31; 31 US (US-M04-03) |  |
| B4-QT-M07-05 | ⬜ | QT-M07-05 (happy) — Berilgan yetkazib beruvchiga kreditorlik "1120000.00" ochiq, qachonki Buxgalter "1120000.00" to'lov qilsa, unda ledger_entries: Dt 6010/Kt 5110="1120… | 31; 31 US (US-M07-04) |  |
| B4-QT-M08-01 | ⬜ | QT-M08-01 (happy) — Berilgan mijoz joriy qarzi "0.00", kredit limiti "500000.00", qachonki "300000.00"lik sotuv "nasiya" bilan yakunlansa, unda debt_moves(direction='rec… | 31; 27 (aniq havola) |  |
| B4-QT-M08-02 | ⬜ | QT-M08-02 (negative) — Berilgan mijoz joriy qarzi "450000.00", limit "500000.00", qachonki "100000.00"lik yangi nasiya (jami "550000.00" limitdan oshadi) so'ralsa online… | 31; 27 (aniq havola) |  |
| B4-QT-M08-03 | ⬜ | QT-M08-03 (negative (offline)) — Berilgan offline rejim, oxirgi ma'lum qoldiq bo'yicha limitdan oshib ketish aniqlangan, qachonki kassir baribir sotishni tanlasa, unda s… | 31; 27 (aniq havola) |  |
| B4-QT-M08-04 | ⬜ | QT-M08-04 (happy) — Berilgan Menejer mijoz limitini "500000.00"dan "800000.00"ga o'zgartiradi, qachonki saqlansa, unda yangi limit darhol kuchga kiradi va barcha kassala… | 31; 27 (aniq havola) |  |
| B4-QT-M08-05 | ⬜ | QT-M08-05 (happy) — Berilgan mijoz qarzi to'lov muddatidan o'tgan, qachonki tizim kunlik tekshirsa, unda AI-06 orqali tayyorlangan eslatma matni taklif qilinadi (odam ta… | 31; 27 (aniq havola) |  |
| B4-QT-M08-06 | ⬜ | QT-M08-06 (happy) — Berilgan mijoz qarzi "300000.00", qachonki "300000.00" naqd to'lasa, unda debt_moves(direction='receivable', amount=-300000.00), ledger_entries: Dt 5… | 31; 27 (aniq havola) |  |
| B4-QT-M08-07 | ⬜ | QT-M08-07 (negative (qisman)) — Berilgan mijoz qarzi "300000.00", qachonki "100000.00" qisman to'lasa, unda qoldiq qarz "200000.00" saqlanadi, debt_settlement cheki faqa… | 31; 27 (aniq havola) |  |
| B4-QT-M08-08 | ⬜ | QT-M08-08 (happy) — Berilgan mijoz ro'yxatda yo'q, qachonki Kassir POS'da "Qarzga" tugmasi bilan faqat ism+telefon kiritib yangi mijoz yaratsa, unda 2-3 soniyada sotuv m… | 31; 27 (aniq havola) |  |
| B4-QT-M08-09 | ⬜ | QT-M08-09 (happy) — Berilgan mijozda bir nechta qarz/to'lov yozuvi, qachonki "Qarz daftari" ochilsa, unda sana bo'yicha har bir qarz (summa, tovarlar, kim berdi) va jori… | 31; 27 (aniq havola) |  |
| B4-QT-M08-10 | ⬜ | QT-M08-10 (happy) — Berilgan yangi tenant, qachonki Egasi "Boshlang'ich qarzlar" orqali mijoz uchun "150000.00" kiritsa, unda debt_openings → ledger_entries: Dt 4010/Kt… | 31; 27 (aniq havola) |  |
| B4-QT-M08-11 | ⬜ | QT-M08-11 (happy) — Berilgan mijozning 2 ochiq qarzi (eski — "100000.00", yangi — "200000.00"), qachonki "100000.00" to'lov kelsa, unda summa eng eski qarzdan boshlab yo… | 31; 27 (aniq havola) |  |
| B4-QT-M08-12 | ⬜ | QT-M08-12 (negative) — Berilgan mijoz qarzi 65 kun davomida to'lanmagan, qachonki kunlik tekshiruv ishga tushsa, unda 60+ kunlik ro'yxatga tushadi va Egasiga faqat eslat… | 31; 27 (aniq havola) |  |
| B4-QT-M08-13 | ⬜ | QT-M08-13 (happy (writeoff)) — Berilgan Egasi qarzni sabab bilan "kechirish" qiladi ("150000.00"), qachonki debt_writeoffs post qilinsa, unda ledger_entries: Dt 9430 (yo… | 31; 27 (aniq havola) |  |
| B4-QT-M08-14 | ⬜ | QT-M08-14 (happy) — Berilgan yetkazib beruvchidan nasiyaga xarid qilingan, qachonki Egasi "Men qarzdorman" daftarini ochsa, unda kimga/qancha/qachon to'lash ko'rinadi; t… | 31; 27 (aniq havola) |  |
| B4-QT-M08-15 | ⬜ | QT-M08-15 (negative (ortiqcha to'lov)) — Berilgan mijoz joriy qarzi "300000.00", qachonki "350000.00" qarz to'lovi yuborilsa, unda 422 VALIDATION_ERROR, message_key=debt… | 31; 27 (aniq havola) |  |
| B4-QT-M08-16 | ⬜ | QT-M08-16 (happy (offline allokatsiya, chek qatorl…) — Berilgan mijozda ikki ochiq sotuv — A "300000.00" (due_date erta) va B "200000.00", qurilma lokal customers.open_d… | 31; 27 (aniq havola) |  |
| B4-QT-M08-17 | ⬜ | QT-M08-17 (happy (offline ortiqcha to'lov)) — Berilgan mijoz qarzi "300000.00" (hisobdan chiqarilgan qarz yo'q), qachonki offline (is_offline=true) naqd qarz to'lovi "35… | 31; 27 (aniq havola) |  |
| B4-QT-M08-18 | ⬜ | QT-M08-18 (negative (back-office qarz to'lovi)) — Berilgan mijoz qarzi "300000.00", qachonki back-office POST /debt-payments method='cash' bilan chaqirilsa, unda 422 VAL… | 31; 31 US (US-M08-04) |  |
| B4-QT-M10-07 | ⬜ | QT-M10-07 (happy (QQS hisobga olish, §2.26)) — Berilgan oy davomida chiquvchi QQS (Kt 6410) jami "120000.00", kiruvchi QQS (Dt 4410) jami "84000.00", qachonki Buxgalter… | 31; 27 (aniq havola) |  |
| B4-QT-M11-07 | ⬜ | QT-M11-07 (happy (5710 → 5110, qaror #42)) — Berilgan filialda kecha karta bilan "1000000.00" sotuv va "50000.00" kartaga qaytarish bo'lgan — 5710 (payment_method='card'… | 31; 27 (aniq havola) |  |
| B4-QT-M11-08 | ⬜ | QT-M11-08 (negative (ruxsat, validatsiya)) — Berilgan Kassir (bank_settlements.manage yo'q), qachonki POST /bank-settlements chaqirsa, unda 403 PERMISSION_DENIED; Berilg… | 31; 31 US (US-M11-04) |  |
| B4-QT-M11-09 | ⬜ | QT-M11-09 (happy (tranzit qoldiq)) — Berilgan QT-M11-07 dagi holat, bank_settlements hali yaratilmagan, qachonki GET /bank-settlements/transit-balances so'ralsa, unda it… | 31; 31 US (US-M11-04) |  |
| B4-QT-M11-10 | ⬜ | QT-M11-10 (happy (ko'chirma importi)) — Berilgan 5710 (card) qoldig'i "950000.00", qachonki Buxgalter POST /bank-settlements/imports ga ekvayerdan "940500.00" kirim qato… | 31; 31 US (US-M11-04) |  |
| B4-QT-M11-11 | ⬜ | QT-M11-11 (negative (ko'chirma fayli)) — Berilgan birinchi qatori 1CClientBankExchange bo'lmagan fayl, qachonki import qilinsa, unda 422 BANK_IMPORT_FILE_INVALID (params… | 31; 31 US (US-M11-04) |  |
| B4-QT-M11-13 | ⬜ | QT-M11-13 (happy (inkassa)) — Berilgan smenada cash_movements(reason='collection', direction='out', amount="2000000.00") o'tkazilgan (Dt 5710 / Kt 5010 = "2000000.00", a… | 31; 31 US (US-M11-04) |  |
| B4-QT-M11-15 | ⬜ | QT-M11-15 (happy (rrn bo'yicha moslashtirish, qaro…) — Berilgan kecha 3 ta integratsiyalangan karta xaridi (rrn R1 "500000.00", R2 "300000.00", R3 "150000.00", jami "950… | 31; 31 US (US-M11-04) |  |
| B4-QT-M12-01 | ⬜ | QT-M12-01 (happy) — Berilgan kun davomida 2 filialda savdo bo'lgan, qachonki Egasi kunlik hisobotni ochsa, unda jami savdo, chek soni, o'rtacha chek summasi filial bo'yi… | 31; 31 US (US-M12-01) |  |
| B4-QT-M12-02 | ⬜ | QT-M12-02 (happy) — Berilgan tanlangan davr, qachonki Menejer hisobot so'rasa, unda tovarlar sotuv miqdori bo'yicha kamayish tartibida ro'yxatlanadi. | 31; 31 US (US-M12-02) |  |
| B4-QT-M12-04 | ⬜ | QT-M12-04 (negative) — Berilgan ba'zi offline qurilmalar hali sinxronlanmagan, qachonki Egasi hisobotni ochsa, unda "faqat sinxronlangan ma'lumot" ogohlantirishi ko'rsat… | 31; 31 US (US-M12-01) |  |
| B4-QT-M14-01 | ⬜ | QT-M14-01 (happy) — Berilgan 2 filial mavjud, qachonki Egasi umumiy dashboard'ni ochsa, unda har bir filial alohida va jami ko'rinishda ko'rsatiladi. | 31; 31 US (US-M14-01) |  |
| B4-QT-M15-01 | ⬜ | QT-M15-01 (happy) — Berilgan "Xarajat qo'shish" ochilgan, qachonki summa "500000.00", toifa "Ijara — savdo zali" (rent_store, default_account=9410), manba "kassa naqdi"… | 31; 31 US (US-M15-01) |  |
| B4-QT-M15-02 | ⬜ | QT-M15-02 (happy) — Berilgan oylik ijara takrorlanuvchi xarajat sifatida sozlangan, qachonki muddat kelsa, unda "Ijara to'lash vaqti: 3 000 000 so'm" eslatmasi beriladi,… | 31; 31 US (US-M15-02) |  |
| B4-QT-M15-03 | ⬜ | QT-M15-03 (happy) — Berilgan davr tanlangan, sotuv tushumi, COGS va xarajatlar ma'lum, qachonki dashboard ochilsa, unda Sof foyda = Sotuv tushumi − COGS − Xarajatlar for… | 31; 31 US (US-M15-03) |  |
| B4-QT-M15-04 | ⬜ | QT-M15-04 (negative) — Berilgan xarajat allaqachon post qilingan, qachonki Egasi uni "bekor qilsa", unda yozuv o'chirilmaydi — teskari (storno) yozuv bilan bekor qilinad… | 31; 31 US (US-M15-01) |  |
| B4-QT-M15-05 | ⬜ | QT-M15-05 (negative (limit)) — Berilgan xarajat summasi Menejer uchun belgilangan expenses.approve.limit_valuedan katta, qachonki POST /expenses/{id}/post chaqirilsa, un… | 31; 31 US (US-M15-01) |  |
| B4-QT-M15-06 | ⬜ | QT-M15-06 (happy (soliq to'lovi)) — Berilgan toifa tax_payment (default_account='6410'), qachonki tax_typesiz xarajat yaratilsa, unda 422 VALIDATION_ERROR; qachonki tax_… | 31; 31 US (US-M15-01) |  |
| B4-QT-M18-01 | ⬜ | QT-M18-01 (happy) — Berilgan back-office'da "Telegram ulash" bosilgan, qachonki Egasi bot havolasini ochib "Start" bossa, unda akkaunt bir martalik kod orqali tenantga b… | 31; 31 US (US-M18-01) |  |
| B4-QT-M18-02 | ⬜ | QT-M18-02 (happy) — Berilgan kun yopilgan, qachonki belgilangan soat kelsa, unda bot kechqurungi hisobotni yuboradi: bugungi savdo, sof foyda (M15), naqd (M16), yangi/qa… | 31; 31 US (US-M18-02) |  |
| B4-QT-M18-03 | ⬜ | QT-M18-03 (happy) — Berilgan smena yopilganda kassa farqi topilgan (M16), qachonki shu hodisa bo'lsa, unda Egasiga darhol Telegram xabari ketadi (yoqilgan bo'lsa). | 31; 31 US (US-M18-03) |  |
| B4-QT-M18-05 | ⬜ | QT-M18-05 (negative) — Berilgan xodim Telegram'ga ulangan, keyin Egasi uni tizimdan o'chiradi, qachonki o'chirish amalga oshsa, unda uning Telegram ulanishi ham bekor qi… | 31; 31 US (US-M18-01) |  |
| B4-QT-M18-06 | ⬜ | QT-M18-06 (happy (ogohlantirish yoqish/o'chirish)) — Berilgan Egasi "kam qolgan tovar" ogohlantirishini notification-settingsda o'chirgan, qachonki P1 qoldig'i minimal c… | 31; 31 US (US-M18-03) |  |

## Bosqich 5: fiskal va e-faktura

**Maqsad (27):** Har bir sotuv fiskal talablarga mos chek chiqaradi, markirovkalangan tovar tekshiriladi, e-faktura oqimi (kiruvchi va chiquvchi) ishlaydi.

Holat: ✅ 0 · 🟡 8 · ⬜ 118 · ⛔ 1 · ⏭ 0 · jami 127

### Bosqich 5 — Vazifalar (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B5-T01 | ⬜ | Do'kon agenti asosi (qaror #60, `34-1c-agent.md` asosida): .NET Fx 4.8 tray-ilova, admin huquqisiz o'rnatish, qurilma ulash (`devices.kind`), `127.0.0.1` lokal API, imzoli avto-yangilanish; Authenticode OV imzosi (26 #105) — pilot tarqatishdan oldin; OAuth `o…` | 27 |  |
| B5-T02 | ⬜ | Fiskal adapterlar `FiscalPort` ortida: (a) Do'kon ko'prigi — `multikassa_local` / `fiscaldrive_local` (POS → agent → FM → OFD); (b) hamkor bulut API — hamkorda bo'lsa (iOS yo'li, qaror #21); `FakeFiscalAdapter` + FM emulyatori CI'da; FM javobi — `fm_terminal_…` | 27 |  |
| B5-T03 | ⬜ | Agentda xom TCP 9100 printer (`print.raw`); tarozi PLU yuklash — MVP'dan keyin (MVP'da PLU CSV eksport); jonli og'irlik — Web Serial, MVP'dan keyin | 27 |  |
| B5-T04 | ⬜ | Agentning karta terminali imkoniyati (qaror #71, `34` §14.4): `capabilities.card_terminal`, lokal API `/v1/card/*` (`21` §16.1), `Erp1C.CardTerminal` — `ICardTerminalDriver` plug-in modeli, `DeviceLane` FIFO, `card_journal` (faqat niqob), faqat ro'yxatdagi xu… | 27 |  |
| B5-T05 | ⛔ | Birinchi real karta terminali drayveri — birinchi imzolangan hamkor bilan (Rahmat/Humo Sunmi P3 yoki ERA PAX A930; 26 #172–#174): drayver + vendor xato kodlari xaritasi, test qurilmada qabul testi; vendor onlayn-kassasi o'chiq/faqat to'lov rejimi tekshiruvi.… | 27 | 26 #172–#174 — vendor shartnomasi |
| B5-T06 | ⬜ | CRPT Turon (qaror #62): `MarkingPort` — qabul (M07 kirim kodlari), `verify_code`, yetkazib beruvchiga qaytarish, hisobdan chiqarish; tenant sirri `crpt_api_key`; `FakeMarkingAdapter` (GS1 parse); real adapter — Xat 2 javobidan keyin (26 #40) | 27 |  |
| B5-T07 | ⬜ | E-faktura — Faktura.uz (`EInvoicePort`, do'kon login/secret `tenant_secrets` da shifrlangan) + E-IMZO brauzerda imzolash (yagona `sign.<domen>`, prod API-KEY — 26 #118); kiruvchi faktura — poll → kirim; `risk_flag='unknown'` standart (26 #47); yetkazib beruvc… | 27 |  |
| B5-T08 | ⬜ | E-TTN (qaror #63): o'z filiallari orasidagi ko'chirishda ham — `transfers` `post` → `ettn_documents` EDO operatori orqali yuboriladi; markirovkali tovar egalik o'tishida muddat tovar guruhi bo'yicha (72 soat / 3 ish kuni); e-TTN ekran amallari — BO-03, BO-15,… | 27 |  |
| B5-T09 | ⬜ | E-ishonchnoma — do'kon o'z xodimiga e-faktura operatori orqali beradi (BP-01 1a; qaror #63): `powers_of_attorney`, `POST /powers-of-attorney` + E-IMZO, `outbox_jobs(kind='poa_send')` (`12` `powers_of_attorney`, `19` §8a) | 27 |  |
| B5-T10 | ⬜ | M10 ichki QQS registri, qizil faktura bo'yicha QQS krediti faqat to'lovdan keyin (US-M07-04 ikkinchi mezoni, US-M10-03 — kutilayotgan QQS krediti, BO-07/BO-10) | 27 |  |
| B5-T11 | ⬜ | M11 buxgalteriya hisobotlari (tasdiqlangan hisoblar rejasi bilan, 4910-hisob shubhali qarz zahirasi) | 27 |  |
| B5-T12 | ⬜ | Davr yopish (US-M11-02): yopilgan davrga kech POS voqealari, readiness `devices_unsynced`/`warnings`, `PERIOD_CLOSE_OUT_OF_ORDER` (qaror #69) | 27 |  |
| B5-T13 | ⬜ | Qo'lda buxgalteriya tuzatishi: `ledger_adjustments` hujjat jadvali (`12` §2.6) + `ledger_entries.branch_id` (`12` §2.7); `POST /ledger-adjustments` (bir bosqichli, darhol `posted`), `POST /ledger-adjustments/{id}/cancel`, `GET /ledger-adjustments` — faqat jor… | 27 |  |
| B5-T14 | ⬜ | Chiquvchi e-faktura (US-M01-06, BP-13/BP-03): `einvoice.create` ruxsati, `POST /api/v1/einvoices` (`direction=out`, B2B nasiya sotuvdan server avtomatik `draft`) va `POST /api/v1/einvoices/from-receipt` (BO-15 "Chek asosida e-faktura chiqarish" tugmasi); `ein…` | 27 |  |

### Bosqich 5 — Tayyor ta'rifi (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B5-DoD-01 | ⬜ | majburiy — CI'da FM emulyatori va `FakeMarkingAdapter` bilan QT-M01-18, QT-M01-20, QT-M01-21, QT-M01-23, QT-OFFLINE48-05 yashil | 27 Tayyor ta'rifi |  |
| B5-DoD-02 | ⬜ | karta terminali drayver emulyatori bilan agent orqali `purchase`/`void`/`settlement` va internetsiz integratsiyalangan karta testlari yashil | 27 Tayyor ta'rifi |  |
| B5-DoD-03 | ⬜ | US-M01-06, US-M11-02, US-M10-03, `ledger_adjustments`, e-ishonchnoma qabul mezonlari testlangan | 27 Tayyor ta'rifi |  |
| B5-DoD-04 | ⬜ | `13` §2.22, §2.23, §5.1, §5.5 misollari avtomatik testlarda. Real hamkor/CRPT test muhitida — 26 #109/#40 javobidan keyin: chek Do'kon agenti (yoki hamkor bulut API) orqali fiskallashadi, QR `ofd.soliq.uz/check` formatida | 27 Tayyor ta'rifi |  |
| B5-DoD-05 | ⬜ | tarmoq uzilganda FM imzolaydi, `resend`dan keyin `ofd_acked_at` yoziladi | 27 Tayyor ta'rifi |  |
| B5-DoD-06 | ⬜ | kiruvchi e-faktura (Faktura.uz) qabul qilinib imzolanadi | 27 Tayyor ta'rifi |  |
| B5-DoD-07 | ⬜ | ichki ko'chirish e-TTN bilan yuboriladi | 27 Tayyor ta'rifi |  |
| B5-DoD-08 | ⬜ | markirovkali kirim kodlari CRPT bilan qabul qilinadi. | 27 Tayyor ta'rifi |  |

### Bosqich 5 — Hikoyalar (27 → 30)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B5-US-M01-03 | ⬜ | US-M01-03 — Markirovkalangan tovar kodini tekshirish | 27 Hikoyalar; 30 (Must) |  |
| B5-US-M01-06 | ⬜ | US-M01-06 — Chekdan keyin chiquvchi e-faktura (B2B) | 27 Hikoyalar; 30 (Must) |  |
| B5-US-M01-08 | ⬜ | US-M01-08 — Integratsiyalangan karta terminali: summa terminalga, natija avtomatik; terminalsiz karta (rekvizitsiz) zaxirasi siyosat bo'yicha — faqat faol term… | 27 Hikoyalar; 30 (Must) |  |
| B5-US-M07-03 | ⬜ | US-M07-03 — Yetkazib beruvchi e-fakturasini kiritib QQS kreditini hisoblash | 27 Hikoyalar; 30 (Must) |  |
| B5-US-M10-03 | ⬜ | US-M10-03 — Yuqori xavfli ("qizil") fakturalarning QQS kreditiga ta'siri | 27 Hikoyalar; 30 (Should) |  |
| B5-US-M11-02 | ⬜ | US-M11-02 — Oy yakunida balans va daromad-xarajat hisoboti | 27 Hikoyalar; 30 (Must) |  |
| B5-US-M11-03 | ⬜ | US-M11-03 — Asosiy moliyaviy ko'rsatkichlarni sodda ko'rinishda ko'rish | 27 Hikoyalar; 30 (Should) |  |

### Bosqich 5 — Endpointlar (14/17/18/19/20/33)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B5-EP-14#5 | ⬜ | POST /oauth/device_authorization | 14 §20; 27 B5: `/oauth/device_authorization` |  |
| B5-EP-18#35 | ⬜ | GET /api/v1/einvoices?direction=out / POST /einvoices / POST /einvoices/from-receipt / si… | 18 §14a; 27 vazifa matni |  |
| B5-EP-18#36 | ⬜ | POST /api/v1/marking-codes/verify | 18 §15; 30 (US API) |  |
| B5-EP-18#37 | ⬜ | POST /api/v1/payments/checkouts | 18 §16.2; dinamik UzQR/Click/Payme checkout — 30 US-M01-05 (5 — dinamik, 26 #49) |  |
| B5-EP-18#38 | ⬜ | GET /api/v1/payments/checkouts/{checkout_ref} | 18 §16.3; dinamik UzQR — 30 US-M01-05 |  |
| B5-EP-18#39 | ⬜ | POST /api/v1/payments/webhooks/{provider} | 18 §16.4; dinamik UzQR — 30 US-M01-05 |  |
| B5-EP-18#L | ⬜ | Agent lokal API GET/POST http://127.0.0.1:47110/v1/card/* | 18 §16a.2; agent lokal API `/v1/card/*` — 27 B5 |  |
| B5-EP-19#30 | ⬜ | POST /goods-receipts/from-einvoice/{einvoice_id} | 19 §8; 30 (US API) |  |
| B5-EP-19#34 | ⬜ | POST /powers-of-attorney | 19 §8a; 27 vazifa matni |  |
| B5-EP-19#35 | ⬜ | GET /powers-of-attorney · GET /powers-of-attorney/{id} | 19 §8a; 27 vazifa matni |  |
| B5-EP-19#36 | ⬜ | POST /powers-of-attorney/{id}/sign-challenge | 19 §8a; 27 (resurs) |  |
| B5-EP-19#37 | ⬜ | POST /powers-of-attorney/{id}/submit-signed | 19 §8a; 27 (resurs) |  |
| B5-EP-19#38 | ⬜ | POST /powers-of-attorney/{id}/cancel | 19 §8a; 27 (resurs) |  |
| B5-EP-19#77 | ⬜ | GET /stock-settings/plu-export | 19 §17; 27 B5: MVP'da PLU CSV eksport |  |
| B5-EP-19#81 | ⬜ | GET /einvoices?direction=in&status=&risk_flag=&cursor=&limit= | 19 §19; 27 vazifa matni |  |
| B5-EP-19#82 | ⬜ | GET /einvoices/{id} | 19 §19; 27 (resurs) |  |
| B5-EP-19#83 | ⬜ | PATCH /einvoices/{id}/risk-flag | 19 §19; 27 (resurs) |  |
| B5-EP-19#84 | ⬜ | POST /einvoices/{id}/accept | 19 §19; 30 (US API) |  |
| B5-EP-19#85 | ⬜ | POST /einvoices/{id}/reject | 19 §19; 27 (resurs) |  |
| B5-EP-19#86 | ⬜ | POST /einvoices/{id}/sign-challenge | 19 §19; 27 (resurs) |  |
| B5-EP-19#87 | ⬜ | POST /einvoices/{id}/submit-signed | 19 §19; 27 (resurs) |  |
| B5-EP-19#88 | ⬜ | GET /ettn-documents?direction=&status=&transfer_id=&cursor=&limit= · GET /ettn-documents/… | 19 §20; 27 B5: e-TTN EDO operatori orqali (B2 da faqat qoralama, `FakeEInvoiceAdapter`) |  |
| B5-EP-19#89 | ⬜ | POST /ettn-documents/{id}/sign-challenge · POST /ettn-documents/{id}/submit-signed | 19 §20; 27 B5: e-TTN + E-IMZO |  |
| B5-EP-19#90 | ⬜ | POST /ettn-documents/{id}/register-manual | 19 §20; 27 B5: e-TTN |  |
| B5-EP-19#91 | ⬜ | POST /ettn-documents/{id}/accept · POST /ettn-documents/{id}/reject | 19 §20; 27 B5: e-TTN |  |
| B5-EP-20#10 | ⬜ | POST /ledger-adjustments — Qo'lda tuzatuvchi yozuv (joriy ochiq davr, bir bosqichli hujja… | 20 indeks; 27 vazifa matni |  |
| B5-EP-20#10a | ⬜ | POST /ledger-adjustments/{id}/cancel — Tuzatuvchi yozuvni bekor qilish | 20 indeks; 27 vazifa matni |  |
| B5-EP-20#10b | ⬜ | GET /ledger-adjustments — Tuzatuvchi yozuvlar ro'yxati | 20 indeks; 27 vazifa matni |  |
| B5-EP-20#11 | ⬜ | GET /reports/trial-balance — Aylanma-saldo vedomosti | 20 indeks; 30 (US API) |  |
| B5-EP-20#13 | ⬜ | GET /reports/balance-sheet — Balans hisoboti | 20 indeks; 30 (katalog raqami) |  |
| B5-EP-20#14 | ⬜ | GET /period-closings — Yopilgan davrlar ro'yxati | 20 indeks; 30 (US API) |  |
| B5-EP-20#15 | ⬜ | POST /period-closings — Davrni yopish | 20 indeks; 30 (US API) |  |
| B5-EP-20#16 | ⬜ | GET /period-closings/{period}/readiness — Yopishga tayyormi (recost, fiskal, qurilma sinx… | 20 indeks; 30 (katalog raqami) |  |
| B5-EP-20#40d | ⬜ | PUT /tenant/integrations/{provider} — Integratsiya kalitlari (Faktura.uz, CRPT, Click/Pay… | 20 indeks; integratsiya kalitlari (Faktura.uz, CRPT) — 27 B5 |  |
| B5-EP-20#40e | ⬜ | DELETE /tenant/integrations/{provider} — Integratsiyani uzish | 20 indeks; integratsiya kalitlari — 27 B5 |  |
| B5-EP-33W-01 | ⬜ | GET /onec-agents — Agentlar ro'yxati | 33 §10; 27 (katalog raqami) |  |
| B5-EP-33W-02 | ⬜ | GET /onec-agents/{id} — Agent tafsiloti | 33 §10; 27 (katalog raqami) |  |
| B5-EP-33W-03 | ⬜ | GET /onec-agents/pairing-requests/{user_code} — Ulash kodi bo'yicha PK ma'lumoti | 33 §10; 27 (katalog raqami) |  |
| B5-EP-33W-04 | ⬜ | POST /onec-agents/pair; rad etish varianti — POST /onec-agents/pairing-requests/{user_cod… | 33 §10; 27 (katalog raqami) |  |
| B5-EP-33W-05 | ⬜ | POST /onec-agents/{id}/revoke — Agentni uzish | 33 §10; 27 (katalog raqami) |  |
| B5-EP-33W-07 | ⬜ | POST /onec-agents/{id}/diagnostics-requests — Diagnostika paketini so'rash | 33 §10; 27 (katalog raqami) |  |
| B5-EP-33W-08 | ⬜ | GET /onec-agents/{id}/logs — Agent loglari | 33 §10; 27 (katalog raqami) |  |
| B5-EP-33A-01 | ⬜ | /onec-agent/hello (A-01) | 33 §9.3; 27 (katalog raqami) |  |
| B5-EP-33A-03 | ⬜ | /onec-agent/poll (A-03) | 33 §9.3; 27 (katalog raqami) |  |
| B5-EP-33A-04 | ⬜ | /onec-agent/heartbeat (A-04) | 33 §9.3; 27 (katalog raqami) |  |
| B5-EP-33A-05 | ⬜ | /onec-agent/result (A-05) | 33 §9.3; 27 (katalog raqami) |  |
| B5-EP-33A-06 | ⬜ | /onec-agent/logs (A-06) | 33 §9.3; 27 (katalog raqami) |  |
| B5-EP-33A-07 | ⬜ | /onec-agent/diagnostics (A-07) | 33 §9.3; 27 (katalog raqami) |  |
| B5-EP-33A-08 | ⬜ | /onec-agent/task-keys (A-08) | 33 §9.3; 27 (katalog raqami) |  |
| B5-EP-33A-09 | ⬜ | /onec-agent/update-manifest (A-09) | 33 §9.3; 27 (katalog raqami) |  |
| B5-EP-33A-10 | ⬜ | /onec-agent/unpair (A-10) | 33 §9.3; 27 (katalog raqami) |  |

### Bosqich 5 — Ekranlar (06/07)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B5-SCR-BO-02 | 🟡 | BO-02 — Dashboard (Egasi/Menejer) | 07; 27/30 | skelet bor (B4 qatoriga qarang) |
| B5-SCR-BO-03 | ⬜ | BO-03 — Ombor qoldig'i (+ Ko'chirishlar tab) | 07; 27/30 |  |
| B5-SCR-BO-04 | ⬜ | BO-04 — Xaridnoma yaratish, yetkazib beruvchiga to'lov/qaytarish | 07; 27/30 |  |
| B5-SCR-BO-07 | ⬜ | BO-07 — QQS ichki hisob-kitobi | 07; 27/30 |  |
| B5-SCR-BO-08 | ⬜ | BO-08 — Buxgalteriya jurnali, provodkalar | 07; 27/30 |  |
| B5-SCR-BO-10 | ⬜ | BO-10 — Davlat hisobotini ichki hisob bilan solishtirish | 07; 27/30 |  |
| B5-SCR-BO-12 | ⬜ | BO-12 — Filiallar boshqaruvi | 07; 27/30 |  |
| B5-SCR-BO-14 | ⬜ | BO-14 — Tenant/do'kon sozlamalari | 07; 27/30 |  |
| B5-SCR-BO-15 | ⬜ | BO-15 — Kiruvchi va chiquvchi e-faktura markazi | 07; 27/30 |  |
| B5-SCR-BO-24 | ⬜ | BO-24 — Bank tushumi tasdig'i (yo'ldagi pul → bank) | 07; 27/30 |  |
| B5-SCR-POS-02 | ⬜ | POS-02 — Sotish paneli (asosiy chek) | 07; 27/30 |  |
| B5-SCR-POS-03 | ⬜ | POS-03 — To'lov usuli va hisoblash | 07; 27/30 |  |
| B5-SCR-POS-06 | ⬜ | POS-06 — Nasiyaga sotish | 07; 27/30 |  |
| B5-SCR-POS-09 | ⬜ | POS-09 — Omborlar orasida tovar ko'chirish | 07; 27/30 |  |
| B5-SCR-POS-16 | ⬜ | POS-16 — Uskunalar sozlamasi (printer, skaner, tarozi) | 07; 27/30 |  |

### Bosqich 5 — Jadvallar / migratsiyalar (12)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B5-TBL-platform.marking_product_groups | 🟡 | `platform.marking_product_groups` (revizion 0004) | 12; 27 B5: markirovka (qaror #63) | DDL 0004 bor; ilova kodi bor, test yo'q |
| B5-TBL-app.ledger_adjustments | 🟡 | `app.ledger_adjustments` (revizion 0016) | 12; 27 vazifa matni | DDL 0016 bor; modul kodi/testi yo'q |
| B5-TBL-app.marking_codes | 🟡 | `app.marking_codes` (revizion 0020) | 12; 30 (US jadvallari) | DDL 0020 bor; modul kodi/testi yo'q |
| B5-TBL-app.einvoices | 🟡 | `app.einvoices` (revizion 0020) | 12; 27 B5: e-faktura (B2 dagi `factura_type` — faqat ustun) | DDL 0020 bor; modul kodi/testi yo'q |
| B5-TBL-app.powers_of_attorney | 🟡 | `app.powers_of_attorney` (revizion 0020) | 12; 27 vazifa matni | DDL 0020 bor; modul kodi/testi yo'q |
| B5-TBL-app.tenant_secrets | 🟡 | `app.tenant_secrets` (revizion 0022) | 12; 27 vazifa matni; ko'chirildi B0 → B5: yozish yo'li — integratsiya kalitlari `20` #40d/#40e (Faktura.uz, CRPT, UzQR — 27 B5); B0 da DDL va envelope shifrlash (`core/secrets.py`), B1 da BO-14 faqat holatini o'qiydi | DDL 0022 bor; ilova kodi bor, test yo'q |
| B5-TBL-app.period_closings | 🟡 | `app.period_closings` (revizion 0024) | 12; 30 (US jadvallari) | DDL 0024 bor; modul kodi/testi yo'q |
| B5-TBL-app.onec_agents | ⬜ | `app.onec_agents` (revizion 0028) | 12; 12 §6.1 — 0028 store_agent (27 B5) | DDL migratsiyasi (0028) hali yo'q |
| B5-TBL-app.onec_agent_tasks | ⬜ | `app.onec_agent_tasks` (revizion 0028) | 12; 12 §6.1 — 0028 store_agent (27 B5) | DDL migratsiyasi (0028) hali yo'q |
| B5-TBL-app.onec_task_results | ⬜ | `app.onec_task_results` (revizion 0028) | 12; 12 §6.1 — 0028 store_agent (27 B5) | DDL migratsiyasi (0028) hali yo'q |
| B5-TBL-auth.onec_device_authorizations | ⬜ | `auth.onec_device_authorizations` (revizion 0028) | 12; 12 §6.1 — 0028 store_agent (27 B5) | DDL migratsiyasi (0028) hali yo'q |

### Bosqich 5 — Qabul testlari (31)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B5-QT-OFFLINE48-05 | ⬜ | QT-OFFLINE48-05 (integration) — Berilgan cash_registers.fm_state='locked' (fiskal modul o'zi bloklangan, FakeFiscalAdapter emulyatsiyasi), qachonki sotuv yaratilsa, unda… | 31; 27 (aniq havola) |  |
| B5-QT-M01-04 | ⬜ | QT-M01-04 (happy) — Berilgan offline, "Hayot suvi 1.5L" (is_marked=true) narxi qurilmada keshlangan, qachonki DataMatrix kodi skanerlansa, unda sotuv ruxsat etiladi — ko… | 31; 31 US (US-M01-03) |  |
| B5-QT-M01-05 | ⬜ | QT-M01-05 (negative) — Berilgan offline, markirovkalangan tovar narxi qurilmada noma'lum, qachonki kod skanerlansa, unda sotuv taqiqlanadi (16-offline-sync.md §7). | 31; 31 US (US-M01-03) |  |
| B5-QT-M01-09 | ⬜ | QT-M01-09 (happy) — Berilgan avval oddiy chek bilan sotilgan tovar (B2C), qachonki mijoz keyinroq B2B sifatida e-faktura so'rasa, unda einvoices.related_doc_type='sales'… | 31; 31 US (US-M01-06) |  |
| B5-QT-M01-18 | ⬜ | QT-M01-18 (happy (MARKING_PRECHECK=warn)) — Berilgan tenant marking_precheck='warn' (standart), online, FakeMarkingAdapter kodni yaroqsiz deb qaytaradi (yoki timeout), q… | 31; 27 (aniq havola) |  |
| B5-QT-M01-19 | ⬜ | QT-M01-19 (negative (lokal takror kod)) — Berilgan DataMatrix kod C1 shu tenantda allaqachon sotilgan (marking_codes.status='sold') yoki shu chekda ikkinchi marta skaner… | 31; 31 US (US-M01-03) |  |
| B5-QT-M01-20 | ⬜ | QT-M01-20 (negative (MARKING_PRECHECK=block)) — Berilgan tenant marking_precheck='block', online, stub kodni yaroqsiz deb qaytaradi, qachonki sotuv yaratilsa, unda 409 M… | 31; 27 (aniq havola) |  |
| B5-QT-M01-21 | ⬜ | QT-M01-21 (happy (fiskal javob maydonlari)) — Berilgan ERP_FISCAL_PROVIDER=fake (FM emulyatori), qachonki 2 qatorli (1 markirovkali) naqd sotuv fiskallashtirilsa, unda f… | 31; 27 (aniq havola) |  |
| B5-QT-M01-23 | ⬜ | QT-M01-23 (happy (lokal ko'prik fiskal natijasi)) — Berilgan ERP_FISCAL_PROVIDER=multikassa_local (soxta FM), chek qurilma FM'ida imzolangan, qachonki sale.created fisca… | 31; 27 (aniq havola) |  |
| B5-QT-M07-03 | ⬜ | QT-M07-03 (happy) — Berilgan faktura "1120000.00" so'm (QQS bilan, nasiyaga), qachonki POST /goods-receipts/{id}/post bajarilsa, unda ledger_entries: Dt 2910/Kt 6010="10… | 31; 31 US (US-M07-03) |  |
| B5-QT-M07-04 | ⬜ | QT-M07-04 (negative) — Berilgan faktura "qizil" (yuqori xavfli) deb belgilangan, qachonki qabul post qilinsa, unda Dt 4410 (kiritiladigan QQS) yozuvi to'lovgacha yozilma… | 31; 31 US (US-M07-03) |  |
| B5-QT-M07-09 | ⬜ | QT-M07-09 (negative (xavf darajasi noma'lum)) — Berilgan kiruvchi faktura uchun operator xavf darajasini qaytarmagan (einvoices.risk_flag='unknown', standart), qachonki… | 31; 31 US (US-M07-03) |  |
| B5-QT-M10-04 | ⬜ | QT-M10-04 (happy) — Berilgan faktura "qizil" deb belgilangan, qachonki Buxgalter QQS hisobotini tayyorlasa, unda bu faktura alohida ko'rsatiladi, krediti "hali tasdiqlan… | 31; 31 US (US-M10-03) |  |
| B5-QT-M11-02 | ⬜ | QT-M11-02 (happy) — Berilgan oy yakunlanmoqda, barcha recost_jobs tugagan, qachonki Buxgalter "oy yopish"ni boshlasa, unda period_closings yozuvi yaratiladi, balans/P&L… | 31; 31 US (US-M11-02) |  |
| B5-QT-M11-03 | ⬜ | QT-M11-03 (negative) — Berilgan oy allaqachon yopilgan (period_closings mavjud), qachonki shu davrga tegishli yangi ledger_entries yozishga (yoki recost_job) urinilsa, u… | 31; 31 US (US-M11-02) |  |
| B5-QT-M11-04 | ⬜ | QT-M11-04 (happy) — Berilgan tanlangan davr, qachonki Egasi dashboard'ni ochsa, unda aylanma, xarajat, sof foyda sodda raqamlar sifatida ko'rsatiladi. | 31; 31 US (US-M11-03) |  |
| B5-QT-M11-05 | ⬜ | QT-M11-05 (negative (tayyor emas)) — Berilgan davrda tugallanmagan recost_jobs yoki hali OFD'ga yuborilmagan offline chek bor, qachonki POST /period-closings chaqirilsa,… | 31; 31 US (US-M11-02) |  |
| B5-QT-M11-06 | ⬜ | QT-M11-06 (negative (qayta yopish)) — Berilgan davr allaqachon yopilgan, qachonki POST /period-closings yana shu davr uchun chaqirilsa, unda 409 PERIOD_ALREADY_CLOSED. | 31; 31 US (US-M11-02) |  |
| B5-QT-M11-12 | ⬜ | QT-M11-12 (negative (boshlang'ich balans 0000)) — Berilgan boshlang'ich tovar (QT-M04-04) va qarz (QT-M08-10) kiritilgan, lekin kassa/kapital qoldiqlari hali kiritilmaga… | 31; 31 US (US-M11-02) |  |
| B5-QT-M11-14 | ⬜ | QT-M11-14 (negative (yopilgan davrga kech voqea)) — Berilgan 2026-10 yopilgan, qachonki 2026-10-31 sanali offline naqd sotuv ("12000.00") 2026-11-03 da /sync/push bilan… | 31; 31 US (US-M11-02) |  |
| B5-QT-NFR-07 | ⬜ | QT-NFR-07 (integration (fake clock)) — Berilgan markirovkalangan tovar yetkazib beruvchidan qabul qilinmoqda (egalik o'tishi, M07), tovar guruhi uchun sozlangan muddat (… | 31; markirovka qabul muddati (B5) |  |

## Bosqich 6: to'lov, AI, pilot

**Maqsad (27):** Obuna to'lovi ishlaydi (qaror #15, #22), AI funksiyalari (AI-01/03/05/06, qaror #16) yordam beradi, 5–10 pilot do'kon haqiqiy foydalanishni boshlaydi.

Holat: ✅ 4 · 🟡 11 · ⬜ 128 · ⛔ 2 · ⏭ 0 · jami 145

### Bosqich 6 — Vazifalar (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B6-T01 | ⬜ | M17 obuna to'lovi (Payme/Click), tarif limitlari; 24 soatlik imtiyoz tugagach qattiq to'xtatish (`14-autentifikatsiya-oauth2.md` §16–17): billing webhook bilan birga tenant bo'yicha sessiya/token ommaviy bekor qilish, Redis `sub_status` keshi, offline litsenz… | 27 |  |
| B6-T02 | ⬜ | D1 — lokautdan oldingi, hali yuborilmagan fiskal cheklar cheklangan `sync.drain` orqali OFD'ga baribir yuboriladi (`16-offline-sync.md` §3.5, `21-integratsiyalar.md` §1/§9) | 27 |  |
| B6-T03 | ⬜ | D2 — lokaut davrida ma'lumot eksporti faqat to'lov (billing) sahifasidan, OTP tasdig'i bilan — Telegram birinchi, SMS zaxira (qaror #20, #34; `16-offline-sync.md` §3.5) | 27 |  |
| B6-T04 | ⬜ | M17 ichki admin panel (ADM-01, US-M17-04, US-M13-08 — platforma admini Egasi hisobini bloklash/parol tiklash/sessiyalarini boshqarishi): tenantlar, obuna holati, to'lov tarixi, AI sarfi, faol kassalar; pilot do'konlar uchun muddatni qo'lda uzaytirish; `platfo…` | 27 |  |
| B6-T05 | ⬜ | AI-01 (savol-javob, whitelisted tool'lar) va AI-06 (qarz eslatma matni) — `22-ai-qatlami.md`; AI limiti va xarajat hisobi | 27 |  |
| B6-T06 | ⬜ | AI-03 (qog'oz hujjat OCR, pilot bilan, tor qamrov; Haiku 5.5 standart, past ishonchda Sonnet 5.5; `ai.ocr_enabled` flag, `eval/ocr_uz` 100 rasm — 26 #19; rasmlar faqat `ai_cross_border_enabled` rozilikdan keyin) — BO-04 kirim avto-to'ldirish, US-M04-04 (3)-yo… | 27 |  |
| B6-T07 | ⬜ | M10 davlat hisobotini solishtirish (fayl yuklash) + AI-05 tushuntirish + 5 ish kunlik taymer, eslatmalar 1-/3-/4-ish kuni (qaror #50) | 27 |  |
| B6-T08 | ⬜ | M09 yorliq chop etish; >200 yorliq yoki iOS uchun server PDF (`outbox_jobs(kind='label_pdf')`, qaror #54) | 27 |  |
| B6-T09 | ⬜ | US-M09-07 mijoz kartasida standart chegirma % (`counterparties.standing_discount_pct`, qaror #23); US-M09-02 narx tasdiqlash (BO-16) | 27 |  |
| B6-T10 | ⬜ | AI parametrlari (qaror #55): CBU kunlik kursi (`platform.fx_rates`), `POST /ai/chat` 10/daq/foydalanuvchi, 300/kun/tenant | 27 |  |
| B6-T11 | ⛔ | `message_key` uz/ru yakuniy matni (qaror #58 a) | 27 | 26 #45 — Eskiz shartnomasi (#130 dan keyin) |
| B6-T12 | ⛔ | SMS zaxira kanali — Eskiz shartnomasi bilan (26 #45) | 27 | 26 #127 — yurist (imzolangan oferta) |
| B6-T13 | ⬜ | Imzolangan Foydalanish shartlari `v1` sifatida yuklanadi (26 #127) — birinchi real tenantdan oldin | 27 |  |
| B6-T14 | ⬜ | Pilot: 5–10 do'kon, xarajat va AI sarfini o'lchash (unit-iqtisod, 26 #24) | 27 |  |

### Bosqich 6 — Tayyor ta'rifi (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B6-DoD-01 | ⬜ | obuna lokauti haqiqiy billing webhook bilan test qilingan | 27 Tayyor ta'rifi |  |
| B6-DoD-02 | ⬜ | AI-01/03/05/06 pilot do'konlarida ishlaydi | 27 Tayyor ta'rifi |  |
| B6-DoD-03 | ⬜ | pilot do'kon qog'oz daftarsiz bir hafta ishlaydi | 27 Tayyor ta'rifi |  |
| B6-DoD-04 | ⬜ | 5–10 pilot do'kondan xarajat/AI sarfi bo'yicha xulosa yig'ilgan. | 27 Tayyor ta'rifi |  |

### Bosqich 6 — Hikoyalar (27 → 30)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B6-US-M08-03 | ⬜ | US-M08-03 — Muddati o'tgan qarzlar uchun avtomatik AI eslatma matni | 27 Hikoyalar; 30 (Should) |  |
| B6-US-M09-02 | ⬜ | US-M09-02 — Katta narx o'zgarishini tasdiqlash | 27 Hikoyalar; 30 (Should) |  |
| B6-US-M09-04 | ⬜ | US-M09-04 — Narxi o'zgargan tovarlarning yorliqlarini qayta chop etish | 27 Hikoyalar; 30 (Should) |  |
| B6-US-M09-07 | ⬜ | US-M09-07 — Doimiy/ulgurji mijozga standart chegirma % (mijoz kartasida) | 27 Hikoyalar; 30 (Should) |  |
| B6-US-M10-02 | ⬜ | US-M10-02 — Davlat QQS hisobotini 5 ish kuni ichida solishtirish (qaror #50) | 27 Hikoyalar; 30 (Must) |  |
| B6-US-M10-04 | ⬜ | US-M10-04 — QQS to'lamaydigan (aylanma solig'i) biznes uchun davlat hisobotini solishtirish | 27 Hikoyalar; 30 (Must) |  |
| B6-US-M12-03 | ⬜ | US-M12-03 — QQS va davlat solishtirish hisobotini eksport qilish | 27 Hikoyalar; 30 (Must) |  |
| B6-US-M13-08 | ⬜ | US-M13-08 — Platforma admini: tenant va Egasi hisobini boshqarish | 27 Hikoyalar; 30 (Must) |  |
| B6-US-M17-02 | ⬜ | US-M17-02 — Tarifni tanlash va to'lash | 27 Hikoyalar; 30 (Must) |  |
| B6-US-M17-03 | ⬜ | US-M17-03 — To'lov muddatini unutmaslik, muddat o'tsa ham darhol to'xtamaslik | 27 Hikoyalar; 30 (Must) |  |
| B6-US-M17-04 | ⬜ | US-M17-04 — Platforma admini: tenantlar/obunalar/to'lovlarni ko'rish | 27 Hikoyalar; 30 (Must) |  |
| B6-US-M18-04 | ⬜ | US-M18-04 — Botdan oddiy savol so'rash (AI-01) | 27 Hikoyalar; 30 (Could) |  |

### Bosqich 6 — Endpointlar (14/17/18/19/20/33)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B6-EP-14#23 | ⬜ | GET /auth/license | 14 §20; offline litsenziya tokeni — 27 B6 |  |
| B6-EP-14#24 | ⬜ | GET /billing/pay | 14 §20; 30 (US API) |  |
| B6-EP-14#25 | ⬜ | POST /billing/checkout | 14 §20; 30 (US API) |  |
| B6-EP-14#26 | ⬜ | GET /billing/plan, /subscription, /addons, /payments | 14 §20; 30 (US API) |  |
| B6-EP-14#27 | ⬜ | POST /billing/webhooks/{provider} | 14 §20; billing webhook — 27 B6 (US-M17-02) |  |
| B6-EP-14§18.1#1 | ⬜ | GET /platform/tenants | 14 §18.1; 30 (US API) |  |
| B6-EP-14§18.1#2 | ⬜ | GET /platform/tenants/{id} | 14 §18.1; 30 (resurs) |  |
| B6-EP-14§18.1#3 | ⬜ | POST /platform/tenants/{id}/extend-subscription | 14 §18.1; 30 (resurs) |  |
| B6-EP-14§18.1#4 | ⬜ | POST /platform/tenants/{id}/revoke-all-sessions | 14 §18.1; 30 (resurs) |  |
| B6-EP-14§18.1#5 | ⬜ | GET /platform/tenants/{id}/ai-usage | 14 §18.1; 30 (resurs) |  |
| B6-EP-14§18.1#6 | ⬜ | POST /platform/tenants/{id}/owner/block, /unblock | 14 §18.1; 30 (resurs) |  |
| B6-EP-14§18.1#7 | ⬜ | POST /platform/tenants/{id}/owner/reset-password | 14 §18.1; 30 (resurs) |  |
| B6-EP-14§18.1#8 | ⬜ | GET /platform/tenants/{id}/owner/sessions, POST …/owner/sessions/{sid}/revoke | 14 §18.1; 30 (resurs) |  |
| B6-EP-19#15 | ⬜ | GET /label-print-queue | 19 §5; 30 (US API) |  |
| B6-EP-19#16 | ⬜ | GET /label-templates | 19 §5; 30 (US API) |  |
| B6-EP-19#17 | ⬜ | POST /label-print-jobs | 19 §5; 30 (US API) |  |
| B6-EP-19#18 | ⬜ | GET /label-print-jobs/{id} | 19 §5; 30 (resurs) |  |
| B6-EP-19#19 | ⬜ | POST /label-print-queue/mark-printed | 19 §5; 30 (resurs) |  |
| B6-EP-20#3 | ⬜ | POST /state-reports — Davlat hisoboti faylini yuklash | 20 indeks; 30 (US API) |  |
| B6-EP-20#4 | ⬜ | POST /state-reports/{id}/compare — Solishtirishni (qayta) ishga tushirish | 20 indeks; 30 (US API) |  |
| B6-EP-20#5 | ⬜ | GET /state-reports — Davlat hisobotlari ro'yxati | 20 indeks; 30 (US API) |  |
| B6-EP-20#6 | ⬜ | GET /state-reports/{id} — Hisobot tafsiloti + holat | 20 indeks; 30 (katalog raqami) |  |
| B6-EP-20#7 | ⬜ | GET /state-reports/{id}/diffs — Farq qatorlari ro'yxati | 20 indeks; 30 (US API) |  |
| B6-EP-20#7a | ⬜ | POST /state-reports/{id}/confirm — Hisobotni tasdiqlangan deb qayd etish | 20 indeks; 30 (katalog raqami) |  |
| B6-EP-20#8 | ⬜ | POST /state-reports/{id}/correction — Kabinetda kiritilgan tuzatishni qayd etish (imzosiz) | 20 indeks; 30 (US API) |  |
| B6-EP-20#22 | ⬜ | POST /reports/{report-kod}/export — Hisobotni Excel/PDF eksport qilish (job) | 20 indeks; 30 (US API) |  |
| B6-EP-20#23 | ⬜ | GET /reports/export-jobs/{job_id} — Eksport job holati | 20 indeks; 30 (US API) |  |
| B6-EP-20#56 | ⬜ | GET /billing/plan — Joriy tarif va limitlar | 20 indeks; 30 (US API) |  |
| B6-EP-20#57 | ⬜ | GET /billing/subscription — Obuna holati (status, muddat) | 20 indeks; obuna — 27 B6 (US-M17-02) |  |
| B6-EP-20#58 | ⬜ | GET /billing/addons — Qo'shimcha xizmatlar katalogi | 20 indeks; obuna — 27 B6 (US-M17-02) |  |
| B6-EP-20#59 | ⬜ | POST /billing/addons — Qo'shimcha kassa qo'shish | 20 indeks; obuna — 27 B6 |  |
| B6-EP-20#60 | ⬜ | POST /billing/addons/{addon_code}/reduce — Qo'shimchadan voz kechish | 20 indeks; obuna — 27 B6 |  |
| B6-EP-20#61 | ⬜ | POST /billing/checkout — To'lov checkout yaratish (Click/Payme) | 20 indeks; 30 (US API) |  |
| B6-EP-20#62 | ⬜ | GET /billing/payments — To'lovlar tarixi (qo'lda uzaytirishlar bilan) | 20 indeks; obuna — 27 B6 (US-M17-02) |  |
| B6-EP-20#63 | ⬜ | POST /billing/webhooks/click — Click webhook (bizning billing) | 20 indeks; billing webhook — 27 B6 |  |
| B6-EP-20#64 | ⬜ | POST /billing/webhooks/payme — Payme webhook (bizning billing) | 20 indeks; billing webhook — 27 B6 |  |
| B6-EP-20#65 | ⬜ | GET /billing/invoices/{payment_id} — To'lov hujjati (kvitansiya PDF) | 20 indeks; obuna — 27 B6 |  |
| B6-EP-20#72 | ⬜ | POST /ai/chat — AI chat (SSE stream) | 20 indeks; 27 vazifa matni |  |
| B6-EP-20#73 | ⬜ | POST /ai/ocr/jobs — Hujjat fotosini OCR tahliliga yuborish | 20 indeks; AI-03 — 27 B6 (US-M04-04 (3)-yo'l) |  |
| B6-EP-20#74 | ⬜ | GET /ai/ocr/jobs/{job_id} — OCR natijasini olish | 20 indeks; AI-03 — 27 B6 |  |
| B6-EP-20#75 | ⬜ | POST /ai/ocr/jobs/{job_id}/confirm — Natijani tasdiqlab hujjat yaratish | 20 indeks; AI-03 — 27 B6 |  |
| B6-EP-20#76 | ⬜ | POST /ai/vat-diffs/{diff_id}/explain — Davlat hisoboti farqini tushuntirish | 20 indeks; AI-05 — 27 B6 (US-M10-02) |  |
| B6-EP-20#77 | ⬜ | POST /ai/debt-reminders/draft — Qarz eslatma matni loyihasi | 20 indeks; 30 (US API) |  |
| B6-EP-20#78 | ⬜ | POST /ai/debt-reminders/send — Tasdiqlangan eslatmani yuborish | 20 indeks; 30 (resurs) |  |
| B6-EP-20#79 | ⬜ | GET /ai/usage — Joriy oy AI limiti sarfi | 20 indeks; AI limiti — 27 B6 |  |

### Bosqich 6 — Ekranlar (06/07)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B6-SCR-ADM-01 | ⬜ | ADM-01 — Ichki admin panel | 07; 27/30 |  |
| B6-SCR-BO-01 | ⬜ | BO-01 — Kirish (login), tenant/filial tanlash | 07; 27/30 |  |
| B6-SCR-BO-04 | ⬜ | BO-04 — Xaridnoma yaratish, yetkazib beruvchiga to'lov/qaytarish | 07; 27/30 |  |
| B6-SCR-BO-05 | ⬜ | BO-05 — Narxlar va chegirma qoidalarini boshqarish | 07; 27/30 |  |
| B6-SCR-BO-06 | ⬜ | BO-06 — Nasiya/qarzdorlar ro'yxati va eslatmalar | 07; 27/30 |  |
| B6-SCR-BO-07 | ⬜ | BO-07 — QQS ichki hisob-kitobi | 07; 27/30 |  |
| B6-SCR-BO-09 | ⬜ | BO-09 — Hisobotlar markazi | 07; 27/30 |  |
| B6-SCR-BO-10 | ⬜ | BO-10 — Davlat hisobotini ichki hisob bilan solishtirish | 07; 27/30 |  |
| B6-SCR-BO-11 | ⬜ | BO-11 — Foydalanuvchilar, huquqlar va sessiyalar | 07; 27/30 |  |
| B6-SCR-BO-13 | ⬜ | BO-13 — AI yordamchi — savol-javob chat | 07; 27/30 |  |
| B6-SCR-BO-16 | ⬜ | BO-16 — Tasdiqlash navbati (limitdan oshgan so'rovlar) | 07; 27/30 |  |
| B6-SCR-BO-18 | ⬜ | BO-18 — Yorliq va shtrix-kod chop etish | 07; 27/30 |  |
| B6-SCR-BO-19 | ⬜ | BO-19 — Obuna va to'lov | 07; 27/30 |  |
| B6-SCR-POS-01 | ⬜ | POS-01 — Kassaga kirish / Smena ochish | 07; 27/30 |  |
| B6-SCR-POS-02 | ⬜ | POS-02 — Sotish paneli (asosiy chek) | 07; 27/30 |  |

### Bosqich 6 — Jadvallar / migratsiyalar (12)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B6-TBL-platform.label_templates | 🟡 | `platform.label_templates` (revizion 0004) | 12; 30 (US jadvallari) | DDL 0004 bor; ilova kodi bor, test yo'q |
| B6-TBL-platform.fx_rates | 🟡 | `platform.fx_rates` (revizion 0007) | 12; 27 vazifa matni | DDL 0007 bor; ilova kodi bor, test yo'q |
| B6-TBL-app.license_tokens | 🟡 | `app.license_tokens` (revizion 0003) | 12; infratuzilma — 12 §6.1 revizioni Bosqich 0 da; ko'chirildi B0 → B6: yozish/o'qish yo'li — `GET /auth/license` offline litsenziya tokeni (27 B6, 14 §17); B0 da faqat DDL | DDL 0003 bor; modul kodi/testi yo'q |
| B6-TBL-platform.platform_admins | ✅ | `platform.platform_admins` (revizion 0007) | 12; 27 vazifa matni | DDL 0007; kod va test: `backend/tests/integration/test_rls.py` |
| B6-TBL-app.tenant_addons | ✅ | `app.tenant_addons` (revizion 0007) | 12; 27 B6: tarif limitlari, qo'shimcha kassa | DDL 0007; kod va test: `backend/tests/support/branches.py` |
| B6-TBL-app.billing_payments | 🟡 | `app.billing_payments` (revizion 0007) | 12; 30 (US jadvallari) | DDL 0007 bor; modul kodi/testi yo'q |
| B6-TBL-app.label_print_queue | ✅ | `app.label_print_queue` (revizion 0008) | 12; 30 (US jadvallari) | DDL 0008; kod va test: `backend/tests/integration/test_catalog_products.py`, `backend/tests/integration/test_import_jobs.py` |
| B6-TBL-app.state_reports | 🟡 | `app.state_reports` (revizion 0020) | 12; 30 (US jadvallari) | DDL 0020 bor; modul kodi/testi yo'q |
| B6-TBL-app.state_report_diffs | 🟡 | `app.state_report_diffs` (revizion 0020) | 12; 30 (US jadvallari) | DDL 0020 bor; modul kodi/testi yo'q |
| B6-TBL-app.ai_requests | 🟡 | `app.ai_requests` (revizion 0021) | 12; AI — 27 B6 | DDL 0021 bor; modul kodi/testi yo'q |
| B6-TBL-app.ai_ocr_jobs | 🟡 | `app.ai_ocr_jobs` (revizion 0021) | 12; AI-03 — 27 B6 | DDL 0021 bor; modul kodi/testi yo'q |
| B6-TBL-app.ai_training_samples | 🟡 | `app.ai_training_samples` (revizion 0023) | 12; AI — 27 B6 (22 ichki quvur) | DDL 0023 bor; modul kodi/testi yo'q |
| B6-TBL-app.ai_feedback | 🟡 | `app.ai_feedback` (revizion 0023) | 12; AI — 27 B6 (22 ichki quvur) | DDL 0023 bor; modul kodi/testi yo'q |
| B6-TBL-app.tenant_glossary | 🟡 | `app.tenant_glossary` (revizion 0023) | 12; AI — 27 B6 (22 ichki quvur) | DDL 0023 bor; modul kodi/testi yo'q |

### Bosqich 6 — Qabul testlari (31)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B6-QT-SUB-01 | ⬜ | QT-SUB-01 (integration) — Berilgan subscriptions.status='active', current_period_end o'tgan, qachonki scheduler tekshirsa, unda holat gracega o'tadi, grace_ends_at = cur… | 31; 31 §1.5 — obuna lokauti (27 B6) |  |
| B6-QT-SUB-02 | ⬜ | QT-SUB-02 (e2e (Playwright)) — Berilgan tenant grace holatida, qachonki foydalanuvchi kassada chek yaratadi, unda sotuv, fiskal chek, AI so'rovlari odatdagidek ishlaydi… | 31; 31 §1.5 — obuna lokauti (27 B6) |  |
| B6-QT-SUB-03 | ⬜ | QT-SUB-03 (integration) — Berilgan grace_ends_at o'tgan va to'lov kelmagan, qachonki scheduler ishga tushsa, unda holat restrictedga o'tadi: app.auth_suspend_tenant(tena… | 31; 31 §1.5 — obuna lokauti (27 B6) |  |
| B6-QT-SUB-04 | ⬜ | QT-SUB-04 (e2e) — Berilgan tenant restricted, qachonki mavjud sessiyadan API so'rovi yuborilsa, unda 403 {code: "SUBSCRIPTION_RESTRICTED"}, frontend interceptor /login… | 31; 31 §1.5 — obuna lokauti (27 B6) |  |
| B6-QT-SUB-05 | ⬜ | QT-SUB-05 (integration) — Berilgan tenant restricted, qachonki autentifikatsiyalanmagan foydalanuvchi GET /billing/payni ochsa, unda 200 — bu sahifa restricted holatida… | 31; 31 §1.5 — obuna lokauti (27 B6) |  |
| B6-QT-SUB-06 | ⬜ | QT-SUB-06 (integration) — Berilgan tenant restricted, qurilmaning suspended refresh tokeni bor, qachonki POST /oauth/token (grant_type=refresh_token) chaqirilsa, unda fa… | 31; 31 §1.5 — obuna lokauti (27 B6) |  |
| B6-QT-SUB-07 | ⬜ | QT-SUB-07 (integration) — Berilgan scope=sync.drain tokeni va qurilmada lokautdan oldin yaratilgan, hali yuborilmagan 3 ta fiskal chek, qachonki /sync/push shu token bil… | 31; 31 §1.5 — obuna lokauti (27 B6) |  |
| B6-QT-SUB-08 | ⬜ | QT-SUB-08 (e2e) — Berilgan tenant restricted, qachonki foydalanuvchi to'lov sahifasidan "Ma'lumotlarimni yuklab olish"ni bosadi, unda SMS/Telegram OTP (purpose=data_ex… | 31; 31 §1.5 — obuna lokauti (27 B6) |  |
| B6-QT-SUB-09 | ⬜ | QT-SUB-09 (integration) — Berilgan restricted tenant to'lov qiladi, qachonki billing_payments.status='success' bo'lsa, unda subscriptions.status='active'ga qaytadi, barc… | 31; 31 §1.5 — obuna lokauti (27 B6) |  |
| B6-QT-M09-02 | ✅ | QT-M09-02 (negative) — Berilgan narx o'zgarishi belgilangan limitdan (±10%, 26-ochiq-savollar-reestri.md #5) katta, qachonki Menejer kiritsa, unda price_changes.status='… | 31; 31 US (US-M09-02) | test: `web/apps/shell/e2e/prices.spec.ts` |
| B6-QT-M09-04 | ⬜ | QT-M09-04 (happy) — Berilgan 3 tovar narxi o'zgargan, hali yorlig'i chop etilmagan, qachonki Menejer "Yorliqlar" bo'limini ochsa, unda shu 3 tovar ro'yxatda chiqadi; tan… | 31; 31 US (US-M09-04) |  |
| B6-QT-M09-07 | ⬜ | QT-M09-07 (happy) — Berilgan mijoz kartasida doimiy chegirma "10.00"% belgilangan, qachonki shu mijozga sotuv qilinsa, unda chegirma avtomatik qo'llanadi (QT-M03-04 bila… | 31; 31 US (US-M09-07) |  |
| B6-QT-M10-02 | ⬜ | QT-M10-02 (happy) — Berilgan davlat QQS hisoboti my.soliq.uz'da e'lon qilingan va ichki hisobga mos keladi, qachonki Buxgalter uni kiritsa, unda holat kutilmoqda → mos k… | 31; 31 US (US-M10-02) |  |
| B6-QT-M10-03 | ⬜ | QT-M10-03 (negative) — Berilgan davlat hisoboti ichki hisobdan farq qiladi (farq "1000.00" tolerance'dan katta), qachonki Buxgalter kiritsa, unda holat farq topildiga o'… | 31; 31 US (US-M10-02) |  |
| B6-QT-M10-05 | ⬜ | QT-M10-05 (happy) — Berilgan tenant aylanma solig'i rejimida (regime='turnover'), filial settlement_category='city_100k_plus', qachonki oy yakunida tax_settlements(tax_k… | 31; 31 US (US-M10-04) |  |
| B6-QT-M10-08 | ⬜ | QT-M10-08 (happy (aylanma solig'i, §4.3)) — Berilgan filial (shahar, retail_city_100k_plus 4%) oyi: 9020 = "50000000.00", 9040 = "1000000.00", 9050 = "500000.00", 9390 =… | 31; 31 US (US-M10-04) |  |
| B6-QT-M12-03 | ⬜ | QT-M12-03 (happy) — Berilgan M10 solishtirish yakunlangan, qachonki Buxgalter "eksport"ni bossa, unda hisobot Excel/PDF formatda yuklab olinadi. | 31; 31 US (US-M12-03) |  |
| B6-QT-M12-05 | ⬜ | QT-M12-05 (negative (eksport muddati)) — Berilgan eksport job yaratilgan, 24 soatdan ko'p vaqt o'tgan, qachonki eski file_url orqali yuklab olinsa, unda signed URL mudda… | 31; 31 US (US-M12-03) |  |
| B6-QT-M13-08 | ⬜ | QT-M13-08 (happy) — Berilgan platforma admin paneli, qachonki admin tenant Egasi hisobini bloklasa/parolini tiklasa, unda amal bajariladi; lekin admin oddiy Kassir/Menej… | 31; 31 US (US-M13-08) |  |
| B6-QT-M17-03 | ⬜ | QT-M17-03 (happy) — Berilgan Egasi qo'shimcha kassa qo'shmoqchi, qachonki "Qo'shimcha kassa qo'shish" bosilsa, unda "39000.00" so'm/oy obuna summasiga qo'shiladi, keying… | 31; 31 US (US-M17-02) |  |
| B6-QT-M17-04 | ⬜ | QT-M17-04 (negative) — Berilgan faol kassalar soni 3 (1 asosiy + 2 qo'shimcha), qachonki Egasi qo'shimchalardan voz kechib yangi sonni 1ga tushirsa, unda ortiqcha 2 kass… | 31; 31 US (US-M17-02) |  |
| B6-QT-M17-05 | ⬜ | QT-M17-05 (happy) — Berilgan platforma admin paneli, qachonki admin pilot tenant uchun obuna muddatini qo'lda uzaytirsa (reason bilan), unda POST /platform/tenants/{id}/… | 31; 31 US (US-M17-04) |  |
| B6-QT-M17-07 | ⬜ | QT-M17-07 (negative (webhook idempotentlik)) — Berilgan Click/Payme webhook provider_tx_id=TX1 bilan allaqachon billing_paymentsda qayd etilgan, qachonki tashqi tizim xu… | 31; 31 US (US-M17-02) |  |
| B6-QT-M17-09 | ⬜ | QT-M17-09 (happy (muddat o'tishi va to'lov)) — Berilgan subscriptions.status='active', current_period_end o'tgan, qachonki scheduler ishlasa, unda grace (24 soat, hamma… | 31; 31 US (US-M17-03) |  |
| B6-QT-M18-04 | ⬜ | QT-M18-04 (happy) — Berilgan bot ulangan, qachonki Egasi "Bugun qancha sotdik?" deb yozsa, unda AI-01 orqali tool-chaqiruv + raqamli nazoratdan o'tgan javob qaytadi, AI… | 31; 31 US (US-M18-04) |  |
| B6-QT-AI-01-01 | ⬜ | QT-AI-01-01 (integration) — Berilgan AI-01 eval to'plami (backend/ai/eval/ai01_qna/cases.jsonl, 50–100 holat, lotin/kirill/rus aralash), qachonki CI regression gate ishg… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-01-02 | ⬜ | QT-AI-01-02 (integration) — Berilgan "Bugun qancha sotdik?" / "бугунги savdo qancha?" / "сколько продали сегодня?" uch xil tildagi bir xil savol, qachonki AI-01 chaqiril… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-03-01 | ⬜ | QT-AI-03-01 (integration) — Berilgan 100 ta O'zbekiston hujjatidan iborat test to'plami (≈40% toza, 40% foto/skaner, 20% qo'lda yozilgan; lotin/kirill/rus), qachonki AI-… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-03-02 | ⬜ | QT-AI-03-02 (integration) — Berilgan AI-03 standart modeli Haiku 5.5 (ai_requests.model='claude-haiku-5-5') natijasida bir maydon ishonch darajasi field-chegaradan past… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-03-03 | ⬜ | QT-AI-03-03 (unit) — Berilgan AI-03 qamrovi (faqat: QQS to'lovchi bo'lmagan yetkazib beruvchining qog'oz yuk xati / texnik uzilishdagi qog'oz faktura / qaytarish uchun q… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-05-01 | ⬜ | QT-AI-05-01 (integration) — Berilgan AI-05 eval to'plami, qachonki CI gate ishga tushsa, unda raqamli nazorat o'tish darajasi 100% (nol tolerantlik) va har javobda manba… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-06-01 | ⬜ | QT-AI-06-01 (integration) — Berilgan AI-06 (qarz eslatmasi) matn generatsiyasi, qachonki natija tekshirilsa, unda matndagi har bir raqam (summa, sana) kod tomonidan qo'y… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-LIMIT-01 | ⬜ | QT-AI-LIMIT-01 (integration) — Berilgan tenant oylik AI token limiti ("2500000" token, standart tarif) tugagan, qachonki yangi AI so'rovi yuborilsa, unda hard-stop — foy… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-GUARD-01 | ⬜ | QT-AI-GUARD-01 (integration) — Berilgan Claude API ishlamay qolgan (timeout/5xx/circuit breaker ochiq), qachonki bir necha urinishdan keyin ham muvaffaqiyatsiz bo'lsa, u… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-GUARD-02 | ⬜ | QT-AI-GUARD-02 (unit) — Berilgan LLM birinchi javobida raqamli nazorat tool natijasida yo'q sonni (masalan "999999.00") yozgan, qachonki numeric_guard tekshirsa, unda so… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-GUARD-03 | ⬜ | QT-AI-GUARD-03 (unit) — Berilgan AI-01'ga "Bugun eng ko'p sotgan kassir kim va u nega ishdan ketmoqchi?" kabi mavjud tool/ma'lumot bazasida javobi yo'q savol beriladi, q… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-OCR-01 | ⬜ | QT-AI-OCR-01 (integration) — Berilgan AI-03 OCR'ga yuklangan rasm o'qib bo'lmaydigan (butunlay qora/noaniq); qachonki GET /ai/ocr/jobs/{job_id} natijasi so'ralsa, unda a… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-AI-PII-02 | ⬜ | QT-AI-PII-02 (integration) — Berilgan tenant settings.ai_cross_border_enabled=false, qachonki AI-03 OCR uchun rasm yuklansa, unda 403 AI_CONSENT_REQUIRED, rasm Claude'ga… | 31; 27 B6 — AI-01/03/05/06 |  |
| B6-QT-NFR-05 | ⬜ | QT-NFR-05 (integration) — Berilgan AI-01 chat so'rovi, qachonki yuborilsa, unda birinchi token < 3 s ichida qaytadi. | 31; AI chat (B6) |  |
| B6-QT-NFR-08 | ⬜ | QT-NFR-08 (integration (fake clock)) — Berilgan davlat hisoboti e'lon qilingan va farq topilgan, unda tasdiqlash yoki tuzatish ≤ 5 ish kuni ichida (topshirish muddatidan… | 31; davlat hisoboti 5 ish kuni (B6) |  |
| B6-QT-NFR-13 | ⬜ | QT-NFR-13 (e2e (performance)) — Berilgan POST /ai/chat SSE stream orqali javob beradi, qachonki javob uzun (masalan ko'p modulni qiyoslovchi tahlil) bo'lsa, unda birinch… | 31; AI chat (B6) |  |

## Bosqich 7: 1C integratsiyasi

**Maqsad (27):** pilot do'konlar ERP'dagi kunlik sotuv va boshqa hujjatlarni o'z kompyuteridagi «Бухгалтерия для Узбекистана 3.0» bazasiga bir tugma bilan, takrorsiz va tekshirilgan holda yozadi (qaror #36–#42).

Holat: ✅ 0 · 🟡 0 · ⬜ 131 · ⛔ 0 · ⏭ 0 · jami 131

### Bosqich 7 — Vazifalar (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B7-T01 | ⬜ | DB: migratsiya `0029 onec_integration` (`33` §5), §5.22 dagi qolganlari (`devices.kind`/`signing_keys.purpose` — Bosqich 0 da, qaror #58 c), 6 ta 1C SECURITY DEFINER funksiyasidan qolganlari (`onec_tenants_due`), RLS CI ro'yxati | 27 |  |
| B7-T02 | ⬜ | Agent API A-02, 1C vazifa turlari (`33` §9; OAuth, A-01, A-03…A-10, long-poll, lease, vazifa imzosi — Bosqich 5) | 27 |  |
| B7-T03 | ⬜ | Do'kon agentining 1C imkoniyati (`34-1c-agent.md`, repo `agent-1c/`; asos — Bosqich 5): supervisor, x86/x64 COM worker, DPAPI, ulash, bazalarni topish, «saqlash=sinash», `33` §8.3 yozish algoritmi, `results.jsonl` outbox | 27 |  |
| B7-T04 | ⬜ | Onboarding tekshiruvlari (`33` §2.3): `comcntr.dll` ro'yxatdan o'tmagan bo'lsa — bir martalik UAC qadami; «Разрешить списание запасов при отсутствии остатков» sozlamasi o'qiladi; metadata snapshot, `bp30_uz` profili (26 #132) | 27 |  |
| B7-T05 | ⬜ | Moslashtirish ustasi: `read_refs` keshi, auto-match, qiymat moslashtirishlari, `onec_ref_create_requests` (BO-22) | 27 |  |
| B7-T06 | ⬜ | `BatchBuilder` — `33` §6.2 barcha turlari (A-qism: `goods_receipt`, `retail_sales_report`, qoldiq preflight; B-qism: qaytarishlar, `credit_sale` + to'lovlar, `debt_payment`, ko'chirish, hisobdan chiqarish, inventarizatsiya, kassa hujjatlari, `bank_settlement`… | 27 |  |
| B7-T07 | ⬜ | Holat mashinalari (`33` §7), tayyorlik (§7.3, `16-offline-sync.md` §9 qurilma qoidasi + `outbox_state`), dispetcher, verify (§8.10) | 27 |  |
| B7-T08 | ⬜ | Revision, kech ma'lumot (`OneCChangeTracker` barcha posting xizmatlarida), bekor qilish, tuzatuvchi partiya, drift (`33` §8) | 27 |  |
| B7-T09 | ⬜ | Jadval (`on_shift_close`, `at_time`), avto-tasdiq (faqat Egasi); 13 SAQ job va 5 cron (`23-backend-arxitekturasi.md` §4.1) | 27 |  |
| B7-T10 | ⬜ | Veb API W-06, W-09…W-55, BO-22, BO-23, BO-14 «1C» qatori, hujjat ekranlarida «1C da» belgisi (`24-frontend-arxitekturasi.md` §1.1) | 27 |  |
| B7-T11 | ⬜ | Ruxsatlar (`33` §11), audit, Telegram shablonlari (§13.3), xato kodlari (§12) i18n | 27 |  |
| B7-T12 | ⬜ | Qabul testlari (`31` M19; `33` §14 qabul mezonlari): GUID test vektorlari, P-20 dublikatsizlik, 7 kunlik offline navbat | 27 |  |

### Bosqich 7 — Tayyor ta'rifi (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B7-DoD-01 | ⬜ | pilot do'konda bir kunlik 300+ qatorli savdo (+ kirim, qaytarish, qarz to'lovi) 1C'ga yozilib o'tkaziladi va `read_totals` 0.00 farq bilan `done` | 27 Tayyor ta'rifi |  |
| B7-DoD-02 | ⬜ | ikkinchi «Yuborish» va yozish o'rtasidagi uzilish dublikat yaratmaydi | 27 Tayyor ta'rifi |  |
| B7-DoD-03 | ⬜ | 7 kunlik offline'dan keyin partiyalar sana tartibida o'tadi | 27 Tayyor ta'rifi |  |
| B7-DoD-04 | ⬜ | kech offline chek o'sha GUID'li ОРП'ni yangilaydi | 27 Tayyor ta'rifi |  |
| B7-DoD-05 | ⬜ | yopiq 1C davri sana almashtirilmasdan `ONEC_DATE_PROHIBITED` beradi. | 27 Tayyor ta'rifi |  |

### Bosqich 7 — Hikoyalar (27 → 30)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B7-US-M19-01 | ⬜ | US-M19-01 — Do'kon kompyuterini (agent) xavfsiz ulash | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-02 | ⬜ | US-M19-02 — 1C bazasi yaroqliligini bir ekranda ko'rish (onboarding tekshiruvlari) | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-03 | ⬜ | US-M19-03 — Filial → 1C bazasi, sana va rejimni belgilash | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-04 | ⬜ | US-M19-04 — ERP ↔ 1C moslashtirish (tovar, kassa, to'lov turi, kontragent) | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-05 | ⬜ | US-M19-05 — 1C'da yangi element faqat tasdiqdan keyin yaratiladi | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-06 | ⬜ | US-M19-06 — Kun yopilgach preview va tayyorlik | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-07 | ⬜ | US-M19-07 — Preview'ni bir tugma bilan 1C ga yuborish | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-08 | ⬜ | US-M19-08 — Takror bosish / uzilishda dublikat yo'q | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-09 | ⬜ | US-M19-09 — Yozilmagan hujjat sababini ko'rib qayta yuborish | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-10 | ⬜ | US-M19-10 — Jamlarni avtomatik solishtirish (read_totals) | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-11 | ⬜ | US-M19-11 — Kech offline chek yuborilgan kunni yangilaydi | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-12 | ⬜ | US-M19-12 — Yopiq 1C davri — faqat tuzatuvchi hujjat | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-13 | ⬜ | US-M19-13 — Avto-tayyorlash va (Egasi yoqsa) avto-tasdiq | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-14 | ⬜ | US-M19-14 — Telegram natija/muammo xabarlari | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-15 | ⬜ | US-M19-15 — Kompyuter o'chiq bo'lsa ham hech narsa yo'qolmaydi | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-16 | ⬜ | US-M19-16 — ERP'da bekor qilingan hujjat 1C'da ham aks etadi | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-17 | ⬜ | US-M19-17 — Kompyuter almashtirilganda tarix saqlanadi | 27 Hikoyalar; 30 (Keyin) |  |
| B7-US-M19-18 | ⬜ | US-M19-18 — 1C'da qo'lda o'zgartirilgan/o'chirilgan hujjatni bilish (drift) | 27 Hikoyalar; 30 (Keyin) |  |

### Bosqich 7 — Endpointlar (14/17/18/19/20/33)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B7-EP-33W-06 | ⬜ | POST /onec-agents/{id}/discover-bases — PK'da 1C bazalarini qayta qidirish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-09 | ⬜ | GET /onec-bases — Bazalar | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-10 | ⬜ | GET /onec-bases/{id} — Baza tafsiloti | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-11 | ⬜ | PATCH /onec-bases/{id} — Nom, write_enabled, profil | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-12 | ⬜ | POST /onec-bases/{id}/checks — Onboarding tekshiruvlarini ishga tushirish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-13 | ⬜ | GET /onec-bases/{id}/checks — Tekshiruv natijalari | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-14 | ⬜ | POST /onec-bases/{id}/reassign — Bazani boshqa agentga o'tkazish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-15 | ⬜ | POST /onec-bases/{id}/archive — Bazani arxivlash | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-16 | ⬜ | GET /onec-branch-bindings — Filial → baza bog'lanishlari | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-17 | ⬜ | PUT /onec-branch-bindings/{branch_id} — Filialni bazaga bog'lash | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-18 | ⬜ | DELETE /onec-branch-bindings/{branch_id} — Bog'lanishni olib tashlash | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-19 | ⬜ | GET /onec-settings/{base_id} — Sozlamalar | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-20 | ⬜ | PATCH /onec-settings/{base_id} — Rejim, jadval, avto-tasdiq, siyosatlar | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-21 | ⬜ | POST /onec-catalog-items/refresh — 1C ma'lumotnomalarini qayta o'qish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-22 | ⬜ | GET /onec-catalog-items — 1C elementlarini qidirish (tanlash uchun) | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-23 | ⬜ | GET /onec-mappings/summary — Moslashtirish holati (entity bo'yicha) | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-24 | ⬜ | GET /onec-mappings — ERP obyektlari va moslashtirish (moslanmaganlar ham) | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-25 | ⬜ | POST /onec-mappings/auto-match — Avtomatik takliflar | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-26 | ⬜ | POST /onec-mappings/confirm — Moslashtirishni tasdiqlash (ommaviy) | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-27 | ⬜ | DELETE /onec-mappings/{id} — Bog'lanishni olib tashlash | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-28 | ⬜ | GET /onec-value-mappings — Qiymat moslashtirishlari | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-29 | ⬜ | PUT /onec-value-mappings — Qiymat moslashtirishlarini saqlash (ommaviy) | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-30 | ⬜ | GET /onec-ref-create-requests — 1C'da yaratish so'rovlari | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-31 | ⬜ | POST /onec-ref-create-requests — Yaratish taklifini tuzish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-32 | ⬜ | POST /onec-ref-create-requests/approve — Tasdiqlash (ommaviy) → 1C'da yaratish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-33 | ⬜ | POST /onec-ref-create-requests/{id}/reject — Rad etish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-34 | ⬜ | GET /onec-export-batches — Partiyalar tarixi | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-35 | ⬜ | GET /onec-export-batches/calendar — Oy kalendari (kun holatlari) | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-36 | ⬜ | POST /onec-export-batches — Kunni tayyorlash | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-37 | ⬜ | GET /onec-export-batches/{id} — Preview / progress / natija | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-38 | ⬜ | GET /onec-export-batches/{id}/items — Itemlar | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-39 | ⬜ | GET /onec-export-batches/{id}/items/{item_id} — Item tafsiloti (manbalar, xato, ObjectSpe… | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-40 | ⬜ | POST /onec-export-batches/{id}/items/{item_id}/preview — 1C'da sinov ko'rinishi (preview_… | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-41 | ⬜ | POST /onec-export-batches/{id}/rebuild — Qayta qurish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-42 | ⬜ | POST /onec-export-batches/{id}/exclude-devices — Sinxronlanmagan qurilmani istisno qilish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-43 | ⬜ | POST /onec-export-batches/{id}/approve — Tasdiqlash va yuborish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-44 | ⬜ | POST /onec-export-batches/{id}/cancel — Bekor qilish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-45 | ⬜ | POST /onec-export-batches/{id}/resend-failed — Xatolarni qayta yuborish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-46 | ⬜ | POST /onec-export-batches/{id}/items/{item_id}/skip — Itemni o'tkazib yuborish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-47 | ⬜ | POST /onec-export-batches/{id}/accept — partial/mismatch ni qabul qilish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-48 | ⬜ | POST /onec-export-batches/{id}/new-revision — Yangi revision | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-49 | ⬜ | POST /onec-export-batches/{id}/correction — Tuzatuvchi partiya (yopiq davr) | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-50 | ⬜ | POST /onec-export-batches/{id}/reconcile — Solishtirishni qayta ishga tushirish | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-51 | ⬜ | GET /onec-export-batches/{id}/events — Partiya voqealari | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-52 | ⬜ | GET /onec-reconciliations — Solishtirishlar | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-53 | ⬜ | POST /onec-reconciliations — Qoldiq solishtiruvi / drift tekshiruvini so'rash | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-54 | ⬜ | GET /onec-object-refs — ERP hujjati → 1C obyekti («1C da») | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33W-55 | ⬜ | GET /onec-status — Umumiy holat (BO-14 qatori, BO-23 sarlavhasi) | 33 §10; 27 (katalog raqami) |  |
| B7-EP-33A-02 | ⬜ | /onec-agent/bases (A-02) | 33 §9.3; 27 (katalog raqami) |  |

### Bosqich 7 — Ekranlar (06/07)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B7-SCR-BO-14 | ⬜ | BO-14 — Tenant/do'kon sozlamalari | 07; 27/30 |  |
| B7-SCR-BO-20 | ⬜ | BO-20 — Telegram va bildirishnomalar | 07; 27/30 |  |
| B7-SCR-BO-22 | ⬜ | BO-22 — 1C integratsiyasi sozlamalari va moslashtirish (M19, Bosqich 7) | 07; 27/30 |  |
| B7-SCR-BO-23 | ⬜ | BO-23 — 1C ga yuborish (kunlar) (M19, Bosqich 7) | 07; 27/30 |  |

### Bosqich 7 — Jadvallar / migratsiyalar (12)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B7-TBL-app.onec_bases | ⬜ | `app.onec_bases` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_settings | ⬜ | `app.onec_settings` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_branch_bindings | ⬜ | `app.onec_branch_bindings` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_metadata_snapshots | ⬜ | `app.onec_metadata_snapshots` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_catalog_items | ⬜ | `app.onec_catalog_items` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_mappings | ⬜ | `app.onec_mappings` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_value_mappings | ⬜ | `app.onec_value_mappings` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_ref_create_requests | ⬜ | `app.onec_ref_create_requests` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_export_batches | ⬜ | `app.onec_export_batches` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_export_items | ⬜ | `app.onec_export_items` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_export_item_sources | ⬜ | `app.onec_export_item_sources` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_object_refs | ⬜ | `app.onec_object_refs` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_reconciliations | ⬜ | `app.onec_reconciliations` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_events | ⬜ | `app.onec_events` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |
| B7-TBL-app.onec_agent_logs | ⬜ | `app.onec_agent_logs` (revizion 0029) | 12; 12 §6.1 — 0029 onec_integration (27 B7) | DDL migratsiyasi (0029) hali yo'q |

### Bosqich 7 — Qabul testlari (31)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| B7-QT-M19-01 | ⬜ | QT-M19-01 (happy (ulash)) — Berilgan agent device kodi WDJB-MJHT olgan, qachonki Egasi BO-22 da W-03 → W-04 bajarsa, unda onec_agents + devices(kind='onec_agent') yarati… | 31; 31 US (US-M19-01) |  |
| B7-QT-M19-02 | ⬜ | QT-M19-02 (negative) — Berilgan kod 10 daqiqadan eski, qachonki W-04, unda 409 ONEC_PAIRING_CODE_EXPIRED; noma'lum yoki allaqachon ishlatilgan kod — 404 ONEC_PAIRING_COD… | 31; 31 US (US-M19-01) |  |
| B7-QT-M19-03 | ⬜ | QT-M19-03 (security (sir)) — Berilgan agent bazani 1C paroli bilan qo'shgan (A-02), qachonki barcha onec_* jadvallari, audit_log va server loglari skanerlansa, unda 1C p… | 31; 31 US (US-M19-01) |  |
| B7-QT-M19-04 | ⬜ | QT-M19-04 (negative (qamrovdan tashqari)) — Berilgan probe natijasi «Базовая» versiya / ws= baza / sotish narxida hisob, qachonki tekshiruvlar yakunlansa, unda mos ravis… | 31; 31 US (US-M19-02) |  |
| B7-QT-M19-05 | ⬜ | QT-M19-05 (happy (chegara)) — Berilgan filial bound_from=2026-11-01, 31.10 va 01.11 sanali sotuvlar bor, qachonki 31.10 uchun W-36, unda 422 ONEC_BEFORE_START_DATE; 01.1… | 31; 31 US (US-M19-03) |  |
| B7-QT-M19-06 | ⬜ | QT-M19-06 (negative (tayyorlik — qurilma)) — Berilgan filialning Android kassasi D kunidan keyin sinxronlanmagan (yoki outbox'ida D dan eski voqea bor, 16-offline-sync.m… | 31; 31 US (US-M19-06) |  |
| B7-QT-M19-07 | ⬜ | QT-M19-07 (negative (tayyorlik — smena, moslash)) — Berilgan readiness_policy='all_shifts_closed' va bitta smena ochiq, unda ONEC_SHIFTS_OPEN (block); Berilgan 5 ta tova… | 31; 31 US (US-M19-06) |  |
| B7-QT-M19-08 | ⬜ | QT-M19-08 (negative (preview xeshi)) — Berilgan Buxgalter preview'ni ko'rgan (preview_hash=H1), shu orada D sanali kech offline chek sinxronlandi, qachonki W-43 {preview… | 31; 31 US (US-M19-07) |  |
| B7-QT-M19-09 | ⬜ | QT-M19-09 (negative (ogohlantirish)) — Berilgan preview'da ONEC_Z_REPORT_DIFF ogohlantirishi bor, qachonki W-43 acknowledged_warnings=[] bilan, unda 422 ONEC_WARNINGS_NO… | 31; 31 US (US-M19-07) |  |
| B7-QT-M19-10 | ⬜ | QT-M19-10 (happy (takroriy yuborish)) — Berilgan D partiyasi done, qachonki W-48 bilan o'zgarishsiz revision qurilib tasdiqlansa, unda barcha itemlar skipped (unchanged)… | 31; 31 US (US-M19-08) |  |
| B7-QT-M19-11 | ⬜ | QT-M19-11 (negative (noma'lum natija)) — Berilgan write_object vazifasi lease'da, soxta 1C obyektni yozgan, lekin natija serverga yetmagan (agent jarayoni o'ldirildi — P… | 31; 31 US (US-M19-08) |  |
| B7-QT-M19-12 | ⬜ | QT-M19-12 (unit (GUID vektorlari)) — Berilgan 33 §8.1 test vektorlari (guid_namespace, kind, erp_key → kutilgan UUIDv5, marker matni), qachonki backend onec_guid() va ag… | 31; 31 US (US-M19-08) |  |
| B7-QT-M19-13 | ⬜ | QT-M19-13 (negative (jamlar farqi)) — Berilgan barcha itemlar yozilgan, read_totals natijasida ОРП summasi ERP'dan "12000.00" ga kam, qachonki onec_verify_batch ishlasa,… | 31; 31 US (US-M19-10) |  |
| B7-QT-M19-14 | ⬜ | QT-M19-14 (negative (yopiq 1C davri)) — Berilgan 1C'da 30.09 gacha sana taqiqi, qachonki 29.09 revisioni yuborilsa, unda item ONEC_DATE_PROHIBITED, 1C'ga hech narsa yozi… | 31; 31 US (US-M19-12) |  |
| B7-QT-M19-15 | ⬜ | QT-M19-15 (happy (kech offline chek)) — Berilgan 15.10 done, qachonki 16.10 da 15.10 sanali offline chek /sync/push bilan kelsa, unda posting tranzaksiyasida OneCChangeT… | 31; 31 US (US-M19-11) |  |
| B7-QT-M19-16 | ⬜ | QT-M19-16 (happy (ketma-ketlik)) — Berilgan agent 7 kun poll qilmagan, qachonki Buxgalter partiyani tasdiqlasa (W-43) yoki W-06/W-12 chaqirilsa, unda amal bajariladi (W-… | 31; 31 US (US-M19-15) |  |
| B7-QT-M19-17 | ⬜ | QT-M19-17 (negative (avto-tasdiq)) — Berilgan Buxgalter (onec.settings.manage berilgan), qachonki W-20 auto_approve=true, unda 403 OWNER_ONLY; Egasi yoqqanda ogohlantiri… | 31; 31 US (US-M19-13) |  |
| B7-QT-M19-18 | ⬜ | QT-M19-18 (negative (ma'lumotnoma)) — Berilgan 3 ta tovar 1C'da yo'q, qachonki W-31 taklifi tuzilib onec.refs.create ruxsatisiz W-32 chaqirilsa, unda 403 PERMISSION_DENI… | 31; 31 US (US-M19-05) |  |
| B7-QT-M19-19 | ⬜ | QT-M19-19 (happy (faqat xatolarni qayta)) — Berilgan partiya partial: ОРП ONEC_NEGATIVE_STOCK (1C asl xabari + o'zbekcha izoh), qachonki W-45, unda faqat failed itemlar… | 31; 31 US (US-M19-09) |  |
| B7-QT-M19-20 | ⬜ | QT-M19-20 (happy (bekor qilingan hujjat)) — Berilgan 1C'ga yozilgan kirim ERP'da bekor qilindi, qachonki revision quriladi, unda preview'da ONEC_UNPOST_REQUIRED ogohlant… | 31; 31 US (US-M19-16) |  |
| B7-QT-M19-21 | ⬜ | QT-M19-21 (security (revoke, reassign)) — Berilgan agent W-05 bilan uzildi, qachonki u ≤ 60 s dan keyin A-03 chaqirsa, unda 403 ONEC_AGENT_REVOKED; yangi PK'dagi agent o… | 31; 31 US (US-M19-17) |  |
| B7-QT-M19-22 | ⬜ | QT-M19-22 (negative (drift)) — Berilgan ERP yozgan ОРП 1C'da qo'lda o'zgartirilgan (ВерсияДанных farq qiladi), qachonki onec_drift_check ishlasa, unda onec_reconciliatio… | 31; 31 US (US-M19-18) |  |
| B7-QT-M19-23 | ⬜ | QT-M19-23 (— (1.1 RLS bilan bir xil ruh)) — Berilgan Tenant A agenti tokeni, qachonki A-04/A-05 da Tenant B vazifasining task_id si yoki so'rov tanasida boshqa tenant_id… | 31; 31 M19 — Bosqich 7 |  |
| B7-QT-M19-24 | ⬜ | QT-M19-24 (security (imzo)) — Berilgan vazifa JWS'i o'zgartirilgan (yoki boshqa agent_id/base_id, muddati o'tgan, oq ro'yxatda yo'q kind), qachonki soxta agent 33 §9.11… | 31; 31 US (US-M19-07) |  |
| B7-QT-M19-25 | ⬜ | QT-M19-25 (happy (avto-moslash)) — Berilgan 1C ma'lumotnomalari o'qilgan (W-22), qachonki W-25 auto-match chaqirilsa, unda takliflar exact/probable guruhlarida (match_qu… | 31; 31 US (US-M19-04) |  |
| B7-QT-M19-26 | ⬜ | QT-M19-26 (happy (Telegram xabarlari)) — Berilgan Egasi va Buxgalter Telegram'ga ulangan (onec.view bor), Kassir ulangan (onec.view yo'q), qachonki partiya done bo'lsa,… | 31; 31 US (US-M19-14) |  |
| B7-QT-NFR-14 | ⬜ | QT-NFR-14 (integration (performance, Bosqich 7)) — Berilgan oddiy do'kon (1 kassa, ~300 qatorli ОРП, 3–5 qo'shimcha hujjat), soxta agent va real vaqtli soxta 1C kechikis… | 31; 31 §4 — Bosqich 7 |  |
| B7-QT-NFR-15 | ⬜ | QT-NFR-15 (integration (load, Bosqich 7)) — Berilgan 1 000 soxta agent, qachonki har biri POST /onec-agent/poll long-poll'ni ushlab tursa (25 s), unda api jarayoni barch… | 31; 31 §4 — Bosqich 7 |  |

## MVP'dan keyin

Holat: ✅ 1 · 🟡 2 · ⬜ 0 · ⛔ 0 · ⏭ 21 · jami 24

### MVP'dan keyin — Vazifalar (27)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| BK-T00 | ⏭ | Bosqich 7 — 1C integratsiyasi (yuqorida) — MVP'dan keyingi birinchi bosqich; keyingi 1C profillari (`ut11_uz`, `roznica30_uz`, `uk30_uz`), smena bo'yicha ОРП, narx o'zgarishi/qarzni kechish/boshlang'ich qoldiq hujjatlari — keyinroq (`33-1c-integratsiya.md` §2… | 27 |  |
| BK-T01 | ⏭ | Rasmiy hisobot shakllarini XML eksport qilish va operator orqali topshirish (26 #110). | 27 |  |
| BK-T02 | ⏭ | Didox — ikkinchi `EInvoicePort` adapteri (MVP'da Faktura.uz; asoschi qayta ko'rishi — 26 #167). | 27 |  |
| BK-T03 | ⏭ | Mijozlarga SMS/Telegram qarz xabarlari (US-M08-08). | 27 |  |
| BK-T04 | ⏭ | Android POS (Kotlin) — `28-android-pos.md` 1–4 bosqichlari (FM SDK — 26 #63); karta — `AndroidIntentCardAdapter` (smart-terminaldagi bank to'lov ilovasi, 26 #172–#173) va `SoftPosAdapter` (MayaSoft SDK, 26 #175), bitta `CardTerminalPort` kontrakti (qaror #71). | 27 |  |
| BK-T05 | ⏭ | Ko'p ombor, talab bashorati (AI-09) — 2–3 oylik savdo tarixidan keyin. | 27 |  |
| BK-T06 | ⏭ | O'z AI modelimiz (markaziy GPU server) — yig'ilgan ma'lumot va eval natijalariga qarab. | 27 |  |
| BK-T07 | ⏭ | US-M03-02 (avtomatik chegirma qoidalari), US-M14-02 (nusxalash), US-M17-05 (to'liq eksport, birinchi pullik mijoz chiqib ketishidan oldin) — MVP'dan keyin, tasdiqlangan (qaror #33); ochiq smena ichida kassir topshirish; bitta egasining bir nechta tenanti uchu… | 27 |  |
| BK-T08 | ⏭ | Ko'p bank hisobi (`bank_accounts`) — hozircha yagona `5110` (qaror #49, 26 #90). | 27 |  |
| BK-T09 | ⏭ | Ko'p yuridik shaxsli (turli STIR) tenant qo'llab-quvvatlanishi — MVP'da 1 tenant = 1 yuridik shaxs (26 #38). | 27 |  |
| BK-T10 | ⏭ | AI-02 ovozli buyruq (26 #20), "2+1" aksiyasi (26 #145), ish haqi moduli 6710 bilan (qaror #52). | 27 |  |

### MVP'dan keyin — Hikoyalar (27 → 30)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| BK-US-M08-08 | ⏭ | US-M08-08 — Mijozga SMS/Telegram qarz xabari | 27 Hikoyalar; 30 (Keyin (post-MVP)) |  |
| BK-US-M03-02 | ⏭ | US-M03-02 — Avtomatik chegirma qoidalari | 27 Hikoyalar; 30 (Keyin (post-MVP)) |  |
| BK-US-M14-02 | ⏭ | US-M14-02 — Filialdan filialga narx/chegirma siyosatini nusxalash | 27 Hikoyalar; 30 (Keyin (post-MVP)) |  |
| BK-US-M17-05 | ⏭ | US-M17-05 — Xizmatdan chiqishda barcha ma'lumotni olib ketish | 27 Hikoyalar; 30 (Keyin (post-MVP, Could)) |  |

### MVP'dan keyin — Endpointlar (14/17/18/19/20/33)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| BK-EP-14#17 | ✅ | POST /auth/google/token | 14 §20; Android native Google Sign-In — Android POS MVP'dan keyin (28) | kod: `backend/app/modules/auth/api/signup.py`; test: `backend/tests/integration/test_google_login.py` |
| BK-EP-14#28 | ⏭ | POST/GET /billing/export-my-data | 14 §20; 30 (US API) |  |
| BK-EP-18#11 | ⏭ | GET /api/v1/discount-rules / POST / GET /{id} / PATCH /{id} / POST /{id}/archive | 18 §8.2; 30 (US API) |  |
| BK-EP-18#20 | ⏭ | POST /api/v1/counterparties/{id}/statement-link | 18 §12.7; 30 (US API) |  |
| BK-EP-20#36 | ⏭ | POST /branches/{id}/copy-pricing — Narx/chegirma siyosatini boshqa filialga nusxalash | 20 indeks; 30 (US API) |  |
| BK-EP-20#65a | ⏭ | POST/GET /billing/export-my-data — Tenant to'liq eksporti (ZIP: CSV + manifest.json, qaro… | 20 indeks; 30 (US API) |  |

### MVP'dan keyin — Ekranlar (06/07)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| BK-SCR-BO-05 | ⏭ | BO-05 — Narxlar va chegirma qoidalarini boshqarish | 07; 27/30 |  |

### MVP'dan keyin — Jadvallar / migratsiyalar (12)

| ID | Holat | Band | Manba | Dalil |
|---|---|---|---|---|
| BK-TBL-app.discount_rules | 🟡 | `app.discount_rules` (revizion 0008) | 12; 30 (US jadvallari) | DDL 0008 bor; modul kodi/testi yo'q |
| BK-TBL-app.counterparty_statement_links | 🟡 | `app.counterparty_statement_links` (revizion 0009) | 12; 30 (US jadvallari) | DDL 0009 bor; modul kodi/testi yo'q |

## Manbalar

- `spec/kod-uchun/27-backlog.md`, `30-izchillik-matritsasi.md`, `31-qabul-testlari.md`, `12-db-sxema.md` §6.1, `14` §9/§18/§20, `17` §1, `18` §1, `19`, `20` "Endpoint indeksi", `33` §9.3/§10, `07`, `26` Jadval B.
- Kod: `backend/` (pytest — 462 test), `web/` (vitest — 347, Playwright — 53), B0 commit `e06e9cc` + Bosqich 1 ishchi daraxti (2026-10-17).
- Generator: `spec/implementatsiya/_scripts/gen_holat.py`.
