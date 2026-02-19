# 📊 Explicación del Schema de Base de Datos

## ✅ Respuesta directa a tu pregunta:

### **¿Deberían ser solo 2 tablas?**

**SÍ, solo necesitas 2 tablas principales:**

1. **`invoices`** - Almacena la información principal de cada factura
2. **`invoice_items`** - Almacena los items/líneas de cada factura

_(Opcionalmente una 3ra tabla `companies` para tracking por teléfono/usuario)_

---

## 🔄 Mapeo de Datos: JSON Response → Tablas

### Endpoint: `/process-image-url` o `/process-pdf-url`

**Response JSON:**

```json
{
  "jobId": "job_1708291200000",
  "status": "success",
  "phoneNumber": "+51987654321",
  "data": {
    "invoice_number": "F001-00012345",
    "invoice_date": "2024-02-15",
    "supplier_name": "EMPRESA PROVEEDORA SAC",
    "supplier_ruc": "20123456789",
    "customer_name": "MI EMPRESA SRL",
    "subtotal": 1000.0,
    "tax": 180.0,
    "total": 1180.0,
    "currency": "PEN",
    "confidence_score": 0.95,
    "items": [
      {
        "description": "Producto A",
        "quantity": 10.0,
        "unit": "UND",
        "unit_price": 100.0,
        "total_price": 1000.0
      },
      {
        "description": "Servicio B",
        "quantity": 1.0,
        "unit": "SRV",
        "unit_price": 180.0,
        "total_price": 180.0
      }
    ]
  },
  "error": null
}
```

**Se convierte en:**

### Tabla `invoices` (1 fila):

```sql
INSERT INTO invoices (
    job_id,
    company_id,
    invoice_number,
    invoice_date,
    supplier_name,
    supplier_ruc,
    customer_name,
    subtotal,
    tax,
    total,
    currency,
    confidence_score,
    source_file,
    source_url,
    mime_type,
    processing_status,
    sequence_id
) VALUES (
    'job_1708291200000',        -- jobId
    '+51987654321',              -- phoneNumber
    'F001-00012345',             -- data.invoice_number
    '2024-02-15',                -- data.invoice_date
    'EMPRESA PROVEEDORA SAC',    -- data.supplier_name
    '20123456789',               -- data.supplier_ruc
    'MI EMPRESA SRL',            -- data.customer_name
    1000.00,                     -- data.subtotal
    180.00,                      -- data.tax
    1180.00,                     -- data.total
    'PEN',                       -- data.currency
    0.95,                        -- data.confidence_score
    'invoice_20240215.pdf',      -- request.filename
    'https://api.whatsapp.com/...', -- request.mediaUrl
    'application/pdf',           -- request.mimeType
    'success',                   -- status
    1                            -- sequence_id (siempre 1 para archivos individuales)
) RETURNING id;  -- Retorna el ID para insertar los items
```

### Tabla `invoice_items` (2 filas, una por cada item):

```sql
-- Asumiendo que el INSERT anterior retornó invoice_id = 123

INSERT INTO invoice_items (
    invoice_id,
    company_id,
    item_number,
    description,
    quantity,
    unit,
    unit_price,
    total_price
) VALUES
-- Item 1
(
    123,                         -- ID de la factura insertada
    '+51987654321',              -- phoneNumber
    1,                           -- Posición en el array
    'Producto A',                -- data.items[0].description
    10.0,                        -- data.items[0].quantity
    'UND',                       -- data.items[0].unit
    100.00,                      -- data.items[0].unit_price
    1000.00                      -- data.items[0].total_price
),
-- Item 2
(
    123,
    '+51987654321',
    2,
    'Servicio B',
    1.0,
    'SRV',
    180.00,
    180.00
);
```

---

## 🏗️ Estructura de las Tablas

### 📋 Tabla: `invoices`

| Campo               | Tipo          | Descripción                     | Origen JSON             |
| ------------------- | ------------- | ------------------------------- | ----------------------- |
| `id`                | BIGSERIAL     | ID único auto-generado          | -                       |
| `job_id`            | TEXT          | Identificador del job           | `response.jobId`        |
| `company_id`        | TEXT          | Número de teléfono              | `request.phoneNumber`   |
| `record_id`         | UUID          | NULL para archivos individuales | -                       |
| `invoice_number`    | TEXT          | Número de factura               | `data.invoice_number`   |
| `invoice_date`      | DATE          | Fecha de emisión                | `data.invoice_date`     |
| `supplier_name`     | TEXT          | Nombre del proveedor            | `data.supplier_name`    |
| `supplier_ruc`      | TEXT          | RUC del proveedor               | `data.supplier_ruc`     |
| `customer_name`     | TEXT          | Nombre del cliente              | `data.customer_name`    |
| `customer_ruc`      | TEXT          | RUC del cliente                 | `data.customer_ruc`     |
| `subtotal`          | DECIMAL(15,2) | Subtotal sin IGV                | `data.subtotal`         |
| `tax`               | DECIMAL(15,2) | IGV (impuesto)                  | `data.tax`              |
| `total`             | DECIMAL(15,2) | Total con IGV                   | `data.total`            |
| `currency`          | TEXT          | Moneda (PEN, USD)               | `data.currency`         |
| `confidence_score`  | DECIMAL(4,3)  | Score de confianza (0-1)        | `data.confidence_score` |
| `source_file`       | TEXT          | Nombre del archivo              | `request.filename`      |
| `source_url`        | TEXT          | URL del medio                   | `request.mediaUrl`      |
| `mime_type`         | TEXT          | Tipo MIME                       | `request.mimeType`      |
| `processing_status` | TEXT          | 'success' o 'error'             | `response.status`       |
| `error_message`     | TEXT          | Mensaje de error                | `response.error`        |
| `sequence_id`       | INTEGER       | Secuencia (1 para individuales) | -                       |
| `created_at`        | TIMESTAMPTZ   | Fecha de creación               | Auto                    |
| `updated_at`        | TIMESTAMPTZ   | Fecha de actualización          | Auto                    |

