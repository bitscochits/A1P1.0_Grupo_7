#!/usr/bin/env python3
"""
ERROR DEMONSTRATION: Wrong Support Condition
Node 1 has its Z-restraint removed (free in vertical direction),
while all other supports remain fully fixed.
Compares correct vs wrong results under gravity load case G.
"""
import openseespy.opensees as ops
import math

# =============================================================================
# GEOMETRY DATA (from benchmark_3d.py)
# =============================================================================
X_axes = [8.02, 11.32, 14.72, 18.02, 28.02, 38.02, 48.02, 53.02]
Y_axes = [46.92, 50.26, 55.20, 60.20, 65.22, 72.75]
heights = [0.0, 4.0, 7.5, 11.0, 14.5, 18.0, 21.5, 25.0, 28.5]

nX = len(X_axes)
nY = len(Y_axes)
nLevels = len(heights)
nNodesPerFloor = nX * nY

# =============================================================================
# MATERIAL AND SECTION DATA
# =============================================================================
fpc = 28.0
Ec = 4700.0 * math.sqrt(fpc) * 1000.0
Gc = Ec / (2.0 * (1.0 + 0.2))

col_b, col_h = 0.50, 0.50
beamX_b, beamX_h = 0.30, 0.60
beamY_b, beamY_h = 0.30, 0.80
slab_t = 0.25
gamma = 25.0

A_col = col_b * col_h
Iy_col = col_b * col_h**3 / 12.0
Iz_col = col_h * col_b**3 / 12.0
J_col = min(Iy_col, Iz_col) * 0.3

A_beamX = beamX_b * beamX_h
Iy_beamX = beamX_b * beamX_h**3 / 12.0
Iz_beamX = beamX_h * beamX_b**3 / 12.0
J_beamX = min(Iy_beamX, Iz_beamX) * 0.3

A_beamY = beamY_b * beamY_h
Iy_beamY = beamY_b * beamY_h**3 / 12.0
Iz_beamY = beamY_h * beamY_b**3 / 12.0
J_beamY = min(Iy_beamY, Iz_beamY) * 0.3

w_slab_dead = gamma * slab_t + 1.5

# =============================================================================
# BUILD MODEL - CONFIGURABLE SUPPORT AT NODE 1
# =============================================================================
def build_model(free_node1_z=False):
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    ops.uniaxialMaterial('Elastic', 1, Ec)
    ops.geomTransf('Linear', 1, 1, 0, 0)
    ops.geomTransf('Linear', 2, 0, 0, 1)
    ops.geomTransf('Linear', 3, 0, 0, 1)

    nid = 1
    for lev in range(nLevels):
        z = heights[lev]
        for ix in range(nX):
            for iy in range(nY):
                ops.node(nid, X_axes[ix], Y_axes[iy], z)
                nid += 1

    for i in range(1, nNodesPerFloor + 1):
        if i == 1 and free_node1_z:
            ops.fix(i, 1, 1, 0, 1, 1, 1)  # free in Z only
        else:
            ops.fix(i, 1, 1, 1, 1, 1, 1)

    elem_counter = 1

    for lev in range(nLevels - 1):
        for ix in range(nX):
            for iy in range(nY):
                bot = lev * nNodesPerFloor + ix * nY + iy + 1
                top = (lev + 1) * nNodesPerFloor + ix * nY + iy + 1
                ops.element('elasticBeamColumn', elem_counter, bot, top,
                            A_col, Ec, Gc, J_col, Iy_col, Iz_col, 1)
                elem_counter += 1

    for lev in range(1, nLevels):
        for ix in range(nX - 1):
            for iy in range(nY):
                n1 = lev * nNodesPerFloor + ix * nY + iy + 1
                n2 = lev * nNodesPerFloor + (ix + 1) * nY + iy + 1
                ops.element('elasticBeamColumn', elem_counter, n1, n2,
                            A_beamX, Ec, Gc, J_beamX, Iy_beamX, Iz_beamX, 2)
                elem_counter += 1

    for lev in range(1, nLevels):
        for ix in range(nX):
            for iy in range(nY - 1):
                n1 = lev * nNodesPerFloor + ix * nY + iy + 1
                n2 = lev * nNodesPerFloor + ix * nY + (iy + 1) + 1
                ops.element('elasticBeamColumn', elem_counter, n1, n2,
                            A_beamY, Ec, Gc, J_beamY, Iy_beamY, Iz_beamY, 3)
                elem_counter += 1

    for lev in range(1, nLevels):
        master = lev * nNodesPerFloor + 1
        for ix in range(nX):
            for iy in range(nY):
                slave = lev * nNodesPerFloor + ix * nY + iy + 1
                if slave != master:
                    ops.equalDOF(master, slave, 1, 2, 6)


