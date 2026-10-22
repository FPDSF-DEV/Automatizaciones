# terridata-graficas

> Este módulo forma parte del proyecto unificado. Lo normal es correrlo desde la
> raíz con `python ejecutar.py terridata pss` (ver el [README principal](../../README.md));
> los datos se leen de `DATA/` y los resultados quedan en `SALIDAS/`.

Convierte las extracciones `.txt` de **TerriData (DNP)** en gráficas (PNG + SVG) y
un dashboard HTML de una sola página. Trae dos entregables:

| Comando | Qué genera |
|---|---|
| `python -m terridata` | Las **52 gráficas** del análisis comparativo municipal |
| `python -m terridata.pss` | Los **32 gráficos** del Inventario del Modelo PSS (ESE Hospital San Antonio, Gigante) |

El segundo cruza TerriData con el Excel de afiliación al SGSSS de **ADRES**; está
documentado [más abajo](#modelo-pss--los-32-gráficos-del-inventario).

```bash
python -m terridata --datos ../../DATA/TERRIDATA --salida ../../SALIDAS/terridata
```

```
Entidades: 7 (CÁCOTA, CHITAGÁ, CUCUTILLA, MUTISCUA, PAMPLONA, PAMPLONITA, SILOS)
Departamento: Norte de Santander | Filas leídas: 12.495 | Año de corte: 2026
Indicadores resueltos: 55/59
Gráficas generadas: 52  (png 52 · svg 52)
Dashboard: SALIDAS/terridata/dashboard.html
```

---

## Instalación

Requiere **Python 3.10 o superior**. `matplotlib` para las gráficas y `openpyxl`
para leer el Excel de afiliación; el parseo de los `.txt` va con la librería
estándar.

```bash
pip install -r ../../requirements.txt
```

## Uso

1. Descarga de TerriData los `.txt` de los municipios que quieras comparar y
   ponlos en `DATA/TERRIDATA/` (en la raíz del proyecto). Puede ser un archivo por municipio o uno con varios
   dentro: ambos casos funcionan, y las filas repetidas entre archivos se
   deduplican solas.
2. Corre el comando.
3. Abre `SALIDAS/terridata/dashboard.html` con doble clic. No necesita servidor ni internet.

### Opciones

| Opción | Qué hace | Por defecto |
|---|---|---|
| `--datos RUTA` | carpeta con los `.txt` | `DATA/TERRIDATA` |
| `--salida RUTA` | carpeta de salida | `SALIDAS/terridata` |
| `--anio-corte N` | ignora los datos posteriores a ese año | el año actual |
| `--titulo TEXTO` | título del análisis | `Análisis comparativo TerriData` |
| `--secciones LISTA` | `poblacion, ods1, ods2, ods3, ods6, salud_publica` | todas |
| `--formatos LISTA` | `png,svg,html` | los tres |
| `--tema claro\|oscuro` | paleta de renderizado | `claro` |
| `--orden-entidades aparicion\|nombre` | orden de los municipios | `aparicion` |
| `--verboso` | imprime la matriz resuelta y cómo se resolvió cada alias | apagado |

### Ejemplos

```bash
# Todo, con el año de corte por defecto
python -m terridata

# Solo agua y saneamiento, en SVG, para meter en un informe
python -m terridata --secciones ods6 --formatos svg

# Cómo se veía el panorama con datos hasta 2020
python -m terridata --anio-corte 2020 --titulo "Línea base 2020"

# Para presentar en pantalla oscura
python -m terridata --tema oscuro

# Ver qué indicador resolvió cada alias y con qué año
python -m terridata --verboso
```

### Códigos de salida

| Código | Significado |
|---|---|
| `0` | todo bien |
| `1` | error de entrada: la carpeta no existe, está vacía o ningún archivo es válido |
| `2` | se generó, pero faltaron indicadores (el dashboard los lista al final) |

---

## Qué hace por dentro

```
lectura.py    descubre y parsea los .txt  (separador |, 13 columnas, UTF-8 con BOM)
catalogo.py   el catálogo de 59 indicadores, con sus alias
resolucion.py elige el alias presente y el dato más reciente sin pasar del corte
derivados.py  porcentajes, brechas y totales que TerriData no publica
estilo.py     paleta, tipografía y las specs de marca
graficas.py   siete primitivas de dibujo
catalogo_graficas.py  las 52 gráficas
dashboard.py  el HTML autocontenido

pss/afiliacion.py    lee el Excel de ADRES (columnas por nombre, no por posición)
pss/ambito.py        departamento real o agregado del área, y los quinquenios
pss/catalogo_pss.py  los indicadores del Modelo PSS y el acceso a los datos
pss/graficos_pss.py  los 32 gráficos del inventario
pss/__main__.py      el comando `python -m terridata.pss`
```

Tres cosas que conviene saber porque cambian los números:

* **Formato numérico colombiano.** `22.395,00` es veintidós mil, no veintidós. El
  parseo nunca usa `float()` directo.
* **Año de corte.** TerriData publica proyecciones de población hasta 2042. Sin
  tope, la densidad poblacional saldría proyectada a 2042. Por eso cada indicador
  toma el año más alto que no pase del corte, y ese año aparece en el subtítulo de
  la gráfica.
* **Hay dos series de población que no coinciden.** `Censo 2005 y proyecciones
  DANE` y `Demografía y población` dan cifras distintas para el mismo municipio y
  el mismo año. Manda la primera, porque es internamente coherente
  (urbana + rural = total, y hombres + mujeres = total). Las dos nunca se mezclan
  en una misma gráfica ni en un mismo cálculo.

Además, el DNP **renombra indicadores entre versiones**. El catálogo trae hasta
tres nombres por indicador y usa el primero que exista en los datos cargados:

| Nombre antiguo | Nombre nuevo |
|---|---|
| `Penetración de banda ancha` | `Penetración de internet fijo en los hogares` / `Penetración de acceso fijo a Internet` |
| `Déficit cualitativo de vivienda` | `Déficit cualitativo de vivienda (Censo)` |
| `Índice de pobreza multidimensional - IPM` | `indice de pobreza multidimensional - IPM (Censo)` (sin tilde) |
| `Afiliados al régimen subsidado` (errata del DNP) | `Afiliados al régimen subsidiado` |

Si ningún nombre aparece, el indicador queda **no disponible**: sus gráficas se
omiten con un aviso y quedan listadas al final del dashboard. Nunca se cae.

---

## Lo que este proyecto NO hace

**27 gráficas del Excel original quedan fuera** porque no salen de TerriData:
distribución por EPS y cifras de afiliación de corte (reporte DANE/ADRES), red de
prestadores (REPS) y segmentación departamental por nodos.

**Indicadores que TerriData no publica a nivel municipal** — y que por tanto no se
pueden graficar aquí:

| | |
|---|---|
| analfabetismo | matrícula oficial |
| IRCA | médicos y camas por 10.000 habitantes |
| desnutrición crónica | pobreza monetaria |
| GINI | desempleo |
| TGP | informalidad |
| PIB municipal | área sembrada |
| hectáreas de amenaza por inundación | vigencia del POT |

**Indicadores descontinuados**: Índice de Desempeño Integral, IGA y Transparencia
por Colombia. El DNP los reemplazó por la Medición de Desempeño Municipal (MDM).

---

## Diferencias deliberadas con el Excel original

El original tenía 79 gráficas. De las 52 que TerriData sí puede alimentar, cinco
se rediseñaron porque tal como estaban engañan al lector:

| Original | Aquí | Por qué |
|---|---|---|
| Dos tortas de "Población total" y una de "%" | Una torta, un ranking de `%` y una columna de PPNA | Tres gráficas mostraban la misma distribución |
| Tortas de fecundidad, mortalidad y vacunación | Barras ordenadas | Una tasa no es parte de un total: sumar las tasas de siete municipios no significa nada |
| Barras agrupadas mezclando `%` con personas | El `%` sale de esas gráficas | Un eje Y con dos escalas distintas deforma la comparación |
| "Comparativo de indicadores de salud" con tasas de unidades distintas en un eje | Small multiples | Cada indicador conserva su escala y sigue siendo comparable entre municipios |
| Línea de inversión en APSB fija a 2011-2017 | Anclada al último año con dato | Con otro municipio o periodo, el rango fijo dejaba la gráfica vacía |

Y tres correcciones de datos:

1. La hoja `SALUD PUBLICA` del Excel alimentaba sus gráficas con municipios del
   Huila mientras su tabla mostraba los de Norte de Santander. Aquí todo sale de
   la misma fuente.
2. Los bloques auxiliares de `DATOS_GRAFICOS` tenían el encabezado corrido una
   fila: cada municipio mostraba los datos del siguiente.
3. Las cifras de cultivos del original no coinciden con las de TerriData 2016.
   Aquí manda TerriData.

---

## Diseño de las gráficas

Todo vive en `estilo.py`. Las reglas que no se rompen:

* Paleta categórica de ocho colores en orden fijo, **nunca cíclica**. Ninguna
  gráfica pasa de ocho series.
* Barras de máximo 24 px de grosor con el extremo del dato redondeado 4 px. El
  aire que sobra es parte del diseño.
* Huecos de 2 px entre marcas, hechos con geometría y no con contorno.
* **Nunca dos ejes Y.** Dos magnitudes de escala distinta son dos gráficas.
* Una sola serie no lleva leyenda; dos o más, siempre.
* **Todas las barras llevan su cifra.** Si el número no cabe acostado en el ancho
  de la barra, todas las etiquetas de esa gráfica se giran a vertical —mezclar
  acostadas y giradas se ve desordenado— y el eje reserva el aire exacto que
  necesitan. La única excepción son los segmentos de una barra apilada que son
  físicamente más delgados que un renglón de texto: ahí la cifra queda en la
  tabla del dashboard, porque forzarla dejaría números encimados.
* Ninguna etiqueta se recorta: se mide el texto antes de dibujarlo y el rango del
  eje se calcula para que quepa.
* Eje en formato colombiano: `1.000`, `20.000`.

Los números de las specs están en píxeles de diseño (96 dpi). Como los PNG salen a
200 dpi, `estilo.py` los convierte a pulgadas: así una barra mide lo mismo en el
PNG y en el SVG.

---

## Modelo PSS — los 32 gráficos del inventario

Reproduce el inventario del *Modelo de Prestación de Servicios de Salud de la ESE
Hospital San Antonio, Gigante (Huila)*: 32 gráficos sobre los 8 municipios del
área de influencia (Agrado, Altamira, Garzón, Gigante, Guadalupe, Pital, Suaza y
Tarqui).

```bash
python -m terridata.pss --excel "../../DATA/AFILIACION/CIFRAS JULIO-2026.xlsx" --anio 2026
```

Si no le pasas `--excel`, busca solo el `.xlsx` más reciente de `DATA/AFILIACION/`.

| Opción | Qué hace | Por defecto |
|---|---|---|
| `--datos RUTA` | carpeta con los `.txt` de TerriData | `DATA/TERRIDATA` |
| `--excel RUTA` | Excel de afiliación de ADRES | el más reciente de `DATA/AFILIACION` |
| `--salida RUTA` | carpeta de salida | `SALIDAS/terridata_pss` |
| `--anio N` | año de referencia de las proyecciones | el año actual |
| `--graficos LISTA` | números a generar, p. ej. `1,13,16` | los 32 |
| `--formatos`, `--tema`, `--verboso` | igual que en el comando principal | |

### De dónde sale cada grupo de gráficos

| # | Grupo | Fuente |
|---|---|---|
| 1-7 | Contexto territorial y de salud | TerriData |
| 8 | Composición del SGSSS del departamento | ADRES |
| 9-12 | Cobertura, brecha, población vs. afiliados y subsidiados sin SISBÉN IV | ADRES |
| 13-15 | Población total, por sexo y urbano/rural de los 8 municipios | TerriData |
| 16-32 | ODS 1 a 17 | TerriData |

**La afiliación no está en TerriData.** Las cifras de corte (contributivo,
subsidiado, excepción, población sin afiliar y subsidiados sin SISBÉN IV) salen
del Excel de ADRES. El lector ubica las columnas **por su nombre**, no por
posición, para que siga funcionando cuando cambie el corte mensual.

### Tres cosas que conviene saber

* **Los gráficos 1 a 7 son del departamento.** Si entre los `.txt` no hay una
  extracción del Huila, se arman con el **agregado del área de influencia**:
  conteos sumados y tasas promediadas ponderando por población. El título y el
  pie lo dicen, y el dashboard lo advierte. Para obtener las cifras
  departamentales de verdad, descarga de TerriData la extracción del Huila y
  ponla en la misma carpeta.
* **La pirámide poblacional puede quedar en un año anterior al pedido.** En las
  extracciones municipales del Huila, la serie masculina por quinquenios solo
  trae 2041-2042, mientras la femenina va de 2018 a 2042. Mezclar sexos de años
  distintos daría una pirámide falsa, así que se usa el año más reciente con los
  17 grupos de **ambos** sexos completos — hoy, 2019 (serie del censo).
* **La población total proyectada se arma sumando hombres y mujeres.** TerriData
  no publica "Población total" en la serie de proyecciones; sí las dos series por
  sexo. La suma reproduce exactamente las cifras del documento (Gigante 2026 =
  11.480 + 11.873 = 23.353). El resto rural se calcula como total menos cabecera,
  porque la "Población rural" directa solo existe en la serie del censo de 2019 y
  mezclarla con la cabecera de 2026 no cuadraría.

### Dos indicadores que se reemplazaron

El documento original usa dos indicadores que **no vienen** en las extracciones
de TerriData cargadas. Se sustituyeron por el más cercano disponible, y tanto el
subtítulo del gráfico como el dashboard lo dicen:

| # | Indicador del documento | Indicador usado |
|---|---|---|
| 26 (ODS 11) | Índice de Calidad de Vida Municipal (v2.0) | Índice de Sostenibilidad (ICM) |
| 27 (ODS 12) | Índice de circularidad ambiental | Índice de Cuidado ambiental (ICM) |

### Diferencias con las imágenes del documento original

* **El gráfico 8 trae las cifras del departamento.** En el documento, ese gráfico
  está rotulado "Departamento Huila" pero muestra los números de Gigante
  (19.153 / 3.706 / 661). Aquí sale del Excel de ADRES con las cifras reales del
  Huila: 70,6 % subsidiado, 27,0 % contributivo y 2,4 % de excepción.
* **Los años se toman de los datos, no del rótulo.** Cada gráfico usa el año que
  cita el documento y, si un municipio no lo tiene, el más reciente anterior; el
  subtítulo siempre muestra el año o el rango real. En el ODS 8, por ejemplo, las
  cifras que el documento fecha en 2019 son de 2015 en TerriData.
* **El diseño es el del sistema de este proyecto**, no el de las capturas: una
  sola serie va en un color, las metas van como categoría o línea de referencia y
  no se usan rojo/verde como colores de serie.

---

## Pruebas

```bash
python -m pytest
```

Cubren el parseo del formato numérico colombiano, la resolución de alias, el año
de corte, el promediado de filas duplicadas, los derivados con operandos
faltantes y las reglas duras de diseño (sin dos ejes Y, sin leyenda de una sola
serie, tope de grosor de barra, agrupación en "Otros" de la torta).

Para el Modelo PSS, además: la lectura del Excel de ADRES con las columnas
ubicadas por nombre, el agregado del ámbito con tasas ponderadas, la regla de la
pirámide (los dos sexos del mismo año) y la coherencia entre cabecera, resto y
población total.

El fixture `tests/fixtures/mini_terridata.txt` está hecho a mano con dos
municipios del Huila y reproduce a propósito las trampas del formato real: filas
duplicadas en subcategorías distintas, las dos series de población, proyecciones a
2042, cultivos con dato numérico y cualitativo a la vez, y un indicador que solo
existe con su nombre nuevo.
