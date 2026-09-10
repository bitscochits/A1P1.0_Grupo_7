# -*- coding: utf-8 -*-
r"""
================================================================
 semana03/parametros.py  -  LO QUE DEFINE EL PROFESOR
================================================================
 Los valores viven en parametros.json, al lado. Este modulo los lee y
 los entrega como un diccionario que se puede sobreescribir por linea
 de comandos, que es lo que sirve si el profesor dicta numeros durante
 la demostracion:

        p = parametros.cargar(sys.argv[1:])
        python semana03/lab_semana03.py lt2 --q 2.5 --cs 0.15 --comb 1.2 1.6 1.0 0.3
        python semana03/lab_semana03.py --uso oficinas        una fila de NCh1537

 Todos los scripts de semana03/ lo usan asi.

 ----------------------------------------------------------------
 POR QUE NO BASTA CON EDITAR UN .py
 ----------------------------------------------------------------
 El enunciado pide que el codigo pueda acomodar CUALQUIER solicitud.
 Con los valores escritos en Python, cambiarlos en vivo significa
 abrir un archivo, editarlo sin equivocarse, guardarlo y volver a
 correr, delante del profesor. Con --q y --cs es un argumento.

 Y separar el valor de su justificacion importa: el JSON puede
 explicar de donde sale cada numero sin que eso ensucie el codigo.

 ----------------------------------------------------------------
 LA CARGA VIVA VIENE DE NCh1537
 ----------------------------------------------------------------
 q_Q por defecto es el de NCh1537 Of.2009 Tabla 4 para el uso que
 declara el JSON: salas de clases, 3.0 kN/m2, el uso predominante de
 una facultad. La tabla con las filas que interesan esta en el JSON y
 se elige con --uso; --q pone un numero cualquiera y lo deja marcado
 como dictado. Si el JSON declara un uso y un q que no calzan con la
 tabla, validar() lo detiene: un q sin fuente no pasa como si fuera
 de norma.
================================================================
"""
from __future__ import annotations

import io
import json
import os

_AQUI = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(_AQUI, 'parametros.json')

# Si el JSON no esta, se cae a estos valores para no dejar de correr.
POR_DEFECTO = {
    'q_Q': 3.0,                  # NCh1537 Of.2009 Tabla 4, salas de clases
    'uso': 'salas_de_clases',
    'usos': {},                  # la Tabla 4, cuando el JSON esta
    'norma_q': 'NCh1537 Of.2009, Tabla 4',
    'coef_sismico': 0.10,
    'fraccion_Q_sismica': 0.50,
    'patron': 'potencia',
    'k_patron': 1.0,
    'fracciones_patron': [],
    'combinacion': {'nombre': 'S3', 'G': 1.0, 'Q': 0.5, 'EX': 1.0, 'EY': 0.0},
    'combinaciones': [],
}

CASOS = ('G', 'Q', 'EX', 'EY')


def _leer(ruta=ARCHIVO):
    if not os.path.isfile(ruta):
        return dict(POR_DEFECTO)
    with io.open(ruta, encoding='utf-8') as f:
        d = json.load(f)
    combos = [c for c in d.get('combinaciones', []) if 'nombre' in c]
    nombre = d.get('combinacion_por_defecto')
    elegida = next((c for c in combos if c['nombre'] == nombre),
                   combos[0] if combos else POR_DEFECTO['combinacion'])
    cv = d.get('carga_viva', {})
    norma = cv.get('nch1537', {})
    return {
        'q_Q': float(cv.get('q_kNm2', POR_DEFECTO['q_Q'])),
        'uso': str(cv.get('uso', POR_DEFECTO['uso'])),
        'usos': {k: float(v)
                 for k, v in norma.get('valores_kNm2', {}).items()},
        'norma_q': str(norma.get('norma', POR_DEFECTO['norma_q'])),
        'coef_sismico': float(d.get('sismo', {}).get(
            'coeficiente', POR_DEFECTO['coef_sismico'])),
        'fraccion_Q_sismica': float(d.get('sismo', {}).get(
            'fraccion_Q', POR_DEFECTO['fraccion_Q_sismica'])),
        'patron': str(d.get('sismo', {}).get(
            'patron', POR_DEFECTO['patron'])),
        'k_patron': float(d.get('sismo', {}).get(
            'k_patron', POR_DEFECTO['k_patron'])),
        'fracciones_patron': [
            float(x) for x in d.get('sismo', {}).get(
                'fracciones_patron', POR_DEFECTO['fracciones_patron'])],
        'combinacion': dict(elegida),
        'combinaciones': combos,
    }


