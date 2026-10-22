# Plan de proyecto — `terridata-graficas`

## Cómo arrancar

1. Crea una carpeta vacía, por ejemplo `terridata-graficas/`.
2. Guarda este archivo dentro como `PLAN.md`.
3. Abre Claude Code en esa carpeta y dale este primer mensaje:

   > Lee `PLAN.md` completo y construye el proyecto que describe. Trabaja por
   > fases como dice la sección 11: no pases a la siguiente hasta que la anterior
   > corra. Al terminar la fase 3 muéstrame una gráfica de ejemplo antes de
   > generar las 52. Usa el catálogo del Apéndice A tal cual está, sin cambiar
   > nombres de indicadores.

4. Pon tus `.txt` de TerriData en `datos/` y corre
   `python -m terridata --datos ./datos --salida ./salidas`.

---

> **Para Claude Code.** Este archivo es la especificación completa del proyecto.
> Léelo entero antes de escribir código. Todo lo que dice sobre el formato de
> TerriData, los nombres de los indicadores y las trampas de los datos está
> verificado contra dos extracciones reales (un municipio del Huila con 6.104
> filas y siete municipios de Norte de Santander con 12.495 filas). **No
> reinventes el catálogo ni adivines nombres de indicadores: úsalos tal como
> están en el Apéndice A.**

---

## 1. Qué tiene que hacer el proyecto

Un script de Python que:

1. Lee **una carpeta** con archivos `.txt` de TerriData (uno por municipio, o uno
   con varios municipios dentro — ambos casos deben funcionar).
2. Normaliza y consolida todo en una sola tabla en memoria.
3. Resuelve, para cada indicador del catálogo y cada entidad, **el dato más
   reciente sin pasar del año de corte**.
4. Genera **52 gráficas** en `PNG` y `SVG`, más un **dashboard HTML** de una sola
   página que las muestra todas organizadas por sección.

Un solo comando:

```bash
python -m terridata --datos ./datos --salida ./salidas --anio-corte 2026
```

### Decisiones ya tomadas (no las cuestiones)

| Tema | Decisión |
|---|---|
| Salidas | PNG + SVG por gráfica, más un dashboard HTML |
| Alcance | Las 52 gráficas que TerriData sí puede alimentar |
| Configuración | Todo en código Python — **sin YAML, sin JSON de configuración** |
| Librería de gráficas | `matplotlib` (backend `Agg`), nada de plotly ni de servidores |
| Dependencias | Solo `matplotlib`. El parseo va con la librería estándar. `pandas` es opcional; si lo usas, que sea la única dependencia extra |

---

## 2. Estructura de carpetas

```
terridata-graficas/
├── README.md
├── requirements.txt
├── datos/                      # los .txt de TerriData (vacía en el repo, con .gitkeep)
│   └── .gitkeep
├── salidas/                    # se crea sola; en .gitignore
│   ├── png/
│   ├── svg/
│   └── dashboard.html
├── terridata/
│   ├── __init__.py
│   ├── __main__.py             # CLI
│   ├── lectura.py              # descubrir y parsear los .txt
│   ├── catalogo.py             # el catálogo de indicadores (Apéndice A)
│   ├── resolucion.py           # alias, año de corte, matriz entidad × indicador
│   ├── derivados.py            # los cálculos (%, brechas, relaciones)
│   ├── estilo.py               # paleta, tipografía, specs de marca
│   ├── graficas.py             # primitivas: barras, barras agrupadas, apiladas, torta, líneas
│   ├── catalogo_graficas.py    # las 52 gráficas (Apéndice B)
│   └── dashboard.py            # el HTML
└── tests/
    ├── fixtures/
    │   └── mini_terridata.txt  # ~40 filas, 2 entidades, hecho a mano
    ├── test_lectura.py
    ├── test_resolucion.py
    └── test_derivados.py
```

---

## 3. Formato de entrada — exacto, verificado

Archivo de texto plano, **separado por `|`**, codificación **UTF-8**, con una
línea de encabezado. Trece columnas, siempre en este orden:

```
Código Departamento|Departamento|Código Entidad|Entidad|Dimensión|Subcategoría|Indicador|Dato Numérico|Dato Cualitativo|Año|Mes|Fuente|Unidad de Medida
```

Ejemplo real:

```
41|Huila|41306|Gigante|Descripción general|Descripción general|Población total|22.395,00||2000|12|DANE|Personas
41|Huila|41306|Gigante|Economía|Principales cultivos transitorios según producción|Primer cultivo transitorio en términos de toneladas producidas|3.606,00|Maíz|2016|12|Evaluación Agropecuaria Municipal, MinAgricultura|Número
```

### Reglas de parseo — cada una existe porque falla si no está

1. **Separador `|`.** Descarta (con aviso en el log) cualquier línea que no tenga
   exactamente 13 campos.
2. **Formato numérico colombiano.** `Dato Numérico` usa **punto de miles y coma
   decimal**: `22.395,00` → `22395.0`; `-1.698,39` → `-1698.39`; `503,35` →
   `503.35`. Nunca uses `float()` directo ni `locale`. Implementa:
   ```python
   def a_numero(txt: str) -> float | None:
       t = (txt or "").strip()
       if not t:
           return None
       t = t.replace(".", "").replace(",", ".")
       try:
           return float(t)
       except ValueError:
           return None
   ```
   Esta función necesita prueba unitaria con los cuatro casos de arriba más
   `""`, `"0,00"` y `"1.344.384,50"`.
