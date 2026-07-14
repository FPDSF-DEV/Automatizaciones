from __future__ import annotations

from pathlib import Path
import argparse
import re

import pandas as pd


def normalizar_nombre_columna(nombre: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(nombre).lower())


def primera_no_nula(serie: pd.Series):
    no_nulos = serie.dropna()
    if no_nulos.empty:
        return pd.NA
    valor = no_nulos.iloc[0]
    if isinstance(valor, str):
        valor = valor.strip()
        return valor if valor else pd.NA
    return valor


def resolver_columnas(df: pd.DataFrame) -> dict[str, str]:
    candidatos: dict[str, list[str]] = {
        "ano": ["ano", "año", "anio"],
        "cargNombre": ["cargnombre", "cargo", "carg_nombre"],
        "ocupNombre": ["ocupnombre", "perfil", "perfil_ocupacional", "ocup_nombre"],
        "asignacion_mensual": ["asignacion_mensual", "asignacionmensual", "salario"],
        "tipo_de_cargo": ["cargTipo"],
        "nivel_cargo": ["cargNivel"],
        "clcaNombre": ["clcanombre", "clca_nombre"],
        "inscrito": ["inscrito"],
        "numero_cargos_aprobados": ["numero_cargos_aprobados", "numerocargosaprobados"],
        "numero_cargos": ["numero_cargos", "numerocargos"],
        "anual_asignacion_total": ["anual_asignacion_total", "anualasignaciontotal"],
        "vacantes": ["vacantes"],
    }

    normalizadas_df = {normalizar_nombre_columna(col): col for col in df.columns}
    resolucion: dict[str, str] = {}

    for canonica, aliases in candidatos.items():
        for alias in aliases:
            clave = normalizar_nombre_columna(alias)
            if clave in normalizadas_df:
                resolucion[canonica] = normalizadas_df[clave]
                break

    return resolucion


def encontrar_archivos(base_dir: Path) -> list[Path]:
    patron = "*/Recursos_Humanos/Recursos_Humanos_*.csv"
    return sorted(base_dir.glob(patron))


def leer_y_unificar_csv(archivos: list[Path]) -> pd.DataFrame:
    dataframes = []
    columnas_requeridas = ["ano", "cargNombre", "ocupNombre", "asignacion_mensual"]
    columnas_adicionales = [
        "tipo_de_cargo",
        "nivel_cargo",
        "clcaNombre",
        "inscrito",
        "numero_cargos_aprobados",
        "numero_cargos",
        "anual_asignacion_total",
        "vacantes",
    ]
    columnas_objetivo = columnas_requeridas + columnas_adicionales

    for archivo in archivos:
        df = pd.read_csv(archivo, dtype=str)
        columnas_resueltas = resolver_columnas(df)

        faltantes = [c for c in columnas_requeridas if c not in columnas_resueltas]
        if faltantes:
            print(f"[WARN] Se omite {archivo.name}: faltan columnas {faltantes}")
            continue

        df_normalizado = pd.DataFrame()
        for col in columnas_objetivo:
            origen = columnas_resueltas.get(col)
            if origen:
                df_normalizado[col] = df[origen]
            else:
                df_normalizado[col] = pd.NA

        df = df_normalizado
        df["archivo_origen"] = str(archivo)
        dataframes.append(df)

    if not dataframes:
        raise RuntimeError("No se encontraron CSV validos de Recursos Humanos.")

    unificado = pd.concat(dataframes, ignore_index=True)
    return unificado


