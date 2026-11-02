"""
Convierte la tabla de cursos en las imágenes del post de Instagram.

Una portada y, detrás, las diapositivas del carrusel con cada curso: nombre,
entidad organizadora, lugar y fecha. Formato 4:5, el vertical del feed: se
compone a 1080 × 1350 y se guarda al doble (2160 × 2700), como los resúmenes
del podcast, cuya estética sigue.

Por qué se compone aquí y no se le pide a una IA de imagen: el contenido del
post ES texto, y esas herramientas escriben mal. Un congreso con el nombre
cambiado es peor que no publicarlo. Aquí el texto se pone con tipografía de
verdad, letra a letra como viene de la web del organizador.

El aspecto está entero en estilo.css (en plantilla/ o junto a este archivo).
Para cambiarlo no hay que tocar este archivo.

    python imagen.py                         # con la última consulta
    python imagen.py --csv salida/AGENDA-ACTUAL.csv
    python imagen.py --fondo fondo.jpg       # con un fondo hecho por IA debajo

Necesita Playwright con Chromium (pip install playwright; playwright install
chromium). En GitHub no se usa: solo hace falta donde se generan las imágenes.
"""

from __future__ import annotations

import argparse
import base64
import csv
import glob
import html
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent
SALIDA = BASE / "salida"
PLANTILLA = BASE / "plantilla"


def _busca_plantilla() -> Path:
    """
    Dónde está estilo.css: en plantilla/ o, si no, junto a este archivo.

    Al subir la carpeta plantilla desde la web de GitHub, el 27/10, la carpeta
    no se conservó y los archivos quedaron sueltos en la raíz del repositorio.
    Moverlos desde la web obliga a borrar y volver a subir uno por uno, así que
    el programa los busca en los dos sitios.
    """
    for sitio in (PLANTILLA, BASE):
        if (sitio / "estilo.css").exists():
            return sitio
    sys.exit("No encuentro estilo.css ni en plantilla/ ni junto a imagen.py.")


def _busca_tipografias() -> list[Path]:
    for sitio in (PLANTILLA / "tipografias", PLANTILLA, BASE):
        hallados = sorted(sitio.glob("*-latin-*-normal.woff2"))
        if hallados:
            return hallados
    return []

ANCHO, ALTO = 1080, 1350
ESCALA = 2                     # se guarda a 2160 × 2700, como los resúmenes
MAX_POR_DIAPOSITIVA = 5        # con más, el texto deja de respirar en un móvil
MAX_DIAPOSITIVAS = 20          # el límite de Instagram para un carrusel
N_ACENTOS = 5                  # menta, coral, azul, ámbar y lila (c0…c4 en estilo.css)
MAX_CIUDADES = 9               # en la portada; si hay más, "+N más"

PLATAFORMAS = (("iVoox", "ivoox"), ("Spotify", "spotify"),
               ("Apple Podcasts", "apple"), ("YouTube Music", "youtube"))

