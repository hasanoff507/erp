# 26. Ochiq savollar reestri

**Maqsad:** Loyihaning barcha noaniq nuqtalarini bir joyda ko'rsatish — qaysi biri allaqachon qaror qilingan (kodlash uchun tayyor) va qaysi biri hali tashqi tomon (davlat idorasi, vendor, buxgalter, yurist, pilot) javobini kutmoqda.
**Kim uchun:** Claude (implementatsiya paytida noaniqlikka duch kelganda, avval shu faylni tekshiradi), asoschi (rasmiy xat javobi kelganda jadval B'ni yangilaydi).
**Bog'liq fayllar:** `01-qarorlar.md`, `27-backlog.md`, `spec/tarix/tekshiruv/rasmiy-xatlar.md`.
**Holat:** joriy, 2026-10-15.

Boshqa `spec/kod-uchun/*` fayllarida `#NN` ko'rinishidagi havolalar shu reestrning **"Eski #"** ustuniga ishora qiladi — qayta raqamlash qilinmagan, raqamlar barqaror qoladi.

---

## Jadval A — Qaror qabul qilingan standart qarorlar

Quyidagilar — ichki texnik yoki mahsulot qarorlari: standart yechim bilan hozir hal qilingan, kod shu asosda yoziladi. Ba'zilari (masalan Egasi ruxsatlari, chek tili, yuridik shaxs modeli, QQS/aylanma solig'i nisbati taxmini, jamoa tarkibi) asoschi tomonidan rasman tasdiqlangan; qolganlari — muhandislik standarti, kerak bo'lsa keyin osongina o'zgartiriladi.

