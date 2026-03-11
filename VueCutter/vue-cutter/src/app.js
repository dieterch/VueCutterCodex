// ************************************************************************************************
//
// Quart VueCutter (c)2024 Dieter Chvatal frontend
//
// ************************************************************************************************

import { ref, computed } from 'vue'
import axios from 'axios';

// Global Functions & Variables
export const host = ref(window.location.host)
export const protocol = ref(window.location.protocol)

// ************************************************************************************************
// general Tools
// ************************************************************************************************

// Leading Zero's
export const zeroPad = (num, places) => String(num).padStart(places, '0')

// export function setCookie(id, value) {
//     document.cookie = id + '=' + value;
// }

// export function getCookie(id) {
//     let value = document.cookie.match('(^|;)?' + id + '=([^;]*)(;|$)');
//     return value ? unescape(value[2]) : null;
//  }

// export function deleteCookie(id) {
//     document.cookie = id + '=;';

//  }

export const setCookie = (name, value, days = 30, path = '/') => {
    const expires = new Date(Date.now() + days * 864e5).toUTCString()
    document.cookie = name + '=' + encodeURIComponent(value) + '; expires=' + expires + '; path=' + path
}

export const getCookie = (name) => {
    return document.cookie.split('; ').reduce((r, v) => {
        const parts = v.split('=')
        return parts[0] === name ? decodeURIComponent(parts[1]) : r
    }, '')
}

export const deleteCookie = (name, path) => {
    setCookie(name, '', -1, path)
}


export function get_themecookie() { return getCookie('theme') || 'LightTheme' }
export function set_themecookie(mytheme) { return setCookie('theme', mytheme) }

// ************************************************************************************************
// position functions
// ************************************************************************************************
export const lpos = ref(0)

// computed variabel pos ... loads frame @ movie position
export const pos = computed({
    get: () => {
            //console.log("in pos getter ", lpos.value)
            const spos = pos2str(lpos.value)
            get_frame(spos)
            return spos
        },
    set: (newValue) => {
            //console.log("in pos setter ", newValue)
            lpos.value = str2pos(newValue)
        }
})

// seconds to 'hh:mm:ss' string
export const pos2str = (pos) => {
    pos = (pos >= 0) ? pos : 0
    return `${zeroPad(Math.trunc(pos / 3600),2)}:${zeroPad(Math.trunc((pos % 3600) / 60),2)}:${zeroPad(Math.trunc(pos % 60,2),2)}`
}

// 'hh:mm:ss' string to seconds
export const str2pos = (st) => {
    let erg = parseInt(String(st).slice(0,2))*3600 + parseInt(String(st).slice(3,5))*60 + parseInt(String(st).slice(-2))
    return erg
}

// position from end, input seconds
export const pos_from_end = (dsec) => {
    let val = Math.trunc(lmovie_info.value.duration_ms / 1000 - dsec)
    val = (val < 0) ? 0 : val
    return val
}

// check if position is valid
export const posvalid = (val) => {
    // if val is outside of movie duration, return -998
    val = (val >=0 ) ? val : -998
    val = (val <= pos_from_end(0)) ? val : -998
    return val
}

// ************************************************************************************************
// timeline functions
// ************************************************************************************************
export const toggle_timeline = ref(false)
export const ltimeline = ref({
    basename: 'frame.gif',
    larray: [],
    pos: 0,
    l: -4,
    r: 4,
    step: 1,
    size: '160'
})

export function pos2fname(pos) {
    if (pos === -999) {
        return '/static/spinner_160x90.gif'
    } else if (pos === -998) {
        return '/static/background.png'
    } else  {
        return  '/static/' + ltimeline.value.basename.slice(0,-4) + '_' + pos2str(pos) + ltimeline.value.basename.slice(-4) + '?' + String(Math.random())
    }
}

export const set_timeline_step = (step) => {
    ltimeline.value.step = step
    lpos.value = Math.trunc(lpos.value / step) * step
}

export const timeline = async (mypos) => {
    const endpoint = `${protocol.value}//${host.value}/timeline`
    if (toggle_timeline.value) {
        ltimeline.value.larray.length = 0
        for (let p=ltimeline.value.l;p<=ltimeline.value.r;p+=1) {
            ltimeline.value.larray.push(-999)
        }
        // const sarray = []
        try {
            const response = await axios.post(endpoint,
                {
                    "basename": ltimeline.value.basename,
                    "pos": mypos,
                    "l": ltimeline.value.l,
                    "r": ltimeline.value.r,
                    "step": ltimeline.value.step,
                    "size": ltimeline.value.size
                },
                { headers: {
                    'Content-type': 'application/json',
                }
            })
            //console.log('promise timeline resolved', response.data)
            ltimeline.value.larray.length = 0
            for (let p=ltimeline.value.l;p <=ltimeline.value.r;p+=1) {
                let val = mypos + p*Math.abs(ltimeline.value.step)
                val = posvalid(val)
                ltimeline.value.larray.push(val)
                // sarray.push(pos2fname(val))
            }
            // console.log(ltimeline.value.larray)
            // console.log(sarray)
        } catch (e) {
            console.log(`${endpoint} \n` + String(e));
            alert(`${endpoint} \n` + String(e));
        }

    }
}

