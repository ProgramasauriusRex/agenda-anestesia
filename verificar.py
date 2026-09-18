#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICADOR DE FUENTES
======================

Comprueba, una por una, todas las webs de `fuentes.yaml`:

  1. ¿Responde la dirección? (siguiendo redirecciones)
  2. ¿Permite el rastreo automatizado? (robots.txt)
  3. ¿Publica un RSS? (el formato fiable, que no se rompe con los rediseños)
  4. Si la dirección es la portada, ¿hay una página de agenda o formación
     mejor a la que apuntar? La busca sola y la propone.

Al terminar actualiza `fuentes.yaml` (marcando cada fuente como ok / roto /
bloqueada) y escribe un informe legible en `salida/verificacion-FECHA.md`.

    python verificar.py                 # comprueba todas
    python verificar.py --nivel 1       # solo las semanales
    python verificar.py --no-aplicar    # informa pero no toca fuentes.yaml

Conviene ejecutarlo al montar el sistema y luego cada 3-6 meses.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
import urllib.robotparser as robotparser
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

BASE = Path(__file__).parent
SALIDA = BASE / "salida"
YAML_PATH = BASE / "fuentes.yaml"

USER_AGENT = (
    "AgendaAnestesiaBot/1.0 (rastreador personal de agenda formativa; "
    "contacto: tu-email@ejemplo.com)"
)
TIMEOUT = 25
HILOS = 6  # peticiones en paralelo; suficiente para ser rápido sin ser un abuso

# Palabras que delatan una página de agenda / formación
PISTAS_AGENDA = [
    "agenda", "eventos", "evento", "cursos", "curso", "congresos", "congreso",
    "formacion", "formación", "jornadas", "actividades", "calendario",
    "proximos", "próximos", "docencia", "actualidad", "noticias",
    "formacio", "activitats", "formación continuada", "estudios propios",
    "formación permanente", "titulos propios", "títulos propios", "masteres",
    "másteres", "postgrado", "posgrado",
]

RUTAS_FEED = [
    "/feed/", "/feed", "/rss", "/rss.xml", "/atom.xml", "/index.xml",
    "?feed=rss2", "/events/feed/", "/agenda/feed/", "/noticias/feed/",
]


def normaliza(t: str) -> str:
    t = t.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def descarga(url: str, timeout: int = TIMEOUT):
    try:
        r = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es;q=0.9"},
            timeout=timeout,
            allow_redirects=True,
        )
        if "charset" not in r.headers.get("Content-Type", "").lower():
            r.encoding = r.apparent_encoding or "utf-8"
        return r
    except Exception as e:
        return e


def robots_permite(url: str) -> bool | None:
    """True permite, False prohíbe, None no se pudo comprobar."""
    p = urlparse(url)
    rp = robotparser.RobotFileParser()
    rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
    try:
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return None


def busca_feed(url: str, html: str) -> str | None:
    try:
        sopa = BeautifulSoup(html, "lxml")
        for link in sopa.find_all("link", rel=lambda v: v and "alternate" in v):
            tipo = (link.get("type") or "").lower()
            if any(x in tipo for x in ("rss", "atom", "xml")):
                href = link.get("href", "")
                if href:
                    return urljoin(url, href)
    except Exception:
        pass

    p = urlparse(url)
    raiz = f"{p.scheme}://{p.netloc}"
    for ruta in RUTAS_FEED[:4]:  # solo las más probables, para no eternizarse
        cand = urljoin(raiz, ruta)
        r = descarga(cand, timeout=12)
        if isinstance(r, Exception) or r.status_code != 200:
            continue
        cabecera = r.text.lstrip()[:200].lower()
        if cabecera.startswith(("<?xml", "<rss", "<feed")):
            return cand
    return None


def busca_pagina_agenda(url: str, html: str) -> str | None:
    """
    Si la dirección apunta a la portada, busca un enlace interno que parezca
    la sección de agenda, cursos o formación. Devuelve el mejor candidato.
    """
    try:
        sopa = BeautifulSoup(html, "lxml")
    except Exception:
        return None

    dominio = urlparse(url).netloc
    candidatos: list[tuple[int, str]] = []

    for a in sopa.find_all("a", href=True):
        texto = normaliza(a.get_text(" ", strip=True))
        href = a["href"]
        destino = urljoin(url, href)
        if urlparse(destino).netloc != dominio:
            continue
        if destino.rstrip("/") == url.rstrip("/"):
            continue

        ruta = normaliza(urlparse(destino).path)
        puntos = 0
        for pista in PISTAS_AGENDA:
            pn = normaliza(pista)
            if pn and pn in texto:
                puntos += 3
            if pn and pn in ruta:
                puntos += 2
        # Preferimos enlaces de menú cortos ("Agenda", "Cursos") a titulares largos
        if puntos and len(texto) < 40:
            puntos += 2
        if puntos >= 4:
            candidatos.append((puntos, destino))

    if not candidatos:
        return None
    candidatos.sort(key=lambda x: (-x[0], len(x[1])))
    return candidatos[0][1]


