"""Exporta a Unity lo que agrega Semana 3: el sismo y la enfierradura.

La regla del repositorio es que el calculo vive en Python y viaja por
JSON; Unity solo muestra. Este script no dibuja nada: deja en
`data/unity/semana03.json` la geometria y los numeros ya resueltos para
que el visor los lea.

El archivo es un anexo. No toca `modelo_unity.json`, asi que el visor,
el analizador y el editor siguen funcionando sin cambios.

Uso:
    python semana03/exportar_unity.py
"""

import json
import shutil
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(RAIZ / "comun"))

import capacidad_ha as ha          # noqa: E402
import lab_semana03 as lab         # noqa: E402
from parametros import (           # noqa: E402
    coef_sismico,
    fraccion_Q_sismica,
    q_Q,
    patron_sismico,
    k_patron,
    lambda_G,
    lambda_Q,
    lambda_EX,
    lambda_EY,
)

SALIDA = RAIZ / "data" / "unity" / "semana03.json"
STREAMING = RAIZ / "unity" / "Assets" / "StreamingAssets"


def bloque_sismo(modelo):
    """Fuerza lateral por nivel, con el patron que este configurado."""
    cotas = [cota for cota, _ in lab.niveles(modelo)]
    nodos = {int(n["id"]): n for n in modelo["nodos"]}

    caso_q = lab.escalar_caso(lab.caso(modelo, "Q"), 1.0)
    vigas = [e for e in modelo["elementos"]
             if e.get("tipo", "").startswith("viga")
             and e.get("area_tributaria", 0) > 0]
    areas = sum(float(v["area_tributaria"]) for v in vigas)
    q_base = sum(lab.peso_vertical_por_nivel(modelo, caso_q, cotas)) / areas
    caso_q = lab.escalar_caso(caso_q, q_Q / q_base)

    pesos_G = lab.peso_vertical_por_nivel(modelo, lab.caso(modelo, "G"), cotas)
    pesos_Q = lab.peso_vertical_por_nivel(modelo, caso_q, cotas)
    pesos = [g + fraccion_Q_sismica * q for g, q in zip(pesos_G, pesos_Q)]

    # sismo_corregido devuelve (caso, V, fuerzas); el reparto se pide
    # aparte a la misma funcion que usa el lab, para no duplicarlo.
    caso_ex, V, fuerzas = lab.sismo_corregido(
        modelo, "EX", pesos, coef_sismico)
    caso_ey, _V, _f = lab.sismo_corregido(
        modelo, "EY", pesos, coef_sismico)
    cota_base = min(float(n["z"]) for n in modelo["nodos"])
    factores = lab.factores_patron(pesos, [c - cota_base for c in cotas])

    descripcion = lab.texto_patron_actual()
    bloque = {
        "patron": descripcion,
        "Cs": coef_sismico,
        "fraccion_Q_sismica": fraccion_Q_sismica,
        "corte_basal_kN": round(V, 4),
        "fuerza_maxima_kN": round(max(fuerzas), 4),
        "niveles": [
            {
                "nodo_maestro": maestro,
                # Se exportan las tres coordenadas para que el visor no
                # tenga que cruzar este anexo con el modelo.
                "x": round(float(nodos[maestro]["x"]), 4),
                "y": round(float(nodos[maestro]["y"]), 4),
                "z": round(float(nodos[maestro]["z"]), 4),
                "peso_kN": round(W, 3),
                "fraccion": round(f, 6),
                "F_kN": round(F, 4),
            }
            for (_cota, maestro), W, f, F
            in zip(lab.niveles(modelo), pesos, factores, fuerzas)
        ],
    }
    return bloque, caso_q, caso_ex, caso_ey


