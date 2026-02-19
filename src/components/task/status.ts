export const toTaskBadgeVariant = (
  status: string,
): 'queued' | 'running' | 'completed' | 'failed' | 'default' => {
  if (status === 'queued') {
    return 'queued';
  }
  if (status === 'canceling') {
    return 'running';
  }
  if (status === 'completed') {
    return 'completed';
  }
  if (status === 'failed' || status === 'canceled') {
    return 'failed';
  }
  if (status === 'running') {
    return 'running';
  }
  return 'default';
};
