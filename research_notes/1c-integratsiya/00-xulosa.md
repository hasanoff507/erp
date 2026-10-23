# 1C integratsiyasi — yakuniy xulosa (asoschi uchun)

**Maqsad:** `01`–`06` tadqiqot fayllarini bitta izchil tavsiyaga keltirish: kun/smena oxirida ERP'dagi sotuv va boshqa hujjatlarni do'konning o'z kompyuteridagi 1C bazasiga ketma-ket yozish.
**Kim uchun:** asoschi (qaror qabul qilish), keyin spec muallifi (`spec/kod-uchun/` ga ko'chirish).
**Bog'liq fayllar:** shu papkadagi `01`–`06`; `research_notes/sonar-1c-integratsiya/00-xulosa.md`; `spec/kod-uchun/01-qarorlar.md` (#26, #28, #30, #31, #36), `12`, `13`, `15`, `16`, `17`, `21`, `27`.
**Holat:** accept gate xulosasi, 2026-10-15. Spec emas. Hech narsa publish qilinmagan. **Bu fayl boshqa R-fayllar bilan farq qilsa — shu fayl ustun.**

---

## 1. Qisqa javob

Do'kon kompyuteriga (1C o'rnatilgan, buxgalter yoki egasi ishlaydigan PK) kichik **«ERP 1C Agent»** dasturi o'rnatiladi. U bulutimizga faqat o'zi chiqadi (HTTPS 443, pull), 1C bazasiga esa 1C'ning o'z **COM tashqi ulanishi** (`V83.COMConnector`) orqali ulanadi — 1C'da hech narsa publish qilinmaydi, kengaytma o'rnatilmaydi, port ochilmaydi. Kun yopilganda server shu kunning **preview**ini quradi: har kassa uchun bitta «Отчет о розничных продажах» (ОРП), qarzga sotuvlar uchun «Реализация», kirimlar, qaytarishlar, kassa hujjatlari. Egasi yoki Buxgalter BO'da ko'rib **«1C ga yuborish»** tugmasini bosadi; agent hujjatlarni qat'iy tartibda yozadi va **o'tkazadi** (1C o'z provodkasi va tannarxini o'zi hisoblaydi), har birini qayta o'qib ERP jamlari bilan solishtiradi. Har 1C hujjatiga ERP o'zi bergan deterministik GUID qo'yiladi — qayta yuborish hech qachon dublikat yaratmaydi, kech kelgan offline chek esa o'sha hujjatni yangilaydi.

## 2. Yakuniy arxitektura

```
 ERP bulut (FastAPI, modul onec_integration)                Do'kon PK (Windows, NAT ortida)
 ┌───────────────────────────────────────────┐            ┌────────────────────────────────────┐
 │ BO-23 "1C ga yuborish"  BO-22 sozlamalar   │            │ ErpOneCAgent.exe (per-user, tray,  │
 │   │ preview → approve (onec.export.approve)│            │  admin huquqisiz, DPAPI sirlar)    │
 │   ▼                                        │  HTTPS 443 │   │ stdin/stdout JSON               │
 │ onec_export_batches/items  ──► dispatcher ─┼─◄─ poll ───┤   ▼                                 │
 │ onec_agent_tasks (Ed25519 imzoli vazifa)   │── task ───►│ OneCWorker.x86.exe / .x64.exe      │
 │ onec_object_refs (GUID daftari)            │◄─ result ──┤   │ COM in-proc (V83.COMConnector) │
 │ OAuth AS: device grant + private_key_jwt   │            │   ▼                                 │
 │ SAQ: build_batch, lease_sweeper, drift     │            │ 1C bazasi (File=… yoki Srvr=;Ref=)  │
 └───────────────────────────────────────────┘            └────────────────────────────────────┘
        kiruvchi ulanish YO'Q · OData YO'Q · 1C'da publish/kengaytma YO'Q
```

