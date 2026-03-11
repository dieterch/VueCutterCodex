<script setup>
import { computed } from 'vue'
import { 
    lmovie_info,
    pos, lpos, hpos,
    pos_from_end, pos2str,  
    ltimeline
} from '@/app';

const buttons_left = computed(() => {
    return [
        {name:"", icon:'mdi-format-horizontal-align-left', val:0, type:"abs", color:"primary-button"},
        {name:" 15'", icon:'mdi-format-horizontal-align-left', val:15*60, type:"abs", color:"primary-button"},
        {name:" 30'", icon: 'mdi-arrow-left-thin', val:-1800, type:"rel", color:"secondary-button"},
        {name:" 10'", icon: 'mdi-arrow-left-thin', val:-600, type:"rel", color:"secondary-button"},
        {name:" 5'", icon: 'mdi-arrow-left-thin', val:-5*60, type:"rel", color:"secondary-button"},
        {name:" 1'", icon: 'mdi-arrow-left-thin', val:-60, type:"rel", color:"secondary-button"},
        {name:' 30"', icon: 'mdi-arrow-left-thin', val:-30, type:"rel", color:"tertiary-button"},
        {name:' 10"', icon: 'mdi-arrow-left-thin', val:-10, type:"rel", color:"tertiary-button"},
        {name:' 5"', icon: 'mdi-arrow-left-thin', val:-5, type:"rel", color:"tertiary-button"},
        {name:' 1"', icon: 'mdi-arrow-left-thin', val:-1, type:"rel", color:"tertiary-button"},
    ]
})

const buttons_right = computed(() => {
    return [
        {name:"",icon: 'mdi-format-horizontal-align-right', val:pos_from_end(0), type:"abs", color:"primary-button"},
        {name:"15' ",icon: 'mdi-format-horizontal-align-right', val:pos_from_end(15*60), type:"abs", color:"primary-button"},
        {name:"30' ", icon: 'mdi-arrow-right-thin', val:1800, type:"rel", color:"secondary-button"},
        {name:"10' ", icon: 'mdi-arrow-right-thin', val:600, type:"rel", color:"secondary-button"},
        {name:"5' ", icon: 'mdi-arrow-right-thin', val:5*60, type:"rel", color:"secondary-button"},
        {name:"1' ", icon: 'mdi-arrow-right-thin', val:60, type:"rel", color:"secondary-button"},
        {name:'30" ', icon: 'mdi-arrow-right-thin', val:30, type:"rel", color:"tertiary-button"},                    
        {name:'10" ', icon: 'mdi-arrow-right-thin', val:10, type:"rel", color:"tertiary-button"},                    
        {name:'5" ', icon: 'mdi-arrow-right-thin', val:5, type:"rel", color:"tertiary-button"},                    
        {name:'1" ', icon: 'mdi-arrow-right-thin', val:1, type:"rel", color:"tertiary-button"},
    ]
})

</script>

<template>
    <v-navigation-drawer
        name="side-bar"
        permanent
        location="right"
        color="toolsbackground"
        :width="160"
    >
        <v-divider/>
        <div>
            <v-chip 
                prepend-icon="mdi-movie-open" 
                label
                variant="text"
                size="default"
                class="mt-2 ml-2">
                <strong>{{ pos2str(lmovie_info.duration * 60) }} &nbsp;&nbsp;&nbsp; ({{ lmovie_info.duration }}')</strong>
            </v-chip>
            <v-chip 
                prepend-icon="mdi-movie-open-edit" 
                variant="text"
                label
                size="default"
                class="mt-0 ml-2">
                <strong>{{ pos }} &nbsp;&nbsp;&nbsp; ({{ Math.trunc(lpos / 60) }}')</strong>
            </v-chip>
        </div>
        <v-divider/>
        <v-sheet class="sb_container bg-toolsbackground">

            <v-sheet class="d-flex flex-column justify-center align-center sb_box-buttons mt-2 bg-toolsbackground">
                <v-btn 
                    v-for="b in buttons_left"
                    :prepend-icon="b.icon"
                    :color="b.color"
                    class="ma-1" 
                    width="65px"
                    @click="hpos(b)">
                    <span :style="(-b.val == ltimeline.step) ? 'text-decoration: overline;' : 'text-decoration: none;'">{{ b.name }}</span>
                </v-btn>
            </v-sheet>

            <v-sheet class="d-flex flex-column justify-center align-center sb_box-buttons mt-2 bg-toolsbackground">
                <v-btn 
                    v-for="b in buttons_right"
                    :append-icon="b.icon"
                    :color="b.color"
                    class="ma-1" 
                    width="65px"
                    @click="hpos(b)">
                    <span :style="(b.val == ltimeline.step) ? 'text-decoration: overline;' : 'text-decoration: none;'">{{ b.name }}</span>
                </v-btn>
            </v-sheet>
            
        </v-sheet>
    </v-navigation-drawer>
  </template>

<style scoped>
button {
  font-weight: bold;
}

/* sidebar grid */
.sb_container {
    display: grid;
    grid-template-rows: auto auto auto 100fr;
    grid-template-columns: 50fr 50fr;   
}

.sb_box-buttons {
    grid-row: 4;
}

/* sidebar grid */
</style>