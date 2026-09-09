"""Capacidad de una columna de hormigon armado de 0.50 x 0.50 m.

PROCEDENCIA DE LA ARMADURA
--------------------------
Se revisaron las 38 laminas del proyecto 2017_67. El edificio NO tiene
cuadro de pilares: su sistema resistente son muros, y las columnas
aparecen como cabezales de borde detallados en las elevaciones de eje
(laminas -300 a -310), no en una lamina propia.

De la lamina 2017_67-000 "ESQUEMA ESTRIBOS EN VIGAS Y PILARES" se midio
el detalle tipico de pilar: 16 barras en disposicion perimetral de 5 por
cara, con estribo exterior mas un segundo estribo interior en rombo que
traba las barras de media cara (nomenclatura 2E; para pilares el
parametro de la lamina es el NUMERO de estribos).

Trazable a plano : numero de barras, disposicion, topologia de estribos.
Supuesto         : el diametro. Se adopta phi16, que es uno de los
                   diametros que el edificio usa (en las elevaciones
                   aparecen phi16, phi18, phi22, phi25 y phi28).

La seccion de 0.50 x 0.50 m tampoco viene de plano: es la que fija
benchmark_3d.py para las 82 columnas del modelo.
"""

import math
from pathlib import Path

import matplotlib.pyplot as plt
import openseespy.opensees as ops


RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "semana03" / "resultados"

# --------------------------------------------------------------------
# SECCION Y MATERIALES
# --------------------------------------------------------------------
B = H = 0.50                   # m, seccion del modelo global
RECUBRIMIENTO = 0.05           # m, al eje del estribo
FPC = 28_000.0                 # kPa = 28 MPa, igual al modelo global
FY = 420_000.0                 # kPa = 420 MPa
ES = 200_000_000.0             # kPa = 200 GPa
EC = 4700.0 * math.sqrt(28.0) * 1000.0

# Armadura: lamina 2017_67-000, detalle tipico de pilar.
BARRAS_POR_CARA = 5            # -> 16 barras perimetrales
DIAMETRO_BARRA = 0.016         # phi16 (unico dato supuesto)
DIAMETRO_ESTRIBO = 0.010       # phi10, espaciamiento a 10 cm (2E)

AREA_BARRA = math.pi * DIAMETRO_BARRA ** 2 / 4.0

# Leyes constitutivas. Concrete01 de OpenSees: parabola hasta EPS_C0,
# recta descendente hasta (EPS_U, FPCU) y meseta constante despues.
EPS_C0, EPS_U, FPCU = 0.002, 0.005, 0.2 * FPC
EPS_CU = 0.003                 # deformacion ultima util para la P-M

# Demanda axial de las 82 columnas del modelo, caso G (kN, compresion).
P_DEMANDA = {"mediana": 867.0, "maxima": 3386.0}


# --------------------------------------------------------------------
# GEOMETRIA DE LA ARMADURA
# --------------------------------------------------------------------
def posiciones_barras():
    """16 barras perimetrales, 5 por cara, segun la lamina -000.

    Devuelve [(y, z)] en metros, con el origen en el centro de la
    seccion. Las esquinas se comparten entre caras, por eso son
    5 + 5 arriba/abajo mas 3 + 3 en los costados.
    """
    d = RECUBRIMIENTO + DIAMETRO_ESTRIBO + DIAMETRO_BARRA / 2.0
    yb, zb = H / 2 - d, B / 2 - d
    n = BARRAS_POR_CARA
    paso_z = 2 * zb / (n - 1)
    paso_y = 2 * yb / (n - 1)

    barras = []
    for i in range(n):                       # cara superior e inferior
        z = -zb + i * paso_z
        barras.append((yb, z))
        barras.append((-yb, z))
    for i in range(1, n - 1):                # costados, sin esquinas
        y = -yb + i * paso_y
        barras.append((y, -zb))
        barras.append((y, zb))
    return barras


BARRAS = posiciones_barras()
AS_TOTAL = len(BARRAS) * AREA_BARRA
CUANTIA = AS_TOTAL / (B * H)


