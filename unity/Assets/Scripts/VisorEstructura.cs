/*
================================================================
  VisorEstructura.cs
================================================================
  DIBUJA el modelo estructural en 3D. Nada mas.

  No habla con el servidor ni define clases de datos: usa las de
  ModeloEstructural.cs. Quien calcula es AnalizadorEstructural.cs,
  que le pasa los desplazamientos ya resueltos.

  Esta separacion es la misma regla del CLAUDE.md: OpenSees calcula,
  Unity muestra.

  ----------------------------------------------------------------
  COMO USARLO
  1. Copia modelo_unity.json a Assets/StreamingAssets/
     (generalo con: python generar_json_unity.py)
  2. Crea un GameObject vacio, llamalo "Visor".
  3. Arrastra este script encima.
  4. Play. Deberias ver el marco en 3D.

  Para ver la deformada de otros casos (Q, EX, EY) necesitas el
  servidor corriendo y el script AnalizadorEstructural.
  ----------------------------------------------------------------
*/

using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

public class VisorEstructura : MonoBehaviour
{
    [Header("Archivo")]
    public string nombreArchivo = "modelo_unity.json";

    [Header("Apariencia")]
    public float radioNodo = 0.15f;
    [Tooltip("Nodos intermedios de las vigas. Se dibujan mas chicos "
           + "para que no compitan con los nudos reales del marco.")]
    public float radioNodoAuxiliar = 0.05f;
    public float grosorBarra = 0.05f;
    public Color colorColumna = new Color(0.36f, 0.62f, 1f);    // azul
    public Color colorViga = new Color(0.88f, 0.48f, 0.37f);    // naranjo
    public Color colorMuro = new Color(0.65f, 0.65f, 0.70f);    // gris
    public Color colorApoyo = new Color(0.18f, 0.60f, 0.37f);   // verde
    public Color colorNodoAuxiliar = new Color(0.55f, 0.58f, 0.62f); // gris
    public Color colorTributaria = new Color(0.95f, 0.75f, 0.20f);   // ambar
    public Color colorDeformada = Color.yellow;

    [Header("Muros")]
    [Tooltip("Dibuja cada muro como un prisma con su largo y espesor "
           + "reales, en vez de una barra en su eje. Las dimensiones "
           + "vienen del JSON (seccion.largo / seccion.espesor).")]
    public bool murosSolidos = true;
    [Tooltip("Espesor minimo de dibujo, en metros. Los muros de 15 cm "
           + "quedan invisibles de lejos si se dibujan a escala.")]
    public float espesorMinimoMuro = 0.10f;

    [Header("Apoyos")]
    [Tooltip("Dibuja los nodos apoyados como cubos, al estilo SAP2000, "
           + "en vez de esferas.")]
    public bool apoyosComoCubos = true;
    [Tooltip("Lado del cubo de apoyo, en metros.")]
    public float ladoCuboApoyo = 0.45f;

    [Header("Deformada")]
    public bool mostrarDeformada = false;
    [Tooltip("Amplifica el desplazamiento. Los mm reales no se verian.")]
    public float factorEscala = 300f;

    [Header("Capas visibles")]
    public bool verNodos = true;
    [Tooltip("Los nodos intermedios de las vigas. Apagalos para ver "
           + "solo los nudos del marco.")]
    public bool verNodosAuxiliares = true;
    public bool verColumnas = true;
    public bool verVigas = true;
    public bool verMuros = true;

    // --- Estado ---
    /// El modelo cargado. AnalizadorEstructural lo lee para mandarlo
    /// al servidor: es el MISMO objeto, no una copia.
    public ModeloEstructural Modelo { get; private set; }

    // Desplazamientos actualmente dibujados, indexados por id de nodo.
    private Dictionary<int, DespNodo> deformadaActual = new Dictionary<int, DespNodo>();

    private List<GameObject> objetosCreados = new List<GameObject>();

    // Objetos de la escena indexados por el id de OpenSees. Es lo que
    // permite seleccionar y resaltar desde EditorEstructura.
    private Dictionary<int, GameObject> objetoDeNodo = new Dictionary<int, GameObject>();
    private Dictionary<int, GameObject> objetoDeElemento = new Dictionary<int, GameObject>();

    public GameObject ObjetoDeNodo(int id)
    {
        GameObject g;
        return objetoDeNodo.TryGetValue(id, out g) ? g : null;
    }

    public GameObject ObjetoDeElemento(int id)
    {
        GameObject g;
        return objetoDeElemento.TryGetValue(id, out g) ? g : null;
    }
    private Dictionary<Color, Material> materiales = new Dictionary<Color, Material>();
    private bool necesitaRedibujar = false;

    // ============================================================
    void Start()
    {
        if (CargarJSON())
        {
            UsarDeformadaPrecalculada();
            Redibujar();
        }
    }

