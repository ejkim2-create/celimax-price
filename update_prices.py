#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CELIMAX 3채널 가격 자동 갱신 + 이력(history) 기록 스크립트
- data.json : 최신 가격 (사이트 기본 표시)
- history.json : 실행 때마다 시각과 함께 스냅샷을 누적 (과거 가격 조회용)
의존성:  pip install requests
"""

import json, os, sys, time, datetime, re

try:
    import requests
except ImportError:
    print("requests 모듈이 필요합니다:  pip install requests", file=sys.stderr)
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
HISTORY_FILE = os.path.join(HERE, "history.json")
PRODUCTS_FILE = os.path.join(HERE, "products.json")

MAX_SNAPSHOTS = 2000

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})


def get_wb_price(nm):
    if not nm:
        return None
    url = ("https://card.wb.ru/cards/v2/detail"
           "?appType=1&curr=rub&dest=-1257786&spp=30&nm=%s" % nm)
    try:
        r = SESSION.get(url, timeout=15); r.raise_for_status()
        prods = r.json().get("data", {}).get("products", [])
        if not prods:
            return None
        p = prods[0]
        for sz in p.get("sizes", []):
            price = (sz.get("price") or {}).get("product")
            if price:
                return round(price / 100)
        for key in ("salePriceU", "priceU"):
            if p.get(key):
                return round(p[key] / 100)
    except Exception as e:
        print("  [WB] %s 실패: %s" % (nm, e), file=sys.stderr)
    return None


def get_ozon_price(url):
    if not url:
        return None
    try:
        r = SESSION.get(url, timeout=20)
        if r.status_code != 200:
            return None
        m = re.search(r'"finalPrice"\s*:\s*"?(\d[\d\s ]*)', r.text)
        if not m:
            m = re.search(r'"cardPrice".*?(\d[\d\s ]{2,})\s*₽', r.text)
        if m:
            return int(re.sub(r"[^\d]", "", m.group(1)))
    except Exception as e:
        print("  [Ozon] %s 실패: %s" % (url, e), file=sys.stderr)
    return None


def get_mall_price(url):
    if not url:
        return None
    try:
        r = SESSION.get(url, timeout=20)
        if r.status_code != 200:
            return None
        m = re.search(r'itemprop="price"[^>]*content="(\d+(?:\.\d+)?)"', r.text)
        if not m:
            m = re.search(r'"price"\s*:\s*"?(\d[\d\s ]{2,})', r.text)
        if m:
            return int(re.sub(r"[^\d]", "", m.group(1)))
    except Exception as e:
        print("  [Mall] %s 실패: %s" % (url, e), file=sys.stderr)
    return None


def main():
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    mapping = {}
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, encoding="utf-8") as f:
            for p in json.load(f):
                mapping[p.get("name_ko", "").strip()] = p

    for it in data["items"]:
        cfg = mapping.get(it.get("name_ko", "").strip())
        if not cfg:
            continue
        for ch, getter, key in (("wb_nm", get_wb_price, "wb"),
                                 ("ozon_url", get_ozon_price, "ozon"),
                                 ("mall_url", get_mall_price, "mall")):
            if cfg.get(ch):
                val = getter(cfg[ch])
                if val:
                    it[key] = val
                time.sleep(0.4)

    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    data["date"] = now.strftime("%Y-%m-%d")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    snapshot = {
        "ts": now.strftime("%Y-%m-%d %H:%M"),
        "i": [{"k": it["name_ko"], "r": it["rec"], "o": it["ozon"],
               "w": it["wb"], "m": it["mall"]} for it in data["items"]],
    }
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            hist = json.load(f)
    else:
        hist = {"snapshots": []}
    hist["snapshots"].append(snapshot)
    hist["snapshots"] = hist["snapshots"][-MAX_SNAPSHOTS:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, separators=(",", ":"))

    print("완료: %s · 이력 스냅샷 %d개" % (snapshot["ts"], len(hist["snapshots"])))


if __name__ == "__main__":
    main()