// ************************************************************************************************
// cutting functions
// ************************************************************************************************

export const t0 = ref("00:00:00")
export const t0_valid = ref(false)
export const t1 = ref("01:00:00")
export const t1_valid = ref(false)
export const inplace = ref(true)
export const cutterdialog = ref(false)
export const cutterdialog_enable_cut = ref(false)
export const cutlist = ref([])
export const lmovie_cut_info = ref({})
export const cutmsg = ref('')
export const useffmpeg = ref(true)

// btn click function for all cutting/position related buttons
export const hpos = (b) => {
    // jump to the left or right relative to the current position
    if (b.type == "rel") {
        set_timeline_step(Math.abs(b.val))
        if (!toggle_timeline.value) {
            // console.log('in hpos type rel, lpos before lpos+=b. :',lpos.value)
            if (posvalid(lpos.value + b.val) >= 0) { lpos.value += b.val }
              else if (b.val > 0) { lpos.value = pos_from_end(0) }
                else if (b.val < 0) { lpos.value = 0 }

            //console.log('before validation lpos:',lpos.value)
            lpos.value = posvalid(lpos.value)
            //console.log('after validation  lpos:',lpos.value)
        }
        // console.log('in hpvalos type rel', b, lpos.value)
        timeline(lpos.value)
    // jump to the left or right to an absolute position
    } else if (b.type == "abs") {
        //console.log('in hpos type abs', b)
        lpos.value = b.val
        timeline(lpos.value)
    // Store Start of the cutting window in t0
    } else if (b.type == "t0")  {
        t0.value = pos.value
        t0_valid.value = true
        toggle_timeline.value = false
    // Store End of the cutting window in t1
    }else if (b.type == "t1")  {
        t1.value = pos.value
        t1_valid.value = true
        toggle_timeline.value = false
    } else {
        alert("unknown type in hpos")
    }

}

// reset the cutting interval buttons
export function reset_t0_t1() {
    t0.value = "00:00:00"
    t0_valid.value = false
    t1.value = "01:00:00"
    t1_valid.value = false
}

// Start the cutlist all over again
export function reset_cutlist() {
    reset_t0_t1();
    cutlist.value = []
    cutmsg.value = ''
    cutterdialog.value = false
}

// rec to store received progress status
export const progress_status = ref({
    "apsc_size": 0,
    "progress": 0,
    "started": 0,
    "status": "idle",
    "title": "-"
  })

// ************************************************************************************************
// plex related functions
// ************************************************************************************************

export const sections = ref([])
export const section = ref('')
export const section_type = ref('')
export const movies = ref([])
export const lmovie = ref('')
export const seasons = ref([])
export const season = ref('')
export const series = ref([])
export const serie = ref('')
export const lmovie_info = ref({})
export const frame_name = ref('');

// load information about the selected movie/video
export async function load_movie_info() {
    const endpoint = `${protocol.value}//${host.value}/movie_info`
    // console.log(`in load movie info, Movie ${lmovie.value}`, endpoint)
    try {
        const response = await axios.post(endpoint,
            { "section": section.value, "movie": lmovie.value },
            { headers: { 'Content-type': 'application/json', }});
        lmovie_info.value = response.data.movie_info
    } catch (e) {
        console.log(`${endpoint} \n` + String(e));
        alert(`${endpoint} \n` + String(e));
    }
}

// computed variabel movie ... a proxy for lmovie
export const movie = computed({
    get: () => {
        lpos.value = 0
        load_movie_info()
        return lmovie.value
    },
    set(val) {
        lmovie.value = val
    }
})

// fetch the frame for the selected movie position
export async function get_frame(pos) {
    const endpoint = `${protocol.value}//${host.value}/frame`
    // console.log(`in load frame, Position ${pos}`)
    try {
        const response = await axios.post(endpoint,
            { "pos_time": pos, "movie_name": movie.value },
            { headers: { 'Content-type': 'application/json', }});
        frame_name.value = response.data.frame + '?' + String(Math.random());
        // toggle_timeline.value = false
    } catch (e) {
        console.log(`${endpoint} \n` + String(e));
        alert(`${endpoint} \n` + String(e));
    }
}
