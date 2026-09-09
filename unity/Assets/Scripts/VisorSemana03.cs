/*
  VisorSemana03.cs
  ----------------
  Dibuja lo que agrega la Semana 3 sobre el modelo ya visible:

    - el sismo: una flecha por nivel, en el nodo maestro del diafragma,
      de largo proporcional a la fuerza lateral de ese piso;
    - la enfierradura: la jaula de la columna mas cargada, con sus 16
      barras, el estribo exterior y el estribo en rombo.

  NO calcula nada. Los numeros vienen resueltos desde Python en
  StreamingAssets/semana03.json, que produce semana03/exportar_unity.py.
  Esa es la regla del repositorio: OpenSees calcula, Unity muestra.

  Como usarlo:
    1. python semana03/exportar_unity.py
    2. Crea un GameObject vacio y llamalo "VisorSemana03".
    3. Arrastrale este script.
    4. Play. Los toggles del inspector prenden y apagan cada capa.
*/

using System.Collections.Generic;
using System.IO;
using UnityEngine;

// --- Contrato del JSON (los nombres calzan con exportar_unity.py) ---

[System.Serializable]
public class NivelSismo
{
    public int nodo_maestro;
    public float x;
    public float y;
    public float z;
    public float peso_kN;
    public float fraccion;
    public float F_kN;
}

[System.Serializable]
public class BloqueSismo
{
    public string patron;
    public float Cs;
    public float corte_basal_kN;
    public float fuerza_maxima_kN;
    public List<NivelSismo> niveles;
}

[System.Serializable]
public class PuntoSeccion
{
    public float y;
    public float z;
}

[System.Serializable]
public class PuntoXYZ
{
    public float x;
    public float y;
    public float z;
}

[System.Serializable]
public class BloqueArmadura
{
    public int columna_id;
    public float axial_G_kN;
    public float b;
    public float h;
    public float diametro_barra;
    public float diametro_estribo;
    public float espaciamiento_estribo;
    public float cuantia_pct;
    public string procedencia;
    public List<PuntoSeccion> barras;
    public List<PuntoSeccion> estribo_exterior;
    public List<PuntoSeccion> estribo_rombo;
    public PuntoXYZ nodo_inferior;
    public PuntoXYZ nodo_superior;
    public List<ColumnaRef> columnas;
}

[System.Serializable]
public class FlechaCarga
{
    public float x, y, z;         // punto de aplicacion (OpenSees)
    public float fx, fy, fz;      // vector fuerza (kN)
    public float kN;              // magnitud
}

[System.Serializable]
public class CasoCarga
{
    public string caso;
    public string descripcion;
    public float maxima_kN;
    public float total_kN;
    public List<FlechaCarga> flechas;
}

[System.Serializable]
public class ColumnaRef
{
    public int id, n1, n2;
    public float axial_G_kN;
}

[System.Serializable]
public class CasoDeformada
{
    public string caso;
    public float max_horizontal_mm;
    public List<DespNodo> desplazamientos;
}

[System.Serializable]
public class CajaEdificio
{
    public float x_min, x_max, y_min, y_max, z_min, z_max;
}

[System.Serializable]
public class AnexoSemana03
{
    public CajaEdificio caja;
    public BloqueSismo sismo;
    public BloqueArmadura armadura;
    public List<CasoDeformada> deformadas;
    public List<CasoCarga> cargas;
}


public class VisorSemana03 : MonoBehaviour
{
    [Header("Archivo")]
    public string nombreArchivo = "semana03.json";

    [Header("Capas")]
    public bool mostrarCargas = true;
    public bool mostrarArmadura = true;

    [Tooltip("Enfierra las 82 columnas, no solo la del detalle. Los " +
             "estribos solo se dibujan en la del detalle: en todas serian " +
             "26 000 objetos.")]
    public bool enfierrarTodas = false;

    [Header("Deformada")]
    [Tooltip("Le pasa al VisorEstructura la deformada del caso sismico. " +
             "El visor la escala con su propio factorEscala (300 por " +
             "defecto): EX son 6.9 mm reales, EY son 33.5 mm.")]
    public bool aplicarDeformada = true;

    [Tooltip("EX o EY.")]
    public string casoDeformada = "EX";

    [Header("Cargas")]
    [Tooltip("G, Q, EX, EY o COMBINACION. La combinacion usa los lambda " +
             "de parametros.py y viene ya sumada desde Python.")]
    public string casoCarga = "EX";

