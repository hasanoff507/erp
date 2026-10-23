# Raqobatchi POS/ERP mahsulotlarining texnik tahlili va kassa uskunalari

*Tadqiqot sanasi: 2026-10-10. Tadqiqotchi: Fiskal (team worker).*

## Asosiy xulosalar

1. Tekshirilgan 9 ta mahsulotning (BILLZ, REGOS, Smartup, MoySklad, HIPPO, Bito ERP, mDokon, iiko, Poster) barchasida kassa+ombor moduli bor; **nasiya/qarz hisobi** alohida pullik yoki alohida modul sifatida faqat BILLZ, Bito ERP, mDokon va Smartupda (debitorlik nazorati) aniq hujjatlashtirilgan — REGOS, MoySklad, HIPPO sahifalarida nasiya moduli alohida tilga olinmagan.
2. **Tasdiqlangan AI funksiyasi** faqat REGOS (AI-yordamchi, Pro tarifida) va Smartup (javondagi tovarni fotodan tanish) sahifalarida topildi; BILLZ, MoySklad, HIPPO, Bito, mDokon rasmiy sahifalarida AI funksiyasi haqida hech qanday da'vo topilmadi.
3. Narx diapazoni: oyiga 69 ming so'mdan (REGOS Start) 999 ming so'mgacha (BILLZ Pro); restoran avtomatlashtirish (iiko) ancha qimmat — 484 ming–1,39 mln so'm/oy (lekin bu raqamlar iiko'ning o'zidan emas, mahalliy dilerlar — kafesoft.uz, soft24.uz, itdo.uz — sahifalaridan, shuning uchun ⚠ bilan belgilangan).
4. Kassa uskunalari (shtrix-kod skaner, chek printeri, tarozi, Android POS terminal) O'zbekiston bozorida keng assortimentda va narxlari manbali topildi (quyida jadval). Ulanish protokollari: chek printerlari uchun **ESC/POS** (Epson de-fakto standarti), skanerlar uchun **USB HID / "keyboard wedge"** eng keng tarqalgan rejim; tarozilar uchun aniq protokol nomi (masalan CAS yoki Shtrix-M) ochiq manbada topilmadi — faqat "Frontol, LiteBox bilan integratsiya" umumiy tarzda aytiladi.
5. Virtual kassa uchun zarur uskuna minimal darajada — internetga ulangan qurilma (smartfon/planshet/PC) + dastur yetarli, chek printeri va fiskal modul alohida uskuna sifatida shart emas (tafsilot 02-faylda; bu yerda takrorlanmadi).
6. **Soliq integratsiyasi tezisi aniqlashtirildi** *(2026-10-14 tekshiruvida qo'shildi)*: "hech bir raqobatchi soliq tizimlari bilan integratsiya qilmagan" tezisi NOTO'G'RI shaklda yozilgan edi. Moysklad.uz o'z saytida E-POS orqali fiskal ro'yxatga olishni ("Регистрация продаж в налоговой Узбекистана через один клик") va AslBelgisi markirovka integratsiyasini aniq reklama qiladi; REGOS ham Didox bilan integratsiyalangan (jadvalga qarang). BILLZ'ning esa o'z sahifasida bunday integratsiya da'volari yo'q. Haqiqiy farqlanish nuqtasi — "integratsiya bor/yo'q" emas, balki: (a) hammasi bitta tizimda birlashganmi (uchinchi tomon kassa/EDO'siz), (b) davlat tuzgan hisobotni ichki hisob bilan avtomatik solishtirish bormi, (c) offline + markirovka qanchalik ishonchli, (d) o'zbek tilida AI bormi. Bu to'rttasi hali hech bir raqobotchida tasdiqlangan holda topilmagan — lekin bu gipoteza, "hech kim" degan universal da'vo emas.

---

## 1) Raqobatchi POS/ERP mahsulotlari — taqqoslash jadvali

| Mahsulot | Modullar | Integratsiyalar | Platforma | Offlayn | Ochiq API | Narx (rasmiy sahifadan) |
|---|---|---|---|---|---|---|
| **BILLZ** ([billz.io/uz](https://billz.io/uz)) | Ombor, kassa/POS, CRM, moliyaviy hisob, nasiya/qarz kuzatuvi, analitika | Payme/Click/Uzum (to'lov); amoCRM/RetailCRM (CRM). ⚠ OFD, e-faktura, Asl belgisi — **manbada topilmadi, tasdiqlanmagan** *(2026-10-14 tekshiruvida tuzatildi: avval "OFD, e-faktura, Payme/Click/Uzum, Asl belgisi" deb yozilgan edi — billz.io/uz/for-developers sahifasida OFD/e-faktura/Asl belgisi haqida hech qanday matn yo'q, faqat amoCRM/RetailCRM integratsiyasi bor)* | Web, Android, Windows | Bor | Bor ([billz.io/uz/for-developers](https://billz.io/uz/for-developers)) | Start 299k, Advanced 499k, Pro 999k so'm/oy ([billz.io/uz/prices](https://billz.io/uz/prices)) |
| **REGOS** ([regos.uz](https://regos.uz/ru/price)) | Kassa, ombor, (Plus/Pro: ishlab chiqarish), hisobot; nasiya alohida tilga olinmagan | Didox, Click, Payme (oldingi tadqiqot, 06_integratsiyalar.md), MCP/webhook (faqat Pro) | Cloud SaaS + EasyTrade desktop | EasyTrade desktop versiyasi (bulutsiz ishlaydi, tabiatan offline) | Pro tarifida MCP-integratsiya | Start 69k, Basic 149k, Plus 299k/oy (yoki 254,6k/oy yillik), Pro 859k/oy (yoki 687,2k/oy yillik); virtual kassa qo'shimchasi +75k/oy; EasyTrade bir martalik 7,2 mln (1 nuqta) / 10,5 mln (tarmoq) ([regos.uz/ru/price](https://regos.uz/ru/price)) |
| **Smartup** ([greenwhite.uz/smartup-en](https://www.greenwhite.uz/smartup-en)) | Savdo/marketing, merchandayzing, moliya (debitorlik nazorati = nasiya o'rnini qisman bosadi), ombor, HR/ish haqi, ishlab chiqarish | ⚠ "SAP, Asl belgisi, Faktura.uz" — eski manba (06_integratsiyalar.md), joriy saytda tasdiqlanmagan; joriy greenwhite.uz/smartup-en sahifasida faqat umumiy "Integrate with any system" bor, aniq nomlar yo'q *(2026-10-14 tekshiruvida qo'shildi)* | Cloud + offlayn rejim qo'llab-quvvatlanadi | Bor | Bor (umumiy, tafsilotsiz) | 120 000 so'm/foydalanuvchi/oy ([greenwhite.uz/smartup-en](https://www.greenwhite.uz/smartup-en)) |
| **MoySklad** ([moysklad.uz](https://www.moysklad.uz/)) | Ombor, POS/kassa (QR-to'lov), CRM, moliya, ishlab chiqarish | E-POS (fiskal — "Регистрация продаж в налоговой Узбекистана через один клик"), Uzum Market, Wildberries, Click, Payme, Anor, Didox, Asl Belgisi ("Интеграция с Национальной системой цифровой маркировки товаров AslBelgisi" — so'zma-so'z sayt matni) | Web, Android/Windows ilovalari | Bor (internet yo'qolganda ishlaydi) | Ochiq JSON API 1.2 (oldingi tadqiqot, 06_integratsiyalar.md) | Bepul tarif: 1 savdo nuqtasi, 5 xodimgacha, muddatsiz *(2026-10-14 tekshiruvida tuzatildi: avval "2 savdo nuqtasi" edi — moysklad.uz/subscription/'da aslida 1 savdo nuqtasi)* ([moysklad.uz](https://www.moysklad.uz/)) |
| **HIPPO** ([hippo.uz/ru/pos](https://hippo.uz/ru/pos/)) | POS/kassa, ombor (cheksiz tovar), CRM/sodiqlik dasturi, hisobot; nasiya moduli bu sahifada ko'rsatilmagan | Virtual kassa reyestrida 2024-yildan; to'lov terminallari, global shtrix-kod bazasi (200 000+ tovar) | Ko'rsatilmagan (umumiy POS, platforma aniq yozilmagan) | Ko'rsatilmagan | Ko'rsatilmagan | Base 247 200, Medium 412 000, Pro 618 000 so'm/oy ([hippo.uz/ru/pos](https://hippo.uz/ru/pos/)) |
| **Bito ERP** ([bito.uz](https://bito.uz/)) | Savdo, CRM, ta'minot zanjiri, HR, logistika, ombor, analitika, moliyaviy hisobot; nasiya/kredit savdosi aniq biznes turi sifatida qo'llab-quvvatlanadi | Click, Payme, Play Mobile, amoCRM, kuryer xizmatlari | Smartfon, kompyuter, planshet | Bor (offlayn/onlayn rejim) | Bor | Bu sahifada ko'rsatilmagan (oldingi tadqiqot, 00_oldingi_hujjat.md: 300 000 so'mdan) |
| **mDokon** ([mdokon.uz](https://mdokon.uz/)) | Kassa (onlayn/offlayn), ombor, analitika, nasiya (qarz hisobi — yuqori tarifda, oldingi tadqiqot) | Click, Payme, Uzum, fiskal/OFD | Ko'rsatilmagan aniq platforma | Bor: "sotuvlar odatdagidek o'tadi, cheklar kassada saqlanadi, internet tiklanishi bilan sinxronlashadi" | Ko'rsatilmagan | 199k–399k so'm/nuqta/oy (3 tarif) ([mdokon.uz](https://mdokon.uz/)) |
| **iiko** (restoran, [kafesoft.uz](https://kafesoft.uz/), [kafesoft.uz/ofd](https://kafesoft.uz/ofd)) | Zal, oshxona, ombor, xodimlar, moliya | IIKOFISCAL virtual kassa — OFD'ga real vaqtda uzatish | Ko'rsatilmagan | Ko'rsatilmagan | Ko'rsatilmagan | ⚠ Dilerlar narxi turlicha: Start 484–500k, Pro 1,01–1,05 mln, Enterprise 1,35–1,39 mln so'm/oy (kafesoft.uz, soft24.uz, itdo.uz — rasmiy iiko.ru narx sahifasi emas, mahalliy integratorlar narxi) |
| **Poster POS** (xorijiy SaaS, [joinposter.com](https://joinposter.com/en/applications)) | Poster o'zi — restoran/chakana POS (asosiy narxi bu tadqiqotda tekshirilmadi — xorijiy, $ da) | O'zbekiston uchun fiskalizatsiya qo'shimcha integratsiya orqali: E-POS Integration, FiscalBox, Rahmat POS (Multikassa) | Ko'rsatilmagan | Ko'rsatilmagan | Ochiq API (POS integratsiyalari uchun) | Fiskalizatsiya qo'shimchasi: E-POS Integration $10/oy, Multikassa integratsiyasi $5/oydan ([joinposter.com knowledge base](https://knowledge-base.joinposter.com/ru/setting-up-fiscalbox-integration-in-uzbekistan)) |

*OX System ([oxapp.io](https://oxapp.io/en)) — bu sessiyada qayta tekshirilmadi; oldingi tadqiqot qaydlariga (00_oldingi_hujjat.md) ko'ra modullari POS/RFID/CRM/HRM, lekin mijozlar soni va AI mavjudligi ziddiyatli (⚠) deb qayd etilgan.*

---

## 2) Texnik bo'shliqlar (faqat manbali dalillar)

- **AI**: 9 ta tekshirilgan mahsulotdan faqat 2 tasida (REGOS — AI-yordamchi hujjat topadi/savdo dinamikasini ko'rsatadi, Pro tarifida; Smartup — javondagi tovarni fotodan tanish) rasmiy sahifada aniq AI funksiyasi haqida da'vo bor. BILLZ, MoySklad, HIPPO, Bito, mDokon'ning rasmiy sahifalarida (bu sessiyada fetch qilingan) AI haqida hech qanday matn topilmadi — bu "topilmadi" ma'nosida, ya'ni AI yo'q degan tasdiqlangan dalil emas, balki sahifada reklama qilinmagan.
- **O'zbek tili**: barcha tekshirilgan mahsulotlarning sayti o'zbek va/yoki rus tilida mavjud (BILLZ, mDokon, Smartup o'zbek tilida sayt taqdim etadi), lekin birortasida "o'zbek tilidagi tabiiy til yordamchisi/chatbot" haqida dalil topilmadi.
- **Nasiya/qarz hisobi**: BILLZ ("nasiya/qarz kuzatuvi" alohida modul), Bito ERP ("kredit savdosi" aniq biznes turi), mDokon (yuqori tarifda qarz hisobi, oldingi tadqiqot qaydi) va Smartup ("debitorlik nazorati", asosiy keys sifatida reklama qilingan) — bu to'rttasida nasiya funksiyasi hujjatlashtirilgan. REGOS, MoySklad, HIPPO sahifalarida bu funksiya aniq ko'rsatilmagan (bu yo'q degani emas, balki marketing sahifasida tilga olinmagan).

---

## 3) Kassa uskunalari — modellar, narxlar, protokollar

*02-faylda (onlayn-NKM/fiskal modul/OFD) allaqachon yoritilgan virtual kassa huquqiy/sertifikatlash talablari bu yerda takrorlanmadi — faqat jismoniy uskunalar va ularning ulanish protokollari.*

### Shtrix-kod skanerlari
| Model | Narx | Izoh |
|---|---|---|
| Arzon simli modellar | ~554 100 so'mdan | Glotr.uz katalogi |
| MERTECH CL-2310 HR P2D SUPERLEAD (simsiz, USB dongle) | 1 500 000 so'm (chegirma bilan) | [mertech.uz](https://mertech.uz/simsiz-shtrix-kod-skaneri-mertech-cl-2310-hr-p2d-superlead-usb-oq/) |
| MERTECH CL-2320 (simsiz, SPP dongle) | 1 414 700 so'm | [glotr.uz](https://glotr.uz/uz/shtrix-kod-skanerlari/) |
| MERTECH CL-2410 (simsiz, BLE dongle) | 1 500 000–1 532 600 so'm | [glotr.uz](https://glotr.uz/uz/shtrix-kod-skanerlari/) |
| Honeywell Youjie HF600 | 1 778 400 so'm | [glotr.uz](https://glotr.uz/uz/shtrix-kod-skanerlari/) |
| Honeywell MS7120 Orbit | 2 696 844 so'm | [glotr.uz](https://glotr.uz/uz/shtrix-kod-skanerlari/) |
| Sanoat/apteka/o'rnatilgan maxsus skanerlar | 1 087 200 so'mdan | [mertech.uz/scanners_uz/embedded_uz](https://mertech.uz/scanners_uz/embedded_uz/) |

**Protokol**: Ko'pchilik USB skaner **"Keyboard Wedge"** (klaviatura emulyatsiyasi) rejimida ishlaydi — skanerlangan kod kompyuterga xuddi klaviaturadan terilgandek yuboriladi, qo'shimcha drayversiz. Zamonaviy skanerlar ikki tomonlama aloqa uchun **HID POS** rejimini ham qo'llab-quvvatlaydi (USB-IF "usage page" 0x8C) ([l-trondirect.com](https://www.l-trondirect.com/blog/barcode-scanners-a-comparison-of-serial-keyboard-wedge-and-usb-interfaces/)). Simsiz modellarda Bluetooth (BLE) yoki 2.4GHz radio-dongle (SPP) orqali ulanish mavjud.

### Chek printerlari (termoprinter)
| Model | Narx | Izoh |
|---|---|---|
| Xprinter T80 | ~$40 | OLX.uz e'lonlari |
| Xprinter XP-58IIT | ~297 000–360 000 so'm | [glotr.uz](https://glotr.uz/cekovye-printery-v-taskente/) *(2026-10-14 tekshiruvida tuzatildi: avval "225 000 so'm" edi — bu model/narx glotr.uz'da shu shaklda topilmadi, joriy narx ~297k–360k so'm oralig'ida)* |
| GP-C180I | 353 814 so'm | glotr.uz |
| MHT-P58C | 355 000 so'm | glotr.uz |
| Xprinter LP-U58 | 396 000 so'm | glotr.uz |
| Xprinter XP-Q200II | 1 607 976 so'm | glotr.uz |
| MITSU RP-809 | 2 105 400 so'm | glotr.uz |
| Sewoo SLK-TS400 | 2 382 186 so'm | glotr.uz |
| Bixolon SRP-330 II | 2 977 733 so'm | glotr.uz |

**Protokol**: Deyarli barcha chek printerlari **ESC/POS** buyruq tilida ishlaydi — Seiko Epson tomonidan yaratilgan, rasmiy standart emas, lekin de-fakto sanoat standarti ("har bir ishlab chiqaruvchi Epson ESC/POS dasturlash qo'llanmasining o'z qism-to'plamini amalga oshiradi"). Epson, Star, Bixolon, Citizen va aksariyat 80mm/58mm printerlar shu buyruqlar to'plamini (ba'zi farqlar bilan) qo'llab-quvvatlaydi ([Epson rasmiy texnik ma'lumotnoma](https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/esc_atsign.html); [Star Micronics ESC/POS rev. 2.52](https://www.starmicronics.com/support/Mannualfolder/escpos_cm_en.pdf)). Ulanish — USB, Ethernet yoki Bluetooth orqali bo'lishi mumkin (model bo'yicha farqlanadi).

### Shtrix-kodli savdo tarozilari
| Model | Narx | Izoh |
|---|---|---|
| AOTE 777 (40kg gacha, 5g aniqlik) | — | [torozi.uz](https://torozi.uz/oz/vesy-tsena-narxi) |
| Umumiy diapazon | 250 000–750 000+ so'm | [prom.uz](https://www.prom.uz/uz/section/vesovoe-oborudovanie/), [mertech.uz](https://mertech.uz/electronic_scales_uz/) |

**Protokol**: MERTECH tarozilari "Frontol, LiteBox bilan integratsiya" imkoniyatiga ega deb reklama qilinadi ([mertech.uz](https://mertech.uz/electronic_scales_uz/scales-for-a-store-en/)), lekin **aniq ulanish protokoli nomi (masalan, seriyali RS-232 "CAS" yoki "Shtrix-M vesy" protokoli) ushbu tadqiqotda ochiq manbada topilmadi** — faqat integratsiya imkoniyati umumiy tarzda tasdiqlangan.

### Android POS terminallari
| Model | Narx | Texnik xususiyat |
|---|---|---|
| UZKASSA N5 | 3 315 000 so'm | Android 7.1, 8GB xotira, 1GB RAM, microSD 64GB gacha ([smartpos.uz](https://smartpos.uz/uz/kassalar)) |
| UZKASSA P100 | 1 950 000 so'm | Android 5.1, Quad-Core 1.0 GHz, 8GB/1GB RAM ([smartpos.uz](https://smartpos.uz/uz/kassalar)) |
| A-Pay P10 | 2 699 000 so'm | [smartpos.uz](https://smartpos.uz/uz/kassalar) |

*PAX A930 (Android/PayDroid, PCI PTS 5.x, EMV) — 02-faylda allaqachon yoritilgan, bu yerda takrorlanmadi. SUNMI modellarining O'zbekistondagi aniq narxi ushbu tadqiqotda topilmadi (faqat SUNMI'ning o'zi mahsulot sahifasi topildi, mahalliy narx yo'q).*

### Virtual kassa uchun minimal uskuna talabi (02-fayl bilan solishtirish)
02-faylda batafsil yoritilganidek, virtual kassa rejimida fiskal modul dasturiy (bulutli) tarzda ishlashi mumkin — alohida jismoniy FM qurilmasi shart emas; minimal talab internetga ulangan qurilma (smartfon/planshet/PC) va ro'yxatdan o'tgan dastur. Chek printeri va shtrix-kod skaneri ixtiyoriy (elektron chek QR orqali ham berilishi mumkin), lekin amaliyotda deyarli barcha vendorlar (BILLZ, HIPPO, mDokon, REGOS) jismoniy chek printeri va skanerni tavsiya qiladi/sotadi.

---

## Ochiq savollar

1. OX System'ning joriy modul/integratsiya/narx tafsilotlari bu sessiyada qayta tekshirilmadi (vaqt cheklovi) — faqat eski tadqiqot qaydiga tayanildi.
2. iiko'ning O'zbekistondagi **rasmiy** narx sahifasi (iiko.ru/uz) ushbu tadqiqotda topilmadi — faqat uchinchi tomon integratorlar (kafesoft.uz, soft24.uz, itdo.uz) narxlari topildi, ular bir-biridan farqlanadi (⚠).
3. Poster POS'ning o'zining asosiy (xorijiy, $ dagi) tarif narxi bu tadqiqotda tekshirilmadi — faqat O'zbekiston uchun fiskalizatsiya qo'shimchasi narxi topildi.
4. Shtrix-kodli tarozilarning aniq ulanish protokoli nomi (seriyali protokol standarti) ochiq manbada topilmadi; faqat "Frontol/LiteBox bilan integratsiya" umumiy da'vosi bor.
5. SUNMI Android POS terminallarining O'zbekistondagi rasmiy chakana narxi topilmadi (faqat ishlab chiqaruvchi sahifasi, mahalliy narx yo'q).
6. BILLZ, MoySklad, HIPPO, Bito, mDokon sahifalarida AI funksiyasi yo'qligi — bu ularning mahsulotida umuman AI yo'qligini anglatmaydi, faqat marketing sahifasida tilga olinmaganini bildiradi; aniqlashtirish uchun mahsulot ichidagi funksiyalar ro'yxati yoki demo kerak bo'ladi.
7. REGOS, MoySklad, HIPPO'da nasiya/qarz moduli borligi yoki yo'qligi mustaqil tasdiqlanmadi (faqat marketing sahifasida tilga olinmagan).

---

## Manbalar

- [billz.io/uz](https://billz.io/uz), [billz.io/uz/prices](https://billz.io/uz/prices), [billz.io/uz/for-developers](https://billz.io/uz/for-developers) — BILLZ
- [regos.uz/ru/price](https://regos.uz/ru/price) — REGOS
- [greenwhite.uz/smartup-en](https://www.greenwhite.uz/smartup-en) — Smartup
- [moysklad.uz](https://www.moysklad.uz/) — MoySklad
- [hippo.uz/ru/pos](https://hippo.uz/ru/pos/) — HIPPO
- [bito.uz](https://bito.uz/) — Bito ERP
- [mdokon.uz](https://mdokon.uz/) — mDokon
- [kafesoft.uz](https://kafesoft.uz/), [kafesoft.uz/ofd](https://kafesoft.uz/ofd) — iiko (mahalliy integrator)
- [joinposter.com/en/applications](https://joinposter.com/en/applications), [knowledge-base.joinposter.com — FiscalBox O'zbekiston](https://knowledge-base.joinposter.com/ru/setting-up-fiscalbox-integration-in-uzbekistan) — Poster POS
- [glotr.uz/uz/shtrix-kod-skanerlari](https://glotr.uz/uz/shtrix-kod-skanerlari/), [mertech.uz](https://mertech.uz/uz/) — shtrix-kod skanerlari
- [glotr.uz/cekovye-printery-v-taskente](https://glotr.uz/cekovye-printery-v-taskente/) — chek printerlari
- [download4.epson.biz — ESC/POS texnik ma'lumotnoma](https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/esc_atsign.html), [starmicronics.com — ESC/POS rev. 2.52](https://www.starmicronics.com/support/Mannualfolder/escpos_cm_en.pdf) — ESC/POS protokoli
- [l-trondirect.com — skaner interfeyslari taqqoslamasi](https://www.l-trondirect.com/blog/barcode-scanners-a-comparison-of-serial-keyboard-wedge-and-usb-interfaces/) — USB HID/Keyboard Wedge
- [torozi.uz](https://torozi.uz/oz/vesy-tsena-narxi), [prom.uz/uz/section/vesovoe-oborudovanie](https://www.prom.uz/uz/section/vesovoe-oborudovanie/), [mertech.uz/electronic_scales_uz](https://mertech.uz/electronic_scales_uz/) — elektron tarozilar
- [smartpos.uz/uz/kassalar](https://smartpos.uz/uz/kassalar) — UZKASSA/A-Pay Android POS terminallar
- `research_notes/AI ERP startap Ozbekistonda/00_oldingi_hujjat.md`, `06_integratsiyalar.md` — oldingi loyihaviy tadqiqot qaydlari (qayta ishlatilgan, qayta qilinmagan)