def limpiar_datos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce")
    df["cargNombre"] = df["cargNombre"].astype(str).str.strip()
    df["ocupNombre"] = df["ocupNombre"].astype(str).str.strip()
    df["asignacion_mensual"] = pd.to_numeric(df["asignacion_mensual"], errors="coerce")
    df["tipo_de_cargo"] = df["tipo_de_cargo"].astype(str).str.strip().replace({"": pd.NA})
    df["nivel_cargo"] = df["nivel_cargo"].astype(str).str.strip().replace({"": pd.NA})
    df["clcaNombre"] = df["clcaNombre"].astype(str).str.strip().replace({"": pd.NA})
    df["inscrito"] = df["inscrito"].astype(str).str.strip().replace({"": pd.NA})
    df["numero_cargos_aprobados"] = pd.to_numeric(df["numero_cargos_aprobados"], errors="coerce")
    df["numero_cargos"] = pd.to_numeric(df["numero_cargos"], errors="coerce")
    df["anual_asignacion_total"] = pd.to_numeric(df["anual_asignacion_total"], errors="coerce")
    df["vacantes"] = pd.to_numeric(df["vacantes"], errors="coerce")

    df = df.dropna(subset=["ano", "cargNombre", "ocupNombre", "asignacion_mensual"])
    df = df[df["cargNombre"] != ""]
    df = df[df["ocupNombre"] != ""]
    df["ano"] = df["ano"].astype(int)
    return df


