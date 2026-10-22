from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pandas as pd

# Las graficas usan el sistema de diseno de terridata (paleta, tipografia, maqueta),
# el mismo de los modulos terridata y pss.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "terridata"))
from terridata import graficas as g  # noqa: E402
from terridata.estilo import CLARO, TAMANO_BASE, formato_es, px  # noqa: E402


DEFAULT_KEY_COLUMNS = ["nombre", "concepto"]
DEFAULT_VALUE_COLUMN = "total"
FILE_YEAR_PATTERN = re.compile(r"(\d{4})")
# Los CSV salen de la carpeta SIHO (estructura de SJDC_SIHO):
# <SIHO>/Formularios_Anuales/<anio>/Produccion/Produccion_<anio>.csv
SIHO_PATTERN = "**/Formularios_Anuales/*/Produccion/*.csv"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMA = CLARO
PIE = "Fuente: SIHO — Formularios anuales de Producción"


def extract_year_from_filename(file_path: Path) -> int:
	match = FILE_YEAR_PATTERN.search(file_path.stem)
	if not match:
		raise ValueError(f"No se pudo detectar el anio en el archivo: {file_path.name}")
	return int(match.group(1))


def load_and_group_csvs(
	data_dir: Path,
	key_columns: Sequence[str],
	value_column: str,
) -> Dict[int, pd.DataFrame]:
	csv_files = sorted(data_dir.glob(SIHO_PATTERN), key=extract_year_from_filename)
	if not csv_files:
		raise FileNotFoundError(f"No se encontraron archivos CSV ({SIHO_PATTERN}) en: {data_dir}")

	grouped_by_year: Dict[int, pd.DataFrame] = {}

	for csv_file in csv_files:
		year = extract_year_from_filename(csv_file)
		if year in grouped_by_year:
			raise ValueError(f"Hay dos reportes de Produccion para {year}; deje solo uno por anio: {csv_file}")
		df = pd.read_csv(csv_file, encoding="utf-8-sig")

		required_columns = list(key_columns) + [value_column]
		missing = [column for column in required_columns if column not in df.columns]
		if missing:
			missing_text = ", ".join(missing)
			raise ValueError(f"{csv_file.name} no tiene las columnas requeridas: {missing_text}")

		# Agrupa por llaves para consolidar duplicados dentro de cada anio.
		grouped = df[list(key_columns) + [value_column]].copy()
		grouped[value_column] = pd.to_numeric(grouped[value_column], errors="coerce").fillna(0.0)
		grouped = grouped.groupby(list(key_columns), as_index=False, dropna=False)[value_column].sum()
		grouped_by_year[year] = grouped

	return grouped_by_year


def get_common_keys(
	grouped_by_year: Dict[int, pd.DataFrame],
	key_columns: Sequence[str],
) -> set[Tuple]:
	keys_per_year: List[set[Tuple]] = []

	for grouped in grouped_by_year.values():
		keys = set(grouped[list(key_columns)].itertuples(index=False, name=None))
		keys_per_year.append(keys)

	if not keys_per_year:
		return set()
	return set.intersection(*keys_per_year)


def build_common_dataframe(
	grouped_by_year: Dict[int, pd.DataFrame],
	key_columns: Sequence[str],
	value_column: str,
) -> pd.DataFrame:
	common_keys = get_common_keys(grouped_by_year, key_columns)
	if not common_keys:
		return pd.DataFrame(columns=list(key_columns))

	years = sorted(grouped_by_year.keys())
	key_name = "__key__"
	merged: pd.DataFrame | None = None

	for year in years:
		grouped = grouped_by_year[year].copy()
		grouped[key_name] = list(grouped[list(key_columns)].itertuples(index=False, name=None))
		grouped = grouped[grouped[key_name].isin(common_keys)][[key_name, value_column]]
		grouped = grouped.rename(columns={value_column: str(year)}).set_index(key_name)

		merged = grouped if merged is None else merged.join(grouped, how="inner")

	if merged is None:
		return pd.DataFrame(columns=list(key_columns))

	merged = merged.reset_index().rename(columns={"index": key_name})
	key_frame = pd.DataFrame(merged[key_name].tolist(), columns=list(key_columns))
	values_frame = merged.drop(columns=[key_name])
	return pd.concat([key_frame, values_frame], axis=1)


def slugify(text: str, max_len: int = 120) -> str:
	value = re.sub(r"[^a-zA-Z0-9]+", "_", str(text)).strip("_")
	return (value[:max_len] or "fila").lower()


