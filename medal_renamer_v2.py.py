import os
import sys
import json
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

# Megjelenés beállítása
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

HISTORY_FILE = "restore_map.json"

# --- EZ A FÜGGVÉNY A KULCS AZ IKONHOZ ---
def resource_path(relative_path):
    """ Megkeresi a fájlt, akár fejlesztői módban, akár EXE-ben vagyunk """
    try:
        # PyInstaller ideiglenes mappája (ha exe-ben fut)
        base_path = sys._MEIPASS
    except Exception:
        # Normál futás
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- A TÁLCA IKON JAVÍTÁSA (WINDOWS) ---
# Ez mondja meg a Windowsnak, hogy ez egy önálló program saját ikonnal
try:
    myappid = 'umgkl.medal.renamer.v2' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass

class ConflictDialog(ctk.CTkToplevel):
    def __init__(self, parent, original_file, target_name, path):
        super().__init__(parent)
        self.title("Névütközés Megoldása")
        self.geometry("600x380")
        self.result = None
        
        # --- IKON JAVÍTVA ITT IS ---
        # Közvetlenül a resource_path-ból töltjük be
        try:
            icon_path = resource_path("icon.ico")
            self.iconbitmap(icon_path)
        except Exception:
            pass # Ha nagyon nincs meg, nem halunk bele
        
        self.attributes("-topmost", True)
        self.transient(parent)
        self.grab_set() 

        ctk.CTkLabel(self, text="⚠️ Már létezik ilyen nevű fájl!", 
                     font=ctk.CTkFont(size=18, weight="bold"), text_color="#e74c3c").pack(pady=(20, 10))

        info_frame = ctk.CTkFrame(self, fg_color="#2b2d31")
        info_frame.pack(fill="x", padx=20, pady=10)
        
        self.create_info_row(info_frame, "Eredeti fájl:", original_file)
        self.create_info_row(info_frame, "Mappa:", path)
        self.create_info_row(info_frame, "Erre akartuk nevezni:", target_name, text_color="#f1c40f")

        ctk.CTkLabel(self, text="Adj meg egy új nevet (kiterjesztés nélkül):").pack(pady=(10, 5))
        
        self.name_entry = ctk.CTkEntry(self, width=400)
        self.name_entry.insert(0, os.path.splitext(target_name)[0] + "_alt")
        self.name_entry.pack(pady=5)
        self.name_entry.focus_set()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(btn_frame, text="Kihagyás", fg_color="#7f8c8d", hover_color="#95a5a6", 
                      command=self.on_skip).pack(side="left", padx=10)
        
        ctk.CTkButton(btn_frame, text="Mentés az új névvel", fg_color="#7289da", hover_color="#5b6eae", 
                      command=self.on_save).pack(side="left", padx=10)

        self.protocol("WM_DELETE_WINDOW", self.on_skip)

    def create_info_row(self, parent, label, value, text_color="silver"):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(weight="bold", size=12), width=100, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=value, text_color=text_color, anchor="w").pack(side="left", fill="x", expand=True)

    def on_save(self):
        new_name = self.name_entry.get().strip()
        if not new_name:
            messagebox.showwarning("Hiba", "A név nem lehet üres!", parent=self)
            return
        if not new_name.endswith(".mp4"):
            new_name += ".mp4"
        self.result = new_name
        self.destroy()

    def on_skip(self):
        self.result = None
        self.destroy()

