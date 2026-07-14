# Calculadora de Riesgo para Empresas Sociales del Estado (ESE)

Sistema de cálculo automatizado de categorización de riesgo según la **Resolución 2509 de 2012** del Ministerio de Salud y Protección Social de Colombia.

## 📋 Descripción

Esta herramienta permite calcular la categorización de riesgo fiscal y financiero de las Empresas Sociales del Estado del nivel territorial, utilizando datos del Sistema de Información Hospitalario (SIHO).

## 🎯 Categorías de Riesgo

- **SIN RIESGO:** Índice ≥ 0.00
- **RIESGO BAJO:** Índice entre -0.01 y -0.10
- **RIESGO MEDIO:** Índice entre -0.11 y -0.20
- **RIESGO ALTO:** Índice ≤ -0.21 o déficit presupuestal

## 📁 Archivos Incluidos

```
IRFF/
│
├── calculadora_riesgo_ese.py   # Script principal (interactivo + lectura XLS de DATOS/)
├── calculadora_riesgo_xls.py   # Variante: lee automáticamente los .xls del SIHO
├── calculadora_riesgo_pdf.py   # Variante: extrae los datos de la Ficha Técnica en PDF
│
├── GUIA_DATOS_SIHO.md          # Guía detallada de obtención de datos
├── REFERENCIA_RAPIDA.md        # Referencia rápida de consulta
├── EJEMPLO_DATOS.md            # Ejemplos de datos de prueba
├── README.md                   # Este archivo
│
├── DATOS/                      # Carpeta de entrada por defecto (ingreso.xls, gasto.xls,
│                               #   carteraDeudor.xls, pasivo.xls, flujoCaja.xls)
├── DATOS1/  DATOS3/            # Juegos de datos alternativos (incluye Ficha Técnica PDF)
├── CAL 2022/  GC 2022/  manaure 2024/   # Datos de ejemplo de distintas entidades/años
└── riesgo_ese_*_AAAAMMDD_HHMMSS.json    # Reportes exportados (una corrida cada uno)
```

## 🧩 Variantes del script

Las tres calculadoras aplican **la misma metodología** (Resolución 2509 de 2012);
solo cambia **de dónde toman los datos**:

| Script | Fuente de datos | Requisitos | Cuándo usarla |
|---|---|---|---|
| **`calculadora_riesgo_ese.py`** | Lee los `.xls` de `DATOS/` **o** los pide interactivamente por teclado | `pandas` (opcional; sin él funciona en modo interactivo) | Uso general; permite entrada manual cuando no hay archivos |
| **`calculadora_riesgo_xls.py`** | `.xls` exportados del SIHO en `DATOS/` (`ingreso.xls`, `gasto.xls`, `carteraDeudor.xls`, `pasivo.xls`) | `pandas` (`pip install pandas`) | Ya se tienen los reportes del SIHO en Excel |
| **`calculadora_riesgo_pdf.py`** | El PDF de **Ficha Técnica** del SIHO | `PyPDF2` (`pip install PyPDF2`) | Solo se dispone de la Ficha Técnica en PDF |

Todas ejecutan igual (`python <script>.py`), muestran el reporte en pantalla y
pueden **exportar el resultado a JSON** (`riesgo_ese_<origen>_<fecha>.json`).

## 🔧 Requisitos

- Python 3.6 o superior
- `calculadora_riesgo_ese.py` en modo **interactivo**: solo librerías estándar.
- Para **leer archivos** del SIHO:
  - `.xls` (`calculadora_riesgo_ese.py` / `calculadora_riesgo_xls.py`) → `pip install pandas`
  - PDF (`calculadora_riesgo_pdf.py`) → `pip install PyPDF2`

## 📥 Instalación

### Opción 1: Descarga directa

1. Descarga el archivo `calculadora_riesgo_ese.py`
2. Guárdalo en una carpeta de tu preferencia

### Opción 2: Desde repositorio

```bash
# Clonar el repositorio (si aplica)
git clone [URL_DEL_REPOSITORIO]
cd calculadora_riesgo_ese

# O simplemente copiar los archivos
```

### Verificar instalación de Python

```bash
# En Windows
python --version

# En Linux/Mac
python3 --version
```

## 🚀 Uso

### Método 1: Ejecución interactiva (Recomendado)

