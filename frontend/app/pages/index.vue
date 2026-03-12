<script setup lang="ts">
const { posToStr, strToPos, posValid } = useTimecode()
const { selection, movieInfo, loading, refreshSelection, reloadSection, selectSection, selectSeries, selectSeason, selectMovie } = useSelection()
const { positionSeconds, frameUrl, frameLoading, frameError, mediaAvailable, loadFrame, clearFrameState, refreshProgress, progress, polling } = usePlayback()
const {
  enabled: timelineEnabled,
  request: timelineRequest,
  items: timelineItems,
  refresh: refreshTimelineItems,
  toggle: toggleTimelineEnabled,
  pageDelta,
} = useTimeline()
const {
  cutStart,
  cutEnd,
  cutlist,
  dialogOpen,
  inplace,
  cutInfo,
  submitting,
  submissionError,
  addInterval,
  openDialog,
  submit,
  resetMarkers,
  resetAll,
} = useCutting()
const {
  status: analysisStatus,
  running: analysisRunning,
  polling: analysisPolling,
  draft: analysisDraft,
  error: analysisError,
  activeBoundaryId,
  activeBoundary,
  start: startAnalysis,
  reset: resetAnalysis,
  selectBoundary,
  setActiveBoundaryTime,
  applyDraftToCutlist,
} = useAnalysis()

const durationSeconds = computed(() => Math.trunc((movieInfo.value?.duration_ms ?? 0) / 1000))
const durationLabel = computed(() => (durationSeconds.value > 0 ? posToStr(durationSeconds.value) : '--:--:--'))
const positionMinuteLabel = computed(() => `${Math.trunc(positionSeconds.value / 60)}'`)
const safeTimelineItems = computed(() => timelineItems.value.filter((item) => item && item.label))
const safeCutlist = computed(() => cutlist.value.filter((interval) => interval && interval.t0 && interval.t1))
const safeAnalysisBoundaries = computed(() => analysisDraft.value?.boundaries ?? [])
const safeAnalysisIntervals = computed(() => analysisDraft.value?.keep_intervals ?? [])
const analysisWarnings = computed(() => analysisDraft.value?.warnings ?? [])
const mediaActionsDisabled = computed(() => frameLoading.value || !mediaAvailable.value)
const markersFormValid = computed(() => Boolean(cutStart.value && cutEnd.value && cutEnd.value > cutStart.value))
const canRunAnalysis = computed(() => Boolean(selection.value?.movie) && !mediaActionsDisabled.value && !analysisRunning.value)
const canOpenCutDialog = computed(() => {
  if (mediaActionsDisabled.value) {
    return false
  }
  if (timelineRequest.value.step !== 1) {
    return false
  }
  return markersFormValid.value || safeCutlist.value.length > 0
})
const positionString = computed({
  get: () => posToStr(positionSeconds.value),
  set: (value: string) => {
    positionSeconds.value = posValid(strToPos(value), durationSeconds.value)
  },
})

const leftJumpButtons = [
  { label: `-10'`, delta: -600 },
  { label: `-5'`, delta: -300 },
  { label: `-1'`, delta: -60 },
  { label: `-30"`, delta: -30 },
  { label: `-10"`, delta: -10 },
  { label: `-5"`, delta: -5 },
  { label: `-1"`, delta: -1 },
]

const rightJumpButtons = [
  { label: `+10'`, delta: 600 },
  { label: `+5'`, delta: 300 },
  { label: `+1'`, delta: 60 },
  { label: `+30"`, delta: 30 },
  { label: `+10"`, delta: 10 },
  { label: `+5"`, delta: 5 },
  { label: `+1"`, delta: 1 },
]

async function refreshFrame() {
  if (!selection.value?.movie) {
    clearFrameState()
    return
  }
  positionSeconds.value = posValid(positionSeconds.value, durationSeconds.value)
  await loadFrame(selection.value.movie, posToStr(positionSeconds.value)).catch(() => {})
}

async function jump(delta: number) {
  positionSeconds.value = posValid(positionSeconds.value + delta, durationSeconds.value)
  timelineRequest.value.step = Math.abs(delta) || 1
  if (!mediaAvailable.value) {
    return
  }
  await refreshFrame()
  if (timelineEnabled.value) {
    await refreshTimeline()
  }
}

async function jumpTo(position: number) {
  positionSeconds.value = posValid(position, durationSeconds.value)
  if (!mediaAvailable.value) {
    return
  }
  await refreshFrame()
}

