'use client'

import { useEffect, useState } from 'react'
import { Sun, Moon } from 'lucide-react'

export default function ThemeToggle() {
  const [light, setLight] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return document.documentElement.classList.contains('light')
  })

  useEffect(() => {
    // Sync with DOM class if modified externally
    const isLight = document.documentElement.classList.contains('light')
    setLight((prev) => (prev !== isLight ? isLight : prev))
  }, [])

  function toggle() {
    const next = !light
    setLight(next)
    if (next) {
      document.documentElement.classList.add('light')
      localStorage.setItem('theme', 'light')
    } else {
      document.documentElement.classList.remove('light')
      localStorage.setItem('theme', 'dark')
    }
  }

  const label = light ? 'Switch to dark mode' : 'Switch to light mode'

  return (
    <button
      onClick={toggle}
      title={label}
      aria-label={label}
      aria-pressed={light}
      className="flex items-center justify-center w-7 h-7 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-700/50 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
    >
      {light ? <Sun size={14} aria-hidden="true" /> : <Moon size={14} aria-hidden="true" />}
    </button>
  )
}
