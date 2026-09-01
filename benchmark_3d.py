#!/usr/bin/env python3
"""
3D OpenSeesPy Model: Edificio de Ingenieria - Universidad de los Andes
Benchmark structural model for computational methods course.
"""

import openseespy.opensees as ops
import json
import math
import os

# Fisica compartida con el benchmark de la Semana 1: una sola
# definicion de la torsion y del reparto tributario para todo el
# proyecto. Antes cada archivo tenia su propia copia y divergian.
import modelo_benchmark as mb

# =============================================================================
# GEOMETRY DATA
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
Ec = 4700.0 * math.sqrt(fpc) * 1000.0  # Convert MPa -> kPa for m/kN units
Gc = Ec / (2.0 * (1.0 + 0.2))

col_b, col_h = 0.50, 0.50
beamX_b, beamX_h = 0.30, 0.60
beamY_b, beamY_h = 0.30, 0.80
slab_t = 0.25
gamma = 25.0

A_col = col_b * col_h
Iy_col = col_b * col_h**3 / 12.0
Iz_col = col_h * col_b**3 / 12.0
# Saint-Venant, no el min(Iy,Iz)*0.3 de antes: esa expresion no
# corresponde a ninguna formula y subestimaba J entre 5.6 y 10.2 veces.
# En un edificio de 9 niveles con planta irregular y sismo EX/EY la
# rigidez torsional si carga las columnas.
J_col = mb.J_rectangular(col_b, col_h)

A_beamX = beamX_b * beamX_h
Iy_beamX = beamX_b * beamX_h**3 / 12.0
Iz_beamX = beamX_h * beamX_b**3 / 12.0
J_beamX = mb.J_rectangular(beamX_b, beamX_h)

A_beamY = beamY_b * beamY_h
Iy_beamY = beamY_b * beamY_h**3 / 12.0
Iz_beamY = beamY_h * beamY_b**3 / 12.0
J_beamY = mb.J_rectangular(beamY_b, beamY_h)

w_slab_dead = gamma * slab_t + 1.5  # 7.75 kN/m2
w_live_val = 2.0


# Mapas de vigas por posicion en la grilla, llenados por build_model().
XBEAM = {}   # (nivel, ix, iy) -> viga en X entre los ejes ix e ix+1
YBEAM = {}   # (nivel, ix, iy) -> viga en Y entre los ejes iy e iy+1


