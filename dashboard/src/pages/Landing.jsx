/**
 * Landing Page — Voice AI Platform
 * Pagina publica de marketing con animaciones SVG y scroll effects.
 */
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

// ── Hook: Intersection Observer para animaciones on-scroll ──
function useInView(options = {}) {
  const ref = useRef(null)
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setInView(true) },
      { threshold: 0.15, ...options }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  return [ref, inView]
}

// ── SVG: Waveform animado ──
function Waveform() {
  return (
    <svg viewBox="0 0 200 60" className="w-full max-w-md h-16 mx-auto" aria-hidden="true">
      {Array.from({ length: 40 }, (_, i) => (
        <rect
          key={i}
          x={i * 5}
          y={10}
          width={3}
          height={40}
          rx={1.5}
          className="fill-accent/60"
          style={{
            animation: `waveform 1.2s ease-in-out ${i * 0.05}s infinite alternate`,
            transformOrigin: 'center',
          }}
        />
      ))}
    </svg>
  )
}

// ── SVG: Icono de canal ──
function ChannelIcon({ type }) {
  const icons = {
    phone: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8">
        <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    whatsapp: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/>
        <path d="M12 2C6.477 2 2 6.477 2 12c0 1.89.525 3.66 1.438 5.168L2 22l4.832-1.438A9.955 9.955 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2z" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      </svg>
    ),
    widget: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8">
        <circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    ghl: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  }
  return icons[type] || null
}

