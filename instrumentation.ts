export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    await import('@server/pipeline/runner').then((m) =>
      m.getTaskPipelineRunner(),
    )
  }
}