def build_model():
    """Build the full model: nodes, elements, constraints, analysis settings."""
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)

    # Material
    ops.uniaxialMaterial('Elastic', 1, Ec)

    # Geometric transformations
    ops.geomTransf('Linear', 1, 1, 0, 0)
    ops.geomTransf('Linear', 2, 0, 0, 1)
    ops.geomTransf('Linear', 3, 0, 0, 1)

    # Nodes
    node_coords = {}
    nid = 1
    for lev in range(nLevels):
        z = heights[lev]
        for ix in range(nX):
            for iy in range(nY):
                node_coords[nid] = (X_axes[ix], Y_axes[iy], z)
                ops.node(nid, X_axes[ix], Y_axes[iy], z)
                nid += 1

    # Fixed supports at level 0
    for i in range(1, nNodesPerFloor + 1):
        ops.fix(i, 1, 1, 1, 1, 1, 1)

    # Elements
    elem_counter = 1
    col_list = []
    xbeam_list = []
    ybeam_list = []
    # Mapas (nivel, ix, iy) -> tag. Sin esto no se puede saber que
    # elemento borda cada pano de losa al repartir la carga.
    XBEAM.clear()
    YBEAM.clear()

    # Columns
    for lev in range(nLevels - 1):
        for ix in range(nX):
            for iy in range(nY):
                bot = lev * nNodesPerFloor + ix * nY + iy + 1
                top = (lev + 1) * nNodesPerFloor + ix * nY + iy + 1
                ops.element('elasticBeamColumn', elem_counter, bot, top,
                            A_col, Ec, Gc, J_col, Iy_col, Iz_col, 1)
                col_list.append(elem_counter)
                elem_counter += 1

    # X-beams
    for lev in range(1, nLevels):
        for ix in range(nX - 1):
            for iy in range(nY):
                n1 = lev * nNodesPerFloor + ix * nY + iy + 1
                n2 = lev * nNodesPerFloor + (ix + 1) * nY + iy + 1
                ops.element('elasticBeamColumn', elem_counter, n1, n2,
                            A_beamX, Ec, Gc, J_beamX, Iy_beamX, Iz_beamX, 2)
                XBEAM[(lev, ix, iy)] = elem_counter
                xbeam_list.append(elem_counter)
                elem_counter += 1

    # Y-beams
    for lev in range(1, nLevels):
        for ix in range(nX):
            for iy in range(nY - 1):
                n1 = lev * nNodesPerFloor + ix * nY + iy + 1
                n2 = lev * nNodesPerFloor + ix * nY + (iy + 1) + 1
                ops.element('elasticBeamColumn', elem_counter, n1, n2,
                            A_beamY, Ec, Gc, J_beamY, Iy_beamY, Iz_beamY, 3)
                YBEAM[(lev, ix, iy)] = elem_counter
                ybeam_list.append(elem_counter)
                elem_counter += 1

    # -------------------------------------------------------------
    # DIAFRAGMAS RIGIDOS
    # -------------------------------------------------------------
    # Antes esto era:
    #     ops.equalDOF(master, slave, 1, 2, 6)
    # que NO es un diafragma: obliga a que todos los nodos tengan el
    # MISMO ux, uy y rz, o sea que el piso solo puede trasladarse y
    # nunca rotar. En una planta irregular bajo sismo la torsion es
    # justo lo que hay que capturar, y quedaba eliminada.
    #
    # Un diafragma rigido deja el piso moverse como CUERPO RIGIDO en su
    # plano, rotacion incluida:
    #     ux_i = ux_m - rz*(y_i - y_m)
    #     uy_i = uy_m + rz*(x_i - x_m)
    #     rz_i = rz_m           <- esto si es comun a todos
    #
    # El nodo maestro va en el CENTRO GEOMETRICO del piso, que es donde
    # se aplica el corte sismico. Necesita constraints('Transformation').
    xc = sum(X_axes) / nX
    yc = sum(Y_axes) / nY
    master_nodes = {}
    mid = nLevels * nNodesPerFloor + 1

    for lev in range(1, nLevels):
        ops.node(mid, xc, yc, heights[lev])
        node_coords[mid] = (xc, yc, heights[lev])
        master_nodes[lev] = mid

        esclavos = [lev * nNodesPerFloor + ix * nY + iy + 1
                    for ix in range(nX) for iy in range(nY)]
        ops.rigidDiaphragm(3, mid, *esclavos)

        # El diafragma solo ata los DOF EN el plano (ux, uy, rz). Los de
        # fuera (uz, rx, ry) del maestro quedan sueltos y la matriz
        # saldria singular, porque el nodo no tiene ningun elemento.
        ops.fix(mid, 0, 0, 1, 1, 1, 0)
        mid += 1

    return node_coords, col_list, xbeam_list, ybeam_list, master_nodes


def tributarias():
    """
    Reparte cada pano de losa a las 4 vigas que lo bordean, trazando
    bisectrices a 45 grados desde las esquinas.

        pano corto (b <= a)  -> la viga larga recibe un TRAPECIO
        pano largo  (b >  a) -> la viga corta recibe un TRIANGULO

    Una viga interior borda DOS panos, asi que acumula las dos
    contribuciones. Iterando por pano y sumando sus 4 aportes, la
    conservacion queda garantizada por construccion:
        sum(A_tributaria) == A_piso  por nivel

    Antes el reparto era 50/50 por franjas de media luz, que le da lo
    mismo a la viga larga que a la corta. En un pano 10x5 eso puede
    equivocar la carga de cada viga en decenas de por ciento.

    Devuelve (area_por_viga, A_piso, detalle_panos).
    """
    area_por_viga = {}
    A_piso = 0.0
    detalle = []

    for ix in range(nX - 1):
        Lx = X_axes[ix + 1] - X_axes[ix]
        for iy in range(nY - 1):
            Ly = Y_axes[iy + 1] - Y_axes[iy]
            A_piso += Lx * Ly

            # Cada una de las 2 vigas en X recibe Ax; cada una de las 2
            # vigas en Y recibe Ay. Se cumple 2*Ax + 2*Ay == Lx*Ly.
            Ax = mb.area_tributaria_viga(Lx, Ly)
            Ay = mb.area_tributaria_viga(Ly, Lx)
            detalle.append({'ix': ix, 'iy': iy, 'Lx': Lx, 'Ly': Ly,
                            'A_pano': Lx * Ly, 'Ax': Ax, 'Ay': Ay,
                            'forma_x': 'trapecio' if Ly <= Lx else 'triangulo',
                            'forma_y': 'trapecio' if Lx <= Ly else 'triangulo'})

            for lev in range(1, nLevels):
                for t, A in ((XBEAM[(lev, ix, iy)], Ax),
                             (XBEAM[(lev, ix, iy + 1)], Ax),
                             (YBEAM[(lev, ix, iy)], Ay),
                             (YBEAM[(lev, ix + 1, iy)], Ay)):
                    area_por_viga[t] = area_por_viga.get(t, 0.0) + A

    return area_por_viga, A_piso, detalle


