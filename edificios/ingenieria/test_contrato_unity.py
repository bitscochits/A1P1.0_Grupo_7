"""
================================================================
 test_contrato_unity.py
================================================================
 Verifica que el C# de Unity y el Python de OpenSees hablen el
 MISMO idioma.

 POR QUE ESTE TEST EXISTE
 ------------------------
 JsonUtility de Unity falla EN SILENCIO. Si una clase C# declara
 'public float uz' y el JSON trae 'Uz' o 'u_z', no hay error, no
 hay warning: el campo simplemente queda en 0.0 y la deformada sale
 plana. Se descubre mirando la escena y no entendiendo por que.

 Como aca no hay Unity para compilar, se hace lo siguiente:
   1. Se leen los campos publicos de las clases de ModeloEstructural.cs
      con una regex.
   2. Se comparan contra las claves reales del JSON que produce
      generar_json_unity.py y contra las que devuelve el servidor.
   3. Se simula el comportamiento de JsonUtility al SERIALIZAR
      (escribe siempre todos los campos, los vacios como []) y se
      manda eso al servidor, que debe aceptarlo.

 LO QUE ESTE TEST NO PUEDE HACER
   - Compilar el C#. Errores de sintaxis o de tipos no se detectan.
   - Verificar que la escena de Unity este bien armada.
   Eso hay que probarlo en Unity.

 Correr con:  python test_contrato_unity.py
================================================================
"""

import io
import json
import re
import os
import sys

# El servidor y el benchmark ya no viven junto a este archivo.
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _c in ('comun', 'benchmark'):
    sys.path.insert(0, os.path.join(_RAIZ, _c))


fallos = []
RAIZ = _RAIZ

# Los .cs viven dentro del proyecto Unity, no sueltos en la raiz: una
# sola copia, la que Unity compila. Antes estaban duplicados y podian
# divergir en silencio.
SCRIPTS = os.path.join(RAIZ, 'unity', 'Assets', 'Scripts')


def check(nombre, cond, detalle=""):
    print(f"  [{'OK  ' if cond else 'FALLA'}] {nombre}" +
          (f"   {detalle}" if detalle else ""))
    if not cond:
        fallos.append(nombre)


# ------------------------------------------------------------
# Leer los campos publicos de cada clase C#
# ------------------------------------------------------------
# Captura:  public float ux, uy, uz;   ->  [ux, uy, uz]
#           public List<Nodo> nodos;   ->  [nodos]
#           public int[] restricciones;->  [restricciones]
# Ignora:   propiedades (get/set), metodos (parentesis), const.
RE_CLASE = re.compile(r'public\s+(?:static\s+)?class\s+(\w+)')
RE_CAMPO = re.compile(
    r'^\s*public\s+'
    r'(?!class\b|static\b)'
    r'(?:[\w<>\[\],\s\.]+?)\s+'          # tipo
    r'([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)'   # nombre(s)
    r'\s*(?:=\s*[^;]+)?;'                # inicializador opcional
)


def campos_csharp(ruta):
    """Devuelve {NombreClase: [campos publicos]} de un archivo .cs."""
    texto = io.open(ruta, encoding='utf-8').read()
    # quitar comentarios de bloque y de linea
    texto = re.sub(r'/\*.*?\*/', '', texto, flags=re.S)
    texto = re.sub(r'//[^\n]*', '', texto)

    clases = {}
    actual = None
    for linea in texto.splitlines():
        m = RE_CLASE.search(linea)
        if m:
            actual = m.group(1)
            clases[actual] = []
            continue
        if actual is None:
            continue
        if '{' in linea and '}' in linea and 'get' in linea:
            continue                      # propiedad en una linea
        m = RE_CAMPO.match(linea)
        if m:
            for n in m.group(1).split(','):
                clases[actual].append(n.strip())
    return clases


print("=" * 68)
print("  TEST: CONTRATO UNITY <-> OPENSEES")
print("=" * 68)

