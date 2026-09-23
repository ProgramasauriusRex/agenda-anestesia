#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNÓSTICO DE RENDIMIENTO
==========================

De las 211 webs de la lista, solo unas pocas aportan cursos. Este programa
averigua POR QUÉ falla cada una, en vez de adivinarlo.

En cada página, el rastreador pasa por cuatro fases:

    enlaces  →  ¿hay una fecha cerca?  →  ¿es de la especialidad?  →  título

Aquí se cuenta cuántos candidatos sobreviven a cada fase, y con eso cada web
queda clasificada en un diagnóstico:

  PRODUCE               funciona; aporta cursos
  SIN ENLACES           apenas hay enlaces: web dinámica que se dibuja con
                        JavaScript, o contenido que no está en enlaces
  SIN FECHAS            no hay ninguna fecha futura en toda la página
  FECHA EN LA FICHA     hay fechas en la página, pero no junto a los enlaces:
                        el listado solo da títulos y la fecha vive dentro de
                        cada curso. Habría que entrar un nivel más
  FILTRO                hay enlaces con fecha, pero el filtro los rechaza
  TÍTULO                pasan el filtro y tienen fecha, pero el título no vale
  FUERA DE VENTANA      encuentra cursos, pero todos caducados o a más de un
                        año vista

Escribe salida/diagnostico-FECHA.md con el recuento y ejemplos reales de los
textos que se están descartando, que es lo que permite decidir qué tocar.

    python diagnostico.py                # todas
    python diagnostico.py --nivel 1      # solo unas pocas, para probar
    python diagnostico.py --limite 20    # las 20 primeras
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin

import feedparser
import yaml
from bs4 import BeautifulSoup

from agenda import (SALIDA, descarga, robots_permite, es_relevante, normaliza,
                    limpia_titulo, titulo_util, titulo_desde_url,
                    separa_sin_plazas, desde_feed, desde_html)
from fechas import extrae_fechas

BASE = Path(__file__).parent
HILOS = 6
MUESTRAS = 3          # ejemplos por fuente y por motivo de descarte