def datos_vigas():
    """
    Devuelve {tag: (luz, direccion, area_seccion)} para todas las vigas.
    Se arma una vez; buscar linealmente en los mapas por cada viga seria
    O(n^2) sobre 656 vigas.
    """
    d = {}
    for (lev, ix, iy), t in XBEAM.items():
        d[t] = (X_axes[ix + 1] - X_axes[ix], 'X', A_beamX)
    for (lev, ix, iy), t in YBEAM.items():
        d[t] = (Y_axes[iy + 1] - Y_axes[iy], 'Y', A_beamY)
    return d


def apply_gravity(pattern_tag, use_self_weight, apply_live):
    """
    Aplica la carga de gravedad como DISTRIBUIDA sobre las vigas.

    Antes se aplicaba como dos fuerzas puntuales en los extremos
    (F = w*L/2 en cada nodo). La carga total se conservaba -por eso el
    equilibrio cerraba- pero las vigas NO flectaban por la losa: todo
    el momento del vano desaparecia. Para dimensionar vigas eso
    invalida el resultado.

    eleLoad -beamUniform con vecxz=(0,0,1) pone la gravedad en Wz local.
    """
    q = w_live_val if apply_live else w_slab_dead
    area_por_viga, _, _ = tributarias()
    vigas = datos_vigas()

    for tag, A in area_por_viga.items():
        L, _dir, A_sec = vigas[tag]
        w = q * A / L                      # uniforme equivalente

        if use_self_weight and not apply_live:
            w += gamma * A_sec             # peso propio de la viga

        ops.eleLoad('-ele', tag, '-type', '-beamUniform', 0.0, -w, 0.0)

    # Peso propio de las columnas, como fuerzas nodales en sus extremos.
    if use_self_weight and not apply_live:
        for lev in range(nLevels - 1):
            h = heights[lev + 1] - heights[lev]
            W = gamma * A_col * h
            for ix in range(nX):
                for iy in range(nY):
                    n_bot = lev * nNodesPerFloor + ix * nY + iy + 1
                    n_top = (lev + 1) * nNodesPerFloor + ix * nY + iy + 1
                    ops.load(n_bot, 0.0, 0.0, -W / 2.0, 0.0, 0.0, 0.0)
                    ops.load(n_top, 0.0, 0.0, -W / 2.0, 0.0, 0.0, 0.0)


# Coeficiente sismico pseudoestatico: corte basal como fraccion del
# peso sismico. Es un valor de trabajo, NO un calculo NCh433 completo
# (falta el espectro, el factor R, la zona y el tipo de suelo).
#
# El valor anterior era F = 10*nivel, o sea 360 kN de corte basal
# contra ~100.000 kN de peso: un coeficiente de 0.36%. Dos ordenes de
# magnitud por debajo de cualquier valor razonable en Chile, asi que
# los desplazamientos de EX/EY no representaban nada.
COEF_SISMICO = 0.10


