class CPU:
    def __init__(self):
        self.registers = {f"R{i}": 0 for i in range(8)}
        self.memory = [0] * 1024
        self.instruction_memory = [""] * 512
        self.executed_instr_count = 0
        self.pc = 0
        self.labels = {}
        self.pipeline = {
            "IF": "Empty",
            "ID": "Empty",
            "EX": "Empty",
            "MEM": "Empty",
            "WB": "Empty"
        }
        self.total_cycles = 0
        self.stall_count = 0
        self.hazards = []

    def to_signed_16(self, val):
        val &= 0xFFFF
        return val - 0x10000 if val > 0x7FFF else val

    def sign_extend_imm(self, val, bits):
        if val & (1 << (bits - 1)):
            return val - (1 << bits)
        return val

    def load_program(self, raw_code):
        self.reset()
        lines = raw_code.strip().split("\n")
        temp_instructions = []
        for line in lines:
            line = line.split("#")[0].strip()
            if not line: continue
            if ":" in line:
                label_part, instr_part = line.split(":", 1)
                self.labels[label_part.strip()] = len(temp_instructions)
                line = instr_part.strip()
            if line:
                temp_instructions.append(line)
        for i, instr in enumerate(temp_instructions):
            if i < 512:
                self.instruction_memory[i] = instr

    def reset(self):
        self.registers = {f"R{i}": 0 for i in range(8)}
        self.pc = 0 
        self.pipeline = {s: "Empty" for s in self.pipeline}
        self.total_cycles = 0
        self.stall_count = 0
        self.executed_instr_count = 0
        self.hazards = []

    def is_finished(self):
        for stage_content in self.pipeline.values():
            content_str = str(stage_content["text"]) if isinstance(stage_content, dict) else str(stage_content)
            if content_str != "Empty" and "NOP" not in content_str and "Flush" not in content_str:
                return False
        if self.pc < 512 and self.instruction_memory[self.pc] != "":
            return False
        return True

    def step(self):
        if self.is_finished():
            return False
        
        # 1. WB aşamasındaki komutu yürüt
        wb_content = self.pipeline["WB"]
        jump_occurred = False
        
        if wb_content != "Empty" and "NOP" not in str(wb_content):
            old_pc = self.pc
            self.execute(wb_content)
            
            # Eğer PC değiştiyse (Jump/Branch olduysa) 
            # Pipeline zaten execute içinde flush_pipeline() ile temizlendi.
            if self.pc != old_pc:
                jump_occurred = True

        # Eğer zıplama olduysa, bu cycle'da kaydırma yapma, direkt bitir.
        if jump_occurred:
            self.total_cycles += 1
            return True

        # 2. Hazard Kontrolü
        hazard_result = self.detect_hazards()

        # --- STALL DURUMU ---
        if hazard_result == "STALL":
            self.stall_count += 1
            self.total_cycles += 1
            self.pipeline["WB"] = self.pipeline["MEM"]
            self.pipeline["MEM"] = self.pipeline["EX"]
            
            id_pkg = self.pipeline["ID"]
            waiting_instr = id_pkg["text"] if isinstance(id_pkg, dict) else str(id_pkg)
            self.pipeline["EX"] = {"text": f"STALL (Wait: {waiting_instr})", "addr": -1}
            return True

        # --- NORMAL AKIŞ (SHIFT) ---
        self.total_cycles += 1
        
        self.pipeline["WB"] = self.pipeline["MEM"]
        self.pipeline["MEM"] = self.pipeline["EX"]
        self.pipeline["EX"] = self.pipeline["ID"]
        self.pipeline["ID"] = self.pipeline["IF"]

        # 3. FETCH
        if self.pc < 512 and self.instruction_memory[self.pc]:
            instr_text = self.instruction_memory[self.pc]
            self.pipeline["IF"] = {"text": instr_text, "addr": self.pc}
            self.pc += 1
        else:
            self.pipeline["IF"] = "Empty"
        
        return True

    def detect_hazards(self):
        id_pkg = self.pipeline["ID"]
        ex_pkg = self.pipeline["EX"]
        mem_pkg = self.pipeline["MEM"]

        if id_pkg == "Empty" or "NOP" in str(id_pkg) or "STALL" in str(id_pkg):
            return False

        instr_text = id_pkg["text"] if isinstance(id_pkg, dict) else str(id_pkg)
        clean_id = instr_text.replace(",", " ").replace("(", " ").replace(")", " ")
        parts = clean_id.split()
        if len(parts) < 2: return False

        op = parts[0].lower()
        sources = []
        if op in ["add", "sub", "and", "or", "slt"]: sources = [parts[2], parts[3]]
        elif op in ["beq", "bne"]: sources = [parts[1], parts[2]]
        elif op in ["addi", "lw", "sw"]: sources = [parts[2]]
        elif op == "jr": sources = [parts[1]]

        for stage_pkg in [ex_pkg, mem_pkg]:
            if stage_pkg != "Empty" and "NOP" not in str(stage_pkg) and "STALL" not in str(stage_pkg):
                stage_text = stage_pkg["text"] if isinstance(stage_pkg, dict) else str(stage_pkg)
                clean_stage = stage_text.replace(",", " ").replace("(", " ").replace(")", " ")
                s_parts = clean_stage.split()
                
                if len(s_parts) > 1:
                    target = s_parts[1]
                    target_op = s_parts[0].lower()
                    if target in sources and target != "R0":
                        # Load-Use Hazard Kontrolü
                        if target_op == "lw" and stage_pkg == ex_pkg:
                            return "STALL"
        return False

    def get_forwarded_value(self, reg_name):
        if reg_name == "R0": return 0
        # MEM ve WB'den forwarding kontrolü (Dinamik Register okuma)
        return self.registers[reg_name]
            
    def execute(self, instr_pkg):
        # NOP, Empty veya STALL durumlarında işlem yapma
        if instr_pkg == "Empty" or "NOP" in str(instr_pkg) or "STALL" in str(instr_pkg):
            return

        self.executed_instr_count += 1

        # Paket yapısından metni ve adresi çıkart
        if isinstance(instr_pkg, dict):
            instr_text = instr_pkg["text"]
            instr_addr = instr_pkg["addr"]
        else:
            instr_text = str(instr_pkg)
            instr_addr = 0 

        parts = instr_text.replace(",", " ").split()
        if not parts: return
        op = parts[0].lower()

        try:
            # --- ARİTMETİK VE MANTIKSAL İŞLEMLER ---
            if op in ["add", "sub", "and", "or", "slt"]:
                rd, rs, rt = parts[1], parts[2], parts[3]
                # Register yerine Forwarding biriminden en güncel veriyi alıyoruz
                val_s = self.get_forwarded_value(rs)
                val_t = self.get_forwarded_value(rt)
                
                if op == "add": res = val_s + val_t
                elif op == "sub": res = val_s - val_t
                elif op == "and": res = val_s & val_t
                elif op == "or": res = val_s | val_t
                elif op == "slt": res = 1 if val_s < val_t else 0
                
                if rd != "R0": self.registers[rd] = self.to_signed_16(res)

            # --- ADDI ---
            elif op == "addi":
                rt, rs, imm = parts[1], parts[2], int(parts[3])
                res = self.get_forwarded_value(rs) + self.sign_extend_imm(imm, 16)
                if rt != "R0": self.registers[rt] = self.to_signed_16(res)

            # --- LW / SW ---
            elif op in ["lw", "sw"]:
                rt = parts[1]
                offset_reg = parts[2].replace(")", "").split("(")
                offset = int(offset_reg[0])
                rs = offset_reg[1]
                addr = (self.get_forwarded_value(rs) + offset) & 0x3FE
                
                if op == "sw":
                    val = self.get_forwarded_value(rt) # Kaydedilecek veriyi de forward et
                    self.memory[addr] = (val >> 8) & 0xFF
                    self.memory[addr + 1] = val & 0xFF
                else:
                    loaded_val = (self.memory[addr] << 8) | self.memory[addr + 1]
                    self.registers[rt] = self.to_signed_16(loaded_val)

            # --- JUMP (j) ---
            elif op == "j":
                target = parts[1]
                if target in self.labels:
                    self.pc = self.labels[target]
                    self.flush_pipeline()

            # --- JUMP AND LINK (jal) ---
            elif op == "jal":
                # Örn: jal R7, my_func
                rd, target = parts[1], parts[2]
                if target in self.labels:
                    # R7'ye (veya rd'ye) JAL komutunun bir sonraki adresini kaydet
                    self.registers[rd] = instr_addr + 1 
                    self.pc = self.labels[target]
                    self.flush_pipeline()

            # --- JUMP REGISTER (jr) ---
            elif op == "jr":
                rs = parts[1]
                # Hedef adresi register'dan (veya forwarding biriminden) al
                self.pc = self.get_forwarded_value(rs)
                self.flush_pipeline()

            # --- BEQ / BNE ---
            elif op in ["beq", "bne"]:
                rs, rt, label = parts[1], parts[2], parts[3]
                val_s = self.get_forwarded_value(rs)
                val_t = self.get_forwarded_value(rt)
                condition = (val_s == val_t) if op == "beq" else (val_s != val_t)
                if condition and label in self.labels:
                    self.pc = self.labels[label]
                    self.flush_pipeline()

            # --- SHIFT OPERATIONS ---
            elif op == "sll":
                # Sola Kaydır (SLL R1, R1, 1 -> R1'i 2 ile çarpmak gibidir)
                rd, rs, shamt = parts[1], parts[2], int(parts[3])
                res = self.get_forwarded_value(rs) << shamt
                if rd != "R0": self.registers[rd] = self.to_signed_16(res)

            elif op == "srl":
                # Sağa Kaydır (SRL R1, R1, 1 -> R1'i 2'ye bölmek gibidir)
                rd, rs, shamt = parts[1], parts[2], int(parts[3])
                # Python'da sağa kaydırma işareti korur, ama 16-bit maskeleme ile SRL yapalım
                val = self.get_forwarded_value(rs) & 0xFFFF
                res = val >> shamt
                if rd != "R0": self.registers[rd] = self.to_signed_16(res)

            # --- HALT ---
            elif op == "halt":
                self.pc = 512
                self.flush_pipeline()

        except Exception as e:
            print(f"Execute Error ({op}): {e}")
        finally:
            self.registers["R0"] = 0 # R0 her zaman 0 kalmalı

    def flush_pipeline(self):
        # Sadece henüz bitmemiş olan aşamaları temizle
        # WB'yi (Write-Back) temizlemiyoruz çünkü o an biten komutun 
        # sonucunun kaydedilmesi gerekiyor.
        for stage in ["IF", "ID", "EX", "MEM"]:
            self.pipeline[stage] = {"text": "NOP (Flush)", "addr": -1}
            
        # Debug için konsola yazdırabilirsin
        print(f"--- PIPELINE FLUSHED AT PC: {self.pc} ---")

    def get_memory_dump(self, limit=64):
        return {addr: self.memory[addr] for addr in range(limit)}

    def get_performance_metrics(self):
        cpi = self.total_cycles / self.executed_instr_count if self.executed_instr_count > 0 else 0
        return {
            "Total Cycles": self.total_cycles,
            "Executed Instructions": self.executed_instr_count,
            "Stall Count": self.stall_count,
            "CPI": round(cpi, 2),
            "IPC": round(1/cpi, 2) if cpi > 0 else 0
        }