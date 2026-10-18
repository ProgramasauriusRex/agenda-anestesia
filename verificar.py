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
from collections import Counter, defaultdict
from threading import Lock
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

# Cabeceras. Nos identificamos como lo que somos, pero algunos servidores
# tienen filtros rudimentarios que rechazan cualquier visitante que no parezca
# un navegador y devuelven 406 o 403 — le pasa a SEMICYUC y a la SED, que en el
# navegador se abren sin problema. Cuando eso ocurre reintentamos una vez con
# cabeceras de navegador. Seguimos respetando robots.txt, que es donde una web
# expresa de verdad si quiere o no ser rastreada.
CAB_BOT = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}
CAB_NAVEGADOR = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}
RECHAZO_POR_CABECERAS = (403, 406, 412)

# 429 ("vas muy rápido") y 503 ("ahora no puedo") piden espera, no insistencia.
REINTENTO_LENTO = (429, 503)
# Dos reintentos con espera creciente: ver el comentario de agenda.py. Al
# crecer a 238 fuentes aparecieron tiempos de espera agotados en webs que
# respondían bien la semana anterior.
ESPERAS_REINTENTO = (8, 20)


# Palabras que delatan una página de agenda / formación
PISTAS_AGENDA = [
    "agenda", "eventos", "evento", "cursos", "curso", "congresos", "congreso",
    "formacion", "formación", "jornadas", "actividades", "calendario",
    "proximos", "próximos", "docencia", "actualidad", "noticias",
    "formacio", "activitats", "formación continuada", "estudios propios",
    "formación permanente", "titulos propios", "títulos propios", "masteres",
    "másteres", "postgrado", "posgrado",
]

# La misma lista que usa agenda.py, y aquí se prueba ENTERA: este programa
# se ejecuta cuatro veces al año, así que puede permitirse buscar a fondo.
# Su resultado se guarda en fuentes.yaml (campo "feed"), y gracias a eso el
# rastreo semanal no tiene que volver a sondear nada.
RUTAS_FEED = [
    "/feed/", "/feed", "/rss", "/rss.xml", "/atom.xml", "/index.xml",
    "?feed=rss2", "/feed/atom/", "/events/feed/", "/agenda/feed/",
    "/blog/feed/", "/noticias/feed/", "/?format=feed&type=rss",
]


def normaliza(t: str) -> str:
    t = t.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


# Reloj por dominio. El rastreo semanal lo tenía desde el principio, el
# verificador no: con seis hilos, quince hospitales seguidos de
# comunidad.madrid recibían hasta seis peticiones a la vez, y cada uno además
# probaba trece rutas buscando un canal. Es la receta exacta para que el
# servidor conteste 429 y la fuente se marque como rota sin estarlo.
PAUSA = 1.5
_ultimo_acceso: dict[str, float] = defaultdict(float)
_candado = Lock()


def espera_turno(url: str) -> None:
    dominio = urlparse(url).netloc
    while True:
        with _candado:
            falta = PAUSA - (time.monotonic() - _ultimo_acceso[dominio])
            if falta <= 0:
                _ultimo_acceso[dominio] = time.monotonic()
                return
        time.sleep(min(falta, 0.5))


def _peticion(url: str, cabeceras: dict, timeout: int):
    espera_turno(url)
    try:
        return requests.get(url, headers=cabeceras, timeout=timeout,
                            allow_redirects=True)
    except Exception as e:
        return e


def descarga(url: str, timeout: int = TIMEOUT):
    """
    Igual que la de agenda.py: reintento con cabeceras de navegador si el
    servidor rechaza al robot, y reintento con espera si pide calma o si la
    conexión se cae. Devuelve la respuesta, o la excepción para poder
    explicar en el informe qué ha pasado.
    """
    r = _peticion(url, CAB_BOT, timeout)

    if not isinstance(r, Exception) and r.status_code in RECHAZO_POR_CABECERAS:
        r = _peticion(url, CAB_NAVEGADOR, timeout)

    for espera in ESPERAS_REINTENTO:
        if not isinstance(r, Exception) and r.status_code not in REINTENTO_LENTO:
            break
        time.sleep(espera)
        otro = _peticion(url, CAB_NAVEGADOR, timeout)
        # si el reintento tampoco va, se informa del primer error
        if not isinstance(otro, Exception):
            r = otro

    if isinstance(r, Exception):
        return r
    if "charset" not in r.headers.get("Content-Type", "").lower():
        r.encoding = r.apparent_encoding or "utf-8"
    return r


