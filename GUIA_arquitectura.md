# Proyecto: Análisis estructural de la universidad en Unity + OpenSees

## Arquitectura

```
   UNITY (C#)                      PYTHON (Flask + OpenSees)
   ┌──────────────┐                ┌──────────────────────┐
   │ Modelas la   │  POST /analizar│  Recibe JSON         │
   │ universidad  │───────────────>│  Construye modelo    │
   │ (nodos,vigas)│   (JSON)       │  Resuelve OpenSees   │
   │              │                │                      │
   │ Dibuja la    │<───────────────│  Devuelve JSON con   │
   │ deformada    │  (deformaciones)│  desplazamientos    │
   └──────────────┘                └──────────────────────┘
```

Unity = lo visual e interactivo. OpenSees = el cálculo. Se hablan por HTTP local.

## Archivos entregados

| Archivo | Dónde va | Qué hace |
|---|---|---|
| `servidor_opensees.py` | tu PC (Python) | recibe modelo, calcula, responde |
| `AnalizadorEstructural.cs` | proyecto Unity | envía modelo, recibe deformaciones |

## Pasos para armarlo

### 1. Levantar el servidor Python
```
pip install flask openseespy
python servidor_opensees.py
```
Queda en `http://localhost:5000`. Déjalo corriendo en una terminal.

### 2. En Unity
1. GameObject vacío → nombre "Analizador".
2. Arrastra `AnalizadorEstructural.cs` sobre él.
3. Crea un prefab de esfera (nodo) y arrástralo al campo `prefabNodo`.
4. Play. Unity envía el marco de ejemplo y recibe resultados (ver Console).

### 3. Modelar la universidad
Reemplaza `ConstruirMarcoEjemplo()` por tu geometría real. Puedes:
- Leer las coordenadas de los DXF que ya tienes (ejes reales del edificio).
- O modelar a mano en Unity y exportar nodos/elementos.

## PUNTO CRÍTICO: sistema de coordenadas

**Unity y OpenSees usan ejes distintos:**

| | Eje vertical | Convención |
|---|---|---|
| OpenSees | **Z** hacia arriba | ingeniería |
| Unity | **Y** hacia arriba | videojuego |

En el código ya está el swap: cuando dibujas en Unity usas
`new Vector3(nd.x, nd.z, nd.y)` — la Z de ingeniería va a la Y de Unity.
**No olvides este cambio** o el edificio saldrá acostado.

## PUNTO CRÍTICO: parseo del JSON en Unity

`JsonUtility` (el de Unity) **no maneja diccionarios** con claves numéricas
como `{"5": [...], "6": [...]}`. Para leer bien las deformaciones necesitas:

**Newtonsoft.Json** (gratis, oficial):
- Window → Package Manager → + → Add package by name →
  `com.unity.nuget.newtonsoft-json`

Con eso:
```csharp
var disp = JsonConvert.DeserializeObject<Dictionary<int, float[]>>(...);
Vector3 d = new Vector3(disp[id][0], disp[id][2], disp[id][1]); // swap Y/Z
nodoVisual.transform.position = posOriginal + d * factorEscala;
```

## El factor de escala (importante para que se VEA)

Los desplazamientos reales son **milimétricos** (-0.06 mm). Si mueves los
nodos esa cantidad, no se nota nada en pantalla. Por eso multiplicas por
`factorEscala` (ej. 500 o 1000) para **exagerar la deformada** — como hacen
todos los software estructurales con el "scale factor" de la deformada.
Es visual, no cambia el cálculo.

## Interacciones tipo videojuego que puedes agregar

| Interacción | Cómo |
|---|---|
| Arrastrar un nodo | OnMouseDrag → actualiza coord → EnviarModelo() |
| Slider de sección | cambia A/I en el JSON → reenvía |
| Botón "sismo X" | agrega cargas nodales laterales → reenvía |
| Color por esfuerzo | lee fuerzas_elementos → pinta viga (rojo=alto) |
| Animar deformada | Lerp entre posición original y deformada |

## Casos de carga

El servidor actual resuelve **un caso por llamada**. Para G, Q, EX:
- Envía 3 peticiones (una por caso), o
- Extiende el servidor para recibir varios patrones y devolver los 3.

## Validación

El servidor da los mismos números que validaste en SAP:
- Marco ejemplo, carga G → UZ techo = **-0.0635 mm** ✓

Así que tu tarea queda respaldada: Unity muestra, OpenSees calcula, y el
resultado coincide con SAP2000. Tres herramientas, mismo resultado.
