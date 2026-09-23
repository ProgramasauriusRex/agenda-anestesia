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

from fechas import extrae_fechas, formatea, anio_en_texto

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


def _pide_robots(url_robots: str):
    """Pide robots.txt con NUESTRAS cabeceras, y devuelve la respuesta tal cual
    (con su código), sin tratar el 404 como un fallo."""
    espera_turno(url_robots)
    try:
        r = requests.get(url_robots, headers=CAB_BOT, timeout=TIMEOUT)
        if r.status_code in RECHAZO_POR_CABECERAS:
            espera_turno(url_robots)
            r = requests.get(url_robots, headers=CAB_NAVEGADOR, timeout=TIMEOUT)
        return r
    except Exception:
        return None


def _lee_robots(dominio: str) -> robotparser.RobotFileParser | None:
    """
    Descarga e interpreta el robots.txt de un dominio.

    No se usa `rp.read()`, que es lo que hace todo el mundo, porque pide el
    archivo con el User-Agent por defecto de Python. Muchos sitios con
    cortafuegos delante (Cloudflare y similares) responden 403 a ese cliente,
    y la librería estándar traduce ese 403 a «este sitio prohíbe todo».

    Así fue como 27 de las 211 webs quedaron marcadas como bloqueadas sin que
    ninguna lo prohibiera de verdad: al mirar sus robots.txt uno por uno, ni
    uno solo tenía la regla que se les atribuía. La UCLM, la Universidad de
    Extremadura, el CGCOM o la Universidad de Córdoba se limitaban a rechazar
    a un cliente que no parecía un navegador.

    El criterio que se sigue aquí es el del RFC 9309, el estándar vigente de
    robots.txt:
      - 200  → se obedece lo que diga el archivo.
      - 4xx  → no hay archivo, o no se nos deja verlo: sin restricciones.
      - 5xx  → el servidor falla: se asume prohibido, por prudencia.
      - error de red → sin restricciones (no se puede paralizar el rastreo
        entero porque una petición se caiga).

    Devolver None significa «sin restricciones».
    """
    url_robots = urljoin(dominio, "/robots.txt")
    r = _pide_robots(url_robots)

    if r is None:
        return None
    if r.status_code >= 500:
        rp = robotparser.RobotFileParser()
        rp.disallow_all = True
        return rp
    if r.status_code >= 400:
        return None

    if "charset" not in r.headers.get("Content-Type", "").lower():
        r.encoding = r.apparent_encoding or "utf-8"
    rp = robotparser.RobotFileParser()
    rp.set_url(url_robots)
    try:
        rp.parse(r.text.splitlines())
    except Exception:
        return None
    return rp


def robots_permite(url: str) -> bool:
    """Comprueba robots.txt. Ante la duda (error de red), permite."""
    dominio = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if dominio not in _robots_cache:
        _robots_cache[dominio] = _lee_robots(dominio)
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

# Enlaces que no son un título aunque estén junto a una fecha: "Leer más",
# "Ver programa"… Solo se descartan si el texto es corto; si no, se estaría
# tirando un título legítimo que contenga la palabra ("Inscripción abierta:
# Curso de…").
NO_SON_TITULO = [
    "leer mas", "ver mas", "saber mas", "ver y leer", "mas informacion",
    "mas info", "ampliar informacion", "ver programa", "descargar programa",
    "descargar", "pincha aqui", "clic aqui", "haz clic", "acceder",
    "comunicaciones online", "ver detalle", "ver ficha", "continuar leyendo",
]
# Avisos de que el curso se ha llenado. No se descarta —que exista y se haya
# llenado también es información— pero se saca del título y se deja como nota
# al final, para que el título se lea limpio.
SIN_PLAZAS = [
    "plazas agotadas", "aforo completo", "inscripcion cerrada",
    "curso completo", "matricula cerrada", "plazo cerrado", "completo",
]

# Muchas webs cuelgan la ficha entera dentro del enlace: "Curso X Nombre del
# curso: … Día y hora: … Plazas: …". A partir de una de estas etiquetas ya no
# hay título, hay formulario: se corta ahí. Se exige los dos puntos para no
# cortar títulos legítimos, y que haya al menos tres palabras antes.
ETIQUETAS_FICHA = [
    "nombre del curso:", "dia y hora:", "dias y horas:", "fecha de inicio:",
    "lugar de celebracion:", "horario:", "duracion:", "plazas:", "precio:",
    "dirigido a:", "modalidad:", "matricula:", "objetivos:", "temario:",
]
# Etiquetas que quedan colgando al quitar la fecha ("...Medicina Intensiva Fecha")
ETIQUETAS_FINALES = {"fecha", "fechas", "cuando", "horario", "inicio", "lugar", "sede"}