3. **`Dato Numérico` y `Dato Cualitativo` son excluyentes casi siempre**, pero hay
   filas con ambos: los cultivos traen el tonelaje en `Dato Numérico` y el nombre
   del cultivo (`Maíz`, `Café`) en `Dato Cualitativo`. El modelo debe conservar los
   dos.
4. **`Año` es un entero**; `Mes` puede ser `0`.
5. **BOM**: abre con `encoding="utf-8-sig"`.
6. **Filas duplicadas.** Existen combinaciones `(entidad, dimensión, indicador,
   año)` repetidas — normalmente con el mismo valor, a veces en subcategorías
   distintas. Al agregar, usa **promedio**, no suma. (Verificado: `Déficit
   cualitativo de vivienda (Censo)` aparece dos veces con `46,17` las dos.)
7. **Un archivo puede traer varias entidades** y varios archivos pueden traer la
   misma. Al consolidar, **deduplica por la tupla completa de las 13 columnas**.
8. El orden de las entidades en la salida es **el orden de primera aparición** al
   recorrer los archivos ordenados alfabéticamente por nombre. Expón
   `--orden-entidades nombre` para ordenarlas alfabéticamente.

---

## 4. Reglas de negocio

### 4.1 Clave de búsqueda

La identidad de un indicador es la pareja **`(Dimensión, Indicador)`**. No metas
`Subcategoría` en la clave: el DNP la cambia entre versiones y es lo que provoca
las filas duplicadas del punto 3.6.

### 4.2 Alias

El DNP **renombra indicadores entre versiones**. Cada entrada del catálogo trae
hasta tres parejas `(dimensión, indicador)`. Regla de resolución:

> **se usa la primera pareja del catálogo que exista en los datos cargados.**

El orden dentro del catálogo ya está puesto a propósito. Renombramientos
confirmados que el catálogo ya resuelve:

| Nombre antiguo | Nombre nuevo |
|---|---|
| `Penetración de banda ancha` | `Penetración de internet fijo en los hogares` / `Penetración de acceso fijo a Internet` |
| `Déficit cualitativo de vivienda` | `Déficit cualitativo de vivienda (Censo)` |
| `Índice de pobreza multidimensional - IPM` | `indice de pobreza multidimensional - IPM (Censo)` (ojo: sin tilde en la nueva) |
| `Afiliados al régimen subsidado` (con la errata del DNP) | `Afiliados al régimen subsidiado` |

Si ninguna pareja aparece, el indicador queda **no disponible** y sus gráficas se
omiten con un aviso — nunca con una excepción.

### 4.3 Año de corte

`--anio-corte` (por defecto, el año actual). Para cada `(entidad, indicador)` se
toma el **año más alto con dato numérico que no supere el corte**.

Esto no es un adorno: TerriData trae proyecciones de población **hasta 2042**. Sin
el tope, la densidad poblacional de un municipio saldría proyectada a 2042.

El año efectivamente usado debe quedar registrado y aparecer en el subtítulo de
cada gráfica (`Dato 2021`) y en el dashboard.

### 4.4 Las dos series de población — la trampa más grande

TerriData publica **dos series de población que no coinciden**:

| Dimensión | Gigante 2019 | Cobertura temporal |
|---|---|---|
| `Censo 2005 y proyecciones DANE` | **35.498** | solo 2019 |
| `Demografía y población` | 24.490 | 2018–2042 |

El catálogo **prioriza `Censo 2005 y proyecciones DANE`** para población total,
urbana, rural, hombres y mujeres, porque es internamente coherente
(`17.993 + 17.505 = 35.498` y `19.369 + 16.129 = 35.498`).

**No mezcles las dos series en una misma gráfica ni en un mismo cálculo.** Si el
archivo cargado solo trae la serie nueva, el alias 2 la recoge y todo sigue
coherente.

### 4.5 Indicadores de texto

`REGION`, `CAT_RURAL`, `COD_DANE`, `CAT617`, `SUBREGION` y los `NOM_*` de cultivos
salen de `Dato Cualitativo`. No tienen año útil (el DNP les pone `2000`). Se
resuelven tomando la primera fila que coincida con la clave y la entidad.

---

## 5. Modelo de datos

```python
@dataclass(frozen=True)
class Fila:
    cod_departamento: str
    departamento: str
    cod_entidad: str
    entidad: str
    dimension: str
    subcategoria: str
    indicador: str
    valor: float | None
    texto: str | None
    anio: int
    mes: int
    fuente: str
    unidad: str

@dataclass(frozen=True)
class Ind:                      # una entrada del catálogo
    id: str
    etiqueta: str
    unidad: str
    tipo: str                   # "NUM" | "TXT"
    decimales: int
    alias: list[tuple[str, str]]   # [(dimensión, indicador), ...] en orden de preferencia

@dataclass
class Resultado:
    entidades: list[str]        # en orden
    departamento: str
    valores: dict[str, dict[str, float | str | None]]   # id_indicador -> entidad -> valor
    anios: dict[str, int | None]                        # id_indicador -> año usado
    faltantes: list[str]                                # ids no disponibles
```

`resolucion.py` expone una sola función pública:
`resolver(filas, catalogo, anio_corte) -> Resultado`.

---

## 6. Derivados

`derivados.py` calcula, sobre el `Resultado`, lo que las gráficas necesitan y que
no viene directo de TerriData. Cada uno con su prueba:

