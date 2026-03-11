export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const path = getRouterParam(event, 'path') || ''
  const query = getRequestURL(event).search
  const target = `${config.apiProxyBase}/api/${path}${query}`

  const method = event.method
  const body = ['GET', 'HEAD'].includes(method) ? undefined : await readBody(event)
  const contentType = getHeader(event, 'content-type') || 'application/json'
  const encodedBody = body === undefined
    ? undefined
    : contentType.includes('application/json')
      ? JSON.stringify(body)
      : body

  return proxyRequest(event, target, {
    fetchOptions: {
      method,
      body: encodedBody,
      headers: {
        'content-type': contentType,
      },
    },
  })
})
