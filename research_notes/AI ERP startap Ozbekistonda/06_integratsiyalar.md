# Majburiy integratsiyalar: Tadqiqot qaydlari (2026-10-10)

## Online/Virtual Kassa (OFD) — Onlayn NKM

- Muhim qonun: Soliq qo'mitasi Rezolyutsiyasi No. 522 (2019-06-25), qo'shimchasi VMQ-943
- Sertifikatsiya: soliq.uz/page/virtual-kassa-reestri da ro'yxat; E-POS, SOFT TECH SOLUTIONS, mDokon kabi dasturlar sertifikatlangan
- OFD operatorlari: UZKASSA, e-POS, QPos (Paloma365 bilan ishlaydi); Soliq.uz OFD hammaga ochiq
- Chek formati: Real vaqtda OFD'ga yuboriladi, QR-kod bilan; 2026-01-01 dan QR majburiy
- MXIK/IKPU kodlar: tasnif.soliq.uz-dagi 17-raqamli kodlar; POS'da majburiy; vaqti o'tgan tovar 2026-03-01 dan bloklangan
- Xarchlar: Sertifikatsiya xaraji hujjatlangan emas ⚠; OFD dalolatlar serverlarini o'zlari ishlab chiqaradi
- 2026-04-01 dan: Ilojlari cheklangan tovar (farmonlar, buyumlar, receptdan vositalar) majburiy qilindi

## E-invoicing (Elektron Hisob-faktura)

- Qonun: Qonun No. ZRU-1108 (2025-12-25), VMQ-168 (2025-03-18); majburiy 2020-01-01 dan VAT ro'yxatida olinganlar uchun
- Operatorlari: ~15 ta rasm ⚠, eng bosh: Didox (250 000 kompaniya), Faktura.uz; SoliqOnline
- API: Faktura.uz MCP serveri bor, Didox TypeScript SDK; REGOS, Smartup, MoySklad bilan integratsiyalangan
- E-signature (ERI): EIDSS (Elektronik Raqamli Imzo / EDS) Soliq qo'mitasidan; SoliqOnline-ga registratsiya majburiy
- AI xavf baholashi: 2025-12-22 dan pilot, 2026-01-01 dan to'liq; past/o'rta/yuqori risk; yuqori risk QQS kreditini kechiktiradi
- Invoice+waybill (e-TTN): Rezolyutsiya No. 168 (2025-03-18); bitta elektron hujjat
- Komma: JSON struktura; tasnif.soliq.uz va OFD operatorlar qo'shimchasi

## Asl Belgisi (Mahsulot Markirovkasi)

- Operator: CRPT Turon (crpt-turon.uz), API yo'q ⚠
- Tovarlar: Spirtli va tabak, piva, uy-joy texnikasi, dori va tibbiy qurilmalar, suv va salqin ichimliklar
- Deadline: 2026-03-01 dan o'tgan tovar bloklangan; 2026-07-01 dan chek-turida majburiy; vegetable oil (2026-10-24 dan maslahat)
- POS integratsiyasi: "Mahsulot qo'shish" paytida tekshirish; chekda markirovka kodi majburiy
- Qo'shimchalar: ERI bilan olib o'tish yo'q; soddagina API yo'q, qo'lda qidirish tasnif.soliq.uz-da

## Soliq va Hojxojaliq Hisobi

- my.soliq.uz: Avtomatik hisoblar 2026-01-01 dan (5 ish kunida to'g'rilash ruxsat); tanlangan 3-taraf REGOS, Smartup, Didox, Global Pay qo'llab-quvvatlangan
- Soliq-servis API: OFD yordami; har bir chek tasnif kodiga 0,25-0,5% xariji ⚠
- my.mehnat.uz: Ish qo'zligi elektron ro'yxat, oyiga 5 ish kunida; 2026-01-01 dan majburiy
- Vergilash stavkalari 2026: Korporativ 15%, shaxsi 12%, EPI 8%, QQS 15%

## To'lovlar (Korporativ)

- Click: REST API, 1–2% narxi (kontrakt asosida), 3–5 ish kun tasdiq
- Payme: ~1–1,5% narxi; widget API
- Uzum Bank: ~0,8–1,5% narxi; QR, halaллар, obunalar
- Paynet: Aniq ma'lumot yo'q ⚠
- Humo/Uzcard: OPAKET (Uzbek xalqaro to'lov tarmog'i); Click/Payme/Uzum bilan integratsiya
- Nasiya: Uzum Nasiya (QRR), Alif (SME bank tayyorlanmoqda); Payme uyallari bor

## Bank API (Open Banking)

- CBU: cbu.uz/services/open_data — ma'lumotlar portal CSV/JSON; ikkinchi darajali API yo'q ⚠
- TBC Bank: Capital Banking Solutions (CBS) API bilan 2026-yilda avvalgi
- Agregatorlar: Plaid, Tink, TrueLayer, Salt Edge orqali; to'g'ridan-to'g'ri Bank API cheklangan

## Bozorlar / Yetkazib Berish API

- Uzum Market: API dokumentlar topilmadi ⚠; 15 mln oylik tashrif; Didox, MoySklad bilan integratsiya
- Uzum Tezkor: Yetkazib berish; API dokumentar yo'q ⚠
- Yandex Eats: Rossiya/Qozog'iston/Armyaniya/Gruziya/O'zbekiston; API cheklangan ⚠
- Express24: API dokumentar yo'q ⚠

## Shaxsi Ma'lumot Lokalizatsiyasi

- Qonun: No. O'RQ-547 (2019-07-02); Amendent 2026-03-27
- Talab: Biometrik va genetik ma'lumot, telecom foydalanuvchilari ma'lumoti Uzbekistanda qoladi; boshqa: shartnomali (Standard Contract Clauses) yoki Binding Corporate Rules bilan chet elda
- Tamon: Cloud SaaS (AWS, Azure, GCP) — biometrik emas bo'lsa yaxshi; LLM API — o'zbek tarjimalari, o'zbekistanda serverlar yo'q

## IT Park Davlat Residentligi

- Manfaat: 2028-01-01 gacha barcha soliqdan muft; 2028-2040 50%+ eksport — vergi (QQS tashqari) muft
- PIT: 7,5%; oyiga 1% (standart) yoki 2-3% (past eksport); eksport shartli 20% (2027: 35%)
- Qo'llanish: 2026-04-01 dan to'lov, bozor, mikrofinans yo'q; "Digital Startups" statusi doimiy 1%
- Jurnal: Amaliy buxgalteriya, yillik audit, tasdiqlanmagan biznes-plan

---

## Manba joyi

- soliq.uz — Virtual kassa, OFD, Asl Belgisi
- didox.uz, faktura.uz — E-invoicing operatorlari
- tasnif.soliq.uz — MXIK kodlar
- my.soliq.uz, my.mehnat.uz — Davlat platformalari
- cbu.uz — CBU open data portal
- it-park.uz — IT Park foydalari
- VATupdate, Dentons, ey.com — Qonun sharhi
- [raos.uz](https://raos.uz/blog/ozbekistonda-pos-tizimlari-royxati), [paloma365.uz](https://paloma365.uz/blog/guides/onlajn-kassa-uzbekistan), [moysklad.uz](https://www.moysklad.uz/poleznoe/shkola-torgovli/programmy-dlya-roznichnogo-magazina-v-uzbekistane/) — POS sharhlari
