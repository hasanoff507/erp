# Qabul-1: review topilmalari bo'yicha qaror (fakt-tekshiruvi)

Sana: 2026-10-14. Har bir topilma spec matni va birlamchi manba (lex.uz, developer.uzumbank.uz) bilan mustaqil tekshirildi. lex.uz barcha hujjatlar uchun ochildi; Soliq kodeksi joriy tahrirda o'qildi.

Natija: 2 QABUL (#1, #6), 3 QISMAN (#2, #4, #7), 2 RAD (#3, #5).

---

## 1 — QABUL

**Dalil**: https://lex.uz/uz/docs/-7897630 (PF-246, 10.12.2025), 3-band (b): "…banklarda generatsiya qilingan yagona QR kod orqali… 2026-yil 1-iyuldan boshlab: (i) barcha savdo va xizmat koʻrsatish sohasidagi **yuridik shaxslarda** yagona QR kodli toʻlov tizimi orqali toʻlovlarni qabul qilish ham majburiy… (ii) yagona QR kodlardan foydalanilmayotganligi savdo qoidalarini buzish deb hisoblanadi."
- Farmonda Click, Payme yoki Uzum nomi yo'q.
- Faqat yuridik shaxslarga taalluqli; YTT'lar (yakka tartibdagi tadbirkorlar) bu bandda tilga olinmagan.
- "ham" so'zi: yagona QR boshqa to'lov usullari bilan **bir qatorda** majburiy, ularning o'rniga emas.

**Fayl**: `spec/kod-uchun/21-integratsiyalar.md`
- 459-qator. Eski: `(M01, to'lov turi `click`/`payme`/`uzum`), **2026-07-01'dan to'liq majburiy** (PF-246-son);`
  Yangi: `(M01, to'lov turi `click`/`payme`/`uzum` — ixtiyoriy kanallar). Alohida: 2026-07-01'dan barcha savdo va xizmat ko'rsatuvchi **yuridik shaxslar** uchun banklarda generatsiya qilingan **yagona QR kod** orqali to'lov qabul qilish ham majburiy, undan foydalanmaslik savdo qoidalarini buzish hisoblanadi (PF-246-son, 10.12.2025, 3-band "b"); PF-246 Click/Payme/Uzum'ni nomma-nom majburiy qilmaydi, YTT'lar bu bandda tilga olinmagan;`
- 494-qator. Eski: `QR to'lov qabul qilish 2026-07-01'dan to'liq majburiy (PF-246-son)`
  Yangi: `yagona (bank) QR kod orqali to'lov qabul qilish yuridik shaxslar uchun 2026-07-01'dan majburiy (PF-246-son, 3-band "b")`
- 684-qator. Eski: `PF-246-son (QR to'lov majburiyligi)`
  Yangi: `PF-246-son (yagona QR kod orqali to'lov qabul qilish majburiyligi, yuridik shaxslar)`

## 2 — QISMAN (467-modda to'g'ri; "4% standart" chakana savdo uchun to'liq emas)

**Dalil**: https://lex.uz/docs/4674902 (Soliq kodeksi). Sarlavha: "XX BO'LIM… 66-bob… 467-modda. Soliq stavkalari". Stavkalar jadvali O'RQ-1108 tahririda, 2026-01-01'dan kuchda:

| Qator | To'lovchilar | Stavka |
|---|---|---|
| 1 | Barcha tarmoqlar, 2–5-qatorlardan tashqari | 4% |
| 2.1 | Chakana savdo, aholisi 100 ming+ shaharlar | 4% |
| 2.1 | Chakana savdo, boshqa aholi punktlari | 2% |
| 2.1 | Chakana savdo, borish qiyin va tog'li tumanlar | 1% |
| 2.2 | Tamaki | 4% |
| 5 | YTT va o'zini o'zi band qilganlar | 1% |

- 1 mlrd so'm chegarasi **461-moddada** (aylanma solig'i to'lovchisi kim), 467-moddada emas.
- Chakana POS mahsuloti uchun bu muhim: stavka do'kon qayerda joylashganiga bog'liq.

**Fayl**: `spec/kod-uchun/13-provodka-qoidalari.md`
- 26-qator. Eski: `(4% standart 2026, ba'zi holatlarda 1% — O'RQ-1108)`
  Yangi: `(Soliq kodeksi 467-moddasi, O'RQ-1108 tahririda: umumiy 4%; chakana savdo — 100 ming+ aholili shaharda 4%, boshqa aholi punktida 2%, borish qiyin/tog'li tumanda 1%; YTT va o'zini o'zi band qilganlar 1%)`
- 272-qator. Eski: `2026-yil standart stavka **4%**` dan `**Soliq kodeksining aniq modda raqami bu tadqiqotda topilmadi, ochiq savol** (pastda).` gacha
  Yangi: `2026-yil stavkalari — Soliq kodeksi **467-moddasi** (66-bob; O'RQ-1108 tahririda, 2026-01-01'dan): umumiy **4%**; chakana savdo joylashuvga qarab **4% / 2% / 1%** (100 ming+ aholili shahar / boshqa aholi punkti / borish qiyin va tog'li tuman), tamaki **4%**; YTT va o'zini o'zi band qilganlar **1%**. Aylanma solig'i to'lovchisi bo'lish chegarasi (jami daromad 1 mlrd so'mgacha) — 461-modda ([lex.uz/docs/4674902](https://lex.uz/docs/4674902)). Shuning uchun tenant/filial sozlamasida "aholi punkti toifasi" maydoni kerak.`
- 318-qator: 3-ochiq savol o'chiriladi. 17-qatordagi ochiq savol (9-band) ham shu tarzda yopiladi.

## 3 — RAD (mavjud iqtiboslar to'g'ri; reviewer tuzatishi spec'ni yomonlashtiradi)

**Dalil**: https://lex.uz/docs/4674902
- **84-modda** "Soliq hisobotini saqlash muddati": "…ushbu hisobot taqdim etilgan yildan keyin kamida uch yil saqlashi shart" (O'RQ-891, 2024-01-01'dan).
- **22-modda**, 1-qism, 7-xatboshi: "…kalendar yildan keyingi uch yil mobaynida but saqlanishini ta'minlashi".
- **88-modda** — soliq majburiyati bo'yicha 3 yillik da'vo muddati. Saqlash qoidasi emas, lekin qo'shish foydali.
- 270- va 306-moddalarda saqlash qoidasi yo'q. "13 yil" da'vosini ulardan tasdiqlab bo'lmadi.

**Fayl**: `spec/kod-uchun/25-nofunksional-talablar.md`, 193-qator.
- Eski: `Soliq kodeksi, 22/84/270/306-moddalar — qonuniy, qisman ikkinchi darajali manba orqali`
- Yangi: `Soliq kodeksi 22-modda (1-qism, 7-xatboshi) va 84-modda (saqlash, kamida 3 yil), 88-modda (3 yillik da'vo muddati; 84-moddaning 2-qismidagi shartli imtiyozlarda uzayadi) — birlamchi manba lex.uz/docs/4674902. "13 yilgacha" — tasdiqlanmagan (270/306-moddalarda saqlash qoidasi yo'q)`

## 4 — QISMAN

**Dalil**:
- https://developer.uzumbank.uz/checkout (Uzum Checkout): "Проведите тестовую интеграцию используя тестовую среду и тестовые карты." "Тестирование" bo'limida test kartalari: HUMO 9860 0901 0121 9724, UzCard 8600 3129 2957 7175, 3-DS 777777. API kalitni Uzum beradi.
- https://developer.uzumbank.uz/merchant (Merchant API, Uzum Bank ilovasi orqali vebxuk oqimi): test muhiti yoki sandbox haqida hech narsa yo'q.
- Payment Hub (BaaS) uchun alohida test muhiti bor (`topup.ub.ufintech.uz`, test kredensiallari Uzum Bank menejeridan), lekin bu merchant ekvayringi emas.

**Fayl**: `spec/kod-uchun/21-integratsiyalar.md`, 468-qator. Eski: `Sandbox **topilmadi**.`
Yangi: `Test muhiti: **Uzum Checkout** uchun rasmiy test muhiti va test kartalari bor (HUMO/UzCard, 3-DS 777777; API kalit Uzum tomonidan beriladi — developer.uzumbank.uz/checkout, "Тестирование"); **Merchant API** (ilova orqali, vebxuk) hujjatida sandbox ko'rsatilmagan — Uzum menejeridan so'raladi.`

## 5 — RAD (xato yo'q)

**Dalil**: https://lex.uz/docs/-4890446
- Matnda: "Toshkent sh., 2020-yil 28-may, 24-son… Oʻzbekiston Respublikasi moliya vazirining 2020-yil 28-maydagi 24-son buyrugʻiga ILOVA". lex.uz sarlavhasida: "30.06.2020 yilda ro'yxatdan o'tgan, ro'yxat raqami 3259".
- Demak 28.05.2020 — buyruq sanasi, 30.06.2020 — Adliya vazirligida ro'yxatdan o'tish sanasi. Spec ularni to'g'ri juftlagan.
- 62-band identifikatsiyalangan tannarx / AVECO / FIFO'ni sanab o'tadi.

Ixtiyoriy aniqlik, 217-qator. Eski: `buyrug'i №24, 28.05.2020,`
Yangi: `buyrug'i №24, 28.05.2020, AV 30.06.2020 №3259 bilan ro'yxatdan o'tgan,`

## 6 — QABUL

**Dalil**: https://lex.uz/docs/8012407 (VMQ 23-son, 23.01.2026).
- 72 soat qoidasi faqat **1-ilovada** — "…tajriba loyihasini amalga oshirish tartibi to'g'risida NIZOM": "Mahsulotlarga egalik huquqi o'tgandan so'ng 72 (yetmish ikki) soatdan ko'p bo'lmagan muddatda…". U "tajriba loyihasi ishtirokchilari"ga tegishli; qarorning 1-bandiga ko'ra pilot o'simlik yog'i ("o'simlik yog'i") uchun.
- 4-banddagi 2026-07-01'dan avtomatlashtirish qoidalari (e-faktura tekshiruvi, kassa cheki) umumiy, faqat pilot uchun emas.

**Fayl**: `spec/kod-uchun/21-integratsiyalar.md`, 271-qator. Eski: `ko'chirish **72 soat** (23-son qaror, 2026-01-23);`
Yangi: `ko'chirish **72 soat** — faqat tajriba loyihasi ishtirokchilari uchun (VMQ 23-son, 23.01.2026, 1-ilova Nizom; hozircha o'simlik yog'i pilot loyihasi), umumiy majburiy muddat sifatida tasdiqlanmagan;`
264-qator (`72 soat` oynasida) ichki siyosat sifatida qolishi mumkin, lekin `(pilot normasi, ichki siyosat sifatida qabul qilindi)` qo'shilsin.

## 7 — QISMAN (natija reviewer aytganidan ham jiddiyroq)

**Dalil**:
- https://lex.uz/ru/docs/-90762 — 279-I'ning 1996-yilgi tahriri. lex.uz o'zi qayd etadi: "…2016-yil 13-apreldagi OʻRQ-404-sonli Qonuniga muvofiq yangi tahrirda qabul qilingan". Undagi 23-modda ("kamida uch yil") eski matn.
- Amaldagi "Buxgalteriya hisobi to'g'risida"gi Qonun — O'RQ-404, 13.04.2016: https://lex.uz/docs/-2931253 (rus tilida: https://lex.uz/docs/2931251). Uning **29-moddasi** (O'RQ-683 tahririda, 21.04.2021): "…qonunchilikda belgilangan muddatlar mobaynida, biroq hisobot yilidan keyin **kamida besh yil** buxgalteriya hisobi subyekti tomonidan saqlanadi."
- Demak qoida — kamida 5 yil, O'RQ-404 29-moddasi bo'yicha; 279-I / 23-modda iqtibosi olib tashlanishi kerak.

