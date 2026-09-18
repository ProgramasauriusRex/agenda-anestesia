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
