#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compra_app.py
-------------
Aplicación CLI sencilla para Linux: introduce una URL de producto y analiza
motivos probables de compra con heurísticas (título, descripción y reseñas).
Dependencias: requests, beautifulsoup4
Instalación: pip install requests beautifulsoup4
Uso: ./compra_app.py  (modo interactivo)
"""

import sys
import re
import json
from collections import Counter, defaultdict
from urllib.parse import urlparse
from typing import List, Dict


import os
import time
import random
import re
import json
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter, Retry

# Rotación simple de User Agents (navegadores reales)
USER_AGENTS = [
    # Chrome Win
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox Win
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Edge Win
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

def make_session():
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.8, status_forcelist=[429, 500, 502, 503, 504], raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

def default_headers(url):
    ua = random.choice(USER_AGENTS)
    host = urlparse(url).netloc
    # Cabeceras que suelen ayudar frente a 403 básicos
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": os.environ.get("LANG", "es-ES,es;q=0.9,en;q=0.8"),
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Referer": f"https://{host}/",
        "Connection": "keep-alive",
    }

def fetch_html_resilient(url: str, timeout: int = 25) -> str:
    session = make_session()

    # Opcional: proxy/cookies desde variables de entorno
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})

    cookies_env = os.environ.get("SCRAPE_COOKIES")  # formato: "key1=val1; key2=val2"
    cookies = {}
    if cookies_env:
        for kv in cookies_env.split(";"):
            if "=" in kv:
                k, v = kv.strip().split("=", 1)
                cookies[k.strip()] = v.strip()

    # Intentos con ligera espera y rotación de UA
    for attempt in range(1, 4):
        headers = default_headers(url)
        try:
            resp = session.get(url, headers=headers, cookies=cookies or None, timeout=timeout, allow_redirects=True)
            # Algunos sites responden 403 a la primera, 200 tras retry con delay
            if resp.status_code == 403 and attempt < 3:
                time.sleep(0.8 * attempt)
                continue
            resp.raise_for_status()
            # Si la codificación no llega, intenta detectar
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        except requests.HTTPError as e:
            # Si 403 y tenemos cookies, pedir nuevo intento con otro UA
            if resp is not None and resp.status_code == 403 and attempt < 3:
                time.sleep(0.8 * attempt)
                continue
            raise
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(0.8 * attempt)
    raise RuntimeError("No se pudo obtener el HTML tras varios intentos")
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print("Falta una dependencia. Instala con:\n  pip install requests beautifulsoup4")
    sys.exit(1)

DRIVER_KEYWORDS = {
    "precio": [
        "precio", "barato", "oferta", "descuento", "rebaja", "económico", "relación calidad precio",
        "calidad-precio", "mejor precio", "coste", "costoso", "caro", "vale la pena"
    ],
    "calidad": [
        "calidad", "duradero", "resistente", "robusto", "bien hecho", "premium", "materiales",
        "acabados", "fiable", "funciona bien", "exacto", "preciso"
    ],
    "envío": [
        "envío", "llegó", "rápido", "entrega", "tardó", "tiempo", "prime", "logística", "paquete",
        "embalaje", "devolución", "devolver"
    ],
    "marca/confianza": [
        "marca", "oficial", "original", "autentico", "auténtico", "garantía", "confianza",
        "recomendado", "opiniones", "reseñas", "valoraciones"
    ],
    "características": [
        "característica", "función", "funciona", "especificación", "compatibilidad", "tamaño",
        "capacidad", "batería", "potencia", "velocidad", "memoria", "resolución"
    ],
    "usabilidad": [
        "fácil", "sencillo", "intuitivo", "instalar", "montar", "configurar", "manual", "instrucciones",
        "cómodo", "ergonómico"
    ],
    "estética": [
        "bonito", "diseño", "estético", "elegante", "color", "acabado", "luce", "moderno"
    ],
    "ajuste/compatibilidad": [
        "encaja", "compatible", "sirve", "para", "modelo", "ajuste", "montaje", "repuesto"
    ],
    "necesidad/regalo": [
        "necesitaba", "urgente", "repuesto", "regalo", "cumpleaños", "navidad", "detalle"
    ],
    "recomendación/social": [
        "me lo recomendaron", "recomendado por", "amigo", "familia", "influencer", "redes", "tiktok",
        "instagram", "youtube"
    ]
}

NEGATIONS = {"no", "nunca", "jamás", "ningún", "ninguna", "sin"}

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

def fetch_html(url: str, timeout: int = 25) -> str:
    return fetch_html_resilient(url, timeout=timeout)

def clean_text(t: str) -> str:
    t = re.sub(r"\s+", " ", t or "")
    return t.strip()

def extract_text_blocks(soup: BeautifulSoup) -> Dict[str, List[str]]:
    blocks = defaultdict(list)

    # título
    title_candidates = [
        {"name": "h1"}, {"attrs": {"id": re.compile(r"title|productTitle", re.I)}},
        {"attrs": {"class": re.compile(r"title|product-title", re.I)}}
    ]
    for selector in title_candidates:
        for el in soup.find_all(**selector):
            text = clean_text(el.get_text(" "))
            if len(text) > 5:
                blocks["titulo"].append(text)

    # precio
    price_regex = re.compile(r"(\d+[.,]\d{2})\s?(€|eur|euros)", re.I)
    for el in soup.find_all(string=price_regex):
        blocks["precio"].append(clean_text(el))

    # descripción
    desc_candidates = [
        {"attrs": {"id": re.compile(r"productDescription|description", re.I)}},
        {"attrs": {"class": re.compile(r"description|product-desc|about|feature", re.I)}},
    ]
    for selector in desc_candidates:
        for el in soup.find_all(**selector):
            text = clean_text(el.get_text(" "))
            if len(text) > 40:
                blocks["descripcion"].append(text)

    # reseñas
    review_selectors = [
        {"attrs": {"data-hook": "review-body"}},
        {"attrs": {"class": re.compile(r"review|opini[oó]n|valoraci[oó]n", re.I)}},
        {"name": "q"}, {"name": "blockquote"},
        {"name": "p", "attrs": {"class": re.compile(r"comment", re.I)}},
    ]
    for selector in review_selectors:
        for el in soup.find_all(**selector):
            txt = clean_text(el.get_text(" "))
            if 20 <= len(txt) <= 2000:
                blocks["reseñas"].append(txt)
    return blocks

def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-záéíóúñü]+", text.lower())

def score_drivers(texts: List[str]) -> Dict[str, int]:
    scores = {k: 0 for k in DRIVER_KEYWORDS.keys()}
    for chunk in texts:
        tokens = tokenize(chunk)
        token_set = set(tokens)
        for driver, kws in DRIVER_KEYWORDS.items():
            count = 0
            for kw in kws:
                if " " in kw:
                    count += chunk.lower().count(kw.lower())
                else:
                    count += tokens.count(kw.lower())
            if count > 0:
                neg_penalty = count * (1 if any(n in token_set for n in NEGATIONS) else 0)
                scores[driver] += max(0, count - neg_penalty)
    return scores

def normalize(scores: Dict[str, int]) -> Dict[str, float]:
    total = sum(scores.values()) or 1
    return {k: round(v/total, 4) for k, v in scores.items()}

def text_bar(value: float, total: int = 30) -> str:
    filled = int(round(value * total))
    return "█" * filled + "·" * (total - filled)

def pretty_print(result: Dict):
    print("\n================= RESULTADO =================")
    print("URL:      ", result.get("url"))
    print("Dominio:  ", result.get("dominio"))
    tit = result.get("titulo") or []
    if tit:
        print("Título:   ", tit[0][:140])
    precio = result.get("precio_detectado") or []
    if precio:
        print("Precio:   ", precio[0])
    print("Reseñas detectadas:", result.get("num_reseñas_detectadas"))
    print("--------------------------------------------")
    print("Motivos probables de compra (proporción):")
    proportions = result.get("drivers_proportions", {})
    ordered = sorted(proportions.items(), key=lambda x: x[1], reverse=True)
    for driver, p in ordered:
        print(f" - {driver:<20} {text_bar(p)}  {p:>5.0%}")
    print("--------------------------------------------")
    print("Top palabras en reseñas:")
    for w, c in result.get("top_keywords_reseñas", [])[:12]:
        print(f" {w:<14} x{c}")
    print("--------------------------------------------")
    print(result.get("nota", ""))
    print("============================================\n")

def analyze_url(url: str) -> Dict:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    blocks = extract_text_blocks(soup)

    weighted_texts = []
    weighted_texts += blocks.get("titulo", []) * 3
    weighted_texts += blocks.get("descripcion", []) * 2
    weighted_texts += blocks.get("reseñas", []) * 4

    scores = score_drivers(weighted_texts)
    proportions = normalize(scores)

    review_tokens = []
    for r in blocks.get("reseñas", []):
        review_tokens.extend(tokenize(r))
    freq = Counter([t for t in review_tokens if len(t) > 3])
    top_keywords = freq.most_common(20)

    return {
        "url": url,
        "dominio": urlparse(url).netloc,
        "titulo": blocks.get("titulo", [])[:3],
        "precio_detectado": blocks.get("precio", [])[:3],
        "num_reseñas_detectadas": len(blocks.get("reseñas", [])),
        "drivers_scores": scores,
        "drivers_proportions": proportions,
        "top_keywords_reseñas": top_keywords,
        "nota": "Heurístico basado en texto de título, descripción y reseñas. "
                "Para precisión real, cruza con datos de venta/UTM o usa NLP avanzado.",
    }

def main():
    print("=== Analizador de Motivos de Compra (CLI) ===")
    print("Pega una URL de producto (o escribe 'salir'):")
    while True:
        try:
            url = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo.")
            break
        if not url:
            continue
        if url.lower() in {"salir", "exit", "quit"}:
            print("Hasta luego 👋")
            break
        if not re.match(r"^https?://", url):
            print("Introduce una URL válida que empiece por http(s)://")
            continue
        try:
            result = analyze_url(url)
            pretty_print(result)
            print("¿Guardar resultado en JSON? (s/n): ", end="")
            choice = input("").strip().lower()
            if choice == "s":
                fname = "resultado_compra.json"
                with open(fname, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"Guardado en {fname}")
        except requests.HTTPError as e:
            print(f"Error HTTP: {e}")
        except requests.RequestException as e:
            print(f"Error de red: {e}")
        except Exception as e:
            print(f"Ocurrió un error: {e}")

if __name__ == "__main__":
    main()
