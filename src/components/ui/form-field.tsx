import type React from 'react'

type FormFieldProps = {
  children: React.ReactNode
  error?: string
  htmlFor: string
  label: string
}

export const FormField = ({
  children,
  error,
  htmlFor,
  label,
}: FormFieldProps) => (
  <div className="space-y-2">
    <label className="font-medium text-sm" htmlFor={htmlFor}>
      {label}
    </label>
    {children}
    {error ? <p className="text-rose-600 text-xs">{error}</p> : null}
  </div>
)