MES_CORTO = ["", "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
             "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
MES_LARGO = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Lo que viene tras la raya en el nombre de una fuente es el apartado de la web
# de donde salió ("H. U. La Fe — agenda", "Dolor.com — Congresos y jornadas"),
# no parte del nombre de la entidad. En el post no aporta nada.
_APARTADO = re.compile(r"\s+[—–-]\s+.*$")

ICONO_LUGAR = ('<svg viewBox="0 0 24 24"><path d="M12 2C8.1 2 5 5.1 5 9c0 5.2 7 13 '
               '7 13s7-7.8 7-13c0-3.9-3.1-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 '
               '0 0 1 0 5z"/></svg>')
ICONO_ONLINE = ('<svg viewBox="0 0 24 24"><path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 '
                '1-1 1h-6v2h3v2H7v-2h3v-2H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm1 2v8h14V7z"/>'
                '</svg>')
# La flecha va dibujada: "→" no está en Montserrat y salía con otra letra.
ICONO_FLECHA = ('<svg viewBox="0 0 24 24"><path d="M13.2 5.3 19.9 12l-6.7 6.7-1.4-1.4 4.3-4.3H4v-2h12.1'
                'l-4.3-4.3z"/></svg>')
# Un micrófono, junto al nombre de la cuenta. Va en lugar del logo de
# Instagram de los resúmenes: un logo de otra marca no se dibuja aquí.
ICONO_MARCA = ('<svg viewBox="0 0 24 24"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 '
               '3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 '
               '11z"/></svg>')


# --- Datos -----------------------------------------------------------------

def tabla_por_defecto() -> Path:
    """La última consulta; si no hay, la agenda del lunes."""
    for nombre in ("CONSULTA.csv", "AGENDA-ACTUAL.csv"):
        ruta = SALIDA / nombre
        if ruta.exists():
            return ruta
    sys.exit("No encuentro ninguna tabla en salida/. Lanza antes la consulta.")


def lee_cursos(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8") as f:
        filas = [r for r in csv.DictReader(f) if r.get("inicio")]
    filas.sort(key=lambda r: (r["inicio"], r.get("titulo", "")))
    return filas


# Fuentes que no organizan nada: recogen cursos de otros. Cuando el curso sale
# de una de estas, la entidad organizadora es la que nombra el título ("II
# Jornada Enfermería de SEMDOR", recogida por Dolor.com, la organiza SEMDOR).
AGREGADORES = ("AnestesiaR", "Dolor.com", "DimeCongresos", "Hospitecnia",
               "Revista de Congresos", "Mutual Médica", "Redacción Médica", "ConSalud")
SOCIEDADES = ("SEDAR", "SEMICYUC", "SEMDOR", "SECPAL", "SEEIUC", "SECIP", "ESRA",
              "ESAIC", "SEMES", "SEUP", "SENeo", "PEDPAL", "AECPAL", "SEMPAL", "ASECMA",
              "CERCP", "AAEAR", "SCARTD", "SBARTD", "AGARYD", "SADARTD", "ACMARTD",
              "SOCARTD", "SOCLARTD", "SVNARTD", "SAMIUC", "SARMICYUC", "SOCAMICYUC",
              "SCLMICYUC", "SOMIUCAM", "SOCMIC", "SEXMICYUC", "SOGAMIUC", "SOMIAMA",
              "SOVAMICYUC", "SOMIUC", "SED")


def entidad_corta(entidad: str) -> str:
    return _APARTADO.sub("", entidad or "").strip()


def organizador(fila: dict) -> str:
    """La entidad que organiza, no la web donde se encontró el curso."""
    entidad = entidad_corta(fila.get("entidad", ""))
    if any(entidad.startswith(a) for a in AGREGADORES):
        titulo = fila.get("titulo", "")
        for sigla in SOCIEDADES:
            if re.search(rf"\b{sigla}\b", titulo, re.I):
                return sigla
    return entidad


def separa_agotado(titulo: str) -> tuple[str, bool]:
    limpio = re.sub(r"\s*—\s*plazas agotadas\s*$", "", titulo or "", flags=re.I)
    return limpio.strip(), limpio != (titulo or "")


def fecha_corta(fila: dict) -> tuple[str, str, str]:
    """
    (día, mes, hasta): ('27', 'OCT', ''), ('8-10', 'OCT', ''),
    ('26', 'OCT', 'hasta 1 DIC').

    Una fecha que cruza de mes no cabe en una sola línea grande: en la primera
    prueba "26 OCT – 1 DIC" se salía de su columna y descolocaba la fila.
    """
    d1 = date.fromisoformat(fila["inicio"])
    fin = fila.get("fin") or ""
    if fin and fin != fila["inicio"]:
        d2 = date.fromisoformat(fin)
        if (d2.year, d2.month) == (d1.year, d1.month):
            return f"{d1.day}-{d2.day}", MES_CORTO[d1.month], ""
        return str(d1.day), MES_CORTO[d1.month], f"hasta {d2.day} {MES_CORTO[d2.month]}"
    return str(d1.day), MES_CORTO[d1.month], ""


def periodo(filas: list[dict]) -> str:
    """'Octubre 2026', 'Octubre – Noviembre 2026', 'Diciembre 2026 – Enero 2027'."""
    fechas = [date.fromisoformat(f["inicio"]) for f in filas]
    a, b = min(fechas), max(fechas)
    if (a.year, a.month) == (b.year, b.month):
        return f"{MES_LARGO[a.month]} {a.year}"
    if a.year == b.year:
        return f"{MES_LARGO[a.month]} – {MES_LARGO[b.month]} {a.year}"
    return f"{MES_LARGO[a.month]} {a.year} – {MES_LARGO[b.month]} {b.year}"


def periodo_corto(filas: list[dict]) -> str:
    """Para la etiqueta de arriba: 'NOV 2026', 'OCT – NOV 2026', 'DIC 2026 – ENE 2027'."""
    fechas = [date.fromisoformat(f["inicio"]) for f in filas]
    a, b = min(fechas), max(fechas)
    if (a.year, a.month) == (b.year, b.month):
        return f"{MES_CORTO[a.month]} {a.year}"
    if a.year == b.year:
        return f"{MES_CORTO[a.month]} – {MES_CORTO[b.month]} {a.year}"
    return f"{MES_CORTO[a.month]} {a.year} – {MES_CORTO[b.month]} {b.year}"


def _dia_de_mes(d: date) -> str:
    return f"{d.day} de {MES_LARGO[d.month].lower()}"


def rango(filas: list[dict]) -> str:
    """Para la entradilla: 'del 26 de octubre al 22 de noviembre', 'el 12 de noviembre'."""
    fechas = [date.fromisoformat(f["inicio"]) for f in filas]
    a, b = min(fechas), max(fechas)
    if a == b:
        return f"el {_dia_de_mes(a)}"
    return f"del {_dia_de_mes(a)} al {_dia_de_mes(b)}"


def rango_corto(filas: list[dict]) -> str:
    """Encabezado de cada diapositiva: '12 de noviembre', '26 – 29 de octubre',
    '29 de octubre – 5 de noviembre'."""
    fechas = [date.fromisoformat(f["inicio"]) for f in filas]
    a, b = min(fechas), max(fechas)
    if a == b:
        return _dia_de_mes(a)
    if (a.year, a.month) == (b.year, b.month):
        return f"{a.day} – {b.day} de {MES_LARGO[a.month].lower()}"
    return f"{_dia_de_mes(a)} – {_dia_de_mes(b)}"


def es_online(fila: dict) -> bool:
    return (fila.get("lugar") or "").strip().lower() == "online"


def ciudades(filas: list[dict]) -> list[tuple[str, int]]:
    """Ciudades de los cursos presenciales, de más a menos cursos."""
    cuenta: dict[str, int] = {}
    for f in filas:
        lugar = (f.get("lugar") or "").strip()
        if lugar and not es_online(f):
            cuenta[lugar] = cuenta.get(lugar, 0) + 1
    return sorted(cuenta.items(), key=lambda c: (-c[1], _sin_tildes(c[0])))


def _sin_tildes(texto: str) -> str:
    """Para ordenar: 'Ávila' va con la A, no detrás de 'Zaragoza'."""
    return "".join(ch for ch in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(ch) != "Mn")


# --- Composición -----------------------------------------------------------

def _tipografias() -> str:
    """Las tipografías van dentro del HTML: la imagen sale idéntica en
    cualquier ordenador, tenga o no esas letras instaladas."""
    reglas = []
    for ruta in _busca_tipografias():
        m = re.match(r"(montserrat|inter)-latin-(\d{3})-normal", ruta.stem)
        if not m:
            continue
        familia = m.group(1).capitalize()
        datos = base64.b64encode(ruta.read_bytes()).decode()
        reglas.append(f"@font-face{{font-family:'{familia}';font-weight:{m.group(2)};"
                      f"src:url(data:font/woff2;base64,{datos}) format('woff2');}}")
    return "\n".join(reglas)


def _fondo(ruta: Path | None) -> str:
    if not ruta:
        return ""
    tipo = "jpeg" if ruta.suffix.lower() in (".jpg", ".jpeg") else "png"
    datos = base64.b64encode(ruta.read_bytes()).decode()
    return (f'<div class="fondo-imagen" style="background-image:'
            f'url(data:image/{tipo};base64,{datos})"></div>')


def _pagina(cuerpo: str, fondo: Path | None) -> str:
    estilo = (_busca_plantilla() / "estilo.css").read_text(encoding="utf-8")
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
            f'<style>{_tipografias()}\n{estilo}</style></head>'
            f'<body>{_fondo(fondo)}{cuerpo}</body></html>')


def _cinta(etiqueta: str) -> str:
    return (f'<div class="cinta"><span class="etiqueta">{html.escape(etiqueta)}</span>'
            f'<span class="marca">Hablando de Anestesia</span></div>')


def _apartado(numero: int, nombre: str) -> str:
    return (f'<div class="apartado"><span class="num">{numero}</span>'
            f'<span class="nombre">{html.escape(nombre)}</span><span class="raya"></span></div>')


def _usuario() -> str:
    return (f'<div class="usuario"><span class="icono-marca">{ICONO_MARCA}</span>'
            f'@hablandodeanestesia</div>')


def _caja_marca() -> str:
    chips = "".join(f'<span class="plataforma {clase}">{nombre}</span>'
                    for nombre, clase in PLATAFORMAS)
    return (f'<div class="caja-marca">{_usuario()}'
            f'<div class="escuchanos">ESCÚCHANOS EN</div>'
            f'<div class="plataformas">{chips}</div></div>')


def _tip(texto_html: str) -> str:
    return f'<div class="tip"><span class="insignia-tip">TIP</span><span>{texto_html}</span></div>'


def _cifra(color: int, rotulo: str, valor: str, nota: str, es_fecha: bool = False) -> str:
    clase_valor = "valor fecha" if es_fecha else "valor"
    return (f'<div class="cifra c{color}"><div class="rotulo">{html.escape(rotulo)}</div>'
            f'<div class="{clase_valor}">{html.escape(valor)}</div>'
            f'<div class="nota">{html.escape(nota)}</div></div>')


def html_portada(filas: list[dict], fondo: Path | None = None,
                 max_ciudades: int = MAX_CIUDADES) -> str:
    """La portada. Si las ciudades no caben, genera() la vuelve a pedir con
    menos (`max_ciudades`) y el resto sale como "+N más"."""
    n = len(filas)
    online = sum(1 for f in filas if es_online(f))
    lista_ciudades = ciudades(filas)
    presenciales = sum(c for _, c in lista_ciudades)
    primero = filas[0]
    dia, mes, _ = fecha_corta(primero)

    cifras = "".join((
        _cifra(0, "En total", str(n), "curso o congreso" if n == 1 else "cursos y congresos"),
        _cifra(1, "Presenciales", str(presenciales),
               f"en {len(lista_ciudades)} {'ciudad' if len(lista_ciudades) == 1 else 'ciudades'}"),
        _cifra(2, "Online", str(online), "sin moverte de casa"),
        _cifra(3, "El primero", f"{dia} {mes}", separa_agotado(primero.get("titulo", ""))[0],
               es_fecha=True),
    ))

    if len(lista_ciudades) > max_ciudades:
        vistas, resto = lista_ciudades[:max_ciudades - 1], lista_ciudades[max_ciudades - 1:]
    else:
        vistas, resto = lista_ciudades, []
    chips = "".join(f'<span class="ciudad c{i % N_ACENTOS}">{html.escape(nombre)} <b>{c}</b></span>'
                    for i, (nombre, c) in enumerate(vistas))
    if resto:
        chips += f'<span class="ciudad resto">+{len(resto)} más</span>'
    bloque_ciudades = (f'{_apartado(2, "¿Dónde?")}<div class="ciudades">{chips}</div>'
                       if vistas else "")

    citas = "1 cita" if n == 1 else f"{n} citas"
    cuerpo = f"""
    <section class="diapositiva portada">
      {_cinta(periodo_corto(filas))}
      <h1>Cursos y<br><span class="menta">congresos</span></h1>
      <p class="entradilla"><b>{citas}</b> de Anestesiología, Cuidados Críticos y Dolor
        en España, <b>{html.escape(rango(filas))}</b>. Recogidas cada lunes de las webs de
        sociedades, hospitales y colegios de médicos.</p>
      {_apartado(1, "De un vistazo")}
      <div class="cifras">{cifras}</div>
      {bloque_ciudades}
      <div class="cierre">
        <div class="tips">
          {_tip("<b>Desliza:</b> están todos, ordenados por fecha.")}
          {_tip("<b>Antes de inscribirte,</b> comprueba fechas y plazas en la web del organizador.")}
          {_tip("<b>¿Falta alguno?</b> Dínoslo en comentarios.")}
        </div>
        {_caja_marca()}
      </div>
    </section>"""
    return _pagina(cuerpo, fondo)


def _curso(fila: dict, color: int) -> str:
    titulo, agotado = separa_agotado(fila.get("titulo", ""))
    dia, mes, hasta = fecha_corta(fila)
    lugar = (fila.get("lugar") or "").strip()
    icono = ICONO_ONLINE if es_online(fila) else ICONO_LUGAR
    lugar_html = f'<p class="lugar">{icono}{html.escape(lugar)}</p>' if lugar else ""
    insignia = '<span class="insignia">COMPLETO</span>' if agotado else ""
    clase_dia = "dia largo" if len(dia) > 2 else "dia"
    hasta_html = f'<span class="hasta">{html.escape(hasta)}</span>' if hasta else ""
    return f"""
        <li class="curso c{color}">
          <div class="fecha"><span class="{clase_dia}">{html.escape(dia)}</span>
                             <span class="mes">{mes}</span>{hasta_html}</div>
          <div class="datos">
            <p class="titulo">{html.escape(titulo)}</p>
            <p class="entidad">{html.escape(organizador(fila))}{insignia}</p>
            {lugar_html}
          </div>
        </li>"""


def html_lista(filas: list[dict], pagina: int, total: int, titulo_post: str,
               ultima: bool, fondo: Path | None = None, midiendo: bool = False,
               primer_color: int = 0) -> str:
    """
    Una diapositiva de cursos. `titulo_post` va en la etiqueta de arriba
    ("OCT – NOV 2026") y `primer_color` es el acento de la primera tarjeta,
    para que los colores sigan alternándose de una diapositiva a la siguiente.
    """
    # Con tres o más cursos la lista ocupa toda la altura; con una o dos, las
    # tarjetas no se estiran (quedarían huecas) y van centradas.
    if midiendo:
        clase_lista = "cursos"
    elif len(filas) < 3:
        clase_lista = "cursos pocas"
    else:
        clase_lista = "cursos llena"
    tarjetas = "".join(_curso(f, (primer_color + j) % N_ACENTOS) for j, f in enumerate(filas))
    if ultima:
        derecha = ('<span class="aviso"><span class="insignia-tip">TIP</span>'
                   'Comprueba fechas y plazas en la web del organizador</span>')
    else:
        derecha = f'<span class="desliza">Desliza {ICONO_FLECHA}</span>'
    cuerpo = f"""
    <section class="diapositiva lista">
      {_cinta(titulo_post)}
      {_apartado(pagina, rango_corto(filas))}
      <ul class="{clase_lista}">{tarjetas}</ul>
      <div class="pie">
        {_usuario()}
        {derecha}
      </div>
    </section>"""
    return _pagina(cuerpo, fondo)


# --- Reparto en diapositivas, midiendo de verdad ---------------------------

# Solo se mira si la última tarjeta acaba antes del pie. Hasta el 27/10 también
# se exigía que ningún título saliera cortado, pero un título demasiado largo
# sale cortado vaya con quien vaya: con esa regla se quedaba solo en su
# diapositiva y arrastraba a las demás a ir de dos en dos.
_CABE = """() => {
  const cursos = [...document.querySelectorAll('.curso')];
  const ultimo = cursos[cursos.length - 1].getBoundingClientRect();
  const pie = document.querySelector('.pie').getBoundingClientRect();
  return ultimo.bottom <= pie.top - 40;
}"""


_CABE_PORTADA = """() => {
  const cierre = document.querySelector('.cierre').getBoundingClientRect();
  const encima = [...document.querySelectorAll('.ciudad, .cifra')];
  const fondo = Math.max(...encima.map(e => e.getBoundingClientRect().bottom));
  return fondo <= cierre.top - 28 && cierre.bottom <= document.body.clientHeight;
}"""


def reparte(filas: list[dict], cabe) -> list[list[dict]]:
    """
    Llena cada diapositiva con todos los cursos que quepan, hasta cinco.

    No se decide a ojo por número de cursos: cuatro títulos cortos dejan media
    imagen vacía y cuatro de tres líneas se salen. Se mide cada diapositiva tal
    y como va a quedar, con `cabe(grupo)`, y se para justo antes de desbordar.
    Al final se equilibra: mejor 4 y 4 que 5 y 3.
    """
    def voraz(tope: int) -> list[list[dict]]:
        paginas, resto = [], list(filas)
        while resto:
            n = 1
            while n < min(tope, len(resto)) and cabe(resto[:n + 1]):
                n += 1
            paginas.append(resto[:n])
            resto = resto[n:]
        return paginas

    # 1. Lo más apretado posible, para saber cuántas diapositivas hacen falta
    apretado = voraz(MAX_POR_DIAPOSITIVA)
    # 2. Con ese mismo número de diapositivas, tamaños a partes iguales: 21
    #    cursos en 6 diapositivas son tres de 4 y tres de 3. En las pruebas, ni
    #    llenar a tope (4-4-4-4-3-2) ni llenar de cuatro en cuatro (4-4-4-4-4-1)
    #    servían: la última quedaba casi vacía.
    total = len(apretado)
    base, sobran = divmod(len(filas), total)
    tamanos = [base + 1] * sobran + [base] * (total - sobran)
    paginas, i = [], 0
    for tam in tamanos:
        grupo = filas[i:i + tam]
        while len(grupo) > 1 and not cabe(grupo):
            grupo = grupo[:-1]
        paginas.append(grupo)
        i += len(grupo)
    # Si algún grupo no cabía entero, el reparto igualado no sale: se usa el apretado
    return paginas if i == len(filas) else apretado


def _navegador(p):
    try:
        return p.chromium.launch()
    except Exception:
        candidatos = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
        if not candidatos:
            raise
        return p.chromium.launch(executable_path=candidatos[-1])


def _sello(destino: Path, ruta_csv: Path, cursos: int, imagenes: int) -> None:
    """generado.txt: cuándo, de qué tabla y cuántos cursos e imágenes."""
    (destino / "generado.txt").write_text(
        f"fecha: {date.today().isoformat()}\n"
        f"tabla: {ruta_csv.name}\n"
        f"cursos: {cursos}\n"
        f"imagenes: {imagenes}\n", encoding="utf-8")


def _quitado(fila: dict, quitar: list[str]) -> bool:
    t = (fila.get("titulo") or "").lower()
    return any(q.lower() in t for q in quitar)


def genera(ruta_csv: Path, destino: Path, fondo: Path | None = None,
           quitar: list[str] | None = None) -> list[Path]:
    filas = [f for f in lee_cursos(ruta_csv) if not _quitado(f, quitar or [])]
    destino.mkdir(parents=True, exist_ok=True)
    # Lo de la semana anterior se borra SIEMPRE, también si esta semana no hay
    # cursos: si no, el post viejo se quedaría en la carpeta y podría
    # publicarse creyendo que es el nuevo.
    for viejo in list(destino.glob("*.png")) + list(destino.glob("*.txt")):
        viejo.unlink()
    if not filas:
        (destino / "SIN-CURSOS.txt").write_text(
            f"La tabla {ruta_csv.name} no tiene ningún curso con fecha.\n", encoding="utf-8")
        _sello(destino, ruta_csv, 0, 0)
        print(f"La tabla {ruta_csv.name} no tiene cursos: no hay post esta vez.", file=sys.stderr)
        return []
    titulo_post = periodo_corto(filas)
    # Solo hace falta el navegador si hay algo que componer
    from playwright.sync_api import sync_playwright

    hechas = []
    with sync_playwright() as p:
        nav = _navegador(p)
        pag = nav.new_page(viewport={"width": ANCHO, "height": ALTO},
                           device_scale_factor=ESCALA)

        def cabe(grupo):
            pag.set_content(html_lista(grupo, 1, 1, titulo_post, True, fondo,
                                       midiendo=True))
            return pag.evaluate(_CABE)

        grupos = reparte(filas, cabe)
        total = len(grupos)

        # La portada: si hay muchas ciudades y no caben, se enseñan menos
        tope = MAX_CIUDADES
        pag.set_content(html_portada(filas, fondo, tope))
        while tope > 2 and not pag.evaluate(_CABE_PORTADA):
            tope -= 1
            pag.set_content(html_portada(filas, fondo, tope))
        hechas.append(destino / "01-portada.png")
        pag.screenshot(path=str(hechas[-1]))

        color = 0
        for i, grupo in enumerate(grupos, start=1):
            pag.set_content(html_lista(grupo, i, total, titulo_post, i == total, fondo,
                                       primer_color=color))
            color = (color + len(grupo)) % N_ACENTOS
            hechas.append(destino / f"{i + 1:02d}-cursos.png")
            pag.screenshot(path=str(hechas[-1]))
        nav.close()

    _sello(destino, ruta_csv, len(filas), len(hechas))
    if len(hechas) > MAX_DIAPOSITIVAS:
        print(f"¡Ojo! Salen {len(hechas)} imágenes y Instagram admite {MAX_DIAPOSITIVAS} "
              f"por carrusel: habrá que partirlo en dos posts.", file=sys.stderr)
    return hechas


def pie_del_post(filas: list[dict]) -> str:
    n = len(filas)
    return (f"📅 Agenda formativa · {periodo(filas)}\n\n"
            f"{n} cursos y congresos de Anestesiología, Cuidados Críticos y Dolor "
            f"en España. Desliza para verlos todos.\n\n"
            f"Las fechas vienen de la web de cada organizador: compruébalas antes "
            f"de inscribirte. ¿Falta alguno? Dínoslo en comentarios.\n\n"
            f"#anestesia #anestesiologia #cuidadosintensivos #medicinaintensiva "
            f"#dolor #formacionmedica #congresosmedicos #residentes #MIR")


def main() -> int:
    ap = argparse.ArgumentParser(description="Imágenes del post de la agenda")
    ap.add_argument("--csv", type=Path, default=None,
                    help="tabla de cursos (por defecto, la última consulta)")
    ap.add_argument("--salida", type=Path, default=SALIDA / "post",
                    help="carpeta donde dejar las imágenes")
    ap.add_argument("--fondo", type=Path, default=None,
                    help="imagen de fondo opcional (por ejemplo, hecha con Gemini)")
    ap.add_argument("--quitar", action="append", default=[], metavar="TEXTO",
                    help="quita del post los cursos cuyo título contenga TEXTO "
                         "(se puede repetir). Para quitarlos siempre, descartes.txt")
    args = ap.parse_args()

    ruta = args.csv or tabla_por_defecto()
    hechas = genera(ruta, args.salida, args.fondo, quitar=args.quitar)
    filas = [f for f in lee_cursos(ruta) if not _quitado(f, args.quitar)]
    if filas:
        (args.salida / "pie-del-post.txt").write_text(pie_del_post(filas), encoding="utf-8")
    print(f"{len(hechas)} imágenes a partir de {ruta.name} → {args.salida}/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
