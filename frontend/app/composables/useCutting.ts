type CutInterval = {
  t0: string
  t1: string
}

type CutInfo = {
  movie: string
  eta: number
  eta_cut: number
  eta_apsc: number
  cutfile: boolean
  apsc: boolean
}

export function useCutting() {
  const { apiFetch } = useApi()
  const { refreshProgress, startProgressPolling } = usePlayback()

  const cutStart = useState('cutStart', () => '')
  const cutEnd = useState('cutEnd', () => '')
  const cutlist = useState<CutInterval[]>('cutlist', () => [])
  const dialogOpen = useState('cutDialogOpen', () => false)
  const inplace = useState('cutInplace', () => true)
  const useffmpeg = useState('cutUseffmpeg', () => true)
  const cutInfo = useState<CutInfo | null>('cutInfo', () => null)
  const submitting = useState('cutSubmitting', () => false)
  const submissionError = useState('cutSubmissionError', () => '')

  function resetMarkers() {
    cutStart.value = ''
    cutEnd.value = ''
  }

  function normalizeCutlist(list: CutInterval[]) {
    const sorted = [...list].sort((a, b) => a.t0.localeCompare(b.t0))
    const valid = sorted.every((interval) => interval.t1 > interval.t0)
    const merged = sorted.reduce<CutInterval[]>((acc, interval) => {
      if (acc.length === 0) {
        acc.push({ ...interval })
        return acc
      }
      const last = acc[acc.length - 1]
      if (interval.t0 <= last.t1) {
        last.t1 = interval.t1
      } else {
        acc.push({ ...interval })
      }
      return acc
    }, [])
    return { valid, merged }
  }

  function addInterval(interval: CutInterval) {
    if (cutlist.value.some((entry) => entry.t0 === interval.t0 && entry.t1 === interval.t1)) {
      return
    }
    const result = normalizeCutlist([...cutlist.value, interval])
    cutlist.value = result.merged
    return result.valid
  }

  async function loadCutInfo() {
    cutInfo.value = await apiFetch<CutInfo>('/api/movie-cut-info')
  }

  async function openDialog(section: string, movie: string) {
    if (!cutStart.value || !cutEnd.value) {
      return false
    }
    addInterval({ t0: cutStart.value, t1: cutEnd.value })
    await loadCutInfo()
    dialogOpen.value = true
    return true
  }

  async function submit(section: string, movie: string) {
    if (!movie || cutlist.value.length === 0) {
      return
    }
    submitting.value = true
    submissionError.value = ''
    try {
      await apiFetch('/api/cut', {
        method: 'POST',
        body: {
          section,
          movie_name: movie,
          cutlist: cutlist.value,
          inplace: inplace.value,
          useffmpeg: useffmpeg.value,
          etaest: cutInfo.value?.eta ?? 0,
        },
      })
      dialogOpen.value = false
      await refreshProgress()
      startProgressPolling()
    } catch (error: any) {
      submissionError.value = error?.data?.error || error?.message || 'Unable to start cut.'
      throw error
    } finally {
      submitting.value = false
    }
  }

  function resetAll() {
    resetMarkers()
    cutlist.value = []
    dialogOpen.value = false
    cutInfo.value = null
    submitting.value = false
    submissionError.value = ''
    inplace.value = true
    useffmpeg.value = true
  }

  return {
    cutStart,
    cutEnd,
    cutlist,
    dialogOpen,
    inplace,
    useffmpeg,
    cutInfo,
    submitting,
    submissionError,
    addInterval,
    openDialog,
    submit,
    resetMarkers,
    resetAll,
  }
}
