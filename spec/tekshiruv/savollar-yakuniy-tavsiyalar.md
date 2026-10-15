# Savollar — yakuniy tavsiyalar (qabul agenti, Opus)

*2026-10-15 · Kirish: `savollar-research-1-fiskal.md`, `savollar-research-2-buxgalteriya.md`, `savollar-research-3-biznes.md`, `savollar-research-4-ai-xavfsizlik.md`; savollar ro'yxati — `kamchiliklar-yakuniy.md` §3 (1–16). Kontekst: `00-qarorlar.md`, `01-mahsulot/06-mvp-chegarasi.md` (Start 49 000 / Biznes 129 000 / Pro 249 000 so'm), `02-arxitektura/06-nofunksional-talablar.md` §11 (tenant xarajati). Faktlar 2026-10-15 kuni WebFetch bilan qayta ochildi (WebSearch byudjeti tugagan — faqat to'g'ridan-to'g'ri sahifalar).*

*Belgilar: **TASDIQLANDI** — manba sahifasi ochildi va da'voni aytadi; **TASDIQLANMADI** — sahifa yopiq (403/paywall) yoki manba uchinchi tomon, da'vo na tasdiqlandi, na rad etildi; **NOTO'G'RI** — manba boshqa narsani aytadi yoki da'vo noto'g'ri talqin qilingan.*

---

## (a) Faktlarni tekshirish jadvali

