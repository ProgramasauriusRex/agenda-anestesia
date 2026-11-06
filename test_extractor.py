"""Prueba el extractor genérico con HTML que imita las webs reales."""
from agenda import desde_html, desde_feed, es_relevante, extrae_lugar
from fechas import formatea
from datetime import date

# Imita un WordPress de sociedad (estructura tipo socartd.es / samiuc.es)
HTML_SOCIEDAD = """
<html><head><link rel="alternate" type="application/rss+xml" href="/feed/"></head>
<body>
<nav><a href="/politica-privacidad">Política de privacidad</a><a href="/socios">Hazte socio</a></nav>
<div class="eventos">
  <article><h2><a href="/evento/xxv-jornadas">XXV Jornadas Canarias de Anestesiología, Reanimación y Terapéutica del Dolor</a></h2>
    <p class="meta">15, 16 y 17 de mayo de 2027 · Colegio Oficial de Médicos de Santa Cruz de Tenerife</p></article>
  <article><h2><a href="/evento/curso-sva">Curso de Soporte Vital Avanzado (SVA)</a></h2>
    <p class="meta">Del 26 al 27 de octubre de 2026 — sede SEMICYUC, Madrid. 16 plazas.</p></article>
  <article><h2><a href="/noticia/junta">Nueva junta directiva de la sociedad</a></h2>
    <p>Se ha renovado la junta.</p></article>
  <article><h2><a href="/evento/taller-via-aerea">Taller de manejo de vía aérea difícil ecoguiada</a></h2>
    <p class="meta">22/10/2026, Hospital Universitario La Paz, Madrid</p></article>
</div>
<footer><a href="/aviso-legal">Aviso legal</a></footer>
</body></html>
"""

# Imita un agregador generalista (filtro estricto debe descartar lo no-especialidad)
HTML_AGREGADOR = """
<html><body>
<ul>
 <li><a href="/e/1">52º Congreso Nacional de la Sociedad Española de Reumatología</a> — 5 de mayo de 2027, Valencia</li>
 <li><a href="/e/2">XIX Curso de Ecografía en el Paciente Crítico</a> — del 3 al 5 de marzo de 2027, Barcelona</li>
 <li><a href="/e/3">Congreso SEOM de Oncología Médica</a> — 11 de noviembre de 2026, Madrid</li>
 <li><a href="/e/4">Jornada de actualización en dolor crónico y opioides</a> — 14 de enero de 2027, Sevilla</li>
</ul>
</body></html>
"""

def prueba(nombre, html, fuente):
    print(f"\n=== {nombre} (filtro: {fuente['filtro']}) ===")
    ev = desde_html("https://ejemplo.es/agenda", html, fuente)
    for e in ev:
        ini = date.fromisoformat(e.inicio); fin = date.fromisoformat(e.fin) if e.fin else None
        print(f"  ✓ {e.titulo[:58]:<58} | {formatea(ini,fin):<26} | {e.lugar or '—'}")
    if not ev: print("  (nada)")
    return ev

a = prueba("Web de sociedad", HTML_SOCIEDAD,
           {"nombre":"SOCARTD","filtro":"evento","ambito":"anestesia"})
b = prueba("Agregador generalista", HTML_AGREGADOR,
           {"nombre":"DimeCongresos","filtro":"estricto","ambito":"mixto"})

print("\n--- Comprobaciones ---")
titulos_a = " ".join(e.titulo for e in a)
assert "Jornadas Canarias" in titulos_a, "debería capturar las jornadas"
assert "Soporte Vital" in titulos_a, "debería capturar el curso SVA"
assert "junta directiva" not in titulos_a, "no debería capturar noticias sin fecha de evento"
assert len(a) == 3, f"esperados 3 eventos, obtenidos {len(a)}"
titulos_b = " ".join(e.titulo for e in b)
assert "Reumatología" not in titulos_b, "filtro estricto debería descartar reumatología"
assert "Oncología" not in titulos_b, "filtro estricto debería descartar oncología"
assert "Ecografía" in titulos_b and "dolor" in titulos_b.lower()
assert len(b) == 2, f"esperados 2 eventos, obtenidos {len(b)}"
print("Todas las comprobaciones OK ✓")


# ---------------------------------------------------------------------------
# Filtro de especialidad (webs generalistas: colegios, universidades...)
# ---------------------------------------------------------------------------
from agenda import limpia_titulo

DEBE_PASAR = [
    "Curso de Soporte Vital Avanzado (SVA) para médicos",
    "Taller de manejo de la vía aérea difícil",
    "Jornada de actualización en dolor crónico",
    "Curso de ecografía clínica a pie de cama (POCUS)",
    "Webinar: sedoanalgesia en la UCI",
    "Curso de bloqueos nerviosos ecoguiados",
    "XV Congreso Internacional SECPAL de cuidados paliativos",
    "Jornada sobre el manejo del paciente crítico politraumatizado",
    "Multidisciplinary World Pain Forum 2027",
    "Euroanaesthesia Congress 2027",
    "Jornada de neuroanestesia",
    "Taller de ventilación mecánica no invasiva",
    "XV Congreso Internacional SECPAL",
    "Jornada SEDAR de residentes",
    "22 Congreso de la Sociedad Española del Dolor SED",
]
NO_DEBE_PASAR = [
    "Curso intensivo de inglés médico",
    "Taller para reducir el estrés en consulta",
    "Curso de pensamiento crítico y lectura de artículos",
    "Curso de fiscalidad para médicos autónomos",
    "Jornada sobre bloqueo AV y trastornos de la conducción",
    "63 Congreso SECOT 2026",
    "48 Congreso SEMERGEN 2026",
    "Taller de conducción segura para residentes",
    "International Congress in Spain on Dermatology",
]
for t in DEBE_PASAR:
    assert es_relevante(t, "estricto"), f"debería pasar el filtro: {t}"
for t in NO_DEBE_PASAR:
    assert not es_relevante(t, "estricto"), f"no debería pasar el filtro: {t}"
print(f"Filtro de especialidad: {len(DEBE_PASAR)} aciertos, {len(NO_DEBE_PASAR)} descartes ✓")

# ---------------------------------------------------------------------------
# Limpieza de títulos
# ---------------------------------------------------------------------------
for orig, frag, esperado in [
    ("63 Congreso SECOT 2026 30 de septiembre de 2026 63 Congreso SECOT 2026",
     "30 de septiembre de 2026", "63 Congreso SECOT 2026"),
    ("Curso de Vía Aérea · 12, 13 y 14 de noviembre de 2026",
     "12, 13 y 14 de noviembre de 2026", "Curso de Vía Aérea"),
    ("Curso SVA Semipresencial del PNRCP-SEMICYUC", "28 de septiembre",
     "Curso SVA Semipresencial del PNRCP-SEMICYUC"),
    ("Jornada 17 de octubre", "17 de octubre", "Jornada 17 de octubre"),
]:
    r = limpia_titulo(orig, frag)
    assert r == esperado, f"«{r}» ≠ «{esperado}»"
print("Limpieza de títulos ✓")
assert limpia_titulo("Curso de Soporte Vital Avanzado (SVA)", "26 de octubre") == \
    "Curso de Soporte Vital Avanzado (SVA)", "no debe comerse el paréntesis"
assert limpia_titulo("«Jornada de Dolor» 5 de mayo de 2027", "5 de mayo de 2027") == \
    "«Jornada de Dolor»", "debe conservar las comillas"
print("Paréntesis y comillas intactos ✓")


# ---------------------------------------------------------------------------
# Defectos reales detectados en la agenda del 21/09/2026
# ---------------------------------------------------------------------------
from agenda import titulo_util, titulo_desde_url, sanea_memoria, separa_sin_plazas
from fechas import extrae_fechas as _ef

# 1. Curso lleno: SÍ figura, pero con el título limpio y marcado.
#    La ficha del curso que venía dentro del enlace se corta.
_malaga = ("PLAZAS AGOTADAS | Curso de Soporte Vital Básico (SVB) y DEA Presencial y "
           "online PLAZAS AGOTADAS Nombre del curso: Curso de Soporte Vital Básico "
           "(SVB) y DEA. Día y hora: Martes de 1")
