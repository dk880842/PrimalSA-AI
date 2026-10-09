// HotUpdate.dll 靜態分析小工具（只用 ReflectionOnly 載入，不執行任何遊戲程式碼）
// 用 Windows 內建 csc.exe（C# 5）編譯：
//   C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /out:SchemaDump.exe SchemaDump.cs
// 用法：
//   SchemaDump.exe schema <HotUpdate.dll> [依賴 dll 資料夾]   → Tabtoy tag→欄位 對照（TSV）
//   SchemaDump.exe enums  <HotUpdate.dll> [依賴 dll 資料夾]   → 所有列舉（TSV）
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;

class SchemaDump
{
    static Dictionary<short, OpCode> ops = new Dictionary<short, OpCode>();
    static string depDir;

    static int Main(string[] a)
    {
        if (a.Length < 2) { Console.Error.WriteLine("用法: SchemaDump.exe schema|enums <HotUpdate.dll> [依賴資料夾]"); return 1; }
        Console.OutputEncoding = System.Text.Encoding.UTF8;
        depDir = a.Length > 2 ? a[2] : Path.GetDirectoryName(Path.GetFullPath(a[1]));
        foreach (var f in typeof(OpCodes).GetFields(BindingFlags.Public | BindingFlags.Static))
        {
            var op = (OpCode)f.GetValue(null); ops[op.Value] = op;
        }
        AppDomain.CurrentDomain.ReflectionOnlyAssemblyResolve += Resolve;
        var asm = Assembly.ReflectionOnlyLoadFrom(Path.GetFullPath(a[1]));
        Type[] types;
        try { types = asm.GetTypes(); }
        catch (ReflectionTypeLoadException e) { types = e.Types.Where(t => t != null).ToArray(); }
        if (a[0] == "enums") DumpEnums(types); else DumpSchema(asm.ManifestModule, types);
        return 0;
    }

    static Assembly Resolve(object s, ResolveEventArgs e)
    {
        var name = new AssemblyName(e.Name).Name;
        foreach (var cand in new[] { Path.Combine(depDir, name + ".dll"), Path.Combine(depDir, name + ".dll.bin") })
            if (File.Exists(cand)) return Assembly.ReflectionOnlyLoadFrom(cand);
        try { return Assembly.ReflectionOnlyLoad(e.Name); } catch { }
        try { return Assembly.ReflectionOnlyLoad(name); } catch { }
        return null;
    }

