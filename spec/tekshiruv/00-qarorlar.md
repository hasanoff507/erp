# Tekshiruv qarorlari — ziddiyatlarni hal qilish (koordinator, 2026-10-14)

Qabul agentlari (Opus) fayllari: `qabul-1-faktlar.md`, `qabul-2-texnik.md`, `qabul-3-talablar.md`, `qabul-4-malumotlar-modeli.md`. Ular orasida ziddiyat bo'lsa, **shu fayl ustun turadi**.

| # | Masala | Ziddiyat | Qaror |
|---|---|---|---|
| 1 | Tenant konteksti | qabul-2 va qabul-4 (yakuniy) | **`tenant_transaction(session, tenant_id)`** helper, `autobegin=False`; ichida `SELECT set_config('app.tenant_id', :tid, true)`. `SET LOCAL` ishlatilmaydi. `/sync/push` har voqeani alohida `tenant_transaction`da; worker job'lari majburiy `tenant_id` bilan; scheduler `list_active_tenant_ids()` (SECURITY DEFINER) orqali har tenantga alohida job |
| 2 | Navbat kutubxonasi | qabul-4 matnida arq | **SAQ** (qabul-2), `JobQueue` porti ortida. Hamma joyda arq → SAQ; job imzosida `tenant_id` majburiy |
| 3 | Veb-kassa autentifikatsiyasi | qabul-4 (yakuniy, qabul-2 bilan moslashtirilgan) | Veb-kassa — foydalanuvchi sessiyasi (HttpOnly cookie, 12 soat bo'sh / **7 kun** mutlaq, taxmin); `/sync/push` 401 bersa — qayta kirish oynasi, Dexie/outbox **o'chmaydi**; har voqeada `actor_user_id` (offline PIN bilan tasdiqlangan), server a'zolikni tekshiradi. **Qurilma tokeni faqat Android** (Bearer) |
| 4 | CSRF | qabul-2 | Sinxronizator-token: `GET /api/v1/auth/csrf` → xotirada → `X-CSRF-Token` (namuna loyihadagidek), `/sync/*` uchun ham; Android Bearer — CSRF'dan ozod |
| 5 | Qizil faktura QQS krediti | qabul-3 (X2): `vat_moves.status` qo'shish; qabul-4 (#7): status yo'q, to'lovgacha yozilmaydi | **qabul-4** (append-only saqlanadi). BO-07/BO-10'dagi "kutilayotgan QQS krediti" `einvoices.risk_flag='red'` va to'lanmagan qoldiqdan hisoblanadi (qabul-3 ekran talablari saqlanadi) |
| 6 | Teskari hujjat | eski matn: "teskari hujjat" | **qabul-4**: alohida teskari hujjat yo'q; `status=cancelled` + storno registr qatorlari (`reversal_of_id`) |
| 7 | Saqlash muddati | qabul-3 US-M17-05 / 05-xavfsizlik: 3 yil | **Kamida 5 yil** — O'RQ-404, 29-modda (qabul-1 #7, lex.uz/docs/-2931253). Soliq hujjatlari — 3 yil (SK 84-modda) |
| 8 | Barcode | — | treepoem taqiqlangan; brauzerda bwip-js, serverda python-barcode + zxing-cpp (qabul-2 #3) |
| 9 | Veb-kassa brauzerlari | — | Faqat Chromium (Chrome/Edge, Android Chrome), o'rnatilgan PWA; back-office — barcha zamonaviy brauzerlar (qabul-2 #15) |
| 10 | Yagona QR | — | M01 to'lov turlariga **UzQR (bank yagona QR)** qo'shiladi — yuridik shaxslar uchun 2026-07-01'dan majburiy (PF-246, 3-b); Click/Payme/Uzum — ixtiyoriy (qabul-1 #1) |
| 11 | Aylanma solig'i | — | SK 467-modda; chakana savdo stavkasi aholi punkti toifasiga bog'liq → `branches.settlement_category` (`city_100k_plus` / `other` / `remote_mountain`) + `branch_tax_settings` tarixi (qabul-1 #2) |

| 12 | Fiskal chek raqami | qabul-4 #2 | Qurilma beradi (onlayn ham); server faqat `UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)` bilan tekshiradi; bitta smena — bitta qurilma |
| 13 | Obuna holati | qabul-4 #9 | Yagona manba `subscriptions.status`; `tenants.status` olib tashlanadi |
