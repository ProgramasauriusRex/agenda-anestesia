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
