# GUÍA PARA OBTENER DATOS DEL SIHO
## Calculadora de Riesgo ESE - Resolución 2509 de 2012

---

## INFORMACIÓN GENERAL

**Sistema:** SIHO (Sistema de Información Hospitalario)  
**Corte de información:** 31 de diciembre de la vigencia anterior  
**Responsable:** Área financiera y presupuestal de la ESE  
**Reporte al MSPS:** A través de las Direcciones Territoriales de Salud

---

## 1. INGRESOS OPERACIONALES CORRIENTES RECAUDADOS

### 1.1 Ingresos por venta de servicios de salud (RECAUDADOS)

**Ruta en SIHO:**
```
Menú Principal → Presupuesto → Ejecución Presupuestal
→ Ingresos → Ingresos Recaudados
```

**Pasos detallados:**
1. Ingresar al módulo de "Ejecución Presupuestal de Ingresos"
2. Seleccionar "Ingresos Recaudados" (NO reconocidos ni causados)
3. Filtrar por clasificación económica: "Ingresos Operacionales"
4. Subcategoría: "Venta de Servicios de Salud"
5. Incluir:
   - Venta de servicios POS (contributivo y subsidiado)
   - Venta de servicios NO POS
   - Eventos de alto costo
   - Tutelas
   - SOAT y accidentes de tránsito
   - Riesgos laborales
   - Servicios a particulares
6. Período: Del 01/01 al 31/12 de la vigencia
7. Exportar o tomar nota del valor TOTAL RECAUDADO

**Cuentas contables relacionadas (CGN):**
- 4.1.10 Venta de Servicios de Salud

**Valor a ingresar en la calculadora:** Total recaudado efectivamente


### 1.2 Otros ingresos corrientes (RECAUDADOS)

**Ruta en SIHO:**
```
Menú Principal → Presupuesto → Ejecución Presupuestal
→ Ingresos → Ingresos Recaudados
```

**Pasos detallados:**
1. En el mismo módulo de Ejecución Presupuestal de Ingresos
2. Seleccionar "Otros Ingresos Corrientes Recaudados"
3. Incluir:
   - Arrendamientos
   - Intereses
   - Multas y sanciones
   - Cuotas de recuperación
   - Otros ingresos operacionales
4. EXCLUIR:
   - Aportes de capital
   - Transferencias para inversión
   - Créditos y préstamos
5. Período: Del 01/01 al 31/12 de la vigencia
6. Tomar el valor TOTAL RECAUDADO

**Cuentas contables relacionadas:**
- 4.1.90 Otros Ingresos Operacionales
- 4.8.00 Otros Ingresos (solo corrientes)

**Valor a ingresar:** Total de otros ingresos corrientes recaudados


### 1.3 Aportes no ligados a ventas de servicios (SOLO PARA MERCADO ESPECIAL)

**Aplica únicamente si:**
- La ESE está en quintil más alto de dispersión poblacional Y
- Es la única opción para urgencias/partos en el municipio
- O presta servicios exclusivos de salud mental

**Ruta en SIHO:**
```
Menú Principal → Presupuesto → Ingresos Recaudados
→ Transferencias Corrientes
```

**Incluir:**
- Aportes del ente territorial no ligados a prestación de servicios
- Subsidios a la operación
- Transferencias para funcionamiento

**Valor a ingresar:** Total de aportes recaudados

---

## 2. CARTERA RADICADA (CUENTAS POR COBRAR)

### 2.1 Módulo de Cartera en SIHO

**Ruta en SIHO:**
```
Menú Principal → Cartera → Consultas e Informes
→ Antigüedad de Cartera (Aging de Cartera)
```

**Pasos detallados:**
1. Ingresar al módulo de "Cartera" o "Cuentas por Cobrar"
2. Seleccionar reporte "Antigüedad de Cartera" o "Aging"
3. Fecha de corte: 31 de diciembre de la vigencia anterior
4. Tipo de cartera: Facturación radicada y legalizada
5. Clasificar por días de antigüedad desde la fecha de radicación

### 2.2 Para NIVEL 1 de atención

**Cartera menor a 90 días:**
- Sumar todos los saldos de cartera radicada con 0 a 89 días de antigüedad
- Este valor se proyectará al 80% para el cálculo

