<script setup lang="ts">
const { posToStr, strToPos, posValid } = useTimecode()
const { selection, movieInfo, loading, refreshSelection, selectSection, selectSeries, selectSeason, selectMovie } = useSelection()
const { positionSeconds, frameUrl, frameLoading, frameError, mediaAvailable, loadFrame, clearFrameState, refreshProgress, progress } = usePlayback()
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
  useffmpeg,
  cutInfo,
  submitting,
  addInterval,
  openDialog,
  submit,
  resetMarkers,
  resetAll,
} = useCutting()

const durationSeconds = computed(() => Math.trunc((movieInfo.value?.duration_ms ?? 0) / 1000))
const safeTimelineItems = computed(() => timelineItems.value.filter((item) => item && item.label))
const safeCutlist = computed(() => cutlist.value.filter((interval) => interval && interval.t0 && interval.t1))
const mediaActionsDisabled = computed(() => frameLoading.value || !mediaAvailable.value)
const positionString = computed({
  get: () => posToStr(positionSeconds.value),
  set: (value: string) => {
    positionSeconds.value = posValid(strToPos(value), durationSeconds.value)
  },
})

const jumpButtons = [
  { label: `-10'`, delta: -600 },
  { label: `-1'`, delta: -60 },
  { label: `-30"`, delta: -30 },
  { label: `-10"`, delta: -10 },
  { label: `+10"`, delta: 10 },
  { label: `+30"`, delta: 30 },
  { label: `+1'`, delta: 60 },
  { label: `+10'`, delta: 600 },
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
  if (!mediaAvailable.value) {
    return
  }
  await refreshFrame()
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
  if (cutStart.value && cutEnd.value) {
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
  await submit(selection.value.section, selection.value.movie)
}

function removeCutInterval(index: number) {
  const next = [...cutlist.value]
  next.splice(index, 1)
  cutlist.value = next
}

async function changeSection(value: string) {
  await selectSection(value)
  positionSeconds.value = 0
  clearFrameState()
  timelineItems.value = []
}

async function changeSeries(value: string) {
  await selectSeries(value)
  positionSeconds.value = 0
  clearFrameState()
  timelineItems.value = []
}

async function changeSeason(value: string) {
  await selectSeason(value)
  positionSeconds.value = 0
  clearFrameState()
  timelineItems.value = []
}

async function changeMovie(value: string) {
  await selectMovie(value)
  positionSeconds.value = 0
  clearFrameState()
  timelineItems.value = []
}

onMounted(async () => {
  resetAll()
  timelineEnabled.value = false
  timelineItems.value = []
  clearFrameState()
  await refreshSelection()
  await refreshProgress()
})
</script>

<template>
  <v-app>
    <v-main>
      <v-container class="py-8">
        <v-row>
          <v-col cols="12">
            <v-alert
              type="info"
              variant="tonal"
              text="This screen is intentionally minimal until the NAS/media mount is configured. Plex selection and metadata should work even when the media source is offline."
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="4">
            <v-card rounded="xl" elevation="2">
              <v-card-title>Selection</v-card-title>
              <v-card-text>
                <v-select
                  :items="selection?.sections ?? []"
                  :model-value="selection?.section ?? null"
                  :loading="loading"
                  label="Section"
                  @update:model-value="changeSection"
                />

                <v-select
                  v-if="selection?.section_type === 'show'"
                  :items="selection?.series ?? []"
                  :model-value="selection?.serie ?? null"
                  label="Series"
                  @update:model-value="changeSeries"
                />

                <v-select
                  v-if="selection?.section_type === 'show'"
                  :items="selection?.seasons ?? []"
                  :model-value="selection?.season ?? null"
                  label="Season"
                  @update:model-value="changeSeason"
                />

                <v-select
                  :items="selection?.movies ?? []"
                  :model-value="selection?.movie ?? null"
                  label="Movie"
                  @update:model-value="changeMovie"
                />
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="4">
            <v-card rounded="xl" elevation="2">
              <v-card-title>Movie Info</v-card-title>
              <v-card-text>
                <div><strong>Title:</strong> {{ movieInfo?.title ?? '-' }}</div>
                <div><strong>Year:</strong> {{ movieInfo?.year ?? '-' }}</div>
                <div><strong>Duration:</strong> {{ movieInfo?.duration ?? '-' }} min</div>
                <div class="mt-3 text-body-2">{{ movieInfo?.summary ?? '-' }}</div>
              </v-card-text>
            </v-card>

            <v-card rounded="xl" elevation="2" class="mt-4">
              <v-card-title>Worker Status</v-card-title>
              <v-card-text>
                <div><strong>Status:</strong> {{ progress.status }}</div>
                <div><strong>Title:</strong> {{ progress.title }}</div>
                <div><strong>Cut:</strong> {{ progress.cut_progress }}%</div>
                <div><strong>APSC:</strong> {{ progress.apsc_progress }}%</div>
                <v-btn class="mt-4" color="primary" @click="refreshProgress">Refresh Progress</v-btn>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="4">
            <v-card rounded="xl" elevation="2">
              <v-card-title>Preview</v-card-title>
              <v-card-text>
                <v-alert
                  v-if="frameError"
                  type="warning"
                  variant="tonal"
                  class="mb-4"
                  title="Media source unavailable"
                  :text="frameError"
                />

                <v-alert
                  v-else-if="!mediaAvailable"
                  type="info"
                  variant="tonal"
                  class="mb-4"
                  text="The NAS or host media mount is unavailable. Frame preview is disabled until the media path exists."
                />

                <v-img
                  v-if="frameUrl"
                  :src="frameUrl"
                  aspect-ratio="16/9"
                  cover
                  class="rounded-lg border"
                />

                <v-skeleton-loader
                  v-else-if="frameLoading"
                  type="image"
                  class="rounded-lg"
                />

                <v-sheet
                  v-else
                  class="d-flex align-center justify-center rounded-lg border pa-8 text-medium-emphasis"
                  min-height="260"
                >
                  No preview loaded.
                </v-sheet>

                <div class="d-flex align-center mt-4">
                  <v-text-field
                    v-model="positionString"
                    label="Position"
                    hide-details
                    density="comfortable"
                  />
                  <v-btn class="ml-2" color="primary" :loading="frameLoading" @click="refreshFrame">
                    Load Frame
                  </v-btn>
                </div>

                <div class="d-flex flex-wrap ga-2 mt-4">
                  <v-btn
                    v-for="button in jumpButtons"
                    :key="button.label"
                    size="small"
                    variant="outlined"
                    :disabled="mediaActionsDisabled"
                    @click="jump(button.delta)"
                  >
                    {{ button.label }}
                  </v-btn>
                </div>

                <div class="d-flex flex-wrap ga-2 mt-4">
                  <v-btn size="small" variant="tonal" :disabled="mediaActionsDisabled" @click="jumpTo(0)">Start</v-btn>
                  <v-btn size="small" variant="tonal" :disabled="mediaActionsDisabled" @click="jumpTo(durationSeconds)">End</v-btn>
                  <v-btn size="small" :disabled="!mediaAvailable && !timelineEnabled" @click="toggleTimeline">Timeline</v-btn>
                  <v-btn size="small" :disabled="!timelineEnabled || mediaActionsDisabled" @click="pageTimeline(-1)">Page Left</v-btn>
                  <v-btn size="small" :disabled="!timelineEnabled || mediaActionsDisabled" @click="pageTimeline(1)">Page Right</v-btn>
                  <v-btn size="small" :disabled="!timelineEnabled || mediaActionsDisabled" @click="refreshTimeline">Refresh Timeline</v-btn>
                </div>

                <div v-if="timelineEnabled" class="timeline-strip mt-4">
                  <button
                    v-for="item in safeTimelineItems"
                    :key="`${item.label}-${item.pos}`"
                    class="timeline-item"
                    type="button"
                    :disabled="mediaActionsDisabled"
                    @click="jumpTo(item.pos)"
                  >
                    <img :src="item.src" :alt="item.label" />
                    <span>{{ item.label }}</span>
                  </button>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-row class="mt-2">
          <v-col cols="12" md="6">
            <v-card rounded="xl" elevation="2">
              <v-card-title>Cut Markers</v-card-title>
              <v-card-text>
                <div class="d-flex flex-wrap ga-2">
                  <v-btn color="primary" :disabled="mediaActionsDisabled" @click="setCutStart">
                    Start: {{ cutStart || '--:--:--' }}
                  </v-btn>
                  <v-btn color="primary" :disabled="mediaActionsDisabled" @click="setCutEnd">
                    End: {{ cutEnd || '--:--:--' }}
                  </v-btn>
                  <v-btn :disabled="!(cutStart && cutEnd) || mediaActionsDisabled" @click="addCurrentInterval">
                    Add Interval
                  </v-btn>
                  <v-btn color="error" variant="tonal" @click="resetMarkers">
                    Reset Markers
                  </v-btn>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="6">
            <v-card rounded="xl" elevation="2">
              <v-card-title>Cutlist</v-card-title>
              <v-card-text>
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
                <div class="d-flex flex-wrap ga-2 mt-4">
                  <v-btn color="primary" :disabled="safeCutlist.length === 0 || mediaActionsDisabled" @click="openCutDialog">
                    Review Cut
                  </v-btn>
                  <v-btn variant="tonal" color="error" @click="resetAll">
                    Reset All
                  </v-btn>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-dialog v-model="dialogOpen" max-width="720">
          <v-card rounded="xl">
            <v-card-title>Cut Dialog</v-card-title>
            <v-card-text>
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
                <v-checkbox v-model="useffmpeg" label="FFMPEG" hide-details />
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
.timeline-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
  gap: 8px;
}

.timeline-item {
  border: 0;
  border-radius: 12px;
  background: #f4f6fa;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
}

.timeline-item:disabled {
  cursor: default;
  opacity: 0.6;
}

.timeline-item img {
  width: 100%;
  border-radius: 8px;
}

.timeline-item span {
  font-size: 12px;
  font-weight: 600;
}
</style>
