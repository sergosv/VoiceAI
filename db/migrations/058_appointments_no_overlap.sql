-- 058: Prevenir double-booking de citas con EXCLUDE constraint
--
-- Contexto: `calendar_tool.schedule_appointment` hace "check conflicts → insert"
-- sin atomicidad, lo que permite que dos llamadas concurrentes al mismo
-- horario pasen la validación y ambas inserten (double-booking).
--
-- Solución: constraint EXCLUDE con btree_gist que rechaza citas confirmadas
-- que se solapen en tiempo para el mismo cliente. La tool captura el error
-- de constraint y devuelve un mensaje limpio al agente.

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE appointments
    ADD CONSTRAINT no_overlapping_appointments
    EXCLUDE USING gist (
        client_id WITH =,
        tstzrange(start_time, end_time, '[)') WITH &&
    )
    WHERE (status = 'confirmed');
