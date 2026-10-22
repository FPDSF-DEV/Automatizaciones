#!/usr/bin/env python3
"""
Lee el CSV exportado de Google Forms (Encuesta de Cultura Corporativa de una ESE)
y produce un JSON estructurado por secciones + un resumen en Markdown.

Uso:
    python3 parse_encuesta.py <encuesta.csv> <carpeta_salida>

Genera:
    <carpeta_salida>/encuesta.json      -> datos estructurados (para redactar)
    <carpeta_salida>/encuesta_resumen.md -> lectura humana / tabulación

No depende de nombres de columna exactos: detecta las secciones porque la
numeración de las preguntas reinicia en "1." al empezar cada sección, y las
etiqueta por palabras clave.
"""
import csv
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path


def leer_csv(ruta):
    raw = Path(ruta).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    muestra = texto[:5000]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    filas = list(csv.reader(io.StringIO(texto), dialecto))
    filas = [f for f in filas if any(c.strip() for c in f)]
    return filas[0], filas[1:]


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").upper()


def limpiar(s):
    s = s.replace("\r", "").strip()
    s = re.sub(r"[ \t]+", " ", s)
    # Restos de citas copiadas de la web (p. ej. "�" o "Salud y Protección Social" sueltos)
    s = s.replace("�", "").strip()
    return s


ETIQUETAS = [
    ("mision", ["ACTIVIDAD CENTRAL", "CADENA DE VALOR", "ESLOGAN", "PRINCIPIO DE LA SEGURIDAD"]),
    ("vision", ["COMO CREE QUE SEA", "CONSTRUIR SU FUTURO", "A QUIEN VA A BENEFICIAR"]),
    ("valores", ["VALORES"]),
    ("propositos", ["PROPUESTA DE CAMBIO", "PRINCIPAL PROPOSITO"]),
    ("objetivo", ["OBJETIVO PRINCIPAL", "OBJETIVO"]),
]


def etiquetar(preguntas):
    texto = " ".join(sin_tildes(p) for p in preguntas)
    for nombre, claves in ETIQUETAS:
        if any(k in texto for k in claves):
            return nombre
    return "otra"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    ruta_csv, salida = sys.argv[1], Path(sys.argv[2])
    salida.mkdir(parents=True, exist_ok=True)

    encabezado, filas = leer_csv(ruta_csv)

    # Columna de marca temporal
    idx_tiempo = next((i for i, h in enumerate(encabezado) if "MARCA TEMPORAL" in sin_tildes(h) or "TIMESTAMP" in sin_tildes(h)), None)

    # Agrupar columnas en secciones según reinicio de numeración "1."
    secciones, actual, ultimo_num = [], None, None
    for i, h in enumerate(encabezado):
        if i == idx_tiempo:
            continue
        m = re.match(r"\s*(\d+)\s*[.)]", h)
        num = int(m.group(1)) if m else None
        if actual is None or (num is not None and ultimo_num is not None and num <= ultimo_num):
            actual = {"columnas": []}
            secciones.append(actual)
        actual["columnas"].append(i)
        if num is not None:
            ultimo_num = num

    # Nombre de la entidad y municipio a partir del texto de las preguntas
    todo = " ".join(encabezado)
    m = re.search(r"(EMPRESA SOCIAL DEL ESTADO\s+.+?)(?:\s*[?:¿]|\s+PARA\s|\s+DIARIAMENTE)", todo, re.I)
    entidad = limpiar(m.group(1)) if m else ""
    mm = re.search(r"MUNICIPIO DE\s+([A-ZÁÉÍÓÚÑ ]+?)(?:\s*[?:¿]|$)", entidad + "?", re.I)
    municipio = mm.group(1).strip().title() if mm else ""

    # Año de la visión (p. ej. "¿EL 2031, CÓMO CREE...")
    anio_vision = None
    for h in encabezado:
        if "COMO CREE QUE SEA" in sin_tildes(h) or "VISION" in sin_tildes(h):
            a = re.search(r"\b(20\d\d)\b", h)
            if a:
                anio_vision = int(a.group(1))
                break

    resultado = {
        "entidad": entidad,
        "municipio": municipio,
        "anio_vision": anio_vision,
        "total_respuestas": len(filas),
        "fechas": sorted({limpiar(f[idx_tiempo]).split(" ")[0] for f in filas if idx_tiempo is not None and len(f) > idx_tiempo}),
        "secciones": {},
    }

    for s in secciones:
        preguntas = [limpiar(encabezado[i]) for i in s["columnas"]]
        nombre = etiquetar(preguntas)
        if nombre in resultado["secciones"]:
            nombre = f"{nombre}_{len(resultado['secciones'])}"
        bloque = []
        for i in s["columnas"]:
            respuestas = [limpiar(f[i]) for f in filas if len(f) > i and limpiar(f[i])]
            bloque.append({"pregunta": limpiar(encabezado[i]), "respuestas": respuestas})
        resultado["secciones"][nombre] = bloque

    # Conteo de valores (selección múltiple separada por ';')
    conteo = Counter()
    for bloque in resultado["secciones"].get("valores", []):
        for r in bloque["respuestas"]:
            vistos = {sin_tildes(v.strip()) for v in re.split(r"[;,]", r) if v.strip()}
            conteo.update(vistos)  # sin duplicados por persona
    n = max(resultado["total_respuestas"], 1)
    tildes = {"ETICA": "Ética", "PARTICIPACION": "Participación", "VOCACION DE SERVICIO": "Vocación de servicio",
              "HUMANIZACION": "Humanización", "INNOVACION": "Innovación", "COMUNICACION": "Comunicación"}
    resultado["valores_frecuencia"] = [
        {"valor": tildes.get(v, v.capitalize()), "votos": c, "porcentaje": round(100 * c / n, 1)}
        for v, c in conteo.most_common()
    ]

    (salida / "encuesta.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    # Resumen legible
    md = [f"# Tabulación encuesta – {entidad or 'ESE'}", "",
          f"- Municipio: {municipio}", f"- Respuestas: {resultado['total_respuestas']}",
          f"- Fechas: {', '.join(resultado['fechas'])}", f"- Año de visión preguntado: {anio_vision}", ""]
    for nombre, bloque in resultado["secciones"].items():
        md.append(f"## Sección: {nombre}")
        for q in bloque:
            md.append(f"### {q['pregunta']}")
            for k, r in enumerate(q["respuestas"], 1):
                md.append(f"{k}. {r}")
            md.append("")
    if resultado["valores_frecuencia"]:
        md.append("## Frecuencia de valores")
        md.append("| Valor | Votos | % |\n|---|---|---|")
        for v in resultado["valores_frecuencia"]:
            md.append(f"| {v['valor']} | {v['votos']} | {v['porcentaje']} |")
    (salida / "encuesta_resumen.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({k: resultado[k] for k in ("entidad", "municipio", "anio_vision", "total_respuestas")}, ensure_ascii=False))
    print("Secciones:", {k: len(v) for k, v in resultado["secciones"].items()})


if __name__ == "__main__":
    main()