def apply_gravity():
    for lev in range(1, nLevels):
        for ix in range(nX - 1):
            dx = X_axes[ix + 1] - X_axes[ix]
            for iy in range(nY):
                if iy == 0:
                    tw = (Y_axes[1] - Y_axes[0]) / 2.0
                elif iy == nY - 1:
                    tw = (Y_axes[-1] - Y_axes[-2]) / 2.0
                else:
                    tw = (Y_axes[iy + 1] - Y_axes[iy - 1]) / 2.0
                w = w_slab_dead * tw * 0.5 + gamma * beamX_b * beamX_h
                n1 = lev * nNodesPerFloor + ix * nY + iy + 1
                n2 = lev * nNodesPerFloor + (ix + 1) * nY + iy + 1
                F = w * dx / 2.0
                ops.load(n1, 0.0, 0.0, -F, 0.0, 0.0, 0.0)
                ops.load(n2, 0.0, 0.0, -F, 0.0, 0.0, 0.0)

        for ix in range(nX):
            if ix == 0:
                tw = (X_axes[1] - X_axes[0]) / 2.0
            elif ix == nX - 1:
                tw = (X_axes[-1] - X_axes[-2]) / 2.0
            else:
                tw = (X_axes[ix + 1] - X_axes[ix - 1]) / 2.0
            for iy in range(nY - 1):
                dy = Y_axes[iy + 1] - Y_axes[iy]
                w = w_slab_dead * tw * 0.5 + gamma * beamY_b * beamY_h
                n1 = lev * nNodesPerFloor + ix * nY + iy + 1
                n2 = lev * nNodesPerFloor + ix * nY + (iy + 1) + 1
                F = w * dy / 2.0
                ops.load(n1, 0.0, 0.0, -F, 0.0, 0.0, 0.0)
                ops.load(n2, 0.0, 0.0, -F, 0.0, 0.0, 0.0)

    for lev in range(nLevels - 1):
        h = heights[lev + 1] - heights[lev]
        W = gamma * A_col * h
        for ix in range(nX):
            for iy in range(nY):
                n_bot = lev * nNodesPerFloor + ix * nY + iy + 1
                n_top = (lev + 1) * nNodesPerFloor + ix * nY + iy + 1
                ops.load(n_bot, 0.0, 0.0, -W / 2.0, 0.0, 0.0, 0.0)
                ops.load(n_top, 0.0, 0.0, -W / 2.0, 0.0, 0.0, 0.0)


def setup_analysis():
    ops.system('BandSPD')
    ops.numberer('RCM')
    ops.constraints('Plain')
    ops.integrator('LoadControl', 1.0)
    ops.algorithm('Linear')
    ops.analysis('Static')


def run_gravity(label, free_node1_z):
    ops.wipe()
    build_model(free_node1_z)
    setup_analysis()
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    apply_gravity()
    ok = ops.analyze(1)
    print(f"  {label}: Convergence {'OK' if ok == 0 else 'FAILED'}")
    ops.reactions()

    disp = {}
    for nid in range(1, nNodesPerFloor * nLevels + 1):
        disp[nid] = [ops.nodeDisp(nid, i) for i in range(1, 7)]

    support_nodes = list(range(1, nNodesPerFloor + 1))
    react = {}
    for nid in support_nodes:
        react[nid] = [ops.nodeReaction(nid, i) for i in range(1, 7)]

    return disp, react


