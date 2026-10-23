base = r'E:/Project/erp/spec/kod-uchun/'


def apply(fn, pairs):
    p = base + fn
    s = open(p, encoding='utf-8').read()
    for old, new, cnt in pairs:
        assert s.count(old) == cnt, (fn, s.count(old), old[:90])
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8', newline='').write(s)
    print('ok', fn)


apply('24-frontend-arxitekturasi.md', [
    ("natija (`fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`) chekka chop etiladi va `sale.created` voqeasi bilan sinxronlanadi;",
     "natija (`fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`, `fiscal_at`) chekka chop etiladi va outbox voqeasiga (`sale.created`, `return.created`, `debt_payment.created`) `fiscal_result` sifatida yoziladi (`18-api-kassa.md` §4.1);", 1),
])

apply('25-nofunksional-talablar.md', [
    ("lokal fiskal ko'prik tanlansa Bosqich 5 dan oldin, aks holda Bosqich 7 dan oldin kerak.",
     "lokal fiskal ko'prik tanlansa Bosqich 5/6 pilotidan oldin, aks holda Bosqich 7 dan oldin kerak (qaror #38).", 1),
])

apply('28-android-pos.md', [
    ("kassir `card_type` (`personal/corporate/social/unknown`, `method='card'` da majburiy),",
     "kassir `card_type` (`personal/corporate/social/unknown`, `method='card'` da majburiy; standart qiymat yo'q — kassir har to'lovda tanlaydi, qaror #64),", 1),
    ("(online va offline) — `card_type` majburiy, ijtimoiy kartada",
     "(online va offline) — `card_type` majburiy (standart qiymat yo'q — kassir har to'lovda tanlaydi, qaror #64), ijtimoiy kartada", 1),
])
