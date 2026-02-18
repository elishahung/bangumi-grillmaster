import type { TaskEventRow } from "@shared/view-models";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const TaskEventsList = ({ events }: { events: TaskEventRow[] }) => (
  <Card>
    <CardHeader>
      <CardTitle>Task Events</CardTitle>
    </CardHeader>
    <CardContent className="space-y-2">
      {events.length === 0 ? (
        <p className="text-sm text-zinc-600">No events yet.</p>
      ) : (
        events.map((event) => (
          <div
            className="rounded-md border border-zinc-200 p-3"
            key={event._id}
          >
            <p className="text-sm">{event.message}</p>
            <p className="text-xs text-zinc-500">{event.percent}%</p>
          </div>
        ))
      )}
    </CardContent>
  </Card>
);
