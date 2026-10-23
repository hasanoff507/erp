# Biznes savollari — tadqiqot 3 (2026-10-15)

*Manba: foydalanuvchi so'rovi bo'yicha 4 ochiq biznes savoli (kamchiliklar-yakuniy.md, bo'lim 3) — har biri uchun bozor tadqiqoti (O'zbekiston raqobatchilari + xalqaro SME POS tizimlari) va tavsiya.*

---

## Savol 1: Standart rol limitlari (kassir chegirma %, PIN'siz qaytarish, kassadan pul olish, bekor qilish huquqi)

### Bozorda qanday (jadval)

| Tizim | Kassir chegirma limiti | PIN'siz qaytarish | PIN'siz kassadan pul olish | Bekor qilish (void) huquqi | Manba |
|---|---|---|---|---|---|
| Loyverse | Raqamli standart yo'q. "Apply discounts with restricted access" — ON/OFF tumbler; o'chirilgan bo'lsa, kassir cheklangan chegirmani bera olmaydi, POS PIN-pad chiqaradi, faqat menejer/administrator PIN kiritgach ishlaydi. | Raqamli standart yo'q — "Perform returns" huquqi ON/OFF; o'chirilsa, kassirda umuman qaytarish tugmasi ko'rinmaydi (miqdor chegarasi emas, to'liq ruxsat/taqiq). | Alohida "Open cash drawer without making a sale" huquqi bor (ON/OFF), summa chegarasi yo'q. | "Void saved items in open tickets" huquqi — ON/OFF, kassirga berilishi/olib tashlanishi mumkin, audit haqida alohida eslatilmagan. | [help.loyverse.com — How to Manage Access Rights of Employees](https://help.loyverse.com/help/how-manage-access-rights-employees) |
| Square | Raqamli % standart yo'q. "Apply Restricted Discounts and Comps" — rol darajasida ON/OFF checkbox; chegirmaning o'zida "Passcode Required" tumbleri bor (4 xonali PIN), lekin bu summa chegarasi emas, balki "ruxsat bor/yo'q" + parol so'rash. | Raqamli standart yo'q — "Issue Refunds" checkbox (ON/OFF), summa bo'yicha emas. | "Manage & Start Cash Drawers" huquqi yo'q bo'lsa, savdosiz kassani ochish uchun menejer parol (passcode) talab qilinadi — summa chegarasi ko'rsatilmagan. | Alohida "Comps/Voids" huquqi; barcha chegirma/qaytarish/bekor qilish amallari "Activity Log"da xodim bo'yicha kuzatiladi (audit). | [squareup.com/help — Create and edit discounts](https://squareup.com/help/us/en/article/3955-create-and-manage-discounts); [Team Management: restricted discounts passcode (community)](https://community.squareup.com/t5/Questions-How-To/Team-Management-How-do-I-set-up-a-restricted-discounts-where-the/m-p/42480); [Re: Can I prevent employees from issuing refunds? (community)](https://community.squareup.com/t5/Questions-How-To/Can-I-prevent-employees-from-issuing-refunds/m-p/150731); [Add and manage team members](https://squareup.com/help/us/en/article/8356-add-and-manage-team-members) |
| Poster POS | Topilmadi — ochiq manbalarda kassir uchun aniq foiz/summa standarti yo'q, faqat "kassir mijozga chegirma bera oladi" degan umumiy tasvir bor; aniq limit sozlamasi haqida jamoat bilim bazasida alohida sahifa topilmadi. | Topilmadi — qaytarish huquqi borligi aytiladi, lekin summa chegarasi haqida ma'lumot topilmadi. | Topilmadi — manba sahifalarida aniq ko'rsatilmagan. | Topilmadi — kassa/rollar bo'yicha umumiy sahifalar bor, lekin "void" uchun alohida huquq/limit tavsifi topilmadi. | [joinposter.com — bilim bazasi (umumiy)](https://knowledge-base.joinposter.com/ru/); [Как настроить доступы сотрудников по заведениям](https://knowledge-base.joinposter.com/ru/how-to-assign-employee-access-by-locations) |
| iiko | Raqamli standart yo'q — chegirma cheklovlari kategoriya, vaqt, summa va foiz bo'yicha moslashtiriladi ("Скидки и надбавки" bo'limi); "katta kassir" (старший кассир) kassirning barcha huquqi + chegirma bilan ishlash huquqiga ega bo'ladi, ya'ni oddiy kassirda chegirma huquqi standart bo'yicha cheklangan bo'lishi mumkin, lekin aniq % ko'rsatilmagan. | Topilmadi (rasmiy hujjatlarda aniq summa chegarasi ko'rsatilmagan, faqat rol asosida ruxsat/taqiq). | Topilmadi (rasmiy hujjatlarda aniq ko'rsatilmagan). | Topilmadi (rasmiy hujjatlarda "void" uchun aniq standart ko'rsatilmagan; rol bo'yicha ruxsat tizimi bor). | [Права доступа в iiko (open-s.info, uchinchi tomon sharh)](https://open-s.info/blog/prava_dostupa_v_iiko/); [iikoFront API — Скидки и надбавки](https://iiko.github.io/front.api.doc/v6/ru/Discounts.html); [iikoOffice foydalanuvchi qo'llanmasi (PDF)](https://ru.iiko.help/resources/Storage/archive/PDF/UG_iikoOffice_5.1.pdf) |
| BILLZ (O'zbekiston) | Topilmadi — marketing/yordam sahifalarida "kassir mijozga qo'lda yoki avtomatik chegirma qo'shishi mumkin" deyiladi, lekin foiz/summa standarti yoki menejer tasdiqlash chegarasi hech qayerda ochiq ko'rsatilmagan. | Topilmadi — "tovarni almashtirish/qaytarish" funksiyasi bor degan umumiy tasvir, summa chegarasi yo'q. | Topilmadi. | Topilmadi — rollarni sozlash imkoniyati borligi aytiladi, lekin "void" uchun alohida sahifa topilmadi. | [billz.io — Простая программа для продаж и кассы](https://billz.io/why-billz/sales-and-cash); [billz.io — Features](https://billz.io/features) |
| REGOS (O'zbekiston) | Topilmadi — "rol va huquqlarni sozlash mumkin" deyiladi, aniq standart raqam ko'rsatilmagan. | Topilmadi — "qaytarishlarni ro'yxatga olish" funksiyasi bor, limit ko'rsatilmagan. | Topilmadi. | Topilmadi — "operatsiyalar jurnali kim nima qilganini ko'rsatadi" (audit bor), lekin "void" uchun alohida ruxsat/limit topilmadi. | [regos.uz — REGOS: POS](https://regos.uz/ru/product/servis-regos/regos-pos-info); [Кассовая дисциплина: что входит в обязанности кассира](https://regos.uz/ru/blog/polezno-znat/kassovaya-distsiplina-chto-vkhodit-v-obyazannosti-kassira) |
| Hippo POS (O'zbekiston) | Topilmadi — "chegirmalar va sodiqlik dasturlari" bor deyiladi, kassir uchun aniq limit ko'rsatilmagan. | Topilmadi — "qaytarish" ombor funksiyasida bor, savdo kassasida limit ko'rsatilmagan. | Topilmadi. | Topilmadi. | [hippo.uz — Hippo POS](https://hippo.uz/ru/pos/) |
| Toast (qo'shimcha, restoran POS) | — (chegirma emas, lekin naqd/void bo'yicha aniq rol tizimi bor) | Qaytarish/void uchun aniq summa chegarasi yo'q — rol darajasida ("Void/Refund Payments" huquqi) va vaqt darajasida cheklanadi: "Void/Refund Payments (Limited to Same Day Only)" huquqi olib tashlansa, har qanday kech void/refund uchun menejer o'ziga tegishli huquq bilan tasdiqlashi kerak. | — | Void "Items/Orders" va "Void/Refund Payments" alohida huquqlar; kassirda bo'lmasa, menejer o'z kodi bilan tasdiqlaydi (summadan qat'i nazar, rol asosida). | [doc.toasttab.com — Refund permissions and limitations](https://doc.toasttab.com/doc/platformguide/adminRefundPermissionsLimitations.html); [support.toasttab.com — Void Items, Payments, and Checks](https://support.toasttab.com/en/article/Voiding-Items-Payments-and-Checks); [support.toasttab.com — Permissions Reference Guide](https://support.toasttab.com/en/article/Access-Permissions-Reference) |
| Restera (umumiy restoran POS, qo'shimcha kontekst uchun) | Kassirga "Discounts" huquqi beriladi; ba'zi chegirma turlarida "Confirmation of manager" belgisi qo'yilsa, menejer tasdiqlashi shart — bu ham foiz emas, balki chegirma-turi darajasida bayroq. | Kassirda "Voids"/"Undo check"/"Delete closed check" alohida huquqlar; summa chegarasi ko'rsatilmagan. | Kassa bo'yicha "Maximum amount in the cash drawer for warning/blocking" parametri bor, lekin standart raqam ko'rsatilmagan — administrator o'zi kiritadi. | "Voids (Reasons for deletion)" direktoriyasi menejer tomonidan boshqariladi; kassirga sabab tanlash huquqi beriladi. | [docs.restera.com — Cashier and Manager Restrictions](https://docs.restera.com/translate/cashier-and-manager-restrictions-35292079.html) |

**Muhim izoh:** yuqoridagi barcha asosiy tizimlarda (Loyverse, Square, Poster, iiko, BILLZ, REGOS, Hippo) kassir uchun **standart raqamli chegirma foizi, qaytarish summasi yoki kassadan pul olish summasi topilmadi**. Bu tizimlarning hammasi "ON/OFF ruxsat + PIN bilan bekor qilish" modelidan foydalanadi — ya'ni ega/menejer o'zi raqamni belgilamaguncha, standart holat odatda "cheklanmagan" (agar huquq yoqilgan bo'lsa) yoki "butunlay yo'q" (agar huquq o'chirilgan bo'lsa), aniq oraliq (masalan, "0–5% PIN'siz, 5%+ PIN bilan") emas.

### Variantlar

1. **"Hammasi yoki hech narsa" modeli (Loyverse/Square uslubi):** Kassirga chegirma/qaytarish/kassa huquqini butunlay berish yoki butunlay olib tashlash, oraliq limit qo'ymasdan. Afzalligi — sodda, tezda sozlanadi. Kamchiligi — kichik, kundalik chegirmalar (masalan, 2000 so'mlik yaxlitlash) uchun ham menejerni chaqirish kerak bo'lib qoladi, bu amaliyotda tez-tez chetga chiqiladi (kassir menejer PIN'ini so'raydi, menejer "keyin aytaman" deb o'zi PIN beradi — nazorat zaiflashadi).
2. **Past, "ishonch" limitlari bilan boshlash (iiko/Restera uslubidagi moslashuvchan limit, lekin kichik raqam bilan):** Kassirga kichik chegirma (masalan, 5% yoki 10 000 so'mgacha), kichik qaytarish (masalan, 50 000 so'mgacha) va kichik kassadan pul olish (masalan, 20 000 so'mgacha) ruxsatini standart qilib berish, undan yuqorisini PIN'ga yo'naltirish. Afzalligi — kundalik mayda amallar uzluksiz ishlaydi, nazorat kattaroq summalarda saqlanadi. Kamchiligi — "to'g'ri" raqamni tanlash oson emas, chunki hech bir ko'rilgan tizim buni ochiq hujjatlashtirmagan — bu o'zimiz sinab ko'rishimiz kerak bo'ladigan taxmin bo'ladi.
3. **Nol-limit, hammasi tasdiqlashga (konservativ, audit-birinchi):** Kassirga chegirma/qaytarish/pul olish bo'yicha standart huquq umuman berilmaydi (limit = 0), hammasi menejer PIN orqali o'tadi, lekin void kabi tez-tez kerak bo'ladigan amal auditlanган holda kassirga qoldiriladi (spec'dagi joriy qaror bilan mos). Afzalligi — eng xavfsiz, kichik do'kon egasi uchun "hech narsa noto'g'ri ketmaydi" tuyg'usi beradi. Kamchiligi — birinchi kundan menejer bandligi ortadi, kichik do'konlarda ko'pincha menejer=egasi bo'lib, u doim kassa oldida bo'lmaydi — ish sekinlashadi.
4. **Chakana savdo sanoatining "qaytarish-kvitansiyasiz" amaliyotidan ilhomlanish:** Yirik chakana tarmoqlarda (Walmart, Target) kvitansiyasiz qaytarish uchun yillik/bir martalik qattiq chegara qo'yiladi (pastda), lekin bu B2C "iste'molchi huquqi" siyosati, kassir-menejer ichki nazorat limiti emas — to'g'ridan-to'g'ri ko'chirib bo'lmaydi, faqat tartib sifatida moslashtirish mumkin (masalan, "kvitansiyasiz qaytarish — faqat menejer PIN bilan, summasidan qat'i nazar").

### Tavsiya (+ ishonch darajasi)

**Hech bir ko'rilgan asosiy POS tizimi (Loyverse, Square, Poster, iiko) standart raqamli limitni (% yoki summa) ochiq hujjatlashtirmagan va ship qilmagan** — bu o'z-o'zidan muhim topilma: ular bu qarorni to'liq do'kon egasiga qoldiradi, faqat ON/OFF + PIN mexanizmini taqdim etadi (**yuqori ishonch** — bu bir nechta mustaqil manbada: Loyverse, Square, Toast, Restera'da takrorlanadi). Shuning uchun quyidagi raqamlar **bevosita manbadan olingan emas, balki AIOS uchun mustaqil taxmin — "tasdiqlanmagan"** deb belgilanadi:

- **Kassir chegirma limiti:** standart bo'yicha **5%** (yoki belgilangan narx chizig'idan past bo'lgan mahsulotlar uchun amalda 5 000–10 000 so'mgacha), undan yuqorisi — `discount.approve` orqali menejer/egasi PIN. *(tasdiqlanmagan, past-o'rta ishonch — sanoat standartidan emas, umumiy chakana amaliyotdan kelib chiqilgan taxmin)*
- **Kvitansiyali qaytarish, PIN'siz:** standart bo'yicha **100 000 so'mgacha** (o'rtacha kichik do'kon cheki qiymatidan kelib chiqib), undan yuqori yoki kvitansiyasiz qaytarish — majburiy menejer PIN. *(tasdiqlanmagan, o'rta ishonch — Walmart/Target kabi yirik tarmoqlarning kvitansiyasiz-qaytarish amaliyoti umumiy yo'nalishni tasdiqlaydi, lekin ular B2C siyosat, bizning holat — ichki nazorat)*
- **Kassadan PIN'siz pul olish (cash.withdraw):** standart bo'yicha **50 000 so'mgacha**, undan yuqori — majburiy PIN. *(tasdiqlanmagan, past ishonch — hech bir ko'rilgan manbada aniq raqam yo'q, faqat "limit bor, lekin administrator sozlaydi" degan umumiy pattern tasdiqlangan)*
- **Bekor qilish (sales.void — tugallanmagan chek):** kassirga **standart bo'yicha ruxsat beriladi, limit qo'yilmaydi, lekin har doim majburiy audit-log bilan** — bu Loyverse, Square va Toast'ning barchasida tasdiqlangan umumiy pattern (void — kassir darajasidagi oddiy amal, audit orqali nazorat qilinadi; **refund/qaytarish** va **chegirma** aksincha, odatda yuqoriroq cheklovga ega bo'ladi). *(yuqori ishonch — bu qoida uchta mustaqil manbada mos keladi: Loyverse "Void saved items", Square "Comps/Voids" + Activity Log, Toast "Void Items/Orders" alohida huquq)*. Bizning joriy spec qarorimiz ("Kassirda sales.void bor, majburiy audit bilan, limitsiz") sanoat amaliyotiga mos keladi — **o'zgartirish shart emas**.

Umumiy xulosa: AIOS standart raqamlarni **taxminiy qiymat** sifatida belgilab, "ega keyinroq o'zgartira oladi" degan UI xabari bilan birga chiqarishi kerak — bu aynan sanoatning o'zi qilayotgan narsa (raqamni hujjatlashtirmaslik, lekin mexanizmni taqdim etish).

### Manbalar

- [help.loyverse.com — How to Manage Access Rights of Employees](https://help.loyverse.com/help/how-manage-access-rights-employees) — 2026-10-15 kuni o'qildi.
- [loyverse.com — Employee Management & Staff management](https://loyverse.com/employee-management) — 2026-10-15.
- [squareup.com/help — Create and edit discounts](https://squareup.com/help/us/en/article/3955-create-and-manage-discounts) — 2026-10-15.
- [squareup.com/help — Add and manage team members](https://squareup.com/help/us/en/article/8356-add-and-manage-team-members) — 2026-10-15.
- [community.squareup.com — Team Management: restricted discounts passcode](https://community.squareup.com/t5/Questions-How-To/Team-Management-How-do-I-set-up-a-restricted-discounts-where-the/m-p/42480) — 2026-10-15.
- [community.squareup.com — Can I prevent employees from issuing refunds?](https://community.squareup.com/t5/Questions-How-To/Can-I-prevent-employees-from-issuing-refunds/m-p/150731) — 2026-10-15.
- [knowledge-base.joinposter.com — bilim bazasi (bosh sahifa)](https://knowledge-base.joinposter.com/ru/) — 2026-10-15.
- [knowledge-base.joinposter.com — Как настроить доступы сотрудников по заведениям](https://knowledge-base.joinposter.com/ru/how-to-assign-employee-access-by-locations) — 2026-10-15.
- [open-s.info — Права доступа в iiko: как управлять ролями сотрудников](https://open-s.info/blog/prava_dostupa_v_iiko/) — uchinchi tomon sharh, 2026-10-15.
- [iiko.github.io — iikoFront API: Скидки и надбавки](https://iiko.github.io/front.api.doc/v6/ru/Discounts.html) — rasmiy API hujjati, 2026-10-15.
- [ru.iiko.help — iikoOffice foydalanuvchi qo'llanmasi (PDF)](https://ru.iiko.help/resources/Storage/archive/PDF/UG_iikoOffice_5.1.pdf) — rasmiy hujjat, 2026-10-15.
- [billz.io — Простая программа для продаж и кассы](https://billz.io/why-billz/sales-and-cash) — 2026-10-15.
- [billz.io — Features](https://billz.io/features) — 2026-10-15.
- [regos.uz — REGOS: POS rabochee mesto kassira](https://regos.uz/ru/product/servis-regos/regos-pos-info) — 2026-10-15.
- [regos.uz — Кассовая дисциплина: что входит в обязанности кассира](https://regos.uz/ru/blog/polezno-znat/kassovaya-distsiplina-chto-vkhodit-v-obyazannosti-kassira) — 2026-10-15.
- [hippo.uz — Hippo POS](https://hippo.uz/ru/pos/) — 2026-10-15.
- [doc.toasttab.com — Refund permissions and limitations](https://doc.toasttab.com/doc/platformguide/adminRefundPermissionsLimitations.html) — 2026-10-15.
- [support.toasttab.com — Void Items, Payments, and Checks](https://support.toasttab.com/en/article/Voiding-Items-Payments-and-Checks) — 2026-10-15.
- [support.toasttab.com — Access Permissions Reference Guide](https://support.toasttab.com/en/article/Access-Permissions-Reference) — 2026-10-15.
- [docs.restera.com — Cashier and Manager Restrictions](https://docs.restera.com/translate/cashier-and-manager-restrictions-35292079.html) — qo'shimcha kontekst uchun (asosiy ro'yxatdagi tizim emas), 2026-10-15.
- [support.miosalon.com — How to setup and manage a discount restriction in POS](https://support.miosalon.com/support/solutions/articles/19000162426-how-to-setup-and-manage-a-discount-restriction-in-pos-) — boshqa sohadagi (salon) dastur, faqat "rol bo'yicha % misol" namunasi sifatida, asosiy manba emas, 2026-10-15.
- [fiscal.screenstepslive.com — What Are Cashier Permissions?](https://fiscal.screenstepslive.com/s/help/m/mws/l/59259-what-are-cashier-permissions) — Petrosoft SmartPOS, qo'shimcha kontekst, 2026-10-15.
- [purchy.ai — How to Return Without a Receipt in 2026](https://www.purchy.ai/blog/how-to-return-without-receipt) — Walmart/Target/Dollar General kvitansiyasiz-qaytarish siyosatlari uchun (B2C kontekst, ichki nazorat emas), 2026-10-15.
- [pluang.com — USD/UZS valyuta kursi](https://pluang.com/en/tools/currency-converter/usd-uzs) — 2026-10-15 holatiga ko'ra taxminan 1 USD ≈ 11 900–11 950 so'm (kontekst uchun, hisob-kitoblarda ishlatilmadi, chunki barcha tavsiyalar to'g'ridan-to'g'ri so'mda berildi).

**Izoh (shaffoflik uchun):** qidiruv natijalarida bir nechta shubhali/soxta ko'rinishdagi manba (masalan, tasodifiy GitHub "feature" Pull Request sahifalari — `VigesimalTech/xpos`, `buitrungtuan-4ps/pos-framework-4ps`, `salehzarora/RestoFlow`, `deepunites/Pos-`) rasmiy POS hujjati sifatida ko'rinib chiqdi; bular tasodifiy/noma'lum repozitoriyalar bo'lib, rasmiy vendor hujjatlari emas. Ushbu hisobotda ulardan hech qanday raqam yoki da'vo manba sifatida ishlatilmadi.

---

## Savol 8 (#60): AI limit tugagandan keyin — overage, hard cap yoki qo'shimcha paket

### Bozorda qanday (jadval)

| Mahsulot | AI narxlash modeli | Limit tugaganda nima bo'ladi | Overage narxi (agar bor bo'lsa) | Manba |
|---|---|---|---|---|
| Shopify Magic | Matn AI (tovar tasvir yozish, email, chat) — barcha tariflarga bepul, amalda cheksiz. Rasm generatsiyasi (Magic Images) — tarifga bog'liq oylik bepul limit (masalan, Basic'da ~50 rasm/oy) | Matn uchun limit yo'q. Rasm uchun limitdan oshganda qo'shimcha kredit sotib olish taklif qilinadi | Aniq overage narxi oshkora e'lon qilinmagan (topilmadi) | [uxify.com](https://uxify.com/blog/shopify-ai-guide/), [letstalkshop.com](https://www.letstalkshop.com/blog/shopify-magic-free-ai-assistant-for-small-store) |
| Square | AI-asosli menyu/rasm/matn generatsiyasi va ChatGPT/Claude orqali "AI discovery" integratsiyasi — qo'shimcha haq yo'q. AI-kiosk (ovozli buyurtma) — alohida apparat ($1,999) + oylik dastur haqi | Foydalanish limiti/overage siyosati hech qayerda alohida hujjatlashtirilmagan | Topilmadi | [squareup.com](https://squareup.com/us/en/press/claude-chatgpt-integrations), [investing.com](https://www.investing.com/news/company-news/square-launches-aipowered-kiosk-with-voice-ordering-for-1999-93CH-4949752) |
| Zoho Zia | Zoho-hosted LLM: oylik bepul token hajmi (Standard — 30 mln, Pro — 20 mln token/oy), keyin prepaid "AI kredit" tizimi (1000 kredit ≈ $1). Alternativ: Zia to'liq Desk Enterprise tarifiga ($40/user/oy) bundle qilingan, overage yo'q | Bepul hajmdan oshganda 1 mln tokenga kredit yechiladi (kredit-asosida to'lov, taxminan $1/1mln token atrofida) | ~1000 kredit = $1, ya'ni ~$1/1 mln token (taxminiy, aniq rasmiy raqam topilmadi) | [zoho.com/agents/pricing](https://www.zoho.com/agents/pricing.html), [eesel.ai](https://www.eesel.ai/blog/zoho-desk-ai-pricing-explained), [layer3labs.io](https://www.layer3labs.io/guides/zoho-zia-explained) |
| Intercom Fin | Oylik token/limit yo'q — toza "per-outcome" (natija bo'yicha) to'lov: muvaffaqiyatli AI yechimi (resolution), protsedura handoff, disqualifikatsiya — har biri bitta narx | Cap/limit tushunchasi yo'q, shunchaki har bir muvaffaqiyatli AI natija uchun to'laysiz; muvaffaqiyatsiz bo'lsa to'lov yo'q | $0.99/natija (resolution), lead-qualification $9.99; alohida xizmat sifatida ishlatilganda +$19/agent/oy baza | [fin.ai/pricing](https://fin.ai/pricing), [intercom.com](https://www.intercom.com/help/en/articles/8205718-fin-ai-agent-outcomes), [getmacha.com](https://www.getmacha.com/blog/intercom-fin-ai-agent-complete-guide) |
| OpenAI API | Oldindan "tarif + limit" yo'q — toza token-bo'yicha pay-as-you-go. "Tier" tushunchasi faqat rate-limit (so'rov tezligi)ni belgilaydi, pul sarfiga bog'liq | Cap/overage tushunchasi mavjud emas — har bir token boshidanoq to'lanadi | Modelga qarab (masalan $0.10–$5.00/1 mln kirish tokeni) | [developers.openai.com](https://developers.openai.com/api/docs/guides/rate-limits), [eesel.ai](https://www.eesel.ai/blog/openai-api-pricing) |
| Notion AI | Tarifga bog'liq oylik AI hajmi (Business/Enterprise'da included), tugaganda kredit paketi sotib olinadi | Oylik hajm tugaganda avtomatik yoki qo'l bilan kredit sotib olish; kreditlar oyga o'tmaydi (expire bo'ladi) | $10/1000 kredit (oylik to'lov) yoki $13/1000 (yillik to'lov, prepaid) | [breeze.pm](https://www.breeze.pm/articles/notion-ai-pricing), [fayedtion.com](https://fayedtion.com/notion-ai-credits-explained-2026/) |
| GitHub Copilot | Tarifga biriktirilgan oylik "premium so'rov" kvotasi (masalan Pro — 300/oy) | Kvota tugaganda — agar overage yoqilgan bo'lsa, avtomatik qo'shimcha to'lov; aks holda to'xtaydi | $0.04/qo'shimcha so'rov (model multiplikatoriga qarab o'sadi); 2026 yilda token-asosli "AI kredit" tizimiga o'tilmoqda | [docs.github.com](https://docs.github.com/en/copilot/reference/copilot-billing/request-based-billing-legacy/github-copilot-premium-requests), [rationalgo.ai](https://rationalgo.ai/resources/app-builder/pricing-guides/github-copilot-premium-requests-explained) |
| Zapier | Tarifga biriktirilgan oylik "task" kvotasi | Kvota tugaganda avtomatik overage yoqilgan bo'lsa Zap ishlashda davom etadi va ortiqcha task uchun to'laydi; aks holda Zap pauza qilinadi (keyingi oygacha) | Baza narxning 1.25x; overage 3x kvotagacha cheklangan (undan keyin to'xtaydi) | [community.zapier.com](https://community.zapier.com/p/pricing-changes), [tinycommand.com](https://tinycommand.com/blogs/zapier-pricing-explained) |
| Mailchimp | Tarifga biriktirilgan oylik kontakt/yuborish limiti | Limitdan oshganda xizmat to'xtamaydi — avtomatik qo'shimcha "add-on blok" hisobga yoziladi, keyingi hisob-kitobda chiqadi | Oshkora e'lon qilinmagan; uchinchi tomon hisoblariga ko'ra taxminan $8–15/1000 email (tarifga qarab) | [mailchimp.com](https://mailchimp.com/help/about-additional-charges/), [salespanel.io](https://salespanel.io/blog/marketing/mailchimp-pricing/) |

**Kam daromadli bozorlar (Janubi-Sharqiy Osiyo, Afrika, Markaziy Osiyo) haqida alohida topilma:** yuqoridagi AI mahsulotlarning hech biri uchun bu mintaqalarga xos alohida AI-overage narxi topilmadi. Topilgan yagona naqsh — umumiy SaaS **PPP (purchasing power parity) chegirmasi**: Janubi-Sharqiy Osiyo (Indoneziya, Filippin, Tailand, Vetnam) uchun bazaviy obuna narxiga ~30–50% chegirma, Janubiy Osiyo/Afrika uchun ~40–60% chegirma — lekin bu **obuna narxining o'ziga** tegishli, AI token/overage narxiga alohida emas ([fungies.io](https://fungies.io/ppp-pricing-saas-boost-global-revenue-2026), [priceparity.net](https://priceparity.net/blog/saas-pricing-by-country-guide)). Markaziy Osiyo/O'zbekiston uchun alohida ma'lumot topilmadi.

**O'zbekiston to'lov tizimlari komissiyasi:** Click va Payme savdo nuqtalari (merchant) uchun komissiya odatda ~1–2% (shartnomaga va oylik aylanmaga qarab 1–2.5% gacha) ([spot.uz](https://www.spot.uz/oz/2026/08/08/fintech-h1), [bank.uz](https://bank.uz/uz/perevodi)).

### Variantlar

**A. Hard cap (overage yo'q — faqat keyingi oygacha kutish yoki tarifni oshirish).**
- Afzalligi: eng oddiy — mavjud "AI soft-block" xatti-harakatidan tashqari hech qanday qo'shimcha billing infratuzilma, Click/Payme mikro-to'lov integratsiyasi, hisob-kitob yoki support yuki kerak emas.
- Kamchiligi: foydalanuvchi oyning o'rtasida AI'dan mahrum bo'lishi mumkin, bu esa tarifni zudlik bilan oshirishga (yoki AI'siz davom etishga) majburlaydi — bu ayni paytdagi spec qarori ("AI soft-block") bilan to'liq mos.
- Bizning holatda alohida muhim: AI xarajati tarif narxining atigi 1.5–6.3%ini tashkil etadi (founder taqdim etgan baho), demak cap'ni kerak bo'lsa birmuncha kengaytirish bizga arzon turadi — bu hard cap variantini amalda "deyarli hech kim duch kelmaydigan" holatga aylantiradi.

**B. Overage — birlik narxida to'lov (token yoki per-action/per-resolution).**
- Token-asosida (OpenAI, Zoho, GitHub Copilot, Zapier naqshi): texnik jihatdan to'g'ridan-to'g'ri — cap hisoblash infratuzilmasi allaqachon kerak. Lekin oxirgi foydalanuvchiga (do'kon egasiga) "token" tushunchasi notanish va mavhum.
- Per-resolution/per-action (Intercom Fin naqshi, $0.99/natija): bizning holatda AI xususiyatlari bir xil turdagi emas — chat javobi, OCR skanerlash, soliq hisobotini tushuntirish, qarz-eslatma matni — bularning har biri turlicha xarajat va qiymatga ega, shuning uchun bitta "natija narxi"ga tenglashtirish adolatli emas va tushuntirish qiyin.
- Eng katta amaliy to'siq: har ikkala holatda ham **mikro-to'lov** kerak bo'ladi — tipik overage summasi oyiga bir necha ming so'mdan unga yaqin bo'ladi (chunki hatto "og'ir" foydalanishda ham umumiy AI xarajati atigi ~15,580 so'm/oy). Click/Payme orqali bunday mayda, tartibsiz summalarni avtomatik yechish: (1) 1–2% komissiya mayda summada nisbatan katta ta'sir qiladi, (2) alohida to'lov so'rovi/tasdiqlash oqimi foydalanuvchi uchun qo'shimcha friksiya, (3) hisob-kitob va support ("nega mendan yana pul yechildi?") yuki — bu yutuqdan ko'ra ko'proq operatsion xarajat yaratadi.

**C. Qo'shimcha paket (oldindan to'lanadigan belgilangan hajmli bandl, masalan "+1 mln token — 10,000 so'm").**
- Notion'ning kredit-paket naqshiga o'xshash, lekin O'zbekiston kontekstida bundan ham yaqinroq analog — mobil operatorlarning "internet paketi sotib olish" tajribasi: do'kon egasi bu UX naqshini allaqachon biladi (*tasdiqlanmagan — bu taxmin, maxsus manbada tasdiqlanmagan*).
- Paket hajmi yetarlicha katta (masalan minimal 5,000–10,000 so'm) qilib belgilansa, Click/Payme'ning 1–2% komissiyasi nisbatan arzon bo'lib qoladi va mavjud obuna to'lov oqimiga (bir martalik invoys) qo'shilishi mumkin — alohida real-time metering/billing integratsiyasi shart emas.
- Kamchiligi: foydalanuvchi paketni oldindan sotib olishi kerak (proaktiv harakat), ya'ni "oyning oxirida bir necha so'rov kerak bo'lib qoldi" holatida foyda keltirmaydi — lekin bizning hajmlarimizda bu holat kam uchraydi degan asos bor (AI cap allaqachon keng).

### Tavsiya (+ ishonch darajasi)

Tavsiya: **hard cap'ni asosiy standart sifatida saqlash (joriy spec qarori — AI soft-block) + cap'larni birmuncha kengroq belgilash + overage/per-resolution to'lovini KIRITMASLIK, o'rniga ixtiyoriy "qo'shimcha paket" (prepaid bundle) imkoniyatini qo'shish.**

Asoslash:
1. Bizning o'z xarajat raqamlarimiz (founder taqdim etgan: Start ~725, Biznes ~5,130, Pro ~15,580 so'm/oy — tarif narxining 1.5–6.3%i) shuni ko'rsatadiki, cap'ni 20–50%ga kengaytirish bizga amalda arzon turadi, bu esa overage/billing murakkabligidan ko'ra sodda va samarali yechim — bu xulosa bizning o'z raqamlarimizga asoslangan, tashqi manbada tasdiqlanmagan.
2. Tadqiqot shuni ko'rsatadiki (Metronome 2025 field report va boshqalar), 2026-yilda SaaS bozorida ustunlik qilayotgan naqsh — "baza obuna + included quota + (ixtiyoriy) overage/kredit" gibrid modeli ([metronome.com](https://metronome.com/blog/ai-pricing-in-practice-2025-field-report-from-leading-saas-teams)), lekin bizning past-ARPU, kichik tranzaksiyali O'zbekiston bozorimiz uchun token-asosida avtomatik overage (OpenAI/Zoho/Copilot naqshi) yoki per-resolution (Intercom naqshi) **mikro-to'lov friksiyasi va tushunarsizlik tufayli nomutanosib murakkablik** keltiradi — bu xulosa qisman manbalashtirilgan (PPP/narx-sezgir bozor xulosalari orqali — [fungies.io](https://fungies.io/ppp-pricing-saas-boost-global-revenue-2026)), qisman founder mahsulot mantiqiga asoslangan (tasdiqlanmagan).
3. Agar kelajakda ba'zi tenant'lar doimiy ravishda cap'ga urilib qolsa (masalan ko'p do'konli zanjirlar), ularga **qo'shimcha paket** (Notion-uslubidagi prepaid bundle, lekin yirikroq va kamroq sodir bo'ladigan summa bilan) taklif qilish — Click/Payme mavjud obuna-to'lov oqimidan foydalanib, yangi real-time billing integratsiyasisiz amalga oshiriladi.
4. Per-resolution (Intercom-uslubida) modelni **rad etish** tavsiya etiladi, chunki bizning AI xususiyatlarimiz heterogen (chat, OCR, hisobot tushuntirish, eslatma) — bitta "natija narxi"ga tenglashtirish adolatli emas va UI/UX'da tushuntirish qiyin bo'ladi.

Ishonch darajasi: **o'rta** — bozor naqshlari (hard cap/overage/paket uchlik taksonomiyasi, Click/Payme komissiya darajasi, umumiy gibrid-modellar trendi) yaxshi manbalashtirilgan, lekin O'zbekistonga/Markaziy Osiyoga xos AI-overage amaliyoti bo'yicha to'g'ridan-to'g'ri manba topilmadi — mahalliy bozor xulosalari (mobil-paket analogiyasi, do'kon egasining to'lov xatti-harakati) founder mahsulot intuitsiyasiga asoslangan va **tasdiqlanmagan** deb belgilanadi.

### Manbalar
- https://uxify.com/blog/shopify-ai-guide/
- https://www.letstalkshop.com/blog/shopify-magic-free-ai-assistant-for-small-store
- https://squareup.com/us/en/press/claude-chatgpt-integrations
- https://www.investing.com/news/company-news/square-launches-aipowered-kiosk-with-voice-ordering-for-1999-93CH-4949752
- https://www.zoho.com/agents/pricing.html
- https://www.eesel.ai/blog/zoho-desk-ai-pricing-explained
- https://www.layer3labs.io/guides/zoho-zia-explained
- https://fin.ai/pricing
- https://www.intercom.com/help/en/articles/8205718-fin-ai-agent-outcomes
- https://www.getmacha.com/blog/intercom-fin-ai-agent-complete-guide
- https://developers.openai.com/api/docs/guides/rate-limits
- https://www.eesel.ai/blog/openai-api-pricing
- https://www.breeze.pm/articles/notion-ai-pricing
- https://fayedtion.com/notion-ai-credits-explained-2026/
- https://docs.github.com/en/copilot/reference/copilot-billing/request-based-billing-legacy/github-copilot-premium-requests
- https://rationalgo.ai/resources/app-builder/pricing-guides/github-copilot-premium-requests-explained
- https://community.zapier.com/p/pricing-changes
- https://tinycommand.com/blogs/zapier-pricing-explained
- https://mailchimp.com/help/about-additional-charges/
- https://salespanel.io/blog/marketing/mailchimp-pricing/
- https://fungies.io/ppp-pricing-saas-boost-global-revenue-2026
- https://priceparity.net/blog/saas-pricing-by-country-guide
- https://www.spot.uz/oz/2026/08/08/fintech-h1
- https://bank.uz/uz/perevodi
- https://metronome.com/blog/ai-pricing-in-practice-2025-field-report-from-leading-saas-teams

---

## Savol 11 (9.3): Support modeli — kanallar, ish vaqti, javob SLA

### Bozorda qanday (jadval)

| Raqobatchi/mahsulot | Kanallar | Ish vaqti | SLA/javob vaqti | Shikoyatlar (agar topilsa) | Manba |
|---|---|---|---|---|---|
| BILLZ (billz.io/uz) | Telefon (+998 78 113 60 14, menejer: +998 78 113 71 44), Telegram (shaxsiy menejerlar — Baxtiyor, Shohrux), email, veb-sayt forma | 09:00–18:59, Dush–Juma (ish kunlari) — 24/7 emas | Topilmadi (rasmiy SLA raqami yo'q) | Topilmadi (o'zbek manbalarida shikoyat topilmadi — avvalgi tadqiqot bilan mos) | [billz.io/uz/support-service](https://billz.io/uz/support-service), [billz.io/uz/contacts](https://billz.io/uz/contacts) |
| REGOS (regos.uz) | Telefon — "Qo'llab-quvvatlash markazi" (+998 55 501 00 30), Telegram bot (@regos_uzbot), Instagram, LinkedIn | Topilmadi (sahifada ko'rsatilmagan) | Topilmadi | Topilmadi | [regos.uz/uz/search](https://regos.uz/uz/search) |
| MoySklad UZ (moysklad.uz) | Telefon (+998 71-205-16-87 — texnik, +998 78-113-64-69 — savdo), email (support@moysklad.uz), Telegram bot, servis holati sahifasi | RF-sayti (moysklad.ru) "24/7 qo'llab-quvvatlash"ni e'lon qiladi, lekin bu UZ-domen uchun alohida tasdiqlanmagan — UZ kontakt sahifasida ish vaqti ko'rsatilmagan | Topilmadi (UZ uchun) | RF-bozor manbalarida (avvalgi tadqiqot): telefon orqali qo'llab-quvvatlash yo'q (faqat chat/email), narx oshirishi/pullik funksiyalarga o'tishi tanqid qilingan — **bu faqat otzovik.com/startpack.ru (RF-bozor) dan, UZ operatsiyasiga tatbiq etilgani tasdiqlanmagan** | [moysklad.uz/contacts](https://www.moysklad.uz/contacts/), avvalgi tadqiqot: `research_notes/texnik/11-raqobatchilar-kamchiliklari.md` |
| Poster POS (joinposter.com) + UZ fiskalizatsiya integratorlari (Multikassa, Rahmat) | Poster o'zi — asosan xalqaro (RU/EN) kanal; UZ-fiskalizatsiya integratorlari alohida: Multikassa tex-support (+998 78 113 77 08), Rahmat tex-support (telefon +998 90 054 74 07 va Telegram @rahmat_support) | Topilmadi (integratorlar uchun ko'rsatilmagan) | Topilmadi | Topilmadi | [joinposter.com/en/applications/multikassa](https://joinposter.com/en/applications/multikassa), [joinposter.com/en/applications/rahmat](https://joinposter.com/en/applications/rahmat) |
| Smart Business / Smartup (ex-UZKASSA) | Telefon (+998 71 203 03 01 — umumiy, +998 71 203 03 05 — tex-support, +998 71 200 88 33 — savdo), Telegram bot (@Greenwhite_bot, @smartup_license), email (support@greenwhite.uz) | Topilmadi | Topilmadi | Topilmadi | [smart-ecosystem.uz/uz/qollab-quvvatlash](https://smart-ecosystem.uz/uz/qollab-quvvatlash/) |
| HIPPO (hippo.uz) | Telefon (+998 33 200 63 63), Instagram, Telegram | Topilmadi | Topilmadi | Topilmadi | WebSearch natijalari (hippo.uz) |
| mDokon (mdokon.uz) | Telegram (o'zbek va rus tilida), telefon (+998 55 500 00 89), Instagram | **24/7 Telegram orqali** — bu ishlab chiquvchi tomonidan aniq e'lon qilingan yagona 24/7 da'vo | Topilmadi (aniq soat/daqiqa raqami yo'q, faqat "24/7" sifat ko'rsatkichi) | Topilmadi | WebSearch natijalari (mdokon.uz) |
| **Xulosa** | Barcha O'zbekiston POS/ERP o'yinchilari telefon + Telegramga tayanadi; hech biri rasmiy, raqamli SLA (masalan "1 soat ichida javob") e'lon qilmaydi | Aksariyati ish kunlari/ish vaqti (BILLZ aniq ko'rsatgan); mDokon "24/7" deb da'vo qiladi, lekin aniqlashtirilmagan | **Butun bozorda bitta ham rasman e'lon qilingan SLA raqami topilmadi** | O'zbek-tilidagi shikoyat manbalari topilmadi (Play Store/forum) — avvalgi tadqiqot bilan bir xil xulosa | — |
| Loyverse (xalqaro, taqqoslash uchun) | Jonli chat (24/7 da'vo qilinadi), email (help@loyverse.com), yordam markazi 17 tilda, jamoat forumi | Chat — 24/7 da'vo | Rasmiy SLA raqami topilmadi; foydalanuvchi shikoyati: email 3 kungacha javobsiz qolgan holatlar bor | Loyverse Town forumida: "help@loyverse.com not replying after 3 days" | [loyverse.town/topic/7147](https://loyverse.town/topic/7147-loyverse-helployversecom-not-replying-after-3-days-of-sending-email/), [loyverse.com](https://loyverse.com/) |
| Shopify (POS/Plus, taqqoslash uchun) | Telefon, jonli chat, email; Plus darajasida — Sidekick, ustuvor chat, qaytar-qo'ng'iroq | Asosiy tariflar — ish vaqti; Plus — 24/7 (javob vaqti tashqi soatlarda sekinlashadi) | Plus: favqulodda holat — ~10 daqiqada qaytar-qo'ng'iroq; email — 48 soat SLA; uchinchi tomon agentliklari odatda P1=1 soat, P2=4 soat, P3=24 soat taklif qiladi | — | [ringly.io/blog/shopify-support-sla](https://www.ringly.io/blog/shopify-support-sla), [charleagency.com](https://www.charleagency.com/articles/shopify-support-how-to-get-help/) |
| Square (taqqoslash uchun) | Telefon (1-855-700-6000), chat (Support Assistant), email | Free/Plus: Dush–Juma 06:00–18:00 Pacific; Premium: 24/7 ustuvor telefon | Email javobi — 24–48 soat; chatda AI-bot soniyalar ichida javob beradi | — | [squareup.com/help](https://squareup.com/help/us/en/article/4993-contact-square-support), [koronapos.com](https://koronapos.com/blog/square-pos-customer-service/) |
| Zendesk sanoat standarti (benchmark, taqqoslash uchun) | — | — | P1/Urgent: 15 daqiqa birinchi javob, 2 soat hal qilish; P2/High: 1 soat / 8 soat; P3/Normal: 4 soat / 24 soat; P4/Low: 24 soat / 72 soat | — | [eesel.ai/blog/zendesk-sla-policy-metrics-by-priority](https://www.eesel.ai/blog/zendesk-sla-policy-metrics-by-priority), [intuitionlabs.ai](https://intuitionlabs.ai/articles/veeva-support-sla-severity-tiers) |

### Variantlar

**A. "Faqat Telegram-bot + FAQ" (eng arzon, minimal)**
- Kanal: mavjud Telegram-bot (hozir bildirishnoma uchun qurilgan) ustiga support-rejim qo'shiladi — foydalanuvchi "/yordam" yozadi, navbatga tushadi, 1 operator javob beradi.
- Xarajat: ~0 qo'shimcha xarajat (mavjud botga qo'shimcha modul), lekin 1 kishi hamon kerak — to'liq avtomatlashtirish yo'q, chunki fiskal/markirovka muammolari insoniy diagnostika talab qiladi.
- Kamchilik: telefon yo'q — fiskal/to'lov blokirovkasi kabi vaziyatda do'kon egasi vahima bosganda qo'ng'iroq qila olmaydi; bu O'zbekiston bozorida kutilmagan holat bo'lishi mumkin, chunki **barcha topilgan raqobatchilar telefon raqamini birinchi o'ringa qo'ygan** (yuqoridagi jadval).

**B. "Telegram + telefon, ish vaqti" (tavsiya etiladigan MVP — pastga qarang)**
- Kanal: Telegram-bot (umumiy savollar, status so'rovlari, oddiy diagnostika) + 1 telefon raqami (kritik holatlar — fiskal/markirovka/to'lov blokirovkasi) uchun.
- Ish vaqti: ish kunlari, masalan 09:00–19:00 (BILLZ namunasida).
- Xodim: 1 support-operator (to'liq stavka) + asoschi/texnik rahbar zaxira sifatida kritik eskalatsiya uchun.
- Bu — bozordagi **de-fakto standart** (BILLZ aynan shu modelni qo'llaydi).

**C. "Telegram + telefon, kengaytirilgan soat (masalan 08:00–22:00 yoki qisman dam kuni)"**
- mDokonning "24/7 Telegram" da'vosiga yaqinroq, lekin to'liq 24/7 emas — kechqurun/dam kuni uchun 1 operator qo'shiladi yoki asosiy operator smena bilan ishlaydi.
- Xarajat taxminan 1.5–2x (A/B variantiga nisbatan), chunki qo'shimcha smena yoki ikkinchi operator kerak.
- Fiskal 48 soatlik muddat nuqtai nazaridan mantiqiy: agar nosozlik juma kechqurun yoki dam kuni yuzaga kelsa, ish kuni boshlanishini kutish 48 soatlik deadlinening katta qismini yeb qo'yishi mumkin — bu stsenariy uchun kengaytirilgan soat qo'shimcha xavfsizlik zahirasi beradi (**bu mulohaza tasdiqlanmagan — raqobatchilarning aynan shu sabab bilan soat tanlagani hech qayerda yozilmagan, bu bizning xulosa**).
- Hozircha "haqiqiy 24/7 jonli operator" variantini **chiqarib tashlash tavsiya etiladi** — Loyverse/Square Premium kabi xalqaro misollar buni yuqori tarifli mijozlar (yoki minglab mijozlar) bazasida qila oladi; bizning dastlabki tenant sonimiz va past ARPU bunga mos emas.

**D. "Telegram + telefon + tashqi autsorsing kol-markaz (ish vaqtidan tashqari uchun)"**
- Asosiy soat — ichki 1 operator; tashqaridan chaqiriladigan autsorsing kol-markaz faqat "kritik" kalendar so'zlarni (masalan "fiskal", "blok", "OFD") aniqlaganda signal beradi va asoschiga qo'ng'iroq yo'naltiradi.
- Bu yondashuv xarajatni past ushlab turadi, lekin texnik murakkablik (marshrutlash, integratsiya) qo'shadi — MVP uchun ortiqcha murakkab, keyingi bosqich uchun saqlanishi mumkin.

### Tavsiya (+ ishonch darajasi)

**Tavsiya etilgan MVP modeli: Variant B — "Telegram + telefon, ish kunlari 09:00–19:00".**

- **Kanallar:** (1) Telegram — mavjud bot ustiga "/yordam" bo'limi (yangi integratsiya xarajati yo'q, chunki bot allaqachon bor); (2) bitta telefon raqami — faqat kritik holatlar (fiskal/OFD, markirovka, to'lov/obuna blokirovkasi) uchun reklama qilinadi, umumiy savollar Telegram/botga yo'naltiriladi. Bu aynan **BILLZ va mDokonning amaldagi modeliga mos** — ishonch darajasi: **yuqori** (ikki yirik O'zbekiston raqobatchisining haqiqiy amaliyoti bilan tasdiqlangan).
- **Ish vaqti:** ish kunlari, 09:00–19:00 (BILLZ namunasi). Dam kunlari — faqat Telegram orqali xabar qoldirish, keyingi ish kuni ertalab birinchi navbatda javob berish siyosati bilan. Ishonch: **o'rta** — BILLZ bilan mos, ammo biz uchun dam kuni siyosati hali sinovdan o'tmagan.
- **Javob SLA — kritik (fiskal/OFD/markirovka/to'lov blokirovkasi):** birinchi javob — **≤1 soat ish vaqti ichida** (Telegram orqali "qabul qilindi, ko'rib chiqilyapti" avtomatik javob bilan ko'ring — bu operator yo'q paytda ham "javob" hisoblanadi; haqiqiy operator aloqasi — maqsad 2 soat ichida). Bu Zendesk sanoat standarti (P1=15 daq, P2=1 soat) bilan solishtirganda **yumshatilgan** — chunki bizda 1-2 kishilik jamoa bor, 15 daqiqalik SLA real emas. 1 soatlik maqsad 48 soatlik qonuniy OFD muddatining ozchiligini (~2%) egallaydi — bu oqilona zahira. Ishonch: **o'rta** — sanoat benchmarkidan moslashtirilgan, bizning haqiqiy operator sig'imi bilan hali sinovdan o'tmagan (**tasdiqlanmagan taxmin**).
- **Javob SLA — oddiy savol/qanday-qilish:** birinchi javob — **≤24 soat ish vaqti ichida** (Zendesk P3/Normal darajasiga mos — 4–24 soat oralig'ining yuqori chegarasi, chunki jamoa kichik). Ishonch: **o'rta**.
- **Rasman e'lon qilish:** hech bir O'zbekiston raqobatchisi raqamli SLA e'lon qilmagani uchun, bizning raqamli SLA'ni ommaga e'lon qilish o'zi **differensiatsiya omili** bo'lishi mumkin ("fiskal muammoda 1 soat ichida javob" — marketing ustunligi). Bu **tasdiqlanmagan** marketing gipotezasi, lekin past xavfli — chunki raqibda yo'q narsa.

**Xodim va xarajat tahmini:**
- hh.uz va olx.uz'dagi Toshkent kol-markaz/support-operator e'lonlari asosida: tajribasiz operator — ~4–6 million so'm/oy, tajribali/ikki tilli (o'zbek+rus) operator — ~6–8 million so'm/oy oralig'ida (bir qancha e'lonlar 15 million so'mgacha ko'tariladi, lekin bular sotuv-og'irlikli yoki ixtisoslashgan rollar). MVP uchun **1 ta to'liq stavka support-operator, ~6 million so'm/oy asosiy maosh** taxmin qilinadi (o'rtacha bozor darajasi).
- Ishga oluvchi tomonidan to'lanadigan ijtimoiy to'lov (yagona ijtimoiy to'lov, ~taxminan 12% atrofida) qo'shilganda — **jami kompaniya xarajati ~6.7–7 million so'm/oy** (**tasdiqlanmagan — aniq YIT stavkasi O'zbekiston soliq qonunchiligidan tasdiqlanishi kerak, bu yurist/buxgalter vazifasi, taxminiy raqam**).
- Shu xarajatni **2–5% daromaddan support xarajati** sanoat benchmarkiga solishtirsak (manba: SaaS Capital/MetricHQ — eng yaxshi SaaS kompaniyalar support+success uchun ARRning <5%ini sarflaydi, o'rtacha 8–9%): oyiga ~7 million so'm xarajatni oqlash uchun, agar support xarajati daromadning 5%ini tashkil etishi kerak bo'lsa — oylik daromad ~140 million so'm bo'lishi kerak. Bizning tariflar bo'yicha (Biznes — 129,000 so'm/oy o'rtacha tenant deb olinsa): 140,000,000 / 129,000 ≈ **~1,085 to'lovchi tenant**. Agar past chegarani (Start, 49,000 so'm) olsak — ~2,850 tenant kerak bo'ladi. Agar yumshatilgan 8% benchmarkni olsak (kichik SaaS uchun odatiyroq) — ~680–1,700 tenant kerak.
- **Xulosa:** 1 operatorlik support xarajati (~7 mln so'm/oy) MVP bosqichida (taxminan 100–300 tenant, `06-nofunksional` §3 sig'im rejasiga ko'ra) daromadning 5% chegarasidan **sezilarli yuqori** bo'ladi (masalan 150 tenant × o'rtacha ~100,000 so'm = 15 million so'm oylik daromad bo'lsa, support xarajati shu daromadning **~45–47%**ini tashkil etadi). Bu **kutilgan holat** — erta bosqichda support xarajati nisbati har doim yuqori bo'ladi (bitta operatorning minimal narxi bor, daromad hali kichik); sanoat benchmarkiga yetish uchun ~1,000+ tenant kerak. Ishonch: **yuqori** (matematik hisob to'g'ri), lekin kirish taxminlari (o'rtacha tarif, YIT stavkasi) — **o'rta ishonch**.
- **Amaliy xulosa:** 1 operator bilan boshlash iqtisodiy jihatdan "yo'qotishli" ko'rinadi, lekin bu **MVP bosqichida kutilgan va qabul qilinadigan xarajat** — chunki (a) operator mavjud bo'lmasa, erta mijozlar yo'qoladi (ayniqsa fiskal/markirovka muammolarida), (b) asoschi/texnik rahbar zaxira support sifatida ishlashi mumkin (qo'shimcha xarajatsiz), bu operator yukini 50% kamaytiradi. Shu sababli **MVP uchun 1 operator + asoschi zahira** modeli tavsiya etiladi, 300+ to'lovchi tenantga yetganda 2-operatorga o'tish ko'rib chiqilsin.

**Umumiy ishonch darajasi: o'rta** — raqobatchi kanal/soat ma'lumotlari aniq manbalardan olingan (yuqori ishonch), ammo SLA raqamlari, maosh taxminlari va tenant-break-even hisobi ko'p joyda ekstrapolatsiya/taxminga asoslangan (**tasdiqlanmagan**) va foydalanuvchi qarori/pilot sinovi bilan tasdiqlanishi kerak.

### Manbalar

- [billz.io/uz/support-service](https://billz.io/uz/support-service)
- [billz.io/uz/contacts](https://billz.io/uz/contacts)
- [regos.uz/uz/search](https://regos.uz/uz/search)
- [moysklad.uz/contacts](https://www.moysklad.uz/contacts/)
- [joinposter.com/en/applications/multikassa](https://joinposter.com/en/applications/multikassa)
- [joinposter.com/en/applications/rahmat](https://joinposter.com/en/applications/rahmat)
- [smart-ecosystem.uz/uz/qollab-quvvatlash](https://smart-ecosystem.uz/uz/qollab-quvvatlash/)
- hippo.uz — telefon +998 33 200 63 63 (WebSearch orqali topilgan, rasmiy sahifa to'liq tekshirilmagan)
- mdokon.uz — 24/7 Telegram support (WebSearch orqali topilgan, rasmiy sahifa to'liq tekshirilmagan)
- [loyverse.com](https://loyverse.com/)
- [loyverse.town/topic/7147](https://loyverse.town/topic/7147-loyverse-helployversecom-not-replying-after-3-days-of-sending-email/)
- [ringly.io/blog/shopify-support-sla](https://www.ringly.io/blog/shopify-support-sla)
- [charleagency.com/articles/shopify-support-how-to-get-help](https://www.charleagency.com/articles/shopify-support-how-to-get-help/)
- [squareup.com/help/us/en/article/4993-contact-square-support](https://squareup.com/help/us/en/article/4993-contact-square-support)
- [koronapos.com/blog/square-pos-customer-service](https://koronapos.com/blog/square-pos-customer-service/)
- [eesel.ai/blog/zendesk-sla-policy-metrics-by-priority](https://www.eesel.ai/blog/zendesk-sla-policy-metrics-by-priority)
- [intuitionlabs.ai/articles/veeva-support-sla-severity-tiers](https://intuitionlabs.ai/articles/veeva-support-sla-severity-tiers)
- [saas-capital.com/blog-posts/spending-benchmarks-for-private-b2b-saas-companies](https://www.saas-capital.com/blog-posts/spending-benchmarks-for-private-b2b-saas-companies/)
- [umbrex.com/resources/company-analysis/customer-service-support/support-cost-as-percentage-of-revenue](https://umbrex.com/resources/company-analysis/customer-service-support/support-cost-as-percentage-of-revenue/)
- hh.uz vakansiyalar: [tashkent.hh.uz/vacancy/131728502](https://tashkent.hh.uz/vacancy/131728502), [tashkent.hh.uz/vacancy/132651756](https://tashkent.hh.uz/vacancy/132651756), [hh.uz/vacancies/operator_call_center](https://hh.uz/vacancies/operator_call_center)
- olx.uz vakansiyalar: [olx.uz/oz/rabota/tashkent/q-operator](https://www.olx.uz/oz/rabota/tashkent/q-operator/)
- Ichki manba (taqqoslash uchun): `research_notes/texnik/11-raqobatchilar-kamchiliklari.md`, `spec/tarix/tekshiruv/kamchiliklar-yakuniy.md` (9.3-band)

---

## Savol 12 (9.1): Unit-iqtisod va Start narxi

### Bozorda qanday (jadval)

**Komponent bo'yicha yangi topilgan narxlar:**

| Komponent | Bizning oldingi taxmin | Yangi topilgan narx | Manba |
|---|---|---|---|
| SMS (nasiya eslatma + OTP) | 5,000–10,000 so'm/oy (20-50 ta × 150-300 so'm — to'liq asossiz taxmin) | **Eskiz.uz**: 95 so'm/SMS, barcha operatorlarga, obuna to'lovsiz, minimal to'lov majburiyati yo'q. 20-50 SMS/oy × 95 so'm = **1,900–4,750 so'm/oy**. Reklama SMS (Ucell/Uzmobile/Mobiuz) — 175 so'm/SMS (bizga tegishli emas, bu nasiya/OTP emas). **Play Mobile**: paket tizimi — "Start" paketi 250 SMSgacha = 5,000 so'm (≈20 so'm/SMS to'liq paket sarflansa), "Infinite" paketi 20,000+ SMS = 500,000 so'm. Playmobile'ning alohida topilgan 168.40 so'm/SMS raqami — bu UZCARD bank-xabarnoma kanali uchun (bizning use-case emas, chalkashtirmaslik kerak) | [eskiz.uz/uz/sms](https://eskiz.uz/uz/sms); [playmobile.uz](https://playmobile.uz/uz/instruction/); [spot.uz UZCARD SMS narxi](https://www.spot.uz/oz/2025/02/15/sms-notification/) |
| Click/Payme — mijoz to'lovi (checkout, karta/QR) | ~1-2% (taxmin) | **Click**: savdo nuqtasida QR/Click Pass — 1% (Uzcard/Humo), 2% (Visa). Billing/integratsiya (onlayn-do'kon, obuna) — 1.5-2.5% (Uzcard/Humo), 2.5% (Visa). **Payme**: xizmat to'lovi/QR — 1%, karta to'lovi — 1.5-2%, birinchi 3 oy ulanish bepul. Taxminimiz **to'g'ri tasdiqlandi** — 1-2% oralig'i real | [click.uz/uz/tarifs](https://click.uz/uz/tarifs); [business.click.uz/uz](https://business.click.uz/uz); Payme biznes qidiruv natijalari (b2b-partner.payme.uz saytiga to'g'ridan-to'g'ri kirish muvaffaqiyatsiz bo'ldi, lekin qidiruv orqali tasdiqlangan) |
| AIOS obuna to'lovi (49,000 so'm/oy) Click/Payme orqali o'tsa | Hisobga olinmagan (bu gap sifatida belgilangan edi) | Click/Payme o'z tariflarida "SaaS obuna" uchun alohida chegirma/kategoriya ko'rsatmaydi — billing/integratsiya tarifiga (1.5-2.5%) tushadi. 49,000 so'm × ~2% = **~980 so'm/oy/tenant qo'shimcha xarajat**, AGAR o'z obuna to'lovimizni Click/Payme orqali qabul qilsak. O'zbek SaaS'lar odatda bu komissiyani o'zi "yutadi" (mijozga qo'shib yubormaydi) — bu amaliyot keng tarqalgan, lekin alohida maqola bilan tasdiqlanmadi (**tasdiqlanmagan, amaliy kuzatuvga asoslangan**) | [click.uz/uz/tarifs](https://click.uz/uz/tarifs) |
| OFD/virtual-kassa partner to'lovi (agar o'z kassani davlat reyestriga ro'yxatdan o'tkazmasdan, partner orqali ishlasak) | REGOS +75,000 so'm/oy (berilgan) | **Multikassa** (Poster POS integratsiyasi misolida): ulanish — $28 (bir martalik), xizmat to'lovi — $8/oy, integratsiya — $5/oy → jami **$13/oy ≈ 155,500 so'm/oy/kassa** (kurs 1$ ≈ 11,963 so'm, 15.10.2026). **REGOS VCR**: fiskal modulni ulash — 1 BHM/yil (davlat belgilagan, "Yangi texnologiyalar" markaziga to'lanadi, barcha OFD operatorlari uchun majburiy — partner tanlovidan mustaqil), + oylik xizmat to'lovi — REGOS obunachilari uchun 0 so'm, boshqalar uchun **100,000 so'm/oy**. Demak, partner-OFD yo'li orqali **bitta kassa uchun ~75,000–155,500 so'm/oy** oraliqida xarajat chiqadi — bu bizning butun Start narximizdan (49,000 so'm) KO'P KATTA | [joinposter.com/multikassa](https://joinposter.com/en/applications/multikassa); [regos.uz/uz/product/regos-vcr/faq](https://regos.uz/uz/product/regos-vcr/faq) |
| O'z kassani davlat reyestrida ro'yxatdan o'tkazish (muqobil yo'l — partner emas) | Spec'da ochiq arxitektura savoli sifatida qoldirilgan | **Davlat Soliq Qo'mitasi**: onlayn-NKM/virtual kassa dasturini reyestrga ro'yxatdan o'tkazish — **bepul** ("hech qanday to'lov olinmaydi"), ariza 4 soat ichida ko'rib chiqiladi, virtual kassa dasturining bazaviy qismi davlat tomonidan bepul taqdim etiladi. Lekin baribir fiskal modul yillik to'lovi (1 BHM, "Yangi texnologiyalar" markaziga) barcha yo'llar uchun majburiy ko'rinadi — bu davlat tomonidan belgilangan, partner emas | [my.gov.uz/uz/service/627](https://my.gov.uz/uz/service/627); [kun.uz/50403927](https://kun.uz/50403927); [gov.uz/oz/soliq/page/virtual-kassa-reestri](https://www.gov.uz/oz/soliq/page/virtual-kassa-reestri?lang=ru) |
| 1 BHM qiymati (2026) | — | **Tasdiqlanmagan** — qidiruv limiti tugagani uchun 2026-yil BHM rasmiy qiymatini tasdiqlay olmadim. Taxminan 400,000-450,000 so'm/yil oralig'ida (2025-yilgi ~375,000 so'm asosida ekstrapolyatsiya) — **taxmin, tasdiqlash kerak** | — |

**Raqobatchilar narxi (kontekst uchun, oldin manbalashtirilgan):**

| Mahsulot | Bazaviy tarif | Virtual kassa holati | Jami (eng past, kassa bilan) |
|---|---|---|---|
| AIOS Start (bizniki) | 49,000 so'm/oy | Bundle ichida (bepul deklaratsiya) | 49,000 so'm/oy |
| REGOS Start | 69,000 so'm/oy | +75,000 so'm/oy majburiy qo'shimcha (eski ma'lumot; yangi FAQ'da REGOS obunachilariga 0 so'm, bo'lmasa 100,000 so'm/oy ko'rsatilgan — tarif o'zgargan bo'lishi mumkin) | 144,000 so'm/oy |
| mDokon | 199,000 so'm/oy dan | Noma'lum | 199,000+ so'm/oy |
| HIPPO Base | 247,200 so'm/oy | Noma'lum | 247,200 so'm/oy |
| BILLZ Start | 299,000 so'm/oy | Noma'lum | 299,000+ so'm/oy |

### Variantlar

**Variant A — Start'ni 49,000 so'mda saqlash, OFD'ni partner orqali "bepul bundle" qilib qoldirish**

Xarajat stacki (partner-OFD yo'li, 1 kassa/tenant):
- Hosting: ~20,500 so'm
- AI: ~2,000-5,000 so'm
- SMS (Eskiz, 20-50/oy): ~1,900-4,750 so'm
- Click/Payme (obuna to'lovi ustida, ~2%): ~980 so'm
- OFD partner (Multikassa/REGOS-tipidagi): **~75,000-155,500 so'm**
- **Jami: ~100,380–186,730 so'm/oy/tenant**

Natija: **-51,000 dan -138,000 so'm/oy gacha ZARAR** har bir Start mijozida. Bu variant **ishlamaydi** — OFD partner to'lovi yolg'iz o'zi butun Start narxidan 1.5-3 marta katta. Bu eng muhim topilma: agar partner-OFD yo'lini tanlasak, Start tarifini "virtual kassa included" deb e'lon qilish moliyaviy jihatdan mumkin emas.

**Variant B — O'z kassani davlat reyestriga ro'yxatdan o'tkazish (partner emas), Start'ni 49,000 so'mda saqlash**

Davlat ro'yxatidan o'tish bepul, faqat fiskal modul yillik to'lovi (1 BHM, taxminan 400-450 ming so'm/yil ≈ 33,000-37,500 so'm/oyga bo'linsa) qoladi — bu barcha yo'llar uchun majburiy, partner tanlovidan mustaqil.

Xarajat stacki:
- Hosting: ~20,500 so'm
- AI: ~2,000-5,000 so'm
- SMS: ~1,900-4,750 so'm
- Click/Payme (obuna ustida): ~980 so'm
- Fiskal modul (1 BHM/yil ÷ 12, taxmin): ~33,000-37,500 so'm
- **Jami: ~58,380–69,730 so'm/oy/tenant**

Natija: Start narxi (49,000 so'm) hali ham **yetarli emas** — bu stack bilan ham ~9,000-21,000 so'm/oy zarar chiqadi (asosan fiskal modul yillik to'lovi tufayli). Lekin bu partner yo'liga nisbatan SEZILARLI yaxshiroq (zarar 5-10 marta kichik) — chunki davlat ro'yxatidan o'tish bepul va faqat majburiy fiskal modul to'lovi qoladi, ustiga qo'yilgan tijorat partner marjasi yo'q. Buning uchun o'z dasturimizni davlat virtual-kassa reyestrida texnik servis markazi/ishlab chiquvchi sifatida ro'yxatdan o'tkazish zarur — bu bir martalik muhandislik/sertifikatlash ishi, lekin oylik qaytariladigan xarajatni tubdan kamaytiradi.

**Variant C — Narxni oshirish (Start'ni 59,000-69,000 so'mga ko'tarish) + o'z-reyestr yo'li**

Variant B stackida (~58,000-70,000 so'm/oy xarajat) Start narxini 69,000 so'mga ko'tarsak:
- Marja: 69,000 - 58,380 (eng past xarajat) = **+10,620 so'm/oy** dan 69,000 - 69,730 = **-730 so'm/oy** gacha — hali ham tor, lekin musbat tomonga yaqinroq.

Bu narx hali ham REGOS'ning asosiy tarifi (69,000 so'm, virtual kassasiz) bilan teng — raqobatbardosh, ayniqsa bizning narx "virtual kassa included" bo'lgani uchun REGOS'ning jami 144,000 so'm/oyiga nisbatan ancha arzon qoladi.

**Variant D — Start'ni 49,000 so'mda saqlash + foydalanish chegaralari (kassa/kvitansiya/AI cap)**

Agar narx o'zgarmasin, lekin quyidagi cheklovlar kiritilsa:
- 1 kassa/nuqta (allaqachon rejalashtirilgan)
- Oyiga kvitansiya/tranzaksiya soni chegarasi (masalan, 1,500-2,000 ta/oy) — SMS va hosting xarajatini nazorat qiladi, chunki eslatma SMS soni savdo hajmiga proportsional
- AI cap (allaqachon rejalashtirilgan)
- **Virtual kassa — ALOHIDA to'lovli qo'shimcha** (REGOS modeli kabi), Start narxiga "bundle ichida bepul" deb KIRITILMASIN, balki +qo'shimcha narx (masalan +25,000-40,000 so'm/oy, davlat-reyestr yo'li bilan hisoblangan xarajatni qoplaydigan darajada) sifatida sotilsin

Bu variant eng realist — chunki asosiy muammo "OFD/virtual kassa bepul" degan va'da, bu xarajatning eng katta va eng beqaror qismi. Boshqa barcha komponentlar (hosting, AI, SMS, to'lov komissiyasi) Start narxiga nisbatan kichik va boshqariladigan (~25,000-30,000 so'm/oy jami, davlat-reyestr fiskal modul to'lovisiz).

### Tavsiya (+ ishonch darajasi)

**Tavsiya: Variant D (narxni 49,000 so'mda saqlash, lekin virtual kassani Start ichida "bepul bundle" qilib EMAS, alohida qo'shimcha xizmat sifatida sotish) + Variant B (o'z dasturni davlat reyestrida ro'yxatdan o'tkazish, tijorat OFD partnyoriga bog'lanmaslik).**

Asoslash:
1. Eng katta topilma — **OFD/virtual-kassa partner to'lovi (75,000-155,500 so'm/oy/kassa) yolg'iz o'zi Start narxidan (49,000 so'm) katta**. Agar "virtual kassa included" va'dasini partner orqali bajarsak, har bir Start mijozida muntazam zarar ko'ramiz. Bu hozirgi spec'dagi "Start — OFD virtual kassa included" tilini qayta ko'rib chiqishni talab qiladi.
2. Davlat reyestriga bepul ro'yxatdan o'tish imkoniyati mavjud (my.gov.uz/soliq xizmati), bu yo'l tijorat partner marjasini butunlay olib tashlaydi va faqat majburiy fiskal modul yillik to'lovini (1 BHM, taxminan 400-450 ming so'm/yil) qoldiradi — bu ham katta, lekin boshqariladigan xarajat.
3. SMS xarajati **bizning asl taxminimizdan ancha arzonroq** chiqdi — Eskiz.uz bo'yicha 95 so'm/SMS flat, oyiga ~1,900-4,750 so'm/tenant (asl taxmin 5,000-10,000 so'm edi). Bu gap endi yopildi va yaxshi tomonga.
4. Click/Payme komissiyasi (1-2%) taxminimizni tasdiqladi — bu kichik qo'shimcha xarajat (~980 so'm/oy agar o'z obuna to'lovimiz ham shu kanal orqali o'tsa).
5. Hosting + AI + SMS + to'lov komissiyasi jami taxminan **25,000-31,000 so'm/oy/tenant** — bu Start narxiga (49,000 so'm) nisbatan sog'lom, ~18,000-24,000 so'm/oy musbat marja qoldiradi, **OFD xarajatini hisobga olmaganda**. Demak muammo faqat OFD/virtual-kassa qismida — qolgan model asosan to'g'ri edi.

**Yakuniy raqamlar (Variant D, davlat-reyestr yo'li, virtual kassa alohida add-on sifatida, taxminan +30,000 so'm/oy):**
- Start asosiy xarajat (OFD'siz): ~25,000-31,000 so'm/oy
- Start narxi: 49,000 so'm/oy
- **Marja (OFD'siz, asosiy Start)**: ~18,000-24,000 so'm/oy — sog'lom
- Virtual-kassa add-on narxi taklifi: +30,000-40,000 so'm/oy (fiskal modul + operatsion xarajatni qoplash uchun)
- Qo'shimcha add-on marjasi: taxminan 0 dan +5,000 so'm/oy (fiskal modul yillik to'lovi noaniqligi tufayli tor)

**Ishonch darajasi:**
- SMS narxi (Eskiz.uz 95 so'm/SMS) — **yuqori** ishonch, rasmiy saytdan to'g'ridan-to'g'ri olingan.
- Click/Payme komissiyasi (1-2%) — **yuqori** ishonch, ikki kompaniyaning rasmiy tarif sahifalaridan olingan, ammo aniq tarif toifasi (POS vs billing/integratsiya) bizning holatimiz uchun qaysi toifaga tushishi hali **tasdiqlanmagan**.
- OFD partner to'lovi (75,000-155,500 so'm/oy) — **o'rta** ishonch — ikki konkret misol (REGOS, Multikassa) topildi, lekin ular bizning aniq integratsiya shartlarimizni aks ettirmaydi; real narx muzokaraga bog'liq bo'lishi mumkin.
- Davlat-reyestr yo'lining bepulligi — **o'rta** ishonch — rasmiy davlat xizmati sahifasida tasdiqlangan, lekin texnik servis markazi sifatida ro'yxatdan o'tish shartlari (kapital, sertifikatlash xarajati) alohida **tasdiqlanmagan**.
- 1 BHM 2026-yil qiymati — **past** ishonch, qidiruv limiti tugagani sababli tasdiqlanmagan, taxmin sifatida belgilangan.
- SaaS obuna to'lovini Click/Payme komissiyasini o'zi yutishi amaliyoti — **past** ishonch, alohida manba bilan tasdiqlanmagan, umumiy bozor amaliyotiga asoslangan taxmin.

### Manbalar

- https://eskiz.uz/uz/sms
- https://playmobile.uz/uz/instruction/
- https://www.spot.uz/oz/2025/02/15/sms-notification/
- https://click.uz/uz/tarifs
- https://business.click.uz/uz
- https://joinposter.com/en/applications/multikassa
- https://regos.uz/uz/product/regos-vcr/faq
- https://my.gov.uz/uz/service/627
- https://kun.uz/50403927
- https://www.gov.uz/oz/soliq/page/virtual-kassa-reestri?lang=ru
- https://soliq.uz/page/virtual-kassa-reestri?lang=ru (asl havola, yuqoridagi manzilga yo'naltiriladi)
- https://www.spot.uz/oz/2026/10/14/dollar-yana-oshdi (1$ ≈ 11,963 so'm, 15.10.2026 kursi uchun)
