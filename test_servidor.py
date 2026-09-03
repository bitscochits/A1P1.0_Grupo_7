"""
================================================================
 test_servidor.py
================================================================
 Verifica las capacidades del servidor OpenSees:

   1. Regresion: el marco benchmark sigue dando -0.06348 mm.
   2. Multi-caso: resolver N casos sobre el MISMO modelo da
      identico a reconstruir el modelo para cada caso.
   3. Superposicion lineal: G + Q calculado por separado y sumado
      == un unico caso con las cargas ya sumadas.
   4. Apoyos por grado de libertad (empotrado vs rotula).
   5. Diafragma rigido: los nodos del piso se mueven juntos.
   6. Brazos rigidos (muro como columna ancha).
   7. Entradas invalidas rechazadas con mensaje claro.

 Correr con:  python test_servidor.py
================================================================
"""

import copy

import os
import sys

_RAIZ = os.path.dirname(os.path.abspath(__file__))
for _c in ('comun', 'benchmark'):
    sys.path.insert(0, os.path.join(_RAIZ, _c))

from servidor_opensees import construir_y_resolver
import modelo_benchmark as mb

fallos = []


def check(nombre, cond, detalle=""):
    print(f"  [{'OK  ' if cond else 'FALLA'}] {nombre}" +
          (f"   {detalle}" if detalle else ""))
    if not cond:
        fallos.append(nombre)


def rechaza(nombre, data, fragmento):
    try:
        construir_y_resolver(data)
        check(nombre, False, "no lanzo excepcion")
    except Exception as e:
        ok = fragmento.lower() in str(e).lower()
        check(nombre, ok, f'"{str(e)[:70]}"')


SEC = {
    "columna": {"A": mb.A_col, "Iy": mb.Iy_col, "Iz": mb.Iz_col, "J": mb.J_col},
    "viga":    {"A": mb.A_vig, "Iy": mb.Iy_vig, "Iz": mb.Iz_vig, "J": mb.J_vig},
    "muro":    {"A": 0.6, "Iy": 0.045, "Iz": 0.0018, "J": 0.0072},
}

NODOS = [
    {"id": 1, "x": 0, "y": 0, "z": 0, "fijo": True},
    {"id": 2, "x": 0, "y": 4, "z": 0, "fijo": True},
    {"id": 3, "x": 4, "y": 0, "z": 0, "fijo": True},
    {"id": 4, "x": 4, "y": 4, "z": 0, "fijo": True},
    {"id": 5, "x": 0, "y": 0, "z": 3},
    {"id": 6, "x": 0, "y": 4, "z": 3},
    {"id": 7, "x": 4, "y": 0, "z": 3},
    {"id": 8, "x": 4, "y": 4, "z": 3},
]
ELEMS = [
    {"id": 1, "n1": 1, "n2": 5, "seccion": "columna", "tipo": "columna"},
    {"id": 2, "n1": 2, "n2": 6, "seccion": "columna", "tipo": "columna"},
    {"id": 3, "n1": 3, "n2": 7, "seccion": "columna", "tipo": "columna"},
    {"id": 4, "n1": 4, "n2": 8, "seccion": "columna", "tipo": "columna"},
    {"id": 5, "n1": 5, "n2": 7, "seccion": "viga", "tipo": "viga_x"},
    {"id": 6, "n1": 6, "n2": 8, "seccion": "viga", "tipo": "viga_x"},
    {"id": 7, "n1": 5, "n2": 6, "seccion": "viga", "tipo": "viga_y"},
    {"id": 8, "n1": 7, "n2": 8, "seccion": "viga", "tipo": "viga_y"},
]
W_G = mb.w_viga(mb.q_losa, 4.0, 4.0, incluir_peso_vigas=True)
W_Q = mb.w_viga(mb.q_viva, 4.0, 4.0)

