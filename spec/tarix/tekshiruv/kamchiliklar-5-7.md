# Kamchiliklar tekshiruvi — 5-7 bo'limlar (43-61 bandlar)

*2026-10-15 · Tekshiruvchi: Arxitektura auditi, status verifikatsiyasi*

---

## Jadvali

| # | Kamchilik (qisqa) | 08-dagi belgi | Haqiqiy holat | Dalil (fayl:qator + iqtibos) | Nima qoldi / kim yopadi |
|---|---|---|---|---|---|
| 43 | Huquqlar matritsasi tasdiqlanmagan | Ochiq savol | HAL QILINGAN | `15-xavfsizlik-va-audit.md` §2.1-2.2 (51-170q.): "5 tizim rol (Egasi, Menejer, Kassir, Omborchi, Buxgalter) uchun standart matritsa `02-rollar-va-ssenariylar.md` bilan izchil loyihalantirilgan; kod darajasidagi ruxsat (`permission_code`) + ixtiyoriy limit" + jadvali 66-170 qatorlar | Limit qiymatlari hali "taxmin, MVP oldidan biznes-qoida sifatida sozlanadi"; Mahsulot egasi bilan rasmiy tasdiqlash sessiyasi qoldi |
| 44 | Tenant onboarding/provisioning jarayoni | Ochiq savol | QISMAN | `15-xavfsizlik-va-audit.md` §1 (25-28q.): "Ro'yxatdan o'tish: telefon raqami → SMS OTP → do'kon nomi/faoliyat turi (US-M17-01)"; lekin standart hisob rejasi, rollar, MXIK katalogi avtomatik yaratilishi yo'q | Standart provisioning shabloni (hisob rejasi, rollar, MXIK katalogi) yozish kerak; Arxitektura + Biznes |
| 45 | Audit-log'ning aniq sxemasi | Ochiq savol | HAL QILINGAN | `15-xavfsizlik-va-audit.md` §6.1-6.3 (277-302q.): "`audit_log` (tenant_id, user_id, action, entity, entity_id, before JSONB, after JSONB, ip, device_id, at — `11-malumotlar-modeli.md`)" + 291-292 qatorlardagi "OAuth/autentifikatsiya voqealari (to'liq ro'yxat `14-autentifikatsiya-oauth2.md` §14'da)"; saqlash muddati "kamida buxgalteriya hujjatlari muddati (5 yil) bilan tenglashtiriladi" | Qonuniy minimal muddat (5 yil) qabul qilindi (O'RQ-404, 29-modda); tamper-evidence validatsiyasi — test kerak |
| 46 | AI-03 (OCR) chet el LLM API'ga yuboriladigan hujjat rasmlari | Ochiq savol | QISMAN | `15-xavfsizlik-va-audit.md` §5.2 (265-270q.): "Claude API'ga nima boradi... ba'zan mijoz ismi/mahsulot nomi kabi matn maydonlari (AI-05, AI-06, AI-03)" + "Minimallashtirish qoidasi: prompt faqat vazifaga kerakli maydonlarni o'z ichiga oladi"; PII masking "22-ai-qatlami.md" §7 (151-153q.): ixtiyoriy, standart yoqilmagan | ZRU-547 doirasining aniq tahlili (15/27-1-moddalari) va AI-03'da PII mask yoqilish talabi — Yurist |
| 47 | Backup/DR RPO/RTO maqsadlari | Ochiq savol | QISMAN | `15-xavfsizlik-va-audit.md` §7.1 (309-312q.): "RPO — bir necha daqiqa (**taxmin**)" + "`04-arxitektura-va-stack.md`, 8-bo'lim jadvali" va "RTO — belgilanmagan"; "saqlash muddati... 5 yil (buxgalteriya muddatiga mos)" | Aniq RPO (soatlar darajasida) va RTO (soat/kun) raqamlari tasdiqlanmagan; Arxitektura |
| 48 | Backup/restore test siklining o'zi | Ochiq savol | QISMAN | `15-xavfsizlik-va-audit.md` §7.2 (314-317q.): "Backup'dan tiklash muntazam **sinovdan o'tkazilishi** kerak (masalan choraklik, staging muhitida to'liq restore) — bu amaliyot manbada yo'q"; operatsion runbook mavjud emas | Staging muhitida choraklik restore testi jadval va playbook yozish kerak; Arxitektura |
| 49 | Karta to'lovi PCI-DSS talabi | Ochiq savol | QISMAN | `15-xavfsizlik-va-audit.md` §9.3 (359-361q.): "AIOS **hech qachon** to'liq karta raqami/CVV saqlamaydi... Click/Payme (JSON-RPC/REST API, merchant tokenlashtirilgan oqim) yoki bank POS-terminali orqali... bu amaliyotda PCI DSS qamrovini **minimal** qiladi — lekin manbada 'PCI' so'zi to'g'ridan-to'g'ri tilga olinmagan, bu xulosa **mantiqiy natija, taxmin**" | Acquiring bank/terminal ta'minotchisi bilan PCI qamrovi resmi tasdiqlanishi kerak; Arxitektura |
| 50 | Parol/PIN siyosati | Ochiq savol | QISMAN | `15-xavfsizlik-va-audit.md` §1.2 (32-36q.): "PIN — **1-4-6 raqam, **taxmin***" + "`14-autentifikatsiya-oauth2.md` §12'da to'liq" (qulfash siyosati + rate limit); parol — "argon2id" (29q.) | PIN uzunligi (4-6) taxmin; qulfash chegarasi (progressive bloklash) "OWASP ASVS L2 asosida, taxmin"; aniq raqamlar — Arxitektura |
| 51 | Shifrlash (at-rest, in-transit) standartlari | Ochiq savol | QISMAN | `15-xavfsizlik-va-audit.md` §4.2 (241-249q.): "Variantlar: (1) ilova darajasidagi envelope encryption (AES-256-GCM)... KEK — muhit o'zgaruvchisi/sir boshqaruv xizmatida (**taxmin**, UzCloud'da tayyor KMS borligi tasdiqlanmagan); (2) PostgreSQL `pgcrypto`; (3) UzCloud KMS-as-a-Service — rasmiy narx/sahifa tadqiqotda topilmadi — **agar yo'q bo'lsa, (1)dagi KEK saqlash joyi shunga ko'chiriladi**" | UzCloud KMS borligi rasmiy tasdiq kerak; aks holda Vault yoki boshqa KMS tanlovi — Arxitektura |
| 52 | Penetration test/xavfsizlik auditi rejasi | Ochiq savol | OCHIQ | `15-xavfsizlik-va-audit.md` §8 (326-340q.): "**Taxmin** — manbada yo'q, lekin davlat tizimlariga (OFD, soliq) ulanuvchi mahsulot uchun oqilona ehtiyot chorasi" + "Ustuvorlik: P2"; "Ishga tushirishdan oldin kamida bir marta mustaqil pentest — **taxmin** — manbada yo'q" | MVP oldidan pentest/xavfsizlik audit rejasi — Biznes; kim yopadi: independent pentest kompaniyasi |
| 53 | Xodim ishdan bo'shaganda huquqni real-time bekor qilish | Ochiq savol | QISMAN | `15-xavfsizlik-va-audit.md` §1.2 (36q.): "Qurilma bekor qilinganda unda kirgan xodimlarning PIN'i majburiy almashtiriladi (`16-offline-sync.md` §9)"; + `14-autentifikatsiya-oauth2.md` (foydalanuvchi qarori 2026-10-15, 7.bo'lim): "offline litsenziya tokeni (`valid_until = subscription_end + 24 soat`)" | PIN/sessiya muddati aniq, lekin offline POS'da eski token qancha vaqt amal qilib qolishi nazorat qilinishi kerak; Arxitektura (token refresh mexanizmi) |
| 54 | Hech qanday tasdiqlangan ishlash (performance) maqsadi | Ochiq savol | HAL QILINGAN | `25-nofunksional-talablar.md` §1 (20-33q.): "SLO jadvalida: shtrix-kod skanerlashdan qator qo'shilishigacha — <100ms, chekni yakunlash — <1s, API p95 o'qish — <300ms, yozuvchi — <800ms, AI-01 — <3s, offline chek OFD'ga — 48 soat (qonuniy), markirovka ko'chirish — 72 soat (qonuniy), davlat hisoboti tafovuti — 5 kun (qonuniy)" | Barcha raqamlar "taxmin, manbada topilmagani sababli"; pilot davrida telemetriya bilan tasdiqlanishi shart — Arxitektura |
| 55 | Fiskal modul (FM) uskuna ro'yxati tasdiqlanmagan | Ochiq savol | QISMAN | `25-nofunksional-talablar.md` §7.2 (132-144q.): "PAX A930, UZKASSA" — namuna sifatida; "AIOS qaysi uskuna bilan rasman integratsiya qilishini tanlamagan" | FM ta'minotchisi va chek printeri modeli rasmiy tanlov — Biznes + Arxitektura |
| 56 | Tarozi protokoli noma'lum | Ochiq savol | OCHIQ | `25-nofunksional-talablar.md` §7.3 (147-151q.): "Umumiy diapazon: 250 000–750 000+ so'm; **Aniq ulanish protokoli (masalan CAS/Shtrix-M) ochiq manbada topilmadi** — faqat 'Frontol/LiteBox bilan integratsiya' umumiy da'vosi bor" | Tarozi protokoli tadqiqoti; Uskuna tadqiqoti / vendor — kim yopadi: Texnik tadqiqot |
| 57 | Chekni ikki tilda chiqarish | Ochiq savol | QISMAN | `25-nofunksional-talablar.md` §8 (169-173q.): "Chekni ikki tilda (o'zbek/rus) chiqarish talabi **tasdiqlanmagan** — bu **ochiq savol/taxmin**" + "`06-ekranlar-umumiy.md`, Ochiq savol 1" | Soliq.uz/amaliyot bilan aniqlashtirish kerak; Mahsulot/Soliq integratsiyasi |
| 58 | Tizim sig'imi (capacity planning) belgilanmagan | Ochiq savol | QISMAN | `25-nofunksional-talablar.md` §3.1-3.2 (48-81q.): "Taxminiy o'sish jadvalida: birinchi 3 oy 20–50 tenant, 6-12 oy ~100, 18-24 oy ~1000; o'rtacha kassa/tenant 1–2 (Start/Biznes), 3+ (Pro); 100 tenant uchun infratuzilma — ~2 047 500 so'm/oy" | Barcha raqamlar "manbasiz, faqat birlik narxlar (UzCloud'dan) manbali"; 1000 tenant uchun "aniq raqam yo'q, keyingi moliyaviy rejalashtirish" — Arxitektura |
| 59 | AI eval-dataset minimal aniqlik chegarasi yo'q | Ochiq savol | QISMAN | `22-ai-qatlami.md` §8.1-8.2 (157-176q.): "Hajm: **50–100 holat/funksiya**; metrikalar: AI-01 — raqamli nazorat o'tish darajasi **100% talab qilinadi**; AI-03 — maydon darajasidagi aniqlik (precision per field)"; lekin "Manba: dastlabki to'plam qo'lda yoziladi (haqiqiy pilot ma'lumoti yo'q); pilotdan keyin haqiqiy so'rovlar qo'shiladi" | Minimal aniqlik chegara (masalan AI-03 OCR — 90% ishonch) "MVP pilotida sozlanadi" — Mahsulot + AI jamoasi; **Ochiq savol 1** (279q.) |
| 60 | Tenant boshiga LLM xarajat limiti siyosati | Ochiq savol | HAL QILINGAN | `22-ai-qatlami.md` §5 (118-130q.): "Har tenant uchun oylik token limiti — `plans.limits.ai_monthly_tokens`... Start: 500k, Biznes: 2M, Pro: 6M token; soft-block qilinadi — foydalanuvchiga 'bu oy uchun AI limiti tugadi' ko'rsatiladi, kassa/ombor to'liq ishlayveradi" + `11-malumotlar-modeli.md` jadvali | Limit qiymatlari "taxmin, unit-iqtisod hisobi bilan tasdiqlanishi shart"; overage siyosati "ochiq savol" — Arxitektura |
| 61 | AI xato/noaniq javob review jarayoni | Ochiq savol | QISMAN | `22-ai-qatlami.md` §8.4 (183-187q.): "Production'da har AI javobidan keyin foydalanuvchi fikr-mulohazasi yig'iladi (👍/👎 va 'tuzat' tugmasi); haftalik: pilot tenant(lar)dagi real `ai_requests`/`ai_feedback` ko'rib chiqiladi; birinchi 90 kunlik pilot maqsadi... AI-01 raqamli nazorat o'tish darajasi ≥99,9%" | Aniq maqsad/mezon foydalanuvchi tomonidan ko'riladigan guard_failed darajasi uchun belgilanmagan (3.2-bo'lim, "monitoring uchun hisoblanadi"); Arxitektura (monitoring) |

