#!/usr/bin/env python3
"""
Calculadora de Riesgo para ESE - Versión XLS
Lee datos desde archivos exportados del SIHO (carpeta DATOS/)

Basado en la Resolución 2509 de 2012 del Ministerio de Salud y Protección Social
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

try:
    import pandas as pd
    PANDAS_DISPONIBLE = True
except ImportError:
    PANDAS_DISPONIBLE = False
    print("ERROR: pandas no está instalado. Ejecute: pip install pandas")


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
        if self.datos.get('mercado_especial'):
            ingresos_corrientes += self.datos.get('aportes_no_ligados', 0)
        
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
        if self.datos.get('mercado_especial'):
            ingresos_totales += self.datos.get('aportes_no_ligados', 0)
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
    
    def generar_reporte(self):
        print("\n" + "="*70)
        print("REPORTE DE CATEGORIZACION DE RIESGO")
        print("="*70)
        print(f"\nESE: {self.datos.get('nombre_ese', 'No disponible')}")
        print(f"Municipio: {self.datos.get('municipio', 'No disponible')}")
        print(f"Departamento: {self.datos.get('departamento', 'No disponible')}")
        print(f"Nivel de atencion: {self.datos.get('nivel_atencion', 'No disponible')}")
        print(f"Fecha de calculo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Calcular todos los valores primero
        self.calcular_indice_riesgo()
        self.calcular_superavit_deficit_presupuestal()
        
        print("\n" + "-"*70)
        print("RESUMEN FINANCIERO")
        print("-"*70)
        
        print(f"\n1. INGRESOS OPERACIONALES CORRIENTES:")
        print(f"   Venta de servicios:        ${self.datos['ingresos_venta_servicios']:>20,.2f}")
        print(f"   Otros ingresos corrientes: ${self.datos['otros_ingresos_corrientes']:>20,.2f}")
        print(f"   Proyeccion cartera C.P.:   ${self.calcular_proyeccion_recaudo_corto_plazo():>20,.2f}")
        print(f"   TOTAL INGRESOS CORRIENTES: ${self.resultados['ingresos_corrientes']:>20,.2f}")
        
        print(f"\n2. GASTOS OPERACIONALES CORRIENTES:")
        print(f"   Gastos de funcionamiento:  ${self.datos['gastos_funcionamiento']:>20,.2f}")
        print(f"   Gastos de operacion:       ${self.datos['gastos_operacion']:>20,.2f}")
        print(f"   TOTAL GASTOS CORRIENTES:   ${self.resultados['gastos_corrientes']:>20,.2f}")
        
        print(f"\n3. SUPERAVIT/DEFICIT CORRIENTE:   ${self.resultados['superavit_deficit_corriente']:>20,.2f}")
        print(f"\n4. PROYECCION RECAUDO LARGO PLAZO: ${self.resultados['proyeccion_largo_plazo']:>20,.2f}")
        print(f"   Pasivos > 1 anio:           ${self.resultados['pasivos']:>20,.2f}")
        print(f"\n5. SUPERAVIT/DEFICIT NO CORRIENTE: ${self.resultados['superavit_deficit_no_corriente']:>20,.2f}")
        print(f"\n6. SUPERAVIT/DEFICIT TOTAL:        ${self.resultados['superavit_deficit_total']:>20,.2f}")
        print(f"\n7. INGRESOS OPERACIONALES TOTALES: ${self.resultados['ingresos_operacionales_totales']:>20,.2f}")
        print(f"\n8. INDICE DE RIESGO:               {self.resultados['indice_riesgo']:>24.4f}")
        
        print(f"\n9. EJECUCION PRESUPUESTAL:")
        print(f"   Ingresos reconocidos:      ${self.datos['ingresos_reconocidos_total']:>20,.2f}")
        print(f"   Gastos comprometidos:      ${self.datos['gastos_comprometidos_total']:>20,.2f}")
        print(f"   Superavit/Deficit:         ${self.resultados['superavit_deficit_presupuestal']:>20,.2f}")
        
        categoria = self.determinar_categoria_riesgo()
        
        print("\n" + "="*70)
        print(f"CATEGORIZACION: {categoria}")
        print("="*70)
        
        return categoria
    
    def exportar_json(self, nombre_archivo: str = None):
        if nombre_archivo is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nombre_archivo = f"riesgo_ese_xls_{timestamp}.json"
        
        datos_exportar = {
            'fecha_calculo': datetime.now().isoformat(),
            'datos_ese': self.datos,
            'resultados': self.resultados,
            'categoria_riesgo': self.determinar_categoria_riesgo()
        }
        
        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos_exportar, f, indent=2, ensure_ascii=False)
        
        print(f"\nResultados exportados a: {nombre_archivo}")


class LectorDatosSIHO:
    """Lee datos desde archivos XLS exportados del SIHO"""
    
    def __init__(self, carpeta_datos: str = "DATOS"):
        self.carpeta_datos = Path(carpeta_datos)
        self.archivos = {}
        self.datos_cargados = {}
    
    def verificar_archivos(self) -> bool:
        if not PANDAS_DISPONIBLE:
            return False
        if not self.carpeta_datos.exists():
            return False
        
        archivos_requeridos = {
            'ingreso': ['ingreso.xls', 'ingresos.xls'],
            'gasto': ['gasto.xls', 'gastos.xls'],
            'cartera': ['carteraDeudor.xls', 'cartera.xls', 'carteradeudor.xls'],
            'pasivo': ['pasivo.xls', 'pasivos.xls'],
        }
        
        for categoria, posibles in archivos_requeridos.items():
            for posible in posibles:
                archivo = self.carpeta_datos / posible
                if archivo.exists():
                    self.archivos[categoria] = archivo
                    break
        
        return len(self.archivos) >= 4
    
    def _leer_archivo_siho(self, archivo: Path) -> pd.DataFrame:
        try:
            dfs = pd.read_html(str(archivo))
            if dfs:
                df = dfs[0]
                df.columns = df.iloc[0]
                df = df.iloc[1:].reset_index(drop=True)
                return df
        except Exception:
            try:
                return pd.read_excel(archivo)
            except:
                pass
        return None
    
    def _convertir_valor(self, valor) -> float:
        if pd.isna(valor) or valor is None:
            return 0.0
        if isinstance(valor, (int, float)):
            return float(valor)
        valor_str = str(valor).strip()
        if valor_str in ['000', '0', '', 'NaN']:
            return 0.0
        valor_str = valor_str.replace('.', '').replace(',', '')
        try:
            return float(valor_str)
        except ValueError:
            return 0.0
    
    def cargar_datos(self) -> Dict:
        datos = {}
        
        print("\n" + "="*70)
        print("CARGANDO DATOS DESDE ARCHIVOS XLS DEL SIHO")
        print("="*70)
        
        if 'ingreso' in self.archivos:
            print(f"\nLeyendo {self.archivos['ingreso'].name}...")
            df_ing = self._leer_archivo_siho(self.archivos['ingreso'])
            if df_ing is not None:
                self._procesar_ingresos(df_ing, datos)
        
        if 'gasto' in self.archivos:
            print(f"Leyendo {self.archivos['gasto'].name}...")
            df_gas = self._leer_archivo_siho(self.archivos['gasto'])
            if df_gas is not None:
                self._procesar_gastos(df_gas, datos)
        
        if 'cartera' in self.archivos:
            print(f"Leyendo {self.archivos['cartera'].name}...")
            df_car = self._leer_archivo_siho(self.archivos['cartera'])
            if df_car is not None:
                self._procesar_cartera(df_car, datos)
        
        if 'pasivo' in self.archivos:
            print(f"Leyendo {self.archivos['pasivo'].name}...")
            df_pas = self._leer_archivo_siho(self.archivos['pasivo'])
            if df_pas is not None:
                self._procesar_pasivos(df_pas, datos)
        
        self.datos_cargados = datos
        return datos
    
    def _procesar_ingresos(self, df: pd.DataFrame, datos: Dict):
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
        
        if 'conc_codigo' in df.columns and 'recaudado' in df.columns:
            fila_venta = df[df['conc_codigo'].astype(str) == '4']
            if not fila_venta.empty:
                datos['ingresos_venta_servicios'] = self._convertir_valor(fila_venta['recaudado'].iloc[0])
            
            fila_corrientes = df[df['conc_codigo'].astype(str) == '2']
            if not fila_corrientes.empty:
                ingresos_corrientes_total = self._convertir_valor(fila_corrientes['recaudado'].iloc[0])
                datos['otros_ingresos_corrientes'] = ingresos_corrientes_total - datos.get('ingresos_venta_servicios', 0)
            
            if 'reconocido' in df.columns:
                fila_disp = df[df['conc_codigo'].astype(str) == '1']
                fila_ing_corr = df[df['conc_codigo'].astype(str) == '2']
                total_reconocido = 0
                if not fila_disp.empty:
                    total_reconocido += self._convertir_valor(fila_disp['reconocido'].iloc[0])
                if not fila_ing_corr.empty:
                    total_reconocido += self._convertir_valor(fila_ing_corr['reconocido'].iloc[0])
                datos['ingresos_reconocidos_total'] = total_reconocido
        
        datos['aportes_no_ligados'] = 0
        datos['mercado_especial'] = False
    
    def _procesar_gastos(self, df: pd.DataFrame, datos: Dict):
        if 'conc_codigo' not in df.columns or 'compromiso' not in df.columns:
            return
        
        fila_func = df[df['conc_codigo'].astype(str) == '29']
        if not fila_func.empty:
            datos['gastos_funcionamiento'] = self._convertir_valor(fila_func['compromiso'].iloc[0])
        
        fila_oper = df[df['conc_codigo'].astype(str) == '46']
        if not fila_oper.empty:
            datos['gastos_operacion'] = self._convertir_valor(fila_oper['compromiso'].iloc[0])
        else:
            datos['gastos_operacion'] = 0
        
        fila_total = df[df['conc_codigo'].astype(str) == '52']
        if not fila_total.empty:
            datos['gastos_comprometidos_total'] = self._convertir_valor(fila_total['compromiso'].iloc[0])
        else:
            datos['gastos_comprometidos_total'] = datos.get('gastos_funcionamiento', 0) + datos.get('gastos_operacion', 0)
    
    def _procesar_cartera(self, df: pd.DataFrame, datos: Dict):
        fila_total = df[df['concepto'].astype(str).str.strip() == 'TOTAL']
        if fila_total.empty and 'conc_codigo' in df.columns:
            fila_total = df[df['conc_codigo'].astype(str) == '96']
        
        if not fila_total.empty:
            fila = fila_total.iloc[0]
        else:
            return
        
        nivel = datos.get('nivel_atencion', 1)
        hasta60 = self._convertir_valor(fila.get('hasta60', 0))
        de61a90 = self._convertir_valor(fila.get('de61a90', 0))
        de91a180 = self._convertir_valor(fila.get('de91a180', 0))
        de181a360 = self._convertir_valor(fila.get('de181a360', 0))
        mayor360 = self._convertir_valor(fila.get('mayor360', 0))
        
        if nivel == 1:
            datos['cartera_menor_90'] = hasta60 + de61a90
            datos['cartera_90_360'] = de91a180 + de181a360
            datos['cartera_mayor_360'] = mayor360
        else:
            datos['cartera_menor_180'] = hasta60 + de61a90 + de91a180
            datos['cartera_180_360'] = de181a360
            datos['cartera_mayor_360'] = mayor360
    
    def _procesar_pasivos(self, df: pd.DataFrame, datos: Dict):
        fila_total = df[df['concepto'].astype(str).str.contains('Total Pasivos', case=False, na=False)]
        if fila_total.empty and 'conc_codigo' in df.columns:
            fila_total = df[df['conc_codigo'].astype(str) == '6929']
        
        if not fila_total.empty:
            datos['pasivos_mayores_1_anio'] = self._convertir_valor(fila_total['vigencia_anterior'].iloc[0])
        else:
            datos['pasivos_mayores_1_anio'] = 0
    
    def mostrar_resumen_datos(self):
        datos = self.datos_cargados
        print("\n" + "-"*70)
        print("DATOS CARGADOS:")
        print("-"*70)
        print(f"ESE: {datos.get('nombre_ese', 'No disponible')}")
        print(f"Municipio: {datos.get('municipio', 'No disponible')}")
        print(f"Nivel: {datos.get('nivel_atencion', 'No disponible')}")
        print(f"\nIngresos venta servicios: ${datos.get('ingresos_venta_servicios', 0):,.2f}")
        print(f"Otros ingresos: ${datos.get('otros_ingresos_corrientes', 0):,.2f}")
        print(f"Gastos funcionamiento: ${datos.get('gastos_funcionamiento', 0):,.2f}")
        print(f"Gastos operacion: ${datos.get('gastos_operacion', 0):,.2f}")
        
        nivel = datos.get('nivel_atencion', 1)
        if nivel == 1:
            print(f"Cartera < 90 dias: ${datos.get('cartera_menor_90', 0):,.2f}")
            print(f"Cartera 90-360 dias: ${datos.get('cartera_90_360', 0):,.2f}")
        else:
            print(f"Cartera < 180 dias: ${datos.get('cartera_menor_180', 0):,.2f}")
            print(f"Cartera 180-360 dias: ${datos.get('cartera_180_360', 0):,.2f}")
        print(f"Cartera > 360 dias: ${datos.get('cartera_mayor_360', 0):,.2f}")
        print(f"Pasivos > 1 anio: ${datos.get('pasivos_mayores_1_anio', 0):,.2f}")


def main():
    print("\n" + "="*70)
    print("CALCULADORA DE RIESGO ESE - VERSION XLS")
    print("Resolucion 2509 de 2012")
    print("="*70)
    
    lector = LectorDatosSIHO("DATOS")
    
    if not lector.verificar_archivos():
        print("\nERROR: No se encontraron los archivos requeridos en la carpeta DATOS/")
        print("Archivos necesarios: ingreso.xls, gasto.xls, carteraDeudor.xls, pasivo.xls")
        return
    
    print(f"\nArchivos encontrados: {list(lector.archivos.keys())}")
    
    datos = lector.cargar_datos()
    lector.mostrar_resumen_datos()
    
    calculadora = CalculadoraRiesgoESE()
    calculadora.datos = datos.copy()
    calculadora.datos['mercado_especial'] = False
    
    categoria = calculadora.generar_reporte()
    
    exportar = input("\nExportar resultados a JSON? (S/N): ").strip().upper()
    if exportar == 'S':
        calculadora.exportar_json()
    
    print("\nCalculo completado.")


if __name__ == "__main__":
    main()