// ── Componente: Feature Card con animacion ──
function FeatureCard({ icon, title, desc, delay = 0, inView }) {
  return (
    <div
      className={`bg-[#12121a] border border-gray-800/50 rounded-xl p-6 transition-all duration-700 ${
        inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
      }`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      <div className="w-12 h-12 rounded-lg bg-accent/10 flex items-center justify-center text-accent mb-4">
        {icon}
      </div>
      <h3 className="text-white font-semibold text-lg mb-2">{title}</h3>
      <p className="text-gray-400 text-sm leading-relaxed">{desc}</p>
    </div>
  )
}

// ── Componente: Step del flujo ──
function FlowStep({ number, title, desc, active }) {
  return (
    <div className={`flex items-start gap-4 transition-all duration-500 ${active ? 'opacity-100' : 'opacity-30'}`}>
      <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 transition-colors duration-500 ${
        active ? 'bg-accent text-black' : 'bg-gray-800 text-gray-500'
      }`}>
        {number}
      </div>
      <div>
        <h4 className="text-white font-medium">{title}</h4>
        <p className="text-gray-400 text-sm mt-1">{desc}</p>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════
// LANDING PAGE
// ══════════════════════════════════════════════════════════

export function Landing() {
  const [activeStep, setActiveStep] = useState(0)
  const [featRef, featInView] = useInView()
  const [hookRef, hookInView] = useInView()
  const [channelRef, channelInView] = useInView()

  // Animar pasos del flujo
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep(s => (s + 1) % 5)
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white overflow-x-hidden">
      {/* ── Navbar ── */}
      <nav className="fixed top-0 w-full z-50 bg-[#0a0a0f]/80 backdrop-blur-xl border-b border-gray-800/50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
              <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5 text-accent">
                <path d="M12 2a3 3 0 00-3 3v7a3 3 0 006 0V5a3 3 0 00-3-3z" stroke="currentColor" strokeWidth="2"/>
                <path d="M19 10v2a7 7 0 01-14 0v-2M12 19v3M8 22h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <span className="font-bold text-lg">VoiceAI</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="#features" className="text-sm text-gray-400 hover:text-white transition-colors hidden sm:block">Funciones</a>
            <a href="#pricing" className="text-sm text-gray-400 hover:text-white transition-colors hidden sm:block">Precios</a>
            <Link to="/login" className="text-sm text-gray-400 hover:text-white transition-colors">Iniciar sesion</Link>
            <Link to="/login" className="px-4 py-2 bg-accent text-black text-sm font-semibold rounded-lg hover:bg-accent/90 transition-colors">
              Empezar gratis
            </Link>
          </div>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent/10 border border-accent/20 text-accent text-sm mb-8 landing-fade-in">
            <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            Plataforma de agentes de IA para negocios
          </div>
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold leading-tight mb-6 landing-fade-in" style={{ animationDelay: '0.1s' }}>
            Agentes de IA que<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent via-cyan-300 to-blue-400">
              atienden como humanos
            </span>
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10 landing-fade-in" style={{ animationDelay: '0.2s' }}>
            Llamadas, WhatsApp, Web — tu negocio disponible 24/7 con agentes
            inteligentes que agendan citas, responden preguntas y nunca se cansan.
          </p>
          <div className="flex items-center justify-center gap-4 mb-16 landing-fade-in" style={{ animationDelay: '0.3s' }}>
            <Link to="/login" className="px-8 py-3.5 bg-accent text-black font-bold rounded-xl hover:bg-accent/90 transition-all hover:scale-105 text-lg">
              Empezar gratis
            </Link>
            <a href="#how-it-works" className="px-8 py-3.5 border border-gray-700 text-gray-300 font-medium rounded-xl hover:border-gray-500 transition-all">
              Ver como funciona
            </a>
          </div>
          {/* Waveform animado */}
          <div className="landing-fade-in" style={{ animationDelay: '0.4s' }}>
            <Waveform />
            <p className="text-xs text-gray-600 mt-3">Simulacion de conversacion en tiempo real</p>
          </div>
        </div>
      </section>

      {/* ── CANALES ── */}
      <section ref={channelRef} className="py-20 px-6" id="channels">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">Un agente, todos los canales</h2>
            <p className="text-gray-400 text-lg max-w-xl mx-auto">
              El mismo agente responde por telefono, WhatsApp, tu sitio web y GoHighLevel.
              Una sola configuracion, experiencia consistente en todos lados.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {[
              { type: 'phone', name: 'Llamadas', desc: 'Voz natural con Deepgram + Cartesia. Detecta emociones y cambia de idioma.' },
              { type: 'whatsapp', name: 'WhatsApp', desc: 'Respuestas automaticas via Evolution API. Emojis, formato, horario.' },
              { type: 'widget', name: 'Widget Web', desc: 'Chat o voz embebible en tu sitio. Una linea de codigo.' },
              { type: 'ghl', name: 'GoHighLevel', desc: 'Integrado con GHL. Responde SMS, webchat y redes sociales.' },
            ].map((ch, i) => (
              <div
                key={ch.type}
                className={`group bg-[#12121a] border border-gray-800/50 rounded-xl p-6 text-center hover:border-accent/40 hover:bg-accent/5 transition-all duration-500 cursor-default ${
                  channelInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
                }`}
                style={{ transitionDelay: `${i * 100}ms` }}
              >
                <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center text-accent mx-auto mb-4 group-hover:scale-110 transition-transform">
                  <ChannelIcon type={ch.type} />
                </div>
                <h3 className="text-white font-semibold text-lg mb-2">{ch.name}</h3>
                <p className="text-gray-400 text-sm">{ch.desc}</p>
              </div>
            ))}
          </div>

          {/* SVG lines connecting to center */}
          <div className="hidden md:flex justify-center mt-8">
            <svg viewBox="0 0 600 40" className="w-full max-w-2xl h-10 text-accent/20">
              <line x1="75" y1="0" x2="300" y2="35" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" />
              <line x1="225" y1="0" x2="300" y2="35" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" />
              <line x1="375" y1="0" x2="300" y2="35" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" />
              <line x1="525" y1="0" x2="300" y2="35" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" />
              <circle cx="300" cy="35" r="4" className="fill-accent" />
            </svg>
            <div className="absolute text-xs text-accent/60 -mt-1">Tu Agente IA</div>
          </div>
        </div>
      </section>

      {/* ── COMO FUNCIONA ── */}
      <section className="py-20 px-6 bg-[#08080d]" id="how-it-works">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">Como funciona</h2>
            <p className="text-gray-400 text-lg">De llamada a cita agendada en segundos</p>
          </div>

          <div className="grid md:grid-cols-2 gap-12 items-center">
            {/* Steps */}
            <div className="space-y-6">
              {[
                { title: 'El cliente contacta', desc: 'Por telefono, WhatsApp o tu sitio web. El agente responde al instante.' },
                { title: 'Escucha y entiende', desc: 'STT en tiempo real con Deepgram Nova-3. Detecta idioma automaticamente.' },
                { title: 'Busca la respuesta', desc: 'Consulta tu base de conocimientos, calendario, CRM o APIs externas.' },
                { title: 'Responde naturalmente', desc: 'Voz humana con Cartesia Sonic-3. Respuestas cortas y naturales.' },
                { title: 'Ejecuta la accion', desc: 'Agenda citas, envia WhatsApp, guarda contactos, transfiere a humano.' },
              ].map((step, i) => (
                <FlowStep key={i} number={i + 1} title={step.title} desc={step.desc} active={activeStep === i} />
              ))}
            </div>

            {/* Visual */}
            <div className="relative">
              <div className="bg-[#12121a] border border-gray-800/50 rounded-2xl p-8 overflow-hidden">
                {/* Animated glow */}
                <div className="absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent" />
                <div className="relative space-y-4">
                  {/* Simulated chat */}
                  <div className={`flex gap-3 transition-all duration-500 ${activeStep >= 0 ? 'opacity-100' : 'opacity-0'}`}>
                    <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center text-xs text-blue-400">C</div>
                    <div className="bg-[#1a1a2e] rounded-xl rounded-tl-none px-4 py-2 text-sm text-gray-300 max-w-xs">
                      Hola, quiero agendar una cita para manana
                    </div>
                  </div>
                  <div className={`flex gap-3 justify-end transition-all duration-500 ${activeStep >= 2 ? 'opacity-100' : 'opacity-0'}`}>
                    <div className="bg-accent/10 border border-accent/20 rounded-xl rounded-tr-none px-4 py-2 text-sm text-gray-200 max-w-xs">
                      Claro, tenemos disponible manana martes a las 10 o a las 3. Cual le queda mejor?
                    </div>
                    <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-xs text-accent">IA</div>
                  </div>
                  <div className={`flex gap-3 transition-all duration-500 ${activeStep >= 3 ? 'opacity-100' : 'opacity-0'}`}>
                    <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center text-xs text-blue-400">C</div>
                    <div className="bg-[#1a1a2e] rounded-xl rounded-tl-none px-4 py-2 text-sm text-gray-300 max-w-xs">
                      A las 10 esta bien
                    </div>
                  </div>
                  <div className={`flex gap-3 justify-end transition-all duration-500 ${activeStep >= 4 ? 'opacity-100' : 'opacity-0'}`}>
                    <div className="bg-accent/10 border border-accent/20 rounded-xl rounded-tr-none px-4 py-2 text-sm text-gray-200 max-w-xs">
                      Perfecto, su cita queda para manana a las 10. Le envio la confirmacion por WhatsApp?
                    </div>
                    <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-xs text-accent">IA</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── INTELIGENCIA ── */}
      <section ref={featRef} className="py-20 px-6" id="features">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">Inteligencia que otros no tienen</h2>
            <p className="text-gray-400 text-lg max-w-xl mx-auto">
              No es solo un chatbot con voz. Es un agente con reglas de negocio,
              memoria, evaluacion de calidad y aprendizaje continuo.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <FeatureCard inView={featInView} delay={0}
              icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>}
              title="Reglas Inquebrantables"
              desc="Lifecycle hooks determinísticos. No agendar domingos, siempre confirmar nombre, nunca dar precios sin verificar. El agente SIEMPRE cumple."
            />
            <FeatureCard inView={featInView} delay={100}
              icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>}
              title="Evaluador de Calidad"
              desc="Un segundo LLM verifica cada respuesta antes de enviarla. Si detecta un error, el agente se corrige automaticamente."
            />
            <FeatureCard inView={featInView} delay={200}
              icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>}
              title="Detecta Emociones"
              desc="Analisis de sentimiento en tiempo real. Si el cliente se frustra, el agente cambia a tono empatico o transfiere a un humano."
            />
            <FeatureCard inView={featInView} delay={300}
              icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>}
              title="Base de Conocimiento"
              desc="Sube PDFs, docs y manuales. El agente busca la respuesta correcta en tus documentos con Gemini File Search."
            />
            <FeatureCard inView={featInView} delay={400}
              icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>}
              title="Memoria de Clientes"
              desc="Recuerda conversaciones anteriores. 'Hola Juan, que gusto. La ultima vez preguntaste por la limpieza dental.'"
            />
            <FeatureCard inView={featInView} delay={500}
              icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>}
              title="Aprende Solo"
              desc="Analiza todas las llamadas y detecta patrones: preguntas frecuentes, puntos de abandono. Se mejora continuamente."
            />
          </div>
        </div>
      </section>

      {/* ── HOOKS VISUAL ── */}
      <section ref={hookRef} className="py-20 px-6 bg-[#08080d]" id="hooks">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">Ajuste fino con reglas de negocio</h2>
            <p className="text-gray-400 text-lg max-w-xl mx-auto">
              Define reglas que el agente SIEMPRE cumple. No depende del prompt — es codigo determinístico.
            </p>
          </div>

          <div className={`bg-[#12121a] border border-gray-800/50 rounded-2xl p-8 transition-all duration-700 ${hookInView ? 'opacity-100' : 'opacity-0'}`}>
            {/* Hook lifecycle diagram */}
            <div className="flex items-center justify-between gap-2 mb-8 overflow-x-auto pb-2">
              {['Usuario habla', 'PreResponse', 'Agente responde', 'PreToolCall', 'Ejecuta accion'].map((step, i) => (
                <div key={step} className="flex items-center gap-2 flex-shrink-0">
                  <div className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
                    i === 1 || i === 3 ? 'bg-accent/20 text-accent border border-accent/30' : 'bg-gray-800 text-gray-400'
                  }`}>
                    {step}
                  </div>
                  {i < 4 && (
                    <svg viewBox="0 0 24 24" className="w-4 h-4 text-gray-600 flex-shrink-0">
                      <path d="M9 18l6-6-6-6" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round"/>
                    </svg>
                  )}
                </div>
              ))}
            </div>

            {/* Example rules */}
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-[#0a0a0f] rounded-xl p-4 border border-gray-800/50">
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-2 h-2 rounded-full bg-yellow-400" />
                  <span className="text-sm font-medium text-yellow-400">PreToolCall</span>
                  <span className="text-xs text-gray-600">schedule_appointment</span>
                </div>
                <div className="font-mono text-sm space-y-1">
                  <p className="text-gray-400"><span className="text-purple-400">if</span> dia == <span className="text-green-400">"domingo"</span></p>
                  <p className="text-red-400 pl-4">BLOQUEAR</p>
                  <p className="text-gray-500 pl-4 text-xs">"No agendamos domingos, ofrece otro dia"</p>
                </div>
              </div>
              <div className="bg-[#0a0a0f] rounded-xl p-4 border border-gray-800/50">
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-2 h-2 rounded-full bg-green-400" />
                  <span className="text-sm font-medium text-green-400">PreResponse</span>
                  <span className="text-xs text-gray-600">evaluator</span>
                </div>
                <div className="font-mono text-sm space-y-1">
                  <p className="text-gray-400"><span className="text-purple-400">if</span> respuesta contiene <span className="text-green-400">precio</span></p>
                  <p className="text-cyan-400 pl-4">VERIFICAR con segundo LLM</p>
                  <p className="text-gray-500 pl-4 text-xs">"Agregar disclaimer: precios sujetos a cambio"</p>
                </div>
              </div>
            </div>

            <p className="text-center text-gray-500 text-sm mt-6">
              20 reglas predefinidas listas para activar con un click
            </p>
          </div>
        </div>
      </section>

      {/* ── PRICING ── */}
      <section className="py-20 px-6" id="pricing">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">Precios simples, sin sorpresas</h2>
            <p className="text-gray-400 text-lg">Pagas solo por lo que usas. Sin contratos.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                name: 'Starter',
                price: '$499',
                period: '/mes MXN',
                desc: 'Para negocios que empiezan',
                features: ['1 agente', '500 minutos/mes', '1 canal (voz o WhatsApp)', 'Base de conocimiento', 'Soporte por email'],
                cta: 'Empezar',
                accent: false,
              },
              {
                name: 'Pro',
                price: '$1,499',
                period: '/mes MXN',
                desc: 'Para negocios en crecimiento',
                features: ['3 agentes', '2,000 minutos/mes', 'Todos los canales', 'Hooks + Quality Scoring', 'Insights + Auto-tuning', 'Soporte prioritario'],
                cta: 'Empezar gratis',
                accent: true,
              },
              {
                name: 'Enterprise',
                price: 'Contactanos',
                period: '',
                desc: 'Para operaciones grandes',
                features: ['Agentes ilimitados', 'Minutos ilimitados', 'Multi-agente orquestado', 'SLA 99.9%', 'API publica + webhooks', 'Soporte dedicado'],
                cta: 'Hablar con ventas',
                accent: false,
              },
            ].map((plan) => (
              <div
                key={plan.name}
                className={`rounded-2xl p-6 ${
                  plan.accent
                    ? 'bg-accent/5 border-2 border-accent/40 relative'
                    : 'bg-[#12121a] border border-gray-800/50'
                }`}
              >
                {plan.accent && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-accent text-black text-xs font-bold rounded-full">
                    Popular
                  </div>
                )}
                <h3 className="text-xl font-bold mb-1">{plan.name}</h3>
                <p className="text-gray-400 text-sm mb-4">{plan.desc}</p>
                <div className="mb-6">
                  <span className="text-3xl font-bold">{plan.price}</span>
                  <span className="text-gray-400 text-sm">{plan.period}</span>
                </div>
                <ul className="space-y-2 mb-6">
                  {plan.features.map(f => (
                    <li key={f} className="flex items-center gap-2 text-sm text-gray-300">
                      <svg viewBox="0 0 24 24" className="w-4 h-4 text-accent flex-shrink-0">
                        <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      {f}
                    </li>
                  ))}
                </ul>
                <Link
                  to="/login"
                  className={`block text-center py-2.5 rounded-xl font-semibold text-sm transition-all ${
                    plan.accent
                      ? 'bg-accent text-black hover:bg-accent/90'
                      : 'border border-gray-700 text-gray-300 hover:border-gray-500'
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA FINAL ── */}
      <section className="py-20 px-6 bg-[#08080d]">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">Listo para automatizar tu atencion?</h2>
          <p className="text-gray-400 text-lg mb-8">
            Configura tu primer agente en menos de 5 minutos. Sin tarjeta de credito.
          </p>
          <Link to="/login" className="inline-block px-10 py-4 bg-accent text-black font-bold rounded-xl hover:bg-accent/90 transition-all hover:scale-105 text-lg">
            Crear mi agente gratis
          </Link>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="border-t border-gray-800/50 py-12 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-accent/20 flex items-center justify-center">
              <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4 text-accent">
                <path d="M12 2a3 3 0 00-3 3v7a3 3 0 006 0V5a3 3 0 00-3-3z" stroke="currentColor" strokeWidth="2"/>
                <path d="M19 10v2a7 7 0 01-14 0v-2" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <span className="text-sm text-gray-400">VoiceAI Platform</span>
          </div>
          <div className="flex gap-6 text-sm text-gray-500">
            <a href="#features" className="hover:text-gray-300 transition-colors">Funciones</a>
            <a href="#pricing" className="hover:text-gray-300 transition-colors">Precios</a>
            <Link to="/login" className="hover:text-gray-300 transition-colors">Dashboard</Link>
          </div>
          <p className="text-xs text-gray-600">
            2026 Innotecnia. Todos los derechos reservados.
          </p>
        </div>
      </footer>
    </div>
  )
}
