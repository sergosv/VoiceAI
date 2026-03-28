-- Migration 048: Enforce unique agent slugs
-- Previene que dos agentes tengan el mismo slug (bug crítico de seguridad:
-- un cliente podría conectarse al agente de otro cliente via widget)

-- Primero arreglar slugs duplicados existentes (agregar sufijo con id parcial)
UPDATE agents a
SET slug = a.slug || '-' || LEFT(a.id::text, 6)
WHERE a.slug IN (
    SELECT slug FROM agents GROUP BY slug HAVING COUNT(*) > 1
);

-- Agregar constraint UNIQUE
ALTER TABLE agents ADD CONSTRAINT agents_slug_unique UNIQUE (slug);
