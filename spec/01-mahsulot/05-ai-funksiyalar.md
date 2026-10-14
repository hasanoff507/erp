# AI funksiyalar — MVP da nima real

## Asosiy xulosalar

1. *(2026-10-14: tekshiruv)* MVP uchun **3 ta AI funksiya real**: AI-01 (umumiy biznes savol-javob chat, "bugun qancha foyda?"), AI-05 (davlat hisoboti tafovutini tushuntirish) va AI-06 (debitorlik/nasiya eslatma matni) — barchasi "kod hisoblaydi, AI tushuntiradi" tamoyili bilan (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim). **AI-03** (qog'oz faktura/yuk xati fotosidan OCR, pilot bilan, torroq qamrovda — 2-band) — **MVP'dan keyin** (`02-arxitektura/11-backlog.md`), pilotdan keyin backlog sifatida rejalashtirilgan.
2. **Arxitektura qoidasi — har bir funksiyada majburiy**: raqamni (foyda, qoldiq, tafovut summasi, risk balli) doim kod/SQL hisoblaydi; AI/LLM faqat o'zbek tilida tushuntiradi, matn yozadi yoki tavsiya beradi — hech qachon raqamni o'zi "o'ylab topmaydi" (`texnik/05-ozbek-tilidagi-ai.md`, Xulosa #8; `AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, "Architecture principle").
3. **AI hech qachon davlat tizimiga (OFD, Soliq, CRPT Turon, Didox/Faktura.uz) hujjatni o'zi yubormaydi** — faqat loyiha/tavsiya tayyorlaydi, yuborishni odam (Buxgalter/Menejer) tasdiqlaydi. Sabab: AI xatosi bo'lsa ham, yuridik javobgarlik va jarima xavfi (masalan Asl belgisi skanerlash xatosi aylanmaning 20%igacha jarima) odam nazoratisiz oshadi (`texnik/00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #6).
4. **Hozircha real emas**: AI-04 (qo'lda yozilgan "nasiya daftari" OCR) — kirill qo'lyozma uchun hech qanday benchmark yo'q (`texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim).
5. **Keyingi bosqichga qoldirilgan**: AI-02 (ovozli savol-javob/STT), AI-07 (POS/o'g'irlik anomaliya aniqlash — yuqori murakkablik, qimmat infratuzilma), AI-08 (bank tranzaksiya avtomatik kategoriyalash), AI-09 (talab bashorati/buyurtma tavsiyasi), AI-10 (narx optimallashtirish tavsiyasi) va AI-11 (kundalik ovozli brifing/TTS) — sabab har birida yo yetarli tarixiy ma'lumot yo'q, yo mahalliy aniqlik raqami ochiq manbada topilmadi, yo infratuzilma MVP uchun ortiqcha.
6. **O'zbek tili uchun rasmiy LLM benchmark umuman yo'q** (Claude/GPT/Gemini) — bu barcha funksiyalar uchun umumiy chegara: aniqlik raqamlari ingliz-tilidagi benchmarklardan olingan, o'zbekcha/kirill matn uchun MVP davrida mahalliy pilot-sinov shart (`texnik/05-ozbek-tilidagi-ai.md`, Asosiy xulosa #1).
7. *(2026-10-14: tuzatildi — model ro'yxati yangilandi, quyida yechim)* Model/narx claude.com/pricing va boshqa rasmiy narx sahifalaridan olinadi: matn/tushuntirish vazifalari uchun endi standart arzon model **Claude Haiku 5.5** ($0,10–0,50 kirish / $0,50–2,50 chiqish, 1M tok, hajmga qarab — Anthropic, 2026-10-07 relizi) yoki Gemini 2.5 Flash-Lite / GPT-5-nano; **Claude Haiku 4.5 ($1/$5) endi legacy va Haiku 5.5'dan qimmatroq — yangi loyihalarda ishlatilmaydi**. Murakkabroq fikrlash uchun Claude Sonnet 5.5 yoki Sonnet 5 (ikkisi ham $2/$10 — narx bir xil) yoki GPT-5; hujjat OCR (vision) uchun multimodal model (Gemini/GPT-5 vision rejimi). Haiku 5.5'ga o'tish MVP AI xarajat hisob-kitobini pasaytiradi (AI-01, AI-06 uchun taxminan 2–10x arzonroq, hajmga qarab).
8. Ma'lumot lokalizatsiyasi: faqat biometrik/genetik/telekom ma'lumot O'zbekistonda saqlanishi majburiy; mijoz nomi, tranzaksiya, faktura matni kabi ma'lumotlarni xavfsizlik talablariga rioya qilgan holda chet el LLM API'ga (Claude/GPT/Gemini) yuborish mumkin (`texnik/05-ozbek-tilidagi-ai.md`, 1.3-bo'lim).

---

## 1. O'zbek tilida savol-javob (Q&A)

### AI-01: Umumiy biznes savol-javob chat

- **Hukm**: **MVP**.
- **Sabab**: Global ERP vendorlari (Xero JAX, QuickBooks Intuit Assist, Zoho Zia) buni allaqachon "code computes, AI explains" tamoyili bilan amalga oshirgan; LLM raqamni o'zi hisoblamaydi, faqat SQL natijasini o'zbek tilida tabiiy shaklda tushuntiradi — xato darajasi past (`texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali: "Past-o'rta"; `AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, 7-band).
- **Misollar**:
  1. So'rov: "Bugun qancha foyda qildim?" → Javob: "Bugun sof foyda 1 240 000 so'm (kod hisoblagan). Kechagiga nisbatan 8% ko'p — asosiy sabab ichimlik toifasidagi sotuv o'sishi (sabab ham toifalar bo'yicha farqni kod hisoblagan natija, AI faqat uni so'z bilan ifodalaydi — AI o'zi sabab o'ylab topmaydi)."
  2. So'rov: "Shu oy eng ko'p sotilgan 5 mahsulotni ayt" → Javob: kod SQL orqali TOP-5 ro'yxatini chiqaradi, AI uni ro'yxat shaklida o'zbekcha izoh bilan taqdim etadi.
  3. So'rov: "Omborda qaysi tovarlar tugayapti?" → Javob: M04 (ombor qoldig'i) jadvalidan kod minimal qoldiq qoidasi bo'yicha tovarlarni tanlaydi, AI ro'yxatni ro'yxat+izoh shaklida taqdim etadi (buyurtma miqdori/tavsiyasi bermaydi — bu AI-09, Keyingi bosqich).
- **Chegaralar**: Aniqlik — javob matnining o'zbek tilidagi tabiiyligi tekshirilmagan (rasmiy benchmark yo'q); lotin/kirill aralash so'rovlarni tushunish darajasi tasdiqlanmagan — pilot kerak. Xato narxi — past, chunki raqamni kod hisoblaydi; faqat izoh/uslub xato bo'lishi mumkin, moliyaviy qaror AI izohiga emas, kod raqamiga asoslanadi.
- **Xavf va himoya**: LLM hech qachon raqamni o'zi generatsiya qilmasligi kod darajasida majburlanadi (prompt-da raqam kiritiladi, LLM faqat qayta ifodalaydi); javobda ko'rsatilgan har bir raqam tegishli SQL natijasiga bog'langan holda saqlanadi (audit uchun).
- **Ulangan modul**: M12 (hisobotlar) — ma'lumot manbai; dolzarb holatda M01, M04, M08, M09, M10, M11 ga so'rov yuboradi.
- **Model/xarajat**: Oddiy tushuntirish uchun **Claude Haiku 5.5** ($0,10–0,50 kirish / $0,50–2,50 chiqish, 1M tok, hajmga qarab) yetarli va Haiku 4.5'dan ($1/$5) arzonroq *(2026-10-14: tuzatildi — Haiku 4.5 endi legacy)*; murakkabroq ko'p bosqichli tahlil (bir nechta modul kesishmasi) uchun Claude Sonnet 5.5/Sonnet 5 ($2/$10, ikkisi bir xil narx) — claude.com/pricing (2026-10-14).

