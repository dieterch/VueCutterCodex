type AnalysisBoundaryKind = 'content_start' | 'content_end' | 'ad_start' | 'ad_end'

type AnalysisBoundary = {
  id: string
  kind: AnalysisBoundaryKind
  time: string
  confidence: number
}

type AnalysisKeepInterval = {
  t0: string
  t1: string
  start_id: string
  end_id: string
}

type AnalysisResult = {
  movie: string
  duration: string
  mode?: 'start_end' | 'full'
  boundaries: AnalysisBoundary[]
  keep_intervals: AnalysisKeepInterval[]
  warnings: string[]
  analysis_seconds: number
  cancelled?: boolean
  cached?: boolean
}

type AnalysisStatusResponse = {
  job_id: string
  status: string
  movie?: string
  mode?: 'start_end' | 'full'
  error?: string
  progress?: {
    phase: string
    percent: number
    movie?: string
    cancellable?: boolean
    mode?: 'start_end' | 'full'
  }
  result?: AnalysisResult
}

type AnalysisRequest = {
  section: string
  serie?: string
  season?: string
  movie_name: string
  mode?: 'start_end' | 'full'
}

function sortBoundaries(boundaries: AnalysisBoundary[], strToPos: (value: string) => number) {
  return [...boundaries].sort((left, right) => strToPos(left.time) - strToPos(right.time))
}

function deriveKeepIntervals(boundaries: AnalysisBoundary[], strToPos: (value: string) => number, posToStr: (value: number) => string) {
  const warnings: string[] = []
  const startBoundary = boundaries.find((boundary) => boundary.kind === 'content_start')
  const endBoundary = boundaries.find((boundary) => boundary.kind === 'content_end')

  if (!startBoundary || !endBoundary) {
    return {
      keepIntervals: [] as AnalysisKeepInterval[],
      warnings: ['Unable to derive keep intervals because start/end detection is incomplete.'],
    }
  }

  const startSeconds = strToPos(startBoundary.time)
  const endSeconds = strToPos(endBoundary.time)
  if (endSeconds <= startSeconds) {
    return {
      keepIntervals: [] as AnalysisKeepInterval[],
      warnings: ['Detected end is not after detected start.'],
    }
  }

  const keepIntervals: AnalysisKeepInterval[] = []
  let cursorSeconds = startSeconds
  let cursorId = startBoundary.id
  const adStarts = sortBoundaries(boundaries.filter((boundary) => boundary.kind === 'ad_start'), strToPos)
  const adEnds = sortBoundaries(boundaries.filter((boundary) => boundary.kind === 'ad_end'), strToPos)
  let adEndIndex = 0

  for (const adStart of adStarts) {
    const adStartSeconds = strToPos(adStart.time)
    if (adStartSeconds <= cursorSeconds || adStartSeconds >= endSeconds) {
      continue
    }
    while (adEndIndex < adEnds.length && strToPos(adEnds[adEndIndex].time) <= adStartSeconds) {
      adEndIndex += 1
    }
    if (adEndIndex >= adEnds.length) {
      warnings.push(`Ad start at ${adStart.time} has no matching ad end.`)
      break
    }
    const adEnd = adEnds[adEndIndex]
    const adEndSeconds = strToPos(adEnd.time)
    if (adEndSeconds <= adStartSeconds) {
      warnings.push(`Ad end at ${adEnd.time} is not after ad start ${adStart.time}.`)
      adEndIndex += 1
      continue
    }
    if (adStartSeconds > cursorSeconds) {
      keepIntervals.push({
        t0: posToStr(cursorSeconds),
        t1: adStart.time,
        start_id: cursorId,
        end_id: adStart.id,
      })
    }
    cursorSeconds = adEndSeconds
    cursorId = adEnd.id
    adEndIndex += 1
  }

  if (cursorSeconds < endSeconds) {
    keepIntervals.push({
      t0: posToStr(cursorSeconds),
      t1: endBoundary.time,
      start_id: cursorId,
      end_id: endBoundary.id,
    })
  }

  return {
    keepIntervals: keepIntervals.filter((interval) => strToPos(interval.t1) > strToPos(interval.t0)),
    warnings,
  }
}

