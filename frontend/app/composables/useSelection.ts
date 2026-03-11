type SectionState = {
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
      movieInfo.value = await apiFetch<{ movie_info: MovieInfo }>('/api/movie').then((res) => res.movie_info)
    } finally {
      loading.value = false
    }
  }

  async function selectSection(section: string) {
    selection.value = await apiFetch<SectionState>('/api/selection/section', {
      method: 'POST',
      body: { section },
    })
    movieInfo.value = await apiFetch<{ movie_info: MovieInfo }>('/api/movie').then((res) => res.movie_info)
  }

  async function selectSeries(serie: string) {
    selection.value = await apiFetch<SectionState>('/api/selection/series', {
      method: 'POST',
      body: { serie },
    })
    movieInfo.value = await apiFetch<{ movie_info: MovieInfo }>('/api/movie').then((res) => res.movie_info)
  }

  async function selectSeason(season: string) {
    selection.value = await apiFetch<SectionState>('/api/selection/season', {
      method: 'POST',
      body: { season },
    })
    movieInfo.value = await apiFetch<{ movie_info: MovieInfo }>('/api/movie').then((res) => res.movie_info)
  }

  async function selectMovie(movie: string) {
    selection.value = await apiFetch<SectionState>('/api/selection/movie', {
      method: 'POST',
      body: { movie },
    })
    movieInfo.value = await apiFetch<{ movie_info: MovieInfo }>('/api/movie').then((res) => res.movie_info)
  }

  return {
    selection,
    movieInfo,
    loading,
    refreshSelection,
    selectSection,
    selectSeries,
    selectSeason,
    selectMovie,
  }
}