def analiza_html(url: str, html: str, fuente: dict, hoy: date) -> dict:
    """Recorre la página igual que el rastreador, pero contando en vez de extraer."""
    r = {"enlaces": 0, "con_fecha": 0, "relevantes": 0, "candidatos": 0,
         "finales": 0, "fechas_en_pagina": 0,
         "ej_sin_filtro": [], "ej_sin_fecha": [], "ej_sin_titulo": []}

    sopa = BeautifulSoup(html, "lxml")
    for tag in sopa(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # ¿Hay fechas en la página, aunque sea lejos de los enlaces? Distingue
    # "esta web no anuncia nada" de "las fechas están dentro de cada ficha".
    texto_pagina = sopa.get_text(" ", strip=True)
    for trozo in [texto_pagina[i:i + 400] for i in range(0, min(len(texto_pagina), 40000), 400)]:
        ini, _, _ = extrae_fechas(trozo, hoy=hoy)
        if ini and hoy <= ini <= hoy + timedelta(days=400):
            r["fechas_en_pagina"] += 1

    filtro = fuente.get("filtro", "evento")
    for a in sopa.find_all("a", href=True):
        texto_enlace = a.get_text(" ", strip=True)
        if len(texto_enlace) < 12:
            continue
        r["enlaces"] += 1

        contenedor = a
        while contenedor.parent is not None:
            padre = contenedor.parent
            if padre.name in ("body", "html", "[document]"):
                break
            otros = [x for x in padre.find_all("a", href=True)
                     if len(x.get_text(" ", strip=True)) >= 12]
            if len(otros) > 1 or len(padre.get_text(" ", strip=True)) > 500:
                break
            contenedor = padre
        contexto = contenedor.get_text(" ", strip=True)[:600]
        conjunto = f"{texto_enlace}. {contexto}"

        relevante = es_relevante(conjunto, filtro)
        ini, fin, frag = extrae_fechas(conjunto, hoy=hoy)

        if ini:
            r["con_fecha"] += 1
        if relevante:
            r["relevantes"] += 1

        if relevante and not ini and len(r["ej_sin_fecha"]) < MUESTRAS:
            r["ej_sin_fecha"].append(texto_enlace[:90])
        if ini and not relevante and len(r["ej_sin_filtro"]) < MUESTRAS:
            r["ej_sin_filtro"].append(texto_enlace[:90])
        if not (relevante and ini):
            continue

        r["candidatos"] += 1
        limpio, _ = separa_sin_plazas(limpia_titulo(texto_enlace, frag))
        if not titulo_util(limpio):
            limpio = titulo_desde_url(urljoin(url, a["href"]))
            if not titulo_util(limpio):
                if len(r["ej_sin_titulo"]) < MUESTRAS:
                    r["ej_sin_titulo"].append(texto_enlace[:90])
                continue
        if hoy - timedelta(days=2) <= ini <= hoy + timedelta(days=400):
            r["finales"] += 1
    return r


def analiza_feed(url_feed: str, fuente: dict, hoy: date) -> dict:
    r = {"entradas": 0, "con_fecha": 0, "relevantes": 0, "finales": 0,
         "ej_sin_filtro": [], "ej_sin_fecha": []}
    resp = descarga(url_feed)
    if not resp:
        return r
    d = feedparser.parse(resp.content)
    filtro = fuente.get("filtro", "evento")
    for e in d.entries[:60]:
        r["entradas"] += 1
        titulo = BeautifulSoup(e.get("title", ""), "lxml").get_text(" ", strip=True)
        resumen = BeautifulSoup(e.get("summary", ""), "lxml").get_text(" ", strip=True)
        conjunto = f"{titulo}. {resumen}"
        relevante = es_relevante(conjunto, filtro)
        ini, _, _ = extrae_fechas(conjunto, hoy=hoy)
        if ini:
            r["con_fecha"] += 1
        if relevante:
            r["relevantes"] += 1
        if relevante and not ini and len(r["ej_sin_fecha"]) < MUESTRAS:
            r["ej_sin_fecha"].append(titulo[:90])
        if ini and not relevante and len(r["ej_sin_filtro"]) < MUESTRAS:
            r["ej_sin_filtro"].append(titulo[:90])
        if relevante and ini and hoy - timedelta(days=2) <= ini <= hoy + timedelta(days=400):
            r["finales"] += 1
    return r


def diagnostica(fuente: dict, hoy: date) -> dict:
    url = fuente["url"]
    res = {"nombre": fuente["nombre"], "url": url, "filtro": fuente.get("filtro", "evento"),
           "via": "", "motivo": "", "html": None, "feed": None, "detalle": ""}

    if fuente.get("estado") == "roto":
        res["motivo"] = "ROTA"
        return res
    if not robots_permite(url):
        res["motivo"] = "BLOQUEADA"
        return res

    conocido = str(fuente.get("feed") or "").strip()
    if conocido and conocido.lower() != "none":
        res["feed"] = analiza_feed(conocido, fuente, hoy)
        res["via"] = "feed"
        if res["feed"]["finales"]:
            res["motivo"] = "PRODUCE"
            return res

    r = descarga(url)
    if not r:
        res["motivo"] = "NO RESPONDE"
        return res
    res["html"] = analiza_html(url, r.text, fuente, hoy)
    h = res["html"]
    res["via"] = res["via"] or "html"

    # El orden importa: primero los motivos que se saben con certeza porque
    # hay evidencia (candidatos, enlaces con fecha), y solo al final los que
    # se deducen de una ausencia. Al revés, una web con pocos enlaces pero
    # con fechas se clasificaba como "sin enlaces" y se ocultaba el motivo real.
    if h["finales"]:
        res["motivo"] = "PRODUCE"
    elif h["candidatos"]:
        res["motivo"] = "TÍTULO" if h["ej_sin_titulo"] else "FUERA DE VENTANA"
    elif h["con_fecha"]:
        res["motivo"] = "FILTRO"
    elif h["enlaces"] < 5:
        res["motivo"] = "SIN ENLACES"
    elif h["fechas_en_pagina"] == 0:
        res["motivo"] = "SIN FECHAS"
    else:
        res["motivo"] = "FECHA EN LA FICHA"
    return res


def informe(rs: list[dict], hoy: date) -> str:
    orden = ["PRODUCE", "FILTRO", "FECHA EN LA FICHA", "SIN FECHAS", "SIN ENLACES",
             "TÍTULO", "FUERA DE VENTANA", "NO RESPONDE", "BLOQUEADA", "ROTA"]
    cuenta = Counter(r["motivo"] for r in rs)

    L = [f"# Diagnóstico de rendimiento — {hoy.strftime('%d/%m/%Y')}", "",
         f"{len(rs)} fuentes analizadas.", "", "| Diagnóstico | Fuentes |", "|---|---|"]
    for m in orden:
        if cuenta[m]:
            L.append(f"| {m} | {cuenta[m]} |")
    L += ["", "---", ""]

    for m in orden:
        grupo = [r for r in rs if r["motivo"] == m]
        if not grupo or m in ("ROTA", "BLOQUEADA"):
            continue
        L += [f"## {m} ({len(grupo)})", ""]
        for r in sorted(grupo, key=lambda x: x["nombre"]):
            h, f = r["html"], r["feed"]
            cifras = []
            if f:
                cifras.append(f"feed: {f['entradas']} entradas, {f['con_fecha']} con fecha, "
                              f"{f['relevantes']} de la especialidad, {f['finales']} válidas")
            if h:
                cifras.append(f"html: {h['enlaces']} enlaces, {h['con_fecha']} con fecha, "
                              f"{h['relevantes']} de la especialidad, {h['finales']} válidas "
                              f"({h['fechas_en_pagina']} fechas sueltas en la página)")
            L.append(f"**{r['nombre']}** · filtro {r['filtro']}  ")
            L.append(f"{r['url']}  ")
            for c in cifras:
                L.append(f"- {c}")
            for clave, etiqueta in (("ej_sin_filtro", "tienen fecha pero el filtro los rechaza"),
                                    ("ej_sin_fecha", "son de la especialidad pero sin fecha"),
                                    ("ej_sin_titulo", "descartados por el título")):
                ejemplos = (h or {}).get(clave) or (f or {}).get(clave) or []
                for e in ejemplos:
                    L.append(f"    - _{etiqueta}_: «{e}»")
            L.append("")
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnóstico de rendimiento del rastreo")
    ap.add_argument("--nivel", nargs="+", type=int, default=None)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    hoy = date.today()
    cfg = yaml.safe_load((BASE / "fuentes.yaml").read_text(encoding="utf-8"))
    fuentes = cfg["fuentes"]
    if args.nivel:
        fuentes = [f for f in fuentes if f.get("nivel", 1) in args.nivel]
    if args.limite:
        fuentes = fuentes[:args.limite]

    print(f"Analizando {len(fuentes)} fuentes…\n", file=sys.stderr)
    inicio = time.time()
    rs = []
    with ThreadPoolExecutor(max_workers=HILOS) as ex:
        for i, r in enumerate(ex.map(lambda f: diagnostica(f, hoy), fuentes), 1):
            rs.append(r)
            print(f" [{i:>3}/{len(fuentes)}] {r['nombre'][:42]:<42} {r['motivo']}",
                  file=sys.stderr)

    SALIDA.mkdir(exist_ok=True)
    ruta = SALIDA / f"diagnostico-{hoy.isoformat()}.md"
    ruta.write_text(informe(rs, hoy), encoding="utf-8")
    print(f"\n{time.time()-inicio:.0f} segundos · informe en {ruta}", file=sys.stderr)
    for m, n in Counter(r["motivo"] for r in rs).most_common():
        print(f"  {n:>3}  {m}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
