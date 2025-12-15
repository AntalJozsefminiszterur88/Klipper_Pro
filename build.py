import os
import subprocess
import sys
import shutil

# --- BEÁLLÍTÁSOK ---
SCRIPT_NEVE = "medal_renamer_v2.py"
EXE_NEVE = "MedalRenamer_Final"
IKON_NEVE = "icon.ico" 

def install_pyinstaller():
    print("PyInstaller ellenőrzése...")
    try:
        import PyInstaller
        print("PyInstaller már telepítve van.")
    except ImportError:
        print("PyInstaller nincs telepítve. Telepítés folyamatban...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build_exe():
    if not os.path.exists(SCRIPT_NEVE):
        print(f"HIBA: Nem találom a fájlt: {SCRIPT_NEVE}")
        input("Nyomj Entert a kilépéshez...")
        return

    print(f"EXE generálása ebből: {SCRIPT_NEVE}...")
    
    # Parancs összeállítása
    cmd = [
        "pyinstaller",
        "--noconsole",
        "--onefile",
        "--name", EXE_NEVE,
        "--collect-all", "customtkinter",
    ]

    # Ikon hozzáadása
    if os.path.exists(IKON_NEVE):
        print(f"Ikon fájl megtalálva: {IKON_NEVE}")
        # Ez teszi az ikont az EXE fájlra magára (Fájlkezelőben)
        cmd.extend(["--icon", IKON_NEVE])
        # Ez csomagolja be az ikont az EXE belsejébe (hogy a program megtalálja futás közben)
        cmd.extend(["--add-data", f"{IKON_NEVE};."])
    else:
        print("FIGYELEM: Nem találtam 'icon.ico' fájlt.")

    cmd.append(SCRIPT_NEVE)

    try:
        subprocess.check_call(cmd)
        print("\n" + "="*30)
        print("SIKERES GENERÁLÁS!")
        print("="*30)
        print(f"Az elkészült programot itt találod: dist/{EXE_NEVE}.exe")
        
        if os.path.exists("build"): shutil.rmtree("build")
        if os.path.exists(f"{EXE_NEVE}.spec"): os.remove(f"{EXE_NEVE}.spec")
        
    except subprocess.CalledProcessError as e:
        print("\nHIBA történt a generálás közben!")
        print(e)

if __name__ == "__main__":
    install_pyinstaller()
    build_exe()
    input("\nNyomj Entert a kilépéshez...")