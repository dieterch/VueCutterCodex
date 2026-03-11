<script setup lang="ts">
const { selection, movieInfo, loading, refreshSelection, selectSection, selectSeries, selectSeason, selectMovie } = useSelection()
const { frameUrl, progress, loadFrame, refreshProgress } = usePlayback()

const position = ref('00:00:00')

onMounted(async () => {
  await refreshSelection()
  if (selection.value?.movie) {
    await loadFrame(selection.value.movie, position.value)
  }
  await refreshProgress()
})

watch(
  () => selection.value?.movie,
  async (movie) => {
    if (!movie) {
      return
    }
    position.value = '00:00:00'
    await loadFrame(movie, position.value)
  },
)

async function refreshFrame() {
  if (!selection.value?.movie) {
    return
  }
  await loadFrame(selection.value.movie, position.value)
}
</script>

<template>
  <v-app>
    <v-main>
      <v-container class="py-8">
        <v-row class="mb-6" align="stretch">
          <v-col cols="12" md="8">
            <v-sheet elevation="2" rounded="xl" class="pa-6">
              <div class="text-overline mb-2">VueCutter Next</div>
              <h1 class="text-h4 font-weight-bold mb-3">Nuxt 4 migration workspace</h1>
              <p class="text-body-1 mb-0">
                This frontend talks to the new `/api/...` contract while the existing Python cutting engine stays in place.
              </p>
            </v-sheet>
          </v-col>
          <v-col cols="12" md="4">
            <v-sheet elevation="2" rounded="xl" class="pa-6 fill-height">
              <div class="text-overline mb-2">Worker Status</div>
              <div class="text-h6 mb-2">{{ progress.status }}</div>
              <div class="text-body-2">Title: {{ progress.title }}</div>
              <div class="text-body-2">Cut: {{ progress.cut_progress }}%</div>
              <div class="text-body-2">APSC: {{ progress.apsc_progress }}%</div>
              <v-btn class="mt-4" color="primary" variant="flat" @click="refreshProgress">Refresh Progress</v-btn>
            </v-sheet>
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="4">
            <v-sheet elevation="2" rounded="xl" class="pa-4">
              <div class="d-flex align-center justify-space-between mb-4">
                <div class="text-h6">Selection</div>
                <v-btn size="small" variant="text" @click="refreshSelection">Reload</v-btn>
              </div>

              <v-select
                :items="selection?.sections ?? []"
                :model-value="selection?.section"
                label="Section"
                :loading="loading"
                @update:model-value="selectSection"
              />

              <v-select
                v-if="selection?.section_type === 'show'"
                :items="selection?.series ?? []"
                :model-value="selection?.serie"
                label="Series"
                @update:model-value="selectSeries"
              />

              <v-select
                v-if="selection?.section_type === 'show'"
                :items="selection?.seasons ?? []"
                :model-value="selection?.season"
                label="Season"
                @update:model-value="selectSeason"
              />

              <v-select
                :items="selection?.movies ?? []"
                :model-value="selection?.movie"
                label="Movie"
                @update:model-value="selectMovie"
              />
            </v-sheet>
          </v-col>

          <v-col cols="12" md="4">
            <v-sheet elevation="2" rounded="xl" class="pa-4">
              <div class="text-h6 mb-4">Playback Preview</div>
              <v-text-field
                v-model="position"
                label="Position (HH:MM:SS)"
                hide-details="auto"
              />
              <v-btn class="mt-3" color="primary" @click="refreshFrame">Load Frame</v-btn>

              <v-img
                v-if="frameUrl"
                :src="frameUrl"
                cover
                class="mt-4 rounded-lg"
                aspect-ratio="16/9"
              />
            </v-sheet>
          </v-col>

          <v-col cols="12" md="4">
            <v-sheet elevation="2" rounded="xl" class="pa-4">
              <div class="text-h6 mb-4">Movie Info</div>
              <div class="text-body-2 mb-2"><strong>Title:</strong> {{ movieInfo?.title ?? '-' }}</div>
              <div class="text-body-2 mb-2"><strong>Year:</strong> {{ movieInfo?.year ?? '-' }}</div>
              <div class="text-body-2 mb-2"><strong>Duration:</strong> {{ movieInfo?.duration ?? '-' }} min</div>
              <div class="text-body-2"><strong>Summary:</strong> {{ movieInfo?.summary ?? '-' }}</div>
            </v-sheet>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>
