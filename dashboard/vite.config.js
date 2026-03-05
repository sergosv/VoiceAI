import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    // Fallback: si las env vars no se inyectan (Cloudflare Pages), usar valores de producción
    ...(!process.env.VITE_SUPABASE_URL && {
      'import.meta.env.VITE_SUPABASE_URL': JSON.stringify('https://tfecomyseybwlvmoypqh.supabase.co'),
      'import.meta.env.VITE_SUPABASE_ANON_KEY': JSON.stringify('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRmZWNvbXlzZXlid2x2bW95cHFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIxNDMwNjUsImV4cCI6MjA4NzcxOTA2NX0.OmZf_QRElCpuUGxHUogtEKcMQeXLpF-OfRCHAgwfr6w'),
      'import.meta.env.VITE_API_URL': JSON.stringify('https://voiceai-production-f4e4.up.railway.app/api'),
    }),
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
