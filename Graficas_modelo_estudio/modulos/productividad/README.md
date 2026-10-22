# Productividad frente a capacidad instalada y talento humano

> Este módulo forma parte del proyecto unificado. Lo normal es correrlo desde la
> raíz con `python ejecutar.py productividad` (ver el [README principal](../../README.md));
> los datos se leen de `DATA/` y los resultados quedan en `SALIDAS/`.

Proyecto en Python que lee los reportes crudos del hospital (tal como se
descargan, sin organizarlos a mano), calcula los indicadores de productividad
y genera las gráficas (PNG y SVG) y un informe HTML con todas las tablas.

Sirve para cualquier hospital que entregue los reportes con la misma
estructura.

---

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate        # en Windows:  .venv\Scripts\activate
pip install -r ../../requirements.txt
```

## Uso

```bash
python main.py
```

Y en `SALIDAS/productividad/` aparece:

```
SALIDAS/productividad/
├── informe.html          ← ábralo en el navegador
├── graficas/             ← una .png y una .svg por gráfica
├── tablas/               ← el cálculo de cada indicador, en CSV
└── datos_consolidados/   ← lo que el programa leyó de los reportes, por año
```

Para leer los datos de otra carpeta (por ejemplo, otro hospital) o escribir en
otro lado:

```bash
python main.py --datos ruta/a/datos_otro_hospital --salida ruta/de/resultados
```

---

## Los datos de entrada

Copie la carpeta del hospital en `DATA/SIHO/` **tal como se descarga** (estructura
de SJDC_SIHO). De ella se usa esto:

```
DATA/SIHO/SJDC_SIHO/
├── Formularios_Anuales/
│   ├── 2020/
│   │   ├── Capacidad_Instalada/Capacidad_Instalada_2020.csv   ← se usa
│   │   ├── Produccion/Produccion_2020.csv                     ← se usa
│   │   ├── Recursos_Humanos/Recursos_Humanos_2020.csv         ← se usa
│   │   └── Balance_General/, Gastos/, Ingresos/, ...          ← se ignoran
│   ├── 2021/
│   └── ...
└── Consultas_Detalladas/
    └── Reporte_Contratacion_Externa_desde_2020/
        ├── 2020/
        │   ├── Reporte_Contratacion_Externa_desde_2020_2020_octubre-dic.csv   ← se usa
        │   └── ..._enero-mar.csv, ..._abril-jun.csv, ..._julio-sep.csv       ← se ignoran
        ├── ...
        └── 2025/
