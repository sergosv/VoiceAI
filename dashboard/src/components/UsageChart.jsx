import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export function UsageChart({ data = [], dataKey = 'calls', label = 'Llamadas' }) {
  if (!data.length) {
    return <p className="text-text-muted text-sm py-8 text-center">Sin datos de uso</p>
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="colorAccent" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#00f0ff" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#00f0ff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tickFormatter={v => v.slice(5)}
          stroke="#555570"
          fontSize={11}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="#555570"
          fontSize={11}
          tickLine={false}
          axisLine={false}
          width={35}
        />
        <Tooltip
          contentStyle={{
            background: '#1a1a2e',
            border: '1px solid #2a2a3e',
            borderRadius: 8,
            fontSize: 12,
          }}
          labelFormatter={v => `Fecha: ${v}`}
        />
        <Area
          type="monotone"
          dataKey={dataKey}
          name={label}
          stroke="#00f0ff"
          fill="url(#colorAccent)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
