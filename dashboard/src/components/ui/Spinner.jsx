export function Spinner({ size = 20 }) {
  return (
    <div
      className="border-2 border-border border-t-accent rounded-full animate-spin"
      style={{ width: size, height: size }}
    />
  )
}

export function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <Spinner size={32} />
    </div>
  )
}