def verifica(f: dict) -> dict:
    """Comprueba una fuente y devuelve su diagnóstico."""
    url = f["url"]
    res = {
        "nombre": f["nombre"], "url": url, "nivel": f.get("nivel", 1),
        "estado": "roto", "detalle": "", "feed": None,
        "url_sugerida": None, "url_final": None,
    }

    permite = robots_permite(url)
    if permite is False:
        res["estado"] = "bloqueada"
        res["detalle"] = "robots.txt prohíbe el rastreo automatizado"
        return res

    r = descarga(url)
    if isinstance(r, Exception):
        res["detalle"] = f"{type(r).__name__}: {str(r)[:70]}"
        return res
    if r.status_code >= 400:
        res["detalle"] = f"HTTP {r.status_code}"
        return res

    res["estado"] = "ok"
    res["detalle"] = f"HTTP {r.status_code}"
    if r.url.rstrip("/") != url.rstrip("/"):
        res["url_final"] = r.url
        res["detalle"] += " (redirige)"

    html = r.text
    res["feed"] = busca_feed(r.url, html)

    # ¿Es una portada (o casi)? Entonces buscamos una página de agenda mejor.
    # Contamos tramos de la dirección: "socartd.es/" tiene 0, "socartd.es/inicio/"
    # tiene 1 — ambas son portadas a efectos prácticos. A partir de 2 tramos
    # damos por hecho que ya apunta a una sección concreta.
    tramos = [t for t in urlparse(r.url).path.split("/") if t and t != "index.html"]
    if len(tramos) <= 1:
        sugerida = busca_pagina_agenda(r.url, html)
        if sugerida:
            res["url_sugerida"] = sugerida

    return res


def aplica_a_yaml(resultados: list[dict]) -> int:
    """
    Actualiza fuentes.yaml SIN destruir los comentarios: edita las líneas
    una a una en lugar de regenerar el fichero.
    """
    lineas = YAML_PATH.read_text(encoding="utf-8").split("\n")

    # Borramos las anotaciones que puso una ejecución anterior. Sin esto, cada
    # pasada añadiría una copia más y el fichero acabaría ilegible.
    AUTO = ("# sugerencia:", "# redirige a:", "# RSS:")
    lineas = [ln for ln in lineas if not ln.strip().startswith(AUTO)]

    por_url = {r["url"]: r for r in resultados}
    cambios = 0
    url_actual = None

    for i, linea in enumerate(lineas):
        m = re.match(r"^(\s*)url:\s*(\S+)\s*$", linea)
        if m:
            url_actual = m.group(2)
            continue
        m = re.match(r"^(\s*)estado:\s*(\S+)\s*$", linea)
        if m and url_actual in por_url:
            r = por_url[url_actual]
            nuevo = r["estado"]
            if nuevo != m.group(2):
                lineas[i] = f"{m.group(1)}estado: {nuevo}"
                cambios += 1
            # Anotamos la sugerencia como comentario, para que la revises tú
            extras = []
            if r["url_sugerida"]:
                extras.append(f"{m.group(1)}# sugerencia: {r['url_sugerida']}")
            if r["url_final"]:
                extras.append(f"{m.group(1)}# redirige a: {r['url_final']}")
            if r["feed"]:
                extras.append(f"{m.group(1)}# RSS: {r['feed']}")
            if extras:
                lineas[i] = lineas[i] + "\n" + "\n".join(extras)
            url_actual = None

    YAML_PATH.write_text("\n".join(lineas), encoding="utf-8")
    return cambios