def validar(p):
    """
    Rechaza lo que no tiene sentido fisico. Vale la pena aunque los
    valores vengan de un archivo: un q negativo o una fraccion mayor
    que uno no dan error en ninguna parte, dan resultados.
    """
    if p['q_Q'] < 0:
        raise ValueError('q_Q no puede ser negativo')
    if p['uso'] != 'dictado' and p['usos']:
        if p['uso'] not in p['usos']:
            raise ValueError("uso %r no esta en la tabla de NCh1537 del "
                             "JSON. Hay: %s"
                             % (p['uso'], ', '.join(sorted(p['usos']))))
        if abs(p['q_Q'] - p['usos'][p['uso']]) > 1e-9:
            raise ValueError(
                'q_kNm2 = %g no es el valor de NCh1537 para %r (%g kN/m2): '
                'cambie el uso, o declare uso "dictado"'
                % (p['q_Q'], p['uso'], p['usos'][p['uso']]))
    if p['coef_sismico'] < 0:
        raise ValueError('el coeficiente sismico no puede ser negativo')
    if not 0.0 <= p['fraccion_Q_sismica'] <= 1.0:
        raise ValueError('la fraccion de Q para el peso sismico va entre '
                         '0 y 1')
    if p['patron'] not in ('potencia', 'nch433', 'manual'):
        raise ValueError("patron %r desconocido: use 'potencia', 'nch433' "
                         "o 'manual'" % p['patron'])
    if p['patron'] == 'potencia' and p['k_patron'] < 0:
        raise ValueError('k_patron no puede ser negativo')
    if p['patron'] == 'manual':
        if not p['fracciones_patron']:
            raise ValueError("patron 'manual' exige fracciones_patron")
        if any(float(f) < 0 for f in p['fracciones_patron']):
            raise ValueError('fracciones_patron no admite negativos')
    return p