def clean_title_text(value: object) -> str:
	text = str(value).strip()
	text = re.sub(r"^[\"'“”‘’]+|[\"'“”‘’]+$", "", text)
	text = re.sub(r"^(\.\.\.|…)+\s*", "", text)
	return text


def build_chart_basename(row: pd.Series, key_columns: Sequence[str]) -> str:
	if "concepto" in row.index:
		base_text = clean_title_text(row["concepto"])
	else:
		parts = [
			clean_title_text(row[column])
			for column in key_columns
			if "codigo" not in str(column).lower()
		]
		base_text = "_".join(parts)

	# Elimina puntos y comillas para nombres de archivo mas limpios.
	base_text = re.sub(r"[\"'“”‘’\.]+", "", base_text)
	return slugify(base_text)


def _variacion(values: Sequence[float], idx: int) -> Tuple[str, str]:
	"""Texto de la variacion frente al anio anterior y el color con que se escribe."""
	tema = TEMA
	if idx == 0:
		return "Base", tema.texto_secundario
	prev = values[idx - 1]
	if prev == 0:
		return "N/A", tema.texto_secundario
	pct = ((values[idx] - prev) / prev) * 100
	signo = "+" if pct >= 0 else "−"
	return f"{signo}{formato_es(abs(pct), 0)} %", tema.color(6) if pct >= 0 else tema.color(8)


def _titulo_y_subtitulo(title_text: str, ancho_util: float) -> Tuple[str, str]:
	"""El concepto va de titulo. Si no cabe en dos lineas se acorta con '…' y el
	nombre completo pasa al subtitulo: la cabecera nunca recorta en silencio."""
	subtitulo = "Total anual reportado y promedio del periodo · el porcentaje es la variación frente al año anterior"
	def cabe(texto: str) -> bool:
		lineas = g.envolver(texto, ancho_util, TEMA.fuente_titulo, max_lineas=2)
		return " ".join(lineas) == " ".join(texto.split())

	if cabe(title_text):
		return title_text, subtitulo
	# Lo que va entre parentesis es una aclaracion: baja al subtitulo.
	partes = re.match(r"^(.*?)\s*\((.*)\)\s*$", title_text)
	if partes and cabe(partes.group(1)):
		return partes.group(1), f"{partes.group(2)} · {subtitulo[0].lower()}{subtitulo[1:]}"
	lineas = g.envolver(title_text, ancho_util, TEMA.fuente_titulo, max_lineas=2)
	ultima = lineas[-1]
	while " " in ultima and g.ancho_texto(ultima + "…", TEMA.fuente_titulo) > ancho_util:
		ultima = ultima.rsplit(" ", 1)[0]
	return " ".join(lineas[:-1] + [ultima + "…"]), title_text


