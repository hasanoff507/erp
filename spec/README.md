# AI ERP+POS — spetsifikatsiya bosqichi

O'zbekiston kichik va o'rta chakana/ulgurji biznesi uchun **AI ichiga qurilgan ERP+POS** —
**noldan quriladigan** mahsulot. Asosiy qiymat taklifi: kassadan
buxgalteriya va soliq hisobotigacha **bitta tizim** + o'zbek tilidagi AI yordamchi.

## Asosiy qarorlar (tadqiqotdan, o'zgarmaydi)

- Tashqi buxgalteriya/ERP tizimlari bilan hech qanday bog'liqlik yo'q — mahsulot noldan qurilgan *(2026-10-15: qabul-5 KICHIK #12 bo'yicha neytral ifodaga almashtirildi)*.
- MVP 18 modul: kassa, qaytarish, chegirma, ombor qoldig'i, inventarizatsiya, ko'chirish, xarid,
  nasiya/qarz daftari, narxlar, QQS, buxgalteriya, hisobotlar, huquqlar, filiallar, xarajatlar,
  kassa pul harakati, obuna/ro'yxatdan o'tish, bildirishnomalar/Telegram bot (2026-10-14)
  (`research_notes/texnik/08-mahsulot-modullari.md`). Kadrlar/ish haqi, CRM, ishlab chiqarish — keyin.
- Markaziy oqim: davlat (Soliq qo'mitasi) tuzgan hisobotni ichki hisob bilan solishtirish, 5 kalendar kun ichida (O'RQ-1108, Soliq kodeksi 81-modda).
- Multi-tenant SaaS (umumiy baza + tenant_id + RLS), PostgreSQL; offline-first kassa
  (append-only event-log, 48 soat OFD chegarasi).
- Stack (2026-10-14, foydalanuvchi qarori): backend — **Python + FastAPI**; birinchi navbatda **veb**
  (back-office + veb-kassa); Android POS (**Kotlin**) — keyingi bosqich, hujjatlari hozirdan tayyorlanadi.
- AI: Claude API (Haiku 5.5 asosiy), `AiProvider` interfeysi; obuna/CLI faqat ishlab chiqishda. MVP'da **4 ta AI funksiya**: AI-01, AI-03 (hujjat OCR), AI-05, AI-06 *(2026-10-15: foydalanuvchi qarori — AI-03 qaytadan MVP'ga kiritildi)*.
- Majburiy davlat tizimlari: virtual kassa/OFD, e-faktura, e-TTN, Asl belgisi, MXIK, e-ishonchnoma, E-IMZO, soliq hisobotlari.
- Autentifikatsiya: o'z (mustaqil) OAuth 2.0 implementatsiyasi, hech qanday mock/soxta login yo'q; admin panel orqali foydalanuvchi qo'shish/bloklash/parol tiklash/sessiya boshqaruvi *(2026-10-15: foydalanuvchi qarori, `spec/kod-uchun/14-autentifikatsiya-oauth2.md`)*. *(2026-10-15: asoschi qarori, Q7)* Ro'yxatdan o'tish/kirish — telefon+parol **yoki "Google bilan kirish"** (Google OIDC, bizning OAuth AS'da tashqi provayder sifatida); tasdiqlash kodi (OTP), parol tiklash, xodim taklifi, eksport tasdig'i va mijoz qarz eslatmalari — **Telegram bot** orqali birinchi navbatda, SMS (Eskiz) faqat Google ham, Telegram ham yo'q foydalanuvchi uchun **zaxira** (Google'ning SMS-asosli telefon autentifikatsiyasi pullik bo'lgani uchun ishlatilmaydi).
- Narx *(2026-10-15: foydalanuvchi qarori)*: **yagona tarif — 99 000 so'm/oy, hammasi narxga kiradi** (18 modul, 1 virtual kassa, AI oylik limiti, Telegram bot); qo'shimcha kassa +39 000 so'm/oy (taxmin); eski Start/Biznes/Pro (49k/129k/249k) uchburchagi bekor qilindi, faqat tarixiy ma'lumot sifatida saqlanadi (`spec/kod-uchun/05-mvp-chegarasi.md`, 3.3-bo'lim).
- Obuna to'lovi kechikkanda: 24 soatlik imtiyozdan keyin tenant uchun kirish **to'liq to'xtaydi** (barcha sessiya bekor, login rad etiladi, to'lov bilan darhol tiklanadi) *(2026-10-15: foydalanuvchi qarori)*. Tor istisno *(2026-10-15: foydalanuvchi qarori, D1)*: lokautdan oldin (imtiyoz davrida) offline yaratilgan, hali yuborilmagan cheklar fiskal 48 soat muddatini buzmasligi uchun fon rejimida (`sync.drain`) OFD'ga yuborilishda davom etadi — yangi sotuv, login va boshqa hamma narsa yopiq qoladi. Ma'lumotlarni eksport qilish lokaut paytida **faqat to'lov sahifasidan**, SMS kod bilan tasdiqlangandan keyin mumkin *(2026-10-15: foydalanuvchi qarori, D2)*.

## Manbalar (avval o'qing)

1. `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` — yakuniy xulosa.
2. `research_notes/texnik/01…11` — modullar, kassa/OFD, e-faktura/to'lov, arxitektura, AI, raqobatchilar, hosting, soliq.
3. `research_notes/AI ERP startap Ozbekistonda/` — bozor tadqiqoti.
4. Asosiy hujjat (Claude Docs): https://claude.ai/code/artifact/e57e7cd7-1117-40a7-8af5-8154a8d22540 — ochilsa o'qing.

## Natija papkalari

| Papka | Mazmuni |
|---|---|
| **`spec/kod-uchun/`** | **Kod uchun yagona spetsifikatsiya** — 00–28 o'qish tartibida (`00-README.md` dan boshlang) |
| `spec/tarix/` | Tekshiruvlar, qabul agentlari qarorlari, kamchiliklar tahlili, tuzatishlar jurnali, rasmiy xatlar — kod uchun shart emas |
| `research_notes/` | Bozor va texnik tadqiqot (manbalar) |

**Jamoa: asoschi + Claude** *(2026-10-15: asoschi qarori, Q8)* — qat'iy muddat yo'q; backlog ikki kishilik jamoaga moslashtirilgan: ishlar ketma-ket, har sprint — bitta vertikal bo'lak (backend+veb birga), hafta hisobidagi muddatlar olib tashlangan (`spec/kod-uchun/27-backlog.md`).

## Qoidalar (barcha agentlar uchun)

- **Kod yozilmaydi** — faqat Markdown hujjatlar (mermaid diagrammalar mumkin).
- O'zbek tilida (lotin). Har fayl: "Asosiy xulosalar" (5-10 qator) → batafsil → "Ochiq savollar" → "Manbalar".
- Talab va raqamlar tadqiqot fayllaridan yoki URL manbadan olinadi; manbasiz raqam yo'q.
  Tadqiqotda yo'q narsa "taxmin" yoki "ochiq savol" deb aniq belgilanadi.
- Har kim faqat o'ziga berilgan faylga yozadi. `research_notes/` ga tegilmaydi.
