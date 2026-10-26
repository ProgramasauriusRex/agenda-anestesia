# Agenda Anestesia

Rastrea automáticamente **297 webs** españolas y genera cada semana una tabla con
los cursos y congresos de Anestesiología, Cuidados Críticos y Dolor:

**Título · Fechas · Lugar · Entidad organizadora**

---

## Qué es cada archivo

No hace falta entenderlos todos. En la práctica solo tocarás el primero.

| Archivo | Para qué sirve | ¿Lo tocas tú? |
|---|---|---|
| **`fuentes.yaml`** | La lista de las 297 webs | **Sí**, este es el tuyo |
| `agenda.py` | El programa que visita las webs y hace la tabla | No |
| `verificar.py` | Comprueba que las 297 direcciones siguen vivas | No (lo ejecutas, no lo editas) |
| `fechas.py` | Entiende las fechas en español | No |
| **`post.py`** | Monta el post de Instagram: prompts + texto de cada diapositiva | No |
| `test_extractor.py` | Control de calidad del programa | No |
| `requirements.txt` | Lista de programas auxiliares a instalar | No |
| `.github/workflows/` | El despertador: hace que todo corra solo | No |
| `estado.json` | Recuerda qué cursos ya te enseñó, para no repetirlos (se crea solo) | No |
| `salida/eventos-conocidos.json` | Memoria de cursos encontrados hasta un año vista (se crea sola) | No |
| `salida/AGENDA-ACTUAL.md` | La tabla de esta semana, siempre en la misma dirección | No |
| `salida/POST-ACTUAL.md` | El post de Instagram listo: prompts y textos | No |
| `salida/` | Aquí aparecen las tablas (se crea sola) | No |

---

## Las tres órdenes que vas a usar

```bash
python verificar.py      # comprueba que las 297 webs responden (al empezar, y cada 3-6 meses)
python agenda.py         # los cursos NUEVOS del próximo mes  ← el del post semanal
python agenda.py --todo --meses 6    # mirar sin más: no altera el post del lunes
```

### El post de Instagram, ya montado

Cada lunes, junto a la tabla, aparece también esto:

```
salida/POST-ACTUAL.md
```

Dentro está todo lo que hace falta para publicar: los dos prompts de imagen,
el texto de cada diapositiva listo para pegar y el pie con los hashtags.

**El reparto del trabajo es a propósito: la IA hace el fondo, el texto lo
pones tú encima.** No es una pereza de este programa, es que las IA de imagen
no saben escribir: doce títulos en español con tildes, comillas y números
romanos salen convertidos en garabatos. Por eso los dos prompts piden
explícitamente *no text, no letters, no numbers* y dejan reservado el hueco
donde va la lista. Es el mismo reparto que ya usas en la carátula de iVoox.

Los prompts no cambian nunca: el de portada se genera una vez al mes y el de
fondo de lista, una vez y ya. Lo que cambia cada semana es el texto, y de eso
se encarga `post.py` solo.

Formato 4:5 vertical (1080 × 1350), cuatro cursos por diapositiva. Con seis
hay que achinar los ojos en el móvil.

### Cómo consultar los cursos (sin tocar nada)

Hay dos formas, y la diferencia importa.

**1. El lunes, que llega solo.** El rastreo corre a las 8:00 y deja la tabla en
el repositorio. Siempre en la misma dirección, para guardar en favoritos:

```
salida/AGENDA-ACTUAL.md
```

Ese archivo se reescribe cada lunes con la tabla de la semana, así que no hay
que ir buscando cuál es el más reciente. Al lado queda `AGENDA-ACTUAL.csv` para
abrir en una hoja de cálculo, y los archivos con fecha (`agenda-2026-10-05.md`)
como histórico.

Además, al terminar la ejecución, GitHub muestra en el resumen de ese lunes la
tabla de **cursos nuevos** — que es exactamente el contenido del post.

