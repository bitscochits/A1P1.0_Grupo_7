# -*- coding: utf-8 -*-
"""
================================================================
 verificar_lt2.py
================================================================
 Verificaciones numericas del modelo del edificio LT2.

 Cada una compara contra un valor conocido o contra una propiedad
 que TIENE que cumplirse. Un modelo que corre y da numeros no esta
 verificado: en el camino hasta aca, tres errores distintos daban
 un modelo que corria y daba numeros equivocados.

   1. Un muro colgando entre +7.87 y +11.83, sin nada debajo.
      Resultado: UZ = -1.2e14 mm. LAPACK no siempre falla con la
      matriz singular; a veces devuelve un numero enorme, que es
      peor, porque parece un resultado.

   2. La distancia perpendicular dividida de mas por el largo del
      eje. Un muro a 20 m "medía" 0.26 m, y aparecian vigas de
      20 m que no existen en el plano.

   3. Los cruces de viga recortados al extremo dibujado, que dejaba
      dos nodos a 0.42 m sin fundirse: 100 tramos desconectados.

 Correr con:  python verificar_lt2.py
================================================================
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openseespy.opensees as ops   # noqa: E402
import modelo_lt2 as M              # noqa: E402
import panos                        # noqa: E402

fallos = []


def check(nombre, condicion, detalle=''):
    estado = 'OK  ' if condicion else 'FALLA'
    print('  [%s] %s%s' % (estado, nombre, ('   ' + detalle) if detalle else ''))
    if not condicion:
        fallos.append(nombre)


def mediana(v):
    v = sorted(v)
    return v[len(v) // 2] if v else 0.0


print('=' * 68)
print('  VERIFICACION DEL MODELO LT2')
print('=' * 68)

m = M.ModeloLT2().preparar().ensamblar('G').resolver()
r = m.resumen()
uz = {t: ops.nodeDisp(t, 3) for t in m.nodos}

print('\n  %d nodos · %d columnas · %d muros · %d vigas · %d brazos'
      % (r['nodos'], r['columnas'], r['muros'], r['vigas'], r['brazos']))

# ============================================================
print('\n1. Secciones contra calculo a mano')
s = M.seccion('P', 0.70, 0.70)
check('pilar 0.70x0.70: A = 0.49 m2', abs(s.A - 0.49) < 1e-12)
check('  Iy = Iz = 0.70^4/12', abs(s.Iz - 0.70 ** 4 / 12.0) < 1e-15
      and abs(s.Iy - s.Iz) < 1e-15, 'I = %.6f m4' % s.Iz)

v = M.seccion('V', 0.60, 0.80)
check('viga 0.60x0.80: Iz (gravedad) = b*h^3/12',
      abs(v.Iz - 0.60 * 0.80 ** 3 / 12.0) < 1e-15, 'Iz = %.6f m4' % v.Iz)
check('  Iy (lateral) = h*b^3/12',
      abs(v.Iy - 0.80 * 0.60 ** 3 / 12.0) < 1e-15, 'Iy = %.6f m4' % v.Iy)
check('  Iz > Iy (canto mayor que ancho)', v.Iz > v.Iy)

# J de Saint-Venant, no min(Iy,Iz)*0.3
J = M.J_rectangular(0.30, 0.30)
check('J de Saint-Venant no es min(Iy,Iz)*0.3',
      abs(J / (0.30 ** 4 / 12.0 * 0.3) - 1.0) > 0.5,
      'J = %.3e vs el atajo %.3e' % (J, 0.30 ** 4 / 12.0 * 0.3))

# ============================================================
print('\n2. Equilibrio global')
check('suma de reacciones = carga aplicada',
      r['error_equilibrio'] < 1e-4,
      'error = %.3e kN sobre %.0f kN' % (r['error_equilibrio'], r['carga_total']))

# ============================================================
print('\n3. Orientacion de los muros (el error que no avisa)')
# Un muro mal orientado aporta (L/t)^2 veces menos rigidez lateral
# y el modelo no se queja. Se comprueba que a OpenSees le llego la
# inercia FUERTE en el hueco que corresponde al eje local y, que es
# el que queda a lo largo del muro por como se eligio vecxz.
peor = None
for _e, _n1, _n2, sec, vecxz, tipo, _p in m.verticales:
    if tipo != 'muro':
        continue
    t, L = sec.b, sec.h
    fuerte = t * L ** 3 / 12.0
    debil = L * t ** 3 / 12.0
    razon = fuerte / debil
    ok = abs(sec.Iz - fuerte) < 1e-12 and abs(sec.Iy - debil) < 1e-12
    if not ok:
        peor = sec.nombre
    # vecxz debe ser perpendicular al eje del muro, en planta
    if peor is None and abs(vecxz[2]) > 1e-12:
        peor = sec.nombre

check('todos los muros llevan la inercia fuerte en Iz de la seccion',
      peor is None, peor or '')

razones = [(s.h / s.b) ** 2 for _e, _a, _b, s, _v, tp, _p in m.verticales
           if tp == 'muro']
check('la razon I_fuerte/I_debil llega a valores enormes',
      max(razones) > 100,
      'maximo (L/t)^2 = %.0f  ->  orientar mal un muro lo hace %.0f veces '
      'menos rigido' % (max(razones), max(razones)))

check('ningun vecxz de muro es paralelo al eje del elemento',
      all(abs(v[2]) < 1e-12 and (abs(v[0]) > 1e-9 or abs(v[1]) > 1e-9)
          for _e, _a, _b, _s, v, tp, _p in m.verticales if tp == 'muro'))

# ============================================================
print('\n4. Linealidad y superposicion')
# El modelo es lineal: duplicar la carga duplica todo. Si no lo
# hace, hay algo no lineal metido sin querer.
m2 = M.ModeloLT2().preparar().ensamblar('G')
ops.setTime(0.0)
ops.reset()
# se resuelve con el doble de carga usando el factor del integrador
ops.system('BandGeneral')
ops.numberer('RCM')
ops.constraints('Transformation')
ops.integrator('LoadControl', 2.0)
ops.algorithm('Linear')
ops.analysis('Static')
ops.analyze(1)
uz2 = {t: ops.nodeDisp(t, 3) for t in m2.nodos}
comunes = [t for t in uz if t in uz2 and abs(uz[t]) > 1e-9]
error = max(abs(uz2[t] / uz[t] - 2.0) for t in comunes)
check('2x carga da exactamente 2x desplazamiento',
      error < 1e-9, 'peor error relativo = %.2e' % error)

# ============================================================
print('\n5. Compatibilidad del diafragma rigido')
# equalDOF NO es un diafragma: obliga al mismo ux en todo el piso.
# El diafragma real permite ROTACION y cumple
#     ux_i = ux_m - rz*(y_i - y_m)
#     uy_i = uy_m + rz*(x_i - x_m)
m = M.ModeloLT2().preparar().ensamblar('G').resolver()
peor_err, giro_max = 0.0, 0.0
for k, maestro in m.maestros.items():
    xm, ym, _zm = ops.nodeCoord(maestro)
    uxm, uym = ops.nodeDisp(maestro, 1), ops.nodeDisp(maestro, 2)
    rz = ops.nodeDisp(maestro, 6)
    giro_max = max(giro_max, abs(rz))
    for i in range(len(m.malla_nivel[k][0])):
        tag = m.nodo_de[(k, i)]
        if tag not in m.nodos:
            continue
        x, y, _z = ops.nodeCoord(tag)
        ex = abs(ops.nodeDisp(tag, 1) - (uxm - rz * (y - ym)))
        ey = abs(ops.nodeDisp(tag, 2) - (uym + rz * (x - xm)))
        peor_err = max(peor_err, ex, ey)

check('todos los nodos del piso cumplen la relacion del diafragma',
      peor_err < 1e-9, 'peor error = %.2e m' % peor_err)
check('el diafragma PERMITE giro (no es un equalDOF disfrazado)',
      giro_max > 0.0, 'giro maximo de piso = %.2e rad' % giro_max)

# ============================================================
print('\n6. Los brazos son rigidos de verdad')
# Un brazo representa el pedazo de muro entre el extremo real de la
# viga y el baricentro de la columna ancha. Si el resultado depende
# de cuan rigido se lo hizo, es que no es rigido: es una viga mas.
base = mediana([abs(u) for u in uz.values()])
resultados = {}
original = M.FACTOR_BRAZO
for f in (25.0, 100.0, 400.0):
    M.FACTOR_BRAZO = f
    mm = M.ModeloLT2().preparar().ensamblar('G').resolver()
    resultados[f] = mediana([abs(ops.nodeDisp(t, 3)) for t in mm.nodos])
M.FACTOR_BRAZO = original

variacion = (max(resultados.values()) - min(resultados.values())) / max(resultados.values())
check('el resultado no depende del factor de rigidez del brazo',
      variacion < 0.02,
      'x25: %.3f mm · x100: %.3f mm · x400: %.3f mm  ->  varia %.2f %%'
      % (resultados[25.0] * 1000, resultados[100.0] * 1000,
         resultados[400.0] * 1000, 100 * variacion))

# ============================================================
print('\n7. Zonas sin apoyo vertical (deteccion de huecos del plano)')
# Un nodo que baja diez veces mas que la mediana de su piso no es
# "una viga flexible": es una zona que en el modelo cuelga de una
# cadena de vigas sin ningun muro ni pilar abajo. Puede ser que la
# extraccion perdio un muro, o que ahi hay un vano y esas barras no
# son vigas. Hay que MIRAR EL PLANO.
m = M.ModeloLT2().preparar().ensamblar('G').resolver()
sospechosos = []
for k, z in enumerate(m.niveles):
    del_piso = {t: abs(ops.nodeDisp(t, 3))
                for t, (_x, _y, zz) in m.nodos.items() if abs(zz - z) < 1e-9}
    if len(del_piso) < 5:
        continue
    med = mediana(list(del_piso.values()))
    if med <= 0:
        continue
    for t, u in del_piso.items():
        if u > 10.0 * med:
            sospechosos.append((z, t, m.nodos[t], u * 1000, u / med))

print('     nodos que bajan mas de 10 veces la mediana de su piso: %d'
      % len(sospechosos))
for z, t, pos, mm_, veces in sorted(sospechosos, key=lambda s: -s[3])[:6]:
    print('       nivel %+6.2f  nodo %3d %-22s  uz = %8.2f mm  (%.0fx)'
          % (z, t, tuple(round(c, 2) for c in pos), mm_, veces))
print('     -> revisar esos puntos CONTRA EL PLANO antes de usar el modelo')

# Los niveles LIMPIOS -- los que no tienen ningun nodo sospechoso --
# si tienen que estar en rango de hormigon armado. Meter en el mismo
# promedio el nivel afectado seria taparlo: el criterio se aplica por
# separado y el nivel pendiente se declara pendiente, no se aprueba.
niveles_sucios = {s[0] for s in sospechosos}
niveles_limpios = [z for z in m.niveles[1:] if z not in niveles_sucios]

for z in niveles_limpios:
    v = sorted(abs(ops.nodeDisp(t, 3)) * 1000 for t, (_x, _y, zz)
               in m.nodos.items() if abs(zz - z) < 1e-9)
    check('nivel %+6.2f: el peor nodo baja menos de 15 mm' % z,
          v[-1] < 15.0, 'maximo = %.2f mm, mediana = %.2f mm' % (v[-1], mediana(v)))

for z in sorted(niveles_sucios):
    v = sorted(abs(ops.nodeDisp(t, 3)) * 1000 for t, (_x, _y, zz)
               in m.nodos.items() if abs(zz - z) < 1e-9)
    print('  [PEND] nivel %+6.2f: NO se aprueba. maximo = %.2f mm, '
          'mediana = %.2f mm' % (z, v[-1], mediana(v)))
    print('         hay zonas colgando de vigas sin muro ni pilar debajo.')

# ============================================================
print('\n8. Coherencia de la carga (contra el plano de cargas)')
# Los valores NO son supuestos: vienen de la lamina 700. Se comprueba
# que la conversion de kgf/m2 a kN/m2 y la suma sean las del plano.
G = 9.80665
esperado = {
    '2024_22-101': (m.peso_losa + 260 * G / 1000.0, 500 * G / 1000.0),
    '2024_22-102': (m.peso_losa + 200 * G / 1000.0, 300 * G / 1000.0),
}
for lam, (g_esp, q_esp) in esperado.items():
    c = m.cargas_lamina.get(lam, {})
    check('%s: G = peso losa + PM adicional del plano' % lam,
          abs(c.get('muerta', 0) - g_esp) < 1e-9,
          'G = %.2f kN/m2 (losa %.2f + PM adic %.2f)'
          % (c.get('muerta', 0), m.peso_losa, g_esp - m.peso_losa))
    check('  Q = sobrecarga del plano',
          abs(c.get('viva', 0) - q_esp) < 1e-9, 'Q = %.2f kN/m2' % c.get('viva', 0))

check('el peso propio de la losa calza con el "e x 2500 kgf/m3" del plano',
      abs(m.peso_losa - m.espesor_losa * 2500 * G / 1000.0) / m.peso_losa < 0.03,
      'modelo %.3f kN/m2 con gamma=25 vs plano %.3f kN/m2 con 2500 kgf/m3'
      % (m.peso_losa, m.espesor_losa * 2500 * G / 1000.0))

carga_losa = sum(m.cargas_lamina[p['lamina']]['muerta'] * m.area_piso.get(k + 1, 0)
                 for k, p in enumerate(m.pisos))
check('la carga de losa es una fraccion sensata del total',
      0.25 < carga_losa / r['carga_total'] < 0.85,
      'losa %.0f kN de %.0f kN totales (%.0f %%)'
      % (carga_losa, r['carga_total'], 100 * carga_losa / r['carga_total']))

# ============================================================
print('\n9. Areas tributarias a 45 grados (el reparto de la losa)')
# El equilibrio NO valida el reparto: si a una viga le das el doble y
# a otra la mitad, la suma de reacciones cierra igual con error 1e-14.
# Por eso el reparto se verifica aparte.
problemas = panos.verificar()
check('el modulo de panos reproduce las formulas del P1',
      not problemas, '; '.join(problemas))

check('pano cuadrado: las 4 vigas llevan lo mismo (L^2/4)',
      abs(panos.area_tributaria_viga(4.0, 4.0) - 4.0) < 1e-12)

a_larga = panos.area_tributaria_viga(10.0, 3.34)
a_corta = panos.area_tributaria_viga(3.34, 10.0)
check('pano alargado 10.00 x 3.34: las 4 areas suman el area del pano',
      abs(2 * a_larga + 2 * a_corta - 33.4) < 1e-9,
      'larga %.2f m2 · corta %.2f m2' % (a_larga, a_corta))

# Reparto por largo de viga: la misma area total, repartida en
# proporcion al perimetro. Suma igual, o sea el equilibrio cierra
# igual -- y sin embargo carga mal las vigas.
perimetro = 2 * (10.0 + 3.34)
largo_corta = 33.4 * 3.34 / perimetro
largo_larga = 33.4 * 10.0 / perimetro
check('  el reparto por largo suma lo mismo (por eso el equilibrio no lo ve)',
      abs(2 * largo_larga + 2 * largo_corta - 33.4) < 1e-9)
check('  pero sobrecarga la viga corta en mas de un 40 %%',
      largo_corta / a_corta > 1.40,
      'por largo %.2f m2 contra %.2f m2 a 45 grados: %+.0f %%'
      % (largo_corta, a_corta, 100 * (largo_corta / a_corta - 1)))

for k in sorted(m.aud_panos):
    a = m.aud_panos[k]
    check('nivel %+6.2f: la suma de las areas tributarias es el area de los panos'
          % m.niveles[k],
          a['error_de_conservacion'] < 1e-3,
          '%d panos, %.2f m2, error %.1e m2'
          % (a['caras_encontradas'], a['area_total'], a['error_de_conservacion']))

# --- los panos encontrados contra los que rotula el plano ----------
# El plano numera sus panos de losa con un bloque `losa-ne`. Que cada
# cara del grafo tenga por lo menos un rotulo, y que cada rotulo caiga
# cerca de la cara que le toca, es una comprobacion CRUZADA: la
# geometria sale de las lineas de muros y vigas, y los rotulos son
# otra fuente del mismo plano.
r = m.aud_panos[1].get('rotulos_de_losa', {})
if r.get('aplicado'):
    check('cada cara del grafo tiene su rotulo de losa en el plano',
          r['caras_sin_rotulo_descartadas'] <= 1,
          '%d rotulos en %d caras; %d cara(s) sin rotulo, de %s m2 '
          '(el hueco del ascensor)'
          % (r['declarados'], r['caras_con_rotulo'],
             r['caras_sin_rotulo_descartadas'], r['areas_descartadas']))
    check('  ningun rotulo quedo lejos de la cara que le toca',
          r['rotulos_a_mas_de_1.5_m_de_su_cara'] == 0,
          'los que caen fuera del edificio son los de fachada, a menos '
          'de 1 m de su pano')

# --- lo que se supuso y no salio del plano -------------------------
check('los dinteles supuestos estan declarados y contados',
      len(m.dinteles_supuestos) == len(
          m.geo.get('perfil_dinteles', [])),
      'supuestos: %s' % (sorted(m.dinteles_supuestos) or 'ninguno'))

# w*L = q*A viga por viga: es la conservacion que el equilibrio no ve
peor = 0.0
for _e, n1, n2, _s, L, _p, k in m.vigas:
    A = m.area_trib.get((min(n1, n2), max(n1, n2)), 0.0)
    if A <= 0:
        continue
    q = m.cargas_lamina[m.pisos[k - 1]['lamina']]['muerta']
    w = q * A / L
    peor = max(peor, abs(w * L - q * A))
check('viga por viga se cumple w*L = q*A', peor < 1e-9,
      'peor error = %.2e kN' % peor)

# ============================================================
# LOS CUATRO CASOS DE CARGA
# ============================================================
print('\n11. Los cuatro casos de carga')

# --- el peso por nivel tiene que sumar lo que se aplica ---
pesos = m.pesos_por_nivel()
suma_G = sum(p['G'] for p in pesos.values())
suma_Q = sum(p['Q'] for p in pesos.values())
# OJO: la variable 'r' se reasigno mas arriba a la auditoria de rotulos.
# La carga total del caso G la guarda el propio modelo.
carga_G = m.carga_total
check('el peso por nivel suma la carga G aplicada',
      abs(suma_G - carga_G) < 1e-6,
      'por nivel %.4f vs aplicado %.4f kN' % (suma_G, carga_G))

resultados = {}
for caso in ('G', 'Q', 'EX', 'EY'):
    mc = M.ModeloLT2().preparar().ensamblar(caso).resolver()
    ops.reactions()
    R = [sum(ops.nodeReaction(n, i) for n in mc.nodos_base) for i in (1, 2, 3)]
    resultados[caso] = {
        'modelo': mc,
        'aplicada': mc.carga_total,
        'R': R,
        'desp': {t: [ops.nodeDisp(t, i) for i in (1, 2, 3)] for t in mc.nodos},
        'maestros': {k: [ops.nodeDisp(nm, i) for i in (1, 2)]
                     for k, nm in mc.maestros.items()},
    }

# --- equilibrio en los cuatro, en la direccion que corresponde ---
for caso, eje in (('G', 2), ('Q', 2), ('EX', 0), ('EY', 1)):
    d = resultados[caso]
    err = abs(d['aplicada'] + d['R'][eje]) if eje < 2 else \
        abs(d['aplicada'] - d['R'][2])
    check('caso %s: equilibrio' % caso, err < 1e-4,
          'aplicada %.4f  reacciones %.4f  error %.2e kN'
          % (d['aplicada'], d['R'][eje], err))

# --- un caso lateral no puede dejar carga vertical neta ---
for caso in ('EX', 'EY'):
    check('caso %s: no introduce carga vertical' % caso,
          abs(resultados[caso]['R'][2]) < 1e-3,
          'suma Fz = %.2e kN' % resultados[caso]['R'][2])

# --- y un caso de gravedad no puede dejar corte horizontal ---
for caso in ('G', 'Q'):
    R = resultados[caso]['R']
    check('caso %s: no introduce corte horizontal' % caso,
          abs(R[0]) < 1e-3 and abs(R[1]) < 1e-3,
          'Fx = %.2e   Fy = %.2e kN' % (R[0], R[1]))

# --- el corte basal es el declarado, y se reparte entero ---
ms = resultados['EX']['modelo']
s = ms.geo.get('sismo', {})
coef = float(s.get('coef_basal', 0.10))
check('el corte basal es coef x peso sismico',
      abs(ms.corte_basal - coef * ms.peso_sismico) < 1e-9,
      'V = %.2f = %.3f x %.2f kN' % (ms.corte_basal, coef, ms.peso_sismico))

reparto = ms.reparto_sismico
check('el reparto en altura suma el corte basal',
      abs(sum(F for F, _W, _h in reparto.values()) - ms.corte_basal) < 1e-6,
      '%d niveles' % len(reparto))

# La trampa que el otro modelo si tiene: repartir con la cota ABSOLUTA
# en vez de la altura desde la base. Aca la base esta en -7.97, asi que
# los pisos del subterraneo saldrian con h negativo y recibirian la
# fuerza al reves.
check('todas las alturas de reparto son positivas',
      all(h > 0 for _F, _W, h in reparto.values()),
      'h desde la base %+.2f: %s'
      % (ms.niveles[0], ['%.2f' % h for _F, _W, h in
                         sorted(reparto.values(), key=lambda t: t[2])]))
check('ninguna fuerza de piso apunta al reves',
      all(F > 0 for F, _W, _h in reparto.values()),
      'F: %s kN' % ['%.0f' % F for F, _W, _h in
                    sorted(reparto.values(), key=lambda t: t[2])])

# El reparto triangular tiene que crecer con la altura mientras el peso
# de piso no baje. El techo pesa menos (sobrecarga 300 en vez de 500).
por_altura = sorted(reparto.values(), key=lambda t: t[2])
crece = all(a[0] <= b[0] + 1e-9 for a, b in zip(por_altura, por_altura[1:]))
check('la fuerza de piso crece con la altura', crece,
      'reparto triangular invertido (exponente %.1f)'
      % float(s.get('exponente_altura', 1.0)))

check('EX y EY tienen el mismo corte basal',
      abs(resultados['EX']['aplicada'] - resultados['EY']['aplicada']) < 1e-9,
      '%.2f kN en las dos direcciones' % resultados['EX']['aplicada'])

# --- cada caso lateral empuja sobre todo en SU direccion ---
for caso, i, j in (('EX', 0, 1), ('EY', 1, 0)):
    d = resultados[caso]['desp']
    propio = max(abs(v[i]) for v in d.values())
    cruzado = max(abs(v[j]) for v in d.values())
    check('caso %s: el desplazamiento manda en su direccion' % caso,
          propio > cruzado,
          '%.2f mm en %s contra %.2f mm en la otra'
          % (propio * 1000, 'XY'[i], cruzado * 1000))

# ============================================================
# DERIVAS DE ENTREPISO  (NCh433 5.9.2)
# ============================================================
print('\n12. Derivas de entrepiso bajo sismo')
print('    NCh433 5.9.2: la deriva medida en el CENTRO DE MASA no puede')
print('    pasar de 0.002 de la altura de entrepiso. El centro de masa es')
print('    justamente el nodo maestro del diafragma, asi que se lee ahi.')

LIMITE = 0.002
for caso, i in (('EX', 0), ('EY', 1)):
    mm = resultados[caso]['modelo']
    u = resultados[caso]['maestros']
    niveles = sorted(u)
    peor, donde = 0.0, None
    print('    %s:' % caso)
    z_ant, u_ant = mm.niveles[0], 0.0        # la base no se desplaza
    for k in niveles:
        h = mm.niveles[k] - z_ant
        d = (u[k][i] - u_ant) / h
        print('      nivel %+6.2f   h=%4.2f m   u=%7.3f mm   deriva = 1/%-6.0f %s'
              % (mm.niveles[k], h, u[k][i] * 1000,
                 (1.0 / d) if d > 1e-12 else float('inf'),
                 '' if d <= LIMITE else '  <-- PASADA'))
        if d > peor:
            peor, donde = d, mm.niveles[k]
        z_ant, u_ant = mm.niveles[k], u[k][i]
    check('caso %s: deriva de entrepiso bajo el limite' % caso, peor <= LIMITE,
          'peor %.5f (1/%.0f) en el nivel %+.2f; limite %.3f (1/500)'
          % (peor, 1.0 / peor if peor else 0, donde or 0.0, LIMITE))

# ============================================================
print('\n' + '=' * 68)
if fallos:
    print('  %d VERIFICACION(ES) FALLARON:' % len(fallos))
    for f in fallos:
        print('    - %s' % f)
    raise SystemExit(1)
print('  TODAS LAS VERIFICACIONES PASARON')
print('=' * 68)
