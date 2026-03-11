export function zeroPad(num: number, places = 2) {
  return String(Math.trunc(num)).padStart(places, '0')
}

export function posToStr(pos: number) {
  const safe = Math.max(0, Math.trunc(pos))
  const hours = Math.trunc(safe / 3600)
  const minutes = Math.trunc((safe % 3600) / 60)
  const seconds = safe % 60
  return `${zeroPad(hours)}:${zeroPad(minutes)}:${zeroPad(seconds)}`
}

export function strToPos(value: string) {
  const match = /^(\d{2}):(\d{2}):(\d{2})$/.exec(value)
  if (!match) {
    return 0
  }
  return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3])
}

export function posValid(pos: number, durationSeconds: number) {
  if (durationSeconds <= 0) {
    return 0
  }
  return Math.min(Math.max(0, Math.trunc(pos)), Math.trunc(durationSeconds))
}

export function useTimecode() {
  return {
    zeroPad,
    posToStr,
    strToPos,
    posValid,
  }
}
