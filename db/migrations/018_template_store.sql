-- Migration 018: Template Store — frameworks, verticales, templates, objectives, lead_scores
-- Sistema de plantillas para generar agentes pre-configurados

-- 1. Frameworks de calificación
CREATE TABLE IF NOT EXISTS qualification_frameworks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    best_for TEXT,
    steps JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Verticales de industria
CREATE TABLE IF NOT EXISTS industry_verticals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    default_framework_slug TEXT REFERENCES qualification_frameworks(slug),
    custom_fields JSONB DEFAULT '[]',
    objections JSONB DEFAULT '[]',
    terminology JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Objetivos predefinidos
CREATE TABLE IF NOT EXISTS agent_objectives (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    requires_framework BOOLEAN DEFAULT true,
    compatible_directions TEXT[] DEFAULT '{inbound,outbound}',
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Plantillas de agentes
CREATE TABLE IF NOT EXISTS agent_templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    vertical_slug TEXT REFERENCES industry_verticals(slug),
    framework_slug TEXT REFERENCES qualification_frameworks(slug),
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    objective TEXT NOT NULL,
    direction TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    greeting TEXT,
    farewell TEXT,
    qualification_steps JSONB NOT NULL,
    scoring_tiers JSONB NOT NULL DEFAULT '[
        {"tier": "hot", "min_score": 70, "action": "transfer_human", "label": "Lead caliente"},
        {"tier": "warm", "min_score": 40, "action": "schedule_followup", "label": "Lead tibio"},
        {"tier": "cold", "min_score": 0, "action": "nurturing", "label": "Lead frio"}
    ]',
    rules JSONB DEFAULT '[]',
    tone_description TEXT,
    outbound_opener TEXT,
    outbound_permission TEXT,
    tags TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(vertical_slug, slug)
);

CREATE INDEX IF NOT EXISTS idx_templates_vertical ON agent_templates(vertical_slug, is_active);
CREATE INDEX IF NOT EXISTS idx_templates_direction ON agent_templates(direction);

