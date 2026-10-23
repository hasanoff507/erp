# Majburiy integratsiyalar: Tadqiqot qaydlari (2026-10-10)

## Online/Virtual Kassa (OFD) — Onlayn NKM

- Muhim qonun: **VMQ-943 (2019-11-23)** — onlayn/virtual kassaning asosiy huquqiy asosi *(2026-10-14 tekshiruvida tuzatildi: avval "Soliq qo'mitasi Rezolyutsiyasi No. 522 (2019-06-25)" asosiy qonun sifatida ko'rsatilgan edi — 522-son qaror aslida elektron hisob-fakturaga oid, onlayn kassaga aloqasi yo'q)*
- Sertifikatsiya: soliq.uz/page/virtual-kassa-reestri da ro'yxat; E-POS, SOFT TECH SOLUTIONS, mDokon kabi dasturlar sertifikatlangan
- OFD operatorlari: UZKASSA, e-POS, QPos (Paloma365 bilan ishlaydi); Soliq.uz OFD hammaga ochiq
- Chek formati: Real vaqtda OFD'ga yuboriladi, QR-kod bilan; QR majburiyligi — Prezident Farmoni **PF-246 (2025-12-10)** asosida, 2026-01-01 dan *(2026-10-14 tekshiruvida tuzatildi: avval huquqiy manbasiz yozilgan edi)*
- MXIK/IKPU kodlar: tasnif.soliq.uz-dagi 17-raqamli kodlar; POS'da majburiy; vaqti o'tgan tovar 2026-03-01 dan bloklangan
- Xarchlar: Sertifikatsiya xaraji hujjatlangan emas ⚠; OFD dalolatlar serverlarini o'zlari ishlab chiqaradi
- 2026-04-01 dan: Ilojlari cheklangan tovar (farmonlar, buyumlar, receptdan vositalar) majburiy qilindi

## E-invoicing (Elektron Hisob-faktura)

- Qonun: **O'RQ-1108 (2025-12-25)** — bu maxsus e-hisob-faktura qonuni emas, balki "2026-yilga mo'ljallangan soliq-byudjet siyosati asosiy yo'nalishlari" haqidagi keng qonun (lex.uz/docs/-7944527), unda QQS stavkalari ham o'zgargan; VMQ-168 (2025-03-18) — e-hisob-faktura va e-TTN birlashtiruvchi qaror; majburiy 2020-01-01 dan VAT ro'yxatida olinganlar uchun *(2026-10-14 tekshiruvida tuzatildi: avval O'RQ-1108 "e-hisob-faktura qonuni" sifatida noto'g'ri tavsiflangan edi)*
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

- my.soliq.uz / davlat tuzgan hisobotlar: **O'RQ-1108 (2025-12-25, 2026-01-01 dan kuchda)**, Soliq kodeksi **81-moddasi** asosida davlat mol-mulk, yer, JShDS, ijtimoiy soliq, QQS va aylanma solig'i bo'yicha hisobotlarni avtomatik tuzadi (**foyda solig'i bundan mustasno**); soliq to'lovchi farqni **5 kalendar kun ichida** tuzatishi mumkin, aks holda davlat tuzgan hisobot topshirilgan deb hisoblanadi (lex.uz/docs/-7944527); tanlangan 3-taraf REGOS, Smartup, Didox, Global Pay qo'llab-quvvatlangan *(2026-10-14 tekshiruvida tuzatildi: avval "5 ish kunida" va huquqiy asossiz yozilgan edi)*
- Soliq-servis API: OFD yordami; har bir chek tasnif kodiga 0,25-0,5% xariji ⚠
- my.mehnat.uz: Ish qo'zligi elektron ro'yxat, oyiga 5 ish kunida; elektron mehnat daftarchasi 2020-01-01'dan amalda, elektron mehnat shartnomalari VM 891-son qarori (2024-12-27) bilan majburiy qilingan *(2026-10-14 tekshiruvida tuzatildi: avval "2026-01-01 dan majburiy" deb yozilgan edi — bu sana manbasiz edi)*
- Vergilash stavkalari 2026: Korporativ foyda solig'i 15%, JShDS (shaxsiy daromad solig'i) 12%, QQS **12%** *(2026-10-14 tekshiruvida tuzatildi: avval QQS 15% deb yozilgan edi — Soliq kodeksi 258-moddasi, stavka 2023-01-01'dan 12%, 2026-yilda o'zgarishsiz qoladi)*; "EPI 8%" raqami hech qanday manbada tasdiqlanmadi va olib tashlandi (haqiqiy ijtimoiy soliq/yagona ijtimoiy to'lov stavkalari 12% yoki byudjet tashkilotlari uchun 25%)

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

- Qonun: O'RQ-547 (2019-07-02); tuzatish qonuni **O'RQ-1125, 2026-03-26** *(2026-10-14 tekshiruvida tuzatildi: avval "2026-03-27" deb yozilgan edi)*
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
