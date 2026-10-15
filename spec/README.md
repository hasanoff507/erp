# AI ERP+POS — spetsifikatsiya bosqichi

**Maqsad:** `spec/` papkasiga kirish nuqtasi — mahsulot, asosiy qarorlar va papkalar xaritasi. · **Kim uchun:** asoschi, Claude, yangi qo'shiluvchi. · **Bog'liq fayllar:** `kod-uchun/00-README.md`, `kod-uchun/01-qarorlar.md`, `kod-uchun/26-ochiq-savollar-reestri.md`. · **Holat:** joriy, 2026-10-16.

O'zbekiston kichik va o'rta chakana/ulgurji biznesi uchun **AI ichiga qurilgan ERP+POS** —
**noldan quriladigan** mahsulot. Asosiy qiymat taklifi: kassadan
buxgalteriya va soliq hisobotigacha **bitta tizim** + o'zbek tilidagi AI yordamchi.

## Asosiy qarorlar (to'liq ro'yxat — `kod-uchun/01-qarorlar.md` #1–#65)

- Mahsulot noldan quriladi, yadro 1C'siz ishlaydi. 1C bilan bog'lanish — alohida **1C integratsiya moduli** (noldan yoziladi, Sonar AI namunasi; qaror #36, `../research_notes/sonar-1c-integratsiya/`): **faqat COM** (Do'kon agentining 1C imkoniyati, bulutdan pull, faqat chiquvchi HTTPS; OData/publish yo'q), ERP → 1C bir tomonlama, MVP'dan keyin **Bosqich 7** (`kod-uchun/33-1c-integratsiya.md`, `kod-uchun/34-1c-agent.md`, qarorlar #36–#42).
- **Do'kon agenti** (qaror #60) — do'kon Windows PK'sidagi yagona lokal dastur: fiskal ko'prik (POS → FM → OFD), xom TCP 9100 printer, tarozi (Bosqich 5), 1C (Bosqich 7). MVP kodi `FISCAL_PROVIDER=fake` bilan yoziladi.
- MVP — 18 modul (M01–M18): kassa, qaytarish, chegirma, ombor qoldig'i, inventarizatsiya, ko'chirish, xarid, nasiya/qarz daftari, narxlar, QQS, buxgalteriya, hisobotlar, huquqlar, filiallar, xarajatlar, kassa pul harakati, obuna/ro'yxatdan o'tish, bildirishnomalar/Telegram bot; M19 (1C) — MVP'dan keyin. Kadrlar/ish haqi hisoblash, CRM, ishlab chiqarish — keyin.
- Markaziy oqim: davlat (Soliq qo'mitasi) tuzgan hisobotni ichki hisob bilan solishtirish; tasdiqlash yoki tuzatib taqdim etish — **5 ish kuni** ichida, hisobot topshirish muddatidan kechiktirmay (SK 5-modda 7-qism, 81-modda; qaror #50).
- Multi-tenant SaaS (umumiy baza + `tenant_id` + RLS), PostgreSQL; offline-first kassa (append-only event-log). Offline fiskal shkala 24/40/46 soat ogohlantirish, **48 soatda kassa bloklanadi** — to'plangan cheklar OFD'ga yetguncha yangi fiskal chek chiqarilmaydi (qaror #43).
- Stack: backend — **Python + FastAPI**; birinchi navbatda **veb** (back-office + veb-kassa); Android POS (**Kotlin**) — MVP'dan keyin, hujjatlari tayyor (`kod-uchun/28-android-pos.md`).
- AI: Claude API, `AiProvider` interfeysi; MVP'da **4 ta AI funksiya** — AI-01, AI-03 (hujjat OCR, standart model Haiku 5.5, past ishonchda Sonnet 5.5), AI-05, AI-06 (qaror #16). AI'ga yuborishda shaxsiy maydonlar **maskalanadi** (majburiy), chegaradan tashqari uzatishga tenant roziligi (qaror #61).
- Majburiy davlat tizimlari: virtual kassa/OFD, e-faktura (MVP operatori Faktura.uz), e-TTN (o'z filiallari orasida ham), Asl belgisi (sotuvda kod fiskal chek ichida), MXIK, e-ishonchnoma (e-faktura operatori orqali), E-IMZO, soliq hisobotlari.
- Autentifikatsiya: o'z OAuth 2.0 implementatsiyasi (mock/soxta login yo'q), admin panel orqali foydalanuvchi boshqaruvi (qaror #14). Kirish — telefon+parol yoki "Google bilan kirish"; OTP va xabarlar — **Telegram bot** birinchi, SMS (Eskiz) faqat zaxira (qaror #34).
- Narx: **yagona tarif — 99 000 so'm/oy, hammasi kiradi** (barcha modul, 1 virtual kassa, AI oylik limiti, Telegram bot); qo'shimcha kassa +39 000 so'm/oy (taxmin, 26 #168) (qaror #22).
- Obuna to'lovi kechikkanda: 24 soatlik imtiyozdan keyin tenant uchun kirish **to'liq to'xtaydi**, to'lov bilan darhol tiklanadi (qaror #15). Istisnolar: lokautdan oldin yaratilgan, yuborilmagan fiskal cheklar `sync.drain` orqali OFD'ga yetadi (qaror #19); ma'lumot eksporti — faqat to'lov sahifasidan, OTP tasdig'i bilan (qaror #20).
- Jamoa: **asoschi + Claude**; qat'iy kalendar muddat yo'q, ishlar ketma-ket bosqichlarda (qaror #35, `kod-uchun/27-backlog.md`).

## Manbalar

1. `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` — texnik tadqiqot xulosasi.
2. `research_notes/texnik/01…11` — modullar, kassa/OFD, e-faktura/to'lov, arxitektura, AI, raqobatchilar, hosting, soliq.
3. `research_notes/AI ERP startap Ozbekistonda/` — bozor tadqiqoti.
4. `research_notes/ochiq-savollar/` — ochiq savollarni yopish tadqiqoti (qarorlar #43–#65 manbasi).
5. Asosiy hujjat (Claude Docs): https://claude.ai/code/artifact/e57e7cd7-1117-40a7-8af5-8154a8d22540.

## Natija papkalari

| Papka | Mazmuni |
|---|---|
| **`spec/kod-uchun/`** | **Kod uchun yagona spetsifikatsiya** — 00–34 o'qish tartibida (`00-README.md` dan boshlang) |
| `spec/tarix/` | Tekshiruvlar, qabul agentlari qarorlari, kamchiliklar tahlili, tuzatishlar jurnali, rasmiy xatlar — kod uchun shart emas |
| `research_notes/` | Bozor va texnik tadqiqot (manbalar) |

## Qoidalar (spec fayllari uchun)

- O'zbek tilida (lotin). Har fayl boshida standart blok: **Maqsad · Kim uchun · Bog'liq fayllar · Holat**; keyin asosiy xulosalar → batafsil → "Ochiq savollar" (faqat tashqi javob kutayotgan bandlar, 26 raqami bilan) → "Manbalar".
- Talab va raqamlar tadqiqot fayllaridan yoki URL manbadan olinadi; manbasiz raqam *taxmin* deb belgilanadi.
- Fayllarda faqat joriy haqiqat yoziladi; o'zgarishlar tarixi — git va `spec/tarix/`. Ziddiyatda `kod-uchun/01-qarorlar.md` ustun.
