Option Explicit
On Error Resume Next

Dim sh, fso, base, app, pyw, pye, cmd, e
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

base = fso.GetParentFolderName(WScript.ScriptFullName)
app = fso.BuildPath(base, "app.py")

If Not fso.FileExists(app) Then
    MsgBox "Solinaj Shorts app.py bulunamadi: " & app, 16, "Solinaj Shorts"
    WScript.Quit 2
End If

pyw = ""
For Each pye In Array( _
    sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python313\pythonw.exe", _
    sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe", _
    sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python311\pythonw.exe", _
    sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python310\pythonw.exe" _
)
    If fso.FileExists(pye) Then
        pyw = pye
        Exit For
    End If
Next

If pyw = "" Then
    Set e = sh.Exec("cmd /c where pythonw.exe 2>nul")
    If Not e Is Nothing Then
        If Not e.StdOut.AtEndOfStream Then pyw = Trim(e.StdOut.ReadLine)
    End If
End If

sh.CurrentDirectory = base

If pyw <> "" Then
    cmd = Chr(34) & pyw & Chr(34) & " " & Chr(34) & app & Chr(34)
    sh.Run cmd, 0, False
    WScript.Quit 0
End If

pye = ""
Set e = sh.Exec("cmd /c where python.exe 2>nul")
If Not e Is Nothing Then
    If Not e.StdOut.AtEndOfStream Then pye = Trim(e.StdOut.ReadLine)
End If

If pye <> "" Then
    cmd = Chr(34) & pye & Chr(34) & " " & Chr(34) & app & Chr(34)
    sh.Run cmd, 0, False
    WScript.Quit 0
End If

MsgBox "Python bulunamadi. Solinaj Shorts baslatilamadi.", 16, "Solinaj Shorts"
WScript.Quit 3
