import { zodResolver } from '@hookform/resolvers/zod';
import { SubmitProjectInputSchema } from '@shared/domain';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import type { z } from 'zod';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { FormField } from '@/components/ui/form-field';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { trpc } from '@/lib/trpc';

type FormValues = z.input<typeof SubmitProjectInputSchema>;

export const SubmitProjectForm = () => {
  const {
    formState: { errors, isValid },
    handleSubmit,
    register,
    reset,
  } = useForm<FormValues>({
    defaultValues: { sourceOrUrl: '', translationHint: '' },
    mode: 'onChange',
    resolver: zodResolver(SubmitProjectInputSchema),
  });
  const submitMutation = trpc.submitProject.useMutation();

  const onSubmit = (data: FormValues) => {
    submitMutation.mutate(
      {
        sourceOrUrl: data.sourceOrUrl,
        translationHint: data.translationHint?.trim() || undefined,
      },
      { onSuccess: () => reset() },
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Submit New Project</CardTitle>
        <CardDescription>
          貼上影片網址或 videoId，系統會建立 UUID project 並啟動任務。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
          <FormField
            error={errors.sourceOrUrl?.message}
            htmlFor="sourceOrUrl"
            label="Video URL / Video ID"
          >
            <Input
              id="sourceOrUrl"
              placeholder="https://www.bilibili.com/video/BV..."
              {...register('sourceOrUrl')}
            />
          </FormField>
          <FormField
            error={errors.translationHint?.message}
            htmlFor="hint"
            label="Translation Hint (Optional)"
          >
            <Textarea
              id="hint"
              placeholder="節目名稱、集數資訊、術語偏好"
              {...register('translationHint')}
            />
          </FormField>
          <Button disabled={!isValid || submitMutation.isPending} type="submit">
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
        </form>
      </CardContent>
    </Card>
  );
};
