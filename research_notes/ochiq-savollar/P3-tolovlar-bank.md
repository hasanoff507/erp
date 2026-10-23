# P3 — To'lovlar va banklar: OQ-030, OQ-032, OQ-033, OQ-034, OQ-038

**Maqsad:** `00-inventar.md` §4/§12 dagi P3 partiyasining 5 ta R-bandini desk-research bilan yopish: har biriga manbali javob, ishonch darajasi, spec'ga aniq taklif va holat. · **Kim uchun:** asoschi, spec'ni yangilovchi agentlar, P1 (fiskal) va P7 (NSBU 21) partiyalari. · **Bog'liq fayllar:** `spec/kod-uchun/21-integratsiyalar.md` §9/§9.1/§9.2/§13/OS5–OS6/OS12–OS13, `13-provodka-qoidalari.md` §1/§2.2/§2.18/§2.18a/ogohlantirish 6, `01-qarorlar.md` #10/#23/#42, `11-malumotlar-modeli.md` §6, `12-db-sxema.md` (`sale_payments`, `bank_settlements`), `18-api-kassa.md` §16, `26-ochiq-savollar-reestri.md` B#34/B#43/B#49/A#48, `research_notes/texnik/03-efaktura-va-tolov.md` §2–§3. · **Holat:** tadqiqot, 2026-10-16. Spec fayllari **o'zgartirilmadi** — quyidagi "Spec'ga ta'sir" bloklari tayyor matn taklifi. `1c-ut11` MCP ishlatilmadi.

**Usul:** birlamchi manbalar to'g'ridan-to'g'ri o'qildi — lex.uz (to'liq matn, tahrirlar izohlari bilan), CBU press-relizi va qo'llanmasi, Payme/Click/Uzum dasturchi portallari (Click va Uzum hujjatlari SPA ichidagi JS/OpenAPI spetsifikatsiyasidan chiqarib olindi), bank sahifalari. Ikkilamchi manbalar (gazeta.uz, kun.uz, buxgalter.uz, podrobno.uz, bss.uz) faqat birlamchi manba yo'q joyda yoki amaliyotni tasvirlash uchun ishlatildi va shunday belgilandi. Barcha URL'lar 2026-10-15/16 da ochilgan.

---

## 0. Qisqa xulosa

