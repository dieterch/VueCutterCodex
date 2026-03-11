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
  const frameUrl = useState('frameUrl', () => '')
  const progress = useState<ProgressState>('progress', () => ({
    title: '-',
    cut_progress: 0,
    apsc_progress: 0,
    started: 0,
    status: 'idle',
  }))

  async function loadFrame(movieName: string, posTime: string) {
    if (!movieName) {
      frameUrl.value = ''
      return
    }
    const response = await apiFetch<FrameResponse>('/api/frame', {
      method: 'POST',
      body: {
        movie_name: movieName,
        pos_time: posTime,
      },
    })
    frameUrl.value = response.frame
  }

  async function refreshProgress() {
    progress.value = await apiFetch<ProgressState>('/api/progress')
  }

  return {
    frameUrl,
    progress,
    loadFrame,
    refreshProgress,
  }
}
