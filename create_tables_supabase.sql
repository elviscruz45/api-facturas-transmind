-- CREAR TABLAS PARA FACTURAS (Supabase)
-- Copiar y pegar todo este código en Supabase SQL Editor

-- Tabla: companies (opcional - para tracking por usuario/teléfono)
CREATE TABLE IF NOT EXISTS companies (
    chat_id TEXT PRIMARY KEY,
    name TEXT,
    plan TEXT DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    usage_current_month INTEGER DEFAULT 0,
    limit_monthly INTEGER DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_companies_plan ON companies(plan);

-- Tabla: invoices (FACTURAS - DATOS PRINCIPALES)
CREATE TABLE IF NOT EXISTS invoices (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT,
    company_id TEXT REFERENCES companies(chat_id) ON DELETE SET NULL,
    record_id UUID,
    invoice_number TEXT,
    invoice_date DATE,
    supplier_name TEXT,
    supplier_ruc TEXT,
    customer_name TEXT,
    customer_ruc TEXT,
    subtotal DECIMAL(15,2),
    tax DECIMAL(15,2),
    total DECIMAL(15,2),
    currency TEXT DEFAULT 'PEN',
    confidence_score DECIMAL(4,3),
    source_file TEXT,
    source_url TEXT,
    sequence_id INTEGER,
    mime_type TEXT,
    processing_status TEXT DEFAULT 'success' CHECK (processing_status IN ('success', 'error')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_invoices_job_id ON invoices(job_id);
CREATE INDEX IF NOT EXISTS idx_invoices_company_id ON invoices(company_id);
CREATE INDEX IF NOT EXISTS idx_invoices_record_id ON invoices(record_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date DESC);
CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoices_supplier_ruc ON invoices(supplier_ruc);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(processing_status);
CREATE INDEX IF NOT EXISTS idx_invoices_created ON invoices(created_at DESC);

-- Tabla: invoice_items (ITEMS/LÍNEAS DE LAS FACTURAS)
CREATE TABLE IF NOT EXISTS invoice_items (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    company_id TEXT REFERENCES companies(chat_id) ON DELETE SET NULL,
    item_number INTEGER NOT NULL,
    description TEXT,
    quantity DECIMAL(12,4),
    unit TEXT,
    unit_price DECIMAL(15,2),
    total_price DECIMAL(15,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_company_id ON invoice_items(company_id);

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para updated_at
CREATE TRIGGER update_invoices_updated_at 
    BEFORE UPDATE ON invoices
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_invoice_items_updated_at 
    BEFORE UPDATE ON invoice_items
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS)
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow service role full access to companies" ON companies FOR ALL USING (true);
CREATE POLICY "Allow service role full access to invoices" ON invoices FOR ALL USING (true);
CREATE POLICY "Allow service role full access to invoice_items" ON invoice_items FOR ALL USING (true);

-- Permisos
GRANT SELECT, INSERT, UPDATE ON companies TO authenticated;
GRANT SELECT, INSERT, UPDATE ON invoices TO authenticated;
GRANT SELECT, INSERT, UPDATE ON invoice_items TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
