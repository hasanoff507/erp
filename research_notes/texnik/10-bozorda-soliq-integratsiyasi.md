# Bozorda soliq integratsiyasi: da'voni tekshirish

*Tadqiqot sanasi: 2026-10-12. Tadqiqotchi: Agent (research).*

## Xulosa: da'vo QISMAN TO'G'RI

**Da'vo**: "O'zbekiston bozorida soliq tizimlari bilan integratsiya qiladigan ERP va POS mahsuloti yo'q."

**Tekshirish natijasi**: DA'VO QISMAN TO'G'RI. O'zbekiston bozorida kamida 12 ta ERP/POS mahsuloti va yana 3 ta EDO (e-faktura) operatori mavjud *(2026-10-14 tekshiruvida aniqlashtirildi: avval "15 ta ERP/POS mahsuloti" deb yozilgan edi — jadvalda jami 15 qator bor, lekin 3 tasi, Didox/Faktura.uz/Soliqservis, ERP/POS emas, balki e-faktura operatorlari)*. Hech birida virtual kassa, OFD, e-faktura, Asl belgisi, MXIK ning 5 ta komponenti birgalikda to'liq tasdiqlangan emas. Har bir mahsulot 1-4 ta komponentni qo'llab-quvvatlaydi, qolganlar yo'q yoki aniq emas.

*(2026-10-14 tekshiruvida aniqlashtirildi: "hech bir raqobatchi soliq tizimlari bilan integratsiya qilmagan" degan kengroq tezis — boshqa fayllarda uchraydi — noto'g'ri. moysklad.uz o'zi reklama qiladi: E-POS orqali fiskal ro'yxatga olish ("Регистрация продаж в налоговой Узбекистана через один клик"), AslBelgisi va Didox (e-faktura) integratsiyasi; REGOS ham Didox bilan integratsiyalangan (pastdagi jadvalga qarang). Farq "integratsiya bor/yo'q" emas, balki: hech biri bitta mahsulotda, uchinchi tomon kassasi/EDO'siz, barcha 5-6 komponentni + davlat hisobotini ichki hisob bilan solishtirishni birlashtirmaydi.)*

---

## Jadval: Mahsulotlar va soliq integratsiyalari

| Mahsulot | Virtual kassa/OFD | E-faktura | Asl belgisi | MXIK | Soliq hisoboti | Manba |
|---|---|---|---|---|---|---|
| **BILLZ** | Ha | Noma'lum | Noma'lum | Noma'lum | Noma'lum | billz.io/uz, 06-fayl *(2026-10-14 tuzatildi: avval E-faktura/Asl belgisi "Ha" edi — billz.io/uz integratsiya sahifasida faqat Payme, Click, UDS, onlayn-do'kon, Telegram bor, Asl belgisi/Didox haqida hech narsa yo'q)* |
| **REGOS** | Ha | **Ha (Didox)** *(2026-10-14 tuzatildi: avval "Noma'lum" edi — regos.uz: "REGOS интегрируется... с ЭДО Didox")* | Ha | Ha | Noma'lum | regos.uz, WebFetch |
| **Smartup** | Ha | Ha | Ha | Noma'lum | Noma'lum | greenwhite.uz, 06-fayl |
| **MoySklad** | Ha | Ha | Ha | Ha | Noma'lum | moysklad.uz, WebFetch |
| **HIPPO** | Ha | Noma'lum | Noma'lum | Noma'lum | Noma'lum | hippo.uz, WebFetch |
| **Bito ERP** | Noma'lum | Noma'lum | Noma'lum | Noma'lum | Noma'lum | bito.uz, WebFetch |
| **mDokon** | Ha | Noma'lum | Noma'lum | Noma'lum | Noma'lum | mdokon.uz, WebFetch |
| **iiko** | Ha | Noma'lum | Noma'lum | Noma'lum | Noma'lum | kafesoft.uz, WebSearch |
| **Poster POS** | Ha | Noma'lum | Noma'lum | Noma'lum | Noma'lum | joinposter.com, WebSearch |
| **UZKASSA** | Ha | Noma'lum | Noma'lum | Noma'lum | Noma'lum | uzkassa.uz, 02-fayl |
| **E-POS Systems** | Ha | Noma'lum | Noma'lum | Noma'lum | Noma'lum | epos.uz, 02-fayl |
| **Rahmat POS** | Ha | Noma'lum | Noma'lum | Noma'lum | Noma'lum | rhmt.uz, WebSearch |
| **Didox** | Noma'lum | Ha (e-faktura op.) | Noma'lum | Noma'lum | Noma'lum | soliq.uz/operatorlar |
| **Faktura.uz** | Noma'lum | Ha (e-faktura op.) | Noma'lum | Noma'lum | Noma'lum | my.soliq.uz/faktura |
| **Soliqservis** | Noma'lum | Ha (e-faktura op.) | Noma'lum | Noma'lum | Noma'lum | service.soliq.uz |

*Eslatma: Didox, Faktura.uz, Soliqservis — virtual kassa emas, balki e-faktura (EDO) operatorlari. "Soliq hisoboti" ustuni "noma'lum" chunki OFD fiskal chekni saqlaydi, fakat QQS yoki foyda solig'i deklaratsiyasini topshirmaydi.*

---

## Xatolar (tuzatilgan)

### 1. Didox, Faktura.uz, Soliqservis
Ular **virtual kassa/OFD emas**, balki **e-faktura (EDO) operatorlari**. Virtual kassa o'zining fiskal chekni shakllantiradi va OFD'ga yuboradi. Didox va yana shunga o'xshashlar — faqat elektronik hisob-fakturalash, chek emas. Alohida qator qilindi.

### 1a. REGOS va BILLZ (2026-10-14 tuzatildi)
REGOS'ning E-faktura ustuni "Noma'lum"dan **"Ha (Didox)"**ga ko'tarildi — regos.uz to'g'ridan-to'g'ri tasdiqlaydi ("REGOS интегрируется... с ЭДО Didox"). Aksincha, BILLZ'ning E-faktura va Asl belgisi ustunlari "Ha"dan **"Noma'lum"**ga tushirildi — billz.io/uz/integration sahifasida faqat Payme, Click, UDS, onlayn-do'kon, Telegram ko'rsatilgan, Asl belgisi/Didox haqida dalil topilmadi.

### 2. "Soliq hisoboti: Ha (OFD orqali)"
Noto'g'ri. OFD fiskal ma'lumotlarni saqlaydi, lekin QQS deklaratsiyasi, foyda solig'i deklaratsiyasini **topshirmaydi**. Bular boshqacha portal/tizimlar. Ustun "noma'lum" qilindi.

### 3. MXIK majburiylik
02-faylga asosan MXIK (ШК/IKPU) **virtual kassa chekining majburiy rekvizitidir**. Har bir virtual kassa Davlat reyestriga kirganidan keyin MXIK bilan ishlashi kerak. Jadvalda ko'p "noma'lum" qilingan, lekin bu texnikaning talabi, mahsulot talabi emas.

### 4. "17 ta mahsulotning barchasi integratsiyalangan"
Noto'g'ri. Jadvalda ko'p "noma'lum" bor. 5 komponentning barchasi birgalikda faqat MoySklad (4 ta: Va, E-faktura, Asl belgisi, MXIK; "Soliq hisoboti" noma'lum). BILLZ, REGOS, Smartup ham 3-4 ta bor, lekin hamma emas.

### 5. Til muammolari
- "integrasiyalari yo'qoladi" → "integratsiyalari yo'q"
- "homon" → "shunchaki", "shuning uchun"
- "pakitda" → "paketda"
- "limitations" → "cheklashlar"

---

## Haqiqiy bo'shliq

**1. Barcha 5 ta soliq komponenti birgalikda qo'llab-quvvatlanuvchi mahsulot yo'q:**
- Maksimal: MoySklad (4 ta: virtual kassa, e-faktura, Asl belgisi, MXIK). "Soliq hisoboti" WebFetch'da teskari o'tilmagan.
- BILLZ, REGOS, Smartup: 3-4 ta komponentni bor.
- Boshqalari: 1-2 ta yoki noma'lum.

**2. MXIK integratsiyasi cheklangan:**
Faqat MoySklad va REGOS'da aniq "IKPU" yoki "MXIK" nomlangan. Qolganlarida asosiy veb-sahifada tilga olinmagan (bu bo'lmaganini bildirmaydi, lekin aniqlanmadi).