    static void DumpEnums(Type[] types)
    {
        foreach (var t in types.OrderBy(x => x.FullName))
        {
            bool isEnum;
            try { isEnum = t.IsEnum; } catch { continue; }
            if (!isEnum) continue;
            var parts = new List<string>();
            foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Static))
            {
                object v; try { v = f.GetRawConstantValue(); } catch { v = "?"; }
                parts.Add(f.Name + "=" + v);
            }
            Console.WriteLine(t.FullName + "\t" + string.Join(", ", parts));
        }
    }

    class Ins { public int Off; public OpCode Op; public long Arg; public int[] Targets; }

    static List<Ins> Decode(byte[] il)
    {
        var list = new List<Ins>(); int p = 0;
        while (p < il.Length)
        {
            var ins = new Ins { Off = p };
            short v = il[p++];
            if (v == 0xFE) v = (short)(0xFE00 | il[p++]);
            OpCode op; if (!ops.TryGetValue(v, out op)) break;
            ins.Op = op;
            switch (op.OperandType)
            {
                case OperandType.InlineNone: break;
                case OperandType.ShortInlineBrTarget: ins.Arg = (sbyte)il[p]; p += 1; ins.Arg += p; break;
                case OperandType.ShortInlineI: ins.Arg = (sbyte)il[p]; p += 1; break;
                case OperandType.ShortInlineVar: ins.Arg = il[p]; p += 1; break;
                case OperandType.InlineVar: ins.Arg = BitConverter.ToUInt16(il, p); p += 2; break;
                case OperandType.InlineBrTarget: ins.Arg = BitConverter.ToInt32(il, p); p += 4; ins.Arg += p; break;
                case OperandType.InlineI8: case OperandType.InlineR: ins.Arg = BitConverter.ToInt64(il, p); p += 8; break;
                case OperandType.InlineSwitch:
                    int n = BitConverter.ToInt32(il, p); p += 4;
                    var rel = new int[n];
                    for (int k = 0; k < n; k++) { rel[k] = BitConverter.ToInt32(il, p); p += 4; }
                    ins.Targets = rel.Select(r => p + r).ToArray(); break;
                default: ins.Arg = BitConverter.ToInt32(il, p); p += 4; break;
            }
            list.Add(ins);
        }
        return list;
    }

    static bool IsLdc(Ins x) { return x.Op.Name.StartsWith("ldc.i4"); }
    static int LdcVal(Ins x)
    {
        string n = x.Op.Name;
        if (n == "ldc.i4" || n == "ldc.i4.s") return (int)x.Arg;
        if (n == "ldc.i4.m1") return -1;
        return int.Parse(n.Substring(7));
    }

    static string TypeName(Type t)
    {
        if (t.IsGenericType)
        {
            var name = t.GetGenericTypeDefinition().FullName;
            return name + "<" + string.Join(",", t.GetGenericArguments().Select(TypeName)) + ">";
        }
        return t.FullName ?? t.Name;
    }

    static void DumpSchema(Module mod, Type[] types)
    {
        foreach (var t in types)
        {
            MethodInfo[] ms;
            try { ms = t.GetMethods(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly); }
            catch { continue; }
            foreach (var md in ms.Where(m => m.Name == "Deserialize"))
            {
                MethodBody body; try { body = md.GetMethodBody(); } catch { continue; }
                if (body == null) continue;
                var pars = md.GetParameters(); if (pars.Length == 0) continue;
                var ins = Decode(body.GetILAsByteArray());
                var byOff = new Dictionary<int, int>();
                for (int i = 0; i < ins.Count; i++) byOff[ins[i].Off] = i;
                var target = new Dictionary<int, int>();   // 指令索引 → tag
                for (int i = 0; i < ins.Count; i++)
                {
                    var x = ins[i];
                    if (x.Op.Value == OpCodes.Switch.Value)
                    {
                        int bas = 0;
                        if (i >= 2 && ins[i - 1].Op.Value == OpCodes.Sub.Value && IsLdc(ins[i - 2])) bas = LdcVal(ins[i - 2]);
                        for (int k = 0; k < x.Targets.Length; k++)
                        {
                            int ti; if (byOff.TryGetValue(x.Targets[k], out ti) && !target.ContainsKey(ti)) target[ti] = bas + k;
                        }
                    }
                    if ((x.Op.Value == OpCodes.Beq.Value || x.Op.Value == OpCodes.Beq_S.Value) && i >= 1 && IsLdc(ins[i - 1]))
                    {
                        int ti; if (byOff.TryGetValue((int)x.Arg, out ti) && !target.ContainsKey(ti)) target[ti] = LdcVal(ins[i - 1]);
                    }
                }
                string p0; try { p0 = TypeName(pars[0].ParameterType.IsByRef ? pars[0].ParameterType.GetElementType() : pars[0].ParameterType); } catch { p0 = "?"; }
                foreach (var kv in target.OrderBy(k => k.Value))
                {
                    string fld = null, rd = null; int j = kv.Key, n = 0;
                    while (j < ins.Count && n < 12)
                    {
                        var c = ins[j];
                        if ((c.Op.Value == OpCodes.Stfld.Value || c.Op.Value == OpCodes.Ldfld.Value) && fld == null)
                        {
                            try { var f = mod.ResolveField((int)c.Arg, t.IsGenericType ? t.GetGenericArguments() : null, null); fld = f.Name + "|" + TypeName(f.FieldType); }
                            catch (Exception e) { fld = "?" + e.GetType().Name; }
                        }
                        if ((c.Op.Value == OpCodes.Call.Value || c.Op.Value == OpCodes.Callvirt.Value) && rd == null)
                        {
                            try
                            {
                                var m = mod.ResolveMethod((int)c.Arg);
                                if (m.Name.StartsWith("Read"))
                                    rd = m.Name + (m.IsGenericMethod ? "<" + string.Join(",", m.GetGenericArguments().Select(z => z.Name)) + ">" : "");
                            }
                            catch { }
                        }
                        if (c.Op.Value == OpCodes.Stfld.Value && rd != null) break;
                        if (c.Op.Value == OpCodes.Br.Value || c.Op.Value == OpCodes.Br_S.Value) break;
                        j++; n++;
                    }
                    if (fld != null) Console.WriteLine(p0 + "\t0x" + kv.Value.ToString("x") + "\t" + fld + "\t" + rd);
                }
            }
        }
    }
}
