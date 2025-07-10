import streamlit as st
import io
from mss65_hex_library import HEX_LIBRARY

def calculate_offsets(bin_data):
    length = len(bin_data)
    offsets = {"locationoffset1": 0, "locationoffset2": 0, "locationoffset8": 0, "locationoffset9": 0, "locationoffset12": 0}
    if length == 786432:   # 0xC0000
        offsets = {k: 0 for k in offsets}
    elif length == 788740:
        for k in offsets: offsets[k] = 4860
    return offsets

def apply_patch(bin_data, patch_entry, offsets, default_offset=0):
    offset = patch_entry.get("offset", default_offset)
    if callable(offset):
        offset = offset(offsets)
    patch_bytes = bytes.fromhex(patch_entry["hex"].replace('\n','').replace(' ',''))
    bin_data[offset:offset + len(patch_bytes)] = patch_bytes

# Feature patch functions as in previous replies...
def apply_stage_remap(bin_data, offsets, stage):
    key = "stage1_remap_main" if stage == 1 else "stage2_remap_main"
    apply_patch(bin_data, HEX_LIBRARY[key], offsets)
    for k in ["remap_axis1","remap_axis2","remap_axis3","remap_axis4","remap_axis5","remap_table1","remap_table2","remap_table3"]:
        apply_patch(bin_data, HEX_LIBRARY[k], offsets)
    apply_patch(bin_data, HEX_LIBRARY["wot_fuel_axis"], offsets)
    apply_patch(bin_data, HEX_LIBRARY["axis_patch2"], offsets)

def apply_vmax(bin_data, offsets):
    apply_patch(bin_data, HEX_LIBRARY["vmax_check_tuned"], offsets)

def apply_valet(bin_data, offsets):
    apply_patch(bin_data, HEX_LIBRARY["valet_mode"], offsets)

def apply_sap(bin_data, offsets):
    apply_patch(bin_data, HEX_LIBRARY["sap_patch"], offsets)

def apply_coldstart(bin_data, offsets):
    apply_patch(bin_data, HEX_LIBRARY["cold_start_patch"], offsets)

def apply_cat(bin_data, offsets):
    apply_patch(bin_data, HEX_LIBRARY["cat_patch"], offsets)

def apply_o2(bin_data, offsets):
    apply_patch(bin_data, HEX_LIBRARY["postcat_o2_patch"], offsets)

def apply_burble(bin_data, offsets):
    apply_patch(bin_data, HEX_LIBRARY["burble_patch"], offsets)

def apply_alphan(bin_data, offsets):
    bin_data[127144 + offsets["locationoffset1"]] = 0x01

def apply_trans_swap(bin_data, offsets, mode):
    v = 0x01 if mode=="Manual" else 0x02
    bin_data[36000 + offsets["locationoffset1"]] = v

def apply_rev_limit_gear(bin_data, offsets, limits):
    base = 19610 + offsets["locationoffset1"]
    for i,val in enumerate(limits):
        bin_data[base+i*2:base+i*2+2] = int(val).to_bytes(2, 'little')

def apply_rev_limit_temp(bin_data, offsets, rpm_list, temp_list):
    base_rpm = 19660 + offsets["locationoffset1"]
    base_temp = 19674 + offsets["locationoffset1"]
    for i, rpm in enumerate(rpm_list):
        bin_data[base_rpm+i*2:base_rpm+i*2+2] = int(rpm).to_bytes(2,'little')
    for i, t in enumerate(temp_list):
        t_scaled = int((float(t)+273.2)*10)
        bin_data[base_temp+i*2:base_temp+i*2+2] = t_scaled.to_bytes(2,'little')

def apply_throttle(bin_data, offsets, throttle_map, mode):
    base = {"Comfort": 33988, "Normal": 34004, "Sport": 34020}[mode] + offsets["locationoffset1"]
    bin_data[base:base+16] = bytes(throttle_map)

# --- STREAMLIT UI ---
st.title("MSS65 Binary Tuning Tool (Web Version)")

st.markdown("*Upload your MSS65 .bin, edit features, and download the patched file. No install needed!*")

uploaded_file = st.file_uploader("Upload your MSS65 .bin file", type=["bin"])

if uploaded_file:
    bin_data = bytearray(uploaded_file.read())
    offsets = calculate_offsets(bin_data)
    st.success(f"Loaded {len(bin_data)} bytes.")

    st.header("Engine Features")
    remap = st.selectbox("Performance Remap", ["None", "Stage 1", "Stage 2"])
    vmax = st.checkbox("Remove VMAX Limiter")
    valet = st.checkbox("Enable Valet Mode")
    alphan = st.checkbox("Enable AlphaN")

    st.subheader("Rev Limit Per Gear")
    default_gears = [8250]*8
    rev_limit_gear = []
    for i in range(8):
        rev_limit_gear.append(st.number_input(f"Gear {i+1} RPM Limit", 0, 10000, default_gears[i]))

    st.subheader("Rev Limit by Temp")
    default_rpms = [8250]*6
    default_temps = [70, 80, 90, 100, 110, 120]
    rev_limit_temp_rpms = []
    rev_limit_temp_temps = []
    for i in range(6):
        rev_limit_temp_rpms.append(st.number_input(f"RPM Limit {i+1} (by Temp)", 0, 10000, default_rpms[i], key=f"temp_rpm_{i}"))
        rev_limit_temp_temps.append(st.number_input(f"Temp Breakpoint {i+1} (°C)", -40, 150, default_temps[i], key=f"temp_bp_{i}"))

    st.subheader("Throttle Maps")
    throttle_maps = {}
    for mode in ["Comfort","Normal","Sport"]:
        throttle_maps[mode] = []
        st.markdown(f"**{mode}**")
        cols = st.columns(8)
        for i in range(16):
            with cols[i%8]:
                throttle_maps[mode].append(st.number_input(f"{mode} Point {i+1}", 0, 255, i*16, key=f"{mode}_{i}"))

    st.header("Emissions / DTC Features")
    sap = st.checkbox("SAP Delete (DTC Suppression)")
    coldstart = st.checkbox("Cold Start Delete")
    cat = st.checkbox("Primary Cat DTC Delete")
    o2 = st.checkbox("Post-Cat O2 DTC Delete")
    burble = st.checkbox("Enable Overrun Burble/Pops")

    st.header("Transmission Features")
    trans = st.selectbox("Transmission Coding", ["No Change","Manual","SMG"])

    if st.button("Patch and Download"):
        patched = bytearray(bin_data)
        if remap=="Stage 1":
            apply_stage_remap(patched, offsets, 1)
        elif remap=="Stage 2":
            apply_stage_remap(patched, offsets, 2)
        if vmax:
            apply_vmax(patched, offsets)
        if valet:
            apply_valet(patched, offsets)
        if alphan:
            apply_alphan(patched, offsets)
        apply_rev_limit_gear(patched, offsets, rev_limit_gear)
        apply_rev_limit_temp(patched, offsets, rev_limit_temp_rpms, rev_limit_temp_temps)
        for mode in throttle_maps:
            apply_throttle(patched, offsets, throttle_maps[mode], mode)
        if sap:
            apply_sap(patched, offsets)
        if coldstart:
            apply_coldstart(patched, offsets)
        if cat:
            apply_cat(patched, offsets)
        if o2:
            apply_o2(patched, offsets)
        if burble:
            apply_burble(patched, offsets)
        if trans in ("Manual","SMG"):
            apply_trans_swap(patched, offsets, trans)
        st.success("All patches applied! Download your file below.")
        st.download_button("Download patched .bin", data=patched, file_name="patched.bin", mime="application/octet-stream")
