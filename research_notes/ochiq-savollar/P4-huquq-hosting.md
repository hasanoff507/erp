# P4 — Huquqiy, shaxsiy ma'lumot, hosting (OQ-039, 040, 041, 043)

**Maqsad:** `00-inventar.md` §5/§12 dagi P4 partiyasining 4 ta R-bandini desk-research bilan yopish: har biriga manbali javob, ishonch darajasi, spec'ga aniq taklif va qolgan tashqi tasdiq. · **Kim uchun:** asoschi, spec'ni yangilovchi agentlar, OQ-042 (ToS) uchun yurist. · **Bog'liq fayllar:** `spec/kod-uchun/15-xavfsizlik-va-audit.md` (§4.2, §5, §7, §8, §9, §10, OS1/2/4/7), `21-integratsiyalar.md` (§12, §13, OS8), `22-ai-qatlami.md` (§7), `25-nofunksional-talablar.md` (§2, §3.2), `23-backend-arxitekturasi.md` (§8), `10-umumiy-arxitektura.md` (OS2/OS3), `05-mvp-chegarasi.md`, `26-ochiq-savollar-reestri.md` (A#28, B#27/51/53), `research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md`. · **Holat:** tadqiqot natijasi, 2026-10-16. Barcha manbalar shu sanada ochilgan. Spec fayllari **o'zgartirilmadi**.

**Usul:** qonun va qarorlar matni lex.uz'dan to'g'ridan-to'g'ri olindi (rasmiy o'zbekcha matn, kerak joyda ruscha norasmiy tarjima). Iqtiboslar asl tilda berilgan. Vendor ma'lumoti uzcloud.uz, pd.gov.uz, csec.uz, anthropic.com va docs.aws.amazon.com sahifalaridan olindi. WebSearch kvotasi tugagani uchun qidiruv Playwright orqali Google'da qilindi. Ikkinchi darajali manbalar faqat yo'naltiruvchi sifatida ishlatildi va ular alohida belgilangan.

---

## 0. Yig'ma

| OQ | Qisqa javob | Ishonch | Holat |
|---|---|---|---|
| **OQ-039** ЗРУ-764 ekspertiza/sertifikatlash | **Bizga majburiy emas.** 18–19-moddalar faqat davlat organlari va KAI reyestriga kiritilgan tizimlarga tegishli. Xususiy tizim uchun ekspertiza **ixtiyoriy** (DXX buyrug'i, reg. 3573, 2-band). **Alohida talab bor:** virtual kassani Davlat reyestriga kiritish uchun "Kiberxavfsizlik markazi" ekspertiza xulosasi kerak (VMQ-943, 4-ilova, 11-band; 15 ish kuni). Bu OQ-011 ga tegishli, ЗРУ-764 ga emas. | Yuqori (qonun matni). KAI tayinlanmasligi — o'rta-yuqori. | **YOPILDI** (Xat 3 — ixtiyoriy tasdiq) |
| **OQ-040** Claude API'ga chet elga uzatish | Lokalizatsiya bizga tegishli emas (27-1-m., ЗРУ-1125 tahriri). **Yangi:** VMQ **415** (29.07.2026, kuchga kirgan 03.08.2026) 49 ta "bir xil himoya" davlatini tasdiqladi. AQSh ro'yxatda **faqat EU-US DPF ishtirokchilari** uchun. Anthropic DPF ishtirokchisi **emas** (ikkinchi darajali manba). Demak to'g'ridan-to'g'ri Anthropic API'ga **shaxsga doir ma'lumot** yuborish uchun asos subyekt roziligi bo'ladi (15-m.). Standart shartnoma shartlari talablari hali tasdiqlanmagan (415, 7-band, muddat ~2026-11). Ikki toza yo'l bor: (1) promptdan oldin **majburiy maskalash** — shunda shaxsga doir ma'lumot chiqmaydi; (2) Claude'ni **AWS Bedrock EU** orqali chaqirish — Germaniya, Fransiya, Irlandiya va boshqalar ro'yxatda. **Yangi xavf:** MJtK 46-2-m. 2-qismi (ЗРУ-1115, 2026-01) — shaxsga doir ma'lumotga AI yordamida qonunga xilof ishlov berish uchun BHMning 50–100 baravari miqdorida jarima. | Yuqori (qonun/qaror). Anthropic DPF holati — o'rta. | **QISMAN** (yurist: rozilik matni va maskalangan ma'lumot maqomi) |
| **OQ-041** Ma'lumot buzilishi xabari | **Umumiy (ichki) buzilish uchun qonunda muddat yo'q.** Transchegaraviy uzatishda tarqalish bo'lsa — vakolatli organga (IIV huzuridagi Migratsiya va personallashtirish departamenti) **24 soatda xabar, 72 soatda batafsil axborot** (VMQ 415, 4-band). Kiberxavfsizlik insidenti bo'lsa — DXX (csec) ga xabar berish majburiyati bor, muddat ko'rsatilmagan (ЗРУ-764, 16-m.). Subyektlarga ma'lumot o'zgarganda, yo'q qilinganda yoki kirish cheklanganda yozma xabar beriladi (ЗРУ-547, 31-m.). pd.gov.uz menyusida "buzilganlik haqida xabar berish" xizmati bor, lekin sahifa 404 qaytaradi. | Yuqori (matn). Format — past. | **QISMAN** (format; yurist runbook'ni ko'radi) |
| **OQ-043** UzCloud xizmatlari | **S3-mos ombor — bor**, narxi tasdiqlandi. **KMS — katalogda yo'q.** **Tempo/Jaeger — yo'q** (K8s sahifasi o'z Prometheus/Grafana stackini ulashni taklif qiladi). **Tinch holatda shifrlash** — faqat BaaS uchun yozilgan ("encrypted during transfer and storage"); S3, DBaaS va VM uchun yo'q. **DBaaS PITR** — hujjat mundarijasida "coming soon", DBaaS sahifasida backup "optional add-on". **SLA** — marketing raqami 99,982% va K8s Control Plane 99,9%; **ofertada foiz ham, kompensatsiya ham yo'q**. **Yangi xavf:** oferta 4.4 — to'lov kechiksa server o'chiriladi va 20 kundan keyin ma'lumot butunlay yo'q qilinadi. | Yuqori (vendor sahifalari, 2026-10-16) | **QISMAN** (savdo bo'limi: shartnoma SLA, DBaaS PITR/HA, at-rest shifrlash) |

**Spec'ga ta'sir qiladigan eng muhim 5 topilma:**
1. `15` §9.1, `05` #6 va §8-4, `21` §13 va OS8 dagi "ЗРУ-764 noaniqligi — eng katta bloklovchi omil" endi **bloklovchi emas**. Uning o'rnini bitta aniq talab egallaydi: virtual kassa reyestri uchun csec ekspertizasi (OQ-011 jadvali).
2. `22` §7 da "PII masking standart **yoqilmagan**, chunki lokalizatsiya qonuni ruxsat beradi" degan asos **noto'g'ri**. Lokalizatsiya va transchegaraviy uzatish alohida qoidalar. Maskalash **standart yoqilgan va o'chirib bo'lmaydigan** bo'lishi kerak.
3. `15` §9.2/§5.2, `22` #6, `09` #8 dagi "chet elga yuborish qonuniy" degan da'vo to'liq emas. Anthropic'ga (AQSh, DPF yo'q) shaxsga doir ma'lumot yuborish uchun **rozilik yoki boshqa asos** kerak.
4. Shaxsga doir ma'lumotlar bo'yicha vakolatli organ amalda **IIV huzuridagi Migratsiya va personallashtirish departamenti** (VMQ 415, 3-band; pd.gov.uz sarlavhasi). ЗРУ-547 8-moddasi esa hamon "VM huzuridagi Davlat personallashtirish markazi" deydi.
5. UzCloud'da "sir-ombori" ham, KMS ham yo'q. `23` §8 dagi "UzCloud sir-ombori" iborasi noto'g'ri. Shuningdek, oferta bo'yicha to'lov kechiksa ma'lumot o'chiriladi — bu billing/ops xavfi.

---