def bloque_armadura(modelo):
    """Jaula de la columna: barras, estribo exterior y estribo en rombo.

    Se ancla a la columna mas cargada del modelo para que el visor sepa
    donde dibujarla; las coordenadas de la jaula son locales a la
    seccion (y, z), con el origen en su centro.
    """
    nodos = {int(n["id"]): n for n in modelo["nodos"]}
    columnas = [e for e in modelo["elementos"] if e.get("tipo") == "columna"]

    resultados = json.loads(
        (RAIZ / "data/resultados/ingenieria_G.json").read_text(encoding="utf-8"))
    axial = {int(f["id"]): abs(f["f"][0]) for f in resultados["fuerzas_elementos"]}
    elegida = max(columnas, key=lambda e: axial.get(int(e["id"]), 0.0))

    hc = ha.H / 2 - ha.RECUBRIMIENTO
    bc = ha.B / 2 - ha.RECUBRIMIENTO
    return {
        "columna_id": int(elegida["id"]),
        "n1": int(elegida["n1"]),
        "n2": int(elegida["n2"]),
        "axial_G_kN": round(axial.get(int(elegida["id"]), 0.0), 3),
        "b": ha.B,
        "h": ha.H,
        "recubrimiento": ha.RECUBRIMIENTO,
        "diametro_barra": ha.DIAMETRO_BARRA,
        "diametro_estribo": ha.DIAMETRO_ESTRIBO,
        "espaciamiento_estribo": 0.10,
        "cuantia_pct": round(ha.CUANTIA * 100, 4),
        "as_total_cm2": round(ha.AS_TOTAL * 1e4, 3),
        "procedencia": ("numero de barras, disposicion y estribos: lamina "
                        "2017_67-000; diametro phi16 supuesto"),
        "barras": [{"y": round(y, 5), "z": round(z, 5)} for y, z in ha.BARRAS],
        # Poligonos cerrados, en coordenadas de seccion.
        "estribo_exterior": [{"y": y, "z": z} for y, z in
                             ((hc, bc), (hc, -bc), (-hc, -bc), (-hc, bc))],
        "estribo_rombo": [{"y": y, "z": z} for y, z in
                          ((hc, 0.0), (0.0, -bc), (-hc, 0.0), (0.0, bc))],
        "nodo_inferior": {k: float(nodos[int(elegida["n1"])][k])
                          for k in ("x", "y", "z")},
        "nodo_superior": {k: float(nodos[int(elegida["n2"])][k])
                          for k in ("x", "y", "z")},
        # Las 82 columnas, para poder enfierrar todas. Se entregan por id
        # de nodo: asi el visor puede moverlas con la deformada sin
        # recalcular nada.
        "columnas": [
            {"id": int(e["id"]), "n1": int(e["n1"]), "n2": int(e["n2"]),
             "axial_G_kN": round(axial.get(int(e["id"]), 0.0), 2)}
            for e in sorted(columnas, key=lambda c: int(c["id"]))
        ],
    }


def _flechas_de_caso(modelo, caso, factor=1.0):
    """Convierte un caso de carga en flechas ya resueltas.

    Las cargas distribuidas se reducen a UNA flecha en el centro de la
    barra, con la resultante w*L: dibujar la carga repartida viga por
    viga daria miles de objetos y no se leeria mejor.
    """
    nodos = {int(n["id"]): n for n in modelo["nodos"]}
    elementos = {int(e["id"]): e for e in modelo["elementos"]}
    flechas = []

    for c in caso.get("cargas_nodales", []):
        n = nodos[int(c["nodo"])]
        fx = factor * float(c.get("fx", 0.0))
        fy = factor * float(c.get("fy", 0.0))
        fz = factor * float(c.get("fz", 0.0))
        if abs(fx) + abs(fy) + abs(fz) < 1e-9:
            continue
        flechas.append({"x": float(n["x"]), "y": float(n["y"]),
                        "z": float(n["z"]), "fx": fx, "fy": fy, "fz": fz})

    for c in caso.get("cargas_distribuidas", []):
        e = elementos[int(c["elemento"])]
        n1, n2 = nodos[int(e["n1"])], nodos[int(e["n2"])]
        largo = sum((float(n2[k]) - float(n1[k])) ** 2
                    for k in ("x", "y", "z")) ** 0.5
        fx = factor * float(c.get("wx", 0.0)) * largo
        fy = factor * float(c.get("wy", 0.0)) * largo
        fz = factor * float(c.get("wz", 0.0)) * largo
        if abs(fx) + abs(fy) + abs(fz) < 1e-9:
            continue
        flechas.append({
            "x": (float(n1["x"]) + float(n2["x"])) / 2.0,
            "y": (float(n1["y"]) + float(n2["y"])) / 2.0,
            "z": (float(n1["z"]) + float(n2["z"])) / 2.0,
            "fx": fx, "fy": fy, "fz": fz})

    for f in flechas:
        f["kN"] = (f["fx"] ** 2 + f["fy"] ** 2 + f["fz"] ** 2) ** 0.5
        for k in ("x", "y", "z", "fx", "fy", "fz", "kN"):
            f[k] = round(f[k], 5)
    return flechas


