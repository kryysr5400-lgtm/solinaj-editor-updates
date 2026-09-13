# -*- coding: utf-8 -*-
import ast
import re
import textwrap

TARGET_VERSION="17.1.1"

def _find_app(tree):
    for node in tree.body:
        if isinstance(node,ast.ClassDef) and node.name=="App":
            return node
    raise RuntimeError("App sınıfı bulunamadı.")

def _method_block(text):
    return textwrap.indent(textwrap.dedent(text).strip("\n"),"    ")+"\n"

def _replace_method(source_text,name,body_text):
    tree=ast.parse(source_text)
    app=_find_app(tree)
    matches=[n for n in app.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
    if not matches:
        raise RuntimeError(name+" metodu bulunamadı.")
    target=matches[-1]
    lines=source_text.splitlines(keepends=True)
    return "".join(lines[:target.lineno-1])+_method_block(body_text)+"".join(lines[target.end_lineno:])

def apply_update(source_text):
    m=re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',source_text)
    if not m:
        raise RuntimeError("Sürüm bilgisi bulunamadı.")
    if m.group(1)!="17.1":
        raise RuntimeError("Bu düzeltme yalnızca V17.1 içindir. Mevcut: V"+m.group(1))

    source_text=_replace_method(source_text,"_v171_install_scan_counters", """
def _v171_install_scan_counters(self):
    try:
        old=getattr(self,"scan_counts_frame",None)
        if old is not None and old.winfo_exists():
            try:
                old.destroy()
            except Exception:
                pass
    except Exception:
        pass

    try:
        work=self.progress.master
        dash=work.master

        scan_counts=tk.Frame(
            dash,bg="#091522",
            highlightbackground="#1e435d",
            highlightthickness=1
        )
        self.scan_counts_frame=scan_counts

        try:
            scan_counts.pack(fill="x",padx=24,pady=(0,10),after=work)
        except Exception:
            scan_counts.pack(fill="x",padx=24,pady=(0,10))

        self.scan_total_var=tk.StringVar(value="0")
        self.scan_scanned_var=tk.StringVar(value="0")
        self.scan_processed_var=tk.StringVar(value="0")

        defs=[
            ("TARANACAK DOSYA",self.scan_total_var),
            ("TARANAN DOSYA",self.scan_scanned_var),
            ("İŞLEM GÖREN",self.scan_processed_var),
        ]

        for i,(title,var) in enumerate(defs):
            box=tk.Frame(
                scan_counts,bg="#0d1b29",
                highlightbackground="#1e435d",
                highlightthickness=1
            )
            box.grid(row=0,column=i,sticky="nsew",padx=(0 if i==0 else 5,0),pady=0)
            scan_counts.columnconfigure(i,weight=1)

            tk.Label(
                box,text=title,bg="#0d1b29",fg="#7894a8",
                font=("Segoe UI",8,"bold")
            ).pack(anchor="w",padx=10,pady=(7,0))

            tk.Label(
                box,textvariable=var,bg="#0d1b29",fg="#ffffff",
                font=("Segoe UI",15,"bold")
            ).pack(anchor="w",padx=10,pady=(0,7))

        try:
            scan_counts.lift()
        except Exception:
            pass

    except Exception as e:
        try:
            self.add_log_ui("V17.1.1 sabit sayaç paneli kurulamadı: "+str(e))
        except Exception:
            pass
""")

    source_text=_replace_method(source_text,"_v171_set_scan_counters", """
def _v171_set_scan_counters(self,total=None,scanned=None,processed=None,games=None):
    def _apply():
        try:
            frame=getattr(self,"scan_counts_frame",None)
            if frame is not None and frame.winfo_exists():
                try:
                    if not frame.winfo_ismapped():
                        work=self.progress.master
                        frame.pack(fill="x",padx=24,pady=(0,10),after=work)
                    frame.lift()
                except Exception:
                    pass

            if total is not None and hasattr(self,"scan_total_var"):
                self.scan_total_var.set(str(total))
            if scanned is not None and hasattr(self,"scan_scanned_var"):
                self.scan_scanned_var.set(str(scanned))
            if processed is not None and hasattr(self,"scan_processed_var"):
                self.scan_processed_var.set(str(processed))
            if games is not None:
                self.stats["Oyunlar"]=int(games)
                if hasattr(self,"stat_vars") and "Oyunlar" in self.stat_vars:
                    self.stat_vars["Oyunlar"].set(str(games))
        except Exception:
            pass
    self.after(0,_apply)
""")

    source_text=re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V17.1.1"',
        source_text,count=1
    )
    source_text=re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "17.1.1"',
        source_text,count=1
    )

    compile(source_text,"<solinaj_v17_1_1>","exec")
    return source_text
