# O'zbek tilidagi AI: LLM, STT, OCR imkoniyatlari va MVP uchun real AI funksiyalar

## Asosiy xulosalar

1. **LLM**: Claude/GPT/Gemini'ning hech biri o'zbek tili uchun rasmiy benchmark e'lon qilmagan — barchasi faqat "umumiy ko'p tilli" qamrovga kiradi. Ochiq manbalarda faqat kichik ochiq modellar (Llama-3.2-1B, Qwen3-0.6B) uchun akademik benchmark topildi, ular esa aynan o'zbek tili uchun past-resurs til sifatida baholangan.
2. **Narx (2026-10-14, faqat rasmiy narx sahifalari: claude.com/pricing, developers.openai.com/api/docs/pricing, ai.google.dev/pricing)**: eng arzon ishlab chiqarish darajasidagi modellar — Claude **Haiku 5.5** ($0,10–0,50 kirish / $0,50–2,50 chiqish, 1M tok, prompt uzunligiga qarab), Gemini 2.5 Flash-Lite ($0,10/$0,40) va GPT-5-nano ($0,05/$0,40); kuchli umumiy vazifalar uchun Claude **Sonnet 5.5** (yoki Sonnet 5 — ikkisi ham $2/$10, bir xil narx) yoki GPT-5 ($1,25/$10) oqilona balans beradi. Anthropic'ning joriy ("Latest") modellari — Fable 5.1 ($10/$50), Opus 5.5 ($4/$20), **Sonnet 5.5** ($2/$10), **Haiku 5.5** ($0,10–0,50/$0,50–2,50); Sonnet 5 va Haiku 4.5 ($1/$5) endi "Legacy" toifasida. *(2026-10-14 tekshiruvida tuzatildi: avval "Sonnet 5 (5.5 emas)" deb Sonnet 5.5'ning mavjudligi rad etilgan edi va Haiku 5.5 umuman tilga olinmagan edi — ikkisi ham 2026-10-07 da chiqarilgan va claude.com/pricing'da "Latest Models" sifatida ko'rsatilgan.)*
3. **Ma'lumot lokalizatsiyasi**: 2026-yil 27-martdan kuchga kirgan tuzatish (Qonun "Shaxsiy ma'lumotlar to'g'risida"ga) faqat **biometrik, genetik va mahalliy telekom foydalanuvchi ma'lumotini** O'zbekistonda saqlashni majburiy qiladi; boshqa shaxsiy ma'lumotlar xavfsizlik talablariga rioya qilingan holda chet elga (demak — Claude/GPT/Gemini API'ga) yuborilishi mumkin ([Dentons](https://www.dentons.com/en/insights/articles/2026/march/31/uzbekistan-dismantles-strict-data-localization-regime)).
4. **STT**: faqat o'zbek tili uchun maxsus o'qitilgan Whisper modellari (NavAI, Hugging Face) WER 8,8–11,6% oralig'ida (domenga qarab 7,9%–17%); Yandex SpeechKit (2023-yildan, lotin yozuvi) va Google Cloud STT (2020-yildan, "uz-UZ" kodi) ham qo'llab-quvvatlaydi, lekin ikkisi uchun ham mustaqil WER raqami ochiq manbada topilmadi. Mahalliy startaplar (UzbekVoiceAI, Aisha AI) aniqlik foizini ommaga e'lon qilmagan — faqat marketing da'volari bor.
5. **Shovqinli do'kon muhitida STT aniqligi** — ochiq manbada hech qanday raqam topilmadi (qidirildi: Whisper/Yandex/Google + "noise"/"shovqin" + Uzbek); bu haqiqiy xavf — pilot sinov kerak.
6. **OCR**: tayyor chop etilgan hujjat (faktura, chek) uchun umumiy OCR 97–99,5% (ABBYY, Google Vision), lekin bu raqamlar asosan lotin-ingliz hujjatlari uchun; qo'lda yozilgan matn uchun aniqlik 63–95% oralig'ida keskin tushadi va kirill-o'zbek qo'lyozmasi uchun maxsus benchmark ochiq manbada topilmadi. Multimodal LLM (Gemini 3 Pro, GPT-5) "vision" rejimi tuzilgan faktura/chek rasmidan ma'lumot chiqarishda 92–97% aniqlik beradi (ingliz tilidagi benchmarklarda) — bu klassik OCR+shablon yondashuvidan ko'ra amaliy MVP yo'li.
7. **Qo'lda yozilgan "nasiya daftari"** — eng yuqori texnik xavfli funksiya: kirill qo'lyozma uchun hech qanday sonli benchmark topilmadi, umumiy qo'lyozma aniqligi (63–95%) juda keng oraliqda va ishonchsiz. MVP'da avtomatik OCR o'rniga tuzilgan raqamli kiritishni (forma) birinchi qadam qilish tavsiya etiladi.
8. MVP uchun real: debitorlik eslatmalari (LLM matn generatsiyasi + oddiy qoida), savol-javob chat ("bugun qancha foyda"), toza faktura/chek fotosidan OCR (vision-LLM orqali). Keyingi bosqich: talab bashorati, pul oqimi bashorati, bank tranzaksiya avtomatik kategoriyalash (CBU ochiq bank API cheklangan). Hozircha real emas / yuqori xavf: qo'lda yozilgan daftar OCR'i, video+POS anomaliya aniqlash (qimmat infratuzilma talab qiladi).

