# M&B 모드 번역기 (구버전 / 간단하게 쓸 사람만 쓰세요)
# 이 코드는 Google Gemini API를 사용하여 Mount & Blade 모드의 영어 텍스트를 한국어로 번역하는 GUI 애플리케이션입니다.

import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, simpledialog
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions # Google API 예외 처리를 위해 임포트
import re
import os
import json
import csv

# --- 설정 파일 경로 ---
CONFIG_FILE = "translator_config.json"
API_KEY_NAME_IN_CONFIG = "gemini_api_key"

class CoreTranslatorApp:
    def __init__(self, master):
        self.master = master
        master.title("M&B 모드 번역기 (핵심 기능 v1.2 - 개선 사항 적용)")
        master.geometry("800x650") # 높이 약간 늘림 (상태표시줄 등 고려)

        self.api_key = ""
        self.unsaved_translation = False # 번역 후 저장 안 된 상태 추적

        # CSV 관련 변수
        self.is_csv_mode = False
        self.original_csv_data = []
        self.csv_header = []
        self.csv_target_column_index = None

        # --- 상태 표시줄 (다른 위젯보다 먼저 정의) ---
        self.status_label = tk.Label(master, text="상태: 초기화 중...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0,5)) # 패딩 추가

        # 설정 파일에서 API 키 로드
        self.load_config()

        # --- API 키 설정 영역 ---
        api_frame = tk.Frame(master)
        api_frame.pack(fill=tk.X, padx=10, pady=5)

        api_label = tk.Label(api_frame, text="Gemini API Key:")
        api_label.pack(side=tk.LEFT, padx=(0, 5))

        self.api_key_entry = tk.Entry(api_frame, width=50, show="*")
        self.api_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        if self.api_key:
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
        button_frame.pack(fill=tk.X, padx=10, pady=10) # 하단 패딩 증가

        self.load_file_button = tk.Button(button_frame, text="파일 열기", command=self.load_file_action)
        self.load_file_button.pack(side=tk.LEFT, padx=(0,5))

        self.save_file_button = tk.Button(button_frame, text="번역 결과 저장", command=self.save_file_action)
        self.save_file_button.pack(side=tk.LEFT, padx=(0,5))

        self.translate_button = tk.Button(button_frame, text="번역하기", command=self.translate_action, font=("Arial", 10, "bold"))
        self.translate_button.pack(side=tk.RIGHT, fill=tk.X, expand=True)


        # 초기 API 키 확인 및 안내
        if not self.api_key:
            self.update_status("API 키를 입력하고 저장해주세요.")
            messagebox.showinfo("API 키 필요", "Gemini API 키를 입력하고 'API 키 저장' 버튼을 눌러주세요.\nAPI 키가 없으면 번역 기능을 사용할 수 없습니다.")
            self.api_key_entry.focus_set() # API 키 입력창에 포커스
        else:
            self.update_status("API 키 로드 완료. 번역 준비되었습니다.")

        # 창 닫기 버튼(X) 클릭 시 호출될 함수 설정
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

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
                        # self.update_status("저장된 API 키를 로드했습니다.") # __init__에서 최종 메시지 설정
                        pass
                    return True
            except Exception as e:
                self.update_status(f"설정 파일 로드 오류: {e}") # 초기 상태표시줄에 표시
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
        if self.save_config(): # 저장 성공 시 메시지 박스 표시
            messagebox.showinfo("API 키 저장됨", "API 키가 성공적으로 저장되었습니다.")

    def mnb_preprocess_text(self, text):
        replacements = {
            r"(\{s\d+\})": r"__MNBTAG_S\1__",
            r"(\{reg\d+\})": r"__MNBTAG_REG\1__",
            r"(\{player_name\})": r"__MNBTAG_PLAYERNAME__",
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)
        return text

    def mnb_postprocess_text(self, text):
        replacements_restore = {
            r"__MNBTAG_S(\{s\d+\})__": r"\1",
            r"__MNBTAG_REG(\{reg\d+\})__": r"\1",
            r"__MNBTAG_PLAYERNAME__": r"{player_name}",
        }
        for pattern, replacement in replacements_restore.items():
            text = re.sub(pattern, replacement, text)
        text = re.sub(r"{\s*([a-zA-Z_0-9]+)\s*}", r"{\1}", text)
        return text

    def call_gemini_api(self, text_to_translate):
        if not self.api_key:
            messagebox.showerror("API 키 오류", "Gemini API 키가 설정되지 않았습니다.")
            return None
        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17') # 실제 사용 가능한 모델명으로 변경 필요
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
        except google_exceptions.PermissionDenied as e:
            messagebox.showerror("API 권한 오류", f"API 키가 유효하지 않거나 권한이 없습니다.\n세부 정보: {e}")
            self.update_status(f"오류: API 권한 문제")
            return None
        except google_exceptions.ResourceExhausted as e: # 할당량 초과 등
            messagebox.showerror("API 리소스 오류", f"API 할당량을 초과했거나 리소스가 부족합니다.\n세부 정보: {e}")
            self.update_status(f"오류: API 리소스 문제")
            return None
        except google_exceptions.DeadlineExceeded as e:
            messagebox.showerror("API 시간 초과", f"API 호출 시간이 초과되었습니다.\n세부 정보: {e}")
            self.update_status(f"오류: API 시간 초과")
            return None
        except google_exceptions.GoogleAPIError as e: # 그 외 Google API 관련 오류
            messagebox.showerror("Google API 오류", f"Google API 관련 오류 발생:\n세부 정보: {e}")
            self.update_status(f"오류: Google API 문제")
            return None
        except Exception as e: # 그 외 모든 예외
            messagebox.showerror("API 알 수 없는 오류", f"Gemini API 호출 중 알 수 없는 오류 발생:\n세부 정보: {e}")
            self.update_status(f"오류: API 알 수 없는 오류")
            return None

    def toggle_buttons_state(self, state):
        """주요 버튼들의 상태를 일괄 변경하는 헬퍼 메소드"""
        self.translate_button.config(state=state)
        self.load_file_button.config(state=state)
        self.save_file_button.config(state=state)
        # API 키 저장 버튼은 항상 활성화 상태 유지 또는 별도 로직
        # self.save_api_key_button.config(state=state) # 필요시 주석 해제

    def translate_action(self):
        original_content = self.original_text_area.get("1.0", tk.END).strip()
        if not self.api_key:
            messagebox.showwarning("API 키 필요", "API 키를 입력하고 저장 버튼을 눌러주세요.")
            return
        if not original_content:
            messagebox.showwarning("입력 필요", "번역할 텍스트를 입력하거나 파일을 불러오세요.")
            return

        self.toggle_buttons_state(tk.DISABLED) # 버튼 비활성화
        self.update_status("번역 준비 중...")

        try:
            preprocessed_text = self.mnb_preprocess_text(original_content)
            translated_text_raw = self.call_gemini_api(preprocessed_text)

            if translated_text_raw:
                final_translation = self.mnb_postprocess_text(translated_text_raw.strip())

                self.translated_text_area.config(state=tk.NORMAL)
                self.translated_text_area.delete("1.0", tk.END)
                self.translated_text_area.insert(tk.END, final_translation)
                self.translated_text_area.config(state=tk.DISABLED)
                self.unsaved_translation = True # 번역 결과가 있으므로 저장 안 된 상태
                self.update_status("번역 완료!")
            else:
                # call_gemini_api 내부에서 이미 오류 메시지 및 상태 업데이트
                self.update_status("번역 실패. API 오류를 확인하세요.")
        except Exception as e:
            messagebox.showerror("번역 오류", f"번역 중 예상치 못한 오류 발생: {e}")
            self.update_status(f"오류: 번역 중 오류 - {e}")
        finally:
            self.toggle_buttons_state(tk.NORMAL) # 버튼 다시 활성화

    def load_file_action(self):
        # 파일 열기 전, 현재 번역된 내용 저장 여부 확인 (선택 사항)
        if self.unsaved_translation:
            if not messagebox.askokcancel("확인", "저장되지 않은 번역 내용이 있습니다. 계속 진행하시겠습니까?"):
                return

        self.update_status("파일 여는 중...")
        filepath = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not filepath:
            self.update_status("파일 열기 취소됨.")
            return

        file_extension = os.path.splitext(filepath)[1].lower()
        encodings_to_try = ['utf-8', 'cp1252', 'latin-1', 'euc-kr', 'cp949'] # 한국어 인코딩 추가 시도
        content_to_display = ""

        self.is_csv_mode = False
        self.original_csv_data = []
        self.csv_header = []
        self.csv_target_column_index = None

        try:
            loaded_encoding = None
            raw_content_bytes = None

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

            if file_extension == ".csv":
                self.is_csv_mode = True
                self.update_status(f"CSV 파일 로드: {os.path.basename(filepath)} (인코딩: {loaded_encoding}). 전체 내용 표시.")
            else:
                self.update_status(f"TXT 파일 로드 완료: {os.path.basename(filepath)} (인코딩: {loaded_encoding})")

            self.original_text_area.delete("1.0", tk.END)
            self.original_text_area.insert(tk.END, content_to_display)

            self.translated_text_area.config(state=tk.NORMAL)
            self.translated_text_area.delete("1.0", tk.END)
            self.translated_text_area.config(state=tk.DISABLED)
            self.unsaved_translation = False # 새 파일 로드 시 이전 번역은 의미 없음
            self.update_status(f"파일 로드 완료: {os.path.basename(filepath)}")

        except FileNotFoundError:
            messagebox.showerror("파일 오류", f"파일을 찾을 수 없습니다: {filepath}")
            self.update_status(f"오류: 파일을 찾을 수 없음")
        except Exception as e:
            messagebox.showerror("파일 처리 오류", f"파일 처리 중 알 수 없는 오류 발생: {e}")
            self.update_status(f"오류: 파일 처리 실패 - {e}")

    def save_file_action(self):
        content_to_save = self.translated_text_area.get("1.0", tk.END).strip()
        if not content_to_save:
            messagebox.showwarning("저장 오류", "저장할 번역된 내용이 없습니다.")
            return

        self.update_status("번역 파일 저장 중...")
        initial_filename = "translated_output.txt"
        if self.is_csv_mode:
             initial_filename = "translated_output.csv"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=initial_filename,
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filepath:
            self.update_status("파일 저장 취소됨.")
            return

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            self.unsaved_translation = False # 저장했으므로
            messagebox.showinfo("저장 완료", "번역된 파일이 성공적으로 저장되었습니다.")
            self.update_status(f"파일 저장 완료: {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("파일 저장 오류", f"파일 저장 중 오류 발생: {e}")
            self.update_status(f"오류: 파일 저장 실패 - {e}")

    def on_closing(self):
        if self.unsaved_translation:
            if messagebox.askokcancel("종료 확인", "저장되지 않은 번역 내용이 있습니다. 정말로 종료하시겠습니까?"):
                self.master.destroy()
        else:
            self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CoreTranslatorApp(root)
    root.mainloop()
