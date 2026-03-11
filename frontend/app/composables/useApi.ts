export function useApi() {
  const config = useRuntimeConfig()

  const apiFetch = <T>(path: string, options: Parameters<typeof $fetch<T>>[1] = {}) => {
    return $fetch<T>(path, {
      baseURL: config.public.apiBase || '',
      ...options,
    })
  }

  return {
    apiBase: config.public.apiBase,
    apiFetch,
  }
}
