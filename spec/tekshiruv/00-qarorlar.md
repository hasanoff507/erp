# Tekshiruv qarorlari — ziddiyatlarni hal qilish (koordinator, 2026-10-14)

Qabul agentlari (Opus) fayllari: `qabul-1-faktlar.md`, `qabul-2-texnik.md`, `qabul-3-talablar.md`, `qabul-4-malumotlar-modeli.md`. Ular orasida ziddiyat bo'lsa, **shu fayl ustun turadi**.

| # | Masala | Ziddiyat | Qaror |
|---|---|---|---|
| 1 | Tenant konteksti | qabul-2: `tenant_transaction()` + `autobegin=False`; qabul-4: `after_begin` listener + `session.info["tenant_id"]` | **qabul-4 varianti** (`after_begin` + `set_config('app.tenant_id', :tid, true)`), chunki har qanday tranzaksiyani qamraydi. `/sync/push` har voqeani alohida tranzaksiyada qayta ishlaydi. Ikkalasida ham `SET LOCAL` ishlatilmaydi |
| 2 | Navbat kutubxonasi | qabul-4 matnida arq | **SAQ** (qabul-2), `JobQueue` porti ortida. Hamma joyda arq → SAQ; job imzosida `tenant_id` majburiy |
| 3 | Veb-kassa autentifikatsiyasi | qabul-2: sessiya 401 → qayta kirish, outbox saqlanadi; qabul-4: sinxron uchun alohida qurilma tokeni `erp_device` | **Ikkalasi birga**: `/sync/*` — qurilma tokeni (qabul-4); back-office so'rovlari — foydalanuvchi sessiyasi (12 soat bo'sh / 7 kun mutlaq, taxmin), 401 da qayta kirish oynasi, Dexie tozalanmaydi (qabul-2) |
| 4 | CSRF | qabul-2: sinxronizator-token `GET /auth/csrf`; qabul-4: `/sync/*` uchun SameSite=Strict + `X-Device-Id` | **Ikkalasi birga**: back-office — sinxronizator-token (namuna loyihadagidek); `/sync/*` — SameSite=Strict + `X-Device-Id`; Android Bearer — CSRF'dan ozod |
| 5 | Qizil faktura QQS krediti | qabul-3 (X2): `vat_moves.status` qo'shish; qabul-4 (#7): status yo'q, to'lovgacha yozilmaydi | **qabul-4** (append-only saqlanadi). BO-07/BO-10'dagi "kutilayotgan QQS krediti" `einvoices.risk_flag='red'` va to'lanmagan qoldiqdan hisoblanadi (qabul-3 ekran talablari saqlanadi) |
| 6 | Teskari hujjat | eski matn: "teskari hujjat" | **qabul-4**: alohida teskari hujjat yo'q; `status=cancelled` + storno registr qatorlari (`reversal_of_id`) |
| 7 | Saqlash muddati | qabul-3 US-M17-05 / 05-xavfsizlik: 3 yil | **Kamida 5 yil** — O'RQ-404, 29-modda (qabul-1 #7, lex.uz/docs/-2931253). Soliq hujjatlari — 3 yil (SK 84-modda) |
| 8 | Barcode | — | treepoem taqiqlangan; brauzerda bwip-js, serverda python-barcode + zxing-cpp (qabul-2 #3) |
| 9 | Veb-kassa brauzerlari | — | Faqat Chromium (Chrome/Edge, Android Chrome), o'rnatilgan PWA; back-office — barcha zamonaviy brauzerlar (qabul-2 #15) |
| 10 | Yagona QR | — | M01 to'lov turlariga **UzQR (bank yagona QR)** qo'shiladi — yuridik shaxslar uchun 2026-07-01'dan majburiy (PF-246, 3-b); Click/Payme/Uzum — ixtiyoriy (qabul-1 #1) |
| 11 | Aylanma solig'i | — | SK 467-modda; chakana savdo stavkasi aholi punkti toifasiga bog'liq → `branches.settlement_category` (`city_100k_plus` / `other` / `remote_mountain`) + `branch_tax_settings` tarixi (qabul-1 #2) |
