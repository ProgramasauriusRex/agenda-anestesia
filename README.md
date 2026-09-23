# Agenda Anestesia

Rastrea automáticamente **211 webs** españolas y genera cada semana una tabla con
los cursos y congresos de Anestesiología, Cuidados Críticos y Dolor:

**Título · Fechas · Lugar · Entidad organizadora**

---

## Qué es cada archivo

No hace falta entenderlos todos. En la práctica solo tocarás el primero.

| Archivo | Para qué sirve | ¿Lo tocas tú? |
|---|---|---|
| **`fuentes.yaml`** | La lista de las 211 webs | **Sí**, este es el tuyo |
| `agenda.py` | El programa que visita las webs y hace la tabla | No |
| `verificar.py` | Comprueba que las 211 direcciones siguen vivas | No (lo ejecutas, no lo editas) |
| `fechas.py` | Entiende las fechas en español | No |
| `test_extractor.py` | Control de calidad del programa | No |
| `requirements.txt` | Lista de programas auxiliares a instalar | No |
| `.github/workflows/` | El despertador: hace que todo corra solo | No |
| `estado.json` | Recuerda qué cursos ya te enseñó, para no repetirlos (se crea solo) | No |
| `salida/eventos-conocidos.json` | Memoria de cursos encontrados hasta un año vista (se crea sola) | No |
| `salida/` | Aquí aparecen las tablas (se crea sola) | No |

---

## Las tres órdenes que vas a usar

```bash
python verificar.py      # comprueba que las 211 webs responden (al empezar, y cada 3-6 meses)
python agenda.py         # los cursos NUEVOS del próximo mes  ← el del post semanal
python agenda.py --todo --meses 6    # mirar sin más: no altera el post del lunes
```

### Cómo encaja con tu rutina

Cada lunes, `python agenda.py` te da **los cursos nuevos del próximo mes**: los
que no te ha enseñado todavía. Eso es justo el contenido del post.

- La **pantalla** muestra solo lo nuevo.
- El **archivo** `salida/agenda-FECHA.md` lleva todo lo del próximo mes, nuevo o no.

**`--todo` es una consulta de lectura**: enseña lo que le pidas sin apuntar nada,
así que puedes curiosear con ventanas amplias sin estropear el post del lunes
siguiente. Esto importa más de lo que parece — ver el apartado siguiente.

### Las dos memorias

El programa lleva dos memorias, y conviene entender por qué.

**1. Memoria de cursos conocidos** (`salida/eventos-conocidos.json`). Cada
rastreo guarda **todo lo que encuentra hasta un año vista**, y el post del lunes
se construye desde ahí, no solo desde lo visitado ese día.

Sin ella, las fuentes mensuales y trimestrales serían casi invisibles: una web
que se visita cada tres meses solo aportaría los cursos del mes siguiente a la
visita, y los de los meses dos y tres no aparecerían nunca. Con ella, un curso
que un colegio anuncia en septiembre para noviembre sale en tu post de finales
de octubre, aunque la web del colegio no se haya vuelto a visitar.

Los cursos ya celebrados se olvidan solos.

**2. Memoria de lo ya enseñado** (`estado.json`). Para no repetirte cada lunes
los mismos cursos. Solo apunta lo que sale en pantalla: si apuntara todo lo que
encuentra, un congreso lejano quedaría marcado como "visto" antes de tiempo y
nunca llegaría al post.

`--todo` no escribe en ninguna de las dos: es una consulta de lectura.

---

## Primero de todo: verificar

```bash
python verificar.py
```

Tarda unos minutos. Va una por una comprobando cuatro cosas, y al terminar
**actualiza `fuentes.yaml` él solo** y escribe un informe en `salida/`.

Lo que verás en el informe:

- **Con RSS** → las sólidas. Publican un canal pensado para máquinas, y no se
  rompen cuando la entidad rediseña su web. El verificador anota ese canal en
  el campo `feed`, y a partir de ahí el rastreo semanal va directo a él: es lo
  que permite revisar las 211 cada lunes en un par de minutos.
