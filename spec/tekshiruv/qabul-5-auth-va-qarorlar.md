# Qabul-5 — Autentifikatsiya (OAuth 2.0) va 2026-10-15 foydalanuvchi qarorlari

*Qabul agenti (Opus), 2026-10-15. Tekshirilgan: `git diff` (18 fayl, commit qilinmagan) + yangi `spec/02-arxitektura/12-autentifikatsiya-oauth2.md`. Mezon — foydalanuvchining 5 ta qarori: (1) o'z OAuth 2.0, mock yo'q, admin panel; (2) 24 soat imtiyozdan keyin butun tenant to'liq to'xtaydi, offline litsenziya; (3) AI-03 MVP'da, 4 ta AI funksiya; (4) markirovkalangan tovar offline — narx ma'lum bo'lsa ruxsat, noma'lum bo'lsa taqiq; (5) chekdan keyin e-faktura, QQS ikki marta emas.*

**Umumiy hukm: QISMAN QABUL.** Yo'nalish to'g'ri va qarorlarning ko'pchiligi izchil kiritilgan, lekin 5 ta KRITIK muammo bor (ulardan 2 tasi — qarorga bevosita zid eskirgan matn, 3 tasi — OAuth/lokaut dizaynidagi haqiqiy nuqson). KRITIK bandlar tuzatilmaguncha spec'ni commit qilish tavsiya etilmaydi.

Hisob: **KRITIK — 5, O'RTA — 13, KICHIK — 12.**

---

## KRITIK

### K1. `04-offline-sync.md` §7 — markirovka offline siyosati eskirgan (4-qarorga zid)
- **Joy**: `spec/02-arxitektura/04-offline-sync.md:227-236`
- **Muammo**: §7 diff'da umuman o'zgartirilmagan. Hamon eski siyosat yozilgan: "sotuvning o'zi bloklanmaydi … qaror kassirga qoldiriladi" va "qat'iy taqiq siyosati … taxmin". Unda "narx qurilmada noma'lum bo'lsa taqiq" sharti yo'q. 4-qarorga zid, ustiga-ustak 02/03-integratsiyalar/04-ekranlar bilan ham mos emas. Dasturchilar aynan shu hujjatdan ishlaydi.
- **Tuzatish** (§7 tanasini to'liq almashtirish):
  > ## 7. Markirovkalangan tovar — offline siyosati *(2026-10-15: foydalanuvchi qarori)*
  >
  > CRPT Turon'da kodni real vaqtda tekshirish offline holatda **mumkin emas**. Siyosat (`02-modullar-talablari.md` US-M01-03, `03-integratsiyalar.md` §4):
  > - **Narx qurilmada ma'lum** (tovar va uning amaldagi narxi Dexie `catalog`/`prices`da bor) — sotuvga **ruxsat**. DataMatrix kod skanerlanadi, faqat mahalliy format/nazorat raqami tekshiriladi, kod `sale.created` voqeasi payload'iga yoziladi, chekka "⚠ Offlayn sotildi, CRPT tekshiruvi kutilmoqda" belgisi qo'yiladi.
  > - **Narx qurilmada noma'lum** (tovar hali sinxronlanmagan) — sotuv **ruxsat etilmaydi**, POS "Offlaynda sotib bo'lmaydi, narx noma'lum" xabarini ko'rsatadi. Kassir qarorni chetlab o'ta olmaydi.
  > - Internet qaytganda worker `outbox_jobs(kind="marking_sell")` orqali CRPT'ga `verify_code` + `sell` yuboradi; `verify_failed` bo'lsa Egasi/Buxgalterga ogohlantirish beriladi (tovar allaqachon sotilgan — faqat qayd va tuzatish).
  > - Offline **qaytarish/ko'chirish** (M02/M06) siyosati — hali ochiq savol.
  > - Bu mahsulot qarori. Huquqshunos tasdig'i tavsiya etiladi, lekin spec darajasidagi qaror qabul qilingan.

### K2. `11-backlog.md` — AI-03 hamon "MVP'dan keyin" bo'limida (3-qarorga zid)
- **Joy**: `spec/02-arxitektura/11-backlog.md:82` (va 6-sprint, :73)
- **Muammo**: "MVP'dan keyin" ro'yxatining 2-bandi: "AI-03 (US-M04-04 (3)-yo'l) — qog'oz hujjat OCR…". Hech bir sprintda AI-03 yo'q. 05/06/07-ai-qatlami/README esa "4 ta AI funksiya MVP'da" deydi.
- **Tuzatish**:
  - `:82` eski → yangi: `2. Mijozlarga SMS/Telegram qarz xabarlari (US-M08-08). *(2026-10-15: AI-03 bu ro'yxatdan olib tashlandi — foydalanuvchi qarori, MVP'da, 6-sprint)*`
  - 6-sprintga, `:73`dan keyin qo'shish: `- **AI-03** (qog'oz hujjat OCR, pilot bilan, tor qamrov) — BO-04 kirim avto-to'ldirish, US-M04-04 (3)-yo'l, M02 qog'oz chek; `07-ai-qatlami.md` §10 OCR quvuri, majburiy inson tasdig'i va ishonch chegarasi. *(2026-10-15: foydalanuvchi qarori — AI-03 MVP'ga qaytarildi)*`

### K3. Lokaut offline cheklarni "qamab qo'yadi" — fiskal ma'lumot yo'qolishi (12 §8, §16.1 ichki ziddiyat)
- **Joy**: `12-autentifikatsiya-oauth2.md:184` (§8: "eski … cheklar baribir yuborilishi kerak"), `:275` (§16.1.1 istisnolar), `:277` (§16.1.3 barcha refresh token bekor); `04-offline-sync.md:126`, `:130`; `08-frontend-arxitekturasi.md` (403 interceptor)
- **Muammo**: Imtiyoz davrida (lokautgacha) offline yaratilgan cheklar OFD'ga faqat server orqali boradi (`outbox_jobs.ofd_send`, qaror #12). Lokaut paytida: (a) barcha refresh tokenlar bekor qilinadi, (b) `/sync/push` istisnolar ro'yxatida yo'q → `403 SUBSCRIPTION_RESTRICTED`, (c) login rad etiladi. Natijada qonuniy yaratilgan cheklar to'lov qilinguncha serverga yetmaydi va 48 soatlik fiskal muddat (VM 943) **bizning tizim sababli** buziladi. §8 o'zi "yuborilishi kerak" deydi, lekin mexanizm buni taqiqlaydi. Bundan tashqari, 08'dagi `/login?reason=subscription_expired` yo'naltirishi logout bilan aralashtirilsa, Dexie o'chiriladi (`04-offline-sync.md` §12 — logout Dexie'ni o'chiradi) va outbox yo'qoladi.
- **Tuzatish** — 12-hujjatga yangi §16.4 qo'shish (bu tor istisno; foydalanuvchi tasdig'i so'ralsin, chunki qarorda "faqat to'lov yo'li" deyilgan):
  > ### 16.4 Lokautdan oldingi offline cheklarni yuborish (drain)
  > Lokaut kassani to'xtatadi, lekin **lokautdan oldin qonuniy yaratilgan** cheklarni yo'qotmasligi kerak (fiskal 48 soat, VM 943). Shuning uchun:
  > 1. Lokautda qurilmaga bog'langan refresh tokenlar o'chirilmaydi — `revoked_reason='subscription'` bilan **`suspended`** holatiga o'tadi. Bunday token faqat `scope=sync.drain` bilan access token oladi.
  > 2. `sync.drain` tokeni bilan **faqat** `POST /sync/push` ishlaydi, u ham faqat `created_at <= grace_ends_at` bo'lgan voqealar uchun (qurilma `seq` va `license.jti` bo'yicha server tekshiradi, §8 clamp qo'llanadi). Undan keyingi voqealar `rejected: SUBSCRIPTION_RESTRICTED`. Boshqa hech qanday endpoint, UI yoki login ochilmaydi.
  > 3. Frontend `SUBSCRIPTION_RESTRICTED` holatini **logout deb hisoblamaydi**: Dexie/outbox o'chirilmaydi, login sahifasi ko'rsatiladi, fon rejimida drain davom etadi.
  > 4. To'lovdan keyin `suspended` tokenlar odatdagi holatga qaytadi (K3 va O2 bilan bog'liq).
  - `09-backend-arxitekturasi.md:222` (4)-qadam istisnolariga qo'shish: `, /sync/push (faqat sync.drain, 12 §16.4)`.
  - `04-offline-sync.md:130` oxiriga: `Lokautdan oldin yaratilgan, hali yuborilmagan voqealar `sync.drain` orqali yuboriladi (12 §16.4); `SUBSCRIPTION_RESTRICTED` logout emas — Dexie o'chirilmaydi.`