| Derivado | Fórmula |
|---|---|
| `PCT_DEL_TOTAL` | `POB_TOTAL(e) / Σ POB_TOTAL × 100` |
| `PCT_RURAL` | `POB_RUR / POB_TOTAL × 100` |
| `PCT_URBANA` | `POB_URB / POB_TOTAL × 100` |
| `TOTAL_AFILIADOS` | `AFIL_SUBS + AFIL_CONTRIB + AFIL_ESP` — si `AFIL_SGSSS` existe, úsalo y deja este de respaldo |
| `COBERTURA_SGSSS` | `TOTAL_AFILIADOS / POB_TOTAL × 100`, topado en 100 |
| `SIN_AFILIAR_PCT` | `100 − COBERTURA_SGSSS`, con piso en 0 |
| `VAR_ACU_CENSO_REC` | `ACU_REC − ACU_CENSO` (puntos porcentuales) |
| `VAR_ALC_CENSO_REC` | `ALC_REC − ALC_CENSO` |
| `BRECHA_ACU_URB_RUR` | `ACU_URB − ACU_RUR` |
| `BRECHA_ALC_URB_RUR` | `ALC_URB − ALC_RUR` |
| `PROD_AGRICOLA_TOTAL` | suma de los ocho `CULT_*` |

Cualquier operando `None` produce `None`, nunca cero y nunca una excepción.

---

## 7. Diseño de las gráficas

`estilo.py` centraliza todo. **No inventes colores.**

### 7.1 Paleta categórica (orden fijo, nunca cíclico)

| Slot | Tono | Claro | Oscuro |
|---|---|---|---|
| 1 | azul | `#2a78d6` | `#3987e5` |
| 2 | naranja | `#eb6834` | `#d95926` |
| 3 | aqua | `#1baf7a` | `#199e70` |
| 4 | amarillo | `#eda100` | `#c98500` |
| 5 | magenta | `#e87ba4` | `#d55181` |
| 6 | verde | `#008300` | `#008300` |
| 7 | violeta | `#4a3aa7` | `#9085e9` |
| 8 | rojo | `#e34948` | `#e66767` |

Asigna los slots **en orden**: una gráfica de una serie usa el slot 1, una de tres
series usa 1-2-3. Nunca los recicles ni los rotes. Ninguna gráfica del catálogo
pasa de 8 series.

**El color sigue a la entidad, no a su posición.** En las gráficas de barras por
municipio (una serie), todas las barras van del mismo color — el municipio ya está
en el eje. En las de varias series, cada serie mantiene su color en todas las
gráficas del set.

### 7.2 Rampa secuencial (azul, claro → oscuro)

`#cde2fb · #b7d3f6 · #9ec5f4 · #86b6ef · #6da7ec · #5598e7 · #3987e5 · #2a78d6 · #256abf · #1c5cab · #184f95 · #104281 · #0d366b`

Úsala solo si alguna gráfica codifica magnitud continua. Para las de ranking
(ODS 6 ordenadas de menor a mayor) **no** uses la rampa: una sola color sólido,
que el orden ya comunica la magnitud.

### 7.3 Superficies y texto

| Rol | Claro | Oscuro |
|---|---|---|
| Superficie | `#fcfcfb` | `#1a1a19` |
| Texto primario | `#0b0b0b` | `#ffffff` |
| Texto secundario | `#52514e` | `#c3c2b7` |
| Rejilla / ejes | `#e6e5e1` | `#383835` |

Por defecto todo se renderiza en **modo claro** — los PNG y SVG van a Word y
PowerPoint, que son claros. `--tema oscuro` vuelve a renderizar el set completo
con la columna oscura, y el dashboard usa el set que se haya generado.

### 7.4 Specs de marca — fijos en todas las gráficas

- **Barras**: máximo **24 px** de grosor. No llenes el slot: el aire sobrante es
  parte del diseño. Extremo del dato **redondeado 4 px**, cuadrado en la línea base.
- **Separación entre marcas**: **2 px del color de la superficie** entre segmentos
  de una barra apilada y entre barras adyacentes. Es un hueco, no un borde. Nunca
  dibujes contorno alrededor de una marca para separarla.
- **Líneas**: 2 px, unión y extremo redondeados. Marcadores ≥ 8 px de diámetro con
  **anillo de 2 px del color de la superficie**.
- **Rejilla y ejes**: 1 px sólido, del gris de rejilla, recesivos. Nunca punteados.
  Solo rejilla horizontal en columnas, solo vertical en barras horizontales.
- **Sin marco**: quita los `spines` superior y derecho.

### 7.5 Etiquetas y leyenda

- **Una sola serie → sin caja de leyenda.** El título ya dice qué se está
  graficando; una leyenda de un ítem repite el título y roba espacio.
- **Dos o más series → leyenda siempre presente**, arriba, horizontal, sin marco.
  Hasta 4 series, además, etiqueta directa sobre la marca.
- **Etiqueta selectivamente, nunca un número sobre cada punto.** En las gráficas de
  una serie por municipio sí va el valor en la punta de cada barra (son pocas
  categorías y es el uso real: leer la cifra). En las de varias series, el valor va
  solo en el máximo y el mínimo; el resto lo carga el eje.
- **Una etiqueta que no cabe no se recorta: se mueve afuera de la barra o se
  omite.** Mide el texto antes de dibujarlo. Prohibido `overflow: hidden` o
  equivalente.
- **El texto nunca lleva el color de la serie.** Valores, etiquetas de eje y
  leyenda van en los tokens de texto. La identidad la da la marca de color que está
  al lado.
- Eje Y: números redondos con separador de miles (`1.000`, `20.000`). Formato
  colombiano (punto de miles).

### 7.6 Reglas duras — si la gráfica incumple una, está mal

- **Nunca dos ejes Y.** Dos magnitudes de escala distinta → dos gráficas. Esto
  afecta a "Población vs Total afiliados": ambas son personas, así que **sí** van
  juntas. Pero si en algún momento quieres cruzar cobertura (%) con población
  (personas), son dos gráficas.