def titulo_util(titulo: str) -> bool:
    """¿Este texto sirve como título de un curso?"""
    n = normaliza(titulo)
    if len(n) < 12:
        return False
    if len(n) < 50 and any(p in n for p in NO_SON_TITULO):
        return False
    return True


def corta_en_ficha(titulo: str) -> str:
    """Corta el título donde empieza la ficha del curso."""
    w = titulo.split()
    norm = [normaliza(x) for x in w]
    corte = None
    for etiqueta in ETIQUETAS_FICHA:
        trozo = etiqueta.split()
        n = len(trozo)
        for i in range(3, len(norm) - n + 1):
            if norm[i:i + n] == trozo:
                corte = i if corte is None else min(corte, i)
                break
    return " ".join(w[:corte]) if corte else titulo


def separa_sin_plazas(titulo: str) -> tuple[str, bool]:
    """
    Saca del título los avisos de "plazas agotadas" y devuelve el título
    limpio junto con la señal de si el curso está lleno.
    """
    lleno = False
    limpio = titulo
    for aviso in SIN_PLAZAS:
        patron = re.compile(re.escape(aviso).replace(r"\ ", r"\s+"), re.IGNORECASE)
        # Tolerante con tildes: "inscripción cerrada" y "matrícula cerrada"
        patron_tildes = re.compile(
            patron.pattern.replace("inscripcion", "inscripci[oó]n")
                          .replace("matricula", "matr[ií]cula"), re.IGNORECASE)
        if patron_tildes.search(limpio):
            lleno = True
            limpio = patron_tildes.sub(" ", limpio)
    if lleno:
        limpio = re.sub(r"\s+", " ", limpio).strip(" " + _BORDES)
    return limpio, lleno


def titulo_desde_url(url: str) -> str:
    """
    Último recurso cuando el enlace dice "Ver y leer más": la propia dirección
    suele llevar el nombre. De .../70-reunion-anual-aaear-2026 sale un título
    pobre pero informativo, que es mejor que perder el curso.
    """
    ruta = urlparse(url).path.rstrip("/").split("/")[-1]
    ruta = re.sub(r"\.(html?|php|aspx?|jsp)$", "", ruta, flags=re.I)
    ruta = re.sub(r"[-_]+", " ", ruta).strip()
    if len(ruta) < 12 or ruta.replace(" ", "").isdigit():
        return ""
    return ruta[:1].upper() + ruta[1:]


# Siglas y números romanos que deben seguir en mayúsculas al arreglar un
# título que venía gritado
SIGLAS_INTACTAS = {
    "SVA", "SVB", "DEA", "RCP", "UCI", "URPA", "TIVA", "TCI", "POCUS", "DEU",
    "SEDAR", "SEMICYUC", "SED", "SEMDOR", "SECPAL", "ESRA", "SECIP", "SEEIUC",
    "FEEA", "EDAIC", "SEMES", "CERCP", "ONT", "IA", "EPOC", "SDRA", "VMNI",
    "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "XIII", "XIV",
    "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV",
    "XXV", "XXVI", "XXVII", "XXVIII", "XXIX", "XXX",
}


def arregla_mayusculas(titulo: str) -> str:
    """
    "DIPLOMA DE ESPECIALIZACIÓN EN EL MANEJO DE LA SEPSIS" grita en un post.
    Si el título viene casi entero en mayúsculas se pasa a formato normal,
    respetando siglas y números romanos. Si no, se deja como está: puede que
    las mayúsculas sean intencionadas.
    """
    letras = [c for c in titulo if c.isalpha()]
    if len(letras) < 12 or sum(c.isupper() for c in letras) / len(letras) < 0.8:
        return titulo
    MINUSCULAS = {"de", "del", "la", "las", "el", "los", "y", "e", "en", "a",
                  "al", "con", "para", "por", "sobre", "un", "una", "the", "of"}
    salida = []
    for i, palabra in enumerate(titulo.split()):
        nucleo = palabra.strip(".,;:()[]«»\"'")
        if nucleo.upper() in SIGLAS_INTACTAS or (nucleo.isupper() and len(nucleo) <= 4
                                                 and not nucleo.isalpha()):
            salida.append(palabra)
        elif i > 0 and nucleo.lower() in MINUSCULAS:
            salida.append(palabra.lower())
        else:
            salida.append(palabra.capitalize())
    return " ".join(salida)


