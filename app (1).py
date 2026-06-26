"""
Rajasthan InSTS Open Access — Capacity Estimator
Pure Python · No Excel dependency · Streamlit Cloud ready
"""
import math
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Rajasthan OA Estimator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""<style>
.kpi-card{background:#f0f4ff;border-radius:10px;padding:12px 16px;
  border-left:4px solid #1F3864;margin-bottom:8px}
.kpi-green{background:#f0faf0;border-left-color:#2E7D32}
.kpi-amber{background:#fff8f0;border-left-color:#E65100}
.kpi-red  {background:#fff0f0;border-left-color:#C62828}
.kpi-label{font-size:11px;color:#555;font-weight:500}
.kpi-value{font-size:20px;font-weight:700;color:#1F3864}
.kpi-unit {font-size:10px;color:#888}
.sec-title{font-size:16px;font-weight:700;color:#1F3864;
  border-bottom:2px solid #1F3864;padding-bottom:3px;margin:14px 0 8px}
.warn-box{background:#fff3cd;border:1px solid #ffc107;border-radius:8px;
  padding:10px 14px;margin:8px 0;color:#856404;font-weight:600}
.info-box{background:#d1ecf1;border:1px solid #bee5eb;border-radius:8px;
  padding:10px 14px;margin:8px 0;color:#0c5460}
</style>""", unsafe_allow_html=True)

# ── Solar generation profile (kWh per 1 MWp, Apr-Mar, 24 hrs × 12 months) ────
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
MONTHS  = ["April","May","June","July","August","September",
           "October","November","December","January","February","March"]
MABR    = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"]
DAYS    = [30,31,30,31,31,30,31,30,31,31,28,31]
SLOTS   = ["Normal","Morning Peak","Off-Peak","Evening Peak"]
SLOT_HRS= {"Normal":14,"Morning Peak":2,"Off-Peak":4,"Evening Peak":4}
TOD_PCT = {"Normal":0.0,"Morning Peak":0.05,"Off-Peak":-0.10,"Evening Peak":0.10}

def tod_slot(hr):
    if hr in [0,1,2,3,4,5,8,9,10,11,16,17,22,23]: return "Normal"
    elif hr in [6,7]:          return "Morning Peak"
    elif hr in [12,13,14,15]:  return "Off-Peak"
    else:                      return "Evening Peak"

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

    # Solar Gross (T1)
    t1 = {s:[0.0]*12 for s in SLOTS}
    for hr in range(24):
        s = tod_slot(hr)
        for m in range(12): t1[s][m] += PROFILE[hr][m] * solar_dc
    solar_gross_ann = sum(sum(t1[s]) for s in SLOTS)

    # BESS flat monthly
    bess_raw_mo    = bess_mwh * 1000 * 365 / 12
    bess_stored_mo = bess_raw_mo * chg_eff
    bess_disc_mo   = bess_stored_mo * dsc_eff * (1 - td)
    bess_ann       = bess_disc_mo * 12

    # Solar after BESS (T3) and after T&D (T4)
    t3 = {s: list(t1[s]) for s in SLOTS}
    for m in range(12): t3["Off-Peak"][m] = max(0, t1["Off-Peak"][m] - bess_raw_mo)
    solar_after_bess_ann = sum(sum(t3[s]) for s in SLOTS)
    t4 = {s: [v*(1-td) for v in t3[s]] for s in SLOTS}
    solar_net_ann  = sum(sum(t4[s]) for s in SLOTS)
    t4_total_mo    = [sum(t4[s][m] for s in SLOTS) for m in range(12)]

    # Consumption (flat)
    cons_ann = load_mw * 1000 * 8760
    cons_mo  = {s:[cons_ann*SLOT_HRS[s]/24*DAYS[m]/365 for m in range(12)] for s in SLOTS}
    total_cons_mo  = [sum(cons_mo[s][m] for s in SLOTS) for m in range(12)]
    total_cons_ann = sum(total_cons_mo)

    # After BESS
    cons_ab = {s: list(cons_mo[s]) for s in SLOTS}
    for m in range(12):
        cons_ab["Evening Peak"][m] = max(0, cons_mo["Evening Peak"][m] - bess_disc_mo)
    cons_ab_total = [sum(cons_ab[s][m] for s in SLOTS) for m in range(12)]

    # Banking (T4 solar only)
    p2p = [max(0,(cons_ab["Morning Peak"][m]+cons_ab["Evening Peak"][m])
                 -(t4["Morning Peak"][m]+t4["Evening Peak"][m]))
           for m in range(12)]
    cons_ex   = [cons_ab_total[m] - p2p[m]    for m in range(12)]
    gen_minus = [t4_total_mo[m] - cons_ex[m]  for m in range(12)]
    excess_pw = [max(0, v) for v in gen_minus]
    pct30     = [0.30*total_cons_mo[m] for m in range(12)]
    pct25     = [0.25*t4_total_mo[m]   for m in range(12)]
    boundary  = [max(pct30[m],pct25[m]) for m in range(12)]
    allowable = [min(excess_pw[m],boundary[m]) for m in range(12)]
    bank_loss = [0.08*allowable[m] for m in range(12)]
    carry_pool= [0.92*allowable[m] for m in range(12)]
    lapsed_s1 = [max(0,excess_pw[m]-allowable[m]) for m in range(12)]

    banked=[0.0]*12; carry_fwd=[0.0]*12
    for m in range(12):
        consol = carry_fwd[m-1] if m > 0 else 0.0
        pool   = carry_pool[m] + consol
        gm     = gen_minus[m]
        adj    = (pool+gm) if (gm<0 and pool>0) else (gm if gm<0 else 0.0)
        if pool > 0 and adj < 0:   banked[m] = pool
        elif pool > 0 and adj > 0: banked[m] = max(0, pool - adj)
        carry_fwd[m] = max(0, pool - banked[m])

    rts = [cons_ex[m] if gen_minus[m]>=0 else cons_ex[m]+gen_minus[m] for m in range(12)]
    bess_settled_mo  = [bess_disc_mo]*12
    total_settled_mo = [rts[m]+banked[m]+bess_settled_mo[m] for m in range(12)]
    total_settled    = sum(total_settled_mo)
    rts_ann          = sum(rts)
    banked_ann       = sum(banked)
    bank_loss_ann    = sum(bank_loss)
    lapsed_ann       = sum(lapsed_s1)
    residual_ann     = total_cons_ann - total_settled
    re_disp          = total_settled / total_cons_ann if total_cons_ann > 0 else 0
    td_loss_ann      = solar_gross_ann - solar_net_ann

    # Tariff
    addon_total = sum(addons_dict.values())
    grid_tariff = {s: base_tariff*(1+TOD_PCT[s])+addon_total-icr for s in SLOTS}
    pre_oa      = sum(grid_tariff[s]*SLOT_HRS[s] for s in SLOTS) / 24

    # RE landed
    oa_tc_sol_rate = (oa_tc_fixed*solar_ac*1000*12/solar_after_bess_ann
                     if solar_after_bess_ann>0 else 0)
    oa_tc_bess_rate= ((oa_tc_fixed*bess_mw*1000*12/bess_ann)*(1-bess_tc_disc)
                     if bess_ann>0 else 0)
    whl_bess       = wheeling*(1-bess_whl_disc)
    tc_inr_sol     = oa_tc_sol_rate  * solar_after_bess_ann
    tc_inr_bess    = oa_tc_bess_rate * bess_ann
    whl_inr_sol    = wheeling        * solar_net_ann
    whl_inr_bess   = whl_bess        * bess_ann
    ogc_inr        = ogc_mult        * solar_ac * 1000 * 12
    lapse_inr      = lapsed_ann      * re_sol

    re_payout_sol  = re_sol  * solar_after_bess_ann
    solar_landed   = ((re_payout_sol+tc_inr_sol+whl_inr_sol+ogc_inr+lapse_inr)
                     / solar_net_ann + ed) if solar_net_ann>0 else 0
    bess_landed    = ((re_bess*bess_ann+tc_inr_bess+whl_inr_bess)
                     / bess_ann + ed) if bess_ann>0 else 0
    sol_settled    = total_settled - bess_ann
    blended        = ((sol_settled*solar_landed+bess_ann*bess_landed)/total_settled
                     if total_settled>0 else 0)
    blended_tariff = ((sol_settled*re_sol+bess_ann*re_bess)/total_settled
                     if total_settled>0 else 0)

    pre_cr   = total_cons_ann*pre_oa/1e7
    post_cr  = total_settled*blended/1e7 + residual_ann*pre_oa/1e7
    savings  = pre_cr - post_cr

    # Monthly ToD analysis data (for ToD chart)
    tod_slots_list = [
        ("TOD 1","Normal",       "Before: 4pm-6pm,10pm-6am,8am-12pm"),
        ("TOD 2","Morning Peak", "Before: 6am-8am"),
        ("TOD 3: Summer","Off-Peak",    "Before: 12pm-4pm (summer)"),
        ("TOD 3: Winter","Off-Peak",    "Before: 12pm-4pm (winter)"),  # same slot, different label
        ("TOD 4","Evening Peak", "Before: 6pm-10pm"),
    ]

    return dict(
        solar_ac=solar_ac, bess_mwh=bess_mwh,
        solar_gross_ann=solar_gross_ann, solar_net_ann=solar_net_ann,
        bess_ann=bess_ann, total_cons_ann=total_cons_ann,
        rts_ann=rts_ann, banked_ann=banked_ann,
        bess_settled_ann=bess_ann, lapsed_ann=lapsed_ann,
        bank_loss_ann=bank_loss_ann, td_loss_ann=td_loss_ann,
        total_settled_ann=total_settled, residual_ann=residual_ann,
        re_disp=re_disp, pre_oa=pre_oa, grid_tariff=grid_tariff,
        solar_landed=solar_landed, bess_landed=bess_landed,
        blended_landed=blended, blended_tariff=blended_tariff,
        savings_cr=savings, pre_oa_cost_cr=pre_cr, post_oa_cost_cr=post_cr,
        mo=dict(
            gen=t4_total_mo, settled=total_settled_mo, cons=total_cons_mo,
            rts=rts, banked=banked, bess=bess_settled_mo, lapsed=lapsed_s1,
            t4n=t4["Normal"], t4mp=t4["Morning Peak"],
            t4op=t4["Off-Peak"], t4ep=t4["Evening Peak"],
        ),
        tod=dict(
            labels     =["TOD 1","TOD 2","TOD 3: Summer","TOD 3: Winter","TOD 4"],
            slots      =["Normal","Morning Peak","Off-Peak","Off-Peak","Evening Peak"],
            pre_cons   =[total_cons_ann*SLOT_HRS[s]/24 for s in
                         ["Normal","Morning Peak","Off-Peak","Off-Peak","Evening Peak"]],
            post_settled=[total_settled*SLOT_HRS[s]/24 for s in
                          ["Normal","Morning Peak","Off-Peak","Off-Peak","Evening Peak"]],
            pre_tariff =[grid_tariff[s] for s in
                         ["Normal","Morning Peak","Off-Peak","Off-Peak","Evening Peak"]],
            post_tariff=[blended if s in ["Normal","Morning Peak","Off-Peak"] else blended
                         for s in ["Normal","Morning Peak","Off-Peak","Off-Peak","Evening Peak"]],
        ),
    )

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ Rajasthan OA Estimator")
    st.caption("InSTS Cumulative Settlement · Sunsure Energy")
    st.divider()

    # Contract demand inputs
    st.markdown("### 🏭 Consumer")
    contract_demand = st.number_input("Contract Demand (MW AC)", 1.0, 500.0, 20.0, 1.0,
                                       help="Customer's sanctioned contract demand in MW AC")
    existing_oa     = st.number_input("Existing OA Already Taken (MW AC)", 0.0, 500.0, 0.0, 1.0,
                                       help="Open Access capacity already utilised")
    allowable_oa    = max(0.0, contract_demand - existing_oa)
    st.markdown(f"""<div class="info-box">
    Allowable new OA: <b>{allowable_oa:.1f} MW AC</b><br>
    Max Solar DC: <b>{allowable_oa*1.5:.1f} MWp</b>
    </div>""", unsafe_allow_html=True)

    load_mw = st.number_input("Consumer Load (MW flat)", 1.0, 500.0, 11.0, 0.5)
    st.divider()

    # Solar DC slider
    st.markdown("### 🔆 Solar Plant")
    max_dc = round(allowable_oa * 1.5, 1) if allowable_oa > 0 else 300.0
    solar_dc = st.slider("Solar DC Capacity (MWp)",
                          min_value=1.0, max_value=max(max_dc*2, 100.0),
                          value=min(20.0, max_dc), step=0.5)

    # Warning if exceeds contract demand
    solar_ac_val = solar_dc / 1.5
    if solar_ac_val > allowable_oa:
        st.markdown(f"""<div class="warn-box">
        ⚠️ Solar AC ({solar_ac_val:.2f} MW) exceeds allowable OA ({allowable_oa:.1f} MW AC).
        Please reduce Solar DC below {allowable_oa*1.5:.1f} MWp.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="info-box">
        ✓ Solar AC: {solar_ac_val:.2f} MW — within allowable OA
        </div>""", unsafe_allow_html=True)

    re_sol  = st.number_input("RE Tariff – Solar (Rs/kWh)", 1.0, 8.0, 3.66, 0.01)
    re_bess = 6.70
    st.markdown(f"**RE Tariff – BESS:** ₹6.70/kWh *(fixed)*")

    st.markdown("### 🔌 Grid")
    voltage = st.selectbox("Voltage Level", ["132 kV","220 kV","33 kV","11 kV"])
    VTMAP   = {"11 kV":(6.50,0.62,0.126),"33 kV":(6.305,0.12,0.038),
               "132 kV":(6.24,0.01,0.0),"220 kV":(6.175,0.01,0.0)}
    base_t, wheeling, whl_loss = VTMAP[voltage]
    td_pct = 4.05

    with st.expander("Add-on charges (Rs/kWh)"):
        pf  = st.number_input("PF Incentive",        -1.0,1.0,-0.00577,0.001,format="%.5f")
        rs  = st.number_input("Reg. Surcharge",       0.0,5.0, 1.0,   0.01)
        sfa = st.number_input("Special Fuel Amount",  0.0,2.0, 0.00517,0.001,format="%.5f")
        icr = st.number_input("ICR",                 -2.0,2.0, 0.0,   0.01)
        ed  = st.number_input("Electricity Duty",     0.0,2.0, 0.40,  0.01)
        wc  = st.number_input("Water CESS",           0.0,1.0, 0.10,  0.01)
        uc  = st.number_input("Urban CESS",           0.0,1.0, 0.0,   0.01)

    addons = {"pf":pf,"rs":rs,"sfa":sfa,"ed":ed,"wc":wc,"uc":uc}

# ── Run ───────────────────────────────────────────────────────────────────────
R = run(solar_dc=solar_dc, re_sol=re_sol, re_bess=re_bess,
        base_tariff=base_t, addons_dict=addons, td_pct=td_pct,
        wheeling=wheeling, icr=icr, ed=ed, ogc_mult=1.3185,
        oa_tc_fixed=157.87, bess_tc_disc=0.75, bess_whl_disc=0.75, load_mw=load_mw)

# Blended tariff display
blended_tariff_display = R["blended_tariff"]

# ── Header ────────────────────────────────────────────────────────────────────
exceed_flag = solar_ac_val > allowable_oa
banner_color = "#8B0000" if exceed_flag else "linear-gradient(90deg,#1F3864,#2E75B6)"
st.markdown(f"""
<div style="background:{banner_color};border-radius:12px;padding:16px 22px;margin-bottom:14px">
 <h2 style="color:white;margin:0">⚡ Rajasthan InSTS Open Access — Capacity Estimator</h2>
 <p style="color:#BDD7EE;margin:4px 0 0">
  {solar_dc:.1f} MWp Solar &nbsp;|&nbsp; {R['solar_ac']:.2f} MW AC &nbsp;|&nbsp;
  {R['bess_mwh']:.3f} MWh BESS &nbsp;|&nbsp; {voltage} &nbsp;|&nbsp; {load_mw:.1f} MW Load
  {"&nbsp;|&nbsp; <b style='color:#FFD700'>⚠️ EXCEEDS CONTRACT DEMAND</b>" if exceed_flag else ""}
 </p>
</div>""", unsafe_allow_html=True)

# Blended tariff info bar
sol_settled_ann = R["total_settled_ann"] - R["bess_ann"]
st.markdown(f"""
<div style="background:#1a1a2e;border-radius:8px;padding:10px 20px;
 display:flex;gap:40px;margin-bottom:12px;color:white;flex-wrap:wrap">
 <span>☀️ <b>Solar Tariff:</b> ₹{re_sol:.2f}/kWh</span>
 <span>🔋 <b>BESS Tariff:</b> ₹{re_bess:.2f}/kWh <i>(fixed)</i></span>
 <span>⚡ <b>Blended RE Tariff:</b> ₹{blended_tariff_display:.3f}/kWh
  <i>(solar {sol_settled_ann/1e6:.1f}MU × {re_sol:.2f} + BESS {R['bess_ann']/1e6:.3f}MU × {re_bess:.2f})</i></span>
</div>""", unsafe_allow_html=True)

def card(val, label, unit, cls=""):
    return (f'<div class="kpi-card {cls}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{val}</div>'
            f'<div class="kpi-unit">{unit}</div></div>')

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5 = st.tabs([
    "📊 Summary","⚡ Generation & Banking",
    "📈 ToD Analysis","💰 Tariff & Savings","📋 Monthly Detail"])

# ══════════ TAB 1: SUMMARY ═══════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="sec-title">Settlement KPIs</div>',unsafe_allow_html=True)
    inj = max(R["solar_net_ann"]+R["bess_ann"],1)
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: st.markdown(card(f"{R['re_disp']*100:.1f}%","RE Displacement","% of consumption","kpi-green"),unsafe_allow_html=True)
    with c2: st.markdown(card(f"{R['rts_ann']/inj*100:.1f}%","Real-Time Settlement","% of injection"),unsafe_allow_html=True)
    with c3: st.markdown(card(f"{R['banked_ann']/inj*100:.1f}%","Banking Settlement","% of injection"),unsafe_allow_html=True)
    with c4: st.markdown(card(f"{R['bess_settled_ann']/inj*100:.1f}%","BESS Settlement","% of injection"),unsafe_allow_html=True)
    with c5: st.markdown(card(f"{R['lapsed_ann']/inj*100:.1f}%","Lapsation","% of injection","kpi-amber"),unsafe_allow_html=True)
    with c6: st.markdown(card(f"{R['bank_loss_ann']/inj*100:.1f}%","Banking Loss","% of injection"),unsafe_allow_html=True)

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: st.markdown(card(f"₹{R['pre_oa']:.3f}","Grid Tariff Pre-OA","Rs/kWh"),unsafe_allow_html=True)
    with c2: st.markdown(card(f"₹{R['blended_landed']:.3f}","RE Landed Cost","Rs/kWh"),unsafe_allow_html=True)
    with c3: st.markdown(card(f"₹{R['savings_cr']:.2f} Cr","Yearly Savings","Rs Crore/yr","kpi-green"),unsafe_allow_html=True)
    with c4: st.markdown(card(f"{R['total_settled_ann']/1e6:.2f} MU","Settled Units","MU/yr","kpi-green"),unsafe_allow_html=True)
    with c5: st.markdown(card(f"{R['bess_mwh']:.3f} MWh","BESS Capacity","MWh"),unsafe_allow_html=True)
    with c6: st.markdown(card(f"{allowable_oa:.1f} MW","Allowable OA","MW AC"),unsafe_allow_html=True)

    # Charts
    c1,c2 = st.columns(2)
    with c1:
        labels=["RTS","BESS Settled","Banked","Lapsed","Banking Loss","T&D Loss"]
        vals  =[R["rts_ann"],R["bess_settled_ann"],R["banked_ann"],
                R["lapsed_ann"],R["bank_loss_ann"],R["td_loss_ann"]]
        colors=["#2E7D32","#1F3864","#2E75B6","#E65100","#C62828","#BFBFBF"]
        fig=go.Figure(go.Pie(labels=labels,values=vals,hole=0.52,
                             marker_colors=colors,textinfo="label+percent",textfont_size=10))
        fig.update_layout(title="Injection Unit Trace",height=320,
                          legend=dict(orientation="h",y=-0.25),
                          margin=dict(t=30,b=10,l=5,r=5))
        st.plotly_chart(fig,use_container_width=True)

    with c2:
        pre =[R["mo"]["cons"][m]*R["pre_oa"]/1e5 for m in range(12)]
        re_c=[R["mo"]["settled"][m]*R["blended_landed"]/1e5 for m in range(12)]
        res =[max(0,R["mo"]["cons"][m]-R["mo"]["settled"][m])*R["pre_oa"]/1e5 for m in range(12)]
        fig2=go.Figure()
        fig2.add_bar(name="Pre-OA Grid",x=MABR,y=pre,marker_color="#C62828",opacity=0.7)
        fig2.add_bar(name="RE Cost",    x=MABR,y=re_c,marker_color="#2E7D32")
        fig2.add_bar(name="Residual Grid",x=MABR,y=res,marker_color="#2E75B6")
        fig2.update_layout(title="Monthly Cost Comparison (₹ Lakh)",barmode="group",
                           height=320,yaxis_title="₹ Lakh",
                           legend=dict(orientation="h",y=-0.25),
                           margin=dict(t=30,b=10,l=5,r=5))
        st.plotly_chart(fig2,use_container_width=True)

# ══════════ TAB 2: GENERATION & BANKING ═════════════════════════════════════
with tab2:
    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sec-title">Generation Summary</div>',unsafe_allow_html=True)
        gdf=pd.DataFrame({
            "Component":["Solar Gross","BESS Raw Charged","Solar Net (T&D)","BESS Injected","Total Net"],
            "MU/yr":[R["solar_gross_ann"]/1e6,R["bess_mwh"]*1000*365/1e6,
                     R["solar_net_ann"]/1e6,R["bess_ann"]/1e6,
                     (R["solar_net_ann"]+R["bess_ann"])/1e6],
        })
        st.dataframe(gdf.style.format({"MU/yr":"{:.3f}"}),use_container_width=True,hide_index=True)

    with c2:
        st.markdown('<div class="sec-title">Banking Audit</div>',unsafe_allow_html=True)
        bdf=pd.DataFrame({
            "Parameter":["Total Injection","RTS","BESS Settled","Banked",
                          "Lapsed","Banking Loss","Total Settled","Residual"],
            "MU/yr":[inj/1e6,R["rts_ann"]/1e6,R["bess_settled_ann"]/1e6,
                     R["banked_ann"]/1e6,R["lapsed_ann"]/1e6,R["bank_loss_ann"]/1e6,
                     R["total_settled_ann"]/1e6,R["residual_ann"]/1e6],
            "% of Inj":[100,R["rts_ann"]/inj*100,R["bess_settled_ann"]/inj*100,
                        R["banked_ann"]/inj*100,R["lapsed_ann"]/inj*100,
                        R["bank_loss_ann"]/inj*100,R["total_settled_ann"]/inj*100,
                        R["residual_ann"]/R["total_cons_ann"]*100],
        })
        st.dataframe(bdf.style.format({"MU/yr":"{:.3f}","% of Inj":"{:.2f}"}),
                     use_container_width=True,hide_index=True)

    # Monthly settlement breakdown chart
    st.markdown('<div class="sec-title">Month-on-Month Settlement Breakdown</div>',unsafe_allow_html=True)
    fig3=go.Figure()
    fig3.add_bar(name="Real-Time Settlement",x=MABR,y=R["mo"]["rts"],   marker_color="#2E7D32")
    fig3.add_bar(name="BESS Settlement",     x=MABR,y=R["mo"]["bess"],  marker_color="#1F3864")
    fig3.add_bar(name="Banking Settlement",  x=MABR,y=R["mo"]["banked"],marker_color="#2E75B6")
    fig3.add_scatter(name="Total Settled",   x=MABR,y=R["mo"]["settled"],
                     mode="lines+markers",line=dict(color="#2E7D32",width=2))
    fig3.update_layout(barmode="stack",title="Monthly: RTS + BESS + Banking Settlement (kWh)",
                       height=350,yaxis_title="kWh",
                       legend=dict(orientation="h",y=-0.2),
                       margin=dict(t=36,b=10,l=5,r=5))
    st.plotly_chart(fig3,use_container_width=True)

    # Lapsation month-on-month
    st.markdown('<div class="sec-title">Month-on-Month Lapsation</div>',unsafe_allow_html=True)
    fig_lapse=go.Figure()
    fig_lapse.add_bar(name="Lapsed Units",x=MABR,y=R["mo"]["lapsed"],
                      marker_color="#E65100",
                      text=[f"{v/1e3:.1f}k" if v>0 else "" for v in R["mo"]["lapsed"]],
                      textposition="outside")
    fig_lapse.add_scatter(name="Total Settled",x=MABR,y=R["mo"]["settled"],
                          mode="lines+markers",line=dict(color="#2E7D32",width=2),
                          yaxis="y2")
    fig_lapse.update_layout(
        title="Monthly Lapsation (kWh) vs Total Settled",
        height=320,
        yaxis=dict(title="Lapsed kWh",side="left"),
        yaxis2=dict(title="Settled kWh",side="right",overlaying="y"),
        legend=dict(orientation="h",y=-0.2),
        margin=dict(t=36,b=10,l=5,r=5)
    )
    st.plotly_chart(fig_lapse,use_container_width=True)

    # Gen vs consumption
    st.markdown('<div class="sec-title">Monthly Generation vs Consumption</div>',unsafe_allow_html=True)
    fig4=go.Figure()
    for slot,col in [("t4n","#1F3864"),("t4mp","#FFC000"),("t4op","#2E75B6"),("t4ep","#FF4444")]:
        name={"t4n":"Normal","t4mp":"Morning Peak","t4op":"Off-Peak","t4ep":"Evening Peak"}[slot]
        fig4.add_bar(name=name,x=MABR,y=R["mo"][slot],marker_color=col)
    fig4.add_scatter(name="Consumption",x=MABR,y=R["mo"]["cons"],
                     mode="lines+markers",line=dict(color="black",width=2,dash="dash"))
    fig4.update_layout(barmode="stack",height=320,yaxis_title="kWh",
                       legend=dict(orientation="h",y=-0.2),margin=dict(t=20,b=10,l=5,r=5))
    st.plotly_chart(fig4,use_container_width=True)

# ══════════ TAB 3: ToD ANALYSIS ═════════════════════════════════════════════
with tab3:
    st.markdown('<div class="sec-title">ToD Slot Analysis — Before vs After Open Access</div>',
                unsafe_allow_html=True)

    tod_labels     = ["TOD 1","TOD 2","TOD 3: Summer","TOD 3: Winter","TOD 4"]
    tod_slots_key  = ["Normal","Morning Peak","Off-Peak","Off-Peak","Evening Peak"]
    pre_cons_tod   = [R["total_cons_ann"]*SLOT_HRS[s]/24/1e6 for s in tod_slots_key]
    post_sett_tod  = [R["total_settled_ann"]*SLOT_HRS[s]/24/1e6 for s in tod_slots_key]
    pre_tariff_tod = [R["grid_tariff"][s] for s in tod_slots_key]
    post_tariff_tod= [R["blended_landed"] for _ in tod_slots_key]

    fig_tod = make_subplots(specs=[[{"secondary_y": True}]])
    fig_tod.add_bar(name="Before OA Consumption", x=tod_labels,
                    y=pre_cons_tod, marker_color="#1565C0", opacity=0.85,
                    secondary_y=False)
    fig_tod.add_bar(name="Post OA Settled Units", x=tod_labels,
                    y=post_sett_tod, marker_color="#E65100", opacity=0.85,
                    secondary_y=False)
    fig_tod.add_scatter(name="Before OA Tariff per Unit", x=tod_labels,
                        y=pre_tariff_tod, mode="lines+markers+text",
                        line=dict(color="white",width=2),
                        marker=dict(color="white",size=8),
                        text=[f"₹{v:.2f}" for v in pre_tariff_tod],
                        textposition="top center",textfont=dict(color="white",size=10),
                        secondary_y=True)
    fig_tod.add_scatter(name="Post OA Tariff per Unit", x=tod_labels,
                        y=post_tariff_tod, mode="lines+markers+text",
                        line=dict(color="#FFD700",width=2),
                        marker=dict(color="#FFD700",size=8),
                        text=[f"₹{v:.2f}" for v in post_tariff_tod],
                        textposition="bottom center",textfont=dict(color="#FFD700",size=10),
                        secondary_y=True)
    fig_tod.update_layout(
        title=dict(text="ToD Analysis — Consumption (MU) & Tariff (Rs/kWh)",
                   font=dict(color="white",size=14)),
        plot_bgcolor="#8B0000",paper_bgcolor="#8B0000",
        font=dict(color="white"),
        barmode="group", height=450,
        legend=dict(orientation="h",y=-0.15,font=dict(color="white")),
        margin=dict(t=50,b=20,l=10,r=10),
        xaxis=dict(gridcolor="#666",tickfont=dict(color="white")),
    )
    fig_tod.update_yaxes(title_text="Millions (MU)",secondary_y=False,
                         gridcolor="#666",tickfont=dict(color="white"))
    fig_tod.update_yaxes(title_text="₹/kWh",secondary_y=True,
                         gridcolor="#666",tickfont=dict(color="white"),
                         range=[3,16])
    st.plotly_chart(fig_tod,use_container_width=True)

    # ToD data table
    tod_df=pd.DataFrame({
        "ToD Slot":     tod_labels,
        "Before OA Cons (MU)":   [round(v,3) for v in pre_cons_tod],
        "Post OA Settled (MU)":  [round(v,3) for v in post_sett_tod],
        "Before OA Rs/kWh":      [round(v,3) for v in pre_tariff_tod],
        "Post OA Rs/kWh":        [round(v,3) for v in post_tariff_tod],
    })
    st.dataframe(tod_df,use_container_width=True,hide_index=True)

# ══════════ TAB 4: TARIFF & SAVINGS ══════════════════════════════════════════
with tab4:
    c1,c2=st.columns(2)
    with c1:
        st.markdown('<div class="sec-title">Grid Tariff (Post OA, excl ICR)</div>',unsafe_allow_html=True)
        tdf=pd.DataFrame({
            "ToD Slot":     list(R["grid_tariff"].keys()),
            "Rs/kWh":       [round(v,3) for v in R["grid_tariff"].values()],
            "Hours/Day":    [SLOT_HRS[s] for s in R["grid_tariff"]],
        })
        st.dataframe(tdf,use_container_width=True,hide_index=True)

        st.markdown('<div class="sec-title">RE Landed Cost</div>',unsafe_allow_html=True)
        redf=pd.DataFrame({
            "Component":["Solar Landed","BESS Landed","Blended Landed"],
            "Rs/kWh":[round(R["solar_landed"],3),round(R["bess_landed"],3),
                      round(R["blended_landed"],3)],
        })
        st.dataframe(redf,use_container_width=True,hide_index=True)

    with c2:
        st.markdown('<div class="sec-title">Savings Summary</div>',unsafe_allow_html=True)
        sdf=pd.DataFrame({
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
    st.markdown('<div class="sec-title">Savings Waterfall (Rs Crore)</div>',unsafe_allow_html=True)
    re_cr  = R["total_settled_ann"]*R["blended_landed"]/1e7
    res_cr = R["residual_ann"]*R["pre_oa"]/1e7
    fig5=go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute","relative","relative","total"],
        x=["Pre-OA Grid Cost","RE Power Cost","Residual Grid","Net Savings"],
        y=[R["pre_oa_cost_cr"],-re_cr,-res_cr,R["savings_cr"]],
        connector={"line":{"color":"#888"}},
        text=[f"₹{v:.2f}Cr" for v in [R["pre_oa_cost_cr"],-re_cr,-res_cr,R["savings_cr"]]],
        textposition="outside",
        increasing={"marker":{"color":"#2E7D32"}},
        decreasing={"marker":{"color":"#C62828"}},
        totals={"marker":{"color":"#1F3864"}},
    ))
    fig5.update_layout(height=340,yaxis_title="Rs Crore",
                       margin=dict(t=20,b=20,l=10,r=10))
    st.plotly_chart(fig5,use_container_width=True)

# ══════════ TAB 5: MONTHLY DETAIL ════════════════════════════════════════════
with tab5:
    st.markdown('<div class="sec-title">Month-wise Detail Table</div>',unsafe_allow_html=True)
    mdf=pd.DataFrame({
        "Month":         MABR,
        "Days":          DAYS,
        "Gen (kWh)":     [round(v) for v in R["mo"]["gen"]],
        "Consumption":   [round(v) for v in R["mo"]["cons"]],
        "RTS (kWh)":     [round(v) for v in R["mo"]["rts"]],
        "BESS Settled":  [round(v) for v in R["mo"]["bess"]],
        "Banked (kWh)":  [round(v) for v in R["mo"]["banked"]],
        "Total Settled": [round(v) for v in R["mo"]["settled"]],
        "Lapsed (kWh)":  [round(v) for v in R["mo"]["lapsed"]],
        "Displacement":  [f"{R['mo']['settled'][m]/max(R['mo']['cons'][m],1)*100:.1f}%"
                          for m in range(12)],
    })
    fmt={c:"{:,.0f}" for c in ["Gen (kWh)","Consumption","RTS (kWh)",
         "BESS Settled","Banked (kWh)","Total Settled","Lapsed (kWh)"]}
    st.dataframe(mdf.style.format(fmt),use_container_width=True,hide_index=True)
    csv=mdf.to_csv(index=False).encode()
    st.download_button("⬇️ Download CSV",csv,"rajasthan_oa_monthly.csv","text/csv")
    st.caption("Built by Sunsure Energy · Rajasthan InSTS Open Access · Pure Python")