CARGAS_G = [{"elemento": e, "wy": 0, "wz": -W_G, "wx": 0} for e in (5, 6, 7, 8)]
CARGAS_Q = [{"elemento": e, "wy": 0, "wz": -W_Q, "wx": 0} for e in (5, 6, 7, 8)]
CARGAS_EX = [{"nodo": n, "fx": 50.0} for n in (5, 6, 7, 8)]


def base(**extra):
    d = {"material": {"fpc_MPa": 25, "poisson": 0.2},
         "nodos": copy.deepcopy(NODOS), "secciones": SEC,
         "elementos": copy.deepcopy(ELEMS)}
    d.update(extra)
    return d


def uz(res, nid=5):
    return [x for x in res['desplazamientos'] if x['id'] == nid][0]['uz']


def ux(res, nid=5):
    return [x for x in res['desplazamientos'] if x['id'] == nid][0]['ux']


print("=" * 66)
print("  TEST: SERVIDOR OPENSEES")
print("=" * 66)

# ------------------------------------------------------------
print("\n1. Regresion del benchmark")
r = construir_y_resolver(base(cargas_distribuidas=CARGAS_G))
check("UZ techo = -0.06348 mm",
      abs(uz(r) * 1000 - mb.UZ_TECHO_G_REFERENCIA_MM) < 1e-4,
      f"{uz(r)*1000:.5f} mm")
check("equilibrio vertical",
      abs(sum(x['fz'] for x in r['reacciones']) - 179.0) < 1e-3,
      f"{sum(x['fz'] for x in r['reacciones']):.4f} kN")
check("respuesta plana (sin 'casos')", 'casos' not in r)

# ------------------------------------------------------------
print("\n2. Multi-caso == reconstruir el modelo por cada caso")
multi = construir_y_resolver(base(casos_de_carga=[
    {"nombre": "G", "cargas_distribuidas": CARGAS_G},
    {"nombre": "Q", "cargas_distribuidas": CARGAS_Q},
    {"nombre": "EX", "cargas_nodales": CARGAS_EX},
]))
check("devuelve 'casos' como lista", isinstance(multi.get('casos'), list))
check("3 casos", len(multi['casos']) == 3)
check("nombres conservados",
      [c['nombre'] for c in multi['casos']] == ["G", "Q", "EX"])

solos = {
    "G": construir_y_resolver(base(cargas_distribuidas=CARGAS_G)),
    "Q": construir_y_resolver(base(cargas_distribuidas=CARGAS_Q)),
    "EX": construir_y_resolver(base(cargas_nodales=CARGAS_EX)),
}
for c in multi['casos']:
    s = solos[c['nombre']]
    dmax = max(abs(a['ux'] - b['ux']) + abs(a['uy'] - b['uy'])
               + abs(a['uz'] - b['uz'])
               for a, b in zip(c['desplazamientos'], s['desplazamientos']))
    check(f"caso {c['nombre']} identico al modelo reconstruido",
          dmax < 1e-12, f"dif max {dmax:.2e} m")

# El bug clasico: sin setTime(0) el 2do caso saldria x2.
g_multi = [x for x in multi['casos'][0]['desplazamientos'] if x['id'] == 5][0]
q_multi = [x for x in multi['casos'][1]['desplazamientos'] if x['id'] == 5][0]
check("el caso 2 NO viene amplificado por el tiempo",
      abs(q_multi['uz'] - uz(solos['Q'])) < 1e-12,
      f"Q multi={q_multi['uz']:.3e}  solo={uz(solos['Q']):.3e}")

# ------------------------------------------------------------
print("\n3. Superposicion lineal:  R(G) + R(Q) == R(G+Q)")
sumadas = [{"elemento": e, "wy": 0, "wz": -(W_G + W_Q), "wx": 0}
           for e in (5, 6, 7, 8)]
juntos = construir_y_resolver(base(cargas_distribuidas=sumadas))
suma = uz(solos['G']) + uz(solos['Q'])
# La respuesta se redondea a 8 decimales, asi que comparar una SUMA de
# dos valores redondeados arrastra hasta 2e-8. Esa es la tolerancia real
# del contrato, no la precision del solver.
check("UZ(G)+UZ(Q) == UZ(G+Q)", abs(suma - uz(juntos)) < 2e-8,
      f"{suma:.8e} vs {uz(juntos):.8e}  (dif {abs(suma-uz(juntos)):.1e})")

