# -*- coding: utf-8 -*-
r"""
================================================================
 exportar_unity.py  -  CONTRATO JSON  OpenSees -> Unity  (LT2)
================================================================
 Corre el modelo del edificio LT2, resuelve el caso G y escribe
 data/modelo_unity.json con el MISMO contrato del laboratorio
 P1L2, para que el visor de Unity lo abra sin tocar una linea
 de C#.

 REGLA DE ORO: OpenSees calcula, el JSON es la fuente de verdad,
 Unity solo MUESTRA. Por eso aca se exporta ya calculado todo lo
 que Unity necesita dibujar:

   - nodos con sus restricciones por GDL (no un booleano);
   - elementos con su tipo, su seccion y su tamano real;
   - EJES LOCALES calculados en Python. Unity NO debe deducirlos:
     dependen de vecxz y de la convencion de OpenSees, y adivinarlos
     en C# es la duplicacion que despues diverge del modelo;
   - diafragmas (maestro + esclavos);
   - el caso de carga G COMPLETO.

 ----------------------------------------------------------------
 EL JSON TIENE QUE DESCRIBIR EL MISMO PROBLEMA QUE RESOLVIO PYTHON
 ----------------------------------------------------------------
 Si se reanaliza desde Unity y el JSON no calza, el servidor
 devuelve otros numeros y NO hay ningun error. En el P1L2 paso dos
 veces: una porque el caso G exportado no traia el peso propio
 (10.04 mm en vez de 11.78) y otra porque las inercias iban ya
 cruzadas y el servidor las cruzaba de nuevo (12.17 mm).

 Por eso al final esta funcion COMPARA la carga exportada contra la
 que se aplico de verdad y falla si no coinciden.

 ----------------------------------------------------------------
 CONVENCION DE Iy / Iz EN EL CONTRATO
 ----------------------------------------------------------------
 Van en EJES DE LA SECCION, no en los huecos de ops.element().
 Quien construya el modelo aplica el cruce segun la geometria:

   horizontal (vecxz = 0,0,1) -> Iy_slot = sec.Iz   (gravedad)
   vertical   (vecxz = 1,0,0) -> Iy_slot = sec.Iy

 Correr:  python src/exportar_unity.py
================================================================
"""
import json
import math
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(_AQUI)), 'comun'))

import rutas                             # noqa: E402
import openseespy.opensees as ops        # noqa: E402

import modelo_lt2 as M                   # noqa: E402

_RAIZ = rutas.RAIZ
SALIDA = rutas.unity('lt2')


# ============================================================
def ejes_locales(pi, pj, vecxz):
    r"""
    Los tres versores locales de una barra, con la MISMA convencion
    que usa OpenSees en geomTransf:

        local_x = (j - i) normalizado
        local_z = componente de vecxz perpendicular a local_x
        local_y = local_z x local_x
    """
    dx = [pj[k] - pi[k] for k in range(3)]
    L = math.sqrt(sum(c * c for c in dx))
    if L < 1e-12:
        raise ValueError('barra de largo cero')
    ex = [c / L for c in dx]

    v = list(vecxz)
    proy = sum(v[k] * ex[k] for k in range(3))
    ez = [v[k] - proy * ex[k] for k in range(3)]
    n = math.sqrt(sum(c * c for c in ez))
    if n < 1e-9:
        raise ValueError('vecxz paralelo al eje del elemento')
    ez = [c / n for c in ez]

    ey = [ez[1] * ex[2] - ez[2] * ex[1],
          ez[2] * ex[0] - ez[0] * ex[2],
          ez[0] * ex[1] - ez[1] * ex[0]]
    return ex, ey, ez


def r6(v):
    return [round(float(c), 6) for c in v]


def tipo_de_viga(pi, pj):
    """'viga_x' o 'viga_y' segun hacia donde corre en planta.

    El visor del P1L2 colorea y filtra por estos dos tipos; una barra
    horizontal con cualquier otro nombre no aparece en ningun toggle.
    """
    return 'viga_x' if abs(pj[0] - pi[0]) >= abs(pj[1] - pi[1]) else 'viga_y'


