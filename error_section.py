#!/usr/bin/env python3
"""
ERROR DEMONSTRATION: Wrong Column Section
Columns use Iy and Iz multiplied by 10 (50x50cm section treated as 10x stiffer).
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
# BUILD MODEL WITH CONFIGURABLE COLUMN STIFFNESS
# =============================================================================
def build_model(col_Iy_mult=1.0):
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
        ops.fix(i, 1, 1, 1, 1, 1, 1)

    cIy = Iy_col * col_Iy_mult
    cIz = Iz_col * col_Iy_mult
    elem_counter = 1

    for lev in range(nLevels - 1):
        for ix in range(nX):
            for iy in range(nY):
                bot = lev * nNodesPerFloor + ix * nY + iy + 1
                top = (lev + 1) * nNodesPerFloor + ix * nY + iy + 1
                ops.element('elasticBeamColumn', elem_counter, bot, top,
                            A_col, Ec, Gc, J_col, cIy, cIz, 1)
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


def run_gravity(label, col_Iy_mult):
    ops.wipe()
    build_model(col_Iy_mult)
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
print("ERROR DEMONSTRATION: WRONG COLUMN SECTION (Iy, Iz x 10)")
print("=" * 80)
print(f"\nCorrect column: {col_b*100:.0f}x{col_h*100:.0f} cm")
print(f"  Iy = {Iy_col:.6f} m4,  Iz = {Iz_col:.6f} m4")
print(f"WRONG column: same 50x50 cm dimensions but Iy and Iz multiplied by 10")
print(f"  Wrong Iy = {Iy_col*10:.6f} m4,  Wrong Iz = {Iz_col*10:.6f} m4")

print("\n--- Running CORRECT model ---")
disp_c, react_c = run_gravity("Correct (x1)", col_Iy_mult=1.0)

print("\n--- Running WRONG model (columns 10x stiffer) ---")
disp_w, react_w = run_gravity("WRONG  (x10)", col_Iy_mult=10.0)

support_nodes = list(range(1, nNodesPerFloor + 1))

# ============================================================================
# MAX DISPLACEMENTS
# ============================================================================
max_uz_c = max(abs(d[2]) for nid, d in disp_c.items() if nid not in support_nodes)
max_uz_w = max(abs(d[2]) for nid, d in disp_w.items() if nid not in support_nodes)

max_ux_c = max(abs(d[0]) for nid, d in disp_c.items() if nid not in support_nodes)
max_ux_w = max(abs(d[0]) for nid, d in disp_w.items() if nid not in support_nodes)

max_uy_c = max(abs(d[1]) for nid, d in disp_c.items() if nid not in support_nodes)
max_uy_w = max(abs(d[1]) for nid, d in disp_w.items() if nid not in support_nodes)

print("\n" + "=" * 80)
print("COMPARISON: MAXIMUM DISPLACEMENTS (Load Case G)")
print("=" * 80)
print(f"\n{'Quantity':<35} {'Correct':>14} {'Wrong (x10)':>14} {'Difference':>14} {'Rel.%':>10}")
print("-" * 89)
for lbl, vc, vw in [("Max |UZ| non-support [m]", max_uz_c, max_uz_w),
                     ("Max |UX| non-support [m]", max_ux_c, max_ux_w),
                     ("Max |UY| non-support [m]", max_uy_c, max_uy_w)]:
    rel = (vw / vc - 1) * 100 if abs(vc) > 1e-12 else 0
    print(f"{lbl:<35} {vc:>14.8f} {vw:>14.8f} {vw-vc:>+14.8f} {rel:>+9.2f}%")

# Top floor Z displacements at center node
top_center = (nLevels - 1) * nNodesPerFloor + (nX // 2) * nY + (nY // 2) + 1
uz_c = disp_c[top_center][2]
uz_w = disp_w[top_center][2]
print(f"\n  Top-floor center node (#{top_center}):")
print(f"    UZ correct = {uz_c:.8f} m")
print(f"    UZ wrong   = {uz_w:.8f} m")
print(f"    Difference = {uz_w - uz_c:+.8f} m  ({(uz_w/uz_c-1)*100:+.2f}%)")

# ============================================================================
# REACTIONS
# ============================================================================
sum_Rx_c = sum(react_c[n][0] for n in support_nodes)
sum_Ry_c = sum(react_c[n][1] for n in support_nodes)
sum_Rz_c = sum(react_c[n][2] for n in support_nodes)

sum_Rx_w = sum(react_w[n][0] for n in support_nodes)
sum_Ry_w = sum(react_w[n][1] for n in support_nodes)
sum_Rz_w = sum(react_w[n][2] for n in support_nodes)

print("\n" + "=" * 80)
print("COMPARISON: TOTAL SUPPORT REACTIONS (Load Case G)")
print("=" * 80)
print(f"\n{'Reaction':<20} {'Correct [kN]':>16} {'Wrong [kN]':>16} {'Difference':>16} {'Rel.%':>10}")
print("-" * 79)
for lbl, vc, vw in [("Sum Rx", sum_Rx_c, sum_Rx_w),
                     ("Sum Ry", sum_Ry_c, sum_Ry_w),
                     ("Sum Rz", sum_Rz_c, sum_Rz_w)]:
    rel = (vw / vc - 1) * 100 if abs(vc) > 1e-6 else 0
    print(f"{lbl:<20} {vc:>16.4f} {vw:>16.4f} {vw-vc:>+16.4f} {rel:>+9.4f}%")

print("\n--- Individual Support Rz (representative nodes) ---")
print(f"{'Node':<8} {'Correct [kN]':>16} {'Wrong [kN]':>16} {'Difference':>16} {'Rel.%':>10}")
print("-" * 67)
sample = [1, 2, nY, nY + 1, nNodesPerFloor // 2, nNodesPerFloor]
for n in sample:
    rc, rw = react_c[n][2], react_w[n][2]
    rel = (rw / rc - 1) * 100 if abs(rc) > 1e-6 else 0
    print(f"{n:<8} {rc:>16.4f} {rw:>16.4f} {rw-rc:>+16.4f} {rel:>+9.4f}%")

# ============================================================================
print("\n" + "=" * 80)
print("DETECTION ANALYSIS")
print("=" * 80)
print(f"""
1. DISPLACEMENTS:
   Correct max |UZ| = {max_uz_c:.8f} m
   Wrong   max |UZ| = {max_uz_w:.8f} m
   Relative change  = {(max_uz_w/max_uz_c-1)*100:+.2f}%
   -> Stiffer columns REDUCE displacements. This is DETECTABLE:
      if displacements are smaller than expected, section properties
      may be overestimated.

2. TOTAL REACTIONS (sum Rz):
   Correct = {sum_Rz_c:.4f} kN,  Wrong = {sum_Rz_w:.4f} kN
   Difference = {abs(sum_Rz_w - sum_Rz_c):.6f} kN
   -> Total vertical reaction is UNCHANGED because gravity equilibrium
      must always be satisfied. This means checking ONLY total reaction
      is NOT sufficient to detect the error.

3. INDIVIDUAL REACTIONS:
   The distribution of reactions among supports CHANGES because
   the relative stiffness between columns and beams changes.
   -> Comparing individual support reactions can help detect section errors.

CONCLUSION: Check displacements AND individual reaction distributions
to detect wrong section properties. Total reaction equilibrium alone
is not enough.
""")
print("Done!")