    [Tooltip("Largo en metros de la flecha mas grande del caso.")]
    public float largoFlechaMaxima = 6f;

    [Tooltip("Bajo este porcentaje de la fuerza mayor la flecha no se " +
             "dibuja. Evita 800 palitos invisibles en G o Q.")]
    [Range(0f, 50f)] public float umbralPorcentaje = 8f;

    public float grosorFlecha = 0.18f;
    public Color colorSismo = new Color(1f, 0.35f, 0.1f);

    [Header("Armadura")]
    [Tooltip("Dibuja la jaula dentro de la columna real. A escala del " +
             "edificio (50 x 29 m) queda del porte de un punto.")]
    public bool jaulaEnSitio = true;

    [Tooltip("Copia ampliada al costado del edificio, como lamina de " +
             "detalle. Es la que se ve de verdad en una demo.")]
    public bool jaulaDetalle = true;

    [Tooltip("Cuantas veces se amplia la jaula de la vista de detalle.")]
    public float escalaDetalle = 6f;

    [Tooltip("Las barras reales son de 16 mm: a escala del edificio no " +
             "se ven. Este factor las engorda solo para poder mirarlas.")]
    public float exageracionBarra = 6f;
    public Color colorBarra = new Color(0.1f, 0.1f, 0.12f);
    public Color colorEstribo = new Color(0.7f, 0.1f, 0.1f);

    public AnexoSemana03 Anexo { get; private set; }

    private readonly List<GameObject> creados = new List<GameObject>();
    private readonly Dictionary<Color, Material> materiales =
        new Dictionary<Color, Material>();

    void Start()
    {
        if (Cargar()) StartCoroutine(DibujarCuandoElVisorEsteListo());
    }

    /// Se espera un frame: VisorEstructura carga su modelo en Start() y
    /// el orden entre dos Start() no esta garantizado.
    System.Collections.IEnumerator DibujarCuandoElVisorEsteListo()
    {
        yield return null;
        Dibujar();
        if (aplicarDeformada) PasarDeformadaAlVisor();
    }

    /// El visor ya sabe dibujar deformadas; aca solo se le entrega la
    /// del caso sismico que corresponda.
    public void PasarDeformadaAlVisor()
    {
        if (Anexo == null || Anexo.deformadas == null) return;

        VisorEstructura visor = FindFirstObjectByType<VisorEstructura>();
        if (visor == null)
        {
            Debug.LogWarning("VisorSemana03: no hay VisorEstructura en la "
                             + "escena, asi que no hay deformada que aplicar.");
            return;
        }

        CasoDeformada c = Anexo.deformadas.Find(d => d.caso == casoDeformada);
        if (c == null)
        {
            Debug.LogWarning($"VisorSemana03: no encontre el caso "
                             + $"'{casoDeformada}'. Usa EX o EY.");
            return;
        }

        visor.mostrarDeformada = true;
        visor.AplicarDeformada(c.desplazamientos);
        Debug.Log($"VisorSemana03: deformada {c.caso} aplicada "
                  + $"({c.desplazamientos.Count} nodos, maximo real "
                  + $"{c.max_horizontal_mm:0.00} mm; el visor la amplifica "
                  + $"x{visor.factorEscala:0}).");
    }

    bool Cargar()
    {
        string ruta = Path.Combine(Application.streamingAssetsPath, nombreArchivo);
        if (!File.Exists(ruta))
        {
            Debug.LogError("VisorSemana03: no encontre " + ruta
                           + ". Corre primero: python semana03/exportar_unity.py");
            return false;
        }
        Anexo = JsonUtility.FromJson<AnexoSemana03>(File.ReadAllText(ruta));
        if (Anexo == null)
        {
            Debug.LogError("VisorSemana03: no pude leer " + nombreArchivo);
            return false;
        }
        return true;
    }

    /// Se puede llamar desde el inspector o desde otro script tras
    /// cambiar los toggles.
    public void Redibujar()
    {
        Limpiar();
        if (Anexo != null || Cargar()) Dibujar();
    }

    void Limpiar()
    {
        foreach (GameObject g in creados)
            if (g != null) DestroyImmediate(g);
        creados.Clear();
    }

