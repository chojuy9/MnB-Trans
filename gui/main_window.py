import tkinter as tk
from tkinter import scrolledtext, messagebox, Spinbox, ttk, filedialog, Listbox, END, SINGLE, Scrollbar
from tkinter import font as tkfont # 폰트 관리를 위해
import os
import threading
import queue
import time
import sys # PyInstaller 경로 처리를 위해

# core 모듈에서 필요한 클래스 및 함수 임포트
from core.config_manager import (
    load_config, save_config,
    API_KEY_NAME_IN_CONFIG, CHUNK_SIZE_NAME_IN_CONFIG, SELECTED_PROMPT_ID_NAME_IN_CONFIG,
    ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG, SELECTED_MODEL_ID_NAME_IN_CONFIG,
    DEFAULT_CHUNK_SIZE, USER_DATA_DIR, AVAILABLE_MODELS, DEFAULT_MODEL_ID
)
from core.prompt_manager import PromptManager
from core.translator import TextProcessor
from core.file_handler import FileHandler
from core.glossary_manager import GlossaryManager

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
        master.title("M&B 모드 번역기 (v1.9 - 모델 선택)") # 버전 업데이트
        master.geometry("800x780")

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
        self.current_selected_model_id = DEFAULT_MODEL_ID

        self.glossary_manager = GlossaryManager(self)
        self.text_processor = TextProcessor(self)
        self.file_handler = FileHandler(self)

        self.default_font_family = "Noto Sans KR" # 또는 "Malgun Gothic", "Segoe UI", "Open Sans" 등
        self.default_font_size = 10
        self.default_font = (self.default_font_family, self.default_font_size)
        self.small_font = (self.default_font_family, self.default_font_size - 1) # 작은 폰트 (버튼 등)

        # 중세/고전 느낌의 포인트 폰트 (제목 등에 사용)
        self.title_font_family = "Georgia" # 또는 "Times New Roman", 특정 고딕 스타일 폰트 (설치 필요)
        self.title_font_size = 12
        self.title_font = (self.title_font_family, self.title_font_size, "bold")

        # Tkinter의 기본 폰트 설정 (일부 위젯에 영향)
        default_font_obj = tkfont.nametofont("TkDefaultFont")
        default_font_obj.configure(family=self.default_font_family, size=self.default_font_size)
        # text_font_obj = tkfont.nametofont("TkTextFont") # ScrolledText 등에 영향
        # text_font_obj.configure(family=self.default_font_family, size=self.default_font_size)

        # 색상 팔레트 (예시)
        self.color_bg_main = "#ECECEC"      # 주 배경 (밝은 회색)
        self.color_bg_frame = "#E0E0E0"     # 프레임 배경 (주 배경보다 약간 어둡게)
        self.color_bg_input = "white"       # 입력 필드 배경
        self.color_text_main = "#333333"    # 주 텍스트 (어두운 회색)
        self.color_text_label = "#555555"   # 라벨 텍스트 (중간 회색)
        self.color_text_title = "#4A3B31"   # 제목/강조 텍스트 (고풍스러운 갈색 계열)
        self.color_accent_medieval = "#8B4513" # 중세풍 포인트 (SaddleBrown)
        self.color_accent_hover = "#A0522D"   # 마우스 오버 (Sienna)
        self.color_border = "#A9A9A9"       # 테두리 색 (DarkGray)

        # ttk 스타일에도 폰트 적용
        self.style = ttk.Style()
        # self.style.theme_use('clam') # 테마에 따라 기본 폰트가 다를 수 있음

        self.style.configure(".", font=self.default_font, background=self.color_bg_main, foreground=self.color_text_main) # 모든 ttk 위젯에 기본 폰트
        self.style.configure("TFrame", background=self.color_bg_frame)
        self.style.configure("TLabel", background=self.color_bg_frame, foreground=self.color_text_label, font=self.default_font)
        self.style.configure("TButton", font=self.default_font, padding=5)
        self.style.configure("TEntry", font=self.default_font) # ttk.Entry가 있다면
        self.style.configure("TCombobox", font=self.default_font, padding=3)
        self.style.configure("TProgressbar", troughcolor=self.color_border, background=self.color_accent_medieval) # 진행바 색상
        # Spinbox는 ttk 위젯이 아닐 수 있으므로, 직접 font 옵션 설정 필요
        # 중세풍 버튼 스타일 정의 (이름 변경)
        self.style.configure("Medieval.TButton",
            foreground="white",
            background=self.color_accent_medieval,
            font=self.default_font, # 기본 버튼 폰트 유지 또는 (self.default_font_family, self.default_font_size, "bold")
            relief=tk.RAISED,
            borderwidth=2,
            padding=(8, 4)) # 가로, 세로 패딩
        self.style.map("Medieval.TButton",
            background=[('active', self.color_accent_hover), ('pressed', self.color_accent_hover)],
            relief=[('pressed', tk.SUNKEN), ('active', tk.RAISED)])

        # 일반 버튼 스타일 (덜 강조)
        self.style.configure("Standard.TButton",
            foreground=self.color_text_main,
            background="#DCDCDC", # 밝은 회색 버튼
            font=self.small_font,
            padding=(6,3))
        self.style.map("Standard.TButton",
            background=[('active', "#C0C0C0")])

        # 창 전체 배경 설정
        self.master.configure(bg=self.color_bg_main)

        self._setup_ui()
        self.load_initial_config_gui()
        self.update_initial_status_message()

        master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.after(100, self.process_message_queue)

    def _setup_ui(self):
        # --- 하단 상태 표시줄 및 진행률 표시줄 ---
        bottom_status_frame = tk.Frame(self.master, bg=self.color_bg_main) # tk.Frame 사용
        bottom_status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(5,10)) # 하단 여백 추가

        self.status_label = tk.Label(bottom_status_frame, text="상태: 초기화 중...",
                                     bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                     font=self.small_font, bg="#D0D0D0", fg=self.color_text_main) # 약간 다른 배경
        self.status_label.pack(side=tk.TOP, fill=tk.X)

        self.progress_var = tk.DoubleVar()
        self.progressbar = ttk.Progressbar(bottom_status_frame, variable=self.progress_var, maximum=100,
                                           style="TProgressbar") # 위에서 정의한 스타일 적용
        self.progressbar.pack(side=tk.TOP, fill=tk.X, pady=(3,0))

        # --- 상단 설정 영역 (전체 프레임) ---
        # relief와 borderwidth로 약간의 입체감/구분선 효과
        settings_outer_frame = tk.Frame(self.master, bg=self.color_bg_frame,
                                        relief=tk.GROOVE, borderwidth=1, padx=5, pady=5)
        settings_outer_frame.pack(fill=tk.X, padx=10, pady=(10,5))

        # 설정 영역 - 첫 번째 줄
        settings_row1_frame = tk.Frame(settings_outer_frame, bg=self.color_bg_frame) # tk.Frame 사용
        settings_row1_frame.pack(fill=tk.X)

        # API 키 입력 프레임
        api_key_frame = tk.Frame(settings_row1_frame, bg=self.color_bg_frame) # tk.Frame 사용
        api_key_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,10))
        api_label = tk.Label(api_key_frame, text="Gemini API Key:", font=self.default_font,
                              bg=self.color_bg_frame, fg=self.color_text_label) # tk.Label
        api_label.pack(side=tk.LEFT, padx=(0, 5))
        self.api_key_entry = tk.Entry(api_key_frame, width=25, show="*",
                                      font=self.default_font, bg=self.color_bg_input, fg=self.color_text_main,
                                      relief=tk.SUNKEN, borderwidth=1) # tk.Entry
        self.api_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        # "키 저장" 버튼은 ttk.Button으로 변경하고 Standard 스타일 적용
        self.save_api_key_button = ttk.Button(api_key_frame, text="키 저장",
                                             command=self.save_api_key_action_gui,
                                             style="Standard.TButton")
        self.save_api_key_button.pack(side=tk.LEFT, padx=(5, 0))

        # 청크 크기 설정 프레임
        chunk_size_frame = tk.Frame(settings_row1_frame, bg=self.color_bg_frame) # tk.Frame
        chunk_size_frame.pack(side=tk.LEFT)
        chunk_label = tk.Label(chunk_size_frame, text="청크(줄):", font=self.default_font,
                                bg=self.color_bg_frame, fg=self.color_text_label) # tk.Label
        chunk_label.pack(side=tk.LEFT, padx=(0, 5))
        self.chunk_size_var = tk.IntVar()
        self.chunk_size_spinbox = tk.Spinbox( # tk.Spinbox는 ttk 스타일 직접 적용 어려움
            chunk_size_frame, from_=10, to=100, increment=10,
            textvariable=self.chunk_size_var, width=4, command=self.on_chunk_size_changed,
            font=self.default_font, bg=self.color_bg_input, fg=self.color_text_main,
            relief=tk.SUNKEN, borderwidth=1, buttonbackground=self.color_bg_frame # 스핀박스 버튼 배경
        )
        self.chunk_size_spinbox.pack(side=tk.LEFT)

        # 설정 영역 - 두 번째 줄
        settings_row2_frame = tk.Frame(settings_outer_frame, bg=self.color_bg_frame) # tk.Frame
        settings_row2_frame.pack(fill=tk.X, pady=(8,0)) # 줄 간 간격

        # 프롬프트 선택 프레임
        prompt_select_frame = tk.Frame(settings_row2_frame, bg=self.color_bg_frame) # tk.Frame
        prompt_select_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,10))
        prompt_label = ttk.Label(prompt_select_frame, text="번역 프롬프트:", style="TLabel") # ttk.Label
        prompt_label.pack(side=tk.LEFT, padx=(0,5))
        self.prompt_combobox_var = tk.StringVar()
        self.prompt_combobox = ttk.Combobox(
            prompt_select_frame, textvariable=self.prompt_combobox_var,
            values=self.available_prompt_names, state="readonly", style="TCombobox",
            font=self.default_font # Combobox 폰트는 직접 지정하는 것이 더 확실할 수 있음
        )
        if self.available_prompt_names:
            self.prompt_combobox.bind("<<ComboboxSelected>>", self.on_prompt_selected)
        self.prompt_combobox.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # 모델 선택 프레임
        model_select_frame = tk.Frame(settings_row2_frame, bg=self.color_bg_frame) # tk.Frame
        model_select_frame.pack(side=tk.LEFT, expand=True, fill=tk.X) # side=tk.LEFT로 수정
        model_label = ttk.Label(model_select_frame, text="번역 모델:", style="TLabel") # ttk.Label
        model_label.pack(side=tk.LEFT, padx=(0,5))
        self.model_combobox_var = tk.StringVar()
        self.model_display_names = list(AVAILABLE_MODELS.values())
        self.model_ids = list(AVAILABLE_MODELS.keys())
        self.model_combobox = ttk.Combobox(
            model_select_frame, textvariable=self.model_combobox_var,
            values=self.model_display_names, state="readonly", style="TCombobox",
            font=self.default_font
        )
        if self.model_display_names:
            self.model_combobox.bind("<<ComboboxSelected>>", self.on_model_selected)
        self.model_combobox.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # --- 용어집 설정 영역 ---
        glossary_main_frame = tk.Frame(self.master, bg=self.color_bg_frame,
                                       relief=tk.GROOVE, borderwidth=1, padx=5, pady=5)
        glossary_main_frame.pack(fill=tk.X, padx=10, pady=5)
        glossary_label = tk.Label(glossary_main_frame, text="활성 용어집 파일 (CSV):",
                                  font=self.title_font, fg=self.color_text_title, # 제목 폰트/색상
                                  bg=self.color_bg_frame) # tk.Label
        glossary_label.pack(anchor=tk.W, pady=(0,3)) # 라벨 아래 약간의 여백

        glossary_ui_frame = tk.Frame(glossary_main_frame, bg=self.color_bg_frame) # tk.Frame
        glossary_ui_frame.pack(fill=tk.X, expand=True)

        listbox_frame = tk.Frame(glossary_ui_frame, bg=self.color_bg_frame) # tk.Frame
        listbox_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        self.glossary_listbox = tk.Listbox( # tk.Listbox
            listbox_frame, selectmode=SINGLE, height=3, exportselection=False,
            font=self.default_font, bg=self.color_bg_input, fg=self.color_text_main,
            selectbackground=self.color_accent_medieval, selectforeground="white", # 선택 시 색상
            relief=tk.SUNKEN, borderwidth=1
        )
        self.glossary_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # 스크롤바도 ttk.Scrollbar로 변경 가능 (더 일관된 모양)
        glossary_scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.glossary_listbox.yview)
        # self.style.configure("Vertical.TScrollbar", background=self.color_bg_frame, troughcolor=self.color_border)
        # glossary_scrollbar.configure(style="Vertical.TScrollbar") # 필요시 스타일 적용
        glossary_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.glossary_listbox.config(yscrollcommand=glossary_scrollbar.set)

        glossary_button_frame = tk.Frame(glossary_ui_frame, bg=self.color_bg_frame) # tk.Frame
        glossary_button_frame.pack(side=tk.LEFT, anchor=tk.N, padx=(5,0))
        # 용어집 추가/제거 버튼도 ttk.Button Standard 스타일로
        add_glossary_button = ttk.Button(glossary_button_frame, text="추가",
                                         command=self.add_glossary_file_action, width=5,
                                         style="Standard.TButton")
        add_glossary_button.pack(fill=tk.X, pady=(0,3))
        remove_glossary_button = ttk.Button(glossary_button_frame, text="제거",
                                            command=self.remove_glossary_file_action, width=5,
                                            style="Standard.TButton")
        remove_glossary_button.pack(fill=tk.X)


        # --- 텍스트 영역 ---
        text_frame = tk.Frame(self.master, bg=self.color_bg_main) # tk.Frame
        text_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        original_text_frame = tk.Frame(text_frame, bg=self.color_bg_frame, relief=tk.SUNKEN, borderwidth=1) # tk.Frame
        original_text_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 5))
        original_label = tk.Label(original_text_frame, text="원본 텍스트 (영어)",
                                   font=self.title_font, fg=self.color_text_title, # 제목 폰트/색상
                                   bg=self.color_bg_frame) # tk.Label
        original_label.pack(anchor=tk.W, padx=5, pady=(2,2))
        self.original_text_area = scrolledtext.ScrolledText(
            original_text_frame, wrap=tk.WORD, height=10,
            font=self.default_font, bg=self.color_bg_input, fg=self.color_text_main,
            relief=tk.FLAT, borderwidth=0 # 내부 테두리 제거, 프레임이 테두리 역할
        )
        self.original_text_area.pack(expand=True, fill=tk.BOTH, padx=5, pady=(0,5))


        translated_text_frame = tk.Frame(text_frame, bg=self.color_bg_frame, relief=tk.SUNKEN, borderwidth=1) # tk.Frame
        translated_text_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(5, 0))
        translated_label = tk.Label(translated_text_frame, text="번역된 텍스트 (한국어)",
                                     font=self.title_font, fg=self.color_text_title,
                                     bg=self.color_bg_frame) # tk.Label
        translated_label.pack(anchor=tk.W, padx=5, pady=(2,2))
        self.translated_text_area = scrolledtext.ScrolledText(
            translated_text_frame, wrap=tk.WORD, height=10,
            font=self.default_font, bg=self.color_bg_input, fg=self.color_text_main,
            relief=tk.FLAT, borderwidth=0
        )
        self.translated_text_area.pack(expand=True, fill=tk.BOTH, padx=5, pady=(0,5))
        self.translated_text_area.config(state=tk.DISABLED)


        # --- 주요 액션 버튼 영역 ---
        action_button_frame = tk.Frame(self.master, bg=self.color_bg_main) # tk.Frame
        action_button_frame.pack(fill=tk.X, padx=10, pady=5)

        # 파일 열기/저장 버튼은 ttk.Button Standard 스타일
        self.load_file_button = ttk.Button(action_button_frame, text="파일 열기",
                                           command=self.load_file_action_gui, style="Standard.TButton")
        self.load_file_button.pack(side=tk.LEFT, padx=(0,5))
        self.save_file_button = ttk.Button(action_button_frame, text="번역 결과 저장",
                                           command=self.save_file_action_gui, style="Standard.TButton")
        self.save_file_button.pack(side=tk.LEFT, padx=(0,5))

        # "번역하기" 버튼은 가장 중요하므로 Medieval.TButton 스타일
        self.translate_button = ttk.Button(action_button_frame, text="번역하기",
                                           command=self.translate_action_gui,
                                           style="Medieval.TButton") # 강조 스타일
        self.translate_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10,0)) # 약간 더 여백


        # --- 작업 제어 버튼 영역 ---
        control_button_frame = tk.Frame(self.master, bg=self.color_bg_main) # tk.Frame
        control_button_frame.pack(fill=tk.X, padx=10, pady=(0,5))
        # 작업 취소 버튼도 Standard 스타일 (덜 강조)
        self.cancel_button = ttk.Button(control_button_frame, text="작업 취소",
                                        command=self.request_cancel_operation, state=tk.DISABLED,
                                        style="Standard.TButton")
        self.cancel_button.pack(side=tk.RIGHT)

    def put_message_in_queue(self, msg_type, data=None):
        self.message_queue.put((msg_type, data))

    def process_message_queue(self):
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

        active_files_from_config = self.config.get(ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG, [])
        self.glossary_manager.set_active_glossary_files(active_files_from_config)
        self._update_glossary_listbox()

        selected_prompt_id = self.config.get(SELECTED_PROMPT_ID_NAME_IN_CONFIG)
        if selected_prompt_id:
            self.current_selected_prompt_name = self.prompt_manager.get_prompt_name_by_id(selected_prompt_id)
        elif self.available_prompt_names:
            default_prompt_id = self.prompt_manager.get_default_prompt_id()
            if default_prompt_id:
                self.current_selected_prompt_name = self.prompt_manager.get_prompt_name_by_id(default_prompt_id)
                self.config[SELECTED_PROMPT_ID_NAME_IN_CONFIG] = default_prompt_id
        if hasattr(self, 'prompt_combobox_var') and self.current_selected_prompt_name:
            if self.current_selected_prompt_name in self.available_prompt_names:
                self.prompt_combobox_var.set(self.current_selected_prompt_name)
            elif self.available_prompt_names:
                self.prompt_combobox_var.set(self.available_prompt_names[0])
                self.current_selected_prompt_name = self.available_prompt_names[0]
                first_prompt_id = self.prompt_manager.prompts[0]['id'] if self.prompt_manager.prompts else None
                if first_prompt_id: self.config[SELECTED_PROMPT_ID_NAME_IN_CONFIG] = first_prompt_id
        elif self.available_prompt_names :
             self.prompt_combobox_var.set(self.available_prompt_names[0])
             self.current_selected_prompt_name = self.available_prompt_names[0]
             first_prompt_id = self.prompt_manager.prompts[0]['id'] if self.prompt_manager.prompts else None
             if first_prompt_id: self.config[SELECTED_PROMPT_ID_NAME_IN_CONFIG] = first_prompt_id

        self.current_selected_model_id = self.config.get(SELECTED_MODEL_ID_NAME_IN_CONFIG, DEFAULT_MODEL_ID)
        if hasattr(self, 'model_combobox_var') and self.current_selected_model_id:
            display_name_to_set = AVAILABLE_MODELS.get(self.current_selected_model_id)
            if display_name_to_set and display_name_to_set in self.model_display_names:
                self.model_combobox_var.set(display_name_to_set)
            elif self.model_display_names:
                self.model_combobox_var.set(self.model_display_names[0])
                self.current_selected_model_id = self.model_ids[0]
                self.config[SELECTED_MODEL_ID_NAME_IN_CONFIG] = self.current_selected_model_id

    def update_initial_status_message(self):
        if not self.api_key:
            self.put_message_in_queue(MSG_TYPE_STATUS, "API 키를 입력하고 저장해주세요.")
            messagebox.showinfo("API 키 필요", "Gemini API 키를 입력하고 'API 키 저장' 버튼을 눌러주세요.\nAPI 키가 없으면 번역 기능을 사용할 수 없습니다.")
            if hasattr(self, 'api_key_entry'): self.api_key_entry.focus_set()
        else:
            self.put_message_in_queue(MSG_TYPE_STATUS, "API 키 로드 완료. 번역 준비되었습니다.")

    def save_api_key_action_gui(self):
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
            
    def on_model_selected(self, event=None):
        selected_display_name = self.model_combobox_var.get()
        for model_id, display_name in AVAILABLE_MODELS.items():
            if display_name == selected_display_name:
                self.current_selected_model_id = model_id
                self.config[SELECTED_MODEL_ID_NAME_IN_CONFIG] = model_id
                if save_config(self.config):
                    self.put_message_in_queue(MSG_TYPE_STATUS, f"번역 모델 '{selected_display_name}' 선택 및 저장됨.")
                else:
                    self.put_message_in_queue(MSG_TYPE_STATUS, f"번역 모델 '{selected_display_name}' 선택 저장 실패.")
                return
        self.put_message_in_queue(MSG_TYPE_STATUS, f"선택한 모델 '{selected_display_name}'의 ID를 찾을 수 없음.")

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
            if self.glossary_manager.remove_glossary_file(filepath_to_remove):
                self.config[ACTIVE_GLOSSARY_FILES_NAME_IN_CONFIG] = self.glossary_manager.active_glossary_files
                if save_config(self.config):
                     self.put_message_in_queue(MSG_TYPE_STATUS, f"용어집 '{os.path.basename(filepath_to_remove)}' 제거 및 저장됨.")
                else:
                     self.put_message_in_queue(MSG_TYPE_STATUS, f"용어집 제거 후 설정 저장 실패.")
                self._update_glossary_listbox()
        else:
            self.put_message_in_queue(MSG_TYPE_ERROR, "잘못된 용어집 선택입니다.")

    def toggle_main_buttons_state(self, state):
        self.translate_button.config(state=state)
        self.load_file_button.config(state=state)
        # save_api_key_button, chunk_size_spinbox 등은 항상 활성화 유지

    def request_cancel_operation(self):
        if self.current_operation_thread and self.current_operation_thread.is_alive():
            self.cancel_requested.set()
            self.put_message_in_queue(MSG_TYPE_STATUS, "작업 취소 요청 중...")
            self.cancel_button.config(state=tk.DISABLED)

    def _start_operation_thread(self, target_function, args_tuple):
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
        operation_status = None # 작업 성공/실패/취소 상태 기록
        try:
            # 사용자 알림은 TextProcessor 내부에서 처리하므로 여기서는 제거 또는 간소화
            # model_display = AVAILABLE_MODELS.get(self.current_selected_model_id, self.current_selected_model_id)
            # self.put_message_in_queue(MSG_TYPE_STATUS,
            #     f"번역 작업 준비 (프롬프트: '{self.current_selected_prompt_name}', 모델: '{model_display}')")
            
            prompt_template = self.prompt_manager.get_prompt_template_by_name(self.current_selected_prompt_name)
            # 프롬프트 템플릿이 없는 경우 TextProcessor 내부에서 기본값 처리 및 알림

            final_translation_raw = self.text_processor.translate_by_chunks(
                original_content, api_key, chunk_size, 
                self.cancel_requested, prompt_template,
                model_name_override=self.current_selected_model_id # 항상 모델 ID 전달
            )

            if final_translation_raw == "CANCELLED_BY_TRANSLATOR": # 취소 시 특별 문자열 확인
                operation_status = "cancelled"
            elif final_translation_raw is not None: # None이 아니면 (성공 또는 부분 성공)
                self.put_message_in_queue(MSG_TYPE_STATUS, "번역 결과에 용어집 적용 중...")
                final_translation_with_glossary = self.glossary_manager.apply_glossary_to_text(
                    final_translation_raw
                )
                self.put_message_in_queue(MSG_TYPE_RESULT, final_translation_with_glossary)
                self.put_message_in_queue(MSG_TYPE_STATUS, "번역 및 용어집 적용 완료!") # 최종 완료 메시지
            else: # final_translation_raw가 None인 경우 (심각한 오류로 전체 번역 실패)
                operation_status = "error"
                # TextProcessor 내부에서 이미 오류 메시지를 큐에 넣었을 것이므로, 여기서는 상태만 업데이트
                self.put_message_in_queue(MSG_TYPE_STATUS, "번역 작업 중 심각한 오류가 발생하여 중단되었습니다.")
        
        except Exception as e: # GUI 스레드에서 예상치 못한 예외 발생 시
            operation_status = "error"
            self.put_message_in_queue(MSG_TYPE_ERROR, f"번역 처리 스레드 외부에서 예외 발생: {e}")
        finally:
            # 작업 완료 메시지를 큐에 넣어 GUI 스레드에서 버튼 상태 등을 복구하도록 함
            self.put_message_in_queue(MSG_TYPE_OPERATION_COMPLETE, operation_status)

    def load_file_action_gui(self):
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