export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const path = getRouterParam(event, 'path') || ''
  const query = getRequestURL(event).search
  const target = `${config.apiProxyBase}/static/${path}${query}`

  return proxyRequest(event, target)
})
