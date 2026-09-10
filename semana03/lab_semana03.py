# -*- coding: utf-8 -*-
r"""
================================================================
 semana03/lab_semana03.py  -  PARTES A, B Y C
================================================================
 Carga viva, sismo pseudoestatico y superposicion sobre cualquiera
 de los tres edificios, con los parametros que dicte el profesor.

 Correr:
   python semana03/lab_semana03.py                      ingenieria
   python semana03/lab_semana03.py lt2
   python semana03/lab_semana03.py conjunto --cs 0.20 --k 2
   python semana03/lab_semana03.py lt2 --patron manual --fracciones 5 10 20 30 35
   python semana03/lab_semana03.py lt2 --q 3 --comb 1.2 1.0 1.4 0

 Los parametros salen de parametros.json y cualquiera se sobreescribe
 por linea de comandos; la lista completa esta en parametros.py.

 ----------------------------------------------------------------
 QUE HACE Y QUE NO
 ----------------------------------------------------------------
 Toma el modelo de data/modelo/, construye EN MEMORIA los casos Q
 (escalado a q_Q), EX y EY (con el patron pedido), los resuelve con el
 mismo motor que usa todo el proyecto y verifica lo que pide el
 enunciado. No escribe en data/: el modelo y sus resultados guardados
 no cambian.

 Las verificaciones no se reimplementan aca. La Parte B se la pide a
 comun/sismo.py y la Parte C a comun/combinar.py, que son los mismos
 modulos que se corren solos sobre data/resultados/. Una definicion de
 cada verificacion, no dos que despues divergen.

 ----------------------------------------------------------------
 COMO SE CONSTRUYE Q, Y QUE VERIFICA LA PARTE A DE VERDAD
 ----------------------------------------------------------------
 El caso Q del modelo dice DONDE va cada carga: repartida sobre una
 viga, o puntual en la cabeza del muro que recibe la losa. Eso se
 conserva. Lo que se reemplaza es la intensidad: cada elemento pasa a
 recibir q_Q * A_i, con el A_i que trae sellado.

 No se escala el caso entero por un factor. El plano del LT2 trae dos
 intensidades -- 500 kgf/m2 en los pisos y 300 en el techo -- y un
 factor unico habria dejado el techo a una presion y los pisos a otra,
 ninguna igual a q_Q. El enunciado pide UNA intensidad.

 Con eso, sum(Q) = q_Q * A es una identidad: asi se construyo. Lo que
 si dice algo es:

   1. que la construccion cubra toda la losa: cada carga nodal del
      modelo tiene que corresponder a un elemento con area, y cada
      elemento con area tiene que bajar por algun lado. Si no, se
      detiene con el elemento que sobra, en vez de adivinar;
   2. que la carga llegue al suelo: las reacciones de OpenSees contra
      lo aplicado. Un elemento suelto o una carga huerfana se ve aca.

 La revision fina del reparto -- contra el dibujo, con el peso propio
 separado, piso por piso -- es comun/verificar_tributarias.py.

 ----------------------------------------------------------------
 EL PESO SISMICO SE REPARTE POR DIAFRAGMA, NO POR COTA
 ----------------------------------------------------------------
 El conjunto tiene dos cuerpos y por lo tanto DOS diafragmas por
 nivel, a la misma altura. Buscar el nivel de una carga por su cota
 mas cercana metia todo el peso en el primero de cada par y dejaba al
 segundo cuerpo sin sismo. Un diafragma ya identifica cuerpo y nivel,
 asi que el reparto es por pertenencia: el nodo esta en tal diafragma,
 su peso va a ese diafragma.
================================================================
"""
from __future__ import annotations

import copy
import math
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))
sys.path.insert(0, _AQUI)

import calcular                              # noqa: E402
import combinar                              # noqa: E402
import contrato                              # noqa: E402
import parametros                            # noqa: E402
import rutas                                 # noqa: E402
import servidor_opensees as motor            # noqa: E402
import sismo                                 # noqa: E402

CASOS = ('G', 'Q', 'EX', 'EY')

# Tolerancias de las verificaciones, relativas.
TOL_REACCIONES = 1e-6      # carga aplicada contra reacciones
TOL_CONSTRUCCION_Q = 1e-9  # autocontrol: cada carga de Q a q_Q exacto


