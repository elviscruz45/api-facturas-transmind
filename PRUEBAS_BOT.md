# 🧪 Guía de Pruebas - Bot de Telegram

## Pre-requisitos

1. Bot de Telegram configurado con BotFather
2. Token en `.env` como `TELEGRAM_BOT_TOKEN`
3. Supabase configurado con todas las tablas
4. Al menos 1-2 facturas ya procesadas en la base de datos

---

## ✅ Plan de Pruebas

### 1. Comandos Básicos

#### `/start`

**Objetivo:** Verificar registro de empresa

**Pasos:**

1. Abre Telegram y busca tu bot
2. Envía `/start`
3. Verifica que recibas mensaje de bienvenida
4. Revisa en Supabase tabla `companies` que se creó tu registro

**Resultado esperado:**

```
✅ ¡Bienvenido al Bot de Facturas!

Tu empresa ha sido registrada exitosamente.

📸 Envía una foto de tu factura para procesarla
💡 Usa /ayuda para ver todos los comandos
```

---

#### `/ayuda`

**Objetivo:** Verificar documentación completa

**Pasos:**

1. Envía `/ayuda`
2. Verifica que se muestre toda la documentación

**Resultado esperado:**

- Sección de procesamiento de facturas
- Todos los comandos de consulta
- Comandos de búsqueda
- Gestión de facturas
- Consejos para PYMEs

---

### 2. Procesamiento de Facturas

#### Procesar Foto

**Objetivo:** Verificar flujo completo de procesamiento

**Pasos:**

1. Toma una foto clara de una factura física
2. Envía la foto al bot
3. Espera mensaje de confirmación
4. Haz clic en "✅ Sí, procesar"
5. Espera el Excel generado

**Resultado esperado:**

```
📸 Foto recibida!

¿Quieres que procese esta imagen?

[✅ Sí, procesar] [❌ No, cancelar]
```

Luego:

```
⏳ Procesando tu factura...
```

Finalmente:

```
✅ Factura procesada exitosamente

💰 Total: PEN 1,250.00
📊 IGV: PEN 190.00
📄 Nro: F001-12345

[factura_20260115_143022.xlsx]
```

---

### 3. Comandos de Consulta

#### `/resumen DD-MM-YYYY DD-MM-YYYY`

**Prueba 1: Periodo con facturas**

```
/resumen 01-01-2026 31-01-2026
```

**Resultado esperado:**

```
⏳ Consultando facturas...

📊 Resumen de Gastos
📅 Periodo: 01-01-2026 - 31-01-2026

💰 Total: PEN 15,450.00
📄 Subtotal: PEN 13,093.22
💵 IGV: PEN 2,356.78

📋 Facturas: 12
📈 Promedio: PEN 1,287.50

[resumen_01-01-2026_31-01-2026.xlsx]
📎 Resumen detallado en Excel
```

**Prueba 2: Periodo sin facturas**

```
/resumen 01-06-2025 30-06-2025
```

**Resultado esperado:**

```
📭 No hay facturas entre 01-06-2025 y 30-06-2025
```

**Prueba 3: Formato incorrecto**

```
/resumen 2026-01-01 2026-01-31
```

**Resultado esperado:**

```
❌ Formato de fecha inválido.

Usa: DD-MM-YYYY
Ejemplo: /resumen 01-01-2026 31-01-2026
```

---

#### `/proveedores [mes]`

**Prueba 1: Mes actual**

```
/proveedores
```

**Resultado esperado:**

```
⏳ Analizando proveedores...

🏪 Top Proveedores 01-2026

1. Sodimac
   💰 PEN 4,500.00 (29.1%)
   📄 4 factura(s)
   🆔 RUC: 20123456789

2. Oechsle
   💰 PEN 3,200.00 (20.7%)
   📄 3 factura(s)
   🆔 RUC: 20987654321

3. Tottus
   💰 PEN 2,800.00 (18.1%)
   📄 5 factura(s)
   🆔 RUC: 20111222333

💰 Total periodo: PEN 15,450.00
```

**Prueba 2: Mes específico**

```
/proveedores 12-2025
```

**Prueba 3: Rango de fechas**

```
/proveedores 01-01-2026 15-01-2026
```

---

#### `/estadisticas [mes]`

