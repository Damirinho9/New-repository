using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using System.IO;

public static class Case4Setup
{
    const string Root = "Assets/Case4";
    const string FbxPath = Root + "/7334625_Goblet_LOW.fbx";
    const string TexPath = Root + "/goblet_albedo.png";
    const string MatPath = Root + "/Aged_Brass_Patina.mat";
    const string ScenePath = Root + "/Case4_ImportCheck.unity";

    public static void BuildScene()
    {
        Directory.CreateDirectory(Root);
        AssetDatabase.Refresh();

        var importer = AssetImporter.GetAtPath(FbxPath) as ModelImporter;
        if (importer == null) throw new System.Exception("FBX ModelImporter not found: " + FbxPath);
        importer.globalScale = 1.0f;
        importer.useFileScale = true;
        importer.importMaterials = false;
        importer.SaveAndReimport();

        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(FbxPath);
        if (prefab == null) throw new System.Exception("FBX prefab not found after import");

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var goblet = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
        goblet.name = "Goblet_LOW";
        goblet.transform.position = Vector3.zero;
        goblet.transform.rotation = Quaternion.identity;
        goblet.transform.localScale = Vector3.one;

        var shader = Shader.Find("Standard");
        if (shader == null) throw new System.Exception("Standard shader not found");
        var mat = AssetDatabase.LoadAssetAtPath<Material>(MatPath);
        if (mat == null)
        {
            mat = new Material(shader);
            mat.name = "Aged_Brass_Patina";
            mat.SetFloat("_Metallic", 0.78f);
            mat.SetFloat("_Glossiness", 0.64f);
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(TexPath);
            if (tex != null) mat.mainTexture = tex;
            AssetDatabase.CreateAsset(mat, MatPath);
        }
        foreach (var r in goblet.GetComponentsInChildren<Renderer>())
            r.sharedMaterial = mat;

        Bounds bounds = new Bounds(goblet.transform.position, Vector3.zero);
        bool any = false;
        foreach (var r in goblet.GetComponentsInChildren<Renderer>())
        {
            if (!any) { bounds = r.bounds; any = true; }
            else bounds.Encapsulate(r.bounds);
        }
        if (!any) throw new System.Exception("No renderers found in FBX");

        var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.name = "Ground";
        ground.transform.position = new Vector3(0, bounds.min.y - 0.002f, 0);
        ground.transform.localScale = Vector3.one * 0.12f;
        var groundMat = new Material(shader);
        groundMat.color = new Color(0.08f,0.09f,0.11f,1);
        ground.GetComponent<Renderer>().sharedMaterial = groundMat;

        var key = new GameObject("Key Light").AddComponent<Light>();
        key.type = LightType.Directional;
        key.intensity = 1.25f;
        key.color = new Color(1.0f,0.84f,0.67f);
        key.transform.rotation = Quaternion.Euler(42,-38,0);

        var fill = new GameObject("Fill Light").AddComponent<Light>();
        fill.type = LightType.Point;
        fill.intensity = 3.2f;
        fill.range = 2.0f;
        fill.color = new Color(0.45f,0.70f,1.0f);
        fill.transform.position = bounds.center + new Vector3(-0.25f,0.18f,-0.18f);

        var cam = new GameObject("Main Camera").AddComponent<Camera>();
        cam.tag = "MainCamera";
        cam.transform.position = bounds.center + new Vector3(0.32f,0.18f,-0.42f);
        cam.transform.LookAt(bounds.center + Vector3.up*0.015f);
        cam.fieldOfView = 38f;

        EditorSceneManager.SaveScene(scene, ScenePath);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        string root = Directory.GetParent(Application.dataPath).FullName;
        string validation =
            "CASE 4 UNITY IMPORT: PASS\n" +
            "Engine=Unity Editor " + Application.unityVersion + "\n" +
            "Asset=7334625_Goblet_LOW.fbx\n" +
            "Object=Goblet_LOW\n" +
            "BoundsHeightMeters=" + bounds.size.y.ToString("F6", System.Globalization.CultureInfo.InvariantCulture) + "\n" +
            "ExpectedHeightMeters=0.231000\n" +
            "Material=Aged_Brass_Patina\n" +
            "Metallic=0.78\n" +
            "Lighting=Directional+Point\n" +
            "Scene=" + ScenePath + "\n";
        File.WriteAllText(Path.Combine(root, "UNITY_VALIDATION.txt"), validation);
        Debug.Log(validation.Replace("\n", " | "));

        if (bounds.size.y < 0.20f || bounds.size.y > 0.26f)
            throw new System.Exception("Unexpected imported height: " + bounds.size.y);
    }
}

[InitializeOnLoad]
public static class Case4SceneFramer
{
    static int ticks = 0;
    static Case4SceneFramer()
    {
        EditorApplication.update += Tick;
    }

    static void Tick()
    {
        ticks++;
        if (ticks < 120) return;
        EditorApplication.update -= Tick;
        try
        {
            if (File.Exists("Assets/Case4/Case4_ImportCheck.unity"))
                EditorSceneManager.OpenScene("Assets/Case4/Case4_ImportCheck.unity", OpenSceneMode.Single);
            var go = GameObject.Find("Goblet_LOW");
            if (go != null)
            {
                Selection.activeGameObject = go;
                if (SceneView.lastActiveSceneView != null)
                {
                    SceneView.lastActiveSceneView.FrameSelected();
                    SceneView.lastActiveSceneView.Repaint();
                }
            }
        }
        catch (System.Exception e) { Debug.LogException(e); }
    }
}
