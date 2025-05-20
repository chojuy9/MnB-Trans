# core/translator.py
import re
import time
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
# from tkinter import messagebox # GUI 종속성 제거

# 메시지 타입 (main_window와 일치 또는 공유)
MSG_TYPE_PROGRESS = "progress"
MSG_TYPE_STATUS = "status"
MSG_TYPE_ERROR = "error" # 오류 발생 시 사용

DEFAULT_CHUNK_SIZE_FOR_TRANSLATOR = 50

class TextProcessor:
    def __init__(self, app_instance):
        self.app = app_instance # Main GUI app instance for callbacks (e.g., put_message_in_queue)

    def mnb_preprocess_text(self, text):
        # ... (기존과 동일) ...
        replacements = {
            r"(\{s\d+\})": r"__MNBTAG_S\1__",
            r"(\{reg\d+\})": r"__MNBTAG_REG\1__",
            r"(\{player_name\})": r"__MNBTAG_PLAYERNAME__",
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)
        return text

    def mnb_postprocess_text(self, text):
        # ... (기존과 동일) ...
        replacements_restore = {
            r"__MNBTAG_S(\{s\d+\})__": r"\1",
            r"__MNBTAG_REG(\{reg\d+\})__": r"\1",
            r"__MNBTAG_PLAYERNAME__": r"{player_name}",
        }
        for pattern, replacement in replacements_restore.items():
            text = re.sub(pattern, replacement, text)
        text = re.sub(r"{\s*([a-zA-Z_0-9]+)\s*}", r"{\1}", text)
        return text

    def _call_single_chunk_api(self, chunk_text, api_key, model_name, cancel_event):
        """단일 청크 API 호출. 취소 기능 지원."""
        if cancel_event.is_set():
            # self.app.put_message_in_queue(MSG_TYPE_STATUS, "API 호출 전 취소됨 (청크)")
            return "CANCELLED" # 취소되었음을 알리는 특별한 문자열

        # genai.configure는 스레드에 안전한지 확인 필요.
        # 일반적으로 API 클라이언트 객체를 생성하여 사용하는 것이 더 안전할 수 있음.
        # 여기서는 기존 방식 유지.
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        prompt = f"""...""" # 프롬프트 동일 (이전 코드 참고)
        
        # API 호출 자체가 블로킹이므로, 호출 중 cancel_event 확인은 어려움.
        # 타임아웃 설정 등으로 너무 긴 호출을 방지할 수 있음.
        # 여기서는 호출 전/후에만 cancel_event 확인.
        
        # self.app.put_message_in_queue(MSG_TYPE_STATUS, f"API 호출 중 ({model_name})...") # 호출자에서 관리
        try:
            response = model.generate_content(prompt) # 이 부분이 블로킹
            if cancel_event.is_set(): # 호출 후에도 확인
                return "CANCELLED"
            return response.text
        except Exception as e: # 모든 예외를 잡아서 호출자에게 전달
            if cancel_event.is_set(): # 예외 발생 중 취소 요청 확인
                return "CANCELLED"
            raise e # 예외를 다시 발생시켜 호출자가 상세 처리


    def translate_by_chunks(self, full_text, api_key, chunk_size_lines=DEFAULT_CHUNK_SIZE_FOR_TRANSLATOR, cancel_event=None):
        if cancel_event and cancel_event.is_set():
            return None # 또는 "CANCELLED"

        if not api_key:
            self.app.put_message_in_queue(MSG_TYPE_ERROR, "API 키가 설정되지 않았습니다 (청크 번역).")
            return None

        lines = full_text.splitlines(keepends=True)
        if not lines: # 빈 텍스트면 바로 반환
            self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (0,0)) # 진행률 0
            return ""

        translated_chunks = []
        total_lines = len(lines)
        total_chunks = (total_lines + chunk_size_lines - 1) // chunk_size_lines
        
        # 진행률 초기화
        self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (0, total_chunks if total_chunks > 0 else 1))

        model_name = 'gemini-2.5-flash-preview-04-17' # 설정 또는 상수

        for i in range(total_chunks):
            if cancel_event and cancel_event.is_set():
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks} 처리 전 취소됨.")
                return "CANCELLED" # 취소 시 특별 반환값

            chunk_start_line = i * chunk_size_lines
            chunk_end_line = min((i + 1) * chunk_size_lines, total_lines)
            current_chunk_lines = lines[chunk_start_line:chunk_end_line]
            current_chunk_text = "".join(current_chunk_lines)

            if not current_chunk_text.strip():
                translated_chunks.append(current_chunk_text)
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks}: 내용 없음, 원본 유지.")
                self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (i + 1, total_chunks))
                continue

            self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks} 전처리 중...")
            preprocessed_chunk = self.mnb_preprocess_text(current_chunk_text)
            
            translated_chunk_raw = None
            api_error_occurred = False
            try:
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks} API 호출 ({model_name})...")
                translated_chunk_raw = self._call_single_chunk_api(preprocessed_chunk, api_key, model_name, cancel_event)

                if translated_chunk_raw == "CANCELLED":
                    return "CANCELLED"

            except google_exceptions.PermissionDenied as e_perm:
                self.app.put_message_in_queue(MSG_TYPE_ERROR, f"청크 {i+1}: API 권한 오류 - {e_perm}")
                api_error_occurred = True
            except google_exceptions.ResourceExhausted as e_res:
                self.app.put_message_in_queue(MSG_TYPE_ERROR, f"청크 {i+1}: API 리소스 오류 - {e_res}")
                api_error_occurred = True
            except google_exceptions.DeadlineExceeded as e_dead:
                self.app.put_message_in_queue(MSG_TYPE_ERROR, f"청크 {i+1}: API 시간 초과 - {e_dead}")
                api_error_occurred = True
            except google_exceptions.GoogleAPIError as e_gapi:
                self.app.put_message_in_queue(MSG_TYPE_ERROR, f"청크 {i+1}: Google API 오류 - {e_gapi}")
                api_error_occurred = True
            except Exception as e_api:
                self.app.put_message_in_queue(MSG_TYPE_ERROR, f"청크 {i+1}: API 호출 중 알 수 없는 오류 ({type(e_api).__name__}) - {e_api}")
                api_error_occurred = True
            
            if api_error_occurred:
                translated_chunks.append(current_chunk_text) # 오류 시 원본 사용
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks}: 오류로 원본 사용.")
                # (선택) 심각한 API 오류 시 전체 중단 로직 추가 가능
                # if isinstance(e_api, google_exceptions.PermissionDenied): return None
            elif translated_chunk_raw:
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks} 후처리 중...")
                final_translated_chunk = self.mnb_postprocess_text(translated_chunk_raw.strip())
                translated_chunks.append(final_translated_chunk)
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks} 번역 완료.")
            else: # translated_chunk_raw is None or empty (but not "CANCELLED" or error)
                translated_chunks.append(current_chunk_text) # 예기치 않은 경우 원본 사용
                self.app.put_message_in_queue(MSG_TYPE_STATUS, f"청크 {i+1}/{total_chunks}: API 응답 없음, 원본 사용.")

            self.app.put_message_in_queue(MSG_TYPE_PROGRESS, (i + 1, total_chunks))
            
            if cancel_event and cancel_event.is_set(): # 각 청크 처리 후에도 취소 확인
                self.app.put_message_in_queue(MSG_TYPE_STATUS, "작업 취소됨 (청크 처리 중).")
                return "CANCELLED"
            
            time.sleep(0.1) # API 과부하 방지 및 취소 요청 감지 시간 확보 (선택적)

        if cancel_event and cancel_event.is_set():
            return "CANCELLED"
            
        return "".join(translated_chunks)