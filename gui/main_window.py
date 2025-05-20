import tkinter as tk
from tkinter import scrolledtext, messagebox, Spinbox, ttk, filedialog, Listbox, END, SINGLE, Scrollbar
import os
import threading
import queue
import time
import sys # PyInstaller 경로 처리를 위해

# core 모듈에서 필요한 클래스 및 함수 임포트
from core.config_manager import (
    load_config, save_config,
    API_KEY_NAME_IN_CONFIG, CHUNK_SIZE_NAME_IN_CONFIG, SELECTED_PROMPT_ID_NAME_IN_CONFIG,
    ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG, DEFAULT_CHUNK_SIZE, USER_DATA_DIR
)
from core.prompt_manager import PromptManager
from core.translator import TextProcessor
from core.file_handler import FileHandler
from core.glossary_manager import GlossaryManager # GlossaryManager 임포트

# 메시지 타입 정의
MSG_TYPE_PROGRESS = "progress"
MSG_TYPE_STATUS = "status"
MSG_TYPE_RESULT = "result"
MSG_TYPE_ERROR = "error"
MSG_TYPE_FILE_LOAD_RESULT = "file_load_result"
MSG_TYPE_OPERATION_COMPLETE = "operation_complete"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)


class CoreTranslatorApp:
    def __init__(self, master):
        self.master = master
        master.title("M&B 모드 번역기 (v1.8 - 용어집 적용)")
        master.geometry("800x780") # 용어집 UI 공간 고려하여 높이 증가

        self.config = {}
        self.api_key = ""
        self.current_chunk_size = DEFAULT_CHUNK_SIZE
        self.unsaved_translation = False
        self.is_csv_mode = False

        self.current_operation_thread = None
        self.cancel_requested = threading.Event()
        self.message_queue = queue.Queue()

        default_prompts_path = resource_path(os.path.join("data", "default_prompts.json"))
        self.prompt_manager = PromptManager(prompts_file_path=default_prompts_path)
        self.available_prompt_names = self.prompt_manager.get_prompt_names()
        self.current_selected_prompt_name = ""

        self.glossary_manager = GlossaryManager(self) # GlossaryManager 인스턴스

        self.text_processor = TextProcessor(self)
        self.file_handler = FileHandler(self)

        self._setup_ui()
        self.load_initial_config_gui()
        self.update_initial_status_message()

        master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.after(100, self.process_message_queue)

    def _setup_ui(self):
        # --- 상태 표시줄 & 진행률 바 (하단에 먼저 배치) ---
        bottom_status_frame = tk.Frame(self.master)
        bottom_status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        self.status_label = tk.Label(bottom_status_frame, text="상태: 초기화 중...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.TOP, fill=tk.X) # 상태 레이블을 위로

        self.progress_var = tk.DoubleVar()
        self.progressbar = ttk.Progressbar(bottom_status_frame, variable=self.progress_var, maximum=100)
        self.progressbar.pack(side=tk.TOP, fill=tk.X, pady=(2,0)) # 진행률 바를 아래로


        # --- 설정 프레임 (API 키, 청크, 프롬프트) ---
        settings_outer_frame = tk.Frame(self.master) # 모든 설정을 담을 외부 프레임
        settings_outer_frame.pack(fill=tk.X, padx=10, pady=5)

        # 첫 번째 설정 줄 (API 키, 청크 크기)
        settings_row1_frame = tk.Frame(settings_outer_frame)
        settings_row1_frame.pack(fill=tk.X)

        api_key_frame = tk.Frame(settings_row1_frame)
        api_key_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,10))
        api_label = tk.Label(api_key_frame, text="Gemini API Key:")
        api_label.pack(side=tk.LEFT, padx=(0, 5))
        self.api_key_entry = tk.Entry(api_key_frame, width=25, show="*") # 너비 조절
        self.api_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.save_api_key_button = tk.Button(api_key_frame, text="키 저장", command=self.save_api_key_action_gui) # 텍스트 줄임
        self.save_api_key_button.pack(side=tk.LEFT, padx=(5, 0))

        chunk_size_frame = tk.Frame(settings_row1_frame)
        chunk_size_frame.pack(side=tk.LEFT)
        chunk_label = tk.Label(chunk_size_frame, text="청크(줄):")
        chunk_label.pack(side=tk.LEFT, padx=(0, 5))
        self.chunk_size_var = tk.IntVar()
        self.chunk_size_spinbox = Spinbox(
            chunk_size_frame, from_=10, to=100, increment=10,
            textvariable=self.chunk_size_var, width=4, command=self.on_chunk_size_changed
        )
        self.chunk_size_spinbox.pack(side=tk.LEFT)

        # 두 번째 설정 줄 (프롬프트 선택)
        prompt_select_frame = tk.Frame(settings_outer_frame)
        prompt_select_frame.pack(fill=tk.X, pady=(5,0))
        prompt_label = tk.Label(prompt_select_frame, text="번역 프롬프트:")
        prompt_label.pack(side=tk.LEFT, padx=(0,5))
        self.prompt_combobox_var = tk.StringVar()
        self.prompt_combobox = ttk.Combobox(
            prompt_select_frame, textvariable=self.prompt_combobox_var,
            values=self.available_prompt_names, state="readonly", width=30
        )
        if self.available_prompt_names:
            self.prompt_combobox.bind("<<ComboboxSelected>>", self.on_prompt_selected)
        self.prompt_combobox.pack(side=tk.LEFT, expand=True, fill=tk.X)


        # --- 용어집 관리 프레임 ---
        glossary_main_frame = tk.Frame(self.master)
        glossary_main_frame.pack(fill=tk.X, padx=10, pady=5)
        
        glossary_label = tk.Label(glossary_main_frame, text="활성 용어집 파일 (CSV):")
        glossary_label.pack(anchor=tk.W)

        glossary_ui_frame = tk.Frame(glossary_main_frame)
        glossary_ui_frame.pack(fill=tk.X, expand=True)

        listbox_frame = tk.Frame(glossary_ui_frame) # 리스트박스 + 스크롤바
        listbox_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        self.glossary_listbox = Listbox(listbox_frame, selectmode=SINGLE, height=3, exportselection=False)
        self.glossary_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        glossary_scrollbar = Scrollbar(listbox_frame, orient="vertical", command=self.glossary_listbox.yview)
        glossary_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.glossary_listbox.config(yscrollcommand=glossary_scrollbar.set)

        glossary_button_frame = tk.Frame(glossary_ui_frame) # 추가/제거 버튼
        glossary_button_frame.pack(side=tk.LEFT, anchor=tk.N)
        add_glossary_button = tk.Button(glossary_button_frame, text="추가", command=self.add_glossary_file_action, width=5)
        add_glossary_button.pack(fill=tk.X, pady=(0,2))
        remove_glossary_button = tk.Button(glossary_button_frame, text="제거", command=self.remove_glossary_file_action, width=5)
        remove_glossary_button.pack(fill=tk.X)


        # --- 텍스트 영역 프레임 ---
        text_frame = tk.Frame(self.master)
        text_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        original_text_frame = tk.Frame(text_frame)
        original_text_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 5))
        original_label = tk.Label(original_text_frame, text="원본 텍스트 (영어)")
        original_label.pack(anchor=tk.W)
        self.original_text_area = scrolledtext.ScrolledText(original_text_frame, wrap=tk.WORD, height=10) # 높이 조절
        self.original_text_area.pack(expand=True, fill=tk.BOTH)

        translated_text_frame = tk.Frame(text_frame)
        translated_text_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(5, 0))
        translated_label = tk.Label(translated_text_frame, text="번역된 텍스트 (한국어)")
        translated_label.pack(anchor=tk.W)
        self.translated_text_area = scrolledtext.ScrolledText(translated_text_frame, wrap=tk.WORD, height=10) # 높이 조절
        self.translated_text_area.pack(expand=True, fill=tk.BOTH)
        self.translated_text_area.config(state=tk.DISABLED)

        # --- 버튼 프레임 ---
        action_button_frame = tk.Frame(self.master)
        action_button_frame.pack(fill=tk.X, padx=10, pady=5)
        self.load_file_button = tk.Button(action_button_frame, text="파일 열기", command=self.load_file_action_gui)
        self.load_file_button.pack(side=tk.LEFT, padx=(0,5))
        self.save_file_button = tk.Button(action_button_frame, text="번역 결과 저장", command=self.save_file_action_gui)
        self.save_file_button.pack(side=tk.LEFT, padx=(0,5))
        self.translate_button = tk.Button(action_button_frame, text="번역하기", command=self.translate_action_gui, font=("Arial", 10, "bold"))
        self.translate_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5,0))

        control_button_frame = tk.Frame(self.master)
        control_button_frame.pack(fill=tk.X, padx=10, pady=(0,5)) # 하단 여백 조정
        self.cancel_button = tk.Button(control_button_frame, text="작업 취소", command=self.request_cancel_operation, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.RIGHT)


    def put_message_in_queue(self, msg_type, data=None):
        # ... (이전과 동일) ...
        self.message_queue.put((msg_type, data))

    def process_message_queue(self):
        # ... (이전과 동일) ...
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()

                if msg_type == MSG_TYPE_STATUS:
                    self.status_label.config(text=f"상태: {data}")
                elif msg_type == MSG_TYPE_PROGRESS:
                    if isinstance(data, tuple):
                        current, maximum = data
                        percentage = (current / maximum) * 100 if maximum > 0 else 0
                        self.progress_var.set(percentage)
                    else:
                        self.progress_var.set(data)
                elif msg_type == MSG_TYPE_RESULT:
                    final_translation = data
                    self.translated_text_area.config(state=tk.NORMAL)
                    self.translated_text_area.delete("1.0", tk.END)
                    self.translated_text_area.insert(tk.END, final_translation.strip())
                    self.translated_text_area.config(state=tk.DISABLED)
                    self.unsaved_translation = True
                elif msg_type == MSG_TYPE_FILE_LOAD_RESULT:
                    filepath, content, is_csv = data
                    if filepath and content is not None:
                        self.original_text_area.delete("1.0", tk.END)
                        self.original_text_area.insert(tk.END, content)
                        self.translated_text_area.config(state=tk.NORMAL)
                        self.translated_text_area.delete("1.0", tk.END)
                        self.translated_text_area.config(state=tk.DISABLED)
                        self.is_csv_mode = is_csv
                        self.unsaved_translation = False
                        self.put_message_in_queue(MSG_TYPE_STATUS, f"파일 로드 완료: {os.path.basename(filepath)}")
                elif msg_type == MSG_TYPE_ERROR:
                    error_message = data
                    messagebox.showerror("오류 발생", error_message)
                    self.put_message_in_queue(MSG_TYPE_STATUS, f"오류: {str(error_message)[:70]}...")
                elif msg_type == MSG_TYPE_OPERATION_COMPLETE:
                    self.toggle_main_buttons_state(tk.NORMAL)
                    self.cancel_button.config(state=tk.DISABLED)
                    self.progress_var.set(0)
                    if data == "cancelled":
                         self.put_message_in_queue(MSG_TYPE_STATUS, "작업이 사용자에 의해 취소되었습니다.")
                    elif data == "error":
                         self.put_message_in_queue(MSG_TYPE_STATUS, "작업 중 오류 발생하여 중단됨.")
                    self.current_operation_thread = None
        except queue.Empty:
            pass
        finally:
            self.master.after(100, self.process_message_queue)


    def load_initial_config_gui(self):
        self.config = load_config()
        self.api_key = self.config.get(API_KEY_NAME_IN_CONFIG, "")
        self.current_chunk_size = self.config.get(CHUNK_SIZE_NAME_IN_CONFIG, DEFAULT_CHUNK_SIZE)
        
        if hasattr(self, 'api_key_entry') and self.api_key:
            self.api_key_entry.delete(0, tk.END)
            self.api_key_entry.insert(0, self.api_key)

        if hasattr(self, 'chunk_size_var'):
            self.chunk_size_var.set(self.current_chunk_size)

        # 용어집 파일 로드 및 리스트박스 채우기
        active_files_from_config = self.config.get(ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG, [])
        self.glossary_manager.set_active_glossary_files(active_files_from_config)
        self._update_glossary_listbox()

        # 프롬프트 콤보박스 설정
        selected_prompt_id = self.config.get(SELECTED_PROMPT_ID_NAME_IN_CONFIG)
        if selected_prompt_id:
            self.current_selected_prompt_name = self.prompt_manager.get_prompt_name_by_id(selected_prompt_id)
        elif self.available_prompt_names:
            default_prompt_id = self.prompt_manager.get_default_prompt_id()
            if default_prompt_id: # 기본 ID가 있는 경우
                self.current_selected_prompt_name = self.prompt_manager.get_prompt_name_by_id(default_prompt_id)
                self.config[SELECTED_PROMPT_ID_NAME_IN_CONFIG] = default_prompt_id
                # save_config(self.config) # 로드 시 자동 저장은 지양
        
        if hasattr(self, 'prompt_combobox_var') and self.current_selected_prompt_name:
            if self.current_selected_prompt_name in self.available_prompt_names:
                self.prompt_combobox_var.set(self.current_selected_prompt_name)
            elif self.available_prompt_names:
                first_available_prompt = self.available_prompt_names[0]
                self.prompt_combobox_var.set(first_available_prompt)
                self.current_selected_prompt_name = first_available_prompt
                # 이 경우, config의 ID도 첫번째 프롬프트 ID로 업데이트 필요
                first_prompt_id = self.prompt_manager.prompts[0]['id'] if self.prompt_manager.prompts else None
                if first_prompt_id:
                    self.config[SELECTED_PROMPT_ID_NAME_IN_CONFIG] = first_prompt_id
                    # save_config(self.config)
        elif self.available_prompt_names : # 선택된 이름도 없고, 저장된 ID도 없으면 첫번째로
             first_available_prompt = self.available_prompt_names[0]
             self.prompt_combobox_var.set(first_available_prompt)
             self.current_selected_prompt_name = first_available_prompt
             first_prompt_id = self.prompt_manager.prompts[0]['id'] if self.prompt_manager.prompts else None
             if first_prompt_id:
                self.config[SELECTED_PROMPT_ID_NAME_IN_CONFIG] = first_prompt_id

    def update_initial_status_message(self):
        # ... (이전과 동일) ...
        if not self.api_key:
            self.put_message_in_queue(MSG_TYPE_STATUS, "API 키를 입력하고 저장해주세요.")
            messagebox.showinfo("API 키 필요", "Gemini API 키를 입력하고 'API 키 저장' 버튼을 눌러주세요.\nAPI 키가 없으면 번역 기능을 사용할 수 없습니다.")
            if hasattr(self, 'api_key_entry'): self.api_key_entry.focus_set()
        else:
            self.put_message_in_queue(MSG_TYPE_STATUS, "API 키 로드 완료. 번역 준비되었습니다.")


    def save_api_key_action_gui(self):
        # ... (이전과 동일) ...
        entered_key = self.api_key_entry.get().strip()
        if not entered_key:
            messagebox.showwarning("API 키 필요", "Gemini API 키를 입력해주세요.")
            return
        self.config[API_KEY_NAME_IN_CONFIG] = entered_key
        if save_config(self.config):
            self.api_key = entered_key
            self.put_message_in_queue(MSG_TYPE_STATUS, "API 키가 설정 파일에 저장되었습니다.")
            messagebox.showinfo("API 키 저장됨", "API 키가 성공적으로 저장되었습니다.")
        else:
            messagebox.showerror("저장 오류", "API 키를 설정 파일에 저장하는 데 실패했습니다.")
            self.put_message_in_queue(MSG_TYPE_STATUS, "오류: API 키 저장 실패")


    def on_chunk_size_changed(self):
        # ... (이전과 동일) ...
        try:
            new_size = self.chunk_size_var.get()
            self.current_chunk_size = new_size
            self.config[CHUNK_SIZE_NAME_IN_CONFIG] = new_size
            if save_config(self.config):
                self.put_message_in_queue(MSG_TYPE_STATUS, f"청크 크기가 {new_size}줄로 설정 및 저장되었습니다.")
            else:
                self.put_message_in_queue(MSG_TYPE_STATUS, f"청크 크기 {new_size}줄 설정 저장 실패.")
        except tk.TclError:
            self.put_message_in_queue(MSG_TYPE_STATUS, "잘못된 청크 크기 값입니다. 숫자를 입력하세요.")
            self.chunk_size_var.set(self.current_chunk_size)


    def on_prompt_selected(self, event=None):
        # ... (이전과 동일) ...
        selected_name = self.prompt_combobox_var.get()
        self.current_selected_prompt_name = selected_name
        selected_id = None
        for p in self.prompt_manager.prompts:
            if p['name'] == selected_name:
                selected_id = p['id']
                break
        if selected_id:
            self.config[SELECTED_PROMPT_ID_NAME_IN_CONFIG] = selected_id
            if save_config(self.config):
                self.put_message_in_queue(MSG_TYPE_STATUS, f"프롬프트 '{selected_name}' 선택 및 저장됨.")
            else:
                self.put_message_in_queue(MSG_TYPE_STATUS, f"프롬프트 '{selected_name}' 선택 저장 실패.")
        else:
            self.put_message_in_queue(MSG_TYPE_STATUS, f"선택한 프롬프트 '{selected_name}'의 ID를 찾을 수 없음.")


    def _update_glossary_listbox(self):
        if hasattr(self, 'glossary_listbox'):
            self.glossary_listbox.delete(0, END)
            for filepath in self.glossary_manager.active_glossary_files:
                self.glossary_listbox.insert(END, os.path.basename(filepath))

    def add_glossary_file_action(self):
        filepath = filedialog.askopenfilename(
            title="용어집 파일 선택 (CSV)", defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filepath:
            if filepath in self.glossary_manager.active_glossary_files:
                messagebox.showinfo("알림", "이미 추가된 용어집 파일입니다.")
                return
            if self.glossary_manager.load_glossary_file(filepath):
                self.glossary_manager.active_glossary_files.append(filepath)
                self.config[ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG] = self.glossary_manager.active_glossary_files
                if save_config(self.config):
                    self.put_message_in_queue(MSG_TYPE_STATUS, f"용어집 '{os.path.basename(filepath)}' 추가 및 저장됨.")
                else:
                    self.put_message_in_queue(MSG_TYPE_STATUS, f"용어집 추가 후 설정 저장 실패.")
                self._update_glossary_listbox()

    def remove_glossary_file_action(self):
        selected_indices = self.glossary_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("선택 필요", "제거할 용어집 파일을 목록에서 선택해주세요.")
            return
        selected_index = selected_indices[0]
        if 0 <= selected_index < len(self.glossary_manager.active_glossary_files):
            filepath_to_remove = self.glossary_manager.active_glossary_files[selected_index]
            if self.glossary_manager.remove_glossary_file(filepath_to_remove): # active_glossary_files에서도 제거됨
                self.config[ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG] = self.glossary_manager.active_glossary_files
                if save_config(self.config):
                     self.put_message_in_queue(MSG_TYPE_STATUS, f"용어집 '{os.path.basename(filepath_to_remove)}' 제거 및 저장됨.")
                else:
                     self.put_message_in_queue(MSG_TYPE_STATUS, f"용어집 제거 후 설정 저장 실패.")
                self._update_glossary_listbox()
        else:
            self.put_message_in_queue(MSG_TYPE_ERROR, "잘못된 용어집 선택입니다.")

    def toggle_main_buttons_state(self, state):
        # ... (이전과 동일) ...
        self.translate_button.config(state=state)
        self.load_file_button.config(state=state)


    def request_cancel_operation(self):
        # ... (이전과 동일) ...
        if self.current_operation_thread and self.current_operation_thread.is_alive():
            self.cancel_requested.set()
            self.put_message_in_queue(MSG_TYPE_STATUS, "작업 취소 요청 중...")
            self.cancel_button.config(state=tk.DISABLED)


    def _start_operation_thread(self, target_function, args_tuple):
        # ... (이전과 동일) ...
        if self.current_operation_thread and self.current_operation_thread.is_alive():
            messagebox.showwarning("작업 중", "이미 다른 작업이 진행 중입니다.")
            return False
        self.cancel_requested.clear()
        self.toggle_main_buttons_state(tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.current_operation_thread = threading.Thread(
            target=target_function, args=args_tuple, daemon=True
        )
        self.current_operation_thread.start()
        return True


    def translate_action_gui(self):
        # ... (이전과 동일) ...
        print(f"번역 시작 - 청크 크기: {chunk_size_to_use}")
        original_content = self.original_text_area.get("1.0", tk.END).strip()
        if not self.api_key:
            messagebox.showwarning("API 키 필요", "API 키를 입력하고 저장 버튼을 눌러주세요.")
            return
        if not original_content:
            messagebox.showwarning("입력 필요", "번역할 텍스트를 입력하거나 파일을 불러오세요.")
            return
        self.put_message_in_queue(MSG_TYPE_STATUS, "번역 시작... (스레드 준비 중)")
        chunk_size_to_use = self.current_chunk_size
        if self._start_operation_thread(self.translate_thread_target,
                                     (original_content, self.api_key, chunk_size_to_use)):
            self.put_message_in_queue(MSG_TYPE_STATUS, "번역 스레드 시작됨.")


    def translate_thread_target(self, original_content, api_key, chunk_size):
        operation_status = None
        try:
            self.put_message_in_queue(MSG_TYPE_STATUS, f"번역 작업 시작 (청크: {chunk_size}줄, 프롬프트: '{self.current_selected_prompt_name}')")
            prompt_template = self.prompt_manager.get_prompt_template_by_name(self.current_selected_prompt_name)
            if not prompt_template:
                self.put_message_in_queue(MSG_TYPE_STATUS, "경고: 선택된 프롬프트를 찾을 수 없어 기본 프롬프트 사용.")
                default_id = self.prompt_manager.get_default_prompt_id()
                prompt_template = self.prompt_manager.get_prompt_template_by_id(default_id if default_id else self.prompt_manager.prompts[0]['id']) # Fallback

            final_translation_raw = self.text_processor.translate_by_chunks(
                original_content, api_key, chunk_size, self.cancel_requested, prompt_template
            )

            if self.cancel_requested.is_set() or final_translation_raw == "CANCELLED_BY_TRANSLATOR":
                operation_status = "cancelled"
            elif final_translation_raw is not None:
                self.put_message_in_queue(MSG_TYPE_STATUS, "용어집 적용 중...")
                final_translation_with_glossary = self.glossary_manager.apply_glossary_to_text(
                    final_translation_raw
                )
                self.put_message_in_queue(MSG_TYPE_RESULT, final_translation_with_glossary)
                self.put_message_in_queue(MSG_TYPE_STATUS, "번역 및 용어집 적용 완료.")
            else:
                operation_status = "error"
        except Exception as e:
            operation_status = "error"
            self.put_message_in_queue(MSG_TYPE_ERROR, f"번역 스레드 예외: {e}")
        finally:
            self.put_message_in_queue(MSG_TYPE_OPERATION_COMPLETE, operation_status)


    def load_file_action_gui(self):
        # ... (이전과 동일) ...
        if self.unsaved_translation:
            if not messagebox.askokcancel("확인", "저장되지 않은 번역 내용이 있습니다. 계속 진행하시겠습니까?"):
                return
        filepath_selected = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not filepath_selected:
            self.put_message_in_queue(MSG_TYPE_STATUS, "파일 열기 취소됨.")
            return
        self.put_message_in_queue(MSG_TYPE_STATUS, "파일 로드 시작... (스레드 준비 중)")
        if self._start_operation_thread(self.load_file_thread_target, (filepath_selected,)):
             self.put_message_in_queue(MSG_TYPE_STATUS, "파일 로드 스레드 시작됨.")


    def load_file_thread_target(self, filepath_from_gui):
        # ... (이전과 동일) ...
        operation_status = None
        try:
            _fp, content, is_csv = self.file_handler.load_file_core(self.cancel_requested, filepath_from_gui)
            if self.cancel_requested.is_set():
                operation_status = "cancelled"
            elif _fp is not None:
                self.put_message_in_queue(MSG_TYPE_FILE_LOAD_RESULT, (_fp, content, is_csv))
            else:
                operation_status = "error"
        except Exception as e:
            operation_status = "error"
            self.put_message_in_queue(MSG_TYPE_ERROR, f"파일 로드 스레드 예외: {e}")
        finally:
            self.put_message_in_queue(MSG_TYPE_OPERATION_COMPLETE, operation_status)


    def save_file_action_gui(self):
        # ... (이전과 동일) ...
        content_to_save = self.translated_text_area.get("1.0", tk.END).strip()
        if not content_to_save:
            messagebox.showwarning("저장 불가", "저장할 번역된 내용이 없습니다.")
            return

        initial_filename = "translated_output.txt"
        if self.is_csv_mode:
             initial_filename = "translated_output.csv"
        
        filepath_to_save = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=initial_filename,
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filepath_to_save:
            self.put_message_in_queue(MSG_TYPE_STATUS, "파일 저장 취소됨.")
            return

        if self.file_handler.save_file(content_to_save, initial_filename, filepath_to_save):
            self.unsaved_translation = False


    def on_closing(self):
        # ... (이전과 동일) ...
        if self.current_operation_thread and self.current_operation_thread.is_alive():
            if messagebox.askokcancel("작업 중 종료", "진행 중인 작업이 있습니다. 정말로 종료하시겠습니까?\n(작업이 즉시 중단되지 않을 수 있습니다.)"):
                self.request_cancel_operation()
                self.master.after(500, self.master.destroy) 
            return

        if self.unsaved_translation:
            if messagebox.askokcancel("종료 확인", "저장되지 않은 번역 내용이 있습니다. 정말로 종료하시겠습니까?"):
                self.master.destroy()
        else:
            self.master.destroy()