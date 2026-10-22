"""Cálculos que las gráficas necesitan y que no vienen directos de TerriData (§6).

Regla general: cualquier operando `None` produce `None` — nunca cero y nunca una
excepción. La única excepción es el denominador de `PCT_DEL_TOTAL`, que suma las
entidades con dato (si no, un municipio sin población anularía el porcentaje de
todos los demás).
"""

from __future__ import annotations

from .resolucion import Resultado

# id -> (etiqueta, unidad, decimales)
META: dict[str, tuple[str, str, int]] = {
    "PCT_DEL_TOTAL": ("Participación en la población del conjunto", "%", 2),
    "PCT_RURAL": ("Población rural sobre el total", "%", 2),
    "PCT_URBANA": ("Población urbana sobre el total", "%", 2),
    "TOTAL_AFILIADOS": ("Total afiliados al SGSSS", "Personas", 0),
    "COBERTURA_SGSSS": ("Cobertura de aseguramiento en salud", "%", 2),
    "SIN_AFILIAR_PCT": ("Población sin afiliación estimada", "%", 2),
    "VAR_ACU_CENSO_REC": ("Variación acueducto: REC menos Censo", "p.p.", 2),
    "VAR_ALC_CENSO_REC": ("Variación alcantarillado: REC menos Censo", "p.p.", 2),
    "BRECHA_ACU_URB_RUR": ("Brecha urbano–rural en acueducto", "p.p.", 2),
    "BRECHA_ALC_URB_RUR": ("Brecha urbano–rural en alcantarillado", "p.p.", 2),
    "PROD_AGRICOLA_TOTAL": ("Producción agrícola total", "Toneladas", 2),
}

IDS = list(META)

CULTIVOS = ["CULT_T1", "CULT_T2", "CULT_T3", "CULT_TO",
            "CULT_P1", "CULT_P2", "CULT_P3", "CULT_PO"]


def division(numerador: float | None, denominador: float | None) -> float | None:
    """`numerador / denominador × 100`. None si falta un operando o el divisor es 0."""
    if numerador is None or denominador is None or denominador == 0:
        return None
    return numerador / denominador * 100.0


def resta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return a - b


def suma(valores: list[float | None]) -> float | None:
    if not valores or any(v is None for v in valores):
        return None
    return sum(v for v in valores if v is not None)


def _anio_de(res: Resultado, ids: list[str]) -> int | None:
    anios = [res.anios.get(i) for i in ids]
    validos = [a for a in anios if a is not None]
    return max(validos) if validos else None


def _fuente_de(res: Resultado, ids: list[str]) -> str:
    for i in ids:
        f = res.fuentes.get(i)
        if f:
            return f
    return ""


def _registrar(res: Resultado, id_derivado: str, valores: dict, origen: list[str]) -> None:
    etiqueta, unidad, decimales = META[id_derivado]
    res.registrar(
        id_derivado,
        etiqueta,
        unidad,
        decimales,
        valores,
        anio=_anio_de(res, origen),
        fuente=_fuente_de(res, origen),
    )


def agregar_derivados(res: Resultado) -> Resultado:
    """Calcula los derivados y los deja registrados en el mismo `Resultado`."""
    ents = res.entidades
    num = res.numero

    # --- Participación en la población del conjunto
    poblaciones = [num("POB_TOTAL", e) for e in ents]
    total_conjunto = sum(p for p in poblaciones if p is not None) or None
    _registrar(
        res,
        "PCT_DEL_TOTAL",
        {e: division(num("POB_TOTAL", e), total_conjunto) for e in ents},
        ["POB_TOTAL"],
    )

    _registrar(
        res,
        "PCT_RURAL",
        {e: division(num("POB_RUR", e), num("POB_TOTAL", e)) for e in ents},
        ["POB_RUR", "POB_TOTAL"],
    )
    _registrar(
        res,
        "PCT_URBANA",
        {e: division(num("POB_URB", e), num("POB_TOTAL", e)) for e in ents},
        ["POB_URB", "POB_TOTAL"],
    )

    # --- Aseguramiento: el total reportado manda; la suma de regímenes es el respaldo
    def total_afiliados(e: str) -> float | None:
        reportado = num("AFIL_SGSSS", e)
        if reportado is not None:
            return reportado
        return suma([num("AFIL_SUBS", e), num("AFIL_CONTRIB", e), num("AFIL_ESP", e)])

    totales = {e: total_afiliados(e) for e in ents}
    _registrar(res, "TOTAL_AFILIADOS", totales,
               ["AFIL_SGSSS", "AFIL_SUBS", "AFIL_CONTRIB", "AFIL_ESP"])

    def cobertura(e: str) -> float | None:
        c = division(totales[e], num("POB_TOTAL", e))
        return None if c is None else min(c, 100.0)

    coberturas = {e: cobertura(e) for e in ents}
    _registrar(res, "COBERTURA_SGSSS", coberturas,
               ["AFIL_SGSSS", "AFIL_SUBS", "POB_TOTAL"])
    _registrar(
        res,
        "SIN_AFILIAR_PCT",
        {e: (None if coberturas[e] is None else max(100.0 - coberturas[e], 0.0)) for e in ents},
        ["AFIL_SGSSS", "AFIL_SUBS", "POB_TOTAL"],
    )

    # --- Servicios públicos: variaciones y brechas, en puntos porcentuales
    _registrar(res, "VAR_ACU_CENSO_REC",
               {e: resta(num("ACU_REC", e), num("ACU_CENSO", e)) for e in ents},
               ["ACU_REC", "ACU_CENSO"])
    _registrar(res, "VAR_ALC_CENSO_REC",
               {e: resta(num("ALC_REC", e), num("ALC_CENSO", e)) for e in ents},
               ["ALC_REC", "ALC_CENSO"])
    _registrar(res, "BRECHA_ACU_URB_RUR",
               {e: resta(num("ACU_URB", e), num("ACU_RUR", e)) for e in ents},
               ["ACU_URB", "ACU_RUR"])
    _registrar(res, "BRECHA_ALC_URB_RUR",
               {e: resta(num("ALC_URB", e), num("ALC_RUR", e)) for e in ents},
               ["ALC_URB", "ALC_RUR"])

    # --- Producción agrícola
    _registrar(res, "PROD_AGRICOLA_TOTAL",
               {e: suma([num(c, e) for c in CULTIVOS]) for e in ents},
               CULTIVOS)

    return res
