# -*- coding: utf-8 -*-
import ast
import re

TARGET_VERSION = "16.9"

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sınıfı bulunamadı.")

def _replace_method(source_text, method_name, new_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [n for n in app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name]
    if not matches:
        raise RuntimeError(f"{method_name} metodu bulunamadı.")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    return "".join(lines[:target.lineno-1]) + new_source.strip("\n") + "\n" + "".join(lines[target.end_lineno:])

def apply_update(source_text):
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', source_text)
    if not m:
        raise RuntimeError("Sürüm bilgisi bulunamadı.")
    if m.group(1) != "16.8":
        raise RuntimeError("Bu düzeltme yalnızca V16.8 içindir. Mevcut: V" + m.group(1))

    new_download = '''
    def _download_update_bytes(self, url, timeout=30):
        import base64
        import subprocess
        import urllib.request
        import time as _time

        sep="&" if "?" in url else "?"
        live_url=url+sep+"_="+str(int(_time.time()*1000))
        first_error=None

        try:
            req=urllib.request.Request(
                live_url,
                headers={
                    "User-Agent":"Solinaj-Arsivleyici/"+APP_VERSION,
                    "Cache-Control":"no-cache, no-store, max-age=0",
                    "Pragma":"no-cache",
                    "Expires":"0",
                }
            )
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return r.read()
        except Exception as e:
            first_error=e

        if os.name=="nt":
            try:
                safe_url=live_url.replace("'", "''")
                ps=(
                    "$ErrorActionPreference='Stop';"
                    "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;"
                    "$wc=New-Object Net.WebClient;"
                    "$wc.Headers['User-Agent']='Solinaj-Arsivleyici/"+APP_VERSION+"';"
                    "$wc.Headers['Cache-Control']='no-cache';"
                    "$b=$wc.DownloadData('"+safe_url+"');"
                    "[Console]::Out.Write([Convert]::ToBase64String($b))"
                )
                cp=subprocess.run(
                    ["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-Command",ps],
                    capture_output=True,text=True,encoding="utf-8",errors="replace",
                    timeout=max(8,int(timeout)+8),
                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)
                )
                if cp.returncode != 0:
                    raise RuntimeError((cp.stderr or cp.stdout or "PowerShell indirme hatası").strip())
                data=base64.b64decode((cp.stdout or "").strip())
                if not data:
                    raise RuntimeError("PowerShell boş veri döndürdü.")
                return data
            except Exception as second_error:
                raise RuntimeError(
                    "İnternet güncellemesi indirilemedi. "
                    "Python: "+str(first_error)+" | Windows: "+str(second_error)
                )

        raise RuntimeError("İnternet güncellemesi indirilemedi: "+str(first_error))
'''

    source_text = _replace_method(source_text, "_download_update_bytes", new_download)
    source_text = re.sub(r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"', 'APP_NAME = "Solinaj Arşivleyici V16.9"', source_text, count=1)
    source_text = re.sub(r'APP_VERSION\s*=\s*"[^"]+"', 'APP_VERSION = "16.9"', source_text, count=1)
    compile(source_text, "<solinaj_arsivleyici_v16_9>", "exec")
    return source_text
