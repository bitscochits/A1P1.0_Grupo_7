"""
================================================================
 export_unity.py
================================================================
 Convierte el modelo del edificio (benchmark_3d.py) al contrato
 que consume Unity: modelo_unity.json.

 Es el puente que faltaba. benchmark_3d.py terminaba diciendo
 "export_unity.py no encontrado; Unity no se actualiza": el
 edificio se calculaba pero no se podia ver.

 El JSON que produce es el MISMO formato que genera_json_unity.py
 para el benchmark, asi que el visor, el analizador y el editor
 funcionan sin cambiarles una linea.

 Uso:
     python export_unity.py

 Salida:
     modelo_unity_edificio.json          (junto a este script)
     unity/Assets/StreamingAssets/...    (si existe la carpeta)
================================================================
"""

import json
import os

import openseespy.opensees as ops

# OJO: benchmark_3d NO se importa aca arriba. benchmark_3d importa a
# este modulo al final de su ejecucion, y si el import fuera mutuo a
# nivel de modulo, export_model todavia no estaria definida cuando el
# lo llama. Se importa dentro de las funciones.

RAIZ = os.path.dirname(os.path.abspath(__file__))


def construir_json(desplazamientos=None):
    """
    Arma el modelo y lo resuelve bajo 'resolver_caso' para dejar la
    deformada precalculada en el JSON (Unity la dibuja sin servidor).
    """
    import benchmark_3d as ed          # ya cargado cuando el nos llama
    import modelo_benchmark as mb

    coords, cols, vx, vy, masters, muros, wall_nodes = ed.build_model()
    area_por_viga, A_piso, _ = ed.tributarias()
    vigas = ed.datos_vigas()

    # --- Secciones (LISTA: JsonUtility no lee diccionarios) ---
    secciones = [
        {"nombre": "columna", "A": ed.A_col, "Iy": ed.Iy_col,
         "Iz": ed.Iz_col, "J": ed.J_col},
        {"nombre": "viga_x", "A": ed.A_beamX, "Iy": ed.Iy_beamX,
         "Iz": ed.Iz_beamX, "J": ed.J_beamX},
        {"nombre": "viga_y", "A": ed.A_beamY, "Iy": ed.Iy_beamY,
         "Iz": ed.Iz_beamY, "J": ed.J_beamY},
    ]
    # Una seccion por muro: pueden tener largos distintos.
    for im, (dirn, largo, A, Iy, Iz, J) in ed.MUROS_PROPS.items():
        secciones.append({"nombre": f"muro_{im}", "A": A, "Iy": Iy,
                          "Iz": Iz, "J": J})

    # --- Nodos ---
    nodos = []
    n_base = ed.nNodesPerFloor
    maestros = set(masters.values())
    for nid, (x, y, z) in coords.items():
        # Deformada del caso G. Viene del archivo de resultados que ya
        # escribio benchmark_3d; el dominio vivo tiene el ultimo caso
        # resuelto (EY), que no es el que queremos precalcular.
        d = (desplazamientos or {}).get(str(nid), [0.0] * 6)
        bases_muro = {wall_nodes[(im, 0)] for im in range(len(ed.MUROS))}
        empotrado = nid <= n_base or nid in bases_muro
        if nid in maestros:
            # Maestro de diafragma: solo se restringe fuera del plano.
            restr = [0, 0, 1, 1, 1, 0]
        elif empotrado:
            restr = [1, 1, 1, 1, 1, 1]
        else:
            restr = [0, 0, 0, 0, 0, 0]

        nodos.append({
            "id": nid, "x": x, "y": y, "z": z,
            "fijo": empotrado,
            # Los maestros son nodos de control, no nudos de la
            # estructura: Unity los dibuja chicos y se pueden apagar.
            "auxiliar": nid in maestros,
            "restricciones": restr,
            "ux": round(d[0], 8), "uy": round(d[1], 8), "uz": round(d[2], 8),
        })

    # --- Elementos ---
    elementos = []
    for tag in cols:
        n1, n2 = ops.eleNodes(tag)
        elementos.append({"id": tag, "n1": n1, "n2": n2,
                          "seccion": "columna", "tipo": "columna",
                          "area_tributaria": 0.0, "w_gravedad": 0.0})
    # Las vigas llevan su area tributaria y la carga que reciben, para
    # que el visor las pueda mostrar al seleccionar (el servidor las
    # ignora; son datos de preproceso, no de calculo).
    for tag, sec in [(t, "viga_x") for t in vx] + [(t, "viga_y") for t in vy]:
        n1, n2 = ops.eleNodes(tag)
        A = area_por_viga.get(tag, 0.0)
        L = vigas[tag][0]
        elementos.append({
            "id": tag, "n1": n1, "n2": n2, "seccion": sec, "tipo": sec,
            "area_tributaria": round(A, 4),
            "w_gravedad": round(ed.w_slab_dead * A / L
                                + ed.gamma * vigas[tag][2], 4),
        })

    # --- Muros (columna ancha) ---
    # vecxz apunta a lo largo del muro para que su eje fuerte quede en
    # su propio plano. Sin ese vector, el servidor lo orientaria solo
    # segun la geometria y un muro no tiene orientacion "obvia".
    for im, (dirn, largo, A, Iy, Iz, J) in ed.MUROS_PROPS.items():
        vec = [1.0, 0.0, 0.0] if dirn == 'X' else [0.0, 1.0, 0.0]
        for lev in range(ed.nLevels - 1):
            tag = ed.WALL[(im, lev)]
            n1, n2 = ops.eleNodes(tag)
            elementos.append({
                "id": tag, "n1": n1, "n2": n2,
                "seccion": f"muro_{im}", "tipo": "muro",
                "vecxz": vec,
                "area_tributaria": 0.0, "w_gravedad": 0.0,
            })

    # --- Poligonos tributarios ---
    # La GEOMETRIA se calcula en Python (modelo_benchmark) y Unity solo
    # la dibuja. Se guardan como arrays planos vx/vy + una cota z:
    # JsonUtility no sabe leer listas de listas.
    tributarias_poly = []
    for lev in range(1, ed.nLevels):
        z = ed.heights[lev]
        for ix in range(ed.nX - 1):
            for iy in range(ed.nY - 1):
                polis = mb.poligonos_tributarios(
                    ed.X_axes[ix], ed.X_axes[ix + 1],
                    ed.Y_axes[iy], ed.Y_axes[iy + 1])
                destino = {
                    'y0': ed.XBEAM[(lev, ix, iy)],
                    'y1': ed.XBEAM[(lev, ix, iy + 1)],
                    'x0': ed.YBEAM[(lev, ix, iy)],
                    'x1': ed.YBEAM[(lev, ix + 1, iy)],
                }
                for po in polis:
                    tributarias_poly.append({
                        "elemento": destino[po['lado']],
                        "forma": po['forma'],
                        "area": round(po['area'], 4),
                        "vx": [round(v[0], 4) for v in po['vertices']],
                        "vy": [round(v[1], 4) for v in po['vertices']],
                        "z": z,
                    })

    # --- Diafragmas ---
    diafragmas = []
    for lev, m in masters.items():
        diafragmas.append({
            "nodo_maestro": m,
            "nodos": ([lev * ed.nNodesPerFloor + ix * ed.nY + iy + 1
                       for ix in range(ed.nX) for iy in range(ed.nY)]
                      + [wall_nodes[(im, lev)] for im in range(len(ed.MUROS))]),
            "perpendicular": 3,
        })

    # --- Casos de carga ---
    def distribuidas(q, con_peso):
        out = []
        for tag, A in area_por_viga.items():
            L, _dir, A_sec = vigas[tag]
            w = q * A / L + (ed.gamma * A_sec if con_peso else 0.0)
            out.append({"elemento": tag, "wy": 0.0, "wz": -round(w, 6),
                        "wx": 0.0})
        return out

    def nodales_columnas():
        """Peso propio de columnas, mitad en cada extremo."""
        acum = {}
        for lev in range(ed.nLevels - 1):
            h = ed.heights[lev + 1] - ed.heights[lev]
            W = ed.gamma * ed.A_col * h / 2.0
            for ix in range(ed.nX):
                for iy in range(ed.nY):
                    a = lev * ed.nNodesPerFloor + ix * ed.nY + iy + 1
                    b = (lev + 1) * ed.nNodesPerFloor + ix * ed.nY + iy + 1
                    acum[a] = acum.get(a, 0.0) + W
                    acum[b] = acum.get(b, 0.0) + W
        return [{"nodo": n, "fz": -round(w, 6)} for n, w in acum.items()]

    W_niv = ed.peso_sismico()
    V = ed.COEF_SISMICO * sum(W_niv.values())
    denom = sum(W_niv[l] * ed.heights[l] for l in W_niv)

    def sismo(comp):
        return [{"nodo": masters[l],
                 comp: round(V * (W_niv[l] * ed.heights[l]) / denom, 4)}
                for l in W_niv]

    casos = [
        {"nombre": "G", "descripcion": "Peso propio + losa + terminaciones",
         "cargas_distribuidas": distribuidas(ed.w_slab_dead, True),
         "cargas_nodales": nodales_columnas()},
        {"nombre": "Q", "descripcion": "Sobrecarga de uso",
         "cargas_distribuidas": distribuidas(ed.w_live_val, False),
         "cargas_nodales": []},
        {"nombre": "EX", "descripcion": "Sismo pseudoestatico en X",
         "cargas_distribuidas": [], "cargas_nodales": sismo("fx")},
        {"nombre": "EY", "descripcion": "Sismo pseudoestatico en Y",
         "cargas_distribuidas": [], "cargas_nodales": sismo("fy")},
    ]

    return {
        "info": {
            "descripcion": "Edificio de Ingenieria UAndes - modelo global v1",
            "unidades": "m, kN, kPa",
            "caso_precalculado": "G",
            "nota": (f"{len(nodos)} nodos, {len(elementos)} elementos, "
                     f"{len(diafragmas)} diafragmas. Area de piso "
                     f"{A_piso:.1f} m2."),
        },
        "material": {"fpc_MPa": ed.fpc, "poisson": 0.2, "gamma": ed.gamma},
        "secciones": secciones,
        "nodos": nodos,
        "elementos": elementos,
        "diafragmas": diafragmas,
        "areas_tributarias": tributarias_poly,
        "brazos_rigidos": [],
        "casos_de_carga": casos,
    }