**Prueba 1: Mes con datos**

```
/estadisticas 01-2026
```

**Resultado esperado:**

```
📊 Generando estadísticas...

📊 Estadísticas 01/2026

💰 Total gastado: PEN 15,450.00
📄 Facturas: 12
📈 Promedio: PEN 1,287.50

🔝 Día con más gastos:
   2026-01-15 - PEN 3,450.00

🏪 Top 3 Proveedores:
   1. Sodimac - PEN 4,500.00
   2. Oechsle - PEN 3,200.00
   3. Tottus - PEN 2,800.00
```

---

#### `/comparar [mes1] [mes2]`

**Prueba 1: Comparar meses**

```
/comparar 01-2026 12-2025
```

**Resultado esperado (más gasto):**

```
📊 Comparando periodos...

📊 Comparación de Periodos

📅 Periodo 1: 01/2026
   💰 PEN 15,450.00 (12 facturas)

📅 Periodo 2: 12/2025
   💰 PEN 12,300.00 (10 facturas)

📈 Diferencia:
   ⬆️ +PEN 3,150.00 (+25.6%)
   ⚠️ Gastaste MÁS en 01/2026
```

**Resultado esperado (menos gasto):**

```
📈 Diferencia:
   ⬇️ -PEN 2,500.00 (-16.2%)
   ✅ Gastaste MENOS en 01/2026
```

---

### 4. Comandos de Búsqueda

#### `/buscar [término]`

**Prueba 1: Buscar por número**

```
/buscar F001-12345
```

**Resultado esperado:**

```
🔍 Buscando 'F001-12345'...

📄 Facturas encontradas: 1
🔍 Búsqueda: 'F001-12345'

1. F001-12345
   📅 2026-01-15
   🏪 Sodimac
   💰 PEN 1,250.00
```

**Prueba 2: Buscar por proveedor**

```
/buscar Sodimac
```

**Prueba 3: Buscar por RUC**

```
/buscar 20123456789
```

---

#### `/items [producto]`

**Prueba 1: Buscar producto**

```
/items laptop
```

**Resultado esperado:**

```
🔍 Buscando items con 'laptop'...

💼 Items encontrados: 3
🔍 Búsqueda: 'laptop'

1. Laptop HP 15-dy2021la
   📅 2026-01-10 | F001-00123
   🏪 Oechsle
   📦 Cant: 1 x S/ 2,499.00 = S/ 2,499.00

2. Laptop Lenovo IdeaPad 3
   📅 2025-12-20 | F002-00456
   🏪 Sodimac
   📦 Cant: 1 x S/ 1,899.00 = S/ 1,899.00

3. Laptop Dell Inspiron
   📅 2025-11-15 | F001-00789
   🏪 Tottus
   📦 Cant: 1 x S/ 2,299.00 = S/ 2,299.00

💰 Total gastado: S/ 6,697.00
```

**Prueba 2: Items de un mes**

```
/items 01-2026
```

---

#### `/historial [cantidad]`

**Prueba 1: Historial por defecto**

```
/historial
```

**Resultado esperado:**

```
📚 Consultando últimas 10 facturas...

📚 Últimas 10 facturas

1. F001-12350
   📅 2026-01-15 | 🏪 Sodimac
   💰 PEN 1,250.00

2. F002-08921
   📅 2026-01-14 | 🏪 Oechsle
   💰 PEN 890.00

...
```

**Prueba 2: Cantidad específica**

```
/historial 20
```

---

### 5. Gestión de Facturas

#### `/eliminar`

**Prueba 1: Eliminar factura**

**Pasos:**

1. Envía `/eliminar`
2. Verifica que se muestren últimas 5 facturas con botones
3. Haz clic en una factura
4. Verifica mensaje de confirmación
5. Haz clic en "⚠️ Sí, eliminar"
6. Verifica confirmación final

**Resultado esperado (paso 1):**

```
🗑️ Selecciona factura a eliminar:

⚠️ Esta acción se puede revertir contactando al administrador.

[🗑️ F001-12345 - Sodimac - S/ 1250]
[🗑️ F002-08921 - Oechsle - S/ 890]
[🗑️ F001-12346 - Tottus - S/ 650]
[🗑️ F003-00111 - Metro - S/ 1420]
[🗑️ F001-12347 - Plaza Vea - S/ 340]
[❌ Cancelar]
```

