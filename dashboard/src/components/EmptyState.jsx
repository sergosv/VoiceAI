import { Button } from './ui/Button'

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  actionLabel,
  actionIcon: ActionIcon,
  className = '',
}) {
  return (
    <div className={`flex flex-col items-center justify-center py-16 px-6 text-center ${className}`}>
      {Icon && (
        <div className="w-16 h-16 rounded-2xl bg-bg-secondary border border-border flex items-center justify-center mb-5">
          <Icon size={28} className="text-text-muted" />
        </div>
      )}
      <h3 className="text-base font-semibold text-text-primary mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-text-muted max-w-sm mb-6">{description}</p>
      )}
      {action && actionLabel && (
        <Button onClick={action}>
          {ActionIcon && <ActionIcon size={16} className="mr-2" />}
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
