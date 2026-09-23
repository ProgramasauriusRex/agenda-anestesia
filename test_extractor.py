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
assert set(sanea_memoria(_m)) == {"c"}

# Y lo bueno sigue pasando
for _t in ["Curso de Soporte Vital Avanzado (SVA)",
           "Cartagena: Acto Conmemorativo del Día Mundial de los Cuidados Paliativos",
           "Webinar – Del diagnóstico al tratamiento: hacia una analgesia individualizada en UCI"]:
    assert titulo_util(_t), _t
print("Defectos reales del 21/09 corregidos ✓")


# ---------------------------------------------------------------------------
# Entrar en la ficha del curso (diagnóstico del 23/09: era la mayor pérdida)
# ---------------------------------------------------------------------------
import http.server, socketserver, threading, tempfile, os, shutil, csv, glob
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
