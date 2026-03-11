type TimelineRequest = {
  basename: string
  pos: number
  l: number
  r: number
  step: number
  size: string
}

type TimelineItem = {
  pos: number
  label: string
  src: string
}

export function useTimeline() {
  const { apiFetch } = useApi()
  const { posToStr, posValid } = useTimecode()

  const enabled = useState('timelineEnabled', () => false)
  const request = useState<TimelineRequest>('timelineRequest', () => ({
    basename: 'frame.gif',
    pos: 0,
    l: -4,
    r: 4,
    step: 1,
    size: '160',
  }))
  const items = useState<TimelineItem[]>('timelineItems', () => [])

  function frameSrc(label: string) {
    const basename = request.value.basename
    return `/backend-static/${basename.slice(0, -4)}_${label}${basename.slice(-4)}`
  }

  async function refresh(position: number, durationSeconds: number) {
    if (!enabled.value) {
      items.value = []
      return
    }

    const payload = {
      ...request.value,
      pos: position,
    }
    await apiFetch<{ status: string }>('/api/timeline', {
      method: 'POST',
      body: payload,
    })

    const nextItems: TimelineItem[] = []
    for (let offset = request.value.l; offset <= request.value.r; offset += 1) {
      const pos = posValid(position + offset * Math.abs(request.value.step), durationSeconds)
      const label = posToStr(pos)
      nextItems.push({
        pos,
        label,
        src: frameSrc(label),
      })
    }
    items.value = nextItems
  }

  function toggle() {
    enabled.value = !enabled.value
  }

  function pageDelta() {
    return (request.value.r - request.value.l) * request.value.step
  }

  return {
    enabled,
    request,
    items,
    refresh,
    toggle,
    pageDelta,
  }
}
