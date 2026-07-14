# REFERENCIA RÁPIDA - CALCULADORA DE RIESGO ESE

## CHECKLIST DE DATOS NECESARIOS DEL SIHO

### ✅ INFORMACIÓN BÁSICA
- [ ] Nombre de la ESE
- [ ] Municipio
- [ ] Departamento
- [ ] Nivel de atención (1, 2 o 3)
- [ ] ¿Condiciones especiales de mercado? (Sí/No)

---

### ✅ INGRESOS OPERACIONALES RECAUDADOS
- [ ] Venta de servicios de salud (efectivamente recaudado)
- [ ] Otros ingresos corrientes (efectivamente recaudado)
- [ ] Aportes no ligados (solo si mercado especial)

**Fuente SIHO:** Presupuesto → Ejecución → Ingresos Recaudados

---

### ✅ CARTERA RADICADA (por antigüedad)

**Si es NIVEL 1:**
- [ ] Cartera menor a 90 días
- [ ] Cartera entre 90 y 360 días
- [ ] Cartera mayor a 360 días

**Si es NIVEL 2 o 3:**
- [ ] Cartera menor a 180 días
- [ ] Cartera entre 180 y 360 días
- [ ] Cartera mayor a 360 días

**Fuente SIHO:** Cartera → Antigüedad de Cartera (Aging)

---

### ✅ GASTOS COMPROMETIDOS
- [ ] Gastos de funcionamiento
- [ ] Gastos de operación y prestación de servicios

**Fuente SIHO:** Presupuesto → Ejecución → Gastos Comprometidos

---

### ✅ PASIVOS
- [ ] Pasivos con antigüedad mayor a un año

**Fuente SIHO:** Contabilidad → Balance General → Pasivos por Antigüedad

---

### ✅ EJECUCIÓN PRESUPUESTAL TOTAL
- [ ] Total ingresos reconocidos (todos los conceptos)
- [ ] Total gastos comprometidos (todos los conceptos)

**Fuente SIHO:** Presupuesto → Ejecución Presupuestal Consolidada

---

## CATEGORÍAS DE RIESGO

| Índice de Riesgo | Categoría | Acción Requerida |
|------------------|-----------|------------------|
| ≥ 0.00 | **SIN RIESGO** | Ninguna |
| -0.01 a -0.10 | **RIESGO BAJO** | Ninguna |
| -0.11 a -0.20 | **RIESGO MEDIO** | Programa de Saneamiento* |
| ≤ -0.21 | **RIESGO ALTO** | Programa de Saneamiento* |
| Déficit presupuestal | **RIESGO ALTO** | Programa de Saneamiento* |

*Debe adoptarse en los 60 días siguientes a la comunicación oficial

---

## FÓRMULAS DE CÁLCULO

### 1. Proyección Recaudo Corto Plazo

**Nivel 1:**
```
Proyección = 80% × Cartera(<90 días)
```

**Nivel 2 y 3:**
```
Proyección = 80% × Cartera(<180 días)
```

### 2. Proyección Recaudo Largo Plazo

**Nivel 1:**
```
Proyección = (70% × Cartera[90-360]) + (50% × Cartera[>360])
```

**Nivel 2 y 3:**
```
Proyección = (75% × Cartera[180-360]) + (50% × Cartera[>360])
```

### 3. Superávit/Déficit Corriente

```
S/D Corriente = Ingresos Corrientes - Gastos Corrientes

Donde:
Ingresos Corrientes = Venta Servicios + Otros Ingresos + 
                      Proyección Recaudo CP + Aportes*

Gastos Corrientes = Gastos Funcionamiento + Gastos Operación

*Solo si mercado especial
```

### 4. Superávit/Déficit No Corriente

```
S/D No Corriente = Proyección Recaudo LP - Pasivos(>1 año)
```

### 5. Superávit/Déficit Total

```
S/D Total = S/D Corriente + S/D No Corriente
```

### 6. Ingresos Operacionales Totales

```
Ing. Op. Totales = Venta Servicios + Otros Ingresos + 
                   Proyección CP + Proyección LP + Aportes*
```

### 7. Índice de Riesgo