class MedalRenamerV2(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("UMGKL - Medal Átnevező (Visszaállítással)")
        self.geometry("800x650")
        
        # --- IKON JAVÍTVA ITT IS ---
        # Közvetlenül a resource_path-ból töltjük be, nem ellenőrizzük az os.path.exists-et a CWD-ben
        try:
            icon_path = resource_path("icon.ico")
            self.iconbitmap(icon_path)
        except Exception:
            print("Nem sikerült betölteni az ikont.")
        
        default_json = os.path.join(os.getenv('APPDATA'), 'Medal', 'store', 'clips.json')
        
        self.label_title = ctk.CTkLabel(self, text="Medal Klip Átnevező", font=ctk.CTkFont(size=24, weight="bold"))
        self.label_title.pack(pady=15)

        # JSON
        self.frame_json = ctk.CTkFrame(self)
        self.frame_json.pack(fill="x", padx=20, pady=5)
        self.entry_json = ctk.CTkEntry(self.frame_json, placeholder_text="clips.json helye...", width=550)
        self.entry_json.insert(0, default_json if os.path.exists(default_json) else "")
        self.entry_json.pack(side="left", padx=10, pady=10)
        ctk.CTkButton(self.frame_json, text="Tallózás", width=80, command=self.browse_json).pack(side="right", padx=10)

        # Video
        self.frame_video = ctk.CTkFrame(self)
        self.frame_video.pack(fill="x", padx=20, pady=5)
        self.entry_video = ctk.CTkEntry(self.frame_video, placeholder_text="Klipek mappája...", width=550)
        self.entry_video.pack(side="left", padx=10, pady=10)
        ctk.CTkButton(self.frame_video, text="Tallózás", width=80, command=self.browse_video).pack(side="right", padx=10)

        # Log
        self.textbox = ctk.CTkTextbox(self, height=280, font=("Consolas", 12))
        self.textbox.pack(fill="both", padx=20, pady=10)
        self.log("A program készen áll.")
        self.log("Tipp: Átnevezés után használd a 'Visszanevezés' gombot, hogy a Medal ne lassuljon be.")

        # Gombok
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)

        self.btn_start = ctk.CTkButton(btn_frame, text="ÁTNEVEZÉS (Exportáláshoz)", height=50, 
                                       font=ctk.CTkFont(size=16, weight="bold"), 
                                       fg_color="#7289da", hover_color="#5b6eae",
                                       command=self.start_rename)
        self.btn_start.pack(fill="x", pady=(0, 10))

        self.btn_revert = ctk.CTkButton(btn_frame, text="VISSZANEVEZÉS (Eredeti állapot)", height=40, 
                                       font=ctk.CTkFont(size=14, weight="bold"), 
                                       fg_color="#4f545c", hover_color="#686d73", # Szürke gomb
                                       command=self.start_revert)
        self.btn_revert.pack(fill="x")

        self.filename_to_title = {}

    def log(self, msg):
        self.textbox.insert("end", msg + "\n")
        self.textbox.see("end")

    def browse_json(self):
        f = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if f: self.entry_json.delete(0, "end"); self.entry_json.insert(0, f)

    def browse_video(self):
        d = filedialog.askdirectory()
        if d: self.entry_video.delete(0, "end"); self.entry_video.insert(0, d)

    def extract_mapping_recursive(self, data):
        if isinstance(data, dict):
            path_val = data.get('localContentUrl') or data.get('FilePath') or data.get('videoFile')
            title = data.get('contentTitle')

            if title and path_val and isinstance(path_val, str):
                filename = os.path.basename(path_val.replace("\\", "/"))
                self.filename_to_title[filename] = title
            
            for k, v in data.items():
                self.extract_mapping_recursive(v)
        elif isinstance(data, list):
            for item in data:
                self.extract_mapping_recursive(item)

    # --- TÖRTÉNET KEZELÉS ---
    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return {}
        return {}

    def save_history(self, history):
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            self.log(f"[HIBA] Nem sikerült menteni a visszaállítási fájlt: {e}")

    # --- ÁTNEVEZÉS (FORWARD) ---
    def start_rename(self):
        json_path = self.entry_json.get()
        video_path = self.entry_video.get()
        
        if not os.path.exists(json_path) or not os.path.exists(video_path):
            messagebox.showerror("Hiba", "Ellenőrizd az útvonalakat!")
            return

        self.log("\n--- ÁTNEVEZÉS INDUL ---")
        self.update()

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            self.filename_to_title = {}
            self.extract_mapping_recursive(raw_data)
            
            if len(self.filename_to_title) == 0:
                self.log("HIBA: Nem találtam klipeket a JSON-ban.")
                return
            
            self.log(f"Adatbázis betöltve. Klipek keresése...")
            self.update()

            history = self.load_history() 
            renamed = 0
            skipped = 0
            
            for root, dirs, files in os.walk(video_path):
                for file in files:
                    if file.endswith(".mp4"):
                        if file in self.filename_to_title:
                            raw_title = self.filename_to_title[file]
                            clean_title = "".join([c for c in raw_title if c not in '<>:"/\\|?*']).strip()
                            if not clean_title: continue

                            new_name = f"{clean_title}.mp4"
                            old_full_path = os.path.join(root, file)
                            
                            if file == new_name:
                                skipped += 1
                                continue

                            target_full_path = os.path.join(root, new_name)
                            should_rename = True
                            
                            while os.path.exists(target_full_path):
                                dialog = ConflictDialog(self, file, new_name, root)
                                self.wait_window(dialog)
                                
                                if dialog.result:
                                    new_name = dialog.result
                                    target_full_path = os.path.join(root, new_name)
                                else:
                                    self.log(f"[SKIP] Kihagyva: {file}")
                                    should_rename = False
                                    break
                            
                            if should_rename:
                                try:
                                    os.rename(old_full_path, target_full_path)
                                    history[target_full_path] = file 
                                    self.log(f"[OK] {file} -> {new_name}")
                                    renamed += 1
                                except Exception as e:
                                    self.log(f"[HIBA] {file}: {e}")
            
            self.save_history(history)
            self.log("-" * 30)
            self.log(f"Átnevezve: {renamed} db. Visszaállítási adatok mentve.")
            messagebox.showinfo("Kész", f"{renamed} fájl átnevezve!\nNe felejtsd el visszaállítani feltöltés után.")

        except Exception as e:
            self.log(f"Kritikus hiba: {e}")

    # --- VISSZANEVEZÉS (REVERT) ---
    def start_revert(self):
        history = self.load_history()
        if not history:
            messagebox.showinfo("Infó", "Nincs visszaállítható előzmény (restore_map.json üres vagy hiányzik).")
            return

        if not messagebox.askyesno("Visszaállítás", "Biztosan visszaállítod a fájlok eredeti nevét?\n(Ez szükséges a Medal helyes működéséhez)"):
            return

        self.log("\n--- VISSZANEVEZÉS INDUL ---")
        self.update()

        reverted = 0
        missing = 0
        new_history = history.copy() 

        for current_path, original_filename in history.items():
            if os.path.exists(current_path):
                folder = os.path.dirname(current_path)
                original_full_path = os.path.join(folder, original_filename)
                
                try:
                    os.rename(current_path, original_full_path)
                    self.log(f"[VISSZA] {os.path.basename(current_path)} -> {original_filename}")
                    reverted += 1
                    del new_history[current_path]
                except Exception as e:
                    self.log(f"[HIBA] Nem sikerült visszaállítani: {current_path} ({e})")
            else:
                self.log(f"[HIÁNYZIK] Nem találom ezt a fájlt: {current_path}")
                missing += 1

        self.save_history(new_history)
        
        self.log("-" * 30)
        self.log(f"Visszaállítva: {reverted}. Hiányzik/Hiba: {missing}.")
        
        if reverted > 0:
            messagebox.showinfo("Kész", f"{reverted} fájl neve visszaállítva az eredetire!")
        else:
            messagebox.showwarning("Eredmény", "Egyetlen fájlt sem sikerült visszaállítani.")

if __name__ == "__main__":
    app = MedalRenamerV2()
    app.mainloop()