<script setup>
import { computed } from 'vue'
import axios from 'axios';
import CutterDialog from './CutterDialog.vue';

import {
    protocol, host,
    lpos, posvalid, pos_from_end,
    toggle_timeline, timeline, 
    t0, t0_valid, 
    t1, t1_valid,
    inplace,
    ltimeline,
    lmovie, section,
    cutlist, cutterdialog, cutterdialog_enable_cut, cutmsg, lmovie_cut_info,
    hpos } from '@/app';

const cut_ok = computed(() => {
        // console.log(t0_valid.value, t1_valid.value, ltimeline.value.step)
        return t0_valid.value & t1_valid.value & ( ltimeline.value.step == 1 )
    })

const inplaceIcon = computed(() => {
    let ret = (inplace.value) ? "mdi-toggle-switch-variant" :  "mdi-toggle-switch-variant-off"
    // console.log(ret)
    return ret
})

// function toggle_inplace() {
//         inplace.value = !inplace.value
//     }

function add_to_cutlist(interval) {
    // check if interval is already in cutlist, if not, add it
    if (cutlist.value.some((e) => e.t0 == interval.t0 && e.t1 == interval.t1)) {
        console.log("Interval already in cutlist")
    } else {
        cutlist.value.push(interval)
    }
    console.log("add_to_cutlist", cutlist.value)
}

function validate_cutlist() {
    // check if t1 > t0 for all intervals in cutlist
    const isValidCutlist = cutlist.value.every((interval) => interval.t1 > interval.t0);
    // sort cutlist intervals by t0 in ascending order
    cutlist.value.sort((a, b) => a.t0.localeCompare(b.t0));
    // combine intervals that overlap
    cutlist.value = cutlist.value.reduce((acc, interval) => {
        if (acc.length === 0) return [interval];
        const lastInterval = acc[acc.length - 1];
        if (interval.t0 <= lastInterval.t1) {
            lastInterval.t1 = interval.t1;
        } else {
            acc.push(interval);
        }
        return acc;
    }, []);
    // check if intervals still overlap
    const isNotoverlappingCutlist = cutlist.value.every((interval, index, array) => {
        if (index === 0) return true;
        return interval.t0 > array[index - 1].t1;
    });
    //if all checks pass, return true
    return isValidCutlist && isNotoverlappingCutlist;
}

async function cut_info() {
    const endpoint = `${protocol.value}//${host.value}/movie_cut_info`
    try {
        const response = await axios.get(endpoint, { headers: { 'Content-type': 'application/json', }});
        lmovie_cut_info.value = response.data;
        //console.log("in movie_cut_info", this.lmovie_cut_info)
        // store t0 and t1 in cutlist if not already there
        add_to_cutlist({t0: t0.value, t1: t1.value})
        cutterdialog_enable_cut.value = validate_cutlist()
        cutmsg.value = {
            section: section.value,
            movie: lmovie.value,
            cutlist: cutlist.value,
            //Inplace: inplace.value,
            //".ap .sc Files ?": lmovie_cut_info.value.apsc,
            //"_cut File ?": lmovie_cut_info.value.cutfile
        }
        console.log(cutmsg.value)
        cutterdialog.value = true
    } catch (e) {
        console.log(`${endpoint} \n` + String(e));
        alert(`${endpoint} \n` + String(e));
    }
}

function extend_cutlist() {
    // store t0 and t1 in cutlist if not already there
    add_to_cutlist({t0: t0.value, t1: t1.value})
    // set t0_valid, t1_valid to false
    t0_valid.value = false
    t1_valid.value = false
    // alert("extend_cutlist", cutlist.value)
    console.log("extend_cutlist", cutlist.value)
}

function page_minus_timeline() {
    if (lpos.value + ((ltimeline.value.l - ltimeline.value.r) * ltimeline.value.step)> 0) {
        lpos.value += (ltimeline.value.l - ltimeline.value.r) * ltimeline.value.step
        lpos.value = posvalid(lpos.value)                
    } else lpos.value = 0
    timeline(lpos.value)
}

function page_plus_timeline() {
    //console.log('in ">":',this.lpos, this.pos_from_end(0), this.lpos + (this.ltimeline.r - this.ltimeline.l) * this.ltimeline.step)
    if (lpos.value + ((ltimeline.value.r - ltimeline.value.l) * ltimeline.value.step ) < pos_from_end(0)) {
        lpos.value += (ltimeline.value.r - ltimeline.value.l) * ltimeline.value.step
        //console.log('in ">, if ... nach +=":',this.lpos)
        lpos.value = posvalid(lpos.value)
        //console.log('in ">, if ... nach this.posvalid":',this.lpos)
    } else lpos.value = pos_from_end(0)
    timeline(lpos.value)
}

function toggle_and_timeline(mypos) {
    let tlt = toggle_timeline.value
    toggle_timeline.value = !tlt
    lpos.value = posvalid(lpos.value)
    // console.log('in "toggle_and_timeline":',mypos)
    timeline(mypos)
}


</script>

<template>
    <CutterDialog />
    <v-app-bar
    name="cutter-bar" 
    color="toolsbackground"
    density="compact"
    :elevation="0"
    >
        <template v-slot:prepend>
                    <v-btn
                        v-if="t0_valid"
                        variant="flat"
                        class="mr-2"
                        color="primary-button"
                        size="default"
                        prepend-icon="mdi-align-horizontal-right"
                        block="true"
                        @click="hpos({type:'t0'})"
                    >
                    {{ t0 }}
                    </v-btn>
                    <v-btn
                        v-else
                        variant="flat"
                        class="mr-2"
                        color="primary-button"
                        size="default"
                        prepend-icon="mdi-align-horizontal-right"
                        block="true"
                        @click="hpos({type:'t0'})"
                    >
                    -- : -- : --
                    </v-btn>
                    <v-btn
                        v-if="t1_valid"
                        variant="flat"
                        color="primary-button"
                        block="true"
                        size="default"
                        append-icon="mdi-align-horizontal-left"
                        @click="hpos({type:'t1'})"
                        >
                        {{ t1 }}
                    </v-btn>
                    <v-btn
                        v-else
                        variant="flat"
                        color="primary-button"
                        block="true"
                        size="default"
                        append-icon="mdi-align-horizontal-left"
                        @click="hpos({type:'t1'})"
                        >
                        -- : -- : --
                    </v-btn>
                    <v-col>
                        <v-btn
                            v-if="t0_valid & t1_valid"
                            icon="mdi-plus" 
                            color="primary-button"
                            size="small"
                            @click="extend_cutlist"
                            >
                        </v-btn>
                    </v-col>
        </template>
        <template v-slot:append>
            <v-btn 
                icon="mdi-arrow-left-bold-box-outline"
                color="primary-button"
                size="small"
                @click="page_minus_timeline()"
            ></v-btn>
            <v-btn 
                icon="mdi-filmstrip" 
                color="primary-button"
                size="small"
                @click="toggle_and_timeline(lpos)"
            ></v-btn>
            <v-btn
                icon="mdi-arrow-right-bold-box-outline" 
                color="primary-button"
                size="small"
                @click="page_plus_timeline()"
            ></v-btn>
            <v-btn
                v-if="cut_ok"
                icon="mdi-content-cut"
                color="primary-button"
                size="small"
                @click="cut_info"
            >
            </v-btn>
            <v-btn
                v-else
                icon="mdi-content-cut"
                color="primary-button"
                size="small"
                disabled
            >
            </v-btn>
    </template>
    </v-app-bar>
</template>

<style scoped>
    .text--black {
        color: black  !important;
    }
</style>