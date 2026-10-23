# Qabul tekshiruvi uchun qoldiq ishlar (agentlar xabarlaridan)

1. 17 §15: 33 endi 81 ta ONEC_* kod — yangi: ONEC_BASE_EXCLUSIVE, ONEC_DUPLICATE_REF, ONEC_NO_RIGHTS, ONEC_UNKNOWN, ONEC_NEGATIVE_STOCK_ALLOWED, ONEC_LICENSE_SEPARATE_REQUIRED; ONEC_AGENT_OFFLINE 409 emas — 202 warnings[] ichida. 17 katalogini 33 §12 bilan aynan moslash.
2. 34: yangi kodlar, GUID to'qnashuvi yo'li (ONEC_DUPLICATE_REF), read_metadata `constants`/`queries` payload maydonlari; 33 §13.1 aniqliklari bilan to'liq moslik; #60 Do'kon agenti kengaytmasi bo'limi (fiscal.*, print.*, scale.* vazifa turlari — Bosqich 5).
3. 14–20 agenti topgan, boshqa fayllardagi eskirganlar: 21 (marking `pending_verification`, Vakolat, `FiscalAdapter` nomi → `FiscalPort`, statik QR zaxira), 22 §7 (maskalash ixtiyoriy deyilgan), 23 §8 (UzCloud secret store), 13 §2.18a (komissiya 9410 "taxmin" → 9430), 26 #13 va #10 eski matn, 03 M06 (72 soat), 07 (bank import, sync istisnolari, soliq hisob-kitobi tugmalari/ekranlari).
4. Qaror #53: offline sanoqda qurilma vaqti (counted_at).
5. "taxmin" qolgan: 14 pay-token/admin-token/litsenziya vaqtlari, 15 rol limitlari summasi, 16 soat siljishi chegarasi va 30 kunlik PIN bekor qilish oynasi — D-standart bilan yopish.
6. Ekranlar 41 ta (POS-16 «Uskunalar sozlamasi» qo'shildi), 39 tasi MVP; US 104 ta (US-M01-07). "POS-01…15" → "…16": 00-README, 18 (~879), 24 (~37); 30: "38 ta ekran" → 39, US 104.
7. 15: `devices.revoke` ruxsati mavjudligini tekshirish.
8. 17–20 da 07 havola qilgan endpointlar mavjudligini tekshirish: GET/PATCH /tenant-settings, GET /devices, POST /devices/{id}/revoke, GET /sync-exceptions, GET /recost-jobs, PATCH /einvoices/{id} (risk_flag), POST /reports/scale-plu/export, GET/POST /tax-settlements.
9. 17 §15 message key'lar: fiscal.offline_block_soon, errors.marking_code_duplicate, validation.social_card_details_required; SUPPLIER_OVERPAY_BLOCKED bor.
10. 33 §9.5 probe natija sxemasiga `data.base.session_kind` ('console'|'rdp') qo'shilsin (34 §13.1 #1, license_source tekshiruvi uchun).
11. Ish haqi: 13 da 9410 (sotuvchilar)/9420 (boshqaruv) bo'linishi vs qaror #52 "faqat 9420" — P7 bo'yicha bo'linish to'g'ri; #52 matnini yangilash.
12. 20: tax_settlements endpointlari mavjudligini tekshirish; bank_settlements.net_amount = gross − commission + variance (manfiy variance = kamomad) 20 va 13 bilan mos.
13. 30: `POST /tenant/consents` endpointi 20 da borligini tekshirish.
14. 31: M19 (1C) testlari 33/34 yangilanishlari bilan mosligini tekshirish (ONEC_* kodlar, warnings[]).
15. Statik UzQR offline: QAROR — **faqat online** (16 bilan mos); 21 §9/§9.1 dagi "offline ham" tuzatiladi.
16. Do'kon agenti lokal API xavfsizligi (Origin allow-list + qurilmaga bog'langan token) va POS "Fiskal modul ulanmagan" holati — 21/24 da; 16/18 va 34 §14 bilan moslash.
17. 33 §9.5 / 34 §14: fiscal.* / print.* / scale.* vazifa turlari ro'yxati 21 §16, 23 §4.2 bilan bir xil bo'lsin (sotuv vaqtidagi fiskal/chop — lokal 127.0.0.1 API, server vazifasi emas).
