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
