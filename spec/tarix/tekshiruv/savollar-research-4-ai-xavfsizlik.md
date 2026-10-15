# Tadqiqot — AI (AI-03 OCR) va xavfsizlik (pentest) ochiq savollari

*2026-10-15 · Manba vazifasi: `tarix/tekshiruv/kamchiliklar-yakuniy.md` §3 (foydalanuvchi qarori kerak, band #59 va #52), `spec/kod-uchun/09-ai-funksiyalar.md` (AI-03), `spec/kod-uchun/22-ai-qatlami.md` (§8 baholash, §10 OCR quvuri), `research_notes/texnik/05-ozbek-tilidagi-ai.md`, `spec/kod-uchun/15-xavfsizlik-va-audit.md` (§8 baseline, §9.1 ЗРУ-764), `14-autentifikatsiya-oauth2.md`. Ikki savol — #59 (AI-03 ishga tushirish chegarasi) va #52 (pentest rejasi) — tashqi manbalar (WebSearch/WebFetch) bilan tekshirildi. Hech qanday band 1C bilan bog'liq emas (loyihada 1C integratsiyasi yo'q).*

---

## Savol 10 (#59) — AI-03 (hujjat OCR) uchun ishga tushirish mezoni

### Savol

AI-03 (qog'oz yuk xati/faktura/chek fotosidan OCR → M07 xarid hujjati loyihasi, foydalanuvchi tasdiqlaydi) MVP pilotiga chiqishi uchun qanday aniqlik chegarasi (threshold) qo'yilishi kerak? `22-ai-qatlami.md` §8.2'da "AI-03: maydon darajasidagi aniqlik (precision per field)" yozilgan, lekin **aniq raqam yo'q**; `kamchiliklar-yakuniy.md` §3-band-10 taklifi — "100 holatli to'plamda summa/sana/miqdor maydonlari bo'yicha ≥90% aniqlik" — tasdiqlanishi kerak.

### Amaliyotda qanday

**1. Rasmiy/tijorat OCR mahsulotlari — qanday chegara va metrika ishlatadi**

| Mahsulot | Metrika | Qiymat | Manba |
|---|---|---|---|
| **Azure Document Intelligence** | Umumiy tavsiya | "It's best to target a score of 80% or higher. For more sensitive cases, like financial or medical records, we recommend a score of close to 100%." | [learn.microsoft.com — Interpret accuracy and confidence scores](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-accuracy-confidence?view=doc-intel-2.1.0) |
| **Azure Document Intelligence** | Maydon darajasida ishonch (3-tomon amaliy tavsiya) | "Critical financial fields like InvoiceTotal, AmountDue, and TotalTax should use a threshold of 0.95 or higher with arithmetic checks. VendorName and VendorTaxId should use 0.90, InvoiceId should use 0.90 with duplicate checks, and InvoiceDate and DueDate should use 0.85." | CloudGate / theneuralbase sharhi (WebSearch natijasi, [theneuralbase.com — Confidence thresholds](https://theneuralbase.com/document-ai/learn/beginner/confidence-thresholds/)) |
| **Google Document AI** | Maydon aniqligi (benchmark) | "roughly 82% field accuracy but only 40% line-item score"; sarlavha maydonlari ishonchi 0.93–0.97, qator-maydonlari 0.60–0.71 | [businesswaretech.com — Research: AI Models Invoice Processing Benchmark](https://www.businesswaretech.com/blog/research-ai-models-invoice-processing-benchmark) |
| **AWS (umumiy IDP qoidasi)** | Maydon-boshiga chegara, narxga qarab | "Price confidence thresholds per field, by what a wrong value costs you... roughly 50% for archival text and 90% or higher for financial decisions." | parseur.com HITL sharhi (WebSearch) |
| **Rossum** | Field accuracy / STP | "Field accuracy ranges from 95–98%... production straight-through rates of 75 to 85 percent in enterprise AP environments" — lekin "a single incorrect field... triggers exception handling even if all other fields were correct" | [hypatos.ai — IDP Invoice Accuracy Benchmarks](https://www.hypatos.ai/knowledge-base/invoice-processing-accuracy-benchmarks-idp); [rossum.ai — touchless invoice processing](https://rossum.ai/blog/touchless-invoice-processing-for-ap-efficiency/) |
| **Mindee** | Asosiy 16 maydon | "success rate for these core fields of nearly 100%, including for scanned invoices"; umumiy field accuracy ~96,1% (3-tomon benchmark) | [mindee.com — Invoice OCR API](https://www.mindee.com/product/invoice-ocr-api) |
| **Veryfi** | Qator-maydon (line-item) aniqligi | "99.56% accuracy in line-item extraction from expense receipts"; "98-99% field-level accuracy without training" | [veryfi.com — Line-Item Extraction Accuracy Benchmarks](https://www.veryfi.com/technology/line-item-extraction-accuracy-benchmarks/) |

**Muhim ogohlantirish**: yuqoridagi barcha raqamlar **ingliz-tilidagi, sof chop etilgan hujjatlar** uchun (ko'pincha AQSh/Yevropa fakturalari). `research_notes/texnik/05-ozbek-tilidagi-ai.md` (3-bo'lim) allaqachon qayd etgan: kirill+lotin+rus aralash O'zbekiston hujjatlari uchun mustaqil benchmark **hech qayerda topilmadi** — bu haligacha tasdiqlanmagan ("tasdiqlanmagan").

**2. Akademik invoice benchmark to'plamlari** (maydon darajasidagi aniqlik metodologiyasi uchun namuna):

- **SROIE** (ICDAR 2019) — 1000 skanerlangan chek, 4 kalit maydon (kompaniya, manzil, sana, summa), 626 train/347 test. ([ceur-ws.org sharhi](https://ceur-ws.org/Vol-4044/paper12.pdf))
- **CORD** — 800 train/100 val/100 test chek, 30 nozik maydon, entity-level F1 metrikasi.
- **DocILE** — 106 680 belgilangan faktura-tipidagi hujjat, 55 sinf, ko'p sahifali. ([arxiv.org/pdf/2302.05658](https://arxiv.org/pdf/2302.05658))

Bu uchtasi ham **metodologiya namunasi** sifatida foydali: har maydon alohida F1/aniqlik bilan o'lchanadi, "umumiy aniqlik" emas — bizning 100-holatli eval to'plamimiz (`22-ai-qatlami.md` §8.1) xuddi shu tarzda tuzilishi kerak (har maydon — summa, sana, miqdor, tovar nomi, yetkazib beruvchi — alohida aniqlik ko'rsatkichi bilan).

**3. Vision-LLM (loyihada tanlangan yondashuv) — ingliz-til benchmarklar**: `research_notes/texnik/05-ozbek-tilidagi-ai.md` 3-bo'limida allaqachon keltirilgan: toza faktura Gemini 2.5 Pro 96,50%, Gemini 3 Pro 94,75%, GPT 5.2/GPT-5 mini ~88%; chek — GPT-4o 84,40%, Gemini 1.5 Pro 91,15%. Bular ham ingliz-til, maydon-aralash (field-mix) umumiy aniqlik, emas sof "summa maydoni aniqligi" — field-level breakdown ochiq manbada yo'q.

**4. Human-in-the-loop (HITL) dizayn standart amaliyoti**:

- "The core mechanic is confidence scoring with threshold routing... If the AI is certain, the data flows to the database; if it is confused, the file routes to a human reviewer." ([unstract.com — HITL for AI Document Processing](https://unstract.com/blog/human-in-the-loop-hitl-for-ai-document-processing/))
- "A human-in-the-loop workflow has three lanes, not two: straight-through, field-level review, and full manual exception." (parseur.com, WebSearch natijasi)
- "Typically 70-90% of documents clear straight-through; the remainder get targeted human verification." (WebSearch, HITL sharhi)
- Straight-through processing (STP) bo'yicha **mustaqil** (Ardent Partners) va **vendor** raqamlari sezilarli farqlanadi: "The all-buyer average straight-through processing rate is near 25%... best-in-class... 35% or more" / "Ardent Partners' 2025 AP metrics report puts the industry-average touchless rate at 32.6%, with Best-in-Class organizations hitting 49.2%" — bularga qarshi vendor da'volari "85–92%... achievable with agentic architecture in production". ([imagetotable.ai — STP rate ta'rifi](https://imagetotable.ai/references/straight-through-processing-rate); [hypatos.ai](https://www.hypatos.ai/knowledge-base/invoice-processing-accuracy-benchmarks-idp))

Bizning arxitekturamizda (AI hech qachon avtomatik tasdiqlamaydi — `22-ai-qatlami.md` §10) STP "to'liq avtomatik o'tish" ma'nosida qo'llanmaydi (har hujjat har doim odam tasdig'idan o'tadi); amaliy ekvivalenti — **"tahrirsiz tasdiqlangan hujjat ulushi"** (`22-ai-qatlami.md` §8.4'da allaqachon shu metrikaga ishora bor: "AI-03 foydalanuvchi tomonidan hech qanday tahrirsiz tasdiqlangan hujjat ulushi — aniq maqsad yo'q, kuzatiladi").

### Variantlar

| Variant | Tasvir | Afzallik | Kamchilik |
|---|---|---|---|
| A. Yagona chegara (masalan ≥90% umumiy aniqlik) | Bitta raqam, barcha maydonlarga bir xil | Sodda, tushunarli | Noto'g'ri — summa xatosi bilan tovar nomi xatosi bir xil og'irlikda emas (Rossum/AWS amaliyoti buni rad etadi) |
| B. **Maydon-boshiga differensial chegara** (Azure/AWS amaliyoti) | Moliyaviy maydon (summa, QQS) ≥95%; sana/STIR/yetkazib beruvchi ≥85–90%; tovar nomi/miqdor (qator maydoni, odatda pastroq ishonchli) ≥80% + har doim past-ishonch belgisi | Xato narxiga mos ("price confidence thresholds per field, by what a wrong value costs you" — AWS tavsiyasi); loyihaning "kod hisoblaydi, AI tushuntiradi" falsafasiga mos (moliyaviy raqam eng qattiq nazoratda) | Sozlash murakkabroq, pilotda kalibrlash kerak |
| C. Faqat ishonch-asosli yo'naltirish (threshold yo'q, har doim past-ishonchli maydonlar belgilanadi) | `22-ai-qatlami.md` §10'dagi joriy loyiha ("ishonch ≥ chegara — taxmin") | Hech qachon avtomatik xato kiritilmaydi | Pilot boshida kalibrlanmagan chegara — juda ko'p/kam belgilash xavfi |

### Tavsiya (ishonch: o'rta — xalqaro amaliyotga mos, lekin O'zbekiston-specific aniqlik hali sinalmagan)

1. **Variant B** qabul qilinsin — maydon-boshiga differensial chegara, Azure/AWS amaliyotiga moslashtirilgan:
   - **Summa (jami)**: eval to'plamida ≥95% to'g'ri o'qilishi SHART (moliyaviy yozuv) — Azure'ning "InvoiceTotal ≥0.95" tavsiyasiga mos.
   - **Sana**: ≥90% (Azure "InvoiceDate 0.85" dan biroz qattiqroq, chunki QQS davri/muddat hisobga bog'liq).
   - **Miqdor va tovar nomi** (qator maydonlari — barcha manbalarda eng past ishonchli: Google Document AI 0,60–0,71, Mindee/Rossum'da ham qator-darajasi asosiy aniqlik to'g'risida alohida past): ≥80% maydon aniqligi, past-ishonch belgisi majburiy qo'llanilsin (bu daraja pastroq bo'lsa ham xavfsiz, chunki foydalanuvchi har doim tasdiqlaydi/tahrirlaydi).
   - **Yetkazib beruvchi nomi**: ≥85%.
2. **100-hujjatli O'zbekiston eval to'plami** (`22-ai-qatlami.md` §8.1 bilan bir xil joy): SROIE/CORD uslubida — har hujjat uchun kutilgan maydon qiymatlari oldindan yozilsin; tarkib **majburiy** aralash: ~40% toza chop (printer), ~40% skanerlangan/fotosurat (burchak qiyshaygan, soya), ~20% qo'lda to'ldirilgan qism (tovar nomi yozma, summa raqamlar bilan) — chunki qog'oz yuk xati (AI-03 qamrovi (a)-bandi) ko'pincha qisman qo'lda to'ldiriladi; til taqsimoti — lotin, kirill, rus aralash (loyihaning "05-ozbek-tilidagi-ai.md" Ochiq savol #2 bilan bir xil ehtiyot).
3. **Go/no-go qoida (pilot uchun)**:
   - **GO**: 100-hujjatli to'plamda summa ≥95% va sana ≥90% maydon aniqligi, VA past-ishonch belgisining "haqiqiy xatoni ushlash" ko'rsatkichi (ya'ni past-ishonch deb belgilangan maydonlarning haqiqatan xato bo'lish ulushi) ≥70% (kalibrlash sifati) — HITL amaliyotidagi "programmatic confidence thresholds as automated logic gates" tamoyiliga mos.
   - **NO-GO**: summa yoki sana aniqligi <90% — AI-03 pilot start'i kechiktiriladi, mavjud zaxira (qo'lda M07 kirim kiritish, AI-04'dagi kabi "tuzilgan forma") davom etadi.
   - Hech qachon avtomatik tasdiqlash yo'q (bu allaqachon arxitektura qoidasi, `22-ai-qatlami.md` §10) — shuning uchun past aniqlik tizimni buzmaydi, faqat foydalanuvchi ko'proq tahrir qiladi; go/no-go asosan **foydalanuvchi vaqtini tejash** mezoni (agar har hujjatni qayta yozish kerak bo'lsa, AI-03 foyda keltirmaydi).
   - Qo'shimcha kuzatiladigan (lekin bloklamaydigan) metrika: "tahrirsiz tasdiqlangan hujjat ulushi" — `22-ai-qatlami.md` §8.4'dagi mavjud reja bilan bir xil, maqsad belgilanmagan, pilotda kuzatiladi.
4. `kamchiliklar-yakuniy.md`dagi "≥90% summa/sana/miqdor" taklifi **qisman** tasdiqlanadi: summa uchun ≥90% yetarli emas (xalqaro amaliyot ≥95% talab qiladi moliyaviy maydonlar uchun), lekin miqdor/tovar nomi uchun ≥80–85% ham amaliy jihatdan oqlanadi (qator-maydon barcha manbalarda eng past ishonchli).

### Manbalar
- [learn.microsoft.com — Azure Document Intelligence: Interpret accuracy and confidence scores](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-accuracy-confidence?view=doc-intel-2.1.0)
- [theneuralbase.com — Confidence thresholds](https://theneuralbase.com/document-ai/learn/beginner/confidence-thresholds/)
- [businesswaretech.com — Research: AI Models Invoice Processing Benchmark](https://www.businesswaretech.com/blog/research-ai-models-invoice-processing-benchmark)
- [hypatos.ai — IDP Invoice Accuracy Benchmarks: Production Data 2026](https://www.hypatos.ai/knowledge-base/invoice-processing-accuracy-benchmarks-idp)
- [rossum.ai — Unlock AP Efficiency with Touchless Invoice Processing Automation](https://rossum.ai/blog/touchless-invoice-processing-for-ap-efficiency/)
- [mindee.com — Invoice OCR API](https://www.mindee.com/product/invoice-ocr-api)
- [veryfi.com — 2025 Accuracy Benchmarks for Line-Item Extraction](https://www.veryfi.com/technology/line-item-extraction-accuracy-benchmarks/)
- [ceur-ws.org — Invoice and receipt OCR review (SROIE/CORD)](https://ceur-ws.org/Vol-4044/paper12.pdf)
- [arxiv.org — DocILE Benchmark](https://arxiv.org/pdf/2302.05658)
- [unstract.com — Human In The Loop (HITL) for AI Document Processing](https://unstract.com/blog/human-in-the-loop-hitl-for-ai-document-processing/)
- [imagetotable.ai — What is Straight-Through Processing (STP) Rate](https://imagetotable.ai/references/straight-through-processing-rate)
- `research_notes/texnik/05-ozbek-tilidagi-ai.md` (3-bo'lim — O'zbekiston-specific OCR aniqligi tasdiqlanmagan, ichki manba)
- `spec/kod-uchun/22-ai-qatlami.md` §8, §10 (ichki manba — joriy eval reja, OCR quvuri)

---

## Savol 14 (#52) — Ishga tushirishdan oldin penetratsion test (pentest)

### Savol

Ishga tushirishdan (pilot/ommaviy) oldin pentest kerak — kim o'tkazadi (O'zbekistonda), qamrov qanday bo'lishi kerak (veb+API+OAuth+mobil), muddat/narx qancha, qaysi standartga (OWASP ASVS/WSTG) asoslanadi, qachon o'tkaziladi (pilotdan oldin vs ommaviy ishga tushirishdan oldin) va yengilroq muqobillar (DAST, bug bounty) bormi? `15-xavfsizlik-va-audit.md` §8 — "Penetratsion test | Ishga tushirishdan oldin kamida bir marta mustaqil pentest | **Taxmin**" — ijrochi/byudjet yo'q.

### Amaliyotda qanday

**1. O'zbekistondagi pentest xizmati ko'rsatuvchilar** (WebSearch orqali topilgan, narx **hech birida ochiq ko'rsatilmagan**):

| Kompaniya | Joylashuv | Qamrov (sayt matnidan) | Manba |
|---|---|---|---|
| **Celion** | Tashkent | "Web, API & network testing—A real attacker's view of your exposed systems"; metodologiya: scope→manual exploitation→report→re-test; natijalar "mapped to ISO 27001, PCI-DSS and GDPR"; mijozlar — Olcha, MyTaxi, EMU University | [celion.io/en/penetration-testing](https://celion.io/en/penetration-testing) |
| **ONESEC.UZ** | Tashkent, Chilonzor | "penetration testing, information security audits, and security analysis of information systems, servers, and websites" | [onesec.uz/en](https://onesec.uz/en) |
| **Sigma Software** | Tashkent (xalqaro IT-kompaniyaning mahalliy ofisi) | Veb-ilova pentest xizmati | [sigma.software/services/penetration-testing-services](https://sigma.software/services/penetration-testing-services) |
| **WPROIT** | Tashkent | Pentest, MDR, 24/7 SOC, ISO 27001 konsalting | WebSearch natijasi |
| **Loialte, Adminz, ArkStone** | Tashkent | Muntazam audit/pentest xizmatlari (saytlarda tasdiqlangan, tafsilot yo'q) | WebSearch natijasi |

**Davlat tomoni**: **csec.uz** ("Kiberxavfsizlik markazi", UZCERT shu tashkilot ichidagi bo'linma) — rasmiy "Xizmatlar" (`/uz/services/`) sahifasida umumiy xizmatlar ro'yxati bor, lekin **pentest xizmati yoki narxi aniq ko'rsatilmagan** (sahifa tarkibini to'liq WebFetch qilishda aniq matn chiqmadi — **tasdiqlanmagan**, to'g'ridan-to'g'ri murojaat/yozma so'rov kerak). UZCERT'ning o'z tasvirida asosiy vazifa — insident javobi (incident response), domen ekspertizasi, kiberhavf razvedkasi; **pentest aniq xizmat sifatida sanalmagan** — buning o'rniga mustaqil "ONESEC" firmasi alohida eslatilgan (WebSearch xulosasi).

**2. Standartlar**: `15-xavfsizlik-va-audit.md` §8 allaqachon "OWASP ASVS L2 asosida (taxmin)" deb belgilagan. Tasdiqlovchi topilma:
- "Level 2 is the recommended target for the majority of applications, particularly those handling sensitive data, conducting significant transactions, or interacting with critical systems or business processes." — bu bizning holatimizga (moliyaviy/soliq ma'lumoti, OAuth, davlat API integratsiyasi) to'g'ridan-to'g'ri mos. ([aikido.dev / securitysenses.com, WebSearch xulosasi](https://securitysenses.com/posts/how-choose-right-asvs-level-your-organization))
- "Level 2 verification requires deeper access than black box testing alone, including authenticated testing, source code review where applicable, and structured verification of controls across all ASVS requirement categories." — demak pentest **faqat tashqi (black-box)** emas, autentifikatsiyalangan (ichki rollar — Kassir/Menejer/Egasi) testlash ham qamrovga kiradi; bu bizning `05-xavfsizlik` §2 huquqlar matritsasiga mos tekshiruv talab qiladi.
- WSTG (OWASP Web Security Testing Guide) — ASVS'ning "qanday test qilish" qo'llanmasi hisoblanadi (umumiy bilim, alohida qidiruv natijasi yo'q, lekin ASVS manbalarida doimiy birga tilga olinadi).

**3. Qamrov tarkibi — bizning tizim uchun**: veb (back-office+veb-kassa, BFF+OAuth), REST API, **OAuth 2.0 oqimlari** (`14-autentifikatsiya-oauth2.md` — Authorization Code+PKCE, refresh token rotation, tenant almashtirish, admin panel), Android POS (public OAuth client, offline litsenziya tokeni) — bularning barchasi Celion kabi firmalarning "Web, API & network" standart qamroviga kiradi; mobil (Android) uchun alohida band so'ralishi kerak (ko'pchilik mahalliy firma sahifasida "mobile" alohida tilga olinmagan — so'rov paytida aniqlashtiriladi).

**4. Muddat/narx — faqat xalqaro (asosan AQSh/Yevropa) manbalardan, O'zbekiston narxi hech qayerda ochiq emas**:
- "For a small business, a single focused penetration test, such as one web application or the external perimeter, typically costs $5,000–$10,000." / "Most small-business web application penetration testing projects land somewhere between $2,500 and $15,000, depending on scope, complexity, authentication, user roles, API surface..." ([wardenbit.com — Web App Pentest Cost for Small Businesses 2026](https://wardenbit.com/posts/web-application-penetration-testing-cost-small-businesses-2026/))
- "Penetration testing rates typically run $100–$300 per hour in the US, and UK providers commonly charge around £800–£1,500 per day." ([lorikeetsecurity.com — Web Pentest Cost Breakdown](https://lorikeetsecurity.com/blog/web-pentest-cost-breakdown))
- "small businesses typically budget US$8,000 to US$20,000 annually for penetration testing" (hackenproof.com/blazeinfosec.com klasteridagi WebSearch xulosasi)
- **Taxmin ekstrapolyatsiya (tasdiqlanmagan)**: O'zbekiston mahalliy firma narxi, odatda mintaqaviy ish haqi farqi sababli AQSh/Yevropa narxining ~30–50%i atrofida bo'lishi mumkin (umumiy IT-xizmat bozori amaliyoti, **bu loyihaga xos manbada tasdiqlanmagan**) — ya'ni veb+API+OAuth qamrovli, bir martalik pentest uchun **taxminan $1 500–$7 000 (~19–87 million so'm, kurs 12 500) oralig'ida** bo'lishi mumkin, lekin bu **faqat taxmin**, Celion/ONESEC'dan rasmiy taklif olinmaguncha tasdiqlanmaydi.

**5. Yengilroq muqobillar**:
- **DAST (avtomatik skanerlash)**: "automated DAST tools can run any number of automated scans at any time with no additional cost... Unified AI security platforms perform continuous scanning... start at USD 499 per assessment." ([invicti.com](https://www.invicti.com/blog/web-security/dast-vs-penetration-testing); narx — WebSearch xulosasi). Bepul variant — OWASP ZAP (open-source, o'z-o'zidan ishga tushiriladi, narxsiz, lekin OAuth/business-logic chuqur tekshiruvini qamrab olmaydi).
- **Bug bounty**: "Small businesses can budget $10k–$50k/year for limited-scope programs with fewer assets and capped payouts... platform fees start at $12,000 to $25,000 per year, plus per-vulnerability payouts." ([deepstrike.io / appsentinels.ai, WebSearch xulosasi](https://deepstrike.io/blog/penetration-testing-vs-bug-bounty)) — **bizning bosqich uchun ortiqcha qimmat va ortiqcha erta** (bug bounty dastur targ'ib qilish uchun yetarlicha tanilgan mahsulot va triage resursi kerak — bizda pilot bosqichida yo'q).

**6. ЗРУ-764 bilan bog'liqlik (mavjud ochiq savol, qayta ishlab chiqilmadi)**: `15-xavfsizlik-va-audit.md` §9.1 allaqachon qayd etgan — "18-modda (ekspertiza) va 19-modda (sertifikatlash) faqat davlat organlari va KAI (kritik axborot infratuzilmasi) obyektlariga tegishli" va "AIOS kabi oddiy xususiy SaaS ERP... shu majburiy ekspertiza/sertifikatlashga tushadimi — ochiq manbada aniq tasdiqlanmagan", tavsiya — csec.uz'ga yozma so'rov (Xat 3, `kamchiliklar-yakuniy.md` §4). **Bu tadqiqot ushbu ochiq savolni hal qilmadi** — WebFetch csec.uz/uz/services/ sahifasidan aniq xizmat/talab matnini chiqarib bera olmadi (texnik sabab — JS-asosidagi sahifa yoki tarkib ko'rinmadi). **Xulosa o'zgarmaydi**: ЗРУ-764 majburiy sertifikatlash talabi oddiy SaaS'ga tegishli emasligi hali **tasdiqlanmagan**, rasmiy yozma javob kutilmoqda.

### Variantlar

| Variant | Qachon | Narx/og'irlik | Qamrov chuqurligi |
|---|---|---|---|
| A. Faqat DAST (OWASP ZAP/bepul yoki $499/skan tijorat) | Pilotdan oldin, doimiy CI'da | Eng arzon | Past — business-logic/OAuth oqimini chuqur sinamaydi |
| B. **Mahalliy firma bilan to'liq manual pentest** (Celion/ONESEC, ASVS L2 qamrovida: veb+API+OAuth+Android) | Pilotdan oldin (birinchi marta) VA ommaviy ishga tushirishdan oldin (qayta, agar katta arxitektura o'zgargan bo'lsa) | O'rta — taxmin $1 500–$7 000 (tasdiqlanmagan) | Yuqori — ASVS L2 autentifikatsiyalangan test |
| C. Xalqaro firma (remote) | Ommaviy ishga tushirishdan oldin, agar mahalliy sifat/qamrov yetarli bo'lmasa | Yuqori — $5 000–$30 000 (xalqaro, tasdiqlangan diapazon) | Yuqori, lekin O'zbekiston-specific kontekst (davlat API'lari, mahalliy til) yo'qligi mumkin |
| D. Bug bounty dasturi | Faqat yetuk bosqichda (pilotdan keyin, mahsulot tanilgandan keyin) | Yuqori va oldindan noma'lum ($10k–$50k/yil + to'lovlar) | O'zgaruvchan, erta bosqich uchun mos emas |

### Tavsiya (ishonch: o'rta-past — standart/qamrov bo'yicha ishonch yuqori, O'zbekiston narxi bo'yicha past, faqat taxmin)

1. **Ikki bosqichli yondashuv**:
   - **Pilotdan oldin (arzon, tezkor)**: OWASP ZAP yoki shunga o'xshash bepul/arzon DAST skanerlash + ichki jamoa tomonidan OAuth/to'lov/fiskal oqimlarining qo'lda tekshiruvi (checklist, ASVS L2 talablaridan qisqartirilgan). Byudjet — amalda deyarli 0 (ichki vaqt sarfi bilan).
   - **Ommaviy ishga tushirishdan oldin (yoki birinchi 10–20 haqiqiy to'lovchi tenant bosqichida)**: **mahalliy firma bilan to'liq manual pentest** — Celion yoki ONESEC'dan **rasmiy taklif (quote) so'ralsin** (qamrov: veb back-office+veb-kassa, REST API, OAuth 2.0 oqimlari — Authorization Code+PKCE, refresh rotation, admin panel, Android POS public client), OWASP ASVS L2 asosida. Ikkisidan ham narx/muddat so'rab, taqqoslab tanlash tavsiya etiladi — bu ishni **rasmiy xat/so'rov** sifatida `kamchiliklar-yakuniy.md` §4 ro'yxatiga (vendor ishlari) qo'shish mumkin.
   - Byudjet rejalashtirishda **taxmin chegara $1 500–$7 000 (yoki real taklif kelgandan keyin aniqlashtiriladigan raqam)** ishlatilsin — bu loyihaning unit-iqtisod hisobiga (`22-ai-qatlami.md` §13, `06-nofunksional` §11) bir martalik xarajat sifatida kiritilishi kerak, chunki hozirgi hisoblarda pentest xarajati umuman yo'q.
2. **ЗРУ-764 savoli — hal qilinmagan, ustuvor**: csec.uz'ga rasmiy yozma so'rov (Xat 3) birinchi navbatda yuborilishi kerak, chunki javob "ha, sertifikatlash shart" bo'lsa, bu butun pentest rejasini (kim, qanday format) o'zgartiradi — mahalliy pentest firmasi bilan shartnoma tuzishdan oldin shuni bilish amaliy jihatdan foydali (`15-xavfsizlik-va-audit.md` §9.1, Ochiq savol 1 — ushbu tadqiqot bilan hal qilinmadi, faqat tasdiqlandi).
3. **Bug bounty — hozircha tavsiya etilmaydi** (D variant): mahsulot hali kam tanilgan, triage resursi yo'q — pilotdan keyin, agar mahsulot kattalashsa qayta ko'rib chiqilsin.
4. Xalqaro firma (C) — faqat agar mahalliy ikkita firma (Celion/ONESEC) taklifi narx/sifat jihatidan mos kelmasa, zaxira variant sifatida saqlansin.

### Manbalar
- [celion.io/en/penetration-testing](https://celion.io/en/penetration-testing)
- [onesec.uz/en](https://onesec.uz/en)
- [csec.uz/uz/services/](https://csec.uz/uz/services/) — xizmat tarkibi tasdiqlanmadi (texnik WebFetch cheklovi)
- [securitysenses.com — How to Choose the Right ASVS Level](https://securitysenses.com/posts/how-choose-right-asvs-level-your-organization)
- [wardenbit.com — Web App Pentest Cost for Small Businesses 2026](https://wardenbit.com/posts/web-application-penetration-testing-cost-small-businesses-2026/)
- [lorikeetsecurity.com — Web Pentest Cost Breakdown](https://lorikeetsecurity.com/blog/web-pentest-cost-breakdown)
- [deepstrike.io — Penetration Testing vs Bug Bounty: 2025 Decision Guide](https://deepstrike.io/blog/penetration-testing-vs-bug-bounty)
- [invicti.com — DAST vs Penetration Testing](https://www.invicti.com/blog/web-security/dast-vs-penetration-testing)
- `spec/kod-uchun/15-xavfsizlik-va-audit.md` §8 (baseline/pentest taxmin), §9.1 (ЗРУ-764 ochiq savol — ichki manba)
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` (OAuth qamrovi — ichki manba)

---

## Yakuniy tavsiya (1–2 qator/savol)

**#59 (AI-03 ishga tushirish chegarasi)**: Yagona ≥90% o'rniga maydon-boshiga chegara qo'yilsin — summa ≥95%, sana ≥90%, miqdor/tovar nomi ≥80–85% (past-ishonch belgisi bilan); 100-hujjatli eval to'plami toza/skaner/qo'lda qism aralashmasida tuzilsin; go/no-go — summa va sana shu chegaradan past bo'lsa pilot kechiktiriladi, aks holda ishga tushiriladi (avtomatik tasdiqlash hech qachon yo'q).

**#52 (Pentest)**: Pilotdan oldin — bepul/arzon DAST + ichki OAuth/to'lov tekshiruvi; ommaviy ishga tushirishdan oldin — Celion yoki ONESEC'dan (Tashkent) OWASP ASVS L2 qamrovida (veb+API+OAuth+Android) rasmiy taklif so'ralsin, taxmin byudjet $1 500–$7 000 (tasdiqlanmagan, taklif kelgach aniqlashtiriladi); ЗРУ-764 sertifikatlash talabi haligacha hal qilinmagan — csec.uz javobi kutilmoqda, bu pentest rejasiga ta'sir qilishi mumkin.