def recorta(titulo: str, maximo: int = 120) -> str:
    """Corta por separador o por palabra, nunca a mitad de una."""
    if len(titulo) <= maximo:
        return titulo
    trozo = titulo[:maximo]
    corte = max(trozo.rfind(" · "), trozo.rfind(" | "), trozo.rfind(". "),
                trozo.rfind(" – "), trozo.rfind(" - "))
    if corte < maximo // 2:
        corte = trozo.rfind(" ")
    return trozo[:corte].rstrip(" " + _BORDES) + "…"


def limpia_titulo(titulo: str, frag: str) -> str:
    """
    Algunas agendas meten la fecha dentro del enlace y además repiten el
    título: "63 Congreso SECOT 2026 30 de septiembre de 2026 63 Congreso SECOT
    2026". Quitamos la fecha (ya va en su columna) y la repetición. Si el
    resultado queda demasiado corto, devolvemos el título original.
    """
    titulo = corta_en_ficha(titulo)
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
                # Separadores colgando ("Curso X ·"); los paréntesis y las
                # comillas se respetan
                limpio = " ".join(palabras).strip(" -–—·|:,;")
                break

    # Etiquetas huérfanas al final ("…Medicina Intensiva Fecha"). Se hace
    # siempre, no solo si la fecha estaba en el título: muchas webs la guardan
    # en un atributo oculto y dejan la etiqueta suelta en el texto visible.
    w = limpio.split()
    while w and normaliza(w[-1]).strip(_BORDES) in ETIQUETAS_FINALES:
        w.pop()
    limpio = " ".join(w).strip(" -–—·|:,;")

    w = limpio.split()
    mitad = len(w) // 2
    if len(w) >= 4 and len(w) % 2 == 0 and \
            [normaliza(x) for x in w[:mitad]] == [normaliza(x) for x in w[mitad:]]:
        limpio = " ".join(w[:mitad])
    return limpio if len(limpio) >= 8 else titulo


def extrae_lugar(texto: str) -> str:
    """
    Ciudad o modalidad del curso. En la primera tanda real, 12 de 27 cursos
    salían sin lugar, así que aquí se mira en tres pasadas: primero si es
    online, luego una etiqueta explícita ("Sede:", "Lugar:"), y por último
    cualquier ciudad española reconocible.

    Si no encuentra nada devuelve vacío. Nunca se deduce del organizador:
    que un curso lo dé el Colegio de Málaga no significa que sea en Málaga,
    y un hueco visible es preferible a un dato inventado.
    """
    t = " " + re.sub(r"\s+", " ", texto) + " "

    # 1. Modalidad a distancia, que gana a cualquier ciudad que se mencione
    if re.search(r"\b(?:100%\s*)?(?:on-?line|en línea|virtual|streaming|"
                 r"tele(?:formación|matic\w*)|a distancia)\b", t, re.I):
        return "Online"

    CIUDADES = [
        "A Coruña", "Albacete", "Alcalá de Henares", "Algeciras", "Alicante",
        "Almería", "Ávila", "Badajoz", "Badalona", "Barcelona", "Bilbao",
        "Burgos", "Cáceres", "Cádiz", "Cartagena", "Castellón", "Ceuta",
        "Ciudad Real", "Córdoba", "Cuenca", "Donostia", "Elche", "Ferrol",
        "Getafe", "Gijón", "Girona", "Granada", "Guadalajara", "Huelva",
        "Huesca", "Jaén", "Jerez de la Frontera", "Las Palmas de Gran Canaria",
        "Las Palmas", "León", "Lleida", "Logroño", "Lugo", "Madrid", "Málaga",
        "Marbella", "Melilla", "Mérida", "Móstoles", "Murcia", "Ourense",
        "Oviedo", "Palencia", "Palma", "Pamplona", "Pontevedra", "Reus",
        "Sabadell", "Salamanca", "San Sebastián", "Santander",
        "Santa Cruz de Tenerife", "Santiago de Compostela", "Segovia",
        "Sevilla", "Soria", "Tarragona", "Terrassa", "Teruel", "Toledo",
        "Valdepeñas", "Valencia", "Valladolid", "Vigo", "Vitoria-Gasteiz",
        "Vitoria", "Zamora", "Zaragoza", "Talavera de la Reina",
    ]

    # 2. Etiqueta explícita: "Sede: Hotel X, Valencia" / "Lugar: Madrid"
    etiqueta = re.search(r"\b(?:sede|lugar|ubicaci[oó]n|celebra(?:ci[oó]n)?\s+en|"
                         r"tendr[aá]\s+lugar\s+en)\s*:?\s*([^.;|]{3,80})", t, re.I)
    # Gana la que aparece ANTES en el texto, y a igualdad la más larga: en
    # "Valdepeñas (Ciudad Real)" la sede es Valdepeñas y la provincia solo
    # acompaña; en "Las Palmas de Gran Canaria" gana el nombre completo.
    def primera(donde: str) -> str:
        halladas = []
        for c in CIUDADES:
            m = re.search(rf"\b{re.escape(c)}\b", donde, re.I)
            if m:
                halladas.append((m.start(), -len(c), c))
        return min(halladas)[2] if halladas else ""

    if etiqueta and (c := primera(etiqueta.group(1))):
        return c
    return primera(t)


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
        limpio, lleno = separa_sin_plazas(limpia_titulo(titulo, frag) or resumen)
        if not titulo_util(limpio):
            continue
        eventos.append(Evento(
            titulo=recorta(arregla_mayusculas(limpio)) + (" — plazas agotadas" if lleno else ""),
            fecha_texto=frag,
            inicio=ini.isoformat(), fin=fin.isoformat() if fin else None,
            lugar=extrae_lugar(conjunto),
            entidad=fuente["nombre"],
            url=e.get("link", url_feed),
            ambito=fuente.get("ambito", "mixto"),
            via="feed",
        ))
    return eventos