# --------------------------------------------------------------------
# LEYES CONSTITUTIVAS (las mismas que usa la seccion de OpenSees)
# --------------------------------------------------------------------
def tension_hormigon(epsilon, fc=FPC, eps0=EPS_C0, fcu=FPCU, epsu=EPS_U):
    """Concrete01 reproducido: parabola, recta descendente y meseta.

    El signo es negativo en compresion. Antes esta funcion caia de golpe
    a 0.2*fc pasado eps0, mientras la seccion de OpenSees bajaba en
    recta: eran dos hormigones distintos y por eso la M-phi y la P-M no
    describian la misma seccion.
    """
    if epsilon >= 0.0:
        return 0.0                            # sin traccion
    x = abs(epsilon)
    if x <= eps0:
        return -fc * (2.0 * x / eps0 - (x / eps0) ** 2)
    if x <= epsu:
        return -(fc + (fcu - fc) * (x - eps0) / (epsu - eps0))
    return -fcu


def tension_acero(epsilon):
    """Steel01 elastoplastico, sin endurecimiento para la integracion."""
    return max(-FY, min(FY, ES * epsilon))


def respuesta_fibras(epsilon_0, phi, fibras):
    """epsilon(y) = epsilon_0 - phi*y; integra P y M sobre las fibras."""
    P = M = 0.0
    for y, area, material in fibras:
        epsilon = epsilon_0 - phi * y
        sigma = (tension_hormigon(epsilon) if material == "hormigon"
                 else tension_acero(epsilon))
        P += sigma * area
        M += sigma * area * y
    return P, M


def fibras_numericas(n=40):
    """Malla de hormigon mas las 16 barras, para integrar P y M.

    El area de las barras se descuenta del hormigon que ocupan, si no la
    seccion queda con mas material del que tiene.
    """
    fibras = []
    dy, dz = H / n, B / n
    for iy in range(n):
        y = -H / 2 + (iy + 0.5) * dy
        for iz in range(n):
            fibras.append((y, dy * dz, "hormigon"))
    for y, _z in BARRAS:
        fibras.append((y, AREA_BARRA, "acero"))
        fibras.append((y, -AREA_BARRA, "hormigon"))
    return fibras


# --------------------------------------------------------------------
# SECCION DE FIBRAS EN OPENSEES
# --------------------------------------------------------------------
def crear_fiber_section():
    """Fiber Section con nucleo confinado, recubrimiento y 16 barras."""
    ops.wipe()
    ops.model("basic", "-ndm", 2, "-ndf", 3)
    # 1 nucleo confinado por los estribos 2E; 2 recubrimiento sin confinar.
    ops.uniaxialMaterial("Concrete01", 1, -FPC, -EPS_C0, -FPCU, -EPS_U)
    ops.uniaxialMaterial("Concrete01", 2, -0.8 * FPC, -EPS_C0,
                         -0.1 * FPC, -0.0035)
    ops.uniaxialMaterial("Steel01", 3, FY, ES, 0.01)

    sec = 1
    ops.section("Fiber", sec, "-GJ", 1.0e6)
    hc = H / 2 - RECUBRIMIENTO
    bc = B / 2 - RECUBRIMIENTO
    ops.patch("rect", 1, 24, 24, -hc, -bc, hc, bc)
    ops.patch("rect", 2, 4, 24, -H / 2, -B / 2, -hc, B / 2)
    ops.patch("rect", 2, 4, 24, hc, -B / 2, H / 2, B / 2)
    ops.patch("rect", 2, 24, 4, -hc, -B / 2, hc, -bc)
    ops.patch("rect", 2, 24, 4, -hc, bc, hc, B / 2)
    for y, z in BARRAS:
        ops.fiber(y, z, AREA_BARRA, 3)
    return sec


