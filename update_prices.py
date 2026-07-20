#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CELIMAX 가격 자동 갱신 + 이력 기록 (판매자별 구조)
data.json     : {updated, sellers:[{id,name_*,items:[{name_*,rec,ozon,wb,mall}]}]}
history.json  : {snapshots:[{ts, s:{sellerId:[{k,r,o,w,m}]}}]}
products.json : (선택) [{name_ko, wb_nm, ozon_url, mall_url}]
의존성: pip install requests
"""

import json, os, sys, time, datetime, re

try:
    import requests
except ImportError:
    print("requests 필요:  pip install requests", file=sys.stderr); sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
HISTORY_FILE = os.path.join(HERE, "history.json")
PRODUCTS_FILE = os.path.join(HERE, "products.json")
MAX_SNAPSHOTS = 3000

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})


def wb(nm):
    if not nm: return None
    u = "https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm=%s" % nm
    try:
        r = S.get(u, timeout=15); r.raise_for_status()
        ps = r.json().get("data", {}).get("products", [])
        if not ps: return None
        p = ps[0]
        for sz in p.get("sizes", []):
            v = (sz.get("price") or {}).get("product")
            if v: return round(v/100)
        for k in ("salePriceU","priceU"):
            if p.get(k): return round(p[k]/100)
    except Exception as e:
        print("  [WB]", nm, e, file=sys.stderr)
    return None


def ozon(url):
    if not url: return None
    try:
        r = S.get(url, timeout=20)
        if r.status_code != 200: return None
        m = re.search(r'"finalPrice"\s*:\s*"?(\d[\d\s ]*)', r.text) or \
            re.search(r'"cardPrice".*?(\d[\d\s ]{2,})\s*₽', r.text)
        if m: return int(re.sub(r"[^\d]", "", m.group(1)))
    except Exception as e:
        print("  [Ozon]", url, e, file=sys.stderr)
    return None


def mall(url):
    if not url: return None
    try:
        r = S.get(url, timeout=20)
        if r.status_code != 200: return None
        m = re.search(r'itemprop="price"[^>]*content="(\d+(?:\.\d+)?)"', r.text) or \
            re.search(r'"price"\s*:\s*"?(\d[\d\s ]{2,})', r.text)
        if m: return int(re.sub(r"[^\d]", "", m.group(1)))
    except Exception as e:
        print("  [Mall]", url, e, file=sys.stderr)
    return None


def main():
    data = json.load(open(DATA_FILE, encoding="utf-8"))

    mapping = {}
    if os.path.exists(PRODUCTS_FILE):
        for p in json.load(open(PRODUCTS_FILE, encoding="utf-8")):
            mapping[p.get("name_ko", "").strip()] = p

    for seller in data["sellers"]:
        for it in seller["items"]:
            cfg = mapping.get(it.get("name_ko", "").strip())
            if not cfg: continue
            for field, fn, key in (("wb_nm", wb, "wb"), ("ozon_url", ozon, "ozon"), ("mall_url", mall, "mall")):
                if cfg.get(field):
                    v = fn(cfg[field])
                    if v: it[key] = v
                    time.sleep(0.4)

    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    data["updated"] = now.strftime("%Y-%m-%d")
    json.dump(data, open(DATA_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    snap = {"ts": now.strftime("%Y-%m-%d %H:%M"), "s": {}}
    for seller in data["sellers"]:
        snap["s"][seller["id"]] = [{"k": it["name_ko"], "r": it["rec"], "o": it["ozon"],
                                    "w": it["wb"], "m": it["mall"]} for it in seller["items"]]

    hist = json.load(open(HISTORY_FILE, encoding="utf-8")) if os.path.exists(HISTORY_FILE) else {"snapshots": []}
    hist["snapshots"].append(snap)
    hist["snapshots"] = hist["snapshots"][-MAX_SNAPSHOTS:]
    json.dump(hist, open(HISTORY_FILE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    print("완료:", snap["ts"], "· 판매자", len(data["sellers"]), "· 스냅샷", len(hist["snapshots"]))


if __name__ == "__main__":
    main()
