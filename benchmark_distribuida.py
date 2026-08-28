"""
================================================================
 benchmark_distribuida.py
================================================================
 Corre el marco de benchmark bajo G, Q y EX, verifica equilibrio
 y contrasta contra el valor validado con SAP2000.

 La geometria, secciones y cargas viven en modelo_benchmark.py
 (fuente de verdad unica). Este archivo SOLO orquesta y verifica.
================================================================
"""

import json
import os

import openseespy.opensees as ops

import modelo_benchmark as mb

# ============================================================
# EJECUCION
# ============================================================
print("=" * 60)
print("  LAB BENCHMARK 3D - CARGA DISTRIBUIDA (eleLoad)")
print("=" * 60)

coords, cols, vx, vy = mb.construir_modelo()
nodos_piso1 = list(range(mb.nNodosPorPiso + 1, 2 * mb.nNodosPorPiso + 1))
nY = mb.nY
print(f"\n  Columnas: {len(cols)} | Vigas X: {len(vx)} | Vigas Y: {len(vy)}")
print(f"  J_col = {mb.J_col:.6e} m4  (Saint-Venant, no el 'min(I)*0.3' de antes)")


def extraer_resultados(coords):
    disp = {nid: [ops.nodeDisp(nid, i) for i in range(1, 7)] for nid in coords}
    reac = {nid: [ops.nodeReaction(nid, i) for i in range(1, 7)]
            for nid in range(1, mb.nNodosPorPiso + 1)}
    return disp, reac


# --- CASO G (distribuida + peso propio) ---
print("\n[G] Carga muerta distribuida...")
coords, cols, vx, vy = mb.construir_modelo()
mb.nuevo_patron_de_carga()
mb.aplicar_carga_distribuida(mb.q_losa, vx, vy, incluir_peso_vigas=True)
ok_G = mb.resolver()
disp_G, reac_G = extraer_resultados(coords)
# localForce, NO eleForce: eleForce() devuelve ejes GLOBALES.
fuerzas_G = {etag: [round(f, 4) for f in ops.eleResponse(etag, 'localForce')]
             for etag in mb.tags(vx) + mb.tags(vy)}
print(f"    Convergencia: {'OK' if ok_G == 0 else 'FALLO'}")

# --- CASO Q ---
print("[Q] Carga viva distribuida...")
coords, cols, vx, vy = mb.construir_modelo()
mb.nuevo_patron_de_carga()
mb.aplicar_carga_distribuida(mb.q_viva, vx, vy, incluir_peso_vigas=False)
ok_Q = mb.resolver()
disp_Q, reac_Q = extraer_resultados(coords)
print(f"    Convergencia: {'OK' if ok_Q == 0 else 'FALLO'}")

# --- CASO EX (lateral, nodal) ---
print("[EX] Carga lateral...")
coords, cols, vx, vy = mb.construir_modelo()
mb.nuevo_patron_de_carga()
F_sismo = 50.0
for nid in nodos_piso1:
    ops.load(nid, F_sismo, 0.0, 0.0, 0.0, 0.0, 0.0)
ok_EX = mb.resolver()
disp_EX, reac_EX = extraer_resultados(coords)
print(f"    Convergencia: {'OK' if ok_EX == 0 else 'FALLO'}")


# ============================================================
# EQUILIBRIO
# ============================================================
print("\n" + "=" * 60)
print("  EQUILIBRIO")
print("=" * 60)

area = mb.Lx * mb.Ly

# G = losa+terminaciones sobre el area + peso propio de las 4 vigas
# (2 vigas de luz Lx + 2 de luz Ly)
G_losa = mb.q_losa * area
G_peso_vigas = 2 * mb.gamma * mb.A_vig * (mb.Lx + mb.Ly)
G_tot = G_losa + G_peso_vigas
Q_tot = mb.q_viva * area

sG = sum(reac_G[n][2] for n in reac_G)
sQ = sum(reac_Q[n][2] for n in reac_Q)
sX = sum(reac_EX[n][0] for n in reac_EX)

