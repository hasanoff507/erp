# Tekshiruv — fiskal integratsiya savollari (Research-1)

*2026-10-15 · Manba: `kamchiliklar-yakuniy.md` §3 (foydalanuvchi qarori kerak — band 2, 3, 5, 6), `spec/kod-uchun/21-integratsiyalar.md`, `16-offline-sync.md`, `research_notes/texnik/02-kassa-ofd-markirovka.md`, `06-raqobatchilar-texnik-va-uskunalar.md`, `10-bozorda-soliq-integratsiyasi.md`, `12-taxminlar-va-murojaatlar.md` + yangi veb-tadqiqot (2026-10-15). Metodologiya: lex.uz (birlamchi huquqiy manba), rasmiy/yarim-rasmiy portallar (help.crpt-turon.uz, buxgalter.uz, soliq.uz), bozor manbalari (vendor saytlari). Har bir tasdiqlanmagan/bir marotaba topilgan da'vo **"tasdiqlanmagan"** deb belgilangan. Mahsulot bo'shliqdan (from-scratch) qurilmoqda; soliq/fiskal integratsiya — farqlanish nuqtasi.*

---

## Q2. Fiskal yo'l: o'z virtual kassa (Davlat reyestri) vs reyestr hamkori orqali boshlash + pilot uskunasi

### Savol

Bizning o'z dasturiy virtual kassamizni (VMQ-943 asosida) Davlat reyestriga mustaqil kiritamizmi (4-ilova: 20+15+10+5 ish kuni, narx noma'lum) yoki reyestrda allaqachon bor hamkor (E-POS, UZKASSA, Rahmat POS/Multikassa, FiscalBox) orqali "oq-etiket"/API bilan boshlaymizmi? MoySklad va Poster qanday yo'l tutgan? Pilot uchun qanday uskuna (printer, skaner, tarozi, Android POS) arzon va keng tarqalgan?

### Bozorda qanday

| Kompaniya/vosita | Fiskal yo'l | API/uchinchi tomonga ulanish | Narx (topilgan) | Izoh |
|---|---|---|---|---|
| **REGOS** | O'z virtual kassa qo'shimchasi (EasyTrade desktop — tabiatan offline, + Cloud) | Pro tarifida MCP/webhook, Didox bilan EDO integratsiyasi | Virtual kassa qo'shimchasi +75 000 so'm/oy (`regos.uz/ru/price`) | Mustaqil reyestr yozuvi; uchinchi tomon POS uchun oq-etiket xizmati ko'rinmadi |
| **BILLZ** | Noma'lum (saytda OFD/Asl belgisi haqida dalil yo'q) | Ochiq API (`billz.io/uz/for-developers`) — lekin fiskal/markirovka uchun emas, CRM/buyurtma integratsiyasi uchun | Start 299k, Advanced 499k, Pro 999k so'm/oy | *(tasdiqlanmagan: OFD yo'li qaysi)* |
| **MoySklad** | **E-POS orqali** — "Регистрация продаж в налоговой Узбекистана через один клик" (`moysklad.uz`) | E-POS, Didox, Asl Belgisi | Bepul tarif: 1 nuqta/5 xodim | Uchinchi tomon reyestr-hamkori orqali ulangan — mustaqil reyestr yozuvi yo'q |
| **E-POS Systems** | O'z virtual kassasi (Cashdesk/Mobile) **+ "E-POS Communicator"** — "Integration module for developers... Connect E-POS to your CRM, ERP, websites and apps via REST API" (`epos.uz/en`); "istalgan kassa dasturini bir necha daqiqada E-POS platformasiga ulash mumkin" (`docs.epos.uz/uz`, "Integratorlar uchun kirish" sahifasi) | REST API, chek avtomatik yuboriladi, markirovka/QR/to'lov qo'llab-quvvatlanadi | Narx topilmadi (sahifa "alpha" bosqichida) | **Uchinchi tomon POS uchun fiskal backend-as-a-service namunasi** |
| **Rahmat POS / Multikassa** | O'z virtual kassasi + ochiq API | "Ochiq API yordamida biz bozordagi ommabop POS tizimlari bilan integratsiya qila olamiz" (`rhmt.uz/uz/pos/virtual-kassa/`) | Virtual kassa **123 600 so'm/oy**, Onlayn-NKM **100 000 so'm/oy**, to'lov terminali **0 so'm/oy**, SUNMI P3 uskuna **990 000 so'm** (bir martalik) | Markirovkani "to'liq qo'llab-quvvatlaydi" deb yozilgan |
| **FiscalBox** | Vositachi — Poster kabi xorijiy SaaS'ni O'zbekiston fiskalizatsiyasiga ulaydi | Shartnoma + API kalit almashinuvi orqali (`knowledge-base.joinposter.com`) | Aniq narx topilmadi | Poster uchun bir nechta hamkordan biri |
| **Poster POS** (xorijiy namuna) | Hamkor orqali — **3 muqobil yo'l**: E-POS Integration ($10/oy), FiscalBox, Rahmat POS/Multikassa ($5/oydan) | — | $5–10/oy | **"Registry hamkori orqali ulanish" patternining eng aniq dalili** — xorijiy POS O'zbekistonga mustaqil kirmasdan, bir nechta mavjud hamkordan birini tanlab fiskalizatsiya qiladi |
| **UZKASSA** | O'z uskuna/dastur vendori, reyestrda | Alohida OEM/API dalili topilmadi | N5 — 3 315 000 so'm, P100 — 1 950 000 so'm (`smartpos.uz`) | *(tasdiqlanmagan: uchinchi tomon POS uchun backend taklif qiladimi)* |

### Qonun/manba