def informe(resultados: list[dict], hoy: date) -> str:
    ok = [r for r in resultados if r["estado"] == "ok"]
    con_feed = [r for r in ok if r["feed"]]
    bloq = [r for r in resultados if r["estado"] == "bloqueada"]
    rotas = [r for r in resultados if r["estado"] == "roto"]
    sugeridas = [r for r in ok if r["url_sugerida"]]

    L = [f"# Verificación de fuentes — {hoy.strftime('%d/%m/%Y')}", ""]
    L += [
        f"- **Funcionan:** {len(ok)} de {len(resultados)}",
        f"- **Con RSS** (las fiables): {len(con_feed)}",
        f"- **Bloqueadas** por robots.txt: {len(bloq)}",
        f"- **No responden:** {len(rotas)}",
        "",
    ]

    if con_feed:
        L += ["## Fuentes con RSS — las sólidas", "",
              "Estas publican un canal pensado para máquinas. No se rompen cuando",
              "la entidad rediseña su web.", "",
              "| Fuente | RSS |", "|---|---|"]
        L += [f"| {r['nombre']} | {r['feed']} |" for r in sorted(con_feed, key=lambda x: x["nombre"])]
        L += [""]

    if sugeridas:
        L += ["## Páginas de agenda encontradas", "",
              "La dirección configurada era la portada. El verificador ha encontrado",
              "una página más concreta. Revísalas y, si son correctas, cámbialas en",
              "`fuentes.yaml` (ya están anotadas allí como comentario).", "",
              "| Fuente | Página propuesta |", "|---|---|"]
        L += [f"| {r['nombre']} | {r['url_sugerida']} |" for r in sorted(sugeridas, key=lambda x: x["nombre"])]
        L += [""]

    if bloq:
        L += ["## Bloqueadas por robots.txt", "",
              "El sitio prohíbe el rastreo automatizado y el programa lo respeta.",
              "Para estas, la vía es el boletín de socio o sus redes sociales.", ""]
        L += [f"- **{r['nombre']}** — {r['url']}" for r in sorted(bloq, key=lambda x: x["nombre"])]
        L += [""]

    if rotas:
        L += ["## No responden", "",
              "Puede ser que la dirección haya cambiado, que la entidad ya no tenga web,",
              "o una caída puntual. Búscalas en Google y corrige la dirección en",
              "`fuentes.yaml`; si no existen, borra el bloque.", "",
              "| Fuente | Dirección | Qué ha pasado |", "|---|---|---|"]
        L += [f"| {r['nombre']} | {r['url']} | {r['detalle']} |"
              for r in sorted(rotas, key=lambda x: x["nombre"])]
        L += [""]

    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Verifica las fuentes de fuentes.yaml")
    ap.add_argument("--nivel", nargs="+", type=int, default=None)
    ap.add_argument("--no-aplicar", action="store_true",
                    help="informa pero no modifica fuentes.yaml")
    args = ap.parse_args()

    cfg = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    fuentes = cfg["fuentes"]
    if args.nivel:
        fuentes = [f for f in fuentes if f.get("nivel", 1) in args.nivel]

    print(f"Verificando {len(fuentes)} fuentes con {HILOS} peticiones en paralelo.", file=sys.stderr)
    print("Esto tarda unos minutos. Puedes dejarlo trabajando.\n", file=sys.stderr)

    resultados = []
    inicio = time.time()
    with ThreadPoolExecutor(max_workers=HILOS) as ex:
        for i, r in enumerate(ex.map(verifica, fuentes), 1):
            resultados.append(r)
            icono = {"ok": "✓", "bloqueada": "⛔", "roto": "✗"}[r["estado"]]
            extra = ""
            if r["feed"]:
                extra = "  [RSS]"
            elif r["url_sugerida"]:
                extra = "  [agenda encontrada]"
            print(f" {icono} [{i:>3}/{len(fuentes)}] {r['nombre'][:42]:<42}"
                  f" {r['detalle'][:28]}{extra}", file=sys.stderr)

    hoy = date.today()
    SALIDA.mkdir(exist_ok=True)
    ruta = SALIDA / f"verificacion-{hoy.isoformat()}.md"
    ruta.write_text(informe(resultados, hoy), encoding="utf-8")

    if not args.no_aplicar:
        n = aplica_a_yaml(resultados)
        print(f"\nfuentes.yaml actualizado ({n} estados cambiados).", file=sys.stderr)

    ok = sum(1 for r in resultados if r["estado"] == "ok")
    feeds = sum(1 for r in resultados if r["feed"])
    print(f"\n{ok}/{len(resultados)} funcionan · {feeds} con RSS "
          f"· {time.time()-inicio:.0f} segundos", file=sys.stderr)
    print(f"→ Informe completo: {ruta}", file=sys.stderr)

    print(informe(resultados, hoy))
    return 0


if __name__ == "__main__":
    sys.exit(main())