def bloque_cargas(modelo, caso_q, caso_ex, caso_ey):
    """G, Q, EX, EY y la combinacion, cada uno como lista de flechas.

    La combinacion se arma aca y no en Unity: el repositorio manda que
    todo calculo viva en Python. Los lambda salen de parametros.py, asi
    que cambiarlos ahi cambia lo que se dibuja.
    """
    casos = [
        ("G", "peso propio y carga muerta", lab.caso(modelo, "G"), 1.0),
        ("Q", f"carga viva q_Q = {q_Q:g} kN/m2", caso_q, 1.0),
        ("EX", "sismo en X", caso_ex, 1.0),
        ("EY", "sismo en Y", caso_ey, 1.0),
    ]

    salida = []
    for nombre, descripcion, caso, factor in casos:
        flechas = _flechas_de_caso(modelo, caso, factor)
        salida.append({
            "caso": nombre,
            "descripcion": descripcion,
            "maxima_kN": round(max((f["kN"] for f in flechas), default=0.0), 4),
            "total_kN": round(sum(f["kN"] for f in flechas), 4),
            "flechas": flechas,
        })

    combinadas = []
    for (nombre, _d, caso, _f), lam in zip(
            casos, (lambda_G, lambda_Q, lambda_EX, lambda_EY)):
        if lam:
            combinadas.extend(_flechas_de_caso(modelo, caso, lam))
    salida.append({
        "caso": "COMBINACION",
        "descripcion": (f"{lambda_G:g}G + {lambda_Q:g}Q + "
                        f"{lambda_EX:g}EX + {lambda_EY:g}EY"),
        "maxima_kN": round(max((f["kN"] for f in combinadas), default=0.0), 4),
        "total_kN": round(sum(f["kN"] for f in combinadas), 4),
        "flechas": combinadas,
    })
    return salida


def bloque_deformadas():
    """Desplazamientos de EX y EY, listos para VisorEstructura.

    El visor ya sabe dibujar una deformada: recibe una lista de DespNodo
    y la aplica. Aca solo se le entrega la del caso sismico, con los
    mismos nombres de campo que espera.
    """
    salida = []
    for caso in ("EX", "EY"):
        ruta = RAIZ / f"data/resultados/ingenieria_{caso}.json"
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        desplazamientos = [
            {
                "id": int(d["id"]),
                "ux": round(float(d.get("ux", 0.0)), 8),
                "uy": round(float(d.get("uy", 0.0)), 8),
                "uz": round(float(d.get("uz", 0.0)), 8),
                "rx": round(float(d.get("rx", 0.0)), 8),
                "ry": round(float(d.get("ry", 0.0)), 8),
                "rz": round(float(d.get("rz", 0.0)), 8),
            }
            for d in datos["desplazamientos"]
        ]
        maximo = max((d["ux"] ** 2 + d["uy"] ** 2) ** 0.5
                     for d in desplazamientos)
        salida.append({
            "caso": caso,
            "max_horizontal_mm": round(maximo * 1000.0, 3),
            "desplazamientos": desplazamientos,
        })
    return salida


