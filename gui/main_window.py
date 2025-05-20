# gui/main_window.py
import tkinter as tk
from tkinter import scrolledtext, messagebox, Spinbox # Spinbox 임포트
import os

from core.config_manager import load_config, save_config, DEFAULT_CHUNK_SIZE, API_KEY_NAME_IN_CONFIG, CHUNK_SIZE_NAME_IN_CONFIG
from core.translator import TextProcessor
from core.file_handler import FileHandler

class CoreTranslatorApp:
    def __init__(self, master):
        self.master = master
        master.title("M&B 모드 번역기 (v1.4 - 청크 설정)")
        master.geometry("800x680") # UI 추가로 높이 약간 더 늘림

        self.config = {} # 전체 설정을 담을 딕셔너리
        self.api_key = "" # 편의상 유지 (self.config에서도 접근 가능)
        self.current_chunk_size = DEFAULT_CHUNK_SIZE # 현재 선택된 청크 크기

        self.unsaved_translation = False
        self.is_csv_mode = False

        self.text_processor = TextProcessor(self)
        self.file_handler = FileHandler(self)

        # --- 상태 표시줄 ---
        self.status_label = tk.Label(master, text="상태: 초기화 중...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0,5))

        self.load_initial_config_gui() # 설정 로드 및 GUI 반영

        # --- 설정 프레임 (API 키와 청크 크기) ---
        settings_frame = tk.Frame(master)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)

        # API 키 설정 부분
        api_key_frame = tk.Frame(settings_frame)
        api_key_frame.pack(fill=tk.X)
        api_label = tk.Label(api_key_frame, text="Gemini API Key:")
        api_label.pack(side=tk.LEFT, padx=(0, 5))
        self.api_key_entry = tk.Entry(api_key_frame, width=40, show="*") # 너비 약간 조절
        self.api_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        if self.api_key:
            self.api_key_entry.insert(0, self.api_key)
        self.save_api_key_button = tk.Button(api_key_frame, text="API 키 저장", command=self.save_api_key_action_gui)
        self.save_api_key_button.pack(side=tk.LEFT, padx=(5, 0))

        # 청크 크기 설정 부분
        chunk_size_frame = tk.Frame(settings_frame)
        chunk_size_frame.pack(fill=tk.X, pady=(5,0)) # 상단에 약간의 여백
        chunk_label = tk.Label(chunk_size_frame, text="청크 크기 (줄 수, 10-100):")
        chunk_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.chunk_size_var = tk.IntVar(value=self.current_chunk_size)
        self.chunk_size_spinbox = Spinbox(
            chunk_size_frame,
            from_=10,
            to=100,
            increment=10,
            textvariable=self.chunk_size_var,
            width=5,
            command=self.on_chunk_size_changed # 변경 시 바로 저장하도록
        )
        self.chunk_size_spinbox.pack(side=tk.LEFT)
        # (선택) 청크 크기 저장 버튼을 따로 만들 수도 있음
        # self.save_chunk_size_button = tk.Button(chunk_size_frame, text="청크 크기 적용", command=self.save_chunk_size_action_gui)
        # self.save_chunk_size_button.pack(side=tk.LEFT, padx=(5,0))


        # --- 텍스트 영역 및 버튼 프레임 (기존과 유사) ---
        # ... (기존 text_frame, button_frame 코드) ...
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


        button_frame = tk.Frame(master)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        self.load_file_button = tk.Button(button_frame, text="파일 열기", command=self.load_file_action_gui)
        self.load_file_button.pack(side=tk.LEFT, padx=(0,5))
        self.save_file_button = tk.Button(button_frame, text="번역 결과 저장", command=self.save_file_action_gui)
        self.save_file_button.pack(side=tk.LEFT, padx=(0,5))
        self.translate_button = tk.Button(button_frame, text="번역하기", command=self.translate_action_gui, font=("Arial", 10, "bold"))
        self.translate_button.pack(side=tk.RIGHT, fill=tk.X, expand=True)


        # 초기 API 키 확인 및 안내 (load_initial_config_gui에서 처리)
        self.update_initial_status_message()

        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_status(self, message):
        self.status_label.config(text=f"상태: {message}")
        self.master.update_idletasks()

    def load_initial_config_gui(self):
        self.config = load_config()
        self.api_key = self.config.get(API_KEY_NAME_IN_CONFIG, "")
        self.current_chunk_size = self.config.get(CHUNK_SIZE_NAME_IN_CONFIG, DEFAULT_CHUNK_SIZE)
        if hasattr(self, 'chunk_size_var'): # Spinbox가 생성된 후 값 설정
            self.chunk_size_var.set(self.current_chunk_size)


    def update_initial_status_message(self):
        if not self.api_key:
            self.update_status("API 키를 입력하고 저장해주세요.")
            messagebox.showinfo("API 키 필요", "Gemini API 키를 입력하고 'API 키 저장' 버튼을 눌러주세요.\nAPI 키가 없으면 번역 기능을 사용할 수 없습니다.")
            if hasattr(self, 'api_key_entry'): self.api_key_entry.focus_set()
        else:
            self.update_status("API 키 로드 완료. 번역 준비되었습니다.")


    def save_api_key_action_gui(self):
        entered_key = self.api_key_entry.get().strip()
        if not entered_key:
            messagebox.showwarning("API 키 필요", "Gemini API 키를 입력해주세요.")
            return
        
        self.config[API_KEY_NAME_IN_CONFIG] = entered_key
        if save_config(self.config):
            self.api_key = entered_key
            self.update_status("API 키가 설정 파일에 저장되었습니다.")
            messagebox.showinfo("API 키 저장됨", "API 키가 성공적으로 저장되었습니다.")
        else:
            messagebox.showerror("저장 오류", "API 키를 설정 파일에 저장하는 데 실패했습니다.")
            self.update_status("오류: API 키 저장 실패")

    def on_chunk_size_changed(self):
        try:
            new_size = self.chunk_size_var.get()
            # 유효성 검사 (Spinbox에서 이미 범위 제한하지만, 만약을 위해)
            if not (10 <= new_size <= 100 and new_size % 10 == 0):
                # messagebox.showwarning("입력 오류", "청크 크기는 10에서 100 사이의 10의 배수여야 합니다.")
                # self.chunk_size_var.set(self.current_chunk_size) # 이전 값으로 복원
                # Spinbox가 자동으로 범위를 맞춰주므로, 여기서는 저장만
                pass # Spinbox가 범위를 벗어난 값은 자동으로 조정해줌

            self.current_chunk_size = new_size
            self.config[CHUNK_SIZE_NAME_IN_CONFIG] = new_size
            if save_config(self.config):
                self.update_status(f"청크 크기가 {new_size}줄로 설정 및 저장되었습니다.")
            else:
                self.update_status(f"청크 크기 {new_size}줄 설정 저장 실패.")
        except tk.TclError: # Spinbox에 잘못된 값이 들어갔을 때 (예: 문자)
            self.update_status("잘못된 청크 크기 값입니다. 숫자를 입력하세요.")
            self.chunk_size_var.set(self.current_chunk_size) # 이전 값으로 복원


    def toggle_buttons_state(self, state):
        # ... (기존 코드 동일) ...
        self.translate_button.config(state=state)
        self.load_file_button.config(state=state)
        self.save_file_button.config(state=state)


    def translate_action_gui(self):
        original_content = self.original_text_area.get("1.0", tk.END).strip()
        if not self.api_key:
            messagebox.showwarning("API 키 필요", "API 키를 입력하고 저장 버튼을 눌러주세요.")
            return
        if not original_content:
            messagebox.showwarning("입력 필요", "번역할 텍스트를 입력하거나 파일을 불러오세요.")
            return

        self.toggle_buttons_state(tk.DISABLED)
        self.update_status("전체 번역 시작... (청크 단위 처리)")

        # 현재 GUI에서 설정된 청크 크기 사용
        chunk_size_to_use = self.current_chunk_size

        try:
            final_translation_by_chunks = self.text_processor.translate_by_chunks(
                original_content, 
                self.api_key, 
                chunk_size_lines=chunk_size_to_use # 수정된 청크 크기 전달
            )

            if final_translation_by_chunks is not None:
                self.translated_text_area.config(state=tk.NORMAL)
                self.translated_text_area.delete("1.0", tk.END)
                self.translated_text_area.insert(tk.END, final_translation_by_chunks.strip())
                self.translated_text_area.config(state=tk.DISABLED)
                self.unsaved_translation = True
                self.update_status(f"전체 번역 완료! (청크 크기: {chunk_size_to_use}줄)")
            else:
                self.update_status("전체 번역 실패 또는 중단됨.")
        except Exception as e:
            messagebox.showerror("번역 오류", f"번역 중 예상치 못한 오류 발생: {e}")
            self.update_status(f"오류: 번역 중 오류 - {e}")
        finally:
            self.toggle_buttons_state(tk.NORMAL)

    # ... (load_file_action_gui, save_file_action_gui, on_closing 메소드는 기존과 유사하게 유지) ...
    def load_file_action_gui(self):
        filepath, content, is_csv = self.file_handler.load_file()
        if filepath and content is not None:
            self.original_text_area.delete("1.0", tk.END)
            self.original_text_area.insert(tk.END, content)
            self.translated_text_area.config(state=tk.NORMAL)
            self.translated_text_area.delete("1.0", tk.END)
            self.translated_text_area.config(state=tk.DISABLED)
            self.is_csv_mode = is_csv
            self.update_status(f"파일 로드 완료: {os.path.basename(filepath)}")

    def save_file_action_gui(self):
        content_to_save = self.translated_text_area.get("1.0", tk.END).strip()
        initial_filename = "translated_output.txt"
        if self.is_csv_mode:
             initial_filename = "translated_output.csv"
        self.file_handler.save_file(content_to_save, initial_filename)

    def on_closing(self):
        if self.unsaved_translation:
            if messagebox.askokcancel("종료 확인", "저장되지 않은 번역 내용이 있습니다. 정말로 종료하시겠습니까?"):
                self.master.destroy()
        else:
            self.master.destroy()