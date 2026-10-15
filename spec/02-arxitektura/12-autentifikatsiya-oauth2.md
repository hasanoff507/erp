# Autentifikatsiya — OAuth 2.0 (o'z implementatsiyamiz)

*2026-10-15 · Foydalanuvchi qarori: autentifikatsiya **to'liq o'zimiz yozamiz** — uchinchi tomon auth xizmati yo'q, hech qanday mock yo'q; protokol OAuth 2.0, bizning backend **Authorization Server (AS) + Resource Server (RS)**. Asos: `00-umumiy-arxitektura.md`, `01-malumotlar-modeli.md` (users, memberships, roles, devices, platform_admins, subscriptions), `05-xavfsizlik-va-audit.md` (eski sessiya/CSRF/qurilma bo'limi — bu hujjat bilan almashtiriladi), `04-offline-sync.md` (401, actor_user_id, qurilma bekor qilish), `08-frontend-arxitekturasi.md`, `09-backend-arxitekturasi.md`, `spec/tekshiruv/00-qarorlar.md` (#3, #13), `spec/01-mahsulot/02-modullar-talablari.md` (M13, M17 — US-M17-03), `04-ekranlar-va-ux.md` (BO-11, BO-21, ADM-01).* *(2026-10-15: foydalanuvchi qarori)*

## Asosiy xulosalar

1. **Bitta backend — ham AS, ham RS**: FastAPI ilovasi o'zi OAuth 2.0 Authorization Server (token/kod beradi) va Resource Server (API so'rovlarini tekshiradi) vazifasini bajaradi — tashqi auth xizmati (Keycloak, Auth0, Firebase Auth va h.k.) ishlatilmaydi. Protokol skeleti uchun **Authlib** (RFC 6749/7636/7009/7662/8414/9068 ga mos generic grant/endpoint sinflari) ishlatiladi, lekin foydalanuvchi saqlash, parol/PIN tekshirish, token rotatsiyasi, qurilma bog'lash, obuna tekshiruvi — **hammasi bizning kod va bizning Postgres jadvallarimiz**; Authlib hech qachon tashqi tarmoqqa so'rov yubormaydi, bizning jarayonimiz ichida ishlaydi (2-bo'lim). *(2026-10-15: foydalanuvchi qarori)*
2. **To'rt turdagi OAuth mijoz**: veb SPA (back-office + veb-kassa) — **BFF** (Backend-for-Frontend) naqshi orqali, token hech qachon brauzer JS'iga chiqmaydi (HttpOnly cookie, eski qaror bilan izchil); Android POS — **public native client**, Authorization Code + PKCE, to'g'ridan-to'g'ri Bearer bilan API chaqiradi; Telegram bot — **confidential client**, Client Credentials; ichki admin panel (ADM-01) — BFF orqali boshqa veb SPA, alohida `client_id`.
3. **Ruxsat etilgan grant turlari**: Authorization Code + PKCE (RFC 7636, S256) — veb (BFF ichida) va Android uchun majburiy; Refresh Token — **rotatsiya + qayta ishlatish aniqlash (reuse detection)** bilan; Client Credentials — faqat ichki xizmatlar/bot uchun. **Implicit va Resource Owner Password Credentials (parol) grant'lari umuman yo'q** — OAuth 2.1 tavsiyasiga mos, xavfsizroq. *(2026-10-15: foydalanuvchi qarori)*
4. **Kirish usullari aniq uchta**: telefon+parol (back-office rollari), telefon+SMS OTP (**faqat ro'yxatdan o'tish va parolni tiklash**, kundalik kirish usuli emas), kassir **PIN — OAuth grant emas**, qurilmada mahalliy (hatto offline) tezkor almashish/tasdiqlash vositasi (4-bo'lim).
5. **Access token — JWT, RFC 9068 profili**, ~12 daqiqa (taxmin, 10–15 daqiqa oralig'ida), EdDSA bilan imzolanadi, `JWKS` orqali ochiq kalit e'lon qilinadi; **refresh token — opaque, bazada faqat hash holida**, qurilmaga bog'langan, rotatsiya va oila (`family_id`) bo'yicha qayta ishlatish aniqlanadi (7-bo'lim).
6. **Obuna muddati — qattiq to'xtatish (foydalanuvchi qarori, 2026-10-15)**: 24 soatlik imtiyoz tugagach tenant **barcha** sessiya/tokenlari bekor qilinadi, har bir mijoz login sahifasiga yo'naltiriladi, login **rad etiladi** (faqat to'lov havolasi ochiq qoladi); bu avvalgi "kassa ishlashda davom etadi" taklifini **bekor qiladi** (16-bo'lim). Fiskal oqibat: chek chiqarib bo'lmaydi — bu do'konning mas'uliyati, foydalanish shartlarida alohida qayd etiladi.
7. **Offline qurilmalar — imzolangan litsenziya tokeni** (`license`, JWT): `tenant_id`, `device_id`, `valid_until = subscription_end + 24 soat`; qurilma (veb-kassa ham, Android ham) internet bo'lmasa ham shu tokenni mahalliy tekshiradi va muddat o'tganda **o'zini mahalliy bloklaydi** — serverga murojaat shart emas (17-bo'lim).
8. **Veb-kassaning 48 soatlik offline oynasi** (fiskal, VM 943) va **24 soatlik obuna imtiyozi** (bizning ichki qaror) — **ikki mustaqil muddat**, bir-biriga bog'liq emas; qurilmaga bog'langan refresh token muddati ikkisidan ham ancha uzun qilib loyihalanadi (sliding 14 kun / mutlaq 180 kun, taxmin) — shu sababli 48 soatlik offline davrda mahalliy PIN, outbox yozish va `actor_user_id` bilan ishlash to'xtamaydi (8-bo'lim). *(2026-10-15: foydalanuvchi qarori)*
9. **Admin panel ikki qatlamda**: platforma admin (`platform_admins`) — tenant/Egasi darajasida boshqaradi (obuna uzaytirish, sessiyalarni majburiy bekor qilish, AI sarfi); tenant Egasi — o'z xodimlarini qo'shadi/bloklaydi, rol/filial tayinlaydi, **PIN'ni qayta o'rnatadi**, sessiya/qurilmalarni bekor qiladi (18-bo'lim).
10. **Scope — permission_code'dan hisoblanadi, qo'shimcha katalog kerak emas**: token `scope` claimi — foydalanuvchi rollarining joriy `role_permissions.permission_code` to'plamidagi noyob prefikslar ro'yxati (token yaratilganda hisoblanadi); bu faqat tezkor module-darajasidagi birinchi filtr, yakuniy ruxsat hamon `require_permission` + `limit_value` orqali tekshiriladi — ikkilanish yo'q (10-bo'lim).
11. **Xavfsizlik testlari — mock yo'q**: haqiqiy PostgreSQL va Redis (`testcontainers`) ustida to'liq Authorization Code+PKCE oqimi, refresh rotatsiyasi/reuse, revoke/introspect, obuna lokaut sinovlari ishga tushiriladi (21-bo'lim).
12. **2026-10-15 qabul-5 tuzatishlar** *(2026-10-15: qabul-5)*: haqiqiy front-channel login redirect (§2.1), refresh-rotatsiya poygasi uchun single-flight+30s imtiyoz oynasi (§7), Telegram bot har so'rovda obuna/bloklash tekshiradi (§2), lokaut `suspended` (to'liq `revoked` emas) + tor `sync.drain` drenaj yo'li (§16.4) + D1 qarori, eksport faqat to'lov-sahifa yo'lida SMS OTP bilan (§16.5) + D2 qarori, litsenziya tokeni alohida kalit/qisqa muddat/qurilmada soat-orqaga-surish himoyasi (§17), platforma admin MFA+alohida `aud`/prefiks (§18.1), auth-sxema jadvallari uchun to'g'ri RLS istisnosi (§19).

---

## 1. AS va RS rollari

Bitta FastAPI ilovasi (`app/modules/auth/`) ikki roli bajaradi:

| Rol | Vazifa | Endpoint'lar |
|---|---|---|
| **Authorization Server (AS)** | Foydalanuvchini autentifikatsiya qiladi, kod/token beradi, bekor qiladi, introspeksiya qiladi, kalitlarni e'lon qiladi | `/oauth/authorize`, `/oauth/token`, `/oauth/revoke`, `/oauth/introspect`, `/.well-known/oauth-authorization-server`, `/.well-known/jwks.json` |
| **Resource Server (RS)** | Har bir biznes so'rovida `Authorization: Bearer` (Android) yoki BFF sessiyasi (veb) orqali tokenni tekshiradi, `tenant_id`/`sid`/obuna holatini dependency orqali chiqaradi | `/api/v1/*` barcha modul endpoint'lari |

AS va RS **bitta jarayon, bitta DB** bo'lgani uchun token imzosini tashqi tarmoq orqali tekshirish shart emas — lekin RFC 8414/9068 formatiga qat'iy rioya qilinadi, chunki kelajakda RS modul(lar)i alohida xizmatga ajratilishi mumkin (`00-umumiy-arxitektura.md`, 1-xulosa — modulli monolitni keyin bo'lish rejasi) va Telegram bot/boshqa ichki xizmatlar allaqachon "tashqi" mijoz sifatida ishlaydi.

**Nega Authlib**: PKCE `code_verifier`/`code_challenge` solishtirish, redirect_uri qat'iy tekshiruvi, grant dispatch, RFC 8414 metadata formati — xavfsizlik jihatidan nozik primitivlar, qo'lda yozilsa xato qilish xavfi yuqori. Authlib (MIT, faol qo'llab-quvvatlanadi, FastAPI/Starlette bilan ishlatiladigan `authlib.oauth2.rfc6749` abstrakt grant/klient sinflari) shu primitivlarni beradi; **storage hook**'lari (`query_client`, `save_token`, `authenticate_user` va h.k.) orqali bizning SQLAlchemy repozitorilarimiz ulanadi — Authlib hech qanday ma'lumotni o'zida saqlamaydi, tashqariga yubormaydi. JWT/JWS/JWK operatsiyalari (imzolash, JWKS) — **joserfc** (Authlib muallifining zamonaviy kutubxonasi, EdDSA/ES256 ikkisini ham qo'llab-quvvatlaydi); muqobil — `PyJWT` + `cryptography`.

---

## 2. Mijozlar (OAuth clients)

| Mijoz (`oauth_clients.name`) | Turi | Oqim | Tafsilot |
|---|---|---|---|
| `web-bff` | **Confidential** (client_secret serverda, brauzerga hech qachon chiqmaydi) | Authorization Code + PKCE | Back-office va veb-kassa SPA'si **BFF naqshi** orqali: brauzer hech qachon access/refresh tokenni ko'rmaydi, faqat `sid` (sessiya ID) bilan imzolangan HttpOnly cookie oladi (3-bo'lim). PKCE confidential mijozda ham ishlatiladi (OAuth 2.1 tavsiyasi — qo'shimcha himoya qatlami, kod o'g'irlanishiga qarshi). |
| `admin-bff` | Confidential | Authorization Code + PKCE | ADM-01 ichki admin panel — alohida `client_id`/`scope` (`platform.admin`), login faqat `platform_admins` jadvaliga qarshi (18-bo'lim). |
| `android-pos` | **Public** (client_secret yo'q — APK ichida sir saqlab bo'lmaydi) | Authorization Code + PKCE | Android ilovasi to'g'ridan-to'g'ri `/oauth/authorize`+`/oauth/token` bilan gaplashadi, keyin API'ga **to'g'ridan-to'g'ri `Authorization: Bearer <access_token>`** bilan so'rov yuboradi (BFF orasida yo'q). Redirect — App Links bilan tasdiqlangan `https://<domen>/android/callback` (RFC 8252 — "OAuth 2.0 for Native Apps" tavsiyasi, custom scheme'ga qaraganda fishingga chidamliroq). Token qurilmada Android Keystore bilan himoyalangan saqlashda (`10-android-pos.md`da batafsil). |
| `telegram-bot` | Confidential | **Client Credentials** | Bot xizmati (aiogram) o'zining xizmat darajasidagi tokenini oladi (`scope: bot.internal`); muayyan foydalanuvchi/tenant konteksti **token orqali emas**, mavjud `telegram_links` (tenant_id, user_id, chat_id) jadvali orqali uzatiladi — bot va API bir xil ichki tarmoqda, ishonch chegarasi bir xil (`05-xavfsizlik-va-audit.md` §1.4 bilan izchil). |

**Bot so'rovlari uchun majburiy tekshiruvlar** *(2026-10-15: qabul-5)*: `bot.internal` tokeni faqat `/internal/bot/*` endpoint'lariga kiradi (boshqa hech qanday `/api/v1/*` yo'lini chaqirolmaydi — confused deputy oldini olish). Har so'rovda server `chat_id` → `telegram_links` (tenant_id, user_id) ni o'zi aniqlaydi va **foydalanuvchi so'rovi kabi** quyidagilarni tekshiradi: (1) `require_subscription_ok(tenant_id)` — `restricted`/`closed` bo'lsa faqat obuna/to'lov eslatmasi yuboriladi, AI-01 va hisobotlar botda yopiladi (2-qarorga mos — "butun tenant yopiladi" bot orqali ham amal qiladi); (2) `memberships.status='active'` — bloklangan foydalanuvchiga (US-M13-05) javob berilmaydi, uning `telegram_links` yozuvi bekor qilinadi (05 §1.4); (3) `require_permission` (masalan AI-01 uchun `ai.chat.use`, hisobot uchun `reports.sales.view`). Har chaqiruv `tenant_transaction(tenant_id)` ichida RLS bilan ochiladi — bot hech qachon `tenant_id`siz so'rov yubormaydi. Scope jadvali (10-bo'lim) `bot.internal`ni ham o'z ichiga oladi: `bot.internal` — Telegram bot xizmati, faqat `/internal/bot/*`, foydalanuvchi huquqlari har safar `telegram_links` orqali qayta tekshiriladi.

**NO**: implicit grant yo'q (token URL fragmentda ochiq qoladi, refresh yo'q — OAuth 2.1 olib tashlagan), parol (ROPC) grant yo'q. Telefon+parol/OTP login **AS'ning o'z `/oauth/authorize` sahifasi/`/auth/login` BFF endpoint'i** orqali, ya'ni birinchi tomon login shakli parolni to'g'ridan-to'g'ri AS'ning o'ziga beradi — bu ROPC emas, chunki parol hech qachon alohida "token" endpoint'iga mustaqil parametr sifatida kelmaydi va uchinchi tomon mijoziga aylanmaydi (standart birinchi-tomon AS naqshi).

### 2.1 Login oqimi (haqiqiy Authorization Code + PKCE, front-channel redirect) *(2026-10-15: qabul-5 — O6 tuzatish, variant a tanlandi)*

**Muammo va qaror**: avvalgi diagrammada brauzer parolni to'g'ridan-to'g'ri BFF'ga yuborar, BFF esa ichki `GET /oauth/authorize`ni chaqirardi — bu holda parolning AS'ga qanday yetishi noaniq edi va front-channel redirect yo'qligi sababli PKCE amalda hech narsani himoya qilmasdi ("bu ROPC emas" da'vosi asossiz edi). Shu sababli **haqiqiy front-channel redirect** tanlandi: parol faqat brauzerdan **to'g'ridan-to'g'ri AS login sahifasiga** (bitta domen, birinchi-tomon) POST qilinadi, hech qachon BFF orqali oraliq uzatilmaydi.

```mermaid
sequenceDiagram
    participant Br as Brauzer (SPA)
    participant BFF as Backend — BFF qatlami
    participant AS as OAuth AS (/oauth/authorize, /oauth/token)
    participant DB as PostgreSQL

    Br->>BFF: GET /auth/login/start
    BFF->>BFF: state + PKCE: code_verifier (Redis, sid'ga bog'langan, qisqa TTL), code_challenge = S256(verifier)
    BFF-->>Br: 302 Location: /oauth/authorize?client_id=web-bff&code_challenge=...&state=...&redirect_uri=/auth/callback
    Br->>AS: GET /oauth/authorize (brauzer AS login sahifasini ko'rsatadi, bitta domen)
    Br->>AS: POST (login sahifasidan) {phone, password} — parol faqat shu yerda, hech qachon BFF orqali emas
    AS->>DB: auth_find_user(phone) (SECURITY DEFINER) + argon2id tekshirish
    DB-->>AS: user_id, memberships (tenant tanlash kerak bo'lsa alohida qadam)
    AS->>DB: authorization_codes INSERT (code_hash, code_challenge, 60s TTL, bir martalik)
    AS-->>Br: 302 /auth/callback?code=...&state=...
    Br->>BFF: GET /auth/callback?code=...&state=...
    BFF->>BFF: state mosligini tekshiradi (login-CSRF/session-fixation'ga qarshi)
    BFF->>AS: POST /oauth/token {grant_type=authorization_code, code, code_verifier, client_secret}
    AS->>AS: S256(code_verifier) == code_challenge? redirect_uri mos?
    AS->>DB: access_token (JWT) + refresh_token (opaque) yaratish, sessions INSERT (yangi sid)
    AS-->>BFF: access_token (~12 daqiqa), refresh_token
    BFF->>DB: sessions.id = sid — token'lar serverda saqlanadi, brauzerga chiqmaydi
    BFF-->>Br: Set-Cookie: __Host-sid=... (HttpOnly, Secure, Path=/, Domain yo'q, SameSite=Lax)
```

Shu sababli PKCE bu oqimda haqiqiy himoya beradi: `code` front-channel redirect orqali o'tadi (brauzer tarixi/referrer orqali oshkor bo'lishi mumkin), lekin `code_verifier` hech qachon brauzerga chiqmaydi (BFF Redis'da, `sid`ga bog'langan) — kodni ushlab olgan uchinchi tomon `code_verifier`siz uni almashtira olmaydi.

**Qo'shimcha himoya** *(2026-10-15: qabul-5)*: (1) login so'rovida `Origin`/`Sec-Fetch-Site` tekshiruvi (login-CSRF'ga qarshi, boshqa sayt bu formani o'z nomidan yubora olmasligi uchun); (2) muvaffaqiyatli login va tenant almashtirishda `sid` **har doim yangilanadi** (session fixation'ga qarshi — eski `sid` bilan yangi sessiyaga "yopishib qolish" mumkin emas); (3) cookie nomi **`__Host-sid`** (Secure, Path=/, Domain atributi yo'q — brauzer bu cookie faqat aynan shu domenda, faqat HTTPS orqali yaratilishini kafolatlaydi).

API so'rovlarida: brauzer cookie yuboradi → BFF `sid` bo'yicha joriy access_token'ni topadi (kerak bo'lsa 7-bo'lim bo'yicha avtomatik refresh) → ichki chaqiruv (bir xil jarayon ichida) RS dependency'siga claims'ni uzatadi — bu "forward" tarmoq orqali emas, funksiya chaqiruvi darajasida. CSRF mexanizmi (sinxronizator-token, `GET /api/v1/auth/csrf`) **o'zgarmaydi** — faqat endi shu cookie OAuth tokeniga bog'langan sessiyani bildiradi (`05-xavfsizlik-va-audit.md` §1.3 bilan izchil).

---

## 3. Grant turlari — jadval

| Grant | Kim ishlatadi | Muhim qoidalar |
|---|---|---|
| `authorization_code` + PKCE (S256) | `web-bff`, `admin-bff`, `android-pos` | Kod bir martalik, 60 soniya TTL; `code_challenge_method=S256` majburiy (`plain` qabul qilinmaydi) |
| `refresh_token` | Hammasi (tokenni qayta olish) | Har ishlatishda **rotatsiya**; eski token qayta kelsa — butun oila (`family_id`) bekor qilinadi (7-bo'lim) |
| `client_credentials` | `telegram-bot`, kelajakdagi ichki xizmatlar | Foydalanuvchi konteksti yo'q, faqat xizmat darajasidagi scope |
| ~~`implicit`~~ | **Yo'q** | OAuth 2.1 bo'yicha olib tashlangan — token URL fragmentda, refresh yo'q, XSS xavfi yuqori |
| ~~`password` (ROPC)~~ | **Yo'q** | Parolni uchinchi tomon mijoziga ishonib topshirish modeli — BFF izolyatsiyasi maqsadiga zid |

---

## 4. Kirish usullari (login methods)

### 4.1 Telefon + parol

Back-office rollari (Egasi, Menejer, Buxgalter) uchun asosiy usul. Parol — **argon2id** (`passlib[argon2]`/`argon2-cffi`), parametrlar OWASP tavsiyasiga yaqin (taxmin, ishga tushirishdan oldin yuklama testi bilan tasdiqlanadi: m≈19 MiB, t=2, p=1). Bu `05-xavfsizlik-va-audit.md`dagi eski "bcrypt yoki argon2" ochiq tanlovini **argon2id**ga toraytiradi. *(2026-10-15: foydalanuvchi qarori — aniq algoritm belgilandi)*

### 4.2 Telefon + SMS OTP — faqat ro'yxatdan o'tish va tiklash

- **Ro'yxatdan o'tish** (US-M17-01, BO-21): telefon → 6 xonali OTP (5 daqiqa TTL, taxmin) → tasdiqlangach `users` yaratiladi.
- **Parolni tiklash**: telefon → OTP → OTP tasdiqlangan qisqa muddatli "tiklash seansi" → yangi parol o'rnatiladi. OTP bu yerda ham, kundalik kirish uchun emas, faqat identifikatsiyani tasdiqlash vositasi.
- OTP — **kundalik login usuli emas** (vazifa talabiga aniq mos): har kuni kirish parol (yoki PIN, quyida) bilan.
- Qoidalar: 6 raqam, bir martalik, heshlangan holda saqlanadi (`otp_challenges.code_hash`), maksimal 5 tekshirish urinishi (keyin challenge bekor, yangi OTP talab qilinadi), yuborish cheklovi — 12-bo'limdagi to'liq limitlar jadvaliga qarang (telefon/IP/global, O11 tuzatish).
- **Taklif va Egasi tomonidan tiklash** *(2026-10-15: qabul-5 — O10 tuzatish)*: `otp_challenges.purpose` qiymatlari kengaytirildi — `signup`/`recovery`/**`invite`**/**`admin_reset`**/**`pin_reset`**. `invite` — Egasi yangi xodimni qo'shganda (BO-11), `admin_reset` — Egasi xodimning parolini majburiy tiklaganda (`POST /admin/users/{id}/reset-password`, 18.2-bo'lim). Ikkala holatda ham: eski kredensial (parol/PIN) **avval bekor qilinadi**, xodimning barcha sessiya/refresh-token oilasi revoke qilinadi, so'ng xodimga SMS orqali **bir martalik taklif/tiklash kodi** yuboriladi (hech qachon parol/PIN ochiq matnda emas) — xodim shu kod bilan **o'zi** yangi parol/PIN o'rnatadi; kod token qaytarmaydi, faqat qisqa muddatli "credential-set seansi" ochadi. `pin_reset` — xuddi shunday, faqat PIN uchun (mavjud `POST /admin/users/{id}/reset-pin` oqimi bilan birlashtiriladi).

### 4.3 Kassir PIN — **OAuth grant emas, aniq ta'rif**

PIN — token olish vositasi emas, balki **allaqachon OAuth orqali autentifikatsiya qilingan qurilmada** mahalliy, tezkor amal bajaruvchini aniqlash/tasdiqlash vositasi:

1. Qurilma (veb-kassa brauzeri yoki Android POS) kuniga bir marta (yoki smena boshida) **to'liq OAuth Authorization Code+PKCE login** qiladi — bu qurilmaga bog'langan `sessions`/`refresh_tokens` yozuvini yaratadi (`scope` ichida `pos` bor).
2. Shundan keyin kassir almashganda **yangi OAuth login kerak emas** — PIN mahalliy keshlangan `users.pin_hash` (sync orqali tushadi, `04-offline-sync.md` §1 `permissions` jadvali) bilan solishtiriladi, offline ham ishlaydi.
3. PIN natijasi **token emas** — u outbox voqeasining `actor_user_id` maydonini to'ldiradi (allaqachon `04-offline-sync.md` §2'da bor naqsh); server sinxronlashda `actor_user_id`ning shu `created_at` paytida faol `membership`i borligini qayta tekshiradi.
4. **Step-up tasdiqlash PIN** (limitdan yuqori chegirma/qaytarish/nasiya, `05-xavfsizlik-va-audit.md` §2.3): Menejer/Egasi PIN kiritadi → bu ham token emas, balki voqea payload'iga qo'shiladigan tasdiqlovchi maydon (`approved_by_user_id`, `approved_by_pin_verified_at`), server qayta tekshiradi (limit, faollik). Mahalliy noto'g'ri PIN limiti — mavjud qoida (taxmin: 5 urinish, `04-offline-sync.md` §12) o'zgarmaydi, bu yerda faqat OAuth bilan bog'liq emasligi aniqlashtiriladi.
5. Online holatda PIN qurilma-almashtirish uchun qo'shimcha server tasdig'i kerak bo'lsa — `POST /auth/pin/verify` (20-bo'lim) chaqiriladi, lekin bu ham yangi OAuth token qaytarmaydi, faqat `actor_user_id`ni serverda tasdiqlaydi va audit yozadi.

**Xulosa**: PIN hech qachon mustaqil ravishda API chaqirish huquqini bermaydi — bu huquq faqat qurilmaning OAuth access/refresh tokenidan keladi. PIN — "kim bosdi" savoliga javob, "ruxsat bor-yo'qligi" savoliga emas.

---

## 5. Access token (JWT, RFC 9068)

| Jihat | Qaror |
|---|---|
| Format | JWT, header `typ: "at+jwt"` (RFC 9068) |
| Muddat | **~12 daqiqa** (taxmin, 10–15 daqiqa oralig'ida — vazifa talabi) |
| Standart claim'lar | `iss`, `aud` (`urn:erp:api`), `sub` (user_id), `client_id`, `iat`, `exp`, `jti` |
| Bizning claim'lar | `tenant_id`, `branch_ids` (bo'sh = hammasi), `roles` (rol kodlari), `scope` (10-bo'lim), `sid` (sessiya ID — pastda), `device_id` (bo'lsa), `sub_status` |
| `sub_status` ma'nosi | Token yaratilgan paytdagi `subscriptions.status` **keshi** — faqat UI tezkor ko'rsatish uchun, **hal qiluvchi emas**: har so'rovda Redis'dagi joriy holat tekshiriladi (16-bo'lim), token ichidagi eski qiymatga ishonilmaydi |

**`sid` — revoke uchun kalit**: JWT o'zi stateless, lekin "barcha sessiyalarni bekor qilish" (18-bo'lim) va obuna to'xtatilganda **darhol** ta'sir qilishi uchun har bir himoyalangan so'rovda `sid` Redis'dagi bekor qilingan-sessiyalar to'plamiga (yoki `sessions.revoked_at`) qarshi tekshiriladi (qisqa TTL kesh, 30–60 soniya). Shu sababli 10–15 daqiqalik token muddati amalda "eng yomon holatda shuncha vaqt kutish" degani emas — bekor qilish keshi orqali deyarli zudlik bilan ishlaydi.

**`branch_ids`/`roles` eskirishi** *(2026-10-15: qabul-5 — KICHIK 10 tuzatish)*: token ichidagi `branch_ids`/`roles` token yaratilgan paytdagi qiymat, demak token muddati davomida (≤12 daqiqa) eskirgan bo'lishi mumkin. Shu sababli filial doirasi (`current_branch_scope` dependency, `05-xavfsizlik-va-audit.md` §2.4) har so'rovda token claim'iga emas, **DB/Redis'dagi joriy `memberships.branch_ids`ga** qarshi tekshiriladi. A'zolik (rol/filial) o'zgarganda `settings.users` amali shu foydalanuvchining `sid`ini majburiy refresh qilinadigan deb belgilaydi (keyingi so'rovda access token yangi claim bilan qayta chiqariladi) — bu `18.2-bo'lim`dagi "Sessiya/qurilmalarni bekor qilish" bilan bir xil mexanizm, faqat to'liq revoke o'rniga yengil "claims stale" belgisi.

---

## 6. Imzolash kalitlari va JWKS

- **Algoritm: EdDSA (Ed25519)** — tezkor, qisqa imzo, zamonaviy; **ES256** — moslik zaxirasi (agar kelajakda alohida RS chiqarilsa va uning kutubxonasi EdDSA'ni qo'llamasa). HMAC (simmetrik) ishlatilmaydi — JWKS orqali ochiq kalit e'lon qilish faqat asimmetrik kalit bilan xavfsiz.
- **`GET /.well-known/jwks.json`** — joriy + oldingi (overlap davridagi) ochiq kalitlar, `kid` bilan.
- **Rotatsiya**: `signing_keys` jadvalida (19-bo'lim) `next → active → retired` holat zanjiri; rejalashtirilgan rotatsiya — **90 kun** (taxmin); favqulodda rotatsiya (shubhali buzilish) — darhol, mos ravishda ommaviy sessiya/refresh-token bekor qilish bilan birga. Eski kalit shu kalit bilan imzolangan eng uzoq muddatli tokenning amal qilish muddati tugaguncha (access token max + clock skew bufer, ≈30 daqiqa) JWKS'da qoladi, keyin olib tashlanadi.
- Xususiy kalit — `signing_keys.private_key_encrypted`, `05-xavfsizlik-va-audit.md` §4.2'dagi **DEK/KEK envelope encryption** sxemasi bilan bir xil mexanizmda saqlanadi (qayta ixtiro qilinmaydi).

---

## 7. Refresh token: rotatsiya va oila (family)

| Jihat | Qaror |
|---|---|
| Format | **Opaque** (tasodifiy, yuqori entropiya), JWT emas — oshkor bo'lsa claim oshkor qilmaydi |
| Saqlash | Faqat **hash** (`refresh_tokens.token_hash`, SHA-256 — token o'zi yuqori entropiyali bo'lgani uchun argon2 shart emas) |
| Rotatsiya | Har ishlatilganda **yangi** refresh token chiqariladi, eskisi `used_at` bilan belgilanadi (qayta ishlatib bo'lmaydi) |
| Oila (`family_id`) | Bitta login'dan tarqalgan barcha ketma-ket refresh tokenlar bir xil `family_id`ga ega |
| **Qayta ishlatishni aniqlash** | Allaqachon `used_at`li token qayta kelsa → **butun oila** (barcha avlod tokenlar + `sessions`) darhol bekor qilinadi, `audit_log`ga `refresh_token_reuse_detected`, foydalanuvchiga qayta login talab qilinadi |
| **Parallellik va tarmoq uzilishi** *(2026-10-15: qabul-5 — K4 tuzatish)* | (1) BFF bitta `sid` bo'yicha refresh so'rovini **single-flight** qiladi: Redis lock `refresh:{sid}` (qisqa TTL, masalan 5 soniya) olinadi, shu lock ostida kelgan boshqa parallel so'rovlar birinchisi tugashini **kutadi** va uning natijasini qaytaradi (qayta `/oauth/token` chaqirmaydi) — SPA'ning bir vaqtda 3–6 so'rov yuborishi endi oilani bekor qilmaydi. (2) **Imtiyoz oynasi (reuse grace window)**: agar RT1 qayta kelsa va `now − RT1.used_at ≤ 30 soniya` (taxmin) hamda undan tug'ilgan RT2 **hali ishlatilmagan** bo'lsa — bu "reuse" deb hisoblanmaydi (tarmoq uzilib javob yetmagan holat), oila bekor qilinmaydi, RT2 (idempotent, qayta yaratilmaydi) qaytariladi. Shu oynadan tashqarida yoki RT2 allaqachon ishlatilgan bo'lsa — odatdagi reuse detection (yuqoridagi qator) to'liq kuchda qoladi. |
| Muddat (veb, qurilmasiz) | Sirpanuvchi bo'sh turish 12 soat / mutlaq **7 kun** (`05-xavfsizlik-va-audit.md` §1.3 bilan izchil) |
| Muddat (qurilmaga bog'langan — Android, veb-kassa) | Sirpanuvchi **14 kun** / mutlaq **180 kun** (taxmin) — 48 soatlik offline oynadan ancha uzun, shu bilan 8-bo'limdagi talabni qondiradi |
| Bog'lanish | `client_id`, `user_id`, `tenant_id`, `device_id` (qurilma konteksti bo'lsa) |
| **Obuna tekshiruvi** | Har bir refresh so'rovi ham (nafaqat har API so'rovi) obuna holatini tekshiradi (16-bo'lim) — `restricted` tenant uchun hali amal qiladigan refresh token ham yangi access token olishga yaroqsiz |

### 7.1 Refresh rotatsiyasi va reuse detection diagrammasi

```mermaid
sequenceDiagram
    participant D as Qurilma/BFF
    participant AS as /oauth/token
    participant DB as refresh_tokens

    D->>AS: grant_type=refresh_token, refresh_token=RT1
    AS->>DB: RT1 topildi, used_at IS NULL?
    DB-->>AS: ha — amal qiladi
    AS->>DB: RT1.used_at=now; RT2 INSERT (family_id bir xil, RT1.replaced_by=RT2)
    AS-->>D: yangi access_token + RT2

    Note over D,AS: ...keyinroq, kimdir eski RT1'ni qayta yuboradi (o'g'irlangan nusxa)
    D->>AS: grant_type=refresh_token, refresh_token=RT1 (allaqachon ishlatilgan)
    AS->>DB: RT1.used_at IS NOT NULL — qayta ishlatish aniqlandi!
    AS->>DB: family_id bo'yicha BARCHA tokenlar + sessions.revoked_at=now
    AS->>AS: audit_log: refresh_token_reuse_detected
    AS-->>D: 400 invalid_grant — qayta login talab qilinadi
```

**Eslatma** *(2026-10-15: qabul-5)*: yuqoridagi diagramma "haqiqiy o'g'irlash" holatini ko'rsatadi. Agar RT1 qaytib kelgan payt `now − RT1.used_at ≤ 30 soniya` va RT2 hali ishlatilmagan bo'lsa (BFF single-flight qulfi ostida yoki tarmoq uzilib javob yetmagan holat) — bu oila bekor qilinmaydi, 7-bo'lim jadvalidagi "Parallellik va tarmoq uzilishi" qoidasi qo'llanadi.

---

## 8. Offline va ikki mustaqil muddat

**Muhim aniqlik** (vazifa talabi — ikkisini aralashtirmaslik): 48 soat va 24 soat — ikki har xil, bog'liqsiz hisob-kitob:

| Muddat | Nima uchun | Qayerda hisoblanadi | Tugaganda nima bo'ladi |
|---|---|---|---|
| **48 soat** | Fiskal qonun (VM 943, 1-ilova 31-band) — offline chek OFD'ga yetib borish muddati | Birinchi offline voqea `created_at`'idan (`04-offline-sync.md` §6) | Bloklanish yo'q (qonunda topilmadi), faqat audit + eskalatsiya (`04-offline-sync.md` §6) |
| **24 soat** | Bizning ichki obuna qarori (foydalanuvchi qarori, 2026-10-15) — to'lov imtiyozi | `subscriptions.current_period_end`'dan (`grace_ends_at`) | **Qattiq to'xtatish**: barcha sessiya bekor, login rad etiladi, offline qurilma mahalliy bloklanadi (16–17-bo'lim) |

Bu ikkisi mustaqil bo'lgani uchun, masalan, obuna muddati tugashi 48 soatlik fiskal taymerni "qisqartirmaydi" va aksincha — lekin amaliyotda obuna `restricted` bo'lgan tenant allaqachon yangi sotuv qila olmaydi (17-bo'lim), shu sababli yangi fiskal taymer boshlanmaydi; **lokautdan oldin** qonuniy yaratilgan, hali OFD'ga yetmagan cheklar esa yo'qolmasligi kerak (fiskal 48 soat, VM 943) — bu **tor, cheklangan** `sync.drain` yo'li orqali ta'minlanadi, batafsil **16.4-bo'lim**. Bu cheklov emas, faqat **yangi** amal (`sale.created` va h.k.) mahalliy litsenziya tekshiruvidan o'tmaydi. *(2026-10-15: qabul-5 — K3 tuzatish)*

**Qurilmaga bog'langan refresh token muddati** (7-bo'lim, sliding 14 kun/mutlaq 180 kun) ikkala muddatdan ham ancha uzun qilib tanlangan — shu sababli 48 soatlik offline davr davomida: (a) mahalliy PIN bilan kassir almashish davom etadi (4.3-bo'lim, serverga bog'liq emas), (b) outbox'ga yozish va `actor_user_id` biriktirish davom etadi (4.3-bo'lim, `04-offline-sync.md` §2 o'zgarmaydi), (c) internet qaytganda, agar 12–15 daqiqalik access token eskirgan bo'lsa, qurilma **jim** (foydalanuvchidan so'ramasdan) refresh token bilan yangi access token oladi va keyin push qiladi — faqat shu refresh so'rovi ham 16-bo'limdagi obuna tekshiruvidan o'tishi kerak.

---

## 9. Tenant almashtirish

Bitta `users.id` bir nechta tenantda `memberships`ga ega bo'lishi mumkin (mavjud model). **Qaror: bir tenant — bir token** (foydalanuvchi talabi aniq): JWT'dagi `tenant_id` claim fiksirlangan, bir token boshqa tenantga "ko'chmaydi". **Bitta brauzer — bitta `__Host-sid` cookie — bitta faol tenant** *(2026-10-15: qabul-5 — KICHIK 6 tuzatish)*: ikki tenant sessiyasi bitta cookie ichida parallel bo'lishi **mumkin emas** (bitta `__Host-sid` faqat bitta `sessions` yozuvini ko'rsatadi). Tenant almashtirish — maxsus `tenant_id` parametri (`login_hint` emas — bu OpenID Connect semantikasi, bu yerda noto'g'ri ishlatilgan edi) bilan **yangi** Authorization Code+PKCE oqimi: foydalanuvchining shu tenant'da `membership`i borligi tekshiriladi, **eski sessiya (eski `sid`, eski refresh-token oilasi) almashtirishda bekor qilinadi**, yangi `access_token`/`refresh_token`/`sid` juftligi beriladi. Parallel ishlash (masalan ikki tenant bir vaqtda ochiq turishi) faqat **alohida brauzer profilida/qurilmada** mumkin — bu ikkisi mustaqil cookie-muhitlar, shuning uchun model buzilmaydi. Frontend'dagi `$tenant` tanlovchisi (`08-frontend-arxitekturasi.md`) ichki `POST /bff/switch-tenant` chaqiradi, bu AS bilan to'liq kod almashinuvini qayta bajaradi, eski `sid`ni revoke qiladi va **bitta** cookie'dagi `sid`ni yangi sessiyaga ko'rsatadi.

---

## 10. Scope ↔ ruxsat kodlari (permission_code)

Alohida scope katalogi **yaratilmaydi** — token yaratilganda foydalanuvchining joriy `role_permissions.permission_code` to'plamidan **noyob prefikslar** (nuqtadan oldingi qism) hisoblab chiqariladi va `scope` claim'iga (bo'sh joy bilan ajratilgan ro'yxat, RFC 6749) qo'yiladi:

| Prefiks (= scope) | Manba modul (`05-xavfsizlik-va-audit.md` §2.1) |
|---|---|
| `sales`, `shift`, `cash_register` | M01 |
| `returns` | M02 |
| `discount` | M03 |
| `stock` | M04, M05 |
| `transfer` | M06 |
| `purchases`, `einvoice` | M07 |
| `debts` | M08 |
| `prices`, `labels` | M09 |
| `tax` | M10 |
| `accounting` | M11 |
| `reports` | M12 |
| `settings` | M13, M14 |
| `expenses` | M15 |
| `cash` | M16 |
| `billing` | M17 |
| `notifications`, `telegram` | M18 |
| `ai` | AI-xx |
| `platform` | `platform.admin` |
| `sync` (yangi) | `/sync/push`, `/sync/pull` — Android/veb-kassa uchun implicit |
| `pos` (yangi) | PIN-asosli tezkor amallar uchun implicit (4.3-bo'lim) |

**Qoida**: `scope` — RS'da DB so'rovisiz tezkor, **birinchi** (kesishtiruvchi) filtr: agar kerakli prefiks token `scope`ida yo'q bo'lsa, so'rov darhol `403` (DB'ga borilmaydi). Lekin **yakuniy** ruxsat — hamon bugungidek `require_permission("sales.create")` dependency orqali `role_permissions` (limit bilan) tekshiriladi, o'zgarmaydi. Scope hech qachon permission tekshiruvining o'rnini bosmaydi, faqat tezkorlashtiradi.

---

## 11. Step-up/tasdiqlash PIN — cross-ref

4.3-bo'limda ta'riflangan. Limit/tasdiqlash mantiqi (`05-xavfsizlik-va-audit.md` §2.3) o'zgarmaydi — bu bo'lim faqat uning OAuth bilan bog'liq emasligini aniqlashtiradi.

---

## 12. Brute-force himoyasi va rate limit

| Kanal | Limit | Natija |
|---|---|---|
| Login (telefon+parol) | 5 ketma-ket xato / **(telefon, IP/qurilma) juftligi** / 15 daqiqa (taxmin) *(2026-10-15: qabul-5 — KICHIK 8 tuzatish)* | Progressiv bloklash: 1 → 5 → 15 → 60 daqiqa (taxmin); `audit_log: account_locked`. Bloklash juftlik bo'yicha, shuning uchun hujumchi bitta telefon raqamini **boshqa manbadan to'g'ri parol bilan** kirishni istalgan vaqt bloklay olmaydi (lockout-DoS'ga qarshi); qo'shimcha himoya — progressiv kechikishdan keyin CAPTCHA. Xato xabari har doim umumiy: "telefon yoki parol noto'g'ri" (qaysi qism xato ekanini oshkor qilmaydi) |
| Login (IP bo'yicha, mustaqil) | 20 xato / IP / soat (taxmin) | Credential stuffing'ga qarshi, telefon limitidan mustaqil |
| OTP yuborish *(2026-10-15: qabul-5 — O11 tuzatish)* | 10 / telefon / sutka; 20 / IP / soat; global sutkalik byudjet (alert bilan); faqat `+998` raqamlar qabul qilinadi | `429`; global byudjetdan oshganda qo'shimcha CAPTCHA talab qilinadi (SMS pumping/toll-fraud'ga qarshi) |
| OTP tekshirish | 5 urinish / challenge | Challenge bekor qilinadi, yangi OTP talab qilinadi |
| **Enumeratsiya** *(2026-10-15: qabul-5 — O11 tuzatish)* | — | `recovery`/login javobi telefon ro'yxatda bor-yo'qligidan qat'i nazar **bir xil** ("Agar raqam ro'yxatda bo'lsa, kod yuborildi") — javob vaqti ham barqarorlashtiriladi (timing oracle'ga qarshi) |
| PIN (mahalliy/`/auth/pin/verify`) | 5 urinish (taxmin, `04-offline-sync.md` §12 bilan bir xil) | Qurilmada shu foydalanuvchi uchun vaqtincha bloklanadi (15 daqiqa, taxmin) |
| `/oauth/token` (refresh) | Client_id/device bo'yicha cheklangan (`slowapi`) | Refresh-token-grinding hujumiga qarshi |

Barchasi `slowapi` (Redis backend) orqali, `09-backend-arxitekturasi.md` §5'dagi tanlov bilan izchil.

---

## 13. Parol/PIN heshlash, hisob bloklash — xulosa

- Parol: **argon2id** (4.1-bo'lim).
- PIN: `user_credentials.pin_hash` (19-bo'lim) — alohida, qisqa (4–6 raqam, taxmin), tuz bilan heshlangan, faqat tenant/qurilma kontekstida tekshiriladi.
- Hisob bloklash ikki xil: (a) **avtomatik, vaqtinchalik** — brute-force limitidan (12-bo'lim), o'zi tugaydi; (b) **qo'lda, doimiy** — Egasi "Bloklash" tugmasi (`memberships.status='blocked'`, BO-11, 18-bo'lim) — faqat Egasi qayta ocha oladi. *(2026-10-14 → 2026-10-15: imlo tuzatildi — KICHIK 11)*

---

## 14. Audit voqealari (qo'shimcha ro'yxat)

`05-xavfsizlik-va-audit.md` §6.1'dagi ro'yxatga quyidagilar qo'shiladi: `login_success`, `login_failed`, `account_locked`, `otp_requested`, `otp_verified`, `otp_failed`, `password_changed`, `password_reset`, `pin_changed`, `pin_reset_forced`, `refresh_token_reuse_detected`, `session_revoked`, `all_sessions_revoked`, `tenant_switched`, `device_registered`, `device_revoked` (mavjud), `subscription_lockout_triggered`, `subscription_restored`, `signing_key_rotated`.

---

## 15. Kalitlar va sirlar boshqaruvi

- Imzolash xususiy kaliti (6-bo'lim) va `oauth_clients.client_secret_encrypted` (confidential mijozlar: `web-bff`, `admin-bff`, `telegram-bot`) — `05-xavfsizlik-va-audit.md` §4.2'dagi **DEK/KEK envelope encryption** sxemasi orqali saqlanadi, qayta ixtiro qilinmaydi.
- `client_secret` rotatsiyasi — favqulodda holatda (kod bazasi buzilgan gumon) darhol, rejalashtirilgan — yillik (taxmin).

---

## 16. Obuna muddati bo'yicha kirish nazorati (foydalanuvchi qarori 2026-10-15)

**Qaror aniq**: 24 soatlik imtiyoz tugagach — kassa **to'liq** to'xtaydi (avvalgi "kassa ishlashda davom etadi" taklifi **bekor qilinadi**). Barcha sessiya/token bekor, har bir mijoz login sahifasiga yo'naltiriladi, login rad etiladi (faqat to'lov yo'li ochiq). *(2026-10-15: foydalanuvchi qarori — supersedes avvalgi taklif)*

### 16.1 Mexanizm

1. **Har bir himoyalangan so'rov**: `require_subscription_ok` dependency Redis'dan `sub_status:{tenant_id}` o'qiydi (qisqa TTL kesh, masalan 60 soniya fallback bilan — asosiy yangilanish cron/webhook orqali darhol). `restricted`/`closed` bo'lsa → `403 {code: SUBSCRIPTION_RESTRICTED}`, **faqat** quyidagilar bundan mustasno: `/auth/*` (login rad javobi, parol/PIN tiklash OTP oqimi), `/.well-known/*`, to'lov sahifasi yo'li (`/billing/pay`, 16.3-bo'lim), **`GET /billing/plan`, `GET /billing/subscription`, `GET /billing/addons`, `GET /billing/payments`** (o'qish — tenant qancha qarzi borligini ko'rishi uchun), **`POST /billing/checkout`** (16.1.1a-bo'lim — oddiy sessiya o'rniga `pay_token` bilan ishlaydi) va **`/billing/webhooks/*`** (provayder o'z imzosi bilan tasdiqlaydi, sessiyadan mustaqil, 9-bo'lim). Eksport **yopiq** (US-M17-03/US-M17-05) — D2 qarori bo'yicha faqat to'lov sahifasidan alohida, cheklangan yo'l bilan mumkin (16.5-bo'lim), `/billing/export-my-data` shu sabab yuqoridagi istisno ro'yxatiga **kiritilmaydi** o'z OTP shartisiz. `/sync/push` bundan alohida: faqat `scope=sync.drain` bilan, faqat lokautdan oldingi voqealar uchun ochiq (16.4-bo'lim). **KRITIK tuzatish** *(2026-10-15: qabul-6 — B-02/Z-01)*: avvalgi ro'yxatda `POST /billing/checkout` yo'q edi — bu holda `restricted` tenant hech qanday yo'l bilan to'lay olmasdi (faqat `/billing/pay` sahifa ochilib, lekin checkout endpoint'ining o'zi bloklanardi). Bu ro'yxat `09-backend-arxitekturasi.md` §3 middleware tartibida ham bir xil. *(2026-10-15: qabul-5 — O1 tuzatish, D2 qarori)*
   - **Redis ishlamasa yoki kalit topilmasa** *(2026-10-15: qabul-5 — KICHIK 9 tuzatish)*: `require_subscription_ok` **fail-to-DB** qiladi — `subscriptions.status` to'g'ridan-to'g'ri Postgres'dan o'qiladi (fail-closed emas, soft-fail — Redis uzilishi butun tizimni to'xtatmaydi), natija qisqa muddatga qayta Redis'ga yoziladi.
2. **Har bir `/oauth/token` (kod almashtirish YOKI refresh)**: xuddi shu tekshiruv — `restricted` tenant uchun token **berilmaydi** (bundan mustasno — 16.4-bo'limdagi `sync.drain`), lekin javobda `tenant_id`, `plan_id`, `amount_due`, `pay_url` qaytariladi — shunda BFF/login sahifasi generik xato o'rniga "Obuna muddati tugagan" + to'lov havolasi ko'rsatadi (`08-frontend-arxitekturasi.md`da bu holat). **`pay_url`** — hisob-faktura/to'lov havolasi uchun alohida, **token bermaydigan** qisqa muddatli havola (hech qanday OAuth scope yoki sessiya bermaydi, faqat Click/Payme checkout'ga olib boradi); u faqat parol muvaffaqiyatli tasdiqlangandan (yoki mavjud sessiya tasdiqlangandan) keyin qaytariladi — anonim so'rovchiga tenant to'lov holati oshkor qilinmaydi. *(2026-10-15: qabul-5 — KICHIK 9 tuzatish)*

### 16.1.1a `pay_token` — `restricted` holatda `POST /billing/checkout`ni ochish *(2026-10-15: qabul-6 — B-02/Z-01/K3-04, KRITIK tuzatish)*

**Muammo**: `restricted`/`closed` holatda oddiy OAuth sessiya/access-token berilmaydi (16.1.3-bo'lim), lekin tenant aynan shu holatda to'lov qilishi kerak — `POST /billing/checkout`ning o'zi himoyalangan endpoint, demak sessiyasiz chaqirilmaydi. Yechim — checkout uchun **alohida, juda tor** autentifikatsiya artefakti:

1. `/login?reason=subscription_expired` sahifasida foydalanuvchi telefon+parol bilan tasdiqlanadi (16.1.2-bandidagi kabi, to'liq login emas — oddiy OAuth token berilmaydi).
2. Tasdiqlangandan keyin server qisqa muddatli (taxmin: 15 daqiqa), opaque **`pay_token`** qaytaradi (Redis'da, `tenant_id`+`user_id` bilan bog'langan, faqat **bitta** maqsad uchun).
3. `POST /billing/checkout` so'rovi bu token bilan `Authorization: PayToken <token>` sarlavhasida chaqiriladi. RS bu sxemani alohida taniydi: `require_subscription_ok`ni **chetlab o'tadi** (aynan shu sabab checkout ishlashi kerak), lekin **faqat** `POST /billing/checkout` yo'lini ochadi — boshqa hech qanday `/api/v1/*` yoki `/billing/*` endpoint `PayToken` bilan ishlamaydi (403).
4. Checkout muvaffaqiyatli yaratilgach (yoki foydalanuvchi to'lovni yakunlagach, webhook orqali), `pay_token` **bir martalik** sifatida iste'mol qilinadi (consumed) — qayta ishlatib bo'lmaydi.
5. To'lov webhook orqali tasdiqlangach — 16.1.5-band bo'yicha oddiy holat tiklanadi, qayta login (parol) shart emas.

Bu mexanizm `active`/`grace` holatida ishlatilmaydi — u yerda oddiy sessiya orqali `POST /billing/checkout` chaqiriladi, `pay_token` faqat `restricted`/`closed`ga xos.

3. **Zudlik bilan ta'sir — `suspended`, to'liq `revoked` emas** *(2026-10-15: qabul-5 — K3/O2 tuzatish, D1 qarori)*: grace tugashi bilan scheduler (SAQ cron, `09-backend-arxitekturasi.md` §4) shu tenant bo'yicha **barcha** `sessions`/`refresh_tokens`ni **`suspended_at=now`, `revoked_reason='subscription'`** bilan belgilaydi — bu **xavfsiz-sodda tanlov** (O2): to'liq `revoked_at` emas, chunki keyin to'lov qilinganda token zanjirini qaytadan yaratish (qayta login) shart bo'lmasin, oddiy kassir faqat PIN biladi va parol bilan qayta kira olmaydi. `suspended` refresh token **oddiy** (`scope` to'liq) access token olishga yaroqsiz — faqat `scope=sync.drain` bilan cheklangan access token olishi mumkin (16.4-bo'lim). Redis `sub_status`/`sid`-revoke keshi darhol yangilanadi — shu sababli hali amal qilishi kerak bo'lgan (10–15 daqiqalik) access tokenlar ham keyingi so'rovda rad etiladi, tabiiy `exp`ni kutish shart emas.
4. **Frontend javobi**: mavjud 401/403 interceptor (`08-frontend-arxitekturasi.md` §3) `SUBSCRIPTION_RESTRICTED` kodini tanib, `/login?reason=subscription_expired` ga yo'naltiradi. **Bu logout emas** — Dexie/outbox o'chirilmaydi (16.4-bo'lim bilan izchil). Ekran ochiq, lekin foydalanuvchi hech narsa bosmasa ham tezroq sezish uchun — yengil davriy "heartbeat" (`GET /auth/session`, taxmin ~30 soniya) tavsiya etiladi (ixtiyoriy, kelajakdagi WebSocket/SSE "majburiy chiqish" kanali — ochiq savol).
5. **To'lov qaytganda**: Click/Payme webhook → `billing_payments` yoziladi → `subscriptions.status='active'`, `current_period_end` uzayadi → Redis kesh **darhol** yangilanadi → shu tenant bo'yicha barcha `suspended_at`/`revoked_reason='subscription'` yozuvlar **tozalanadi** (tokenlar odatdagi holatga qaytadi, qayta login shart emas — 16.1.3 va 17.2.4 bilan izchil) → kirish darhol tiklanadi.

### 16.2 Diagramma

```mermaid
sequenceDiagram
    participant SCH as Scheduler (SAQ cron)
    participant DB as subscriptions
    participant R as Redis (sub_status kesh)
    participant API as Himoyalangan endpoint
    participant Br as Brauzer/Android

    Note over DB: grace_ends_at <= now(), status='grace'
    SCH->>DB: UPDATE subscriptions SET status='restricted'
    SCH->>DB: shu tenant bo'yicha barcha sessions/refresh_tokens — revoke
    SCH->>R: SET sub_status:{tenant_id} = restricted
    SCH->>SCH: outbox_jobs: Telegram/SMS ogohlantirish (M18)

    Br->>API: istalgan so'rov (yoki heartbeat GET /auth/session)
    API->>R: sub_status:{tenant_id}?
    R-->>API: restricted
    API-->>Br: 403 {code: SUBSCRIPTION_RESTRICTED}
    Br->>Br: /login?reason=subscription_expired ga yo'naltirish

    Note over Br: Egasi Click/Payme orqali to'laydi
    Br->>API: to'lov webhook orqali tasdiqlanadi
    API->>DB: subscriptions.status='active', current_period_end uzaytiriladi
    API->>R: SET sub_status:{tenant_id} = active
    Br->>API: POST /oauth/token (qayta login)
    API-->>Br: access_token — kirish darhol tiklanadi
```

### 16.3 Fiskal oqibat (qisqa qayd)

Kassa to'liq to'xtagach **chek chiqarib bo'lmaydi** — bu holatda savdo davom ettirilmasligi kerak (chekssiz sotuv — alohida huquqiy xavf). Bu **do'konning mas'uliyati**: foydalanish shartlarida (Terms of Service) aniq yozilishi kerak — "obuna muddati o'tganda tizim foydalanishni to'xtatadi; shu davrda sotuv davom ettirilsa, fiskal javobgarlik mijozning zimmasida". Bu qarorga qarshi dalil keltirilmaydi — foydalanuvchi qarori sifatida qabul qilinadi.

### 16.4 Lokautdan oldingi offline cheklarni yuborish (drain) *(2026-10-15: foydalanuvchi qarori D1 + qabul-5 K3 tuzatish)*

**Muammo**: imtiyoz davrida (lokautgacha) offline yaratilgan, lekin hali serverga yetmagan cheklar bor bo'lishi mumkin (`outbox_jobs`, Dexie/IndexedDB'da). Lokaut ularni "qamab qo'ysa" — qonuniy yaratilgan fiskal hujjat 48 soatlik muddatda (VM 943) OFD'ga yetmay qoladi, bu **bizning tizim sababli** yuzaga keladigan buzilish bo'lardi. Foydalanuvchi qarori (D1, 2026-10-15): bu **tor, aniq chegaralangan istisno** — "faqat to'lov yo'li ochiq" qoidasini buzmaydi, chunki yangi savdo/login/o'qish ochilmaydi, faqat eskirgan fiskal voqealarni drenaj qilish.

**Mexanizm**:

1. Lokautda qurilmaga bog'langan refresh tokenlar **o'chirilmaydi** — 16.1.3-bo'limdagi kabi `revoked_reason='subscription'` bilan **`suspended`** holatiga o'tadi (bitta umumiy mexanizm, O2 bilan bir xil).
2. `suspended` refresh token bilan `/oauth/token` so'rovi qilinganda AS **faqat** cheklangan scope — `scope=sync.drain` — bilan qisqa muddatli (taxmin: 5 daqiqa) access token qaytaradi. Bu token boshqa hech qanday scope so'rolsa rad etiladi.
3. `sync.drain` scope'li access token bilan **faqat** `POST /sync/push` ishlaydi, u ham faqat `created_at <= grace_ends_at` bo'lgan voqealar uchun (qurilma `seq` va `license.jti` bo'yicha server tekshiradi, §8 clamp qo'llanadi). Lokautdan **keyin** yaratilgan har qanday voqea (`created_at > grace_ends_at`) `rejected: SUBSCRIPTION_RESTRICTED` bilan rad etiladi — yangi sotuv imkonsiz. **Boshqa hech qanday endpoint** (`/sync/pull`, `GET /reports/*`, login, boshqa yozuvchi amallar) `sync.drain` token bilan ochilmaydi — 403.
4. Frontend/Android worker `SUBSCRIPTION_RESTRICTED` holatini **logout deb hisoblamaydi**: Dexie/outbox **o'chirilmaydi**, login sahifasi ko'rsatiladi (foydalanuvchi uchun UI — "obuna tugagan"), lekin fon rejimida (service worker/Android background job) drain davom etadi — qolgan offline voqealar jim yuboriladi.
5. To'lovdan keyin (16.1.5-bo'lim) `suspended` tokenlar odatdagi holatga qaytadi — endi to'liq scope bilan ishlaydi, drain alohida bosqich sifatida tugaydi (agar hali yuborilmagan voqea qolmagan bo'lsa).
6. Audit: `sync_drain_started`, `sync_drain_completed` (tenant_id, device_id, qancha voqea yuborildi) — 14-bo'limdagi ro'yxatga qo'shiladi.

```mermaid
sequenceDiagram
    participant D as Qurilma (suspended)
    participant AS as /oauth/token
    participant API as /sync/push

    D->>AS: grant_type=refresh_token (suspended refresh token)
    AS->>AS: suspended_at bor — faqat scope=sync.drain beriladi
    AS-->>D: access_token (scope=sync.drain, ~5 daqiqa)
    D->>API: POST /sync/push (voqealar, created_at <= grace_ends_at bo'lganlar)
    API->>API: scope tekshiradi: sync.drain — faqat shu turdagi voqea qabul qilinadi
    API-->>D: qabul qilindi (lokautdan keyingi voqea bo'lsa — rejected)
    Note over D: UI hamon login sahifasini ko'rsatadi; drain fonda ishlaydi
```

### 16.5 Ma'lumotlarni eksport qilish — faqat to'lov sahifasidan *(2026-10-15: foydalanuvchi qarori D2)*

**Qaror**: `restricted` holatda oddiy `/reports/export` yopiq (16.1.1, O1 tuzatish — US-M17-03'dagi avvalgi "eksport huquqi doim saqlanadi" taklifi D2 bilan **almashtirildi**). Buning o'rniga login/to'lov sahifasida alohida, tor tugma: **"Ma'lumotlarimni yuklab olish"**.

1. Foydalanuvchi `/login?reason=subscription_expired` sahifasida telefon+parol bilan tasdiqlanadi (to'liq login emas — token berilmaydi, faqat identifikatsiya).
2. Tasdiqlangandan keyin **SMS OTP** bilan qo'shimcha tasdiqlash talab qilinadi (`purpose=data_export`) — ikki faktorli, chunki bu amal to'liq tenant ma'lumotini tashqariga chiqaradi.
3. OTP tasdiqlangach, qisqa muddatli (taxmin: 15 daqiqa) bir martalik eksport havolasi beriladi (`GET /billing/export-my-data?token=...`) — Excel/CSV, mavjud `reports.export` formatiga mos.
4. **Rate limit**: tenant bo'yicha 1 marta / 24 soat (taxmin) — qayta-qayta to'liq ma'lumot bazasini yuklab olishning oldini olish uchun.
5. **Audit**: `data_export_during_restriction` (tenant_id, user_id, ip, created_at) — 14-bo'limdagi ro'yxatga qo'shiladi, `05-xavfsizlik-va-audit.md` §6.1'dagi "ma'lumot eksporti" talabining lokaut-maxsus holati.
6. Bu yo'l faqat `restricted`/`closed` holatida ko'rinadi; `active` holatda oddiy `/reports/export` (BO-09) ishlatiladi.

---

## 17. Offline litsenziya tokeni (foydalanuvchi qarori 2026-10-15)

### 17.1 Muammoning aniq ta'rifi

BFF naqshida token brauzer JS'iga chiqmaydi (3-bo'lim) — lekin veb-kassa **to'liq offline** (server bilan hech qanday aloqasiz) ishlashi kerak (8-bo'lim) va shu holatda ham obuna muddati o'tganini **mahalliy** (serversiz) bilishi kerak. Bu ikki talab orasidagi ziddiyat quyidagicha hal qilinadi: **ikki mustaqil artefakt**:

| Artefakt | Qayerda | Nima uchun | Kim ko'radi |
|---|---|---|---|
| OAuth access/refresh token | Faqat serverda (BFF), yoki Android'da Keystore'da | API chaqirish huquqi | Hech qachon oddiy JS kod/IndexedDB'da ochiq |
| **`license` token** | Qurilmada (Dexie `settings`, Android lokal fayl) | Faqat **mahalliy o'z-o'zini tekshirish** — API chaqirmaydi, huquq bermaydi | Qurilma JS/Kotlin kodi o'zi, offline ham |

`license` — **imzolangan JWT**, lekin 6-bo'limdagi access-token kalitidan **ajratilgan, alohida** kalit juftligi bilan imzolanadi (`signing_keys.purpose='license'`, o'z `kid`i, o'z rotatsiyasi — O5 tuzatish, pastda). Header `typ: "license+jwt"` (access token'ning `at+jwt`idan qat'iy farqli — RS har qanday `typ != at+jwt` yoki `aud != urn:erp:api` tokenni **avtomatik rad etadi**, shuning uchun litsenziya tokenini API chaqiruvida almashtirib ishlatish imkonsiz). Claim'lari: `iss`, `aud: "urn:erp:device-license"`, `sub=device_id`, `tenant_id`, `plan_id`, `limits` (ma'lumot uchun), `iat`, **`valid_until`** (`exp` sifatida ham takrorlanadi), `jti`, **`server_time`** (litsenziya berilgan paytdagi server soati — O3 tuzatish, pastda). Qurilma `GET /auth/license` javobida litsenziya kalitining **alohida JWKS**'ini (`/.well-known/license-jwks.json`) ham oladi va saqlaydi; eski litsenziya kaliti eng uzoq `valid_until` tugaguncha JWKS'da qoladi. *(2026-10-15: qabul-5 — O5 tuzatish)*

**Muddat qisqartirildi (O4 tuzatish)**: avvalgi `valid_until = subscription_end + 24 soat` (amalda butun obuna davri, ~30 kun) xavfsizlik nuqtai nazaridan xato edi — o'g'irlangan yoki bekor qilingan (`devices.revoked_at`) qurilma internetsiz bir oycha sotuv qila olardi, chunki bekor qilish faqat online paytda kuchga kiradi. Yangi qoida: **`valid_until = min(grace_ends_at, issued_at + 7 kun)`** (taxmin, 72 soat–7 kun oralig'ida pilotda aniqlanadi). Obuna qarori o'zgarmaydi (server obuna faol bo'lsa har sync'da litsenziyani yangilaydi) — faqat **uzoq vaqt (7 kundan ko'p) internetsiz qolgan yoki bekor qilingan** qurilma o'zini qulflaydi, bu fiskal 48 soatlik online-bo'lish talabiga ham mos (qurilma baribir ancha tez-tez onlayn bo'lishi kerak). *(2026-10-15: qabul-5 — O4 tuzatish)*

### 17.2 Oqim

1. **Jim (silent) yangilanish**: qurilma online bo'lgan har safar (sync paytida, `GET /auth/license` yoki `/sync/pull`ga biriktirilgan) — amalda **har sync tsiklida** (taxmin: har 5–15 daqiqada, 02-bandga mos) — yangi `license` oladi, eskisini almashtiradi; foydalanuvchidan hech narsa so'ralmaydi. Shu sababli 7 kunlik muddat amaliyotda doim "yangilanib turadi" — faqat uzoq (>7 kun) offline qolganda haqiqiy chegara ishga tushadi.
2. Qurilma (web-kassa service worker / Android) har ilova ochilganda va davriy (taxmin: har 5 daqiqada) + har yangi outbox yozishdan oldin: lokal keshlangan **litsenziya JWKS** (yuqoridagi, access-token JWKS'idan alohida) bilan imzoni tekshiradi (JS/Kotlin kodini o'zgartirmasdan soxtalashtirib bo'lmasligi uchun — IndexedDB qiymatini qo'lda tahrirlash endi yetarli emas, imzo buziladi) va `now <= valid_until`ni tekshiradi.
3. Muddat o'tgan bo'lsa — qurilma **o'zi** (serversiz) yangi sotuv/amalni bloklaydi, "Obuna muddati tugagan" xabarini ko'rsatadi; ekranlar yopiladi (D2/O1 bilan izchil — ko'rish/eksport **ochiq qolmaydi**), faqat sinxronlanmagan outbox saqlanadi va internet qaytganda 16.4-bo'lim (drain) bo'yicha yuboriladi; ma'lumot eksporti faqat 16.5-bo'limdagi to'lov-sahifa yo'li orqali. *(2026-10-15: qabul-5 — O1/D2 tuzatish)*
4. To'lov qilinganda, qurilma keyingi onlayn bo'lishida **`suspended` refresh token odatdagi holatga qaytgani uchun** (16.1.3/16.1.5-bo'lim, O2 tuzatish) yangi (uzaytirilgan `valid_until`) litsenziya oladi va **darhol** qayta ishlay boshlaydi — qayta login (parol) shart emas, kassir PIN bilan davom etadi. *(2026-10-15: qabul-5 — O2 tuzatish)*
5. **Soatni orqaga surishdan himoya (qurilmada)** *(2026-10-15: qabul-5 — O3 tuzatish)*: avvalgi yechim (`04-offline-sync.md` §8 clamp) **serverda**, sinxronlash paytida ishlaydi — bu offline qurilmada foydasiz, chunki qurilma soatini orqaga surish `now <= valid_until` tekshiruvini cheksiz aylanib o'tishga imkon berardi. Yangi qoida — **qurilmaning o'zida**: qurilma litsenziya bilan birga olingan `server_time`ni doimiy saqlaydi va har tekshiruvda `last_trusted_time = max(last_trusted_time, now, server_time)` yangilanadi (monoton — faqat o'sadi, hech qachon kamaymaydi). Agar qurilma soati (`now`) `last_trusted_time − 10 daqiqa` (taxmin)dan kichik bo'lsa — soat orqaga surilgan deb hisoblanadi, qurilma bloklanadi ("Qurilma soatini to'g'rilang va internetga ulaning"). Android'da qo'shimcha signal — `SystemClock.elapsedRealtime()` (qayta ishga tushirishlar orasida monoton, tizim soatidan mustaqil) + qurilma qayta yuklanishlar soni, ikkisi orasidagi mos kelmaslik qo'shimcha signal beradi. Server sinxronlashda hamon §8 clamp'ini qo'llaydi (ikkinchi, mustaqil qatlam). Veb-kassada bu himoya JS darajasida — qasddan o'zgartirilgan brauzerga qarshi qat'iy kafolat emas, faqat oddiy soat-orqaga-surish stsenariysidan himoya (qaror shuni ongli ravishda qabul qiladi).

---

## 18. Admin panel (foydalanuvchi qarori 2026-10-15)

### 18.1 Platforma admin (bizning jamoa) — `platform_admins`

**Izolyatsiya** *(2026-10-15: qabul-5 — O8 tuzatish)*: avvalgi dizaynda `platform_admins` jadvalida parol/MFA ustuni yo'q edi (haqiqiy kredensial qayerdan kelishi aniqlanmagan), `aud` claim tenant API bilan bir xil (`urn:erp:api`) edi va `/admin/*` prefiksi tenant Egasining o'z `/admin/users` yo'li bilan bir xil nom edi — bu barcha tenantga RLS bypass huquqi bo'lgan rol uchun yetarli emas. Yangi dizayn:

- `platform_admins` (id, **`user_id` → `users`**, role, **`mfa_secret_encrypted`**, **`allowed_ips`** (ixtiyoriy, CIDR ro'yxati)) — platforma admini oddiy `users` hisobiga bog'lanadi (parol — `user_credentials.password_hash`, boshqa foydalanuvchilar bilan bir xil argon2id), lekin `admin-bff` login'da **majburiy ikkinchi faktor — TOTP** (taxmin; kelajakda WebAuthn) talab qilinadi; `allowed_ips` berilgan bo'lsa, shundan tashqari IP'dan login rad etiladi.
- Admin token: `aud: "urn:erp:platform"` (tenant API'nikidan — `urn:erp:api` — **qat'iy farqli**), `scope: platform.admin`, **`tenant_id`siz**. Tenant API'lari `aud=urn:erp:platform` tokenni avtomatik rad etadi, va aksincha — platforma endpoint'lari `aud=urn:erp:api` tokenni rad etadi.
- Platforma endpoint'lari **`/platform/*`** prefiksida (tenant Egasining `/admin/users` bilan endi aralashmaydi).
- `admin-bff` — alohida `client_id` (mavjud), access token muddati **5 daqiqa** (taxmin, tenant tokenidan qisqa — yuqori huquqli rol), refresh — **8 soat mutlaq** (sliding yo'q — har smena boshida qayta login).

Mavjud ADM-01 (`04-ekranlar-va-ux.md`) ustiga qo'shiladi:

| Ekran/bo'lim | Nima qiladi |
|---|---|
| Tenantlar ro'yxati (mavjud) | Obuna holati, to'lov tarixi, AI sarfi, faol kassalar |
| **"Xavfsizlik" tab (yangi)** | Tenant bo'yicha faol sessiya/qurilmalar soni (faqat ko'rish), **"Barcha sessiyalarni tugatish"** tugmasi (insident javobi uchun, `05-xavfsizlik-va-audit.md` §10) |
| Obuna muddatini qo'lda uzaytirish (mavjud) | Pilot do'konlar uchun |
| **"Egasi hisobi" bo'limi (yangi)** *(2026-10-15: qabul-5 — O9 tuzatish, US-M13-08)* | Egasi a'zoligini bloklash/blokdan chiqarish, parolini SMS orqali tiklash, sessiyalarini ko'rish/bekor qilish — **faqat Egasi hisobiga tegishli**, oddiy xodimlar (Kassir/Menejer/Buxgalter) ma'lumotiga platforma admini kirmaydi |

API'lar:

| Endpoint | Vazifa |
|---|---|
| `GET /platform/tenants` | Ro'yxat, filtr (holat, tarif) |
| `GET /platform/tenants/{id}` | Tafsilot: obuna, to'lov, AI sarfi, qurilmalar |
| `POST /platform/tenants/{id}/extend-subscription` | Muddatni qo'lda uzaytirish |
| `POST /platform/tenants/{id}/revoke-all-sessions` | Insident javobi — tenant bo'yicha barcha sessiya/token bekor |
| `GET /platform/tenants/{id}/ai-usage` | AI sarfi |
| **`POST /platform/tenants/{id}/owner/block`, `/unblock`** *(O9, US-M13-08)* | Egasi a'zoligini bloklash/blokdan chiqarish (bloklashda sessiyalar bekor) |
| **`POST /platform/tenants/{id}/owner/reset-password`** *(O9, O10)* | Egasiga SMS orqali bir martalik tiklash havolasi/OTP yuboriladi (`purpose=admin_reset`) — **hech qachon parol matni emas** |
| **`GET /platform/tenants/{id}/owner/sessions`, `POST …/owner/sessions/{sid}/revoke`** *(O9)* | Egasi sessiyalari — ko'rish va bekor qilish |

Barcha amallar `audit_log`ga `platform_admin_access` turi bilan (mavjud qoida, `05-xavfsizlik-va-audit.md` §3.4).

### 18.2 Tenant Egasi — xodimlar boshqaruvi (BO-11)

Mavjud BO-11 ("Foydalanuvchilar va huquqlar" + "Qurilmalar" tab) ustiga **ikki aniq amal** qo'shiladi:

| Amal | Ekran | API |
|---|---|---|
| Xodim qo'shish/bloklash (mavjud) | BO-11 | `POST /admin/users`, `PATCH /admin/users/{id}` (`status`) — **`status='blocked'` qo'yilganda shu foydalanuvchining barcha `sessions`/`refresh_tokens` oilasi darhol revoke qilinadi + Redis `sid`-revoke keshi yangilanadi** (US-M13-05 talabi, keyingi so'rov emas — hozir). *(2026-10-15: qabul-5 — KICHIK 7 tuzatish)* |
| Rol/filial tayinlash (mavjud) | BO-11 | `PATCH /admin/users/{id}` (`role_ids`, `branch_ids`) — tayinlashdan keyin foydalanuvchining `sid`i "claims stale" deb belgilanadi (5-bo'lim, KICHIK 10) |
| **PIN'ni qayta o'rnatish (yangi)** | BO-11, xodim qatoridagi "PIN'ni qayta o'rnatish" tugmasi | `POST /admin/users/{id}/reset-pin` — eski `pin_hash` bekor, xodim keyingi kirishda yangi PIN o'rnatishga majburlanadi (`04-offline-sync.md` §9'dagi qurilma-bekor-qilish PIN majburiy almashtirish bilan bir xil naqsh); `otp_challenges.purpose='pin_reset'` (4.2-bo'lim) |
| **Parolni tiklash (Egasi tomonidan)** *(2026-10-15: qabul-5 — O10 tuzatish)* | BO-11, xodim qatoridagi "Parolni tiklash" tugmasi | `POST /admin/users/{id}/reset-password` — eski `password_hash` bekor qilinadi, barcha sessiya/refresh-token oilasi revoke qilinadi, xodimga SMS orqali **bir martalik tiklash kodi** (`purpose=admin_reset`) yuboriladi; xodim kod bilan o'zi yangi parol o'rnatadi — **parol hech qachon SMS'da ochiq matnda yuborilmaydi** |
| **Sessiya/qurilmalarni bekor qilish (yangi)** | BO-11, xodim qatoridagi "Seanslarni tugatish" tugmasi | `POST /admin/users/{id}/revoke-sessions`, `GET /admin/users/{id}/sessions`, `GET /admin/users/{id}/devices` |

Bu amallar `settings.users` ruxsat kodi ostida (mavjud, `05-xavfsizlik-va-audit.md` §2.1), **faqat Egasi** — "(va vakolatli Menejer)" degan avvalgi eslatma olib tashlandi, chunki `05-xavfsizlik-va-audit.md` §2.2 standart matritsasida `settings.users` faqat Egasida (KICHIK 7 tuzatish; agar kelajakda Menejerga ham berilsa, bu ikki hujjat birgalikda yangilanadi). `user_credentials`ga `must_change_password`, `must_change_pin` bool ustunlari qo'shiladi (19-bo'lim) — `admin_reset`/`pin_reset` OTP tasdiqlanganda `true`, yangi kredensial o'rnatilganda `false`.

---

## 19. Ma'lumotlar bazasi jadvallari

`01-malumotlar-modeli.md`ga qo'shiladigan/o'zgartiriladigan yangi jadvallar (ustunlar — asosiylari, to'liq ro'yxat emas):

| Jadval | Asosiy ustunlar | Izoh |
|---|---|---|
| `users` (mavjud, tozalanadi) | id, phone (unique), name, locale | Parol/PIN heshlari `user_credentials`ga ko'chirildi *(2026-10-15: qabul-5 — KICHIK 11, imlo/atama tuzatildi)* |
| `user_credentials` (**yangi**) | user_id (PK/FK), password_hash, password_algo, password_updated_at, pin_hash, pin_updated_at, failed_login_count, locked_until, **must_change_password**, **must_change_pin** | Sirlarni `users`dan ajratish — oddiy ro'yxat so'rovida heshlar oshkor bo'lmasin. Oxirgi ikki ustun — `admin_reset`/`pin_reset`/`invite` OTP tasdiqlangandan keyin `true`, yangi kredensial o'rnatilganda `false` (O10 tuzatish, 18.2-bo'lim) |
| `memberships` (mavjud) | — | O'zgarmaydi |
| `oauth_clients` (**yangi**) | id, client_id, client_type (`confidential`/`public`), name, client_secret_encrypted (null=public), redirect_uris[], allowed_grant_types[], allowed_scopes[] | 2-bo'limdagi 4 mijoz shu yerda ro'yxatga olinadi |
| `authorization_codes` (**yangi**) | code_hash, client_id, user_id, tenant_id, code_challenge, code_challenge_method, redirect_uri, scope, expires_at (60s), used_at | Bir martalik |
| `refresh_tokens` (**yangi**) | id, token_hash, family_id, client_id, user_id, tenant_id, device_id (null), scope, issued_at, expires_at, used_at, replaced_by_id, revoked_at, **revoked_reason**, **suspended_at** | 7-bo'lim. `suspended_at` — `revoked_at`dan **farqli**: `revoked_reason='subscription'` bilan birga qo'yiladi (16.1.3-bo'lim), to'liq bekor qilish emas, faqat `scope=sync.drain`ga toraytiradi (16.4-bo'lim); to'lovdan keyin tozalanadi (`NULL`) — token qayta yaratilmaydi *(2026-10-15: qabul-5 — K3/O2 tuzatish)* |
| `sessions` (**yangi**) | id (=`sid`), user_id, tenant_id, client_id, device_id (null), current_refresh_token_id, created_at, last_seen_at, idle_expires_at, absolute_expires_at, revoked_at, revoked_reason, ip, user_agent | BFF cookie shu yozuvga ishora qiladi |
| `signing_keys` (**yangi**) | kid, algorithm, **purpose** (`access`/`license`), public_key, private_key_encrypted, status (`next`/`active`/`retired`), created_at, activated_at, retired_at | 6-bo'lim va 17.1-bo'lim. `purpose` ustuni **yangi** — access token va litsenziya tokeni endi **alohida** kalit juftligi bilan imzolanadi, aralashmasligi uchun (O5 tuzatish) *(2026-10-15: qabul-5)* |
| `otp_challenges` (**yangi**) | id, phone, purpose (`signup`/`recovery`/**`invite`**/**`admin_reset`**/**`pin_reset`**/**`data_export`**), code_hash, attempts, max_attempts, expires_at, verified_at | 4.2-bo'lim, 16.5-bo'lim. Qiymatlar ro'yxati kengaytirildi *(2026-10-15: qabul-5 — O10 tuzatish)* |
| `login_attempts` (**yangi**) | id, phone, ip, success, failure_reason, created_at | Qisqa saqlash (90 kun, taxmin) — `audit_log`dan farqli, yuqori hajm |
| `license_tokens` (**yangi**) | id, tenant_id, device_id, issued_at, valid_until, jti, **server_time** | 17-bo'lim — server tomoni bookkeeping, haqiqiy artefakt qurilmada. `server_time` — litsenziya berilgan paytdagi server soati (O3, qurilma `last_trusted_time` hisoblashi uchun) |
| `devices` (mavjud, **o'zgartiriladi**) | tenant_id, cash_register_id, kind (`web`/`android`), revoked_at, revoked_by, last_seen_at, last_sync_at, app_version | `token_hash`/`token_expires_at` **olib tashlanadi** — endi `refresh_tokens.device_id`/`license_tokens.device_id` orqali bog'lanadi. **Veb-kassa endi ham `devices` yozuviga ega** (faqat litsenziya tokeni uchun — to'g'ridan-to'g'ri API chaqirmaydi, hamon cookie+BFF); faqat Android to'g'ridan-to'g'ri Bearer bilan API chaqiradi. *(2026-10-15: foydalanuvchi qarori)* |
| `platform_admins` (mavjud, **o'zgartiriladi**) | id, **user_id** (→ `users`), role, **mfa_secret_encrypted**, **allowed_ips** | O8 tuzatish — kredensial endi `user_id` orqali `user_credentials`dan keladi, MFA majburiy *(2026-10-15: qabul-5)* |

**RLS** *(2026-10-15: qabul-5 — O7 tuzatish, "standart tenant_id RLS" texnik jihatdan noto'g'ri edi)*: `user_credentials` (foydalanuvchi global, hali tenant tanlanmagan bo'lishi mumkin), `otp_challenges` (ro'yxatdan o'tishda tenant hali yo'q), `login_attempts` (phone/ip — tenant kontekstidan tashqari), `authorization_codes`/`refresh_tokens`/`sessions` (tenant kontekstidan **oldin** `code_hash`/`token_hash` bo'yicha qidiriladi) — bu jadvallarda oddiy `tenant_id` RLS **ishlamaydi yoki AS'ni sindiradi** (login paytida `app.tenant_id` hali o'rnatilmagan). Shuning uchun: `oauth_clients`, `signing_keys` — platforma darajasida global (`plans`/`units` kabi istisno, faqat SELECT ilova roliga). **`user_credentials`, `otp_challenges`, `login_attempts`, `authorization_codes`, `refresh_tokens`, `sessions`** — **auth-sxema jadvallari**: alohida PostgreSQL `auth` sxemasida, ilova (`app`) roliga to'g'ridan-to'g'ri `SELECT`/`INSERT`/`UPDATE` ruxsati **yo'q**, kirish faqat `SECURITY DEFINER` funksiyalar orqali (`auth_find_user(phone)`, `auth_consume_code(code_hash)`, `auth_rotate_refresh(token_hash)`, `auth_revoke_tenant(tenant_id)`, `auth_suspend_tenant(tenant_id)` — 16.1.3 uchun, va h.k.) — bu funksiyalar o'z ichida kerakli `tenant_id`/`user_id` tekshiruvini bajaradi. **`license_tokens`** — bu alohida: tenant/qurilma konteksti login'dan **keyin** mavjud, shuning uchun standart `tenant_id` RLS siyosati qo'llaniladi. CI RLS testi (`05-xavfsizlik-va-audit.md` §3.3) auth-sxema jadvallarini **istisno** sifatida (RLS o'rniga SECURITY DEFINER funksiya qamrovi tekshiriladi), `license_tokens`ni esa **standart** ro'yxatda tekshiradi.

---

## 20. API endpoint ro'yxati

| Endpoint | Metod | Qatlam | Vazifa |
|---|---|---|---|
| `/.well-known/oauth-authorization-server` | GET | AS | RFC 8414 metadata |
| `/.well-known/jwks.json` | GET | AS | Ochiq kalitlar |
| `/oauth/authorize` | GET/POST | AS | Kod berish, birinchi-tomon login shaklini ko'rsatadi/qayta ishlaydi |
| `/oauth/token` | POST | AS | `authorization_code`/`refresh_token`/`client_credentials` |
| `/oauth/revoke` | POST | AS | RFC 7009 |
| `/oauth/introspect` | POST | AS | RFC 7662 (faqat confidential mijozlar) |
| `/auth/login` | POST | BFF | Telefon+parol → ichki kod+token almashinuvi → cookie |
| `/auth/signup` | POST | BFF | **(2026-10-15: qabul-6 — A-01)** `{phone, otp_challenge_id (purpose=signup, verified), password, store_name, business_type}` → bitta tranzaksiyada `05-xavfsizlik-va-audit.md` §1.5 provisioning (tenant, `subscriptions(status=trial, 30 kun)`, Egasi membership, 5 rol, standart filial/ombor/kassa, `doc_sequences`, standart xarajat toifalari) + login cookie; xatolar `OTP_INVALID`, `VALIDATION_ERROR` (telefon allaqachon ro'yxatda), `RATE_LIMITED` |
| `/auth/otp/request` | POST | BFF/AS | Signup/recovery OTP yuborish |
| `/auth/otp/verify` | POST | BFF/AS | OTP tasdiqlash |
| `/auth/logout` | POST | BFF | Joriy sessiya bekor, cookie tozalanadi |
| `/auth/sessions/revoke-all` | POST | BFF | O'z-o'zini — "barcha seanslarimni tugat" |
| `/auth/pin/verify` | POST | RS | Online PIN tasdiqlash (4.3-bo'lim) |
| `/auth/session` | GET | BFF | "Men kimman" + heartbeat (16.1-bo'lim) |
| `/auth/license` | GET | RS | Offline litsenziya tokenini olish (17-bo'lim) |
| `/billing/pay` | GET | BFF | To'lov sahifasi yo'li — `SUBSCRIPTION_RESTRICTED` holatida ham ochiq (16.1.1-bo'lim) |
| `/billing/checkout` | POST | BFF/RS | **(2026-10-15: qabul-6 — B-02/Z-01, 16.1.1a)** `active`/`grace`da oddiy sessiya; `restricted`/`closed`da `pay_token` (`Authorization: PayToken ...`) bilan — ikkisida ham lokaut ro'yxatida ochiq, aks holda tenant to'lov qila olmay qoladi |
| `GET /billing/plan`, `/subscription`, `/addons`, `/payments` | GET | BFF/RS | Lokaut holatida ham ochiq (o'qish, 16.1-bo'lim) |
| `/billing/webhooks/{provider}` | POST | RS | Provayder imzosi bilan, sessiyadan mustaqil — lokautda ham ochiq |
| `/billing/export-my-data` | POST/GET | BFF | Login+SMS OTP tasdiqlangandan keyin bir martalik eksport havolasi (16.5-bo'lim, D2 qarori) |
| `/platform/tenants...` | GET/POST | RS (platform, `aud=urn:erp:platform`) | 18.1-bo'lim *(2026-10-15: qabul-5 — O8 tuzatish, avvalgi `/admin/tenants` dan ko'chirildi)* |
| `/platform/tenants/{id}/owner/...` | GET/POST | RS (platform) | US-M13-08, Egasi hisobi boshqaruvi (18.1-bo'lim, O9 tuzatish) |
| `/admin/users...` | GET/POST/PATCH | RS (tenant) | 18.2-bo'lim |
| `/admin/users/{id}/reset-password` | POST | RS (tenant) | Egasi tomonidan xodim parolini tiklash — `admin_reset` OTP (18.2-bo'lim, O10 tuzatish) |

---

## 21. Xavfsizlik test rejasi — mock yo'q

Vazifa talabi: **hech qanday mock** — haqiqiy PostgreSQL va Redis (`testcontainers`, `09-backend-arxitekturasi.md` §6'dagi mavjud strategiya bilan izchil). Vaqt (soat) uchun boshqariladigan klok (`pendulum` orqali in-process inject qilinadi) ishlatiladi — bu I/O mock emas, haqiqiy real vaqtni kutib o'tirmaslik uchun standart texnika.

| Test | Tekshiradi |
|---|---|
| To'liq Authorization Code+PKCE oqimi | `code_verifier`/`code_challenge` mos kelmasa rad; `redirect_uri` mos kelmasa rad; kod bir martalik (ikkinchi marta ishlatilsa rad) |
| Refresh rotatsiyasi | Bir marta ishlatilgan RT yangi RT beradi; eski RT qayta kelsa — butun oila bekor, keyingi legitim refresh ham endi muvaffaqiyatsiz |
| Revoke | `/oauth/revoke` dan keyin shu `sid`li, hali `exp`i tugamagan JWT bilan so'rov rad etiladi (Redis `sid`-revoke tekshiruvi orqali, nafaqat `exp`) |
| Introspect | Revoke'dan keyin `active: false` |
| **Obuna lokaut** | `grace` → `restricted` o'tganda: (a) refresh so'rovi rad etiladi (`sync.drain`dan tashqari), (b) hali amal qiladigan eski access token bilan so'rov Redis kesh orqali rad etiladi, (c) to'lov kelgach kesh darhol yangilanadi va login muvaffaqiyatli bo'ladi |
| **Lokaut drain (16.4-bo'lim)** *(2026-10-15: qabul-5)* | `suspended` refresh token faqat `scope=sync.drain` access token oladi; shu token bilan `created_at <= grace_ends_at` voqea qabul qilinadi, undan keyingisi rad etiladi; boshqa endpoint (masalan `/sync/pull`, `GET /reports`) shu token bilan 403; to'lovdan keyin `suspended_at` tozalanadi va token odatdagi scope bilan ishlaydi |
| **Parallel refresh (7-bo'lim, K4)** *(2026-10-15: qabul-5)* | Bitta `sid` uchun 5 ta parallel refresh so'rovi — sessiya saqlanadi (single-flight); uzilgan javobdan keyin RT1 takrori (≤30 soniya, RT2 ishlatilmagan) — oila bekor bo'lmaydi; oynadan tashqari takror — oila bekor bo'ladi |
| Brute-force | N+1 xato login progressiv bloklashni ishga tushiradi (haqiqiy Redis counter); (telefon, IP) juftligi bo'yicha — boshqa IP'dan to'g'ri parol bilan kirish bloklanmaydi (KICHIK 8) |
| Qurilma bekor qilish | `devices.revoked_at` o'rnatilgach, shu qurilmaning refresh/access tokenlari rad etiladi, PIN majburiy almashtiriladi |
| **Litsenziya tokeni** *(2026-10-15: qabul-5 — O5 tuzatish)* | `license` tokeni access-token JWKS bilan tasdiqlanmaydi (boshqa `kid`/`purpose`); `typ != at+jwt` bo'lgan litsenziya tokeni API endpoint'ida rad etiladi; `valid_until` muddati tugagach qurilma mahalliy bloklanadi; online bo'lganda jim yangilanadi |
| **Platforma admin MFA** *(2026-10-15: qabul-5 — O8 tuzatish)* | TOTP kodi noto'g'ri bo'lsa login rad etiladi; `aud=urn:erp:platform` token bilan tenant API so'rovi 403, va aksincha |
| **Tenant almashtirish (9-bo'lim, KICHIK 6)** *(2026-10-15: qabul-5)* | Tenant almashtirilganda eski `sid`/refresh-token oilasi bekor bo'ladi; bitta cookie bilan ikki tenant parallel ishlay olmaydi |
| RLS | Yangi jadvallar (19-bo'lim) `05-xavfsizlik-va-audit.md` §3.3'dagi "har jadvalda RLS" CI testiga kiradi; cross-tenant leak testi. Auth-sxema jadvallari (O7) — `SECURITY DEFINER` funksiya qamrovi alohida tekshiriladi |
| Kalit rotatsiyasi | Eski `kid` bilan imzolangan token rotatsiyadan keyin ham retirement oynasi ichida tasdiqlanadi; yangi tokenlar yangi `kid` bilan; JWKS ikkisini ham ko'rsatadi overlap davrida |

---

## Ochiq savollar

1. Access token aniq muddati (10–15 daqiqa oralig'ida qaysi son) — taxmin 12 daqiqa, yuklama/UX sinovida aniqlanadi.
2. Qurilmaga bog'langan refresh token aniq muddatlari (sliding 14/mutlaq 180 kun) — taxmin, pilotda tasdiqlanadi.
3. Imzolash kaliti rotatsiya chastotasi (90 kun) — taxmin, aniq siyosat yo'q.
4. Obuna lokaut holatida "zudlik" uchun heartbeat/WebSocket-SSE "majburiy chiqish" kanali kerakmi — MVP'da oddiy keyingi-so'rov+ixtiyoriy heartbeat yetarli deb taxmin qilindi, kelajakda kuchaytirilishi mumkin.
5. SMS provayder tanlovi (OTP yetkazish) — hali ochiq (`spec/tekshiruv/00-qarorlar.md` va `02-modullar-talablari.md`dagi mavjud ochiq savol bilan bog'liq, bu yerda qaytarilmaydi).
6. argon2id aniq parametrlari (m/t/p) — OWASP tavsiyasi asosida taxmin, ishga tushirish oldidan load-test bilan tasdiqlanadi.
7. ~~Telegram bot — har foydalanuvchi uchun alohida scope'langan token kerak bo'lishi.~~ **Qisman yopildi** *(2026-10-15: qabul-5 — K5 tuzatish)*: `telegram_links` + Client Credentials naqshi saqlanadi, lekin endi har bot so'rovida `require_subscription_ok`/`memberships.status`/`require_permission` **majburiy qayta tekshiriladi** (2-bo'lim). Agar kelajakda botdan to'g'ridan-to'g'ri yozuvchi amal (masalan sotuv yaratish) qo'shilsa — alohida foydalanuvchi-darajasidagi token modeli qayta ko'rib chiqilishi kerak, hozircha o'qish/javob darajasidagi funksiyalar (AI-01, hisobot, obuna eslatmasi) uchun yetarli.
8. Platforma admin panelining o'z BFF'si (`admin-bff`) bilan asosiy `web-bff`dan to'liq alohida deploy qilinishi kerakmi (qo'shimcha izolyatsiya) — arxitektura qarori ochiq, hozircha bir xil backend, alohida `client_id`/scope bilan yetarli deb taxmin qilindi.
9. WebAuthn/biometrik parolsiz kirish — vazifada so'ralmagan, kelajakdagi kengaytma sifatida qoldirildi.
10. `license_tokens` jadvalining saqlash muddati va tozalash siklida aniq son — taxmin, boshqa operatsion jadvallar bilan bir xil siyosat (masalan 30–90 kun) qo'llanishi mumkin.

## Manbalar

- `spec/02-arxitektura/00-umumiy-arxitektura.md`, `01-malumotlar-modeli.md`, `05-xavfsizlik-va-audit.md`, `04-offline-sync.md`, `08-frontend-arxitekturasi.md`, `09-backend-arxitekturasi.md`.
- `spec/01-mahsulot/02-modullar-talablari.md` (M13, M17 — US-M17-03), `04-ekranlar-va-ux.md` (BO-11, BO-21, ADM-01).
- `spec/tekshiruv/00-qarorlar.md` (#3 veb-kassa autentifikatsiyasi, #4 CSRF, #13 obuna holati).
- RFC 6749 (OAuth 2.0), RFC 7636 (PKCE), RFC 7009 (Token Revocation), RFC 7662 (Token Introspection), RFC 8414 (Authorization Server Metadata), RFC 9068 (JWT Profile for OAuth 2.0 Access Tokens), RFC 8252 (OAuth 2.0 for Native Apps).
- Authlib (https://authlib.org), joserfc — kutubxona tanlovi asosi.
- Foydalanuvchi qarori, 2026-10-15 (shu suhbat) — autentifikatsiya arxitekturasining asosiy manbai.