# ============================================================
# EL MODELO
# ============================================================
def caso_del_modelo(modelo, nombre):
    c = next((c for c in modelo.get('casos_de_carga', [])
              if c.get('nombre') == nombre), None)
    if c is None:
        raise SystemExit('el modelo no trae el caso %s' % nombre)
    return c


def largo(e, nodos):
    a, b = nodos[int(e['n1'])], nodos[int(e['n2'])]
    return math.sqrt(sum((float(b[k]) - float(a[k])) ** 2
                         for k in ('x', 'y', 'z')))


def niveles(modelo):
    """(cota, nodo maestro) de cada diafragma, de abajo hacia arriba."""
    nodos = {int(n['id']): n for n in modelo['nodos']}
    return sorted(((float(nodos[int(d['nodo_maestro'])]['z']),
                    int(d['nodo_maestro']))
                   for d in modelo.get('diafragmas', [])),
                  key=lambda t: t[0])


def indice_de_diafragma(modelo):
    """{nodo: i} con el diafragma al que pertenece cada nodo."""
    de_nodo = {}
    for i, d in enumerate(modelo.get('diafragmas', [])):
        de_nodo[int(d['nodo_maestro'])] = i
        for n in d.get('nodos', []):
            de_nodo.setdefault(int(n), i)
    return de_nodo


def peso_vertical_por_nivel(modelo, caso, de_nodo=None):
    """
    La carga vertical de un caso, sumada como peso positivo, por
    diafragma. Devuelve una lista alineada con niveles(modelo).

    Se reparte por PERTENENCIA al diafragma (ver el encabezado). La
    cota mas cercana queda solo de respaldo, para nodos sueltos que no
    cuelgan de ninguno.
    """
    nodos = {int(n['id']): n for n in modelo['nodos']}
    elementos = {int(e['id']): e for e in modelo['elementos']}
    orden = niveles(modelo)
    cotas = [c for c, _m in orden]
    # El indice que devuelve indice_de_diafragma es el del JSON, no el
    # ordenado por cota: se traduce.
    de_nodo = de_nodo if de_nodo is not None else indice_de_diafragma(modelo)
    maestros_ordenados = [m for _c, m in orden]
    posicion = {int(d['nodo_maestro']): maestros_ordenados.index(int(d['nodo_maestro']))
                for d in modelo.get('diafragmas', [])}
    json_a_orden = {i: posicion[int(d['nodo_maestro'])]
                    for i, d in enumerate(modelo.get('diafragmas', []))}

    def mas_cercano(z):
        return min(range(len(cotas)), key=lambda i: abs(z - cotas[i]))

    pesos = [0.0] * len(cotas)
    for c in caso.get('cargas_nodales', []):
        nid = int(c['nodo'])
        i = de_nodo.get(nid)
        i = json_a_orden[i] if i is not None else mas_cercano(float(nodos[nid]['z']))
        pesos[i] += -float(c.get('fz', 0.0))

    for c in caso.get('cargas_distribuidas', []):
        e = elementos[int(c['elemento'])]
        a, b = int(e['n1']), int(e['n2'])
        i = de_nodo.get(a, de_nodo.get(b))
        if i is not None:
            i = json_a_orden[i]
        else:
            z = (float(nodos[a]['z']) + float(nodos[b]['z'])) / 2.0
            i = mas_cercano(z)
        pesos[i] += -float(c.get('wz', 0.0)) * largo(e, nodos)
    return pesos


