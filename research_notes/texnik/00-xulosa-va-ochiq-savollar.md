# Yakuniy xulosa va bozor hujjatidagi ochiq savollarga javoblar

*Tadqiqotchi: Fiskal · 2026-10-12*

## Asosiy xulosalar

1. **Yo'nalish o'zgardi (foydalanuvchidan, 2026-10-12):** mahsulot 1C'dan ma'lumot OLMAYDI va 1C bilan integratsiya qilmaydi — noldan quriladi; 1C faqat ma'lumotlar modeli uchun namuna ([Claude Docs asosiy hujjat](https://claude.ai/code/artifact/e57e7cd7-1117-40a7-8af5-8154a8d22540)). Asosiy qiymat taklifi — kassadan buxgalteriya va soliq hisobotigacha **bitta tizim**.
2. **MVP 14 modul**: kassa, qaytarish, chegirma, ombor qoldig'i, inventarizatsiya, ko'chirish, xarid, nasiya, narxlar, QQS, buxgalteriya, hisobotlar, huquqlar, filiallar. Kadrlar/ish haqi, CRM/sodiqlik va ishlab chiqarish — keyingi bosqich.
3. **8 ta majburiy davlat tizimi**: virtual kassa/OFD, e-faktura, e-TTN, Asl belgisi markirovkasi, MXIK, e-ishonchnoma, E-IMZO, soliq hisobotlari (my.soliq.uz). Faqat Faktura.uz, MXIK va to'lov tizimlarining ochiq hujjati bor — Soliq qo'mitasining o'z ochiq dasturchi API portali topilmadi, ulanish asosan vositachilar (OFD, EDO operatorlari, CRPT Turon) orqali.
4. **Ikkita oldin "tasdiqlanmagan" belgilangan da'vo endi birlamchi manbadan tasdiqlandi** (bu sessiyada tekshirildi): E-IMZO'ning asosiy qonuni — **O'RQ-793-son (2022-10-12) "Elektron raqamli imzo to'g'risida"**, 2023-01-14 dan kuchda ([lex.uz/docs/-6234904](https://lex.uz/docs/-6234904)); QR to'lov majburiyligi — Prezident Farmoni (2025-12-10, "Naqdsiz hisob-kitoblarni ommalashtirish..."); farmon raqami manbada yo'q. CBU Qarori №3817 (2026-04-15) faqat yagona QR to'lov xizmati qoidalarini belgilaydi, majburiylikni o'zi joriy etmaydi. Talab 2026-01-01 dan boshlanadi, **2026-07-01 dan to'liq majburiy** ([gazeta.uz, 2025-12-10](https://www.gazeta.uz/oz/2025/12/10/qr-code/); [lex.uz/docs/8139307](https://lex.uz/docs/8139307)). "48 soat offline" qoidasi ham ilgari tasdiqlangan (943-son qaror, 1-ilova, 31-band — `02-fayl`).
5. **2026-yildagi eng katta arxitektura o'zgarishi**: Soliq qo'mitasi 2026-01-01 dan QQS va boshqa hisobotlarni cheklar/e-fakturalardan **o'zi tuzadi**, korxonaga 5 ish kuni tekshirish beriladi. Mahsulotning markaziy qiymati — deklaratsiya yozish emas, **davlat hisobotini ichki hisob bilan solishtirish** (`04-fayl`, 6-bo'lim).
6. **Eng katta amaliy xavf mahsulotlarda emas — soliq tizimining o'zida**: Asl belgisi markirovkasida yuklarning 80–90%i skanerlash xatosi bilan qaytadi, jarima choraklik aylanmaning 20%igacha ([gazeta.uz, 2026-04-14](https://www.gazeta.uz/oz/2026/04/14/marking/); [gazeta.uz, 2026-03-31](https://www.gazeta.uz/oz/2026/03/31/marking-fine/)).
7. Bozor hujjatidagi ochiq savollarning katta qismi (01–07 fayllar orqali) javob topdi; eng muhim ikkitasi hamon **ochiq**: virtual kassa reyestriga kiritish narxi/muddati, va Asl belgisi integrator API hujjatlari (403 bilan yopiq).
8. Raqobatchilar tahlilidagi raqamli ziddiyatlar (mijozlar soni, investitsiya) ko'pchiligi hal qilinmadi — bular mustaqil tasdiqlab bo'lmaydigan marketing da'volari, suhbat/so'rov orqali aniqlanishi kerak.

---

## 1. Bozor hujjatidagi ochiq savollarga javoblar

*Manba: `research_notes/AI ERP startap Ozbekistonda/00_oldingi_hujjat.md` ("Tekshirilmagan ma'lumotlar" bo'limi) va Claude Docs asosiy hujjati (e57e7cd7) + texnik fayllar 01–07.*

| # | Savol / ziddiyat | Javob / holat | Manba |
|---|---|---|---|
| 1 | 1C foydalanuvchilari soni (O'zbekistonda) | **Topilmadi.** Ochiq manbalarda umuman yo'q — 01-faylda ham qayta qidirilib topilmadi. **Kim bilan bog'lanish**: mahalliy 1C franchayzilari (~30 ta, masalan Business Automatization, 1C:Birinchi Bit, FINSOFT). | `01-fayl`, oldingi tadqiqot |
| 2 | Virtual kassa reyestriga kiritish narxi va muddati | **Qisman javob topildi, aniq narx/muddat hamon yo'q.** Jarayon va 10 ta hujjat aniqlandi; tadbirkorning qurilma ro'yxatiga olish muddati (4+8 ish soati) bilan dastur sertifikatlash muddatini farqlash kerak — ikkinchisi qonun matnida yo'q. **Kim bilan bog'lanish**: Soliq qo'mitasi / "Yangi texnologiyalar" DUK. | `02-fayl` |
| 3 | Asl belgisi (CRPT Turon) ochiq API | **Hamon yopiq.** help.crpt-turon.uz asosiy bo'limlari 403 xatosi bilan yopiq; integrator ro'yxatdan o'tish shartlari aniqlanmadi. **Kim bilan bog'lanish**: CRPT Turon (crpt-turon.uz) rasmiy murojaat. | `02-fayl`, `04-fayl` |
| 4 | BILLZ mijozlar soni (4 000+ vs 1 700+) | **Hal qilinmadi.** 06-faylda narx (299k/499k/999k, 2026) rasmiy sahifadan tasdiqlandi, lekin mijozlar sonini mustaqil tasdiqlovchi manba topilmadi. | `06-fayl` |
| 5 | OX System mijozlar soni (350+ vs 2 000+) | **Hal qilinmadi** — bu sessiyada qayta tekshirilmadi (vaqt yetishmadi, `06-fayl`da aniq qayd etilgan). | `06-fayl` |
| 6 | Bito ERP mijozlar soni (600+ vs 2 000+) | **Hal qilinmadi, ziddiyat kengaydi** — Bito'ning o'z sayti endi "1000+ клиентов" deydi, ya'ni uchinchi raqam qo'shildi. | `06-fayl` |
| 7 | HIPPO "bepul tarif" reklamasi vs sayt pullik | **Hal qilindi** — HIPPO'ning barcha 3 tarifi pullik (247,2k–618k so'm/oy), bepul tarif umuman yo'q; eski "bepul tarif" da'vosi noto'g'ri chiqdi. | `06-fayl` |
| 8 | Smartup investitsiya holati (moliyalashtirilmagan vs 2025 seed) | **Hal qilinmadi** — qayta tekshirilmadi. | oldingi tadqiqot |
| 9 | Sellerpeak24 — faol/yopiq | **Hal qilinmadi.** | oldingi tadqiqot |
| 10 | Paloma365 — mahalliy/Qozog'iston kelib chiqishi | **Hal qilinmadi.** | oldingi tadqiqot |
| 11 | MDokon "aqlli kamera" funksiyasi | **Ehtimol noto'g'ri, lekin aniq rad etilmadi** — 06-faylda MDokon qayta tekshirilganda sayt kassa/ombor/analitika/fiskal/to'lovlarni sanaydi, kamera haqida hech narsa yo'q. | `06-fayl` |
| 12 | Didox "250 000 kompaniya" da'vosi | **Hal qilinmadi** — 03-faylda qayta tekshirilmadi, tekshirilmagan qidiruv parchasi sifatida qoldi. | `03-fayl`, oldingi tadqiqot |
| 13 | 1C hamkorlari (franchayzilar) joriy etishlar soni | **Hal qilinmadi** — ochilmagan katalog parchasi. | oldingi tadqiqot |
| 14 | E-IMZO qonuni raqami (yangi hujjatda "tasdiqlanmagan") | **✅ Hal qilindi** — O'RQ-793-son (2022-10-12), kuchga kirgan 2023-01-14. | [lex.uz/docs/-6234904](https://lex.uz/docs/-6234904) |
| 15 | QR to'lov majburiyligi (yangi hujjatda "tasdiqlanmagan") | **✅ Hal qilindi** — 2026-01-01 dan boshlanadi, 2026-07-01 dan majburiy (Prezident Farmoni, 2025-12-10; raqami manbada yo'q). CBU 3817-son (2026-04-15) faqat xizmat qoidalari. | [gazeta.uz](https://www.gazeta.uz/oz/2025/12/10/qr-code/), [lex.uz/docs/8139307](https://lex.uz/docs/8139307) |
| 16 | 48 soat offline qoidasi (yangi hujjatda "tasdiqlanmagan" deb yozilgan edi) | **✅ Allaqachon hal qilingan edi** (2026-10-12dagi 02-fayl tuzatishida) — 943-son qaror, 1-ilova, 31-band. | `02-fayl`, [lex.uz/docs/4603329](https://lex.uz/docs/4603329) |

**Umumiy naqsh**: davlat tizimlari (OFD, E-IMZO, Asl belgisi, soliq hisobotlari) bo'yicha savollarning aksariyati lex.uz/soliq.uz orqali hal qilinadi — bular topildi. Raqobatchilarning o'z marketing da'volari (mijozlar soni, investitsiya) esa mustaqil tekshirib bo'lmaydigan toifaga kiradi — bular do'kon egalari/raqobatchi mijozlari bilan to'g'ridan-to'g'ri suhbat orqali aniqlanishi kerak, bu `06-fayl`da ham alohida qayd etilgan.

### 1.1 Bozor hujjatining "Xavflar va ochiq savollar" bo'limidagi, FAQAT suhbat/bozor tadqiqoti orqali javob topiladigan savollar

Bular texnik tadqiqot (01–07 fayllar) bilan javob berib bo'lmaydigan, biznes/bozor xarakteridagi savollar — ochiq veb-manbada ham topilmaydi, chunki javob mahalliy do'kon egalari/mijozlar bilan suhbatda yotadi:

1. O'zbekistonda nechta korxona litsenziyali yoki pirat 1C ishlatadi? — franchayzilardan so'rash kerak.
2. Kichik do'konlar oyiga qancha to'lashga tayyor? — 20–30 ta do'kon egasi bilan suhbat kerak.
3. Qaysi bank yoki mikromoliya tashkiloti kredit hamkorligiga qiziqadi?
4. Mahalliy SME SaaS'da mijozlarni yo'qotish (churn) darajasi qancha? — ochiq manbada yo'q, pilot mijozlarda o'lchanishi kerak.

### 1.2 Bozor hujjatining biznes-xavf jadvali (qisqartirilgan, mitigatsiya bilan)

| Xavf | Ehtimol/Ta'sir | Mitigatsiya (bozor hujjatidan) |
|---|---|---|
| Buxgalterlar 1C'ni tashlamaydi | Yuqori/Yuqori | Avval POS+ombor bilan kirish; buxgalteriya modulini keyin to'liq qilish. *Eslatma: bozor hujjatidagi "1C'ga eksport" g'oyasi 2026-10-12 yo'nalishiga zid (1C bilan integratsiya yo'q), foydalanuvchi qarori kerak.* |
| Soliq qoidalari tez o'zgaradi (e-faktura, Asl belgisi, AI baholash) | Yuqori/O'rta | Soliq bo'yicha alohida jamoa a'zosi; bulutda yangilanish 1C'dan tezroq |
| Virtual kassa sertifikatlash muddati/narxi noma'lum | O'rta/Yuqori | Birinchi oyning o'zida Soliq qo'mitasi va OFD operatori bilan uchrashuv — bu `02-fayl`dagi ochiq savol bilan bir xil |
| REGOS yoki BILLZ AI'ni tez qo'shadi | O'rta/O'rta | To'liq qamrov (buxgalteriya+ish haqi) va o'zbek tilidagi chuqur AI bilan farqlanish |
| Rossiyalik "1C ustida AI" vendorlari franchayzilar orqali kiradi | O'rta/O'rta | Franchayzilarni dilerga aylantirish |
| LLM xarajati obuna narxidan oshadi | Past/O'rta | Kichik model, kesh, foydalanuvchi boshiga limit |

*To'liq jadval va "⚠" bilan belgilangan boshqa tasdiqlanmagan raqamlar (soha statistikasi, 1C sozlash xarajati, pirat nusxalar, xalqaro AI bank-kategoriyalash aniqligi va h.k.) uchun bozor hujjatining o'ziga qarang — bu yerda faqat texnik tadqiqot bilan kesishgan qismlari keltirildi.*

---

## 2. 01–07 fayllar uchun umumiy xulosa

### MVP uchun eng muhim texnik qarorlar

| Soha | Qaror | Fayl |
|---|---|---|
| 1C'ning roli | Faqat ma'lumotlar modeli namunasi — migratsiya YO'Q, integratsiya YO'Q | `01-fayl` (yangilangan yo'nalish) |
| Buxgalteriya hisob rejasi | Yangi NSBU №21 (2024/2025) asosida, eski 2002-yilgi reja EMAS | `01-fayl` |
| Multi-tenant model | Umumiy baza + `tenant_id` + PostgreSQL RLS | `04-fayl` |
| Offline-first | Majburiy (ixtiyoriy emas); append-only event-log (outbox), CRDT EMAS | `04-fayl` |
| Kassa platformasi | Android-native (Kotlin) — bozor uskunalari asosan Android (PAX A930, UZKASSA) | `02-fayl`, `04-fayl`, `06-fayl` |
| Orqa ofis platformasi | PWA — o'rnatishsiz, markazlashgan yangilanish | `04-fayl` |
| Backend/baza | PostgreSQL, UzCloud DBaaS orqali (managed, HA, PITR) | `04-fayl`, `07-fayl` |
| Hosting | UzCloud/Uztelecom — biznes tanlovi, qonuniy majburiyat EMAS (faqat biometrik/genetik/telekom ma'lumoti lokalizatsiya talab qiladi) | `07-fayl` |
| Fiskal/OFD | Yagona davlat OFD operatori ("Yangi texnologiyalar" DUK); 48 soat offline chegarasi (943-son, 1-ilova, 31-band) | `02-fayl` |
| AI — MVP uchun real | Debitorlik eslatma matni, savol-javob chat ("code computes, AI explains"), toza faktura/chek fotosidan vision-LLM OCR | `05-fayl` |
| AI — hozircha real emas | Qo'lda yozilgan "nasiya daftari" OCR (kirill qo'lyozma uchun ishonchli benchmark yo'q) | `05-fayl` |
| To'lov/e-faktura integratsiyasi | Har biri (Payme/Click/Uzum, Didox/Faktura.uz) uchun alohida adapter — yagona umumiy abstraksiya yo'q | `03-fayl` |
| Soliq bilan integratsiya | 8 ta majburiy tizim; faqat 3 tasida (Faktura.uz, MXIK, to'lovlar) ochiq API hujjati | Claude Docs asosiy hujjat, `02-fayl`, `03-fayl` |
| Yangi markaziy oqim (2026) | Davlat hisobotini (my.soliq.uz) ichki hisob bilan solishtirish motori — rasmiy API yo'qligi sababli MVP'da qo'lda/yarim-avtomatik boshlanadi | `04-fayl`, 6-bo'lim |

### Eng katta 5 texnik xavf (birinchi 90 kun)

1. **Asl belgisi integratsiyasi yopiq** — CRPT Turon integrator API hujjatlari 403 bilan yopiq; markirovkalangan tovar (suv, ichimlik, tamaki) sotuvi birinchi kundanoq bloklanishi xavfi. (`02-fayl`, `04-fayl`)
2. **Davlat hisobotini olish uchun rasmiy API yo'q** — my.soliq.uz'dan dasturiy o'qish yo'li topilmadi; mahsulotning markaziy qiymat taklifi ("solishtirish motori") MVP'da qo'lda boshlanishi kerak, bu avtomatlashtirish va'dasini kechiktiradi. (`04-fayl`)
3. **Virtual kassa reyestriga kiritish narxi/muddati noma'lum** — mustaqil dastur sifatida ro'yxatdan o'tish xarajati loyiha jadvaliga ta'sir qilishi mumkin; muqobil — mavjud reyestr a'zosi (E-POS/UZKASSA) bilan OEM/hamkorlik. (`02-fayl`)
4. **ЗРУ-764 sertifikatlash talabi noaniqligi** — oddiy xususiy SaaS'ning davlat ekspertizasiga tushish-tushmasligi ochiq manbada tasdiqlanmagan; agar "ha" bo'lsa, MVP jadvaliga katta ta'sir. (`07-fayl`)
5. **E-IMZO'ning rasmiy dasturchi hujjati yo'q** — faqat jamoatchilik GitHub repo (`qo0p/e-imzo-doc`); e-faktura/e-TTN/hisobot imzolash integratsiyasi kutilganidan ko'proq vaqt olishi mumkin, rasmiy qo'llab-quvvatlash kanali yo'q. (`03-fayl`)

*Bonus/6-xavf: offline paytda markirovka kodini tekshirish mumkin emas (CRPT Turon markaziy tizimga bog'liq) — internetsiz do'kon markirovkalangan tovar sotishga majbur bo'lsa, huquqiy xavf (jarima aylanmaning 2–20%i) yuzaga keladi; MVP'da aniq siyosat (ruxsat/taqiq) ishlab chiqarishgacha hal qilinishi kerak (`04-fayl`).*

### Fayllarga havolalar
- `research_notes/texnik/01-1c-modullar-va-malumot-modeli.md`
- `research_notes/texnik/02-kassa-ofd-markirovka.md`
- `research_notes/texnik/03-efaktura-va-tolov.md`
- `research_notes/texnik/04-arxitektura-va-stack.md`
- `research_notes/texnik/05-ozbek-tilidagi-ai.md`
- `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`
- `research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md`
- Claude Docs asosiy hujjat: [e57e7cd7-1117-40a7-8af5-8154a8d22540](https://claude.ai/code/artifact/e57e7cd7-1117-40a7-8af5-8154a8d22540) (modullar, 8 soliq tizimi, raqobatchilar jadvali, kamchiliklar, foydalanuvchiga 6 savol)

---

## Ochiq savollar

1. Virtual kassa reyestriga mustaqil dastur sifatida kiritish narxi/muddati — hamon ochiq (`02-fayl`'dan meros).
2. CRPT Turon (Asl belgisi) bilan integrator sifatida ro'yxatdan o'tish shartlari — help.crpt-turon.uz 403 bilan yopiq.
3. 1C foydalanuvchilari soni O'zbekistonda — ochiq manbalarda umuman topilmadi, mahalliy franchayzilarga murojaat kerak.
4. BILLZ, OX System, Bito ERP mijozlar sonidagi ziddiyatlar — marketing da'volari, mustaqil tasdiqlab bo'lmaydi.
5. Didox "250 000 kompaniya" da'vosi — tekshirilmagan qidiruv parchasi, qayta tekshirilmadi.
6. ЗРУ-764 (Kiberxavfsizlik) sertifikatlash talabining oddiy SaaS ERP'ga tegishliligi — csec.uz bilan yozma aniqlashtirish kerak (`07-fayl`'dan meros).
7. Davlat hisobotini (my.soliq.uz) dasturiy o'qish uchun yarim-rasmiy yo'l (masalan E-IMZO orqali) bormi — to'g'ridan-to'g'ri aniqlashtirish kerak (`04-fayl`'dan meros).
8. Mahalliy POS raqobatchilari bo'yicha haqiqiy mijoz shikoyatlari — ochiq manbada deyarli topilmadi (Google Play/forum sharhlari yo'q); 10–15 ta do'kon egasi bilan suhbat tavsiya etiladi (Claude Docs asosiy hujjat, oxirgi bo'lim).
9. Kichik do'konlarning to'lovga tayyorligi (oyiga qancha so'm), bank/mikromoliya hamkorligi qiziqishi, mahalliy SaaS churn darajasi — faqat bozor tadqiqoti/suhbat orqali, veb-qidiruvda topilmaydi (1.1-bo'lim).

## Manbalar

- `research_notes/AI ERP startap Ozbekistonda/00_oldingi_hujjat.md` — bozor tadqiqoti xom qaydlari ("Tekshirilmagan ma'lumotlar" bo'limi)
- Claude Docs asosiy hujjat: [artifact e57e7cd7-1117-40a7-8af5-8154a8d22540](https://claude.ai/code/artifact/e57e7cd7-1117-40a7-8af5-8154a8d22540)
- [lex.uz/docs/-6234904](https://lex.uz/docs/-6234904) — O'RQ-793-son, Elektron raqamli imzo to'g'risida (2022-10-12)
- [gazeta.uz, 2025-12-10 — yagona QR kod majburiyligi](https://www.gazeta.uz/oz/2025/12/10/qr-code/)
- [lex.uz/docs/8139307](https://lex.uz/docs/8139307) — CBU Qarori №3817 (2026-04-15), yagona QR-kod qoidalari
- [gazeta.uz, 2026-04-14 — markirovka skanerlash xatolari](https://www.gazeta.uz/oz/2026/04/14/marking/)
- [gazeta.uz, 2026-03-31 — markirovka jarimalari](https://www.gazeta.uz/oz/2026/03/31/marking-fine/)
- Ichki tadqiqot fayllari: `01` – `07` (yuqorida ro'yxatlangan)