def momento_curvatura(P=0.0, pasos=260, d_phi=0.0001):
    """M-phi con axial P constante (kN, positivo en compresion).

    El axial se aplica primero y se congela con loadConst; recien
    entonces se impone la curvatura. Con P = 0 la seccion responde como
    viga: es el axial el que cambia la capacidad de momento.
    """
    sec = crear_fiber_section()
    ops.node(1, 0.0, 0.0)
    ops.node(2, 0.0, 0.0)
    ops.fix(1, 1, 1, 1)
    ops.fix(2, 0, 1, 0)
    ops.element("zeroLengthSection", 1, 1, 2, sec)

    ops.system("BandGeneral")
    ops.constraints("Plain")
    ops.numberer("Plain")
    ops.test("NormDispIncr", 1.0e-8, 40)
    ops.algorithm("Newton")

    if P:
        ops.timeSeries("Constant", 1)
        ops.pattern("Plain", 1, 1)
        ops.load(2, -P, 0.0, 0.0)             # compresion = axial negativo
        ops.integrator("LoadControl", 1.0)
        ops.analysis("Static")
        if ops.analyze(1) != 0:
            raise RuntimeError(f"no converge el axial P = {P} kN")
        ops.loadConst("-time", 0.0)

    ops.timeSeries("Linear", 2)
    ops.pattern("Plain", 2, 2)
    ops.load(2, 0.0, 0.0, 1.0)
    ops.integrator("DisplacementControl", 2, 3, d_phi)
    ops.analysis("Static")

    phi, momento = [0.0], [0.0]
    pico = 0.0
    for _ in range(pasos):
        if ops.analyze(1) != 0:
            break
        M = abs(ops.eleForce(1)[2])
        pico = max(pico, M)
        # Pasado el peak la seccion se degrada; cuando cae bajo el 20 %
        # del maximo ya perdio capacidad y el analisis deja de ser util.
        # Sin este corte el momento cruzaba cero y el valor absoluto lo
        # devolvia hacia arriba, dibujando un rebote que no existe.
        if pico > 0.0 and M < 0.2 * pico:
            break
        phi.append(ops.nodeDisp(2, 3))
        momento.append(M)
    return phi, momento


# --------------------------------------------------------------------
# INTERACCION P-M
# --------------------------------------------------------------------
def puntos_interaccion(fibras, n=60):
    """Envolvente P-M barriendo la profundidad del eje neutro.

    El barrido llega hasta 2*H y no hasta 3 m: pasada la compresion
    total los puntos se apilan en el mismo sitio y no aportan nada. Se
    devuelven todos los puntos calculados, sin casco convexo, para que
    la curva muestre su forma real.
    """
    P_traccion, _ = respuesta_fibras(0.01, 0.0, fibras)

    puntos = [(-P_traccion, 0.0)]
    c_min, c_max = 0.05 * H, 2.0 * H
    signo = 0.0
    for i in range(n):
        c = c_min * (c_max / c_min) ** (i / (n - 1))
        phi = EPS_CU / c
        epsilon_0 = -EPS_CU + phi * H / 2
        P, M = respuesta_fibras(epsilon_0, phi, fibras)
        # Pasada cierta profundidad del eje neutro el momento CAMBIA DE
        # SIGNO: la fibra mas comprimida ya esta en la rama descendente
        # del hormigon y aporta menos que la menos comprimida. Ahi
        # termina la envolvente; tomar el valor absoluto la doblaba hacia
        # arriba y cerraba un lazo que no existe.
        if signo == 0.0 and M != 0.0:
            signo = math.copysign(1.0, M)
        if signo and M * signo < 0.0:
            break
        puntos.append((-P, abs(M)))

    # El barrido impone eps_cu en la fibra extrema, asi que no alcanza la
    # compresion pura: esa exige deformacion uniforme eps_c0, con el
    # hormigon en su peak. Po se calcula aparte, como cota superior.
    return puntos


def compresion_pura(fibras):
    """Po con deformacion uniforme eps_c0 (peak del hormigon)."""
    P, _ = respuesta_fibras(-EPS_C0, 0.0, fibras)
    return -P


def punto_balanceado(puntos):
    return max(puntos, key=lambda p: p[1])


def momento_para(puntos, P):
    """Interpola el momento de la envolvente para un axial dado."""
    for (p1, m1), (p2, m2) in zip(puntos, puntos[1:]):
        if p1 <= P <= p2:
            if abs(p2 - p1) < 1e-9:
                return max(m1, m2)
            return m1 + (m2 - m1) * (P - p1) / (p2 - p1)
    return 0.0