_limpio, _lleno = separa_sin_plazas(limpia_titulo(_malaga, "6 de octubre de 2026"))
assert _lleno, "debería detectar que está lleno"
assert titulo_util(_limpio), "debería seguir figurando"
assert _limpio == "Curso de Soporte Vital Básico (SVB) y DEA Presencial y online", _limpio
assert "Nombre del curso" not in _limpio and "PLAZAS" not in _limpio

# 1b. Un título legítimo no se corta por parecerse a una etiqueta de ficha
assert limpia_titulo("Jornada sobre objetivos hemodinámicos en shock séptico", "") == \
    "Jornada sobre objetivos hemodinámicos en shock séptico"

# 2. Etiqueta "Fecha" huérfana cuando la fecha venía de un atributo oculto
assert limpia_titulo("Congreso Panamericano e Ibérico de Medicina Intensiva Fecha",
                     "2026-10-04") == "Congreso Panamericano e Ibérico de Medicina Intensiva"

# 3. Enlace sin título: se recupera de la dirección
assert not titulo_util("Ver y leer más sobre el congreso...")
assert titulo_desde_url("https://www.aaear.es/70-reunion-anual-aaear-2026") == \
    "70 reunion anual aaear 2026"

# 4. Páginas que no son un curso
assert not titulo_util("COMUNICACIONES ONLINE")

# 5. Congreso de 2022 con fecha sin año: NO debe fecharse en el futuro
_i, _f, _ = _ef("XVIII Congreso SED 2022 Valencia. 26 al 29 de octubre", hoy=date(2026, 9, 21))
assert _i.year == 2022, f"debería quedarse en 2022, no en {_i.year}"

# 6. La memoria se limpia sola con las reglas nuevas
_m = {"a": {"titulo": "COMUNICACIONES ONLINE", "inicio": "2027-05-04"},
      "d": {"titulo": "PLAZAS AGOTADAS | Curso X Nombre del curso: X", "inicio": "2026-12-01"},
      "b": {"titulo": "XVIII Congreso SED 2022 Valencia", "inicio": "2026-10-26"},
      "c": {"titulo": "Curso de Anestesia Regional Ecoguiada", "inicio": "2026-11-20"}}
_limpia = sanea_memoria(_m)
# "a" no es un curso y "b" es de 2022: fuera. "d" ya no se tira, se CURA:
# antes se borraba el registro y, si la fuente era trimestral, el curso
# desaparecía durante meses. Ahora se le arregla el título y se queda.
assert set(_limpia) == {"c", "d"}, set(_limpia)
assert _limpia["d"]["titulo"] == "Curso X — plazas agotadas", _limpia["d"]["titulo"]
assert _limpia["c"]["titulo"] == "Curso de Anestesia Regional Ecoguiada"
# El defecto real del 05/10: un título guardado el 18/09 con la etiqueta suelta
_viejo = {"z": {"titulo": "Congreso Panamericano e Ibérico de Medicina Intensiva Fecha",
                "inicio": "2026-10-04"}}
assert sanea_memoria(_viejo)["z"]["titulo"] == \
    "Congreso Panamericano e Ibérico de Medicina Intensiva"

# Y lo bueno sigue pasando
for _t in ["Curso de Soporte Vital Avanzado (SVA)",
           "Cartagena: Acto Conmemorativo del Día Mundial de los Cuidados Paliativos",
           "Webinar – Del diagnóstico al tratamiento: hacia una analgesia individualizada en UCI"]:
    assert titulo_util(_t), _t
print("Defectos reales del 21/09 corregidos ✓")


# ---------------------------------------------------------------------------
# Entrar en la ficha del curso (diagnóstico del 23/09: era la mayor pérdida)
# ---------------------------------------------------------------------------
import http.server, socketserver, threading, tempfile, os, shutil, csv, glob, pathlib
from agenda import desde_html, SEGUIR_POR_FUENTE

_dir = tempfile.mkdtemp()
open(os.path.join(_dir, "index.html"), "w", encoding="utf-8").write("""
<html><body><ul>
<li><a href="/d1.html">DIPLOMA DE ESPECIALIZACIÓN EN EL MANEJO DE LA SEPSIS Y SHOCK SÉPTICO</a></li>
<li><a href="/d4.html">2021 - Curso de Simulación clínica en soporte vital</a></li>
<li><a href="/d5.html">Presentación del libro "Cuentos y relatos de paz"</a></li>
<li><a href="/d6.html">Formación tutores y residentes</a></li>
</ul></body></html>""")
# La ficha lleva primero la fecha de publicación: NO debe confundirse con ella
open(os.path.join(_dir, "d1.html"), "w", encoding="utf-8").write(
    '<html><body><p>Publicado el 2 de septiembre de 2026.</p>'
    '<p>El curso se celebrará del 10 al 12 de diciembre de 2026 en Sevilla.</p></body></html>')
for _n in ("d4", "d5", "d6"):
    open(os.path.join(_dir, f"{_n}.html"), "w", encoding="utf-8").write(
        "<html><body><p>Se celebró el 14 de mayo de 2021.</p></body></html>")

_cwd = os.getcwd()
os.chdir(_dir)
_srv = socketserver.TCPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
_puerto = _srv.server_address[1]
threading.Thread(target=_srv.serve_forever, daemon=True).start()
try:
    _base = f"http://127.0.0.1:{_puerto}/index.html"
    _html = open("index.html", encoding="utf-8").read()
    _ev = desde_html(_base, _html, {"nombre": "Prueba", "filtro": "evento", "ambito": "mixto"})
finally:
    _srv.shutdown(); os.chdir(_cwd); shutil.rmtree(_dir, ignore_errors=True)

assert len(_ev) == 1, f"debería recuperar solo el diploma, recuperó {len(_ev)}"
_e = _ev[0]
assert _e.via == "ficha"
assert _e.inicio == "2026-12-10", f"debe coger la fecha de celebración, no la de publicación: {_e.inicio}"
assert _e.lugar == "Sevilla", f"debe sacar la ciudad de la ficha: {_e.lugar}"
# El título venía gritado en la web y ahora se normaliza
assert _e.titulo == "Diploma de Especialización en el Manejo de la Sepsis y Shock Séptico", _e.titulo
print("Entrada en fichas: recupera el curso, ignora publicación, año pasado y no-cursos ✓")

# ---------------------------------------------------------------------------
# Mejoras del 23/09: meses abreviados, lugar y mayúsculas
# ---------------------------------------------------------------------------
from agenda import extrae_lugar, arregla_mayusculas

for _txt in ["Curso el 15 oct 2026", "Jornada 3 nov. 2026", "Del 12 al 14 dic 2026",
             "Taller 20 ene 2027", "Sesión 8 feb. 2027", "Congreso 5 de sept. de 2026"]:
    assert _ef(_txt, hoy=date(2026, 9, 23))[0], f"mes abreviado no reconocido: {_txt}"
# Un día y un mes sueltos, sin "de" ni año, NO son una fecha
for _txt in ["Sala 3 marzo cerrada por obras", "Aula 2 junio disponible",
             "Reunión de 15 mayores de edad"]:
    assert not _ef(_txt, hoy=date(2026, 9, 23))[0], f"falso positivo: {_txt}"
print("Meses abreviados ✓")

assert extrae_lugar("Jornada en Valdepeñas (Ciudad Real)") == "Valdepeñas"
assert extrae_lugar("Webinar 100% online desde Madrid") == "Online"
assert extrae_lugar("Sede: Hotel Rafael, Atocha, Madrid") == "Madrid"
assert extrae_lugar("Congreso en Las Palmas de Gran Canaria") == "Las Palmas de Gran Canaria"
assert extrae_lugar("Curso de dolor crónico, plazas limitadas") == ""
print("Detección de lugar ✓")

assert arregla_mayusculas("CURSO DE SOPORTE VITAL AVANZADO (SVA) Y DEA") == \
    "Curso de Soporte Vital Avanzado (SVA) y DEA"
