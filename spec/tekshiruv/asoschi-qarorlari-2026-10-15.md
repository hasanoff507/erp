# Asoschi qarorlari — 2026-10-15 (8 ta savolga javob)

Bu qarorlar `*(tasdiq kutilmoqda)*` belgisi bilan yozilgan vaqtinchalik variantlarni **almashtiradi**.

| # | Savol | Qaror (asoschi so'zi bilan) | Spec'ga ta'siri |
|---|---|---|---|
| Q1 | Egasi ruxsatlari | "Hamma narsani egasi boshqaradi" | Egasi = barcha ruxsatlar (sotuv, smena, qaytarish, buxgalteriya, sozlamalar). `tasdiq kutilmoqda` belgisi olib tashlanadi |
| Q2 | Chek tili | O'zbek **va** rus tilida: har qatorda "non / хлеб" | `products.name` (uz, asosiy) + `products.name_ru` (ixtiyoriy). Chek qatori: `name / name_ru` (name_ru bo'lmasa faqat name). Chekning sarlavha/yakun matnlari ham ikki tilda ("Jami / Итого"). Fiskal rekvizitlar — OFD talab qilgan formatda |
| Q3 | Qarzga sotuvda fiskal chek | Qarzga olinganda **fiskal chek berilmaydi**, sotuv qarz daftariga yoziladi; **to'langanda fiskal chek beriladi** | Nasiya sotuvi: hujjat (sotuv, qoldiq −, qarz +) yoziladi, `fiscal_receipts` yaratilmaydi (holat: `deferred`). Har bir qarz to'lovida (`debt_payments`) to'langan summaga **fiskal chek** chiqariladi (`fiscal_receipts.kind = debt_settlement`), tovar qatorlari — to'lov qaysi sotuv(lar)ni yopsa, shu sotuv qatorlaridan proporsional. Aralash to'lovda (qisman naqd + qisman qarz) naqd qismiga darhol chek, qarz qismiga to'langanda chek. ⚠ QQS/daromadni tan olish vaqti va bu tartibning qonuniyligi — **buxgalter va yurist tasdig'i** (ochiq savol, kod `FiscalPolicy` sozlamasi ortida yoziladi, keyin o'zgartirish oson) |
| Q4 | Yuridik shaxs | Bitta do'kon = 1 yuridik shaxs; faoliyat turlari ko'p, kassalar ko'p | 1 tenant = 1 yuridik shaxs; ko'p filial, ko'p kassa, ko'p faoliyat turi (`branches.activity_type`) qo'llab-quvvatlanadi |
| Q5 | "Segmentning >70% aylanma solig'i to'laydi" taxmini | Rad — pilotda o'lchanadi | Taxmin olib tashlanadi; QQS va aylanma rejimlari teng qo'llab-quvvatlanadi; pilot ko'rsatkichi: rejimlar ulushi |
| Q6 | 4 ta munozarali hikoya | MVP'dan keyin — to'g'ri | US-M03-02, US-M14-02, US-M08-08, US-M17-05 — MVP'dan keyin (tasdiqlandi) |
| Q7 | SMS | Google bilan kirish + Telegram kod | Ro'yxatdan o'tish/kirish: telefon+parol **yoki "Google bilan kirish"** (OIDC, bizning OAuth AS'da tashqi provayder sifatida). Tasdiqlash kodi (OTP), parolni tiklash, xodim taklifi, eksport tasdig'i, qarz eslatmalari — **Telegram bot** orqali. SMS (Eskiz) — faqat zaxira, Google ham Telegram ham yo'q foydalanuvchi uchun. Google'ning SMS'i ham pullik (Firebase phone auth), shuning uchun ishlatilmaydi |
| Q8 | Jamoa va muddat | Jamoa: asoschi + Claude; qat'iy muddat yo'q | Backlog 2 kishilik jamoaga moslashadi: ishlar ketma-ket, har sprint — bitta vertikal bo'lak (backend+veb birga); hafta hisobidagi muddatlar olib tashlanadi |
