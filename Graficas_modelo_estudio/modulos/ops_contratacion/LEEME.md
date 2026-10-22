# Análisis de contratación OPS

> Este módulo forma parte del proyecto unificado. Lo normal es correrlo desde la
> raíz con `python ejecutar.py ops` (ver el [README principal](../../README.md));
> los datos se leen de `DATA/` y los resultados quedan en `SALIDAS/`.

Pipeline reutilizable: apuntas a una carpeta con los CSV del reporte de
contratación externa y produce el consolidado normalizado, tablas y gráficas.

## Uso

```bash
python analisis_ops.py      # lee DATA/SIHO/<HOSPITAL>/Consultas_Detalladas/Reporte_Contratacion_Externa_desde_2020
                            # y escribe SALIDAS/ops_contratacion
python analisis_ops.py --carpeta "OPS 2026" --salida resultados
```

Requiere `pandas` y `matplotlib` (`requirements.txt` de la raíz).

## Qué hace

**1. Detecta los archivos.** Recorre la carpeta completa (incluidas subcarpetas)
buscando CSV que traigan las columnas del reporte. Los que no las tengan se
omiten y se avisa por consola. No depende de cómo se llamen los archivos ni de
cómo estén organizadas las subcarpetas.

**2. Elige el consolidado de cada año.** Los reportes trimestrales son
*acumulativos*: el de julio-sep ya contiene enero-sep, y el de octubre-dic
contiene el año completo. Usar los cuatro archivos contaría cada contrato hasta
cuatro veces. El script se queda, por año, con el archivo que cubre más meses —
en la práctica el de octubre-dic, pero la decisión se toma leyendo las fechas,
no el nombre del archivo, así que sigue funcionando si un año llega incompleto.

**3. Normaliza los nombres.** La cédula es el identificador confiable, así que
agrupa por documento y elige un nombre canónico por persona:

- unifica variantes ortográficas (`RUBY`/`RUBI`, `VELOSA`/`VELOZA`, `LEIDA`/`LEYDA`)
- prefiere la versión más completa cuando el nombre viene truncado
  (`ZULMA VANEGAS` → `Zulma Claritza Vanegas Medina`)
- corrige la caja y conserva la Ñ y las partículas (`Miguel Angel de la Hoz`)
- reordena a `NOMBRES APELLIDOS` cuando el registro viene con los apellidos
  primero, usando léxicos de nombres de pila y apellidos comunes en Colombia

Las razones sociales (sindicatos, cooperativas) se detectan por el propio texto
y solo se les corrige la caja. Nota: la columna `clase_persona` **no** sirve
para eso — dice "Jurídica" en el 91% de los contratos porque describe el
vehículo de contratación, no al contratista.

Si en el futuro aparecen nombres de pila o apellidos nuevos que el script no
reconozca, se agregan a las listas `NOMBRES_PILA` y `APELLIDOS_COMUNES` en
[normalizar_nombres.py](normalizar_nombres.py).

## Salidas

| Archivo | Contenido |
|---|---|
| `ops_consolidado_normalizado.csv` | todos los contratos con `nombre_normalizado`, `documento`, `anio` y campos numéricos ya parseados |
| `auditoria_nombres.csv` | cada persona con más de una grafía y sus variantes originales |
| `contratistas_consolidado.csv` | una fila por contratista: contratos, valor total, años activos |
| `resumen_por_anio.csv` | contratos, valor, personas, valor promedio |
| `valor_por_area_anio.csv`, `contratos_por_perfil_anio.csv` | tablas cruzadas |
| `01`–`08` `.png` | las gráficas |

### La columna `revisar` de la auditoría

Marca con `SI` los casos donde una de las variantes no comparte ningún apellido
con el nombre elegido — casi siempre significa que **se digitó el nombre de una
persona bajo la cédula de otra**. Son errores de la fuente que el script no
puede resolver solo; conviene revisarlos contra el soporte del contrato.
