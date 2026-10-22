# Generación de gráficas — SIHO, TerriData y afiliación

Un solo comando genera todas las gráficas a partir de tres fuentes de datos:

| Fuente | Dónde se pone | Módulos que la usan |
|---|---|---|
| Reportes del **SIHO** (estructura de `SJDC_SIHO`) | `DATA/SIHO/<HOSPITAL>_SIHO/` | `ops`, `produccion`, `productividad` |
| Extracciones **TerriData** (`.txt`) | `DATA/TERRIDATA/` | `terridata`, `pss` |
| **Cifras de afiliación** de [MinSalud](https://www.minsalud.gov.co/Proteccion-Social/Paginas/cifras-aseguramiento-salud.aspx) (`.xlsx`) | `DATA/AFILIACION/` | `pss` |

El detalle de cada carpeta está en [DATA/README.md](DATA/README.md).

## Uso

En Windows, doble clic en **`iniciar.bat`**. La primera vez crea el entorno
virtual (`.venv`) e instala las dependencias; después corre todos los módulos.

Desde una terminal:

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt

python ejecutar.py                    # todos los módulos
python ejecutar.py ops productividad  # solo algunos
python ejecutar.py --siho SJDC_SIHO   # si hay varios hospitales en DATA/SIHO
python ejecutar.py --listar           # módulos, datos que usa y salida de cada uno
python ejecutar.py app                # app web interactiva de contratación OPS
```

`iniciar.bat` acepta los mismos argumentos (`iniciar.bat app`, `iniciar.bat ops`).

Si falta la fuente de un módulo, ese módulo se omite con un aviso y los demás
siguen. Al final se imprime un resumen con el estado de cada uno.

## Módulos

| Módulo | Qué genera | Salida |
|---|---|---|
| `ops` | Consolidado de contratación OPS con nombres normalizados, auditoría de identidad y 8 gráficas | `SALIDAS/ops_contratacion/` |
| `produccion` | Una gráfica SVG por concepto de producción (variación anual y promedio) y la tabla Excel por año | `SALIDAS/produccion/` |
| `productividad` | Indicadores de productividad frente a capacidad instalada y talento humano, con informe HTML | `SALIDAS/productividad/` |
| `terridata` | Las 52 gráficas del análisis comparativo municipal y su dashboard | `SALIDAS/terridata/` |
| `pss` | Los 32 gráficos del Modelo PSS (TerriData + afiliación) y su dashboard | `SALIDAS/terridata_pss/` |

La documentación de cada módulo está en su carpeta:
[ops_contratacion](modulos/ops_contratacion/LEEME.md) ·
[productividad](modulos/productividad/README.md) ·
[terridata](modulos/terridata/README.md).

## Estructura

```
├── ejecutar.py          punto de entrada único
├── iniciar.bat          arranque en un clic (Windows)
├── requirements.txt     dependencias de todos los módulos
├── DATA/                fuentes de datos (no se suben a git)
├── SALIDAS/             resultados (no se suben a git)
└── modulos/
    ├── ops_contratacion/
    ├── produccion/
    ├── productividad/
    └── terridata/
```

`DATA/`, `SALIDAS/`, las imágenes, los Excel y el entorno virtual están en
`.gitignore`.

## Pruebas

```bash
cd modulos/terridata && python -m pytest
cd modulos/productividad && python -m pytest
```

Las pruebas de productividad comparan contra valores calculados a mano con los
reportes del ESE Hospital San Antonio; con los datos de otro hospital no
coinciden, y es lo esperado.