- **VMQ-943 (lex.uz/docs/4603329), 4-ilova** — dastur ishlab chiquvchining mahsulotini Davlat reyestriga kiritish muddati: Soliq qo'mitasi qarori 20 ish kuni + Kiberxavfsizlik markazi xulosasi 15 ish kuni + fiskal ma'lumotlar operatori (FMO, "Yangi texnologiyalar" DUK) xulosasi 10 ish kuni + texnik tartibga solish agentligi/«O'zeltexsanoat» xulosasi 5 ish kuni — jami **~50 ish kuni** (ketma-ket/parallelligi aniq emas, bitta tekshiruv forki tomonidan topilgan, ikkinchisi mustaqil tasdiqlamagan). Zahira mablag' talabi (100/500/1000/200 BHM) virtual kassani **mustasno** qiladi. Sertifikatlash/ekspertiza xizmat haqi so'mda **hech qayerda topilmadi** — biroq **operatsion (davriy) xarajat bo'yicha aniq raqam topildi**: REGOS'ning rasmiy FAQ sahifasiga ko'ra, fiskal modul + fiskal ma'lumotlar operatori (FMO, "Yangi texnologiyalar" DUK) xizmati uchun yiliga **1 BHM** (2026-09-01 holatiga ~440 000 so'm) to'lanadi; oylik xizmat haqi REGOS foydalanuvchilari uchun 0 so'm, "boshqa foydalanuvchilar" (ya'ni boshqa dastur orqali ulangan reyestr a'zolari) uchun **100 000 so'm/oy** (`regos.uz/uz/product/regos-vcr/faq`, ikkinchi darajali manba — birlamchi lex.uz matnida tasdiqlanmagan, ehtiyotkorlik bilan qabul qilinsin). Bu — mustaqil reyestr yo'li (A) uchun ham, hamkor yo'li (B) uchun ham tegishli bo'lishi mumkin bo'lgan yagona topilgan davriy narx ko'rsatkichi.
- O'zbekistonda **yagona davlat OFD operatori** bor — "Yangi texnologiyalar" ilmiy-axborot markazi DUK (Soliq qo'mitasi qaramog'ida). E-POS, UZKASSA, REGOS, Rahmat POS — OFD emas, Davlat reyestriga kiritilgan dastur/uskuna **vendorlari**, ular ham shu yagona OFD orqali ishlaydi.
- Reyestrga kiritish uchun 10 hujjat turi (muvofiqlik sertifikati, Kiberxavfsizlik xulosasi, FMO integratsiya xulosasi va h.k.) — manba: `buxgalter.uz/uz/publish/doc/text195345`.

### Variantlar