err_G = abs(G_tot - sG)
err_Q = abs(Q_tot - sQ)
err_X = abs(F_sismo * 4 + sX)

print(f"\n  G: aplicado {G_tot:.2f} kN | reaccion {sG:.2f} kN | error {err_G:.6f}")
print(f"  Q: aplicado {Q_tot:.2f} kN | reaccion {sQ:.2f} kN | error {err_Q:.6f}")
print(f"  EX: aplicado {F_sismo*4:.2f} kN | reaccion {sX:.2f} kN | error {err_X:.6f}")


# ============================================================
# DESPLAZAMIENTOS Y MOMENTOS
# ============================================================
print("\n" + "=" * 60)
print("  DESPLAZAMIENTOS NODO TECHO")
print("=" * 60)
print(f"  {'Nodo':<6}{'UZ_G(mm)':<12}{'UZ_Q(mm)':<12}{'UX_EX(mm)':<12}")
for nid in nodos_piso1:
    print(f"  {nid:<6}{disp_G[nid][2]*1000:<12.5f}"
          f"{disp_Q[nid][2]*1000:<12.5f}{disp_EX[nid][0]*1000:<12.5f}")

print()
print("=" * 60)
print("  ESFUERZOS EN VIGAS (Caso G) - EJES LOCALES")
print("=" * 60)
print("  eleResponse(tag,'localForce') =")
print("     [N_i,Vy_i,Vz_i,T_i,My_i,Mz_i, N_j,Vy_j,Vz_j,T_j,My_j,Mz_j]")
print("  Gravedad -> cortante en Vz (idx 2) y momento en My (idx 4,10).")
print()
print("  CUIDADO: eleForce() devuelve fuerzas GLOBALES, no locales.")
print("  Para una viga que corre en Y, su momento de gravedad sale en")
print("  la casilla Mx global; si se lee como 'torsion' parece que el")
print("  modelo estuviera malo. Por eso aca se usa localForce.")
print()
print(f"  Cada viga son {mb.ULTIMA_TOPOLOGIA['subdivisiones']} elementos en serie.")
print("  Se muestra el momento en el apoyo y en el centro del vano.")
print()
for etq, grupo in (("X", mb.ULTIMA_TOPOLOGIA['vigas'][:nY]),
                   ("Y", mb.ULTIMA_TOPOLOGIA['vigas'][nY:])):
    for tags_viga in grupo:
        f_apoyo = fuerzas_G[tags_viga[0]]
        f_centro = fuerzas_G[tags_viga[len(tags_viga) // 2]]
        print(f"  Viga {etq} (elems {tags_viga[0]}..{tags_viga[-1]}): "
              f"My apoyo={f_apoyo[4]:8.3f}   My centro={f_centro[4]:8.3f} kN*m"
              f"   Vz={f_apoyo[2]:7.3f} kN")

# Chequeo de simetria: en el marco CUADRADO las vigas X e Y deben tener
# esfuerzos LOCALES identicos. El equilibrio global no puede detectar
# esto; es justamente el tipo de error que se nos escapo antes.
_fx = fuerzas_G[mb.tags(vx)[0]]
_fy = fuerzas_G[mb.tags(vy)[0]]
simetria_ok = all(abs(a - b) < 1e-6 for a, b in zip(_fx, _fy))
print()
print(f"  Simetria X/Y en ejes locales: {'OK' if simetria_ok else 'FALLA'}")


# ============================================================
# VERIFICACION AUTOMATICA (regla 6 del CLAUDE.md)
# ============================================================
print("\n" + "=" * 60)
print("  VERIFICACION")
print("=" * 60)

fallos = []

for nombre, err in (("G", err_G), ("Q", err_Q), ("EX", err_X)):
    estado = "OK" if err < 1e-6 else "FALLA"
    print(f"  Equilibrio {nombre:<3}: error {err:.2e}  -> {estado}")
    if err >= 1e-6:
        fallos.append(f"equilibrio {nombre} error={err:.2e}")

uz = disp_G[nodos_piso1[0]][2] * 1000.0
delta = abs(uz - mb.UZ_TECHO_G_REFERENCIA_MM)
estado = "OK" if delta < mb.TOLERANCIA_MM else "FALLA"
print(f"  UZ techo bajo G : {uz:.5f} mm "
      f"(referencia {mb.UZ_TECHO_G_REFERENCIA_MM:.5f}) -> {estado}")
if delta >= mb.TOLERANCIA_MM:
    fallos.append(f"UZ techo {uz:.5f} != {mb.UZ_TECHO_G_REFERENCIA_MM:.5f}")

# La flecha del centro del vano: 5 veces la del nodo de esquina, y es
# lo que el visor no mostraba cuando cada viga era un solo elemento.
centros = mb.ULTIMA_TOPOLOGIA['centros_vano']
if centros:
    uz_c = disp_G[centros[0]][2] * 1000.0
    d_c = abs(uz_c - mb.UZ_CENTRO_VANO_G_REFERENCIA_MM)
    print(f"  UZ centro del vano G: {uz_c:.5f} mm "
          f"(referencia {mb.UZ_CENTRO_VANO_G_REFERENCIA_MM:.5f}) -> "
          f"{'OK' if d_c < mb.TOLERANCIA_MM else 'FALLA'}")
    if d_c >= mb.TOLERANCIA_MM:
        fallos.append(f"UZ centro de vano {uz_c:.5f}")

if not simetria_ok:
    fallos.append("simetria X/Y de esfuerzos locales")

if fallos:
    print("\n  *** BENCHMARK ROTO ***")
    for f in fallos:
        print(f"    - {f}")
else:
    print("\n  Benchmark intacto.")


# ============================================================
# GUARDAR JSON
# ============================================================
os.makedirs('results', exist_ok=True)
resultados = {
    'model_info': {
        'description': 'Marco 3D vigas L, CARGA DISTRIBUIDA (eleLoad beamUniform)',
        'metodo_carga': 'distribuida uniforme equivalente sobre vigas',
        'material': {'fpc_MPa': mb.fpc, 'Ec_kPa': round(mb.Ec, 0)},
        'secciones': {
            'columna': {'A': mb.A_col, 'Iy': mb.Iy_col,
                        'Iz': mb.Iz_col, 'J': mb.J_col},
            'viga_L': {'A': mb.A_vig, 'Iy': mb.Iy_vig,
                       'Iz': mb.Iz_vig, 'J': mb.J_vig},
        },
        'units': 'm, kN, kPa',
    },
    'nodes': {str(k): list(v) for k, v in coords.items()},
    'elements': {'columns': mb.tags(cols),
                 'beams_x': mb.tags(vx),
                 'beams_y': mb.tags(vy)},
    'load_cases': {
        'G': {'applied_kN': round(G_tot, 2), 'reaction_kN': round(sG, 2),
              'error_kN': round(err_G, 6),
              'displacements': {str(k): [round(v[i], 8) for i in range(3)]
                                for k, v in disp_G.items()},
              'reactions': {str(k): [round(v[i], 4) for i in range(3)]
                            for k, v in reac_G.items()}},
        'Q': {'applied_kN': round(Q_tot, 2), 'reaction_kN': round(sQ, 2),
              'error_kN': round(err_Q, 6),
              'displacements': {str(k): [round(v[i], 8) for i in range(3)]
                                for k, v in disp_Q.items()}},
        'EX': {'applied_kN': F_sismo * 4,
               'displacements': {str(k): [round(v[i], 8) for i in range(3)]
                                 for k, v in disp_EX.items()}},
    },
}
with open('results/lab_results_distribuida.json', 'w') as f:
    json.dump(resultados, f, indent=2)

print(f"\nGuardado en results/lab_results_distribuida.json")
print("=" * 60)
