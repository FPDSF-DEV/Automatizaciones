# DATA — fuentes de datos

Todo lo que hay aquí está en `.gitignore`: los datos nunca se suben al
repositorio. Solo se versionan este README y las carpetas vacías.

```
DATA/
├── SIHO/
│   └── SJDC_SIHO/                ← la carpeta del hospital, tal como se descarga
│       ├── Consultas_Detalladas/
│       │   └── Reporte_Contratacion_Externa_desde_2020/<año>/*.csv
│       ├── Formularios_Anuales/<año>/<formulario>/<formulario>_<año>.csv
│       ├── Formularios_Semestrales/
│       └── Formularios_Trimestrales/
├── TERRIDATA/
│   └── TerriData*.txt            ← extracciones de TerriData (DNP), una o varias
└── AFILIACION/
    └── CIFRAS <MES>-<AÑO>.xlsx   ← cifras de aseguramiento de MinSalud
```

## SIHO

Copie la carpeta del hospital **completa y sin reorganizar** dentro de
`DATA/SIHO/` (por ejemplo `DATA/SIHO/SJDC_SIHO/`). El nombre de la carpeta no
importa; lo que importa es la estructura interna, que es la de SJDC_SIHO.

| Módulo | Lo que lee |
|---|---|
| `ops` | `Consultas_Detalladas/Reporte_Contratacion_Externa_desde_2020/` (los 4 trimestres de cada año) |
| `produccion` | `Formularios_Anuales/<año>/Produccion/` |
| `productividad` | `Formularios_Anuales/<año>/{Capacidad_Instalada, Produccion, Recursos_Humanos}/` y el reporte OPS de octubre-dic |

Los años se detectan solos: al agregar `2026` en las carpetas, aparece en todas
las gráficas.

Si hay más de un hospital en `DATA/SIHO/`, indique cuál con
`python ejecutar.py --siho NOMBRE_CARPETA`.

## TERRIDATA

Los `.txt` descargados de [TerriData](https://terridata.dnp.gov.co/), uno por
municipio o varios en un archivo. Las filas repetidas se deduplican solas. Para
que los gráficos 1 a 7 del Modelo PSS sean departamentales, incluya también la
extracción del departamento.

## AFILIACION

El Excel de cifras de aseguramiento de
[MinSalud](https://www.minsalud.gov.co/Proteccion-Social/Paginas/cifras-aseguramiento-salud.aspx).
Se usa el `.xlsx` más reciente de la carpeta; las columnas se ubican por nombre,
así que sirve el de cualquier corte mensual. Sin este archivo el Modelo PSS se
genera igual, pero omite los gráficos 8 a 12.