**Almashtirishlar**:
- `25-nofunksional-talablar.md`, 192-qator. Eski: `**Kamida 3 yil** | Buxgalteriya hisobi to'g'risidagi qonun, 279-I-son, 23-modda — qonuniy, manbali (`07-fayl`, 3.3-bo'lim)`
  Yangi: `**Kamida 5 yil** (hisobot yilidan keyin) | "Buxgalteriya hisobi to'g'risida"gi Qonun (O'RQ-404, 13.04.2016, yangi tahrir), 29-modda (O'RQ-683 tahririda) — birlamchi manba [lex.uz/docs/-2931253](https://lex.uz/docs/-2931253)`
- Shu fayl, 13-qator. Eski: `buxgalteriya hujjatlari kamida **3 yil** (Buxgalteriya hisobi to'g'risidagi qonun, 23-modda)`
  Yangi: `buxgalteriya hujjatlari hisobot yilidan keyin kamida **5 yil** (Buxgalteriya hisobi to'g'risidagi qonun, O'RQ-404, 29-modda)`
- Shu fayl, 194-qator (audit_log) va 196-qator (arxiv backup). Eski: `**Kamida 3 yil**` / `**≥ 3 yil**`
  Yangi: `**Kamida 5 yil**` / `**≥ 5 yil**`