```
Índice = S/D Total ÷ Ingresos Operacionales Totales
```

### 8. Superávit/Déficit Presupuestal

```
S/D Presupuestal = Ingresos Reconocidos Total - Gastos Comprometidos Total
```

---

## CONDICIONES ESPECIALES DE MERCADO

Una ESE tiene condiciones especiales si cumple UNO de estos criterios:

**Criterio 1:**
- Ubicada en municipio del quintil más alto de dispersión poblacional, Y
- Es la única opción para servicios de urgencias o partos, O
- No cuenta con estos servicios

**Criterio 2:**
- Presta servicios de internación EXCLUSIVAMENTE para salud mental

**Efecto:**
- Se incluyen "Aportes no ligados" en los ingresos operacionales

---

## PUNTOS CRÍTICOS A VERIFICAR

### ⚠️ Antes de calcular:

1. **Fecha de corte:** Todos los datos al 31 de diciembre
2. **Recaudado vs Reconocido:** Para ingresos operacionales usar RECAUDADO
3. **Comprometido:** Para gastos usar COMPROMETIDO (no pagado)
4. **Nivel correcto:** Verificar nivel de atención registrado
5. **Cartera radicada:** Solo incluir cartera en proceso de cobro
6. **Clasificación días:** Respetar los rangos según nivel

### ⚠️ Durante el cálculo:

1. **No incluir:**
   - Cartera castigada
   - Provisiones de cartera
   - Pasivos provisionados sin obligación legal
   
2. **Sí incluir:**
   - Toda la cartera radicada y legalizada
   - Todos los pasivos exigibles > 1 año
   - Todos los conceptos de ingresos/gastos en ejecución presupuestal

### ⚠️ Después del cálculo:

1. **Validar coherencia:**
   - ¿Los porcentajes de proyección son los correctos?
   - ¿El índice de riesgo tiene sentido con la situación financiera?
   - ¿La categorización corresponde al índice?

2. **Verificar criterio (e):**
   - Si hay déficit presupuestal → AUTOMÁTICAMENTE RIESGO ALTO
   - Prevalece sobre cualquier otra categoría

---

## PROGRAMA DE SANEAMIENTO

### ¿Cuándo es obligatorio?

- Categorización en RIESGO MEDIO
- Categorización en RIESGO ALTO

### ¿Cuándo NO es obligatorio?

- Categorización SIN RIESGO
- Categorización en RIESGO BAJO

### Plazo de adopción:

**60 días calendario** desde la comunicación oficial del MSPS

### Consecuencia de NO adoptar:

- Causal de INTERVENCIÓN por la Superintendencia Nacional de Salud
- Investigaciones por organismos de vigilancia y control

---

## ERRORES FRECUENTES

❌ **Error 1:** Usar ingresos reconocidos en vez de recaudados
✅ **Correcto:** Usar ingresos efectivamente RECAUDADOS

❌ **Error 2:** Clasificar mal la cartera por nivel
✅ **Correcto:** Nivel 1 (90 días), Niveles 2-3 (180 días)

❌ **Error 3:** No aplicar los porcentajes de proyección
✅ **Correcto:** Aplicar 80%, 70%/75%, 50% según corresponda

❌ **Error 4:** Incluir cartera incobrable
✅ **Correcto:** Solo cartera radicada en proceso de cobro

❌ **Error 5:** Ignorar el déficit presupuestal
✅ **Correcto:** Déficit presupuestal = RIESGO ALTO automático

---

## CONTACTOS ÚTILES

**Ministerio de Salud y Protección Social**
- Línea: 330 5000 (Bogotá)
- Nacional: 018000 952525

**Dirección Territorial de Salud**
- Contactar oficina departamental correspondiente

**Superintendencia Nacional de Salud**
- www.supersalud.gov.co

---

## MARCO NORMATIVO

- **Resolución 2509 de 2012:** Metodología de categorización
- **Ley 1438 de 2011:** Artículos 80, 81 y 83
- **Decreto 2193 de 2004:** Reporte de información
- **Contaduría General de la Nación:** Plan de cuentas

---

**Documento de referencia rápida**  
**Versión:** 1.0  
**Fecha:** Febrero 2026