    void Dibujar()
    {
        if (mostrarCargas && Anexo.cargas != null) DibujarCargas();
        if (mostrarArmadura && Anexo.armadura != null)
        {
            if (jaulaEnSitio) DibujarArmadura(Anexo.armadura, 1f, Vector3.zero);
            if (jaulaDetalle)
                DibujarArmadura(Anexo.armadura, escalaDetalle, OffsetDetalle());
            if (enfierrarTodas) DibujarBarrasDeTodas();
        }
    }

    // ----------------------------------------------------------------
    // SISMO
    // ----------------------------------------------------------------
    void DibujarCargas()
    {
        CasoCarga c = Anexo.cargas.Find(x => x.caso == casoCarga);
        if (c == null)
        {
            Debug.LogWarning($"VisorSemana03: no existe el caso de carga "
                             + $"'{casoCarga}'. Usa G, Q, EX, EY o COMBINACION.");
            return;
        }
        if (c.flechas == null || c.maxima_kN <= 0f) return;

        // G y Q traen ~500 flechas, casi todas chicas. Dibujarlas todas
        // llena la pantalla de palitos y no se entiende nada.
        float umbral = c.maxima_kN * umbralPorcentaje / 100f;

        Transform padre = new GameObject("Cargas_" + c.caso).transform;
        padre.SetParent(transform, false);
        creados.Add(padre.gameObject);

        int dibujadas = 0;
        foreach (FlechaCarga f in c.flechas)
        {
            if (f.kN < umbral) continue;

            Vector3 punta = Ejes.AUnity(f.x, f.y, f.z);
            // AUnity es lineal, asi que sirve igual para el vector fuerza.
            Vector3 dir = Ejes.AUnity(f.fx, f.fy, f.fz);
            if (dir.sqrMagnitude < 1e-12f) continue;
            dir.Normalize();

            float largo = largoFlechaMaxima * f.kN / c.maxima_kN;
            Vector3 cola = punta - dir * largo;
            Vector3 cuello = punta - dir * largo * 0.32f;

            GameObject cuerpo = Cilindro(cola, cuello, grosorFlecha);
            cuerpo.name = $"{c.caso}_{f.kN:0.#}kN";
            cuerpo.transform.SetParent(padre, true);
            Pintar(cuerpo, colorSismo);
            creados.Add(cuerpo);

            GameObject cabeza = Cono(cuello, punta, grosorFlecha * 2.4f);
            cabeza.name = cuerpo.name + "_punta";
            cabeza.transform.SetParent(padre, true);
            Pintar(cabeza, colorSismo);
            creados.Add(cabeza);
            dibujadas++;
        }

        Debug.Log($"VisorSemana03: caso {c.caso} ({c.descripcion}) - "
                  + $"{dibujadas} de {c.flechas.Count} flechas sobre el "
                  + $"{umbralPorcentaje:0}% de {c.maxima_kN:0.0} kN. "
                  + $"Total del caso: {c.total_kN:0.0} kN.");
    }

    /// Barras de las 82 columnas, siguiendo la deformada si esta puesta.
    /// Los estribos NO se dibujan aca: serian 26 000 objetos.
    void DibujarBarrasDeTodas()
    {
        BloqueArmadura a = Anexo.armadura;
        if (a.columnas == null || a.columnas.Count == 0) return;

        VisorEstructura visor = FindFirstObjectByType<VisorEstructura>();
        if (visor == null || visor.Modelo == null)
        {
            Debug.LogWarning("VisorSemana03: sin VisorEstructura no se donde "
                             + "estan las columnas; no puedo enfierrarlas.");
            return;
        }

        Dictionary<int, DespNodo> desp = null;
        float escalaDef = visor.factorEscala;
        if (aplicarDeformada && Anexo.deformadas != null)
        {
            CasoDeformada cd = Anexo.deformadas.Find(d => d.caso == casoDeformada);
            if (cd != null)
            {
                desp = new Dictionary<int, DespNodo>();
                foreach (DespNodo d in cd.desplazamientos) desp[d.id] = d;
            }
        }

        Transform padre = new GameObject("Armadura_todas").transform;
        padre.SetParent(transform, false);
        creados.Add(padre.gameObject);

        float grosor = a.diametro_barra * exageracionBarra;
        int hechas = 0;
        foreach (ColumnaRef col in a.columnas)
        {
            Nodo na = visor.Modelo.NodoPorId(col.n1);
            Nodo nb = visor.Modelo.NodoPorId(col.n2);
            if (na == null || nb == null) continue;

            Vector3 pa = PosicionQuizaDeformada(na, desp, escalaDef);
            Vector3 pb = PosicionQuizaDeformada(nb, desp, escalaDef);

            foreach (PuntoSeccion p in a.barras)
            {
                Vector3 off = new Vector3(p.y, 0f, p.z);
                GameObject barra = Cilindro(pa + off, pb + off, grosor);
                barra.name = $"col{col.id}_barra";
                barra.transform.SetParent(padre, true);
                Pintar(barra, colorBarra);
                creados.Add(barra);
            }
            hechas++;
        }

        Debug.Log($"VisorSemana03: {hechas} columnas enfierradas "
                  + $"({hechas * a.barras.Count} barras"
                  + (desp != null ? $", sobre la deformada {casoDeformada}" : "")
                  + "). Los estribos van solo en la vista de detalle.");
    }

