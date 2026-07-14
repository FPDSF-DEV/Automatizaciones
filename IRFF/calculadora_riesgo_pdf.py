#!/usr/bin/env python3
"""
Calculadora de Riesgo para ESE - Versión PDF
Lee datos desde archivos PDF de Ficha Técnica del SIHO

Basado en la Resolución 2509 de 2012 del Ministerio de Salud y Protección Social
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import PyPDF2
    PYPDF2_DISPONIBLE = True
except ImportError:
    PYPDF2_DISPONIBLE = False
    print("ERROR: PyPDF2 no está instalado. Ejecute: pip install PyPDF2")


class CalculadoraRiesgoESE:
    """Calcula el índice de riesgo según Resolución 2509 de 2012"""
    
    PORCENTAJES_RECAUDO = {
        1: {'corto_plazo': 0.80, 'largo_plazo_medio': 0.70, 'largo_plazo_largo': 0.50},
        2: {'corto_plazo': 0.80, 'largo_plazo_medio': 0.75, 'largo_plazo_largo': 0.50},
        3: {'corto_plazo': 0.80, 'largo_plazo_medio': 0.75, 'largo_plazo_largo': 0.50}
    }
    
    def __init__(self):
        self.datos = {}
        self.resultados = {}
    
    def calcular_proyeccion_recaudo_corto_plazo(self) -> float:
        nivel = self.datos['nivel_atencion']
        porcentajes = self.PORCENTAJES_RECAUDO[nivel]
        if nivel == 1:
            return self.datos['cartera_menor_90'] * porcentajes['corto_plazo']
        else:
            return self.datos['cartera_menor_180'] * porcentajes['corto_plazo']
    
    def calcular_proyeccion_recaudo_largo_plazo(self) -> float:
        nivel = self.datos['nivel_atencion']
        porcentajes = self.PORCENTAJES_RECAUDO[nivel]
        if nivel == 1:
            return (
                self.datos['cartera_90_360'] * porcentajes['largo_plazo_medio'] +
                self.datos['cartera_mayor_360'] * porcentajes['largo_plazo_largo']
            )
        else:
            return (
                self.datos['cartera_180_360'] * porcentajes['largo_plazo_medio'] +
                self.datos['cartera_mayor_360'] * porcentajes['largo_plazo_largo']
            )
    
    def calcular_superavit_deficit_corriente(self) -> float:
        ingresos_corrientes = (
            self.datos['ingresos_venta_servicios'] +
            self.datos['otros_ingresos_corrientes'] +
            self.calcular_proyeccion_recaudo_corto_plazo()
        )
        gastos_corrientes = (
            self.datos['gastos_funcionamiento'] +
            self.datos['gastos_operacion']
        )
        
        self.resultados['ingresos_corrientes'] = ingresos_corrientes
        self.resultados['gastos_corrientes'] = gastos_corrientes
        
        return ingresos_corrientes - gastos_corrientes
    
    def calcular_superavit_deficit_no_corriente(self) -> float:
        proyeccion = self.calcular_proyeccion_recaudo_largo_plazo()
        pasivos = self.datos['pasivos_mayores_1_anio']
        self.resultados['proyeccion_largo_plazo'] = proyeccion
        self.resultados['pasivos'] = pasivos
        return proyeccion - pasivos
    
    def calcular_superavit_deficit_total(self) -> float:
        corriente = self.calcular_superavit_deficit_corriente()
        no_corriente = self.calcular_superavit_deficit_no_corriente()
        total = corriente + no_corriente
        self.resultados['superavit_deficit_corriente'] = corriente
        self.resultados['superavit_deficit_no_corriente'] = no_corriente
        self.resultados['superavit_deficit_total'] = total
        return total
    
    def calcular_ingresos_operacionales_totales(self) -> float:
        ingresos_totales = (
            self.datos['ingresos_venta_servicios'] +
            self.datos['otros_ingresos_corrientes'] +
            self.calcular_proyeccion_recaudo_corto_plazo() +
            self.calcular_proyeccion_recaudo_largo_plazo()
        )
        self.resultados['ingresos_operacionales_totales'] = ingresos_totales
        return ingresos_totales
    
    def calcular_indice_riesgo(self) -> float:
        superavit_deficit_total = self.calcular_superavit_deficit_total()
        ingresos_totales = self.calcular_ingresos_operacionales_totales()
        if ingresos_totales == 0:
            return float('-inf')
        indice = superavit_deficit_total / ingresos_totales
        self.resultados['indice_riesgo'] = indice
        return indice
    
    def calcular_superavit_deficit_presupuestal(self) -> float:
        superavit = (
            self.datos['ingresos_reconocidos_total'] -
            self.datos['gastos_comprometidos_total']
        )
        self.resultados['superavit_deficit_presupuestal'] = superavit
        return superavit
    
    def determinar_categoria_riesgo(self) -> str:
        indice = self.calcular_indice_riesgo()
        deficit_presupuestal = self.calcular_superavit_deficit_presupuestal() < 0
        
        if deficit_presupuestal:
            return 'RIESGO ALTO'
        if indice >= 0.00:
            return 'SIN RIESGO'
        elif -0.10 <= indice <= -0.01:
            return 'RIESGO BAJO'
        elif -0.20 <= indice <= -0.11:
            return 'RIESGO MEDIO'
        else:
            return 'RIESGO ALTO'
    
    def calcular_y_mostrar(self, anio: int = None):
        """Calcula y muestra el índice de riesgo de forma compacta"""
        indice = self.calcular_indice_riesgo()
        self.calcular_superavit_deficit_presupuestal()
        categoria = self.determinar_categoria_riesgo()
        
        prefijo = f"Año {anio}: " if anio else ""
        print(f"  {prefijo}Índice = {indice:+.4f} -> {categoria}")
        
        return {
            'anio': anio,
            'indice': indice,
            'categoria': categoria,
            'resultados': self.resultados.copy()
        }


class LectorFichaTecnicaPDF:
    """Lee datos desde archivos PDF de Ficha Técnica del SIHO"""
    
    def __init__(self, archivo_pdf: str):
        self.archivo_pdf = Path(archivo_pdf)
        self.texto_completo = ""
        self.datos_por_anio = {}
        self.anios_disponibles = []
        self.nombre_ese = ""
        self.nivel_atencion = 1
    
    def leer_pdf(self) -> bool:
        if not PYPDF2_DISPONIBLE:
            print("ERROR: PyPDF2 no disponible")
            return False
        
        if not self.archivo_pdf.exists():
            print(f"ERROR: No se encontró el archivo {self.archivo_pdf}")
            return False
        
        try:
            with open(self.archivo_pdf, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                texto_paginas = []
                for pagina in reader.pages:
                    texto_paginas.append(pagina.extract_text())
                self.texto_completo = "\n".join(texto_paginas)
            return True
        except Exception as e:
            print(f"ERROR al leer PDF: {e}")
            return False
    
    def detectar_anios(self) -> List[int]:
        """Detecta los años disponibles en el PDF basándose en encabezados de tabla"""
        # Buscar patrones de encabezados de tabla como "Variable 2022 2023 2024"
        patron_encabezado = r'Variable\s+(\d{4})\s+(\d{4})\s+(\d{4})(?:\s+(\d{4}))?'
        match = re.search(patron_encabezado, self.texto_completo)
        
        if match:
            anios = [int(g) for g in match.groups() if g is not None]
            self.anios_disponibles = sorted(anios)
            return self.anios_disponibles
        
        # Fallback: buscar todos los años y filtrar
        anios_encontrados = set()
        patron_anios = r'\b(20[12][0-9])\b'
        matches = re.findall(patron_anios, self.texto_completo)
        
        for m in matches:
            anio = int(m)
            if 2015 <= anio <= 2030:
                anios_encontrados.add(anio)
        
        self.anios_disponibles = sorted(list(anios_encontrados))
        return self.anios_disponibles
    
    def _extraer_valor(self, texto: str, patron: str, posicion_anio: int = 0) -> float:
        """Extrae un valor numérico del texto usando regex"""
        try:
            match = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
            if match:
                # Buscar números después del patrón
                resto = texto[match.end():]
                numeros = re.findall(r'[\d.,]+', resto[:200])
                if numeros and posicion_anio < len(numeros):
                    valor_str = numeros[posicion_anio].replace('.', '').replace(',', '')
                    return float(valor_str)
        except:
            pass
        return 0.0
    
    def _parsear_linea_tabla(self, linea: str) -> List[float]:
        """Extrae todos los valores numéricos de una línea de tabla"""
        valores = []
        partes = re.split(r'\s{2,}|\t', linea)  # Separar por espacios múltiples o tabs
        
        for parte in partes:
            # Limpiar y convertir a número
            valor_str = parte.strip().replace('.', '').replace(',', '')
            try:
                if valor_str.isdigit():
                    valores.append(float(valor_str))
            except:
                continue
        
        return valores
    
    def extraer_datos_por_anio(self) -> Dict[int, Dict]:
        """Extrae los datos financieros para cada año detectado"""
        
        # Primero extraer nombre de la ESE
        match_nombre = re.search(r'E\.?S\.?E\.?\s+([^\n]+)', self.texto_completo, re.IGNORECASE)
        if match_nombre:
            self.nombre_ese = match_nombre.group(1).strip()
        
        # Detectar nivel de atención
        match_nivel = re.search(r'Nivel\s*:?\s*(\d)', self.texto_completo, re.IGNORECASE)
        if match_nivel:
            self.nivel_atencion = int(match_nivel.group(1))
        else:
            if 'local' in self.nombre_ese.lower() or 'municipal' in self.nombre_ese.lower():
                self.nivel_atencion = 1
            elif 'regional' in self.nombre_ese.lower():
                self.nivel_atencion = 2
            else:
                self.nivel_atencion = 1
        
        # Filtrar solo años recientes con datos (últimos 4-5 años)
        anio_actual = datetime.now().year
        self.anios_disponibles = [a for a in self.anios_disponibles if anio_actual - 5 <= a <= anio_actual]
        
        datos = {anio: {} for anio in self.anios_disponibles}
        
        lineas = self.texto_completo.split('\n')
        
        # Mapeo de conceptos a buscar
        conceptos = {
            'Ingreso Total Recaudado': 'ingreso_total',
            'Total Venta de Servicios': 'venta_servicios',
            'Gastos de Funcionamiento': 'gastos_funcionamiento',
            'Gasto de Funcionamiento': 'gastos_funcionamiento',
            'Gastos de Operación': 'gastos_operacion',
            'Gastos de Operacion': 'gastos_operacion',
            'Gasto de Funcionamiento operativo': 'gastos_funcionamiento',
            'Total Cartera': 'cartera_total',
            '< 60 dias': 'cartera_hasta_60',
            '61 a 360 dias': 'cartera_61_360',
            '> 360 dias': 'cartera_mayor_360',
            'TOTAL PASIVO': 'pasivos_total',
        }
        
        # Procesar línea por línea
        num_anios = len(self.anios_disponibles)
        for linea in lineas:
            valores = self._extraer_numeros_de_linea(linea)
            
            if len(valores) < num_anios:
                continue
            
            # Verificar qué concepto es esta línea
            for concepto, campo in conceptos.items():
                if concepto.lower() in linea.lower():
                    # Los valores corresponden a los años detectados
                    for j, anio in enumerate(self.anios_disponibles):
                        if j < len(valores):
                            # Evitar sobrescribir valores ya extraídos (ej: venta servicios)
                            if campo not in datos[anio] or datos[anio][campo] == 0:
                                datos[anio][campo] = valores[j]
                    break
        
        # Buscar datos específicos en formato de tabla que PyPDF2 concatena
        self._extraer_datos_tabla_financiera(datos)
        
        self.datos_por_anio = datos
        return datos
    
    def _extraer_datos_tabla_financiera(self, datos: Dict):
        """Extrae datos de tablas financieras línea por línea"""
        lineas = self.texto_completo.split('\n')
        num_anios = len(self.anios_disponibles)
        
        # Mapeo de patrones a campos
        patrones_campos = [
            ('ingreso total recaudado', 'ingreso_total'),
            ('total venta de servicios', 'venta_servicios'),
            ('gasto de funcionamiento', 'gastos_funcionamiento'),
            ('gastos de funcionamiento', 'gastos_funcionamiento'),
            ('gastos de operaci', 'gastos_operacion'),  # Coincide con "operación" y "operacion"
            ('gasto de operaci', 'gastos_operacion'),
            ('total cartera', 'cartera_total'),
            ('total pasivo', 'pasivos_total'),
        ]
        
        for linea in lineas:
            linea_lower = linea.lower()
            
            for patron, campo in patrones_campos:
                if patron in linea_lower:
                    valores = self._extraer_numeros_de_linea(linea)
                    if len(valores) >= num_anios:
                        for j, anio in enumerate(self.anios_disponibles):
                            if j < len(valores):
                                if campo not in datos[anio] or datos[anio][campo] == 0:
                                    datos[anio][campo] = valores[j]
                    break
        
        # Extraer cartera por líneas separadas
        self._extraer_cartera_por_lineas(datos)
    
    def _extraer_cartera_por_lineas(self, datos: Dict):
        """Extrae datos de cartera analizando líneas individuales"""
        lineas = self.texto_completo.split('\n')
        en_seccion_cartera = False
        
        for linea in lineas:
            linea_lower = linea.lower()
            
            # Detectar inicio de sección de cartera
            if 'cartera deudores' in linea_lower:
                en_seccion_cartera = True
                continue
            
            # Detectar fin de sección de cartera
            if en_seccion_cartera and 'pasivos' in linea_lower:
                en_seccion_cartera = False
                continue
            
            if not en_seccion_cartera:
                continue
            
            # Extraer valores de cartera
            valores = self._extraer_numeros_de_linea(linea)
            num_anios = len(self.anios_disponibles)
            if len(valores) < num_anios:
                continue
            
            if '< 60' in linea or '<60' in linea or 'hasta 60' in linea_lower:
                for j, anio in enumerate(self.anios_disponibles):
                    if j < len(valores):
                        if datos[anio].get('cartera_hasta_60', 0) == 0:
                            datos[anio]['cartera_hasta_60'] = valores[j]
            
            elif '61 a 360' in linea or '61 a360' in linea:
                for j, anio in enumerate(self.anios_disponibles):
                    if j < len(valores):
                        if datos[anio].get('cartera_61_360', 0) == 0:
                            datos[anio]['cartera_61_360'] = valores[j]
            
            elif '> 360' in linea or '>360' in linea or 'mayor 360' in linea_lower:
                for j, anio in enumerate(self.anios_disponibles):
                    if j < len(valores):
                        if datos[anio].get('cartera_mayor_360', 0) == 0:
                            datos[anio]['cartera_mayor_360'] = valores[j]
    
    def _extraer_numeros_de_linea(self, linea: str) -> List[float]:
        """Extrae todos los números de una línea"""
        numeros = []
        num_anios = len(self.anios_disponibles) if self.anios_disponibles else 3
        
        # Patrón para números colombianos con exactamente 1-2 decimales (valores financieros)
        # Ejemplo: 1.651.088,05 o 803.114,02 o 47.800,87
        patron = r'\d{1,3}(?:\.\d{3})+,\d{1,2}'
        matches = re.findall(patron, linea)
        
        for match in matches:
            try:
                # Convertir formato colombiano a número
                valor_str = match.replace('.', '').replace(',', '.')
                valor = float(valor_str)
                # Umbral para valores significativos en miles de pesos
                if valor > 10000:
                    numeros.append(valor)
            except:
                continue
        
        # Si encontramos suficientes números, retornar
        if len(numeros) >= num_anios:
            return numeros
        
        # Segundo intento: números sin decimales (formato entero)
        # Ejemplo: 1.651.088 o 803.114
        numeros_enteros = []
        patron_entero = r'\d{1,3}(?:\.\d{3})+'
        matches = re.findall(patron_entero, linea)
        
        for match in matches:
            # Evitar capturar números que ya se extrajeron con decimales
            if ',' not in linea or match + ',' not in linea:
                try:
                    valor_str = match.replace('.', '')
                    valor = float(valor_str)
                    if valor > 10000:
                        numeros_enteros.append(valor)
                except:
                    continue
        
        if len(numeros_enteros) >= num_anios:
            return numeros_enteros
        
        # Retornar lo que se haya encontrado
        return numeros if numeros else numeros_enteros
    
    def preparar_datos_calculadora(self, anio: int) -> Dict:
        """Prepara los datos en el formato requerido por la calculadora"""
        if anio not in self.datos_por_anio:
            return {}
        
        d = self.datos_por_anio[anio]
        nivel = self.nivel_atencion
        
        # Calcular otros ingresos corrientes
        ingreso_total = d.get('ingreso_total', 0)
        venta_servicios = d.get('venta_servicios', 0)
        otros_ingresos = ingreso_total - venta_servicios if ingreso_total > venta_servicios else 0
        
        # Calcular cartera por rangos
        # El PDF tiene: < 60 dias, 61 a 360 dias, > 360 dias (consolidado)
        cartera_hasta_60 = d.get('cartera_hasta_60', 0)
        cartera_61_360 = d.get('cartera_61_360', 0)
        cartera_mayor_360 = d.get('cartera_mayor_360', 0)
        
        # Si no tenemos desglose de cartera, usar el total y estimar
        if cartera_hasta_60 == 0 and cartera_61_360 == 0 and d.get('cartera_total', 0) > 0:
            cartera_total = d.get('cartera_total', 0)
            # Estimación basada en promedios típicos
            cartera_hasta_60 = cartera_total * 0.15
            cartera_61_360 = cartera_total * 0.35
            cartera_mayor_360 = cartera_total * 0.50
        
        # Para nivel 1: corto plazo = < 90 días, medio plazo = 90-360, largo = > 360
        # Como el PDF tiene < 60 y 61-360, aproximamos:
        # - cartera_menor_90 ≈ cartera_hasta_60 + (cartera_61_360 * 0.1)
        # - cartera_90_360 ≈ cartera_61_360 * 0.9
        
        datos_calc = {
            'nombre_ese': self.nombre_ese,
            'nivel_atencion': nivel,
            'anio': anio,
            'ingresos_venta_servicios': venta_servicios,
            'otros_ingresos_corrientes': otros_ingresos,
            'gastos_funcionamiento': d.get('gastos_funcionamiento', 0),
            'gastos_operacion': d.get('gastos_operacion', 0),
            'ingresos_reconocidos_total': ingreso_total,
            'gastos_comprometidos_total': d.get('gastos_funcionamiento', 0) + d.get('gastos_operacion', 0),
            # Asumir todos los pasivos son > 1 año (según indicación del usuario)
            'pasivos_mayores_1_anio': d.get('pasivos_total', 0),
            'mercado_especial': False,
            'aportes_no_ligados': 0,
        }
        
        # Configurar cartera según nivel
        if nivel == 1:
            # Para nivel 1: corto plazo = < 90 días
            datos_calc['cartera_menor_90'] = cartera_hasta_60 + (cartera_61_360 * 0.10)
            datos_calc['cartera_90_360'] = cartera_61_360 * 0.90
            datos_calc['cartera_mayor_360'] = cartera_mayor_360
        else:
            # Para nivel 2+: corto plazo = < 180 días
            datos_calc['cartera_menor_180'] = cartera_hasta_60 + (cartera_61_360 * 0.40)
            datos_calc['cartera_180_360'] = cartera_61_360 * 0.60
            datos_calc['cartera_mayor_360'] = cartera_mayor_360
        
        return datos_calc
    
    def mostrar_datos_extraidos(self):
        print("\n" + "-"*70)
        print("DATOS EXTRAÍDOS DEL PDF")
        print("-"*70)
        print(f"ESE: {self.nombre_ese}")
        print(f"Nivel de atención: {self.nivel_atencion}")
        print(f"Años disponibles: {self.anios_disponibles}")
        print()
        
        for anio in self.anios_disponibles:
            print(f"\n--- Año {anio} ---")
            d = self.datos_por_anio.get(anio, {})
            print(f"  Ingreso Total: ${d.get('ingreso_total', 0):,.0f}")
            print(f"  Venta Servicios: ${d.get('venta_servicios', 0):,.0f}")
            print(f"  Gastos Funcionamiento: ${d.get('gastos_funcionamiento', 0):,.0f}")
            print(f"  Gastos Operación: ${d.get('gastos_operacion', 0):,.0f}")
            print(f"  Cartera Total: ${d.get('cartera_total', 0):,.0f}")
            print(f"  Pasivos Total: ${d.get('pasivos_total', 0):,.0f}")


def buscar_archivo_pdf(carpeta: str = ".") -> Optional[str]:
    """Busca archivos PDF en la carpeta especificada"""
    carpeta_path = Path(carpeta)
    
    # Buscar en la carpeta principal
    pdfs = list(carpeta_path.glob("*.pdf"))
    
    # También buscar en DATOS
    datos_path = carpeta_path / "DATOS"
    if datos_path.exists():
        pdfs.extend(datos_path.glob("*.pdf"))
    
    # Priorizar "Ficha Técnica" o similar
    for pdf in pdfs:
        if 'ficha' in pdf.name.lower() or 'tecnica' in pdf.name.lower():
            return str(pdf)
    
    # Si no hay ficha técnica, retornar el primero
    if pdfs:
        return str(pdfs[0])
    
    return None


def main():
    print("\n" + "="*70)
    print("CALCULADORA DE RIESGO ESE - VERSION PDF")
    print("Resolución 2509 de 2012")
    print("="*70)
    
    # Buscar archivo PDF
    archivo_pdf = buscar_archivo_pdf(".")
    
    if archivo_pdf is None:
        archivo_pdf = buscar_archivo_pdf("DATOS")
    
    if archivo_pdf is None:
        print("\nERROR: No se encontró ningún archivo PDF")
        archivo_pdf = input("Ingrese la ruta del archivo PDF: ").strip()
        if not archivo_pdf:
            return
    
    print(f"\nUsando archivo: {archivo_pdf}")
    
    # Crear lector y procesar PDF
    lector = LectorFichaTecnicaPDF(archivo_pdf)
    
    if not lector.leer_pdf():
        return
    
    # Detectar años
    anios = lector.detectar_anios()
    if not anios:
        print("\nNo se detectaron años en el PDF")
        return
    
    print(f"\nAños detectados: {anios}")
    
    # Extraer datos por año
    lector.extraer_datos_por_anio()
    lector.mostrar_datos_extraidos()
    
    # Calcular índice para cada año
    print("\n" + "="*70)
    print("RESULTADOS DEL CÁLCULO DE RIESGO")
    print("="*70)
    print(f"\nESE: {lector.nombre_ese}")
    print(f"Nivel de atención: {lector.nivel_atencion}")
    print("\nNOTA: Se asume que todos los pasivos son > 1 año")
    print("-"*70)
    
    resultados = []
    
    for anio in lector.anios_disponibles:
        datos = lector.preparar_datos_calculadora(anio)
        
        if not datos or datos.get('ingresos_venta_servicios', 0) == 0:
            print(f"  Año {anio}: Datos insuficientes para el cálculo")
            continue
        
        calculadora = CalculadoraRiesgoESE()
        calculadora.datos = datos
        
        resultado = calculadora.calcular_y_mostrar(anio)
        resultados.append(resultado)
    
    # Resumen
    print("\n" + "="*70)
    print("RESUMEN POR AÑOS")
    print("="*70)
    print(f"\n{'Año':<8} {'Índice':>12} {'Categoría':<15}")
    print("-"*38)
    
    for r in resultados:
        if r:
            print(f"{r['anio']:<8} {r['indice']:>+12.4f} {r['categoria']:<15}")
    
    # Exportar resultados
    exportar = input("\n¿Exportar resultados a JSON? (S/N): ").strip().upper()
    if exportar == 'S':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_archivo = f"riesgo_ese_pdf_{timestamp}.json"
        
        datos_exportar = {
            'fecha_calculo': datetime.now().isoformat(),
            'archivo_fuente': str(archivo_pdf),
            'ese': lector.nombre_ese,
            'nivel_atencion': lector.nivel_atencion,
            'anios_analizados': lector.anios_disponibles,
            'resultados_por_anio': resultados
        }
        
        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos_exportar, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\nResultados exportados a: {nombre_archivo}")
    
    print("\nCálculo completado.")


if __name__ == "__main__":
    main()
