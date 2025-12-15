import os
import sys
import json
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import subprocess
from datetime import datetime
import requests
import shutil
import hashlib
from collections import Counter, defaultdict

# --- Program beállítások és segédfüggvények ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

HISTORY_FILE = "restore_map.json"
CACHE_FILE = "local_hashes.json"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

try:
    myappid = 'umgkl.medal.uploader.v4.hash_sync' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass

class ConflictDialog(ctk.CTkToplevel):
    # Ez a class változatlan, a régi átnevezéshez kell
    def __init__(self, parent, original_file, target_name, path):
        super().__init__(parent)
        self.title("Névütközés Megoldása")
        self.geometry("600x380")
        self.result = None
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except: pass
        self.attributes("-topmost", True)
        self.transient(parent)
        self.grab_set() 
        ctk.CTkLabel(self, text="⚠️ Már létezik ilyen nevű fájl!", font=ctk.CTkFont(size=18, weight="bold"), text_color="#e74c3c").pack(pady=(20, 10))
        info_frame = ctk.CTkFrame(self, fg_color="#2b2d31")
        info_frame.pack(fill="x", padx=20, pady=10)
        self.create_info_row(info_frame, "Eredeti fájl:", original_file)
        self.create_info_row(info_frame, "Mappa:", path)
        self.create_info_row(info_frame, "Erre akartuk nevezni:", target_name, text_color="#f1c40f")
        ctk.CTkLabel(self, text="Adj meg egy új nevet (kiterjesztés nélkül):").pack(pady=(10, 5))
        self.name_entry = ctk.CTkEntry(self, width=400)
        self.name_entry.insert(0, os.path.splitext(target_name)[0] + "_alt")
        self.name_entry.pack(pady=5); self.name_entry.focus_set()
        btn_frame = ctk.CTkFrame(self, fg_color="transparent"); btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Kihagyás", fg_color="#7f8c8d", hover_color="#95a5a6", command=self.on_skip).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Mentés az új névvel", fg_color="#7289da", hover_color="#5b6eae", command=self.on_save).pack(side="left", padx=10)
        self.protocol("WM_DELETE_WINDOW", self.on_skip)
    def create_info_row(self, parent, label, value, text_color="silver"):
        row = ctk.CTkFrame(parent, fg_color="transparent"); row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(weight="bold", size=12), width=100, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=value, text_color=text_color, anchor="w").pack(side="left", fill="x", expand=True)
    def on_save(self):
        new_name = self.name_entry.get().strip()
        if not new_name: messagebox.showwarning("Hiba", "A név nem lehet üres!", parent=self); return
        self.result = new_name if new_name.endswith(".mp4") else new_name + ".mp4"; self.destroy()
    def on_skip(self): self.result = None; self.destroy()

