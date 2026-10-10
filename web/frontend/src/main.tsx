import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './growth/GrowthApp.tsx'
import ErrorBoundary from './components/ErrorBoundary.tsx'

export const BUILD_ID = 'growth-phase3';
// 打到控制台，便于确认浏览器加载的是最新前端（排查缓存旧包）
console.log(`Growth Copilot build: ${BUILD_ID}`);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