def main():
    modelo = json.loads(
        (RAIZ / "data/modelo/ingenieria.json").read_text(encoding="utf-8"))

    xs = [float(n["x"]) for n in modelo["nodos"]]
    ys = [float(n["y"]) for n in modelo["nodos"]]
    zs = [float(n["z"]) for n in modelo["nodos"]]

    sismo, caso_q, caso_ex, caso_ey = bloque_sismo(modelo)

    datos = {
        "info": {
            "descripcion": "Anexo de Semana 3 para el visor: sismo y armadura",
            "unidades": "m, kN",
            "nota": ("Calculado por semana03/exportar_unity.py. Unity solo "
                     "dibuja; el calculo vive en Python."),
        },
        # Caja del edificio, para que el visor sepa donde poner la vista
        # de detalle sin que se encime con la estructura.
        "caja": {
            "x_min": round(min(xs), 3), "x_max": round(max(xs), 3),
            "y_min": round(min(ys), 3), "y_max": round(max(ys), 3),
            "z_min": round(min(zs), 3), "z_max": round(max(zs), 3),
        },
        "sismo": sismo,
        "armadura": bloque_armadura(modelo),
        "deformadas": bloque_deformadas(),
        "cargas": bloque_cargas(modelo, caso_q, caso_ex, caso_ey),
    }

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(datos, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    if STREAMING.is_dir():
        shutil.copy2(SALIDA, STREAMING / "semana03.json")

    s, a = datos["sismo"], datos["armadura"]
    print("ANEXO SEMANA 3 PARA UNITY")
    print(f"\n[SISMO]  patron {s['patron']}, Cs = {s['Cs']:.2f}")
    print(f"  corte basal = {s['corte_basal_kN']:.2f} kN")
    for n in s["niveles"]:
        print(f"    z = {n['z']:6.2f} m   nodo {n['nodo_maestro']:4}   "
              f"W = {n['peso_kN']:9.2f} kN   {n['fraccion'] * 100:6.2f} %   "
              f"F = {n['F_kN']:9.2f} kN")
    suma = sum(n["F_kN"] for n in s["niveles"])
    print(f"  suma de fuerzas = {suma:.2f} kN  "
          f"(error {abs(suma - s['corte_basal_kN']):.4g} kN)")

    print(f"\n[ARMADURA]  columna {a['columna_id']} "
          f"(la mas cargada: {a['axial_G_kN']:.1f} kN en G)")
    print(f"  {len(a['barras'])} barras phi{a['diametro_barra'] * 1000:.0f}, "
          f"cuantia {a['cuantia_pct']:.2f} %")
    print(f"  estribos phi{a['diametro_estribo'] * 1000:.0f} a "
          f"{a['espaciamiento_estribo'] * 100:.0f} cm, exterior + rombo")
    print(f"  entre {a['nodo_inferior']} y {a['nodo_superior']}")
    print(f"  columnas enfierrables: {len(a['columnas'])}")

    print("\n[DEFORMADAS]")
    for d in datos["deformadas"]:
        print(f"  {d['caso']:4} {len(d['desplazamientos']):4} nodos   "
              f"max horizontal = {d['max_horizontal_mm']:7.2f} mm")

    print("\n[CARGAS]")
    for c in datos["cargas"]:
        print(f"  {c['caso']:12} {len(c['flechas']):4} flechas   "
              f"max {c['maxima_kN']:9.2f} kN   {c['descripcion']}")

    print(f"\nEscrito: {SALIDA}")
    if STREAMING.is_dir():
        print(f"Copiado: {STREAMING / 'semana03.json'}")


if __name__ == "__main__":
    main()
