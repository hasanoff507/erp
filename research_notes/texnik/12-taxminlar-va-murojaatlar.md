# Taxminlar reyestri va rasmiy murojaat xatlari loyihasi

*Tadqiqotchi: Fiskal · 2026-10-12*

*Maqsad: `00-xulosa-va-ochiq-savollar.md`dagi hal qilinmagan 6 ta savol bo'yicha Mahsulot va Arxitektura jamoalari MVP'ni **taxmin + zaxira yo'l** bilan loyihalashi uchun. Xatlar faqat loyiha — hech qayerga yuborilmaydi.*

## Taxminlar reyestri

| # | Savol | Ishchi taxmin (MVP shu bilan quriladi) | Taxmin noto'g'ri chiqsa — zaxira yo'l | Spetsifikatsiyaga ta'siri | Kimga murojaat | Qachongacha javob kerak |
|---|---|---|---|---|---|---|
| 1 | Virtual kassa reyestriga mustaqil dastur sifatida kiritish narxi va muddati qancha? (`02-fayl`) | Narx nolga yaqin bo'lmaydi (sertifikatlash + Kiberxavfsizlik markazi ekspertizasi + fiskal operator integratsiyasi xizmat sifatida pullik); muddat haftalar emas, oylar (sinov integratsiyasi + ko'plab xulosalar yig'ish jarayoni sababli) | Agar narx/muddat MVP byudjetiga mos kelmasa — mavjud reyestr a'zosi (E-POS, UZKASSA, Rahmat POS) bilan OEM/oq-etiket (white-label) hamkorlik orqali tezroq bozorga kirish, o'z sertifikatini keyinroq olish | Arxitekturada fiskal modul qatlami E-POS/UZKASSA kabi uchinchi tomon API orqali abstraksiyalanishi kerak — to'g'ridan-to'g'ri OFD protokoliga qattiq bog'lanmaslik | Davlat soliq qo'mitasi / "Yangi texnologiyalar" ilmiy-axborot markazi DUK ([soliq.uz](https://soliq.uz)) | MVP arxitektura qarorlaridan oldin — 2–4 hafta ichida |
| 2 | CRPT Turon (Asl belgisi) integrator sifatida ro'yxatdan o'tish shartlari va API qanday? (`02-fayl`, `04-fayl`) | Ro'yxatdan o'tish shartnoma + texnik sinov talab qiladi, jarayon oylab davom etadi; API faqat ro'yxatdan o'tgan integratorlarga ochiq | Agar API ochilmasa/juda sekin bo'lsa — markirovka funksiyasini mavjud integratorlar (MoySklad, E-POS, Smartup) orqali proxy sifatida ulash, yoki markirovka modulini MVP'dan keyingi bosqichga ko'chirish | Markirovka moduli MVP'ning birinchi relizida to'liq avtomatik bo'lmasligi mumkin — uchinchi tomon integrator orqali vositachi qatlam kerak bo'ladi | CRPT Turon ([crpt-turon.uz](https://crpt-turon.uz), [help.crpt-turon.uz](https://help.crpt-turon.uz)) | Markirovka modulini loyihalashdan oldin — 1 oy ichida |
| 3 | ЗРУ-764 (Kiberxavfsizlik) bo'yicha majburiy sertifikatlash/ekspertiza oddiy xususiy SaaS ERP'ga (davlat organi/KAI emas) tegishlimi? (`07-fayl`) | Tegishli EMAS — mahsulot davlat API'lariga faqat mijoz sifatida ulanadi, davlat infratuzilmasini o'zi boshqarmaydi, shuning uchun 18/19-moddalar doirasiga kirmaydi | Agar javob "ha" bo'lsa — MVP jadvaliga sertifikatlash vaqti (oylar) va narxi qo'shiladi, ishga tushirish sanasi kechiktiriladi | Agar majburiy bo'lsa, loyiha boshlanishidan oldin byudjet/vaqt rejasi tubdan o'zgaradi — bu eng yuqori ta'sirli noaniqlik | Davlat kiberxavfsizlik xizmati markazi ([csec.uz](https://csec.uz)) | Loyiha boshlanishidan oldin — zudlik bilan, 1–2 hafta ichida |
| 4 | my.soliq.uz'dan davlat tuzgan soliq hisobotini dasturiy (API) o'qish yo'li bormi? (`04-fayl`, 6-bo'lim) | Rasmiy API yo'q; MVP'da foydalanuvchi hisobotni qo'lda yuklab oladi (PDF/Excel) va tizimga qo'lda yuklaydi/kiritadi | Agar E-IMZO orqali autentifikatsiyalangan yarim-rasmiy yo'l ham topilmasa — doimiy qo'lda jarayon qoladi, lekin UI orqali fayl yuklash + avtomatik parsing bilan osonlashtiriladi | "Davlat hisobotini solishtirish motori" (markaziy qiymat taklifi) MVP'da to'liq avtomatik emas, yarim-avtomatik bo'lib boshlanadi | Davlat soliq qo'mitasi / my.soliq.uz qo'llab-quvvatlash xizmati | "Solishtirish motori"ni loyihalashdan oldin — 1 oy ichida |
| 5 | E-IMZO'ning rasmiy dasturchi hujjati/qo'llab-quvvatlash kanali bormi? (`03-fayl`) | Yo'q — faqat jamoatchilik hujjati ([qo0p/e-imzo-doc](https://github.com/qo0p/e-imzo-doc)) va test muhiti (testvpn.e-imzo.uz) bilan ishlanadi, rasmiy texnik qo'llab-quvvatlash kanali bo'lmaydi | Agar jamoatchilik hujjati etarli bo'lmasa — "Yangi texnologiyalar" DUK bilan to'g'ridan-to'g'ri bog'lanish, yoki E-IMZO'ni allaqachon integratsiya qilgan kompaniyalar (Didox, Faktura.uz) bilan maslahatlashish | E-faktura/e-TTN/hisobot imzolash integratsiyasi rejalashtirilgandan ko'proq vaqt olishi mumkin — jadvalga bufer vaqt qo'shilishi kerak | "Yangi texnologiyalar" ilmiy-axborot markazi DUK / [e-imzo.uz](https://e-imzo.uz) | Imzolash integratsiyasini boshlashdan oldin — 2–3 hafta ichida |
| 6 | Internet yo'qligida markirovkalangan tovarni sotish siyosati (ruxsat/taqiq) qanday bo'lishi kerak? (`04-fayl`, 2.4-bo'lim) | Offlayn paytda markirovkalangan tovar sotuvi **vaqtincha cheklanadi** (kassa ogohlantirish beradi, sotuvni kechiktirishni tavsiya qiladi); internet qaytganda kod avtomatik tekshiriladi | Agar huquqiy maslahat "vaqtinchalik ruxsat bilan keyinroq tekshirish mumkin" desa — shu rejimga o'tiladi, lekin aniq audit-log bilan | Offline-first arxitekturada (`04-fayl`) markirovkalangan tovar uchun alohida "internet talab qilinadi yoki ogohlantirish" qoidasi qo'shiladi — bu umumiy offline-first prinsipdan istisno | Ichki yurist/huquqshunos maslahati + tasdiqlash uchun CRPT Turon yoki Soliq qo'mitasi | Offline-first arxitekturani yakunlashdan oldin — 2 hafta ichida |

---

## Rasmiy murojaat xatlari loyihasi

*Faqat loyiha — hech qayerga yuborilmaydi. Yuborishdan oldin kompaniya rahbariyati tasdiqlashi va rasmiy blankaga ko'chirilishi kerak.*

### Xat 1 — Davlat soliq qo'mitasi / "Yangi texnologiyalar" ilmiy-axborot markazi DUK

> Hurmatli rahbariyat,
>
> Biz O'zbekiston kichik va o'rta biznes segmenti uchun kassa, ombor va buxgalteriyani birlashtirgan dasturiy mahsulot (ERP+POS) ishlab chiqish ustida ishlamoqdamiz. Loyihani to'g'ri rejalashtirish uchun quyidagi savollarga rasmiy javob olishni so'raymiz:
>
> 1. Dasturiy virtual kassa mahsulotini Davlat reyestriga kiritish (sertifikatlash) uchun qanday xizmatlar pullik, ularning taxminiy narxi qancha va butun jarayon o'rtacha necha kun/oy davom etadi?
> 2. Hujjatlarni ko'rib chiqish bosqichlari (muvofiqlik sertifikati, Kiberxavfsizlik markazi xulosasi, fiskal operator integratsiyasi) uchun alohida-alohida qancha vaqt ketadi?
> 3. my.soliq.uz orqali korxona tomonidan avtomatik tuzilgan soliq hisobotlarini (QQS, aylanma va boshqalar) dasturiy ravishda (API orqali) olish imkoniyati bormi? Agar bo'lsa, qaysi hujjatga/portalga murojaat qilishimiz kerak?
> 4. E-IMZO integratsiyasi uchun rasmiy dasturchi texnik hujjati (API tavsifi) mavjudmi, yoki faqat qo'llanma darajasida ma'lumot beriladimi?
>
> Javobingizni email orqali kutib qolamiz. Hamkorlikka tayyormiz.
>
> Hurmat bilan, [kompaniya nomi]

### Xat 2 — CRPT Turon (Asl belgisi operatori)

> Hurmatli hamkorlar,
>
> Biz O'zbekistonda chakana savdo uchun kassa dasturi (POS) ishlab chiqmoqdamiz, bu dastur orqali Asl belgisi tizimiga ulangan tovarlarni (suv, ichimlik, tamaki va boshqalar) sotish nazarda tutilgan. Quyidagi savollarga javob olishni so'raymiz:
>
> 1. Uchinchi tomon dasturiy ta'minot (POS/ERP) ishlab chiquvchisi sifatida rasmiy integrator maqomini olish uchun qanday hujjatlar va shartlar talab qilinadi?
> 2. Integrator uchun texnik API hujjatlariga (kod tekshirish, sotuvni ro'yxatga olish/"chiqarish") qanday kirish mumkin — bu hujjatlar ochiq portalda bormi yoki faqat shartnoma asosida beriladimi?
> 3. Internet aloqasi yo'q paytda markirovkalangan tovarni sotish uchun qanday rasmiy qoida/tartib belgilangan — bunday holatda sotuvga vaqtincha ruxsat beriladimi, yoki sotuv internet qaytgunga qadar to'xtatilishi shartmi?
>
> Javobingizni kutib qolamiz.
>
> Hurmat bilan, [kompaniya nomi]

### Xat 3 — Davlat kiberxavfsizlik xizmati markazi (csec.uz)

> Hurmatli rahbariyat,
>
> Biz O'zbekistonda xususiy SaaS tarzida ishlaydigan kassa/ERP dasturiy mahsulotini ishlab chiqmoqdamiz. Mahsulot soliq qo'mitasining davlat axborot tizimlariga (OFD, e-faktura, Asl belgisi) faqat **mijoz/foydalanuvchi** sifatida ulanadi — davlat infratuzilmasini o'zi boshqarmaydi va davlat organi emas.
>
> Savolimiz: "Kiberxavfsizlik to'g'risida"gi qonun (ЗРУ-764)ning 18- va 19-moddalaridagi majburiy ekspertiza/sertifikatlash talabi shunday xususiy, oddiy tijorat SaaS mahsulotiga ham tegishlimi, yoki bu talab faqat davlat organlari va kritik axborot infratuzilmasi (KAI) obyektlariga tegishlimi? Agar bizning holatimizda ham ekspertiza/sertifikatlash talab qilinsa, bu jarayonning taxminiy muddati va narxi haqida ma'lumot berishingizni so'raymiz.
>
> Javobingizni kutib qolamiz.
>
> Hurmat bilan, [kompaniya nomi]

---

## Manbalar

- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` — savollar manbasi
- `research_notes/texnik/02-kassa-ofd-markirovka.md`, `03-efaktura-va-tolov.md`, `04-arxitektura-va-stack.md`, `07-hosting-lokalizatsiya-xavfsizlik.md` — har savolning texnik konteksti
- [soliq.uz](https://soliq.uz) — Davlat soliq qo'mitasi
- [crpt-turon.uz](https://crpt-turon.uz), [help.crpt-turon.uz](https://help.crpt-turon.uz) — CRPT Turon
- [csec.uz](https://csec.uz) — Davlat kiberxavfsizlik xizmati markazi
- [e-imzo.uz](https://e-imzo.uz), [github.com/qo0p/e-imzo-doc](https://github.com/qo0p/e-imzo-doc) — E-IMZO
