type ServerState = {
  id: string
  name: string
  url: string
  status: 'online' | 'offline'
  reason?: string
  selectable: boolean
}

type SectionState = {
  servers: ServerState[]
  server: string
  sections: string[]
  section: string
  section_type: string
  series?: string[]
  serie?: string
  seasons?: string[]
  season?: string
  movies: string[]
  movie: string
  pos_time: string
}

type MovieInfo = {
  title?: string
  summary?: string
  duration?: number
  duration_ms?: number
  year?: number
}

export function useSelection() {
  const { apiFetch } = useApi()

  const selection = useState<SectionState | null>('selection', () => null)
  const movieInfo = useState<MovieInfo | null>('movieInfo', () => null)
  const loading = useState('selectionLoading', () => false)

  async function refreshSelection() {
    loading.value = true
    try {
      selection.value = await apiFetch<SectionState>('/api/selection')
      if (selection.value?.section && selection.value?.movie) {
        await refreshMovieInfo()
      } else {
        movieInfo.value = null
      }
    } finally {
      loading.value = false
    }
  }

  async function refreshMovieInfo() {
    movieInfo.value = await apiFetch<{ movie_info: MovieInfo }>('/api/movie').then((res) => res.movie_info)
  }

  async function selectServer(server: string) {
    selection.value = await apiFetch<SectionState>('/api/selection/server', {
      method: 'POST',
      body: { server },
    })
    if (selection.value?.section && selection.value?.movie) {
      await refreshMovieInfo()
    } else {
      movieInfo.value = null
    }
  }

  async function selectSection(section: string) {
    selection.value = await apiFetch<SectionState>('/api/selection/section', {
      method: 'POST',
      body: { section },
    })
    await refreshMovieInfo()
  }

  async function reloadSection(section?: string) {
    const previous = {
      section: section || selection.value?.section || '',
      serie: selection.value?.serie || '',
      season: selection.value?.season || '',
      movie: selection.value?.movie || '',
    }

    selection.value = await apiFetch<SectionState>('/api/selection/reload', {
      method: 'POST',
      body: { section: previous.section },
    })

    if (selection.value?.section_type === 'show') {
      if (previous.serie && selection.value?.series?.includes(previous.serie)) {
        await selectSeries(previous.serie)
      }
      if (previous.season && selection.value?.seasons?.includes(previous.season)) {
        await selectSeason(previous.season)
      }
    }

    if (previous.movie && selection.value?.movies?.includes(previous.movie)) {
      await selectMovie(previous.movie)
      return
    }

    await refreshMovieInfo()
  }

  async function selectSeries(serie: string) {
    selection.value = await apiFetch<SectionState>('/api/selection/series', {
      method: 'POST',
      body: { serie },
    })
    await refreshMovieInfo()
  }

  async function selectSeason(season: string) {
    selection.value = await apiFetch<SectionState>('/api/selection/season', {
      method: 'POST',
      body: { season },
    })
    await refreshMovieInfo()
  }

  async function selectMovie(movie: string) {
    selection.value = await apiFetch<SectionState>('/api/selection/movie', {
      method: 'POST',
      body: {
        section: selection.value?.section || '',
        serie: selection.value?.serie || '',
        season: selection.value?.season || '',
        movie,
      },
    })
    await refreshMovieInfo()
  }

  return {
    selection,
    movieInfo,
    loading,
    refreshSelection,
    refreshMovieInfo,
    selectServer,
    reloadSection,
    selectSection,
    selectSeries,
    selectSeason,
    selectMovie,
  }
}