**A. Mustaqil dastur sifatida Davlat reyestriga kiritish**
- *Pros*: to'liq nazorat, uzoq muddatda qo'shimcha oylik hamkor to'lovi yo'q, brend/strategik mustaqillik, OFD protokoliga to'g'ridan-to'g'ri kirish.
- *Cons*: ~50 ish kuni (ketma-ket bo'lsa ≈2,5 taqvim oyi) + sertifikatlash/ekspertiza narxi noma'lum (moliyaviy xavf), MVP jadvaliga sezilarli kechikish xavfi, jarayon birinchi marta qilinganda ko'proq davom etishi mumkin.

**B. Reyestr hamkori orqali boshlash (E-POS Communicator / Rahmat POS–Multikassa / FiscalBox)**
- *Pros*: kunlar/haftalar ichida ishga tushirish mumkin (Poster POS buni allaqachon 3 xil hamkor bilan amalga oshirgan — isbotlangan pattern), oylik narx taxminan aniq (Rahmat POS: ~100–125k so'm/do'kon, Poster hamkorlari: $5–10/oy), markirovka ko'pincha allaqachon "quti ichida" ishlaydi (Rahmat, E-POS).
- *Cons*: uchinchi tomonga texnik/narx/SLA bog'liqligi, ko'p-tenant SaaS uchun har bir do'kon hamkor tizimida alohida sozlanishi kerak bo'lishi mumkin (operatsion murakkablik — bizning markazlashgan arxitekturamizga ziddir), marja hamkor ulushi hisobiga kamayadi, uzoq muddatda baribir o'z reyestr yozuvi kerak bo'lishi mumkin.

**C. Gibrid (MVP = B, parallel A boshlanadi)**
- Pilotni B bilan (eng tez variant, masalan E-POS Communicator yoki Rahmat POS/Multikassa) ishga tushirish, shu bilan parallel ravishda mustaqil reyestr arizasi (A) uchun hujjatlarni tayyorlash va rasmiy so'rov (Xat 1) yuborish — bu allaqachon `21-integratsiyalar.md` §1 "Zaxira yo'l" sifatida yozilgan yondashuv bilan mos.

**Pilot uskunasi (eng arzon amaliy to'plam)**:
Virtual kassa rejimida alohida fiskal modul/Android POS terminal **shart emas** — brauzer ishlaydigan har qanday smartfon/planshet/PC yetarli. Eng arzon boshlang'ich to'plam: arzon USB shtrix-kod skaneri (~550 000 so'mdan, Keyboard Wedge rejimi, drayversiz) + termoprinter (ESC/POS, ~300–360 000 so'm, Xprinter XP-58IIT/LP-U58 kabi) ≈ **jami 850 000–950 000 so'm/kassa**, tarozi ixtiyoriy (250–750 000+ so'm, aniq protokol nomi topilmadi — "Frontol/LiteBox bilan integratsiya" umumiy da'vosi bor, tasdiqlanmagan). Android POS terminal (UZKASSA N5 3,3 mln, P100 1,95 mln, Rahmat'ning SUNMI P3 bundle 990 000 so'm) — faqat agar kassirga alohida uskuna kerak bo'lsa, MVP pilotda shart emas.

### Tavsiya

**B (reyestr hamkori, masalan Rahmat POS/Multikassa yoki E-POS Communicator) bilan pilotni boshlash, A (mustaqil reyestr arizasi) ni parallel boshlash.** Pilot uskunasi: smartfon/PC + arzon skaner + ESC/POS termoprinter (~900k so'm/kassa), Android POS terminal keyinroq.

**Ishonch darajasi: o'rta-yuqori.** Narx/muddat raqamlari (Rahmat POS, Poster hamkorlari) aniq topilgan va bir nechta manba bilan izchil; lekin ko'p-tenant SaaS holatida hamkor shartnomasi shartlari (narx qanday o'sadi 10, 100, 1000 tenant bilan) tekshirilmagan — rasmiy so'rov (Xat 1 + yangi so'rov E-POS/Rahmat POS'ga) tavsiya etiladi.

### Manbalar

- [lex.uz/docs/4603329](https://lex.uz/docs/4603329) — VMQ-943, 4-ilova (reyestr muddati/narx)
- [rhmt.uz/uz/pos/virtual-kassa/](https://rhmt.uz/uz/pos/virtual-kassa/) — Rahmat POS narxlari, ochiq API, markirovka
- [epos.uz/en](http://epos.uz/en), [docs.epos.uz/uz](https://docs.epos.uz/uz) — E-POS Communicator, "Integratorlar uchun kirish"
- [knowledge-base.joinposter.com/ru/setting-up-fiscalbox-integration-in-uzbekistan](https://knowledge-base.joinposter.com/ru/setting-up-fiscalbox-integration-in-uzbekistan) — Poster + FiscalBox
- [joinposter.com/en/applications](https://joinposter.com/en/applications) — Poster + E-POS/Multikassa narxlari
- [moysklad.uz](https://www.moysklad.uz/) — E-POS orqali fiskal ro'yxatga olish
- [regos.uz/ru/price](https://regos.uz/ru/price), [smartpos.uz/uz/kassalar](https://smartpos.uz/uz/kassalar) — narxlar
- [buxgalter.uz/uz/publish/doc/text195345](https://buxgalter.uz/uz/publish/doc/text195345_avtomatlashtirish_dasturlarini_soliq_organlarining_ahborot_tizimlari_bilan_integraciya_qilish_talablari) — reyestr hujjatlari
- `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md` — uskuna narxlari (skaner, printer, tarozi)

---

## Q3. Asl belgisi (CRPT Turon) MVP'da — uchinchi tomon POS qanday kirish oladi

### Savol

MVP'da markirovkalangan tovarni qanday qo'llab-quvvatlaymiz: CRPT Turon'ga rasmiy "integrator" bo'lib ro'yxatdan o'tamizmi (muddat/talab noma'lum), yoki har bir "do'kon" o'z ishtirokchi hisobidan API kalit olib bizga beradi, yoki mavjud integrator (MoySklad, E-POS, Rahmat POS) orqali proksi qilamiz?

### Bozorda qanday

| Kompaniya | Holat | Manba/iqtibos |
|---|---|---|
| **MoySklad** | Tasdiqlangan integratsiya | "Интеграция с Национальной системой цифровой маркировки товаров AslBelgisi" (`moysklad.uz`) |
| **REGOS** | Tasdiqlangan integratsiya | 06-fayl (oldingi tadqiqot) + WebFetch tasdiqlagan |
| **E-POS Systems** | Tasdiqlangan, "quti ichida" ishlaydi | "ASL Belgisi works out of the box. Cashiers don't even notice — they scan it like any other product" (`epos.uz/en`) |
| **Rahmat POS** | Tasdiqlangan | "tizim tovarlarni raqamli markalashni to'liq qo'llab-quvvatlaydi" (`rhmt.uz/uz/pos/virtual-kassa/`) |
| **BILLZ, HIPPO** | Noma'lum | Rasmiy sahifalarida Asl belgisi/CRPT haqida dalil topilmadi — bu yo'q degani emas, faqat reklama qilinmagan (**tasdiqlanmagan**) |

### Qonun/manba

1. **CRPT Turon'ning rasmiy "Partner Program" sahifasi mavjud** (`help.crpt-turon.uz/hc/en-us/articles/18977054012049`) va alohida **"Working with API and Technical Documentation"** bo'limi bor (xTrace Open API, "API NK" milliy katalog API'si). To'liq matn bu tekshiruvda 403 bilan yopiq chiqdi — faqat sarlavha va qidiruv natijalaridagi parchalar o'qildi (**tasdiqlanmagan to'liq**).
2. **Muhim farqlash (bir nechta mustaqil qidiruv natijasi bilan izchil)**: Asl belgisi tizimida ikki turdagi hisob bor:
   - **"Ishtirokchi" (Participant/MAI)** — markirovkalangan tovar aylanmasida qatnashuvchi biznes (bizning holatda — **har bir do'kon/tenant**). "Registration of a participant in the turnover of goods in NIS 'ASL BELGISI' and granting access to a Personal Account is carried out by the Operator **free of charge**" (`help.crpt-turon.uz`, qidiruv natijasi). Majburiyat yuzaga kelganidan ~7 kalendar kun ichida ro'yxatdan o'tish talab qilinishi haqida ma'lumot bor (**tasdiqlanmagan** — aniq modda raqami topilmadi).
   - **"Integrator"** — texnik dastur ishlab chiquvchi (bizning holatda — platforma/biz).
3. **Eng muhim topilma**: ishtirokchi (tenant)ning o'zi **"Participant's API Key Manager"** roli bilan o'z API kalitini yaratadi va buni istalgan dasturiy ta'minotga (hattoki uchinchi tomon POS'ga) berishi mumkin — "To interact with the Open API on behalf of a participant... it is necessary to create an API key... Each user can have only one active API key" (`help.crpt-turon.uz`, qidiruv natijalari). Bu — **rasmiy "integrator" maqomini olmasdan ham**, har bir tenant o'z kalitini bizning tizimga ulashi orqali texnik ishlashimiz mumkinligini ko'rsatadi.
4. **Rossiya "Chestny Znak" bilan solishtirish (FAQAT ANALOGIYA, O'zbekiston uchun tasdiqlanmagan)**: rasmiy "integratorlar reyestri" bor, sertifikatlash (attestatsiya) talab qilinadi; bir blog/forum manbasida loyihani amalga oshirish muddati "**120 ish kuni**" deb ko'rsatilgan (`vc.ru`, `dtf.ru` — norasmiy, **tasdiqlanmagan**, hatto Rossiya uchun ham rasmiy emas).
5. **833-son qaror (2020-12-31)** — huquqiy jihatdan muhim: "online NKM receipts should contain the marking code of sold goods in the 'Asl Belgisi' system **and send it to FMO**" — ya'ni kassa cheki markirovka kodini **FMO (fiskal ma'lumotlar operatori — "Yangi texnologiyalar" DUK) orqali** yuborishi kerak. Bu bizning OFD integratsiyasida ALLAQACHON rejalashtirilgan yo'l (`fiscal_receipts.payload`da kod). Bu, ehtimol, "sotuvni CRPT'ga qayd etish (chiqarish)" OFD→FMO kanali orqali ham amalga oshishini bildiradi — to'g'ridan-to'g'ri CRPT Turon API chaqiruvisiz. **Bu band mustaqil ikkinchi manba bilan tasdiqlanmagan**, lekin yuridik ahamiyati katta — Xat 2'da aniq so'ralishi shart.
6. **23-son qaror (2026-01-23)**, 2026-07-01'dan "elektron hisob-fakturada kod avtomatik tekshirish **va** kassada avtomatik kiritish" majburiy — bu kassaning kodni REAL-VAQTDA tekshirishi (`verify_code`) kerakligini ko'rsatadi, faqat passiv OFD orqali yuborish etarli emas — bu 5-banddagi gipotezani qisman zaiflashtiradi (faol tekshiruv alohida kerak).

### Variantlar

**A. Mustaqil "integrator" maqomi** — CRPT Turon bilan to'g'ridan-to'g'ri shartnoma, barcha tenantlar uchun bitta markaziy integratsiya. *Pros*: to'liq nazorat, bitta kodli yechim. *Cons*: rasmiy jarayon/muddat/narx hamon tasdiqlanmagan (403 bilan yopiq hujjat), Rossiya analogi bo'yicha oylab davom etishi mumkin (**tasdiqlanmagan**).

**B. Har bir tenant o'z "ishtirokchi" hisobidan API kalit yaratadi, biz shu kalit bilan ishlaymiz** (rasmiy "integrator" ro'yxatida bo'lmasdan). *Pros*: tezroq boshlash (ishtirokchi ro'yxatdan o'tishi bepul, kun/hafta darajasida bo'lishi mumkin), API kalit mexanizmi aynan shuning uchun mo'ljallangan ko'rinadi. *Cons*: har bir tenant uchun alohida kalit boshqaruvi (lekin bu bizning `tenant_secrets` naqshimizga allaqachon mos), CRPT Turon tomonidan rasmiy "integrator" sifatida tanilmasligimiz holatida qo'llab-quvvatlash/rasmiy status xavfi.

**C. Mavjud integratorlar (MoySklad, E-POS, Rahmat POS) orqali proksi/oq-etiket** — ular allaqachon ishlaydi. *Pros*: eng tez, markirovka "quti ichida" (E-POS misoli). *Cons*: uchinchi tomonga qattiq bog'liqlik, marja pasayishi, ko'p-tenant operatsion murakkablik.

### Tavsiya

MVP uchun **B+C gibrid**: (1) zudlik bilan rasmiy xat (Xat 2, loyiha allaqachon tayyor) yuborish va parallel B variantini (tenant darajasida ishtirokchi ro'yxatdan o'tish + API kalit, bizning `tenant_secrets` orqali saqlash) amalda sinab ko'rish — eng tez va huquqiy asoslangan yo'l ko'rinadi; (2) agar B murakkab/sekin chiqsa — C (E-POS Communicator yoki Rahmat POS orqali proksi) zaxira sifatida; (3) mustaqil "integrator" maqomi (A) — faqat miqyos o'sgandan keyin, uzoq muddatli parallel loyiha. Offline fallback bo'yicha allaqachon qabul qilingan qaror (narx ma'lum bo'lsa sotuvga ruxsat, bo'lmasa taqiq, `16-offline-sync.md` §7) bu tanlovdan mustaqil — o'z holicha qoladi.

**Ishonch darajasi: o'rta.** API kalit mexanizmi (B) kuchli, bir nechta qidiruv natijasi bilan izchil dalillangan; lekin bizning ko'p-tenant SaaS kontekstida CRPT Turon buni rasman qanday ko'rishi (har bir kichik do'kon alohida "ishtirokchi" sifatida ro'yxatdan o'tishi shartmi, yoki platforma darajasida bitta shartnoma kifoyami) hali **tasdiqlanmagan** — bu aynan Xat 2'da so'ralishi kerak bo'lgan markaziy savol.

### Manbalar

- [help.crpt-turon.uz/hc/en-us/articles/18977054012049](https://help.crpt-turon.uz/hc/en-us/articles/18977054012049--Partner-Program-of-LLC-CRPT-TURON) — Partner Program (sarlavha, to'liq matn 403)
- [help.crpt-turon.uz/hc/en-us/categories/4416596243601](https://help.crpt-turon.uz/hc/en-us/categories/4416596243601-Working-with-API-and-Technical-Documentation) — API/texnik hujjat bo'limi
- [help.crpt-turon.uz/hc/uz/articles/36062776211601](https://help.crpt-turon.uz/hc/uz/articles/36062776211601-Foydalanuvchi-profili-API-kalit-yaratish) — API kalit yaratish (Participant's API Key Manager)
- [epos.uz/en](http://epos.uz/en) — "ASL Belgisi works out of the box"
- [rhmt.uz/uz/pos/virtual-kassa/](https://rhmt.uz/uz/pos/virtual-kassa/) — Rahmat POS markirovka qo'llab-quvvatlashi
- [lex.uz/docs/-5205248](https://lex.uz/uz/docs/5205248) — 833-son qaror (NKM chekida markirovka kodi, FMOga yuborish)
- [lex.uz/docs/8012407](https://www.lex.uz/docs/8012407) — 23-son qaror (2026-07-01 avtomatik tekshirish)
- `vc.ru/retail/2939460`, `dtf.ru/flood/5073085` — Rossiya "Chestny Znak" integrator jarayoni (analogiya, tasdiqlanmagan)

---

## Q5. Offline qaytarish va ko'chirish (markirovkalangan tovar)

### Savol

Offline rejimda markirovkalangan tovarni qaytarish va o'z filiallar/omborlar orasida ko'chirish qanday siyosat bilan boshqariladi? Qonun qaytarish/ko'chirish uchun CRPT operatsiyasini talab qiladimi? Raqobatchilar buni offline qanday hal qiladi?

### Bozorda qanday

Raqobatchilarning (REGOS, MoySklad, E-POS, BILLZ, HIPPO, Smartup) rasmiy sahifalarida offline qaytarish/ko'chirish siyosati bu darajada texnik tafsilot bilan **tilga olinmagan** (marketing sahifalarida odatda bu chuqurlikdagi ma'lumot yo'q — **tasdiqlanmagan**, yo'q degani emas). E-POS'ning "ASL Belgisi works out of the box" da'vosi faqat SOTUVga tegishli ko'rinadi, qaytarish/ko'chirish alohida tilga olinmagan.

### Qonun/manba

- **buxgalter.uz** (`text186704`, huquqiy sharh maqolasi): "Xaridordan markirovkalangan tovarlar raqamli markirovkalash kodi aks ettirilgan **EHF yoki NKMning qaytarish cheki** asosida qaytariladi" — ya'ni qaytarish HAM elektron hujjat (NKM qaytarish cheki), kod bilan, orqali amalga oshishi kerak; bu — rasmiy fiskal/hujjat talab, oddiy "qoldirib qo'yish" emas. Alohida cheklov: dorixonalar yakuniy iste'molchiga berilgan dori vositalarini qabul qila olmaydi.
- **833-son qaror**: online NKM cheki markirovka kodini FMOga yuborishi kerak — qaytarish cheki ham mantiqan xuddi shu kanal orqali o'tishi kutiladi (**tasdiqlanmagan to'g'ridan-to'g'ri**, lekin izchil).
- **23-son qaror (2026-01-23)**: ko'chirish muddati — 72 soatdan oshmasligi kerak; matn "ichki" (bir tenant filiallari orasida) va "tashqi" (boshqa yuridik shaxsga) ko'chirishni aniq farqlamaydi.
- Bizning spec'da (`21-integratsiyalar.md` §3) e-TTN'ning ICHKI ko'chirishga majburiyligi hali **ochiq savol** (rasmiy xat kutilmoqda) — bu Q5 bilan bevosita bog'liq.
- Ichki filiallar/omborlar orasidagi ko'chirish uchun maxsus (sotuvdan/tashqi ko'chirishdan ajratilgan) qoida ochiq manbada **topilmadi**.
- **23-son qarorning o'zini o'qishda topilgan aniqlashtirish**: 72 soatlik ko'chirish bandi (8-bob, 30(a)-band) matnida "**mahsulot aylanmasi subyektlari o'rtasida**" (ya'ni **egalik huquqi o'tishi bilan bog'liq, turli yuridik shaxslar orasidagi**) ko'chirishga tegishli ko'rinadi — bitta yuridik shaxsning o'z filiallari/omborlari orasidagi harakatiga aniq tegishli ekanligi **tasdiqlanmagan** ([lex.uz/uz/docs/-8012407](https://lex.uz/uz/docs/-8012407?ONDATE=23.01.2026+00), WebFetch orqali parafraz qilingan — o'rta ishonch, ikkinchi marta so'zma-so'z tekshirilmagan).
- **Rossiya "Chestny Znak" analogiyasi (FAQAT KONTEKST, O'zbekiston uchun tasdiqlanmagan, lekin CRPT Turon aynan shu texnologiya negizida qurilgan)**: (1) **Ko'chirish** — markirovka tizimi faqat **egasi (INN) o'zgarganda** harakatni qayd etadi; "egalik huquqi o'zgarmasdan" (bir yuridik shaxsning o'z omborlari orasida) ko'chirish Chestny Znak'ga umuman xabar qilinmaydi ([markirovka.ru](https://markirovka.ru/knowledge/tovarnye-gruppy/obschie-voprosy-gis/neobkhodimo-fiksirovat-peremeshchenie-markirovannykh-tovarov-mezhdu-magazinami-skladami-v-ramkakh-od)) — bu yuqoridagi lex.uz topilmasi bilan izchil va "ichki ko'chirish — CRPT masalasi emas, faqat logistika/e-TTN masalasi" gipotezasini kuchaytiradi. (2) **Qaytarish** — kod o'qilsa, "возврат оформляется прямо через кассу операцией 'возврат чека', и система ЧЗ автоматически возвращает уникальный код товара назад в оборот" — ya'ni oddiy kassadagi "qaytarish" amali orqali kod **avtomatik** muomalaga qaytariladi, alohida maxsus CRPT operatsiyasi shart emas; kod shikastlangan/o'qilmasa — qaytarish rad etiladi, "Перемаркировка" (qayta markirovka) talab qilinadi ([markznak.ru](https://markznak.ru/blog/vozvrat-markirovannogo-tovara-chestny-znak)); MoySklad'ning o'z (Rossiya) hujjati ham tasdiqlaydi: "никаких специальных действий не требуется" ([moysklad.ru](https://www.moysklad.ru/poleznoe/markirovka-tovarov/kak-oformit-vozvrat-markirovannogo-tovara-na-primere-obuvi/)). (3) MoySklad'ning Rossiya mahsulotida **offline sotuv VA offline qaytarishni** qo'llab-quvvatlovchi mahalliy modul bor, ulanish tiklangunga qadar **72 soat** avtonomiya oynasi bilan, shundan keyin yangi sotuvni bloklaydi ([moysklad.ru — lokal modul](https://www.moysklad.ru/poleznoe/markirovka-tovarov/lokalniy-modul-chestniy-znak-oflayn-proverka-kodov/)) — O'zbekistondagi MoySklad/Asl belgisi joylashtirilishida xuddi shu imkoniyat borligi **tasdiqlanmagan**.

### Variantlar

**A. Offline qaytarish/ko'chirishni taqiqlash** (faqat online, sotuvdan farqli siyosat) — *Pros*: huquqiy xavfni minimallashtiradi (qaytarish rasmiy "qaytarish cheki" hujjati talab qiladi, bu — fiskal/CRPT ahamiyatli hujjat), real-vaqt tekshiruvi imkoni yo'qligi muammosini oldini oladi. *Cons*: internet uzilganda mijoz qaytarishni kuta olmaydi — UX yomonlashuvi, chakana savdoda qaytarish tezkor bo'lishi amaliy ehtiyoj.

**B. Offline qaytarish/ko'chirishga ruxsat, sotuv bilan bir xil naqsh** (status mahalliy ma'lum bo'lsa ruxsat, keyin CRPT'ga sinxronlash, `pending_return_verification`) — *Pros*: mantiqiy izchillik (sotuv siyosati bilan bir xil), yaxshi foydalanuvchi tajribasi. *Cons*: sinxronlashda kod allaqachon boshqa joyda "chiqarilgan" bo'lib chiqsa, nizo holatlari murakkablashadi (sotuvdagi "overselling"ga o'xshash, lekin "over-returning" xavfi yangi va nazoratsiz qaytarish/firibgarlik imkoni kattaroq).

**C. Farqlangan siyosat — ko'chirish offline ruxsat, qaytarish online talab** — ko'chirish hali tovar aylanmasida (mas'uliyat kamroq, 72 soatlik oyna allaqachon bufer beradi), qaytarish esa "status revert" operatsiyasi (noto'g'ri/firibgar ishlatilish xavfi yuqori, buxgalter.uz manbasi rasmiy hujjat talabini alohida ta'kidlaydi).

### Tavsiya

**C variant (kuchaytirilgan)**: ko'chirish (filiallar/omborlar orasida, ichki, egalik o'zgarmaydi) — offline ruxsat, sotuv siyosati bilan bir xil naqsh (mahalliy yozish + keyin sinxronlash, audit bilan); **qo'shimcha asos** — Rossiya analogiyasi va 23-son qarorning o'zi ko'chirish bandini "aylanma subyektlari o'rtasida" (egalik o'tishi) deb cheklagandek ko'rinadi, demak ichki ko'chirish ehtimol CRPT'ga umuman xabar qilinishi shart bo'lmagan, faqat ichki hisobot/e-TTN masalasi bo'lishi mumkin — bu holda "offline ruxsat" qarori huquqiy xavfni kamaytiradi, chunki CRPT operatsiyasi umuman kerak bo'lmaydi. Qaytarish — online talab qilinadi (internet yo'q bo'lsa, qaytarish kechiktiriladi yoki Menejer PIN bilan "vaqtinchalik qabul" + keyinroq rasmiy qaytarish cheki chiqariladi — ikkinchi variant qo'shimcha spec ishi talab qiladi); **nuans** — Rossiya tizimida qaytarish texnik jihatdan kod avtomatik muomalaga qaytarilishi bilan sodda ("hech qanday maxsus amal talab qilinmaydi"), lekin O'zbekiston uchun birlamchi manba (buxgalter.uz) rasmiy "qaytarish cheki" hujjatini aniq talab qiladi — shuning uchun ehtiyotkorlik saqlanadi, offline qaytarish keyinroq (CRPT tasdiqlagandan so'ng) B variantga (sotuv kabi asinxron) kengaytirilishi mumkin.

**Ishonch darajasi: past-o'rta → ko'chirish uchun o'rta, qaytarish uchun past-o'rta.** Ko'chirish bo'yicha xulosa endi ikki mustaqil (lex.uz matni + Rossiya analogiyasi) dalil bilan qo'llab-quvvatlanadi; qaytarish bo'yicha CRPT Turon'ning o'zi buni rasman qanday ajratishi **tasdiqlanmagan** — yuridik maslahat va Xat 2 javobi shart.

### Manbalar

- [buxgalter.uz/oz/publish/doc/text186704](https://buxgalter.uz/oz/publish/doc/text186704_raqamli_markirovkalanadigan_tovarlarni_hisobga_olishga_oid_muhim_savollar) — qaytarish cheki talabi
- [lex.uz/docs/8012407](https://www.lex.uz/docs/8012407) — 23-son qaror (72 soat)
- [lex.uz/uz/docs/-8012407](https://lex.uz/uz/docs/-8012407?ONDATE=23.01.2026+00) — 23-son qaror, 8-bob 30(a)-band matni (aylanma subyektlari o'rtasida)
- [lex.uz/docs/-5205248](https://lex.uz/uz/docs/5205248) — 833-son qaror
- [markirovka.ru](https://markirovka.ru/knowledge/tovarnye-gruppy/obschie-voprosy-gis/neobkhodimo-fiksirovat-peremeshchenie-markirovannykh-tovarov-mezhdu-magazinami-skladami-v-ramkakh-od) — Rossiya analogiyasi: ichki ko'chirish (egalik o'zgarmasa) hisobotga kiritilmaydi
- [markznak.ru/blog/vozvrat-markirovannogo-tovara-chestny-znak](https://markznak.ru/blog/vozvrat-markirovannogo-tovara-chestny-znak), [moysklad.ru — qaytarish](https://www.moysklad.ru/poleznoe/markirovka-tovarov/kak-oformit-vozvrat-markirovannogo-tovara-na-primere-obuvi/) — Rossiya analogiyasi: avtomatik qaytarish/"Перемаркировка"
- [moysklad.ru — lokal modul](https://www.moysklad.ru/poleznoe/markirovka-tovarov/lokalniy-modul-chestniy-znak-oflayn-proverka-kodov/) — Rossiya: offline sotuv+qaytarish moduli, 72 soat oyna
- `spec/kod-uchun/21-integratsiyalar.md` §3, §4 — e-TTN ichki ko'chirish ochiq savoli, MarkingAdapter
- `spec/kod-uchun/16-offline-sync.md` §7, Ochiq savol 2 — offline sotuv qarori (qiyoslash uchun)

---

## Q6. Mustaqil bank terminali orqali karta to'lovi — qo'lda belgilash

### Savol

Kassir mustaqil (integratsiyalanmagan) bank terminalida to'lovni qabul qilgach, kassada "karta" deb qo'lda belgilaydi — bu online va offline'da ham mumkinmi? Fiskal oqibatlari (chekda to'lov turi), bozordagi amaliyot, xavflar?

### Bozorda qanday

| Kompaniya/vosita | Karta to'lovi yondashuvi | Manba/iqtibos |
|---|---|---|
| **HUMO/Uzcard "smart" kassa-terminallar** | Karta to'lovi va fiskal kassa **bitta qurilmada birlashtirilgan** (SmartOne "3in1"/"4in1", UZKASSA N5, A-Pay P10, CASHBOX, SUNMI P2 Pro, NEXGO N82) — to'lov natijasi avtomatik kassaga bog'lanadi | `humocard.uz/uz/business/onlayn-nkm/` |
| **An'anaviy kassa + tashqi pin-pad** | MERKURIY-115F-UZ, ORION-105F-UZ, SIMURG 001 — tashqi Ingenico pin-pad talab qiladi (standalone terminal holati) | `humocard.uz/uz/business/onlayn-nkm/` |
| **Rahmat POS** | "To'lov terminali — 0 so'm/oyiga" — ularning ekotizimida terminal kassaga integratsiya qilingan holda bepul taklif qilinadi | `rhmt.uz/uz/pos/virtual-kassa/` |
| **REGOS** | Payme/Click/Uzum (QR, API orqali) aniq integratsiya qilingan; jismoniy bank karta terminali integratsiyasi haqida dalil topilmadi | **tasdiqlanmagan** |
| **MoySklad** | "Aralash to'lovlar (naqd+karta)ni qo'llab-quvvatlaydi" — texnik jihatdan terminal integratsiyasi aniq ko'rsatilmagan, ko'rinishidan qo'lda belgilashga yaqin | `moysklad.uz` |
| **E-POS** | "Cash, card, or QR" to'lov variantlari ro'yxatlangan — "karta" yo'lining texnik mohiyati (standalone yoki integratsiyalangan) aniqlanmagan | `epos.uz/en` |

### Qonun/manba

- VMQ-943 texnik talablari chekda **to'lov turini ko'rsatishni** talab qiladi (bu maydon bizning `fiscal_receipts.payload`da allaqachon bor; umumlashtirilgan ikkinchi darajali manbalar — moysklad.uz, buxgalter.uz — "naqd/karta/aralash" uchta variantni tasdiqlaydi). Biroq bu ma'lumotning **manbasi** (avtomatik terminal signali yoki kassir qo'lda tanlagan tugma) qonun matnida aniq farqlanganligi **tasdiqlanmagan** — bu band veb-qidiruv byudjeti tugagani sababli to'liq tekshirilmadi, qo'shimcha huquqiy tekshiruv tavsiya etiladi.
- **Standalone terminal — bozor amaliyoti sifatida to'g'ridan-to'g'ri tasdiqlandi**: "Terminal kvitansiyasi kassa chekiga teng bo'lmaydi" va xaridorlarga "ikkalasini ham berish kerak" — ya'ni bank terminali va fiskal kassa rasman **ikki alohida tizim** sifatida qaraladi, terminal cheki fiskal hujjat o'rnini bosmaydi ([uzum.uz/media/uz/ekvayring-nima](https://uzum.uz/media/uz/ekvayring-nima/)). Bu bizning arxitektura taxminimizni (standalone terminal + qo'lda belgilash — normal amaliyot) kuchli tasdiqlaydi.
- **Bank terminali narxi/ijarasi**: banklar standart ijara shartnomasi asosida terminalni do'konga beradi ([ofb.uz — POS terminal ijarasi shartlari (PDF)](https://ofb.uz/upload/iblock/931/mvtoja0guifbj83zr01y2olre2rudt41/POS-%20TERMINALNI%20IJARASI%20UMUMIY%20ShARTLARIGA.pdf)); Humo o'z terminal liniyasini to'g'ridan-to'g'ri sotadi ([humocard.uz/uz/business/terminals](https://humocard.uz/uz/business/terminals/)); qidiruv natijalariga ko'ra odatiy tarif — oyiga ~49 000 so'm ijara + Uzcard/Humo komissiyasi ~0,2% aylanmadan (**tasdiqlanmagan**, aniq bank/kampaniya ko'rsatilmagan).
- **Rossiya 54-FZ analogiyasi (FAQAT KONTEKST)**: "эквайринг и касса — это два параллельных процесса, которые должны работать вместе", terminal kvitansiyasi "не заменяет фискальный документ" — har bir karta sotuvi integratsiya darajasidan qat'i nazar fiskal chek talab qiladi ([astral.ru](https://astral.ru/aj/elem/ekvayring-bez-chekov-chto-razresheno-a-chto-grozit-shtrafami/)). Nomuvofiqlik **bank va fiskal operator ma'lumotlarini solishtirish** ("сверка данных банка и ОФД"), mijoz shikoyati yoki yashirin tekshiruv orqali aniqlanadi; hisobga olinmagan/mos kelmagan daromad uchun jarima — jismoniy shaxs/YaTT uchun 25–50%, yuridik shaxs uchun 75–100% (qayta buzilishda 90 kungacha faoliyat to'xtatilishi mumkin) — **bu Rossiya raqamlari, O'zbekiston uchun aniq jarima miqdori topilmadi**, lekin tuzilishi (bank↔OFD solishtirish orqali nomuvofiqlikni aniqlash) bir xil me'yoriy oilaga (OFD-asosidagi fiskal nazorat) tegishli bo'lgani uchun oqilona qiyoslash hisoblanadi. Rossiya amaliyotida tavsiya etilgan nazorat chorasi — terminal integratsiyasi emas, balki kassada **alohida "karta" tugmasi** + kun oxirida terminal partiya summasi va POS "karta" summasini **solishtirish** ([moysklad.ru](https://www.moysklad.ru/poleznoe/izmenenija-v-54-fz/novye-rekvizity-v-kassovih-chekah/)) — bu quyidagi tavsiyada allaqachon aks etgan yondashuv bilan mos.
- PCI-DSS bizga bevosita tegishli emas — karta ma'lumoti (PAN/CVV) hech qachon bizning tizimga kirmaydi, bank terminali mustaqil ishlaydi (bu bizning spec'da `15-xavfsizlik-va-audit.md` §9.3'da allaqachon qayd etilgan).

### Variantlar

**A. Standalone terminal + kassirning qo'lda "karta" tugmasini bosishi** (hozirgi amaliy taxmin, online va offline'da ham) — *Pros*: eng arzon va tez implementatsiya (qo'shimcha integratsiya shart emas), bank terminali odatda mustaqil/GSM orqali ishlaydi va internet yo'qligida ham to'lovni qabul qila oladi — demak MIJOZ uchun to'lov offline'da ham fizik jihatdan mumkin, faqat bizning tizimga "karta" deb yozish kerak; bozorda keng tarqalgan (an'anaviy kassa + tashqi pin-pad modeli hamon mavjud). *Cons*: firibgar xavfi (kassir "karta" deb belgilab pulni cho'ntakka solishi, yoki aksincha), soliq tekshiruvida bizning "karta" summamiz bilan bank hisobotidagi haqiqiy tranzaksiyalar orasida avtomatik moslashtirish yo'q — faqat davr oxirida qo'lda solishtiriladi.

**B. Integratsiyalangan "smart" terminal** (SmartOne/UZKASSA kabi, karta+kassa bitta qurilmada) — *Pros*: avtomatik, firibgar xavfi kam, bozorda aniq namuna bor (`humocard.uz` ro'yxati). *Cons*: qo'shimcha uskuna xarajati, bizning "veb-kassa — istalgan qurilmada" arxitekturamizga mos kelmasligi mumkin (bu qurilmalar o'z ichida alohida OS/dastur bilan ishlaydi, bizning veb-kassa ularning ustida to'g'ridan-to'g'ri ishlamaydi — faqat ular taklif qiladigan API orqali bog'lanish mumkin, bu alohida integratsiya loyihasi).

### Tavsiya

MVP uchun **A variantni davom ettirish** (standalone terminal + qo'lda belgilash, online va offline'da ham) — bozorda keng tarqalgan amaliyot va bizning arxitekturaga mos. Ikkita ehtiyot chorasi qo'shilishi tavsiya etiladi: (1) kassir "karta" tugmasini bosganda ixtiyoriy "terminal operatsiya raqami/izoh" maydoni (audit uchun, majburiy emas); (2) smena yopilishida (Z-hisobot) "karta" summasi jamini aniq ko'rsatish va Egasiga kun oxirida bank SMS/hisob ko'chirmasi bilan solishtirishni tavsiya qiluvchi eslatma (M18 orqali). Integratsiyalangan smart-terminal (B) — keyingi bosqich, MVP uchun shart emas.

**Ishonch darajasi: o'rta-yuqori.** Amaliy xulosa bozor namunalariga (humocard.uz, Rahmat POS) va endi to'g'ridan-to'g'ri bozor-amaliyoti tasdig'iga (uzum.uz: terminal va fiskal chek ikki alohida hujjat) asoslanadi; Rossiya 54-FZ analogiyasi xavf tuzilishini (bank↔OFD solishtirish, jarima tuzilishi) mustahkam qo'llab-quvvatlaydi. Ammo O'zbekiston qonun matnida to'lov turi "manbasi"ga (avtomatik/qo'lda) qo'yiladigan aniq talab va O'zbekistonga xos jarima miqdori **hamon tasdiqlanmagan** — yurist tasdig'i tavsiya etiladi (bu band bizning ichki kuzatuvda allaqachon #37 sifatida OCHIQ belgilangan).

### Manbalar

- [humocard.uz/uz/business/onlayn-nkm/](https://humocard.uz/uz/business/onlayn-nkm/) — smart kassa-terminal modellari, integratsiya darajasi
- [rhmt.uz/uz/pos/virtual-kassa/](https://rhmt.uz/uz/pos/virtual-kassa/) — to'lov terminali narxi
- [moysklad.uz](https://www.moysklad.uz/), [epos.uz/en](http://epos.uz/en) — aralash to'lov/karta yo'li tasvirlari
- [uzum.uz/media/uz/ekvayring-nima](https://uzum.uz/media/uz/ekvayring-nima/) — terminal kvitansiyasi ≠ fiskal chek, ikkalasini berish talabi
- [ofb.uz — POS terminal ijarasi (PDF)](https://ofb.uz/upload/iblock/931/mvtoja0guifbj83zr01y2olre2rudt41/POS-%20TERMINALNI%20IJARASI%20UMUMIY%20ShARTLARIGA.pdf), [humocard.uz/uz/business/terminals](https://humocard.uz/uz/business/terminals/) — terminal narxi/ijarasi
- [astral.ru — эквайринг без чеков](https://astral.ru/aj/elem/ekvayring-bez-chekov-chto-razresheno-a-chto-grozit-shtrafami/), [moysklad.ru — 54-FZ rekvizitlar](https://www.moysklad.ru/poleznoe/izmenenija-v-54-fz/novye-rekvizity-v-kassovih-chekah/) — Rossiya analogiyasi: ikki parallel jarayon, solishtirish, jarima tuzilishi
- `spec/kod-uchun/15-xavfsizlik-va-audit.md` §9.3 — PCI-DSS qamrovi (karta ma'lumoti saqlanmaydi)
- `spec/kod-uchun/06-ekranlar-umumiy.md` OS 11, `spec/kod-uchun/28-android-pos.md` §4.5 — ichki ochiq savol #37

---

## Yakuniy tavsiyalar (1–2 qator/savol)

- **Q2** — Pilotni reyestr hamkori (Rahmat POS/Multikassa yoki E-POS Communicator, oylik ~100–125k so'm/do'kon) orqali boshlash, mustaqil Davlat reyestri arizasini parallel yuritish; uskuna — smartfon/PC + arzon skaner + ESC/POS printer (~900k so'm/kassa), Android terminal shart emas.
- **Q3** — Rasmiy "integrator" bo'lishni kutmasdan, har bir do'kon o'z bepul "ishtirokchi" hisobidan API kalit olib bizning tizimga ulashi (B) bilan boshlash, Xat 2'ni zudlik bilan yuborib rasmiylashtirish; muvaffaqiyatsiz bo'lsa mavjud integrator (E-POS/Rahmat POS) orqali proksi (C) zaxira.
- **Q5** — Ichki filiallar/omborlar orasida ko'chirishga offline ruxsat (sotuv bilan bir xil naqsh), lekin qaytarishni online talab qilish — chunki qaytarish rasmiy "qaytarish cheki" hujjati va yuqori firibgarlik xavfi bilan bog'liq.
- **Q6** — Standalone bank terminali + kassirning qo'lda "karta" belgilashini MVP'da davom ettirish (online/offline farqsiz), faqat ixtiyoriy audit maydoni va kun oxiri solishtirish eslatmasi qo'shish; integratsiyalangan smart-terminal — keyingi bosqich.
