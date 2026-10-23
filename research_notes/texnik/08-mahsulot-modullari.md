# Mahsulot modullari

MVP uchun zarur modullar: kassa, ombor, nasiya, QQS, asosiy buxgalteriya va foydalanuvchi huquqlari. Qo'shimcha modullar (kadrlar/ish haqi, CRM, ishlab chiqarish) keyingi bosqichda.

| Modul | Asosiy funksiyalar | Bosqich | Sabab |
| --- | --- | --- | --- |
| Kassa (POS) | Chek, smenasi, to'lov usullari (naqd, Payme/Click/Uzum), chek printeri | MVP | Chakana savdosining asosiy |
| Qaytarish | Mijozdan tovar qaytarish, balans tuzatish | MVP | Savdo operatsiyasi standart bosqichi |
| Chegirma | Avtomatik chegirma, loyallik bonus, manual chegirma | MVP | Raqobiylik va savdo stimuli |
| Ombor qoldig'i | Tovar balansi real vaqtda (Nomenklatura × Ombor), FIFO yoki o'rtacha tannarx (AVECO) | MVP | Savdo asosining majburiy; **tuzatish**: 4-sonli BHMS "Tovar-moddiy zaxiralar" standarti ([lex.uz/docs/-4890446](https://lex.uz/docs/-4890446)) faqat 3 usulni ko'rsatadi — identifikatsiyalangan tannarx, o'rtacha tortilgan qiymat (AVECO), FIFO. **LIFO standartda umuman ko'rsatilmagan** — avvalgi "FIFO/LIFO" yozuvi noto'g'ri edi |
| Inventarizatsiya | Jismoniy sanash, farq aniqlash, ma'lumotlar o'tkazish | MVP | Buxgalteriya nazoratining talabi |
| Ko'chirish | Ombor orasida tovar ko'chirish | MVP | Ko'p-omborlarda standart operatsiya |
| Xarid/yetkazib beruvchi | Xaridnoma qabul, yetkazib beruvchi hisob-kitob | MVP | Ombor to'ldirishning asosiy |
| Nasiya/qarz | Kredit limiti, to'lov shartlari, eslatma | MVP | Kichik biznesning asosiy savdo turi |
| Narx boshqaruvi | Chakana/optom narxlar, kategoriyalar, tarixi | MVP | Margin maksimallashtirish |
| QQS | Stavkalari (12% standart, 0% ayrim toifa, 2026-06-01 dan ixtiyoriy 6%), deklaratsiya | MVP | Soliq kodeksi, 258-modda; 15%'dan 12%'ga **2023-yil 1-yanvarda** tushirilgan, 2026-yilda stavka o'zgarishsiz qoladi ([kovchegpremium.com](https://kovchegpremium.com/academy/nalogi/nds.html), [uz24.uz](https://uz24.uz/ru/articles/soliq-25-12-22), `01-fayl`) *(2026-10-14 tekshiruvida tuzatildi: avval "2026-yildan 15%'dan 12%'ga tushirilgan" deb yozilgan edi)* |
| Buxgalteriya | Kassa (5010), hisob-kitob (5110), tovar (2010-2090), daromad/xarajat | MVP | Savdo raporti (NSBU №21 asosida) |
| Hisobotlar | Savdo, ombor, buxgalteriya, QQS | MVP | Ratsional nazorati |
| Foydalanuvchi huquqlari | Rol (kassir, ombor, menejer), operatsiya chegaralanishi | MVP | Ko'p-xodim xavfsizligi |
| Ko'p filial | Filiallar sinxronizatsiyasi, konsolidatsiyalangan hisobi | MVP | 2+ do'konlarini borligi |
| Kadrlar/ish haqi | Xodim katalog, ish haqi, soliq | Keyingi bosqich | MVP uchun ortiqcha murakkabligi |
| CRM/sodiqlik | Mijozlar katalog, loyal dasturi | Keyingi bosqich | Savdo asosiga qo'shimcha |
| Ishlab chiqarish | Retseptlar, ishlab chiqarish buyurtmalari | Keyingi bosqich | Kichik biznes uchun ahamiyatsiz |

## Manbalar

1. **ERP+POS ma'lumotlar modeli (umumiy savdo/ombor/kassa qatlami)** — generik obyekt va registr nomlari uchun qarang: `01-erp-modullar-va-malumot-modeli.md`
   - Katalog obyektlari: Nomenklatura, Kontragentlar, Omborlar, Kassalar
   - Hujjatlar: Sotuv hujjati, Kassa cheki, Kassa smenasi, Mijozdan qaytarish, Inventarizatsiya
   - Registrlar: Ombor qoldig'i, Mijoz bilan hisob-kitob, Kassadagi naqd pul (to'liq ro'yxat va manba: `01-erp-modullar-va-malumot-modeli.md`)

2. **Rasmiy buxgalteriya qatlami (NSBU asosida)**
   - NSBU №21 (2024/2025) hisob rejasi asosida
   - QQS (12%, 0%, 6% ixtiyoriy) stavkalari
   - Soliq deklaratsiyalari

3. **Raqobatchilar teknik tahlili** — mavjud tadqiqot 06-faylidan:
   - **BILLZ** ([billz.io/uz](https://billz.io/uz)) — kassa, ombor, nasiya, moliya
   - **REGOS** ([regos.uz](https://regos.uz)) — kassa, ombor, ishlab chiqarish
   - **Smartup** ([greenwhite.uz/smartup](https://www.greenwhite.uz/smartup-en)) — savdo, merchandayzing, nasiya, ombor, HR, ishlab chiqarish
   - **MoySklad** ([moysklad.uz](https://www.moysklad.uz)) — ombor, POS, CRM, moliya, ishlab chiqarish
   - **HIPPO** ([hippo.uz/ru/pos](https://hippo.uz/ru/pos/)) — POS, ombor, CRM, hisobot
   - **Bito ERP** ([bito.uz](https://bito.uz)) — savdo, CRM, ta'minot zanjiri, HR, logistika, ombor
   - **mDokon** ([mdokon.uz](https://mdokon.uz)) — kassa, ombor, nasiya; offline/online
   - **iiko** (restoran, [kafesoft.uz](https://kafesoft.uz)) — zal, oshxona, ombor, xodimlar, moliya
   - **Poster POS** ([joinposter.com](https://joinposter.com)) — xorijiy SaaS, restoran/chakana

## Tahlil

**MVP uchun shart bo'lgan modullar (ERP ma'lumotlar modeli va raqobatchilar asosida)**:
- Kassa/POS, ombor, nasiya, narx boshqaruvi — barcha raqobatchilarida bor
- QQS, asosiy buxgalteriya — NSBU asosida, MVP uchun faqat savdo operatsiyalari
- Foydalanuvchi huquqlari, ko'p filial — BILLZ, Smartup, MoySklad'da aniq qo'llab-quvvatlanadi

**Keyingi bosqiching modullari**:
- Kadrlar/ish haqi — faqat Smartupda asosiy, kichik MVP uchun zarur emas
- CRM/sodiqlik, ishlab chiqarish — BILLZ, Smartup, Bito ERP, MoySklad'da, lekin MVP uchun qo'shimcha
