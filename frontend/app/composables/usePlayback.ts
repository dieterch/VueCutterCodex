type FrameResponse = {
  frame: string
}

type ProgressState = {
  title: string
  cut_progress: number
  apsc_progress: number
  started: number
  status: string
}

export function usePlayback() {
  const { apiFetch } = useApi()
  const positionSeconds = useState('positionSeconds', () => 0)
  const frameUrl = useState('frameUrl', () => '')
  const frameLoading = useState('frameLoading', () => false)
  const frameError = useState('frameError', () => '')
  const mediaAvailable = useState('mediaAvailable', () => true)
  const progress = useState<ProgressState>('progress', () => ({
    title: '-',
    cut_progress: 0,
    apsc_progress: 0,
    started: 0,
    status: 'idle',
  }))
  const polling = useState('progressPolling', () => false)
  const pollingTimer = useState<ReturnType<typeof setInterval> | null>('progressPollingTimer', () => null)

  async function loadFrame(movieName: string, posTime: string) {
    if (!movieName) {
      frameUrl.value = ''
      frameError.value = ''
      mediaAvailable.value = true
      return
    }
    frameLoading.value = true
    try {
      const response = await apiFetch<FrameResponse>('/api/frame', {
        method: 'POST',
        body: {
          movie_name: movieName,
          pos_time: posTime,
        },
      })
      frameUrl.value = withCacheBust(normalizeFrameUrl(response.frame))
      frameError.value = ''
      mediaAvailable.value = true
    } catch (error: any) {
      frameUrl.value = ''
      frameError.value = error?.data?.error || error?.message || 'Unable to load frame.'
      mediaAvailable.value = false
    } finally {
      frameLoading.value = false
    }
  }

  function clearFrameState() {
    frameUrl.value = ''
    frameError.value = ''
    frameLoading.value = false
    mediaAvailable.value = true
  }

  async function refreshProgress() {
    progress.value = await apiFetch<ProgressState>('/api/progress')
  }

  function stopProgressPolling() {
    if (pollingTimer.value) {
      clearInterval(pollingTimer.value)
      pollingTimer.value = null
    }
    polling.value = false
  }

  function startProgressPolling(intervalMs = 3000) {
    stopProgressPolling()
    polling.value = true
    pollingTimer.value = setInterval(async () => {
      try {
        await refreshProgress()
        if (progress.value.status === 'idle' && progress.value.started === 0) {
          stopProgressPolling()
        }
      } catch {
        stopProgressPolling()
      }
    }, intervalMs)
  }

  return {
    positionSeconds,
    frameUrl,
    frameLoading,
    frameError,
    mediaAvailable,
    progress,
    polling,
    loadFrame,
    clearFrameState,
    refreshProgress,
    startProgressPolling,
    stopProgressPolling,
  }
}

function normalizeFrameUrl(url: string) {
  if (!url) {
    return ''
  }
  try {
    const parsed = new URL(url)
    if (parsed.pathname.startsWith('/static/')) {
      return `/backend-static/${parsed.pathname.slice('/static/'.length)}`
    }
  } catch {
    if (url.startsWith('/static/')) {
      return `/backend-static/${url.slice('/static/'.length)}`
    }
  }
  return url
}

function withCacheBust(url: string) {
  if (!url) {
    return ''
  }
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}t=${Date.now()}`
}
