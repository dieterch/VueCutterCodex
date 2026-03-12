<script setup>
import { progress_status } from '@/app';
</script>

<template>
    <v-footer app color="toolsbackground" class="mt-2">
        <v-row v-if="progress_status.status == 'started'" justify="center" no-gutters>
            <v-col class="text-left mt-0 mb-1" cols="12">
                <strong>{{ progress_status.title }}</strong> 
            </v-col>
        </v-row>
        <v-row v-if="progress_status.status == 'started'" no-gutters>
            <v-col cols="5">
                <small size="x-small">FFMPEG:</small>
                <v-progress-linear :model-value="progress_status.cut_progress" color="primary" height="12" class="mb-2">
                    <small>{{ progress_status.cut_progress }}%</small></v-progress-linear>
            </v-col>
        </v-row>
    </v-footer>
</template>
