import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from engine import CPU  # engine.py içindeki CPU sınıfını çağırıyoruz

class RISC16GUI:
    def __init__(self, root):
        self.cpu = CPU()
        self.root = root
        self.root.title("RISC-16 Pipeline Simulator")
        self.root.geometry("1000x750")
        self.root.configure(bg="#d4d0c8") # Klasik Windows Grisi
        # Klasik Windows Renkleri
        BG_COLOR = "#d4d0c8"      # Klasik pencere grisi
        FRAME_BG = "#ffffff"      # Beyaz giriş alanları
        TEXT_COLOR = "#000000"    # Siyah metin
        BTN_BG = "#d4d0c8"        # Buton grisi
        HIGHLIGHT = "#808080"     # Koyu gri çerçeve

        self.setup_ui()

        # Otomatik ilerleme değişkenleri
        self.is_running = False
        self.run_speed = 500

    def setup_ui(self):
        # Genel arka plan rengini ayarla
        self.root.configure(bg="#d4d0c8")
        
        # Aşama açıklamaları sözlüğü
        self.stage_info = {
            "IF": "Instruction Fetch: Komut bellekten getirilir.",
            "ID": "Instruction Decode: Komut çözülür ve hazard kontrolü yapılır.",
            "EX": "Execute: Aritmetik ve mantıksal işlemler yapılır.",
            "MEM": "Memory: RAM okuma/yazma işlemleri yapılır.",
            "WB": "Write Back: Sonuç register'a kaydedilir."
        }

        # --- 1. PIPELINE GÖRÜNÜMÜ ---
        self.pipeline_frame = tk.LabelFrame(self.root, text="Pipeline Stages", fg="black", bg="#d4d0c8", font=("MS Sans Serif", 9, "bold"), bd=2, relief="groove")
        self.pipeline_frame.pack(fill="x", padx=10, pady=5)

        self.pipeline_vars = {}
        stages = ["IF", "ID", "EX", "MEM", "WB"]
        for stage in stages:
            # 3D Efekti için relief="sunken"
            frame = tk.Frame(self.pipeline_frame, bg="#d4d0c8", bd=2, relief="sunken", cursor="hand2")
            frame.pack(side="left", expand=True, fill="both", padx=3, pady=5)
            
            title = tk.Label(frame, text=stage, fg="blue", bg="#d4d0c8", font=("MS Sans Serif", 8, "bold"))
            title.pack()
            
            label = tk.Label(frame, text="Empty", fg="black", bg="white", font=("Courier", 10), wraplength=140, bd=1, relief="solid")
            label.pack(pady=5, padx=5, fill="both", expand=True)
            self.pipeline_vars[stage] = (label, frame)

            for widget in (frame, title, label):
                widget.bind("<Button-1>", lambda e, s=stage: self.show_stage_info(s))

        # --- 2. ORTA BÖLÜM ---
        middle_frame = tk.Frame(self.root, bg="#d4d0c8")
        middle_frame.pack(fill="both", expand=True, padx=10)

        # Kod Giriş Alanı (Beyaz zemin, siyah yazı)
        editor_frame = tk.LabelFrame(middle_frame, text="Assembly Source", bg="#d4d0c8", bd=2, relief="groove")
        editor_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.code_editor = scrolledtext.ScrolledText(editor_frame, font=("Courier New", 11), bg="white", fg="black", insertbackground="black")
        self.code_editor.pack(fill="both", expand=True, padx=2, pady=2)

        # Register ve Memory Paneli
        right_panel = tk.Frame(middle_frame, bg="#d4d0c8")
        right_panel.pack(side="right", fill="y")

        # Registers
        reg_frame = tk.LabelFrame(right_panel, text="Registers", bg="#d4d0c8", bd=2, relief="groove")
        reg_frame.pack(fill="x", padx=5, pady=2)
        self.reg_labels = {}
        for i in range(8):
            r_name = f"R{i}"
            f = tk.Frame(reg_frame, bg="#d4d0c8")
            f.pack(fill="x", pady=1, padx=5)
            tk.Label(f, text=f"{r_name}:", fg="black", bg="#d4d0c8", font=("MS Sans Serif", 8, "bold")).pack(side="left")
            label = tk.Label(f, text="0", fg="black", bg="white", font=("Courier New", 10, "bold"), width=10, bd=1, relief="sunken")
            label.pack(side="right")
            self.reg_labels[r_name] = label

        # Memory (Treeview stili)
        self.mem_frame = tk.LabelFrame(right_panel, text="Memory (RAM)", bg="#d4d0c8", bd=2, relief="groove")
        self.mem_frame.pack(fill="both", expand=True, padx=5, pady=2)
        
        style = ttk.Style()
        style.theme_use("clam") # Klasik görünüme en yakın tema
        self.mem_tree = ttk.Treeview(self.mem_frame, columns=("Addr", "Value"), show="headings", height=8)
        self.mem_tree.heading("Addr", text="Addr")
        self.mem_tree.heading("Value", text="Data")
        self.mem_tree.column("Addr", width=50)
        self.mem_tree.column("Value", width=100)
        self.mem_tree.pack(side="left", fill="both", expand=True)

        # --- 3. ALT BÖLÜM ---
        bottom_frame = tk.Frame(self.root, bg="#d4d0c8", bd=2, relief="raised", pady=5)
        bottom_frame.pack(fill="x", padx=10, pady=10)

        # Klasik Buton Stili
        btn_style = {"font": ("MS Sans Serif", 8), "bg": "#d4d0c8", "relief": "raised", "bd": 2}
        
        tk.Button(bottom_frame, text="Load Program", command=self.load_code, **btn_style).pack(side="left", padx=5)
        tk.Button(bottom_frame, text="Step Cycle", command=self.step_cycle, **btn_style).pack(side="left", padx=5)
        
        self.run_btn = tk.Button(bottom_frame, text="Run", command=self.toggle_run, **btn_style, width=8)
        self.run_btn.pack(side="left", padx=5)

        self.pause_btn = tk.Button(bottom_frame, text="Pause", command=self.pause_run, **btn_style, width=8)
        self.pause_btn.pack(side="left", padx=5)

        tk.Label(bottom_frame, text="Speed:", bg="#d4d0c8").pack(side="left", padx=5)
        self.speed_scale = tk.Scale(bottom_frame, from_=50, to=2000, orient="horizontal", command=self.update_speed, bg="#d4d0c8", length=100)
        self.speed_scale.set(500)
        self.speed_scale.pack(side="left", padx=5)

        tk.Button(bottom_frame, text="Reset", command=self.reset_simulator, **btn_style).pack(side="left", padx=5)

        self.perf_label = tk.Label(bottom_frame, text="CPI: 0.0 | IPC: 0.0", bg="#d4d0c8", font=("MS Sans Serif", 8, "bold"))
        self.perf_label.pack(side="right", padx=10)

    # --- Bilgi Penceresi Metodu ---
    def show_stage_info(self, stage):
        info = self.stage_info.get(stage, "Bilgi yok.")
        messagebox.showinfo(f"{stage} Stage", info)

    # --- YENİ FONKSİYONLAR ---
    def update_speed(self, val):
        self.run_speed = int(val)

    def toggle_run(self):
        if not self.is_running:
            self.is_running = True
            self.run_btn.config(state="disabled")
            self.auto_step()

    def pause_run(self):
        self.is_running = False
        self.run_btn.config(state="normal")

    def auto_step(self):
        if self.is_running:
            if not self.cpu.is_finished():
                self.cpu.step()
                self.update_ui()
                self.root.after(self.run_speed, self.auto_step)
            else:
                self.is_running = False
                self.run_btn.config(state="normal")
                messagebox.showinfo("Done", "Program execution finished.")

    # --- MEVCUT FONKSİYONLAR ---
    def load_code(self):
        raw_code = self.code_editor.get("1.0", tk.END)
        if not raw_code.strip():
            messagebox.showwarning("Warning", "Please enter some code!")
            return
        self.cpu.load_program(raw_code)
        self.update_ui()
        messagebox.showinfo("Success", "Program loaded into Instruction Memory.")

    def step_cycle(self):
        if self.cpu.is_finished():
            messagebox.showinfo("Done", "Program execution finished.")
            return
        self.cpu.step()
        self.update_ui()

    def reset_simulator(self):
        self.is_running = False
        self.run_btn.config(state="normal")
        self.cpu.reset()
        self.update_ui()

    def update_ui(self):
        # 1. Pipeline Güncelle
        for stage, content in self.cpu.pipeline.items():
            label, frame = self.pipeline_vars[stage]
            if isinstance(content, dict):
                display_text = content["text"]
                is_stall = "Stall" in display_text or "STALL" in display_text
                is_flush = "Flush" in display_text or "NOP" in display_text
            else:
                display_text = str(content)
                is_stall = "Stall" in display_text or "STALL" in display_text
                is_flush = "Flush" in display_text or "NOP" in display_text

            label.config(text=display_text)
            
            if is_stall:
                frame.config(highlightbackground="#800000" , bg="#bc7c7c")
                label.config(fg="#800000" , bg="#bc7c7c")
            elif is_flush and display_text != "Empty":
                frame.config(highlightbackground="#800000" , bg="#d6d69b")
                label.config(fg="#800000" , bg="#d6d69b")
            elif display_text == "Empty":
                frame.config(highlightbackground="#d4d0c8" , bg="#d4d0c8")
                label.config(fg="#d4d0c8" , bg="#d4d0c8")
            else:
                frame.config(highlightbackground="white" , bg="white")
                label.config(fg="black" , bg="white")

        # 2. Register Güncelle
        for r_name, label in self.reg_labels.items():
            label.config(text=str(self.cpu.registers[r_name]))

        # 3. Performans Güncelle
        metrics = self.cpu.get_performance_metrics()
        self.perf_label.config(text=f"CPI: {metrics['CPI']} | IPC: {metrics['IPC']} | Cycles: {metrics['Total Cycles']} | Stalls: {metrics['Stall Count']}")

        # 4. Bellek Tablosu Güncelle
        for i in self.mem_tree.get_children():
            self.mem_tree.delete(i)
        mem_data = self.cpu.get_memory_dump(limit=32)
        for addr, val in mem_data.items():
            hex_val = f"0x{val:04X}"
            self.mem_tree.insert("", "end", values=(f"{addr:03d}", f"{hex_val} ({val})"))

if __name__ == "__main__":
    root = tk.Tk()
    app = RISC16GUI(root)
    root.mainloop()