## 1. OQ-039 — ЗРУ-764 majburiy ekspertiza/sertifikatlash xususiy SaaS ERP'ga tegishlimi

### Javob
- **ЗРУ-764 bo'yicha majburiy ekspertiza** (18-m.) faqat uch toifaga tegishli: (a) davlat organlarining axborot resurslari, (b) davlat organlarining axborot tizimlari, (c) **KAI obyektlari toifasiga kiritilgan** axborot tizimlari. Boshqa tizimlar uchun ekspertiza **subyektning tashabbusi bilan** o'tkaziladi (DXX buyrug'i bilan tasdiqlangan Nizom, 2-band).
- **Majburiy sertifikatlash** (19-m.) **mahsulotga emas**, kiberxavfsizlikni ta'minlash *vositalariga* (apparat/dastur) tegishli. U ham faqat davlat organlari va tashkilotlari hamda KAI obyektlari tizimlari uchun majburiy. Bizning ERP kiberxavfsizlik vositasi emas.
- **KAI maqomi** avtomatik berilmaydi. KAI obyektlari ta'rifi keng ("ishlab chiqarish sohasida, shuningdek iqtisodiyotning boshqa tarmoqlarida"), lekin toifalash mezonlarini va yagona reyestrni vakolatli organ (DXX) belgilaydi va yuritadi (26–27-m.; PQ-167 2023: "Vaqtinchalik Yagona davlat reyestri"). Kichik do'konlar uchun ERP'ni KAI reyestriga kiritish haqida ochiq manbada hech qanday belgi yo'q.
- **Bizga baribir tegishli bo'lgan narsalar:**
  1. **"Kiberxavfsizlik subyekti" umumiy majburiyatlari** (16-m.): insidentlar haqida vakolatli organga xabar berish, raqamli izlarni saqlash va hokazo. Bu OQ-041 ga o'tadi.
  2. **Virtual kassa reyestri:** agar o'z virtual kassamizni Davlat reyestriga kiritsak (OQ-011), arizaga *"виртуал касса ёки онлайн-НКМ дастурий маҳсулотига «Киберхавфсизлик маркази» ДУК томонидан берилган экспертиза хулосаси"* ilova qilinadi. Xulosa 15 ish kunida beriladi. Bu ЗРУ-764 dan emas, VMQ-943 dan kelib chiqadigan **alohida va aniq** talab. Narx ochiq manbada topilmadi (csec.uz "Xizmatlar" sahifasi bo'sh render bo'ladi).
- Muhim tafsilot: ishlatilayotgan tizim ekspertizasi har 2 yilda, veb-sayt ekspertizasi har yili (Nizom 6–7-bandlar). Bu faqat ekspertizadan o'tadigan tizimlar uchun. Ixtiyoriy ekspertizaga kirsak, shu davriylik bizga ham qo'llanishi mumkin. **Ishonch: o'rta** — matnda "киберхавфсизлик субъектларининг" deyilgan, cheklov yo'q.

### Dalil
- **ЗРУ-764, 18-m.** (lex.uz/ru/docs/5960609, 2026-10-16): «Экспертизе на соответствие требованиям кибербезопасности в обязательном порядке подлежат: информационные ресурсы государственных органов; информационные системы государственных органов; информационные системы, включенные в категорию объектов критической информационной инфраструктуры.»
- **ЗРУ-764, 19-m.:** «Аппаратные, аппаратно-программные и программные средства, применяемые для обеспечения кибербезопасности информационных систем и ресурсов государственных органов и организаций, а также объектов критической информационной инфраструктуры, подлежат сертификации в обязательном порядке.»
- **ЗРУ-764, 26–27-m.:** «Критерии категорирования объектов критической информационной инфраструктуры определяются уполномоченным государственным органом.» / «Уполномоченный государственный орган ведет единый реестр объектов критической информационной инфраструктуры.» **11-m.:** vakolatli organ — Davlat xavfsizlik xizmati.
- **DXX raisining 113-son buyrug'i, AV'da 14.11.2024 reg. № 3573** (o'zgartirish 3573-1, 14.07.2025), Nizom 2-band (lex.uz/docs/7222910): «Давлат органларининг ахборот тизимлари ва ресурслари, муҳим ахборот инфратузилмаси объектлари тоифасига киритилган ахборот тизимлари киберхавфсизлик талабларига мувофиқлик юзасидан мажбурий тартибда экспертизадан ўтказилади. Мазкур банднинг биринчи хатбошисида кўрсатилганидан бошқа ахборот тизимлари ва ресурсларини киберхавфсизлик талабларига мувофиқлик юзасидан экспертизадан ўтказиш киберхавфсизлик субъектларининг ташаббуси билан амалга оширилади.» Ekspertiza o'tkazuvchi tashkilot — «"Киберхавфсизлик маркази" давлат унитар корхонаси ва Ўзбекистон Республикаси Марказий банки» (1-band).
- **VMQ-943, 4-ilova (Davlat reyestrini yuritish tartibi), 11-band** (lex.uz/docs/4603329): «виртуал касса ёки онлайн-НКМ дастурий маҳсулотига «Киберхавфсизлик маркази» ДУК томонидан берилган экспертиза хулосаси» … «Бунда «Киберхавфсизлик маркази» давлат унитар корхонаси томонидан экспертиза хулосаси ариза келиб тушган кундан бошлаб 15 иш кунидан кечиктирмасдан тақдим этилади.» (VMQ 736 2020 va VMQ 255 2022 tahririda).
- **PQ-167, 31.05.2023** (lex.uz/ru/docs/6479197): DXX zimmasiga «сформировать Временный Единый государственный реестр объектов КИИ».
- csec.uz (2026-10-16): sayt o'zini «Центр кибербезопасности — Государственное учреждение» deb ko'rsatadi. Insident telefoni **555-02-1010**. "Xizmatlar" sahifasi kontentsiz render bo'ladi.

### Ishonch
- Qonun va Nizom matni bo'yicha xulosa — **yuqori**.
- Bizning ERP'ning KAI reyestriga kiritilmasligi — **o'rta-yuqori** (DXX qarori; ochiq reyestr yo'q).
- csec ekspertiza narxi — **noma'lum**.

### Spec'ga ta'sir (taklif, aniq matn)
- **`15` §9.1** — butun bo'lim o'rniga:
  > - ЗРУ-764 18-modda (majburiy ekspertiza) faqat davlat organlarining axborot resurslari/tizimlariga va **KAI reyestriga kiritilgan** axborot tizimlariga tegishli. 19-modda (majburiy sertifikatlash) esa shu toifalarda ishlatiladigan kiberxavfsizlik *vositalariga* tegishli. KAI toifalash mezonlarini va reyestrni DXX belgilaydi (26–27-m.). Bizning tizim KAI reyestrida yo'q, shuning uchun **ЗРУ-764 bo'yicha majburiy ekspertiza va sertifikatlash bizga tegishli emas**. Ekspertiza ixtiyoriy (DXX buyrug'i, reg. 3573, 2-band) (`research_notes/ochiq-savollar/P4-huquq-hosting.md` §1).
  > - **Alohida majburiy talab:** o'z virtual kassamizni Davlat reyestriga kiritishda (OQ-011) arizaga "Kiberxavfsizlik markazi" ekspertiza xulosasi ilova qilinadi (VMQ-943, 4-ilova, 11-band; 15 ish kuni). Bu Bosqich 5 rejasiga kiritiladi. Narxi csec'dan so'raladi.
  > - "Kiberxavfsizlik subyekti" sifatidagi umumiy majburiyatlar (insident xabari, raqamli izlarni saqlash — ЗРУ-764, 16-m.) §10 da.
- **`15` "Ochiq savollar" 1-band** — o'chiriladi, o'rniga: "~~1.~~ Yopildi — P4 §1. Qoldi: virtual kassa reyestri uchun csec ekspertiza narxi (OQ-011)".
- **`05-mvp-chegarasi.md` Asosiy xulosa #6** — ro'yxatdan "ЗРУ-764 sertifikatlash noaniqligi" olib tashlanadi va o'rniga "virtual kassa reyestri uchun csec ekspertizasi (15 ish kuni, narx noma'lum)" yoziladi. **§(xavflar) 4-band** "Hali ochiq" → "**Yopildi** (P4 §1): majburiy emas. Faqat virtual kassa reyestri uchun csec ekspertiza xulosasi kerak". **177-qator** "Keyin tekshiriladi" ro'yxatidan ЗРУ-764 bandi olib tashlanadi.
- **`21-integratsiyalar.md` §13 jadvalidagi "Kiberxavfsizlik sertifikatlash (ЗРУ-764)" qatori:** "Majburiyligi noaniq" → "Majburiy emas (KAI emas). Virtual kassa reyestri uchun csec ekspertiza xulosasi — OQ-011 qatorida". **OS8** → "Yopildi (P4 §1)".
- **`26` reestri:** Xat 3 ni kutadigan qator bo'lsa, "Xat 3 — ixtiyoriy tasdiq, bloklamaydi" deb belgilanadi.

### Holat: **YOPILDI**
Qo'shimcha tasdiq **ixtiyoriy**: Xat 3 (csec.uz) ga savol "biz KAI emasmiz va ekspertiza ixtiyoriy — to'g'rimi; virtual kassa ekspertizasi narxi qancha" shaklida qayta yozilsin. Javob kodni bloklamaydi.

---

## 2. OQ-040 — ZRU-547: Claude API'ga chet elga shaxsga doir ma'lumot uzatish

### Javob
**(a) Lokalizatsiya — bizga tegishli emas.** Hududda saqlanishi shart bo'lgan toifalar faqat uchta: biometrik ma'lumot, genetik ma'lumot, telekom operatori abonentlari ma'lumoti (27-1-m., ЗРУ-1125 tahriri, 27.03.2026). Bazani Davlat reyestrida ro'yxatdan o'tkazish ham faqat shu toifadagi bazalar uchun (20-m., ЗРУ-1125 tahriri). Oldingi tadqiqot xulosasi to'g'ri.

**(b) Transchegaraviy uzatish — alohida qoida.** Uning shartlari quyidagicha:
- **15-m.:** uzatish "bir xil himoyani ta'minlovchi" davlatlarga amalga oshiriladi. Ro'yxatda bo'lmagan davlatga uzatish faqat uch holda mumkin: subyektning **roziligi**, konstitutsiyaviy tuzum/jamoat tartibini himoya qilish, yoki xalqaro shartnoma.
- **27-1-m. 3-qism:** lokalizatsiya qilinmaydigan ma'lumotni chet elda saqlash va ishlov berish uchta shartdan biri bajarilganda mumkin: (1) davlat "bir xil himoya" davlati deb tan olingan; (2) vakolatli organ talablariga mos **standart shartnoma shartlari / majburiy korporativ qoidalar** qabul qilingan; (3) vakolatli organ tasdiqlagan ro'yxatdagi **xalqaro standartlarga** rioya qilinadi.
- **VMQ 415 (29.07.2026, kuchga kirgan 03.08.2026):**
  - 49 ta davlat ro'yxati tasdiqlandi. Unda Germaniya, Fransiya, Irlandiya, Buyuk Britaniya, Shveytsariya, Shvetsiya, Italiya, Ispaniya va boshqalar bor.
  - **AQSh "*" belgisi bilan:** faqat "EU-US Data Privacy Framework doirasida faoliyat ko'rsatayotgan kompaniyalar uchun".
  - Ro'yxatdagi davlatlarga uzatish qo'shimcha ruxsatsiz va vakolatli organni xabardor qilmasdan bajariladi.
  - Ro'yxatda bo'lmagan davlatlarga uzatish uchun vakolatli organ belgilagan huquqiy, tashkiliy va texnik shartlar bajarilishi kerak.
  - Standart shartnoma shartlari va majburiy korporativ qoidalarga talablar **3 oy ichida** tasdiqlanishi kerak (7-band) — taxminan 2026-11 boshigacha. 2026-10-16 holatida lex.uz'da topilmadi.
- **Anthropic holati:**
  - API tijorat shartlari bo'yicha nazoratchi AQShdagi Anthropic PBC (Yevropadan tashqari mijozlar uchun).
  - Anthropic DPA (2025-02-24) EU SCC (Module 2/3), UK va Swiss addendum'larini o'z ichiga oladi va Commercial Terms'ga avtomatik kiradi.
  - Buzilish haqida mijozga xabar — **48 soat ichida**.
  - DPF ishtirokchisi **emas**. Privacy Policy (2026-09-10) DPF'ni tilga olmaydi. Ikkinchi darajali manbaga ko'ra 2026-10-04 dagi DPF reyestr qidiruvi "not a registered participant" natijasini bergan. Reyestr sahifasi Playwright'da render bo'lmadi, shuning uchun mustaqil tasdiqlanmadi.
  - **Xulosa:** to'g'ridan-to'g'ri `api.anthropic.com` ga shaxsga doir ma'lumot yuborish — ro'yxatda bo'lmagan qabul qiluvchiga uzatish hisoblanadi. Hozir ishlaydigan yagona asos — **subyekt roziligi** (15-m.). Standart shartnoma shartlari yo'li vakolatli organ talablari tasdiqlangandan keyin ochiladi. Anthropic'ning EU SCC'lari O'zbekiston talablariga moslik tekshiruvidan o'tmagan.

**(c) Amaliy yo'llar** (biri yetarli, ikkalasi birga bo'lsa eng xavfsiz):
1. **Majburiy maskalash** (`tenant_glossary`): mijoz/kontragent F.I.Sh., telefon, JSHSHIR va STIR (yakka tadbirkor uchun) promptdan oldin tokenga almashtiriladi. AI-01/AI-05 agregat raqamlar bilan ishlaydi. Shunda **shaxsga doir ma'lumot chegaradan chiqmaydi**. Qabul qiluvchi tomonidan identifikatsiya qilib bo'lmaydi, kalit bizda qoladi. 16-m. "egasizlantirish" ta'rifi va VMQ 415 dagi "эгасизлантирилган маълумотлар" iborasi shu yo'lni qo'llab-quvvatlaydi. Lekin kalit bizda qolgan psevdonimlashtirish egasizlantirish hisoblanadimi — buni **yurist tasdiqlashi kerak**.
2. **Claude'ni AWS Bedrock EU orqali chaqirish:** Bedrock EU "Geo" inference profili Claude Sonnet/Haiku 5.5 uchun eu-central-1 (Frankfurt), eu-west-1/2/3, eu-north-1, eu-south-1/2, eu-central-2 regionlarida mavjud. Bu davlatlarning barchasi VMQ 415 ro'yxatida. Ishlov beruvchi AWS (DPF ishtirokchisi). `AiProvider` porti allaqachon bor (`21` §12), shuning uchun bu adapter almashtirish xolos. Narx va model mavjudligi farqi tekshirilmagan — bu asoschi qarori.
3. **ToS'da transchegaraviy uzatishga rozilik bandi** (OQ-042). Yo'l 1/2 bilan birga zaxira asos sifatida.

**(d) Qo'shimcha majburiyatlar:**
- **23-m. 2-qism:** shaxsga doir ma'lumot uchinchi shaxsga berilsa, subyekt **3 kun ichida yozma** xabardor qilinadi. Maskalashsiz AI chaqiruvi (masalan AI-06 nasiya eslatmasi matnida mijoz ismi) har bir chaqiruvda bu majburiyatni keltirib chiqaradi. Bu maskalashni majburiy qilish uchun yana bir sabab.
- **31-m. 3-qism:** mulkdor (do'kon — tenant) ishlov berishni uchinchi shaxsga (bizga va bizning sub-processor'imizga) yozma rozilik, shartnoma ijrosi yoki qonunda nazarda tutilgan hollarda topshirishi mumkin. Shuning uchun ToS'da "operator/ishlov beruvchi" roli va sub-processor ro'yxati (UzCloud, AWS/Anthropic, Eskiz, Telegram) yoziladi.
- **MJtK 46-2-m. 2-qism** (ЗРУ-1115, 21.01.2026): *"Сунъий интеллект технологияларидан фойдаланган холда шахсга доир маълумотларга қонунга хилоф равишда ишлов бериш…"* — jarima BHMning 50–100 baravari, qurol musodara qilinadi. 1-qism (umumiy buzilish): fuqarolarga BHMning 7 baravari, mansabdor shaxslarga 50 baravari. pd.gov.uz FAQ dagi "3–5 / 5–10 BHM" raqamlari eskirgan.
- **Nomuvofiqlik:** MJtK 46-2-m. 1-qismi hamon *"жисман Ўзбекистон Республикаси ҳудудида жойлашган техник воситаларда … сақлашга оид талабларга риоя этмаслик"* iborasini saqlaydi. Bu ЗРУ-666 davridagi keng lokalizatsiya talabining izi va ЗРУ-1125 bilan mos kelmaydi. Biz baribir UzCloud'da saqlaymiz, shuning uchun bizga xavf yo'q. Faqat qayd sifatida.

### Dalil
- **ЗРУ-547, 271-modda (ЗРУ-1125 tahriri, 27.03.2026)** (lex.uz/docs/4396419, o'zbekcha rasmiy): «Ушбу модданинг иккинчи қисмида назарда тутилмаган шахсга доир маълумотлар куйидаги шартлардан бири бажарилган тақдирда, Ўзбекистон Республикаси ҳудудидан ташқарида сақланиши ва уларга ишлов берилиши мумкин: чет давлатни шахсга доир маълумотларнинг бир хил ҳимоя қилинишини таъминловчи давлат сифатида тан олиш; оператор томонидан ваколатли давлат органи тасдиқлайдиган талабларга жавоб берувчи стандарт шартномавий шартлар ёки мажбурий корпоратив қоидалар қабул қилиниши ва уларга риоя этилиши; рўйхати ваколатли давлат органи томонидан тасдиқланадиган шахсга доир маълумотларни бошқариш ва сақлаш соҳасидаги халқаро стандартларга оператор томонидан риоя этилиши.»
- **ЗРУ-547, 15-m.:** «Шахсга доир маълумотларнинг бир хилда ҳимоя қилинишини таъминламайдиган чет давлатлар ҳудудига шахсга доир маълумотларни трансчегаравий узатиш қуйидаги ҳолларда амалга оширилиши мумкин: субъектнинг ўз шахсга доир маълумотларини трансчегаравий узатиш бўйича розилиги мавжуд бўлганда; …»
- **ЗРУ-547, 20-m. 1-qism (ЗРУ-1125 tahriri)** (ruscha norasmiy tarjima, lex.uz/ru/docs/4396428): «Базы персональных данных, подлежащие обязательному хранению на территории Республики Узбекистан в соответствии с частью второй статьи 271 настоящего Закона, подлежат регистрации в Государственном реестре баз персональных данных.»
- **ЗРУ-547, 23-m. 2-qism:** «Шахсга доир маълумотлар учинчи шахсга берилган тақдирда, мулкдор ва (ёки) оператор бу ҳақда субъектни уч кун ичида ёзма шаклда хабардор қилади.»
- **ЗРУ-547, 16-m.** (ruscha): «Обезличиванием персональных данных являются действия, в результате совершения которых определение принадлежности персональных данных конкретному субъекту становится невозможным.»
- **ЗРУ-547 tahrirlar ro'yxati** (lex.uz, 2026-10-16): ЎРҚ-683 (2021), ЎРҚ-880 (2023), ЎРҚ-1125 (2026-03-26), ЎРҚ-1158 (2026-07-13, 3-m. — maxsus huquqiy rejim hududi, bizga ta'siri yo'q), ЎРҚ-1174 (2026-09-11, 25-m. — vasiylik, bizga ta'siri yo'q).
- **VMQ 415, 29.07.2026** (lex.uz/docs/8369688; ruscha karta lex.uz/ru/docs/8371371; pd.gov.uz/posts/view?id=53, 2026-08-07):
  - 3-band: «Ички ишлар вазирлиги ҳузуридаги Миграция ва персоналлаштириш департаменти (кейинги ўринларда — ваколатли давлат органи)…»
  - 4-band: «Рўйхатга киритилмаган чет давлатларга шахсга доир маълумотларнинг ҳар қандай шаклда узатилишига оператор ва шахсга доир маълумотлар базаси мулкдори томонидан ваколатли давлат органи белгилаган ҳуқуқий, ташкилий ва техник шартлар бажарилган тақдирда рухсат берилади»
  - 7-band: «…уч ой муддатда … стандарт шартномавий шартлар ва мажбурий корпоратив қоидаларга нисбатан талабларни тасдиқласин.»
  - Ilova, 2-pozitsiya: «Америка Қўшма Штатлари *» — «* Европа Иттифоқи ва АҚШ ўртасидаги маълумотларни ҳимоя қилишнинг ҳадли дастури (EU-US Data Privacy Framework) доирасида фаолият кўрсатаётган компаниялар учун.»
  - Ro'yxatda **10. Германия**, 16. Ирландия, 8. Буюк Британия, 42. Франция, 45. Швейцария, 46. Швеция, 20. Италия, 17. Испания, 34. Россия ва b.
- **MJtK 46-2-m.** (lex.uz/docs/97664, 2026-10-16): 1-qism sanksiyasi «фуқароларга базавий ҳисоблаш миқдорининг етти баравари, мансабдор шахсларга эса — эллик баравари» (ЗРУ-726). 2-qism (ЗРУ-1115, 21.01.2026): «Сунъий интеллект технологияларидан фойдаланган холда шахсга доир маълумотларга қонунга хилоф равишда ишлов бериш, уларни … тарқатиш, — … базавий ҳисоблаш миқдорининг эллик бараваридан юз бараваригача миқдорда жарима солишга сабаб бўлади.»
- **Anthropic DPA** (anthropic.com/legal/data-processing-addendum, 2026-10-16): effective 2025-02-24. EU SCC Module 2/3 havola orqali kiritilgan. «Anthropic will notify Customer in writing without undue delay, but in any event within 48 hours, after becoming aware of any Security Breach» (G.1). DPA «incorporated into and forms part of the Anthropic Commercial Terms of Service».
- **Anthropic Privacy Policy** (anthropic.com/legal/privacy, effective 2026-09-10): DPF tilga olinmagan. Uzatish uchun adequacy qarorlari va SCC ishlatiladi. Yevropadan tashqarida nazoratchi — Anthropic PBC (San Francisco).
- **DPF holati** (ikkinchi darajali, Google natijasi, 2026-10-16): "Anthropic compliance: GDPR, AI Act, DPA, training, transfers" — «holds no [DPF] certification. The registry at dataprivacyframework.gov was searched again on 4 October 2026». **Ishonch o'rta.** dataprivacyframework.gov/list da qo'lda tekshirish kerak.
- **AWS Bedrock** (docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html, 2026-10-16): Claude Sonnet 5.5 va Haiku 5.5 — Geo inference: eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3. Claude Opus 5.5 in-region — eu-west-2 (London).

### Ishonch
- Qonun va qaror matnlari — **yuqori**.
- Anthropic DPF'da yo'qligi — **o'rta** (bitta ikkinchi darajali manba va Privacy Policy'da DPF eslatilmagani).
- Kalit bizda qolgan maskalangan ma'lumot "shaxsga doir emas" deb hisoblanishi — **o'rta**, yurist kerak.
- Standart shartnoma shartlari talablari hali yo'qligi — **o'rta** (lex.uz'da qidiruvda topilmadi; muddat 2026-11 boshigacha).

### Spec'ga ta'sir (taklif, aniq matn)
- **`22-ai-qatlami.md` §7, "PII masking (ixtiyoriy himoya qatlami)" bandi** — butunlay almashtiriladi:
  > - **PII maskalash — majburiy, standart yoqilgan, tenant o'chira olmaydi.** Promptga yuborilishidan oldin jismoniy shaxsga oid maydonlar (mijoz/kontragent F.I.Sh., telefon, JSHSHIR, yakka tadbirkor STIR'i, manzil) `tenant_glossary` tokeniga almashtiriladi ("mijoz A"). Javob qaytgach kod tokenni asl qiymatga qaytaradi. Sabab: Anthropic (AQSh) VMQ 415 ro'yxatida faqat DPF ishtirokchisi bo'lsa qamraladi, Anthropic esa DPF ishtirokchisi emas. Maskalanmagan ma'lumot transchegaraviy uzatish (ZRU-547 15-m.) va uchinchi shaxsga berish (23-m., 3 kunda yozma xabar) hisoblanadi. AI orqali qonunga xilof ishlov berish — MJtK 46-2-m. 2-qism (BHMning 50–100 baravari) (`research_notes/ochiq-savollar/P4-huquq-hosting.md` §2).
  > - Maskalab bo'lmaydigan istisno — **AI-03 OCR rasmi** (faktura/yuk xati fotosida yetkazib beruvchi rahbarining ismi bo'lishi mumkin). U `AI_PII_ROUTE` sozlamasi orqali faqat **VMQ 415 ro'yxatidagi davlatda ishlov beradigan endpoint**ga yuboriladi (masalan AWS Bedrock EU Geo profili). Bunday endpoint sozlanmagan bo'lsa, AI-03 o'chiriladi.
- **`22` §7 "Ma'lumot lokalizatsiyasi" bandi, `22` Asosiy xulosa #6, `09` Asosiy xulosa #8** — "…chet el API'ga (Claude) yuborilishi mumkin" iborasi o'rniga:
  > "Lokalizatsiya majburiyati faqat biometrik/genetik/telekom ma'lumotga tegishli (ZRU-547 27-1-m., ЗРУ-1125). Lekin **chet elga uzatish** alohida qoida bilan tartibga solinadi (15-m., 27-1-m. 3-qism, VMQ 415). Shuning uchun Claude'ga faqat maskalangan yoki agregat ma'lumot yuboriladi (§7)."
- **`15` §5.2 "Boradi" bandi** — "…chet elga yuborilishi ZRU-547 27-1 modda doirasida **qonuniy**" o'rniga: "…**faqat maskalangan holda** yuboriladi (`22` §7). Maskalanmagan shaxsga doir ma'lumot Anthropic'ga (AQSh, DPF yo'q) faqat subyekt roziligi bilan yuborilishi mumkin (15-m.)". **"Ochiq savol" bandi** o'rniga: "Hal qilindi (P4 §2): asos — maskalash (shaxsga doir ma'lumot chiqmaydi) + EU endpoint (VMQ 415 ro'yxati). Zaxira asos — ToS'dagi rozilik. Yurist tasdig'i: OQ-042."
- **`15` §9.2 oxirgi bandi** — "uch shartdan qaysi birini tanlash — ochiq savol" o'rniga:
  > "Chet elga uzatish: VMQ 415 (29.07.2026) bilan 49 davlat tan olingan. AQSh faqat EU-US DPF ishtirokchilari uchun. Anthropic DPF ishtirokchisi emas, shuning uchun §5.2/`22` §7 dagi maskalash va EU endpoint qoidalari qo'llanadi. Vakolatli organ — IIV huzuridagi Migratsiya va personallashtirish departamenti (pd.gov.uz)."
  **`15` OS4** → "Yopildi (P4 §2); yurist tasdig'i OQ-042".
- **`21-integratsiyalar.md` §12 "Xavfsizlik" bandi** oxiriga:
  > "Yuboriladigan ma'lumot: faqat maskalangan/agregat (`22` §7). `AiProvider` uchun ikki adapter: `AnthropicDirect` (PII yo'q promptlar) va `BedrockEu` (OCR va PII bo'lishi mumkin bo'lgan promptlar, VMQ 415 ro'yxatidagi region). Tanlov `AI_PII_ROUTE` sozlamasi bilan qilinadi."
- **`10-umumiy-arxitektura.md` OS3** → "Hal qilindi: majburiy maskalash + EU endpoint (P4 §2)". **`26` A#28** interimi — "Faqat zarur maydonlar yuboriladi, **jismoniy shaxs identifikatorlari majburiy maskalanadi**, OCR — faqat VMQ 415 ro'yxatidagi endpoint orqali", sababi: "VMQ 415 + ZRU-547 15/23-m.".
- **Yangi qaror taklifi (`01`, asoschi):** "AI endpoint: matn — Anthropic API (maskalangan); OCR va PII ehtimoli bor vazifalar — AWS Bedrock EU Geo." Muqobil: hammasi Bedrock EU orqali, narx farqi tekshirilsin.

### Holat: **QISMAN**
- **Interim (kod uchun):** maskalash majburiy (`FLAG` emas, doimiy). `AiProvider` ikki adapter bilan quriladi. OCR faqat EU endpoint orqali, sozlanmagan bo'lsa o'chiq. `accepted_terms_version` saqlanadi (OQ-042).
- **Kim tasdiqlaydi:**
  - **Yurist:** (1) kalit bizda qolgan psevdonimlashtirish 16-m. ma'nosida egasizlantirish hisoblanadimi; (2) ToS'dagi transchegaraviy uzatish va uchinchi shaxsga berish roziligi matni; (3) tenant ↔ biz ↔ sub-processor rollari (31-m. 3-qism).
  - **Asoschi:** Bedrock EU qarori.
- Qayta tekshirish: 2026-11 dan keyin lex.uz'da VMQ 415 7-band ijrosini (standart shartnoma shartlari talablarini) tekshirish; dataprivacyframework.gov/list da "Anthropic" ni qo'lda qidirish.

---

## 3. OQ-041 — Ma'lumot buzilishi haqida xabar berish muddati va formati

### Javob
| Holat | Kimga | Muddat | Asos |
|---|---|---|---|
| Shaxsga doir ma'lumot **transchegaraviy uzatish jarayonida** tarqalib ketdi (masalan AI endpoint yoki chet el sub-processor tomonida) | Vakolatli organ — IIV huzuridagi Migratsiya va personallashtirish departamenti (pd.gov.uz) | **24 soat** — xabar; **72 soat** — sabablari va bartaraf etish choralari haqida batafsil axborot | VMQ 415, 4-band 3-xatboshi |
| **Kiberxavfsizlik insidenti** (tizimimizga ruxsatsiz kirish, ma'lumotni o'g'irlash yoki blokirovka qilish) | Vakolatli organ — DXX (amalda "Kiberxavfsizlik markazi", tel. 555-02-1010) | Qonunda muddat yo'q ("xabardor qilish" majburiy). O'zimiz tergov o'tkazsak — natijasi ham xabar qilinadi | ЗРУ-764, 16-m., 22-m. 2-qism |
| Shaxsga doir ma'lumot **o'zgartirilgan, yo'q qilingan yoki kirish cheklangan** bo'lsa | Subyekt va ishlov berishning boshqa ishtirokchilari (tenant) | Muddat ko'rsatilmagan, **yozma shaklda** | ЗРУ-547, 31-m. 2-qism |
| Ishlov berish shartlari buzilgani haqida ma'lumot bor | — (ichki majburiyat) | Darhol: ishlov berishni vaqtincha to'xtatish yoki yo'q qilish | ЗРУ-547, 31-m. 2-qism |
| Sub-processor (Anthropic) bizga | Bizga | 48 soat | Anthropic DPA G.1 |

- **Mamlakat ichidagi oddiy buzilish** (masalan UzCloud'dagi bazamizdan sizib chiqish) uchun ZRU-547, Namunaviy tartib (AV reg. 3478, 15.11.2023) va VMQ 415 da **vakolatli organga xabar berish muddati yo'q**. Faqat ЗРУ-764 dagi umumiy insident xabari va 31-m. dagi subyektga yozma xabar bor.
- **Format:** pd.gov.uz menyusida "Shaxsga doir ma'lumotlarni buzilganlik haqida xabar berish" (`/personal-data-breach/create`) xizmati bor, lekin 2026-10-16 da **"Sahifa topilmadi" (404)**. Zaxira kanallar: pdpgovuz@gmail.com, devonxona (+99871) 207 70 95 (pd.gov.uz kontaktlari). Rasmiy shakl/maydonlar ro'yxati topilmadi.

### Dalil
- **VMQ 415, 4-band** (lex.uz/docs/8369688): «шахсга доир маълумотларнинг трансчегаравий узатиш жараёнида тарқалиб кетиш ҳолати аниқланган тақдирда, шахсга доир маълумотлар базасининг оператори бу ҳақида ваколатли давлат органига мазкур ҳолат аниқлангандан бошлаб 24 соат ичида хабар бериши ва 72 соат ичида маълумотларнинг тарқалиб кетиш сабаблари ва уларни бартараф этиш бўйича амалга оширилган ишлар ҳақида батафсил ахборот бериши шарт.»
- **ЗРУ-764, 16-m.** (lex.uz/ru/docs/5960609): субъекты кибербезопасности обязаны «уведомлять уполномоченный государственный орган о произошедших инцидентах кибербезопасности и киберпреступлениях, принимать меры по недопущению утери соответствующих цифровых следов … а также обеспечивать постоянное хранение сведений, необходимых для анализа инцидентов кибербезопасности». **22-m.:** «…При этом уполномоченный государственный орган должен быть уведомлен о результатах расследования.» **3-m.** «субъект кибербезопасности» ta'rifi — elektron axborot xizmatlari ko'rsatuvchi yuridik shaxs. Biz shu ta'rifga kiramiz deb hisoblaymiz — **o'rta** ishonch.
- **ЗРУ-547, 31-m.** (ruscha): «временно приостанавливать обработку или уничтожать персональные данные в случае наличия информации о нарушении условий их обработки; … уведомить в письменной форме субъекта, а также других участников обработки персональных данных в случаях изменения, уничтожения персональных данных и ограничения доступа к ним».
- **Namunaviy tartib, AV reg. 3478, 15.11.2023** (lex.uz/docs/6663967): "insident", "соат", "сизиб" so'zlari yo'q. Faqat 31-m. dagi yozma xabar takrorlanadi.
- **pd.gov.uz** (2026-10-16): sarlavha «O'zbеkiston Rеspublikаsi Ichki ishlаr vаzirligi huzuridagi Migratsiya va personallashtirish departamenti». Menyuda «Shaxsga doir ma'lumotlarni buzilganlik haqida xabar berish» bor, havola `/personal-data-breach/create` → «Sahifa topilmadi!».
- **csec.uz** (2026-10-16): «Контактный номер для сообщений об инцидентах кибербезопасности 555-02-1010».

### Ishonch
- Muddatlar (24/72 soat, transchegaraviy) — **yuqori**.
- Ichki buzilish uchun muddat yo'qligi — **o'rta-yuqori** (asosiy hujjatlar ko'rildi, maxsus qaror topilmadi).
- Format — **past**.

### Spec'ga ta'sir (taklif, aniq matn)
- **`15` §10, 3-band "Xabar berish"** — o'rniga:
  > 3. **Xabar berish** (runbook, eng qattiq muddat hammaga qo'llanadi):
  > - **T+0:** insident ochiladi (`incident_id`, aniqlangan vaqt UTC+5). Ishlov berish shartlari buzilgan bo'lsa, ta'sirlangan ishlov berish to'xtatiladi (ZRU-547 31-m.).
  > - **≤ 24 soat:** shaxsga doir ma'lumot ta'sirlangan bo'lsa — vakolatli organga (IIV huzuridagi Migratsiya va personallashtirish departamenti, pd.gov.uz xizmati yoki pdpgovuz@gmail.com) dastlabki xabar. Bu transchegaraviy holat uchun majburiy (VMQ 415 4-band), ichki holat uchun ixtiyoriy, lekin bir xil qilinadi. Kiberinsident bo'lsa — DXX/"Kiberxavfsizlik markazi"ga (555-02-1010) xabar (ЗРУ-764 16-m.). Ta'sirlangan tenant Egasiga M18 + email.
  > - **≤ 72 soat:** vakolatli organga batafsil axborot (sabab, ta'sirlangan yozuvlar soni/toifalari, bartaraf etish choralari). Tenant orqali subyektlarga yozma xabar (31-m.) — matn shabloni tenantga beriladi.
  > - **Tergov tugagach:** ЗРУ-764 22-m. bo'yicha natija DXX ga yuboriladi. Raqamli izlar (log, `audit_log`, infra loglari) o'chirilmaydi (16-m.).
  > - Sub-processor xabarlari: Anthropic ≤ 48 soat (DPA G.1). UzCloud — ofertada muddat yo'q, shartnomaga qo'shish so'raladi.
- **`15` §10 sarlavhasi ostidagi** "…xabar berish muddati **topilmadi** … taxmin" iborasi o'rniga: "Muddatlar manbali: VMQ 415 (24/72 soat, transchegaraviy), ЗРУ-764 16/22-m., ZRU-547 31-m. (P4 §3)."
- **`15` OS7** → "Qisman yopildi (P4 §3). Qoldi: pd.gov.uz buzilish shakli (404) — yurist/organdan so'raladi".
- Kod ta'siri — **runbook** + `audit_log`'ga `incident_*` voqealari, `audit_log` va infra loglarini kamida 1 yil o'chirmaslik. Bu ЗРУ-764 dagi "doimiy saqlash" iborasi uchun; aniq muddat yo'q, 5 yillik ichki siyosat (§6.3) allaqachon qamraydi.

### Holat: **QISMAN**
- **Interim:** yuqoridagi runbook — 24/72 soat barcha shaxsga doir ma'lumot insidentlariga qo'llanadi.
- **Kim tasdiqlaydi:** yurist (runbook va subyektga xabar shabloni). Format — pd.gov.uz shakli tiklanganda yoki departamentdan so'rov bilan (Xat ro'yxatiga qo'shish mumkin).

---

## 4. OQ-043 — UzCloud: S3, KMS, Tempo/Jaeger, at-rest shifrlash, SLA, narxlar

### Javob (2026-10-16, uzcloud.uz — operator: "Uzbektelecom" AJ)
| Savol | Javob | Manba |
|---|---|---|
| S3-mos obyekt ombori | **Bor.** "Совместимо с AWS S3 API", tarkibida uch karra replikatsiya. Standard 450 so'm/GB/oy + 300 so'm/GB chiquvchi trafik; Cold 350 + 350; kiruvchi trafik, UzCloud ichki trafik va Tas-IX bepul. Hujjat (bucket, AWS CLI, lifecycle/versioning) — "coming soon". | `/en/cloud/s3`, `/en/prices`, bosh sahifa |
| KMS-as-a-Service | **Yo'q.** "Xavfsizlik" bo'limida faqat Anti-DDoS, SIEM, ZTNA, IAM va WAF ("скоро") bor. IAM — SSO/MFA mahsuloti (35 900 so'm/foydalanuvchi, 300 foydalanuvchidan), KMS emas. | bosh sahifa menyusi, `/en/corporate/iam` |
| Tempo/Jaeger (trace) | **Yo'q.** K8s sahifasi: "Connect Prometheus, Grafana, and a logging stack" (o'zimiz o'rnatamiz). Hujjatda "Monitoring a cluster with Grafana — coming soon". | `/en/cloud/k8s`, `/en/docs` |
| Tinch holatda shifrlash | **Faqat BaaS uchun yozilgan:** "Backups are encrypted during transfer and storage". S3, DBaaS va VM disklari uchun **hech qanday bayonot yo'q**. | `/en/cloud/baas` |
| DBaaS (PostgreSQL) HA/PITR | Bosh sahifa: "Управляемый PostgreSQL с автоматическими резервными копиями и failover". DBaaS sahifasi: "Backup is connected as an optional add-on", "We help deploy the DBMS". PITR faqat hujjat mundarijasida ("Restoring from a backup (PITR) — coming soon"). Narx VM kabi hisoblanadi (vCPU/RAM/disk + backup). Pooler haqida ma'lumot yo'q. **Oldingi tadqiqotdagi "avtomatik backup + PITR" da'vosi rasmiy sahifada tasdiqlanmadi** — hozirgi sahifa "assisted/managed" modelni ko'rsatadi. | `/en/cloud/dbaas`, `/en/docs`, bosh sahifa |
| BaaS narxi | Basic: kuniga 1 marta, 7 kun saqlash — 2 000 so'm/GB/oy. Standard: kuniga 4 marta, 30 kun — 2 760 so'm/GB/oy. Hajm koeffitsienti ×1,3. "Includes S3 storage, encryption, and restore testing". Ofertada VM uchun bepul backup yo'q: haftalik backup (4 nusxa) pullik xizmat sifatida ko'rsatilgan (2.8, 4.6). | `/en/cloud/baas`, `/en/oferta` |
| SLA | Marketing: "SLA 99,982%" / "Uptime SLA 99,982%" (Tier III **Design** sertifikati asosida; TCCF va TCOS sertifikatlari "in progress"). K8s: "99.9% Control Plane SLA". **Ommaviy ofertada foizli SLA ham, kredit/kompensatsiya ham yo'q** — faqat "Stable CPU and RAM operation…" (4.10). Status sahifasi (2026-08-14 dan monitoring): S3 30 kunlik/12 oylik 99,99%; Toshkent DC virtualizatsiyasi 99,99%. | bosh sahifa, `/en/infrastructure/data-centers`, `/en/oferta`, `/en/status` |
| VM narxlari | O'zgarmagan: vCPU 85 000; RAM 12 000/GB; SSD 2 000/GB; NVMe 3 300/GB; HDD 700/GB; IPv4 50 000 (oyiga, QQS bilan). 100 Mbit/s internet va 100 Mbit/s Tas-IX barcha rejalarga kiradi. | `/en/prices` |
| K8s Control Plane | Narx sahifasi: single-node 500 000, HA 1 500 000 so'm/oy. **Bosh sahifada "Control Plane от 380к сум"** — nomuvofiqlik, savdo bo'limidan so'ralsin. | `/en/prices`, bosh sahifa |
| **Oferta xavfi** | 4.4: "If the User does not pay within 5 days after server shutdown — backup copies are created and the server is deleted. If 'Resume' is not clicked within 20 days after 'Suspended' status — all data is permanently deleted." Yuridik shaxslar: postpaid, hisob-faktura 5-sanagacha keladi, 10 kun ichida to'lanadi (6.2.5–6.2.6). Shartnomani bekor qilish — 15 kun oldin xabar berish. Rejali ishlar haqida 1 kun oldin xabar beriladi (4.16), tarif o'zgarishi haqida 10 kun oldin (4.19). | `/en/oferta` |
| Ma'lumot joylashuvi | S3, DBaaS, K8s va BaaS — "physically located in Uzbekistan". 5 ta DC: Ohangaron ×2, Zangiota, Buxoro, Qo'qon. | tegishli sahifalar |

### Ishonch
- Ro'yxatdagi mavjud/yo'q xizmatlar va narxlar — **yuqori** (2026-10-16 dagi rasmiy sahifalar).
- DBaaS PITR va at-rest shifrlash — **past** (sahifada yo'q ≠ xizmatda yo'q; savdo bo'limidan tasdiq kerak).
- Shartnoma SLA — ofertada **yo'qligi yuqori ishonch bilan tasdiqlandi**. Yuridik shaxs bilan alohida shartnomada bo'lishi mumkin (oferta 1.4, 3.9.4 — shartnoma Didox orqali tuziladi).

### Spec'ga ta'sir (taklif, aniq matn)
- **`15` §4.2, 1-variant** ichidagi "(masalan HashiCorp Vault yoki shunga o'xshash — taxmin, UzCloud'da tayyor KMS borligi tasdiqlanmagan…)" o'rniga:
  > "UzCloud katalogida KMS **yo'q** (2026-10-16, P4 §4: Xavfsizlik bo'limida faqat Anti-DDoS/SIEM/ZTNA/IAM/WAF). MVP: KEK — deploy-vaqtidagi sir (muhit o'zgaruvchisi). Keyingi bosqich — o'z-hosted Vault/OpenBao (K8s ichida)."
  **3-variant** → "UzCloud KMS — mavjud emas. Paydo bo'lsa, KEK joyi ko'chiriladi". **OS2** → "Yopildi: UzCloud KMS yo'q, ilova darajasidagi envelope encryption qoladi".
- **`15` §7.1, 1-band** — "UzCloud DBaaS — HA klaster + avtomatik backup + PITR" o'rniga:
  > "UzCloud DBaaS — 'failover va avtomatik backup' bosh sahifada aytilgan, lekin DBaaS sahifasida backup 'optional add-on' (BaaS: 1×/kun 7 kun yoki 4×/kun 30 kun), PITR esa faqat hujjat mundarijasida ('coming soon'). **Shartnomada PITR va HA yozma tasdiqlanmaguncha zaxira reja amal qiladi:** o'zimiz WAL-arxivlash (pgBackRest/WAL-G → UzCloud S3 Cold) bilan PITR qilamiz. RPO ≤ 5 daqiqa shu orqali ta'minlanadi."
- **`15` §8 jadvalidagi "Shifrlash (tinch holatda)" qatori:**
  > "UzCloud faqat BaaS uchun 'encrypted during transfer and storage' deydi. S3, DBaaS va VM uchun bayonot yo'q. Shuning uchun: (1) S3 ga yoziladigan hujjat va fotolar — ilova darajasida shifrlanadi (SSE-C yoki mijoz tomonida AES-GCM, kalit — envelope KEK). (2) Backup arxivlari — pgBackRest shifrlash bilan. (3) DBaaS disk shifrlashi savdo bo'limidan so'raladi."
- **`23-backend-arxitekturasi.md` §8, 348-qator:** "UzCloud sir-ombori yoki muhit o'zgaruvchisi orqali" → "**muhit o'zgaruvchisi** (deploy-vaqti siri; UzCloud'da sir-ombori/KMS yo'q — P4 §4)". **357-qator va OS3** → "Trace eksport — o'z-hosted Grafana Tempo (UzCloud'da tayyor xizmat yo'q, P4 §4)". **375-qator** (pooler) — "UzCloud DBaaS'da pooler haqida ma'lumot yo'q — MVP'da ilova pool'i, kerak bo'lsa o'z PgBouncer'imiz".
- **`10-umumiy-arxitektura.md` OS2** → "Yopildi: UzCloud S3 bor (AWS S3 API mos), Standard 450 so'm/GB/oy + 300 so'm/GB chiquvchi trafik (P4 §4)". **`26` B#27** → "Yopildi — S3 bor; `StoragePort` qoladi, MinIO zaxira shart emas (faqat local/dev)". **B#53** → "Yopildi — tayyor Tempo/Jaeger yo'q; o'z-hosted Tempo yakuniy". **B#51** → "Qisman: marketing 99,982%, K8s CP 99,9%, ofertada foiz yo'q; yuridik shaxs shartnomasida SLA va kompensatsiya bandi so'raladi".
- **`25-nofunksional-talablar.md` §2:** "UzCloud 99,982% … rasmiy oferta SLA'si emas" saqlanadi va qo'shiladi: "K8s Control Plane uchun 99,9% e'lon qilingan. UzCloud status sahifasi (uzcloud.uz/status) — monitoring manbai sifatida runbook'ga kiritiladi." **§3.2 jadval, DBaaS qatori** — "(HA, PITR)" → "(bitta tugun; HA ikkinchi tugun va BaaS qo'shimcha — ~+862 000 va hajm×2 000 so'm/oy, HA/PITR shartnomada tasdiqlanmagan)". **OS2** → "Ofertada foiz yo'q (tasdiqlandi, P4 §4) — shartnoma muzokarasi".
- **`25` yoki `15` ga yangi ops band (Yangi xavf):**
  > "UzCloud ofertasi 4.4: to'lov kechiksa server o'chiriladi va 'Suspended' holatidan 20 kun o'tgach ma'lumot qaytarib bo'lmaydigan tarzda yo'q qilinadi. Shuning uchun UzCloud hisobi uchun avto-to'lov/oldindan to'lov va billing alerti (hisob-faktura 5-sanada, muddat +10 kun) majburiy. Kamida bitta oflayn backup nusxasi boshqa provayderda (masalan boshqa mahalliy DC yoki sovuq arxiv) saqlanadi."

### Holat: **QISMAN**
- **Yopilganlar:** S3 (bor + narx), KMS (yo'q), Tempo/Jaeger (yo'q), ofertadagi SLA (yo'q), VM/S3/K8s/BaaS narxlari.
- **Qolganlar** (savdo bo'limi, info@uzcloud.uz / +998 77 718 76 70, kodni bloklamaydi):
  1. Yuridik shaxs shartnomasida SLA foizi va kompensatsiya;
  2. DBaaS PostgreSQL: HA, PITR, versiya, `max_connections`, pooler, disk shifrlash;
  3. S3: SSE va versioning/object lock;
  4. K8s Control Plane narxi (380k va 500k);
  5. insident xabari muddati (OQ-041).
- **Interim:** o'z WAL-PITR, ilova darajasidagi shifrlash, o'z-hosted Tempo, maqsad 99,5%.

---

## 5. OQ-042 (yurist) uchun kirish ma'lumotlari — ToS/oferta qoralamasi bandlari

Bular R emas, OQ-042 qoralamasi uchun manbali "majburiy tarkib" ro'yxati:
- **Oferta rekvizitlari** — ЗРУ-792 "Elektron tijorat to'g'risida", 16-m. (lex.uz/ru/docs/6213428). Oferta quyidagilarni o'z ichiga olishi shart: nomi; pochta va elektron manzil, telefon; litsenziya (kerak bo'lsa); shartnoma tuzish tartibi va aktseptni yuborish/qaytarib olish tartibi; o'zgartirish kiritish tartibi; yetkazib berish va to'lov shartlari, narxlar (tariflar); havola orqali kiritiladigan shartlar. 16-m. ga **2026-12-12 dan kuchga kiradigan o'zgartirishlar bor** (lex.uz belgisi) — yurist yangi tahrirni ko'rsin.
- **Til** — ЗРУ-792, 21-m.: «Условия договора должны быть сформулированы в конкретной, понятной форме на государственном языке. При необходимости они могут быть составлены на иных удобных для сторон языках одновременно с государственным языком.» Ya'ni ToS **o'zbek tilida majburiy**.
- **Aktsept** — 14-m.: aktsept "путем совершения действий по выполнению условий, содержащихся в оферте" ham bo'lishi mumkin. Ro'yxatdan o'tishdagi belgilash + `accepted_terms_version` yetarli asos bo'ladi.
- **Raqamli mahsulot shartnomasini tasdiqlash** — 20-m. (obuna onlayn-servisga; chek/kvitansiya, ichki hujjatlar, birlamchi hujjat bir tomonlama rasmiylashtirilishi mumkin).
- **Shaxsga doir ma'lumot bandlari** (P4 §2–3):
  - (a) tenant — mulkdor/operator; biz — topshiriq bo'yicha ishlov beruvchi "uchinchi shaxs" (31-m. 3-qism);
  - (b) sub-processorlar ro'yxati va joylashuvi (UzCloud — O'zbekiston; AI — AWS EU / Anthropic AQSh, maskalangan holda; Eskiz; Telegram);
  - (c) transchegaraviy uzatishga rozilik (15-m.) — zaxira asos;
  - (d) tenant o'z mijozlaridan rozilik olish majburiyati (`notify_consent`) va 23-m. dagi 3 kunlik xabar majburiyati qaysi tomonda ekanligi;
  - (e) buzilish xabari muddatlari (24/72 soat);
  - (f) subyekt so'rovlari (30-m.), o'zgartirish 3 kunda (Namunaviy tartib).
- **Xodim ma'lumoti** (`15` §5.1 "taxmin"): 20-m. 3-qism — "меҳнат тўғрисидаги қонунчиликка мувофиқ ишлов бериладиган" ma'lumotli bazalar ro'yxatdan o'tkazilmaydi. Lekin bu rozilik masalasini hal qilmaydi — 18-m. dagi "qonunchilikdagi majburiyatni bajarish" asosi; yurist tasdiqlaydi.

---

## 6. Topilgan spec nomuvofiqliklari (OQ-101 ga qo'shish uchun)
1. `22` §7 "PII masking — standart yoqilmagan, chunki lokalizatsiya qonuni ruxsat beradi" ↔ ZRU-547 15/23-m. + VMQ 415. Lokalizatsiya ≠ transchegaraviy uzatish (§2).
2. `15` §9.2 va §5.1 "Davlat shaxsiylashtirish markazi" ↔ VMQ 415 3-band / pd.gov.uz: vakolatli organ — **IIV huzuridagi Migratsiya va personallashtirish departamenti**.
3. `23` §8 "UzCloud sir-ombori" ↔ UzCloud'da sir-ombori/KMS yo'q (§4).
4. `15` §7.1 va `25` §3.2 "DBaaS (HA, PITR)" ↔ rasmiy sahifada PITR tasdiqlanmagan, backup — qo'shimcha xizmat (§4).
5. `05` #6 / §8-4, `21` §13 "ЗРУ-764 — bloklovchi" ↔ majburiy emas; bloklovchi faqat virtual kassa reyestri uchun csec ekspertizasi (§1).
6. `25` §3.2 K8s CP narxi (500 000) ↔ bosh sahifadagi "от 380к" (vendor ichki nomuvofiqligi).

---

## 7. Manbalar (hammasi 2026-10-16 da ochilgan)

**Qonun va normativ hujjatlar (lex.uz):**
- ЗРУ-547 "Shaxsga doir ma'lumotlar to'g'risida": o'zbekcha https://lex.uz/docs/4396419 · ruscha https://lex.uz/ru/docs/4396428 — 4, 8, 15, 16, 18, 20, 21, 23, 27, 27-1, 31, 33-m.; tahrirlar ЎРҚ-683, 880, 1125, 1158, 1174.
- ЗРУ-1125 (26.03.2026): https://lex.uz/docs/8104580 (pasport).
- VMQ 415 (29.07.2026) "Bir xil himoya davlatlari ro'yxati": https://lex.uz/docs/8369688 · https://lex.uz/ru/docs/8371371 · pd.gov.uz yangiligi https://pd.gov.uz/posts/view?id=53.
- ЗРУ-764 "Kiberxavfsizlik to'g'risida": https://lex.uz/ru/docs/5960609 — 3, 11, 16–19, 22–24, 26–27, 37-m.
- DXX raisining 113-son buyrug'i (AV reg. 3573, 14.11.2024; 3573-1, 14.07.2025) — ekspertiza Nizomi: https://lex.uz/docs/7222910 · https://lex.uz/ru/docs/7222926.
- PQ-167 (31.05.2023) KAI: https://lex.uz/ru/docs/6479197.
- VMQ-943 (23.11.2019), 4-ilova 11-band: https://lex.uz/docs/4603329 · https://lex.uz/ru/docs/4603340.
- Namunaviy tartib (AV reg. 3478, 15.11.2023): https://lex.uz/docs/6663967.
- MJtK 46-2-m.: https://lex.uz/docs/97664.
- ЗРУ-792 "Elektron tijorat to'g'risida": https://lex.uz/ru/docs/6213428 — 14, 16, 20, 21-m.

**Davlat portallari:** https://pd.gov.uz (bosh sahifa, /site/question, /site/for-nonresidents, /personal-data-breach/create → 404) · https://csec.uz/ru/services.

**Vendorlar:**
- UzCloud: https://uzcloud.uz/ (ru), https://uzcloud.uz/en/prices, /en/cloud/s3, /en/cloud/dbaas, /en/cloud/k8s, /en/cloud/baas, /en/corporate/iam, /en/docs, /en/status, /en/infrastructure/data-centers, /en/oferta.
- Anthropic: https://www.anthropic.com/legal/data-processing-addendum, https://www.anthropic.com/legal/privacy.
- AWS: https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html.

**Ikkinchi darajali (faqat yo'naltiruvchi):** Google qidiruv natijalari (Playwright, 2026-10-16) — "Anthropic compliance: GDPR, AI Act, DPA, training, transfers" (DPF reyestri 2026-10-04 da qidirilgan); VMQ 415 bo'yicha yangiliklar (uznews.uz, yuz.uz, servercore.com), asosiy matn esa lex.uz'dan olingan.