**Cartera entre 90 y 360 días:**
- Sumar saldos con 90 a 360 días de antigüedad
- Este valor se proyectará al 70% para el cálculo

**Cartera mayor a 360 días:**
- Sumar saldos con más de 360 días de antigüedad
- Este valor se proyectará al 50% para el cálculo

### 2.3 Para NIVEL 2 y 3 de atención

**Cartera menor a 180 días:**
- Sumar todos los saldos de cartera radicada con 0 a 179 días de antigüedad
- Este valor se proyectará al 80% para el cálculo

**Cartera entre 180 y 360 días:**
- Sumar saldos con 180 a 360 días de antigüedad
- Este valor se proyectará al 75% para el cálculo

**Cartera mayor a 360 días:**
- Sumar saldos con más de 360 días de antigüedad
- Este valor se proyectará al 50% para el cálculo

**Cuentas contables relacionadas:**
- 1.3.12 Prestación de Servicios de Salud
- 1.3.84 Otras cuentas por cobrar

**IMPORTANTE:** Solo incluir cartera radicada y en proceso de cobro. NO incluir:
- Cartera glosada no aceptada
- Cartera castigada
- Provisiones

---

## 3. GASTOS OPERACIONALES CORRIENTES COMPROMETIDOS

### 3.1 Gastos de funcionamiento (COMPROMETIDOS)

**Ruta en SIHO:**
```
Menú Principal → Presupuesto → Ejecución Presupuestal
→ Gastos → Gastos Comprometidos
```

**Pasos detallados:**
1. Ingresar al módulo "Ejecución Presupuestal de Gastos"
2. Seleccionar "Gastos Comprometidos" (NO solo los pagados)
3. Clasificación: "Gastos de Funcionamiento"
4. Incluir:
   - Gastos de personal (nómina y prestaciones)
   - Gastos generales
   - Transferencias corrientes
5. Período: Del 01/01 al 31/12 de la vigencia
6. Tomar el valor TOTAL COMPROMETIDO

**Cuentas del plan de cuentas:**
- Grupo 5.1 Administración
- Gastos de personal
- Gastos generales
- Impuestos, tasas y contribuciones

**Valor a ingresar:** Total gastos de funcionamiento comprometidos


### 3.2 Gastos de operación comercial y prestación de servicios (COMPROMETIDOS)

**Ruta en SIHO:**
```
Menú Principal → Presupuesto → Ejecución Presupuestal
→ Gastos → Gastos Comprometidos
```

**Incluir:**
1. Personal asistencial y médico
2. Medicamentos y material médico-quirúrgico
3. Dispositivos médicos
4. Reactivos y material de laboratorio
5. Combustibles y lubricantes
6. Servicios públicos
7. Mantenimiento de equipos médicos
8. Alimentación de pacientes
9. Aseo y lavandería
10. Servicios de apoyo diagnóstico contratados

**Cuentas del plan de cuentas:**
- Grupo 5.2 Prestación de Servicios de Salud
- 5.2.01 a 5.2.99

**Valor a ingresar:** Total gastos de operación comprometidos

---

## 4. PASIVOS CON ANTIGÜEDAD MAYOR A UN AÑO

### 4.1 Obtención desde Balance General

**Ruta en SIHO:**
```
Menú Principal → Contabilidad → Informes Contables
→ Balance General → Pasivos por Antigüedad
```

**Pasos detallados:**
1. Generar Balance General al 31 de diciembre
2. Ir a la sección de "Pasivos"
3. Solicitar reporte por antigüedad o fecha de origen
4. Filtrar pasivos adquiridos en vigencias anteriores
5. Incluir TODOS los pasivos con antigüedad > 1 año:
   - Cuentas por pagar a proveedores
   - Obligaciones laborales
   - Acreedores
   - Pasivos estimados (cesantías, vacaciones)
   - Otros pasivos

### 4.2 Ruta alternativa - Módulo de Cuentas por Pagar

**Ruta en SIHO:**
```
Menú Principal → Tesorería → Cuentas por Pagar
→ Informe de Antigüedad de Cuentas por Pagar
```

**Filtros:**
- Pasivos con fecha de causación anterior al 31/12 del año anterior
- Estado: Pendientes de pago
- Todas las clasificaciones