def peso_sismico():
    """
    Peso por nivel: losa + terminaciones + peso propio de vigas y de la
    mitad de columnas de arriba y abajo. Se usa para repartir el corte
    basal en altura.
    """
    _, A_piso, _ = tributarias()
    vigas = datos_vigas()

    W_vigas_piso = sum(gamma * A_sec * L
                       for tag, (L, _d, A_sec) in vigas.items()
                       if tag in [XBEAM[(1, ix, iy)]
                                  for ix in range(nX - 1) for iy in range(nY)]
                       or tag in [YBEAM[(1, ix, iy)]
                                  for ix in range(nX) for iy in range(nY - 1)])

    W = {}
    for lev in range(1, nLevels):
        h_inf = heights[lev] - heights[lev - 1]
        h_sup = (heights[lev + 1] - heights[lev]) if lev < nLevels - 1 else 0.0
        W_col = gamma * A_col * nNodesPerFloor * (h_inf + h_sup) / 2.0
        W[lev] = w_slab_dead * A_piso + W_vigas_piso + W_col
    return W


def apply_lateral(direction):
    """
    Corte basal repartido en altura segun NCh433 simplificado:

        F_i = V * (W_i * h_i) / sum(W_j * h_j)

    Se aplica en el NODO MAESTRO de cada diafragma, que esta en el
    centro geometrico del piso. Antes se aplicaba en el nodo de esquina
    (ix=0, iy=0), lo que introduce una excentricidad artificial.
    """
    W = peso_sismico()
    V = COEF_SISMICO * sum(W.values())
    denom = sum(W[lev] * heights[lev] for lev in W)

    for lev in W:
        F = V * (W[lev] * heights[lev]) / denom
        nodo = master_nodes[lev]
        if direction == 'X':
            ops.load(nodo, F, 0.0, 0.0, 0.0, 0.0, 0.0)
        else:
            ops.load(nodo, 0.0, F, 0.0, 0.0, 0.0, 0.0)


def setup_analysis():
    # BandGeneral y Transformation: 'Plain' no sabe imponer un
    # rigidDiaphragm (su matriz de restriccion no es la identidad).
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Transformation')
    ops.integrator('LoadControl', 1.0)
    ops.algorithm('Linear')
    ops.analysis('Static')


# =============================================================================
# BUILD MODEL ONCE AND EXTRACT DATA
# =============================================================================
print("Building model...")
node_coords, col_list, xbeam_list, ybeam_list, master_nodes = build_model()
total_nodes = len(node_coords)
nColumns = len(col_list)
nXbeams = len(xbeam_list)
nYbeams = len(ybeam_list)
nElements = nColumns + nXbeams + nYbeams
print(f"Nodes: {total_nodes}, Columns: {nColumns}, X-beams: {nXbeams}, Y-beams: {nYbeams}, Total elements: {nElements}")
print("Constraints: fixed base + rigid diaphragm at all floors\n")

support_nodes = list(range(1, nNodesPerFloor + 1))


def run_load_case(name, load_func, **kwargs):
    """Rebuild model, apply loads, run analysis, return results."""
    ops.wipe()
    build_model()
    setup_analysis()

    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    load_func(1, **kwargs)

    ok = ops.analyze(1)
    print(f"  {name}: Convergence {'OK' if ok == 0 else 'FAILED'}")

    ops.reactions()

    disp = {nid: [round(ops.nodeDisp(nid, i), 8) for i in range(1, 7)]
            for nid in node_coords}
    react = {nid: [round(ops.nodeReaction(nid, i), 4) for i in range(1, 7)]
             for nid in support_nodes}
    return disp, react


# =============================================================================
# RUN ALL LOAD CASES
# =============================================================================
results = {}
os.makedirs('results', exist_ok=True)

print("--- Running Load Cases ---")
results['G'] = dict(zip(['displacements', 'reactions'],
    run_load_case('G', apply_gravity, use_self_weight=True, apply_live=False)))
results['Q'] = dict(zip(['displacements', 'reactions'],
    run_load_case('Q', apply_gravity, use_self_weight=False, apply_live=True)))
results['EX'] = dict(zip(['displacements', 'reactions'],
    run_load_case('EX', lambda pt, **kw: apply_lateral('X'))))
results['EY'] = dict(zip(['displacements', 'reactions'],
    run_load_case('EY', lambda pt, **kw: apply_lateral('Y'))))

# =============================================================================
# ELEMENT FORCES (Representative Elements)
# =============================================================================
print("\n--- Extracting Element Forces ---")