# ============================================================
def construir_casos(m, r):
    r"""
    Los cuatro casos de carga, escritos en el contrato JSON.

        G   peso propio + losa + peso muerto adicional
        Q   sobrecarga de uso
        EX  sismo pseudoestatico en X
        EY  sismo pseudoestatico en Y

    ----------------------------------------------------------------
    POR QUE SE REARMAN ACA EN VEZ DE LEERLOS DE OPENSEES
    ----------------------------------------------------------------
    OpenSees no devuelve las cargas que se le metieron: hay que
    escribirlas de nuevo. Y ahi esta el riesgo -- que lo que viaja en
    el JSON no sea lo mismo que se resolvio en Python. Quien reanalice
    desde Unity obtendria otros numeros y nadie se enteraria.

    Por eso cada caso se CONTRASTA contra un total calculado por otro
    camino, y si no calza el exportador se cae:

        G   contra la carga total que reporto el modelo resuelto
        Q   contra la suma de pesos_por_nivel()['Q']
        EX  contra el corte basal de fuerzas_sismicas()
        EY  idem

    ----------------------------------------------------------------
    G Y Q COMPARTEN GEOMETRIA, NO INTENSIDAD
    ----------------------------------------------------------------
    La sobrecarga se reparte por las MISMAS areas tributarias a 45
    grados que el peso muerto: es la misma losa. Lo que cambia es q.
    Q no lleva peso propio de barras, obviamente.
    """
    def vacio(nombre, descripcion):
        return {'nombre': nombre, 'descripcion': descripcion,
                'cargas_nodales': [], 'cargas_distribuidas': []}

    # ---------- G y Q: gravedad, por areas tributarias ----------
    gravitatorios = []
    for nombre, clave, con_peso_propio, desc in (
            ('G', 'muerta', True,
             'Peso propio de barras + losa + peso muerto adicional del '
             'plano de cargas. Caso COMPLETO.'),
            ('Q', 'viva', False,
             'Sobrecarga de uso del plano de cargas (500 kgf/m2 hasta el '
             'piso 3, 300 en el techo), repartida por las mismas areas '
             'tributarias a 45 grados que el peso muerto.')):
        caso = vacio(nombre, desc)
        total = 0.0
        acum = {}

        if con_peso_propio:
            # columnas y muros: mitad del peso en cada extremo
            for _tag, n1, n2, _sec, _v, _tipo, peso in m.verticales:
                acum[n1] = acum.get(n1, 0.0) - peso / 2.0
                acum[n2] = acum.get(n2, 0.0) - peso / 2.0
                total += peso

        for tag, n1, n2, sec, L, _peso, k in m.vigas:
            q = m.cargas_lamina[m.pisos[k - 1]['lamina']][clave]
            A = m.area_trib.get((min(n1, n2), max(n1, n2)), 0.0)
            w = (sec.A * m.gamma if con_peso_propio else 0.0) + q * A / L
            if w == 0.0:
                continue
            caso['cargas_distribuidas'].append(
                {'elemento': tag, 'wy': 0.0, 'wz': round(-w, 6), 'wx': 0.0})
            total += w * L

        # los brazos no llevan peso propio (ya esta contado en el muro),
        # pero si la losa que se apoya en ellos
        for tag, n1, n2, _sec, L, k in m.brazos:
            q = m.cargas_lamina[m.pisos[k - 1]['lamina']][clave]
            A = m.area_trib.get((min(n1, n2), max(n1, n2)), 0.0)
            if A <= 0:
                continue
            w = q * A / L
            caso['cargas_distribuidas'].append(
                {'elemento': tag, 'wy': 0.0, 'wz': round(-w, 6), 'wx': 0.0})
            total += w * L

        # losa que apoya directo sobre un muro: puntual en su nodo
        for tag, A in m.area_trib_nodal.items():
            if tag not in m.nodos:
                continue
            z = m.nodos[tag][2]
            k = next((i for i, zz in enumerate(m.niveles)
                      if abs(zz - z) < 1e-9), None)
            if k is None or k == 0:
                continue
            q = m.cargas_lamina[m.pisos[k - 1]['lamina']][clave]
            acum[tag] = acum.get(tag, 0.0) - q * A
            total += q * A

        for n, fz in sorted(acum.items()):
            caso['cargas_nodales'].append(
                {'nodo': n, 'fx': 0.0, 'fy': 0.0, 'fz': round(fz, 6),
                 'mx': 0.0, 'my': 0.0, 'mz': 0.0})
        gravitatorios.append((caso, total))

    # ---------- el contraste de G y Q ----------
    pesos = m.pesos_por_nivel()
    esperado = {'G': r['carga_total'],
                'Q': sum(p['Q'] for p in pesos.values())}
    casos = []
    for caso, total in gravitatorios:
        n = caso['nombre']
        err = abs(total - esperado[n])
        print('  caso %-2s exportado: %11.4f kN  (esperado %11.4f, error %.3e)'
              % (n, total, esperado[n], err))
        if err > 1e-4:
            raise RuntimeError(
                'El caso %s exportado (%.4f kN) no coincide con el que se '
                'resolvio (%.4f kN). Quien reanalice desde Unity obtendria '
                'otros resultados.' % (n, total, esperado[n]))
        casos.append(caso)

    # ---------- EX y EY: sismo en el maestro de cada diafragma ----------
    reparto = m.fuerzas_sismicas()
    s = m.geo.get('sismo', {})
    detalle = ('Sismo pseudoestatico: V = %.2f x peso sismico = %.2f kN, '
               'repartido en altura como V*W_k*h_k/suma(W*h) y aplicado en '
               'el nodo maestro de cada diafragma. h se mide desde la base '
               '(%+.2f). NO es un calculo NCh433 completo.'
               % (s.get('coef_basal', 0.10), m.corte_basal, m.niveles[0]))

    for nombre, ix in (('EX', 0), ('EY', 1)):
        caso = vacio(nombre, detalle.replace('Sismo', 'Sismo en %s:'
                                             % nombre[-1], 1))
        total = 0.0
        for k, (F, _W, _h) in sorted(reparto.items()):
            f = [0.0, 0.0, 0.0]
            f[ix] = round(F, 6)
            caso['cargas_nodales'].append(
                {'nodo': m.maestros[k], 'fx': f[0], 'fy': f[1], 'fz': f[2],
                 'mx': 0.0, 'my': 0.0, 'mz': 0.0})
            total += F
        err = abs(total - m.corte_basal)
        print('  caso %-2s exportado: %11.4f kN  (corte basal %11.4f, error %.3e)'
              % (nombre, total, m.corte_basal, err))
        if err > 1e-4:
            raise RuntimeError(
                'El caso %s suma %.4f kN pero el corte basal es %.4f kN.'
                % (nombre, total, m.corte_basal))
        casos.append(caso)

    return casos