    // ============================================================
    // CARGAR EL JSON
    // ============================================================
    public bool CargarJSON()
    {
        string ruta = Path.Combine(Application.streamingAssetsPath, nombreArchivo);

        if (!File.Exists(ruta))
        {
            Debug.LogError("No encontre el archivo: " + ruta);
            Debug.LogError("Generalo con 'python generar_json_unity.py' y "
                           + "copialo a Assets/StreamingAssets/");
            return false;
        }

        try
        {
            Modelo = JsonUtility.FromJson<ModeloEstructural>(File.ReadAllText(ruta));
        }
        catch (System.Exception ex)
        {
            Debug.LogError("El JSON no se pudo interpretar: " + ex.Message);
            return false;
        }

        if (Modelo == null || Modelo.nodos == null || Modelo.nodos.Count == 0)
        {
            Debug.LogError("El JSON no trae nodos. Revisa que sea el formato "
                           + "que genera generar_json_unity.py");
            return false;
        }

        Modelo.InvalidarIndice();
        Debug.Log($"Modelo cargado: {Modelo.nodos.Count} nodos, "
                  + $"{Modelo.elementos.Count} elementos, "
                  + $"{(Modelo.casos_de_carga != null ? Modelo.casos_de_carga.Count : 0)} casos.");
        return true;
    }

    // ============================================================
    // DEFORMADA
    // ============================================================

    /// Usa los ux/uy/uz que vienen en el JSON (caso G precalculado).
    /// Permite ver una deformada sin tener el servidor corriendo.
    public void UsarDeformadaPrecalculada()
    {
        deformadaActual.Clear();
        foreach (Nodo n in Modelo.nodos)
        {
            deformadaActual[n.id] = new DespNodo {
                id = n.id, ux = n.ux, uy = n.uy, uz = n.uz
            };
        }
    }

    /// Borra la deformada dibujada. Se llama al editar el modelo: los
    /// desplazamientos anteriores ya no corresponden a esta geometria.
    public void LimpiarDeformada()
    {
        deformadaActual.Clear();
        mostrarDeformada = false;
    }

    /// Recibe los desplazamientos resueltos por el servidor.
    /// Lo llama AnalizadorEstructural cuando llega una respuesta.
    public void AplicarDeformada(List<DespNodo> desplazamientos)
    {
        if (desplazamientos == null) return;
        deformadaActual.Clear();
        foreach (DespNodo d in desplazamientos) deformadaActual[d.id] = d;
        Redibujar();
    }

    /// Posicion de un nodo, deformada o no segun el toggle.
    Vector3 PosicionDe(Nodo n)
    {
        if (!mostrarDeformada) return Ejes.PosicionDe(n);

        DespNodo d;
        if (!deformadaActual.TryGetValue(n.id, out d)) return Ejes.PosicionDe(n);
        return Ejes.PosicionDeformada(n, d.ux, d.uy, d.uz, factorEscala);
    }

    // ============================================================
    // DIBUJO
    // ============================================================
    public void Redibujar()
    {
        if (Modelo == null) return;

        foreach (var go in objetosCreados) if (go != null) Destroy(go);
        objetosCreados.Clear();
        objetoDeNodo.Clear();
        objetoDeElemento.Clear();
        LimpiarTributaria();

        // --- Nodos ---
        if (verNodos)
        {
            foreach (Nodo n in Modelo.nodos)
            {
                if (n.auxiliar && !verNodosAuxiliares) continue;

                bool apoyado = n.fijo || TieneAlgunaRestriccion(n);

                // Los apoyos van como CUBO (convencion SAP2000) y el
                // resto como esfera. Los auxiliares nunca: son nodos de
                // control, no apoyos de verdad, aunque el maestro de
                // diafragma lleve restringidos uz, rx y ry.
                bool cubo = apoyosComoCubos && apoyado && !n.auxiliar;

                GameObject go = GameObject.CreatePrimitive(
                    cubo ? PrimitiveType.Cube : PrimitiveType.Sphere);
                go.name = (n.auxiliar ? "NodoAux_" : "Nodo_") + n.id;
                go.transform.position = PosicionDe(n);

                if (cubo)
                {
                    go.transform.localScale = Vector3.one * ladoCuboApoyo;
                }
                else
                {
                    // Los auxiliares van mas chicos y en gris: estan
                    // para que se vea la curva de la viga, no para
                    // leerlos.
                    float r = n.auxiliar ? radioNodoAuxiliar : radioNodo;
                    go.transform.localScale = Vector3.one * r * 2f;
                }

                Pintar(go, n.auxiliar ? colorNodoAuxiliar
                         : (apoyado ? colorApoyo : colorColumna));

                go.AddComponent<DatoNodo>().idNodo = n.id;
                objetoDeNodo[n.id] = go;
                objetosCreados.Add(go);
            }
        }

        // --- Elementos ---
        if (Modelo.elementos == null) return;
        foreach (Elemento e in Modelo.elementos)
        {
            if (!CapaVisible(e.tipo)) continue;

            Nodo a = Modelo.NodoPorId(e.n1);
            Nodo b = Modelo.NodoPorId(e.n2);
            if (a == null || b == null)
            {
                Debug.LogError($"Elemento {e.id} referencia un nodo inexistente "
                               + $"(n1={e.n1}, n2={e.n2}). Se omite.");
                continue;
            }

            GameObject barra = (e.tipo == "muro" && murosSolidos)
                ? CrearPrismaMuro(e, PosicionDe(a), PosicionDe(b))
                : CrearCilindro(PosicionDe(a), PosicionDe(b), grosorBarra);

            barra.name = "Elem_" + e.id + "_" + e.tipo;
            Pintar(barra, mostrarDeformada ? colorDeformada : ColorDe(e.tipo));
            barra.AddComponent<DatoElemento>().idElemento = e.id;
            objetoDeElemento[e.id] = barra;
            objetosCreados.Add(barra);
        }
    }

