# core/file_handler.py
import os
# from tkinter import filedialog, messagebox # GUI 종속성은 app_instance.put_message_in_queue 로 전달
import time

MSG_TYPE_STATUS = "status" # main_window 와 동일한 메시지 타입 사용
MSG_TYPE_ERROR = "error"

class FileHandler:
    def __init__(self, app_instance):
        self.app = app_instance

    def load_file_core(self, cancel_event=None, filepath_from_gui=None):
        """실제 파일 로딩 로직 (스레드에서 호출 가능)"""
        if not filepath_from_gui: # GUI에서 파일 경로를 받지 못했다면 (예: 테스트용)
            # 이 부분은 GUI의 filedialog를 대체할 수 없음. GUI에서 경로를 받아 전달해야 함.
            # 여기서는 filepath_from_gui가 항상 제공된다고 가정.
            self.app.put_message_in_queue(MSG_TYPE_ERROR, "파일 경로가 제공되지 않았습니다.")
            return None, None, False
        
        filepath = filepath_from_gui

        # file_extension = os.path.splitext(filepath)[1].lower() # GUI에서 이미 처리 가능
        encodings_to_try = ['utf-8', 'cp1252', 'latin-1', 'euc-kr', 'cp949']
        content_to_display = None
        is_csv_mode = filepath.lower().endswith(".csv")

        try:
            loaded_encoding = None
            self.app.put_message_in_queue(MSG_TYPE_STATUS, f"파일 읽는 중: {os.path.basename(filepath)}...")
            
            # 파일을 조금씩 읽으면서 cancel_event 확인 (매우 큰 파일의 경우)
            # 여기서는 일단 한 번에 읽는 방식 유지, GUI가 멈추지 않도록 스레드에서 실행
            with open(filepath, "rb") as f_bytes:
                raw_content_bytes = f_bytes.read() # 이 부분이 블로킹
            
            if cancel_event and cancel_event.is_set():
                self.app.put_message_in_queue(MSG_TYPE_STATUS, "파일 로드 취소됨 (읽기 중).")
                return None, None, False

            self.app.put_message_in_queue(MSG_TYPE_STATUS, "인코딩 확인 중...")
            for i, enc in enumerate(encodings_to_try):
                if cancel_event and cancel_event.is_set():
                    self.app.put_message_in_queue(MSG_TYPE_STATUS, "파일 로드 취소됨 (인코딩 중).")
                    return None, None, False
                try:
                    content_to_display = raw_content_bytes.decode(enc)
                    loaded_encoding = enc
                    self.app.put_message_in_queue(MSG_TYPE_STATUS, f"인코딩 감지: {loaded_encoding}")
                    break 
                except UnicodeDecodeError:
                    self.app.put_message_in_queue(MSG_TYPE_STATUS, f"인코딩 시도 실패: {enc}")
                time.sleep(0.01) # 아주 짧은 딜레이로 취소 감지 기회

            if loaded_encoding is None:
                self.app.put_message_in_queue(MSG_TYPE_ERROR, f"파일 인코딩을 확인할 수 없습니다: {filepath}")
                return None, None, False

            # self.app.unsaved_translation = False # 이건 GUI 로직에서 처리
            return filepath, content_to_display, is_csv_mode

        except FileNotFoundError:
            self.app.put_message_in_queue(MSG_TYPE_ERROR, f"파일을 찾을 수 없습니다: {filepath}")
            return None, None, False
        except Exception as e:
            self.app.put_message_in_queue(MSG_TYPE_ERROR, f"파일 처리 중 알 수 없는 오류 발생: {e}")
            return None, None, False

    def save_file(self, content_to_save, initial_filename_suggestion, filepath_from_gui=None):
        """실제 파일 저장 로직. filepath_from_gui는 filedialog 결과를 받음."""
        if not content_to_save:
            # self.app.put_message_in_queue(MSG_TYPE_ERROR, "저장할 내용이 없습니다.") # GUI에서 처리
            return False 

        if not filepath_from_gui:
            self.app.put_message_in_queue(MSG_TYPE_ERROR, "저장할 파일 경로가 지정되지 않았습니다.")
            return False
            
        filepath = filepath_from_gui
        self.app.put_message_in_queue(MSG_TYPE_STATUS, f"파일 저장 중: {os.path.basename(filepath)}...")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            # self.app.unsaved_translation = False # GUI에서 처리
            self.app.put_message_in_queue(MSG_TYPE_STATUS, f"파일 저장 완료: {os.path.basename(filepath)}")
            return True
        except Exception as e:
            self.app.put_message_in_queue(MSG_TYPE_ERROR, f"파일 저장 중 오류 발생: {e}")
            return False