    Vector3 PosicionQuizaDeformada(Nodo n, Dictionary<int, DespNodo> desp,
                                   float escala)
    {
        DespNodo d;
        if (desp == null || !desp.TryGetValue(n.id, out d))
            return Ejes.PosicionDe(n);
        return Ejes.PosicionDeformada(n, d.ux, d.uy, d.uz, escala);
    }

    // ----------------------------------------------------------------
    // ARMADURA
    // ----------------------------------------------------------------
    /// La lamina de detalle se pone junto al edificio, apoyada en el
    /// suelo, separada una vez su ancho para que no se encime.
    Vector3 OffsetDetalle()
    {
        if (Anexo.caja == null) return new Vector3(-20f, 0f, 0f);
        CajaEdificio c = Anexo.caja;
        BloqueArmadura a = Anexo.armadura;
        // Ejes.AUnity manda: OpenSees x -> Unity x, OpenSees z -> Unity y.
        // La jaula queda al costado del edificio (x por debajo de x_min),
        // apoyada en el suelo y centrada en la profundidad de la planta.
        return new Vector3(c.x_min - (c.x_max - c.x_min) * 0.35f
                                   - a.nodo_inferior.x,
                           c.z_min - a.nodo_inferior.z,
                           (c.y_min + c.y_max) * 0.5f - a.nodo_inferior.y);
    }

    void DibujarArmadura(BloqueArmadura a, float escala, Vector3 offset)
    {
        if (a.barras == null || a.nodo_inferior == null || a.nodo_superior == null)
            return;

        Vector3 pie = Ejes.AUnity(a.nodo_inferior.x, a.nodo_inferior.y,
                                  a.nodo_inferior.z) + offset;
        Vector3 cabeza = pie + Vector3.up
                       * (a.nodo_superior.z - a.nodo_inferior.z) * escala;

        string nombre = escala > 1f ? "Armadura_DETALLE"
                                    : $"Armadura_columna_{a.columna_id}";
        Transform padre = new GameObject(nombre).transform;
        padre.SetParent(transform, false);
        creados.Add(padre.gameObject);

        // La seccion vive en el plano horizontal: su eje y va a X de
        // Unity y su eje z va a Z de Unity, porque la columna sube en Y.
        // En la vista de detalle la jaula ya viene ampliada, asi que la
        // barra solo se escala: queda al 4 % del ancho, igual que 16 mm
        // en 400 mm reales. Multiplicar ademas por exageracionBarra la
        // dejaba al 24 % y la jaula se veia como un bloque macizo.
        float exagera = escala > 1f ? escala : exageracionBarra;
        float grosorBarra = a.diametro_barra * exagera;
        foreach (PuntoSeccion p in a.barras)
        {
            Vector3 off = new Vector3(p.y, 0f, p.z) * escala;
            GameObject barra = Cilindro(pie + off, cabeza + off, grosorBarra);
            barra.name = $"barra_{p.y:0.000}_{p.z:0.000}";
            barra.transform.SetParent(padre, true);
            Pintar(barra, colorBarra);
            creados.Add(barra);
        }

        float grosorEstribo = a.diametro_estribo * exagera;
        float altura = Vector3.Distance(pie, cabeza);
        int cuantos = Mathf.Max(
            1, Mathf.RoundToInt(altura / (a.espaciamiento_estribo * escala)));
        for (int i = 0; i <= cuantos; i++)
        {
            float t = (float)i / cuantos;
            Vector3 centro = Vector3.Lerp(pie, cabeza, t);
            Poligono(a.estribo_exterior, centro, grosorEstribo, escala, padre,
                     $"estribo_ext_{i}");
            Poligono(a.estribo_rombo, centro, grosorEstribo, escala, padre,
                     $"estribo_rombo_{i}");
        }

        Debug.Log($"VisorSemana03: {(escala > 1f ? "DETALLE x" + escala : "en sitio")} "
                  + $"columna {a.columna_id} "
                  + $"({a.axial_G_kN:0} kN en G) con {a.barras.Count} barras "
                  + $"phi{a.diametro_barra * 1000f:0}, cuantia {a.cuantia_pct:0.00} %. "
                  + a.procedencia);
    }

