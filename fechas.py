"""
Extracción de fechas en español a partir de texto libre.

Este es el núcleo del sistema: las webs de sociedades científicas escriben las
fechas de mil maneras distintas ("12-14 de noviembre de 2026", "26-28 de Marzo",
"15, 16 y 17 de mayo", "del 27 al 29 de mayo de 2026"). Aquí se normalizan todas
a (fecha_inicio, fecha_fin).
"""

import re
import unicodedata
from datetime import date

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    # catalán / gallego / euskera, porque varias sociedades publican en lengua cooficial
    "gener": 1, "febrer": 2, "marc": 3, "abril_ca": 4, "maig": 5, "juny": 6,
    "juliol": 7, "agost": 8, "setembre": 9, "octubre_ca": 10, "novembre": 11,
    "desembre": 12,
    "xaneiro": 1, "febreiro": 2, "maio": 5, "xuno": 6, "xullo": 7, "agosto_gl": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "decembro": 12,
    # Abreviados: "15 oct 2026", "3 nov. 2026", "del 12 al 14 dic". Es de las
    # formas más habituales en los listados y no se reconocía ninguna.
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
    "ago": 8, "sep": 9, "sept": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
    "gen": 1, "febr": 2, "juny": 6, "jul_ca": 7, "des": 12,
    "xan": 1, "xuñ": 6, "xul": 7, "out": 10, "dec": 12,
}

_MES_RE = "|".join(sorted(MESES.keys(), key=len, reverse=True))

# El \b tras el mes evita que "mayo" case dentro de "mayores" ahora que el
# "de" ya no es obligatorio; el punto opcional recoge "oct." y "sept."
MES = rf"({_MES_RE})\b\.?"
DE = r"\s+(?:de\s+)?"                       # "15 de octubre" y "15 octubre"
ANIO = r"(?:\s*,?\s*(?:de(?:l)?\s+)?(\d{4}))?"   # "de 2026", ", 2026", "2026"