- **Páginas de agenda encontradas** → la dirección apuntaba a la portada y el
  verificador ha encontrado una página mejor (la sección "Cursos", "Agenda"…).
  Quedan anotadas en `fuentes.yaml` como comentario, para que las revises.
- **Bloqueadas por robots.txt** → el sitio prohíbe el rastreo y el programa lo
  respeta. AnestesiaR y la web principal de la SED están aquí. Para esas, el camino es
  el boletín de socio o Instagram.
- **No responden** → dirección equivocada o web desaparecida. Búscala en Google
  y corrige la línea `url:`, o borra el bloque entero si ya no existe.

Que aparezcan bastantes en esos dos últimos grupos es **normal y esperado**: la
lista se montó con las direcciones conocidas de cada entidad, y las webs
pequeñas cambian a menudo. El verificador existe precisamente para eso.

---

## Cómo está organizada la lista de webs

**Las 211 se revisan todas cada lunes.** Los niveles siguen existiendo en
`fuentes.yaml`, pero solo sirven para pedir una pasada parcial a mano
(`python agenda.py --nivel 1`), no para decidir el rastreo automático.

| Nivel | Cuántas | Qué hay |
|---|---|---|
| **1** | 12 | SEDAR, SEMICYUC, SED, SEMDOR, ESRA, AnestesiaR, Dolor.com |
| **2** | 132 | Los **52 colegios de médicos**, grupos de trabajo de SEDAR, las 12 sociedades autonómicas de anestesia, las 13 de intensivos, agregadores y los portales de formación de los 17 servicios autonómicos de salud |
| **3** | 67 | 38 universidades públicas, 19 privadas, grupos hospitalarios privados y el Consejo General de Colegios |

### Por qué se pueden revisar todas

Porque cada visita cuesta poco. El verificador apunta en `fuentes.yaml`, en el
campo `feed`, si la web tiene canal RSS y cuál es — o `none` si no tiene. El
rastreo semanal lee ese dato y va directo, en vez de sondear a ciegas trece
direcciones buscando un canal que quizá no exista.

La diferencia es de 21 segundos por web a 2, y es lo que convierte "las 211
cada lunes" en un par de minutos y unas 340 peticiones repartidas: dos por web
y una vez por semana. Menos de lo que gasta una persona abriendo esa misma
página en el navegador.

**Sobre los hospitales:** en vez de perseguir 840 webs de hospital, el nivel 2
incluye los **portales de formación de los servicios autonómicos de salud**
(Sacyl, IAVANTE, ACIS, EVES, IACS, Acadèmia de Ciències Mèdiques…). Cada uno
agrupa los cursos de todos los hospitales de su comunidad. Diecisiete
direcciones en lugar de cientos, y con mejor cobertura.

---

## Añadir una web nueva

Abre `fuentes.yaml` y copia este bloque al final, cambiando los datos:

```yaml
  - nombre: "Hospital Universitario X — Formación"
    url: https://ejemplo.es/docencia
    nivel: 2
    ambito: anestesia
    filtro: estricto
    estado: pendiente
```

El campo `feed` lo rellena solo el verificador; no lo escribas tú.

- `nivel`: solo para pasadas parciales a mano; el rastreo automático las visita todas
- `ambito`: `anestesia`, `criticos`, `dolor` o `mixto`
- `filtro`: `evento` en webs ya específicas de la especialidad;
  `estricto` en webs generalistas (colegios, universidades, hospitales,
  agregadores), donde además exige que el texto mencione la especialidad. Sin
  eso, la tabla se te llena de congresos de traumatología.

  El filtro estricto busca **palabras completas y expresiones clínicas**, no
  trozos: "UCI" no salta con "reducir", ni "intensivo" con "curso intensivo de
  inglés", ni "crítico" con "pensamiento crítico". También reconoce las siglas
  de las sociedades del campo (SEDAR, SEMICYUC, SECPAL…). La ecografía cuenta
  como especialidad, así que alguna ecografía para primaria se colará: es
  preferible a perder los cursos de ecografía perioperatoria o POCUS.