def draw_chart_for_row(
	row: pd.Series,
	years: Sequence[int],
	key_columns: Sequence[str],
	output_file: Path,
) -> None:
	tema = TEMA
	year_labels = [str(year) for year in years]
	values = [float(row[label]) for label in year_labels]
	average_value = sum(values) / len(values) if values else 0.0

	categories = year_labels + ["Promedio"]
	chart_values = values + [average_value]

	concept_column = "concepto" if "concepto" in row.index else None
	if concept_column:
		title_text = clean_title_text(row[concept_column])
	else:
		title_parts = [
			clean_title_text(row[column])
			for column in key_columns
			if "codigo" not in str(column).lower()
		]
		title_text = " - ".join(title_parts)
	ancho_util = TAMANO_BASE[0] - g.BORDE - g.MARGEN_DER
	titulo, subtitulo = _titulo_y_subtitulo(title_text, ancho_util)

	ancho_slot = (TAMANO_BASE[0] - g.MARGEN_IZQ - g.MARGEN_DER) / len(categories)
	etiquetas, rotacion, alto_cat = g._preparar_categorias(categories, ancho_slot, tema.fuente_eje)
	lienzo = g.crear_lienzo(tema, titulo, subtitulo, PIE, TAMANO_BASE, alto_categorias=alto_cat)
	ax = lienzo.ax
	ax.set_xlim(-0.5, len(categories) - 0.5)
	g._rejilla_horizontal(lienzo)
	ax.set_xticks(range(len(categories)))
	ax.set_xticklabels(etiquetas, rotation=rotacion,
	                   ha="right" if rotacion else "center", rotation_mode="anchor")

	# Cada barra lleva su cifra y, encima, la variacion: se reserva el aire de las dos.
	textos = [formato_es(v, 0) for v in chart_values]
	variaciones = [_variacion(values, i) for i in range(len(values))]
	giro, espacio = g.plan_etiquetas(tema, textos, lienzo.ancho_ejes / len(categories))
	espacio_variacion = g.alto_texto(tema.fuente_valor) + px(4)
	ax.set_ylim(*g._limites_con_espacio(chart_values, lienzo.alto_ejes, espacio + espacio_variacion))
	g.ajustar_formato_eje(ax, "y")

	grosor = g._grosor_barra(lienzo, len(categories))
	holgura_y = lienzo.a_datos_y(px(6))
	for i, valor in enumerate(chart_values):
		# El promedio no es un anio mas: va en el slot 2 para distinguirlo.
		color = tema.color(2) if i == len(values) else tema.color(1)
		g.dibujar_barra(lienzo, i - grosor / 2, 0.0, i + grosor / 2, valor, color, "arriba")
		g._etiqueta_valor(lienzo, i, valor + holgura_y, textos[i], va="bottom", rotacion=giro)
		if i < len(values):
			texto, color_var = variaciones[i]
			alto_cifra = g.ancho_texto(textos[i], tema.fuente_valor) if giro else g.alto_texto(tema.fuente_valor)
			ax.text(i, valor + holgura_y + lienzo.a_datos_y(alto_cifra + px(2)), texto,
			        va="bottom", ha="center", fontsize=tema.fuente_valor,
			        fontweight="semibold", color=color_var, zorder=4, clip_on=False)

	fig = lienzo.fig
	g.guardar(fig, output_file.with_suffix(""), formatos=(output_file.suffix.lstrip("."),))
	g.cerrar(fig)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=(
			"Lee CSV por anio, encuentra filas que existen en todos los anios y "
			"genera un grafico por fila comun."
		)
	)
	parser.add_argument(
		"--input-dir",
		default=str(PROJECT_ROOT / "DATA" / "SIHO"),
		help="Carpeta SIHO (estructura de SJDC_SIHO) con Formularios_Anuales/<anio>/Produccion/.",
	)
	parser.add_argument(
		"--output-dir",
		default=str(PROJECT_ROOT / "SALIDAS" / "produccion"),
		help="Carpeta donde se guardaran los graficos.",
	)
	parser.add_argument(
		"--key-columns",
		nargs="+",
		default=DEFAULT_KEY_COLUMNS,
		help="Columnas que definen una fila (deben coincidir en todos los anios).",
	)
	parser.add_argument(
		"--value-column",
		default=DEFAULT_VALUE_COLUMN,
		help="Columna numerica para graficar.",
	)
	parser.add_argument(
		"--max-charts",
		type=int,
		default=0,
		help="Limita cantidad de graficos (0 = sin limite).",
	)
	parser.add_argument(
		"--output-format",
		choices=["png", "svg"],
		default="svg",
		help="Formato de salida para los graficos.",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	input_dir = Path(args.input_dir).resolve()
	output_dir = Path(args.output_dir).resolve()
	output_dir.mkdir(parents=True, exist_ok=True)

	grouped_by_year = load_and_group_csvs(
		data_dir=input_dir,
		key_columns=args.key_columns,
		value_column=args.value_column,
	)

	common_df = build_common_dataframe(
		grouped_by_year=grouped_by_year,
		key_columns=args.key_columns,
		value_column=args.value_column,
	)

	if common_df.empty:
		print("No hay filas que coincidan en todos los anios con las llaves indicadas.")
		return

	years = sorted(grouped_by_year.keys())
	year_columns = [str(year) for year in years]
	common_df = common_df.sort_values(by=list(args.key_columns)).reset_index(drop=True)
	common_df["promedio_final"] = common_df[year_columns].mean(axis=1).round(2)

	limit = args.max_charts if args.max_charts and args.max_charts > 0 else len(common_df)
	generated = 0

	for _, row in common_df.head(limit).iterrows():
		file_name = f"{build_chart_basename(row, args.key_columns)}.{args.output_format}"
		output_file = output_dir / file_name

		draw_chart_for_row(
			row=row,
			years=years,
			key_columns=args.key_columns,
			output_file=output_file,
		)
		generated += 1

	report_file = output_dir / "filas_comunes.csv"
	common_df[list(args.key_columns) + year_columns + ["promedio_final"]].to_csv(
		report_file,
		index=False,
		encoding="utf-8-sig",
	)

	print(f"Anios detectados: {', '.join(year_columns)}")
	print(f"Filas comunes en todos los anios: {len(common_df)}")
	print(f"Graficos generados: {generated}")
	print(f"Formato de salida: {args.output_format}")
	print(f"Reporte de filas comunes: {report_file}")
	print(f"Carpeta de salida: {output_dir}")


if __name__ == "__main__":
	main()
