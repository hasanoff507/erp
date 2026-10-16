# Spike: `zxing-cpp` va GS1 DataMatrix (FNC1)

**Savol:** 26 #62 / OQ-064 (qaror #57, 27 Bosqich 0). **Sana:** 2026-10-16.
**Test:** `backend/tests/unit/test_spike_datamatrix.py`, vektorlar — `backend/tests/fixtures/datamatrix/vectors.json`.

## Nima tekshirildi

- **Versiyalar:** `zxing-cpp` 3.1.1 (Python, Windows wheel, Python 3.13); mustaqil enkoder sifatida `bwip-js` 4.11.4 (`bcid=gs1datamatrix`).
- **Vektorlar (5 ta, sintetik, Asl belgisi / CRPT ko'rinishida):** sut (`01`+`21`+`93`), tamaki qutisi (`01`+`21`+`8005`+`93`), poyabzal/kiyim (`01`+`21`(13)+`91`+`92`(44)), CSET 82 maxsus belgilari bilan serial (`!"%&'*+-./_,:`, imzoda `+ / =`), suv (`01`+`21`+`93`). Har biri uchun kutilgan element satri GS (`\x1d`) ajratgichlari bilan, AI ro'yxatidan qayta hisoblab tekshiriladi.
- **Tekshiruvlar:**
  1. zxing-cpp enkod (`create_barcode(hri, DataMatrix, gs1=True)`) → zxing-cpp dekod (`read_barcode`, `TextMode.Plain`): matn = element satri GS bilan; `content_type == GS1`; `symbology_identifier == "]d2"` (FNC1 birinchi pozitsiyada); `TextMode.HRI` esa `(01)…(21)…` ko'rinishini qaytaradi.
  2. bwip-js chizgan simvol (modul matritsasi fixture'da) → zxing-cpp dekod: xuddi shu natija.
  3. Qo'shimcha (qo'lda): 90° burilgan va kichik masshtab (2 px/modul, 1 modul quiet zone) ham o'qildi.

## Natija

16/16 test yashil. **Dekod** to'liq mos: FNC1 → `]d2` + GS1 kontent turi, o'zgaruvchan uzunlikdagi AI'lardan keyingi FNC1 → GS (`\x1d`), oxirgi AI'dan keyin ajratgich yo'q; mustaqil enkoder simvoli ham to'g'ri o'qiladi.

**Enkodda** uchta xususiyat bor (kod yozishda hisobga olinadi):

1. **Kirish HRI ko'rinishida bo'lishi shart** — `(01)…(21)…`; GS/boshqaruv belgilari bilan xom satr `gs1=True` rejimida rad etiladi (`Control characters are not supported by GS1`). Demak skaner bergan satrni chop etish uchun avval AI'larga ajratib HRI qilish kerak. Serialdagi `(`/`)` `\(`/`\)` deb ekranlanadi.
2. **Avtomatik o'lcham DMRE to'rtburchakni tanlashi mumkin** — uzun kodlarda (`92` imzo bilan) 24x48 DMRE chiqdi va identifikator `]d8` bo'ldi. Asl belgisi kvadrat ECC 200 kutadi, ko'p skanerlar DMRE'ni o'qimaydi. `rectangle=False` ta'sir qilmadi; yechim — `version=1…24` (kvadrat o'lchamlar) dan eng kichigini tanlash (testdagi `encode_square`), shunda 36x36 kvadrat va `]d2` chiqadi.
3. **GTIN nazorat raqamini tekshirmaydi** (noto'g'ri `01` qabul qilindi; bwip-js rad etadi) — tekshiruv domen qatlamida (`marking` moduli) bo'lishi kerak.

Diqqat: noma'lum kwarg'lar jim e'tiborsiz qoldiriladi, `version` ga satr berilsa jarayon yiqiladi (native crash) — faqat butun son bering.

## Xulosa

`zxing-cpp` 3.1.1 server tomonda GS1 DataMatrix (FNC1) uchun **yetarli**: dekod to'liq mos, enkod yuqoridagi uch qoida bilan (HRI kirish, majburiy kvadrat `version`, GTIN tekshiruvi o'zimizda) to'g'ri kvadrat GS1 simvol beradi. `bwip-js` server zahirasi **kerak emas**; bwip-js brauzer yorliqlari uchun qoladi (qaror #8) va ikkala enkoder bir-birining simvolini o'qishda mos. Ochiq qoldiq: haqiqiy Asl belgisi kodlari va fizik skaner (kamera/2D skaner, HID rejimida GS uzatilishi) bilan sinov — Bosqich 1 da, real yorliq namunalari bilan.
