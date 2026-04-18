import React, { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar.jsx'
import Upload from './pages/Upload.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Combinations from './pages/Combinations.jsx'
import ComboDetail from './pages/ComboDetail.jsx'
import Analytics from './pages/Analytics.jsx'
import { useStore } from './store/useStore.js'

export default function App() {
  const fetchStats = useStore(s => s.fetchStats)

  useEffect(() => {
    fetchStats()
  }, [])

  return (
    <div style={{ display: 'flex', width: '100%', minHeight: '100vh' }}>
      <Sidebar />
      <main style={{ flex: 1, overflowX: 'hidden', paddingLeft: '240px' }}>
        <Routes>
          <Route path="/"             element={<Navigate to="/upload" replace />} />
          <Route path="/upload"       element={<Upload />} />
          <Route path="/dashboard"    element={<Dashboard />} />
          <Route path="/combinations" element={<Combinations />} />
          <Route path="/combinations/:id" element={<ComboDetail />} />
          <Route path="/analytics"    element={<Analytics />} />
        </Routes>
      </main>
    </div>
  )
}
