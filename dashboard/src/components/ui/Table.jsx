export function Table({ children, className = '' }) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-sm">{children}</table>
    </div>
  )
}

export function Th({ children, className = '' }) {
  return (
    <th className={`text-left py-3 px-4 text-text-muted font-medium text-xs uppercase tracking-wider border-b border-border ${className}`}>
      {children}
    </th>
  )
}

export function Td({ children, className = '' }) {
  return (
    <td className={`py-3 px-4 border-b border-border/50 ${className}`}>
      {children}
    </td>
  )
}
