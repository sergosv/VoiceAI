-- Atomic increment for usage_daily (prevents race condition on concurrent call finalization)
CREATE OR REPLACE FUNCTION increment_usage_daily(
    p_client_id UUID,
    p_date DATE,
    p_calls INT DEFAULT 1,
    p_minutes NUMERIC DEFAULT 0,
    p_cost NUMERIC DEFAULT 0
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO usage_daily (client_id, date, total_calls, total_minutes, total_cost)
    VALUES (p_client_id, p_date, p_calls, p_minutes, p_cost)
    ON CONFLICT (client_id, date)
    DO UPDATE SET
        total_calls = usage_daily.total_calls + EXCLUDED.total_calls,
        total_minutes = usage_daily.total_minutes + EXCLUDED.total_minutes,
        total_cost = usage_daily.total_cost + EXCLUDED.total_cost;
END;
$$;

-- Atomic increment for WhatsApp/GHL conversation message_count
CREATE OR REPLACE FUNCTION increment_message_count(
    p_table_name TEXT,
    p_conversation_id UUID,
    p_increment INT DEFAULT 1
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_table_name = 'whatsapp_conversations' THEN
        UPDATE whatsapp_conversations
        SET message_count = COALESCE(message_count, 0) + p_increment,
            last_message_at = NOW()
        WHERE id = p_conversation_id;
    ELSIF p_table_name = 'ghl_conversations' THEN
        UPDATE ghl_conversations
        SET message_count = COALESCE(message_count, 0) + p_increment,
            last_message_at = NOW()
        WHERE id = p_conversation_id;
    ELSE
        RAISE EXCEPTION 'Invalid table name: %', p_table_name;
    END IF;
END;
$$;