def cargar(argv=None, ruta=ARCHIVO):
    """
    Los parametros, con lo que venga por linea de comandos encima.

        --q  <kN/m2>              sobrecarga de uso, un numero cualquiera
        --uso <nombre>            una fila de la Tabla 4 de NCh1537 (JSON)
        --cs <fraccion>           coeficiente sismico
        --fq <fraccion>           cuanta Q entra al peso sismico
        --comb <G> <Q> <EX> <EY>  factores de la combinacion
        --patron <potencia|nch433|manual>  reparto del corte en altura
        --k <exponente>              k de "potencia"
        --fracciones <f1> <f2> ...   reparto manual, se normaliza solo
        --combinacion <nombre>    una de las declaradas en el JSON

    Los argumentos que no reconoce los ignora, para poder convivir con
    los de cada script.
    """
    p = _leer(ruta)
    a = list(argv or [])

    def numero(bandera):
        if bandera in a:
            i = a.index(bandera)
            try:
                return float(a[i + 1])
            except (IndexError, ValueError):
                raise SystemExit('%s necesita un numero' % bandera)
        return None

    if '--uso' in a:
        i = a.index('--uso')
        nombre = a[i + 1] if i + 1 < len(a) else ''
        if nombre not in p['usos']:
            raise SystemExit('no hay uso %r en la tabla de NCh1537. Hay: %s'
                             % (nombre, ', '.join(sorted(p['usos']))))
        p['uso'] = nombre
        p['q_Q'] = p['usos'][nombre]
    v = numero('--q')
    if v is not None:
        p['q_Q'] = v
        p['uso'] = 'dictado'
    v = numero('--cs')
    if v is not None:
        p['coef_sismico'] = v
    v = numero('--fq')
    if v is not None:
        p['fraccion_Q_sismica'] = v
    v = numero('--k')
    if v is not None:
        p['k_patron'] = v

    if '--patron' in a:
        i = a.index('--patron')
        p['patron'] = a[i + 1] if i + 1 < len(a) else ''
    if '--fracciones' in a:
        i = a.index('--fracciones')
        crudas = []
        for x in a[i + 1:]:
            try:
                crudas.append(float(x))
            except ValueError:
                break
        if not crudas:
            raise SystemExit('--fracciones necesita al menos un numero')
        p['fracciones_patron'] = crudas
        p['patron'] = 'manual'

    if '--combinacion' in a:
        i = a.index('--combinacion')
        nombre = a[i + 1] if i + 1 < len(a) else ''
        elegida = next((c for c in p['combinaciones']
                        if c['nombre'] == nombre), None)
        if elegida is None:
            raise SystemExit(
                'no existe la combinacion %r. Declaradas: %s'
                % (nombre, ', '.join(c['nombre'] for c in p['combinaciones'])))
        p['combinacion'] = dict(elegida)

    if '--comb' in a:
        i = a.index('--comb')
        try:
            f = [float(x) for x in a[i + 1:i + 5]]
        except (IndexError, ValueError):
            raise SystemExit('--comb necesita cuatro numeros: G Q EX EY')
        if len(f) < 4:
            raise SystemExit('--comb necesita cuatro numeros: G Q EX EY')
        p['combinacion'] = dict(zip(CASOS, f))
        p['combinacion']['nombre'] = 'a mano'

    return validar(p)


def factores(combinacion):
    """Solo los cuatro factores, sin el nombre ni los comentarios."""
    return {c: float(combinacion.get(c, 0.0)) for c in CASOS}


def como_texto(combinacion):
    """'1.20 G + 1.60 Q + 1.00 EX' -- sin los terminos en cero."""
    partes = ['%.2f %s' % (v, c)
              for c, v in factores(combinacion).items() if abs(v) > 1e-12]
    return ' + '.join(partes) if partes else '(nula)'


def origen_q(p):
    """'NCh1537 Of.2009, Tabla 4: salas de clases'  o  'dictado, --q'."""
    if p['uso'] == 'dictado':
        return 'dictado, --q'
    return '%s: %s' % (p['norma_q'], p['uso'].replace('_', ' '))


def texto_patron(p):
    """'potencia k = 1 (triangular invertido)' o 'manual: 5, 10, ...'."""
    if p['patron'] == 'manual':
        return 'manual: ' + ', '.join('%g' % f for f in p['fracciones_patron'])
    if p['patron'] == 'nch433':
        return 'NCh433 6.2.6'
    k = p['k_patron']
    apodo = {0.0: ' (uniforme)', 1.0: ' (triangular invertido)'}.get(float(k), '')
    return 'potencia k = %g%s' % (k, apodo)


def describir(p):
    L = ['q_Q                 = %.4f kN/m2   (%s)' % (p['q_Q'], origen_q(p)),
         'coeficiente sismico = %.4f' % p['coef_sismico'],
         'fraccion de Q       = %.2f' % p['fraccion_Q_sismica'],
         'patron en altura    = %s' % texto_patron(p),
         'combinacion %-8s= %s' % ('(%s)' % p['combinacion'].get('nombre', ''),
                                   como_texto(p['combinacion']))]
    return '\n'.join('  ' + x for x in L)


if __name__ == '__main__':
    import sys
    p = cargar(sys.argv[1:])
    print('PARAMETROS DE LA SEMANA 3')
    print(describir(p))
    if p['combinaciones']:
        print()
        print('  combinaciones declaradas:')
        for c in p['combinaciones']:
            print('    %-18s %s' % (c['nombre'], como_texto(c)))
