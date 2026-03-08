-- Migration 024: Contact channels tracking
-- Registra por cuáles canales ha interactuado cada contacto.

ALTER TABLE contacts
  ADD COLUMN IF NOT EXISTS channels TEXT[] NOT NULL DEFAULT '{}';