rep_elems = {
    'col_bottom': (col_list[0], 'G'),
    'col_mid': (col_list[192], 'G'),
    'col_top': (col_list[-1], 'G'),
    'xbeam_first': (xbeam_list[0], 'G'),
    'xbeam_mid': (xbeam_list[len(xbeam_list) // 2], 'EX'),
    'ybeam_first': (ybeam_list[0], 'G'),
    'ybeam_mid': (ybeam_list[len(ybeam_list) // 2], 'EY'),
}

results['element_forces'] = {}
for label, (eid, lc) in rep_elems.items():
    ops.wipe()
    build_model()
    setup_analysis()
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)

    if lc in ('G',):
        apply_gravity(1, use_self_weight=True, apply_live=False)
    elif lc in ('Q',):
        apply_gravity(1, use_self_weight=False, apply_live=True)
    elif lc == 'EX':
        apply_lateral('X')
    elif lc == 'EY':
        apply_lateral('Y')

    ops.analyze(1)
    # eleResponse(..., 'localForce') entrega fuerzas en ejes LOCALES.
    # (ops.eleForce da ejes GLOBALES: en una columna el axial de gravedad
    #  aparece como cortante y la viga-Y parece no flectar. Ver reports/semana01.md §3.)
    forces = ops.eleResponse(eid, 'localForce')
    entry = {'element_id': eid, 'load_case': lc}
    if len(forces) >= 12:
        entry['i_end_local_N_Vy_Vz_T_My_Mz'] = [round(f, 4) for f in forces[:6]]
        entry['j_end_local_N_Vy_Vz_T_My_Mz'] = [round(f, 4) for f in forces[6:12]]
    results['element_forces'][label] = entry
    print(f"  {label}: elem {eid}, LC={lc}")

# =============================================================================
# EQUILIBRIUM CHECK
# =============================================================================
print("\n" + "=" * 60)
print("EQUILIBRIUM CHECK")
print("=" * 60)

total_G_applied = 0.0
total_Q_applied = 0.0

for lev in range(1, nLevels):
    for ix in range(nX - 1):
        dx = X_axes[ix + 1] - X_axes[ix]
        for iy in range(nY - 1):
            dy = Y_axes[iy + 1] - Y_axes[iy]
            total_G_applied += w_slab_dead * dx * dy
            total_Q_applied += w_live_val * dx * dy

for lev in range(1, nLevels):
    for ix in range(nX - 1):
        dx = X_axes[ix + 1] - X_axes[ix]
        for iy in range(nY):
            total_G_applied += gamma * beamX_b * beamX_h * dx
    for ix in range(nX):
        for iy in range(nY - 1):
            dy = Y_axes[iy + 1] - Y_axes[iy]
            total_G_applied += gamma * beamY_b * beamY_h * dy

for lev in range(nLevels - 1):
    h = heights[lev + 1] - heights[lev]
    total_G_applied += gamma * A_col * h * nX * nY

print(f"\nTotal Dead Load Applied (G):  {total_G_applied:.2f} kN")
print(f"Total Live Load Applied (Q):  {total_Q_applied:.2f} kN")

sum_Rz_G = sum(results['G']['reactions'][nid][2] for nid in support_nodes)
sum_Rz_Q = sum(results['Q']['reactions'][nid][2] for nid in support_nodes)

print(f"\nDead Load (G):")
print(f"  Applied:   {total_G_applied:>14.2f} kN")
print(f"  Reactions: {sum_Rz_G:>14.2f} kN  (error: {abs(total_G_applied - sum_Rz_G):.6f} kN)")

print(f"\nLive Load (Q):")
print(f"  Applied:   {total_Q_applied:>14.2f} kN")
print(f"  Reactions: {sum_Rz_Q:>14.2f} kN  (error: {abs(total_Q_applied - sum_Rz_Q):.6f} kN)")

# Corte basal real: COEF_SISMICO por el peso sismico. Antes estaba
# fijo en 360 kN, y al cambiar el sismo el chequeo comparaba
# contra un numero que ya no correspondia.
total_lateral = COEF_SISMICO * sum(peso_sismico().values())
sum_Rx_EX = sum(results['EX']['reactions'][nid][0] for nid in support_nodes)
sum_Ry_EY = sum(results['EY']['reactions'][nid][1] for nid in support_nodes)

print(f"\nLateral Load EX:")
print(f"  Applied:   {total_lateral:>14.2f} kN")
print(f"  Reactions: {sum_Rx_EX:>14.2f} kN  (error: {abs(total_lateral + sum_Rx_EX):.6f} kN)")

print(f"\nLateral Load EY:")
print(f"  Applied:   {total_lateral:>14.2f} kN")
print(f"  Reactions: {sum_Ry_EY:>14.2f} kN  (error: {abs(total_lateral + sum_Ry_EY):.6f} kN)")

# =============================================================================
# MAX DISPLACEMENTS
# =============================================================================
print("\n" + "=" * 60)
print("MAXIMUM DISPLACEMENTS SUMMARY")
print("=" * 60)
for lc in ['G', 'Q', 'EX', 'EY']:
    d = results[lc]['displacements']
    max_ux = max(abs(v[0]) for v in d.values())
    max_uy = max(abs(v[1]) for v in d.values())
    max_uz = max(abs(v[2]) for v in d.values())
    print(f"  {lc:3s}: UX_max = {max_ux:.6f} m, UY_max = {max_uy:.6f} m, UZ_max = {max_uz:.6f} m")

# =============================================================================
# SAVE JSON
# =============================================================================
results['model_info'] = {
    'n_nodes': total_nodes,
    'n_elements': nElements,
    'n_columns': nColumns,
    'n_xbeams': nXbeams,
    'n_ybeams': nYbeams,
    'n_levels': nLevels,
    'n_fixed_supports': len(support_nodes),
    'dimensions_m': f"{X_axes[-1] - X_axes[0]:.1f} x {Y_axes[-1] - Y_axes[0]:.1f}",
    'height_m': heights[-1],
    'concrete_fpc_MPa': fpc,
    'concrete_E_MPa': round(Ec, 1),
    'column_section': f"{col_b*100:.0f}x{col_h*100:.0f} cm",
    'beam_x_section': f"{beamX_b*100:.0f}x{beamX_h*100:.0f} cm",
    'beam_y_section': f"{beamY_b*100:.0f}x{beamY_h*100:.0f} cm",
    'slab_thickness_m': slab_t,
}

results['node_coordinates'] = {str(k): v for k, v in node_coords.items()}

results['equilibrium_check'] = {
    'G_applied_kN': round(total_G_applied, 2),
    'G_reaction_kN': round(sum_Rz_G, 2),
    'G_error_kN': round(abs(total_G_applied - sum_Rz_G), 6),
    'Q_applied_kN': round(total_Q_applied, 2),
    'Q_reaction_kN': round(sum_Rz_Q, 2),
    'Q_error_kN': round(abs(total_Q_applied - sum_Rz_Q), 6),
    'EX_applied_kN': round(total_lateral, 2),
    'EX_reaction_kN': round(sum_Rx_EX, 2),
    'EX_error_kN': round(abs(total_lateral + sum_Rx_EX), 6),
    'EY_applied_kN': round(total_lateral, 2),
    'EY_reaction_kN': round(sum_Ry_EY, 2),
    'EY_error_kN': round(abs(total_lateral + sum_Ry_EY), 6),
}

output_path = os.path.join('results', 'benchmark_results.json')
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to: {output_path}")
print("\nDone!")

# =============================================================================
# EXPORT TO UNITY (automatic visualization)
# =============================================================================
try:
    import export_unity

    export_unity.export_model(
        X_axes, Y_axes, heights,
        col_tags=col_list,
        bx_tags=xbeam_list,
        by_tags=ybeam_list,
        supports=support_nodes,
        label="Edificio de Ingenieria - Universidad de los Andes",
        extra={
            "n_columns": nColumns,
            "n_xbeams": nXbeams,
            "n_ybeams": nYbeams,
            "n_levels": nLevels,
            'dimensions_m': f"{X_axes[-1] - X_axes[0]:.1f} x {Y_axes[-1] - Y_axes[0]:.1f}",
            'height_m': heights[-1],
            "concrete_fpc_MPa": fpc,
        },
        results_file="results/benchmark_results.json",
    )
    print("Unity: model.json actualizado (el visor se recarga solo).")
except ImportError:
    print("(export_unity.py no encontrado; Unity no se actualiza)")
