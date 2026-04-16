-- 057: Wipe embeddings legacy generados con text-embedding-004
--
-- Contexto: en la migración de text-embedding-004 → gemini-embedding-001
-- (agent/embeddings.py) los vectores antiguos quedaron en un espacio vectorial
-- distinto al que produce el modelo nuevo, haciendo que la similitud coseno
-- devuelva ruido. Además ahora L2-normalizamos (requisito de MRL truncado).
--
-- Esta migración:
--   1. Relaja memories.embedding para que pueda ser NULL.
--   2. Pone NULL en todos los embeddings existentes (memories y contacts).
--
-- Después de correr esta migración, ejecutar scripts/reembed_memories.py
-- para regenerar los embeddings a partir del texto original (memories.summary
-- y contacts.summary).

-- 1. memories.embedding: permitir NULL (antes era NOT NULL)
ALTER TABLE memories ALTER COLUMN embedding DROP NOT NULL;

-- 2. Borrar embeddings viejos — se regenerarán con scripts/reembed_memories.py
UPDATE memories SET embedding = NULL WHERE embedding IS NOT NULL;
UPDATE contacts SET summary_embedding = NULL WHERE summary_embedding IS NOT NULL;

-- 3. Validar que la RPC search_memories_by_embedding filtra IS NOT NULL
--    (ya lo hace desde la migración 028 pero dejamos comentario para referencia)
