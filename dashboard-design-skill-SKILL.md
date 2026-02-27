# Dashboard Design Skill — Voice AI Platform

## Aesthetic Direction: "Mission Control" Dark Tech SaaS

This dashboard is a COMMAND CENTER for voice AI agents. It should feel powerful, data-rich, and futuristic — like monitoring a fleet of AI workers in real-time.

## Design System

### Colors
```css
:root {
  /* Backgrounds — layered depth, NOT flat black */
  --bg-primary: #06060b;        /* Deepest layer */
  --bg-secondary: #0d0d14;      /* Cards, panels */
  --bg-tertiary: #13131f;       /* Elevated elements */
  --bg-hover: #1a1a2e;          /* Hover states */
  
  /* Accent — Electric Cyan (primary action color) */
  --accent: #00e5ff;
  --accent-dim: #00b8d4;
  --accent-glow: rgba(0, 229, 255, 0.15);
  --accent-glow-strong: rgba(0, 229, 255, 0.3);
  
  /* Status colors */
  --success: #00e676;           /* Active calls, healthy */
  --warning: #ffab00;           /* Approaching limits */
  --error: #ff1744;             /* Failed calls, errors */
  --info: #7c4dff;              /* Informational */
  
  /* Text */
  --text-primary: #e8eaf6;      /* Primary content */
  --text-secondary: #9e9eb8;    /* Secondary/labels */
  --text-muted: #5c5c7a;        /* Disabled, hints */
  
  /* Borders & Dividers */
  --border: rgba(255, 255, 255, 0.06);
  --border-accent: rgba(0, 229, 255, 0.2);
  
  /* Glass effect */
  --glass-bg: rgba(13, 13, 20, 0.7);
  --glass-blur: 12px;
}
```

### Typography
- **Display/Headers**: `"Space Grotesk"` or `"Outfit"` — geometric, modern, techy
  - IMPORTANT: If Space Grotesk feels generic, use `"Sora"` or `"Chakra Petch"` instead
- **Body/UI**: `"Inter"` weight 400/500 — clean readability
  - Alternative: `"DM Sans"` for slightly warmer feel
- **Data/Numbers/Code**: `"JetBrains Mono"` or `"IBM Plex Mono"` — monospace for metrics, costs, phone numbers, durations
- **Sizing scale**: 11px labels, 13px body, 16px subheadings, 24px headings, 36px+ hero metrics

### Component Patterns

#### Cards
```css
.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  transition: border-color 0.2s;
}
.card:hover {
  border-color: var(--border-accent);
}
```

#### Metric Display (hero numbers)
```
┌─────────────────────────┐
│  Total Calls Today      │  ← label in --text-secondary, 11px uppercase tracking-wider
│  847                    │  ← value in --text-primary, 36px, JetBrains Mono, font-weight: 600
│  ↑ 12.3% vs yesterday  │  ← change in --success (green) or --error (red), 12px
└─────────────────────────┘
```

#### Active Call Indicator
- Green pulsing dot (CSS animation, no JS)
- "3 active calls" with live count
- Each call shows: duration ticking, client name, caller number

#### Sidebar
- Collapsed by default (icons only, 64px wide)
- Expand on hover to show labels (240px)
- Icons: lucide-react
- Active item: accent color left border + accent text
- Sections: Overview, Clients, Calls, Documents, Settings

#### Tables (Call History)
- Alternating subtle row backgrounds
- Sortable columns with subtle arrow indicators
- Status badges: colored dots (green=completed, red=failed, yellow=transferred)
- Duration in MM:SS format, monospace font
- Cost in $X.XX format, monospace font
- Expandable rows for transcript preview

#### Charts (Recharts)
- Dark backgrounds, NO grid lines or minimal dotted grid
- Accent color for primary data line/bars
- Gradient fill under line charts (accent → transparent)
- Tooltip: glass effect card with accent border
- Smooth curves (type="monotone")

### Animations
- Page transitions: fade-in + slight upward slide (200ms ease-out)
- Cards: staggered entrance (50ms delay between cards)
- Metrics: count-up animation on load
- Active calls: pulse animation on status dot
- Skeleton loaders for data fetching states

### Layout
- Full viewport, no scroll on main layout
- Sidebar left, content right
- Top bar: breadcrumb + user menu + notifications bell
- Content area: responsive grid of cards
- Max content width: none (full width utilization)

### Key Pages

#### 1. Overview Dashboard
```
┌──────┬───────────────────────────────────────────┐
│      │  [Breadcrumb]                    [👤] [🔔] │
│  📊  │                                           │
│  👥  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌─────┐│
│  📞  │  │Calls   │ │Minutes │ │Cost    │ │Live ││
│  📄  │  │  847   │ │ 2,340  │ │$98.50  │ │🟢 3 ││
│  ⚙️  │  └────────┘ └────────┘ └────────┘ └─────┘│
│      │                                           │
│      │  ┌─── Calls Over Time (7d) ──────────────┐│
│      │  │  ╱╲    ╱╲                             ││
│      │  │ ╱  ╲╱╱╱  ╲    ╱╲                     ││
│      │  │╱          ╲╱╱╱  ╲                     ││
│      │  └───────────────────────────────────────┘│
│      │                                           │
│      │  ┌─── Recent Calls ──────────────────────┐│
│      │  │ Client    │ Duration │ Status │ Cost  ││
│      │  │ Dr.García │ 3:24     │ 🟢     │ $0.14 ││
│      │  │ Gym Power │ 1:52     │ 🟢     │ $0.08 ││
│      │  │ Dr.García │ 0:45     │ 🔴     │ $0.03 ││
│      │  └───────────────────────────────────────┘│
└──────┴───────────────────────────────────────────┘
```

#### 2. Client Detail Page
- Client info card (name, phone, agent name, voice)
- File Search documents list with upload button
- System prompt editor (syntax highlighted)
- Voice selector with audio preview
- Call statistics for this client
- Recent calls table filtered to this client

#### 3. Live Calls View
- Real-time updating cards for each active call
- Duration counting up
- Waveform visualization (CSS-only or lightweight)
- Client name, caller number
- Option to listen live (future feature indicator)

### Anti-patterns to AVOID
- ❌ White/light backgrounds — this is DARK theme only
- ❌ Rounded-full buttons that look like pills — use rounded-lg max
- ❌ Excessive gradients — subtle or none, accent color solid
- ❌ Generic "dashboard template" layouts — this is custom
- ❌ Cluttered sidebars with too many items
- ❌ Purple gradients (cliché AI aesthetic)
- ❌ Shadows on dark backgrounds (use borders and glows instead)
- ❌ Comic sans, Papyrus, or other joke fonts (obviously)
- ❌ Tailwind default colors — use custom palette above

### Tech Stack for Dashboard
- React 18+ with hooks
- Tailwind CSS with custom config (colors above)
- Recharts for charts
- Lucide React for icons
- Framer Motion for animations
- Supabase JS client for auth + realtime
- React Router for navigation
- React Query (TanStack) for data fetching