- **"Aqlli server, sodda agent":** qaysi 1C hujjatiga qaysi maydon yozilishini server **profili** (`bp30_uz` …) hal qiladi va deklarativ `OpSpec` yuboradi; agent faqat bajaradi (`04` §3.1).
- **Agent texnologiyasi (standart):** C# / .NET Framework 4.8 — supervisor + x86/x64 COM worker; biznes mantiq serverda Python'da (`04` §2.1). Python/pywin32 — muqobil (savol 1).
- **Ishga tushirish:** Windows xizmati emas, foydalanuvchi sessiyasidagi tray ilova (litsenziya bo'lishish, ulangan disklar, DPAPI, UI) (`01` §3.2, `04` §2.3).
- **Ulash:** RFC 8628 device code (BO-22'da kod kiritiladi) + doimiy `private_key_jwt`; 1C paroli faqat PK'da (DPAPI), serverga hech qachon chiqmaydi (`04` §2.4–2.5).

## 3. Kunlik eksport oqimi

**Foydalanuvchi ko'zi bilan:**
1. Kassir smenani yopadi (POS-07). Oxirgi smena yopilgach Egasi/Buxgalterga Telegram: «15-okt eksporti tayyor — ko'rib tasdiqlang».
2. BO-23 ochiladi: tayyorlik checklisti (smenalar yopilgan, kassalar sinxronlangan, agent onlayn, moslanmagan tovar yo'q), preview jadvali («1C'da 4 hujjat: ОРП Kassa-1, ОРП Kassa-2, Поступление №…, Реализация …»), jami «ERP 45 230 000.00 = 1C ga 45 230 000.00».
3. «1C ga yuborish» → tasdiq modali → progress (har hujjat: kutilmoqda / yozilmoqda / ✓ № 0000123 / ✗ xato + maslahat).
4. Yashil banner + Telegram «1C ga 4 hujjat yozildi ✓». Buxgalter 1C'da hujjatlarni `ERP integratsiya` foydalanuvchisi nomidan, izohida `ERP #…` bilan ko'radi.

**Tizim ko'zi bilan:**
1. `shift.closed` → `readiness` tekshiruvi (`04` §3.5) → `build_batch`: ERP agregatlari → `onec_export_items` (har biriga `OpSpec`, GUID, kutilgan jamlar) → `preview` (+ `preview_hash`).
2. Moslanmagan havola bo'lsa → `blocked`, «Moslash» tugmasi.
3. `approve` (ruxsat + xesh) → `queued`; dispetcher eng kichik `(sana, phase, seq)` itemni lease qiladi, vazifa Ed25519 bilan imzolanadi, long-poll uyg'otiladi.
4. Agent: imzo/`base_id`/muddat/«yozishga ruxsat» qulfi → worker → COM `Connect` → `upsert` algoritmi (`04` §5.3): GUID bo'yicha bor-yo'qligi → yaratish (`УстановитьСсылкуНового`) yoki yangilash (kontent xeshi, `ВерсияДанных`) → `Записать(Проведение, Неоперативный)` → qayta o'qish (Номер, Проведен, summa, QQS).
5. Natija → `written`; hammasi tugagach `verify_totals` (1C ichida bitta so'rov) → `done` yoki `mismatch`. Ulanish yopiladi (litsenziya bo'shaydi).
6. Agent o'chiq bo'lsa partiyalar navbatda kutadi; qaytganda **sana tartibida** ketadi. D+1 kuni D yakunlanmaguncha boshlanmaydi.

**Hujjatlar tartibi (partiya ichida):** yangi ma'lumotnomalar (tasdiqlanganlari) → kirim → yetkazib beruvchiga qaytarish → ko'chirish → hisobdan chiqarish/inventarizatsiya → ОРП (har kassa, `23:50:00`) → Реализация (qarz/B2B) → unga bog'liq to'lovlar → oldingi kun cheklari bo'yicha qaytarish (`23:55:00`) → qarz to'lovlari → kassa hujjatlari (`03` §5.1 — kanonik).

## 4. Nima 1C ga ketadi / ketmaydi

| ERP | 1C (БП UZ 3.0, metadata nomi pilotda tasdiqlanadi) | Jamlash | Bosqich |
|---|---|---|---|
| Chakana sotuv (naqd/karta/UzQR/Click/Payme/Uzum) | `ОтчетОРозничныхПродажах`: tovar qatorlari + naqdsiz to'lovlar «вид оплаты» bo'yicha; naqd = qoldiq | **kun × kassa** (sozlama: kun × filial; smena — keyinroq) | A |
| Shu kungi qaytarish | ОРП ichida manfiy qator (§10 test 7 o'tmasa — alohida qaytarish hujjati) | kun × kassa | B |
| Oldingi kun cheki qaytarishi | `ВозвратТоваровОтПокупателя` + РКО «Возврат покупателю» | kun × kassa | B |
| Qarzga / B2B sotuv | `РеализацияТоваровУслуг` (nomli kontragent, 4010) | har chek | B |
| Qarz to'lovi (naqd/karta) | ПКО «Оплата от покупателя» / karta operatsiyasi — **daromad yaratmaydi** (qaror #30) | har to'lov | B |
| Tovar kirimi | `ПоступлениеТоваровУслуг` (e-faktura raqami bilan, dublikat tekshiruvi) | har hujjat | **A** |
| Ko'chirish, hisobdan chiqarish, inventarizatsiya | `ПеремещениеТоваров`, `СписаниеТоваров`, `Инвентаризация…` + `Оприходование` | har hujjat | B |
| Kassa: inkasso, xarajat (naqd), yetkazib beruvchiga naqd to'lov | РКО/ПКО tegishli operatsiya turi bilan | har hujjat | B |
| Smena farqi, qarz kechish, narx o'zgarishi, boshlang'ich qoldiq | standart **o'chiq** (buxgalter yoqadi) | — | C |
| **Ketmaydi:** provodkalar (`ledger_entries`, `vat_moves`), tannarx (`stock_lots`, `cost_amount`), alohida fiskal cheklar/Z-hisobot, qoralamalar, buyurtmalar, markirovka kodlari, e-faktura obyektlari, bank orqali to'lovlar (bank-klientdan dublikat), AI/audit/billing | 1C hujjatni **o'zi** o'tkazadi va tannarxni o'z hisob siyosati bilan hisoblaydi | — | — |

**Rejimlar** (`onec_settings.mode`): `full` (tavsiya — kirim ham ERP'dan), `sales_only` (buxgalter kirimni 1C'da o'zi kiritadi; qoldiq preflight'i majburiy), `money_only` (tovarsiz). **Tannarx haqiqat manbai:** 1C ichidagi hisobot uchun — 1C; ERP tannarxi — boshqaruv hisobi; oylik «ERP vs 1C» solishtiruvi.

## 5. Ma'lumotnomalarni moslash

- **Birinchi ulanish ustasi** (BO-22): profil aniqlash → Tashkilot (STIR) → filial↔ombor (АТТ/«розничный магазин» turi)/bo'linma → kassa↔Касса/КассаККМ → to'lov turi↔Вид оплаты (+ ekvayer kontragenti) → QQS stavkasi → birliklar → tovarlar → kontragentlar → `start_date` va qoldiq solishtiruvi (`03` §4.2).
- **Tovar moslash tartibi:** ИКПУ (MXIK) + nom o'xshashligi → shtrix-kod/артикул → kod → aniq nom → trigram (faqat taklif). Natija `onec_mappings`da GUID bilan saqlanadi — nom keyin o'zgarsa ham bog'lanish buzilmaydi (MoySklad xatosi takrorlanmaydi).
- **Yaratish siyosati (yakuniy):** yozish paytida 1C'da hech narsa nom bo'yicha qidirilmaydi va **jimgina yaratilmaydi**. Topilmagan tovar/kontragent/birlik/ombor/kassa/to'lov turi → preview'da «1C'da yaratiladi» ro'yxati → `onec.mapping.edit` ruxsatli inson tasdig'i → agent yaratadi (`product_create_policy`: `deny` | `ask`, standart `ask`; `auto` yo'q). **Tashkilot va QQS stavkasi — hech qachon yaratilmaydi (blok).** ERP'da ma'lumotnoma o'zgarsa — 1C elementi avtomatik o'zgarmaydi, «yangilash taklifi».
- Yangi tovar sotilsa → kun `blocked` + Telegram «3 ta yangi tovarni moslang».

## 6. Takror yozilmaslik va tuzatishlar

- **Asosiy:** deterministik GUID `UUIDv5(onec_bases.guid_namespace, "{kind}:{erp_key}")` (barcha obyektlar uchun bitta qoida) + `УстановитьСсылкуНового`. `erp_key` revision'dan mustaqil — qayta yuborish shu hujjatni yangilaydi.
- **Server daftari:** `onec_object_refs` (GUID, raqam, `ВерсияДанных`, kontent xeshi) — hisobot, drift, tuzatish uchun.
- **Inson izi va zaxira:** `Комментарий = "ERP #<qisqa_id> …"`; T-1 sinovi GUID usulini tasdiqlamasa — marker bo'yicha qidiruv asosiy bo'ladi (Sonar usuli). Agentda `results.jsonl` outbox — 1C'ga yozilgan, lekin server bilmagan holat.
- **«Noma'lum natija» (timeout):** xavfsiz — keyingi urinish «avval GUID bo'yicha tekshir, keyin yoz».
- **`ОбменДанными.Загрузка` ishlatilmaydi** — 1C'ning to'ldirish/tekshiruv/o'tkazish mantiqi kerak.
- **Tuzatishlar:** kech offline chek (48 soat) → kun `stale` → yangi revision, **o'sha GUID**li ОРП yangilanadi va qayta o'tkaziladi. 1C'da shu sana «Дата запрета изменения» bilan yopilgan bo'lsa → avtomatik sana almashtirish **yo'q**: buxgalter tasdig'i bilan joriy ochiq sanada **tuzatuvchi ОРП** (faqat farq). 1C'da hujjat qo'lda o'zgartirilgan (`ВерсияДанных` farq) → `conflict`, ustiga yozilmaydi. Bekor qilingan 1:1 hujjat → `ОтменаПроведения` + `ПометкаУдаления`; jismoniy o'chirish yo'q.

## 7. Xavfsizlik va litsenziya

- Kiruvchi port yo'q; vazifalar alohida Ed25519 imzosi bilan (AV/proksi TLS'ni ushlasa ham soxta vazifa bajarilmaydi); agent faqat oq ro'yxatdagi `kind`lar, ixtiyoriy 1C kod/so'rov matni yo'q.
- **Uch qulf:** server `write_enabled` + PK'dagi «yozishga ruxsat» + har partiya tasdig'i ruxsat bilan (Sonar'ning rolsiz tasdiq zaifligi yo'q).
- Alohida minimal huquqli 1C foydalanuvchisi `ERP integratsiya` (tashqi ulanish huquqi + kerakli hujjatlar); «Полные права» yo'q.
- Sirlar: 1C paroli va agent kaliti — DPAPI `CurrentUser`; serverda faqat ulanish satrining xeshi va maskalangan ko'rinishi.
- **Litsenziya:** huquqiy qoida tasdiqlangan — vositachi dastur litsenziya sonini kamaytirmaydi (1C FAQ IX.1-57). Texnik jihat (agent 1C ochiq turgan o'sha OS sessiyasida litsenziyani bo'lishadimi) — *tasdiqlanmagan*, 1C manbasi «с оговорками» deydi. **Qoida:** agent allaqachon 1C litsenziyasi bor PK'ga o'rnatiladi, ulanish faqat yuborish paytida ochiladi va darhol yopiladi; litsenziya xatosi — `ONEC_LICENSE_UNAVAILABLE` (qayta urinish).
- Avto-yangilanish: Ed25519 manifest + SHA-256 + Authenticode OV.

## 8. Qamrov chegaralari

| Holat | Qaror |
|---|---|
| 1C **Базовая** versiya | **Qamrovdan tashqari** — COM platforma darajasida yo'q (tasdiqlandi). Onboarding'ning 1-tekshiruvi: «ПРОФ kerak» xabari |
| Bulutdagi 1C (1С:Фреш, uzcloud, clobus) | **Qamrovdan tashqari** — baza mijoz PK'sida emas, COM imkonsiz; sotuvdan oldin aytiladi |
| Konfiguratsiyalar | 1) **«Бухгалтерия для Узбекистана 3.0»** (pilot, `bp30_uz`); 2) УТ 11 для Узбекистана; 3) Розница / Управление компанией для Узбекистана 3.0. БП 1.5 — yo'q |
| Bir mijozda УТ/Розница + БП | ERP faqat **bitta** bazaga yozadi (odatda БП), aks holda 1C almashuvi orqali ikki marta tushadi |
| Tovarni sotish narxida hisoblaydigan bazalar (2920/2980) | MVP'da ogohlantirish bilan qo'llab-quvvatlanmaydi (savol 6) |
| Markirovka tekshiruvi yoqilgan 1C | MVP'da kod yuborilmaydi; sozlama aniqlansa ogohlantirish |
| Platforma | 8.3 (va 8.5 — ProgID registrdan qidiriladi, qattiq kodlanmaydi); 32/64-bit avtomatik |

