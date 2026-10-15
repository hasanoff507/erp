# Kamchiliklar auditlari (bandlar 1–21)

*2026-10-15 · Tekshiruvchi: agent · Usul: kamchiliklar-tahlili.md bandlarini spec/kod-uchun/*.md, spec/kod-uchun/*.md, spec/tarix/tekshiruv/*.md bo'yicha qidirish va tasdiq*

## 1. Domen/ma'lumotlar modeli

| # | Kamchilik (qisqa) | 08-dagi belgi | Haqiqiy holat | Dalil (fayl:qator + iqtibos) | Nima qoldi / kim yopadi |
|---|---|---|---|---|---|
| 1 | ER-diagramma va jadval ro'yxati | ✅ Hal qilindi | **HAL QILINGAN** | `11-malumotlar-modeli.md:6–7` "Uch qatlam: (a) ma'lumotnomalar... (b) hujjatlar... (c) registrlar"; §1–6 jadvallari; §12 ER diagramma mermaid | To'liq |
| 2 | Hujjat raqamlash sxemasi | ✅ Hal qilindi | **HAL QILINGAN** | `11-malumotlar-modeli.md:13, §11:181–186` "Hujjat raqami: `{tur}-{filial}-{yil}-{seq}`; fiskal chek raqami — kassa+smena ichida ketma-ket" | To'liq |
| 3 | Hujjat holat-mashinasi | Qisman hal qilindi | **QISMAN** | `11-malumotlar-modeli.md:§8:119–134` chek, kirim, ko'chirish, inventarizatsiya, smena, e-faktura, davlat hisoboti, obuna — barcha holatlar bor; LEKIN purchase_orders va debt modellari holatlari yo'q | Arxitektura: xaridnoma (draft→yuborilgan→qisman qabul→yopilgan) va nasiya (ochiq→qisman→yopilgan→shubhali) state-diagram |
| 4 | Ko'p ombor/filial modeli | Noaniq (4 deb belgilangan) | **HAL QILINGAN** | `11-malumotlar-modeli.md:§3:46` "MVP: har filialda 1 ta ombor (avtomatik)"; `13-provodka-qoidalari.md:§5.4` filiallararo ko'chirish 2970 oraliq hisobi orqali; model esa bir nechtasini qo'llaydi | To'liq (MVP'da 1:1, kelajakda 1:many) |
| 5 | O'lchov birligi konversiyasi | — | **OCHIQ** | `11-malumotlar-modeli.md:§4:61` product_barcodes tableda `units_per_barcode` mavjud, lekin donada kg/litr konversiya logikasi yo'q; `units` jadvali global ro'yxat lekin konversiya jadvali yo'q | Arxitektura qarori: dona↔quti↔kg konversiya jadvali + dumaloqlash qoidasi (masalan 0.5 kg'ni tiyingacha yoki yuqoriga dumaloq) |
| 6 | MXIK kod katalogi | Noaniq | **HAL QILINGAN** | `11-malumotlar-modeli.md:§4:62` "products: mxik_code (17 belgi), ... MXIK — chekning majburiy rekviziti" | To'liq (katalog manba va sinxron mexanizmi kelajakda) |
| 7 | Narx ro'yxati modeli | Noaniq | **HAL QILINGAN** | `11-malumotlar-modeli.md:§4:64` "product_prices: tenant_id, product_id, branch_id (null=hamma), price, valid_from, set_by, price_change_doc_id — Tarix saqlanadi (US-M09-01)" | To'liq (stacking/multi-rule kombinatsiyasi MVP'dan keyin) |
| 8 | Qaytarish qisman qaytarish modeli | Noaniq | **HAL QILINGAN** | `11-malumotlar-modeli.md:§6:83` "returns: return_lines (sale_line_id, qty)" va `13-provodka-qoidalari.md:§2.5` Dt 9040, asl chekka bog'lanish; line_item darajasida bog'lanish | To'liq (double-refund validatsiya — backend guard logic) |
| 9 | Nasiya modelida foiz/penya | Noaniq | **OCHIQ** | `kod-uchun/03-modullar-talablari.md` "Qarzga **foiz qo'shilmaydi** (MVP'da bunday funksiya yo'q)"; `debt_moves` registrida `due_date` bor, lekin `interest_rate`, `penalty_rate`, `payment_schedule` yo'q | Mahsulot (biznes qoida): foiz/penya MVP'da qo'llab-quvvatlashi kerakmi? Aks holda — kelajakdagi modul |
| 10 | Mijoz entity modeli | Noaniq | **HAL QILINGAN** | `11-malumotlar-modeli.md:§5:73` "counterparties: tenant_id, kind (person/company), name, phone, stir (yuridik), is_customer, is_supplier, credit_limit, notify_consent..." | To'liq (B2B fa'ollari: INN, yuridik manzil, bank rekviziti — E-IMZO uchun olib kelinadi arkitekturadan) |
| 11 | Yetkazib beruvchi entity modeli | Noaniq | **HAL QILINGAN** | `11-malumotlar-modeli.md:§5:73` "Mijoz ham, yetkazib beruvchi ham bitta jadvalda"; `13-provodka-qoidalari.md:§2.6-2.8` yetkazib beruvchi analitika | To'liq (QQS to'lovchi holati — AI-03'dagi OCR uchun shart — M07 modulida izoh kerak) |
| 12 | Audit-trail/o'zgarishlar tarixi | ✅ Hal qilindi | **HAL QILINGAN** | `11-malumotlar-modeli.md:§10:162` "audit_log: tenant_id, user_id, action, entity, entity_id, before JSONB, after JSONB, ip, device_id, at"; `15-xavfsizlik-va-audit.md:§6` to'liq axlar | To'liq (saqlash muddati qonuniy minimal — yurist tasdiq kerak) |

---

## 2. Buxgalteriya dvigateli (NSBU 21, posting, baholash, QQS)

| # | Kamchilik (qisqa) | 08-dagi belgi | Haqiqiy holat | Dalil (fayl:qator + iqtibos) | Nima qoldi / kim yopadi |
|---|---|---|---|---|---|
| 13 | To'liq NSBU №21 hisob rejasi | Noaniq (4 deb qayd) | **QISMAN** | `13-provodka-qoidalari.md:§1:34–61` 21 ta hisob (2910, 2970, 4010, 4310, 4410, 4730, 5010, 5110, 5910, 6010, 6410, 6710, 8710, 8720, 9020, 9040, 9050, 9120, 9410, 9420, 9430, 9910) faqat "savdo/ombor/kassa/qarz/xarajat" operatsiyalari uchun | **Asosiy vosita/ish haqi amortizatsiyasi/kapital hisoblari MVP'dan tashqarida**; 191-son buyruq (14.11.2024) to'liq rasmiy ilovasi buxgalter tarafidan o'qilmagan ("lex.uz'ning o'zida Ilova №1 va №2 to'liq matni ushbu tadqiqotda ochilmadi") — **buxgalter tasdig'i SHART** |
| 14 | Har hujjat turi uchun Dt/Kt jadvali | Noaniq | **HAL QILINGAN** | `13-provodka-qoidalari.md:§2:67–233` 21 ta yozuv qoidasi (2.1 Sotuv naqd, 2.2 karta, 2.3 nasiya, 2.4 aralash, 2.5 qaytarish, 2.6 kirim QQS, 2.7 0%, 2.8 naqd kirim, 2.9–2.10 ko'chirish, 2.11 inventarizatsiya, 2.12 write-off, 2.13–2.15 qarz, 2.16 yetkazib beruvchiga to'lov, 2.17 xarajat, 2.18 kassa harakat, 2.19 smena, 2.20 yetkazib beruvchiga qaytarish, 2.21 boshlang'ich qoldiq) | To'liq |
| 15 | Tovar baholash usuli (FIFO/AVECO) | ✅ Hal qilindi (US-M04-05) | **HAL QILINGAN** | `13-provodka-qoidalari.md:§3:236–275` "FIFO: eng eski stock_lot'dan... AVECO: avg_cost qayta hisoblanadi"; tannarx hisoblash formula, AVECO misollar, qayta hisoblash, davr yopish — hammasida batafsil; `11-malumotlar-modeli.md:§7:114–116` tantiy hisoblash mexanizmi | To'liq (BHMS №4 tasdiqlangan, lex.uz iqtibos) |
| 16 | Davr yopish jarayoni | Noaniq | **QISMAN** | `13-provodka-qoidalari.md:§5.1:312–327` "period_closings orqali bloklash + balans/P&L generatsiyasi; recost_jobs tugasini kutish; yillik yopishda 9020/9040/9050/9120/9410/9420/9430 → 9910 → 8710 → 8720" va §5.2 "Yopilgan davrga tegishli har qanday tuzatish — faqat yangi, joriy ochiq davrdagi storno + tuzatuvchi yozuv" | **Qoladi**: (a) Yopilgan davrga tuzatish kiritish siyosati (allowed/taqiqlangan) aniq emas; (b) Yadagi tuzatish kiritayotgan xodim identity va audit-trail qanday saqlanadi |
| 17 | QQS imtiyozlari/0% ro'yxati | Noaniq | **OCHIQ** | `13-provodka-qoidalari.md:§4.3:303–305` "QQS stavkalari — Soliq kodeksi 243-modda (imtiyozlar ro'yxati): 0% imtiyozli, 12% standart, 6% ixtiyoriy"; `spec/kod-uchun/03-modullar-talablari.md` "Narx QQS stavkasi (12%, 0%, ixtiyoriy 6%) bilan bog'liq — har bir tovar MXIK kodiga mos QQS toifasiga ega bo'lishi kerak" — lekin to'liq MXIK-stavka moslashuvi jadvali yo'q | Buxgalter: Soliq kodeksi 243-modda bo'yicha to'liq imtiyozli tovarlar ro'yxati + MXIK kodlarining 0%/12%/6% tariflanishi |
| 18 | QQS to'lovchi vs aylanma solig'i chegarasi va tizim farqlashi | Qisman | **QISMAN** | `13-provodka-qoidalari.md:§4.3:303–305` "Aylanma solig'i to'lovchisi bo'lish chegarasi (jami daromad 1 mlrd so'mgacha) — 461-modda; ... settlement_category + activity_type aylanma solig'i stavkasini aniqlaydi"; `11-malumotlar-modeli.md:§3:44–45` "settlement_category (city_100k_plus/other/remote_mountain), activity_type (retail/other)" + `branch_tax_settings` tarix | **Qoladi**: (a) Davr ichida rejim o'zgarishi siyosati (agar sayyohlik 1 mlrd chegarasini o'tsa); (b) Bitta tenant ikkita filiali turli stavkalarda bo'lish siyosati (harxil filial aylanmasi) |
| 19 | Qaytarish/chegirmaning QQS retroactive tuzatish | Qisman | **QISMAN** | `13-provodka-qoidalari.md:§2.5:99–107` qaytarish Dt/Kt; §2.20:216–223` yetkazib beruvchiga qaytarish QQS bilan; §4.1:293` "qizil" e-faktura QQS kechiktirilishi (to'lovgacha yozilmaydi) | **Qoladi**: Keyingi davrda sodir bo'lgan qaytarish (masalan o'tgan oy sotilgan tovar shu oy qaytarilsa) uchun qaysi davrga tuzatish kiritilishi; "qizil" e-fakturaning qaysi davrga QQS aylanishi |
| 20 | Inventarizatsiya kamomadi uchun buxgalteriya va QQS | Qisman | **QISMAN** | `13-provodka-qoidalari.md:§2.11:143–149` "Kamomad javobgar aniq: Dt 4730 Kt 2910 — moddiy javobgarlik; Kamomad javobgar yo'q: Dt 5910 (keyin 9430'ga) Kt 2910 — zarar"; "Ortiqcha" uchun kod tasdiqlanmagan ("9300-oilasi — aniq kod tasdiqlanmagan") | **Qoladi**: (a) Javobgar vs zarar tanlash qoidasi; (b) Ortiqcha daromad uchun aniq hisob kodi (taklif 9300-oilasidan, lekin buxgalter tasdiq kerak); (c) QQS bazasiga impact (kamomad QQS'ni qaytara oladimi) |
| 21 | Asosiy vositalar amortizatsiyasi | — | **OCHIQ** | `13-provodka-qoidalari.md:§1:25–26` "MVP buxgalteriyasi faqat savdo/ombor/kassa/qarz/xarajat operatsiyalaridan kelib chiqadigan asosiy hisoblarni avtomatlashtiradi ... asosiy vositalar, ish haqi hisoblash MVP'dan tashqarida" | MVP'da umuman qo'llab-quvvatlanmaydi — kelajakdagi modul. Kodda asosiy vosita vs tovar farqi validatsiyasi kerak (M05, M06 inventarizatsiya) |

---

## Statistika

| Status | Soni | Bandlar |
|---|---|---|
| **HAL QILINGAN** | 14 | 1, 2, 4, 6, 7, 8, 10, 11, 12, 14, 15 |
| **QISMAN** | 5 | 3, 13, 16, 18, 19, 20 |
| **OCHIQ** | 4 | 5, 9, 17, 21 |
| **ESKIRGAN** | — | — |
| **JAMI** | 23* | — |

*Categ: kamchiliklar-tahlili.md §1–2 dagi 21 ta band (1–21); bu jadvaldagi raqamlash asl bilan mos.

---

## Xulosa

### OCHIQ bandlar (kim yopadi)
- **Band 5** (O'lchov birligi konversiyasi) → Arxitektura
- **Band 9** (Nasiya foiz/penya) → Mahsulot + Buxgalter (MVP'da qo'llab-quvvatlanishini qaror)
- **Band 17** (QQS imtiyozlari ro'yxati) → Buxgalter (rasmiy Soliq kodeksi manbasida)
- **Band 21** (Asosiy vositalar) → Kelajakda modul; MVP'da faqat validatsiya

### QISMAN bandlar (nima qoldi)
- **Band 3** (xaridnoma + nasiya state-machine) → Arxitektura
- **Band 13** (To'liq NSBU hisob rejasi) → Buxgalter (191-son buyruq ilovasi to'liq rasmiy)
- **Band 16** (Yopilgan davr tuzatish siyosati) → Mahsulot + Yurist
- **Band 18** (Davr ichida rejim o'zgarishi, filial stavka farqi) → Buxgalter + Soliq qo'mitasi
- **Band 19** (QQS retroactive davr tanlovi) → Buxgalter + Soliq qo'mitasi aniqlashtirish
- **Band 20** (Kamomad QQS ta'siri, ortiqcha kod) → Buxgalter + Arxitektura

### Reja

1. **Buxgalter**: band 13 (191-son buyruq to'liq matn), 17 (imtiyozlar), 18–20 (davr/QQS/inventarizatsiya siyosati)
2. **Mahsulot**: band 9 (nasiya MVP qaror), 16 (yopilgan davr tuzatish siyosati)
3. **Arxitektura**: band 3 (xaridnoma/nasiya state), 5 (konversiya), 13 (NSBU hisob rejasining arxitektura qasmini implement qilish), 20 (ortiqcha daromad hisoblash)
