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

# 프록시(러시아 IP 우회): GitHub Secret PROXY_URL 에 넣으면 자동 적용. 없으면 그냥 직접 접속.
PROXY_URL = os.environ.get("PROXY_URL", "").strip()
if PROXY_URL:
    S.proxies.update({"http": PROXY_URL, "https": PROXY_URL})
    print("프록시 사용 중")

WB_WALLET = 0.02  # WB 지갑 할인율(빨간 가격). WB가 바꾸면 이 숫자만 수정 (예: 3%면 0.03, 미적용이면 0)

def get_wb(nm):
    if not nm: return None
    u = "https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm=%s" % nm
    try:
        r = S.get(u, timeout=15); r.raise_for_status()
        ps = r.json().get("data", {}).get("products", [])
        if not ps: return None
        p = ps[0]
