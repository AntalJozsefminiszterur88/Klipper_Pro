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
    
    ikon_path = os.path.abspath(IKON_NEVE)

    # Parancs összeállítása
    cmd = [
        "pyinstaller",
        "--noconsole",
        "--onefile",
        "--name", EXE_NEVE,
        "--collect-all", "customtkinter",
    ]

    # Ikon hozzáadása
    if os.path.exists(ikon_path):
        print(f"Ikon fájl megtalálva: {ikon_path}")
        # Ez teszi az ikont az EXE fájlra magára (Fájlkezelőben)
        cmd.extend(["--icon", ikon_path])
        # Ez csomagolja be az ikont az EXE belsejébe (hogy a program megtalálja futás közben)
        cmd.extend(["--add-data", f"{ikon_path}{os.pathsep}."])
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

        dist_exe_path = os.path.join("dist", f"{EXE_NEVE}.exe")
        if os.path.exists(ikon_path) and os.path.exists(dist_exe_path):
            try:
                shutil.copy2(ikon_path, os.path.join("dist", os.path.basename(ikon_path)))
                print("Ikon bemásolva a dist mappába is, hogy a parancsikonok is ezt használják.")
            except Exception as copy_error:
                print(f"FIGYELEM: Az ikon másolása nem sikerült: {copy_error}")

    except subprocess.CalledProcessError as e:
        print("\nHIBA történt a generálás közben!")
        print(e)

if __name__ == "__main__":
    install_pyinstaller()
    build_exe()
    input("\nNyomj Entert a kilépéshez...")