def robots_permite(url: str) -> bool | None:
    """
    True permite, False prohíbe, None no se pudo comprobar.

    Mismo criterio que agenda.py, y por el mismo motivo: `rp.read()` pide el
    archivo con el User-Agent por defecto de Python, muchos cortafuegos le
    responden 403, y la librería estándar convierte ese 403 en «prohibido todo
    el sitio». Eso marcó como bloqueadas 27 webs que no prohibían nada.

    Se sigue el RFC 9309: 200 → obedecer el archivo; 4xx → sin restricciones;
    5xx → prohibido por prudencia; error de red → no se puede saber.
    """
    p = urlparse(url)
    url_robots = f"{p.scheme}://{p.netloc}/robots.txt"
    r = descarga(url_robots, timeout=15)

    # Un 5xx deja la web fuera del rastreo; merece una segunda oportunidad
    # antes de anotarla como bloqueada.
    for espera in ESPERAS_REINTENTO:
        if isinstance(r, Exception) or r.status_code < 500:
            break
        time.sleep(espera)
        r = descarga(url_robots, timeout=15)

    if isinstance(r, Exception):
        return None
    if r.status_code >= 500:
        return False
    if r.status_code >= 400:
        return True

    rp = robotparser.RobotFileParser()
    rp.set_url(url_robots)
    try:
        rp.parse(r.text.splitlines())
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return None


# Se rellena en main(): dominios que alojan varias fuentes. Ver
# feed_es_propio() en agenda.py, que sigue el mismo criterio.
DOMINIOS_COMPARTIDOS: set[str] = set()


def _seccion(url: str) -> str:
    partes = [s for s in urlparse(url).path.split("/") if s][:2]
    return "/" + "/".join(partes)


def feed_es_propio(url_fuente: str, url_feed: str) -> bool:
    """En un dominio compartido, el canal tiene que colgar de la sección de
    la fuente. Si no, es el del sitio entero (la Consejería, la web de SECPAL)
    y no el del hospital o la asociación que estamos verificando."""
    pf, pc = urlparse(url_fuente), urlparse(url_feed)
    if pf.netloc not in DOMINIOS_COMPARTIDOS or not pf.path.strip("/"):
        return True
    if pc.netloc and pc.netloc != pf.netloc:
        return False
    return pc.path.startswith(_seccion(url_fuente))


def _candidatos_feed(url: str) -> list[str]:
    p = urlparse(url)
    if p.netloc in DOMINIOS_COMPARTIDOS and p.path.strip("/"):
        base = f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
        return [base + "/feed/", base + "/rss", base + "/rss.xml"]
    raiz = f"{p.scheme}://{p.netloc}"
    return [urljoin(raiz, ruta) for ruta in RUTAS_FEED]


def busca_feed(url: str, html: str) -> str | None:
    try:
        sopa = BeautifulSoup(html, "lxml")
        for link in sopa.find_all("link", rel=lambda v: v and "alternate" in v):
            tipo = (link.get("type") or "").lower()
            if any(x in tipo for x in ("rss", "atom", "xml")):
                href = link.get("href", "")
                if href and feed_es_propio(url, urljoin(url, href)):
                    return urljoin(url, href)
    except Exception:
        pass

    for cand in _candidatos_feed(url):
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
    texto = YAML_PATH.read_text(encoding="utf-8")
    por_url = {r["url"]: r for r in resultados}
    cambios = 0

    # Se trabaja bloque a bloque (cada fuente es un bloque) en lugar de línea
    # a línea: así se puede añadir o sustituir campos sin descolocar nada.
    partes = texto.split("  - nombre: ")
    salida = [partes[0]]
    for bloque in partes[1:]:
        m = re.search(r"\n    url:\s*(\S+)", bloque)
        r = por_url.get(m.group(1)) if m else None
        if not r:
            salida.append(bloque)
            continue

        # Fuera las anotaciones de la pasada anterior, o se acumularían
        lineas = [l for l in bloque.split("\n")
                  if not l.strip().startswith(("# sugerencia:", "# redirige a:", "# RSS:"))]
        lineas = [l for l in lineas if not re.match(r"^\s*feed:", l)]

        nuevas = []
        for l in lineas:
            me = re.match(r"^(\s*)estado:\s*(\S+)\s*$", l)
            if not me:
                nuevas.append(l)
                continue
            sangria = me.group(1)
            if me.group(2) != r["estado"]:
                cambios += 1
            nuevas.append(f"{sangria}estado: {r['estado']}")
            # El canal RSS se guarda como dato, no como comentario: el rastreo
            # semanal lo lee y se ahorra sondear la web cada lunes.
            # "none" significa "comprobado: no tiene", que vale tanto como
            # saber la dirección del canal.
            nuevas.append(f"{sangria}feed: {r['feed'] or 'none'}")
            if r["url_sugerida"]:
                nuevas.append(f"{sangria}# sugerencia: {r['url_sugerida']}")
            if r["url_final"]:
                nuevas.append(f"{sangria}# redirige a: {r['url_final']}")
        salida.append("\n".join(nuevas))

    YAML_PATH.write_text("  - nombre: ".join(salida), encoding="utf-8")
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
    global DOMINIOS_COMPARTIDOS
    cuenta = Counter(urlparse(f["url"]).netloc for f in fuentes)
    DOMINIOS_COMPARTIDOS = {d for d, n in cuenta.items() if n >= 2}
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
