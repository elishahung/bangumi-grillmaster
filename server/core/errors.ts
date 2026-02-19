export class ValidationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ValidationError'
  }
}

export class ConflictError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ConflictError'
  }
}

export class InfrastructureError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'InfrastructureError'
  }
}

export class PipelineError extends Error {
  readonly retryable: boolean
  readonly step: string

  constructor(step: string, message: string, retryable: boolean) {
    super(message)
    this.name = 'PipelineError'
    this.step = step
    this.retryable = retryable
  }
}
