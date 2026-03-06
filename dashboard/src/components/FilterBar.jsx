import { useState } from 'react'
import { Calendar, Filter, X, Download } from 'lucide-react'
import { Button } from './ui/Button'

function getDatePresets() {
  const today = new Date()
  const fmt = d => d.toISOString().split('T')[0]

  const daysAgo = n => {
    const d = new Date(today)
    d.setDate(d.getDate() - n)
    return fmt(d)
  }

  return [
    { label: 'Hoy', from: fmt(today), to: fmt(today) },
    { label: '7 dias', from: daysAgo(7), to: fmt(today) },
    { label: '30 dias', from: daysAgo(30), to: fmt(today) },
    { label: '90 dias', from: daysAgo(90), to: fmt(today) },
  ]
}

export function FilterBar({
  filters = [],        // [{ key, label, options: [{value, label}] }]
  values = {},         // { status: 'active', type: 'purchase' }
  onChange,            // (key, value) => void
  dateRange = false,   // show date range picker
  dateFrom,
  dateTo,
  onDateChange,        // (from, to) => void
  onExport,            // () => void — optional export button
  onClear,             // () => void
  className = '',
}) {
  const [showDatePicker, setShowDatePicker] = useState(false)
  const presets = getDatePresets()
  const hasActiveFilters = Object.values(values).some(v => v) || dateFrom || dateTo

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      {/* Status/type filters */}
      {filters.map(filter => (
        <div key={filter.key} className="flex items-center gap-1">
          <span className="text-[10px] text-text-muted uppercase tracking-wide mr-1">{filter.label}:</span>
          <div className="flex gap-1">
            <button
              onClick={() => onChange(filter.key, '')}
              className={`px-2 py-1 rounded text-xs border transition-colors cursor-pointer ${
                !values[filter.key]
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border text-text-muted hover:text-text-primary'
              }`}
            >
              Todas
            </button>
            {filter.options.map(opt => (
              <button
                key={opt.value}
                onClick={() => onChange(filter.key, opt.value)}
                className={`px-2 py-1 rounded text-xs border transition-colors cursor-pointer ${
                  values[filter.key] === opt.value
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border text-text-muted hover:text-text-primary'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* Date range */}
      {dateRange && (
        <div className="relative">
          <button
            onClick={() => setShowDatePicker(!showDatePicker)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs border transition-colors cursor-pointer ${
              dateFrom || dateTo
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-border text-text-muted hover:text-text-primary'
            }`}
          >
            <Calendar size={12} />
            {dateFrom && dateTo
              ? `${dateFrom} — ${dateTo}`
              : dateFrom
              ? `Desde ${dateFrom}`
              : 'Fecha'
            }
          </button>

          {showDatePicker && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowDatePicker(false)} />
              <div className="absolute top-full mt-1 left-0 z-20 bg-bg-secondary border border-border rounded-lg shadow-xl p-3 space-y-3 min-w-[260px]">
                {/* Presets */}
                <div className="flex flex-wrap gap-1">
                  {presets.map(p => (
                    <button
                      key={p.label}
                      onClick={() => {
                        onDateChange(p.from, p.to)
                        setShowDatePicker(false)
                      }}
                      className="px-2 py-1 rounded text-xs border border-border text-text-muted hover:text-accent hover:border-accent/50 transition-colors cursor-pointer"
                    >
                      {p.label}
                    </button>
                  ))}
                </div>

                {/* Custom range */}
                <div className="flex items-center gap-2">
                  <input
                    type="date"
                    value={dateFrom || ''}
                    onChange={e => onDateChange(e.target.value, dateTo)}
                    className="flex-1 bg-bg-primary border border-border rounded px-2 py-1 text-xs text-text-primary"
                  />
                  <span className="text-text-muted text-xs">a</span>
                  <input
                    type="date"
                    value={dateTo || ''}
                    onChange={e => onDateChange(dateFrom, e.target.value)}
                    className="flex-1 bg-bg-primary border border-border rounded px-2 py-1 text-xs text-text-primary"
                  />
                </div>

                {(dateFrom || dateTo) && (
                  <button
                    onClick={() => {
                      onDateChange('', '')
                      setShowDatePicker(false)
                    }}
                    className="text-xs text-text-muted hover:text-danger transition-colors cursor-pointer"
                  >
                    Limpiar fechas
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Clear all */}
      {hasActiveFilters && onClear && (
        <button
          onClick={onClear}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs text-text-muted hover:text-danger transition-colors cursor-pointer"
        >
          <X size={12} /> Limpiar filtros
        </button>
      )}

      {/* Export */}
      {onExport && (
        <button
          onClick={onExport}
          className="flex items-center gap-1 px-2.5 py-1 rounded text-xs border border-border text-text-muted hover:text-text-primary transition-colors cursor-pointer"
        >
          <Download size={12} /> Exportar
        </button>
      )}
    </div>
  )
}

export function SortableHeader({ children, active, direction, onClick, className = '' }) {
  return (
    <th
      onClick={onClick}
      className={`py-2 px-3 text-left text-xs font-medium text-text-muted cursor-pointer hover:text-text-primary transition-colors select-none ${className}`}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        {active && (
          <span className="text-accent">
            {direction === 'asc' ? '↑' : '↓'}
          </span>
        )}
        {!active && <span className="text-text-muted/30">↕</span>}
      </span>
    </th>
  )
}