- `15-xavfsizlik-va-audit.md`, 12-, 268- va 278-qatorlar. Buxgalteriya hujjatlari / audit_log / arxiv backup uchun "3 yil" deyilgan har bir joy, "Buxgalteriya hisobi to'g'risidagi qonun 23-modda" iqtibosi bilan birga, `5 yil` + `O'RQ-404, 29-modda` ga almashtiriladi.
- `21-integratsiyalar.md`, 235-qator (`5 yil saqlash talabi (tasdiqlanmagan)`) endi mos keladi. Shunday yozilishi mumkin: `5 yil saqlash (buxgalteriya hujjati sifatida — O'RQ-404, 29-modda)`.
- Soliq hujjatlari 3 yil bo'lib qoladi (Soliq kodeksi 84-modda). Tizimning saqlash sozlamasini qat'iyroq 5 yillik qoida belgilaydi.

Xuddi shu iqtibos tadqiqot eslatmasida ham bo'lishi mumkin: `research_notes/.../07-hosting-lokalizatsiya-xavfsizlik.md` (3.3-bo'lim). U ochilmadi; tuzatishlar kiritilganda tekshirilsin.

---

## Mahsulot ta'siri

### (a) Yagona QR (UzQR, bank) — M01 to'lov usuli

**Asos**: PF-246-son, 10.12.2025, 3-band "b" (https://lex.uz/uz/docs/-7897630) — 2026-07-01'dan barcha savdo va xizmat ko'rsatuvchi **yuridik shaxslar** uchun banklarda generatsiya qilingan yagona QR kod orqali to'lov qabul qilish majburiy; foydalanmaslik — savdo qoidalarini buzish.

**1. `spec/kod-uchun/03-modullar-talablari.md`, M01:**

- US-M01-01, 2-mezon. Eski: `When kassir to'lovni tanlaydi (naqd/karta/Payme/Click/Uzum QR yoki aralash)`
  Yangi: `When kassir to'lovni tanlaydi (naqd/karta/yagona QR (UzQR, bank)/Payme/Click/Uzum yoki aralash)`

- US-M01-04 dan keyin yangi hikoya qo'shilsin:

```
**US-M01-05**: Kassir sifatida yuridik shaxs bo'lgan do'konda mijozdan bank tomonidan generatsiya qilingan yagona QR kod (UzQR) orqali to'lov qabul qilishni istayman, chunki 2026-07-01'dan bu majburiy (PF-246-son, 10.12.2025, 3-band "b").
- Given tenant yuridik shaxs va filialga bank tomonidan berilgan yagona QR (statik yoki dinamik) ulangan, When kassir to'lov usuli sifatida "Yagona QR (UzQR)"ni tanlaydi, Then chek summasi bilan QR ko'rsatiladi (dinamik QR bo'lsa) yoki statik QR bo'yicha to'lov kutiladi va bank tasdig'i kelgach chek yakunlanadi.
- Given tenant yuridik shaxs va 2026-07-01 yoki undan keyingi sana, When filialda yagona QR sozlanmagan, Then tizim Egasi va kassirga "Yagona QR ulanmagan — savdo qoidalarini buzish xavfi" ogohlantirishini ko'rsatadi (sotuvni bloklamaydi).
- Given tenant YTT (yakka tartibdagi tadbirkor), When sozlamalar ochiladi, Then yagona QR ixtiyoriy deb ko'rsatiladi (PF-246 3-band "b" faqat yuridik shaxslarni nomlaydi).
- Yagona QR Click/Payme/Uzum'ning o'rnini bosmaydi: ular ixtiyoriy kanal sifatida qoladi ("ham majburiy").
```

- "Davlat tizimlari bog'liqligi" bo'limi. Eski: `2026-07-01'dan QR to'lov qabul qilish to'liq majburiy (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 4-band).`
  Yangi: `2026-07-01'dan yuridik shaxslar uchun bank tomonidan generatsiya qilingan yagona QR kod (UzQR) orqali to'lov qabul qilish majburiy (PF-246-son, 10.12.2025, 3-band "b", [lex.uz/uz/docs/-7897630](https://lex.uz/uz/docs/-7897630)); Click/Payme/Uzum — ixtiyoriy kanallar.`

- "Chekka holatlar" ga qo'shilsin: `- Yagona QR to'lovi bank tasdig'i kelmay qolsa (internet uzilishi yoki to'lov kechikishi) — chek "to'lov kutilmoqda" holatida qoladi, kassir boshqa to'lov usuliga o'tishi yoki bekor qilishi mumkin; ikki marta to'lov tushishining oldini olish uchun provider_tx_id bo'yicha idempotentlik.`

**2. `spec/kod-uchun/11-malumotlar-modeli.md`, 78-qator (`sales` → `sale_payments`):**
- Eski: `` `sale_payments` (method: `cash`/`card`/`click`/`payme`/`uzum`/`debt`, amount, provider_tx_id) ``
- Yangi: `` `sale_payments` (method: `cash`/`card`/`uzqr`/`click`/`payme`/`uzum`/`debt`, amount, provider_tx_id, qr_type: `static`/`dynamic`/null — `uzqr` = bank tomonidan generatsiya qilingan yagona QR, PF-246 bo'yicha yuridik shaxslar uchun 2026-07-01'dan majburiy) ``

**Ochiq savol (tasdiqlanmagan)**: UzQR'ni banklar qanday API/vebxuk orqali tasdiqlashi va Markaziy bank yagona QR standarti texnik hujjati — bu tekshiruvda topilmadi; `12-taxminlar-va-murojaatlar.md` ga savol sifatida qo'shish tavsiya etiladi.

### (b) Filial sozlamasi "aholi punkti toifasi" — aylanma solig'i stavkasi

**Asos**: Soliq kodeksi 467-moddasi, O'RQ-1108 tahririda, 2026-01-01'dan (https://lex.uz/docs/4674902): chakana savdo — 100 ming+ aholili shaharda 4%, boshqa aholi punktida 2%, borish qiyin va tog'li tumanda 1%; tamaki 4% (joydan qat'i nazar); boshqa tarmoqlar 4%; YTT va o'zini o'zi band qilganlar 1%. 468-modda — "Alohida-alohida hisob yuritish" (turli stavkali faoliyat uchun alohida hisob; batafsil matni bu tekshiruvda o'qilmadi).

**1. `spec/kod-uchun/11-malumotlar-modeli.md`, 43-qator (`branches`):**
- Eski: `` | `branches` | tenant_id, name, address, is_default | Filial (M14) | ``
- Yangi: `` | `branches` | tenant_id, name, address, is_default, settlement_category (`city_100k_plus`/`other`/`remote_mountain`), activity_type (`retail`/`other`) | Filial (M14). `settlement_category` + `activity_type` aylanma solig'i stavkasini aniqlaydi (Soliq kodeksi 467-modda: chakana 4% / 2% / 1%; tamaki savdosi har doim 4%; boshqa faoliyat 4%; YTT/o'zini o'zi band qilgan 1% — tenant darajasida). Stavka o'zgarishi tarixini saqlash uchun `branch_tax_settings(branch_id, valid_from, settlement_category, activity_type)` | ``

**2. `spec/kod-uchun/03-modullar-talablari.md`, M14 — US-M14-03 dan keyin yangi hikoya:**

```
**US-M14-04**: Egasi sifatida har bir filial uchun "aholi punkti toifasi"ni belgilashni istayman, chunki chakana savdoda aylanma solig'i stavkasi joylashuvga bog'liq (Soliq kodeksi 467-modda, O'RQ-1108 tahririda, 2026-01-01'dan).
- Given yangi filial yaratilmoqda yoki tahrirlanmoqda, When Egasi "aholi punkti toifasi"ni tanlaydi (Shahar, aholisi 100 ming+ / Boshqa aholi punkti / Borish qiyin yoki tog'li tuman), Then filialning chakana savdo aylanmasiga mos stavka (4% / 2% / 1%) qo'llanadi.
- Given toifa tanlanmagan, When filial saqlanadi, Then standart qiymat "Shahar, 100 ming+" (4%, eng ehtiyotkor) qo'yiladi va Egasiga tekshirish eslatmasi ko'rsatiladi.
- Given toifa o'zgartirildi, When saqlanadi, Then yangi stavka faqat `valid_from` sanasidan boshlab qo'llanadi, oldingi davrlar qayta hisoblanmaydi.
```

- M14 "Chekka holatlar" dagi qator. Eski: `- Bir xil MXIK/QQS stavkasi barcha filiallarda bir xil bo'lishi (farqlanishi mumkin emas).`
  Yangi: `- Bir xil MXIK/QQS stavkasi barcha filiallarda bir xil bo'lishi (farqlanishi mumkin emas). **Lekin aylanma solig'i stavkasi filiallar bo'yicha farq qilishi mumkin** (467-modda: chakana savdo joylashuvga qarab 4% / 2% / 1%) — turli toifadagi filiallari bor tenant uchun aylanma filial bo'yicha alohida hisoblanadi (468-modda "Alohida-alohida hisob yuritish" — batafsil talabi tasdiqlanmagan).`

**3. `spec/kod-uchun/03-modullar-talablari.md`, M10 — US-M10-04 ga qo'shimcha mezon:**

```
- Given tenant aylanma solig'i to'lovchisi (Soliq kodeksi 461-modda: jami daromad 1 mlrd so'mgacha), When oy yakunida ichki aylanma solig'i hisoblanadi, Then stavka 467-modda bo'yicha aniqlanadi: YTT/o'zini o'zi band qilgan — 1%; yuridik shaxs chakana savdosi — filialning "aholi punkti toifasi" bo'yicha 4% / 2% / 1% (tamaki savdosi aylanmasi har doim 4%, MXIK guruhi bo'yicha ajratiladi); boshqa faoliyat — 4%; summa filial va stavka bo'yicha alohida ko'rsatiladi.
```

- M10 "Davlat tizimlari bog'liqligi" ga qo'shilsin: `Aylanma solig'i stavkalari — Soliq kodeksi 467-moddasi (O'RQ-1108 tahririda, 2026-01-01'dan), to'lovchilar va 1 mlrd so'm chegarasi — 461-modda ([lex.uz/docs/4674902](https://lex.uz/docs/4674902)).`
