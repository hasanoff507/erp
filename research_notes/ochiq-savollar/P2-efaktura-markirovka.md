# P2 — E-faktura, E-TTN, markirovka, E-IMZO, e-ishonchnoma (desk-research natijasi)

**Maqsad:** `00-inventar.md` §12 P2 partiyasidagi 9 ta R-savolni (OQ-019, 020, 021, 022, 023, 024, 026, 027, 028) birlamchi manbalar bilan yopish va har biri uchun `spec/kod-uchun/` ga aniq o'zgarish matnini taklif qilish. · **Kim uchun:** asoschi, spec'ni yangilovchi agentlar, backend ishlab chiquvchi. · **Bog'liq fayllar:** `00-inventar.md` §3, `spec/kod-uchun/21-integratsiyalar.md` §2–§6/§13, `04-biznes-jarayonlar.md` (BP-01, BP-03, BP-09, Ochiq savollar 5/6/10/11), `03-modullar-talablari.md` (M06, US-M07-05), `13-provodka-qoidalari.md` §2.20, `16-offline-sync.md` §7, `26-ochiq-savollar-reestri.md` (A#4, B#43, B#47), `research_notes/texnik/02`, `03`, `09`. · **Holat:** desk-research yakunlangan, 2026-10-16. **Spec fayllari o'zgartirilmadi** — quyidagi "Spec'ga ta'sir" bandlari faqat taklif.

**Usul:** lex.uz'dagi qaror matnlari to'liq yuklab o'qildi (VM 23, VM 249 + 3-/31-ilova, VM 168, VM 489, VM 673, VM 737/833, VM 631, VM 149, VM 322, VM 825, VM 830, VM 943, PQ-190, Soliq kodeksi 47/257/269-moddalar); vendor hujjatlari jonli sahifadan (api.faktura.uz/help, api-docs.didox.uz, github.com/qo0p/e-imzo-doc, yt.uz); amaliyotchi manbalar (buxgalter.uz, bss.uz, legalise.uz, norma.uz — qisman pullik). Tadqiqot 3 parallel Opus agent bilan bajarildi; WebSearch kvotasi oxirida tugadi — qolgani WebFetch/Playwright/curl bilan. Iqtiboslar asl tilda (o'zbek/rus). Kirish sanasi ko'rsatilmagan barcha URL — **2026-10-16**.

---

## Yig'ma

| OQ | Qisqa javob | Holat | Kodga ta'sir |
|---|---|---|---|
| 019 | Faktura.uz: har kompaniyaning o'z login+client_id/secret (integrator dasturi yo'q), imzo — hash → E-IMZO PKCS#7 → `SignDocument`; webhook yo'q, faqat poll (`GetDocuments?IsInbox`); VM 830 xavf darajasi EHF rasmiylashtirilayotganda va my.soliq kabinetida ko'rinadi, operator API'si haqida qarorda gap yo'q; Didox API'da `scoring` maydoni bor, Faktura.uz'da topilmadi | **QISMAN** | FLAG (risk_flag `unknown` holati) |
| 020 | Didox API hujjati **ochiq** (login shart emas); kirish — Didox akkaunt-menejeridan **partner token** (`Partner-Authorization`), test + prod URL bor; foydalanuvchi E-IMZO yoki parol bilan `user-key` oladi | **YOPILDI** | YO'Q (MVP) — lekin operator tanlovini qayta ko'rish tavsiya etiladi |
| 021 | e-TTN — faqat EDO operatorlari orqali (sotuv bilan bir vaqtda e-faktura bilan **birlashtirilgan**); **o'z omborlari/filiallari orasida ko'chirishda ham majburiy** ("Ombordan omborga" rejimi) | **YOPILDI** | **FLAG → interim teskari** (ichki ko'chirishda talab qilinadi) |
| 022 | Jismoniy shaxsga savdoda kassa cheki berilsa e-faktura shart emas (SK 47-m. 3-q., VM 489 3-band); nasiyada amaliyot — topshirish kuni to'liq summaga "Продажа" cheki → qaror #30 bilan ziddiyat | **QISMAN** | FLAG; qaror #30 ga kesishma xavfi |
| 023 | Qaytarishda **yetkazib beruvchi** salbiy summali **qo'shimcha** EHF chiqaradi, xaridor tasdiqlaydi va kiruvchi QQS'ni shu davrda kamaytiradi (SK 257, 269; VM 489 40–42-band); 1 yil/kafolat muddatidan keyin — xaridorning "teskari realizatsiyasi" (chiquvchi QQS bilan); 6010/9430 qatori — P7/buxgalter | **QISMAN** | FLAG |
| 024 | VM 825 — **davlat xizmatlari** uchun ishonchnoma, yuridik shaxslar uchun ixtiyoriy; tovar olish ishonchnomasi VM 249 3-ilova bo'yicha **EDO operatori orqali**, uni **xaridor (do'kon) o'z vakiliga** beradi, sotuvchi EHF'dan **oldin** tekshiradi; Vakolat.uz ommaviy API topilmadi (kerak ham emas) | **YOPILDI** | FLAG → model soddalashadi |
| 026 | Offline sotuv qonunga zid emas (VM 943 31-band, 48 soat; kod chekka yoziladi, OFD → Asl belgisi uzatadi — VM 833 75–77-band); "ruxsat beruvchi rejim" yo'q; qaytarish — kodli qaytarish cheki, "faqat online" — qonundan qat'iyroq ichki tanlov; ichki ko'chirish — CRPT'ga xabar majburiyati topilmadi; ochiq qism: "avval ishlatilgan kod" tekshiruvi offline'da | **QISMAN** | FLAG; **arxitektura**: chakana "sell" — OFD orqali, to'g'ridan-to'g'ri CRPT chaqiruvi emas |
| 027 | 72 soat — VM 23 2-ilova **sxemasida**, faqat o'simlik yog'i **tajriba loyihasi** (ixtiyoriy) ishtirokchilari uchun; suv/ichimlik (VM 631), dori (VM 149) sxemalarida ham bor; **umumiy qoida — 3 ish kuni** (VM 833 66–67-band); hammasi **egalik o'tishiga** (subyektlar orasida, EHF) bog'liq, ichki ko'chirishga emas | **YOPILDI** | FLAG (muddat — tovar guruhi bo'yicha konfiguratsiya) |
| 028 | Rasmiy dasturchi portali yo'q; amaldagi qo'llanma — `qo0p/e-imzo-doc` (2026-10-09 yangilangan); **API-KEY (har prod domen uchun alohida), VPN-kalit (E-IMZO-SERVER), SiteID** — barchasini НИЦ "Yangi texnologiyalar" (yt.uz) beradi; E-IMZO-SERVER faqat yozma shartnoma + yopiq Telegram kanal orqali; narx/muddat ommaviy emas | **QISMAN** | FLAG; domen arxitekturasi cheklovi |

---

## OQ-019 — Faktura.uz API: multi-tenant, kiruvchi faktura, VM 830 xavf natijasi

### Javob
1. **Autentifikatsiya va multi-tenant.** OAuth2 "password grant": `POST https://account.faktura.uz/token` (`username`, `password`, `client_id`, `client_secret`). Login/parol — **Faktura.uz foydalanuvchisining o'zi**niki; `client_id`/`client_secret` ni ham foydalanuvchi o'z kabinetida ("Доступ к API → Настройки клиентов") yaratadi. Alohida integrator/hamkor kredensiali va hamkorlik dasturi **hujjatda yo'q**. Bitta token bilan bir necha kompaniya — faqat "мультиаккаунтный пользователь" (`?companyInn=` parametri), bu esa Faktura tarifidagi "мульти-организации" soni bilan cheklangan. Token muddati 604799 s (7 kun), `refresh_token` qaytariladi. **Amaliy xulosa:** SaaS sifatida har tenant o'z Faktura.uz login + client_id/secret'ini bizga beradi (`tenant_secrets`), parolni saqlash kerak bo'ladi — bu xavfsizlik nuqtai nazaridan noqulay.
2. **Imzolash:** `POST Api/Sign/GetDocumentsHashCodes` (UniqueId massivi) → brauzerda E-IMZO bilan PKCS#7 → `POST Api/Sign/SignDocument` (`UniqueId`, `SignedContent`, `CertificateSerial`). Bizning `sign-challenge/submit-signed` oqimiga to'liq mos.
3. **Kiruvchi faktura:** **webhook yo'q** — faqat poll: `GET Api/Document/GetDocuments` (`CompanyInn` majburiy, `IsInbox`, `Statuses`, `Types`, `CreatedFrom/To`, `UpdatedFrom/To`, `Limit/Skip`). Sozlamadagi "Callback URL" — OAuth redirect maydoni, hodisa push qilinishi hujjatda tasvirlanmagan.
4. **VM 830 xavf darajasi kanali:** qaror ikki kanalni nomlaydi — (a) xavf darajasi **avtomatik shakllanadi va EHF rasmiylashtirilayotgan/taqdim etilayotganda soliq to'lovchiga ko'rsatiladi** (11-band) — amalda EDO oqimi ichida; (b) **my.soliq.uz shaxsiy kabineti** — xavf darajasi aks etgan to'lov hujjatlari (3-band), qizil EHF bo'yicha QQS'ni EHF ID'si bilan kabinet orqali to'lash (14-band), reyestrdan foydalanish (25-band). Operator API'si yoki "xabarnoma" qarorda tilga olinmagan. **Amalda** Didox API'si `scoring` maydonini qaytaradi (`0` — Низкий, `1` — Высокий, `null` — Нет данных); Faktura.uz API hujjatida va lending kodida xavf maydoni **topilmadi**.
5. **Sandbox/narx:** ommaviy sandbox hujjatlanmagan (`test.faktura.uz`, `testapi.faktura.uz`, `testaccount.faktura.uz` mavjud, lekin 403 — yopiq test stendi ehtimoli, tasdiqlanmagan). API alohida narxlanmaydi; tariflar tashkilotlar sonini cheklaydi va "Интеграция с внешними системами" tarif narxiga kirmaydi; summalar olinmadi.

