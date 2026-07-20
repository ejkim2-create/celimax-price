#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CELIMAX 가격 자동 갱신 + 이력 기록 (제품에 채널코드 내장). 의존성: pip install requests"""
import json, os, sys, time, datetime, re
try:
    import requests
except ImportError:
    print("requests 필요: pip install requests", file=sys.stderr); sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
HISTORY_FILE = os.path.join(HERE, "history.json")
MAX_SNAPSHOTS = 3000
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
S = requests.Session(); S.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})

WB_WALLET = 0.02  # WB 지갑 할인율(빨간 가격). WB가 바꾸면 이 숫자만 수정 (예: 3%면 0.03, 미적용이면 0)

def get_wb(nm):
    if not nm: return None
    u = "https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm=%s" % nm
    try:
        r = S.get(u, timeout=15); r.raise_for_status()
        ps = r.json().get("data", {}).get("products", [])
        if not ps: return None
        p = ps[0]
        base = None
        for sz in p.get("sizes", []):
            v = (sz.get("price") or {}).get("product")
            if v: base = v; break
        if base is None:
            for k in ("salePriceU","priceU"):
                if p.get(k): base = p[k]; break
        if base is None: return None
        return int(base/100*(1-WB_WALLET))  # 지갑가(빨간 가격)
    except Exception as e:
        print("  [WB]", nm, e, file=sys.stderr)
    return None

def get_ozon(code):
    if not code: return None
    url = "https://www.ozon.ru/product/%s/" % code
    try:
        r = S.get(url, timeout=20)
        if r.status_code != 200: return None
        m = re.search(r'"finalPrice"\s*:\s*"?(\d[\d\s ]*)', r.text) or \
            re.search(r'"cardPrice".*?(\d[\d\s ]{2,})\s*₽', r.text)
        if m: return int(re.sub(r"[^\d]", "", m.group(1)))
    except Exception as e:
        print("  [Ozon]", code, e, file=sys.stderr)
    return None

def get_mall(url):
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
    for seller in data["sellers"]:
        for it in seller["items"]:
            if it.get("wb_nm"):
                v = get_wb(it["wb_nm"]);  it["wb"] = v if v else it.get("wb"); time.sleep(0.3)
            if it.get("ozon_code"):
                v = get_ozon(it["ozon_code"]);  it["ozon"] = v if v else it.get("ozon"); time.sleep(0.3)
            if it.get("mall_url"):
                v = get_mall(it["mall_url"]);  it["mall"] = v if v else it.get("mall"); time.sleep(0.3)

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
    print("완료:", snap["ts"], "· 판매자", len(data["sellers"]))

if __name__ == "__main__":
    main()
