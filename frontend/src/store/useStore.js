import { create } from 'zustand'

const API = '/api'

export const useStore = create((set, get) => ({
  // State
  uploadResult:    null,
  combinations:    [],
  totalCombos:     0,
  stats:           null,
  selectedCombo:   null,
  comboDetail:     null,
  chatHistory:     {},
  loading:         { upload: false, combos: false, detail: false, chat: false },
  error:           null,
  typeFilter:      'ALL',
  page:            1,
  pages:           1,

  // Setters
  setFilter: (f) => { set({ typeFilter: f, page: 1 }); get().fetchCombinations(1, f); },
  setPage:   (p) => { set({ page: p }); get().fetchCombinations(p, get().typeFilter); },
  clearError: ()  => set({ error: null }),

  // Upload file
  uploadFile: async (file) => {
    set({ loading: { ...get().loading, upload: true }, error: null })
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`${API}/upload`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload failed')
      set({ uploadResult: data })
      await get().fetchCombinations(1, 'ALL')
      await get().fetchStats()
    } catch (e) {
      set({ error: e.message })
    } finally {
      set({ loading: { ...get().loading, upload: false } })
    }
  },

  // Fetch combinations list
  fetchCombinations: async (page = 1, filter = 'ALL') => {
    set({ loading: { ...get().loading, combos: true } })
    try {
      const params = new URLSearchParams({ page, limit: 50 })
      if (filter !== 'ALL') params.set('type_filter', filter)
      const res  = await fetch(`${API}/combinations?${params}`)
      const data = await res.json()
      set({
        combinations: data.combinations || [],
        totalCombos:  data.total || 0,
        page:         data.page  || 1,
        pages:        data.pages || 1,
      })
    } catch (e) {
      set({ error: e.message })
    } finally {
      set({ loading: { ...get().loading, combos: false } })
    }
  },

  // Fetch detailed combo
  selectCombo: async (id) => {
    set({ selectedCombo: id, comboDetail: null, loading: { ...get().loading, detail: true } })
    try {
      const res  = await fetch(`${API}/combination/${id}`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Not found')
      // Merge chat history from store
      const localHistory = get().chatHistory[id] || []
      const merged = [...(data.chat_history || []), ...localHistory.filter(
        lh => !(data.chat_history || []).some(dh => dh.user === lh.user)
      )]
      set({ comboDetail: data, chatHistory: { ...get().chatHistory, [id]: merged } })
    } catch (e) {
      set({ error: e.message, comboDetail: null })
    } finally {
      set({ loading: { ...get().loading, detail: false } })
    }
  },

  // Fetch stats
  fetchStats: async () => {
    try {
      const res  = await fetch(`${API}/stats`)
      const data = await res.json()
      set({ stats: data })
    } catch {}
  },

  // Send chat message
  sendChat: async (comboId, question) => {
    const prev = get().chatHistory[comboId] || []
    const optimistic = [...prev, { user: question, assistant: '...', timestamp: new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) }]
    set({ chatHistory: { ...get().chatHistory, [comboId]: optimistic }, loading: { ...get().loading, chat: true } })
    try {
      const res  = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ combo_id: comboId, question })
      })
      const data = await res.json()
      const updated = [...prev, { user: question, assistant: data.answer, timestamp: new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) }]
      set({ chatHistory: { ...get().chatHistory, [comboId]: updated } })
    } catch (e) {
      const errHistory = [...prev, { user: question, assistant: `❌ ${e.message}`, timestamp: '--:--' }]
      set({ chatHistory: { ...get().chatHistory, [comboId]: errHistory } })
    } finally {
      set({ loading: { ...get().loading, chat: false } })
    }
  },

  // Clear chat
  clearChat: async (comboId) => {
    await fetch(`${API}/chat/${comboId}`, { method: 'DELETE' })
    set({ chatHistory: { ...get().chatHistory, [comboId]: [] } })
  },
}))
