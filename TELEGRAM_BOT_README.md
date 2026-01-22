# Telegram Bot - Instrucciones de Uso

## 🚀 Configuración Inicial

### 1. Obtener Token del Bot

1. Abre Telegram y busca [@BotFather](https://t.me/BotFather)
2. Envía el comando `/newbot`
3. Sigue las instrucciones:
   - Nombre del bot: `Facturas Extractor Bot` (o el que prefieras)
   - Username: `tu_empresa_facturas_bot` (debe terminar en `_bot`)
4. BotFather te dará un **token** similar a: `7362518493:AAHVdP8qK2xJ9vL_h4BxYz8Fn7Q5TdEpXYz`
5. **Copia ese token**

### 2. Configurar el Token

Abre el archivo `.env` y reemplaza `your_bot_token_here` con tu token real:

```bash
TELEGRAM_BOT_TOKEN=7362518493:AAHVdP8qK2xJ9vL_h4BxYz8Fn7Q5TdEpXYz
```

### 3. Iniciar el Bot

```bash
poetry run python telegram_bot.py
```

Deberías ver:

```
🤖 Bot iniciado correctamente!
📱 Envía /start al bot para comenzar
⏹️  Presiona Ctrl+C para detener
```

## 📱 Cómo Usar el Bot

### Para Usuarios

1. **Busca tu bot** en Telegram por el username que configuraste
2. **Envía `/start`** para registrarte
3. **Envía una foto** de tu factura
4. **Confirma** haciendo clic en "✅ Sí, procesar"
5. **Recibe tu Excel** con todos los datos extraídos

### Comandos Disponibles

- `/start` - Registrar empresa y comenzar a usar el bot
- `/ayuda` - Ver instrucciones de uso

## ✨ Características

✅ **Procesamiento con confirmación** - El bot pregunta antes de procesar  
✅ **Multi-tenant** - Cada chat = una empresa diferente  
✅ **Excel automático** - Genera Excel con datos estructurados  
✅ **Base de datos** - Guarda historial en Supabase  
✅ **Cloud Storage** - Backup de archivos en GCP  
✅ **Límites por plan** - Free: 100 facturas/mes

## 🔧 Administración

### Ver Logs

Los logs se generan automáticamente y muestran:

- Registros de nuevas empresas
- Archivos procesados
- Errores de extracción
- Guardado en Supabase

### Consultar Facturas en Supabase

```sql
-- Ver todas las empresas registradas
SELECT * FROM companies;

-- Ver facturas procesadas hoy
SELECT * FROM invoices WHERE DATE(created_at) = CURRENT_DATE;

-- Ver estadísticas de una empresa
SELECT
    chat_id,
    name,
    usage,
    limit_monthly,
    (limit_monthly - usage) as remaining
FROM companies
WHERE chat_id = 'CHAT_ID_AQUI';
```

## ⚠️ Limitaciones del MVP

- ❌ **PDFs**: Solo fotos por ahora (PDF próximamente)
- ❌ **Procesamiento masivo**: Una factura a la vez
- ❌ **Edición manual**: No se puede corregir datos extraídos
- ❌ **Dashboard web**: Solo Telegram, sin interfaz web

## 🛠️ Solución de Problemas

### Error: "TELEGRAM_BOT_TOKEN no está configurado"

→ Verifica que el token esté en `.env` sin espacios

### Error: "Invalid token"

→ Copia de nuevo el token completo desde BotFather

### Error: "No pude extraer datos"

→ Asegúrate de que la foto sea clara y la factura visible

### Bot no responde

→ Verifica que `poetry run python telegram_bot.py` esté corriendo

## 📊 Estructura de Datos Guardados

### En Supabase

**companies** - Una fila por cada chat que use el bot  
**processing_records** - Una fila por cada factura procesada  
**invoices** - Datos de la factura (número, proveedor, totales)  
**invoice_items** - Items/productos de cada factura

### En Cloud Storage

**Bucket**: `facturacion-484614-invoices`  
**Path**: `{chat_id}/excel/{timestamp}_factura.xlsx`

## 🎯 Próximos Pasos

Para mejorar el bot, considera agregar:

1. ✅ Procesamiento de PDFs completo
2. ✅ Comando `/historial` para ver últimas facturas
3. ✅ Comando `/estadisticas` para ver uso mensual
4. ✅ Procesamiento por lotes (enviar múltiples fotos)
5. ✅ Edición de datos extraídos
6. ✅ Exportar a otros formatos (CSV, Google Sheets)
7. ✅ Notificaciones de límites
8. ✅ Planes premium con más límites
