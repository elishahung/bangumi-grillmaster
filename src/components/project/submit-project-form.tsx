import Link from 'next/link';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { trpc } from '@/lib/trpc';

export const SubmitProjectForm = () => {
  const [sourceOrUrl, setSourceOrUrl] = useState('');
  const [translationHint, setTranslationHint] = useState('');
  const submitMutation = trpc.submitProject.useMutation();

  const isSubmitDisabled = useMemo(
    () => !sourceOrUrl.trim() || submitMutation.isPending,
    [sourceOrUrl, submitMutation.isPending],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Submit New Project</CardTitle>
        <CardDescription>
          貼上影片網址或 videoId，系統會建立 UUID project 並啟動任務。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label className="font-medium text-sm" htmlFor="sourceOrUrl">
            Video URL / Video ID
          </label>
          <Input
            id="sourceOrUrl"
            onChange={(event) => setSourceOrUrl(event.target.value)}
            placeholder="https://www.bilibili.com/video/BV..."
            value={sourceOrUrl}
          />
        </div>
        <div className="space-y-2">
          <label className="font-medium text-sm" htmlFor="hint">
            Translation Hint (Optional)
          </label>
          <Textarea
            id="hint"
            onChange={(event) => setTranslationHint(event.target.value)}
            placeholder="節目名稱、集數資訊、術語偏好"
            value={translationHint}
          />
        </div>
        <Button
          disabled={isSubmitDisabled}
          onClick={() => {
            submitMutation.mutate({
              sourceOrUrl,
              translationHint: translationHint.trim() || undefined,
            });
          }}
        >
          {submitMutation.isPending ? 'Submitting...' : 'Submit Project'}
        </Button>
        {submitMutation.data ? (
          <div className="space-y-1 text-emerald-700 text-sm">
            <p>建立成功：projectId = {submitMutation.data.projectId}</p>
            <Link
              className="font-medium underline"
              href={`/projects/${submitMutation.data.projectId}`}
            >
              前往專案頁查看進度
            </Link>
          </div>
        ) : null}
        {submitMutation.error ? (
          <p className="text-rose-700 text-sm">
            {submitMutation.error.message}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
};