class MedalUploaderTool(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("UMGKL - Medal Klip Előkészítő v4 (Hash alapú szinkronizálás)")
        self.geometry("800x850")
        
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except: pass
        
        self.label_title = ctk.CTkLabel(self, text="Medal Klip Előkészítő", font=ctk.CTkFont(size=24, weight="bold"))
        self.label_title.pack(pady=15)
        
        # GUI elemek
        default_json = os.path.join(os.getenv('APPDATA'), 'Medal', 'store', 'clips.json')
        self.create_path_entry("1. Medal Adatbázis (clips.json):", "entry_json", self.browse_json, default_json)
        self.create_path_entry("2. Medal Klipek Mappája:", "entry_video", self.browse_video)
        self.create_path_entry("3. Weboldal Címe (URL):", "entry_server", None, "http://localhost:3000")
        self.create_path_entry("4. Célmappa (ide kerülnek a feltöltendők):", "entry_output", self.browse_output)
        
        self.btn_prepare = ctk.CTkButton(self, text="ÚJ KLIPPEK ELŐKÉSZÍTÉSE FELTÖLTÉSHEZ", height=50, 
                                       font=ctk.CTkFont(size=16, weight="bold"), 
                                       fg_color="#27ae60", hover_color="#2ecc71",
                                       command=self.prepare_new_uploads)
        self.btn_prepare.pack(fill="x", padx=20, pady=(20, 10))
        
        self.textbox_label = ctk.CTkLabel(self, text="Folyamatnapló (Konzol)", font=ctk.CTkFont(size=14))
        self.textbox_label.pack(pady=(10, 2))
        self.textbox = ctk.CTkTextbox(self, height=200, font=("Consolas", 12))
        self.textbox.pack(fill="both", padx=20, pady=5)
        
        # Régi, manuális gombok
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)
        self.btn_start = ctk.CTkButton(btn_frame, text="Csak átnevezés (régi módszer)", command=self.start_rename)
        self.btn_start.pack(side="left", expand=True, padx=5)
        self.btn_revert = ctk.CTkButton(btn_frame, text="Visszanevezés", fg_color="#4f545c", hover_color="#686d73", command=self.start_revert)
        self.btn_revert.pack(side="left", expand=True, padx=5)

        self.filename_to_title = {}
        self.log("Program indítva. Add meg az elérési utakat, majd kattints a zöld gombra.")

    def create_path_entry(self, label_text, entry_attr, browse_cmd, default_text=""):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame, text=label_text, width=250, anchor="w").pack(side="left", padx=10)
        entry = ctk.CTkEntry(frame, placeholder_text="...")
        entry.pack(side="left", fill="x", expand=True)
        if default_text: entry.insert(0, default_text if os.path.exists(default_text) else "")
        setattr(self, entry_attr, entry)
        if browse_cmd:
            ctk.CTkButton(frame, text="Tallózás", width=80, command=browse_cmd).pack(side="right", padx=10)

    def log(self, msg):
        self.textbox.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.textbox.see("end")
        self.update_idletasks()

    def browse_json(self): self.browse_file(self.entry_json, [("JSON files", "*.json")])
    def browse_video(self): self.browse_dir(self.entry_video)
    def browse_output(self): self.browse_dir(self.entry_output)
    def browse_file(self, entry, filetypes): f = filedialog.askopenfilename(filetypes=filetypes); entry.delete(0, "end"); entry.insert(0, f)
    def browse_dir(self, entry): d = filedialog.askdirectory(); entry.delete(0, "end"); entry.insert(0, d)
    
    def calculate_file_hash(self, filepath):
        sha1 = hashlib.sha1()
        try:
            with open(filepath, 'rb') as f:
                # Csak az első 5 MB-ot olvassuk be a sebesség miatt
                buffer = f.read(5 * 1024 * 1024) 
                sha1.update(buffer)
            return sha1.hexdigest()
        except Exception as e:
            self.log(f"HIBA: Nem sikerült olvasni a fájlt a hash-eléshez: {filepath} ({e})")
            return None

    def embed_creation_date(self, video_path):
        try:
            creation_timestamp = os.path.getctime(video_path)
            creation_datetime = datetime.fromtimestamp(creation_timestamp)
            formatted_date = creation_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            self.log(f"  -> Metaadat javítása, dátum: {creation_datetime.strftime('%Y.%m.%d %H:%M')}")
            temp_path = video_path + ".tmp.mp4"
            command = ['ffmpeg', '-i', video_path, '-c', 'copy', '-metadata', f'creation_time={formatted_date}', '-y', temp_path]
            
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            
            if result.returncode == 0:
                os.replace(temp_path, video_path)
                return True
            else:
                self.log(f"  -> META HIBA: ffmpeg hiba:\n{result.stderr.strip()}")
                if os.path.exists(temp_path): os.remove(temp_path)
        except FileNotFoundError:
            self.log("[HIBA] Az 'ffmpeg.exe' nem található! A metaadatok javítása kihagyva.")
            messagebox.showerror("FFmpeg Hiba", "Az 'ffmpeg.exe' nem található!\nA program nem tudja javítani a dátumokat e nélkül.")
            return 'ffmpeg_not_found'
        except Exception as e:
            self.log(f"  -> META HIBA: {e}")
        return False

    def prepare_new_uploads(self):
        # 1. Bemeneti adatok ellenőrzése
        json_path, video_path, server_url, output_path = self.entry_json.get(), self.entry_video.get(), self.entry_server.get().strip(), self.entry_output.get()
        if not all([json_path, video_path, server_url, output_path]):
            messagebox.showerror("Hiba", "Minden mezőt ki kell tölteni!"); return
        
        self.log("\n--- ÚJ KLIPPEK SZINKRONIZÁLÁSA INDUL (HASH ALAPON) ---")

        try:
            # 2. Helyi klipek elemzése és hash-elése (cache használatával)
            self.log("Helyi klipek elemzése és ujjlenyomatok (hash) készítése...")
            cache = {}
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f: cache = json.load(f)

            with open(json_path, 'r', encoding='utf-8') as f:
                raw_clips = {}; self.extract_mapping_recursive(json.load(f), raw_clips)
            
            local_hashes = {}
            needs_update = False
            
            for i, (original_name, title) in enumerate(raw_clips.items()):
                self.log(f"  Elemzés: {i+1}/{len(raw_clips)} - {original_name}")
                file_path = os.path.join(video_path, original_name)
                if not os.path.exists(file_path): continue

                mtime = os.path.getmtime(file_path)
                
                # Cache ellenőrzés
                if original_name in cache and cache[original_name].get('mtime') == mtime:
                    file_hash = cache[original_name]['hash']
                else:
                    file_hash = self.calculate_file_hash(file_path)
                    if file_hash:
                        cache[original_name] = {'hash': file_hash, 'mtime': mtime}
                        needs_update = True
                
                if file_hash:
                    local_hashes[file_hash] = {'original_name': original_name, 'title': title}

            if needs_update:
                with open(CACHE_FILE, 'w') as f: json.dump(cache, f, indent=2)
            self.log(f"Helyi klipek elemzése kész. {len(local_hashes)} érvényes klip azonosítva.")

            # 3. Szerveren lévő hash-ek lekérése
            self.log("Kapcsolódás a szerverhez...")
            api_endpoint = f"{server_url.rstrip('/')}/api/videos/get-uploaded-hashes"
            response = requests.get(api_endpoint, timeout=10)
            response.raise_for_status()
            server_hashes = set(response.json())
            self.log(f"Szerveren lévő klipek (hash) száma: {len(server_hashes)}.")

            # 4. Hiányzó klipek meghatározása
            files_to_process = []
            for file_hash, clip_info in local_hashes.items():
                if file_hash not in server_hashes:
                    files_to_process.append(clip_info)
            
            if not files_to_process:
                self.log("\nNem található új, feltöltésre váró klip.")
                messagebox.showinfo("Naprakész", "Minden helyi kliped már fent van a weboldalon!"); return

            # 5. Előkészítés: másolás, átnevezés, metaadat javítás
            self.log(f"\nElőkészítés: {len(files_to_process)} új klip másolása és javítása...")
            copied_count = 0
            for clip_info in files_to_process:
                original_name, title = clip_info['original_name'], clip_info['title']
                source_path = os.path.join(video_path, original_name)
                
                clean_title = "".join([c for c in title if c not in '<>:"/\\|?*']).strip()
                if not clean_title: clean_title = os.path.splitext(original_name)[0]
                target_name = f"{clean_title}.mp4"
                target_path = os.path.join(output_path, target_name)

                counter = 1
                while os.path.exists(target_path):
                    target_path = os.path.join(output_path, f"{clean_title}_{counter}.mp4"); counter += 1
                
                try:
                    shutil.copy2(source_path, target_path)
                    self.log(f"  -> ÁTMÁSOLVA: {original_name} -> {os.path.basename(target_path)}")
                    
                    if self.embed_creation_date(target_path) == 'ffmpeg_not_found': break
                    copied_count += 1
                except Exception as e:
                    self.log(f"  -> HIBA a másolás során ({original_name}): {e}")

            self.log("-" * 30)
            self.log(f"KÉSZ! {copied_count} új klip előkészítve a '{output_path}' mappába.")
            messagebox.showinfo("Siker", f"{copied_count} új klip átmásolva és előkészítve a feltöltéshez!")

        except requests.exceptions.RequestException as e:
            self.log(f"SZERVER HIBA: Nem sikerült elérni a weboldalt. Ellenőrizd az URL-t és a szerver állapotát."); messagebox.showerror("Szerver Hiba", f"Nem sikerült kapcsolódni a szerverhez:\n{e}")
        except Exception as e:
            self.log(f"Kritikus hiba: {e}"); messagebox.showerror("Hiba", f"Váratlan hiba történt:\n{e}")

    # A régi függvények itt kezdődnek (változatlanul)
    def extract_mapping_recursive(self, data, result_dict):
        if isinstance(data, dict):
            path_val = data.get('localContentUrl') or data.get('FilePath') or data.get('videoFile')
            title = data.get('contentTitle')
            if title and path_val and isinstance(path_val, str):
                filename = os.path.basename(path_val.replace("\\", "/")); result_dict[filename] = title
            for v in data.values(): self.extract_mapping_recursive(v, result_dict)
        elif isinstance(data, list):
            for item in data: self.extract_mapping_recursive(item, result_dict)
            
    def start_rename(self): pass # Itt van a régi átnevező kódod
    def start_revert(self): pass # Itt van a régi visszanevező kódod

if __name__ == "__main__":
    app = MedalUploaderTool()
    app.mainloop()
