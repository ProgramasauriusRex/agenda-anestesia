#!/usr/bin/env python3
"""
Rastreador semanal de cursos y congresos de Anestesiología, Cuidados Críticos
y Terapia del Dolor en España.

Uso:
    python agenda.py                 # nivel 1: los cursos nuevos del próximo mes
    python agenda.py --nivel 1 2     # nivel 1 y 2
    python agenda.py --meses 3       # el post muestra 3 meses en vez de 1
    python agenda.py --todo          # muestra también lo ya visto; no escribe nada
    python agenda.py --diagnostico   # informe de salud de cada fuente

Cada rastreo guarda lo que encuentra hasta un año vista en
salida/eventos-conocidos.json, y el post se construye desde esa memoria:
así los cursos de las fuentes mensuales y trimestrales aparecen cuando les
toca, aunque su web no se haya vuelto a visitar.

Estrategia por fuente, en este orden:
  1. Busca un feed RSS/Atom. Es lo ideal: formato estable, pensado para
     máquinas y explícitamente publicado para ser consumido.
  2. Si no hay feed, rasca el HTML con un extractor genérico (no hay un parser
     a medida por web: se buscan bloques con enlace + fecha + palabra clave).
  3. Respeta robots.txt. Si una web prohíbe el rastreo, se salta y lo avisa.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.robotparser as robotparser
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict, field, fields
from datetime import date, timedelta
from pathlib import Path
from threading import Lock
from urllib.parse import urljoin, urlparse

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

from fechas import extrae_fechas, formatea

BASE = Path(__file__).parent
SALIDA = BASE / "salida"
ESTADO = BASE / "estado.json"

USER_AGENT = (
    "AgendaAnestesiaBot/1.0 (rastreador personal de agenda formativa; "
    "contacto: tu-email@ejemplo.com)"
)
PAUSA = 1.5          # segundos entre peticiones al MISMO dominio: cortesía básica
TIMEOUT = 25
HILOS = 6            # fuentes en paralelo (dominios distintos), para no eternizarse

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
RECHAZO_POR_CABECERAS = (403, 406, 412, 429)


# Reloj por dominio: varias webs a la vez, sí; varias peticiones seguidas al
# mismo servidor, no. Es la diferencia entre rastrear con educación y martillear.
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

# --- Vocabulario de filtrado ---------------------------------------------

PALABRAS_EVENTO = [
    "curso", "congreso", "jornada", "jornadas", "taller", "talleres", "master",
    "master", "simposio", "simposium", "symposium", "reunion", "webinar",
    "seminario", "diploma", "diplomatura", "formacion", "sesion", "encuentro",
    "workshop", "ponencia", "inscripcion", "inscripciones", "programa cientifico",
    "foro", "forum", "congress", "conference", "course", "meeting", "summit",
]

# Términos de la especialidad. Se buscan como PALABRA COMPLETA (o raíz al
# principio de palabra), nunca como trozo de otra. Con la búsqueda por trozos
# que había antes, "uci" saltaba con "reducir", "intensiv" con "curso
# intensivo de inglés" y "critico" con "pensamiento crítico": en webs
# generalistas como los colegios de médicos eso era ruido asegurado.
# "Crítico" e "intensivo" solo cuentan dentro de sus expresiones clínicas.
PATRONES_ESPECIALIDAD = [
    # Raíces largas y exclusivas del campo: se aceptan también DENTRO de otra
    # palabra ("neuroanestesia", "Euroanaesthesia", "sedoanalgesia"), porque
    # no aparecen en palabras ajenas. Las cortas o ambiguas llevan \b.
    # Anestesiología
    r"anestesi\w*", r"anesthe\w*", r"anaesthe\w*", r"reanimacion\b",
    r"\bsedacion\b", r"\bsedoanalgesia\b", r"\bquirofano\w*", r"\burpa\b",
    r"\bperioperatori\w*", r"\bperioperative\b", r"\bpreoperatori\w*",
    r"\bpostoperatori\w*", r"\bvia aerea\b", r"\bairway\b", r"\bintubacion\b",
    r"\blocorregional\w*", r"\braquid\w*", r"\bepidural\w*", r"\bneuroaxial\w*",
    r"\bbloqueos?\s+(?:de\s+|del\s+)?(?:nervi|plex|regional|periferic|neuromuscular"
    r"|ecoguiad|interfascial|fascial|epidural|raquid)\w*",
    # Dolor y paliativos
    r"\bdolor\b", r"\bpain\b", r"analgesi\w*", r"opioid\w*",
    r"paliativ\w*", r"\bpalliative\b",
    # Críticos
    r"\buci\b", r"\bicu\b", r"\bmedicina intensiva\b", r"\bcuidados intensivos\b",
    r"\bintensive care\b", r"\bcuidados criticos\b", r"\bmedicina critica\b",
    r"\bpaciente critico\b", r"\benfermo critico\b", r"\bcritical care\b",
    r"\bcritically ill\b", r"\bventilacion mecanica\b", r"\bventilacion no invasiva\b",
    r"\bhemodinamic\w*", r"\bsepsis\b", r"\bshock\b",
    # Reanimación cardiopulmonar
    r"\brcp\b", r"\bsoporte vital\b", r"\bsv[ab]\b", r"\bresuscitation\b",
    # Ecografía (útil en anestesia y críticos; puede colar algo de primaria)
    r"ecografi\w*", r"ecocardiograf\w*", r"\bpocus\b",
    # Siglas de las sociedades del campo: "Congreso SECPAL" o "Jornada SEDAR"
    # no dicen la especialidad con palabras, pero la sigla ya la delata
    r"\b(?:sedar|semicyuc|seeiuc|secip|semdor|secpal|setri|esra|esaic|edaic|feea"
    r"|aaear|scartd|sbartd|agaryd|sadartd|acmartd|socartd|soclartd|svnartd"
    r"|samiuc|sarmicyuc|sbmiuc|socamicyuc|sclmicyuc|somiucam|socmic|sexmicyuc"
    r"|sogamiuc|somiama|snmiuc|sovamicyuc|somiuc|pnrcp|cercp)\b",
]
_RE_ESPECIALIDAD = re.compile("|".join(PATRONES_ESPECIALIDAD))

# Ruido típico de menús y pies de página que nunca es un evento
RUIDO = [
    "politica de privacidad", "aviso legal", "politica de cookies", "hazte socio",
    "iniciar sesion", "buscar", "contacto", "quienes somos", "bolsa de trabajo",
    "obituario", "mi sedar", "acceso socios", "newsletter", "suscribete",
]


def normaliza(t: str) -> str:
    t = t.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class Evento:
    titulo: str
    fecha_texto: str
    inicio: str | None
    fin: str | None
    lugar: str
    entidad: str
    url: str
    ambito: str
    via: str = ""           # "feed" o "html": de dónde salió
    id: str = field(default="")

    def __post_init__(self):
        if not self.id:
            semilla = f"{normaliza(self.titulo)[:90]}|{self.inicio}|{self.entidad}"
            self.id = hashlib.sha1(semilla.encode()).hexdigest()[:14]


# --- Utilidades de red ----------------------------------------------------

_robots_cache: dict[str, robotparser.RobotFileParser | None] = {}


def robots_permite(url: str) -> bool:
    """Comprueba robots.txt. Ante la duda (error de red), permite."""
    dominio = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if dominio not in _robots_cache:
        rp = robotparser.RobotFileParser()
        rp.set_url(urljoin(dominio, "/robots.txt"))
        try:
            rp.read()
            _robots_cache[dominio] = rp
        except Exception:
            _robots_cache[dominio] = None
    rp = _robots_cache[dominio]
    if rp is None:
        return True
    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def descarga(url: str) -> requests.Response | None:
    espera_turno(url)
    try:
        r = requests.get(url, headers=CAB_BOT, timeout=TIMEOUT)
        if r.status_code in RECHAZO_POR_CABECERAS:
            espera_turno(url)
            r = requests.get(url, headers=CAB_NAVEGADOR, timeout=TIMEOUT)
        r.raise_for_status()
        # Si el servidor no declara charset, requests asume ISO-8859-1 y
        # destroza tildes y eñes. Detectamos la codificación real.
        if "charset" not in r.headers.get("Content-Type", "").lower():
            r.encoding = r.apparent_encoding or "utf-8"
        return r
    except Exception:
        return None


# --- Descubrimiento de feeds ---------------------------------------------

RUTAS_FEED = [
    "/feed/", "/feed", "/rss", "/rss.xml", "/atom.xml", "/index.xml",
    "?feed=rss2", "/feed/atom/", "/events/feed/", "/agenda/feed/",
    "/blog/feed/", "/noticias/feed/", "/?format=feed&type=rss",
]


def busca_feed(url: str, html: str | None = None) -> str | None:
    """
    Intenta localizar un RSS/Atom. Primero en el <head> de la página
    (lo declaran casi todos los WordPress), luego probando rutas típicas.
    """
    if html:
        sopa = BeautifulSoup(html, "lxml")
        for link in sopa.find_all("link", rel=lambda v: v and "alternate" in v):
            tipo = (link.get("type") or "").lower()
            if "rss" in tipo or "atom" in tipo or "xml" in tipo:
                return urljoin(url, link.get("href", ""))

    raiz = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    for ruta in RUTAS_FEED:
        candidato = urljoin(raiz, ruta)
        r = descarga(candidato)
        if r and ("xml" in r.headers.get("Content-Type", "").lower()
                  or r.text.lstrip()[:200].lower().startswith(("<?xml", "<rss", "<feed"))):
            d = feedparser.parse(r.content)
            if d.entries:
                return candidato
        time.sleep(0.3)
    return None


# --- Extractores ----------------------------------------------------------

def es_relevante(texto: str, filtro: str) -> bool:
    t = normaliza(texto)
    if any(r in t for r in RUIDO) and len(t) < 60:
        return False
    tiene_evento = any(p in t for p in PALABRAS_EVENTO)
    if filtro == "estricto":
        return tiene_evento and bool(_RE_ESPECIALIDAD.search(t))
    return tiene_evento


_BORDES = ".,;:·-–—()[]|\"'«»"


def limpia_titulo(titulo: str, frag: str) -> str:
    """
    Algunas agendas meten la fecha dentro del enlace y además repiten el
    título: "63 Congreso SECOT 2026 30 de septiembre de 2026 63 Congreso SECOT
    2026". Quitamos la fecha (ya va en su columna) y la repetición. Si el
    resultado queda demasiado corto, devolvemos el título original.
    """
    palabras = titulo.split()
    # Los signos se ignoran solo para COMPARAR; el título conserva los suyos
    norm = [normaliza(p).strip(_BORDES) for p in palabras]
    trozo = [x for x in (normaliza(p).strip(_BORDES) for p in frag.split()) if x]
    n = len(trozo)
    limpio = titulo.strip()
    if n:
        for i in range(len(norm) - n + 1):
            if norm[i:i + n] == trozo:
                palabras = palabras[:i] + palabras[i + n:]
                # Al quitar la fecha pueden quedar separadores colgando
                # ("Curso X ·"); paréntesis y comillas se respetan
                limpio = " ".join(palabras).strip(" -–—·|:,;")
                break
    w = limpio.split()
    mitad = len(w) // 2
    if len(w) >= 4 and len(w) % 2 == 0 and \
            [normaliza(x) for x in w[:mitad]] == [normaliza(x) for x in w[mitad:]]:
        limpio = " ".join(w[:mitad])
    return limpio if len(limpio) >= 8 else titulo


def extrae_lugar(texto: str) -> str:
    """
    Heurística para la ciudad. Busca patrones 'en <Ciudad>' o una ciudad
    conocida en el texto. Si no la encuentra, devuelve vacío para que se
    revise a mano: mejor un hueco visible que un dato inventado.
    """
    CIUDADES = [
        "Madrid", "Barcelona", "Valencia", "Sevilla", "Zaragoza", "Málaga",
        "Murcia", "Bilbao", "Alicante", "Córdoba", "Valladolid", "Vigo",
        "Gijón", "Granada", "A Coruña", "Vitoria", "Vitoria-Gasteiz",
        "Santa Cruz de Tenerife", "Las Palmas de Gran Canaria", "Pamplona",
        "Santander", "Salamanca", "Toledo", "Badajoz", "Cáceres", "Oviedo",
        "San Sebastián", "Donostia", "Palma", "Logroño", "Albacete",
        "Ciudad Real", "Cádiz", "Huelva", "Jaén", "Almería", "León", "Burgos",
        "Girona", "Lleida", "Tarragona", "Castellón", "Santiago de Compostela",
        "Online", "Virtual",
    ]
    for c in sorted(CIUDADES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(c)}\b", texto, re.IGNORECASE):
            return c
    return ""


def desde_feed(url_feed: str, fuente: dict) -> list[Evento]:
    r = descarga(url_feed)
    if not r:
        return []
    d = feedparser.parse(r.content)
    eventos = []
    for e in d.entries[:60]:
        titulo = BeautifulSoup(e.get("title", ""), "lxml").get_text(" ", strip=True)
        resumen = BeautifulSoup(e.get("summary", ""), "lxml").get_text(" ", strip=True)
        conjunto = f"{titulo}. {resumen}"
        if not es_relevante(conjunto, fuente.get("filtro", "evento")):
            continue
        ini, fin, frag = extrae_fechas(conjunto)
        if not ini:
            continue
        eventos.append(Evento(
            titulo=limpia_titulo(titulo, frag)[:180] or resumen[:120],
            fecha_texto=frag,
            inicio=ini.isoformat(), fin=fin.isoformat() if fin else None,
            lugar=extrae_lugar(conjunto),
            entidad=fuente["nombre"],
            url=e.get("link", url_feed),
            ambito=fuente.get("ambito", "mixto"),
            via="feed",
        ))
    return eventos


def desde_html(url: str, html: str, fuente: dict) -> list[Evento]:
    """
    Extractor genérico. En lugar de un parser a medida por web, recorre los
    enlaces de la página y examina el bloque de texto que los rodea: si ahí
    hay una fecha y una palabra de evento, es candidato.
    """
    sopa = BeautifulSoup(html, "lxml")
    for tag in sopa(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    eventos, vistos = [], set()

    for a in sopa.find_all("a", href=True):
        texto_enlace = a.get_text(" ", strip=True)
        if len(texto_enlace) < 12:
            continue

        # Contexto: el bloque propio del enlace (título + fecha + sede).
        # Subimos por el árbol mientras el ancestro siga conteniendo UN SOLO
        # enlace sustancial. En cuanto abarca varios, es el contenedor de la
        # lista entera: paramos, o el evento heredaría la fecha del vecino.
        contenedor = a
        while contenedor.parent is not None:
            padre = contenedor.parent
            if padre.name in ("body", "html", "[document]"):
                break
            enlaces = [x for x in padre.find_all("a", href=True)
                       if len(x.get_text(" ", strip=True)) >= 12]
            if len(enlaces) > 1:
                break
            if len(padre.get_text(" ", strip=True)) > 500:
                break
            contenedor = padre
        contexto = contenedor.get_text(" ", strip=True)[:600]
        conjunto = f"{texto_enlace}. {contexto}"

        if not es_relevante(conjunto, fuente.get("filtro", "evento")):
            continue
        ini, fin, frag = extrae_fechas(conjunto)
        if not ini:
            continue

        clave = normaliza(texto_enlace)[:70]
        if clave in vistos:
            continue
        vistos.add(clave)

        eventos.append(Evento(
            titulo=limpia_titulo(texto_enlace, frag)[:180],
            fecha_texto=frag,
            inicio=ini.isoformat(), fin=fin.isoformat() if fin else None,
            lugar=extrae_lugar(conjunto),
            entidad=fuente["nombre"],
            url=urljoin(url, a["href"]),
            ambito=fuente.get("ambito", "mixto"),
            via="html",
        ))
    return eventos


# --- Rastreo de una fuente ------------------------------------------------

def rastrea(fuente: dict, verbose: bool = True) -> tuple[list[Evento], str]:
    url = fuente["url"]
    nombre = fuente["nombre"]

    if not robots_permite(url):
        return [], "robots.txt prohíbe el rastreo"

    r = descarga(url)
    if not r:
        return [], "no responde / error de red"

    html = r.text
    feed = busca_feed(url, html)
    if feed:
        ev = desde_feed(feed, fuente)
        if ev:
            return ev, f"feed ({len(ev)})"
        # hay feed pero sin eventos relevantes: probamos HTML igualmente
    ev = desde_html(url, html, fuente)
    via = "feed vacío → html" if feed else "html"
    return ev, f"{via} ({len(ev)})"


# --- Estado (para ver solo lo nuevo) --------------------------------------

def carga_estado() -> dict:
    if ESTADO.exists():
        return json.loads(ESTADO.read_text())
    return {"vistos": {}}


def guarda_estado(estado: dict) -> None:
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1))


# --- Memoria de cursos conocidos ------------------------------------------
#
# Las fuentes de nivel 2 y 3 se visitan una vez al mes o al trimestre. Si de
# cada visita solo se aprovechase "el próximo mes", los cursos de los meses
# siguientes no se verían nunca: cuando llegase su momento, nadie estaría
# mirando esa web. Por eso cada rastreo guarda TODO lo que encuentra hasta
# un año vista, y el post de cada lunes se construye con esta memoria:
# un curso descubierto en enero para marzo sale en el post de finales de
# febrero, aunque su web no se vuelva a visitar hasta abril.
#
# Vive dentro de salida/ para que el workflow de GitHub la guarde sin
# necesidad de tocarlo.

MEMORIA = SALIDA / "eventos-conocidos.json"
_CAMPOS_EVENTO = {f.name for f in fields(Evento)}


def carga_memoria() -> dict[str, dict]:
    if MEMORIA.exists():
        try:
            return json.loads(MEMORIA.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def guarda_memoria(memoria: dict[str, dict]) -> None:
    SALIDA.mkdir(exist_ok=True)
    MEMORIA.write_text(json.dumps(memoria, ensure_ascii=False, indent=1), encoding="utf-8")


def evento_desde_memoria(d: dict) -> "Evento":
    return Evento(**{k: v for k, v in d.items() if k in _CAMPOS_EVENTO})


# --- Salida ---------------------------------------------------------------

def a_markdown(eventos: list[Evento], hoy: date) -> str:
    lineas = [
        f"# Agenda — Anestesiología, Cuidados Críticos y Dolor",
        f"\nGenerada el {hoy.strftime('%d/%m/%Y')} · {len(eventos)} eventos\n",
        "| Título | Fechas | Lugar | Entidad organizadora |",
        "|---|---|---|---|",
    ]
    for e in eventos:
        ini = date.fromisoformat(e.inicio) if e.inicio else None
        fin = date.fromisoformat(e.fin) if e.fin else None
        titulo = e.titulo.replace("|", "/")
        lineas.append(
            f"| [{titulo}]({e.url}) | {formatea(ini, fin)} | {e.lugar or '—'} | {e.entidad} |"
        )
    lineas.append(
        "\n> Verificar cada evento en la web oficial antes de publicar: "
        "los rastreadores capturan fechas desactualizadas cuando el organizador las cambia."
    )
    return "\n".join(lineas)


def a_csv(eventos: list[Evento]) -> str:
    import csv, io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(asdict(eventos[0]).keys()) if eventos else
                       ["titulo", "fecha_texto", "inicio", "fin", "lugar", "entidad", "url", "ambito", "via", "id"])
    w.writeheader()
    for e in eventos:
        w.writerow(asdict(e))
    return buf.getvalue()


# --- Principal ------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Rastreador de agenda formativa")
    ap.add_argument("--nivel", nargs="+", type=int, default=[1],
                    help="niveles a rastrear (1 semanal, 2 mensual, 3 anual)")
    ap.add_argument("--meses", type=int, default=1,
                    help="ventana del post: cuántos meses hacia delante se muestran (por defecto 1)")
    ap.add_argument("--horizonte", type=int, default=12,
                    help="cuántos meses hacia delante se recogen y se guardan en memoria (por defecto 12)")
    ap.add_argument("--todo", action="store_true",
                    help="muestra también lo ya visto; NO escribe ninguna memoria")
    ap.add_argument("--diagnostico", action="store_true",
                    help="informe de salud de cada fuente")
    ap.add_argument("--hoy", help=argparse.SUPPRESS)  # solo para pruebas: simula otra fecha
    args = ap.parse_args()

    hoy = date.fromisoformat(args.hoy) if args.hoy else date.today()
    limite = hoy + timedelta(days=args.meses * 31)
    horizonte = hoy + timedelta(days=max(args.horizonte, args.meses) * 31)
    margen = hoy - timedelta(days=2)

    cfg = yaml.safe_load((BASE / "fuentes.yaml").read_text(encoding="utf-8"))
    fuentes = [f for f in cfg["fuentes"] if f.get("nivel", 1) in args.nivel]

    # Las marcadas como rotas por verificar.py se saltan: no tiene sentido
    # llamar cada semana a una puerta que sabemos que no abre.
    saltadas = [f for f in fuentes if f.get("estado") == "roto"]
    fuentes = [f for f in fuentes if f.get("estado") != "roto"]

    print(f"Rastreando {len(fuentes)} fuentes (nivel {args.nivel})"
          + (f" · {len(saltadas)} marcadas como rotas, se saltan" if saltadas else "")
          + "\n", file=sys.stderr)

    todos: list[Evento] = []
    informe: list[tuple[str, str, int]] = []
    hecho = 0

    with ThreadPoolExecutor(max_workers=HILOS) as ex:
        for f, (ev, estado_txt) in zip(fuentes, ex.map(lambda x: rastrea(x), fuentes)):
            hecho += 1
            informe.append((f["nombre"], estado_txt, len(ev)))
            marca = "✓" if ev else (
                "!" if ("prohíbe" in estado_txt or "no responde" in estado_txt) else "·")
            print(f" {marca} [{hecho:>3}/{len(fuentes)}] {f['nombre'][:40]:<40} {estado_txt}",
                  file=sys.stderr)
            todos.extend(ev)

    # Deduplicar entre fuentes (un congreso aparece en varias webs)
    unicos: dict[str, Evento] = {}
    for e in todos:
        if e.id not in unicos:
            unicos[e.id] = e
    # Lo recién encontrado, hasta el horizonte (un año por defecto)
    frescos = [e for e in unicos.values()
               if e.inicio and margen <= date.fromisoformat(e.inicio) <= horizonte]

    # Se suma a la memoria de cursos conocidos y se olvida lo ya pasado
    memoria = carga_memoria()
    for e in frescos:
        d = asdict(e)
        d["descubierto"] = memoria.get(e.id, {}).get("descubierto", hoy.isoformat())
        d["ultima_vez"] = hoy.isoformat()
        memoria[e.id] = d
    memoria = {k: v for k, v in memoria.items()
               if v.get("inicio") and date.fromisoformat(v["inicio"]) >= margen}
    if not args.todo:
        guarda_memoria(memoria)

    # El post sale de la memoria, no solo de lo visitado hoy: así entran los
    # cursos de fuentes mensuales y trimestrales cuando les llega su momento.
    eventos = [evento_desde_memoria(d) for d in memoria.values()
               if margen <= date.fromisoformat(d["inicio"]) <= limite]

    # Solo lo nuevo.
    #
    # Ojo con la memoria: solo se apunta lo que se ha ENSEÑADO. Si se apuntara
    # todo lo que entra en la ventana, un rastreo con ventana ancha marcaría
    # como "ya visto" un congreso de dentro de seis meses, y cuando ese congreso
    # entrase en la ventana del post semanal ya no aparecería como nuevo:
    # se perdería sin dejar rastro. Por eso --todo no escribe nada: es una
    # consulta de lectura, no altera lo que verás el lunes.
    estado = carga_estado()
    if args.todo:
        nuevos = eventos
    else:
        nuevos = [e for e in eventos if e.id not in estado["vistos"]]
        for e in nuevos:
            estado["vistos"][e.id] = hoy.isoformat()
        # Lo enseñado hace más de un año ya no puede repetirse: se olvida
        antiguedad = (hoy - timedelta(days=400)).isoformat()
        estado["vistos"] = {k: v for k, v in estado["vistos"].items() if v >= antiguedad}
        guarda_estado(estado)

    eventos.sort(key=lambda e: e.inicio or "9999")
    nuevos.sort(key=lambda e: e.inicio or "9999")

    SALIDA.mkdir(exist_ok=True)
    sello = hoy.isoformat()
    (SALIDA / f"agenda-{sello}.md").write_text(a_markdown(eventos, hoy), encoding="utf-8")
    if eventos:
        (SALIDA / f"agenda-{sello}.csv").write_text(a_csv(eventos), encoding="utf-8")

    print(f"\n{len(frescos)} cursos encontrados hoy · {len(memoria)} en memoria · "
          f"{len(eventos)} en la ventana del post · {len(nuevos)} nuevos",
          file=sys.stderr)
    print(f"→ salida/agenda-{sello}.md\n", file=sys.stderr)

    if args.diagnostico:
        print("\n--- Salud de las fuentes ---", file=sys.stderr)
        for nombre, est, n in sorted(informe, key=lambda x: -x[2]):
            print(f"{n:>3}  {nombre:<34} {est}", file=sys.stderr)

    print(a_markdown(nuevos if not args.todo else eventos, hoy))
    return 0


if __name__ == "__main__":
    sys.exit(main())
