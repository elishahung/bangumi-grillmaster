import { zodResolver } from '@hookform/resolvers/zod';
import { SubmitProjectInputSchema } from '@shared/domain';
import Link from 'next/link';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import type { z } from 'zod';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { FormField } from '@/components/ui/form-field';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { trpc } from '@/lib/trpc';

type FormValues = z.input<typeof SubmitProjectInputSchema>;

const SubmitForm = ({
  onSuccess,
}: {
  onSuccess: (projectId: string) => void;
}) => {
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
      {
        onSuccess: (result) => {
          reset();
          onSuccess(result.projectId);
        },
      },
    );
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
      <FormField
        error={errors.sourceOrUrl?.message}
        htmlFor="sourceOrUrl"
        label="影片網址 / 影片 ID"
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
        label="翻譯提示（選填）"
      >
        <Textarea
          id="hint"
          placeholder="節目名稱、集數資訊、術語偏好"
          {...register('translationHint')}
        />
      </FormField>
      <Button disabled={!isValid || submitMutation.isPending} type="submit">
        {submitMutation.isPending ? '提交中...' : '開始翻譯'}
      </Button>
      {submitMutation.data ? (
        <div className="space-y-1 text-emerald-700 text-sm">
          <p>新增成功！</p>
          <Link
            className="font-medium underline"
            href={`/projects/${submitMutation.data.projectId}`}
          >
            查看進度
          </Link>
        </div>
      ) : null}
      {submitMutation.error ? (
        <p className="text-rose-700 text-sm">{submitMutation.error.message}</p>
      ) : null}
    </form>
  );
};

export const SubmitProjectDialog = () => {
  const [open, setOpen] = useState(false);
  const utils = trpc.useUtils();

  const handleSuccess = (_projectId: string) => {
    utils.listProjects.invalidate().then(() => undefined);
    setTimeout(() => setOpen(false), 1200);
  };

  return (
    <Dialog onOpenChange={setOpen} open={open}>
      <DialogTrigger asChild>
        <Button size="sm">+ 新增影片</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增翻譯任務</DialogTitle>
          <DialogDescription>
            貼上影片網址或影片 ID 以新增字幕翻譯任務
          </DialogDescription>
        </DialogHeader>
        <SubmitForm onSuccess={handleSuccess} />
      </DialogContent>
    </Dialog>
  );
};