## 9. Raqobatchilardan ustunligimiz

1. «Бухгалтерия для Узбекистана 3.0» uchun hujjatlashtirilgan tayyor POS konnektori bozorda topilmadi; O'zbekistonda bu ish integratorlarda 5–20 mln so'm.
2. **Tarifga kiritilgan** (Evotor 630 ₽/oy/terminal o'rniga).
3. 1C'ga `.epf`/kengaytma o'rnatilmaydi — «1C yangilandi, обработку обновите» muammosi yo'q.
4. **Dublikat kafolatli yo'q** — GUID darajasida (Evotor/iiko'ning asosiy og'rig'i).
5. Nomenklatura dublikati yo'q — GUID xaritasi, «faqat moslanmaganlar» ekrani, yaratish faqat tasdiq bilan.
6. **Preflight** (yopiq davr, qoldiq, maydon uzunligi, moslash) va **yozgandan keyin solishtirish** — raqobatchilar xatoni faqat yozish paytida ko'rsatadi.
7. Qaytarish, kassa, qarz to'lovlari to'liq; kunlik Telegram xulosasi; rolga bog'liq tasdiq.
8. Halol cheklovlar (Базовая, bulut 1C) onboarding'ning birinchi ekranida.

## 10. Pilotdan oldingi testlar (real БП UZ 3.0.64.x bazada, kod yozishdan oldin)

