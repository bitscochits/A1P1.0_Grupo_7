"""
================================================================
 test_areas_tributarias.py
================================================================
 Verifica el reparto de la losa a las vigas por areas tributarias.

 POR QUE ESTE TEST EXISTE
 ------------------------
 El chequeo de equilibrio (suma de reacciones = carga aplicada) NO
 sirve para validar el reparto: si le das a una viga el doble y a la
 otra la mitad, el total sigue cerrando perfecto y el error sigue
 siendo 1e-14. Un reparto mal hecho es INVISIBLE al equilibrio.

 Lo que si se puede verificar:
   1. Conservacion  : las 4 areas suman exactamente el area del pano.
   2. Geometria     : trapecio para la viga larga, triangulo para la corta.
   3. Caso cuadrado : las 4 areas iguales a A/4 (regresion del benchmark).
   4. Simetria      : intercambiar Lx<->Ly intercambia los resultados.

 Correr con:  python test_areas_tributarias.py
================================================================
"""

import modelo_benchmark as mb

TOL = 1e-12
fallos = []


def check(nombre, condicion, detalle=""):
    estado = "OK  " if condicion else "FALLA"
    print(f"  [{estado}] {nombre}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(nombre)


print("=" * 64)
print("  TEST: AREAS TRIBUTARIAS (reparto a 45 grados)")
print("=" * 64)

# Relaciones de aspecto a probar: cuadrada, poco alargada, muy alargada,
# y las mismas invertidas.
PANOS = [
    (4.0, 4.0),
    (6.0, 4.0),
    (4.0, 6.0),
    (8.0, 3.0),
    (3.0, 8.0),
    (10.0, 2.5),
    (5.5, 5.5),
    (7.3, 4.1),
]

# ------------------------------------------------------------
# 1. CONSERVACION DEL AREA
# ------------------------------------------------------------
print("\n1. Conservacion: 2*A_vigaX + 2*A_vigaY == Lx*Ly")
print(f"   {'Lx':>6}{'Ly':>6}{'A_vigaX':>12}{'A_vigaY':>12}"
      f"{'suma':>10}{'Lx*Ly':>10}{'error':>12}")

for Lx, Ly in PANOS:
    Ax = mb.area_tributaria_viga(Lx, Ly)   # viga que corre en X, luz Lx
    Ay = mb.area_tributaria_viga(Ly, Lx)   # viga que corre en Y, luz Ly
    suma = 2 * Ax + 2 * Ay
    area = Lx * Ly
    err = abs(suma - area)
    print(f"   {Lx:>6.2f}{Ly:>6.2f}{Ax:>12.5f}{Ay:>12.5f}"
          f"{suma:>10.4f}{area:>10.4f}{err:>12.2e}")
    check(f"conservacion {Lx}x{Ly}", err < TOL)

# ------------------------------------------------------------
# 2. GEOMETRIA CORRECTA (trapecio vs triangulo)
# ------------------------------------------------------------
print("\n2. La viga LARGA recibe trapecio, la CORTA recibe triangulo")

# Pano 6 x 4 -> vigas de 6 m son las largas
Lx, Ly = 6.0, 4.0
A_larga = mb.area_tributaria_viga(Lx, Ly)     # luz 6
A_corta = mb.area_tributaria_viga(Ly, Lx)     # luz 4

trapecio_esperado = Ly * (2 * Lx - Ly) / 4.0  # 4*(12-4)/4 = 8.0
triangulo_esperado = Ly * Ly / 4.0            # 16/4 = 4.0

check("trapecio viga larga (6m)", abs(A_larga - trapecio_esperado) < TOL,
      f"{A_larga:.5f} == {trapecio_esperado:.5f} m2")
check("triangulo viga corta (4m)", abs(A_corta - triangulo_esperado) < TOL,
      f"{A_corta:.5f} == {triangulo_esperado:.5f} m2")
check("la larga recibe MAS que la corta", A_larga > A_corta,
      f"{A_larga:.3f} > {A_corta:.3f}")

# El bug viejo repartia Lx*Ly/4 = 6 m2 a TODAS las vigas por igual.
reparto_viejo = Lx * Ly / 4.0
check("el reparto viejo era distinto (bug confirmado)",
      abs(A_larga - reparto_viejo) > 1.0,
      f"correcto={A_larga:.3f} vs viejo={reparto_viejo:.3f} m2 "
      f"-> {100*(A_larga-reparto_viejo)/reparto_viejo:+.1f}%")

# ------------------------------------------------------------
# 3. CASO CUADRADO = REGRESION DEL BENCHMARK
# ------------------------------------------------------------
print("\n3. Pano cuadrado: las 4 vigas reciben A/4 (benchmark intacto)")

L = 4.0
A_sq = mb.area_tributaria_viga(L, L)
check("cuadrado da A/4", abs(A_sq - L * L / 4.0) < TOL,
      f"{A_sq:.5f} == {L*L/4.0:.5f} m2")

w = mb.w_viga(mb.q_losa, mb.Lx, mb.Ly, incluir_peso_vigas=True)
check("w del benchmark sigue siendo 11.1875 kN/m", abs(w - 11.1875) < 1e-9,
      f"{w:.6f} kN/m")

# ------------------------------------------------------------
# 4. SIMETRIA
# ------------------------------------------------------------
print("\n4. Simetria: intercambiar Lx<->Ly intercambia las areas")

for Lx, Ly in [(6.0, 4.0), (8.0, 3.0), (7.3, 4.1)]:
    a1 = mb.area_tributaria_viga(Lx, Ly)
    a2 = mb.area_tributaria_viga(Ly, Lx)
    b1 = mb.area_tributaria_viga(Ly, Lx)
    b2 = mb.area_tributaria_viga(Lx, Ly)
    check(f"simetria {Lx}x{Ly}", abs(a1 - b2) < TOL and abs(a2 - b1) < TOL)

# ------------------------------------------------------------
# 5. ENTRADAS INVALIDAS
# ------------------------------------------------------------
print("\n5. Luces invalidas se rechazan")

for mala in [(0.0, 4.0), (4.0, 0.0), (-2.0, 4.0)]:
    try:
        mb.area_tributaria_viga(*mala)
        check(f"rechaza {mala}", False, "no lanzo excepcion")
    except ValueError:
        check(f"rechaza {mala}", True)

# ------------------------------------------------------------
# RESUMEN
# ------------------------------------------------------------
print("\n" + "=" * 64)
if fallos:
    print(f"  {len(fallos)} TEST(S) FALLARON:")
    for f in fallos:
        print(f"    - {f}")
    raise SystemExit(1)
print("  TODOS LOS TESTS PASARON")
print("=" * 64)