# ------------------------------------------------------------
print("\n4. Apoyos por grado de libertad")
emp = construir_y_resolver(base(cargas_nodales=CARGAS_EX))
rot = base(cargas_nodales=CARGAS_EX)
for nd in rot['nodos']:
    if nd.get('fijo'):
        nd.pop('fijo')
        nd['restricciones'] = [1, 1, 1, 0, 0, 0]   # rotula
rot = construir_y_resolver(rot)
check("rotula es mas flexible que empotrado",
      abs(ux(rot)) > abs(ux(emp)) * 2,
      f"empotrado {ux(emp)*1000:.3f} mm  vs rotula {ux(rot)*1000:.3f} mm")
mom_emp = sum(abs(x['my']) for x in emp['reacciones'])
mom_rot = sum(abs(x['my']) for x in rot['reacciones'])
check("la rotula no transmite momento", mom_rot < 1e-6 < mom_emp,
      f"My empotrado {mom_emp:.3f}  vs rotula {mom_rot:.3e} kN*m")
check("equilibrio horizontal con rotulas",
      abs(sum(x['fx'] for x in rot['reacciones']) + 200.0) < 1e-3)

# ------------------------------------------------------------
print("\n5. Diafragma rigido")
d = base(cargas_nodales=[{"nodo": 5, "fx": 100.0}])   # carga en UN nodo
sin_dia = construir_y_resolver(d)
disp_sin = [ux(sin_dia, n) for n in (5, 6, 7, 8)]

d = base(cargas_nodales=[{"nodo": 5, "fx": 100.0}])
d['nodos'].append({"id": 99, "x": 2, "y": 2, "z": 3})
d['diafragmas'] = [{"nodo_maestro": 99, "nodos": [5, 6, 7, 8],
                    "perpendicular": 3}]
con_dia = construir_y_resolver(d)
disp_con = [ux(con_dia, n) for n in (5, 6, 7, 8)]

check("sin diafragma los nodos se mueven distinto",
      (max(disp_sin) - min(disp_sin)) > 1e-6,
      f"rango {1000*(max(disp_sin)-min(disp_sin)):.4f} mm")

# OJO: un diafragma rigido NO obliga a que todos los nodos tengan el
# mismo ux. El piso se mueve como CUERPO RIGIDO en su plano, y con una
# carga excentrica ademas ROTA, asi que los ux difieren legitimamente.
# Lo que si debe cumplirse:
#   (a) todos los nodos comparten el mismo giro rz
#   (b) ux_i = ux_m - rz*(y_i - y_m)   y   uy_i = uy_m + rz*(x_i - x_m)
D = {x['id']: x for x in con_dia['desplazamientos']}
XY = {5: (0, 0), 6: (0, 4), 7: (4, 0), 8: (4, 4), 99: (2, 2)}
rz = [D[n]['rz'] for n in (5, 6, 7, 8, 99)]
check("todos los nodos del diafragma comparten el giro rz",
      (max(rz) - min(rz)) < 1e-12, f"rango {max(rz)-min(rz):.2e} rad")

xm, ym = XY[99]
um, vm, rzm = D[99]['ux'], D[99]['uy'], D[99]['rz']
err_rig = max(abs(D[n]['ux'] - (um - rzm*(XY[n][1]-ym)))
              + abs(D[n]['uy'] - (vm + rzm*(XY[n][0]-xm)))
              for n in (5, 6, 7, 8))
check("cinematica de cuerpo rigido en el plano",
      err_rig < 1e-9, f"error max {err_rig:.2e} m")
check("el diafragma SI rigidiza (menos deformacion relativa)",
      (max(disp_con) - min(disp_con)) < (max(disp_sin) - min(disp_sin)))
check("equilibrio con diafragma",
      abs(sum(x['fx'] for x in con_dia['reacciones']) + 100.0) < 1e-3,
      f"{sum(x['fx'] for x in con_dia['reacciones']):.4f} kN")