def caso_q_uniforme(modelo, q, base, con_area):
    r"""
    El caso Q con cada elemento a la misma intensidad q. Ver el
    encabezado: se conserva por donde baja cada carga y se reemplaza
    cuanto vale.

    Devuelve el caso y, aparte, que elementos bajan como carga puntual
    y en que nodo, para poder informarlo y revisarlo.
    """
    nodos = {int(n['id']): n for n in modelo['nodos']}
    elementos = {int(e['id']): e for e in modelo['elementos']}

    repartidos = {int(c['elemento']) for c in base.get('cargas_distribuidas', [])}
    # Un elemento con losa que no la baja repartida la baja puntual, en
    # su cabeza (n2). Es como la arma el LT2 para los muros.
    puntuales = {}
    for t in con_area:
        if t not in repartidos:
            puntuales.setdefault(int(elementos[t]['n2']), []).append(t)

    caso = {'nombre': 'Q',
            'descripcion': 'sobrecarga de uso q_Q = %g kN/m2, uniforme, por '
                           'las areas tributarias del modelo' % q,
            contrato.CAMPO_PESO_PROPIO: False,
            'cargas_nodales': [], 'cargas_distribuidas': []}

    for c in base.get('cargas_distribuidas', []):
        t = int(c['elemento'])
        if t not in con_area:
            raise SystemExit('el caso Q del modelo carga el elemento %d, que '
                             'no tiene area tributaria: esa carga no es losa '
                             'y no se sabe que es' % t)
        caso['cargas_distribuidas'].append(
            {'elemento': t, 'wx': 0.0, 'wy': 0.0,
             'wz': -q * con_area[t] / largo(elementos[t], nodos)})

    pendientes = dict(puntuales)
    for c in base.get('cargas_nodales', []):
        n = int(c['nodo'])
        ids = pendientes.pop(n, None)
        if not ids:
            raise SystemExit('el caso Q del modelo pone una carga puntual en '
                             'el nodo %d y ningun elemento con area la '
                             'explica' % n)
        caso['cargas_nodales'].append(
            {'nodo': n, 'fx': 0.0, 'fy': 0.0,
             'fz': -q * sum(con_area[t] for t in ids),
             'mx': 0.0, 'my': 0.0, 'mz': 0.0})
    if pendientes:
        sobran = sorted(t for ids in pendientes.values() for t in ids)
        raise SystemExit('%d elemento(s) con area de losa no bajan ni '
                         'repartidos ni como carga puntual: %s'
                         % (len(sobran), sobran[:8]))
    return caso, puntuales


def intensidades_del_modelo(modelo, base, con_area, puntuales):
    """
    Con que presion viene el caso Q del modelo, carga por carga, para
    poder decir de donde se partio: el plano puede traer una intensidad
    distinta a q_Q, o mas de una. Devuelve {q: cuantas cargas}.
    """
    nodos = {int(n['id']): n for n in modelo['nodos']}
    elementos = {int(e['id']): e for e in modelo['elementos']}
    cuenta = {}
    for c in base.get('cargas_distribuidas', []):
        t = int(c['elemento'])
        A = con_area.get(t, 0.0)
        if A > 0:
            q = round(-float(c.get('wz', 0.0)) * largo(elementos[t], nodos) / A, 4)
            cuenta[q] = cuenta.get(q, 0) + 1
    for c in base.get('cargas_nodales', []):
        A = sum(con_area[t] for t in puntuales.get(int(c['nodo']), []))
        if A > 0:
            q = round(-float(c.get('fz', 0.0)) / A, 4)
            cuenta[q] = cuenta.get(q, 0) + 1
    return dict(sorted(cuenta.items(), key=lambda kv: -kv[1]))


# ============================================================
# LOS CASOS DE LA SEMANA 3
# ============================================================
def factores_nch433(pesos, alturas):
    r"""
    El reparto en altura de NCh433 Of.1996 Mod.2009, articulo 6.2.6.

    NO es la forma de exponente. NCh433 define

        A_k = raiz(1 - Z_(k-1)/H) - raiz(1 - Z_k/H)
        F_k = A_k P_k / suma(A_j P_j) * Q_0

    con Z_k la altura del nivel k sobre la base, Z_0 = 0 y H la altura
    total. La diferencia de raices concentra mas fuerza arriba que el
    triangular, y en el ultimo nivel el segundo termino se anula.

    El coeficiente se calcula por ALTURA DISTINTA y no por indice: el
    conjunto tiene dos diafragmas por nivel, a la misma cota, y tomar
    "el anterior de la lista" le daria A = 0 al segundo de cada par.
    """
    H = max(alturas)
    if H <= 0:
        raise SystemExit('el edificio no tiene altura sobre la base')

    cotas = sorted(set(alturas))
    A = {}
    anterior = 0.0
    for z in cotas:
        A[z] = math.sqrt(max(0.0, 1.0 - anterior / H)) \
             - math.sqrt(max(0.0, 1.0 - z / H))
        anterior = z
    return [A[h] * W for W, h in zip(pesos, alturas)]


