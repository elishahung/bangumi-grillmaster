import { zodResolver } from '@hookform/resolvers/zod'
import { SubmitProjectInputSchema } from '@shared/domain'
import Link from 'next/link'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import type { z } from 'zod'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { trpc } from '@/lib/trpc'

type FormValues = z.input<typeof SubmitProjectInputSchema>

const SubmitForm = ({
  onSuccess,
}: {
  onSuccess: (projectId: string) => void
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
  })
  const submitMutation = trpc.submitProject.useMutation()

  const onSubmit = (data: FormValues) => {
    submitMutation.mutate(
      {
        sourceOrUrl: data.sourceOrUrl,
        translationHint: data.translationHint?.trim() || undefined,
      },
      {
        onSuccess: (result) => {
          reset()
          onSuccess(result.projectId)
        },
      },
    )
  }

  return (
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
          placeholder="Program name, episode info, preferred terms"
          {...register('translationHint')}
        />
      </FormField>
      <Button disabled={!isValid || submitMutation.isPending} type="submit">
        {submitMutation.isPending ? 'Submitting...' : 'Submit'}
      </Button>
      {submitMutation.data ? (
        <div className="space-y-1 text-emerald-700 text-sm">
          <p>Project created successfully!</p>
          <Link
            className="font-medium underline"
            href={`/projects/${submitMutation.data.projectId}`}
          >
            View Progress
          </Link>
        </div>
      ) : null}
      {submitMutation.error ? (
        <p className="text-rose-700 text-sm">{submitMutation.error.message}</p>
      ) : null}
    </form>
  )
}

export const SubmitProjectDialog = () => {
  const [open, setOpen] = useState(false)
  const utils = trpc.useUtils()

  const handleSuccess = (_projectId: string) => {
    utils.listProjects.invalidate().then(() => undefined)
    setOpen(false)
  }

  return (
    <Dialog onOpenChange={setOpen} open={open}>
      <DialogTrigger asChild>
        <Button size="sm">+ New Video</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Video</DialogTitle>
          <DialogDescription>
            Paste video URL or ID to add a new subtitle translation task
          </DialogDescription>
        </DialogHeader>
        <SubmitForm onSuccess={handleSuccess} />
      </DialogContent>
    </Dialog>
  )
}