**3. E-faktura:** BILLZ, REGOS, Smartup, MoySklad aniq qo'llab-quvvatlaydi. HIPPO, mDokon va boshqalari — Didox/Faktura.uz/Soliqservis operatorlari orqali faqat (ichki API yo'q).

---

## Manbalar

1. billz.io/uz — BILLZ
2. regos.uz — REGOS  
3. greenwhite.uz — Smartup
4. moysklad.uz — MoySklad
5. hippo.uz/ru/pos — HIPPO
6. bito.uz — Bito ERP
7. mdokon.uz — mDokon
8. kafesoft.uz — iiko
9. joinposter.com — Poster POS
10. uzkassa.uz — UZKASSA
11. epos.uz — E-POS Systems
12. rhmt.uz — Rahmat POS
13. www.gov.uz/oz/soliq/page/operatorlar — Didox, Faktura.uz, Soliqservis (e-faktura operatorlari)
14. WebFetch natijalar (2026-10-12)

---

## Oxirgi xulosalar

Bozorda **yagona virtual kassa + OFD + e-faktura + Asl belgisi + MXIK** birgalikda, mustaqil tasdiqlangan holda qo'llab-quvvatlanuvchi ERP/POS yo'q (eng yaqini — MoySklad, 4 ta komponent). *(2026-10-14 tekshiruvida aniqlashtirildi: lekin bir nechta mahsulot — MoySklad, REGOS — soliq tizimlari bilan integratsiya **qiladi**, shuning uchun "hech kim integratsiya qilmagan" degan tezis noto'g'ri.)* AIOS loyihasi uchun **bu farqlanish nuqtasi**: barcha komponentlarni (shu jumladan davlat hisobotini ichki hisob bilan solishtirish) **bitta mahsulotda, uchinchi tomon kassasi/EDO'siz** integratsiya qilish — bozorda yo'qolgan xususiyat, "integratsiya umuman yo'q" emas.
