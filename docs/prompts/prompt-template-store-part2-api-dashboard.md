# PROMPT PARA CLAUDE CODE - Template Store y Generador de Agentes (PARTE 2 de 2)
## API + Wizard Dashboard + Templates Iniciales por Vertical

Continuacion de prompt-template-store-part1.md. Esta parte tiene: API endpoints completos, wizard del dashboard para crear agentes, y los datos iniciales de todas las verticales con sus templates.

---

## PARTE 5: API ENDPOINTS (api/routes/templates.py)

```python
"""
api/routes/templates.py - Template Store y Generador de Agentes.

Endpoints publicos (para wizard del cliente):
  GET  /templates/objectives          - Objetivos disponibles
  GET  /templates/verticals           - Verticales disponibles
  GET  /templates/frameworks          - Frameworks disponibles
  GET  /templates/search              - Buscar templates por vertical+objetivo+direccion
  POST /templates/generate            - Generar agente desde template

Endpoints admin:
  POST   /templates/admin/templates   - Crear template
  PATCH  /templates/admin/templates   - Editar template
  GET    /templates/admin/stats       - Estadisticas de uso
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from generator.main import generate_agent_from_template

router = APIRouter(prefix="/templates", tags=["templates"])


# ===== WIZARD: Paso 1 - Objetivos =====

@router.get("/objectives")
async def list_objectives():
    """Lista objetivos disponibles para el wizard."""
    result = supabase.table("agent_objectives") \
        .select("*") \
        .eq("is_active", True) \
        .order("sort_order") \
        .execute()
    return result.data or []


# ===== WIZARD: Paso 2 - Verticales =====

@router.get("/verticals")
async def list_verticals():
    """Lista verticales de industria disponibles."""
    result = supabase.table("industry_verticals") \
        .select("slug, name, description, icon, default_framework_slug, sort_order") \
        .eq("is_active", True) \
        .order("sort_order") \
        .execute()
    return result.data or []


# ===== WIZARD: Info - Frameworks =====

@router.get("/frameworks")
async def list_frameworks():
    """Lista frameworks de calificacion disponibles."""
    result = supabase.table("qualification_frameworks") \
        .select("slug, name, description, best_for, sort_order") \
        .eq("is_active", True) \
        .order("sort_order") \
        .execute()
    return result.data or []


# ===== WIZARD: Paso 3 - Buscar templates =====

@router.get("/search")
async def search_templates(
    vertical: Optional[str] = None,
    objective: Optional[str] = None,
    direction: Optional[str] = None,
):
    """
    Buscar templates filtrados por vertical, objetivo y/o direccion.
    Retorna templates con info de vertical y framework incluida.
    """
    query = supabase.table("agent_templates") \
        .select("*, industry_verticals(name, icon), qualification_frameworks(name, slug)") \
        .eq("is_active", True)

    if vertical:
        query = query.eq("vertical_slug", vertical)
    if direction and direction != "both":
        query = query.in_("direction", [direction, "both"])
    if objective:
        query = query.contains("tags", [objective])

    result = query.order("sort_order").execute()
    return result.data or []


# ===== WIZARD: Paso 4 - Preview template =====

@router.get("/preview/{template_id}")
async def preview_template(template_id: str):
    """Ver detalle completo de un template antes de generar."""
    result = supabase.table("agent_templates") \
        .select("*, industry_verticals(*), qualification_frameworks(*)") \
        .eq("id", template_id) \
        .single() \
        .execute()

    if not result.data:
        raise HTTPException(404, "Template not found")
    return result.data


# ===== WIZARD: Paso 5 - Generar agente =====

@router.post("/generate")
async def generate_agent(request: GenerateRequest):
    """
    Genera un agente completo desde un template.

    Recibe template_id + configuracion del cliente + modo.
    Retorna system prompt o flow de nodos listo para usar.
    """
    try:
        result = await generate_agent_from_template(
            supabase=supabase,
            template_id=request.template_id,
            client_config={
                "business_name": request.business_name,
                "agent_name": request.agent_name,
                "tone": request.tone,
                "custom_greeting": request.custom_greeting,
                "custom_rules": request.custom_rules or [],
                "transfer_phone": request.transfer_phone,
                "tool_calls_enabled": request.tool_calls_enabled,
            },
            mode=request.mode,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


# ===== ADMIN: Crear template =====

@router.post("/admin/templates")
async def create_template(template: CreateTemplateRequest):
    """Crear un nuevo template de agente."""
    data = template.model_dump()
    data["created_at"] = datetime.utcnow().isoformat()
    data["updated_at"] = datetime.utcnow().isoformat()

    result = supabase.table("agent_templates") \
        .insert(data) \
        .execute()
    return result.data[0] if result.data else None


# ===== ADMIN: Stats =====

@router.get("/admin/stats")
async def template_stats():
    """Estadisticas de uso de templates."""
    result = supabase.table("agent_templates") \
        .select("name, vertical_slug, usage_count, direction") \
        .eq("is_active", True) \
        .order("usage_count", desc=True) \
        .execute()
    return {
        "templates": result.data or [],
        "total_uses": sum(t.get("usage_count", 0) for t in (result.data or [])),
    }


# ===== LEAD SCORING: Dashboard data =====

@router.get("/leads/{client_id}")
async def get_leads_summary(client_id: str, days: int = 30):
    """Resumen de leads calificados para el dashboard del cliente."""
    from datetime import timedelta
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    result = supabase.table("lead_scores") \
        .select("*") \
        .eq("client_id", client_id) \
        .gte("created_at", since) \
        .order("created_at", desc=True) \
        .execute()

    leads = result.data or []
    hot = len([l for l in leads if l["tier"] == "hot"])
    warm = len([l for l in leads if l["tier"] == "warm"])
    cold = len([l for l in leads if l["tier"] == "cold"])

    return {
        "total": len(leads),
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "leads": leads,
    }


# ===== SCHEMAS =====

class GenerateRequest(BaseModel):
    template_id: str
    mode: str = "system_prompt"             # 'system_prompt' o 'builder_flow'
    business_name: str
    agent_name: str = "Asistente"
    tone: Optional[str] = None
    custom_greeting: Optional[str] = None
    custom_rules: Optional[List[str]] = None
    transfer_phone: Optional[str] = None
    tool_calls_enabled: bool = True


class CreateTemplateRequest(BaseModel):
    vertical_slug: str
    framework_slug: str
    slug: str
    name: str
    description: Optional[str] = None
    objective: str
    direction: str
    agent_role: str
    greeting: Optional[str] = None
    farewell: Optional[str] = None
    qualification_steps: list
    scoring_tiers: Optional[list] = None
    rules: Optional[list] = None
    tone_description: Optional[str] = None
    outbound_opener: Optional[str] = None
    outbound_permission: Optional[str] = None
    tags: Optional[List[str]] = None
```