def construir():
    """
    Arma el LT2, lo resuelve bajo G y devuelve el diccionario completo:
    el modelo estructural, sus resultados y lo que solo sirve para
    dibujar.

    Se separo de main() para que el pipeline pueda quedarse con la parte
    puramente estructural (ver comun/contrato.py) y escribir
    data/modelo/lt2.json -- el formato neutro, el mismo con el que se
    van a unir los dos edificios.
    """
    print('Construyendo el modelo LT2 ...')
    m = M.ModeloLT2().preparar().ensamblar('G').resolver()
    r = m.resumen()
    print('  caso G resuelto. Carga total %.2f kN' % r['carga_total'])
    print('  equilibrio: aplicada %.4f = reacciones %.4f (error %.2e)'
          % (r['carga_total'], r['reaccion_vertical'], r['error_equilibrio']))

    coords = m.nodos
    apoyos = set(m.nodos_base)

    # ---------- Nodos ----------
    nodos = []
    for n in sorted(coords):
        x, y, z = coords[n]
        d = ops.nodeDisp(n)
        fijo = n in apoyos
        nodos.append({
            'id': n,
            'x': round(x, 4), 'y': round(y, 4), 'z': round(z, 4),
            'fijo': fijo,
            'restricciones': [1] * 6 if fijo else [0] * 6,
            'auxiliar': False,
            'ux': round(d[0], 9), 'uy': round(d[1], 9), 'uz': round(d[2], 9),
        })

    # ---------- Secciones ----------
    # Iy = inercia LATERAL, Iz = inercia de GRAVEDAD, igual que el P1L2.
    # En modelo_lt2.seccion(): Iz = b*h^3/12 e Iy = h*b^3/12, con b el
    # ancho y h el canto. Para un muro b = espesor y h = largo, asi que
    # su Iz es la inercia FUERTE. Es la misma convencion.
    secciones = []
    for s in sorted(m.secciones.values(), key=lambda s: s.nombre):
        secciones.append({
            'nombre': s.nombre,
            'A': round(s.A, 6),
            'Iy': round(s.Iy, 9),
            'Iz': round(s.Iz, 9),
            'J': round(s.J, 9),
            'b': round(s.b, 4),
            'h': round(s.h, 4),
        })

    # ---------- Elementos ----------
    elementos = []

    def agregar(tag, ni, nj, tipo, sec, vecxz, largo=0.0, espesor=0.0,
                dir_largo=(0.0, 0.0)):
        ex, ey, ez = ejes_locales(coords[ni], coords[nj], vecxz)
        elementos.append({
            'id': tag, 'n1': ni, 'n2': nj,
            'tipo': tipo, 'seccion': sec.nombre,
            'vecxz': r6(vecxz),
            'localX': r6(ex), 'localY': r6(ey), 'localZ': r6(ez),
            # Hacia donde corre el LARGO del muro en planta.
            #
            # Unity no lo puede deducir de vecxz: en un muro vecxz es
            # la NORMAL al muro (asi queda la inercia fuerte donde
            # corresponde), no su direccion. Deducirlo dibujaba todos
            # los muros girados 90 grados -- el del ascensor atravesado
            # y el de fachada metido para adentro del edificio.
            'dir_largo': r6(dir_largo),
            # Solo para muros: su tamano REAL en planta. La barra
            # equivalente vive en el eje baricentrico; sin estos dos
            # numeros Unity dibujaria un muro de 8 m como una columna
            # flaca en medio del vano y no se podria juzgar si esta
            # donde dice el plano.
            'largo': round(float(largo), 4),
            'espesor': round(float(espesor), 4),
        })

    for tag, n1, n2, sec, vecxz, tipo, _peso in m.verticales:
        if tipo == 'muro':
            # vecxz es la normal al muro en planta; el largo corre
            # perpendicular a ella.
            agregar(tag, n1, n2, 'muro', sec, vecxz,
                    largo=sec.h, espesor=sec.b,
                    dir_largo=(-vecxz[1], vecxz[0]))
        else:
            agregar(tag, n1, n2, 'columna', sec, vecxz)

    VEC_HORIZONTAL = (0.0, 0.0, 1.0)
    for tag, n1, n2, sec, _L, _peso, _k in m.vigas:
        agregar(tag, n1, n2, tipo_de_viga(coords[n1], coords[n2]),
                sec, VEC_HORIZONTAL)

    # Los brazos van con tipo PROPIO. No son vigas (no tienen luz ni
    # seccion de viga) ni se pueden dibujar como placa de muro: son
    # horizontales, y la placa de muro usa la distancia entre nodos
    # como ALTURA -- un brazo de 3.6 m salia como una plancha de
    # 3.6 x 3.6 m flotando de canto. Eran las "escaleras" grises que
    # aparecian en el aire.
    for tag, n1, n2, sec, L, _k in m.brazos:
        agregar(tag, n1, n2, 'brazo', sec, VEC_HORIZONTAL)

    # ---------- Diafragmas ----------
    diafragmas = []
    for k, maestro in sorted(m.maestros.items()):
        esclavos = [m.nodo_de[(k, i)] for i in range(len(m.malla_nivel[k][0]))
                    if m.nodo_de[(k, i)] in m.nodos]
        diafragmas.append({'nodo_maestro': maestro, 'nodos': esclavos,
                           'perpendicular': 3})
        # El maestro tambien tiene que estar en la lista de nodos.
        xm, ym, zm = ops.nodeCoord(maestro)
        nodos.append({
            'id': maestro,
            'x': round(xm, 4), 'y': round(ym, 4), 'z': round(zm, 4),
            'fijo': False,
            'restricciones': [0, 0, 1, 1, 1, 0],
            'auxiliar': True,
            'ux': round(ops.nodeDisp(maestro, 1), 9),
            'uy': round(ops.nodeDisp(maestro, 2), 9),
            'uz': round(ops.nodeDisp(maestro, 3), 9),
        })

    # ---------- Areas tributarias ----------
    # Se exporta el area, la luz, la carga Y EL POLIGONO de cada barra:
    # el trapecio o el triangulo que la losa le descarga.
    #
    # Los poligonos van CONCATENADOS con una lista de tamanos, porque
    # JsonUtility de Unity no lee listas de listas. Una viga interior
    # toma un trapecio de un pano (4 vertices) y un triangulo del otro
    # (3): 7 vertices y tamanos [4, 3]. Dividir 7 entre 2 mezclaria los
    # vertices de los dos y dibujaria lineas que no existen.
    tributarias = []
    for tag, n1, n2, _sec, L, _peso, k in m.vigas:
        par = (min(n1, n2), max(n1, n2))
        A = m.area_trib.get(par, 0.0)
        if A <= 0:
            continue
        q = m.cargas_lamina[m.pisos[k - 1]['lamina']]['muerta']
        z = m.niveles[k]
        vertices, tamanos = [], []
        for pg in m.poli_trib.get(par, []):
            if len(pg) < 3:
                continue
            for (px, py) in pg:
                # VerticePlanta solo lleva (x, y): la cota es la del
                # piso y viaja una sola vez, en 'z' del area.
                vertices.append({'x': round(float(px), 4),
                                 'y': round(float(py), 4)})
            tamanos.append(len(pg))
        tributarias.append({
            'elemento': tag, 'nivel': k,
            'area': round(A, 6), 'luz': round(L, 4),
            'qG': round(q, 4),
            'carga_total': round(q * A, 4),
            'w': round(q * A / L, 6),
            'z': round(z, 4),
            'vertices': vertices, 'tamanos': tamanos,
            'n_poligonos': len(tamanos),
        })

    # Los BRAZOS son borde de pano igual que una viga -- son un pedazo
    # de muro -- y por lo tanto tambien reciben losa. Sin exportarlos
    # quedaban huecos blancos justo alrededor del nucleo de ascensores,
    # que es donde mas brazos hay.
    for tag, n1, n2, _sec, L, k in m.brazos:
        par = (min(n1, n2), max(n1, n2))
        A = m.area_trib.get(par, 0.0)
        if A <= 0:
            continue
        q = m.cargas_lamina[m.pisos[k - 1]['lamina']]['muerta']
        z = m.niveles[k]
        vertices, tamanos = [], []
        for pg in m.poli_trib.get(par, []):
            if len(pg) < 3:
                continue
            for (px, py) in pg:
                vertices.append({'x': round(float(px), 4),
                                 'y': round(float(py), 4)})
            tamanos.append(len(pg))
        tributarias.append({
            'elemento': tag, 'nivel': k,
            'area': round(A, 6), 'luz': round(L, 4),
            'qG': round(q, 4),
            'carga_total': round(q * A, 4),
            'w': round(q * A / L, 6),
            'z': round(z, 4),
            'vertices': vertices, 'tamanos': tamanos,
            'n_poligonos': len(tamanos),
        })

    # Los MUROS tambien reciben losa. Donde no hay viga -- el bloque
    # nororiente de esta planta -- el pano descarga directo sobre el
    # muro, y en el modelo eso va como carga PUNTUAL en su baricentro,
    # que es estaticamente equivalente.
    #
    # Sin exportar tambien esos panos, el visor mostraba un hueco
    # blanco de 56 m2 por piso donde en realidad si hay losa cargando:
    # la carga estaba en el modelo, pero no se veia, y quien mirara
    # habria concluido que faltaba.
    #
    # 'luz' es el largo del muro y 'w' la carga repartida sobre el:
    # es la lectura util al senalarlo, y es la misma resultante que el
    # modelo aplica en el nodo.
    for tag, n1, n2, sec, vecxz, tipo, _peso in m.verticales:
        if tipo != 'muro':
            continue
        A = m.area_trib_nodal.get(n2, 0.0)
        if A <= 0:
            continue
        z = coords[n2][2]
        k = next((i for i, zz in enumerate(m.niveles) if abs(zz - z) < 1e-9), None)
        if k is None or k == 0:
            continue
        q = m.cargas_lamina[m.pisos[k - 1]['lamina']]['muerta']
        vertices, tamanos = [], []
        for pg in m.poli_trib_nodal.get(n2, []):
            if len(pg) < 3:
                continue
            for (px, py) in pg:
                vertices.append({'x': round(float(px), 4),
                                 'y': round(float(py), 4)})
            tamanos.append(len(pg))
        L = max(sec.h, 1e-6)
        tributarias.append({
            'elemento': tag, 'nivel': k,
            'area': round(A, 6), 'luz': round(L, 4),
            'qG': round(q, 4),
            'carga_total': round(q * A, 4),
            'w': round(q * A / L, 6),
            'z': round(z, 4),
            'vertices': vertices, 'tamanos': tamanos,
            'n_poligonos': len(tamanos),
        })

    # ---------- Casos de carga ----------
    casos = construir_casos(m, r)

    modelo = {
        'info': {
            'descripcion': 'Edificio LT2 - planos de calculo 2024_22',
            'unidades': 'm, kN, kPa',
            'caso_precalculado': 'G',
            'nota': ('Geometria extraida de los planos DXF. Ejes locales '
                     'calculados en Python. Carga de losa por areas '
                     'tributarias a 45 grados sobre los panos detectados.'),
        },
        'material': {'fpc_MPa': m.fc, 'poisson': m.poisson, 'gamma': m.gamma},
        'secciones': secciones,
        'nodos': nodos,
        'elementos': elementos,
        'diafragmas': diafragmas,
        'brazos_rigidos': [],
        'areas_tributarias': tributarias,
        # OJO: los parametros del sismo (coef_basal, factor_sobrecarga,
        # exponente) NO van como clave suelta de este JSON. El contrato
        # con Unity es cerrado -- toda clave de aca tiene que existir
        # como campo en ModeloEstructural.cs, y agregarle un campo al C#
        # solo para transportar metadata no vale la pena.
        #
        # Su trazabilidad esta cubierta igual: los valores estan
        # declarados en perfiles/lt2_2024_22.json, viajan a
        # data/geometria/lt2.json, y el corte basal y como se repartio
        # quedan escritos en la 'descripcion' de los casos EX y EY.
        'casos_de_carga': casos,
        'resumen': {
            'n_nodos': len(nodos),
            'n_elementos': len(elementos),
            'n_columnas': r['columnas'],
            'n_vigas': r['vigas'],
            'n_muros': r['muros'] + r['brazos'],
            'n_apoyos': r['apoyos'],
            'n_diafragmas': r['diafragmas'],
            'carga_total_G': round(r['carga_total'], 4),
            'reaccion_vertical_kN': round(r['reaccion_vertical'], 4),
            'error_equilibrio_kN': r['error_equilibrio'],
            'uz_max_mm': round(r['uz_max_mm'], 4),
            'area_losa_por_piso_m2': {str(k): round(a, 2)
                                      for k, a in sorted(m.area_piso.items())},
        },
    }

    return modelo


def main(salida=None):
    salida = salida or SALIDA
    modelo = construir()

    os.makedirs(os.path.dirname(salida), exist_ok=True)
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump(modelo, f, indent=1, ensure_ascii=False)

    res = modelo['resumen']
    print('\n  %d nodos, %d elementos, %d secciones, %d diafragmas'
          % (res['n_nodos'], res['n_elementos'],
             len(modelo['secciones']), len(modelo['diafragmas'])))
    print('  UZ maximo: %.3f mm' % res['uz_max_mm'])
    print('  %s  (%.1f MB)' % (salida, os.path.getsize(salida) / 1e6))
    return 0


if __name__ == '__main__':
    # -o permite escribir el JSON en otra parte (lo usa el
    # laboratorio, que tiene su propio data/).
    _o = None
    if '-o' in sys.argv:
        _o = sys.argv[sys.argv.index('-o') + 1]
    sys.exit(main(_o))
