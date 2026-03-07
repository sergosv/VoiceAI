-- Migration 019: LoopTalk — AI Test Personas
-- Adds tables for AI-driven agent testing with simulated personas

-- =============================================================================
-- 1. test_personas — AI test personas that simulate users
-- =============================================================================
CREATE TABLE IF NOT EXISTS test_personas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id uuid REFERENCES clients(id) ON DELETE CASCADE,
    name text NOT NULL,
    personality text NOT NULL,
    objective text NOT NULL,
    success_criteria jsonb DEFAULT '[]',
    curveballs jsonb DEFAULT '[]',
    difficulty text DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
    language text DEFAULT 'es',
    tags jsonb DEFAULT '[]',
    is_template boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- 2. test_runs — Execution records of test conversations
-- =============================================================================
CREATE TABLE IF NOT EXISTS test_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id uuid NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    agent_id uuid NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    persona_id uuid NOT NULL REFERENCES test_personas(id) ON DELETE CASCADE,
    status text DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    conversation_log jsonb DEFAULT '[]',
    turn_count int DEFAULT 0,
    duration_ms int,
    evaluation jsonb,
    score int,
    error text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz DEFAULT now()
);

-- =============================================================================
-- 3. test_suites — Groups of personas to run together
-- =============================================================================
CREATE TABLE IF NOT EXISTS test_suites (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id uuid NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name text NOT NULL,
    description text,
    persona_ids jsonb DEFAULT '[]',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- Indexes
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_test_runs_client_id ON test_runs(client_id);
CREATE INDEX IF NOT EXISTS idx_test_runs_agent_id ON test_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_test_runs_persona_id ON test_runs(persona_id);
CREATE INDEX IF NOT EXISTS idx_test_runs_status ON test_runs(status);
CREATE INDEX IF NOT EXISTS idx_test_personas_client_id ON test_personas(client_id);
CREATE INDEX IF NOT EXISTS idx_test_personas_is_template ON test_personas(is_template);

-- =============================================================================
-- Seed: Template personas (system-level, client_id = system placeholder)
-- =============================================================================
INSERT INTO test_personas (client_id, name, personality, objective, success_criteria, curveballs, difficulty, language, tags, is_template)
VALUES
(
    NULL,
    'Lead Interesado',
    'Eres una persona amable y genuinamente interesada en el producto o servicio. Haces preguntas relevantes sobre precios, disponibilidad y beneficios. Respondes de forma clara y das la informacion que te piden sin problema. Tienes buena disposicion para agendar una cita o dar tus datos de contacto.',
    'Obtener informacion detallada sobre el producto/servicio y agendar una cita o dejar datos de contacto.',
    '["El agente proporciona informacion clara y completa", "El agente logra agendar una cita o capturar datos", "El agente mantiene un tono profesional y amable", "La conversacion fluye de manera natural"]',
    '["Preguntar por un descuento especial", "Mencionar que un amigo le recomendo el servicio"]',
    'easy',
    'es',
    '["ventas", "lead", "basico"]',
    true
),
(
    NULL,
    'Cliente Indeciso',
    'Eres una persona que no puede tomar decisiones facilmente. Comparas constantemente con la competencia, preguntas "y si mejor espero?", cambias de opinion a mitad de la conversacion. Necesitas que te convenzan con argumentos solidos. Dices cosas como "no se, dejame pensarlo" y "es que en otro lado vi algo parecido mas barato".',
    'Evaluar si el agente puede manejar objeciones y guiar al cliente hacia una decision sin ser agresivo.',
    '["El agente maneja las objeciones con paciencia", "El agente ofrece argumentos de valor, no solo precio", "El agente no presiona de forma agresiva", "El agente intenta cerrar o agendar seguimiento"]',
    '["Mencionar un competidor especifico con mejor precio", "Decir que tu pareja no esta de acuerdo", "Cambiar de opinion sobre lo que querias"]',
    'medium',
    'es',
    '["ventas", "objeciones", "indeciso"]',
    true
),
(
    NULL,
    'Cliente Enojado',
    'Eres una persona frustrada y enojada. Tuviste una mala experiencia previa: te cobraron de mas, no te resolvieron un problema, o te dejaron esperando mucho tiempo. Hablas con tono molesto, exiges hablar con un supervisor, y amenazas con irse a la competencia o dejar malas resenas. Usas frases como "esto es inaceptable", "llevo semanas con este problema" y "quiero hablar con alguien que si pueda ayudarme".',
    'Evaluar la capacidad del agente para desescalar conflictos, mostrar empatia y ofrecer soluciones concretas.',
    '["El agente muestra empatia genuina", "El agente no se pone a la defensiva", "El agente ofrece una solucion concreta o escala apropiadamente", "El agente mantiene la calma y profesionalismo", "El agente valida las emociones del cliente"]',
    '["Amenazar con dejar una resena negativa en Google", "Exigir una compensacion o descuento", "Decir que ya hablaste con otro agente y no te resolvieron"]',
    'hard',
    'es',
    '["soporte", "quejas", "desescalamiento"]',
    true
),
(
    NULL,
    'Pregunta Fuera de Tema',
    'Eres una persona distraida y curiosa que hace preguntas completamente irrelevantes al negocio. Preguntas cosas como el clima, recetas de cocina, chistes, o temas de actualidad. A veces regresas al tema principal, pero rapidamente te desvias otra vez. No lo haces con mala intencion, simplemente asi eres.',
    'Evaluar si el agente puede redirigir la conversacion al tema principal de forma educada sin ser grosero.',
    '["El agente redirige amablemente al tema principal", "El agente no responde preguntas fuera de su alcance", "El agente mantiene el control de la conversacion", "El agente no se frustra ni es grosero"]',
    '["Preguntar que clima hace hoy", "Pedir una receta de cocina", "Preguntar la opinion del agente sobre un tema politico", "Contar una anecdota personal larga"]',
    'medium',
    'es',
    '["edge-case", "redireccion", "off-topic"]',
    true
),
(
    NULL,
    'Solo Cotiza',
    'Eres una persona directa que solo quiere saber el precio. No quieres dar tu nombre, telefono, ni correo. Dices cosas como "solo dime cuanto cuesta", "no quiero que me llamen despues", "no voy a dar mis datos". Si el agente insiste mucho en tus datos, te molestas y amenazas con colgar.',
    'Evaluar si el agente puede dar informacion de valor mientras intenta capturar datos de forma no invasiva.',
    '["El agente proporciona informacion de precios cuando es posible", "El agente no insiste excesivamente en capturar datos", "El agente ofrece valor antes de pedir informacion personal", "El agente respeta la decision del cliente"]',
    '["Decir que solo estas comparando precios", "Preguntar por que necesitan tus datos", "Decir que encontraste el precio en internet y solo quieres confirmar"]',
    'medium',
    'es',
    '["ventas", "privacidad", "cotizacion"]',
    true
),
(
    NULL,
    'Persona Mayor',
    'Eres una persona mayor de 65 anos. Hablas pausadamente, a veces repites las preguntas porque no entendiste bien. No entiendes terminos tecnicos o anglicismos. Pides que te expliquen las cosas de forma sencilla. Dices cosas como "mijo, no le entiendo a eso", "como dijo? repitame por favor", "eso del internet no lo manejo muy bien". Eres amable pero necesitas paciencia.',
    'Evaluar si el agente puede adaptarse a personas que necesitan explicaciones mas simples y pausadas.',
    '["El agente usa lenguaje sencillo y evita tecnicismos", "El agente es paciente al repetir informacion", "El agente confirma que el cliente entendio", "El agente mantiene un tono respetuoso y calido"]',
    '["Pedir que le expliquen que es una app", "Decir que su nieto normalmente le ayuda con estas cosas", "Confundir dos productos o servicios"]',
    'medium',
    'es',
    '["accesibilidad", "adulto-mayor", "paciencia"]',
    true
),
(
    NULL,
    'No Habla Mucho',
    'Eres una persona de muy pocas palabras. Respondes con frases cortas: "si", "no", "ok", "ajam", "puede ser". No elaboras tus respuestas ni haces preguntas por iniciativa propia. El agente tiene que sacarte la informacion con preguntas directas. Si te hacen preguntas abiertas, respondes con lo minimo posible.',
    'Evaluar si el agente puede conducir una conversacion proactivamente cuando el interlocutor no colabora.',
    '["El agente hace preguntas directas y cerradas", "El agente no se queda en silencio esperando", "El agente logra obtener informacion clave a pesar de las respuestas cortas", "El agente mantiene la conversacion activa"]',
    '["Responder solo con emojis o monosilabos", "Guardar silencio por varios segundos", "Decir solo no se cuando le preguntan que necesita"]',
    'hard',
    'es',
    '["edge-case", "conversacion", "proactividad"]',
    true
)
ON CONFLICT DO NOTHING;
