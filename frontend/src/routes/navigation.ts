import { useSyncExternalStore } from 'react'

// pushState fires no event of its own; navigate() dispatches popstate so every subscriber re-reads the path.
function subscribe(onChange: () => void) {
  window.addEventListener('popstate', onChange)
  return () => {
    window.removeEventListener('popstate', onChange)
  }
}

const pathname = () => window.location.pathname

export function usePathname(): string {
  return useSyncExternalStore(subscribe, pathname)
}

export function navigate(path: string): void {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}
