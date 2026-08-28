# Guía: usar el modelo en Unity (paso a paso, desde cero)

Hay **dos flujos**. El A no necesita Python corriendo; el B sí.

| | qué hace | necesita el servidor |
|---|---|---|
| **A — Visor** | dibuja la estructura y la deformada de G | ❌ |
| **B — Recálculo en vivo** | cualquier caso (G, Q, EX, EY), reanálisis | ✅ |
| **C — Editar** | mover nodos, crear/borrar barras, cambiar secciones | ✅ |

Empieza por el A. Si no ves el marco en pantalla, el B no te va a servir de nada.

---

# FLUJO A — Solo visualizar

## PASO 0 — Generar el JSON

En la carpeta del proyecto, con Python:

```bash
python generar_json_unity.py
```

Debe terminar diciendo:

```
  UZ nodo 5 = -0.06348 mm (referencia -0.06348 mm)
  -> OK, el benchmark sigue intacto.
  -> OK, el JSON es enviable al servidor tal cual.
```

Si dice **BENCHMARK ROTO**, para acá: algo del modelo está mal y no tiene
sentido llevarlo a Unity.

Esto crea/actualiza `modelo_unity.json`.

---

## PASO 1 — Abrir el proyecto

El proyecto Unity **ya está en el repositorio**, en la carpeta `unity/`.
No hay que crearlo ni copiar scripts a mano.

1. Abre **Unity Hub** → **Add** → **Add project from disk**
2. Elige la carpeta `unity/` del repositorio
3. Ábrelo

La primera vez tarda varios minutos: Unity reconstruye su caché
(`Library/`, unos 2 GB). Eso **no** está en el repo a propósito — son
40.000 archivos regenerables. Lo versionado son 73 archivos, 0,3 MB.

Al abrir, la escena `SampleScene` ya trae los objetos `Visor` y
`Analizador` armados y cableados.

---

## PASO 2 — Actualizar el JSON

Cada vez que cambies el modelo en Python:

```bash
python generar_json_unity.py
copy modelo_unity.json unity\Assets\StreamingAssets```

> Es el error más común: cambias el modelo, no copias el JSON, y Unity
> sigue mostrando el anterior.

---

## PASO 3 — Los scripts

Ya están en `unity/Assets/Scripts/`, y esa es **la única copia**:

```
ModeloEstructural.cs      clases de datos
VisorEstructura.cs        dibuja
AnalizadorEstructural.cs  habla con el servidor
CamaraOrbital.cs          navegar
EditorEstructura.cs       seleccionar y editar
```

> Antes estaban duplicados: una copia en la raíz del repo y otra dentro
> de Unity. Divergieron —la de Unity se quedó sin el arreglo del shader
> y sin el campo `auxiliar`— y nadie se enteró hasta que
> `test_contrato_unity.py` lo detectó. Ahora hay una sola.

---

## PASO 4 — Crear el objeto Visor

1. En **Hierarchy**, click derecho → **Create Empty**.
2. Renómbralo `Visor`.
3. Con `Visor` seleccionado, en el **Inspector** → **Add Component**.
4. Escribe `VisorEstructura` y selecciónalo.

En el Inspector aparecen sus campos: `nombreArchivo`, `radioNodo`,
colores, `mostrarDeformada`, `factorEscala` y las **capas visibles**
(nodos, columnas, vigas, muros).

---

## PASO 5 — Play

Presiona **▶**. Deberías ver:

- 4 esferas **verdes** abajo (apoyos)
- 4 esferas **azules** arriba (nodos de techo)
- barras **azules** (columnas) y **naranjas** (vigas)

En la Console debe decir:
`Modelo cargado: 8 nodos, 8 elementos, 4 casos.`

**Si no ves nada**, mira la Console:

| mensaje | causa |
|---|---|
| "No encontré el archivo" | falta el PASO 2, o el nombre no calza |
| "El JSON no trae nodos" | el JSON es de un formato viejo; regenéralo |
| nada, pantalla vacía | la cámara está lejos — ver PASO 6 |

---

## PASO 6 — Mover la cámara

En la ventana **Scene**:

- **Click derecho + arrastrar** = girar
- **Rueda** = zoom
- **Click rueda + arrastrar** = desplazar
- Selecciona `Visor` y presiona **F** para centrar en él

---

## PASO 7 — Ver la deformada