assert arregla_mayusculas("VI CONGRESO SEMDOR 2026") == "VI Congreso SEMDOR 2026"
assert arregla_mayusculas("Curso de Ventilación Mecánica") == "Curso de Ventilación Mecánica"
print("Títulos gritados ✓")

# ---------------------------------------------------------------------------
# robots.txt: el 403 del cortafuegos no es una prohibición (RFC 9309)
#
# Esta prueba existe por un fallo real: 27 de las 211 webs figuraban como
# "bloqueadas por robots.txt" y, al mirar sus archivos uno a uno, ninguna
# prohibía nada. Lo que pasaba es que el servidor respondía 403 a la petición
# del robots.txt, y la librería estándar de Python interpreta ese 403 como
# "prohibido todo el sitio".
# ---------------------------------------------------------------------------
import agenda as _ag


def _servidor_robots(codigo, cuerpo=""):
    """Levanta un servidor que responde lo que se le diga en /robots.txt."""
    class _H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/robots.txt":
                self.send_response(codigo)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(cuerpo.encode("utf-8"))
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body>ok</body></html>")

        def log_message(self, *a):
            pass

    s = socketserver.TCPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}/cursos"


_casos = [
    # (código, contenido del robots.txt, ¿debe permitir?, descripción)
    (403, "", True, "403 del cortafuegos: no es una regla, se permite"),
    (404, "", True, "no hay robots.txt: se permite"),
    (200, "User-agent: *\nDisallow: /", False, "prohibición real: se respeta"),
    (200, "User-agent: *\nDisallow: /wp-admin/", True, "solo rutas concretas: se permite"),
    (200, "User-agent: *\nDisallow:", True, "Disallow vacío: se permite"),
    (200, "User-agent: CCBot\nDisallow: /", True, "prohibido a otro robot, no a nosotros"),
    (500, "", False, "servidor caído: por prudencia, no se rastrea"),
]

for _cod, _cuerpo, _esperado, _desc in _casos:
    _s, _u = _servidor_robots(_cod, _cuerpo)
    try:
        _ag._robots_cache.clear()
        _r = _ag.robots_permite(_u)
    finally:
        _s.shutdown()
    assert _r is _esperado, f"robots.txt — {_desc}: esperaba {_esperado}, dio {_r}"

_ag._robots_cache.clear()
print("Lectura de robots.txt ✓")

# ---------------------------------------------------------------------------
# Defectos reales de la tabla del 05/10 — la primera que se miró con intención
# de publicarla. Todos los casos de abajo salieron de ahí tal cual.
# ---------------------------------------------------------------------------
from agenda import (pule_titulo, es_pagina_de_seccion, unifica, recura_titulo,
                    recorta, limpia_titulo, separa_sin_plazas, titulo_util,
                    arregla_mayusculas, Evento)


def _pulido(t):
    limpio, lleno = separa_sin_plazas(pule_titulo(limpia_titulo(t, "")))
    return recorta(arregla_mayusculas(limpio)) + (" — plazas agotadas" if lleno else "")


# 1. Texto de interfaz metido dentro del enlace
assert _pulido("Plazas limitadas Máster en Ecografía Musculoesquelética e "
               "Intervencionismo Ecoguiado Matrícula : Abierta para el curso 2026/2027") == \
    "Máster en Ecografía Musculoesquelética e Intervencionismo Ecoguiado"
assert _pulido("Enfermería Formación de Postgrado en Atención Enfermera en Cuidados "
               "Paliativos Semipresencial 30 Créditos ECTS Añadir a favoritos") == \
    "Formación de Postgrado en Atención Enfermera en Cuidados Paliativos Semipresencial"

# 2. Mayúsculas sueltas, y siglas escritas en minúscula
assert _pulido("FUNDAMENTOS EN cuidados Críticos") == "Fundamentos en cuidados Críticos"
assert _pulido("analgesia y sedación en el paciente pediátrico en URGENCIAS") == \
    "Analgesia y sedación en el paciente pediátrico en Urgencias"
assert _pulido("70 reunion anual aaear 2026") == "70 Reunion anual AAEAR 2026"

# 3. Páginas de sección: el índice de congresos no es un congreso
assert es_pagina_de_seccion("Congressos i Jornades SCARTD")
assert es_pagina_de_seccion("Próximos eventos")
assert not titulo_util("Congressos i Jornades SCARTD")
# ...pero una jornada de verdad de la misma sociedad sí entra
assert not es_pagina_de_seccion(
    "VI Jornada de la Societat Catalana d'Anestesiologia, Reanimació i Terapèutica del Dolor")
assert not es_pagina_de_seccion("Congreso Nacional de Cuidados Paliativos 2026")

# 4. No recortar la cabeza si lo que queda ya no es un título
assert _pulido("Enfermería en cuidados críticos y urgencias") == \
    "Enfermería en cuidados críticos y urgencias"
print("Títulos de la tabla real del 05/10 ✓")


# ---------------------------------------------------------------------------
# Unificar lo que es el mismo curso contado dos veces
# ---------------------------------------------------------------------------
def _ev(titulo, inicio, entidad, url, lugar="", fin=None):
    return Evento(titulo=titulo, fecha_texto="", inicio=inicio, fin=fin,
                  lugar=lugar, entidad=entidad, url=url, ambito="mixto")


# a) Misma dirección = mismo curso; gana el título corto
_u = unifica([
    _ev("Congreso Panamericano e Ibérico de Medicina Intensiva Fecha", "2026-10-04",
        "DimeCongresos", "https://dimecongresos.com/congresos/panamericano/"),
    _ev("Congreso Panamericano e Ibérico de Medicina Intensiva", "2026-10-04",
        "DimeCongresos", "https://dimecongresos.com/congresos/panamericano/", lugar="Madrid"),
])
assert len(_u) == 1, _u
assert _u[0].titulo == "Congreso Panamericano e Ibérico de Medicina Intensiva"
assert _u[0].lugar == "Madrid", "al unir no se pierde la ciudad que traía el otro"

# b) El titular de la noticia y el congreso son el mismo acto
_u = unifica([
    _ev("XV Congreso Internacional SECPAL", "2026-10-08",
        "Dolor.com — Congresos y jornadas", "https://www.dolor.com/xv-secpal"),
    _ev("El XV Congreso Internacional de SECPAL combinará ciencia, innovación, "
        "humanismo y autocuidado", "2026-10-08", "SECPAL",
        "https://www.secpal.org/noticia-xv-congreso", lugar="Cartagena", fin="2026-10-10"),
])
assert len(_u) == 1, [e.titulo for e in _u]
assert _u[0].titulo == "XV Congreso Internacional SECPAL"
assert _u[0].lugar == "Cartagena"
assert _u[0].fin == "2026-10-10"
assert _u[0].entidad == "SECPAL", f"el título nombra a SECPAL: {_u[0].entidad}"

# c) Dos cursos distintos el mismo día NO se juntan
_u = unifica([
    _ev("Curso de Ventilación Mecánica no Invasiva", "2026-11-10", "SEMICYUC",
        "https://semicyuc.org/a"),
    _ev("Curso de Ecografía en el Paciente Crítico", "2026-11-10", "SEMICYUC",
        "https://semicyuc.org/b"),
])
assert len(_u) == 2, [e.titulo for e in _u]
print("Unificación de repetidos ✓")


# ---------------------------------------------------------------------------
# Rellenar la ciudad abriendo la ficha
# En la tabla del 05/10, nueve de quince cursos salían sin lugar porque la
# ciudad solo aparece dentro de la página del curso, no en el listado.
# ---------------------------------------------------------------------------
from agenda import completa_lugares

_d2 = tempfile.mkdtemp()
open(os.path.join(_d2, "ficha.html"), "w", encoding="utf-8").write(
    '<html><body><h1>VIII Curso Avanzado de Ecografía en el Paciente Crítico</h1>'
    '<p>Lugar de celebración: Hospital Universitario, Burgos.</p></body></html>')