### Qué se descarta y qué no

Los cursos **con las plazas agotadas sí aparecen** —que existan y se hayan
llenado también es información—, con el título limpio y la nota
"— plazas agotadas" al final.

Sí se descartan: los enlaces que no son un título ("Ver y leer más…"), las
páginas que no son un curso, y lo que ya ha pasado. Cuando una web mete la
ficha entera dentro del enlace ("Curso X Nombre del curso: … Día y hora: …"),
el título se corta donde empieza la ficha.

---

## Ponerlo en marcha

### Opción A — en tu ordenador

```bash
pip install -r requirements.txt
python verificar.py
python agenda.py
```

### Opción B — en GitHub, automático (recomendada)

Sube estos archivos a un repositorio de GitHub y se ejecutará solo:

- **Cada lunes a las 8:00** → las 211 webs, cursos del próximo mes
- **Cada tres meses** → verificación de que las direcciones siguen vivas, y
  actualización del campo `feed` de cada una

(En horario de invierno se ejecuta a las 7:00: el reloj interno va en horario
universal.)

No necesitas tener el ordenador encendido y es gratis. Las tablas quedan
guardadas en la carpeta `salida/` del repositorio, con su histórico.

---

## Cómo funciona por dentro

Para cada web, en este orden:

1. **robots.txt** — si el sitio prohíbe el rastreo, se salta y lo avisa.
2. **Busca un RSS** — el camino fiable.
3. **Si no hay, lee el HTML** con un extractor genérico. No hay un programa a
   medida para cada una de las 211: recorre los enlaces y mira el bloque de
   texto que rodea a cada uno. Si ahí hay una fecha y una palabra tipo "curso"
   o "congreso", es candidato.
4. **Interpreta la fecha** — "12, 13 y 14 de noviembre de 2026", "del 27 al 29
   de mayo", "26-28 de Marzo" (sin año: lo deduce), "22/10/2026", rangos que
   cambian de mes y de año. También en catalán y gallego.
5. **Quita duplicados** — un congreso aparece en varias webs a la vez.

### Cuando la fecha está dentro de la ficha

Muchas webs listan solo el título y esconden la fecha dentro de cada curso.
Cuando un enlace **por sí solo** delata que es de la especialidad ("Diploma de
especialización en el manejo de la sepsis y shock séptico") pero no lleva fecha
al lado, el programa abre esa ficha y la busca allí — y de paso saca la ciudad.

Se hace con cuentagotas: como mucho 8 fichas por web y 250 en total por
rastreo, solo dentro del mismo dominio, y nunca para enlaces cuyo título ya
delata un año pasado. En la ficha prefiere la fecha que va precedida de "se
celebrará", "tendrá lugar" o "fechas", para no quedarse con la de publicación.

En el CSV, estos cursos salen con `via=ficha`.

### El detalle que más importa

Al buscar el contexto de un enlace, el programa sube por el HTML **solo mientras
el bloque contenga un único enlace**. En cuanto abarca varios, para. Sin esa
condición, cada curso heredaba la fecha y la ciudad del curso de al lado — un
fallo real que apareció en las pruebas y daba resultados creíbles pero falsos,
que es la peor clase de error para algo que vas a publicar.

---

## Lo que esto no puede hacer

- **Verifica antes de publicar.** Los agregadores no siempre actualizan cuando
  el organizador cambia fechas. Esto te ahorra la búsqueda, no el contraste.
- **El lugar es una aproximación.** Busca ciudades españolas en el texto. Si no
  la encuentra, deja el hueco vacío en lugar de inventárselo.
- **Lo que nunca llega a una web pública** (el correo a socios, la story de
  Instagram) es invisible para cualquier rastreador. Suscribirte a las listas de
  socio de SEDAR, SEMICYUC y SED sigue cubriendo terreno que esto no alcanza.
- **Se irá rompiendo.** Las webs cambian. Por eso `verificar.py` y el aviso
  `--diagnostico`: si una fuente que daba 5 cursos pasa a dar 0, algo cambió.
