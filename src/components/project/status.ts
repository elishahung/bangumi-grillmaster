export const toProjectBadgeVariant = (
  status: string,
): 'queued' | 'running' | 'completed' | 'failed' | 'default' => {
  if (status === 'queued') {
    return 'queued';
  }
  if (status === 'completed') {
    return 'completed';
  }
  if (status === 'failed' || status === 'canceled') {
    return 'failed';
  }
  if (
    ['downloading', 'asr', 'translating', 'running', 'canceling'].includes(
      status,
    )
  ) {
    return 'running';
  }
  return 'default';
};
