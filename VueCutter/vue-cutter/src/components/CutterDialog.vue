<script setup>
import { ref, computed } from 'vue'
import axios from 'axios';
import {
    host, protocol,
    inplace, useffmpeg, lmovie, movie, section,
    t0, t1, lmovie_cut_info,
    cutterdialog, cutterdialog_enable_cut, 
    reset_cutlist, cutlist, cutmsg, progress_status
} from '@/app';

async function do_cut() {
    const endpoint = `${protocol.value}//${host.value}/cut2`
    try {
        const response = await axios.post(endpoint,
        {   
            "section": section.value, 
            "movie_name": lmovie.value,
            "cutlist": cutlist.value,
            "inplace": inplace.value,
            "useffmpeg": useffmpeg.value,
            "etaest": lmovie_cut_info.value.eta
        },
        { headers: { 'Content-type': 'application/json',}});
        console.log(response.data)
        progress()
        cutterdialog.value = false
    } catch (e) {
        console.log(`${endpoint} \n` + String(e));
        alert(`${endpoint} \n` + String(e));
    }
}

function progress() {
    const endpoint = `${protocol.value}//${host.value}/progress`
    let timer_id = setInterval( async () => {
        try {
            const response = await axios.get(endpoint, { headers: { 'Content-type': 'application/json', }});
            progress_status.value = response.data
            console.log(progress_status.value)
            if (progress_status.value.status == "idle") {
                console.log("done")
                clearInterval(timer_id)
            }
        } catch (e) {
            console.log(`${endpoint} \n` + String(e));
            alert(`${endpoint} \n` + String(e));
        }
    }, 3000)
    console.log("progress", timer_id)
}
</script>

<template>
    <v-dialog
    v-model="cutterdialog"
    persistent="true"
    width="auto"
    >
        <v-card
            title="Cut Dialog"
            color="dialogbackground"
            :subtitle="movie"
        >
            <v-card-text>
                <v-table 
                    density="compact"
                    class="bg-toolsbackground"      
                    >
                    <thead>
                        <tr>
                            <th class="text-left">Name</th>
                            <th class="text-left">Wert</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr
                            v-for = "(val, key) in cutmsg"
                            :key = "key"
                            >
                            <td>{{ key }}</td>
                            <td>{{ val }}</td>
                        </tr>
                        <tr v-if = "!useffmpeg">
                            <td>.ap .sc Files ?</td>
                            <td>{{ lmovie_cut_info.apsc }}</td>
                        </tr>
                        <tr v-if = "!useffmpeg">
                            <td>_cut File ?</td>
                            <td>{{ lmovie_cut_info.cutfile }}</td>
                        </tr>
                </tbody>
            </v-table>
        </v-card-text>
        <v-divider></v-divider>
        <v-card-actions>
            <v-sheet 
                class="d-flex flex-1-1-100 flex-column"
                >
                    <v-sheet
                        class="d-flex justify-end bg-toolsbackground"
                        height="35">
                        <v-checkbox
                            density="dense"
                            class="ma-2"
                            v-model="useffmpeg"
                            label="FFMPEG"
                        ></v-checkbox>
                        <v-checkbox
                            density="dense"
                            class="ma-2"
                            v-model="inplace"
                            label="Inplace"
                        ></v-checkbox>
                    </v-sheet>
                    <v-sheet 
                        class="d-flex justify-end align-center bg-toolsbackground"
                        >
                        <v-btn
                            class="flex-1-1 ma-2"
                            color="danger-button"
                            variant="flat"
                            prepend-icon="mdi-content-cut"
                            @click="do_cut"
                            :disabled="!cutterdialog_enable_cut"
                            width="135"
                            >
                            Cut
                        </v-btn>

                        <v-btn
                            class="flex-1-1 ma-2"
                            color="primary-button"
                            variant="flat"
                            prepend-icon="mdi-cancel"
                            @click="cutterdialog = false"
                            width="135"
                            >
                            Cancel
                        </v-btn>

                        <v-btn
                            class="flex-1-1 ma-2"
                            color="tertiary-button"
                            variant="flat"
                            prepend-icon="mdi-restart"
                            @click="reset_cutlist"
                            width="135"
                            >
                            Reset
                        </v-btn>
                    </v-sheet>
                </v-sheet>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>