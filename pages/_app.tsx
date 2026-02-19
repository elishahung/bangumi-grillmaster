import type { AppType } from 'next/app';
import { AppLayout } from '@/components/app-layout';
import { trpc } from '@/lib/trpc';
import '../styles/globals.css';

const App: AppType = ({ Component, pageProps }) => {
  return (
    <AppLayout>
      <Component {...pageProps} />
    </AppLayout>
  );
};

export default trpc.withTRPC(App);