1. COM: `ПолучитьСсылку(Новый УникальныйИдентификатор)` mavjud bo'lmagan obyektda `ПолучитьОбъект()` → `Неопределено`; `УстановитьСсылкуНового` + `Записать` → shu GUID bilan qayta topish; ikkinchi yozish dublikat bermasligi.
2. `ПередЗаписью/ПриЗаписи` `Ссылка`ni o'zgartirmasligi.
3. Metadata dump: `ОтчетОРозничныхПродажах` rekvizitlari va jadval qismlari (`Товары`, to'lov jadvali nomi — `Оплата`/`Безналичные оплаты`/`ОплатаПлатежнымиКартами`), `Касса`/`КассаККМ` bormi.
4. `Номенклатура`dagi ИКПУ va qadoq kodi rekviziti; `СтавкиНДС` — sanoqmi yoki ma'lumotnoma, qiymat nomlari; imtiyoz kodi rekviziti.
5. ОРП `СчетУчета…` bo'sh holda yozilganda 1C o'zi to'ldiradimi (`Заполнить`, menejer modul protseduralari); bo'lmasa qaysi yo'l.
6. COM orqali yaratilgan ОРП provodkalari qo'lda kiritilgan ОРП bilan bir xilmi (schyotlar, QQS, tannarx).
7. ОРП'da manfiy miqdorli qator (shu kungi qaytarish) qabul qilinadimi.
8. Chakana qaytarish va kartaga qaytarish hujjatlari mavjudligi.
9. `ВидыОплатОрганизаций` tuzilmasi (tur, kontragent, shartnoma, hisob).
10. «Разрешить списание запасов при отсутствии остатков» o'chiq holatda ОРП xatosi matni.
11. «Дата запрета изменения» — COM yozuvida xato matni; taqiq sanasini o'qish yo'li.
12. `Цена` aniqligi va `Цена×Количество ≠ Сумма` holatida o'tkazish xatosizligi; QQS yaxlitlash farqi.
13. Bazaning asosi: БП 3.0 tipidagi oy yopish yoki БП 2.0 tipidagi «Восстановление последовательности».
14. **Litsenziya:** 1 litsenziyali fayl baza, 1C ochiq + agent shu OS sessiyasida → ikkinchi foydalanuvchi kira oladimi; agent boshqa PK/xizmat sifatida — farq.
15. 32-bit va 64-bit platforma; bir PK'da ikki platforma versiyasi; klient-server versiya nomuvofiqligi xato matni.
16. Monopol rejim, Konfigurator ochiq, «Блокировка работы пользователей» xato matnlari.
17. Buxgalter shu hujjatni formada ochib turganda yozish xatosi.
18. Minimal huquqli `ERP integratsiya` foydalanuvchisi bilan ulanish va o'tkazish (aniq rollar ro'yxati).
19. Vaqt: 100/300/1 500 qatorli ОРП yozish + o'tkazish (fayl baza), foydalanuvchi parallel ishlayotganda kutish.
20. Tarmoq yozish o'rtasida uzilganda (worker o'ldirildi) → keyingi urinish dublikatsiz.
21. «Касса ККМ» elementi uskunaga bog'lanmaganda COM o'tkazish fiskal qurilmaga murojaat qilmasligi.
22. AV'ning HTTPS skanerlashi bilan long-poll va imzo tekshiruvi.

