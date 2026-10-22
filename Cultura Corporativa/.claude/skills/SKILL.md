---
name: cultura-corporativa-ese
description: Genera el documento PDF "Primera Fase Ajuste de Cultura Corporativa" de Fundasaberes (misión y visión redactadas; propósitos y valores fijos) para una ESE a partir del CSV de la encuesta al personal. Usar cuando se suba un CSV de Encuesta Cultura Corporativa o se pida ese documento.
---

# Cultura corporativa ESE – Fundasaberes

Entrada: el CSV exportado de Google Forms de la "Encuesta Cultura Corporativa" de una ESE.
Salida: un PDF con el membrete de Fundasaberes, con la misma estructura del documento
"Primera Fase Ajuste de Cultura Corporativa" (introducción, marco de referencia,
procedimiento de la skill, misión, visión, propósitos, valores, cierre y firmas).

**Regla principal:** lo único que se redacta para cada ESE es la **misión** y la **visión**.
Los **propósitos** y **valores** son siempre los mismos: están en `assets/contenido_fijo.json`
y `build_pdf.py` los inserta tal cual. No se redactan, no se adaptan a la encuesta y no se
incluyen en `contenido.json`. Para cambiarlos en todos los documentos, se edita ese archivo.

El usuario solo debe subir el CSV. Todo lo demás (nombre de la entidad, municipio, año de la
visión, número de respuestas) se obtiene del propio archivo.

## Archivos de la skill

- `scripts/parse_encuesta.py` – lee y tabula el CSV → `encuesta.json` y `encuesta_resumen.md`.
- `scripts/build_pdf.py` – arma el PDF con membrete a partir de `contenido.json`.
- `references/plantilla_documento.md` – textos fijos del documento y campos variables.
- `references/criterios_redaccion.md` – definiciones ISO 9000, marco legal y reglas para redactar misión y visión.
- `assets/contenido_fijo.json` – propósitos y valores fijos (iguales en todos los documentos).
- `assets/header.png`, `assets/footer.png` – membrete de Fundasaberes (encabezado y pie).

`SKILL_DIR` = carpeta donde está este archivo.

## Procedimiento

### 1. Tabular la encuesta
```bash
python3 SKILL_DIR/scripts/parse_encuesta.py <ruta.csv> <carpeta_trabajo>
```
Leer `encuesta_resumen.md` completo (todas las respuestas). Verificar en la salida:
entidad, municipio, `anio_vision`, `total_respuestas` y que existan las secciones
`mision`, `vision`, `valores`, `propositos`, `objetivo`. Si el parser no detecta la entidad
o una sección, revisar el CSV a mano y continuar; no detenerse por eso.

Las celdas pueden traer saltos de línea, comillas tipográficas o restos de texto copiado de
la web (p. ej. "Salud y Protección Social" suelto, el carácter �): tratarlos como ruido.

### 2. Completar datos que el CSV no trae
- **Departamento** de la ESE: inferirlo solo si es un hecho seguro (p. ej. San Jacinto del Cauca → Bolívar). Si hay duda, preguntar.
- **Reseña institucional**: si el usuario la adjunta, usarla y dejar la viñeta en el marco de referencia; si no, omitir esa viñeta (no inventar historia de la institución).
- **Lugar y fecha de firma**: por defecto Cartagena, Bolívar y la fecha de hoy, con el mes en letras.
- **Firmantes**: por defecto los de la plantilla. Si el usuario entrega imágenes de firma, pasarlas en `firma`; si no, queda la línea en blanco para firmar.

Si el usuario no está disponible, usar los valores por defecto y decir cuáles se asumieron.

### 3. Redactar el contenido
Leer `references/criterios_redaccion.md` y `references/plantilla_documento.md`. Redactar
solo la misión y la visión (con el año del CSV), usando todas las secciones de la encuesta
como insumo. No redactar propósitos, valores ni objetivo.
Si están disponibles los PDF de las leyes y la ISO 9000 (archivos del proyecto), se pueden
consultar para afinar términos.

### 4. Armar `contenido.json`
Con las claves documentadas en el encabezado de `scripts/build_pdf.py`, copiando los textos
fijos de la plantilla y reemplazando las variables. El texto admite `<b>`, `<i>`; escapar
`&` como `&amp;` y no usar `<` sueltos.

### 5. Generar y revisar el PDF
```bash
python3 SKILL_DIR/scripts/build_pdf.py contenido.json "Primera_Fase_Ajuste_de_Cultura_Corporativa_<ESE>.pdf"
```
Requiere `reportlab` (`pip install reportlab --break-system-packages` si falta).
Convertir las páginas a imagen (`pdftoppm -png -r 60`) y mirarlas: membrete en cada página,
texto sin solaparse con encabezado o pie, firmas juntas en la última página, tildes correctas.
Corregir y regenerar si algo falla.

### 6. Entregar
Enviar el PDF. En la respuesta: una línea con el resultado, los datos asumidos (departamento,
fecha, reseña omitida) y recordar que es un borrador para validar en el taller presencial.
Ofrecer también el `encuesta_resumen.md` (tabulación) como anexo si lo quieren.
