export function Card({ children, className = '', ...props }) {
  return (
    <div
      className={`bg-bg-card/80 backdrop-blur-sm border border-border rounded-xl p-5 ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
