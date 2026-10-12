# Mahsulot modullari

MVP uchun zarur modullar: kassa, ombor, nasiya, QQS, asosiy buxgalteriya va foydalanuvchi huquqlari. Qo'shimcha modullar (kadrlar/ish haqi, CRM, ishlab chiqarish) keyingi bosqichda.

| Modul | Asosiy funksiyalar | Bosqich | Sabab |
| --- | --- | --- | --- |
| Kassa (POS) | Chek, smenasi, to'lov usullari (naqd, Payme/Click/Uzum), chek printeri | MVP | Chakana savdosining asosiy |
| Qaytarish | Mijozdan tovar qaytarish, balans tuzatish | MVP | Savdo operatsiyasi standart bosqichi |
| Chegirma | Avtomatik chegirma, loyallik bonus, manual chegirma | MVP | Raqobiylik va savdo stimuli |
| Ombor qoldig'i | Tovar balansi real vaqtda (Nomenklatura × Ombor), FIFO/LIFO | MVP | Savdo asosining majburiy |
| Inventarizatsiya | Jismoniy sanash, farq aniqlash, ma'lumotlar o'tkazish | MVP | Buxgalteriya nazoratining talabi |
| Ko'chirish | Ombor orasida tovar ko'chirish | MVP | Ko'p-omborlarda standart operatsiya |
| Xarid/yetkazib beruvchi | Xaridnoma qabul, yetkazib beruvchi hisob-kitob | MVP | Ombor to'ldirishning asosiy |
| Nasiya/qarz | Kredit limiti, to'lov shartlari, eslatma | MVP | Kichik biznesning asosiy savdo turi |
| Narx boshqaruvi | Chakana/optom narxlar, kategoriyalar, tarixi | MVP | Margin maksimallashtirish |
| QQS | Stavkalari (12%, 0%), deklaratsiya | MVP | Soliq kodeksi asosida, O'zbekiston |
| Buxgalteriya | Kassa (5010), hisob-kitob (5110), tovar (2010-2090), daromad/xarajat | MVP | Savdo raporti (NSBU №21 asosida) |
| Hisobotlar | Savdo, ombor, buxgalteriya, QQS | MVP | Ratsional nazorati |
| Foydalanuvchi huquqlari | Rol (kassir, ombor, menejer), operatsiya chegaralanishi | MVP | Ko'p-xodim xavfsizligi |
| Ko'p filial | Filiallar sinxronizatsiyasi, konsolidatsiyalangan hisobi | MVP | 2+ do'konlarini borligi |
| Kadrlar/ish haqi | Xodim katalog, ish haqi, soliq | Keyingi bosqich | MVP uchun ortiqcha murakkabligi |
| CRM/sodiqlik | Mijozlar katalog, loyal dasturi | Keyingi bosqich | Savdo asosiga qo'shimcha |
| Ishlab chiqarish | Retseptlar, ishlab chiqarish buyurtmalari | Keyingi bosqich | Kichik biznes uchun ahamiyatsiz |

## Manbalar

1. **1C:Savdo boshqaruvi UT 11** — [v8.1c.ru — O'zbekiston lokalizatsiyalari](https://v8.1c.ru/static/lokalizovannye-prikladnye-resheniya-uzbekistan/)
   - Spravochniklar: Nomenklutura, Kontragentlar, Omborlar, Kassalar
   - Hujjatlar: RealizatsiyaTovarov, ChekKKM, KassovayaSmena, VozvatTovarovOtKlienta, Inventarizatsiya
   - Registrlar: TovarNaSkladakh, RaschtotySKlientami, DenezhnieSredstaVKassakh

2. **1C:Buxgalteriya 8 (O'zbekiston lokalizatsiyasi)** — [1c.uz — UZ buxgalteriya](https://1c.uz/v8/generic_products/uz_accounting.php)
   - NSBU №21 (2024/2025) hisob rejasi asosida
   - QQS (12%, 0%, 6% ixtiyoriy) stavkalari
   - Soliq deklaratsiyalari

3. **Raqobatchilar teknik tahlili** — mavjud tadqiqot 06-faylidan:
   - **BILLZ** ([billz.io/uz](https://billz.io/uz)) — kassa, ombor, nasiya, moliya
   - **REGOS** ([regos.uz](https://regos.uz)) — kassa, ombor, ishlab chiqarish
   - **Smartup** ([greenwhite.uz/smartup](https://www.greenwhite.uz/smartup-en)) — savdo, merchandayzing, nasiya, ombor, HR, ishlab chiqarish; 1C yonida parallel ishlaydi
   - **MoySklad** ([moysklad.uz](https://www.moysklad.uz)) — ombor, POS, CRM, moliya, ishlab chiqarish
   - **HIPPO** ([hippo.uz/ru/pos](https://hippo.uz/ru/pos/)) — POS, ombor, CRM, hisobot
   - **Bito ERP** ([bito.uz](https://bito.uz)) — savdo, CRM, ta'minot zanjiri, HR, logistika, ombor
   - **mDokon** ([mdokon.uz](https://mdokon.uz)) — kassa, ombor, nasiya; offline/online
   - **iiko** (restoran, [kafesoft.uz](https://kafesoft.uz)) — zal, oshxona, ombor, xodimlar, moliya
   - **Poster POS** ([joinposter.com](https://joinposter.com)) — xorijiy SaaS, restoran/chakana

## Tahlil

**MVP uchun shart bo'lgan modullar (1C va raqobatchilar asosida)**:
- Kassa/POS, ombor, nasiya, narx boshqaruvi — barcha raqobatchilarida bor
- QQS, asosiy buxgalteriya — 1C asosida, MVP uchun faqat savdo operatsiyalari
- Foydalanuvchi huquqlari, ko'p filial — BILLZ, Smartup, MoySklad'da aniq qo'llab-quvvatlanadi

**Keyingi bosqiching modullari**:
- Kadrlar/ish haqi — faqat 1C:Ish Haqi va Smartupda asosiy, kichik MVP uchun zarur emas
- CRM/sodiqlik, ishlab chiqarish — BILLZ, Smartup, Bito ERP, MoySklad'da, lekin MVP uchun qo'shimcha
