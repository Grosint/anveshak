import axios from 'axios'

const api = axios.create({ baseURL: '/' })

// Attach JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('anveshak_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Global 401 handler — clear token and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('anveshak_token')
      localStorage.removeItem('anveshak_session_id')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export default api
