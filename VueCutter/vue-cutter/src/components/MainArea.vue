<script setup>
import { ref } from 'vue';
import { useLayout } from 'vuetify';

import {hpos,
        frame_name,
        pos2fname,
        toggle_timeline,
        ltimeline, progress_status
} from '@/app';

</script>

<template>
    <v-main color="black">    
        <v-container
            class="pa-0"
            fluid
            elevation="0"
        >
            <div class="dbox dbox-main-detail" v-if="toggle_timeline">
                <v-img
                    v-for="ival in ltimeline.larray"
                    :key="ival"
                    @click="hpos({val: ival, type:'abs'})"
                    :src="pos2fname(ival)" 
                    class="mx-auto shift_down" 
                    >
                </v-img>  
            </div>
            <div 
                class="dbox dbox-main"
            >
                <v-img 
                    class="mx-0 pa-1 shift_down"
                    :src="frame_name" 
                    alt="... loading ..."
                    >
                </v-img>
            </div>
        </v-container>
    </v-main>
</template>

<style scoped>
.v-progress-circular {
  margin: 1rem;
}

.shift_down {
    /* top: calc(2*48px); */
    top: 1px;
}

.dbox {
    display: flex;
    justify-content: center;
    align-items: center;
}

.dbox-main-detail {
    flex-direction: row;
    justify-content: stretch;
    /* background: var(--bg-pic); */
    grid-column: 1;
    grid-row: 1;
}

.dbox-main {
    /* background: var(--bg-pic); */
    grid-column: 1;
    grid-row: 2;
}
.frame {
    min-width: 50%;
    max-width: 100%;
    height: auto;
}
</style>