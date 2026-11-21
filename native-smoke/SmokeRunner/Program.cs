using System.Reflection;
using System.Drawing;
using System.Windows.Forms;
using Lab1;

internal static class Program
{
    static readonly string OutDir = Path.GetFullPath("NativeResults");

    [STAThread]
    static int Main()
    {
        Directory.CreateDirectory(OutDir);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        try
        {
            using MainForm form = new MainForm();
            form.StartPosition = FormStartPosition.Manual;
            form.Location = new Point(10, 10);
            form.Size = new Size(1220, 780);
            form.CreateControl();
            form.PerformLayout();

            var source = Get<RichTextBox>(form, "sourceTextBox");
            var s1 = Get<ListBox>(form, "section1ListBox");
            var s2 = Get<ListBox>(form, "section2ListBox");
            var sr = Get<ListBox>(form, "searchResultsListBox");
            var c1 = Get<ComboBox>(form, "section1SortComboBox");
            var c2 = Get<ComboBox>(form, "section2SortComboBox");
            var all = Get<RadioButton>(form, "allRadioButton");
            var digits = Get<RadioButton>(form, "digitsRadioButton");
            var email = Get<RadioButton>(form, "emailRadioButton");
            var chk1 = Get<CheckBox>(form, "searchSection1CheckBox");
            var chk2 = Get<CheckBox>(form, "searchSection2CheckBox");
            var search = Get<TextBox>(form, "searchTextBox");

            Assert(s1.SelectionMode == SelectionMode.MultiExtended, "section1 MultiExtended");
            Assert(s2.SelectionMode == SelectionMode.MultiExtended, "section2 MultiExtended");
            Assert(c1.Items.Count == 4 && c2.Items.Count == 4, "4 sort modes");
            Save(form, "01_main_form.png");

            string sample = File.ReadAllText("test.txt");
            source.Text = sample;
            Save(form, "02_open_file.png");

            all.Checked = true;
            Invoke(form, "StartFiltering");
            Assert(s1.Items.Count == 14, "All filter count");
            Save(form, "03_filter_all.png");

            digits.Checked = true;
            Invoke(form, "StartFiltering");
            Assert(Seq(s1).SequenceEqual(new[] { "test42", "another99", "12345" }), "Digits filter");
            Save(form, "04_filter_digits.png");

            email.Checked = true;
            Invoke(form, "StartFiltering");
            Assert(Seq(s1).SequenceEqual(new[] { "user@example.com", "mail@test.ru", "student@mail.com" }), "Email filter");
            Save(form, "05_filter_email.png");

            all.Checked = true;
            Invoke(form, "StartFiltering");
            s1.SetSelected(0, true);
            s1.SetSelected(1, true);
            s1.SetSelected(2, true);
            InvokeStatic(typeof(MainForm), "MoveSelected", s1, s2);
            Assert(s2.Items.Count == 3 && s1.Items.Count == 11, "Move selected");
            Save(form, "06_transfer.png");

            Invoke(form, "ResetForm");
            source.Text = sample;
            all.Checked = true;
            Invoke(form, "StartFiltering");
            c1.SelectedIndex = 2;
            Invoke(form, "SortList", s1, 2);
            var sorted = Seq(s1);
            for (int i = 1; i < sorted.Count; i++)
                Assert(sorted[i - 1].Length <= sorted[i].Length, "Length ascending sort");
            Save(form, "07_sort.png");

            search.Text = "mail";
            chk1.Checked = true;
            chk2.Checked = true;
            Invoke(form, "Search");
            Assert(Seq(sr).Count == 3, "Search results");
            Save(form, "08_search.png");

            using AddWordForm add = new AddWordForm();
            add.CreateControl();
            add.PerformLayout();
            Get<TextBox>(add, "wordTextBox").Text = "новое_слово";
            Save(add, "09_add_form.png");

            var bubble = WordProcessor.BubbleSort(new[] { "bbb", "a", "cc" }, SortMode.LengthAscending);
            Assert(bubble.SequenceEqual(new[] { "a", "cc", "bbb" }), "Bubble sort direct");

            using (var w = new StreamWriter(Path.Combine(OutDir, "saved_result.txt"), false, System.Text.Encoding.UTF8))
                foreach (var item in s2.Items.Cast<object>())
                    w.WriteLine(item?.ToString() ?? "");

            File.WriteAllText(Path.Combine(OutDir, "SMOKE_PASS.txt"),
                "NATIVE WINDOWS WINFORMS SMOKE TEST: PASS\r\n" +
                "Build: PASS\r\n" +
                "Controls: PASS\r\n" +
                "Filters: PASS\r\n" +
                "Transfer: PASS\r\n" +
                "Bubble sort: PASS\r\n" +
                "Search: PASS\r\n" +
                "AddWordForm render: PASS\r\n");

            Console.WriteLine("NATIVE_SMOKE_PASS");
            return 0;
        }
        catch (Exception ex)
        {
            File.WriteAllText(Path.Combine(OutDir, "SMOKE_FAIL.txt"), ex.ToString());
            Console.Error.WriteLine(ex);
            return 1;
        }
    }

    static T Get<T>(object obj, string name) where T : class
    {
        var f = obj.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingFieldException(obj.GetType().FullName, name);
        return (T)(f.GetValue(obj) ?? throw new NullReferenceException(name));
    }

    static object? Invoke(object obj, string name, params object[] args)
    {
        var methods = obj.GetType().GetMethods(BindingFlags.Instance | BindingFlags.NonPublic)
            .Where(m => m.Name == name && m.GetParameters().Length == args.Length).ToList();
        if (methods.Count == 0) throw new MissingMethodException(obj.GetType().FullName, name);
        return methods[0].Invoke(obj, args);
    }

    static object? InvokeStatic(Type t, string name, params object[] args)
    {
        var m = t.GetMethods(BindingFlags.Static | BindingFlags.NonPublic)
            .FirstOrDefault(x => x.Name == name && x.GetParameters().Length == args.Length)
            ?? throw new MissingMethodException(t.FullName, name);
        return m.Invoke(null, args);
    }

    static List<string> Seq(ListBox box) => box.Items.Cast<object>().Select(x => x?.ToString() ?? "").ToList();

    static void Assert(bool ok, string name)
    {
        if (!ok) throw new InvalidOperationException("ASSERT FAIL: " + name);
        Console.WriteLine("PASS: " + name);
    }

    static void Save(Control control, string fileName)
    {
        control.PerformLayout();
        foreach (Control c in control.Controls) c.CreateControl();
        using Bitmap bmp = new Bitmap(Math.Max(1, control.Width), Math.Max(1, control.Height));
        control.DrawToBitmap(bmp, new Rectangle(0, 0, bmp.Width, bmp.Height));
        bmp.Save(Path.Combine(OutDir, fileName), System.Drawing.Imaging.ImageFormat.Png);
    }
}
