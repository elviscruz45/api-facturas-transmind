-- Supabase Database Schema for Invoice Processing System
-- Execute this SQL in Supabase SQL Editor to create tables

-- ============================================================================
-- Table: companies
-- Purpose: Store company/tenant information for multi-tenancy
-- ============================================================================
CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY,  -- Unique identifier (e.g., Telegram chat_id)
    name TEXT NOT NULL,
    plan TEXT DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    usage_current_month INTEGER DEFAULT 0,
    limit_monthly INTEGER DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_companies_plan ON companies(plan);

-- ============================================================================
-- Table: processing_records
-- Purpose: Track each ZIP processing event
-- ============================================================================
CREATE TABLE IF NOT EXISTS processing_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id TEXT REFERENCES companies(company_id) ON DELETE SET NULL,
    zip_filename TEXT NOT NULL,
    zip_blob_path TEXT,  -- Cloud Storage path
    excel_blob_path TEXT,  -- Cloud Storage path
    total_invoices INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for querying
CREATE INDEX IF NOT EXISTS idx_processing_records_company ON processing_records(company_id);
CREATE INDEX IF NOT EXISTS idx_processing_records_date ON processing_records(processed_at DESC);

-- ============================================================================
-- Table: invoices
-- Purpose: Store individual invoice data
-- ============================================================================
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    company_id TEXT REFERENCES companies(company_id) ON DELETE SET NULL,
    record_id UUID REFERENCES processing_records(id) ON DELETE CASCADE,
    
    -- Invoice details
    invoice_number TEXT,
    invoice_date DATE,
    
    -- Supplier information
    supplier_name TEXT,
    supplier_ruc TEXT,
    
    -- Customer information
    customer_name TEXT,
    customer_ruc TEXT,
    
    -- Amounts
    subtotal DECIMAL(15,2),
    tax DECIMAL(15,2),
    total DECIMAL(15,2),
    currency TEXT DEFAULT 'PEN',
    
    -- Line items as JSONB array
    items JSONB,
    
    -- Metadata
    confidence_score DECIMAL(4,3),
    source_file TEXT,
    sequence_id INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_invoices_company ON invoices(company_id);
CREATE INDEX IF NOT EXISTS idx_invoices_record ON invoices(record_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date DESC);
CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoices_supplier_ruc ON invoices(supplier_ruc);

-- GIN index for JSONB items search
CREATE INDEX IF NOT EXISTS idx_invoices_items ON invoices USING GIN (items);

-- ============================================================================
-- PostgreSQL Function: increment_usage
-- Purpose: Atomic counter increment for company usage
-- ============================================================================
CREATE OR REPLACE FUNCTION increment_usage(
    p_company_id TEXT,
    p_count INTEGER
)
RETURNS VOID AS $$
BEGIN
    UPDATE companies
    SET usage_current_month = usage_current_month + p_count,
        updated_at = NOW()
    WHERE company_id = p_company_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PostgreSQL Function: reset_monthly_usage
-- Purpose: Reset usage counters at the start of each month
-- ============================================================================
CREATE OR REPLACE FUNCTION reset_monthly_usage()
RETURNS INTEGER AS $$
DECLARE
    rows_updated INTEGER;
BEGIN
    UPDATE companies
    SET usage_current_month = 0,
        updated_at = NOW();
    
    GET DIAGNOSTICS rows_updated = ROW_COUNT;
    RETURN rows_updated;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Row Level Security (RLS) Policies
-- Purpose: Secure multi-tenant data isolation
-- Note: Backend uses service_role key which bypasses RLS
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;

-- Policy: Companies can only see their own data
CREATE POLICY company_isolation_companies ON companies
    FOR ALL
    USING (company_id = current_setting('app.current_company_id', TRUE));

CREATE POLICY company_isolation_processing ON processing_records
    FOR ALL
    USING (company_id = current_setting('app.current_company_id', TRUE));

CREATE POLICY company_isolation_invoices ON invoices
    FOR ALL
    USING (company_id = current_setting('app.current_company_id', TRUE));

-- ============================================================================
-- Views for Analytics
-- ============================================================================

-- View: Company monthly statistics
CREATE OR REPLACE VIEW company_monthly_stats AS
SELECT 
    c.company_id,
    c.name,
    c.plan,
    c.usage_current_month,
    c.limit_monthly,
    (c.limit_monthly - c.usage_current_month) AS remaining,
    ROUND(100.0 * c.usage_current_month / NULLIF(c.limit_monthly, 0), 2) AS usage_percent
FROM companies c;

-- View: Processing summary per company
CREATE OR REPLACE VIEW processing_summary AS
SELECT 
    pr.company_id,
    c.name AS company_name,
    COUNT(pr.id) AS total_processings,
    SUM(pr.total_invoices) AS total_invoices_extracted,
    SUM(pr.success_count) AS total_success,
    SUM(pr.error_count) AS total_errors,
    MIN(pr.processed_at) AS first_processing,
    MAX(pr.processed_at) AS last_processing
FROM processing_records pr
LEFT JOIN companies c ON pr.company_id = c.company_id
GROUP BY pr.company_id, c.name;

-- ============================================================================
-- Sample Data (Optional - for testing)
-- ============================================================================

-- Insert test company
INSERT INTO companies (company_id, name, plan, limit_monthly)
VALUES ('test_company_001', 'Test Company SRL', 'pro', 500)
ON CONFLICT (company_id) DO NOTHING;

-- ============================================================================
-- Grants (for authenticated users - optional)
-- ============================================================================

-- Grant access to authenticated role (if using Supabase Auth)
GRANT SELECT, INSERT, UPDATE ON companies TO authenticated;
GRANT SELECT, INSERT ON processing_records TO authenticated;
GRANT SELECT, INSERT ON invoices TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- ============================================================================
-- Complete! Your database is ready.
-- ============================================================================

-- Verify tables were created:
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
