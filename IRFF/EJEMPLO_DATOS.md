# EJEMPLO DE DATOS PARA LA CALCULADORA
# ESE Hospital San Rafael - Ejemplo ficticio

## DATOS BÁSICOS
Nombre ESE: Hospital San Rafael
Municipio: Popayán
Departamento: Cauca
Nivel de atención: 2
Condiciones especiales de mercado: No

## DATOS FINANCIEROS (Todos en pesos colombianos)

### 1. INGRESOS OPERACIONALES CORRIENTES RECAUDADOS
Ingresos por venta de servicios de salud: 5,250,000,000
Otros ingresos corrientes: 180,000,000
Aportes no ligados (solo si mercado especial): 0

### 2. CARTERA RADICADA
Para Nivel 2:
Cartera menor a 180 días: 1,850,000,000
Cartera entre 180 y 360 días: 620,000,000
Cartera mayor a 360 días: 340,000,000

### 3. GASTOS OPERACIONALES CORRIENTES COMPROMETIDOS
Gastos de funcionamiento: 1,420,000,000
Gastos de operación comercial y prestación de servicios: 4,680,000,000

### 4. PASIVOS
Pasivos con edad superior a un año: 890,000,000

### 5. EJECUCIÓN PRESUPUESTAL
Total ingresos reconocidos: 7,850,000,000
Total gastos comprometidos: 7,320,000,000

---

## CÁLCULOS ESPERADOS (para validación)

### Proyecciones de recaudo:
- Cartera corto plazo (80% de < 180 días): 1,480,000,000
- Cartera largo plazo medio (75% de 180-360): 465,000,000
- Cartera largo plazo largo (50% de > 360): 170,000,000
- Total proyección largo plazo: 635,000,000

### Ingresos y gastos corrientes:
- Ingresos corrientes totales: 6,910,000,000
- Gastos corrientes totales: 6,100,000,000
- Superávit corriente: 810,000,000

### Operación no corriente:
- Proyección recaudo largo plazo: 635,000,000
- Pasivos > 1 año: 890,000,000
- Déficit no corriente: -255,000,000

### Cálculo final:
- Superávit/Déficit total: 555,000,000
- Ingresos operacionales totales: 7,545,000,000
- Índice de riesgo: 0.0736
- Superávit presupuestal: 530,000,000

### CATEGORIZACIÓN ESPERADA: SIN RIESGO
(Índice >= 0.00 y superávit presupuestal positivo)

---

## OTRO EJEMPLO - CASO DE RIESGO ALTO

### Datos de entrada:
ESE: Hospital María Auxiliadora
Nivel: 1
Ingresos venta servicios: 2,100,000,000
Otros ingresos: 45,000,000
Cartera < 90 días: 580,000,000
Cartera 90-360 días: 320,000,000
Cartera > 360 días: 450,000,000
Gastos funcionamiento: 680,000,000
Gastos operación: 2,450,000,000
Pasivos > 1 año: 720,000,000
Ingresos reconocidos: 3,850,000,000
Gastos comprometidos: 4,120,000,000

### Resultado esperado: RIESGO ALTO
- Por déficit presupuestal (ingresos < gastos)
- Índice de riesgo aproximado: -0.28

---

## INSTRUCCIONES DE USO

1. Ejecutar el script: python calculadora_riesgo_ese.py
2. Ingresar los datos cuando se soliciten
3. Revisar el reporte generado
4. Exportar a JSON si lo desea

## FORMATO DE ENTRADA
- Los valores se ingresan SIN puntos ni comas
- Ejemplo: Para $5.250.000.000 ingresar: 5250000000
- El script formateará automáticamente la presentación

## VALIDACIÓN DE RESULTADOS
- Verificar que los cálculos intermedios tengan sentido
- Comparar índice de riesgo con rangos establecidos
- Confirmar categorización con criterios de la norma
