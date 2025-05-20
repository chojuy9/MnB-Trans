import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, simpledialog # simpledialog는 CSV 열 선택 시 예시로 사용 가능
import google.generativeai as genai
import re
import os
import json
import csv # CSV 처리를 위해 임포트 (향후 확장 시 사용)

# --- 설정 파일 경로 ---
CONFIG_FILE = "translator_config.json"
API_KEY_NAME_IN_CONFIG = "gemini_api_key" # 설정 파일 내 API 키 이름

class CoreTranslatorApp:
    def __init__(self, master):
        self.master = master
        master.title("M&B 모드 번역기 (핵심 기능 v1.1 - CSV 로드 가능)")
        master.geometry("800x600")

        self.api_key = ""
        
        # CSV 관련 변수 (향후 확장용) - 이것들은 status_label과 직접 관련 없으므로 위치는 크게 상관 없음
        self.is_csv_mode = False
        self.original_csv_data = []
        self.csv_header = []
        self.csv_target_column_index = None

        # --- 상태 표시줄을 먼저 정의하고 초기화합니다. ---
        self.status_label = tk.Label(master, text="상태: 초기화 중...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X) # pack도 여기서 미리 해줍니다.

        # 이제 load_config를 호출해도 status_label이 존재합니다.
        self.load_config()

        # --- API 키 설정 영역 ---
        api_frame = tk.Frame(master)
        api_frame.pack(fill=tk.X, padx=10, pady=5)

        api_label = tk.Label(api_frame, text="Gemini API Key:")
        api_label.pack(side=tk.LEFT, padx=(0, 5))

        self.api_key_entry = tk.Entry(api_frame, width=50, show="*")
        self.api_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        if self.api_key: # load_config 이후 api_key 값이 설정되었을 수 있으므로 여기서 insert
            self.api_key_entry.insert(0, self.api_key)

        self.save_api_key_button = tk.Button(api_frame, text="API 키 저장", command=self.save_api_key_action)
        self.save_api_key_button.pack(side=tk.LEFT, padx=(5, 0))

        # --- 텍스트 영역 프레임 ---
        text_frame = tk.Frame(master)
        text_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        original_text_frame = tk.Frame(text_frame)
        original_text_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 5))
        
        original_label = tk.Label(original_text_frame, text="원본 텍스트 (영어)")
        original_label.pack(anchor=tk.W)
        self.original_text_area = scrolledtext.ScrolledText(original_text_frame, wrap=tk.WORD, height=15)
        self.original_text_area.pack(expand=True, fill=tk.BOTH)

        translated_text_frame = tk.Frame(text_frame)
        translated_text_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(5, 0))

        translated_label = tk.Label(translated_text_frame, text="번역된 텍스트 (한국어)")
        translated_label.pack(anchor=tk.W)
        self.translated_text_area = scrolledtext.ScrolledText(translated_text_frame, wrap=tk.WORD, height=15)
        self.translated_text_area.pack(expand=True, fill=tk.BOTH)
        self.translated_text_area.config(state=tk.DISABLED)

        # --- 버튼 프레임 ---
        button_frame = tk.Frame(master)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        self.load_file_button = tk.Button(button_frame, text="파일 열기", command=self.load_file_action)
        self.load_file_button.pack(side=tk.LEFT, padx=(0,5))

        self.save_file_button = tk.Button(button_frame, text="번역 결과 저장", command=self.save_file_action)
        self.save_file_button.pack(side=tk.LEFT, padx=(0,5))
        
        self.translate_button = tk.Button(button_frame, text="번역하기", command=self.translate_action, font=("Arial", 10, "bold"))
        self.translate_button.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # --- 상태 표시줄 --- (정의는 위로 옮겼고, 마지막 상태 업데이트는 그대로 둡니다)
        # self.status_label = tk.Label(master, text="상태: 준비", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        # self.status_label.pack(side=tk.BOTTOM, fill=tk.X) # 이미 위에서 pack 했음

        # load_config 호출 이후, API 키가 로드되었는지 여부에 따라 상태 메시지를 다시 설정할 수 있습니다.
        if not self.api_key: # load_config 후에도 api_key가 없다면
            self.update_status("API 키를 입력하고 저장해주세요.")
        # else: # api_key가 있다면 load_config 내부에서 이미 "저장된 API 키를 로드했습니다."로 설정됨

    def update_status(self, message):
        self.status_label.config(text=f"상태: {message}")
        self.master.update_idletasks()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    self.api_key = config.get(API_KEY_NAME_IN_CONFIG, "")
                    if self.api_key:
                        self.update_status("저장된 API 키를 로드했습니다.")
                    return True
            except Exception as e:
                self.update_status(f"설정 파일 로드 오류: {e}")
        return False

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({API_KEY_NAME_IN_CONFIG: self.api_key}, f)
            self.update_status("API 키가 설정 파일에 저장되었습니다.")
            return True
        except Exception as e:
            messagebox.showerror("저장 오류", f"설정 파일 저장 실패: {e}")
            self.update_status(f"오류: 설정 파일 저장 실패 - {e}")
            return False

    def save_api_key_action(self):
        entered_key = self.api_key_entry.get().strip()
        if not entered_key:
            messagebox.showwarning("API 키 필요", "Gemini API 키를 입력해주세요.")
            return
        self.api_key = entered_key
        self.save_config()
        messagebox.showinfo("API 키 저장됨", "API 키가 성공적으로 저장되었습니다.")

    def mnb_preprocess_text(self, text):
        replacements = {
            r"(\{s\d+\})": r"__MNBTAG_S\1__",
            r"(\{reg\d+\})": r"__MNBTAG_REG\1__",
            r"(\{player_name\})": r"__MNBTAG_PLAYERNAME__",
            # 추가적인 일반 태그 보호 (예: {faction_name}, {city_name})
            # 좀 더 포괄적인 태그: (\{[a-zA-Z_][a-zA-Z_0-9]*\}) -> __MNBTAG_GENERIC\1__
            # 주의: 너무 광범위한 패턴은 오작동을 일으킬 수 있으므로 테스트 필요
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)
        return text

    def mnb_postprocess_text(self, text):
        replacements_restore = {
            r"__MNBTAG_S(\{s\d+\})__": r"\1",
            r"__MNBTAG_REG(\{reg\d+\})__": r"\1",
            r"__MNBTAG_PLAYERNAME__": r"{player_name}",
            # r"__MNBTAG_GENERIC(\{[a-zA-Z_][a-zA-Z_0-9]*\})__": r"\1", # 일반 태그 복원
        }
        for pattern, replacement in replacements_restore.items():
            text = re.sub(pattern, replacement, text)
        text = re.sub(r"{\s*([a-zA-Z_0-9]+)\s*}", r"{\1}", text)
        # text = text.replace("\n", "|_") # 필요시 주석 해제 (M&B 파일 특성 고려)
        return text

    def call_gemini_api(self, text_to_translate):
        if not self.api_key:
            messagebox.showerror("API 키 오류", "Gemini API 키가 설정되지 않았습니다.")
            return None
        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
            prompt = f"""Translate the following English text from a Mount & Blade game mod into Korean.
Preserve special placeholders like __MNBTAG_S{{s0}}__, __MNBTAG_REG{{reg0}}__, or __MNBTAG_PLAYERNAME__ exactly as they are.
Do not translate the content inside these placeholders.
If the original text contains line breaks, try to maintain a similar structure in Korean if it makes sense.

English Text:
{text_to_translate}

Korean Translation:
"""
            self.update_status("Gemini API 호출 중...")
            response = model.generate_content(prompt)
            self.update_status("API 응답 받음.")
            return response.text
        except Exception as e:
            messagebox.showerror("API 오류", f"Gemini API 호출 중 오류 발생: {e}")
            self.update_status(f"오류: API 호출 실패 - {e}")
            return None

    def translate_action(self):
        original_content = self.original_text_area.get("1.0", tk.END).strip()
        if not self.api_key:
            messagebox.showwarning("API 키 필요", "API 키를 입력하고 저장 버튼을 눌러주세요.")
            return
        if not original_content:
            messagebox.showwarning("입력 필요", "번역할 텍스트를 입력하거나 파일을 불러오세요.")
            return

        self.update_status("번역 준비 중...")
        
        # 핵심 기능 단계에서는 원본 텍스트 영역의 내용을 그대로 번역
        # CSV 특정 열 번역 로직은 여기에 추가되지 않음 (다음 단계에서)
        
        preprocessed_text = self.mnb_preprocess_text(original_content)
        translated_text_raw = self.call_gemini_api(preprocessed_text)
        
        if translated_text_raw:
            final_translation = self.mnb_postprocess_text(translated_text_raw.strip())
            
            self.translated_text_area.config(state=tk.NORMAL)
            self.translated_text_area.delete("1.0", tk.END)
            self.translated_text_area.insert(tk.END, final_translation)
            self.translated_text_area.config(state=tk.DISABLED)
            self.update_status("번역 완료!")
        else:
            self.update_status("번역 실패. API 오류를 확인하세요.")

    def load_file_action(self):
        self.update_status("파일 여는 중...")
        filepath = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")] # CSV를 먼저
        )
        if not filepath:
            self.update_status("파일 열기 취소됨.")
            return

        file_extension = os.path.splitext(filepath)[1].lower()
        encodings_to_try = ['utf-8', 'cp1252', 'latin-1']
        content_to_display = ""
        
        # 이전 CSV 관련 상태 초기화
        self.is_csv_mode = False
        self.original_csv_data = []
        self.csv_header = []
        self.csv_target_column_index = None

        try:
            loaded_encoding = None
            raw_content_bytes = None # 바이너리로 먼저 읽어서 인코딩 추정 시도

            # 파일을 바이너리 모드로 읽어서 인코딩 감지 시도 (간단한 방식)
            with open(filepath, "rb") as f_bytes:
                raw_content_bytes = f_bytes.read()

            for enc in encodings_to_try:
                try:
                    content_to_display = raw_content_bytes.decode(enc)
                    loaded_encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
            
            if loaded_encoding is None:
                messagebox.showerror("파일 읽기 오류", f"파일 인코딩을 확인할 수 없습니다 (시도: {', '.join(encodings_to_try)}): {filepath}")
                self.update_status("오류: 파일 인코딩 문제")
                return

            # 현재 핵심 단계에서는 CSV 파일도 전체 텍스트를 원본 영역에 표시
            # CSV 특정 열 처리 로직은 다음 단계에서 구현
            if file_extension == ".csv":
                self.is_csv_mode = True # CSV 모드임을 표시 (향후 사용)
                # 예시: 첫 줄을 헤더로 간주하고 저장 (향후 사용)
                # import io
                # reader = csv.reader(io.StringIO(content_to_display))
                # try:
                #     self.csv_header = next(reader)
                #     self.original_csv_data = list(reader) # 헤더 제외한 데이터
                # except StopIteration: # 빈 파일이거나 헤더만 있는 경우
                #     self.csv_header = []
                #     self.original_csv_data = []
                # except csv.Error as e:
                #     messagebox.showwarning("CSV 파싱 경고", f"CSV 파일 파싱 중 문제 발생: {e}\n파일이 올바른 CSV 형식이 아닐 수 있습니다. 전체 텍스트로 로드합니다.")
                #     self.is_csv_mode = False # CSV 모드 해제
                self.update_status(f"CSV 파일 로드: {os.path.basename(filepath)} (인코딩: {loaded_encoding}). 전체 내용이 표시됩니다.")
            else:
                self.update_status(f"TXT 파일 로드 완료: {os.path.basename(filepath)} (인코딩: {loaded_encoding})")

            self.original_text_area.delete("1.0", tk.END)
            self.original_text_area.insert(tk.END, content_to_display)
            
            self.translated_text_area.config(state=tk.NORMAL)
            self.translated_text_area.delete("1.0", tk.END)
            self.translated_text_area.config(state=tk.DISABLED)

        except FileNotFoundError:
            messagebox.showerror("파일 오류", f"파일을 찾을 수 없습니다: {filepath}")
            self.update_status(f"오류: 파일을 찾을 수 없음")
        except Exception as e:
            messagebox.showerror("파일 처리 오류", f"파일 처리 중 알 수 없는 오류 발생: {e}")
            self.update_status(f"오류: 파일 처리 실패 - {e}")

    def save_file_action(self):
        self.update_status("번역 파일 저장 중...")
        content_to_save = self.translated_text_area.get("1.0", tk.END).strip()
        if not content_to_save:
            messagebox.showwarning("저장 오류", "저장할 번역된 내용이 없습니다.")
            return

        # 핵심 기능 단계에서는 번역된 텍스트 전체를 새 파일에 저장
        # CSV 특정 열을 번역했다면, 원본 CSV 구조에 번역된 열을 다시 삽입하는 로직은 다음 단계에서 구현
        
        initial_filename = "translated_output.txt"
        if self.is_csv_mode: # 로드한 파일이 CSV였다면 저장 파일명도 .csv 제안
             initial_filename = "translated_output.csv"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt", # 기본 확장자는 txt
            initialfile=initial_filename,
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filepath:
            self.update_status("파일 저장 취소됨.")
            return
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            messagebox.showinfo("저장 완료", "번역된 파일이 성공적으로 저장되었습니다.")
            self.update_status(f"파일 저장 완료: {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("파일 저장 오류", f"파일 저장 중 오류 발생: {e}")
            self.update_status(f"오류: 파일 저장 실패 - {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = CoreTranslatorApp(root)
    root.mainloop()