export function useAnalysis() {
  const { apiFetch } = useApi()
  const { posToStr, strToPos } = useTimecode()
  const cutlist = useState<{ t0: string; t1: string }[]>('cutlist', () => [])

  const jobId = useState('analysisJobId', () => '')
  const status = useState('analysisStatus', () => 'idle')
  const running = useState('analysisRunning', () => false)
  const polling = useState('analysisPolling', () => false)
  const pollingTimer = useState<ReturnType<typeof setInterval> | null>('analysisPollingTimer', () => null)
  const draft = useState<AnalysisResult | null>('analysisDraft', () => null)
  const error = useState('analysisError', () => '')
  const mode = useState<'start_end' | 'full'>('analysisMode', () => 'start_end')
  const activeBoundaryId = useState('analysisActiveBoundaryId', () => '')
  const progress = useState('analysisProgress', () => ({
    phase: 'idle',
    percent: 0,
    movie: '',
    cancellable: false,
    mode: 'start_end' as 'start_end' | 'full',
  }))

  function stopPolling() {
    if (pollingTimer.value) {
      clearInterval(pollingTimer.value)
      pollingTimer.value = null
    }
    polling.value = false
    running.value = false
  }

  function reset() {
    stopPolling()
    jobId.value = ''
    status.value = 'idle'
    draft.value = null
    error.value = ''
    mode.value = 'start_end'
    activeBoundaryId.value = ''
    progress.value = {
      phase: 'idle',
      percent: 0,
      movie: '',
      cancellable: false,
      mode: 'start_end',
    }
  }

  function applyStatusResponse(response: AnalysisStatusResponse) {
    jobId.value = response.job_id
    status.value = response.status
    if (response.mode) {
      mode.value = response.mode
    }
    if (response.result) {
      draft.value = response.result
      if (response.result.mode) {
        mode.value = response.result.mode
      }
      if (!activeBoundaryId.value && response.result.boundaries.length > 0) {
        activeBoundaryId.value = response.result.boundaries[0].id
      }
    }
    if (response.progress) {
      progress.value = {
        phase: response.progress.phase,
        percent: response.progress.percent,
        movie: response.progress.movie || '',
        cancellable: response.progress.cancellable ?? false,
        mode: response.progress.mode || mode.value,
      }
    }
    if (response.error) {
      error.value = response.error
    }
  }

  async function refreshStatus() {
    if (!jobId.value) {
      return
    }
    const response = await apiFetch<AnalysisStatusResponse>(`/api/analyze/recording/${jobId.value}`)
    applyStatusResponse(response)
    if (response.status === 'finished' || response.status === 'failed' || response.status === 'cancelled') {
      stopPolling()
    }
  }

  function startPolling(intervalMs = 3000) {
    stopPolling()
    polling.value = true
    running.value = true
    pollingTimer.value = setInterval(async () => {
      try {
        await refreshStatus()
      } catch (cause: any) {
        error.value = cause?.data?.error || cause?.message || 'Unable to refresh analysis status.'
        stopPolling()
      }
    }, intervalMs)
  }

  async function start(request: AnalysisRequest) {
    reset()
    mode.value = request.mode || 'start_end'
    const response = await apiFetch<AnalysisStatusResponse>('/api/analyze/recording', {
      method: 'POST',
      body: request,
    })
    applyStatusResponse(response)
    if (response.status === 'finished' && response.result) {
      running.value = false
      return
    }
    running.value = true
    startPolling()
  }

  async function cancel() {
    if (!jobId.value || !running.value) {
      return
    }
    const response = await apiFetch<AnalysisStatusResponse>(`/api/analyze/recording/${jobId.value}/cancel`, {
      method: 'POST',
    })
    applyStatusResponse(response)
    if (response.status === 'cancelled') {
      stopPolling()
    }
  }

  function selectBoundary(boundaryId: string) {
    activeBoundaryId.value = boundaryId
  }

  function setActiveBoundaryTime(time: string) {
    if (!draft.value || !activeBoundaryId.value) {
      return
    }
    const nextBoundaries = sortBoundaries(
      draft.value.boundaries.map((boundary) => (
        boundary.id === activeBoundaryId.value
          ? { ...boundary, time }
          : boundary
      )),
      strToPos,
    )
    const derived = deriveKeepIntervals(nextBoundaries, strToPos, posToStr)
    draft.value = {
      ...draft.value,
      boundaries: nextBoundaries,
      keep_intervals: derived.keepIntervals,
      warnings: derived.warnings,
    }
  }

  function applyDraftToCutlist() {
    if (!draft.value) {
      return
    }
    cutlist.value = draft.value.keep_intervals.map((interval) => ({
      t0: interval.t0,
      t1: interval.t1,
    }))
  }

  const activeBoundary = computed(() => draft.value?.boundaries.find((boundary) => boundary.id === activeBoundaryId.value) ?? null)

  return {
    jobId,
    status,
    running,
    polling,
    draft,
    error,
    progress,
    mode,
    activeBoundaryId,
    activeBoundary,
    start,
    cancel,
    reset,
    refreshStatus,
    selectBoundary,
    setActiveBoundaryTime,
    applyDraftToCutlist,
  }
}
