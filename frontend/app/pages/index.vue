<script setup lang="ts">
const { posToStr, strToPos, posValid } = useTimecode()
const { selection, movieInfo, loading, refreshSelection, selectSection, selectSeries, selectSeason, selectMovie } = useSelection()
const { positionSeconds, frameUrl, frameLoading, frameError, mediaAvailable, loadFrame, clearFrameState, refreshProgress, progress } = usePlayback()

const durationSeconds = computed(() => Math.trunc((movieInfo.value?.duration_ms ?? 0) / 1000))
const positionString = computed({
  get: () => posToStr(positionSeconds.value),
  set: (value: string) => {
    positionSeconds.value = posValid(strToPos(value), durationSeconds.value)
  },
})

async function refreshFrame() {
  if (!selection.value?.movie) {
    clearFrameState()
    return
  }
  positionSeconds.value = posValid(positionSeconds.value, durationSeconds.value)
  await loadFrame(selection.value.movie, posToStr(positionSeconds.value)).catch(() => {})
}

async function changeSection(value: string) {
  await selectSection(value)
  positionSeconds.value = 0
  clearFrameState()
}

async function changeSeries(value: string) {
  await selectSeries(value)
  positionSeconds.value = 0
  clearFrameState()
}

async function changeSeason(value: string) {
  await selectSeason(value)
  positionSeconds.value = 0
  clearFrameState()
}

async function changeMovie(value: string) {
  await selectMovie(value)
  positionSeconds.value = 0
  clearFrameState()
}

onMounted(async () => {
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
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>