1. Selecciona `Visor`.
2. Marca **Mostrar Deformada** en el Inspector.

Se redibuja al instante (también en pleno Play). La estructura sale en
amarillo, exagerada ×300. Como es gravedad, las vigas se curvan hacia
abajo. Cambia **Factor Escala** para exagerar más o menos.

Esta deformada es la del caso **G**, precalculada y guardada en el JSON.
Para los otros casos necesitas el Flujo B.

---

# FLUJO B — Recálculo en vivo

## PASO 8 — Levantar el servidor

En una terminal aparte, **déjala abierta**:

```bash
python servidor_opensees.py
```

Debe quedar escuchando en `http://localhost:5000`, y decir
*"Solo accesible desde este equipo"*. Para conectar desde el celular
(fase de AR) hay que agregarle `--lan`, y solo en una red de confianza. Compruébalo en el
navegador: `http://localhost:5000/ping` debe responder
`{"estado":"vivo","motor":"OpenSees"}`.

---

## PASO 9 — Crear el objeto Analizador

1. En **Hierarchy**, click derecho → **Create Empty**.
2. Renómbralo `Analizador`.
3. **Add Component** → `AnalizadorEstructural`.
4. Conectarlo al Visor:

```
a. Click en  Analizador   en Hierarchy   <- debe quedar SELECCIONADO
b. El Inspector muestra "Analizador Estructural (Script)"
   con un campo  Visor  que dice "None (Visor Estructura)"
c. Arrastra  Visor  desde Hierarchy  hasta ese campo
```

> **El Inspector siempre muestra el objeto seleccionado.** El campo
> `visor` pertenece al *Analizador*, así que el Analizador tiene que
> estar seleccionado para poder llenarlo. Si arrastras con el `Visor`
> seleccionado, Unity marca "prohibido" — y con razón: ahí no hay
> ningún campo que lo acepte.
>
> Se arrastra **desde Hierarchy hacia el Inspector**, nunca el archivo
> `.cs` desde Project.

**Si el arrastre no funciona igual**, déjalo vacío: el script busca el
Visor solo con `FindObjectOfType`. Asignarlo a mano es más explícito,
pero no es obligatorio.

**Si aparece el cursor de "prohibido"** con el Analizador seleccionado,
entonces el objeto `Visor` no tiene el componente `VisorEstructura`
puesto — el campo solo acepta objetos que lo tengan.

---

## PASO 10 — Play

Al darle Play, el Analizador manda el modelo completo y recibe los 4
casos. En la Console:

```
Respuesta OK: 4 caso(s) [G, Q, EX, EY]
[G] Suma de reacciones: Fx=0.0000  Fy=0.0000  Fz=179.0000 kN
[G] Max desplazamiento = 0.06348 mm
```

**Ese `Fz=179.0000` es tu verificación de equilibrio.** Debe igualar la
carga aplicada. Si no calza, algo está mal en las cargas.

---

## PASO 11 — Cambiar de caso

Cambia el campo `casoActivo` a `EX`, `EY` o `Q`.

Desde código, sin volver a consultar al servidor:

```csharp
analizador.MostrarCaso("EX");
```

Los 4 casos ya están en memoria. **No se vuelve a pedir nada** — es
instantáneo. Esto es lo que necesitas para el *Load Combination
Explorer*.

---

# FLUJO C — Editar y recalcular

## PASO 12 — Cámara y editor

Son dos scripts más: `CamaraOrbital.cs` y `EditorEstructura.cs`.
Cópialos a `Assets/Scripts/` junto a los otros tres.

1. Selecciona la **Main Camera** de la escena → Add Component → `CamaraOrbital`.
2. GameObject vacío → `Editor` → Add Component → `EditorEstructura`.
3. Con **`Editor` seleccionado**, arrastra `Visor` y `Analizador` desde
   Hierarchy a sus campos. (También puedes dejarlos vacíos: se buscan
   solos.)

El panel es `OnGUI`, así que **no hay que armar ningún Canvas** ni
arrastrar prefabs. Aparece solo al darle Play.

---

## PASO 13 — Controles

