import os
import sys
import json
import ctypes
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import subprocess
from datetime import datetime
import requests
import concurrent.futures
import hashlib
from collections import Counter, defaultdict

# --- Program beállítások és segédfüggvények ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

HISTORY_FILE = "restore_map.json"
CACHE_FILE = "local_hashes.json"
CONFIG_FILE = "config.json"

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
        self.title("UMKGL - Medal Klip Előkészítő v4 (Hash alapú szinkronizálás)")
        self.geometry("800x800")

        try:
            self.iconbitmap(resource_path("icon.ico"))
        except: pass

        self.label_title = ctk.CTkLabel(self, text="Medal Klip Előkészítő", font=ctk.CTkFont(size=24, weight="bold"))
        self.label_title.pack(pady=15)

        self.config_data = self.load_config()

        # GUI elemek
        self.create_path_entry("1. Medal Adatbázis (clips.json):", "entry_json", self.browse_json, self.config_data.get("json_path", ""))
        self.create_path_entry("2. Medal Klipek Mappája:", "entry_video", self.browse_video, self.config_data.get("video_path", ""))
        self.create_path_entry("3. Weboldal Címe (URL):", "entry_server", None, self.config_data.get("server_url", ""))
        self.create_path_entry("4. Célmappa (ide kerülnek a feltöltendők):", "entry_output", self.browse_output, self.config_data.get("output_path", ""))

        self.btn_preview = ctk.CTkButton(self, text="ELŐNÉZET / TESZT", height=50,
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       fg_color="#5b6eae", hover_color="#7289da",
                                       command=lambda: self.start_processing_thread(dry_run=True))
        self.btn_preview.pack(fill="x", padx=20, pady=(20, 10))

        self.btn_prepare = ctk.CTkButton(self, text="ÚJ KLIPPEK EXPORTÁLÁSA", height=50,
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       fg_color="#27ae60", hover_color="#2ecc71",
                                       command=lambda: self.start_processing_thread(dry_run=False))
        self.btn_prepare.pack(fill="x", padx=20, pady=(0, 10))

        self.textbox_label = ctk.CTkLabel(self, text="Folyamatnapló (Konzol)", font=ctk.CTkFont(size=14))
        self.textbox_label.pack(pady=(10, 2))
        self.textbox = ctk.CTkTextbox(self, height=200, font=("Consolas", 12))
        self.textbox.pack(fill="both", padx=20, pady=5)

        self.progressbar = ctk.CTkProgressBar(self, progress_color="#27ae60")
        self.progressbar.pack(fill="x", padx=20, pady=(0, 10))
        self.progressbar.set(0)

        self.filename_to_title = {}
        self.log_counter = 0
        self.path_lock = threading.Lock()
        self.log("Program indítva. Add meg az elérési utakat, majd kattints a zöld gombra.")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_path_entry(self, label_text, entry_attr, browse_cmd, default_text=""):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame, text=label_text, width=250, anchor="w").pack(side="left", padx=10)
        entry = ctk.CTkEntry(frame, placeholder_text="...")
        entry.pack(side="left", fill="x", expand=True)
        if default_text is not None:
            entry.insert(0, default_text)
        setattr(self, entry_attr, entry)
        if browse_cmd:
            ctk.CTkButton(frame, text="Tallózás", width=80, command=browse_cmd).pack(side="right", padx=10)

    def get_default_config(self):
        appdata = os.getenv('APPDATA') or ""
        default_json = ""
        if appdata:
            candidate = os.path.join(appdata, 'Medal', 'store', 'clips.json')
            if os.path.exists(candidate):
                default_json = candidate

        desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
        default_output = os.path.join(desktop_path, 'Export_Klippek')

        return {
            "json_path": default_json,
            "video_path": "",
            "server_url": "http://api.umkgl.online:3000",
            "output_path": default_output,
        }

    def load_config(self):
        defaults = self.get_default_config()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                defaults.update({
                    "json_path": data.get("json_path", defaults["json_path"]),
                    "video_path": data.get("video_path", defaults["video_path"]),
                    "server_url": data.get("server_url", defaults["server_url"]),
                    "output_path": data.get("output_path", defaults["output_path"]),
                })
            except Exception:
                pass
        return defaults

    def save_config(self):
        data = {
            "json_path": self.entry_json.get().strip(),
            "video_path": self.entry_video.get().strip(),
            "server_url": self.entry_server.get().strip(),
            "output_path": self.entry_output.get().strip(),
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"Nem sikerült menteni a beállításokat: {e}")

    def format_size(self, size_bytes):
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(size_bytes)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.2f} {unit}"
            size /= 1024

    def sanitize_title(self, title, fallback_name):
        clean_title = "".join([c for c in title if c not in '<>:"/\\|?*']).strip()
        if not clean_title:
            clean_title = os.path.splitext(fallback_name)[0]
        return f"{clean_title}.mp4"

    def set_buttons_state(self, state):
        self.after(0, lambda: (self.btn_preview.configure(state=state), self.btn_prepare.configure(state=state)))

    def start_processing_thread(self, dry_run=False):
        self.set_buttons_state("disabled")
        threading.Thread(target=self.run_sync, args=(dry_run,), daemon=True).start()

    def log(self, msg, force_update=False):
        def append_message():
            self.log_counter += 1
            self.textbox.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            if force_update or self.log_counter % 10 == 0:
                self.textbox.see("end")
        self.after(0, append_message)

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

    def process_single_clip(self, clip_info, video_path, output_path):
        original_name, title = clip_info['original_name'], clip_info['title']
        source_path = clip_info['source_path']
        target_name = self.sanitize_title(title, original_name)

        relative_folder = os.path.relpath(os.path.dirname(source_path), video_path)
        target_dir = os.path.join(output_path, relative_folder)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, target_name)

        with self.path_lock:
            counter = 1
            while os.path.exists(target_path):
                name, ext = os.path.splitext(target_name)
                target_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
                counter += 1

        try:
            creation_timestamp = os.path.getmtime(source_path)
            creation_datetime = datetime.fromtimestamp(creation_timestamp)
            formatted_date = creation_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')

            self.log(f"  -> Export: {original_name} -> {os.path.basename(target_path)}")
            command = [
                'ffmpeg', '-i', source_path, '-c', 'copy',
                '-metadata', f'creation_time={formatted_date}',
                '-y', target_path
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            if result.returncode == 0:
                return True, f"  -> KÉSZ: {os.path.basename(target_path)} (dátum: {creation_datetime.strftime('%Y.%m.%d %H:%M')})"
            else:
                return False, f"  -> META HIBA: ffmpeg hiba ({original_name}):\n{result.stderr.strip()}"
        except FileNotFoundError:
            return False, "[HIBA] Az 'ffmpeg.exe' nem található! A metaadatok javítása kihagyva."
        except Exception as e:
            return False, f"  -> HIBA a feldolgozás során ({original_name}): {e}"

    def run_sync(self, dry_run=False):
        try:
            json_path = self.entry_json.get().strip()
            video_path = self.entry_video.get().strip()
            server_url = self.entry_server.get().strip()
            output_path = self.entry_output.get().strip()

            self.progressbar.set(0)

            if not all([json_path, video_path, server_url, output_path]):
                messagebox.showerror("Hiba", "Minden mezőt ki kell tölteni!")
                return

            header = "ELŐNÉZET / TESZT" if dry_run else "ÚJ KLIPPEK EXPORTÁLÁSA"
            self.log(f"\n--- {header} (HASH ALAPÚ SZINKRONIZÁLÁS) ---", force_update=True)

            cache = {}
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f:
                    cache = json.load(f)

            # Fájlok rekurzív feltérképezése az almappákkal együtt
            file_map = {}
            mp4_count = 0
            for root, _, files in os.walk(video_path):
                for file in files:
                    if file.lower().endswith('.mp4'):
                        mp4_count += 1
                        abs_path = os.path.abspath(os.path.join(root, file))
                        file_map.setdefault(file.lower(), abs_path)

            self.log(f"Találtam {mp4_count} fájlt a mapparendszerben.")

            with open(json_path, 'r', encoding='utf-8') as f:
                raw_clips = {}
                self.extract_mapping_recursive(json.load(f), raw_clips)

            local_hashes = {}
            needs_update = False
            missing_files = []

            missing_debug_logged = 0

            total_items = len(raw_clips)

            for i, (original_name, title) in enumerate(raw_clips.items()):
                self.log(f"  Elemzés: {i + 1}/{len(raw_clips)} - {original_name}")
                file_path = file_map.get(original_name.lower())

                if (not file_path) or (not os.path.exists(file_path)):
                    clean_filename = self.sanitize_title(title, original_name).lower()
                    file_path = file_map.get(clean_filename)

                if not file_path or not os.path.exists(file_path):
                    missing_files.append(original_name)
                    if missing_debug_logged < 3:
                        self.log(f"[DEBUG] Nem található a térképben: '{original_name}'")
                        missing_debug_logged += 1
                    continue

                mtime = os.path.getmtime(file_path)

                if original_name in cache and cache[original_name].get('mtime') == mtime:
                    file_hash = cache[original_name]['hash']
                else:
                    file_hash = self.calculate_file_hash(file_path)
                    if file_hash:
                        cache[original_name] = {'hash': file_hash, 'mtime': mtime}
                        needs_update = True

                if file_hash:
                    local_hashes[file_hash] = {
                        'original_name': original_name,
                        'title': title,
                        'size': os.path.getsize(file_path),
                        'source_path': file_path
                    }

                if total_items:
                    self.progressbar.set((i + 1) / total_items)

            if needs_update and not dry_run:
                with open(CACHE_FILE, 'w') as f:
                    json.dump(cache, f, indent=2)

            self.log(f"Helyi klipek elemzése kész. {len(local_hashes)} érvényes klip azonosítva.")
            self.progressbar.set(0)
            if missing_files:
                self.log(f"Figyelem: {len(missing_files)} fájl nem található a klipek mappájában.")

            self.log("Kapcsolódás a szerverhez...")
            api_endpoint = f"{server_url.rstrip('/')}/api/videos/get-uploaded-hashes"
            response = requests.get(api_endpoint, timeout=10)
            response.raise_for_status()
            server_hashes = set(response.json())
            self.log(f"Szerveren lévő klipek (hash) száma: {len(server_hashes)}.")

            files_to_process = []
            total_missing_size = 0
            for file_hash, clip_info in local_hashes.items():
                if file_hash not in server_hashes:
                    files_to_process.append(clip_info)
                    total_missing_size += clip_info['size']

            self.log(f"Helyi klipek száma: {len(local_hashes)} db")
            self.log(f"Ebből új, feltöltendő: {len(files_to_process)} db")
            self.log(f"A várható export mérete: {self.format_size(total_missing_size)}")

            if dry_run:
                if not files_to_process:
                    messagebox.showinfo("Naprakész", "Minden helyi kliped már fent van a weboldalon!")
                else:
                    messagebox.showinfo("Előnézet kész", "A naplóban láthatod a várható export részleteit.")
                self.save_config()
                return

            if not files_to_process:
                self.log("\nNem található új, feltöltésre váró klip.")
                messagebox.showinfo("Naprakész", "Minden helyi kliped már fent van a weboldalon!")
                self.save_config()
                return

            os.makedirs(output_path, exist_ok=True)
            self.log(f"\nExportálás: {len(files_to_process)} új klip másolása és javítása...")
            copied_count = 0
            processed_exports = 0
            total_exports = len(files_to_process)

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_clip = {
                    executor.submit(self.process_single_clip, clip_info, video_path, output_path): clip_info
                    for clip_info in files_to_process
                }

                for future in concurrent.futures.as_completed(future_to_clip):
                    success, message = future.result()
                    if message:
                        self.log(message)
                    if success:
                        copied_count += 1

                    processed_exports += 1
                    if total_exports:
                        self.progressbar.set(processed_exports / total_exports)

            self.log("-" * 30)
            self.log(f"KÉSZ! {copied_count} új klip előkészítve a '{output_path}' mappába.")
            messagebox.showinfo("Siker", f"{copied_count} új klip átmásolva és előkészítve a feltöltéshez!")
            self.save_config()

        except requests.exceptions.RequestException as e:
            self.log("SZERVER HIBA: Nem sikerült elérni a weboldalt. Ellenőrizd az URL-t és a szerver állapotát.")
            messagebox.showerror("Szerver Hiba", f"Nem sikerült kapcsolódni a szerverhez:\n{e}")
        except Exception as e:
            self.log(f"Kritikus hiba: {e}")
            messagebox.showerror("Hiba", f"Váratlan hiba történt:\n{e}")
        finally:
            self.set_buttons_state("normal")

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

    def on_close(self):
        self.save_config()
        self.destroy()

if __name__ == "__main__":
    app = MedalUploaderTool()
    app.mainloop()
