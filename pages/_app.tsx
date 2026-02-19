import type { AppType } from 'next/app'
import { Noto_Sans_TC, Playfair_Display } from 'next/font/google'
import { AppLayout } from '@/components/app-layout'
import { trpc } from '@/lib/trpc'
import '../styles/globals.css'

const notoSansTC = Noto_Sans_TC({
  subsets: ['latin'],
  weight: ['400', '500', '700'],
  variable: '--font-sans',
})

const playfair = Playfair_Display({
  subsets: ['latin'],
  weight: ['400', '700'],
  variable: '--font-serif',
})

const App: AppType = ({ Component, pageProps }) => {
  return (
    <div className={`${notoSansTC.variable} ${playfair.variable} font-sans`}>
      <AppLayout>
        <Component {...pageProps} />
      </AppLayout>
    </div>
  )
}

export default trpc.withTRPC(App)
