export function Input({ label, className = '', ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-sm text-text-secondary">{label}</label>}
      <input
        className={`bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50 transition-colors ${className}`}
        {...props}
      />
    </div>
  )
}

export function Textarea({ label, className = '', ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-sm text-text-secondary">{label}</label>}
      <textarea
        className={`bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50 transition-colors resize-y min-h-[80px] ${className}`}
        {...props}
      />
    </div>
  )
}

export function Select({ label, options = [], className = '', ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-sm text-text-secondary">{label}</label>}
      <select
        className={`bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent/50 transition-colors ${className}`}
        {...props}
      >
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}
