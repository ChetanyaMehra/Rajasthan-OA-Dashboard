"""
Rajasthan InSTS Open Access — Capacity Estimator
Pure Python · No Excel dependency · Streamlit Cloud ready
"""
import math
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Rajasthan OA Estimator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""<style>
.kpi-card{background:#f0f4ff;border-radius:10px;padding:14px 18px;
  border-left:4px solid #1F3864;margin-bottom:8px}
.kpi-green{background:#f0faf0;border-left-color:#2E7D32}
.kpi-amber{background:#fff8f0;border-left-color:#E65100}
.kpi-red  {background:#fff0f0;border-left-color:#C62828}
.kpi-label{font-size:12px;color:#555;font-weight:500}
.kpi-value{font-size:22px;font-weight:700;color:#1F3864}
.kpi-unit {font-size:11px;color:#888}
.sec-title{font-size:17px;font-weight:700;color:#1F3864;
  border-bottom:2px solid #1F3864;padding-bottom:3px;margin:16px 0 10px}
</style>""", unsafe_allow_html=True)

# ── Solar generation profile ──────────────────────────────────────────────────
# kWh per 1 MWp per month per hour-slot (Apr→Mar order, 12 months)
PROFILE = {
    0:[0]*12,1:[0]*12,2:[0]*12,3:[0]*12,4:[0]*12,5:[0]*12,
    6:[0,0,2.95,542.79,1177.39,1265.06,606.65,581.04,341.65,113.25,0,0],
    7:[206.71,737.49,2233.88,4193.05,4909.30,4632.35,2967.78,3494.40,3665.23,3342.29,1437.00,494.48],
    8:[3287.61,5029.70,8367.65,10304.40,10315.70,9149.03,6245.11,8567.55,8945.35,9873.48,6713.06,4338.47],
    9:[9053.72,11027.26,14527.17,15910.82,15738.37,13316.30,10230.15,13439.60,14049.71,15969.47,13023.15,10901.35],
    10:[13395.43,15322.76,19473.25,19345.59,19688.51,17615.12,14299.29,16837.22,17605.34,20019.48,17229.13,15084.36],
    11:[16565.50,17062.84,20062.39,19534.06,20616.45,18580.22,16022.0,17488.80,17899.19,20643.0,18983.89,17395.30],
    12:[19670.52,20624.12,18645.09,16424.0,18727.36,17757.87,20666.67,19364.62,18170.97,17080.95,17461.93,20493.04],
    13:[19484.96,19675.57,18480.70,17515.58,18779.12,17921.17,20556.46,18330.06,18066.97,16783.06,17170.27,20044.33],
    14:[18893.28,18180.09,16469.18,16751.0,16189.37,16756.49,18417.21,15069.75,15935.31,15451.92,16975.93,19457.35],
    15:[15599.37,14294.59,12487.65,13489.22,13767.84,12287.18,13492.04,10546.08,11619.35,11544.05,13991.23,16770.07],
    16:[10601.85,9606.06,9233.68,8727.07,8678.02,8006.78,7270.41,4190.31,4647.72,6083.02,8646.72,11017.53],
    17:[5039.50,4901.80,4821.44,4235.40,4152.08,3295.47,1835.55,555.41,625.64,1268.75,2893.64,4651.64],
    18:[970.54,1279.07,1553.20,1170.91,923.42,351.05,0.41,0,0,0,142.03,386.26],
    19:[0,2.33,67.11,33.34,2.63,0,0,0,0,0,0,0],
    20:[0]*12,21:[0]*12,22:[0]*12,23:[0]*12,
}
MONTHS = ["April","May","June","July","August","September",
          "October","November","December","January","February","March"]
MABR   = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"]
DAYS   = [30,31,30,31,31,30,31,30,31,31,28,31]
SLOTS  = ["Normal","Morning Peak","Off-Peak","Evening Peak"]
SLOT_HRS = {"Normal":14,"Morning Peak":2,"Off-Peak":4,"Evening Peak":4}
TOD_PCT  = {"Normal":0.0,"Morning Peak":0.05,"Off-Peak":-0.10,"Evening Peak":0.10}

def tod_slot(hr):
    if hr in [0,1,2,3,4,5,8,9,10,11,16,17,22,23]: return "Normal"
    elif hr in [6,7]:         return "Morning Peak"
    elif hr in [12,13,14,15]: return "Off-Peak"
    else:                     return "Evening Peak"

# ── Core calculation engine ───────────────────────────────────────────────────
def run(solar_dc, re_sol, re_bess, base_tariff, addons_dict,
        td_pct, wheeling, icr, ed, ogc_mult, oa_tc_fixed,
        bess_tc_disc, bess_whl_disc, load_mw):

    solar_ac = solar_dc / 1.5
    bess_mwh = solar_ac * 0.05 * 2
    bess_mw  = bess_mwh / 2
    chg_eff  = math.sqrt(0.82)
    dsc_eff  = math.sqrt(0.82)
    td       = td_pct / 100

    # ── TABLE 1: Solar Gross ────────────────────────────────────────────────
    t1 = {s: [0.0]*12 for s in SLOTS}
    for hr in range(24):
        s = tod_slot(hr)
        for m in range(12):
            t1[s][m] += PROFILE[hr][m] * solar_dc

    solar_gross_ann = sum(sum(t1[s]) for s in SLOTS)

    # ── TABLE 2: BESS Charging (flat monthly, hrs 12&13) ───────────────────
    bess_raw_mo     = bess_mwh * 1000 * 365 / 12  # same every month
    bess_stored_mo  = bess_raw_mo * chg_eff

    # ── TABLE 3: Solar after BESS deduction (Off-Peak, hrs 12-15) ──────────
    t3 = {s: list(t1[s]) for s in SLOTS}
    for m in range(12):
        t3["Off-Peak"][m] = max(0, t1["Off-Peak"][m] - bess_raw_mo)

    # ── TABLE 4: Solar after T&D loss ──────────────────────────────────────
    t4 = {s: [v*(1-td) for v in t3[s]] for s in SLOTS}

    solar_net_ann  = sum(sum(t4[s]) for s in SLOTS)
    t4_total_mo    = [sum(t4[s][m] for s in SLOTS) for m in range(12)]

    # ── TABLE 7: BESS Discharge (Evening Peak, hrs 18-21) ──────────────────
    bess_disc_mo   = bess_stored_mo * dsc_eff * (1 - td)
    bess_ann       = bess_disc_mo * 12

    # ── Consumer Consumption (flat load, proportional by slot hours) ────────
    cons_ann = load_mw * 1000 * 8760
    cons_mo  = {s: [cons_ann * SLOT_HRS[s] / 24 * DAYS[m] / 365
                    for m in range(12)] for s in SLOTS}
    total_cons_mo  = [sum(cons_mo[s][m] for s in SLOTS) for m in range(12)]
    total_cons_ann = sum(total_cons_mo)

    # ── Consumer after BESS settlement ─────────────────────────────────────
    cons_ab = {s: list(cons_mo[s]) for s in SLOTS}
    for m in range(12):
        cons_ab["Evening Peak"][m] = max(0, cons_mo["Evening Peak"][m] - bess_disc_mo)
    cons_ab_total  = [sum(cons_ab[s][m] for s in SLOTS) for m in range(12)]

    # ── Banking ─────────────────────────────────────────────────────────────
    # Peak to Peak: uses T4 solar gen (not T8) and after-BESS consumption
    p2p = [max(0, (cons_ab["Morning Peak"][m] + cons_ab["Evening Peak"][m])
                  - (t4["Morning Peak"][m] + t4["Evening Peak"][m]))
           for m in range(12)]

    cons_ex_peak = [cons_ab_total[m] - p2p[m] for m in range(12)]
    gen_minus    = [t4_total_mo[m]   - cons_ex_peak[m] for m in range(12)]
    excess_pw    = [max(0, v) for v in gen_minus]

    pct30     = [0.30 * total_cons_mo[m] for m in range(12)]
    pct25     = [0.25 * t4_total_mo[m]   for m in range(12)]
    boundary  = [max(pct30[m], pct25[m]) for m in range(12)]
    allowable = [min(excess_pw[m], boundary[m]) for m in range(12)]
    bank_loss = [0.08 * allowable[m] for m in range(12)]
    carry_pool= [0.92 * allowable[m] for m in range(12)]
    lapsed_s1 = [max(0, excess_pw[m] - allowable[m]) for m in range(12)]

    # Month-on-month rolling consolidation
    banked        = [0.0]*12
    adjustments   = [0.0]*12
    carry_fwd     = [0.0]*12
    consolidation = [0.0]*12
    for m in range(12):
        consolidation[m] = carry_fwd[m-1] if m > 0 else 0.0
        pool = carry_pool[m] + consolidation[m]
        gm   = gen_minus[m]
        adj  = (pool + gm) if (gm < 0 and pool > 0) else (gm if gm < 0 else 0.0)
        adjustments[m] = adj
        if pool > 0 and adj < 0:
            banked[m] = pool
        elif pool > 0 and adj > 0:
            banked[m] = max(0, pool - adj)
        carry_fwd[m] = max(0, pool - banked[m])

    # RTS: Real-Time Settlement (solar only)
    rts = [cons_ex_peak[m] if gen_minus[m] >= 0
           else cons_ex_peak[m] + gen_minus[m]
           for m in range(12)]

    bess_settled_mo   = [bess_disc_mo] * 12
    total_settled_mo  = [rts[m] + banked[m] + bess_settled_mo[m] for m in range(12)]
    total_settled_ann = sum(total_settled_mo)
    rts_ann           = sum(rts)
    banked_ann        = sum(banked)
    bank_loss_ann     = sum(bank_loss)
    lapsed_ann        = sum(lapsed_s1)
    residual_ann      = total_cons_ann - total_settled_ann
    re_disp           = total_settled_ann / total_cons_ann if total_cons_ann > 0 else 0
    td_loss_ann       = solar_gross_ann - solar_net_ann

    # ── Grid Tariff (post OA, excl ICR) ────────────────────────────────────
    addon_total = sum(addons_dict.values())
    grid_tariff = {s: base_tariff*(1+TOD_PCT[s]) + addon_total - icr for s in SLOTS}
    # Weighted blended pre-OA tariff
    pre_oa_tariff = sum(grid_tariff[s]*SLOT_HRS[s] for s in SLOTS) / 24

    # ── RE Landed Cost ──────────────────────────────────────────────────────
    # OA Transmission charges (annualised fixed charge per kWh of gross injection)
    solar_after_bess_gross = sum(sum(t3[s]) for s in SLOTS)  # T3 annual
    oa_tc_solar = (oa_tc_fixed * solar_ac * 1000 * 12 / solar_after_bess_gross
                   if solar_after_bess_gross > 0 else 0)
    oa_tc_bess  = ((oa_tc_fixed * bess_mw * 1000 * 12 / bess_ann) * (1-bess_tc_disc)
                   if bess_ann > 0 else 0)

    whl_bess     = wheeling * (1 - bess_whl_disc)
    tc_inr_solar = oa_tc_solar * solar_gross_ann
    tc_inr_bess  = oa_tc_bess  * bess_ann
    whl_inr_solar= wheeling    * solar_net_ann
    whl_inr_bess = whl_bess    * bess_ann
    ogc_inr      = ogc_mult * solar_ac * 1000 * 12   # INR annual OGC
    lapse_inr    = lapsed_ann * re_sol

    # RE payout uses T3 (solar after BESS deduction, before T&D) units
    solar_after_bess_ann = sum(sum(t3[s]) for s in SLOTS)
    re_payout_solar = re_sol * solar_after_bess_ann

    solar_landed = ((re_payout_solar
                     + tc_inr_solar + whl_inr_solar
                     + ogc_inr + lapse_inr)
                    / solar_net_ann + ed) if solar_net_ann > 0 else 0

    bess_landed  = ((re_bess * bess_ann
                     + tc_inr_bess + whl_inr_bess)
                    / bess_ann + ed) if bess_ann > 0 else 0

    # Blended: SUMPRODUCT weighted by settled units
    sol_settled_ann = total_settled_ann - bess_ann
    blended_landed  = ((sol_settled_ann * solar_landed + bess_ann * bess_landed)
                       / total_settled_ann if total_settled_ann > 0 else 0)

    # ── Savings ─────────────────────────────────────────────────────────────
    pre_oa_cost_cr   = total_cons_ann  * pre_oa_tariff / 1e7
    re_cost_cr       = total_settled_ann * blended_landed / 1e7
    residual_cost_cr = residual_ann    * pre_oa_tariff   / 1e7
    post_oa_cost_cr  = re_cost_cr + residual_cost_cr
    savings_cr       = pre_oa_cost_cr - post_oa_cost_cr

    return dict(
        solar_ac=solar_ac, bess_mwh=bess_mwh,
        solar_gross_ann=solar_gross_ann, solar_net_ann=solar_net_ann,
        bess_ann=bess_ann, total_cons_ann=total_cons_ann,
        rts_ann=rts_ann, banked_ann=banked_ann,
        bess_settled_ann=bess_ann, lapsed_ann=lapsed_ann,
        bank_loss_ann=bank_loss_ann, td_loss_ann=td_loss_ann,
        total_settled_ann=total_settled_ann, residual_ann=residual_ann,
        re_disp=re_disp, pre_oa_tariff=pre_oa_tariff,
        solar_landed=solar_landed, bess_landed=bess_landed,
        blended_landed=blended_landed, savings_cr=savings_cr,
        pre_oa_cost_cr=pre_oa_cost_cr, post_oa_cost_cr=post_oa_cost_cr,
        grid_tariff=grid_tariff,
        mo=dict(gen=t4_total_mo, settled=total_settled_mo,
                cons=total_cons_mo, rts=rts, banked=banked,
                bess=bess_settled_mo, lapsed=lapsed_s1,
                t4n=t4["Normal"], t4mp=t4["Morning Peak"],
                t4op=t4["Off-Peak"], t4ep=t4["Evening Peak"]),
    )

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ Rajasthan OA Estimator")
    st.caption("InSTS Cumulative Settlement · Sunsure Energy")
    st.divider()

    st.markdown("### 🔆 Plant")
    solar_dc    = st.number_input("Solar DC Capacity (MWp)", 1.0, 300.0, 20.0, 1.0)
    re_sol      = st.number_input("RE Tariff – Solar (Rs/kWh)", 1.0, 8.0, 3.66, 0.01)
    re_bess     = st.number_input("RE Tariff – BESS (Rs/kWh)", 1.0, 15.0, 6.70, 0.01)

    st.markdown("### 🏭 Consumer")
    load_mw     = st.number_input("Load (MW flat)", 1.0, 500.0, 11.0, 0.5)

    st.markdown("### 🔌 Grid")
    voltage = st.selectbox("Voltage", ["132 kV","220 kV","33 kV","11 kV"])
    VTMAP = {"11 kV":(6.50,0.62,0.126),"33 kV":(6.305,0.12,0.038),
             "132 kV":(6.24,0.01,0.0),"220 kV":(6.175,0.01,0.0)}
    base_t, wheeling, whl_loss = VTMAP[voltage]
    td_pct = 4.05

    with st.expander("Add-on charges (Rs/kWh)"):
        pf  = st.number_input("PF Incentive",      -1.0,1.0,-0.00577,0.001,format="%.5f")
        rs  = st.number_input("Reg. Surcharge",     0.0,5.0, 1.0,   0.01)
        sfa = st.number_input("Special Fuel Amount",0.0,2.0, 0.00517,0.001,format="%.5f")
        icr = st.number_input("ICR",               -2.0,2.0, 0.0,   0.01)
        ed  = st.number_input("Electricity Duty",   0.0,2.0, 0.40,  0.01)
        wc  = st.number_input("Water CESS",         0.0,1.0, 0.10,  0.01)
        uc  = st.number_input("Urban CESS",         0.0,1.0, 0.0,   0.01)

    addons = {"pf":pf,"rs":rs,"sfa":sfa,"ed":ed,"wc":wc,"uc":uc}

# ── Run engine ────────────────────────────────────────────────────────────────
R = run(solar_dc=solar_dc, re_sol=re_sol, re_bess=re_bess,
        base_tariff=base_t, addons_dict=addons, td_pct=td_pct,
        wheeling=wheeling, icr=icr, ed=ed, ogc_mult=1.3185,
        oa_tc_fixed=157.87, bess_tc_disc=0.75, bess_whl_disc=0.75,
        load_mw=load_mw)

# ── Header banner ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(90deg,#1F3864,#2E75B6);
 border-radius:12px;padding:18px 24px;margin-bottom:16px">
 <h2 style="color:white;margin:0">Rajasthan InSTS Open Access – Capacity Estimator</h2>
 <p style="color:#BDD7EE;margin:4px 0 0">
  {solar_dc:.0f} MWp Solar &nbsp;|&nbsp; {R['solar_ac']:.2f} MW AC &nbsp;|&nbsp;
  {R['bess_mwh']:.3f} MWh BESS &nbsp;|&nbsp; {voltage} &nbsp;|&nbsp;
  {load_mw:.1f} MW Load
 </p>
</div>""", unsafe_allow_html=True)

def card(val, label, unit, cls=""):
    return (f'<div class="kpi-card {cls}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{val}</div>'
            f'<div class="kpi-unit">{unit}</div></div>')

# ── Tabs ──────────────────────────────────────────────────────────────────────
t1,t2,t3,t4 = st.tabs(["📊 Summary","⚡ Generation & Banking","💰 Tariff & Savings","📋 Monthly"])

# ═════════════════════ TAB 1: SUMMARY ════════════════════════════════════════
with t1:
    st.markdown('<div class="sec-title">Settlement KPIs</div>', unsafe_allow_html=True)
    inj = max(R["solar_net_ann"]+R["bess_ann"],1)
    c1,c2,c3,c4,c5 = st.columns(5)
    with c1: st.markdown(card(f"{R['re_disp']*100:.1f}%","RE Displacement","% of consumption","kpi-green"),unsafe_allow_html=True)
    with c2: st.markdown(card(f"{R['rts_ann']/inj*100:.1f}%","Real-Time Settlement","% of injection"),unsafe_allow_html=True)
    with c3: st.markdown(card(f"{R['banked_ann']/inj*100:.1f}%","Banking Settlement","% of injection"),unsafe_allow_html=True)
    with c4: st.markdown(card(f"{R['bess_settled_ann']/inj*100:.1f}%","BESS Settlement","% of injection"),unsafe_allow_html=True)
    with c5: st.markdown(card(f"{R['lapsed_ann']/inj*100:.1f}%","Lapsation","% of injection","kpi-amber"),unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    with c1: st.markdown(card(f"{R['bank_loss_ann']/inj*100:.1f}%","Banking Loss","% of injection"),unsafe_allow_html=True)
    with c2: st.markdown(card(f"{R['td_loss_ann']/max(R['solar_gross_ann'],1)*100:.1f}%","T&D Loss","% of solar gross"),unsafe_allow_html=True)
    with c3: st.markdown(card(f"{R['total_settled_ann']/1e6:.2f} MU","Settled Units","million kWh/yr","kpi-green"),unsafe_allow_html=True)
    with c4: st.markdown(card(f"{R['bess_mwh']:.3f} MWh","BESS Capacity","MWh"),unsafe_allow_html=True)
    with c5: st.markdown(card(f"₹{R['savings_cr']:.2f} Cr","Yearly Savings","Rs Crore/yr","kpi-green"),unsafe_allow_html=True)

    st.markdown('<div class="sec-title">Cost Summary</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1: st.markdown(card(f"₹{R['pre_oa_tariff']:.3f}","Grid Tariff (Pre-OA)","Rs/kWh"),unsafe_allow_html=True)
    with c2: st.markdown(card(f"₹{R['blended_landed']:.3f}","RE Landed Cost (Blended)","Rs/kWh"),unsafe_allow_html=True)
    with c3: st.markdown(card(f"₹{R['pre_oa_tariff']-R['blended_landed']:.3f}","Tariff Delta","Rs/kWh saved","kpi-green"),unsafe_allow_html=True)

    # Charts row
    c1,c2 = st.columns(2)
    with c1:
        labels = ["RTS (Solar)","BESS","Banked","Lapsed","Banking Loss","T&D Loss"]
        vals   = [R["rts_ann"],R["bess_settled_ann"],R["banked_ann"],
                  R["lapsed_ann"],R["bank_loss_ann"],R["td_loss_ann"]]
        colors = ["#2E7D32","#1F3864","#2E75B6","#E65100","#C62828","#BFBFBF"]
        fig = go.Figure(go.Pie(labels=labels,values=vals,hole=0.52,
                               marker_colors=colors,textinfo="label+percent",textfont_size=10))
        fig.update_layout(title="Injection Unit Trace",height=340,
                          legend=dict(orientation="h",y=-0.2),
                          margin=dict(t=36,b=10,l=10,r=10))
        st.plotly_chart(fig,use_container_width=True)

    with c2:
        fig2 = go.Figure()
        pre = [R["mo"]["cons"][m]*R["pre_oa_tariff"]/1e5 for m in range(12)]
        post_re  = [R["mo"]["settled"][m]*R["blended_landed"]/1e5 for m in range(12)]
        post_grid= [max(0,R["mo"]["cons"][m]-R["mo"]["settled"][m])*R["pre_oa_tariff"]/1e5 for m in range(12)]
        fig2.add_bar(name="Pre-OA Grid Cost",x=MABR,y=pre,marker_color="#C62828",opacity=0.7)
        fig2.add_bar(name="RE Cost",x=MABR,y=post_re,marker_color="#2E7D32")
        fig2.add_bar(name="Residual Grid",x=MABR,y=post_grid,marker_color="#2E75B6")
        fig2.update_layout(title="Monthly Cost Comparison (₹ Lakh)",barmode="group",
                           height=340,yaxis_title="₹ Lakh",
                           legend=dict(orientation="h",y=-0.2),
                           margin=dict(t=36,b=10,l=10,r=10))
        st.plotly_chart(fig2,use_container_width=True)

# ═════════════════════ TAB 2: GENERATION & BANKING ═══════════════════════════
with t2:
    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sec-title">Generation Summary</div>',unsafe_allow_html=True)
        gdf = pd.DataFrame({
            "Component":["Solar Gross","BESS Raw Charged","Solar Net (after T&D)",
                          "BESS Injected","Total Net Injected"],
            "MU/yr":[R["solar_gross_ann"]/1e6,R["bess_mwh"]*1000*365/1e6,
                     R["solar_net_ann"]/1e6,R["bess_ann"]/1e6,
                     (R["solar_net_ann"]+R["bess_ann"])/1e6],
        })
        st.dataframe(gdf.style.format({"MU/yr":"{:.3f}"}),use_container_width=True,hide_index=True)

    with c2:
        st.markdown('<div class="sec-title">Annual Banking Audit</div>',unsafe_allow_html=True)
        inj = max(R["solar_net_ann"]+R["bess_ann"],1)
        bdf = pd.DataFrame({
            "Parameter":["Total Injection","Real-Time Settled","BESS Settled",
                          "Banked","Lapsed (Stage 1)","Banking Loss (8%)",
                          "Total Settled","Residual Grid","RE Displacement"],
            "kWh/yr":[inj,R["rts_ann"],R["bess_settled_ann"],R["banked_ann"],
                      R["lapsed_ann"],R["bank_loss_ann"],R["total_settled_ann"],
                      R["residual_ann"],None],
            "% of Injection":[100,R["rts_ann"]/inj*100,R["bess_settled_ann"]/inj*100,
                               R["banked_ann"]/inj*100,R["lapsed_ann"]/inj*100,
                               R["bank_loss_ann"]/inj*100,R["total_settled_ann"]/inj*100,
                               R["residual_ann"]/R["total_cons_ann"]*100,
                               R["re_disp"]*100],
        })
        st.dataframe(bdf.style.format({"kWh/yr":"{:,.0f}","% of Injection":"{:.2f}"},
                                       na_rep="—"),
                     use_container_width=True,hide_index=True)

    # Monthly gen stacked
    st.markdown('<div class="sec-title">Monthly Generation vs Consumption</div>',unsafe_allow_html=True)
    fig3 = go.Figure()
    for slot,col in [("t4n","#1F3864"),("t4mp","#FFC000"),("t4op","#2E75B6"),("t4ep","#FF4444")]:
        name={"t4n":"Normal","t4mp":"Morning Peak","t4op":"Off-Peak","t4ep":"Evening Peak"}[slot]
        fig3.add_bar(name=name,x=MABR,y=R["mo"][slot],marker_color=col)
    fig3.add_scatter(name="Consumption",x=MABR,y=R["mo"]["cons"],
                     mode="lines+markers",line=dict(color="black",width=2,dash="dash"))
    fig3.update_layout(barmode="stack",height=360,yaxis_title="kWh",
                       legend=dict(orientation="h",y=-0.18),margin=dict(t=20,b=20,l=10,r=10))
    st.plotly_chart(fig3,use_container_width=True)

    fig4 = go.Figure()
    fig4.add_bar(name="RTS",    x=MABR,y=R["mo"]["rts"],   marker_color="#2E7D32")
    fig4.add_bar(name="BESS",   x=MABR,y=R["mo"]["bess"],  marker_color="#1F3864")
    fig4.add_bar(name="Banked", x=MABR,y=R["mo"]["banked"],marker_color="#2E75B6")
    fig4.add_scatter(name="Total Settled",x=MABR,y=R["mo"]["settled"],
                     mode="lines+markers",line=dict(color="#2E7D32",width=2))
    fig4.update_layout(barmode="stack",title="Monthly Settlement Breakdown",
                       height=320,yaxis_title="kWh",
                       legend=dict(orientation="h",y=-0.18),margin=dict(t=36,b=20,l=10,r=10))
    st.plotly_chart(fig4,use_container_width=True)

# ═════════════════════ TAB 3: TARIFF & SAVINGS ════════════════════════════════
with t3:
    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sec-title">Grid Tariff (Post Open Access, excl ICR)</div>',unsafe_allow_html=True)
        tdf = pd.DataFrame({
            "ToD Slot": list(R["grid_tariff"].keys()),
            "Tariff (Rs/kWh)": [round(v,3) for v in R["grid_tariff"].values()],
            "Hours/Day": [SLOT_HRS[s] for s in R["grid_tariff"]],
        })
        st.dataframe(tdf,use_container_width=True,hide_index=True)

        st.markdown('<div class="sec-title">RE Landed Cost Breakdown</div>',unsafe_allow_html=True)
        redf = pd.DataFrame({
            "Component":["Solar Landed","BESS Landed","Blended Landed"],
            "Rs/kWh":[round(R["solar_landed"],3),round(R["bess_landed"],3),round(R["blended_landed"],3)],
        })
        st.dataframe(redf,use_container_width=True,hide_index=True)

    with c2:
        st.markdown('<div class="sec-title">Savings Summary</div>',unsafe_allow_html=True)
        sdf = pd.DataFrame({
            "Item":["Total Consumption","Settled (RE)","Residual Grid",
                    "Pre-OA Cost","Post-OA Cost","NET SAVINGS"],
            "Value":[
                f"{R['total_cons_ann']/1e6:.2f} MU",
                f"{R['total_settled_ann']/1e6:.2f} MU",
                f"{R['residual_ann']/1e6:.2f} MU",
                f"₹ {R['pre_oa_cost_cr']:.2f} Cr",
                f"₹ {R['post_oa_cost_cr']:.2f} Cr",
                f"₹ {R['savings_cr']:.2f} Cr  🎯",
            ]
        })
        st.dataframe(sdf,use_container_width=True,hide_index=True)

    # Waterfall
    st.markdown('<div class="sec-title">Cost Waterfall (Rs Crore)</div>',unsafe_allow_html=True)
    re_cost_cr  = R["total_settled_ann"]*R["blended_landed"]/1e7
    res_cost_cr = R["residual_ann"]*R["pre_oa_tariff"]/1e7
    fig5 = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute","relative","relative","total"],
        x=["Pre-OA Grid Cost","RE Power Cost","Residual Grid Cost","Net Savings"],
        y=[R["pre_oa_cost_cr"],-re_cost_cr,-res_cost_cr,R["savings_cr"]],
        connector={"line":{"color":"#888"}},
        text=[f"₹{v:.2f}Cr" for v in [R["pre_oa_cost_cr"],-re_cost_cr,-res_cost_cr,R["savings_cr"]]],
        textposition="outside",
        increasing={"marker":{"color":"#2E7D32"}},
        decreasing={"marker":{"color":"#C62828"}},
        totals={"marker":{"color":"#1F3864"}},
    ))
    fig5.update_layout(height=360,yaxis_title="Rs Crore",
                       margin=dict(t=20,b=20,l=10,r=10))
    st.plotly_chart(fig5,use_container_width=True)

# ═════════════════════ TAB 4: MONTHLY DETAIL ══════════════════════════════════
with t4:
    st.markdown('<div class="sec-title">Month-wise Detail</div>',unsafe_allow_html=True)
    mdf = pd.DataFrame({
        "Month":          MABR,
        "Days":           DAYS,
        "Gen (kWh)":      [round(v) for v in R["mo"]["gen"]],
        "Consumption":    [round(v) for v in R["mo"]["cons"]],
        "RTS (kWh)":      [round(v) for v in R["mo"]["rts"]],
        "BESS Settled":   [round(v) for v in R["mo"]["bess"]],
        "Banked (kWh)":   [round(v) for v in R["mo"]["banked"]],
        "Total Settled":  [round(v) for v in R["mo"]["settled"]],
        "Lapsed (kWh)":   [round(v) for v in R["mo"]["lapsed"]],
        "Displacement":   [f"{R['mo']['settled'][m]/max(R['mo']['cons'][m],1)*100:.1f}%"
                           for m in range(12)],
    })
    cols_fmt = {c:"{:,.0f}" for c in ["Gen (kWh)","Consumption","RTS (kWh)",
                "BESS Settled","Banked (kWh)","Total Settled","Lapsed (kWh)"]}
    st.dataframe(mdf.style.format(cols_fmt),use_container_width=True,hide_index=True)

    csv = mdf.to_csv(index=False).encode()
    st.download_button("⬇️ Download CSV",csv,"rajasthan_oa_monthly.csv","text/csv")

    st.caption("Built by Sunsure Energy · Rajasthan InSTS Open Access · Pure Python")
