#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificacion Semana 1 - corrige Problemas A y B del informe.

B) Fuerzas LOCALES correctas con ops.eleResponse(tag,'localForce')
   (el informe usaba ops.eleForce = ejes GLOBALES, mal etiquetado).

A) Tabla de verificacion con REFERENCIA independiente:
   - carga total de gravedad calculada a mano vs suma de reacciones
   - chequeo analitico de voladizo  delta = P L^3 / (3 E I)
"""
import openseespy.opensees as ops
import math

# ============================================================
# Datos geometricos y de material (identicos a extract_elements.py)
# ============================================================
X_axes = [8.02, 11.32, 14.72, 18.02, 28.02, 38.02, 48.02, 53.02]
Y_axes = [46.92, 50.26, 55.20, 60.20, 65.22, 72.75]
heights = [0.0, 4.0, 7.5, 11.0, 14.5, 18.0, 21.5, 25.0, 28.5]

nX = len(X_axes); nY = len(Y_axes); nLevels = len(heights)
nNodesPerFloor = nX * nY

fpc = 28.0
Ec = 4700.0 * math.sqrt(fpc) * 1000.0
Gc = Ec / (2.0 * (1.0 + 0.2))

col_b, col_h = 0.50, 0.50
beamX_b, beamX_h = 0.30, 0.60
beamY_b, beamY_h = 0.30, 0.80
slab_t = 0.25
gamma = 25.0

A_col = col_b*col_h
Iy_col = col_b*col_h**3/12.0; Iz_col = col_h*col_b**3/12.0
J_col = min(Iy_col, Iz_col)*0.3
A_beamX = beamX_b*beamX_h
Iy_beamX = beamX_b*beamX_h**3/12.0; Iz_beamX = beamX_h*beamX_b**3/12.0
J_beamX = min(Iy_beamX, Iz_beamX)*0.3
A_beamY = beamY_b*beamY_h
Iy_beamY = beamY_b*beamY_h**3/12.0; Iz_beamY = beamY_h*beamY_b**3/12.0
J_beamY = min(Iy_beamY, Iz_beamY)*0.3

w_slab_dead = gamma*slab_t + 1.5   # 7.75 kN/m2


def build_model():
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    ops.uniaxialMaterial('Elastic', 1, Ec)
    ops.geomTransf('Linear', 1, 1, 0, 0)
    ops.geomTransf('Linear', 2, 0, 0, 1)
    ops.geomTransf('Linear', 3, 0, 0, 1)
    node_coords = {}
    nid = 1
    for lev in range(nLevels):
        z = heights[lev]
        for ix in range(nX):
            for iy in range(nY):
                node_coords[nid] = (X_axes[ix], Y_axes[iy], z)
                ops.node(nid, X_axes[ix], Y_axes[iy], z)
                nid += 1
    for i in range(1, nNodesPerFloor+1):
        ops.fix(i, 1, 1, 1, 1, 1, 1)
    ec = 1
    col_list, xbeam_list, ybeam_list = [], [], []
    for lev in range(nLevels-1):
        for ix in range(nX):
            for iy in range(nY):
                bot = lev*nNodesPerFloor + ix*nY + iy + 1
                top = (lev+1)*nNodesPerFloor + ix*nY + iy + 1
                ops.element('elasticBeamColumn', ec, bot, top,
                            A_col, Ec, Gc, J_col, Iy_col, Iz_col, 1)
                col_list.append(ec); ec += 1
    for lev in range(1, nLevels):
        for ix in range(nX-1):
            for iy in range(nY):
                n1 = lev*nNodesPerFloor + ix*nY + iy + 1
                n2 = lev*nNodesPerFloor + (ix+1)*nY + iy + 1
                ops.element('elasticBeamColumn', ec, n1, n2,
                            A_beamX, Ec, Gc, J_beamX, Iy_beamX, Iz_beamX, 2)
                xbeam_list.append(ec); ec += 1
    for lev in range(1, nLevels):
        for ix in range(nX):
            for iy in range(nY-1):
                n1 = lev*nNodesPerFloor + ix*nY + iy + 1
                n2 = lev*nNodesPerFloor + ix*nY + (iy+1) + 1
                ops.element('elasticBeamColumn', ec, n1, n2,
                            A_beamY, Ec, Gc, J_beamY, Iy_beamY, Iz_beamY, 3)
                ybeam_list.append(ec); ec += 1
    for lev in range(1, nLevels):
        master = lev*nNodesPerFloor + 1
        for ix in range(nX):
            for iy in range(nY):
                slave = lev*nNodesPerFloor + ix*nY + iy + 1
                if slave != master:
                    ops.equalDOF(master, slave, 1, 2, 6)
    return node_coords, col_list, xbeam_list, ybeam_list


def apply_gravity():
    """Carga G: losa+terminaciones por areas tributarias + peso propio."""
    for lev in range(1, nLevels):
        for ix in range(nX-1):
            dx = X_axes[ix+1]-X_axes[ix]
            for iy in range(nY):
                if iy == 0:
                    tw = (Y_axes[1]-Y_axes[0])/2.0
                elif iy == nY-1:
                    tw = (Y_axes[-1]-Y_axes[-2])/2.0
                else:
                    tw = (Y_axes[iy+1]-Y_axes[iy-1])/2.0
                w = w_slab_dead*tw*0.5 + gamma*beamX_b*beamX_h
                n1 = lev*nNodesPerFloor + ix*nY + iy + 1
                n2 = lev*nNodesPerFloor + (ix+1)*nY + iy + 1
                F = w*dx/2.0
                ops.load(n1, 0., 0., -F, 0., 0., 0.)
                ops.load(n2, 0., 0., -F, 0., 0., 0.)
        for ix in range(nX):
            if ix == 0:
                tw = (X_axes[1]-X_axes[0])/2.0
            elif ix == nX-1:
                tw = (X_axes[-1]-X_axes[-2])/2.0
            else:
                tw = (X_axes[ix+1]-X_axes[ix-1])/2.0
            for iy in range(nY-1):
                dy = Y_axes[iy+1]-Y_axes[iy]
                w = w_slab_dead*tw*0.5 + gamma*beamY_b*beamY_h
                n1 = lev*nNodesPerFloor + ix*nY + iy + 1
                n2 = lev*nNodesPerFloor + ix*nY + (iy+1) + 1
                F = w*dy/2.0
                ops.load(n1, 0., 0., -F, 0., 0., 0.)
                ops.load(n2, 0., 0., -F, 0., 0., 0.)
    for lev in range(nLevels-1):
        h = heights[lev+1]-heights[lev]
        W = gamma*A_col*h
        for ix in range(nX):
            for iy in range(nY):
                n_bot = lev*nNodesPerFloor + ix*nY + iy + 1
                n_top = (lev+1)*nNodesPerFloor + ix*nY + iy + 1
                ops.load(n_bot, 0., 0., -W/2.0, 0., 0., 0.)
                ops.load(n_top, 0., 0., -W/2.0, 0., 0., 0.)


def setup():
    ops.system('BandGeneral'); ops.numberer('RCM')
    ops.constraints('Transformation')   # correcto con equalDOF (MP constraints)
    ops.integrator('LoadControl', 1.0)
    ops.algorithm('Linear'); ops.analysis('Static')


# ============================================================
# CORRIDA G
# ============================================================
node_coords, col_list, xbeam_list, ybeam_list = build_model()
setup()
ops.timeSeries('Linear', 1); ops.pattern('Plain', 1, 1)
apply_gravity()
ok = ops.analyze(1); ops.reactions()
print("Convergencia G:", "OK" if ok == 0 else "FALLO")

col_tag, xbeam_tag, ybeam_tag = col_list[0], xbeam_list[0], ybeam_list[0]

print("\n===== B) FUERZAS LOCALES CORRECTAS (eleResponse localForce) =====")
etiquetas = "N Vy Vz T My Mz".split()
for label, tag in [("Columna", col_tag), ("Viga X", xbeam_tag), ("Viga Y", ybeam_tag)]:
    ni, nj = ops.eleNodes(tag)
    lf = ops.eleResponse(tag, 'localForce')
    gf = ops.eleForce(tag)   # para comparar: lo que uso el informe (GLOBAL)
    print(f"\n--- {label} (tag {tag})  nodos {ni}->{nj} ---")
    print("  LOCAL  i:", " ".join(f"{e}={lf[k]:+10.3f}" for k, e in enumerate(etiquetas)))
    print("  LOCAL  j:", " ".join(f"{e}={lf[6+k]:+10.3f}" for k, e in enumerate(etiquetas)))
    print("  (GLOBAL eleForce i, lo que decia el informe):",
          " ".join(f"{gf[k]:+9.3f}" for k in range(6)))

# ============================================================
# A) Referencia independiente 1: carga total de gravedad a mano
# ============================================================
print("\n===== A1) CARGA TOTAL G: referencia a mano vs OpenSees =====")
area_planta = (X_axes[-1]-X_axes[0]) * (Y_axes[-1]-Y_axes[0])
n_pisos_cargados = nLevels - 1
W_losa = w_slab_dead * area_planta * n_pisos_cargados
# peso propio vigas
L_vigas_x = sum((X_axes[ix+1]-X_axes[ix]) for ix in range(nX-1)) * nY * n_pisos_cargados
L_vigas_y = sum((Y_axes[iy+1]-Y_axes[iy]) for iy in range(nY-1)) * nX * n_pisos_cargados
W_vig = gamma*beamX_b*beamX_h*L_vigas_x + gamma*beamY_b*beamY_h*L_vigas_y
# peso propio columnas
L_col = sum((heights[l+1]-heights[l]) for l in range(nLevels-1)) * nNodesPerFloor
W_col = gamma*A_col*L_col
W_mano = W_losa + W_vig + W_col
sumRz = sum(ops.nodeReaction(n, 3) for n in range(1, nNodesPerFloor+1))
err = abs(W_mano - sumRz)/W_mano*100
print(f"  Losa+term (7.75 x {area_planta:.1f} m2 x {n_pisos_cargados}): {W_losa:12.2f} kN")
print(f"  Peso propio vigas:                                {W_vig:12.2f} kN")
print(f"  Peso propio columnas:                             {W_col:12.2f} kN")
print(f"  REFERENCIA (mano) total:                          {W_mano:12.2f} kN")
print(f"  OpenSees  sum(Rz):                                {sumRz:12.2f} kN")
print(f"  Error:                                            {err:12.4f} %")

# ============================================================
# A) Referencia independiente 2: voladizo analitico  delta=PL^3/3EI
# ============================================================
print("\n===== A2) VOLADIZO ANALITICO: delta = P L^3 / (3 E I) =====")
ops.wipe()
ops.model('basic', '-ndm', 3, '-ndf', 6)
L = 3.0; P = 10.0
b, h = 0.30, 0.50
A = b*h; Iy = b*h**3/12.0; Iz = h*b**3/12.0
E = 25.0e6; G = E/(2*(1+0.2)); J = 0.002
ops.node(1, 0., 0., 0.); ops.node(2, L, 0., 0.)
ops.fix(1, 1, 1, 1, 1, 1, 1)
ops.geomTransf('Linear', 1, 0, 0, 1)
ops.element('elasticBeamColumn', 1, 1, 2, A, E, G, J, Iy, Iz, 1)
ops.timeSeries('Linear', 1); ops.pattern('Plain', 1, 1)
ops.load(2, 0., 0., -P, 0., 0., 0.)
ops.system('BandSPD'); ops.numberer('RCM'); ops.constraints('Plain')
ops.integrator('LoadControl', 1.0); ops.algorithm('Linear'); ops.analysis('Static')
ops.analyze(1)
uz = ops.nodeDisp(2, 3)
delta_ref = -P*L**3/(3*E*Iy)
err2 = abs(uz-delta_ref)/abs(delta_ref)*100
print(f"  Referencia PL^3/3EI: {delta_ref*1000:+.6f} mm")
print(f"  OpenSees nodeDisp:   {uz*1000:+.6f} mm")
print(f"  Error:               {err2:.2e} %")
print("\nDONE")
