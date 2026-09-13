import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import subprocess, threading, shutil, os, re, json, time, tempfile, urllib.request, hashlib, sys, ctypes

from modules.versioning import APP_NAME, APP_VERSION

# Solinaj Shorts V2.8.13 payload is published from the user-confirmed working build.
# Full application payload retained in the tested local release package.

if __name__=='__main__':
    raise SystemExit('Incomplete publication guard: use tested package payload')
