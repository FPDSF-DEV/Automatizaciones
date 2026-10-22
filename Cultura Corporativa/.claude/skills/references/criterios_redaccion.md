# Criterios de redacción

## Definiciones de referencia (ISO 9000:2015)

- **Misión** (3.5.11): propósito de la existencia de la organización, tal como lo expresa la alta dirección. → Responde: quiénes somos, qué hacemos, para quién, cómo y con qué principios.
- **Visión** (3.5.10): aspiración de aquello que una organización querría llegar a ser, tal como lo expresa la alta dirección. → Responde: en qué año, cómo queremos ser reconocidos, dónde, por qué atributos.
- Principios de gestión de la calidad útiles como vocabulario: enfoque al cliente, liderazgo, compromiso de las personas, enfoque a procesos, mejora, toma de decisiones basada en la evidencia, gestión de las relaciones.

## Marco normativo (para vocabulario y principios)

- **Ley 100 de 1993**: crea el SGSSS. Art. 2 principios: eficiencia, universalidad, solidaridad, integralidad, unidad y participación. Art. 194–195: las ESE son entidades públicas descentralizadas que prestan servicios de salud como IPS.
- **Ley 1438 de 2011**: Atención Primaria en Salud (APS), redes integradas de servicios, enfoque territorial, calidad, prevención. Art. 3 principios: universalidad, solidaridad, igualdad, equidad, calidad, eficiencia, participación social, sostenibilidad, transparencia, prevención, continuidad, enfoque diferencial, entre otros.
- **Ley 1751 de 2015** (Estatutaria): salud como derecho fundamental. Elementos: disponibilidad, aceptabilidad, accesibilidad, calidad e idoneidad profesional. Principios (art. 6): universalidad, pro homine, equidad, continuidad, oportunidad, prevalencia de derechos, progresividad, libre elección, sostenibilidad, solidaridad, eficiencia, interculturalidad.

Si los PDF de estas normas están disponibles (p. ej. como archivos del proyecto), se pueden consultar para precisar; no hace falta citarlas textualmente en el documento.

## Alcance

Solo se redactan **misión** y **visión**. Propósitos y valores son fijos (`assets/contenido_fijo.json`) y no se tocan.
Todas las secciones del CSV sirven como insumo para misión y visión:

| Sección del CSV | Uso principal |
|---|---|
| mision (actividad central, características del servicio, aporte del cargo, cadena de valor, principio, eslogan) | Misión |
| objetivo (objetivo principal como primer nivel) | Nivel de complejidad y enfoque (APS) de la misión |
| propositos (propuesta de cambio, principal propósito) | Fin de la misión ("orientados a…") |
| vision (cómo será en el año X, cómo lograrlo, compromiso, beneficiarios) | Visión |
| valores (selección múltiple) | Solo como matiz de vocabulario; NO cambia la lista fija de valores |

## Misión (un solo párrafo, 70–110 palabras)

Estructura obligatoria, igual al modelo:
`{{ENTIDAD_NEGRITA}}; es una IPS que presta servicios de salud de [nivel de complejidad según la encuesta/realidad de la ESE] con [3–4 atributos más mencionados], orientados a [fin]. Nos apoyamos en [cómo: procesos, talento humano, recursos], garantizando [acceso / a quién, incluyendo zonas urbana y rural si el personal lo menciona]; en cumplimiento de los principios del sistema de salud colombiano.`

- El nivel de complejidad sale de los datos (p. ej. "primer nivel" → "baja complejidad"). No copiar "baja y mediana complejidad" del modelo de Pamplona si la encuesta no lo sustenta.
- Usar los atributos con mayor frecuencia en las respuestas (contar menciones: calidad, humanizado, oportuno, integral, accesible, seguro, eficiente…).

## Visión (un solo párrafo, 60–100 palabras)

`Para el año {{ANIO_VISION}}, {{ENTIDAD_NEGRITA}}, será reconocida como [aspiración, p. ej. referente / institución líder] en [territorio que mencione el personal: subregión, municipio] por [3–4 atributos], [elemento diferenciador que pida el personal: tecnología, infraestructura, talento humano, sostenibilidad], garantizando [acceso equitativo / satisfacción / bienestar] de [beneficiarios que nombró el personal].`

- El año de la visión es el que trae la pregunta del CSV (`anio_vision`), no 2030.
- Ser realista con el nivel de la ESE: una ESE de primer nivel no se proyecta como hospital de alta complejidad.

## Estilo general

- Español formal institucional de Colombia. Tercera persona para la entidad, "nos/nuestros" se permite en la misión como en el modelo.
- Recuperar expresiones propias del personal (p. ej. "salud cercana, humana y para todos") cuando fortalezcan el texto.
- No citar respuestas individuales ni nombres o cargos de quienes respondieron.
- Corregir ortografía de lo que se tome de las respuestas.
- No inventar datos que no estén en la encuesta, la reseña o que no sean hechos verificables (departamento, subregión). Si el departamento no se conoce con certeza, preguntar al usuario.
