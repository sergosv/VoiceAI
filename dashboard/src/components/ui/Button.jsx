export function Button({ children, variant = 'primary', className = '', ...props }) {
  const base = 'px-4 py-2 rounded-lg font-medium text-sm transition-all duration-200 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed'
  const variants = {
    primary: 'bg-accent/20 text-accent border border-accent/30 hover:bg-accent/30',
    secondary: 'bg-bg-card text-text-secondary border border-border hover:bg-bg-hover hover:text-text-primary',
    danger: 'bg-danger/20 text-danger border border-danger/30 hover:bg-danger/30',
  }
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  )
}