-- 5. Lead scores
CREATE TABLE IF NOT EXISTS lead_scores (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    contact_id UUID,
    agent_id UUID REFERENCES agents(id),
    total_score INTEGER DEFAULT 0,
    tier TEXT DEFAULT 'cold',
    captured_data JSONB DEFAULT '{}',
    qualification_steps_completed JSONB DEFAULT '[]',
    source_channel TEXT,
    source_template_id UUID REFERENCES agent_templates(id),
    status TEXT DEFAULT 'new',
    assigned_to TEXT,
    notes TEXT,
    first_contact_at TIMESTAMPTZ DEFAULT NOW(),
    last_contact_at TIMESTAMPTZ DEFAULT NOW(),
    converted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lead_scores_client ON lead_scores(client_id, tier, status);
CREATE INDEX IF NOT EXISTS idx_lead_scores_agent ON lead_scores(agent_id, created_at DESC);

-- ═══════════════════════════════════════════════════════
-- DATOS INICIALES
-- ═══════════════════════════════════════════════════════

-- Objetivos
INSERT INTO agent_objectives (slug, name, description, icon, requires_framework, compatible_directions, sort_order) VALUES
    ('qualify_leads', 'Calificar leads', 'Evaluar prospectos y clasificarlos por potencial de compra', '🎯', true, '{inbound,outbound}', 1),
    ('schedule_appointments', 'Agendar citas', 'Gestionar agendamiento de citas, visitas o reuniones', '📅', false, '{inbound,outbound}', 2),
    ('customer_support', 'Atender soporte', 'Responder preguntas frecuentes y resolver dudas', '💬', false, '{inbound}', 3),
    ('follow_up', 'Seguimiento a prospectos', 'Recontactar prospectos que no cerraron', '🔄', true, '{outbound}', 4),
    ('collections', 'Cobranza amable', 'Recordar pagos pendientes de forma profesional', '💰', false, '{outbound}', 5),
    ('reminders', 'Recordatorios', 'Avisar de citas, eventos o fechas importantes', '⏰', false, '{outbound}', 6),
    ('reception', 'Recepcion general', 'Atender llamadas entrantes y dirigir al area correcta', '📞', false, '{inbound}', 7)
ON CONFLICT (slug) DO NOTHING;

-- Frameworks
INSERT INTO qualification_frameworks (slug, name, description, best_for, steps, sort_order) VALUES
('bant', 'BANT', 'Budget, Authority, Need, Timeline. El framework clasico de calificacion de ventas.', 'Ventas directas, servicios, educacion', '[
    {"id":"budget","letter":"B","name":"Budget","purpose":"Determinar si tiene presupuesto","generic_questions":["Tienes un presupuesto definido para esto?","Cual es tu rango de inversion?"],"score_rules":{"defined":25,"undefined":-5}},
    {"id":"authority","letter":"A","name":"Authority","purpose":"Identificar si es el decisor","generic_questions":["Tu tomarias la decision?","Alguien mas participa en la decision?"],"score_rules":{"is_decider":20,"not_decider":5}},
    {"id":"need","letter":"N","name":"Need","purpose":"Descubrir la necesidad real","generic_questions":["Que es lo que necesitas exactamente?","Que problema intentas resolver?"],"score_rules":{"specific":15,"vague":5}},
    {"id":"timeline","letter":"T","name":"Timeline","purpose":"Determinar urgencia","generic_questions":["Para cuando lo necesitas?","Tienes una fecha limite?"],"score_rules":{"urgent":30,"soon":15,"exploring":5}}
]'::jsonb, 1),
('champ', 'CHAMP', 'Challenges, Authority, Money, Prioritization. Empieza por el dolor, no por el dinero. Ideal para Latam.', 'Inmobiliaria, salud, servicios premium, Latam', '[
    {"id":"challenges","letter":"C","name":"Challenges","purpose":"Descubrir el problema o necesidad","generic_questions":["Que es lo que estas buscando?","Que situacion intentas resolver?"],"score_rules":{"specific":15,"vague":5}},
    {"id":"authority","letter":"A","name":"Authority","purpose":"Identificar decisor","generic_questions":["Tu tomarias la decision o lo ves con alguien mas?"],"score_rules":{"is_decider":20,"not_decider":5}},
    {"id":"money","letter":"M","name":"Money","purpose":"Rango de inversion","generic_questions":["Tienes un rango de inversion en mente?"],"score_rules":{"defined":25,"undefined":-5}},
    {"id":"priority","letter":"P","name":"Prioritization","purpose":"Urgencia y prioridad","generic_questions":["Que tan pronto necesitas resolverlo?","Es prioridad ahorita?"],"score_rules":{"urgent":30,"soon":15,"exploring":5}}
]'::jsonb, 2),
('spin', 'SPIN', 'Situation, Problem, Implication, Need-Payoff. Venta consultiva que lleva al prospecto a descubrir su necesidad.', 'B2B, servicios de alto valor, consultoria', '[
    {"id":"situation","letter":"S","name":"Situation","purpose":"Entender situacion actual","generic_questions":["Como manejas esto actualmente?","Cuentame sobre tu situacion actual"],"score_rules":{"detailed":10,"brief":5}},
    {"id":"problem","letter":"P","name":"Problem","purpose":"Identificar problemas","generic_questions":["Que desafios tienes con eso?","Que te gustaria mejorar?"],"score_rules":{"clear_pain":20,"no_pain":5}},
    {"id":"implication","letter":"I","name":"Implication","purpose":"Mostrar consecuencias","generic_questions":["Que pasa si no lo resuelves?","Como afecta a tu negocio?"],"score_rules":{"aware":15,"unaware":5}},
    {"id":"need_payoff","letter":"N","name":"Need-Payoff","purpose":"Visualizar beneficio","generic_questions":["Como te beneficiaria resolver esto?","Que cambiaria para ti?"],"score_rules":{"motivated":20,"indifferent":5}}
]'::jsonb, 3),
('simple', 'Simple', 'Solo captura datos basicos. Sin scoring complejo. Para soporte o recepcion.', 'Soporte, recepcion, FAQs', '[
    {"id":"identify","letter":"","name":"Identificar","purpose":"Obtener datos basicos","generic_questions":["Me puedes dar tu nombre?","En que te puedo ayudar?"],"score_rules":{}},
    {"id":"need","letter":"","name":"Necesidad","purpose":"Entender que necesita","generic_questions":["Que necesitas?","Como te puedo ayudar?"],"score_rules":{}}
]'::jsonb, 4)
ON CONFLICT (slug) DO NOTHING;

-- Verticales
INSERT INTO industry_verticals (slug, name, description, icon, default_framework_slug, custom_fields, objections, terminology, sort_order) VALUES
('inmobiliaria', 'Inmobiliaria', 'Bienes raices: casas, departamentos, terrenos, locales comerciales', '🏠', 'champ',
    '[{"key":"tipo_propiedad","label":"Tipo de propiedad","type":"text"},{"key":"recamaras","label":"Recamaras","type":"number"},{"key":"zona","label":"Zona preferida","type":"text"},{"key":"presupuesto_min","label":"Presupuesto minimo","type":"number"},{"key":"presupuesto_max","label":"Presupuesto maximo","type":"number"},{"key":"metros_cuadrados","label":"Metros cuadrados","type":"number"},{"key":"amenidades","label":"Amenidades deseadas","type":"text"}]'::jsonb,
    '[{"trigger":"solo estoy viendo","keywords":["solo viendo","nomas viendo","explorando"],"response":"Perfecto, sin compromiso. Te gustaria que te avise cuando haya algo en tu zona ideal?"},{"trigger":"es muy caro","keywords":["caro","mucho dinero","no alcanza","fuera de presupuesto"],"response":"Entiendo. Tenemos opciones en diferentes rangos. Cual seria un monto comodo para ti?"},{"trigger":"tengo que consultarlo","keywords":["consultarlo","pensar","ver con mi pareja","mi esposa","mi esposo"],"response":"Claro, es una decision importante. Te gustaria agendar una visita para que lo vean juntos?"},{"trigger":"ya tengo asesor","keywords":["ya tengo","otro asesor","ya me atienden"],"response":"Entiendo. Si en algun momento necesitas una segunda opinion o ver opciones diferentes, aqui estamos para ti."}]'::jsonb,
    '{"property":"propiedad","buyer":"comprador","visit":"visita","price":"precio de lista"}'::jsonb, 1),

('educacion', 'Educacion', 'Colegios, universidades, cursos, academias', '🎓', 'bant',
    '[{"key":"nivel_educativo","label":"Nivel educativo","type":"text"},{"key":"grado","label":"Grado","type":"text"},{"key":"nombre_alumno","label":"Nombre del alumno","type":"text"},{"key":"ciclo_escolar","label":"Ciclo escolar","type":"text"},{"key":"colegiatura_rango","label":"Rango de colegiatura","type":"text"},{"key":"transporte","label":"Necesita transporte","type":"boolean"},{"key":"becas","label":"Interesado en becas","type":"boolean"}]'::jsonb,
    '[{"trigger":"es muy cara la colegiatura","keywords":["cara","colegiatura","costoso","no alcanza"],"response":"Entiendo tu preocupacion. Contamos con planes de pago y opciones de becas. Te gustaria conocer los detalles?"},{"trigger":"necesito pensarlo","keywords":["pensarlo","consultarlo","ver otras opciones"],"response":"Claro, es una decision importante para la familia. Te puedo agendar una visita al campus para que conozcan las instalaciones y resuelvan dudas?"},{"trigger":"queda lejos","keywords":["lejos","distancia","ubicacion"],"response":"Tenemos servicio de transporte escolar que cubre varias zonas. Te gustaria saber si tu zona esta incluida?"}]'::jsonb,
    '{"tuition":"colegiatura","enrollment":"inscripcion","campus":"campus","student":"alumno"}'::jsonb, 2),

('salud', 'Salud', 'Clinicas, consultorios, hospitales, laboratorios', '🏥', 'simple',
    '[{"key":"tipo_servicio","label":"Tipo de servicio","type":"text"},{"key":"especialidad","label":"Especialidad","type":"text"},{"key":"tiene_seguro","label":"Tiene seguro medico","type":"boolean"},{"key":"aseguradora","label":"Aseguradora","type":"text"},{"key":"urgencia","label":"Es urgente","type":"boolean"},{"key":"horario_preferido","label":"Horario preferido","type":"text"}]'::jsonb,
    '[{"trigger":"cuanto cuesta la consulta","keywords":["cuesta","precio","costo","consulta"],"response":"El costo varia segun la especialidad. Te gustaria que te de la informacion de la especialidad que necesitas?"},{"trigger":"aceptan mi seguro","keywords":["seguro","aseguradora","cobertura"],"response":"Trabajamos con varias aseguradoras. Cual es tu aseguradora para verificar?"},{"trigger":"es urgente","keywords":["urgente","emergencia","dolor fuerte","grave"],"response":"Entiendo que es urgente. Te puedo agendar la cita mas proxima disponible o te comunico directamente con el area de urgencias."}]'::jsonb,
    '{"appointment":"cita","doctor":"doctor/a","consultation":"consulta","patient":"paciente"}'::jsonb, 3),

('servicios', 'Servicios Profesionales', 'Abogados, contadores, consultores, agencias, freelancers', '💼', 'champ',
    '[{"key":"tipo_servicio","label":"Servicio que necesita","type":"text"},{"key":"descripcion_caso","label":"Descripcion del caso","type":"text"},{"key":"presupuesto","label":"Presupuesto","type":"text"},{"key":"urgencia","label":"Urgencia","type":"text"},{"key":"intentos_previos","label":"Ha intentado resolverlo antes","type":"text"}]'::jsonb,
    '[{"trigger":"es muy caro","keywords":["caro","costoso","precio","presupuesto"],"response":"Entiendo. Nuestros precios reflejan la calidad del servicio. Tenemos diferentes paquetes que se ajustan a diferentes necesidades. Te gustaria conocerlos?"},{"trigger":"necesito pensarlo","keywords":["pensarlo","considerarlo","no estoy seguro"],"response":"Claro, toma tu tiempo. Te puedo enviar una propuesta detallada por correo para que lo revises con calma?"},{"trigger":"otro profesional me cobra menos","keywords":["mas barato","otro","competencia","menos"],"response":"Cada profesional tiene su enfoque. Lo importante es la experiencia y los resultados. Te gustaria conocer nuestros casos de exito?"}]'::jsonb,
    '{"quote":"cotizacion","service":"servicio","case":"caso","client":"cliente"}'::jsonb, 4),

('restaurantes', 'Restaurantes y Hospitalidad', 'Restaurantes, hoteles, catering, bares, cafeterias', '🍽️', 'simple',
    '[{"key":"tipo_evento","label":"Tipo de evento","type":"text"},{"key":"num_personas","label":"Numero de personas","type":"number"},{"key":"fecha","label":"Fecha deseada","type":"text"},{"key":"hora","label":"Hora preferida","type":"text"},{"key":"restricciones","label":"Restricciones alimenticias","type":"text"},{"key":"presupuesto_por_persona","label":"Presupuesto por persona","type":"text"}]'::jsonb,
    '[{"trigger":"no tienen mesa","keywords":["no hay mesa","lleno","no tienen espacio"],"response":"Entiendo, ese horario esta muy solicitado. Tengo disponibilidad a las [hora alternativa]. Te funcionaria? Tambien puedo ponerte en lista de espera."},{"trigger":"es muy caro","keywords":["caro","precio","costoso"],"response":"Tenemos opciones para diferentes presupuestos. Te gustaria conocer nuestro menu del dia o paquetes para grupos?"}]'::jsonb,
    '{"reservation":"reservacion","table":"mesa","menu":"menu","guest":"comensal"}'::jsonb, 5),

('automotriz', 'Automotriz', 'Agencias de autos, talleres, refacciones, seguros de auto', '🚗', 'bant',
    '[{"key":"tipo_vehiculo","label":"Tipo de vehiculo","type":"text"},{"key":"marca_modelo","label":"Marca y modelo","type":"text"},{"key":"anio","label":"Anio","type":"text"},{"key":"nuevo_usado","label":"Nuevo o usado","type":"text"},{"key":"presupuesto","label":"Presupuesto","type":"text"},{"key":"forma_pago","label":"Forma de pago","type":"text"},{"key":"tiene_auto_cambio","label":"Auto a cuenta","type":"boolean"}]'::jsonb,
    '[{"trigger":"esta caro","keywords":["caro","precio","mucho"],"response":"Tenemos planes de financiamiento con mensualidades accesibles. Te gustaria que te haga una cotizacion personalizada?"},{"trigger":"tengo que ver mas opciones","keywords":["otras opciones","comparar","otros","otra agencia"],"response":"Claro, es bueno comparar. Te puedo enviar una cotizacion detallada para que la tengas como referencia. Que te parece?"},{"trigger":"no tengo enganche","keywords":["enganche","inicial","no tengo"],"response":"Tenemos planes sin enganche o con enganche minimo. Te gustaria conocer las opciones de financiamiento?"}]'::jsonb,
    '{"vehicle":"vehiculo","test_drive":"prueba de manejo","financing":"financiamiento","trade_in":"auto a cuenta"}'::jsonb, 6),

('gimnasios', 'Gimnasios y Fitness', 'Gimnasios, crossfit, yoga, pilates, entrenadores personales', '💪', 'champ',
    '[{"key":"objetivo_fitness","label":"Objetivo fitness","type":"text"},{"key":"experiencia","label":"Nivel de experiencia","type":"text"},{"key":"horario_preferido","label":"Horario preferido","type":"text"},{"key":"lesiones","label":"Lesiones o limitaciones","type":"text"},{"key":"presupuesto_mensual","label":"Presupuesto mensual","type":"text"}]'::jsonb,
    '[{"trigger":"es caro","keywords":["caro","precio","mensualidad"],"response":"Tenemos diferentes planes que se ajustan a cada presupuesto. Ademas, tu primera semana de prueba es gratuita para que veas si te gusta."},{"trigger":"no tengo tiempo","keywords":["tiempo","ocupado","horario"],"response":"Tenemos clases desde las 6am hasta las 10pm. Muchos de nuestros miembros trabajan y encuentran su horario ideal. Cual seria tu horario disponible?"},{"trigger":"ya intente y no funciono","keywords":["no funciono","deje","abandone","no sirve"],"response":"Es muy comun. La diferencia es tener un plan personalizado y acompanamiento. Te gustaria una sesion de evaluacion gratuita con un entrenador?"}]'::jsonb,
    '{"membership":"membresia","trainer":"entrenador","class":"clase","trial":"prueba gratuita"}'::jsonb, 7)
ON CONFLICT (slug) DO NOTHING;

-- Templates iniciales
INSERT INTO agent_templates (vertical_slug, framework_slug, slug, name, description, objective, direction, agent_role, greeting, farewell, qualification_steps, scoring_tiers, rules, tone_description, tags, sort_order) VALUES
('inmobiliaria', 'champ', 'calificar_leads_inbound', 'Calificador de Leads Inbound', 'Califica prospectos que llaman interesados en propiedades usando CHAMP', 'Calificar prospectos entrantes y clasificarlos por potencial de compra', 'inbound', 'Asesor inmobiliario digital',
'Gracias por comunicarte con nosotros. Estoy aqui para ayudarte a encontrar tu propiedad ideal. Que tipo de propiedad te interesa?',
'Fue un gusto atenderte. Cualquier duda adicional, aqui estamos para ayudarte.',
'[{"id":"challenges","framework_step":"C","purpose":"Descubrir que tipo de propiedad busca","questions":["Que tipo de propiedad te interesa? Casa, departamento, terreno?","Cuantas recamaras necesitas?","Que zona de la ciudad prefieres?"],"extract_fields":["tipo_propiedad","recamaras","zona"],"score_rules":{"specific_need":{"points":15,"condition":"Da detalles claros"},"vague":{"points":5,"condition":"Respuestas vagas"}},"tips":"No hagas las 3 preguntas seguidas. Integralas naturalmente."},{"id":"authority","framework_step":"A","purpose":"Saber si decide solo","questions":["La decision la tomarias tu o la ves con tu pareja o familia?"],"extract_fields":["es_decisor"],"score_rules":{"is_decider":{"points":20,"condition":"Decide solo"},"not_decider":{"points":5,"condition":"Consulta con otros"}},"tips":"Si no es decisor, sugiere que vengan juntos a visitar."},{"id":"money","framework_step":"M","purpose":"Rango de inversion","questions":["Tienes un rango de inversion en mente?","Te pregunto para mostrarte solo opciones que apliquen."],"extract_fields":["presupuesto_min","presupuesto_max"],"score_rules":{"defined":{"points":25,"condition":"Da rango claro"},"undefined":{"points":-5,"condition":"No quiere decir"}},"tips":"Justifica: para no mostrar opciones fuera de rango."},{"id":"priority","framework_step":"P","purpose":"Urgencia","questions":["Para cuando estas buscando mudarte?"],"extract_fields":["timeline"],"score_rules":{"urgent":{"points":30,"condition":"Este mes"},"soon":{"points":15,"condition":"1-3 meses"},"exploring":{"points":5,"condition":"Solo explorando"}},"tips":"La urgencia predice conversion."}]'::jsonb,
'[{"tier":"hot","min_score":70,"action":"transfer_human","label":"Lead caliente"},{"tier":"warm","min_score":40,"action":"schedule_followup","label":"Lead tibio"},{"tier":"cold","min_score":0,"action":"nurturing","label":"Lead frio"}]'::jsonb,
'["Nunca inventar propiedades que no existen","Nunca dar precios sin consultar catalogo","Nunca presionar para cerrar","Si pide hablar con humano, transferir inmediato","Maximo 2 preguntas seguidas, luego aporta valor"]'::jsonb,
'Profesional pero cercano. Conocedor del mercado. Nunca presiona.', '{qualify_leads,inmobiliaria}', 1),

('inmobiliaria', 'spin', 'seguimiento_outbound', 'Seguimiento a Prospectos', 'Recontacta prospectos que mostraron interes pero no cerraron', 'Reactivar prospectos frios y agendar visitas', 'outbound', 'Asesor inmobiliario de seguimiento',
NULL, 'Gracias por tu tiempo. Que tengas excelente dia.',
'[{"id":"situation","framework_step":"S","purpose":"Recordar contacto previo","questions":["Te llamo porque hace poco mostraste interes en propiedades en [zona]. Sigues buscando?"],"extract_fields":["sigue_buscando"],"score_rules":{"yes":{"points":20,"condition":"Sigue interesado"},"no":{"points":0,"condition":"Ya no busca"}},"tips":"Menciona algo especifico de su busqueda anterior."},{"id":"problem","framework_step":"P","purpose":"Identificar que lo detuvo","questions":["Que te ha impedido avanzar?","Hubo algo que no te convencio de las opciones anteriores?"],"extract_fields":["obstaculo"],"score_rules":{"clear":{"points":15,"condition":"Identifica obstaculo claro"},"none":{"points":5,"condition":"No identifica"}},"tips":"Escucha sin juzgar."},{"id":"implication","framework_step":"I","purpose":"Crear urgencia suave","questions":["Has visto como se han movido los precios en esa zona?"],"extract_fields":[],"score_rules":{"concerned":{"points":15,"condition":"Le preocupa"},"indifferent":{"points":0,"condition":"No le importa"}},"tips":"No presionar. Solo informar."},{"id":"need_payoff","framework_step":"N","purpose":"Ofrecer valor concreto","questions":["Tenemos nuevas opciones que podrian interesarte. Te gustaria verlas?"],"extract_fields":["quiere_ver"],"score_rules":{"interested":{"points":20,"condition":"Quiere ver"},"not_now":{"points":5,"condition":"Ahora no"}},"tips":"Ofrece algo concreto, no generico."}]'::jsonb,
'[{"tier":"hot","min_score":50,"action":"schedule_followup","label":"Reactivado"},{"tier":"warm","min_score":25,"action":"nurturing","label":"Interesado leve"},{"tier":"cold","min_score":0,"action":"archive","label":"No interesado"}]'::jsonb,
'["Justificar la llamada en los primeros 10 segundos","Pedir permiso para continuar","Si dice que no le interesa, agradecer y no insistir","Nunca mentir sobre nuevas opciones"]'::jsonb,
'Respetuoso del tiempo. No vendedor. Informativo.', '{follow_up,inmobiliaria}', 2),

('educacion', 'bant', 'inscripciones_inbound', 'Atencion a Inscripciones', 'Atiende familias interesadas en inscribir a sus hijos', 'Informar sobre el colegio, calificar interes y agendar visita al campus', 'inbound', 'Asistente de admisiones',
'Gracias por tu interes en nuestro colegio. Estoy aqui para darte toda la informacion que necesites. En que grado estas buscando inscripcion?',
'Fue un gusto atenderte. Esperamos verte pronto en nuestro campus.',
'[{"id":"need","framework_step":"N","purpose":"Nivel educativo y grado","questions":["Para que nivel buscas? Preescolar, primaria, secundaria, preparatoria?","Para que grado seria?","Cuantos hijos inscribirias?"],"extract_fields":["nivel_educativo","grado","nombre_alumno"],"score_rules":{"specific":{"points":15,"condition":"Sabe exactamente que nivel y grado"},"exploring":{"points":5,"condition":"Esta explorando opciones"}},"tips":"Pregunta el nombre del alumno para personalizar."},{"id":"budget","framework_step":"B","purpose":"Expectativa de colegiatura","questions":["Tienes un rango de colegiatura en mente?","Nuestras colegiaturas van desde [rango]. Te parece dentro de tu presupuesto?"],"extract_fields":["colegiatura_rango"],"score_rules":{"fits":{"points":25,"condition":"El rango le funciona"},"concerned":{"points":10,"condition":"Le preocupa el precio"},"no_budget":{"points":-5,"condition":"Muy fuera de rango"}},"tips":"Menciona becas y planes de pago si muestra preocupacion."},{"id":"authority","framework_step":"A","purpose":"Quien decide","questions":["Tu tomarias la decision o la ves con tu pareja?"],"extract_fields":["es_decisor"],"score_rules":{"decider":{"points":20,"condition":"Decide"},"consults":{"points":5,"condition":"Consulta"}},"tips":"Invita a ambos a la visita."},{"id":"timeline","framework_step":"T","purpose":"Para que ciclo","questions":["Seria para el proximo ciclo escolar o para este?"],"extract_fields":["ciclo_escolar"],"score_rules":{"this_cycle":{"points":30,"condition":"Este ciclo o el proximo inmediato"},"next_year":{"points":10,"condition":"Para despues"},"unsure":{"points":5,"condition":"No sabe"}},"tips":"Si es para este ciclo, crear urgencia de cupo."}]'::jsonb,
'[{"tier":"hot","min_score":70,"action":"schedule_visit","label":"Visita al campus"},{"tier":"warm","min_score":40,"action":"send_info","label":"Enviar informacion"},{"tier":"cold","min_score":0,"action":"nurturing","label":"Seguimiento"}]'::jsonb,
'["Nunca garantizar disponibilidad de cupo sin verificar","Ser honesto sobre costos","Invitar siempre a conocer el campus","No hablar mal de otros colegios"]'::jsonb,
'Calido, confiable. Transmite orgullo por la institucion sin ser arrogante.', '{qualify_leads,schedule_appointments,educacion}', 1)
ON CONFLICT (vertical_slug, slug) DO NOTHING;
