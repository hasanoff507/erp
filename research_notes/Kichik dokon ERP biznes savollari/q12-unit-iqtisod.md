## Savol 12 (9.1): Unit-iqtisod va Start narxi

### Bozorda qanday (jadval)

**Komponent bo'yicha yangi topilgan narxlar:**

| Komponent | Bizning oldingi taxmin | Yangi topilgan narx | Manba |
|---|---|---|---|
| SMS (nasiya eslatma + OTP) | 5,000–10,000 so'm/oy (20-50 ta × 150-300 so'm — to'liq asossiz taxmin) | **Eskiz.uz**: 95 so'm/SMS, barcha operatorlarga, obuna to'lovsiz, minimal to'lov majburiyati yo'q. 20-50 SMS/oy × 95 so'm = **1,900–4,750 so'm/oy**. Reklama SMS (Ucell/Uzmobile/Mobiuz) — 175 so'm/SMS (bizga tegishli emas, bu nasiya/OTP emas). **Play Mobile**: paket tizimi — "Start" paketi 250 SMSgacha = 5,000 so'm (≈20 so'm/SMS to'liq paket sarflansa), "Infinite" paketi 20,000+ SMS = 500,000 so'm. Playmobile'ning alohida topilgan 168.40 so'm/SMS raqami — bu UZCARD bank-xabarnoma kanali uchun (bizning use-case emas, chalkashtirmaslik kerak) | [eskiz.uz/uz/sms](https://eskiz.uz/uz/sms); [playmobile.uz](https://playmobile.uz/uz/instruction/); [spot.uz UZCARD SMS narxi](https://www.spot.uz/oz/2025/02/15/sms-notification/) |
| Click/Payme — mijoz to'lovi (checkout, karta/QR) | ~1-2% (taxmin) | **Click**: savdo nuqtasida QR/Click Pass — 1% (Uzcard/Humo), 2% (Visa). Billing/integratsiya (onlayn-do'kon, obuna) — 1.5-2.5% (Uzcard/Humo), 2.5% (Visa). **Payme**: xizmat to'lovi/QR — 1%, karta to'lovi — 1.5-2%, birinchi 3 oy ulanish bepul. Taxminimiz **to'g'ri tasdiqlandi** — 1-2% oralig'i real | [click.uz/uz/tarifs](https://click.uz/uz/tarifs); [business.click.uz/uz](https://business.click.uz/uz); Payme biznes qidiruv natijalari (b2b-partner.payme.uz saytiga to'g'ridan-to'g'ri kirish muvaffaqiyatsiz bo'ldi, lekin qidiruv orqali tasdiqlangan) |
| Tizim obuna to'lovi (49,000 so'm/oy) Click/Payme orqali o'tsa | Hisobga olinmagan (bu gap sifatida belgilangan edi) | Click/Payme o'z tariflarida "SaaS obuna" uchun alohida chegirma/kategoriya ko'rsatmaydi — billing/integratsiya tarifiga (1.5-2.5%) tushadi. 49,000 so'm × ~2% = **~980 so'm/oy/tenant qo'shimcha xarajat**, AGAR o'z obuna to'lovimizni Click/Payme orqali qabul qilsak. O'zbek SaaS'lar odatda bu komissiyani o'zi "yutadi" (mijozga qo'shib yubormaydi) — bu amaliyot keng tarqalgan, lekin alohida maqola bilan tasdiqlanmadi (**tasdiqlanmagan, amaliy kuzatuvga asoslangan**) | [click.uz/uz/tarifs](https://click.uz/uz/tarifs) |
| OFD/virtual-kassa partner to'lovi (agar o'z kassani davlat reyestriga ro'yxatdan o'tkazmasdan, partner orqali ishlasak) | REGOS +75,000 so'm/oy (berilgan) | **Multikassa** (Poster POS integratsiyasi misolida): ulanish — $28 (bir martalik), xizmat to'lovi — $8/oy, integratsiya — $5/oy → jami **$13/oy ≈ 155,500 so'm/oy/kassa** (kurs 1$ ≈ 11,963 so'm, 15.10.2026). **REGOS VCR**: fiskal modulni ulash — 1 BHM/yil (davlat belgilagan, "Yangi texnologiyalar" markaziga to'lanadi, barcha OFD operatorlari uchun majburiy — partner tanlovidan mustaqil), + oylik xizmat to'lovi — REGOS obunachilari uchun 0 so'm, boshqalar uchun **100,000 so'm/oy**. Demak, partner-OFD yo'li orqali **bitta kassa uchun ~75,000–155,500 so'm/oy** oraliqida xarajat chiqadi — bu bizning butun Start narximizdan (49,000 so'm) KO'P KATTA | [joinposter.com/multikassa](https://joinposter.com/en/applications/multikassa); [regos.uz/uz/product/regos-vcr/faq](https://regos.uz/uz/product/regos-vcr/faq) |
| O'z kassani davlat reyestrida ro'yxatdan o'tkazish (muqobil yo'l — partner emas) | Spec'da ochiq arxitektura savoli sifatida qoldirilgan | **Davlat Soliq Qo'mitasi**: onlayn-NKM/virtual kassa dasturini reyestrga ro'yxatdan o'tkazish — **bepul** ("hech qanday to'lov olinmaydi"), ariza 4 soat ichida ko'rib chiqiladi, virtual kassa dasturining bazaviy qismi davlat tomonidan bepul taqdim etiladi. Lekin baribir fiskal modul yillik to'lovi (1 BHM, "Yangi texnologiyalar" markaziga) barcha yo'llar uchun majburiy ko'rinadi — bu davlat tomonidan belgilangan, partner emas | [my.gov.uz/uz/service/627](https://my.gov.uz/uz/service/627); [kun.uz/50403927](https://kun.uz/50403927); [gov.uz/oz/soliq/page/virtual-kassa-reestri](https://www.gov.uz/oz/soliq/page/virtual-kassa-reestri?lang=ru) |
| 1 BHM qiymati (2026) | — | **Tasdiqlanmagan** — qidiruv limiti tugagani uchun 2026-yil BHM rasmiy qiymatini tasdiqlay olmadim. Taxminan 400,000-450,000 so'm/yil oralig'ida (2025-yilgi ~375,000 so'm asosida ekstrapolyatsiya) — **taxmin, tasdiqlash kerak** | — |

**Raqobatchilar narxi (kontekst uchun, oldin manbalashtirilgan):**

| Mahsulot | Bazaviy tarif | Virtual kassa holati | Jami (eng past, kassa bilan) |
|---|---|---|---|
| Start (bizniki) | 49,000 so'm/oy | Bundle ichida (bepul deklaratsiya) | 49,000 so'm/oy |
| REGOS Start | 69,000 so'm/oy | +75,000 so'm/oy majburiy qo'shimcha (eski ma'lumot; yangi FAQ'da REGOS obunachilariga 0 so'm, bo'lmasa 100,000 so'm/oy ko'rsatilgan — tarif o'zgargan bo'lishi mumkin) | 144,000 so'm/oy |
| mDokon | 199,000 so'm/oy dan | Noma'lum | 199,000+ so'm/oy |
| HIPPO Base | 247,200 so'm/oy | Noma'lum | 247,200 so'm/oy |
| BILLZ Start | 299,000 so'm/oy | Noma'lum | 299,000+ so'm/oy |

### Variantlar

**Variant A — Start'ni 49,000 so'mda saqlash, OFD'ni partner orqali "bepul bundle" qilib qoldirish**

Xarajat stacki (partner-OFD yo'li, 1 kassa/tenant):
- Hosting: ~20,500 so'm
- AI: ~2,000-5,000 so'm
- SMS (Eskiz, 20-50/oy): ~1,900-4,750 so'm
- Click/Payme (obuna to'lovi ustida, ~2%): ~980 so'm
- OFD partner (Multikassa/REGOS-tipidagi): **~75,000-155,500 so'm**
- **Jami: ~100,380–186,730 so'm/oy/tenant**

Natija: **-51,000 dan -138,000 so'm/oy gacha ZARAR** har bir Start mijozida. Bu variant **ishlamaydi** — OFD partner to'lovi yolg'iz o'zi butun Start narxidan 1.5-3 marta katta. Bu eng muhim topilma: agar partner-OFD yo'lini tanlasak, Start tarifini "virtual kassa included" deb e'lon qilish moliyaviy jihatdan mumkin emas.

**Variant B — O'z kassani davlat reyestriga ro'yxatdan o'tkazish (partner emas), Start'ni 49,000 so'mda saqlash**

Davlat ro'yxatidan o'tish bepul, faqat fiskal modul yillik to'lovi (1 BHM, taxminan 400-450 ming so'm/yil ≈ 33,000-37,500 so'm/oyga bo'linsa) qoladi — bu barcha yo'llar uchun majburiy, partner tanlovidan mustaqil.

Xarajat stacki:
- Hosting: ~20,500 so'm
- AI: ~2,000-5,000 so'm
- SMS: ~1,900-4,750 so'm
- Click/Payme (obuna ustida): ~980 so'm
- Fiskal modul (1 BHM/yil ÷ 12, taxmin): ~33,000-37,500 so'm
- **Jami: ~58,380–69,730 so'm/oy/tenant**

Natija: Start narxi (49,000 so'm) hali ham **yetarli emas** — bu stack bilan ham ~9,000-21,000 so'm/oy zarar chiqadi (asosan fiskal modul yillik to'lovi tufayli). Lekin bu partner yo'liga nisbatan SEZILARLI yaxshiroq (zarar 5-10 marta kichik) — chunki davlat ro'yxatidan o'tish bepul va faqat majburiy fiskal modul to'lovi qoladi, ustiga qo'yilgan tijorat partner marjasi yo'q. Buning uchun o'z dasturimizni davlat virtual-kassa reyestrida texnik servis markazi/ishlab chiquvchi sifatida ro'yxatdan o'tkazish zarur — bu bir martalik muhandislik/sertifikatlash ishi, lekin oylik qaytariladigan xarajatni tubdan kamaytiradi.

**Variant C — Narxni oshirish (Start'ni 59,000-69,000 so'mga ko'tarish) + o'z-reyestr yo'li**

Variant B stackida (~58,000-70,000 so'm/oy xarajat) Start narxini 69,000 so'mga ko'tarsak:
- Marja: 69,000 - 58,380 (eng past xarajat) = **+10,620 so'm/oy** dan 69,000 - 69,730 = **-730 so'm/oy** gacha — hali ham tor, lekin musbat tomonga yaqinroq.

Bu narx hali ham REGOS'ning asosiy tarifi (69,000 so'm, virtual kassasiz) bilan teng — raqobatbardosh, ayniqsa bizning narx "virtual kassa included" bo'lgani uchun REGOS'ning jami 144,000 so'm/oyiga nisbatan ancha arzon qoladi.

**Variant D — Start'ni 49,000 so'mda saqlash + foydalanish chegaralari (kassa/kvitansiya/AI cap)**

Agar narx o'zgarmasin, lekin quyidagi cheklovlar kiritilsa:
- 1 kassa/nuqta (allaqachon rejalashtirilgan)
- Oyiga kvitansiya/tranzaksiya soni chegarasi (masalan, 1,500-2,000 ta/oy) — SMS va hosting xarajatini nazorat qiladi, chunki eslatma SMS soni savdo hajmiga proportsional
- AI cap (allaqachon rejalashtirilgan)
- **Virtual kassa — ALOHIDA to'lovli qo'shimcha** (REGOS modeli kabi), Start narxiga "bundle ichida bepul" deb KIRITILMASIN, balki +qo'shimcha narx (masalan +25,000-40,000 so'm/oy, davlat-reyestr yo'li bilan hisoblangan xarajatni qoplaydigan darajada) sifatida sotilsin

Bu variant eng realist — chunki asosiy muammo "OFD/virtual kassa bepul" degan va'da, bu xarajatning eng katta va eng beqaror qismi. Boshqa barcha komponentlar (hosting, AI, SMS, to'lov komissiyasi) Start narxiga nisbatan kichik va boshqariladigan (~25,000-30,000 so'm/oy jami, davlat-reyestr fiskal modul to'lovisiz).

### Tavsiya (+ ishonch darajasi)

**Tavsiya: Variant D (narxni 49,000 so'mda saqlash, lekin virtual kassani Start ichida "bepul bundle" qilib EMAS, alohida qo'shimcha xizmat sifatida sotish) + Variant B (o'z dasturni davlat reyestrida ro'yxatdan o'tkazish, tijorat OFD partnyoriga bog'lanmaslik).**

Asoslash:
1. Eng katta topilma — **OFD/virtual-kassa partner to'lovi (75,000-155,500 so'm/oy/kassa) yolg'iz o'zi Start narxidan (49,000 so'm) katta**. Agar "virtual kassa included" va'dasini partner orqali bajarsak, har bir Start mijozida muntazam zarar ko'ramiz. Bu hozirgi spec'dagi "Start — OFD virtual kassa included" tilini qayta ko'rib chiqishni talab qiladi.
2. Davlat reyestriga bepul ro'yxatdan o'tish imkoniyati mavjud (my.gov.uz/soliq xizmati), bu yo'l tijorat partner marjasini butunlay olib tashlaydi va faqat majburiy fiskal modul yillik to'lovini (1 BHM, taxminan 400-450 ming so'm/yil) qoldiradi — bu ham katta, lekin boshqariladigan xarajat.
3. SMS xarajati **bizning asl taxminimizdan ancha arzonroq** chiqdi — Eskiz.uz bo'yicha 95 so'm/SMS flat, oyiga ~1,900-4,750 so'm/tenant (asl taxmin 5,000-10,000 so'm edi). Bu gap endi yopildi va yaxshi tomonga.
4. Click/Payme komissiyasi (1-2%) taxminimizni tasdiqladi — bu kichik qo'shimcha xarajat (~980 so'm/oy agar o'z obuna to'lovimiz ham shu kanal orqali o'tsa).
5. Hosting + AI + SMS + to'lov komissiyasi jami taxminan **25,000-31,000 so'm/oy/tenant** — bu Start narxiga (49,000 so'm) nisbatan sog'lom, ~18,000-24,000 so'm/oy musbat marja qoldiradi, **OFD xarajatini hisobga olmaganda**. Demak muammo faqat OFD/virtual-kassa qismida — qolgan model asosan to'g'ri edi.

**Yakuniy raqamlar (Variant D, davlat-reyestr yo'li, virtual kassa alohida add-on sifatida, taxminan +30,000 so'm/oy):**
- Start asosiy xarajat (OFD'siz): ~25,000-31,000 so'm/oy
- Start narxi: 49,000 so'm/oy
- **Marja (OFD'siz, asosiy Start)**: ~18,000-24,000 so'm/oy — sog'lom
- Virtual-kassa add-on narxi taklifi: +30,000-40,000 so'm/oy (fiskal modul + operatsion xarajatni qoplash uchun)
- Qo'shimcha add-on marjasi: taxminan 0 dan +5,000 so'm/oy (fiskal modul yillik to'lovi noaniqligi tufayli tor)

**Ishonch darajasi:**
- SMS narxi (Eskiz.uz 95 so'm/SMS) — **yuqori** ishonch, rasmiy saytdan to'g'ridan-to'g'ri olingan.
- Click/Payme komissiyasi (1-2%) — **yuqori** ishonch, ikki kompaniyaning rasmiy tarif sahifalaridan olingan, ammo aniq tarif toifasi (POS vs billing/integratsiya) bizning holatimiz uchun qaysi toifaga tushishi hali **tasdiqlanmagan**.
- OFD partner to'lovi (75,000-155,500 so'm/oy) — **o'rta** ishonch — ikki konkret misol (REGOS, Multikassa) topildi, lekin ular bizning aniq integratsiya shartlarimizni aks ettirmaydi; real narx muzokaraga bog'liq bo'lishi mumkin.
- Davlat-reyestr yo'lining bepulligi — **o'rta** ishonch — rasmiy davlat xizmati sahifasida tasdiqlangan, lekin texnik servis markazi sifatida ro'yxatdan o'tish shartlari (kapital, sertifikatlash xarajati) alohida **tasdiqlanmagan**.
- 1 BHM 2026-yil qiymati — **past** ishonch, qidiruv limiti tugagani sababli tasdiqlanmagan, taxmin sifatida belgilangan.
- SaaS obuna to'lovini Click/Payme komissiyasini o'zi yutishi amaliyoti — **past** ishonch, alohida manba bilan tasdiqlanmagan, umumiy bozor amaliyotiga asoslangan taxmin.

### Manbalar

- https://eskiz.uz/uz/sms
- https://playmobile.uz/uz/instruction/
- https://www.spot.uz/oz/2025/02/15/sms-notification/
- https://click.uz/uz/tarifs
- https://business.click.uz/uz
- https://joinposter.com/en/applications/multikassa
- https://regos.uz/uz/product/regos-vcr/faq
- https://my.gov.uz/uz/service/627
- https://kun.uz/50403927
- https://www.gov.uz/oz/soliq/page/virtual-kassa-reestri?lang=ru
- https://soliq.uz/page/virtual-kassa-reestri?lang=ru (asl havola, yuqoridagi manzilga yo'naltiriladi)
- https://www.spot.uz/oz/2026/10/14/dollar-yana-oshdi (1$ ≈ 11,963 so'm, 15.10.2026 kursi uchun)