CS = campos_csharp(os.path.join(SCRIPTS, 'ModeloEstructural.cs'))
print(f"\n  Clases leidas de ModeloEstructural.cs: {len(CS)}")

# ------------------------------------------------------------
print("\n1. No hay clases duplicadas entre los .cs")
# Si dos archivos declaran la misma clase, Unity no compila.
declaradas = {}
for f in ('ModeloEstructural.cs', 'VisorEstructura.cs',
          'AnalizadorEstructural.cs', 'CamaraOrbital.cs',
          'EditorEstructura.cs'):
    ruta = os.path.join(SCRIPTS, f)
    if not os.path.exists(ruta):
        continue
    for c in campos_csharp(ruta):
        declaradas.setdefault(c, []).append(f)
dups = {c: fs for c, fs in declaradas.items() if len(fs) > 1}
check("ninguna clase declarada dos veces", not dups,
      "" if not dups else f"duplicadas: {dups}")

# ------------------------------------------------------------
print("\n2. modelo_unity.json calza con las clases C#")
# Nuestras clases viven en el namespace GLOBAL, asi que le GANAN al
# 'using UnityEngine'. Declarar 'class Material' rompe cualquier
# 'new Material(Shader.Find(...))' del proyecto -- y en Unity un solo
# error de compilacion bloquea Add Component para TODOS los scripts.
UNITYENGINE = {
    'Material', 'Mesh', 'Object', 'Transform', 'Camera', 'Light',
    'Renderer', 'Collider', 'Rigidbody', 'Texture', 'Shader', 'Color',
    'Vector2', 'Vector3', 'Vector4', 'Quaternion', 'Bounds', 'Ray',
    'Animation', 'Animator', 'Sprite', 'Canvas', 'Random', 'Debug',
    'Time', 'Input', 'Application', 'Resources', 'GameObject', 'Scene',
    'Component', 'Behaviour', 'MonoBehaviour', 'Event', 'Gradient',
}
choques = sorted(set(declaradas) & UNITYENGINE)
check("ningun nombre de clase choca con UnityEngine", not choques,
      "" if not choques else f"CHOCAN: {choques} -> renombralas")

ruta_json = os.path.join(RAIZ, 'data', 'unity', 'benchmark.json')
check("modelo_unity.json existe", os.path.exists(ruta_json))
if not os.path.exists(ruta_json):
    raise SystemExit("Genera el JSON primero: python generar_json_unity.py")

M = json.load(io.open(ruta_json, encoding='utf-8'))


def comparar(nombre_clase, dic, contexto):
    """Toda clave del JSON debe existir como campo de la clase C#."""
    campos = set(CS.get(nombre_clase, []))
    if not campos:
        check(f"{contexto}: la clase {nombre_clase} existe en C#", False)
        return
    faltan = [k for k in dic if k not in campos]
    check(f"{contexto} -> {nombre_clase}", not faltan,
          "" if not faltan else f"el C# NO tiene: {faltan}")


comparar('ModeloEstructural', M, "raiz del JSON")
comparar('InfoModelo', M['info'], "info")
comparar('MaterialModelo', M['material'], "material")
comparar('Seccion', M['secciones'][0], "secciones[0]")
comparar('Nodo', M['nodos'][0], "nodos[0]")
comparar('Elemento', M['elementos'][0], "elementos[0]")
comparar('CasoDeCarga', M['casos_de_carga'][0], "casos_de_carga[0]")
comparar('CargaDistribuida', M['casos_de_carga'][0]['cargas_distribuidas'][0],
         "cargas_distribuidas[0]")
ex = next(c for c in M['casos_de_carga'] if c['nombre'] == 'EX')
comparar('CargaNodal', ex['cargas_nodales'][0], "cargas_nodales[0]")