open(os.path.join(_d2, "muda.html"), "w", encoding="utf-8").write(
    '<html><body><p>Inscripción abierta. Plazas limitadas.</p></body></html>')

_cwd2 = os.getcwd()
os.chdir(_d2)
_srv2 = socketserver.TCPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
_p2 = _srv2.server_address[1]
threading.Thread(target=_srv2.serve_forever, daemon=True).start()
try:
    _con = _ev("VIII Curso Avanzado de Ecografía en el Paciente Crítico", "2026-10-27",
               "Colegio de Médicos de Burgos", f"http://127.0.0.1:{_p2}/ficha.html")
    _sin = _ev("Soporte Vital Intermedio Pediátrico", "2026-11-02",
               "Colegio de Médicos de Murcia", f"http://127.0.0.1:{_p2}/muda.html")
    _ya = _ev("Visión actual del dolor pélvico crónico", "2026-10-29",
              "Formación SED", f"http://127.0.0.1:{_p2}/ficha.html", lugar="Online")
    _n = completa_lugares([_con, _sin, _ya])
finally:
    _srv2.shutdown(); os.chdir(_cwd2); shutil.rmtree(_d2, ignore_errors=True)

assert _con.lugar == "Burgos", f"debe sacar la ciudad de la ficha: {_con.lugar!r}"
assert _sin.lugar == "", "si la ficha no dice la ciudad, se deja el hueco vacío"
assert _ya.lugar == "Online", "no se toca el que ya tenía lugar"
assert _n == 1, _n
print("Relleno de lugares desde la ficha ✓")


# ---------------------------------------------------------------------------
# Sedes equivocadas de la agenda del 02/11 (aviso de Luis)
#
# - Jornada Balear de Anestesiología: salió "Madrid". La ficha dice "27 de
#   noviembre de 2026 · Hospital Universitari Son Llàtzer" (Palma) sin nombrar
#   la ciudad, y la única ciudad de la página era la de un ponente: "Hospital
#   Universitario Puerta de Hierro, Majadahonda (Madrid)".
# - Soporte vital intermedio pediátrico (Colegio de Murcia): salió "Online"
#   por su "Fase online". Es semipresencial, con las clases en la Arrixaca.
# - El curso de ecocardiografía del Colegio de Córdoba sí es en Madrid: "Lugar:
#   Madrid · Centro Tecnológico de Simulación eSalùdate". El Colegio lo anuncia.
# ---------------------------------------------------------------------------
_balear = ("Jornada Balear de Anestesiología\n27 de noviembre de 2026 · Hospital Universitari "
           "Son Llàtzer\nPonentes\nDr. Pedro X\nUnidad del Dolor del Hospital Quirónsalud "
           "Tenerife. Director de MIVI Canarias.\nDr. Juan Y\nJefe del Servicio de "
           "Anestesiología, UCI Quirúrgica y Dolor del Hospital Universitario Puerta de Hierro, "
           "Majadahonda (Madrid).\nInscripción\nNombre y Apellidos *")
assert extrae_lugar(_balear, "2026-11-27", "27 de noviembre de 2026", final=True) == "Palma"
# Sin hospital conocido, la ciudad del ponente tampoco vale: mejor vacío
assert extrae_lugar(_balear.replace("Hospital Universitari Son Llàtzer", "Sala Magna"),
                    "2026-11-27", final=True) == ""
assert extrae_lugar("Fecha: 22 de noviembre de 2026\nLugar: Madrid · Centro Tecnológico de "
                    "Simulación eSalùdate\nInscripción online", "2026-11-22", final=True) == "Madrid"
_murcia = ("SOPORTE VITAL INTERMEDIO PEDIÁTRICO\nModalidad: semipresencial\nInicio Fase No "
           "Presencial: lunes 02 de noviembre, entrega del material vía email.\nFase online : "
           "Examen tipo test al iniciar la fase presencial\nLugar: Hospital Universitario "
           "Virgen de la Arrixaca")
assert extrae_lugar(_murcia, "2026-11-02", final=True) == "Murcia"
# En el listado, un semipresencial sin ciudad se deja vacío: así se abre la ficha
assert extrae_lugar("Soporte vital intermedio pediátrico. Semipresencial. Fase online") == ""
# "Online" solo si lo es el curso
assert extrae_lugar("Inscripción online abierta. Sede: Hotel Meliá, Valencia") == "Valencia"
assert extrae_lugar("Un webinar de la revista Medicina Intensiva") == "Online"
assert extrae_lugar("Presencial y en streaming. Lugar: Palacio de Congresos de Granada") == "Granada"
assert extrae_lugar("Instructor en SVB y DEA | Presencial y online") == ""
assert extrae_lugar("Instructor en SVB y DEA | Presencial y online", final=True) == "Online"
assert extrae_lugar("Actualización en línea con las guías. Hospital Clínico Universitario de "
                    "Valladolid") == "Valladolid"
assert extrae_lugar("Taller de realidad virtual. Salamanca, 3 de diciembre") == "Salamanca"
assert extrae_lugar("Organiza el Servicio. Dra. Ana López (Hospital Clínic de Barcelona). "
                    "Lugar: Hotel NH, Zaragoza") == "Zaragoza"
assert extrae_lugar("VI Jornada SCARTD. Dr. Martí, Hospital de Bellvitge. 5 de novembre 2026, "
                    "Barcelona", "2026-11-05", final=True) == "Barcelona"

# La ficha leída con sus líneas: el ponente va en su párrafo, la sede en el suyo
_d3 = tempfile.mkdtemp()
open(os.path.join(_d3, "jornada.html"), "w", encoding="utf-8").write(
    '<html><body><h1>Jornada Balear de Anestesiología</h1>'
    '<p>27 de noviembre de 2026 · Hospital Universitari Son Llàtzer</p>'
    '<h2>Ponentes</h2><div><b>Dr. Juan Y</b><br>Jefe del Servicio de Anestesiología del '
    '<a href="#">Hospital Universitario Puerta de Hierro</a>, Majadahonda (Madrid).</div>'
    '<form>Nombre y Apellidos *</form></body></html>')
_cwd3 = os.getcwd()
os.chdir(_d3)
_srv3 = socketserver.TCPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
_p3 = _srv3.server_address[1]
threading.Thread(target=_srv3.serve_forever, daemon=True).start()
try:
    _jb = _ev("Jornada Balear de Anestesiología", "2026-11-27", "SBARTD (Baleares)",
              f"http://127.0.0.1:{_p3}/jornada.html")
    completa_lugares([_jb])
finally:
    _srv3.shutdown(); os.chdir(_cwd3); shutil.rmtree(_d3, ignore_errors=True)
assert _jb.lugar == "Palma", _jb.lugar

# El texto del botón no es parte del título
from agenda import recura_titulo as _rt
assert _rt("Inscripción Jornada Balear de Anestesiología") == "Jornada Balear de Anestesiología"
assert _rt("Inscripción en el registro de anestesia pediátrica") == \
    "Inscripción en el registro de anestesia pediátrica"
print("Sedes de la agenda del 02/11: ponentes, online y semipresenciales ✓")


# ---------------------------------------------------------------------------
# Titulares de noticias — defectos reales del rastreo del 12/10
#
# Tres de los dieciséis cursos de ese lunes eran noticias de la web de un
# colegio, no cursos. La señal que las separa es gramatical: el título de una
# actividad es un sustantivo, un titular es una oración con verbo conjugado.
# ---------------------------------------------------------------------------
from agenda import parece_noticia

for _t in ["Menos de la mitad de las facultades de Medicina imparten formación "
           "en cuidados paliativos",
           "El COM Cantabria y el Ayuntamiento de Santander celebran la Semana del Corazón",
           "Icoma y el Ayuntamiento organizan la X edición de “BihotzAraba”",
           "El XV Congreso Internacional de SECPAL combinará ciencia e innovación"]:
    assert parece_noticia(_t), f"titular no detectado: {_t}"
    assert not titulo_util(_t), f"debería descartarse: {_t}"