async function toggleTimeline() {
  if (!mediaAvailable.value && !timelineEnabled.value) {
    return
  }
  toggleTimelineEnabled()
  if (timelineEnabled.value) {
    await refreshTimelineItems(positionSeconds.value, durationSeconds.value).catch(() => {})
  }
}

async function refreshTimeline() {
  if (!timelineEnabled.value || !mediaAvailable.value) {
    return
  }
  await refreshTimelineItems(positionSeconds.value, durationSeconds.value).catch(() => {})
}

async function pageTimeline(direction: -1 | 1) {
  if (!timelineEnabled.value || !mediaAvailable.value) {
    return
  }
  positionSeconds.value = posValid(positionSeconds.value + direction * pageDelta(), durationSeconds.value)
  await refreshFrame()
  await refreshTimeline()
}

function setCutStart() {
  cutStart.value = positionString.value
}

function setCutEnd() {
  cutEnd.value = positionString.value
}

function addCurrentInterval() {
  if (markersFormValid.value) {
    addInterval({ t0: cutStart.value, t1: cutEnd.value })
    resetMarkers()
  }
}

async function openCutDialog() {
  if (!selection.value?.section || !selection.value?.movie || mediaActionsDisabled.value) {
    return
  }
  await openDialog(selection.value.section, selection.value.movie)
}

async function submitCut() {
  if (!selection.value?.section || !selection.value?.movie || mediaActionsDisabled.value) {
    return
  }
  await submit(selection.value.section, selection.value.movie).catch(() => {})
}

function removeCutInterval(index: number) {
  const next = [...cutlist.value]
  next.splice(index, 1)
  cutlist.value = next
}

function resetEverything() {
  resetAll()
  resetAnalysis()
}

function analysisBoundaryLabel(kind: string) {
  switch (kind) {
    case 'content_start':
      return 'Start'
    case 'content_end':
      return 'End'
    case 'ad_start':
      return 'Ad Start'
    case 'ad_end':
      return 'Ad End'
    default:
      return kind
  }
}

async function focusDetectedBoundary(boundaryId: string) {
  const boundary = safeAnalysisBoundaries.value.find((entry) => entry.id === boundaryId)
  if (!boundary) {
    return
  }
  selectBoundary(boundaryId)
  await jumpTo(strToPos(boundary.time))
}

function applyCurrentPositionToBoundary() {
  if (!activeBoundary.value) {
    return
  }
  setActiveBoundaryTime(positionString.value)
}

function applyDetectedIntervals() {
  applyDraftToCutlist()
  resetMarkers()
}

async function analyzeRecording() {
  if (!selection.value?.section || !selection.value?.movie || mediaActionsDisabled.value) {
    return
  }
  await startAnalysis({
    section: selection.value.section,
    serie: selection.value.serie,
    season: selection.value.season,
    movie_name: selection.value.movie,
  }).catch(() => {})
}

async function changeSection(value: string) {
  await selectSection(value)
  positionSeconds.value = 0
  clearFrameState()
  timelineItems.value = []
  resetAnalysis()
  await refreshFrame()
}

async function changeSeries(value: string) {
  await selectSeries(value)
  positionSeconds.value = 0
  clearFrameState()
  timelineItems.value = []
  resetAnalysis()
  await refreshFrame()
}

async function changeSeason(value: string) {
  await selectSeason(value)
  positionSeconds.value = 0
  clearFrameState()
  timelineItems.value = []
  resetAnalysis()
  await refreshFrame()
}

async function changeMovie(value: string) {
  await selectMovie(value)
  positionSeconds.value = 0
  clearFrameState()
  timelineItems.value = []
  resetAnalysis()
  await refreshFrame()
}

onMounted(async () => {
  resetAll()
  resetAnalysis()
  timelineEnabled.value = false
  timelineItems.value = []
  clearFrameState()
  try {
    await refreshSelection()
  } catch {}
  if (selection.value?.movie) {
    await refreshFrame()
  }
  try {
    await refreshProgress()
  } catch {}
})

async function reloadCurrentSection() {
  if (!selection.value?.section) {
    return
  }
  await reloadSection(selection.value.section)
  positionSeconds.value = 0
  clearFrameState()
  timelineItems.value = []
  resetAnalysis()
  await refreshFrame()
}
</script>

