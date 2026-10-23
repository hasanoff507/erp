# AI funksiyalar — MVP da nima real

**Maqsad:** MVP'da qaysi AI funksiyalar real ishlatiladi — hukm, sabab, chegara, xavf va xarajat har biri uchun.
**Kim uchun:** Backend/AI dasturchilar, mahsulot egasi.
**Bog'liq fayllar:** `22-ai-qatlami.md`, `03-modullar-talablari.md`, `15-xavfsizlik-va-audit.md` (§5.2 shaxsiy ma'lumot), `27-backlog.md`.
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. MVP uchun **4 ta AI funksiya real**: AI-01 (umumiy biznes savol-javob chat, "bugun qancha foyda?"), **AI-03** (qog'oz faktura/yuk xati/chek fotosidan OCR, pilot bilan, torroq qamrovda — 2-band), AI-05 (davlat hisoboti tafovutini tushuntirish) va AI-06 (debitorlik/nasiya eslatma matni) — barchasi "kod hisoblaydi, AI tushuntiradi" tamoyili bilan (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim; qaror #16).
2. **Arxitektura qoidasi — har bir funksiyada majburiy**: raqamni (foyda, qoldiq, tafovut summasi, risk balli) doim kod/SQL hisoblaydi; AI/LLM faqat o'zbek tilida tushuntiradi, matn yozadi yoki tavsiya beradi — hech qachon raqamni o'zi "o'ylab topmaydi" (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, Xulosa #8; `AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, "Architecture principle").
3. **AI hech qachon davlat tizimiga (OFD, Soliq, CRPT Turon, Didox/Faktura.uz) hujjatni o'zi yubormaydi** — faqat loyiha/tavsiya tayyorlaydi, yuborishni odam (Buxgalter/Menejer) tasdiqlaydi. Sabab: AI xatosi bo'lsa ham, yuridik javobgarlik va jarima xavfi (masalan Asl belgisi skanerlash xatosi aylanmaning 20%igacha jarima) odam nazoratisiz oshadi (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #6).
4. **Hozircha real emas**: AI-04 (qo'lda yozilgan "nasiya daftari" OCR) — kirill qo'lyozma uchun hech qanday benchmark yo'q (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim).
5. **Keyingi bosqichga qoldirilgan**: AI-02 (ovozli savol-javob/STT), AI-07 (POS/o'g'irlik anomaliya aniqlash — yuqori murakkablik, qimmat infratuzilma), AI-08 (bank tranzaksiya avtomatik kategoriyalash), AI-09 (talab bashorati/buyurtma tavsiyasi), AI-10 (narx optimallashtirish tavsiyasi) va AI-11 (kundalik ovozli brifing/TTS) — sabab har birida yo yetarli tarixiy ma'lumot yo'q, yo mahalliy aniqlik raqami ochiq manbada topilmadi, yo infratuzilma MVP uchun ortiqcha.
6. **O'zbek tili uchun rasmiy LLM benchmark umuman yo'q** (Claude/GPT/Gemini) — bu barcha funksiyalar uchun umumiy chegara: aniqlik raqamlari ingliz-tilidagi benchmarklardan olingan, o'zbekcha/kirill matn uchun MVP davrida mahalliy pilot-sinov shart (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, Asosiy xulosa #1).
7. Model/narx — rasmiy narx sahifalaridan: matn/tushuntirish va hujjat OCR (AI-03, vision) uchun standart model **Claude Haiku 5.5** (`claude-haiku-5-5`, $0,10 kirish / $0,50 chiqish per 1M token, prompt ≤ 100 000 token bo'lganda; uzunroq promptda $0,50/$2,50; kesh o'qish $0,01; Batch −50%); past ishonchda yoki murakkab ko'p bosqichli tahlilda **Claude Sonnet 5.5** ($2/$10). Claude Haiku 4.5 ($1/$5) — legacy, ishlatilmaydi. Rasm tokeni = ⌈w/28⌉×⌈h/28⌉ (≤ 4 784 token, uzun tomon ≤ 2 576 px) — `research_notes/ochiq-savollar/P6-uskuna-ai-narx.md` (OQ-077). So'm xarajati Markaziy bankning kunlik rasmiy kursi bilan hisoblanadi (`fx_rates`, `ai_requests.fx_rate_used`; olinmasa `ERP_FX_USD_UZS_FALLBACK = 12 500`) (qaror #55).
8. Shaxsiy ma'lumot (qaror #61): lokalizatsiya majburiyati faqat biometrik/genetik/telekom ma'lumotga tegishli (ZRU-547 27-1-modda), lekin **chet elga uzatish** alohida qoida bilan tartibga solinadi (15-modda, VMQ-415 — AQSh faqat DPF ishtirokchilari uchun, Anthropic DPF'da emas). Shuning uchun AI'ga yuborishdan oldin jismoniy shaxsga oid maydonlar (mijoz/kontragent F.I.Sh., telefon, JSHSHIR, YaTT STIR, manzil) tokenga **majburiy maskalanadi** (har so'rov uchun xotiradagi xarita, `22-ai-qatlami.md` §7) — tenant o'chira olmaydi; javob qaytgach kod tokenni asl qiymatga qaytaradi. Maskalab bo'lmaydigan AI-03 rasmlari faqat tenant chegaradan tashqari uzatishga rozilik bergandan keyin yuboriladi (`settings.ai_cross_border_enabled`, faqat `POST /tenant/consents` orqali — ro'yxatdan o'tishda BO-21 yoki BO-14 sozlamalarida); rozilik yo'q — AI-03 o'chiq (`research_notes/ochiq-savollar/P4-huquq-hosting.md` §2).
9. Cheklovlar (qaror #55): `POST /ai/chat` — foydalanuvchiga 10 so'rov/daqiqa, tenantga 300 so'rov/kun, ustidan oylik token budjeti → `429 RATE_LIMITED`; OCR past ishonchi xato emas — `200` javobda `low_confidence_fields[]` (UI maydonni sariq qiladi).

---

## 1. O'zbek tilida savol-javob (Q&A)

### AI-01: Umumiy biznes savol-javob chat

- **Hukm**: **MVP**.
- **Sabab**: Global ERP vendorlari (Xero JAX, QuickBooks Intuit Assist, Zoho Zia) buni allaqachon "code computes, AI explains" tamoyili bilan amalga oshirgan; LLM raqamni o'zi hisoblamaydi, faqat SQL natijasini o'zbek tilida tabiiy shaklda tushuntiradi — xato darajasi past (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali: "Past-o'rta"; `AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, 7-band).
- **Misollar**:
  1. So'rov: "Bugun qancha foyda qildim?" → Javob: "Bugun sof foyda 1 240 000 so'm (kod hisoblagan). Kechagiga nisbatan 8% ko'p — asosiy sabab ichimlik toifasidagi sotuv o'sishi (sabab ham toifalar bo'yicha farqni kod hisoblagan natija, AI faqat uni so'z bilan ifodalaydi — AI o'zi sabab o'ylab topmaydi)."
  2. So'rov: "Shu oy eng ko'p sotilgan 5 mahsulotni ayt" → Javob: kod SQL orqali TOP-5 ro'yxatini chiqaradi, AI uni ro'yxat shaklida o'zbekcha izoh bilan taqdim etadi.
  3. So'rov: "Omborda qaysi tovarlar tugayapti?" → Javob: M04 (ombor qoldig'i) jadvalidan kod minimal qoldiq qoidasi bo'yicha tovarlarni tanlaydi, AI ro'yxatni ro'yxat+izoh shaklida taqdim etadi (buyurtma miqdori/tavsiyasi bermaydi — bu AI-09, Keyingi bosqich).
- **Chegaralar**: Aniqlik — javob matnining o'zbek tilidagi tabiiyligi tekshirilmagan (rasmiy benchmark yo'q); lotin/kirill aralash so'rovlarni tushunish darajasi tasdiqlanmagan — pilot kerak. Xato narxi — past, chunki raqamni kod hisoblaydi; faqat izoh/uslub xato bo'lishi mumkin, moliyaviy qaror AI izohiga emas, kod raqamiga asoslanadi.
- **Xavf va himoya**: LLM hech qachon raqamni o'zi generatsiya qilmasligi kod darajasida majburlanadi (prompt-da raqam kiritiladi, LLM faqat qayta ifodalaydi); javobda ko'rsatilgan har bir raqam tegishli SQL natijasiga bog'langan holda saqlanadi (audit uchun). Promptdagi shaxsiy maydonlar maskalanadi (qaror #61); so'rov chegarasi 10/daq, 300/kun (qaror #55).
- **Ulangan modul**: M12 (hisobotlar) — ma'lumot manbai; dolzarb holatda M01, M04, M08, M09, M10, M11 ga so'rov yuboradi.
- **Model/xarajat**: Oddiy tushuntirish uchun **Claude Haiku 5.5** (`claude-haiku-5-5`, $0,10 kirish / $0,50 chiqish per 1M token, prompt ≤ 100 000 token bo'lganda; uzunroq promptda $0,50/$2,50; kesh o'qish $0,01; Batch −50%); murakkabroq ko'p bosqichli tahlil (bir nechta modul kesishmasi) uchun Claude Sonnet 5.5 ($2/$10).

### AI-02: Ovozli savol-javob (STT orqali)

- **Hukm**: **Keyingi bosqich**.
- **Sabab**: Shovqinli do'kon muhitida o'zbek tili uchun STT aniqligi (WER) bo'yicha hech qanday manbada raqam topilmadi (Whisper, Yandex SpeechKit, Google Cloud STT — uchtasida ham); bu "ochiq manbada topilmadi" deb aniq belgilangan amaliy xavf, mahalliy pilot-sinov talab qiladi (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 2-bo'lim va Ochiq savollar).
- **Misollar**: (pilotdan keyin rejalashtirilgan, hozircha amalga oshirilmaydi) — "Ovoz bilan: bugungi savdo qancha?" kabi so'rovlar faqat matnli chat (AI-01) orqali ishlaydi, ovozli kiritish keyingi bosqichda qo'shiladi.
- **Chegaralar**: Eng yaqin raqam — toza o'qilgan nutqda NavAI whisper-medium-uzbek WER 7,4–14,1% (nomlar eng zaif), Google STT uz-UZ uchun WER e'lon qilinmagan; shovqinli do'kon uchun ma'lumot yo'q. Yoqish sharti: 50 ibora × 3 shovqin darajasi, WER ≤ 15% (`ai.stt_enabled=false`, `SttPort`) — 26 #20 (OQ-079).
- **Xavf va himoya**: Noto'g'ri tanilgan ovozli buyruq xato amalga (masalan noto'g'ri chegirma) olib kelmasligi uchun MVP'da ovozli kiritish ishlatilmaydi; matnli chat (AI-01) orqali asosiy funksiya ta'minlanadi.
- **Ulangan modul**: M12 (hisobotlar) — AI-01 bilan bir xil ma'lumot manbalari.
- **Model/xarajat**: Baholanmagan — MVP'da ishlatilmaydi.

---

## 2. Hujjat OCR (yuk xati, faktura, chek)

### AI-03: Qog'oz hujjat (yuk xati/faktura/chek) fotosidan ma'lumot chiqarish

- **Hukm**: **MVP** (pilot bilan, qog'oz hujjatlar bilan cheklangan qamrov) (qaror #16).
- **Qamrov**: Soliq kodeksiga ko'ra (2019-12-30) QQS to'lovchilar o'rtasidagi fakturalar faqat elektron axborot tizimida tuziladi, saqlanadi va hisobga olinadi; qog'oz shakli faqat **texnik uzilish** holatida ruxsat etiladi (`research_notes/texnik/03-efaktura-va-tolov.md`, 26-qator). Shuning uchun QQS to'lovchi yetkazib beruvchidan kelgan standart e-faktura/e-TTN **OCR orqali emas**, EDO operatori (Didox/Faktura.uz) orqali tuzilgan ma'lumot sifatida tizimga import qilinadi. AI-03 faqat quyidagi qog'oz holatlar bilan cheklanadi: (a) QQS to'lovchi bo'lmagan yoki norasmiy yetkazib beruvchining qog'oz yuk xati, (b) texnik uzilish davridagi qog'oz faktura, (c) mijozga berilgan/qaytarish uchun qog'oz chek.
- **Sabab**: Multimodal vision-LLM toza chop etilgan hujjat rasmidan tuzilgan maydonlarni (summa, sana, MXIK kodi) 87–97% aniqlik bilan chiqaradi — bu klassik shablonli OCR'dan ko'ra amaliy MVP yo'li; o'zbek bosma sahifalarida ochiq modellar WER 7,9–12% (Qwen3), fine-tuned uzocr-8b 1,42% (kirill 1,74%) — faktura/telefon rasmlari uchun raqam yo'q, shuning uchun pilot bilan cheklanadi (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 3 va 4-bo'limlar; `research_notes/ochiq-savollar/D-qarorlar-va-E-standartlar.md` OQ-078).
- **Misollar**:
  1. Omborchi QQS to'lovchi bo'lmagan mayda yetkazib beruvchidan kelgan qog'oz yuk xatining fotosini yuklaydi → AI tovar nomi, miqdor, narx, umumiy summa maydonlarini tuzilgan shaklda chiqaradi → foydalanuvchi tasdiqlagandan keyin M07 (xarid) hujjatiga aylanadi.
  2. Texnik uzilish tufayli qog'oz shaklda tuzilgan faktura fotosi yuklanadi → AI sana, MXIK kodi, QQS summasini ajratadi → Buxgalter ko'rib chiqadi, xato bo'lsa qo'lda tuzatadi, so'ng tasdiqlaydi.
  3. Mijozga berilgan qog'oz chek fotosi (qaytarish uchun) yuklanadi → AI chek raqami va summani o'qiydi → M02 (qaytarish) jarayoniga mos tovar/sana topiladi.
- **Chegaralar**: Aniqlik — toza faktura uchun 92,71–96,50% (Gemini 2.5 Pro), 94,75% (Gemini 3 Pro), **~88% (GPT 5.2/GPT-5 mini** — businesswaretech.com 2026 benchmark), chek uchun 84,40% (GPT-4o) — 91,15% (Gemini 1.5 Pro); bularning barchasi ingliz-tilidagi benchmark, **kirill+lotin+rus aralash O'zbekiston hujjatlari uchun mustaqil raqam yo'q** — ichki pilot `eval/ocr_uz` (100 rasm: 50 kirill, 50 lotin) bilan o'lchanadi, shungacha `ai.ocr_enabled=false` (tenant bo'yicha yoqiladi) — 26 #19 (OQ-078). **Qabul chegarasi va inson tekshiruvi**: AI ishonch darajasi (confidence) past bo'lgan maydonlar (masalan summa/sana aniq o'qilmagan) avtomatik "past ishonch" belgisi bilan ajratiladi va foydalanuvchi tasdig'isiz hujjatga kiritilmaydi. **AI-03 ishga tushirish sharti — maydon bo'yicha aniq chegara** (qaror #23): 100 ta O'zbekiston hujjatidan iborat sinov to'plamida **summa ≥ 95%**, **sana ≥ 90%**, **miqdor va tovar nomi ≥ 80%** aniqlik ko'rsatilishi kerak; past ishonchli maydon har doim sariq belgilanadi. Agar summa yoki sana aniqligi 90%dan past chiqsa — AI-03 pilotga chiqarilmaydi (sabab: pul maydonidagi xato eng qimmat, shuning uchun eng qattiq chegara — `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #10). Keyin tekshiriladi: 100 hujjatlik to'plam (≈40% toza, 40% foto/skaner, 20% qo'lda yozilgan; lotin/kirill/rus) bo'yicha haqiqiy natija. Xato narxi — o'rta: noto'g'ri o'qilgan summa/miqdor moliyaviy hujjatga xato kiritilishi mumkin, shuning uchun AI natijasi har doim foydalanuvchi tasdig'idan o'tadi, avtomatik tasdiqlanmaydi.
- **Xavf va himoya**: AI hujjatni o'zi davlat tizimiga (Didox/Faktura.uz, e-TTN) yubormaydi — faqat ichki hujjat loyihasini tayyorlaydi; yakuniy tasdiq va yuborish odam tomonidan amalga oshiriladi. Standart QQS to'lovchilar orasidagi elektron faktura/e-TTN AI-03 orqali OCR qilinmaydi — EDO operatori orqali import qilinadi (yuqoridagi qamrov eslatmasi). Skanerlangan/burchak qiyshaygan rasmlarda aniqlik pasayishi (87,46% chek darajasigacha) kutilishi kerak — foydalanuvchiga "tasdiqlang yoki tuzating" ekrani majburiy. Rasmni maskalab bo'lmaydi (yetkazib beruvchi rahbari ismi bo'lishi mumkin) — rasm faqat `settings.ai_cross_border_enabled=true` (tenant roziligi) bo'lsa yuboriladi, aks holda AI-03 o'chiq (qaror #61).
- **Ulangan modul**: M07 (xarid), M02 (qaytarish); natija M04 (ombor qoldig'i) va M11 (buxgalteriya) ga ta'sir qiladi.
- **Model/xarajat**: Standart — Claude Haiku 5.5 (vision qo'llab-quvvatlanadi); maydon ishonchi chegaradan past bo'lsa Sonnet 5.5 ga eskalatsiya. Rasm narxi = vizual token × kirish narxi; vizual token = ⌈w/28⌉×⌈h/28⌉ (≤ 4 784); 2048 px'ga siqilgan rasm ≈ 3 850–4 800 token → Haiku 5.5 bilan ≈ 7,7 so'm/rasm, Sonnet 5.5 bilan ≈ 153 so'm/rasm (P6 OQ-077, CBU kursi 2026-10-16). 1568 px varianti (≈ 2 350 token, narx ~42% kam) pilotda A/B qilinadi. Haiku 5.5 AI-03 chegaralarini (summa ≥95% va h.k.) pilotda o'tmasa — standart Sonnet 5.5 bo'ladi.

### AI-04: Qo'lda yozilgan "nasiya daftari"ni OCR qilish

- **Hukm**: **Hozircha real emas** (MVP'ga kiritilmaydi).
- **Sabab**: Kirill-o'zbek qo'lyozma uchun hech qanday ishonchli benchmark ochiq manbada topilmadi; umumiy qo'lyozma OCR aniqligi 63–95% oralig'ida juda keng va ishonchsiz (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 3-bo'lim va 7-xulosa).
- **Misollar**: MVP'da ishlatilmaydi. O'rniga: M08 (nasiya) modulida tuzilgan raqamli forma — Kassir mijozni tanlaydi, summani qo'lda kiritadi (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 7-xulosa va 3-bo'lim xulosasi: "tuzilgan raqamli forma qo'lyozma-OCR'dan ko'ra ishonchli muqobil"). Kelajakda (agar benchmark topilsa) kutilgan ko'rinish: Kassir qo'lda yozilgan daftar sahifasining fotosini yuklaydi → AI mijoz nomi va summani o'qib, tasdiqlash uchun ko'rsatadi.
- **Chegaralar**: Umumiy qo'lyozma OCR aniqligi 63–95% oralig'ida (yozuv sifatiga qarab juda o'zgaruvchan), kirill-o'zbek qo'lyozma uchun alohida benchmark yo'q — bu oraliq MVP uchun yetarlicha ishonchli emas (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 3-bo'lim).
- **Xavf va himoya**: Qo'llanilmaydi — xavfning o'zi oldini olish uchun funksiya MVP'dan chiqarib tashlangan.
- **Ulangan modul**: M08 (nasiya) — AI o'rniga qo'lda forma kiritiladi.
- **Model/xarajat**: Qo'llanilmaydi.

---

## 3. Anomaliya va ogohlantirishlar (shu jumladan davlat hisoboti tafovutlari)

### AI-05: Davlat hisoboti tafovutini tushuntirish va ogohlantirish

- **Hukm**: **MVP** (AI-01 "code computes, AI explains" tamoyilining davlat hisoboti solishtirish motoriga qo'llanishi; manba — foydalanuvchi my.soliq.uz kabinetidan yuklab olib tizimga yuklagan hisobot fayli (26 #22)).
- **Sabab**: 2026-01-01 dan soliq organlari QQS va aylanma solig'i hisobotlarini o'zi tuzadi (Soliq kodeksi 81-moddasi, O'RQ-1108), korxonaga **5 ish kuni** ichida (hisobot topshirish muddatidan kechiktirmay) kabinetda tasdiqlash yoki tuzatib taqdim etish imkoni beriladi (SK 81-modda 6–8-qism, 5-modda 7-qism) — bu mahsulotning markaziy qiymat taklifi. Tafovutni va uning sababini (qaysi hujjat/toifa/davr) **kod** moslashtirish orqali hisoblaydi; AI faqat kod chiqargan natijani o'zbek tilida tushuntiradi va tasdiq/tuzatish bo'yicha tavsiya beradi — "code computes, AI explains" tamoyili (`AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, Architecture principle). AI hech qachon sababni o'zi taxmin qilib yozmaydi.
- **Misollar**:
  1. Kod aniqlaydi: davlat QQS hisoboti 2 300 000 so'mga ichki hisobdan farq qiladi va kod hujjat darajasida moslashtiradi (3 ta sotuv e-fakturasi tizimga ulanmagan) → AI: "Tafovut sababi: 14-oktyabrdagi 3 ta sotuv e-fakturasi tizimga ulanmagan ko'rinadi (kod aniqlagan) — ro'yxatini ko'rish uchun bosing. 5 ish kuni ichida kabinetda tuzatib taqdim etish mumkin." QQS hisoboti hujjat darajasidagi reyestrlarni (e-faktura: STIR + faktura raqami + sana) o'z ichiga oladi — shuning uchun QQS bo'yicha hujjat darajasidagi moslashtirish mumkin (`research_notes/ochiq-savollar/P1-soliq-fiskal.md`, OQ-014).
  2. Aylanma solig'i hisoboti faqat yig'indi darajasida (5 manba satri: 0101 e-faktura, 0102 NKM/fiskal chek, 0103 marketplace, 0104 eksport, 0105 boshqa — va stavka bo'yicha) — kod manba satri bo'yicha solishtiradi, AI: "Bu oy aylanma hisobotining 0102 (fiskal chek) satri ichki hisobdan 2 300 000 so'mga farq qiladi; ichki tomonda shu davrda OFD tasdig'ini olmagan 12 ta chek bor (kod aniqlagan) — ro'yxatni ko'ring."
  3. Kod aniqlaydi: tafovut yo'q, hisobotlar mos → AI: "Bu oy davlat hisoboti va ichki hisobingiz to'liq mos keldi, qo'shimcha harakat kerak emas."
- **Chegaralar**: Ommaviy my.soliq.uz API yo'q (yagona kanal — shaxsiy kabinet, VM 736 3¹-ilova 10-band) — manba ma'lumoti foydalanuvchi yuklagan hisobot fayli (26 #41 (OQ-014)). Tushuntirish QQS bo'yicha hujjat darajasida (misol 1), aylanma bo'yicha manba satri darajasida (misol 2). Xato narxi — **yuqori** agar AI tushuntirishi noto'g'ri bo'lsa (masalan sababni xato ko'rsatsa) foydalanuvchi noto'g'ri qaror (dispute bermaslik) qabul qilishi mumkin; shuning uchun tushuntirish doim kod aniqlagan manba hujjatlarga (sana, hujjat raqami) havola bilan beriladi, foydalanuvchi o'zi tekshiradi.
- **Xavf va himoya**: AI hech qachon tuzatishni yoki tasdiqni my.soliq.uz'ga o'zi yubormaydi — faqat tavsiya va tushuntirish beradi, kabinetda tasdiqlash/tuzatib taqdim etish Buxgalter tomonidan qo'lda amalga oshiriladi. Tafovut summasi doim kod tomonidan hisoblanadi, AI undan foydalanadi, o'zi qayta hisoblamaydi.
- **Ulangan modul**: M10 (QQS), M11 (buxgalteriya), M12 (hisobotlar).
- **Model/xarajat**: Claude Sonnet 5.5 ($2/$10 per 1M token) — ko'p hujjatni taqqoslab tushuntirish murakkabroq fikrlash talab qiladi, shuning uchun eng arzon model emas.

### AI-06: Debitorlik (nasiya) risk skorlash va eslatma matni

- **Hukm**: **MVP**.
- **Sabab**: Risk belgisini (qancha kun kechikkan, qancha marta kechiktirgan) kod/qoida hisoblaydi; LLM faqat o'zbekcha eslatma matnini generatsiya qiladi — xavf past, chunki raqamni AI o'zi hisoblamaydi (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali: "Past").
- **Misollar**:
  1. Kod aniqlaydi: mijoz A 15 kundan beri 450 000 so'm qarzdor → AI matn yozadi: "Hurmatli [mijoz], 450 000 so'm qarzingiz 15 kundan beri kechikdi. Iltimos, imkon qadar tezroq to'lang."
  2. Kod aniqlaydi: mijoz B risk balli yuqori (3 marta kechiktirgan) → AI Menejerga: "Mijoz B yuqori risk toifasida — keyingi nasiyani cheklashni ko'rib chiqing."
  3. Buxgalter so'raydi: "Eng ko'p qarzdor 5 mijozni ko'rsat" → kod ro'yxatni chiqaradi, AI uni tartiblab, har biriga qisqa izoh qo'shadi.
- **Chegaralar**: Risk balli qoidasi sodda (kechikkan kun/marta soni) bo'lishi kerak — murakkab ML skorlash tarixiy ma'lumot yetarli bo'lmagani uchun MVP'da yo'q. Xato narxi — past: eng yomon holatda matn uslubi noqulay chiqadi, lekin risk balli va summa har doim kod natijasi.
- **Xavf va himoya**: Eslatma matni avtomatik yuborilishidan oldin Menejer/Kassir tasdig'idan o'tishi **majburiy** (Asosiy xulosa #3: AI hujjat/xabarni o'zi yubormaydi) — AI faqat loyiha matnini tayyorlaydi, yuborishni odam amalga oshiradi. Mijoz ismi va telefoni promptga token ("[mijoz]") sifatida boradi, matnga kod qo'yadi (qaror #61).
- **Ulangan modul**: M08 (nasiya).
- **Kanal**: Telegram (M18, US-M08-08) va SMS (`kod-uchun/21-integratsiyalar.md` §10) spec'da bor; MVP'da eslatma Telegram + ekranda ko'rsatish orqali; SMS (Eskiz) — faqat zaxira kanal (qaror #34).
- **Model/xarajat**: **Claude Haiku 5.5** (`claude-haiku-5-5`, $0,10 kirish / $0,50 chiqish per 1M token, prompt ≤ 100 000 token bo'lganda; uzunroq promptda $0,50/$2,50; kesh o'qish $0,01; Batch −50%) — oddiy matn generatsiyasi, eng arzon model yetarli.

### AI-07: POS/o'g'irlik anomaliya aniqlash (behavioral + video)

- **Hukm**: **Keyingi bosqich (yuqori murakkablik)**.
- **Sabab**: Video+POS integratsiyasi va behavioral model qimmat infratuzilma talab qiladi (kamera, saqlash, qayta ishlash); global misollarda ham bu alohida qimmat qatlam — MVP uchun ortiqcha deb baholangan (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali: "Keyingi bosqich / yuqori murakkablik").
- **Misollar**: MVP'da ishlatilmaydi. Keyingi bosqichda kutilgan ko'rinish: Menejer so'raydi "Bugun shubhali operatsiyalar bormi?" → AI (kod aniqlagan ko'p bekor qilingan chek/chegirma hodisalari asosida): "Kassir X bugun 7 marta chekni bekor qildi — odatdagi o'rtachadan (1-2) yuqori, tekshirib ko'rish tavsiya etiladi." MVP'da esa o'rniga M13 (huquqlar) orqali oddiy qoida-asosli ogohlantirish (masalan ko'p bekor qilingan chek chegarasidan oshganda) mumkin — bu AI emas, kod/qoida darajasida, shu sabab AI-nn ro'yxatiga kiritilmagan.
- **Chegaralar**: Texnik tadqiqotda O'zbekiston-specific aniqlik raqami yo'q, global raqamlar (masalan video+POS orqali 50% shrinkage kamayishi) ham faqat market tadqiqotida, 05-fayl (asosiy manba) tomonidan tasdiqlanmagan (`AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, 4-band) — **manbasiz raqam sifatida MVP qaroriga asos qilib olinmadi**; video-asosli yechim uchun kamera infratuzilmasi xarajati ham baholanmagan.
- **Xavf va himoya**: Ishga tushganda ham AI faqat ogohlantiradi, xodimga nisbatan avtomatik chora (ish haqidan ushlab qolish, ishdan bo'shatish) ko'rmaydi — yakuniy qaror Menejer/Egasi tomonidan qabul qilinadi.
- **Ulangan modul**: M01 (kassa), M13 (huquqlar) — keyingi bosqichda.
- **Model/xarajat**: Baholanmagan.

### AI-08: Bank tranzaksiya avtomatik kategoriyalash

- **Hukm**: **Keyingi bosqich**.
- **Sabab**: O'zbekistonda ochiq bank API cheklangan (CBU'da faqat ma'lumotlar portali, dasturiy API yo'q), shuning uchun avtomatik kategoriyalash uchun ma'lumot manbai yetarli emas — xavf "Yuqori" deb baholangan (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali).
- **Misollar**: MVP'da ishlatilmaydi — bank ko'chirmasi (1CClientBankExchange .txt) BO-24 da kod qoidalari bilan bank tushumi tasdig'i qoralamalariga aylanadi (`POST /api/v1/bank-settlements/imports`), `post` — Buxgalter. Kelajakda kutilgan ko'rinish: AI faqat moslashtirish taklifini tushuntiradi: "Bu 15 tranzaksiyadan 12 tasi 'yetkazib beruvchiga to'lov' toifasiga mos keladi (kod qoida bo'yicha aniqlagan) — tasdiqlaysizmi?"
- **Chegaralar**: O'zbekistonda ochiq banking API yo'q — PQ-359 dagi 2026-09-01 muddati bajarilmagan, 2026-10-16 holatida CBU normativ hujjati yo'q; ma'lumot faqat yuklangan ko'chirma (de-fakto format — 1CClientBankExchange) orqali kiradi (`research_notes/ochiq-savollar/P3-tolovlar-bank.md`, OQ-038). Global vendorlardagi 85–95% aniqlik (QuickBooks, Xero) O'zbekiston bank format sharoitiga tatbiq etilmaydi — bu raqam **asosiy manbada (research_notes/texnik/05) tasdiqlanmagan, faqat market tadqiqotida**, shuning uchun MVP qaroriga asos bo'lmaydi.
- **Xavf va himoya**: Qo'llanilmaydi.
- **Ulangan modul**: M11 (buxgalteriya).
- **Model/xarajat**: Baholanmagan.

---

## 4. Tavsiyalar (buyurtma, narx)

### AI-09: Talab bashorati asosida qayta buyurtma tavsiyasi

- **Hukm**: **Keyingi bosqich**.
- **Sabab**: Klassik statistik/ML model talab qilinadi (LLM shart emas), bunga kamida bir necha oylik tarixiy savdo ma'lumoti kerak — MVP boshida bu ma'lumot hali to'planmagan (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali: "O'rta — yetarli tarixiy ma'lumot to'planishi kerak").
- **Misollar**: Ishlatilmaydi MVP'da. Keyingi bosqichda: "Tovar X 5 kundan keyin tugaydi, o'tgan oylardagi sotuv tendentsiyasiga ko'ra 200 dona buyurtma qilish tavsiya etiladi."
- **Chegaralar**: Global misollarda 20–50% xato kamayishi va 10–30% ombor xarajati tejash ko'rsatilgan, ammo bu raqamlar global vendorlar (Odoo, Zoho, Toast) uchun, O'zbekiston SME ma'lumotiga tatbiq etilmagan — bu raqam **faqat market tadqiqotida (`AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, 1-band), asosiy texnik manbada tasdiqlanmagan — taxmin**.
- **Xavf va himoya**: Qo'llanilmaydi (MVP'da yo'q) — ishga tushganda ham tavsiya faqat ko'rsatma bo'ladi, buyurtma avtomatik yuborilmaydi, Omborchi/Menejer tasdiqlaydi.
- **Ulangan modul**: M04 (ombor qoldig'i), M07 (xarid), M09 (narxlar).
- **Model/xarajat**: Baholanmagan — ML/statistik model, LLM narx jadvali bu yerga tatbiq etilmaydi.

### AI-10: Narx optimallashtirish tavsiyasi

- **Hukm**: **Keyingi bosqich**.
- **Sabab**: Asosiy texnik manba (`research_notes/texnik/05-ozbek-tilidagi-ai.md`) narx optimallashtirishni alohida baholamagan — faqat market tadqiqotida ("Narx taklifi | Price optimization from margins | Odoo, custom | Yuqori") qisqa eslatma bor, murakkablik "Yuqori" deb belgilangan (`AI ERP startap Ozbekistonda/05_ai_funksiyalar.md`, "Uzbek SME pain points" jadvali).
- **Misollar**: MVP'da ishlatilmaydi. Kelajakda kutilgan ko'rinish: Menejer so'raydi "Tovar Y narxini oshirsam bo'ladimi?" → AI (M09 narxlar va M11 buxgalteriya'dagi marja ma'lumoti asosida, kod hisoblagan): "Tovar Y'ning joriy marjasi 12% — raqobatchilar o'rtachasi haqida ma'lumot yo'q, shuning uchun aniq tavsiya berib bo'lmaydi."
- **Chegaralar**: MVP'da AI emas, qoida-asosidagi ogohlantirish (past marja / sekin aylanish ko'rsatkichi) — kod darajasida (26 #21); ML yondashuv keyingi bosqichda, yetarli tarixiy ma'lumot to'plangach.
- **Xavf va himoya**: Qo'llanilmaydi.
- **Ulangan modul**: M09 (narxlar).
- **Model/xarajat**: Baholanmagan.

### AI-11: Kundalik ovozli brifing (TTS)

- **Hukm**: **Keyingi bosqich**.
- **Sabab**: TTS tabiiyligi (Muxlisa/UzbekVoiceAI/Aisha) tekshirilmagan, hech qanday aniqlik/sifat raqami ochiq manbada yo'q — matnli brifing (AI-01 orqali) birinchi qadam bo'lishi tavsiya etiladi (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali: "O'rta — TTS tabiiyligi tekshirilmagan").
- **Misollar**: MVP'da ishlatilmaydi — o'rniga AI-01 orqali matnli kunlik xulosa. Kelajakda kutilgan ko'rinish: ertalab Egasi ilovani ochganda ovozli xabar eshitadi: "Xayrli tong! Kecha sof foyda 980 000 so'm bo'ldi, 2 ta tovar qoldig'i kam."
- **Chegaralar**: TTS tabiiyligi (talaffuz, urg'u) va shovqinli muhitda eshitilishi tekshirilmagan — hech qanday sifat/aniqlik raqami ochiq manbada yo'q (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim jadvali).
- **Xavf va himoya**: Qo'llanilmaydi.
- **Ulangan modul**: M12 (hisobotlar).
- **Model/xarajat**: Baholanmagan.

---

## 5. AI provayderi: obuna, API yoki lokal model

**Savol (foydalanuvchi):** AI uchun Claude Code CLI'ni obuna (Pro/Max) orqali ishlatish yoki Ollama'da lokal model (oddiy kompyuterda ishlaydigan) ishlatish.

| Variant | Xulosa | Sabab |
|---|---|---|
| Claude obunasi (Pro/Max) + Claude Code CLI / Agent SDK, mahsulot ichida | **Ishlatilmaydi** | Anthropic qoidasi: "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK. Use the API key authentication…" ([code.claude.com/docs/en/agent-sdk/overview](https://code.claude.com/docs/en/agent-sdk/overview)). Obuna bitta odam uchun; yuzlab do'kon so'rovlarini ko'tarmaydi (limitlar), bloklanish xavfi bor. Claude Code — **jamoa ilovani yozishi uchun** ishlatiladi, mahsulot ichida emas |
| **Claude API (Haiku 5.5, kerak bo'lsa Sonnet 5.5)** | **Asosiy yo'l** | Tijorat shartlari bo'yicha ruxsat; Haiku 5.5 $0,10 / $0,50 per 1M token (prompt ≤ 100 000). Tenant xarajati ~900–6 900 so'm/oy (yengil–o'rta; `25` §11, `22` §13, CBU kursi 12 011,65); og'ir profil oylik token budjeti bilan cheklanadi — yagona tarifning (99 000) ~1–7% i (qaror #22). Prompt caching va Batch (−50%) bilan arzonlashadi; haqiqiy raqam pilotda `ai_requests`dan o'lchanadi. Shaxsiy ma'lumot — maskalangan (qaror #61); ro'yxatdagi davlatda ishlov beradigan endpoint (masalan AWS Bedrock EU) — asoschi tanlovi, standart: rozilik + Anthropic API |
| Ollama + lokal model, oddiy kompyuterda (8–16 GB RAM, GPU yo'q) | **MVP'da yo'q** | Bunday kompyuterda faqat ~1–8B modellar sig'adi, CPU'da sekin (soniyasiga bir necha so'z). O'zbek tili uchun kichik ochiq modellar "past-resurs til" sifatida zaif baholangan; ochiq modellar ichida eng yaxshisi Qwen2.5 **72B** (TUMLU) — oddiy kompyuterga sig'maydi (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 1-bo'lim). Rasmdan o'qish (OCR) uchun vision model yanada og'ir |
| Lokal modelni o'zimiz o'qitish (fine-tune) | **Hozir yo'q, keyin ko'rib chiqiladi** | Minglab sifatli o'zbekcha misol, GPU va doimiy qo'llab-quvvatlash kerak. Faqat tor vazifalar (masalan tovar nomini toifaga ajratish) uchun, pilotdan real ma'lumot to'plangandan keyin |

**CLI+obuna transporti nega ishlatilmaydi:** `claude -p --output-format json` CLI subprocess + obuna tokeni orqali ishlash bitta-tenant/ichki vositalar uchun mos, lekin yuzlab tashqi mijozli SaaS uchun yaroqsiz: har so'rovga ~8–23 soniya kechikish, streaming yo'q, obunaning 5 soatlik limiti barcha foydalanuvchilarga umumiy bo'lib qoladi, shartlar bo'yicha ham tasdiqlanmagan. Shuning uchun ERP'da **transport API kaliti orqali** bo'ladi; quyidagilar — bizning standartimiz:
- port interfeysi — ERP'dagi `AiProvider`;
- CLI adapteridagi himoyalar: timeout, retry + backoff, circuit breaker — API adapterida ham qo'llaniladi;
- token/xarajat hisobi, readiness tekshiruvi;
- o'zbek/rus intent prompti, "raqamni kod beradi" qoidalari, `numeric_guard` (AI matnini deterministik tekshirish);
- STT: Vosk (o'zbek lotin) — AI-02 keyingi bosqichi uchun.
CLI+obuna adapteri faqat **ishlab chiqish/demo** muhitida ixtiyoriy qoladi (`fake | cli | api` rejimlari).

**Arxitektura qoidalari:**
- AI provayderi bitta interfeys orqali ulanadi (`AiProvider`), shunda keyin model/provayder almashtirish kodni buzmaydi.
- Promptga yuborishdan oldin shaxsiy maydonlar tokenga maskalanadi (so'rov ichidagi xotira xaritasi, `22-ai-qatlami.md` §7) — majburiy, o'chirib bo'lmaydi; AI-03 rasmlari faqat tenant roziligi bilan (`settings.ai_cross_border_enabled`) (qaror #61).
- "Kod hisoblaydi, AI tushuntiradi" — pul, soliq, qoldiq hech qachon AI'ga bog'liq emas. Internet yo'q bo'lsa kassa va hisob to'liq ishlaydi, faqat AI funksiyalari vaqtincha o'chadi.
- Har bir tenant uchun oylik AI limiti (token/so'rov) — yagona tarif ichiga kiradi (`05-mvp-chegarasi.md`, 3.3); limit tugasa AI to'xtaydi, tizim (kassa, ombor, buxgalteriya) to'liq ishlayveradi. **Limit tugaganda overage (qo'shimcha avtomatik to'lov) yo'q** (qaror #23): AI funksiyalari (AI-01, 03, 05, 06) shu oy davomida **keyingi oygacha to'xtaydi** yoki Egasiga tarifni/limitni oshirish taklif qilinadi; limitlar boshidanoq biroz kengroq qo'yiladi (AI xarajati tarifning ~1–6% i, mayda summalarni Click/Payme orqali yechish komissiya va murakkablik keltiradi). **Oldindan to'lanadigan "AI paket"** — faqat **pilotdan keyin**, agar tenantlarning ≥10% i limitga urilsa, kiritiladi (`spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #11). Keyin tekshiriladi: pilotda tenantlar limitga qanchalik tez-tez urilishi.
- API kaliti faqat serverda; mijoz qurilmasiga hech qachon tushmaydi.
- Lokal model faqat kelajakdagi variant: kuchli server (GPU) bilan, o'zbek tili sifati sinov to'plamida Claude'ga yaqin chiqsa.

## Ochiq savollar

Faqat tashqi javob kutayotgan bandlar (raqamlar barqaror):

2. Tashqi javob kerak: kirill-lotin aralash O'zbekiston hujjatlarida AI-03 aniqligi — ichki pilot `eval/ocr_uz` (100 rasm), chegara summa ≥95%, sana ≥90%, miqdor/nom ≥80% (qaror #23); interim: `ai.ocr_enabled=false` — 26 #19 (OQ-078).
3. Tashqi javob kerak: shovqinli do'kon muhitida STT aniqligi (AI-02) — 50 ibora × 3 shovqin darajasi, WER ≤ 15%; interim: `ai.stt_enabled=false` — 26 #20 (OQ-079).
6. Tashqi javob kerak: foydalanish shartlari va AI'ga chegaradan tashqari uzatish roziligi matni (yurist), maskalangan ma'lumot maqomi; interim: majburiy maskalash, `ai_cross_border_enabled=false` rozilikgacha — 26 #127 (OQ-042).

## Manbalar

- `research_notes/texnik/05-ozbek-tilidagi-ai.md` — asosiy manba (LLM/STT/OCR imkoniyatlari, narxlar, MVP baholash jadvali, lokalizatsiya).
- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` — markaziy oqim (davlat hisobotini solishtirish), Asl belgisi jarima xavfi, ochiq savollar.
- `research_notes/texnik/03-efaktura-va-tolov.md` — e-faktura/e-TTN majburiyligi (qog'oz shakl faqat texnik uzilishda), ochiq banking holati (AI-03, AI-08 uchun).
- `research_notes/AI ERP startap Ozbekistonda/05_ai_funksiyalar.md` — global ERP AI funksiyalari, "code computes, AI explains" tamoyili, Uzbek SME og'riq-feature jadvali.
- `spec/README.md` — asosiy qarorlar (noldan qurilgan, tashqi buxgalteriya/ERP tizimiga bog'liq emas, 18 modul, davlat hisobotini solishtirish 5 ish kuni).
- `research_notes/ochiq-savollar/` — P1 (OQ-013, OQ-014), P3 (OQ-038), P4 (OQ-040 shaxsiy ma'lumotni chet elga uzatish), P6 (OQ-077 rasm tokeni va narx), D-qarorlar (#55, OQ-078/079).
- `spec/kod-uchun/01-qarorlar.md` — qaror #16 (AI-03 MVP'da; 4 ta AI funksiya: AI-01, AI-03, AI-05, AI-06).
- `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` — tavsiya #10 (AI-03 ishga tushirish sharti — maydon bo'yicha chegara) va #11 (AI limit tugaganda — overage yo'q, keyingi oygacha to'xtash, pilotdan keyin prepaid paket).