def factores_patron(pesos, alturas, p):
    """
    Fraccion del corte basal que toma cada nivel, de abajo hacia arriba.

    El enunciado deja el patron en manos del profesor y pide que el
    codigo acomode cualquier solicitud, asi que la forma del reparto no
    puede estar fija aca. Hay tres formas:

        'potencia'  F_i proporcional a W_i * h_i**k, la forma de ASCE 7
                    12.8.3: k = 0 uniforme, k = 1 el triangular clasico,
                    k = 2 el tope que ASCE da a los edificios de periodo
                    largo
        'nch433'    el reparto de NCh433 6.2.6, que es la norma chilena
                    y NO usa exponente: ver factores_nch433()
        'manual'    el reparto explicito que se dicte

    No depende de la forma del edificio: recibe pesos y alturas por
    nivel, que es lo unico que el reparto necesita.
    """
    if p['patron'] == 'manual':
        if len(p['fracciones_patron']) != len(pesos):
            raise SystemExit(
                'fracciones_patron trae %d valores y el edificio tiene %d '
                'niveles' % (len(p['fracciones_patron']), len(pesos)))
        crudos = [float(f) for f in p['fracciones_patron']]
    elif p['patron'] == 'nch433':
        crudos = factores_nch433(pesos, alturas)
    else:
        crudos = [W * h ** p['k_patron'] for W, h in zip(pesos, alturas)]
    total = sum(crudos)
    if total <= 0.0:
        raise SystemExit('el patron da fuerza nula en todos los niveles: '
                         'revise k_patron o fracciones_patron')
    return [c / total for c in crudos]


def caso_sismico(nombre, maestros, fuerzas):
    """El caso EX o EY: una fuerza horizontal en cada nodo maestro."""
    eje = 'fx' if nombre == 'EX' else 'fy'
    return {'nombre': nombre,
            'descripcion': 'sismo pseudoestatico en %s' % nombre[-1],
            'cargas_nodales': [{'nodo': m, eje: F}
                               for m, F in zip(maestros, fuerzas)],
            'cargas_distribuidas': []}


def armar_casos(modelo, p):
    r"""
    Los cuatro casos de la semana, construidos en memoria con los
    parametros del profesor, mas todo lo intermedio que hace falta
    para mostrarlos.

    G    el del modelo, tal cual
    Q    cada elemento con losa a q_Q * A_i, por la misma via -- repartida
         o puntual -- que en el caso Q del modelo (ver caso_q_uniforme)
    EX   V = Cs * W, con W = G + f * Q por nivel, repartido en altura
    EY   segun el patron pedido y aplicado en los nodos maestros
    """
    elementos = {int(e['id']): e for e in modelo['elementos']}
    con_area = {t: float(e[contrato.CAMPO_AREA]) for t, e in elementos.items()
                if float(e.get(contrato.CAMPO_AREA, 0.0)) > 0}
    if not con_area:
        raise SystemExit('el modelo no trae areas tributarias; sin ellas no '
                         'hay Parte A. Hay que volver a armarlo.')
    area = sum(con_area.values())

    orden = niveles(modelo)
    if not orden:
        raise SystemExit('el modelo no trae diafragmas; sin ellos no hay '
                         'nodos maestros donde aplicar el sismo')
    maestros = [m for _c, m in orden]
    cota_base = min(float(n['z']) for n in modelo['nodos'])
    alturas = [c - cota_base for c, _m in orden]

    caso_g = caso_del_modelo(modelo, 'G')
    q_del_modelo = caso_del_modelo(modelo, 'Q')
    caso_q, puntuales = caso_q_uniforme(modelo, p['q_Q'], q_del_modelo, con_area)
    intensidades = intensidades_del_modelo(modelo, q_del_modelo, con_area, puntuales)

    pesos_G = peso_vertical_por_nivel(modelo, caso_g)
    pesos_Q = peso_vertical_por_nivel(modelo, caso_q)
    pesos = [g + p['fraccion_Q_sismica'] * q for g, q in zip(pesos_G, pesos_Q)]
    factores = factores_patron(pesos, alturas, p)
    V = p['coef_sismico'] * sum(pesos)
    fuerzas = [V * f for f in factores]

    return {
        'casos': {'G': caso_g, 'Q': caso_q,
                  'EX': caso_sismico('EX', maestros, fuerzas),
                  'EY': caso_sismico('EY', maestros, fuerzas)},
        'con_area': con_area, 'area': area, 'puntuales': puntuales,
        'intensidades_del_modelo': intensidades,
        'niveles': orden, 'alturas': alturas,
        'pesos_G': pesos_G, 'pesos_Q': pesos_Q, 'pesos_sismicos': pesos,
        'factores': factores, 'V': V, 'fuerzas': fuerzas,
    }


