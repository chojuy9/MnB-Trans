# gui/main_window.py
import tkinter as tk
from tkinter import scrolledtext, messagebox, Spinbox, ttk # ttk 임포트 for Progressbar
import os
import threading
import queue
import time # 취소 기능의 부드러운 종료를 위해 (선택적)

from core.config_manager import load_config, save_config, DEFAULT_CHUNK_SIZE, API_KEY_NAME_IN_CONFIG, CHUNK_SIZE_NAME_IN_CONFIG
from core.translator import TextProcessor # TextProcessor는 app_instance를 받음
from core.file_handler import FileHandler # FileHandler도 app_instance를 받음

# 메시지 타입 정의 (큐에서 사용)
MSG_TYPE_PROGRESS = "progress"
MSG_TYPE_STATUS = "status"
MSG_TYPE_RESULT = "result"
MSG_TYPE_ERROR = "error"
MSG_TYPE_FILE_LOAD_RESULT = "file_load_result"
MSG_TYPE_OPERATION_COMPLETE = "operation_complete" # 작업 완료 후 버튼 상태 변경용

class CoreTranslatorApp:
    def __init__(self, master):
        self.master = master
        master.title("M&B 모드 번역기 (v1.6 - 고급 기능)")
        master.geometry("800x720") # 진행률 바, 취소 버튼 공간 고려

        self.config = {}
        self.api_key = ""
        self.current_chunk_size = DEFAULT_CHUNK_SIZE
        self.unsaved_translation = False
        self.is_csv_mode = False

        # 스레드 작업 관리
        self.current_operation_thread = None
        self.cancel_requested = threading.Event() # 취소 요청 플래그
        self.message_queue = queue.Queue() # 모든 메시지를 하나의 큐로 통합

        # 핵심 로직 클래스 인스턴스화 (self를 전달하여 콜백 가능하도록)
        self.text_processor = TextProcessor(self)
        self.file_handler = FileHandler(self)

        # --- 상태 표시줄 ---
        self.status_label = tk.Label(master, text="상태: 초기화 중...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0,5))

        # --- 진행률 바 ---
        self.progress_var = tk.DoubleVar()
        self.progressbar = ttk.Progressbar(master, variable=self.progress_var, maximum=100)
        self.progressbar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0,5))


        self.load_initial_config_gui()

        # --- 설정 프레임 (API 키와 청크 크기) ---
        settings_frame = tk.Frame(master)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        # ... (API 키, 청크 크기 Spinbox UI 기존과 동일) ...
        api_key_frame = tk.Frame(settings_frame)
        api_key_frame.pack(fill=tk.X)
        api_label = tk.Label(api_key_frame, text="Gemini API Key:")
        api_label.pack(side=tk.LEFT, padx=(0, 5))
        self.api_key_entry = tk.Entry(api_key_frame, width=40, show="*")
        self.api_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        if self.api_key:
            self.api_key_entry.insert(0, self.api_key)
        self.save_api_key_button = tk.Button(api_key_frame, text="API 키 저장", command=self.save_api_key_action_gui)
        self.save_api_key_button.pack(side=tk.LEFT, padx=(5, 0))

        chunk_size_frame = tk.Frame(settings_frame)
        chunk_size_frame.pack(fill=tk.X, pady=(5,0))
        chunk_label = tk.Label(chunk_size_frame, text="청크 크기 (줄 수, 10-100):")
        chunk_label.pack(side=tk.LEFT, padx=(0, 5))
        self.chunk_size_var = tk.IntVar(value=self.current_chunk_size)
        self.chunk_size_spinbox = Spinbox(
            chunk_size_frame, from_=10, to=100, increment=10,
            textvariable=self.chunk_size_var, width=5, command=self.on_chunk_size_changed
        )
        self.chunk_size_spinbox.pack(side=tk.LEFT)


        # --- 텍스트 영역 프레임 ---
        text_frame = tk.Frame(master)
        text_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        # ... (original_text_area, translated_text_area 생성 기존과 동일) ...
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
        action_button_frame = tk.Frame(master) # 작업 버튼들
        action_button_frame.pack(fill=tk.X, padx=10, pady=5)
        self.load_file_button = tk.Button(action_button_frame, text="파일 열기", command=self.load_file_action_gui)
        self.load_file_button.pack(side=tk.LEFT, padx=(0,5))
        self.save_file_button = tk.Button(action_button_frame, text="번역 결과 저장", command=self.save_file_action_gui)
        self.save_file_button.pack(side=tk.LEFT, padx=(0,5))
        self.translate_button = tk.Button(action_button_frame, text="번역하기", command=self.translate_action_gui, font=("Arial", 10, "bold"))
        self.translate_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5,0)) # 위치 변경

        control_button_frame = tk.Frame(master) # 제어 버튼들
        control_button_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        self.cancel_button = tk.Button(control_button_frame, text="작업 취소", command=self.request_cancel_operation, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.RIGHT)


        self.update_initial_status_message()
        master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.after(100, self.process_message_queue) # 메시지 큐 처리 시작


    def put_message_in_queue(self, msg_type, data=None):
        """스레드에서 GUI 업데이트를 위해 메시지를 큐에 넣습니다."""
        self.message_queue.put((msg_type, data))

    def process_message_queue(self):
        try:
            while True: # 큐에 있는 모든 메시지 처리
                msg_type, data = self.message_queue.get_nowait()

                if msg_type == MSG_TYPE_STATUS:
                    self.status_label.config(text=f"상태: {data}")
                elif msg_type == MSG_TYPE_PROGRESS:
                    # data는 (현재값, 최대값) 튜플 또는 현재 퍼센트 값
                    if isinstance(data, tuple):
                        current, maximum = data
                        if maximum > 0:
                            percentage = (current / maximum) * 100
                            self.progress_var.set(percentage)
                        else:
                            self.progress_var.set(0)
                    else: # 퍼센트 값 직접 전달
                        self.progress_var.set(data)
                elif msg_type == MSG_TYPE_RESULT: # 번역 결과
                    final_translation = data
                    self.translated_text_area.config(state=tk.NORMAL)
                    self.translated_text_area.delete("1.0", tk.END)
                    self.translated_text_area.insert(tk.END, final_translation.strip())
                    self.translated_text_area.config(state=tk.DISABLED)
                    self.unsaved_translation = True
                elif msg_type == MSG_TYPE_FILE_LOAD_RESULT: # 파일 로드 결과
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
                    # 실패 경우는 FileHandler에서 이미 메시지박스 띄우고 상태 업데이트 할 수 있음
                elif msg_type == MSG_TYPE_ERROR:
                    error_message = data
                    messagebox.showerror("오류 발생", error_message) # 메인 스레드에서 오류 메시지박스
                    self.put_message_in_queue(MSG_TYPE_STATUS, f"오류: {error_message[:50]}...") # 상태창에도 간략히
                elif msg_type == MSG_TYPE_OPERATION_COMPLETE:
                    self.toggle_main_buttons_state(tk.NORMAL)
                    self.cancel_button.config(state=tk.DISABLED)
                    self.progress_var.set(0) # 작업 완료 후 프로그레스 바 초기화
                    if data == "cancelled":
                         self.put_message_in_queue(MSG_TYPE_STATUS, "작업이 사용자에 의해 취소되었습니다.")
                    elif data == "error":
                         self.put_message_in_queue(MSG_TYPE_STATUS, "작업 중 오류 발생하여 중단됨.")
                    # data가 None이거나 다른 값이면 일반 완료 메시지
                    self.current_operation_thread = None # 현재 작업 스레드 참조 해제

        except queue.Empty:
            pass
        finally:
            self.master.after(100, self.process_message_queue) # 주기적 확인


    def load_initial_config_gui(self):
        # ... (기존 코드와 유사, self.config 사용) ...
        self.config = load_config()
        self.api_key = self.config.get(API_KEY_NAME_IN_CONFIG, "")
        self.current_chunk_size = self.config.get(CHUNK_SIZE_NAME_IN_CONFIG, DEFAULT_CHUNK_SIZE)
        if hasattr(self, 'chunk_size_var'):
            self.chunk_size_var.set(self.current_chunk_size)

    def update_initial_status_message(self):
        # ... (기존 코드와 유사) ...
        if not self.api_key:
            self.put_message_in_queue(MSG_TYPE_STATUS, "API 키를 입력하고 저장해주세요.")
            messagebox.showinfo("API 키 필요", "Gemini API 키를 입력하고 'API 키 저장' 버튼을 눌러주세요.\nAPI 키가 없으면 번역 기능을 사용할 수 없습니다.")
            if hasattr(self, 'api_key_entry'): self.api_key_entry.focus_set()
        else:
            self.put_message_in_queue(MSG_TYPE_STATUS, "API 키 로드 완료. 번역 준비되었습니다.")


    def save_api_key_action_gui(self):
        # ... (기존 코드와 유사, self.config 사용, 메시지는 큐로) ...
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
            # ... (오류 처리) ...
            messagebox.showerror("저장 오류", "API 키를 설정 파일에 저장하는 데 실패했습니다.")
            self.put_message_in_queue(MSG_TYPE_STATUS, "오류: API 키 저장 실패")


    def on_chunk_size_changed(self):
        # ... (기존 코드와 유사, self.config 사용, 메시지는 큐로) ...
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


    def toggle_main_buttons_state(self, state):
        self.translate_button.config(state=state)
        self.load_file_button.config(state=state)
        # save_file_button은 번역 결과가 있을 때만 활성화되도록 별도 관리 가능
        # self.save_api_key_button, self.chunk_size_spinbox 등은 작업 중에도 사용 가능하도록 둠

    def request_cancel_operation(self):
        if self.current_operation_thread and self.current_operation_thread.is_alive():
            self.cancel_requested.set() # 취소 이벤트 설정
            self.put_message_in_queue(MSG_TYPE_STATUS, "작업 취소 요청 중...")
            self.cancel_button.config(state=tk.DISABLED) # 중복 클릭 방지

    def _start_operation_thread(self, target_function, args_tuple):
        """공통 스레드 시작 로직"""
        if self.current_operation_thread and self.current_operation_thread.is_alive():
            messagebox.showwarning("작업 중", "이미 다른 작업이 진행 중입니다.")
            return False

        self.cancel_requested.clear() # 새 작업 시작 전 취소 플래그 초기화
        self.toggle_main_buttons_state(tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.progress_var.set(0) # 프로그레스 바 초기화

        self.current_operation_thread = threading.Thread(
            target=target_function,
            args=args_tuple,
            daemon=True
        )
        self.current_operation_thread.start()
        return True

    def translate_action_gui(self):
        original_content = self.original_text_area.get("1.0", tk.END).strip()
        if not self.api_key: # API 키 체크는 메인 스레드에서
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
        operation_status = None # "cancelled", "error", None (success)
        try:
            self.put_message_in_queue(MSG_TYPE_STATUS, f"번역 작업 시작 (청크: {chunk_size}줄)")
            
            final_translation = self.text_processor.translate_by_chunks(
                original_content, api_key, chunk_size, self.cancel_requested
            )

            if self.cancel_requested.is_set():
                operation_status = "cancelled"
                # self.put_message_in_queue(MSG_TYPE_STATUS, "번역 작업 취소됨.") # operation_complete에서 처리
            elif final_translation is not None:
                self.put_message_in_queue(MSG_TYPE_RESULT, final_translation)
                self.put_message_in_queue(MSG_TYPE_STATUS, "번역 작업 완료.")
            else: # 번역 실패 (translate_by_chunks가 None 반환 시)
                operation_status = "error"
                # self.put_message_in_queue(MSG_TYPE_ERROR, "번역 작업 중 오류 발생 또는 데이터 없음.") # translator에서 이미 처리했을 수 있음

        except Exception as e:
            operation_status = "error"
            self.put_message_in_queue(MSG_TYPE_ERROR, f"번역 스레드 예외: {e}")
        finally:
            self.put_message_in_queue(MSG_TYPE_OPERATION_COMPLETE, operation_status)


    def load_file_action_gui(self):
        if self.unsaved_translation:
            if not messagebox.askokcancel("확인", "저장되지 않은 번역 내용이 있습니다. 계속 진행하시겠습니까?"):
                return
        
        self.put_message_in_queue(MSG_TYPE_STATUS, "파일 로드 시작... (스레드 준비 중)")
        if self._start_operation_thread(self.load_file_thread_target, ()):
             self.put_message_in_queue(MSG_TYPE_STATUS, "파일 로드 스레드 시작됨.")


    def load_file_thread_target(self):
        operation_status = None
        try:
            # FileHandler의 load_file 메소드가 (filepath, content, is_csv) 또는 오류 시 None 등을 반환하도록 수정 필요
            # FileHandler의 load_file은 이제 GUI app 인스턴스를 통해 큐에 직접 메시지를 보낼 수 있음
            # 또는 여기서 결과를 받아 큐에 넣음
            filepath, content, is_csv = self.file_handler.load_file_core(self.cancel_requested) # 핵심 로직 분리

            if self.cancel_requested.is_set():
                operation_status = "cancelled"
            elif filepath is not None: # 성공
                self.put_message_in_queue(MSG_TYPE_FILE_LOAD_RESULT, (filepath, content, is_csv))
            else: # 실패 (FileHandler에서 이미 메시지박스 띄웠을 수 있음)
                operation_status = "error"
                # self.put_message_in_queue(MSG_TYPE_STATUS, "파일 로드 실패 또는 취소됨.") # FileHandler가 처리

        except Exception as e:
            operation_status = "error"
            self.put_message_in_queue(MSG_TYPE_ERROR, f"파일 로드 스레드 예외: {e}")
        finally:
            self.put_message_in_queue(MSG_TYPE_OPERATION_COMPLETE, operation_status)


    def save_file_action_gui(self):
        # 파일 저장은 보통 빠르므로 스레딩 필수 아님. 단, 매우 큰 파일이면 고려.
        # 여기서는 동기적으로 처리
        content_to_save = self.translated_text_area.get("1.0", tk.END).strip()
        initial_filename = "translated_output.txt"
        if self.is_csv_mode:
             initial_filename = "translated_output.csv"
        
        if self.file_handler.save_file(content_to_save, initial_filename): # save_file이 성공/실패 bool 반환 가정
            self.unsaved_translation = False # save_file 내부에서도 처리 가능
            self.put_message_in_queue(MSG_TYPE_STATUS, "파일 저장 완료.")
        else:
            self.put_message_in_queue(MSG_TYPE_STATUS, "파일 저장 실패 또는 취소됨.")


    def on_closing(self):
        if self.current_operation_thread and self.current_operation_thread.is_alive():
            if messagebox.askokcancel("작업 중 종료", "진행 중인 작업이 있습니다. 정말로 종료하시겠습니까?\n(작업이 즉시 중단되지 않을 수 있습니다.)"):
                self.request_cancel_operation() # 취소 요청
                # 스레드가 완전히 종료될 때까지 기다리거나, 바로 destroy 할 수 있음
                # 안전하게는 스레드 종료를 기다리는 로직이 필요하나, 여기서는 단순화
                self.master.destroy()
            return

        if self.unsaved_translation:
            if messagebox.askokcancel("종료 확인", "저장되지 않은 번역 내용이 있습니다. 정말로 종료하시겠습니까?"):
                self.master.destroy()
        else:
            self.master.destroy()