## 11. Bosqichma-bosqich reja

| Bosqich | Tarkib | Qabul mezoni |
|---|---|---|
| **A — pilot** (bitta profil `bp30_uz`, 1–3 do'kon) | Agent (ulash, bazani topish, «saqlash=sinash», `probe/base_info/meta_sync/catalog_read/object_upsert/verify_totals`); moslashtirish ustasi; **ОРП + kirim + qoldiq preflight**; qo'lda trigger; preview → approve → yozish → solishtirish; Telegram | 300 qatorli kun yoziladi va o'tadi; ikkinchi «Yuborish» hech narsa takrorlamaydi; yozish o'rtasida uzish → dublikat yo'q |
| **B** | Qaytarishlar, Реализация + qarz to'lovlari, ko'chirish/hisobdan chiqarish/inventarizatsiya, kassa hujjatlari; `on_shift_close`/`at_time`; `auto_approve` (0 ogohlantirish); revision va tuzatuvchi ОРП; drift tekshiruvi | 7 kunlik offline'dan keyin partiyalar sana tartibida o'tadi; kech chek o'sha GUID'li ОРП'ni yangilaydi |
| **C** | УТ/Розница/УК profillari, ko'p baza, server-PK rejimi (Task Scheduler), smena bo'yicha ОРП, `.epf` optimallashtirishi (asoschi roziligi bilan), E16–E19 | — |

**Spec'ga nima qo'shiladi** (qabul qilingach, `00-README` qoida 2 bo'yicha bitta commit'da):
- `01-qarorlar.md` #36 — qamrov «yozish», bosqich va agent texnologiyasi bilan yangilanadi; `26` asoschi bandi #4 yopiladi.
- `21-integratsiyalar.md` — yangi **§15 «1C integratsiyasi (COM agent)»**: topologiya, protokol (`/api/v1/onec-agent/*`), xato tasnifi, `outbox_jobs` emas `onec_agent_tasks`.
- `11`/`12` — 11 jadval: `onec_agents`, `onec_bases`, `onec_branch_bindings`, `onec_mappings`, `onec_object_refs`, `onec_export_batches`, `onec_export_items`, `onec_export_item_sources`, `onec_agent_tasks`, `onec_agent_logs`, `onec_settings`, `onec_metadata_snapshots` (hammasi `app` sxemasi, `tenant_id` + RLS uchligi, UUIDv7, `NUMERIC(18,2)`, `TEXT + CHECK`); `devices.kind` CHECK'ga `'onec_agent'`; `platform.signing_keys.purpose`ga `'onec_task'`, `'agent_update'`.
- `14` — OAuth mijoz turi `onec-agent` (device grant + `private_key_jwt`), scope `onec.agent`.
- `15` §2.1/§2.2 — `onec.view`, `onec.settings.manage`, `onec.mapping.edit`, `onec.export.prepare`, `onec.export.approve`, `onec.export.correct` (matritsa `04` §3.9); audit voqealari `onec.*`.
- `17` — `ONEC_*` xato kodlari katalogga; `20` yoki yangi API bo'limi — `/onec-agents`, `/onec-bases`, `/onec-mappings`, `/onec-export-batches`, `/onec-settings` (kebab-case ko'plik, snake_case JSON, `Idempotency-Key`).
- `06`/`07` — **BO-22** «1C integratsiyasi sozlamalari», **BO-23** «1C ga yuborish»; BO-14 integratsiyalar holatiga «1C» qatori.
- `03` — yangi modul (M19 «1C integratsiyasi») US'lari; `04` — BP-14 «Kunni 1C ga yuborish»; `30`, `31` — matritsa va qabul testlari.
- `27-backlog.md` — «MVP'dan keyin» bo'limiga **1C bosqichi** (A/B/C), A uchun shart: pilotdan oldingi testlar (§10) bajarilgan.

