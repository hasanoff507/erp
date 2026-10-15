# Tadqiqot 2 — Buxgalteriya va biznes qoidalari (Q4, Q7, Q9, Q15)

*2026-10-15 · Manba vazifasi: `kamchiliklar-yakuniy.md` §3 (foydalanuvchi qarori kerak, bandlar #7, #9, #16, #26), `spec/01-mahsulot/02-modullar-talablari.md` (M07, M08, M09, M11), `spec/02-arxitektura/02-provodka-qoidalari.md`, `03-integratsiyalar.md` (§2, e-faktura), `research_notes/texnik/03-efaktura-va-tolov.md`. To'rt savol (Q4, Q7, Q9, Q15) tashqi manbalar (WebSearch/WebFetch) bilan tekshirildi: O'zbek raqobatchilar (REGOS, BILLZ, MoySklad UZ, Smartup, Bito, mDokon, HIPPO), xalqaro amaliyot (Square, Lightspeed, Odoo, QuickBooks, Zoho, Loyverse, Xero), lex.uz/nrm.uz huquqiy manbalar. Mahsulot noldan yoziladi — tashqi buxgalteriya/ERP tizimlari bilan hech qanday integratsiya yo'q.*

*Eslatma: ushbu sessiyada WebSearch byudjeti (200 so'rov) tugaganidan keyin bir qator savollar faqat to'g'ridan-to'g'ri WebFetch va ilgari to'plangan tadqiqot (`research_notes/texnik/03-efaktura-va-tolov.md`) asosida javoblandi. Qayerda yangi, mustaqil manba topilmagan bo'lsa, keng tanilgan (lekin bu sessiyada qayta tekshirilmagan) xalqaro amaliyot sifatida **"tasdiqlanmagan"** deb alohida belgilangan.*

---

## Q4. E-faktura operatori — MVP tanlovi

### Savol

MVP uchun qaysi e-faktura (EDO) operatori bilan integratsiya qilinadi: **Faktura.uz** (ochiq, mustaqil o'qilgan API hujjati — `api.faktura.uz/help/`) vs **Didox** (login talab qiladigan hujjat portali) vs davlatning o'z **my.soliq.uz** tizimi / boshqa akkreditatsiyalangan operatorlar (jumladan "Hippo" — tasdiqlanishi kerak)? Kichik bizneslar orasida qaysi operator ustun, narx/API shartlari qanday, qaysi raqobatchi qaysi operatorni ishlatadi?

### Bozorda qanday

| Operator | API ochiqligi (dasturchi uchun) | Narx (kichik hajm, oyiga) | Sandbox | Tarmoq hajmi / mashhurligi | Manba |
|---|---|---|---|---|---|
| **Faktura.uz** | Rasmiy, **ochiq, mustaqil o'qilgan** (`api.faktura.uz/help/`): token auth, `Document/SendDocument`, `SignDocument`, `GetDocumentStatus`, `CheckCompanyExist/:inn` | ~50 000 so'm/oy (10 kiruvchi+10 chiquvchi hujjatgacha) | Ochiq sahifada topilmadi | "Birinchi rasmiy EDO operatori" (o'z sayti shunday ataydi) | [faktura.uz](https://faktura.uz/); [api.faktura.uz/help/](https://api.faktura.uz/help/); buxgalter.uz taqqoslash jadvali |
| **Didox** | Login-gated (`api-docs.didox.uz`), faqat **norasmiy** npm SDK (`didox`, muallif Mirzaev) | 10 hujjat/oy bepul, so'ng tarifga qarab 350–800 so'm/hujjat (ba'zi manbalarda 1000 hujjatgacha bepul) | Alohida sandbox topilmadi | **Eng katta**: 250 000+ tashkilot, kunlik o'rtacha 62 000, oylik ~220 000 foydalanuvchi, 4 mln+ hujjat/oy | [the-tech.kz](https://the-tech.kz/kak-startap-iz-uzbekistana-didox-izmenil-rynok-dokumentooborota/); [buxgalter.uz — taqqoslash jadvali](https://buxgalter.uz/publish/doc/text171838_kak_opredelitsya_s_operatorom_esf_sravnitelnaya_tablica) |
| **Soliq-servis** (soliqservis.uz) | Davlat unitar korxonasi (Soliq qo'mitasi qoshida), API hujjati ochiq manbada **topilmadi** | 10 hujjat/oy bepul, 300–500 so'm/hujjat | Noma'lum | Birinchilardan bo'lib ishga tushgan davlat xizmati | [uzdaily.uz](https://www.uzdaily.uz/ru/operator-esf-soliqservisuz-prodlil-besplatnyi-servis/); [api.soliq-servis.uz](https://api.soliq-servis.uz/ru/news/new-soliqservis-uz-avtomatlashtirilgan-elektron-hujjat-aylanishi-tizimi-statistikasi/) |
| **Hippo EDO** (hippo.uz) | Ochiq manbada API hujjati **topilmadi** ("Hippo Matching", "Mass Signature" funksiyalari tasvirlangan, texnik API emas) | ~412 so'm/hujjat (EDO-Base tarif) | Noma'lum | 2022-yildan rasmiy operator rolida | [hippo.uz/ru/edo/](https://hippo.uz/ru/edo/) |
| **E-invoice.uz** | Topilmadi | Bepul yo'q, 345–506 so'm/hujjat, 13 hujjat turi | Noma'lum | 3 000+ buxgalter oylik foydalanuvchi (o'z da'vosi) | [e-invoice.uz](https://e-invoice.uz/) |
| **E-Docs.uz** | Topilmadi | 10 hujjat/oy bepul, 190–750 so'm/hujjat | Noma'lum | — | [edocs.uz](https://edocs.uz/) |

**Muhim topilma**: "Hippo" haqiqatan mavjud EDO operatori ekanligi **tasdiqlandi** (savolda taxmin qilingan edi) — hippo.uz/ru/edo/ 2022-yildan rasmiy ishlaydi, lekin texnik API hujjati bu tadqiqotda topilmadi.

**Raqobatchilarning qaysi operatorni ishlatishi**: **REGOS**'da Faktura.uz bilan tayyor, rasmiy hujjatlashtirilgan integratsiya moduli topildi (`apps.regos.uz/integration/details/edo_fakturauz`) — kiruvchi faktura qabul qilinganda avtomatik qabul hujjati yaratiladi, chiquvchi faktura to'g'ridan-to'g'ri REGOS ichidan yuboriladi. Bu Faktura.uz'ning kichik-biznes POS/ERP tizimlarida amaliy ishlatilayotganining aniq, tekshirilgan dalili. BILLZ, Smartup, mDokon saytlarida esa biror aniq operator bilan integratsiya reklama qilingani **topilmadi** (**tasdiqlanmagan**). Didox'ning o'z sayti "buxgalteriya/billing tizimi bilan integratsiya — ERP'dan chiqmay imzolash" imkoniyatini umumiy tarzda reklama qiladi, lekin aniq hamkor nomlarini ko'rsatmaydi.

### Qonun/standart

- E-faktura 2020-01-01'dan majburiy: VM Qarori №522 (2019-06-25, [lex.uz/docs/-4386769](https://lex.uz/docs/-4386769)); Soliq kodeksi fakturalarning elektron axborot tizimida tuzilishi shart ekanligini belgilaydi ([lex.uz/acts/-4674902](https://lex.uz/acts/-4674902)).
- Operatorlar Soliq qo'mitasi reestrida **akkreditatsiyadan o'tgan** bo'lishi kerak — reestrda 2026 boshida ~27 pozitsiya bor (ikkinchi darajali manba, rasmiy reestr sahifasining o'zi bu tadqiqotda ko'rilmadi — **tasdiqlanmagan** aniq son). Manba: [tusoft.ru](https://tusoft.ru/blog/edo/operatory-edo/).
- **Roaming**: barcha akkreditatsiyalangan operatorlar bir-biri bilan hujjat almashishi (roaming.uz orqali) mumkin — demak kontragent boshqa operatorda bo'lsa ham, bizning operatorimiz orqali yuborilgan faktura unga yetib boradi. Bu operator tanlovining B2B izolyatsiya xavfini kamaytiradi (**ikkinchi darajali manba, mexanizmning texnik tafsiloti bu tadqiqotda chuqur tekshirilmadi**).
- AI xavf-baholash (VM Qarori №830, 2025-12-26) — operator tanlovidan qat'i nazar barcha fakturalarga qo'llanadi (allaqachon `03-integratsiyalar.md`da hisobga olingan).

### Variantlar

**(a) Faqat Faktura.uz bilan boshlash (joriy MVP-zaxira qarori)**
+ Yagona mustaqil o'qilgan, ochiq, rasmiy API hujjati — texnik integratsiya xavfi eng past.
+ Token-based autentifikatsiya sodda; norasmiy MCP wrapper (theYahia/factura-uz-mcp) ham prototiplash uchun mavjud; REGOS'dagi tayyor integratsiya moduli (apps.regos.uz) amaliy ishlayotganini ko'rsatadi — bu yo'l amalda sinalgan.
− Didox'ga nisbatan tarmoq ancha kichikroq — agar ko'p mijozimizning B2B kontragentlari Didox foydalanuvchisi bo'lsa, lekin roaming mavjud bo'lgani uchun bu amalda muammo bo'lmasligi mumkin.
− Narxi (~50 000 so'm/oy past hajmda) past hajmli kichik do'kon uchun hujjat boshiga qimmat bo'lib ko'rinishi mumkin (aniq narx/sandbox tasdiqlanmagan).

**(b) Didox bilan boshlash**
+ Eng katta tarmoq (250 000+ tashkilot) — statistik ehtimol bo'yicha ko'proq kontragent allaqachon shu tizimda.
+ Kam hajmda narx arzonroq (10 hujjat bepul, keyin 350–800 so'm).
− Mustaqil tekshirilgan, ochiq API hujjati yo'q (login-gated portal) — faqat norasmiy npm SDK; bu MVP jadvaliga to'g'ridan-to'g'ri texnik xavf.

**(c) Ikkalasini parallel qurish (adapter qatlami ortida, allaqachon arxitektura qarori)**
+ Tanlov erkinligi, kontragentga mos operator.
− Ikki marta integratsiya ishi; Didox tomoni hujjatsiz bo'lgani uchun MVP muddatini kechiktirish xavfi yuqori.

**(d) Davlat operatori (Soliq-servis) bilan boshlash**
+ Davlat tomonidan boshqariladi, eng arzon (300–500 so'm/hujjat).
− API hujjati butunlay topilmagan — texnik integratsiya yo'li noma'lum, amalda faqat veb-portal bo'lishi mumkin.

### Tavsiya

**Variant (a)ni davom ettirish — faqat Faktura.uz bilan MVP, Didox'ni fast-follow sifatida (ikkinchi bosqich, tijorat shartnoma/API kirish qo'lga olingandan keyin) qo'shish.** Sabab: Faktura.uz — ushbu tadqiqotda ham, oldingi tadqiqotda ham yagona mustaqil tekshirilgan ochiq API hujjatiga ega operator; roaming mexanizmi (agar tasdiqlansa) Didox tarmog'idagi kontragentlar bilan muloqotni ham ta'minlaydi, chunki ular bizning Faktura.uz orqali yuborilgan hujjatimizni roaming orqali qabul qiladi. Didox'ning katta tarmog'i jiddiy afzallik, shuning uchun uni to'liq rad etmaslik, balki MVP'dan keyingi birinchi navbatdagi integratsiya qilish tavsiya etiladi — bu allaqachon qabul qilingan zaxira qarorga mos keladi.

**Ishonch: o'rta-yuqori.** API hujjat assimetriyasi (Faktura.uz ochiq, Didox yopiq) ikki mustaqil tadqiqotda ham tasdiqlangan — yuqori ishonch. Narx raqamlari (ayniqsa Didox'niki — manbalar 350–800 so'm, boshqa joyda 1000 hujjatgacha bepul deb nomuvofiq) va roaming mexanizmining texnik tafsilotlari — **tasdiqlanmagan**, rasmiy manba/vendor bilan tasdiqlash tavsiya etiladi (K7/vendor murojaati doirasida).

### Manbalar

- [api.faktura.uz/help/](https://api.faktura.uz/help/), [faktura.uz](https://faktura.uz/)
- [buxgalter.uz — Как выбрать оператора ЭДО 2026](https://buxgalter.uz/publish/doc/text171838_kak_opredelitsya_s_operatorom_esf_sravnitelnaya_tablica)
- [the-tech.kz — Didox tarmog'i statistikasi](https://the-tech.kz/kak-startap-iz-uzbekistana-didox-izmenil-rynok-dokumentooborota/)
- [hippo.uz/ru/edo/](https://hippo.uz/ru/edo/)
- [uzdaily.uz — Soliq-servis](https://www.uzdaily.uz/ru/operator-esf-soliqservisuz-prodlil-besplatnyi-servis/), [api.soliq-servis.uz](https://api.soliq-servis.uz/ru/news/new-soliqservis-uz-avtomatlashtirilgan-elektron-hujjat-aylanishi-tizimi-statistikasi/)
- [e-invoice.uz](https://e-invoice.uz/), [edocs.uz](https://edocs.uz/)
- [tusoft.ru — Операторы ЭДО 2026](https://tusoft.ru/blog/edo/operatory-edo/)
- [apps.regos.uz/integration/details/edo_fakturauz](https://apps.regos.uz/integration/details/edo_fakturauz?lang=en) — REGOS'ning Faktura.uz bilan tayyor integratsiya moduli
- `research_notes/texnik/03-efaktura-va-tolov.md` §1.3–1.4 (ilgari to'plangan — Didox/Faktura.uz API holati)

---

## Q7. Optom narx turlari va chegirmalar stacking

*(Ushbu bo'lim fon-agent (fork) tomonidan parallel tadqiq qilindi; fork hali yakunlanmagan taqdirda quyida koordinator tomonidan to'g'ridan-to'g'ri yig'ilgan dastlabki natija keltiriladi.)*

### Savol

Mijoz turi (chakana/optom/VIP) bo'yicha narx turlari qanday modellanadi, va bitta chekda bir nechta chegirma qo'llanilsa — ular birlashadi (stacking) yoki faqat eng yaxshi/eng ustuvor bittasi qo'llaniladi? Raqobatchilar va xalqaro amaliyot qanday qiladi; kichik O'zbek do'kon/ulgurjichilarga nima kerak?

### Bozorda qanday

| Tizim | Optom/mijoz-toifa narx modeli | Chegirma stacking qoidasi | Manba |
|---|---|---|---|
| **Odoo** | **Pricelist** — mijoz/mijoz guruhiga bog'lanadi (kontakt kartasida "Pricelist" maydoni); har qoida 3 turda: foiz chegirma, formula (chegirma+yaxlitlash+ustama), qat'iy narx | Bitta mahsulotga **eng mos keladigan BITTA qoida** tanlanadi (minimal miqdor, muddat, mahsulot toifasi bo'yicha eng spetsifik mos keluvchi) — rasmiy hujjatda bir nechta qoidaning birlashishi (stacking) haqida ma'lumot yo'q, demak amalda "eng mos — bitta g'olib" | [odoo.com/documentation — Pricelists](https://www.odoo.com/documentation/18.0/applications/sales/sales/products_prices/prices/pricing.html) |
| **BILLZ** | Sahifada aniq "optom narx/mijoz toifasi" tasvirlangan funksiya **topilmadi** (faqat umumiy "Mijoz boshqarish" bo'limi) | Topilmadi | billz.io |
| **REGOS, Smartup** | Ochiq saytlarda narx turi/stacking tafsiloti **topilmadi** (faqat umumiy "CRM va chegirmalar" eslatmasi) | Topilmadi | regos.uz, smartup.online |
| **Square** | Customer-specific/guruh narxi — cheklangan (asosan "Discounts" + mijoz guruhiga bog'langan avtomatik chegirma qoidalari); alohida "wholesale price tier" tushunchasi yo'q | Odatda bir nechta chegirma qo'llanilganda eng yaxshi/birinchi mos qoida qo'llaniladi (sozlamaga qarab combine/exclusive belgilash) — **tasdiqlanmagan**, bu sessiyada yangi manba bilan qayta tekshirilmadi | umumiy ma'lum amaliyot |
| **Lightspeed Retail** | "Price books"/"customer groups" — mijoz guruhiga bog'langan maxsus narx kitoblari (tier pricing) | **Tasdiqlanmagan** (manba topilmadi) | umumiy ma'lum amaliyot |
| **Zoho Inventory/Books** | "Price lists" — mijozga yoki mijoz guruhiga alohida narx ro'yxati tayinlanadi | **Tasdiqlanmagan** | umumiy ma'lum amaliyot |
| **QuickBooks** | "Price rules" (faqat Plus/Advanced tarifda) — mijoz, mahsulot guruhi, miqdorga qarab narx/chegirma qoidasi | **Tasdiqlanmagan** | umumiy ma'lum amaliyot |
| **Loyverse** | Sodda POS — "Customer groups" bilan cheklangan chegirma, alohida ko'p bosqichli optom narx darajasi **odatda yo'q** (kichik do'kon uchun mo'ljallangan sodda model) | — | umumiy ma'lum amaliyot |

### Qonun/standart

To'g'ridan-to'g'ri tegishli huquqiy norma yo'q (narxlash — tijorat erkinligi masalasi). Faqat bitta bog'liq qoida: `02-provodka-qoidalari.md` Asosiy xulosa 3/M03 bo'yicha — **QQS bazasi chegirmadan keyingi (yakuniy) summadan hisoblanadi**, demak qanday stacking qoidasi tanlansa ham, yakuniy chek summasi (barcha chegirmalardan keyin) QQS hisob-kitobiga asos bo'ladi — bu stacking tartibini buxgalteriya natijasiga ta'sir qilmaydigan qiladi (faqat UX/biznes qoidasi).

### Variantlar

**(a) Narx turi — mijoz toifasiga bog'langan alohida narx jadvali** (`product_prices`ga `price_type: retail|wholesale` yoki mijoz profiliga `customer_type` + alohida narx qatori)
+ Odoo pricelist uslubiga mos, ulgurji savdo qiluvchi do'konlar uchun to'g'ri yechim (narx har safar qo'lda kiritilmaydi).
− Ma'lumotlar modeliga yangi struktura kerak (`kamchiliklar-yakuniy.md` #7 — hozir yo'q); MVP murakkabligini oshiradi.

**(b) Foiz chegirma — mijoz profilida ("doimiy mijoz chegirmasi")**
+ Oddiy: `counterparties.default_discount_pct` kabi bitta maydon, mavjud chegirma mexanizmi (M03) orqali avtomatik qo'llanadi.
+ Hech qanday yangi narx jadvali kerak emas — tezroq amalga oshiriladi.
− Optom narxni aniq, "qattiq" narx sifatida emas, balki chakana narxdan chegirma sifatida modellanadi — ba'zi buxgalteriya/hisobot holatlarida (masalan "optom narx ro'yxati" chop etish) noqulay.

**(c) MVP'da hech narsa qilmaslik — faqat kassir qo'lda chegirma beradi (joriy holat)**
+ Hech qanday qo'shimcha ish yo'q, tezkor MVP.
− Tez-tez optom sotadigan kichik ulgurjichilar uchun har safar qo'lda chegirma kiritish amaliy emas (xato xavfi, tezlik yo'qotish).

**Stacking bo'yicha qo'shimcha variant**: **(d) bitta eng ustuvor qoida g'olib chiqadi** (Odoo modeliga mos, kamchiliklar-yakuniy #7da taklif qilingan) vs **(e) hamma mos qoidalar yig'iladi (stacking)** — (e) narxni manfiyga yoki mantiqsiz pastga tushirish xavfini oshiradi (M03 chekka holatida allaqachon qayd etilgan "chegirma tovar narxini manfiy qilib yubormasligi tekshirilishi kerak").

### Tavsiya

MVP uchun **(b) + (d)**: mijoz profiliga **ixtiyoriy doimiy foiz chegirma** maydoni qo'shish (optom mijozlar uchun kifoya, yangi narx jadvali kerak emas) va bir chekda bir nechta chegirma manbai (mijoz chegirmasi, promo-qoida, kassir qo'lda chegirmasi) to'qnashsa — **faqat eng yuqori ustuvorlikdagi/eng katta foyda beradigan BITTA qoida qo'llanilsin** (Odoo'ning "eng mos qoida g'olib" mantiqiga mos, stacking emas). To'liq narx-jadvali asosidagi optom narx turlari (variant a) — keyingi bosqichga qoldirilsin, chunki hech bir tekshirilgan O'zbek raqobatchida bu funksiya ochiq tasdiqlanmadi.

**Ishonch: o'rta.** Odoo'ning "bitta eng mos qoida" mantiqi birlamchi manba bilan tasdiqlangan (yuqori ishonch); O'zbek raqobatchilarning aniq yechimi (BILLZ/REGOS/Smartup) ochiq manbalarda topilmadi — **tasdiqlanmagan**, pilot mijozlardan to'g'ridan-to'g'ri so'rash tavsiya etiladi.

### Manbalar

- [odoo.com/documentation — Pricelists](https://www.odoo.com/documentation/18.0/applications/sales/sales/products_prices/prices/pricing.html)
- billz.io, regos.uz, smartup.online (sayt matni — funksiya tafsiloti topilmadi)
- `spec/02-arxitektura/02-provodka-qoidalari.md` Asosiy xulosa 3 (QQS bazasi — chegirmadan keyingi summa)
- `spec/01-mahsulot/02-modullar-talablari.md` M03, M09 (chekka holatlar)

---

## Q9. Nasiya: to'lash grafigi va shubhali qarz tasnifi

### Savol

Nasiya (mijoz qarzi) uchun bo'lib-bo'lib to'lash jadvali (installment schedule) kerakmi, yoki bitta va'da sanasi yetarlimi? "Shubhali qarz" (doubtful debt) qanday belgilanadi — Egasi qo'lda, yoki N kundan keyin avtomatik? Buxgalteriya asosi (NSBU/BHMS — shubhali qarzlar zahirasi standarti) qanday, kichik bizneslar zahira yaratishi shartmi? O'zbekistondagi nasiya ilovalari (BILLZ, mDokon va boshqalar) buni qanday hal qiladi?

### Bozorda qanday

| Tizim | Installment (bo'lib-bo'lib to'lash) grafigi | Shubhali qarz belgilash | Manba |
|---|---|---|---|
| **BILLZ** | Topilmadi — faqat **"qaytarish muddatini belgilash"** (bitta sana) tasvirlangan ("Mijoz qarzasini boshqarish" bo'limi) | Tafsilot topilmadi | billz.io |
| **mDokon** | Topilmadi — "Mijozlar balansi va qarzlari" (Business tarif, 299 000 so'm/oy), batafsil tavsif yo'q | Tafsilot topilmadi | mdokon.uz |
| **QuickBooks/Xero/Zoho (xalqaro amaliyot)** | Yo'q — "customer credit/tab" oddiy balans, muddat emas | **Har doim qo'lda** jurnal yozuvi (Dt Bad debt expense / Kt Accounts Receivable yoki Allowance for doubtful accounts); avtomatik N-kun qoidasi yo'q, faqat aging hisobot (0–30/31–60/60+) ko'rsatiladi, qaror inson tomonidan | **Tasdiqlanmagan** — bu sessiyada yangi manba bilan qayta tekshirilmadi, lekin keng tanilgan standart amaliyot |
| **Square/Lightspeed** | "Store credit"/"customer accounts" — odatda bitta ochiq balans, bosqichli jadval yo'q | — | **Tasdiqlanmagan** |
| **pDaftar (UZ, qarz daftari ilovasi)** | Nomida va tasvirida **"nasiya savdo" + "muddatli (installment) savdo"** alohida reklama qilinadi — kichik O'zbek raqobatchilar orasida installment'ni asosiy funksiya sifatida ko'rsatadigan yagona topilgan misol | Tafsilot topilmadi | [pdaftar.uz](https://pdaftar.uz/en?from=AppAgg.com) |
| **Odoo** | Invoys darajasida bitta to'lov muddati; alohida "installment plan" standart emas, lekin **avtomatik follow-up (eslatma) darajalari** kun soniga sozlanadi (masalan +7/+15/+30) | Eslatma darajalari avtomatik, lekin haqiqiy "bad debt" buxgalteriya yozuvi har doim qo'lda (reconciliation paytida) | [odoo.com/documentation — followup](https://www.odoo.com/documentation/18.0/applications/finance/accounting/payments/followup.html) |

**Xulosa**: tekshirilgan hech bir mashhur manbada (BILLZ, mDokon, QuickBooks/Xero/Zoho) kichik do'kon darajasida to'liq **installment-schedule** (bosqichma-bosqich summa+sana jadvali) funksiyasi topilmadi — faqat **pDaftar** (qarz daftari turidagi mahalliy ilova) buni asosiy reklama funksiyasi sifatida ko'rsatadi; qolgan tizimlar (a) bitta muddat/sana, yoki (b) umuman muddatsiz ochiq balans bilan ishlaydi; Odoo esa "avtomatik eslatma darajalari" bilan oraliq yechim beradi (jadval emas, faqat eskalatsiyalanadigan ogohlantirish).

### Qonun/standart

- **NSBU №21 (191-son buyruq) hisob rejasida `4910` — "Резерв по сомнительным долгам" (Shubhali qarzlar zahirasi) hisobi mavjud** (ikkinchi darajali manba orqali tasdiqlangan — [buxgalter.uz/publish/doc/text150192](https://buxgalter.uz/publish/doc/text150192_schet_4910_rezerv_po_somnitelnym_dolgam)). Topilgan tavsif: *"Резерв по сомнительным долгам создается на основе результатов проведенной в конце отчетного года инвентаризации дебиторской задолженности предприятия. Величина резерва определяется отдельно по каждому сомнительному долгу в зависимости от финансового состояния (платежеспособности) должника и оценки вероятности погашения долга."* — demak rasmiy model **individual baholash** (har bir qarz alohida, yil oxiri inventarizatsiyasi asosida), **avtomatik N-kun qoidasi EMAS**.
- **Kichik biznes uchun zahira yaratish majburiyligi** — bu tadqiqotda aniq topilmadi (191-son buyruqning to'liq ilova matni o'qilmagan, `02-provodka-qoidalari.md`dagi ogohlantirish 5-bandida ham shu muammo qayd etilgan). **Tasdiqlanmagan.**
- **NSFO №2** ("Asoslar: uchet siyosati va baholash", IAS 1 + IAS 8 asosida, 3810-son buyruq, [lex.uz/ru/docs/8130720](https://lex.uz/ru/docs/8130720)) — bu standart buxgalteriya **baholash o'zgarishlari va xatolar**ni tartibga soladi, lekin faqat **2027-01-01**'dan kuchga kiradi; hozircha (2026) shubhali qarz bo'yicha alohida IAS 8-uslubidagi me'yor yo'q, faqat yuqoridagi 4910-hisob amaliyoti bor.

### Variantlar

**(a) Faqat bitta va'da sanasi (joriy spec holati, M08)**
+ Soddalik; BILLZ va mDokon xuddi shunday qiladi (raqobatchi amaliyoti tasdiqlaydi); kichik do'konning og'zaki kelishuv madaniyatiga mos.
− Katta summali/ulgurji qarzlar uchun bosqichma-bosqich reja yo'qligi ayrim holatlarda noqulay bo'lishi mumkin (lekin bu holat hozircha tasdiqlangan ehtiyoj emas).

**(b) Installment jadvali (bo'lib-bo'lib to'lash) MVP'da**
+ Ulgurji/katta buyurtmalar uchun moslashuvchan.
− Hech bir tekshirilgan Uzbek yoki xalqaro kichik-biznes tizimida topilmadi — ortiqcha murakkablik (over-engineering), MVP muddatini kechiktiradi.

**(c) Shubhali qarz — avtomatik N kundan keyin belgilanadi**
+ Operatsion soddalik, tizimli hisobot.
− Xalqaro amaliyotda (QuickBooks/Xero) va NSBU 4910 individual-baholash mantiqida **topilmagan** — standart har doim qo'lda/inson bahosi asosida; avtomatik belgilash noto'g'ri signal berishi mumkin (mijoz haligacha to'lashi mumkin bo'lgan holatda "shubhali" deb belgilash huquqiy/ishonch xavfi).

**(d) Shubhali qarz — faqat Egasi qo'lda belgilaydi, sabab bilan, audit-log (joriy spec holati, US-M08-10)**
+ NSBU 4910 "individual baholash" mantiqiga va xalqaro amaliyotga (QuickBooks/Xero) mos; huquqiy xavfni kamaytiradi.
− Egasi unutib qolishi mumkin — shuning uchun tizim aging (0–30/31–60/60+, allaqachon mavjud) asosida **faqat eslatma/ro'yxat** taklif qilishi kerak (status emas).

### Tavsiya

**(a) + (d) — joriy spec holatini saqlash**: bitta va'da sanasi MVP uchun yetarli (raqobatchilar BILLZ/mDokon ham installment taklif qilmaydi); "shubhali qarz" faqat Egasi tomonidan qo'lda, sabab bilan belgilanadi (NSBU 4910 individual-baholash mantiqiga mos), tizim faqat aging-asosidagi ro'yxat/eslatma taklif qiladi, avtomatik status o'zgartirmaydi.

**Ishonch: yuqori** (installment yo'qligi tomonida — ikkala manba guruhi, Uzbek va xalqaro, mos keladi) / **o'rta** (shubhali qarz qo'lda-belgilash tomonida — NSBU 4910 to'liq rasmiy matni o'qilmagani uchun buxgalter tasdig'i tavsiya etiladi, ayniqsa kichik biznes zahira majburiyati bo'yicha).

### Manbalar

- [buxgalter.uz — Счет 4910 «Резерв по сомнительным долгам»](https://buxgalter.uz/publish/doc/text150192_schet_4910_rezerv_po_somnitelnym_dolgam)
- [lex.uz/ru/docs/8130720 — НСФО №2 (3810-son, 2026-04-11, kuchga kirish 2027-01-01)](https://lex.uz/ru/docs/8130720)
- [nrm.uz — (IAS) 8 Учетная политика, изменения в оценках и ошибки (referens)](https://nrm.uz/contentf?doc=650004_%28ias%29_8_uchetnaya_politika_izmeneniya_v_buhgalterskih_ocenkah_i_oshibki)
- billz.io ("Mijoz qarzasini boshqarish" bo'limi), mdokon.uz ("Mijozlar balansi va qarzlari", Business tarif)
- [pdaftar.uz](https://pdaftar.uz/en?from=AppAgg.com) — pDaftar (installment/muddatli savdo reklamasi)
- [odoo.com/documentation — avtomatik follow-up darajalari](https://www.odoo.com/documentation/18.0/applications/finance/accounting/payments/followup.html)
- `spec/01-mahsulot/02-modullar-talablari.md` M08 (US-M08-05…11), `spec/02-arxitektura/02-provodka-qoidalari.md` §2.15

---

## Q15. Yopilgan davrni qayta ochish

### Savol

Yopilgan buxgalteriya davrini (`period_closings`) qayta ochish — NSBU/BHMS va soliq qoidalari nimaga ruxsat beradi (oldingi davr xatolarini tuzatish standarti)? Xalqaro ERP amaliyotida umumiy yondashuv (lock date + admin override + audit) qanday ishlaydi? Tavsiya qanday?

### Bozorda qanday

| Tizim | Lock mexanizmi | Qayta ochish/override kim | Manba |
|---|---|---|---|
| **Odoo** | 3 turdagi sana: **Lock Everything** (barcha yozuvlarni bloklaydi), **Hard Lock** ("irreversible" — qaytarilmaydigan, qattiqroq), **Tax Lock** (faqat soliqqa tegishli) | **Faqat Buxgalteriya ilovasiga Administrator huquqiga ega foydalanuvchilar** istisno (exception) yarata oladi — joriy/barcha foydalanuvchi uchun, muddat va sabab bilan | [odoo.com/documentation — avoid_pitfalls](https://www.odoo.com/documentation/18.0/applications/finance/accounting/get_started/avoid_pitfalls.html) (birlamchi manba, bu sessiyada o'qildi) |
| **QuickBooks Online** | "Closing date" + parol — bitta chegara sanasi | Faqat master/company admin (parol bilan); boshqa foydalanuvchiga ogohlantirish/parol so'raladi; tranzaksiya tarixida o'zgarish qayd etiladi | [quickbooks.intuit.com — Close your books](https://quickbooks.intuit.com/learn-support/en-us/help-article/close-books/close-books-quickbooks-online/L59LelyPM_US_en_US) ("You can't change any transactions on or before that date without approval") |
| **Xero** | **Ikki alohida lock date**: oddiy foydalanuvchilar uchun va "adviser" uchun alohida (ikkinchisi qo'yilsa hech kim — adviser ham — post qila olmaydi) | Faqat "adviser" roli lock date'ni o'zgartiradi; "History and notes" bo'limi har bir o'zgarishni va kimni yozadi | [chargebee.com — Xero lock dates](https://www.chargebee.com/docs/billing/2.0/kb/accounting/xero-lock-dates) ("together they work like a soft close and a hard close") |

### Qonun/standart

- **NSBU №3 (1998-yilgi, "Отчет о финансовых результатах") 2025-01-01'dan kuchini yo'qotgan** (Iqtisodiyot va moliya vaziri 2024-06-14 №130-buyruq, 2-band) — demak eski standart bazasi endi amal qilmaydi, yangilangan NSBU №3 esa moliyaviy natijalar hisobotiga tegishli, xatolarni tuzatish tartibiga emas. Manba: [base.spinform.ru](https://base.spinform.ru/show_doc.fwx?rgn=6452), [lex.uz/acts/711000](https://lex.uz/acts/711000).
- **O'zbekistonda IAS 8 (хатолар, baholash o'zgarishi, uchet siyosati)ning to'g'ridan-to'g'ri analogi — NSFO №2** ("Asoslar: uchet siyosati va uchet baholari", 3810-son buyruq, [lex.uz/ru/docs/8130720](https://lex.uz/ru/docs/8130720)) — IAS 1 + IAS 8 asosida ishlab chiqilgan, lekin **faqat 2027-01-01'dan kuchga kiradi**. **Demak hozirgi vaqtda (MVP davri, 2026) O'zbekistonda prior-period xatolarni tuzatish bo'yicha maxsus, alohida milliy standart YO'Q** — bu me'yoriy bo'shliq, spec'dagi "joriy ochiq davrda tuzatish" yondashuvi buning o'rnini bosadi (me'yoriy taqiq emas, balki arxitektura/amaliy qaror).
- **Soliq kodeksi**: aniqlashtirilgan (uточненная) soliq hisobotini topshirish mumkin, lekin **soliq organi kamchilikni aniqlagandan keyin yoki soliq tekshiruvi tayinlanganidan keyin EMAS**; aniqlashtirilgan hisobotdan oldin kamomad summasi + penya to'lanishi shart ([lex.uz/ru/docs/4674893](https://lex.uz/ru/docs/4674893) — umumiy norma, aniq modda raqami bu tadqiqotda **tasdiqlanmagan**). Bu — davlat tuzgan QQS hisobotini 5 kalendar kun ichida solishtirish qoidasidan (81-modda, O'RQ-1108) **alohida**, umumiyroq norma.

### Variantlar

**(a) Hech qachon qayta ochilmaydi — faqat joriy ochiq davrda tuzatuvchi hujjat (joriy spec holati, `02-provodka-qoidalari.md` §5.1)**
+ Eng oddiy, append-only audit-trail eng toza, moliyaviy hisobotlar barqaror (qayta nashr qilinmaydi).
− Agar moddiy xato (masalan QQS bazasiga ta'sir qiluvchi) topilsa va soliq idorasiga aniqlashtirilgan deklaratsiya topshirish kerak bo'lsa, tizimdagi "o'tgan davr" raqamlari o'zgarmay qoladi — deklaratsiya va ichki hisob orasidagi tafovut alohida kuzatilishi kerak (hozircha mexanizm yo'q).

**(b) Admin/Buxgalter override bilan "qayta ochish" + to'liq audit (Odoo "exception" namunasi)**
+ Moddiy xatolarni asl davrga bog'lab tuzatish imkoni; Odoo'ning vaqtinchalik, foydalanuvchi/muddatga bog'langan, sabab-yozuvli "exception" mexanizmi tayyor namuna.
− Append-only tamoyiliga ehtiyotkorlik bilan moslashtirilishi kerak — "qayta ochish" hech qachon mavjud `ledger_entries`ni UPDATE qilmasligi, faqat **yopilgan davrga bog'langan yangi tuzatuvchi yozuvlarga ruxsat berish** ma'nosida bo'lishi kerak (Odoo'da ham asl yozuv o'zgarmaydi — yangi yozuv + "exception" audit yozuvi qo'shiladi).

**(c) Vaqt oynasi (masalan Soliq kodeksi 81-moddasidagi 5 kalendar kunlik davlat-solishtirish oynasi bilan moslashtirilgan) ichida avtomatik qayta ochish, undan keyin qat'iy yopiq**
+ QQS/aylanma solig'i davlat-solishtirish jarayoni bilan tabiiy mos keladi.
− Boshqa turdagi (QQS'ga aloqasi yo'q) xatolar uchun bu oyna mantiqsiz; ikki xil "oyna" tushunchasi (davlat-solishtirish vs umumiy davr-tuzatish) aralashib ketishi mumkin.

### Tavsiya

**MVP uchun variant (a)ni davom ettirish**, lekin **variant (b)dagi Odoo-uslubidagi "controlled exception" mexanizmini** keyingi bosqichda (Buxgalter rasmiy tasdig'idan keyin) qo'shishni rejalashtirish — bu allaqachon joriy spec qarori ("qayta ochish — faqat Buxgalter tasdig'idan keyin ko'rib chiqiladigan, MVP'dan tashqari jarayon", `02-provodka-qoidalari.md` §5.1) bilan to'liq mos keladi va uni xalqaro amaliyot (Odoo) orqali tasdiqlaydi.

**Ishonch: yuqori** (xalqaro amaliyot — Odoo'ning 3 turdagi lock + admin-exception modeli birlamchi manba bilan tasdiqlangan; append-only + joriy-davr-tuzatish arxitektura tamoyili allaqachon mustahkam) / **o'rta** (O'zbekiston uchun "davrni qayta ochish taqiqlangan/ruxsat etilgan" degan alohida rasmiy normativ topilmadi — bu huquqiy taqiq emas, balki amaliy/me'yoriy bo'shliqdagi arxitektura qarori; 2027-yildan NSFO №2 kuchga kirgach bu band qayta ko'rib chiqilishi kerak).

### Manbalar

- [odoo.com/documentation — Avoid common pitfalls (lock dates)](https://www.odoo.com/documentation/18.0/applications/finance/accounting/get_started/avoid_pitfalls.html)
- [base.spinform.ru — НСБУ №3 (1998, 2025-01-01'dan kuchsiz)](https://base.spinform.ru/show_doc.fwx?rgn=6452); [lex.uz/acts/711000](https://lex.uz/acts/711000)
- [lex.uz/ru/docs/8130720 — НСФО №2 (2027-01-01'dan kuchga kiradi)](https://lex.uz/ru/docs/8130720)
- [lex.uz/ru/docs/4674893 — Soliq kodeksi (aniqlashtirilgan hisobot umumiy normasi)](https://lex.uz/ru/docs/4674893)
- `spec/02-arxitektura/02-provodka-qoidalari.md` §3.3–3.4, §5.1, §5.2

---

## Yakuniy tavsiyalar (1–2 qator har savol uchun)

**Q4 (e-faktura operatori)**: MVP'da faqat **Faktura.uz** bilan boshlash (yagona mustaqil tekshirilgan ochiq API); **Didox** (eng katta tarmoq, 250k+ tashkilot) — ikkinchi bosqichda qo'shiladi; "Hippo" operator sifatida mavjudligi tasdiqlandi, lekin API hujjati topilmadi.

**Q7 (optom narx/stacking)**: To'liq narx-jadvali asosidagi optom narx turlarini keyingi bosqichga qoldirish; MVP'da mijoz profiliga ixtiyoriy doimiy foiz chegirma qo'shish, bir nechta chegirma to'qnashganda **faqat eng ustuvor bittasi** qo'llanilsin (stacking emas) — Odoo "bitta eng mos qoida" mantiqiga mos.

**Q9 (nasiya/shubhali qarz)**: Bitta va'da sanasi MVP uchun yetarli (installment jadvali hech bir tekshirilgan raqobatchida yo'q); "shubhali qarz" faqat Egasi qo'lda belgilaydi (NSBU 4910 individual-baholash mantiqiga mos), avtomatik N-kun qoidasi yo'q.

**Q15 (davr qayta ochish)**: MVP'da yopilgan davr qayta ochilmaydi (joriy qaror saqlanadi); Odoo-uslubidagi admin-exception + audit mexanizmini Buxgalter tasdig'idan keyin keyingi bosqichda qo'shish tavsiya etiladi.
