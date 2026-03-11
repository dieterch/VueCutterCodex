// cutlist is ok
const cutlist1 = {value: [
    { "t0": "00:00:00", "t1": "00:20:00" }, 
    { "t0": "00:30:00", "t1": "00:40:00" }, 
    { "t0": "00:41:00", "t1": "00:50:00" } 
]}
const cutlist1_text = 'cutlist is ok,'

// order of intervals is wrong but sorted it is ok
const cutlist2 = {value: [
    { "t0": "00:30:00", "t1": "00:40:00" }, 
    { "t0": "00:00:00", "t1": "00:20:00" }, 
    { "t0": "00:41:00", "t1": "00:50:00" } 
]}
const cutlist2_text = 'order of intervals is wrong but sorted it is ok,'

// order is ok but 1 inteval is reversed
const cutlist3 = {value: [
    { "t0": "00:00:00", "t1": "00:20:00" }, 
    { "t0": "00:40:00", "t1": "00:30:00" }, 
    { "t0": "00:41:00", "t1": "00:50:00" } 
]}
const cutlist3_text = 'order is ok but 1 inteval is reversed,'

// t0 equal t1
const cutlist4 = {value: [
    { "t0": "00:00:00", "t1": "00:00:00" }, 
    { "t0": "00:30:00", "t1": "00:40:00" }, 
    { "t0": "00:41:00", "t1": "00:50:00" } 
]}
const cutlist4_text = 't0 equal t1,'

// overlapping intervals
const cutlist5 = {value: [
    { "t0": "00:00:00", "t1": "00:50:00" }, 
    { "t0": "00:30:00", "t1": "00:40:00" }, 
    { "t0": "00:41:00", "t1": "00:50:00" } 
]}
const cutlist5_text = 'overlapping intervals,'

// cutlist is ok, just 1 interval
const cutlist6 = {value:[ { "t0": "00:00:00", "t1": "01:31:44" } ]}
const cutlist6_text = 'cutlist is ok, just 1 interval,'

// cutlist is ok, intervals are side by side
const cutlist7 = {value: [
    { "t0": "00:00:00", "t1": "00:30:00" }, 
    { "t0": "00:30:00", "t1": "00:50:00" }
]}
const cutlist7_text = 'cutlist is ok, intervals are side by side,'

function validate_cutlist(cutlist) {
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
    // else return false and disable cut button in CutterDialog.vue
}

console.table([
    { "before" : cutlist1.value, "Cutlist": cutlist1_text, "IsValid": validate_cutlist(cutlist1), 'after': cutlist1.value},
    { "before" : cutlist2.value, "Cutlist": cutlist2_text, "IsValid": validate_cutlist(cutlist2), 'after': cutlist2.value},
    { "before" : cutlist3.value, "Cutlist": cutlist3_text, "IsValid": validate_cutlist(cutlist3), 'after': cutlist3.value},
    { "before" : cutlist4.value, "Cutlist": cutlist4_text, "IsValid": validate_cutlist(cutlist4), 'after': cutlist4.value},
    { "before" : cutlist5.value, "Cutlist": cutlist5_text, "IsValid": validate_cutlist(cutlist5), 'after': cutlist5.value},
    { "before" : cutlist6.value, "Cutlist": cutlist6_text, "IsValid": validate_cutlist(cutlist6), 'after': cutlist6.value},
    { "before" : cutlist7.value, "Cutlist": cutlist7_text, "IsValid": validate_cutlist(cutlist7), 'after': cutlist7.value}
]);
