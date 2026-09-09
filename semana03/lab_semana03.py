"""Demostracion de demanda y superposicion lineal para Semana 3."""

import copy
import json
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(RAIZ / "comun"))

import calcular  # noqa: E402
import servidor_opensees as motor  # noqa: E402
from parametros import (  # noqa: E402
    q_Q,
    coef_sismico,
    fraccion_Q_sismica,
    lambda_G,
    lambda_Q,
    lambda_EX,
    lambda_EY,
)


def cargar_json(ruta):
    with ruta.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def validar_parametros():
    """Evita ejecutar la demostracion con entradas fisicamente invalidas."""
    if q_Q < 0:
        raise ValueError("Parametro invalido: q_Q no puede ser negativo")
    if coef_sismico < 0:
        raise ValueError("Parametro invalido: coef_sismico no puede ser negativo")
    if not 0 <= fraccion_Q_sismica <= 1:
        raise ValueError("Parametro invalido: fraccion_Q_sismica debe estar entre 0 y 1")


def escalar_caso(caso_original, factor):
    """Escala las cargas de un caso sin modificar el JSON original."""
    caso_nuevo = copy.deepcopy(caso_original)
    for carga in caso_nuevo.get("cargas_nodales", []):
        for clave in ("fx", "fy", "fz", "mx", "my", "mz"):
            if clave in carga:
                carga[clave] *= factor
    for carga in caso_nuevo.get("cargas_distribuidas", []):
        for clave in ("wx", "wy", "wz"):
            if clave in carga:
                carga[clave] *= factor
    return caso_nuevo


def error_relativo(valor, referencia):
    return abs(valor - referencia) / max(abs(referencia), 1e-12)


def niveles(modelo):
    """Devuelve (cota, nodo maestro) ordenados desde abajo hacia arriba."""
    nodos = {int(n["id"]): n for n in modelo["nodos"]}
    return sorted(
        ((float(nodos[int(d["nodo_maestro"])]["z"]), int(d["nodo_maestro"]))
         for d in modelo.get("diafragmas", [])),
        key=lambda item: item[0],
    )


def nivel_de_z(z, cotas):
    return min(range(len(cotas)), key=lambda i: abs(z - cotas[i]))


def peso_vertical_por_nivel(modelo, caso, cotas):
    """Suma como peso positivo las cargas verticales de un caso."""
    nodos = {int(n["id"]): n for n in modelo["nodos"]}
    elementos = {int(e["id"]): e for e in modelo["elementos"]}
    pesos = [0.0] * len(cotas)

    for carga in caso.get("cargas_nodales", []):
        nodo = nodos[int(carga["nodo"])]
        i = nivel_de_z(float(nodo["z"]), cotas)
        pesos[i] += -float(carga.get("fz", 0.0))

    for carga in caso.get("cargas_distribuidas", []):
        elemento = elementos[int(carga["elemento"])]
        n1, n2 = nodos[int(elemento["n1"])], nodos[int(elemento["n2"])]
        z1, z2 = float(n1["z"]), float(n2["z"])
        i = nivel_de_z((z1 + z2) / 2.0, cotas)
        largo = sum((float(n2[k]) - float(n1[k])) ** 2 for k in ("x", "y", "z")) ** 0.5
        pesos[i] += -float(carga.get("wz", 0.0)) * largo

    return pesos


def caso(modelo, nombre):
    return next(c for c in modelo["casos_de_carga"] if c["nombre"] == nombre)


def sismo_corregido(modelo, nombre, pesos, Cs):
    """Crea EX/EY localmente con W = G + 0.5 Q."""
    cotas_maestros = niveles(modelo)
    cota_base = min(float(n["z"]) for n in modelo["nodos"])
    alturas = [cota - cota_base for cota, _ in cotas_maestros]
    V = Cs * sum(pesos)
    denominador = sum(W * h for W, h in zip(pesos, alturas))
    cargas = []
    for W, h, (_, maestro) in zip(pesos, alturas, cotas_maestros):
        F = V * W * h / denominador
        cargas.append({"nodo": maestro, "fx": F if nombre == "EX" else 0.0,
                       "fy": F if nombre == "EY" else 0.0})
    return {"nombre": nombre, "cargas_nodales": cargas,
            "cargas_distribuidas": []}, V, [c["fx"] + c["fy"] for c in cargas]


def combinar_casos(casos, lambdas):
    """Suma cargas nodales y distribuidas de varios casos."""
    nodales = {}
    distribuidas = {}
    for nombre, factor in lambdas.items():
        for carga in casos[nombre].get("cargas_nodales", []):
            destino = nodales.setdefault(int(carga["nodo"]), {})
            for clave in ("fx", "fy", "fz", "mx", "my", "mz"):
                destino[clave] = destino.get(clave, 0.0) + factor * float(carga.get(clave, 0.0))
        for carga in casos[nombre].get("cargas_distribuidas", []):
            destino = distribuidas.setdefault(int(carga["elemento"]), {})
            for clave in ("wx", "wy", "wz"):
                destino[clave] = destino.get(clave, 0.0) + factor * float(carga.get(clave, 0.0))

    return {
        "nombre": "COMBINACION",
        "cargas_nodales": [{"nodo": n, **c} for n, c in nodales.items()],
        "cargas_distribuidas": [{"elemento": e, **c} for e, c in distribuidas.items()],
    }