    bool TieneAlgunaRestriccion(Nodo n)
    {
        if (n.restricciones == null) return false;
        foreach (int r in n.restricciones) if (r != 0) return true;
        return false;
    }

    bool CapaVisible(string tipo)
    {
        if (tipo == "columna") return verColumnas;
        if (tipo == "muro") return verMuros;
        return verVigas;   // viga_x, viga_y y cualquier otra
    }

    Color ColorDe(string tipo)
    {
        if (tipo == "columna") return colorColumna;
        if (tipo == "muro") return colorMuro;
        return colorViga;
    }

    // ------------------------------------------------------------
    // El muro se MODELA como columna ancha (una barra en su eje) pero
    // se DIBUJA como el prisma que es. Dibujarlo como linea es lo que
    // hace creer que tiene espesor cero.
    //
    // Las tres dimensiones salen del JSON, no se deducen aca:
    //   largo    -> seccion.largo    (a lo largo del muro)
    //   espesor  -> seccion.espesor
    //   altura   -> distancia entre los dos nodos del elemento
    //
    // La direccion del largo la da el vecxz del elemento, que es el
    // mismo vector con que el servidor orienta el eje fuerte de la
    // seccion. Asi el dibujo y el calculo no pueden discrepar.
    //
    // OJO: el prisma se dibuja centrado en el EJE del muro, que es
    // donde esta la barra. Las vigas que en el edificio real llegan a
    // la CARA se ven llegando al eje: es la limitacion de no tener
    // brazos rigidos, y ahora se ve.
    // ------------------------------------------------------------
    GameObject CrearPrismaMuro(Elemento e, Vector3 desde, Vector3 hasta)
    {
        Seccion s = Modelo.SeccionPorNombre(e.seccion);

        // Sin dimensiones no se puede dibujar el prisma. Pasa con un
        // JSON viejo, anterior a que se exportaran largo y espesor.
        if (s == null || s.largo <= 0f)
        {
            Debug.LogWarning($"El muro {e.id} usa la seccion '{e.seccion}', "
                + "que no trae 'largo'. Se dibuja como barra. "
                + "Vuelve a exportar con: python export_unity.py");
            return CrearCilindro(desde, hasta, grosorBarra);
        }

        GameObject caja = GameObject.CreatePrimitive(PrimitiveType.Cube);
        caja.transform.position = (desde + hasta) / 2f;

        Vector3 eje = hasta - desde;
        float altura = eje.magnitude;
        if (altura < 1e-6f) altura = 0.01f;

        // vecxz esta en coordenadas OpenSees; hay que pasarlo a Unity
        // por el mismo camino que todo lo demas.
        Vector3 largoDir = (e.vecxz != null && e.vecxz.Length >= 3)
            ? Ejes.AUnity(e.vecxz[0], e.vecxz[1], e.vecxz[2])
            : Vector3.right;
        if (largoDir.sqrMagnitude < 1e-12f) largoDir = Vector3.right;
        largoDir.Normalize();

        // El cubo mide 1 en cada lado: escala = dimension real.
        // Y local = altura del muro, X local = su largo, Z = espesor.
        float esp = Mathf.Max(s.espesor, espesorMinimoMuro);
        caja.transform.rotation = Quaternion.LookRotation(
            Vector3.Cross(largoDir, eje.normalized), eje.normalized);
        caja.transform.localScale = new Vector3(s.largo, altura, esp);
        return caja;
    }