### K4. BFF va Android'da refresh rotatsiyasi poygasi — oddiy foydalanishda butun sessiya bekor bo'ladi
- **Joy**: `12-autentifikatsiya-oauth2.md:143-145` (§7), `:151-171` (§7.1), `:71` (§2.1, avtomatik refresh)
- **Muammo**: Qayta ishlatishni aniqlash qat'iy: `used_at`li token qaytib kelsa, butun oila bekor qilinadi. Ikki real holatda bu legitim foydalanuvchini uloqtiradi:
  - (a) BFF bitta `sid` uchun ikkita parallel so'rovni qayta ishlaydi (SPA odatda bir vaqtda 3–6 so'rov yuboradi), access token eskirgan, ikkalasi ham RT1 bilan refresh qiladi → ikkinchisi "reuse" → sessiya o'ladi.
  - (b) Android/veb-kassa beqaror tarmoqda: server RT1→RT2 ni aylantirdi, lekin javob yetib bormadi → qurilma RT1 ni qayta yuboradi → oila bekor → kassa login ekraniga tushadi. O'zbekiston mobil tarmog'ida bu tez-tez uchraydi.
- **Tuzatish** — §7 jadvaliga qator qo'shish:
  > | **Parallellik va tarmoq uzilishi** | (1) BFF bitta `sid` bo'yicha refresh'ni **single-flight** qiladi: Redis lock `refresh:{sid}`, boshqa so'rovlar natijani kutadi. (2) **Imtiyoz oynasi**: RT1 qayta kelsa va (`now - RT1.used_at`) ≤ 30 soniya (taxmin) hamda RT2 hali ishlatilmagan bo'lsa — oila bekor qilinmaydi, xuddi shu RT2 (yoki RT2 ni bekor qilib yangi RT3) qaytariladi (idempotent). Bu oynadan tashqarida yoki RT2 allaqachon ishlatilgan bo'lsa — butun oila bekor qilinadi (reuse detection). |
  - §21 test jadvaliga: `| Parallel refresh | Bitta sid uchun 5 ta parallel so'rov — sessiya saqlanadi; uzilgan javobdan keyin RT1 takrori (≤30 s) — oila bekor bo'lmaydi |`.