# --------------------------------------------------------------------
# GRAFICOS
# --------------------------------------------------------------------
def grafico_discretizacion(ruta, n=24):
    """Dibuja la discretizacion en fibras, el confinamiento y las barras."""
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    hc, bc = H / 2 - RECUBRIMIENTO, B / 2 - RECUBRIMIENTO

    ax.add_patch(plt.Rectangle((-B / 2, -H / 2), B, H,
                               facecolor="#d9d9d9", edgecolor="black",
                               lw=1.6, label="recubrimiento (sin confinar)"))
    ax.add_patch(plt.Rectangle((-bc, -hc), 2 * bc, 2 * hc,
                               facecolor="#a8c4e0", edgecolor="navy",
                               lw=1.4, label="nucleo confinado"))
    for i in range(1, n):                     # malla de fibras del nucleo
        ax.plot([-bc, bc], [-hc + 2 * hc * i / n] * 2,
                color="navy", lw=0.3, alpha=0.5)
        ax.plot([-bc + 2 * bc * i / n] * 2, [-hc, hc],
                color="navy", lw=0.3, alpha=0.5)

    # Estribo 2E: cuadrado exterior mas rombo interior (lamina -000).
    ax.add_patch(plt.Rectangle((-bc, -hc), 2 * bc, 2 * hc, fill=False,
                               edgecolor="darkred", lw=2.0))
    ax.plot([-bc, 0, bc, 0, -bc], [0, hc, 0, -hc, 0],
            color="darkred", lw=1.6, ls="--")

    zs = [z for _y, z in BARRAS]
    ys = [y for y, _z in BARRAS]
    ax.scatter(zs, ys, s=110, color="black", zorder=5,
               label=f"{len(BARRAS)} phi{DIAMETRO_BARRA * 1000:.0f}")

    ax.set_aspect("equal")
    ax.set_xlim(-B / 2 - 0.05, B / 2 + 0.05)
    ax.set_ylim(-H / 2 - 0.05, H / 2 + 0.05)
    ax.set_xlabel("z [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(f"Fiber Section {B:.2f} x {H:.2f} m\n"
                 f"{len(BARRAS)} phi{DIAMETRO_BARRA * 1000:.0f} "
                 f"(5 por cara) + estribo 2E "
                 f"phi{DIAMETRO_ESTRIBO * 1000:.0f}a10  -  "
                 f"cuantia {CUANTIA * 100:.2f} %")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(ruta, dpi=160)
    plt.close(fig)


def grafico_momento_curvatura(ruta, curvas):
    plt.figure(figsize=(7.2, 4.8))
    for etiqueta, (phi, momento) in curvas.items():
        plt.plot(phi, momento, lw=1.8, label=etiqueta)
    plt.xlabel("Curvatura phi [1/m]")
    plt.ylabel("Momento M [kN m]")
    plt.title("Momento-curvatura de la columna, segun el axial")
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=9)
    plt.tight_layout()
    plt.savefig(ruta, dpi=160)
    plt.close()


def grafico_interaccion(ruta, puntos, Po):
    axial = [p for p, _m in puntos]
    momentos = [m for _p, m in puntos]
    # Envolvente cerrada: rama negativa, rama positiva y meseta superior
    # que une los dos extremos del barrido.
    mx = [-m for m in reversed(momentos)] + momentos + [-momentos[-1]]
    px = list(reversed(axial)) + axial + [axial[-1]]

    plt.figure(figsize=(7.6, 5.4))
    plt.plot(mx, px, "-", color="darkred", lw=1.8, label="capacidad P-M")
    plt.plot(momentos, axial, ".", color="darkred", ms=4,
             label=f"{len(puntos)} puntos calculados")

    Pb, Mb = punto_balanceado(puntos)
    plt.plot([Mb], [Pb], "o", color="black", ms=8, zorder=5)
    plt.annotate(f"balanceado\n({Mb:.0f} kN m, {Pb:.0f} kN)",
                 (Mb, Pb), textcoords="offset points", xytext=(-95, -34),
                 fontsize=8)

    plt.axhline(Po, color="gray", ls="--", lw=1.2)
    plt.annotate(f"Po = {Po:.0f} kN (compresion pura)",
                 (0, Po), textcoords="offset points", xytext=(6, 5),
                 fontsize=8, color="gray")

    for nombre, P in P_DEMANDA.items():
        plt.axhline(P, color="tab:blue", ls=":", lw=1.2)
        plt.annotate(f"demanda G, {nombre}: {P:.0f} kN",
                     (0, P), textcoords="offset points", xytext=(6, 4),
                     fontsize=8, color="tab:blue")

    plt.xlabel("Momento M [kN m]")
    plt.ylabel("Compresion P [kN]")
    plt.title("Interaccion P-M de la columna")
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=9, loc="lower right")
    plt.tight_layout()
    plt.savefig(ruta, dpi=160)
    plt.close()