def export_model(X_axes=None, Y_axes=None, heights=None,
                 col_tags=None, bx_tags=None, by_tags=None,
                 supports=None, label=None, extra=None,
                 results_file="results/benchmark_results.json"):
    """
    Firma que llama benchmark_3d.py al terminar. Los argumentos de
    geometria se aceptan por compatibilidad pero no hacen falta: el
    modelo se reconstruye desde benchmark_3d, que es la fuente de
    verdad. Lo que si se usa es results_file, de donde sale la
    deformada del caso G.
    """
    desp = None
    ruta = results_file if os.path.isabs(results_file)         else os.path.join(RAIZ, results_file)
    if os.path.exists(ruta):
        with open(ruta, encoding='utf-8') as f:
            desp = json.load(f).get('G', {}).get('displacements')

    modelo = construir_json(desplazamientos=desp)
    if label:
        modelo['info']['descripcion'] = label
    if extra:
        modelo['info']['extra'] = {k: str(v) for k, v in extra.items()}

    return escribir(modelo)


def escribir(modelo):

    destinos = [os.path.join(RAIZ, 'modelo_unity_edificio.json')]
    sa = os.path.join(RAIZ, 'unity', 'Assets', 'StreamingAssets')
    if os.path.isdir(sa):
        destinos.append(os.path.join(sa, 'modelo_unity_edificio.json'))

    for d in destinos:
        with open(d, 'w', encoding='utf-8') as f:
            json.dump(modelo, f, indent=2)
        print(f"  escrito: {os.path.relpath(d, RAIZ)}")

    print(f"\n  nodos      : {len(modelo['nodos'])}")
    print(f"  elementos  : {len(modelo['elementos'])}")
    print(f"  diafragmas : {len(modelo['diafragmas'])}")
    print(f"  poligonos  : {len(modelo['areas_tributarias'])}")
    print(f"  muros      : {sum(1 for e in modelo['elementos'] if e['tipo']=='muro')}")
    print(f"  casos      : {[c['nombre'] for c in modelo['casos_de_carga']]}")

    # El JSON tiene que ser enviable al servidor TAL CUAL. Se verifica
    # aca para no descubrirlo recien dentro de Unity.
    try:
        from servidor_opensees import construir_y_resolver
    except ImportError:
        print("\n  (servidor no importable; se omite el round-trip)")
        return

    print("\n  Round-trip por el servidor...")
    r = construir_y_resolver(modelo)
    if not r['ok']:
        raise SystemExit(f"  *** El servidor rechazo el modelo: {r['error']}")

    # OJO: solo los apoyos de la base. Los nodos MAESTROS de diafragma
    # tambien aparecen en 'reacciones' (llevan restringidos uz, rx, ry),
    # y nodeReaction ahi devuelve la fuerza de la RESTRICCION, no una
    # reaccion de apoyo: como el corte sismico se aplica en el maestro,
    # reaparece con signo cambiado y el total sale al doble.
    base = {n['id'] for n in modelo['nodos'] if n['fijo']}
    for c in r['casos']:
        ap = [x for x in c['reacciones'] if x['id'] in base]
        print(f"    {c['nombre']:<3} suma reacciones en la base  "
              f"Fx={sum(x['fx'] for x in ap):11.2f}  "
              f"Fy={sum(x['fy'] for x in ap):11.2f}  "
              f"Fz={sum(x['fz'] for x in ap):11.2f} kN")
    if r['avisos']:
        print(f"    avisos: {len(r['avisos'])}")
    print("  -> OK, el JSON del edificio es enviable al servidor.")
    return modelo


if __name__ == '__main__':
    # Importar benchmark_3d dispara su analisis completo, y el llama a
    # export_model() al terminar. Asi hay un solo camino de ejecucion.
    import benchmark_3d   # noqa: F401