# Y lo que NO debe confundirse con una noticia. Ojo a los dos últimos: no
# llevan la palabra "curso" ni "jornada", así que exigir un sustantivo de
# actividad los habría tirado. Por eso la regla busca el verbo, no el nombre.
for _t in ["Curso del Colegio: Manejo Vía Aérea",
           "VIII Curso Avanzado de Ecografía en el Paciente Crítico",
           "XV Congreso de la Sociedad Murciana de Medicina Intensiva",
           "VI Jornada de la Societat Catalana d'Anestesiologia",
           "70 Reunion anual AAEAR 2026",
           "Soporte Vital Intermedio Pediátrico",
           "Visión actual del dolor pélvico crónico"]:
    assert not parece_noticia(_t), f"falso titular: {_t}"
    assert titulo_util(_t), f"debería quedarse: {_t}"

# La etiqueta con signos de apertura, que antes no se quitaba
assert _pulido("¡Últimas plazas! El nueva sesión del Curso de Soporte Vital Básico") == \
    "El nueva sesión del Curso de Soporte Vital Básico"
# ...pero sin llevarse parte del título cuando lo que queda es una preposición
assert _pulido("Enfermería en cuidados críticos y urgencias") == \
    "Enfermería en cuidados críticos y urgencias"
print("Titulares de noticias del 12/10 ✓")


# ---------------------------------------------------------------------------
# Canales en dominios compartidos — 14/10, al añadir los hospitales
#
# Quince hospitales viven dentro de comunidad.madrid y trece dentro del portal
# del SAS. El canal de la portada de esos sitios es el de la Consejería entera,
# no el de cada hospital: si se les asignara, los quince leerían las noticias
# del gobierno regional en vez de su propia agenda.
# ---------------------------------------------------------------------------
import agenda as _ag2

_guardado = set(_ag2.DOMINIOS_COMPARTIDOS)
_ag2.DOMINIOS_COMPARTIDOS = {"www.comunidad.madrid", "www.secpal.org"}
try:
    _paz = "https://www.comunidad.madrid/hospital/lapaz/ciudadanos/actividades"
    # El canal del hospital, sí
    assert _ag2.feed_es_propio(_paz,
        "https://www.comunidad.madrid/hospital/lapaz/rss/latest-events.xml")
    # El de la Consejería entera, no
    assert not _ag2.feed_es_propio(_paz, "https://www.comunidad.madrid/rss.xml")
    # Y el de OTRO hospital del mismo sitio, tampoco
    assert not _ag2.feed_es_propio(_paz,
        "https://www.comunidad.madrid/hospital/12octubre/rss/latest-events.xml")
    # AECPAL vive dentro de la web de SECPAL: no debe leer el canal de SECPAL
    assert not _ag2.feed_es_propio("https://www.secpal.org/aecpal/",
                                   "https://www.secpal.org/feed/")
    # ...pero SECPAL, que está en la raíz de su propia web, sí
    assert _ag2.feed_es_propio("https://www.secpal.org/", "https://www.secpal.org/feed/")
    # Una sociedad con web propia no cambia nada: su canal de portada es el suyo
    assert _ag2.feed_es_propio("https://sovamicyuc.es/cursos-jornadas/",
                               "https://sovamicyuc.es/feed/")
    # Al sondear a ciegas en dominio compartido, solo bajo la sección
    _c = _ag2._candidatos_feed(_paz)
    assert all(x.startswith(_paz) for x in _c), _c
    assert "https://www.comunidad.madrid/feed/" not in _c
finally:
    _ag2.DOMINIOS_COMPARTIDOS = _guardado
print("Canales en dominios compartidos ✓")


# ---------------------------------------------------------------------------
# El 404 disfrazado — 18/10
#
# La Comunidad de Madrid contestó "404, no existe" a los quince hospitales,
# cuando las páginas existen y traen jornadas fechadas. Un bloqueo que se hace
# pasar por página inexistente. Aquí se simula un servidor así: 404 al robot,
# 200 al navegador, y 404 de verdad a una página que no existe.
# ---------------------------------------------------------------------------
import agenda as _ag3


class _Disfrazado(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        navegador = "Mozilla" in (self.headers.get("User-Agent") or "")
        if self.path == "/robots.txt":
            codigo, cuerpo = 404, b""
        elif self.path.startswith("/no-existe"):
            codigo, cuerpo = 404, b"no"
        elif navegador:
            codigo, cuerpo = 200, b"<html><body>Jornada de anestesia</body></html>"
        else:
            codigo, cuerpo = 404, b"no"           # al robot, siempre 404
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):
        pass


_s3 = socketserver.TCPServer(("127.0.0.1", 0), _Disfrazado)
threading.Thread(target=_s3.serve_forever, daemon=True).start()
_b3 = f"http://127.0.0.1:{_s3.server_address[1]}"
_dom3 = f"127.0.0.1:{_s3.server_address[1]}"
try:
    _ag3._PIDE_NAVEGADOR.discard(_dom3)
    # Sin el reintento, la página "no existe"
    assert _ag3.descarga(_b3 + "/hospital/lapaz/actividades") is None
    assert _dom3 not in _ag3._PIDE_NAVEGADOR
    # Con el reintento, aparece
    _r = _ag3.descarga(_b3 + "/hospital/lapaz/actividades", reintenta_404=True)
    assert _r is not None and "anestesia" in _r.text, "debe abrirla como navegador"
    # ...y el dominio queda aprendido: la ficha del curso ya entra a la primera
    assert _dom3 in _ag3._PIDE_NAVEGADOR
    assert _ag3.descarga(_b3 + "/hospital/lapaz/actividad/120376") is not None
    # Un 404 de verdad sigue siendo un 404
    assert _ag3.descarga(_b3 + "/no-existe", reintenta_404=True) is None
finally:
    _s3.shutdown()
    _ag3._PIDE_NAVEGADOR.discard(_dom3)

# Y un 404 de verdad NO enseña al programa a disfrazarse en ese dominio
_s4 = socketserver.TCPServer(("127.0.0.1", 0), _Disfrazado)
threading.Thread(target=_s4.serve_forever, daemon=True).start()
_b4 = f"http://127.0.0.1:{_s4.server_address[1]}"
try:
    assert _ag3.descarga(_b4 + "/no-existe", reintenta_404=True) is None
    assert f"127.0.0.1:{_s4.server_address[1]}" not in _ag3._PIDE_NAVEGADOR
finally:
    _s4.shutdown()
print("404 disfrazado ✓")


# ---------------------------------------------------------------------------
# oEmbed no es un canal — encontrado el 18/10 en seis fuentes
# ---------------------------------------------------------------------------
_html_wp = """<html><head>
<link rel="alternate" type="application/json+oembed" href="https://x.es/wp-json/oembed/1.0/embed?url=a">
<link rel="alternate" type="text/xml+oembed" href="https://x.es/wp-json/oembed/1.0/embed?url=a&format=xml">
<link rel="alternate" type="application/rss+xml" href="https://x.es/feed/">
</head><body></body></html>"""
_ag3.DOMINIOS_COMPARTIDOS = set()
assert _ag3.busca_feed("https://x.es/", _html_wp) == "https://x.es/feed/", \
    "debe saltarse el oEmbed y quedarse con el RSS de verdad"
assert _ag3.es_oembed("https://cst.cat/wp-json/oembed/1.0/embed?url=x&format=xml")
assert not _ag3.es_oembed("https://cst.cat/feed/")
print("oEmbed descartado como canal ✓")


# ---------------------------------------------------------------------------
# Tabla del 19/10: noticias, boletines y cursos para otro público
#
# El primer rastreo con los hospitales dio 25 cursos. Cinco no eran para un
# anestesiólogo: dos titulares de noticia, un boletín, dos cursos de RCP para la
# población general y un máster de fisioterapia. Probado además contra los 95
# títulos que han salido alguna vez: estas reglas no quitan ningún curso real.
# ---------------------------------------------------------------------------
for _t in ["Ocupadas todas las plazas de los cursos gratuitos en RCP para la "
           "ciudadanía de la Quincena del corazón",
           "Talavera aprende a salvar vidas el próximo",
           "Toledo se forma en reanimación cardiopulmonar y primeros auxilios el próximo",
           "Número 18 de ‘Actualidad SECPAL’",
           "Máster Universitario en Terapia Manual Ortopédica en el Tratamiento del Dolor"]:
    assert not titulo_util(_t), f"debería descartarse: {_t}"

