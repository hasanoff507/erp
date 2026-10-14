# AI ERP+POS — spetsifikatsiya bosqichi

O'zbekiston kichik va o'rta chakana/ulgurji biznesi uchun **AI ichiga qurilgan ERP+POS** —
**noldan quriladigan** mahsulot. Asosiy qiymat taklifi: kassadan
buxgalteriya va soliq hisobotigacha **bitta tizim** + o'zbek tilidagi AI yordamchi.

## Asosiy qarorlar (tadqiqotdan, o'zgarmaydi)

- 1C bilan hech qanday bog'liqlik yo'q.
- MVP 18 modul: kassa, qaytarish, chegirma, ombor qoldig'i, inventarizatsiya, ko'chirish, xarid,
  nasiya/qarz daftari, narxlar, QQS, buxgalteriya, hisobotlar, huquqlar, filiallar, xarajatlar,
  kassa pul harakati, obuna/ro'yxatdan o'tish, bildirishnomalar/Telegram bot (2026-10-14)
  (`research_notes/texnik/08-mahsulot-modullari.md`). Kadrlar/ish haqi, CRM, ishlab chiqarish — keyin.
- Markaziy oqim: davlat (Soliq qo'mitasi) tuzgan hisobotni ichki hisob bilan solishtirish, 5 kalendar kun ichida (O'RQ-1108, Soliq kodeksi 81-modda).
- Multi-tenant SaaS (umumiy baza + tenant_id + RLS), PostgreSQL; offline-first kassa
  (append-only event-log, 48 soat OFD chegarasi).
- Stack (2026-10-14, foydalanuvchi qarori): backend — **Python + FastAPI**; birinchi navbatda **veb**
  (back-office + veb-kassa); Android POS (**Kotlin**) — keyingi bosqich, hujjatlari hozirdan tayyorlanadi.
- AI: Claude API (Haiku 5.5 asosiy), `AiProvider` interfeysi; obuna/CLI faqat ishlab chiqishda.
- Majburiy davlat tizimlari: virtual kassa/OFD, e-faktura, e-TTN, Asl belgisi, MXIK, e-ishonchnoma, E-IMZO, soliq hisobotlari.

## Manbalar (avval o'qing)

1. `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` — yakuniy xulosa.
2. `research_notes/texnik/01…11` — modullar, kassa/OFD, e-faktura/to'lov, arxitektura, AI, raqobatchilar, hosting, soliq.
3. `research_notes/AI ERP startap Ozbekistonda/` — bozor tadqiqoti.
4. Asosiy hujjat (Claude Docs): https://claude.ai/code/artifact/e57e7cd7-1117-40a7-8af5-8154a8d22540 — ochilsa o'qing.

## Natija papkalari

| Papka | Mazmuni | Team |
|---|---|---|
| `spec/01-mahsulot/` | PRD: rollar, modullar bo'yicha talablar, biznes jarayonlar, ekranlar, AI funksiyalar, MVP chegarasi | Mahsulot |
| `spec/02-arxitektura/` | Tizim arxitekturasi, ma'lumotlar modeli, buxgalteriya provodkalari, integratsiyalar, offline sync, AI qatlami, xavfsizlik, backlog | Arxitektura |

## Qoidalar (barcha agentlar uchun)

- **Kod yozilmaydi** — faqat Markdown hujjatlar (mermaid diagrammalar mumkin).
- O'zbek tilida (lotin). Har fayl: "Asosiy xulosalar" (5-10 qator) → batafsil → "Ochiq savollar" → "Manbalar".
- Talab va raqamlar tadqiqot fayllaridan yoki URL manbadan olinadi; manbasiz raqam yo'q.
  Tadqiqotda yo'q narsa "taxmin" yoki "ochiq savol" deb aniq belgilanadi.
- Har kim faqat o'ziga berilgan faylga yozadi. `research_notes/` ga tegilmaydi.