    /// Dibuja un poligono cerrado de la seccion como aro de cilindros.
    void Poligono(List<PuntoSeccion> puntos, Vector3 centro, float grosor,
                  float escala, Transform padre, string nombre)
    {
        if (puntos == null || puntos.Count < 2) return;
        for (int i = 0; i < puntos.Count; i++)
        {
            PuntoSeccion p = puntos[i];
            PuntoSeccion q = puntos[(i + 1) % puntos.Count];
            GameObject lado = Cilindro(centro + new Vector3(p.y, 0f, p.z) * escala,
                                       centro + new Vector3(q.y, 0f, q.z) * escala,
                                       grosor);
            lado.name = nombre + "_" + i;
            lado.transform.SetParent(padre, true);
            Pintar(lado, colorEstribo);
            creados.Add(lado);
        }
    }

    // ----------------------------------------------------------------
    private static Mesh mallaCono;

    /// Unity no trae primitiva de cono, y una caja como punta hacia que
    /// las flechas parecieran martillos. Se genera una vez y se comparte.
    static Mesh MallaCono(int lados = 16)
    {
        if (mallaCono != null) return mallaCono;

        var vertices = new List<Vector3>();
        var triangulos = new List<int>();
        vertices.Add(new Vector3(0f, 1f, 0f));           // 0: punta
        vertices.Add(Vector3.zero);                      // 1: centro base
        for (int i = 0; i < lados; i++)
        {
            float t = 2f * Mathf.PI * i / lados;
            vertices.Add(new Vector3(Mathf.Cos(t), 0f, Mathf.Sin(t)));
        }
        for (int i = 0; i < lados; i++)
        {
            int a = 2 + i, b = 2 + (i + 1) % lados;
            triangulos.Add(0); triangulos.Add(b); triangulos.Add(a);   // manto
            triangulos.Add(1); triangulos.Add(a); triangulos.Add(b);   // tapa
        }

        mallaCono = new Mesh { name = "ConoFlecha" };
        mallaCono.SetVertices(vertices);
        mallaCono.SetTriangles(triangulos, 0);
        mallaCono.RecalculateNormals();
        return mallaCono;
    }

    GameObject Cono(Vector3 baseP, Vector3 punta, float radio)
    {
        GameObject cono = new GameObject("cono");
        cono.AddComponent<MeshFilter>().sharedMesh = MallaCono();
        cono.AddComponent<MeshRenderer>();

        Vector3 direccion = punta - baseP;
        float largo = direccion.magnitude;
        cono.transform.position = baseP;
        cono.transform.localScale = new Vector3(radio, largo, radio);
        if (largo > 1e-6f) cono.transform.up = direccion.normalized;
        return cono;
    }

    GameObject Cilindro(Vector3 desde, Vector3 hasta, float grosor)
    {
        GameObject cil = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        Collider col = cil.GetComponent<Collider>();
        if (col != null) DestroyImmediate(col);   // no estorbar al editor
        cil.transform.position = (desde + hasta) / 2f;

        Vector3 direccion = hasta - desde;
        float largo = direccion.magnitude;
        // El cilindro de Unity mide 2 de alto y apunta en Y.
        cil.transform.localScale = new Vector3(grosor, largo / 2f, grosor);
        if (largo > 1e-6f) cil.transform.up = direccion.normalized;
        return cil;
    }

    void Pintar(GameObject go, Color color)
    {
        Material mat;
        if (!materiales.TryGetValue(color, out mat))
        {
            // El mismo shader que usa el visor: con URP, Shader.Find
            // ("Standard") devuelve null y todo sale magenta.
            mat = new Material(VisorEstructura.ShaderCompatible());
            mat.color = color;
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            materiales[color] = mat;
        }
        go.GetComponent<Renderer>().sharedMaterial = mat;
    }
}
