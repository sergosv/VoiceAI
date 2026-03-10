-- Persistent onboarding progress tracking
ALTER TABLE clients ADD COLUMN IF NOT EXISTS onboarding_progress JSONB DEFAULT '{}';
ALTER TABLE clients ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN clients.onboarding_progress IS 'Tracks completion of onboarding steps';
COMMENT ON COLUMN clients.onboarding_completed IS 'True when all onboarding steps are done';