| OQ | Savol (qisqa) | Holat | Asosiy javob | Kodga ta'siri |
|---|---|---|---|---|
| OQ-030 | Click/Payme/Uzum API, sandbox, obuna API | **YOPILDI** | Uchalasining ham to'liq ochiq hujjati bor. **Click'da rasmiy sandbox paydo bo'ldi** (Playground + 15 ssenariyli Postman to'plami). Payme Subscribe API metodlari to'liq. Uzum Merchant API — OpenAPI 3.1 dagi JSON vebxuklar (JSON-RPC emas). Rekurrent to'lov uchalasida bor (karta tokeni). | FLAG → adapterlarni yozish mumkin |
| OQ-032 | UzQR: standart, bank API/vebxuk | **QISMAN** | Normativ va arxitektura aniq: CBU 5/11-son qoidalar (reg. 3817, 16.04.2026), operator — **MUNIS**, merchant kabineti **uzqr.uz** (E-IMZO bilan kirish), **dinamik QR har kassaga alohida API kalit** orqali POS dasturiga ulanadi. **POS API texnik hujjati ochiq emas.** VMQ-393 (20.07.2026) bo'yicha UzQR'ga ulanish **kassa dasturi uchun majburiy texnik talab**, UzQR to'lovi uchun ham NKT cheki majburiy. | BLOK toraydi: dinamik UzQR adapteri faqat API hujjatini kutadi; statik UzQR qo'lda tasdiqlash bilan hozir yoziladi |
| OQ-033 | Mustaqil terminal bilan "karta"ni qo'lda belgilash | **YOPILDI** | Qonuniy: VMQ-943 1-ilova 6-band terminal cheki + kassa fiskal chekini nazarda tutadi. Lekin chekda **to'lov shakli** (22.10.2026 dan: naqd / bank kartalari / QR-kodli to'lov / aralash) va **karta turi** (korporativ/shaxsiy/ijtimoiy) bo'lishi shart; ijtimoiy kartada karta niqobi va tranzaksiya raqami (RRN) ham kerak. | FLAG: `sale_payments`ga `card_type` va (ijtimoiy karta uchun) `card_mask` qo'shish |
| OQ-034 | 5710, komissiya hisobi, "вид оплаты" | **YOPILDI** (buxgalter faqat tasdiqlaydi) | NSBU 21 Ilova 237–239-b.: 5710 — tranzit hisob, `Dt 5110 / Kt 5710` aynan misol qilib berilgan. **Bank komissiyasi — 9430** (410-b.: "банк ва депозитарий хизматларининг тўловлари"), 9410 emas. VMQ-54 Nizom 2.3.12 ham bu xarajatni "boshqa operatsion xarajatlar"ga kiritadi. | FLAG: `13` §2.18a 2-qatorda 9410 → 9430 |
| OQ-038 | Ko'chirma importi formati, ochiq banking | **QISMAN** | De-fakto format — **1CClientBankExchange** (.txt), ayrim banklarda xml/Excel. UzQR kabineti CSV eksport beradi (davr ≤ 35 kun). Ochiq banking: PQ-359 dagi 2026-09-01 muddati **bajarilmagan** — 2026-10-16 holatida lex.uz da CBU ochiq banking normativ hujjati yo'q. Ekvayer hisob-kitob hisoboti namunalari ochiq manbada yo'q. | FLAG: `statement_import` uchun 1CClientBankExchange parseri (draft), qolgani qo'lda |

**P3 doirasida qo'shimcha ravishda yopilganlari:** OQ-031 litsenziya qismi (O'RQ-578 14-modda — texnologik vositachi to'lov xizmati hisoblanmaydi, §7.1); `21` OS5 "QR/onlayn to'lovda fiskal chekni kim chiqaradi" (§7.2 — endi ziddiyat yo'q: POS'da kassa chiqaradi, ikki marta fiskalizatsiya qilishga yo'l qo'yilmaydi).

---

## 1. Tadqiqot davomida topilgan, spec'da hali yo'q muhim normativ o'zgarishlar

Quyidagi uch hujjat 2026-yil 2- va 3-choraklarida chiqqan va `21`/`13`/`11` dagi bir nechta farazni o'zgartiradi. Ular quyidagi OQ'larda ishlatiladi.

**1.1 CBU Boshqaruvining 25.03.2026 dagi 5/11-son qarori** — "To'lovlarni amalga oshirishda yagona QR-kod orqali to'lov xizmatlarini ko'rsatish qoidalari" (AV reg. 3817, 15.04.2026; kuchga kirgan: 16.04.2026) — [lex.uz/docs/8139307](https://lex.uz/docs/8139307). QR turlari (3-band), operator vazifalari (4–11), ekvayer (12–20), ekvayer agenti — to'lov tashkiloti (21–26), tashabbuskor ilova (27–29), merchant majburiyatlari (30–32).

**1.2 VMQ 20.07.2026 dagi 393-son qarori**, 1-ilova 14-band — VMQ-943 ga o'zgartirishlar (kuchga kirgan: 21.07.2026; ayrim bandlari 22.10.2026 dan) — [lex.uz/docs/8343102](https://lex.uz/docs/8343102):
- VMQ-943 2-ilova (onlayn-NKM 3-band va **virtual kassa** 6-band texnik talablari): *«банкларда генерация қилинган ягона QR-кодни шакллантириш ахборот тизими ҳамда электрон тўлов тизимларига мажбурий уланиши»*; *«барча банк карталари ва QR-кодлар орқали тўловларни тўғридан-тўғри шу қурилма орқали қабул қилиш имконияти»*.
- VMQ-943 1a-ilova 2-band: *«жойларда, шу жумладан, банкларда генерация қилинган ягона QR-код орқали амалга оширилган тўловлар тўғрисидаги маълумотларни операторга юбориш. Бунда ягона QR-код орқали амалга оширилган тўловларга ҳам назорат-касса техникаларидан мажбурий равишда чек берилиши шарт»*.
- VMQ-943 1-ilova 7-band (chek rekvizitlari), lex.uz izohi bilan *«Кучга кириш санаси — 2026 йил 22 октябрь»*: *«тўлов шакли: нақд, банк карталари, QR-кодли тўлов ёки аралаш»*. 1-ilova 2-bandga "QR-kodli to'lov" ta'rifi qo'shilgan: *«…тижорат банклари ёки тўлов ташкилотлари орқали харидорлар томонидан мобиль илова дастурларига бириктирилган банк карталари ҳисобварақлари ва электрон пул ҳамёнлардан фойдаланган ҳолда маблағларни тўлаш ҳақидаги маълумот»*.
- VMQ-75 (chakana savdo qoidalari) 189-band — sanksiyaga sabab bo'luvchi qoidabuzarliklar ro'yxatiga qo'shilgan: *«банк карталари орқали тўловни қабул қилишдан бош тортиш»* va *«якка тартибдаги тадбиркорлар ва ўзини ўзи банд қилган шахслар тўлов ташкилотларининг рақамли платформаларида генерация қилинган … махсус QR-коддан, юридик шахслар эса банкларда генерация қилинган ягона QR-коддан фойдаланиш имкониятларини яратмаслик ва (ёки) улар орқали тўловларни қабул қилмаслик»*.
- VMQ-943 3-ilova 25-band (22.10.2026 dan) — TXKM'ni reyestrdan chiqarish asoslari qatoriga: *«Давлат реестрига киритилган онлайн-НКТларга бошқа турдаги (иккиламчи) … ахборот тизимлари … QR-кодли чек чоп этиш мақсадида интеграция қилинганлиги аниқланганда»*. **Bu P1/OQ-012 (fiskal yo'l, hamkor kassa) uchun xavf** — P1 partiyasiga uzatiladi; P3 xulosalariga ta'sir qilmaydi.

**1.3 Prezidentning 12.08.2025 dagi PQ-247-son qarori**, 7-band "a" (2026-01-01 dan) — [lex.uz/docs/-7681520](https://lex.uz/docs/-7681520): *«yakka tartibdagi tadbirkorlar va oʻzini oʻzi band qilgan shaxslarda raqamli platformalarda generatsiya qilingan elektron toʻlovlarni qabul qiluvchi maxsus QR kod mavjud boʻlishi chakana savdo qoidalarining majburiy talabi etib belgilanadi va maxsus QR kod mavjud emasligi nazorat-kassa texnikasini va (yoki) hisob-kitob terminallarini qoʻllamaslikka tenglashtiriladi»*. **`21` §9.1 dagi "YTT'lar uchun ixtiyoriy" degan gap noto'g'ri**: YTT uchun ham QR majburiy, faqat u bank UzQR emas, to'lov tashkiloti platformasidagi QR (Click/Payme/Paynet Xolis va h.k.).

---

## 2. OQ-030 — Click/Payme/Uzum: rasmiy API, sandbox, Uzum protokoli, obuna (rekurrent) API

### Javob

| | Payme | Click | Uzum |
|---|---|---|---|
| Do'kon (merchant) qabul qilish protokoli | Merchant API: Payme merchant serveriga RPC so'rov yuboradi (`CheckPerformTransaction`, `CreateTransaction`, `PerformTransaction`, `CancelTransaction`, `CheckTransaction`, `GetStatement` (**majburiy**), `SetFiscalData` (ixtiyoriy)); Basic Auth | SHOP API: Prepare/Complete callback'lari, MD5 `sign_string`; Merchant API (REST, `https://api.click.uz/v2/merchant/...`, sarlavha `Auth: merchant_user_id:sha1(timestamp+secret_key):timestamp`) | Merchant API: Uzum merchant serveriga **JSON vebxuklar** `/check`, `/create`, `/confirm`, `/reverse`, `/status` (OpenAPI 3.1, `POST`, `application/json`, Basic Auth). JSON-RPC **emas** |
| Kassada (POS) QR | Payme QR (ilova), `receipts.create` | **Click Pass**: kassir mijoz ilovasidagi QR'ni skanerlaydi → `POST /v2/merchant/click_pass/payment` (`otp_data`, `amount`, `cashbox_code`) | **Dynamic QR** (`/api/dynamic-qr/merchant/payment/create`, `status-by-order`, `fiscal`, `reversal`, `cancel-order`); **FastPay** (kassir mijoz QR'ini skanerlaydi) |
| Sandbox / test | **Bor**: `test.paycom.uz`, `TEST_KEY`; Subscribe API test hosti `checkout.test.paycom.uz/api` | **Endi bor**: docs.click.uz "Тестовая площадка (Sandbox)" — Prepare/Complete'ni brauzerdan o'z serveringizga sinash; "Postman-коллекция" — 15 ssenariy generatori | **Checkout** — test kartalari bor; **Fiscalization** — test host `https://test-ofd.ipt-merch.com`; **Merchant API** — test muhiti hujjatda yo'q, kredensial "provided by our team" |
| Obuna / rekurrent (M17 billing) | **Subscribe API**: `cards.create`, `cards.get_verify_code`, `cards.verify`, `cards.check`, `cards.remove`, `receipts.create`, `receipts.pay`, `receipts.send`, `receipts.cancel`, `receipts.check`, `receipts.get`, `receipts.get_all`, `receipts.set_fiscal_data`, xolding | Karta tokeni: `card_token/request`, `card_token/verify`, `card_token/payment`, `DELETE card_token/:service_id/:card_token` | Checkout: `getBindings`, `unBindCard`, `payment/register`, `merchantPay` (back-to-back), `acquiring/complete` (ikki bosqichli) |
| Fiskalizatsiya API | Merchant API: Payme o'zi fiskalizatsiya qiladi va natijani `SetFiscalData` bilan yuboradi; Subscribe API: `receipts.set_fiscal_data` — merchant **o'z** fiskal chekini Payme'ga beradi | `ofd_data/submit_items` (Click chekni o'zi fiskalizatsiya qiladi, `CommissionInfo` = merchant STIR/JShShIR) **yoki** `ofd_data/submit_qrcode` (merchant o'z chekining `ofd.soliq.uz` havolasini beradi) | Uzum Fiscalization API (`/v2/receipt`, `/v2/refund_receipt`, `/v2/qr_payment`); Dynamic QR'da `/fiscal` — merchant chek havolasini beradi |
| Merchant komissiyasi | 1% (joyida QR/ilova), 1,5–2% onlayn — `03-efaktura-va-tolov.md` §2.4 (2026-10-14), bu safar qayta tekshirilmadi (sayt JS) | QR/Click Pass: Uzcard/Humo **1%**, Visa 2%; sayt: 1,5–2,5%; avtomoyka 5% — business.click.uz/ru, **2026-10-16 qayta tasdiqlandi** | Uzum karta 0%, boshqa karta 0,4% (merchants.uzumbank.uz, 2026-10-14); Dynamic QR/FastPay stavkasi ochiq emas |

### Dalil
- Payme Subscribe API metodlari va hostlar — [developer.help.paycom.uz/metody-subscribe-api/](https://developer.help.paycom.uz/metody-subscribe-api/) (sahifa ro'yxati), [developer.help.paycom.uz/protokol-subscribe-api](https://developer.help.paycom.uz/protokol-subscribe-api): *«Test: https://checkout.test.paycom.uz/api … Production: https://checkout.paycom.uz/api»*, *«X-Auth: {id}:{password}»* (back-end).
- Payme `GetStatement`: *«Реализация метода GetStatement обязательна!»*; *«Информация о транзакциях используется для актов сверки транзакций мерчанта и Payme Business.»* — [developer.help.paycom.uz/metody-merchant-api/getstatement](https://developer.help.paycom.uz/metody-merchant-api/getstatement).
- Payme sandbox: *«Песочница — среда для безопасного тестирования реализованного Merchant API … ключ для песочницы — TEST_KEY»* — [developer.help.paycom.uz/pesochnitsa](https://developer.help.paycom.uz/pesochnitsa).
- Click sandbox: sahifa sarlavhasi *«Тестовая площадка (Sandbox)»*, tavsif *«Интерактивная песочница для тестирования запросов Prepare и Complete SHOP API прямо в браузере.»*; Postman: *«Генератор Postman-коллекции из 15 сценариев для тестирования интеграции с CLICK SHOP API.»* — [docs.click.uz/testing/playground](https://docs.click.uz/testing/playground), [docs.click.uz/testing/postman](https://docs.click.uz/testing/postman) (SPA; matn sayt JS bandlaridan o'qildi, 2026-10-16).
- Click Merchant API endpointlari (`invoice/create`, `payment/status`, `payment/status_by_mti`, `payment/reversal`, `card_token/*`) — [docs.click.uz/merchant-api/requests](https://docs.click.uz/merchant-api/requests); Click Pass — [docs.click.uz/merchant-api/click-pass](https://docs.click.uz/merchant-api/click-pass).
- Uzum Merchant API: *«Merchant API allows partners to accept payments through the Uzum Bank mobile application. When a customer pays for a service, Uzum Bank sends webhooks to your server — HTTP POST requests containing payment data.»*; *«Requests are sent via the POST method in application/json format»*; *«The user credentials, including the username and password, are provided by our team.»* — [developer.uzumbank.uz/en/merchant](https://developer.uzumbank.uz/en/merchant) (`en_merchant.yaml`, OpenAPI 3.1.0).
- Uzum Checkout test kartalari: *«HUMO: 9860 0901 0121 9724 … 3-DS: 777777»* — [developer.uzumbank.uz/en/checkout](https://developer.uzumbank.uz/en/checkout); Uzum Fiscalization test hosti: *«For testing, use the host https://test-ofd.ipt-merch.com»* — [developer.uzumbank.uz/en/fiscalization](https://developer.uzumbank.uz/en/fiscalization).
- Click komissiyasi — [business.click.uz/ru](https://business.click.uz/ru) (2026-10-16 da sahifada "Uzcard/Humo 1%", "1,5%–2,5%", "5%" qatorlari bor).

### Ishonch
**Yuqori** — barcha da'volar vendorlarning o'z hujjatidan. Payme/Uzum komissiyasi — o'rta (2 kun oldingi manba, merchant shartnomasida farq qilishi mumkin).

### Spec'ga ta'sir
1. `21-integratsiyalar.md` §9 "API holati" — Click va Uzum bandlarini almashtirish:
   > - **Click**: SHOP API (Prepare/Complete, MD5 imzo) + Merchant API (REST `https://api.click.uz/v2/merchant/…`, `Auth: merchant_user_id:sha1(timestamp+secret_key):timestamp`): invoys, holat, reversal, **karta tokeni** (obuna uchun), **Click Pass** (kassir mijoz QR'ini skanerlaydi), fiskal ma'lumot (`ofd_data/submit_items` | `submit_qrcode`). **Rasmiy sandbox bor**: docs.click.uz "Тестовая площадка" + 15 ssenariyli Postman to'plami (2026-10-16 tekshirildi). Komissiya: QR/Click Pass Uzcard/Humo 1%, Visa 2%.
   > - **Uzum**: Merchant API — Uzum'dan merchant serveriga JSON vebxuklar `/check`, `/create`, `/confirm`, `/reverse`, `/status` (OpenAPI 3.1, Basic Auth; JSON-RPC emas); `/confirm` javobsiz qolsa `/status` 10 martagacha qayta so'raladi; 30 daqiqada `/confirm` kelmasa tranzaksiya `FAILED`. Kassa uchun — **Dynamic QR** (`/api/dynamic-qr/merchant/payment/*`) va **FastPay**. Checkout'da test kartalari bor; Merchant API test kredensiali Uzum menejeridan olinadi.
   > - **Payme Subscribe API** (obuna billing): `cards.*` + `receipts.*` (to'liq ro'yxat — developer.help.paycom.uz), test `checkout.test.paycom.uz/api`.
2. `21` §13 jadvali: "Click" qatori → `Bor — rasmiy Playground/Postman | ✅ Bor | Prod merchant hisobi | —`; jami qatoridagi "5 tasida to'liq" → "6 tasida to'liq".
3. `21` OS6 va OS12 — yopildi deb belgilash; `26` B#43 dan "Click rasmiy sandbox" va "Uzum Merchant API aniq protokoli" qismlarini olib tashlash (Didox qismi qoladi); `26` A#48 — "Click sandbox bor, Uzum Merchant API uchun mock qoladi".
4. `21` §14 8-band: "Click, Uzum — sandbox/hujjat yetishmovchiligi sababli" → "Click — Payme bilan parallel (sandbox bor); Uzum — Checkout test muhiti bilan, Merchant API menejer kredensiali bilan".

### Holat
**YOPILDI.** Interim (`PaymentPort` + dev/staging mock) o'zgarmaydi. Uzum Merchant API test kredensiali — tijorat qadami (Uzum menejeri), bloklamaydi.

---

## 3. OQ-032 — UzQR (bank yagona QR): standart, bank API/vebxuk orqali tasdiqlash

### Javob
1. **Normativ baza to'liq aniq.** PF-246 (10.12.2025) 3-band "b" + CBU 5/11-son qoidalari (16.04.2026 dan) + VMQ-393 (21.07.2026 dan) tahriridagi VMQ-943.
2. **Arxitektura.** Operator — Markaziy bankning banklararo chakana to'lov tizimi **MUNIS** (kliring, QR identifikatorlari reyestri, real vaqt xabarlari). Ekvayer — merchantning hisob raqami ochilgan **bank**; QR'ni ekvayer generatsiya qiladi (statik — bosma/elektron; dinamik — merchant qurilmasida ko'rsatish uchun). Mijoz har qanday ulangan bank/to'lov ilovasi bilan to'laydi (Payme/Click/Uzum ham shu yerda "tashabbuskor" bo'ladi). Faqat Uzcard/Humo kartalari ishlaydi.
3. **POS integratsiyasi (amalda).** CBU 2026-07-01 da **uzqr.uz** merchant kabinetini ishga tushirdi (E-IMZO bilan kirish). Kabinetda: statik va dinamik QR yaratish, QR'ni bloklash, statik QR uchun Telegram-bot xabarnomasi, tranzaksiyalar tarixi (qidiruv oralig'i ≤ 35 kun), **qaytarish (refund)** va CSV eksport. **Dinamik QR faqat API kalit orqali POS dasturiga ulanadi**: kalit faqat dinamik QR uchun yaratiladi, bir marta ko'rsatiladi, boshqa dinamik QR'ga qayta biriktirilishi mumkin; CBU tavsiyasi — **har kassa uchun alohida dinamik QR va alohida API kalit**. Kassa summasi bilan QR'ni o'zi chiqaradi, mijoz skanerlaydi, kassa to'lov holatini oladi.
4. **Hal bo'lmagan qism:** API kalit bilan chaqiriladigan **POS API'ning texnik spetsifikatsiyasi** (endpointlar, vebxuk yoki so'rov orqali holat olish, imzo) ochiq e'lon qilinmagan. Amalda u kassa ishlab chiqaruvchisi/TXKM orqali tarqatiladi. uzqr.uz frontendi faqat kabinetning ichki `/api/v1/merchant/*` endpointlarini ko'rsatadi; ochiq docs/swagger topilmadi.
5. **Statik va dinamik QR'da fiskalizatsiya.** VMQ-393 bo'yicha UzQR to'loviga ham NKT cheki majburiy. Statik UzQR kassa bilan integratsiya qilinmagan — buxgalter.uz'dagi amaliyotchi eksperti yozishicha, kassa tranzaksiya raqamini avtomatik ololmaydi, to'lov faktini kassir mijoz telefonidan ko'rib tasdiqlaydi. Shuning uchun **kassa avtomatik fiskalizatsiya qilishi uchun dinamik QR kerak**.
6. **Tariflar.** Merchant uchun 0,65% (ekvayer 0,1% qoldiradi, MUNIS 0,2%, Uzcard+Humo 0,15%). Mijozdan ilova 1% gacha olishi mumkin (CBU buni cheklash ustida ishlamoqda). Pul hisob raqamga 24 soat ichida tushadi. QR olish va ulanish bepul.
7. **Boshqa QR'lar ham qoladi.** CBU rasmiy javobi: Click/Payme/Uzum QR'larini olib tashlash talabi yo'q. UzQR qo'shimcha usul; karta terminali va naqd pul ham saqlanadi.

### Dalil
- CBU 5/11 qoidalari, 3-band: *«statik QR-kod — doimiy toʻlov rekvizitlariga … ega oʻzgarmas QR-kod; dinamik QR-kod — toʻlovni amalga oshirishda toʻlovni qabul qiluvchi qurilmada avtomatik yaratiladigan … hamda har bir toʻlovlar boʻyicha operatsiyalar uchun alohida identifikator va amal qilish muddati bilan bogʻlangan QR-kod»*. 4-band: *«Operator QR-kod tizimi ishtirokchilarini QR-kod tizimiga integratsiya qilish va ushbu tizim doirasida ularning ishlashini taʼminlash uchun zarur texnik hujjatlarni ishlab chiqadi.»* 14-band: ekvayer *«dinamik QR-kodni toʻlovni qabul qiluvchiga biriktirilgan toʻlovni qabul qiluvchi qurilmada aks ettirish imkonini yaratgan holda unga taqdim etadi»*. 18-band: ekvayer masofaviy bank xizmatida *«har bir tranzaksiya (toʻlov) uchun onlayn maʼlumotnoma»* beradi. 30-band: merchant *«QR-kod boʻyicha amalga oshirilgan toʻlovning holati bilan tanishadi»*. 32-band: *«amal qilish muddati oʻtgan QR-kodlar boʻyicha toʻlovlarni qabul qilishga yoʻl qoʻyilmaydi»* — [lex.uz/docs/8139307](https://lex.uz/docs/8139307).
- Operator va tariflar: *«Yagona QR kod tizimining operatori Markaziy bankning banklararo chakana toʻlov tizimi — MUNIS hisoblanadi.»*; *«ekvayer-bank oʻz ixtiyorida 0,1 foizni qoldiradi … MUNISning ulushi 0,2 foizni tashkil etadi, Uzcard va Humo esa birgalikda 0,15 foiz oladi»*; *«mablagʻlarning 24 soat ichida hisob-kitob raqamiga kelib tushishi»* — [gazeta.uz, 2026-06-22](https://www.gazeta.uz/oz/2026/06/22/uzqr/) (ikkilamchi).
- CBU press-relizi (2026-07-01): *«разработан специальный программный комплекс «Личный кабинет», функционирующий через сайт uzqr.uz … дистанционная регистрация QR-код-стикеров в системе; получение подробной информации и отчётов обо всех платежах … в режиме реального времени»*, call-markaz **1835** — [cbu.uz/ru/press_center/adverts/4092130/](https://cbu.uz/ru/press_center/adverts/4092130/); qo'llanma (rasmli PDF, 30 bet) — [cbu.uz/…/rus_uzqr.pdf](https://cbu.uz/upload/medialibrary/19b/di115k6xbunhm2883oawkbbaisgnyyo9/rus_uzqr.pdf).
- Qo'llanmaning matnli nusxasi (Ipoteka bank, `Instruction_UzQR.pptx`, 2026-07-21): *«Dynamic QR — Used to automate payment acceptance through point-of-sale (POS) software.»*; *«An API key is used to connect point-of-sale (POS) software to UzQR. API keys can be created only for dynamic QR codes.»*; *«The API key is displayed only once.»*; *«Use a Separate API Key for Each Cash Register … Each API key should be linked to its own dynamic QR code.»*; *«The maximum search period is 35 days.»*; *«The report will be generated in CSV format.»*; *«The Telegram bot feature is available only for static QR codes.»* — [ipotekabank.uz/upload/rko/Instruction_UzQR.pptx](https://www.ipotekabank.uz/upload/rko/Instruction_UzQR.pptx) (sahifa: [ipotekabank.uz/en/business/acquiring/qr-code/](https://www.ipotekabank.uz/en/business/acquiring/qr-code/)).
- Amaliyot (ikkilamchi, ekspert V. Gibel, "GAROV TARAQQIYOT NKM"): *«Сақланган API-калитни ўз кассасига мустақил равишда киритиш ва интеграцияни созлашни амалга ошириш – ТХКМга хизмат кўрсатувчи ушбу моделни ишлаб чиқарувчи етказиб берувчининг йўриқномасига мувофиқ…»*; *«Кассанинг ўзи QR-кодни шакллантиради, унда … тўлов суммаси ҳам кўрсатилади.»* — [buxgalter.uz, 2026-07-01](https://buxgalter.uz/uz/publish/doc/text215905_1_iyuldan_boshlab_yuridik_shahslar_uchun_yagona_qr-kod_majburiy_buladi_-_boshqa_qr-kodlardan_foydalanish_mumkinmi). Statik QR haqida: *«тўлов онлайн-НКМда электрон тўлов тизими томонидан автоматик тарзда эмас, балки фақат кассир томонидан «харидор смартфонида тўлов ҳақидаги маълумотни кўрганлиги» билан тасдиқланади»* — [buxgalter.uz, 2026-04-14](https://buxgalter.uz/uz/publish/doc/text214588_yagona_qr-kod_buyicha_tulovlarni_fiskallashtirishni_kim_taminlashi_kerak).
- VMQ-393: virtual kassa talabi va UzQR to'loviga chek berish majburiyati — §1.2 iqtiboslari, [lex.uz/docs/8343102](https://lex.uz/docs/8343102).
- Boshqa QR'lar: *«Центральный банк никогда не давал торговым точкам указаний убирать какие-либо QR-коды … возможность выбора способов оплаты сохраняется»*; *«UzQR пока работает только с картами национальных платежных систем Uzcard и Humo.»* — [kun.uz, 2026-07-03](https://kun.uz/ru/news/2026/07/03/tsb-s-poyavleniyem-uzqr-predprinimateli-ne-obyazany-ubirat-qr-kody-drugix-servisov-32c9cc).
- Banklar API'ni POS'ga ulash xizmati sifatida taklif qilmoqda: *«Интеграция через API — Подключение Единого QR к вашей кассовой системе…»*, 0,65% — [ru.ipakyulibank.uz/blog/business/ediniy-qr-kod-resheniye-dlya-vashego-biznesa](https://ru.ipakyulibank.uz/blog/business/ediniy-qr-kod-resheniye-dlya-vashego-biznesa).

### Ishonch
Normativ va arxitektura — **yuqori**. Kabinet va API kalit mexanizmi — **yuqori** (CBU qo'llanmasi). POS API protokoli — **noma'lum** (manba yo'q). Statik QR'dagi fiskal amaliyot — **o'rta** (ekspert fikri; VMQ-393 talabi esa yuqori ishonchli).

### Spec'ga ta'sir
1. `21-integratsiyalar.md` §9.1 "Maqsad va modullar" — "YTT'lar uchun ixtiyoriy (PF-246 3-band "b" faqat yuridik shaxslarni nomlaydi)" o'rniga:
   > Yuridik shaxslar — bank UzQR (PF-246 3-b. "b"; CBU 5/11 qoidalari, reg. 3817; VMQ-75 189-b. tahriri VMQ-393 bilan). YTT va o'zini o'zi band qilganlar — to'lov tashkiloti raqamli platformasida generatsiya qilingan **maxsus QR** (PQ-247 7-b. "a", 2026-01-01 dan; yo'qligi NKT qo'llamaslikka tenglashtiriladi). Tizimda YTT uchun bu talab `click`/`payme`/`uzum` (yoki boshqa platforma) QR'i bilan bajariladi, bank UzQR shart emas.
2. `21` §9.1 "API holati" — "Ochiq savol (tasdiqlanmagan)…" o'rniga:
   > Operator — CBU MUNIS. Merchant kabineti `uzqr.uz` (E-IMZO). **Dinamik QR** — kassa dasturi kabinetda har kassa uchun yaratilgan **API kalit** bilan ulanadi (kalit faqat dinamik QR'ga, bir marta ko'rsatiladi; CBU tavsiyasi: 1 kassa = 1 dinamik QR = 1 API kalit). POS API texnik spetsifikatsiyasi ochiq emas — CBU/MUNIS (1835, t.me/uzqr_cbu_gsi) yoki ekvayer bankdan so'raladi (`UzQrPort` real adapteri shungacha stub). **Statik QR** — kassa bilan integratsiyasiz; to'lov faktini kassir qo'lda tasdiqlaydi (ixtiyoriy ravishda tranzaksiya raqamini kiritadi), xabarnoma — kabinetning Telegram-boti. Merchant tarifi 0,65%, hisob raqamga tushish ≤ 24 soat, faqat Uzcard/Humo. VMQ-943 2-ilova (VMQ-393 tahriri): virtual kassa UzQR tizimiga **majburiy ulangan** bo'lishi kerak — reyestr (P1/OQ-012) talabi.
3. `21` §9.1 "Adapter interfeysi" — `UzqrAdapter`ga qo'shish: `async def refund(self, provider_tx_id: str, amount: Money) -> RefundResult: ...` (kabinet va qoidalar qaytarishni qo'llab-quvvatlaydi). "Ma'lumot moslashtirish"ga: `tenant_secrets`da `uzqr_api_key` **kassa (`cash_register_id`) darajasida** saqlanadi, filial/tenant darajasida emas.
4. `21` §9.1 "MVP bosqichi / Zaxira yo'l" — "statik QR (bosma) bilan boshlash" o'rniga:
   > MVP: (1) **statik UzQR — qo'lda tasdiqlanadigan to'lov turi** (mustaqil terminaldagi `card` kabi, §9.2), online va offline'da; (2) dinamik UzQR — `UzQrPort` stub, POS API hujjati olingach real adapter (Bosqich 3). Har ikkalasida ham **fiskal chekni kassamiz chiqaradi** (VMQ-943 1a-ilova 2-b., VMQ-393 tahriri), chekda to'lov shakli "QR-kodli to'lov".
5. `12-db-sxema.md` `sale_payments` CHECK (909-qator) — statik UzQR'da `provider_tx_id` bo'lmaydi. Taklif:
   `CHECK (method NOT IN ('uzqr','click','payme','uzum') OR provider_tx_id IS NOT NULL OR (method = 'uzqr' AND qr_type = 'static'))`; `18-api-kassa.md` §(sotuv to'lovlari jadvali) `checkout_ref`/`provider_tx_id` — "`uzqr`+`qr_type=static` bundan mustasno (qo'lda tasdiq; `terminal_ref`ga ixtiyoriy to'lov raqami)".
6. `16-offline-sync.md` / `21` §9.1 "Offline": "yo'q — bank QR online amal" → "dinamik UzQR — faqat online; statik UzQR — offline'da ham qo'lda tasdiq bilan ruxsat (mijoz o'z telefonidan to'laydi; tushum 5710 orqali `bank_settlements` bilan solishtiriladi)" — **asoschi qarori kerak** (firibgarlik xavfi: kassir to'lovni ko'rmasdan tasdiqlashi).
7. `26` B#49 — "Yo'l: CBU/MUNIS (1835) yoki ekvayer bankka POS API hujjati so'rovi; Click/Payme/Uzum xatlari emas"; holat "QISMAN — normativ yopildi".

### Holat
**QISMAN.** Normativ, arxitektura, kabinet, tariflar, statik/dinamik farqi — yopildi. **Ochiq qolgan yagona narsa** — dinamik QR POS API texnik spetsifikatsiyasi.
**Interim:** `UzQrPort` (dinamik — stub/mock); statik UzQR — qo'lda tasdiqlanadigan `uzqr` (`qr_type='static'`) to'lov turi sifatida hozir yoziladi.
**Kim tasdiqlaydi / beradi:** CBU MUNIS (call-markaz 1835, Telegram `t.me/uzqr_cbu_gsi` — qo'llanmadagi kanal) yoki tenant'ning ekvayer banki (Ipak Yo'li, Ipoteka, Kapitalbank "API integratsiya"ni ochiq taklif qilmoqda). Bu tijorat/texnik so'rov, E-klass emas. 6-banddagi statik QR offline siyosati — asoschi.

---

## 4. OQ-033 — Mustaqil bank terminali bilan to'lovni "karta" deb qo'lda belgilash: yuridik cheklov/jarima

### Javob
1. **Ruxsat etilgan.** VMQ-943 1-ilova 6-band terminal orqali qabul qilingan to'lov uchun xaridorga **terminal cheki bilan birga** onlayn-NKM/virtual kassaning fiskal chekini berishni nazarda tutadi. Ya'ni "mustaqil terminal + kassada fiskal chek" — qonuniy model. Integratsiyalashgan terminalni har bir sotuv uchun talab qiluvchi norma topilmadi.
2. **Majburiy bo'lgan narsa — chek rekvizitlari, belgilash usuli emas.** VMQ-943 1-ilova 7-band:
   - **to'lov shakli**: 22.10.2026 dan *"naqd, bank kartalari, QR-kodli to'lov yoki aralash"*;
   - **bank kartasi turi**: korporativ, shaxsiy yoki ijtimoiy (VMQ-610, 29.09.2025 tahriri);
   - ijtimoiy karta bilan to'lovda — **ijtimoiy karta raqami** (birinchi va oxirgi 4 raqam) va **tranzaksiyaning unikal raqami** (VMQ-610 kontekstida — ijtimoiy karta orqali xarid uchun QQSni qaytarish mexanizmi).

   Demak qo'lda belgilashda kassir kamida karta turini tanlashi, ijtimoiy kartada esa terminal chekidan niqob va RRN'ni kiritishi kerak. Hozirgi `terminal_ref` (ixtiyoriy) bunga yetmaydi.
3. **Jarima xavfi qayerda.** To'lovni noto'g'ri belgilash (masalan, karta to'lovini "naqd" deb) — chek rekvizitlari talabini buzish: MJtK 175-modda, oxirgi qismi — *"fiskal belgilarni aks ettirish … talablarni yoki tartibni buzish"*, mansabdor shaxslarga 100 BHM. Kartani umuman qabul qilmaslik — VMQ-75 189-band (VMQ-393 tahriri) va MJtK 164-modda (savdo qoidalarini buzish: fuqarolarga 10 BHM, mansabdor shaxslarga 20 BHM). Karta bilan to'lovni qo'lda "karta" deb to'g'ri belgilashning o'zi uchun alohida sanksiya topilmadi.
4. **Kelajakdagi talab (fiskal yo'l, P1).** VMQ-393 virtual kassa texnik talablariga *"barcha bank kartalari va QR-kodlar orqali to'lovlarni to'g'ridan-to'g'ri shu qurilma orqali qabul qilish imkoniyati"*ni qo'shdi. Bu — mahsulotni Davlat reyestriga kiritish talabi (bizning virtual kassamiz yoki hamkor kassasi uchun, OQ-012). Har bir do'konda integratsiyalangan terminalni majburlamaydi ("imkoniyat"), lekin reyestr ekspertizasida **integratsiyalangan karta/QR qabul qilish funksiyasi so'ralishi ehtimoli yuqori** (UzQR dinamik API — §3; karta uchun SoftPOS/bank terminali integratsiyasi).

### Dalil
- VMQ-943 1-ilova 6-band: *«Онлайн-НКМ ёки виртуал кассадан фойдаланишга ўтган тадбиркорлик субъектлари томонидан тўлов терминали орқали қабул қилинган тўловлар учун харидорларга тўлов терминали чеки билан бирга, шунингдек, жойларда харид қилинган маҳсулот ва хизматларга электрон тўлов тизимлари орқали амалга оширилган тўловлар учун харидорларга онлайн-НКМ ёки виртуал кассанинг фискал чеки берилиши шарт.»* — [lex.uz/docs/4603329](https://lex.uz/docs/4603329) (2026-10-16 tahriri).
- 7-band: *«банк картаси тури (корпоратив, шахсий ёки ижтимоий)»*; *«ижтимоий карта рақами (биринчи ва охирги тўртта рақам); транзакциянинг уникал рақами»* (VMQ-610, 29.09.2025 bilan to'ldirilgan); *«тўлов шакли: нақд, банк карталари, QR-кодли тўлов ёки аралаш»* (VMQ-393; *«Кучга кириш санаси — 2026 йил 22 октябрь»*) — o'sha manba.
- VMQ-610 (29.09.2025) maqsadi — ijtimoiy karta orqali xaridda QQSni qaytarish: *«ижтимоий карта орқали товар (хизмат)лар харид қилинганда, тегишли харид чекида ижтимоий карта ва транзакциянинг уникал рақамини … тақдим этиш амалиётини жорий этсин»* — [lex.uz/docs/7747538](https://lex.uz/docs/7747538).
- VMQ-393: 2-ilova 6-band talabi; VMQ-75 189-band qo'shimchasi — §1.2, [lex.uz/docs/8343102](https://lex.uz/docs/8343102).
- MJtK 164-modda: *«Савдо ёки хизмат кўрсатиш қоидаларини бузиш — фуқароларга базавий ҳисоблаш миқдорининг ўн баравари, мансабдор шахсларга эса — йигирма баравари миқдорида жарима»*. 175-modda: *«Фискал белгиларни акс эттириш ёхуд автоматлаштирилган ҳисобга олиш ўлчов воситалари билан жиҳозлаш … бўйича қонунчиликда белгиланган талабларни ёки тартибни бузиш — мансабдор шахсларга базавий ҳисоблаш миқдорининг юз баравари миқдорида жарима»* — [lex.uz/docs/97664](https://lex.uz/docs/97664).
- Amaliyot: *«Субъекты розничной торговли и услуг по-прежнему должны принимать банковские карты через терминалы и наличные.»* — [kun.uz, 2026-07-03](https://kun.uz/ru/news/2026/07/03/tsb-s-poyavleniyem-uzqr-predprinimateli-ne-obyazany-ubirat-qr-kody-drugix-servisov-32c9cc).

### Ishonch
Ruxsat — **yuqori** (6-band to'g'ridan-to'g'ri). Chek rekvizitlari — **yuqori**. "Karta turi" har bir karta to'loviga, RRN esa faqat ijtimoiy kartaga tegishli degan talqin — **o'rta-yuqori** (7-band shartsiz sanaydi; VMQ-610 konteksti ijtimoiy karta). Jarima moddalariga moslash — **o'rta** (amaliyot shakllanmoqda).

### Spec'ga ta'sir
1. `21-integratsiyalar.md` §9.2 "Ochiq savol" o'rniga:
   > **Huquqiy asos (yopildi, P3 2026-10-16):** VMQ-943 1-ilova 6-b. — terminal cheki + kassa fiskal cheki qonuniy model. Chekda majburiy: to'lov shakli "bank kartalari" (7-b., 22.10.2026 dan), **karta turi** (korporativ/shaxsiy/ijtimoiy); ijtimoiy kartada — karta niqobi (birinchi/oxirgi 4 raqam) va tranzaksiya unikal raqami (VMQ-610). Kassir bularni terminal chekidan kiritadi. Noto'g'ri belgilash — MJtK 175-m. (100 BHM, mansabdor shaxs) xavfi. VMQ-393 virtual kassa reyestr talabi (karta/QR to'lovini qurilmaning o'zida qabul qilish imkoniyati) — P1/OQ-012 da hisobga olinadi.
2. `11-malumotlar-modeli.md` §6 `sale_payments` va `12-db-sxema.md` (`sale_payments`, ~900-qator) — yangi ustunlar:
   `card_type TEXT NULL CHECK (card_type IN ('personal','corporate','social'))`, `card_mask TEXT NULL` (format `NNNN****NNNN`), qoidalar:
   `CHECK (method <> 'card' OR card_type IS NOT NULL)`,
   `CHECK (card_type IS DISTINCT FROM 'social' OR (card_mask IS NOT NULL AND terminal_ref IS NOT NULL))`.
   `terminal_ref` ta'rifi: "terminal operatsiya raqami (RRN); `card_type='social'` bo'lsa majburiy, boshqa holatda ixtiyoriy".
3. `18-api-kassa.md` (sotuv to'lovi maydonlari jadvali, 253–258-qatorlar atrofi) — `card_type` (enum, `method=card` bo'lsa majburiy, standart `personal`) va `card_mask` (string|null, `social`da majburiy) qatorlarini qo'shish; 862-qatordagi ochiq savol — o'chirish.
4. Fiskal chek xaritasi (`21` §1 yoki fiskal adapter spetsifikatsiyasi) — yangi qoida:
   > Chek "to'lov shakli": `cash`→naqd; `card`→bank kartalari (+`card_type`); `uzqr`/`click`/`payme`/`uzum`→QR-kodli to'lov; bir chekda bir nechta shakl→aralash. `debt` qismi — P1 (bo'nak/kredit turi) bilan kelishiladi.
5. `01-qarorlar.md` #23 (#6) — "mustaqil terminal bilan karta qo'lda belgilash" yoniga: "(huquqiy asos VMQ-943 1-ilova 6-b.; chekda karta turi majburiy — P3)".

### Holat
**YOPILDI** (yuridik savol). Interim: ruxsat qoladi, lekin `card_type` qo'shiladi (migratsiya — yangi NULL ustun + CHECK; Bosqich 2 dan oldin bo'lsa arzon).
**Ixtiyoriy tasdiq:** yurist yoki OFD operatori — "karta turi har bir karta to'lovida majburiymi yoki faqat ijtimoiy kartada" (bloklamaydi; interim — har doim so'raladi, standart qiymat `personal`).

---

## 5. OQ-034 — Naqdsiz tushum va inkassa uchun 5710, bank komissiyasi hisobi, "вид оплаты" tuzilmasi

### Javob
1. **5710 — to'g'ri hisob.** NSBU 21 Yo'riqnomasi 237–239-bandlari 5710'ni *naqd pul va pul o'tkazmalari orqali sotishdan olingan, hali bankka yetib bormagan tushum* uchun tranzit hisob deb ta'riflaydi. Ikkala yozuv ham namunaviy korrespondensiya sifatida berilgan: inkassatorga topshirish `Dt 5710 / Kt 5010`, bankka tushish `Dt 5110 / Kt 5710`. Karta/QR ekvayring tushumi — "pul o'tkazmalari" ma'nosida. `13` §2.2/§2.18/§2.18a interim qoidasi NSBU 21 ga mos.
2. **Komissiya — 9430 "Boshqa operatsion xarajatlar", 9410 emas.** NSBU 21 410-band 9430 tarkibida *"bank va depozitariy xizmatlarining to'lovlari"*ni to'g'ridan-to'g'ri sanaydi. VMQ-54 Nizomi 2.3.12-band ham *"Bankning … xizmatlariga haq to'lash"*ni 2.3 "Boshqa operatsion xarajatlar" guruhiga kiritadi. Ekvayring (bank), UzQR (bank-ekvayer), inkassa (bank) komissiyalari bank xizmati hisoblanadi → 9430. Click/Payme/Uzum to'lov tashkiloti komissiyasi bank xizmati emas, lekin moliyaviy vositachilik xizmati sifatida xuddi shu guruhga tushadi — buni buxgalter tasdiqlaydi; interim — 9430.
3. **"Вид оплаты" tuzilmasi** (1C eksporti uchun, `33-1c-integratsiya.md`). Tavsiya (D): 1C `ВидыОплатОрганизаций` xaritasi kaliti — `(payment_method, ekvayer kontragenti)`. `card` — terminal bankiga bittadan, `uzqr` — tenant'ning UzQR ekvayer bankiga bitta, `click`/`payme`/`uzum` — har provayderga bitta; hisob har doim 5710. Bizning `ledger_entries.analytics.payment_method` yetarli, 1C xaritasi BO-22 ustasida to'ldiriladi. Bitta tenant'da bir nechta terminal-bank bo'lsa, `cash_registers`ga ixtiyoriy `acquirer_counterparty_id` qo'shiladi (MVP'dan keyin, `bank_accounts` OQ-035 bilan birga).

### Dalil
- NSBU 21 (AV reg. 3593, 27.12.2024) Yo'riqnoma: *«237. Йўлдаги пул маблағлари (нақд пулга ва пул ўтказиш орқали маҳсулот сотишдан олинган даромад) тўғрисидаги ахборотларни умумлаштириш 5710 «Йўлдаги пул маблағ (ўтказма)лари» ҳисобварағида амалга оширилади.»*; *«238. … сақлаш жойидан чиқиб кетган, аммо мўлжалланган жойига етиб бормаган пул маблағлари (инкассаторга берилган сотишдан олинган тушумлар, пул ўтказмалари) ҳисобга олинади. Ушбу ҳисобварақ транзит ҳисобварақ ҳисобланади…»*; 239-band jadvali: *«1. Кассадаги нақд пуллар … инкассаторга топширилиши — 5710 / 5010, 5020»*; *«2. Келиб тушган пул ўтказмалари бўйича харидорларнинг қарзлари қопланиши — 5710 / 4010»*; *«7. Йўлдаги пул маблағлари банкдаги ҳисоб-китоб ҳисобварағига келиб тушиши — 5110 / 5710»* — [lex.uz/docs/7282737](https://lex.uz/docs/7282737).
- O'sha hujjat, 410-band: *«9430 «Бошқа операцион харажатлар» ҳисобварағида кадрлар тайёрлаш …, ахборот, аудиторлик ва маслаҳат хизматлари учун тўлов харажатлари, … банк ва депозитарий хизматларининг тўловлари, зарарлар, жарималар, пенялар ва бошқа операцион фаолият жараёнида вужудга келадиган … харажатлар акс эттирилади.»*
- VMQ-54 (05.02.1999) Nizomi: *«2.3. Бошқа операция харажатлари»* → *«2.3.12. Банкнинг, Қимматли қоғозлар марказий депозитарийсининг ва қимматли қоғозлар бозори профессионал иштирокчиларининг хизматларига ҳақ тўлаш.»* — [lex.uz/docs/264422](https://lex.uz/docs/264422).

### Ishonch
5710 — **yuqori** (Yo'riqnomada aynan shu korrespondensiyalar). 9430 (bank komissiyasi) — **yuqori**. 9430 (to'lov tashkiloti komissiyasi) — **o'rta-yuqori**. "Вид оплаты" — muhandislik tavsiyasi.

### Spec'ga ta'sir
1. `13-provodka-qoidalari.md` §2.18a jadval 2-qatori: `| 2 (komissiya > 0) | 9410 (*taxmin*) | 5710 | …` → `| 2 (komissiya > 0) | **9430** | 5710 | commission_amount (ekvayring/UzQR/to'lov tashkiloti/inkassa komissiyasi) — NSBU 21 Yo'riqnoma 410-b. ("bank va depozitariy xizmatlarining to'lovlari"), VMQ-54 Nizom 2.3.12 | payment_method, filial |`. 236-qatordagi misol: `Dt 9410 / Kt 5710 = "9500.00"` → `Dt 9430 / Kt 5710 = "9500.00"`.
2. `13` boshidagi ogohlantirish 6-band:
   > 6. Karta/UzQR/Click/Payme/Uzum tushumlari va inkassa **5710** orqali (NSBU 21 Yo'riqnoma 237–239-b. — `Dt 5710/Kt 5010` va `Dt 5110/Kt 5710` aynan misol qilingan), komissiya — **9430** (410-b.). Manbali; buxgalter faqat tasdiqlaydi (to'lov tashkiloti komissiyasining 9430 ga tushishi — talqin).
3. `13` §1 jadvali 5710 qatori "Manba" ustuni → "lex.uz NSBU 21 Yo'riqnoma 237–239-b. — **tasdiqlangan**; karta/QR tushumi = 'pul o'tkazmalari' talqini". 9430 qatori → "… shu jumladan bank/ekvayring komissiyasi (410-b.)". `13` "Asosiy xulosalar" 8-band va "Ochiq savollar" 3-band — "(9410, *taxmin*)" → "(9430, NSBU 21 410-b.)".
4. `13` §2.17 (xarajat toifalari) — "Bank xizmatlari (hisob raqam xizmati, RKO)" toifasini qo'shish → 9430.
5. `26` B#34 — interim "To'g'ridan-to'g'ri **5110**" → "5710 + `bank_settlements`, komissiya 9430 (qaror #42, P3 manbali)" — bu OQ-101 nomuvofiqlik 1-bandini ham yopadi.
6. `01-qarorlar.md` #42 — oxiriga: "Komissiya — 9430 (NSBU 21 410-b.)."
7. `33-1c-integratsiya.md` (BO-22 ustasi, "to'lov turi↔Вид оплаты") — "xarita kaliti `(payment_method, ekvayer kontragenti)`, hisob 5710".

### Holat
**YOPILDI** (manbali). Buxgalter ko'rib chiqadi — bloklamaydi; P7 (OQ-066…074) bilan kelishilgan holda 9430 ni hisoblar rejasi jadvaliga kiritadi. **P7 diqqatiga:** `13` §1 da 9430 bor, yangi hisob qo'shish kerak emas.

---

## 6. OQ-038 — Bank ko'chirmasi importi formati (`statement_import`) va ochiq banking (PQ-359, 2026-09-01)

### Javob
1. **Ochiq banking hali yo'q.** PQ-359 (27.11.2025) ochiq bankingni 2026-09-01 gacha joriy etishni topshirgan: konsepsiya, "yo'l xaritasi", cheklangan ishtirokchilar bilan pilot. 2026-10-16 holatida lex.uz qidiruvida ("очиқ банкинг", "ochiq banking", "Open banking", "открытый банкинг") CBU'ning ochiq banking normativ hujjati topilmadi — faqat PQ-359'ning o'zi chiqadi. Demak bank hisob ma'lumotiga standartlashgan API orqali kirish **yo'q**. Bo'lsa ham pilot bosqichida, uchinchi tomon ERP uchun mavjud emas.
2. **Fayl formati — de-fakto 1CClientBankExchange.** O'zbekiston banklarining bank-klient tizimlari ko'chirmani 1C uchun `1CClientBankExchange` (.txt, `СекцияРасчСчет`/`СекцияДокумент`) formatida beradi. Ayrimlari xml, ba'zan faqat Excel beradi (keyin 1C formatiga o'giriladi). Bu buxgalterlar uchun standart oqim. Kapitalbank DiBank ko'chirmani to'g'ridan-to'g'ri 1C/Didox'ga uzatadi (`03-efaktura-va-tolov.md` §3.2).
3. **Provayder hisob-kitob ma'lumotlari:**
   - UzQR — kabinetdagi tranzaksiyalar tarixi (≤ 35 kun), CSV eksport; komissiya ma'lumoti operator→ishtirokchilarga beriladi (CBU qoidalari 6-b.), merchantga alohida komissiya hisoboti formati e'lon qilinmagan.
   - Payme — `GetStatement` (merchant tomonda majburiy; Payme bilan solishtirish uchun).
   - Click — `payment/status_by_mti`.
   - Uzum Checkout — `getReceipts`.

   Bularning hech biri ekvayerning bankka o'tkazgan **netto summasi va ushlangan komissiyani** bitta hujjatda bermaydi: netto — bank ko'chirmasidagi kirim, komissiya = gross − netto.
4. **Ekvayer (terminal) hisob-kitob hisoboti namunalari** — ochiq manbada topilmadi (bank kabinetlari login talab qiladi).

### Dalil
- PQ-359 7-band (a): *«2026-yil 1-sentabrga qadar banklar, toʻlov tashkilotlari va moliyaviy texnologiyalar bozori ishtirokchilari oʻrtasida xavfsiz va standartlashgan maʼlumot almashinuvini taʼminlaydigan "ochiq banking" tizimini joriy etish»*; ilova: *«1. "Ochiq banking" tizimi konsepsiyasi va boshqaruv modelini shakllantirish … 3. "Ochiq banking" tizimini joriy etish "yoʻl xaritasi"ni ishlab chiqish, cheklangan ishtirokchilar bilan pilot bosqichini oʻtkazish»* — [lex.uz/docs/-7864242](https://lex.uz/docs/-7864242).
- lex.uz qidiruvi (2026-10-16): `lex.uz/uz/search/all?query=ochiq banking` va boshqa variantlari — ochiq banking qoidasi chiqmadi (natijalar: PQ-359, "ochiq valyuta pozitsiyasi" hujjatlari va h.k.).
- 1C formati: *«Основной формат — 1CClientBankExchange (текстовый файл .txt с секциями «СекцияДокумент», «СекцияРасчСчет»). Некоторые банки отдают выписку в xml. … Перед первой выгрузкой банка в 1С уточните в банке поддерживаемый формат и кодировку.»* (misol — Kapitalbank bank-klientidan yuklash) — [bss.uz, 2026-09-30](https://www.bss.uz/article/4939-vygruzka-banka-v-1s-kak-zagruzit-vypisku-i-otpravit-platezhki-v-klient-bank) (ikkilamchi, O'zbekiston buxgalteriya portali).
- UzQR eksporti — §3 dalili (pptx 15/17-slaydlar). Payme `GetStatement` — §2 dalili. CBU qoidalari 6-band: *«Operator … ushbu hisob-kitoblar va komissiyalar toʻgʻrisidagi maʼlumotlarni QR-kod tizimi ishtirokchilariga real vaqt rejimida yoki eng kamida hisob-kitoblar amalga oshirilgan kunning oʻzida taqdim etadi.»* — [lex.uz/docs/8139307](https://lex.uz/docs/8139307).

### Ishonch
Ochiq banking yo'qligi — **o'rta-yuqori** (lex.uz da yo'q; CBU ichki pilot e'lonlari bo'lishi mumkin, ular ERP'ga ta'sir qilmaydi). 1CClientBankExchange de-fakto standart — **o'rta-yuqori** (ikkilamchi manba + 1C amaliyoti; har bankning kodirovkasi/variantini tekshirish kerak). Ekvayer hisobotlari — **ma'lumot yo'q**.

### Spec'ga ta'sir
1. `13-provodka-qoidalari.md` §2.18a 1-xatboshi — `source='statement_import'` jumlasidan keyin qo'shish:
   > Import formati (MVP'dan keyin, FLAG): **1CClientBankExchange** (.txt; `СекцияРасчСчет` = hisob raqam/davr, `СекцияДокумент` = kirim qatorlari). Parser faqat **kirimlar**ni o'qiydi va ularni `bank_settlements` **draft**lariga taklif qiladi: `method`ni to'lovchi (ekvayer bank / Click / Payme / Uzum / MUNIS STIR) va to'lov maqsadi bo'yicha aniqlaydi; `gross_amount` — shu `method`/filial bo'yicha 5710 qoldig'idan Buxgalter tanlaydi; `commission_amount = gross − kirim`. Xml/Excel — keyinroq, bank so'roviga ko'ra. Ochiq banking API — PQ-359 bo'yicha joriy etilgach (2026-10-16 holatida normativ hujjat yo'q).
2. `09-ai-funksiyalar.md` AI-06 chegaralari (agar ko'chirma tahlilini eslatsa) — "manba: 1CClientBankExchange fayli; AI faqat moslashtirish taklifi, `post` — Buxgalter".
3. `research_notes/texnik/03-efaktura-va-tolov.md` §3.2 — "2026-09-01 ga rejalashtirilgan" → "muddat o'tdi, 2026-10-16 holatida normativ hujjat yo'q" (tadqiqot hujjatini yangilovchi agent uchun).

### Holat
**QISMAN.** Format savoli yopildi (1CClientBankExchange), ochiq banking holati aniqlandi (yo'q). **Ochiq qolgani:** ekvayer hisob-kitob hisoboti namunalari va tenant banklarining aniq eksport varianti (kodirovka, xml/Excel).
**Interim:** `source='manual'` (hozirgidek); `statement_import` — 1CClientBankExchange parseri bilan draft (Bosqich 6+).
**Kim beradi:** pilot tenant buxgalteri — o'z bankidan 1 oylik ko'chirma (anonimlashtirilgan) va terminal/UzQR hisob-kitob hisoboti namunasi. Bu E-klass emas: namuna parser testlari uchun kerak, qarorni bloklamaydi.

---

## 7. P3 doirasidagi qo'shimcha natijalar

### 7.1 OQ-031 — litsenziya tekshiruvi (inventar §12, P3 qatori)
**Javob:** har tenant o'z Click/Payme/Uzum/UzQR merchant hisobini ishlatsa va pul platformamiz hisobidan o'tmasa, bizning xizmatimiz **to'lov xizmati emas** → to'lov tashkiloti litsenziyasi talab qilinmaydi. O'RQ-578 14-moddasi to'lov xizmatlari qatoriga kirmaydiganlar orasida aynan shu holatni sanaydi.
**Dalil:** O'RQ-578 (01.11.2019) 14-modda: *«Quyidagilar boʻyicha xizmatlar koʻrsatish toʻlov xizmatlari jumlasiga kirmaydi: … uchinchi shaxslar ishtirokisiz qabul qilingan toʻlovlar boʻyicha pul mablagʻlarini toʻlov xizmatlarini yetkazib beruvchi tomonidan benefitsiar foydasiga oʻtkazishni amalga oshirish chogʻida yuridik shaxs boʻlgan benefitsiar, yakka tartibdagi tadbirkor va toʻlov xizmatlarini yetkazib beruvchi oʻrtasidagi axborot-kommunikatsiyaga oid va texnologik hamkorlikni taʼminlash.»* Qarama-qarshi tomondan, to'lov xizmatiga kiradi: *«elektron shakldagi toʻlovlarga ishlov berish va toʻlovni amalga oshirish uchun zarur axborotni bankka berish yoki mazkur toʻlovlar boʻyicha pul mablagʻlarini qabul qilish»* — [lex.uz/docs/-4575786](https://lex.uz/docs/-4575786).
**Ishonch:** o'rta-yuqori.
**Spec'ga ta'sir:** `15-xavfsizlik-va-audit.md` §4.1 / `21` §9 "Muhim ajratish"ga: "Platforma faqat texnologik vositachi (O'RQ-578 14-m., istisno ro'yxati); pul to'g'ridan-to'g'ri tenant hisobiga tushadi — to'lov tashkiloti litsenziyasi kerak emas. Split/pul yig'ish modeliga o'tish litsenziya talabini keltirib chiqaradi (taqiq)."
**Holat:** OQ-031 tavsiyasi (D) manba bilan tasdiqlandi. Asoschi qarorini kutadi.

### 7.2 `21` OS5 / §9 — "QR/onlayn to'lovda fiskal chekni kim chiqaradi" (P1 bilan kesishadi)
**Javob:** ikki model ham rasmiy API'da mavjud va **tanlov integratsiya turiga bog'liq**:
- **(A) To'lovni kassamiz boshlaydi** (dinamik QR, Click Pass, Uzum Dynamic QR/FastPay, dinamik UzQR, karta): fiskal chekni **kassamiz** chiqaradi va uning `ofd.soliq.uz` havolasini provayderga beradi — Click `ofd_data/submit_qrcode`, Payme Subscribe `receipts.set_fiscal_data`, Uzum `/dynamic-qr/.../fiscal` va FastPay `/fiscal`. UzQR uchun VMQ-393 aniq talab qiladi: *«ягона QR-код орқали амалга оширилган тўловларга ҳам назорат-касса техникаларидан мажбурий равишда чек берилиши шарт»*.
- **(B) To'lovni provayder boshlaydi** (mijoz ilovada statik QR'ni skanerlaydi yoki onlayn/obuna to'lovi): provayderning virtual fiskal moduli chekni chiqaradi — Payme Merchant API `SetFiscalData` *«Данные о фискализации чека»* (`terminal_id` — virtual fiskal modul), Click `ofd_data/submit_items` (`CommissionInfo` — merchant STIR/JShShIR, komissioner cheki), Uzum Fiscalization API.

**POS uchun qoida:** do'kon sotuvida har bir to'lov usulida chekni **faqat kassamiz** chiqaradi (A). Tenant'ning provayder kabinetida provayder tomonidan fiskalizatsiya o'chirilishi yoki "merchant fiskalizatsiya qiladi" rejimi tanlanishi kerak — aks holda **ikki marta fiskalizatsiya** bo'ladi (buxgalter.uz'da tasvirlangan "dublikatdan qo'rqish" muammosi). (B) faqat bizning obuna billingimiz (M17) uchun: platforma provayderi chek chiqaradi yoki biz `receipts.set_fiscal_data` bilan o'z chekimizni beramiz — P1 qaror qiladi.
**Ishonch:** yuqori (vendor API + VMQ-393).
**Spec'ga ta'sir:** `21` §9 to'rtinchi band ("Uchtasida ham fiskal chekni kim chiqarishi … ikki talqin") o'rniga:
> **Fiskalizatsiya qoidasi (P3, 2026-10-16):** do'kon sotuvida chekni har doim bizning kassamiz chiqaradi (VMQ-943 1-ilova 6-b.; 1a-ilova 2-b. VMQ-393 tahriri — UzQR uchun ham). Provayderga faqat chek havolasi yuboriladi (Click `submit_qrcode`, Payme `receipts.set_fiscal_data`, Uzum `/fiscal`). Tenant onboarding'ida provayder tomonidagi avtomatik fiskalizatsiya o'chirilganini tasdiqlash — BO-14 tekshiruv bandi. Provayder fiskalizatsiyasi (`SetFiscalData`, `submit_items`) — faqat platforma billingi (M17) uchun, P1 qarori bilan.
`21` OS5 — yopildi deb belgilash.

### 7.3 Spec nomuvofiqliklari (OQ-101 ga qo'shish)
1. `21` §9.1: "YTT'lar uchun ixtiyoriy" ↔ PQ-247 7-b. "a" (YTT uchun maxsus QR majburiy, 2026-01-01 dan) — §3 Spec'ga ta'sir 1.
2. `13` §2.18a: komissiya 9410 ↔ NSBU 21 410-b. (9430) — §5.
3. `12-db-sxema.md` `sale_payments` CHECK `uzqr`da `provider_tx_id` majburiy ↔ statik UzQR'da tranzaksiya ID'si yo'q — §3 Spec'ga ta'sir 5.
4. `21` §13: "Click — sandbox topilmadi" ↔ docs.click.uz Playground/Postman — §2.

---

## 8. Kim nimani tasdiqlaydi (bloklamaydi)

| Savol | Kim | Interim |
|---|---|---|
| Dinamik UzQR POS API spetsifikatsiyasi va test kaliti | CBU MUNIS (1835, t.me/uzqr_cbu_gsi) yoki tenant ekvayer banki | `UzQrPort` stub; statik UzQR qo'lda tasdiq bilan |
| Statik UzQR'ni offline/qo'lda tasdiqlashga ruxsat | **Asoschi** | Online'da ruxsat, offline — asoschi qaroriga qadar yo'q |
| "Karta turi" har karta to'lovidami yoki faqat ijtimoiy kartada | Yurist yoki OFD operatori (ixtiyoriy) | Har doim so'raladi, standart `personal` |
| 9430 — to'lov tashkiloti komissiyasi uchun ham | Buxgalter (P7 bilan) | 9430 |
| Bank ko'chirmasi va ekvayer hisoboti namunalari | Pilot tenant buxgalteri | `source='manual'` |
| Uzum Merchant API test kredensiali | Uzum menejeri | Mock |

---

## Manbalar

Barcha havolalar 2026-10-15/16 da ochildi.

**Normativ (lex.uz):**
- PF-246, 10.12.2025 — [lex.uz/uz/docs/-7897630](https://lex.uz/uz/docs/-7897630) (3-band "a", "b" (i)–(ii)).
- CBU Boshqaruvi 25.03.2026 dagi 5/11-son qarori, AV reg. 3817 (15.04.2026), "Toʻlovlarni amalga oshirishda yagona QR-kod orqali toʻlov xizmatlarini koʻrsatish qoidalari" — [lex.uz/docs/8139307](https://lex.uz/docs/8139307).
- VMQ 20.07.2026 dagi 393-son qarori — [lex.uz/docs/8343102](https://lex.uz/docs/8343102) (1-ilova 2-, 14-bandlar; Izoh — kuchga kirish sanalari).
- VMQ-943, 23.11.2019 (2026-10-16 tahriri) — [lex.uz/docs/4603329](https://lex.uz/docs/4603329) (1-ilova 2-, 6-, 7-bandlar; 1a-ilova 2-band; 2-ilova 3-, 6-bandlar).
- VMQ-610, 29.09.2025 (ijtimoiy karta, QQS qaytarish) — [lex.uz/docs/7747538](https://lex.uz/docs/7747538).
- PQ-247, 12.08.2025 — [lex.uz/docs/-7681520](https://lex.uz/docs/-7681520) (7-band "a").
- PQ-359, 27.11.2025 — [lex.uz/docs/-7864242](https://lex.uz/docs/-7864242) (7-band "a", ilova).
- O'RQ-578, 01.11.2019 "Toʻlovlar va toʻlov tizimlari toʻgʻrisida" — [lex.uz/docs/-4575786](https://lex.uz/docs/-4575786) (13–15-moddalar).
- NSBU 21 Yo'riqnomasi (AV reg. 3593, 27.12.2024) — [lex.uz/docs/7282737](https://lex.uz/docs/7282737) (237–239-, 410-bandlar).
- VMQ-54, 05.02.1999, Xarajatlar tarkibi nizomi — [lex.uz/docs/264422](https://lex.uz/docs/264422) (2.3, 2.3.12).
- MJtK — [lex.uz/docs/97664](https://lex.uz/docs/97664) (164-, 175-moddalar).

**Regulyator va banklar:**
- CBU press-relizi, 2026-07-01, "Система UzQR…" — [cbu.uz/ru/press_center/adverts/4092130/](https://cbu.uz/ru/press_center/adverts/4092130/); qo'llanma PDF — [cbu.uz/upload/medialibrary/19b/…/rus_uzqr.pdf](https://cbu.uz/upload/medialibrary/19b/di115k6xbunhm2883oawkbbaisgnyyo9/rus_uzqr.pdf).
- Ipoteka bank: UzQR qo'llanmasi (pptx) — [ipotekabank.uz/upload/rko/Instruction_UzQR.pptx](https://www.ipotekabank.uz/upload/rko/Instruction_UzQR.pptx); sahifa (2026-07-21) — [ipotekabank.uz/en/business/acquiring/qr-code/](https://www.ipotekabank.uz/en/business/acquiring/qr-code/); yangilik (2026-07-13) — [ipotekabank.uz/en/blog/news/the-central-bank-has-launched-new-UzQR-services/](https://www.ipotekabank.uz/en/blog/news/the-central-bank-has-launched-new-UzQR-services/).
- Ipak Yo'li bank, "Единый QR код" — [ru.ipakyulibank.uz/blog/business/ediniy-qr-kod-resheniye-dlya-vashego-biznesa](https://ru.ipakyulibank.uz/blog/business/ediniy-qr-kod-resheniye-dlya-vashego-biznesa).
- uzqr.uz (merchant kabineti, SPA; ochiq API hujjati yo'q — `/docs`, `/swagger`, `/openapi.json` SPA'ga qaytadi) — [uzqr.uz](https://uzqr.uz).

**Vendor hujjatlari:**
- Payme — [developer.help.paycom.uz](https://developer.help.paycom.uz/): `/metody-merchant-api/setfiscaldata`, `/metody-merchant-api/getstatement`, `/metody-subscribe-api/` (+ `receipts.create`, `receipts.set_fiscal_data`), `/protokol-subscribe-api`, `/pesochnitsa`.
- Click — [docs.click.uz](https://docs.click.uz/): `/merchant-api/requests`, `/merchant-api/click-pass`, `/merchant-api/fiscalization`, `/testing/playground`, `/testing/postman`, `/additional/shop-split` (matn sayt JS bandlaridan); tariflar — [business.click.uz/ru](https://business.click.uz/ru).
- Uzum — [developer.uzumbank.uz/en/](https://developer.uzumbank.uz/en/): `merchant`, `dynamicqr`, `fastpay`, `checkout`, `fiscalization` (OpenAPI spetsifikatsiyalari `redocusaurus/en_*.yaml`, sayt JS'ida).

**Ikkilamchi (amaliyot, kontekst):**
- gazeta.uz, 2026-06-22 — [gazeta.uz/oz/2026/06/22/uzqr/](https://www.gazeta.uz/oz/2026/06/22/uzqr/).
- kun.uz, 2026-07-03 — [kun.uz/ru/news/2026/07/03/tsb-s-poyavleniyem-uzqr-…](https://kun.uz/ru/news/2026/07/03/tsb-s-poyavleniyem-uzqr-predprinimateli-ne-obyazany-ubirat-qr-kody-drugix-servisov-32c9cc).
- podrobno.uz, 2026-07-30 — [podrobno.uz/cat/economic/chto-izmenilos-posle-zapuska-uzqr-…](https://podrobno.uz/cat/economic/chto-izmenilos-posle-zapuska-uzqr-i-pochemu-vokrug-nego-mnogo-voprosov/).
- buxgalter.uz, 2026-04-14 — [text214588](https://buxgalter.uz/uz/publish/doc/text214588_yagona_qr-kod_buyicha_tulovlarni_fiskallashtirishni_kim_taminlashi_kerak); 2026-04-16 — [text214616](https://buxgalter.uz/publish/doc/text214616_utverjdeny_pravila_ispolzovaniya_edinogo_qr-koda_pri_sovershenii_platejey_po_up-246); 2026-07-01 — [text215905](https://buxgalter.uz/uz/publish/doc/text215905_1_iyuldan_boshlab_yuridik_shahslar_uchun_yagona_qr-kod_majburiy_buladi_-_boshqa_qr-kodlardan_foydalanish_mumkinmi).
- bss.uz, 2026-09-30 — [bss.uz/article/4939-…](https://www.bss.uz/article/4939-vygruzka-banka-v-1s-kak-zagruzit-vypisku-i-otpravit-platezhki-v-klient-bank).
- Oldingi tadqiqot: `research_notes/texnik/03-efaktura-va-tolov.md` §2.1–§2.5, §3.1–§3.2 (2026-10-14).

**Topilmadi / ochilmadi:** UzQR POS API texnik hujjati (ochiq emas); Kapitalbank UzQR qo'llanmasi PDF (Cloudflare 403); CBU ochiq banking qoidasi (lex.uz da yo'q); ekvayer hisob-kitob hisoboti namunalari; business.payme.uz joriy tariflari (sahifa JS, bu safar qayta o'qilmadi).