- **Nunca arcoíris en una rampa secuencial.**
- **Nunca un color de estado (rojo/verde) reutilizado como "serie 4".**
- **Las tortas solo para composición de un total**, máximo 7 porciones, con el
  porcentaje en la etiqueta. Si hay más de 7 entidades, las que estén por debajo
  del 2 % se agrupan en "Otros".
- Título de la gráfica: qué se mide. Subtítulo: fuente, año del dato y unidad.
- Cada gráfica lleva al pie: `Fuente: TerriData (DNP) — <fuente original> · Dato <año>`.

### 7.7 Archivos de salida

- `salidas/png/<seccion>_<id>.png` a **200 dpi**, fondo del color de superficie
  (no transparente: se pega en documentos claros).
- `salidas/svg/<seccion>_<id>.svg`, mismo dibujo, texto como texto (no trazados),
  para poder reescalar y editar.
- Tamaño base **1600 × 900 px**; las tortas **1100 × 900**; la de líneas de
  inversión **2000 × 800**.

---

## 8. El dashboard HTML

Un solo archivo `salidas/dashboard.html`, **autocontenido**: los SVG van **en
línea** dentro del HTML (no `<img src>`), así abre desde el disco sin depender de
rutas ni de servidor.

Contenido:

1. **Encabezado**: título del análisis, departamento detectado, año de corte,
   número de entidades, fecha de generación.
2. **Fila de tarjetas** (stat tiles) con: entidades analizadas, población total del
   conjunto, cobertura SGSSS promedio, indicadores resueltos / indicadores del
   catálogo.
3. **Navegación lateral pegajosa** con las seis secciones.
4. **Una sección por bloque**, cada gráfica en su tarjeta con título, subtítulo y
   el SVG.
5. **Vista de tabla**: debajo de cada gráfica, un `<details>` plegado con los datos
   que la alimentan en una `<table>`. Esto no es opcional — es lo que hace que la
   información no dependa solo del color.
6. **Avisos**: al final, la lista de indicadores no disponibles en los datos
   cargados y las gráficas que se omitieron por eso.

Detalles de implementación:

- Responsive: una columna por debajo de 900 px.
- Modo oscuro por `prefers-color-scheme` **solo para el cromo de la página**. Las
  tarjetas de gráfica mantienen su superficie clara, porque los SVG se generaron
  con la paleta clara. Dilo en un comentario del HTML para que no confunda a quien
  lo lea después.
- Sin CDN, sin fuentes externas, sin JavaScript salvo el mínimo para el índice
  lateral. Debe funcionar con doble clic desde el explorador de archivos.

---

## 9. CLI

```
python -m terridata [opciones]

  --datos RUTA          carpeta con los .txt          (por defecto ./datos)
  --salida RUTA         carpeta de salida             (por defecto ./salidas)
  --anio-corte N        año de corte                  (por defecto, el año actual)
  --titulo TEXTO        título del análisis           (por defecto "Análisis comparativo TerriData")
  --secciones LISTA     secciones a generar, separadas por coma
                        (poblacion, ods1, ods2, ods3, ods6, salud_publica; por defecto todas)
  --formatos LISTA      png,svg,html                  (por defecto los tres)
  --tema claro|oscuro   paleta de renderizado         (por defecto claro)
  --orden-entidades aparicion|nombre
  --verboso             log detallado de resolución de indicadores
```

Al terminar, imprime un resumen:

```
Entidades: 7 (CÁCOTA, CHITAGÁ, CUCUTILLA, MUTISCUA, PAMPLONA, PAMPLONITA, SILOS)
Departamento: Norte de Santander | Filas leídas: 12.495 | Año de corte: 2026
Indicadores resueltos: 45/45
Gráficas generadas: 52  (png 52 · svg 52)
Dashboard: salidas/dashboard.html
```

Códigos de salida: `0` todo bien · `1` error de entrada (carpeta vacía, sin
archivos válidos) · `2` se generó parcialmente (hubo indicadores faltantes).

---

## 10. Pruebas y criterios de aceptación

### Pruebas unitarias (`pytest`)

- `a_numero` con los siete casos del punto 3.2.
- Parseo de una línea completa, incluida una con `Dato Cualitativo` y `Dato
  Numérico` a la vez.
- Resolución de alias: catálogo con tres alias, datos que solo traen el tercero.
- Año de corte: un indicador con datos 2019, 2021 y 2042 y corte 2026 devuelve 2021.
- Duplicados: dos filas iguales promedian a su valor, no lo duplican.
- Derivados con `None` en un operando.
- Una entidad sin datos de un indicador no rompe el resto.

### Criterios de aceptación

1. Con una carpeta de **un solo municipio**, corre sin error y genera las 52
   gráficas (las de comparación mostrarán una sola barra: es correcto).
2. Con una carpeta de **siete municipios**, las entidades aparecen en el orden
   esperado y ninguna gráfica queda vacía.
3. Con una carpeta **vacía**, sale con código 1 y un mensaje claro, sin traza.
4. Con un `.txt` **corrupto** (líneas de 11 campos), los avisa y sigue con el resto.
5. `dashboard.html` abre por doble clic, sin red, y muestra las 52 gráficas.
6. Ninguna gráfica tiene dos ejes Y; ninguna leyenda de una sola serie.
7. `python -m terridata --anio-corte 2020` cambia los años usados y se nota en los
   subtítulos.
8. **Verificación numérica contra la fuente**: un test de integración toma tres
   valores conocidos del fixture y comprueba que la matriz resuelta los reproduce.

