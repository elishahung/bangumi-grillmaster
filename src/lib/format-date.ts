/**
 * Format a Unix timestamp (ms) to a human-readable relative or absolute date.
 * Returns relative time for recent dates (< 7 days), absolute otherwise.
 */
export const formatDate = (timestampMs: number): string => {
  const date = new Date(timestampMs);
  const now = Date.now();
  const diffMs = now - timestampMs;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffDay < 1 && diffHour < 1 && diffMin < 1) {
    return 'Just now';
  }
  if (diffDay < 1 && diffHour < 1) {
    return `${diffMin} minutes ago`;
  }
  if (diffDay < 1) {
    return `${diffHour} hours ago`;
  }
  if (diffDay < 7) {
    return `${diffDay} days ago`;
  }

  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
};