def consolidar_y_rankear_por_ano(df: pd.DataFrame) -> pd.DataFrame:
    columnas_extra = [
        "tipo_de_cargo",
        "nivel_cargo",
        "clcaNombre",
        "inscrito",
        "numero_cargos_aprobados",
        "numero_cargos",
        "anual_asignacion_total",
        "vacantes",
    ]
    llaves = ["ano", "cargNombre", "ocupNombre", "asignacion_mensual"]

    extras_por_grupo = (
        df[llaves + columnas_extra]
        .groupby(llaves, as_index=False)
        .agg({col: primera_no_nula for col in columnas_extra})
    )

    # 1) Dejar una sola fila por combinacion exacta: anio + cargo + perfil + salario.
    base = (
        df[llaves]
        .drop_duplicates()
        .sort_values(["ano", "cargNombre", "ocupNombre", "asignacion_mensual"], ascending=[True, True, True, False])
        .reset_index(drop=True)
    )

    base = base.merge(extras_por_grupo, on=llaves, how="left")

    # 2) Rankear salario dentro de cada grupo anio + cargo + perfil: 1 = salario mas alto.
    base["orden_salario"] = (
        base.groupby(["ano", "cargNombre", "ocupNombre"])["asignacion_mensual"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    base = base.rename(
        columns={
            "ano": "anio",
            "cargNombre": "cargo",
            "ocupNombre": "perfil_ocupacional",
            "asignacion_mensual": "salario",
        }
    )

    base["cargo_perfil"] = (
        base["cargo"].astype(str)
        + " "
        + base["perfil_ocupacional"].astype(str)
    )

    base["cargo_perfil_orden"] = (
        base["cargo"].astype(str)
        + "-"
        + base["perfil_ocupacional"].astype(str)
        + "-"
        + base["orden_salario"].astype(str)
    )

    return base[
        [
            "anio",
            "cargo",
            "perfil_ocupacional",
            "cargo_perfil",
            "salario",
            "orden_salario",
            "cargo_perfil_orden",
            "tipo_de_cargo",
            "nivel_cargo",
            "clcaNombre",
            "inscrito",
            "numero_cargos_aprobados",
            "numero_cargos",
            "anual_asignacion_total",
            "vacantes",
        ]
    ]


def nombre_hoja_seguro(nombre: str, usados: set[str]) -> str:
    limpio = re.sub(r"[:\\/?*\[\]]", "_", nombre).strip()
    if not limpio:
        limpio = "Cargo"
    limpio = limpio[:31]

    original = limpio
    i = 1
    while limpio in usados:
        sufijo = f"_{i}"
        limpio = f"{original[: 31 - len(sufijo)]}{sufijo}"
        i += 1

    usados.add(limpio)
    return limpio


def exportar_resultados(df_ranking: pd.DataFrame, salida_dir: Path) -> tuple[Path, Path]:
    salida_dir.mkdir(parents=True, exist_ok=True)

    csv_salida = salida_dir / "ranking_salarios_por_cargo_perfil_anual.csv"
    xlsx_salida = salida_dir / "ranking_salarios_por_cargo_perfil_anual.xlsx"

    df_ranking.to_csv(csv_salida, index=False, encoding="utf-8-sig")

    usados: set[str] = set()
    with pd.ExcelWriter(xlsx_salida, engine="openpyxl") as writer:
        df_ranking.to_excel(writer, sheet_name="Resumen", index=False)
        usados.add("Resumen")

        # Matriz: filas = cargo_perfil + orden_salario + año (segmentación por orden), columnas = metadatos + salario + variacion + otros
        df_matriz = df_ranking.copy()

        df_matriz["cargo_perfil_orden"] = (
            df_matriz["cargo_perfil"].astype(str) + " | " + df_matriz["orden_salario"].astype(str)
        )
        
        # Calcular variación porcentual vs año anterior (dentro de cada cargo_perfil + orden_salario)
        df_matriz = df_matriz.sort_values(["cargo_perfil", "orden_salario", "anio"], na_position="last")
        df_matriz["salario_anterior"] = df_matriz.groupby(["cargo_perfil", "orden_salario"])["salario"].shift(1)
        df_matriz["variacion_pct"] = (
            ((df_matriz["salario"] - df_matriz["salario_anterior"]) / df_matriz["salario_anterior"] * 100)
            .round(0)
            .astype('Int64')  # Nullable int para manejar NaN
        )
        df_matriz["variacion_str"] = df_matriz["variacion_pct"].apply(
            lambda x: f"{int(x)}%" if pd.notna(x) else "0%"
        )
        
        # Construir matriz con formato: cargo_perfil | orden_salario | año | tipo | nivel | clca | salario | variacion | aprobados | cargos | vacantes | anual
        matriz_salarios = df_matriz[
            [
                "cargo_perfil",
                "orden_salario",
            "anio",
                "tipo_de_cargo",
                "nivel_cargo",
                "clcaNombre",
                "salario",
                "variacion_str",
                "numero_cargos_aprobados",
                "numero_cargos",
                "vacantes",
                "anual_asignacion_total",
            ]
        ].copy()
        
        matriz_salarios = matriz_salarios.sort_values(["cargo_perfil", "orden_salario", "anio"], na_position="last")
        matriz_salarios.columns = [
            "Cargo Perfil",
            "Orden Salario",
            "Año",
            "Tipo de Cargo",
            "Nivel",
            "Clasificación Nombre",
            "Salario",
            "Variación %",
            "Cargos Aprobados",
            "Cargos",
            "Vacantes",
            "Asignación Anual Total",
        ]
        
        hoja_matriz = nombre_hoja_seguro("Matriz_Cargo_Perfil_Orden", usados)
        matriz_salarios.to_excel(writer, sheet_name=hoja_matriz, index=False)

        for anio, grupo in df_ranking.groupby("anio", sort=True):
            hoja = nombre_hoja_seguro(f"Anio_{anio}", usados)
            grupo.sort_values(["cargo_perfil", "orden_salario"], na_position="last").to_excel(
                writer, sheet_name=hoja, index=False
            )

    return csv_salida, xlsx_salida


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consolida y rankea salarios por anio, cargo y perfil ocupacional en Recursos Humanos."
    )
    parser.add_argument(
        "--base-dir",
        default="descargas_csv/Formularios_Anuales",
        help="Directorio base que contiene los anios y subcarpetas de Recursos_Humanos.",
    )
    parser.add_argument(
        "--out-dir",
        default="descargas_csv/analisis_recursos_humanos",
        help="Directorio de salida para el CSV y Excel con ranking anual.",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    out_dir = Path(args.out_dir)

    archivos = encontrar_archivos(base_dir)
    if not archivos:
        raise RuntimeError(f"No se encontraron archivos en {base_dir}")

    df = leer_y_unificar_csv(archivos)
    df_limpio = limpiar_datos(df)
    df_ranking = consolidar_y_rankear_por_ano(df_limpio)
    csv_salida, xlsx_salida = exportar_resultados(df_ranking, out_dir)

    print(f"OK: ranking anual CSV -> {csv_salida}")
    print(f"OK: ranking anual Excel -> {xlsx_salida}")


if __name__ == "__main__":
    main()