## 1. LLM: o'zbek tilida sifat, narx, lokalizatsiya

### 1.1 Sifat va benchmarklar

- Claude, GPT, Gemini — uchtasi ham Unicode va ko'p tilli darajada o'zbek tilini (lotin va kirill) qo'llab-quvvatlaydi, lekin hech biri rasmiy "Uzbek benchmark" raqamini chop etmagan (oldingi tadqiqot, `05_ai_funksiyalar.md`, tasdiqlandi — qayta qidirilganda ham yangi rasmiy raqam topilmadi).
- Akademik tadqiqot (2026) ochiq modellarni (Llama-3.2-1B-Instruct, Qwen3-0.6B) tarjima, matn tushunish va generatsiya bo'yicha o'zbek tilida "past-resurs til" sifatida sinab ko'rdi — o'zbek tili 60 million+ so'zlovchiga ega bo'lsa ham, NLP resurslari kam ([zenodo.org](https://zenodo.org/records/17223973)).
- TUMLU (turkiy tillar uchun unified benchmark, qozoq/qirg'iz/o'zbek/qoraqalpoq va h.k.) natijalariga ko'ra ochiq modellar orasida **Qwen2.5 72B Instruct** eng yaxshi natija ko'rsatdi; Llama 3.1 70B o'zining 8B versiyasidan sezilarli ustun ([aclanthology.org — TUMLU](https://aclanthology.org/2025.acl-long.1112.pdf)).
- Mahalliy loyihalar: **Salom AI** (salom-ai.uz) — o'zbekcha (lotin+kirill) tushunadigan birinchi AI, ochiq modellar (Llama, Mistral) asosida moslashtirilgan ([salom-ai.uz blog](https://salom-ai.uz/blog/llama-uzbek/)); **Tilmoch** — turkiy tillar uchun AI-tarjimon, $1,5 mln baholashga **2025-yil sentyabrida** (150 ming dollarlik investitsiya raundida) chiqqan ([digitalbusiness.kz, 2026-10-08](https://digitalbusiness.kz/en/2026-10-08/uzbekistanets-sozdal-ii-perevodchik-dlya-tyurkskih-yazikov-startap-otsenili-v-15-mln/) — maqola e'lon sanasi 2026-oktyabr, lekin matn va boshqa manbalar voqea sanasini 2025-sentyabr deb ko'rsatadi). *(2026-10-14 tekshiruvida tuzatildi: avval "2026-yil oktyabrda... chiqdi" deyilgan edi — bu maqola e'lon sanasini voqea sanasi bilan aralashtirgan; baholash aslida 2025-sentyabrda bo'lgan.)*; **TilLab** — o'zbek tili uchun ochiq-kodli "raqamli laboratoriya" (GitHub loyihasi, hobbi/tadqiqot darajasida) ([github.com/AbrorMusulmonov/tillab](https://github.com/AbrorMusulmonov/tillab)).
- Xulosa: mahalliy-maxsus LLM hali yetuk emas (asosan tarjima/chatbot darajasida); tizim uchun eng amaliy yo'l — umumiy ko'p tilli flagman modellardan (Claude/GPT/Gemini) foydalanish, chunki ular sifat jihatidan sinalgan va "code computes, AI explains" me'morchiligida raqamni emas, tilni generatsiya qiladi (xato darajasi past).

### 2.2 Narxlar (1M token uchun, **faqat rasmiy narx sahifalari**, 2026-10 holatiga)

**Tuzatish (birinchi qoralama, 2026-10-10)**: o'sha versiyada uchinchi-tomon agregator saytlar ishlatilgan va ba'zi tasdiqlanmagan model nomlari (GPT-5.4, GPT-5.5) olib tashlangan edi; shu jarayonda **Sonnet 5.5 ham noto'g'ri "tasdiqlanmagan" deb hisoblanib ro'yxatdan chiqarilgan edi — bu xato edi**. claude.com/pricing sahifasida Sonnet 5.5 (va Haiku 5.5) rasmiy ravishda "Latest Models" sifatida mavjud — ikkisi ham 2026-10-07 da chiqarilgan. Quyidagi jadval 2026-10-14 holatiga ko'ra claude.com/pricing, developers.openai.com/api/docs/pricing va ai.google.dev/pricing'dan olingan rasmiy model nomi/narxlarni aks ettiradi. *(2026-10-14 tekshiruvida tuzatildi.)*

| Model | Kirish ($/1M) | Chiqish ($/1M) | Holat | Manba |
|---|---|---|---|---|
| Claude Haiku 5.5 | 0,10–0,50* | 0,50–2,50* | Joriy (eng arzon) | [claude.com/pricing](https://claude.com/pricing) |
| Claude Haiku 4.5 | 1 | 5 | Legacy | [claude.com/pricing](https://claude.com/pricing) |
| Claude Sonnet 5.5 | 2 | 10 | Joriy | [claude.com/pricing](https://claude.com/pricing) |
| Claude Sonnet 5 | 2 | 10 | Legacy (Sonnet 5.5 bilan bir xil narx) | [claude.com/pricing](https://claude.com/pricing) |
| Claude Opus 5.5 | 4 | 20 | Joriy | [claude.com/pricing](https://claude.com/pricing) |
| Claude Fable 5.1 | 10 | 50 | Joriy | [claude.com/pricing](https://claude.com/pricing) |

*Haiku 5.5 narxi prompt uzunligiga qarab farqlanadi: ≤100K token — kirish $0,10 / chiqish $0,50; >100K token — kirish $0,50 / chiqish $2,50.
| GPT-5 | 1,25 | 10 | [developers.openai.com/api/docs/pricing](https://developers.openai.com/api/docs/pricing) |
| GPT-5-mini | 0,25 | 2 | [developers.openai.com/api/docs/pricing](https://developers.openai.com/api/docs/pricing) |
| GPT-5-nano | 0,05 | 0,40 | [developers.openai.com/api/docs/pricing](https://developers.openai.com/api/docs/pricing) |
| GPT-4o | 2,50 | 10 | [developers.openai.com/api/docs/pricing](https://developers.openai.com/api/docs/pricing) |
| GPT-4o-mini | 0,15 | 0,60 | [developers.openai.com/api/docs/pricing](https://developers.openai.com/api/docs/pricing) |
| Gemini 2.5 Flash-Lite | 0,10 | 0,40 | [ai.google.dev/pricing](https://ai.google.dev/pricing) |
| Gemini 2.5 Flash | 0,30 | 2,50 | [ai.google.dev/pricing](https://ai.google.dev/pricing) |
| Gemini 2.5 Pro (≤200k token) | 1,25 | 10 | [ai.google.dev/pricing](https://ai.google.dev/pricing) |
| Gemini 3.8 Flash (2026 yil 31-dekabrgacha) | 0,75 | 3,75 | [ai.google.dev/pricing](https://ai.google.dev/pricing) |
| Gemini 3.1 Pro Preview (≤200k token) | 2 | 12 | [ai.google.dev/pricing](https://ai.google.dev/pricing) |

Eslatma: OpenAI'ning rasmiy narx sahifasida yuqoridagilardan tashqari ko'plab qo'shimcha model (GPT-4.1, o1/o3/o4-mini va h.k.) bor; bu jadvalga faqat eng amaliy/tez-tez ishlatiladigan va boshqa (ikkinchi) manba bilan ham mos kelgan modellar kiritildi — to'liq ro'yxat uchun rasmiy sahifaning o'ziga qarang.

### 1.3 Ma'lumot lokalizatsiyasi va chet el API

2026-yil 27-martdan kuchga kirgan "Shaxsiy ma'lumotlar to'g'risida"gi qonunga tuzatish ([Dentons huquqiy tahlili](https://www.dentons.com/en/insights/articles/2026/march/31/uzbekistan-dismantles-strict-data-localization-regime); [daryo.uz](https://daryo.uz/en/2026/03/29/uzbekistan-amends-personal-data-law-for-domestic-storage-and-regulated-foreign-processing/)):

- Avval: FUQAROLARNING BARCHA shaxsiy ma'lumoti O'zbekiston hududida saqlanishi majburiy edi.
- Endi: faqat **biometrik ma'lumot, genetik ma'lumot va mahalliy telekom-operator foydalanuvchisi ma'lumoti** majburiy lokalizatsiyaga tushadi.
- Boshqa shaxsiy ma'lumotlar (mijoz ismi, telefon raqami, xarid tarixi) xavfsizlik talablari (axborot xavfsizligi, xalqaro standartlarga muvofiqlik yoki davlat organi nazorati) bajarilgan holda **chet elda** (demak — Claude/GPT/Gemini API serverlarida) qayta ishlanishi mumkin.
- Amaliy natija: Tizim Claude/GPT/Gemini API'dan foydalanishi mumkin, lekin mijozning pasport/biometrik ma'lumotini (agar kelajakda to'plansa) chet el API'ga yubormasligi kerak.

## 2. STT (ovozdan matn)

| Yechim | Til/skript | Aniqlik (WER yoki %) | Manba |
|---|---|---|---|
| Whisper (NavAI fine-tune, Hugging Face) — medium | O'zbek, lotin | Makro-WER 9,73% / mikro-WER 8,81% | [huggingface.co/Mannon/whisper-medium-uzbek](https://huggingface.co/Mannon/whisper-medium-uzbek) |
| Whisper (NavAI, small) | O'zbek | Makro 11,57% / mikro 10,69%; domen bo'yicha: FLEURS 16,96%, Common Voice 9,58%, USC 11,81%, FeruzaSpeech 7,95% | [huggingface.co/Mannon/whisper-small-uzbek](https://huggingface.co/Mannon/whisper-small-uzbek) |
| Google Cloud Speech-to-Text | O'zbek (`uz-UZ`), 2020-yildan qo'shilgan; Chirp 3 modeli 85+ til/variantni qamrab oladi | Aniq WER raqami ochiq manbada topilmadi | [siliconangle.com](https://siliconangle.com/2020/03/05/google-cloud-extends-speech-text-service-7-new-languages/); [Google Cloud hujjati](https://docs.cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages) |
| Yandex SpeechKit | O'zbek, lotin yozuvi, 2023-yil iyundan (16-til); 2025-yil martda yangilangan | Aniq WER raqami ochiq manbada topilmadi; ming soatlab audio bilan o'qitilgan deyilgan | [habr.com](https://habr.com/ru/companies/yandex_cloud_and_infra/articles/741746/); [nuz.uz (2025)](https://nuz.uz/2025/03/22/yandex-cloud-zapuskaet-uzbekskij-yazyk-v-speechkit-novye-vozmozhnosti-dlya-golosovyh-servisov-v-uzbekistane/) |
| UzbekVoiceAI | O'zbek (birinchi mahalliy STT/TTS) | Aniqlik raqami yo'q; faqat "raqobatchilardan 3x arzon" marketing da'vosi | [uzbekvoice.ai/en-US](https://uzbekvoice.ai/en-US) |
| Aisha AI (Tashkent) | O'zbek, rus, ingliz + speaker diarization | Aniqlik raqami yo'q; 1 mln+ ovoz muloqoti qayta ishlangan (o'z da'vosi) | [aisha.group](https://aisha.group/en) |

**Shovqinli do'kon muhiti**: hech bir manbada o'zbek tili uchun shovqin sharoitida WER raqami topilmadi (qidirildi: Whisper/Yandex/Google + "noise"/shovqin kombinatsiyasi) — "ochiq manbada topilmadi". Bu amaliy xavf: POS atrofidagi fon shovqini (mijozlar, muzika) aniqlikni sezilarli pasaytirishi mumkin; ishga tushirishdan oldin mahalliy pilot-sinov zarur.

## 3. OCR (yuk xati, faktura, chek, qo'lda yozilgan daftar)

| Senariy | Vosita turi | Aniqlik | Manba |
|---|---|---|---|
| Toza chop etilgan faktura/chek (lotin-ingliz) | ABBYY (strukturaviy) | **manba topilmadi — tasdiqlanmagan** (avval 99,5% deyilgan edi) | docsumo.com sahifasida ABBYY uchun hech qanday aniqlik foizi yo'q — faqat Docsumo'ning o'zi uchun "99% field-level accuracy" bor. *(2026-10-14 tekshiruvida tuzatildi: 99,5% raqamining manbasi topilmadi, raqam olib tashlandi.)* |
| Chop etilgan matn, umumiy | Google Cloud Vision | 99,1% (ingliz, chop) | [imagetotable.ai (2026 qiyosi)](https://imagetotable.ai/blog/best-handwriting-ocr-software-2026) |
| Kursiv/qo'lyozma, umumiy | Google Cloud Vision | **70–75%** (mustaqil baholovlar, sezilarli pasayish) | [imagetotable.ai](https://imagetotable.ai/blog/best-handwriting-ocr-software-2026) — "independent assessments place it around 70-75%". *(2026-10-14 tekshiruvida tuzatildi: avval 63,4% deyilgan edi, bu raqam manbada topilmadi.)* |
| Qo'lyozma, Azure Document Intelligence v4.0 | — | ~8,67% WER (≈91,3%); IAM benchmarkda ~1,8% CER (bu ingliz-lotin benchmark) | [Azure 2026 benchmark sharhi](https://imagetotable.ai/blog/best-handwriting-ocr-software-2026) |
| 100+ til, kirill dagi da'vo (Smart Engines, RF kompaniyasi) | Vendor da'vosi | 99,9% gacha (mustaqil tasdiqlanmagan) | [smartengines.ru](https://smartengines.ru/raspoznavanie-teksta-ocr/) |
| Toza faktura, multimodal LLM vision (Gemini 2.5 Pro) | Vision-LLM | 96,50% (toza faktura), 92,71% (skanerlangan faktura), 87,46% (skanerlangan chek) | [arxiv.org/pdf/2509.04469](https://arxiv.org/pdf/2509.04469) |
| Faktura, Gemini 3 Pro (eng yangi) | Vision-LLM | 94,75% (eng yaxshi natija, test to'plamida) | [businesswaretech.com](https://www.businesswaretech.com/blog/best-ai-models-for-invoice-processing-in-2026-gemini-aws-chatgpt) |
| Chek, GPT-4o vs Gemini 1.5 Pro | Vision-LLM | GPT-4o 84,40% vs Gemini 1.5 Pro 91,15% (factuality) | [medium.com/underdoc](https://medium.com/underdoc/llm-evaluation-for-expense-document-image-understanding-d9b3549970b7) |
| Toza faktura, GPT 5.2/GPT-5 mini | Vision-LLM | **~88%** | [businesswaretech.com](https://www.businesswaretech.com/blog/best-ai-models-for-invoice-processing-in-2026-gemini-aws-chatgpt) — "GPT 5.2 and GPT 5 Mini achieved very similar accuracy results, both around 88%". *(2026-10-14 tekshiruvida tuzatildi: avval ">96%" deyilgan edi, manbada yo'q; model nomi ham aniqlashtirildi — "GPT 5.2", "GPT-5" emas.)* |

**Muhim ogohlantirish**: yuqoridagi barcha vision-LLM va OCR benchmarklar asosan ingliz/lotin tilidagi hujjatlar ustida o'tkazilgan. **Kirill+lotin+rus aralash O'zbekiston hujjatlari (yuk xati, chek) uchun mustaqil benchmark ochiq manbada topilmadi** — bu amaliyotda sinov o'tkazish kerak bo'lgan ochiq savol.

**Qo'lda yozilgan "nasiya daftari"**: qo'lyozma aniqligi umuman 63–95% oralig'ida (yozuv sifatiga qarab juda o'zgaruvchan) va buning uchun ham kirill-o'zbek maxsus raqam topilmadi. **Xulosa**: bu funksiya hozircha ishonchli emas — MVP'da qo'lda tuzilgan raqamli forma (mijoz tanlab, summa kiritib) qo'lyozma-OCR'dan ko'ra ishonchli muqobil.

## 4. 05_ai_funksiyalar.md funksiyalarini baholash

| Funksiya | Baho | Texnik yondashuv | Asosiy xavf |
|---|---|---|---|
| Debitorlik (nasiya) risk skorlash + eslatma matni | **MVP** | Qoida asosida risk belgisi (kod hisoblaydi) + LLM faqat o'zbekcha eslatma matnini yozadi | Past — LLM faqat matn generatsiya qiladi, raqam o'zi hisoblamaydi |
| Savol-javob chat ("bugun qancha foyda qildim?") | **MVP** | SQL/kod hisoblaydi → LLM tushuntiradi ("code computes, AI explains" tamoyili) | Past-o'rta — LLM javobni o'zbek tilida tabiiy shaklda bersin, lekin raqam LLM'dan kelmasligi nazorat qilinishi kerak |
| Toza faktura/chek fotosidan ma'lumot chiqarish (nakladnaya) | **MVP** (pilot bilan) | Vision-LLM (Gemini/GPT/Claude) — strukturaviy maydonlarni (summa, sana, ИКПУ) chiqarish | O'rta — kirill/UZ-specific aniqlik tasdiqlanmagan, pilot kerak |
| Talab bashorati (ombor kamayishi) | **Keyingi bosqich** | Klassik statistik/ML (LLM shart emas) — tarixiy savdo ma'lumoti kerak | O'rta — yetarli tarixiy ma'lumot to'planishi kerak (kamida bir necha oy) |
| Pul oqimi bashorati | **Keyingi bosqich** | Prophet/LSTM kabi vaqt qatori modeli | O'rta — tarixiy ma'lumot va kassa/bank integratsiyasi kerak |
| Bank tranzaksiya avtomatik kategoriyalash | **Keyingi bosqich** | Qoida+klassifikator | Yuqori — O'zbekistonda ochiq bank API cheklangan (oldingi tadqiqot, `06_integratsiyalar.md`: CBU'da faqat ma'lumotlar portali, API yo'q) |
| Anomaliya aniqlash (o'g'rilik, POS) | **Keyingi bosqich / yuqori murakkablik** | Video+POS integratsiyasi, behavioral model | Yuqori — qimmat infratuzilma (kamera), MVP uchun ortiqcha |
| Qo'lda yozilgan nasiya daftarini OCR qilish | **Hozircha real emas** | — | Yuqori — kirill qo'lyozma uchun hech qanday ishonchli benchmark yo'q; tuzilgan raqamli forma muqobil |
| Kundalik ovozli brifing (TTS, o'zbek ovozi) | **Keyingi bosqich** | Muxlisa/UzbekVoiceAI/Aisha TTS | O'rta — TTS tabiiyligi tekshirilmagan, matn-brifing birinchi qadam bo'lsin |
| Ovozli savol-javob (STT orqali) | **Keyingi bosqich** | Whisper-UZ/Yandex SpeechKit + yuqoridagi chat | O'rta-yuqori — shovqinli do'kon muhitida WER noma'lum, pilot kerak |

## Ochiq savollar

- Claude/OpenAI/Google rasmiy narx sahifalaridan (anthropic.com, platform.openai.com, ai.google.dev) to'g'ridan-to'g'ri tasdiqlangan 2026-10 narxlari — qidiruv natijalarida faqat uchinchi tomon agregator-saytlar ko'rindi; rasmiy sahifa tasdiqlanishi tavsiya etiladi.
- O'zbek tili (lotin+kirill) uchun Claude/GPT/Gemini'ning mustaqil sifat/benchmark raqami — ochiq manbada umuman topilmadi, faqat kichik ochiq modellar uchun akademik baho bor.
- Google Cloud STT va Yandex SpeechKit'ning o'zbek tili uchun aniq WER ko'rsatkichi — ikkisi uchun ham rasmiy raqam ochiq manbada topilmadi (faqat til qo'shilgani haqida yangilik bor).
- Shovqinli do'kon (fon shovqini, bir nechta ovoz) muhitida har qanday STT yechimining aniqligi — hech qanday manbada topilmadi, mahalliy pilot-sinov zarur.
- Kirill-lotin aralash O'zbekiston hujjatlari (faktura, yuk xati, chek) uchun OCR/vision-LLM aniqligi — mustaqil benchmark topilmadi, faqat ingliz-tilidagi umumiy benchmarklar bor.
- Qo'lda yozilgan kirill-o'zbek matn (nasiya daftari) uchun maxsus HTR benchmark — topilmadi.

## Manbalar

- [claude.com/pricing — Anthropic rasmiy narx sahifasi (anthropic.com/pricing shu yerga yo'naltiradi)](https://claude.com/pricing)
- [developers.openai.com/api/docs/pricing — OpenAI rasmiy narx sahifasi (platform.openai.com/docs/pricing shu yerga yo'naltiradi)](https://developers.openai.com/api/docs/pricing)
- [ai.google.dev/pricing — Google Gemini rasmiy narx sahifasi](https://ai.google.dev/pricing)
- [Uzbek LLM benchmark (zenodo.org, 2026)](https://zenodo.org/records/17223973)
- [TUMLU turkiy tillar benchmark (aclanthology.org)](https://aclanthology.org/2025.acl-long.1112.pdf)
- [Salom AI — ochiq model asosida o'zbekcha AI](https://salom-ai.uz/blog/llama-uzbek/)
- [Tilmoch AI-tarjimon, $1,5 mln baholash (digitalbusiness.kz, 2026-10-08)](https://digitalbusiness.kz/en/2026-10-08/uzbekistanets-sozdal-ii-perevodchik-dlya-tyurkskih-yazikov-startap-otsenili-v-15-mln/)
- [TilLab GitHub loyihasi](https://github.com/AbrorMusulmonov/tillab)
- [Dentons — O'zbekiston ma'lumot lokalizatsiyasi tuzatishi (2026-03-31)](https://www.dentons.com/en/insights/articles/2026/march/31/uzbekistan-dismantles-strict-data-localization-regime)
- [daryo.uz — lokalizatsiya qonuni tuzatishi tafsiloti](https://daryo.uz/en/2026/03/29/uzbekistan-amends-personal-data-law-for-domestic-storage-and-regulated-foreign-processing/)
- [Whisper-medium-uzbek (Hugging Face, NavAI)](https://huggingface.co/Mannon/whisper-medium-uzbek)
- [Whisper-small-uzbek (Hugging Face, NavAI)](https://huggingface.co/Mannon/whisper-small-uzbek)
- [Google Cloud STT o'zbek tili qo'shilishi (siliconangle.com, 2020)](https://siliconangle.com/2020/03/05/google-cloud-extends-speech-text-service-7-new-languages/)
- [Google Cloud STT qo'llab-quvvatlanadigan tillar (rasmiy hujjat)](https://docs.cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages)
- [Yandex SpeechKit o'zbek tili (habr.com, 2023)](https://habr.com/ru/companies/yandex_cloud_and_infra/articles/741746/)
- [Yandex SpeechKit yangilanishi (nuz.uz, 2025)](https://nuz.uz/2025/03/22/yandex-cloud-zapuskaet-uzbekskij-yazyk-v-speechkit-novye-vozmozhnosti-dlya-golosovyh-servisov-v-uzbekistane/)
- [UzbekVoiceAI](https://uzbekvoice.ai/en-US)
- [Aisha AI (Tashkent)](https://aisha.group/en)
- [Handwriting OCR 2026 qiyosiy sharh (imagetotable.ai)](https://imagetotable.ai/blog/best-handwriting-ocr-software-2026)
- [Smart Engines OCR (RF, kirill da'vosi)](https://smartengines.ru/raspoznavanie-teksta-ocr/)
- [Vision-LLM faktura/chek benchmark (arxiv.org 2509.04469)](https://arxiv.org/pdf/2509.04469)
- [Gemini/GPT/Claude faktura ekstraksiyasi 2026 (businesswaretech.com)](https://www.businesswaretech.com/blog/best-ai-models-for-invoice-processing-in-2026-gemini-aws-chatgpt)
- [GPT-4o vs Gemini chek ekstraksiyasi (medium.com/underdoc)](https://medium.com/underdoc/llm-evaluation-for-expense-document-image-understanding-d9b3549970b7)
- Loyihaning oldingi tadqiqot qaydi: `research_notes/AI ERP startap Ozbekistonda/05_ai_funksiyalar.md` (global ERP AI funksiyalari, qayta qilinmadi, faqat o'zbek-specific qism yangilandi), `06_integratsiyalar.md` (CBU ochiq bank API holati)