---

## Status shakli

- **HAL QILINGAN (Hujjatda bor, texnik tafsili bor)**: 43, 45, 54, 60
- **QISMAN (Qisman bor, qolgan qismi ochiq/taxmin)**: 44, 46, 47, 48, 49, 50, 51, 53, 55, 57, 58, 59, 61
- **OCHIQ (Hujjatda yo'q, hal qilishi shart)**: 52, 56
- **ESKIRGAN**: —

---

## Hollari summasi

| Status | Bandlar | Soni |
|---|---|---|
| HAL QILINGAN | 43, 45, 54, 60 | **4 ta** |
| QISMAN | 44, 46, 47, 48, 49, 50, 51, 53, 55, 57, 58, 59, 61 | **13 ta** |
| OCHIQ | 52, 56 | **2 ta** |
| **JAMI** | — | **19 ta** |

---

## OCHIQ bandlar (kim yopadi)

- **52 (Penetration test/xavfsizlik auditi rejasi)**: Biznes, independent pentest kompaniyasi — MVP oldidan
- **56 (Tarozi protokoli)**: Texnik tadqiqot, uskuna vendor — MVP boshlanishidan oldin

## QISMAN bandlar (nima qoldi, kim yopadi)

- **44**: Standart provisioning shabloni — Arxitektura + Biznes
- **46**: ZRU-547 aniq tahlili + PII mask yoqilish — Yurist + Arxitektura
- **47**: Aniq RPO/RTO raqamlari — Arxitektura
- **48**: Staging restore test playbook — Arxitektura
- **49**: PCI DSS resmi tasdiq — Acquiring bank + Arxitektura
- **50**: PIN uzunligi va qulfash chegarasi aniqlashtirish — Arxitektura
- **51**: UzCloud KMS borligi tasdiq yoki Vault tanlov — Arxitektura
- **53**: Offline token muddat mexanizmi — Arxitektura
- **55**: FM ta'minotchisi va uskuna modeli tanlov — Biznes + Arxitektura
- **57**: Chekni ikki tilda talab tasdiq — Mahsulot / Soliq.uz
- **58**: Capacity planning aniq raqamlari — Arxitektura (pilot ma'lumoti bilan)
- **59**: Eval-dataset minimal aniqlik chegara — Mahsulot + AI jamoasi
- **61**: Guard_failed monitoring mezon — Arxitektura

---

## Manbalar

- `spec/kod-uchun/15-xavfsizlik-va-audit.md` — multitenancy, huquqlar, audit, backup
- `spec/kod-uchun/25-nofunksional-talablar.md` — SLO, uskuna, sig'im, lokalizatsiya
- `spec/kod-uchun/22-ai-qatlami.md` — eval, budjet, review
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` (2026-10-15 foydalanuvchi qarori) — token, offline litsenziya
- `spec/kod-uchun/11-malumotlar-modeli.md` — audit_log, ai_requests, plans.limits
- `spec/kod-uchun/02-rollar-va-ssenariylar.md` — huquqlar matritsasi
- `spec/kod-uchun/09-ai-funksiyalar.md` — AI hukmlari
- `spec/kod-uchun/05-mvp-chegarasi.md` — tariflar, capacity maqsadi
- `research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md` — UzCloud, saqlash muddatlari
- `research_notes/texnik/05-ozbek-tilidagi-ai.md` — AI narxlar, lokalizatsiya qonuni
