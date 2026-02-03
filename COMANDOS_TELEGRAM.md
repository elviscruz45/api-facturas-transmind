# 📖 Guía de Comandos - Bot de Facturas para PYMEs

## 📸 Procesamiento de Facturas

### Enviar Factura (Foto)

1. Envía una foto clara de tu factura al bot
2. El bot te pedirá confirmación
3. Haz clic en **✅ Sí, procesar**
4. Recibirás un archivo Excel con los datos extraídos

**Consejos para mejores resultados:**

- Buena iluminación
- Factura completa visible
- Imagen clara y enfocada
- Evita sombras y reflejos

---

## 💰 Comandos de Consulta de Gastos

### `/resumen DD-MM-YYYY DD-MM-YYYY`

Genera un resumen completo de gastos en un periodo específico.

**Ejemplos:**

```
/resumen 01-01-2026 31-01-2026
/resumen 15-12-2025 15-01-2026
```

**Qué incluye:**

- 💰 Total gastado en el periodo
- 📄 Subtotal e IGV desglosados
- 📋 Cantidad de facturas procesadas
- 📈 Promedio por factura
- 📎 Excel con todas las facturas del periodo

**Ideal para:**

- Reportes mensuales
- Declaraciones de impuestos
- Control de presupuesto

---

### `/proveedores [mes]` o `/proveedores [inicio] [fin]`

Muestra los 10 proveedores con mayor gasto.

**Ejemplos:**

```
/proveedores 01-2026
/proveedores
/proveedores 01-01-2026 31-01-2026
```

**Qué muestra:**

- 🏪 Nombre del proveedor
- 💰 Total gastado y porcentaje
- 📄 Cantidad de facturas
- 🆔 RUC del proveedor

**Ideal para:**

- Negociar mejores precios
- Consolidar proveedores
- Identificar gastos recurrentes

---

### `/estadisticas [mes]`

Dashboard con estadísticas del mes especificado.

**Ejemplos:**

```
/estadisticas 01-2026
/estadisticas
```

**Qué incluye:**

- 💰 Total gastado en el mes
- 📄 Cantidad de facturas
- 📈 Promedio por factura
- 🔝 Día con más gastos
- 🏪 Top 3 proveedores del mes

**Ideal para:**

- Vista rápida mensual
- Identificar patrones de gasto
- Detectar días de alto gasto

---

### `/comparar [mes1] [mes2]`

Compara gastos entre dos meses.

**Ejemplos:**

```
/comparar 01-2026 12-2025
/comparar 02-2026 02-2025
```

**Qué muestra:**

- 📅 Total de cada periodo
- 📄 Cantidad de facturas
- 📈 Diferencia absoluta y porcentual
- ⚠️ Alerta si gastaste más o menos

**Ideal para:**

- Seguimiento de reducción de gastos
- Comparar temporadas
- Evaluar crecimiento del negocio

---

## 🔍 Comandos de Búsqueda

### `/buscar [término]`

Busca facturas por número, proveedor, RUC o cliente.

**Ejemplos:**

```
/buscar F001-12345
/buscar Sodimac
/buscar 20123456789
/buscar Juan Pérez
```

**Busca en:**

- 📄 Número de factura (exacto)
- 🏪 Nombre del proveedor
- 🆔 RUC del proveedor
- 👤 Nombre del cliente

**Ideal para:**

- Encontrar una factura específica
- Ver todas las compras a un proveedor
- Auditorías y verificaciones

---

### `/items [producto]` o `/items [mes]`

Busca productos y muestra su historial de precios.

**Ejemplos:**

```
/items laptop
/items cemento
/items 01-2026
```

**Qué muestra:**

- 💼 Descripción del producto
- 📅 Fecha de compra
- 🏪 Proveedor
- 📦 Cantidad y precio unitario
- 💰 Total gastado en ese item

**Ideal para:**

- Comparar precios entre proveedores
- Detectar aumentos de precio
- Controlar compras recurrentes

---

### `/historial [cantidad]`

Muestra las últimas N facturas procesadas.

**Ejemplos:**

```
/historial
/historial 10
/historial 20
```

**Qué muestra:**

