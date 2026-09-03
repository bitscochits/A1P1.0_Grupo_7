"""
================================================================
 generar_json_unity.py
================================================================
 Exporta modelo_unity.json: el contrato que consume Unity.

 El archivo es un MODELO COMPLETO, no solo geometria. Trae material,
 secciones, apoyos, elementos y los 4 casos de carga, de modo que
 Unity pueda:

   1. Dibujarlo sin servidor (nodos + elementos).
   2. Dibujar la deformada de G sin servidor (ux/uy/uz precalculados).
   3. MANDARLO TAL CUAL al servidor para recalcular cualquier caso,
      sin tener que inventar secciones ni cargas del lado de Unity.

 El punto 3 es la razon de ser del formato: antes el JSON solo traia
 geometria y resultados, asi que Unity no podia reenviarlo -- le
 faltaban 'secciones' y las cargas, y terminaba armandolas a mano.

 IMPORTANTE: 'secciones' se exporta como LISTA, no como diccionario.
 JsonUtility de Unity no sabe leer diccionarios con claves arbitrarias.
 El servidor acepta ambas formas.

 Salida: modelo_unity.json (junto a este script).
 Para usarlo en Unity, copialo a Assets/StreamingAssets/.
================================================================
"""

import json
import os
import sys

# El servidor vive en comun/, ya no junto a este archivo.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'comun'))

import openseespy.opensees as ops

import modelo_benchmark as mb

# ============================================================
# 1. CONSTRUIR Y RESOLVER (caso G, para la deformada precalculada)
# ============================================================
coords, cols, vx, vy = mb.construir_modelo()

mb.nuevo_patron_de_carga()
mb.aplicar_carga_distribuida(mb.q_losa, vx, vy, incluir_peso_vigas=True)

if mb.resolver() != 0:
    raise SystemExit("El analisis NO convergio. Revisa el modelo.")

# ============================================================
# 2. CARGAS DE CADA CASO
# ============================================================
F_SISMO = 50.0     # kN por nodo de techo (pseudoestatico)

w_G_x = mb.w_viga(mb.q_losa, mb.Lx, mb.Ly, incluir_peso_vigas=True)
w_G_y = mb.w_viga(mb.q_losa, mb.Ly, mb.Lx, incluir_peso_vigas=True)
w_Q_x = mb.w_viga(mb.q_viva, mb.Lx, mb.Ly)
w_Q_y = mb.w_viga(mb.q_viva, mb.Ly, mb.Lx)

# OJO: solo los NUDOS del marco (los 4 originales de techo), no los
# nodos intermedios que aparecen al subdividir las vigas. Con la version
# anterior ("todo nodo por encima de la base") el sismo pasaba de
# 4 x 50 = 200 kN a 16 x 50 = 800 kN sin que se notara.
nodos_techo = list(range(mb.nNodosPorPiso + 1, 2 * mb.nNodosPorPiso + 1))


def distribuidas(wx, wy):
    """Cargas -beamUniform sobre vigas X (wx) y vigas Y (wy)."""
    return ([{"elemento": t, "wy": 0.0, "wz": -wx, "wx": 0.0} for t, _, _ in vx]
            + [{"elemento": t, "wy": 0.0, "wz": -wy, "wx": 0.0} for t, _, _ in vy])


casos = [
    {"nombre": "G",
     "descripcion": "Peso propio + losa + terminaciones",
     "cargas_distribuidas": distribuidas(w_G_x, w_G_y),
     "cargas_nodales": []},
    {"nombre": "Q",
     "descripcion": "Sobrecarga de uso",
     "cargas_distribuidas": distribuidas(w_Q_x, w_Q_y),
     "cargas_nodales": []},
    {"nombre": "EX",
     "descripcion": "Sismo pseudoestatico en X",
     "cargas_distribuidas": [],
     "cargas_nodales": [{"nodo": n, "fx": F_SISMO} for n in nodos_techo]},
    {"nombre": "EY",
     "descripcion": "Sismo pseudoestatico en Y",
     "cargas_distribuidas": [],
     "cargas_nodales": [{"nodo": n, "fy": F_SISMO} for n in nodos_techo]},
]