| acción | control |
|---|---|
| Orbitar | click izquierdo + arrastrar |
| Paner | click derecho + arrastrar |
| Zoom | rueda |
| Encuadrar todo | **F** |
| Seleccionar | click sobre un nodo o barra |
| Mover en planta | arrastrar el nodo **ya seleccionado** |
| Mover en altura | **Shift** + arrastrar |
| Deseleccionar | **Esc** |
| Borrar | **Supr** |
| Recalcular | **Enter** |

Un click corto selecciona; si arrastras, orbita. Por eso hay que
seleccionar el nodo **primero** y arrastrarlo **después**.

---

## PASO 14 — El ciclo de trabajo

1. Mueve un nodo, cambia una sección o borra una barra.
2. **Enter** → se manda al servidor.
3. La deformada nueva aparece sola.

Al editar, la deformada anterior se borra: ya no corresponde a esa
geometría. El panel muestra `(modificado)` hasta que recalculas.

**Guardar JSON** escribe el modelo editado en `persistentDataPath`
(la ruta completa sale en la Console). Ese archivo se puede copiar de
vuelta a `StreamingAssets/` para que quede como modelo de partida.

---

## Borrar cosas: por qué no basta con quitarlas

Si borras una barra y dejas su carga distribuida, **OpenSees no falla**:
emite un warning por consola y descarta la carga. El análisis "funciona"
con menos carga de la que crees, y el equilibrio **cierra igual** porque
la carga descartada nunca entró.

Por eso al borrar, el editor limpia también:

- las cargas distribuidas de la barra,
- las cargas nodales del nodo,
- las barras que llegaban a ese nodo,
- las referencias en diafragmas y brazos rígidos.

Y el servidor además lo valida y lo rechaza con un mensaje explícito, por
si el JSON llega mal armado desde otro lado.

---

# Errores frecuentes

| síntoma | causa |
|---|---|
| **Todo se ve MAGENTA/rosado** | no se encontró el shader. Pasa en URP (plantilla 3D de Unity 6, se reconoce por el `Global Volume` en la escena). `VisorEstructura` ya elige el shader según el pipeline; si lo ves rosado, tu copia del script está desactualizada. |
| **El edificio se ve acostado** | el swap de ejes. OpenSees usa Z vertical, Unity usa Y. Está centralizado en `Ejes.AUnity()` — un solo lugar que revisar. |
| **La deformada sale plana** | un campo del C# no calza con el JSON. `JsonUtility` **no avisa**: deja el campo en 0. Corre `python test_contrato_unity.py`. |
| **"No pude conectar con el servidor"** | falta el PASO 8, o cerraste la terminal. |
| **"El servidor rechazó el modelo (HTTP 400)"** | el mensaje trae el motivo real (sección inexistente, nodo que no existe, `vecxz` paralelo...). Léelo, es explícito. |
| **Unity muestra datos viejos** | no copiaste el JSON de nuevo a StreamingAssets tras regenerarlo. |
| **La clase no aparece en Add Component** | hay un error de compilación en ALGÚN script (bloquea todos), o el nombre del archivo no coincide con el de la clase. |
| **El click no selecciona nada** | los objetos necesitan Collider. `CreatePrimitive` los trae; si cambiaste el dibujo, revísalo. |
| **Arrastrar el nodo orbita la cámara** | hay que seleccionarlo primero con un click corto, y arrastrarlo después. |
| **No deja arrastrar un objeto a un campo** | el Inspector muestra el objeto SELECCIONADO: para llenar un campo del Analizador, selecciona el Analizador. Y el objeto arrastrado debe tener el componente de ese tipo. |
| **Warnings `[modelo] Elemento N dice tipo=...`** | la etiqueta no calza con la geometría. El modelo se resolvió igual (manda la geometría), pero delata datos mal importados del DXF. |

---

# El punto de los ejes

- **OpenSees**: Z es vertical (convención de ingeniería).
- **Unity**: Y es vertical (convención de videojuego).
- **Conversión**: `Unity(x, z_opensees, y_opensees)`.

Está en un solo lugar, `Ejes.AUnity()` en `ModeloEstructural.cs`. Si el
edificio se ve acostado, ahí es.

---

# Resumen del flujo

```
python generar_json_unity.py          # 1. genera el modelo
copiar modelo_unity.json -> StreamingAssets/   # 2. OJO: cada vez
python servidor_opensees.py           # 3. dejar corriendo (solo flujo B)
Play en Unity                         # 4.
```

Y cada vez que toques el modelo en Python: **repite los pasos 1 y 2**.