check("avisa que restringio el maestro fuera de plano",
      any("fuera del plano" in a for a in con_dia['avisos']))

# ------------------------------------------------------------
print("\n6. Brazos rigidos (muro como columna ancha)")
# Muro vertical con un nodo colgando a 1 m de su eje. El brazo rigido
# obliga a que ese nodo siga al del eje del muro.
d = {"material": {"fpc_MPa": 25, "poisson": 0.2},
     "nodos": [{"id": 1, "x": 0, "y": 0, "z": 0, "fijo": True},
               {"id": 2, "x": 0, "y": 0, "z": 3},
               {"id": 3, "x": 1, "y": 0, "z": 3}],
     "secciones": SEC,
     "elementos": [{"id": 1, "n1": 1, "n2": 2, "seccion": "muro",
                    "tipo": "muro", "vecxz": [1, 0, 0]}],
     "brazos_rigidos": [{"maestro": 2, "esclavo": 3, "tipo": "beam"}],
     "cargas_nodales": [{"nodo": 3, "fx": 50.0}]}
r = construir_y_resolver(d)
n2 = [x for x in r['desplazamientos'] if x['id'] == 2][0]
n3 = [x for x in r['desplazamientos'] if x['id'] == 3][0]
check("el modelo con rigidLink resuelve", r['ok'])
check("el nodo colgado gira solidario con el eje del muro",
      abs(n2['ry'] - n3['ry']) < 1e-12,
      f"ry eje={n2['ry']:.6e}  ry cara={n3['ry']:.6e}")
# Brazo rigido: ux_esclavo = ux_maestro + ry_maestro * dz, con dz=0 aqui
check("traslacion consistente con el brazo",
      abs(n3['ux'] - n2['ux']) < 1e-12,
      f"ux eje={n2['ux']:.6e}  ux cara={n3['ux']:.6e}")
check("equilibrio con rigidLink",
      abs(sum(x['fx'] for x in r['reacciones']) + 50.0) < 1e-3)

# ------------------------------------------------------------
print("\n7. Entradas invalidas")
d = base(cargas_distribuidas=CARGAS_G)
d['nodos'][0]['restricciones'] = [1, 1, 1]
rechaza("restricciones de largo != 6", d, "6 valores")

d = base(cargas_distribuidas=CARGAS_G)
d['nodos'][0]['restricciones'] = [1, 1, 2, 0, 0, 0]
rechaza("restriccion distinta de 0/1", d, "solo acepta 0 o 1")

d = base(cargas_distribuidas=CARGAS_G)
d['diafragmas'] = [{"nodo_maestro": 999, "nodos": [5, 6]}]
rechaza("diafragma con maestro inexistente", d, "no existe")

d = base(cargas_distribuidas=CARGAS_G)
d['nodos'].append({"id": 99, "x": 2, "y": 2, "z": 3})
d['diafragmas'] = [{"nodo_maestro": 99, "nodos": [1, 5, 6]}]
rechaza("diafragma con nodos a distinta cota", d, "mismo plano")

d = base(cargas_distribuidas=CARGAS_G)
d['brazos_rigidos'] = [{"maestro": 5, "esclavo": 5}]
rechaza("brazo rigido a si mismo", d, "mismo nodo")

d = base(cargas_distribuidas=CARGAS_G)
d['elementos'][0]['seccion'] = "inventada"
rechaza("seccion inexistente", d, "no esta definida")

d = base(cargas_distribuidas=CARGAS_G)
d['elementos'][0]['vecxz'] = [0, 0, 1]
rechaza("vecxz paralelo al eje", d, "paralelo")

# ------------------------------------------------------------
print("\n" + "=" * 66)
if fallos:
    print(f"  {len(fallos)} TEST(S) FALLARON:")
    for f in fallos:
        print(f"    - {f}")
    raise SystemExit(1)
print("  TODOS LOS TESTS PASARON")
print("=" * 66)
