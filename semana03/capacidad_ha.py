"""Capacidad aproximada de una columna de hormigon armado de 0.50 x 0.50 m.

La armadura es un supuesto de laboratorio: el modelo global no contiene
armaduras de hormigon extraidas desde planos.
"""

import math
from pathlib import Path

import matplotlib.pyplot as plt
import openseespy.opensees as ops


RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "semana03" / "resultados"

# SUPUESTO DE LABORATORIO - NO EXTRAIDO DE PLANOS.
B = H = 0.50
RECUBRIMIENTO = 0.05
DIAMETRO_BARRA = 0.020
FY = 420_000.0                 # kPa = 420 MPa
ES = 200_000_000.0             # kPa = 200 GPa
FPC = 28_000.0                 # kPa = 28 MPa, igual al modelo global
EC = 4700.0 * math.sqrt(28.0) * 1000.0
AREA_BARRA = math.pi * DIAMETRO_BARRA ** 2 / 4.0


def fibras_numericas(n=36):
    """Fibras de hormigon y 10 barras para integrar P y M."""
    fibras = []
    dy, dz = H / n, B / n
    for iy in range(n):
        y = -H / 2 + (iy + 0.5) * dy
        for iz in range(n):
            z = -B / 2 + (iz + 0.5) * dz
            fibras.append((y, dy * dz, "hormigon"))

    y_barra = H / 2 - RECUBRIMIENTO - DIAMETRO_BARRA / 2
    z_barra = B / 2 - RECUBRIMIENTO - DIAMETRO_BARRA / 2
    for y in (-y_barra, y_barra):
        for z in (-z_barra, 0.0, z_barra):
            fibras.append((y, AREA_BARRA, "acero"))
    for z in (-z_barra, z_barra):
        fibras.append((0.0, AREA_BARRA, "acero"))
    return fibras


def tension_hormigon(epsilon):
    """Ley comprimida simple, coherente con Concrete01."""
    if epsilon >= 0.0:
        return 0.0
    x = abs(epsilon)
    if x <= 0.002:
        return -FPC * (2.0 * x / 0.002 - (x / 0.002) ** 2)
    if x <= 0.005:
        return -0.2 * FPC
    return 0.0


def tension_acero(epsilon):
    return max(-FY, min(FY, ES * epsilon))


def respuesta_fibras(epsilon_0, phi, fibras):
    """epsilon(y) = epsilon_0 - phi*y; integra P y M de las fibras."""
    P = M = 0.0
    for y, area, material in fibras:
        epsilon = epsilon_0 - phi * y
        sigma = (tension_hormigon(epsilon) if material == "hormigon"
                 else tension_acero(epsilon))
        P += sigma * area
        M += sigma * area * y
    return P, M


def crear_fiber_section():
    """Crea en OpenSees la misma seccion que se usa en la demostracion."""
    ops.wipe()
    ops.model("basic", "-ndm", 2, "-ndf", 3)
    ops.uniaxialMaterial("Concrete01", 1, -FPC, -0.002, -0.2 * FPC, -0.005)
    ops.uniaxialMaterial("Concrete01", 2, -0.8 * FPC, -0.002, -0.1 * FPC, -0.0035)
    ops.uniaxialMaterial("Steel01", 3, FY, ES, 0.01)

    sec = 1
    ops.section("Fiber", sec, "-GJ", 1.0e6)
    hc = H / 2 - RECUBRIMIENTO
    bc = B / 2 - RECUBRIMIENTO
    # Hormigon confinado interior y cuatro franjas de recubrimiento.
    ops.patch("rect", 1, 24, 24, -hc, -bc, hc, bc)
    ops.patch("rect", 2, 4, 24, -H / 2, -B / 2, -hc, B / 2)
    ops.patch("rect", 2, 4, 24, hc, -B / 2, H / 2, B / 2)
    ops.patch("rect", 2, 24, 4, -hc, -B / 2, hc, -bc)
    ops.patch("rect", 2, 24, 4, -hc, bc, hc, B / 2)

    yb = H / 2 - RECUBRIMIENTO - DIAMETRO_BARRA / 2
    zb = B / 2 - RECUBRIMIENTO - DIAMETRO_BARRA / 2
    ops.layer("straight", 3, 3, AREA_BARRA, -yb, -zb, -yb, zb)
    ops.layer("straight", 3, 3, AREA_BARRA, yb, -zb, yb, zb)
    ops.layer("straight", 3, 2, AREA_BARRA, 0.0, -zb, 0.0, zb)
    return sec


