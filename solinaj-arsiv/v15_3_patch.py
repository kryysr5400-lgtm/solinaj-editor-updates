def apply_update(source_text):
    source_text = source_text.replace('APP_NAME = "Solinaj Arşivleyici V15.2"',
                                      'APP_NAME = "Solinaj Arşivleyici V15.3"')
    source_text = source_text.replace('APP_VERSION = "15.2"',
                                      'APP_VERSION = "15.3"')
    old = """        self.update_btn=ttk.Button(controls,text="↻  GÜNCELLE",command=self.start_self_update,style="Gray.TButton")
        self.update_btn.pack(side="right")
"""
    new = """        # V15.3: Orta bölümdeki tekrar eden GÜNCELLE düğmesi kaldırıldı.
        # Güncelleme yalnızca sol menüdeki Güncelleme sayfasından yapılır.
"""
    if old not in source_text:
        raise RuntimeError("Ana ekrandaki GÜNCELLE düğmesi bulunamadı.")
    return source_text.replace(old, new, 1)