# ============================================================
# 3. ARMAR EL JSON
# ============================================================
modelo = {
    "info": {
        "descripcion": "Benchmark marco 4 columnas + 4 vigas L",
        "unidades": "m, kN, kPa",
        "caso_precalculado": "G",
        "nota": ("ux/uy/uz de cada nodo son la deformada del caso G, para "
                 "poder dibujarla sin servidor. Para cualquier otro caso, "
                 "manda este mismo JSON a POST /analizar."),
    },

    # --- Definicion del modelo (lo que el servidor necesita) ---
    "material": {"fpc_MPa": mb.fpc, "poisson": mb.poisson, "gamma": mb.gamma},

    # LISTA, no diccionario: ver nota del encabezado.
    "secciones": [
        {"nombre": "columna", "A": mb.A_col, "Iy": mb.Iy_col,
         "Iz": mb.Iz_col, "J": mb.J_col},
        {"nombre": "viga", "A": mb.A_vig, "Iy": mb.Iy_vig,
         "Iz": mb.Iz_vig, "J": mb.J_vig},
    ],

    "nodos": [],
    "elementos": [],
    "diafragmas": [],
    "brazos_rigidos": [],
    "casos_de_carga": casos,
}

# Los nodos creados al subdividir las vigas se marcan como auxiliares:
# existen para poder DIBUJAR la flecha del vano, no son nudos del marco.
# Unity los pinta mas chicos para que no compitan con los reales.
auxiliares = set(mb.ULTIMA_TOPOLOGIA['nodos_auxiliares'])

for nid, (x, y, z) in coords.items():
    d = [ops.nodeDisp(nid, i) for i in range(1, 7)]
    empotrado = nid <= mb.nNodosPorPiso
    modelo["nodos"].append({
        "id": nid,
        "x": x, "y": y, "z": z,
        "fijo": empotrado,
        "auxiliar": nid in auxiliares,
        "restricciones": [1, 1, 1, 1, 1, 1] if empotrado else [0, 0, 0, 0, 0, 0],
        # Deformada del caso G, para dibujar sin servidor.
        "ux": round(d[0], 8),
        "uy": round(d[1], 8),
        "uz": round(d[2], 8),
    })

for tag, n1, n2 in cols:
    modelo["elementos"].append({"id": tag, "n1": n1, "n2": n2,
                                "seccion": "columna", "tipo": "columna"})
for tag, n1, n2 in vx:
    modelo["elementos"].append({"id": tag, "n1": n1, "n2": n2,
                                "seccion": "viga", "tipo": "viga_x"})
for tag, n1, n2 in vy:
    modelo["elementos"].append({"id": tag, "n1": n1, "n2": n2,
                                "seccion": "viga", "tipo": "viga_y"})

# ============================================================
# 4. GUARDAR
# ============================================================
ruta_salida = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'data', 'unity', 'benchmark.json')
os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
with open(ruta_salida, 'w', encoding='utf-8') as f:
    json.dump(modelo, f, indent=2)

print(f"JSON generado: {ruta_salida}")
print(f"  Nodos: {len(modelo['nodos'])} | Elementos: {len(modelo['elementos'])}"
      f" | Secciones: {len(modelo['secciones'])}"
      f" | Casos: {len(modelo['casos_de_carga'])}")

# ============================================================
# 5. VERIFICACION (regla 6 del CLAUDE.md)
# ============================================================
nodo_techo = mb.nNodosPorPiso + 1
uz_mm = modelo["nodos"][nodo_techo - 1]["uz"] * 1000.0
delta = abs(uz_mm - mb.UZ_TECHO_G_REFERENCIA_MM)

print(f"\n  UZ nodo {nodo_techo} = {uz_mm:.5f} mm "
      f"(referencia {mb.UZ_TECHO_G_REFERENCIA_MM:.5f} mm)")

if delta >= mb.TOLERANCIA_MM:
    raise SystemExit(
        f"  -> *** BENCHMARK ROTO *** diferencia {delta:.5f} mm.\n"
        f"     El JSON se escribio igual, pero NO confies en el.")
print("  -> OK, el benchmark sigue intacto.")

# El JSON debe poder mandarse al servidor TAL CUAL. Se verifica aqui
# para que no se descubra recien en Unity.
try:
    from servidor_opensees import construir_y_resolver
except ImportError:
    print("\n  (servidor_opensees no importable; se omite el round-trip)")
else:
    r = construir_y_resolver(modelo)
    caso_G = next(c for c in r['casos'] if c['nombre'] == 'G')
    uz_srv = next(d for d in caso_G['desplazamientos']
                  if d['id'] == nodo_techo)['uz'] * 1000.0
    print(f"\n  Round-trip por el servidor: {len(r['casos'])} casos, "
          f"UZ(G) = {uz_srv:.5f} mm")
    if abs(uz_srv - uz_mm) > 1e-4:
        raise SystemExit("  -> *** El servidor NO reproduce el JSON ***")
    print("  -> OK, el JSON es enviable al servidor tal cual.")
