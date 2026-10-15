import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import './styles/app.css'

import { Router } from './routes/router.tsx'

const root = document.getElementById('root')
if (!root) throw new Error('Missing #root element')

createRoot(root).render(
  <StrictMode>
    <Router />
  </StrictMode>,
)
