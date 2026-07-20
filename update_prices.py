#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CELIMAX 3채널 가격 자동 갱신 스크립트
------------------------------------------------
data.json 을 읽어 각 제품의 채널별 최신 판매가를 가져와 다시 저장한다.
cron 으로 매일 실행하면 웹사이트가 자동으로 최신 가격을 보여준다.

동작 방식
  - Wildberries : 공개 JSON API(card.wb.ru) 로 즉시 조회 가능 → nm(상품번호)만 넣으면 바로 작동.
  - Ozon / 공식몰(podrygka.ru) : 강력한 봇 차단이 있어 상품 URL과 파싱 규칙 설정이 필요.
                                 (SELLERS 참고. 미설정 시 기존 값 유지)

준비물 (products.json — data.json 과 같은 폴더)
  각 제품의 채널 식별자를 매핑한다. 예:
  [
    {"name_ko":"셀리맥스 듀얼배리어 크리미 토너 150ml",
     "wb_nm": 123456789,
     "ozon_url": "https://www.ozon.ru/product/...-123/",
     "mall_url": "https://podrygka.ru/catalog/...-toner/"},
    ...
  ]
  name_ko 로 data.json 항목과 매칭한다. 없는 필드는 건너뛰고 기존 값을 유지한다.

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
PRODUCTS_FILE = os.path.join(HERE, "products.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})


def get_wb_price(nm):
    """Wildberries 판매가(₽, 정수) 반환. 실패 시 None."""
    if not nm:
        return None
    url = ("https://card.wb.ru/cards/v2/detail"
           "?appType=1&curr=rub&dest=-1257786&spp=30&nm=%s" % nm)
    try:
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
        prods = r.json().get("data", {}).get("products", [])
        if not prods:
            return None
        p = prods[0]
        # 신규 스키마: sizes[].price.product (코펙 단위, 100으로 나눔)
        for sz in p.get("sizes", []):
            price = (sz.get("price") or {}).get("product")
            if price:
                return round(price / 100)
        # 구 스키마 fallback
        for key in ("salePriceU", "priceU"):
            if p.get(key):
                return round(p[key] / 100)
    except Exception as e:
        print("  [WB] %s 실패: %s" % (nm, e), file=sys.stderr)
    return None


def get_ozon_price(url):
    """
    Ozon 은 봇 차단이 강해 단순 requests 로는 대부분 막힌다.
    운영 환경(회사 서버 고정 IP)에서 아래를 상황에 맞게 구현/보강하세요.
    옵션: (1) Ozon Seller API,  (2) 헤드리스 브라우저(Playwright),  (3) 가격 피드.
    미구현 상태에서는 None 을 반환해 기존 값을 유지한다.
    """
    if not url:
        return None
    try:
        r = SESSION.get(url, timeout=20)
        if r.status_code != 200:
            return None
        m = re.search(r'"finalPrice"\s*:\s*"?(\d[\d\s ]*)', r.text)
        if not m:
            m = re.search(r'"cardPrice".*?(\d[\d\s ]{2,})\s*₽', r.text)
        if m:
            return int(re.sub(r"[^\d]", "", m.group(1)))
    except Exception as e:
        print("  [Ozon] %s 실패: %s" % (url, e), file=sys.stderr)
    return None


def get_mall_price(url):
    """공식몰(podrygka.ru) 상품 페이지에서 가격 추출(best-effort)."""
    if not url:
        return None
    try:
        r = SESSION.get(url, timeout=20)
        if r.status_code != 200:
            return None
        # 사이트 구조에 맞게 정규식/셀렉터 보강 필요
        m = re.search(r'itemprop="price"[^>]*content="(\d+(?:\.\d+)?)"', r.text)
        if not m:
            m = re.search(r'"price"\s*:\s*"?(\d[\d\s ]{2,})', r.text)
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
    else:
        print("products.json 이 없습니다. 채널 식별자 매핑을 추가하면 자동 조회가 활성화됩니다.",
              file=sys.stderr)

    updated = 0
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
                    if it.get(key) != val:
                        updated += 1
                    it[key] = val
                time.sleep(0.4)  # 예의상 간격

    data["date"] = datetime.date.today().isoformat()

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("완료: %s · 갱신된 가격 %d건" % (data["date"], updated))


if __name__ == "__main__":
    main()
