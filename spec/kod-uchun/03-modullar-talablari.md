# Modullar funksional talablari (18 MVP modul + M19)

**Maqsad:** 19 modulning funksional talablari — 18 MVP moduli (M01–M18) va MVP'dan keyingi M19 «1C integratsiyasi» (Bosqich 7): foydalanuvchi hikoyalari, qabul mezonlari, offline xatti-harakati va chekka holatlar. · **Kim uchun:** hammasi (backend + frontend). · **Bog'liq fayllar:** 02, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 25, 26, 27, 33. · **Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. 19 modulning har biri uchun maqsad, kamida 3 foydalanuvchi hikoyasi (US-Mxx-nn; jami 105 ta, M01 — 8 ta), qabul mezonlari (Given/When/Then yoki tekshiriladigan ro'yxat), davlat tizimlari bog'liqligi, offline xatti-harakati va chekka holatlar yozilgan (shu jumladan M15–M19). MVP — M01–M18; **M19 «1C integratsiyasi» — MVP'dan keyin, Bosqich 7** (qaror #37), yagona manbasi `33-1c-integratsiya.md`.
2. **M01 Kassa** — eng murakkab modul: offline-first (append-only event-log, 48 soatda fiskal blok — VMQ-943 2-ilova 6-band, qaror #43), markirovka (kod fiskal chek ichida OFD orqali, qaror #62), karta rekvizitlari va UzQR (qaror #64), integratsiyalangan karta terminali (qaror #71) hamda uskunalar sozlamasini (qaror #60) birlashtiradi.
3. **M10 QQS** va **M12 Hisobotlar** — 2026-yildagi eng katta arxitektura o'zgarishini (davlat hisobotni o'zi tuzadi, **5 ish kuni** ichida (hisobot topshirish muddatidan kechiktirmay) tuzatish — Soliq kodeksi 5-modda 7-qism, 81-modda, O'RQ-1108, lex.uz/docs/-7944527) tashuvchi modullar; ommaviy API yo'q (yagona kanal — shaxsiy kabinet), shuning uchun davlat hisoboti fayl sifatida yuklanadi va tizim solishtiradi.
4. Barcha davlat integratsiyalari port+adapter ortida: fiskal — `FiscalPort` (hamkor bulut API yoki Do'kon agenti → FM → OFD, MVP'da `ERP_FISCAL_PROVIDER=fake`, qaror #60), e-faktura — Faktura.uz (MVP), Didox ochiq API bilan zaxira, e-TTN — EDO operatori orqali (ichki ko'chirishda ham, qaror #63), markirovka — `MarkingPort` faqat kirim/tekshiruv/qaytarish/hisobdan chiqarish uchun. Tashqi javob kutayotgan qismlar — hujjat oxiridagi ro'yxat.
5. Offline xatti-harakati faqat **M01 (kassa)** uchun to'liq majburiy talab; boshqa modullarda (M04, M05, M06, M07) offline faqat qisman (mahalliy qoralama, keyin sinxronlash) qo'llab-quvvatlanadi, chunki ular odatda internet mavjud joyda (ofis/ombor) bajariladi.
6. Mavjud ERP tizimlarining jonli ma'lumotlar modeli faqat **struktura namunasi** sifatida ishlatildi — O'zbekiston-specific qiymatlar (QQS 12%, MXIK/IKPU, Asl belgisi) hech qachon ulardan emas, faqat O'zbekiston qonunchiligi manbalaridan olindi (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, 2-band).
7. Har bir modulda kamida bitta chekka holat davlat tizimi bilan bog'liq xavfni (markirovka jarimasi, offline sinxronlash kechikishi, AI xavf-baholash) aks ettiradi — bu `11-raqobatchilar-kamchiliklari.md`dagi real shikoyatlardan kelib chiqadi.
8. Limitlar, muddatlar va sozlamalar standart qiymat sifatida berilgan (qarorlar #23, #43–#64); faqat tashqi javob kutayotgan bandlar hujjat oxirida `26` ga havola bilan.

---

## M01 — Kassa (POS)

**Maqsad**: mijozga tez, aniq va fiskal talablarga mos sotuv amalga oshirish, internet bo'lmaganda ham ishlashni davom ettirish.

### Foydalanuvchi hikoyalari

**US-M01-01**: Kassir sifatida tovarni skanerlab/tanlab chek yaratmoqchiman, mijozga tez xizmat ko'rsatish uchun.
- Given kassir smena ochgan, When tovar shtrix-kodi skanerlanadi yoki qo'lda tanlanadi, Then tovar chekka narx va MXIK kodi bilan qo'shiladi.
- Given chekda bir yoki bir nechta tovar bor, When kassir to'lovni tanlaydi (naqd/karta/yagona QR (UzQR, bank)/Payme/Click/Uzum yoki aralash), Then chek yakunlanadi va fiskal belgi+QR-kod bilan **chop etiladi** (standart — bosma chek; chekda to'lov shakli: naqd / bank kartalari / QR-kodli to'lov / aralash — VMQ-943 1-ilova 7-band). To'lov qaysi usulda bo'lmasin (shu jumladan Click/Payme/Uzum/UzQR), fiskal chekni bizning kassa chiqaradi (VMQ-943 1-ilova 6-band; 1a-ilova 2-band).
- Given printer ishlamayapti yoki xaridor elektron chek so'radi, When kassir "Elektron chek"ni tasdiqlaydi, Then chek ekranda `ofd.soliq.uz` QR havolasi (yoki Telegram/SMS havola) sifatida beriladi, `fiscal_receipts.delivery='electronic'` va `delivery_reason` audit qilinadi; elektron chek — faqat zahira.
- (qaror #30) **Istisno — "Nasiya" to'lov turi**: to'lov to'liq nasiya bo'lsa, Then sotuv hujjati (qoldiq −, mijoz qarzi +) yoziladi, lekin **fiskal chek shu zahotda chiqarilmaydi** (sotuv `posted`, fiskal holat `deferred` (javobdagi `fiscal.status`), `fiscal_receipts` yozuvi yo'q) — batafsil qoida va sabab `M08 — Nasiya` bo'limida.
- Given kassaga integratsiyalangan karta terminali bog'langan, When kassir "Karta"ni tanlaydi, Then summa terminalga avtomatik yuboriladi va karta rekvizitlari terminal natijasidan olinadi — batafsil US-M01-08 (qaror #71).
- (qaror #23, tavsiya #6, qaror #64, #71) **Terminalsiz karta (rekvizitsiz)** — kassaga integratsiyalangan terminal bog'lanmagan bo'lsa asosiy usul, bog'langan bo'lsa faqat zaxira (US-M01-08, `card_manual_fallback` siyosati): Given do'konda kassaga integratsiyalanmagan karta terminali bor (yoki umuman yo'q) — karta bilan ishlash do'konning o'z ishi, When kassir "Karta" to'lov turini tanlaydi (online va offline'da ham ruxsat, tasdiqsiz; `sale_payments.method='card'`, `card_entry_mode='manual'`, `manual_reason='standalone_terminal'`), Then faqat summa yoziladi — ilova hech qanday karta ma'lumotini so'ramaydi va qabul qilmaydi: `card_type`, `card_type_source`, `card_mask`, `rrn`, `approval_code`, `card_scheme`, `card_terminal_transaction_id`, `terminal_ref` — `NULL` (API'da qiymat berilsa — `422 VALIDATION_ERROR`); POS faqat "Karta terminalsiz qabul qilindi" tasdig'ini ko'rsatadi; fiskal chek "bank kartalari" to'lov shakli bilan, karta turi/niqobi/RRN'siz chiqadi (bunday chekning qonuniy yetarliligi — 26 #178); smena yopilganda Z-hisobotda "Karta (terminalsiz)" jami alohida chiqadi (M16, US-M16-02/03), Egasi kun oxirida bank ko'chirmasi bilan summa/sana bo'yicha solishtiradi.

**US-M01-02**: Kassir sifatida internet bo'lmaganda ham savdo qilishni, keyin avtomatik sinxronlanishini istayman.
- Given internet aloqasi yo'q, When kassir chek yaratadi, Then chek mahalliy append-only jurnalga yoziladi va "offline" belgisi bilan ko'rsatiladi.
- Given internet qaytdi, When tizim avtomatik sinxronlanadi, Then barcha offline cheklar OFD'ga yuboriladi (VMQ-943 1-ilova 31-band).
- (qaror #43) Given shu kassada OFD tasdig'ini olmagan eng eski chekning `created_at`idan 24 soat o'tdi, Then status panel 🟡 sariq; 40 soatda 🔴 qizil va Egasiga M18 (Telegram) xabari; 46 soatda har yangi chek oldidan yopiladigan modal "2 soatdan keyin kassa bloklanadi" (sotuv to'xtamaydi).
- (qaror #43) Given 48 soat o'tdi, When kassir yangi fiskal chek (sotuv, qaytarish, `debt_settlement`, kredit) yaratmoqchi bo'ladi, Then amal `FISCAL_OFFLINE_48H_BLOCKED` bilan rad etiladi (VMQ-943 2-ilova 6-band, VMQ-23 tahriri), `audit_log` yoziladi va Egasiga M18 xabari ketadi; sinxron/qayta yuborish, qoldiqni ko'rish, smenani yopish va naqd sanash ishlayveradi; barcha kutilayotgan cheklar OFD tasdig'ini olgach blok avtomatik yechiladi; qo'lda chetlab o'tish yo'q.

**US-M01-03**: Kassir sifatida markirovkalangan tovar (suv, ichimlik, tamaki va h.k.) sotishda kodni tekshirishni istayman.
- (qaror #62) Given tovar Asl belgisi bilan markirovkalangan, When kassir DataMatrix kodini skanerlaydi, Then kod chek qatoriga yoziladi va **fiskal chek ichida** OFD orqali Asl belgisiga uzatiladi (VMQ 833 75–77-band) — sotuv uchun CRPT API'ga alohida "sotildi" chaqiruvi yo'q.
- (qaror #62) Given `MARKING_PRECHECK=warn` (standart; tenant sozlamasi `off|warn|block`) va internet bor, When sotuvdan oldingi tekshiruv kodni yaroqsiz/muddati o'tgan deb qaytaradi, Then kassirga ogohlantirish ko'rsatiladi, `audit_log` yoziladi va sotuv davom etadi; `block` rejimida sotuv rad etiladi.
- Given kod shu chekda takrorlangan yoki tenantda avval sotilgan (lokal sinxronlangan `marking_codes`), Then qator rad etiladi (PQ-190 7(в)(ii)); markirovkali tovar kodsiz chekka qo'shilmaydi.
- (qaror #17) Given internet yo'q (offline) va tovar narxi qurilmada ma'lum bo'lsa (keshlangan katalog narxi, M09), When kassir DataMatrix kodini skanerlaydi, Then sotuv **ruxsat etiladi** — lokal format va takror-kod nazoratidan o'tgan kod chekka yoziladi, FM chekni offline imzolaydi va kod chek bilan OFD'ga yuboriladi (batafsil — Offline xatti-harakati, pastda).
- Given internet yo'q va tovar narxi qurilmada ma'lum emas (hali sinxronlanmagan yangi tovar), When kassir shu tovarni sotishga harakat qiladi, Then sotuv **ruxsat etilmaydi** — narx online bo'lganda sinxronlangandan keyin sotiladi.

**US-M01-04**: Kassir sifatida smenani ochish va yopishni (Z-hisobot) istayman.
- Given ish kuni boshlanadi, When kassir boshlang'ich naqd summani kiritadi, Then smena "ochiq" holatga o'tadi.
- Given smena yakunlanmoqda, When kassir "smenani yopish"ni bosadi, Then Z-hisobot generatsiya qilinadi va OFD'ga yuboriladi.

**US-M01-05**: Kassir sifatida yuridik shaxs bo'lgan do'konda mijozdan bank tomonidan generatsiya qilingan yagona QR kod (UzQR) orqali to'lov qabul qilishni istayman, chunki 2026-07-01'dan bu majburiy (PF-246-son, 10.12.2025, 3-band "b").
- Given tenant yuridik shaxs va filialga bank tomonidan berilgan yagona QR (statik yoki dinamik) ulangan, When kassir to'lov usuli sifatida "Yagona QR (UzQR)"ni tanlaydi, Then dinamik QR'da chek summasi bilan QR ko'rsatiladi va bank tasdig'i kelgach chek yakunlanadi; statik QR'da kassir to'lovni qo'lda tasdiqlaydi (pastda).
- Given tenant yuridik shaxs va 2026-07-01 yoki undan keyingi sana, When filialda yagona QR sozlanmagan, Then tizim Egasi va kassirga "Yagona QR ulanmagan — savdo qoidalarini buzish xavfi" ogohlantirishini ko'rsatadi (sotuvni bloklamaydi).
- (qaror #64) Given filialda **statik** UzQR (`qr_type='static'`), When mijoz o'z telefonidan to'laydi, Then kassir to'lovni qo'lda tasdiqlaydi (**faqat online** — offline'da statik UzQR tasdig'i yo'q, `16-offline-sync.md`) (ixtiyoriy tranzaksiya raqami bilan, `provider_tx_id` majburiy emas) va chek "QR-kodli to'lov" shakli bilan yakunlanadi; tushum 5710 orqali `bank_settlements` (BO-24) bilan solishtiriladi.
- (qaror #64) Given **dinamik** UzQR (`qr_type='dynamic'`), Then `UzqrPort` orqali kassa uchun QR yaratiladi (har kassaning o'z API kaliti) va bank tasdig'i kelgach chek yakunlanadi, `provider_tx_id` majburiy; real adapter CBU/MUNIS yoki ekvayer bank POS API hujjati kelgach yoziladi, ungacha stub.
- Given tenant yakka tartibdagi tadbirkor (`tenants.legal_form='sole_proprietor'`), When sozlamalar ochiladi, Then QR to'lov **majburiy** deb ko'rsatiladi (PQ-247 7-band "a", 2026-01-01 dan): YTT uchun talab to'lov tashkiloti platformasidagi maxsus QR (Click/Payme/Uzum) bilan bajariladi, bank UzQR shart emas; QR sozlanmagan bo'lsa yuqoridagi ogohlantirish chiqadi.
- Yagona QR Click/Payme/Uzum'ning o'rnini bosmaydi: ular qo'shimcha kanal sifatida qoladi. Barcha QR/onlayn to'lovlarda provayder tomonidagi avtomatik fiskallashtirish tenant kabinetida o'chiq bo'lishi shart (BO-14 tekshiruv bandi); Click'ga tayyor chek havolasi `submit_qrcode` bilan yuboriladi.

**US-M01-07** (qaror #60): Kassir/Egasi sifatida kassa qurilmasida chek printeri va tarozini bir marta sozlab, sinov chek chiqarishni istayman.
- Given POS-16 "Uskunalar sozlamasi" ochildi, When "Printerni aniqlash" bosiladi, Then transport avtomatik aniqlanadi: Web Serial → WebUSB → tizim printeri (Chrome/Edge desktop va Android Chrome); BLE printer — Web Bluetooth; LAN raw 9100 (ESC/POS) printer — faqat Do'kon agenti orqali (brauzer xom TCP ocha olmaydi); iOS — bulut printer (Star TSP143IV CloudPRNT, Epson TM-m30III Server Direct Print).
- Given printer tanlandi, When "Sinov chek" bosiladi, Then "Ўзбекистон Қўқон Ғалла Ҳисоб / Oʻzbekiston gʻalla" matni chiqadi: kod sahifa `cp866`, matnda Қ/Ғ/Ҳ bo'lsa raster rejim avtomatik yoqiladi, U+02BB (ʻ) `'` ga almashtiriladi.
- Sozlama qurilma-lokal saqlanadi (boshqa kassaga ko'chmaydi); printer topilmasa — elektron chek zahira (US-M01-01).
- Tarozi: yorliqli tarozi kodi skanerlanadi (US-M09-06), prefikslar do'kon sozlamasida (`weight_barcode_templates`, BO-14); yorliqsiz kassa tarozisidan jonli og'irlik (Web Serial) — MVP'dan keyin; qo'lda og'irlik kiritish — doimiy zahira.

**US-M01-08** (qaror #71): Kassir sifatida karta to'lovida summani do'kondagi bank terminaliga avtomatik yuborib, natijani (tasdiq, niqoblangan karta raqami, RRN, tasdiq kodi) qo'lda yozmasdan olishni istayman — xato va kutish kamaysin.
- Given kassaga integratsiyalangan karta terminali bog'langan (BO-12, `app.card_terminals.cash_register_id`) va terminal holati `online`, When kassir POS-03'da "Karta"ni tanlaydi, Then POS `CardTerminalPort.purchase` ni yangi `attempt_id` (UUIDv7) bilan chaqiradi (Windows veb-kassada — Do'kon agenti orqali LAN/Wi-Fi'dagi terminalga), ekranda qadamlar ko'rsatiladi: "Summa yuborildi" → "Mijoz kartani tegizadi / PIN" → "Bank javobi" → "Fiskal chek"; karta raqami, RRN va karta turi maydonlari kassir tomonidan kiritilmaydi ("terminaldan keladi").
- Given terminal `approved` qaytardi va tasdiqlangan summa so'ralgan summaga teng, Then `sale_payments` qatori `card_entry_mode='integrated'`, `card_terminal_transaction_id`, `rrn`, `card_mask`, `approval_code`, `card_scheme` bilan to'ldiriladi; fiskal chek kassir bosmasdan avtomatik chiqadi (to'lov shakli "bank kartalari", `card_type`, `card_mask`, `rrn`), keyin `sale.created`. Tartib qat'iy: karta tasdig'i → fiskal chek → `sale.created`.
- Given natijada `card_type` yo'q, Then u BIN bo'yicha `platform.card_bin_rules` dan aniqlanadi; topilmasa `card_type='unknown'` — kassir hech narsa tanlamaydi va yozmaydi; manba `card_type_source` (`terminal|bin_table`) da saqlanadi.
- Given tasdiqlangan summa so'ralgan summadan farq qiladi, Then to'lov qabul qilinmaydi (`CARD_AMOUNT_MISMATCH`), tranzaksiya avtomatik `void` qilinadi (`card.void.auto`) va kassirga xabar ko'rsatiladi.
- Given terminal rad etdi yoki terminalda bekor qilindi (`status='declined'`, `CARD_DECLINED`), Then rad sababi (`decline_message`) ko'rsatiladi, chek ochiq qoladi; kassir "Qayta yuborish" (yangi `attempt_id` bilan yangi urinish) yoki boshqa to'lov usulini tanlaydi.
- Given kutish paytida kassir "Terminalda bekor qilish"ni bosadi, Then terminaldagi kutish bekor qilinadi (`cancel-pending`), urinish `declined` bo'lib yakunlanadi (`decline_code` — bekor qilish).
- Given `purchase` taymauti tugadi yoki aloqa uzildi, Then urinish `unknown` holatiga o'tadi (`CARD_TERMINAL_TIMEOUT` → `CARD_OUTCOME_UNKNOWN`); `purchase` **hech qachon avtomatik takrorlanmaydi**: POS avval `get_status(attempt_id)` / `get_last_transaction` bilan natijani so'raydi; natija aniqlanmaguncha shu chekka yangi karta urinishi bloklanadi ("Terminal javobini tekshiring"). Natija aniqlanmasa, Menejer/Egasi PIN bilan (ApprovalDialog, `kind='card_manual_entry'`, `card.manual_entry.approve`) terminal chekiga qarab to'lov o'tgan-o'tmaganini tasdiqlaydi — hech narsa yozmaydi: o'tgan bo'lsa tranzaksiya `status='approved'`, `resolved_by='manager'`, `approved_amount` = summa, `rrn`/`card_mask`/`approval_code`/`card_type` `NULL` qoladi; to'lov qatori `card_entry_mode='manual'`, `manual_reason='unknown_result'`, rekvizitsiz, `card_terminal_transaction_id` `NULL`, tranzaksiya hujjatga `card_terminal_transactions.doc_type/doc_id` orqali bog'lanadi; o'tmagan bo'lsa — `declined` (`decline_code='not_found'`); audit `card.outcome.resolved_manual`.
- Given karta tasdiqlangan, lekin fiskal chek chiqmadi, Then sotuv "to'lov qabul qilingan, chek kutilmoqda" holatida qoladi (savat yo'qolmaydi), fiskal qayta urinish mavjud qoidalar bo'yicha; kassir sotuvni bekor qilsa — karta tranzaksiyasi avtomatik `void` qilinadi (settlementgacha, `card.void.auto`), aks holda `refund`; `void` muvaffaqiyatsiz bo'lsa — `CARD_VOID_FAILED` (audit `card.void.failed`), sotuv bekor qilinmaydi va Menejerga ogohlantirish.
- Given terminal `offline`/`error` (`CARD_TERMINAL_UNREACHABLE`) yoki Do'kon agenti ulanmagan, Then integratsiyalangan "Karta" tugmasi sababi bilan o'chiriladi va "terminalsiz karta (rekvizitsiz)" — to'lovni ilovadan tashqarida qabul qilingan deb belgilash — `tenants.settings.card_manual_fallback` siyosati bo'yicha taklif qilinadi: `allow` — kassir o'zi belgilaydi; `manager_approval` (standart) — Menejer/Egasi PIN tasdig'i (`approval kind='card_manual_entry'`, ruxsat `card.manual_entry.approve`; offline'da lokal PIN tasdig'i) talab qilinadi, tasdiqsiz yuborilsa `CARD_MANUAL_APPROVAL_REQUIRED`; `forbid` — terminalsiz karta yopiq (`CARD_MANUAL_NOT_ALLOWED`). Siyosat faqat faol integratsiyalangan terminal bog'langan kassaga taalluqli; terminal bog'lanmagan kassada terminalsiz karta har doim tasdiqsiz ruxsat (`manual_reason='standalone_terminal'`). Terminalsiz kartada `card_entry_mode='manual'` va `manual_reason` (`terminal_offline|terminal_error|unknown_result|standalone_terminal`) majburiy, karta rekvizitlari yo'q (`NULL`), audit `card.manual_entry` yoziladi.
- Given aralash to'lov, Then har bir karta qismi alohida `attempt_id` va alohida `sale_payments` qatori bilan yuboriladi.
- Given do'kon interneti yo'q, lekin Do'kon agenti va terminal ishlayapti, Then integratsiyalangan karta to'lovi ishlaydi (terminal bankka o'z kanali bilan chiqadi); natija `sale.created` voqeasi ichida (`payments[].card_result`) navbatga yoziladi va sinxronlanganda serverga boradi.
- Given smena yopilmoqda, Then shu smenada hal qilinmagan (`pending`/`unknown`) karta urinishi bo'lsa smena yopilmaydi (`CARD_OUTCOME_UNKNOWN` — avval holat so'rovi yoki menejer yopishi); har bir bog'langan terminal uchun `settlement` chaqiriladi (`shift.closed.card_settlements[]`); natija (`app.card_terminal_settlements`) Z-hisobotdagi "Karta (integratsiyalangan)" jami bilan solishtiriladi, farq bo'lsa ogohlantirish (`card.settlement.mismatch`).

**US-M01-06** (qaror #18): Buxgalter sifatida fiskal chek bilan allaqachon sotilgan tovarga keyinroq yuridik shaxs (B2B) mijoz e-faktura so'rasa, shu sotuv uchun chiquvchi e-faktura chiqarishni istayman.
- Given tovar fiskal chek bilan (B2C yoki avvaldan e-fakturasiz) sotilgan, When mijoz (endi yuridik shaxs sifatida) keyinroq shu xaridga e-faktura talab qiladi, Then Buxgalter BO-15'da asl chekni tanlab yangi chiquvchi e-faktura yaratadi — bu e-faktura `einvoices.related_doc` orqali asl chekka bog'lanadi.
- Given e-faktura chekka bog'langan, Then QQS **ikkinchi marta hisoblanmaydi** — e-faktura faqat asl chekda allaqachon hisoblangan QQS summasini rasmiylashtiradi (hujjat ko'rinishida); `ledger_entries`/`vat_moves` registrlariga yangi yozuv qo'shilmaydi (append-only saqlanadi), bog'lanish faqat hujjat darajasida `einvoices.related_doc` orqali JOIN bilan quriladi (`13-provodka-qoidalari.md` §2.22).
- Given e-faktura E-IMZO bilan imzolanib EDO operatoriga yuborilgan, Then chek va e-faktura o'zaro ikki tomonlama ko'rinadi (chekdan e-fakturaga, e-fakturadan chekka).

### Davlat tizimlari bog'liqligi
OFD (fiskal operator — "Yangi texnologiyalar" DUK), Asl belgisi (CRPT Turon), MXIK (chekning majburiy rekviziti), 2026-07-01'dan yuridik shaxslar uchun bank tomonidan generatsiya qilingan yagona QR kod (UzQR) orqali to'lov qabul qilish majburiy (PF-246-son, 10.12.2025, 3-band "b", [lex.uz/uz/docs/-7897630](https://lex.uz/uz/docs/-7897630); CBU 5/11-son qoidalar); YTT uchun to'lov tashkiloti maxsus QR'i (PQ-247); virtual kassa UzQR va karta to'lov tizimlariga ulangan bo'lishi kerak (VMQ-943 2-ilova 6-band, VMQ-393 tahriri) va mahsulot sifatida "barcha bank kartalari va QR-kodlar orqali to'lovlarni to'g'ridan-to'g'ri shu qurilma orqali qabul qilish imkoniyati"ga ega bo'lishi shart (VMQ-943 2-ilova 6-band 10-xatboshi, 21.07.2026 dan) — shuning uchun integratsiyalangan karta terminali (US-M01-08, qaror #71); terminal cheki bilan birga fiskal chek beriladi (VMQ-943 1-ilova 6-band); Click/Payme/Uzum — qo'shimcha kanallar.

**Fiskal arxitektura** (qaror #60): `FiscalPort` ikki adapter turini qo'llaydi — (a) hamkor bulut API, (b) **Do'kon agenti** (do'kon Windows kompyuteridagi lokal dastur) → fiskal modul (FM) → OFD. MVP kodi `ERP_FISCAL_PROVIDER=fake` bilan yoziladi; real adapter — hamkor javobidan keyin (Bosqich 5). FM chekni offline ham imzolaydi; FM bergan raqam `fm_receipt_seq` alohida saqlanadi. iOS'da fiskal chek faqat hamkor bulut rejimida mumkin, aks holda iOS — back-office va elektron chek zahirasi.

**Fiskal yo'l** (qaror #23, tavsiya #2): birinchi kundanoq o'z virtual kassamizni Davlat reyestriga kiritish arizasi boshlanadi (VMQ-943, 4-ilova: operator xulosasi 10 ish kuni va Kiberxavfsizlik markazi ekspertizasi 15 ish kuni parallel, DSQ qarori 20 ish kuni — reja 35 ish kuni, eng yomon 45); ariza tasdiqlanguncha pilot (10–20 do'kon) bitta reyestr hamkori (Multikassa yoki E-POS Communicator) orqali o'tkaziladi, hamkor haqini biz to'laymiz — mijozga ko'rinmaydi (`05-mvp-chegarasi.md`, §3.3 va §5).

**Markirovka (Asl belgisi)** (qaror #62): chakana sotuv va xaridordan qaytarishda kod fiskal chek orqali OFD → Asl belgisiga ketadi, sotuv CRPT API'ga bog'liq emas. CRPT xTrace API (har do'konning o'z API kaliti, `crpt_api_key` tenant sirida) faqat kirim qabuli (M07), ixtiyoriy sotuvdan oldingi tekshiruv, yetkazib beruvchiga qaytarish va hisobdan chiqarish uchun ishlatiladi.

### Offline xatti-harakati
Majburiy: append-only event-log (outbox naqshi); offline ogohlantirish shkalasi va 48 soatdagi fiskal blok (qaror #43, US-M01-02). Offline chek qonuniy (VMQ-943 1-ilova 31-band). (qaror #17, #62) **Markirovkalangan tovarni offline sotish ruxsat etiladi**, agar tovar narxi qurilmada ma'lum bo'lsa (keshlangan katalog narxi, M09): DataMatrix kod qurilmada format/nazorat raqami va **lokal takror-kod nazorati** (qurilma + tenant bo'yicha sinxronlangan `marking_codes`) bilan tekshiriladi, kod chekka yoziladi, FM chekni offline imzolaydi va kod chek bilan OFD'ga yuboriladi; sotuvdan oldingi online tekshiruv offline'da o'tkazib yuboriladi. Tovar narxi qurilmada ma'lum **bo'lmasa** — offline sotuv ruxsat etilmaydi. Qaytarish/ko'chirish siyosati — M02/M06'da.

### Chekka holatlar
- Internet savdo o'rtasida uzilsa — chek offline rejimga avtomatik o'tishi kerak, mijoz kutib qolmasligi uchun.
- Fiskal modul texnik xatosi — chek berilmasligi huquqiy javobgarlik keltiradi (SK 221-modda); 48 soatlik blokda yangi sotuv `FISCAL_OFFLINE_48H_BLOCKED` bilan to'xtaydi (qaror #43).
- (qaror #71) Integratsiyalangan karta to'lovi natijasi noma'lum (`unknown`) qolsa — shu chek uchun yangi `purchase` bloklanadi, natija `get_status` bilan aniqlanadi; ikki marta yechib olishning oldini olish — `attempt_id` idempotentligi (agent jurnali va `app.card_terminal_transactions` da UNIQUE, `id = attempt_id`).
- Aralash to'lov (qisman naqd + qisman karta) qo'llab-quvvatlanishi kerak. (qaror #30) **Aralash to'lov, qisman nasiya bo'lsa**: naqd/karta/QR qismiga **darhol** fiskal chek chiqariladi, nasiya qismiga esa — qarz **to'langan paytda** (`M08`, debt_settlement) alohida fiskal chek.
- Bir nechta kassa bir smenada parallel ishlashi (filial/do'kon ichida bir nechta POS).
- Yagona QR to'lovi bank tasdig'i kelmay qolsa (internet uzilishi yoki to'lov kechikishi) — chek "to'lov kutilmoqda" holatida qoladi, kassir boshqa to'lov usuliga o'tishi yoki bekor qilishi mumkin; ikki marta to'lov tushishining oldini olish uchun `provider_tx_id` bo'yicha idempotentlik (dinamik QR va Click/Payme/Uzum).
- To'lovdan oldin qator o'chirilsa yoki chek bekor qilinsa (`sales.void`) — fiskal chek yo'q, lekin bekor qilingan qatorlar va summa `sale.draft_voided` voqeasi bilan audit uchun serverga yuboriladi; smena hisobotida bekor qilishlar soni va summasi ko'rsatiladi.
- Chekni qayta chop etish — nusxada "NUSXA" belgisi, har qayta chop etish audit jurnaliga yoziladi (kim, qachon, qaysi chek); son cheklanmaydi.
- (qaror #18) Chek bilan sotilgan tovarga keyinroq yuridik shaxs mijoz e-faktura so'rasa — bu **qo'llab-quvvatlanadi** (US-M01-06): shu chekka bog'langan chiquvchi e-faktura yaratiladi (`einvoices.related_doc`), QQS ikkinchi marta hisoblanmaydi.
- (qaror #21) **iPhone/iPad (iOS)**: kassa/back-office **o'rnatilgan PWA** sifatida (Home Screen'ga qo'shilgan) ishlaydi. iOS'da chek chop etish faqat **bulut printer** (Star TSP143IV — CloudPRNT, Epson TM-m30III — Server Direct Print; Toshkentda ~5,1–7,1 mln so'm) orqali — iOS Safari/PWA USB/Bluetooth printer ulanishini qo'llab-quvvatlamaydi; printer bo'lmasa "faqat elektron chek" rejimi ogohlantirish bilan ishlaydi (elektron chek — zahira, US-M01-01). iOS'da fiskal chek faqat hamkor bulut rejimida (qaror #60). **Chrome/Edge (Windows, Android Chrome)** — Web Serial/WebUSB/Web Bluetooth (BLE), tizim printeri, LAN raw 9100 printer (Do'kon agenti orqali) va bulut printerlarni qo'llab-quvvatlaydi (US-M01-07, `06-ekranlar-umumiy.md` §1.6).

---

## M02 — Qaytarish

**Maqsad**: mijozdan tovarni qaytarib olish va pul/balansni to'g'ri tuzatish.

### Foydalanuvchi hikoyalari

**US-M02-01**: Kassir sifatida mijozdan tovarni asl chek bo'yicha qaytarib olishni istayman.
- Given mijozda asl chek (raqami/QR) bor, When kassir qaytarishni boshlaydi va chekni topadi, Then qaytarilgan tovar miqdori ombor balansiga qaytadi (M04) va pul naqd/kartaga qaytariladi yoki nasiya balansi tuzatiladi (M08).
- (qaror #71) Given asl karta to'lovi `card_entry_mode='integrated'`, When pul kartaga qaytariladi, Then shu terminalda kun settlementidan oldin `void`, keyin — `refund` (asl `rrn` va summa bilan) bajariladi (audit `card.refund`), natija `return.created.refund_card` orqali qaytarish to'lovi qatoriga xuddi shu karta maydonlari bilan yoziladi; terminal boshqa yoki ishlamasa — terminalsiz karta qaytarish (`refund_method='card'`, `card_entry_mode='manual'`, rekvizitsiz) `card_manual_fallback` siyosati bo'yicha (standart — Menejer/Egasi PIN; terminal bog'lanmagan kassada — tasdiqsiz).
- Given asl chek topilmaydi, When kassir shunga qaramay qaytarishga harakat qiladi, Then operatsiya Menejer tasdig'isiz yakunlanmaydi.

**US-M02-02**: Menejer sifatida belgilangan limitdan yuqori qaytarishni tasdiqlashni istayman.
- Given qaytarish summasi limitdan yuqori, When kassir qaytarishni yuboradi, Then operatsiya "kutilmoqda" holatiga o'tadi va Menejerga bildirishnoma boradi.
- Given Menejer tasdiqlaydi, When u "tasdiqlash" tugmasini bosadi, Then qaytarish yakunlanadi; rad etilsa, operatsiya bekor qilinadi va sabab yoziladi.
- (qaror #23, tavsiya #1) **Standart limit**: asl chek bilan qaytarish — Kassir PIN'siz **100 000 so'mgacha** mustaqil amalga oshiradi; chek topilmasa (asl chek yo'q) — summadan qat'i nazar **har doim Menejer PIN** talab qilinadi (US-M02-01'dagi "topilmagan chek" holati bilan birga). Egasi istalgan paytda bu limitni (M13 orqali) o'zgartirishi mumkin (`02-rollar-va-ssenariylar.md`, 6-bo'lim izohi).

**US-M02-03**: Buxgalter sifatida qaytarilgan tovar bo'yicha QQS tuzatishini avtomatik ko'rishni istayman.
- Given qaytarish yakunlangan, When tizim buxgalteriya yozuvini yaratadi, Then sotuv summasi va unga mos QQS summasi manfiy yozuv bilan tuzatiladi (M10, M11).

### Davlat tizimlari bog'liqligi
Markirovkalangan tovar xaridordan qaytarilganda kod yozilgan **qaytarish cheki** OFD orqali Asl belgisiga uzatiladi (VMQ 833 90-band, qaror #62) — CRPT API'ga alohida chaqiruv yo'q.

### Offline xatti-harakati
Oddiy (markirovkalanmagan) tovar uchun qaytarish offline rejimda mahalliy jurnalga yoziladi (M01 bilan bir xil append-only naqsh), internet qaytganda sinxronlanadi. (qaror #23, tavsiya #5) **Markirovkalangan (Asl belgisi) tovarni qaytarish faqat internet bor paytda mumkin** — offline rejimda bunday tovar uchun "Qaytarish" tugmasi bloklanadi (POS-05'da aniq xabar bilan). Qonun offline qaytarish chekini taqiqlamaydi (VMQ 833 84/90-band) — bu ichki ehtiyot tanlovi: kod holatini tekshirish va firibgarlikning oldini olish.

### Chekka holatlar
- Qisman qaytarish (chekdagi bir nechta tovardan faqat bittasi).
- Markirovkalangan tovarni qaytarish siyosati: **faqat online** (yuqoridagi Offline xatti-harakati). (qaror #48) Muddati o'tgan tovarni qaytarish — faqat `returns.approve` (Menejer/Egasi) bilan; qaytgan qator `restock=false` (`return_lines.restock`), avtomatik `write_offs` qoralamasi (`write_off_lines.reason='expired_return'`) yaratiladi, tovar sotuvga qaytmaydi.
- Nasiya bilan sotilgan tovarni qaytarish — balans tuzatish ikki tomonlama (ombor + qarz) bo'ladi.

---

## M03 — Chegirma

**Maqsad**: chegirma va promo aksiyalarini nazoratli tarzda qo'llash. (Loyallik/bonus kartasi dasturi — **keyingi bosqich**, CRM/sodiqlik moduli bilan birga; MVP'da emas — `research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #2; `05-mvp-chegarasi.md` §1.3.)

### Foydalanuvchi hikoyalari

**US-M03-01**: Kassir sifatida ruxsat etilgan limit ichida chekka chegirma berishni istayman.
- Given chegirma foizi limitdan past, When kassir chegirmani kiritadi, Then chek summasi avtomatik qayta hisoblanadi.
- Given chegirma limitdan yuqori, When kassir kiritishga harakat qiladi, Then tizim Menejer PIN-kodini so'raydi.
- (qaror #23, tavsiya #1) **Standart limit**: Kassir PIN'siz chekka **5% gacha** chegirma beradi; chekni bekor qilish (`sales.void`) Kassirga limitsiz ruxsat etiladi, lekin har doim audit yoziladi. Egasi istalgan raqamni (M13 orqali) o'zgartirishi mumkin — sabab: raqobatchilarning (Loyverse, Square, BILLZ, REGOS) birortasida ham tayyor standart raqam yo'q, kichik standart qiymat kundalik mayda amallarni to'xtatmaydi.

**US-M03-02** (MVP'dan keyin — qaror #33): Menejer sifatida avtomatik chegirma qoidalarini (kategoriya, muddat, mijoz toifasi bo'yicha) sozlashni istayman.
- Given yangi aksiya boshlanishi kerak, When Menejer qoida yaratadi (tovar/kategoriya, foiz, boshlanish-tugash sanasi), Then qoida saqlanadi va kassada avtomatik qo'llaniladi, muddat tugagach avtomatik to'xtaydi.

**US-M03-03**: Egasi sifatida chegirmalarning margin'ga ta'sirini hisobotda ko'rishni istayman.
- Given tanlangan davr, When Egasi hisobotni ochadi, Then berilgan chegirmalar summasi va ular tufayli kamaygan margin ko'rsatiladi (M12 bilan bog'liq).

### Davlat tizimlari bog'liqligi
Chegirmali (yakuniy) narx QQS bazasiga asos bo'ladi — QQS chegirmadan keyingi summadan hisoblanishi kerak (M10).

### Offline xatti-harakati
Chegirma qoidalari oldindan POS'ga sinxronlanadi; offline rejimda oxirgi yuklangan qoidalar bo'yicha ishlaydi, markaz bilan real-time aloqa shart emas.

### Chekka holatlar
- Bir nechta chegirma manbai (masalan mijozning doimiy chegirma %'i — M09/US-M09-07, M08 — va kassir/aksiya chegirmasi) bir chekda to'qnashsa, chegirmalar **yig'ilmaydi**: faqat bittasi — mijozga eng katta foyda beradigani — qo'llaniladi (Odoo'ning "bitta eng mos qoida" modeliga mos, qaror #23 tavsiya #8).
- Chegirma tovar narxini manfiy qilib yubormasligi tekshirilishi kerak.
- Aksiya muddati offline paytda tugashi — POS eski qoidani ishlatib qolishi mumkin.
- "2+1" turidagi aksiya — US-M03-02 qoidasi sifatida (uchinchi donaga 100% chegirma), alohida "bepul tovar" hujjati emas; QQS chegirmadan keyingi summadan (chek chegirmasi — SK 248-modda 2-qism; "2+1" ning QQS talqini — 26 #145 (OQ-074)).
- (qaror #23, tavsiya #8) **Optom narx jadvali yo'q**: MVP'da alohida "optom narx" turi yo'q (M09'ga qarang) — mijozning doimiy chegirmasi shu yerdagi "faqat bitta eng foydali chegirma" qoidasi bilan bir xil mantiqda ishlaydi.

---

## M04 — Ombor qoldig'i

**Maqsad**: har bir ombordagi tovar miqdorini real vaqtda to'g'ri ko'rsatish.

### Foydalanuvchi hikoyalari

**US-M04-01**: Omborchi sifatida tovar kelganda balansni avtomatik yangilashni istayman.
- Given xaridnoma bo'yicha tovar qabul qilindi (M07), When qabul hujjati tasdiqlanadi, Then ombor balansi (miqdor) avtomatik oshadi.

**US-M04-02**: Menejer sifatida minimal zaxira chegarasiga yetilganda ogohlantirish olishni istayman.
- Given tovar uchun minimal chegara belgilangan, When qoldiq shu chegaraga yetadi yoki pastga tushadi, Then Menejerga bildirishnoma yuboriladi.

**US-M04-03**: Egasi/Menejer sifatida barcha filiallar bo'yicha umumlashtirilgan qoldiqni ko'rishni istayman.
- Given bir nechta filial (M14) mavjud, When konsolidatsiyalangan hisobot ochiladi, Then har bir filial va umumiy jami qoldiq ko'rsatiladi.

**US-M04-04**: Egasi/Menejer sifatida tizimga birinchi marta kirganda boshlang'ich tovar/qoldiq ro'yxatini tizimga kiritishni istayman.
- Given yangi tenant ro'yxatdan o'tgan, When Egasi/Menejer boshlang'ich katalog/qoldiqni kiritadi, Then uchta yo'l qo'llab-quvvatlanadi: (1) **qo'lda kiritish** (tovar-tovar), (2) **Excel/CSV shablon** orqali ommaviy import, (3) **AI-03** yordamida qog'oz katalog/qoldiq varag'i fotosidan kiritish (AI faqat o'qiydi, foydalanuvchi tasdiqlaydi).
- **Boshqa tashqi buxgalteriya/ERP tizimlari bu ro'yxatda yo'q** — tizim yadrosi ulardan ma'lumot o'qimaydi va ular bilan sinxronlanmaydi. Yagona istisno — alohida **1C integratsiya moduli** (M19, qaror #36–#41, Bosqich 7). Mavjud tizimlar ma'lumotlar modelini loyihalashda struktura namunasi sifatida ham ishlatilgan.
- (qaror #16) (3)-yo'l (AI-03) — MVP ichida; MVP'da uchta yo'l (1), (2), (3) barchasi mavjud. Kiritilgan qoldiq "boshlang'ich qoldiq" hujjati sifatida o'tkaziladi (chek/faktura yo'q, `13-provodka-qoidalari.md` 2.21).
- **Excel/CSV shablon formati** (2-yo'l, `import_jobs`): `products.csv` — ustunlar `name, name_ru, barcode, unit_code, mxik_code, vat_rate, price, category, is_marked` (`name_ru` — ixtiyoriy, bilingual chek uchun, `03-modullar-talablari.md` M09, qaror #29); `opening_stock.csv` — `barcode, qty, unit_cost, expiry_date`; `opening_debts.csv` — `name, phone, amount, direction` (`receivable`/`payable`), `date`. Kodlash UTF-8, ustun ajratgichi `;`, kasr son nuqta (`.`) bilan; validatsiya xatolari qator/maydon darajasida `import_jobs.errors`ga yoziladi (validate→commit ikki bosqich).

**US-M04-05**: Egasi/Buxgalter sifatida tovar tannarxini hisoblash usulini korxonamga mos tanlashni istayman.
- Given korxona sozlamalarida "Hisob siyosati → zaxira baholash usuli" bor, When Egasi/Buxgalter usulni tanlaydi, Then ikki variant mavjud: **O'rtacha narx (AVECO)** — standart (default), kichik do'konlar uchun soddaroq; **FIFO** — kattaroq do'konlar/ulgurji uchun, partiya bo'yicha aniqroq tannarx. Ikkalasi BHMS №4 ga mos (LIFO yo'q) (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`).
- Ikkala usul **barcha tariflarda** mavjud — buxgalteriya to'g'riligi tarifga bog'lanmaydi.
- Usul hisob davri ichida o'zgartirilmaydi; o'zgartirish faqat **keyingi hisobot yili boshidan** kuchga kiradi va tizim buni ogohlantirish bilan tasdiqlatadi (hisob siyosati izchilligi — buxgalter bilan tasdiqlanadi).
- Given usul tanlangan, When sotuv/qaytarish/ko'chirish/hisobdan chiqarish o'tkaziladi, Then sotilgan tovar tannarxi (COGS) tanlangan usul bo'yicha avtomatik hisoblanadi va M11 provodkasiga tushadi.

**US-M04-06**: Omborchi/Egasi sifatida yaroqlilik muddati yaqinlashgan tovarni oldindan bilishni va muddati o'tganini hisobdan chiqarishni istayman.
- Given kirimda partiya uchun yaroqlilik muddati kiritilgan (ixtiyoriy maydon), When muddatga 7 kun qolganda (standart, sozlanadi), Then Egasi/Menejerga ro'yxat (tovar, partiya, qoldiq, muddat) M18 orqali boradi va BO-03'da belgi ko'rinadi.
- Given tovar muddati o'tgan/buzilgan yoki bepul berilgan (namuna, sovg'a), When Omborchi "Hisobdan chiqarish" hujjatini sabab bilan yaratadi, Then qoldiq kamayadi va tannarx xarajatga yoziladi (`13-provodka-qoidalari.md` 2.12); bepul berish — `reason='gift'` va `gift_kind` bilan (`13-provodka-qoidalari.md` 2.12; QQS talqini — 26 #145 (OQ-074)). Hisobdan chiqarish faqat online back-office'da (qaror #54). Yetkazib beruvchi qaytarib olsa — US-M07-05.

### Davlat tizimlari bog'liqligi
Markirovkalangan tovarlar uchun balans kod (serial) darajasida, oddiy tovarlar uchun miqdor darajasida kuzatiladi — Asl belgisi tizimi bilan moslik talab qilinadi.

### Offline xatti-harakati
POS'dagi sotuv (kamayish) offline event-log orqali yoziladi va sinxronlanganda balansga qo'llaniladi; bu operatsiya faqat kamaytiruvchi bo'lgani uchun konflikt xavfi past (CRDT shart emas, `research_notes/texnik/04-arxitektura-va-stack.md`, 4-band).

### Chekka holatlar
- Manfiy balansga (overselling) yo'l qo'ymaslik siyosati — offline paytda ikki kassa bir xil oxirgi tovarni sota olishi mumkin, sinxronlashda konflikt yuzaga keladi.
- Bir mahsulotning bir nechta o'lchov birligi (dona/quti/kg) balansi.
- **Tannarx (US-M04-05) uchun texnik talablar**:
  - Har bir kirim **partiya (lot)** sifatida saqlanadi (sana, miqdor, kirim narxi, manba hujjat) — usul AVECO bo'lsa ham. Shunda keyingi yil FIFO'ga o'tish yoki tekshiruv uchun qayta hisoblash mumkin bo'ladi; partiya markirovka va yaroqlilik muddati kuzatuvi bilan ham bir xil tuzilma.
  - AVECO: har kirimda o'rtacha narx qayta hisoblanadi (ombor bo'yicha alohida).
  - FIFO: chiqimda eng eski partiyadan boshlab yechiladi; bitta chek bir nechta partiyaga bo'linishi mumkin.
  - **O'tgan sanali hujjat** (kechikkan kirim, offline sotuv kech sinxronlangani, qaytarish) kiritilsa — shu sanadan keyingi tannarx avtomatik **qayta hisoblanadi** (qayta o'tkazish) va yopilgan davrga tegsa bloklanadi.
  - Offline POS sotuv paytida tannarxni hisoblamaydi — faqat miqdorni yozadi; tannarx serverda sinxronlashdan keyin hisoblanadi.
  - Manfiy qoldiqda sotuv bo'lsa (offline konflikt) — tannarx vaqtincha oxirgi ma'lum narx bilan olinadi va keyingi kirimda tuzatiladi.
- **Asosiy vosita vs tovar**: Asosiy vositalar (uskuna, jihoz va h.k.) M04 katalogiga tovar sifatida kiritilmaydi; ularning xaridi M15 (Xarajatlar) xarajati sifatida yoziladi, ombor/tannarx hisobiga kirmaydi. Tovar yaratish ekranida ogohlantirish matni ko'rsatiladi: "Agar bu uskuna/jihoz bo'lsa, uni Xarajatlar bo'limiga kiriting, tovar katalogiga emas."

---

## M05 — Inventarizatsiya

**Maqsad**: jismoniy sanash orqali haqiqiy qoldiqni tasdiqlash va farqni aniqlash.

### Foydalanuvchi hikoyalari

**US-M05-01**: Omborchi sifatida sanash varag'ini olib, haqiqiy sonlarni kiritishni istayman.
- Given inventarizatsiya boshlangan, When Omborchi har bir tovar bo'yicha haqiqiy sonni kiritadi, Then tizim haqiqiy son bilan tizimdagi qoldiqni solishtirib farqni ko'rsatadi.

**US-M05-02**: Menejer/Egasi sifatida aniqlangan farqni (ortiqcha/kamomad) ko'rib tasdiqlashni istayman.
- Given farq ro'yxati tayyor, When Menejer/Egasi ko'rib tasdiqlaydi, Then ombor balansi (M04) haqiqiy songa moslashtiriladi.

**US-M05-03**: Buxgalter sifatida kamomad/ortiqchani buxgalteriya yozuviga aks ettirishni istayman.
- Given inventarizatsiya tasdiqlangan, When tizim buxgalteriya yozuvini yaratadi, Then kamomad xarajat sifatida, ortiqcha daromad sifatida qayd etiladi (M11).

### Davlat tizimlari bog'liqligi
Inventarizatsiya CRPT'ga xabar qilinmaydi; markirovkalangan tovar kamomadi hisobdan chiqarish hujjati bilan rasmiylashtiriladi va kodlar `MarkingPort.writeoff` (CRPT API) orqali chiqariladi (qaror #62; real adapter — Ochiq savollar 11).

### Offline xatti-harakati
Mobil skanerlash (Android POS) offline ishlashi kerak (ombor sharoitida internet barqaror bo'lmasligi mumkin), natija keyin sinxronlanadi; lekin yakuniy tasdiqlash online rejimda amalga oshiriladi.

### Chekka holatlar
- (qaror #53) Inventarizatsiya paytida savdo davom etadi, tovar bloklanmaydi: `post` paytida har qator uchun `expected = snapshot_qty(started_at) + Σ stock_moves(started_at < moved_at ≤ counted_at)`, farq `counted − expected` (`count_lines.counted_at` — qator kiritilgan server vaqti).
- Partiyali/seriyali tovarlarni sanash murakkabroq.

---

## M06 — Ko'chirish

**Maqsad**: omborlar/filiallar orasida tovarni nazorat ostida ko'chirish.

### Foydalanuvchi hikoyalari

**US-M06-01**: Omborchi sifatida boshqa do'kon/omborga tovar yuborish hujjatini yaratishni istayman.
- Given tovar boshqa filialga kerak, When Omborchi ko'chirish hujjatini yaratadi (tovar, miqdor, manzil), Then yuboruvchi ombor balansi "yo'lda" holatiga o'tadi.
- (qaror #63) Given ko'chirish avtotransportda (`transfers.transport_mode='vehicle'`, standart), When hujjat jo'natiladi (`post`), Then "Ombordan omborga" turidagi e-TTN (`ettn_documents`, `transport_type=warehouse_to_warehouse`) yaratiladi va EDO operatori orqali E-IMZO bilan yuboriladi, `transfers.ettn_ref` saqlanadi; e-TTN `registered` bo'lmaguncha `send` rad etiladi (`409 ETTN_REQUIRED`) (VM 249 31-ilova 13, 16-band). `transport_mode='on_foot_or_public'` (qo'lda/jamoat transportida) — e-TTN talab qilinmaydi (24-band).

**US-M06-02**: Qabul qiluvchi Omborchi sifatida kelgan tovarni tasdiqlab qabul qilishni istayman.
- Given tovar manzilga yetib keldi, When qabul qiluvchi tomon miqdorni tasdiqlaydi, Then qabul qiluvchi ombor balansi oshadi, yuboruvchi ombordan "yo'lda" holati yopiladi va qabul qiluvchi filial e-TTN'ni tasdiqlaydi.

**US-M06-03**: Menejer sifatida ko'chirishlar tarixini va bajarilish vaqtini ko'rishni istayman.
- Given tanlangan davr, When Menejer ro'yxatni ochadi, Then barcha ko'chirishlar holati (yo'lda/yetib kelgan/kechikkan) ko'rsatiladi.

### Davlat tizimlari bog'liqligi
E-TTN — ichki ko'chirishda ham **majburiy** ("Ombordan omborga" rejimi, VM 249 31-ilova 13-band; qaror #63): jo'natuvchi bir vaqtda yuk oluvchi, e-faktura chiqarilmaydi; kanal — EDO operatori. Asl belgisi: bir yuridik shaxsning o'z filiallari orasidagi ko'chirish CRPT'ga xabar qilinmaydi (VM 833 Qoidalarida xabarnoma faqat egalik o'tishiga bog'liq, 66–67-band) — markirovka kodlari filial balansida ichki ko'chadi. Markirovkali tovar egalik o'tishidagi 72 soat qoidasi ichki ko'chirishga tegishli emas — u faqat ayrim tovar guruhlari (o'simlik yog'i, suv/ichimlik, dori) kirimida, tovar guruhi bo'yicha sozlanadigan muddat sifatida qo'llanadi, umumiy muddat — 3 ish kuni (M07 qabul, qaror #63). E-TTN yozuvchisi — ko'chirish (`transfers`) `post`.

### Offline xatti-harakati
Qabul qiluvchi tomonda internet yo'q bo'lsa, qabul mahalliy qayd etilib keyin sinxronlanadi. (qaror #23, tavsiya #5) **Markirovkalangan tovarni o'z filiallar/omborlar orasida ko'chirish offline rejimda ruxsat etiladi** (jo'natish ham, qabul ham) — hujjat mahalliy append-only jurnalga yoziladi, internet qaytganda serverga sinxronlanadi, barcha amal audit bilan qayd etiladi; sabab — ichki ko'chirishda tovar egasi (yuridik shaxs) o'zgarmaydi. Offline yaratilgan avtotransport ko'chirishi uchun e-TTN internet qaytgach, **tashish boshlanishidan oldin** rasmiylashtiriladi.

### Chekka holatlar
- Yo'lda tovar yo'qolishi/buzilishi — qisman qabul qilish imkoniyati kerak.
- Offline `transfer.sent` (avtotransport, e-TTN yo'q) — hujjat `posted` da qoladi, `warnings: ["ETTN_REQUIRED"]`; jo'natish e-TTN ro'yxatdan o'tgach online (BO-03 "Ko'chirishlar" tabi va M12 xavf ro'yxati).

---

## M07 — Xarid

**Maqsad**: yetkazib beruvchidan tovar qabul qilish va hisob-kitobni yuritish.

### Foydalanuvchi hikoyalari

**US-M07-01**: Menejer/Omborchi sifatida yetkazib beruvchiga xaridnoma yaratishni istayman.
- Given kam qolgan tovarlar aniqlangan (M04), When Menejer xaridnoma yaratadi (yetkazib beruvchi, tovar, miqdor, narx), Then hujjat "yuborilgan" holatga o'tadi.

**US-M07-02**: Omborchi sifatida kelgan tovarni xaridnoma bilan solishtirib qabul qilishni istayman.
- Given tovar yetib keldi, When Omborchi haqiqiy miqdorni kiritib tasdiqlaydi, Then farq (kam/ko'p) belgilanadi, kirim `draft` holatda saqlanadi; ombor balansi (M04) Buxgalter/Egasi `post` qilganda oshadi (qaror #49).

**US-M07-03**: Buxgalter sifatida yetkazib beruvchining e-fakturasini tizimga kiritib, QQS kreditini hisoblashni istayman.
- (qaror #23, tavsiya #4) **E-faktura operatori — MVP'da faqat Faktura.uz**; Didox — MVP'dan keyingi birinchi integratsiya (`EInvoicePort` ikki adapterga tayyor; Didox — ochiq API, platforma partner tokeni bilan; asoschi qayta ko'rishi tavsiya etiladi — 26 #167). Faktura.uz token `grant_type=password` bilan olinadi — tenantning Faktura.uz login/paroli va `client_id/client_secret` `tenant_secrets` da shifrlangan saqlanadi; kiruvchi hujjatlar faqat poll orqali (webhook yo'q).
- Given e-faktura Faktura.uz orqali keldi yoki qo'lda kiritildi, When Buxgalter uni E-IMZO bilan tasdiqlaydi, Then faktura summasi va QQS buxgalteriya yozuviga (M11) va QQS hisobiga (M10) qo'shiladi.
- Given faktura AI xavf-baholash tizimida "yuqori xavfli" (qizil) deb belgilangan, When Buxgalter buni ko'radi, Then tizim QQS krediti to'lovdan keyin kreditlanishi haqida ogohlantiradi (VM 830). `einvoices.risk_flag` — `green|red|unknown` (standart `unknown`); operator xavf darajasini qaytarmasa (`unknown`) QQS krediti qizil kabi to'lovgacha kechiktiriladi, Buxgalter my.soliq kabinetidan ko'rib BO-15'da qo'lda belgilaydi (audit bilan).

**US-M07-04**: Buxgalter sifatida yetkazib beruvchiga bo'lgan kreditorlik qarzini to'lashni va buni tizimda qayd etishni istayman.
- Given yetkazib beruvchi fakturasi tasdiqlangan (M07, M11), When Buxgalter to'lovni (bank/naqd) amalga oshiradi, Then kreditorlik balansi shu summaga kamayadi.
- (qaror #47) Given to'lov summasi joriy qarzdan katta, When `settings.supplier_overpay_policy='warn'` (standart), Then ogohlantirish bilan ruxsat etiladi va ortig'i avans (4310) sifatida yoziladi; `block` bo'lsa `422 SUPPLIER_OVERPAY_BLOCKED`.
- Given faktura "qizil" (yuqori xavfli) deb belgilangan, When to'lov amalga oshadi, Then shundan keyingina QQS krediti kreditlanishi tizimda aks etadi (US-M10-03 bilan bog'liq, `research_notes/texnik/03-efaktura-va-tolov.md`, 1.2-bo'lim).

**US-M07-05**: Omborchi/Menejer sifatida muddati o'tgan, buzilgan yoki ortiqcha tovarni yetkazib beruvchiga qaytarishni istayman.
- Given tovar shu yetkazib beruvchidan kirim qilingan (US-M07-02), When Omborchi "Yetkazib beruvchiga qaytarish" hujjatini yaratadi (yetkazib beruvchi, asl kirim hujjati, tovar, miqdor, sabab), Then ombor qoldig'i (M04) kamayadi va yetkazib beruvchiga qarzimiz (US-M08-11) shu summaga kamayadi; qarz bo'lmasa — yetkazib beruvchi bizga qarzdor bo'ladi yoki pulni naqd/bank orqali qaytaradi.
- Given asl kirim QQS bilan bo'lgan va qaytarish asl kirimdan **12 oy ichida** (kafolatli tovarda — kafolat muddati ichida), When qaytarish o'tkaziladi, Then hujjat holati "yetkazib beruvchidan qo'shimcha (salbiy) e-faktura kutilmoqda" bo'ladi; kiruvchi QQS (`vat_moves(kind=input)`, manfiy) **qo'shimcha e-faktura qabul qilingan (Buxgalter imzolagan) soliq davrida** yoziladi (SK 257, 269-m.; VM 489 40-band). Muddat o'tgan yoki shartnomada qaytarish asosi yo'q bo'lsa — tizim "teskari realizatsiya" ogohlantirishini ko'rsatadi: qaytarish do'konning yetkazib beruvchiga sotuvi sifatida chiquvchi e-faktura va chiquvchi QQS bilan rasmiylashtiriladi (Buxgalter tasdig'i bilan).
- Given tovar markirovkalangan, When yetkazib beruvchiga qaytariladi, Then egalik o'tishi xabarnomasi CRPT API (`MarkingPort`) orqali yuboriladi (VM 833 85-band, 3 ish kuni; qaror #62).

### Davlat tizimlari bog'liqligi
E-faktura (Faktura.uz — MVP'da yagona operator, qaror #23 tavsiya #4; Didox — MVP'dan keyin, ochiq API, partner token bilan), e-TTN (sotuv bilan birga jo'natishda e-faktura bilan birlashtirilgan holda keladi — alohida ish yo'q), MXIK kod tekshiruvi, E-IMZO (imzolash), AI xavf-baholash (VM Qarori №830).

**E-ishonchnoma** (qaror #63): do'kon o'z xodimiga (Omborchi) e-faktura operatori orqali (Faktura.uz PowerOfAttorney / Didox Empowerment, VM 249 3-ilova) e-ishonchnoma beradi — **e-fakturadan oldin**; yetkazib beruvchi uni tekshirib e-fakturani ishonchnoma asosida shakllantiradi, Omborchi e-fakturani E-IMZO bilan imzolaydi. Vakolat.uz (VM 825) — davlat xizmatlari uchun, tovar qabulida ishlatilmaydi. Ishonchnoma bo'lmasa — e-fakturani Buxgalter (direktor ERI) imzolaydi, tizim bloklamaydi; ishonchnoma raqami — `goods_receipts.poa_number`.

**Markirovka qabul muddati**: markirovkalangan tovar kirimida Asl belgisi qabul xabarnomasi (e-faktura shaklida) tovar guruhi muddatida imzolanishi kerak — umumiy **3 ish kuni**, lekin tovar uchinchi shaxsga berilgunga qadar (VM 833 66–67-band); suv va salqin ichimliklar (VM 631), dori vositalari (VM 149) va o'simlik yog'i tajriba loyihasi (VM 23) guruhlarida — **72 soat**. Muddat tovar guruhi bo'yicha sozlanadi (standart 3 ish kuni; 72 soatli guruhlar ro'yxati — konfiguratsiya, qaror #63); tizim muddatni kuzatadi va ogohlantiradi, bloklamaydi.

### Offline xatti-harakati
**Qabul (tovar kirimi) faqat online** — offline kirim voqeasi yo'q. Xaridnoma bo'yicha jismoniy sanash/skanerlash (miqdorni solishtirish) Omborchi tomonidan internetsiz ham lokal davom ettirilishi mumkin, lekin qabulni **yakunlash/o'tkazish** har doim internetga ulangan holda amalga oshadi — markirovkalangan tovar qabulida tovar egaligi o'zgaradi va CRPT qabul xabarnomasi talab qilinadi. Omborchi qabulni `draft` qiladi, `post` — Buxgalter/Egasi (`purchases.post`; Egasi uni BO-11'da Omborchiga berishi mumkin — qaror #49).

### Chekka holatlar
- Qisman yetkazib berish (buyurtma qilingan miqdordan kam/ko'p kelishi).
- Narx farqi (xaridnomadagi narx bilan fakturadagi narx mos kelmasligi).
- Markirovkalangan tovar xaridida kodlar CRPT xTrace API orqali tekshiriladi va qabul xabarnomasi imzolanadi (`MarkingPort`; real adapter — Ochiq savollar 11); qabul muddati yaqinlashsa ogohlantirish (yuqorida).
- Yetkazib beruvchi bonus tovari (masalan "10 + 1 tekin") — bonus miqdori kirim qatoriga qo'shiladi, partiya `unit_cost` = faktura summasi / (to'langan + bonus miqdor) (13 §2.6, BHMS №4); 0 narxli alohida partiya yo'q.

---

## M08 — Nasiya (mijoz qarzi)

**Maqsad**: mijozga nazoratli tarzda qarzga sotish, limit va eslatmalarni boshqarish.

### Foydalanuvchi hikoyalari

**US-M08-01**: Kassir sifatida mijozga belgilangan limit ichida nasiyaga sotishni istayman.
- Given mijoz tanlangan, When kassir "nasiya" to'lov turini tanlaydi, Then tizim mijozning joriy qarzi + yangi summa kredit limitidan oshmasligini tekshiradi.
- Given limit yetarli, When kassir yakunlaydi, Then mijoz qarz balansi (M08) oshadi; (qaror #30) **fiskal chek bu paytda chiqarilmaydi** — sotuv hujjati (tovar qatorlari, qoldiq −, mijoz qarzi +) yoziladi, sotuv `posted`, fiskal holat `deferred` (javobdagi `fiscal.status`), `fiscal_receipts` yozuvi yo'q; kassirga ekranda "Qarzga yozildi — chek qarz to'langanda chiqadi" ko'rsatiladi.
- Given limit yetarli emas, When kassir yakunlashga harakat qiladi, Then operatsiya rad etiladi yoki Menejer tasdig'i so'raladi (online rejim). (qaror #23, tavsiya #7) Given offline rejim va oxirgi ma'lum qoldiq bo'yicha limitdan oshib ketish aniqlansa, When kassir shunga qaramay sotishni tanlaydi, Then sotuv **bloklanmaydi** — qarz yoziladi, bayroq qo'yiladi, internet qaytganda Egasiga xabar boradi (M08 Offline xatti-harakati bo'limiga qarang).

**US-M08-02**: Menejer sifatida mijoz kredit limitini belgilash/o'zgartirishni istayman.
- Given mijoz tanlangan, When Menejer limitni kiritadi/o'zgartiradi, Then yangi limit darhol kuchga kiradi va barcha kassalarga sinxronlanadi.

**US-M08-03**: Egasi/Menejer sifatida muddati o'tgan qarzlar bo'yicha avtomatik eslatma matnini olishni istayman.
- Given mijoz qarzi to'lov muddatidan o'tgan, When tizim kunlik tekshiradi, Then AI yordamida tayyorlangan eslatma matni (o'zbek tilida) taklif qilinadi (AI funksiyalar bilan bog'liq, `09-ai-funksiyalar.md`).

**US-M08-04**: Kassir/Buxgalter sifatida mijozning nasiya qarzini keyinroq (qisman yoki to'liq) to'lashini qabul qilishni istayman.
- Given mijoz oldingi nasiya qarziga ega, When mijoz naqd/karta/QR orqali to'lov qiladi, Then qarz balansi (M08) shu summaga kamaytiriladi; qisman to'lovda qoldiq qarz saqlanadi.
- (qaror #30) **Har bir qarz to'lovida (`debt_payments`) to'langan summaga fiskal chek chiqariladi** (`fiscal_receipts.kind = debt_settlement`). Tovar qatorlari — to'lov qaysi sotuv(lar)ni yopsa (eng eski qarzdan, US-M08-09), shu sotuv(lar)ning qatorlaridan **proporsional** hisoblanadi (bir nechta sotuv yopilsa ham **bitta** chek chiqadi, qatorlar shu sotuvlardan proporsional — qaror #45; `FiscalPolicy.debt_receipt_split='single'`). Qarz to'lovidagi chek majburiy (VMQ-943 1-ilova 30-band). Daromad va QQS **sotuv kuni** tan olinadi (BHMS 2; SK 242, 78-modda; qaror #30, #42) — qarz to'lovi kunida faqat pul harakati va fiskal chek, provodka sanasi ≠ fiskal chek sanasi.
- (qaror #45) Given to'lov summasi mijozning joriy qarzidan katta, When kassir to'lovni yakunlaydi, Then `422 VALIDATION_ERROR` (`message_key=debt_payment_exceeds_balance`) — faqat qarz summasigacha qabul qilinadi, qaytim naqd beriladi; mijoz avansi MVP'da yo'q.
- Given qarz karta bilan to'lanmoqda, Then `debt_payments` da karta rekvizitlari sotuvdagi qoida bilan to'ldiriladi: integratsiyalangan terminalda — terminal natijasidan avtomatik (US-M01-08, qaror #71), aks holda terminalsiz karta — faqat summa, karta rekvizitlari `NULL` (US-M01-01, qaror #64).

**Qarz daftari.** Quyidagilar US-M08-01…04 ni to'ldiradi; kichik do'konda Menejer yo'q bo'lishi mumkin, shuning uchun limit **ixtiyoriy**.

**US-M08-05**: Kassir/Egasi sifatida qarzga berishni 2–3 soniyada, xuddi daftarga yozgandek qilishni istayman.
- Given POS ekranida "Qarzga" tugmasi, When kassir mijozni ism yoki telefon bo'yicha qidiradi (yoki faqat **ism + telefon** bilan yangisini yaratadi), Then sotuv mijoz qarziga yoziladi; limit belgilanmagan bo'lsa tekshiruv o'tkazilmaydi.
- Ixtiyoriy izoh ("o'g'li olib ketdi", "oylikdan keyin beradi") va va'da qilingan to'lov sanasi kiritiladi.
- Internet yo'q bo'lsa ham to'liq ishlaydi (POS lokal bazasida), sinxronlanganda serverga tushadi.

**US-M08-06**: Egasi/Kassir sifatida har bir mijozning qarz daftarini qog'oz daftardek ko'rishni istayman.
- Given mijoz tanlangan, When "Qarz daftari" ochiladi, Then sana bo'yicha ro'yxat: har bir qarz (summa, **qaysi tovarlar olingan**, kim berdi, izoh), har bir to'lov va joriy qoldiq ko'rinadi; POS'da ham (tezkor ko'rish), back-office'da ham (BO-06).
- Har bir qarz qatorida holat: ochiq / qisman yopilgan (qolgan summa) / to'liq yopilgan — qisman to'lov qaysi qarz(lar)ni yopgani `debt_payments.allocations` bo'yicha (eng eski qarzdan, US-M08-09) ko'rsatiladi.

**US-M08-07**: Egasi sifatida eski qog'oz daftardagi qarzlarni tizimga tez ko'chirishni istayman.
- Given yangi do'kon, When Egasi "Boshlang'ich qarzlar" ekranini ochadi, Then har bir mijoz uchun ism, telefon, qarz summasi va (ixtiyoriy) sana qatorma-qator yoki Excel shablon orqali kiritiladi; bu qarzlar "boshlang'ich qoldiq" deb belgilanadi (tovar tarkibisiz, chek chiqarilmaydi).
- Qo'lyozma daftar fotosidan o'qish (AI-04) — keyingi bosqich (`09-ai-funksiyalar.md`).

**US-M08-08** (MVP'dan keyin — qaror #33): Mijoz sifatida qancha qarzim borligini bilishni istayman (nizolarning oldini olish).
- Given mijozning telefoni bor va u rozilik bergan, When qarz yoki to'lov yoziladi, Then mijozga xabar ketadi: "Bugun 45 000 so'm qarz yozildi. Jami qarzingiz: 230 000 so'm. — [Do'kon nomi]" (sozlamada o'chirish mumkin) — (qaror #34) **birinchi navbatda Telegram** (mijoz do'konning Telegram botiga ulangan/yozgan bo'lsa), Telegram mavjud bo'lmasa **SMS zaxira** sifatida.
- Mijoz Telegram havola orqali o'z qarz tarixini (faqat o'zinikini) ko'ra oladi.

**US-M08-09**: Egasi sifatida qarzlarni o'z vaqtida qaytarib olishni istayman.
- Given va'da sanasi keldi yoki o'tdi, When kunlik tekshiruv ishlaydi, Then Egasiga ro'yxat ("bugun to'lashi kerak: 5 kishi, 640 000 so'm") va mijozga eslatma yuborish taklifi chiqadi (matnni AI-06 yozadi yoki standart shablon; yuborishni odam tasdiqlaydi).
- To'lov qabul qilinganda summa **eng eski qarzdan boshlab** yopiladi (qisman to'lov qoldig'i saqlanadi).

**US-M08-10**: Egasi sifatida qarzlar holatini bir qarashda ko'rishni istayman.
- Given qarzdorlar bor, When hisobot ochiladi, Then: jami qarz, qarzdorlar soni, muddat bo'yicha guruhlar (0–30 / 31–60 / 60+ kun), eng katta qarzdorlar, bu oy berilgan va qaytgan qarz.
- (qaror #23, tavsiya #9) **60 kunlik "eski qarzlar" eslatmasi**: qarz yaratilgan/oxirgi to'lovdan **60 kundan ortiq** o'tgan va hali yopilmagan qarzlar alohida ro'yxat sifatida Egasiga eslatma (M18) bilan ko'rsatiladi — bu faqat **eslatma**, tizim o'zi "shubhali qarz" deb avtomatik belgilamaydi.
- Qarzni kechib yuborish yoki "undirib bo'lmaydigan" (shubhali) deb yopish — **faqat Egasi, sabab bilan**, audit jurnaliga yoziladi; 60 kunlik ro'yxat (yuqorida) faqat shuni ko'rib chiqishni eslatadi, o'zi avtomatik harakat qilmaydi.

**US-M08-11**: Egasi sifatida **o'zim yetkazib beruvchilarga** qarzimni ham daftar kabi yuritishni istayman (mol qarzga olinadi).
- Given xarid nasiyaga qabul qilingan (M07), When yetkazib beruvchi tanlanadi, Then "Men qarzdorman" daftari: kimga, qancha, qachon to'lash kerak; to'lov BP-12 orqali yopiladi; to'lov sanasi yaqinlashganda eslatma.

**Qoidalar:**
- Qarzga **foiz qo'shilmaydi** (MVP'da bunday funksiya yo'q).
- (qaror #30) Qarzga sotuvda (to'lov turi: nasiya, BP-03) fiskal chek standart **berilmaydi** (`FiscalPolicy.credit_sale_receipt='none'`; `credit_type` — sotuv paytida "kredit" turidagi chek, OFD/hamkor tasdig'idan keyin yoqiladi, 26 #9 (OQ-002)), sotuv qarz daftariga hujjat sifatida yoziladi, daromad/QQS shu kuni tan olinadi; **fiskal chek har bir qarz to'lovida** chiqariladi (yuqorida, US-M08-04). "Boshlang'ich qarz" (US-M08-07) bundan ham mustasno — u yangi sotuv emas, tovar tarkibisiz boshlang'ich qoldiq hujjati.
- Mijoz telefon raqami shaxsiy ma'lumot: SMS/Telegram faqat mijoz roziligi bilan.

### Davlat tizimlari bog'liqligi
Daromad/QQS — **sotuv kuni** (BHMS 2; SK 242, 78, 297, 463-modda; qaror #30), fiskal chek — qarz to'langan kuni (`debt_settlement`, VMQ-943 1-ilova 30-band, qaror #30, #45). Jismoniy shaxsga sotuvda chek berilsa e-faktura talab qilinmaydi (SK 47-m. 3-q., VM 489 3-band); yuridik shaxs va bank o'tkazmasi bilan to'laydigan YTT uchun e-faktura majburiy. Sotuv paytidagi "kredit" turidagi chek va OFD chek turi kodi — 26 #9 (OQ-002).

### Offline xatti-harakati
Offline rejimda nasiya yaratish mumkin, lekin limit tekshiruvi faqat oxirgi sinxronlashgan ma'lumot asosida bo'ladi — bir mijozga bir nechta kassada parallel nasiya berilsa, limitdan oshib ketishi mumkin — quyidagi qoida bilan hal qilingan (qaror #23, tavsiya #7). (qaror #23 tavsiya #7; qaror #30) **Offline'da limitdan oshgan nasiya**: qurilma oxirgi ma'lum qoldiq bo'yicha ogohlantiradi, lekin kassir baribir sotishni tanlasa — sotuv **bekor qilinmaydi**, qarz limitdan oshgan holicha yoziladi, operatsiyaga **bayroq** qo'yiladi va internet qaytganda Egasiga xabar (M18) boradi; sabab — sotuv hujjati (tovar chiqimi, qarz ortishi) allaqachon amalga oshgan va uni orqaga qaytarish ombor/buxgalteriyani buzadi (fiskal chek bu bosqichda hali chiqarilmagan bo'lsa ham), nazorat xabar/audit orqali amalga oshadi.

### Chekka holatlar
- Bir nechta kassa bir vaqtda bitta mijozga nasiya berishi (offline sinxronlash konflikti).
- Qarzni qisman to'lash va qoldiq balansni qayta hisoblash.
- Mijoz butunlay to'lamay qolganda qarzni "shubhali qarz" sifatida belgilash (M11 bilan bog'liq).

---

## M09 — Narxlar

**Maqsad**: chakana narxlarni, kategoriyalarni va narx tarixini boshqarish. (qaror #23, tavsiya #8) **Alohida optom narx jadvali MVP'da yo'q** — ulgurji/doimiy mijozlar uchun o'rniga mijoz kartasida (M08/counterparty) "doimiy chegirma %" maydoni ishlatiladi (pastga qarang va M03 chekka holatlar).

(qaror #29) **Tovar nomi — ikki tilli**: `products.name` (o'zbek, lotin — majburiy, asosiy) + `products.name_ru` (rus, ixtiyoriy). `name_ru` tovar kartasida/import shablonida to'ldirilsa, fiskal chek qatorida "{name} / {name_ru}" formatida ko'rsatiladi (`06-ekranlar-umumiy.md` §1.4, `08-dizayn-tizimi.md` chek shabloni); to'ldirilmasa — chekda faqat `name`. Maydon — `07-ekran-tafsilotlari.md` BO-05 (`nameRu`).

### Foydalanuvchi hikoyalari

**US-M09-01**: Menejer sifatida tovar narxini yangilashni, eski narx tarixda saqlanishini istayman.
- Given tovar tanlangan, When Menejer yangi narxni kiritadi, Then eski narx "tarix" yozuviga ko'chadi, yangi narx amal qilish sanasi bilan saqlanadi.

**US-M09-02**: Egasi sifatida katta (masalan belgilangan foizdan yuqori) narx o'zgarishini tasdiqlashni istayman.
- Given narx o'zgarishi katalog narxidan ±10%dan katta (`prices.approve`, `role_permissions.limit_value='10.00'`, 26 #5), When Menejer narxni kiritadi, Then o'zgarish Egasi tasdiqlamaguncha kuchga kirmaydi; o'zgarish `pending_approval` holatida BO-16 navbatiga tushadi, rad etilsa sabab yoziladi.

**US-M09-03**: Kassir sifatida kassada joriy (amaldagi) narxni ko'rishni istayman, lekin o'zgartira olmasligim kerak.
- Given kassa ekrani ochiq, When tovar tanlanadi, Then joriy narx ko'rsatiladi, tahrirlash tugmasi yo'q/faol emas.

**US-M09-04**: Menejer sifatida narxi o'zgargan tovarlarning javon yorliqlarini qayta chop etishni istayman.
- Given bir yoki bir nechta tovar narxi o'zgardi, When Menejer "Yorliqlar" bo'limini ochadi, Then narxi o'zgargan, lekin yorlig'i hali chop etilmagan tovarlar ro'yxati chiqadi; tanlab chop etiladi, chop etilganlar belgilanadi.
- Yorliq shabloni: tovar nomi, narx, (ixtiyoriy) eski narx, o'lchov birligi, shtrix-kod. Standart o'lchamlar: 58×40 (asosiy narx yorlig'i), 58×30, 43×25, 40×30, 30×20 mm va A4 varaq (3×8 yoki 4×10 to'r, oddiy printer uchun). Chop etish — brauzerda (HTML/SVG + `bwip-js`, CSS `@page { size: Wmm Hmm; margin: 0 }`) tizim drayveri orqali (bozor standarti — Xprinter XP-365B, TSPL+ESC/POS); xom TSPL/ZPL MVP'da yo'q. Server PDF — faqat >200 yorliq yoki iOS uchun (qaror #54).

**US-M09-05**: Menejer sifatida shtrix-kodi yo'q tovarga ichki shtrix-kod berishni istayman.
- Given tovar shtrix-kodsiz, When "Ichki shtrix-kod yaratish" bosiladi, Then tenant ichida noyob kod yaratiladi va yorliqda chop etiladi; kod ishlab chiqaruvchi kodlari va tarozi prefikslari (20–29) bilan to'qnashmaydigan diapazonda bo'ladi — EAN-13 `04` + 10 raqam + nazorat raqami (GS1 RCN 040–049, `11-malumotlar-modeli.md` §11).

**US-M09-06**: Kassir sifatida tarozida tortilgan tovarni (go'sht, meva) bitta skanerlash bilan sotishni istayman.
- Given yorliq chiqaradigan tarozi og'irlik kiritilgan shtrix-kod chop etgan, When kassir uni skanerlaydi, Then POS koddan tovar va og'irlikni ajratib chekka qo'shadi. Kod formati — EAN-13 `PP CCCCC VVVVV K` (PP — 20–29 dan sozlanadigan prefiks, CCCCC — 5 xonali PLU, VVVVV — og'irlik grammda yoki summa so'mda, K — nazorat raqami); standart: 22 = og'irlik (g), 21 = summa (so'm, ≤ 99 999); boshqa prefikslar do'kon sozlamasida qo'shiladi (`tenants.settings.weight_barcode_templates`).
- Given bir tovarning ikki og'irlik yorlig'i skanerlanadi, Then og'irliklar bitta chek qatorida jamlanadi.
- Given nazorat raqami mos kelmaydi, Then kod rad etiladi.
- Given summa prefiksi (21), Then miqdor = summa ÷ joriy narx; yorliqdagi summa joriy narxdan farqli bo'lsa ogohlantirish.
- PLU ro'yxati tarozi vendor dasturi (CL-Works, Shtrih Loader, Rongta tool) uchun CSV eksport qilinadi (PLU kodi, nom, narx, yaroqlilik muddati); tarozining o'ziga to'g'ridan-to'g'ri yuklash — MVP'da yo'q.
- Given yorliqli tarozi yo'q, When tovar tanlanadi, Then og'irlik qo'lda kiritiladi (doimiy zahira yo'l, `06-ekranlar-umumiy.md` §1.6); yorliqsiz kassa tarozisidan Web Serial orqali jonli og'irlik — MVP'dan keyin.

**US-M09-07**: Menejer sifatida doimiy/ulgurji mijozga standart chegirma foizini mijoz kartasida belgilashni istayman.
- Given mijoz kartasi (M08/counterparty) ochilgan, When Menejer "doimiy chegirma %" maydoniga qiymat kiritadi, Then shu mijoz bilan qilingan har bir sotuvda bu chegirma avtomatik qo'llanadi.
- Given bir chekda doimiy chegirma va boshqa chegirma (kassir/aksiya) manbai to'qnashsa, Then **faqat bittasi — mijozga eng katta foyda beradigani** qo'llaniladi, ikkisi yig'ilmaydi (M03 chekka holatlar bilan bir xil qoida, qaror #23 tavsiya #8).

### Davlat tizimlari bog'liqligi
Narx QQS stavkasi — QQS 12% (SK 258-modda), 0% / imtiyoz (`vat_exemption_code`) — bilan bog'liq — har bir tovar MXIK kodiga mos QQS toifasiga ega bo'lishi kerak (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, "QQS" bandi).

### Offline xatti-harakati
Narxlar POS'ga oldindan sinxronlanadi (lokal keshda saqlanadi); offline paytida oxirgi sinxronlangan narx ishlatiladi — markazda narx o'zgargan bo'lsa, internet qaytguncha POS eski narxda sotishi mumkin (**chekka holat**).

### Chekka holatlar
- Optom va chakana narx bir vaqtda qo'llanilishi: alohida optom narx yo'q, faqat mijoz kartasidagi doimiy chegirma % (US-M09-07), eng foydali chegirma qoidasi bilan (qaror #23 tavsiya #8).
- Vaqtinchalik aksiya narxi muddati tugagandan keyin asl narxga avtomatik qaytishi.
- Offline POS'dagi eskirgan narx bilan sotilgan cheklarni keyin tuzatish kerak bo'lmasligi (narx chek yaratilish vaqtida "qotiriladi").
- Onlayn ochiq chek davomida narx o'zgarsa — chekka allaqachon qo'shilgan qator narxi qo'shilgan paytdagidek qoladi, keyin qo'shilgan qator yangi narxni oladi (offline'dagi "qotirish" qoidasi bilan bir xil).

---

## M10 — QQS

**Maqsad**: QQS'ni to'g'ri hisoblash va 2026-yildan davlat tuzgan hisobotni ichki hisob bilan solishtirish.

### Foydalanuvchi hikoyalari

**US-M10-01**: Buxgalter sifatida har bir sotuvdan QQS avtomatik hisoblanishini istayman.
- Given tovar MXIK kodiga mos QQS toifasi — QQS 12% (SK 258-modda), 0% / imtiyoz (`vat_exemption_code`) — belgilangan, When sotuv amalga oshadi, Then QQS summasi avtomatik hisoblanib chekka va buxgalteriya yozuviga kiritiladi (12% standart stavka, Soliq kodeksi 258-modda). QQS har chek qatori uchun `ROUND_HALF_UP(line_total×r/(100+r), 2)`, chek QQSi — qatorlar yig'indisi; qonunda yaxlitlash qoidasi yo'q — bu muhandislik qarori (qaror #26).
- Given QQS davri (oy) yopilmoqda, When server davr bo'yicha `tax_settlements` (`tax_kind='vat_offset'`, `period`, `base_amount`, `amount`) qoralamasini hisoblaydi, Then Buxgalter uni ko'rib tasdiqlaydi (`post`) — hisobga olinadigan QQS hisob-kitobga o'tkaziladi (`Dt 6410 / Kt 4410`, `13-provodka-qoidalari.md` §2.26); bekor qilish — `cancel`.

**US-M10-02**: Buxgalter sifatida 2026-01-01'dan davlat tuzgan QQS hisobotini ichki hisob bilan **5 ish kuni** ichida solishtirishni istayman.

**Huquqiy asos**: Soliq kodeksining 81-moddasi (O'RQ-1108-son Qonun, 2025-12-25, 2026-01-01 dan kuchda — [lex.uz/docs/-7944527](https://lex.uz/docs/-7944527)). Davlat (soliq organlari) QQS, aylanma solig'i, mol-mulk solig'i, yer solig'i, JShDS va ijtimoiy soliq hisobotlarini o'zida bor ma'lumot + shaxsiy kabinetning interaktiv xizmatiga soliq to'lovchi kiritgan ma'lumot asosida elektron shaklda shakllantiradi. **Foyda solig'i bu ro'yxatga kirmaydi.** Agar davlat shakllantirgan ma'lumot korxona hisobidan farq qilsa, korxona **5 ish kuni** ichida (SK 5-modda 7-qism; hisobot shaxsiy kabinetga joylashtirilgan kundan keyingi kundan, lekin hisobot topshirish muddatidan kechiktirmay — QQS: keyingi oyning 20-sanasi, SK 273-modda; aylanma: 15-sana, SK 470-modda) tuzatish kiritadi. **Mexanizm** (VM 736 3¹-ilova 11-band; SK 81-modda 6–8-qism): my.soliq.uz shaxsiy kabinetida "tasdiqlash" yoki "tuzatish kiritib taqdim etish" — alohida e'tiroz arizasi yo'q; javob berilmasa hisobot topshirish muddati tugagan kun davlat shakllantirgan ko'rinishda taqdim etilgan hisoblanadi; muddat o'tgach — SK 83-modda bo'yicha aniqlashtirilgan hisobot. Tizim ichki hisob va farqlar ro'yxatini tayyorlaydi; tuzatish/tasdiq my.soliq.uz kabinetida kiritiladi, tizim uni faqat qayd etadi (imzosiz, avtomatik yuborish yo'q).

**Qamrov** (MVP): faqat **QQS va aylanma solig'i** — bu ikkisi uchun tizimda to'liq ichki ma'lumot bor (M01, M07, M09, M10, M11 dan). Mol-mulk, yer, JShDS va ijtimoiy soliq — davlat ularni ham o'zi tuzadi, lekin tizimda ichki solishtirish uchun kerakli ma'lumot (asosiy vositalar hisobi, kadrlar/ish haqi) MVP modullari qatorida yo'q, shuning uchun bu to'rttasi MVP'da faqat "davlat ko'rsatgan raqam" sifatida ko'rsatiladi, ichki solishtirish qilinmaydi (keyingi bosqich). Foyda solig'i — davlat o'zi tuzmaydi, tizimda ham alohida modul yo'q, MVP'dan tashqarida, korxonaning o'zi tayyorlaydigan hisobot sifatida qoladi.

**Holat mashinasi** (`state_reports.status`): `uploaded` (Buxgalter davlat hisoboti faylini yukladi) → `compared` (avtomatik solishtirish bajarildi) → `match` (farq yo'q yoki tolerance ichida) YOKI `diff_found` (tolerance'dan tashqari farq) → Buxgalter farqni ko'rib chiqadi → `correction_sent` (tuzatish kabinetda kiritilgan, tizimda izoh bilan qayd etilgan) YOKI `confirmed` ("Tasdiqlandi" — kabinetda tasdiqlangan) YOKI `auto_accepted` (5 ish kuni ichida javob berilmagan).

- Given hisobot davri yopildi, When har oyning 10-sanasi — ichki eslatma sanasi (sozlanadi), qonuniy muddat emas — kelganda, Then tizim Buxgalterga shaxsiy kabinetning interaktiv xizmatiga kiritiladigan ma'lumotlar eslatmasini va tayyor raqamlarni beradi (aylanma — soliq solinmaydigan daromad, chegirmalar, imtiyozlar; QQS — hisobga olinadigan QQS tuzatishlari, imtiyozlar).
- Given my.soliq.uz'da davlat tomonidan tuzilgan QQS/aylanma hisoboti e'lon qilingan (kabinetdan fayl — PDF/Excel — sifatida yuklab olinadi; ommaviy API yo'q, ichki my.soliq.uz endpoint'lari ishlatilmaydi), When Buxgalter faylni tizimga yuklaydi, Then tizim ichki hisob bilan avtomatik solishtiradi: **QQS** — e-faktura darajasida (STIR + faktura raqami + sana bo'yicha moslashtirish) va yig'indi darajasida; **aylanma** — faqat yig'indi darajasida, manba (e-faktura / NKM / marketplace / eksport / boshqa — 0101–0105 satrlari) va stavka bo'yicha (ichki hisobot ham shu 5 manba bo'yicha bo'linadi: fiskal chek → 0102, e-faktura → 0101); **5 ish kunlik hisoblagich** hisobot joylashtirilgan kundan keyingi kundan, lekin shu soliq turining hisobot topshirish muddatidan oshmaydigan tarzda ishga tushadi.
- (qaror #50) Given farq `tenants.settings.vat_diff_tolerance_amount` (standart `"1000.00"` so'm; ichki UX chegarasi, har qanday farq baribir ko'rsatiladi) dan katta, Then holat `diff_found` ga o'tadi va **1-, 3- va 4-ish kunida** Buxgalterga eslatma yuboriladi; 3-ish kunigacha yopilmasa BO-10 banneri Egasiga ham ko'rinadi (26 #3).
- Given Buxgalter 5 ish kuni ichida farqni kabinetda tasdiqlagan yoki tuzatib taqdim etgan, When buni tizimda qayd etadi, Then holat `correction_sent` (tuzatilgan) yoki `confirmed` (tasdiqlangan) ga o'tadi va natija Egasiga yakuniy ko'rsatish uchun yuboriladi. Given 5 ish kuni ichida javob berilmagan, When muddat tugaydi, Then holat **`auto_accepted`** ga o'tadi (SK 81-modda).

**US-M10-03**: Buxgalter sifatida yuqori xavfli (davlat xavf-baholashi (VM 830) / qo'lda belgi "qizil"; `unknown` — qizil kabi) fakturalarning QQS kreditiga ta'sirini kuzatishni istayman.
- Given faktura "qizil" deb belgilangan (M07), When Buxgalter QQS hisobotini tayyorlaydi, Then bu fakturalar alohida ko'rsatiladi va ularning krediti hali tasdiqlanmagani belgilanadi (VM Qarori №830, 2025-12-26, 6- va 8-moddalar — `research_notes/texnik/03-efaktura-va-tolov.md`, 1.2-bo'lim).

**US-M10-04**: Buxgalter sifatida QQS to'lamaydigan, aylanma solig'i rejimidagi biznes uchun ham davlat tuzgan aylanma solig'i hisobotini ichki hisob bilan solishtirishni istayman.
- Given biznes aylanma solig'i to'lovchisi (QQS emas), When davlat 2026-01-01'dan aylanma solig'i hisobotini ham o'zi tuzadi (Soliq kodeksi 81-moddasi, O'RQ-1108), Then tizim xuddi QQS kabi ichki hisob bilan solishtirish jarayonini (US-M10-02 bilan bir xil mantiq, 5 ish kuni) qo'llaydi.
- Given tenant aylanma solig'i to'lovchisi (Soliq kodeksi 461-modda: jami daromad 1 mlrd so'mgacha), When oy yakunida ichki aylanma solig'i hisoblanadi, Then stavka 467-modda bo'yicha aniqlanadi: YTT/o'zini o'zi band qilgan — 1%; yuridik shaxs chakana savdosi — filialning "aholi punkti toifasi" bo'yicha 4% / 2% / 1% (tamaki savdosi aylanmasi har doim 4%, MXIK guruhi bo'yicha ajratiladi); boshqa faoliyat — 4%; summa filial va stavka bo'yicha alohida ko'rsatiladi (bir nechta aholi punktidagi filiallar — alohida hisob, 468-modda 2-qism). Seed stavkalari (SK 467-modda 1-qism): `city_100k_plus`=4, `other`=2, `remote_mountain`=1, `tobacco`=4, `individual_entrepreneur`=1, `general_non_retail`=4.
- Given oy yopilmoqda, When server `tax_settlements` (`tax_kind='turnover_tax'`, `period`, `base_amount`, `rate`, `amount`) qoralamasini hisoblaydi, Then Buxgalter uni tasdiqlaydi (`post`) — `Dt 9430 / Kt 6410` (`13-provodka-qoidalari.md` §4.3).
- Given jami daromad 1 mlrd so'm chegarasiga yetdi yoki tenant import qildi, Then tizim QQS rejimiga o'tish ogohlantirishini ko'rsatadi (461-modda 2-qism, 462-modda 7, 13-qism).

*Qamrov chegarasi: MVP faqat **QQS va aylanma solig'i** hisobotlarini solishtiradi. Mol-mulk, yer, JShDS va ijtimoiy soliq hisobotlari ham 2026-01-01'dan davlat tomonidan avtomatik tuziladi, lekin bular MVP'dan **tashqarida** qoladi — sabab: JShDS/ijtimoiy soliq xodim/ish haqi hisobini, mol-mulk solig'i esa asosiy vositalar hisobini talab qiladi, ikkisi ham MVP 18 moduliga kiritilmagan (qaror #52 — ish haqi hisoblash moduli yo'q; `research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #2).*

### Davlat tizimlari bog'liqligi
my.soliq.uz (davlat hisoboti), e-faktura/EDO (QQS bazasi manbai — MVP'da Faktura.uz, Didox keyinroq), VM Qarori №830 (2025-12-26, AI xavf-baholash), Soliq kodeksi 81-moddasi/O'RQ-1108 (davlat hisobot shakllantirish va 5 ish kunlik tuzatish huquqi — lex.uz/docs/-7944527), VM 736 3¹-ilova (yagona kanal — shaxsiy kabinet). Ommaviy o'qish API'si yo'q — davlat hisoboti fayl sifatida yuklanadi (26 #41 (OQ-014)). Aylanma solig'i stavkalari — Soliq kodeksi 467-moddasi (O'RQ-1108 tahririda, 2026-01-01'dan), to'lovchilar va 1 mlrd so'm chegarasi — 461-modda ([lex.uz/docs/4674902](https://lex.uz/docs/4674902)).

### Offline xatti-harakati
Deklaratsiya/solishtirish jarayoni online tizim (my.soliq.uz) talab qiladi, shuning uchun offline ishlamaydi; faqat ichki QQS hisob-kitobi (sotuvlardan) offline tayyorlanib, online bo'lganda solishtiriladi.

### Chekka holatlar
- Davlat hisoboti kutilgandan kech e'lon qilinishi — tizim ikkala chegarani (e'lon + 5 ish kuni va qonuniy topshirish muddati) hisoblab, qaysi biri birinchi kelsa shuni qo'llaydi; eslatma kunlari ham topshirish muddati bilan kesiladi.
- Farq juda katta bo'lsa (masalan tizim xatosi natijasida) — eskalatsiya jarayoni kerak.
- Qaytarish (M02) va chegirma (M03) QQS bazasini orqaga qarab tuzatishi.

---

## M11 — Buxgalteriya

**Maqsad**: savdo/ombor operatsiyalaridan NSBU №21 (2024/2025) asosidagi buxgalteriya yozuvlarini avtomatik generatsiya qilish.

### Foydalanuvchi hikoyalari

**US-M11-01**: Buxgalter sifatida har bir sotuv/xariddan avtomatik provodka olishni istayman.
- Given sotuv yakunlangan (M01), When tizim buxgalteriya modulini ishga tushiradi, Then tegishli hisob toifalari (kassa, hisob-kitob, tovar-moddiy zaxira, QQS, daromad/xarajat) bo'yicha ikki tomonlama yozuv avtomatik yaratiladi. Aniq hisob raqamlari va provodka juftliklari — NSBU №21 hisob rejasi bo'yicha `13-provodka-qoidalari.md` da (ombor — 2910, savdo zalidagi tovar — 2920, har ombor uchun `warehouses.inventory_account`).

**US-M11-02**: Buxgalter sifatida oy yakunida balans va daromad-xarajat hisobotini olishni istayman.
- Given oy yakunlangan, When Buxgalter "oy yopish"ni boshlaydi, Then barcha provodkalar yig'ilib balans va foyda-zarar hisoboti shakllanadi.
- (qaror #23, tavsiya #15) **Yopilgan oy qayta ochilmaydi**: MVP'da yopilgan davr (oy) hech qanday rolga (shu jumladan Buxgalter/Egasiga) qayta ochilmaydi; shu davrga tegishli xato aniqlansa, tuzatish **joriy ochiq oyda tuzatuvchi hujjat** (storno/qo'shimcha yozuv) bilan kiritiladi, asl yopilgan davr o'zgarmaydi (append-only). Sabab: hozircha O'zbekistonda oldingi davr xatolarini tuzatish bo'yicha alohida standart yo'q (NSFO №2 faqat 2027-01-01'dan kuchga kiradi), shuning uchun eng xavfsiz yondashuv — xalqaro tizimlardagi "lock date" tamoyili. Keyinroq (buxgalter roziligi bilan) Odoo uslubidagi "faqat Buxgalter, sabab va muddat bilan, audit yozuvli" istisno qo'shilishi mumkin — MVP'da yo'q.

**US-M11-03**: Egasi sifatida asosiy moliyaviy ko'rsatkichlarni (foyda, aylanma) sodda ko'rinishda ko'rishni istayman.
- Given tanlangan davr, When Egasi dashboard'ni ochadi, Then aylanma, xarajat, sof foyda asosiy raqamlar sifatida ko'rsatiladi (texnik tafsilotsiz).

**US-M11-04** (qaror #42): Buxgalter sifatida bank ko'chirmasi kelganda karta, UzQR, Click, Payme, Uzum tushumlari va inkassa summasini yo'ldagi pul mablag'laridan bank hisobiga o'tkazishni va komissiyani xarajatga yozishni istayman.
- Given filialda kun davomida karta bilan sotuv bo'lgan (5710 `card` qoldig'i `"950000.00"`), When Buxgalter BO-24 da «Bank tushumi tasdig'i» yaratadi (`method='card'`, `settled_from`…`settled_to`, `gross_amount="950000.00"`, `commission_amount="9500.00"`, `bank_ref`, ixtiyoriy ko'chirma fayli) va `post` qiladi, Then `Dt 5110 / Kt 5710 = "940500.00"` va `Dt 9430 / Kt 5710 = "9500.00"` yoziladi, 5710 (`card`) qoldig'i `"0.00"` (`13-provodka-qoidalari.md` §2.18a).
- Bitta hujjat — bitta filial va bitta to'lov usuli (`card`/`uzqr`/`click`/`payme`/`uzum`/`collection`); bir nechta kunlik tushumni qamrashi mumkin (`settled_from` ≤ `settled_to`).
- Given `gross_amount` shu filial va usul bo'yicha `doc_date` holatidagi 5710 qoldig'idan katta, When `post`, Then `422 VALIDATION_ERROR`, hujjat `draft` da qoladi; `commission_amount ≥ gross_amount` ham validatsiya xatosi.
- Formada tanlangan filial/usul bo'yicha joriy 5710 qoldig'i (bankka hali o'tmagan tranzit, `GET /api/v1/bank-settlements/transit-balances`) ko'rsatiladi; `net_amount = gross_amount − commission_amount + variance_amount` avtomatik hisoblanadi (`variance_amount` — faqat inkassa, manfiy — kamomad).
- Given Buxgalter bank ko'chirmasi faylini (1CClientBankExchange `.txt`) BO-24 da yuklaydi (`POST /api/v1/bank-settlements/imports`), Then faqat **kirim** qatorlari o'qiladi va `bank_settlements` **qoralamalari** taklif qilinadi: `method` to'lovchi (ekvayer bank / Click / Payme / Uzum / MUNIS STIR) va to'lov maqsadi bo'yicha aniqlanadi, `gross_amount`ni Buxgalter shu usul/filial bo'yicha 5710 qoldig'idan tanlaydi, `commission_amount = gross − kirim`; `post` — faqat Buxgalter.
- Bekor qilish — storno (`cancel`, sabab majburiy); yopilgan davrga tegmaydi. `cash_moves` yozilmaydi — faqat `ledger_entries`.
- Ruxsat — `bank_settlements.manage` (Egasi, Buxgalter); faqat back-office, POS'da yo'q (sync voqeasi yo'q).
- Karta/UzQR/Click/Payme/Uzum tushumi va inkassa 5710 orqali (NSBU 21 Yo'riqnoma 237–239-band); bank/ekvayring komissiyasi — **9430** (410-band), inkassa komissiyasi — 9410 (qaror #42).

### Davlat tizimlari bog'liqligi
NSBU №21 (2024/2025, 191-son buyruq) hisob rejasi — eski 2002-yilgi reja **emas**; moliyaviy hisobot shakllari — MEF №181 (08.10.2024) 1- va 2-ilova.

### Offline xatti-harakati
Markazlashtirilgan serverda ishlaydi, offline kiritilmaydi; faqat sotuv/xarid ma'lumotlari kelib tushgandan keyin provodka yaratiladi.

### Chekka holatlar
- Avtomatik provodkada xato aniqlansa, qo'lda tuzatish imkoniyati (audit-trail bilan) kerak — yopilgan oyda esa faqat joriy ochiq oyda tuzatuvchi yozuv orqali (yuqoridagi US-M11-02).
- Ko'p filialli (M14) konsolidatsiyalangan balans.
- Naqdsiz tushum bankka hali tushmagan (bank tushumi tasdig'i yaratilmagan) — summa 5710 da qoladi; «yo'ldagi pul» qoldig'i to'lov usuli va filial bo'yicha BO-24 da ko'rinadi. Bank ko'chirmasi faylidan import (`source='statement_import'`) faqat `draft` hujjat yaratadi — Buxgalter tekshirib `post` qiladi.
- To'liq NSBU hisob rejasi (asosiy vositalar, ish haqi) MVP'dan tashqarida — faqat savdo/ombordan kelib chiqadigan asosiy hisoblar avtomatlashtiriladi (qaror #52; `research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #2).

---

## M12 — Hisobotlar

**Maqsad**: savdo, ombor, buxgalteriya va QQS bo'yicha tushunarli hisobotlar berish.

### Foydalanuvchi hikoyalari

**US-M12-01**: Egasi sifatida kunlik savdo hisobotini (umumiy va filial bo'yicha) ko'rishni istayman.
- Given kun yakunlangan (yoki jarayonda), When Egasi hisobotni ochadi, Then jami savdo, chek soni, o'rtacha chek summasi filial bo'yicha ajratib ko'rsatiladi (M14 bilan bog'liq).

**US-M12-02**: Menejer sifatida eng ko'p/kam sotiladigan tovarlar hisobotini olishni istayman.
- Given tanlangan davr, When Menejer hisobotni so'raydi, Then tovarlar sotuv miqdori bo'yicha tartiblangan ro'yxat ko'rsatiladi.

**US-M12-03**: Buxgalter sifatida QQS va davlat solishtirish hisobotini eksport qilishni istayman.
- Given M10'dagi solishtirish yakunlangan, When Buxgalter "eksport" tugmasini bosadi, Then hisobot Excel/PDF formatda yuklab olinadi.

### Davlat tizimlari bog'liqligi
Rasmiy shakllar: QQS — DSQ qarori №3221 1-ilova (№3221-8 tahriri, 2026-01-01), aylanma solig'i — 9-ilova; moliyaviy hisobot — MEF №181 1- va 2-ilova (kichik korxona, yillik). MVP: rasmiy shakl satr kodlari bilan Excel/PDF **tayyorlov** eksporti; topshirish — Buxgalter shaxsiy kabinetda (XML/operator API orqali topshirish yo'q).

### Offline xatti-harakati
Hisobotlar faqat online holatda to'liq va aniq; offline paytda faqat mahalliy keshdagi (sinxronlanmagan) ma'lumot bilan qisman ko'rsatiladi, bu holat foydalanuvchiga aniq bildiriladi.

### Chekka holatlar
- Katta hajmli ma'lumotni eksport qilishda vaqt/hajm chegarasi.
- Bir nechta filial turli vaqt zonasida bo'lmasa ham, smena vaqtlari mos kelmasligi hisobotni chalkashtirishi mumkin.

---

## M13 — Huquqlar

**Maqsad**: rol asosida foydalanuvchi huquqlarini (ko'rish/yaratish/tasdiqlash) boshqarish, kichik do'konda rol birlashuviga imkon berish; shu bilan birga — Egasi uchun xodim/foydalanuvchi va ularning sessiyalarini (kirgan qurilmalar) to'liq boshqarish paneli. Autentifikatsiya **o'z (mustaqil) OAuth 2.0 implementatsiyasi** asosida quriladi, hech qanday mock/soxta login yo'q (qaror #14) — texnik arxitektura `spec/kod-uchun/14-autentifikatsiya-oauth2.md`da.

### Foydalanuvchi hikoyalari

**US-M13-01**: Egasi sifatida yangi xodim qo'shib, unga bir yoki bir nechta rol (Kassir/Omborchi/Menejer/Buxgalter) belgilashni istayman.
- Given yangi xodim ma'lumoti kiritildi, When Egasi rol(lar)ni tanlaydi, Then xodim login huquqlari shu rol(lar)ga mos modul ruxsatlarini oladi (`02-rollar-va-ssenariylar.md`, 6-bo'lim, huquqlar matritsasi).

**US-M13-02**: Egasi sifatida kichik do'konda bitta xodimga bir nechta rolni birlashtirib berishni istayman.
- Given xodim bir vaqtning o'zida Kassir va Omborchi bo'lishi kerak, When Egasi ikkita rolni belgilaydi, Then xodim ikki rolning jamlangan huquqlariga ega bo'ladi.

**US-M13-03**: Menejer sifatida operatsiya chegaralarini (masalan chegirma/qaytarish limiti) rolga yoki shaxsga bog'lab sozlashni istayman.
- Given limit o'zgartirilishi kerak, When Menejer yangi limitni kiritadi, Then bu limit tegishli rol/xodim uchun darhol kuchga kiradi.

**US-M13-04**: Egasi sifatida yangi xodimni admin panel orqali to'liq ma'lumoti bilan (telefon, ism, rol(lar), filial(lar)) qo'shishni istayman.
- Given "Foydalanuvchi qo'shish" ochildi, When Egasi telefon raqami, to'liq ism, rol(lar) va qaysi filial(lar)da ishlaydi (M14) kiritadi, Then xodim yaratiladi va unga bir martalik taklif kodi (OTP, `purpose=invite`) yuboriladi — (qaror #34) **birinchi navbatda Telegram bot** orqali (xodim botga ulangan bo'lsa) yoki xodim hali botga ulanmagan bo'lsa, bot havolasi va bir martalik taklif kodi; Telegram mavjud bo'lmasa — **SMS zaxira sifatida**; xodim shu kod bilan o'zi parol va/yoki PIN o'rnatadi (parol/PIN hech qachon ochiq matnda — Telegram yoki SMS'da — yuborilmaydi).
- Xodim faqat o'ziga tayinlangan filial(lar) ma'lumotini ko'radi/boshqaradi (boshqa filiallar yopiq).

**US-M13-05**: Egasi sifatida xodimni vaqtincha bloklashni/blokdan chiqarishni istayman.
- Given xodim ro'yxatda tanlangan, When Egasi "Bloklash" bosadi, Then xodimning barcha faol sessiyalari/tokenlari darhol bekor qilinadi (revoke) va u qayta login qila olmaydi, toki Egasi "Blokdan chiqarish"ni bosmaguncha.
- Xodim ishdan bo'shaganda ham xuddi shu "Bloklash" amali ishlatiladi.

**US-M13-06**: Egasi sifatida xodimning parolini/PIN kodini qayta tiklashni (reset) istayman.
- Given xodim parolini/PIN'ini unutgan, When Egasi "Parolni tiklash" bosadi, Then eski parol/PIN bekor qilinadi, xodimning barcha faol sessiyalari tugatiladi va unga bir martalik tiklash kodi (OTP, `purpose=admin_reset`) yuboriladi — (qaror #34) **Telegram bot orqali birinchi navbatda**, Telegram ulanmagan bo'lsa **SMS zaxira**; xodim shu kod bilan yangi parol/PIN o'rnatadi (parol/PIN hech qachon ochiq matnda yuborilmaydi).
- Xodimning o'zi ham login ekranidan OTP orqali parol tiklashni so'rashi mumkin — kod Telegram botga (ulangan bo'lsa) yoki SMS'ga (zaxira) yuboriladi (`06-ekranlar-umumiy.md`, BO-01/POS-01 login holatlari).

**US-M13-07**: Egasi sifatida har bir xodimning faol sessiyalarini (qaysi qurilma, qachon kirgan, oxirgi faollik) ko'rishni va kerak bo'lsa bekor qilishni istayman.
- Given xodim tanlangan, When Egasi "Sessiyalar/qurilmalar" bo'limini ochadi, Then shu xodimning barcha faol sessiyalari (qurilma turi, IP/joylashuv — mavjud bo'lsa, kirgan vaqt, oxirgi faollik) ro'yxati ko'rinadi.
- Given bitta sessiya shubhali (masalan yo'qolgan qurilma), When Egasi "Bekor qilish" bosadi, Then shu sessiyaning tokeni darhol bekor qilinadi, qurilma login ekraniga qaytariladi, boshqa sessiyalarga ta'sir qilmaydi.

**US-M13-08** (M17 US-M17-04 bilan bog'liq): Platforma admini sifatida tenantlar va ularning Egasi (owner) hisoblarini boshqarishni istayman.
- Given platforma admin paneli (ADM-01), When admin tenant tanlaydi, Then Egasi hisobini bloklash/blokdan chiqarish, Egasi parolini tiklash va Egasining faol sessiyalarini ko'rish/bekor qilish mumkin (masalan nizoli holatda yoki to'lov bo'yicha).
- Platforma admini oddiy tenant foydalanuvchilarining (Kassir/Menejer/Buxgalter) kundalik ma'lumotiga kirmaydi — faqat Egasi hisobi va obuna/texnik holat darajasida (`02-rollar-va-ssenariylar.md`, M15–M18 izohi: `platform.admin` tenant rollariga kirmaydi).

### Davlat tizimlari bog'liqligi
To'g'ridan-to'g'ri davlat talabi yo'q; lekin E-IMZO bilan imzolangan hujjatlar (e-faktura, hisobotlar) uchun aniq qaysi shaxs imzolagani audit maqsadida kerak.

### Offline xatti-harakati
Rol/huquqlar markazdan sinxronlanadi; offline rejimda faqat oxirgi sinxronlangan huquqlar amal qiladi, o'zgartirish faqat online holatda mumkin. Bloklash/sessiya bekor qilish amali internetga bog'liq — qurilma offline bo'lsa, bekor qilish shu qurilma keyingi marta internetga ulanganda kuchga kiradi.

### Chekka holatlar
- Xodim ishdan bo'shaganda huquqni darhol (real-time) bekor qilish — US-M13-05/US-M13-07 orqali yechiladi: Egasi xodimni bloklaydi yoki aniq sessiyani bekor qiladi, token darhol amal qilmay qoladi.
- Bir xodimga berilgan ikki rol o'rtasida huquq ziddiyati (masalan bir modulda bir rol "T" beradi, ikkinchisi bermaydi) — yuqori huquq ustun bo'lishi kerak.
- Egasi o'zining yagona hisobini bloklay olmasligi kerak (tenant egasiz qolib ketmasin) — platforma admini orqali tiklash yo'li saqlanadi (US-M13-08).

---

## M14 — Filiallar

**Maqsad**: ko'p filialni (do'kon/ombor) bitta tizimda boshqarish va konsolidatsiyalangan hisobot berish.

(qaror #31) **Yuridik shaxs — filial munosabati**: bitta do'kon (tenant) = **1 yuridik shaxs** (yoki YTT); shu bitta yuridik shaxs ichida **ko'p faoliyat turi, ko'p filial va ko'p kassa** qo'llab-quvvatlanadi — bular cheklanmaydi. Filialning faoliyat turi `branches.activity_type` maydonida saqlanadi (masalan chakana savdo, ulgurji, aralash — aniq ro'yxat arxitektura jamoasi bilan, `kod-uchun/11-malumotlar-modeli.md`); har bir faoliyat turi/filial o'zining MXIK/QQS va "aholi punkti toifasi" (US-M14-04) sozlamalariga ega bo'lishi mumkin. Bir nechta **yuridik shaxs** (masalan bir egasining ikki alohida firmasi) bitta tenant ichida qo'llab-quvvatlanmaydi — bu holat alohida tenant/obuna talab qiladi (M17).

### Foydalanuvchi hikoyalari

**US-M14-01**: Egasi sifatida barcha filiallar bo'yicha konsolidatsiyalangan savdo/ombor holatini ko'rishni istayman.
- Given 2 va undan ko'p filial mavjud, When Egasi umumiy dashboard'ni ochadi, Then har bir filial alohida va jami ko'rinishda ko'rsatiladi.

**US-M14-02** (MVP'dan keyin — qaror #33): Menejer sifatida bitta filialdan boshqasiga narx/chegirma siyosatini nusxalashni istayman.
- Given manba filial tanlangan, When Menejer "nusxalash"ni bosib maqsad filialni tanlaydi, Then narx/chegirma qoidalari maqsad filialga ko'chiriladi.

**US-M14-03**: Egasi sifatida yangi filial (do'kon) qo'shishni istayman.
- Given biznes yangi do'kon ochyapti, When Egasi yangi filialni ro'yxatdan o'tkazadi (nom, manzil, kassa soni), Then filial tenant ichida yangi mustaqil ombor/kassa birligi sifatida yaratiladi.

**US-M14-04**: Egasi sifatida har bir filial uchun "aholi punkti toifasi"ni belgilashni istayman, chunki chakana savdoda aylanma solig'i stavkasi joylashuvga bog'liq (Soliq kodeksi 467-modda, O'RQ-1108 tahririda, 2026-01-01'dan).
- Given yangi filial yaratilmoqda yoki tahrirlanmoqda, When Egasi "aholi punkti toifasi"ni tanlaydi (Shahar, aholisi 100 ming+ / Boshqa aholi punkti / Borish qiyin yoki tog'li tuman), Then filialning chakana savdo aylanmasiga mos stavka (4% / 2% / 1%) qo'llanadi.
- Given toifa tanlanmagan, When filial saqlanadi, Then standart qiymat "Shahar, 100 ming+" (4%, eng ehtiyotkor) qo'yiladi va Egasiga tekshirish eslatmasi ko'rsatiladi.
- Given toifa o'zgartirildi, When saqlanadi, Then yangi stavka faqat `valid_from` sanasidan boshlab qo'llanadi, oldingi davrlar qayta hisoblanmaydi.

### Davlat tizimlari bog'liqligi
Dastur (versiya) Davlat reyestriga bir marta kiritiladi (VMQ-943 4-ilova 3-band). **Har bir `cash_register`** savdodan oldin shoxobcha manzili bo'yicha TXKM orqali soliq organida alohida ro'yxatdan o'tadi (1-ilova 16–20-band: bepul, ≈4+8 ish soati) va alohida fiskal modulga ega bo'ladi (2-ilova 6-band); `cash_registers.tax_registered_at`, `outlet_address_snapshot`, `txkm_contract_ref`. Ro'yxatdan o'tmagan (`ofd_status` `registered`/`active` emas) kassada fiskal chek chiqarilmaydi (SK 221-modda 2-qism). Filial manzili o'zgarsa — shu filial kassalari uchun **3 ish kunida** qayta ariza eslatmasi (25-band).

### Offline xatti-harakati
Har bir filial o'z offline event-log'iga ega; filiallar o'zaro real-time sinxronlanmaydi, markaziy serverga ulanganda sinxronlanadi (offline-first; qaror #12, #43).

### Chekka holatlar
- Filiallar orasida bir xil tovarga turli narx siyosati (ruxsat etiladimi — biznes qoidasi).
- Bitta mijozning bir nechta filialdagi nasiya balansi — tenant darajasida yagona balans, filial faqat hisobotda qator darajasida (26 #7).
- Bir xil MXIK/QQS stavkasi barcha filiallarda bir xil bo'lishi (farqlanishi mumkin emas). **Lekin aylanma solig'i stavkasi filiallar bo'yicha farq qilishi mumkin** (467-modda: chakana savdo joylashuvga qarab 4% / 2% / 1%) — turli toifadagi filiallari bor tenant uchun aylanma filial bo'yicha alohida hisoblanadi (468-modda 2-qism — alohida hisob). Tamaki savdosi aylanmasi (YTT ham) — 4% (qaror #11, 26 #111 (OQ-017)).

---

## M15 — Xarajatlar

**Maqsad**: do'konning operatsion xarajatlarini (ijara, kommunal, ish haqi to'lovi, transport va h.k.) yozib borish, shunda Egasi **haqiqiy sof foydani** ko'radi.

### Foydalanuvchi hikoyalari

**US-M15-01**: Egasi/Menejer sifatida xarajatni 10 soniyada yozishni istayman.
- Given "Xarajat qo'shish" ochildi, When summa, toifa, to'lov manbai (kassa naqdi / bank / karta) va (ixtiyoriy) izoh kiritiladi, Then xarajat saqlanadi; manba "kassa naqdi" bo'lsa, M16'da avtomatik "kassadan chiqim" yozuvi yaratiladi.
- Toifalar standart ro'yxat bilan keladi — `13` §2.17 seed xaritasi (21 kod, ish haqi 9410/9420 alohida); Egasi o'zgartira oladi.
- Chek/hujjat fotosini biriktirish mumkin (ixtiyoriy).

**US-M15-02**: Egasi sifatida doimiy xarajatlarni (oylik ijara) har oy qayta kiritmaslikni istayman.
- Given takrorlanuvchi xarajat (summa, sana, davr) sozlangan, When muddat keladi, Then tizim "Ijara to'lash vaqti: 3 000 000 so'm" eslatmasini beradi; Egasi bir bosishda tasdiqlaydi (avtomatik to'lanmaydi).

**US-M15-03**: Egasi sifatida haqiqiy foydani ko'rishni istayman.
- Given davr tanlangan, When dashboard/hisobot ochiladi, Then **Sof foyda = Sotuv tushumi − Sotilgan tovar tannarxi (M04, FIFO/AVECO) − Xarajatlar (M15)**, toifalar bo'yicha xarajat taqsimoti bilan ko'rsatiladi.
- Xarajatlar M11 buxgalteriyada tegishli xarajat hisobiga o'tkaziladi (aniq hisob raqamlari — `13-provodka-qoidalari.md`da).

### Davlat tizimlari bog'liqligi
To'g'ridan-to'g'ri yo'q. Ish haqi soliqlari (JShDS, ijtimoiy soliq) hisoblanmaydi — kadrlar/ish haqi moduli MVP'dan tashqarida; bu yerda faqat "ish haqi to'landi" summasi yoziladi.

### Offline xatti-harakati
Kassadan to'langan xarajat POS'da offline yoziladi (M16 bilan birga), sinxronlashda serverga tushadi.

### Chekka holatlar
- Xarajat bekor qilinsa — o'chirilmaydi, teskari yozuv bilan bekor qilinadi (audit).
- Bir xarajat bir nechta filialga tegishli (umumiy ijara) — MVP'da bitta filialga yoziladi, taqsimlash keyin.

---

## M16 — Kassa pul harakati (naqd pul)

**Maqsad**: kassadagi naqd pulning har bir harakati yozilsin; smena oxirida "kassada qancha bo'lishi kerak" va "qancha bor" aniq solishtirilsin.

### Foydalanuvchi hikoyalari

**US-M16-01**: Kassir sifatida kassaga pul qo'yish va kassadan pul olishni sabab bilan yozishni istayman.
- Given smena ochiq, When kassir "Pul qo'yish" (maydalash uchun) yoki "Pul olish" ni tanlaydi, Then summa, sabab (Egasi oldi / Inkasso / Xarajat to'lovi → M15 / Boshqa) va kim bajargani yoziladi.
- (qaror #23, tavsiya #1) **Standart limit**: Kassir PIN'siz kassadan pul olishni **50 000 so'mgacha** mustaqil amalga oshiradi; shundan katta "Pul olish" — Egasi/Menejer PIN tasdig'i bilan. Egasi istalgan raqamni (M13 orqali) o'zgartirishi mumkin.

**US-M16-02**: Kassir sifatida smena yopilganda kassadagi pulni sanab kiritishni istayman.
- Given smena yopilmoqda, When kassir sanalgan naqd summani kiritadi, Then tizim **kutilgan naqd** (boshlang'ich naqd + naqd sotuvlar − naqd qaytarishlar + naqd qarz to'lovlari + qo'yilgan − olingan) bilan solishtiradi va farqni (kamomad/ortiqcha) ko'rsatadi.
- Farq bo'lsa, kassir izoh yozadi va Egasiga xabar ketadi (M18).
- (qaror #23, tavsiya #6, qaror #71) Smena yopilganda naqd bilan bir qatorda **"karta" jami** ikki qatorda — "Karta (integratsiyalangan)" (karta turi va `rrn` bilan) va "Karta (terminalsiz)" (faqat summa) — alohida ko'rsatiladi (POS-07 Z-hisobot `z_report.card_split {integrated, manual}`, POS-15); hal qilinmagan karta urinishi bo'lsa smena yopilmaydi (`CARD_OUTCOME_UNKNOWN`); integratsiyalangan qism terminal `settlement` natijasi bilan avtomatik solishtiriladi, bank ko'chirmasi (BO-24) integratsiyalangan qism uchun `rrn` bo'yicha, terminalsiz qism uchun summa/sana (va ko'chirmadagi filial/merchant) bo'yicha moslashtiriladi.

**US-M16-03**: Egasi sifatida har bir smena va kassa bo'yicha naqd pul tarixini ko'rishni istayman.
- Given davr tanlangan, When "Kassa harakati" hisoboti ochiladi, Then har bir smena bo'yicha: boshlanish, sotuvlar, qo'yilgan/olingan (kim, nega), kutilgan va sanalgan naqd, farq.

### Davlat tizimlari bog'liqligi
Fiskal bo'lmagan operatsiya; OFD'ga yuborilmaydi (VMQ-943 2-ilova 11-band — fiskal modulga faqat sotish va qaytarish). Fiskal hamkor protokoli talab qilsa — faqat adapter darajasida ixtiyoriy aks ettirish.

### Offline xatti-harakati
To'liq offline ishlaydi (M01 bilan bir xil append-only jurnal).

### Chekka holatlar
- Bir smenada kassir almashsa (masalan tushlik) — MVP'da joriy smena yopiladi (POS-15 sanash + Z-hisobot) va yangi kassir yangi smena ochadi; ochiq smena ichida topshirish — MVP'dan keyin.
- Aralash to'lovdagi naqd qismi kutilgan naqdga kiradi.

---

## M17 — Obuna va ro'yxatdan o'tish (platforma)

**Maqsad**: do'kon tizimga o'zi ro'yxatdan o'tsin, sinab ko'rsin, obuna uchun to'lasin — bu bizning daromad oqimimiz. (qaror #22) Tarif **yagona** (99 000 so'm/oy, hammasi narxga kiradi); Egasi faqat qo'shimcha kassa sonini va oylik/yillik to'lov davrini tanlaydi (`05-mvp-chegarasi.md`, 3.3).

### Foydalanuvchi hikoyalari

**US-M17-01**: Do'kon egasi sifatida 2 daqiqada ro'yxatdan o'tishni istayman.
- Vaqt mezoni: ro'yxatdan o'tish ≤ 2 daqiqa; 500 tovar Excel importi bilan birga ≤ 10 daqiqa (`27` Bosqich 1 tayyor ta'rifi, QT-NFR-SIGNUP-01).
- (qaror #34) Given sayt ochildi, When Egasi ro'yxatdan o'tish/kirish usulini tanlaydi, Then ikki yo'l mavjud: (1) **telefon raqami + parol** (ro'yxatdan o'tishda telefon bir martalik kod bilan tasdiqlanadi — kod birinchi navbatda **Telegram bot** orqali, agar foydalanuvchi hali botga ulanmagan bo'lsa, bot havolasi ko'rsatilib shu yerda tasdiqlanadi; Telegram mavjud bo'lmasa **SMS zaxira**), yoki (2) **"Google bilan kirish"** — bizning OAuth 2.0 authorization serverimizda Google OIDC tashqi provayder sifatida ulangan, alohida parol/kod talab qilinmaydi. Ikkala yo'ldan keyin ham do'kon nomi, faoliyat turi va huquqiy shakl (`tenants.legal_form`: `llc|jsc|private_enterprise|sole_proprietor`) so'raladi; STIR, OFD, e-faktura ulash keyinroq (sozlamalarda, bosqichma-bosqich yo'riqnoma bilan).
- (qaror #61) Given ro'yxatdan o'tish formasi (BO-21), When Egasi davom etadi, Then **foydalanish shartlari** (o'zbek tilida) bilan tanishib roziligini belgilashi majburiy — `tenants.accepted_terms_version`, `accepted_terms_at`, `accepted_terms_ip` saqlanadi; **chegaradan tashqariga uzatishga (AI — Anthropic, AQSh) alohida rozilik** ixtiyoriy belgi sifatida so'raladi (`consents`, `purpose='ai_cross_border'`); rozilik berilmaguncha `settings.ai_cross_border_enabled=false` — AI-03 rasmlari yuborilmaydi (AI-03 o'chiq), matnli AI faqat maskalangan ma'lumot bilan ishlaydi. Rozilikni Egasi keyin BO-14'da berishi yoki qaytarib olishi mumkin.
- Ro'yxatdan o'tgach **30 kunlik bepul sinov** boshlanadi (qaror #22 — yagona tarifning to'liq imkoniyatlari bilan).
- (qaror #34) **Kirish (login)** ham xuddi shu ikki usul bilan: telefon+parol yoki "Google bilan kirish"; Google hisobi ulangan foydalanuvchi istalgan vaqt telefon+parolga ham o'tishi mumkin (sozlamalarda). SMS (Eskiz) — faqat Google ham, Telegram ham yo'q/ulanmagan foydalanuvchi uchun **zaxira** kanal; Google'ning o'z SMS-asosli telefon autentifikatsiyasi (Firebase phone auth) pullik bo'lgani uchun ishlatilmaydi.

**US-M17-02**: Egasi sifatida tarifni tanlash va to'lashni istayman.
- Given sinov tugayapti yoki Egasi "Tarif" ni ochadi, Then **tarif tanlovi yo'q** — faqat bitta yagona tarif (99 000 so'm/oy, barcha modul+1 virtual kassa+AI+Telegram) va oylik/yillik (−20%) tanlanadi (qaror #22, `05-mvp-chegarasi.md`, 3.3); to'lov Click yoki Payme orqali amalga oshiriladi va obuna muddati uzayadi, to'lov uchun hujjat beriladi.
- Given Egasi qo'shimcha savdo nuqtasi (kassa) ochmoqchi, When "Qo'shimcha kassa qo'shish" tugmasini bosadi, Then har bir qo'shimcha kassa uchun **+39 000 so'm/oy** (qaror #22) obuna summasiga qo'shiladi, keyingi to'lovdan qo'llanadi.
- Tarif limitlari tizimda qo'llanadi: faol kassalar soni (asosiy 1 + sotib olingan qo'shimchalar), AI oylik limiti; filiallar soni cheklanmaydi (filial — M14, kassa — M17 obunasi, ikkisi alohida tushuncha).

**US-M17-03**: Egasi sifatida to'lov muddatini unutmasligim va muddat o'tsa ham darhol to'xtab qolmasligimni istayman.
- **Eslatmalar (muddatdan oldin):** to'lov sanasidan **3 kun**, **1 kun** oldin va **to'lov kuni ertalab** — Egasiga Telegram (M18), ilova ichida banner va SMS (Telegram ulanmagan bo'lsa). Xabarda: summa, tarif, "To'lash" havolasi (Click/Payme). Bu kanal tartibi (Telegram bot birinchi, SMS faqat zaxira) qaror #34 bilan izchil.
- **Muddat o'tganda — 24 soatlik imtiyoz:** Given to'lov muddati o'tdi va to'lov kelmadi, Then tenant `grace` holatiga o'tadi va **24 soat davomida hamma narsa odatdagidek ishlaydi** (kassa, back-office, AI — barchasi to'liq ishlaydi); barcha ekranlarda qizil banner: "Obuna muddati o'tdi. 24 soat ichida to'lang, aks holda kassa to'xtaydi" + qolgan vaqt hisoblagichi.
- **Imtiyoz davomidagi eslatmalar:** muddat o'tishi bilan darhol, **12 soat qolganda** va **2 soat qolganda** — Telegram + banner + SMS.
- **24 soat o'tgach — to'liq to'xtash** (qaror #15): Given 24 soatlik imtiyoz tugadi va to'lov hali kelmadi, Then tenant `restricted` holatiga o'tadi va butun tenant uchun kirish **to'liq yopiladi**: (a) tenant'ning barcha faol sessiya/tokenlari serverda bekor qilinadi (revoke); (b) har bir ochiq ekran — kassa (Android POS/veb-kassa) va back-office — darhol login sahifasiga qaytariladi; (c) login sahifasida "Obuna muddati tugagan" xabari va Click/Payme orqali to'lov havolasi ko'rsatiladi; (d) shu tenant hisoblaridan **yangi kirish ham rad etiladi**, to'lov amalga oshmaguncha. Boshqacha aytganda, kassa sotuvi ham, back-office ham — **hech biri** ishlamaydi.
- (qaror #19, D1) **Lokautdan oldingi offline cheklarni yuborish (drain)**: yuqoridagi band bo'yicha `restricted` holatda yangi sotuv, login va boshqa barcha amal yopiq qoladi — lekin **lokautdan oldin** (24 soatlik imtiyoz davrida) offline qurilmada allaqachon yaratilgan, hali OFD'ga yuborilmagan cheklar 48 soatlik fiskal blokka (qaror #43) yetmasligi uchun fon rejimida (`sync.drain`) serverga va OFD'ga yuborilishda davom etadi. Bu yagona istisno: kassirga yangi ekran ochilmaydi, yangi sotuv qilib bo'lmaydi — faqat avval yaratilgan hujjatlar fonda yuboriladi.
- **Offline qurilmalar**: internetga ulanmagan kassa/POS qurilmasi serverdan signal kutmaydi — qurilmadagi mahalliy imzolangan litsenziya (`valid_until = min(grace_ends_at, issued_at + 7 kun)`, qaror #15) tugagan payt qurilma **o'zi mahalliy ravishda qulflanadi**; internet qaytib, yangi muddatli litsenziya tasdiqlanmaguncha qurilma qayta ochilmaydi. To'lov qilinganda qurilma tokenlari bekor qilinmaydi, balki `suspended` holatidan tiklanadi — qurilma keyingi onlayn bo'lishida jim (silent) ravishda yangi litsenziya oladi va kassir qayta parol kiritmasdan, PIN bilan ishni davom ettiradi.
- To'lov kelishi bilan darhol `active` holatiga qaytadi, kirish qayta ochiladi va "To'lov qabul qilindi, rahmat" xabari ketadi.
- Ma'lumotlarni eksport qilish (Excel) huquqi `active` holatda odatdagidek ishlaydi. `restricted` holatda back-office/kassaning o'zi butunlay yopiq, lekin (qaror #20, qaror #34) login sahifasidagi to'lov havolasi ochadigan **to'lov sahifasidan** "Ma'lumotlarimni yuklab olish" tugmasi orqali, bir martalik tasdiqlash kodi **birinchi navbatda Telegram bot** orqali (ulangan bo'lsa), aks holda telefon raqamiga **SMS** (zaxira) yuboriladi; shu kod bilan tasdiqlangandan keyin to'liq eksport (US-M17-05'dagi kabi ZIP) so'rash mumkin — bu login yoki boshqa hech qanday ekranni ochmaydi, faqat eksport faylini tayyorlab beradi.
- **Foydalanish shartnomasi (ToS) eslatmasi** (qaror #15): xizmat shartlarida aniq ko'rsatilishi shart — to'lov kechiktirilib kassaga kirish to'xtatilgan davrda ham do'kon o'zining fiskal/soliq majburiyatlari uchun (agar savdo boshqa vosita bilan davom etsa) **to'liq o'zi javobgar** ekanligi; oferta yakuniy matni yurist bilan tayyorlanadi (Ochiq savollar 17).

**US-M17-04**: Platforma admini sifatida (bizning jamoa) tenantlar, obunalar, to'lovlar va limitlarni ko'rishni istayman.
- Given ichki admin panel, When tenant tanlanadi, Then obuna holati, to'lov tarixi, AI sarfi, faol kassalar soni ko'rinadi; muddatni qo'lda uzaytirish (masalan pilot do'konlarga) mumkin — `billing_payments(kind='manual_extension', amount="0.00", reason)` yozuvi yaratiladi va tenant to'lov tarixida ko'rinadi (qaror #56).

**US-M17-05** (Could; MVP'dan keyin — qaror #33): Egasi sifatida xizmatdan chiqsam ham barcha ma'lumotlarimni olib ketishni istayman.
- Given tenant **o'z xohishi bilan** `closed` holatga o'tgan (xizmatdan voz kechgan, obuna to'lovi kechikkani uchun emas), When Egasi "To'liq eksport"ni bosadi, Then barcha ma'lumotnomalar, hujjatlar va registrlar CSV (har jadval alohida) + asosiy hisobotlar PDF bitta ZIP faylda yuklanadi; amal audit jurnaliga yoziladi.
- Given tenant `closed`, Then ma'lumot kamida 90 kun eksport uchun saqlanadi (eksport formati — har jadval CSV + `manifest.json`, qaror #51); keyingi o'chirish tartibi huquqiy maslahatdan keyin (buxgalteriya hujjatlari muddati **kamida 5 yil**, qaror #7).
- (qaror #20) `restricted` holat (to'lov kechikkani uchun kirish to'xtatilgan, US-M17-03) bu **to'liq** hikoyaga asosan **kirmaydi** — back-office/kassaga umuman kirib bo'lmaydi. Lekin tor istisno sifatida US-M17-03'dagi kabi **faqat to'lov sahifasidan, Telegram bot (yoki zaxira SMS) kod bilan tasdiqlangan** "Ma'lumotlarimni yuklab olish" yo'li mavjud (login yoki boshqa ekranlar ochilmaydi). To'liq (barcha jadval/hisobotlar bilan) eksport faqat to'lov qilib `active` holatga qaytgandan keyin yoki ixtiyoriy `closed` oqimida mavjud.

### Davlat tizimlari bog'liqligi
Mijozga bizning xizmatimiz uchun beriladigan hujjat — bizning yuridik shaxsimizning soliq majburiyati (mahsulot funksiyasi emas).

### Offline xatti-harakati
Ro'yxatdan o'tish va to'lov — faqat online. (qaror #15) Offline qurilma (internetga ulanmagan kassa) serverdan signal kutmaydi — qurilmada mahalliy saqlangan, imzolangan litsenziya (`valid_until = min(grace_ends_at, issued_at + 7 kun)`) bor; shu muddat tugaganda qurilma **o'zi mahalliy ravishda qulflanadi** (login ekraniga qaytadi), internet qaytib yangi muddatli litsenziya tasdiqlanmaguncha qayta ochilmaydi.

### Chekka holatlar
- To'lov o'tdi, lekin tizimga xabar kelmadi — Click/Payme holatini qayta tekshirish.
- **Qo'shimcha kassa sonini kamaytirish**: Egasi qo'shimcha kassalardan voz kechsa, faol kassalar soni yangi (kamroq) sonidan ko'p bo'lsa, ortiqcha kassa(lar)ni o'chirish/arxivlash so'raladi — ma'lumot (tarix, hujjatlar) o'chirilmaydi, faqat shu kassa yangi sotuv uchun yopiladi.

---

## M18 — Bildirishnomalar va Egasi uchun Telegram bot

**Maqsad**: Egasi do'konda bo'lmasa ham asosiy raqamlar va muammolarni Telegram orqali bilsin.

### Foydalanuvchi hikoyalari

**US-M18-01**: Egasi sifatida Telegram akkauntimni do'konga ulashni istayman.
- Given back-office BO-20 ekranida "Telegram ulash" bosildi (qaror #56), When Egasi bot havolasini ochib "Start" bosadi, Then akkaunt bir martalik kod orqali tenantga bog'lanadi; Menejerlarni ham ulash mumkin (huquqlariga qarab, M13).

**US-M18-02**: Egasi sifatida har kuni kechqurun qisqa hisobot olishni istayman.
- Given kun yopildi (yoki belgilangan soat keldi), Then bot yuboradi: bugungi savdo, sof foyda (M15 hisobga olingan), naqd (M16), yangi va qaytgan qarzlar, ertaga to'lashi kerak bo'lgan qarzdorlar (M08).

**US-M18-03**: Egasi sifatida muhim hodisalar haqida darhol xabar olishni istayman.
- Ogohlantirishlar (har birini yoqish/o'chirish mumkin): kam qolgan tovar (M04), smena kassa farqi (M16), limitdan katta qaytarish/chegirma (M02/M03), davlat hisobotidagi farq va **5 ish kunlik** muddat (M10), offline kassa 40 soat (qizil) va 48 soatlik fiskal blok (M01, qaror #43), obuna to'lovi: muddatdan 3 kun va 1 kun oldin, to'lov kuni, muddat o'tganda va 24 soatlik imtiyozning 12 va 2 soati qolganda (M17, US-M17-03).

**US-M18-04**: Egasi sifatida botdan oddiy savol so'rashni istayman.
- Given bot ulangan, When Egasi "Bugun qancha sotdik?" deb yozadi, Then javob AI-01 orqali beriladi (raqamni kod hisoblaydi) va tarifning AI oylik limitidan hisoblanadi.

### Davlat tizimlari bog'liqligi
Yo'q.

### Offline xatti-harakati
Server tomonida ishlaydi; kassa offline bo'lsa, ma'lumotlar sinxronlangach xabarlar yangilanadi.

### Chekka holatlar
- Ulanmagan chatga hech qanday ma'lumot yuborilmaydi; xodim o'chirilsa, uning Telegram ulanishi ham bekor qilinadi.
- Mijozlarga qarz xabarlari (US-M08-08) alohida bot/kanal orqali — Egasi boti bilan aralashtirilmaydi.

---

## M19 — 1C integratsiyasi (MVP'dan keyin, Bosqich 7)

**Maqsad**: ERP'dagi kunlik sotuv va boshqa birlamchi hujjatlarni do'konning o'z kompyuteridagi 1C bazasiga («Бухгалтерия для Узбекистана 3.0», 3.0.64+) Windows agenti va COM orqali, ketma-ket, takrorsiz va tekshirilgan holda yozish — buxgalter va Egasi natijani 1C'da ko'radi (qaror #36–#42). Yo'nalish — **ERP → 1C bir tomonlama**; ERP yadrosi 1C'siz ishlaydi. Yagona manba — `33-1c-integratsiya.md` (jadval, endpoint W-xx, ruxsat va xato kodi nomlari shu yerdan o'zgarishsiz olinadi). Bosqich — MVP'dan keyin, **Bosqich 7** (`27-backlog.md`); tarif — 99 000 so'm ichida (qaror #41). Jarayon — BP-14; ekranlar — BO-22, BO-23, BO-14 «1C» qatori, hujjat ekranlarida «1C da» belgisi.

### Foydalanuvchi hikoyalari

**US-M19-01**: Egasi sifatida do'kon kompyuterini (1C o'rnatilgan) ERP'ga xavfsiz ulashni istayman.
- Given agent o'rnatilgan va oynada `WDJB-MJHT` kodi ko'rinadi, When Egasi BO-22 da kodni kiritadi, Then kompyuter nomi, IP va OS ko'rsatiladi va faqat «Ulash» bosilgandan keyin `onec_agents` + `devices(kind='onec_agent')` yaratiladi, Telegram «DOKON-PC ulandi» keladi.
- Given kod 10 daqiqadan eski, When kiritiladi, Then `ONEC_PAIRING_CODE_INVALID`/`EXPIRED` va agentda «Yangi kod» taklifi.
- Given Menejer (`onec.settings.manage` yo'q), When ulashga urinadi, Then `PERMISSION_DENIED`.
- Agentda refresh token yo'q; har 10 daqiqada `private_key_jwt` bilan token oladi; 1C paroli serverga hech qachon yuborilmaydi (server loglari va DB'da yo'qligi testda tekshiriladi).

**US-M19-02**: Egasi sifatida ulangan 1C bazasi ishlashga yaroqliligini bir ekranda ko'rishni istayman.
- Given agent bazani qo'shdi (A-02), Then `33` §2.3 tekshiruvlari avtomatik ishga tushadi va BO-22 «Tekshiruv» yorlig'ida har biri ✓/⚠/✗ + o'zbekcha sabab + tuzatish tugmasi bilan ko'rinadi.
- Given 1C «Базовая» yoki bulut bazasi yoki sotish narxida hisob, Then aniq «qamrovdan tashqari» matni (`ONEC_EDITION_NO_COM` / `ONEC_CLOUD_BASE_UNSUPPORTED` / `ONEC_SALE_PRICE_ACCOUNTING_UNSUPPORTED`) va baza `ready` bo'lmaydi.
- Given 1C'da tenant STIR'i bilan tashkilot yo'q, Then `ONEC_ORGANIZATION_NOT_FOUND`, ERP tashkilotni yaratmaydi.
- «1C ga yozishga ruxsat» kaliti standart o'chiq; faqat `ready/error` bazada yoqiladi.

**US-M19-03**: Egasi sifatida qaysi filial qaysi 1C bazasiga, qaysi sanadan va qaysi rejimda ketishini belgilashni istayman.
- Given ikki filial, When biri «Do'kon BP» ga `bound_from=2026-11-01` bilan bog'lanadi, Then faqat shu filialning 01.11 dan keyingi hujjatlari partiyalarga kiradi; bitta filial ikkinchi bazaga bir vaqtda bog'lanmaydi.
- Rejim standart `full`; `sales_only` tanlansa ogohlantirish va qoldiq preflight majburiy.
- `start_date` dan oldingi hujjat hech qachon yuborilmaydi (test: 31.10 dagi sotuv hech bir partiyada yo'q).

**US-M19-04**: Buxgalter sifatida ERP tovarlari, kassalari, to'lov turlari va kontragentlarini 1C'dagilar bilan tez moslashni istayman.
- Given 1C ma'lumotnomalari o'qilgan, When «Avto-moslash», Then MXIK+nom, shtrix-kod, artikul, STIR, aniq nom bo'yicha takliflar «aniq»/«ehtimoliy» guruhlarda chiqadi; hech biri tasdiqlanmaguncha eksportda ishlatilmaydi.
- «Barcha aniq moslarni tasdiqlash» bitta amal; qo'lda tanlash — 1C elementini qidirib (o'chirishga belgilanganlar ko'rsatilmaydi).
- ERP'da tovar nomi keyin o'zgarsa bog'lanish buzilmaydi (GUID bo'yicha); «Yangilash taklifi» ro'yxatida ko'rinadi.
- To'lov turi 1C'da 5710 hisobli bo'lmasa — ogohlantirish (`ONEC_PAYMENT_ACCOUNT_NOT_TRANSIT`).

**US-M19-05**: Buxgalter sifatida 1C'da yo'q tovar/kontragentni faqat o'zim ko'rib tasdiqlagandan keyin yaratilishini istayman.
- Given 3 ta tovar 1C'da topilmadi, When «1C da yaratish» taklifi tuziladi, Then karta qaysi maydonlar bilan yaratilishini ko'rsatadi va `onec.refs.create` tasdig'isiz hech narsa yaratilmaydi.
- Tashkilot, QQS stavkasi, hisoblar uchun «yaratish» tugmasi yo'q (`ONEC_REF_CREATE_FORBIDDEN`).
- Yaratilgan element GUID'i deterministik — tasdiq ikki marta bosilsa ham 1C'da bitta element.
- `ref_create_policy='deny'` da faqat qo'lda moslash.

**US-M19-06**: Buxgalter sifatida kun yopilgach 1C'ga nima yozilishini oldindan ko'rishni istayman.
- Given barcha smenalar yopilgan, When BO-23 da kun ochiladi, Then tayyorlik checklisti, 1C'da paydo bo'ladigan har hujjat (turi, kassa, qatorlar, summa, QQS, yangi/yangilanadi/o'zgarishsiz) va «ERP jami = 1C ga yoziladigan jami» ko'rinadi.
- Given Android kassa D kunidan keyin sinxronlanmagan yoki outbox'ida D kunidan eski voqea bor, Then `ONEC_DEVICES_NOT_SYNCED` bloki (qurilma nomi, oxirgi sinxron); qurilma sinxronlangach preview avtomatik yangilanadi; yoki sabab bilan qo'lda istisno.
- Given 5 ta tovar moslanmagan, Then «1C ga yuborish» o'chiq, [Moslash] havolasi.

**US-M19-07**: Buxgalter sifatida ko'rgan preview'imni bir tugma bilan 1C ga yuborishni istayman.
- Given preview, When «1C ga yuborish» → tasdiq modali, Then partiya `approved` → navbat sharti bo'lsa `queued`; progress har item bo'yicha (kutilmoqda / yozilmoqda / ✓ № / xato).
- Given tasdiq paytida yangi offline chek keldi, Then `ONEC_PREVIEW_CHANGED` — yangi preview, hech narsa yozilmagan.
- Ogohlantirishlar har biri «Ko'rdim» bilan belgilanmaguncha yuborilmaydi.
- Yakunda 1C'da har hujjat `ERP integratsiya` foydalanuvchisi nomidan, `Комментарий`da `ERP #…` bilan, **o'tkazilgan** holda; Telegram «✅ 4 ta hujjat yozildi».
- Oddiy do'kon (1 kassa, ~300 qator, 3–5 qo'shimcha hujjat) approve → `done` < 3 daqiqa (*taxmin* maqsad, `33` §15.1).

**US-M19-08**: Egasi sifatida «Yuborish» ikki marta bosilsa yoki internet yozish o'rtasida uzilsa ham 1C'da dublikat bo'lmasligini istayman.
- Given partiya `done`, When yangi revision o'zgarishsiz quriladi, Then barcha itemlar `skipped (unchanged)`, 1C'ga hech narsa yozilmaydi.
- Given yozish paytida agent jarayoni o'ldirildi (P-20), When keyingi urinish, Then o'sha GUID topiladi va `existed`/`updated` — 1C'da hujjat soni o'zgarmaydi.
- GUID test vektorlari (`33` §8.1) backend va agentda bir xil natija beradi.

**US-M19-09**: Buxgalter sifatida yozilmagan hujjat sababini tushunarli tilda ko'rib, tuzatib qayta yuborishni istayman.
- Given ОРП `ONEC_NEGATIVE_STOCK`, Then item kartasida 1C'ning asl xabari («Недостаточно…») + o'zbekcha izoh + maslahat; partiya `partial`.
- When kirim 1C'ga kiritilib «Faqat xatolarni qayta yuborish», Then faqat `failed` itemlar qayta yuboriladi, GUID o'zgarmaydi.
- «O'tkazib yuborish» — sabab majburiy, audit; bog'liq to'lov hujjatlari ham o'tkaziladi.

**US-M19-10**: Buxgalter sifatida 1C'ga yozilgan jamlar ERP bilan mos ekanini avtomatik tekshirilishini istayman.
- Given barcha itemlar yozildi, Then `read_totals` bilan har hujjat summasi, QQS, qatorlar soni, o'tkazilganligi solishtiriladi (chegara 0.00); farq bo'lsa `mismatch` + farq jadvali + Telegram.
- `partial`/`mismatch` sabab bilan «Qabul qilish»dan keyin keyingi kunlar navbatga chiqadi; qabul qilinmaguncha chiqmaydi.

**US-M19-11**: Egasi sifatida offline kassaning kech kelgan cheki allaqachon yuborilgan kunni to'g'ri yangilashini istayman.
- Given 15.10 `done`, When 16.10 da 15.10 sanali offline chek sinxronlanadi, Then 15.10 partiyasi `needs_resync`, avtomatik rejimda revision 2 quriladi va **o'sha** ОРП (o'sha GUID) yangilanib qayta o'tkaziladi; boshqa hujjatlar `unchanged`.
- Qo'lda rejimda Telegram «kech chek — revision kerak» va BO-23 banneri.

**US-M19-12**: Buxgalter sifatida 1C'da yopilgan oyga ERP ma'lumoti jimgina yozilmasligini va tuzatish faqat mening qarorim bilan bo'lishini istayman.
- Given 1C'da 30.09 gacha taqiq, When 29.09 revisioni yuboriladi, Then `ONEC_DATE_PROHIBITED`, hech narsa yozilmaydi, sana avtomatik almashtirilmaydi.
- When «Tuzatuvchi hujjat» (sana bugun, sabab), Then 1C'da faqat **farq** bilan ОРП bugungi sanada, `Комментарий` da «29.09 kuni uchun tuzatish».

**US-M19-13**: Egasi sifatida kunlar avtomatik tayyorlanishini va ogohlantirishsiz kun o'zim ruxsat bergan bo'lsa avtomatik yuborilishini istayman.
- `on_shift_close`: oxirgi smena yopilgach kun tayyorlanadi; `at_time 23:30`: o'sha soatda bugun va qolib ketgan kunlar.
- `auto_approve` faqat Egasi yoqadi (`OWNER_ONLY`), faqat `blocking_issues` va `warnings` bo'sh partiyaga ishlaydi; `approved_by` = yoqqan Egasi, audit `onec.export.auto_approved`.
- Standart — `manual`, `auto_approve=false`.

**US-M19-14**: Egasi/Buxgalter sifatida 1C eksporti natijasi va muammolari haqida Telegram'da xabar olishni istayman.
- `33` §13.3 shablonlari; botda tasdiqlash tugmasi yo'q, faqat BO-23 havolasi; `notification_settings` (`onec_export_result`, `onec_problems`) bilan o'chiriladi.

**US-M19-15**: Egasi sifatida kompyuter bir necha kun o'chiq bo'lsa ham hech narsa yo'qolmasligini istayman.
- Given kompyuter 7 kun o'chiq, tasdiqlangan 7 partiya `approved`, When kompyuter yoqiladi, Then partiyalar **sana tartibida** birma-bir yuboriladi; D+1 D yakunlanmaguncha boshlanmaydi.
- 2 soat jimlikdan keyin Telegram `onec_agent_offline`, keyin kuniga bir marta.

**US-M19-16**: Buxgalter sifatida ERP'da bekor qilingan hujjat 1C'da ham to'g'ri aks etishini istayman.
- Given 1C'ga yozilgan kirim ERP'da bekor qilindi, When revision, Then preview'da «1C'da o'tkazishdan chiqariladi va o'chirishga belgilanadi» (`ONEC_UNPOST_REQUIRED`), tasdiqdan keyin `ОтменаПроведения` + `ПометкаУдаления`; jismoniy o'chirish yo'q.

**US-M19-17**: Egasi sifatida 1C kompyuteri almashtirilganda tarix va moslashtirish yo'qolmasligini istayman.
- Given eski agent uzilgan, When yangi PK'da agent o'sha bazani qo'shadi, Then `ONEC_BASE_DUPLICATE` → «Bu kompyuterga o'tkazish» — moslashtirishlar, GUID nomlar fazosi, `onec_object_refs` saqlanadi; keyingi yuborishlar dublikat yaratmaydi.
- Uzilgan agentning tokeni ≤ 60 s ichida rad etiladi.

**US-M19-18**: Buxgalter sifatida ERP yozgan hujjat 1C'da qo'lda o'zgartirilsa yoki o'chirilsa, buni bilishni istayman.
- Kunlik drift tekshiruvi: 1C'da o'zgartirilgan/o'chirishga belgilangan/o'tkazishdan chiqarilgan/yo'qolgan ERP hujjatlari ro'yxati (BO-22 jurnali, Telegram); ERP ularni avtomatik «tuzatmaydi»; keyingi revisionda o'zgartirilgan hujjat ustiga yozilmaydi (`ONEC_CHANGED_IN_1C`), faqat «ERP bilan almashtirish» qarori bilan.

### Davlat tizimlari bog'liqligi
Yo'q — 1C mijozning o'z buxgalteriya dasturi. Provodka, QQS registri, tannarx, fiskal cheklar, Z-hisobot, markirovka kodlari, e-faktura obyektlari 1C ga **yuborilmaydi** (qaror #39, `33` §6.12) — 1C hujjatni o'zi o'tkazadi; 1C ishlatadigan tenant uchun buxgalteriya haqiqat manbai — 1C.

### Offline xatti-harakati
Server va agent tomonida ishlaydi; agent faqat chiquvchi HTTPS bilan vazifa tortadi (pull). Kompyuter o'chiq bo'lsa tasdiqlangan partiyalar `approved` holatida navbatda kutadi (muddat yo'q) va qaytganda sana tartibida yuboriladi (US-M19-15). Kun eksporti filialning POS qurilmalari kun yopilgandan keyin sinxronlanmaguncha bloklanadi (`ONEC_DEVICES_NOT_SYNCED`, `16-offline-sync.md` §9); kech kelgan offline chek — yangi revision (US-M19-11).

### Chekka holatlar
- Qamrovdan tashqari (qaror #41, `33` §2.2): 1C «Базовая» (COM yo'q), bulutdagi 1C (1С:Фреш, ijara), tovarni sotish narxida hisoblaydigan baza (2920/2980), БП UZ 1.5/2.0 va o'zi yozilgan konfiguratsiyalar; УТ UZ 11 / Розница UZ 3.0 — keyingi bosqich. Onboarding tekshiruvi buni aniq aytadi.
- 1C ichiga `.epf`/kengaytma, HTTP-servis yoki OData o'rnatilmaydi (qaror #36, #41).
- Bir filial bir vaqtda faqat bitta 1C bazasiga yoziladi; ikki bazaga parallel yozish taqiqlangan.
- Bank tushumi tasdig'i (`bank_settlement`, US-M11-04) va bank orqali to'lovlar standart **yuborilmaydi** (`send_bank_settlements`, `send_bank_payments` — o'chiq): buxgalter odatda bank ko'chirmasini 1C'ga bank-klientdan import qiladi, ikkalasi birga yoqilsa dublikat.
- Narx o'zgarishi, qarzni kechish, boshlang'ich qoldiqlar — Bosqich 7 da 1C ga yuborilmaydi (keyingi bosqich).
- 1C'da sana taqiqlangan davr — avtomatik sana almashtirish yo'q, faqat buxgalter qarori bilan tuzatuvchi hujjat (US-M19-12).

---

## Ochiq savollar

- **11.** Tashqi javob kerak: CRPT xTrace API — sotuvdan oldingi onlayn tekshiruv majburiyligi, kirim/hisobdan chiqarish metodlari, SaaS integratorga har tenant uchun API kalit — interim: `MARKING_PRECHECK=warn`, `FakeMarkingAdapter` — 26 #40 (OQ-025).
- **13.** Tashqi javob kerak: do'kon savdosida faqat elektron chek (qog'ozsiz) ruxsati — interim: standart bosma, elektron — zahira (US-M01-01) — 26 #112 (OQ-018).
- **14.** Tashqi javob kerak: nasiya sotuvida "kredit" turidagi chek majburiymi va OFD chek turi kodi — interim: `FiscalPolicy.credit_sale_receipt='none'` — 26 #9 (OQ-002).
- **15.** Tashqi javob kerak: fiskal hamkor protokoli (bulut rejimi yoki lokal ko'prik, autentifikatsiya, test FM) — interim: `ERP_FISCAL_PROVIDER=fake`, real adapter Bosqich 5 — 26 #109 (OQ-012).
- **16.** Tashqi javob kerak: dinamik UzQR POS API texnik spetsifikatsiyasi (CBU/MUNIS yoki ekvayer bank) — interim: `UzqrPort` stub, statik QR qo'lda tasdiq bilan — 26 #49 (OQ-032).
- **17.** Tashqi javob kerak: oferta (foydalanish shartlari) va chegaradan tashqari uzatish roziligi yakuniy matni — interim: `terms_versions`, `ai_cross_border_enabled=false` — 26 #127 (OQ-042).
- **18.** Tashqi javob kerak: Faktura.uz API xavf darajasini (VM 830) qaytaradimi — interim: `risk_flag='unknown'`, qizil kabi, Buxgalter qo'lda belgilaydi — 26 #47 (OQ-019).
- **21.** Tashqi javob kerak: chek printerlari transport matritsasi sinovi (Xprinter USB/LAN/BT × Web Serial/WebUSB/raster) — interim: US-M01-07 avto-aniqlash, elektron chek zahira — 26 #139 (OQ-060).
- **22.** Tashqi javob kerak: real karta terminali vendor protokoli va shartnomasi (Rahmat/Humo Sunmi P3, ERA PAX A930, Humo Ingenico Lane/3600) — interim: `FakeCardTerminalAdapter`, terminalsiz karta (rekvizitsiz) zaxira (US-M01-08) — 26 #172–#174; karta turi BIN ro'yxati — 26 #176; mustaqil terminal har do'kon uchun ruxsatmi (VMQ-943 1-ilova 6-band 2-xatboshi) — 26 #177; terminalsiz karta chekida karta turi/niqobi/RRN yo'qligi yetarlimi (VMQ-943 1-ilova 7-band, ijtimoiy kartalar) — 26 #178.

## Manbalar

- `01-qarorlar.md` — asosiy qarorlar
- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md`
- `research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`
- `research_notes/texnik/02-kassa-ofd-markirovka.md`
- `research_notes/texnik/03-efaktura-va-tolov.md`
- `research_notes/texnik/08-mahsulot-modullari.md`
- `research_notes/texnik/09-soliq-integratsiyasi.md`
- `research_notes/texnik/11-raqobatchilar-kamchiliklari.md`
- `spec/kod-uchun/02-rollar-va-ssenariylar.md` (huquqlar matritsasi uchun o'zaro havola)
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — autentifikatsiya arxitekturasi (qaror #14)
- `spec/kod-uchun/33-1c-integratsiya.md` — M19 yagona manbasi (§14 hikoyalar, qaror #36–#42)
- `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` — 15 ta tasdiqlangan tavsiya (qaror #23)