**2. Cualquier otro día: el botón de consulta.** En la pestaña **Actions** del
repositorio, **Consultar cursos (no cambia nada)** → *Run workflow* → elige
cuántos meses quieres ver → *Run*. En un par de minutos la tabla aparece en el
resumen de la ejecución, en pantalla, sin descargar nada.

> **Lo que no hay que hacer:** lanzar a mano el workflow **Agenda semanal**. Ese
> apunta en memoria lo que te ha enseñado, para no repetírtelo. Si lo lanzas un
> miércoles, esos cursos quedan marcados como vistos y el lunes siguiente ya no
> saldrán como nuevos. Para mirar, usa siempre el de consulta: ese no apunta
> nada.

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
  que permite revisar las 297 cada lunes en un par de minutos.
- **Páginas de agenda encontradas** → la dirección apuntaba a la portada y el
  verificador ha encontrado una página mejor (la sección "Cursos", "Agenda"…).
  Quedan anotadas en `fuentes.yaml` como comentario, para que las revises.
- **Bloqueadas por robots.txt** → el sitio prohíbe el rastreo y el programa lo
  respeta. Conviene leer el apartado siguiente antes de dar una por perdida:
  durante meses aparecieron aquí 27 webs que en realidad no prohibían nada.
- **No responden** → dirección equivocada o web desaparecida. Búscala en Google
  y corrige la línea `url:`, o borra el bloque entero si ya no existe.

Que aparezcan bastantes en esos dos últimos grupos es **normal y esperado**: la
lista se montó con las direcciones conocidas de cada entidad, y las webs
pequeñas cambian a menudo. El verificador existe precisamente para eso.

### Cuándo "bloqueada" no significa bloqueada

Una advertencia que costó 27 fuentes. Para saber si una web permite el rastreo
hay que leer su archivo `robots.txt`, y la forma estándar de hacerlo en Python
pide ese archivo identificándose como *Python-urllib*. Muchos sitios con
cortafuegos delante responden **403** a cualquier cliente que no parezca un
navegador — incluido el que pide el `robots.txt` — y la librería estándar
traduce ese 403 a «este sitio prohíbe todo».

Al revisar uno por uno los 27 `robots.txt` de las webs que figuraban como
bloqueadas, **ninguno** contenía la prohibición que se les atribuía. La UCLM,
la Universidad de Extremadura, el CGCOM, Quirónsalud, la Clínica Universidad de
Navarra, cinco colegios de médicos y la propia web de la SED solo estaban
rechazando a un visitante que no parecía humano.

Ahora el `robots.txt` se pide con las cabeceras del programa y se aplica el
criterio del **RFC 9309**, que es el estándar vigente:

| Respuesta del servidor | Qué se hace |
|---|---|
| 200 | se obedece lo que diga el archivo |
| 4xx (no existe, o no nos lo enseñan) | sin restricciones |
| 5xx (el servidor falla) | no se rastrea, por prudencia |

Esto **no** es saltarse el `robots.txt`: cuando el archivo existe y dice que no,
se respeta, y la prueba automática lo comprueba en siete escenarios distintos.
Lo que se ha corregido es tratar un error del cortafuegos como si fuera una
decisión de la entidad.

El resultado de la corrección, medido: **de 27 bloqueadas se pasó a 3**, y las
fuentes utilizables subieron de 170 a 195.

### Cuando el servidor pide calma

