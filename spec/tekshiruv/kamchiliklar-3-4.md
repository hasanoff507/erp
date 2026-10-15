# Kamchiliklar tahlili — 3 va 4-bo'limlar tekshiruvi

*2026-10-15 · Auditor: Spec arkitektura + 03-integratsiyalar.md + 04-offline-sync.md + 12-autentifikatsiya-oauth2.md va 00-qarorlar.md vs 08-kamchiliklar-tahlili.md*

---

## 3. Soliq integratsiyalari — haqiqiy holat

| # | Kamchilik (qisqa) | 08-dagi belgi | Haqiqiy holat | Dalil (fayl:qator/bo'lim + iqtibos) | Nima qoldi / kim yopadi |
|---|---|---|---|---|---|
| 22 | Sandbox/test muhitlari (OFD, CRPT, Didox, Faktura.uz, my.soliq.uz, Vakolat.uz, Click, Uzum) | Qisman (2026-10-14) | QISMAN | 03-integratsiyalar.md §1: "Faqat 3 tizimda to'liq ochiq...API hujjati va/yoki sandbox bor: Faktura.uz, Payme, E-IMZO. Qolgan 9 tasida hujjat yopiq" | OFD, CRPT, Didox, my.soliq.uz, Vakolat.uz, Click, Uzum uchun rasmiy murojaat/tekshiruv kerak. Hujjat: 12-taxminlar-va-murojaatlar.md |
| 23 | Virtual kassa registratsiya muddati va narxi | Muddat topildi | QISMAN | 03-integratsiyalar.md §1: "Muddat endi topildi: VMQ-943 4-ilova — 50 ish kunigacha (bosqichlar ketma-ket/parallelligi ochiq, VMQ-943 4-ilova). Narx hamon **ochiq savol**" | Sertifikatlash narxi topilishi kerak. Murojaat: Soliq qo'mitasi yoki VMQ boshqarmasi. P0 |
| 24 | CRPT Turon (Asl belgisi) API hujjatlari yopiq | Ochiq savol | OCHIQ | 03-integratsiyalar.md §4: "**Rasmiy, ochiq API texnik hujjati topilmadi** — `help.crpt-turon.uz` asosiy integratsiya bo'limlari **403 (kirish taqiqlangan)**; integrator ro'yxatidan o'tish shartlari noma'lum" | Rasmiy murojaat CRPT Turon'ga, muqobil olish (MoySklad/E-POS/Smartup proxy integratsiyasi, 12-taxminlar-va-murojaatlar.md band 2). Kim yopadi: texnik arxitektura |
| 25 | Offline markirovkalangan tovar sotuvi siyosati (ruxsat/taqiq) | Ochiq savol (4 ta spec faylida) | HAL QILINGAN | 04-offline-sync.md §4: "*(2026-10-15: foydalanuvchi qarori)* offline **sotish** siyosati endi aniq: narx qurilmada ma'lum bo'lsa ruxsat (CRPT tasdig'i internet qaytganda), bo'lmasa taqiq" | Yuridik tasdiq tavsiya etiladi (huquqshunos bilan). P0 |
| 26 | E-faktura operatori tanlovi (Didox vs Faktura.uz, ikkalasi) | Qilinmagan | OCHIQ | 03-integratsiyalar.md §2: "Didox API hujjat portali (`api-docs.didox.uz`) **login talab qiladi**, ochiq o'qib bo'lmadi. Faqat norasmiy npm SDK. Sandbox **topilmadi**" | Faqat Faktura.uz API'si ochiq; Didox bilan hamkorlik yo'li tanlash kerak yoki Faktura.uz'da boshlash. Kim yopadi: mahsulot/arxitektura qarori |
| 27 | e-TTN majburi ekanligini ichki filiallararo ko'chirishda | Aniqlanmagan | OCHIQ | 03-integratsiyalar.md §3: "ichki ko'chirish uchun majburiyligi **ochiq savol** (`spec/01-mahsulot/03-biznes-jarayonlar.md`, Ochiq savol 5)" | Soliq.uz bilan rasmiy aniqlashtirish kerak: ichki ko'chirish e-TTN talab qiladimi. Kim yopadi: yurist/soliq.uz aloqasi |
| 28 | E-ishonchnoma (Vakolat.uz) integratsiyasi API | API yo'q, noaniq | OCHIQ | 03-integratsiyalar.md §6: "**API hujjati topilmadi** — integratsiya usuli (REST, qanday autentifikatsiya) **ochiq savol**. Majburiy 2026-01-01'dan (VM 825-son)" | Vakolat.uz bilan rasmiy murojaat, API mavjudligini/usulini taniqlash. Kim yopadi: rasmiy murojaat |
| 29 | my.soliq.uz davlat hisobotini olish (API yo'q, qo'lda yuklash) | Rasmiy API yo'q | OCHIQ | 03-integratsiyalar.md §8: "**Rasmiy dasturiy (API) o'qish yo'li topilmadi** — bu `00-xulosa-va-ochiq-savollar.md`, `14-tekshiruv-xulosasi.md` va `12-taxminlar-va-murojaatlar.md`ning barchasida takrorlangan eng muhim ochiq savol/blokker" | my.soliq.uz qo'llab-quvvatlash xizmatiga rasmiy murojaat, yoki yarim-avtomatik yo'l (E-IMZO orqali). P0 |
| 30 | Davlat hisoboti document darajasida (har chek) vs yig'ma summa | Hali tasdiqlanmagan | QISMAN | 03-integratsiyalar.md §8: "MVP — faylga asoslangan 'adapter'" — qo'lda import bilan boshlanadi. Hujjat darajasida/yig'ma suncha qaror yo'q | Solishtirish motori arxitekturasi hujjat yoki yig'ma darajada qaror boshqa integratsiya talabiga bog'liq. Kim yopadi: my.soliq.uz aloqasi → arxitektura |
| 31 | "5 ish kuni" → "5 taqvim kuni", e'tiroz kanali | 5 taqvim kun qaror qilindi | QISMAN | 03-integratsiyalar.md §8: "**5 kalendar kun** (min(e'lon+5 kun, qonuniy topshirish muddati))" va 04-offline-sync.md §6: "Soliq kodeksi 81-moddasi, O'RQ-1108". Lekin e'tiroz/tuzatish yuborish **kanali va shakli** aniq emas | E'tiroz kanali (электрондалди/qo'lda, my.soliq.uz'dagi forma) aniqlanishi kerak. Kim yopadi: mahsulot/soliq aloqasi |
| 32 | QR/Click/Payme chekni kim chiqarishi (to'lov tizimi vs merchant) | Ziddiyatli talqin | OCHIQ | 03-integratsiyalar.md §6: "Do'kon QR to'lovlari... chiquvchi so'rov... **kredensial va tenant kontekst butunlay ajratilgan**" lekin huquqiy javobgarlik aniq emas | Noorasmiy tanqid: odatda terminal to'lov ma'lumotini ushlaydi, AIOS faqat natija oladi. Lekin rasmiy aniqlashtirish kerak. Kim yopadi: yurist/acquiring bank aloqasi |
| 33 | Retry/idempotentlik (outbox pattern) | Asosan hal qilindi | QISMAN | 03-integratsiyalar.md §0: "Outbox/navbat naqshi (`outbox_jobs`, 2-bo'lim), idempotentlik kaliti (client_event_id/provider_tx_id). Qayta urinish siyosati eksponensial backoff + jitter". Lekin **circuit-breaker faqat AI qatlami uchun** aniqlangan, davlat integratsiyalari uchun yo'q | Circuit-breaker, backpressure, timeout siyosati davlat integratsiyalari uchun yozilishi kerak. Kim yopadi: arxitektura/integratsiya hujjati |
| 34 | Har integratsiya uchun xato kodlari katalogi | To'liq emas | QISMAN | 03-integratsiyalar.md §1: "masalan FM xato kodi 704031 — bitta misol topilgan" | OFD, Didox, Faktura.uz, Payme, CRPT, e-TTN uchun xato katalogi ixcham qo'shilishi kerak. Kim yopadi: integrator xatolarini yig'ish (rasmiy hujjatlar orqali) |
| 35 | Sertifikatlash (ЗРУ-764) — SaaS'ga tegishlimi | Hali ochiq | OCHIQ | 03-integratsiyalar.md §1: "Sertifikatlash (ЗРУ-764) xususiy SaaS'ga tegishli-tegishli emasligi hamon ochiq — bu MVP byudjeti/jadvaliga eng katta ta'sirli noaniqlik" | **Zudlik bilan** csec.uz'ga rasmiy murojaat (Xat 3, 12-taxminlar-va-murojaatlar.md). P0 — javob olinmasa MVP sana suradi |

---

## 4. Offline-first POS — haqiqiy holat

| # | Kamchilik (qisqa) | 08-dagi belgi | Haqiqiy holat | Dalil (fayl:qator/bo'lim + iqtibos) | Nima qoldi / kim yopadi |
|---|---|---|---|---|---|
| 36 | 48 soat tugaganida yangi sotuv bloklash yoki ogohlash | Huquqiy qaror yo'q | QISMAN + foydalanuvchi qarori | 04-offline-sync.md §6: "48 soatda yangi sotuvni bloklash — **ochiq savol**: qonun matnida faqat 'chek 48 soat ichida yetib borishi zarur'... yangi sotuvni to'xtatish talabi **topilmadi**. **Taklif**: yangi sotuvni **bloklamaslik**... (1) audit_log'ga qat'iy huquqiy-xavf yozuvi, (2) Egasiga Telegram orqali zudlik bilan xabar, (3) back-office'da doimiy ko'rinadigan 'huquqiy xavf' bayrog'i". 2026-10-15 foydalanuvchi qarori: **obuna muddati** 24 soatga o'tgach kassa **qattiq to'xtaydi** (12-autentifikatsiya-oauth2.md §16) | 48 soat fiskal muddati + 24 soat obuna imtiyozi **ikki mustaqil muddat**. Fiskal 48 saod: taklif bo'yicha ishlash. Obuna 24 soat: hal qilindi. Kim yopadi: yakuniy huquqiy maslahat (obuna qat'i to'xtatish tasdiq) |
| 37 | Offline paytda karta terminali (mustaqil aloqa) | Aniq emas | OCHIQ | 04-offline-sync.md: Karta terminali offline xatti-harakati belgilanmagan | Acquiring bank/terminal ta'minotchisi bilan aniqlashtirish (terminal o'zining simkartasi bor-yo'qligi, offline rejimi). Kim yopadi: acquiring bank aloqasi |
| 38 | Overselling (manfiy balans konflikt hal qilish) | Hal qilindi (2026-10-14) | HAL QILINGAN | 04-offline-sync.md §5: "Ombor qoldig'ida overselling... Sotuv **ruxsat etiladi**; qoldiq manfiy bo'lishi mumkin, `stock_balances`ga manfiy qiymat yoziladi, BO-03'da '⚠ manfiy qoldiq' belgisi" | Malumotlar modeli + UI ushbu qarorni ko'rsatadi. Hal qilindi |
| 39 | Nasiya limitining offline parallel oshishi (ikki qurilma bir mijozga) | Server qayta tekshiradi | QISMAN | 04-offline-sync.md §5: "Qarz limiti offline oshib ketgan \| Sotuv **ruxsat etiladi** (allaqachon bo'lib o'tgan); server qayta tekshiradi, `limit_exceeded=true` bayrog'i qo'yiladi, Egasi/Menejerga M18 orqali bildirishnoma" | Faqat ruxsat etish qaror bor; ortiqcha summani "kim yopadi" (qayta o'rin, chegirma bekor, qarz qayta hisoblash) — UI/biznes qoida yo'q. Kim yopadi: mahsulot biznes qaror |
| 40 | POS lokal saqlash hajmi (necha kun offline) | Hisoblanmagan | QISMAN | 04-offline-sync.md §10: "Outbox voqealari — `accepted`/`duplicate` natija olgandan keyin... **taxmin: 7 kun** xavfsizlik buferi bilan saqlanadi"; §5 outbox muddati — "Sotuv/chek tarixi... **taxmin: 90 kunlik** aylanma oyna" | Aniq hajm metrikalari (GB, qo'lda tozalash) va eskirgan ma'lumotni arxivlash siyosati. Kim yopadi: arxitektura (lokal sig'im hisob-kitobi) |
| 41 | Sinxronlash backpressure (bir martalik katta push, server yuklanishi) | Aniq emas | OCHIQ | 04-offline-sync.md: Partiya hajmi "taxmin — 50 voqea/so'rov", lekin server **backpressure/throttle siyosati yo'q** | `/sync/push` backoff, `429 Too Many Requests`, rate-limit siyosati yozilishi kerak (katta uzilishdan keyingi zarur sotuv qo'llab-quvvatlanishi uchun). Kim yopadi: arxitektura |
| 42 | Markirovka offline: audit-log va "tekshirilmagan" belgisi | Spetsifikatsiyalanmagan | QISMAN | 04-offline-sync.md §7: "Chekka '⚠ markirovka tekshirilmagan, internet qaytganda tasdiqlanadi' belgisi"; 03-integratsiyalar.md §4: "offline kod `marking_codes`ga (status kutilmoqda) va mahalliy event-logga yoziladi" | Aniq: audit_log qaysi voqea/maydonlari (ki, "kode offline kiritildi"), UI "tekshirilmagan kod" holati, qayd yozuvi format. Kim yopadi: arxitektura (marking audit specification) |

---

## Xulosa (status bo'yicha)

### HAL QILINGAN (hal qilindi, faqat referensiya kerak)
- Band 25 (offline markirovka sotuvi) — foydalanuvchi qarori 2026-10-15
- Band 38 (overselling konflikt) — model + UI bor

### QISMAN (qisman hal, nimalar qoldi)
- Band 22 (sandbox'lar) — 5 ta tizim uchun tekshiruv kerak (OFD, CRPT, Didox, my.soliq.uz, Vakolat.uz)
- Band 23 (VM narxi) — narx topilishi kerak
- Band 26 (e-faktura operator) — Didox vs Faktura.uz tanlovni tasdig'i
- Band 30 (davlat hisoboti hujjat/yig'ma) — solishtirish motorining arquitektura qaror
- Band 31 (e'tiroz kanali) — my.soliq.uz forma/kanal aniqlanishi
- Band 33 (circuit-breaker) — davlat API'lari uchun
- Band 34 (xato katalogi) — integrator xatolarini yig'ish
- Band 36 (48 soat fiskal) — taklif bo'yicha ishlash (ogohlash + audit, bloklanish emas)
- Band 39 (nasiya limit ortiqcha summasi) — qayta hisoblash qaror
- Band 40 (lokal saqlash hajmi) — aniq qiymatlar (GB, tozalash siyosati)
- Band 42 (markirovka audit-log) — exact format va UI state

### OCHIQ (hal qiluvchi qaror yoki murojaat kerak)
- Band 24 (CRPT API) — rasmiy murojaat yoki muqobil integrator
- Band 27 (e-TTN ichki ko'chirish) — soliq.uz aniqlashtirish
- Band 28 (Vakolat.uz API) — rasmiy murojaat
- Band 29 (my.soliq.uz API) — rasmiy murojaat (eng muhim blokker)
- Band 32 (QR/Click chek javobgarligi) — yurist aniqlashtirish
- Band 35 (ЗРУ-764 sertifikatlash) — csec.uz zudlik bilan murojaat (P0)
- Band 37 (karta terminali offline) — acquiring bank aniqlashtirish
- Band 41 (backpressure) — arxitektura

### ESKIRGAN
Yo'q — barcha bandlar hali amal qiladi.

---

## OCHIQ / QISMAN band raqamlari

**OCHIQ**: 24, 27, 28, 29, 32, 35, 37, 41  
**QISMAN**: 22, 23, 26, 30, 31, 33, 34, 36, 39, 40, 42

**Jami**: 10 ta OCHIQ, 11 ta QISMAN, 2 ta HAL QILINGAN
