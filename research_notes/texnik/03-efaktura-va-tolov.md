# E-faktura va to'lov tizimlari: texnik talablar

*Tadqiqotchi: Integrator · 2026-10-10*

## Asosiy xulosalar

1. **Didox va Faktura.uz'ning rasmiy ochiq API hujjati yo'q darajada yopiq.** Faktura.uz'ning ochiq API hujjati bor (`api.faktura.uz/help/`), Didox'niki esa login talab qiladigan portalda (`api-docs.didox.uz`) — ikkisi uchun ham faqat **norasmiy, uchinchi tomon** SDK/MCP server topildi, rasmiy SDK yo'q.
2. **To'g'ridan-to'g'ri davlat e-faktura API'si uchun ommaviy hujjat topilmadi.** Soliq qo'mitasining o'z ochiq API'si haqida ommaviy manbada hujjat topilmadi; integratsiya faqat akkreditatsiyalangan EDO operatorlari (Didox, Faktura.uz va boshqalar) orqali o'tadi.
3. **E-IMZO'ning rasmiy dasturchi portali yo'q** — yagona batafsil texnik hujjat jamoatchilik tomonidan yozilgan GitHub repo (`qo0p/e-imzo-doc`). Bu davlat kripto-middleware'iga bog'liqlik nuqtai nazaridan tadqiqot uchun muhim xavf.
4. **Fakturalarni AI bilan xavf bo'yicha baholash** 2025-12-22 pilot, 2026-01-01 dan to'liq ishga tushdi (PQ-830, 26.12.2025); yuqori xavfli fakturalar ulushi davr uchun ≤10% bilan cheklangan, QQS krediti to'lovdan keyin beriladi.
5. **Payme, Click, Uzum'ning uchtasi ham turlicha protokolda ishlaydi**: Payme — JSON obyekt sifatida yuboriladigan RPC-so'rov (`method`/`params`/`id` maydonlari bilan; rasmiy hujjatda aniq "JSON-RPC 2.0" deb atalmaydi, push model), Click — REST+MD5 imzo (Prepare/Complete), Uzum — aralash (OpenAPI + BaaS qismida JSON-RPC). Uchtasida ham Check/Create/Perform(Confirm)/Cancel uslubidagi metodlar bor.
6. **Click'ning komissiya stavkasi business.click.uz'da (1–5%, toifa bo'yicha) rasman tasdiqlangan.** co.click.uz'dagi "0%" da'vosi keltirilgan havola (co.click.uz/ru/xizmat-haqide/tarify) tekshirishda 404 qaytardi — ishlaydigan manba bilan tasdiqlanmaguncha bu da'vo hujjatdan olib tashlandi.
7. **Onlayn/QR to'lovda fiskal chekni kim chiqarishi aniq emas.** Soliq qo'mitasi amalda to'lov tizimi "komissioner" sifatida chekni o'zi chiqarishini talab qiladi, lekin huquqiy tahlil (PQ-943, PQ-5252, Soliq kodeksi 227-1-modda) buni majburiy deb emas, kelishiladigan deb talqin qiladi.
8. **Humo/Uzcard'da ochiq merchant SDK yo'q.** "UzPay"/"OPAKET" degan yagona birlashgan tizim **mavjud emas** (faqat terminal/ATM o'zaro ishlashi 2024-yil aprelda tugallangan). To'g'ridan-to'g'ri karta qabul qilish faqat litsenziyalangan acquiring bank (Kapitalbank, Ipak Yuli) yoki gateway (PaySys, Multicard) orqali.
9. **Ochiq banking (bank ko'chirmasi API'si) Oʻzbekistonda hali yoʻq** — rasmiy standart 2026-yil 1-sentyabrga rejalashtirilgan (PQ-359). Yagona haqiqiy ishlaydigan integratsiya: Kapitalbank DiBank → 1C/Didox'ga ko'chirma avtomatik tushishi.
10. AIOS uchun amaliy xulosa: barcha uch to'lov integratsiyasi (Payme/Click/Uzum) va ikki EDO operatori (Didox/Faktura.uz) bilan **alohida, moslashuvchan adapter qatlami** kerak — protokollar, imzolash va komissiya modeli har birida farq qiladi, yagona umumiy abstraktsiya yo'q.

---

## 1. E-faktura (Elektron hisob-faktura, EHF)

### 1.1 Huquqiy asos

- Majburiylik: Vazirlar Mahkamasi Qarori **№522 (2019-06-25)**, 2020-01-01 dan majburiy ([lex.uz/docs/-4386769](https://lex.uz/docs/-4386769?ONDATE=08.01.2021+00)).
- Dastlabki vaqtinchalik tartib: Qaror **№3136 (2019-02-05)** ([lex.uz/docs/-4190561](https://lex.uz/docs/-4190561)).
- Soliq kodeksi (2019-12-30): fakturalar elektron axborot tizimida tuzilishi, saqlanishi, hisobga olinishi shart; qog'oz shakli faqat texnik uzilish holatida ([lex.uz/acts/-4674902](https://lex.uz/acts/-4674902)).
- To'g'ridan-to'g'ri davlat API'si (my.soliq.uz / SoliqOnline): **ommaviy hujjat topilmadi**. Qidirildi: soliq.uz rasmiy sayti, my.soliq.uz — faqat akkreditatsiyalangan EDO operatorlari orqali integratsiya yo'li topildi, davlatning o'z ochiq dasturchi API'si haqida ommaviy hujjat ko'rinmadi (bu API'ning mutlaqo yo'qligini anglatmaydi, faqat ochiq qidiruvda topilmadi).

### 1.2 AI xavf bo'yicha baholash (risk-scoring)

- Huquqiy asos: Prezident Farmoni **PF-153 (2025-09-04)** — sarlavhasi asosan QQS'ni soddalashtirish haqida, lekin matbuot (gazeta.uz) uni EHF xavf baholash majburiyatining asosi deb ko'rsatadi, IMF Soliq qo'mitasi maslahatchisi Georgiy Kandelaki bilan ishlab chiqilgan ([lex.uz/uz/docs/-7716359](https://lex.uz/uz/docs/-7716359); [gazeta.uz, 2025-10-15](https://www.gazeta.uz/oz/2025/10/15/tax-vat/)).
- Amalga oshirish qarori: Vazirlar Mahkamasi Qarori **№830 (2025-12-26)**, 6-modda (xavf mezonlari — soliq to'lovchi tarixi, moliyaviy holati, biznes toifasi, tranzaksiya naqshi asosida Soliq qo'mitasi belgilaydi) va 8-modda (EHF'ni past/yuqori xavf toifasiga ajratish) ([lex.uz/docs/-7962143](https://lex.uz/docs/-7962143)).
- Pilot: **2025-12-22** dan test rejimi (shaxsiy kabinetda qizil/yashil belgi); to'liq majburiy: **2026-01-01** ([spot.uz, 2025-12-22](https://www.spot.uz/oz/2025/12/22/risk-analysis)).
- Cheklov: yuqori xavfli fakturalar hisobot davri uchun soliq to'lovchining jami fakturalarining ≤10%ini tashkil qilishi mumkin; qizil fakturadagi QQS faqat sotuvchi/xaridor to'lagandan keyin kreditlanadi ([spot.uz, 2026-01-05](https://www.spot.uz/oz/2026/01/05/risk-assessment); [spot.uz, 2025-10-16](https://www.spot.uz/oz/2025/10/16/electronic-invoices)).
- Metodologiya: matbuotda "48 mezon" va "71 davlat idorasi" ma'lumotlari takrorlanadi ([gazeta.uz, 2025-10-15](https://www.gazeta.uz/oz/2025/10/15/tax-vat/)). **Qaror №830'ning lex.uz'dagi asl matni qayta tekshirildi — bu ikki raqam (48, 71) o'sha matnda yo'q.** 6-modda xavf mezonlari omillarini (soliq to'lovchi tarixi, moliyaviy holat, biznes toifasi) sonsiz, umumiy shaklda sanab o'tadi. Shuning uchun "48 mezon / 71 idora" **faqat OAV (ommaviy axborot vositalari) manbasi** sifatida belgilanadi, qonun matnida tasdiqlanmagan.
- Pilot natijalari (2025-yil iyul–sentabr): 27 soliq to'lovchi nomuvofiq operatsiyalarda aniqlangan; 281 kompaniya 5,9 trln so'mlik shubhali faktura ro'yxatdan o'tkazgan; 706 mlrd so'mlik potensial soxta QQS da'vosi ([gazeta.uz, 2025-10-15](https://www.gazeta.uz/oz/2025/10/15/tax-vat/)).

### 1.3 Didox

- Rasmiy sayt: didox.uz. API hujjat portali mavjud: **api-docs.didox.uz**, lekin login talab qiladi — to'liq endpoint ro'yxatini ochiq holda olib bo'lmadi ([api-docs.didox.uz/login](https://api-docs.didox.uz/login)).
- "1C kabi buxgalteriya dasturlari bilan integratsiya uchun tayyor modul/API" borligi haqida ikkinchi darajali yozuvlar bor, rasmiy texnik tafsilotsiz ([internet-zapis.ru](https://internet-zapis.ru/info/didox-uz-v-uzbekistane-revolyutsiya-elektronnogo-dokumentooborota-i-rabota-s-esf); [spravke.livejournal.com](https://spravke.livejournal.com/691773.html)).
- TypeScript/Node.js SDK npm'da `didox` nomi bilan bor, lekin bu **norasmiy, jamoatchilik tomonidan yozilgan** SDK (muallif Ahrorbek Mirzaev, repo `mirzaevoff/didox`, sayt `didox.mirzaev.uz`) — Didox kompaniyasining rasmiy mahsuloti emas ([registry.npmjs.org/didox](https://registry.npmjs.org/didox); [socket.dev/npm/package/didox](https://socket.dev/npm/package/didox)).
- Hujjat turlari (ochiq manbalarda tasdiqlangan): hisob-faktura, ishonchnoma (e-doverennost), bajarilgan ishlar dalolatnomasi, TTN (tovar-transport xati), shartnomalar, Rossiya kontragentlari bilan skan hujjat almashinuvi ([buxgalter.uz](https://buxgalter.uz/publish/doc/text159643_elektronnye_doverennosti_didox_pozvolyayut_identificirovat_podpisavshih); [internet-zapis.ru](https://internet-zapis.ru/info/didox-uz-v-uzbekistane-revolyutsiya-elektronnogo-dokumentooborota-i-rabota-s-esf)). Birlashtirilgan e-TTN (faktura+yo'l xati) Didox'da alohida qo'llab-quvvatlanishi **ochiq manbada topilmadi**.
- Narx: 10 tagacha hujjat bepul; 11–100 va 101–1000 oralig'ida bosqichli narx (~800 so'm/hujjat atrofida, manbalar bir-biriga mos kelmaydi); ba'zi manbalar oyiga 1000 fakturagacha bepul, undan yuqorida ~300 so'm/hujjat (support bilan) deydi ([buxgalter.uz taqqoslash jadvali](https://buxgalter.uz/publish/doc/text171838_kak_opredelitsya_s_operatorom_esf_sravnitelnaya_tablica)). Ichki to'lov birligi "DICOIN" deb ataladi ([t.me/didox_info](https://t.me/s/didox_info?before=775)). Rasmiy integratsiya shartnomasi hujjati ochiq holda topilmadi.
- Sinov (sandbox) muhiti Didox API uchun alohida **ochiq manbada topilmadi** (E-IMZO'ning o'z sandbox'i bor, lekin Didox'ning alohidasi yo'q).
- Integratsiya uchun kontakt (qidiruv natijasidan, asl manba mustaqil tasdiqlanmadi): didox@venkon.uz, info@venkon.uz, +998 97 737 04 23.

### 1.4 Faktura.uz

- Rasmiy API hujjati **to'g'ridan-to'g'ri topildi va o'qildi**: [api.faktura.uz/help/](https://api.faktura.uz/help/) (ruscha), [api.faktura.uz/help/en.html](https://api.faktura.uz/help/en.html) (inglizcha).
- Autentifikatsiya: token asosida. `POST account.faktura.uz/token` (username/password/client_id/client_secret) → qaytgan Bearer token `Authorization: Bearer [access_token]` header sifatida ishlatiladi (manba: yuqoridagi hujjat).
- Baza URL: `https://Api.Faktura.uz`. Asosiy endpointlar: `GET /Api/Document/GetDocumentTypes`, `GET /Api/Document/GetDocumentStatuses`, `GET /Api/CheckCompanyExist/:inn`, `GET /Api/DownloadArchive/:uniqueId`, `POST /Api/VerifySignature`, `POST /Api/Document/SendDocument`, `POST /Api/Document/ImportDocumentRegister`, `/Api/Document/GetDocumentHashcodes`, `/Api/Document/SignDocument`, `/Api/Document/GetDocumentStatus`, `/Api/Document/DeleteDocuments`, `/Api/Document/CreateDocumentReferenceGroup` (bir xil manba).
- Format: JSON va XML ikkisi ham qo'llab-quvvatlanadi.
- Hujjat turlari (API hujjatidan): Shartnoma (Договор), Faktura/Invoice, Taklif (Оферта), Tranzaksiya hisoboti, Akt va faktura, Oldindan to'lov hisobvarag'i, Material hisoboti, Jarima akti, Ishonchnoma, To'lov topshiriqnomasi. TTN/e-TTN aniq shu nom bilan ro'yxatda **topilmadi** — "Akt va faktura" qisman mos kelishi mumkin, lekin tasdiqlanmagan.
- Sandbox/narx/rasmiy shartnoma shartlari: ochiq (login talab qilmaydigan) sahifalarda **topilmadi**.
- **MCP server tasdiqlandi** (dastlabki taxmin to'g'ri chiqdi): `theYahia/factura-uz-mcp` GitHub'da ([github.com/theYahia/factura-uz-mcp](https://github.com/theYahia/factura-uz-mcp) — tadqiqot vaqtida to'g'ridan-to'g'ri so'rov 404 qaytardi, repo xususiy/o'chirilgan/qayta nomlangan bo'lishi mumkin; MCP kataloglarida hali ko'rinadi: [mcpmarket.com/server/factura-uz](https://mcpmarket.com/server/factura-uz), [lobehub.com/mcp/theyahia-factura-uz-mcp](https://lobehub.com/mcp/theyahia-factura-uz-mcp)). Katalog yozuvlariga ko'ra: 8 vosita (`create_invoice`, `sign_invoice`, `get_invoice`, `list_invoices`, `accept_invoice`, `reject_invoice`, `get_company_by_inn`, `list_products`); `FACTURA_CLIENT_ID`/`FACTURA_CLIENT_SECRET` (OAuth2) talab qiladi; MIT litsenziya. Bu **norasmiy, uchinchi tomon** wrapper, Faktura.uz'ning o'zi chiqarmagan.

### 1.5 E-IMZO / ERI (raqamli imzo)

- Rasmiy sayt: [e-imzo.uz](https://e-imzo.uz/) (qidiruv natijasiga ko'ra Soliq qo'mitasining yangi texnologiyalar ilmiy-tadqiqot markazi tomonidan ishlab chiqilgan — asl manba mustaqil tasdiqlanmadi).
- Rasmiy dasturchi portali (OpenAPI/Swagger) **topilmadi** — yagona batafsil texnik hujjat jamoatchilik tomonidan yozilgan: [github.com/qo0p/e-imzo-doc](https://github.com/qo0p/e-imzo-doc/blob/master/README.md) (ko'zgu: [deepwiki.com/qo0p/e-imzo-doc](https://deepwiki.com/qo0p/e-imzo-doc)).
- Arxitektura (shu hujjatdan):
  - **E-IMZO.exe** — lokal desktop dastur, xususiy kalitlarni saqlaydi, hech qachon tashqariga yubormaydi; brauzer bilan WebSocket orqali "CAPIWS" interfeysi orqali gaplashadi (eski NPAPI emas).
  - **E-IMZO-SERVER** — Java backend (JAR, JRE 1.8+), REST API beradi, sertifikat holatini tekshirish (OCSP) va vaqt belgisi (TSA) uchun `vpn.e-imzo.uz:3443` (prod) bilan bog'lanadi.
  - **Mobil komponent** (ID-CARD E-IMZO MOBILE) — Android ilova va jisman ID-karta orqali NFC asosida imzolash.
- Kalit/sertifikat formatlari: **PFX** fayllar (parol bilan himoyalangan), **ID-karta** (OZDST 1092:2009 kripto smart-karta, ichiga o'rnatilgan Java applet), **BAIK token** (USB kripto token), **PKCS#7** imzolangan konteynerlar (attached/detached).
- Hujjatlashtirilgan REST endpointlar: `/frontend/challenge`, `/frontend/timestamp/pkcs7`, `/frontend/timestamp/data`, `/frontend/pkcs7/make-attached`, `/frontend/pkcs7/join`, `/frontend/mobile/auth`, `/frontend/mobile/sign`, `/frontend/mobile/status`, `/frontend/mobile/upload`, `/backend/auth`, `/backend/pkcs7/verify/attached`, `/backend/pkcs7/verify/detached`, `/backend/mobile/authenticate/{DocumentID}`, `/backend/mobile/verify`, `/ping`, `/info`.
- Imzolash oqimi: brauzer `/frontend/challenge`'dan so'rov oladi → foydalanuvchi kalitni tanlaydi (PFX/ID-karta/BAIK) → E-IMZO.exe parolni so'raydi va lokal imzolaydi → PKCS#7 brauzerga qaytadi → backend `/backend/auth` yoki `/backend/pkcs7/verify/*`ga yuboriladi; vaqt belgisi `/frontend/timestamp/pkcs7` orqali qo'shiladi va `vpn.e-imzo.uz` TSA/OCSP'ga qarshi tekshiriladi.
- **Sandbox tasdiqlandi**: `testvpn.e-imzo.uz:2443` (prod'dan alohida VPN kalit/truststore); test sertifikatlari **TestCA** tomonidan beriladi; demo saytlar `https://test.e-imzo.uz/demo/`, `https://test.e-imzo.uz/demo/eimzoidcard/`, `https://test.e-imzo.uz/registrator/public/ckc.html`; jismoniy uskunasiz test uchun ID-karta emulyatori `wss://test.e-imzo.uz/idcard-emulator`.
- Boshqa jamoatchilik kodlari (chuqur tekshirilmagan): [github.com/0605AbMu/e-imzo-client](https://github.com/0605AbMu/e-imzo-client), [github.com/alimovshohrukh/horcrux](https://github.com/alimovshohrukh/horcrux).

---

## 2. To'lov tizimlari (Payme, Click, Uzum)

### 2.1 Payme

- Protokol: rasmiy hujjat buni aniq "JSON-RPC 2.0" deb atamaydi — so'zma-so'z: "Barcha xabarlar merchant billingiga RPC-so'rov sifatida keladi. RPC-so'rov — `method`, `params`, `id` maydonlari bilan JSON obyekt" ([developer.help.paycom.uz/protokol-merchant-api/format-zaprosa/](https://developer.help.paycom.uz/protokol-merchant-api/format-zaprosa/)). Amalda bu JSON-RPC uslubidagi protokol, lekin rasmiy hujjat versiya raqamini (2.0) ko'rsatmaydi.
- Yo'nalish: Payme Business merchant dasturiga so'rov yuboradi (push model) — merchant o'z qabul qiluvchi endpoint'ini amalga oshirishi kerak ([developer.help.paycom.uz/nastroyka-vzaimodeystviya/](https://developer.help.paycom.uz/nastroyka-vzaimodeystviya/)).
- Autentifikatsiya: HTTP Basic Auth (masalan, `Authorization: Basic ...`, login/parol = kassa Merchant ID + kalit) ([developer.help.paycom.uz/protokol-merchant-api/format-zaprosa/](https://developer.help.paycom.uz/protokol-merchant-api/format-zaprosa/)).
- Asosiy Merchant API metodlari: `CheckPerformTransaction`, `CreateTransaction`, `PerformTransaction`, `CancelTransaction`, `CheckTransaction`, `GetStatement`, `SetFiscalData` ([developer.help.paycom.uz/metody-merchant-api/](https://developer.help.paycom.uz/metody-merchant-api/)).
- Subscribe API alohida protokol sifatida sanab o'tilgan (takroriy/karta bog'lash uchun), lekin uning to'liq metod ro'yxati bu tadqiqotda **topilmadi** — alohida chuqur tekshirish kerak.
- QR to'lov: Payme ilovasi orqali do'konda skanerlash qo'llab-quvvatlanadi ("Joylarda to'lash") ([help.payme.uz/uz/oplata-na-mestakh/oplata-po-qr-kodu/](https://help.payme.uz/uz/oplata-na-mestakh/oplata-po-qr-kodu/)). Statik yoki dinamik QR ekanligi rasmiy sahifada **aniq ko'rsatilmagan** — faqat ikkinchi darajali manbalarda taxmin qilingan, tasdiqlanmagan deb belgilanadi.
- Sandbox: **mavjud**, `https://test.paycom.uz`. TEST_KEY bilan kassa yaratiladi, Endpoint URL sozlanadi, ikki test ssenariysi (tasdiqlanmagan/tasdiqlangan tranzaksiya) o'tkaziladi ([developer.help.paycom.uz/pesochnitsa/](https://developer.help.paycom.uz/pesochnitsa/)).
- Merchant bo'lish talablari (business.payme.uz): rahbar pasporti, "Guvohnoma" (ro'yxatdan o'tish guvohnomasi), QQS to'lovchi sertifikati (agar bor bo'lsa); to'liq onlayn shartnoma uchun ERI kerak; to'lovlar tashkilotning rasmiy hisob raqamiga tushishi shart; ePOS terminal kassa faollashtirish uchun talab qilinadi ([business.payme.uz](https://business.payme.uz/)).
- Komissiya (merchant, business.payme.uz manbasi): billing bilan e-commerce (bot/do'kon) — 2,0%; billingsiz elektron to'lov — 1,5%; Payme GO — 1%; joyida QR/ilova to'lovi — 1% ([business.payme.uz](https://business.payme.uz/)). **Eslatma**: help.payme.uz/chavo/komissii/ sahifasi faqat iste'molchi uchun karta-kartaga o'tkazma komissiyasini (1,1%) ko'rsatadi — merchant stavkasi emas, shuning uchun ikkisi aralashtirilmasin.

### 2.2 Click

- Protokol: **REST + MD5 imzo** (JSON-RPC emas). Ikki bosqichli "Prepare" (action=0) / "Complete" (action=1) callback oqimi ("Shop API"); alohida chiquvchi "Click-API"/Merchant API hisob-faktura yaratish uchun (`/invoice/create`, `/invoice/check`) ([docs.click.uz/en/merchant-api-request/](https://docs.click.uz/en/merchant-api-request/), [docs.click.uz/en/click-api-request/](https://docs.click.uz/en/click-api-request/)).
- Imzolash: `sign_string` = MD5(`click_trans_id + service_id + secret_key + merchant_trans_id + amount + action + sign_time` ketma-ketligi); merchant `merchant_id`, `service_id`, `merchant_user_id`, `secret_key` orqali aniqlanadi (manba: jamoatchilik namunasi, [gist.github.com/uzbekdev1](https://gist.github.com/uzbekdev1/c46761106460e85eb6ade443f656e1cb); [github.com/click-llc/click-integration-php](https://github.com/click-llc/click-integration-php)).
- Transport: HTTPS + to'g'ri SSL majburiy; HTTP qo'llab-quvvatlanmaydi.
- To'lov interfeyslari: Click SuperApp, my.click.uz veb-portal, USSD, Telegram bot.
- QR to'lov: "QR-code & Click Pass" tarif qatlami mavjud (business.click.uz/ru); statik yoki dinamik QR ekanligi **ochiq manbada topilmadi**.
- Sandbox: jamoatchilik vositalarida ("Click test tool") eslatiladi, lekin **rasmiy sandbox hujjat sahifasi topilmadi** — tasdiqlanmagan.
- Merchant ro'yxatdan o'tish: merchant.click.uz'da (~5 daqiqa), INN va biznes hujjatlari kiritiladi; tasdiqdan keyin Merchant Id, Service Id, Secret Key, Merchant User Id beriladi (ikkinchi darajali manba, sahifa to'g'ridan-to'g'ri o'qilmadi).
- **Komissiya**: [business.click.uz/ru](https://business.click.uz/ru) — QR/Click Pass joyida: Uzcard/Humo 1%, Visa 2%; veb-sayt integratsiyasi: Uzcard/Humo 1,5–2,5%, Visa 2,5%; chakana tovar billingi: 2%; o'z-o'ziga xizmat avtomoyka: 5% flat; obuna to'lovi yo'q. Bu — tadqiqotda tasdiqlangan yagona rasmiy stavka manbasi. (Oldingi loyihada keltirilgan `co.click.uz/ru/xizmat-haqide/tarify` sahifasidagi "0%" da'vosi qayta tekshirishda **HTTP 404 qaytardi** — havola ishlamaydi, shuning uchun bu da'vo hujjatdan olib tashlandi; faqat business.click.uz'dagi 1–5% stavkalari qoldirildi.)
- Click Up — merchant tomonidagi POS ilova (Click to'lovlarini skanerlash/qabul qilish uchun), ko'rsatma PDF: [click.uz/click/click_up.pdf](https://click.uz/click/click_up.pdf) — chuqur ko'rib chiqilmadi.

### 2.3 Uzum (Uzum Bank / Uzum Pay)

- Dasturchi portali: [developer.uzumbank.uz/en/](https://developer.uzumbank.uz/en/) — onlayn to'lovlar, QR to'lovlar, ichki/xalqaro o'tkazmalar, "Nasiya" (bo'lib to'lash), fiskalizatsiya, "Checkout", "Merchant API", "FastPay", "Dynamic QR", "CrossBorder", "RemitCore", "BaaS (Payment Hub)" qamraydi.
- Protokol: aralash — sahifada bir nechta integratsiya uchun "OpenAPI", BaaS Payment Hub mahsuloti uchun aniq "JSON-RPC" tilga olinadi. Asosiy Merchant API'ning aniq protokoli (JSON-RPC/REST) **to'liq tasdiqlanmagan**, faqat metod nomlari ma'lum.
- Autentifikatsiya: HTTP Basic авторизация; summalar tiyinda ifodalanadi. Kredensiallar: `UZUM_USERNAME`, `UZUM_PASSWORD`, `UZUM_SERVICE_ID` (ikkinchi darajali manbadan, to'g'ridan-to'g'ri qayta tasdiqlanmagan).
- Asosiy metodlar: check, create, confirm, reverse, status (Payme'ning Check/Create/Perform/Cancel naqshiga o'xshash) — [developer.uzumbank.uz/en/](https://developer.uzumbank.uz/en/), tasdiqlovchi jamoatchilik paketi: [packagist.org/packages/inwebuz/uzumbank-merchant](https://packagist.org/packages/inwebuz/uzumbank-merchant).
- Webhook: mijoz Uzum Bank ilovasida to'lovni yakunlagach, Merchant API webhook orqali bildirishnoma yuboradi.
- QR to'lov: ikki alohida mahsulot — **"FastPay"** (kassir mijozning QR kodini skanerlaydi) va **"Dynamic QR"** (mijoz chekdan generatsiya qilingan QR'ni skanerlaydi, narx oldindan kodlangan, qaytarish qo'llab-quvvatlanadi). Bu Uzum'ning kamida bitta oqimda **dinamik QR** ishlatishini tasdiqlaydi.
- Fiskalizatsiya bo'limi: savdo/qaytarish hisobotlari, QR-to'lov ma'lumotlarini soliq tizimlariga yuborish, chek havolasi generatsiyasi uchun alohida API — bu Uzum'ning merchantlar uchun fiskalizatsiya-xizmat sifatida integratsiya taklif qilishini ko'rsatadi.
- Sandbox: bu tadqiqotda **topilmadi** — dasturchi portalining asosiy sahifasida ko'rinmadi, ichki sahifalarni chuqurroq tekshirish kerak.
- Merchant bo'lish talablari (merchants.uzumbank.uz): tashkilot rekvizitlari (INN, hisob raqami, bank MFO), davlat ro'yxatdan o'tish guvohnomasi, rahbarning pasporti (ro'yxatga olish joyi bilan), buyruq (YaTT bundan mustasno), logotip (JPG/PNG), mobil raqam. "Ulanish bepul; xizmat narxi tanlangan acquiring turiga bog'liq" ([merchants.uzumbank.uz/en/](https://merchants.uzumbank.uz/en/)).
- Komissiya: "Uzum to'lov" usuli — Uzum kartasi bilan to'lovda 0%, boshqa bank kartalarida 0,4% ([merchants.uzumbank.uz/en/](https://merchants.uzumbank.uz/en/)). FastPay/Dynamic QR/Checkout mahsulotlari uchun alohida stavkalar **topilmadi**.

### 2.4 Komissiya stavkalari — jamlangan jadval

| Tizim | Kanal | Stavka | Manba |
|---|---|---|---|
| Payme | Billing bilan e-commerce | 2,0% | [business.payme.uz](https://business.payme.uz/) |
| Payme | Billingsiz elektron to'lov | 1,5% | business.payme.uz |
| Payme | Payme GO | 1% | business.payme.uz |
| Payme | Joyida QR/ilova | 1% | business.payme.uz |
| Payme | (iste'molchi) karta-kartaga | 1,1% | [help.payme.uz/chavo/komissii](https://help.payme.uz/chavo/komissii/) |
| Click | QR/Click Pass, Uzcard/Humo | 1% | [business.click.uz/ru](https://business.click.uz/ru) |
| Click | QR/Click Pass, Visa | 2% | business.click.uz/ru |
| Click | Veb-sayt, Uzcard/Humo | 1,5–2,5% | business.click.uz/ru |
| Click | Chakana tovar billingi | 2% | business.click.uz/ru |
| Click | O'z-o'ziga xizmat avtomoyka | 5% | business.click.uz/ru |
| Uzum | Uzum to'lov, Uzum kartasi | 0% | [merchants.uzumbank.uz](https://merchants.uzumbank.uz/en/) |
| Uzum | Uzum to'lov, boshqa bank kartasi | 0,4% | merchants.uzumbank.uz |

### 2.5 Onlayn/QR to'lovda fiskal chek majburiyati — kim chiqaradi

- **Soliq qo'mitasi (ГНК) pozitsiyasi** (gazeta.uz, 2022-11): to'lov tizimi operatorlari (Payme, Click, Apelsin va boshqalar) onlayn kassalar va soliq axborot tizimlari bilan integratsiyalashishi shart; mijoz to'lov xizmati orqali to'laganda, **shu to'lov xizmati fiskal chekni o'zi chiqaradi**, merchantning INN'ini "komissioner" sifatida kiritadi, shunda summasi merchant aylanmasida to'g'ri ko'rinadi ([gazeta.uz, 2022-11-01](https://www.gazeta.uz/ru/2022/11/01/fiscalization-of-payments/)).
  - Vaqt jadvali: talab Soliq kodeksiga ko'ra 2022-yil martdan kuchga kirgan; dastlabki muddat 2022-yil iyul (bir necha bor uzaytirilgan); ijro chorasi 2022-yil 1-noyabr; mahsulot kodi (IKPU) xatolari uchun jazo 2023-yil 1-martgacha yo'q.
  - Jazo (ikkinchi darajali manbadan, Soliq kodeksining asl moddasi mustaqil tasdiqlanmagan): Soliq kodeksi 221-moddasiga ko'ra 5 000 000 so'm jarima.
- **Muqobil/nozikroq huquqiy talqin** (buxgalter.uz): qonun to'lov ilovasi har doim chekni chiqarishi shart emas — merchantga tanlov beradi: onlayn-KKM, virtual kassa, ОФД bilan to'g'ridan-to'g'ri integratsiya, yoki to'lov ilovasi orqali — aniq usul **to'lov tizimi va merchant o'rtasida kelishiladi**, bir xil qoida sifatida majburlanmaydi. Maqola ГНК'ning "to'lov ilovasi doim chekni chiqarishi kerak" talqinini ko'p elementli chek, kechiktirilgan/nasiya to'lovlar uchun amaliy muammolar yaratishi sababli tanqid qiladi ([buxgalter.uz](https://buxgalter.uz/publish/doc/text185470_kogda_platejnoe_prilojenie_doljno_vydat_fiskalnyy_chek)).
  - Keltirilgan huquqiy asoslar: **PQ-5252 (2021-10-04)** "Nazorat-kassa texnikasidan foydalanishni takomillashtirish bo'yicha qo'shimcha chora-tadbirlar to'g'risida"; **Vazirlar Mahkamasi Qarori №943 (2019-11-23)**, 1 va 1a-ilovalar (to'lov tashkilotlari va marketpleyslar orqali onlayn kassa/fiskal chek berish tartib-qoidalari); **Soliq kodeksi 227-1-modda** (iste'molchi tranzaksiyalari uchun fiskal chek talablari).
- **Umumiy xulosa**: ham merchantning o'z kassasi, ham to'lov provayderi qonuniy chekni chiqaruvchi bo'lishi mumkin, konfiguratsiyaga bog'liq — **yagona shartsiz qoida yo'q**. 2022-yil oxiridan amaldagi ustun model: to'lov provayderi "komissioner" sifatida merchant nomidan chekni chiqaradi (ГНК/gazeta.uz bo'yicha), lekin buxgalter.uz'ning huquqiy tahlili asosdagi qarorlar (№943, PQ-5252, 227-1-modda) merchant tomonidan kassa orqali chiqarishga ham joy qoldiradi deb bahslashadi. **AIOS'ning fiskalizatsiya modulini loyihalashdan oldin bu savolni ГНК (soliq.uz) yoki litsenziyalangan ОФД operatori bilan to'g'ridan-to'g'ri aniqlashtirish tavsiya etiladi** — bu sohada noaniqlik/amaliyot o'zgarib turadi.

---

## 3. Bonus: Humo/Uzcard POS integratsiyasi va bank-klient API

### 3.1 Humo/Uzcard POS terminal integratsiyasi

- **"UzPay"/"OPAKET" degan yagona birlashgan tizim mavjud emas** — bu taxmin tasdiqlanmadi. Haqiqatda sodir bo'lgan: Humo va Uzcard **alohida to'lov tizimlari** bo'lib qolmoqda; ATM/terminal **o'zaro ishlashi** (interoperability, birlashish emas) 2024-yil aprelda tugallangan ([yuz.uz, 2024](https://yuz.uz/en/news/v-uzbekistane-zavershilas-integratsiya-bankomatov-platejnx-sistem-uzcard-i-humo)).
- Qo'shimcha fakt: Humo 2025-yil yanvarda Paynet'ga $65M'ga sotilgan/xususiylashtirilgan ([gazeta.uz, 2025-01-14](https://www.gazeta.uz/en/2025/01/14/humo-paynet/)).
- Qidirilgan, lekin topilmagan so'rovlar: "UzPay Uzbekistan Humo Uzcard", "OPAKET uzbekistan", "Humo Uzcard unification 2023 2024 2025" — bu atamalar ostida rasmiy birlashgan brend/tashkilot haqida e'lon topilmadi.
- **Ochiq merchant SDK rasmiy tarmoq saytlarida topilmadi**: humocard.uz'da texnik hujjatlar bo'limi bor, lekin login talab qiladi ([humocard.uz/en/banks/normative-documents/technical/](https://humocard.uz/en/banks/normative-documents/technical/), kontakt: info@nmpc.uz); uzcard.uz'da ochiq dasturchi bo'limi yo'q, api.uzcard.uz esa hisobot/boshqaruv portali, merchant integratsiya SDK'si emas ([api.uzcard.uz/en/](https://api.uzcard.uz/en/)).
- **Ochiq hujjatlashtirilgan narsa — acquiring/gateway qatlami, xom tarmoq API emas**:
  - PaySys Gateway — Humo/Uzcard acquiring uchun yagona to'liq ochiq hujjatlangan uchinchi tomon API, Postman kolleksiyasi bilan, PCI DSS talab qiladi ([docs.paysys.uz/en/host-to-host/paysys-gateway/](https://docs.paysys.uz/en/host-to-host/paysys-gateway/)).
  - Multicard.uz gateway (jamoatchilik Ruby SDK): [github.com/pashgo/multicard-ruby](https://github.com/pashgo/multicard-ruby).
  - Uzum Bank merchant/omnikanal API (Humo, Uzcard, Visa, MC, QR): [merchants.uzumbank.uz/en/](https://merchants.uzumbank.uz/en/), [developer.uzumbank.uz/en/](https://developer.uzumbank.uz/en/).
  - Payme Merchant API Uzcard Online/Humo'ni aniq qo'llab-quvvatlaydi ([business.payme.uz/en](https://business.payme.uz/en)).
  - Acquiring banklar: Kapitalbank ("Kapital API"), Ipak Yuli Bank (20 000+ POS, SoftPOS) ([en.ipakyulibank.uz/legal](https://en.ipakyulibank.uz/legal)); Orient Finans, Aloqabank, Agrobank, APEXBANK nomlari topildi, lekin individual ochiq API hujjati topilmadi ([innosoft.uz/en/services/e-commerce](https://innosoft.uz/en/services/e-commerce)).
  - Terminal ishlab chiqaruvchilari: PAX A930 Humo'ni 2024-yil apreldan qabul qila boshladi ([api.uzcard.uz/en/news/...](https://api.uzcard.uz/en/news/uzcard_terminals_accepting_humo_bank_cards/)); Ingenico Humo'da 2021-yildan ishlaydi ([apta.uz/en/news/14](https://apta.uz/en/news/14)) — **ikkisi ham ochiq SDK chiqarmaydi**, integratsiya yopiq/bank orqali.
- **Xulosa**: Humo yoki Uzcard'ning o'zidan ochiq merchant SDK/API yo'q. To'g'ridan-to'g'ri qabul qilish faqat litsenziyalangan acquiring bank yoki PaySys/Multicard kabi gateway orqali mumkin.

### 3.2 Bank-klient API / ochiq banking

- CBU (cbu.uz) Ochiq ma'lumotlar portali mavjud, lekin faqat makro/monetar statistika (XML/CSV/JSON/XLSX) — **hisob/ko'chirma API'si yo'q** ([cbu.uz/en/services/open_data/portal/](https://cbu.uz/en/services/open_data/portal/)).
- **Rasmiy ochiq banking regulyatsiyasi hali mavjud emas — 2026-yil 1-sentyabrga rejalashtirilgan**, milliy fintech strategiyasi doirasida ([intellinews.com](https://www.intellinews.com/uzbekistan-advances-ambitious-plan-to-become-regional-fintech-hub-by-2030-452143/); Prezident Qarori **PQ-359, 2025-noyabr**, [uzdaily.uz](https://www.uzdaily.uz/en/uzbekistan-approves-fintech-development-strategy-through-2030/)).
- Kapitalbank "Kapital API" mavjud ([kapitalbank.uz/en/corporate/services/kapital-api/](https://www.kapitalbank.uz/en/corporate/services/kapital-api/)), lekin hujjatlari cheklangan/faqat murojaat orqali.
- **Kapitalbank DiBank** — bank ko'chirmalarini to'g'ridan-to'g'ri 1C:Buxgalteriya va Didox'ga yuboruvchi **tasdiqlangan ishlaydigan integratsiya**, bu tadqiqotda topilgan eng yaqin "bank-klient API" ([kapitalbank.uz matbuot xabari](https://www.kapitalbank.uz/en/press_center/news/news-for-accountants-bank-payments-directly-to-1c-and-didox/); [dibank.uz/Instruction/](https://dibank.uz/Instruction/)).
- TBC Bank O'zbekiston "CapitalBanker/CapitalConnect" API-asosidagi korporativ platformasi ~2025-yilda ishga tushdi, lekin texnik hujjatlari ochiq emas ([retailbankerinternational.com](https://www.retailbankerinternational.com/news/tbc-bank-goes-live-with-cbs-api-based-open-platform-in-uzbekistan/)).
- Ipak Yuli Bank, Hamkorbank, Agrobank: ochiq dasturchi/korporativ API hujjati **topilmadi**.
- Open Banking Tracker 61 ta O'zbek bankini sanaydi, lekin **0 tasida dasturchi portali, 0 tasida sandbox** borligini tasdiqlaydi ([openbankingtracker.com/providers/country/uz](https://www.openbankingtracker.com/providers/country/uz)).
- Plaid, Tink, TrueLayer, Salt Edge: hech birida O'zbek banki qo'llab-quvvatlanishi **topilmadi** ([plaid.com/docs/institutions/](https://plaid.com/docs/institutions/) tekshirildi; saltedge.com/tink.com/truelayer.com'da sayt-cheklangan qidiruv natija bermadi).
- **Xulosa**: rasmiy ochiq banking standarti 2026-yil sentyabrgacha yo'q; Kapitalbank DiBank — topilgan yagona haqiqiy ko'chirma→1C integratsiyasi.

### 3.3 Dasturchi jamiyati kodi (GitHub, habr.com, infostart.ru)

**Topilgan haqiqiy kod (barchasi gateway/aggregator orqali, Humo/Uzcard xom tarmog'i orqali emas):**
- [github.com/iamtime/uzpay](https://github.com/iamtime/uzpay) — PHP SDK: Payme, Click, Uzum, Paynet, Octo (Humo/Uzcard/Visa/MC'ni qamraydi).
- [github.com/pashgo/multicard-ruby](https://github.com/pashgo/multicard-ruby) — Multicard.uz gateway (Humo, Uzcard, 9 hamyon).
- [github.com/PayTechUz](https://github.com/PayTechUz) — Python/Go SDK'lar, Payme/Click/Uzum/Humo/Uzcard/Apelsin'ni birlashtiradi.
- [github.com/azamatnarzuloyev/uzbekistan-web-developer-resources](https://github.com/azamatnarzuloyev/uzbekistan-web-developer-resources) — O'zbek to'lov API'lari ro'yxati.
- [github.com/maximal/1c-client-bank-exchange-php](https://github.com/maximal/1c-client-bank-exchange-php) — umumiy (O'zbekistonga xos emas) 1C Client-Bank Exchange formatini tahlil qiluvchi parser; agar biror O'zbek banki shu formatda eksport qilsa, asos sifatida ishlatish mumkin.
- [github.com/Artuganov/WWmcp](https://github.com/Artuganov/WWmcp) — 1C:Korxona + Payme (O'zbekiston)'ni birlashtiruvchi MCP server.

**Topilmadi:**
- To'g'ridan-to'g'ri "Humo API"/"Uzcard API" SDK'lari uchun GitHub repo yo'q.
- habr.com'da O'zbek Humo/Uzcard/acquiring integratsiyasi haqida maqola topilmadi.
- infostart.ru'da O'zbekiston banki/1C integratsiyasi haqida maxsus post topilmadi.

**Umumiy xulosa**: Bugungi kunda to'g'ridan-to'g'ri ochiq Humo/Uzcard POS yoki ochiq-banking ko'chirma API'si yo'q. Har qanday haqiqiy integratsiya yo'li (a) litsenziyalangan acquiring bank/gateway (PaySys, Multicard, Kapitalbank DiBank) orqali, yoki (b) uchta aggregator (Payme/Click/Uzum) orqali o'tadi — ya'ni ERP+POS uchun oxir-oqibat ulardan biriga qarshi qurish, yoki CBU'ning ochiq banking freymvorki chiqishigacha (PQ-359 bo'yicha 2026-yil sentyabrga mo'ljallangan) bank bilan yopiq shartnoma tuzish kerak bo'ladi.

---

## Ochiq savollar

1. Didox API'ning to'liq endpoint ro'yxati va rasmiy narx/shartnoma shartlari — login talab qiladigan `api-docs.didox.uz` portaliga kirish huquqi kerak.
2. Payme Subscribe API'ning to'liq metod ro'yxati.
3. Payme va Click'da QR kod statik yoki dinamikligi — rasmiy sahifalarda aniq ko'rsatilmagan.
4. Click'ning rasmiy sandbox muhiti mavjudligi.
5. Uzum Merchant API'ning aniq protokoli (OpenAPI/REST yoki JSON-RPC) va sandbox muhiti.
6. Onlayn/QR to'lovda fiskal chek majburiyati — ГНК'ning amaldagi talabi va buxgalter.uz'ning huquqiy talqini orasidagi ziddiyatni ГНК/ОФД operatori bilan to'g'ridan-to'g'ri aniqlashtirish kerak.
7. AI xavf-baholash tizimining "48 mezon" va "71 davlat idorasi" raqamlari — Qaror №830'ning lex.uz'dagi asl matnida tasdiqlanmadi (qayta tekshirildi, matnda yo'q); faqat jurnalistik manbada bor.
8. Kapitalbank "Kapital API" va TBC "CapitalBanker/CapitalConnect"ning texnik hujjatlariga kirish — murojaat qilish kerak.

## Manbalar

**E-faktura / E-IMZO:**
- [lex.uz/docs/-4386769](https://lex.uz/docs/-4386769?ONDATE=08.01.2021+00) — VM Qarori №522
- [lex.uz/docs/-4190561](https://lex.uz/docs/-4190561) — VM Qarori №3136
- [lex.uz/acts/-4674902](https://lex.uz/acts/-4674902) — Soliq kodeksi
- [lex.uz/uz/docs/-7716359](https://lex.uz/uz/docs/-7716359) — Prezident Farmoni PF-153
- [lex.uz/docs/-7962143](https://lex.uz/docs/-7962143) — VM Qarori №830
- [gazeta.uz/oz/2025/10/15/tax-vat/](https://www.gazeta.uz/oz/2025/10/15/tax-vat/)
- [spot.uz/oz/2025/12/22/risk-analysis](https://www.spot.uz/oz/2025/12/22/risk-analysis), [spot.uz/oz/2026/01/05/risk-assessment](https://www.spot.uz/oz/2026/01/05/risk-assessment), [spot.uz/oz/2025/10/16/electronic-invoices](https://www.spot.uz/oz/2025/10/16/electronic-invoices)
- [api-docs.didox.uz](https://api-docs.didox.uz/login), [registry.npmjs.org/didox](https://registry.npmjs.org/didox), [socket.dev/npm/package/didox](https://socket.dev/npm/package/didox)
- [buxgalter.uz/.../text171838](https://buxgalter.uz/publish/doc/text171838_kak_opredelitsya_s_operatorom_esf_sravnitelnaya_tablica), [buxgalter.uz/.../text159643](https://buxgalter.uz/publish/doc/text159643_elektronnye_doverennosti_didox_pozvolyayut_identificirovat_podpisavshih)
- [api.faktura.uz/help/en.html](https://api.faktura.uz/help/en.html)
- [github.com/theYahia/factura-uz-mcp](https://github.com/theYahia/factura-uz-mcp)
- [github.com/qo0p/e-imzo-doc](https://github.com/qo0p/e-imzo-doc)

**To'lov tizimlari:**
- [developer.help.paycom.uz](https://developer.help.paycom.uz/) (Merchant API, sandbox), [business.payme.uz](https://business.payme.uz/), [help.payme.uz/chavo/komissii](https://help.payme.uz/chavo/komissii/)
- [docs.click.uz/en/merchant-api-request/](https://docs.click.uz/en/merchant-api-request/), [docs.click.uz/en/click-api-request/](https://docs.click.uz/en/click-api-request/), [business.click.uz/ru](https://business.click.uz/ru) (co.click.uz/ru/xizmat-haqide/tarify — tekshirildi, 404, komissiya manbasi sifatida ishlatilmadi)
- [developer.uzumbank.uz/en/](https://developer.uzumbank.uz/en/), [merchants.uzumbank.uz/en/](https://merchants.uzumbank.uz/en/)
- [gazeta.uz/ru/2022/11/01/fiscalization-of-payments/](https://www.gazeta.uz/ru/2022/11/01/fiscalization-of-payments/), [buxgalter.uz/.../text185470](https://buxgalter.uz/publish/doc/text185470_kogda_platejnoe_prilojenie_doljno_vydat_fiskalnyy_chek)

**Humo/Uzcard/bank API:**
- [yuz.uz/en/news/...](https://yuz.uz/en/news/v-uzbekistane-zavershilas-integratsiya-bankomatov-platejnx-sistem-uzcard-i-humo), [gazeta.uz/en/2025/01/14/humo-paynet/](https://www.gazeta.uz/en/2025/01/14/humo-paynet/)
- [humocard.uz/en/banks/normative-documents/technical/](https://humocard.uz/en/banks/normative-documents/technical/), [api.uzcard.uz/en/](https://api.uzcard.uz/en/)
- [docs.paysys.uz/en/host-to-host/paysys-gateway/](https://docs.paysys.uz/en/host-to-host/paysys-gateway/), [github.com/pashgo/multicard-ruby](https://github.com/pashgo/multicard-ruby)
- [cbu.uz/en/services/open_data/portal/](https://cbu.uz/en/services/open_data/portal/)
- [intellinews.com/...](https://www.intellinews.com/uzbekistan-advances-ambitious-plan-to-become-regional-fintech-hub-by-2030-452143/), [uzdaily.uz/...](https://www.uzdaily.uz/en/uzbekistan-approves-fintech-development-strategy-through-2030/)
- [kapitalbank.uz matbuot xabari](https://www.kapitalbank.uz/en/press_center/news/news-for-accountants-bank-payments-directly-to-1c-and-didox/), [dibank.uz/Instruction/](https://dibank.uz/Instruction/)
- [openbankingtracker.com/providers/country/uz](https://www.openbankingtracker.com/providers/country/uz)
- [github.com/iamtime/uzpay](https://github.com/iamtime/uzpay), [github.com/PayTechUz](https://github.com/PayTechUz), [github.com/Artuganov/WWmcp](https://github.com/Artuganov/WWmcp)
