---
nombre: VoiceAI
entidad: sergio-sanchez
medios: Innotecnia/VoiceAI
cliente: Innotecnia
estado: pausado
actualizado: 2026-10-06
clase: proyecto
---

## Qué es

Plataforma multi-tenant de agentes de voz con IA para el mercado mexicano y LATAM (Twilio, Resend).
Proyecto propio de Innotecnia. El diseño completo está en `ARCHITECTURE.md`.

## Estado

**6-oct-2026 · mudanza.** Antes `C:\Claude\VoiceAI`; ahora `C:\Atlas\proyectos\Innotecnia\VoiceAI`,
sin cambiar de nombre (ni la carpeta ni el repo).

El trabajo que iba a medias desde abril (subcuentas de Twilio, salud de proveedores con las
migraciones 059 y 060, y sus pruebas) se guardó primero en la rama `wip/2026-10-06-mudanza` y ese
mismo día **se juntó con `master` y se subió**, a pedido de Sergio: nadie usa la plataforma, así
que el despliegue a Railway no afecta a nadie. Ojo al retomarlo: ese código **no está terminado**.

`.claude/settings.local.json` dejó de guardarse en git ese día: una regla de permiso llevaba
escrita la API key de Resend (GitHub bloqueó el push; la clave nunca llegó al repo). Vive en el
`.env`, que git ignora.

## Siguiente

_(Lo próximo que toca hacer.)_

## Deudas

_(Lo que se difirió a propósito, con su disparador.)_