def resolver(modelo, casos):
    """Los casos resueltos en memoria, por nombre. El modelo no se toca."""
    datos = copy.deepcopy(modelo)
    datos['casos_de_carga'] = list(casos.values())
    salida = motor.construir_y_resolver(datos)
    return datos, {r['nombre']: r for r in salida['casos']}


# ============================================================
# LAS PARTES
# ============================================================
def parte_a(modelo, arm, resultados, p):
    """Carga viva: Q se construyo a q_Q en cada elemento; lo que se
    verifica es que cubra toda la losa y que llegue entera al suelo."""
    q = p['q_Q']
    nodos = {int(n['id']): n for n in modelo['nodos']}
    elementos = {int(e['id']): e for e in modelo['elementos']}
    caso_q = arm['casos']['Q']
    aplicada = sum(peso_vertical_por_nivel(modelo, caso_q))
    reacciones = sum(float(r['fz']) for r in resultados['Q']['reacciones'])
    err_reac = abs(aplicada - reacciones) / max(abs(aplicada), 1e-12)

    # Autocontrol de la construccion: cada carga, leida de vuelta, tiene
    # que dar q_Q. Si esto falla es un error del script, no del modelo.
    peor = 0.0
    for c in caso_q['cargas_distribuidas']:
        e = elementos[int(c['elemento'])]
        q_i = -float(c['wz']) * largo(e, nodos) / arm['con_area'][int(e['id'])]
        peor = max(peor, abs(q_i - q) / q)
    for c in caso_q['cargas_nodales']:
        A = sum(arm['con_area'][t] for t in arm['puntuales'][int(c['nodo'])])
        peor = max(peor, abs(-float(c['fz']) / A - q) / q)

    n_puntuales = sum(len(v) for v in arm['puntuales'].values())
    venia = '  y  '.join('%.4f kN/m2 en %d cargas' % (qq, n)
                         for qq, n in arm['intensidades_del_modelo'].items())

    print()
    print('[A] CARGA VIVA   q_Q = %.2f kN/m2   (%s)'
          % (q, parametros.origen_q(p)))
    print('  elementos con losa  %4d   %d bajan repartidos sobre la barra, %d '
          'como carga puntual en la cabeza del muro'
          % (len(arm['con_area']), len(caso_q['cargas_distribuidas']), n_puntuales))
    print('  area tributaria     %.4f m2' % arm['area'])
    print('  el modelo traia Q a %s' % venia)
    print('  se reconstruye con q_Q en cada elemento; leida de vuelta, peor '
          'desvio %.1e' % peor)
    print('  q_Q * A                            %14.4f kN   lo que se pide'
          % (q * arm['area']))
    print('  aplicada, sum(w L) + sum(F)        %14.4f kN   identidad: asi se '
          'construyo' % aplicada)
    print('  reacciones Rz de OpenSees          %14.4f kN   lo que llega al '
          'suelo' % reacciones)
    print('  error aplicada vs reacciones       %14.3e relativo' % err_reac)
    print('  Q por diafragma [kN]: ' + ', '.join('%.2f' % w for w in arm['pesos_Q']))
    ok = err_reac < TOL_REACCIONES and peor < TOL_CONSTRUCCION_Q
    print('  %s' % ('OK' if ok else 'REVISAR'))
    return ok


def parte_b(datos, arm, resultados, p):
    """
    Sismo: carga total, corte basal, sentido de la deformada y torsion.
    La revision la hace comun/sismo.py; aca solo se le entregan los
    casos que se acaban de construir y resolver.
    """
    print()
    print('[B] SISMO PSEUDOESTATICO   Cs = %.4f   W = G + %.2f Q   patron: %s'
          % (p['coef_sismico'], p['fraccion_Q_sismica'],
             parametros.texto_patron(p)))
    print('  %8s %14s %14s %12s %12s'
          % ('cota', 'W sismico [kN]', 'reparto [%]', 'F [kN]', 'maestro'))
    for (cota, m), W, f, F in zip(arm['niveles'], arm['pesos_sismicos'],
                                  arm['factores'], arm['fuerzas']):
        print('  %+8.2f %14.2f %14.2f %12.2f %12d' % (cota, W, 100 * f, F, m))
    print('  corte basal V = Cs * sum(W) = %.4f kN;  sum(F) = %.4f kN;  '
          'diferencia %.1e' % (arm['V'], sum(arm['fuerzas']),
                               abs(arm['V'] - sum(arm['fuerzas']))))

    malos = []
    for caso in ('EX', 'EY'):
        inf = sismo.analizar(datos, arm['casos'][caso], resultados[caso], caso)
        print()
        sismo.imprimir(inf)
        malos += sismo.problemas(inf)

    print()
    if malos:
        print('  %d PROBLEMA(S):' % len(malos))
        for m in malos:
            print('    - %s' % m)
        print('  REVISAR')
        return False
    print('  la carga aplicada baja entera al suelo, cada piso va hacia donde')
    print('  lo empujan y el desplazamiento crece con la altura.')
    print('  OK')
    return True