### Después de generar — míralo

El validador de paleta revisa color, no geometría. **Abre el dashboard y mira las
gráficas** antes de dar el trabajo por terminado: etiquetas encimadas, barras que
se salen, títulos cortados, tortas con porciones ilegibles. Si algo se ve mal, se
arregla aunque los tests pasen.

---

## 11. Orden de implementación

Trabaja en fases y deja cada una funcionando antes de seguir.

| Fase | Qué queda listo |
|---|---|
| **1** | `lectura.py` + `catalogo.py` + tests. Un comando que imprime entidades y filas leídas. |
| **2** | `resolucion.py` + `derivados.py` + tests. Un `--verboso` que imprime la matriz resuelta como tabla en consola. |
| **3** | `estilo.py` + `graficas.py` con las cinco primitivas y **una** gráfica de ejemplo bien terminada. Míralas antes de seguir. |
| **4** | `catalogo_graficas.py` con las 52 y el bucle de renderizado a PNG y SVG. |
| **5** | `dashboard.py`. |
| **6** | `README.md` con instalación, uso, ejemplos y la tabla de qué no se puede reproducir. |

---

## 12. Lo que este proyecto NO hace

Déjalo escrito en el `README.md` para que nadie lo busque:

- **27 gráficas del Excel original quedan fuera** porque no salen de TerriData:
  distribución por EPS y cifras de afiliación de corte (reporte DANE/ADRES), red de
  prestadores (REPS), segmentación departamental por nodos.
- **Indicadores que TerriData no publica a nivel municipal**: analfabetismo,
  matrícula oficial, IRCA, médicos y camas por 10.000 habitantes, desnutrición
  crónica, pobreza monetaria, GINI, desempleo, TGP, informalidad, PIB municipal,
  área sembrada, hectáreas de amenaza por inundación, vigencia del POT.
- **Indicadores descontinuados**: Índice de Desempeño Integral, IGA y Transparencia
  por Colombia — el DNP los reemplazó por la Medición de Desempeño Municipal (MDM).

---

## Apéndice A — `catalogo.py`

Cópialo tal cual. **Los nombres están verificados contra extracciones reales de
TerriData; una tilde o un espacio de más rompe la búsqueda.** El orden de los
alias dentro de cada entrada es deliberado (ver §4.2 y §4.4).

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Ind:
    id: str
    etiqueta: str
    unidad: str
    tipo: str            # "NUM" | "TXT"
    decimales: int
    alias: list          # [(dimensión, indicador), ...] en orden de preferencia