```

De cada reporte solo se usa esto:

| reporte | columnas que se leen | para qué |
|---|---|---|
| `Capacidad_Instalada` | `concepto`, `vigencia_actual` | camas, consultorios, quirófanos, mesas de partos, unidades de odontología |
| `Produccion` | `concepto`, `total` | consultas, partos, cirugías, días cama, sesiones y la producción total |
| `Recursos_Humanos` | `cargTipo`, `numero_cargos` | cargos de planta ocupados: APOYO, OPERATIVO y TOTAL |
| `OPS` | `nombre_area`, `numero_meses` | contratos y meses contratados: operativos (área "Operativo Asistencial") y totales |

- El año de los formularios sale del nombre de la carpeta (`2020`, `2021`...).
- El año de cada reporte OPS sale del último año que aparece en el nombre del
  archivo (`..._2020_2025_octubre-dic.csv` es 2025). Los reportes pueden ir en
  subcarpetas por año o sueltos. **Solo se lee el de octubre-dic** de cada año
  (el que trae "octubre-dic" en el nombre), que trae **todos** los contratos
  del año; los demás trimestres se ignoran solos. Se cuentan todas sus filas,
  sin filtrar por fecha de inicio.
- Los nombres de los archivos .csv dentro de cada carpeta no importan.
- Las demás columnas (nombres, cédulas, valores, etc.) no se usan.

### Agregar un año

Agregue la carpeta `Formularios_Anuales/2026/` y la carpeta `Consultas_Detalladas/Reporte_Contratacion_Externa_desde_2020/2026/` con sus reportes, y
vuelva a ejecutar `python main.py`. Los años se detectan solos. Un indicador
solo muestra los años en que están todos los reportes que necesita.

> Si un reporte no trae una columna o un concepto que algún indicador
> necesita, el programa se detiene y le dice cuál falta y en qué archivo, en
> lugar de calcular mal en silencio. Las tildes, mayúsculas y espacios de más
> en los conceptos no afectan.

Si otro hospital descarga los reportes con nombres de columna distintos,
se ajustan en `prodlib/config.py` (`FORMULARIOS`, `RECURSOS_HUMANOS`, `OPS`).

---

## Los parámetros de cálculo

Están en `prodlib/config.py`, en un solo diccionario. Son supuestos, no datos
medidos, y por eso se ven también en el encabezado del informe:

| parámetro | valor | para qué |
|---|---|---|
| `DIAS_ANIO` | 365 | consultorios de urgencias, cirugías por día |
| `SEMANAS_ANIO` | 52 | cupos de observación por semana |
| `DIAS_HABILES` | 260 | consulta externa y odontología (5 días x 52 semanas) |
| `MESES_ANIO` | 12 | convierte las personas de nómina en meses contratados |

---

## Agregar un indicador

Todo indicador se declara una sola vez, en la lista `INDICADORES` de
`prodlib/indicadores.py`. El cálculo, la tabla, las dos gráficas y la sección
del informe salen solos:

```python
Indicador(
    clave="laboratorio",
    grupo=CAPACIDAD,
    titulo="Laboratorio clínico",
    descripcion="Exámenes procesados por día hábil.",
    fuentes=("capacidad", "produccion"),
    columnas=(
        Columna("Exámenes de laboratorio", de("produccion", "Exámenes de laboratorio")),
        Columna("Días hábiles", calculo(lambda t, p: t["Exámenes de laboratorio"] * 0 + p["DIAS_HABILES"])),
        Columna("Exámenes por día", razon("Exámenes de laboratorio", "Días hábiles"), "{:,.2f}"),
    ),
    indicador="Exámenes por día",
    eje_y="Exámenes / día",
    volumen=("Exámenes de laboratorio",),
    eje_y_volumen="Exámenes",
)
```

Constructores disponibles para el origen de una columna:

| función | qué hace |
|---|---|
| `de(fuente, concepto)` | trae tal cual una fila del CSV |
| `suma(fuente, *conceptos)` | suma varias filas del mismo CSV |
| `total(fuente)` | suma todas las filas (producción total del año) |
| `calculo(fn)` | calcula con las columnas ya resueltas de la misma tabla |
| `razon(num, den)` | divide dos columnas, protegido contra el cero |

---

## Estructura

```
productividad/
├── main.py                  punto de entrada
├── prodlib/
│   ├── config.py            parámetros, rutas, columnas de los reportes y paleta
│   ├── carga.py             lectura y consolidación de los reportes crudos
│   ├── indicadores.py       definición y cálculo de los indicadores
│   ├── graficas.py          PNG y SVG con matplotlib
│   ├── informe.py           informe HTML
│   └── cli.py               orquestación y argumentos de línea de comandos
└── tests/
    └── test_indicadores.py  compara contra valores calculados a mano
```

## Verificación

```bash
python tests/test_indicadores.py     # o:  python -m pytest -q
```

Compara varios indicadores contra cuentas hechas a mano con los reportes de
`DATA/SIHO/` y revisa la consolidación de nómina y OPS. Si cambia los datos por
los de otro hospital, estas pruebas dejarán de coincidir: es lo esperado.

---

## Sobre las gráficas

- Un solo eje de valores por gráfica; nunca dos escalas en el mismo dibujo.
- Los colores se asignan en orden fijo (serie 1 azul, serie 2 naranja) con una
  paleta verificada para daltonismo; el color nunca es la única señal, siempre
  hay leyenda o rótulo.
- Cada gráfica se guarda en PNG (para pegar en un documento) y en SVG (para
  imprimir o escalar sin perder nitidez). El informe HTML usa los SVG.

## Fuente de los datos

Las cifras salen directamente de los reportes crudos de `DATA/SIHO/` y no se
modifican. En `SALIDAS/productividad/datos_consolidados/` queda lo que el programa leyó de
cada reporte, para revisarlo a mano.