- 📄 Número de factura
- 📅 Fecha
- 🏪 Proveedor
- 💰 Total

**Configuración:**

- Por defecto: 10 facturas
- Máximo: 50 facturas

**Ideal para:**

- Vista rápida de actividad reciente
- Verificar facturas procesadas
- Acceso rápido a documentos

---

## 🗑️ Gestión de Facturas

### `/eliminar`

Permite eliminar facturas con confirmación.

**Cómo funciona:**

1. Ejecuta `/eliminar`
2. El bot muestra las últimas 5 facturas
3. Selecciona la que quieres eliminar
4. Confirma la operación

**⚠️ Importante:**

- Es una eliminación suave (soft delete)
- Los datos se marcan como eliminados pero no se borran
- Puedes recuperarlos contactando al administrador
- No afecta los archivos Excel ya generados

**Ideal para:**

- Corregir facturas duplicadas
- Eliminar errores de procesamiento
- Mantener base de datos limpia

---

## ⚙️ Otros Comandos

### `/start`

Inicia el bot y registra tu empresa en el sistema.

**Qué hace:**

- Registra tu chat_id como empresa
- Crea tu perfil en la base de datos
- Muestra mensaje de bienvenida

**Importante:**

- Ejecuta esto la primera vez que uses el bot
- Necesario para guardar tus facturas

---

### `/ayuda`

Muestra esta guía de ayuda completa.

---

## 📊 Formatos de Fecha

El bot acepta varios formatos de fecha:

| Formato        | Ejemplo    | Uso                |
| -------------- | ---------- | ------------------ |
| DD-MM-YYYY     | 01-01-2026 | Fechas específicas |
| MM-YYYY        | 01-2026    | Meses completos    |
| Sin argumentos | (vacío)    | Usa el mes actual  |

---

## 💡 Consejos para PYMEs

### Control Diario

```
/historial
```

Revisa las últimas facturas procesadas cada día.

### Reporte Semanal

```
/resumen [lunes] [domingo]
```

Genera reporte de gastos semanales.

### Cierre Mensual

```
/resumen 01-01-2026 31-01-2026
/proveedores 01-2026
/estadisticas 01-2026
```

Análisis completo del mes.

### Seguimiento de Precios

```
/items [producto que compras frecuentemente]
```

Detecta si un proveedor subió precios.

### Negociación con Proveedores

```
/proveedores 01-2026
```

Identifica con quién gastas más para negociar descuentos.

### Comparación Trimestral

```
/comparar 01-2026 02-2026
/comparar 02-2026 03-2026
```

Evalúa tendencias de gasto.

---

## ❓ Preguntas Frecuentes

**P: ¿Puedo procesar facturas en PDF?**
R: Actualmente el MVP solo acepta fotos. Envía una captura de pantalla del PDF.

**P: ¿Cuántas facturas puedo procesar?**
R: En el plan gratuito no hay límite, pero está sujeto a las cuotas de Gemini (15 RPM).

**P: ¿Los datos son seguros?**
R: Sí, todo se guarda en Supabase con encriptación. Cada empresa solo ve sus propios datos.

**P: ¿Puedo exportar todos mis datos?**
R: Usa `/resumen` con un rango amplio para obtener Excel completo.

**P: ¿Qué pasa si el bot se equivoca?**
R: Usa `/eliminar` para quitar la factura incorrecta y procésala nuevamente.

**P: ¿Cómo veo gastos del año completo?**
R: Ejecuta `/resumen 01-01-2026 31-12-2026` (ajusta el año).

---

## 🆘 Soporte

Si encuentras problemas:

1. Verifica que la foto sea clara
2. Intenta con `/ayuda` para ver comandos
3. Contacta al administrador del sistema

---

## 🚀 Próximas Funcionalidades

- ✅ Procesamiento de PDFs nativos
- ✅ Gráficos y dashboards visuales
- ✅ Alertas automáticas de gastos
- ✅ Exportación a formato contable
- ✅ Integración con WhatsApp
- ✅ Reportes automáticos por email

---

**Última actualización:** Enero 2026
**Versión:** 2.0.0 - MVP con comandos avanzados
