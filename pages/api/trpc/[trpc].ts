import { createTrpcContext } from '@server/trpc/context'
import { appRouter } from '@server/trpc/router'
import { createNextApiHandler } from '@trpc/server/adapters/next'

export default createNextApiHandler({
  router: appRouter,
  createContext: createTrpcContext,
  onError({ error, path }) {
    console.error(`[tRPC:${path ?? 'unknown'}]`, error)
  },
})
