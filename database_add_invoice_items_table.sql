-- Tabla de items de facturas (invoice_items)
-- Esta tabla almacena cada item/línea de las facturas
CREATE TABLE IF NOT EXISTS invoice_items (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    company_id TEXT NOT NULL REFERENCES companies(chat_id) ON DELETE CASCADE,
    
    item_number INTEGER NOT NULL,
    description TEXT,
    quantity DECIMAL(12, 4),
    unit TEXT,
    unit_price DECIMAL(12, 2),
    total_price DECIMAL(12, 2),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para mejorar performance
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_company_id ON invoice_items(company_id);

-- Trigger para updated_at
CREATE TRIGGER update_invoice_items_updated_at BEFORE UPDATE ON invoice_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security
ALTER TABLE invoice_items ENABLE ROW LEVEL SECURITY;

-- Política de acceso
CREATE POLICY "Allow service role full access to invoice_items" ON invoice_items
    FOR ALL USING (true);

-- Verificar que la tabla se creó
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'invoice_items'
ORDER BY ordinal_position;
