-- Insert anonymous company for testing/development
-- This allows processing without authentication

INSERT INTO companies (chat_id, name, plan, usage, limit_monthly, active, registered_by)
VALUES ('anonymous', 'Anonymous User (Testing)', 'free', 0, 999999, true, 'system')
ON CONFLICT (chat_id) DO UPDATE SET
    active = true,
    limit_monthly = 999999;

-- Verify the company was created
SELECT * FROM companies WHERE chat_id = 'anonymous';