---

## PARTE 6: DASHBOARD WIZARD COMPLETO (dashboard/src/pages/AgentWizard.jsx)

```jsx
import React, { useState, useEffect } from "react";
import { useAuth } from "../hooks/useAuth";

const STEPS = ["objective", "vertical", "direction", "template", "customize", "result"];

export default function AgentWizardPage() {
    const { clientId, token } = useAuth();
    const API = import.meta.env.VITE_API_URL || "";

    // State del wizard
    const [step, setStep] = useState(0);
    const [objectives, setObjectives] = useState([]);
    const [verticals, setVerticals] = useState([]);
    const [templates, setTemplates] = useState([]);
    const [generating, setGenerating] = useState(false);

    // Selecciones del usuario
    const [selectedObjective, setSelectedObjective] = useState(null);
    const [selectedVertical, setSelectedVertical] = useState(null);
    const [selectedDirection, setSelectedDirection] = useState(null);
    const [selectedTemplate, setSelectedTemplate] = useState(null);
    const [selectedMode, setSelectedMode] = useState("system_prompt");

    // Config del cliente
    const [config, setConfig] = useState({
        business_name: "",
        agent_name: "",
        tone: "",
        custom_greeting: "",
        transfer_phone: "",
    });

    // Resultado
    const [result, setResult] = useState(null);

    // Cargar datos iniciales
    useEffect(() => {
        Promise.all([
            fetch(`${API}/templates/objectives`, {
                headers: { Authorization: `Bearer ${token}` },
            }).then(r => r.json()),
            fetch(`${API}/templates/verticals`, {
                headers: { Authorization: `Bearer ${token}` },
            }).then(r => r.json()),
        ]).then(([objs, verts]) => {
            setObjectives(objs);
            setVerticals(verts);
        });
    }, []);

    // Buscar templates cuando se selecciona vertical + direccion
    useEffect(() => {
        if (selectedVertical && selectedDirection) {
            const params = new URLSearchParams({
                vertical: selectedVertical,
                direction: selectedDirection,
            });
            if (selectedObjective) params.append("objective", selectedObjective);

            fetch(`${API}/templates/search?${params}`, {
                headers: { Authorization: `Bearer ${token}` },
            })
                .then(r => r.json())
                .then(setTemplates);
        }
    }, [selectedVertical, selectedDirection, selectedObjective]);

    // Generar agente
    async function handleGenerate() {
        setGenerating(true);
        try {
            const res = await fetch(`${API}/templates/generate`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    template_id: selectedTemplate.id,
                    mode: selectedMode,
                    ...config,
                }),
            });
            const data = await res.json();
            setResult(data);
            setStep(5); // Ir al resultado
        } catch (err) {
            console.error("Generate error:", err);
            alert("Error al generar agente");
        } finally {
            setGenerating(false);
        }
    }

    function nextStep() { setStep(s => Math.min(s + 1, STEPS.length - 1)); }
    function prevStep() { setStep(s => Math.max(s - 1, 0)); }

    return (
        <div className="max-w-3xl mx-auto p-6">
            {/* Progress bar */}
            <div className="flex items-center mb-8">
                {STEPS.map((s, i) => (
                    <div key={s} className="flex items-center flex-1">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                            ${i <= step ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-500"}`}>
                            {i + 1}
                        </div>
                        {i < STEPS.length - 1 && (
                            <div className={`flex-1 h-1 mx-2 ${i < step ? "bg-blue-600" : "bg-gray-200"}`} />
                        )}
                    </div>
                ))}
            </div>

            {/* ===== PASO 1: OBJETIVO ===== */}
            {step === 0 && (
                <div>
                    <h2 className="text-2xl font-bold mb-2">Para que necesitas tu agente?</h2>
                    <p className="text-gray-500 mb-6">Selecciona el objetivo principal</p>
                    <div className="grid grid-cols-2 gap-4">
                        {objectives.map(obj => (
                            <button key={obj.slug} onClick={() => { setSelectedObjective(obj.slug); nextStep(); }}
                                className={`border rounded-xl p-4 text-left hover:border-blue-500 hover:bg-blue-50 transition
                                    ${selectedObjective === obj.slug ? "border-blue-500 bg-blue-50" : ""}`}>
                                <div className="text-2xl mb-2">{obj.icon}</div>
                                <div className="font-semibold">{obj.name}</div>
                                <div className="text-sm text-gray-500 mt-1">{obj.description}</div>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* ===== PASO 2: VERTICAL ===== */}
            {step === 1 && (
                <div>
                    <h2 className="text-2xl font-bold mb-2">Tu industria?</h2>
                    <p className="text-gray-500 mb-6">Esto personaliza las preguntas y el vocabulario del agente</p>
                    <div className="grid grid-cols-2 gap-4">
                        {verticals.map(vert => (
                            <button key={vert.slug} onClick={() => { setSelectedVertical(vert.slug); nextStep(); }}
                                className={`border rounded-xl p-4 text-left hover:border-blue-500 hover:bg-blue-50 transition
                                    ${selectedVertical === vert.slug ? "border-blue-500 bg-blue-50" : ""}`}>
                                <div className="text-2xl mb-2">{vert.icon}</div>
                                <div className="font-semibold">{vert.name}</div>
                                <div className="text-sm text-gray-500 mt-1">{vert.description}</div>
                            </button>
                        ))}
                    </div>
                    <button onClick={prevStep} className="mt-4 text-gray-500 hover:text-gray-700">Atras</button>
                </div>
            )}

            {/* ===== PASO 3: DIRECCION ===== */}
            {step === 2 && (
                <div>
                    <h2 className="text-2xl font-bold mb-2">Como llegan tus prospectos?</h2>
                    <p className="text-gray-500 mb-6">Esto cambia el tono y flujo del agente</p>
                    <div className="grid grid-cols-3 gap-4">
                        <button onClick={() => { setSelectedDirection("inbound"); nextStep(); }}
                            className="border rounded-xl p-6 text-center hover:border-blue-500 hover:bg-blue-50">
                            <div className="text-3xl mb-2">📥</div>
                            <div className="font-semibold">Inbound</div>
                            <div className="text-xs text-gray-500 mt-2">Ellos te llaman o escriben</div>
                        </button>
                        <button onClick={() => { setSelectedDirection("outbound"); nextStep(); }}
                            className="border rounded-xl p-6 text-center hover:border-blue-500 hover:bg-blue-50">
                            <div className="text-3xl mb-2">📤</div>
                            <div className="font-semibold">Outbound</div>
                            <div className="text-xs text-gray-500 mt-2">Tu los contactas</div>
                        </button>
                        <button onClick={() => { setSelectedDirection("both"); nextStep(); }}
                            className="border rounded-xl p-6 text-center hover:border-blue-500 hover:bg-blue-50">
                            <div className="text-3xl mb-2">🔄</div>
                            <div className="font-semibold">Ambos</div>
                            <div className="text-xs text-gray-500 mt-2">Inbound y outbound</div>
                        </button>
                    </div>
                    <button onClick={prevStep} className="mt-4 text-gray-500 hover:text-gray-700">Atras</button>
                </div>
            )}

            {/* ===== PASO 4: SELECCIONAR TEMPLATE + MODO ===== */}
            {step === 3 && (
                <div>
                    <h2 className="text-2xl font-bold mb-2">Elige una plantilla</h2>
                    <p className="text-gray-500 mb-6">Selecciona la que mejor se ajuste a tu necesidad</p>

                    {templates.length === 0 ? (
                        <div className="text-center text-gray-400 py-8 border rounded-xl">
                            No hay plantillas disponibles para esta combinacion. Intenta otra vertical o direccion.
                        </div>
                    ) : (
                        <div className="space-y-3 mb-8">
                            {templates.map(tpl => (
                                <button key={tpl.id}
                                    onClick={() => setSelectedTemplate(tpl)}
                                    className={`w-full border rounded-xl p-4 text-left transition
                                        ${selectedTemplate?.id === tpl.id ? "border-blue-500 bg-blue-50 ring-2 ring-blue-200" : "hover:border-gray-300"}`}>
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <div className="font-semibold">{tpl.name}</div>
                                            <div className="text-sm text-gray-500 mt-1">{tpl.description}</div>
                                        </div>
                                        <div className="flex gap-2">
                                            <span className="text-xs bg-gray-100 px-2 py-1 rounded">
                                                {tpl.qualification_frameworks?.name || "Simple"}
                                            </span>
                                            <span className="text-xs bg-gray-100 px-2 py-1 rounded">
                                                {tpl.direction}
                                            </span>
                                        </div>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Seleccion de modo */}
                    {selectedTemplate && (
                        <div className="mb-6">
                            <h3 className="font-semibold mb-3">Como quieres configurar tu agente?</h3>
                            <div className="grid grid-cols-2 gap-4">
                                <button onClick={() => setSelectedMode("system_prompt")}
                                    className={`border rounded-xl p-4 text-left transition
                                        ${selectedMode === "system_prompt" ? "border-blue-500 bg-blue-50 ring-2 ring-blue-200" : ""}`}>
                                    <div className="text-xl mb-2">📝</div>
                                    <div className="font-semibold">System Prompt</div>
                                    <div className="text-xs text-gray-500 mt-1">
                                        Un prompt inteligente que guia toda la conversacion.
                                        Mas flexible y natural.
                                    </div>
                                </button>
                                <button onClick={() => setSelectedMode("builder_flow")}
                                    className={`border rounded-xl p-4 text-left transition
                                        ${selectedMode === "builder_flow" ? "border-blue-500 bg-blue-50 ring-2 ring-blue-200" : ""}`}>
                                    <div className="text-xl mb-2">🔀</div>
                                    <div className="font-semibold">Builder Flow</div>
                                    <div className="text-xs text-gray-500 mt-1">
                                        Flujo visual paso a paso con nodos.
                                        Control total de cada etapa.
                                    </div>
                                </button>
                            </div>
                        </div>
                    )}

                    <div className="flex justify-between">
                        <button onClick={prevStep} className="text-gray-500 hover:text-gray-700">Atras</button>
                        {selectedTemplate && (
                            <button onClick={nextStep} className="bg-blue-600 text-white px-6 py-2 rounded-lg">
                                Siguiente
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* ===== PASO 5: PERSONALIZAR ===== */}
            {step === 4 && (
                <div>
                    <h2 className="text-2xl font-bold mb-2">Personaliza tu agente</h2>
                    <p className="text-gray-500 mb-6">Estos datos hacen que el agente suene como parte de tu equipo</p>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium mb-1">Nombre de tu negocio *</label>
                            <input type="text" value={config.business_name}
                                onChange={e => setConfig({...config, business_name: e.target.value})}
                                placeholder="Ej: Inmobiliaria Patria"
                                className="w-full border rounded-lg px-4 py-2" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Nombre del agente</label>
                            <input type="text" value={config.agent_name}
                                onChange={e => setConfig({...config, agent_name: e.target.value})}
                                placeholder="Ej: Sofia, Carlos (o dejalo vacio para 'Asistente')"
                                className="w-full border rounded-lg px-4 py-2" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Tono de comunicacion</label>
                            <select value={config.tone}
                                onChange={e => setConfig({...config, tone: e.target.value})}
                                className="w-full border rounded-lg px-4 py-2">
                                <option value="">Usar default de la plantilla</option>
                                <option value="Profesional y formal">Profesional y formal</option>
                                <option value="Profesional pero cercano">Profesional pero cercano</option>
                                <option value="Amigable y casual">Amigable y casual</option>
                                <option value="Serio y directo">Serio y directo</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Saludo personalizado (opcional)</label>
                            <textarea value={config.custom_greeting}
                                onChange={e => setConfig({...config, custom_greeting: e.target.value})}
                                placeholder="Deja vacio para usar el saludo de la plantilla"
                                rows={2} className="w-full border rounded-lg px-4 py-2" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Telefono para transferir leads calientes</label>
                            <input type="tel" value={config.transfer_phone}
                                onChange={e => setConfig({...config, transfer_phone: e.target.value})}
                                placeholder="+52 999 123 4567"
                                className="w-full border rounded-lg px-4 py-2" />
                        </div>
                    </div>

                    <div className="flex justify-between mt-8">
                        <button onClick={prevStep} className="text-gray-500 hover:text-gray-700">Atras</button>
                        <button onClick={handleGenerate} disabled={!config.business_name || generating}
                            className="bg-green-600 text-white px-6 py-2 rounded-lg disabled:opacity-50">
                            {generating ? "Generando..." : "Generar mi agente"}
                        </button>
                    </div>
                </div>
            )}

            {/* ===== PASO 6: RESULTADO ===== */}
            {step === 5 && result && (
                <div>
                    <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6">
                        <div className="text-green-700 font-semibold">Agente generado exitosamente</div>
                        <div className="text-green-600 text-sm mt-1">
                            {result.template_info?.vertical} &bull; {result.template_info?.framework} &bull; {result.template_info?.direction}
                        </div>
                    </div>

                    {result.mode === "system_prompt" ? (
                        <div>
                            <h3 className="font-semibold mb-3">Tu System Prompt</h3>
                            <div className="bg-gray-900 text-green-400 rounded-xl p-6 font-mono text-sm whitespace-pre-wrap max-h-96 overflow-y-auto">
                                {result.result}
                            </div>
                            <div className="flex gap-3 mt-4">
                                <button onClick={() => navigator.clipboard.writeText(result.result)}
                                    className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm">
                                    Copiar prompt
                                </button>
                                <button onClick={() => {/* TODO: crear agente directamente con este prompt */}}
                                    className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm">
                                    Crear agente con este prompt
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div>
                            <h3 className="font-semibold mb-3">Tu Builder Flow</h3>
                            <div className="bg-gray-50 border rounded-xl p-4 mb-4">
                                <div className="text-sm text-gray-500 mb-2">
                                    {result.result.nodes?.length || 0} nodos generados
                                </div>
                                {result.result.nodes?.map((node, i) => (
                                    <div key={node.id} className="flex items-center gap-2 py-1">
                                        <span className={`w-6 h-6 rounded flex items-center justify-center text-xs text-white
                                            ${node.type === "start" ? "bg-gray-500" :
                                              node.type === "condition" ? "bg-yellow-500" :
                                              node.type === "action" ? "bg-purple-500" : "bg-blue-500"}`}>
                                            {i + 1}
                                        </span>
                                        <span className="text-sm font-medium">{node.data?.label}</span>
                                        <span className="text-xs text-gray-400">{node.type}</span>
                                    </div>
                                ))}
                            </div>
                            <button onClick={() => {/* TODO: abrir en builder flow editor */}}
                                className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm">
                                Abrir en Builder Flow
                            </button>
                        </div>
                    )}

                    <button onClick={() => { setStep(0); setResult(null); }}
                        className="mt-6 text-gray-500 hover:text-gray-700 text-sm">
                        Crear otro agente
                    </button>
                </div>
            )}
        </div>
    );
}
```

---

## PARTE 7: DATOS INICIALES - FRAMEWORKS

```sql
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
```

## PARTE 8: DATOS INICIALES - VERTICALES

```sql
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
```

## PARTE 9: DATOS INICIALES - TEMPLATES

```sql
-- INMOBILIARIA: Calificador inbound CHAMP
INSERT INTO agent_templates (vertical_slug, framework_slug, slug, name, description, objective, direction, agent_role, greeting, farewell, qualification_steps, scoring_tiers, rules, tone_description, tags, sort_order) VALUES
('inmobiliaria', 'champ', 'calificar_leads_inbound', 'Calificador de Leads Inbound', 'Califica prospectos que llaman interesados en propiedades usando CHAMP', 'Calificar prospectos entrantes y clasificarlos por potencial de compra', 'inbound', 'Asesor inmobiliario digital',
'Gracias por comunicarte con nosotros. Estoy aqui para ayudarte a encontrar tu propiedad ideal. Que tipo de propiedad te interesa?',
'Fue un gusto atenderte. Cualquier duda adicional, aqui estamos para ayudarte.',
'[{"id":"challenges","framework_step":"C","purpose":"Descubrir que tipo de propiedad busca","questions":["Que tipo de propiedad te interesa? Casa, departamento, terreno?","Cuantas recamaras necesitas?","Que zona de la ciudad prefieres?"],"extract_fields":["tipo_propiedad","recamaras","zona"],"score_rules":{"specific_need":{"points":15,"condition":"Da detalles claros"},"vague":{"points":5,"condition":"Respuestas vagas"}},"tips":"No hagas las 3 preguntas seguidas. Integralas naturalmente."},{"id":"authority","framework_step":"A","purpose":"Saber si decide solo","questions":["La decision la tomarias tu o la ves con tu pareja o familia?"],"extract_fields":["es_decisor"],"score_rules":{"is_decider":{"points":20,"condition":"Decide solo"},"not_decider":{"points":5,"condition":"Consulta con otros"}},"tips":"Si no es decisor, sugiere que vengan juntos a visitar."},{"id":"money","framework_step":"M","purpose":"Rango de inversion","questions":["Tienes un rango de inversion en mente?","Te pregunto para mostrarte solo opciones que apliquen."],"extract_fields":["presupuesto_min","presupuesto_max"],"score_rules":{"defined":{"points":25,"condition":"Da rango claro"},"undefined":{"points":-5,"condition":"No quiere decir"}},"tips":"Justifica: para no mostrar opciones fuera de rango."},{"id":"priority","framework_step":"P","purpose":"Urgencia","questions":["Para cuando estas buscando mudarte?"],"extract_fields":["timeline"],"score_rules":{"urgent":{"points":30,"condition":"Este mes"},"soon":{"points":15,"condition":"1-3 meses"},"exploring":{"points":5,"condition":"Solo explorando"}},"tips":"La urgencia predice conversion."}]'::jsonb,
'[{"tier":"hot","min_score":70,"action":"transfer_human","label":"Lead caliente"},{"tier":"warm","min_score":40,"action":"schedule_followup","label":"Lead tibio"},{"tier":"cold","min_score":0,"action":"nurturing","label":"Lead frio"}]'::jsonb,
'["Nunca inventar propiedades que no existen","Nunca dar precios sin consultar catalogo","Nunca presionar para cerrar","Si pide hablar con humano, transferir inmediato","Maximo 2 preguntas seguidas, luego aporta valor"]'::jsonb,
'Profesional pero cercano. Conocedor del mercado. Nunca presiona.', '{qualify_leads,inmobiliaria}', 1),

-- INMOBILIARIA: Seguimiento outbound
('inmobiliaria', 'spin', 'seguimiento_outbound', 'Seguimiento a Prospectos', 'Recontacta prospectos que mostraron interes pero no cerraron', 'Reactivar prospectos frios y agendar visitas', 'outbound', 'Asesor inmobiliario de seguimiento',
NULL, 'Gracias por tu tiempo. Que tengas excelente dia.',
'[{"id":"situation","framework_step":"S","purpose":"Recordar contacto previo","questions":["Te llamo porque hace poco mostraste interes en propiedades en [zona]. Sigues buscando?"],"extract_fields":["sigue_buscando"],"score_rules":{"yes":{"points":20,"condition":"Sigue interesado"},"no":{"points":0,"condition":"Ya no busca"}},"tips":"Menciona algo especifico de su busqueda anterior."},{"id":"problem","framework_step":"P","purpose":"Identificar que lo detuvo","questions":["Que te ha impedido avanzar?","Hubo algo que no te convencio de las opciones anteriores?"],"extract_fields":["obstaculo"],"score_rules":{"clear":{"points":15,"condition":"Identifica obstaculo claro"},"none":{"points":5,"condition":"No identifica"}},"tips":"Escucha sin juzgar."},{"id":"implication","framework_step":"I","purpose":"Crear urgencia suave","questions":["Has visto como se han movido los precios en esa zona?"],"extract_fields":[],"score_rules":{"concerned":{"points":15,"condition":"Le preocupa"},"indifferent":{"points":0,"condition":"No le importa"}},"tips":"No presionar. Solo informar."},{"id":"need_payoff","framework_step":"N","purpose":"Ofrecer valor concreto","questions":["Tenemos nuevas opciones que podrian interesarte. Te gustaria verlas?"],"extract_fields":["quiere_ver"],"score_rules":{"interested":{"points":20,"condition":"Quiere ver"},"not_now":{"points":5,"condition":"Ahora no"}},"tips":"Ofrece algo concreto, no generico."}]'::jsonb,
'[{"tier":"hot","min_score":50,"action":"schedule_followup","label":"Reactivado"},{"tier":"warm","min_score":25,"action":"nurturing","label":"Interesado leve"},{"tier":"cold","min_score":0,"action":"archive","label":"No interesado"}]'::jsonb,
'["Justificar la llamada en los primeros 10 segundos","Pedir permiso para continuar","Si dice que no le interesa, agradecer y no insistir","Nunca mentir sobre nuevas opciones"]'::jsonb,
'Respetuoso del tiempo. No vendedor. Informativo.', '{follow_up,inmobiliaria}', 2),

-- EDUCACION: Inscripciones inbound BANT
('educacion', 'bant', 'inscripciones_inbound', 'Atencion a Inscripciones', 'Atiende familias interesadas en inscribir a sus hijos', 'Informar sobre el colegio, calificar interes y agendar visita al campus', 'inbound', 'Asistente de admisiones',
'Gracias por tu interes en nuestro colegio. Estoy aqui para darte toda la informacion que necesites. En que grado estas buscando inscripcion?',
'Fue un gusto atenderte. Esperamos verte pronto en nuestro campus.',
'[{"id":"need","framework_step":"N","purpose":"Nivel educativo y grado","questions":["Para que nivel buscas? Preescolar, primaria, secundaria, preparatoria?","Para que grado seria?","Cuantos hijos inscribirias?"],"extract_fields":["nivel_educativo","grado","nombre_alumno"],"score_rules":{"specific":{"points":15,"condition":"Sabe exactamente que nivel y grado"},"exploring":{"points":5,"condition":"Esta explorando opciones"}},"tips":"Pregunta el nombre del alumno para personalizar."},{"id":"budget","framework_step":"B","purpose":"Expectativa de colegiatura","questions":["Tienes un rango de colegiatura en mente?","Nuestras colegiaturas van desde [rango]. Te parece dentro de tu presupuesto?"],"extract_fields":["colegiatura_rango"],"score_rules":{"fits":{"points":25,"condition":"El rango le funciona"},"concerned":{"points":10,"condition":"Le preocupa el precio"},"no_budget":{"points":-5,"condition":"Muy fuera de rango"}},"tips":"Menciona becas y planes de pago si muestra preocupacion."},{"id":"authority","framework_step":"A","purpose":"Quien decide","questions":["Tu tomarias la decision o la ves con tu pareja?"],"extract_fields":["es_decisor"],"score_rules":{"decider":{"points":20,"condition":"Decide"},"consults":{"points":5,"condition":"Consulta"}},"tips":"Invita a ambos a la visita."},{"id":"timeline","framework_step":"T","purpose":"Para que ciclo","questions":["Seria para el proximo ciclo escolar o para este?"],"extract_fields":["ciclo_escolar"],"score_rules":{"this_cycle":{"points":30,"condition":"Este ciclo o el proximo inmediato"},"next_year":{"points":10,"condition":"Para despues"},"unsure":{"points":5,"condition":"No sabe"}},"tips":"Si es para este ciclo, crear urgencia de cupo."}]'::jsonb,
'[{"tier":"hot","min_score":70,"action":"schedule_visit","label":"Visita al campus"},{"tier":"warm","min_score":40,"action":"send_info","label":"Enviar informacion"},{"tier":"cold","min_score":0,"action":"nurturing","label":"Seguimiento"}]'::jsonb,
'["Nunca garantizar disponibilidad de cupo sin verificar","Ser honesto sobre costos","Invitar siempre a conocer el campus","No hablar mal de otros colegios"]'::jsonb,
'Calido, confiable. Transmite orgullo por la institucion sin ser arrogante.', '{qualify_leads,schedule_appointments,educacion}', 1)
ON CONFLICT (vertical_slug, slug) DO NOTHING;
```

---

## PARTE 10: RESUMEN DE ARCHIVOS

```
ARCHIVOS NUEVOS:
  db/migrations/014_template_store.sql           <- Tablas + datos iniciales
  api/generator/__init__.py                       <- Package init
  api/generator/main.py                           <- Orquestador de generacion
  api/generator/system_prompt.py                  <- Generador de system prompts
  api/generator/builder_flow.py                   <- Generador de nodos
  api/routes/templates.py                         <- API endpoints
  dashboard/src/pages/AgentWizard.jsx             <- Wizard completo

ARCHIVOS MODIFICADOS:
  api/main.py                  <- Registrar router de templates
  dashboard/src/App.jsx        <- Agregar ruta /create-agent

VARIABLES DE ENTORNO:
  Ninguna nueva. Usa las existentes de Supabase.

NO SE TOCAN:
  Sistema de billing, motor de voz, MCP, memoria, LiveKit, webhooks
```

## PARTE 11: ORDEN DE IMPLEMENTACION

1. Migracion SQL: tablas + datos iniciales frameworks + verticales + templates (20 min)
2. api/generator/system_prompt.py (30 min)
3. api/generator/builder_flow.py (30 min)
4. api/generator/main.py orquestador (15 min)
5. api/routes/templates.py endpoints (25 min)
6. dashboard/src/pages/AgentWizard.jsx wizard completo (45 min)
7. Integrar con creacion de agente existente (20 min)
8. Probar end-to-end (20 min)

Tiempo estimado: ~3.5 horas.
Prioridad: 1-6 primero (generacion funcional), luego 7 (integracion con agente real).

## PARTE 12: PRUEBA END-TO-END

1. GET /templates/objectives -> 7 objetivos
2. GET /templates/verticals -> 7 verticales
3. GET /templates/frameworks -> 4 frameworks
4. GET /templates/search?vertical=inmobiliaria&direction=inbound -> templates inmobiliaria
5. POST /templates/generate con mode=system_prompt -> prompt completo generado
6. POST /templates/generate con mode=builder_flow -> array de nodos generado
7. Wizard dashboard: objetivo -> vertical -> direccion -> template -> personalizar -> generar
8. Copiar system prompt generado -> pegarlo en agente -> probar en chat de prueba
9. Generar builder flow -> abrir en editor de nodos -> verificar nodos conectados
10. Verificar usage_count incrementa al generar

## NOTAS PARA ESCALAR

- Para agregar una vertical nueva: INSERT en industry_verticals + INSERT templates en agent_templates. Automaticamente aparece en el wizard.
- Para agregar un framework nuevo: INSERT en qualification_frameworks. Se puede usar en cualquier template.
- Los templates son la combinacion de vertical + framework + direccion. Cada combinacion es un template diferente.
- El generador es determinista: misma receta + misma config = mismo resultado. No usa LLM para generar.
- Futuro: agregar IA para generar system prompts mas sofisticados usando el template como base y Gemini para enriquecer.
- Futuro: marketplace donde clientes comparten templates exitosos.
- Futuro: A/B testing de templates (cual framework convierte mas por vertical).