def momento_curvatura():
    """Analisis M-phi con un elemento zeroLengthSection."""
    sec = crear_fiber_section()
    ops.node(1, 0.0, 0.0)
    ops.node(2, 0.0, 0.0)
    ops.fix(1, 1, 1, 1)
    ops.fix(2, 0, 1, 0)
    ops.element("zeroLengthSection", 1, 1, 2, sec)
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    ops.load(2, 0.0, 0.0, 1.0)
    ops.system("BandGeneral")
    ops.constraints("Plain")
    ops.numberer("Plain")
    ops.algorithm("Newton")
    ops.integrator("DisplacementControl", 2, 3, 0.00005)
    ops.analysis("Static")

    phi, momento = [], []
    for _ in range(160):
        if ops.analyze(1) != 0:
            break
        phi.append(ops.nodeDisp(2, 3))
        momento.append(ops.eleForce(1)[2])
    return phi, momento


def puntos_interaccion(fibras):
    """Genera puntos PM por compatibilidad de deformaciones."""
    puntos = []
    # Carga axial casi pura: M es cercano a cero.
    for epsilon in [0.0, -0.0005, -0.001, -0.002, -0.003, -0.004, -0.005]:
        P, M = respuesta_fibras(epsilon, 0.0, fibras)
        puntos.append((-P, abs(M)))

    # Flexion con deformacion maxima de compresion de 0.003.
    for c in [0.03, 0.05, 0.08, 0.12, 0.20, 0.35, 0.60, 1.0, 2.0]:
        phi = 0.003 / c
        epsilon_0 = 0.003 - phi * (H / 2)
        P, M = respuesta_fibras(epsilon_0, phi, fibras)
        puntos.append((-P, abs(M)))
    return puntos


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    fibras = fibras_numericas()
    phi, momento = momento_curvatura()
    if not phi:
        raise RuntimeError("OpenSees no pudo completar el analisis M-phi")

    plt.figure(figsize=(7, 4.5))
    plt.plot(phi, momento, color="navy")
    plt.xlabel("Curvatura phi [1/m]")
    plt.ylabel("Momento M [kN m]")
    plt.title("Columna 0.50 x 0.50 m: momento-curvatura")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(SALIDA / "momento_curvatura.png", dpi=160)
    plt.close()

    puntos = puntos_interaccion(fibras)
    axial, momentos = zip(*puntos)
    plt.figure(figsize=(7, 4.5))
    plt.plot(momentos, axial, "o-", color="darkred")
    plt.xlabel("Momento M [kN m]")
    plt.ylabel("Compresion -P [kN]")
    plt.title("Interaccion P-M aproximada")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(SALIDA / "interaccion_PM.png", dpi=160)
    plt.close()

    print("CAPACIDAD HA")
    print("SUPUESTO DE LABORATORIO - armadura no extraida de planos")
    print(f"Seccion: {B:.2f} x {H:.2f} m; recubrimiento: {RECUBRIMIENTO:.2f} m")
    print(f"M-phi: {len(phi)} puntos; |M|max aproximado = {max(map(abs, momento)):.2f} kN m")
    print(f"P-M: {len(puntos)} puntos")
    print(f"Graficos: {SALIDA / 'momento_curvatura.png'}")
    print(f"          {SALIDA / 'interaccion_PM.png'}")


if __name__ == "__main__":
    main()