### Dalil
- api.faktura.uz/help/ (HTTP Last-Modified 13.03.2023): «1. Войдите в аккаунт 2. Перейдите в настройки 3. Перейдите в Доступ к API и нажмите на кнопку "Настройки клиентов" … 6. После успешного сохранения, вы получите "client_secret"»; «username string … Имя пользователя password string … Пароль пользователья»; «expires_in … (по умолчанию - 604799) refresh_token …»; «Если пользователь прикреплен к нескольким предприятиям (т.е. мультиаккаунтный пользователь) Следует указать ИНН предприятия … ?companyInn=»; «Api/Sign/GetDocumentsHashCodes POST Получение хеш-кодов документов»; «Api/Sign/SignDocument POST … SignedContent string Да Результат подписи Pkcs7 … CertificateSerial»; «Api/Document/GetDocuments GET … IsInbox bool Нет Определяет входящие документы … UpdatedFrom long …». Sahifada "webhook"/"уведомлен" so'zlari yo'q.
- VM qarori №830, 26.12.2025 (kuchga kirgan 30.12.2025), [lex.uz/docs/-7962143](https://lex.uz/docs/-7962143): 3-band «soliq toʻlovchining shaxsiy kabinetida elektron hisobvaraq-fakturalarning xavf darajasini aks ettirgan holda toʻlov hujjatlarini shakllantirish … funksiyasini yaratsin»; 11-band «EHFlarga berilgan xavf darajasi avtomatik tarzda shakllantiriladi va soliq toʻlovchi tomonidan uni rasmiylashtirish va taqdim etishda koʻrsatiladi…»; 12-band — past xavf darajasi qabul qilingandan keyin o'zgarmaydi; 14-band «QQS tegishli EHFning identifikatsiya raqamini majburiy koʻrsatgan holda soliq toʻlovchining shaxsiy kabineti orqali toʻlanadi»; 25-band «… Reyestrda mavjud axborotdan soliq toʻlovchining shaxsiy kabineti orqali foydalanadi»; 4-band — yuqori xavfli ulush ≤10%.
- [api-docs.didox.uz/ru/integrators-documents](https://api-docs.didox.uz/ru/integrators-documents): javob namunasida `"scoring": null` (ro'yxat), `"scoring": 0` (tafsilot); Didox veb-ilova bandli (`didox.uz/index_cd87c57c.js`): `scoring:"Уровень риска"`, `scoring_values={0:"Низкий",1:"Высокий",null:"Нет данных"}`.
- [buxgalter.uz — «Как учитывать НДС по ЭСФ в зависимости от уровня риска с 1 января 2026 года»](https://buxgalter.uz/ru/esf2/kak_uchityvat_nds_po_esf_v_zavisimosti_ot_urovnya_riska_s_1_yanvarya_2026_goda) (10.06.2026, qisman pullik): «Уровень риска ЭСФ определяется автоматически в момент его оформления»; «В рекомендацию внесены изменения согласно Указу Президента №УП-100 от 26.05.2026».
- edo.faktura.uz `/js/app.9fd576b4.js`: «В одном аккаунте в системе можно иметь несколько организаций. Количество … будет исходя из вашего тарифного плана»; «Все тарифные планы предоставляют возможность пользоваться внешними модулями … Данная услуга не будет входить в стоимость тарифа».

### Ishonch
Auth/imzo/poll — **yuqori**; VM 830 matni va Didox `scoring` — **yuqori**; Faktura.uz'da xavf maydoni yo'qligi — **past** (faqat hujjatda yo'q, kabinet UI tekshirilmadi); "hamkor dasturi yo'q" — **o'rta**.

### Spec'ga ta'sir
- `21-integratsiyalar.md` §2, "API holati", Faktura.uz bandi — almashtirish:
  > **Faktura.uz** — ochiq API hujjati ([api.faktura.uz/help/](https://api.faktura.uz/help/), 2026-10-16 qayta tekshirildi): OAuth2 password grant `POST account.faktura.uz/token` — **tenantning o'z** Faktura.uz login/paroli + o'z kabinetida yaratgan `client_id/client_secret` (integrator kredensiali va hamkor dasturi hujjatda yo'q); token 7 kun, `refresh_token` bilan. Ko'p kompaniya — faqat "мультиаккаунт" (`?companyInn=`), tarif bilan cheklangan. Imzo: `Api/Sign/GetDocumentsHashCodes` → brauzerda E-IMZO PKCS#7 → `Api/Sign/SignDocument`. Kiruvchi hujjatlar — **faqat poll** (`GET Api/Document/GetDocuments?IsInbox=true&UpdatedFrom=…`), webhook yo'q. Sandbox — ommaviy emas (test xostlari 403), narx — tarif ichida emas, sotuv bo'limidan.
- `21-integratsiyalar.md` §2, uchinchi band (xavf-baholash kanali) — almashtirish:
  > VM 830 (11-band) bo'yicha xavf darajasi EHF rasmiylashtirilayotganda avtomatik shakllanadi va **EDO oqimida** ko'rsatiladi; QQS to'lovi va xavf reyestri — **my.soliq.uz kabinetida** (3, 14, 25-bandlar). Operator API'sida: **Didox — `scoring` maydoni** (`0` past/yashil, `1` yuqori/qizil, `null` — ma'lumot yo'q); **Faktura.uz — hujjatda maydon topilmadi** (Xat 4 bilan tasdiqlanadi). Shuning uchun `risk_flag` uch qiymatli: `green` / `red` / `unknown`; `unknown` bo'lsa QQS krediti **qizil kabi** (to'lovgacha kechiktirilgan) hisoblanadi va Buxgalter BO-15'da qo'lda belgilaydi (my.soliq kabinetidan ko'rib).
- `21` §2 adapter: `get_risk_flag(...) -> RiskFlag  # green|red|unknown; Didox: scoring, Faktura.uz: hozircha unknown` va §2.1 diagrammasidagi "poll — webhook mavjudligi ochiq savol" → "poll (ikkala operatorda webhook yo'q, `UpdatedFrom` bo'yicha inkremental)".
- `11-malumotlar-modeli.md` / `12-db-sxema.md`: `einvoices.risk_flag` CHECK `('green','red','unknown')`, default `'unknown'`.
- `21` Ochiq savol 11 va `04` Ochiq savol 11 — "VM 830 kanali" o'rniga: "Faktura.uz API'si xavf darajasini qaytaradimi — Xat 4 (Didox'da `scoring` bor)".
- `26` B#47 — interim matni: "Didox `scoring`; Faktura.uz — `unknown`, qizil kabi ehtiyotkor hisob + qo'lda belgilash".

### Holat: **QISMAN**
- **Qolgan:** Faktura.uz API'si xavf darajasini qaytaradimi; sandbox va narx; UP-100 (26.05.2026) VM 830 mexanizmiga nima o'zgartirgani.
- **Interim default:** `risk_flag='unknown'` → QQS krediti to'lovgacha kechiktiriladi (ehtiyotkor), Buxgalter qo'lda `green` qila oladi (audit bilan).
- **Kim tasdiqlaydi:** Faktura.uz sotuv/qo'llab-quvvatlash (Xat 4); UP-100 — P1/P7 partiyasi yoki buxgalter.

---

## OQ-020 — Didox API'ga to'liq kirish

### Javob
Didox API hujjati **endi ochiq** — `api-docs.didox.uz` (Wiki.js, 11 bo'lim: E-IMZO, ro'yxatdan o'tish, login, akkaunt, profil, hujjatlar, hujjat JSON, utilitalar, kataloglar, shablonlar, oferta imzolash) login talab qilmaydi. Ishlatish uchun **partner token** kerak — Didox akkaunt-menejeridan olinadi; har so'rovda `Partner-Authorization: <PARTNER_TOKEN>` sarlavhasi. Muhitlar: test `https://testapi3.didox.uz/`, prod `https://api-partners.didox.uz/`. Foydalanuvchi bizning partner token ostida `user-key` (UUID, 360 daqiqa) oladi: E-IMZO bilan (STIR PKCS#7 + `/v1/dsvs/timestamp` → `POST /v1/auth/{taxId}/token`), parol bilan (`/v1/auth/{taxId}/password`) yoki jismoniy shaxs kompaniyaga (`/v1/auth/company/{companyTaxId}/login`). API orqali ro'yxatdan o'tish ham bor (`/v1/auth/signup`). Imzo: `GET /v1/documents/{id}?owner=1` → base64 → E-IMZO `create_pkcs7` + timestamp → `POST /v1/documents/{id}/sign`; birinchi imzodan oldin oferta imzolanadi. Kiruvchi — faqat poll (`GET /v2/documents?owner=0`, `status`, `doctype`, `dateFromUpdated…`, `limit≤100`). Hujjatlarda `scoring` (VM 830 xavf) maydoni bor. Partner shartlari/narxi e'lon qilinmagan.

**Multi-tenant SaaS uchun Didox modeli Faktura.uz'dan qulayroq:** bitta platforma partner tokeni + har tenant foydalanuvchisining E-IMZO bilan olingan qisqa muddatli tokeni (parol saqlash shart emas), test muhiti bor, xavf darajasi API'da.

### Dalil
- [api-docs.didox.uz/ru/home](https://api-docs.didox.uz/ru/home): «Чтобы использовать API необходимо получить партнерский токен Тестовая URL https://testapi3.didox.uz/ Прод партнерский URL https://api-partners.didox.uz/ Для получения партнеского токена необходимо обратиться к Аккаунт менеджеру: https://t.me/Didox_account ; +998 50 122 05 18 Канал по изменениям и обновлениям в API Didox: https://t.me/didoxapiupdates»; «Во всех запросах обязателен заголовок партнёрской авторизации: Partner-Authorization: <PARTNER_TOKEN>»; «Все токены выдаются в формате UUID и действительны 360 минут.»
- [api-docs.didox.uz/ru/integrators-documents](https://api-docs.didox.uz/ru/integrators-documents): «owner 1 / 0 … 1 — исходящие, 0 — входящие»; «Перед первым подписанием у пользователя (или компании) должна быть подписана оферта».
- [api-docs.didox.uz/ru/integrators-eimzo](https://api-docs.didox.uz/ru/integrators-eimzo): «wss://127.0.0.1:64443/service/cryptapi … Origin:https://{your web site}» — imzo bizning domenimizda bo'ladi (OQ-028 bilan bog'liq).

### Ishonch
**Yuqori** (jonli rasmiy hujjat).

### Spec'ga ta'sir
- `21-integratsiyalar.md` §2, "API holati", Didox bandi — almashtirish:
  > **Didox** — ochiq API hujjati ([api-docs.didox.uz](https://api-docs.didox.uz/ru/home), login shart emas, 2026-10-16 tekshirildi). Kirish — Didox akkaunt-menejeridan **platforma partner tokeni** (`Partner-Authorization` sarlavhasi; t.me/Didox_account, +998 50 122 05 18). Test `testapi3.didox.uz`, prod `api-partners.didox.uz`. Tenant foydalanuvchisi E-IMZO (yoki parol) bilan 360 daqiqalik `user-key` oladi. Imzo — hujjat JSON base64 → E-IMZO PKCS#7 + timestamp → `POST /v1/documents/{id}/sign`. Kiruvchi — poll (`GET /v2/documents?owner=0`). Xavf darajasi — `scoring` maydoni. Partner shartnomasi/narxi — ochiq emas (commercial so'rov).
- `21` §13 jadvalidagi Didox qatori: "Yo'q — login talab qiluvchi portal" → "Hujjat ochiq; partner token kerak (akkaunt-menejer); test muhiti ✅ `testapi3.didox.uz`".
- `21` §2 "MVP bosqichi": "Didox API hujjati login ortida, faqat norasmiy SDK bor" iborasi olib tashlanadi; **asoschiga D-savol** sifatida qo'shiladi: "MVP operatori — Faktura.uz (qaror #23 tavsiya #4) qoladimi yoki Didox'ga almashtiriladimi (partner token modeli, test muhiti, `scoring` — multi-tenant uchun qulayroq)". Asosiy xulosalar 2-band: "Faqat 3 tizimda…" ro'yxatiga Didox qo'shiladi.
- `26` B#43 — Didox qismi yopiladi ("hujjat ochiq; qolgani — partner token olish, commercial").
- `03-modullar-talablari.md` M07 "Davlat tizimlari bog'liqligi": "Didox — … login talab qiladigan API" → "Didox — ochiq API, partner token bilan".

### Holat: **YOPILDI**
Research savoli (to'liq kirish yo'li) yopildi. Keyingi qadam — commercial: partner token so'rash (asoschi harakati, bloklamaydi). Operator tanlovini qayta ko'rish — asoschi qarori (D).

---

## OQ-021 — E-TTN: kanal, API, ichki ko'chirishda majburiylik

### Javob
1. **Amaldagi matn:** Nizom — VM 249-son (28.04.2021) **31-ilova**, VM 673 (21.12.2023) bilan kiritilgan va **VM 168 (18.03.2025, 19.03.2025 dan kuchda) bilan to'liq yangi tahrirda**. Muddatlar (VM 673, 2-band): 2024-04-01 dan yirik soliq to'lovchilar, 2024-07-01 dan barcha xo'jalik yurituvchi subyektlar.
2. **Kanal:** e-TTN **faqat EDO operatorlari** (Didox, Faktura.uz va boshqalar) axborot tizimi orqali, oferta/shartnoma asosida shakllantiriladi (Nizom 5, 6-band); rouming — "Yangi texnologiyalar" markazi. Tovar sotuv bilan bir vaqtda jo'natilsa — e-TTN **e-faktura bilan birlashtirilgan** holda shakllantiriladi (12, 33-band; VM 489 Nizom 4-ilova — birlashtirilgan EHF+TTN shakli). Haydovchi Face-ID bilan tasdiqlashi mumkin. Alohida davlat e-TTN API'si yo'q — operator API'si orqali.
3. **Operator hujjat turlari:** Faktura.uz ommaviy `GetDocumentTypes` ro'yxatida TTN turi **yo'q** (ro'yxat eskirgan bo'lishi mumkin; `UniversalInvoice=28` va birlashtirilgan shakl orqali bo'lishi ehtimoli bor); Didox'da "ТТН (новый)" turi bor (norasmiy SDK: `TTNBuilder (041)`; buxgalter.uz Didox qo'llanmasi). Amaliyotchilar ikkala operatorda e-TTN chiqarish mumkinligini tasdiqlaydi.
4. **Ichki ko'chirish (bir yuridik shaxs ichida):** **majburiy.** Nizomda alohida **"Ombordan omborga"** tashish turi bor — yuk jo'natuvchi bir vaqtda yuk oluvchi ham bo'ladi; bunda **EHF rasmiylashtirilmaydi**, faqat e-TTN. Istisno faqat: qo'lda/jamoat transportida/ro'yxatdan o'tmagan vositalarda tashish (24-band), davlat siri yoki xorijiy transport (25-band — qog'ozda).
5. **Yetkazib beruvchi do'konga olib kelganda:** e-TTN'ni **yuk jo'natuvchi (yetkazib beruvchi)** chiqaradi (4-band, odatda EHF bilan birlashtirilgan), do'kon (yuk oluvchi) tashish yakunida **elektron tasdiqlaydi yoki rad etadi** (17-band). Xaridor o'z transportida olib ketsa ham e-TTN kerak (3-band — "yuk oluvchi tomonidan oʻz transport vositasi … orqali tashish"); jo'natuvchi — sotuvchi.
6. **B2C:** jismoniy shaxsga chek bilan savdoda e-TTN shart emas (legalise.uz Q2); do'kon jismoniy shaxsga transportda yetkazsa — bir tomonlama e-TTN (28-band).
7. **Tuzatish/qaytarish:** yuk oluvchi tasdiqlagunga qadar — tuzatuvchi e-TTN (27-band); tasdiqlangandan keyin — asl jo'natuvchi manzillarni almashtirib "qo'shimcha" e-TTN (amaliyot, buxgalter.uz).

### Dalil
- VM 168, 18.03.2025, [lex.uz/docs/-7436697](https://lex.uz/docs/-7436697), ilova 3-band: «...249-son qarori bilan tasdiqlangan Tovar-transport yuk xatlarini ... nizom quyidagi tahrirda bayon etilsin».
- VM 673, 21.12.2023, [lex.uz/docs/-6709063](https://lex.uz/docs/-6709063), 2-band: «2024-yil 1-apreldan boshlab yirik soliq toʻlovchilar uchun, 2024-yil 1-iyuldan boshlab barcha xoʻjalik yurituvchi subyektlar uchun ... majburiy tartibda joriy etish...».
- Nizom (VM 168 tahriri): 1-band — «yuridik shaxslar, yakka tartibdagi tadbirkorlar, va ... daromadlari ... yuz million soʻmdan oshgan oʻzini oʻzi band qilgan shaxslar»; 5-band — «...elektron hujjat aylanish tizimi operatorlarining axborot tizimi orqali veb-sayt yoki maxsus mobil ilova yordamida shakllantiriladi»; 12-band — «elektron tovar-transport yuk xati elektron hisob-faktura bilan birlashtirilgan holda rasmiylashtirilishi mumkin…»; 13-band — «tashish turi (“Ombordan omborga”, “Sotuvchidan sotib oluvchiga”, “Qayta ishlash/xizmatlar koʻrsatishga”, “Pochta va kuryerlik xizmati orqali”) tanlanadi; ... “Ombordan omborga” rejimi tanlanganda, yuk joʻnatuvchi yuk oluvchi sifatida ham ishtirok etadi»; 16-band — «...elektron tovar-transport yuk xati rasmiylashtirilmagan yuklar yuk joʻnatuvchi tomonidan taqdim etilishi, yukni yetkazib beruvchi (yuk tashuvchi) esa uni tashish uchun qabul qilib olishi taqiqlanadi»; 17-band — «...yuk oluvchi esa yuk tashish jarayoni yakunlanganda tovar-transport yuk xatini elektron tasdiqlaydi yoki ... rad etishi mumkin»; 33-band — «yuklab joʻnatish bilan bir vaqtda realizatsiya qilinganda, elektron tovar-transport yuk xatini elektron hisobvaraq-fakturada birlashtirilgan holda shakllantirish».
- bss.uz savol-javob 15648 (26.05.2026): «Ҳа. Товар ўзининг бир омборидан бошқа бир омборига жўнатилганда ТТЮ расмийлаштирилади... Бундай ҳолда ЭҲФ расмийлаштирилмайди. Юк жўнатувчининг ўзи юк қабул қилувчи ҳам бўлади.»
- legalise.uz e-TTN FAQ (yangilangan 10.03.2026): Q1 «используйте функционал любого оператора ЭДО – didox.uz, faktura.uz»; Q2 «Нет, ЭТТН оформляется при перемещении грузов между субъектами предпринимательства» (jismoniy shaxsga chekli savdo haqida).
- buxgalter.uz text201304 (10.07.2024) — Didox'da "ТТН (новый)", "Дополнительный" ko'rinishi.
- Zid manba: kifato.uz (filiallararo e-TTN shart emas) — Rossiya 140-ФЗ bilan aralash, **ishonchsiz** deb baholandi.

### Ishonch
Ichki ko'chirishda majburiylik — **yuqori** (Nizom matni + amaliyot javobi); operator kanali — **yuqori**; operator API'sidagi aniq TTN kodlari — **o'rta**.

### Spec'ga ta'sir
**Muhim:** joriy interim ("ichki ko'chirishda talab qilinmaydi") **noto'g'ri** — teskarisiga o'zgaradi.
- `04-biznes-jarayonlar.md` Ochiq savol 5 — o'chiriladi, o'rniga BP-09 "Manba" eslatmasi:
  > E-TTN **ichki ko'chirishda ham majburiy** — Nizom (VM 249 31-ilova, VM 168 tahriri, 13-band) "Ombordan omborga" tashish turi: jo'natuvchi bir vaqtda yuk oluvchi, EHF chiqarilmaydi; istisno — qo'lda/jamoat transportida tashish (24-band). Ko'chirish hujjati jo'natilganda e-TTN (`transport_type=warehouse_to_warehouse`) shakllantiriladi, qabul qiluvchi filial tasdiqlaydi.
- `04` BP-09 jadvaliga yangi qadam: `| 2a | Omborchi (jo'natuvchi) | M06 | E-TTN ("Ombordan omborga") | E-TTN (EDO operatori), E-IMZO | — |` va 4-qadamga "qabul qiluvchi e-TTN'ni tasdiqlaydi".
- `21-integratsiyalar.md` §3 — "Maqsad" va "API holati" almashtirish:
  > M06 (filiallararo ko'chirish) — **majburiy** ("Ombordan omborga" rejimi, Nizom 13-band). Kanal — faqat EDO operatori (Didox — "ТТН (новый)"; Faktura.uz — ommaviy turlar ro'yxatida yo'q, Xat 4 bilan aniqlanadi). Sotuv bilan bir vaqtda jo'natishda e-TTN **e-faktura bilan birlashtirilgan** (12, 33-band) — kiruvchi xaridda alohida e-TTN emas, EHF'ning bir qismi sifatida keladi. Asos: VM 249 31-ilova (VM 168, 18.03.2025 tahriri), VM 673 (muddatlar).
- `21` §3 "MVP bosqichi": "keyin — faqat tashqi tashish…" → "**Kiruvchi (birlashtirilgan EHF+TTN)** — e-faktura bilan MVP'da (alohida ish yo'q, EHF payload'idan o'qiladi); **ichki ko'chirish e-TTN'i** — avtomatik yuborish MVP'dan keyin bo'lishi mumkin, lekin MVP'da M06 hujjatida `ettn_ref` + 'e-TTN operator kabinetida rasmiylashtirildi' tasdiq belgisi **majburiy maydon** (bo'sh bo'lsa ogohlantirish, avtotransport ko'chirishida M12 xavf ro'yxatiga tushadi)". Istisno uchun `transport_mode` (`vehicle`/`on_foot_or_public` — ikkinchisida e-TTN talab qilinmaydi).
- `03-modullar-talablari.md` M06 "Davlat tizimlari bog'liqligi"ga: "E-TTN — ichki ko'chirishda ham majburiy (Ombordan omborga)".
- `16-offline-sync.md` §7 va `03` M06 dagi "ichki ko'chirishda tovar egasi o'zgarmaydi" asoslanishi markirovka uchun qoladi, lekin "e-TTN zarurligi ochiq" iborasi → "e-TTN majburiy, offline ko'chirish yaratilsa e-TTN internet qaytgach (tashishdan oldin) rasmiylashtirilishi kerak — tashish boshlanishidan oldin e-TTN yo'qligi qonunbuzarlik (16-band)".
- `11-malumotlar-modeli.md` §9 / `12` — `ettn_documents` ga `transfer_id` (nullable), `transport_type` (`warehouse_to_warehouse`/`seller_to_buyer`/…), `direction` qo'shish; `30` §3-G bo'shlig'i M06 yozuvchisi bilan yopiladi.

### Holat: **YOPILDI**
Qonuniy javob aniq. Operator API'sidagi TTN kodlari — implementatsiya vaqtida operatordan (bloklamaydi).

---

## OQ-022 — Jismoniy shaxsga (B2C) nasiya savdosida e-faktura

### Javob
Jismoniy shaxsga chakana savdoda **kassa (onlayn-NKM yoki virtual kassa) cheki berilsa, e-faktura shart emas** — chek hisobvaraq-faktura o'rnini bosuvchi hujjat. **Nasiya nuansi:** VM 489 3-bandi to'lov naqd/karta bilan bo'lgan holat sifatida yozilgan; nasiya uchun amaliyot (bss.uz) — **tovar topshirilgan kuni to'liq summaga "Продажа" turidagi chek**, keyingi to'lovlarda "Кредит" turidagi cheklar. Agar jismoniy shaxs chek berilmasdan bank orqali to'lasa — uning JShShIR va ERI bilan **ikki tomonlama EHF** kerak (2022-07-11 dan bir tomonlama EHF cheklangan). YaTT/yuridik shaxs xaridor bo'lsa: chek faqat naqd/shaxsiy karta/korporativ karta (milliy valyutada) to'lovida EHF o'rnini bosadi; bank o'tkazmasida — EHF majburiy.

**Kesishma xavfi (muhim):** qaror #30 — "qarzga sotuvda fiskal chek chiqarilmaydi, har to'lovda chek". Amaliyot manbasi topshirish kuni to'liq "Продажа" chekini talab qiladi. Agar topshirish kuni chek bo'lmasa, B2C nasiyada "chek EHF o'rnini bosadi" asosi ham zaiflashadi. Bu P1 (OQ-009/010, fiskal chek turi) va `26` #9 bilan bir savol — u yerda hal qilinadi.

### Dalil
- Soliq kodeksi 47-modda 3-qism, [lex.uz/docs/-4674902](https://lex.uz/docs/-4674902) (1-qism O'RQ-1108, 25.12.2025 bilan o'zgargan, 2026-01-01 dan): «Tovarlarni (xizmatlarni) realizatsiya qilish chogʻida, agar sotuvchi xaridorga kassa cheki yoki belgilangan shakldagi boshqa hujjatni bersa, ushbu moddaning birinchi va ikkinchi qismlarida nazarda tutilgan qoidalar qoʻllanilmaydi.»
- VM 489 (14.08.2020) Nizom 3-band (VM 168 tahriri), [lex.uz/docs/-4948595](https://lex.uz/docs/-4948595): «Hisobvaraq-faktura quyidagi hollarda taqdim etilishi shart emas: sotilgan tovarlar (xizmatlar) uchun toʻlovlar naqd pulda yoki jismoniy shaxslarning bank kartalari, shuningdek, yuridik shaxslarning yoki yakka tartibdagi tadbirkorlarning milliy valyutadagi korporativ bank kartalari orqali amalga oshirilganda, nazorat-kassa texnikasi yoki virtual kassa cheki taqdim etilganda»; «...hujjatlar hisobvaraq-faktura oʻrnini bosadigan hujjatlar hisoblanadi.»
- bss.uz savol-javob 10902 (14.07.2025): «продавец в день передачи товара обязан выдать чек на полную стоимость товара с реквизитом «Тип платежа» – «Продажа»... При последующих платежах... отдельные чеки... с тем же типом – «Кредит».»
- buxgalter.uz text175937 (22.11.2021, Soliq qo'mitasi tushuntirishi): to'lov turlari «продажа; возврат; рассрочка (кредит); аванс».
- buxgalter.uz text183087: «...платеж за них идет без применения онлайн-ККМ (оплата через банк), оформляйте двусторонний ЭСФ».
- VM 489 9-band (VM 400, 30.06.2025 tahriri): xaridor (YaTT/yuridik shaxs) chekdan QQS kreditini keyingi oyning 10-sanasigacha kabinetda ro'yxatdan o'tkazish orqali oladi.

### Ishonch
B2C chek bilan — **yuqori**; nasiya chek mexanikasi — **o'rta** (ikkinchi darajali manba).

### Spec'ga ta'sir
- `04-biznes-jarayonlar.md` Ochiq savol 6 — almashtirish:
  > **6.** (javob topildi) Jismoniy shaxsga savdoda kassa cheki berilsa e-faktura talab qilinmaydi (SK 47-m. 3-q.; VM 489 Nizom 3-band — chek EHF o'rnini bosadi). Shart — chek berilgan bo'lishi; qaror #30 (nasiya sotuvda chek yo'q) bilan kesishma — `26` #9 / P1 natijasida hal qilinadi. Chek berilmasdan jismoniy shaxs bank orqali to'lasa — ikki tomonlama EHF (JShShIR+ERI) kerak.
- `04` BP-03 "Manba" eslatmasi: "B2C nasiya savdosida ham e-faktura kerakligi … taxmin" → "B2C — e-faktura yo'q (chek o'rnini bosadi, VM 489 3-band); B2B (`counterparty.kind=company`) va **YaTT bank o'tkazmasi bilan to'lasa** — e-faktura majburiy".
- `21` §2 "Chiquvchi e-faktura oqimi" 1-qadam: avtomatik `draft` sharti `counterparty.kind=company` → `counterparty.kind in (company, individual_entrepreneur)` **yoki** to'lov usuli `bank_transfer` bo'lsa (kontragent turidan qat'i nazar, jismoniy shaxs bo'lsa — ikki tomonlama EHF ogohlantirishi).
- `26` #9 ga havola qo'shish: "OQ-022: B2C nasiyada e-faktura istisnosi chek mavjudligiga tayanadi — qaror #30 bo'yicha qarorga kirish ma'lumoti".

### Holat: **QISMAN**
- **Qolgan:** nasiya B2C'da topshirish kunidagi chek talabi (qaror #30 bilan ziddiyat) va nasiya bank o'tkazmasi bilan qaytarilsa nima qilinadi.
- **Interim default:** B2C nasiya — e-faktura chiqarilmaydi (FLAG o'zgarmaydi); `FiscalPolicy` sozlamasi — P1 natijasigacha qaror #30 bo'yicha.
- **Kim tasdiqlaydi:** buxgalter (P7 bilan birga) va/yoki Soliq qo'mitasi (1198); P1 partiyasi (OQ-009/010) natijasi bilan solishtiriladi.

---

## OQ-023 — Yetkazib beruvchiga qaytarish: e-faktura turi va QQS

### Javob
1. **Hujjat:** tovar to'liq/qisman qaytarilganda **yetkazib beruvchi (asl sotuvchi) salbiy miqdor/summali "qo'shimcha" (дополнительный) EHF** chiqaradi, **xaridor (do'kon) uni tasdiqlaydi**. "Tuzatilgan" (исправленный) EHF — faqat **xato**larni tuzatish uchun (asl EHF bekor qilinadi), qaytarish uchun emas. Xaridor yetkazib beruvchiga "qaytarish EHF"ini o'zi yozishga haqli emas (bss.uz).
2. **QQS:** xaridor **qo'shimcha EHF asosida**, holat yuz bergan **soliq davrida**, ilgari hisobga olgan kiruvchi QQS'ni kamaytiradi (SK 257-m. oxirgi qism, 269-m.). Muddat — **1 yil** (kafolatli tovarda — kafolat muddati) (SK 257-m. 2-q.; VM 489 41-band).
3. **Muddat o'tgan yoki shartnomada qaytarish asosi yo'q bo'lsa:** qaytarish **xaridorning yetkazib beruvchiga realizatsiyasi** (teskari sotuv) — xaridor o'zi EHF chiqaradi, **chiquvchi QQS** va daromad solig'i/aylanma solig'i obyekti; yangi shartnoma tavsiya etiladi.
4. **Operator turlari:** Faktura.uz `factura_type`: «Стандартный 0, Дополнительный 1, Возмещение расходов 2, Без оплаты 3, Корректировочный 4», bog'lash maydonlari `korrektirovoch_document_number/date`; alohida "Возвратная Счёт фактура — SystemRefundInvoice (42)" ham bor — huquqiy maqomi aniq emas.
5. **E-TTN:** qaytarishda asl jo'natuvchi manzillarni almashtirib qo'shimcha e-TTN (amaliyot).
6. **Hisob qismi (2.20, 3-qator, AVECO narx farqi 6010/9430)** — bu partiyada tekshirilmadi, P7 (NSBU №21/№4) va buxgalterga o'tkaziladi.

### Dalil
- Soliq kodeksi, [lex.uz/docs/-4674902](https://lex.uz/docs/-4674902): 257-m. 1-q. «Soliq bazasiga tuzatish kiritish quyidagi hollarda amalga oshiriladi: 1) tovarlar toʻliq yoki qisman qaytarilganda»; 2-q. «...bir yillik muddat doirasida, kafolat muddati belgilangan tovarlar ... boʻyicha esa kafolat muddati doirasida»; 4-q. «...qoʻshimcha hisobvaraq-faktura ... asosida ... holatlar roʻy bergan soliq davrida amalga oshiriladi»; 5-q. «...ilgari yozib berilgan hisobvaraq-faktura bekor qilinadi va uning oʻrniga ... tuzatilgan hisobvaraq-faktura rasmiylashtiriladi» (xatolar uchun); oxirgi qism «...xaridor yetkazib beruvchi tomonidan rasmiylashtirilgan qoʻshimcha hisobvaraq-faktura asosida ilgari oʻzi hisobga olish uchun qabul qilgan soliq summasiga tegishli tarzda tuzatish kiritadi (koʻpaytiradi yoki kamaytiradi).»; 269-m. «...qoʻshimcha (yoki tuzatilgan) hisobvaraq-faktura asosida ... holatlar yuzaga kelgan soliq davrida amalga oshiriladi»; 47-m. 4-q. «...sotuvchi sotib oluvchiga ... qoʻshimcha yoki tuzatilgan hisobvaraq-fakturani taqdim etishi shart.»
- VM 489 Nizom 5-bob, [lex.uz/docs/-4948595](https://lex.uz/docs/-4948595): 40-band «...ushbu tovarlarni (xizmatlarni) oluvchi tomonidan tasdiqlanadigan qoʻshimcha hisobvaraq-faktura tuziladi: tovarlar toʻliq yoki qisman qaytarilganda»; 42-band «...tuzatish kiritilayotgan hisobvaraq-fakturaning raqami va sanasi; ... (ijobiy yoki salbiy)»; 44-band — tuzatilgan EHF faqat xato/o'zgartirish uchun.
- bss.uz maqola 5568 (14.10.2026): «Покупатель не имеет права выписывать возвратный ЭСФ продавцу — документ оформляет продавец... количество и стоимость показываются со знаком минус.»
- buxgalter.uz text207624 (11.04.2025): «покупатель оформил ЭСФ на имя поставщика... произвел обратную реализацию... сумма... является доходом, облагаемым НДС и налогом на прибыль или налогом с оборота»; text217132 (03.09.2026): «Возврат без оснований в договоре – это реализация с НДС».
- api.faktura.uz/help/: `factura_type` qiymatlari va `korrektirovoch_document_number/date` maydonlari.

### Ishonch
Qo'shimcha EHF yetkazib beruvchidan — **yuqori** (SK + Nizom); teskari sotuv talqini — **o'rta** (amaliyotchi manbalar); hisob provodkasi — **tekshirilmadi**.

### Spec'ga ta'sir
- `03-modullar-talablari.md` US-M07-05, ikkinchi Given — almashtirish:
  > Given asl kirim QQS bilan bo'lgan va qaytarish asl kirimdan **12 oy ichida** (kafolatli tovarda — kafolat muddati ichida), When qaytarish o'tkaziladi, Then hujjat holati "yetkazib beruvchidan **qo'shimcha (salbiy) e-faktura** kutilmoqda" bo'ladi; kiruvchi QQS (`vat_moves(kind=input)`, manfiy) **qo'shimcha EHF qabul qilingan (Buxgalter imzolagan) soliq davrida** yoziladi (SK 257, 269-m.; VM 489 40-band). Muddat o'tgan yoki shartnomada qaytarish asosi yo'q bo'lsa — tizim "**teskari realizatsiya**" ogohlantirishini ko'rsatadi: qaytarish do'konning yetkazib beruvchiga sotuvi sifatida chiquvchi EHF + chiquvchi QQS bilan rasmiylashtiriladi (buxgalter tasdig'i bilan).
- `13-provodka-qoidalari.md` §2.20 izohiga qo'shish: "2-qator (QQS kamaytirish) **qo'shimcha EHF qabul qilinganda** yoziladi (alohida voqea `supplier_return.vat_adjusted`, `einvoices(direction=in, factura_type=additional, related_doc=asl EHF)`), qaytarish o'tkazilganda emas. 12 oydan keyin — 2.20 o'rniga sotuv provodkasi (2.x, chiquvchi QQS), buxgalter tasdig'i bilan. 3-qator (AVECO farqi) — P7."
- `21` §2 `EInvoiceAdapter`: `fetch_incoming` natijasida `factura_type` (`standard/additional/corrected/...`) va `related_operator_doc_id` maydonlari; `einvoices` ga `factura_type`, `related_einvoice_id` ustunlari (`11`, `12`).
- `04` BP-04 (yoki yetkazib beruvchiga qaytarish oqimi) va `13` ogohlantirish 11 — "tuzatuvchi e-faktura talab qilinishi — ochiq savol" iborasi yuqoridagi bilan almashtiriladi.

### Holat: **QISMAN**
- **Qolgan:** (a) 2.20 3-qator (AVECO narx farqi 6010/9430) — P7/buxgalter; (b) 12 oylik muddat qaysi sanadan (asl EHF sanasi yoki qaytarish asosi yuzaga kelgan sana) hisoblanadi; (c) Faktura.uz "Возвратная (42)" turining huquqiy maqomi.
- **Interim default:** QQS kamaytirish faqat qo'shimcha EHF qabul qilinganda; 12 oy asl kirim EHF sanasidan (ehtiyotkor); 3-qator — joriy *taxmin* qoladi.
- **Kim tasdiqlaydi:** buxgalter/auditor (P7 bilan birga), kerak bo'lsa Soliq qo'mitasi.

---

## OQ-024 — E-ishonchnoma (Vakolat.uz): majburiylik, API, BP-01'da qachon

### Javob
1. **VM 825 (25.12.2025) tovar olish ishonchnomasi haqida emas.** U **davlat xizmatlaridan foydalanish** uchun ishonchnomalarni Vakolat.uz'da rasmiylashtirishni tartibga soladi; **yuridik shaxslar uchun — ixtiyoriy** ro'yxatdan o'tkazish; Vakolat ishonchnomasini barcha tashkilotlar tan olishi shart (3a-band), lekin u yagona amaldagi shakl emas. Shuning uchun "2026-01-01 dan uchinchi tomon dasturlar uchun ham majburiy" degan farazimiz **tasdiqlanmadi**.
2. **TMZ (tovar) olish ishonchnomasi** — **VM 249 3-ilova** (elektron ishonchnoma nizomi) bo'yicha **EDO operatorlari orqali** (Faktura.uz "Доверенность" `PowerOfAttorney=20`; Didox "Empowerment" 006). VM 825 VM 249 ga o'zgartirish kiritmagan. Elektron shakl qat'iy majburiy ekani bo'yicha birlamchi norma topilmadi (BHMS №4 95-band elektron shaklga ruxsat beradi; amaliyot — elektron).
3. **Yo'nalish (spec'dagi xato):** ishonchnomani **xaridor (do'kon) o'z xodimiga/vakiliga** beradi — EHF shakllantirishdan **oldin**; **sotuvchi** uni tekshiradi va tasdiqlaydi, so'ng EHF'ni ishonchnoma asosida shakllantiradi; EHF'ni **ishonchli shaxs imzolaydi**, keyin u xaridor kabinetida ko'rinadi. Ya'ni bizning BP-01'da do'kon "yetkazib beruvchi vakilining ishonchnomasini tekshirmaydi" — aksincha, **do'kon o'z omborchisiga ishonchnoma chiqaradi**.
4. **API:** Vakolat reyestri unikal raqam bo'yicha **hamma uchun ochiq qidiruv** (19-band, `vakolat.adliya.uz/search` — raqam + tekshiruv kodi); integratsiya faqat idoralararo platforma (MIP) orqali davlat tomoniga; **ommaviy dasturchi API topilmadi**. EDO ishonchnomalari esa operator API'si orqali o'qiladi/yaratiladi; QR-kod orqali tekshirish mumkin (VM 249 3-ilova 8-band).
5. **EHF'dagi havola:** Faktura.uz EHF maydonlari `doverennost_number`, `doverennost_date`; birlashtirilgan EHF+TTN shaklida «… -son ishonchnoma boʻyicha» qatori.

### Dalil
- VM 825, 25.12.2025, [lex.uz/docs/-7946843](https://lex.uz/docs/-7946843): 1-band «...davlat xizmatlaridan foydalanish ... boʻyicha boshqa shaxslarga ishonchnomalarni rasmiylashtirish; yuridik shaxslar tomonidan rasmiylashtirilgan ishonchnomalarni ixtiyoriy roʻyxatdan oʻtkazish; barcha turdagi ishonchnomalarning haqiqiyligini onlayn rejimda tekshirish»; Nizom 1-band «...hamda yuridik shaxslar tomonidan oʻz ixtiyoriga koʻra elektron ishonchnomalarni “Vakolat.uz” platformasi orqali rasmiylashtirish...»; Nizom 3-band «Mazkur Nizom qoidalari ishonchnoma asosida foydalanish mumkin boʻlgan davlat xizmatlariga nisbatan tatbiq etiladi.»; 19-band «Reyestr ishonchnomalarni unikal raqam orqali qidirish uchun barcha uchun ochiq hisoblanadi».
- VM 249 3-ilova, [lex.uz/docs/-5394977](https://lex.uz/docs/-5394977): 4-band «Elektron ishonchnomalar elektron hujjat aylanish tizimi operatorlari axborot tizimi orqali shartnoma yoki onlayn oferta asosida amalga oshiriladi.»; 8-band «Soliq toʻlovchilar ... QR-kod haqqoniyligini mobil ilovalar va rasmiy veb-sayt orqali tekshirish huquqiga ega»; 14-band — ishonchnoma «elektron hisobvaraq-fakturalarni shakllantirishga qadar»; sxema 1-bosqich (xaridor) «Elektron hisobvaraq-fakturani shakllantirishdan oldin»; 3-bosqich (sotuvchi) «Elektron ishonchnoma maʼlumotlarini tekshiradi va toʻgʻri boʻlsa, tasdiqlaydi... Elektron hisobvaraq-faktura shakllantirishdan oldin»; 15-band «elektron ishonchnoma asosida shakllantirilgan elektron hisobvaraq-fakturalarni ishonchli shaxs imzolashi va undan keyin elektron hisobvaraq-faktura xaridorning shaxsiy kabinetida koʻrinadi.»
- buxgalter.uz text167963 (05.03.2021): «Требование контрагента не противоречит законодательству, но и электронная форма доверенности допустима»; text160843 (24.10.2025): «доверенность на получение ТМЦ составляется в электронном виде» (amaliyot).
- api.faktura.uz/help/: hujjat turi `PowerOfAttorney` (20); EHF maydonlari `doverennost_number`, `doverennost_date`.

### Ishonch
VM 825 TMZ'ga tegishli emasligi — **yuqori**; EDO oqimi va yo'nalish — **yuqori**; elektron shaklning qat'iy majburiyligi — **o'rta**; Vakolat API yo'qligi — **o'rta-past** (topilmadi).

### Spec'ga ta'sir
- `04-biznes-jarayonlar.md` BP-01 diagramma va jadval 1a-qadami — almashtirish:
  > 1a. **Do'kon o'z vakiliga (Omborchi) e-ishonchnoma chiqaradi** (EDO operatori orqali, VM 249 3-ilova) — **e-fakturadan oldin**; yetkazib beruvchi uni tekshirib tasdiqlaydi va e-fakturani ishonchnoma asosida shakllantiradi; e-fakturani ishonchli shaxs (Omborchi) E-IMZO bilan imzolaydi. Vakolat.uz (VM 825) — davlat xizmatlari uchun, TMZ qabulida majburiy emas.
  Jadval qatori: `| 1a | Menejer/Buxgalter (chiqaradi), Omborchi (imzolaydi) | M07 | E-ishonchnoma (EDO: Faktura.uz PowerOfAttorney / Didox Empowerment) | E-faktura operatori, E-IMZO | Effekt yo'q |`.
- `04` Ochiq savol 10 va `21` Ochiq savol 7 — o'chiriladi (javob topildi).
- `21-integratsiyalar.md` §6 — sarlavha "E-ishonchnoma (EDO operatori orqali; Vakolat.uz — ixtiyoriy)"; "API holati":
  > TMZ olish ishonchnomasi — VM 249 3-ilova, EDO operatori hujjati (Faktura.uz `PowerOfAttorney=20`, Didox `Empowerment`), ya'ni **`EInvoiceAdapter` kengaytmasi** (`send_power_of_attorney`, `get_status`), alohida Vakolat adapteri kerak emas. VM 825 (Vakolat.uz) — davlat xizmatlari, yuridik shaxslar uchun ixtiyoriy; Vakolat reyestri faqat ommaviy veb-qidiruv (`vakolat.adliya.uz/search`), dasturchi API'si topilmadi — `PowerOfAttorneyAdapter.verify` **olib tashlanadi**; boshqa tashkilot Vakolat ishonchnomasini ko'rsatsa — qo'lda tekshirish (raqam + kod) va izoh.
- `21` §0 `outbox_jobs.kind`: `poa_verify` → `poa_send`; §13 jadvali Vakolat.uz qatori — "kerak emas (TMZ ishonchnomasi EDO orqali)"; BO-14 ro'yxatidan "Vakolat.uz" olib tashlanadi.
- `11-malumotlar-modeli.md` `goods_receipts.poa_number` qoladi + `poa_date`, `poa_einvoice_id` (EDO hujjati); `21` §6 "Xato UX" dagi "taxmin: ogohlantirish bilan davom etish" → "ishonchnomasiz e-faktura vakil tomonidan imzolanmaydi — Buxgalter (direktor ERI) imzolaydi; tizim bloklamaydi".
- `26` A#4 yopiladi ("VM 825 TMZ'ga tatbiq etilmaydi; ishonchnoma — EDO orqali").
- `02-rollar-va-ssenariylar.md` OS6 / Omborchi 1 va `03` OS9 — shu yo'nalishga moslashtiriladi.

### Holat: **YOPILDI**
Qolgan savol (Vakolat ommaviy API) mahsulot uchun endi kerak emas. Agar 2026 yilda TMZ ishonchnomasining elektron shaklini qat'iy majburiy qilgan akt chiqqan bo'lsa — yurist tekshiruvi (bloklamaydi).

---

## OQ-026 — Markirovkalangan tovar offline siyosatining huquqiy asosi

### Javob
1. **Offline sotish — qonunga zid emas.** VM 943 (VM 23 tahriri) 1-ilova 31-band: internet uzilganda chek offline beriladi, birinchi offline chek **48 soat** ichida operatorga uzatilishi shart; 48 soatdan keyin kassa **avtomatik bloklanadi**. Markirovkalangan tovarni offline sotishni alohida taqiqlovchi norma **topilmadi**.
2. **Kassaga qo'yilgan majburiy talablar (VM 943 2-ilova 3/6-band, VM 23 bilan):** markirovka kodi aks ettirilmasa chekni shakllantirishni **cheklash**; bitta chekda **dublikat** kodlarni cheklash. PQ-190 (23.05.2025) 7(в)(ii) — 2025-09-01 dan «**avval foydalanilgan** markirovka kodlari kiritilganda» chekni shakllantirishga yo'l qo'yilmaydi (VM 407, VM 75 ham shunday). VM 23 4(б) — 2026-07-01 dan chekda Asl belgisi kodini aks ettirish majburiy.
3. **"Ruxsat beruvchi rejim" (Rossiya kabi sotuvdan oldin online tekshiruv) — O'zbekistonda topilmadi.**
4. **Arxitekturaviy topilma:** chakana sotuvda **"muomaladan chiqarish" CRPT'ga to'g'ridan-to'g'ri emas, fiskal chek orqali** — kod chekka kiritiladi, **OFD har kuni real vaqtda** ma'lumotni Asl belgisi tizimiga uzatadi (VM 833 75–77-band; VM 23 Nizom 34–35-band; sxemalarda — "bir sutka ichida, NKT ishlamay qolgan hollar bundan mustasno"). Demak bizning `MarkingAdapter.sell` chakana sotuv uchun **ortiqcha** bo'lishi mumkin — kodni to'g'ri chekka yozish (`FiscalAdapter`) asosiy majburiyat.
5. **Xaridordan qaytarish:** kod ko'rsatilgan **qaytarish fiskal cheki** ("tushumni qaytarish" belgisi) orqali OFD'ga; DataMatrix shikastlanmagan bo'lsa qayta markirovka shart emas (VM 833 84, 90, 77(д)-band). "Faqat online" talabi qonunda **yo'q** — qaytarish cheki ham oddiy chek, 31-banddagi offline qoida unga ham tatbiq etiladi. Bizning siyosat — **qonundan qat'iyroq ichki tanlov** (firibgarlik/kod holatini tekshirish xavfi uchun asoslangan, qoldirsa bo'ladi).
6. **Ichki ko'chirish:** VM 833 Qoidalarida o'z filial/omborlari orasidagi ko'chirishni CRPT'ga xabar qilish majburiyati **topilmadi** — barcha xabarnomalar egalik o'tishi/komissiyaga, EHF shaklida (ikki STIR) bog'langan. Offline ko'chirish siyosati bunga zid emas.
7. **Ochiq xavf:** offline holatda kassa "kod boshqa joyda avval ishlatilganmi"ni bila olmaydi — PQ-190 tekshiruvi kassada (online) bo'ladimi yoki OFD/Asl belgisi tomonida keyin — norma aniq emas. **Tavsiya:** qurilma + tenantning boshqa kassalari bo'yicha lokal dublikat nazorati (sinxronlangan `marking_codes` keshi).
8. **Rossiya analogi:** Честный ЗНАК motor moylari uchun ruxsat beruvchi rejim (01.10.2026 yangilik) — «Проверка обязательна в режиме онлайн или офлайн» (lokal modul orqali); PP 1944 matni ochilmadi.

### Dalil
- VM 943 (23.11.2019, VM 23 tahriri), [lex.uz/docs/4603329](https://lex.uz/docs/4603329), 1-ilova 31-band: «...Интернет тармоғидаги вақтинча узилишлар бўлганда ... чеклар оффлайн режимида берилиши мумкин. Бунда биринчи оффлайн режимда шаклланган чекни 48 соат ичида операторга узатилиши таъминланиши зарур.»; 2-ilova: «48 соат оффлайн режимида ишлагандан сўнг автоматик блоклаш тизимига ўтиш»; «маркировка коди акс эттирилмаган тақдирда, чекни шакллантириш имкониятини чеклаш механизмига эга бўлиши; касса чекида иккита бир хил маркировка кодларни (дубликатларни) акс эттириш имкониятини чеклаш...».
- PQ-190, 23.05.2025, [lex.uz/docs/7540338](https://lex.uz/docs/7540338), 7(в)(ii): «аввал фойдаланилган маркировка кодлари киритилганда онлайн НКТнинг касса чекини шакллантиришга йўл қўйилмайди».
- VM 23, 23.01.2026, [lex.uz/docs/8012407](https://lex.uz/docs/8012407), 4(б): «товарлар учун «Asl belgisi» МАТда мавжуд рақамли маркировка кодлари мажбурий акс эттирилишини белгилаш» (2026-07-01 dan).
- VM 833, 31.12.2020, [lex.uz/docs/5205248](https://lex.uz/docs/5205248), 1-ilova: 75-band «чакана савдосини амалга оширувчи ... иштирокчилари маркировкалаш ахборот тизимига назорат-касса техникасини қўллаш билан маҳсулотнинг айланмадан чиқарилиши тўғрисидаги маълумотни йўналтиради»; 77-band «Фискал маълумотлар оператори ҳар куни реал вақт режимида ... маркировкалаш ахборот тизимига узатади» (maydonlar orasida «тушум ..., тушумни қайтариш»); 84-band «Истеъмолчи томонидан маҳсулот рақамли идентификациялаш воситаси шикастланмаган ҳолда қайтарилганда маҳсулот қайта маркировкаланиши шарт эмас…»; 90-band «...аввал сотилган маҳсулотни қайтариш аломати билан электрон фискал ҳужжат шаклида ... Операторга йўллайди».
- VM 631 (01.11.2022, suv/ichimliklar), [lex.uz/docs/6266709](https://lex.uz/docs/6266709) va VM 149 (02.04.2022, dori), [lex.uz/docs/5936145](https://lex.uz/docs/5936145) sxemalari: «бир сутка»; «Онлайн-касса аппарати ишламай қолиши ҳоллари бундан мустасно».
- "Рухсат берувчи режим" iborasi VM 737, 833, 943, 631, 149, 322, 23, PQ-190 matnlarida va crpt-turon.uz'ning 136 yangiligida **uchramadi**. aslbelgisi.uz (sertifikat muddati o'tgan, FAQ yo'q), help.crpt-turon.uz (403).
- Честный ЗНАК, 01.10.2026: [честныйзнак.рф/info/news/start-markirovki-kolbasy-i-zapusk-razreshitelnogo-rezhima-dlya-motornykh-masel…](https://xn--80ajghhoc2aj1c8b.xn--p1ai/info/news/start-markirovki-kolbasy-i-zapusk-razreshitelnogo-rezhima-dlya-motornykh-masel-chto-menyaetsya-v-sis/).

### Ishonch
48 soat + bloklash + OFD orqali uzatish — **yuqori**; ruxsat beruvchi rejim yo'qligi — **o'rta** (topilmadi xulosasi); offline qaytarish qonuniyligi — **o'rta**; ichki ko'chirish — **o'rta**.

### Spec'ga ta'sir
- `16-offline-sync.md` §7 boshiga huquqiy asos qo'shish:
  > **Huquqiy asos (P2, 2026-10-16):** offline chek VM 943 1-ilova 31-band bilan ruxsat (48 soat, keyin kassa bloklanadi); chakana sotuvda markirovka kodi **fiskal chek orqali** OFD → Asl belgisi ga uzatiladi (VM 833 75–77-band) — sotuvchi CRPT'ni alohida "sotdim" deb chaqirmaydi; O'zbekistonda "ruxsat beruvchi rejim" (sotuvdan oldin majburiy online tekshiruv) topilmadi. Kassa majburiy cheklovlari: kodsiz markirovkali qator — chek yo'q; bitta chekda dublikat kod — yo'q; **avval ishlatilgan kod — yo'q** (PQ-190 7(в)(ii)) → offline'da **lokal dublikat nazorati** (qurilma + tenant bo'yicha sinxronlangan `marking_codes`) majburiy.
- `16` §7 qaytarish bandi: "Nega: rasmiy qaytarish uchun kod yozilgan maxsus qaytarish cheki kerak…" ga qo'shish: "Qonun offline qaytarish chekini taqiqlamaydi (VM 833 84/90-band) — bu **ichki ehtiyot tanlovi** (kod holatini tekshirish, firibgarlik); kelajakda `FiscalPolicy.marking_offline_return=allow` bayrog'i bilan yumshatilishi mumkin".
- `16` §7 ko'chirish bandi: "(ichki ko'chirishga emas — bu taxmin, huquqiy xat bilan tasdiqlanadi)" → "(VM 833 Qoidalarida ichki ko'chirish uchun CRPT xabarnomasi talabi yo'q; xabarnomalar egalik o'tishiga bog'liq — 66–67-band). **E-TTN esa majburiy** (OQ-021)".
- `21-integratsiyalar.md` §4 "API holati" — "OFD orqali (yoki to'g'ridan-to'g'ri, aniq emas)" → "chakana sotuv va xaridordan qaytarish — **OFD orqali** (VM 833 75–77, 90-band; chekda kod majburiy, VM 23 4(б), 2026-07-01 dan)". `MarkingAdapter`: `sell`/`return_codes` chakana yo'l uchun **ixtiyoriy** (CRPT tasdiqlasa olib tashlanadi), asosiy yo'l — `FiscalReceiptPayload.lines[].marking_code`; `verify_code` — ixtiyoriy sifat tekshiruvi (qonuniy talab emas), lekin "avval ishlatilgan kod" xavfini kamaytiradi.
- `21` §4 "Xato UX": "MVP standart siyosat sotuvni rad etish — bu taxmin" → "dublikat/avval ishlatilgan kod bilan chek shakllantirish **qonun bo'yicha taqiqlangan** (PQ-190 7(в)(ii), VM 943 2-ilova) — rad etish taxmin emas, majburiy".
- `21` Ochiq savol 2 va `26` (OQ-026) — "huquqiy tasdiq" o'rniga qolgan 2 savol (Xat 2'ga qo'shiladi, quyida).
- **OQ-025 (E) ga kirish:** CRPT API'siga ehtiyoj chakana sotuv uchun kamayadi (OFD orqali) — Bosqich 5 BLOK ko'lami qisqarishi mumkin; Xat 2'ga savol: "chakana sotuvchi uchun OFD orqali uzatishdan tashqari to'g'ridan-to'g'ri API chaqiruvi talab qilinadimi".

### Holat: **QISMAN**
- **Qolgan (Xat 2 ga qo'shiladi):** (1) "avval ishlatilgan kod" tekshiruvi offline chekda qanday ishlaydi (kassa tomonida yoki OFD/CRPT keyin rad etadimi); (2) offline qaytarish chekidan tashqari VM 833 84-banddagi ma'lumotni Asl belgisiga alohida kiritish kerakmi; (3) ichki ko'chirishni xabar qilish majburiyati yo'qligini tasdiqlash.
- **Interim default:** 01 #17 siyosati o'zgarmaydi + lokal dublikat nazorati qo'shiladi; qaytarish — faqat online (ichki tanlov).
- **Kim tasdiqlaydi:** CRPT Turon (Xat 2), "Yangi texnologiyalar" (OFD, Xat 1); yurist — ixtiyoriy.

---

## OQ-027 — 72 soatlik ko'chirish muddati

### Javob
1. **VM 23 dagi 72 soat** — Nizom matnida emas, uning **2-ilovasi (sxema) 4-bosqichida**; faqat **o'simlik yog'i tajriba loyihasi** ishtirokchilari uchun (ishtirok **ixtiyoriy**, Nizom 4-band); **subyektlar o'rtasida egalik o'tganda** topshirish/qabul xabarnomasini (EHF shaklida, ikki tomon ERI) yuborish muddati.
2. **Boshqa sxemalar:** suv va salqin ichimliklar (VM 631, 5-ilova sxema 4-bosqich) — 72 soat, **lekin** shu Nizom 38-bandi muddatlarni VM 833 ga havola qiladi (3 ish kuni) — ichki ziddiyat; dori vositalari (VM 149, 6-ilova sxema) — 72 soat; VM 322 (20.05.2021) pilot sxemalari — 72 soat va ayrim bandlarda 3 ish kuni.
3. **Umumiy qoida (VM 833 Qoidalari 66–67-band):** egalik o'tishi (va komissiya/agentlik) bo'yicha jo'natuvchi va qabul qiluvchi xabarnomani **3 ish kuni** ichida, **lekin tovar uchinchi shaxsga berilgan kundan kechiktirmay** imzolaydi. Shuningdek 79 (sotuvdan boshqa sabab bilan chiqarish), 85 (yuridik shaxsning qaytarishi), 87-band (ma'lumot o'zgarishi) — 3 ish kuni.
4. **Ichki ko'chirish:** hamma muddatlar **egalik o'tishiga** bog'liq — bir yuridik shaxsning o'z filial/omborlari orasidagi ko'chirishga **tegishli emas** (OQ-026, 6-band).
5. **Bizga ta'siri:** 72 soatlik kuzatuv M06 (ichki ko'chirish) uchun **noto'g'ri joyda** — muddat M07 (kirim, yetkazib beruvchidan qabul) va yetkazib beruvchiga qaytarish xabarnomasini **tasdiqlash** uchun kerak, qiymati tovar guruhiga bog'liq (umumiy 3 ish kuni; suv/dori/pilot — 72 soat).

### Dalil
- VM 23, 23.01.2026, [lex.uz/docs/8012407](https://lex.uz/docs/8012407): 1-band «...Солиқ қўмитасининг ўсимлик ёғини рақамли маркировкалаш механизмларини ишлаб чиқиш бўйича тажриба лойиҳаларини ... амалга ошириш тўғрисидаги таклифига розилик берилсин.»; 1-ilova 4-band «Маҳсулотлар айланмаси субъектлари тажриба лойиҳасида ихтиёрий равишда қатнашадилар.»; 30(а)-band «маҳсулотни тажриба лойиҳаси иштирокчилари — маҳсулот айланмаси субъектлари ўртасида ўтказишда (қабул қилишда) ... эгалик ҳуқуқи ёки реализация қилиш учун ... ЭҲФ шаклида хабарнома яратиш; ... ҳар икки томоннинг ... ЭРИ билан имзолаш»; 2-ilova sxema 4-bosqich «...маҳсулотлар муомаласи субъектлари — тажриба лойиҳаси иштирокчилари ўртасида маҳсулотларни топшириш (қабул қилиш) вақтида ... «Asl belgisi» МАТга юборади... — Маҳсулотларга эгалик ҳуқуқи ўтгандан сўнг 72 (етмиш икки) соатдан кўп бўлмаган муддатда».
- VM 833, [lex.uz/docs/5205248](https://lex.uz/docs/5205248), 66-band «Эгалик ҳуқуқи ... ўтишини назарда тутувчи битимлар ҳамда комиссия ва (ёки) агентлик шартномалари доирасида маҳсулотни бериб юборишда ... хабарномани шакллантиради (ЭҲФ шаклида) ҳамда ... юклаб жўнатиш ... кунидан бошлаб 3 иш кунидан ортиқ бўлмаган муддатда, аммо ушбу маҳсулот учинчи шахсларга бериб юборилиши кунидан кечиктирмасдан, уни ЭРИ билан имзолайди.»; 67-band «қабул қилинган кундан бошлаб 3 иш кунидан ортиқ бўлмаган муддатда...».
- VM 631, [lex.uz/docs/6266709](https://lex.uz/docs/6266709), sxema: «Сув ва салқин ичимликларга эгалик ҳуқуқи ўтгандан сўнг 72 (етмиш икки) соатдан кўп бўлмаган муддатда»; VM 149, [lex.uz/docs/5936145](https://lex.uz/docs/5936145): «Дори воситалари ва тиббий буюмларга эгалик ҳуқуқи ўтгандан сўнг 72 (етмиш икки) соатдан кўп бўлмаган муддатда»; VM 322, [lex.uz/docs/5429990](https://lex.uz/docs/5429990).

### Ishonch
**Yuqori** (birlamchi matnlar to'liq o'qildi). VM 631 ichki ziddiyati — yurist uchun eslatma.

### Spec'ga ta'sir
- `21-integratsiyalar.md` Asosiy xulosalar 3-band: "markirovkalangan tovar ko'chirish **72 soat** (23-son qaror, 2026-01-23)" → "markirovkalangan tovar **egalik o'tishi** xabarnomasi — umumiy **3 ish kuni** (VM 833 66–67-band), ayrim guruhlarda (suv/ichimlik VM 631, dori VM 149, o'simlik yog'i pilot VM 23) **72 soat**".
- `21` §4 "SLA" — almashtirish:
  > Markirovkalangan tovar **subyektlar o'rtasida** (yetkazib beruvchidan kirim, yetkazib beruvchiga qaytarish) egalik o'tganda topshirish/qabul xabarnomasi (EHF shaklida) — **3 ish kuni**, lekin tovar uchinchi shaxsga berilgunga qadar (VM 833 66–67-band); suv/ichimlik, dori va o'simlik yog'i pilot sxemalarida — **72 soat**. Muddat `marking_product_groups.acceptance_deadline` (seed: `3_business_days` / `72_hours`) konfiguratsiyasi bilan. **Ichki ko'chirish (M06) uchun CRPT muddati yo'q.**
- `21` §4 "Qayta urinish": "ko'chirish uchun **72 soat** oynasida (pilot normasi, ichki siyosat sifatida qabul qilindi)" → "kirim/qaytarish xabarnomasi uchun guruh muddati oynasida".
- `03-modullar-talablari.md` M06 236-qator ("ko'chirish muddati 72 soatdan oshmasligi kerak …") — o'chiriladi; o'rniga M07: "Markirovkalangan tovar kirimida Asl belgisi qabul xabarnomasi (EHF) tovar guruhi muddatida (umumiy 3 ish kuni, ayrim guruhlarda 72 soat) imzolanishi kerak; tizim muddatni kuzatadi va ogohlantiradi, bloklamaydi." M06 chekka holatlaridagi "72 soatlik muddat buzilgani…" bandi M07 ga ko'chadi.
- `04` BP-09 3a-qadami "Asl belgisi (72 soat — 23-son qaror)" → "— (ichki ko'chirish CRPT'ga xabar qilinmaydi; VM 833)"; BP-01 5-qadamiga muddat qo'shiladi.
- `16` §7 va `03` M06 239-qatordagi "72 soatlik muddat hisoblagichi offline davrni ham hisobga oladi" — o'chiriladi.

### Holat: **YOPILDI**
VM 631 dagi 3 ish kuni ↔ 72 soat ziddiyati — konfiguratsiyada qat'iyrog'i (72 soat) olinadi; yurist ko'zdan kechirishi ixtiyoriy.

---

## OQ-028 — E-IMZO: dasturchi hujjati, prod kalit jarayoni, qo'llab-quvvatlash

### Javob
1. **Rasmiy dasturchi portali yo'q.** `e-imzo.uz` endi `e-imzo.soliq.uz` ga yo'naltiradi — faqat oxirgi foydalanuvchi uchun (kalit olish, modulni yuklab olish). Amaldagi asosiy integratsiya qo'llanmasi — [github.com/qo0p/e-imzo-doc](https://github.com/qo0p/e-imzo-doc) "Инструкция по интеграции E-IMZO" (**2026-10-09 yangilangan**). JS kutubxonalari — `test.e-imzo.uz/demo/` dagi `e-imzo.js`, `e-imzo-client.js`, `e-imzo-init.js` (`CAPIWS` obyekti).
2. **Uch alohida komplekt, hammasini НИЦ "Yangi texnologiyalar" (yt.uz) beradi:**
   - **API-KEY** — **bitta production domen** uchun; boshqa domen yoki **subdomen — alohida kalit**; IP-manzilli prod sayt uchun berilmaydi. Lokal/test uchun `localhost`/`127.0.0.1` kalitlari va E-IMZO tray-menyusida "Режим разработчика". E-IMZO v6 kalitni sahifa domeni bo'yicha o'zi yuklay oladi.
   - **VPN-kalit** (E-IMZO-SERVER uchun) — test `testvpn.e-imzo.uz:2443` va prod `vpn.e-imzo.uz:3443` — **har xil kalitlar**; serverlar **faqat O'zbekiston ichidan** ochiladi.
   - **SiteID** — faqat ID-karta/mobil ssenariy uchun.
3. **E-IMZO-SERVER** (Java 8 jar) — faqat **litsenziya kelishuvi + yozma shartnoma**dan keyin, **yopiq Telegram kanal** orqali tarqatiladi; shartnomasiz foydalanish — НИЦ mualliflik huquqini buzish.
4. **Test muhiti:** `test.e-imzo.uz/demo/`, test kalit yaratish `test.e-imzo.uz/registrator/public/ckc.html`, ID-karta emulyatori `wss://test.e-imzo.uz/idcard-emulator`, TestCA «CN=TestCA,O=test.e-imzo.uz».
5. **Prod kalit olish va qo'llab-quvvatlash:** yt.uz "Услуги по интеграции E-imzo" — qayta qo'ng'iroq so'rovi formasi; aloqa: **(71) 202-32-32, info@yt.uz**, Toshkent, Muqimiy 166. **Narx, ariza shakli va muddat ommaviy emas.**
6. **Arxitekturaga ta'sir:** imzolash sahifasi **bizning domenimizda** bo'lishi shart (Didox ham `Origin:https://{your web site}` ni talab qiladi) — tenant uchun alohida subdomenlar ishlatilsa, har biriga alohida API-KEY kerak bo'ladi. Shuning uchun imzolash bitta umumiy domenda (masalan `app.<domen>`) bo'lishi kerak. Server tomonda PKCS#7 tekshiruvi uchun E-IMZO-SERVER (shartnoma) **yoki** o'z tekshiruvimiz (O'zDSt kriptografiyasi — murakkab) — birinchisi tavsiya etiladi.

### Dalil
- [github.com/qo0p/e-imzo-doc README](https://github.com/qo0p/e-imzo-doc) (push 2026-10-09): «API-KEY и VPN-ключ выдаёт НИЦ НТ, это разные комплекты.»; «API-KEY выдаётся на один production-домен. Другой домен или поддомен требует отдельный API-KEY. Для production-сайта по IP-адресу API-KEY не выдаётся. … Для тестового домена или IP вместо ключа включается «Режим разработчика» в Tray-меню E-IMZO … В E-IMZO v6 локальное приложение может загрузить API-KEY само по домену открытой страницы.»; «Тестовый и промышленный VPN — разные адреса (testvpn.e-imzo.uz:2443 и vpn.e-imzo.uz:3443) и разные ключи.»; «Программное обеспечение e-imzo-server официально распространяется только через Telegram-канал разработчика. Канал не публичный: ссылка выдаётся после лицензионного соглашения и подписания договора.»; «Требуется: JRE v1.8 … (сервера доступны только из Узбекистана)»; «Использование модулей, без заключенного письменного договора является нарушением авторского права НИЦ.»
- [yt.uz/ru/services/5](https://yt.uz/ru/services/5): «Услуги по интеграции E-imzo … Сервис позволяет использовать ЭЦП выданный НИЦ НТ для идентификации пользователей на всех официальных веб-сайтах … Запрос обратного звонка … (71) 202-32-32 info@yt.uz».
- [yt.uz/ru/services/7](https://yt.uz/ru/services/7): «Регистрация юридических лиц в качестве оператора системы оборота ЭСФ … даёт возможность осуществлять деятельность информационного посредника» (o'z EDO operatori bo'lish yo'li — ma'lumot uchun).
- [e-imzo.soliq.uz](https://e-imzo.soliq.uz/): «Muallifi : "Янги Технологиялар" илмий ахборот маркази … (71) 202-32-32 info@yt.uz».
- [api-docs.didox.uz/ru/integrators-eimzo](https://api-docs.didox.uz/ru/integrators-eimzo): «Origin:https://{your web site}».

### Ishonch
Texnik jarayon va kalit beruvchi — **yuqori**; narx/muddat — **past** (ommaviy emas).

### Spec'ga ta'sir
- `21-integratsiyalar.md` §5 "API holati" — almashtirish:
  > Rasmiy dasturchi portali yo'q; amaldagi qo'llanma — [qo0p/e-imzo-doc](https://github.com/qo0p/e-imzo-doc) (2026-10-09). Prod uchun НИЦ "Yangi texnologiyalar"dan (yt.uz, (71) 202-32-32, info@yt.uz) **uch komplekt**: (1) **API-KEY** — bitta prod domen uchun (har subdomen — alohida kalit; IP uchun berilmaydi); (2) **VPN-kalit** E-IMZO-SERVER uchun (`vpn.e-imzo.uz:3443`, faqat O'zbekiston IP'laridan — server UzCloud'da bo'lishi shart); (3) SiteID (faqat ID-karta/mobil). **E-IMZO-SERVER** — litsenziya + yozma shartnoma bilan, yopiq Telegram kanal orqali. Test: `testvpn.e-imzo.uz:2443`, TestCA, `test.e-imzo.uz/demo/`, dev uchun "Режим разработчика". Narx/muddat — so'rov bilan.
- `21` §5 "Xavfsizlik"ga qo'shish: "**Imzolash faqat bitta umumiy domenda** (`app.<domen>`) — tenantga alohida subdomen ishlatilmaydi (har biriga API-KEY kerak bo'lardi). Yangi subdomen qo'shish = yangi API-KEY arizasi (ops chek-listi)."
- `21` §5 "MVP bosqichi" — "Zaxira yo'l" oldidan: "**Bosqich 0'da yt.uz bilan shartnoma arizasi** (API-KEY + VPN-kalit + E-IMZO-SERVER litsenziyasi) — OFD reyestr arizasi bilan parallel; dev/test — 'Режим разработчика' va TestCA bilan bloklanmaydi". `27-backlog.md` 0-bosqichga shu vazifa.
- `21` §13 E-IMZO qatori: "Prod sertifikat olish jarayoni, qo'llab-quvvatlash kanali" → "Ma'lum: API-KEY/VPN/E-IMZO-SERVER — yt.uz shartnomasi; noma'lum: narx, muddat".
- `05-mvp-chegarasi.md` §4.5 (5-xavf) — "Hali ochiq" → "Qisman yopildi: jarayon va beruvchi ma'lum (yt.uz), narx/muddat — so'rov bilan".
- `25-nofunksional-talablar.md` hosting bandiga: "E-IMZO-SERVER O'zbekiston ichidagi IP'dan ishlashi shart (UzCloud tanlovini tasdiqlaydi)".

### Holat: **QISMAN**
- **Qolgan:** API-KEY va E-IMZO-SERVER shartnomasi narxi, ariza shakli, muddati.
- **Interim default:** dev/test — TestCA + "Режим разработчика" + `testvpn`; prod jadvalida ~1 oy bufer; imzolash bitta umumiy domenda.
- **Kim tasdiqlaydi:** НИЦ "Yangi texnologiyalar" ((71) 202-32-32, info@yt.uz) — Xat 1 q4 ga qo'shiladi yoki alohida so'rov (asoschi).

---

## Kesishmalar va asoschi e'tiboriga (D-savollar)

1. **Operator tanlovi (OQ-019/020):** Didox — ochiq hujjat, test muhiti, platforma partner tokeni (tenant parolini saqlamaymiz), `scoring` maydoni. Faktura.uz — tenantning o'z login/parolini saqlash, xavf maydoni topilmadi, sandbox yopiq. **Tavsiya:** qaror #23 tavsiya #4 ni qayta ko'rish — MVP operatori Didox (yoki ikkalasi `EInvoicePort` ortida, Didox birinchi). Yakuniy so'z — asoschida.
2. **Qaror #30 ↔ OQ-022:** nasiya B2C'da topshirish kuni to'liq "Продажа" cheki amaliyoti qaror #30 ga zid bo'lishi mumkin — P1 (OQ-009/010) va `26` #9 bilan birga hal qilinadi.
3. **OQ-021 ↔ 01 #23 tavsiya #5 / 16 §7:** offline ichki ko'chirish (markirovka) qonuniy jihatdan qoladi, lekin avtotransportda tashishdan oldin e-TTN **majburiy** — offline yaratilgan ko'chirish hujjati tashish boshlanishidan oldin e-TTN bilan rasmiylashtirilishi kerak (yoki "qo'lda/jamoat transporti" istisnosi belgilanadi).
4. **OQ-026 ↔ OQ-025 (E, BLOK):** chakana sotuv va xaridordan qaytarishda kod OFD orqali Asl belgisiga ketadi — CRPT API'ga ehtiyoj asosan **kirim qabul xabarnomasi** (M07), yetkazib beruvchiga qaytarish va hisobdan chiqarish uchun qoladi. Xat 2'ga savollar qo'shiladi (OQ-026 "Qolgan" bandi).
5. **OQ-023 ↔ P7:** 2.20 provodkasining 3-qatori va QQS kamaytirish vaqti (qo'shimcha EHF qabul qilingan davr) P7 natijasi bilan kelishiladi.
6. **Xat 2 (CRPT Turon) ga qo'shimcha 3 savol:** (a) offline chekda "avval ishlatilgan kod" tekshiruvi; (b) offline qaytarish va VM 833 84-band ma'lumoti; (c) ichki ko'chirishni xabar qilish majburiyati yo'qligini tasdiqlash; (d) chakana sotuvchi uchun OFD'dan tashqari to'g'ridan-to'g'ri API talab qilinadimi.

## Tekshirilmaganlar
- Rossiya PP 1944 (21.11.2023) matni va "ЛМ ЧЗ" offline davri — ochilmadi (faqat analog, bloklamaydi).
- UP-100 (26.05.2026) — VM 830 mexanizmiga o'zgarishlari o'qilmadi.
- VM 665 (tamaki/alkogol) alohida ochilmadi (VM 833 3-/4-ilovalari orqali qamrab olingan).
- soliq.uz yangiliklari (WebSearch kvotasi tugagan); help.crpt-turon.uz — 403.
- Faktura.uz kabinet UI'sida xavf darajasi; tarif summalari.
- Sputnik.uz (04.01.2026) "yangi EHF xavf-baholash nizomi" xabari — ochilmadi.

## Manbalar (asosiy)
- lex.uz: [VM 830](https://lex.uz/docs/-7962143), [VM 825](https://lex.uz/docs/-7946843), [VM 249 3-ilova](https://lex.uz/docs/-5394977), [VM 168](https://lex.uz/docs/-7436697), [VM 673](https://lex.uz/docs/-6709063), [VM 489](https://lex.uz/docs/-4948595), [Soliq kodeksi](https://lex.uz/docs/-4674902), [VM 943](https://lex.uz/docs/4603329), [VM 23](https://lex.uz/docs/8012407), [VM 833](https://lex.uz/docs/5205248), [VM 631](https://lex.uz/docs/6266709), [VM 149](https://lex.uz/docs/5936145), [VM 322](https://lex.uz/docs/5429990), [PQ-190](https://lex.uz/docs/7540338)
- Vendor: [api.faktura.uz/help](https://api.faktura.uz/help/), [api-docs.didox.uz](https://api-docs.didox.uz/ru/home), [github.com/qo0p/e-imzo-doc](https://github.com/qo0p/e-imzo-doc), [yt.uz/ru/services/5](https://yt.uz/ru/services/5), [yt.uz/ru/services/7](https://yt.uz/ru/services/7), [e-imzo.soliq.uz](https://e-imzo.soliq.uz/), [vakolat.adliya.uz/search](https://vakolat.adliya.uz/search)
- Amaliyot: buxgalter.uz (text201304, text207624, text217132, text167963, text160843, text175937, text183087, ESF risk 10.06.2026), bss.uz (15648, 10902, 5568), legalise.uz e-TTN FAQ (10.03.2026), e-gazeta.norma.uz text217041
