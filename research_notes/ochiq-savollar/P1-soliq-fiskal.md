# P1 — Soliq va fiskal qonunchilik (OFD, virtual kassa, chek, davlat hisobotlari)

**Maqsad:** `00-inventar.md` §12 P1 partiyasidagi 13 ta R-bandni (OQ-001, 002, 004, 006, 007, 009, 010, 011, 013, 014, 015, 017, 018) desk-research bilan yopish. · **Kim uchun:** spec'ni yangilovchi agent, asoschi, buxgalter/yurist (faqat tasdiq). · **Sana:** 2026-10-16 (barcha manbalarga murojaat sanasi). · **Usul:** lex.uz'dan joriy konsolidatsiyalangan matnlar to'g'ridan-to'g'ri olindi (WebFetch + to'liq HTML curl + mahalliy grep, so'zma-so'z iqtibos), lex.uz `?ONDATE=` orqali eski/kelgusi tahrirlar solishtirildi; vendor hujjatlari (Payme, Click, Multikassa Postman, GitHub ochiq kod). WebSearch kvotasi tugagani sababli qidiruv Bing/WebFetch orqali. 4 ta parallel Opus agent, natijalar shu faylga birlashtirildi. `1c-ut11` MCP ishlatilmadi. **Spec fayllari o'zgartirilmadi** — "Spec'ga ta'sir" bo'limlari keyingi qadam uchun taklif.

**Asosiy normativ manbalar (joriy tahrir, 2026-10-16):**
- VMQ-943 (23.11.2019) "Onlayn NKM va virtual kassa tizimi qo'llanilishini ta'minlash chora-tadbirlari to'g'risida" — https://lex.uz/docs/4603329. Ilovalar: 1 (Nizom), 1a (to'lov tashkiloti/Marketplace orqali elektron fiskal chek), 2 (texnik talablar), 3 (TXKM reyestri), 4 (onlayn-NKM/virtual kassa Davlat reyestri), 5. Oxirgi tahrirlar: VMQ-23 (23.01.2026, https://lex.uz/docs/8012407), VMQ-393 (20.07.2026; bir qismi 21.07.2026 dan, bir qismi **22.10.2026** dan kuchga kiradi), PF-191 (10.09.2026).
- Soliq kodeksi — https://lex.uz/docs/4674902 (uz: https://lex.uz/docs/-4674902), O'RQ-1108 (25.12.2025, https://lex.uz/docs/-7944527) va O'RQ-1126 (27.03.2026) tahrirlari bilan.
- VM №736 (20.11.2020), 3¹-ilova "Soliq organlari tomonidan soliq hisobotini shakllantirish va tuzish tartibi to'g'risida nizom", VM №154 (09.04.2026) tahriri — https://lex.uz/docs/-5115911.
- DSQ qarori №2020-03 (ro'yxat №3221) — soliq hisobot shakllari, №3221-8 tahriri — https://lex.uz/docs/-4745555.
- MEF buyrug'i №181 (08.10.2024, ro'yxat №3567) — moliyaviy hisobot shakllari — https://lex.uz/docs/-7194594.
- NSBU №2 — https://lex.uz/ru/docs/710346; MJtK — https://lex.uz/docs/97664; VMQ-75 (chakana savdo qoidalari) — https://lex.uz/docs/243235.

---

## Yig'ma jadval

| OQ | Mavzu | Holat | Ishonch | Eng muhim natija |
|---|---|---|---|---|
| OQ-001 | Onlayn/QR to'lovda chekni kim chiqaradi | **YOPILDI** | yuqori | Do'kondagi har qanday elektron to'lovda (QR/Click/Payme/Uzum/UzQR/karta) — **merchant kassasi** (VMQ-943 1-ilova 6-band; 1a-ilova 2-band). To'lov tashkiloti faqat masofaviy savdoda (1a-ilova 4–5-band). |
| OQ-002 | Nasiya: daromad/QQS vaqti, qarz to'lovi cheki | **QISMAN** | yuqori / past-o'rta | Daromad/QQS — **sotuv kuni** (SK 242, 78, 297, 463; NSBU №2). Qarz to'lovida chek **majburiy** (1-ilova 30-band). Ochiq: sotuvda "kredit" turidagi chek majburiyligi va OFD chek turi kodi. |
| OQ-004 | 48 soat — bloklash yoki ogohlantirish | **YOPILDI** | yuqori | **Bloklash majburiy** — 2-ilova 6-band: "48 соат оффлайн режимида ишлагандан сўнг автоматик блоклаш тизимига ўтиш" (VMQ-23). Interim "bloklanmaydi" **noto'g'ri**. |
| OQ-006 | Kassaga pul kiritish/olish OFD'ga | **YOPILDI** | o'rta-yuqori | **Yo'q** — fiskal modulga faqat "сотиш ёки қайтариш" (2-ilova 11-band). |
| OQ-007 | Har kassa alohida ro'yxatdanmi | **YOPILDI** | yuqori | Ha: dastur reyestrga 1 marta; **har `cash_register`** — shoxobcha manzili bo'yicha TXKM orqali, bepul, 4+8 ish soati (1-ilova 16–20, 25-band). |
| OQ-009 | Chek formati | **QISMAN** | yuqori / o'rta | Rekvizitlar — 1-ilova 7-band (to'liq ro'yxat). API'da summalar **butun son tiyinda**; `PackageCode` majburiy. Ko'p stavka jamlanmasi ixtiyoriy. Ochiq: hamkor protokoli bilan tasdiq. |
| OQ-010 | Yaxlitlash qoidalari | **YOPILDI** | o'rta-yuqori | Qonunda yaxlitlash qoidasi **yo'q** — formulamiz muhandislik qarori, qonunga zid emas. Eng kichik tanga 50 so'm (tiyin 01.03.2020 dan muomalada emas). |
| OQ-011 | Davlat reyestriga kiritish: muddat/narx | **QISMAN** | yuqori / o'rta | 10 (operator) ∥ 15 (KXM) ish kuni + 20 ish kuni (DSQ) → **35 ish kuni** (eng yomon 45). Virtual kassa zaxira mablag'idan **ozod**. 1 BHM/yil (440 000 so'm) — tadbirkor to'laydi. Ochiq: ekspertiza/sertifikat narxi. |
| OQ-013 | Davlat hisobotiga tuzatish | **YOPILDI** | yuqori | Shaxsiy kabinetda tasdiqlash yoki **tuzatib taqdim etish**; **5 ish kuni** (SK 5-modda 7-qism), topshirish muddatidan oshmay; javob yo'q = rozilik (SK 81-modda 6–7-qism; VM 736 3¹-ilova 11-band). Spec'dagi "5 kalendar kun" **xato**. |
| OQ-014 | Davlat hisobotini API orqali o'qish | **QISMAN** | yuqori / o'rta | Granulyarlik: QQS — faktura darajasidagi reyestrlar + yig'indi; aylanma — faqat yig'indi (5 manba satri). Ommaviy API **topilmadi** → fayl yuklash interim yakuniy. |
| OQ-015 | Rasmiy hisobot shakllari | **QISMAN** | yuqori / past | QQS — №3221 1-ilova, aylanma — 9-ilova (№3221-8, 2026-01-01); moliyaviy — MEF №181 1-/2-ilova. Ochiq: XML formati va operator API orqali topshirish. |
| OQ-017 | Aylanma solig'i stavkalari | **YOPILDI** | yuqori | 467-modda: umumiy 4%; chakana 4/2/1% (100k+ shahar / boshqa / tog'li); tamaki 4%; YaTT 1%. Chegara 1 mlrd (461-modda). Seed tasdiqlandi. |
| OQ-018 | Faqat elektron chek qonuniymi | **QISMAN** | o'rta | Ta'rif elektron chekni chek deb biladi (1-ilova 2-band), lekin do'kon uchun "virtual kassaning elektron cheki" ruxsati VMQ-23 bilan **olib tashlangan**. Standart — bosma; elektron — zahira. Tasdiq: Soliq (Xat 1) + yurist. |

**Jami:** YOPILDI — 7 (001, 004, 006, 007, 010, 013, 017); QISMAN — 6 (002, 009, 011, 014, 015, 018); YOPILMADI — 0.

**Diqqat — interim'ni teskarisiga o'zgartiradigan topilmalar:**
1. **OQ-004:** 48 soatda fiskal bloklash qonuniy talab (dastur texnik talabi → reyestrga kirish sharti). `16` §6, `31` QT-OFFLINE48-01, `26 A#13`, `06` §1.3 va OQ-005 (D) tavsiyasi ("46 soat — sotuvni to'xtatmaydi") qayta yoziladi.
2. **OQ-013:** "5 kalendar kun" → "5 ish kuni, topshirish muddatidan oshmay".
3. **OQ-002:** `FiscalPolicy`da "daromadni to'lov kuni tan olish" bayrog'i bo'lmasligi kerak (kassa usuli qonunda yo'q).
4. **Yangi talablar (§ "Qo'shimcha topilmalar"):** virtual kassaning karta/QR to'lov tizimlariga majburiy ulanishi (2-ilova 6-band, VMQ-393) — `21` §9.2 "karta — qo'lda belgilash" qaroriga ta'sir qiladi.

---

## OQ-001 — Onlayn/QR to'lovda fiskal chekni kim chiqaradi

- **Javob:** Javob savdo qayerda bo'lganiga bog'liq. Normativ matnda "ziddiyat" yo'q.
  - **(A) Do'kondagi sotuv, to'lov QR/Click/Payme/Uzum/UzQR yoki karta orqali.** Chekni **merchantning o'z onlayn-NKM yoki virtual kassasi** chiqaradi — majburiy. UzQR (banklarda generatsiya qilingan yagona QR) uchun 2026-07-21 dan alohida aytilgan: "NKTdan majburiy chek".
  - **(B) Masofaviy (onlayn) hisob-kitob.** 1a-ilova ishlaydi: elektron fiskal chekni **Marketplace** (reyestrdagi elektron tijorat platformasi; to'lov tashkilotlari ham shu tushunchaga kiradi) o'zining **virtual fiskal moduli** bilan chiqaradi va to'g'riligiga o'zi javob beradi. Merchant chekda "Комитент (воситачи)" STIR/JShShIR sifatida ko'rinadi.
  - Ilgarigi "komissioner" modeli (2022, DSQ/gazeta.uz) faqat (B) holatga tegishli.
  - Do'kon POS'i uchun "kim chiqaradi" tanlovi **kerak emas** — chekni bizning virtual kassa chiqaradi.
- **Dalil** (VMQ-943, https://lex.uz/docs/4603329, joriy tahrir VMQ-393 bilan):
  - 1-ilova **6-band** (VMQ-23, 23.01.2026 tahriri): «…жойларда харид қилинган маҳсулот ва хизматларга электрон тўлов тизимлари орқали амалга оширилган тўловлар учун харидорларга онлайн-НКМ ёки виртуал кассанинг фискал чеки берилиши шарт.» — joyida xarid + elektron to'lov = NKM/virtual kassa cheki shart.
  - 1-ilova **4-band 3-xatboshi** (VMQ-255, 2022): «Харид чекини тўлиқ миқдорда шакллантирилиши ҳамда белгиланган тартибда харидорга тақдим этилиши учун масъулият тадбиркорлик субъектлари зиммасига юклатилади.»
  - **1a-ilova** — «…электрон тўлов ташкилоти ва (ёки) электрон тижорат платформалари (Маркетплейс) орқали электрон фискал чек тақдим қилиш тартиби тўғрисида НИЗОМ»:
    - 2-band 3-xatboshi: «тадбиркорлик субъектлари томонидан харидорларга жойларда харид қилинган маҳсулот ва хизматлар учун Маркетплейс, шу жумладан тўлов ташкилотлар орқали амалга оширилган тўловлар учун онлайн-НКМ ёки виртуал касса чекларини тақдим қилиш;»
    - 2-band 4-xatboshi (VMQ-393, 21.07.2026 dan): «жойларда, шу жумладан, банкларда генерация қилинган ягона QR-код орқали амалга оширилган тўловлар тўғрисидаги маълумотларни операторга юбориш. Бунда ягона QR-код орқали амалга оширилган тўловларга ҳам назорат-касса техникаларидан мажбурий равишда чек берилиши шарт.»
    - 3-band: «Маркетплейс фойдаланувчиси — … фискал маълумотларни Маркетплейс сервери орқали операторга юборувчи тадбиркорлик субъекти.»
    - 4-band (VMQ-23): «Фискал чек маълумотларни операторга юборилиши Маркетплейснинг виртуал фискал модули билан тасдиқлаш орқали амалга оширилади.»
    - 5-band: «…Маркетплейс жавобгар ҳисобланади.»
  - 1-ilova 7-band: chek rekvizitida «Комитент (воситачи) СТИРи/(ЖШШИРи)».
  - Soliq kodeksi **221-modda 1-qism** (O'RQ-1108, 2026-01-01 dan): chek bermasdan sotish va QR to'lovni rad etish — «беш миллион сўм миқдорида жарима».
  - Vendorlar: Payme `SetFiscalData` (https://developer.help.paycom.uz/metody-merchant-api/setfiscaldata): «Через этот метод мерчантам передаются данные о фискализации чека… terminal_id — Номер Виртуального Фискального Модуля» — Payme masofaviy to'lovni o'z VFM'i bilan fiskallashtiradi. Click (https://docs.click.uz/merchant-api/fiscalization): ikki rejim — `ofd_data/submit_items` (Click fiskallashtiradi; majburiy `SPIC`, `PackageCode`, `VAT`, `VATPercent`, `CommissionInfo`) va `ofd_data/submit_qrcode` (merchant tayyor `ofd.soliq.uz/epi?...` havolasini yuboradi).
- **Ishonch:** **yuqori** — (A)/(B) bo'linishi birlamchi normaning joriy tahririda so'zma-so'z. **O'rta** — vendor qismi (Payme `detail`/IKPU va Uzum fiskalizatsiya sahifalari SPA, ochilmadi; Payme/Click/Uzum Marketplace reyestridaligi tekshirilmadi).
- **Spec'ga ta'sir:**
  - `26-ochiq-savollar-reestri.md` **B#8** → yopiladi: «YOPILDI (2026-10-16): do'kondagi sotuvda QR/Click/Payme/Uzum/UzQR yoki karta bilan to'langanda fiskal chekni merchantning virtual kassasi (bizning tizim) chiqaradi — VMQ-943 1-ilova 6-band; 1a-ilova 2-band 3–4-xatboshi (VMQ-393, 21.07.2026). To'lov tashkiloti chekni faqat masofaviy (Marketplace) hisob-kitobda chiqaradi (1a-ilova 4–5-band).»
  - `04-biznes-jarayonlar.md` **BP-05**: Mermaid `E` tuguni → `"To'lov ilovasi orqali;\nfiskal chek — merchant virtual kassasidan (1a-ilova 2-band)"`; "Manba" ostidagi *Ochiq savol* jumlasi va **OS1** o'rniga: «Hal qilindi: do'kondagi har qanday elektron to'lovda (QR, Click/Payme/Uzum, UzQR, karta) fiskal chekni merchant kassasi chiqaradi (VMQ-943 1-ilova 6-band; 1a-ilova 2-band). To'lov tizimi chek chiqarishi faqat masofaviy savdoga tegishli. Ikki marta fiskallashtirmaslik uchun Click'ka tayyor chek havolasi `ofd_data/submit_qrcode` bilan yuboriladi.»
  - `03-modullar-talablari.md` **OS7**, `06-ekranlar-umumiy.md` **OS8** va POS-03 → "Hal qilindi"; POS-03 ichidagi "…huquqiy jihatdan ziddiyatli … ochiq savol" bo'lagi o'rniga: «QR/Click/Payme/Uzum/UzQR to'lovida ham fiskal chekni kassamiz chiqaradi (VMQ-943 1-ilova 6-band)».
  - `21-integratsiyalar.md` **§9** va **OS5**: «Do'kon (POS) to'lovlarida fiskal chekni har doim bizning virtual kassa chiqaradi. Adapter to'lov tizimiga faqat tayyor chek havolasini uzatadi: Click — `POST /v2/merchant/payment/ofd_data/submit_qrcode`. Payme `SetFiscalData` — Payme fiskallashtirgan (masofaviy) chekni qabul qiladi, POS oqimida ishlatilmaydi. Payme/Uzum kassasida 'joyida to'lov' uchun ularning o'z fiskalizatsiyasi o'chirilgani merchant kabinetida tekshiriladi (vendor tasdig'i). `FiscalPolicy.issuer` sozlamasi faqat kelajakdagi masofaviy kanal (onlayn-do'kon/Telegram-checkout) uchun qoladi (standart `merchant`).»
- **Holat:** **YOPILDI.** Bloklamaydigan qoldiq: Payme/Uzum "joyida to'lov" kassasida ular ham chek chiqarib, aylanma ikki marta ko'rinmasligini Payme/Uzum menejeri tasdiqlaydi (P3 bilan kesishadi). Interim: Click — `submit_qrcode`; Payme/Uzum — "joyida to'lov" kassa turi, pilotda tekshiriladi.

---

## OQ-002 — Nasiyaga sotuvda daromad/QQS tan olish vaqti va `debt_settlement` cheki

- **Javob:**
  1. **Daromad va QQS sotuv (jo'natish) kuni tan olinadi**, to'lov kuni emas — QQS to'lovchiga ham, aylanma solig'i to'lovchiga ham. Soliq kodeksida "kassa usuli" yo'q.
  2. **Qarz to'langanda fiskal chek berish majburiy** — chek "pul mablag'lari qabul qilinganini tasdiqlovchi" hujjat. `debt_settlement` cheki qonuniy va kerak.
  3. Lekin `01 #30` dagi "nasiya sotuvda chek umuman chiqmaydi" VMQ-943 ga to'liq mos emas: 1-ilova 7-band chek **to'lov turlari** ichida «кредит» ni sanaydi va bu turdagi chekda QR-kod va fiskal belgi bo'lmasligini aytadi. Talqin: nasiya sotuv paytida "kredit" turidagi chek (QR/fiskal belgisiz) shakllanadi, pul tushganda — fiskal belgili chek. Sotuvdagi "kredit" cheki **majburiymi** va qarz to'lovi cheki OFD'da **qaysi tur** bilan yuboriladi — normativ matn aniq aytmaydi.
- **Dalil:**
  - Soliq kodeksi (https://lex.uz/docs/4674902; ko'rilgan oxirgi tahrir O'RQ-1126, 27.03.2026):
    - **242-modda 1-qism:** «…ҳисобварақ-фактура тақдим этилган сана ёки товарлар жўнатилган (берилган) сана, агар ушбу сана ҳисобварақ-фактура тақдим этилган санадан олдин келса, товарларни реализация қилиш бўйича айланма амалга оширилган санадир».
    - **265-modda 2-qism:** soliq «айланмаларни амалга ошириш санасидан келиб чиққан ҳолда» hisoblanadi.
    - **78-modda:** «солиқ тўловчи … ҳисобни ҳисоблаш усули бўйича миллий валютада юритади» (hisoblash/accrual usuli).
    - **463-modda** (aylanma solig'i obyekti — «43-бобига мувофиқ аниқланадиган жами даромад») + **297-modda**: «даромадни эътироф этиш санаси бухгалтерия ҳисоби тўғрисидаги қонунчилик талабларига мувофиқ аниқланади».
  - NSBU №2 (https://lex.uz/ru/docs/710346), **12-band**: «Доход от реализации товаров признается при … 12.1. Хозяйствующий субъект передал покупателю значительную часть рисков и преимуществ…»; ilova **8-misol** («Продажа в рассрочку»): «Доход, имеющий отношение к цене реализации, за исключением процентов, признается на дату реализации».
  - VMQ-943 1-ilova **7-band**: «тўлов тури (сотув, қайтариш, бўнак, бўлиб тўлаш, кредит). Бунда тўловнинг бўнак, бўлиб тўлаш, кредит турлари бўйича шакллантирилган чекларда QR-код ва фискал белги мавжуд бўлмайди».
  - VMQ-943 1-ilova **30-band**: «харидорларга пул маблағлари қабул қилинганлигини тасдиқловчи онлайн-НКМ ёки виртуал касса чекини мажбурий тартибда берилиши лозим».
  - Ikkilamchi: MultiBank virtual kassa C# SDK (https://github.com/spoleto-software/Spoleto.VirtualKassa.MultiBank) alohida `CreditSlip`/`AdvanceSlip` operatsiyalariga ega — amalda chek turlari alohida.
- **Ishonch:** daromad/QQS sanasi — **yuqori**; qarz to'lovida chek — **yuqori**; sotuvdagi "kredit" cheki va OFD turi — **past-o'rta** (OFD protokoli ommaviy emas).
- **Spec'ga ta'sir:**
  - `13-provodka-qoidalari.md` **§2.14** "Daromad/QQS tan olish vaqti" xatboshisi: «**Daromad/QQS tan olish vaqti (OQ-002 yopildi):** qarzga sotuvda daromad (9020) va QQS (6410) **sotuv (jo'natish) kuni** tan olinadi — Soliq kodeksi 242-modda 1-qism (QQS), 78-modda (hisoblash usuli), 463 + 297-modda (aylanma), NSBU №2 12-band va ilova 8-misol. Kassa usuli (to'lov kuni) qonunda yo'q — `FiscalPolicy`da bunday bayroq **bo'lmaydi**. Provodka sanasi ≠ fiskal chek sanasi.» Shu §2.14 "Fiskal chek" xatboshisi oxiriga: «Qarz to'lovidagi `debt_settlement` cheki VMQ-943 1-ilova 30-band bo'yicha **majburiy**. 1-ilova 7-band "kredit" to'lov turini (QR-kod va fiskal belgisiz chek) nazarda tutadi — `FiscalPolicy.credit_sale_receipt`: `none` | `credit_type` (standart `none`, hamkor/OFD tasdig'igacha).»
  - `13` **OS7** → «qisman yopildi (OQ-002)».
  - `01-qarorlar.md` **#30** "⚠ Ochiq: daromad/QQS tan olish vaqti…" → «Daromad/QQS — sotuv kuni (SK 242, 297-modda; NSBU №2), OQ-002 da yopildi. Ochiq qolgani faqat sotuvdagi "kredit" turidagi chek (VMQ-943 1-ilova 7-band) va OFD chek turi kodi.» **#42** dagi "interim" so'zi olib tashlanadi.
  - `04-biznes-jarayonlar.md` **BP-03 6-qadam** va **BP-11 4-qadam**: «daromad/QQS sotuv kuni tan olinadi (13 §2.14); to'lov kunida faqat pul harakati (Dt 5010/5710 Kt 4010) va fiskal chek». **OS12** → qisman yopildi. Bu `00-inventar` §1 nomuvofiqlik #4 ni ham yopadi.
  - `03` **US-M08-04**, `18` **§4.5/§12.2**, `31` **#5**: "daromad to'lov kuni" degan har qanday variant olib tashlanadi.
  - `26` **B#9** → «qisman yopildi — huquqiy qism yopildi; OFD chek turi OQ-012 (E) ga o'tdi». `1C §13.1 onec_settings.credit_revenue_timing` — standart `sale_date`, `payment_date` qiymati olib tashlanishi tavsiya etiladi.
- **Holat:** **QISMAN.** Yopildi: daromad/QQS sanasi, qarz to'lovida chek majburiyligi. Ochiq: (a) nasiya sotuvda "kredit" cheki majburiymi; (b) to'lov cheki OFD'ga qaysi tur bilan ketadi; (c) OFD ma'lumotiga asoslangan davlat hisobotida (OQ-013/014) to'lov chekidagi QQS sotuv QQSi bilan ikki marta sanalmasligi. **Xavfsiz interim:** provodka sotuv kuni; qarz to'lovida fiskal belgili chek; sotuvdagi "kredit" cheki `FiscalPolicy.credit_sale_receipt=credit_type` ortida tayyor, standart o'chiq. **Kim tasdiqlaydi:** fiskal hamkor/OFD (OQ-012), keyin buxgalter.

---

## OQ-004 — 48 soatda OFD'ga yetmagan cheklar: bloklash yoki ogohlantirish

- **Javob:** **Bloklash majburiy.** Virtual kassa (va onlayn-NKM) texnik talabi: 48 soat offline ishlagandan keyin **avtomatik bloklash tizimiga o'tish**. Bu dasturning o'ziga qo'yilgan talab — Davlat reyestriga kiritish sharti; 22.10.2026 dan esa texnik talabga mos kelmaslik reyestrdan chiqarish asosi. VMQ-23 (23.01.2026) muddatni 24 → 48 soatga uzaytirgan va 1-ilova 31-banddan "onlayn rejimga o'tgandan keyin 24 soat ichida" so'zlarini olib tashlagan. Faqat ogohlantirish bilan ishlaydigan kassa texnik talabga mos emas → foydalanuvchiga SK 221-modda 4-qism (20 mln so'm), bizga reyestrdan chiqarish xavfi.
- **Dalil:**
  - VMQ-943 **2-ilova 6-band 6-xatboshi** (virtual kassa): «48 соат оффлайн режимида ишлагандан сўнг автоматик блоклаш тизимига ўтиш;» — izoh: «(6-банднинг олтинчи хатбошиси … 2026 йил 23 январдаги 23-сонли қарори таҳририда — … 23.01.2026 й., 09/26/23/0070-сон)». Onlayn-NKM uchun xuddi shu — **3-band 19-xatboshi**.
  - VMQ-23 (https://lex.uz/docs/8012407) **5-band «в»**: «ўн тўққизинчи хатбошидаги «24» рақами «48» рақами билан алмаштирилсин; 6-бандда: олтинчи хатбошидаги «24» рақами «48» рақами билан алмаштирилсин»; **«а»**: «31-банддаги «шунингдек, онлайн режимига ўтгандан кейин 24 соат ичида» сўзлари чиқариб ташлансин».
  - VMQ-943 **1-ilova 31-band** (joriy): «…чеклар оффлайн режимида берилиши мумкин. Бунда биринчи оффлайн режимда шаклланган чекни 48 соат ичида операторга узатилиши таъминланиши зарур.»
  - 2-ilova 6-band (boshqa avtoblok): «фискал модул носоз ҳолатга келганда ёки унинг хотираси тўлганда автоматик блоклаш тизимига ўтиш»; **8-band**: «Виртуал кассадан қуйидаги ҳолларда фойдаланишга рухсат этилмайди: … чекда мажбурий талаблардан бири ёки бир нечтаси мавжуд бўлмаса».
  - SK **221-modda 4-qism** (O'RQ-1108, 2026-01-01; lex.uz ruscha norasmiy tarjima): «Использование контрольно-кассовой техники, не соответствующей техническим требованиям, или с нарушением электронной программы обслуживания, — влечет наложение штрафа в размере двадцати миллионов сумов.»
  - MJtK **175-modda** (https://lex.uz/docs/97664; lex.uz joriy tartibida 7-qism): «…солиқ органларининг ахборот тизимлари билан интеграция қилинишини таъминлаш … талабларни ёки тартибни бузиш — мансабдор шахсларга базавий ҳисоблаш миқдорининг юз баравари миқдорида жарима».
  - VMQ-943 **4-ilova 19-band** (VMQ-393, 22.10.2026 dan): «онлайн НКМ ва виртуал кассаларнинг техник имкониятлари уларга қўйиладиган техник талабларга мувофиқ бўлмаганда» — reyestrdan chiqarish.
- **Ishonch:** **yuqori** — me'yor va o'zgartiruvchi akt so'zma-so'z. Talqin qoldig'i: "48 soat offline ishlash" hisobining boshlanishi; 31-band bilan birga o'qilganda eng xavfsiz talqin — OFD tasdiqlamagan **eng eski chek** yaratilgan paytdan.
- **Spec'ga ta'sir:**
  - `16-offline-sync.md` **§6** "48 soatda yangi sotuvni bloklash — ochiq savol" o'rniga: «**48 soatda fiskal bloklash — majburiy** (VMQ-943 2-ilova 6-band 6-xatboshi, VMQ-23 23.01.2026 tahriri: "48 соат оффлайн режимида ишлагандан сўнг автоматик блоклаш тизимига ўтиш"). Shu `cash_register`da OFD tasdig'ini olmagan eng eski fiskal chekning `created_at`idan 48 soat o'tsa, yangi fiskal chek (sotuv, qaytarish, avans, kredit, `debt_settlement`) **shakllantirilmaydi**. Fiskal bo'lmagan amallar (sinxronizatsiya, qoldiqni ko'rish, smenani yopish, naqd sanash) ishlayveradi. Barcha kutilayotgan cheklar OFD tasdig'ini olgach blok avtomatik yechiladi. Egasi/admin uchun qo'lda chetlab o'tish **yo'q**. Ogohlantirishlar: 24 soat (sariq), 40 soat (qizil), 46 soat (modal "2 soatdan keyin kassa bloklanadi"). Blokda `audit_log` + M18 xabari.» **OS1** → «Yopildi (OQ-004)».
  - `31-qabul-testlari.md` **#2 / QT-OFFLINE48-01**: «…`t0+48 soat`da shu kassada yangi fiskal chek yaratish rad etiladi (`FISCAL_OFFLINE_48H_BLOCKED`), audit bayrog'i qo'yiladi va M18 xabari ketadi; barcha cheklar OFD tasdig'ini olgach keyingi sotuv muvaffaqiyatli o'tadi.» "Spec'da aniqlashtirish kerak" 2-band o'chiriladi.
  - `06-ekranlar-umumiy.md` **§1.3**: to'rtinchi holat «⛔ Bloklangan — 48 soat o'tdi, yangi chek chiqarib bo'lmaydi; faqat "Qayta urinish/sinxronlash" ishlaydi».
  - **OQ-005 (D)** tavsiyasi tuzatiladi: 46 soatdagi modal endi "sotuvni to'xtatmaydi" emas, balki "48 soatda bloklanadi" ogohlantirishi; `OFFLINE_WARN_HOURS=[24,40,46]`, `OFFLINE_BLOCK_HOURS=48`. `26 A#13` shunga moslanadi.
  - `17`/`18` xato kodlari ro'yxatiga `FISCAL_OFFLINE_48H_BLOCKED` qo'shiladi.
- **Holat:** **YOPILDI.**

---

## OQ-006 — Kassaga pul kiritish/olish (M16) OFD'ga yuboriladimi

- **Javob:** **Yo'q.** VMQ-943 da kassaga pul kiritish, olish yoki inkassatsiya fiskal hujjat sifatida belgilanmagan: chek to'lov turlari — sotuv, qaytarish, bo'nak, bo'lib to'lash, kredit; fiskal modulga faqat "sotish yoki qaytarish" operatsiyasi yuboriladi; Z-hisobot faqat cheklardan tuziladi. Multikassa ilova darajasida "Внесение/Изъятие" (`module_operation_type` 14/15) beradi, lekin so'rovda fiskal maydon yo'q va fiskal modulning Z-hisoboti faqat `TotalSale*`/`TotalRefund*` dan iborat — bu provayderning ichki hisobi, OFD talabi emas.
- **Dalil:**
  - VMQ-943 1-ilova **7-band**: «тўлов тури (сотув, қайтариш, бўнак, бўлиб тўлаш, кредит)».
  - VMQ-943 **2-ilova 11-band**: «…умумий чек суммаси, нақд ёки банк пластик картадан тўлов суммаси, ҚҚС суммаси, операция тури (сотиш ёки қайтариш) маълумотларини фискал модулга юборади.»
  - 1-ilova **2-band** (Z-hisobot ta'rifi): «фискал модулнинг оператив хотирасидаги чекларнинг асосий фискал маълумотларини бўшатиб…».
  - Multikassa Postman kolleksiyasi (https://docs-virtual-kassa.multibank.uz, kolleksiya 6027358/UVeNnNw9): "Получить состав ZReport" javobi — `TotalRefundVAT, TotalRefundCard, TotalRefundCash, TotalRefundCount, TotalSaleVAT, TotalSaleCard, TotalSaleCash, TotalSaleCount`; "Внесение денежных средств" — `{"module_operation_type":"14","receipt_sum":…,"receipt_cashier_name":…,"comment":…}`.
- **Ishonch:** **o'rta-yuqori** — qonunda yo'q, bitta provayderning fiskal modul javobi tasdiqlaydi; OFD rasmiy protokoli ommaviy emas.
- **Spec'ga ta'sir:**
  - `11-malumotlar-modeli.md` **OS2**: «Yopildi (OQ-006): kassa pul harakati OFD'ga yuborilmaydi — VMQ-943 1-ilova 7-band va 2-ilova 11-band (fiskal modulga faqat "сотиш ёки қайтариш"). `cash_movements` fiskal hujjat emas; `fiscal_receipts.kind` kengaytirilmaydi.»
  - `03-modullar-talablari.md` **M16** "Davlat tizimlari bog'liqligi": «Fiskal bo'lmagan operatsiya; OFD'ga yuborilmaydi (VMQ-943 2-ilova 11-band). Fiskal hamkor talab qilsa (masalan, Multikassa op. 14/15) — faqat adapter darajasida ixtiyoriy aks ettirish.»
  - `26` **A#30** asosiga yuqoridagi lex.uz iqtibosi qo'shiladi.
- **Holat:** **YOPILDI.** OFD rasmiy spetsifikatsiyasi (OQ-012) kelganda faqat tasdiqlanadi.

---

## OQ-007 — Har filial/har virtual kassa alohida ro'yxatdan o'tadimi

- **Javob:** **Ha, ikki darajada.** (1) Dastur (model/versiya) Davlat reyestriga bir marta kiritiladi. (2) **Har bir virtual kassa** (o'z fiskal moduli yoki virtual fiskal moduli bilan) savdo boshlanishidan oldin turg'un savdo shoxobchasi manzili bo'yicha davlat soliq organida alohida ro'yxatdan o'tkaziladi: ariza reyestrdagi TXKM yoki uning filiali orqali; arizada shoxobcha manzili, kassa seriya/versiya raqami, fiskal modul seriyasi; har kassaga TXKM bilan xizmat shartnomasi; ro'yxatdan o'tkazish **bepul**; TXKM 4 ish soatida, soliq xodimi 8 ish soatida ko'radi; manzil o'zgarsa — 3 ish kunida qayta ariza; bitta fiskal modul bir vaqtda faqat bitta virtual kassaga xizmat qiladi.
- **Dalil:**
  - VMQ-943 1-ilova **16-band**: «…онлайн-НКМ ёки виртуал кассани давлат солиқ хизмати органларидан рўйхатдан ўтказиш учун Давлат реестрига киритилган ТХКМ ёки унинг ҳудудий филиалларига 1-иловада келтирилган шаклга мувофиқ электрон ёки ёзма равишда ариза билан мурожаат қилинади.» Ilova hujjatlar: shoxobcha hujjatlari, «ТХКМ билан тузилган шартноманинг нусхаси», xaritadagi koordinata.
  - Nizomning 1-ilovasi (ariza shakli) sarlavhasi: «Онлайн-НКМ ёки виртуал кассани турғун шохобча … жойлашган жой бўйича давлат солиқ хизмати органларида рўйхатдан ўтказиш тўғрисида»; ariza «…завод рақами (версияси) … бўлган онлайн-НКМ (виртуал касса) ва … серия рақамли фискал модулни» ro'yxatga qo'yish uchun.
  - **18-band**: «4 иш соати ичида … саккиз иш соати ичида кўриб чиқилади»; **20-band**: «…рўйхатдан ўтказилганлиги учун тўлов ундирилмайди»; **25-band**: manzil o'zgarsa «уч иш кунида».
  - **2-ilova 6-band**: «битта фискал модулдан бир вақтда фақат битта виртуал касса учун фойдаланиши таъминланиши»; **8-band**: TXKM bilan shartnoma bo'lmasa foydalanishga ruxsat yo'q.
  - **4-ilova 3-band**: reyestr «виртуал касса дастурий маҳсулотлари (жумладан, уларнинг моделлари ва версиялари)» ma'lumotlaridan iborat.
  - 1-ilova **55-band** (VMQ-23): «Тадбиркорлик субъектларини фискал модул ёки виртуал фискал модул билан таъминлаш … учун тадбиркорлик субъектлари томонидан йилда бир марта базавий ҳисоблаш миқдорининг бир баравари миқдорида операторга тўлов амалга оширилади.»
- **Ishonch:** **yuqori** (qonun matni). my.soliq.uz yo'riqnomasi ochilmadi (SPA), lekin qonun TXKM yo'lini aniq belgilaydi.
- **Spec'ga ta'sir:**
  - `03-modullar-talablari.md` **M14** "Davlat tizimlari bog'liqligi" ("Taxmin/ochiq savol" o'rniga): «Dastur (versiya) Davlat reyestriga bir marta kiritiladi (VMQ-943 4-ilova 3-band). **Har bir `cash_register`** savdodan oldin shoxobcha manzili bo'yicha TXKM orqali soliq organida alohida ro'yxatdan o'tadi (1-ilova 16–20-band: bepul, ≈4+8 ish soati) va alohida fiskal modul/virtual fiskal modulga ega bo'ladi (2-ilova 6-band). Filial manzili o'zgarsa — 3 ish kunida qayta ariza (25-band). Ro'yxatdan o'tmagan kassada savdo — SK 221-modda 2-qism jarimasi.»
  - `11`/`12` `cash_registers`: `tax_registered_at TIMESTAMPTZ`, `outlet_address_snapshot TEXT`, `txkm_contract_ref TEXT` qo'shiladi; `ofd_status` izohidagi "taxmin" olib tashlanadi (qiymatlar — OQ-008, E). Qoida: `ofd_status` `registered`/`active` bo'lmagan kassada fiskal chek chiqarish taqiqlanadi.
  - Filial manzili o'zgarishi → shu filial kassalari uchun "qayta ro'yxatdan o'tkazish (3 ish kuni)" vazifasi/eslatmasi (M14).
- **Holat:** **YOPILDI.** (SK 221-modda 2-qism jarima summasi o'zbekcha rasmiy matndan tekshirilmadi — kodga ta'siri yo'q.)

---

## OQ-009 — Fiskal chek formati

- **Javob:**
  - **Majburiy rekvizitlar** — VMQ-943 1-ilova 7-band (ro'yxat "Dalil"da).
  - **MXIK** OFD'ga har qator (tovar) darajasida yuboriladi. Qog'oz chekdagi joylashuvi normada belgilanmagan; qo'shimcha rekvizitlarga ruxsat bor.
  - **Ko'p QQS stavkasi:** har qatorda o'z stavkasi va QQS summasi, chek oxirida «жами ҚҚС». Stavka bo'yicha jamlanma qator talab qilinmaydi (ixtiyoriy).
  - **Summa birligi:** OFD/fiskal API'larda summalar **butun son tiyinda** (so'm × 100): `Price`, `GoodPrice`, `VAT`, `Discount`, `ReceivedCash`, `ReceivedCard`. Qog'oz chekda 2 xona.
  - **Qadoq kodi:** `PackageCode`/`Units` tasnif.soliq.uz dan; API'da `PackageCode` majburiy. 23.01.2026 dan o'lchov birligi "yagona elektron milliy katalog bo'yicha" bo'lishi shart.
  - **To'lov shakli:** 22.10.2026 dan "naqd, bank kartalari, **QR-kodli to'lov** yoki aralash".
- **Dalil:**
  - VMQ-943 1-ilova **7-band** (joriy tahrir), rekvizitlar: банк картаси тури (VMQ-610, 2025) · чекнинг тартиб рақами · онлайн-НКМнинг завод рақами ёки виртуал кассанинг серия рақами · тадбиркорлик субъектининг номи · СТИР/ЖШШИР (23.01.2026) · пулли ҳисоб-китоблар амалга ошириладиган манзил · Комитент (воситачи) СТИРи/ЖШШИРи (23.01.2026) · ижтимоий карта рақами (биринчи ва охирги тўртта рақам) · транзакциянинг уникал рақами · товар/хизмат номи · маркировка қилинадиган товарлар учун маркировка белгиси · «маҳсулотлар (товар ва хизматлар) ягона электрон миллий каталоги бўйича ўлчов бирлиги» (23.01.2026) · штрих коди · товар/хизмат миқдори · нархи (қиймати) · «товар/хизматнинг қўшилган қиймат солиғи ставкаси» · «…солиғи суммаси» · тўлов шакли: нақд, банк карталари, QR-кодли тўлов ёки аралаш (VMQ-393, 22.10.2026 dan) · тўловнинг жами суммаси · «харид учун тўловнинг қўшилган қиймат солиғи жами суммаси» · тўлов санаси ва вақти · тўлов тури · фискал модулнинг такрорланмайдиган рақами · фискал белги · камида 30х30 мм QR-код. Shu bandda: «…товарлар ва хизматларнинг идентификация кодлари операторга юборилиши лозим»; oxirida: «Чекда қўшимча равишда бошқа реквизитлар ҳам кўрсатилиши мумкин». Qog'oz: «махсус оқ қоғозда … кенглиги 55 миллиметрдан … кам бўлмаслиги лозим».
  - **38¹-band** (23.01.2026): tuzatuvchi chek «МХИК кодлари, ўлчов бирлиги, сони ва суммаси ва ҚҚС суммаси бўйича тафовут» uchun, soliq hisoboti muddatigacha — MXIK/birlik/son/QQS qator darajasida ekanini tasdiqlaydi.
  - OFD chek JSON (ochiq kod): `Items[]{Name, Barcode, Labels, SPIC, Units, PackageCode, GoodPrice, Price, Amount, VAT, VATPercent, Discount, Other}`, `TotalVAT`, `ReceivedCash/Card` — https://github.com/thebetacompany/fiscal-integration-uz (`src/utils/interfaces.ts`).
  - Click fiskalizatsiya (https://docs.click.uz/merchant-api/fiscalization; mirror: https://github.com/ubranch/uzbekistan-payment-skills `skills/click-integration/references/11-fiscalization.md`): «amounts and item prices are in **tiyin** (1 so'm = 100 tiyin)»; `PackageCode string(20) Yes*`; `VAT uint64 … in tiyin`.
  - MultiBank SDK: `receipt_sum`, `receipt_gnk_receivedcash/card` — `MultiplyDivide100Converter` (×100).
- **Ishonch:** rekvizitlar — **yuqori**; tiyin butun son — **o'rta** (3 mustaqil ikkilamchi manba, OFD rasmiy protokoli ommaviy emas); jamlanma qator ixtiyoriyligi — **o'rta-yuqori**.
- **Spec'ga ta'sir:**
  - `08-dizayn-tizimi.md` **§13** (chek shabloni), **OS4/OS6**: «Chek rekvizitlari — VMQ-943 1-ilova 7-band (tahrir 20.07.2026). Har qatorda: nom, (marka kodi), MXIK, katalog bo'yicha o'lchov birligi, shtrix kod, miqdor, narx, QQS stavkasi, QQS summasi. Chek oxirida: to'lov shakli (naqd/karta/QR/aralash), jami summa, jami QQS, sana-vaqt, to'lov turi, FM raqami, fiskal belgi, QR (≥30×30 mm; kredit/bo'nak/bo'lib to'lash turlarida yo'q). Bosma kenglik ≥55 mm. Stavka bo'yicha jamlanma qator — ixtiyoriy (7-band oxirgi xatboshi).»
  - `11-malumotlar-modeli.md` **OS1** → yopiladi; `fiscal_receipt_lines`: `mxik CHAR(17) NOT NULL`, `package_code VARCHAR(20) NOT NULL`, `unit_code` majburiy. `fiscal_receipts.payment_form` enum'iga `qr` qo'shiladi (`cash/card/qr/mixed`).
  - `01-qarorlar.md` **#26** "Istisno": «fiskal chek: qog'ozda 2 xona; `FiscalAdapter` OFD/hamkorga **butun son tiyinda** uzatadi (`int(amount×100)`, faqat adapter chegarasida)».
  - `26` **B#84** → «yopildi: tiyin integer, OQ-012 hamkor spetsifikatsiyasi bilan tasdiqlanadi»; **A#29** → yopildi.
- **Holat:** **QISMAN.** Yopildi: rekvizitlar, MXIK, ko'p stavka. Ochiq: tiyin formati va `PackageCode` majburiyligi tanlangan fiskal hamkor protokoli bilan tasdiqlanishi. **Interim:** adapterda tiyin integer, qog'ozda 2 xona. **Kim:** fiskal hamkor/OFD (OQ-012); bloklamaydi.

---

## OQ-010 — Yaxlitlash qoidalari

- **Javob:**
  - **Normativda yaxlitlash qoidasi yo'q** — Soliq kodeksining QQS bobida ham, VMQ-943 da ham «тийин», «яхлит» so'zlari uchramaydi. QQS «солиқ базасининг … фоизли улуши». Demak qator bo'yicha `ROUND_HALF_UP` — qonunga zid bo'lmagan muhandislik qarori.
  - **QQS ajratish formulasi** `×r/(100+r)` 248-modda (baza QQSsiz) va 258-modda (12%) dan algebraik kelib chiqadi.
  - **Qator darajasida tiyingacha** hisoblash OFD formatiga mos (har `Item.VAT` tiyinda, alohida `TotalVAT`). OFD `TotalVAT = ΣVAT` ni tekshiradimi — tasdiqlanmagan.
  - **Naqd:** tiyin tangalar va 1–25 so'mlik tangalar **2020-03-01 dan muomalada emas**; eng kichik tanga — **50 so'm**. Qatorni so'mgacha yaxlitlash — qonun talabi emas, biznes tanlovi. Naqd qaytimni 50 so'mga yaxlitlash bo'yicha normativ topilmadi.
- **Dalil:**
  - Soliq kodeksi **265-modda 1-qism**: «солиқ суммаси солиқ базасининг солиқ ставкасига мувофиқ бўлган фоизли улуши сифатида ҳисоблаб чиқарилади»; **248-modda 1-qism**: baza «унга солиқни киритмаган ҳолда … реализация қилинадиган товарларнинг … қиймати сифатида аниқланади»; **258-modda**: «солиқ ставкаси 12 фоиз миқдорида белгиланади». To'liq matnda «тийин»/«яхлит» qidiruvi natija bermadi — https://lex.uz/docs/4674902. VMQ-943 da ham yo'q.
  - Markaziy bank (https://cbu.uz/ru/banknotes-coins/coins/, sahifa 04.01.2023 da yangilangan): «1 тийин (находилась в обращении до 01.03.2020 г.)» — xuddi shunday 3/5/10/20/50 tiyin va 1/5/10/25 so'm; muomalada: 50, 100, 200, 500, 1000 so'm.
  - OFD `Item.VAT` — "VAT amount in tiyin" (Click hujjati, OQ-009).
- **Ishonch:** "qonunda qoida yo'q" — **o'rta-yuqori** (to'liq matn qidiruvi; DSQ hisobot shakllari yo'riqnomalari tekshirilmadi); tangalar — **yuqori**; OFD QQS mosligi tekshiruvi — **past**.
- **Spec'ga ta'sir:**
  - `13-provodka-qoidalari.md` **§5.3** QQS punkti: «QQS: har chek qatori uchun `ROUND_HALF_UP(line_total×r/(100+r), 2)` (tiyin), chek QQSi = qatorlar yig'indisi. Soliq kodeksi (247–265-moddalar) va VMQ-943 da yaxlitlash qoidasi **yo'q** — bu muhandislik qarori (formula 248- va 258-moddalardan), OFD `Item.VAT`/`TotalVAT` (tiyin) formatiga mos. Qator `line_total` so'mgacha yaxlitlanadi (biznes qarori: tiyin tangalar 01.03.2020 dan muomalada emas, eng kichik tanga 50 so'm — CBU).» **OS2** → «yopildi (OQ-010); faqat OFD `TotalVAT=ΣVAT` tekshiruvi hamkor bilan tasdiqlanadi». Ogohlantirish 8 — "buxgalter tasdig'i shart" → "buxgalter tanishadi".
  - `01-qarorlar.md` **#26**: "(buxgalter tasdig'i shart — reestr #82)" → «(qonunda yaxlitlash qoidasi yo'q — OQ-010; buxgalter faqat tanishadi)».
  - `26` **B#82**, **A#33** → yopildi.
  - `31-qabul-testlari.md` **#10** va `shared/money-vectors.json`: vektor qo'shiladi — «turli stavkadagi qatorlar (12% va 0%): Σ qator QQS = chek `TotalVAT`, tiyinda».
- **Holat:** **YOPILDI.** Kichik qoldiq: OFD qator/jami QQS mosligini qanday tekshirishi — OQ-009/012 bilan hamkordan so'raladi. Interim: joriy formula, `TotalVAT` faqat Σ qator QQS.

---

## OQ-011 — Virtual kassa dasturini Davlat reyestriga kiritish: bosqichlar, muddat, narx

- **Javob:**
  - **Bosqichlar:** fiskal ma'lumotlar operatori xulosasi (**10 ish kuni**) va Kiberxavfsizlik markazi ekspertizasi (**15 ish kuni**) arizaga **ilova** sifatida oldindan olinadi (parallel so'rashni taqiqlovchi band yo'q); so'ng DSQ ariza kunidan **20 ish kunida** qaror beradi; texnik tartibga solish agentligi va "O'zeltexsanoat" xulosasi (5 ish kuni) shu 20 kun ichida.
  - **Jami:** parallel ≈ 15 + 20 = **35 ish kuni**; to'liq ketma-ket 10 + 15 + 20 = **45 ish kuni**. Hujjat tayyorlash, mualliflik huquqi guvohnomasi, rad etilsa qayta urinish kirmaydi. (Avvalgi "~50 ish kuni" eng yomon baho — 45 ga tushadi.)
  - **Zaxira mablag':** virtual kassa uchun 200 BHM zaxira **talab qilinmaydi** ("виртуал касса бундан мустасно"); 100/500/1000 BHM (4-ilova 8-band) — onlayn-NKM soni bo'yicha; o'z hisob kompleksini virtual kassa sifatida kiritishda soni bo'yicha zaxira "татбиқ этилмайди" (1-ilova 4-band). TXKM zaxirasi (3-ilova 7-band) faqat TXKM bo'lsak.
  - **1 BHM/yil** — reyestr to'lovi **emas**; tadbirkor (kassa foydalanuvchisi) operatorga to'laydigan fiskal modul/VFM xizmati haqi (1-ilova 55-band). BHM 2026-09-01 dan **440 000 so'm** (avval 412 000).
  - **Davlat boji:** VMQ-943 da reyestrga kiritish uchun boj/to'lov bandi topilmadi.
  - **Topilmadi:** KXM ekspertizasi narxi (csec.uz JS), sertifikatlash narxi.
  - **Ziddiyat:** 4-ilova 11-band muvofiqlik sertifikatini faqat «онлайн-НКМга» talab qiladi; 2-ilova 6-band esa virtual kassa talablari ichida «мувофиқлик сертификатларининг мавжудлиги»ni sanaydi.
  - **Muhim:** fiskal qismga tegadigan har o'zgarish operator va KXM'dan **qayta xulosa** talab qiladi (2-ilova 6-band) — reliz siklini rejalashtirishga ta'sir qiladi.
- **Dalil:**
  - VMQ-943 **4-ilova**: **11-band** — «…икки юз баравари миқдоридаги маблағ … захирага қўйилганлиги ҳақидаги маълумот … (виртуал касса бундан мустасно)»; «…операторнинг хулосаси»; «…«Киберхавфсизлик маркази» ДУК томонидан берилган экспертиза хулосаси»; «онлайн-НКМга сертификатлаштириш органи томонидан берилган мувофиқлик сертификати»; «…экспертиза хулосаси ариза келиб тушган кундан бошлаб 15 иш кунидан кечиктирмасдан тақдим этилади». **12-band** — operator xulosasi «ўн иш кунида». **12¹-band** — agentlik va "Ўзэлтехсаноат" «беш иш кунида». **16-band** — «…ариза тақдим этилган кундан бошлаб йигирма иш кунида». **8-band** — «мингтагача … юз баравари; мингтадан беш мингтагача … беш юз баравари; беш мингтадан кўп … бир минг баравари».
  - 1-ilova **4-band 2-xatboshi**: «…ўз автоматлаштирилган ҳисоб юритиш комплексларини виртуал касса сифатида Давлат реестрига киритишда (киритгандан кейин) … рўйхатга олинган виртуал касса сонидан келиб чиқиб, ваколатли органнинг депозит ҳисоб-рақамига захира суммасини қўйиш талаби татбиқ этилмайди.»
  - 1-ilova **55-band** — OQ-007 dalilida.
  - 2-ilova **6-band**: «Фискал маълумотлар, шунингдек, уларни операторга юборишда ўзгартириш ва қўшимчалар киритилган тақдирда оператор ва киберхавфсизлик марказидан қайта хулоса олиниши шарт.»
  - BHM: https://buxgalter.uz/publish/doc/text189777 — 440 000 so'm, 2026-09-01 dan (PF-115; farmon matni lex.uz'da ochilmadi).
- **Ishonch:** muddatlar va zaxira — **yuqori**; parallellik — **o'rta** (taqiq yo'q, amaliyot tasdiqlanmagan); 1 BHM birligi (modul yoki subyekt) — **o'rta**; ekspertiza/sertifikat narxi — topilmadi.
- **Spec'ga ta'sir:**
  - `04-biznes-jarayonlar.md` **OS7**, `05-mvp-chegarasi.md` **§4.3** va **OS4**, `21-integratsiyalar.md` **§13** va **OS4**, `27-backlog.md` **OS2** — "~50 ish kuni / ketma-ket yoki parallel noma'lum" o'rniga: «VMQ-943 4-ilova: operator xulosasi (10 ish kuni, 12-band) va Kiberxavfsizlik markazi ekspertizasi (15 ish kuni, 11-band) arizadan **oldin**, parallel olinadi; DSQ qarori ariza kunidan **20 ish kuni** (16-band), agentlik/"O'zeltexsanoat" 5 ish kuni shu ichida (12¹-band). Reja: **35 ish kuni** (eng yomon 45) + hujjat tayyorlash. Virtual kassa uchun zaxira mablag' talab qilinmaydi (11-band; 1-ilova 4-band). 1 BHM/yil (440 000 so'm, 2026-09-01 dan) — mijoz operatorga to'laydigan fiskal modul haqi (1-ilova 55-band), reyestr narxi emas. Fiskal qismdagi har o'zgarish — qayta xulosa (2-ilova 6-band): fiskal modul kodi alohida, kam o'zgaradigan paket sifatida ajratiladi.»
  - `05` unit-iqtisod: fiskal modul haqi ≈ 440 000 / 12 ≈ **36 700 so'm/oy/kassa** (agar to'lov har modul uchun bo'lsa).
  - `26` **B#25** → yopildi; **B#42** → faqat "ekspertiza/sertifikat narxi, 1 BHM birligi" qismi ochiq.
  - `21` §13 / `26` yangi xavf qatori: 22.10.2026 dan (VMQ-393) 3-ilova 25-band — TXKM reyestrdan chiqarish asosi: «Давлат реестрига киритилган онлайн-НКТларга бошқа турдаги (иккиламчи) … ахборот тизимлари … QR-кодли чек чоп этиш мақсадида интеграция қилинганлиги аниқланганда». "ERP + hamkor kassa" pilot yo'liga ta'siri Xat 1 da so'raladi.
- **Holat:** **QISMAN.** Yopildi: muddat, ketma-ketlik, zaxira, 1 BHM mohiyati. Ochiq: (a) KXM ekspertizasi narxi; (b) virtual kassaga sertifikat shartmi (4-ilova 11-band ↔ 2-ilova 6-band) va narxi; (c) 55-banddagi 1 BHM har modul uchunmi. **Interim:** byudjetda ekspertiza va sertifikat uchun zahira; 1 BHM har kassa uchun; jadval 45 ish kuni bilan. **Kim:** DSQ / "Yangi texnologiyalar" DUK (Xat 1, Xat 10), Kiberxavfsizlik markazi (narx so'rovi), texnik tartibga solish agentligi. Kodga ta'sir yo'q.

---

## OQ-013 — Davlat shakllantirgan hisobotga tuzatish/e'tiroz mexanizmi

- **Javob:**
  - **Kim tuzadi:** soliq organi 6 ta soliq bo'yicha hisobotni avtomatik tuzadi — yuridik shaxslarning mol-mulk solig'i, yer solig'i, JShDS, ijtimoiy soliq, **QQS** va **aylanma solig'i** — va shaxsiy kabinetga joylashtiradi.
  - **Soliq to'lovchi:** kabinetda **tasdiqlaydi** yoki e'tirozi bo'lsa **tuzatish kiritib taqdim etadi**. Alohida e'tiroz arizasi yo'q.
  - **Muddat:** **5 ish kuni** (kalendar emas — SK 5-modda 7-qism), joylashtirilgan kundan keyingi kundan; hisobot topshirish muddatidan oshmaydi.
  - **Javob berilmasa:** rozilik; hisobot topshirish muddati tugagan kuni "taqdim etilgan" hisoblanadi.
  - **Davlat qachon tuzadi** (VM 736 3¹-ilova): QQS — keyingi oyning 15-sanasigacha (topshirish — 20-sana, SK 273-modda); aylanma — 10-sanagacha (topshirish — 15-sana, SK 470-modda).
  - **Oldindan majburiyat:** kabinetdagi interaktiv xizmatga 10-sanagacha kiritiladi — aylanma uchun soliq solinmaydigan daromadlar, chegirmalar, imtiyozlar; QQS uchun hisobga olinadigan QQS tuzatishlari va imtiyozlar.
  - **Muddat o'tgach:** aniqlashtirilgan hisobot — **SK 83-modda** (84-modda emas; 84 — saqlash muddati).
  - **Kanal:** faqat shaxsiy kabinet; soliq maslahatchilari tashkiloti ham kabinet orqali topshira oladi (SK 82-modda 8-qism).
- **Dalil:**
  - SK **81-modda 5–8-qismlar** (O'RQ-1108, 2026-01-01 dan; https://lex.uz/docs/-4674902, https://lex.uz/docs/-7944527 4-modda 5-band). 6-qism: «Soliq organlari tomonidan shakllantirilgan hisobot maʼlumotlari soliq toʻlovchining … hisob hujjatlaridan farq qilganda, soliq toʻlovchi … mazkur hisobotga besh kun ichida, biroq tegishli hisobotni taqdim etish muddatidan kechiktirmasdan tuzatish kiritadi va uni taqdim etadi.» 7-qism: tuzatish kiritilmasa, bu «rozi ekanligini bildiradi va soliq organlari tomonidan shakllantirilgan holda taqdim etilgan deb hisoblanadi». 8-qism: tartibni VM belgilaydi.
  - SK **5-modda 7-qism**: «Kunlar bilan hisoblanadigan muddat, agar bu muddat kalendar kunlar bilan belgilanmagan boʻlsa, ish kunlari bilan hisoblanadi.» 2-qism: muddat voqeadan keyingi kundan boshlanadi.
  - VM №736 **3¹-ilova** (VM №154, 09.04.2026 tahriri; https://lex.uz/docs/-5115911): **11-band** — «Soliq toʻlovchi … besh kun ichida, lekin tegishli soliq hisobotini taqdim qilish muddatidan kechiktirmasdan … shaxsiy kabinetiga yuborilgan (joylashtirilgan) … hisobotlarining toʻgʻriligi va toʻliqligini tasdiqlaydi yoxud eʼtirozlari mavjud boʻlsa, soliq hisobotiga tuzatish kiritadi»; 2-xatboshi — «…tuzatish kiritmagan va (yoki) uni tasdiqlamagan taqdirda, ushbu soliq hisobotini taqdim qilish muddati tugagan kun hisobot tuzilgan va taqdim etilgan deb hisoblanadi». **15-band "a"** — interaktiv ma'lumotlar 10-sanagacha. **13-band** — soliq organi «batafsil tushuntirish berishi shart». **1-band 2-xatboshi** — nizom tashabbusli aniqlashtirilgan hisobotga tatbiq etilmaydi.
  - SK **83-modda**: soliq summasi kamaygan bo'lsa aniqlashtirilgan hisobot majburiy, aks holda huquq; javobgarlikdan ozod bo'lish — tekshiruvdan oldin berish va kam to'langan soliq + penyani oldindan to'lash.
  - SK **82-modda** 12-qism — soliq to'lovchi hisobotga «imzo qoʻyadi»; 8-qism — soliq maslahatchilari tashkiloti «soliq toʻlovchining shaxsiy kabineti orqali».
- **Ishonch:** **yuqori** (mexanizm, muddat, kanal). Imzo aynan E-IMZO ekani — **o'rta** (SK 82 va elektron hujjat talabidan kelib chiqadi; nizomda "E-IMZO" so'zi yo'q).
- **Spec'ga ta'sir:**
  - `03-modullar-talablari.md` **US-M10-02** (huquqiy asos, Given/Then): "5 kalendar kun" → «**5 ish kuni** (SK 5-modda 7-qism), hisobot shaxsiy kabinetga joylashtirilgan kundan keyingi kundan; hisobot topshirish muddatidan oshmaydi (QQS — keyingi oyning 20-sanasi, SK 273-modda; aylanma — 15-sana, SK 470-modda)». *Eslatma* o'rniga: «Mexanizm (VM 736 3¹-ilova 11-band, VM 154 tahriri; SK 81-modda 6–8-qism): my.soliq.uz shaxsiy kabinetida 'tasdiqlash' yoki 'tuzatish kiritib taqdim etish'; alohida e'tiroz arizasi yo'q. Muddat o'tgach — SK 83-modda bo'yicha aniqlashtirilgan hisobot.» `avtomatik qabul qilingan` holati: «hisobot topshirish muddati tugagan kun taqdim etilgan deb hisoblanadi». **OS8** → yopildi.
  - `13-provodka-qoidalari.md` Asosiy xulosa 5 va **§4.3**: "5 kalendar kun" → "5 ish kuni (topshirish muddatigacha)". Hisobotlar ro'yxati: mol-mulk, yer, JShDS, ijtimoiy, QQS, aylanma (foyda solig'i — yo'q).
  - `26` **B#17** → yopildi: «Kanal — faqat shaxsiy kabinet (VM 736 3¹-ilova 10–11-band, SK 81-modda 6–8-qism); avtomatik yuborish yo'q; tizim ichki hisob + farqlar ro'yxatini tayyorlaydi, Buxgalter kabinetda tuzatadi/imzolaydi.»
  - `04` **BP-08** (5a) va **OS9**, `07` **BO-10**, `05` **OS5/§4**, `06` **OS10**: yangi qadam «10-sanagacha interaktiv ma'lumotlar eslatmasi» (aylanma — soliq solinmaydigan daromad, chegirmalar, imtiyozlar; QQS — hisobga olinadigan QQS tuzatishlari, imtiyozlar) — tizim raqamlarni tayyorlab beradi.
  - **OQ-016 (D):** eslatma kunlari 1/3/4 ish kunlari bo'yicha sanaladi va topshirish muddati bilan kesiladi (aylanma uchun real oyna ~10→15-sana).
- **Holat:** **YOPILDI.** Kichik qoldiq: E-IMZO talabi — DSQ (Xat 1) tasdiqlaydi; kodga ta'sir yo'q.

---

## OQ-014 — Davlat hisobotini dasturiy (API) o'qish va granulyarlik

- **Javob:**
  - **Granulyarlik** — rasmiy shakl bo'yicha: **QQS** — davr yig'indilari **va** har hisob-faktura darajasidagi xarid/sotuv reyestrlari (4-ilova: kontragent nomi, STIR, faktura raqami va sanasi, qiymat, QQS). **Aylanma** — faqat **davr yig'indilari**, daromad manbalar bo'yicha: e-faktura (0101), onlayn NKM (0102), marketplace (0103), eksport (0104), boshqa (0105) + stavkalar ustunlari va chegirmalar.
  - **API:** qonun va nizomda yagona kanal — "shaxsiy kabinetga yuborish (joylashtirish)". Uchinchi tomon uchun ochiq/hujjatlashtirilgan API **topilmadi**. my.soliq.uz — SPA; ichki `/api` modullari ("declaration", "choose-operators") E-IMZO sessiyasi bilan ishlaydi va hujjatlashtirilmagan — reverse-engineering huquqiy va texnik xavf.
- **Dalil:**
  - VM 736 3¹-ilova: **3-band** — «Soliq hisobotlarining koʻrsatkichlari ichki va tashqi manbalar maʼlumotlari asosida soliq turlari kesimida shakllantiriladi»; **2-band** ("ichki manbalar") — «elektron hisobvaraq-faktura, onlayn nazorat-kassa texnikasi, elektron toʻlov cheklari, … 'E-imtiyoz'»; **10-band** — «soliq toʻlovchining shaxsiy kabinetiga yuborish (joylashtirish)»; **17-band** — qabul holati «shaxsiy kabineti orqali».
  - SK **273-modda 5-qism**: «Soliq hisobotiga soliq toʻlovchining xaridlar reyestrida va sotuvlar reyestrida koʻrsatilgan maʼlumotlar kiritiladi.»
  - Shakllar — DSQ qarori №3221 ilovalari: https://lex.uz/files/7889495.zip (QQS 1-ilova, 4-ilova reyestrlari), https://lex.uz/files/7889519.zip (aylanma 9-ilova, 0101–0105 satrlar).
  - my.soliq.uz bundle (`main.43e935dd.js`, 2026-10-16) — ommaviy dasturchi API hujjati/havolasi yo'q.
- **Ishonch:** granulyarlik — **yuqori**; "API yo'q" — **o'rta** (salbiy dalil; yopiq operator kanali bo'lishi mumkin).
- **Spec'ga ta'sir:**
  - `26` **B#41**, **A#22**, `09` **OS5/AI-05**, `21` **§8/OS3**, `03` **OS6**, `04` **OS2**: interim yakuniy MVP qarori: «Foydalanuvchi kabinetdan yuklab olingan faylni (PDF/Excel) yuklaydi, AI-05 tushuntiradi; ommaviy API yo'q (VM 736 3¹-ilova 10-band — yagona kanal shaxsiy kabinet). Ichki my.soliq.uz endpoint'lari ishlatilmaydi.»
  - `03` **US-M10-02**, `05` **§4.2**, `06` **OS9**: «QQS — hujjat darajasida (e-faktura reyestri: STIR + faktura raqami + sana bo'yicha moslashtirish) va yig'indi darajasida; aylanma — faqat yig'indi darajasida, manba (e-faktura / NKM / marketplace / eksport / boshqa — 0101–0105) va stavka bo'yicha.» Ichki hisobot ham shu 5 manba bo'yicha bo'linadi (fiskal chek → 0102, e-faktura → 0101).
  - `31` **#13**: «aylanma: 5 manba satri bo'yicha farq ko'rsatiladi; QQS: faktura darajasida mos kelmaganlar ro'yxati».
- **Holat:** **QISMAN.** Granulyarlik yopildi; API topilmadi. **Default:** qo'lda yuklash (interim yakuniy). **Kim:** DSQ (Xat 1: "davlat shakllantirgan hisobotni EDO operatori yoki API orqali olish mumkinmi?").

---

## OQ-015 — Rasmiy hisobot shakllari va topshirish formati

- **Javob:**
  - **Soliq hisobot shakllari:** DSQ 28.01.2020 №2020-03 qarori (AV ro'yxat **№3221**, 24.02.2020; MF bilan kelishilgan). Joriy: **1-ilova — QQS**, **9-ilova — aylanma solig'i**, ikkalasi DSQ 27.10.2025 №2025-20 qarori tahririda (ro'yxat **№3221-8**, 26.11.2025), 2026-01-01 dan. 2-band: o'tgan davr hisoboti o'sha davr shaklida.
  - **Moliyaviy hisobot:** eski MF №140 (2002, ro'yxat №1209) **2025-01-01 dan kuchsiz**. Yangi — Iqtisodiyot va moliya vazirining 08.10.2024 **№181** buyrug'i (ro'yxat **№3567**, 04.11.2024), 2025-01-01 dan: **1-ilova — buxgalteriya balansi**, **2-ilova — moliyaviy natijalar to'g'risida hisobot**; mikrofirma va kichik korxonalar uchun yillik hisobot faqat shu ikkitasi; muddat — 1-mart (BHMS) / 1-may (MHXS). Nizomda choraklik moliyaviy hisobot nazarda tutilmagan.
  - **Topshirish:** «belgilangan shakllar bo'yicha elektron hujjat tarzida» (SK 82-modda 3-qism), imzo bilan. Boshqa shaxs nomidan — faqat soliq maslahatchilari tashkiloti, kabinet orqali (82-modda 8-qism). 9-ilova izohi: «elektron shaklda … shaxsiy kabineti orqali, shu jumladan axborot tizimi orqali».
  - **Tasdiqlanmagan:** XML sxemasi; EDO operatorlari (soliqservis, didox) API orqali topshirish.
- **Dalil:**
  - SK **81-modda 2-qism**: «Soliq hisoboti Oʻzbekiston Respublikasi Davlat soliq qoʻmitasi tomonidan Oʻzbekiston Respublikasi Moliya vazirligi bilan kelishilgan holda tasdiqlanadigan shakllarda tuziladi» (LexUZ sharhi №3221 ga havola).
  - https://lex.uz/docs/-4745555 (№3221, 1-band): «qoʻshilgan qiymat soligʻi boʻyicha 1-ilovaga muvofiq; … aylanmadan olinadigan soliq boʻyicha 9-ilovaga muvofiq».
  - https://lex.uz/docs/-7194594 (MEF №181): **9-band** — «buxgalteriya balansi; … moliyaviy natijalar toʻgʻrisida hisobot; …»; **10-band** — «Mikrofirmalar va kichik korxonalar uchun yillik moliyaviy hisobot buxgalteriya balansi va moliyaviy natijalar toʻgʻrisidagi hisobotni oʻz ichiga oladi»; **7-band** — muddatlar.
  - https://lex.uz/docs/-4200966 — LexUZ sharhi: №140 №181 asosida 2025-01-01 dan kuchsiz.
  - SK **82-modda 3-qism**: «Yuridik shaxs boʻlgan soliq toʻlovchilar va yakka tartibdagi tadbirkorlar soliq hisobotini … belgilangan shakllar boʻyicha elektron hujjat tarzida taqdim etadi.»
- **Ishonch:** shakllar va rekvizitlar — **yuqori**; elektron format va uchinchi tomon kanali — **past**.
- **Spec'ga ta'sir:**
  - `03` **M12 (US-M12-03)** "Davlat tizimlari bog'liqligi": "aniq format talabi ochiq savol" → «Rasmiy shakllar: QQS — DSQ qarori №3221 1-ilova (№3221-8 tahriri, 2026-01-01); aylanma — 9-ilova; moliyaviy hisobot — MEF №181 1- va 2-ilova (kichik korxona, yillik). MVP: rasmiy shakl satr kodlari bilan Excel/PDF **tayyorlov** eksporti (topshirish emas); topshirish — Buxgalter shaxsiy kabinetda.» **M11** — moliyaviy hisobot havolasi MEF №181 ga.
  - `13` **§4**: "№140/1209" havolasi bo'lsa → «MEF №181 (08.10.2024, ro'yxat №3567)»; choraklik moliyaviy hisobot talabi olib tashlanadi (yoki "qonunda yo'q, ichki" deb belgilanadi).
- **Holat:** **QISMAN.** Shakllar yopildi. Ochiq: XML formati va operator API orqali topshirish. **Default:** faqat "tayyorlov" eksporti, topshirishni inson kabinetda bajaradi. **Kim:** DSQ / EDO operatori (soliqservis, didox texnik yordami).

---

## OQ-017 — Aylanma solig'i stavkalari va aholi punkti toifalari (467-modda)

- **Javob:**
  - **Stavkalar** (2026-01-01 dan, O'RQ-1108 tahriri, SK 467-modda 1-qism): umumiy — **4%**; chakana savdo — 100 ming+ aholili shahar **4%**, boshqa aholi punkti **2%**, borish qiyin va tog'li tuman **1%**; tamaki aylanmasi — joyidan qat'i nazar **4%**; YaTT va o'zini o'zi band qilganlar — **1%**. Avvalgi 2–4-qismlar 2026-01-01 dan kuchsiz.
  - **Chegara (461-modda):** yuridik shaxs — soliq davridagi jami daromad 1 mlrd so'mgacha; YaTT — realizatsiya daromadi 1 mlrd so'mgacha.
  - **Oshganda:** QQS va foyda solig'iga «jami daromadi koʻrsatilgan miqdorga yetgan kundan eʼtiboran» (462-modda 7-qism). Rejimga o'tish — keyingi davr boshidan ≥10 kun oldin xabar (462-modda 2-qism).
  - **Yangi istisnolar:** import qiluvchilar (461-modda 2-qism 1-band; import sanasidan QQS — 462-modda 13-qism), zargarlik (15-band).
  - **Hisob/muddat:** turli aholi punktlaridagi savdo nuqtalari bo'yicha alohida hisob majburiy (468-modda 2-qism); davr — oy (469-modda); hisobot va to'lov — keyingi oyning 15-sanasigacha, yillik — 15-fevralgacha (470-modda).
  - **Topilmadi:** "6% ixtiyoriy" rejim — Kodeksda yo'q (467-moddada ham, umumiy matnda ham); borish qiyin va tog'li tumanlarning rasmiy ro'yxati.
- **Dalil** (https://lex.uz/docs/-4674902, 66-bob):
  - **467-modda 1-qism**: «1. Iqtisodiyotning barcha tarmoqlaridagi soliq toʻlovchilar, bundan 2 — 5-bandlarda nazarda tutilganlar mustasno — 4; 2. Chakana savdo sohasidagi soliq toʻlovchilar 2.1. joylashgan joyiga qarab: aholisi soni yuz ming nafar va undan koʻp kishidan iborat shaharlarda — 4; boshqa aholi punktlarida — 2; borish qiyin boʻlgan va togʻli tumanlarda — 1; 2.2. joylashgan joyidan qatʼi nazar, tamaki mahsulotlarini realizatsiya qilishdan tovar aylanmasi boʻyicha — 4; … 5. Yakka tartibdagi tadbirkorlar va oʻzini oʻzi band qilgan shaxslar — 1». **5-qism**: «ikkinchi, uchinchi va toʻrtinchi qismlarining qoidalari 2026-yil 1-yanvardan eʼtiboran oʻz kuchini yoʻqotgan».
  - **461-modda 1-qism**: «1) soliq davrida jami daromadi bir milliard soʻmdan oshmagan … yuridik shaxslari; 2) … realizatsiya qilishdan olingan daromadi bir milliard soʻmdan oshmagan yakka tartibdagi tadbirkorlar va oʻzini oʻzi band qilgan shaxslar».
  - **468-modda 2-qism**: «… chakana savdo sohasidagi … turli aholi punktlarida joylashgan bir qancha savdo nuqtalariga ega soliq toʻlovchilarga nisbatan ham qoʻllaniladi.»
  - **470-modda 3-qism**: «hisobot davridan keyingi oyning oʻn beshinchi kunidan kechiktirmay; … 15-fevralidan kechiktirmay».
- **Ishonch:** stavkalar va chegara — **yuqori** (Kodeks matni so'zma-so'z); tog'li tumanlar ro'yxati — topilmadi.
- **Spec'ga ta'sir:**
  - `01` **#11**, `13` ogohlantirish 9 va **§4.3**, `03` US-M10-04 / **M14** chekka holatlar, `11`/`12` `settlement_category` — **seed tasdiqlandi**: `city_100k_plus`=4, `other`=2, `remote_mountain`=1; qo'shimcha seed qatorlari: `tobacco`=4 (joyidan qat'i nazar), `individual_entrepreneur`=1, `general_non_retail`=4. "Taxmin" belgisi olib tashlanadi, manba: SK 467-modda 1-qism (O'RQ-1108).
  - `13` **§4.3** qo'shimcha: «461-modda 2-qism 1-band: import qiluvchi aylanma solig'i to'lovchisi bo'la olmaydi — import sanasidan QQS (462-modda 13-qism) → rejim o'zgarishi ogohlantirishi; 1 mlrd chegaraga yetgan **kundan** QQS (462-modda 7-qism) → `tenant_tax_regimes` oy o'rtasida o'zgarishi mumkin (`effective_from` — sana, oy emas). Bir nechta aholi punktidagi filiallar — alohida hisob (468-modda 2-qism) → `branch_tax_settings` bo'yicha alohida aylanma.» ⚠ Bu §4.3 dagi "rejim faqat oy boshidan o'zgaradi" qoidasiga **zid** — buxgalter tasdig'i kerak.
  - `03` **M14** chekka holat: «YaTT tamaki sotsa — 1% (5-band) yoki 4% (2.2-band)? — ochiq, buxgalterga; interim 4%».
  - `13` Asosiy xulosa 5 (va `research_notes/texnik` dagi "1-iyundan ixtiyoriy 6%") — Kodeksdan tasdiqlanmadi → "manba kerak" belgisi.
  - Tog'li/borish qiyin tuman — `branch_tax_settings.settlement_category` ni Egasi tanlaydi (ro'yxat seed qilinmaydi).
- **Holat:** **YOPILDI** (stavkalar, chegara, alohida hisob). Qoldiqlar (bloklamaydi): (1) tog'li tumanlar rasmiy ro'yxati — Egasi tanlaydi; (2) YaTT + tamaki to'qnashuvi — buxgalter, interim 4%; (3) rejimning oy o'rtasida o'zgarishi — buxgalter.

---

## OQ-018 — Faqat elektron chek (qog'ozsiz: QR/Telegram/SMS) qonuniymi

- **Javob:** Normalar elektron chekni **taqiqlamaydi**, lekin do'kondagi savdo uchun "faqat elektron chek yetarli" degan **aniq ruxsat hozir yo'q**.
  - "Kassa cheki" ta'rifi elektron shaklni o'z ichiga oladi; virtual kassa ta'rifida "chop etish **yoki** elektron shaklda yuborish".
  - 2022 tahririda do'kondagi elektron to'lov uchun «виртуал кассанинг электрон чеки» to'g'ridan-to'g'ri ruxsat etilgan edi; **VMQ-23 (23.01.2026) bu so'zlarni 6-banddan olib tashladi** — endi neytral «фискал чеки».
  - Elektron yetkazish yo'li (telefon, e-mail, kabinetga havola) aniq faqat Marketplace uchun yozilgan (1a-ilova 8-band).
  - Chakana savdo qoidalari: «харид билан биргаликда касса чекини бериши шарт» — shakl ko'rsatilmagan.
  - Xaridor roziligi talabi normada **topilmadi**.
- **Dalil** (VMQ-943, https://lex.uz/docs/4603329):
  - 1-ilova **2-band**: «касса чеки — … онлайн-НКМ ёки виртуал кассада … шакллантирилган ва **электрон шаклда ёки қоғозда чоп этилган** … бирламчи ҳисоб ҳужжати»; «виртуал касса — … **чекларни қоғозга чоп этиш ёки уларни электрон шаклда юбориш** функциясига эга бўлган дастурий маҳсулот».
  - 1-ilova **6-band**, eski tahrir (VMQ-255, 13.05.2022; https://lex.uz/docs/4603329?ONDATE=13.05.2022): «…онлайн-НКМ ёки виртуал касса чеки **ёки виртуал кассанинг электрон чеки** берилиши шарт.» Joriy (VMQ-23, 23.01.2026): «…онлайн-НКМ ёки виртуал кассанинг **фискал чеки** берилиши шарт.»
  - 1-ilova **7-band** — qog'oz talabi faqat bosma chekka: «махсус оқ қоғозда … кенглиги 55 миллиметрдан … кам бўлмаслиги лозим».
  - **1a-ilova 8-band**: «Маркетплейс орқали харид чеки электрон шаклда тақдим этилганда, … ҳаволасини харидор кўрсатган абонент рақамига ёки электрон почта манзилига, ёхуд … шахсий кабинетига юборишини таъминлайди.»; 9-band: «…чек қоғоз шаклда тақдим этилган тақдирда…».
  - VMQ-75 (13.02.2003) chakana savdo qoidalari **23-band** (https://lex.uz/docs/243235): «Сотувчи-ходим харидорга харид билан биргаликда касса чекини … бериши шарт».
  - SK **221-modda 1-qism**: chek bermaslik — 5 mln so'm jarima.
  - Ikkilamchi: buxgalter.uz, 18.05.2022 (https://buxgalter.uz/publish/doc/text181462): «в соответствии с п. 6 Положения обязательно нужно было выдавать именно распечатанный чек. Теперь можно выдать и только электронный. Это нововведение связано с дистанционными платежами…» (VMQ-23 dan oldin yozilgan). gov.uz/ru/soliq/news/view/18339 (08.08.2024): «выдавать покупателям чек с QR-кодом и фискальной отметкой».
  - Tekshirilmadi: Iste'molchilar huquqlarini himoya qilish qonuni (lex.uz ID topilmadi), MJtK chek bermaslik moddasi, ofd.soliq.uz QR tekshiruv sahifasi.
- **Ishonch:** **o'rta** — ta'riflar elektron chekka joy qoldiradi, lekin 2026 yilda aniq ruxsat olib tashlangan; nazorat xaridida "qog'oz chek berilmadi" talqini xavfi bor.
- **Spec'ga ta'sir:**
  - `26` **B#11** (huquqiy qism), `01-qarorlar.md` **#21** "⚠ Ochiq", `24-frontend-arxitekturasi.md` **§6/OS1**, `25-nofunksional-talablar.md` **§7.2/OS6**, `27-backlog.md` **OS3**, `03` **OS13/M01**, `06` **OS12** va **§1.6**: «Elektron chek huquqan chek hisoblanadi (VMQ-943 1-ilova 2-band: 'электрон шаклда ёки қоғозда'; virtual kassa — 'чоп этиш ёки электрон шаклда юбориш'). Ammo do'kondagi savdo uchun 'faqat elektron' ruxsati 23.01.2026 tahririda (VMQ-23) 6-banddan olib tashlangan. Shuning uchun **standart — bosma chek**, iOS'da asosiy yo'l — bulut printer. Elektron chek (ekranda `ofd.soliq.uz` QR havolasi, Telegram yoki SMS havola) faqat (a) printer ishlamay qolganda yoki (b) xaridor o'zi so'raganda, kassir tasdig'i bilan zahira; `fiscal_receipts.delivery = electronic` + sabab audit qilinadi. Yakuniy tasdiq — DSQ (Xat 1).»
  - `06` **§1.6** / `08` xabar #27: "QR orqali elektron chek muqobili — **taxmin**, manbada yo'q" → «manba: VMQ-943 1-ilova 2-band (chek elektron shaklda bo'lishi mumkin); faqat zahira».
  - `11`/`12` `fiscal_receipts`: `delivery TEXT CHECK (delivery IN ('printed','electronic'))`, `delivery_reason TEXT`.
- **Holat:** **QISMAN.** Qolgani: do'kon savdosida qog'ozsiz chekka rasmiy ruxsat. **Interim:** "standart — bosma, elektron — zahira"; iOS'da printer bo'lmasa "faqat elektron" rejimi ogohlantirish bilan. **Kim:** DSQ / "Yangi texnologiyalar" DUK (Xat 1 ga savol qo'shilsin) va yurist (Iste'molchilar qonuni, MJtK moddasi).

---

## Qo'shimcha topilmalar (P1 qamrovidan tashqari, spec'ga ta'sir qiladi — tekshirib qo'shish tavsiya etiladi)

1. **Karta/QR to'lovlarni kassaga majburiy integratsiya.** VMQ-943 1-ilova 6-band 2-xatboshi (VMQ-23): «Давлат реестрига киритилган онлайн-НКМ ва виртуал кассалар банк карталаридан тўловларни қабул қилиш тизимларига мажбурий уланиши…»; 2-ilova 6-band (virtual kassa texnik talablari, VMQ-393, 21.07.2026): «барча банк карталари ва QR-кодлар орқали тўловларни тўғридан-тўғри шу қурилма орқали қабул қилиш имконияти»; «банкларда генерация қилинган ягона QR-кодни шакллантириш ахборот тизими ҳамда электрон тўлов тизимларига мажбурий уланиши». → `21` §9.2 ("karta — qo'lda belgilash, integratsiyasiz") va reyestrga kirish talablariga bevosita ta'sir. **Yangi ochiq savol (P3 + yurist/DSQ):** virtual kassa sifatida reyestrga kirish uchun karta-ekvayring va UzQR integratsiyasi qaysi bosqichda majburiy.
2. **To'lov shakli 22.10.2026 dan** — "naqd, bank kartalari, QR-kodli to'lov yoki aralash" (1-ilova 7-band, VMQ-393) → chek shabloni va `payment_form` enum'iga `qr` (OQ-009 da kiritilgan).
3. **QR-kodsiz chek bosish** (3-ilova 25-band, VMQ-393, 22.10.2026 dan) TXKM'ga chora asosi; shu bilan birga 7-band "bo'nak, bo'lib to'lash, kredit" cheklarida QR va fiskal belgi bo'lmaydi → `01 #30` va OQ-002 bilan solishtirilsin.
4. **Ikkilamchi tizimlar** — 1-ilova 4-band yangi tahriri (22.10.2026 dan) soliq tizimiga integratsiyalanmagan avtomatlashtirilgan hisob tizimlari bilan ishlashni taqiqlaydi (aniq **umumiy ovqatlanish** uchun); 3-ilova 25-band — reyestrdagi onlayn-NKT'larga "ikkilamchi" axborot tizimlarini QR chek chop etish uchun integratsiya qilish TXKM'ni reyestrdan chiqarish asosi. → "ERP + hamkor kassa" pilot modeli (`21` §13) uchun **xavf**; Xat 1 da aniq so'ralsin.
5. **Fiskal qism o'zgarsa qayta xulosa** (2-ilova 6-band) → arxitektura: fiskal modul kodini alohida, kam o'zgaradigan paket/servis sifatida ajratish (`23` backend arxitekturasi).
6. **Jarimalar (SK 221-modda, O'RQ-1108):** 1-qism — chek bermaslik / QR to'lovni rad etish 5 mln so'm; 2-qism — ro'yxatdan o'tmagan kassa; 4-qism — texnik talabga mos bo'lmagan KKT 20 mln so'm. `15`/`25` xavf bo'limlariga havola sifatida.

## Kesishmalar
- OQ-004 → **OQ-005 (D)** tavsiyasi o'zgaradi (46 soat — "bloklanadi" ogohlantirishi; 48 soat — blok).
- OQ-013 → **OQ-016 (D)** eslatma kunlari ish kunlarida.
- OQ-002, 009, 010 → **OQ-012 (E)** hamkor spetsifikatsiyasi bilan tasdiqlanadi (chek turi kodi, tiyin, `PackageCode`, `TotalVAT`).
- OQ-001 → **P3** (Payme/Uzum "joyida to'lov" kassasida ikki marta fiskallashtirmaslik).
- OQ-011, 014, 015, 018 va qo'shimcha topilma 1, 4 → **Xat 1** (DSQ) savollar ro'yxatiga qo'shilsin.

## Tekshirib bo'lmagan / cheklovlar
- WebSearch kvotasi tugagan; Bing/DuckDuckGo qisman ishladi — buxgalter.uz/norma.uz'dagi ayrim Q&A topilmadi.
- Payme `detail`, Uzum fiskalizatsiya, csec.uz narxlar, my.soliq.uz va gov.uz reyestr sahifalari — JS/SPA, o'qilmadi.
- OFD rasmiy JSON protokoli ommaviy emas — tiyin/`PackageCode` dalillari ochiq kod va vendor hujjatlaridan.
- SK 221-modda o'zbekcha rasmiy matni (ruscha norasmiy tarjimadan iqtibos), PF-115 (BHM) asl matni, MJtK 175-modda qism raqami (lex.uz tartibi bo'yicha sanalgan), SK 297-modda qism raqami (2026 qo'shimchalaridan keyin siljigan) — mustaqil tasdiqlanmadi.
- Iste'molchilar huquqlarini himoya qilish qonuni matni ochilmadi.