<template>
  <v-app>
    <v-main>
      <v-container fluid class="compact-shell pa-3">
        <v-card rounded="lg" elevation="1" class="selection-bar">
          <v-card-text class="pa-3">
            <div class="selection-grid">
              <div class="selection-field selection-field-section">
                <v-select
                  :items="selection?.sections ?? []"
                  :model-value="selection?.section ?? null"
                  :loading="loading"
                  label="Section"
                  density="compact"
                  hide-details
                  @update:model-value="changeSection"
                />
              </div>

              <div v-if="selection?.section_type === 'show'" class="selection-field selection-field-series">
                <v-select
                  :items="selection?.series ?? []"
                  :model-value="selection?.serie ?? null"
                  label="Series"
                  density="compact"
                  hide-details
                  @update:model-value="changeSeries"
                />
              </div>

              <div v-if="selection?.section_type === 'show'" class="selection-field selection-field-season">
                <v-select
                  :items="selection?.seasons ?? []"
                  :model-value="selection?.season ?? null"
                  label="Season"
                  density="compact"
                  hide-details
                  @update:model-value="changeSeason"
                />
              </div>

              <div class="selection-field selection-field-movie">
                <v-select
                  :items="selection?.movies ?? []"
                  :model-value="selection?.movie ?? null"
                  label="Movie"
                  density="compact"
                  hide-details
                  @update:model-value="changeMovie"
                />
              </div>

              <v-btn size="small" variant="text" icon="mdi-reload" class="selection-reload" @click="reloadCurrentSection" />
            </div>
          </v-card-text>
        </v-card>

        <v-row class="mt-2 preview-layout" dense>
          <v-col class="preview-main">
            <v-card rounded="lg" elevation="1" class="preview-card">
              <v-card-text class="pa-3">
                <v-alert
                  v-if="frameError"
                  type="warning"
                  variant="tonal"
                  density="compact"
                  class="mb-2"
                  title="Media source unavailable"
                  :text="frameError"
                />

                <v-alert
                  v-else-if="!mediaAvailable"
                  type="info"
                  variant="tonal"
                  density="compact"
                  class="mb-2"
                  text="The NAS or host media mount is unavailable. Frame preview is disabled until the media path exists."
                />

                <div v-if="timelineEnabled" class="timeline-strip mb-2">
                  <button
                    v-for="item in safeTimelineItems"
                    :key="`${item.label}-${item.pos}`"
                    class="timeline-item"
                    type="button"
                    :disabled="mediaActionsDisabled"
                    @click="jumpTo(item.pos)"
                  >
                    <img :src="item.src" :alt="item.label" />
                  </button>
                </div>

                <v-img
                  v-if="frameUrl"
                  :src="frameUrl"
                  aspect-ratio="16/9"
                  contain
                  class="border preview-frame"
                />

                <v-skeleton-loader
                  v-else-if="frameLoading"
                  type="image"
                  class="preview-frame"
                />

                <v-sheet
                  v-else
                  class="d-flex align-center justify-center border pa-6 text-medium-emphasis preview-frame"
                >
                  No preview loaded.
                </v-sheet>

                <div class="preview-toolbar mt-2">
                  <v-chip size="small" variant="text" prepend-icon="mdi-movie-open">
                    {{ durationLabel }} / {{ movieInfo?.duration ?? '-' }}'
                  </v-chip>
                  <v-chip size="small" variant="text" prepend-icon="mdi-movie-open-edit">
                    {{ positionString }} / {{ positionMinuteLabel }}
                  </v-chip>
                  <v-text-field
                    v-model="positionString"
                    label="Position"
                    hide-details
                    density="compact"
                    class="position-field"
                  />
                  <v-btn size="small" color="primary" :loading="frameLoading" @click="refreshFrame">
                    Load Frame
                  </v-btn>
                  <v-btn size="small" icon="mdi-arrow-left-bold-box-outline" :disabled="!timelineEnabled || mediaActionsDisabled" @click="pageTimeline(-1)" />
                  <v-btn size="small" icon="mdi-filmstrip" color="primary" :disabled="!mediaAvailable && !timelineEnabled" @click="toggleTimeline" />
                  <v-btn size="small" icon="mdi-arrow-right-bold-box-outline" :disabled="!timelineEnabled || mediaActionsDisabled" @click="pageTimeline(1)" />
                  <v-btn size="small" icon="mdi-refresh" :disabled="!timelineEnabled || mediaActionsDisabled" @click="refreshTimeline" />
                </div>

                <div class="movie-meta mt-2">
                  <div><strong>{{ movieInfo?.title ?? '-' }}</strong><span v-if="movieInfo?.year"> ({{ movieInfo.year }})</span></div>
                  <div class="text-medium-emphasis">{{ movieInfo?.summary ?? '-' }}</div>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col class="preview-sidebar">
            <v-card rounded="lg" elevation="1" class="side-rail">
              <v-card-text class="pa-2 rail-body">
                <div class="rail-top-buttons">
                  <v-btn size="small" color="primary" variant="tonal" class="rail-btn rail-top-btn" :disabled="mediaActionsDisabled" @click="jumpTo(0)">
                    <v-icon size="16">mdi-format-horizontal-align-left</v-icon>
                  </v-btn>
                  <v-btn size="small" color="primary" variant="tonal" class="rail-btn rail-top-btn" :disabled="mediaActionsDisabled" @click="jumpTo(durationSeconds)">
                    <v-icon size="16">mdi-format-horizontal-align-right</v-icon>
                  </v-btn>
                  <v-btn size="small" color="secondary" variant="tonal" class="rail-btn rail-top-btn" :disabled="mediaActionsDisabled" @click="jumpTo(Math.min(15 * 60, durationSeconds))">
                    +15'
                  </v-btn>
                  <v-btn size="small" color="secondary" variant="tonal" class="rail-btn rail-top-btn" :disabled="mediaActionsDisabled" @click="jumpTo(Math.max(durationSeconds - 15 * 60, 0))">
                    -15'
                  </v-btn>
                </div>
                <div class="rail-columns">
                  <div class="rail-column">
                    <v-btn
                      v-for="button in leftJumpButtons"
                      :key="button.label"
                      size="small"
                      variant="tonal"
                      class="rail-btn"
                      :disabled="mediaActionsDisabled"
                      @click="jump(button.delta)"
                    >
                      <span :class="{ 'active-step': Math.abs(button.delta) === timelineRequest.step }">
                        {{ button.label }}
                      </span>
                    </v-btn>
                  </div>
                  <div class="rail-column">
                    <v-btn
                      v-for="button in rightJumpButtons"
                      :key="button.label"
                      size="small"
                      variant="tonal"
                      class="rail-btn"
                      :disabled="mediaActionsDisabled"
                      @click="jump(button.delta)"
                    >
                      <span :class="{ 'active-step': Math.abs(button.delta) === timelineRequest.step }">
                        {{ button.label }}
                      </span>
                    </v-btn>
                  </div>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-row class="mt-2" dense>
          <v-col cols="12" lg="8">
            <v-card rounded="lg" elevation="1">
              <v-card-text class="pa-3">
                <div class="cut-marker-row">
                  <v-btn size="small" color="primary" :disabled="mediaActionsDisabled" @click="setCutStart">
                    Start: {{ cutStart || '--:--:--' }}
                  </v-btn>
                  <v-btn size="small" color="primary" :disabled="mediaActionsDisabled" @click="setCutEnd">
                    End: {{ cutEnd || '--:--:--' }}
                  </v-btn>
                  <v-btn size="small" color="secondary" :loading="analysisRunning" :disabled="!canRunAnalysis" @click="analyzeRecording">
                    Analyze Recording
                  </v-btn>
                  <v-btn size="small" :disabled="!markersFormValid || mediaActionsDisabled" @click="addCurrentInterval">
                    Add Interval
                  </v-btn>
                  <v-btn size="small" color="primary" :disabled="!canOpenCutDialog" @click="openCutDialog">
                    Open Cut Dialog
                  </v-btn>
                  <v-btn size="small" color="error" variant="tonal" @click="resetMarkers">
                    Reset Markers
                  </v-btn>
                  <v-btn size="small" variant="tonal" color="error" @click="resetEverything">
                    Reset All
                  </v-btn>
                </div>

                <v-alert
                  v-if="analysisError"
                  type="error"
                  variant="tonal"
                  density="compact"
                  class="mb-3"
                  :text="analysisError"
                />

                <v-card
                  v-if="analysisRunning || analysisDraft"
                  variant="tonal"
                  rounded="lg"
                  class="analysis-card mb-3"
                >
                  <v-card-text class="pa-3">
                    <div class="analysis-header">
                      <div>
                        <strong>Detection Draft</strong>
                        <span class="text-medium-emphasis">
                          {{ analysisRunning ? ` ${analysisStatus}` : ` for ${analysisDraft?.movie ?? '-'}` }}
                        </span>
                      </div>
                      <div class="text-caption text-medium-emphasis">
                        {{ analysisPolling ? 'polling' : 'ready' }}
                      </div>
                    </div>

                    <div v-if="analysisDraft" class="analysis-body">
                      <div class="analysis-actions">
                        <v-btn
                          size="small"
                          color="primary"
                          variant="tonal"
                          :disabled="!activeBoundary"
                          @click="applyCurrentPositionToBoundary"
                        >
                          Use Current Position for {{ activeBoundary ? analysisBoundaryLabel(activeBoundary.kind) : 'Marker' }}
                        </v-btn>
                        <v-btn
                          size="small"
                          color="primary"
                          :disabled="safeAnalysisIntervals.length === 0"
                          @click="applyDetectedIntervals"
                        >
                          Apply Detected Intervals
                        </v-btn>
                      </div>

                      <div v-if="analysisWarnings.length > 0" class="analysis-warnings">
                        <v-alert
                          v-for="warning in analysisWarnings"
                          :key="warning"
                          type="warning"
                          density="compact"
                          variant="text"
                          :text="warning"
                        />
                      </div>

                      <div class="analysis-grid">
                        <div>
                          <div class="text-caption text-medium-emphasis mb-2">Detected Boundaries</div>
                          <div class="analysis-boundaries">
                            <v-btn
                              v-for="boundary in safeAnalysisBoundaries"
                              :key="boundary.id"
                              size="small"
                              variant="tonal"
                              class="analysis-boundary-btn"
                              :color="activeBoundaryId === boundary.id ? 'primary' : undefined"
                              @click="focusDetectedBoundary(boundary.id)"
                            >
                              {{ analysisBoundaryLabel(boundary.kind) }}: {{ boundary.time }}
                            </v-btn>
                          </div>
                        </div>

                        <div>
                          <div class="text-caption text-medium-emphasis mb-2">Remaining Intervals</div>
                          <v-table density="compact">
                            <tbody>
                              <tr v-for="interval in safeAnalysisIntervals" :key="`${interval.start_id}-${interval.end_id}`">
                                <td>
                                  <v-btn
                                    size="x-small"
                                    variant="text"
                                    :color="activeBoundaryId === interval.start_id ? 'primary' : undefined"
                                    @click="focusDetectedBoundary(interval.start_id)"
                                  >
                                    {{ interval.t0 }}
                                  </v-btn>
                                </td>
                                <td>
                                  <v-btn
                                    size="x-small"
                                    variant="text"
                                    :color="activeBoundaryId === interval.end_id ? 'primary' : undefined"
                                    @click="focusDetectedBoundary(interval.end_id)"
                                  >
                                    {{ interval.t1 }}
                                  </v-btn>
                                </td>
                              </tr>
                              <tr v-if="safeAnalysisIntervals.length === 0">
                                <td colspan="2">No keep intervals detected.</td>
                              </tr>
                            </tbody>
                          </v-table>
                        </div>
                      </div>
                    </div>
                  </v-card-text>
                </v-card>

                <v-table density="compact">
                  <thead>
                    <tr>
                      <th>Start</th>
                      <th>End</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(interval, index) in safeCutlist" :key="`${interval.t0}-${interval.t1}`">
                      <td>{{ interval.t0 }}</td>
                      <td>{{ interval.t1 }}</td>
                      <td class="text-right">
                        <v-btn size="x-small" variant="text" color="error" @click="removeCutInterval(index)">Remove</v-btn>
                      </td>
                    </tr>
                    <tr v-if="safeCutlist.length === 0">
                      <td colspan="3">No intervals queued.</td>
                    </tr>
                  </tbody>
                </v-table>
                <div v-if="timelineRequest.step !== 1" class="text-caption text-medium-emphasis mt-2">
                  Cut dialog is only enabled at 1" step resolution.
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" lg="4">
            <v-card rounded="lg" elevation="1">
              <v-card-text class="pa-3 worker-panel">
                <div><strong>Status:</strong> {{ progress.status }}</div>
                <div><strong>Title:</strong> {{ progress.title }}</div>
                <div><strong>Cut:</strong> {{ progress.cut_progress }}%</div>
                <div><strong>Polling:</strong> {{ polling ? 'active' : 'idle' }}</div>
                <v-btn class="mt-2" size="small" color="primary" @click="refreshProgress">Refresh Progress</v-btn>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-dialog v-model="dialogOpen" max-width="720">
          <v-card rounded="lg">
            <v-card-title>Cut Dialog</v-card-title>
            <v-card-text>
              <v-alert
                v-if="submissionError"
                type="error"
                variant="tonal"
                class="mb-4"
                :text="submissionError"
              />
              <v-table density="compact">
                <tbody>
                  <tr><td>Section</td><td>{{ selection?.section ?? '-' }}</td></tr>
                  <tr><td>Movie</td><td>{{ selection?.movie ?? '-' }}</td></tr>
                  <tr><td>ETA</td><td>{{ cutInfo?.eta ?? '-' }} min</td></tr>
                  <tr><td>.ap/.sc</td><td>{{ cutInfo?.apsc ?? '-' }}</td></tr>
                  <tr><td>Existing cut</td><td>{{ cutInfo?.cutfile ?? '-' }}</td></tr>
                </tbody>
              </v-table>
              <v-table density="compact" class="mt-4">
                <tbody>
                  <tr v-for="interval in safeCutlist" :key="`dialog-${interval.t0}-${interval.t1}`">
                    <td>{{ interval.t0 }}</td>
                    <td>{{ interval.t1 }}</td>
                  </tr>
                </tbody>
              </v-table>
              <div class="d-flex ga-4 mt-4">
                <v-checkbox v-model="inplace" label="Inplace" hide-details />
              </div>
            </v-card-text>
            <v-card-actions>
              <v-btn color="primary" :loading="submitting" :disabled="mediaActionsDisabled" @click="submitCut">
                Start Cut
              </v-btn>
              <v-btn @click="dialogOpen = false">Cancel</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </v-container>
    </v-main>
  </v-app>
