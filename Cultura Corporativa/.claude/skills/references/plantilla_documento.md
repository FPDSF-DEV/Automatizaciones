# Plantilla del documento (textos fijos y campos variables)

Este es el texto base del documento. Lo que está entre `{{ }}` se reemplaza con datos del
CSV o con el contenido redactado. El resto se copia tal cual (puede ajustarse mínimamente
para concordancia gramatical con el nombre de la entidad).

Variables:
- `{{ENTIDAD_CORTA}}`: forma corta para el título, p. ej. "ESE Hospital Centro de Salud con Cama de San Jacinto del Cauca".
- `{{ENTIDAD_NEGRITA}}`: nombre formal en tipo título, p. ej. "La Empresa Social del Estado Hospital Centro de Salud con Cama del Municipio de San Jacinto del Cauca, Departamento de Bolívar".
- `{{N}}`: número de respuestas de la encuesta.
- `{{ANIO_VISION}}`: año que trae la pregunta de visión del CSV.
- `{{CIUDAD}}`, `{{DIA}}`, `{{MES}}`, `{{ANIO}}`: lugar y fecha de firma (por defecto Cartagena, Bolívar y la fecha de hoy).

---

## titulo
Primera Fase Ajuste de Cultura Corporativa para la {{ENTIDAD_CORTA}}

## intro (2 párrafos)

1. Como punto de partida para el proceso de ajuste de la cultura corporativa, desde Fundasaberes se propone una actualización estructurada de la misma, en la cual los funcionarios de la ESE tengan participación activa. En este marco, el área de Psicología diseñó, en primera instancia, un formulario dirigido al personal de la institución, cuyas preguntas se orientan a indagar sobre la misión, la visión, los objetivos y los valores de la ESE. El formulario fue diligenciado por {{N}} funcionarios.

2. Una vez obtenidas las respuestas del formulario, y con el propósito de aportar un valor agregado al proceso de actualización de la cultura corporativa, el área de Psicología, en articulación con el área de Sistemas de Fundasaberes, incorporó Inteligencia Artificial para la generación de un primer borrador de la misión y la visión institucional. Para tal fin, se desarrolló una <i>skill</i> (habilidad especializada) para un Modelo de Lenguaje de Gran Escala (LLM, por sus siglas en inglés). A diferencia de una instrucción aislada o <i>prompt</i>, la <i>skill</i> es un procedimiento documentado y reutilizable que reúne en un solo paquete las instrucciones de trabajo, el marco normativo de referencia, los criterios de redacción y las herramientas de procesamiento de datos, de modo que cada ESE se analiza con el mismo método y los resultados son consistentes y verificables. El marco de referencia incorporado en la <i>skill</i> es el siguiente:

## contexto (viñetas, título en negrita)

- **Ley 100 de 1993:** Establece el Sistema General de Seguridad Social en Salud en Colombia, definiendo su estructura, funcionamiento y los actores responsables (EPS, IPS), con el fin de garantizar el acceso de la población a los servicios de salud.
- **Ley 1438 de 2011:** Modifica y fortalece el sistema de salud, con énfasis en la atención primaria, la calidad del servicio, la prevención de enfermedades y el fortalecimiento de la red pública hospitalaria.
- **Ley 1751 de 2015:** Regula el derecho fundamental a la salud, garantizando el acceso a los servicios de manera oportuna, eficaz y con calidad, y estableciendo la responsabilidad del Estado en su protección y cumplimiento.
- **ISO 9000:2015:** Establece los conceptos, principios y definiciones fundamentales de los sistemas de gestión de la calidad, proporcionando una base común para que las organizaciones definan su misión y visión, y mejoren continuamente sus procesos orientados a la satisfacción del cliente.
- **Reseña institucional** de la {{ENTIDAD_CORTA}}. *(Incluir solo si se suministró o se consultó una reseña; si no, omitir esta viñeta.)*
- **Datos tabulados** correspondientes a la encuesta realizada al personal.

## antes_resultados (1 párrafo)

Con base en este marco, la <i>skill</i> ejecutó de forma automática el siguiente procedimiento sobre el archivo de respuestas de la encuesta:

## pasos_skill (viñetas numeradas)

1. Lectura y tabulación del archivo de respuestas (CSV), identificando las secciones de misión, visión, valores, propósitos y objetivo institucional.
2. Análisis de contenido de las respuestas abiertas para identificar los conceptos recurrentes (por ejemplo, calidad, humanización, oportunidad, territorio) y el conteo de frecuencia de los valores seleccionados por el personal.
3. Contraste de los hallazgos con el marco normativo y con las definiciones de misión y visión de la norma ISO 9000:2015.
4. Redacción del borrador de la misión y la visión institucional, conservando las expresiones propias del personal.
5. Incorporación de los propósitos y valores institucionales definidos por Fundasaberes y generación de este documento.

## Resultados
- **Misión** y **Visión**: se redactan para cada ESE (ver criterios_redaccion.md).
- **Propósitos** y **Valores**: FIJOS, idénticos en todos los documentos. Están en `assets/contenido_fijo.json` y `build_pdf.py` los inserta automáticamente. No se redactan, no se adaptan y no se ponen en `contenido.json`. Si Fundasaberes quiere cambiarlos, se edita ese archivo.

## cierre (1 párrafo)

Este resultado constituirá el insumo inicial para la actualización de la cultura corporativa. Como etapa final del proceso, se llevará a cabo un taller presencial en el cual el personal participante revisará y ajustará in situ la misión y la visión propuestas, con el fin de obtener la versión institucional definitiva.

## lugar_fecha

Para mayor constancia se firma en el municipio de {{CIUDAD}} a los {{DIA}} días del mes de {{MES}} de {{ANIO}}.

## firmantes (por defecto)

- Psicóloga de Fundasaberes — CC. 45479676 de Cartagena
- Ingeniero de Fundasaberes — CC. 1007983653 de Cartagena
