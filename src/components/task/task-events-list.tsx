import type { TaskEventRow } from '@shared/view-models';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const getBadgeVariant = (level: TaskEventRow['level']) => {
  if (level === 'error') {
    return 'failed';
  }
  if (level === 'warn') {
    return 'running';
  }
  return 'default';
};

export const TaskEventsList = ({ events }: { events: TaskEventRow[] }) => (
  <Card>
    <CardHeader>
      <CardTitle>Task Events</CardTitle>
    </CardHeader>
    <CardContent className="space-y-2">
      {events.length === 0 ? (
        <p className="text-muted-foreground text-sm">No events yet.</p>
      ) : (
        events.map((event) => (
          <div
            className="overflow-auto rounded-md border border-border p-3"
            key={event._id}
          >
            <div className="mb-2 flex items-center gap-2">
              <Badge variant={getBadgeVariant(event.level)}>
                {event.level}
              </Badge>
              <p className="font-medium text-muted-foreground text-xs">
                {event.step}
              </p>
            </div>
            <p className="text-sm">{event.message}</p>
            {event.errorMessage ? (
              <p className="mt-1 text-destructive text-xs">
                {event.errorMessage}
              </p>
            ) : null}
            <p className="mt-1 text-muted-foreground text-xs">
              {new Date(event.createdAt).toLocaleString()}
              {event.durationMs
                ? ` · ${(event.durationMs / 1000).toFixed(1)}s`
                : ''}
            </p>
          </div>
        ))
      )}
    </CardContent>
  </Card>
);