</template>

<style scoped>
.compact-shell {
  max-width: 1800px;
}

.selection-bar {
  position: sticky;
  top: 0;
  z-index: 1;
}

.selection-grid {
  display: flex;
  flex-wrap: nowrap;
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.selection-field {
  min-width: 0;
}

.selection-field-section {
  flex: 0 1 220px;
}

.selection-field-series {
  flex: 1 1 240px;
}

.selection-field-season {
  flex: 0 1 140px;
}

.selection-field-movie {
  flex: 2 1 360px;
}

.selection-reload {
  flex: 0 0 auto;
}

.preview-card,
.side-rail {
  height: 100%;
}

.rail-body {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.preview-layout {
  flex-wrap: nowrap;
  align-items: stretch;
}

.preview-main {
  flex: 1 1 auto;
  min-width: 0;
}

.preview-sidebar {
  flex: 0 0 142px;
  max-width: 142px;
}

.preview-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.position-field {
  max-width: 150px;
}

.movie-meta {
  display: grid;
  gap: 4px;
  font-size: 0.9rem;
}

.timeline-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
  gap: 0;
  overflow: hidden;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.timeline-item {
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0;
  display: flex;
  flex-direction: column;
  cursor: pointer;
}

.timeline-item:disabled {
  cursor: default;
  opacity: 0.6;
}

.timeline-item img {
  width: 100%;
  border-radius: 0;
  display: block;
}

.rail-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  justify-items: center;
  width: max-content;
}

.rail-top-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin-bottom: 6px;
  justify-items: center;
  width: max-content;
}

.rail-column {
  display: grid;
  gap: 4px;
}

.rail-btn {
  min-width: 60px;
  width: 60px;
  padding-inline: 4px;
  letter-spacing: 0;
}

.rail-top-btn {
  min-height: 28px;
}

.cut-marker-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.analysis-card {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.analysis-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.analysis-body {
  display: grid;
  gap: 12px;
}

.analysis-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.analysis-warnings {
  display: grid;
  gap: 4px;
}

.analysis-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(260px, 1fr);
  gap: 12px;
}

.analysis-boundaries {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.analysis-boundary-btn {
  text-transform: none;
}

.worker-panel {
  display: grid;
  gap: 6px;
}

.preview-frame {
  min-height: 520px;
}

.active-step {
  text-decoration: underline;
  text-underline-offset: 0.2em;
}

@media (max-width: 1280px) {
  .selection-grid {
    flex-wrap: wrap;
  }

  .selection-reload {
    order: 99;
  }

  .preview-frame {
    min-height: 360px;
  }

  .analysis-grid {
    grid-template-columns: 1fr;
  }
}
</style>