**Resultado esperado (paso 3):**

```
⚠️ ¿Estás seguro?

Esta factura será marcada como eliminada.
Puedes recuperarla contactando al administrador.

[⚠️ Sí, eliminar] [❌ No, cancelar]
```

**Resultado esperado (paso 5):**

```
✅ Factura eliminada exitosamente
```

**Prueba 2: Cancelar eliminación**

1. Envía `/eliminar`
2. Haz clic en "❌ Cancelar"

**Resultado esperado:**

```
❌ Operación cancelada
```

---

## 🐛 Casos de Error a Probar

### 1. Formatos Incorrectos

#### Fecha inválida

```
/resumen 32-01-2026 31-01-2026
/resumen 01-13-2026 31-13-2026
```

**Resultado esperado:**

```
❌ Formato de fecha inválido.

Usa: DD-MM-YYYY
Ejemplo: /resumen 01-01-2026 31-01-2026
```

#### Rango inválido

```
/resumen 31-01-2026 01-01-2026
```

**Resultado esperado:**

```
❌ La fecha de inicio debe ser anterior a la fecha de fin.
```

### 2. Argumentos Faltantes

```
/resumen
/comparar 01-2026
/buscar
/items
```

**Resultado esperado:**
Cada comando debe mostrar mensaje de ayuda con formato correcto.

### 3. Base de Datos Desconectada

**Simular:** Detén Supabase temporalmente

**Resultado esperado:**

```
❌ Servicio de base de datos no disponible.
```

---

## 📊 Verificación en Supabase

Después de cada comando, verifica en Supabase:

### Tabla `companies`

- Chat ID registrado
- Campo `usage` incrementado

### Tabla `invoices`

- Facturas guardadas correctamente
- Campo `deleted_at` NULL para activas
- Campo `deleted_at` con timestamp para eliminadas

### Tabla `invoice_items`

- Items de cada factura guardados
- Relación correcta con `invoice_id`

### Tabla `processing_records`

- Registros de cada procesamiento
- Campos `total_files`, `success_files`, `error_files` correctos

---

## 🎯 Checklist de Prueba Completa

### Comandos Básicos

- [ ] `/start` - Registro exitoso
- [ ] `/ayuda` - Documentación completa

### Procesamiento

- [ ] Foto → Confirmación → Procesamiento → Excel
- [ ] Cancelar procesamiento funciona
- [ ] Datos guardados en Supabase

### Consultas

- [ ] `/resumen` con fechas válidas
- [ ] `/resumen` con periodo vacío
- [ ] `/proveedores` mes actual
- [ ] `/proveedores` mes específico
- [ ] `/estadisticas` con datos
- [ ] `/comparar` dos meses

### Búsqueda

- [ ] `/buscar` por número
- [ ] `/buscar` por proveedor
- [ ] `/buscar` por RUC
- [ ] `/items` por producto
- [ ] `/items` por mes
- [ ] `/historial` cantidad por defecto
- [ ] `/historial` cantidad específica

### Gestión

- [ ] `/eliminar` con confirmación
- [ ] `/eliminar` cancelar
- [ ] Factura marcada como `deleted_at` en DB

### Errores

- [ ] Formato de fecha incorrecto
- [ ] Argumentos faltantes
- [ ] Periodo sin datos
- [ ] Términos de búsqueda sin resultados

---

## 📝 Reporte de Pruebas

Después de ejecutar las pruebas, completa:

**Fecha:** ******\_\_\_******

**Comandos Probados:** **\_** / 9

**Errores Encontrados:**

- [ ] Ninguno
- [ ] Errores menores (documentar abajo)
- [ ] Errores críticos (documentar abajo)

**Notas:**

```
[Espacio para notas sobre comportamiento inesperado]
```

**Estado Final:**

- [ ] ✅ Listo para producción
- [ ] ⚠️ Requiere ajustes menores
- [ ] ❌ Requiere correcciones importantes

---

## 🚀 Siguiente Paso

Una vez que todas las pruebas pasen:

1. Documenta cualquier comportamiento inesperado
2. Ajusta los mensajes de ayuda si es necesario
3. Considera deployment a Cloud Run
4. Implementa webhooks para mayor eficiencia