| # | Da'vo (qaysi research) | Manba | Natija | Izoh |
|---|---|---|---|---|
| F1 | Rahmat POS virtual kassa **123 600 so'm/oy**, onlayn-NKM 100 000, terminal 0, SUNMI P3 990 000; ochiq API; markirovka qo'llab-quvvatlanadi (R1) | [rhmt.uz/uz/pos/virtual-kassa](https://rhmt.uz/uz/pos/virtual-kassa/) | **TASDIQLANDI** | Barcha raqamlar va "ochiq API bilan ommabop POS tizimlariga integratsiya" iborasi sahifada bor |
| F2 | Poster: **E-POS Integration $10/oy** (R1) | [joinposter.com/en/applications](https://joinposter.com/en/applications), [.../epos](https://joinposter.com/en/applications/epos) | **NOTO'G'RI** | Marketplace ro'yxatida E-POS Integration — **"Free"**; E-POS'ning o'z (fiskal) haqi sahifada yo'q. $10 hech qayerda topilmadi |
| F3 | Poster: "Rahmat POS/Multikassa ($5/oydan)" — bitta hamkor sifatida (R1) | [joinposter.com/en/applications/rahmat](https://joinposter.com/en/applications/rahmat), [.../multikassa](https://joinposter.com/en/applications/multikassa) | **NOTO'G'RI (birlashtirilgan)** | Bular **ikki alohida** ilova: Multikassa — "$5/oydan" (bu Poster'ning integratsiya haqi); Rahmat — QR to'lov+fiskal chek, 1,5–2% tranzaksiyadan + $1/oy |
| F4 | Multikassa: $28 ulanish + $8/oy xizmat + $5/oy integratsiya = **$13/oy ≈ 155 500 so'm** "partner to'lovi" (R3) | [joinposter.com/en/applications/multikassa](https://joinposter.com/en/applications/multikassa) | **Raqamlar TASDIQLANDI, xulosa NOTO'G'RI** | $5 — **Poster'ning** o'z haqi, Multikassa'niki emas. Bizga tegishli hamkor haqi — **$8/oy ≈ 96 000 so'm/kassa** (+$28 ≈ 335 000 so'm bir martalik) |
| F5 | REGOS VCR: 1 BHM/yil fiskal modul + operator; oylik xizmat REGOS foydalanuvchisiga 0, boshqalarga **100 000 so'm/oy** (R1, R3) | [regos.uz/uz/product/regos-vcr/faq](https://regos.uz/uz/product/regos-vcr/faq) | **TASDIQLANDI (+ aniqlik)** | Hammasi **har bir virtual kassa uchun**. Qo'shimcha: ulashda yana **1 BHM bir martalik** (har kassa). Yillik 1 BHM — "Yangi texnologiyalar" markaziga (ikkinchi darajali manba, lex.uz'da so'zma-so'z ko'rilmadi) |
| F6 | REGOS virtual kassa qo'shimchasi **+75 000 so'm/oy** (spec, R1) | regos.uz/ru/price (bu sessiyada ochilmadi) | **TASDIQLANMADI (eskirgan bo'lishi mumkin)** | VCR FAQ REGOS obunachilariga 0 so'm deydi; 75 000 — REGOS'ning **o'z mijozlari** uchun qo'shimcha, uchinchi tomon uchun hamkor narxi emas. R3 uni "partner diapazoni"ning pastki chegarasi qilib olgan — noto'g'ri qiyos |
| F7 | "Davlat reyestriga ro'yxatdan o'tish **bepul, 4 soatda**" — o'z dasturimiz uchun (R3, my.gov.uz/service/627) | [my.gov.uz/uz/service/627](https://my.gov.uz/uz/service/627) | **NOTO'G'RI (talqin)** | Bu xizmat — **do'konning** onlayn-NKM/kassasini ro'yxatga olish (bepul, 1 ish kuni, keyin texnik xizmat markaziga borish). Dastur ishlab chiquvchining **Davlat reyestriga kiritilishi** — boshqa jarayon: VMQ-943, 4-ilova, ~50 ish kuni, narxi noma'lum (R1 to'g'ri). R3'ning "Variant B" xarajat hisobi shu sababli faqat fiskal modul to'lovi bo'yicha to'g'ri, "bepul" qismi isbotlanmagan |
| F8 | MoySklad UZ sotuvni **E-POS orqali** soliqqa yuboradi, Asl belgisi integratsiyasi bor (R1) | [moysklad.uz](https://www.moysklad.uz/) | **TASDIQLANDI** | "Регистрация продаж в налоговой Узбекистана через один клик" + AslBelgisi |
| F9 | CRPT Turon: ishtirokchi (Participant) o'zi "API Key Manager" roli bilan API kalit yaratadi va uchinchi tomon dasturga beradi; "Integrator" — alohida maqom (R1) | [help.crpt-turon.uz/.../36062776211601](https://help.crpt-turon.uz/hc/uz/articles/36062776211601-Foydalanuvchi-profili-API-kalit-yaratish), [Partner Program](https://help.crpt-turon.uz/hc/en-us/articles/18977054012049--Partner-Program-of-LLC-CRPT-TURON) | **TASDIQLANMADI** | Ikkala sahifa ham **403**. Da'vo faqat qidiruv parchalariga tayanadi (R1 o'zi ham shunday yozgan). Xat 2 javobisiz qaror qabul qilinmasin |
| F10 | buxgalter.uz: markirovkalangan tovar xaridordan **kod aks ettirilgan EHF yoki NKM qaytarish cheki** asosida qaytariladi (R1) | [buxgalter.uz text186704](https://buxgalter.uz/oz/publish/doc/text186704_raqamli_markirovkalanadigan_tovarlarni_hisobga_olishga_oid_muhim_savollar) | **TASDIQLANDI** | So'zma-so'z iqtibos sahifada bor |
| F11 | Eskiz SMS **95 so'm**, obuna to'lovi yo'q (R3) | [eskiz.uz/uz/sms](https://eskiz.uz/uz/sms) | **TASDIQLANDI** | Reklama SMS — 175 so'm; yangi foydalanuvchiga 100 SMS bepul |
| F12 | Faktura.uz ochiq API (SendDocument, SignDocument, GetDocumentStatus, CheckCompanyExist, token) (R2) | [api.faktura.uz/help](https://api.faktura.uz/help/) | **TASDIQLANDI** | Ochiq o'qiladi. Diqqat: token `grant_type=password` bilan olinadi (tenant Faktura.uz login/parolini saqlash kerak bo'lishi mumkin — `tenant_secrets`, xavfsizlik ko'rib chiqilsin) |
| F13 | REGOS ↔ Faktura.uz tayyor integratsiya moduli (R2) | [apps.regos.uz/.../edo_fakturauz](https://apps.regos.uz/integration/details/edo_fakturauz?lang=en) | **TASDIQLANDI** | Kiruvchi faktura → avtomatik kirim; chiquvchi yuborish |
| F14 | NSBU 21 hisob rejasida **4910 "Резерв по сомнительным долгам"**; zaxira yil oxiri inventarizatsiyasi asosida, har qarz alohida baholanadi (R2) | [buxgalter.uz text150192](https://buxgalter.uz/publish/doc/text150192_schet_4910_rezerv_po_somnitelnym_dolgam) | **Hisob nomi TASDIQLANDI; baholash tartibi TASDIQLANMADI** | Ochiq qism faqat "резервы по сомнительным долгам — счет 4910" deydi; qolgani Buxgalter Pro paywall ortida. R2 keltirgan iqtibos tekshirib bo'lmadi |
| F15 | **NSFO №2** 2027-01-01'dan kuchga kiradi; "3810-son buyruq" (R2) | [lex.uz/ru/docs/8130720](https://lex.uz/ru/docs/8130720) | **Sana TASDIQLANDI; rekvizit noaniq** | lex.uz: buyruq **№345, 2026-03-12**, kuchga kirish **2027-01-01**. "3810" — ehtimol AV ro'yxat raqami; spec'da "№345 (AV ro'yxati — tekshirilsin)" deb yozilsin |
| F16 | Azure: "target 80% or higher… financial — close to 100%" (R4) | [learn.microsoft.com — accuracy/confidence](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-accuracy-confidence?view=doc-intel-2.1.0) | **TASDIQLANDI, lekin kontekst boshqa** | Bu — **custom model o'qitish aniqligi** haqida, maydon chegarasi emas. Microsoft maydon ishonchini "avtomatik qabul yoki odam tekshiruviga yo'naltirish" uchun ishlatishni aytadi — per-field yo'naltirish g'oyasi tasdiqlanadi |
| F17 | Azure per-field chegaralar: InvoiceTotal ≥0.95, VendorName 0.90, InvoiceDate 0.85 (R4) | theneuralbase.com (uchinchi tomon) | **TASDIQLANMADI** | Microsoft hujjatida bunday raqamlar yo'q — uchinchi tomon tavsiyasi |
| F18 | AWS: "~50% arxiv matni, ≥90% moliyaviy qaror" (R4) | parseur.com (uchinchi tomon) | **TASDIQLANMADI** | AWS rasmiy manbasi keltirilmagan |
| F19 | Celion (Toshkent): veb/API/tarmoq pentest, ISO 27001/PCI-DSS/GDPR'ga moslangan hisobot; ONESEC (Toshkent, Chilonzor): pentest; narx ochiq emas (R4) | [celion.io](https://celion.io/en/penetration-testing), [onesec.uz/en](https://onesec.uz/en) | **TASDIQLANDI** | Ikkalasida narx yo'q — faqat so'rov orqali. ONESEC sotuv: +998 50 151 50 14, info@onesec.uz |
| F20 | 1 BHM 2026-yilda ≈ 412 000–440 000 so'm (R1, R3) | — | **TASDIQLANMADI** | Quyidagi hisoblarda 412 000–440 000 diapazoni ishlatildi; buxgalter tasdiqlasin |

**Xulosa:** asosiy narx faktlari (Rahmat, REGOS VCR, Eskiz, Faktura.uz, buxgalter.uz qaytarish cheki, NSFO №2 sanasi, Celion/ONESEC) tasdiqlandi. **Uchta noto'g'ri:** F2 (E-POS $10), F3/F4 (Poster narxlari noto'g'ri bo'lingan — hamkor haqi 155 500 emas, ~96 000), F7 (do'kon kassasini ro'yxatga olish dasturchi reyestri bilan adashtirilgan). CRPT API kaliti (F9) — eng muhim tasdiqlanmagan fakt.

---

## (b) Ziddiyatni hal qilish: fiskal yo'l (research-1 vs research-3)

### Ziddiyat
- **R1:** pilot — reyestr hamkori orqali (tez), parallel — o'z reyestr arizasi.
- **R3:** hamkor haqi (75 000–155 500 so'm/oy) Start (49 000) marjasini yo'q qiladi → o'z reyestri + virtual kassa pullik qo'shimcha.

### Tuzatilgan raqamlar (F4–F7 asosida, har bir kassa uchun)
| Yo'l | Oylik xarajat/kassa | Bir martalik | Manba holati |
|---|---|---|---|
| Hamkor — Multikassa | ~96 000 so'm ($8) | ~335 000 so'm ($28) | Tasdiqlangan (Poster narxi; bizga ulgurji narx muzokara qilinadi) |
| Hamkor — REGOS VCR (REGOS bo'lmagan foydalanuvchi) | 100 000 + 1 BHM/yil (~34–37 000) ≈ **134–137 000** | 1 BHM (~412–440 000) | Tasdiqlangan (REGOS FAQ) |
| Hamkor — Rahmat virtual kassa | 123 600 | — | Tasdiqlangan (chakana narx) |
| **O'z reyestrimiz** | 1 BHM/yil ÷ 12 ≈ **34 000–37 000** (agar bu to'lov hamma uchun majburiy bo'lsa) | 1 BHM ulash + reyestr/sertifikat xarajati (**noma'lum**) | Fiskal modul to'lovi — ikkinchi darajali manba; reyestr narxi — Xat 1 |

**Muhim:** o'z reyestrimiz bilan ham fiskal modul to'lovi (~35 000 so'm/kassa) qoladi. Start'ning OFD'siz xarajati: hosting 20 500 + AI 2 000–5 000 + SMS 1 900–4 750 (Eskiz) + Click/Payme ~1 000 = **~25 400–31 250 so'm** → marja **~17 750–23 600 so'm**. Fiskal modul qo'shilsa jami ~60 000–68 000 so'm > 49 000. Ya'ni **"virtual kassa Start ichida bepul" va'dasi hech qaysi yo'lda zararsiz emas** — R3 bu jihatda to'g'ri. Biznes (129 000, 3 kassagacha) ham 3 × 35 000 = 105 000 fiskal xarajat bilan deyarli nolga tushadi — shuning uchun qaror barcha tariflarga tegishli.

### Yagona tavsiya
1. **Birinchi kun — o'z reyestr arizasini boshlash** (VMQ-943, 4-ilova; ~50 ish kuni ≈ 2,5–3 oy) va Xat 1'da reyestr narxini so'rash. Bu — asosiy, uzoq muddatli yo'l.
2. **Pilot (10–20 do'kon, ariza tasdiqlanguncha) — bitta reyestr hamkori orqali** (Multikassa yoki E-POS Communicator — qaysi biri uchinchi tomon ko'p-tenant SaaS'ga API va ulgurji narx bersa; maqsad ≤ 100 000 so'm/kassa). Pilot do'konlari uchun bu haqni **biz to'laymiz** — marketing xarajati sifatida: 20 kassa × ~100 000 = **~2 mln so'm/oy**, 3 oyga ~6 mln + ulanishlar 20 × 335 000 ≈ 6,7 mln → **jami ≤ ~13 mln so'm** cheklangan byudjet. Kod `FiscalAdapter` porti ortida bo'ladi, shuning uchun keyin almashtirish arzon.
3. **Narx modeli (hamma tariflar):** asosiy tarif narxlari o'zgarmaydi (Start 49 000 / Biznes 129 000 / Pro 249 000), lekin **virtual kassa — har bir kassa uchun alohida qo'shimcha: +39 000 so'm/oy** (fiskal modul ~35 000 + ~4 000 zahira). Start + 1 virtual kassa = **88 000 so'm** — baribir REGOS (69 000 + 75 000 = 144 000) dan arzon. O'z fiskal kassasi (onlayn-NKM) bor do'kon qo'shimchani olmaydi. `06-mvp-chegarasi.md` §3.3'dagi "virtual kassa narxga kiradi" tamoyili shunga yangilanishi kerak.
4. **Ommaviy sotuv o'z reyestrimiz tasdiqlangach boshlanadi.** Agar reyestr 6 oydan ko'p cho'zilsa yoki rad etilsa — hamkor orqali davom etiladi, qo'shimcha narxi **hamkor narxi + ~10%** (taxminan 105 000–135 000 so'm/kassa) qilib, mijozga ochiq "o'tkaziladigan to'lov" sifatida ko'rsatiladi; Start bu holatda ham marjada qoladi.
5. **Ochiq qoladi:** 1 BHM/yil to'lovi o'z reyestri yo'liga ham tegishlimi (agar yo'q bo'lsa, qo'shimcha narxi pasaytiriladi), reyestr/sertifikat narxi, hamkorning ulgurji narxi.

---

## (c) 16 savol — yakuniy tavsiyalar

Format: **Savol — Tavsiya — Nega — Ishonch — Keyin tekshiriladi.**

**1. Rol limitlari (#43)**
- **Tavsiya:** Standart limitlar: kassir chegirmasi PIN'siz **5% gacha**, chek bilan qaytarish PIN'siz **100 000 so'mgacha** (chek yo'q bo'lsa — har doim PIN), kassadan pul olish PIN'siz **50 000 so'mgacha**; chekni bekor qilish (void) kassirga limitsiz, lekin audit bilan. Egasi istalgan raqamni o'zgartira oladi.
- **Nega:** Hech bir raqobatchi (Loyverse, Square, BILLZ, REGOS) tayyor raqam bermaydi — hammasi "yoqish/o'chirish + PIN"; bizning kichik standart raqamlar kundalik mayda amallarni to'xtatmaydi, katta summani nazoratda saqlaydi.
- **Ishonch:** o'rta (mexanizm — yuqori; raqamlarning o'zi — taxmin).
- **Keyin tekshiriladi:** Pilotda PIN so'rovlari soni va Egalar raqamlarni qanchaga o'zgartirgani.

**2. Fiskal yo'l + pilot uskunasi (K10/#55/#23)**
- **Tavsiya:** O'z virtual kassamizni Davlat reyestriga kiritish arizasini darhol boshlaymiz; pilotni (10–20 do'kon) reyestr hamkori orqali, haqini o'zimiz to'lab (≤ ~13 mln so'm) o'tkazamiz; virtual kassa barcha tariflarda alohida **+39 000 so'm/oy/kassa** qo'shimcha bo'ladi. Pilot uskunasi: mavjud telefon/PC + USB skaner + 58 mm ESC/POS printer (Xprinter XP-58 klassi), jami ~0,9 mln so'm/kassa; tarozi va Android POS terminal pilotda shart emas.
- **Nega:** Hamkor haqi (~96 000–137 000 so'm/kassa) Start narxidan katta, o'z reyestrimizda ham ~35 000 so'm fiskal modul to'lovi qoladi — shuning uchun virtual kassani bepul berib bo'lmaydi; hamkor faqat reyestr kutilayotgan vaqtni yopadi (batafsil — (b) bo'lim).
- **Ishonch:** o'rta-yuqori (hamkor narxlari tasdiqlangan; reyestr narxi va 1 BHM qo'llanishi — yo'q).
- **Keyin tekshiriladi:** Xat 1 javobi (reyestr narxi/muddati, 1 BHM to'lovi o'z yo'limizga tegishlimi); Multikassa/E-POS'dan ulgurji narx va ko'p-tenant API shartlari; 2026-yil BHM qiymati.

**3. CRPT (Asl belgisi) MVP'da (Q5, #24)**
- **Tavsiya:** Ha, markirovkalangan tovar sotuvi MVP'ga kiradi: har bir do'kon o'zining bepul "ishtirokchi" kabinetidan API kalit oladi va tizimimizga kiritadi; agar bu yo'l Xat 2 javobi bilan rad etilsa — reyestr hamkori orqali proksi. Ikkalasi ham ishga tushmasa — markirovkalangan tovarni sotish tizimda bloklanadi (CRPT'siz sotilmaydi).
- **Nega:** 2026-07-01'dan kassada kodni avtomatik tekshirish majburiy (23-son qaror), demak CRPT'siz sotish qonunga zid; kalit yo'li rasmiy integrator maqomini kutmasdan eng tez yo'l.
- **Ishonch:** o'rta (CRPT yordam sahifalari 403 — API kalit mexanizmi faqat qidiruv parchalaridan ma'lum).
- **Keyin tekshiriladi:** Xat 2 (CRPT Turon): uchinchi tomon SaaS ishtirokchi kalitidan foydalanishi rasman ruxsat etilganmi; sotuv OFD orqali avtomatik CRPT'ga boradimi.

**4. E-faktura operatori (#26)**
- **Tavsiya:** MVP'da faqat Faktura.uz; Didox — MVP'dan keyingi birinchi integratsiya.
- **Nega:** Faktura.uz'ning API hujjati ochiq va tekshirildi, REGOS uni allaqachon ishlatmoqda; Didox hujjati login ortida, faqat norasmiy SDK bor.
- **Ishonch:** yuqori.
- **Keyin tekshiriladi:** Operatorlararo roaming (kontragent Didox'da bo'lsa ham faktura yetib boradimi); Faktura.uz narxi va sandbox; `grant_type=password` sababli tenant parolini saqlash xavfsizligi.

**5. Offline markirovka — qaytarish va ko'chirish (Q8, #25a)**
- **Tavsiya:** O'z filiallar/omborlar orasida ko'chirish offline'da ruxsat (keyin sinxronlanadi, audit bilan); markirovkalangan tovarni **qaytarish faqat internet bor paytda** — offline'da qaytarish tugmasi bloklanadi.
- **Nega:** Qaytarish uchun kod yozilgan rasmiy qaytarish cheki kerak (buxgalter.uz, tasdiqlandi) va firibgarlik xavfi yuqori; ichki ko'chirishda egasi o'zgarmaydi, 72 soatlik qoida subyektlar o'rtasidagi ko'chirishga tegishli ko'rinadi.
- **Ishonch:** ko'chirish — o'rta; qaytarish — o'rta (ehtiyotkor tanlov, qonun talabi tasdiqlangan).
- **Keyin tekshiriladi:** Xat 2 — ichki ko'chirish CRPT'ga xabar qilinadimi; e-TTN ichki ko'chirishga majburiymi (#27); yurist fikri.

**6. Mustaqil bank terminali bilan "karta"ni qo'lda belgilash (#37)**
- **Tavsiya:** Ha, online va offline'da ruxsat; ixtiyoriy "terminal operatsiya raqami" maydoni va Z-hisobotda "karta" jami alohida chiqadi, Egasi kun oxirida bank ko'chirmasi bilan solishtiradi.
- **Nega:** Bozorda standart amaliyot (terminal kvitansiyasi va fiskal chek — ikki alohida hujjat, uzum.uz); integratsiyalangan terminal veb-kassaga mos emas va qimmat.
- **Ishonch:** o'rta-yuqori.
- **Keyin tekshiriladi:** Yurist: O'zbekistonda to'lov turini qo'lda belgilashga cheklov va jarima bormi.

**7. Offline'da limitdan oshgan nasiya (#39)** *(research qilinmagan — qabul agenti tavsiyasi)*
- **Tavsiya:** Ha, yetarli: offline'da qurilma oxirgi ma'lum qoldiq bo'yicha ogohlantiradi, kassir baribir sotsa qarz shundayligicha qoladi, bayroq qo'yiladi va internet qaytgach Egasiga xabar boradi; sotuv bekor qilinmaydi.
- **Nega:** Sotuv va fiskal chek allaqachon amalga oshgan — uni orqaga qaytarish buxgalteriyani buzadi; nazorat xabar va audit orqali bo'ladi (offline sotuv qarori #17 bilan bir xil mantiq).
- **Ishonch:** o'rta (tashqi manba bilan tekshirilmagan, lekin mavjud offline qoidalarga mos).
- **Keyin tekshiriladi:** Pilotda bunday holatlar soni; kerak bo'lsa offline nasiyani faqat Menejer PIN bilan ruxsat qilish varianti.

**8. Optom narx va chegirmalar (#7)**
- **Tavsiya:** MVP'da alohida optom narx jadvali yo'q — o'rniga mijoz kartasida "doimiy chegirma %" maydoni; bir chekda bir nechta chegirma to'qnashsa, **faqat bittasi — mijozga eng katta foyda beradigani** qo'llaniladi (yig'ilmaydi).
- **Nega:** Odoo ham "bitta eng mos qoida" modelida; tekshirilgan O'zbek raqobatchilarda to'liq optom narx turlari ko'rinmadi; QQS baribir yakuniy summadan hisoblanadi.
- **Ishonch:** o'rta.
- **Keyin tekshiriladi:** Pilotdagi ulgurji do'konlar alohida "qattiq" optom narx so'raydimi — so'rasa, keyingi bosqichda narx turlari qo'shiladi.

**9. Nasiya grafigi va shubhali qarz (#9)**
- **Tavsiya:** Bitta va'da sanasi yetarli (bo'lib to'lash grafigi yo'q); "shubhali qarz"ni faqat Egasi qo'lda, sabab bilan belgilaydi — tizim 60+ kunlik qarzlar ro'yxatini eslatma sifatida ko'rsatadi, o'zi belgilamaydi.
- **Nega:** BILLZ/mDokon ham bitta sana bilan ishlaydi; 4910-hisob (shubhali qarzlar zaxirasi) mantiqi har qarzni alohida baholashga asoslangan, avtomatik N-kun qoidasi emas.
- **Ishonch:** grafik yo'qligi — yuqori; qo'lda belgilash — o'rta.
- **Keyin tekshiriladi:** Buxgalter: kichik biznes 4910 zaxirasini yaratishi shartmi va baholash tartibi (buxgalter.uz matni paywall ortida).

**10. AI-03 ishga tushirish sharti (#59)**
- **Tavsiya:** Yagona 90% o'rniga maydon bo'yicha shart: 100 ta O'zbekiston hujjatida **summa ≥ 95%**, **sana ≥ 90%**, miqdor va tovar nomi **≥ 80%** (past ishonchli maydon har doim sariq belgilanadi); summa yoki sana 90% dan past bo'lsa — AI-03 pilotga chiqmaydi.
- **Nega:** Pul maydonidagi xato eng qimmat, shuning uchun eng qattiq chegara; xalqaro amaliyot ham maydon bo'yicha yo'naltiradi, va baribir har hujjatni foydalanuvchi tasdiqlaydi.
- **Ishonch:** o'rta (yondashuv tasdiqlangan; aniq raqamlar uchinchi tomon tavsiyalaridan, o'zbek hujjatlari uchun benchmark yo'q).
- **Keyin tekshiriladi:** 100 hujjatli to'plam (≈40% toza, 40% foto/skaner, 20% qo'lda yozilgan; lotin/kirill/rus) bo'yicha haqiqiy natija; "tahrirsiz tasdiqlangan" ulushi.

**11. AI limiti tugaganda (#60)**
- **Tavsiya:** Yo'q, overage (qo'shimcha avtomatik to'lov) bo'lmaydi: limit tugasa AI keyingi oygacha to'xtaydi yoki tarifni oshirish taklif qilinadi; limitlarni biroz kengroq qo'yamiz. Oldindan to'lanadigan "AI paket" — faqat pilotdan keyin, agar tenantlarning ≥10% limitga urilsa.
- **Nega:** AI xarajati tarifning atigi ~1,5–6% i; mayda summalarni Click/Payme orqali yechish komissiya, support savollari va murakkablik keltiradi.
- **Ishonch:** o'rta.
- **Keyin tekshiriladi:** Pilotda tenantlar limitga qanchalik tez-tez urilishi.

**12. Support modeli (9.3)**
- **Tavsiya:** Telegram (mavjud bot ichida "/yordam") + bitta telefon raqami; ish kunlari 09:00–19:00; fiskal/OFD, markirovka va bloklanish muammosiga ish vaqtida **1 soat ichida** birinchi javob, oddiy savolga 24 soat. Dam olish kunlari kritik muammolar uchun Telegram orqali **navbatchi (asoschi), 4 soat ichida** javob.
- **Nega:** BILLZ/mDokon aynan Telegram+telefon modelida; navbatchi shart, chunki juma 19:00 dan dushanba 09:00 gacha 62 soat — bu 48 soatlik OFD muddatidan uzun.
- **Ishonch:** o'rta (kanallar — yuqori; SLA raqamlari — taxmin).
- **Keyin tekshiriladi:** Pilotda murojaatlar soni va javob vaqti; 1 operator (~6,7–7 mln so'm/oy) yetarlimi.

**13. Unit-iqtisod va Start narxi (9.1)**
- **Tavsiya:** Start narxi 49 000 so'm qoladi, lekin virtual kassa unga kirmaydi (+39 000 so'm/kassa qo'shimcha — 2-savolga qarang); support xodimi (~7 mln so'm/oy) dastlabki bosqichda zarar sifatida qabul qilinadi va 300 to'lovchi tenantga yetganda narx qayta ko'riladi.
- **Nega:** Kassasiz Start xarajati ~25 000–31 000 so'm (SMS Eskiz bo'yicha arzonroq chiqdi) → marja ~18 000–24 000 so'm sog'lom; marjani buzayotgan yagona katta xarajat — fiskal modul.
- **Ishonch:** o'rta (hosting/sig'im taxmin; fiskal to'lovi ikkinchi darajali manbadan).
- **Keyin tekshiriladi:** Pilotdagi haqiqiy hosting xarajati; 1 BHM qiymati; support nisbati (150 tenantda daromadning ~45% i — kutilgan, 1 000+ tenantda ≤5–8% ga tushishi kerak).

**14. Pentest (#52)**
- **Tavsiya:** Pilotdan oldin — bepul avtomatik skaner (OWASP ZAP) va ichki OAuth/to'lov/fiskal tekshiruv ro'yxati; ommaviy sotuvdan oldin — Celion yoki ONESEC'dan (ikkalasidan narx so'rab) OWASP ASVS L2 bo'yicha to'liq pentest (veb, API, OAuth, Android). Byudjetga hozircha **~60 mln so'm (~$5 000)** rezerv qo'yiladi.
- **Nega:** Pilotda do'kon soni kam va xavf cheklangan, tashqi pentest esa qimmat; mahalliy firmalar mavjud, lekin narxni ochiq bermaydi.
- **Ishonch:** o'rta-past (standart/qamrov — yuqori; narx — xalqaro ma'lumotdan taxmin, $1 500–7 000).
- **Keyin tekshiriladi:** Celion va ONESEC rasmiy takliflari; Xat 3 (csec.uz) — ЗРУ-764 bo'yicha majburiy sertifikatlash bizga tegishlimi (javob "ha" bo'lsa reja o'zgaradi).

**15. Yopilgan oyni qayta ochish (#16)**
- **Tavsiya:** Yo'q, MVP'da yopilgan oy qayta ochilmaydi; xatolar joriy ochiq oyda tuzatuvchi hujjat bilan to'g'rilanadi. Keyinroq (buxgalter roziligi bilan) Odoo uslubidagi "faqat Buxgalter, sabab va muddat bilan, audit yozuvli" istisno qo'shilishi mumkin.
- **Nega:** O'zbekistonda hozir oldingi davr xatolarini tuzatish bo'yicha alohida standart yo'q (NSFO №2 faqat 2027-01-01 dan), append-only yondashuv eng xavfsiz; xalqaro tizimlar ham lock date + admin istisnosi bilan ishlaydi.
- **Ishonch:** yuqori (MVP uchun); o'rta (uzoq muddatga).
- **Keyin tekshiriladi:** Buxgalter tasdig'i; aniqlashtirilgan soliq hisoboti topshirilganda ichki raqamlar bilan farqni qanday kuzatish; 2027-yil NSFO №2 kuchga kirgach qayta ko'rish.

**16. Rasmiy xatlarni kim imzolaydi (K2)** — ***faqat foydalanuvchi***
- **Tavsiya:** Yo'q (agent qaror qilmaydi) — qaysi yuridik shaxs nomidan va kim imzolashini faqat asoschi hal qiladi.
- **Nega:** Bu yuridik vakolat masalasi; Xat 1/2/3 shu qarorsiz yuborilmaydi, shuning uchun 2, 3, 5, 14-savollarning tekshiruvi ham shu qarorga bog'liq.
- **Ishonch:** —
- **Keyin tekshiriladi:** Yuridik shaxs ro'yxatdan o'tganmi; imzo uchun E-IMZO kaliti bormi.