# ============================================================================
print("=" * 80)
print("ERROR DEMONSTRATION: WRONG SUPPORT CONDITION")
print("Node 1 Z-restraint removed (free to move vertically)")
print("=" * 80)
print(f"\nNode 1 is at coordinates ({X_axes[0]:.2f}, {Y_axes[0]:.2f}, 0.0)")
print("Correct: Node 1 fully fixed (UX=UY=UZ=0)")
print("Wrong:   Node 1 free in Z direction (UX=UY=0, UZ free)")

print("\n--- Running CORRECT model (all supports fixed) ---")
disp_c, react_c = run_gravity("Correct (all fixed)", free_node1_z=False)

print("\n--- Running WRONG model (node 1 free in Z) ---")
disp_w, react_w = run_gravity("WRONG (node 1 free Z)", free_node1_z=True)

support_nodes = list(range(1, nNodesPerFloor + 1))

# ============================================================================
# DISPLACEMENT AT NODE 1
# ============================================================================
print("\n" + "=" * 80)
print("DISPLACEMENT AT NODE 1 (the modified support)")
print("=" * 80)
print(f"\n{'DOF':<10} {'Correct [m]':>16} {'Wrong [m]':>16} {'Difference':>16}")
print("-" * 60)
dof_labels = ["UX", "UY", "UZ", "RX", "RY", "RZ"]
for i in range(6):
    vc = disp_c[1][i]
    vw = disp_w[1][i]
    print(f"{dof_labels[i]:<10} {vc:>16.8f} {vw:>16.8f} {vw-vc:>+16.8f}")

# All support node Z-displacements
print("\n--- All Support Node Z-Displacements ---")
print(f"{'Node':<8} {'Correct UZ [m]':>16} {'Wrong UZ [m]':>16} {'Difference':>16}")
print("-" * 58)
for n in support_nodes:
    vc = disp_c[n][2]
    vw = disp_w[n][2]
    flag = " <-- modified" if n == 1 else ""
    print(f"{n:<8} {vc:>16.10f} {vw:>16.10f} {vw-vc:>+16.10f}{flag}")

# ============================================================================
# MAX DISPLACEMENTS OVERALL
# ============================================================================
max_uz_c = max(abs(d[2]) for nid, d in disp_c.items())
max_uz_w = max(abs(d[2]) for nid, d in disp_w.items())

print("\n" + "=" * 80)
print("MAXIMUM VERTICAL DISPLACEMENT OVER ALL NODES")
print("=" * 80)
print(f"  Correct: {max_uz_c:.8f} m")
print(f"  Wrong:   {max_uz_w:.8f} m")
if max_uz_c > 1e-12:
    print(f"  Change:  {(max_uz_w/max_uz_c-1)*100:+.2f}%")
else:
    print(f"  Change:  {max_uz_w - max_uz_c:+.10f} m (new nonzero displacement)")

# ============================================================================
# REACTIONS
# ============================================================================
print("\n" + "=" * 80)
print("SUPPORT REACTIONS")
print("=" * 80)

sum_Rx_c = sum(react_c[n][0] for n in support_nodes)
sum_Ry_c = sum(react_c[n][1] for n in support_nodes)
sum_Rz_c = sum(react_c[n][2] for n in support_nodes)

sum_Rx_w = sum(react_w[n][0] for n in support_nodes)
sum_Ry_w = sum(react_w[n][1] for n in support_nodes)
sum_Rz_w = sum(react_w[n][2] for n in support_nodes)