    // Unity no tiene "linea gruesa 3D": se usa un cilindro estirado.
    GameObject CrearCilindro(Vector3 desde, Vector3 hasta, float grosor)
    {
        GameObject cil = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        cil.transform.position = (desde + hasta) / 2f;

        Vector3 direccion = hasta - desde;
        float largo = direccion.magnitude;

        // El cilindro de Unity mide 2 de alto y apunta en Y.
        cil.transform.localScale = new Vector3(grosor, largo / 2f, grosor);
        if (largo > 1e-6f) cil.transform.up = direccion.normalized;
        return cil;
    }

    // Cachea materiales: crear uno por objeto deja cientos huerfanos
    // que Unity no libera. Con el edificio completo es una fuga real.
    void Pintar(GameObject go, Color color)
    {
        Material mat;
        if (!materiales.TryGetValue(color, out mat))
        {
            mat = new Material(ShaderDelProyecto());
            mat.color = color;
            // URP/HDRP usan _BaseColor. Material.color suele mapearlo
            // solo, pero asignarlo explicito no cuesta nada y evita
            // depender de la version de Unity.
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            materiales[color] = mat;
        }
        go.GetComponent<Renderer>().sharedMaterial = mat;
    }

    // ============================================================
    // El shader depende del RENDER PIPELINE del proyecto.
    // "Standard" solo existe en el Built-in. En URP (que es lo que usa
    // la plantilla 3D de Unity 6) Shader.Find("Standard") devuelve
    // null, y un material sin shader se dibuja MAGENTA.
    // Si toda la estructura se ve rosada, es esto.
    // ============================================================
    static Shader shaderCache;

    static Shader ShaderDelProyecto()
    {
        if (shaderCache != null) return shaderCache;

        // currentRenderPipeline != null significa URP o HDRP.
        if (GraphicsSettings.currentRenderPipeline != null)
        {
            shaderCache = Shader.Find("Universal Render Pipeline/Lit");
            if (shaderCache == null) shaderCache = Shader.Find("HDRP/Lit");
        }
        if (shaderCache == null) shaderCache = Shader.Find("Standard");
        if (shaderCache == null) shaderCache = Shader.Find("Unlit/Color");

        if (shaderCache == null)
            Debug.LogError("No encontre ningun shader utilizable. Todo se "
                           + "vera magenta.");
        return shaderCache;
    }

    // ============================================================
    // AREAS TRIBUTARIAS
    // ------------------------------------------------------------
    // Dibuja el contorno del poligono de losa que descarga en una viga.
    // Solo se dibuja el de la barra SELECCIONADA: hay 1120 poligonos en
    // el edificio y pintarlos todos serian miles de objetos.
    // ============================================================
    private List<GameObject> objetosTributaria = new List<GameObject>();

    public void LimpiarTributaria()
    {
        foreach (var go in objetosTributaria) if (go != null) Destroy(go);
        objetosTributaria.Clear();
    }

    /// Dibuja el/los poligono(s) tributario(s) de una viga. Una viga
    /// interior borda dos panos, asi que puede tener dos poligonos.
    /// Devuelve el area total dibujada.
    public float DibujarTributaria(int idElemento)
    {
        LimpiarTributaria();
        if (Modelo == null || Modelo.areas_tributarias == null) return 0f;

        float total = 0f;
        foreach (AreaTributaria a in Modelo.areas_tributarias)
        {
            if (a.elemento != idElemento) continue;
            if (a.vx == null || a.vy == null || a.vx.Length < 3) continue;
            if (a.vx.Length != a.vy.Length) continue;

            total += a.area;
            int n = a.vx.Length;
            for (int i = 0; i < n; i++)
            {
                int j = (i + 1) % n;
                // Un pelo por encima de la losa, para que no se pelee
                // con las barras por el mismo pixel.
                Vector3 p = Ejes.AUnity(a.vx[i], a.vy[i], a.z + 0.02f);
                Vector3 q = Ejes.AUnity(a.vx[j], a.vy[j], a.z + 0.02f);
                GameObject l = CrearCilindro(p, q, grosorBarra * 0.6f);
                l.name = $"Trib_{idElemento}_{i}";
                Pintar(l, colorTributaria);
                // Sin collider: no debe robarle el click a las barras.
                Collider c = l.GetComponent<Collider>();
                if (c != null) Destroy(c);
                objetosTributaria.Add(l);
            }
        }
        return total;
    }

    // ============================================================
    // Permite prender/apagar toggles desde el Inspector en Play.
    // OJO: NO se puede llamar Destroy() desde OnValidate (Unity lo
    // prohibe). Solo levantamos una bandera; se redibuja en Update.
    // ============================================================
    void OnValidate()
    {
        if (Application.isPlaying && Modelo != null) necesitaRedibujar = true;
    }

    void Update()
    {
        if (necesitaRedibujar) { necesitaRedibujar = false; Redibujar(); }
    }
}