# --- Entrar en la ficha del curso -----------------------------------------
#
# El diagnóstico del 23/09 dejó claro dónde se perdían los cursos: muchas webs
# listan solo el título ("Diploma de especialización en el manejo de la sepsis
# y shock séptico") y la fecha vive dentro de la ficha. Sin entrar, se pierden.
#
# Entrar cuesta una petición por curso, así que se hace con cuentagotas: solo
# para enlaces cuyo PROPIO TEXTO ya delata la especialidad, y con tope por
# fuente y global.

SEGUIR_POR_FUENTE = 8
SEGUIR_TOTAL = 250
_seguidos = 0
_candado_seguir = Lock()

# Palabras que suelen preceder a la fecha del evento en la ficha, para no
# quedarse con la fecha de publicación ni con el plazo de inscripción
PISTAS_FECHA = ["se celebra", "se celebrara", "tendra lugar", "fecha", "fechas",
                "dias", "cuando", "lugar y fecha", "del", "celebracion"]


def _cupo_para_seguir() -> bool:
    global _seguidos
    with _candado_seguir:
        if _seguidos >= SEGUIR_TOTAL:
            return False
        _seguidos += 1
        return True


def fecha_en_la_ficha(url: str) -> tuple[date | None, date | None, str, str]:
    """
    Abre la ficha de un curso y busca allí su fecha. Devuelve también el texto
    de la ficha, que sirve para sacar la ciudad: el listado casi nunca la trae.
    """
    if not robots_permite(url) or not _cupo_para_seguir():
        return None, None, "", ""
    r = descarga(url)
    if not r:
        return None, None, "", ""
    try:
        sopa = BeautifulSoup(r.text, "lxml")
    except Exception:
        return None, None, "", ""
    for tag in sopa(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    texto = sopa.get_text(" ", strip=True)[:6000]

    hoy = date.today()
    trozos = [texto[i:i + 300] for i in range(0, len(texto), 250)]
    respaldo = None
    for trozo in trozos:
        ini, fin, frag = extrae_fechas(trozo)
        if not ini or not (hoy - timedelta(days=2) <= ini <= hoy + timedelta(days=400)):
            continue
        # Con una pista delante, es la fecha del evento y no la de publicación
        if any(p in normaliza(trozo) for p in PISTAS_FECHA):
            return ini, fin, frag, texto
        if respaldo is None:
            respaldo = (ini, fin, frag, texto)
    return respaldo or (None, None, "", "")


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
    sin_fecha: list[tuple[str, str]] = []   # candidatos a mirar en su ficha
    dominio = urlparse(url).netloc

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
            # Sin fecha al lado. Si el texto del enlace ya delata por sí solo
            # que es un curso de la especialidad, vale la pena abrir su ficha.
            destino = urljoin(url, a["href"])
            anio = anio_en_texto(texto_enlace)
            if (es_relevante(texto_enlace, "estricto")
                    and titulo_util(texto_enlace)
                    and urlparse(destino).netloc == dominio
                    and not (anio and anio < date.today().year)
                    and len(sin_fecha) < SEGUIR_POR_FUENTE):
                sin_fecha.append((texto_enlace, destino))
            continue

        limpio, lleno = separa_sin_plazas(limpia_titulo(texto_enlace, frag))
        if not titulo_util(limpio):
            # "Ver y leer más sobre el congreso…" no dice nada, pero la
            # dirección del enlace suele llevar el nombre del evento
            limpio = titulo_desde_url(urljoin(url, a["href"]))
            if not titulo_util(limpio):
                continue

        clave = normaliza(limpio)[:70]
        if clave in vistos:
            continue
        vistos.add(clave)

        eventos.append(Evento(
            titulo=recorta(arregla_mayusculas(limpio)) + (" — plazas agotadas" if lleno else ""),
            fecha_texto=frag,
            inicio=ini.isoformat(), fin=fin.isoformat() if fin else None,
            lugar=extrae_lugar(conjunto),
            entidad=fuente["nombre"],
            url=urljoin(url, a["href"]),
            ambito=fuente.get("ambito", "mixto"),
            via="html",
        ))

    # Segunda pasada: los que no tenían fecha en el listado, se abren
    for texto_enlace, destino in sin_fecha:
        clave = normaliza(texto_enlace)[:70]
        if clave in vistos:
            continue
        ini, fin, frag, texto_ficha = fecha_en_la_ficha(destino)
        if not ini:
            continue
        limpio, lleno = separa_sin_plazas(limpia_titulo(texto_enlace, frag))
        if not titulo_util(limpio):
            continue
        vistos.add(clave)
        eventos.append(Evento(
            titulo=recorta(arregla_mayusculas(limpio)) + (" — plazas agotadas" if lleno else ""),
            fecha_texto=frag,
            inicio=ini.isoformat(), fin=fin.isoformat() if fin else None,
            lugar=extrae_lugar(f"{texto_enlace} {texto_ficha[:1500]}"),
            entidad=fuente["nombre"],
            url=destino,
            ambito=fuente.get("ambito", "mixto"),
            via="ficha",
        ))
    return eventos


# --- Rastreo de una fuente ------------------------------------------------

def rastrea(fuente: dict, verbose: bool = True) -> tuple[list[Evento], str]:
    url = fuente["url"]
    nombre = fuente["nombre"]

    if not robots_permite(url):
        return [], "robots.txt prohíbe el rastreo"

    # Si el verificador ya averiguó si esta web tiene RSS, no se vuelve a
    # preguntar. Sondear 13 direcciones a ciegas cada semana, en webs que ya
    # sabemos que no tienen canal, es la diferencia entre 21 segundos y 2 por
    # fuente: justo lo que permite revisarlas todas cada lunes.
    conocido = str(fuente.get("feed") or "").strip()
    if conocido and conocido.lower() != "none":
        ev = desde_feed(conocido, fuente)
        if ev:
            return ev, f"feed ({len(ev)})"
        # El canal puede haber muerto o no traer eventos: seguimos por HTML

    r = descarga(url)
    if not r:
        return [], "no responde / error de red"

    html = r.text
    feed = None
    if not conocido:                      # aún no sabemos si tiene canal
        feed = busca_feed(url, html)
        if feed:
            ev = desde_feed(feed, fuente)
            if ev:
                return ev, f"feed ({len(ev)})"
    ev = desde_html(url, html, fuente)
    via = "feed vacío → html" if (feed or conocido) else "html"
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
    if not MEMORIA.exists():
        return {}
    try:
        return sanea_memoria(json.loads(MEMORIA.read_text(encoding="utf-8")))
    except Exception:
        return {}


def sanea_memoria(memoria: dict[str, dict]) -> dict[str, dict]:
    """
    Revisa lo guardado con las reglas de HOY, no con las del día en que se
    guardó. Cuando se afina un filtro o se corrige un fallo, la memoria
    arrastraría los errores antiguos para siempre; así se limpian solos.

    Quita dos cosas: lo que ya no pasaría el corte de títulos, y aquello cuyo
    título delata un año anterior al de su fecha guardada — el caso del
    "XVIII Congreso SED 2022" archivado como si fuese de octubre de 2026.
    """
    limpia = {}
    for k, v in memoria.items():
        titulo = v.get("titulo", "")
        if not titulo_util(titulo):
            continue
        anio = anio_en_texto(titulo)
        if anio and v.get("inicio") and anio < int(v["inicio"][:4]):
            continue
        # Guardado con un título sucio (ficha del curso dentro, avisos de
        # plazas): se olvida para que el siguiente rastreo lo recoja limpio
        if corta_en_ficha(titulo) != titulo or separa_sin_plazas(titulo)[1]:
            continue
        limpia[k] = v
    return limpia


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