## 12. Asoschi hal qilishi kerak bo'lgan savollar

1. **Agent tili:** C#/.NET Framework 4.8 yoki Python (pywin32)? — *Standart: .NET Framework 4.8* (runtime o'rnatilmaydi, AV soxta signali kam, Win7/8 ham; biznes mantiq baribir serverda Python).
2. **Bosqich:** MVP ichida yoki MVP'dan keyin? — *Standart: MVP'dan keyin, pilot do'konlar bilan birinchi navbat*.
3. **ОРП jamlash:** kun × kassa / kun × filial / smena? — *Standart: kun × kassa*, filial — sozlama, smena — C bosqichi.
4. **Rejim:** `full` (kirim ham ERP'dan) standartmi? — *Standart: `full`*, `sales_only` faqat buxgalter so'rasa.
5. **Yangi tovarni 1C'da yaratish:** ruxsat (tasdiq bilan) yoki umuman taqiq? — *Standart: `ask` (tasdiq bilan yaratish)*.
6. **Sotish narxida hisob (2920/2980) bazalari** MVP'da? — *Standart: yo'q, ogohlantirish*.
7. **Базовая va bulut 1C mijozlari** — qamrovdan tashqari deb rasman belgilaymizmi? — *Standart: ha*; ularga zaxira (`.epf` yoki fayl) keyin ko'riladi.
8. **`.epf` optimallashtirishi** (1C ichida bizning kodni vaqtincha bajarish, o'rnatmasdan) C bosqichida ruxsatmi? — *Standart: MVP'da yo'q*; §10 test 5 natijasiga qarab.
9. **Avto-tasdiq:** ogohlantirishsiz partiyani avtomatik yuborish ruxsat etiladimi? — *Standart: o'chiq, Egasi yoqadi*.
10. **Narx/sotuv modeli:** 1C integratsiyasi 99 000 tarifga kiradimi yoki qo'shimcha xizmat? — *Standart: tarifga kiradi* (asosiy ustunlik).
11. **Authenticode OV sertifikati** — qaysi yuridik shaxs nomiga va qachon olinadi? — *Standart: A bosqichidan oldin*.

## 13. Buxgalter / yurist savollari

1. Qarzga sotuvda daromad/QQS tan olish vaqti (sotuv kuni yoki to'lov kuni) — 1C'ga Реализация qaysi kunda ketishini belgilaydi (qaror #30 ochiq qismi; `onec_settings.credit_revenue_timing`).
2. Karta/QR/Click/Payme tushumlari uchun 1C'da 5710 tranzit hisobi va «вид оплаты» tuzilmasi (har terminal-bank alohidami).
3. Bank ko'chirmasini (5110 ↔ 5710, komissiya) kim kiritadi — ERP yoki buxgalter (standart: buxgalter, bank-klient orqali).
4. Nasiyachi jismoniy shaxslar — har biri alohida kontragent (ПИНФЛ bilan) yoki bitta guruh?
5. Chegirmani 1C'da alohida 9050'da ko'rsatish kerakmi (standart: sof summa).
6. Yopilgan 1C davriga kech chek — tuzatuvchi hujjat joriy sanadami; oy qayta yopilishi kimning ishi.
7. Smena farqi, egasi olgan pul, inkasso, hisobdan chiqarish hisob raqamlari.
8. Agentning 1C litsenziyasi bo'yicha 1C hamkorining rasmiy javobi (alohida ish o'rni hisoblanadimi).
9. 1C va ERP tannarxi farqi — buxgalter hisobotda 1C tannarxini ishlatishini tasdiqlash.

## 14. Tasdiqlash jadvali (accept gate, 2026-10-15)

Veb-qidiruv limiti tugagan; manbalar WebFetch bilan to'g'ridan-to'g'ri ochildi.

| # | Da'vo | Natija | Manba |
|---|---|---|---|
| V1 | Базовая versiyada COM/Automation yo'q | **tasdiqlandi** — «не поддерживается COM-соединение и Automation-сервер» | v8.1c.ru/stateacc/bazovaya-versiya-bgu/ ; online-ufa.ru/content/articles/1c_baz/ |
| V2 | Vositachi (COM) litsenziya sonini kamaytirmaydi | **tasdiqlandi** — 1C FAQ IX.1-57 | 1c.uz/v8/questions_licence.php |
| V3 | Bir OS sessiyasida klient ilovalar bitta litsenziyani bo'lishadi, tashqi ulanish «с оговорками»; serverdan olinsa har ulanish o'z litsenziyasi | **tasdiqlandi (manba matni)**; amaliy xulq **tasdiqlanmadi (taxmin)** — test 14 | klerk.ru/soft/articles/430201/ |
| V4 | 01 [M7] «XI.1-66 — COM litsenziya» | **tasdiqlanmadi** — sahifada COM faqat IX.1-57 da; `01` tuzatildi | 1c.uz/v8/questions_licence.php |
| V5 | In-proc COM: `ComConnector` bitligi klient bilan bir xil | **tasdiqlandi** | klerk.ru (yuqorida) |
| V6 | Tashqi ulanish — in-proc COM server, UI yo'q, «модуль внешнего соединения» | **tasdiqlandi** | v8.1c.ru/platforma/vneshnee-soedinenie/ |
| V7 | `ОбменДанными.Загрузка` — handlerlar bayroqni tekshirib mantiqni o'tkazib yuboradi, yaxlitlik javobgarligi chaqiruvchida | **tasdiqlandi** (std 773) | its.1c.ru/db/content/v8std/src/200/400/i8100773.htm |
| V8 | `УстановитьСсылкуНового` COM orqali yangi obyektga GUID beradi; `ПолучитьОбъект()` yo'q obyektda `Неопределено` | **tasdiqlanmadi (taxmin)** — sintaksis yordamchisi pullik, ochiq manba ochilmadi; КД2/РИБ amaliyotida keng ma'lum. Test 1–2 majburiy | — |
| V9 | Joriy БП UZ relizi 3.0.64.8 | **tasdiqlandi** (e'lon 14.07.2026); УТ UZ 11.0.0.24 (12.07), Розница UZ 3.0.17.1 (24.07) | its.1c.eu |
| V10 | NSBU 21: 5710 «Йўлдаги пул маблағ (ўтказма)лари», 9020 «Товарларни сотишдан даромадлар», 9120 «Сотилган товарларнинг таннархи», 2910/2920/2980, 9040, 9050, 5110, 5010, 6410 | **tasdiqlandi** | lex.uz/docs/7282737 |
| V11 | 5710 — karta tushumi uchun **mos** tranzit hisob | **tasdiqlanmadi (talqin)** — hisob nomi tasdiqlandi, karta tushumida qo'llash buxgalter tasdig'ini kutadi | lex.uz + bss.uz (`02` [M10]) |
| V12 | ОРП metadata nomlari, ИКПУ rekviziti, `СтавкиНДС` turi UZ БП'da | **tasdiqlanmadi (taxmin)** — testlar 3–4 | — |

## 15. Hal qilingan ziddiyatlar

| # | Ziddiyat | Yakuniy qaror | Qaysi faylda tuzatildi |
|---|---|---|---|
| Z1 | Agent tili: `04` .NET Fx 4.8 vs `01`/`06` Python+pywin32 | Standart .NET Fx 4.8; Python kodi — chaqiruvlar namunasi; asoschi savoli 1 | `01` §0/§9, `06` §0 |
| Z2 | Idempotentlik: marker (`01`) vs GUID+marker (`03`,`06`) vs GUID+daftar (`04`) | GUID asosiy + `onec_object_refs` + marker (iz/zaxira) + agent outbox; algoritm `04` §5.3 | `01` §5, `03` §9, `06` §2 |
| Z3 | GUID manbai: 1:1 hujjatda ERP `id` (`03`) vs hammasi UUIDv5 (`04`) | Hammasi UUIDv5(baza namespace) | `03` §9.1 |
| Z4 | Jamlash: smena (`01`) / kun×ombor×kassa (`02`) / kun×kassa (`03`,`04`) / do'kon×kun (`06`) | Kun × kassa standart; filial va smena — sozlama | `01` §0 |
| Z5 | Jadval nomlari `03` vs `04` (+ `06` `onec_mapping`) | `04` §3.3 kanonik + `onec_export_item_sources` | `03` §4.4 |
| Z6 | `outbox_jobs`ga kind qo'shish (`03`) vs alohida `onec_agent_tasks` (`04`) | `onec_agent_tasks`, `outbox_jobs` emas | `03` §4.4 |
| Z7 | Ma'lumotnoma yaratish: hech qachon (`06`) / tasdiq bilan (`03`,`05`) / `auto` siyosati (`04`) | Faqat preview + inson tasdig'i; `auto` yo'q; Tashkilot/QQS — blok | `02` §8, `04` §3.3, `06` §1.2 |
| Z8 | Pilot: faqat ОРП (`04`) vs `full` rejim tavsiyasi (`02`,`03`) | A bosqichi: ОРП + kirim + qoldiq preflight | `04` §8 |
| Z9 | Schyot/QQS to'ldirish: 1C o'zi (`03`) vs `.epf` tavsiya (`06`) | §10 test 5 (`03` T-4) → Заполнить/menejer protseduralari → «oltin namuna»; `.epf` MVP'da yo'q | `06` §0 |
| Z10 | ОРП vaqti 23:59 (`06`) vs 23:50 slotlar (`03`) | `03` §5.1 slotlari | `06` §2 |
| Z11 | Ketma-ketlik `03` §5.1 vs `04` §3.6 phase | `03` tartibi, `04` phase'lariga joylanadi (§3 yuqorida) | shu fayl |
| Z12 | Litsenziya: «bitta sessiya — bitta litsenziya» (`01`) vs «har ish joyi» (`04`) vs «COM litsenziya oladi» (`06`) | Huquqiy qoida IX.1-57 (tasdiqlandi); texnik xulq — test 14; agent litsenziyali PK'da, qisqa ulanish | `01` §3.1 (manba tuzatildi) |
| Z13 | Базовая — «taxmin» (`06`) vs faktlar (`01`) | Tasdiqlandi, qamrovdan tashqari | `06` §7.2 |
| Z14 | Reliz sanalari «sentabr–oktabr» (`02`) | ИТС: iyul 2026 | `02` §0 |
| Z15 | Profil kodlari `bp_uz_3`… (`03`) vs `bp30_uz`… (`04`) | `bp30_uz`, `ut11_uz`, `roznica30_uz`, `uk30_uz`, `unknown` | `03` §4.4, `04` §3.3 |
| Z16 | Verify chegarasi 0.00 (`04`) vs 0.01 (`06`) vs >1 so'm QQS (`02`) | 0.00 (ERP summalari aynan yoziladi); 1C qayta hisoblasa — profil darajasida hujjatlashtirilgan yaxlitlash qatori (test 12) | shu fayl |

## 16. Spec bilan ziddiyatlar (spec fayllari o'zgartirilmadi — taklif)

| # | Ziddiyat | Taklif |
|---|---|---|
| S1 | `04-biznes-jarayonlar.md` BP-03 6-qadam «daromad/QQS hali tan olinmaydi» va BP-11 4-qadam «daromad shu bosqichda» ↔ `13` §2.14 interim «provodka sotuv kuni» ↔ BP-12 (qator 360) «allaqachon hisoblangan (BP-02/03)» | BP-03/BP-11 matnini `13` §2.14 interimiga moslash: «provodka sotuv kuni; fiskal chek to'lov kuni; yakuniy vaqt — `FiscalPolicy`, buxgalter/yurist tasdig'i» |
| S2 | `13` §2.2 karta/QR → to'g'ridan-to'g'ri **5110**; NSBU 21 da 5710 «Йўлдаги пул маблағ (ўтказма)лари» bor, `02` tavsiyasi — tranzit 5710 | `13` §1 ga 5710 qo'shish, §2.2/§2.4/§2.14 kartada `Dt 5710`, bank tushganda `Dt 5110 / Kt 5710` (+ komissiya) — buxgalter tasdig'i bilan |
| S3 | `13` §2.18 inkasso `Dt 5110 / Kt 5010` to'g'ridan-to'g'ri; NSBU 21 bo'yicha inkassatorga berilgan tushum — 5710 | Inkasso: `Dt 5710 / Kt 5010`, bankka tushganda `Dt 5110 / Kt 5710` |
| S4 | `12` `devices.kind` CHECK faqat `('web','android')` | `'onec_agent'` qo'shish (agent `devices` yozuviga ega bo'lishi uchun) |
| S5 | `platform.signing_keys.purpose` — agent vazifa/yangilanish imzosi uchun qiymat yo'q | `'onec_task'`, `'agent_update'` qo'shish (`14` §6) |
| S6 | `01-qarorlar.md` #36 «qamrov va bosqich — ochiq», `26` asoschi bandi #4 agent texnologiyasini ochiq qoldiradi | Asoschi javobidan keyin #36 yangilanadi, `26` #4 yopiladi |
| S7 | `15` §2.1 katalogida `onec.*` kodlari yo'q; `settings.tenant` «integratsiya kalitlari»ni qamraydi | Alohida `onec.*` oilasi (§11), `settings.tenant` dan ajratiladi |
| S8 | `07`/`06` da BO-22/BO-23 yo'q (oxirgisi BO-21) | Yangi ekranlar BO-22, BO-23 |
| S9 | `21` §0 umumiy naqsh — `outbox_jobs` push modeli; 1C pull modeli unga sig'maydi | `21` yangi §15 da istisno sifatida yoziladi |
| S10 | `16` 48 soat va kech chek: `onec` tayyorlik qoidasi qurilma `last_sync_at` ga tayanadi — `16` da bu maydon semantikasi 1C uchun ko'rsatilmagan | `16` §9 ga «1C eksporti `last_sync_at` dan foydalanadi» havola |

## 17. Fayllar indeksi

| Fayl | Mavzu |
|---|---|
| `00-xulosa.md` | Shu fayl — yakuniy tavsiya (ustun) |
| `01-1c-ga-yozish-kanallari.md` | COM tashqi ulanish chuqur tahlili: talablar, litsenziya, bitlik, regsvr32, fayl/server baza, rad etilgan kanallar |
| `02-ozbekiston-1c-konfiguratsiyalari-va-hujjatlar.md` | O'zbekiston 1C konfiguratsiyalari, relizlar, БП UZ 3.0 hujjatlari, NSBU 21 hisoblari, QQS, tannarx, taqiq sanasi |
| `03-malumot-moslashtirish.md` | ERP → 1C maydon xaritalari (E1–E19), konvertatsiya, ma'lumotnoma moslash, ketma-ketlik, tuzatishlar, testlar T-1…T-10 |
| `04-integratsiya-arxitekturasi.md` | Modul arxitekturasi: agent, ulash, protokol, jadvallar, holat mashinalari, ruxsatlar, API, UX, xavfsizlik, bosqichlar |
| `05-bozor-va-raqobatchilar.md` | UZ/MDH POS→1C bozor tahlili, og'riqlar, saboqlar, ustunliklar |
| `06-1c-ga-yozish-texnikasi.md` | COM yozish mexanikasi, namuna kod, xatolar, tranzaksiyalar, `Загрузка`, GUID, yopiq davr, litsenziya, `.epf` |
