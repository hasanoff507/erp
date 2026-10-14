# Spec/01-mahsulot fayllarini faktlar bo'yicha tekshirish

> **ESKIRGAN (2026-10-14):** bu tekshiruv 2026-10-12 holatida. Undagi "5 ish kuni — qonun raqami topilmadi" va "GPT-5 >96% to'g'ri" xulosalari endi noto'g'ri: muddat **5 kalendar kun** (O'RQ-1108, Soliq kodeksi 81-modda), GPT-5 OCR ~88%. Amaldagi natijalar: `14-tekshiruv-xulosasi.md` va `spec/01-mahsulot/07-tuzatishlar-va-yechimlar.md`.

*Tadqiqotchi: Integrator · 2026-10-12*

## Asosiy xulosalar

1. **`spec/02-arxitektura/` hali bo'sh** — faqat `spec/01-mahsulot/` tekshirildi (6 fayl: 01–06), vazifa tasvirida ko'rsatilgan shartga mos.
2. **Mahsulot jamoasining 6 fayli juda yuqori sifatli va deyarli xatosiz** — har bir fakt/raqam tadqiqot fayllariga (00–11) yoki birlamchi manbaga (lex.uz, gazeta.uz, kursiv.media) to'g'ri havola qilingan, va noaniq joylar izchil "taxmin"/"ochiq savol" deb belgilangan. Bu tekshiruvda **yangi (ilgari aniqlanmagan) qonuniy/raqamli xato topilmadi**.
3. Topilgan narsalar asosan **ikki toifaga kiradi**: (a) meros ("inherited") noaniqliklar — tadqiqot fayllarida (00–07) allaqachon ma'lum bo'lgan ochiq savollar, spec fayllari ularni to'g'ri qayta tasdiqlaydi; (b) **ikkinchi darajali manbaga asoslangan raqamlar** — bular tadqiqot zanjirining boshida (01-fayl) kelib chiqqan, spec fayllari ularni to'g'ri iqtibos qiladi, lekin asl manba hali ham ikkinchi darajali.
4. **Eng muhim topilma**: QQS standart stavkasi (12%) — `spec/01-mahsulot/02-modullar-talablari.md` (US-M10-01) va `04-ekranlar-va-ux.md` (BO-07) ikkisi ham bu raqamni ishlatadi, Soliq kodeksi 258-moddasiga havola bilan — lekin bu havolaning o'zi **ikkinchi darajali manbalardan** (kovchegpremium.com, uz24.uz) kelib chiqqan, `01-erp-modullar-va-malumot-modeli.md`da ham shunday belgilangan. Lex.uz'dan to'g'ridan-to'g'ri 258-modda matni ushbu zanjirning hech bir bosqichida mustaqil o'qilmagan.
5. Bitta **til/belgi** xatosi topildi va aniqlashtirildi (pastda, 2-band) — aslida xato emas, balki ikki xil yozuv konventsiyasi (ЗРУ vs O'RQ) ekanligi tasdiqlandi.
6. Spec fayllari 00-faylda jamoa tomonidan yangi tasdiqlangan 3 faktni (48 soat, E-IMZO O'RQ-793, QR to'lov 2026-07-01) **to'g'ri va izchil** ishlatadi — ziddiyat topilmadi.

---

## Tekshiruv jadvali

| Spec fayli va bo'limi | Da'vo (iqtibos/mazmun) | Holat | To'g'ri ma'lumot va manba | Tavsiya etilgan tuzatish |
|---|---|---|---|---|
| `01-rollar-va-ssenariylar.md`, Asosiy xulosa #5 va 1-bo'lim | Markirovka yuklarining 80–90%i skanerlash xatosi bilan qaytadi | **To'g'ri** | `00-xulosa-va-ochiq-savollar.md`, 6-band; gazeta.uz 2026-04-14 — to'g'ri iqtibos qilingan, "yuk/partiya darajasida, yakka skanerlash emas" deb to'g'ri aniqlashtirilgan | Tuzatish kerak emas |
| `02-modullar-talablari.md`, M01, Davlat tizimlari bog'liqligi | QR to'lov 2026-07-01'dan to'liq majburiy | **To'g'ri** | `00-xulosa-va-ochiq-savollar.md`, 4-band; gazeta.uz 2025-12-10; lex.uz/docs/8139307 (CBU №3817) — bu endi 03-faylga ham qo'shilgan (11ece36e tuzatishi) | Tuzatish kerak emas |
| `02-modullar-talablari.md`, M06 | Markirovka ko'chirish muddati 72 soat, 23-son qaror (2026-01-23) | **To'g'ri** | `02-kassa-ofd-markirovka.md`; lex.uz/docs/8012407 | Tuzatish kerak emas |
| `02-modullar-talablari.md`, M10 (US-M10-01) | QQS standart stavka 12%, Soliq kodeksi 258-modda | **Manbasiz/ikkinchi darajali (meros)** | `01-erp-modullar-va-malumot-modeli.md`dagi asl manba kovchegpremium.com va uz24.uz — ikkinchi darajali; lex.uz'dan 258-modda matni hech qachon to'g'ridan-to'g'ri o'qilmagan | Arxitektura/Buxgalteriya jamoasi MVP ishlab chiqishdan oldin lex.uz Soliq kodeksi 258-moddasini to'g'ridan-to'g'ri tasdiqlashi tavsiya etiladi — bu 12% raqami kod darajasida QQS hisoblashning asosi (M10, M09) |
| `02-modullar-talablari.md`, M10 (US-M10-02, Eslatma) | "5 ish kuni" qoidasining aniq qonun raqami lex.uz'da topilmadi, faqat uz.kursiv.media | **To'g'ri (ochiq savol to'g'ri belgilangan)** | `04-arxitektura-va-stack.md`, 2-band; men mustaqil WebFetch bilan ham qayta tekshirdim (oldingi sessiya) — kursiv.media matnida qonun raqami yo'q, tasdiqlanadi | Tuzatish kerak emas, ochiq savol to'g'ri qoldirilgan |
| `03-biznes-jarayonlar.md`, BP-01 | E-ishonchnoma (Vakolat.uz) 2026-01-01'dan, QQ 825-son | **To'g'ri** | `09-soliq-integratsiyasi.md` — mos keladi | Tuzatish kerak emas |
| `03-biznes-jarayonlar.md`, BP-07 | VM Qarori №830-son (2025-12-26), ≤10% cheklov, yashil/qizil | **To'g'ri** | `03-efaktura-va-tolov.md`, 1.2-bo'lim — mos keladi, men 11ece36e'da bu bo'limni mustaqil qayta tekshirgan edim (48 mezon/71 idora raqamlari OLIB TASHLANGAN, lekin ≤10% va yashil/qizil tasdiqlangan qismi saqlanib qolgan) | Tuzatish kerak emas |
| `03-biznes-jarayonlar.md`, BP-05 | Fiskal chekni kim chiqarishi (to'lov tizimi/merchant) huquqiy ziddiyatli | **To'g'ri** | `03-efaktura-va-tolov.md`, 2.5-bo'lim — ziddiyat to'g'ri tasvirlangan, ikki talqin ham keltirilgan | Tuzatish kerak emas |
| `04-ekranlar-va-ux.md`, POS-03 | Offlaynda Payme/Click/Uzum QR o'chiriladi, chunki uchtasi ham onlayn tasdiq (push/Prepare-Complete/webhook) talab qiladi | **To'g'ri va manbali asoslash to'g'ri** | `03-efaktura-va-tolov.md`, 2.1–2.3-bo'lim — Payme push model, Click Prepare/Complete, Uzum webhook — barchasi serverga bog'liqligi tasdiqlangan | Tuzatish kerak emas |
| `04-ekranlar-va-ux.md`, 1.7-bo'lim | MXIK (IKPU) 17 raqamli kod, DataMatrix (markirovka) kodidan farqlanadi | **To'g'ri** | `02-kassa-ofd-markirovka.md` — ikkisi to'g'ri ajratilgan, chalkashtirish yo'q | Tuzatish kerak emas |
| `05-ai-funksiyalar.md`, AI-01/05/06 | Model narxlari: Claude Haiku 4.5 ($1/$5), Claude Sonnet 5 ($2/$10), GPT-5 ($1,25/$10), Gemini 2.5 Flash-Lite ($0,10/$0,40) | **To'g'ri** | `research_notes/texnik/05-ozbek-tilidagi-ai.md`, 2.2-bo'lim jadvali — aniq mos keladi, model nomi ham to'g'ri ("Sonnet 5", "Sonnet 5.5" emas — bu avvalroq Modelchi tomonidan tuzatilgan xato) | Tuzatish kerak emas |
| `05-ai-funksiyalar.md`, AI-03 | Vision-LLM aniqligi: 92,71–96,50% (Gemini 2.5 Pro), 94,75% (Gemini 3 Pro), >96% (GPT-5) | **To'g'ri** | `05-ozbek-tilidagi-ai.md` — arxiv.org, businesswaretech.com manbalari bilan mos | Tuzatish kerak emas |
| `06-mvp-chegarasi.md`, 4-bo'lim band 4 | "O'RQ-764 (Kiberxavfsizlik to'g'risidagi qonun)" | **Til konventsiyasi farqi, xato emas** | `07-hosting-lokalizatsiya-xavfsizlik.md`da "ЗРУ-764" (lex.uz ruscha sahifasidan) ishlatilgan — ЗРУ va O'RQ bir xil qonunning rus/o'zbek tilidagi qisqartmasi (№764, 2022-04-15), ikkisi ham to'g'ri, faqat yozuv konventsiyasi farq qiladi | Izchillik uchun: kelajakda barcha fayllarda bitta konventsiya (masalan O'RQ, chunki hujjat o'zbek tilida) ishlatilishi tavsiya etiladi — lekin bu **xato emas**, majburiy tuzatish emas |
| `06-mvp-chegarasi.md`, 3-bo'lim | ARPU oraliq mo'ljali 69 000–999 000 so'm/oy (REGOS Start–BILLZ Pro) | **To'g'ri** | `06-raqobatchilar-texnik-va-uskunalar.md`, 1-bo'lim jadvali — mos keladi | Tuzatish kerak emas |
| Barcha 6 fayl | "Didox 250 000 kompaniya" da'vosi | **Mavjud emas** | Bu da'vo spec/01-mahsulot fayllarining hech birida ishlatilmagan — faqat `research_notes` zanjirining boshida (06-fayl/oldingi tadqiqot) "tekshirilmagan" deb qoldirilgan, Mahsulot jamoasi buni meros qilib olmagan | Tuzatish kerak emas |

---

## Eng muhim 5 topilma (spetsifikatsiyaga eng ko'p ta'sir qiladiganlar)

1. **QQS 12% standart stavkasining asl manbasi hali ham ikkinchi darajali** (jadval, 4-qator) — bu raqam M09 (narxlar) va M10 (QQS) modullarining har bir sotuv/hisobotida ishlatiladi, shuning uchun eng yuqori ta'sirli. Lex.uz Soliq kodeksi 258-moddasini to'g'ridan-to'g'ri o'qib tasdiqlash MVP kodlashtirishdan oldin qilinishi **qattiq tavsiya etiladi** — agar stavka boshqacha chiqsa, butun QQS hisoblash mantiqi (M09, M10, barcha BP-02…08) ta'sirlanadi.
2. **"5 ish kuni" qoidasining qonun raqami hamon topilmadi** (jadval, 6-qator) — bu BP-08/M10/BO-10'ning butun muddat mexanizmi faqat bitta ikkilamchi (OAV) manbaga asoslanadi. Agar amalda muddat boshqacha (masalan 3 yoki 10 ish kuni) bo'lsa, markaziy arxitektura oqimi (5 kunlik hisoblagich) butunlay qayta ishlab chiqilishi kerak bo'ladi.
3. **Spec fayllari sifati yuqori, lekin barcha "taxmin"/"ochiq savol" bandlari hali ham tadqiqot bilan yopilmagan** — ayniqsa CRPT Turon (Asl belgisi) offline/qaytarish/qo'lda kiritish siyosati (M01, M02, M06, M09, M10'da takrorlanadi) va my.soliq.uz'dan ma'lumot olish mexanizmi (M10/BP-08/BO-10) — bular MVP boshlanishidan oldin huquqiy/texnik aniqlashtirish talab qiladi, aks holda bir nechta modul (M01, M02, M06, M10, M12) bir vaqtda bloklanadi.
4. **To'lov tizimida fiskal chek chiqaruvchisi haqidagi huquqiy ziddiyat** (BP-05, POS-03/04) hal qilinmagan holda UI darajasigacha "ikki holat ham ko'rsatilmaydi" deb qoldirilgan — bu kichik, ammo amalda har bir QR/Click/Payme sotuvida yuzaga keladigan kundalik noaniqlik, tezroq huquqiy javob olish foydali bo'lardi.
5. **Til/konventsiya farqi (ЗРУ vs O'RQ)** — xato emas, lekin kelajakda chalkashlikni oldini olish uchun hujjatlar bo'ylab bitta konventsiyaga izchil o'tish tavsiya etiladi (kichik ta'sirli, kosmetik).

---

## Ochiq savollar

1. `spec/02-arxitektura/` bo'sh bo'lgani uchun bu tekshiruv faqat `spec/01-mahsulot/`ni qamrab oldi — Arxitektura jamoasi fayl yozgach, alohida tekshiruv kerak bo'ladi.
2. QQS 258-modda matnini lex.uz'dan to'g'ridan-to'g'ri tasdiqlash — hali qilinmagan (yuqoridagi #1-topilma).
3. "5 ish kuni" qoidasining asl qonun/qaror raqami — hali topilmadi (yuqoridagi #2-topilma).

## Manbalar

- `spec/01-mahsulot/01-rollar-va-ssenariylar.md`, `02-modullar-talablari.md`, `03-biznes-jarayonlar.md`, `04-ekranlar-va-ux.md`, `05-ai-funksiyalar.md`, `06-mvp-chegarasi.md` (tekshirilgan fayllar)
- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, `01-erp-modullar-va-malumot-modeli.md`, `02-kassa-ofd-markirovka.md`, `03-efaktura-va-tolov.md`, `04-arxitektura-va-stack.md`, `05-ozbek-tilidagi-ai.md`, `06-raqobatchilar-texnik-va-uskunalar.md`, `07-hosting-lokalizatsiya-xavfsizlik.md`, `09-soliq-integratsiyasi.md` (taqqoslash bazasi)
- [lex.uz/docs/4603329](https://lex.uz/docs/4603329), [lex.uz/docs/8012407](https://www.lex.uz/docs/8012407), [lex.uz/uz/docs/-7962143](https://lex.uz/uz/docs/-7962143) — to'g'ridan-to'g'ri tasdiqlangan qonun manbalari