### AI-02: Ovozli savol-javob (STT orqali)

- **Hukm**: **Keyingi bosqich**.
- **Sabab**: Shovqinli do'kon muhitida o'zbek tili uchun STT aniqligi (WER) bo'yicha hech qanday manbada raqam topilmadi (Whisper, Yandex SpeechKit, Google Cloud STT — uchtasida ham); bu "ochiq manbada topilmadi" deb aniq belgilangan amaliy xavf, mahalliy pilot-sinov talab qiladi (`texnik/05-ozbek-tilidagi-ai.md`, 2-bo'lim va Ochiq savollar).
- **Misollar**: (pilotdan keyin rejalashtirilgan, hozircha amalga oshirilmaydi) — "Ovoz bilan: bugungi savdo qancha?" kabi so'rovlar faqat matnli chat (AI-01) orqali ishlaydi, ovozli kiritish keyingi bosqichda qo'shiladi.
- **Chegaralar**: Eng yaqin raqam — toza studiyaviy sharoitda NavAI Whisper-medium-uzbek makro-WER 9,73% / mikro-WER 8,81% (`texnik/05-ozbek-tilidagi-ai.md`, 2-bo'lim jadvali) — bu do'kon fon shovqinisiz holat, haqiqiy POS muhitidagi aniqlik noma'lum.
- **Xavf va himoya**: Noto'g'ri tanilgan ovozli buyruq xato amalga (masalan noto'g'ri chegirma) olib kelmasligi uchun MVP'da ovozli kiritish ishlatilmaydi; matnli chat (AI-01) orqali asosiy funksiya ta'minlanadi.
- **Ulangan modul**: M12 (hisobotlar) — AI-01 bilan bir xil ma'lumot manbalari.
- **Model/xarajat**: Baholanmagan — MVP'da ishlatilmaydi.

---

## 2. Hujjat OCR (yuk xati, faktura, chek)

### AI-03: Qog'oz hujjat (yuk xati/faktura/chek) fotosidan ma'lumot chiqarish

- **Hukm**: **MVP'dan keyin** (pilot bilan, qog'oz hujjatlar bilan cheklangan qamrov) *(2026-10-14: tekshiruv — T2, `02-arxitektura/11-backlog.md`)*.
- **Qamrov toraytirildi**: Soliq kodeksiga ko'ra (2019-12-30) QQS to'lovchilar o'rtasidagi fakturalar faqat elektron axborot tizimida tuziladi, saqlanadi va hisobga olinadi; qog'oz shakli faqat **texnik uzilish** holatida ruxsat etiladi (`texnik/03-efaktura-va-tolov.md`, 26-qator). Shuning uchun QQS to'lovchi yetkazib beruvchidan kelgan standart e-faktura/e-TTN **OCR orqali emas**, EDO operatori (Didox/Faktura.uz) orqali tuzilgan ma'lumot sifatida tizimga import qilinadi. AI-03 faqat quyidagi qog'oz holatlar bilan cheklanadi: (a) QQS to'lovchi bo'lmagan yoki norasmiy yetkazib beruvchining qog'oz yuk xati, (b) texnik uzilish davridagi qog'oz faktura, (c) mijozga berilgan/qaytarish uchun qog'oz chek.
- **Sabab**: Multimodal vision-LLM (Gemini, GPT-5) toza chop etilgan hujjat rasmidan tuzilgan maydonlarni (summa, sana, MXIK kodi) 87–97% aniqlik bilan chiqaradi — bu klassik shablonli OCR'dan ko'ra amaliy MVP yo'li, lekin kirill/o'zbek-specific aniqlik tasdiqlanmagan, shuning uchun pilot bilan cheklanadi (`texnik/05-ozbek-tilidagi-ai.md`, 3 va 4-bo'limlar).
- **Misollar**:
  1. Omborchi QQS to'lovchi bo'lmagan mayda yetkazib beruvchidan kelgan qog'oz yuk xatining fotosini yuklaydi → AI tovar nomi, miqdor, narx, umumiy summa maydonlarini tuzilgan shaklda chiqaradi → foydalanuvchi tasdiqlagandan keyin M07 (xarid) hujjatiga aylanadi.
  2. Texnik uzilish tufayli qog'oz shaklda tuzilgan faktura fotosi yuklanadi → AI sana, MXIK kodi, QQS summasini ajratadi → Buxgalter ko'rib chiqadi, xato bo'lsa qo'lda tuzatadi, so'ng tasdiqlaydi.
  3. Mijozga berilgan qog'oz chek fotosi (qaytarish uchun) yuklanadi → AI chek raqami va summani o'qiydi → M02 (qaytarish) jarayoniga mos tovar/sana topiladi.
- **Chegaralar**: Aniqlik — toza faktura uchun 92,71–96,50% (Gemini 2.5 Pro), 94,75% (Gemini 3 Pro), **~88% (GPT 5.2/GPT-5 mini** — businesswaretech.com 2026 benchmark*(2026-10-14: tuzatildi — avval ">96%" deb yozilgan, manbada bu raqam yo'q)*), chek uchun 84,40% (GPT-4o) — 91,15% (Gemini 1.5 Pro); bularning barchasi ingliz-tilidagi benchmark, **kirill+lotin+rus aralash O'zbekiston hujjatlari uchun mustaqil raqam yo'q** — ochiq savol. **Qabul chegarasi va inson tekshiruvi**: AI ishonch darajasi (confidence) past bo'lgan maydonlar (masalan summa/sana aniq o'qilmagan) avtomatik "past ishonch" belgisi bilan ajratiladi va foydalanuvchi tasdig'isiz hujjatga kiritilmaydi; aniq chegara (masalan 90%dan past) **taxmin**, MVP pilotida sozlanishi kerak *(2026-10-14: qo'shildi — yechim)*. Xato narxi — o'rta: noto'g'ri o'qilgan summa/miqdor moliyaviy hujjatga xato kiritilishi mumkin, shuning uchun AI natijasi har doim foydalanuvchi tasdig'idan o'tadi, avtomatik tasdiqlanmaydi.
- **Xavf va himoya**: AI hujjatni o'zi davlat tizimiga (Didox/Faktura.uz, e-TTN) yubormaydi — faqat ichki hujjat loyihasini tayyorlaydi; yakuniy tasdiq va yuborish odam tomonidan amalga oshiriladi. Standart QQS to'lovchilar orasidagi elektron faktura/e-TTN AI-03 orqali OCR qilinmaydi — EDO operatori orqali import qilinadi (yuqoridagi qamrov eslatmasi). Skanerlangan/burchak qiyshaygan rasmlarda aniqlik pasayishi (87,46% chek darajasigacha) kutilishi kerak — foydalanuvchiga "tasdiqlang yoki tuzating" ekrani majburiy.
- **Ulangan modul**: M07 (xarid), M02 (qaytarish); natija M04 (ombor qoldig'i) va M11 (buxgalteriya) ga ta'sir qiladi.
- **Model/xarajat**: Vision-LLM talab qilinadi (matn-faqat arzon modellar ishlamaydi); `texnik/05-ozbek-tilidagi-ai.md` 2.2-bo'limida keltirilgan umumiy modellar orasidan multimodal qamrovga ega bo'lganlari (Gemini 2.5 Pro/Flash, GPT-5 oilasi) — aniq vision-narx qatori 05-faylda alohida ko'rsatilmagan, shu sabab narx **taxmin**: matn narxiga yaqin, aniqlashtirish kerak.

### AI-04: Qo'lda yozilgan "nasiya daftari"ni OCR qilish

- **Hukm**: **Hozircha real emas** (MVP'ga kiritilmaydi).
- **Sabab**: Kirill-o'zbek qo'lyozma uchun hech qanday ishonchli benchmark ochiq manbada topilmadi; umumiy qo'lyozma OCR aniqligi 63–95% oralig'ida juda keng va ishonchsiz (`texnik/05-ozbek-tilidagi-ai.md`, 3-bo'lim va 7-xulosa).
- **Misollar**: MVP'da ishlatilmaydi. O'rniga: M08 (nasiya) modulida tuzilgan raqamli forma — Kassir mijozni tanlaydi, summani qo'lda kiritadi (`texnik/05-ozbek-tilidagi-ai.md`, 7-xulosa va 3-bo'lim xulosasi: "tuzilgan raqamli forma qo'lyozma-OCR'dan ko'ra ishonchli muqobil"). Kelajakda (agar benchmark topilsa) kutilgan ko'rinish: Kassir qo'lda yozilgan daftar sahifasining fotosini yuklaydi → AI mijoz nomi va summani o'qib, tasdiqlash uchun ko'rsatadi.
- **Chegaralar**: Umumiy qo'lyozma OCR aniqligi 63–95% oralig'ida (yozuv sifatiga qarab juda o'zgaruvchan), kirill-o'zbek qo'lyozma uchun alohida benchmark yo'q — bu oraliq MVP uchun yetarlicha ishonchli emas (`texnik/05-ozbek-tilidagi-ai.md`, 3-bo'lim).
- **Xavf va himoya**: Qo'llanilmaydi — xavfning o'zi oldini olish uchun funksiya MVP'dan chiqarib tashlangan.
- **Ulangan modul**: M08 (nasiya) — AI o'rniga qo'lda forma kiritiladi.
- **Model/xarajat**: Qo'llanilmaydi.

---

## 3. Anomaliya va ogohlantirishlar (shu jumladan davlat hisoboti tafovutlari)

### AI-05: Davlat hisoboti tafovutini tushuntirish va ogohlantirish

- **Hukm**: **MVP** (texnik/05 4-bo'lim jadvalida AI-05 alohida satr sifatida yo'q — bu funksiya AI-01 ("code computes, AI explains") tamoyilining davlat hisoboti solishtirish motoriga qo'llanishi, mahsulotning markaziy oqimi bilan bog'liqligi sababli MVP deb belgilangan; solishtirish motorining o'zi, texnik/00 ga ko'ra, MVP'da **qo'lda/yarim-avtomatik** ishlaydi, to'liq avtomatik emas).
- **Sabab**: 2026-01-01 dan soliq organlari QQS va aylanma solig'i hisobotlarini o'zi tuzadi (Soliq kodeksi 81-moddasi, O'RQ-1108), korxonaga **5 kalendar kun** ichida tuzatish kiritish imkoni beriladi — bu mahsulotning markaziy qiymat taklifi *(2026-10-14: tuzatildi — "5 ish kuni" emas)*. Tafovutni va uning sababini (qaysi hujjat/toifa/davr) **kod** moslashtirish orqali hisoblaydi; AI faqat kod chiqargan natijani o'zbek tilida tushuntiradi va tasdiq/tuzatish bo'yicha tavsiya beradi — "code computes, AI explains" tamoyili (`AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, Architecture principle). AI hech qachon sababni o'zi taxmin qilib yozmaydi.
- **Misollar**:
  1. Kod aniqlaydi: davlat QQS hisoboti 2 300 000 so'mga ichki hisobdan farq qiladi va kod hujjat darajasida moslashtiradi (3 ta sotuv e-fakturasi tizimga ulanmagan) → AI: "Tafovut sababi: 14-oktyabrdagi 3 ta sotuv e-fakturasi tizimga ulanmagan ko'rinadi (kod aniqlagan) — ro'yxatini ko'rish uchun bosing. 5 kalendar kun ichida tuzatish kiritish mumkin." *(2026-10-14: "5 ish kuni" → "5 kalendar kun" tuzatildi)* **Taxmin/ochiq savol**: bu misol davlat tomonidan hujjat darajasidagi ma'lumot (qaysi chek/e-faktura kiritilgan) olinishini taxmin qiladi — my.soliq.uz'da rasmiy API yo'qligi sababli bu hali tasdiqlanmagan (`texnik/00-xulosa-va-ochiq-savollar.md`, Eng katta texnik xavf #2; Ochiq savol #7).
  2. Agar davlatdan faqat **yig'ma summa** (hujjat darajasisiz) olinadigan bo'lsa — bu ham ehtimoliy, tasdiqlanmagan holat — kod faqat davr/toifa darajasida solishtiradi, AI: "Bu oy QQS bo'yicha davlat hisoboti ichki hisobdan 2 300 000 so'mga farq qiladi; aniq qaysi hujjat sabab bo'lganini davlat tomonidan hujjat darajasida ma'lumot kelmagani uchun ko'rsatib bo'lmaydi — qo'lda tekshirish tavsiya etiladi."
  3. Kod aniqlaydi: tafovut yo'q, hisobotlar mos → AI: "Bu oy davlat hisoboti va ichki hisobingiz to'liq mos keldi, qo'shimcha harakat kerak emas."
- **Chegaralar**: Rasmiy my.soliq.uz API yo'qligi sababli tafovutni avtomatik aniqlash manba ma'lumotiga (korxona yuklagan/kiritgan hisobotga) bog'liq — bu MVP'da qo'lda/yarim-avtomatik boshlanadi (`texnik/00-xulosa-va-ochiq-savollar.md`, Eng katta texnik xavf #2). Hujjat darajasidagi tafovut sababini ko'rsatish (misol 1) shu ochiq savolga bog'liq — **taxmin/ochiq savol** deb belgilanadi; davlat faqat yig'ma summa bersa, tushuntirish faqat davr/toifa darajasida bo'ladi (misol 2). Xato narxi — **yuqori** agar AI tushuntirishi noto'g'ri bo'lsa (masalan sababni xato ko'rsatsa) foydalanuvchi noto'g'ri qaror (dispute bermaslik) qabul qilishi mumkin; shuning uchun tushuntirish doim kod aniqlagan manba hujjatlarga (sana, hujjat raqami) havola bilan beriladi, foydalanuvchi o'zi tekshiradi.
- **Xavf va himoya**: AI hech qachon dispute'ni yoki tasdiqni my.soliq.uz'ga o'zi yubormaydi — faqat tavsiya va tushuntirish beradi, yuborish/tasdiqlash Buxgalter tomonidan qo'lda amalga oshiriladi. Tafovut summasi doim kod tomonidan hisoblanadi, AI undan foydalanadi, o'zi qayta hisoblamaydi.
- **Ulangan modul**: M10 (QQS), M11 (buxgalteriya), M12 (hisobotlar).
- **Model/xarajat**: Claude Sonnet 5.5/Sonnet 5 ($2/$10 1M tok, ikkisi bir xil narx) yoki GPT-5 ($1,25/$10) — ko'p hujjatni taqqoslab tushuntirish murakkabroq fikrlash talab qiladi, shuning uchun eng arzon model emas *(2026-10-14: Sonnet 5.5 qo'shildi)*.

### AI-06: Debitorlik (nasiya) risk skorlash va eslatma matni

- **Hukm**: **MVP**.
- **Sabab**: Risk belgisini (qancha kun kechikkan, qancha marta kechiktirgan) kod/qoida hisoblaydi; LLM faqat o'zbekcha eslatma matnini generatsiya qiladi — xavf past, chunki raqamni AI o'zi hisoblamaydi (`texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali: "Past").
- **Misollar**:
  1. Kod aniqlaydi: mijoz A 15 kundan beri 450 000 so'm qarzdor → AI matn yozadi: "Hurmatli [mijoz], 450 000 so'm qarzingiz 15 kundan beri kechikdi. Iltimos, imkon qadar tezroq to'lang."
  2. Kod aniqlaydi: mijoz B risk balli yuqori (3 marta kechiktirgan) → AI Menejerga: "Mijoz B yuqori risk toifasida — keyingi nasiyani cheklashni ko'rib chiqing."
  3. Buxgalter so'raydi: "Eng ko'p qarzdor 5 mijozni ko'rsat" → kod ro'yxatni chiqaradi, AI uni tartiblab, har biriga qisqa izoh qo'shadi.
- **Chegaralar**: Risk balli qoidasi sodda (kechikkan kun/marta soni) bo'lishi kerak — murakkab ML skorlash tarixiy ma'lumot yetarli bo'lmagani uchun MVP'da yo'q. Xato narxi — past: eng yomon holatda matn uslubi noqulay chiqadi, lekin risk balli va summa har doim kod natijasi.
- **Xavf va himoya**: Eslatma matni avtomatik yuborilishidan oldin Menejer/Kassir tasdig'idan o'tishi **majburiy** (Asosiy xulosa #3: AI hujjat/xabarni o'zi yubormaydi) — AI faqat loyiha matnini tayyorlaydi, yuborishni odam amalga oshiradi.
- **Ulangan modul**: M08 (nasiya).
- **Kanal** *(2026-10-14: yangilandi)*: Telegram (M18, US-M08-08) va SMS (`02-arxitektura/03-integratsiyalar.md` §10) endi spec'da bor; MVP'da eslatma Telegram + ekranda ko'rsatish orqali, SMS provayder tanlangach qo'shiladi. **Ochiq savol**: SMS provayder va narxi tanlanmagan.
- **Model/xarajat**: **Claude Haiku 5.5** ($0,10–0,50/$0,50–2,50, hajmga qarab) yoki Gemini 2.5 Flash-Lite ($0,10/$0,40) — oddiy matn generatsiyasi, eng arzon model yetarli *(2026-10-14: tuzatildi — avval Haiku 4.5 ($1/$5) ko'rsatilgan edi, endi legacy va qimmatroq)*.

### AI-07: POS/o'g'irlik anomaliya aniqlash (behavioral + video)

- **Hukm**: **Keyingi bosqich (yuqori murakkablik)**.
- **Sabab**: Video+POS integratsiyasi va behavioral model qimmat infratuzilma talab qiladi (kamera, saqlash, qayta ishlash); global misollarda ham bu alohida qimmat qatlam — MVP uchun ortiqcha deb baholangan (`texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali: "Keyingi bosqich / yuqori murakkablik").
- **Misollar**: MVP'da ishlatilmaydi. Keyingi bosqichda kutilgan ko'rinish: Menejer so'raydi "Bugun shubhali operatsiyalar bormi?" → AI (kod aniqlagan ko'p bekor qilingan chek/chegirma hodisalari asosida): "Kassir X bugun 7 marta chekni bekor qildi — odatdagi o'rtachadan (1-2) yuqori, tekshirib ko'rish tavsiya etiladi." MVP'da esa o'rniga M13 (huquqlar) orqali oddiy qoida-asosli ogohlantirish (masalan ko'p bekor qilingan chek chegarasidan oshganda) mumkin — bu AI emas, kod/qoida darajasida, shu sabab AI-nn ro'yxatiga kiritilmagan.
- **Chegaralar**: Texnik tadqiqotda O'zbekiston-specific aniqlik raqami yo'q, global raqamlar (masalan video+POS orqali 50% shrinkage kamayishi) ham faqat market tadqiqotida, 05-fayl (asosiy manba) tomonidan tasdiqlanmagan (`AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, 4-band) — **manbasiz raqam sifatida MVP qaroriga asos qilib olinmadi**; video-asosli yechim uchun kamera infratuzilmasi xarajati ham baholanmagan.
- **Xavf va himoya**: Ishga tushganda ham AI faqat ogohlantiradi, xodimga nisbatan avtomatik chora (ish haqidan ushlab qolish, ishdan bo'shatish) ko'rmaydi — yakuniy qaror Menejer/Egasi tomonidan qabul qilinadi.
- **Ulangan modul**: M01 (kassa), M13 (huquqlar) — keyingi bosqichda.
- **Model/xarajat**: Baholanmagan.

### AI-08: Bank tranzaksiya avtomatik kategoriyalash

- **Hukm**: **Keyingi bosqich**.
- **Sabab**: O'zbekistonda ochiq bank API cheklangan (CBU'da faqat ma'lumotlar portali, dasturiy API yo'q), shuning uchun avtomatik kategoriyalash uchun ma'lumot manbai yetarli emas — xavf "Yuqori" deb baholangan (`texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali).
- **Misollar**: MVP'da ishlatilmaydi — bank tranzaksiyalari qo'lda kategoriyalanadi (M11 buxgalteriya ichida). Kelajakda kutilgan ko'rinish: Buxgalter bank ko'chirmasini (vypiska) qo'lda yuklagandan keyin AI: "Bu 15 tranzaksiyadan 12 tasi 'yetkazib beruvchiga to'lov' toifasiga mos keladi (kod qoida bo'yicha aniqlagan) — tasdiqlaysizmi?"
- **Chegaralar**: O'zbekistonda ochiq banking API hali yo'q (rasmiy standart 2026-09-01 ga rejalashtirilgan, PQ-359) — ma'lumot faqat qo'lda yuklangan ko'chirma (vypiska) orqali kirishi mumkin, jonli integratsiya yo'q (`texnik/03-efaktura-va-tolov.md`, 9-band). Global vendorlardagi 85–95% aniqlik (QuickBooks, Xero) O'zbekiston bank format sharoitiga tatbiq etilmaydi — bu raqam **asosiy manbada (texnik/05) tasdiqlanmagan, faqat market tadqiqotida**, shuning uchun MVP qaroriga asos bo'lmaydi.
- **Xavf va himoya**: Qo'llanilmaydi.
- **Ulangan modul**: M11 (buxgalteriya).
- **Model/xarajat**: Baholanmagan.

---

## 4. Tavsiyalar (buyurtma, narx)

### AI-09: Talab bashorati asosida qayta buyurtma tavsiyasi

- **Hukm**: **Keyingi bosqich**.
- **Sabab**: Klassik statistik/ML model talab qilinadi (LLM shart emas), bunga kamida bir necha oylik tarixiy savdo ma'lumoti kerak — MVP boshida bu ma'lumot hali to'planmagan (`texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali: "O'rta — yetarli tarixiy ma'lumot to'planishi kerak").
- **Misollar**: Ishlatilmaydi MVP'da. Keyingi bosqichda: "Tovar X 5 kundan keyin tugaydi, o'tgan oylardagi sotuv tendentsiyasiga ko'ra 200 dona buyurtma qilish tavsiya etiladi."
- **Chegaralar**: Global misollarda 20–50% xato kamayishi va 10–30% ombor xarajati tejash ko'rsatilgan, ammo bu raqamlar global vendorlar (Odoo, Zoho, Toast) uchun, O'zbekiston SME ma'lumotiga tatbiq etilmagan — bu raqam **faqat market tadqiqotida (`AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, 1-band), asosiy texnik manbada tasdiqlanmagan — taxmin**.
- **Xavf va himoya**: Qo'llanilmaydi (MVP'da yo'q) — ishga tushganda ham tavsiya faqat ko'rsatma bo'ladi, buyurtma avtomatik yuborilmaydi, Omborchi/Menejer tasdiqlaydi.
- **Ulangan modul**: M04 (ombor qoldig'i), M07 (xarid), M09 (narxlar).
- **Model/xarajat**: Baholanmagan — ML/statistik model, LLM narx jadvali bu yerga tatbiq etilmaydi.

### AI-10: Narx optimallashtirish tavsiyasi

- **Hukm**: **Keyingi bosqich (ochiq savol)**.
- **Sabab**: Asosiy texnik manba (`texnik/05-ozbek-tilidagi-ai.md`) narx optimallashtirishni alohida baholamagan — faqat market tadqiqotida ("Narx taklifi | Price optimization from margins | Odoo, custom | Yuqori") qisqa eslatma bor, murakkablik "Yuqori" deb belgilangan (`AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, "Uzbek SME pain points" jadvali).
- **Misollar**: MVP'da ishlatilmaydi. Kelajakda kutilgan ko'rinish: Menejer so'raydi "Tovar Y narxini oshirsam bo'ladimi?" → AI (M09 narxlar va M11 buxgalteriya'dagi marja ma'lumoti asosida, kod hisoblagan): "Tovar Y'ning joriy marjasi 12% — raqobatchilar o'rtachasi haqida ma'lumot yo'q, shuning uchun aniq tavsiya berib bo'lmaydi."
- **Chegaralar**: Marja ma'lumoti M09/M11 dan olinishi mumkin, ammo yondashuv (qoidaviy vs ML) va aniqlik texnik tadqiqotda batafsil o'rganilmagan — **ochiq savol**.
- **Xavf va himoya**: Qo'llanilmaydi.
- **Ulangan modul**: M09 (narxlar).
- **Model/xarajat**: Baholanmagan.

### AI-11: Kundalik ovozli brifing (TTS)

- **Hukm**: **Keyingi bosqich**.
- **Sabab**: TTS tabiiyligi (Muxlisa/UzbekVoiceAI/Aisha) tekshirilmagan, hech qanday aniqlik/sifat raqami ochiq manbada yo'q — matnli brifing (AI-01 orqali) birinchi qadam bo'lishi tavsiya etiladi (`texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali: "O'rta — TTS tabiiyligi tekshirilmagan").
- **Misollar**: MVP'da ishlatilmaydi — o'rniga AI-01 orqali matnli kunlik xulosa. Kelajakda kutilgan ko'rinish: ertalab Egasi ilovani ochganda ovozli xabar eshitadi: "Xayrli tong! Kecha sof foyda 980 000 so'm bo'ldi, 2 ta tovar qoldig'i kam."
- **Chegaralar**: TTS tabiiyligi (talaffuz, urg'u) va shovqinli muhitda eshitilishi tekshirilmagan — hech qanday sifat/aniqlik raqami ochiq manbada yo'q (`texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali).
- **Xavf va himoya**: Qo'llanilmaydi.
- **Ulangan modul**: M12 (hisobotlar).
- **Model/xarajat**: Baholanmagan.

---

## 5. AI provayderi: obuna, API yoki lokal model (2026-10-14)

**Savol (foydalanuvchi):** AI uchun Claude Code CLI'ni obuna (Pro/Max) orqali ishlatish yoki Ollama'da lokal model (oddiy kompyuterda ishlaydigan) ishlatish.

| Variant | Xulosa | Sabab |
|---|---|---|
| Claude obunasi (Pro/Max) + Claude Code CLI / Agent SDK, mahsulot ichida | **Ishlatilmaydi** | Anthropic qoidasi: "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK. Use the API key authentication…" ([code.claude.com/docs/en/agent-sdk/overview](https://code.claude.com/docs/en/agent-sdk/overview)). Obuna bitta odam uchun; yuzlab do'kon so'rovlarini ko'tarmaydi (limitlar), bloklanish xavfi bor. Claude Code — **jamoa ilovani yozishi uchun** ishlatiladi, mahsulot ichida emas |
| **Claude API (Haiku 5.5, kerak bo'lsa Sonnet 5.5)** | **Asosiy yo'l** | Tijorat shartlari bo'yicha ruxsat; arzon: Haiku 5.5 $0,10–0,50 / $0,50–2,50 per 1M token. Taxmin: 1 do'kon oyiga 300 so'rov × (3 000 kirish + 500 chiqish token) ≈ **$0,2 (~2–3 ming so'm)**, OCR bilan ~5 ming so'm/oy — Start tarifining (49 000) ~5–10% i. Prompt caching va Batch (−50%) bilan yana arzonlashadi. Aniq raqam pilotda o'lchanadi |
| Ollama + lokal model, oddiy kompyuterda (8–16 GB RAM, GPU yo'q) | **MVP'da yo'q** | Bunday kompyuterda faqat ~1–8B modellar sig'adi, CPU'da sekin (soniyasiga bir necha so'z). O'zbek tili uchun kichik ochiq modellar "past-resurs til" sifatida zaif baholangan; ochiq modellar ichida eng yaxshisi Qwen2.5 **72B** (TUMLU) — oddiy kompyuterga sig'maydi (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 1-bo'lim). Rasmdan o'qish (OCR) uchun vision model yanada og'ir |
| Lokal modelni o'zimiz o'qitish (fine-tune) | **Hozir yo'q, keyin ko'rib chiqiladi** | Minglab sifatli o'zbekcha misol, GPU va doimiy qo'llab-quvvatlash kerak. Faqat tor vazifalar (masalan tovar nomini toifaga ajratish) uchun, pilotdan real ma'lumot to'plangandan keyin |

**Mavjud tajriba — `E:/Project/universal_ai_platform` (2026-10-14 o'rganildi):** u yerda AI `claude -p --output-format json` CLI subprocess + obuna tokeni (`CLAUDE_CODE_OAUTH_TOKEN`) orqali ishlaydi; har kompaniya uchun alohida deploy, ichki B2B vosita. O'sha loyihaning o'z hujjatlari ko'rsatgan cheklovlar: har so'rovga ~8–23 soniya kechikish, streaming yo'q, obunaning 5 soatlik limiti barcha foydalanuvchilarga umumiy (`docs/AIOS.md:386-387`), shartlar egasi tomonidan tasdiqlanmagan (`deploy/README.md:38`). ERP — yuzlab tashqi mijozli SaaS, shuning uchun **transport API kaliti orqali** bo'ladi, lekin quyidagilar **qayta ishlatiladi**:
- port interfeyslari (`domain/ports/claude_port.py`, `text_completion_port.py`) → ERP'dagi `AiProvider`;
- CLI adapteridagi himoyalar: timeout, retry + backoff, circuit breaker (`infrastructure/claude/cli_claude.py`) — API adapteriga ko'chiriladi;
- token/xarajat hisobi (`domain/usage.py`), readiness tekshiruvi (`health_service.py`);
- o'zbek/rus intent prompti, "raqamni kod beradi" qoidalari, `narration_guard.py` (AI matnini deterministik tekshirish);
- STT: Vosk (o'zbek lotin) — AI-02 keyingi bosqichi uchun.
CLI+obuna adapteri faqat **ishlab chiqish/demo** muhitida ixtiyoriy qoladi (`fake | cli | api` rejimlari).

**Arxitektura qoidalari:**
- AI provayderi bitta interfeys orqali ulanadi (`AiProvider`), shunda keyin model/provayder almashtirish kodni buzmaydi.
- "Kod hisoblaydi, AI tushuntiradi" — pul, soliq, qoldiq hech qachon AI'ga bog'liq emas. Internet yo'q bo'lsa kassa va hisob to'liq ishlaydi, faqat AI funksiyalari vaqtincha o'chadi.
- Har bir tenant uchun oylik AI limiti (token/so'rov) — tarifga qarab; limit tugasa AI to'xtaydi, tizim ishlayveradi.
- API kaliti faqat serverda; mijoz qurilmasiga hech qachon tushmaydi.
- Lokal model faqat kelajakdagi variant: kuchli server (GPU) bilan, o'zbek tili sifati sinov to'plamida Claude'ga yaqin chiqsa.

## Ochiq savollar

1. Vision-LLM OCR (AI-03) uchun aniq narx (1M token yoki rasm-boshiga narx) `texnik/05-ozbek-tilidagi-ai.md` 2.2-bo'limida alohida ko'rsatilmagan — faqat matn narxi bor, vision-narx aniqlashtirish kerak (meros: `texnik/05-ozbek-tilidagi-ai.md`, Ochiq savollar).
2. Kirill-lotin aralash O'zbekiston hujjatlari (faktura, yuk xati, chek) uchun OCR/vision-LLM aniqligi — mustaqil benchmark topilmadi, AI-03 uchun MVP ishga tushishidan oldin mahalliy pilot-sinov shart (meros: `texnik/05-ozbek-tilidagi-ai.md`, Ochiq savollar).
3. Shovqinli do'kon muhitida STT aniqligi (AI-02 uchun) — hech qanday manbada topilmadi, keyingi bosqichga o'tishdan oldin pilot kerak (meros: `texnik/05-ozbek-tilidagi-ai.md`, Ochiq savollar).
4. Narx optimallashtirish tavsiyasi (AI-10) uchun yondashuv va aniqlik — texnik tadqiqotda batafsil o'rganilmagan, alohida tadqiqot kerak bo'lishi mumkin.
5. Davlat hisoboti tafovutini aniqlash (AI-05) uchun my.soliq.uz'dan dasturiy o'qish yo'li yo'qligi sababli, AI tushuntirishi qanday manba ma'lumotiga (qo'lda yuklangan hisobot fayli yoki boshqa) asoslanishi — Arxitektura jamoasi bilan kelishish kerak (meros: `texnik/00-xulosa-va-ochiq-savollar.md`, Ochiq savol #7).

## Manbalar

- `research_notes/texnik/05-ozbek-tilidagi-ai.md` — asosiy manba (LLM/STT/OCR imkoniyatlari, narxlar, MVP baholash jadvali, lokalizatsiya).
- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` — markaziy oqim (davlat hisobotini solishtirish), Asl belgisi jarima xavfi, ochiq savollar.
- `research_notes/texnik/03-efaktura-va-tolov.md` — e-faktura/e-TTN majburiyligi (qog'oz shakl faqat texnik uzilishda), ochiq banking holati (AI-03, AI-08 uchun).
- `research_notes/AI ERP startap Ozbekistonda/05_ai_funksiyalar.md` — global ERP AI funksiyalari, "code computes, AI explains" tamoyili, Uzbek SME og'riq-feature jadvali.
- `spec/README.md` — asosiy qarorlar (noldan qurilgan, tashqi buxgalteriya/ERP tizimiga bog'liq emas, 18 modul, davlat hisobotini solishtirish 5 kalendar kun).
