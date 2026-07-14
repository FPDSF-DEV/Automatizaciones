#!/usr/bin/env python3
"""
Calculadora de Riesgo para Empresas Sociales del Estado (ESE)
Basado en la Resolución 2509 de 2012 del Ministerio de Salud y Protección Social

Este script calcula la categorización de riesgo de las ESE usando datos del SIHO
(Sistema de Información Hospitalario)

Puede leer automáticamente los datos desde archivos exportados del SIHO
en la carpeta DATOS/ o solicitarlos interactivamente.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional

# Intentar importar pandas para lectura de archivos
try:
    import pandas as pd
    PANDAS_DISPONIBLE = True
except ImportError:
    PANDAS_DISPONIBLE = False


class CalculadoraRiesgoESE:
    """
    Calcula el índice de riesgo de una ESE según la metodología establecida
    en la Resolución 2509 de 2012
    """
    
    # Porcentajes para proyección de recaudo según nivel de atención
    PORCENTAJES_RECAUDO = {
        1: {  # Nivel 1
            'corto_plazo': 0.80,  # 80% cartera < 90 días
            'largo_plazo_medio': 0.70,  # 70% cartera 90-360 días
            'largo_plazo_largo': 0.50   # 50% cartera > 360 días
        },
        2: {  # Nivel 2
            'corto_plazo': 0.80,  # 80% cartera < 180 días
            'largo_plazo_medio': 0.75,  # 75% cartera 180-360 días
            'largo_plazo_largo': 0.50   # 50% cartera > 360 días
        },
        3: {  # Nivel 3
            'corto_plazo': 0.80,  # 80% cartera < 180 días
            'largo_plazo_medio': 0.75,  # 75% cartera 180-360 días
            'largo_plazo_largo': 0.50   # 50% cartera > 360 días
        }
    }
    
    # Categorías de riesgo
    CATEGORIAS_RIESGO = [
        {'nombre': 'SIN RIESGO', 'min': 0.00, 'max': float('inf')},
        {'nombre': 'RIESGO BAJO', 'min': -0.10, 'max': -0.01},
        {'nombre': 'RIESGO MEDIO', 'min': -0.20, 'max': -0.11},
        {'nombre': 'RIESGO ALTO', 'min': float('-inf'), 'max': -0.21}
    ]
    
    def __init__(self):
        self.datos = {}
        self.resultados = {}
        
    def solicitar_datos_basicos(self):
        """Solicita información básica de la ESE"""
        print("\n" + "="*70)
        print("CALCULADORA DE RIESGO PARA EMPRESAS SOCIALES DEL ESTADO")
        print("Resolución 2509 de 2012")
        print("="*70)
        
        self.datos['nombre_ese'] = input("\nNombre de la ESE: ").strip()
        self.datos['municipio'] = input("Municipio: ").strip()
        self.datos['departamento'] = input("Departamento: ").strip()
        
        while True:
            try:
                nivel = int(input("Nivel de atención (1, 2 o 3): "))
                if nivel in [1, 2, 3]:
                    self.datos['nivel_atencion'] = nivel
                    break
                else:
                    print("Error: El nivel debe ser 1, 2 o 3")
            except ValueError:
                print("Error: Ingrese un número válido")
        
        # Pregunta sobre condiciones especiales de mercado
        print("\n--- CONDICIONES ESPECIALES DE MERCADO ---")
        print("¿La ESE opera en condiciones de mercado especiales?")
        print("(Quintil más alto de dispersión poblacional Y única opción para urgencias/partos)")
        print("O (Servicios de internación exclusivos para salud mental)")
        
        mercado_especial = input("¿Condiciones especiales? (S/N): ").strip().upper()
        self.datos['mercado_especial'] = mercado_especial == 'S'
        
    def solicitar_ingresos_operacionales(self):
        """
        Solicita datos de ingresos operacionales del SIHO
        
        DÓNDE ENCONTRAR EN EL SIHO:
        - Módulo: Ejecución Presupuestal de Ingresos
        - Reporte: Ingresos Recaudados por Concepto
        - Período: Vigencia fiscal correspondiente (01/01 - 31/12)
        """
        print("\n" + "="*70)
        print("INGRESOS OPERACIONALES CORRIENTES RECAUDADOS")
        print("="*70)
        print("\nDÓNDE OBTENER ESTOS DATOS EN EL SIHO:")
        print("• Módulo: Ejecución Presupuestal de Ingresos")
        print("• Reporte: Ingresos Recaudados")
        print("• Filtro: Ingresos Operacionales - Vigencia actual")
        print("• Corte: 31 de diciembre de la vigencia anterior")
        print("-"*70)
        
        self.datos['ingresos_venta_servicios'] = self._solicitar_valor(
            "Ingresos por venta de servicios de salud (recaudados)"
        )
        
        self.datos['otros_ingresos_corrientes'] = self._solicitar_valor(
            "Otros ingresos corrientes (recaudados)"
        )
        
        if self.datos['mercado_especial']:
            self.datos['aportes_no_ligados'] = self._solicitar_valor(
                "Aportes no ligados a ventas de servicios (recaudados)"
            )
        else:
            self.datos['aportes_no_ligados'] = 0
            
    def solicitar_cartera(self):
        """
        Solicita datos de cartera del SIHO
        
        DÓNDE ENCONTRAR EN EL SIHO:
        - Módulo: Cartera
        - Reporte: Antigüedad de Cartera / Aging de Cartera
        - Clasificación por días de antigüedad
        """
        print("\n" + "="*70)
        print("CARTERA RADICADA (CUENTAS POR COBRAR)")
        print("="*70)
        print("\nDÓNDE OBTENER ESTOS DATOS EN EL SIHO:")
        print("• Módulo: Cartera / Cuentas por Cobrar")
        print("• Reporte: Antigüedad de Cartera (Aging)")
        print("• Clasificación: Por rangos de días")
        print("• Corte: 31 de diciembre de la vigencia anterior")
        print("-"*70)
        
        nivel = self.datos['nivel_atencion']
        
        if nivel == 1:
            print("\nNIVEL 1 - Clasificación de cartera:")
            print("• Cartera de CORTO PLAZO: Menor a 90 días")
            print("• Cartera de LARGO PLAZO: 90 días o más")
            print()
            
            self.datos['cartera_menor_90'] = self._solicitar_valor(
                "Cartera menor a 90 días"
            )
            self.datos['cartera_90_360'] = self._solicitar_valor(
                "Cartera entre 90 y 360 días"
            )
            self.datos['cartera_mayor_360'] = self._solicitar_valor(
                "Cartera mayor a 360 días"
            )
            
        else:  # Nivel 2 o 3
            print(f"\nNIVEL {nivel} - Clasificación de cartera:")
            print("• Cartera de CORTO PLAZO: Menor a 180 días")
            print("• Cartera de LARGO PLAZO: 180 días o más")
            print()
            
            self.datos['cartera_menor_180'] = self._solicitar_valor(
                "Cartera menor a 180 días"
            )
            self.datos['cartera_180_360'] = self._solicitar_valor(
                "Cartera entre 180 y 360 días"
            )
            self.datos['cartera_mayor_360'] = self._solicitar_valor(
                "Cartera mayor a 360 días"
            )
    
    def solicitar_gastos_operacionales(self):
        """
        Solicita datos de gastos operacionales del SIHO
        
        DÓNDE ENCONTRAR EN EL SIHO:
        - Módulo: Ejecución Presupuestal de Gastos
        - Reporte: Gastos Comprometidos
        """
        print("\n" + "="*70)
        print("GASTOS OPERACIONALES CORRIENTES COMPROMETIDOS")
        print("="*70)
        print("\nDÓNDE OBTENER ESTOS DATOS EN EL SIHO:")
        print("• Módulo: Ejecución Presupuestal de Gastos")
        print("• Reporte: Gastos Comprometidos")
        print("• Clasificación: Gastos de Funcionamiento + Gastos de Operación")
        print("• Corte: 31 de diciembre de la vigencia anterior")
        print("-"*70)
        
        self.datos['gastos_funcionamiento'] = self._solicitar_valor(
            "Gastos de funcionamiento (comprometidos)"
        )
        
        self.datos['gastos_operacion'] = self._solicitar_valor(
            "Gastos de operación comercial y prestación de servicios (comprometidos)"
        )
    
    def solicitar_pasivos(self):
        """
        Solicita datos de pasivos del SIHO
        
        DÓNDE ENCONTRAR EN EL SIHO:
        - Módulo: Contabilidad / Balance General
        - Reporte: Pasivos por Antigüedad
        """
        print("\n" + "="*70)
        print("PASIVOS CON ANTIGÜEDAD MAYOR A UN AÑO")
        print("="*70)
        print("\nDÓNDE OBTENER ESTOS DATOS EN EL SIHO:")
        print("• Módulo: Contabilidad - Balance General")
        print("• Reporte: Pasivos por Antigüedad")
        print("• Filtro: Pasivos adquiridos en vigencias anteriores (> 1 año)")
        print("• Corte: 31 de diciembre de la vigencia anterior")
        print("-"*70)
        
        self.datos['pasivos_mayores_1_anio'] = self._solicitar_valor(
            "Pasivos con edad superior a un año"
        )
    
    def solicitar_ejecucion_presupuestal(self):
        """
        Solicita datos de ejecución presupuestal total del SIHO
        
        DÓNDE ENCONTRAR EN EL SIHO:
        - Módulo: Presupuesto
        - Reporte: Ejecución Presupuestal Consolidada
        """
        print("\n" + "="*70)
        print("EJECUCIÓN PRESUPUESTAL DE LA VIGENCIA")
        print("="*70)
        print("\nDÓNDE OBTENER ESTOS DATOS EN EL SIHO:")
        print("• Módulo: Ejecución Presupuestal")
        print("• Reporte: Ejecución Presupuestal Consolidada")
        print("• Total de Ingresos Reconocidos vs Gastos Comprometidos")
        print("• Período: Vigencia completa (01/01 - 31/12)")
        print("-"*70)
        
        self.datos['ingresos_reconocidos_total'] = self._solicitar_valor(
            "Total de ingresos RECONOCIDOS (todos los conceptos)"
        )
        
        self.datos['gastos_comprometidos_total'] = self._solicitar_valor(
            "Total de gastos COMPROMETIDOS (todos los conceptos)"
        )
    
    def calcular_proyeccion_recaudo_corto_plazo(self) -> float:
        """Calcula la proyección de recaudo de cartera de corto plazo"""
        nivel = self.datos['nivel_atencion']
        porcentajes = self.PORCENTAJES_RECAUDO[nivel]
        
        if nivel == 1:
            # Nivel 1: 80% de cartera < 90 días
            proyeccion = self.datos['cartera_menor_90'] * porcentajes['corto_plazo']
        else:
            # Nivel 2 y 3: 80% de cartera < 180 días
            proyeccion = self.datos['cartera_menor_180'] * porcentajes['corto_plazo']
        
        return proyeccion
    
    def calcular_proyeccion_recaudo_largo_plazo(self) -> float:
        """Calcula la proyección de recaudo de cartera de largo plazo"""
        nivel = self.datos['nivel_atencion']
        porcentajes = self.PORCENTAJES_RECAUDO[nivel]
        
        if nivel == 1:
            # Nivel 1: 70% cartera 90-360 días + 50% cartera > 360 días
            proyeccion = (
                self.datos['cartera_90_360'] * porcentajes['largo_plazo_medio'] +
                self.datos['cartera_mayor_360'] * porcentajes['largo_plazo_largo']
            )
        else:
            # Nivel 2 y 3: 75% cartera 180-360 días + 50% cartera > 360 días
            proyeccion = (
                self.datos['cartera_180_360'] * porcentajes['largo_plazo_medio'] +
                self.datos['cartera_mayor_360'] * porcentajes['largo_plazo_largo']
            )
        
        return proyeccion
    
    def calcular_superavit_deficit_corriente(self) -> float:
        """Calcula el superávit o déficit de la operación corriente"""
        # Ingresos operacionales corrientes recaudados
        ingresos_corrientes = (
            self.datos['ingresos_venta_servicios'] +
            self.datos['otros_ingresos_corrientes'] +
            self.calcular_proyeccion_recaudo_corto_plazo()
        )
        
        # Para mercado especial, agregar aportes no ligados
        if self.datos['mercado_especial']:
            ingresos_corrientes += self.datos['aportes_no_ligados']
        
        # Gastos operacionales corrientes comprometidos
        gastos_corrientes = (
            self.datos['gastos_funcionamiento'] +
            self.datos['gastos_operacion']
        )
        
        superavit_deficit = ingresos_corrientes - gastos_corrientes
        
        # Guardar para el cálculo del índice
        self.resultados['ingresos_corrientes'] = ingresos_corrientes
        self.resultados['gastos_corrientes'] = gastos_corrientes
        
        return superavit_deficit
    
    def calcular_superavit_deficit_no_corriente(self) -> float:
        """Calcula el superávit o déficit de la operación no corriente"""
        proyeccion_recaudo_largo = self.calcular_proyeccion_recaudo_largo_plazo()
        pasivos = self.datos['pasivos_mayores_1_anio']
        
        superavit_deficit = proyeccion_recaudo_largo - pasivos
        
        # Guardar para referencia
        self.resultados['proyeccion_largo_plazo'] = proyeccion_recaudo_largo
        self.resultados['pasivos'] = pasivos
        
        return superavit_deficit
    
    def calcular_superavit_deficit_total(self) -> float:
        """Calcula el superávit o déficit total"""
        corriente = self.calcular_superavit_deficit_corriente()
        no_corriente = self.calcular_superavit_deficit_no_corriente()
        
        total = corriente + no_corriente
        
        self.resultados['superavit_deficit_corriente'] = corriente
        self.resultados['superavit_deficit_no_corriente'] = no_corriente
        self.resultados['superavit_deficit_total'] = total
        
        return total
    
    def calcular_ingresos_operacionales_totales(self) -> float:
        """Calcula los ingresos operacionales totales recaudados"""
        ingresos_totales = (
            self.datos['ingresos_venta_servicios'] +
            self.datos['otros_ingresos_corrientes'] +
            self.calcular_proyeccion_recaudo_corto_plazo() +
            self.calcular_proyeccion_recaudo_largo_plazo()
        )
        
        # Para mercado especial, agregar aportes no ligados
        if self.datos['mercado_especial']:
            ingresos_totales += self.datos['aportes_no_ligados']
        
        self.resultados['ingresos_operacionales_totales'] = ingresos_totales
        
        return ingresos_totales
    
    def calcular_indice_riesgo(self) -> float:
        """Calcula el índice de riesgo"""
        superavit_deficit_total = self.calcular_superavit_deficit_total()
        ingresos_totales = self.calcular_ingresos_operacionales_totales()
        
        if ingresos_totales == 0:
            print("\n⚠️  ADVERTENCIA: Los ingresos operacionales totales son cero.")
            print("No se puede calcular el índice de riesgo.")
            return float('-inf')
        
        indice = superavit_deficit_total / ingresos_totales
        self.resultados['indice_riesgo'] = indice
        
        return indice
    
    def calcular_superavit_deficit_presupuestal(self) -> float:
        """Calcula el superávit o déficit presupuestal"""
        superavit = (
            self.datos['ingresos_reconocidos_total'] -
            self.datos['gastos_comprometidos_total']
        )
        
        self.resultados['superavit_deficit_presupuestal'] = superavit
        
        return superavit
    
    def determinar_categoria_riesgo(self) -> str:
        """Determina la categoría de riesgo según los criterios establecidos"""
        indice = self.calcular_indice_riesgo()
        deficit_presupuestal = self.calcular_superavit_deficit_presupuestal() < 0
        
        # Criterio (e): Si hay déficit presupuestal, es riesgo alto
        if deficit_presupuestal:
            return 'RIESGO ALTO'
        
        # Determinar categoría por índice
        if indice >= 0.00:
            return 'SIN RIESGO'
        elif -0.10 <= indice <= -0.01:
            return 'RIESGO BAJO'
        elif -0.20 <= indice <= -0.11:
            return 'RIESGO MEDIO'
        else:  # indice <= -0.21
            return 'RIESGO ALTO'
    
    def generar_reporte(self):
        """Genera un reporte detallado de los resultados"""
        print("\n" + "="*70)
        print("REPORTE DE CATEGORIZACIÓN DE RIESGO")
        print("="*70)
        print(f"\nESE: {self.datos['nombre_ese']}")
        print(f"Municipio: {self.datos['municipio']}")
        print(f"Departamento: {self.datos['departamento']}")
        print(f"Nivel de atención: {self.datos['nivel_atencion']}")
        print(f"Condiciones especiales de mercado: {'Sí' if self.datos['mercado_especial'] else 'No'}")
        print(f"Fecha de cálculo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("\n" + "-"*70)
        print("RESUMEN FINANCIERO")
        print("-"*70)
        
        print(f"\n1. INGRESOS OPERACIONALES CORRIENTES:")
        print(f"   Venta de servicios:        ${self.datos['ingresos_venta_servicios']:>20,.2f}")
        print(f"   Otros ingresos corrientes: ${self.datos['otros_ingresos_corrientes']:>20,.2f}")
        print(f"   Proyección cartera C.P.:   ${self.calcular_proyeccion_recaudo_corto_plazo():>20,.2f}")
        if self.datos['mercado_especial']:
            print(f"   Aportes no ligados:        ${self.datos['aportes_no_ligados']:>20,.2f}")
        print(f"   TOTAL INGRESOS CORRIENTES: ${self.resultados['ingresos_corrientes']:>20,.2f}")
        
        print(f"\n2. GASTOS OPERACIONALES CORRIENTES:")
        print(f"   Gastos de funcionamiento:  ${self.datos['gastos_funcionamiento']:>20,.2f}")
        print(f"   Gastos de operación:       ${self.datos['gastos_operacion']:>20,.2f}")
        print(f"   TOTAL GASTOS CORRIENTES:   ${self.resultados['gastos_corrientes']:>20,.2f}")
        
        print(f"\n3. SUPERÁVIT/DÉFICIT CORRIENTE:   ${self.resultados['superavit_deficit_corriente']:>20,.2f}")
        
        print(f"\n4. PROYECCIÓN RECAUDO LARGO PLAZO: ${self.resultados['proyeccion_largo_plazo']:>20,.2f}")
        print(f"   Pasivos > 1 año:           ${self.resultados['pasivos']:>20,.2f}")
        
        print(f"\n5. SUPERÁVIT/DÉFICIT NO CORRIENTE: ${self.resultados['superavit_deficit_no_corriente']:>20,.2f}")
        
        print(f"\n6. SUPERÁVIT/DÉFICIT TOTAL:        ${self.resultados['superavit_deficit_total']:>20,.2f}")
        
        print(f"\n7. INGRESOS OPERACIONALES TOTALES: ${self.resultados['ingresos_operacionales_totales']:>20,.2f}")
        
        print(f"\n8. ÍNDICE DE RIESGO:               {self.resultados['indice_riesgo']:>24.4f}")
        
        print(f"\n9. EJECUCIÓN PRESUPUESTAL:")
        print(f"   Ingresos reconocidos:      ${self.datos['ingresos_reconocidos_total']:>20,.2f}")
        print(f"   Gastos comprometidos:      ${self.datos['gastos_comprometidos_total']:>20,.2f}")
        print(f"   Superávit/Déficit:         ${self.resultados['superavit_deficit_presupuestal']:>20,.2f}")
        
        categoria = self.determinar_categoria_riesgo()
        
        print("\n" + "="*70)
        print(f"CATEGORIZACIÓN: {categoria}")
        print("="*70)
        
        # Interpretación
        print("\nINTERPRETACIÓN:")
        if categoria == 'SIN RIESGO':
            print("✓ La ESE NO presenta riesgo fiscal y financiero.")
            print("  No requiere adoptar Programa de Saneamiento Fiscal y Financiero.")
        elif categoria == 'RIESGO BAJO':
            print("⚠ La ESE presenta riesgo BAJO.")
            print("  No requiere adoptar Programa de Saneamiento Fiscal y Financiero.")
        elif categoria == 'RIESGO MEDIO':
            print("⚠ La ESE presenta riesgo MEDIO.")
            print("  DEBE adoptar Programa de Saneamiento Fiscal y Financiero")
            print("  en los 60 días siguientes a la comunicación oficial.")
        else:  # RIESGO ALTO
            print("⛔ La ESE presenta riesgo ALTO.")
            print("  DEBE adoptar Programa de Saneamiento Fiscal y Financiero")
            print("  en los 60 días siguientes a la comunicación oficial.")
            print("  La no adopción puede ser causal de intervención por parte")
            print("  de la Superintendencia Nacional de Salud.")
        
        return categoria
    
    def exportar_json(self, nombre_archivo: str = None):
        """Exporta los resultados a un archivo JSON"""
        if nombre_archivo is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nombre_archivo = f"riesgo_ese_{timestamp}.json"
        
        datos_exportar = {
            'fecha_calculo': datetime.now().isoformat(),
            'datos_ese': self.datos,
            'resultados': self.resultados,
            'categoria_riesgo': self.determinar_categoria_riesgo()
        }
        
        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos_exportar, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Resultados exportados a: {nombre_archivo}")
        
    def _solicitar_valor(self, concepto: str) -> float:
        """Solicita un valor numérico al usuario"""
        while True:
            try:
                valor_str = input(f"{concepto}: $").strip().replace(',', '').replace('.', '')
                valor = float(valor_str)
                if valor < 0:
                    print("Error: El valor no puede ser negativo")
                    continue
                return valor
            except ValueError:
                print("Error: Ingrese un valor numérico válido")


class LectorDatosSIHO:
    """
    Lee y procesa datos exportados del SIHO desde archivos HTML/XLS
    """
    
    def __init__(self, carpeta_datos: str = "DATOS"):
        self.carpeta_datos = Path(carpeta_datos)
        self.archivos = {}
        self.datos_cargados = {}
        
    def verificar_archivos(self) -> bool:
        """Verifica si existen los archivos necesarios en la carpeta"""
        if not PANDAS_DISPONIBLE:
            print("⚠️  pandas no está instalado. No se pueden leer archivos automáticamente.")
            print("   Instale con: pip install pandas")
            return False
            
        if not self.carpeta_datos.exists():
            return False
            
        archivos_requeridos = {
            'ingreso': ['ingreso.xls', 'ingresos.xls'],
            'gasto': ['gasto.xls', 'gastos.xls'],
            'cartera': ['carteraDeudor.xls', 'cartera.xls', 'carteradeudor.xls'],
            'pasivo': ['pasivo.xls', 'pasivos.xls'],
        }
        
        archivos_encontrados = list(self.carpeta_datos.glob('*.xls'))
        archivos_encontrados.extend(list(self.carpeta_datos.glob('*.xlsx')))
        
        for categoria, posibles in archivos_requeridos.items():
            for posible in posibles:
                archivo = self.carpeta_datos / posible
                if archivo.exists():
                    self.archivos[categoria] = archivo
                    break
        
        return len(self.archivos) >= 4
    
    def _leer_archivo_siho(self, archivo: Path) -> pd.DataFrame:
        """
        Lee un archivo exportado del SIHO (HTML disfrazado de XLS)
        """
        try:
            # Los archivos del SIHO suelen ser HTML con extensión .xls
            dfs = pd.read_html(str(archivo))
            if dfs:
                df = dfs[0]
                # La primera fila contiene los nombres de columnas
                df.columns = df.iloc[0]
                df = df.iloc[1:].reset_index(drop=True)
                return df
        except Exception as e:
            print(f"⚠️  Error leyendo {archivo}: {e}")
            # Intentar como Excel real
            try:
                return pd.read_excel(archivo)
            except:
                pass
        return None
    
    def _convertir_valor(self, valor) -> float:
        """Convierte un valor del SIHO a float"""
        if pd.isna(valor) or valor is None:
            return 0.0
        if isinstance(valor, (int, float)):
            return float(valor)
        valor_str = str(valor).strip()
        if valor_str in ['000', '0', '', 'NaN']:
            return 0.0
        # Remover separadores de miles
        valor_str = valor_str.replace('.', '').replace(',', '')
        try:
            return float(valor_str)
        except ValueError:
            return 0.0
    
    def cargar_datos(self) -> Dict:
        """Carga todos los datos desde los archivos del SIHO"""
        datos = {}
        
        print("\n" + "="*70)
        print("CARGANDO DATOS DESDE ARCHIVOS DEL SIHO")
        print("="*70)
        
        # Cargar archivo de ingresos
        if 'ingreso' in self.archivos:
            print(f"\n✓ Leyendo {self.archivos['ingreso'].name}...")
            df_ing = self._leer_archivo_siho(self.archivos['ingreso'])
            if df_ing is not None:
                self._procesar_ingresos(df_ing, datos)
        
        # Cargar archivo de gastos
        if 'gasto' in self.archivos:
            print(f"✓ Leyendo {self.archivos['gasto'].name}...")
            df_gas = self._leer_archivo_siho(self.archivos['gasto'])
            if df_gas is not None:
                self._procesar_gastos(df_gas, datos)
        
        # Cargar archivo de cartera
        if 'cartera' in self.archivos:
            print(f"✓ Leyendo {self.archivos['cartera'].name}...")
            df_car = self._leer_archivo_siho(self.archivos['cartera'])
            if df_car is not None:
                self._procesar_cartera(df_car, datos)
        
        # Cargar archivo de pasivos
        if 'pasivo' in self.archivos:
            print(f"✓ Leyendo {self.archivos['pasivo'].name}...")
            df_pas = self._leer_archivo_siho(self.archivos['pasivo'])
            if df_pas is not None:
                self._procesar_pasivos(df_pas, datos)
        
        self.datos_cargados = datos
        return datos
    
    def _procesar_ingresos(self, df: pd.DataFrame, datos: Dict):
        """Procesa el archivo de ingresos"""
        # Extraer datos básicos de la ESE (primera fila con datos)
        if 'nombre' in df.columns:
            datos['nombre_ese'] = df['nombre'].iloc[0]
        if 'municipio' in df.columns:
            datos['municipio'] = df['municipio'].iloc[0]
        if 'departamento' in df.columns:
            datos['departamento'] = df['departamento'].iloc[0]
        if 'nivel' in df.columns:
            try:
                datos['nivel_atencion'] = int(df['nivel'].iloc[0])
            except:
                datos['nivel_atencion'] = 1
        
        # Buscar concepto de venta de servicios de salud (código 4)
        if 'conc_codigo' in df.columns and 'recaudado' in df.columns:
            # Venta de servicios de salud
            fila_venta = df[df['conc_codigo'].astype(str) == '4']
            if not fila_venta.empty:
                datos['ingresos_venta_servicios'] = self._convertir_valor(
                    fila_venta['recaudado'].iloc[0]
                )
            else:
                # Intentar buscar por nombre del concepto
                fila_venta = df[df['concepto'].astype(str).str.contains('Venta de servicios de salud', case=False, na=False)]
                if not fila_venta.empty:
                    datos['ingresos_venta_servicios'] = self._convertir_valor(
                        fila_venta['recaudado'].iloc[0]
                    )
            
            # Ingresos corrientes totales (código 2)
            fila_corrientes = df[df['conc_codigo'].astype(str) == '2']
            if not fila_corrientes.empty:
                ingresos_corrientes_total = self._convertir_valor(
                    fila_corrientes['recaudado'].iloc[0]
                )
                # Otros ingresos = corrientes - venta servicios
                datos['otros_ingresos_corrientes'] = ingresos_corrientes_total - datos.get('ingresos_venta_servicios', 0)
            
            # Total de ingresos reconocidos (código 1 - Disponibilidad inicial + 2 - Ingresos corrientes)
            fila_disp = df[df['conc_codigo'].astype(str) == '1']
            fila_ing_corr = df[df['conc_codigo'].astype(str) == '2']
            
            if 'reconocido' in df.columns:
                total_reconocido = 0
                if not fila_disp.empty:
                    total_reconocido += self._convertir_valor(fila_disp['reconocido'].iloc[0])
                if not fila_ing_corr.empty:
                    total_reconocido += self._convertir_valor(fila_ing_corr['reconocido'].iloc[0])
                datos['ingresos_reconocidos_total'] = total_reconocido
        
        # Aportes no ligados (para mercado especial)
        datos['aportes_no_ligados'] = 0
        datos['mercado_especial'] = False
    
    def _procesar_gastos(self, df: pd.DataFrame, datos: Dict):
        """Procesa el archivo de gastos"""
        if 'conc_codigo' not in df.columns or 'compromiso' not in df.columns:
            return
        
        # Gastos de funcionamiento (código 29)
        fila_func = df[df['conc_codigo'].astype(str) == '29']
        if not fila_func.empty:
            datos['gastos_funcionamiento'] = self._convertir_valor(
                fila_func['compromiso'].iloc[0]
            )
        else:
            # Buscar por nombre
            fila_func = df[df['concepto'].astype(str).str.contains('GASTOS DE FUNCIONAMIENTO', case=False, na=False)]
            if not fila_func.empty:
                datos['gastos_funcionamiento'] = self._convertir_valor(
                    fila_func['compromiso'].iloc[0]
                )
        
        # Gastos de operación comercial (código 46)
        fila_oper = df[df['conc_codigo'].astype(str) == '46']
        if not fila_oper.empty:
            datos['gastos_operacion'] = self._convertir_valor(
                fila_oper['compromiso'].iloc[0]
            )
        else:
            # Buscar por nombre
            fila_oper = df[df['concepto'].astype(str).str.contains('operación comercial|GASTOS DE OPERACIÓN', case=False, na=False)]
            if not fila_oper.empty:
                datos['gastos_operacion'] = self._convertir_valor(
                    fila_oper['compromiso'].iloc[0]
                )
            else:
                # Si no hay gastos de operación comercial, usar 0
                datos['gastos_operacion'] = 0
        
        # Total de gastos comprometidos (código 52 - Total gastos)
        fila_total = df[df['conc_codigo'].astype(str) == '52']
        if not fila_total.empty:
            datos['gastos_comprometidos_total'] = self._convertir_valor(
                fila_total['compromiso'].iloc[0]
            )
        else:
            # Buscar por nombre
            fila_total = df[df['concepto'].astype(str).str.contains('TOTAL DE GASTOS', case=False, na=False)]
            if not fila_total.empty:
                datos['gastos_comprometidos_total'] = self._convertir_valor(
                    fila_total['compromiso'].iloc[0]
                )
            else:
                # Usar suma de funcionamiento + operación si no hay total
                datos['gastos_comprometidos_total'] = (
                    datos.get('gastos_funcionamiento', 0) + 
                    datos.get('gastos_operacion', 0)
                )
    
    def _procesar_cartera(self, df: pd.DataFrame, datos: Dict):
        """Procesa el archivo de cartera"""
        # Buscar fila TOTAL o sumar
        fila_total = df[df['concepto'].astype(str).str.strip() == 'TOTAL']
        
        if fila_total.empty:
            # Si no hay TOTAL, buscar por código 96
            if 'conc_codigo' in df.columns:
                fila_total = df[df['conc_codigo'].astype(str) == '96']
        
        if not fila_total.empty:
            fila = fila_total.iloc[0]
        else:
            # Sumar todas las filas numéricas
            return
        
        nivel = datos.get('nivel_atencion', 1)
        
        # Extraer valores de cartera por antigüedad
        hasta60 = self._convertir_valor(fila.get('hasta60', 0))
        de61a90 = self._convertir_valor(fila.get('de61a90', 0))
        de91a180 = self._convertir_valor(fila.get('de91a180', 0))
        de181a360 = self._convertir_valor(fila.get('de181a360', 0))
        mayor360 = self._convertir_valor(fila.get('mayor360', 0))
        
        if nivel == 1:
            # Nivel 1: corto plazo < 90 días, largo plazo >= 90 días
            datos['cartera_menor_90'] = hasta60 + de61a90
            datos['cartera_90_360'] = de91a180 + de181a360
            datos['cartera_mayor_360'] = mayor360
        else:
            # Nivel 2 y 3: corto plazo < 180 días, largo plazo >= 180 días
            datos['cartera_menor_180'] = hasta60 + de61a90 + de91a180
            datos['cartera_180_360'] = de181a360
            datos['cartera_mayor_360'] = mayor360
    
    def _procesar_pasivos(self, df: pd.DataFrame, datos: Dict):
        """Procesa el archivo de pasivos"""
        # Buscar el total de pasivos (código 6929 o concepto "2 Total Pasivos")
        fila_total = df[df['concepto'].astype(str).str.contains('Total Pasivos', case=False, na=False)]
        
        if fila_total.empty and 'conc_codigo' in df.columns:
            fila_total = df[df['conc_codigo'].astype(str) == '6929']
        
        if not fila_total.empty:
            # Pasivos de vigencia anterior (> 1 año)
            datos['pasivos_mayores_1_anio'] = self._convertir_valor(
                fila_total['vigencia_anterior'].iloc[0]
            )
        else:
            # Si no hay datos, usar 0
            datos['pasivos_mayores_1_anio'] = 0
    
    def mostrar_resumen_datos(self):
        """Muestra un resumen de los datos cargados"""
        datos = self.datos_cargados
        
        print("\n" + "-"*70)
        print("DATOS CARGADOS:")
        print("-"*70)
        print(f"ESE: {datos.get('nombre_ese', 'No disponible')}")
        print(f"Municipio: {datos.get('municipio', 'No disponible')}")
        print(f"Departamento: {datos.get('departamento', 'No disponible')}")
        print(f"Nivel de atención: {datos.get('nivel_atencion', 'No disponible')}")
        
        print(f"\nIngresos por venta de servicios: ${datos.get('ingresos_venta_servicios', 0):,.2f}")
        print(f"Otros ingresos corrientes: ${datos.get('otros_ingresos_corrientes', 0):,.2f}")
        print(f"Ingresos reconocidos total: ${datos.get('ingresos_reconocidos_total', 0):,.2f}")
        
        print(f"\nGastos de funcionamiento: ${datos.get('gastos_funcionamiento', 0):,.2f}")
        print(f"Gastos de operación: ${datos.get('gastos_operacion', 0):,.2f}")
        print(f"Gastos comprometidos total: ${datos.get('gastos_comprometidos_total', 0):,.2f}")
        
        nivel = datos.get('nivel_atencion', 1)
        if nivel == 1:
            print(f"\nCartera < 90 días: ${datos.get('cartera_menor_90', 0):,.2f}")
            print(f"Cartera 90-360 días: ${datos.get('cartera_90_360', 0):,.2f}")
        else:
            print(f"\nCartera < 180 días: ${datos.get('cartera_menor_180', 0):,.2f}")
            print(f"Cartera 180-360 días: ${datos.get('cartera_180_360', 0):,.2f}")
        print(f"Cartera > 360 días: ${datos.get('cartera_mayor_360', 0):,.2f}")
        
        print(f"\nPasivos > 1 año: ${datos.get('pasivos_mayores_1_anio', 0):,.2f}")


def main():
    """Función principal"""
    calculadora = CalculadoraRiesgoESE()
    
    try:
        # Intentar cargar datos automáticamente desde archivos
        lector = LectorDatosSIHO("DATOS")
        
        if lector.verificar_archivos():
            print("\n" + "="*70)
            print("CALCULADORA DE RIESGO PARA EMPRESAS SOCIALES DEL ESTADO")
            print("Resolución 2509 de 2012")
            print("="*70)
            print("\n✓ Se encontraron archivos del SIHO en la carpeta DATOS/")
            
            usar_archivos = input("\n¿Desea cargar los datos automáticamente? (S/N) [S]: ").strip().upper()
            if usar_archivos != 'N':
                datos = lector.cargar_datos()
                lector.mostrar_resumen_datos()
                
                # Preguntar si los datos son correctos
                confirmar = input("\n¿Los datos son correctos? (S/N) [S]: ").strip().upper()
                if confirmar != 'N':
                    # Transferir datos al calculador
                    calculadora.datos = datos.copy()
                    
                    # Preguntar solo por mercado especial si no está definido
                    print("\n--- CONDICIONES ESPECIALES DE MERCADO ---")
                    print("¿La ESE opera en condiciones de mercado especiales?")
                    print("(Quintil más alto de dispersión poblacional Y única opción para urgencias/partos)")
                    print("O (Servicios de internación exclusivos para salud mental)")
                    mercado_especial = input("¿Condiciones especiales? (S/N) [N]: ").strip().upper()
                    calculadora.datos['mercado_especial'] = mercado_especial == 'S'
                    
                    # Generar reporte
                    categoria = calculadora.generar_reporte()
                    
                    # Preguntar si desea exportar
                    exportar = input("\n¿Desea exportar los resultados a JSON? (S/N): ").strip().upper()
                    if exportar == 'S':
                        calculadora.exportar_json()
                    
                    print("\n" + "="*70)
                    print("Cálculo completado exitosamente")
                    print("="*70)
                    return
        
        # Si no hay archivos o el usuario prefiere ingreso manual
        print("\n→ Usando modo interactivo (ingreso manual de datos)")
        
        # Recolectar datos manualmente
        calculadora.solicitar_datos_basicos()
        calculadora.solicitar_ingresos_operacionales()
        calculadora.solicitar_cartera()
        calculadora.solicitar_gastos_operacionales()
        calculadora.solicitar_pasivos()
        calculadora.solicitar_ejecucion_presupuestal()
        
        # Generar reporte
        categoria = calculadora.generar_reporte()
        
        # Preguntar si desea exportar
        exportar = input("\n¿Desea exportar los resultados a JSON? (S/N): ").strip().upper()
        if exportar == 'S':
            calculadora.exportar_json()
        
        print("\n" + "="*70)
        print("Cálculo completado exitosamente")
        print("="*70)
        
    except KeyboardInterrupt:
        print("\n\nProceso cancelado por el usuario")
    except Exception as e:
        print(f"\n⛔ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