### 📦 Tabla: `invoice_items`

| Campo         | Tipo          | Descripción            | Origen JSON                 |
| ------------- | ------------- | ---------------------- | --------------------------- |
| `id`          | BIGSERIAL     | ID único auto-generado | -                           |
| `invoice_id`  | BIGINT        | FK a invoices.id       | -                           |
| `company_id`  | TEXT          | Número de teléfono     | `request.phoneNumber`       |
| `item_number` | INTEGER       | Posición en el array   | Array index + 1             |
| `description` | TEXT          | Descripción del item   | `data.items[i].description` |
| `quantity`    | DECIMAL(12,4) | Cantidad               | `data.items[i].quantity`    |
| `unit`        | TEXT          | Unidad de medida       | `data.items[i].unit`        |
| `unit_price`  | DECIMAL(15,2) | Precio unitario        | `data.items[i].unit_price`  |
| `total_price` | DECIMAL(15,2) | Precio total del item  | `data.items[i].total_price` |
| `created_at`  | TIMESTAMPTZ   | Fecha de creación      | Auto                        |
| `updated_at`  | TIMESTAMPTZ   | Fecha de actualización | Auto                        |

---

## 🔍 Consultas Útiles

### Ver todas las facturas con sus items:

```sql
SELECT
    i.job_id,
    i.invoice_number,
    i.invoice_date,
    i.supplier_name,
    i.total,
    i.currency,
    COUNT(ii.id) as total_items
FROM invoices i
LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
WHERE i.deleted = FALSE
GROUP BY i.id
ORDER BY i.created_at DESC;
```

### Ver detalle completo de una factura:

```sql
SELECT
    i.invoice_number,
    i.invoice_date,
    i.supplier_name,
    i.total,
    ii.item_number,
    ii.description,
    ii.quantity,
    ii.unit,
    ii.unit_price,
    ii.total_price
FROM invoices i
LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
WHERE i.job_id = 'job_1708291200000'
ORDER BY ii.item_number;
```

### Facturas por teléfono (usuario):

```sql
SELECT
    company_id as phone_number,
    COUNT(*) as total_facturas,
    SUM(total) as monto_total,
    AVG(confidence_score) as confianza_promedio
FROM invoices
WHERE deleted = FALSE
  AND processing_status = 'success'
GROUP BY company_id
ORDER BY total_facturas DESC;
```

---

## ✨ Ventajas de este Diseño

### ✅ **2 tablas principales es suficiente porque:**

1. **Normalización correcta**: Evita duplicación de datos
2. **Compatible con ambos flujos**:
   - Archivos individuales (`/process-image-url`, `/process-pdf-url`)
   - Procesamiento batch (`/process-zip`)
3. **Escalable**: Puedes agregar millones de facturas sin problemas
4. **Búsquedas eficientes**: Índices optimizados en campos clave
5. **Integridad referencial**: Items siempre están ligados a su factura
6. **Auditoría completa**: Timestamps automáticos

### 📊 **Relación de las tablas:**

```
companies (opcional)
    ↓ (1:N)
invoices
    ↓ (1:N)
invoice_items
```

Una factura puede tener **0 o más items**.

---

## 🚀 Siguiente Paso: Implementación

Ahora necesitas:

1. **Ejecutar el SQL** en Supabase:

   ```bash
   # Ir a Supabase Dashboard > SQL Editor
   # Pegar el contenido de database_schema_single_files.sql
   # Ejecutar
   ```

2. **Actualizar los endpoints** para guardar los datos:
   - `/process-image-url` → guardar en DB
   - `/process-pdf-url` → guardar en DB

3. **Crear funciones en `supabase_service.py`**:
   ```python
   async def save_single_invoice(
       job_id: str,
       phone_number: str,
       invoice_data: dict,
       status: str,
       ...
   ) -> Optional[int]:
       # Guardar invoice y retornar ID
       # Guardar items si existen
   ```

¿Quieres que te ayude con la implementación de los métodos de Python? 🐍