def _normaliza(texto: str) -> str:
    """Minúsculas y sin tildes, para que 'Marzo' y 'marzo' casen igual."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto)


def _mes_num(nombre: str) -> int | None:
    return MESES.get(nombre.strip())


_RE_ANIO_SUELTO = re.compile(r"\b(19\d{2}|20\d{2})\b")


def _anio_del_texto(t: str) -> int | None:
    """
    Año que aparezca en el texto aunque no forme parte de la fecha.

    Existe por un caso real: una web anunciaba "XVIII Congreso SED 2022" y
    justo debajo "26 al 29 de octubre", sin año. Al no verlo en la fecha se
    asumía el próximo octubre y un congreso de 2022 se colaba en la agenda
    como si estuviera por venir. Con esto se lee el 2022 del título, la fecha
    queda en el pasado y el curso se descarta solo.
    """
    m = _RE_ANIO_SUELTO.search(t)
    return int(m.group(1)) if m else None


def anio_en_texto(texto: str) -> int | None:
    """Versión pública de lo anterior, para que agenda.py pueda revisar
    registros viejos guardados en memoria."""
    return _anio_del_texto(_normaliza(texto))


def _infiere_anio(mes: int, dia: int, hoy: date, texto: str = "") -> int:
    """
    Si la web no pone año en la fecha, primero se busca uno en el resto del
    texto. Solo si no hay ninguno se asume el próximo que tenga sentido:
    este año si la fecha aún no ha pasado, el siguiente si ya pasó.
    """
    del_texto = _anio_del_texto(texto)
    if del_texto is not None:
        return del_texto
    candidato = date(hoy.year, mes, min(dia, 28))
    return hoy.year if candidato >= hoy else hoy.year + 1


# Solo las abreviaturas son señal de fecha por sí solas. Un "3 marzo" suelto,
# sin "de" y sin año, aparece en frases como "Sala 3 marzo cerrada por obras",
# así que para una fecha suelta se exige "de", o año, o mes abreviado.
ABREVIADOS = {"ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep",
              "sept", "set", "oct", "nov", "dic", "gen", "febr", "juny",
              "des", "xan", "xul", "out", "dec"}


def _fecha_suelta_fiable(fragmento: str, mes: str, anio: str | None) -> bool:
    return bool(anio) or " de " in fragmento or mes.strip(".") in ABREVIADOS


def _fecha(dia: int, mes: int, anio: int) -> date | None:
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


# --- Patrones, del más específico al más genérico -------------------------

# "del 28 de septiembre al 2 de octubre de 2026"  (rango entre meses distintos)
P_RANGO_2MESES = re.compile(
    rf"(?:del\s+)?(\d{{1,2}}){DE}{MES}{ANIO}\s*"
    rf"(?:al?|a|hasta|[-–—])\s*"
    rf"(\d{{1,2}}){DE}{MES}{ANIO}"
)

# "12 al 14 de noviembre de 2026" / "26-28 de marzo" / "7–10 de junio de 2026"
P_RANGO_1MES = re.compile(
    rf"(?:del\s+)?(\d{{1,2}})\s*(?:al?|a|hasta|[-–—])\s*(\d{{1,2}}){DE}{MES}{ANIO}"
)

# "15, 16 y 17 de mayo de 2026" / "12, 13 y 14 de noviembre"
P_LISTA = re.compile(
    rf"(\d{{1,2}})(?:\s*,\s*\d{{1,2}})*\s*y\s*(\d{{1,2}}){DE}{MES}{ANIO}"
)

# "22 de octubre de 2026" (fecha suelta)
P_SIMPLE = re.compile(rf"(\d{{1,2}}){DE}{MES}{ANIO}")

# "22/10/2026", "22-10-26"
P_NUMERICA = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b")

# "2026-10-22" (ISO, habitual en atributos datetime de HTML)
P_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

# "noviembre de 2026" (solo mes y año — peor que nada, pero mejor que vacío)
P_MES_ANIO = re.compile(rf"\b{MES}\s+de(?:l)?\s+(\d{{4}})\b")


def extrae_fechas(texto: str, hoy: date | None = None) -> tuple[date | None, date | None, str]:
    """
    Devuelve (inicio, fin, fragmento_original).

    Si solo hay una fecha, fin == inicio. Si no encuentra nada, (None, None, "").
    """
    hoy = hoy or date.today()
    t = _normaliza(texto)

    # 1. Rango entre dos meses distintos
    if m := P_RANGO_2MESES.search(t):
        d1, mes1, a1, d2, mes2, a2 = m.groups()
        n1, n2 = _mes_num(mes1), _mes_num(mes2)
        if n1 and n2:
            anio_fin = int(a2) if a2 else (int(a1) if a1 else _infiere_anio(n2, int(d2), hoy, t))
            # si el rango cruza el fin de año (dic → ene), el inicio es del año anterior
            anio_ini = int(a1) if a1 else (anio_fin - 1 if n1 > n2 else anio_fin)
            f1, f2 = _fecha(int(d1), n1, anio_ini), _fecha(int(d2), n2, anio_fin)
            if f1 and f2:
                return f1, f2, m.group(0)

    # 2. Rango dentro del mismo mes
    if m := P_RANGO_1MES.search(t):
        d1, d2, mes, anio = m.groups()
        n = _mes_num(mes)
        if n:
            a = int(anio) if anio else _infiere_anio(n, int(d1), hoy, t)
            f1, f2 = _fecha(int(d1), n, a), _fecha(int(d2), n, a)
            if f1 and f2 and f2 >= f1:
                return f1, f2, m.group(0)

    # 3. Lista de días "15, 16 y 17 de mayo"
    if m := P_LISTA.search(t):
        d1, d2, mes, anio = m.groups()
        n = _mes_num(mes)
        if n:
            a = int(anio) if anio else _infiere_anio(n, int(d1), hoy, t)
            f1, f2 = _fecha(int(d1), n, a), _fecha(int(d2), n, a)
            if f1 and f2:
                return f1, f2, m.group(0)

    # 4. Fecha suelta en formato largo
    if m := P_SIMPLE.search(t):
        d, mes, anio = m.groups()
        n = _mes_num(mes)
        if n and _fecha_suelta_fiable(m.group(0), mes, anio):
            a = int(anio) if anio else _infiere_anio(n, int(d), hoy, t)
            f = _fecha(int(d), n, a)
            if f:
                return f, f, m.group(0)

    # 5. ISO
    if m := P_ISO.search(t):
        a, mes, d = (int(x) for x in m.groups())
        if f := _fecha(d, mes, a):
            return f, f, m.group(0)

    # 6. Numérica dd/mm/aaaa
    if m := P_NUMERICA.search(t):
        d, mes, a = (int(x) for x in m.groups())
        if a < 100:
            a += 2000
        if f := _fecha(d, mes, a):
            return f, f, m.group(0)

    # 7. Solo mes y año
    if m := P_MES_ANIO.search(t):
        mes, a = m.groups()
        n = _mes_num(mes)
        if n and (f := _fecha(1, n, int(a))):
            return f, f, m.group(0)

    return None, None, ""


def formatea(inicio: date | None, fin: date | None) -> str:
    """Formato legible en español para la tabla final."""
    if not inicio:
        return "—"
    MES_ES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
              "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    if not fin or fin == inicio:
        return f"{inicio.day} {MES_ES[inicio.month]} {inicio.year}"
    if inicio.month == fin.month and inicio.year == fin.year:
        return f"{inicio.day}-{fin.day} {MES_ES[inicio.month]} {inicio.year}"
    if inicio.year == fin.year:
        return f"{inicio.day} {MES_ES[inicio.month]} – {fin.day} {MES_ES[fin.month]} {inicio.year}"
    return f"{inicio.day} {MES_ES[inicio.month]} {inicio.year} – {fin.day} {MES_ES[fin.month]} {fin.year}"
