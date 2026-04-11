-- 056: Permitir 'in_progress' en calls.status para checkpoints de transcript
-- El session_handler guarda checkpoints parciales con status='in_progress'
-- mientras la llamada está en curso, pero el CHECK constraint no lo permitía,
-- causando 91+ errores en Sentry (Error en checkpoint de transcript).

ALTER TABLE calls DROP CONSTRAINT IF EXISTS calls_status_check;

ALTER TABLE calls ADD CONSTRAINT calls_status_check
    CHECK (status IN (
        'in_progress',
        'completed',
        'failed',
        'transferred',
        'no_answer',
        'busy'
    ));