# --------------------------------------------------------------------
def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    fibras = fibras_numericas()

    print("=" * 66)
    print("PARTE D - CAPACIDAD DE SECCION DE HORMIGON ARMADO")
    print("=" * 66)
    print(f"\nSeccion              : {B:.2f} x {H:.2f} m")
    print(f"Hormigon             : f'c = {FPC / 1000:.0f} MPa")
    print(f"Acero                : fy = {FY / 1000:.0f} MPa")
    print(f"Armadura             : {len(BARRAS)} phi"
          f"{DIAMETRO_BARRA * 1000:.0f}, {BARRAS_POR_CARA} por cara")
    print(f"Estribos             : 2E phi{DIAMETRO_ESTRIBO * 1000:.0f} a 10 cm")
    print(f"As total             : {AS_TOTAL * 1e4:.2f} cm2")
    print(f"Cuantia              : {CUANTIA * 100:.2f} %  "
          f"(minimo normativo 1.0 %)")
    print("\nDisposicion y estribos: lamina 2017_67-000.")
    print("Diametro phi16        : supuesto; el edificio usa phi16 a phi28.")

    grafico_discretizacion(SALIDA / "discretizacion_seccion.png")

    print("\n--- MOMENTO-CURVATURA ---")
    curvas = {}
    for etiqueta, P in (("P = 0 (flexion pura)", 0.0),
                        (f"P = {P_DEMANDA['mediana']:.0f} kN (demanda mediana)",
                         P_DEMANDA["mediana"]),
                        (f"P = {P_DEMANDA['maxima']:.0f} kN (demanda maxima)",
                         P_DEMANDA["maxima"])):
        phi, momento = momento_curvatura(P)
        curvas[etiqueta] = (phi, momento)
        print(f"  {etiqueta:44} M_max = {max(momento):8.1f} kN m  "
              f"({len(phi)} puntos)")
    grafico_momento_curvatura(SALIDA / "momento_curvatura.png", curvas)

    print("\n--- INTERACCION P-M ---")
    puntos = puntos_interaccion(fibras)
    Pb, Mb = punto_balanceado(puntos)
    P_traccion = puntos[0][0]
    P_compresion = compresion_pura(fibras)
    print(f"  Traccion pura        P = {P_traccion:9.1f} kN   "
          f"(As*fy = {-AS_TOTAL * FY:.1f} kN)")
    print(f"  Balanceado           P = {Pb:9.1f} kN   M = {Mb:8.1f} kN m")
    print(f"  Compresion pura      P = {P_compresion:9.1f} kN   "
          f"(cota, deformacion uniforme)")
    print(f"  Fin del barrido      P = {puntos[-1][0]:9.1f} kN   "
          f"M = {puntos[-1][1]:8.1f} kN m")
    print(f"  Puntos calculados    {len(puntos)}")
    grafico_interaccion(SALIDA / "interaccion_PM.png", puntos, P_compresion)

    print("\n--- DEMANDA CONTRA CAPACIDAD ---")
    for nombre, P in P_DEMANDA.items():
        M_cap = momento_para(puntos, P)
        print(f"  Axial {nombre:8} P = {P:7.1f} kN  ->  "
              f"M disponible = {M_cap:7.1f} kN m")

    M0 = momento_para(puntos, 0.0)
    print("\n--- INTERPRETACION ---")
    print(f"  La curva sube desde traccion pura ({P_traccion:.0f} kN, M = 0),")
    print(f"  alcanza su maximo momento en el punto balanceado")
    print(f"  ({Mb:.0f} kN m con {Pb:.0f} kN) y vuelve hacia M = 0 al")
    print(f"  acercarse a la compresion pura (cota Po = {P_compresion:.0f} kN).")
    print(f"  Bajo el balanceado la compresion AYUDA: cierra las fisuras y")
    print(f"  el momento sube de {M0:.0f} a {Mb:.0f} kN m. Sobre el")
    print(f"  balanceado la compresion ESTORBA: el hormigon ya trabaja al")
    print(f"  limite y cada kN de axial resta capacidad de flexion.")
    print(f"  Por eso una columna no tiene 'un' momento resistente, sino")
    print(f"  uno distinto para cada nivel de carga axial.")
    print(f"  El M-phi lo confirma: con P = 0 la seccion da {M0:.0f} kN m y es")
    print(f"  ductil; con P = {P_DEMANDA['maxima']:.0f} kN da mas momento pero")
    print(f"  se degrada rapido. Mas axial da mas capacidad y menos ductilidad.")

    print(f"\nGraficos en {SALIDA}:")
    for f in ("discretizacion_seccion.png", "momento_curvatura.png",
              "interaccion_PM.png"):
        print(f"  {f}")


if __name__ == "__main__":
    main()