# Y lo que se queda, de esa misma tabla
for _t in ["Publicar y no morir en el intento. Un webinar de la revista Medicina Intensiva",
           "Abordaje interdisciplinar del dolor crónico pediátrico",
           "Curso de Soporte Vital Inmediato",
           "Seminario On-Line Actualización en el manejo de la agitación",
           "Tratamiento del dolor agudo adaptado a cada paciente, 2ª edición",
           "Instructor en Soporte Vital Básico y DEA",
           "Cartagena: Acto Conmemorativo del Día Mundial de los Cuidados Paliativos"]:
    assert titulo_util(_t), f"debería quedarse: {_t}"
print("Tabla del 19/10: noticias, boletines y otro público ✓")


# ---------------------------------------------------------------------------
# Tabla del 26/10 — el primer rastreo con todo, Madrid incluida
#
# 29 cursos. Cinco eran errores y tres, de paliativos sin dolor ni sedación;
# para estos últimos Luis eligió el filtro "dolor" en las fuentes de paliativos.
# Todo probado contra los 110 títulos del histórico.
# ---------------------------------------------------------------------------
from agenda import (es_de_dolor, titulo_de_otro_anio, limpia_nombre_de_fichero)

# 1. Lo que no es un curso
for _t in ["Últimos artículos", "E-Bellvitge 755", "Inscripciones",
           "XIX Curso de Ecocardiografía fetal", "Avances en neuropediatría",
           "Las IV Jornadas Sempal para Residentes finalizan el en Toledo"]:
    assert not titulo_util(recura_titulo(_t)), f"debería descartarse: {_t}"

# ...pero la anestesia de la cirugía fetal sí es de la casa
assert titulo_util("Curso de anestesia en cirugía fetal y procedimiento EXIT")

# 2. Nombres de fichero: se limpian, no se tiran. Los dos primeros son cursos
#    reales que la regla de "descartar ficheros" se habría llevado.
assert limpia_nombre_de_fichero("Programa VII Curso Eco Pulmonar Seneo 2026v0.pdf") == \
    "VII Curso Eco Pulmonar Seneo 2026"
assert limpia_nombre_de_fichero("Programa Curso de Revision 2026.pdf") == "Curso de Revision 2026"
assert limpia_nombre_de_fichero("Curso de Ventilación Mecánica") == "Curso de Ventilación Mecánica"

# 3. Un título de 2022 con fecha de 2026 no entra, tampoco recién encontrado
_e = _ev("18 Actualidad SECPAL Octubre Diciembre 2022", "2026-10-28", "SECPAL", "u")
assert titulo_de_otro_anio(_e)
assert not titulo_de_otro_anio(_ev("VI Congreso SEMDOR 2026", "2026-11-12", "SEMDOR", "u"))

# 4. Filtro "dolor" para las fuentes de paliativos
for _t in ["Curso avanzado en tratamiento opioide", "XV Congreso Internacional SECPAL",
           "Sedación paliativa en el domicilio", "Manejo del dolor irruptivo oncológico"]:
    assert es_de_dolor(_t), f"debería entrar con filtro dolor: {_t}"
for _t in ["Espiritualidad y alzhéimer: cuando el sentido va más allá del significado",
           "La dimensión espiritual en cuidados paliativos: una mirada desde la Psicología",
           "Webinar de Cuidados Paliativos Perinatales: Las 10 mejores comunicaciones"]:
    assert not es_de_dolor(_t), f"no debería entrar con filtro dolor: {_t}"

# 5. Etiquetas pegadas
assert recura_titulo("La dimensión espiritual en cuidados paliativos Webinars") == \
    "La dimensión espiritual en cuidados paliativos"
assert recura_titulo("Cambio de fecha | Las IV Jornadas Sempal para Residentes arrancan") == \
    "Las IV Jornadas Sempal para Residentes arrancan"
assert recura_titulo("Inscripción abierta: Curso de ecografía en el paciente crítico") == \
    "Curso de ecografía en el paciente crítico"
print("Tabla del 26/10 y filtro de paliativos ✓")


# ---------------------------------------------------------------------------
# El post de Instagram: imagen.py (26/10)
#
# Aquí se prueba lo que decide qué sale en cada imagen. La composición en sí
# necesita un navegador y se revisa mirando las imágenes.
# ---------------------------------------------------------------------------
import imagen as _im

# Fechas: la que cruza de mes no cabe en una sola línea grande
assert _im.fecha_corta({"inicio": "2026-10-27", "fin": "2026-10-27"}) == ("27", "OCT", "")
assert _im.fecha_corta({"inicio": "2026-11-12", "fin": "2026-11-14"}) == ("12-14", "NOV", "")
assert _im.fecha_corta({"inicio": "2026-10-26", "fin": "2026-12-01"}) == ("26", "OCT", "hasta 1 DIC")

assert _im.periodo([{"inicio": "2026-10-27"}, {"inicio": "2026-11-22"}]) == "Octubre – Noviembre 2026"
assert _im.periodo([{"inicio": "2026-12-10"}, {"inicio": "2027-01-15"}]) == "Diciembre 2026 – Enero 2027"

# La entidad que organiza, no la web donde se encontró
assert _im.organizador({"entidad": "Dolor.com — Congresos y jornadas",
                        "titulo": "II Jornada Enfermería de SEMDOR"}) == "SEMDOR"
assert _im.organizador({"entidad": "H. U. i Politècnic La Fe — agenda",
                        "titulo": "Curso de Soporte Vital Inmediato"}) == "H. U. i Politècnic La Fe"
assert _im.organizador({"entidad": "Colegio de Médicos de Burgos",
                        "titulo": "VIII Curso Avanzado de Ecografía"}) == "Colegio de Médicos de Burgos"
# Si el agregador no nombra a ninguna sociedad, se queda el agregador
assert _im.organizador({"entidad": "DimeCongresos",
                        "titulo": "Congreso Panamericano e Ibérico de Medicina Intensiva"}) == "DimeCongresos"

assert _im.separa_agotado("Curso de SVB y DEA — plazas agotadas") == ("Curso de SVB y DEA", True)

# Reparto: con 21 cursos y sitio para 4 por imagen, a partes iguales
_cabe4 = lambda g: len(g) <= 4
_rep = _im.reparte([{"i": i} for i in range(21)], _cabe4)
assert [len(g) for g in _rep] == [4, 4, 4, 3, 3, 3], [len(g) for g in _rep]
_rep = _im.reparte([{"i": i} for i in range(8)], _cabe4)
assert [len(g) for g in _rep] == [4, 4], [len(g) for g in _rep]
assert sum(len(g) for g in _im.reparte([{"i": i} for i in range(13)], _cabe4)) == 13
# Lo que añade el diseño de los resúmenes (27/10)
assert _im.periodo_corto([{"inicio": "2026-10-27"}, {"inicio": "2026-11-22"}]) == "OCT – NOV 2026"
assert _im.periodo_corto([{"inicio": "2026-11-02"}, {"inicio": "2026-11-30"}]) == "NOV 2026"
assert _im.periodo_corto([{"inicio": "2026-12-10"}, {"inicio": "2027-01-15"}]) == "DIC 2026 – ENE 2027"
assert _im.rango([{"inicio": "2026-10-26"}, {"inicio": "2026-11-22"}]) == \
    "del 26 de octubre al 22 de noviembre"
assert _im.rango([{"inicio": "2026-11-12"}]) == "el 12 de noviembre"
assert _im.rango_corto([{"inicio": "2026-11-05"}, {"inicio": "2026-11-12"}]) == "5 – 12 de noviembre"
assert _im.rango_corto([{"inicio": "2026-10-29"}, {"inicio": "2026-11-03"}]) == \
    "29 de octubre – 3 de noviembre"