def combinar_resultados(resultados, lambdas):
    """Combina algebraicamente desplazamientos, reacciones y fuerzas."""
    salida = {}
    for clave, identificador in (("desplazamientos", "id"),
                                 ("reacciones", "id"),
                                 ("fuerzas_elementos", "id")):
        por_id = {}
        for nombre, factor in lambdas.items():
            for registro in resultados[nombre][clave]:
                destino = por_id.setdefault(int(registro[identificador]), {})
                for campo, valor in registro.items():
                    if campo not in (identificador, "f"):
                        destino[campo] = destino.get(campo, 0.0) + factor * float(valor)
                    elif campo == "f":
                        destino[campo] = [
                            a + factor * b
                            for a, b in zip(destino.get(campo, [0.0] * len(valor)), valor)
                        ]
        salida[clave] = [{identificador: i, **registro}
                         for i, registro in por_id.items()]
    return salida


def imprimir_comparacion(etiqueta, algebraico, explicito):
    error = abs(algebraico - explicito)
    relativo = error_relativo(algebraico, explicito)
    print(f"{etiqueta}: superposicion={algebraico:.8g}, corrida={explicito:.8g}, "
          f"error={error:.3g}, relativo={relativo * 100:.3g} %")
    return relativo


def main():
    validar_parametros()
    modelo = cargar_json(RAIZ / "data/modelo/ingenieria.json")
    cotas = [cota for cota, _ in niveles(modelo)]
    caso_g = caso(modelo, "G")
    caso_q_base = caso(modelo, "Q")

    # El JSON contiene Q con el valor base vigente del benchmark. Se calcula
    # ese valor desde las cargas guardadas y se escala solo en memoria para
    # que q_Q pueda cambiar sin tocar benchmark_3d.py ni el JSON.
    vigas = [e for e in modelo["elementos"]
             if e.get("tipo", "").startswith("viga") and e.get("area_tributaria", 0) > 0]
    areas = sum(float(v["area_tributaria"]) for v in vigas)
    q_Q_base = sum(peso_vertical_por_nivel(modelo, caso_q_base, cotas)) / areas
    caso_q = escalar_caso(caso_q_base, q_Q / q_Q_base)
    cargas = [q_Q * float(v["area_tributaria"]) for v in vigas]
    Q_transferida = sum(cargas)

    pesos_G = peso_vertical_por_nivel(modelo, caso_g, cotas)
    pesos_Q = peso_vertical_por_nivel(modelo, caso_q, cotas)
    pesos_sismicos = [g + fraccion_Q_sismica * q
                      for g, q in zip(pesos_G, pesos_Q)]
    caso_ex, V_ex, fuerzas_ex = sismo_corregido(
        modelo, "EX", pesos_sismicos, coef_sismico)
    caso_ey, V_ey, fuerzas_ey = sismo_corregido(
        modelo, "EY", pesos_sismicos, coef_sismico)

    # Esta es la conexion local de parametros con la corrida explicita. El
    # motor resuelve una copia en memoria; el benchmark y los JSON no cambian.
    casos = {"G": caso_g, "Q": caso_q, "EX": caso_ex, "EY": caso_ey}
    datos = copy.deepcopy(modelo)
    datos["casos_de_carga"] = list(casos.values())
    salida = motor.construir_y_resolver(datos)
    resultados = {r["nombre"]: r for r in salida["casos"]}

    print("=" * 60)
    print("SEMANA 3 - PARAMETROS DE LA ACTIVIDAD")
    print("=" * 60)
    print(f"\nCarga viva q_Q               = {q_Q:.2f} kN/m2")
    print(f"Coeficiente sismico Cs      = {coef_sismico:.2f}")
    print(f"Fraccion Q para masa sismica= {fraccion_Q_sismica:.2f}")
    print("\nCombinacion:")
    print(f"{lambda_G:.2f} G + {lambda_Q:.2f} Q + "
          f"{lambda_EX:.2f} EX + {lambda_EY:.2f} EY")

    print("\n[A] CARGA VIVA")
    Q_reacciones = sum(float(r["fz"]) for r in resultados["Q"]["reacciones"])
    error_Q = abs(Q_transferida - Q_reacciones)
    Q_niveles = peso_vertical_por_nivel(modelo, caso_q, cotas)
    print(f"q_Q = {q_Q:.4f} kN/m2")
    print(f"Numero de vigas = {len(vigas)}")
    print(f"Area total = {areas:.4f} m2")
    print(f"Q esperada = {q_Q * areas:.4f} kN")
    print(f"Q transferida = {Q_transferida:.4f} kN")
    print("Q por nivel (kN) = " + ", ".join(f"{q:.2f}" for q in Q_niveles))
    print(f"Reacciones Rz = {Q_reacciones:.4f} kN")
    print(f"Error absoluto = {error_Q:.6f} kN")
    print(f"Error relativo = {error_relativo(Q_transferida, Q_reacciones) * 100:.6f} %")
    print("OK" if error_relativo(Q_transferida, Q_reacciones) < 0.0001 else "REVISAR")

    print("\n[B] SISMO EX / EY")
    print(f"Peso sismico = G + {fraccion_Q_sismica:.2f} Q")
    print(f"Cs = {coef_sismico:.4f}")
    print("Pesos por nivel (kN): " + ", ".join(f"{p:.2f}" for p in pesos_sismicos))
    print(f"V_EX = {V_ex:.4f} kN; sum(F_EX) = {sum(fuerzas_ex):.4f} kN; "
          f"error = {abs(sum(fuerzas_ex) - V_ex):.3g} kN")
    print(f"V_EY = {V_ey:.4f} kN; sum(F_EY) = {sum(fuerzas_ey):.4f} kN; "
          f"error = {abs(sum(fuerzas_ey) - V_ey):.3g} kN")

    eq_ex = calcular.equilibrio(modelo, caso_ex, resultados["EX"])
    eq_ey = calcular.equilibrio(modelo, caso_ey, resultados["EY"])
    print(f"Equilibrio EX: reaccion base = {eq_ex['reaccion_kN'][0]:.4f} kN, "
          f"error = {abs(eq_ex['error_kN'][0]):.3g} kN")
    print(f"Equilibrio EY: reaccion base = {eq_ey['reaccion_kN'][1]:.4f} kN, "
          f"error = {abs(eq_ey['error_kN'][1]):.3g} kN")
    techo = niveles(modelo)[-1][1]
    disp_ex = next(d for d in resultados["EX"]["desplazamientos"] if d["id"] == techo)
    disp_ey = next(d for d in resultados["EY"]["desplazamientos"] if d["id"] == techo)
    print(f"Techo EX: ux = {disp_ex['ux']:.6g} m, uy = {disp_ex['uy']:.6g} m, "
          f"rz = {disp_ex['rz']:.6g} rad")
    print(f"Techo EY: ux = {disp_ey['ux']:.6g} m, uy = {disp_ey['uy']:.6g} m, "
          f"rz = {disp_ey['rz']:.6g} rad")

    print("\n[C] SUPERPOSICION")
    lambdas = {"G": lambda_G, "Q": lambda_Q,
               "EX": lambda_EX, "EY": lambda_EY}
    print(f"Combinacion = {lambda_G:.2f}G + {lambda_Q:.2f}Q + "
          f"{lambda_EX:.2f}EX + {lambda_EY:.2f}EY")
    algebraico = combinar_resultados(resultados, lambdas)
    combinado = combinar_casos(casos, lambdas)
    datos_explicitos = copy.deepcopy(modelo)
    datos_explicitos["casos_de_carga"] = [combinado]
    explicito = motor.construir_y_resolver(datos_explicitos)["casos"][0]

    maestros = niveles(modelo)
    soporte = next(n for n in modelo["nodos"] if n.get("restricciones") and n["z"] == min(x["z"] for x in modelo["nodos"]))
    viga = next(e for e in modelo["elementos"] if e.get("tipo", "").startswith("viga"))
    disp_a = next(d["ux"] for d in algebraico["desplazamientos"] if d["id"] == techo)
    disp_e = next(d["ux"] for d in explicito["desplazamientos"] if d["id"] == techo)
    reac_a = next(r["fz"] for r in algebraico["reacciones"] if r["id"] == soporte["id"])
    reac_e = next(r["fz"] for r in explicito["reacciones"] if r["id"] == soporte["id"])
    fuerza_a = next(f["f"][4] for f in algebraico["fuerzas_elementos"] if f["id"] == viga["id"])
    fuerza_e = next(f["f"][4] for f in explicito["fuerzas_elementos"] if f["id"] == viga["id"])
    errores = [
        imprimir_comparacion("Desplazamiento ux techo (m)", disp_a, disp_e),
        imprimir_comparacion("Reaccion fz apoyo (kN)", reac_a, reac_e),
        imprimir_comparacion("Fuerza local My elemento (kN m)", fuerza_a, fuerza_e),
    ]
    print("OK" if max(errores) < 1e-4 else "REVISAR")
    print("\nLa igualdad se espera porque K u = F y el modelo es lineal elastico.")


if __name__ == "__main__":
    main()
