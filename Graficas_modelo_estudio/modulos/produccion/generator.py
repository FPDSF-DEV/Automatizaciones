from __future__ import annotations

import argparse
import re
from textwrap import fill
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_KEY_COLUMNS = ["nombre", "concepto"]
DEFAULT_VALUE_COLUMN = "total"
FILE_YEAR_PATTERN = re.compile(r"(\d{4})")
# Los CSV salen de la carpeta SIHO (estructura de SJDC_SIHO):
# <SIHO>/Formularios_Anuales/<anio>/Produccion/Produccion_<anio>.csv
SIHO_PATTERN = "**/Formularios_Anuales/*/Produccion/*.csv"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def format_int_label(value: float) -> str:
	return f"{int(round(value)):,}".replace(",", ".")


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


def draw_chart_for_row(
	row: pd.Series,
	years: Sequence[int],
	key_columns: Sequence[str],
	output_file: Path,
) -> None:
	year_labels = [str(year) for year in years]
	values = [float(row[label]) for label in year_labels]
	average_value = sum(values) / len(values) if values else 0.0

	categories = year_labels + ["PROMEDIO"]
	chart_values = values + [average_value]
	colors = ["#3f6fb6"] * len(values) + ["#d7263d"]

	fig, ax = plt.subplots(figsize=(12, 6.5), dpi=130)
	fig.patch.set_facecolor("#f6f7fb")
	ax.set_facecolor("#ffffff")

	bars = ax.bar(
		range(len(categories)),
		chart_values,
		color=colors,
		width=0.6,
		edgecolor="#2f4f78",
		linewidth=0.6,
		zorder=3,
	)

	max_value = max(chart_values) if chart_values else 1.0
	value_offset = max_value * 0.02
	pct_offset = max_value * 0.075
	upper_limit = max_value * 1.2 if max_value > 0 else 1.0
	ax.set_ylim(0, upper_limit)

	for bar, value in zip(bars, chart_values):
		center_x = bar.get_x() + bar.get_width() / 2
		ax.text(
			center_x,
			value / 2 if value > 0 else value + value_offset,
			format_int_label(value),
			ha="center",
			va="center",
			fontsize=12,
			color="#1e2b3a",
			fontweight="bold",
			bbox={"facecolor": "#eef2ff", "edgecolor": "none", "pad": 2.8},
			zorder=5,
		)

	for idx, value in enumerate(values):
		if idx == 0:
			pct_text = "BASE"
			pct_color = "#74839a"
		else:
			prev = values[idx - 1]
			if prev == 0:
				pct_text = "N/A"
				pct_color = "#74839a"
			else:
				pct = ((value - prev) / prev) * 100
				pct_text = f"{pct:+.0f}%"
				pct_color = "#2e9b51" if pct >= 0 else "#c13c37"

		ax.text(
			idx,
			value + pct_offset,
			pct_text,
			ha="center",
			va="center",
			fontsize=12,
			color="white",
			fontweight="bold",
			bbox={"facecolor": pct_color, "edgecolor": "none", "pad": 2.8},
			zorder=5,
		)

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
	title = fill(title_text.upper(), width=52)
	ax.set_title(title, fontsize=16, fontweight="bold", color="#243447", pad=20)

	ax.set_xticks(range(len(categories)))
	ax.set_xticklabels(categories, fontsize=11, color="#49576a", fontweight="bold")
	ax.tick_params(axis="x", pad=8)
	ax.tick_params(axis="y", labelsize=9, colors="#74839a")
	ax.yaxis.grid(True, color="#e7ebf1", linestyle="-", linewidth=1, zorder=0)
	ax.xaxis.grid(False)

	for spine in ["top", "right", "left"]:
		ax.spines[spine].set_visible(False)
	ax.spines["bottom"].set_color("#d4dbe5")

	plt.tight_layout()
	fig.savefig(output_file, bbox_inches="tight")
	plt.close(fig)


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
