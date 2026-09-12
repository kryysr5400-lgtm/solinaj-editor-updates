import re

def apply_update(source_text):
    source_text = source_text.replace('APP_NAME = "Solinaj Arşivleyici V15.0"',
                                      'APP_NAME = "Solinaj Arşivleyici V15.1"')
    source_text = source_text.replace('APP_VERSION = "15.0"',
                                      'APP_VERSION = "15.1"')
    return source_text