assert _im.rango_corto([{"inicio": "2026-11-12"}, {"inicio": "2026-11-12"}]) == "12 de noviembre"
# Ciudades: online no cuenta, de más a menos, y "Ávila" se ordena con la A
assert _im.ciudades([{"lugar": "Zaragoza"}, {"lugar": "Ávila"}, {"lugar": "Online"},
                     {"lugar": "Madrid"}, {"lugar": "Madrid"}, {"lugar": ""}]) == \
    [("Madrid", 2), ("Ávila", 1), ("Zaragoza", 1)]
# Un título larguísimo no deja a los demás cursos solos: la medida de
# "cabe" ya no mira si algún título sale cortado
assert "recortado" not in _im._CABE
print("Post de Instagram: fechas, organizador y reparto ✓")

# ---------------------------------------------------------------------------
# Títulos con palabras colgando y descartes.txt (26/10)
# ---------------------------------------------------------------------------
assert recura_titulo("Nueva sesión del Curso de Soporte Vital Básico y DEA dirigido a "
                     "médicos y otros profesionales, el") == \
    "Nueva sesión del Curso de Soporte Vital Básico y DEA dirigido a médicos y otros profesionales"

import agenda as _ag5
_antes = list(_ag5.DESCARTES)
_ag5.DESCARTES = [_ag5.normaliza("hematología en Obstericia")]
try:
    assert not _ag5.titulo_util("Seminario “hematología en Obstericia y Ginecología”")
    assert _ag5.titulo_util("Curso de anestesia en obstetricia")
finally:
    _ag5.DESCARTES = _antes
print("Palabras colgando y descartes.txt ✓")

# Una semana sin cursos: se borra el post viejo y queda constancia, sin error.
# Si el post de la semana anterior se quedara en la carpeta, podría publicarse
# creyendo que es el nuevo.
_dp = pathlib.Path(tempfile.mkdtemp())
try:
    (_dp / "post").mkdir()
    (_dp / "post" / "02-cursos.png").write_bytes(b"viejo")
    (_dp / "vacia.csv").write_text("titulo,fecha_texto,inicio,fin,lugar,entidad,url,ambito,via,id\n",
                                   encoding="utf-8")
    assert _im.genera(_dp / "vacia.csv", _dp / "post") == []
    assert not list((_dp / "post").glob("*.png")), "el post viejo debe desaparecer"
    assert (_dp / "post" / "SIN-CURSOS.txt").exists()
    _sello = (_dp / "post" / "generado.txt").read_text(encoding="utf-8")
    assert f"fecha: {date.today().isoformat()}" in _sello and "cursos: 0" in _sello
finally:
    shutil.rmtree(_dp, ignore_errors=True)
print("Post: semana sin cursos ✓")

# ---------------------------------------------------------------------------
# Tabla de cursos de la Sección RCP de la SEDAR (06/11)
#
# Cinco columnas (FECHA ONLINE · FECHA PRESENCIAL · SEDE · PROGRAMA ·
# INSCRIPCIÓN) y ninguna fila con título. Réplica de la tabla real: clave de
# orden oculta delante de la fecha, años de dos cifras, COMPLETO y POSPUESTO,
# filas sin año y el profesorado metido en la celda de la sede.
# ---------------------------------------------------------------------------
from agenda import desde_tabla, rastrea as _rastrea_fuente

_HTML_RCP = """<html><body><h1>CURSOS</h1>
<table class="table"><thead><tr><th>FECHA ONLINE</th><th>FECHA PRESENCIAL</th><th>SEDE</th><th>PROGRAMA</th><th>INSCRIPCIÓN</th></tr></thead><tbody>
<tr><td><span style="display:none">20261005</span>5 octubre 2026</td><td>6 y 7 Noviembre 26</td><td>H. Universitario de A Coruña</td><td><a href="/images/site/cursos/2026/Diptico_SVA_HUAC_6_y_7_noviembre_2026.pdf">PROGRAMA PDF</a></td><td><a href="https://intranet.pacifico-meetings.com/GescoWeb/?cfg=6765">INSCRIPCIÓN</a></td></tr>
<tr><td><span style="display:none">20261005</span>5 octubre 2026</td><td>5 y 6 Noviembre 26</td><td>Hospital Universitario Dr. Peset de Valencia<br>EVES (Escuela Valenciana de Estudios de Salud)</td><td><a href="/images/site/cursos/2026/Diptico-Curso-SEDAR-SVA-Hosp-Dr-Peset.pdf">PROGRAMA PDF</a></td><td><strong>COMPLETO</strong></td></tr>
<tr><td><span style="display:none">20261123</span>23 noviembre 2026</td><td>11 y 12 Diciembre 26</td><td>Hospital Universitari Son Llàtzer</td><td><a href="/images/site/cursos/2026/sva_son_llatzer.pdf">PROGRAMA PDF</a></td><td><a href="https://intranet.pacifico-meetings.com/GescoWeb/?cfg=7000">INSCRIPCIÓN</a></td></tr>
<tr><td><span style="display:none">20261201</span>1 diciembre 2026</td><td>15 y 16 Enero 27</td><td>Hospital Universitario de Basurto <strong>POSPUESTO</strong></td><td><a href="/images/site/cursos/2027/basurto.pdf">PROGRAMA PDF</a></td><td></td></tr>
<tr><td><span style="display:none">20261210</span>10 diciembre 2026</td><td>22 y 23 de enero</td><td>Hospital General Universitario de Elche</td><td><a href="/images/site/cursos/2027/elche.pdf">PROGRAMA PDF</a></td><td></td></tr>
<tr><td>10 diciembre 2026</td><td>22 y 23 de enero</td><td>Hospital Universitario de Basurto</td><td><a href="/images/site/cursos/2027/basurto2.pdf">PROGRAMA PDF</a></td><td></td></tr>
<tr><td><span style="display:none">20260504</span>4 mayo 2026</td><td>4 y 5 junio 26</td><td>Unidad docente Muktiprofesional de Atención Familiar y Comunitaria Castellón</td><td><a href="/images/site/cursos/2026/castellon.pdf">PROGRAMA PDF</a></td><td></td></tr>
<tr><td><span style="display:none">20231117</span>17 de Noviembre 2023</td><td>15 y 16 de Diciembre</td><td>Hospital Universitario de Cáceres (COMPLETO)</td><td><a href="/images/site/cursos/RCP/Diptico_Caceres15_12_23.pdf">VER PDF</a></td><td></td></tr>
<tr><td><span style="display:none">20210824</span>24 de agosto al 24 de septiembre</td><td>24 y 25 de septiembre</td><td>CURSO DE SOPORTE VITAL AVANZADO EN QUIRÓFANO Y CUIDADOS CRÍTICOS<br>Hospital Universitario Fundación de Alcorcón<br><strong>PROFESORADO</strong><br>Dra. María Aliaño. Directora de Curso. Instructora ERC-SEDAR</td><td><a href="/images/site/cursos/Idehav2.pdf">VER PDF</a></td><td></td></tr>
<tr><td>sin fecha</td><td>por determinar</td><td>Hospital X</td><td></td><td></td></tr>
</tbody></table></body></html>
"""
_F_RCP = {"nombre": "SEDAR · Sección RCP — Cursos SVA", "ambito": "anestesia",
          "url": "https://seccionrcp-sedar.es/index.php/soporte-vital-avanzado-sva/cursos",
          "tabla": {"titulo": "Curso de Soporte Vital Avanzado ERC-SEDAR",
                    "fecha": "FECHA PRESENCIAL", "fecha_previa": "FECHA ONLINE",
                    "sede": "SEDE", "enlace": "PROGRAMA"}}
