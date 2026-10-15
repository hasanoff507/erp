# Hosting, ma'lumotlarni lokalizatsiya qilish va xavfsizlik — texnik talablar

*Tadqiqotchi: Integrator · 2026-10-10*

## Asosiy xulosalar

1. **Ma'lumotlarni O'zbekistonda saqlash majburiyati faqat 3 toifaga tegishli**: fizik shaxslarning biometrik ma'lumotlari, genetik ma'lumotlari, va telekommunikatsiya operatorlari foydalanuvchilarining ma'lumotlari (ZRU-547, 27-1-modda; 2026-yil ZRU-1125 tuzatishi bilan tasdiqlangan). **ERP+POS'ning odatiy biznes/mijoz ma'lumotlari (buxgalteriya, ombor, savdo) bu toifalarga kirmaydi** — ularni chet el bulutida saqlash qonunan taqiqlanmagan, lekin shartlar bilan (quyida).
2. **Shaxsiy ma'lumotlar bazasini ro'yxatdan o'tkazish** faqat yuqoridagi 3 toifadagi ma'lumotlarni saqlovchi bazalar uchun majburiy — Davlat shaxsiylashtirish markazi (Davlat reyestri, pd.gov.uz portali, id.gov.uz orqali autentifikatsiya) orqali, bildirishnoma tartibida.
3. **Chet el buluti (AWS/GCP/Hetzner) qonunan taqiqlanmagan**, lekin shartli: lokalizatsiya talab qilinmaydigan ma'lumotlar uchun — qabul qiluvchi davlat "yetarli himoya" ro'yxatida bo'lishi, standart shartnoma shartlari/korporativ qoidalar, yoki xalqaro standartlarga muvofiqlik kerak.
4. **O'zbekistonda haqiqiy, jismoniy joylashgan bulut infratuzilmasi mavjud**: UzCloud (5 ta Tier III-loyiha sertifikatli data-markaz, to'liq narx jadvali bilan — VM, Managed Kubernetes, DBaaS, S3) — eng yaxshi hujjatlangan va eng arzon variant. **Yandex Cloud'ning O'zbekistonda data-markazi YO'Q** (faqat Rossiya `ru-central1` va Qozog'iston `kz1`) — bu faqat 27-1-moddadagi 3 lokalizatsiya toifasi (biometrik/genetik/telekom) uchun muhim; oddiy ERP ma'lumotlari uchun qonunan taqiqlanmagan (1–3-bandga qarang).
5. **Davlat tizimlariga (soliq, OFD) ulanuvchi dasturlar uchun majburiy sertifikatlash/ekspertiza qonuni (ZRU-764, Kiberxavfsizlik to'g'risida) faqat davlat organlari va KAI (kritik axborot infratuzilmasi) obyektlariga tegishli** — oddiy xususiy SaaS ERP'ning shu toifaga kirishi **ochiq manbada aniq tasdiqlanmagan**, huquqiy xulosa talab qiladi.
6. **Fiskal modul uchun kriptografiya milliy standartlarga asoslangan** (davlat tomonidan tasdiqlangan), lekin umumiy dastur ta'minoti uchun aniq majburiy kripto-algoritm standarti (masalan O'z DSt) qonun darajasida **topilmadi**.
7. **Buxgalteriya hujjatlari saqlash muddati — kamida 3 yil** (Buxgalteriya hisobi to'g'risidagi qonun, 23-modda, to'g'ridan-to'g'ri lex.uz'dan tasdiqlangan) — bu ikkinchi darajali manbalarda uchragan "5 yil" da'vosidan farq qiladi, shuning uchun **3 yil — qonun matnidan tasdiqlangan, ishonchli raqam**.
8. **Soliq kodeksi bo'yicha soliq hujjatlari saqlash muddati 2024-01-01 dan 3 yilga qisqartirildi** (avval 5 yil edi); shartga bog'liq holatlarda (masalan 10 yildan ortiq ishlatiladigan asosiy vositalar) muddat 13 yilgacha uzayishi mumkin.
9. **Internet/elektr uzilishi haqida rasmiy "necha soat/yiliga" statistikasi topilmadi**, lekin offline-first talabini asoslovchi aniq hodisalar ko'p: 2022-yil Qoraqalpog'iston internet to'xtatilishi, yillik imtihon kunlari milliy mobil internet to'xtatilishi, 2022-yil yanvar oyidagi mintaqaviy elektr avariyasi (O'zbekiston ulanishi 37%gacha tushgan), va 2024–2025-yillarda Toshkentda bir necha kunlik rejali/favqulodda elektr uzilishlari.
10. Tizim uchun amaliy xulosa: **UzCloud (yoki Uztelecom bulut platformasi, aslida bir xil tashkilot) — tavsiya etilgan asosiy hosting tanlovi**, lekin bu **qonuniy majburiyat emas, biznes tanlovi**: sababi — kam kechikish (soliq/OFD/bank API'lariga mahalliy yaqinlik), 1–3-bandda ko'rsatilgan shartli talablarni (adekvat himoya/shartnoma shartlari) oldindan hal qilish zarurati yo'q, va agar kelajakda lokalizatsiya doirasi kengaytirilsa (masalan, yangi tuzatish bilan) tizimni qayta ko'chirish xavfi yo'qoladi. Yandex Cloud yoki boshqa chet el bulutlarini ishlatish **qonunan mumkin** (faqat biometrik/genetik/telekom ma'lumotlari bo'lmasa), lekin yuqoridagi sabablarga ko'ra tavsiya etilmaydi. Offline-first kassa arxitekturasi internet/elektr uzilishlarining dalolatlangan holatlari tufayli **shart, ixtiyoriy emas** — bu band o'zgarishsiz qoladi.

---

## 1. Shaxsiy ma'lumotlar qonuni (ZRU-547) va lokalizatsiya

### 1.1 Asosiy qonun va 2026-yil tuzatishi

- Qonun: **"Shaxsga doir ma'lumotlar to'g'risida"**, ЗРУ-547-сон (2019-07-02) ([lex.uz/docs/4396428](https://lex.uz/docs/4396428)).
- Lokalizatsiya talabi kiritilgan tuzatish: **Qonun №ЗРУ-666 (2021-01-14)**, Qonunga 27-1-modda qo'shilgan, 2021-04-15 dan kuchda ([lex.uz/ru/docs/5220725](https://lex.uz/ru/docs/5220725); [spot.uz, 2021-01-29](https://www.spot.uz/ru/2021/01/29/database/)).
- **27-1-modda (to'g'ridan-to'g'ri lex.uz'dan tasdiqlangan)**: O'zbekiston hududida saqlanishi shart bo'lgan ma'lumotlar — faqat **fizik shaxslarning biometrik ma'lumotlari; genetik ma'lumotlari; O'zbekistonda faoliyat yurituvchi telekommunikatsiya operatorlari xizmatlaridan foydalanuvchi fizik shaxslarning ma'lumotlari**. Boshqa barcha shaxsiy ma'lumotlar bu moddaga kirmaydi.
- **2026-yil tuzatishi: Qonun №ЗРУ-1125 (2026-03-26, kuchga kirgan 2026-03-27)** — "Shaxsga doir ma'lumotlar to'g'risida"gi qonunga o'zgartirishlar va qo'shimcha kiritish haqida. Lex.uz'da topildi: [lex.uz/docs/8104580](https://lex.uz/docs/8104580) (ruscha), [lex.uz/docs/8099215](https://www.lex.uz/docs/8099215) (o'zbekcha). Tuzatish lokalizatsiya qilinadigan 3 toifani **o'zgarishsiz tasdiqlaydi** va saqlash/qayta ishlash qoidalarini liberallashtiradi, chegaradan tashqariga uzatish shartlarini aniqlashtiradi (manba: [prg.kz/document/?doc_id=34053408](https://prg.kz/document/?doc_id=34053408), [beone-uz.com](https://beone-uz.com/new-requirements-for-localization-and-transfer-of-personal-data-in-uzbekistan)).
- **ERP+POS uchun amaliy xulosa**: odatiy biznes ma'lumotlari (mijozlar ro'yxati, savdo, ombor qoldiqlari, buxgalteriya) **lokalizatsiya talabiga kirmaydi** — faqat agar tizim mijozlarning biometrik ma'lumotini (masalan, yuz tanish orqali autentifikatsiya) yoki telekom operatorlarining foydalanuvchi ma'lumotini saqlasa, shu qismi O'zbekistonda bo'lishi shart.

### 1.2 Shaxsiy ma'lumotlar bazasini ro'yxatdan o'tkazish

- **20-modda (lex.uz'dan)**: Davlat shaxsiylashtirish markazi (8-moddada belgilangan vakolatli organ) Shaxsiy ma'lumotlar bazalarining davlat reyestrini yuritadi. Ro'yxatdan o'tish — faqat 27-1-moddaga ko'ra O'zbekiston hududida saqlanishi shart bo'lgan ma'lumotlar bazalari uchun, **bildirishnoma tartibida**.
- Amaliy portal: **pd.gov.uz** — ariza shakli ([pd.gov.uz/storage/.../Request for database registration.pdf](https://pd.gov.uz/storage/web/source/Request%20for%20database%20registration.pdf)); autentifikatsiya **id.gov.uz** (yagona davlat identifikatsiya tizimi) orqali; ariza operator huquqiy ma'lumotlari (nomi, STIR, manzil), baza maqsadi, ishga tushirilgan sanasi, ma'lumot turlari, joylashuvini o'z ichiga oladi ([norma.uz](https://www.norma.uz/novoe_v_zakonodatelstve/kak_registriruyutsya_bazy_personalnyh_dannyh); tartib-qoida: [lex.uz/docs/4732190](https://lex.uz/docs/4732190), 71-сон, 2020-02-08).
- **Eslatma**: "Davlat shaxsiylashtirish markazi" (Art. 8) va "pd.gov.uz" portali — bir xil tizimning ikki nomi/interfeysi deb qabul qilinadi (markaz — yuridik vakolatli organ, pd.gov.uz — uning onlayn xizmati). Bu ikkisining aniq institutsional munosabati ochiq manbada to'liq tasdiqlanmadi — agar tizim biometrik/telekom ma'lumot saqlasa, ro'yxatdan o'tishdan oldin pd.gov.uz bilan to'g'ridan-to'g'ri aniqlashtirish tavsiya etiladi.

### 1.3 Chet el bulutidan foydalanish mumkinmi

- **15-modda (chegaradan tashqariga uzatish, lex.uz'dan)**: shaxsiy ma'lumotlarni chet elga uzatish quyidagilardan biri bilan ruxsat etiladi: subyektning yozma roziligi; konstitutsiyaviy tuzum, jamoat tartibi, fuqarolar huquqlari, sog'liq yoki jamoat axlog'ini himoya qilish zarurati; xalqaro shartnoma. Davlat xavfsizligi/farovonligini himoya qilish uchun uzatish **cheklanishi yoki taqiqlanishi mumkin**.
- **27-1-modda, lokalizatsiya qilinmagan ma'lumotlar uchun**: chet elda saqlash/qayta ishlash mumkin, agar: (a) qabul qiluvchi davlat shaxsiy ma'lumotlarni "yetarli himoya qiluvchi davlat" deb tanilgan bo'lsa, YOKI (b) operator vakolatli davlat organi tasdiqlagan talablarga mos standart shartnoma shartlarini yoki majburiy korporativ qoidalarni qabul qilgan bo'lsa, YOKI (c) operator xalqaro standartlarga mos kelsa.
- **Xulosa**: AWS/GCP/Hetzner kabi chet el bulutlarida odatiy ERP ma'lumotlarini (lokalizatsiya qilinmagan toifalar) saqlash **qonunan mumkin**, lekin yuqoridagi uch shartdan birini bajarish kerak — bu amalda huquqiy/shartnoma ishini talab qiladi. Biometrik/genetik/telekom ma'lumotlari esa **har qanday holatda** O'zbekistonda qolishi shart.

---

## 2. O'zbekistondagi hosting/bulut provayderlari

### 2.1 UzCloud (uzcloud.uz)

- Xizmatlar: IaaS/VPS, Bare Metal, VPC, **Managed Kubernetes**, **DBaaS** (PostgreSQL, MySQL, Valkey), **S3-mos obyekt xotira**, Backup-as-a-Service, kolokatsiya ([uzcloud.uz/en/about](https://uzcloud.uz/en/about)).
- VM narxlari (**2026-10-10 holatiga ko'ra**, QQS bilan, so'mda): vCPU — 85 000/oy; RAM — 12 000/oy (GB); SSD Standard — 2 000/oy (GB); SSD NVMe (yuqori IOPS) — 3 300/oy (GB); HDD — 700/oy (GB); ochiq IPv4 — 50 000/oy. Tayyor tariflar: Start (1 vCPU/2GB/10GB HDD) — 116 000 so'm/oy; Business (8 vCPU/16GB/80GB NVMe) — 1 136 000 so'm/oy ([uzcloud.uz/en/prices](https://uzcloud.uz/en/prices) — narxlar o'zgarishi mumkin, bu sanaga qayta tekshirilmagan bo'lsa manbadan yangilansin).
- Managed Kubernetes narxi: bitta-node boshqaruv paneli — 500 000 so'm/oy; HA boshqaruv paneli — 1 500 000 so'm/oy; worker-nodelar VM stavkalari bo'yicha. **SLA: 99,9% Control Plane** ([uzcloud.uz/en/cloud/k8s](https://uzcloud.uz/en/cloud/k8s)).
- DBaaS (PostgreSQL/MySQL/Valkey): HA klaster, avtomatik backup, PITR tiklash; narxi VM kabi hisoblanadi (vCPU/RAM/disk + backup). Alohida DBaaS SLA raqami rasmiy sahifada **topilmadi** ([uzcloud.uz/en/cloud/dbaas](https://uzcloud.uz/en/cloud/dbaas)).
- S3 obyekt xotira: Standard — 450 so'm/GB/oy saqlash + 300 so'm/GB chiquvchi trafik; Cold — 350 so'm/GB/oy + 350 so'm/GB chiquvchi; kiruvchi va UzCloud ichki trafik bepul ([uzcloud.uz/en/cloud/s3](https://uzcloud.uz/en/cloud/s3)).
- **Data-markazlar**: 5 ta Tier III-toifali data-markaz, 4 mintaqada — Ohangaron (2 ta sayt), Toshkent (Zangiota), Buxoro, Qo'qon; >300 km geografik tarqalish; 299 rack, 5,1 MVt, 34 000+ CPU yadrosi, 650+ TB RAM, 36+ PB xotira ([uzcloud.uz/en/infrastructure/data-centers](https://uzcloud.uz/en/infrastructure/data-centers)). **Jismonan O'zbekistonda joylashgani tasdiqlangan.**
- Sertifikat holati: Tier III **Design** sertifikati olingan; Tier III Constructed Facility/Operational Sustainability sertifikatlari **hali jarayonda** (bitmagan) — shu manba.
- Infratuzilma darajasidagi mavjudlik da'vosi: 99,982% (<1,5 soat/yil uzilish) — bu DC infratuzilma da'vosi, shartnoma SLA'si emas. Rasmiy ommaviy oferta hujjatida **aniq foizli SLA topilmadi** — faqat sifat jihatidan majburiyatlar ("barqaror CPU/RAM ishlashi") ([uzcloud.uz/en/oferta](https://uzcloud.uz/en/oferta)).

### 2.2 Uztelecom / UzDC

- **Muhim aniqlik**: Uztelecom UzCloud platformasining o'zini taqdim etadi — "UZTELECOM UZCLOUD.UZ bulut platformasini taqdim etadi" ([uztelecom.uz yangiliklari](https://uztelecom.uz/ru/novosti/novosti/vygodnye-tarify-i-udobnyy-funkcional-uztelecom-predstavlyaet-oblachnuyu-platformu-videokonferencsvyazi-uzcloud-uz/)) — ya'ni **UzCloud va Uztelecom Cloud bir xil milliy bulut infratuzilmasining qismlari**, alohida raqobatchi emas.
- Yangi data-markazlar: Buxoro va Qo'qonda (2026), "UzCloud platformasining yagona konturi ichida" ishlaydi; ikkisi ham Uptime Institute'dan Tier III **Design** sertifikati olgan ([gazeta.uz, 2026-09-22](https://www.gazeta.uz/ru/2026/09/22/uztelecom/)).
- Narx namunasi (to'liq tasdiqlanmagan, JS-render sahifa): "Cloud 1" (1 vCPU/1GB RAM) — CPU 71 000 + RAM 10 000 + Storage 9 000 + ochiq IP 50 000 = jami ~140 000 so'm/oy ([cloud.uztelecom.uz](https://cloud.uztelecom.uz/)).
- Aniq foizli SLA **topilmadi**.

### 2.3 Beeline Cloud / fortifAI (fortifai.uz)

- **Muhim aniqlik**: cloud.beeline.uz endi fortifai.uz'ga yo'naltiriladi — bu Beeline Business'ning (LLC "UNITEL") joriy bulut brendi, ~2024-yil dekabr/2025-yil boshida ishga tushgan ([gazeta.uz, 2024-12-13](https://www.gazeta.uz/ru/2024/12/13/beeline/)).
- Xizmatlar: Virtual Data Center (Nutanix asosida), Managed Kubernetes, **S3 obyekt xotira** (2025-yil fevral/mart, Nutanix Objects asosida), domen ro'yxatdan o'tkazish, veb-hosting ([fortifai.uz](https://fortifai.uz/en/)).
- Managed baza (DBaaS) **topilmadi** — faqat umumiy "Virtual Data Center"da o'zi boshqariladigan baza joylashtirish.
- Narx va aniq SLA **ochiq sahifalarda topilmadi** — so'rov asosida taklif modeli ko'rinadi.
- Data-markaz: Beeline o'z data-markazi(lari) "O'zbekistonda joylashgan" deb bildiradi, lekin aniq shahar/Tier sertifikati **topilmadi** ([gazeta.uz](https://www.gazeta.uz/ru/2024/12/13/beeline/)).

### 2.4 Ucell Cloud

- **Tasdiqlandi: Ucell'ning bulut/IaaS mahsuloti YO'Q.** Ucell (COSCOM tomonidan boshqariladi) faqat mobil tarmoq operatori (GSM/UMTS/HSPA/LTE/5G) ([Wikipedia — Ucell](https://en.wikipedia.org/wiki/Ucell)). Topilgan yagona "bulut" aloqasi — 2017/2021-yillarda ZephyrTel bilan hamkorlikda mijozlar tajribasini boshqarish (CEM) SaaS vositasi (ResponseTek) — bu Ucell'ning uchinchi tomon SaaS'dan foydalanishi, bulut infratuzilmasi taklif qilishi emas.

### 2.5 Yandex Cloud — joylashuv (lokalizatsiya uchun muhim)

- **Yandex Cloud'ning O'zbekistonda jismoniy data-markazi YO'Q.** Rasmiy hujjatlashtirilgan mintaqalari: faqat `ru-central1` (Rossiya) va `kz1` (Qozog'iston, Qarag'andi, 2024-yilda ishga tushgan) ([yandex.cloud/en/docs/overview/concepts/geo-scope](https://yandex.cloud/en/docs/overview/concepts/geo-scope); [datacenterdynamics.com](https://www.datacenterdynamics.com/en/news/yandex-launches-new-cloud-region-in-kazakhstan/)).
- **Yandex Go (taksi ilovasi) bilan aralashtirmaslik kerak**: Yandex Go 2021-yilda O'zbekistonda shaxsiy ma'lumotlar lokalizatsiyasi uchun o'z ilova serverlarini joylashtirdi — bu Yandex Cloud infratuzilmasi emas va uchinchi tomonlarga umumiy maqsadli IaaS/PaaS sifatida taklif etilmaydi ([kun.uz, 2021-06-04](https://kun.uz/ru/news/2021/06/04/yandex-go-soobshchil-o-lokalizatsii-serverov-v-uzbekistane)).
- **Xulosa**: Yandex Cloud'da O'zbekiston ERP ma'lumotlarini saqlash ma'lumotlarni Rossiya yoki Qozog'istonga joylashtiradi, O'zbekistonga emas — lokalizatsiya talab qilinadigan ma'lumotlar (biometrik/genetik/telekom) uchun **mos kelmaydi**.

### 2.6 Qo'shimcha O'zbekiston provayderlari

- **Serverspace (serverspace.uz)** — ITGLOBAL.COM brendi; Toshkentda sayt bor (East Telecom YA DC data-markazi asosida). Narx namunasi: 1GB RAM/1 Core/25GB SSD ≈ 198 789 so'm/oy; 4GB/2 Core/80GB SSD ≈ 785 055 so'm/oy ([serverspace.uz/conditions/price](https://serverspace.uz/conditions/price/)).
- **East Telecom (XCloud)** — Toshkent Yunusobod tumanida Tier III (Design) data-markaz, Korea Telecom bilan hamkorlikda, 2024-yil aprelda ishga tushgan; narx **topilmadi** (faqat so'rov orqali) ([spot.uz, 2023-03-31](https://www.spot.uz/ru/2023/03/31/east-telecom/)).
- **UZINFOCOM Data Center (dc.uz)** — davlat IT integratori; Hosting, Kolokatsiya, VPS. Kolokatsiya narxi (~2025-08): 1U rack — 550 000 so'm/oy; 100 Mbit/s port — 150 000 so'm/oy. Managed DB/K8s/S3 **yo'q**. Aniq SLA/shahar **topilmadi** ([dc.uz](https://dc.uz/)).
- **BILLURCOM** — VPS/VDS, "161 000 so'mdan/oy" (faqat ikkinchi darajali manba orqali, mustaqil tasdiqlanmagan).

### 2.7 Taqqoslash — asosiy topilma

UzCloud/Uztelecom (bitta milliy platforma) — eng to'liq xizmat katalogi (VM, K8s, DBaaS, S3), eng ochiq narx jadvali va eng ko'p data-markazga ega yagona variant. Beeline/fortifAI va East Telecom raqobatchi, lekin narx/SLA shaffofligi past. Ucell'da bulut yo'q. Yandex Cloud biometrik/genetik/telekom ma'lumotlari uchun qonunan mos kelmaydi (O'zbekistonda data-markazi yo'q); oddiy ERP ma'lumotlari uchun qonunan taqiqlanmagan, lekin 1.3-bo'limdagi shartlarni bajarish zarurati va kam kechikish afzalligi tufayli tavsiya etilmaydi.

---

## 3. Axborot xavfsizligi talablari

### 3.1 Davlat tizimlariga ulanish — sertifikatlash/ekspertiza

- Qonun: **"Kiberxavfsizlik to'g'risida"**, ЗРУ-764-сон (2022-04-15) ([lex.uz/ru/docs/5960609](https://lex.uz/ru/docs/5960609)).
  - **18-modda**: davlat organlari va kritik axborot infratuzilmasi (KAI) obyektlarining axborot tizimlari **majburiy ekspertizadan** o'tishi shart; tartib vakolatli organ tomonidan belgilanadi.
  - **19-modda**: davlat organlari va KAI obyektlarining axborot tizimlarini kiberxavfsizlik bilan ta'minlash uchun ishlatiladigan apparat/dastur/kombinatsiyalangan vositalar **majburiy sertifikatlashdan** o'tishi shart.
- Vakolatli/sertifikatlovchi organ: **Davlat kiberxavfsizlik xizmati markazi (csec.uz)** — avvalgi UZCERT brendi endi csec.uz tarkibidagi bo'lim ([csec.uz/ru/company/departments/departament-uzcert/](https://csec.uz/ru/company/departments/departament-uzcert/)).
- Amalga oshirish tartib-qoidasi: **2024-11-14 ro'yxatga olingan tartibnoma** (Davlat xavfsizlik xizmati raisining 2024-10-15 dagi 114-sonli buyrug'i) — "Axborot tizimlari va resurslarining kiberxavfsizligini ta'minlash uchun ishlatiladigan apparat, apparat-dastur va dastur vositalarini sertifikatlash tartibi to'g'risidagi nizom" ([lex.uz/en/docs/7223619](https://lex.uz/en/docs/7223619)) — to'liq matn tafsiloti bu tadqiqotda chuqur o'qilmadi.
- **Hal qilinmagan savol (muhim)**: Oddiy xususiy SaaS ERP (davlat organi yoki rasman KAI deb e'lon qilinmagan) soliq.uz/OFD kabi davlat API'lariga faqat **mijoz sifatida** ulanganda, shu majburiy sertifikatlash/ekspertiza talabiga tushadimi — bu **ochiq manbada aniq tasdiqlanmadi**. Tizim uchun bu muhim amaliy savol: agar javob "ha" bo'lsa, MVP bosqichida sertifikatlash vaqti/narxi loyihaga qo'shiladi. **Tavsiya**: csec.uz bilan to'g'ridan-to'g'ri yozma so'rov yoki huquqiy xulosa olish.

### 3.2 Kriptografiya talablari

- ЗРУ-764, **11-modda**: vakolatli organ kriptografik himoya vositalarini ishlab chiqish/ishlab chiqarish/sotish uchun litsenziyalash vakolatiga ega, lekin modda o'zi **aniq majburiy algoritm standartlarini sanab o'tmaydi** — bu quyi normativ hujjatlarga havola qiladi (bu tadqiqotda olinmadi).
- **Faqat fiskal modul uchun aniq tasdiqlangan**: fiskal modullar "milliy standartlar asosida fiskal ma'lumotlarning kriptografik himoyasi"ni amalga oshiradi — ya'ni O'zbekiston milliy kripto-algoritmlari, umumiy xorijiy standart emas ([regos.uz blog](https://regos.uz/ru/blog/polezno-znat/chto-takoe-fiskalnyj-modul-pofm)).
- Umumiy dastur ta'minoti (fiskal modulsiz) uchun O'z DSt yoki GOST-ekvivalent kriptografiya majburiyligi haqida **qonun darajasidagi yagona manba topilmadi** — faqat fiskal modul niche'si uchun tasdiqlangan.

### 3.3 Audit log / hujjat saqlash muddatlari

- **Buxgalteriya hujjatlari — "Buxgalteriya hisobi to'g'risida" qonuni, 279-I-сон (1996-08-30), 23-modda** (to'g'ridan-to'g'ri lex.uz'dan tasdiqlangan: [lex.uz/en/docs/-90762](https://lex.uz/en/docs/-90762?ONDATE=01.05.2013)): birlamchi buxgalteriya hujjatlari va registrlari — **kamida 3 yil**; moliyaviy hisobotlar — qonun hujjatlarida belgilangan muddat davomida (aniq yil soni shu moddada ko'rsatilmagan, boshqa hujjatlarga havola qiladi).
  - **Diqqat**: ikkinchi darajali manbalarda (buxgalter.uz) "kamida 5 yil" degan raqam uchraydi — bu **qonun matnining o'ziga zid**; shuning uchun hujjatda faqat lex.uz'dan to'g'ridan-to'g'ri tasdiqlangan **3 yil** raqami ishlatiladi, 5 yil raqami **eskirgan/noto'g'ri ikkinchi darajali da'vo** sifatida belgilanadi.
- **Soliq hujjatlari — Soliq kodeksi, 22 va 84-moddalar**: umumiy minimal saqlash muddati **2024-01-01 dan 3 yilga** qisqartirildi (avval 5 yil edi). Shartga bog'liq holatlarda (84-modda, 2-qism) muddat shart davri + undan keyingi 3 yil; masalan 270-modda — 10 yildan ortiq ishlatiladigan asosiy vositalar uchun QQS tuzatish bilan bog'liq hujjatlar ~13 yilgacha, 306-modda — amortizatsiya hisobi butun amortizatsiya davri + undan keyingi 3 yil saqlanadi (manba: [buxgalter.uz](https://buxgalter.uz/publish/doc/text195926_skolko_let_hranit_dokumenty_buhgalterskogo_i_nalogovogo_ucheta) — ikkinchi darajali, Soliq kodeksining to'liq moddalarini to'g'ridan-to'g'ri lex.uz'dan qayta tasdiqlash tavsiya etiladi).
- **Audit log (tizim jurnali) saqlash muddati umumiy qoida sifatida — topilmadi.** Faqat KAI obyektlari uchun zaxira nusxalarini "kamida 3 oy" saqlash qoidasi uchraydi (past ishonchlilik, ikkinchi darajali manba, ЗРУ-764 yoki VM Qarori №167 (2023-05-31) matniga to'g'ridan-to'g'ri bog'lanmagan) — bu qoida faqat KAI toifasiga tegishli, umumiy SaaS uchun emas.

---

## 4. Internet va elektr ta'minoti sifati (offline-first asoslash uchun)

### 4.1 Internet tezligi va reyting

- Ookla Speedtest Global Index bo'yicha O'zbekiston mobil internet reytingi: 2020 — 133-o'rin; 2021-yanvar — 128-o'rin (mobil), 94-o'rin (statsionar); 2023-sentyabr — 100-o'rin (23,63 Mbps); 2024-iyul — 77-o'rin (30,34 Mbps) mobil, 83-o'rin (65,42 Mbps) statsionar; 2025-yanvar — 68-o'rin; 2025-may — 71-o'rin mobil (55,34 Mbps), 72-o'rin statsionar (87,23 Mbps); 2025-dekabr — 76-o'rinda (51,47 Mbps, oy ichida -5 pozitsiya); 2026-yanvar — yana 5 pozitsiya pastga tushgan ([uzdaily.uz](https://www.uzdaily.uz/en/ookla-uzbekistan-climbs-65-spots-in-mobile-internet-speed-rankings-over-the-past-four-years/); [kun.uz, 2024-07-16](https://kun.uz/en/news/2024/07/16/uzbekistan-climbs-11-spots-in-global-mobile-internet-speed-rankings); [kun.uz, 2026-01-17](https://kun.uz/en/news/2026/01/17/uzbekistan-slips-five-spots-in-global-mobile-internet-speed-ranking)).
- **Xulosa**: tezlik vaqt o'tishi bilan sezilarli o'sgan, lekin oy-oyma 5+ pozitsiyali tebranishlar barqaror bo'lmagan ulanish muhitini ko'rsatadi.
- Internet Society Pulse: O'zbekistonning umumiy internet chidamliligi (resilience) bahosi — **57%** ("kutilmagan nosozliklarga o'rtacha chidamlilik"), so'nggi 12 oyda hukumat buyurtmasi bilan to'xtatish — 0 ta (tekshirilgan sana holatida) ([pulse.internetsociety.org/en/reports/UZ](https://pulse.internetsociety.org/en/reports/UZ/)).
- Mintaqaviy tafovut (uzilish emas, kirish darajasi): boy oilalar ~93% internet kirishi, kambag'al oilalar ~64%; shahar ~86%, qishloq ~78%; Buxoro/Navoiy/Samarqand ~75,8% ([vzglyad.uz, 2024-10-08](https://vzglyad.uz/2024/10/08/statistika-internet/)).

### 4.2 Dalolatlangan internet to'xtatilish holatlari

- **2022-yil Qoraqalpog'iston**: mobil internet cheklovlari 2022-06-26 dan boshlangan, 2022-07-02 da to'liq to'xtatilgan, statsionar aloqa cheklovlari iyul oxirigacha davom etgan, favqulodda holat 2022-08-02 gacha (2022-07-21 da bekor qilingan) ([accessnow.org](https://www.accessnow.org/press-release/uzbekistan-information-vacuum-keepiton/); [eurasianet.org](https://eurasianet.org/uzbekistan-unrest-stricken-region-plunged-into-information-blackout)).
- **Yillik imtihon kuni to'xtatilishi**: kamida 2011-yildan boshlab takrorlanuvchi amaliyot — universitet qabul imtihonlari kunlari (odatda avgust boshida, 08:30–13:30 mahalliy vaqt) butun mamlakat bo'yicha mobil internet/SMS to'xtatiladi, ~19 million mobil foydalanuvchiga ta'sir qiladi ([rferl.org](https://www.rferl.org/a/uzbekistan-sms-internet-university-exam-police-cheating/25477815.html); [freedomhouse.org, 2024](https://freedomhouse.org/country/uzbekistan/freedom-net/2024)).
- **Hukumat to'xtatishlarining iqtisodiy narxi**: 2022-yilda ~$219,7–220 million (Top10VPN metodologiyasiga asoslangan, ikkinchi darajali) ([eurasianet.org](https://eurasianet.org/central-asias-government-ordered-internet-blackouts-costing-millions); [kun.uz, 2023-01-12](https://kun.uz/en/news/2023/01/12/govt-internet-shutdowns-cost-uzbekistan-about-220-million-in-2022)).

### 4.3 Elektr ta'minoti

- Milliy darajada ~10% elektr talabi qondirilmagan holatda qolmoqda, ayniqsa qishloq/kam ta'minlangan mintaqalarda uzilishlarga olib keladi (World Bank hisobotiga asoslangan) ([worldbank.org, 2025-06-25](https://www.worldbank.org/en/news/press-release/2025/06/25/uzbekistan-to-enhance-energy-production-through-hydropower-with-world-bank-support)).
- Tarmoq infratuzilmasi: >250 000 km elektr tarmog'i, ko'p qismi Sovet davridan qolgan; texnik yo'qotishlar ~20% ishlab chiqarilgan energiyadan ([adb.org hisobot](https://www.adb.org/sites/default/files/linked-documents/56231-001-ssa.pdf)).
- **2025-yil Toshkent misoli**: bir necha kunlik rejali/favqulodda uzilishlar — 2025-02-07 (Yunusobod/Chilonzor), 2025-04-17–21 (Almazor/Yunusobod, yuqori kuchlanishli liniya modernizatsiyasi uchun); "deyarli har bir tumanda" tez-tez uzilishlar haqida shikoyatlar ([kun.uz, 2025-07-26](https://www.kun.uz/en/news/2025/07/26/residents-and-businesses-hit-hard-by-frequent-power-cuts-in-tashkent); [zamin.uz](https://zamin.uz/en/uzbekistan/147998-tashkent-residents-to-face-5-day-power-outages.html)).
- **2022-yil yanvar mintaqaviy avariya**: Sovet davridan qolgan umumiy elektr tarmog'i uzilishi O'zbekiston, Qozog'iston, Qirg'izistonda keng ko'lamli uzilishga olib keldi; NetBlocks O'zbekistonning kuzatiladigan internet ulanishi faqat **37%** darajasida qolganini o'lchagan (uchtadan eng og'ir ta'sirlangan) ([netblocks.org](https://netblocks.org/reports/power-outage-knocks-out-connectivity-in-central-asian-states-XAD916Bg)).
- Rasmiy uzilish bildirishnomalari **het.uz** (mintaqaviy elektr tarmoqlari operatori) saytida tuman bo'yicha e'lon qilinadi, lekin bu umumlashtirilgan chastota/davomiylik statistikasi emas ([het.uz/en/lists/category/33](https://www.het.uz/en/lists/category/33)).
- **Rasmiy SAIDI/SAIFI uslubidagi milliy statistika (mijozga yiliga o'rtacha uzilish daqiqasi) topilmadi.**

### 4.4 Do'konlar darajasida statistika

- **Do'kon/chakana savdo darajasidagi internet uzilish statistikasi (daqiqa/yil) ochiq manbada topilmadi.** Qidirildi: mitc.uz (Raqamli texnologiyalar vazirligi statistikasi — faqat infratuzilma ko'rsatkichlari, uzilish ko'rsatkichisiz), stat.uz, umumiy veb-qidiruv — natija yo'q.

---

## Ochiq savollar

1. Oddiy xususiy SaaS ERP (davlat organi/KAI emas) soliq.uz/OFD API'lariga mijoz sifatida ulanganda ЗРУ-764'ning majburiy sertifikatlash/ekspertiza talabiga tushishi — csec.uz bilan to'g'ridan-to'g'ri aniqlashtirish kerak.
2. Umumiy dastur ta'minoti uchun majburiy kripto-algoritm standarti (O'z DSt yoki ekvivalent) — faqat fiskal modul uchun tasdiqlangan, umumiy qoida qonun darajasida topilmadi.
3. "Davlat shaxsiylashtirish markazi" va pd.gov.uz portalining aniq institutsional munosabati — agar tizim biometrik/telekom ma'lumot saqlasa, to'g'ridan-to'g'ri aniqlashtirish kerak.
4. ЗРУ-1125 (2026-03-26)'ning to'liq matni — faqat ikkinchi darajali agregatorlar orqali topildi, lex.uz'dan to'liq matn qo'lda o'qilmadi.
5. KAI obyektlari uchun "zaxira nusxa 3 oy" qoidasining asl qonun manbasi (ЗРУ-764 yoki VM Qarori №167) to'g'ridan-to'g'ri tasdiqlanmadi — past ishonchlilik.
6. UzCloud/Uztelecom/Beeline'ning rasmiy shartnoma (oferta) darajasidagi aniq foizli SLA raqami (DC infratuzilma da'vosidan farqli) — hech birida topilmadi, sotuvchi bilan to'g'ridan-to'g'ri so'rov kerak.
7. Do'kon darajasidagi internet/elektr uzilishi chastotasi/davomiyligi bo'yicha rasmiy statistika — topilmadi; faqat dalolatlangan alohida hodisalar va umumiy infratuzilma ko'rsatkichlari mavjud.

## Manbalar

**Shaxsiy ma'lumotlar qonuni:**
- [lex.uz/docs/4396428](https://lex.uz/docs/4396428) — ЗРУ-547 asl matni
- [lex.uz/ru/docs/5220725](https://lex.uz/ru/docs/5220725) — ЗРУ-666 (27-1-modda kiritilishi)
- [lex.uz/docs/8104580](https://lex.uz/docs/8104580), [lex.uz/docs/8099215](https://www.lex.uz/docs/8099215) — ЗРУ-1125 (2026-yil tuzatishi)
- [lex.uz/docs/4732190](https://lex.uz/docs/4732190) — ro'yxatdan o'tish tartib-qoidasi (71-сон)
- [pd.gov.uz](https://pd.gov.uz/storage/web/source/Request%20for%20database%20registration.pdf), [norma.uz](https://www.norma.uz/novoe_v_zakonodatelstve/kak_registriruyutsya_bazy_personalnyh_dannyh)

**Hosting/bulut:**
- [uzcloud.uz/en/prices](https://uzcloud.uz/en/prices), [uzcloud.uz/en/cloud/k8s](https://uzcloud.uz/en/cloud/k8s), [uzcloud.uz/en/cloud/dbaas](https://uzcloud.uz/en/cloud/dbaas), [uzcloud.uz/en/cloud/s3](https://uzcloud.uz/en/cloud/s3), [uzcloud.uz/en/infrastructure/data-centers](https://uzcloud.uz/en/infrastructure/data-centers), [uzcloud.uz/en/oferta](https://uzcloud.uz/en/oferta)
- [uztelecom.uz yangiliklari](https://uztelecom.uz/ru/novosti/novosti/vygodnye-tarify-i-udobnyy-funkcional-uztelecom-predstavlyaet-oblachnuyu-platformu-videokonferencsvyazi-uzcloud-uz/), [gazeta.uz, 2026-09-22](https://www.gazeta.uz/ru/2026/09/22/uztelecom/)
- [fortifai.uz](https://fortifai.uz/en/), [gazeta.uz, 2024-12-13](https://www.gazeta.uz/ru/2024/12/13/beeline/)
- [en.wikipedia.org/wiki/Ucell](https://en.wikipedia.org/wiki/Ucell)
- [yandex.cloud/en/docs/overview/concepts/geo-scope](https://yandex.cloud/en/docs/overview/concepts/geo-scope), [datacenterdynamics.com](https://www.datacenterdynamics.com/en/news/yandex-launches-new-cloud-region-in-kazakhstan/), [kun.uz, 2021-06-04](https://kun.uz/ru/news/2021/06/04/yandex-go-soobshchil-o-lokalizatsii-serverov-v-uzbekistane)
- [serverspace.uz/conditions/price](https://serverspace.uz/conditions/price/), [spot.uz, 2023-03-31](https://www.spot.uz/ru/2023/03/31/east-telecom/), [dc.uz](https://dc.uz/)

**Xavfsizlik:**
- [lex.uz/ru/docs/5960609](https://lex.uz/ru/docs/5960609) — ЗРУ-764 "Kiberxavfsizlik to'g'risida"
- [lex.uz/en/docs/7223619](https://lex.uz/en/docs/7223619) — sertifikatlash tartibnomasi
- [csec.uz/ru/company/departments/departament-uzcert/](https://csec.uz/ru/company/departments/departament-uzcert/)
- [regos.uz blog](https://regos.uz/ru/blog/polezno-znat/chto-takoe-fiskalnyj-modul-pofm) — fiskal modul kriptografiyasi
- [lex.uz/en/docs/-90762](https://lex.uz/en/docs/-90762?ONDATE=01.05.2013) — Buxgalteriya hisobi to'g'risidagi qonun, 23-modda
- [buxgalter.uz/.../text195926](https://buxgalter.uz/publish/doc/text195926_skolko_let_hranit_dokumenty_buhgalterskogo_i_nalogovogo_ucheta) — Soliq kodeksi saqlash muddatlari (ikkinchi darajali)

**Internet/elektr:**
- [pulse.internetsociety.org/en/reports/UZ](https://pulse.internetsociety.org/en/reports/UZ/)
- [accessnow.org](https://www.accessnow.org/press-release/uzbekistan-information-vacuum-keepiton/), [eurasianet.org](https://eurasianet.org/uzbekistan-unrest-stricken-region-plunged-into-information-blackout)
- [rferl.org](https://www.rferl.org/a/uzbekistan-sms-internet-university-exam-police-cheating/25477815.html), [freedomhouse.org/country/uzbekistan/freedom-net/2024](https://freedomhouse.org/country/uzbekistan/freedom-net/2024)
- [netblocks.org/reports/power-outage-knocks-out-connectivity-in-central-asian-states-XAD916Bg](https://netblocks.org/reports/power-outage-knocks-out-connectivity-in-central-asian-states-XAD916Bg)
- [worldbank.org, 2025-06-25](https://www.worldbank.org/en/news/press-release/2025/06/25/uzbekistan-to-enhance-energy-production-through-hydropower-with-world-bank-support), [adb.org hisobot](https://www.adb.org/sites/default/files/linked-documents/56231-001-ssa.pdf)
- [kun.uz, 2025-07-26](https://www.kun.uz/en/news/2025/07/26/residents-and-businesses-hit-hard-by-frequent-power-cuts-in-tashkent), [het.uz/en/lists/category/33](https://www.het.uz/en/lists/category/33)
- [uzdaily.uz](https://www.uzdaily.uz/en/ookla-uzbekistan-climbs-65-spots-in-mobile-internet-speed-rankings-over-the-past-four-years/)