Hay dos respuestas que parecen un fallo y no lo son: el **429** ("vas muy
rápido") y el **503** ("ahora mismo no puedo"). Antes se reintentaban al
instante, lo que daba exactamente el mismo error y dejaba la web marcada como
rota. Ahora se espera antes de repetir, y se repite **dos veces**, a los 8 y a
los 20 segundos. Lo mismo con las conexiones que se caen.

Fueron dos reintentos y no uno por lo que pasó al crecer de 208 a 238 fuentes:
la verificación del 12/10 dio tiempo agotado en cinco colegios (A Coruña,
Cáceres, Granada, Segovia, Soria) que la semana anterior respondían sin
problema, y un 429 en la Universidad de La Rioja. No se habían roto: un único
reintento caía en el mismo mal momento.

Y ojo con esto, porque es fácil que pase desapercibido: **una fuente marcada
`roto` deja de visitarse los lunes**. Un fallo pasajero en la verificación la
saca del rastreo hasta la siguiente verificación, tres meses después. Por eso
esas siete se devolvieron a `pendiente` a mano.

### Lo que no tiene arreglo desde aquí

Nueve webs bloquean por la dirección de origen, y GitHub ejecuta esto desde un
centro de datos. Cuatro responden **403 a todo**, incluso presentándose como
navegador (UCLM, Universidad de Extremadura, Deusto y el CGCOM), y cinco dejan
la conexión colgada sin responder (Navarra Salud, astursalud, la UIB,
SOMIAMA y, con un 503 fijo, SAMIUC). Han fallado igual en todas las
verificaciones desde septiembre, así que no es mala suerte.

Desde un ordenador doméstico se abren sin problema. La única forma de
recuperarlas sería ejecutar el rastreo desde un ordenador en casa en vez de
desde GitHub.

### Titulares de noticias

El 12/10 se colaron tres noticias de webs de colegios como si fueran cursos:
"El COM Cantabria y el Ayuntamiento de Santander **celebran** la Semana del
Corazón", "Icoma y el Ayuntamiento **organizan** la X edición de BihotzAraba" y
"Menos de la mitad de las facultades de Medicina **imparten** formación en…".
Las tres mencionaban palabras de la especialidad, así que el filtro las dejó
pasar.

Lo que las delata es gramatical: el título de un curso es un sustantivo ("Curso
de ecografía", "VI Jornada de la SCARTD") y un titular es una oración con un
verbo conjugado. El programa busca esos verbos y descarta el título que los
lleva.

Se eligió buscar el verbo, y no exigir la palabra "curso" o "jornada", por un
caso concreto de la misma tabla: "Soporte Vital Intermedio Pediátrico" no lleva
ninguna de esas palabras y es un curso de verdad. Exigir el sustantivo lo
habría tirado; buscar el verbo, no. Sobre los dieciséis de ese lunes, se van
exactamente las tres noticias y se quedan los trece cursos.

---

## Cómo está organizada la lista de webs

**Las 297 se revisan todas cada lunes.** Los niveles siguen existiendo en
`fuentes.yaml`, pero solo sirven para pedir una pasada parcial a mano
(`python agenda.py --nivel 1`), no para decidir el rastreo automático.

| Nivel | Cuántas | Qué hay |
|---|---|---|
| **1** | 12 | SEDAR, SEMICYUC, SED, SEMDOR, ESRA, AnestesiaR, Dolor.com |
| **2** | 155 | Los **52 colegios de médicos**, grupos de trabajo de SEDAR, 13 sociedades autonómicas de anestesia, 12 de intensivos, **4 de dolor**, **10 de paliativos**, 24 nacionales, agregadores y los portales de formación de los servicios autonómicos de salud |
| **3** | 130 | 40 universidades públicas, 22 privadas, **60 hospitales universitarios y plataformas de formación hospitalaria**, grupos hospitalarios privados y el Consejo General de Colegios |

### La auditoría del 07/10

Se comprobó la lista contra lo que de verdad existe, y aparecieron dos huecos
grandes que llevaban semanas ahí sin que se notaran:

- **Ninguna sociedad autonómica de dolor.** Se habían pedido "todas las
  sociedades relacionadas con la anestesiología, los cuidados críticos o el
  dolor" y de dolor solo estaban las nacionales. Ahora están las cuatro que
  tienen web: Andalucía, Cataluña, C. Valenciana y Murcia.
- **Ninguna de las 15 federadas de SECPAL.** Están las diez que tienen web,
  con filtro estricto: solo aportan cuando el curso menciona dolor, analgesia,
  sedación o paliativos. Si quieres todo lo que publican, cambia su `filtro`
  a `evento`.

Más: once sociedades nacionales que faltaban (SEMES, ASECMA, GERM/ERAS, SET,
Perfusionistas, SEUP, SENeo, PEDPAL, AECPAL, SEEUE), la asociación de
anestesiólogos de Madrid, la sociedad de intensivos de Murcia, y cuatro
universidades cuyo Grado en Medicina se aprobó en 2025-2026 y por tanto no
existía cuando se montó la lista (La Rioja, UPC, Europea de Canarias y
Atlántico Medio).

Siete sociedades que existen **no tienen web**, así que no hay nada que
rastrear: SAMI (Asturias) y SNMIUC (norte) en intensivos; las sociedades del
dolor de Aragón, Galicia, Madrid y Canarias; y cinco federadas de SECPAL. Todas
difunden a través de su sociedad nacional, que sí está en la lista.

Las sociedades de intensivos del Norte (SNMIUC) y de Murcia (SOMIUC) no tienen
web propia: anuncian por SEMICYUC, que ya está en la lista. IMED Hospitales no
tiene sección de docencia. Las tres se retiraron para no dejar direcciones
muertas en el archivo.

### Por qué se pueden revisar todas

Porque cada visita cuesta poco. El verificador apunta en `fuentes.yaml`, en el
campo `feed`, si la web tiene canal RSS y cuál es — o `none` si no tiene. El
rastreo semanal lee ese dato y va directo, en vez de sondear a ciegas trece
direcciones buscando un canal que quizá no exista.

La diferencia es de 21 segundos por web a 2, y es lo que convierte "las 297
cada lunes" en unos minutos y unas 600 peticiones repartidas: dos por web
y una vez por semana. Menos de lo que gasta una persona abriendo esa misma
página en el navegador.

**Sobre los hospitales.** Hay dos capas.

La primera son los **portales de formación de los servicios autonómicos de
salud** (Sacyl, IAVANTE, ACIS, EVES, IACS, Acadèmia de Ciències Mèdiques…), que
recogen lo que cada hospital publica a través de su comunidad.

La segunda, añadida el 14/10, son **los hospitales universitarios con unidad
docente de Anestesiología**, apuntando siempre a la página donde anuncian sus
cursos y nunca a la portada. Lo que más se encontró no fueron páginas sueltas,
sino plataformas que agrupan a muchos hospitales a la vez:

- **Madrid**: cada hospital público tiene la misma página de actividades
  dentro de comunidad.madrid. Entran quince, más los institutos de
  investigación del Marañón, Ramón y Cajal y La Princesa.
- **Andalucía**: **GesForma**, el portal de formación de cada hospital del
  SAS. Se ve sin iniciar sesión y lista título, fechas e inscripción. Quince
  hospitales, más ibs.GRANADA e IBIMA.
- **Cataluña**: **Assistents Actes**, la plataforma de la Generalitat, que en
  una sola dirección recoge actos de Trueta, Moisès Broggi, Mataró, Reus,
  Tortosa o Vic. Más las agendas propias de Vall d'Hebron, Clínic, Bellvitge,
  Sant Pau, Germans Trias, el Mar, Parc Taulí y otros, y el catálogo de
  **Sant Joan de Déu ya filtrado a anestesiología pediátrica**.
- **Comunitat Valenciana**: La Fe y su instituto, el Clínico, el General, el
  de Alicante (ISABIAL), Elche, Gandia y el catálogo **eformacio** de La
  Ribera.
- Castilla y León, Castilla-La Mancha y Cruces, en el País Vasco: cinco más.

Donde no se encontró nada, casi siempre es porque no lo hay. **Murcia** solo
publica la formación de sus hospitales en una intranet. En **Asturias y
Navarra**, las webs de los hospitales cuelgan de dominios que bloquean al
rastreador. Y en **Galicia, Aragón, Baleares, Extremadura, Cantabria, La Rioja
y Canarias** la búsqueda no pudo confirmar ninguna página de cursos propia.
Ahí quedan los portales autonómicos de la primera capa.

### Varias fuentes en el mismo dominio

Con quince hospitales dentro de comunidad.madrid y trece dentro del portal del
SAS aparecieron dos problemas que antes no existían, y los dos están
corregidos.

**El canal equivocado.** Para buscar un RSS, el programa probaba las rutas
típicas en la raíz del sitio. Con una sociedad que tiene web propia está
bien: el canal de su portada es el suyo. Pero el de la portada de
comunidad.madrid es el de la Consejería entera, y se habría asignado a los
quince hospitales, que habrían leído las noticias del gobierno regional en vez
de su agenda. Ahora, cuando varias fuentes comparten dominio, el canal solo
vale si cuelga de la misma sección que la fuente. Ya pasaba a pequeña escala:
AECPAL, que vive dentro de la web de SECPAL, leía el canal de SECPAL.

**La pausa que faltaba.** El rastreo semanal espera 1,5 segundos entre dos
peticiones al mismo servidor desde el primer día. El verificador no lo hacía:
con seis hilos, los quince hospitales de Madrid habrían recibido hasta seis
peticiones a la vez, y el servidor habría contestado 429. Ahora el
verificador espera igual que el rastreo.

### El 404 disfrazado

La verificación del 18/10 dio **404, "no existe"**, en los quince hospitales de
Madrid. Pero esas páginas existen: abiertas desde un navegador, la de La Paz
muestra tres jornadas con fecha. La Comunidad de Madrid contesta "no existe"
al robot en vez de decir "no te dejo pasar".

Ahora, si la página principal de una fuente da 404, se pide otra vez como
navegador. Si así responde, el programa apunta ese servidor y le habla como
navegador el resto del rastreo, también al abrir las fichas de los cursos. Si
vuelve a dar 404, es que la página no existe de verdad y se queda como está.

Esto solo se hace con la página principal de cada fuente. Hacerlo en cada
sondeo de RSS duplicaría cientos de peticiones a rutas que de verdad no
existen.

Si aun así Madrid sigue en 404, es que el bloqueo es por la dirección de
origen, como en el grupo de las nueve, y no por cómo nos presentamos.

### oEmbed no es un RSS

WordPress declara en cada página un enlace de tipo `text/xml+oembed`. Lleva
"xml" en el nombre, así que el programa lo aceptaba como canal RSS. No lo es:
es la ficha técnica para incrustar la página en otra web, y no trae ni un
curso. Seis fuentes lo tenían apuntado como canal, alguna desde septiembre.
No rompía nada, porque al no salir cursos se volvía a leer la página, pero
inflaba el recuento: las fuentes con RSS de verdad eran 107, no 113. Al quitarlo
apareció otra cosa: en las seis, el oEmbed estaba tapando un RSS de verdad que
la página también declaraba. Ahora lo tienen, y el recuento vuelve a ser 113,
esta vez todos reales.

### Cursos que no son para un anestesiólogo

El primer rastreo con los hospitales (19/10) dio 25 cursos, y cinco sobraban:

- **Titulares de noticia** con verbos que todavía no estaban en la lista:
  "Talavera **aprende** a salvar vidas", "Toledo **se forma** en reanimación…".
  La forma reflexiva va aparte, porque "forma" suelta aparece en títulos de
  cursos de verdad y "se forma" solo en titulares.
- **Boletines**: "Número 18 de 'Actualidad SECPAL'".
- **Cursos para la población general**: RCP "para la ciudadanía", "primeros
  auxilios". Existen y son de salud, pero no son para tu audiencia.
- **Otras profesiones**: un máster de fisioterapia en terapia manual que
  entraba por mencionar el dolor.

Antes de dar por buenas estas reglas se probaron contra los 95 títulos
distintos que han salido alguna vez en una tabla o en la memoria. Quitan seis:
los cinco de arriba y "Cudeca se suma al Día Mundial de Cuidados Paliativos con
dos webinars…", que también es un titular. Ningún curso de verdad.

### El primer rastreo con todo (26/10)

29 cursos, los 29 con ciudad, con los hospitales de Madrid ya dentro. Ocho
filas sobraban, y se corrigió cada causa:

- **Encabezados y boletines** que algunos canales publican como si fueran una
  entrada más: "Últimos artículos" (IACS), "E-Bellvitge 755" (el boletín
  interno de Bellvitge), "Inscripciones" a secas.
- **Nombres de fichero** como título: "18 Actualidad SECPAL Octubre Diciembre
  2022.pdf". Ahora se limpian en vez de descartarse, porque al probar la regla
  de descartarlos contra el histórico se llevaba dos cursos reales ("Programa
  VII Curso Eco Pulmonar Seneo 2026v0.pdf" pasa a "VII Curso Eco Pulmonar
  Seneo 2026").
- **Un título de 2022 con fecha de 2026.** La memoria ya los limpiaba, pero
  solo al cargarla, una semana después: el registro nuevo salía en la tabla
  de esa misma semana. Ahora se mira también en lo recién encontrado.
- **Fuera de ámbito**: ecocardiografía fetal y neuropediatría. La cirugía
  fetal no se excluye, que su anestesia sí es de la especialidad.
- **Sant Joan de Déu**: el verificador le asignó el canal de toda la formación
  del hospital, no solo anestesia. Pasa a filtro estricto.

### Filtro "dolor" para los paliativos

Tres filas de aquel lunes eran de paliativos sin relación con el dolor:
espiritualidad y alzhéimer, la dimensión espiritual de los paliativos, un
webinar de paliativos perinatales. Entraban porque "paliativo" cuenta como
palabra de la especialidad, así que el filtro estricto apenas restringía a las
sociedades de paliativos.

Decisión de Luis: las 13 fuentes de paliativos (SECPAL, sus diez autonómicas,
PEDPAL y AECPAL) llevan ahora filtro `dolor`. Solo aportan un curso si su
**título** habla de dolor, analgesia, opioides, sedación, anestesia o
críticos, o nombra a la sociedad, para que su congreso siga entrando. Los
paliativos que vengan de un hospital no cambian: la "V Jornada de Cuidados
Paliativos de la Comunidad de Madrid" del Ramón y Cajal se queda.

Para que una de esas fuentes vuelva a aportar todo, cambia su `filtro` a
`estricto` (todo lo de paliativos) o a `evento` (absolutamente todo).

Sobre los 110 títulos del histórico, las reglas actuales descartan 28: 17 que
no eran cursos, 3 de un año anterior a su fecha y 8 de paliativos sin dolor.

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
- `filtro`: `dolor` en las fuentes de cuidados paliativos (solo cursos de
  dolor, analgesia, sedación o anestesia, mirando el título);
  `evento` en webs ya específicas de la especialidad;
  `estricto` en webs generalistas (colegios, universidades, hospitales,
  agregadores), donde además exige que el texto mencione la especialidad. Sin
  eso, la tabla se te llena de congresos de traumatología.

  El filtro estricto busca **palabras completas y expresiones clínicas**, no
  trozos: "UCI" no salta con "reducir", ni "intensivo" con "curso intensivo de
  inglés", ni "crítico" con "pensamiento crítico". También reconoce las siglas
  de las sociedades del campo (SEDAR, SEMICYUC, SECPAL…). La ecografía cuenta
  como especialidad, así que alguna ecografía para primaria se colará: es
  preferible a perder los cursos de ecografía perioperatoria o POCUS.

### Que la tabla se pueda publicar tal cual

Las primeras tablas reales (28/09 y 05/10) salieron con 18 cursos cada una, y
al mirarlas con intención de publicarlas aparecieron cuatro problemas. Los
cuatro están corregidos, y las pruebas automáticas guardan cada caso concreto:

- **Texto de interfaz dentro del título.** "Plazas limitadas Máster en
  Ecografía Musculoesquelética e Intervencionismo Ecoguiado Matrícula :
  Abierta para el curso 2026/2027". Ahora el título se corta donde empieza el
  texto de la web ("Añadir a favoritos", "Créditos ECTS", "Matrícula:"), y las
  etiquetas de estado pegadas delante se quitan — pero solo si lo que queda
  sigue siendo un título: de "Enfermería en cuidados críticos" no se toca nada.

- **Mayúsculas descolocadas.** "FUNDAMENTOS EN cuidados Críticos", "…paciente
  pediátrico en URGENCIAS", "70 reunion anual aaear 2026". Antes solo se
  arreglaba el título que gritaba entero; ahora también las palabras sueltas, y
  las siglas de las sociedades escritas en minúscula se suben a AAEAR, SCARTD…

- **Cursos repetidos.** Dos casos distintos. El mismo congreso enlazado dos
  veces en la misma página (misma dirección web: es el mismo acto), y el
  titular de una noticia junto al congreso que anuncia — "El XV Congreso
  Internacional de SECPAL combinará ciencia, innovación…" es el mismo acto que
  "XV Congreso Internacional SECPAL". Se juntan cuando empiezan el mismo día y
  todas las palabras con peso del título corto están en el largo. Gana el
  título corto, que es el oficial, pero se queda con lo que sabía el otro: la
  ciudad y el día de cierre. Y si el título nombra a otra de las entidades, esa
  pasa a ser la organizadora: para un congreso de SECPAL, mejor firma "SECPAL"
  que "Dolor.com".

- **Páginas de sección colándose como cursos.** "Congressos i Jornades SCARTD"
  es el índice de congresos, no un congreso. Se descartan por nombre de
  apartado y solo si el título es corto, para no llevarse por delante "VI
  Jornada de la Societat Catalana d'Anestesiologia…".

Resultado sobre la tabla real del 05/10: de 18 filas a 15, sin perder ningún
curso — las tres que se fueron eran dos repeticiones y un índice.

### La ciudad, cuando solo está dentro de la ficha

Ocho de quince cursos salían con el hueco de lugar vacío. No era un fallo del
detector: la ciudad no está en el listado, solo dentro de la página del curso.
Así que al final del rastreo se abren esas fichas y se busca allí, con tope de
50 por rastreo. Lo que se encuentra se guarda en memoria, para no volver a
pedirlo cada lunes. Si la ficha no lo dice, el hueco se queda vacío: sigue
siendo preferible a una ciudad inventada.

### La memoria se cura, ya no se tira

En la tabla del 05/10 seguía apareciendo "Congreso Panamericano e Ibérico de
Medicina Intensiva **Fecha**", con la etiqueta suelta al final. El limpiador
que corta eso existe desde el 23/09, pero ese registro se había capturado el
18/09 y la memoria lo arrastraba tal cual.

Antes, un título sucio en memoria hacía que se borrara el registro, confiando
en que el siguiente rastreo lo recogiera limpio. Con una fuente trimestral eso
significa que el curso desaparece durante meses. Ahora el título se vuelve a
pasar por el limpiador de hoy y el registro se queda.

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

- **Cada lunes a las 8:00** → las 297 webs, cursos del próximo mes
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
   medida para cada una de las 297: recorre los enlaces y mira el bloque de
   texto que rodea a cada uno. Si ahí hay una fecha y una palabra tipo "curso"
   o "congreso", es candidato.
4. **Interpreta la fecha** — con meses completos o abreviados («15 oct 2026»,
   «3 nov. 2026», «del 12 al 14 dic»), con «de» o sin él. Un día y un mes
   sueltos sin año ni «de» no cuentan como fecha: «Sala 3 marzo cerrada por
   obras» no es un curso. También "12, 13 y 14 de noviembre de 2026", "del 27 al 29
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