_rcp = {(e.inicio, e.lugar): e for e in desde_tabla(_F_RCP["url"], _HTML_RCP, _F_RCP)}
_tb = "Curso de Soporte Vital Avanzado ERC-SEDAR · "
# La fecha es la PRESENCIAL ("6 y 7 Noviembre 26"), no el inicio de la parte online
assert _rcp[("2026-11-06", "A Coruña")].titulo == _tb + "H. Universitario de A Coruña"
assert _rcp[("2026-11-06", "A Coruña")].fin == "2026-11-07"
assert _rcp[("2026-11-06", "A Coruña")].url.endswith("Diptico_SVA_HUAC_6_y_7_noviembre_2026.pdf")
# COMPLETO en la columna de inscripción
assert _rcp[("2026-11-05", "Valencia")].titulo.endswith("Dr. Peset de Valencia — plazas agotadas")
assert ("2026-12-11", "Palma") in _rcp                       # Son Llàtzer
# Sin año, con la parte online en diciembre: el curso es en enero del año siguiente
assert ("2027-01-22", "Elche") in _rcp and ("2027-01-22", "Bilbao") in _rcp
# Año de dos cifras: "4 y 5 junio 26" es junio de 2026, no de 2027
assert ("2026-06-04", "Castellón") in _rcp
# Pospuesto: fuera. Sin fecha: fuera.
assert not any("2027-01-15" == k[0] for k in _rcp)
assert len(_rcp) == 8, sorted(_rcp)
# El profesorado de la celda no se cuela en la sede
assert _rcp[("2021-09-24", "Alcorcón")].titulo == _tb + "Hospital Universitario Fundación de Alcorcón"
# Los títulos aguantan la limpieza de la memoria sin cambiar
from agenda import recura_titulo as _rt2, titulo_util as _tu2
assert all(_rt2(e.titulo) == e.titulo and _tu2(e.titulo) for e in _rcp.values())
# Basurto y Elche, mismo día: dos cursos distintos, no se juntan
assert len(unifica(list(_rcp.values()))) == 8

# Y la fuente con bloque "tabla" se lee con desde_tabla, no con el genérico
_d4 = tempfile.mkdtemp()
open(os.path.join(_d4, "cursos.html"), "w", encoding="utf-8").write(_HTML_RCP)
_cwd4 = os.getcwd()
os.chdir(_d4)
_srv4 = socketserver.TCPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
threading.Thread(target=_srv4.serve_forever, daemon=True).start()
try:
    _ev4, _est4 = _rastrea_fuente(dict(_F_RCP, url=f"http://127.0.0.1:{_srv4.server_address[1]}/cursos.html",
                                       feed="none"))
finally:
    _srv4.shutdown(); os.chdir(_cwd4); shutil.rmtree(_d4, ignore_errors=True)
assert _est4 == "tabla (8)", _est4
assert all(e.via == "tabla" for e in _ev4)

# "A Coruña" conserva su artículo; "Unidad docente" no es un ponente
assert arregla_mayusculas("HOSPITAL UNIVERSITARIO DE A CORUÑA") == "Hospital Universitario de A Coruña"
assert arregla_mayusculas("Introducción A La Ecografía").startswith("Introducción a ")
assert extrae_lugar("Unidad docente Multiprofesional de Atención Familiar y Comunitaria Castellón") \
    == "Castellón"
print("Tabla de cursos de la Sección RCP de la SEDAR ✓")

# ---------------------------------------------------------------------------
# Resto de cursos de la Sección RCP (06/11): SVI, BIC y GIC
# ---------------------------------------------------------------------------
from agenda import desde_pagina

# GIC: una página con un solo curso. La fecha es la de las jornadas
# presenciales, no la del inicio online ni la del webinario; y el "Madrid" de
# la dirección del pie no es la sede.
_HTML_GIC = """<html><body><div class="cabecera">SECCIÓN RCP DE LA SEDAR</div>
<h2>CURSO DE INSTRUCTOR GENÉRICO -GENERIC INSTRUCTOR COURSE – (GIC)</h2>
<p>El curso consta de una parte on-line y dos jornadas presenciales. La inscripción permanecerá abierta hasta completar las 24 plazas.</p>
<ul><li><strong>Jornadas presenciales:</strong> 13 y 14 noviembre 2026</li>
<li><strong>Inicio parte on-line:</strong> 13 octubre 2026</li>
<li><strong>Webinario:</strong> 3 noviembre 2026</li></ul>
<p><a href="/images/site/Diiptico%20GIC%20SEDAR%20Noviembre%202026_V2.pdf">PROGRAMA</a> <a href="#">COMPLETO</a></p>
<div class="pie">SEDAR · C/ José Abascal nº 46, Madrid · Secretaría Técnica: Pacífico Meetings, Calle Castelló 128, Madrid</div>
</body></html>
"""
_F_GIC = {"nombre": "SEDAR · Sección RCP — Instructor GIC", "ambito": "anestesia",
          "pagina": {"titulo": "Curso de Instructor Genérico ERC-SEDAR (GIC)",
                     "fecha": "Jornadas presenciales"}}
_gic = desde_pagina("https://seccionrcp-sedar.es/index.php/general-instructor-course-gic",
                    _HTML_GIC, _F_GIC)
assert len(_gic) == 1
assert (_gic[0].inicio, _gic[0].fin) == ("2026-11-13", "2026-11-14"), (_gic[0].inicio, _gic[0].fin)
assert _gic[0].lugar == "", _gic[0].lugar
assert _gic[0].titulo == "Curso de Instructor Genérico ERC-SEDAR (GIC)"   # sin COMPLETO
assert _gic[0].url.endswith("Diiptico%20GIC%20SEDAR%20Noviembre%202026_V2.pdf")
# Con una línea "Sede:" sí hay ciudad
assert desde_pagina("x", _HTML_GIC.replace("<p>El curso", "<p>Sede: Hospital Universitario "
                    "Marqués de Valdecilla</p><p>El curso"), _F_GIC)[0].lugar == "Santander"

# BIC: tabla de tres columnas, con la clave de orden delante de la fecha
_HTML_BIC = """<html><body><h1>CURSOS</h1><table><tr><th>FECHA</th><th>SEDE</th><th>PROGRAMA</th></tr>
<tr><td><span style="display:none">20240527</span>04 de Octubre de 2024</td><td>Hospital Universitario La Fe</td><td><a href="/images/site/cursos/RCP/bic/Di%C3%ACptico_BIC_SEDAR_41024v2.pdf">PROGRAMA PDF</a></td></tr>
<tr><td><span style="display:none">20270115</span>15 de Enero de 2027</td><td>Hospital Universitario La Fe</td><td><a href="/images/site/cursos/RCP/bic/BIC_2027.pdf">PROGRAMA PDF</a></td></tr>
</table></body></html>
"""
_F_BIC = {"nombre": "SEDAR · Sección RCP — Instructor BIC", "ambito": "anestesia",
          "tabla": {"titulo": "Curso de Instructor Básico ERC-SEDAR (BIC)", "fecha": "FECHA",
                    "sede": "SEDE", "enlace": "PROGRAMA"}}
_bic = desde_tabla("https://seccionrcp-sedar.es/index.php/basic-instructor-course-bic",
                   _HTML_BIC, _F_BIC)
assert [(e.inicio, e.lugar) for e in _bic] == [("2024-10-04", "Valencia"), ("2027-01-15", "Valencia")]

# SVI: la misma tabla que SVA, hoy vacía
_HTML_SVI = """<html><body><h1>CURSOS</h1><table><thead><tr><th>FECHA ONLINE</th><th>FECHA PRESENCIAL</th><th>SEDE</th><th>PROGRAMA</th><th>INSCRIPCIÓN</th></tr></thead><tbody><tr><td></td><td></td><td></td><td></td><td></td></tr></tbody></table></body></html>
"""
assert desde_tabla("x", _HTML_SVI, dict(_F_RCP, nombre="SEDAR · Sección RCP — Cursos SVI")) == []

# Un díptico en PDF no se abre para buscar la ciudad
_pdf = _ev("Curso de Instructor Genérico ERC-SEDAR (GIC)", "2026-11-13",
           "SEDAR · Sección RCP — Instructor GIC", "http://127.0.0.1:9/diptico.pdf")
assert completa_lugares([_pdf]) == 0 and _pdf.lugar == ""
print("Sección RCP: SVI, BIC y GIC ✓")