```bash
# En Windows
python calculadora_riesgo_ese.py

# En Linux/Mac
python3 calculadora_riesgo_ese.py
```

El script te guiará paso a paso solicitando cada dato necesario.

### Método 2: Ejecución con ejemplo

Para probar con datos de ejemplo:

```bash
# Ver los ejemplos en EJEMPLO_DATOS.md
# Ejecutar el script e ingresar los datos manualmente
python calculadora_riesgo_ese.py
```

## 📊 Proceso de Cálculo

### Paso 1: Preparación
1. Reúne todos los datos del SIHO según la guía
2. Ten a mano la información de:
   - Ingresos operacionales recaudados
   - Cartera por antigüedad
   - Gastos comprometidos
   - Pasivos mayores a 1 año
   - Ejecución presupuestal total

### Paso 2: Ejecución
1. Ejecuta el script
2. Ingresa datos básicos de la ESE
3. Ingresa datos financieros cuando se soliciten
4. El script calcula automáticamente

### Paso 3: Resultados
1. Revisa el reporte detallado en pantalla
2. Opcionalmente exporta a JSON
3. Conserva el archivo para tus registros

## 📖 Guía de Datos del SIHO

Consulta el archivo `GUIA_DATOS_SIHO.md` para instrucciones detalladas sobre:

- Dónde encontrar cada dato en el SIHO
- Rutas exactas en los menús
- Filtros y clasificaciones a usar
- Qué incluir y qué excluir
- Cuentas contables relacionadas

## 📝 Ejemplo de Uso

```
$ python calculadora_riesgo_ese.py

======================================================================
CALCULADORA DE RIESGO PARA EMPRESAS SOCIALES DEL ESTADO
Resolución 2509 de 2012
======================================================================

Nombre de la ESE: Hospital San Rafael
Municipio: Popayán
Departamento: Cauca
Nivel de atención (1, 2 o 3): 2

--- CONDICIONES ESPECIALES DE MERCADO ---
¿La ESE opera en condiciones de mercado especiales?
(Quintil más alto de dispersión poblacional Y única opción para urgencias/partos)
O (Servicios de internación exclusivos para salud mental)
¿Condiciones especiales? (S/N): N

======================================================================
INGRESOS OPERACIONALES CORRIENTES RECAUDADOS
======================================================================

Ingresos por venta de servicios de salud (recaudados): $5250000000
Otros ingresos corrientes (recaudados): $180000000

... [continúa solicitando datos] ...

======================================================================
REPORTE DE CATEGORIZACIÓN DE RIESGO
======================================================================

ESE: Hospital San Rafael
Municipio: Popayán
Departamento: Cauca
Nivel de atención: 2
Condiciones especiales de mercado: No
Fecha de cálculo: 2026-02-09 14:30:00

... [muestra cálculos detallados] ...

======================================================================
CATEGORIZACIÓN: SIN RIESGO
======================================================================

INTERPRETACIÓN:
✓ La ESE NO presenta riesgo fiscal y financiero.
  No requiere adoptar Programa de Saneamiento Fiscal y Financiero.
```

## 💾 Exportación de Resultados

El script puede exportar los resultados a formato JSON:

```json
{
  "fecha_calculo": "2026-02-09T14:30:00",
  "datos_ese": {
    "nombre_ese": "Hospital San Rafael",
    "municipio": "Popayán",
    "departamento": "Cauca",
    ...
  },
  "resultados": {
    "indice_riesgo": 0.0736,
    "superavit_deficit_total": 555000000,
    ...
  },
  "categoria_riesgo": "SIN RIESGO"
}
```

## 📌 Puntos Importantes

### ✅ Datos que DEBES usar

- **Ingresos RECAUDADOS** (no reconocidos)
- **Gastos COMPROMETIDOS** (no pagados)
- **Cartera RADICADA** en proceso de cobro
- **Pasivos EXIGIBLES** mayores a 1 año

### ❌ Errores comunes a evitar

- Usar ingresos reconocidos en vez de recaudados
- Clasificar mal la cartera según el nivel de atención
- No aplicar los porcentajes de proyección correctos
- Incluir cartera castigada o provisionada
- Ignorar el criterio de déficit presupuestal

### ⚠️ Condiciones especiales

