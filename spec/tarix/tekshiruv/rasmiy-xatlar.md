# Rasmiy murojaat xatlari — to'liq to'plam (Xat 1–10)

*2026-10-15 · Manba: `research_notes/texnik/12-taxminlar-va-murojaatlar.md` (Xat 1–3, o'zgarishsiz ko'chirildi) + yangi Xat 4–10 (shu fayl). Maqsad: `spec/kod-uchun/26-ochiq-savollar-reestri.md`dagi "C — TASHQI" bandlarining katta qismiga rasmiy javob olish.*

*Faqat loyiha — hech qayerga yuborilmaydi. Yuborishdan oldin kompaniya rahbariyati tasdiqlashi, rasmiy blankaga ko'chirilishi va [ ] bilan belgilangan joylar to'ldirilishi kerak. Kim imzolashi/qaysi yuridik shaxs nomidan yuborilishi — ochiq savol, faqat asoschi hal qiladi (`spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md`, savol #16).*

---

## Xat 1 — Davlat soliq qo'mitasi / "Yangi texnologiyalar" ilmiy-axborot markazi DUK

> Hurmatli rahbariyat,
>
> Biz O'zbekiston kichik va o'rta biznes segmenti uchun kassa, ombor va buxgalteriyani birlashtirgan dasturiy mahsulot (ERP+POS) ishlab chiqish ustida ishlamoqdamiz. Loyihani to'g'ri rejalashtirish uchun quyidagi savollarga rasmiy javob olishni so'raymiz:
>
> 1. Dasturiy virtual kassa mahsulotini Davlat reyestriga kiritish (sertifikatlash) uchun qanday xizmatlar pullik, ularning taxminiy narxi qancha va butun jarayon o'rtacha necha kun/oy davom etadi?
> 2. Hujjatlarni ko'rib chiqish bosqichlari (muvofiqlik sertifikati, Kiberxavfsizlik markazi xulosasi, fiskal operator integratsiyasi) uchun alohida-alohida qancha vaqt ketadi?
> 3. my.soliq.uz orqali korxona tomonidan avtomatik tuzilgan soliq hisobotlarini (QQS, aylanma va boshqalar) dasturiy ravishda (API orqali) olish imkoniyati bormi? Agar bo'lsa, qaysi hujjatga/portalga murojaat qilishimiz kerak?
> 4. E-IMZO integratsiyasi uchun rasmiy dasturchi texnik hujjati (API tavsifi) mavjudmi, yoki faqat qo'llanma darajasida ma'lumot beriladimi?
>
> Javobingizni email orqali kutib qolamiz. Hamkorlikka tayyormiz.
>
> Hurmat bilan, [Kompaniya nomi]

---

## Xat 2 — CRPT Turon (Asl belgisi operatori)

> Hurmatli hamkorlar,
>
> Biz O'zbekistonda chakana savdo uchun kassa dasturi (POS) ishlab chiqmoqdamiz, bu dastur orqali Asl belgisi tizimiga ulangan tovarlarni (suv, ichimlik, tamaki va boshqalar) sotish nazarda tutilgan. Quyidagi savollarga javob olishni so'raymiz:
>
> 1. Uchinchi tomon dasturiy ta'minot (POS/ERP) ishlab chiquvchisi sifatida rasmiy integrator maqomini olish uchun qanday hujjatlar va shartlar talab qilinadi?
> 2. Integrator uchun texnik API hujjatlariga (kod tekshirish, sotuvni ro'yxatga olish/"chiqarish") qanday kirish mumkin — bu hujjatlar ochiq portalda bormi yoki faqat shartnoma asosida beriladimi?
> 3. Internet aloqasi yo'q paytda markirovkalangan tovarni sotish uchun qanday rasmiy qoida/tartib belgilangan — bunday holatda sotuvga vaqtincha ruxsat beriladimi, yoki sotuv internet qaytgunga qadar to'xtatilishi shartmi?
>
> Javobingizni kutib qolamiz.
>
> Hurmat bilan, [Kompaniya nomi]

---

## Xat 3 — Davlat kiberxavfsizlik xizmati markazi (csec.uz)

> Hurmatli rahbariyat,
>
> Biz O'zbekistonda xususiy SaaS tarzida ishlaydigan kassa/ERP dasturiy mahsulotini ishlab chiqmoqdamiz. Mahsulot soliq qo'mitasining davlat axborot tizimlariga (OFD, e-faktura, Asl belgisi) faqat **mijoz/foydalanuvchi** sifatida ulanadi — davlat infratuzilmasini o'zi boshqarmaydi va davlat organi emas.
>
> Savolimiz: "Kiberxavfsizlik to'g'risida"gi qonun (ЗРУ-764)ning 18- va 19-moddalaridagi majburiy ekspertiza/sertifikatlash talabi shunday xususiy, oddiy tijorat SaaS mahsulotiga ham tegishlimi, yoki bu talab faqat davlat organlari va kritik axborot infratuzilmasi (KAI) obyektlariga tegishlimi? Agar bizning holatimizda ham ekspertiza/sertifikatlash talab qilinsa, bu jarayonning taxminiy muddati va narxi haqida ma'lumot berishingizni so'raymiz.
>
> Javobingizni kutib qolamiz.
>
> Hurmat bilan, [Kompaniya nomi]

---

## Xat 4 — Faktura.uz (e-faktura operatori)

> Hurmatli hamkorlar,
>
> Biz O'zbekiston kichik va o'rta biznes segmenti uchun kassa, ombor va buxgalteriyani birlashtirgan dasturiy mahsulot (ERP+POS) ishlab chiqmoqdamiz. Mahsulotimiz ko'plab tenant (mijoz-korxona)ga xizmat ko'rsatadigan **SaaS** tizim bo'lib, har bir tenant nomidan Faktura.uz orqali elektron faktura yaratish va yuborishni rejalashtiramiz. Quyidagi savollarga javob olishni so'raymiz:
>
> 1. Ko'p-tenant (multi-tenant) SaaS integratori sifatida ishlash uchun — har bir yakuniy mijoz (tenant) o'z Faktura.uz hisobidan foydalanadimi, yoki integrator darajasida bitta "ulgurji" (reseller/partner) shartnoma va kalit bilan ishlash imkoniyati bormi?
> 2. API hujjatida (`api.faktura.uz/help`) token `grant_type=password` orqali olinishi ko'rsatilgan — bu degani, har bir tenantning Faktura.uz login/parolini bizning tizimimizda saqlashimiz kerakmi? Xavfsizroq (masalan OAuth client credentials yoki API-kalit asosidagi) muqobil autentifikatsiya usuli bormi?
> 3. Test/sandbox muhiti mavjudmi? Agar bo'lsa, unga kirish uchun qanday ariza berish kerak?
> 4. Integrator/partner sifatida ishlash narxlari (ulanish haqi, oylik/tranzaksiya haqi) qanday, va ko'p-tenant hajmda chegirma (ulgurji narx) mavjudmi?
> 5. Operatorlararo roaming — agar bizning tenant mijozi Faktura.uz orqali, kontragenti esa Didox orqali ishlasa, faktura ikki operator orasida avtomatik yetib boradimi?
>
> Javobingizni kutib qolamiz. Hamkorlikka tayyormiz.
>
> Hurmat bilan, [Imzo egasi, lavozimi]
> [Kompaniya nomi], STIR: [STIR]
> Tel: [Telefon], Email: [Email]

---

## Xat 5 — Didox (e-faktura operatori, zahira/kelajakdagi integratsiya)

> Hurmatli hamkorlar,
>
> Biz O'zbekiston kichik va o'rta biznes segmenti uchun kassa, ombor va buxgalteriyani birlashtirgan dasturiy mahsulot (ERP+POS) ishlab chiqmoqdamiz. Birinchi bosqichda Faktura.uz bilan integratsiya qilamiz, keyingi bosqichda Didox bilan ham integratsiya rejalashtirilgan. Quyidagi savollarga javob olishni so'raymiz:
>
> 1. Rasmiy dasturchi (API) hujjatiga kirish qanday amalga oshiriladi — ochiq portal orqali, yoki faqat shartnoma/ro'yxatdan o'tgandan keyin login orqali beriladimi?
> 2. Ko'p-tenant (multi-tenant) SaaS integratori sifatida ishlash uchun — integrator darajasida bitta shartnoma va ulgurji narx bilan barcha tenant mijozlarga xizmat ko'rsatish imkoniyati bormi?
> 3. Autentifikatsiya usuli qanday (login/parol, API-kalit, yoki OAuth)? Har bir tenantning hisob ma'lumotlarini bizning tizimimizda saqlashimiz kerakmi?
> 4. Test/sandbox muhiti mavjudmi va unga kirish tartibi qanday?
> 5. Integrator/partner narxlari (ulanish, oylik, tranzaksiya haqi) va ulgurji chegirma shartlari qanday?
> 6. Faktura.uz orqali ishlaydigan tenant mijozimiz Didox'da ro'yxatdan o'tgan kontragentga faktura yuborganda, operatorlararo roaming avtomatik ishlaydimi?
>
> Javobingizni kutib qolamiz.
>
> Hurmat bilan, [Imzo egasi, lavozimi]
> [Kompaniya nomi], STIR: [STIR]
> Tel: [Telefon], Email: [Email]

---

## Xat 6 — Click (to'lov tizimi — obuna billing + sotuv QR)

> Hurmatli hamkorlar,
>
> Biz O'zbekiston kichik va o'rta biznes segmenti uchun kassa, ombor va buxgalteriyani birlashtirgan dasturiy mahsulot (ERP+POS, SaaS) ishlab chiqmoqdamiz. Click'dan ikki maqsadda foydalanishni rejalashtiramiz: (a) bizning platformamizning oylik obuna to'lovini undirish (merchant — bizning kompaniyamiz), (b) har bir tenant-do'konimiz kassasida mijozlardan Click QR orqali sotuv to'lovini qabul qilish (merchant — har bir tenant alohida). Quyidagi savollarga javob olishni so'raymiz:
>
> 1. Obuna (takroriy/rekurrent) to'lovlarni avtomatik undirish uchun qanday mahsulot/API mos keladi (masalan Click obuna/saqlangan karta xizmati)? Texnik hujjatga qanday kirish mumkin?
> 2. Ko'p-tenant SaaS platformasi sifatida — har bir tenant-do'kon o'zining alohida Click merchant hisobini ochishi kerakmi, yoki platforma darajasida bitta merchant hisobi orqali barcha tenantlar uchun sub-hisob/bo'linish (split) qilish imkoniyati bormi?
> 3. Rasmiy test/sandbox muhiti mavjudmi? Unga kirish uchun ariza qanday beriladi?
> 4. Merchant shartnomasi tuzish uchun talab qilinadigan hujjatlar ro'yxati va komissiya stavkalari qanday?
> 5. Click QR orqali fiskal chekni kim chiqaradi — Click o'zi "komissioner" sifatida, yoki merchant (bizning tenant-do'konimiz) o'z virtual kassasi orqali chiqarishi shartmi?
>
> Javobingizni kutib qolamiz.
>
> Hurmat bilan, [Imzo egasi, lavozimi]
> [Kompaniya nomi], STIR: [STIR]
> Tel: [Telefon], Email: [Email]

---

## Xat 7 — Payme (to'lov tizimi — obuna billing + sotuv QR)

> Hurmatli hamkorlar,
>
> Biz O'zbekiston kichik va o'rta biznes segmenti uchun kassa, ombor va buxgalteriyani birlashtirgan dasturiy mahsulot (ERP+POS, SaaS) ishlab chiqmoqdamiz. Payme'dan ikki maqsadda foydalanishni rejalashtiramiz: (a) bizning platformamizning oylik obuna to'lovini undirish (merchant — bizning kompaniyamiz), (b) har bir tenant-do'konimiz kassasida mijozlardan Payme QR orqali sotuv to'lovini qabul qilish (merchant — har bir tenant alohida). Quyidagi savollarga javob olishni so'raymiz:
>
> 1. Obuna (takroriy) to'lovlarni avtomatik undirish uchun qanday mahsulot/API mos keladi? Texnik hujjat (`developer.help.paycom.uz`)dagi tegishli bo'limga qanday kirish mumkin?
> 2. Ko'p-tenant SaaS platformasi sifatida — har bir tenant-do'kon o'zining alohida Payme merchant hisobini ochishi kerakmi, yoki platforma darajasida bitta merchant hisobi orqali sub-hisob/bo'linish (split) qilish imkoniyati bormi?
> 3. Rasmiy test/sandbox muhiti mavjudmi? Unga kirish uchun ariza qanday beriladi?
> 4. Merchant shartnomasi tuzish uchun talab qilinadigan hujjatlar ro'yxati va komissiya stavkalari qanday?
> 5. Payme QR orqali fiskal chekni kim chiqaradi — Payme o'zi "komissioner" sifatida, yoki merchant o'z virtual kassasi orqali chiqarishi shartmi?
>
> Javobingizni kutib qolamiz.
>
> Hurmat bilan, [Imzo egasi, lavozimi]
> [Kompaniya nomi], STIR: [STIR]
> Tel: [Telefon], Email: [Email]

---

## Xat 8 — Uzum Bank (Checkout/Merchant API — obuna billing + sotuv QR)

> Hurmatli hamkorlar,
>
> Biz O'zbekiston kichik va o'rta biznes segmenti uchun kassa, ombor va buxgalteriyani birlashtirgan dasturiy mahsulot (ERP+POS, SaaS) ishlab chiqmoqdamiz. Uzum'dan ikki maqsadda foydalanishni rejalashtiramiz: (a) bizning platformamizning oylik obuna to'lovini undirish, (b) har bir tenant-do'konimiz kassasida mijozlardan Uzum QR/Checkout orqali sotuv to'lovini qabul qilish. Quyidagi savollarga javob olishni so'raymiz:
>
> 1. Checkout/Merchant API (`developer.uzumbank.uz`)ning aniq protokoli qanday (REST/webhook, autentifikatsiya usuli)? Obuna (rekurrent) to'lovlarni avtomatik undirish imkoniyati bormi?
> 2. Ko'p-tenant SaaS platformasi sifatida — har bir tenant-do'kon o'zining alohida Uzum merchant hisobini ochishi kerakmi, yoki platforma darajasida bitta merchant hisob orqali sub-hisob/bo'linish qilish imkoniyati bormi?
> 3. Rasmiy test/sandbox muhiti mavjudmi? Unga kirish uchun ariza qanday beriladi?
> 4. Merchant shartnomasi tuzish uchun talab qilinadigan hujjatlar ro'yxati va komissiya stavkalari qanday?
> 5. Uzum QR/Checkout orqali to'langanda fiskal chekni kim chiqaradi — Uzum o'zi, yoki merchant o'z virtual kassasi orqali chiqarishi shartmi?
> 6. UzQR (bank yagona QR, PF-246) standarti bilan Uzum Checkout'ning moslashuvi/integratsiyasi haqida texnik hujjat bormi?
>
> Javobingizni kutib qolamiz.
>
> Hurmat bilan, [Imzo egasi, lavozimi]
> [Kompaniya nomi], STIR: [STIR]
> Tel: [Telefon], Email: [Email]

---

## Xat 9 — Fiskal hamkor murojaati (Multikassa / E-POS Communicator)

> Hurmatli hamkorlar,
>
> Biz O'zbekiston kichik va o'rta biznes segmenti uchun kassa, ombor va buxgalteriyani birlashtirgan dasturiy mahsulot (ERP+POS, SaaS) ishlab chiqmoqdamiz. O'z virtual kassa dasturimizni Davlat reyestriga kiritish arizasini boshlagan bo'lsak-da (jarayon bir necha oy davom etadi), shu muddat ichida pilot bosqichida (10–20 do'kon) sizning fiskal modulingiz orqali onlayn-NKM/OFD xizmatidan foydalanishni rejalashtiramiz. Quyidagi savollarga javob olishni so'raymiz:
>
> 1. Uchinchi tomon POS/ERP dasturi uchun API orqali fiskal modul (OFD, chek shakllantirish, Z-hisobot) xizmatini taqdim etish imkoniyati bormi? API texnik hujjatiga qanday kirish mumkin?
> 2. Ko'p-tenant (multi-tenant) SaaS integratori sifatida — har bir yakuniy do'kon-mijozimiz uchun alohida ulanish/xizmat haqi to'lanadimi, yoki integrator darajasida **ulgurji (wholesale) narx** bilan kelishish imkoniyati bormi? Taxminiy ulgurji narx qanday (bir martalik ulanish + oylik xizmat haqi, kassa boshiga)?
> 3. Xizmat ko'rsatish darajasi (SLA) qanday — API mavjudligi foizi, nosozlik holatida qo'llab-quvvatlash javob vaqti?
> 4. Bizning o'z reyestr arizamiz tasdiqlanganidan keyin, sizning xizmatingizdan boshqa (o'z fiskal modulimizga) o'tish uchun qanday shartlar (bildirishnoma muddati, shartnoma bekor qilish tartibi) bor?
> 5. Zaxira mablag' talabi (BHM asosida) va yillik texnik xizmat (1 BHM) to'lovi uchinchi tomon integrator orqali ulangan do'konlarga ham tegishlimi?
>
> Javobingizni kutib qolamiz. Hamkorlikka tayyormiz.
>
> Hurmat bilan, [Imzo egasi, lavozimi]
> [Kompaniya nomi], STIR: [STIR]
> Tel: [Telefon], Email: [Email]

---

## Xat 10 — Davlat soliq qo'mitasiga virtual kassa dasturini Davlat reyestriga kiritish arizasi (qamrov xati)

> Hurmatli rahbariyat,
>
> [Kompaniya nomi] (STIR: [STIR]) quyidagi dasturiy mahsulotni O'zbekiston Respublikasi Davlat soliq qo'mitasining virtual kassa apparatlari va dasturiy ta'minoti reyestriga kiritish uchun ariza bilan murojaat qilmoqda.
>
> **Mahsulot haqida qisqacha:** [Mahsulot nomi] — chakana savdo nuqtalari uchun kassa (POS), ombor va buxgalteriya hisobini birlashtirgan bulutga asoslangan (SaaS) dasturiy ta'minot. Mahsulot fiskal chekni shakllantirish, OFD bilan ma'lumot almashish, soliq hisobotlarini tayyorlashni qamrab oladi.
>
> O'zbekiston Respublikasi Vazirlar Mahkamasining 2020-yil 10-noyabrdagi 943-sonli qarori (VMQ-943) 4-ilovasiga muvofiq, ariza va quyidagi hujjatlar ilova qilinadi:
>
> 1. Yuridik shaxsni davlat ro'yxatidan o'tkazganlik to'g'risidagi guvohnoma (STIR/guvohnoma nusxasi).
> 2. Dasturiy mahsulotning texnik tavsifi (funksional imkoniyatlar, fiskal modul arxitekturasi, OFD bilan integratsiya sxemasi).
> 3. Dasturiy ta'minotning mualliflik huquqini tasdiqlovchi hujjat (agentlikda ro'yxatdan o'tganlik guvohnomasi yoki shunga teng hujjat).
> 4. Mahsulot xavfsizligi/ishonchliligi bo'yicha ichki test hisoboti (agar mavjud bo'lsa).
> 5. Fiskal ma'lumotlar operatori (OFD) bilan tuzilgan yoki tuzilishi rejalashtirilgan shartnoma loyihasi.
> 6. [Agar talab qilinsa] Kiberxavfsizlik markazi (csec.uz) xulosasi uchun ariza nusxasi.
> 7. Zaxira mablag' holati to'g'risidagi bank ma'lumotnomasi (agar virtual kassa toifasiga tegishli bo'lsa — Xat 1 javobida aniqlashtirilishi so'ralgan).
> 8. Davlat bojini (agar belgilangan bo'lsa) to'langanligini tasdiqlovchi hujjat.
>
> Yuqoridagi hujjatlar ro'yxati va ariza ko'rib chiqish muddati/narxi bo'yicha to'liq rasmiy tavsiyani Xat 1 javobida ham so'ramoqdamiz; ushbu xat — reyestrga kiritish jarayonini rasman boshlash uchun qamrov (cover) xati sifatida taqdim etiladi.
>
> Ariza va ilovalarni ko'rib chiqishingizni va reyestrga kiritish jarayoni bo'yicha keyingi qadamlar haqida xabar berishingizni so'raymiz.
>
> Hurmat bilan,
> [Imzo egasi, lavozimi]
> [Kompaniya nomi], STIR: [STIR]
> Tel: [Telefon], Email: [Email]

---

## Manbalar

- `research_notes/texnik/12-taxminlar-va-murojaatlar.md` — Xat 1–3 asl loyihasi.
- `spec/kod-uchun/26-ochiq-savollar-reestri.md` — ushbu xatlar bilan yopiladigan "C — TASHQI" bandlar ro'yxati.
- `spec/kod-uchun/21-integratsiyalar.md` — Faktura.uz/Didox/Click/Payme/Uzum/CRPT/Vakolat.uz integratsiya konteksti.
- `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` — (b)-bo'lim (fiskal yo'l, pilot hamkor tanlovi), savol #16 (xatlarni kim imzolashi).
- [api.faktura.uz/help/](https://api.faktura.uz/help/), [developer.help.paycom.uz](https://developer.help.paycom.uz/), [docs.click.uz](https://docs.click.uz/), [developer.uzumbank.uz](https://developer.uzumbank.uz/en/) — Xat 4/6/7/8 texnik kontekst.
- [lex.uz/docs/4603329](https://lex.uz/docs/4603329) — VMQ-943, 4-ilova (reyestr talablari, Xat 10).
