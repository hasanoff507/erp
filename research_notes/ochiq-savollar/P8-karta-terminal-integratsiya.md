# P8 — Bank karta terminalini kassaga integratsiya qilish (POS → terminal → natija)

Sana: 2026-10-16. Holat: **tadqiqot yakunlandi; texnik protokol hamkordan kutiladi**. Spec fayllari tahrirlanmagan — pastda taklif qilingan qaror (#71) va o'zgartirishlar ro'yxati.

**Asoschi talabi.** Karta to'lovida kassir karta raqami / RRN'ni **qo'lda kiritmaydi**: POS summani do'kondagi bank terminaliga (Uzcard/Humo/Visa/Mastercard) yuboradi va natijani avtomatik oladi. Terminal kabel bilan emas, **tarmoq orqali (Wi-Fi/LAN)** ulanadi.

**Metod.** WebSearch kvotasi tugagan edi, shuning uchun Google qidiruvi Playwright orqali qilindi va sahifalar to'g'ridan-to'g'ri o'qildi. Me'yoriy hujjatlar lex.uz'dan o'qildi (o'zbek kirill rasmiy matni). Uchta mustaqil yo'nalish tekshirildi: (A) lokal ECR protokollari, (B) bulut API / Android smart-terminal / SoftPOS, (C) huquqiy talablar.

---

## 0. Qisqa xulosa

1. **O'zbekistonda POS → bank terminali uchun ochiq, yagona ECR standarti yo'q.** "Uzcard ECR", "Humo ECR" yoki biror bankning ommaviy protokol hujjati topilmadi. Har integratsiya terminalga to'lov ilovasini o'rnatgan tomon bilan (bank, ARCA/ERA, Rahmat, Smart Business/CDTI, SmartOne, mkassa) **shartnoma/NDA asosida** qilinadi. Ishonch: yuqori.
2. **Bulut API ("terminal ID bo'yicha xaridni yuborish", Stripe Terminal/Adyen Cloud modeli) — ommaviy holda yo'q.** Click, Payme, Uzum, Atmos, Octo, GlobalPay, Multicard, Paynet API'lari faqat e-commerce, QR yoki hamyon uchun. Eng yaqin nomzod — ERA (Arca Group) "ERP moduli" HTTPS API'si. Lekin u fiskalizatsiya va sotuv sinxronizatsiyasi uchun ta'riflangan; karta to'lovini tashqaridan boshlash imkoni tasdiqlanmagan. Ishonch: o'rta-yuqori.
3. **Wi-Fi talabi amalda faqat Android smart-terminallar bilan bajariladi.** Bular Sunmi P2/P3, PAX A930/A930 RTX/A910S, SmartOne P1000/P2000L, NEXGO N82 va A-PAY P10 bo'lib, Uzcard/Humo saytlarida ro'yxatda. Humo'ning "kassa integratsiyasi uchun" Smart PIN Pad'i — Ingenico Lane/3600 — faqat Ethernet/USB/RS232 bilan ishlaydi. Humo, Rahmat va NEXGO o'z qurilmalarini "Open API orqali integratsiya" bilan reklama qiladi, lekin hujjat ommaviy emas. Ishonch: yuqori (mavjudlik), past (API tafsiloti).
4. **SoftPOS mavjud, lekin hozircha kichik.** MARTA (MayaSoft) — Ipoteka, Asaka, Anor va boshqa banklarda ishlaydi. MayaSoft'da uchinchi tomon Android ilovasiga qo'yiladigan **SoftPOS SDK** bor ("so'rov bo'yicha"). TBC SoftPOS esa BILLZ POS ichiga qurilgan — bu raqobatchi. Uzcard SoftPOS hajmi 2025 yilda 9 mlrd so'mdan oshgan. Ishonch: yuqori.
5. **Huquqiy holat.** Har bir do'konda integratsiyalangan terminal **majburiy emas**: VMQ-943 1-ilova 6-band "terminal cheki + kassa fiskal cheki" modelini to'g'ridan-to'g'ri nazarda tutadi. Ammo **VMQ-393 (21.07.2026 dan)** virtual kassa va onlayn-NKM **mahsulotiga** quyidagi texnik talabni qo'ydi: *"barcha bank kartalari va QR-kodlar orqali to'lovlarni to'g'ridan-to'g'ri shu qurilma orqali qabul qilish imkoniyati"*. Unga mos kelmaslik — modelni reyestrdan chiqarish asosi (22.10.2026 dan). Shuning uchun **o'z virtual kassamiz reyestrga kirishi uchun integratsiyalangan karta qabul qilish funksiyasi kerak bo'ladi**. Ishonch: o'rta-yuqori (~75%).
6. **Tavsiya.** Kodda `CardTerminalPort` (bitta kontrakt) bo'lsin, unga bir nechta adapter ulanadi. Asosiy yo'l — **Do'kon agenti (#60) orqali LAN/Wi-Fi'dagi terminal** (Windows PK + veb-kassa), Android POS'da — **intent/SDK adapteri**, bulut adapteri — faqat hamkor taqdim etsa. MVP'da `FakeCardTerminalAdapter` va mavjud qo'lda kiritish (#64) qoladi. Birinchi real adapter — birinchi hamkor bilan shartnoma tuzilgach. Kassa birinchi bo'lib **Sunmi P3 (Rahmat/Humo)** va **PAX A930 (ERA/Uzcard)** bilan sinab ko'riladi. Terminal javob bermasa qo'lda kiritish qonuniy zaxira sifatida qoladi, lekin `card_entry_mode='manual'` bilan belgilanadi va standart bo'yicha **menejer tasdig'i** talab qilinadi.

---

## 1. Integratsiya usullari (O'zbekiston bozori)

### 1(a) Lokal tarmoq ECR protokoli (TCP/IP, Wi-Fi/LAN)

| Protokol | Transport | O'zbekistonda | Manba | Ishonch |
|---|---|---|---|---|
| **Arcus2** (Ingenico; `cashreg.dll`/`cashreg.ini`) | COM/USB yoki Ethernet (`PORT=ETH`, `ADDR_IP`; terminalda Interface → ETH menyusi) | **Ehtimoliy, tasdiqlanmagan.** Rus o'rnatish yo'riqnomalarida host protokoli sifatida "SmartVista" tanlanadi — Uzcard yadrosi ham BPC SmartVista. Humo'ning Ingenico PIN-pad'lari shunga ishora qiladi, lekin O'zbekiston hujjatida Arcus2 nomi uchramadi | docs.artix.su (Arcus2 CAP PDF), kb.gbsmarket.ru, positron.pro, docs.jupiter.systems | past-o'rta |
| **INPAS DualConnector / SA** | Windows COM / DC Service; Ethernet; PAX D200 Wi-Fi orqali (rarus.ru forumi) | O'zbekistonda dalil yo'q (Rossiya) | rarus.ru, docs.rkeeper.ru | past |
| **UCS EFTPOS** | TCP | Dalil yo'q | docs.rkeeper.ru, wiki.ccrs.ru | past |
| **PAX POSLink** | TCP/HTTP, standart port 10009, Ethernet/Wi-Fi | Dalil yo'q — O'zbekistondagi PAX'larda bank/ERA ilovasi turadi | help.petrosoftinc.com | past |
| **Sunmi semi-integrated payment SDK** | Android Service / **TCP/IP** / USB / "POSTMAN" | Humo Sunmi qurilmalari uchun dolzarb, lekin faqat bank o'rnatgan to'lov ilovasi buni ochsa | blog.rospertech.com | past |
| Sber UPOS, Ingenico Telium Caisse/Concert, Verifone ECR-over-IP, OPI | — | O'zbekistonda topilmadi | — | — |

**Uzbek integratorlar amalda nima qiladi (har biri o'z protokoli bilan):**
- **Venkon + Rahmat POS** (2026-08): 1C:Розница 3.0 summani Rahmat POS terminaliga avtomatik yuboradi va tasdiq kassaga qaytadi. Transport oshkor qilinmagan. Rahmat yana SetRetail, iiko, R-Keeper, МойСклад, 1C:УТ va Artix bilan integratsiyani ro'yxatga kiritgan — https://www.gazeta.uz/ru/2026/08/06/rahmat/, https://rhmt.uz/pos/integration (mavjudlik — yuqori, mexanizm — o'rta).
- **Smart Business P10**: "API orqali integratsiya tufayli P10 terminalini virtual kassangiz yoki POS tizimingizga ulashingiz mumkin" (Facebook, 2025-07-15). API ommaviy emas — o'rta.
- **ARCA/ERA**: 1C, iiko, Hippo, Poster, Jowi va Posware bilan bepul integratsiya (gazeta.uz, 2023-12-22). Smartup ↔ ARCA integratsiyasi lokal tarmoq orqali emas, **bulut xosti** (`gate-t.tinda.uz`) orqali — smartup-doc.tilda.ws — o'rta.
- **Xulosa**: O'zbekistondagi "terminal + kassa" qurilmalari ko'proq **vendor bulut/vendor API** orqali integratsiya qilinadi, lokal ECR soketi orqali emas. Bitta standart emas, **bir nechta adapter**ga tayyorlanish kerak.

**Xabar formati**: O'zbekistonga xos format topilmadi. Arcus2/INPAS — xususiy binar/TLV, POSLink — ajratuvchili maydonlar. Barchasi Rossiya yoki AQSh hujjatlaridan.

### 1(b) Bank/protsessing bulut API'si

**Topilmadi.** Tekshirilganlar:
- **ATMOS** — https://docs.atmos.uz/ : `terminal_id` — e-com identifikatori, jismoniy terminal emas.
- **Click Terminal** — https://click.uz/ru/click-terminal : "virtual hisob-kitob terminali" (USSD/ilova/QR/invoys), karta o'qilmaydi.
- **Payme Business** — https://developer.help.paycom.uz/metody-merchant-api : faqat onlayn/hamyon.
- **Uzum** — https://developer.uzumbank.uz : kassa uchun faqat QR (FastPay, Dynamic QR).
- **Octo** (products.octo.uz), **GlobalPay** (docs.globalpay.uz/api), **Multicard** (docs.multicard.uz), **Paynet** (paynet.uz/developer-guide; tms.paynet.uz — faqat o'z kiosklari).
- **ERA (Arca Group)** "ERP moduli" — https://pos.era.uz/ru/erp : buxgalteriya tizimi ↔ PAX A930/A930 RTX/A910S'dagi ERA onlayn-kassa o'rtasida HTTPS API (token, login/parol yoki API kalit). Fiskalizatsiya va sotuv/qaytarish sinxronizatsiyasi uchun ta'riflangan; **karta to'lovini tashqaridan boshlash va RRN/avtorizatsiya kodini olish imkoni ko'rsatilmagan**. Bulut → terminal yo'lining eng yaqin nomzodi, so'rov yuborish kerak. Mavjudlik — o'rta, karta-push — past.
- **Uzcard terminal integratsiyasi sahifasi** — https://uzcard.uz/business?tab=3 : bu sahifa POS dasturi uchun emas, **terminal ishlab chiqaruvchisi/vendor** uchun sertifikatlash tartibini beradi (EMV L1/L2, kontaktsiz yadrolar, BPC SmartVista muvofiqlik sertifikati, PA-DSS, PCI PIN, namuna qurilma, ЕОПЦ bilan shartnoma, test). Demak "terminal + API" mahsulotini amalda faqat ekvayer-vendor (Arca, Rahmat va h.k.) qura oladi. Ishonch — yuqori.
- Xorijiy namuna (O'zbekiston emas): **Kaspi Smart POS** (Qozog'iston) — kassa mijoz sifatida HTTPS API'ga murojaat qiladi; iiko plagini terminaldagi **lokal HTTP-server**ga (port 8080) ulanadi (guide.kaspi.kz, pos-plugin.kz). Uzbek vendorlardan aynan shu modelni so'rash kerak.

### 1(c) Android smart-terminal (bizning POS ilovasi shu qurilmada yoki shu LAN'da)

- **Uzcard** taklif qiladigan qurilmalar: PAX A930 RTX (Android 12, Wi-Fi/4G), A930, A910S, A35 (Android PIN-pad), IM30, A-PAY P10 ("POS terminal + onlayn kassa 2-in-1"). 260 mingdan ortiq POS. Arca bilan "Kassa bez zabot" aksiyasi (2026-06-01 — 07-31) — https://uzcard.uz/business?tab=2, https://uzcard.uz/news/uzcard_and_arca_group_comprehensive_solutions (yuqori).
- **Humo (НМПЦ)** — https://humocard.uz/ru/business/terminals/ :
  - Ingenico Lane/3600 — "Smart PIN Pad", kassa integratsiyasi uchun; Ethernet/USB/RS232, **Wi-Fi yo'q**.
  - Sunmi P3/P3H/P2/P2 PRO/P2 SMARTPAD — Wi-Fi/BT/LAN, "POS tizimlari bilan integratsiya mumkin".
  - SmartOne P1000/P2000L (smartone.uz).
  - Aisino A90 (m4bank).
  - **NEXGO N82** — "Tasnif, OFD, 1C, shuningdek **ochiq API** orqali integratsiya" (mkassa.uz).
  - 2025-12 dan Sunmi P3'ni sotadi/ijaraga beradi, Poster va МойСклад bilan "va Open API orqali boshqa tizimlar bilan" integratsiya (https://www.spot.uz/ru/2025/12/24/humo/).
  - Ishonch: yuqori (mavjudlik).
- **Rahmat POS (Sunmi P3)** — https://rhmt.uz/pos/ :
  - narxlar: qurilma 990 000 so'm; faqat to'lov terminali 0 so'm/oy; onlayn kassa 100 000 so'm/oy; virtual kassa 123 600 so'm/oy;
  - "ochiq API tufayli mashhur POS tizimlari bilan integratsiya".
  - Ishonch: yuqori.
- **Ipoteka** — PAX A930 RTX (https://www.ipotekabank.uz/cash-services/acquiring); **Kapitalbank** — PAX A930 onlayn kassa sifatida (o'rta).
- **Agrobank 2026 tenderi** (2 500 ijara terminal): Android, Wi-Fi 2.4 GHz, 4G, ichki onlayn kassa talab qilingan. **ECR interfeysi talabi yo'q** (agrobank.uz, "ТЗ_Агробанк терминалы.pdf") — yuqori.
- **Android Intent/AIDL** (bank to'lov ilovasi ↔ shu qurilmadagi uchinchi tomon ilovasi): **birorta Uzbek bank/vendor uchun ommaviy spetsifikatsiya topilmadi**. Terminallarda ekvayer yoki vendor ilovasi (ERA, Rahmat, SmartOne, mkassa) turadi. Kirish — shartnoma bo'yicha xususiy integratsiya. Ishonch: o'rta-yuqori.
- **Multikassa** virtual kassa protokoli — https://docs-virtual-kassa.multibank.uz/ : lokal REST (`localhost:8080/api/v1`), "Электронные платежные системы" bo'limi bor. Karta terminali metodlari ko'rinmadi — o'rta.
- **bss.uz** qo'llanmasi (2026-09-29) ikki texnik variantni ajratadi: terminal va FM birlashgan "smart kassa" yoki "kassa + alohida terminal, protokol bilan almashuv" — https://www.bss.uz/article/4805-kassa-v-uzbekistane-kak-vybrat-kupit-i-primenyat-onlayn-kkm-v-2026-godu

### 1(d) SoftPOS / Tap-to-Phone

- **Bozor hajmi** — Uzcard SoftPOS: 2025 yilda >9 mlrd so'm (2024 ga nisbatan 20 baravar), lekin bozorning "juda kichik ulushi". Faqat NFC'li Android. Ulushlar: Anor 74%, Ipoteka 9%, Hamkor 7% — https://uzcard.uz/news/uzcard_softpos (2026-01-29) — yuqori.
- **MARTA (MayaSoft)** — Ipoteka (OTP), Asaka, Orient Finans, Ipak Yo'li va boshqalar. Ichida fiskalizatsiya uchun virtual kassa bor. Komissiyalar:
  - Ipoteka: Uzcard/Humo 0,3%, Visa/MC 1%, ulanish bepul (https://www.ipotekabank.uz/ru/business/acquiring/softpos/, 2026-06-24);
  - Asaka: 0,3% / 1,5% (https://asakabank.uz/ru/small-business/acquiring/marta-softpos-terminal-v-vashem-smartfone).
  - Ishonch: yuqori.
- **MayaSoft SoftPOS SDK** — https://mayasoft.uz/ : Android savdo ilovasiga kontaktsiz karta qabul qilishni joylashtiradi (test ilovasi, attestatsiya, fiskalizatsiya ssenariylari, "so'rov bo'yicha"). Banklar/PSP/fintechlarga mo'ljallangan, shuning uchun bizga **hamkor bank yoki PSP** kerak bo'ladi. Kotlin POS uchun eng aniq yo'l. Narx/shartlar noma'lum.
- **TBC Bank UZ** — SoftPOS **BILLZ POS ilovasi ichida** (TBC Biznes hisobi). Komissiyalar: TBC Salom 0%, Humo/Uzcard 0,4%, Visa/MC 1,4% — https://tbcbank.uz/ru/business/product/soft-pos/. TBC 2025-06 da BILLZ'ning 53% ulushini olgan (https://www.gazeta.uz/2025/06/27/tbc-billz). Bu karta qabul qilish uchinchi tomon POS ilovasiga qurilgan **yagona topilgan holat**, va u raqobatchi.
- Uzum Tap, Humo brendli SoftPOS va CBU'ning SoftPOS'ga xos qoidalari topilmadi.

---

## 2. Banklar/terminallar va kirish tartibi

| Kim | Qurilma | Integratsiya kanali | Kirish | Narx/komissiya |
|---|---|---|---|---|
| Arca Group / ERA (Uzcard, Kapitalbank, Ipoteka) | PAX A930/A930 RTX/A910S | ERA "ERP moduli" HTTPS API (karta-push — tasdiqlanmagan) | Arca bilan shartnoma; 1C/iiko integratsiyasi pretsedent | topilmadi |
| Rahmat (Multicard) | Sunmi P3 | "Ochiq API" (yopiq hujjat), 1C/iiko/R-Keeper tayyor | 1865, shartnoma | terminal 0 so'm/oy, qurilma 990 000; onlayn kassa 100 000/oy |
| Humo (НМПЦ) | Sunmi P2/P3, NEXGO N82, Ingenico Lane/3600 | "Open API" (yopiq); Lane/3600 — LAN/USB ECR | +998 78 113 24 07 | topilmadi |
| Smart Business (CDTI) | A-PAY P10, UZKASSA N5 | API (yopiq) | smart-ecosystem.uz qo'llab-quvvatlash | qurilma 1,95–3,3 mln so'm (texnik/06) |
| SmartOne | P1000/P2000L | noma'lum | smartone.uz | topilmadi |
| MayaSoft | Har qanday NFC Android | SoftPOS SDK | hamkor bank/PSP orqali | 0,3% / 1–1,5% (bank tarifi) |
| Hamkorbank | ijara terminal | ECR — topilmadi | — | "0,2% dan" (hamkorbank.uz/rental-trading-terminals) |
| Uzcard (vendor sertifikati) | — | terminal vendori uchun, POS uchun emas | ariza, namuna, ЕОПЦ shartnomasi, test | e'lon qilinmagan |

**Bizning kirish yo'limiz**: ECR/API interfeysi terminalga to'lov ilovasini o'rnatgan tomonga tegishli. Shuning uchun u bilan **hamkorlik shartnomasi + NDA + qabul testi** kerak bo'ladi. Ommaviy narx yoki NDA shabloni topilmadi.

---

## 3. Huquqiy tahlil

### 3.1 Iqtiboslar

**VMQ-943 1-ilova 6-band, 1-xatboshi** (amalda) — https://lex.uz/docs/4603329 :
> «Онлайн-НКМ ёки виртуал кассадан фойдаланишга ўтган тадбиркорлик субъектлари томонидан тўлов терминали орқали қабул қилинган тўловлар учун харидорларга тўлов терминали чеки билан бирга, … онлайн-НКМ ёки виртуал кассанинг фискал чеки берилиши шарт.»

Tarjima: terminal orqali qabul qilingan to'lovga terminal cheki **bilan birga** fiskal chek beriladi. Bu mustaqil terminal modelini qonuniy deb biladi.

**Xuddi shu 6-band, 2-xatboshi** (VMQ-23, 23.01.2026 tahriri):
> «Давлат реестрига киритилган онлайн-НКМ ва виртуал кассалар банк карталаридан тўловларни қабул қилиш тизимларига мажбурий уланиши, шунингдек, мажбурий равишда 2D сканер қурилмаси қўлланиши шарт.»

Tarjima: reyestrdagi kassalar karta qabul qilish tizimlariga **majburiy ulanishi** shart. Matn ikki xil o'qiladi (pastdagi talqinga qarang).

**VMQ-393 (20.07.2026), 1-ilova 14-band "в"** — VMQ-943 2-ilova (texnik talablar), 3-band 13-xatboshi (onlayn-NKM) va 6-band 10-xatboshi (virtual kassa) — https://lex.uz/docs/8343102 :
> «барча банк карталари ва QR-кодлар орқали тўловларни тўғридан-тўғри шу қурилма орқали қабул қилиш имконияти»

Tarjima: barcha karta va QR to'lovlarini "to'g'ridan-to'g'ri shu qurilma orqali" qabul qilish **imkoniyati**. Avvalgi tahrir faqat «банк карталари орқали тўловларни қабул қилиш имконияти» edi. Yana 6-band yangi 21-xatboshi:
> «банкларда генерация қилинган ягона QR-кодни шакллантириш ахборот тизими ҳамда электрон тўлов тизимларига мажбурий уланиши»

Kuchga kirishi: 14 "в" Izohdagi kechiktirilganlar ro'yxatida yo'q, demak **21.07.2026** (bu xulosa — biz chiqargan; lex.uz alohida sana ko'rsatmaydi).

**VMQ-393 14 "д"** — VMQ-943 4-ilova 19-band, **22.10.2026 dan**. Modelni reyestrdan chiqarish asosi: «онлайн НКМ ва виртуал кассаларнинг техник имкониятлари уларга қўйиладиган техник талабларга мувофиқ бўлмаганда».

**VMQ-943 1-ilova 7-band** — chek rekvizitlari:
- karta turi (korporativ/shaxsiy/ijtimoiy);
- ijtimoiy karta raqami (birinchi va oxirgi 4 raqam);
- tranzaksiyaning unikal raqami (VMQ-610, 29.09.2025);
- to'lov shakli (VMQ-393, **22.10.2026 dan**).

**VMQ-75** (https://lex.uz/docs/243235) — 21-band: "hisob-kitob terminalining **mavjudligi**"; 189-band: karta to'lovidan bosh tortish — javobgarlik. Integratsiya haqida gap yo'q.

**Sanksiyalar**:
- MJtK 164 — savdo qoidalari (10/20 BHM);
- MJtK 175 — fiskal belgilar va integratsiya talablari (mansabdor shaxsga 100 BHM);
- **SK 221-modda** (O'RQ-1108, 2026-01-01 dan): 1-qism — kassa/terminal/QR'siz savdo yoki chek bermaslik, 5 mln so'm; 4-qism — **texnik talablarga mos bo'lmagan KKT'dan foydalanish, 20 mln so'm**. 4-qism amalda model reyestrdan chiqarilgandan keyin xavf tug'diradi.

### 3.2 Talqin

1. **Do'kon darajasida (har sotuv)**: integratsiyalangan terminal **majburiy emas**. Mustaqil terminal + fiskal chek qonuniy (1-ilova 6-band 1-xatboshi). Ishonch ~75%.
2. **Mahsulot darajasida (reyestr)**: virtual kassamiz "kartani to'g'ridan-to'g'ri shu qurilma orqali qabul qilish **imkoniyati**"ga ega bo'lishi kerak. Ekspertiza buni integratsiyalangan karta qabul qilish (terminal integratsiyasi yoki SoftPOS) sifatida tekshirishi ehtimoli yuqori. 22.10.2026 dan mos kelmaslik — reyestrdan chiqarish asosi. Bu 26 #170 savolini **"qachon"dan "qanday"ga** aylantiradi: o'z reyestr arizamiz (26 #25) oldidan kamida bitta real integratsiyalangan adapter bo'lishi kerak.
3. **2-xatboshi noaniqligi**: "reyestrdagi kassalar karta qabul qilish tizimlariga majburiy ulanishi" har do'kon zimmasidagi majburiyat deb ham o'qilishi mumkin. Lekin u 1-xatboshi (terminal cheki + fiskal chek) yonida turibdi, shuning uchun "mustaqil terminal taqiqlanadi" ma'nosi tabiiy emas. Ishonch ~60% — **DSQ'ga Xat 1 da aniq so'ralsin**.
4. **Bog'liq xavf (yuqori ishonch)**: 1-ilova 4-band (22.10.2026 dan) "ikkilamchi tizimlar"ni taqiqlaydi; 3-ilova 25-band — reyestrdagi kassaga tashqi tizimni QR chek chop etish uchun integratsiya qilish. Bu "ERP + hamkor kassa" modeliga tegishli (26 #169). Karta terminali integratsiyasiga bevosita aloqasi yo'q, lekin vendor-kassa (ERA/Rahmat) bilan ishlaganda **fiskal chekni har doim bizning kassamiz chiqarishi** (#64 qoidasi) muhim. Vendor terminalining o'z onlayn-kassasi o'chiq bo'lishi yoki faqat to'lov rejimida ishlashi kerak — aks holda ikki marta fiskalizatsiya va "ikkilamchi tizim" xavfi paydo bo'ladi.

**Tekshirib bo'lmagan**:
- soliq.uz 2026 tushuntirishlari ("integratsiyalashgan terminal");
- "FM + terminal bitta qurilmada" haqidagi PF/PQ (topilgan PF-191 — faqat e-retsept);
- CBU'ning POS/ECR qoidalari;
- VMQ-393 rus tilidagi matni.

---

## 4. Tavsiya etilgan arxitektura

### 4.1 Nega to'g'ridan-to'g'ri brauzerdan emas

- PWA (https) xom TCP ocha olmaydi. Direct Sockets faqat Isolated Web Apps uchun.
- `https` sahifadan LAN'dagi `http://192.168.x.x` ga `fetch` qilish mixed-content va Private/Local Network Access tomonidan bloklanadi; terminal tomonida CORS ham yo'q.
- Shuning uchun Windows PK veb-kassasida terminalga ulanish **Do'kon agenti (#60) orqali** — xuddi FM va 9100 printer kabi. Agent LAN/Wi-Fi'dagi terminalga (TCP yoki terminalning lokal HTTP API'si) ulanadi. POS agentga `127.0.0.1:47110` orqali murojaat qiladi.
- Afzallik: terminal o'zining 4G/Wi-Fi'si bilan bankka chiqadi. Do'kon interneti uzilsa ham **POS ↔ agent ↔ terminal** zanjiri ishlaydi, offline savdo saqlanadi.

### 4.2 Adapterlar (bitta port, bir nechta transport)

| Adapter | Qayerda ishlaydi | Transport | Qachon |
|---|---|---|---|
| `FakeCardTerminalAdapter` | veb + Android + agent emulyatori | — | **MVP** (UI, holat mashinasi, testlar) |
| `ManualCardEntry` (mavjud #64) | hamma joyda | kassir kiritadi | doim — zaxira |
| `AgentEcrAdapter` → agentdagi `card_terminal` imkoniyati, ichida vendor drayveri (`rahmat_lan`, `era_lan`, `arcus2_tcp`, …) | Windows PK veb-kassa | POS → `127.0.0.1:47110/v1/card/*` → agent → terminal (LAN/Wi-Fi, TCP yoki HTTP) | Bosqich 5 (agent infratuzilmasi bilan), real drayver — birinchi hamkor shartnomasidan keyin |
| `CloudTerminalAdapter` (server tomoni) | server ↔ vendor bulut API (terminal ID bo'yicha) | HTTPS + webhook/poll | faqat vendor bunday API bersa (ERA ERP API so'raladi); iOS/Android-Chrome veb-kassa uchun yagona yo'l |
| `AndroidIntentCardAdapter` | Kotlin POS shu smart-terminalda (Sunmi P3/PAX A930) | vendor to'lov ilovasi Intent/AIDL/SDK | `28` Faza 2–3, vendor SDK'si bilan |
| `SoftPosAdapter` (MayaSoft SDK) | Kotlin POS, NFC telefon/planshet | in-app SDK | Faza 3, hamkor bank/PSP bilan |

### 4.3 `CardTerminalPort` kontrakti

```python
class CardTerminalPort(Protocol):
    async def purchase(self, req: CardPurchaseRequest) -> CardTxResult: ...
    async def refund(self, req: CardRefundRequest) -> CardTxResult: ...        # original_rrn, amount
    async def void(self, req: CardVoidRequest) -> CardTxResult: ...            # shu kunning, settlementgacha
    async def get_status(self, attempt_id: UUID) -> CardTxResult: ...         # "unknown"ni hal qilish
    async def get_last_transaction(self, terminal: TerminalRef) -> CardTxResult | None: ...
    async def settlement(self, terminal: TerminalRef) -> SettlementResult: ... # «сверка итогов» / kunni yopish
    async def health(self, terminal: TerminalRef) -> TerminalHealth: ...       # online | busy | offline | error
```

- **`CardPurchaseRequest`**:
  - `attempt_id` — UUIDv7, idempotentlik kaliti; terminalga ERN/order ref sifatida beriladi;
  - `terminal: TerminalRef {card_terminal_id, local_id}`;
  - `amount_tiyin: int64`, `currency='UZS'`;
  - `client_event_id` va `cash_register_id` — sotuv/smena bog'lanishi;
  - `receipt_seq` — mavjud bo'lsa.
- **`CardTxResult`**:
  - `attempt_id`;
  - `status ∈ approved | declined | cancelled | timeout | unknown | error`;
  - `amount_tiyin` — terminal tasdiqlagan summa, so'ralgan bilan solishtiriladi;
  - `approval_code` (auth code, 6 belgi), `rrn` (12 raqam), `stan`;
  - `card_mask` — `^[0-9]{4}\*+[0-9]{4}$` ga normallashtiriladi (terminal `860031******1234` bersa ham);
  - `card_scheme ∈ uzcard | humo | visa | mastercard | unionpay | mir | other` (AID yoki BIN'dan);
  - `card_type ∈ personal | corporate | social | unknown | null` — terminal odatda **bermaydi** (4.6-bandga qarang);
  - `entry_mode ∈ chip | contactless | magstripe | fallback`;
  - `terminal_id` (TID), `merchant_id` (MID), `acquirer` (bank kodi), `tx_at`;
  - `decline_code` va `decline_message`;
  - `slip_text` — ixtiyoriy, terminal cheki matni.
- **PCI**: to'liq PAN, track va CVV hech qachon portdan o'tmaydi. Adapter faqat niqob qaytaradi; agent jurnali `card_mask`dan boshqa narsani yozmaydi (`15` §10).

### 4.4 Holat mashinasi, taymautlar, idempotentlik

```
created → sent → (awaiting_card/pin) → approved | declined | cancelled
                    └── taymaut / aloqa uzildi → unknown → get_status/get_last_transaction → approved | declined | not_found
```

**Taymautlar**:
- ulanish — 5 s;
- `purchase` umumiy kutish — **120 s** (mijoz PIN kiritadi; vendor maksimumiga moslashtiriladi);
- `refund`/`void` — 60 s;
- `health` — 3 s.

**Asosiy qoida — `purchase` hech qachon avtomatik takrorlanmaydi** (fiskal amal kabi, `34` §14.3):
- `unknown` holatida avval `get_status(attempt_id)` yoki `get_last_transaction`; natija `approved` bo'lsa — to'lov qabul qilingan.
- Natija aniqlanmaguncha shu summaga yangi `purchase` **bloklanadi**. Kassirga: "Terminal javobini tekshiring"; terminal chekida tasdiq bo'lsa, menejer "qo'lda tasdiqlash" bilan yopadi.
- Bir terminalga bir vaqtda faqat bitta tranzaksiya: agentda `DeviceLane` FIFO; `busy` → `409 CARD_TERMINAL_BUSY`.
- **Idempotentlik**: `attempt_id` agent jurnalida ham, serverdagi `card_terminal_transactions`da ham UNIQUE. Bir xil `attempt_id` bilan qayta so'rov saqlangan natijani qaytaradi.

**Sotuv ketma-ketligi**:
1. Karta `approved`.
2. Fiskal chek (FM) — chekda `payment_form='card'`, `card_type`, `card_mask`, `rrn`.
3. `sale.created`.

Agar karta tasdiqlangan, lekin fiskal chek chiqmagan bo'lsa:
- sotuv "to'lov qabul qilingan, chek kutilmoqda" holatida qoladi (savat yo'qolmaydi);
- fiskal qayta urinish mavjud qoidalar bo'yicha (`device-status` → `resend`);
- kassir sotuvni bekor qilsa — **avtomatik `void`** (settlementgacha) yoki `refund`.

**Aralash to'lov**: bitta chekda bir nechta karta urinishi bo'lishi mumkin. Har biri alohida `sale_payments` qatori, har birida o'z `attempt_id`.

### 4.5 Offline va zaxira

| Holat | Xatti-harakat |
|---|---|
| Do'kon interneti yo'q, agent + terminal ishlayapti | Integratsiyalangan karta **ishlaydi** (terminal o'z kanali bilan bankka chiqadi). Sotuv offline navbatga tushadi, natija `sale.created` bilan keyin yuboriladi |
| Terminal `offline`/`error`/javob yo'q | POS integratsiyalangan tugmani o'chiradi, sababni ko'rsatadi; zaxira siyosati qo'llanadi (pastda) |
| Agent ishlamayapti | "Karta terminali ulanmagan" (lokal holat, `$agentStatus`); zaxira siyosati |
| Bulut adapteri, server yo'q | integratsiyalangan karta yo'q; zaxira siyosati |

**Zaxira siyosati** — `tenant_settings.card_manual_fallback ∈ allow | manager_approval | forbid`. Standart: integratsiyalangan terminal sozlangan kassada **`manager_approval`**, terminal sozlanmagan kassada `allow` (hozirgi #64).

**Qo'lda kiritish** (#64 bo'yicha):
- `card_type`, `card_mask`, `rrn` terminal chekidan;
- `sale_payments.card_entry_mode='manual'` + `manual_reason ∈ terminal_offline | terminal_error | unknown_result | standalone_terminal`;
- `manager_approval` bo'lsa — menejer PIN'i (mavjud ruxsat tasdig'i mexanizmi); audit yozuvi.

`forbid` faqat egasi tanlasa — qo'lda kiritish qonuniy bo'lgani uchun standart sifatida bloklanmaydi.

Z-hisobot va BO-24'da "Karta (integratsiyalangan)" va "Karta (qo'lda)" alohida ko'rsatiladi; qo'lda kiritilganlar ulushi BO-14'da ogohlantirish beradi.

### 4.6 `sale_payments` va fiskal chekka moslashtirish

| Maydon | Integratsiyalangan | Qo'lda (#64) |
|---|---|---|
| `method` | `card` | `card` |
| `card_entry_mode` (yangi) | `integrated` | `manual` |
| `card_terminal_tx_id` (yangi, FK) | majburiy | null |
| `rrn` | **majburiy**, natijadan | ijtimoiyda majburiy |
| `card_mask` | **majburiy**, natijadan | ijtimoiyda majburiy |
| `auth_code` (yangi) | natijadan | ixtiyoriy |
| `card_scheme` (yangi) | natijadan | ixtiyoriy |
| `card_type` | natijada bo'lsa avtomatik; bo'lmasa (odatda) BIN qoidasidan; topilmasa — kassir bitta bosish bilan tanlaydi (`personal/corporate/social/unknown`) | kassir tanlaydi |
| `terminal_ref` | TID (`terminal_id`) | ixtiyoriy |

**`card_type` muammosi**: ommaviy ECR'lar (Arcus2, POSLink) shaxsiy, korporativ va ijtimoiy kartani ajratmaydi. Taklif:
- tenant darajasida emas, platforma darajasida **`card_bin_rules`** jadvali (BIN prefiksi → `corporate`/`social`). Manbasi — ekvayer bank yoki Uzcard/Humo BIN ro'yxati (ochiq savol);
- topilmasa POS bitta bosish bilan tanlashni so'raydi. Bu "yozish" emas — asoschi talabiga mos;
- `card_mask` faqat ilk 6 raqamni bersa (`860031******1234`), BIN shu yerdan olinadi; saqlashda #64 formati (birinchi 4 + oxirgi 4).

**Fiskal chek** (`FiscalReceiptPayload.payments`): `payment_form='card'` (aralashda `mixed`), `card_tiyin`, `card_type`, `card_mask`, `rrn` — integratsiyada avtomatik. Terminal cheki (slip) — terminalning o'zi chop etadi; `slip_text` bo'lsa, ixtiyoriy ravishda bizning chek ostiga ham qo'shiladi (VMQ-943 1-ilova 6-band — ikkala chek beriladi).

**Qaytarish (M01 return)**:
- asl to'lov `integrated` bo'lsa, `refund(original_rrn, amount)` shu terminalda, kun settlementidan oldin — `void`;
- natija `return_payments`ga xuddi shu maydonlar bilan yoziladi;
- terminal boshqa yoki ishlamasa — `manual` (menejer tasdig'i bilan).

**Settlement va solishtirish**:
- smena yopilganda (yoki kun oxirida) POS/agent `settlement()` chaqiradi; natija `card_terminal_settlements` (TID, sana, soni, jami, batch raqami);
- Z-hisobotdagi karta jami bilan farq — ogohlantirish;
- `bank_settlements` (BO-24, #42) importida `rrn` bo'yicha 5710 → 5110 avtomatik moslashtiriladi;
- komissiya — 9430 (#42, o'zgarmaydi).

### 4.7 Ma'lumotlar modeli (taklif)

- `app.card_terminals`: `id, tenant_id, branch_id, cash_register_id NULL, adapter (agent_ecr|cloud|android_intent|softpos|fake), driver (rahmat_lan|era_lan|arcus2_tcp|…), agent_id NULL, local_id NULL, vendor_terminal_ref NULL, tid, mid, acquirer_counterparty_id NULL, status, created_at`. CHECK: `adapter='agent_ecr' → agent_id, local_id NOT NULL`.
- `app.card_terminal_transactions`: `id (=attempt_id), tenant_id, card_terminal_id, kind (purchase|refund|void), amount, status, rrn, auth_code, card_mask, card_scheme, entry_mode, tid, mid, original_tx_id NULL, client_event_id, decline_code, tx_at, resolved_by (auto|status_query|manager), created_at`. UNIQUE `(tenant_id, id)`; UNIQUE `(tenant_id, tid, rrn) WHERE status='approved'`.
- `app.card_terminal_settlements`.
- `sale_payments`, `debt_payments`, `return_payments` +: `card_entry_mode`, `card_terminal_tx_id`, `auth_code`, `card_scheme`, `manual_reason`.
  - CHECK: `card_entry_mode='integrated' → card_terminal_tx_id, rrn, card_mask NOT NULL`;
  - CHECK: `method='card' ↔ card_entry_mode NOT NULL`.
- Offline POS: tranzaksiya natijasi Dexie/Room'da `sale.created` voqeasi ichida (`payments[].card_terminal_result`) yuboriladi; server `card_terminal_transactions`ni shu voqeadan yaratadi (#68'dagi `fiscal_result` naqshi).

### 4.8 Agent lokal API (taklif, `21` §16.1 ga qo'shimcha)

| Yo'l | So'rov | Javob |
|---|---|---|
| `GET /v1/card/terminals` | — | `[{local_id, driver, host, tid, status}]` |
| `POST /v1/card/purchase` | `{attempt_id, local_id, amount_tiyin, cash_register_id, client_event_id}` | `CardTxResult` (uzun so'rov ≤ 125 s) yoki `202 {attempt_id}` + `GET /v1/card/tx/{attempt_id}` poll |
| `POST /v1/card/refund`, `/void` | `{attempt_id, local_id, amount_tiyin, original_rrn \| original_attempt_id}` | `CardTxResult` |
| `GET /v1/card/tx/{attempt_id}` | — | `CardTxResult` (agent jurnalidan yoki terminal so'rovidan) |
| `POST /v1/card/cancel-pending` | `{attempt_id}` | terminalda kutish ekranini bekor qilish (qo'llansa) |
| `POST /v1/card/settlement` | `{local_id}` | `SettlementResult` |

- Xatolar: `409 CARD_TERMINAL_BUSY`, `503 CARD_TERMINAL_OFFLINE`, `504 CARD_TERMINAL_TIMEOUT` (→ `unknown`), `502 CARD_TERMINAL_ERROR`, `422 CARD_AMOUNT_MISMATCH`.
- `hello.capabilities.card_terminal {enabled, version, devices:[{local_id, driver, status}]}`.
- Himoya — mavjud uchlik: loopback, `Origin` oq ro'yxati, lokal token.
- Terminal manzili faqat ro'yxatdagi xususiy LAN IP; ixtiyoriy host yo'q (printer qoidasi kabi).

---

## 5. Ochiq savollar (tashqi javob kerak)

1. **Rahmat (1865)** va **Humo (НМПЦ)**: Sunmi P3/P2 "Open API" — transport (LAN HTTP/TCP yoki bulut), natija maydonlari (RRN, auth, mask, karta turi), test qurilma, shartnoma/NDA/narx.
2. **Arca/ERA**: ERP API orqali karta to'lovini boshlash va natijani olish mumkinmi? ERA onlayn-kassasini o'chirib, faqat to'lov rejimida ishlatish mumkinmi (ikki marta fiskalizatsiya va "ikkilamchi tizim" xavfi)?
3. **HUMO/НМПЦ**: Ingenico Lane/3600 qaysi ECR protokolida ishlaydi (Arcus2?), dasturchiga qanday beriladi.
4. **MayaSoft**: SoftPOS SDK shartlari, hamkor bank talabi, narx.
5. **Karta turi (shaxsiy/korporativ/ijtimoiy)** — terminal qaytaradimi yoki BIN ro'yxati bormi (Uzcard/Humo/ekvayer bank).
6. **DSQ (Xat 1)**: VMQ-943 1-ilova 6-band 2-xatboshi har do'konga majburiyatmi; 2-ilova "shu qurilma orqali" talabini reyestr ekspertizasi qanday tekshiradi — SoftPOS yoki tashqi terminal integratsiyasi yetarlimi (26 #170).

---

## 6. Taklif qilingan qaror #71

> | 71 | **Integratsiyalangan karta terminali**: karta to'lovi uchun yagona **`CardTerminalPort`** (`purchase`, `refund`, `void`, `get_status`, `get_last_transaction`, `settlement`, `health`; summalar tiyinda; idempotentlik kaliti `attempt_id` UUIDv7). O'zbekistonda ochiq ECR standarti va bulut "terminalga yuborish" API'si yo'q (P8) — real adapterlar vendor hamkor bilan shartnoma asosida. Adapterlar: `FakeCardTerminalAdapter` (MVP), **`AgentEcrAdapter`** (Windows veb-kassa: POS → Do'kon agenti `127.0.0.1:47110/v1/card/*` → LAN/Wi-Fi'dagi terminal; agent imkoniyati `card_terminal`, Bosqich 5; vendor drayveri birinchi hamkordan keyin — Rahmat/Humo Sunmi P3 yoki ERA PAX A930), `CloudTerminalAdapter` (faqat vendor bulut API bersa), `AndroidIntentCardAdapter` va `SoftPosAdapter` (Kotlin POS, `28` Faza 2–3). `purchase` hech qachon avtomatik takrorlanmaydi; taymaut → `unknown` → `get_status`/`get_last_transaction`, natija aniqlanmaguncha yangi urinish bloklanadi. Tartib: karta tasdig'i → fiskal chek (`payment_form`, `card_type`, `card_mask`, `rrn` avtomatik) → `sale.created`; chek chiqmay sotuv bekor qilinsa — avtomatik `void`/`refund`. `sale_payments`/`debt_payments`/`return_payments` ga `card_entry_mode` (`integrated`\|`manual`), `card_terminal_tx_id`, `auth_code`, `card_scheme`, `manual_reason`; `integrated` da `rrn` va `card_mask` majburiy. `card_type` — natijadan yoki platforma `card_bin_rules` dan, topilmasa kassir bitta bosishda tanlaydi. Terminal ulanmagan/xato bo'lsa — qo'lda kiritish (#64) zaxira sifatida qoladi, siyosat `tenant_settings.card_manual_fallback` (`allow`\|`manager_approval`\|`forbid`; integratsiyalangan terminal sozlangan kassada standart `manager_approval`). Agent orqali integratsiya do'kon interneti uzilganda ham ishlaydi. Smena yopilishida `settlement`; `bank_settlements` (#42) `rrn` bo'yicha moslashtiriladi. Huquqiy: har do'konda integratsiya majburiy emas (VMQ-943 1-ilova 6-b. 1-xatboshi), lekin virtual kassa **mahsuloti** "barcha karta va QR to'lovlarini to'g'ridan-to'g'ri shu qurilma orqali qabul qilish imkoniyati"ga ega bo'lishi shart (VMQ-943 2-ilova 6-b. 10-xatboshi, VMQ-393, 21.07.2026 dan; 4-ilova 19-b. — mos kelmaslik reyestrdan chiqarish asosi, 22.10.2026 dan) → o'z reyestr arizamizdan (26 #25) oldin kamida bitta real adapter. | Tadqiqot P8 (2026-10-16); asoschi talabi | `21` §9.2, yangi §9.4, §16, §16.1; `34` §14.2–§14.3; `11`, `12`; `18`; `16`; `17`; `07` (POS-03, POS-16, BO-12, BO-24); `06`; `03` (US-M01-01); `04`; `08`; `23`; `24` §6; `28` §4.5; `15`; `25`; `26`; `27`; `29`; `30`; `31`; `01` #64 |

Bundan tashqari, **#64** matniga qo'shimcha: "mustaqil terminal bilan qo'lda kiritish — integratsiyalangan terminal sozlanmagan kassada asosiy, sozlangan kassada zaxira (#71)".

---

## 7. Spec o'zgarishlari ro'yxati (aniq joylar)

| Fayl | Bo'lim | O'zgarish |
|---|---|---|
| `01-qarorlar.md` | jadval | Yangi **#71** (6-bo'lim matni); #64 ga zaxira izohi |
| `21-integratsiyalar.md` | §9.2 | Sarlavha: "Karta: integratsiyalangan terminal (#71) va qo'lda belgilash (#64)"; qo'lda — zaxira/terminal sozlanmagan holat; "integratsiyalangan bank terminali veb-kassaga ochiq protokol bilan ulanmaydi" jumlasi P8 xulosasi bilan almashtiriladi |
| `21-integratsiyalar.md` | yangi §9.4 | `CardTerminalPort`, adapterlar jadvali, holat mashinasi, taymautlar, idempotentlik, offline, zaxira siyosati, settlement, xato UX, monitoring (BO-14), MVP bosqichi — standart bo'lim shabloni bo'yicha |
| `21-integratsiyalar.md` | §16 jadvallari, §16.1 | "Karta terminali" imkoniyati qatori; `/v1/card/*` yo'llari va sxemalari; `CARD_TERMINAL_*` xato kodlari |
| `21-integratsiyalar.md` | Ochiq savollar | 5-bo'limdagi 1–6 bandlar |
| `34-1c-agent.md` | §14.2 | `capabilities.card_terminal {enabled, version, devices:[{local_id, driver, host, tid, status}]}` |
| `34-1c-agent.md` | §14.3 (a) | "karta terminali" oilasi: amallar, `DeviceLane` FIFO, avtomatik takrorlamaslik, faqat ro'yxatdagi LAN host, jurnalda faqat niqob; ixtiyoriy server vazifasi `card.settlement` (POS yopiq bo'lsa) — `21` §16, `23` §4.2, `33` §9.5 oq ro'yxatlari bilan sinxron |
| `11-malumotlar-modeli.md` | to'lov jadvallari | `card_terminals`, `card_terminal_transactions`, `card_terminal_settlements`, `card_bin_rules` (platforma); `sale_payments`/`debt_payments`/`return_payments` yangi maydonlari |
| `12-db-sxema.md` | `sale_payments` (~1015), `debt_payments` (~1490), qaytarish to'lovlari | Ustunlar va CHECK'lar (4.7); yangi jadvallar DDL; migratsiya ro'yxatiga yangi raqam (`card_terminal`), agent infratuzilmasi bilan Bosqich 5 |
| `18-api-kassa.md` | §4.1 `payments[]` (~276–286), qarz to'lovi (~672), §16 checkout, offline (~946) | `card_entry_mode`, `card_terminal_result{attempt_id, status, rrn, auth_code, card_mask, card_scheme, tid, mid, tx_at}`, `manual_reason`, menejer tasdig'i; validatsiya qoidalari; `counted_card_total` (~184) integratsiyalangan/qo'lda bo'linishi; terminal CRUD (`GET/POST/PATCH /card-terminals`), settlement natijasi endpointi; cloud adapter uchun `POST /api/v1/card-terminal/transactions` + holat |
| `17-api-umumiy.md` | xato kodlari (~449) | `CARD_TERMINAL_BUSY/OFFLINE/TIMEOUT/ERROR/RESULT_UNKNOWN`, `CARD_AMOUNT_MISMATCH`, `validation.card_manual_requires_approval` |
| `16-offline-sync.md` | §(to'lov turlari offline siyosati, ~88), §387 | Integratsiyalangan karta offline'da agent/Android orqali ruxsat; `card_terminal_result` voqea ichida; `unknown` holat offline'da ham bloklaydi |
| `07-ekran-tafsilotlari.md` | POS-03 (~131) | "Karta" tugmasi → terminal holati → "Kartani terminalga qo'ying" ekrani (summa, bekor qilish, taymaut hisoblagichi) → natija; `card_type` bitta bosishli tanlov (kerak bo'lsa); `unknown` va zaxira oqimi (menejer PIN) |
| `07-ekran-tafsilotlari.md` | POS-16, BO-12, BO-24, BO-14 | POS-16 — terminalni topish/sinash ("test 1 so'm" emas — `health`); BO-12 — kassa ↔ terminal bog'lash, `card_manual_fallback`; BO-24 — integratsiyalangan/qo'lda bo'linishi, `rrn` bo'yicha moslashtirish; BO-14 — terminal holati, qo'lda ulushi |
| `06-ekranlar-umumiy.md` | POS-03 (~114) | "Karta (qo'lda belgilash)" → "Karta (terminal / qo'lda)" |
| `08-dizayn-tizimi.md` | holat komponentlari | Terminal kutish/natija holatlari (approved/declined/unknown) |
| `03-modullar-talablari.md` | US-M01-01 (~29), M08 (~327), M16 | Yangi AC: integratsiyalangan karta (Given/When/Then), `unknown` holat, zaxira siyosati, qaytarishda `refund/void`, Z-hisobot bo'linishi |
| `04-biznes-jarayonlar.md` | to'lov jadvali (~166), BP-02/BP-05 | "Karta — integratsiyalangan terminal" qatori; mavjud qator "zaxira/sozlanmagan" deb belgilanadi |
| `13-provodka-qoidalari.md` | — | O'zgarish yo'q (5710 → 5110, 9430); faqat `rrn` bo'yicha avtomatik moslashtirish izohi §2.18a ga |
| `15-xavfsizlik-va-audit.md` | §10 (PCI, ~19) | Integratsiyada ham faqat niqob; agent jurnali; qo'lda kiritish va menejer tasdig'i audit voqeasi |
| `23-backend-arxitekturasi.md` | portlar, §4.2 | `CardTerminalPort` va adapterlar; agent vazifa turi (agar `card.settlement`) |
| `24-frontend-arxitekturasi.md` | §6 | `@shared/lib/cardTerminal` (agent klienti, holat mashinasi, `$cardTerminalStatus`) |
| `25-nofunksional-talablar.md` | taymautlar, uskuna | 120/60/5/3 s taymautlar; tavsiya etilgan qurilmalar (Sunmi P3, PAX A930) — pilotdan keyin |
| `28-android-pos.md` | §4.5 (~117–120), modul daraxti (~63), Faza 2–3 (~170) | `hardware/card-terminal` — `AndroidIntentCardAdapter`, `SoftPosAdapter` (MayaSoft SDK), bir xil kontrakt |
| `26-ochiq-savollar-reestri.md` | #65 (~85), #170 (~210), yangi qatorlar | #65 → "#71 bilan hal qilindi (port + Fake); real adapter hamkorga bog'liq"; #170 → P8 huquqiy xulosasi (mahsulot darajasida majburiy, reyestrdan oldin kamida bitta adapter); yangi: vendor API'lari (Rahmat/Humo/ERA/НМПЦ Lane), MayaSoft SDK, karta turi BIN ro'yxati |
| `27-backlog.md` | MVP (~115), Bosqich 5, Faza 2–3 | MVP — port + Fake + UI + `card_entry_mode`; Bosqich 5 — agent `card_terminal` imkoniyati; hamkor drayveri; Android adapter |
| `29-atamalar-lugati.md` | (~38, ~42) | "Integratsiyalangan terminal", "RRN", "Avtorizatsiya kodi", "Settlement / сверка итогов", "SoftPOS", "ECR"; `terminal_ref` ta'rifi yangilanadi (TID) |
| `30-izchillik-matritsasi.md` | US-M01-01, jadvallar (~455, ~462) | Yangi jadval/ustunlar va endpointlar |
| `31-qabul-testlari.md` | QT-M01-15 yonida, QT-M16-05 | Yangi QT: integratsiyalangan purchase happy; declined; timeout → `unknown` → status so'rovi; takroriy `attempt_id` idempotent; fiskal xato + void; qaytarishda refund; zaxira `manager_approval`; offline agent orqali; Z-hisobot bo'linishi |
| `33-1c-integratsiya.md` | ВидОплаты xaritasi | O'zgarish yo'q (`card` bitta); ixtiyoriy — terminal ekvayer kontragenti `card_terminals.acquirer_counterparty_id` dan |

---

## 8. Ishonch darajalari (yig'ma)

| Xulosa | Ishonch |
|---|---|
| Ochiq ECR standarti/hujjati yo'q | yuqori |
| Ommaviy bulut "terminalga yuborish" API'si yo'q | o'rta-yuqori |
| Wi-Fi faqat Android smart-terminallarda real | yuqori |
| Vendorlar (Rahmat, Humo, NEXGO, ERA, Smart Business) yopiq API taklif qiladi | yuqori (mavjudlik) / past (tafsilot) |
| Har do'konda integratsiya majburiy emas | ~75% |
| Mahsulot (virtual kassa) reyestri uchun karta "shu qurilma orqali" imkoniyati kerak | o'rta-yuqori |
| 14 "в" kuchga kirishi 21.07.2026 | o'rta (Izohdan xulosa) |

## 9. Manbalar

- VMQ-393 (20.07.2026) — https://lex.uz/docs/8343102
- VMQ-943 — https://lex.uz/docs/4603329
- VMQ-75 — https://lex.uz/docs/243235
- Uzcard biznes — https://uzcard.uz/business?tab=2, https://uzcard.uz/business?tab=3, https://uzcard.uz/news/uzcard_and_arca_group_comprehensive_solutions, https://uzcard.uz/news/uzcard_softpos
- Humo — https://humocard.uz/ru/business/terminals/, https://humocard.uz/ru/business/onlayn-nkm/, https://www.spot.uz/ru/2025/12/24/humo/
- Rahmat — https://rhmt.uz/pos/, https://rhmt.uz/pos/integration, https://rhmt.uz/acquiring/online, https://app.docs.rhmt.uz/, https://www.gazeta.uz/ru/2026/08/06/rahmat/
- ERA — https://pos.era.uz/ru/erp
- Ipoteka — https://www.ipotekabank.uz/cash-services/acquiring, https://www.ipotekabank.uz/ru/business/acquiring/softpos/
- Asaka — https://asakabank.uz/ru/small-business/acquiring/marta-softpos-terminal-v-vashem-smartfone
- MayaSoft — https://mayasoft.uz/, https://marta.gitbook.io/marta/instrukcii
- TBC — https://tbcbank.uz/ru/business/product/soft-pos/, https://www.gazeta.uz/2025/06/27/tbc-billz
- Hamkorbank — https://hamkorbank.uz/rental-trading-terminals
- Agrobank tenderi — agrobank.uz "ТЗ_Агробанк терминалы.pdf"
- Multikassa — https://docs-virtual-kassa.multibank.uz/
- To'lov API'lari — https://docs.atmos.uz/, https://click.uz/ru/click-terminal, https://developer.help.paycom.uz/metody-merchant-api, https://developer.uzumbank.uz, https://docs.globalpay.uz/api, https://docs.multicard.uz, https://paynet.uz/developer-guide
- bss.uz — https://www.bss.uz/article/4805-kassa-v-uzbekistane-kak-vybrat-kupit-i-primenyat-onlayn-kkm-v-2026-godu
- smartone.uz, mkassa.uz (NEXGO N82)
- ECR (Rossiya/AQSh, solishtirish uchun) — docs.artix.su (Arcus2), kb.gbsmarket.ru, docs.rkeeper.ru, rarus.ru (INPAS), help.petrosoftinc.com (POSLink), blog.rospertech.com (Sunmi), guide.kaspi.kz, pos-plugin.kz (Kaspi namunasi)
- Ichki: `spec/kod-uchun/01-qarorlar.md` #42, #60, #64, #66, #68; `21-integratsiyalar.md` §9, §9.2, §16; `34-1c-agent.md` §14; `research_notes/ochiq-savollar/P1-soliq-fiskal.md` (qo'shimcha topilma 1), `P3-tolovlar-bank.md` §4