**Cuentas contables relacionadas:**
- 2.4 Cuentas por pagar
- 2.5 Obligaciones laborales
- 2.7 Pasivos estimados

**Valor a ingresar:** Suma total de pasivos con más de un año de antigüedad

---

## 5. EJECUCIÓN PRESUPUESTAL TOTAL DE LA VIGENCIA

### 5.1 Total de ingresos RECONOCIDOS

**Ruta en SIHO:**
```
Menú Principal → Presupuesto → Ejecución Presupuestal
→ Ingresos → Ingresos Reconocidos
```

**Pasos:**
1. Generar reporte de "Ingresos Reconocidos" (NO recaudados)
2. Incluir TODOS los conceptos de ingresos:
   - Operacionales
   - Transferencias
   - Venta de activos
   - Recursos de capital
   - Todos los rubros del presupuesto
3. Período: Del 01/01 al 31/12 de la vigencia
4. Tomar el GRAN TOTAL de ingresos reconocidos

**Valor a ingresar:** Total ingresos reconocidos (todos los conceptos)


### 5.2 Total de gastos COMPROMETIDOS

**Ruta en SIHO:**
```
Menú Principal → Presupuesto → Ejecución Presupuestal
→ Gastos → Gastos Comprometidos
```

**Pasos:**
1. Generar reporte de "Gastos Comprometidos"
2. Incluir TODOS los conceptos de gastos:
   - Funcionamiento
   - Inversión
   - Servicio de la deuda
   - Todos los rubros del presupuesto
3. Período: Del 01/01 al 31/12 de la vigencia
4. Tomar el GRAN TOTAL de gastos comprometidos

**Valor a ingresar:** Total gastos comprometidos (todos los conceptos)

---

## PUNTOS IMPORTANTES

### ✓ Verificaciones antes de iniciar

1. **Corte de información:** Todos los datos deben ser al 31 de diciembre
2. **Consistencia:** Los valores deben coincidir con el reporte anual al MSPS
3. **Conciliación:** Verificar que coincidan contabilidad y presupuesto
4. **Validación:** Los datos deben estar validados por la Dirección Territorial

### ✓ Diferencias importantes

**RECONOCIDO vs RECAUDADO:**
- **Reconocido:** Derecho adquirido (causado), aunque no se haya cobrado
- **Recaudado:** Dinero efectivamente ingresado a la caja

**COMPROMETIDO vs PAGADO:**
- **Comprometido:** Obligación adquirida (firmada), aunque no se haya pagado
- **Pagado:** Dinero efectivamente desembolsado

### ✓ Errores comunes a evitar

1. ❌ Confundir valores reconocidos con recaudados
2. ❌ No clasificar correctamente la cartera por días
3. ❌ Incluir cartera castigada en las proyecciones
4. ❌ Mezclar datos de diferentes vigencias
5. ❌ No considerar las condiciones especiales de mercado
6. ❌ Usar datos del nivel de atención incorrecto

### ✓ Documentación de respaldo

Conservar para auditoría:
- Reporte de ejecución presupuestal certificado
- Balance general certificado
- Aging de cartera detallado
- Certificación de ingresos recaudados
- Certificación de gastos comprometidos
- Acta de validación de datos ante Dirección Territorial

---

## CONTACTOS Y SOPORTE

**Soporte SIHO:**  
Proveedor del sistema o Ministerio de Salud

**Asesoría metodológica:**  
Dirección Territorial de Salud correspondiente

**Normatividad:**  
- Resolución 2509 de 2012 (Ministerio de Salud y Protección Social)
- Decreto 2193 de 2004 (Reporte de información)

---

## FLUJO DE TRABAJO RECOMENDADO

```
1. Preparar cierre contable al 31 de diciembre
   ↓
2. Generar reportes certificados del SIHO
   ↓
3. Validar consistencia de información
   ↓
4. Consolidar datos en formato requerido
   ↓
5. Ejecutar calculadora de riesgo
   ↓
6. Revisar resultados con comité financiero
   ↓
7. Reportar a Dirección Territorial
   ↓
8. Recibir categorización oficial del MSPS
   ↓
9. Si aplica, elaborar Programa de Saneamiento
```

---

**Última actualización:** Febrero 2026  
**Versión del documento:** 1.0