| Eski # | Savol | Qaror | Sabab | Qayerda qo'llanilgan |
|---|---|---|---|---|
| 1 | Huquqlar matritsasining to'liq rasmiy tasdig'i | Mavjud matritsa tasdiqlangan | Raqobatchilar amaliyotiga mos loyihalangan | `15-xavfsizlik-va-audit.md` §2.2; `02-rollar-va-ssenariylar.md` §6 |
| 2 | Kichik do'konda rollar birlashuvi uchun xodim soni chegarasi | ≤3 FTE — Kassir+Omborchi+Menejer bitta xodimda birlashishi mumkin; 4+ FTE — rollar alohida shaxslarga beriladi | O'zbek kichik do'kon tipik tarkibiga mos | `02-rollar-va-ssenariylar.md` OS4 |
| 3 | Davlat hisobotini solishtirish (BO-10) ish oqimi: kim birinchi ko'radi, qanday eskalatsiya | Buxgalter 1-kunda ko'radi; farq 3-kalendar-kungacha yopilmasa BO-10 banner Egasiga ham ko'rinadi; 5-kalendar-kun muddatigacha tuzatish | 5 kunlik qonuniy muddatga mos bufer | `02-rollar-va-ssenariylar.md`, `04-biznes-jarayonlar.md`, `06-ekranlar-umumiy.md` |
| 5 | Narx o'zgarishi (chegirmadan tashqari) uchun tasdiqlash limiti | Katalog narxidan ±10%dan ko'p o'zgarish — faqat Egasi tasdig'i (`prices.approve`); limit `role_permissions.limit_value` (`10.00`) | 05 xavfsizlik matritsasi bilan ziddiyatni yo'qotish | `03-modullar-talablari.md`; `15-xavfsizlik-va-audit.md` §2.2 |
| 7 | Ko'p filialli mijoz (nasiya) balansini konsolidatsiya qilish yoki filial bo'yicha ajratish | Balans tenant darajasida yagona (bitta mijoz — bitta umumiy qarz balansi); filial faqat hisobotda qator darajasida ko'rinadi | Aksariyat kichik-o'rta tenant uchun mijoz bir xil, filial faqat sotuv nuqtasi | `03-modullar-talablari.md` OS5 |
| 10 | Markirovka kodi tekshiruvi muvaffaqiyatsiz bo'lganda sotuvni qat'iy rad etish | Ha, qat'iy rad qoladi | Xavfsiz standart, CRPT javobi kelgach yumshatilishi mumkin | `03-modullar-talablari.md` OS11 |
| 12 | Chekni ikki tilda (o'zbek/rus) chiqarish talabi | Chek har doim ikki tilda chiqadi — har qator `{products.name} / {products.name_ru}` (`name_ru` bo'lmasa faqat `name`), sarlavha/yakun matnlari ham ikki tilda ("Jami / Итого" va h.k.). Fiskal rekvizitlar OFD formatida, tarjima qilinmaydi. O'zbek qatori har doim birinchi va majburiy (`01-qarorlar.md` #29) | Mijozlar ko'pincha ikki tilli; o'zbek qatori birinchi bo'lgani uchun davlat tili talabiga zid emas | `06-ekranlar-umumiy.md` §1.4, `01-qarorlar.md` #29; `18-api-kassa.md` §4.9; `11-malumotlar-modeli.md` (`products.name_ru`) |
| 13 | Aniq teginish/vaqt UX parametrlari (tugma o'lcham, chek yopilish vaqti, ogohlantirish oldindanligi) | Tugma min: POS — 48×48 dp, asosiy tugmalar 56 dp; mobil back-office — 44×44 dp. Chek ekrani chop/QR muvaffaqiyatli bo'lgandan 5 soniya keyin avtomatik asosiy holatga qaytadi (toast bilan) — printer xatosida qaytmaydi. Offline fiskal ogohlantirish 48 soatlik limitdan 6 soat oldin boshlanadi | Mobil UX sanoat standarti (Material/iOS HIG); printer xatosida avtomatik qaytish foydalanuvchini chalg'itardi | `06-ekranlar-umumiy.md` OS2; `08-dizayn-tizimi.md` §5 |
| 14 | DataMatrix (markirovka) kodini qo'lda kiritishga ruxsat | Ruxsat, lekin faqat online: faqat skaner ishlamagan holat uchun zahira, `POST /marking/verify` muvaffaqiyatli bo'lgandagina qabul qilinadi; offline qo'lda kiritilgan kod bilan sotish taqiq; har bir qo'lda kiritish audit-logga yoziladi (`marking.manual_entry`) | Skaner nosozligi amaliy holat, lekin online-shart CRPT majburiy tekshiruvini chetlab o'tishning oldini oladi | `06-ekranlar-umumiy.md` §1.7 |
| 15 | AI chatning offline qisman ishlashi (oxirgi javoblarni keshlash) | MVP'da to'liq o'chadi | Keshlash alohida UX tadqiqotini talab qiladi | `06-ekranlar-umumiy.md` OS6 |
| 16 | BO-10 hisobot qator (hujjat) yoki yig'ma (davr) darajasida ko'rsatilishi | Ikkisi ham: avval yig'ma (davr) ko'rinadi, "Batafsil" tugmasi qator darajasiga tushiradi (drill-down) | Ikki UX ehtiyojini ham qamraydi | `06-ekranlar-umumiy.md` OS9 |
| 18 | Vision-LLM OCR (AI-03) uchun aniq narx | Rasm ≈ 1500 token ekvivalenti sifatida hisoblanadi; haqiqiy xarajat pilotda `ai_requests`dan kuzatiladi | Rasmiy per-image narx manbada yo'q | `09-ai-funksiyalar.md` OS1; `22-ai-qatlami.md` OS1 |
| 21 | AI-10 (narx optimallashtirish) yondashuvi va aniqligi | MVP'da oddiy qoida-asosidagi tavsiya (past margin/sekin aylanish ko'rsatkichiga qarab ogohlantirish), murakkab ML keyingi bosqichga qoldiriladi | AI-10 alohida tadqiqot talab qiladi, MVP sodda yechim bilan boshlaydi | `09-ai-funksiyalar.md` OS4 |
| 22 | AI-05 (davlat hisobot tafovuti tushuntirish) qaysi manba ma'lumotiga asoslanadi | Faqat foydalanuvchi qo'lda yuklagan davlat hisobot fayli (PDF/Excel) bilan solishtiriladi | `my.soliq.uz` dasturiy API yo'qligi sababli | `09-ai-funksiyalar.md` OS5 |
| 23 | Hikoya darajasidagi MoSCoW ustuvorlik taqsimoti | Mavjud taqsimot (1.1-bo'lim) tasdiqlanadi | Bosqich rejalashtirish vaqtida qayta ko'rish imkoniyati saqlanadi | `05-mvp-chegarasi.md` OS1 |
| 24 | Barcha biznes o'lchovlari (3.2-bo'lim) va sig'im/marja taxminlari | Hozirgi taxminlar bilan davom etiladi, birinchi pilot davridagi haqiqiy `ai_requests`/`orders`/xarajat ma'lumoti bilan almashtiriladi | Pilotgacha boshqa manba yo'q | `05-mvp-chegarasi.md` OS3; `25-nofunksional-talablar.md` OS3/OS10 |
| 26 | Maqsadli segmentning QQS to'lovchi / aylanma solig'i to'lovchi nisbati | ">70% aylanma solig'i to'lovchi" taxmini qo'llanilmaydi (`01-qarorlar.md` #32). QQS va aylanma solig'i rejimlari arxitekturada teng darajada birinchi toifali qo'llab-quvvatlanadi, haqiqiy nisbat oldindan belgilanmaydi — pilot ko'rsatkichi: rejimlar ulushi | Taxmin manbasiz edi; ikkala rejimni teng qo'llab-quvvatlash xavfni kamaytiradi | `05-mvp-chegarasi.md` §1.1/§3.2; `25-nofunksional-talablar.md` §3.1; `13-provodka-qoidalari.md` |
| 28 | Claude API'ga yuboriladigan ma'lumot hajmini cheklash siyosati | Faqat zarur maydonlar yuboriladi (shaxs ismi/STIR — `tenant_glossary` orqali xaritalanadi; karta/parol/PIN hech qachon); AI-03 rasm yuborishdan oldin max 2048px'ga siqiladi | Ma'lumot minimizatsiyasi tamoyili | `10-umumiy-arxitektura.md` OS3 |
| 29 | Bitta chekda bir nechta QQS stavkasi chek/e-faktura formatida ko'rsatilishi | Har qator o'z stavkasi bilan chiqadi, chek pastida stavka bo'yicha jamlanma qator (12% jami, 0%/imtiyozli jami) | Ko'p-stavkali chekning odatiy formati | `11-malumotlar-modeli.md` OS1 |
| 30 | M16 kassa pul harakatini OFD'ga yuborish kerakmi | Yo'q — faqat sotuv/qaytarish fiskal hujjat hisoblanadi; kassadan pul qo'yish/olish faqat ichki hisobot (M16) | OFD talabi faqat fiskal sotuv hujjatlariga tegishli | `11-malumotlar-modeli.md` OS2 |
| 32 | `stock_balances`ni trigger bilanmi yoki ilova kodida yangilash | Ilova kodida, posting xizmati ichida bitta tranzaksiyada (trigger ishlatilmaydi) | Testlash va kuzatish oddiyroq, business-logika Python'da markazlashadi | `11-malumotlar-modeli.md` OS5 |
| 33 | QQS yaxlitlash qoidasi (qator-bo'yicha tiyingacha) | ROUND_HALF_UP, qator darajasida, tiyingacha | Eng keng tarqalgan soliq yaxlitlash qoidasi | `13-provodka-qoidalari.md` OS2 |
| 38 | Ko'p yuridik shaxsli (turli STIR/QQS holatidagi filiallar) tenant qo'llab-quvvatlanishi | MVP'da yo'q — **1 tenant = 1 yuridik shaxs**, bitta hisob-kitob; ko'p filial/kassa/faoliyat turi (`branches.activity_type`) bitta tenant ichida qo'llab-quvvatlanadi (`01-qarorlar.md` #31) | Ko'p-yuridik-shaxs holati keyingi bosqich funksiyasi | `13-provodka-qoidalari.md` OS7; `11-malumotlar-modeli.md` `tenants`; `12-db-sxema.md` |
| 45 | SMS (OTP) provayder tanlovi | Eskiz.uz — 95 so'm/SMS, obuna to'lovi yo'q; SMS — faqat zaxira kanal, OTP uchun asosiy kanal Telegram bot (`01-qarorlar.md` #34) | Narxi tasdiqlangan yagona variant, muqobillar tekshirilmagan | `21-integratsiyalar.md` OS9; `25-nofunksional-talablar.md` OS7; `14-autentifikatsiya-oauth2.md` OS5 |
| 46 | `outbox_jobs.kind` ro'yxatini qo'shimcha qiymatlar bilan kengaytirish | Enum kengaytiriladi: `einvoice_accept`, `ettn_send`, `marking_verify`, `marking_sell`, `vat_report_sync` | Sof texnik ro'yxat, bloklamaydi | `21-integratsiyalar.md` OS10 |
| 48 | Billing (M17) uchun Click/Uzum sandbox topilmaguncha test rejimi | Dev/staging muhitida `PaymentPort`ning mock implementatsiyasi (test flag bilan "to'landi" simulyatsiyasi) | Standart port/adapter test amaliyoti | `21-integratsiyalar.md` OS12 |
| 50 | Barcha tezlik maqsadlari (SLO raqamlari, qonuniy 48/72 soat/5 kundan tashqari) | Mavjud SLO jadvali (masalan p95 so'rov <300ms) standart ichki maqsad sifatida qoladi | Pilot telemetriyasi bilan tasdiqlanadi | `25-nofunksional-talablar.md` §1 |
| 52 | Rasmiy accessibility (WCAG) audit | MVP'da asosiy semantik HTML/ARIA yetarli, to'liq audit keyingi bosqichga qoldiriladi | MVP muddatini bosib o'tmaslik uchun | `25-nofunksional-talablar.md` OS8 |
| 53 | Observability vositasi tanlovi (eksport joyi — jadval B'da) | Prometheus + Grafana + Loki (self-hosted) | Keng tarqalgan open-source stack | `25-nofunksional-talablar.md` OS9; `23-backend-arxitekturasi.md` OS3 |
| 54 | Oylik AI token budjeti qiymatlari | Hozirgi jadvaldagi limitlar standart boshlang'ich qiymat, pilotda haqiqiy foydalanish bilan sozlanadi | Unit-iqtisod hisobi shu taxminga asoslangan | `22-ai-qatlami.md` OS2 |
| 55 | LLM-judge uslub/tabiiylik bahosi metodologiyasi | Claude (Sonnet) o'zi rubric (aniqlik, tabiiylik, xavfsizlik) bilan haftalik namunani baholaydi | Qo'shimcha inson-baholovchisiz boshlanadi | `22-ai-qatlami.md` OS4 |
| 56 | `ai_training_samples` saqlash muddati va anonimlashtirish darajasi | 90 kun saqlanadi; ism/STIR/telefon maskalangan holda | Boshqa operatsion loglar bilan bir xil siyosat | `22-ai-qatlami.md` OS5 |
| 57 | Raqamli nazorat (numeric guard) ikki marta muvaffaqiyatsiz bo'lish chastotasi | Tenant bo'yicha >5% chastota — ichki alert (BO-14/M18 kabi kanal) | Prompt/tool dizayn muammosini erta aniqlash uchun chegara | `22-ai-qatlami.md` OS6 |
| 58 | orval vs openapi-typescript+openapi-fetch | orval (axios bilan) | Namuna loyihaga mos | `24-frontend-arxitekturasi.md` OS3 |
| 59 | DI yondashuvi: factory+`Depends` yoki `dependency-injector` | Oddiy factory-funksiya + `Depends` | Modulli monolit hajmi uchun yetarli | `23-backend-arxitekturasi.md` OS1 |
| 60 | CI platformasi | GitHub Actions | Repo joylashuviga mos eng keng tarqalgan tanlov | `23-backend-arxitekturasi.md` OS2 |
| 61 | `scheduler`ning yagona nusxa kafolati | Postgres advisory lock | Qo'shimcha infra shart emas, Postgres allaqachon bor | `23-backend-arxitekturasi.md` OS4 |
| 62 | `zxing-cpp`ning GS1 DataMatrix (FNC1) chiqishi Asl belgisi talabiga mosligi | Birinchi bosqichda sinab ko'riladi; mos kelmasa server tomonida `bwip-js` (Node) zahira | Texnik tekshirish bosqichi, bloklamaydi | `23-backend-arxitekturasi.md` OS8 |
| 64 | `minSdk` tanlovi (UZKASSA P100 — Android 5.1 qamrovi) | minSdk 24 (Android 7.0); eski P100 modeli (Android 5.1) qamrovdan chiqariladi | Zamonaviy xavfsizlik/kutubxona qamrovi ustunlik | `28-android-pos.md` OS2 |
| 65 | NFC/karta terminali integratsiyasi | MVP'da yo'q — mustaqil terminal bilan qo'lda "Karta" belgilash davom etadi | Integratsiyalangan terminal qimmat va aniqlanmagan | `28-android-pos.md` OS4 |
| 66 | Play Store'da GMS mavjudligi maqsadli POS qurilmalarida | MDM/APK — asosiy kanal; Play Store keyinroq ixtiyoriy ikkinchi kanal | GMS'siz qurilmalar (UZKASSA/PAX) uchun xavfsiz yondashuv | `28-android-pos.md` OS5 |
| 67 | OpenAPI'dan Kotlin klient generatsiya vositasi | openapi-generator (Kotlin client generatori) | Keng tarqalgan, qo'lda Retrofit yozishdan tezroq | `28-android-pos.md` OS6 |
| 68 | DI vositasi (Hilt vs Koin) | Hilt | Google rasmiy tavsiyasi | `28-android-pos.md` OS7 |
| 69 | SQLCipher vs Android Keystore maydon-darajasida shifrlash | SQLCipher — butun mahalliy baza shifrlanadi | Maydon-darajasidan sodda, yetarli xavfsizlik | `28-android-pos.md` OS8 |
| 70 | Jamoa tarkibi va muddat | Jamoa — asoschi + Claude (2 kishi); qat'iy kalendar muddat yo'q, ish ketma-ket bosqichlarda olib boriladi (`01-qarorlar.md` #35) | Tashkiliy masala, spec'ni bloklamaydi | `27-backlog.md` |
| 72 | Access token aniq muddati | 15 daqiqa | OAuth sanoat amaliyoti (10–15 daqiqa) | `14-autentifikatsiya-oauth2.md` OS1 |
| 73 | Qurilmaga bog'langan refresh token muddatlari | Sliding 14 kun / mutlaq 180 kun | Joriy taxmin tasdiqlanadi | `14-autentifikatsiya-oauth2.md` OS2 |
| 74 | Imzolash kaliti rotatsiya chastotasi | 90 kun | Tipik PKI/kalit rotatsiyasi siyosati | `14-autentifikatsiya-oauth2.md` OS3 |
| 75 | Obuna lokaut holatida "zudlik" uchun heartbeat/WebSocket kanali kerakmi | Yo'q — oddiy keyingi-so'rov (polling) + ixtiyoriy SSE heartbeat yetarli | WebSocket infratuzilma qo'shimchasi hozir shart emas | `14-autentifikatsiya-oauth2.md` OS4 |
| 76 | argon2id aniq parametrlari (m/t/p) | OWASP tavsiyasi: m=19 MiB, t=2, p=1 (server resursiga qarab sozlanadi) | OWASP Password Storage Cheat Sheet standarti | `14-autentifikatsiya-oauth2.md` OS6 |
| 77 | Telegram bot token modelini kelajakda yozuvchi amal uchun kengaytirish | Hozircha o'qish/javob darajasida yetarli (AI-01, hisobot, eslatma); yozuvchi amal qo'shilsa token modeli qayta ko'riladi | MVP botda yozuvchi amal yo'q | `14-autentifikatsiya-oauth2.md` OS7 |
| 78 | Admin panelining o'z BFF'si (`admin-bff`) alohida deploy qilinishi | Hozircha bitta backend, alohida `client_id`/scope bilan yetarli; kerak bo'lsa keyin ajratiladi | Qo'shimcha izolyatsiya hozir ortiqcha murakkablik | `14-autentifikatsiya-oauth2.md` OS8 |
| 79 | WebAuthn/biometrik parolsiz kirish | MVP'da yo'q — kelajakdagi kengaytma | Vazifada so'ralmagan | `14-autentifikatsiya-oauth2.md` OS9 |
| 80 | `license_tokens` saqlash muddati va tozalash sikli | 90 kun, boshqa operatsion jadvallar bilan bir xil siyosat | — | `14-autentifikatsiya-oauth2.md` OS10 |
| 81 | Resurs nomlash — URL kebab-case vs JSON snake_case | URL yo'li — kebab-case ko'plik (`/goods-receipts`); JSON maydon/query/enum/`operation_id` — snake_case | Orval/Pydantic generatsiyasini blokladi, kodlashdan oldin hal qilindi | `17-api-umumiy.md`; `23-backend-arxitekturasi.md` §3; `01-qarorlar.md` #24 |
| 83 | Omborchi tovar qabulini (`goods_receipts`) o'zi `post` qila oladimi, yoki faqat `draft` yaratib Buxgalterga topshiradimi | **Interim** (asoschi tasdig'ini kutadi, `01-qarorlar.md` #27): Omborchi faqat `draft` yaratadi (`purchases.receive`), Buxgalter `post` qiladi (`purchases.post`) — qoldiq shu paytda oshadi | BP-01 jarayoni bilan solishtirilishi kerak; agar "qabul paytida qoldiq oshsin" desa, `post`ga `purchases.receive`ni ham qo'shish arxitektura jihatidan oson | `19-api-ombor.md` §8 |
| 85 | B2B nasiya sotuvdan chiquvchi e-faktura avtomatik qoralamasi kerakmi | `POST /api/v1/einvoices` (`direction=out`) — B2B nasiya sotuvdan server avtomatik `draft` yaratadi (`counterparty.kind=company`); ruxsat `einvoice.create` | BP-03/BP-13, chekdan keyin e-faktura qarori bilan izchil | `18-api-kassa.md` §15a |
| 86 | Qurilmani o'rnatish yo'riqnomasi alohida route bo'lishi kerakmi | Ha, alohida ochiq route `/install` — biznes ekranlardan tashqari, autentifikatsiyasiz; BO-21 ⑥ shu komponentni ichiga oladi | iOS'da o'rnatish majburiy (ITP IndexedDB tozalaydi), wizard ichida qolib ketsa topib bo'lmaydi | `07-ekran-tafsilotlari.md` UX-INSTALL, E-32 |
| 87 | `approval_requests.expires_at` aniq muddati va POS tasdiqlash navbatini poll qilish chastotasi | `expires_at` = so'rov yaratilgandan 15 daqiqa keyin; POS/BO-16 poll — har 3 soniyada | Aniq raqamlar manbada yo'q, pilotda yuklama/UX bilan tasdiqlanadi | `18-api-kassa.md` (BO-16 tasdiqlash navbati) |
| 90 | Ko'p bank hisobi (`bank_accounts`) qo'llab-quvvatlanishi | MVP'da yo'q — yagona yashirin bank hisobi (`5110`), `cash_moves.bank_account_id` doim `NULL`; ko'p hisob keyingi bosqich (asoschi tasdig'i bilan, `01-qarorlar.md` #27) | MVP ko'lamini kichraytirish | — |
| 91 | Inventarizatsiya davomida sotuv bo'lsa `stock_counts` kutilgan (`expected`) qiymatini qayta hisoblash qoidasi | `post`da `expected` — sanash boshlanganidan keyingi sotuvlarni hisobga olib qayta hisoblanadi | Bir qurilma — bir inventarizatsiya siyosati bilan birga, aniq formula implementatsiya bosqichida tasdiqlanadi | `13-provodka-qoidalari.md` §2.11 |
| 92 | Egasi rolining operatsion ruxsatlari (sotuv/smena/qaytarish/hisobdan chiqarish va h.k.) | Egasi — `platform.admin`dan tashqari barcha tenant ruxsatlarining supersetiga ega, limitlar cheksiz | Kichik do'konda Egasi ko'pincha o'zi kassada/omborda ishlaydi (`01-qarorlar.md` #28) | `15-xavfsizlik-va-audit.md` §2.2 |

---

## Jadval B — Hali ochiq (tashqi javob kerak)

Quyidagilar — tashqi tomon (davlat idorasi, vendor, buxgalter, yurist, pilot) javobini kutayotgan savollar. Har biriga vaqtinchalik muhandislik taxmini belgilangan — kod shu taxmin bilan ishlaydi, javob kelganda almashtiriladi (ko'pchiligi migratsiyasiz, sozlama/flag ortida).

| Eski # | Kim | Nima so'raladi | Qaysi xat | Muhandislik taxmini (interim) | Bloklaydigan bosqich |
|---|---|---|---|---|---|
| 4 | Vakolat.uz / "Yangi texnologiyalar" DUK | API hujjati bormi; 2026-01-01'dan majburiylik uchinchi tomon dasturlarga ham tegishlimi (yetkazib beruvchi vakili ishonchnomasi tekshiruvi) | — (hali yozilmagan) | M07 kirimda ishonchnoma raqami/sanasi qo'lda matn maydoniga kiritiladi, tizim bloklamaydi, faqat ogohlantiradi | Bosqich 2 (ombor) — bloklamaydi |
| 6 | Shartnoma buxgalteri/auditor | To'liq NSBU №21 hisob rejasi (191-son buyruq to'liq ilovasi) — MVP subset bilan solishtirish, 10 ta ogohlantirilgan band (QQS yaxlitlash, klirinig hisob, ortiqcha daromad kodi, 8720, ish haqi 6710 va h.k. — #34–39) | — (to'g'ridan-to'g'ri konsultatsiya) | MVP subset bilan davom etiladi, yangi hisoblar append-only migratsiya bilan qo'shiladi | Bosqich 0'dan boshlab, to'liq tasdiq Bosqich 5 (M11 hisobotlar)gacha kerak |
| 8 | Yurist + Soliq qo'mitasi/OFD operatori | Onlayn/QR to'lovda (Click/Payme/Uzum) fiskal chekni kim chiqarishi — to'lov tizimi yoki merchant | Xat 1 (qo'shimcha savol) | Arxitektura ikkala holatni konfiguratsiya maydoni bilan qo'llab-quvvatlaydi, standart — merchant o'zi chiqaradi | Bosqich 3 (to'lov turlari) / Bosqich 5 (fiskal) |
| 9 | Buxgalter + OFD operatori | Qarz to'lovida alohida fiskal chek chiqarilishining qonuniyligi — daromad/QQS tan olish vaqti (sotuvdami, to'lovdami) | Xat 1 (qo'shimcha savol) | Qaror allaqachon amalga oshirilgan: qarzga sotuvda chek chiqarilmaydi (`fiscal.status="deferred"`), har bir qarz to'lovida to'langan summaga chek chiqariladi (`fiscal_receipts.kind='debt_settlement'`), `FiscalPolicy` sozlamasi ortida — tasdiq kelganda o'chirish/o'zgartirish migratsiyasiz | Bosqich 5 (fiskal) — amalga oshirilgan, faqat yakuniy huquqiy tasdiqni kutadi, bloklamaydi |
| 11 | Star Micronics/Epson mahalliy distributori (vendor) + yurist | Bulut-print (cloud-print) chek printerining O'zbekistonda narxi/mavjudligi; iOS'da faqat-elektron chekning qonuniyligi | — (vendor so'rovi + yurist) | `CloudPrintAdapter` port ortida stub; iOS'da zahira — elektron chek (QR/Telegram) | Bosqich 3 (veb-kassa, bulut printer) |
| 17 | Soliq qo'mitasi | BO-10'dagi tuzatish/e'tiroz yuborish mexanizmi (shakl, kanal) | Xat 1 (qo'shimcha savol) | Tuzatish E-IMZO bilan qo'lda imzolanadi, portal havolasi tizimda saqlanadi, avtomatik yuborish yo'q | Bosqich 5 (M10 davlat hisobotini solishtirish) |
| 19 | Ichki pilot jamoasi | Kirill-lotin aralash O'zbek hujjatlarida OCR aniqligi (100 hujjatlik benchmark) | — (ichki pilot) | AI-03 feature flag ortida, maydon bo'yicha chegara (summa ≥95%, sana ≥90%, miqdor/nom ≥80%) o'tilmaguncha ishga tushmaydi | Bosqich 6 (AI-03, pilot) |
| 20 | Ichki pilot jamoasi | Shovqinli do'kon muhitida STT (AI-02) aniqligi | — (ichki pilot) | Ovozli buyruq ixtiyoriy kanal, matn/tugma kiritish asosiy yo'l | MVP'dan keyin (AI-02 hali rejalashtirilmagan) |
| 25 | Soliq qo'mitasi / "Yangi texnologiyalar" DUK | Davlat reyestriga kiritish bosqichlari ketma-ket/parallelligi va aniq narxi | Xat 1 | Eng yomon holat (bosqichlar ketma-ket, ~50 ish kuni) bilan reja tuziladi; pilot — hamkor orqali parallel boradi | Bosqich 0 (reyestr arizasi) |
| 27 | UzCloud savdo bo'limi (vendor) | UzCloud'da fayl ombori uchun S3-mos xizmat mavjudligi va narxi | — (vendor so'rovi) | S3-mos abstraksiya (`StoragePort`), zaxira — o'z-MinIO | Bosqich 0 (backend skeleti, storage tanlovi) |
| 31 | Tarozi ishlab chiqaruvchisi (vendor) + pilot | Tarozi og'irlik shtrix-kod formati va ulanish protokoli | — (vendor so'rovi) | EAN-13 "og'irlik kodi" prefiksli format (US-M09-06), qo'lda og'irlik kiritish doimiy zahira | Bosqich 2/3 (ombor/kassa) — qo'lda kiritish bilan bloklanmaydi |
| 34 | Buxgalter | Karta/Click/Payme/Uzum uchun alohida klirinig (oraliq) hisobi kerakligi | — | To'g'ridan-to'g'ri **5110**ga yoziladi (klirinig hisobsiz) | Bosqich 2 (provodka yadrosi) |
| 35 | Buxgalter | Inventarizatsiya ortiqchasi uchun daromad hisob kodi | — | **9320** "Boshqa operatsion daromadlar" ishlatiladi | Bosqich 2 (M05 inventarizatsiya) |
| 36 | Buxgalter | Boshlang'ich qarz balansi uchun qarshi hisob (8720) to'g'riligi | — | **8720** ishlatilishda davom etadi | Bosqich 4 (M08 qarz daftari) |
| 37 | Buxgalter/biznes | Ish haqini 6710 orqali ikki bosqichli yozish yoki to'g'ridan-to'g'ri xarajat (9420) | — | To'g'ridan-to'g'ri **9420**ga yoziladi (sodda, joriy yondashuv) | Bosqich 4 (M15 xarajatlar) |
| 39 | Buxgalter | M16 "Egasi oldi" operatsiyasi uchun qarshi hisob | — | **8720** ishlatiladi, keyin alohida "Egasi bilan hisob-kitoblar" sub-hisobi ko'rib chiqiladi | Bosqich 3 (M16 kassa pul harakati) |
| 40 | CRPT Turon | Integrator ro'yxatdan o'tish shartlari va API texnik spetsifikatsiyasi | Xat 2 | Ishtirokchi (Participant) API kaliti yo'li; ishlamasa — hamkor proksi; ikkisi ham ishlamasa — markirovkalangan tovar sotuvi bloklanadi | Bosqich 5 (CRPT Turon integratsiyasi) |
| 41 | Soliq qo'mitasi / my.soliq.uz | my.soliq.uz'dan davlat hisobotini dasturiy (API) o'qish yo'li | Xat 1 | Foydalanuvchi hisobotni qo'lda yuklaydi (fayl/PDF), AI-05 shu fayl asosida tushuntiradi | Bosqich 5/6 (M10, AI-05) |
| 42 | Soliq qo'mitasi | Virtual kassa reyestriga kiritishning aniq narxi (sertifikatlash/ekspertiza haqi) | Xat 1, Xat 10 (reyestr arizasi) | Narx noma'lum deb byudjetda zahira qoldiriladi | Bosqich 0 (reyestr arizasi) |
| 43 | Didox, Click, Uzum | Didox API'ga to'liq kirish, Click rasmiy sandbox, Uzum Merchant API aniq protokoli | Xat 5 (Didox), Xat 6 (Click), Xat 8 (Uzum) | `EInvoicePort`/`PaymentPort` adapter ortida, MVP'da faqat Faktura.uz + Click/Payme/Uzum hujjatlashtirilgan qismi | Bosqich 3 (to'lov turlari); Didox — MVP'dan keyin |
| 47 | Faktura.uz | Davlat xavf-baholash natijasi (yashil/qizil, VM 830) AIOS'ga qaysi kanal orqali kelishi | Xat 4 (qo'shimcha savol) | EDO operatori javobidagi maydon sifatida o'qiladi deb taxmin qilinadi | Bosqich 5 (e-faktura, VM 830) |
| 49 | Emitent/acquirer bank yoki Markaziy bank | UzQR'ni banklar qanday API/vebxuk orqali tasdiqlashi, yagona QR texnik standarti | Click/Payme/Uzum xatlari (Xat 6/7/8) orqali so'raladi | `UzQrPort` abstraksiyasi, PF-246 asosida ishlatish rejalashtiriladi | Bosqich 3 (M01 kassa — UzQR) |
| 51 | UzCloud savdo bo'limi (vendor) | UzCloud'ning aniq mavjudlik SLA foizi | — (vendor so'rovi) | Yo'q — ma'lumot kutilmoqda | Bosqich 0 (infratuzilma) — bloklamaydi |
| 53 | UzCloud (vendor) | UzCloud'da tayyor Tempo/Jaeger (trace eksport nuqtasi) bormi | — (vendor so'rovi) | O'z-hosted Grafana Tempo | Bosqich 0 (observability sozlash) |
| 63 | Multikassa / E-POS | PAX/UZKASSA fiskal SDK'larining rasmiy texnik hujjatlari | Xat 9 | Fiskal modul `FiscalAdapter` porti ortida, SDK hujjati kelmaguncha hamkor API orqali | MVP'dan keyin (Android POS, `28-android-pos.md` Faza 1) |
| 71 | Har bir xat qabul qiluvchisi (Xat 1–10) | Rasmiy xatlarga javob muddati | Xat 1–10 | Eng yomon holat (javobsiz/kech javob) bilan reja tuziladi, integratsiya bosqichlari zaxira vaqt bilan rejalashtiriladi | Bosqich 0'dan boshlab, keyingi bosqichlarga ta'sir qilishi mumkin |
| 82 | Buxgalter | Chakana chek qatorini so'mgacha yaxlitlash qoidasi | — | `line_total = ROUND_HALF_UP(qty × unit_price − discount, 0)`, QQS `= ROUND_HALF_UP(line_total × r/(100+r), 2)` — `shared/lib/money`da backend bilan bitta funksiya, umumiy test-vektorlar bilan | Bosqich 2 (provodka yadrosi) — kod shu qoida bilan yoziladi, tasdiq keyin ham qo'llanadi |
| 84 | OFD operatori | Fiskal chekdagi summa/QQS aniqligi (tiyin bilan, 2 xona, yoki so'mgacha yaxlitlangan) | — | Hozircha 2 xona bilan chiqariladi | Bosqich 5 (fiskal) |
| 88 | Buxgalter | `tenants.settings.vat_diff_tolerance_amount` standart qiymati | — | `"1000.00"` so'm taxmin standart | Bosqich 5 (M10 davlat hisobotini solishtirish) |
| 89 | Soliq qo'mitasi / OFD operatori | `cash_registers.ofd_status` enum qiymatlari to'plami | — | `pending`/`registered`/`active`/`suspended`/`deregistered` taxmin | Bosqich 5 (fiskal, virtual kassa holati) |

*Eslatma:* eski reestrda `#44` — `#4`ning aynan dublikati edi (Vakolat.uz), alohida qator sifatida saqlanmagan.

---

## Asoschi tasdig'ini kutayotgan bandlar (`01-qarorlar.md` #27)

Tashqi javob kerak emas, lekin asoschi yakuniy so'z aytishi kerak; kod hozir interim yechim bilan yoziladi:

1. Rasmiy xatlarni (Xat 1–10) kim imzolaydi — tavsiya #16, ochiq (`spec/tarix/tekshiruv/rasmiy-xatlar.md`).
2. Omborchi tovar qabulini o'zi `post` qila oladimi — jadval A, #83 (interim: faqat `draft`).
3. Ko'p bank hisobi — jadval A, #90 (interim: MVP'da yo'q, yagona `5110`).
4. 1C integratsiya moduli (qaror #36): qamrov — faqat o'qish/AI tahlil, 1C ga yozish (taklif → tasdiq), 1C'dan ERP'ga ko'chirish; bosqich — MVP ichida yoki keyin; AIOS kodi ERP repo'siga ko'chiriladimi yoki alohida servis (adapter) bo'lib qoladimi. Interim: MVP rejasiga kiritilmagan, ERP yadrosi unga bog'liq emas (`research_notes/sonar-1c-integratsiya/00-xulosa.md` §6).

---

## Manbalar

- `spec/kod-uchun/02…25` — har birining "Ochiq savollar" bo'limi.
- `spec/kod-uchun/01-qarorlar.md` — allaqachon qabul qilingan rasmiy qarorlar (asoschi qarorlari #28–#35 va boshqalar).
- `spec/tarix/tekshiruv/rasmiy-xatlar.md` — Jadval B'dagi "Qaysi xat" ustunidagi rasmiy murojaat xatlari (Xat 1–10).
