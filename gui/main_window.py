import tkinter as tk
from tkinter import scrolledtext, messagebox # filedialog는 file_handler에서 사용
import os # os.path.basename 사용

# core 모듈에서 필요한 클래스 및 함수 임포트
from core.config_manager import load_api_key, save_api_key
from core.translator import TextProcessor
from core.file_handler import FileHandler

class CoreTranslatorApp:
    def __init__(self, master):
        self.master = master
        master.title("M&B 모드 번역기 (v1.3 - 구조화)")
        master.geometry("800x650")

        self.api_key = ""
        self.unsaved_translation = False

        self.is_csv_mode = False
        # CSV 관련 데이터는 이제 FileHandler나 TextProcessor에서 직접 관리하지 않고,
        # 필요시 이 클래스에 유지하거나, 또는 각 작업 시 전달받아 사용합니다.
        # self.original_csv_data = []
        # self.csv_header = []
        # self.csv_target_column_index = None

        # 핵심 로직 클래스 인스턴스화
        self.text_processor = TextProcessor(self) # self (GUI 인스턴스) 전달
        self.file_handler = FileHandler(self)   # self (GUI 인스턴스) 전달

        # --- 상태 표시줄 ---
        self.status_label = tk.Label(master, text="상태: 초기화 중...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0,5))

        self.load_initial_config() # API 키 로드 및 초기 설정

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
        # ... (original_text_area, translated_text_area 생성 코드는 동일하게 유지) ...
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
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        self.load_file_button = tk.Button(button_frame, text="파일 열기", command=self.load_file_action_gui)
        self.load_file_button.pack(side=tk.LEFT, padx=(0,5))
        self.save_file_button = tk.Button(button_frame, text="번역 결과 저장", command=self.save_file_action_gui)
        self.save_file_button.pack(side=tk.LEFT, padx=(0,5))
        self.translate_button = tk.Button(button_frame, text="번역하기", command=self.translate_action_gui, font=("Arial", 10, "bold"))
        self.translate_button.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # 초기 API 키 확인 및 안내
        if not self.api_key:
            self.update_status("API 키를 입력하고 저장해주세요.")
            messagebox.showinfo("API 키 필요", "Gemini API 키를 입력하고 'API 키 저장' 버튼을 눌러주세요.\nAPI 키가 없으면 번역 기능을 사용할 수 없습니다.")
            self.api_key_entry.focus_set()
        else:
            self.update_status("API 키 로드 완료. 번역 준비되었습니다.")

        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_status(self, message):
        self.status_label.config(text=f"상태: {message}")
        self.master.update_idletasks()

    def load_initial_config(self):
        self.api_key = load_api_key()
        # self.update_status 호출은 __init__ 마지막에서 하도록 조정

    def save_api_key_action(self):
        entered_key = self.api_key_entry.get().strip()
        if not entered_key:
            messagebox.showwarning("API 키 필요", "Gemini API 키를 입력해주세요.")
            return
        if save_api_key(entered_key):
            self.api_key = entered_key # 성공 시 내부 api_key 변수도 업데이트
            self.update_status("API 키가 설정 파일에 저장되었습니다.") # config_manager에서 직접 호출하지 않음
            messagebox.showinfo("API 키 저장됨", "API 키가 성공적으로 저장되었습니다.")
        else:
            messagebox.showerror("저장 오류", "API 키를 설정 파일에 저장하는 데 실패했습니다.")
            self.update_status("오류: API 키 저장 실패")


    def toggle_buttons_state(self, state):
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

        try:
            # TextProcessor의 translate_by_chunks 메소드 호출
            # API 키와 (선택적) 청크 크기 전달
            final_translation_by_chunks = self.text_processor.translate_by_chunks(original_content, self.api_key)

            if final_translation_by_chunks is not None: # None은 전체 번역 실패 또는 중단을 의미할 수 있음
                self.translated_text_area.config(state=tk.NORMAL)
                self.translated_text_area.delete("1.0", tk.END)
                self.translated_text_area.insert(tk.END, final_translation_by_chunks.strip()) # 마지막에 불필요한 공백 제거
                self.translated_text_area.config(state=tk.DISABLED)
                self.unsaved_translation = True
                self.update_status("전체 번역 완료! (청크 단위)")
            else:
                # translate_by_chunks 내부에서 이미 오류 메시지 및 상태 업데이트 가능성 있음
                self.update_status("전체 번역 실패 또는 중단됨.")
        except Exception as e:
            messagebox.showerror("번역 오류", f"번역 중 예상치 못한 오류 발생: {e}")
            self.update_status(f"오류: 번역 중 오류 - {e}")
        finally:
            self.toggle_buttons_state(tk.NORMAL)

    def load_file_action_gui(self):
        filepath, content, is_csv = self.file_handler.load_file()
        if filepath and content is not None: # 로드 성공 시
            self.original_text_area.delete("1.0", tk.END)
            self.original_text_area.insert(tk.END, content)
            self.translated_text_area.config(state=tk.NORMAL)
            self.translated_text_area.delete("1.0", tk.END)
            self.translated_text_area.config(state=tk.DISABLED)
            self.is_csv_mode = is_csv # CSV 모드 업데이트
            # file_handler.load_file 내부에서 unsaved_translation = False 처리됨
            self.update_status(f"파일 로드 완료: {os.path.basename(filepath)}") # file_handler에서 상태 업데이트 하지만, 여기서 최종 확인

    def save_file_action_gui(self):
        content_to_save = self.translated_text_area.get("1.0", tk.END).strip()
        initial_filename = "translated_output.txt"
        if self.is_csv_mode:
             initial_filename = "translated_output.csv"

        if self.file_handler.save_file(content_to_save, initial_filename):
            # 저장 성공 시 file_handler.save_file 내부에서 unsaved_translation = False 처리됨
            pass # 성공 메시지는 file_handler에서 표시

    def on_closing(self):
        if self.unsaved_translation:
            if messagebox.askokcancel("종료 확인", "저장되지 않은 번역 내용이 있습니다. 정말로 종료하시겠습니까?"):
                self.master.destroy()
        else:
            self.master.destroy()