print(f"\n{'Reaction':<20} {'Correct [kN]':>16} {'Wrong [kN]':>16} {'Difference':>16} {'Rel.%':>10}")
print("-" * 79)
for lbl, vc, vw in [("Sum Rx", sum_Rx_c, sum_Rx_w),
                     ("Sum Ry", sum_Ry_c, sum_Ry_w),
                     ("Sum Rz", sum_Rz_c, sum_Rz_w)]:
    if abs(vc) > 1e-6:
        rel = (vw / vc - 1) * 100
    else:
        rel = 0.0
    print(f"{lbl:<20} {vc:>16.4f} {vw:>16.4f} {vw-vc:>+16.4f} {rel:>+9.4f}%")

print(f"\n--- Individual Support Reactions (Rz) ---")
print(f"{'Node':<8} {'Correct [kN]':>16} {'Wrong [kN]':>16} {'Difference':>16}")
print("-" * 58)
for n in support_nodes:
    rc = react_c[n][2]
    rw = react_w[n][2]
    flag = " <-- modified" if n == 1 else ""
    print(f"{n:<8} {rc:>16.4f} {rw:>16.4f} {rw-rc:>+16.4f}{flag}")

# Sum of reactions EXCLUDING node 1
sum_Rz_excl1_c = sum(react_c[n][2] for n in support_nodes if n != 1)
sum_Rz_excl1_w = sum(react_w[n][2] for n in support_nodes if n != 1)

print(f"\n--- Summary ---")
print(f"  Rz at node 1 (correct): {react_c[1][2]:>14.4f} kN")
print(f"  Rz at node 1 (wrong):   {react_w[1][2]:>14.4f} kN  (should be ~0)")
print(f"  Sum Rz all supports (correct):  {sum_Rz_c:>14.4f} kN")
print(f"  Sum Rz all supports (wrong):    {sum_Rz_w:>14.4f} kN")
print(f"  Sum Rz excl. node 1 (correct):  {sum_Rz_excl1_c:>14.4f} kN")
print(f"  Sum Rz excl. node 1 (wrong):    {sum_Rz_excl1_w:>14.4f} kN")

# ============================================================================
print("\n" + "=" * 80)
print("DETECTION ANALYSIS")
print("=" * 80)
print(f"""
1. NODE 1 VERTICAL DISPLACEMENT:
   Correct: UZ at node 1 = {disp_c[1][2]:.10f} m (zero, as expected)
   Wrong:   UZ at node 1 = {disp_w[1][2]:.10f} m (NONZERO - support settlement!)
   -> This is IMMEDIATELY DETECTABLE: a support should have zero
      displacement. A nonzero value indicates a missing restraint.

2. REACTION AT NODE 1:
   Correct: Rz = {react_c[1][2]:.4f} kN (carries load)
   Wrong:   Rz = {react_w[1][2]:.4f} kN (zero - no restraint = no reaction)
   -> A zero reaction at a support node that should carry load
      is a CLEAR INDICATOR of a missing fixity.

3. TOTAL EQUILIBRIUM:
   Sum Rz (correct): {sum_Rz_c:.4f} kN
   Sum Rz (wrong):   {sum_Rz_w:.4f} kN
   Difference:       {abs(sum_Rz_w - sum_Rz_c):.4f} kN
   -> The remaining supports carry EXTRA load to compensate.
      Total equilibrium is still satisfied, but the LOAD REDISTRIBUTION
      is wrong.

4. GLOBAL DISPLACEMENTS:
   Max |UZ| (correct): {max_uz_c:.8f} m
   Max |UZ| (wrong):   {max_uz_w:.8f} m
   -> Slightly different due to changed load path.

DETECTION METHODS:
  * CHECK EACH SUPPORT: reaction should be nonzero and displacement zero.
  * CHECK EQUILIBRIUM: reactions must balance applied loads.
  * CHECK SYMMETRY: asymmetric reactions for a symmetric structure
    suggest an error.
  * A support with zero reaction but nonzero applied load nearby
    is a red flag.
""")
print("Done!")