CATALOGO = [
    # --- Descripción general
    Ind("COD_DANE", "Código DANE", "Texto", "TXT", 0, [("Descripción general", "Código DANE")]),
    Ind("REGION", "Región", "Texto", "TXT", 0, [("Descripción general", "Región")]),
    Ind("SUBREGION", "Subregión (SGR)", "Texto", "TXT", 0, [("Descripción general", "Subregión (SGR)")]),
    Ind("CAT617", "Categoría Ley 617 de 2000", "Texto", "TXT", 0, [("Descripción general", "Categoría ley 617 de 2000")]),
    Ind("CAT_RURAL", "Categoría de ruralidad", "Texto", "TXT", 0, [("Descripción general", "Categoría de ruralidad")]),
    Ind("EXTENSION", "Extensión territorial", "Km²", "NUM", 2, [("Descripción general", "Extensión")]),
    Ind("DENSIDAD", "Densidad poblacional", "Hab/Km²", "NUM", 2, [("Descripción general", "Densidad poblacional"), ("Censo 2005 y proyecciones DANE", "Densidad poblacional")]),
    # --- Demografía  (ver §4.4: la serie "Censo 2005 y proyecciones DANE" va primero)
    Ind("POB_TOTAL", "Población total", "Personas", "NUM", 0, [("Censo 2005 y proyecciones DANE", "Población total"), ("Demografía y población", "Población total"), ("Descripción general", "Población total")]),
    Ind("POB_URB", "Población cabecera (urbana)", "Personas", "NUM", 0, [("Censo 2005 y proyecciones DANE", "Población urbana"), ("Demografía y población", "Población urbana")]),
    Ind("POB_RUR", "Población resto (rural)", "Personas", "NUM", 0, [("Censo 2005 y proyecciones DANE", "Población rural"), ("Demografía y población", "Población rural")]),
    Ind("POB_H", "Población hombres", "Personas", "NUM", 0, [("Censo 2005 y proyecciones DANE", "Población total de hombres"), ("Demografía y población", "Población total de hombres")]),
    Ind("POB_M", "Población mujeres", "Personas", "NUM", 0, [("Censo 2005 y proyecciones DANE", "Población total de mujeres"), ("Demografía y población", "Población total de mujeres")]),
    Ind("PCT_H", "Porcentaje población de hombres", "%", "NUM", 2, [("Censo 2005 y proyecciones DANE", "Porcentaje población de hombres"), ("Demografía y población", "Porcentaje población de hombres")]),
    Ind("PCT_M", "Porcentaje población de mujeres", "%", "NUM", 2, [("Censo 2005 y proyecciones DANE", "Porcentaje población de mujeres"), ("Demografía y población", "Porcentaje población de mujeres")]),
    Ind("SISBEN_T", "Puntaje SISBEN promedio — Total", "Puntos", "NUM", 2, [("Demografía y población", "Puntaje SISBEN: Promedio - Total")]),
    Ind("SISBEN_REG", "Registros válidos SISBEN", "Personas", "NUM", 0, [("Demografía y población", "Total registros válidos - Personas")]),
    # --- Vivienda y servicios públicos
    Ind("ACU_CENSO", "Cobertura de acueducto (Censo)", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de acueducto (Censo)")]),
    Ind("ACU_REC", "Cobertura de acueducto (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de acueducto (REC)")]),
    Ind("ACU_URB", "Cobertura de acueducto urbana (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de acueducto urbana (REC)")]),
    Ind("ACU_RUR", "Cobertura de acueducto rural (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de acueducto rural (REC)")]),
    Ind("ALC_CENSO", "Cobertura de alcantarillado (Censo)", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de alcantarillado (Censo)")]),
    Ind("ALC_REC", "Cobertura de alcantarillado (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de alcantarillado (REC)")]),
    Ind("ALC_URB", "Cobertura de alcantarillado urbana (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de alcantarillado urbana (REC)")]),
    Ind("ALC_RUR", "Cobertura de alcantarillado rural (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de alcantarillado rural (REC)")]),
    Ind("ASEO_REC", "Cobertura de aseo (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de aseo (REC)")]),
    Ind("ASEO_URB", "Cobertura de aseo urbana (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de aseo urbana (REC)")]),
    Ind("ASEO_RUR", "Cobertura de aseo rural (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de aseo rural (REC)")]),
    Ind("ENER_RUR", "Cobertura de energía eléctrica rural", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de energía eléctrica rural")]),
    Ind("BANDA", "Penetración de internet fijo", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Penetración de banda ancha"), ("Vivienda y acceso a servicios públicos", "Penetración de internet fijo en los hogares"), ("Vivienda y acceso a servicios públicos", "Penetración de acceso fijo a Internet")]),
    Ind("DEF_CUANT", "Déficit cuantitativo de vivienda", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Déficit cuantitativo de vivienda"), ("Vivienda y acceso a servicios públicos", "Déficit cuantitativo de vivienda (Censo)")]),
    Ind("DEF_CUAL", "Déficit cualitativo de vivienda", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Déficit cualitativo de vivienda"), ("Vivienda y acceso a servicios públicos", "Déficit cualitativo de vivienda (Censo)")]),
    # --- Salud  (los primeros alias recogen el bloque de corte propio si lo pegaron)
    Ind("AFIL_CONTRIB", "Afiliados al régimen contributivo", "Personas", "NUM", 0, [("Salud", "Afiliados régimen contributivo"), ("Salud", "Afiliados al régimen contributivo")]),
    Ind("AFIL_SUBS", "Afiliados al régimen subsidiado", "Personas", "NUM", 0, [("Salud", "Afiliados régimen subsidiado"), ("Salud", "Afiliados al régimen subsidado"), ("Salud", "Afiliados al régimen subsidiado")]),
    Ind("AFIL_ESP", "Afiliados a regímenes especiales", "Personas", "NUM", 0, [("Salud", "Afiliados régimen de excepción y especiales"), ("Salud", "Afiliados a regímenes especiales")]),
    Ind("AFIL_SGSSS", "Afiliados al SGSSS", "Personas", "NUM", 0, [("Salud", "Total afiliados SGSSS"), ("Salud", "Afiliados al SGSSS")]),
    Ind("PPNA", "Población pobre no atendida (PPNA)", "Personas", "NUM", 0, [("Salud", "Población pobre no atendida - PPNA")]),
    Ind("VAC_PENTA", "Cobertura vacunación pentavalente <1 año", "% ×100", "NUM", 2, [("Salud", "Cobertura vacunación pentavalente en menores de 1 año")]),
    Ind("MORT_MAT", "Razón de mortalidad materna a 42 días", "x 100.000 NV", "NUM", 2, [("Salud", "Razón de mortalidad materna a 42 días")]),
    Ind("MORT_INF", "Tasa de mortalidad infantil <1 año", "x 1.000 NV", "NUM", 2, [("Salud", "Tasa de mortalidad infantil en menores de 1 año (x cada 1.000 nacidos vivos)")]),
    Ind("MORT_GEN", "Tasa de mortalidad general", "x 1.000 hab", "NUM", 2, [("Salud", "Tasa de mortalidad (x cada 1.000 habitantes)")]),
    Ind("FECUNDIDAD", "Tasa de fecundidad (MEF)", "x 1.000 MEF", "NUM", 2, [("Salud", "Tasa de fecundidad (x cada 1.000 mujeres en edad fértil)")]),
    # --- Convivencia
    Ind("T_VIF", "Tasa de violencia intrafamiliar", "x 100.000 hab", "NUM", 2, [("Convivencia y seguridad ciudadana", "Tasa de violencia intrafamiliar por cada 100.000 habitantes")]),
    # --- Finanzas y pobreza
    Ind("PCT_APSB", "% de inversión en agua potable y saneamiento", "%", "NUM", 2, [("Finanzas públicas", "Porcentaje de inversión - Agua potable y saneamiento básico (sin incluir proyectos de vis)")]),
    Ind("SGP_APSB", "Inversión en agua potable y saneamiento", "Mill $", "NUM", 2, [("Finanzas públicas", "Agua potable"), ("Finanzas públicas", "Inversión - Agua potable y saneamiento básico (sin incluir proyectos de vis)")]),
    Ind("IPM", "Índice de Pobreza Multidimensional", "% ×100", "NUM", 2, [("Pobreza", "Índice de pobreza multidimensional - IPM"), ("Pobreza", "indice de pobreza multidimensional - IPM (Censo)")]),
    # --- Cultivos: el tonelaje va en Dato Numérico y el nombre del cultivo en Dato Cualitativo
    Ind("CULT_T1", "1er cultivo transitorio", "Toneladas", "NUM", 2, [("Economía", "Primer cultivo transitorio en términos de toneladas producidas")]),
    Ind("CULT_T2", "2º cultivo transitorio", "Toneladas", "NUM", 2, [("Economía", "Segundo cultivo transitorio en términos de toneladas producidas")]),
    Ind("CULT_T3", "3er cultivo transitorio", "Toneladas", "NUM", 2, [("Economía", "Tercer cultivo transitorio en términos de toneladas producidas")]),
    Ind("CULT_TO", "Otros cultivos transitorios", "Toneladas", "NUM", 2, [("Economía", "Toneladas producidas por otros cultivos transitorios")]),
    Ind("CULT_P1", "1er cultivo permanente", "Toneladas", "NUM", 2, [("Economía", "Primer cultivo permanente en términos de toneladas producidas")]),
    Ind("CULT_P2", "2º cultivo permanente", "Toneladas", "NUM", 2, [("Economía", "Segundo cultivo permanente en términos de toneladas producidas")]),
    Ind("CULT_P3", "3er cultivo permanente", "Toneladas", "NUM", 2, [("Economía", "Tercer cultivo permanente en términos de toneladas producidas")]),
    Ind("CULT_PO", "Otros cultivos permanentes", "Toneladas", "NUM", 2, [("Economía", "Toneladas producidas por otros cultivos permanentes")]),
    Ind("NOM_T1", "Nombre 1er cultivo transitorio", "Texto", "TXT", 0, [("Economía", "Primer cultivo transitorio en términos de toneladas producidas")]),
    Ind("NOM_T2", "Nombre 2º cultivo transitorio", "Texto", "TXT", 0, [("Economía", "Segundo cultivo transitorio en términos de toneladas producidas")]),
    Ind("NOM_T3", "Nombre 3er cultivo transitorio", "Texto", "TXT", 0, [("Economía", "Tercer cultivo transitorio en términos de toneladas producidas")]),
    Ind("NOM_P1", "Nombre 1er cultivo permanente", "Texto", "TXT", 0, [("Economía", "Primer cultivo permanente en términos de toneladas producidas")]),
    Ind("NOM_P2", "Nombre 2º cultivo permanente", "Texto", "TXT", 0, [("Economía", "Segundo cultivo permanente en términos de toneladas producidas")]),
    Ind("NOM_P3", "Nombre 3er cultivo permanente", "Texto", "TXT", 0, [("Economía", "Tercer cultivo permanente en términos de toneladas producidas")]),
]
```

---

## Apéndice B — Las 52 gráficas

Formas disponibles en `graficas.py` (cinco primitivas, nada más):

| Forma | Cuándo |
|---|---|
| `columnas` | magnitud comparada entre entidades, 1 serie |
| `columnas_agrupadas` | 2-6 series **de la misma unidad** |
| `columnas_apiladas` | composición de un total |
| `barras_ranking` | ordenar entidades de menor a mayor (barras horizontales) |
| `torta` | composición de un total, máximo 7 porciones |
| `lineas` | evolución en el tiempo |
| `panel` | small multiples: varios mini-paneles con escalas propias |

### Sección `poblacion` — 15

| # | id | Forma | Series |
|---|---|---|---|
| 1 | `pob_total` | columnas | `POB_TOTAL` |
| 2 | `pob_pct_total` | columnas | `PCT_DEL_TOTAL` |
| 3 | `densidad` | columnas | `DENSIDAD` |
| 4 | `pob_hombres` | columnas | `POB_H` |
| 5 | `pob_mujeres` | columnas | `POB_M` |
| 6 | `pct_rural` | columnas | `PCT_RURAL` |
| 7 | `afil_subsidiado` | columnas | `AFIL_SUBS` |
| 8 | `afil_contributivo` | columnas | `AFIL_CONTRIB` |
| 9 | `afil_total` | columnas | `TOTAL_AFILIADOS` |
| 10 | `sisbenizados` | columnas | `SISBEN_REG` |
| 11 | `sisben_puntaje` | columnas | `SISBEN_T` |
| 12 | `ipm` | columnas | `IPM` |
| 13 | `dist_sexo` | columnas_agrupadas | `POB_H`, `POB_M` |
| 14 | `dist_urbano_rural` | columnas_agrupadas | `POB_URB`, `POB_RUR` |
| 15 | `regimenes` | columnas_apiladas | `AFIL_SUBS`, `AFIL_CONTRIB`, `AFIL_ESP` |

### Sección `ods1` — 12

| # | id | Forma | Series |
|---|---|---|---|
| 16 | `ods1_pob_torta` | torta | `POB_TOTAL` |
| 17 | `ods1_pct_ranking` | barras_ranking | `PCT_DEL_TOTAL` |
| 18 | `ods1_mujeres_torta` | torta | `POB_M` |
| 19 | `ods1_hombres_torta` | torta | `POB_H` |
| 20 | `ods1_rural_torta` | torta | `POB_RUR` |
| 21 | `ods1_urbana_torta` | torta | `POB_URB` |
| 22 | `ods1_poblacion_comparativo` | columnas_agrupadas | `POB_TOTAL`, `POB_M`, `POB_H`, `POB_RUR`, `POB_URB` |
| 23 | `ods1_sisben_torta` | torta | `SISBEN_REG` |
| 24 | `ods1_contributivo_torta` | torta | `AFIL_CONTRIB` |
| 25 | `ods1_subsidiado_torta` | torta | `AFIL_SUBS` |
| 26 | `ods1_ppna` | columnas | `PPNA` |
| 27 | `ods1_aseguramiento_comparativo` | columnas_agrupadas | `SISBEN_REG`, `AFIL_CONTRIB`, `AFIL_SUBS`, `AFIL_ESP`, `TOTAL_AFILIADOS`, `PPNA` |

### Sección `ods2` — 5

| # | id | Forma | Series |
|---|---|---|---|
| 28 | `ods2_t1_torta` | torta | `CULT_T1` — el título incluye el nombre del cultivo (`NOM_T1`) de la entidad mayor |
| 29 | `ods2_t2_torta` | torta | `CULT_T2` |
| 30 | `ods2_p1_torta` | torta | `CULT_P1` |
| 31 | `ods2_p2_torta` | torta | `CULT_P2` |
| 32 | `ods2_cultivos` | columnas_agrupadas | `CULT_T1`, `CULT_T2`, `CULT_T3`, `CULT_P1`, `CULT_P2` |

### Sección `ods3` — 5

| # | id | Forma | Series |
|---|---|---|---|
| 33 | `ods3_fecundidad` | barras_ranking | `FECUNDIDAD` |
| 34 | `ods3_mort_infantil` | barras_ranking | `MORT_INF` |
| 35 | `ods3_mort_general` | barras_ranking | `MORT_GEN` |
| 36 | `ods3_vacunacion` | barras_ranking + línea de meta en 95 | `VAC_PENTA` |
| 37 | `ods3_panel` | panel 2×2 | `FECUNDIDAD`, `MORT_INF`, `MORT_GEN`, `VAC_PENTA` |

### Sección `ods6` — 10

| # | id | Forma | Series |
|---|---|---|---|
| 38 | `ods6_acueducto_ranking` | barras_ranking | `ACU_REC` |
| 39 | `ods6_alcantarillado_ranking` | barras_ranking | `ALC_REC` |
| 40 | `ods6_acueducto_censo_rec` | columnas_agrupadas | `ACU_CENSO`, `ACU_REC` |
| 41 | `ods6_alcantarillado_censo_rec` | columnas_agrupadas | `ALC_CENSO`, `ALC_REC` |
| 42 | `ods6_acueducto_urb_rur` | columnas_agrupadas | `ACU_URB`, `ACU_RUR` |
| 43 | `ods6_alcantarillado_urb_rur` | columnas_agrupadas | `ALC_URB`, `ALC_RUR` |
| 44 | `ods6_aseo` | columnas_agrupadas | `ASEO_REC`, `ASEO_URB`, `ASEO_RUR` |
| 45 | `ods6_energia_internet` | columnas_agrupadas | `ENER_RUR`, `BANDA` |
| 46 | `ods6_deficit_vivienda` | columnas_agrupadas | `DEF_CUAL`, `DEF_CUANT` |
| 47 | `ods6_inversion_apsb` | lineas | `PCT_APSB`, una línea por entidad, los 10 años más recientes con dato |

La #47 necesita la **serie temporal**, no el valor resuelto. `resolucion.py` debe
exponer `serie_temporal(indicador_id, entidad) -> dict[int, float]`. El eje X va
anclado al último año **con dato** del indicador menos nueve, no al año de corte:
la inversión en APSB suele terminar en 2017, y anclar al corte deja la gráfica
vacía.

### Sección `salud_publica` — 5

| # | id | Forma | Series |
|---|---|---|---|
| 48 | `sp_vacunacion` | columnas + línea de meta en 95 | `VAC_PENTA` |
| 49 | `sp_vif` | columnas | `T_VIF` |
| 50 | `sp_mort_infantil` | columnas | `MORT_INF` |
| 51 | `sp_fecundidad` | columnas | `FECUNDIDAD` |
| 52 | `sp_panel` | panel 2×3 | `FECUNDIDAD`, `MORT_MAT`, `MORT_INF`, `MORT_GEN`, `VAC_PENTA`, `T_VIF` |

**Total: 15 + 12 + 5 + 5 + 10 + 5 = 52**

---

## Apéndice C — Diferencias deliberadas con el Excel original

El original tiene 79 gráficas. De las 52 que sí puede alimentar TerriData, cinco
se rediseñaron porque tal como estaban engañan al lector. Deja esto anotado en el
`README.md`.

| Original | Aquí | Por qué |
|---|---|---|
| Dos tortas de "Población Total" (una por tabla) y una de "%" | Una torta de población, un ranking de `%` y una columna de `PPNA` | Tres gráficas mostraban exactamente la misma distribución |
| Tortas de fecundidad, mortalidad y vacunación (ODS 3) | Barras ordenadas | Una tasa no es parte de un total: sumar las tasas de siete municipios no significa nada, y eso es justo lo que muestra una torta |
| Barras agrupadas mezclando `%` con personas | `%` fuera de esas gráficas | Un solo eje Y con dos escalas distintas deforma la comparación |
| "Comparativo de indicadores de salud" con tasas de unidades distintas en un eje | `panel` de small multiples | Cada indicador conserva su escala y sigue siendo comparable entre municipios |
| Línea de inversión en APSB anclada a 2011-2017 fijo | Anclada al último año con dato | Con otro municipio o periodo, el rango fijo deja la gráfica vacía |

Además, tres correcciones de datos respecto al original:

1. La hoja `SALUD PUBLICA` del Excel alimentaba sus gráficas con municipios del
   Huila mientras su tabla mostraba los de Norte de Santander. Aquí todo sale de
   la misma fuente.
2. Los bloques auxiliares de `DATOS_GRAFICOS` tenían el encabezado corrido una
   fila, así que cada municipio mostraba los datos del siguiente.
3. Las cifras de cultivos del original no coinciden con las de TerriData 2016.
   Aquí manda TerriData.
