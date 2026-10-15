import App from '../App'
import { usePathname } from './navigation'
import { PresenterPage } from './PresenterPage'
import { WatchPage } from './WatchPage'

/** Unknown paths fall through to the match app, mirroring the server's SPA fallback. */
export function Router() {
  switch (usePathname().replace(/\/+$/, '')) {
    case '/presenter':
      return <PresenterPage />
    case '/watch':
      return <WatchPage />
    default:
      return <App />
  }
}