Marca "condiciones especiales" SOLO si:
- Quintil más alto de dispersión + única opción urgencias/partos, O
- Servicios exclusivos de salud mental

## 🔍 Validación de Resultados

### Verificaciones automáticas del script:

✓ Valores numéricos válidos  
✓ No negativos en ingresos y gastos  
✓ Aplicación correcta de porcentajes por nivel  
✓ Categorización según tabla de la norma  
✓ Consideración de déficit presupuestal  

### Verificaciones manuales recomendadas:

1. Coherencia de datos con situación real
2. Comparación con categorización año anterior
3. Validación por comité financiero
4. Revisión antes de reporte oficial

## 📞 Soporte y Consultas

### Dudas sobre el uso del script:
- Revisar `REFERENCIA_RAPIDA.md`
- Consultar `GUIA_DATOS_SIHO.md`

### Dudas sobre la normativa:
- Resolución 2509 de 2012 (completa)
- Dirección Territorial de Salud
- Ministerio de Salud: 018000 952525

### Problemas técnicos:
- Verificar versión de Python
- Revisar permisos de escritura (para exportar JSON)

## 📋 Flujo de Trabajo Recomendado

```
1. Cierre contable al 31 de diciembre
   ↓
2. Generar reportes certificados del SIHO
   ↓
3. Completar checklist de datos (ver REFERENCIA_RAPIDA.md)
   ↓
4. Ejecutar calculadora
   ↓
5. Revisar resultados con comité financiero
   ↓
6. Exportar y conservar documentación
   ↓
7. Reportar a Dirección Territorial
   ↓
8. Esperar categorización oficial MSPS
   ↓
9. Si aplica: Elaborar Programa de Saneamiento (60 días)
```

## 📄 Marco Normativo

- **Resolución 2509 de 2012** - Metodología de categorización
- **Ley 1438 de 2011** - Arts. 80, 81 y 83
- **Decreto 2193 de 2004** - Reporte de información
- **CGN** - Régimen de contabilidad pública

## ⚖️ Consecuencias Legales

### RIESGO MEDIO o ALTO:
- **Obligación:** Adoptar Programa de Saneamiento Fiscal y Financiero
- **Plazo:** 60 días calendario desde comunicación oficial
- **No adopción:** Causal de intervención por Supersalud

### Investigaciones posibles:
- Contraloría (por manejo de recursos)
- Procuraduría (por responsabilidad fiscal)
- Supersalud (intervención)

## 🔐 Confidencialidad

Los datos ingresados en esta calculadora:
- Se procesan localmente en tu computador
- No se envían a ningún servidor externo
- Solo se guardan si exportas a JSON
- Son responsabilidad de la ESE

## 📊 Estadísticas (Resolución 2509/2012)

Según categorización 2012 (Anexo 1):
- **SIN RIESGO:** 431 ESE (42.3%)
- **RIESGO BAJO:** 252 ESE (24.7%)
- **RIESGO MEDIO:** 140 ESE (13.7%)
- **RIESGO ALTO:** 197 ESE (19.3%)

## 🆕 Actualizaciones

**Versión 1.0** (Febrero 2026)
- Implementación inicial
- Basada en Resolución 2509 de 2012
- Incluye todos los criterios de la norma

## 📝 Notas Adicionales

1. Esta herramienta es **auxiliar** para el cálculo interno
2. La categorización **oficial** la realiza el MSPS
3. Los datos deben coincidir con el reporte anual al Decreto 2193/2004
4. Conservar documentación de respaldo para auditorías
5. Validar con Dirección Territorial antes del reporte oficial

## 🤝 Contribuciones

Si encuentras errores o mejoras:
1. Documenta el problema claramente
2. Incluye ejemplo de datos que causan el error
3. Sugiere la solución si es posible

## ⚠️ Disclaimer

Este software se proporciona "tal cual", sin garantías de ningún tipo. El usuario es responsable de:
- Verificar la exactitud de los datos ingresados
- Validar los resultados obtenidos
- Cumplir con la normativa vigente
- Reportar oficialmente según canales establecidos

La categorización oficial debe ser realizada y comunicada por el Ministerio de Salud y Protección Social.

---

**Desarrollado conforme a:** Resolución 2509 de 2012  
**Última actualización:** Febrero 2026  
**Versión:** 1.0