# El JSON del BENCHMARK no tiene muros, asi que comparar solo
# 'secciones[0]' (una columna) deja sin verificar los campos que solo
# trae la seccion de muro: 'largo' y 'espesor', que Unity usa para
# dibujarlo como prisma. Se revisa aparte contra el JSON del edificio.
ruta_edificio = os.path.join(RAIZ, 'data', 'unity', 'ingenieria.json')
if os.path.exists(ruta_edificio):
    E = json.load(io.open(ruta_edificio, encoding='utf-8'))
    muros = [s for s in E['secciones'] if s['nombre'].startswith('muro')]
    check("el JSON del edificio trae secciones de muro", bool(muros))
    if muros:
        comparar('Seccion', muros[0], "edificio: seccion de muro")

    # TODA seccion tiene que traer sus dimensiones de dibujo, no solo
    # los muros: el visor dibuja columnas y vigas con su seccion real.
    #
    # Tres secciones quedan FUERA de las comprobaciones de coherencia
    # que siguen, y por motivos distintos:
    #
    #   brazo_rigido  no es un elemento real, sino el tramo entre el
    #                 eje del muro y la cara donde llega la viga. Su A
    #                 e I estan inflados x100 a proposito.
    #   pilar_metal   son TUBOS CUADRADOS HUECOS (300x300x20 y
    #   viga_metal    300x300x5). Un tubo no cumple A = largo*espesor
    #                 por definicion: 300x300x5 tiene 0.0059 m2, no
    #                 0.09. Sus dimensiones de dibujo son el lado
    #                 exterior, que es lo correcto para dibujarlo.
    #
    # El test tiene razon al cazarlas: se excluyen a mano, con nombre
    # y motivo, en vez de aflojar el criterio para todas.
    #   diagonal_metal  es una barra REDONDA: A = pi*d^2/4, no d^2.
    NO_MACIZAS = {'brazo_rigido', 'pilar_metal', 'viga_metal',
                  'diagonal_metal'}
    secs = [q for q in E['secciones'] if q['nombre'] not in NO_MACIZAS]

    # Pero las huecas SI tienen que traer su material propio: sin E y
    # G el servidor las calcularia con el modulo del hormigon.
    for q in E['secciones']:
        if q['nombre'].endswith('_metal'):
            check(f"la seccion '{q['nombre']}' trae su E y G propios",
                  q.get('E', 0) > 1e6 and q.get('G', 0) > 1e6,
                  f"E={q.get('E')} G={q.get('G')}")
    malos = [s['nombre'] for s in E['secciones']
             if s.get('largo', 0) <= 0 or s.get('espesor', 0) <= 0]
    check("toda seccion trae largo y espesor > 0", not malos,
          "" if not malos else f"sin dimensiones: {malos}")

    # El area tiene que ser consistente con las dimensiones que se
    # dibujan: si no, Unity pintaria una barra distinta de la que se
    # calculo.
    peor = max(abs(s.get('largo', 0) * s.get('espesor', 0) - s['A'])
               for s in secs)
    check("A = largo * espesor en todas las secciones", peor < 1e-6,
          f"peor discrepancia {peor:.2e} m2")

    # El 'largo' que se dibuja tiene que ser el lado que da la inercia
    # FUERTE, o la barra se veria acostada (una viga de 30 de alto por
    # 60 de ancho). Para un rectangulo esa inercia vale
    # espesor*largo^3/12, pero en que casilla queda depende de si el
    # elemento es vertical, porque el servidor solo cruza los que NO
    # lo son:
    #
    #   vertical (columna, muro) -> no cruza -> la fuerte va en Iy
    #   viga (horizontal)        -> cruza    -> la de gravedad va en Iz
    #
    # Confundir esto es facil y no lo delata ningun otro test.
    def casilla(nombre):
        return 'Iy' if (nombre == 'columna'
                        or nombre.startswith('muro')) else 'Iz'

    peor_i, peor_n = 0.0, None
    for s in secs:
        teorico = s['espesor'] * s['largo'] ** 3 / 12.0
        d = abs(teorico - s[casilla(s['nombre'])])
        if d > peor_i:
            peor_i, peor_n = d, s['nombre']
    check("el 'largo' dibujado es el lado de la inercia fuerte",
          peor_i < 1e-9,
          f"peor {peor_i:.2e} m4 en '{peor_n}' -> el canto y el ancho "
          f"estan cambiados")