def parte_c(edificio, datos, resultados, lambdas):
    """
    Superposicion: la combinacion algebraica contra la corrida
    explicita, sobre TODO el modelo, y los tres numeros del enunciado
    a la vista.
    """
    r = combinar.verificar(edificio, lambdas, por_caso=resultados, modelo=datos)
    alg, exp = r['algebraico'], r['explicito']

    # Un nodo, un apoyo y una barra representativos: el maestro del
    # techo, el primer apoyo de la base y la primera viga.
    techo = niveles(datos)[-1][1]
    z0 = min(float(n['z']) for n in datos['nodos'])
    apoyo = next(int(n['id']) for n in datos['nodos']
                 if any(n.get('restricciones', [])) and abs(float(n['z']) - z0) < 1e-6)
    viga = next(int(e['id']) for e in datos['elementos']
                if e.get('tipo', '').startswith('viga'))

    def de(lista, i, k):
        f = next(x for x in lista if int(x['id']) == i)
        return float(f[k]) if k != 'My' else float(f['f'][4])

    print()
    print('[C] SUPERPOSICION   R = %s' % parametros.como_texto(lambdas))
    print('  los tres del enunciado:')
    print('    %-34s %14s %14s %10s'
          % ('', 'superposicion', 'corrida', 'error'))
    for etiqueta, lista, i, k in (
            ('desplazamiento ux, techo (nodo %d)' % techo, 'desplazamientos', techo, 'ux'),
            ('reaccion fz, apoyo (nodo %d)' % apoyo, 'reacciones', apoyo, 'fz'),
            ('momento My, viga (elem %d)' % viga, 'fuerzas_elementos', viga, 'My')):
        a, b = de(alg[lista], i, k), de(exp[lista], i, k)
        print('    %-34s %14.8g %14.8g %10.2e' % (etiqueta, a, b, abs(a - b)))

    print('  y sobre todo el modelo (comun/combinar.py):')
    for clave, v in r['informe'].items():
        print('    %-20s %5d valores   peor %.2e   cota de redondeo %.2e   %s'
              % (clave, v['n_comparados'], v['peor_absoluto'],
                 v['piso_de_redondeo'], 'ok' if v['pasa'] else '<-- REVISAR'))
    print('  el desacuerdo queda bajo lo que mete el redondeo del motor: la')
    print('  superposicion no aporta error medible. K u = F es lineal.')
    print('  %s' % ('OK' if r['paso'] else 'REVISAR'))
    return r['paso']


# ============================================================
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    edificio = 'ingenieria'
    if argv and not argv[0].startswith('-'):
        edificio = argv.pop(0)
    p = parametros.cargar(argv)
    lambdas = parametros.factores(p['combinacion'])

    if not os.path.isfile(rutas.modelo(edificio)):
        hay = sorted(os.path.splitext(f)[0]
                     for f in os.listdir(rutas.MODELO) if f.endswith('.json'))
        raise SystemExit('no existe el modelo %r. Hay: %s'
                         % (edificio, ', '.join(hay)))
    modelo = contrato.cargar_modelo(edificio)

    print('=' * 72)
    print('  SEMANA 3   %s' % edificio.upper())
    print('=' * 72)
    print('  %s' % contrato.resumen(modelo))
    print(parametros.describir(p))

    arm = armar_casos(modelo, p)
    datos, resultados = resolver(modelo, arm['casos'])

    ok = parte_a(modelo, arm, resultados, p)
    ok = parte_b(datos, arm, resultados, p) and ok
    ok = parte_c(edificio, datos, resultados, lambdas) and ok

    print()
    print('=' * 72)
    print('  %s' % ('LAS TRES PARTES CIERRAN' if ok else 'HAY ALGO QUE REVISAR'))
    print('=' * 72)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