### K5. Telegram bot — Client Credentials orqali lokaut va bloklashni chetlab o'tish
- **Joy**: `12-autentifikatsiya-oauth2.md:43` (§2 `telegram-bot`), `:81`, `:451` (Ochiq savol 7)
- **Muammo**: Bot `bot.internal` xizmat tokeni bilan ishlaydi, tenant/foydalanuvchi esa token orqali emas, `telegram_links` orqali uzatiladi. Token'da `tenant_id`/`sid` yo'q, demak `require_subscription_ok` (Redis `sub_status:{tenant_id}`, token claim'idan) va `sid`-revoke tekshiruvi bot so'rovlariga qo'llanmaydi. Oqibat: `restricted` tenant Egasi botda AI-01 orqali hamon moliyaviy ma'lumot oladi va kunlik hisobot keladi — 2-qarordagi "butun tenant yopiladi" talabiga zid. Bloklangan xodim (US-M13-05) ham bot orqali ma'lumot olaveradi. Bundan tashqari, `bot.internal` tokeni istalgan `chat_id`/tenant nomidan ishlay oladi (confused deputy) — scope jadvalida (`:200-221`) `bot.internal` yo'q.
- **Tuzatish** — §2 `telegram-bot` qatoridan keyin yangi band:
  > **Bot so'rovlari uchun majburiy tekshiruvlar**: `bot.internal` tokeni faqat `/internal/bot/*` endpoint'lariga kiradi. Har so'rovda server `chat_id` → `telegram_links` (tenant_id, user_id) ni o'zi aniqlaydi va **foydalanuvchi so'rovi kabi** quyidagilarni tekshiradi: (1) `require_subscription_ok(tenant_id)` — `restricted` bo'lsa faqat obuna/to'lov eslatmasi yuboriladi, AI-01 va hisobotlar yopiq; (2) `memberships.status='active'` — bloklangan foydalanuvchiga javob berilmaydi, havola bekor qilinadi (05 §1.4); (3) `require_permission` (masalan AI-01 uchun `ai.ask`, hisobot uchun `reports.view`). `tenant_transaction(tenant_id)` RLS bilan ochiladi.
  - Scope jadvaliga qator: `| `bot.internal` | Telegram bot xizmati — faqat `/internal/bot/*`, foydalanuvchi huquqlari `telegram_links` orqali qayta tekshiriladi |`.

---

## O'RTA

### O1. Eksport istisnosi qarorga va product spec'ga zid
- **Joy**: `12-autentifikatsiya-oauth2.md:275` (`/reports/export` — "US-M17-03: eksport huquqi doim saqlanadi"), `:334` (§17.2.3 "ko'rish/eksport … ochiq qoladi"), `09-backend-arxitekturasi.md:222`, `04-offline-sync.md:130` ("ko'rish/eksport esa ochiq qoladi")
- **Muammo**: `02-modullar-talablari.md:641`, `:650` aniq: `restricted` holatda eksport ham mavjud emas. 2-qarorda "login rad etiladi, faqat to'lov yo'li ochiq". Arxitektura bu bilan zid.
- **Tuzatish**:
  - 12 `:275`: `**faqat** `/auth/*`, `/billing/*`, `/reports/export` (US-M17-03: eksport huquqi doim saqlanadi), `/.well-known/*` bundan mustasno` → `**faqat** `/auth/*` (login rad javobi, OTP/parol tiklash), to'lov havolasi yo'li (16.1.2) va `/.well-known/*` bundan mustasno; eksport `restricted` holatda **yopiq** (US-M17-03, US-M17-05 — 2026-10-15 qarori)`
  - 12 `:334`: `mavjud lokal ma'lumot (outbox, eksport) ko'rish/eksport qilish uchun ochiq qoladi (US-M17-05 bilan izchil)` → `barcha ekranlar yopiladi; sinxronlanmagan outbox o'chirilmaydi va internet qaytganda 16.4-bo'lim (drain) bo'yicha yuboriladi`
  - 09 `:222`: `(istisnolar: `/auth/*`, `/billing/*`, `/reports/export`)` → `(istisnolar: `/auth/*`, to'lov havolasi, `/sync/push` faqat `sync.drain` bilan — 12 §16.1, §16.4)`
  - 04 `:130`: `mavjud ma'lumotni ko'rish/eksport esa ochiq qoladi` → `ekranlar yopiladi, lekin sinxronlanmagan outbox saqlanadi va drain orqali yuboriladi (12 §16.4)`

### O2. To'lovdan keyin qurilma "darhol" qayta ishlay olmaydi — tokenlari bekor qilingan
- **Joy**: `12-autentifikatsiya-oauth2.md:335` (§17.2.4), `:279` (§16.1.5), `:277`
- **Muammo**: §16.1.3 lokautda barcha refresh tokenlarni bekor qiladi. §17.2.4 esa "qurilma keyingi onlayn bo'lishida yangi litsenziya oladi va darhol ishlaydi" deydi. Lekin `GET /auth/license` uchun haqiqiy token kerak. Kassir faqat PIN biladi, shuning uchun to'lovdan keyin har bir kassada kimdir parol bilan qayta login qilishi kerak bo'ladi.
- **Tuzatish**: K3'dagi `suspended` modeli qabul qilinsa, §17.2.4 → `To'lov qilinganda `suspended` qurilma refresh tokenlari tiklanadi; qurilma keyingi onlayn bo'lishida jim refresh qiladi, yangi litsenziya oladi va qayta ishlaydi (kassir PIN bilan davom etadi).` Agar foydalanuvchi "barcha tokenlar qat'iy bekor" variantini tanlasa: `To'lovdan keyin har bir qurilmada Egasi/Menejer qayta OAuth login qiladi (parol), shundan keyin yangi litsenziya olinadi.` — va shu jumla US-M17-03'ga ham yozilsin.

### O3. Offline soat orqaga surilsa litsenziya hech qachon tugamaydi
- **Joy**: `12-autentifikatsiya-oauth2.md:336` (§17.2.5)
- **Muammo**: §17.2.5 himoyani `04-offline-sync.md` §8 clamp'iga bog'laydi. Lekin clamp **serverda**, sinxronlash paytida ishlaydi. Offline qurilmada soatni orqaga surish `now <= valid_until` tekshiruvini cheksiz o'tkazib yuboradi, ya'ni lokautni aylanib o'tish mumkin.
- **Tuzatish** — §17.2.5 ni almashtirish:
  > 5. **Soatni orqaga surishdan himoya (qurilmada)**: qurilma litsenziya bilan birga serverdan `server_time` oladi va doimiy saqlaydi: `last_trusted_time = max(last_trusted_time, now)`. Har tekshiruvda `now < last_trusted_time − 10 daqiqa` (taxmin) bo'lsa — soat orqaga surilgan deb hisoblanadi, qurilma bloklanadi ("Qurilma soatini to'g'rilang va internetga ulaning"). Android'da qo'shimcha `SystemClock.elapsedRealtime()` + yuklanishlar soni. Server sinxronlashda §8 clamp'ini qo'llaydi. Veb'da bu himoya JS darajasida — qat'iy kafolat emas (O5).

### O4. Litsenziya muddati butun obuna davriga teng — o'g'irlangan yoki bekor qilingan qurilma bir oy offline ishlaydi
- **Joy**: `12-autentifikatsiya-oauth2.md:328`, `04-offline-sync.md:250` (qurilma bekor qilish)
- **Muammo**: `valid_until = grace_ends_at` oylik obunada ~30 kungacha bo'ladi. `devices.revoked_at` va xodim bloklanishi faqat online paytda kuchga kiradi, shuning uchun o'g'irlangan qurilma internetsiz bir oy sotuv qila oladi.
- **Tuzatish**: §17.1 ga qo'shish: `Xavfsizlik chegarasi: `valid_until = min(grace_ends_at, issued_at + 7 kun)` (taxmin). Obuna qarori o'zgarmaydi — server obuna faol bo'lsa har sync'da litsenziyani yangilaydi. Faqat uzoq vaqt (7 kundan ko'p) internetsiz qolgan yoki bekor qilingan qurilma o'zini qulflaydi. Fiskal 48 soat talabi bo'yicha qurilma baribir har 48 soatda online bo'lishi kerak.` (Foydalanuvchiga tasdiq uchun.)

### O5. Litsenziya tokeni access token bilan bir kalitda — almashtirib ishlatish xavfi, JWKS manbai aniqlanmagan
- **Joy**: `12-autentifikatsiya-oauth2.md:328`, `:333`, `:132`
- **Muammo**: (a) Litsenziya "6-bo'limdagi bir xil EdDSA kaliti, boshqa `typ`/`iss` bilan" imzolanadi. RS `typ`/`aud`ni qat'iy tekshirmasa, litsenziya JWT access token sifatida qabul qilinishi mumkin. (b) Eski kalit JWKS'da faqat ≈30 daqiqa qoladi, litsenziya esa haftalab yashaydi. Qurilmaning ochiq kalitni qayerdan va qanday yangilashi aniqlanmagan. (c) Claim'lar to'liq emas.
- **Tuzatish** — §17.1 ga:
  > Litsenziya **alohida kalit** bilan imzolanadi (`signing_keys.purpose='license'`, o'z `kid`i va rotatsiyasi). Header `typ: "license+jwt"`, claim'lar: `iss`, `aud: "urn:erp:device-license"`, `sub=device_id`, `tenant_id`, `iat`, `valid_until` (`exp` sifatida ham), `jti`, `server_time`. RS `typ != at+jwt` yoki `aud != urn:erp:api` bo'lgan har qanday tokenni rad etadi. Qurilma `/auth/license` javobida litsenziya kalitining JWKS'ini ham oladi va saqlaydi. Eski litsenziya kaliti eng uzoq `valid_until` tugaguncha JWKS'da qoladi. Veb-kassada mahalliy tekshiruv JS darajasida — qasddan o'zgartirilgan brauzerga qarshi kafolat emas (qaror shuni qabul qiladi).

### O6. BFF login oqimi noto'g'ri tasvirlangan — aslida ichki "parol grant"
- **Joy**: `12-autentifikatsiya-oauth2.md:45`, `:47-69` (§2.1), `:412`
- **Muammo**: Diagrammada brauzer `POST /auth/login {phone,password}`ni BFF'ga yuboradi, BFF esa `GET /oauth/authorize` chaqiradi. Parol GET'da qanday uzatilishi ko'rsatilmagan (query'da bo'lsa — loglarga tushadi). Front-channel redirect yo'q, shuning uchun PKCE bu yerda hech narsani himoya qilmaydi. Matndagi "bu ROPC emas" da'vosi asossiz. Login CSRF va sessiya fiksatsiyasi ham qayd etilmagan.
- **Tuzatish** — ikki variantdan birini aniq tanlash (tavsiya: a):
  > (a) **Haqiqiy Authorization Code**: SPA `GET /auth/login/start` → BFF `state`+PKCE yaratadi → brauzer `302` bilan AS'ning `/oauth/authorize` login sahifasiga (birinchi-tomon, xuddi shu domen) o'tadi → parol faqat AS sahifasiga POST qilinadi → AS `302 /auth/callback?code&state` → BFF kodni almashtiradi va `Set-Cookie` qiladi.
  > (b) Agar ichki (bitta jarayon) qisqa yo'l saqlansa: "bu — birinchi-tomon resource-owner autentifikatsiyasi, PKCE bu yo'lda qo'shimcha himoya bermaydi; parol faqat POST tanasida, hech qachon URL'da emas" deb halol yozilsin.
  > Ikkala holatda ham: login so'rovida `Origin`/`Sec-Fetch-Site` tekshiruvi (login-CSRF), muvaffaqiyatli login va tenant almashtirishda `sid` **yangilanadi** (session fixation), cookie nomi `__Host-sid` (Secure, Path=/, Domain yo'q).

### O7. Auth jadvallari uchun "standart tenant_id RLS" — texnik jihatdan noto'g'ri
- **Joy**: `12-autentifikatsiya-oauth2.md:398`, `01-malumotlar-modeli.md:28`
- **Muammo**: `user_credentials` (foydalanuvchi global, tenant'siz), `otp_challenges` (ro'yxatdan o'tishda tenant hali yo'q), `login_attempts` (phone/ip) — bu jadvallarda `tenant_id` umuman yo'q. `authorization_codes`/`refresh_tokens` esa tenant kontekstidan **oldin** `code_hash`/`token_hash` bo'yicha qidiriladi. "Standart tenant RLS" bu yerda ishlamaydi yoki AS'ni sindiradi.
- **Tuzatish** (01:28 va 12:398):
  > `user_credentials`, `otp_challenges`, `login_attempts`, `authorization_codes`, `refresh_tokens`, `sessions`, `signing_keys`, `oauth_clients` — **auth-sxema jadvallari**: alohida `auth` sxemasi, ilova roliga to'g'ridan-to'g'ri ruxsat yo'q, kirish faqat `SECURITY DEFINER` funksiyalar orqali (`auth_find_user`, `auth_consume_code(code_hash)`, `auth_rotate_refresh(token_hash)`, `auth_revoke_tenant(tenant_id)` …). `license_tokens` — standart `tenant_id` RLS. CI RLS testi (05 §3.3) bu ro'yxatni istisno sifatida tekshiradi.

### O8. Platforma admini — kredensial manbai yo'q, MFA yo'q, izolyatsiya zaif
- **Joy**: `12-autentifikatsiya-oauth2.md:41`, `:342-362`, `:120` (`aud`), `:452`; `01-malumotlar-modeli.md:38` (`platform_admins`: id, email, role)
- **Muammo**: `admin-bff` login "`platform_admins`ga qarshi" deyilgan, lekin u jadvalda parol yo'q (kredensiallar `users` → `user_credentials`da). Barcha tenantlarga RLS bypass huquqi bor rol bitta faktorli parol bilan himoyalangan. `aud` ikkala mijozda bir xil (`urn:erp:api`). `/admin/*` prefiksi tenant Egasi API'si (`/admin/users`) bilan bir xil.
- **Tuzatish** — 12 §18.1 boshiga:
  > **Izolyatsiya**: `platform_admins` (id, user_id → `users`, role, mfa_secret_encrypted, allowed_ips) — platforma admini oddiy `users` hisobiga bog'lanadi, lekin `admin-bff` login'da **majburiy ikkinchi faktor** (TOTP, taxmin; kelajakda WebAuthn) va ixtiyoriy IP allowlist talab qilinadi. Admin token'i `aud: "urn:erp:platform"`, `scope: platform.admin`, `tenant_id`siz. Tenant API'lari bunday tokenni rad etadi, va aksincha. Platforma endpoint'lari `/platform/*` prefiksida (tenant `/admin/users` bilan aralashmaydi). Access token muddati 5 daqiqa (taxmin), refresh — 8 soat mutlaq.
  - Jadvaldagi `GET /admin/tenants…` → `GET /platform/tenants…` (barcha 5 qator).

### O9. US-M13-08 (platforma admini Egasi hisobini boshqaradi) arxitekturada API'siz
- **Joy**: `12-autentifikatsiya-oauth2.md:352-360` vs `02-modullar-talablari.md:511-513`, `04-ekranlar-va-ux.md` ADM-01
- **Muammo**: Product spec'da Egasini bloklash/blokdan chiqarish, parolini tiklash, sessiyalarini ko'rish/bekor qilish bor. 12 §18.1 da faqat "barcha sessiyalarni tugatish" (tenant bo'yicha) bor.
- **Tuzatish** — §18.1 API jadvaliga:
  > | `POST /platform/tenants/{id}/owner/block`, `/unblock` | Egasi a'zoligini bloklash (sessiyalar bekor) — US-M13-08 |
  > | `POST /platform/tenants/{id}/owner/reset-password` | Egasiga SMS orqali tiklash havolasi/OTP (parol matni emas) |
  > | `GET /platform/tenants/{id}/owner/sessions`, `POST …/owner/sessions/{sid}/revoke` | Egasi sessiyalari |
  > Platforma admini oddiy xodimlarning (Kassir/Menejer/Buxgalter) ma'lumotiga kirmaydi.

### O10. US-M13-04/06 (SMS bilan vaqtinchalik parol/PIN) va 12 §4.2/§18.2 mos emas
- **Joy**: `02-modullar-talablari.md:496`, `:504-505`; `04-ekranlar-va-ux.md:69` (POS-01 "PIN/parolni unutdim — SMS OTP"); `12-autentifikatsiya-oauth2.md:93-98`, `:372`
- **Muammo**: Product spec Egasi tiklaganda "vaqtinchalik parol/PIN SMS orqali yuboriladi" deydi. 12-hujjatda OTP faqat `signup`/`recovery` uchun, Egasi uchun faqat `reset-pin` bor, u ham SMS'siz ("keyingi kirishda yangi PIN"). Egasi tomonidan parol tiklash endpoint'i yo'q. SMS'da parolni ochiq matnda yuborish — xavfsizlik anti-naqshi.
- **Tuzatish**:
  - 02:496 `unga birinchi kirish uchun vaqtinchalik parol/PIN SMS orqali yuboriladi` → `unga SMS orqali bir martalik taklif kodi (OTP, `purpose=invite`) yuboriladi; xodim shu kod bilan o'zi parol va/yoki PIN o'rnatadi`
  - 02:504 `yangi vaqtinchalik parol/PIN generatsiya qilinib xodimning telefoniga SMS orqali yuboriladi; xodim birinchi kirishda o'zgartirishi majburiy` → `eski parol/PIN bekor qilinadi, barcha sessiyalari tugatiladi va xodimga SMS orqali bir martalik tiklash kodi (`purpose=admin_reset`) yuboriladi; xodim kod bilan yangisini o'rnatadi (parol/PIN hech qachon SMS'da ochiq yuborilmaydi)`
  - 12 §4.2 ga band: `- **Taklif va Egasi tiklashi**: `purpose` qiymatlari `signup`/`recovery`/`invite`/`admin_reset`/`pin_reset`; kod bilan faqat parol yoki PIN o'rnatish mumkin, token berilmaydi.`
  - 12 §18.2 jadvaliga: `| **Parolni tiklash (Egasi)** | BO-11 | `POST /admin/users/{id}/reset-password` — kredensial bekor, sessiyalar revoke, `admin_reset` OTP yuboriladi |`
  - `otp_challenges.purpose` (12:393, 01:178) → `signup`/`recovery`/`invite`/`admin_reset`/`pin_reset`; `user_credentials`ga `must_change_password`, `must_change_pin` ustunlari qo'shilsin.

### O11. SMS OTP suiiste'moli (SMS pumping, enumeratsiya) yetarli cheklanmagan
- **Joy**: `12-autentifikatsiya-oauth2.md:98`, `:239`
- **Muammo**: Faqat "3 ta / telefon / 10 daqiqa" belgilangan. IP, global va kunlik limitlar yo'q, raqamlar turli bo'lsa toll-fraud (SMS pumping) ochiq qoladi. Javob telefon ro'yxatda bor-yo'qligini oshkor qilishi mumkin.
- **Tuzatish** — §12 jadvaliga qatorlar:
  > | OTP yuborish (qo'shimcha) | 10 / telefon / sutka; 20 / IP / soat; global sutkalik byudjet (alert bilan); faqat `+998` raqamlar | `429`, ortiqcha holatda CAPTCHA |
  > | Enumeratsiya | `recovery`/login javobi raqam mavjud-mavjud emasligidan qat'i nazar bir xil ("Agar raqam ro'yxatda bo'lsa, kod yuborildi") | — |

### O12. Offline PIN tekshiruvi server `pin_hash`ini qurilmaga tushiradi
- **Joy**: `12-autentifikatsiya-oauth2.md:105`
- **Muammo**: "PIN mahalliy keshlangan `users.pin_hash` (… `permissions` jadvali)". Bu yerda (a) eskirgan nom — endi `user_credentials.pin_hash`; (b) `04-offline-sync.md` §1 `permissions`da PIN yo'q; (c) server verifikatorini brauzer IndexedDB'ga ko'chirish uni oflayn brute-force'ga ochadi (4–6 raqam, 04 §9 o'zi tan oladi).
- **Tuzatish** → `PIN qurilma uchun alohida verifikator bilan solishtiriladi: `device_pin_verifiers(device_id, user_id, verifier, salt)` — server `argon2id(PIN, device_salt)` qiymatini faqat shu qurilmaga, `sync/pull scope=pin_verifiers` orqali beradi; server `user_credentials.pin_hash` hech qachon qurilmaga tushmaydi. Qurilma bekor qilinganda verifikatorlar bekor va PIN majburiy almashtiriladi (04 §9).`

### O13. Chekdan keyingi e-faktura — append-only registr bilan zid, `02-provodka` eslatmasiz, davlat tomonida ikki marta hisoblanish xavfi
- **Joy**: `02-modullar-talablari.md:50` (US-M01-06: "mavjud yozuvga hujjat havolasi qo'shiladi"); `03-biznes-jarayonlar.md` BP-13 (4/7-qadam); `02-arxitektura/02-provodka-qoidalari.md:293-295`; `01-malumotlar-modeli.md:101` (registrlar append-only)
- **Muammo**: (a) `vat_moves` — append-only registr, mavjud qatorga `einvoice_id` yozish (UPDATE) arxitektura qoidasini buzadi. (b) `02-provodka`da bu holat uchun qoida yo'q. Dasturchi 2.1 bo'yicha yangi `vat_moves(output)` yozib qo'yishi mumkin, ya'ni QQS ikki marta hisoblanadi. (c) Davlat QQS hisobotini chek (OFD) va e-faktura asosida o'zi tuzadi. Agar Soliq ularni bog'lamasa, BO-10 solishtirishida farq chiqadi.
- **Tuzatish**:
  - `02-provodka-qoidalari.md`ga yangi bo'lim:
    > ### 2.22 Chek asosida keyinroq chiquvchi e-faktura (`einvoice_from_receipt`) *(2026-10-15: foydalanuvchi qarori, US-M01-06, BP-13)*
    > Provodka **yo'q**: `ledger_entries` va `vat_moves`ga yangi qator yozilmaydi (daromad va chiquvchi QQS 2.1–2.4 bo'yicha chek paytida yozilgan). Bog'lanish faqat hujjat darajasida: `einvoices(direction=out, related_doc=receipt)`. `vat_moves` qatori o'zgartirilmaydi (append-only), "chek ↔ e-faktura" ko'rinishi `einvoices.related_doc` orqali JOIN bilan quriladi. Cheklov: bitta chekka bitta faol (`cancelled` bo'lmagan) chiquvchi e-faktura; e-faktura summasi chek summasidan (qaytarishlar ayirilgan holda) oshmaydi.
  - 02:50 `faqat mavjud yozuvga hujjat havolasi qo'shiladi` → `faqat `einvoices.related_doc` orqali chekka bog'lanadi (registr yozuvlari o'zgarmaydi, `02-provodka-qoidalari.md` 2.22)`; BP-13 4/7-qadamdagi "mavjud QQS yozuviga hujjat havolasi qo'shiladi" ham shunga moslansin.
  - BP-13 eslatmasiga: `BO-10 solishtirishida chekka bog'langan chiquvchi e-fakturalar alohida belgilanadi — davlat hisobotida ikki marta hisoblangan aylanma bo'lsa, farq sababi sifatida ko'rsatiladi. Soliq tizimi bunday e-fakturani chek bilan qanday bog'lashi (fiskal belgi rekviziti) — huquqiy/texnik tasdiq kerak (11-backlog 0-bosqich (d)).`

---

## KICHIK

1. **`spec/tekshiruv/00-qarorlar.md:22`** — #15 "**qaror 3/4ni almashtiradi**" noto'g'ri (#3 — veb-kassa sessiyasi, #4 — CSRF, obunaga aloqasi yo'q). Matndagi "shu matn keyingi tahrirda yangilanishi kerak (mahsulot jamoasi)" ham eskirgan (US-M17-03 allaqachon yangilangan), "#jadval" havolasi buzuq. Tuzatish: `Foydalanuvchi qarori, 2026-10-15 — **US-M17-03'dagi avvalgi taklifni almashtiradi**`; "shu matn keyingi tahrirda…" jumlasi → `US-M17-03 shunga ko'ra yangilangan`; `(#jadval, `04-offline-sync.md` §6)` → `(`04-offline-sync.md` §6)`. #14 ga qo'shish: `**#3ni yangilaydi**: veb-kassa ham OAuth/BFF, `devices` yozuviga ega (litsenziya uchun); CSRF (#4) o'zgarmaydi.` Yangi qatorlar (O'RTA ahamiyatda, chunki qarorlar reyestri to'liq emas):
   `| 16 | AI-03 | Foydalanuvchi qarori, 2026-10-15 | AI-03 (qog'oz OCR) MVP'da — 4 ta AI funksiya (AI-01/03/05/06); 2026-10-14'dagi "MVP'dan keyin" bekor |`
   `| 17 | Markirovka offline | Foydalanuvchi qarori, 2026-10-15 | Offline sotish — narx qurilmada ma'lum bo'lsa ruxsat, kod internet qaytganda CRPT Turon'ga; narx noma'lum — taqiq. Qaytarish/ko'chirish — ochiq |`
   `| 18 | Chekdan keyin e-faktura | Foydalanuvchi qarori, 2026-10-15 | Qo'llab-quvvatlanadi (US-M01-06, BP-13), `einvoices.related_doc`, QQS ikki marta hisoblanmaydi, provodka yo'q (02-provodka 2.22) |`
   Shuningdek `:16` va `:17` orasidagi bo'sh qator olib tashlansin (jadval ikkiga bo'linib qolgan).
2. **`11-backlog.md` 5-sprint (:61-67)** — US-M01-06/BP-13 rejalashtirilmagan. Qo'shish: `- Chek asosida chiquvchi e-faktura (US-M01-06, BP-13, BO-15 "Chek asosida e-faktura chiqarish"). *(2026-10-15)*`. 0-bosqich `:27` (c), (d) bandlariga: `— mahsulot qarori qabul qilingan (2026-10-15), huquqiy maslahat faqat tasdiq uchun`.
3. **`11-backlog.md:31`** — 1-sprint BO-11 ro'yxatida US-M13-04 (SMS taklif), US-M13-06 (parol tiklash) yo'q, 6-sprint ADM-01 qatorida (`:72`) US-M13-08 yo'q. Ikkalasiga ham hikoya ID'lari qo'shilsin.
4. **`11-backlog.md:33`** — "dev/staging'da `FakeSms`" va foydalanuvchining "mock yo'q" talabi. Aniqlashtirish: `FakeSms faqat lokal dev'da (aniq flag bilan); staging va prod — haqiqiy SMS provayder; auth testlari OTP'ni test-raqam yo'li orqali haqiqiy oqimda tekshiradi.` (Foydalanuvchi tasdig'i so'ralsin.)
5. **`04-offline-sync.md:126`** — "qayta kirish oynasi (parol yoki OTP)" 12 §4.2 ga zid (OTP kundalik login emas). `parol yoki OTP` → `parol (Egasi/Menejer); kassir keyin PIN bilan davom etadi`.
6. **`12-autentifikatsiya-oauth2.md:192`** (§9 tenant almashtirish) — `login_hint=tenant_id` login_hint semantikasini noto'g'ri ishlatadi. "Ikki tab'da parallel ikki tenant" bitta cookie bilan imkonsiz. Tuzatish: `login_hint=tenant_id` → maxsus parametr `tenant_id` (a'zolik bo'yicha tekshiriladi); `eskisi avtomatik bekor qilinmaydi (ikki tenant sessiyasi parallel bo'lishi mumkin, masalan ikki brauzer tab'ida…)` → `eski sessiya almashtirishda bekor qilinadi (bitta brauzer — bitta `__Host-sid` cookie — bitta faol tenant); parallel ishlash faqat alohida brauzer profilida`.
7. **`12-autentifikatsiya-oauth2.md:372-375`** (§18.2) — `PATCH /admin/users/{id}` (`status=blocked`) uchun "barcha sessiya/refresh oilasi darhol revoke + Redis `sid` kesh" aniq yozilmagan (US-M13-05 talab qiladi). Qo'shilsin. `:375` "faqat Egasi (va vakolatli Menejer)" — 05 §2.1 matritsasida (`:148`) `settings.users` faqat Egasida, shuning uchun `(va vakolatli Menejer)` olib tashlansin yoki matritsa yangilansin.
8. **`12-autentifikatsiya-oauth2.md:237`** — telefon bo'yicha qattiq bloklash hujumchiga Egasini ataylab bloklab qo'yish (lockout-DoS) imkonini beradi. Qo'shish: `Bloklash (telefon, IP/qurilma) juftligi bo'yicha; boshqa manbadan to'g'ri parol + CAPTCHA bilan kirish mumkin; xato xabari umumiy ("telefon yoki parol noto'g'ri").`
9. **`12-autentifikatsiya-oauth2.md:275`** — Redis ishlamasa `require_subscription_ok` xatti-harakati aniqlanmagan. Qo'shish: `Redis'da kalit yo'q yoki Redis ishlamasa — `subscriptions.status` DB'dan o'qiladi (fail-closed emas, fail-to-DB).` `:276` `pay_url` — hisob-faktura uchun alohida, token bermaydigan to'lov havolasi bo'lishi va faqat parol tasdiqlangandan keyin qaytarilishi aniq yozilsin. `/billing/*` istisnosi sessiyasiz amalda ishlatilmaydi — olib tashlansin.
10. **`12-autentifikatsiya-oauth2.md:121`** — `branch_ids`/`roles` token ichida 12 daqiqagacha eskirgan bo'lishi mumkin. Qo'shish: `filial doirasi (`current_branch_scope`) DB/Redis'dagi joriy `memberships.branch_ids`dan tekshiriladi; a'zolik o'zgarsa `sid` majburiy refresh qilinadi.`
11. **Imlo/eskirgan so'zlar**: `12-autentifikatsiya-oauth2.md:252` "qayta oча oladi" (kirill "ча") → `qayta ocha oladi`; `:385` va `01-malumotlar-modeli.md:49` "Kalendar/kred material", "Kalendar/parol/PIN" → `Parol/PIN heshlari`; `01-malumotlar-modeli.md:50` `user_credentials`da `password_algo` yo'q (12:386 da bor) — moslansin; `05-xavfsizlik-va-audit.md:333` "bcrypt/argon2" → `argon2id (12-autentifikatsiya-oauth2.md §4.1)`.
12. **Eskirgan "ochiq savol" / tarix matnlari**:
   - `03-biznes-jarayonlar.md:10` `— bu siyosat ochiq savol (quyida)` → `— offline **sotish** siyosati 2026-10-15 qarori bilan hal qilindi (narx ma'lum bo'lsa ruxsat, bo'lmasa taqiq, US-M01-03); qaytarish/ko'chirish — ochiq`.
   - `03-biznes-jarayonlar.md:396` boshiga `*(2026-10-15: sotish qismi hal qilindi — US-M01-03)*` qo'shilsin.
   - `07-tuzatishlar-va-yechimlar.md:22` (#15) `kechiksa kassa ishlaydi, back-office cheklanadi (taklif)` → `~~kechiksa kassa ishlaydi, back-office cheklanadi (taklif)~~ — 2026-10-15 #23 bilan bekor qilindi` va holat ustunidagi `kechikish siyosati huquqiy tasdiq kerak` → `#23 bilan almashtirildi`.
   - `README.md:9` "1C bilan hech qanday bog'liqlik yo'q." — bu o'zgarish emas, oldindan bor bo'lgan qator, lekin 07'dagi "vendor nomi ishlatilmaydi" direktivasiga zid. → `Tashqi buxgalteriya/ERP tizimlari bilan hech qanday bog'liqlik yo'q — mahsulot noldan qurilgan.`
   - `11-backlog.md:81` — CRPT Turon "MVP'dan keyin". Shuning uchun 4-qaror (offline markirovka) amalda CRPT integratsiyasi bilan birga quriladi. 1-bandga qo'shilsin: `(offline sotish qoidasi — narx ma'lum bo'lsa ruxsat — shu integratsiya bilan birga, 04-offline-sync §7)`.

---

## Tasdiqlandi

- **1-qaror (OAuth)**: tashqi IdP yo'q, Authlib + joserfc tanlovi asoslangan. Implicit/ROPC grantlari yo'q, PKCE S256 majburiy (`plain` rad etiladi), kod bir martalik va 60 s. RFC 9068 `typ: at+jwt` va standart claim'lar to'g'ri. Asimmetrik EdDSA, HMAC yo'q. Rotatsiya `next→active→retired`. Refresh opaque, faqat SHA-256 hash, oila bo'yicha reuse detection (K4 tuzatilsa). `sid` orqali deyarli darhol revoke. Introspect faqat confidential mijozlar uchun. argon2id (OWASP min m=19 MiB, t=2, p=1). PIN = OAuth grant emas — to'g'ri ta'rif. Scope → permission prefiksi "faqat birinchi filtr", yakuniy ruxsat `require_permission` — xavfsiz. Android RFC 8252 App Links. Testlar mock'siz (testcontainers).
- **BFF + CSRF**: token brauzerga chiqmaydi, sinxronizator-CSRF saqlangan, Bearer ozod — 05/08/09 izchil.
- **2-qaror**: 24 soat imtiyozdan keyin to'liq to'xtash — 00, 01-malumotlar (holat mashinasi), 03-integratsiyalar §9, 04-offline-sync §3.5, 05 #11, 08 (403 `SUBSCRIPTION_RESTRICTED`), 09, 11-backlog, README, 02 (US-M17-03/05), 04-ekranlar (POS-01/BO-01/1.x) va 07 (#23) bir xil. "Kassa ishlayveradi" matni faqat aniq belgilangan tarix sifatida qolgan (07 #15 bundan mustasno — KICHIK 12). Imzolangan litsenziya (`subscription_end + 24 soat`) va 48 soat fiskal muddatining mustaqilligi to'g'ri ajratilgan.
- **3-qaror**: 05-ai-funksiyalar, 06-mvp-chegarasi (jadval, footnote, Won't), README, 07-ai-qatlami §10, 04-ekranlar BO-04, 02 US-M04-04 — "4 ta AI funksiya" izchil (11-backlog bundan mustasno — K2).
- **4-qaror**: 02-modullar (US-M01-03, Offline, ochiq savol 2), 03-integratsiyalar (§4 xulosa, Offline, diagramma, ochiq savol 2), 04-ekranlar (1.3, ochiq savol 3), 01-rollar (ochiq savol 3), 07 (#25) izchil (04-offline-sync §7 bundan mustasno — K1).
- **5-qaror**: US-M01-06, BP-13 + matritsa, BO-15 tugmasi, ochiq savol 12 yopilgan, `einvoices.related_doc` modelda mavjud (O13'dagi registr va provodka eslatmasi bundan mustasno).
- **Admin panel**: BO-11 (Sessiyalar tabi, Bloklash, PIN/parol tiklash), ADM-01 (M13 qo'shilgan), US-M13-04…08 product darajasida to'liq. M13 offline chekka holati va "Egasi o'zini bloklay olmaydi" qoidasi to'g'ri.
- **Ma'lumotlar modeli**: 01 §10.1 va 12 §19 jadvallari asosan mos (`devices.token_hash` olib tashlangan, `user_credentials` ajratilgan); farqlar O7, O10 va KICHIK 11'da.
- Diff'da yangi 1C eslatmasi yo'q.