else:
    print("  (sin modelo_unity_edificio.json; corre python export_unity.py)")

# 'secciones' tiene que ser LISTA: JsonUtility no lee diccionarios.
check("'secciones' es lista (no diccionario)",
      isinstance(M['secciones'], list),
      f"es {type(M['secciones']).__name__}")

# ------------------------------------------------------------
print("\n3. La respuesta del servidor calza con las clases C#")
from servidor_opensees import construir_y_resolver          # noqa: E402

R = construir_y_resolver(M)
comparar('RespuestaServidor', R, "respuesta")
comparar('CasoResultado', R['casos'][0], "casos[0]")
comparar('DespNodo', R['casos'][0]['desplazamientos'][0], "desplazamientos[0]")
comparar('ReacNodo', R['casos'][0]['reacciones'][0], "reacciones[0]")
comparar('FuerzaElemento', R['casos'][0]['fuerzas_elementos'][0],
         "fuerzas_elementos[0]")

for clave in ('desplazamientos', 'reacciones', 'fuerzas_elementos', 'casos'):
    check(f"'{clave}' es lista", isinstance(R.get(clave, []), list))

# ------------------------------------------------------------
print("\n4. Round-trip estilo JsonUtility")
# JsonUtility SIEMPRE escribe todos los campos: los arrays que Unity no
# asigno salen como []. El servidor tiene que aceptarlo.
sim = json.loads(json.dumps(M))
for n in sim['nodos']:
    if not any(n.get('restricciones', [])):
        n['restricciones'] = []
for e in sim['elementos']:
    e['vecxz'] = []
sim['diafragmas'] = []
sim['brazos_rigidos'] = []

try:
    R2 = construir_y_resolver(sim)
    g = next(c for c in R2['casos'] if c['nombre'] == 'G')
    uz = next(d for d in g['desplazamientos'] if d['id'] == 5)['uz'] * 1000
    check("el servidor acepta el JSON con listas vacias", True,
          f"UZ(G) = {uz:.5f} mm")
    check("y da el mismo resultado", abs(uz + 0.06348) < 1e-4,
          f"referencia -0.06348 mm")
except Exception as e:
    check("el servidor acepta el JSON con listas vacias", False, str(e)[:70])

# ------------------------------------------------------------
print("\n5. Los 4 casos vienen resueltos y en equilibrio")
esperados = ["G", "Q", "EX", "EY"]
check("estan los 4 casos", [c['nombre'] for c in R['casos']] == esperados,
      f"{[c['nombre'] for c in R['casos']]}")
for c in R['casos']:
    s = {'fx': sum(r['fx'] for r in c['reacciones']),
         'fy': sum(r['fy'] for r in c['reacciones']),
         'fz': sum(r['fz'] for r in c['reacciones'])}
    esperado = {'G': ('fz', 179.0), 'Q': ('fz', 32.0),
                'EX': ('fx', -200.0), 'EY': ('fy', -200.0)}[c['nombre']]
    comp, val = esperado
    check(f"equilibrio {c['nombre']}", abs(s[comp] - val) < 1e-3,
          f"{comp} = {s[comp]:.4f} kN (esperado {val})")

# ------------------------------------------------------------
print("\n" + "=" * 68)
if fallos:
    print(f"  {len(fallos)} TEST(S) FALLARON:")
    for f in fallos:
        print(f"    - {f}")
    raise SystemExit(1)
print("  TODOS LOS TESTS PASARON")
print("  (esto NO garantiza que el C# compile; eso se prueba en Unity)")
print("=" * 68)
