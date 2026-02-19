import type { AppRouter } from '@server/trpc/router';
import { httpBatchLink } from '@trpc/client';
import { createTRPCNext } from '@trpc/next';
import superjson from 'superjson';

export const trpc = createTRPCNext<AppRouter>({
  transformer: superjson,
  config() {
    return {
      links: [
        httpBatchLink({
          url: '/api/trpc',
          transformer: superjson,
        }),
      ],
    };
  },
  ssr: false,
});
